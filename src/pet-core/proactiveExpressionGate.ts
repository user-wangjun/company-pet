export const PROACTIVE_EXPRESSION_STORAGE_KEY = "yuxin-proactive-expression-gate-v1";
export const PROACTIVE_EXPRESSION_SCHEMA_VERSION = 1;
export const PROACTIVE_TASK_STATE_SCHEMA_VERSION = 2;
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
  /** Stable identity shared by every event receipt in one actual delivery. */
  reservationGroupId: string;
  /** Local calendar date on which this delivery group consumed quota. */
  reservationLocalDate: string;
};

export type ProactiveTaskDeliveryContext = {
  candidateKey: string;
  taskIds: string[];
  taskTitles: string[];
  petId: string;
  deliveredAt: string;
};

export type ProactiveTaskState = {
  schemaVersion: typeof PROACTIVE_TASK_STATE_SCHEMA_VERSION;
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
  if (typeof value !== "string" || !LOCAL_DATE_PATTERN.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  if (year < 1 || month < 1 || month > 12 || day < 1) return false;
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1];
  return day <= daysInMonth;
}

const RESERVATION_GROUP_ID_MAX_LENGTH = 1024;

function isReservationGroupId(value: unknown): value is string {
  return typeof value === "string"
    && value.length > 0
    && Array.from(value).length <= RESERVATION_GROUP_ID_MAX_LENGTH
    && !/[\u0000-\u001f\u007f\s]/u.test(value);
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
  const keys = Object.keys(source);
  return keys.length === 4
    && source.reservationGroupId !== undefined
    && source.reservationLocalDate !== undefined
    && source.status !== undefined
    && source.updatedAt !== undefined
    && (source.status === "reserved" || source.status === "blocked" || source.status === "confirmed")
    && isCanonicalUtcIso(source.updatedAt)
    && isReservationGroupId(source.reservationGroupId)
    && isValidLocalDate(source.reservationLocalDate);
}

const LEGACY_RECEIPT_TIMESTAMP = "1970-01-01T00:00:00.000Z";

const RESERVATION_SHA256_K = [
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

const RESERVATION_SHA256_INITIAL_STATE = [
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
  0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
] as const;

function rotateRight(value: number, amount: number): number {
  return (value >>> amount) | (value << (32 - amount));
}

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

  const state: number[] = [...RESERVATION_SHA256_INITIAL_STATE];
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
      const first = (h + bigSigma1 + choose + RESERVATION_SHA256_K[index] + words[index]) >>> 0;
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

function legacyReservationGroupId(key: string): string {
  // Keep the old opaque event key out of the semantic receipt fields while
  // producing a deterministic group id for migration. Hex encoding also
  // makes malformed legacy keys safe to carry forward without dropping the
  // at-most-once barrier.
  const encoded = Array.from(key)
    .map((character) => character.codePointAt(0)!.toString(16))
    .join(".");
  return `legacy-reservation:${encoded}`;
}

function legacyReservationGroupIdForEvidence(
  status: ProactiveTaskDeliveryReceiptStatus,
  updatedAt: string,
  taskIds: readonly string[],
): string {
  return `legacy-reservation:v2:${sha256Hex(JSON.stringify([status, updatedAt, taskIds]))}`;
}

function legacyReservationLocalDate(
  updatedAt: string,
  fallbackLocalDate: string,
): string {
  return updatedAt === LEGACY_RECEIPT_TIMESTAMP
    ? fallbackLocalDate
    : localDateId(new Date(updatedAt));
}

type ProactiveTaskDeliveryReceiptDraft = {
  status: ProactiveTaskDeliveryReceiptStatus;
  updatedAt: string;
  reservationGroupId?: string;
  reservationLocalDate?: string;
};

function parseTaskState(
  value: unknown,
  legacyReceiptTimestamp = LEGACY_RECEIPT_TIMESTAMP,
  legacyReservationDate = "1970-01-01",
): ProactiveTaskState | undefined | null {
  if (value === undefined) return undefined;
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const source = value as Record<string, unknown>;
  if (source.schemaVersion !== 1 && source.schemaVersion !== PROACTIVE_TASK_STATE_SCHEMA_VERSION) return null;
  const isLegacySchema = source.schemaVersion === 1;

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
  const receiptDrafts: Record<string, ProactiveTaskDeliveryReceiptDraft> = {};
  const legacyReceiptKeys = new Set<string>();
  if (deliveryReceiptsValue !== undefined) {
    for (const [key, rawReceipt] of Object.entries(deliveryReceiptsValue)) {
      if (typeof key !== "string" || key.length === 0 || !rawReceipt || typeof rawReceipt !== "object" || Array.isArray(rawReceipt)) {
        return null;
      }
      const receipt = rawReceipt as Record<string, unknown>;
      if (isProactiveTaskDeliveryReceipt(receipt)) {
        const normalizedReceipt = {
          status: receipt.status,
          updatedAt: receipt.updatedAt,
          reservationGroupId: receipt.reservationGroupId,
          reservationLocalDate: receipt.reservationLocalDate,
        };
        if (isLegacySchema) receiptDrafts[key] = normalizedReceipt;
        else deliveryReceipts[key] = normalizedReceipt;
        continue;
      }
      if (!isLegacySchema || Object.keys(receipt).sort().join("|") !== "status|updatedAt") return null;
      if (
        (receipt.status !== "reserved" && receipt.status !== "blocked" && receipt.status !== "confirmed")
        || !isCanonicalUtcIso(receipt.updatedAt)
      ) return null;
      receiptDrafts[key] = {
        status: receipt.status,
        updatedAt: receipt.updatedAt,
      };
      legacyReceiptKeys.add(key);
    }
  }

  // Migrate the pre-receipt projection conservatively. A delivered key is
  // stronger than a stale reservation projection, so it always becomes a
  // confirmed receipt rather than becoming replayable after restart.
  for (const key of deliveredKeysValue) {
    const existing = deliveryReceipts[key] ?? receiptDrafts[key];
    if (!existing || existing.status !== "confirmed") {
      if (deliveryReceipts[key]) {
        deliveryReceipts[key] = {
          status: "confirmed",
          updatedAt: existing?.updatedAt ?? legacyReceiptTimestamp,
          reservationGroupId: deliveryReceipts[key].reservationGroupId,
          reservationLocalDate: deliveryReceipts[key].reservationLocalDate,
        };
      } else {
        receiptDrafts[key] = {
          status: "confirmed",
          updatedAt: existing?.updatedAt ?? legacyReceiptTimestamp,
          reservationGroupId: existing?.reservationGroupId,
          reservationLocalDate: existing?.reservationLocalDate,
        };
      }
      if (!existing?.reservationGroupId) legacyReceiptKeys.add(key);
    }
  }
  for (const [key, status] of Object.entries(deliveryReservations)) {
    const existing = deliveryReceipts[key] ?? receiptDrafts[key];
    if (existing?.status === "confirmed") {
      delete deliveryReservations[key];
      continue;
    }
    if (existing && existing.status !== status) return null;
    if (!existing) {
      receiptDrafts[key] = {
        status,
        updatedAt: legacyReceiptTimestamp,
      };
      legacyReceiptKeys.add(key);
    }
  }

  const deliveryReservationTaskIds: Record<string, string[]> = {};
  if (deliveryReservationTaskIdsValue !== undefined) {
    for (const [key, rawTaskIds] of Object.entries(deliveryReservationTaskIdsValue)) {
      const receipt = deliveryReceipts[key] ?? receiptDrafts[key];
      if (
        typeof key !== "string"
        || key.length === 0
        || !Array.isArray(rawTaskIds)
        || rawTaskIds.length === 0
        || !rawTaskIds.every((taskId) => typeof taskId === "string" && taskId.length > 0)
        || receipt?.status === "confirmed"
        || !receipt
      ) {
        return null;
      }
      deliveryReservationTaskIds[key] = [...new Set(rawTaskIds)].sort();
    }
  }

  for (const [key, draft] of Object.entries(receiptDrafts)) {
    const taskIds = deliveryReservationTaskIds[key];
    const reservationGroupId = draft.reservationGroupId
      ?? (legacyReceiptKeys.has(key) && taskIds
        ? legacyReservationGroupIdForEvidence(draft.status, draft.updatedAt, taskIds)
        : legacyReservationGroupId(key));
    const reservationLocalDate = draft.reservationLocalDate
      ?? legacyReservationLocalDate(draft.updatedAt, legacyReservationDate);
    if (!isReservationGroupId(reservationGroupId) || !isValidLocalDate(reservationLocalDate)) return null;
    deliveryReceipts[key] = {
      status: draft.status,
      updatedAt: draft.updatedAt,
      reservationGroupId,
      reservationLocalDate,
    };
  }
  for (const [key, receipt] of Object.entries(deliveryReceipts)) {
    if (receipt.status === "reserved" || receipt.status === "blocked") {
      deliveryReservations[key] = receipt.status;
    } else {
      delete deliveryReservations[key];
    }
  }

  const groupDates = new Map<string, string>();
  for (const receipt of Object.values(deliveryReceipts)) {
    const previousDate = groupDates.get(receipt.reservationGroupId);
    if (previousDate !== undefined && previousDate !== receipt.reservationLocalDate) return null;
    groupDates.set(receipt.reservationGroupId, receipt.reservationLocalDate);
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
    schemaVersion: PROACTIVE_TASK_STATE_SCHEMA_VERSION,
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

  const taskState = parseTaskState(source.taskState, lastEvaluatedAt, source.currentLocalDate);
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
    schemaVersion: PROACTIVE_TASK_STATE_SCHEMA_VERSION,
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
  const parsed = parsePersistedState(state);
  if (!storage || !parsed) return false;
  try {
    storage.setItem(PROACTIVE_EXPRESSION_STORAGE_KEY, JSON.stringify(parsed));
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
