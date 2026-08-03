import type {
  ProactiveExpressionStorage,
  ProactiveTaskDecisionOutcome,
  ProactiveTaskDeliveryContext,
  ProactiveTaskPreferenceMode,
  ProactiveTaskState,
  QuietHoursWindow,
} from "./proactiveExpressionGate";
import {
  createProactiveTaskState,
  evaluateProactiveSemanticEvent,
  readProactiveExpressionState,
  recordProactiveSemanticEventSuccess,
  writeProactiveExpressionState,
} from "./proactiveExpressionGate";
import {
  areTaskTitlesSimilar,
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
  aggregateOf?: string;
  aggregatedTaskIds?: string[];
};

export type ProactiveTriggerEvaluation = {
  decisions: ProactiveTriggerDecision[];
  state: ReturnType<typeof readProactiveExpressionState>;
  deliveries: Array<{
    decision: ProactiveTriggerDecision;
    candidates: ProactiveTaskCandidate[];
  }>;
};

export type ProactiveTaskPreferencePatch = {
  mode?: ProactiveTaskPreferenceMode;
  preferredPetId?: string | null;
};

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
};

type PreparedCandidate = {
  candidate: ProactiveTaskCandidate;
  candidateKey: string;
  petId: string;
  score: number;
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
  const time = candidateTime(candidate, now).getTime();
  const windowStart = Math.floor(time / timeWindowMs) * timeWindowMs;
  return `${candidate.taskId}|${new Date(windowStart).toISOString()}`;
}

function taskStateOf(state: ReturnType<typeof readProactiveExpressionState>): ProactiveTaskState {
  return state.taskState ?? createProactiveTaskState();
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
  if (preferredPetId && availablePetIds.includes(preferredPetId)) return preferredPetId;
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

function sameAggregationGroup(
  left: ProactiveTaskCandidate,
  right: ProactiveTaskCandidate,
  aggregationWindowMs: number,
  now: Date,
): boolean {
  const leftTime = candidateTime(left, now).getTime();
  const rightTime = candidateTime(right, now).getTime();
  if (Math.abs(leftTime - rightTime) > aggregationWindowMs) return false;
  if (left.categoryKey && right.categoryKey && left.categoryKey === right.categoryKey) return true;
  return areTaskTitlesSimilar(left.title, right.title);
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
  writeProactiveExpressionState(next, options.storage);
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

  const evaluate = (
    candidates: readonly ProactiveTaskCandidate[],
    now = new Date(),
  ): ProactiveTriggerEvaluation => {
    let state = readProactiveExpressionState(storage, now);
    let taskState = taskStateOf(state);
    const decisions: ProactiveTriggerDecision[] = [];
    const prepared: PreparedCandidate[] = [];

    for (const candidate of candidates) {
      const key = candidateKey(candidate, now, timeWindowMs);
      const petId = choosePet(taskState, candidate.taskId, options.activePetId, availablePetIds);
      const score = scoreCandidate(candidate, taskState);
      const preference = preferenceFor(taskState, candidate.taskId);
      const record = recordFor(taskState, candidate.taskId);
      const lastDeliveredAt = validDate(record.lastDeliveredAt);
      const baseCooldown = preference.mode === "reduced" ? reducedTaskCooldownMs : taskCooldownMs;
      const ignoreBackoff = record.ignoredStreak >= 2
        ? baseCooldown * Math.min(8, 2 ** Math.min(record.ignoredStreak - 1, 3))
        : baseCooldown;
      const cooldown = record.ignoredStreak >= 2 ? ignoreBackoff : baseCooldown;

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
      if (taskState.deliveredKeys.includes(key)) {
        decisions.push({
          taskId: candidate.taskId,
          reminderInstanceId: candidate.reminderInstanceId,
          candidateKey: key,
          result: "suppress",
          score,
          priority: candidate.priority,
          reason: "already-delivered",
          explanation: "同一任务在同一时间窗口已经投递过。",
          nextEligibleAt: null,
          petId,
          actualDelivery: false,
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
      prepared.push({ candidate, candidateKey: key, petId, score });
    }

    if (prepared.length > 0) {
      const groups: PreparedCandidate[][] = [];
      for (const item of prepared.sort((left, right) => right.score - left.score || left.candidateKey.localeCompare(right.candidateKey))) {
        const group = groups.find((existing) => sameAggregationGroup(existing[0].candidate, item.candidate, aggregationWindowMs, now));
        if (group) group.push(item);
        else groups.push([item]);
      }

      for (const group of groups) {
        const primary = group[0];
        if (state.bubbleCounts.task_reminder >= dailyLimit) {
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
          state,
          now,
          quietHours: options.quietHours,
        });
        state = gateDecision.state;
        taskState = taskStateOf(state);
        if (!gateDecision.bubbleAllowed) {
          const isDelay = gateDecision.reason === "bubble-cooldown";
          const nextEligibleAt = isDelay && state.lastActiveBubbleAt
            ? nextIsoAfter(new Date(state.lastActiveBubbleAt), 45 * 60 * 1000)
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
        state = recordProactiveSemanticEventSuccess(state, "task_reminder", now, true);
        taskState = taskStateOf(state);
          const deliveredKeys = new Set(taskState.deliveredKeys);
          const records = { ...taskState.records };
          for (const item of group) {
            deliveredKeys.add(item.candidateKey);
            const previousRecord = recordFor(taskState, item.candidate.taskId);
            records[item.candidate.taskId] = {
              lastDeliveredAt: now.toISOString(),
              // Delivery is not engagement. Keep the prior streak so the
              // next unattended bubble can advance it across deliveries.
              ignoredStreak: previousRecord.ignoredStreak,
            };
          }
        state = withTaskState(state, {
          ...taskState,
          records,
          deliveredKeys: [...deliveredKeys].slice(-PROACTIVE_TASK_DELIVERED_KEY_LIMIT),
          lastDeliveryContext: {
            candidateKey: primary.candidateKey,
            taskIds: group.map((item) => item.candidate.taskId),
            taskTitles: group.map((item) => item.candidate.title),
            petId: primary.petId,
            deliveredAt: now.toISOString(),
          } satisfies ProactiveTaskDeliveryContext,
        });

        decisions.push({
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
          actualDelivery: true,
          aggregatedTaskIds: aggregate ? group.map((item) => item.candidate.taskId) : undefined,
        });
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

    state = appendDecisionLog(state, decisions, now);
    writeProactiveExpressionState(state, storage);
    const deliveries = decisions
      .filter((decision) => decision.actualDelivery)
      .map((decision) => ({
        decision,
        candidates: (decision.aggregatedTaskIds ?? [decision.taskId])
          .map((taskId) => candidates.find((candidate) => candidate.taskId === taskId))
          .filter((candidate): candidate is ProactiveTaskCandidate => Boolean(candidate)),
      }));
    return { decisions, state, deliveries };
  };

  return {
    evaluate,
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
