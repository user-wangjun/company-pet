import { describe, expect, test, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  createCompanionAppHarness,
  COMPANION_LOCAL_USER_ID,
  type CompanionAppHarnessSources,
} from "./companionAppHarness";
import {
  createInMemoryCompanionTaskRepository,
} from "./companionActionPipeline";
import {
  createCompanionMemoryRepository,
  type MemoryRepository,
} from "./companionMemory";
import {
  createCompanionUserSettingsOwner,
  createCompanionUserSettingsRepository,
} from "./companionUserSettingsRepository";
import {
  EMPTY_COMPANION_PREFERENCES,
  type CompanionPreferencesState,
} from "./companionPreferences";
import {
  createProactiveTriggerEngine,
} from "./proactiveTriggerEngine";
import {
  getCompanionProviderProfilePreset,
  type CompanionProviderProfile,
  type CompanionProviderSettings,
} from "./companionProviderConfig";
import type {
  CompanionInput,
  CompanionModelResponse,
  CompanionResponse,
  CompanionResponseSink,
  CompanionTaskRepository,
  MemoryCandidate,
} from "./companionHarnessTypes";
import type { CompanionChatMessage } from "./companionChatRuntime";
import type { PetSoulPackage } from "./petSoul";
import type { ProviderHttpFetcher } from "./companionProviderAdapter";
import type { TaskDatabase } from "../task-core/types";
import { EMPTY_TASK_DATABASE } from "../task-core/taskStore";

const NOW = "2026-08-11T12:00:00.000Z";

function createStorage() {
  const values = new Map<string, string>();
  return {
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((_key: string, nextValue: string) => {
      values.set(_key, nextValue);
    }),
  };
}

function localPackage(petId: string): CompanionAppHarnessSources["getCompanionChatPackage"] extends (
  petId: string,
) => infer T ? T : never {
  return {
    status: "loaded",
    petId,
    config: {
      openers: [{ text: "喵？" }],
      localReplies: [`${petId}-local-reply`],
      style: { maxReplyLength: 80 },
      systemPrompt: petId === "xiaoju-cat" ? "小橘 system prompt" : "ikun system prompt",
    },
  } as never;
}

function remoteProfile(): CompanionProviderProfile {
  const preset = getCompanionProviderProfilePreset("custom-provider");
  if (!preset) throw new Error("custom-provider preset missing");
  return {
    ...preset,
    endpoint: "https://phase7.example.test/v1",
    model: "phase7-model",
  };
}

function input(overrides: Partial<CompanionInput> = {}): CompanionInput {
  return {
    requestId: "phase7-request-1",
    sessionId: "phase7-session-1",
    sourceMessageId: "phase7-message-1",
    userId: COMPANION_LOCAL_USER_ID,
    petId: "xiaoju-cat",
    message: "今天还好吗",
    currentTime: NOW,
    timezone: "Asia/Shanghai",
    utcOffsetMinutes: 480,
    source: "chat",
    contextEpoch: 1,
    ...overrides,
  };
}

function modelMemoryCandidate(sourceMessageId: string): MemoryCandidate {
  return {
    scope: "global",
    type: "preference",
    category: "preference",
    lifetime: "stable",
    content: "用户喜欢桂花茶",
    source: "inferred",
    evidence: "模型候选证据",
    sourceMessageId,
    confidence: 1,
    importance: 1,
    explicitness: "inferred",
    confirmationStatus: "requires_confirmation",
    expiresAt: null,
    requiresConfirmation: true,
    confirmed: false,
  };
}

type Fixture = {
  runtime: ReturnType<typeof createCompanionAppHarness>;
  taskRepository: CompanionTaskRepository & { readonly writes: number; setFailWrites(value: boolean): void };
  memoryRepository: MemoryRepository;
  preferences: () => CompanionPreferencesState;
  setPreferencesWriteFailure(value: boolean): void;
  commits: Array<{ input: CompanionInput; response: CompanionResponse }>;
  modelResponses: Array<CompanionModelResponse>;
  fetcher: ReturnType<typeof vi.fn<ProviderHttpFetcher>>;
  setProvider(settings: CompanionProviderSettings, credential: string | null): void;
  setPet(petId: string): void;
  setRemoteReply(text: string): void;
};

function createFixture(options: {
  remote?: boolean;
  taskDatabase?: TaskDatabase;
  memoryRepository?: MemoryRepository;
  fetcher?: ProviderHttpFetcher;
} = {}): Fixture {
  let activePetId = "xiaoju-cat";
  let settingsWriteFailure = false;
  const settingsValues = new Map<string, string>();
  const settingsStorage = {
    getItem: vi.fn((key: string) => settingsValues.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      if (settingsWriteFailure) throw new Error("settings write failed");
      settingsValues.set(key, value);
    }),
    removeItem: vi.fn((key: string) => {
      if (settingsWriteFailure) throw new Error("settings remove failed");
      settingsValues.delete(key);
    }),
  };
  const settingsRepository = createCompanionUserSettingsRepository({
    owner: createCompanionUserSettingsOwner(settingsStorage),
  });
  let providerProfile: CompanionProviderProfile = options.remote
    ? remoteProfile()
    : (getCompanionProviderProfilePreset("local")!);
  let credential: string | null = options.remote ? "credential-sentinel" : null;
  let remoteReply = "phase7-remote-reply";
  const availablePetIds = ["xiaoju-cat", "ikun"];
  const taskRepository = createInMemoryCompanionTaskRepository(options.taskDatabase ?? EMPTY_TASK_DATABASE);
  const memoryRepository = options.memoryRepository ?? createCompanionMemoryRepository({
    storage: createStorage(),
    now: () => Date.parse(NOW),
    idGenerator: () => "phase7-memory-id",
  });
  const proactiveStorage = createStorage();
  const triggerEngine = createProactiveTriggerEngine({
    storage: proactiveStorage,
    activePetId,
    availablePetIds,
  });
  const commits: Array<{ input: CompanionInput; response: CompanionResponse }> = [];
  const modelResponses: CompanionModelResponse[] = [];
  const fetcher = vi.fn<ProviderHttpFetcher>(async (_url, _init) => ({
    ok: true,
    status: 200,
    json: async () => ({
      choices: [{ message: { content: remoteReply } }],
    }),
  }));
  const responseSink: CompanionResponseSink = {
    commit(nextInput, response, guard) {
      guard.commitIfCurrent(nextInput, response, () => {
        commits.push({ input: nextInput, response });
      });
    },
  };
  const sources: CompanionAppHarnessSources = {
    getProviderProfile: () => providerProfile,
    getProviderCredential: () => credential,
    getFallbackToLocal: () => false,
    getActivePetId: () => activePetId,
    getAvailablePetIds: () => availablePetIds,
    getCompanionChatPackage: (petId) => localPackage(petId),
    getPetSoul: (petId): PetSoulPackage => ({
      status: "loaded",
      petId,
      path: "SOUL.md",
      content: petId === "xiaoju-cat" ? "小橘 soul" : "ikun soul",
    }),
    getPreferences: () => settingsRepository.getSnapshot()?.preferences ?? null,
    getMemoryRepository: () => memoryRepository,
    getHistory: ({ contextEpoch, sourceMessageId }) => [
      {
        id: "old-epoch",
        speaker: "user",
        text: "old visible history",
        contextEpoch: (contextEpoch ?? 1) - 1,
      },
      {
        id: "current-history",
        speaker: "pet",
        text: "current visible history",
        contextEpoch,
      },
    ].filter((message) => message.id !== sourceMessageId) as CompanionChatMessage[],
    taskRepository,
    getProactiveTriggerEngine: () => triggerEngine,
    settingsRepository,
    responseSink,
    fetcher,
    ...(options.remote
      ? { verifiedCapabilities: { structuredOutput: "json_object" as const } }
      : {}),
  };
  const runtime = createCompanionAppHarness(sources);
  return {
    runtime,
    taskRepository,
    memoryRepository,
    preferences: () => settingsRepository.getSnapshot()?.preferences ?? EMPTY_COMPANION_PREFERENCES,
    setPreferencesWriteFailure: (value) => {
      settingsWriteFailure = value;
    },
    commits,
    modelResponses,
    fetcher,
    setProvider: (settings, nextCredential) => {
      providerProfile = settings;
      credential = nextCredential;
    },
    setPet: (petId) => {
      activePetId = petId;
    },
    setRemoteReply: (text) => {
      remoteReply = text;
    },
  };
}

describe("Companion Harness Phase 7 acceptance", () => {
  test("uses one stable App composition root for local chat and local domain commands", async () => {
    const fixture = createFixture();
    const first = await fixture.runtime.harness.respond(input({
      requestId: "local-chat-request",
      sourceMessageId: "local-chat-message",
      message: "普通聊天",
    }));
    const task = await fixture.runtime.harness.respond(input({
      requestId: "local-task-request",
      sourceMessageId: "local-task-message",
      message: "明天交报告",
    }));

    expect(fixture.runtime.harness).toBe(fixture.runtime.harness);
    expect(first).toMatchObject({
      status: "success",
      text: "我会照着小伙伴的性格陪你，xiaoju-cat-local-reply",
      callCounts: { model: 1, external: 0, local: 1, fallback: 0 },
      committed: true,
    });
    expect(task).toMatchObject({
      status: "success",
      text: expect.stringContaining("已经为你创建"),
      callCounts: { model: 0, external: 0, local: 0, fallback: 0 },
      actions: [{ type: "create_task", status: "succeeded" }],
    });
    expect(fixture.taskRepository.writes).toBe(1);
    expect(fixture.fetcher).not.toHaveBeenCalled();
    expect(fixture.commits).toHaveLength(2);
  });

  test("local generation keeps the Turn pet snapshot after the active pet changes", async () => {
    const fixture = createFixture();
    const turn = fixture.runtime.modelPort.beginTurn();
    const turnInput = input({
      requestId: "pet-snapshot-request",
      sourceMessageId: "pet-snapshot-message",
      petId: "xiaoju-cat",
    });
    const context = await fixture.runtime.contextBuilder.build({
      petId: turnInput.petId,
      message: turnInput.message,
      sessionId: turnInput.sessionId,
      sourceMessageId: turnInput.sourceMessageId,
      contextEpoch: turnInput.contextEpoch,
    }, new AbortController().signal);

    fixture.setPet("ikun");
    const response = await turn.generate({
      input: turnInput,
      context,
    });

    expect(response.replyDraft).toContain("xiaoju-cat-local-reply");
    expect(response.replyDraft).not.toContain("ikun-local-reply");
  });

  test("keeps Preference and forget claims behind actual local persistence", async () => {
    const fixture = createFixture();
    const saved = await fixture.runtime.harness.respond(input({
      requestId: "preference-request",
      sourceMessageId: "preference-message",
      message: "以后叫我阿星",
    }));
    expect(saved).toMatchObject({
      status: "success",
      preference: { status: "succeeded", displayData: { key: "nickname" } },
    });
    expect(saved.text).toContain("这个称呼");
    expect(fixture.preferences().preferences).toHaveLength(1);

    fixture.setPreferencesWriteFailure(true);
    const failed = await fixture.runtime.harness.respond(input({
      requestId: "preference-failure-request",
      sourceMessageId: "preference-failure-message",
      message: "以后叫我小星",
    }));
    expect(failed).toMatchObject({
      status: "degraded",
      preference: { status: "failed" },
    });
    expect(failed.text).toContain("没有保存成功");
    expect(fixture.preferences().preferences[0]?.value).toBe("阿星");

    fixture.setPreferencesWriteFailure(false);
    const forgotten = await fixture.runtime.harness.respond(input({
      requestId: "forget-request",
      sourceMessageId: "forget-message",
      message: "忘掉刚才这条",
    }));
    expect(forgotten).toMatchObject({
      status: "success",
      forget: { status: "succeeded" },
    });
    expect(fixture.preferences().preferences).toEqual([]);
  });

  test("requires explicit confirmation, rechecks latest facts, and clears on cancel or pet switch", async () => {
    const fixture = createFixture();
    const initial = await fixture.runtime.harness.respond(input({
      requestId: "confirm-request",
      sourceMessageId: "confirm-message",
      message: "明天发布上线",
    }));
    expect(initial.actions).toMatchObject([{ status: "confirmation_required" }]);
    expect(fixture.taskRepository.writes).toBe(0);

    const ambiguous = await fixture.runtime.harness.respond(input({
      requestId: "ambiguous-confirm-request",
      sourceMessageId: "ambiguous-confirm-message",
      message: "再想想",
    }));
    expect(ambiguous.text).toContain("确认");
    expect(fixture.taskRepository.writes).toBe(0);

    const cancelled = await fixture.runtime.harness.respond(input({
      requestId: "cancel-confirm-request",
      sourceMessageId: "cancel-confirm-message",
      message: "取消",
    }));
    expect(cancelled.text).toBe("好，我不记这条。");
    expect(fixture.taskRepository.writes).toBe(0);

    const secondInitial = await fixture.runtime.harness.respond(input({
      requestId: "confirm-request-2",
      sourceMessageId: "confirm-message-2",
      message: "明天发布上线",
    }));
    expect(secondInitial.actions[0]?.status).toBe("confirmation_required");
    fixture.setPet("ikun");
    fixture.runtime.harness.cancel("phase7-session-1");
    const stale = await fixture.runtime.harness.respond(input({
      requestId: "stale-confirm-request",
      sourceMessageId: "stale-confirm-message",
      petId: "xiaoju-cat",
      message: "确认",
    }));
    expect(stale.actions).toEqual([]);
    expect(stale.text).not.toContain("已经为你创建");
    expect(fixture.taskRepository.writes).toBe(0);
  });

  test("explicit confirmation consumes the original candidate once and rechecks the current clock", async () => {
    const fixture = createFixture();
    const initial = await fixture.runtime.harness.respond(input({
      requestId: "confirm-write-request",
      sourceMessageId: "confirm-write-message",
      message: "明天发布上线",
    }));
    expect(initial.actions[0]?.status).toBe("confirmation_required");

    const confirmed = await fixture.runtime.harness.respond(input({
      requestId: "confirmation-message-request",
      sourceMessageId: "confirmation-message",
      message: "确认",
      currentTime: "2026-08-11T12:01:00.000Z",
    }));
    expect(confirmed.actions).toMatchObject([{ type: "create_task", status: "succeeded" }]);
    expect(fixture.taskRepository.writes).toBe(1);

    const retry = await fixture.runtime.harness.respond(input({
      requestId: "confirmation-retry-request",
      sourceMessageId: "confirm-write-message",
      message: "明天发布上线",
    }));
    expect(retry.actions[0]?.status).toBe("duplicate");
    expect(fixture.taskRepository.writes).toBe(1);
  });

  test("default Harness memory confirmation does not save before confirmation and saves once after it", async () => {
    const fixture = createFixture({ remote: true });
    fixture.setRemoteReply(JSON.stringify({
      replyDraft: "候选记忆",
      memoryCandidates: [modelMemoryCandidate("memory-message")],
    }));
    const original = await fixture.runtime.harness.respond(input({
      requestId: "memory-request",
      sourceMessageId: "memory-message",
      message: "我今天好累",
    }));
    expect(original.status).toBe("success");
    expect(original.memory.decisions[0]?.status).toBe("confirmation_required");
    expect(fixture.memoryRepository.list()).toEqual([]);
    expect(fixture.fetcher).toHaveBeenCalledTimes(1);

    const confirmed = await fixture.runtime.harness.respond(input({
      requestId: "memory-confirm-request",
      sourceMessageId: "memory-confirm-message",
      message: "确认",
    }));
    expect(confirmed.memory).toMatchObject({
      status: "succeeded",
      acceptedCount: 1,
      decisions: [{ status: "inserted" }],
    });
    expect(fixture.memoryRepository.list()).toHaveLength(1);
    expect(fixture.fetcher).toHaveBeenCalledTimes(1);
  });

  test("remote text-only uses one per-Turn snapshot and keeps the credential out of response and context", async () => {
    const fixture = createFixture({ remote: true });
    fixture.setRemoteReply("remote-safe-reply");
    const response = await fixture.runtime.harness.respond(input({
      requestId: "remote-request",
      sourceMessageId: "remote-message",
      message: "普通聊天",
    }));
    expect(response).toMatchObject({
      status: "success",
      text: "remote-safe-reply",
      provider: { kind: "remote", target: "https://phase7.example.test/v1" },
      callCounts: { model: 1, external: 1, local: 0, fallback: 0 },
    });
    const requestBody = String(fixture.fetcher.mock.calls[0]?.[1]?.body ?? "");
    expect(requestBody).not.toContain("credential-sentinel");
    expect(JSON.stringify(response)).not.toContain("credential-sentinel");
    expect(requestBody).not.toContain("xiaoju-cat");
    expect(fixture.fetcher).toHaveBeenCalledTimes(1);
  });

  test("remote structured candidates are admitted only through the local domain gate", async () => {
    const fixture = createFixture({ remote: true });
    fixture.setRemoteReply(JSON.stringify({
      replyDraft: "模型说已创建",
      actions: [{
        sourceMessageId: "structured-message",
        intent: "explicit",
        type: "create_task",
        payload: { title: "不应绕过本地证据" },
      }],
    }));
    const response = await fixture.runtime.harness.respond(input({
      requestId: "structured-request",
      sourceMessageId: "structured-message",
      message: "普通聊天",
    }));
    expect(response.actions).toMatchObject([{ status: "rejected", errorCode: "missing-local-evidence" }]);
    expect(response.text).not.toContain("已经为你创建");
    expect(fixture.taskRepository.writes).toBe(0);
    expect(fixture.fetcher).toHaveBeenCalledTimes(1);
  });

  test("App send handler has no legacy orchestration or direct Provider send; connection test is the sole exception", () => {
    const source = readFileSync(resolve("src/App.tsx"), "utf8");
    const start = source.indexOf("const sendCompanionChatMessage");
    const end = source.indexOf("const retryCompanionChatMessage", start);
    const handler = source.slice(start, end);
    for (const forbidden of [
      "resolveCompanionChatPipelineRoute(",
      "assembleCompanionContext(",
      "provider.send(",
      "createLocalCompanionChatFallbackProvider(",
      "shouldFallbackToLocalCompanion(",
      "forgetRecentCompanionData(",
      "upsertCompanionPreference(",
      "setTaskPreference(",
    ]) {
      expect(handler).not.toContain(forbidden);
    }
    expect(source.match(/provider\.send\(/g)?.length ?? 0).toBe(1);
    expect(source).toContain("createCompanionChatProvider(config");
  });
});
