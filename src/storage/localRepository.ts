import {
  containsSensitiveCompanionData,
  containsSensitiveCompanionText,
} from "../pet-core/companionPrivacy";

export const LOCAL_REPOSITORY_SCHEMA_VERSION = 1;
export const LOCAL_REPOSITORY_DEVICE_ID_KEY = "yuxin-local-repository-device-id-v1";
export const LOCAL_REPOSITORY_SYNC_VERSION_KEY = "yuxin-local-repository-sync-version-v1";
export const LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY = "yuxin-local-repository-outbox-v1";
export const LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY = "yuxin-local-repository-journal-v1";
export const LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY = "yuxin-local-repository-delete-guards-v1";

export type LocalRepositoryStorage = Pick<Storage, "getItem" | "setItem">
  & Partial<Pick<Storage, "removeItem">>;

export type RepositoryEntity<T> = {
  id: string;
  deviceId: string;
  schemaVersion: number;
  syncVersion: number;
  updatedAt: string;
  deletedAt: string | null;
  /** A delete-first remote event has no entity payload; its tombstone uses null. */
  data: T | null;
};

export type OutboxOperation = "upsert" | "delete";

export type OutboxEvent<T = unknown> = {
  eventId: string;
  entityType: string;
  entityId: string;
  operation: OutboxOperation;
  schemaVersion: number;
  deviceId: string;
  createdAt: string;
  syncVersion: number;
  updatedAt?: string;
  deletedAt?: string | null;
  payload?: T;
};

/** Delete guards contain only the metadata needed to keep a deletion final. */
export type RepositoryDeletionGuard = {
  storageKey: string;
  entityType: string;
  entityId: string;
  deletedAt: string;
  syncVersion: number;
};

/**
 * Provider-neutral contract for a future sync transport. This phase only
 * defines the wire boundary; no network implementation is attached.
 */
export type RepositorySyncPushResult = {
  acceptedEventIds: string[];
  duplicateEventIds: string[];
  rejectedEventIds: string[];
};

export type RepositorySyncPullResult = {
  events: OutboxEvent[];
  cursor: string | null;
};

export type RepositorySyncTransport = {
  push(events: readonly OutboxEvent[]): Promise<RepositorySyncPushResult>;
  pull(cursor: string | null): Promise<RepositorySyncPullResult>;
};

export type LocalRepositoryEventInput<T = unknown> = {
  entityType: string;
  entityId: string;
  operation: OutboxOperation;
  schemaVersion: number;
  updatedAt?: string;
  deletedAt?: string | null;
  payload?: T;
};

export type LocalRepositoryWriteOptions<T, TPayload = unknown> = {
  storageKey: string;
  entityType: string;
  entityId: string;
  schemaVersion: number;
  data: T;
  updatedAt: string;
  deletedAt: string | null;
  payload?: TPayload;
  events?: readonly LocalRepositoryEventInput[];
};

export type LocalRepositoryWriteResult<T> =
  | {
      ok: true;
      entity: RepositoryEntity<T>;
      events: OutboxEvent[];
    }
  | {
      ok: false;
      entity: null;
      events: [];
      error: unknown;
    };

export type OutboxApplyResult<T> = {
  entity: RepositoryEntity<T> | null;
  applied: boolean;
  seenEventIds: Set<string>;
};

export type RepositoryVersionComparison = "stale" | "newer" | "incomparable";

/**
 * syncVersion is a per-device sequence. Values from different devices are
 * intentionally incomparable until a future sync layer supplies causal or
 * conflict-resolution metadata.
 */
export function compareRepositoryVersion<T>(
  existing: Pick<RepositoryEntity<T>, "deviceId" | "syncVersion">,
  event: Pick<OutboxEvent<T>, "deviceId" | "syncVersion">,
): RepositoryVersionComparison {
  if (existing.deviceId !== event.deviceId) return "incomparable";
  return event.syncVersion <= existing.syncVersion ? "stale" : "newer";
}

export type LocalRepository = {
  getDeviceId(): string;
  readValue(key: string): string | null;
  writeValue(key: string, value: string): boolean;
  readEntity<T>(storageKey: string): RepositoryEntity<T> | null;
  writeEntity<T, TPayload = unknown>(
    options: LocalRepositoryWriteOptions<T, TPayload>,
  ): LocalRepositoryWriteResult<T>;
  appendOutboxEvent<T>(event: OutboxEvent<T>): boolean;
  listOutbox(): OutboxEvent[];
  listDeletionGuards(): RepositoryDeletionGuard[];
};

export type LocalRepositoryOptions = {
  storage?: LocalRepositoryStorage | null;
  now?: () => number;
  idGenerator?: () => string;
  warn?: (message: string, error?: unknown) => void;
};

type Journal = {
  storageKey: string;
  transaction: "upsert" | "contains-delete";
  previousEntity: string | null;
  nextEntity: string;
  previousOutbox: string | null;
  nextOutbox: string;
  previousSyncVersion: string | null;
  nextSyncVersion: string;
  previousDeletionGuards: string | null;
  nextDeletionGuards: string;
};

const SENSITIVE_SYNC_KEY = /password|passwd|passphrase|token|bearer|api[\s_-]?key|secret|private[\s_-]?key|identity|passport|bank|card|medical|diagnos|address|location|evidence|rawtext|transcript|chathistory|conversation/i;

function createFallbackStorage(): LocalRepositoryStorage {
  const values = new Map<string, string>();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => {
      values.set(key, value);
    },
    removeItem: (key) => {
      values.delete(key);
    },
  };
}

function getDefaultStorage(): LocalRepositoryStorage {
  try {
    if (typeof globalThis !== "undefined" && globalThis.localStorage) {
      return globalThis.localStorage;
    }
  } catch {
    // Access to browser storage can be denied by privacy mode or a WebView.
  }
  return createFallbackStorage();
}

function defaultIdGenerator(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isIsoDate(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

function isOutboxOperation(value: unknown): value is OutboxOperation {
  return value === "upsert" || value === "delete";
}

function isRepositoryEntity(value: unknown): value is RepositoryEntity<unknown> {
  if (!isRecord(value)) return false;
  return (
    typeof value.id === "string" && value.id.length > 0
    && typeof value.deviceId === "string" && value.deviceId.length > 0
    && typeof value.schemaVersion === "number" && Number.isSafeInteger(value.schemaVersion) && value.schemaVersion > 0
    && typeof value.syncVersion === "number" && Number.isSafeInteger(value.syncVersion) && value.syncVersion >= 0
    && isIsoDate(value.updatedAt)
    && (value.deletedAt === null || isIsoDate(value.deletedAt))
    && "data" in value
  );
}

function isOutboxEvent(value: unknown): value is OutboxEvent {
  if (!isRecord(value)) return false;
  return (
    typeof value.eventId === "string" && value.eventId.length > 0
    && typeof value.entityType === "string" && value.entityType.length > 0
    && typeof value.entityId === "string" && value.entityId.length > 0
    && isOutboxOperation(value.operation)
    && typeof value.schemaVersion === "number" && Number.isSafeInteger(value.schemaVersion) && value.schemaVersion > 0
    && typeof value.deviceId === "string" && value.deviceId.length > 0
    && isIsoDate(value.createdAt)
    && typeof value.syncVersion === "number" && Number.isSafeInteger(value.syncVersion) && value.syncVersion > 0
    && (value.updatedAt === undefined || isIsoDate(value.updatedAt))
    && (value.deletedAt === undefined || value.deletedAt === null || isIsoDate(value.deletedAt))
  );
}

function parseOutbox(value: string | null, warn: (message: string, error?: unknown) => void): OutboxEvent[] {
  if (!value) return [];
  try {
    const parsed: unknown = JSON.parse(value);
    if (!Array.isArray(parsed) || !parsed.every(isOutboxEvent)) {
      throw new Error("Invalid outbox schema");
    }
    return parsed.map((event) => ({ ...event }));
  } catch (error) {
    warn("[local-repository] Invalid or damaged outbox; using an empty queue", error);
    return [];
  }
}

function parseJournal(value: string | null): Journal | null {
  if (!value) return null;
  try {
    const parsed: unknown = JSON.parse(value);
    if (!isRecord(parsed)) return null;
    if (
      typeof parsed.storageKey !== "string"
      || (parsed.previousEntity !== null && typeof parsed.previousEntity !== "string")
      || typeof parsed.nextEntity !== "string"
      || (parsed.previousOutbox !== null && typeof parsed.previousOutbox !== "string")
      || typeof parsed.nextOutbox !== "string"
      || (parsed.previousSyncVersion !== null && typeof parsed.previousSyncVersion !== "string")
      || typeof parsed.nextSyncVersion !== "string"
    ) return null;
    const transaction = parsed.transaction === "contains-delete" ? "contains-delete" : "upsert";
    const previousDeletionGuards =
      parsed.previousDeletionGuards === undefined || parsed.previousDeletionGuards === null
        ? null
        : typeof parsed.previousDeletionGuards === "string"
          ? parsed.previousDeletionGuards
          : null;
    const nextDeletionGuards =
      typeof parsed.nextDeletionGuards === "string" ? parsed.nextDeletionGuards : "[]";
    return {
      storageKey: parsed.storageKey,
      transaction,
      previousEntity: parsed.previousEntity,
      nextEntity: parsed.nextEntity,
      previousOutbox: parsed.previousOutbox,
      nextOutbox: parsed.nextOutbox,
      previousSyncVersion: parsed.previousSyncVersion,
      nextSyncVersion: parsed.nextSyncVersion,
      previousDeletionGuards,
      nextDeletionGuards,
    };
  } catch {
    return null;
  }
}

function isDeletionGuard(value: unknown): value is RepositoryDeletionGuard {
  if (!isRecord(value)) return false;
  return typeof value.storageKey === "string" && value.storageKey.length > 0
    && typeof value.entityType === "string" && value.entityType.length > 0
    && typeof value.entityId === "string" && value.entityId.length > 0
    && isIsoDate(value.deletedAt)
    && typeof value.syncVersion === "number"
    && Number.isSafeInteger(value.syncVersion)
    && value.syncVersion > 0;
}

function parseDeletionGuards(
  value: string | null,
  warn: (message: string, error?: unknown) => void,
): RepositoryDeletionGuard[] {
  if (!value) return [];
  try {
    const parsed: unknown = JSON.parse(value);
    if (!Array.isArray(parsed) || !parsed.every(isDeletionGuard)) {
      throw new Error("Invalid delete guard schema");
    }
    return parsed.map((guard) => ({ ...guard }));
  } catch (error) {
    warn("[local-repository] Invalid or damaged delete guards; using the safe empty projection", error);
    return [];
  }
}

export function readRepositoryDeletionGuards(
  storage: Pick<Storage, "getItem"> | null,
  warn: (message: string, error?: unknown) => void = console.warn,
): RepositoryDeletionGuard[] {
  if (!storage) return [];
  try {
    return parseDeletionGuards(
      storage.getItem(LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY),
      warn,
    );
  } catch (error) {
    warn("[local-repository] Failed to read delete guards; using the safe empty projection", error);
    return [];
  }
}

function isSensitiveValue(value: unknown): boolean {
  if (typeof value === "string") {
    return containsSensitiveCompanionText(value) || containsSensitiveCompanionData(value);
  }
  if (Array.isArray(value)) return value.some(isSensitiveValue);
  if (isRecord(value)) {
    return Object.entries(value).some(([key, item]) => SENSITIVE_SYNC_KEY.test(key) || isSensitiveValue(item));
  }
  return false;
}

export function containsSensitiveSyncText(value: unknown): boolean {
  return isSensitiveValue(value);
}

/**
 * Removes raw or sensitive strings before an event is placed in the outbox.
 * The local fact can still remain local; the future sync contract receives
 * only a safe projection of it.
 */
export function sanitizeOutboxPayload(value: unknown): unknown {
  if (typeof value === "string") {
    return containsSensitiveCompanionText(value) || containsSensitiveCompanionData(value)
      ? undefined
      : value;
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => sanitizeOutboxPayload(item))
      .filter((item) => item !== undefined);
  }
  if (isRecord(value)) {
    const output: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value)) {
      if (SENSITIVE_SYNC_KEY.test(key)) continue;
      const sanitized = sanitizeOutboxPayload(item);
      if (sanitized !== undefined) output[key] = sanitized;
    }
    return output;
  }
  return value;
}

function clearKey(storage: LocalRepositoryStorage, key: string): void {
  if (storage.removeItem) {
    storage.removeItem(key);
    return;
  }
  storage.setItem(key, "");
}

function cloneEvent(event: OutboxEvent): OutboxEvent {
  return { ...event };
}

function cloneEntity<T>(entity: RepositoryEntity<T>): RepositoryEntity<T> {
  return { ...entity };
}

function safeJson(value: unknown): string {
  return JSON.stringify(value) ?? "null";
}

export function applyOutboxEvent<T>(
  existing: RepositoryEntity<T> | null,
  event: OutboxEvent<T>,
  seenEventIds: ReadonlySet<string> = new Set(),
): OutboxApplyResult<T> {
  const nextSeenEventIds = new Set(seenEventIds);
  if (nextSeenEventIds.has(event.eventId)) {
    return { entity: existing ? cloneEntity(existing) : null, applied: false, seenEventIds: nextSeenEventIds };
  }
  nextSeenEventIds.add(event.eventId);
  if (existing && compareRepositoryVersion(existing, event) === "stale") {
    return { entity: cloneEntity(existing), applied: false, seenEventIds: nextSeenEventIds };
  }

  if (event.operation === "delete") {
    if (!existing) {
      return {
        entity: {
          id: event.entityId,
          deviceId: event.deviceId,
          schemaVersion: event.schemaVersion,
          syncVersion: event.syncVersion,
          updatedAt: event.updatedAt ?? event.createdAt,
          deletedAt: event.deletedAt ?? event.updatedAt ?? event.createdAt,
          data: null,
        },
        applied: true,
        seenEventIds: nextSeenEventIds,
      };
    }
    return {
      entity: {
        ...existing,
        deviceId: event.deviceId,
        schemaVersion: event.schemaVersion,
        syncVersion: event.syncVersion,
        updatedAt: event.updatedAt ?? event.createdAt,
        deletedAt: event.deletedAt ?? event.updatedAt ?? event.createdAt,
      },
      applied: true,
      seenEventIds: nextSeenEventIds,
    };
  }

  // There is no undelete/recreate operation in the current wire contract.
  // Keep a tombstone terminal so an old or cross-device upsert cannot revive
  // data after a delete-first delivery. A future sync design must explicitly
  // define recreation/conflict semantics before relaxing this guard.
  if (existing?.deletedAt) {
    return { entity: cloneEntity(existing), applied: false, seenEventIds: nextSeenEventIds };
  }

  if (event.payload === undefined) {
    return { entity: existing ? cloneEntity(existing) : null, applied: false, seenEventIds: nextSeenEventIds };
  }
  return {
    entity: {
      id: event.entityId,
      deviceId: event.deviceId,
      schemaVersion: event.schemaVersion,
      syncVersion: event.syncVersion,
      updatedAt: event.updatedAt ?? event.createdAt,
      deletedAt: event.deletedAt ?? null,
      data: event.payload,
    },
    applied: true,
    seenEventIds: nextSeenEventIds,
  };
}

export function createLocalRepository(options: LocalRepositoryOptions = {}): LocalRepository {
  const storage = options.storage ?? getDefaultStorage();
  const now = options.now ?? Date.now;
  const idGenerator = options.idGenerator ?? defaultIdGenerator;
  const warn = options.warn ?? console.warn;
  let recovered = false;
  let cachedDeviceId: string | null = null;

  const readRaw = (key: string): string | null => {
    try {
      return storage.getItem(key);
    } catch (error) {
      warn(`[local-repository] Failed to read ${key}`, error);
      return null;
    }
  };

  const writeRaw = (key: string, value: string): void => {
    storage.setItem(key, value);
  };

  const recoverPendingJournal = () => {
    if (recovered) return;
    recovered = true;
    const journalRaw = readRaw(LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY);
    if (!journalRaw) return;
    const journal = parseJournal(journalRaw);
    if (!journal) {
      warn("[local-repository] Invalid write journal; clearing it fail-safe");
      try {
        clearKey(storage, LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY);
      } catch (error) {
        warn("[local-repository] Failed to clear invalid write journal", error);
      }
      return;
    }

    try {
      const committed =
        readRaw(journal.storageKey) === journal.nextEntity
        && readRaw(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY) === journal.nextOutbox
        && readRaw(LOCAL_REPOSITORY_SYNC_VERSION_KEY) === journal.nextSyncVersion
        && readRaw(LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY) === journal.nextDeletionGuards;
      if (committed) {
        try {
          clearKey(storage, LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY);
        } catch (error) {
          warn("[local-repository] Committed write journal cleanup failed", error);
          recovered = false;
        }
        return;
      }

      if (journal.transaction === "contains-delete") {
        try {
          // Delete transactions recover forward. Restoring previousEntity here
          // would make a deleted Memory/Task visible again after a crash.
          writeRaw(journal.storageKey, journal.nextEntity);
          writeRaw(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY, journal.nextOutbox);
          writeRaw(LOCAL_REPOSITORY_SYNC_VERSION_KEY, journal.nextSyncVersion);
          writeRaw(LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY, journal.nextDeletionGuards);
          clearKey(storage, LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY);
        } catch (error) {
          warn("[local-repository] Delete recovery failed; keeping the delete guard and journal", error);
          recovered = false;
        }
        return;
      }

      if (journal.previousEntity === null) clearKey(storage, journal.storageKey);
      else writeRaw(journal.storageKey, journal.previousEntity);
      if (journal.previousOutbox === null) clearKey(storage, LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY);
      else writeRaw(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY, journal.previousOutbox);
      if (journal.previousSyncVersion === null) clearKey(storage, LOCAL_REPOSITORY_SYNC_VERSION_KEY);
      else writeRaw(LOCAL_REPOSITORY_SYNC_VERSION_KEY, journal.previousSyncVersion);
      if (journal.previousDeletionGuards === null) clearKey(storage, LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY);
      else writeRaw(LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY, journal.previousDeletionGuards);
      clearKey(storage, LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY);
    } catch (error) {
      warn("[local-repository] Write recovery failed; keeping journal for the next initialization", error);
      recovered = false;
    }
  };

  const getDeviceId = (): string => {
    recoverPendingJournal();
    if (cachedDeviceId) return cachedDeviceId;
    const stored = readRaw(LOCAL_REPOSITORY_DEVICE_ID_KEY)?.trim();
    if (stored) {
      cachedDeviceId = stored;
      return stored;
    }
    const generated = `device-${idGenerator().trim() || Date.now().toString(36)}`;
    cachedDeviceId = generated;
    try {
      writeRaw(LOCAL_REPOSITORY_DEVICE_ID_KEY, generated);
    } catch (error) {
      warn("[local-repository] Failed to persist deviceId; using an in-memory id", error);
    }
    return generated;
  };

  const listOutbox = (): OutboxEvent[] => {
    recoverPendingJournal();
    return parseOutbox(readRaw(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY), warn).map(cloneEvent);
  };

  const listDeletionGuards = (): RepositoryDeletionGuard[] => {
    recoverPendingJournal();
    return parseDeletionGuards(
      readRaw(LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY),
      warn,
    ).map((guard) => ({ ...guard }));
  };

  const readEntity = <T>(storageKey: string): RepositoryEntity<T> | null => {
    recoverPendingJournal();
    const raw = readRaw(storageKey);
    if (!raw) return null;
    try {
      const parsed: unknown = JSON.parse(raw);
      if (!isRepositoryEntity(parsed)) return null;
      const entity = parsed as RepositoryEntity<T>;
      const guard = parseDeletionGuards(
        readRaw(LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY),
        warn,
      ).find((candidate) =>
        candidate.storageKey === storageKey
        && candidate.entityId === entity.id
        && !entity.deletedAt
        && Date.parse(entity.updatedAt) <= Date.parse(candidate.deletedAt),
      );
      if (!guard) return cloneEntity(entity);
      return {
        ...entity,
        updatedAt: guard.deletedAt,
        syncVersion: Math.max(entity.syncVersion, guard.syncVersion),
        deletedAt: guard.deletedAt,
        data: null,
      };
    } catch (error) {
      warn(`[local-repository] Failed to parse entity ${storageKey}`, error);
      return null;
    }
  };

  const readValue = (key: string): string | null => {
    recoverPendingJournal();
    return readRaw(key);
  };

  const writeValue = (key: string, value: string): boolean => {
    recoverPendingJournal();
    try {
      writeRaw(key, value);
      return true;
    } catch (error) {
      warn(`[local-repository] Failed to write local value ${key}`, error);
      return false;
    }
  };

  const appendOutboxEvent = <T>(event: OutboxEvent<T>): boolean => {
    recoverPendingJournal();
    if (!isOutboxEvent(event) || containsSensitiveSyncText(event.payload)) return false;
    const events = listOutbox();
    if (events.some((item) => item.eventId === event.eventId)) return true;
    try {
      writeRaw(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY, safeJson([...events, cloneEvent(event)]));
      return true;
    } catch (error) {
      warn("[local-repository] Failed to append outbox event", error);
      return false;
    }
  };

  const writeEntity = <T, TPayload = unknown>(
    writeOptions: LocalRepositoryWriteOptions<T, TPayload>,
  ): LocalRepositoryWriteResult<T> => {
    recoverPendingJournal();
    const deviceId = getDeviceId();
    const previousEntity = readRaw(writeOptions.storageKey);
    const previousOutbox = readRaw(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY);
    const previousSyncVersion = readRaw(LOCAL_REPOSITORY_SYNC_VERSION_KEY);
    const previousDeletionGuards = readRaw(LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY);
    const existingOutbox = parseOutbox(previousOutbox, warn);
    const existingDeletionGuards = parseDeletionGuards(previousDeletionGuards, warn);
    const previousCounter = Number.parseInt(previousSyncVersion ?? "0", 10);
    const maxExistingSyncVersion = existingOutbox.reduce(
      (maximum, event) => Math.max(maximum, event.syncVersion),
      Number.isSafeInteger(previousCounter) && previousCounter > 0 ? previousCounter : 0,
    );
    const inputs: readonly LocalRepositoryEventInput[] = writeOptions.events?.length
      ? writeOptions.events
      : [{
          entityType: writeOptions.entityType,
          entityId: writeOptions.entityId,
          operation: writeOptions.deletedAt ? "delete" : "upsert",
          schemaVersion: writeOptions.schemaVersion,
          updatedAt: writeOptions.updatedAt,
          deletedAt: writeOptions.deletedAt,
          payload: writeOptions.payload,
        }];
    const createdAt = new Date(now()).toISOString();
    const events: OutboxEvent[] = inputs.map((input, index) => {
      const syncVersion = maxExistingSyncVersion + index + 1;
      const payload = sanitizeOutboxPayload(input.payload);
      const event: OutboxEvent = {
        eventId: `${deviceId}:${input.entityType}:${input.entityId}:${input.operation}:${syncVersion}`,
        entityType: input.entityType,
        entityId: input.entityId,
        operation: input.operation,
        schemaVersion: input.schemaVersion,
        deviceId,
        createdAt,
        syncVersion,
        updatedAt: input.updatedAt,
        deletedAt: input.deletedAt,
      };
      if (payload !== undefined) event.payload = payload;
      return event;
    });
    const nextOutboxEvents = [
      ...existingOutbox.filter((existing) => !events.some((event) => event.eventId === existing.eventId)),
      ...events,
    ];
    const nextSyncVersion = events[events.length - 1]?.syncVersion ?? maxExistingSyncVersion;
    const deletionGuardMap = new Map(
      existingDeletionGuards.map((guard) => [
        `${guard.storageKey}:${guard.entityType}:${guard.entityId}`,
        guard,
      ]),
    );
    for (const event of events) {
      if (event.operation !== "delete") continue;
      deletionGuardMap.set(
        `${writeOptions.storageKey}:${event.entityType}:${event.entityId}`,
        {
          storageKey: writeOptions.storageKey,
          entityType: event.entityType,
          entityId: event.entityId,
          deletedAt: event.deletedAt ?? event.updatedAt ?? event.createdAt,
          syncVersion: event.syncVersion,
        },
      );
    }
    const nextDeletionGuards = [...deletionGuardMap.values()];
    const hasDeletion = events.some((event) => event.operation === "delete");
    const entity: RepositoryEntity<T> = {
      id: writeOptions.entityId,
      deviceId,
      schemaVersion: writeOptions.schemaVersion,
      syncVersion: nextSyncVersion,
      updatedAt: writeOptions.updatedAt,
      deletedAt: writeOptions.deletedAt,
      data: writeOptions.data,
    };
    const nextEntity = safeJson(entity);
    const nextOutbox = safeJson(nextOutboxEvents);
    const journal: Journal = {
      storageKey: writeOptions.storageKey,
      transaction: hasDeletion ? "contains-delete" : "upsert",
      previousEntity,
      nextEntity,
      previousOutbox,
      nextOutbox,
      previousSyncVersion,
      nextSyncVersion: String(nextSyncVersion),
      previousDeletionGuards,
      nextDeletionGuards: safeJson(nextDeletionGuards),
    };

    try {
      if (hasDeletion) {
        // This guard is written before the journal so even a journal-write
        // failure cannot make the deleted record eligible for retrieval.
        writeRaw(LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY, safeJson(nextDeletionGuards));
      }
      writeRaw(LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY, safeJson(journal));
      writeRaw(writeOptions.storageKey, nextEntity);
      writeRaw(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY, nextOutbox);
      writeRaw(LOCAL_REPOSITORY_SYNC_VERSION_KEY, String(nextSyncVersion));
      try {
        clearKey(storage, LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY);
      } catch (error) {
        warn("[local-repository] Committed write journal cleanup failed", error);
        return { ok: false, entity: null, events: [], error };
      }
      return { ok: true, entity, events: events.map(cloneEvent) };
    } catch (error) {
      if (hasDeletion) {
        // Never roll back a delete transaction to previousEntity. The durable
        // guard plus the retained journal make the next initialization safe.
        warn("[local-repository] Delete write interrupted; retaining delete guard and journal", error);
        return { ok: false, entity: null, events: [], error };
      }
      let restored = true;
      try {
        if (previousEntity === null) clearKey(storage, writeOptions.storageKey);
        else writeRaw(writeOptions.storageKey, previousEntity);
        if (previousOutbox === null) clearKey(storage, LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY);
        else writeRaw(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY, previousOutbox);
        if (previousSyncVersion === null) clearKey(storage, LOCAL_REPOSITORY_SYNC_VERSION_KEY);
        else writeRaw(LOCAL_REPOSITORY_SYNC_VERSION_KEY, previousSyncVersion);
        if (previousDeletionGuards === null) clearKey(storage, LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY);
        else writeRaw(LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY, previousDeletionGuards);
        clearKey(storage, LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY);
      } catch (restoreError) {
        restored = false;
        warn("[local-repository] Failed to roll back a partial write; journal retained", restoreError);
      }
      if (restored) recovered = true;
      warn("[local-repository] Entity and outbox write failed", error);
      return { ok: false, entity: null, events: [], error };
    }
  };

  return {
    getDeviceId,
    readValue,
    writeValue,
    readEntity,
    writeEntity,
    appendOutboxEvent,
    listOutbox,
    listDeletionGuards,
  };
}
