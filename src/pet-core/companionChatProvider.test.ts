import { describe, expect, test, vi } from "vitest";
import {
  DEFAULT_COMPANION_PROVIDER_TIMEOUT_MS,
  CompanionChatProviderError,
  createCompanionChatProvider,
  getCompanionChatAdapter,
  normalizeCompanionProviderEndpoint,
  type CompanionChatHttpResponse,
  type CompanionChatHttpFetcher,
} from "./companionChatProvider";
import {
  getCompanionProviderProfilePreset,
  normalizeCompanionProviderSettings,
  type CompanionProviderProfile,
} from "./companionProviderConfig";
import type { CompanionChatConfig } from "./companionChat";
import {
  MAX_CONTEXT_HISTORY_MESSAGES,
  assembleCompanionContext,
} from "./companionContext";
import { createCompanionContextEpoch } from "./companionContextEpoch";
import { resolveCompanionChatPipelineRoute } from "./companionChatPipeline";
import type { MemoryEntry } from "./companionMemory";

const config: CompanionChatConfig = {
  openers: [{ text: "喵？" }],
  localReplies: ["嗯，我听着。"],
  style: { tone: "quiet-companion", maxReplyLength: 24 },
};

function response(payload: unknown, status = 200): CompanionChatHttpResponse {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  };
}

function profile(
  protocol: "gemini-native" | "openai-compatible" | "local",
  overrides: Partial<CompanionProviderProfile> = {},
): CompanionProviderProfile {
  const preset = getCompanionProviderProfilePreset(
    protocol === "gemini-native" ? "google-gemini" : protocol === "openai-compatible" ? "custom-provider" : "local",
  )!;
  return normalizeCompanionProviderSettings({
    ...preset,
    ...overrides,
    protocol,
  });
}

function createRemote(
  protocol: "gemini-native" | "openai-compatible",
  fetcher: CompanionChatHttpFetcher,
  overrides: Partial<CompanionProviderProfile> = {},
  options: { timeoutMs?: number; credential?: string } = {},
) {
  return createCompanionChatProvider(config, {
    profile: profile(protocol, overrides),
    credential: options.credential ?? "unit-secret",
    fetcher,
    timeoutMs: options.timeoutMs,
  });
}

describe("provider-neutral chat adapters", () => {
  test("normalizes final request bases for both supported remote protocols", () => {
    expect(normalizeCompanionProviderEndpoint(
      "gemini-native",
      "https://generativelanguage.googleapis.com/v1beta/models/",
    )).toBe("https://generativelanguage.googleapis.com/v1beta");
    expect(normalizeCompanionProviderEndpoint(
      "openai-compatible",
      "https://models.example/v1/chat/completions/",
    )).toBe("https://models.example/v1");
    expect(normalizeCompanionProviderEndpoint(
      "openai-compatible",
      "https://models.example",
    )).toBe("https://models.example/v1");
    expect(() => normalizeCompanionProviderEndpoint(
      "openai-compatible",
      "http://remote.example/v1",
    )).toThrow("HTTPS");
    expect(normalizeCompanionProviderEndpoint(
      "openai-compatible",
      "http://localhost:8787/v1",
    )).toBe("http://localhost:8787/v1");
  });

  test("selects adapters by protocol and fails closed for an unknown protocol", () => {
    expect(getCompanionChatAdapter("local").protocol).toBe("local");
    expect(getCompanionChatAdapter("gemini-native").protocol).toBe("gemini-native");
    expect(getCompanionChatAdapter("openai-compatible").protocol).toBe("openai-compatible");
    expect(() => getCompanionChatAdapter("future-protocol")).toThrow("不支持");
  });

  test("keeps local companionship local and never calls a fetcher", async () => {
    const fetcher = vi.fn(async () => response({}));
    const provider = createCompanionChatProvider(config, {
      profile: profile("local"),
      fetcher,
    });

    await expect(provider.send({ text: "今天还行" })).resolves.toEqual({
      text: "嗯，我听着。",
    });
    expect(provider.info).toMatchObject({ kind: "local", target: "本机" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  test("sends a filtered Gemini-native request and reads the model reply", async () => {
    const fetcher = vi.fn(async (_url, _init) => response({
      candidates: [{ content: { parts: [{ text: "那就慢慢来，我在这里陪你。" }] } }],
    }));
    const provider = createRemote("gemini-native", fetcher, {
      endpoint: "https://generativelanguage.googleapis.com/v1beta",
      model: "gemini-test-model",
    });

    await expect(provider.send({
      text: "今天有点累",
      history: [
        { id: "safe", speaker: "user", text: "你好" },
        { id: "unsafe", speaker: "user", text: "my password is never-send-history" },
      ],
    })).resolves.toEqual({ text: "那就慢慢来，我在这里陪你。" });

    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe(
      "https://generativelanguage.googleapis.com/v1beta/models/gemini-test-model:generateContent",
    );
    const body = JSON.parse(init.body) as {
      system_instruction: { parts: Array<{ text: string }> };
      contents: Array<{ role: string; parts: Array<{ text: string }> }>;
    };
    expect(body.contents).toEqual([
      { role: "user", parts: [{ text: "你好" }] },
      { role: "user", parts: [{ text: "今天有点累" }] },
    ]);
    expect(body.system_instruction.parts[0].text).toContain("平台安全与隐私规则");
    expect(init.headers["x-goog-api-key"]).toBe("unit-secret");
    expect(JSON.stringify(provider.info)).not.toContain("unit-secret");
  });

  test("sends the same context contract through openai-compatible chat/completions", async () => {
    const fetcher = vi.fn(async (_url, _init) => response({
      id: "completion",
      choices: [{ message: { role: "assistant", content: "我在这里。" } }],
    }));
    const provider = createRemote("openai-compatible", fetcher, {
      endpoint: "https://models.example/v1/chat/completions",
      model: "chat-model",
    });

    await expect(provider.send({
      text: "桂花茶",
      petId: "xiaoju-cat",
      context: assembleCompanionContext({
        petId: "xiaoju-cat",
        userInput: "桂花茶",
        systemPrompt: "保留当前宠物的陪伴语气。",
      }),
    })).resolves.toEqual({ text: "我在这里。" });

    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe("https://models.example/v1/chat/completions");
    expect(init.headers.Authorization).toBe("Bearer unit-secret");
    const body = JSON.parse(init.body) as {
      model: string;
      messages: Array<{ role: string; content: string }>;
    };
    expect(body.model).toBe("chat-model");
    expect(body.messages[0]?.role).toBe("system");
    expect(body.messages[body.messages.length - 1]).toEqual({ role: "user", content: "桂花茶" });
    expect(body.messages[0]?.content).not.toContain("当前宠物 ID：xiaoju-cat");
  });

  test.each([
    ["gemini-native", { candidates: [{ content: { parts: [{ text: "预算安全。" }] } }] }],
    ["openai-compatible", { choices: [{ message: { content: "预算安全。" } }] }],
  ] as const)("keeps Budget metadata out of the %s request body", async (protocol, payload) => {
    const fetcher = vi.fn(async () => response(payload));
    const provider = createRemote(protocol, fetcher);
    const context = assembleCompanionContext({
      petId: "xiaoju-cat",
      userInput: "预算测试",
      memories: [{
        id: "budget-memory",
        scope: "global",
        type: "fact",
        content: "BUDGET_SAFE_MEMORY_SENTINEL",
        source: "explicit",
        evidence: "用户明确表达",
        sourceMessageId: "message-budget",
        confidence: 0.9,
        createdAt: "2026-08-01T10:00:00.000Z",
        updatedAt: "2026-08-01T10:00:00.000Z",
        expiresAt: null,
        status: "active",
        supersedesId: null,
        deletedAt: null,
      }],
      preferences: [
        {
          id: "global.nickname",
          scope: "global",
          category: "userProfile",
          key: "nickname",
          value: "PROFILE_NICKNAME_ALLOWED",
          source: "explicit",
        },
        {
          id: "global.gender",
          scope: "global",
          category: "userProfile",
          key: "gender",
          value: "PROFILE_GENDER_SENTINEL",
          source: "explicit",
        },
        {
          id: "global.email",
          scope: "global",
          category: "userProfile",
          key: "email",
          value: "PROFILE_EMAIL_SENTINEL",
          source: "explicit",
        },
        {
          id: "global.phone",
          scope: "global",
          category: "userProfile",
          key: "phone",
          value: "PROFILE_PHONE_SENTINEL",
          source: "explicit",
        },
      ],
      budget: { maxCharacters: 2_400, maxEstimatedTokens: 2_400 },
    });

    await provider.send({ text: "预算测试", petId: "xiaoju-cat", context });
    const [, init] = fetcher.mock.calls[0] as unknown as [string, { body: string }];
    expect(init.body).toContain("BUDGET_SAFE_MEMORY_SENTINEL");
    expect(init.body).toContain("PROFILE_NICKNAME_ALLOWED");
    expect(init.body).not.toContain("PROFILE_GENDER_SENTINEL");
    expect(init.body).not.toContain("PROFILE_EMAIL_SENTINEL");
    expect(init.body).not.toContain("PROFILE_PHONE_SENTINEL");
    expect(init.body).not.toContain("maxCharacters");
    expect(init.body).not.toContain("maxEstimatedTokens");
    expect(init.body).not.toContain("actualCharacters");
    expect(JSON.stringify(context)).not.toContain("maxCharacters");
  });

  test.each([
    ["gemini-native", { candidates: [{ content: { parts: [{ text: "Profile 安全。" }] } }] }],
    ["openai-compatible", { choices: [{ message: { content: "Profile 安全。" } }] }],
  ] as const)("applies the exact Profile allowlist before the %s request body", async (protocol, payload) => {
    const fetcher = vi.fn(async () => response(payload));
    const provider = createRemote(protocol, fetcher);
    const context = assembleCompanionContext({
      petId: "xiaoju-cat",
      userInput: "安全输入",
      preferences: [
        {
          id: "global.nickname",
          scope: "global",
          category: "userProfile",
          key: "nickname",
          value: "阿星",
          source: "explicit",
        },
        {
          id: "global.replyStyle",
          scope: "global",
          category: "userProfile",
          key: "replyStyle",
          value: "short-and-soft",
          source: "explicit",
        },
        {
          id: "global.companionStyle",
          scope: "global",
          category: "userProfile",
          key: "companionStyle",
          value: "quiet",
          source: "inferred",
        },
        {
          id: "contact-a",
          scope: "global",
          category: "userProfile",
          key: "contact-a",
          value: "real.person@example.com",
          source: "explicit",
        },
        {
          id: "global.alias",
          scope: "global",
          category: "userProfile",
          key: "alias",
          value: "+86 138 0013 8000",
          source: "explicit",
        },
        {
          id: "global.status",
          scope: "global",
          category: "userProfile",
          key: "status",
          value: "female",
          source: "explicit",
        },
        {
          id: "pet:other-cat.favorite",
          scope: "pet:other-cat",
          category: "petRelationship",
          key: "favorite",
          value: "OTHER_PET_NEVER_SEND",
          source: "explicit",
        },
      ],
    });

    await expect(provider.send({
      text: "安全输入",
      petId: "xiaoju-cat",
      context,
    })).resolves.toHaveProperty("text", "Profile 安全。");

    const [, init] = fetcher.mock.calls[0] as unknown as [string, { body: string }];
    const body = init.body;
    expect(body).toContain("阿星");
    expect(body).toContain("short-and-soft");
    expect(body).toContain("quiet");
    for (const rejected of [
      "real.person@example.com",
      "+86 138 0013 8000",
      "female",
      "OTHER_PET_NEVER_SEND",
    ]) {
      expect(body).not.toContain(rejected);
    }
  });

  test.each(["gemini-native", "openai-compatible"] as const)(
    "fails closed without a request when a protected rendered context exceeds the hard budget: %s",
    async (protocol) => {
      const fetcher = vi.fn(async () => response({}));
      const provider = createRemote(protocol, fetcher);
      await expect(provider.send({
        text: "安全当前输入",
        context: {
          petId: "xiaoju-cat",
          systemInstruction: "PLATFORM_SAFETY_HARD_BUDGET ".repeat(2_000),
          history: [],
          userInput: "安全当前输入",
        },
      })).rejects.toMatchObject({ kind: "configuration" });
      expect(fetcher).not.toHaveBeenCalled();
    },
  );

  test.each(["gemini-native", "openai-compatible"] as const)(
    "rejects a hand-built context instead of trusting its history for %s",
    async (protocol) => {
      const fetcher = vi.fn(async () => response({}));
      const provider = createRemote(protocol, fetcher);
      const currentEpoch = createCompanionContextEpoch();
      const oldEpoch = createCompanionContextEpoch();
      const visibleHistory = [
        {
          id: "old-topic-visible-only",
          speaker: "user" as const,
          text: "旧话题 visible-only，不应发给 Provider",
          contextEpoch: oldEpoch,
        },
        ...Array.from({ length: MAX_CONTEXT_HISTORY_MESSAGES + 4 }, (_, index) => ({
          id: `current-safe-${index}`,
          speaker: "user" as const,
          text: `当前安全消息 ${index}`,
          contextEpoch: currentEpoch,
        })),
        {
          id: "current-sensitive",
          speaker: "user" as const,
          text: "my password is never-send-history",
          contextEpoch: currentEpoch,
        },
      ];

      await expect(provider.send({
        text: "当前输入最高优先级",
        contextEpoch: currentEpoch,
        context: {
          petId: "xiaoju-cat",
          systemInstruction: "LOCAL_TASK_PROJECTION_MUST_NEVER_LEAVE",
          history: visibleHistory,
          userInput: "当前输入最高优先级",
          contextEpoch: currentEpoch,
        },
      })).rejects.toMatchObject({ kind: "configuration" });
      expect(fetcher).not.toHaveBeenCalled();
    },
  );

  test.each([
    ["gemini-native", { candidates: [{ content: { parts: [{ text: "正式上下文保留。" }] } }] }],
    ["openai-compatible", { choices: [{ message: { content: "正式上下文保留。" } }] }],
  ] as const)("accepts only official builder context for %s", async (protocol, payload) => {
    const fetcher = vi.fn(async () => response(payload));
    const provider = createRemote(protocol, fetcher);
    const currentEpoch = createCompanionContextEpoch();
    const oldEpoch = createCompanionContextEpoch();
    const context = assembleCompanionContext({
      petId: "xiaoju-cat",
      userInput: "帮我把任务安排清楚，但不要读取本地任务。",
      contextEpoch: currentEpoch,
      history: [
        { id: "old", speaker: "user", text: "旧消息不保留", contextEpoch: oldEpoch },
        { id: "safe", speaker: "user", text: "Global Memory 可以参考", contextEpoch: currentEpoch },
        { id: "unsafe", speaker: "user", text: "my password is never-send-history", contextEpoch: currentEpoch },
      ],
      memories: [
        {
          id: "global-safe",
          scope: "global",
          type: "fact",
          content: "GLOBAL_MEMORY_MUST_REMAIN",
          source: "explicit",
          evidence: "用户明确表达",
          sourceMessageId: "message-global-safe",
          confidence: 0.9,
          createdAt: "2026-08-01T10:00:00.000Z",
          updatedAt: "2026-08-01T10:00:00.000Z",
          expiresAt: null,
          status: "active",
          supersedesId: null,
          deletedAt: null,
        },
        {
          id: "pet-safe",
          scope: "pet:xiaoju-cat",
          type: "relationship",
          content: "PET_RELATIONSHIP_MUST_REMAIN",
          source: "confirmed",
          evidence: "用户确认",
          sourceMessageId: "message-pet-safe",
          confidence: 0.9,
          createdAt: "2026-08-01T10:00:00.000Z",
          updatedAt: "2026-08-01T10:00:00.000Z",
          expiresAt: null,
          status: "active",
          supersedesId: null,
          deletedAt: null,
        },
      ],
    });

    await expect(provider.send({
      text: context.userInput,
      context,
    })).resolves.toHaveProperty("text", "正式上下文保留。");
    const [, init] = fetcher.mock.calls[0] as unknown as [string, { body: string }];
    const body = init.body;
    expect(body).toContain("GLOBAL_MEMORY_MUST_REMAIN");
    expect(body).toContain("PET_RELATIONSHIP_MUST_REMAIN");
    expect(body).toContain("帮我把任务安排清楚，但不要读取本地任务。");
    expect(body).not.toContain("LOCAL_TASK_PROJECTION_MUST_NEVER_LEAVE");
    expect(body).not.toContain("never-send-history");
    expect(body).not.toContain("contextEpoch");
  });

  test.each(["gemini-native", "openai-compatible"] as const)(
    "rejects a trusted Context from another pet or epoch before fetch for %s",
    async (protocol) => {
      const fetcher = vi.fn(async () => response({}));
      const provider = createRemote(protocol, fetcher);
      const contextEpoch = createCompanionContextEpoch();
      const context = assembleCompanionContext({
        petId: "xiaoju-cat",
        userInput: "当前输入最高优先级",
        contextEpoch,
        history: [{ id: "pet-a", speaker: "user", text: "只属于小橘" }],
      });

      await expect(provider.send({
        text: "当前输入最高优先级",
        petId: "other-cat",
        contextEpoch,
        context,
      })).rejects.toMatchObject({ kind: "configuration" });
      await expect(provider.send({
        text: "当前输入最高优先级",
        petId: "xiaoju-cat",
        contextEpoch: contextEpoch + 1,
        context,
      })).rejects.toMatchObject({ kind: "configuration" });
      expect(fetcher).not.toHaveBeenCalled();
    },
  );

  test.each(["gemini-native", "openai-compatible"] as const)(
    "blocks preassembled Task/Reminder/Profile payloads before fetch for %s",
    async (protocol) => {
      const fetcher = vi.fn(async () => response({}));
      const provider = createRemote(protocol, fetcher);
      const forgedContext = {
        petId: "xiaoju-cat",
        systemInstruction: "LOCAL_TASK_PROJECTION_MUST_NEVER_LEAVE",
        history: [{
          id: "forged",
          speaker: "user" as const,
          text: "Task title ReminderInstance Tombstone Outbox Task Event currentTime timezone offset profile@example.com +8613800138000 female",
        }],
        userInput: "安全当前输入",
        tasks: [{ title: "TASK_TITLE_NEVER_SEND" }],
        reminderInstance: "REMINDER_INSTANCE_NEVER_SEND",
        tombstone: "TOMBSTONE_NEVER_SEND",
        outboxTaskEvent: "OUTBOX_TASK_EVENT_NEVER_SEND",
        currentTime: "CURRENT_TIME_NEVER_SEND",
        timezone: "TIMEZONE_NEVER_SEND",
        utcOffsetMinutes: 480,
        profile: {
          email: "profile@example.com",
          phone: "+8613800138000",
          gender: "female",
        },
      } as unknown as Parameters<typeof provider.send>[0]["context"];

      await expect(provider.send({
        text: "安全当前输入",
        context: forgedContext,
      })).rejects.toMatchObject({ kind: "configuration" });
      expect(fetcher).not.toHaveBeenCalled();
    },
  );

  test.each([
    ["gemini-native", { candidates: [{ content: { parts: [{ text: "我在。" }] } }] }],
    ["openai-compatible", { choices: [{ message: { content: "我在。" } }] }],
  ] as const)("uses the same remote privacy filter for %s", async (protocol, payload) => {
    const fetcher = vi.fn(async () => response(payload));
    const provider = createRemote(protocol, fetcher);
    const sensitiveMemory: MemoryEntry = {
      id: "memory-1",
      scope: "global",
      type: "fact",
      content: "这条 Memory 的内容不应进入远程请求",
      source: "explicit",
      evidence: "my medical diagnosis is never-send-evidence",
      sourceMessageId: "message-1",
      confidence: 0.9,
      createdAt: "2026-08-01T10:00:00.000Z",
      updatedAt: "2026-08-01T10:00:00.000Z",
      expiresAt: null,
      status: "active",
      supersedesId: null,
      deletedAt: null,
    };

    await provider.send({
      text: "安全输入",
      memories: [sensitiveMemory],
      preferences: [{
        id: "global.nickname",
        scope: "global",
        category: "userProfile",
        key: "nickname",
        value: "my api key is never-send-preference",
        source: "explicit",
      }],
    });

    const firstCall = fetcher.mock.calls[0] as unknown as [string, { body: string }];
    expect(firstCall?.[1]?.body).not.toContain("never-send");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  test.each([
    ["gemini-native", { candidates: [{ content: { parts: [{ text: "慢慢来。" }] } }] }],
    ["openai-compatible", { choices: [{ message: { content: "慢慢来。" } }] }],
  ] as const)("never serializes local Task or Reminder facts for %s", async (protocol, payload) => {
    const fetcher = vi.fn(async () => response(payload));
    const provider = createRemote(protocol, fetcher);
    const text = "交报告这件事让我有点焦虑。";
    const localTaskFacts = {
      tasks: [
        {
          id: "task-related-never-send",
          title: "TASK_PROVIDER_RELATED_NEVER_SEND",
          status: "pending",
          matchEvidence: "交报告",
          dueAt: "2026-08-20T15:00:00.000Z",
          deletedAt: null,
        },
        {
          id: "task-near-due-never-send",
          title: "TASK_PROVIDER_NEAR_DUE_NEVER_SEND",
          status: "pending",
          dueAt: "2026-08-11T15:00:00.000Z",
          deletedAt: null,
        },
        {
          id: "task-unrelated-never-send",
          title: "TASK_PROVIDER_UNRELATED_NEVER_SEND",
          status: "pending",
          dueAt: "2026-09-01T09:00:00.000Z",
          deletedAt: null,
        },
        {
          id: "task-completed-never-send",
          title: "TASK_PROVIDER_COMPLETED_NEVER_SEND",
          status: "completed",
          dueAt: "2026-08-10T15:00:00.000Z",
          deletedAt: null,
        },
        {
          id: "task-cancelled-never-send",
          title: "TASK_PROVIDER_CANCELLED_NEVER_SEND",
          status: "cancelled",
          dueAt: "2026-08-12T15:00:00.000Z",
          deletedAt: null,
        },
        {
          id: "task-deleted-never-send",
          title: "TASK_PROVIDER_DELETED_NEVER_SEND",
          status: "cancelled",
          dueAt: null,
          deletedAt: "2026-08-11T09:00:00.000Z",
        },
        {
          id: "task-soft-deleted-never-send",
          title: "TASK_PROVIDER_SOFT_DELETED_NEVER_SEND",
          status: "pending",
          dueAt: "2026-08-11T15:00:00.000Z",
          deletedAt: "2026-08-11T09:01:00.000Z",
        },
        {
          id: "task-physical-deleted-never-send",
          title: "TASK_PROVIDER_PHYSICAL_DELETED_NEVER_SEND",
          status: "deleted",
          dueAt: null,
          deletedAt: "2026-08-11T09:02:00.000Z",
        },
      ],
      reminders: [{
        id: "reminder-never-send",
        taskId: "task-near-due-never-send",
        remindAt: "2026-08-11T14:45:00.000Z",
        sentinel: "REMINDER_PROVIDER_NEVER_SEND",
      }],
      reminderInstances: [{
        id: "reminder-instance-never-send",
        reminderId: "reminder-never-send",
        taskId: "task-near-due-never-send",
        status: "scheduled",
        scheduledAt: "2026-08-11T14:45:00.000Z",
        sentinel: "REMINDER_INSTANCE_PROVIDER_NEVER_SEND",
      }],
      taskContext: {
        reason: "recently-due",
        sentinel: "TASK_PROJECTION_NEVER_SEND",
      },
      taskProjection: "TASK_PROJECTION_OBJECT_NEVER_SEND",
      tombstone: "TASK_TOMBSTONE_NEVER_SEND",
      outboxTaskEvent: "OUTBOX_TASK_EVENT_NEVER_SEND",
      currentTime: "CURRENT_TIME_NEVER_SEND",
      timezone: "TIMEZONE_NEVER_SEND",
      utcOffsetMinutes: "UTC_OFFSET_NEVER_SEND",
    };
    const context = assembleCompanionContext({
      petId: "xiaoju-cat",
      userInput: text,
      ...localTaskFacts,
    });
    const providerInput = {
      text,
      petId: "xiaoju-cat",
      context,
      ...localTaskFacts,
    };

    await provider.send(providerInput);

    const firstCall = fetcher.mock.calls[0] as unknown as [string, { body: string }];
    const requestBody = firstCall?.[1]?.body ?? "";
    expect(requestBody).toContain(text);
    for (const sentinel of [
      "TASK_PROVIDER_RELATED_NEVER_SEND",
      "TASK_PROVIDER_NEAR_DUE_NEVER_SEND",
      "TASK_PROVIDER_UNRELATED_NEVER_SEND",
      "TASK_PROVIDER_COMPLETED_NEVER_SEND",
      "TASK_PROVIDER_CANCELLED_NEVER_SEND",
      "TASK_PROVIDER_DELETED_NEVER_SEND",
      "TASK_PROVIDER_SOFT_DELETED_NEVER_SEND",
      "TASK_PROVIDER_PHYSICAL_DELETED_NEVER_SEND",
      "REMINDER_PROVIDER_NEVER_SEND",
      "REMINDER_INSTANCE_PROVIDER_NEVER_SEND",
      "TASK_PROJECTION_NEVER_SEND",
      "TASK_PROJECTION_OBJECT_NEVER_SEND",
      "TASK_TOMBSTONE_NEVER_SEND",
      "OUTBOX_TASK_EVENT_NEVER_SEND",
      "CURRENT_TIME_NEVER_SEND",
      "TIMEZONE_NEVER_SEND",
      "UTC_OFFSET_NEVER_SEND",
    ]) {
      expect(requestBody).not.toContain(sentinel);
    }
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  test("blocks sensitive current input before any remote adapter request", async () => {
    const fetcher = vi.fn(async () => response({}));
    const provider = createRemote("openai-compatible", fetcher);

    await expect(provider.send({ text: "我的身份证号是 123" })).resolves.toEqual({
      text: "这类隐私我们先不发到云端，好吗？我可以安静陪着你。",
    });
    expect(fetcher).not.toHaveBeenCalled();
  });

  test.each([
    "my password is NEVER_SEND_PASSWORD",
    "Bearer NEVER_SEND_BEARER_TOKEN",
    "sk-proj-NEVER_SEND_API_KEY_1234567890",
    "我的身份证号是 11010519491231002X",
    "信用卡号 4111111111111111",
    "I live at 123 Main Street",
    "my medical diagnosis is NEVER_SEND_DIAGNOSIS",
    "I take metformin every day",
  ])("blocks sensitive current input for every remote protocol: %s", async (text) => {
    for (const protocol of ["gemini-native", "openai-compatible"] as const) {
      const fetcher = vi.fn(async () => response({
        candidates: [{ content: { parts: [{ text: "不应请求" }] } }],
        choices: [{ message: { content: "不应请求" } }],
      }));
      const provider = createRemote(protocol, fetcher);
      await expect(provider.send({ text })).resolves.toEqual({
        text: "这类隐私我们先不发到云端，好吗？我可以安静陪着你。",
      });
      expect(fetcher).not.toHaveBeenCalled();
    }
  });

  test("classifies authentication, rate-limit, malformed, and network failures without echoing secrets", async () => {
    const auth = createRemote("openai-compatible", async () => response({ error: { message: "secret detail" } }, 401));
    await expect(auth.send({ text: "你好" })).rejects.toMatchObject({
      kind: "authentication",
      status: 401,
    });

    const rate = createRemote("gemini-native", async () => response({ error: { message: "quota" } }, 429));
    await expect(rate.send({ text: "你好" })).rejects.toMatchObject({
      kind: "rate-limit",
      status: 429,
    });

    const malformed = createRemote("openai-compatible", async () => response({ choices: [] }));
    await expect(malformed.send({ text: "你好" })).rejects.toMatchObject({
      kind: "malformed-response",
    });

    const network = createRemote("openai-compatible", async () => {
      throw new Error("request failed with unit-secret");
    });
    await expect(network.send({ text: "你好" })).rejects.toMatchObject({
      kind: "network",
      userMessage: "聊天服务暂时没接上，稍后再试。",
    });
    await expect(network.send({ text: "你好" })).rejects.not.toHaveProperty("message", expect.stringContaining("unit-secret"));
  });

  test("supports a unified timeout and caller cancellation signal", async () => {
    const hanging = createRemote("openai-compatible", () => new Promise(() => {}), {}, {
      timeoutMs: 10,
    });
    await expect(hanging.send({ text: "你好" })).rejects.toMatchObject({
      kind: "timeout",
    });

    const controller = new AbortController();
    const cancellable = createRemote("gemini-native", () => new Promise(() => {}), {}, {
      timeoutMs: DEFAULT_COMPANION_PROVIDER_TIMEOUT_MS,
    });
    const request = cancellable.send({ text: "你好", signal: controller.signal });
    controller.abort();
    await expect(request).rejects.toMatchObject({ kind: "cancelled" });
  });

  test("rejects missing credentials, invalid configuration, and never silently chooses another protocol", () => {
    expect(() => createCompanionChatProvider(config, {
      profile: profile("openai-compatible"),
    })).toThrow("凭据");
    expect(() => createCompanionChatProvider(config, {
      profile: normalizeCompanionProviderSettings({
        id: "future-model",
        displayName: "未来服务",
        protocol: "future-protocol",
        endpoint: "https://models.example/v1",
        model: "future",
        credentialRef: "future-model",
      }),
      credential: "unit-secret",
    })).toThrow("不支持");
    expect(() => createCompanionChatProvider(config, {
      profile: profile("openai-compatible", { endpoint: "https://models.example/v1?token=hidden" }),
      credential: "unit-secret",
    })).toThrow("查询参数");
  });

  test("does not mutate Soul, Memory, Task-adjacent context, or pet identity when profiles change", async () => {
    const context = assembleCompanionContext({
      petId: "xiaoju-cat",
      userInput: "今天还行",
      systemPrompt: "小橘的陪伴语气。",
      soul: {
        status: "loaded",
        petId: "xiaoju-cat",
        path: "SOUL.md",
        content: "小橘只安静陪伴，不执行外部操作。",
      },
      memories: [{
        id: "memory-1",
        scope: "global",
        type: "fact",
        content: "用户喜欢桂花茶",
        source: "explicit",
        evidence: "用户明确说过",
        sourceMessageId: "message-1",
        confidence: 0.9,
        createdAt: "2026-08-01T10:00:00.000Z",
        updatedAt: "2026-08-01T10:00:00.000Z",
        expiresAt: null,
        status: "active",
        supersedesId: null,
        deletedAt: null,
      }],
      history: [],
    });
    const contextBefore = JSON.stringify(context);
    const gemini = createRemote("gemini-native", async () => response({
      candidates: [{ content: { parts: [{ text: "我在。" }] } }],
    }));
    const openai = createRemote("openai-compatible", async () => response({
      choices: [{ message: { content: "我也在。" } }],
    }));

    await gemini.send({ text: "今天还行", petId: "xiaoju-cat", context });
    await openai.send({ text: "今天还行", petId: "xiaoju-cat", context });
    const taskText = "明天下午三点提醒我交报告";
    const taskRouteBefore = resolveCompanionChatPipelineRoute({
      text: taskText,
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
      taskOptions: { now: new Date("2026-08-10T00:00:00.000Z"), timezoneOffsetMinutes: 480 },
    });
    const taskRouteAfter = resolveCompanionChatPipelineRoute({
      text: taskText,
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
      taskOptions: { now: new Date("2026-08-10T00:00:00.000Z"), timezoneOffsetMinutes: 480 },
    });
    expect(JSON.stringify(context)).toBe(contextBefore);
    expect(context.petId).toBe("xiaoju-cat");
    expect(context.systemInstruction).toContain("小橘的陪伴语气");
    expect(context.systemInstruction).toContain("用户喜欢桂花茶");
    expect(taskRouteAfter).toEqual(taskRouteBefore);
  });

  test("preserves the local fallback contract as an explicit local adapter", async () => {
    const provider = createCompanionChatProvider(config, {
      profile: profile("local"),
    });
    expect(provider.info.kind).toBe("local");
    await expect(provider.send({ text: "你好" })).resolves.toHaveProperty("text");
    expect(CompanionChatProviderError).toBeDefined();
  });
});
