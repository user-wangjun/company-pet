import { describe, expect, test, vi } from "vitest";
import {
  COMPANION_MEMORY_STORAGE_KEY,
  createCompanionMemoryRepository,
  extractCompanionMemoryCandidate,
  type MemoryRepository,
} from "./companionMemory";
import {
  authorizeCompanionMemoryCandidate,
  CompanionMemoryPolicy,
  getCompanionMemoryCandidateId,
  getCompanionMemoryRevisionId,
  normalizeCompanionMemoryComparisonText,
} from "./companionMemoryPolicy";
import type {
  CompanionInput,
  CompanionMemoryConfirmationVerifier,
  MemoryCandidate,
} from "./companionHarnessTypes";
import {
  LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY,
  LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY,
  LOCAL_REPOSITORY_SYNC_VERSION_KEY,
} from "../storage/localRepository";

const NOW = Date.parse("2026-08-12T12:00:00.000Z");

function createStorage() {
  const values = new Map<string, string>();
  const failOnceKeys = new Set<string>();
  return {
    values,
    failOnceKeys,
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      if (failOnceKeys.delete(key)) throw new Error(`write failed: ${key}`);
      values.set(key, value);
    }),
  };
}

function input(overrides: Partial<CompanionInput> = {}): CompanionInput {
  return {
    requestId: "request-1",
    sessionId: "session-1",
    sourceMessageId: "message-1",
    userId: "local-user",
    petId: "xiaoju-cat",
    message: "普通聊天",
    currentTime: new Date(NOW).toISOString(),
    timezone: "UTC",
    utcOffsetMinutes: 0,
    source: "chat",
    ...overrides,
  };
}

function candidate(overrides: Partial<MemoryCandidate> = {}): MemoryCandidate {
  return {
    scope: "global",
    type: "preference",
    category: "preference",
    lifetime: "stable",
    content: "用户喜欢桂花茶",
    source: "inferred",
    evidence: "模型提出的候选证据",
    sourceMessageId: "message-1",
    confidence: 1,
    importance: 1,
    explicitness: "inferred",
    confirmationStatus: "requires_confirmation",
    expiresAt: null,
    requiresConfirmation: true,
    confirmed: false,
    ...overrides,
  };
}

function explicitCandidate(
  overrides: Partial<MemoryCandidate> = {},
): MemoryCandidate {
  return candidate({
    source: "explicit",
    explicitness: "explicit",
    confirmationStatus: "not_required",
    requiresConfirmation: false,
    confirmed: true,
    ...overrides,
  });
}

function confirmedCandidate(
  overrides: Partial<MemoryCandidate> = {},
): MemoryCandidate {
  return candidate({
    source: "confirmed",
    confirmationStatus: "confirmed",
    requiresConfirmation: false,
    confirmed: true,
    ...overrides,
  });
}

function outbox(storage: ReturnType<typeof createStorage>): Array<Record<string, unknown>> {
  return JSON.parse(storage.values.get(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY) ?? "[]") as Array<Record<string, unknown>>;
}

function proofVerifier(): CompanionMemoryConfirmationVerifier {
  return {
    verify: (nextInput, nextCandidate, candidateId) => ({
      candidateId,
      sourceMessageId: nextCandidate.sourceMessageId,
      confirmationMessageId: nextInput.sourceMessageId,
      sessionId: nextInput.sessionId,
      petId: nextInput.petId,
      status: "confirmed",
    }),
  };
}

describe("Companion MemoryPolicy", () => {
  test("does not persist an inferred high-confidence candidate from ordinary emotion", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const result = await new CompanionMemoryPolicy({ repository, now: () => NOW }).process(
      input({ message: "我今天好累" }),
      [candidate({ content: "用户是一个永远积极的人" })],
      new AbortController().signal,
    );

    expect(result).toMatchObject({
      status: "ignored",
      acceptedCount: 0,
      rejectedCount: 1,
      decisions: [{ status: "confirmation_required", errorCode: "explicit-proof-missing" }],
    });
    expect(repository.list()).toEqual([]);
  });

  test("requires local explicit evidence and ignores model-fabricated authority fields", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const nextInput = input({
      message: "我今天好累",
      sourceMessageId: "message-emotion",
    });
    const result = await new CompanionMemoryPolicy({ repository, now: () => NOW }).process(
      nextInput,
      [explicitCandidate({ sourceMessageId: nextInput.sourceMessageId })],
      new AbortController().signal,
    );

    expect(result.decisions[0]).toMatchObject({
      status: "confirmation_required",
      errorCode: "explicit-proof-missing",
    });
    expect(repository.list()).toEqual([]);
  });

  test("saves the deterministic local explicit memory with global preference mapping", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const nextInput = input({
      message: "我喜欢桂花茶，请记住",
      sourceMessageId: "message-tea",
    });
    const local = extractCompanionMemoryCandidate(
      nextInput.message,
      nextInput.sourceMessageId,
      nextInput.petId,
    );
    expect(local).not.toBeNull();

    const result = await new CompanionMemoryPolicy({ repository, now: () => NOW }).process(
      nextInput,
      [local!],
      new AbortController().signal,
    );

    expect(result).toMatchObject({
      status: "succeeded",
      acceptedCount: 1,
      decisions: [{ status: "inserted", scope: "global", type: "preference" }],
    });
    expect(repository.list()).toMatchObject([{
      scope: "global",
      type: "preference",
      source: "explicit",
      content: "用户喜欢桂花茶",
      evidence: "我喜欢桂花茶，请记住",
      expiresAt: null,
      status: "active",
    }]);
  });

  test("deduplicates exact and conservative near-duplicate content without a new Outbox event", async () => {
    const storage = createStorage();
    const repository = createCompanionMemoryRepository({ storage, now: () => NOW });
    const policy = new CompanionMemoryPolicy({ repository, now: () => NOW });
    const firstInput = input({
      message: "我喜欢桂花茶，请记住",
      sourceMessageId: "message-first",
    });
    const first = extractCompanionMemoryCandidate(firstInput.message, firstInput.sourceMessageId, firstInput.petId)!;
    expect((await policy.process(firstInput, [first], new AbortController().signal)).acceptedCount).toBe(1);
    const countAfterFirst = outbox(storage).length;

    const retryInput = input({
      message: "我喜欢桂花茶，请记住。",
      sourceMessageId: "message-retry",
    });
    const retry = extractCompanionMemoryCandidate(retryInput.message, retryInput.sourceMessageId, retryInput.petId)!;
    const retryResult = await policy.process(retryInput, [retry], new AbortController().signal);
    expect(retryResult.decisions).toEqual([
      expect.objectContaining({ status: "duplicate", resourceId: expect.any(String) }),
    ]);
    expect(repository.list()).toHaveLength(1);
    expect(outbox(storage)).toHaveLength(countAfterFirst);

    const equivalent = await policy.process(
      input({
        message: "我喜欢桂花茶，请记住",
        sourceMessageId: "message-equivalent",
      }),
      [explicitCandidate({
        sourceMessageId: "message-equivalent",
        content: "用户 喜欢 桂花茶！",
        evidence: "本地明确证据",
        explicitness: "explicit",
        confirmationStatus: "not_required",
        requiresConfirmation: false,
        confirmed: true,
      })],
      new AbortController().signal,
    );
    expect(equivalent.decisions[0]?.status).toBe("duplicate");
    expect(repository.list()).toHaveLength(1);
    expect(normalizeCompanionMemoryComparisonText("用户喜欢桂花茶！")).toBe(
      normalizeCompanionMemoryComparisonText("用户 喜欢 桂花茶"),
    );
  });

  test("treats equivalent preference verbs as one same-polarity fact", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const policy = new CompanionMemoryPolicy({ repository, now: () => NOW });
    const firstInput = input({
      message: "请记住我喜欢咖啡",
      sourceMessageId: "message-like-coffee",
    });
    const first = extractCompanionMemoryCandidate(firstInput.message, firstInput.sourceMessageId, firstInput.petId)!;
    expect((await policy.process(firstInput, [first], new AbortController().signal)).decisions[0]?.status).toBe("inserted");

    const equivalentInput = input({
      message: "我爱喝咖啡，请记住",
      sourceMessageId: "message-drink-coffee",
    });
    const equivalent = extractCompanionMemoryCandidate(
      equivalentInput.message,
      equivalentInput.sourceMessageId,
      equivalentInput.petId,
    )!;
    const result = await policy.process(equivalentInput, [equivalent], new AbortController().signal);

    expect(result.decisions[0]).toMatchObject({ status: "duplicate" });
    expect(repository.list()).toHaveLength(1);
  });

  test.each([
    ["请记住我不喜欢香菜", "我喜欢香菜，请记住"],
    ["请记住我不喝咖啡", "我爱喝咖啡，请记住"],
  ])("supersedes an explicit opposite preference for the same object: %s -> %s", async (oldMessage, newMessage) => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const policy = new CompanionMemoryPolicy({ repository, now: () => NOW });
    const oldInput = input({ message: oldMessage, sourceMessageId: "message-preference-old" });
    const old = extractCompanionMemoryCandidate(oldMessage, oldInput.sourceMessageId, oldInput.petId)!;
    expect((await policy.process(oldInput, [old], new AbortController().signal)).decisions[0]?.status).toBe("inserted");

    const newInput = input({ message: newMessage, sourceMessageId: "message-preference-new" });
    const next = extractCompanionMemoryCandidate(newMessage, newInput.sourceMessageId, newInput.petId)!;
    const result = await policy.process(newInput, [next], new AbortController().signal);

    expect(result.decisions[0]).toMatchObject({ status: "superseded" });
    expect(repository.list().filter((entry) => entry.status === "active")).toMatchObject([
      { content: next.content, status: "active" },
    ]);
    expect(repository.list().filter((entry) => entry.status === "active")).toHaveLength(1);
  });

  test("supersedes a corrected profile name while keeping unrelated facts separate", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const policy = new CompanionMemoryPolicy({ repository, now: () => NOW });
    const oldInput = input({ message: "请记住我叫小明", sourceMessageId: "message-name-old" });
    const old = extractCompanionMemoryCandidate(oldInput.message, oldInput.sourceMessageId, oldInput.petId)!;
    await policy.process(oldInput, [old], new AbortController().signal);

    const newInput = input({ message: "我叫小红，请记住", sourceMessageId: "message-name-new" });
    const next = extractCompanionMemoryCandidate(newInput.message, newInput.sourceMessageId, newInput.petId)!;
    const result = await policy.process(newInput, [next], new AbortController().signal);

    expect(result.decisions[0]).toMatchObject({ status: "superseded" });
    expect(repository.list().filter((entry) => entry.status === "active")).toMatchObject([
      { content: "用户我叫小红", type: "fact" },
    ]);
    expect(repository.list().filter((entry) => entry.status === "active")).toHaveLength(1);

    const unrelated = new CompanionMemoryPolicy({
      repository,
      now: () => NOW,
      confirmationVerifier: proofVerifier(),
    });
    const projectInput = input({ sourceMessageId: "confirmation-project", message: "确认" });
    const projectResult = await unrelated.process(projectInput, [confirmedCandidate({
      sourceMessageId: "candidate-project",
      category: "project",
      type: "fact",
      content: "项目甲",
    })], new AbortController().signal);
    expect(projectResult.decisions[0]?.status).toBe("inserted");
    expect(repository.list().filter((entry) => entry.status === "active")).toHaveLength(2);
  });

  test("does not conflict across different preference objects, people, projects, or shared experiences", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const policy = new CompanionMemoryPolicy({
      repository,
      now: () => NOW,
      confirmationVerifier: proofVerifier(),
    });
    const cases = [
      { category: "preference" as const, type: "preference" as const, scope: "global" as const, content: "用户喜欢咖啡" },
      { category: "preference" as const, type: "preference" as const, scope: "global" as const, content: "用户喜欢茶" },
      { category: "preference" as const, type: "preference" as const, scope: "global" as const, content: "用户不喜欢香菜" },
      { category: "preference" as const, type: "preference" as const, scope: "global" as const, content: "用户喜欢芹菜" },
      { category: "person" as const, type: "fact" as const, scope: "global" as const, content: "用户的朋友小明" },
      { category: "person" as const, type: "fact" as const, scope: "global" as const, content: "用户的朋友小红" },
      { category: "project" as const, type: "fact" as const, scope: "global" as const, content: "项目甲" },
      { category: "project" as const, type: "fact" as const, scope: "global" as const, content: "项目乙" },
      { category: "shared_experience" as const, type: "relationship" as const, scope: "pet:xiaoju-cat" as const, content: "我们一起看雨" },
      { category: "shared_experience" as const, type: "relationship" as const, scope: "pet:xiaoju-cat" as const, content: "我们一起看雪" },
    ];
    for (const [index, item] of cases.entries()) {
      const nextInput = input({ sourceMessageId: `confirmation-unrelated-${index}`, message: "确认" });
      const result = await policy.process(nextInput, [confirmedCandidate({
        sourceMessageId: `candidate-unrelated-${index}`,
        ...item,
      })], new AbortController().signal);
      expect(result.decisions[0]?.status, item.content).toBe("inserted");
    }
    expect(repository.list().filter((entry) => entry.status === "active")).toHaveLength(cases.length);
  });

  test("trusted confirmation can supersede a conflicting preference", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const policy = new CompanionMemoryPolicy({ repository, now: () => NOW });
    const oldInput = input({ message: "请记住我不喜欢香菜", sourceMessageId: "message-confirm-old" });
    const old = extractCompanionMemoryCandidate(oldInput.message, oldInput.sourceMessageId, oldInput.petId)!;
    await policy.process(oldInput, [old], new AbortController().signal);

    const confirmationInput = input({ sourceMessageId: "message-confirm-new", message: "确认这条" });
    const result = await new CompanionMemoryPolicy({
      repository,
      now: () => NOW,
      confirmationVerifier: proofVerifier(),
    }).process(confirmationInput, [confirmedCandidate({
      sourceMessageId: "candidate-confirm-new",
      content: "用户喜欢香菜",
      category: "preference",
      type: "preference",
    })], new AbortController().signal);

    expect(result.decisions[0]).toMatchObject({ status: "superseded" });
    expect(repository.list().filter((entry) => entry.status === "active")).toMatchObject([
      { content: "用户喜欢香菜" },
    ]);
  });

  test("uses separate candidate and revision identities for A -> B -> A", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const policy = new CompanionMemoryPolicy({ repository, now: () => NOW });
    const messages = [
      "请记住我不喜欢香菜",
      "我喜欢香菜，请记住",
      "我不喜欢香菜，请记住",
    ];
    const candidates: MemoryCandidate[] = [];
    const results = [];
    for (const [index, message] of messages.entries()) {
      const nextInput = input({ message, sourceMessageId: `message-revision-${index}` });
      const next = extractCompanionMemoryCandidate(message, nextInput.sourceMessageId, nextInput.petId)!;
      candidates.push(next);
      results.push(await policy.process(nextInput, [next], new AbortController().signal));
    }

    expect(results.map((result) => result.decisions[0]?.status)).toEqual([
      "inserted",
      "superseded",
      "superseded",
    ]);
    expect(getCompanionMemoryCandidateId(candidates[0])).toBe(getCompanionMemoryCandidateId(candidates[2]));
    expect(getCompanionMemoryRevisionId(candidates[0])).not.toBe(getCompanionMemoryRevisionId(candidates[0], "revision-parent"));
    const entries = repository.list({ includeDeleted: true });
    const active = entries.filter((entry) => entry.status === "active");
    expect(active).toHaveLength(1);
    expect(active[0]).toMatchObject({
      content: "用户不喜欢香菜",
      supersedesId: entries.find((entry) => entry.content === "用户喜欢香菜")?.id,
    });
    expect(new Set(entries.map((entry) => entry.id)).size).toBe(3);
    expect(entries.filter((entry) => entry.status === "superseded")).toHaveLength(2);
  });

  test("keeps the 200-entry boundary failed and leaves the old fact and Outbox unchanged", async () => {
    const storage = createStorage();
    const repository = createCompanionMemoryRepository({ storage, now: () => NOW });
    for (let index = 0; index < 199; index += 1) {
      expect(repository.save({
        id: `policy-filler-${index}`,
        scope: "global",
        type: "fact",
        content: `策略填充-${index}`,
        source: "explicit",
        evidence: "本地测试",
        sourceMessageId: `policy-filler-message-${index}`,
        confidence: 0.5,
        expiresAt: null,
        status: "active",
        supersedesId: null,
      })).not.toBeNull();
    }

    const oldInput = input({ message: "请记住我不喝咖啡", sourceMessageId: "policy-boundary-old" });
    const old = extractCompanionMemoryCandidate(oldInput.message, oldInput.sourceMessageId, oldInput.petId)!;
    const policy = new CompanionMemoryPolicy({ repository, now: () => NOW });
    expect((await policy.process(oldInput, [old], new AbortController().signal)).decisions[0]?.status).toBe("inserted");
    expect(repository.list({ includeDeleted: true })).toHaveLength(200);
    const oldEntry = repository.list().find((entry) => entry.content === "用户不喝咖啡")!;

    const keys = [
      COMPANION_MEMORY_STORAGE_KEY,
      LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY,
      LOCAL_REPOSITORY_JOURNAL_STORAGE_KEY,
      LOCAL_REPOSITORY_SYNC_VERSION_KEY,
    ];
    const before = new Map(keys.map((key) => [key, storage.values.get(key)]));
    const nextInput = input({ message: "我爱喝咖啡，请记住", sourceMessageId: "policy-boundary-new" });
    const next = extractCompanionMemoryCandidate(nextInput.message, nextInput.sourceMessageId, nextInput.petId)!;
    const result = await policy.process(nextInput, [next], new AbortController().signal);

    expect(result).toMatchObject({ status: "failed", errorCode: "memory-supersede-failed" });
    expect(repository.list({ includeDeleted: true })).toHaveLength(200);
    expect(repository.get(oldEntry.id)).toMatchObject({ status: "active", content: "用户不喝咖啡" });
    for (const key of keys) expect(storage.values.get(key)).toBe(before.get(key));
    const restarted = createCompanionMemoryRepository({ storage, now: () => NOW });
    expect(restarted.list({ includeDeleted: true })).toHaveLength(200);
    expect(restarted.get(oldEntry.id)).toMatchObject({ status: "active", content: "用户不喝咖啡" });
  });

  test("uses collision-safe identities for the known 32-bit collision pair", () => {
    const first = candidate({
      scope: "global",
      type: "fact",
      category: "profile",
      content: "用户我叫i6adqy1cr8o0r",
      sourceMessageId: "collision-first",
    });
    const second = candidate({
      scope: "global",
      type: "fact",
      category: "profile",
      content: "用户我叫1jpie37tfrvh",
      sourceMessageId: "collision-second",
    });
    const firstId = getCompanionMemoryCandidateId(first);
    const secondId = getCompanionMemoryCandidateId(second);
    expect(firstId).toMatch(/^memory-candidate-(?:[0-9a-f]{8}-){7}[0-9a-f]{8}$/u);
    expect(secondId).toMatch(/^memory-candidate-(?:[0-9a-f]{8}-){7}[0-9a-f]{8}$/u);
    expect(firstId).not.toBe(secondId);

    const repository = createCompanionMemoryRepository({ now: () => NOW });
    expect(repository.save({
      id: firstId,
      scope: first.scope,
      type: first.type,
      content: first.content,
      source: "explicit",
      evidence: "本地测试",
      sourceMessageId: first.sourceMessageId,
      confidence: 1,
      expiresAt: null,
      status: "active",
      supersedesId: null,
    })).not.toBeNull();
    expect(repository.save({
      id: secondId,
      scope: second.scope,
      type: second.type,
      content: second.content,
      source: "explicit",
      evidence: "本地测试",
      sourceMessageId: second.sourceMessageId,
      confidence: 1,
      expiresAt: null,
      status: "active",
      supersedesId: null,
    })).not.toBeNull();
    expect(repository.list()).toMatchObject([
      expect.objectContaining({ id: firstId, content: first.content }),
      expect.objectContaining({ id: secondId, content: second.content }),
    ]);
  });

  test("maps shared experience to a current-pet relationship and rejects another pet scope", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const nextInput = input({
      message: "请记住我们周五一起复盘",
      sourceMessageId: "message-relationship",
    });
    const local = extractCompanionMemoryCandidate(nextInput.message, nextInput.sourceMessageId, nextInput.petId)!;
    const saved = await new CompanionMemoryPolicy({ repository, now: () => NOW }).process(
      nextInput,
      [local],
      new AbortController().signal,
    );
    expect(saved.decisions[0]).toMatchObject({
      status: "inserted",
      scope: "pet:xiaoju-cat",
      type: "relationship",
    });

    const otherPet = await new CompanionMemoryPolicy({ repository, now: () => NOW }).process(
      input({ sourceMessageId: "message-other" }),
      [confirmedCandidate({
        sourceMessageId: "message-other",
        scope: "pet:other-cat",
        category: "shared_experience",
        type: "relationship",
      })],
      new AbortController().signal,
    );
    expect(otherPet.decisions[0]).toMatchObject({ status: "rejected", errorCode: "invalid-candidate" });
    expect(repository.search("复盘", { petId: "other-cat" })).toEqual([]);
  });

  test("maps every stable candidate category to the existing persistence type", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const policy = new CompanionMemoryPolicy({
      repository,
      now: () => NOW,
      confirmationVerifier: proofVerifier(),
    });
    const mappings = [
      ["profile", "fact"],
      ["person", "fact"],
      ["project", "fact"],
      ["goal", "fact"],
      ["event", "episode"],
      ["preference", "preference"],
      ["shared_experience", "relationship"],
    ] as const;
    for (const [category, type] of mappings) {
      const nextInput = input({
        sourceMessageId: `confirmation-${category}`,
        message: "确认这条",
      });
      const saved = await policy.process(
        nextInput,
        [confirmedCandidate({
          sourceMessageId: `candidate-${category}`,
          content: `候选-${category}`,
          category,
          type,
          scope: category === "shared_experience" ? "pet:xiaoju-cat" : "global",
        })],
        new AbortController().signal,
      );
      expect(saved.decisions[0]).toMatchObject({ status: "inserted", type });
    }
    expect(repository.list()).toHaveLength(mappings.length);
  });

  test("accepts future temporal Memory and rejects past, equal, missing, or invalid expiration", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const policy = new CompanionMemoryPolicy({
      repository,
      now: () => NOW,
      confirmationVerifier: proofVerifier(),
    });
    const expiresAt = new Date(NOW + 60_000).toISOString();
    const future = await policy.process(
      input({ sourceMessageId: "confirmation-future", message: "确认" }),
      [confirmedCandidate({
        sourceMessageId: "candidate-future",
        content: "本周准备考试",
        category: "goal",
        type: "fact",
        lifetime: "temporal",
        expiresAt,
      })],
      new AbortController().signal,
    );
    expect(future.decisions[0]).toMatchObject({ status: "inserted" });
    expect(repository.list()[0]?.expiresAt).toBe(expiresAt);

    for (const [suffix, expiration] of [
      ["past", new Date(NOW - 1).toISOString()],
      ["equal", new Date(NOW).toISOString()],
      ["missing", null],
      ["invalid", "not-a-date"],
    ] as const) {
      const result = await policy.process(
        input({ sourceMessageId: `confirmation-${suffix}`, message: "确认" }),
        [confirmedCandidate({
          sourceMessageId: `candidate-${suffix}`,
          content: `临时-${suffix}`,
          category: "goal",
          type: "fact",
          lifetime: "temporal",
          expiresAt: expiration,
        })],
        new AbortController().signal,
      );
      expect(["expired", "rejected"]).toContain(result.decisions[0]?.status);
    }
    expect(repository.list()).toHaveLength(1);
  });

  test("sensitive content, evidence, and source ids are rejected without echoing raw text", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const sensitive = [
      candidate({ content: "用户的密码是 NEVER_STORE" }),
      candidate({ evidence: "用户的银行卡号是 1234567890123456" }),
      candidate({ sourceMessageId: "message-with-token-sk-proj-12345678901234567890" }),
    ];
    const result = await new CompanionMemoryPolicy({ repository, now: () => NOW }).process(
      input(),
      sensitive,
      new AbortController().signal,
    );

    expect(result.decisions.every((item) => item.status === "rejected")).toBe(true);
    expect(JSON.stringify(result)).not.toContain("NEVER_STORE");
    expect(JSON.stringify(result)).not.toContain("1234567890123456");
    expect(JSON.stringify(result)).not.toContain("sk-proj");
    expect(repository.list()).toEqual([]);
  });

  test("requires a local confirmation proof and binds it to session, pet, source, and confirmation message", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const pending = confirmedCandidate({
      sourceMessageId: "original-candidate-message",
      content: "用户不吃香菜",
      category: "preference",
      type: "preference",
    });
    const confirmationInput = input({
      sourceMessageId: "confirmation-message",
      message: "确认记住",
    });
    const noProof = await new CompanionMemoryPolicy({ repository, now: () => NOW }).process(
      confirmationInput,
      [pending],
      new AbortController().signal,
    );
    expect(noProof.decisions[0]).toMatchObject({
      status: "confirmation_required",
      errorCode: "confirmation-proof-missing",
    });
    expect(repository.list()).toEqual([]);

    const verifier = proofVerifier();
    const withProof = await new CompanionMemoryPolicy({
      repository,
      now: () => NOW,
      confirmationVerifier: verifier,
    }).process(confirmationInput, [pending], new AbortController().signal);
    expect(withProof.decisions[0]).toMatchObject({ status: "inserted" });

    const badVerifier: CompanionMemoryConfirmationVerifier = {
      verify: () => ({
        candidateId: "wrong-candidate",
        sourceMessageId: pending.sourceMessageId,
        confirmationMessageId: confirmationInput.sourceMessageId,
        sessionId: confirmationInput.sessionId,
        petId: confirmationInput.petId,
        status: "confirmed",
      }),
    };
    const bad = await authorizeCompanionMemoryCandidate({
      input: confirmationInput,
      candidate: pending,
      index: 0,
      repository,
      now: NOW,
      signal: new AbortController().signal,
      confirmationVerifier: badVerifier,
    });
    expect(bad).toEqual({ status: "confirmation_required", errorCode: "confirmation-proof-missing" });
    expect(getCompanionMemoryCandidateId(pending)).not.toContain(pending.content);
  });

  test("only explicit correction or trusted confirmation can atomically supersede a conflicting fact", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const initialInput = input({
      message: "请记住我不喜欢香菜",
      sourceMessageId: "message-old",
    });
    const old = extractCompanionMemoryCandidate(initialInput.message, initialInput.sourceMessageId, initialInput.petId)!;
    await new CompanionMemoryPolicy({ repository, now: () => NOW }).process(
      initialInput,
      [old],
      new AbortController().signal,
    );

    const inferred = await new CompanionMemoryPolicy({ repository, now: () => NOW }).process(
      input({ message: "我喜欢香菜", sourceMessageId: "message-inferred" }),
      [candidate({
        sourceMessageId: "message-inferred",
        content: "用户喜欢香菜",
        source: "inferred",
        explicitness: "inferred",
      })],
      new AbortController().signal,
    );
    expect(inferred.decisions[0]?.status).toBe("confirmation_required");
    expect(repository.list().find((entry) => entry.status === "active")?.content).toBe("用户不喜欢香菜");

    const correctionInput = input({
      message: "我喜欢香菜，请记住",
      sourceMessageId: "message-new",
    });
    const correction = extractCompanionMemoryCandidate(correctionInput.message, correctionInput.sourceMessageId, correctionInput.petId)!;
    const result = await new CompanionMemoryPolicy({ repository, now: () => NOW }).process(
      correctionInput,
      [correction],
      new AbortController().signal,
    );
    const entries = repository.list({ includeDeleted: true });
    const active = entries.find((entry) => entry.status === "active");
    const superseded = entries.find((entry) => entry.status === "superseded");
    expect(result.decisions[0]).toMatchObject({
      status: "superseded",
      supersedesId: superseded?.id,
    });
    expect(active).toMatchObject({
      content: "用户喜欢香菜",
      status: "active",
      supersedesId: superseded?.id,
    });
    expect(repository.search("香菜", { petId: "xiaoju-cat" })).toEqual([
      expect.objectContaining({ id: active?.id, status: "active" }),
    ]);
  });

  test("keeps the old fact active when atomic supersede persistence fails", async () => {
    const storage = createStorage();
    const repository = createCompanionMemoryRepository({ storage, now: () => NOW });
    const oldInput = input({
      message: "请记住我不喜欢香菜",
      sourceMessageId: "message-old-failure",
    });
    const old = extractCompanionMemoryCandidate(oldInput.message, oldInput.sourceMessageId, oldInput.petId)!;
    await new CompanionMemoryPolicy({ repository, now: () => NOW }).process(
      oldInput,
      [old],
      new AbortController().signal,
    );
    storage.failOnceKeys.add(LOCAL_REPOSITORY_OUTBOX_STORAGE_KEY);

    const replacementInput = input({
      message: "我喜欢香菜，请记住",
      sourceMessageId: "message-new-failure",
    });
    const replacement = extractCompanionMemoryCandidate(replacementInput.message, replacementInput.sourceMessageId, replacementInput.petId)!;
    const result = await new CompanionMemoryPolicy({ repository, now: () => NOW }).process(
      replacementInput,
      [replacement],
      new AbortController().signal,
    );
    expect(result).toMatchObject({ status: "failed", errorCode: "memory-supersede-failed" });
    expect(repository.list({ includeDeleted: true })).toHaveLength(1);
    expect(repository.list()[0]).toMatchObject({ content: "用户不喜欢香菜", status: "active" });
  });

  test("does not revive a deleted Tombstone on a retry", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const nextInput = input({
      message: "我喜欢桂花茶，请记住",
      sourceMessageId: "message-delete",
    });
    const local = extractCompanionMemoryCandidate(nextInput.message, nextInput.sourceMessageId, nextInput.petId)!;
    const policy = new CompanionMemoryPolicy({ repository, now: () => NOW });
    await policy.process(nextInput, [local], new AbortController().signal);
    const saved = repository.list()[0]!;
    expect(repository.delete(saved.id)).not.toBeNull();

    const retry = await policy.process(nextInput, [local], new AbortController().signal);
    expect(retry).toMatchObject({ status: "failed", errorCode: "memory-save-failed" });
    expect(repository.get(saved.id)).toMatchObject({ status: "deleted", content: "（已删除）" });
    expect(repository.search("桂花茶", { petId: "xiaoju-cat" })).toEqual([]);
  });

  test("checks cancellation before the write and keeps a write-confirmed result on late abort", async () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const policy = new CompanionMemoryPolicy({
      repository,
      now: () => NOW,
      confirmationVerifier: proofVerifier(),
    });
    const before = new AbortController();
    before.abort();
    const beforeResult = await policy.process(
      input({ sourceMessageId: "confirmation-before" }),
      [confirmedCandidate({ sourceMessageId: "candidate-before" })],
      before.signal,
    );
    expect(beforeResult.decisions[0]).toMatchObject({ status: "cancelled" });
    expect(repository.list()).toEqual([]);

    const late = new AbortController();
    const lateRepository: MemoryRepository = {
      ...repository,
      save(entry) {
        const saved = repository.save(entry);
        late.abort();
        return saved;
      },
    };
    const lateResult = await new CompanionMemoryPolicy({
      repository: lateRepository,
      now: () => NOW,
      confirmationVerifier: proofVerifier(),
    }).process(
      input({ sourceMessageId: "confirmation-late" }),
      [confirmedCandidate({ sourceMessageId: "candidate-late", content: "用户喜欢桂花茶" })],
      late.signal,
    );
    expect(lateResult).toMatchObject({ status: "succeeded", acceptedCount: 1 });
    expect(repository.search("桂花茶", { petId: "xiaoju-cat" })).toHaveLength(1);
  });

  test("keeps the Outbox as a safe projection without raw evidence, full chat, or error text", async () => {
    const storage = createStorage();
    const repository = createCompanionMemoryRepository({ storage, now: () => NOW });
    const nextInput = input({
      message: "我喜欢桂花茶，请记住",
      sourceMessageId: "message-outbox",
    });
    const local = extractCompanionMemoryCandidate(nextInput.message, nextInput.sourceMessageId, nextInput.petId)!;
    await new CompanionMemoryPolicy({ repository, now: () => NOW }).process(
      nextInput,
      [local],
      new AbortController().signal,
    );
    const serialized = JSON.stringify(outbox(storage));
    expect(serialized).not.toContain(local.evidence);
    expect(serialized).not.toContain("模型候选证据");
    expect(serialized).not.toContain("memory-save-failed");
    expect(serialized).not.toContain("我喜欢桂花茶，请记住");
    expect(serialized).toContain(local.content);
    expect(serialized).toContain("message-outbox");
    expect(serialized).toContain("memory");
    expect(storage.values.has(COMPANION_MEMORY_STORAGE_KEY)).toBe(true);
  });
});
