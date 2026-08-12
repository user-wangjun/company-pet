export const PROACTIVE_EXPRESSION_STORAGE_KEY = "yuxin-proactive-expression-gate-v1";
export const PROACTIVE_EXPRESSION_SCHEMA_VERSION = 1;
export const PROACTIVE_BUBBLE_MIN_INTERVAL_MS = 45 * 60 * 1000;

export const PROACTIVE_SEMANTIC_EVENTS = [
  "idle_alive",
  "morning_greet",
  "celebrate_small",
  "celebrate_big",
  "gentle_concern",
  "notice_return",
  "recall_memory",
  "task_reminder",
] as const;

const LEGACY_PROACTIVE_SEMANTIC_EVENTS = [
  "idle_alive",
  "morning_greet",
  "celebrate_small",
  "celebrate_big",
  "gentle_concern",
  "notice_return",
  "recall_memory",
] as const;

export type ProactiveSemanticEvent = (typeof PROACTIVE_SEMANTIC_EVENTS)[number];

export type ProactiveEventCounts = Record<ProactiveSemanticEvent, number>;

export type ProactiveTaskPreferenceMode = "normal" | "muted" | "reduced";

export type ProactiveTaskPreference = {
  mode: ProactiveTaskPreferenceMode;
  preferredPetId: string | null;
};

export type ProactiveTaskRecord = {
  lastDeliveredAt: string | null;
  ignoredStreak: number;
};

export type ProactiveTaskDecisionOutcome = "send" | "suppress" | "delay" | "aggregate";

export type ProactiveTaskDecisionLog = {
  candidateKey: string;
  result: ProactiveTaskDecisionOutcome;
  reason: string;
  score: number;
  petId: string;
  at: string;
};

/**
 * A persisted reservation is intentionally separate from deliveredKeys.
 * `reserved` means the durable at-most-once barrier was written before the
 * local sink was called; `blocked` means the sink was called but did not
 * confirm success. Neither state is a delivery confirmation.
 */
export type ProactiveTaskDeliveryReservationStatus = "reserved" | "blocked";

/**
 * Durable receipt state is the authoritative idempotency record. The older
 * `deliveredKeys` array remains a bounded compatibility projection, but it is
 * never allowed to evict a receipt that the Task/Reminder domain can still
 * replay.
 */
export type ProactiveTaskDeliveryReceiptStatus = ProactiveTaskDeliveryReservationStatus | "confirmed";

export type ProactiveTaskDeliveryReceipt = {
  status: ProactiveTaskDeliveryReceiptStatus;
  updatedAt: string;
};

export type ProactiveTaskDeliveryContext = {
  candidateKey: string;
  taskIds: string[];
  taskTitles: string[];
  petId: string;
  deliveredAt: string;
};

export type ProactiveTaskState = {
  schemaVersion: 1;
  preferences: Record<string, ProactiveTaskPreference>;
  records: Record<string, ProactiveTaskRecord>;
  deliveredKeys: string[];
  decisionLog: ProactiveTaskDecisionLog[];
  lastDeliveryContext: ProactiveTaskDeliveryContext | null;
  deliveryReservations?: Record<string, ProactiveTaskDeliveryReservationStatus>;
  /** Opaque event receipts; contains no title, note, chat, or Task payload. */
  deliveryReceipts: Record<string, ProactiveTaskDeliveryReceipt>;
  /** Task ids are retained only for reservation gate re-checks; no titles or notes. */
  deliveryReservationTaskIds?: Record<string, string[]>;
};

export type ProactiveExpressionState = {
  schemaVersion: typeof PROACTIVE_EXPRESSION_SCHEMA_VERSION;
  currentLocalDate: string;
  lastActiveBubbleAt: string | null;
  lastEvaluatedAt: string;
  triggerCounts: ProactiveEventCounts;
  bubbleCounts: ProactiveEventCounts;
  conservativeSilenceDate: string | null;
  /** Task-trigger state is kept in this same proactive gate storage. */
  taskState?: ProactiveTaskState;
};

export type ProactiveExpressionStorage = Pick<Storage, "getItem" | "setItem">;

export type QuietHoursWindow = {
  startTime: string;
  endTime: string;
};

export type ProactiveEventDecisionReason =
  | "allowed"
  | "quiet-hours"
  | "conservative-silence"
  | "daily-limit"
  | "bubble-daily-limit"
  | "bubble-cooldown";

export type ProactiveEventDecision = {
  eventAllowed: boolean;
  bubbleAllowed: boolean;
  reason: ProactiveEventDecisionReason;
  state: ProactiveExpressionState;
};

type EventRule = {
  producesBubble: boolean;
  triggerDailyLimit: number | null;
  bubbleDailyLimit: number | null;
  canRunWithoutBubble: boolean;
};

export const PROACTIVE_EVENT_RULES: Record<ProactiveSemanticEvent, EventRule> = {
  idle_alive: {
    producesBubble: false,
    triggerDailyLimit: null,
    bubbleDailyLimit: null,
    canRunWithoutBubble: true,
  },
  morning_greet: {
    producesBubble: true,
    triggerDailyLimit: 1,
    bubbleDailyLimit: 1,
    canRunWithoutBubble: false,
  },
  celebrate_small: {
    producesBubble: true,
    triggerDailyLimit: null,
    bubbleDailyLimit: 3,
    canRunWithoutBubble: true,
  },
  celebrate_big: {
    producesBubble: true,
    triggerDailyLimit: null,
    bubbleDailyLimit: null,
    canRunWithoutBubble: true,
  },
  gentle_concern: {
    producesBubble: true,
    triggerDailyLimit: 1,
    bubbleDailyLimit: 1,
    canRunWithoutBubble: false,
  },
  notice_return: {
    producesBubble: true,
    triggerDailyLimit: 1,
    bubbleDailyLimit: 1,
    canRunWithoutBubble: false,
  },
  recall_memory: {
    producesBubble: true,
    triggerDailyLimit: 1,
    bubbleDailyLimit: 1,
    canRunWithoutBubble: false,
  },
  task_reminder: {
    producesBubble: true,
    triggerDailyLimit: null,
    bubbleDailyLimit: null,
    canRunWithoutBubble: false,
  },
};

const LOCAL_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/;

function zeroCounts(): ProactiveEventCounts {
  return Object.fromEntries(
    PROACTIVE_SEMANTIC_EVENTS.map((event) => [event, 0]),
  ) as ProactiveEventCounts;
}

function isValidDate(date: Date): boolean {
  return Number.isFinite(date.getTime());
}

function isCanonicalUtcIso(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const date = new Date(value);
  return isValidDate(date) && date.toISOString() === value;
}

function isValidLocalDate(value: unknown): value is string {
  return typeof value === "string" && LOCAL_DATE_PATTERN.test(value);
}

function parseCounts(value: unknown): ProactiveEventCounts | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const source = value as Record<string, unknown>;
  const entries = PROACTIVE_SEMANTIC_EVENTS.map((event) => {
    const count = source[event];
    if (count === undefined && !LEGACY_PROACTIVE_SEMANTIC_EVENTS.includes(event as (typeof LEGACY_PROACTIVE_SEMANTIC_EVENTS)[number])) {
      return [event, 0] as const;
    }
    return Number.isSafeInteger(count) && (count as number) >= 0
      ? [event, count as number] as const
      : null;
  });
  if (entries.some((entry) => entry === null)) return null;
  return Object.fromEntries(
    entries as Array<readonly [ProactiveSemanticEvent, number]>,
  ) as ProactiveEventCounts;
}

function isTaskPreferenceMode(value: unknown): value is ProactiveTaskPreferenceMode {
  return value === "normal" || value === "muted" || value === "reduced";
}

function isProactiveTaskDeliveryContext(
  value: unknown,
): value is ProactiveTaskDeliveryContext {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const source = value as Record<string, unknown>;
  return (
    typeof source.candidateKey === "string" && source.candidateKey.length > 0
    && Array.isArray(source.taskIds)
    && source.taskIds.length > 0
    && source.taskIds.every((taskId) => typeof taskId === "string" && taskId.length > 0)
    && Array.isArray(source.taskTitles)
    && source.taskTitles.length === source.taskIds.length
    && source.taskTitles.every((title) => typeof title === "string" && title.trim().length > 0)
    && typeof source.petId === "string" && source.petId.length > 0
    && isCanonicalUtcIso(source.deliveredAt)
  );
}

function isProactiveTaskDeliveryReceipt(
  value: unknown,
): value is ProactiveTaskDeliveryReceipt {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const source = value as Record<string, unknown>;
  return Object.keys(source).sort().join("|") === "status|updatedAt"
    && (source.status === "reserved" || source.status === "blocked" || source.status === "confirmed")
    && isCanonicalUtcIso(source.updatedAt);
}

const LEGACY_RECEIPT_TIMESTAMP = "1970-01-01T00:00:00.000Z";

function parseTaskState(
  value: unknown,
  legacyReceiptTimestamp = LEGACY_RECEIPT_TIMESTAMP,
): ProactiveTaskState | undefined | null {
  if (value === undefined) return undefined;
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const source = value as Record<string, unknown>;
  if (source.schemaVersion !== 1) return null;

  const preferencesValue = source.preferences;
  const recordsValue = source.records;
  const deliveredKeysValue = source.deliveredKeys;
  const decisionLogValue = source.decisionLog;
  const lastDeliveryContextValue = source.lastDeliveryContext;
  const deliveryReservationsValue = source.deliveryReservations;
  const deliveryReceiptsValue = source.deliveryReceipts;
  const deliveryReservationTaskIdsValue = source.deliveryReservationTaskIds;
  if (
    !preferencesValue || typeof preferencesValue !== "object" || Array.isArray(preferencesValue)
    || !recordsValue || typeof recordsValue !== "object" || Array.isArray(recordsValue)
    || !Array.isArray(deliveredKeysValue)
    || !deliveredKeysValue.every((key) => typeof key === "string" && key.length > 0)
    || !Array.isArray(decisionLogValue)
    || (deliveryReservationsValue !== undefined
      && (!deliveryReservationsValue
        || typeof deliveryReservationsValue !== "object"
        || Array.isArray(deliveryReservationsValue)))
    || (deliveryReceiptsValue !== undefined
      && (!deliveryReceiptsValue
        || typeof deliveryReceiptsValue !== "object"
        || Array.isArray(deliveryReceiptsValue)))
    || (deliveryReservationTaskIdsValue !== undefined
      && (!deliveryReservationTaskIdsValue
        || typeof deliveryReservationTaskIdsValue !== "object"
        || Array.isArray(deliveryReservationTaskIdsValue)))
    || (lastDeliveryContextValue !== undefined
      && lastDeliveryContextValue !== null
      && !isProactiveTaskDeliveryContext(lastDeliveryContextValue))
  ) {
    return null;
  }

  const deliveryReservations: Record<string, ProactiveTaskDeliveryReservationStatus> = {};
  if (deliveryReservationsValue !== undefined) {
    for (const [key, rawStatus] of Object.entries(deliveryReservationsValue)) {
      if (
        typeof key !== "string" || key.length === 0
        || (rawStatus !== "reserved" && rawStatus !== "blocked")
      ) {
        return null;
      }
      deliveryReservations[key] = rawStatus;
    }
  }

  const deliveryReceipts: Record<string, ProactiveTaskDeliveryReceipt> = {};
  if (deliveryReceiptsValue !== undefined) {
    for (const [key, rawReceipt] of Object.entries(deliveryReceiptsValue)) {
      if (typeof key !== "string" || key.length === 0 || !isProactiveTaskDeliveryReceipt(rawReceipt)) {
        return null;
      }
      deliveryReceipts[key] = {
        status: rawReceipt.status,
        updatedAt: rawReceipt.updatedAt,
      };
    }
  }

  // Migrate the pre-receipt projection conservatively. A delivered key is
  // stronger than a stale reservation projection, so it always becomes a
  // confirmed receipt rather than becoming replayable after restart.
  for (const key of deliveredKeysValue) {
    const existing = deliveryReceipts[key];
    if (!existing || existing.status !== "confirmed") {
      deliveryReceipts[key] = {
        status: "confirmed",
        updatedAt: legacyReceiptTimestamp,
      };
    }
  }
  for (const [key, status] of Object.entries(deliveryReservations)) {
    const existing = deliveryReceipts[key];
    if (existing?.status === "confirmed") {
      delete deliveryReservations[key];
      continue;
    }
    if (existing && existing.status !== status) return null;
    deliveryReceipts[key] ??= {
      status,
      updatedAt: legacyReceiptTimestamp,
    };
  }
  for (const [key, receipt] of Object.entries(deliveryReceipts)) {
    if (receipt.status === "reserved" || receipt.status === "blocked") {
      deliveryReservations[key] = receipt.status;
    } else {
      delete deliveryReservations[key];
    }
  }

  const deliveryReservationTaskIds: Record<string, string[]> = {};
  if (deliveryReservationTaskIdsValue !== undefined) {
    for (const [key, rawTaskIds] of Object.entries(deliveryReservationTaskIdsValue)) {
      if (
        typeof key !== "string"
        || key.length === 0
        || !Array.isArray(rawTaskIds)
        || rawTaskIds.length === 0
        || !rawTaskIds.every((taskId) => typeof taskId === "string" && taskId.length > 0)
        || deliveryReceipts[key]?.status === "confirmed"
        || !deliveryReceipts[key]
      ) {
        return null;
      }
      deliveryReservationTaskIds[key] = [...new Set(rawTaskIds)];
    }
  }

  const preferences: Record<string, ProactiveTaskPreference> = {};
  for (const [taskId, rawPreference] of Object.entries(preferencesValue)) {
    if (!rawPreference || typeof rawPreference !== "object" || Array.isArray(rawPreference)) return null;
    const preference = rawPreference as Record<string, unknown>;
    if (
      !isTaskPreferenceMode(preference.mode)
      || (preference.preferredPetId !== null && typeof preference.preferredPetId !== "string")
    ) {
      return null;
    }
    preferences[taskId] = {
      mode: preference.mode,
      preferredPetId: preference.preferredPetId,
    };
  }

  const records: Record<string, ProactiveTaskRecord> = {};
  for (const [taskId, rawRecord] of Object.entries(recordsValue)) {
    if (!rawRecord || typeof rawRecord !== "object" || Array.isArray(rawRecord)) return null;
    const record = rawRecord as Record<string, unknown>;
    if (
      (record.lastDeliveredAt !== null && !isCanonicalUtcIso(record.lastDeliveredAt))
      || !Number.isSafeInteger(record.ignoredStreak)
      || (record.ignoredStreak as number) < 0
    ) {
      return null;
    }
    records[taskId] = {
      lastDeliveredAt: record.lastDeliveredAt as string | null,
      ignoredStreak: record.ignoredStreak as number,
    };
  }

  const decisionLog: ProactiveTaskDecisionLog[] = [];
  for (const rawLog of decisionLogValue) {
    if (!rawLog || typeof rawLog !== "object" || Array.isArray(rawLog)) return null;
    const log = rawLog as Record<string, unknown>;
    if (
      typeof log.candidateKey !== "string" || !log.candidateKey
      || !["send", "suppress", "delay", "aggregate"].includes(String(log.result))
      || typeof log.reason !== "string"
      || typeof log.score !== "number" || !Number.isFinite(log.score)
      || typeof log.petId !== "string" || !log.petId
      || !isCanonicalUtcIso(log.at)
    ) {
      return null;
    }
    decisionLog.push({
      candidateKey: log.candidateKey,
      result: log.result as ProactiveTaskDecisionOutcome,
      reason: log.reason,
      score: log.score,
      petId: log.petId,
      at: log.at,
    });
  }

  return {
    schemaVersion: 1,
    preferences,
    records,
    deliveredKeys: [...deliveredKeysValue] as string[],
    decisionLog,
    lastDeliveryContext:
      lastDeliveryContextValue === null || lastDeliveryContextValue === undefined
        ? null
        : {
            candidateKey: lastDeliveryContextValue.candidateKey,
            taskIds: [...lastDeliveryContextValue.taskIds],
            taskTitles: [...lastDeliveryContextValue.taskTitles],
            petId: lastDeliveryContextValue.petId,
            deliveredAt: lastDeliveryContextValue.deliveredAt,
          },
    deliveryReservations,
    deliveryReceipts,
    deliveryReservationTaskIds,
  };
}

function parsePersistedState(value: unknown): ProactiveExpressionState | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const source = value as Record<string, unknown>;
  const triggerCounts = parseCounts(source.triggerCounts);
  const bubbleCounts = parseCounts(source.bubbleCounts);
  const lastActiveBubbleAt = source.lastActiveBubbleAt;
  const lastEvaluatedAt = source.lastEvaluatedAt;
  const conservativeSilenceDate = source.conservativeSilenceDate;
  if (
    source.schemaVersion !== PROACTIVE_EXPRESSION_SCHEMA_VERSION ||
    !isValidLocalDate(source.currentLocalDate) ||
    !isCanonicalUtcIso(lastEvaluatedAt) ||
    (lastActiveBubbleAt !== null && !isCanonicalUtcIso(lastActiveBubbleAt)) ||
    (conservativeSilenceDate !== null && !isValidLocalDate(conservativeSilenceDate)) ||
    !triggerCounts ||
    !bubbleCounts
  ) {
    return null;
  }

  const taskState = parseTaskState(source.taskState, lastEvaluatedAt);
  if (source.taskState !== undefined && !taskState) return null;

  const baseState: ProactiveExpressionState = {
    schemaVersion: PROACTIVE_EXPRESSION_SCHEMA_VERSION,
    currentLocalDate: source.currentLocalDate,
    lastActiveBubbleAt,
    lastEvaluatedAt,
    triggerCounts,
    bubbleCounts,
    conservativeSilenceDate,
  };
  return taskState ? { ...baseState, taskState } : baseState;
}

export function createProactiveTaskState(): ProactiveTaskState {
  return {
    schemaVersion: 1,
    preferences: {},
    records: {},
    deliveredKeys: [],
    decisionLog: [],
    lastDeliveryContext: null,
    deliveryReservations: {},
    deliveryReceipts: {},
    deliveryReservationTaskIds: {},
  };
}

export function localDateId(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function createProactiveExpressionState(
  now: Date = new Date(),
  conservative = false,
): ProactiveExpressionState {
  const safeNow = isValidDate(now) ? now : new Date(0);
  const currentLocalDate = localDateId(safeNow);
  return {
    schemaVersion: PROACTIVE_EXPRESSION_SCHEMA_VERSION,
    currentLocalDate,
    lastActiveBubbleAt: conservative ? safeNow.toISOString() : null,
    lastEvaluatedAt: safeNow.toISOString(),
    triggerCounts: zeroCounts(),
    bubbleCounts: zeroCounts(),
    conservativeSilenceDate: conservative ? currentLocalDate : null,
  };
}

export function normalizeProactiveExpressionState(
  state: ProactiveExpressionState,
  now: Date,
): ProactiveExpressionState {
  if (!isValidDate(now)) {
    return {
      ...state,
      conservativeSilenceDate: state.currentLocalDate,
    };
  }

  const currentLocalDate = localDateId(now);
  const nowMs = now.getTime();
  const lastEvaluatedMs = new Date(state.lastEvaluatedAt).getTime();
  if (
    nowMs < lastEvaluatedMs ||
    currentLocalDate < state.currentLocalDate
  ) {
    return {
      ...state,
      currentLocalDate,
      conservativeSilenceDate: currentLocalDate,
    };
  }

  if (currentLocalDate > state.currentLocalDate) {
    return {
      ...state,
      currentLocalDate,
      triggerCounts: zeroCounts(),
      bubbleCounts: zeroCounts(),
      conservativeSilenceDate: null,
    };
  }

  return state;
}

export function readProactiveExpressionState(
  storage: ProactiveExpressionStorage | null =
    typeof window === "undefined" ? null : window.localStorage,
  now: Date = new Date(),
): ProactiveExpressionState {
  if (!storage) return createProactiveExpressionState(now);

  try {
    const raw = storage.getItem(PROACTIVE_EXPRESSION_STORAGE_KEY);
    if (raw === null) return createProactiveExpressionState(now);
    const parsed = parsePersistedState(JSON.parse(raw));
    if (!parsed) return createProactiveExpressionState(now, true);
    return normalizeProactiveExpressionState(parsed, now);
  } catch {
    return createProactiveExpressionState(now, true);
  }
}

export function writeProactiveExpressionState(
  state: ProactiveExpressionState,
  storage: ProactiveExpressionStorage | null =
    typeof window === "undefined" ? null : window.localStorage,
): boolean {
  if (!storage || !parsePersistedState(state)) return false;
  try {
    storage.setItem(PROACTIVE_EXPRESSION_STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

function minutesOfDay(value: string): number | null {
  if (!TIME_PATTERN.test(value)) return null;
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

function timeFromMinutes(value: number): string {
  const normalized = ((value % 1440) + 1440) % 1440;
  return `${String(Math.floor(normalized / 60)).padStart(2, "0")}:${String(normalized % 60).padStart(2, "0")}`;
}

export function quietHoursFromBedtime(
  bedtime: string,
  durationMinutes = 8 * 60,
): QuietHoursWindow {
  const start = minutesOfDay(bedtime);
  if (
    start === null ||
    !Number.isSafeInteger(durationMinutes) ||
    durationMinutes <= 0 ||
    durationMinutes > 24 * 60
  ) {
    return { startTime: "", endTime: "" };
  }
  return {
    startTime: bedtime,
    endTime: timeFromMinutes(start + durationMinutes),
  };
}

export function isWithinQuietHours(
  now: Date,
  quietHours: QuietHoursWindow,
): boolean {
  if (!isValidDate(now)) return true;
  const start = minutesOfDay(quietHours.startTime);
  const end = minutesOfDay(quietHours.endTime);
  if (start === null || end === null || start === end) return true;
  const current = now.getHours() * 60 + now.getMinutes();
  return start < end
    ? current >= start && current < end
    : current >= start || current < end;
}

export function evaluateProactiveSemanticEvent({
  event,
  state,
  now = new Date(),
  quietHours = quietHoursFromBedtime("23:00"),
  requestBubble = PROACTIVE_EVENT_RULES[event].producesBubble,
}: {
  event: ProactiveSemanticEvent;
  state: ProactiveExpressionState;
  now?: Date;
  quietHours?: QuietHoursWindow;
  requestBubble?: boolean;
}): ProactiveEventDecision {
  const normalized = normalizeProactiveExpressionState(state, now);
  const rule = PROACTIVE_EVENT_RULES[event];
  const isConservative =
    normalized.conservativeSilenceDate === normalized.currentLocalDate ||
    !isValidDate(now) ||
    now.getTime() < new Date(normalized.lastEvaluatedAt).getTime();
  if (isConservative) {
    return {
      eventAllowed: false,
      bubbleAllowed: false,
      reason: "conservative-silence",
      state: normalized,
    };
  }
  if (isWithinQuietHours(now, quietHours)) {
    return {
      eventAllowed: false,
      bubbleAllowed: false,
      reason: "quiet-hours",
      state: normalized,
    };
  }
  if (
    rule.triggerDailyLimit !== null &&
    normalized.triggerCounts[event] >= rule.triggerDailyLimit
  ) {
    return {
      eventAllowed: false,
      bubbleAllowed: false,
      reason: "daily-limit",
      state: normalized,
    };
  }

  if (!requestBubble || !rule.producesBubble) {
    return {
      eventAllowed: true,
      bubbleAllowed: false,
      reason: "allowed",
      state: normalized,
    };
  }

  if (
    rule.bubbleDailyLimit !== null &&
    normalized.bubbleCounts[event] >= rule.bubbleDailyLimit
  ) {
    return {
      eventAllowed: rule.canRunWithoutBubble,
      bubbleAllowed: false,
      reason: "bubble-daily-limit",
      state: normalized,
    };
  }

  if (normalized.lastActiveBubbleAt) {
    const elapsed = now.getTime() - new Date(normalized.lastActiveBubbleAt).getTime();
    if (elapsed < PROACTIVE_BUBBLE_MIN_INTERVAL_MS) {
      return {
        eventAllowed: rule.canRunWithoutBubble,
        bubbleAllowed: false,
        reason: "bubble-cooldown",
        state: normalized,
      };
    }
  }

  return {
    eventAllowed: true,
    bubbleAllowed: true,
    reason: "allowed",
    state: normalized,
  };
}

export function recordProactiveSemanticEventSuccess(
  state: ProactiveExpressionState,
  event: ProactiveSemanticEvent,
  now: Date = new Date(),
  bubbleShown = PROACTIVE_EVENT_RULES[event].producesBubble,
): ProactiveExpressionState {
  const normalized = normalizeProactiveExpressionState(state, now);
  const didShowBubble = bubbleShown && PROACTIVE_EVENT_RULES[event].producesBubble;
  if (
    normalized.conservativeSilenceDate === normalized.currentLocalDate ||
    !isValidDate(now) ||
    now.getTime() < new Date(normalized.lastEvaluatedAt).getTime()
  ) {
    return normalized;
  }

  return {
    ...normalized,
    lastActiveBubbleAt: didShowBubble ? now.toISOString() : normalized.lastActiveBubbleAt,
    lastEvaluatedAt: now.toISOString(),
    triggerCounts: {
      ...normalized.triggerCounts,
      [event]: normalized.triggerCounts[event] + 1,
    },
    bubbleCounts: didShowBubble
      ? {
          ...normalized.bubbleCounts,
          [event]: normalized.bubbleCounts[event] + 1,
        }
      : normalized.bubbleCounts,
  };
}
