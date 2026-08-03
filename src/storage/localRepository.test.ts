import { describe, expect, it } from "vitest";
import {
  applyOutboxEvent,
  compareRepositoryVersion,
  createLocalRepository,
  LOCAL_REPOSITORY_DEVICE_ID_KEY,
  LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY,
  LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY,
  LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY,
  LOCAL_REPOSITORY_SYNC_VERSION_KEY,
  type OutboxEvent,
  type RepositoryEntity,
  type LocalRepositoryStorage,
} from "./localRepository";
import {
  createProactiveExpressionState,
  PROACTIVE_EXPRESSION_STORAGE_KEY,
  writeProactiveExpressionState,
} from "../pet-core/proactiveExpressionGate";

type TestStorage = LocalRepositoryStorage & {
  values: Map<string, string>;
  failKeys: Set<string>;
  failOnceKeys: Set<string>;
  failOnceRemoveKeys: Set<string>;
};

function storage(): TestStorage {
  const values = new Map<string, string>();
  const target: TestStorage = {
    values,
    failKeys: new Set(),
    failOnceKeys: new Set(),
    failOnceRemoveKeys: new Set(),
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => {
      if (target.failKeys.has(key)) throw new Error(`write failed: ${key}`);
      if (target.failOnceKeys.delete(key)) throw new Error(`write failed once: ${key}`);
      values.set(key, value);
    },
    removeItem: (key) => {
      if (target.failKeys.has(key)) throw new Error(`remove failed: ${key}`);
      if (target.failOnceRemoveKeys.delete(key)) throw new Error(`remove failed once: ${key}`);
      values.delete(key);
    },
  };
  return target;
}

const ENTITY_OPTIONS = {
  storageKey: "entity-key",
  entityType: "task",
  entityId: "task-1",
  schemaVersion: 2,
  data: { title: "交报告" },
  updatedAt: "2026-08-02T12:00:00.000Z",
  deletedAt: null,
};

function upsertEvent(overrides: Partial<OutboxEvent> = {}): OutboxEvent {
  return {
    eventId: "device-a:task:task-1:upsert:1",
    entityType: "task",
    entityId: "task-1",
    operation: "upsert",
    schemaVersion: 2,
    deviceId: "device-a",
    createdAt: "2026-08-02T12:00:00.000Z",
    syncVersion: 1,
    payload: { title: "交报告" },
    ...overrides,
  };
}

describe("local repository", () => {
  it("round-trips entity metadata and keeps deviceId stable across initialization", () => {
    const store = storage();
    const repository = createLocalRepository({ storage: store, idGenerator: () => "stable-device" });
    const result = repository.writeEntity(ENTITY_OPTIONS);
    expect(result.ok).toBe(true);
    const restarted = createLocalRepository({ storage: store, idGenerator: () => "different-device" });
    const entity = restarted.readEntity<typeof ENTITY_OPTIONS.data>(ENTITY_OPTIONS.storageKey);
    expect(entity).toMatchObject({
      id: "task-1",
      deviceId: "device-stable-device",
      schemaVersion: 2,
      syncVersion: 1,
      updatedAt: ENTITY_OPTIONS.updatedAt,
      deletedAt: null,
      data: { title: "交报告" },
    });
    expect(restarted.getDeviceId()).toBe(repository.getDeviceId());
    expect(repository.listOutbox()).toHaveLength(1);
    expect(repository.listOutbox()[0]).toMatchObject({
      entityType: "task",
      entityId: "task-1",
      operation: "upsert",
      schemaVersion: 2,
      deviceId: "device-stable-device",
      syncVersion: 1,
    });
  });

  it("increments syncVersion monotonically and de-duplicates eventId", () => {
    const store = storage();
    const repository = createLocalRepository({ storage: store, idGenerator: () => "device" });
    const first = repository.writeEntity(ENTITY_OPTIONS);
    const second = repository.writeEntity({
      ...ENTITY_OPTIONS,
      data: { title: "交最终报告" },
      updatedAt: "2026-08-02T13:00:00.000Z",
      events: [{
        entityType: "task",
        entityId: "task-1",
        operation: "upsert",
        schemaVersion: 2,
        updatedAt: "2026-08-02T13:00:00.000Z",
        payload: { title: "交最终报告" },
      }],
    });

    expect(first.ok && second.ok).toBe(true);
    expect(repository.listOutbox().map((event) => event.syncVersion)).toEqual([1, 2]);
    expect(repository.appendOutboxEvent(first.ok ? first.events[0] : upsertEvent())).toBe(true);
    expect(repository.listOutbox()).toHaveLength(2);
    expect(store.getItem(LOCAL_REPOSITORY_SYNC_VERSION_KEY)).toBe("2");
  });

  it("keeps a deleted entity as a tombstone and ignores duplicate event application", () => {
    const store = storage();
    const repository = createLocalRepository({ storage: store, idGenerator: () => "device" });
    repository.writeEntity(ENTITY_OPTIONS);
    const deletedAt = "2026-08-02T14:00:00.000Z";
    const deleted = repository.writeEntity({
      ...ENTITY_OPTIONS,
      data: { title: "交报告" },
      updatedAt: deletedAt,
      deletedAt,
      events: [{
        entityType: "task",
        entityId: "task-1",
        operation: "delete",
        schemaVersion: 2,
        updatedAt: deletedAt,
        deletedAt,
      }],
    });
    expect(deleted.ok).toBe(true);
    expect(repository.readEntity(ENTITY_OPTIONS.storageKey)).toMatchObject({ deletedAt, syncVersion: 2 });

    const existing: RepositoryEntity<{ title: string }> = {
      id: "task-1",
      deviceId: "device-old",
      schemaVersion: 2,
      syncVersion: 1,
      updatedAt: ENTITY_OPTIONS.updatedAt,
      deletedAt: null,
      data: { title: "交报告" },
    };
    const event = upsertEvent({ syncVersion: 2, eventId: "event-2" });
    const applied = applyOutboxEvent(existing, event);
    const duplicate = applyOutboxEvent(applied.entity, event, applied.seenEventIds);
    expect(applied.applied).toBe(true);
    expect(duplicate.applied).toBe(false);
    expect(duplicate.entity).toEqual(applied.entity);
  });

  it.each([
    ["primary write", ENTITY_OPTIONS.storageKey],
    ["outbox write", LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY],
    ["sync counter write", LOCAL_REPOSITORY_SYNC_VERSION_KEY],
  ])("recovers a delete transaction forward after %s is interrupted", (_label, failedKey) => {
    const store = storage();
    const repository = createLocalRepository({ storage: store, idGenerator: () => "device" });
    expect(repository.writeEntity(ENTITY_OPTIONS).ok).toBe(true);

    store.failOnceKeys.add(failedKey);
    const deletedAt = "2026-08-02T14:00:00.000Z";
    const result = repository.writeEntity({
      ...ENTITY_OPTIONS,
      data: null,
      updatedAt: deletedAt,
      deletedAt,
      events: [{
        entityType: "task",
        entityId: "task-1",
        operation: "delete",
        schemaVersion: 2,
        updatedAt: deletedAt,
        deletedAt,
      }],
    });

    expect(result.ok).toBe(false);
    expect(repository.listDeletionGuards()).toEqual([
      expect.objectContaining({
        storageKey: ENTITY_OPTIONS.storageKey,
        entityType: "task",
        entityId: "task-1",
        deletedAt,
      }),
    ]);

    const restarted = createLocalRepository({ storage: store, idGenerator: () => "new-device" });
    expect(restarted.readEntity(ENTITY_OPTIONS.storageKey)).toMatchObject({
      deletedAt,
      data: null,
    });
    expect(restarted.listOutbox()).toEqual(expect.arrayContaining([
      expect.objectContaining({ entityType: "task", entityId: "task-1", operation: "delete" }),
    ]));
    expect(store.getItem(LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY)).toBeNull();
  });

  it("does not roll a committed delete back when journal cleanup is interrupted", () => {
    const store = storage();
    const repository = createLocalRepository({ storage: store, idGenerator: () => "device" });
    expect(repository.writeEntity(ENTITY_OPTIONS).ok).toBe(true);
    store.failOnceRemoveKeys.add(LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY);

    const deletedAt = "2026-08-02T14:30:00.000Z";
    const result = repository.writeEntity({
      ...ENTITY_OPTIONS,
      data: null,
      updatedAt: deletedAt,
      deletedAt,
      events: [{
        entityType: "task",
        entityId: "task-1",
        operation: "delete",
        schemaVersion: 2,
        updatedAt: deletedAt,
        deletedAt,
      }],
    });

    expect(result.ok).toBe(false);
    expect(store.getItem(ENTITY_OPTIONS.storageKey)).toContain('"data":null');
    expect(store.getItem(LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY)).toContain("task-1");

    const restarted = createLocalRepository({ storage: store });
    expect(restarted.readEntity(ENTITY_OPTIONS.storageKey)).toMatchObject({ deletedAt, data: null });
    expect(store.getItem(LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY)).toBeNull();
  });

  it("keeps a delete tombstone visible when the retained journal is damaged", () => {
    const store = storage();
    const repository = createLocalRepository({ storage: store, idGenerator: () => "device" });
    expect(repository.writeEntity(ENTITY_OPTIONS).ok).toBe(true);

    const deletedAt = "2026-08-02T15:00:00.000Z";
    store.failOnceKeys.add(ENTITY_OPTIONS.storageKey);
    expect(repository.writeEntity({
      ...ENTITY_OPTIONS,
      data: null,
      updatedAt: deletedAt,
      deletedAt,
      events: [{
        entityType: "task",
        entityId: "task-1",
        operation: "delete",
        schemaVersion: 2,
        updatedAt: deletedAt,
        deletedAt,
      }],
    }).ok).toBe(false);
    store.values.set(LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY, "damaged-journal");

    expect(createLocalRepository({ storage: store }).readEntity(ENTITY_OPTIONS.storageKey)).toMatchObject({
      deletedAt,
      data: null,
    });
  });

  it("materializes a delete-first tombstone and blocks an old upsert from reviving it", () => {
    const deleted = applyOutboxEvent(null, {
      eventId: "device-a:task:task-1:delete:5",
      entityType: "task",
      entityId: "task-1",
      operation: "delete",
      schemaVersion: 2,
      deviceId: "device-a",
      createdAt: "2026-08-02T14:00:00.000Z",
      syncVersion: 5,
      updatedAt: "2026-08-02T14:00:00.000Z",
      deletedAt: "2026-08-02T14:00:00.000Z",
    });

    expect(deleted.applied).toBe(true);
    expect(deleted.entity).toMatchObject({
      id: "task-1",
      deviceId: "device-a",
      syncVersion: 5,
      deletedAt: "2026-08-02T14:00:00.000Z",
      data: null,
    });

    const oldUpsert = applyOutboxEvent(
      deleted.entity,
      upsertEvent({
        eventId: "device-a:task:task-1:upsert:4",
        deviceId: "device-a",
        syncVersion: 4,
        createdAt: "2026-08-02T13:00:00.000Z",
        updatedAt: "2026-08-02T13:00:00.000Z",
        payload: { title: "旧任务" },
      }),
    );

    expect(oldUpsert.applied).toBe(false);
    expect(oldUpsert.entity).toEqual(deleted.entity);

    const crossDeviceUpsert = applyOutboxEvent(
      deleted.entity,
      upsertEvent({
        eventId: "device-b:task:task-1:upsert:1",
        deviceId: "device-b",
        syncVersion: 1,
        createdAt: "2026-08-02T13:00:00.000Z",
        updatedAt: "2026-08-02T13:00:00.000Z",
        payload: { title: "另一设备的旧任务" },
      }),
    );

    expect(compareRepositoryVersion(
      deleted.entity!,
      upsertEvent({ deviceId: "device-b", syncVersion: 1 }),
    )).toBe("incomparable");
    expect(crossDeviceUpsert.applied).toBe(false);
    expect(crossDeviceUpsert.entity).toEqual(deleted.entity);
  });

  it("treats syncVersion values from different devices as incomparable", () => {
    const existing: RepositoryEntity<{ title: string }> = {
      id: "task-1",
      deviceId: "device-a",
      schemaVersion: 2,
      syncVersion: 99,
      updatedAt: "2026-08-02T12:00:00.000Z",
      deletedAt: null,
      data: { title: "设备 A 的版本" },
    };
    const incoming = upsertEvent({
      eventId: "device-b:task:task-1:upsert:1",
      deviceId: "device-b",
      syncVersion: 1,
      payload: { title: "设备 B 的版本" },
    });

    expect(compareRepositoryVersion(existing, incoming)).toBe("incomparable");
    const applied = applyOutboxEvent(existing, incoming);
    expect(applied.applied).toBe(true);
    expect(applied.entity?.data).toEqual({ title: "设备 B 的版本" });
  });

  it("fails safely when a primary or outbox write fails", () => {
    const primaryFailure = storage();
    primaryFailure.failKeys.add(ENTITY_OPTIONS.storageKey);
    const primaryResult = createLocalRepository({ storage: primaryFailure }).writeEntity(ENTITY_OPTIONS);
    expect(primaryResult.ok).toBe(false);
    expect(primaryFailure.getItem(ENTITY_OPTIONS.storageKey)).toBeNull();
    expect(primaryFailure.getItem(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY)).toBeNull();

    const outboxFailure = storage();
    outboxFailure.failOnceKeys.add(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY);
    const outboxResult = createLocalRepository({ storage: outboxFailure }).writeEntity(ENTITY_OPTIONS);
    expect(outboxResult.ok).toBe(false);
    expect(outboxFailure.getItem(ENTITY_OPTIONS.storageKey)).toBeNull();
    expect(outboxFailure.getItem(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY)).toBeNull();
  });

  it("recovers damaged data and a retained journal on the next initialization", () => {
    const damaged = storage();
    damaged.values.set(ENTITY_OPTIONS.storageKey, "not-json");
    damaged.values.set(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY, "not-json");
    const warnings: string[] = [];
    const repository = createLocalRepository({ storage: damaged, warn: (message) => warnings.push(message) });
    expect(repository.readEntity(ENTITY_OPTIONS.storageKey)).toBeNull();
    expect(repository.listOutbox()).toEqual([]);
    expect(warnings.length).toBeGreaterThan(0);

    const journalStore = storage();
    journalStore.failKeys.add(LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY);
    const failed = createLocalRepository({ storage: journalStore }).writeEntity(ENTITY_OPTIONS);
    expect(failed.ok).toBe(false);
    journalStore.failKeys.clear();
    const recovered = createLocalRepository({ storage: journalStore });
    expect(recovered.readEntity(ENTITY_OPTIONS.storageKey)).toBeNull();
    expect(journalStore.getItem(LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY)).toBeNull();

    const partialValues = new Map<string, string>();
    let failEntityRollbackOnce = true;
    const partialStorage: LocalRepositoryStorage = {
      getItem: (key) => partialValues.get(key) ?? null,
      setItem: (key, value) => {
        if (key === LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY) {
          throw new Error("outbox quota exceeded");
        }
        partialValues.set(key, value);
      },
      removeItem: (key) => {
        if (key === ENTITY_OPTIONS.storageKey && failEntityRollbackOnce) {
          failEntityRollbackOnce = false;
          throw new Error("rollback interrupted");
        }
        partialValues.delete(key);
      },
    };
    const partialResult = createLocalRepository({ storage: partialStorage }).writeEntity(ENTITY_OPTIONS);
    expect(partialResult.ok).toBe(false);
    expect(partialValues.get(LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY)).not.toBeNull();

    const recoveredPartial = createLocalRepository({ storage: partialStorage });
    expect(recoveredPartial.readEntity(ENTITY_OPTIONS.storageKey)).toBeNull();
    expect(partialValues.get(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY)).toBeUndefined();
    expect(partialValues.get(LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY)).toBeUndefined();
  });

  it("filters sensitive values from outbox payloads", () => {
    const store = storage();
    const repository = createLocalRepository({ storage: store, idGenerator: () => "device" });
    const result = repository.writeEntity({
      ...ENTITY_OPTIONS,
      payload: { title: "普通任务", note: "密码是 secret-123" },
    });
    expect(result.ok).toBe(true);
    const outbox = store.getItem(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY) ?? "";
    expect(outbox).not.toContain("secret-123");
    expect(outbox).not.toContain("密码");
    expect(repository.appendOutboxEvent(upsertEvent({
      eventId: "sensitive",
      payload: { content: "银行卡 1234" },
    }))).toBe(false);
    expect(repository.appendOutboxEvent(upsertEvent({
      eventId: "sensitive-key",
      payload: { password: "arbitrary-secret" },
    }))).toBe(false);
  });

  it("blocks unlabeled credential shapes from the outbox", () => {
    const store = storage();
    const repository = createLocalRepository({ storage: store, idGenerator: () => "device" });
    for (const [index, value] of [
      "sk-proj-12345678901234567890",
      "ghp_12345678901234567890",
      "github_pat_12345678901234567890",
      "xoxb-12345678901234567890",
      "AIza123456789012345678901234567890",
      "Bearer abcdefghijklmnop",
    ].entries()) {
      expect(repository.appendOutboxEvent(upsertEvent({
        eventId: `credential-${index}`,
        payload: { value },
      }))).toBe(false);
    }
    expect(store.getItem(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY) ?? "").not.toMatch(
      /sk-proj|ghp_|github_pat_|xoxb-|AIza|Bearer|abcdefghijklmnop/,
    );
  });

  it("does not mix repository namespaces", () => {
    const store = storage();
    const repository = createLocalRepository({ storage: store, idGenerator: () => "device" });
    repository.writeEntity(ENTITY_OPTIONS);
    const memoryRepository = createLocalRepository({ storage: store, idGenerator: () => "device" });
    memoryRepository.writeEntity({
      ...ENTITY_OPTIONS,
      storageKey: "memory-key",
      entityType: "memory",
      entityId: "memory-1",
      schemaVersion: 1,
      data: { content: "用户喜欢桂花茶" },
      events: [{
        entityType: "memory",
        entityId: "memory-1",
        operation: "upsert",
        schemaVersion: 1,
        payload: { content: "用户喜欢桂花茶" },
      }],
    });
    expect(writeProactiveExpressionState(
      createProactiveExpressionState(new Date("2026-08-02T15:00:00.000Z")),
      store,
    )).toBe(true);
    expect(repository.readEntity(ENTITY_OPTIONS.storageKey)?.data).toEqual({ title: "交报告" });
    expect(memoryRepository.readEntity("memory-key")?.data).toEqual({ content: "用户喜欢桂花茶" });
    expect(repository.listOutbox().map((event) => event.entityType)).toEqual(["task", "memory"]);
    expect(store.getItem(LOCAL_REPOSITORY_DEVICE_ID_KEY)).toBe("device-device");
    expect(store.getItem(PROACTIVE_EXPRESSION_STORAGE_KEY)).toContain('"schemaVersion":1');
  });
});
