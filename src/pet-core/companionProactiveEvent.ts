import type {
  CompanionEvent,
  CompanionProactiveEventService as HarnessProactiveEventService,
} from "./companionHarnessTypes";
import type {
  ProactiveExpressionStorage,
  QuietHoursWindow,
} from "./proactiveExpressionGate";
import {
  createProactiveTaskCandidate,
  createProactiveTriggerEngine,
  type ProactiveDeliveryConfirmation,
  type ProactiveDeliveryTerminalProof,
  type ProactiveDeliveryReservation,
  type ProactiveTaskCandidate,
  type ProactiveTriggerDecision,
  type ProactiveTriggerEngine,
} from "./proactiveTriggerEngine";
import {
  canRenderProactiveTaskDelivery,
  planProactiveTaskDeliveryRoute,
  resolveProactiveTaskDelivery,
  type ProactiveTaskDelivery,
} from "./proactiveDelivery";
import type { TaskFeedbackPackage } from "./taskFeedback";
import type { TriggeredReminder } from "../task-core/types";

export type { CompanionEvent } from "./companionHarnessTypes";

export const COMPANION_EVENT_ID_MAX_LENGTH = 192;
export const COMPANION_EVENT_MAX_MINUTES_LEFT = 24 * 60;

const COMPANION_EVENT_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$/u;
const CANONICAL_UTC_ISO_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/u;

type ReminderDueEvent = Extract<CompanionEvent, { type: "REMINDER_DUE" }>;
type TaskDueSoonEvent = Extract<CompanionEvent, { type: "TASK_DUE_SOON" }>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
}

function isOpaqueEventId(value: unknown): value is string {
  return typeof value === "string"
    && value.length > 0
    && Array.from(value).length <= COMPANION_EVENT_ID_MAX_LENGTH
    && COMPANION_EVENT_ID_PATTERN.test(value);
}

function isNonEmptyId(value: unknown): value is string {
  return typeof value === "string"
    && value.trim().length > 0
    && Array.from(value).length <= 256
    && !/[\u0000-\u001f\u007f\s]/u.test(value);
}

function isValidMinutesLeft(value: unknown): value is number {
  return typeof value === "number"
    && Number.isSafeInteger(value)
    && value > 0
    && value <= COMPANION_EVENT_MAX_MINUTES_LEFT;
}

/** Runtime boundary for events received from a scheduler or persisted queue. */
export function parseCompanionEvent(value: unknown): CompanionEvent | null {
  if (!isRecord(value) || typeof value.type !== "string" || !isOpaqueEventId(value.id)) return null;
  if (value.type === "REMINDER_DUE") {
    if (
      !hasExactKeys(value, ["id", "type", "reminderId", "reminderInstanceId"])
      || !isNonEmptyId(value.reminderId)
      || !isNonEmptyId(value.reminderInstanceId)
    ) return null;
    return {
      id: value.id,
      type: value.type,
      reminderId: value.reminderId,
      reminderInstanceId: value.reminderInstanceId,
    };
  }
  if (value.type === "TASK_DUE_SOON") {
    if (
      !hasExactKeys(value, ["id", "type", "taskId", "minutesLeft"])
      || !isNonEmptyId(value.taskId)
      || !isValidMinutesLeft(value.minutesLeft)
    ) return null;
    return {
      id: value.id,
      type: value.type,
      taskId: value.taskId,
      minutesLeft: value.minutesLeft,
    };
  }
  return null;
}

export function isCompanionEvent(value: unknown): value is CompanionEvent {
  return parseCompanionEvent(value) !== null;
}

const SHA256_K = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
  0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
  0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
  0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
  0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
] as const;

const SHA256_INITIAL_STATE = [
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
  0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
] as const;

function rotateRight(value: number, amount: number): number {
  return (value >>> amount) | (value << (32 - amount));
}

/** Fixed-width SHA-256 keeps event ids opaque and avoids the old 32-bit hash collision class. */
function sha256Hex(value: string): string {
  const bytes = new TextEncoder().encode(value);
  const paddedLength = Math.ceil((bytes.length + 9) / 64) * 64;
  const padded = new Uint8Array(paddedLength);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  const bitLength = bytes.length * 8;
  const view = new DataView(padded.buffer);
  view.setUint32(paddedLength - 8, Math.floor(bitLength / 0x1_0000_0000));
  view.setUint32(paddedLength - 4, bitLength >>> 0);

  const state: number[] = [...SHA256_INITIAL_STATE];
  const words = new Uint32Array(64);
  for (let offset = 0; offset < paddedLength; offset += 64) {
    for (let index = 0; index < 16; index += 1) words[index] = view.getUint32(offset + index * 4);
    for (let index = 16; index < 64; index += 1) {
      const first = words[index - 15];
      const second = words[index - 2];
      const sigma0 = rotateRight(first, 7) ^ rotateRight(first, 18) ^ (first >>> 3);
      const sigma1 = rotateRight(second, 17) ^ rotateRight(second, 19) ^ (second >>> 10);
      words[index] = (words[index - 16] + sigma0 + words[index - 7] + sigma1) >>> 0;
    }

    let [a, b, c, d, e, f, g, h] = state;
    for (let index = 0; index < 64; index += 1) {
      const bigSigma1 = rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25);
      const choose = (e & f) ^ (~e & g);
      const first = (h + bigSigma1 + choose + SHA256_K[index] + words[index]) >>> 0;
      const bigSigma0 = rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const second = (bigSigma0 + majority) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + first) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (first + second) >>> 0;
    }
    state[0] = (state[0] + a) >>> 0;
    state[1] = (state[1] + b) >>> 0;
    state[2] = (state[2] + c) >>> 0;
    state[3] = (state[3] + d) >>> 0;
    state[4] = (state[4] + e) >>> 0;
    state[5] = (state[5] + f) >>> 0;
    state[6] = (state[6] + g) >>> 0;
    state[7] = (state[7] + h) >>> 0;
  }
  return state.map((word) => word.toString(16).padStart(8, "0")).join("");
}

function stableEventId(type: "reminder_due" | "task_due_soon", parts: readonly string[]): string {
  return `companion-event:v1:${type}:${sha256Hex(parts.join("\u001f"))}`;
}

function canonicalUtcIso(value: unknown): string | null {
  if (typeof value !== "string" || !CANONICAL_UTC_ISO_PATTERN.test(value)) return null;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) && date.toISOString() === value ? value : null;
}

function validDate(value: Date): boolean {
  return value instanceof Date && Number.isFinite(value.getTime());
}

/** Returns the occurrence-bound identity without deciding whether it is currently due-soon. */
export function getProactiveTaskCandidateEventId(
  candidate: ProactiveTaskCandidate,
): string | null {
  if (
    !candidate
    || !isNonEmptyId(candidate.taskId)
    || !isNonEmptyId(candidate.reminderId)
    || !isNonEmptyId(candidate.reminderInstanceId)
    || candidate.deletedAt !== null
    || !["pending", "in_progress"].includes(candidate.taskStatus)
    || candidate.status !== "scheduled"
    || candidate.triggeredAt !== null
  ) return null;
  const scheduledAt = canonicalUtcIso(candidate.scheduledAt);
  return scheduledAt
    ? stableEventId("task_due_soon", ["task_due_soon", candidate.taskId, scheduledAt])
    : null;
}

export function adaptTriggeredReminderToCompanionEvent(
  triggered: TriggeredReminder,
): ReminderDueEvent | null {
  if (!triggered || !triggered.task || !triggered.reminder || !triggered.instance) return null;
  const { task, reminder, instance } = triggered;
  if (
    !isNonEmptyId(task.id)
    || !isNonEmptyId(reminder.id)
    || !isNonEmptyId(instance.id)
    || reminder.id !== instance.reminderId
    || reminder.taskId !== task.id
    || task.deletedAt !== null
    || !["pending", "in_progress"].includes(task.status)
    || reminder.status !== "active"
    || reminder.deletedAt !== null
    || !["triggered", "missed"].includes(instance.status)
    || instance.taskId !== task.id
    || canonicalUtcIso(instance.scheduledAt) === null
    || !instance.triggeredAt
    || canonicalUtcIso(instance.triggeredAt) === null
  ) return null;
  return {
    id: stableEventId("reminder_due", ["reminder_due", reminder.id, instance.id]),
    type: "REMINDER_DUE",
    reminderId: reminder.id,
    reminderInstanceId: instance.id,
  };
}

export function adaptProactiveTaskCandidateToCompanionEvent(
  candidate: ProactiveTaskCandidate,
  now = new Date(),
  timeWindowMs = 60 * 60 * 1000,
): TaskDueSoonEvent | null {
  const stableId = getProactiveTaskCandidateEventId(candidate);
  if (
    !candidate
    || !validDate(now)
    || !Number.isFinite(timeWindowMs)
    || timeWindowMs <= 0
    || !isNonEmptyId(candidate.taskId)
    || !isNonEmptyId(candidate.reminderId)
    || !isNonEmptyId(candidate.reminderInstanceId)
    || typeof candidate.title !== "string"
    || !candidate.title.trim()
    || !stableId
  ) return null;
  const scheduledAt = canonicalUtcIso(candidate.scheduledAt);
  if (!scheduledAt) return null;
  const scheduledMs = new Date(scheduledAt).getTime();
  const remainingMs = scheduledMs - now.getTime();
  if (!(remainingMs > 0 && remainingMs <= timeWindowMs)) return null;
  const minutesLeft = Math.max(1, Math.ceil(remainingMs / 60_000));
  if (!isValidMinutesLeft(minutesLeft)) return null;
  return {
    id: stableId,
    type: "TASK_DUE_SOON",
    taskId: candidate.taskId,
    minutesLeft,
  };
}

/** Compatibility aliases make the adapter contract discoverable without duplicating logic. */
export const companionEventFromTriggeredReminder = adaptTriggeredReminderToCompanionEvent;
export const companionEventFromProactiveTaskCandidate = adaptProactiveTaskCandidateToCompanionEvent;

export type CompanionProactiveEventDelivery = ProactiveTaskDelivery & {
  event: CompanionEvent;
  eventIds: string[];
  decision: ProactiveTriggerDecision;
};

export type CompanionProactiveEventSink = (
  delivery: CompanionProactiveEventDelivery,
) => boolean | Promise<boolean>;

export type CompanionProactiveEventServiceOptions = {
  storage?: ProactiveExpressionStorage | null;
  activePetId: string;
  availablePetIds?: readonly string[];
  quietHours?: QuietHoursWindow;
  dailyLimit?: number;
  taskCooldownMs?: number;
  reducedTaskCooldownMs?: number;
  aggregationWindowMs?: number;
  timeWindowMs?: number;
  enabled?: boolean | (() => boolean);
  now?: () => Date;
  engine?: ProactiveTriggerEngine;
  resolveTriggeredReminder?: (
    event: ReminderDueEvent,
  ) => TriggeredReminder | null | Promise<TriggeredReminder | null>;
  resolveTaskCandidate?: (
    event: TaskDueSoonEvent,
  ) => ProactiveTaskCandidate | null | Promise<ProactiveTaskCandidate | null>;
  getTaskFeedbackPackage?: (
    petId: string,
  ) => TaskFeedbackPackage | undefined | Promise<TaskFeedbackPackage | undefined>;
  /**
   * Completes the local pet route before the durable reservation and sink.
   * Returning false (or throwing) leaves the event retryable and fail closed.
   */
  ensureActivePet?: (targetPetId: string) => boolean | Promise<boolean>;
  /** Domain-backed proof gate required before receipt cleanup. */
  verifyTerminalReceipt?: (proof: ProactiveDeliveryTerminalProof) => boolean;
  deliverySink: CompanionProactiveEventSink;
};

/**
 * Ownership boundary: triggerDueReminders()/the Scheduler owns ReminderInstance
 * transitions, formal system notifications and TaskReminderStack own the
 * actionable channels. This service receives only their stable projection and
 * can append at most one non-operational pet expression; it never creates a
 * ReminderInstance, calls the Scheduler, or mutates Task/Reminder facts.
 */

export type CompanionProactiveEventResultStatus =
  | "delivered"
  | "duplicate"
  | "suppressed"
  | "delayed"
  | "disabled"
  | "invalid"
  | "unresolved"
  | "unavailable"
  | "switch-required"
  | "storage-failed"
  | "delivery-failed"
  | "confirmation-failed";

export type CompanionProactiveEventResult = {
  event: CompanionEvent | null;
  status: CompanionProactiveEventResultStatus;
  sinkCalled: boolean;
  delivered: boolean;
  decision?: ProactiveTriggerDecision;
  confirmation?: ProactiveDeliveryConfirmation;
  reservation?: ProactiveDeliveryReservation;
};

function resultForPolicy(
  event: CompanionEvent,
  decision: ProactiveTriggerDecision | undefined,
): CompanionProactiveEventResult {
  const duplicate = decision?.reason === "already-delivered"
    || decision?.reason === "delivery-reserved"
    || decision?.reason === "delivery-blocked";
  return {
    event,
    status: duplicate ? "duplicate" : decision?.result === "delay" ? "delayed" : "suppressed",
    sinkCalled: false,
    delivered: false,
    ...(decision ? { decision } : {}),
  };
}

function isEnabled(value: CompanionProactiveEventServiceOptions["enabled"]): boolean {
  if (typeof value === "function") {
    try {
      return value();
    } catch {
      return false;
    }
  }
  return value !== false;
}

export type CompanionProactiveEventService = HarnessProactiveEventService & {
  handleEvents(events: readonly CompanionEvent[]): Promise<void>;
  processEvent(event: unknown): Promise<CompanionProactiveEventResult>;
  processEvents(events: readonly unknown[]): Promise<readonly CompanionProactiveEventResult[]>;
  engine: ProactiveTriggerEngine;
};

export function createCompanionProactiveEventService(
  options: CompanionProactiveEventServiceOptions,
): CompanionProactiveEventService {
  const availablePetIds = options.availablePetIds ?? [options.activePetId];
  const timeWindowMs = options.timeWindowMs ?? 60 * 60 * 1000;
  const engine = options.engine ?? createProactiveTriggerEngine({
    storage: options.storage,
    activePetId: options.activePetId,
    availablePetIds,
    dailyLimit: options.dailyLimit,
    quietHours: options.quietHours,
    taskCooldownMs: options.taskCooldownMs,
    reducedTaskCooldownMs: options.reducedTaskCooldownMs,
    aggregationWindowMs: options.aggregationWindowMs,
    timeWindowMs,
    verifyTerminalReceipt: options.verifyTerminalReceipt,
  });

  const resolveCandidate = async (
    event: CompanionEvent,
    now: Date,
  ): Promise<{ event: CompanionEvent; candidate: ProactiveTaskCandidate } | null> => {
    if (event.type === "REMINDER_DUE") {
      if (!options.resolveTriggeredReminder) return null;
      let triggered: TriggeredReminder | null;
      try {
        triggered = await options.resolveTriggeredReminder(event);
      } catch {
        return null;
      }
      if (!triggered) return null;
      const adapted = adaptTriggeredReminderToCompanionEvent(triggered);
      if (!adapted || adapted.id !== event.id) return null;
      return {
        event,
        candidate: { ...createProactiveTaskCandidate(triggered), eventId: event.id },
      };
    }
    if (!options.resolveTaskCandidate) return null;
    let candidate: ProactiveTaskCandidate | null;
    try {
      candidate = await options.resolveTaskCandidate(event);
    } catch {
      return null;
    }
    if (!candidate) return null;
    const adapted = adaptProactiveTaskCandidateToCompanionEvent(candidate, now, timeWindowMs);
    if (!adapted) {
      // A previously confirmed or reserved occurrence may be replayed after
      // Sleep/Resume, when its scheduledAt is now in the past. It is still
      // safe to resolve it for an idempotent no-op, but never for a new sink.
      try {
        const taskState = engine.getState(now).taskState;
        const known = taskState?.deliveryReceipts?.[event.id] !== undefined
          || taskState?.deliveredKeys.includes(event.id)
          || taskState?.deliveryReservations?.[event.id] !== undefined;
        if (known && getProactiveTaskCandidateEventId(candidate) === event.id) {
          return { event, candidate: { ...candidate, eventId: event.id } };
        }
      } catch {
        // A failed state read is fail closed; do not turn an old event into a
        // new delivery based on an unverifiable local occurrence.
      }
      return null;
    }
    if (adapted.id !== event.id || adapted.taskId !== event.taskId) return null;
    return { event, candidate: { ...candidate, eventId: event.id } };
  };

  const processEventsNow = async (
    rawEvents: readonly unknown[],
  ): Promise<readonly CompanionProactiveEventResult[]> => {
    const parsedEvents = rawEvents
      .map((event) => parseCompanionEvent(event))
      .filter((event): event is CompanionEvent => event !== null);
    const invalidCount = rawEvents.length - parsedEvents.length;
    const invalidResults: CompanionProactiveEventResult[] = Array.from(
      { length: invalidCount },
      () => ({ event: null, status: "invalid" as const, sinkCalled: false, delivered: false }),
    );
    if (parsedEvents.length === 0) return invalidResults;
    if (!isEnabled(options.enabled)) {
      return [
        ...invalidResults,
        ...parsedEvents.map((event) => ({
          event,
          status: "disabled" as const,
          sinkCalled: false,
          delivered: false,
        })),
      ];
    }

    const now = options.now?.() ?? new Date();
    if (!validDate(now)) {
      return [
        ...invalidResults,
        ...parsedEvents.map((event) => ({
          event,
          status: "suppressed" as const,
          sinkCalled: false,
          delivered: false,
        })),
      ];
    }
    const uniqueEvents = [...new Map(parsedEvents.map((event) => [event.id, event])).values()];
    const resolved = (await Promise.all(uniqueEvents.map((event) => resolveCandidate(event, now))))
      .filter((value): value is { event: CompanionEvent; candidate: ProactiveTaskCandidate } => value !== null);
    const unresolvedIds = new Set(uniqueEvents.map((event) => event.id));
    for (const item of resolved) unresolvedIds.delete(item.event.id);
    const results: CompanionProactiveEventResult[] = [
      ...invalidResults,
      ...uniqueEvents
        .filter((event) => unresolvedIds.has(event.id))
        .map((event) => ({ event, status: "unresolved" as const, sinkCalled: false, delivered: false })),
    ];
    if (resolved.length === 0) return results;

    const evaluation = engine.evaluateEligibility(resolved.map(({ candidate }) => candidate), now);
    const eligibleEventIds = new Set(
      evaluation.eligibleDeliveries.flatMap(({ candidates }) =>
        candidates.map((candidate) => candidate.eventId).filter((id): id is string => Boolean(id)),
      ),
    );
    if (evaluation.eligibleDeliveries.length > 0 && !evaluation.evaluationPersistenceConfirmed) {
      for (const item of resolved) {
        if (!eligibleEventIds.has(item.event.id)) continue;
        results.push({
          event: item.event,
          status: "storage-failed",
          sinkCalled: false,
          delivered: false,
        });
      }
      return results;
    }
    for (const item of resolved) {
      if (eligibleEventIds.has(item.event.id)) continue;
      const decision = evaluation.decisions.find((candidateDecision) =>
        candidateDecision.candidateKey === item.event.id,
      );
      if (decision && decision.result !== "send" && decision.result !== "aggregate") {
        results.push(resultForPolicy(item.event, decision));
      }
    }

    for (const eligible of evaluation.eligibleDeliveries) {
      const group = resolved.filter(({ candidate }) =>
        eligible.candidates.some((groupCandidate) => groupCandidate.eventId === candidate.eventId),
      );
      if (group.length === 0) continue;
      const decision = eligible.decision;
      const primary = group.find(({ event }) => event.id === decision.candidateKey) ?? group[0];
      const route = planProactiveTaskDeliveryRoute(
        decision,
        options.activePetId,
        availablePetIds,
      );
      if (route.status === "unavailable") {
        for (const item of group) {
          results.push({ event: item.event, status: "unavailable", sinkCalled: false, delivered: false, decision });
        }
        continue;
      }
      if (route.status === "switch") {
        let switched = false;
        try {
          switched = options.ensureActivePet
            ? (await options.ensureActivePet(route.targetPetId)) === true
            : false;
        } catch {
          switched = false;
        }
        if (switched) {
          // The injected coordinator has made the target the renderable pet;
          // reserve only after that local route boundary succeeds.
          // Continue through the same package/sink path below.
        } else {
          for (const item of group) {
            results.push({ event: item.event, status: "switch-required", sinkCalled: false, delivered: false, decision });
          }
          continue;
        }
      }
      let packageState: TaskFeedbackPackage | undefined;
      try {
        packageState = await options.getTaskFeedbackPackage?.(route.targetPetId);
      } catch {
        packageState = undefined;
      }
      const delivery = resolveProactiveTaskDelivery(
        decision,
        eligible.candidates,
        packageState,
      );
      if (!canRenderProactiveTaskDelivery(delivery, route.targetPetId)) {
        for (const item of group) {
          results.push({ event: item.event, status: "unavailable", sinkCalled: false, delivered: false, decision });
        }
        continue;
      }

      const reservation = engine.reserveDelivery(decision, eligible.candidates, now);
      if (reservation.status !== "reserved") {
        const status: CompanionProactiveEventResultStatus = reservation.status === "storage-failed"
          ? "storage-failed"
          : reservation.status === "already-delivered" || reservation.status === "already-reserved" || reservation.status === "blocked"
            ? "duplicate"
            : "suppressed";
        for (const item of group) {
          results.push({ event: item.event, status, sinkCalled: false, delivered: false, decision, reservation });
        }
        continue;
      }

      const sinkDelivery: CompanionProactiveEventDelivery = {
        ...delivery,
        event: primary.event,
        eventIds: group.map(({ event }) => event.id),
        decision,
      };
      let sinkConfirmed = false;
      try {
        sinkConfirmed = (await options.deliverySink(sinkDelivery)) === true;
      } catch {
        sinkConfirmed = false;
      }
      if (!sinkConfirmed) {
        engine.blockDelivery(reservation, now);
        for (const item of group) {
          results.push({ event: item.event, status: "delivery-failed", sinkCalled: true, delivered: false, decision, reservation });
        }
        continue;
      }

      const confirmation = engine.confirmDelivery(reservation, eligible.candidates, now);
      const confirmed = confirmation.status === "confirmed";
      for (const item of group) {
        results.push({
          event: item.event,
          status: confirmed ? "delivered" : "confirmation-failed",
          sinkCalled: true,
          delivered: confirmed,
          decision,
          reservation,
          confirmation,
        });
      }
    }
    return results;
  };

  type QueuedProcessRequest = {
    events: CompanionEvent[];
    invalidResults: CompanionProactiveEventResult[];
    resolve: (results: readonly CompanionProactiveEventResult[]) => void;
  };

  const pendingRequests: QueuedProcessRequest[] = [];
  let flushScheduled = false;
  let flushing = false;

  const failureResult = (event: CompanionEvent): CompanionProactiveEventResult => ({
    event,
    status: "storage-failed",
    sinkCalled: false,
    delivered: false,
  });

  const duplicateResult = (
    result: CompanionProactiveEventResult,
  ): CompanionProactiveEventResult => {
    if (
      result.status !== "delivered"
      && result.status !== "delivery-failed"
      && result.status !== "confirmation-failed"
      && result.status !== "duplicate"
    ) {
      return result;
    }
    return {
      ...result,
      status: "duplicate",
      sinkCalled: false,
      delivered: false,
    };
  };

  const flushRequests = async (): Promise<void> => {
    if (flushing) return;
    flushing = true;
    try {
      while (pendingRequests.length > 0) {
        const requests = pendingRequests.splice(0, pendingRequests.length);
        const batchEvents = requests.flatMap((request) => request.events);
        let batchResults: readonly CompanionProactiveEventResult[];
        try {
          batchResults = await processEventsNow(batchEvents);
        } catch {
          // A failed resolver/sink/storage must not strand the coordinator.
          // Each request receives a concrete fail-closed result and later
          // requests continue through a fresh micro-batch.
          batchResults = batchEvents.map(failureResult);
        }

        const resultByEventId = new Map<string, CompanionProactiveEventResult>();
        for (const result of batchResults) {
          if (result.event && !resultByEventId.has(result.event.id)) {
            resultByEventId.set(result.event.id, result);
          }
        }
        const consumedEventIds = new Set<string>();
        for (const request of requests) {
          const requestResults = [...request.invalidResults];
          const uniqueRequestEvents = [...new Map(request.events.map((event) => [event.id, event])).values()];
          for (const event of uniqueRequestEvents) {
            const base = resultByEventId.get(event.id) ?? failureResult(event);
            const result = consumedEventIds.has(event.id) ? duplicateResult(base) : base;
            consumedEventIds.add(event.id);
            requestResults.push(result);
          }
          request.resolve(requestResults);
        }
      }
    } finally {
      flushing = false;
      if (pendingRequests.length > 0 && !flushScheduled) {
        flushScheduled = true;
        queueMicrotask(() => {
          flushScheduled = false;
          void flushRequests();
        });
      }
    }
  };

  const enqueueProcess = (
    rawEvents: readonly unknown[],
  ): Promise<readonly CompanionProactiveEventResult[]> => {
    const parsedEvents = rawEvents
      .map((event) => parseCompanionEvent(event))
      .filter((event): event is CompanionEvent => event !== null);
    const invalidCount = rawEvents.length - parsedEvents.length;
    const invalidResults: CompanionProactiveEventResult[] = Array.from(
      { length: invalidCount },
      () => ({ event: null, status: "invalid" as const, sinkCalled: false, delivered: false }),
    );
    if (parsedEvents.length === 0) return Promise.resolve(invalidResults);

    return new Promise((resolve) => {
      pendingRequests.push({
        events: parsedEvents,
        invalidResults,
        resolve,
      });
      if (!flushScheduled && !flushing) {
        flushScheduled = true;
        queueMicrotask(() => {
          flushScheduled = false;
          void flushRequests();
        });
      }
    });
  };

  const service: HarnessProactiveEventService = {
    handleEvent: async (event) => {
      await enqueueProcess([event]);
    },
  };
  return Object.assign(service, {
    handleEvents: async (events: readonly CompanionEvent[]) => {
      await enqueueProcess(events);
    },
    processEvent: async (event: unknown) => (await enqueueProcess([event]))[0] ?? {
      event: null,
      status: "invalid" as const,
      sinkCalled: false,
      delivered: false,
    },
    processEvents: enqueueProcess,
    engine,
  });
}
