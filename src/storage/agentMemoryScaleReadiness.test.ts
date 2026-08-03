import { describe, expect, it } from "vitest";
import {
  applyOutboxEvent,
  createLocalRepository,
  LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY,
  LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY,
  type LocalRepositoryStorage,
  type OutboxEvent,
} from "./localRepository";
import {
  COMPANION_MEMORY_SCHEMA_VERSION,
  COMPANION_MEMORY_STORAGE_KEY,
  createCompanionMemoryRepository,
  type MemoryEntry,
} from "../pet-core/companionMemory";
import {
  EMPTY_TASK_DATABASE,
} from "../task-core/taskStore";
import {
  selectProactiveTaskCandidates,
  createProactiveTriggerEngine,
} from "../pet-core/proactiveTriggerEngine";
import type { Reminder, ReminderInstance, Task, TaskDatabase } from "../task-core/types";

type FixtureStorage = LocalRepositoryStorage & {
  values: Map<string, string>;
  failKeys: Set<string>;
};

const NOW_MS = Date.parse("2026-08-02T12:00:00.000Z");
const NOW = new Date(NOW_MS);
const FIXTURE_DEVICE_ID = "fixture-device";

function createFixtureStorage(): FixtureStorage {
  const values = new Map<string, string>();
  const storage: FixtureStorage = {
    values,
    failKeys: new Set(),
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => {
      if (storage.failKeys.has(key)) throw new Error(`fixture write failed: ${key}`);
      values.set(key, value);
    },
    removeItem: (key) => {
      if (storage.failKeys.has(key)) throw new Error(`fixture remove failed: ${key}`);
      values.delete(key);
    },
  };
  return storage;
}

function byteLength(value: string | null): number {
  return value === null ? 0 : new TextEncoder().encode(value).byteLength;
}

function percentile(values: readonly number[], fraction: number): number {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.floor((sorted.length - 1) * fraction)] ?? 0;
}

function measureDurations<T>(
  operation: () => T,
  samples: number,
  warmup = 10,
): { p50Ms: number; p95Ms: number; samples: number } {
  for (let index = 0; index < warmup; index += 1) operation();
  const durations: number[] = [];
  for (let index = 0; index < samples; index += 1) {
    const startedAt = performance.now();
    operation();
    durations.push(performance.now() - startedAt);
  }
  return {
    p50Ms: percentile(durations, 0.5),
    p95Ms: percentile(durations, 0.95),
    samples,
  };
}

function createMemoryFixture(count: number): MemoryEntry[] {
  return Array.from({ length: count }, (_, index) => ({
    id: `fixture-memory-${index}`,
    scope: index % 5 === 0 ? "pet:xiaoju-cat" as const : "global" as const,
    type: "preference" as const,
    content: `用户喜欢桂花茶，以及第 ${index} 项稳定偏好`,
    source: "explicit" as const,
    evidence: `用户在 fixture 对话 ${index} 中明确要求记住这项偏好`,
    sourceMessageId: `fixture-message-${index}`,
    confidence: 0.9,
    createdAt: "2026-08-01T12:00:00.000Z",
    updatedAt: "2026-08-02T11:00:00.000Z",
    expiresAt: null,
    status: "active" as const,
    supersedesId: null,
    deletedAt: null,
  }));
}

function seedMemoryFixture(count = 200): {
  storage: FixtureStorage;
  repository: ReturnType<typeof createCompanionMemoryRepository>;
  entries: MemoryEntry[];
} {
  const storage = createFixtureStorage();
  const entries = createMemoryFixture(count);
  const localRepository = createLocalRepository({
    storage,
    idGenerator: () => FIXTURE_DEVICE_ID,
    now: () => NOW_MS,
    warn: () => undefined,
  });
  const state = { version: COMPANION_MEMORY_SCHEMA_VERSION, entries };
  const result = localRepository.writeEntity({
    storageKey: COMPANION_MEMORY_STORAGE_KEY,
    entityType: "memory-state",
    entityId: "memory-collection",
    schemaVersion: COMPANION_MEMORY_SCHEMA_VERSION,
    data: state,
    updatedAt: NOW.toISOString(),
    deletedAt: null,
    events: entries.map((entry) => ({
      entityType: "memory",
      entityId: entry.id,
      operation: "upsert" as const,
      schemaVersion: COMPANION_MEMORY_SCHEMA_VERSION,
      updatedAt: entry.updatedAt,
      deletedAt: null,
      payload: entry,
    })),
  });
  if (!result.ok) throw new Error("fixture memory seed failed");

  return {
    storage,
    entries,
    repository: createCompanionMemoryRepository({
      storage,
      now: () => NOW_MS,
      warn: () => undefined,
    }),
  };
}

function createOutboxFixtureEvent(index: number): OutboxEvent {
  return {
    eventId: `${FIXTURE_DEVICE_ID}:fixture:entity-${index}:upsert:${index + 1}`,
    entityType: "fixture",
    entityId: `entity-${index}`,
    operation: "upsert",
    schemaVersion: 1,
    deviceId: FIXTURE_DEVICE_ID,
    createdAt: NOW.toISOString(),
    syncVersion: index + 1,
    updatedAt: NOW.toISOString(),
    deletedAt: null,
    payload: { title: `fixture entity ${index}` },
  };
}

function createTaskFixture(count: number): TaskDatabase {
  const tasks: Task[] = [];
  const reminders: Reminder[] = [];
  const reminderInstances: ReminderInstance[] = [];
  for (let index = 0; index < count; index += 1) {
    const taskId = `fixture-task-${index}`;
    const reminderId = `fixture-reminder-${index}`;
    const instanceId = `fixture-instance-${index}`;
    const scheduledAt = index % 2 === 0
      ? "2026-08-02T11:59:00.000Z"
      : "2026-08-02T18:00:00.000Z";
    tasks.push({
      id: taskId,
      title: `整理第 ${index} 项资料`,
      note: "fixture task",
      status: "pending",
      priority: index % 10 === 0 ? "high" : "normal",
      projectId: "fixture-project",
      dueAt: scheduledAt,
      kind: "single",
      parentTaskId: null,
      startAt: null,
      schedulePrecision: "datetime",
      includeToday: true,
      attachmentRefs: [],
      completedAt: null,
      cancelledAt: null,
      postponedCount: 0,
      createdAt: "2026-08-01T12:00:00.000Z",
      updatedAt: "2026-08-02T11:00:00.000Z",
      deletedAt: null,
      archivedAt: null,
      archiveReason: null,
      version: 1,
      sourceDeviceId: FIXTURE_DEVICE_ID,
    });
    reminders.push({
      id: reminderId,
      taskId,
      remindAt: scheduledAt,
      repeatType: "none",
      repeatRule: null,
      status: "active",
      snoozeCount: 0,
      createdAt: "2026-08-01T12:00:00.000Z",
      updatedAt: "2026-08-02T11:00:00.000Z",
      deletedAt: null,
      version: 1,
    });
    reminderInstances.push({
      id: instanceId,
      reminderId,
      taskId,
      scheduledAt,
      triggeredAt: null,
      snoozedFrom: null,
      snoozeCount: 0,
      dismissedAt: null,
      handledAt: null,
      status: "scheduled",
      createdAt: "2026-08-01T12:00:00.000Z",
      updatedAt: "2026-08-02T11:00:00.000Z",
    });
  }
  return {
    ...EMPTY_TASK_DATABASE,
    tasks,
    reminders,
    reminderInstances,
    history: [],
    metrics: {},
    settings: { ...EMPTY_TASK_DATABASE.settings },
  };
}

function createEntityWriteOptions(storageKey = "fixture-entity") {
  return {
    storageKey,
    entityType: "fixture",
    entityId: "fixture-entity",
    schemaVersion: 1,
    data: { title: "fixture" },
    updatedAt: NOW.toISOString(),
    deletedAt: null,
  };
}

describe("agent memory scale readiness fixtures", () => {
  it("measures bounded local fixtures and records recovery outcomes", () => {
    const memoryFixture = seedMemoryFixture();
    const memoryRepository = memoryFixture.repository;
    const memorySearch = measureDurations(
      () => memoryRepository.search("桂花茶", { petId: "xiaoju-cat" }),
      1000,
      100,
    );
    const memoryRaw = memoryFixture.storage.getItem(COMPANION_MEMORY_STORAGE_KEY);
    const memoryOutboxRaw = memoryFixture.storage.getItem(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY);
    expect(memoryRepository.list()).toHaveLength(memoryFixture.entries.length);
    expect(memoryRepository.search("桂花茶", { petId: "xiaoju-cat" })).not.toHaveLength(0);

    const outboxStorage = createFixtureStorage();
    const outboxRepository = createLocalRepository({
      storage: outboxStorage,
      idGenerator: () => FIXTURE_DEVICE_ID,
      now: () => NOW_MS,
      warn: () => undefined,
    });
    const outboxStartedAt = performance.now();
    const outboxFixtureCount = 256;
    for (let index = 0; index < outboxFixtureCount; index += 1) {
      expect(outboxRepository.appendOutboxEvent(createOutboxFixtureEvent(index))).toBe(true);
    }
    const outboxElapsedMs = performance.now() - outboxStartedAt;
    const outboxRaw = outboxStorage.getItem(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY);
    const outboxSizeBytes = byteLength(outboxRaw);
    const taskFixture = createTaskFixture(1000);
    const taskCandidates = selectProactiveTaskCandidates(taskFixture, NOW);
    const taskScan = measureDurations(
      () => selectProactiveTaskCandidates(taskFixture, NOW),
      50,
      10,
    );
    const proactiveEvaluation = measureDurations(
      () => {
        const engine = createProactiveTriggerEngine({
          activePetId: "xiaoju-cat",
          availablePetIds: ["xiaoju-cat", "black-cat"],
          dailyLimit: 10_000,
          storage: createFixtureStorage(),
        });
        return engine.evaluate(taskCandidates, NOW);
      },
      50,
      10,
    );
    expect(taskCandidates.length).toBe(500);

    const corruptStorage = createFixtureStorage();
    corruptStorage.values.set("fixture-entity", "not-json");
    corruptStorage.values.set(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY, "not-json");
    const corruptRepository = createLocalRepository({
      storage: corruptStorage,
      warn: () => undefined,
    });
    const corruptRecovery = {
      entityIsNull: corruptRepository.readEntity("fixture-entity") === null,
      outboxIsEmpty: corruptRepository.listOutbox().length === 0,
    };

    const failingStorage = createFixtureStorage();
    failingStorage.failKeys.add("fixture-entity");
    const failedWrite = createLocalRepository({
      storage: failingStorage,
      warn: () => undefined,
    }).writeEntity(createEntityWriteOptions());
    const writeFailureRecovery = {
      writeReturnedFalse: !failedWrite.ok,
      entityIsAbsent: failingStorage.getItem("fixture-entity") === null,
      outboxIsAbsent: failingStorage.getItem(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY) === null,
    };

    const partialValues = new Map<string, string>();
    let failEntityRollbackOnce = true;
    const partialStorage: LocalRepositoryStorage = {
      getItem: (key) => partialValues.get(key) ?? null,
      setItem: (key, value) => {
        if (key === LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY) throw new Error("fixture outbox failure");
        partialValues.set(key, value);
      },
      removeItem: (key) => {
        if (key === "fixture-entity" && failEntityRollbackOnce) {
          failEntityRollbackOnce = false;
          throw new Error("fixture rollback interruption");
        }
        partialValues.delete(key);
      },
    };
    const partialResult = createLocalRepository({
      storage: partialStorage,
      warn: () => undefined,
    }).writeEntity(createEntityWriteOptions());
    const journalRetained = partialValues.has(LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY);
    const recoveredRepository = createLocalRepository({
      storage: partialStorage,
      warn: () => undefined,
    });
    const journalRecovery = {
      writeReturnedFalse: !partialResult.ok,
      journalWasRetained: journalRetained,
      entityIsAbsentAfterRestart: recoveredRepository.readEntity("fixture-entity") === null,
      journalCleared: !partialValues.has(LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY),
    };

    expect(corruptRecovery).toEqual({ entityIsNull: true, outboxIsEmpty: true });
    expect(writeFailureRecovery).toEqual({
      writeReturnedFalse: true,
      entityIsAbsent: true,
      outboxIsAbsent: true,
    });
    expect(journalRecovery).toEqual({
      writeReturnedFalse: true,
      journalWasRetained: true,
      entityIsAbsentAfterRestart: true,
      journalCleared: true,
    });

    const measurement = {
      fixtureOnly: true,
      measurementRunAt: new Date().toISOString(),
      fixtureNow: NOW.toISOString(),
      memory: {
        entries: memoryFixture.entries.length,
        storageBytesUtf8: byteLength(memoryRaw),
        outboxEvents: JSON.parse(memoryOutboxRaw ?? "[]").length,
        outboxBytesUtf8: byteLength(memoryOutboxRaw),
        keywordSearch: memorySearch,
      },
      outbox: {
        events: outboxRepository.listOutbox().length,
        storageBytesUtf8: outboxSizeBytes,
        appendElapsedMs: outboxElapsedMs,
        eventsPerSecond: outboxFixtureCount / Math.max(outboxElapsedMs / 1000, Number.EPSILON),
        bytesPerSecond: outboxSizeBytes / Math.max(outboxElapsedMs / 1000, Number.EPSILON),
      },
      tasks: {
        tasks: taskFixture.tasks.length,
        candidates: taskCandidates.length,
        scan: taskScan,
        proactiveEvaluation,
      },
      recovery: {
        corruptData: corruptRecovery,
        writeFailure: writeFailureRecovery,
        journal: journalRecovery,
      },
    };
    console.info(`[scale-readiness-fixture] ${JSON.stringify(measurement)}`);
  }, 15_000);

  it("keeps delete-first tombstones terminal for fixture sync events", () => {
    const deleted = applyOutboxEvent(null, {
      eventId: "fixture-device-a:fixture:entity-1:delete:2",
      entityType: "fixture",
      entityId: "entity-1",
      operation: "delete",
      schemaVersion: 1,
      deviceId: "fixture-device-a",
      createdAt: NOW.toISOString(),
      syncVersion: 2,
      deletedAt: NOW.toISOString(),
    });
    const oldUpsert = applyOutboxEvent(deleted.entity, {
      eventId: "fixture-device-b:fixture:entity-1:upsert:1",
      entityType: "fixture",
      entityId: "entity-1",
      operation: "upsert",
      schemaVersion: 1,
      deviceId: "fixture-device-b",
      createdAt: "2026-08-02T11:00:00.000Z",
      syncVersion: 1,
      payload: { title: "old" },
    });
    expect(deleted.entity?.deletedAt).toBe(NOW.toISOString());
    expect(oldUpsert.applied).toBe(false);
    expect(oldUpsert.entity).toEqual(deleted.entity);
  });
});
