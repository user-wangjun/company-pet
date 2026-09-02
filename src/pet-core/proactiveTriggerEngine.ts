import type {
  ProactiveExpressionStorage,
  ProactiveTaskDecisionOutcome,
  ProactiveTaskDeliveryContext,
  ProactiveTaskDeliveryReceipt,
  ProactiveTaskPreferenceMode,
  ProactiveTaskDeliveryReservationStatus,
  ProactiveTaskState,
  QuietHoursWindow,
} from "./proactiveExpressionGate";
import {
  createProactiveTaskState,
  evaluateProactiveSemanticEvent,
  localDateId,
  readProactiveExpressionState,
  recordProactiveSemanticEventSuccess,
  writeProactiveExpressionState,
} from "./proactiveExpressionGate";
import { PROACTIVE_BUBBLE_MIN_INTERVAL_MS } from "./proactiveExpressionGate";
import {
  normalizeTaskTitle,
} from "./companionTaskExtractor";
import type {
  Task,
  TaskDatabase,
  TaskPriority,
  TaskStatus,
  TriggeredReminder,
} from "../task-core/types";

export const PROACTIVE_TASK_DAILY_LIMIT = 3;
export const PROACTIVE_TASK_COOLDOWN_MS = 4 * 60 * 60 * 1000;
export const PROACTIVE_REDUCED_TASK_COOLDOWN_MS = 12 * 60 * 60 * 1000;
export const PROACTIVE_TASK_AGGREGATION_WINDOW_MS = 30 * 60 * 1000;
export const PROACTIVE_TASK_TIME_WINDOW_MS = 60 * 60 * 1000;
export const PROACTIVE_TASK_DECISION_LOG_LIMIT = 200;
export const PROACTIVE_TASK_DELIVERED_KEY_LIMIT = 256;

/**
 * Only the Task/Reminder domain adapter may construct this proof. The engine
 * deliberately accepts no title, note, chat text, or mutable candidate data.
 */
export type ProactiveDeliveryTerminalProof = {
  eventId: string;
  authority: "task-reminder-domain";
  status: "terminal";
};

export type ProactiveTaskCandidateStatus = "scheduled" | "triggered" | "missed";

export type ProactiveTaskCandidate = {
  taskId: string;
  reminderId: string;
  reminderInstanceId: string;
  title: string;
  priority: TaskPriority;
  taskStatus: TaskStatus;
  deletedAt: string | null;
  scheduledAt: string;
  triggeredAt: string | null;
  status: ProactiveTaskCandidateStatus;
  categoryKey?: string;
  /** Stable CompanionEvent id used as the idempotency key when available. */
  eventId?: string;
};

export type ProactiveTriggerResult = ProactiveTaskDecisionOutcome;

export type ProactiveTriggerDecision = {
  taskId: string;
  reminderInstanceId: string;
  candidateKey: string;
  result: ProactiveTriggerResult;
  score: number;
  priority: TaskPriority;
  reason: string;
  explanation: string;
  nextEligibleAt: string | null;
  petId: string;
  actualDelivery: boolean;
  /** Policy may allow or reserve a delivery before a local sink confirms it. */
  deliveryStatus?: "allowed" | "reserved" | "delivered" | "blocked";
  aggregateOf?: string;
  aggregatedTaskIds?: string[];
};

export type ProactiveTriggerEvaluation = {
  decisions: ProactiveTriggerDecision[];
  state: ReturnType<typeof readProactiveExpressionState>;
  /** Whether the non-delivery evaluation timestamp was durably recorded. */
  evaluationPersistenceConfirmed: boolean;
  /** Policy-approved candidates; these are not sink confirmations. */
  eligibleDeliveries: Array<{
    decision: ProactiveTriggerDecision;
    candidates: ProactiveTaskCandidate[];
  }>;
  /** Kept as an explicit empty list so callers cannot mistake policy for delivery. */
  deliveries: Array<{
    decision: ProactiveTriggerDecision;
    candidates: ProactiveTaskCandidate[];
  }>;
};

export type ProactiveDeliveryReservation = {
  status: "reserved" | "already-delivered" | "already-reserved" | "blocked" | "storage-failed" | "not-eligible";
  candidateKeys: string[];
  taskIds: string[];
  decision: ProactiveTriggerDecision;
  /** Present for a successful reservation; shared by all member receipts. */
  reservationGroupId?: string;
  /** Present for a successful reservation; quota belongs to this local date. */
  reservationLocalDate?: string;
};

export type ProactiveDeliveryConfirmation = {
  status: "confirmed" | "already-delivered" | "not-reserved" | "confirmation-failed";
  candidateKeys: string[];
  taskIds: string[];
  decisions: ProactiveTriggerDecision[];
};

export type ProactiveTaskPreferencePatch = {
  mode?: ProactiveTaskPreferenceMode;
  preferredPetId?: string | null;
};

export class ProactivePreferencePersistenceError extends Error {
  constructor() {
    super("Failed to persist proactive task preference.");
    this.name = "ProactivePreferencePersistenceError";
  }
}

export type ProactivePreferenceCommand = {
  action: "mute" | "reduce" | "switch_pet";
  targetTitle: string | null;
};

export type ProactiveTriggerEngineOptions = {
  storage?: ProactiveExpressionStorage | null;
  activePetId: string;
  availablePetIds?: readonly string[];
  dailyLimit?: number;
  quietHours?: QuietHoursWindow;
  taskCooldownMs?: number;
  reducedTaskCooldownMs?: number;
  aggregationWindowMs?: number;
  timeWindowMs?: number;
  /** Domain-owned proof verifier; cleanup is disabled when absent. */
  verifyTerminalReceipt?: (proof: ProactiveDeliveryTerminalProof) => boolean;
};

type PreparedCandidate = {
  candidate: ProactiveTaskCandidate;
  candidateKey: string;
  petId: string;
  score: number;
  candidateTimeMs: number;
  titleProfile: TaskTitleProfile;
};

type TaskTitleProfile = {
  normalized: string;
  bigrams: Set<string>;
};

function validDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? date : null;
}

function candidateTime(candidate: ProactiveTaskCandidate, fallback: Date): Date {
  return validDate(candidate.scheduledAt) ?? validDate(candidate.triggeredAt) ?? fallback;
}

function candidateKey(
  candidate: ProactiveTaskCandidate,
  now: Date,
  timeWindowMs: number,
): string {
  if (candidate.eventId && candidate.eventId.trim()) return candidate.eventId;
  const time = candidateTime(candidate, now).getTime();
  const windowStart = Math.floor(time / timeWindowMs) * timeWindowMs;
  return `${candidate.taskId}|${new Date(windowStart).toISOString()}`;
}

function taskStateOf(state: ReturnType<typeof readProactiveExpressionState>): ProactiveTaskState {
  const taskState = state.taskState ?? createProactiveTaskState();
  return taskState.deliveryReceipts
    ? taskState
    : {
        ...taskState,
        deliveryReservations: taskState.deliveryReservations ?? {},
        deliveryReceipts: {},
        deliveryReservationTaskIds: taskState.deliveryReservationTaskIds ?? {},
      };
}

/**
 * Daily quota is measured in actual delivery groups, not event receipts.
 * Every receipt in an aggregate shares one group id, while a reserved group
 * from a previous local date remains an at-most-once barrier but does not
 * consume the current day's quota.
 */
export function countCurrentProactiveReservationGroups(
  taskState: ProactiveTaskState,
  now: Date,
): number {
  if (!Number.isFinite(now.getTime())) return Number.POSITIVE_INFINITY;
  const currentLocalDate = localDateId(now);
  const groups = new Set<string>();
  for (const receipt of Object.values(taskState.deliveryReceipts ?? {})) {
    if (!receipt || typeof receipt !== "object") return Number.POSITIVE_INFINITY;
    if (
      receipt.status === "reserved"
      && receipt.reservationLocalDate === currentLocalDate
      && typeof receipt.reservationGroupId === "string"
      && receipt.reservationGroupId.length > 0
    ) {
      groups.add(receipt.reservationGroupId);
    }
    // A typed caller may still hand us a pre-receipt projection directly.
    // Count that opaque reservation conservatively instead of silently
    // reopening quota when it has not gone through storage migration.
  }
  for (const [key, status] of Object.entries(taskState.deliveryReservations ?? {})) {
    if (status === "reserved" && !taskState.deliveryReceipts?.[key]) {
      groups.add(`legacy-unmigrated:${key}`);
    }
  }
  return groups.size;
}

function reservationGroupIdForDecision(decision: ProactiveTriggerDecision): string {
  const encoded = Array.from(decision.candidateKey)
    .map((character) => character.codePointAt(0)!.toString(16))
    .join(".");
  return `proactive-reservation:v1:${encoded}`;
}

function withTaskState(
  state: ReturnType<typeof readProactiveExpressionState>,
  taskState: ProactiveTaskState,
): ReturnType<typeof readProactiveExpressionState> {
  return { ...state, taskState };
}

function preferenceFor(taskState: ProactiveTaskState, taskId: string) {
  return taskState.preferences[taskId] ?? { mode: "normal" as const, preferredPetId: null };
}

function recordFor(taskState: ProactiveTaskState, taskId: string) {
  return taskState.records[taskId] ?? { lastDeliveredAt: null, ignoredStreak: 0 };
}

function choosePet(
  taskState: ProactiveTaskState,
  taskId: string,
  activePetId: string,
  availablePetIds: readonly string[],
): string {
  const preferredPetId = preferenceFor(taskState, taskId).preferredPetId;
  // An explicit but unavailable preference is a hard route failure. Falling
  // back to the active pet would silently violate the user's selected-pet
  // contract and could render the same event twice under two identities.
  if (preferredPetId) return preferredPetId;
  if (availablePetIds.includes(activePetId)) return activePetId;
  return availablePetIds[0] ?? activePetId;
}

function scoreCandidate(
  candidate: ProactiveTaskCandidate,
  taskState: ProactiveTaskState,
): number {
  const priorityScore: Record<TaskPriority, number> = { high: 0.92, normal: 0.68, low: 0.44 };
  const preference = preferenceFor(taskState, candidate.taskId);
  const ignoredStreak = recordFor(taskState, candidate.taskId).ignoredStreak;
  const missedBonus = candidate.status === "missed" ? 0.08 : 0;
  const reducedPenalty = preference.mode === "reduced" ? 0.12 : 0;
  const ignoredPenalty = Math.min(0.24, ignoredStreak * 0.06);
  return Math.max(0, Math.min(1, priorityScore[candidate.priority] + missedBonus - reducedPenalty - ignoredPenalty));
}

function taskTitleProfile(title: string): TaskTitleProfile {
  const normalized = normalizeTaskTitle(title);
  const characters = Array.from(normalized);
  return {
    normalized,
    bigrams: new Set(
      characters.length > 1
        ? characters.slice(0, -1).map((_, index) => characters.slice(index, index + 2).join(""))
        : characters,
    ),
  };
}

function areTaskTitleProfilesSimilar(left: TaskTitleProfile, right: TaskTitleProfile): boolean {
  if (!left.normalized || !right.normalized) return false;
  if (
    left.normalized === right.normalized
    || left.normalized.includes(right.normalized)
    || right.normalized.includes(left.normalized)
  ) {
    return true;
  }
  const intersection = [...left.bigrams].filter((value) => right.bigrams.has(value)).length;
  return (2 * intersection) / (left.bigrams.size + right.bigrams.size) >= 0.72;
}

function sameAggregationGroup(
  left: PreparedCandidate,
  right: PreparedCandidate,
  aggregationWindowMs: number,
): boolean {
  if (Math.abs(left.candidateTimeMs - right.candidateTimeMs) > aggregationWindowMs) return false;
  if (
    left.candidate.categoryKey
    && right.candidate.categoryKey
    && left.candidate.categoryKey === right.candidate.categoryKey
  ) {
    return true;
  }
  return areTaskTitleProfilesSimilar(left.titleProfile, right.titleProfile);
}

function nextIsoAfter(base: Date, delayMs: number): string {
  return new Date(base.getTime() + Math.max(0, delayMs)).toISOString();
}

function appendDecisionLog(
  state: ReturnType<typeof readProactiveExpressionState>,
  decisions: readonly ProactiveTriggerDecision[],
  now: Date,
): ReturnType<typeof readProactiveExpressionState> {
  if (!decisions.length) return state;
  const taskState = taskStateOf(state);
  const logs = decisions.map((decision) => ({
    candidateKey: decision.candidateKey,
    result: decision.result,
    reason: decision.reason,
    score: decision.score,
    petId: decision.petId,
    at: now.toISOString(),
  }));
  return withTaskState(state, {
    ...taskState,
    decisionLog: [...taskState.decisionLog, ...logs].slice(-PROACTIVE_TASK_DECISION_LOG_LIMIT),
  });
}

function candidateFromTriggeredReminder(reminder: TriggeredReminder): ProactiveTaskCandidate {
  return {
    taskId: reminder.task.id,
    reminderId: reminder.reminder.id,
    reminderInstanceId: reminder.instance.id,
    title: reminder.task.title,
    priority: reminder.task.priority,
    taskStatus: reminder.task.status,
    deletedAt: reminder.task.deletedAt,
    scheduledAt: reminder.instance.scheduledAt,
    triggeredAt: reminder.instance.triggeredAt,
    status: reminder.instance.status === "missed" ? "missed" : "triggered",
  };
}

export function createProactiveTaskCandidate(
  reminder: TriggeredReminder,
): ProactiveTaskCandidate {
  return candidateFromTriggeredReminder(reminder);
}

export function selectProactiveTaskCandidates(
  database: TaskDatabase,
  now = new Date(),
): ProactiveTaskCandidate[] {
  const nowMs = now.getTime();
  return database.reminderInstances.flatMap((instance) => {
    const scheduledAt = validDate(instance.scheduledAt);
    const isDue = instance.status === "scheduled" && scheduledAt && scheduledAt.getTime() <= nowMs;
    const isReevaluation = ["triggered", "missed"].includes(instance.status) && !instance.summaryClosedAt;
    if (!isDue && !isReevaluation) return [];
    const task = database.tasks.find((item) => item.id === instance.taskId);
    const reminder = database.reminders.find((item) => item.id === instance.reminderId);
    if (!task || !reminder || reminder.status !== "active") return [];
    return [{
      taskId: task.id,
      reminderId: reminder.id,
      reminderInstanceId: instance.id,
      title: task.title,
      priority: task.priority,
      taskStatus: task.status,
      deletedAt: task.deletedAt,
      scheduledAt: instance.scheduledAt,
      triggeredAt: instance.triggeredAt,
      status: instance.status === "missed" ? "missed" : instance.status === "triggered" ? "triggered" : "scheduled",
    }];
  });
}

export function parseProactivePreferenceCommand(text: string): ProactivePreferenceCommand | null {
  const input = text.replace(/[。！？!?]+$/u, "").trim();
  if (!input) return null;

  const mute = input.match(/^(?:别再提醒|不要再提醒|不用再提醒)(?:我)?(?:这件事|这个任务|这个待办)?(?:[：:、\s]*(.+))?$/u);
  if (mute) return { action: "mute", targetTitle: mute[1]?.trim() || null };

  const reduce = input.match(/^(?:少提醒一点|少提醒|提醒少一点)(?:我)?(?:这件事|这个任务|这个待办)?(?:[：:、\s]*(.+))?$/u);
  if (reduce) return { action: "reduce", targetTitle: reduce[1]?.trim() || null };

  const switchPet = input.match(/^(?:换一只宠物|换个宠物|换宠物)(?:提醒我?|提醒)?(?:这件事|这个任务|这个待办)?(?:[：:、\s]*(.+))?$/u);
  if (switchPet) return { action: "switch_pet", targetTitle: switchPet[1]?.trim() || null };

  return null;
}

export function setProactiveTaskPreference(
  taskId: string,
  patch: ProactiveTaskPreferencePatch,
  options: Pick<ProactiveTriggerEngineOptions, "storage">,
  now = new Date(),
): ReturnType<typeof readProactiveExpressionState> {
  const state = readProactiveExpressionState(options.storage, now);
  const taskState = taskStateOf(state);
  const previous = preferenceFor(taskState, taskId);
  const nextPreference = {
    mode: patch.mode ?? previous.mode,
    preferredPetId: Object.prototype.hasOwnProperty.call(patch, "preferredPetId")
      ? patch.preferredPetId ?? null
      : previous.preferredPetId,
  };
  const next = withTaskState(state, {
    ...taskState,
    preferences: { ...taskState.preferences, [taskId]: nextPreference },
  });

  // This return value is an authoritative post-write state, not merely the
  // candidate computed above. The shared writer must confirm that persistence
  // completed before the state can be returned to a domain caller.
  if (!writeProactiveExpressionState(next, options.storage)) {
    throw new ProactivePreferencePersistenceError();
  }
  return next;
}

export function recordProactiveTaskIgnored(
  taskId: string,
  options: Pick<ProactiveTriggerEngineOptions, "storage">,
  now = new Date(),
): ReturnType<typeof readProactiveExpressionState> {
  const state = readProactiveExpressionState(options.storage, now);
  const taskState = taskStateOf(state);
  const record = recordFor(taskState, taskId);
  const next = withTaskState(state, {
    ...taskState,
    records: {
      ...taskState.records,
      [taskId]: { ...record, ignoredStreak: record.ignoredStreak + 1 },
    },
  });
  writeProactiveExpressionState(next, options.storage);
  return next;
}

export function recordProactiveTaskEngaged(
  taskId: string,
  options: Pick<ProactiveTriggerEngineOptions, "storage">,
  now = new Date(),
): ReturnType<typeof readProactiveExpressionState> {
  const state = readProactiveExpressionState(options.storage, now);
  const taskState = taskStateOf(state);
  const record = recordFor(taskState, taskId);
  const next = withTaskState(state, {
    ...taskState,
    records: {
      ...taskState.records,
      [taskId]: { ...record, ignoredStreak: 0 },
    },
  });
  writeProactiveExpressionState(next, options.storage);
  return next;
}

export function createProactiveTriggerEngine(options: ProactiveTriggerEngineOptions) {
  const storage = options.storage ?? (typeof window === "undefined" ? null : window.localStorage);
  const availablePetIds = options.availablePetIds ?? [options.activePetId];
  const dailyLimit = Number.isSafeInteger(options.dailyLimit) && (options.dailyLimit ?? 0) > 0
    ? options.dailyLimit!
    : PROACTIVE_TASK_DAILY_LIMIT;
  const taskCooldownMs = options.taskCooldownMs ?? PROACTIVE_TASK_COOLDOWN_MS;
  const reducedTaskCooldownMs = options.reducedTaskCooldownMs ?? PROACTIVE_REDUCED_TASK_COOLDOWN_MS;
  const aggregationWindowMs = options.aggregationWindowMs ?? PROACTIVE_TASK_AGGREGATION_WINDOW_MS;
  const timeWindowMs = options.timeWindowMs ?? PROACTIVE_TASK_TIME_WINDOW_MS;

  const evaluateEligibility = (
    candidates: readonly ProactiveTaskCandidate[],
    now = new Date(),
  ): ProactiveTriggerEvaluation => {
    const persistedState = readProactiveExpressionState(storage, now);
    const persistedTaskState = taskStateOf(persistedState);
    let policyState = persistedState;
    const decisions: ProactiveTriggerDecision[] = [];
    const prepared: PreparedCandidate[] = [];

    for (const candidate of candidates) {
      const key = candidateKey(candidate, now, timeWindowMs);
      const petId = choosePet(persistedTaskState, candidate.taskId, options.activePetId, availablePetIds);
      const score = scoreCandidate(candidate, persistedTaskState);
      const preference = preferenceFor(persistedTaskState, candidate.taskId);
      const record = recordFor(persistedTaskState, candidate.taskId);
      const lastDeliveredAt = validDate(record.lastDeliveredAt);
      const baseCooldown = preference.mode === "reduced" ? reducedTaskCooldownMs : taskCooldownMs;
      const ignoreBackoff = record.ignoredStreak >= 2
        ? baseCooldown * Math.min(8, 2 ** Math.min(record.ignoredStreak - 1, 3))
        : baseCooldown;
      const cooldown = record.ignoredStreak >= 2 ? ignoreBackoff : baseCooldown;
      const reservationStatus = persistedTaskState.deliveryReservations?.[key];

      if (candidate.deletedAt || !["pending", "in_progress"].includes(candidate.taskStatus)) {
        decisions.push({
          taskId: candidate.taskId,
          reminderInstanceId: candidate.reminderInstanceId,
          candidateKey: key,
          result: "suppress",
          score,
          priority: candidate.priority,
          reason: "task-not-active",
          explanation: "任务已完成、取消或删除，不再生成主动提醒。",
          nextEligibleAt: null,
          petId,
          actualDelivery: false,
        });
        continue;
      }
      if (persistedTaskState.deliveryReceipts?.[key]?.status === "confirmed") {
        decisions.push({
          taskId: candidate.taskId,
          reminderInstanceId: candidate.reminderInstanceId,
          candidateKey: key,
          result: "suppress",
          score,
          priority: candidate.priority,
          reason: "already-delivered",
          explanation: "同一事件已经收到本地投递确认。",
          nextEligibleAt: null,
          petId,
          actualDelivery: false,
          deliveryStatus: "delivered",
        });
        continue;
      }
      if (reservationStatus) {
        decisions.push({
          taskId: candidate.taskId,
          reminderInstanceId: candidate.reminderInstanceId,
          candidateKey: key,
          result: "suppress",
          score,
          priority: candidate.priority,
          reason: reservationStatus === "blocked" ? "delivery-blocked" : "delivery-reserved",
          explanation: reservationStatus === "blocked"
            ? "这次本地投递未确认成功，已阻止重复气泡。"
            : "这次事件已有持久化投递占位，等待同一处理结果。",
          nextEligibleAt: null,
          petId,
          actualDelivery: false,
          deliveryStatus: "blocked",
        });
        continue;
      }
      if (preference.mode === "muted") {
        decisions.push({
          taskId: candidate.taskId,
          reminderInstanceId: candidate.reminderInstanceId,
          candidateKey: key,
          result: "suppress",
          score,
          priority: candidate.priority,
          reason: "muted-task",
          explanation: "你已选择不再提醒这件事。",
          nextEligibleAt: null,
          petId,
          actualDelivery: false,
        });
        continue;
      }
      if (lastDeliveredAt) {
        const nextEligibleAt = new Date(lastDeliveredAt.getTime() + cooldown);
        if (now.getTime() < nextEligibleAt.getTime()) {
          decisions.push({
            taskId: candidate.taskId,
            reminderInstanceId: candidate.reminderInstanceId,
            candidateKey: key,
            result: "delay",
            score,
            priority: candidate.priority,
            reason: record.ignoredStreak >= 2 ? "ignored-backoff" : preference.mode === "reduced" ? "reduced-frequency" : "task-cooldown",
            explanation: record.ignoredStreak >= 2
              ? "连续忽略后已自动拉长提醒间隔。"
              : preference.mode === "reduced"
                ? "你已选择降低这件事的提醒频率。"
                : "同一任务仍在单任务冷却期内。",
            nextEligibleAt: nextEligibleAt.toISOString(),
            petId,
            actualDelivery: false,
          });
          continue;
        }
      }
      const preparedTime = candidateTime(candidate, now);
      prepared.push({
        candidate,
        candidateKey: key,
        petId,
        score,
        candidateTimeMs: preparedTime.getTime(),
        titleProfile: taskTitleProfile(candidate.title),
      });
    }

    const eligibleDeliveries: Array<{
      decision: ProactiveTriggerDecision;
      candidates: ProactiveTaskCandidate[];
    }> = [];
    if (prepared.length > 0) {
      const groups: PreparedCandidate[][] = [];
      for (const item of prepared.sort((left, right) => right.score - left.score || left.candidateKey.localeCompare(right.candidateKey))) {
        const group = groups.find((existing) => sameAggregationGroup(existing[0], item, aggregationWindowMs));
        if (group) group.push(item);
        else groups.push([item]);
      }

      for (const group of groups) {
        const primary = group[0];
        const currentReservationGroups = countCurrentProactiveReservationGroups(
          taskStateOf(policyState),
          now,
        );
        if (policyState.bubbleCounts.task_reminder + currentReservationGroups >= dailyLimit) {
          for (const item of group) {
            decisions.push({
              taskId: item.candidate.taskId,
              reminderInstanceId: item.candidate.reminderInstanceId,
              candidateKey: item.candidateKey,
              result: "suppress",
              score: item.score,
              priority: item.candidate.priority,
              reason: "daily-limit",
              explanation: `今天的主动任务提醒已达到用户上限（${dailyLimit} 次）。`,
              nextEligibleAt: null,
              petId: item.petId,
              actualDelivery: false,
            });
          }
          continue;
        }

        const gateDecision = evaluateProactiveSemanticEvent({
          event: "task_reminder",
          state: policyState,
          now,
          quietHours: options.quietHours,
        });
        policyState = gateDecision.state;
        if (!gateDecision.bubbleAllowed) {
          const isDelay = gateDecision.reason === "bubble-cooldown";
          const nextEligibleAt = isDelay && policyState.lastActiveBubbleAt
            ? nextIsoAfter(new Date(policyState.lastActiveBubbleAt), 45 * 60 * 1000)
            : null;
          for (const item of group) {
            decisions.push({
              taskId: item.candidate.taskId,
              reminderInstanceId: item.candidate.reminderInstanceId,
              candidateKey: item.candidateKey,
              result: isDelay ? "delay" : "suppress",
              score: item.score,
              priority: item.candidate.priority,
              reason: isDelay ? "global-bubble-cooldown" : gateDecision.reason,
              explanation: isDelay
                ? "最近已经有主动气泡，稍后再提醒。"
                : gateDecision.reason === "quiet-hours"
                  ? "当前处于安静时段，提醒会留到下一次调度评估。"
                  : "主动表达门禁暂时不允许投递。",
              nextEligibleAt,
              petId: item.petId,
              actualDelivery: false,
            });
          }
          continue;
        }

        const aggregate = group.length > 1;
        const action: ProactiveTriggerResult = aggregate ? "aggregate" : "send";
        const decision: ProactiveTriggerDecision = {
          taskId: primary.candidate.taskId,
          reminderInstanceId: primary.candidate.reminderInstanceId,
          candidateKey: primary.candidateKey,
          result: action,
          score: primary.score,
          priority: primary.candidate.priority,
          reason: aggregate ? "allowed-aggregate" : "allowed",
          explanation: aggregate
            ? `将 ${group.length} 件相近任务合并成一次提醒。`
            : "任务已到期或需要重新评估，且通过主动表达门禁。",
          nextEligibleAt: null,
          petId: primary.petId,
          // Policy permission is deliberately not a delivery confirmation.
          actualDelivery: false,
          deliveryStatus: "allowed",
          aggregatedTaskIds: aggregate ? group.map((item) => item.candidate.taskId) : undefined,
        };
        decisions.push(decision);
        eligibleDeliveries.push({ decision, candidates: group.map((item) => item.candidate) });
        // Provisional state prevents two independent groups in one scan from
        // both passing the global cooldown. It is never persisted here; only
        // confirmDelivery() may turn it into a real count.
        policyState = recordProactiveSemanticEventSuccess(policyState, "task_reminder", now, true);
        for (const item of group.slice(1)) {
          decisions.push({
            taskId: item.candidate.taskId,
            reminderInstanceId: item.candidate.reminderInstanceId,
            candidateKey: item.candidateKey,
            result: "suppress",
            score: item.score,
            priority: item.candidate.priority,
            reason: "aggregated",
            explanation: `已并入「${primary.candidate.title}」的主动提醒。`,
            nextEligibleAt: null,
            petId: primary.petId,
            actualDelivery: false,
            aggregateOf: primary.candidate.taskId,
          });
        }
      }
    }

    // A scheduler scan can contain hundreds of candidates. Persisting the
    // entire expression-state JSON for every such pure policy evaluation
    // makes the scan O(candidate-count * state-size) without adding delivery
    // safety. The Phase 6 event path evaluates a small resolved batch and
    // still persists its timestamp; large batches rely on the durable
    // reserveDelivery write immediately before the sink instead.
    const shouldPersistEvaluationStamp = candidates.length <= 8;
    const stateIsConservative = !Number.isFinite(now.getTime())
      || persistedState.conservativeSilenceDate === localDateId(now);
    const evaluationPersistenceConfirmed = stateIsConservative
      ? false
      : shouldPersistEvaluationStamp
        ? writeProactiveExpressionState(
          { ...persistedState, lastEvaluatedAt: now.toISOString() },
          storage,
        )
        : true;
    return {
      decisions,
      state: persistedState,
      evaluationPersistenceConfirmed,
      eligibleDeliveries,
      // The transactional API intentionally leaves the legacy projection
      // empty. The public evaluate() wrapper below restores the old App
      // contract without claiming that a sink has run.
      deliveries: [],
    };
  };

  /**
   * Legacy App contract. App currently consumes `evaluate().deliveries`
   * directly and has no reserve/confirm callback. Preserve that old
   * compatibility path by committing its projection through the existing
   * durable reserve/confirm boundary. The Phase 6 event service never calls
   * this method; it uses evaluateEligibility() and owns the real sink.
   */
  const evaluate = (
    candidates: readonly ProactiveTaskCandidate[],
    now = new Date(),
  ): ProactiveTriggerEvaluation => {
    const evaluation = evaluateEligibility(candidates, now);
    if (!evaluation.evaluationPersistenceConfirmed) return evaluation;

    const committedByKey = new Map<string, ProactiveTriggerDecision>();
    const deliveries: ProactiveTriggerEvaluation["deliveries"] = [];
    for (const eligible of evaluation.eligibleDeliveries) {
      const reservation = reserveDelivery(eligible.decision, eligible.candidates, now);
      if (reservation.status !== "reserved") continue;
      // This is the pre-Phase-6 App compatibility path. Its existing contract
      // treats the projected delivery as committed; the new Harness event
      // path never calls evaluate() and therefore cannot inherit this legacy
      // assumption.
      const confirmation = confirmDeliveryInternal(reservation, eligible.candidates, now);
      if (confirmation.status !== "confirmed") continue;
      for (const decision of confirmation.decisions) committedByKey.set(decision.candidateKey, decision);
      const primary = confirmation.decisions.find(
        (decision) => decision.candidateKey === eligible.decision.candidateKey,
      );
      if (primary?.actualDelivery) {
        deliveries.push({ decision: primary, candidates: [...eligible.candidates] });
      }
    }
    return {
      ...evaluation,
      decisions: evaluation.decisions.map((decision) => committedByKey.get(decision.candidateKey) ?? decision),
      state: readProactiveExpressionState(storage, now),
      deliveries,
    };
  };

  const candidateKeysForDecision = (
    decision: ProactiveTriggerDecision,
    candidates: readonly ProactiveTaskCandidate[],
    now: Date,
  ): string[] => {
    const keys = decision.aggregatedTaskIds
      ? candidates
        .filter((candidate) => decision.aggregatedTaskIds?.includes(candidate.taskId))
        .map((candidate) => candidateKey(candidate, now, timeWindowMs))
      : [];
    return [...new Set([decision.candidateKey, ...keys])];
  };

  const reserveDelivery = (
    decision: ProactiveTriggerDecision,
    candidates: readonly ProactiveTaskCandidate[],
    now = new Date(),
  ): ProactiveDeliveryReservation => {
    const candidateKeys = candidateKeysForDecision(decision, candidates, now);
    const taskIds = [...new Set(decision.aggregatedTaskIds ?? [decision.taskId])];
    if (decision.result !== "send" && decision.result !== "aggregate") {
      return { status: "not-eligible", candidateKeys, taskIds, decision };
    }

    if (!Number.isFinite(now.getTime())) {
      return { status: "not-eligible", candidateKeys, taskIds, decision };
    }
    const state = readProactiveExpressionState(storage, now);
    const taskState = taskStateOf(state);
    const receipts = taskState.deliveryReceipts ?? {};
    const reservations = taskState.deliveryReservations ?? {};
    const reservationTaskIds = taskState.deliveryReservationTaskIds ?? {};
    if (candidateKeys.some((key) => receipts[key]?.status === "confirmed")) {
      return { status: "already-delivered", candidateKeys, taskIds, decision };
    }
    if (candidateKeys.some((key) => receipts[key]?.status === "blocked" || reservations[key] === "blocked")) {
      return { status: "blocked", candidateKeys, taskIds, decision };
    }
    if (candidateKeys.some((key) => receipts[key]?.status === "reserved" || reservations[key] === "reserved")) {
      return { status: "already-reserved", candidateKeys, taskIds, decision };
    }
    for (const [key, receipt] of Object.entries(receipts)) {
      if (
        !candidateKeys.includes(key)
        && (receipt.status === "reserved" || receipt.status === "blocked")
        && reservationTaskIds[key]?.some((taskId) => taskIds.includes(taskId))
      ) {
        return {
          status: receipt.status === "blocked" ? "blocked" : "already-reserved",
          candidateKeys,
          taskIds,
          decision,
        };
      }
    }

    // Re-read and re-check every shared gate immediately before the sink. The
    // service-level micro-batch prevents normal races, while this second
    // boundary keeps a different event from bypassing a just-reserved or
    // just-confirmed daily limit/cooldown when callers use the engine directly.
    if (
      state.bubbleCounts.task_reminder
        + countCurrentProactiveReservationGroups(taskState, now)
        >= dailyLimit
    ) {
      return { status: "not-eligible", candidateKeys, taskIds, decision };
    }
    const recentBubbleAt = state.lastActiveBubbleAt
      ? Date.parse(state.lastActiveBubbleAt)
      : Number.NaN;
    const hasRecentConfirmedBubble = Number.isFinite(recentBubbleAt)
      && now.getTime() - recentBubbleAt < PROACTIVE_BUBBLE_MIN_INTERVAL_MS;
    const hasRecentReservation = Object.values(receipts).some((receipt) => {
      if (receipt.status !== "reserved") return false;
      const reservedAt = Date.parse(receipt.updatedAt);
      return Number.isFinite(reservedAt)
        && now.getTime() - reservedAt < PROACTIVE_BUBBLE_MIN_INTERVAL_MS;
    });
    if (hasRecentConfirmedBubble || hasRecentReservation) {
      return { status: "not-eligible", candidateKeys, taskIds, decision };
    }

    const gateDecision = evaluateProactiveSemanticEvent({
      event: "task_reminder",
      state,
      now,
      quietHours: options.quietHours,
    });
    if (!gateDecision.bubbleAllowed) {
      return { status: "not-eligible", candidateKeys, taskIds, decision };
    }

    for (const candidate of candidates) {
      if (candidate.deletedAt || !["pending", "in_progress"].includes(candidate.taskStatus)) {
        return { status: "not-eligible", candidateKeys, taskIds, decision };
      }
    }
    for (const taskId of taskIds) {
      const preference = preferenceFor(taskState, taskId);
      if (preference.mode === "muted") {
        return { status: "not-eligible", candidateKeys, taskIds, decision };
      }
      const record = recordFor(taskState, taskId);
      const lastDeliveredAt = validDate(record.lastDeliveredAt);
      if (!lastDeliveredAt) continue;
      const baseCooldown = preference.mode === "reduced" ? reducedTaskCooldownMs : taskCooldownMs;
      const cooldown = record.ignoredStreak >= 2
        ? baseCooldown * Math.min(8, 2 ** Math.min(record.ignoredStreak - 1, 3))
        : baseCooldown;
      if (now.getTime() < lastDeliveredAt.getTime() + cooldown) {
        return { status: "not-eligible", candidateKeys, taskIds, decision };
      }
    }

    const nextReservations: Record<string, ProactiveTaskDeliveryReservationStatus> = {
      ...reservations,
    };
    const nextReceipts: Record<string, ProactiveTaskDeliveryReceipt> = {
      ...receipts,
    };
    const nextReservationTaskIds: Record<string, string[]> = {
      ...reservationTaskIds,
    };
    const reservedAt = now.toISOString();
    const reservationGroupId = reservationGroupIdForDecision(decision);
    const reservationLocalDate = localDateId(now);
    for (const key of candidateKeys) {
      nextReservations[key] = "reserved";
      nextReceipts[key] = {
        status: "reserved",
        updatedAt: reservedAt,
        reservationGroupId,
        reservationLocalDate,
      };
      nextReservationTaskIds[key] = [...taskIds];
    }
    const next = withTaskState(state, {
      ...taskState,
      deliveryReservations: nextReservations,
      deliveryReceipts: nextReceipts,
      deliveryReservationTaskIds: nextReservationTaskIds,
    });
    // The reservation is the at-most-once barrier. If it cannot be durably
    // written, the sink is never called and the event remains retryable.
    if (!writeProactiveExpressionState(next, storage)) {
      return { status: "storage-failed", candidateKeys, taskIds, decision };
    }
    return {
      status: "reserved",
      candidateKeys,
      taskIds,
      decision: { ...decision, deliveryStatus: "reserved", actualDelivery: false },
      reservationGroupId,
      reservationLocalDate,
    };
  };

  const confirmDeliveryInternal = (
    reservation: ProactiveDeliveryReservation,
    candidates: readonly ProactiveTaskCandidate[],
    now = new Date(),
  ): ProactiveDeliveryConfirmation => {
    const decision = reservation.decision;
    if (reservation.status !== "reserved") {
      return {
        status: reservation.status === "already-delivered" ? "already-delivered" : "not-reserved",
        candidateKeys: reservation.candidateKeys,
        taskIds: reservation.taskIds,
        decisions: [],
      };
    }

    const state = readProactiveExpressionState(storage, now);
    const taskState = taskStateOf(state);
    const receipts = taskState.deliveryReceipts ?? {};
    const reservations = taskState.deliveryReservations ?? {};
    if (reservation.candidateKeys.every((key) => receipts[key]?.status === "confirmed")) {
      return {
        status: "already-delivered",
        candidateKeys: reservation.candidateKeys,
        taskIds: reservation.taskIds,
        decisions: [],
      };
    }
    if (reservation.candidateKeys.some((key) => (
      receipts[key]?.status ?? reservations[key]
    ) !== "reserved")) {
      return {
        status: "not-reserved",
        candidateKeys: reservation.candidateKeys,
        taskIds: reservation.taskIds,
        decisions: [],
      };
    }

    const confirmedState = recordProactiveSemanticEventSuccess(state, "task_reminder", now, true);
    const confirmedTaskState = taskStateOf(confirmedState);
    const deliveredKeys = new Set(confirmedTaskState.deliveredKeys);
    const nextReservations = { ...(confirmedTaskState.deliveryReservations ?? {}) };
    const nextReceipts: Record<string, ProactiveTaskDeliveryReceipt> = {
      ...(confirmedTaskState.deliveryReceipts ?? {}),
    };
    const nextReservationTaskIds = { ...(confirmedTaskState.deliveryReservationTaskIds ?? {}) };
    const records = { ...confirmedTaskState.records };
    for (const key of reservation.candidateKeys) {
      const reservedReceipt = receipts[key] ?? nextReceipts[key];
      if (!reservedReceipt) {
        return {
          status: "not-reserved",
          candidateKeys: reservation.candidateKeys,
          taskIds: reservation.taskIds,
          decisions: [],
        };
      }
      deliveredKeys.add(key);
      delete nextReservations[key];
      nextReceipts[key] = {
        status: "confirmed",
        updatedAt: now.toISOString(),
        reservationGroupId: reservedReceipt.reservationGroupId,
        reservationLocalDate: reservedReceipt.reservationLocalDate,
      };
      delete nextReservationTaskIds[key];
    }
    for (const taskId of reservation.taskIds) {
      const previousRecord = recordFor(confirmedTaskState, taskId);
      records[taskId] = {
        lastDeliveredAt: now.toISOString(),
        // Delivery is not engagement. Keep the prior streak so the next
        // unattended bubble can advance it across deliveries.
        ignoredStreak: previousRecord.ignoredStreak,
      };
    }
    const deliveryContext: ProactiveTaskDeliveryContext = {
      candidateKey: decision.candidateKey,
      taskIds: reservation.taskIds,
      taskTitles: reservation.taskIds.map((taskId) =>
        candidates.find((candidate) => candidate.taskId === taskId)?.title ?? "这件事",
      ),
      petId: decision.petId,
      deliveredAt: now.toISOString(),
    };
    let nextState = withTaskState(confirmedState, {
      ...confirmedTaskState,
      records,
      deliveredKeys: [...deliveredKeys].slice(-PROACTIVE_TASK_DELIVERED_KEY_LIMIT),
      deliveryReservations: nextReservations,
      deliveryReceipts: nextReceipts,
      deliveryReservationTaskIds: nextReservationTaskIds,
      lastDeliveryContext: deliveryContext,
    });
    const confirmedDecisions: ProactiveTriggerDecision[] = [{
      ...decision,
      actualDelivery: true,
      deliveryStatus: "delivered",
    }];
    for (const candidate of candidates) {
      const key = candidateKey(candidate, now, timeWindowMs);
      if (key === decision.candidateKey || !reservation.candidateKeys.includes(key)) continue;
      confirmedDecisions.push({
        taskId: candidate.taskId,
        reminderInstanceId: candidate.reminderInstanceId,
        candidateKey: key,
        result: "suppress",
        score: decision.score,
        priority: candidate.priority,
        reason: "aggregated",
        explanation: "已并入同一次宠物主动提醒。",
        nextEligibleAt: null,
        petId: decision.petId,
        actualDelivery: false,
        aggregateOf: decision.taskId,
      });
    }
    nextState = appendDecisionLog(nextState, confirmedDecisions, now);
    if (!writeProactiveExpressionState(nextState, storage)) {
      // The pre-sink reservation remains durable, so a confirmation write
      // failure cannot make a later Harness instance call the sink again.
      return {
        status: "confirmation-failed",
        candidateKeys: reservation.candidateKeys,
        taskIds: reservation.taskIds,
        decisions: [],
      };
    }
    return {
      status: "confirmed",
      candidateKeys: reservation.candidateKeys,
      taskIds: reservation.taskIds,
      decisions: confirmedDecisions,
    };
  };

  const confirmDelivery = (
    reservation: ProactiveDeliveryReservation,
    candidates: readonly ProactiveTaskCandidate[],
    now = new Date(),
  ): ProactiveDeliveryConfirmation => confirmDeliveryInternal(reservation, candidates, now);

  const blockDelivery = (
    reservation: ProactiveDeliveryReservation,
    now = new Date(),
  ): boolean => {
    if (reservation.status !== "reserved") return false;
    const state = readProactiveExpressionState(storage, now);
    const taskState = taskStateOf(state);
    const reservations = { ...(taskState.deliveryReservations ?? {}) };
    const receipts: Record<string, ProactiveTaskDeliveryReceipt> = {
      ...(taskState.deliveryReceipts ?? {}),
    };
    const reservationTaskIds = { ...(taskState.deliveryReservationTaskIds ?? {}) };
    for (const key of reservation.candidateKeys) {
      if (receipts[key]?.status === "reserved" || reservations[key] === "reserved") {
        const reservedReceipt = receipts[key];
        if (!reservedReceipt) return false;
        reservations[key] = "blocked";
        receipts[key] = {
          status: "blocked",
          updatedAt: now.toISOString(),
          reservationGroupId: reservedReceipt.reservationGroupId,
          reservationLocalDate: reservedReceipt.reservationLocalDate,
        };
      }
    }
    // A failed block write leaves the original reservation intact, which is
    // the safer at-most-once outcome after an ambiguous sink result.
    return writeProactiveExpressionState(withTaskState(state, {
      ...taskState,
      deliveryReservations: reservations,
      deliveryReceipts: receipts,
      deliveryReservationTaskIds: reservationTaskIds,
    }), storage);
  };

  const pruneTerminalReceipts = (
    proofs: readonly ProactiveDeliveryTerminalProof[],
    now = new Date(),
  ): boolean => {
    if (!Array.isArray(proofs) || proofs.some((proof) => (
      !proof
      || typeof proof.eventId !== "string"
      || proof.eventId.trim().length === 0
      || proof.authority !== "task-reminder-domain"
      || proof.status !== "terminal"
    ))) {
      return false;
    }
    if (!options.verifyTerminalReceipt) return false;
    try {
      if (proofs.some((proof) => options.verifyTerminalReceipt?.(proof) !== true)) return false;
    } catch {
      return false;
    }
    if (proofs.length === 0) return true;

    const state = readProactiveExpressionState(storage, now);
    const taskState = taskStateOf(state);
    const receiptIds = new Set(proofs.map((proof) => proof.eventId));
    const nextReceipts = { ...(taskState.deliveryReceipts ?? {}) };
    const nextReservations = { ...(taskState.deliveryReservations ?? {}) };
    const nextReservationTaskIds = { ...(taskState.deliveryReservationTaskIds ?? {}) };
    const nextDeliveredKeys = taskState.deliveredKeys.filter((key) => !receiptIds.has(key));
    for (const eventId of receiptIds) {
      delete nextReceipts[eventId];
      delete nextReservations[eventId];
      delete nextReservationTaskIds[eventId];
    }
    const nextContext = taskState.lastDeliveryContext
      && receiptIds.has(taskState.lastDeliveryContext.candidateKey)
      ? null
      : taskState.lastDeliveryContext;

    // A failed write leaves the receipt intact, so a restart cannot resurrect
    // a live event merely because cleanup was attempted.
    return writeProactiveExpressionState(withTaskState(state, {
      ...taskState,
      deliveredKeys: nextDeliveredKeys,
      deliveryReservations: nextReservations,
      deliveryReceipts: nextReceipts,
      deliveryReservationTaskIds: nextReservationTaskIds,
      lastDeliveryContext: nextContext,
    }), storage);
  };

  return {
    evaluateEligibility,
    evaluate,
    reserveDelivery,
    confirmDelivery,
    blockDelivery,
    pruneTerminalReceipts,
    pruneDeliveryReceipts: pruneTerminalReceipts,
    getState: (now = new Date()) => readProactiveExpressionState(storage, now),
    getLastDeliveryContext: (now = new Date()) =>
      taskStateOf(readProactiveExpressionState(storage, now)).lastDeliveryContext,
    setTaskPreference: (taskId: string, patch: ProactiveTaskPreferencePatch, now = new Date()) =>
      setProactiveTaskPreference(taskId, patch, { storage }, now),
    recordIgnored: (taskId: string, now = new Date()) => recordProactiveTaskIgnored(taskId, { storage }, now),
    recordEngaged: (taskId: string, now = new Date()) => recordProactiveTaskEngaged(taskId, { storage }, now),
  };
}

export type ProactiveTriggerEngine = ReturnType<typeof createProactiveTriggerEngine>;

export function taskCandidateFromTask(
  task: Pick<Task, "id" | "title" | "priority" | "status" | "deletedAt">,
  reminder: Pick<TriggeredReminder["reminder"], "id">,
  instance: Pick<TriggeredReminder["instance"], "id" | "scheduledAt" | "triggeredAt" | "status">,
): ProactiveTaskCandidate {
  return {
    taskId: task.id,
    reminderId: reminder.id,
    reminderInstanceId: instance.id,
    title: task.title,
    priority: task.priority,
    taskStatus: task.status,
    deletedAt: task.deletedAt,
    scheduledAt: instance.scheduledAt,
    triggeredAt: instance.triggeredAt,
    status: instance.status === "missed" ? "missed" : instance.status === "scheduled" ? "scheduled" : "triggered",
  };
}

export function normalizeProactiveTaskTarget(value: string): string {
  return normalizeTaskTitle(value).replace(/^(?:这件事|这个任务|这个待办)$/u, "");
}
