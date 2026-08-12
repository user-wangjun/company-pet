import { describe, expect, test, vi } from "vitest";
import {
  COMPANION_MEMORY_SCHEMA_VERSION,
  COMPANION_MEMORY_STORAGE_KEY,
  confirmCompanionMemoryCandidate,
  createCompanionMemoryRepository,
  extractCompanionMemoryCandidate,
  saveCompanionMemoryCandidate,
  searchCompanionMemorySafely,
  type MemoryEntryInput,
  type MemoryRepository,
} from "./companionMemory";
import {
  LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY,
  LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY,
  LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY,
  LOCAL_REPOSITORY_SYNC_VERSION_KEY,
} from "../storage/localRepository";

function createStorage(initial: string | null = null) {
  const values = new Map<string, string>();
  const failOnceKeys = new Set<string>();
  if (initial !== null) values.set(COMPANION_MEMORY_STORAGE_KEY, initial);
  return {
    values,
    failOnceKeys,
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, next: string) => {
      if (failOnceKeys.delete(key)) throw new Error(`write failed once: ${key}`);
      values.set(key, next);
    }),
    corrupt(next: string) {
      values.set(COMPANION_MEMORY_STORAGE_KEY, next);
    },
  };
}

function memoryInput(
  content: string,
  overrides: Partial<MemoryEntryInput> = {},
): MemoryEntryInput {
  return {
    id: content,
    scope: "global",
    type: "fact",
    content,
    source: "explicit",
    evidence: `请记住${content}`,
    sourceMessageId: `message-${content}`,
    confidence: 0.95,
    expiresAt: null,
    status: "active",
    supersedesId: null,
    ...overrides,
  };
}

const NOW = Date.parse("2026-08-02T12:00:00.000Z");

describe("local companion memory v1", () => {
  test("round-trips entries through the versioned repository", () => {
    const store = createStorage();
    const repository = createCompanionMemoryRepository({
      storage: store,
      now: () => NOW,
      idGenerator: () => "generated-id",
    });

    const saved = repository.save(
      memoryInput("用户喜欢桂花茶", {
        id: undefined,
        createdAt: "2026-08-01T10:00:00.000Z",
        updatedAt: "2026-08-01T10:00:00.000Z",
      }),
    );
    expect(saved).not.toBeNull();
    expect(store.setItem).toHaveBeenCalledWith(
      COMPANION_MEMORY_STORAGE_KEY,
      expect.stringContaining(`"version":${COMPANION_MEMORY_SCHEMA_VERSION}`),
    );

    const reloaded = createCompanionMemoryRepository({ storage: store, now: () => NOW });
    expect(reloaded.get("generated-id")).toEqual(saved);
    expect(reloaded.list()).toHaveLength(1);
  });

  test("migrates legacy entries without deletedAt and writes a tombstone event", () => {
    const store = createStorage(JSON.stringify({
      version: 1,
      entries: [{
        ...memoryInput("旧 Memory", {
          id: "legacy-memory",
          createdAt: "2026-08-01T10:00:00.000Z",
          updatedAt: "2026-08-01T10:00:00.000Z",
          deletedAt: undefined,
        }),
      }],
    }));
    const repository = createCompanionMemoryRepository({ storage: store, now: () => NOW });
    expect(repository.get("legacy-memory")?.deletedAt).toBeNull();

    expect(repository.delete("legacy-memory")?.deletedAt).toBe("2026-08-02T12:00:00.000Z");
    const outbox = JSON.parse(store.getItem(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY) ?? "[]") as Array<Record<string, unknown>>;
    expect(outbox).toEqual(expect.arrayContaining([
      expect.objectContaining({
        entityType: "memory",
        entityId: "legacy-memory",
        operation: "delete",
        deletedAt: "2026-08-02T12:00:00.000Z",
      }),
    ]));
  });

  test("derives a tombstone timestamp for legacy deleted entries missing deletedAt", () => {
    const legacy = memoryInput("已删除的旧 Memory", {
      id: "legacy-deleted-memory",
      status: "deleted",
      createdAt: "2026-08-01T10:00:00.000Z",
      updatedAt: "2026-08-01T11:00:00.000Z",
      deletedAt: undefined,
    });
    const repository = createCompanionMemoryRepository({
      storage: createStorage(JSON.stringify({ version: 1, entries: [legacy] })),
      now: () => NOW,
    });

    expect(repository.get("legacy-deleted-memory")?.deletedAt).toBe("2026-08-01T11:00:00.000Z");
  });

  test("falls back to empty memory when storage is damaged or incomplete", () => {
    const store = createStorage('{"version":1,"entries":[{"id":"broken"}]}');
    const warn = vi.fn();
    const repository = createCompanionMemoryRepository({ storage: store, warn });

    expect(repository.list()).toEqual([]);
    expect(repository.search("茶", { petId: "xiaoju-cat" })).toEqual([]);
    expect(warn).toHaveBeenCalled();
  });

  test("rejects sensitive memory identifiers as well as content", () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });

    expect(repository.save(memoryInput("用户喜欢茶", {
      id: "sk-proj-12345678901234567890",
    }))).toBeNull();
    expect(repository.save(memoryInput("用户喜欢茶", {
      id: "safe-id",
      sourceMessageId: "message-safe",
      supersedesId: "sk-proj-12345678901234567890",
    }))).toBeNull();
  });

  test("makes global memory visible to the current pet but isolates pet relationships", () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    repository.save(memoryInput("用户喜欢猫", { id: "global-cat" }));
    // Keep the storage contract keyed so repository metadata cannot overwrite the fact.
    repository.save(
      memoryInput("和小橘一起看雨", {
        id: "pet-a-rain",
        scope: "pet:xiaoju-cat",
        type: "relationship",
      }),
    );
    repository.save(
      memoryInput("和篮球伙伴一起训练", {
        id: "pet-b-ball",
        scope: "pet:ikun",
        type: "relationship",
      }),
    );

    const xiaojuResults = repository.search("猫", { petId: "xiaoju-cat" });
    expect(xiaojuResults.map((entry) => entry.id)).toContain("global-cat");
    expect(repository.search("一起", { petId: "xiaoju-cat" }).map((entry) => entry.id)).toEqual([
      "pet-a-rain",
    ]);
    expect(repository.search("训练", { petId: "xiaoju-cat" })).toEqual([]);
    expect(repository.search("训练", { petId: "ikun" }).map((entry) => entry.id)).toEqual([
      "pet-b-ball",
    ]);
  });

  test("filters disabled, deleted, superseded, and expired memory", () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    repository.save(memoryInput("active 茶", { id: "active" }));
    repository.save(memoryInput("disabled 茶", { id: "disabled", status: "disabled" }));
    repository.save(memoryInput("deleted 茶", { id: "deleted", status: "deleted" }));
    repository.save(memoryInput("superseded 茶", { id: "superseded", status: "superseded" }));
    repository.save(
      memoryInput("expired 茶", {
        id: "expired",
        expiresAt: "2026-08-02T11:59:59.999Z",
      }),
    );

    expect(repository.search("active", { petId: "xiaoju-cat" }).map((entry) => entry.id)).toEqual([
      "active",
    ]);
    expect(repository.search("disabled", { petId: "xiaoju-cat" })).toEqual([]);
    expect(repository.search("deleted", { petId: "xiaoju-cat" })).toEqual([]);
    expect(repository.search("superseded", { petId: "xiaoju-cat" })).toEqual([]);
    expect(repository.search("expired", { petId: "xiaoju-cat" })).toEqual([]);
  });

  test("returns at most three relevant memories and ignores low-relevance queries", () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    for (let index = 0; index < 5; index += 1) {
      repository.save(memoryInput(`用户喜欢猫${index}`, { id: `cat-${index}` }));
    }

    expect(repository.search("喜欢猫", { petId: "xiaoju-cat" })).toHaveLength(3);
    expect(repository.search("火车站", { petId: "xiaoju-cat" })).toEqual([]);
  });

  test.each([198, 199])("allows an atomic supersede at the %i-entry boundary", (count) => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    for (let index = 0; index < count; index += 1) {
      expect(repository.save(memoryInput(`边界事实-${index}`, { id: `boundary-${index}` }))).not.toBeNull();
    }

    const previous = repository.get("boundary-0")!;
    const replaced = repository.supersede(
      previous.id,
      memoryInput(`边界替换-${count}`, { id: `boundary-replacement-${count}` }),
    );

    expect(replaced).toMatchObject({
      id: `boundary-replacement-${count}`,
      status: "active",
      supersedesId: previous.id,
    });
    expect(repository.list({ includeDeleted: true })).toHaveLength(count + 1);
  });

  test("rejects a supersede that would exceed 200 entries without touching local facts or Outbox", () => {
    const store = createStorage();
    const repository = createCompanionMemoryRepository({ storage: store, now: () => NOW });
    for (let index = 0; index < 200; index += 1) {
      expect(repository.save(memoryInput(`容量事实-${index}`, { id: `capacity-${index}` }))).not.toBeNull();
    }
    const previous = repository.get("capacity-0")!;
    const keys = [
      COMPANION_MEMORY_STORAGE_KEY,
      LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY,
      LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY,
      LOCAL_REPOSITORY_DELETE_GUARD_STORAGE_KEY,
      LOCAL_REPOSITORY_SYNC_VERSION_KEY,
    ];
    const before = new Map(keys.map((key) => [key, store.values.get(key)]));

    expect(repository.supersede(
      previous.id,
      memoryInput("容量替换", { id: "capacity-replacement" }),
    )).toBeNull();

    expect(repository.get(previous.id)).toMatchObject({ status: "active", content: "容量事实-0" });
    const rawEntity = JSON.parse(store.values.get(COMPANION_MEMORY_STORAGE_KEY) ?? "null") as {
      data?: { entries?: unknown[] };
    };
    expect(rawEntity.data?.entries).toHaveLength(200);
    for (const key of keys) expect(store.values.get(key)).toBe(before.get(key));

    const restarted = createCompanionMemoryRepository({ storage: store, now: () => NOW });
    expect(restarted.list({ includeDeleted: true })).toHaveLength(200);
    expect(restarted.get(previous.id)).toMatchObject({ status: "active", content: "容量事实-0" });
  });

  test("fails closed instead of silently replacing a different entry with the same id", () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    expect(repository.save(memoryInput("第一个事实", { id: "same-id" }))).not.toBeNull();
    expect(repository.save(memoryInput("第二个事实", { id: "same-id" }))).toBeNull();
    expect(repository.list({ includeDeleted: true })).toMatchObject([
      { id: "same-id", content: "第一个事实", status: "active" },
    ]);
  });

  test("turns explicit remember language into a confirmed, low-risk candidate", () => {
    const candidate = extractCompanionMemoryCandidate(
      "请记住我喜欢桂花茶。",
      "message-1",
      "xiaoju-cat",
    );

    expect(candidate).toMatchObject({
      scope: "global",
      type: "preference",
      content: "用户喜欢桂花茶",
      source: "explicit",
      evidence: "请记住我喜欢桂花茶。",
      sourceMessageId: "message-1",
      confirmed: true,
      requiresConfirmation: false,
    });
  });

  test("keeps nickname expressions out of ordinary Memory", () => {
    expect(
      extractCompanionMemoryCandidate("以后叫我阿星。", "message-nickname", "xiaoju-cat"),
    ).toBeNull();
    expect(
      extractCompanionMemoryCandidate("我喜欢桂花茶，请记住。", "message-tea", "xiaoju-cat"),
    ).toMatchObject({
      content: "用户喜欢桂花茶",
      type: "preference",
      scope: "global",
    });
  });

  test("does not persist an unconfirmed candidate", () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const candidate = {
      scope: "global" as const,
      type: "fact" as const,
      category: "goal" as const,
      lifetime: "stable" as const,
      content: "用户可能喜欢夜跑",
      source: "inferred" as const,
      evidence: "用户说也许会去夜跑",
      sourceMessageId: "message-inferred",
      confidence: 0.55,
      importance: 0.5,
      explicitness: "inferred" as const,
      confirmationStatus: "requires_confirmation" as const,
      expiresAt: null,
      requiresConfirmation: true,
      confirmationReason: "表达不确定，需要用户确认。",
      confirmed: false,
    };

    expect(saveCompanionMemoryCandidate(repository, candidate)).toBeNull();
    expect(repository.list()).toEqual([]);
  });

  test("persists an inferred candidate only after explicit confirmation", () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const candidate = {
      scope: "pet:xiaoju-cat" as const,
      type: "relationship" as const,
      category: "shared_experience" as const,
      lifetime: "stable" as const,
      content: "我们一起看过雨",
      source: "inferred" as const,
      evidence: "你提到和小橘一起看过雨",
      sourceMessageId: "message-confirmed",
      confidence: 0.72,
      importance: 0.7,
      explicitness: "inferred" as const,
      confirmationStatus: "requires_confirmation" as const,
      expiresAt: null,
      requiresConfirmation: true,
      confirmationReason: "这是从表达中推断的关系，需要用户确认。",
      confirmed: false,
    };

    const confirmed = confirmCompanionMemoryCandidate(candidate);
    expect(saveCompanionMemoryCandidate(repository, confirmed)).toMatchObject({
      source: "confirmed",
      scope: "pet:xiaoju-cat",
    });
  });

  test("rejects sensitive memory at both extraction and repository boundaries", () => {
    expect(
      extractCompanionMemoryCandidate(
        "请记住我的密码是 abc123",
        "message-sensitive",
        "xiaoju-cat",
      ),
    ).toBeNull();

    const repository = createCompanionMemoryRepository({ now: () => NOW });
    expect(repository.save(memoryInput("用户的银行卡是 1234"))).toBeNull();
    expect(
      extractCompanionMemoryCandidate(
        "我通常吃二甲双胍，请记住。",
        "message-medication",
        "xiaoju-cat",
      ),
    ).toBeNull();
    expect(repository.list()).toEqual([]);
  });

  test("does not place sensitive Memory content or raw evidence in the outbox", () => {
    const store = createStorage();
    const repository = createCompanionMemoryRepository({ storage: store, now: () => NOW });
    expect(repository.save(memoryInput("用户喜欢纸质书", {
      id: "safe-memory",
      evidence: "用户明确说喜欢纸质书",
    }))).not.toBeNull();
    expect(repository.save(memoryInput("用户的密码是 secret-123", {
      id: "sensitive-memory",
    }))).toBeNull();

    const outbox = JSON.parse(
      store.getItem(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY) ?? "[]",
    ) as Array<Record<string, unknown>>;
    const serialized = JSON.stringify(outbox);
    expect(serialized).toContain("用户喜欢纸质书");
    expect(serialized).not.toContain("用户明确说喜欢纸质书");
    expect(serialized).not.toContain("secret-123");
  });

  test("supports disable, delete, and JSON/Markdown export", () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const saved = repository.save(memoryInput("用户喜欢纸质书", { id: "book" }));
    expect(saved).not.toBeNull();
    expect(repository.disable("book")?.status).toBe("disabled");
    expect(repository.update("book", { status: "active", content: "用户喜欢旧书" })?.content).toBe(
      "用户喜欢旧书",
    );
    expect(repository.delete("book")?.status).toBe("deleted");
    expect(repository.list()).toEqual([]);
    expect(repository.list({ includeDeleted: true })[0]?.status).toBe("deleted");
    expect(repository.export("json")).toContain('"entries"');
    expect(repository.export("markdown")).toContain("# 愈心桌宠已保存 Memory");
  });

  test("redacts deleted Memory content and evidence from local tombstones and outbox", () => {
    const store = createStorage();
    const repository = createCompanionMemoryRepository({ storage: store, now: () => NOW });
    expect(repository.save(memoryInput("用户喜欢桂花茶", {
      id: "tea",
      evidence: "请记住我喜欢桂花茶。",
    }))).not.toBeNull();

    const deleted = repository.delete("tea");
    expect(deleted).toMatchObject({
      id: "tea",
      status: "deleted",
      content: "（已删除）",
      evidence: "（已删除）",
      sourceMessageId: "deleted:tea",
    });
    const serialized = JSON.stringify(store.getItem(COMPANION_MEMORY_STORAGE_KEY));
    const outbox = JSON.parse(
      store.getItem(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY) ?? "[]",
    ) as Array<Record<string, unknown>>;
    expect(serialized).not.toContain("用户喜欢桂花茶");
    expect(serialized).not.toContain("请记住我喜欢桂花茶");
    const deleteEvent = outbox.find(
      (event) => event.operation === "delete" && event.entityId === "tea",
    );
    expect(deleteEvent).toMatchObject({ payload: { id: "tea" } });
    expect(JSON.stringify(deleteEvent)).not.toContain("请记住我喜欢桂花茶");
    expect(repository.search("桂花茶", { petId: "xiaoju-cat" })).toEqual([]);
  });

  test("keeps a deleted Memory deleted when the repository fails at a write boundary and restarts", () => {
    const store = createStorage();
    const repository = createCompanionMemoryRepository({ storage: store, now: () => NOW });
    expect(repository.save(memoryInput("用户喜欢桂花茶", { id: "restart-delete" }))).not.toBeNull();

    store.failOnceKeys.add(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY);
    expect(repository.delete("restart-delete")).toBeNull();

    const restarted = createCompanionMemoryRepository({ storage: store, now: () => NOW });
    expect(restarted.get("restart-delete")).toMatchObject({ status: "deleted", content: "（已删除）" });
    expect(restarted.list()).toEqual([]);
    expect(restarted.search("桂花茶", { petId: "xiaoju-cat" })).toEqual([]);
  });

  test("uses the durable delete guard even when the journal is damaged", () => {
    const store = createStorage();
    const repository = createCompanionMemoryRepository({ storage: store, now: () => NOW });
    expect(repository.save(memoryInput("用户喜欢纸质书", { id: "damaged-journal-delete" }))).not.toBeNull();

    store.failOnceKeys.add(COMPANION_MEMORY_STORAGE_KEY);
    expect(repository.delete("damaged-journal-delete")).toBeNull();
    store.values.set(LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY, "not-json");

    const restarted = createCompanionMemoryRepository({ storage: store, now: () => NOW });
    expect(restarted.list()).toEqual([]);
    expect(restarted.search("纸质书", { petId: "xiaoju-cat" })).toEqual([]);
  });

  test("fails open when a provider-specific memory search throws", () => {
    const repository = {
      search: () => {
        throw new Error("storage unavailable");
      },
    } as unknown as MemoryRepository;

    expect(
      searchCompanionMemorySafely(repository, "猫", { petId: "xiaoju-cat" }, vi.fn()),
    ).toEqual([]);
  });
});
