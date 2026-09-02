import { describe, expect, test, vi } from "vitest";
import {
  createCompanionAppHarness,
  COMPANION_LOCAL_USER_ID,
  type CompanionAppHarnessSources,
} from "./companionAppHarness";
import { createCompanionHarness } from "./companionHarness";
import {
  createInMemoryCompanionTaskRepository,
} from "./companionActionPipeline";
import { createCompanionProactivePreferenceService } from "./companionProactivePreference";
import {
  createCompanionMemoryRepository,
  type MemoryRepository,
} from "./companionMemory";
import {
  EMPTY_COMPANION_PREFERENCES,
  type CompanionPreferencesState,
} from "./companionPreferences";
import {
  createCompanionObservationRecorder,
} from "./companionObservability";
import {
  createCompanionUserSettingsOwner,
  createCompanionUserSettingsRepository,
} from "./companionUserSettingsRepository";
import {
  getCompanionProviderProfilePreset,
  type CompanionProviderProfile,
} from "./companionProviderConfig";
import {
  createProactiveTriggerEngine,
  type ProactiveTaskCandidate,
} from "./proactiveTriggerEngine";
import type {
  CompanionEvent,
  CompanionInput,
  CompanionModelResponse,
  CompanionResponse,
  CompanionResponseSink,
  CompanionTaskRepository,
} from "./companionHarnessTypes";
import type {
  CompanionModelPort,
  CompanionModelPortInfo,
  HarnessModelRequest,
  ResolvedCompanionModelTurn,
} from "./companionModelPort";
import type {
  ProviderAdapter,
  ProviderHttpFetcher,
} from "./companionProviderAdapter";
import type { PetSoulPackage } from "./petSoul";
import {
  createTask,
  EMPTY_TASK_DATABASE,
} from "../task-core/taskStore";
import type { TaskDatabase } from "../task-core/types";

const NOW = "2026-08-11T12:00:00.000Z";
const REMOTE_CREDENTIAL = "PHASE8_CREDENTIAL_SENTINEL";

function input(overrides: Partial<CompanionInput> = {}): CompanionInput {
  return {
    requestId: "phase8-request-1",
    sessionId: "phase8-session-1",
    sourceMessageId: "phase8-message-1",
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

function createStorage() {
  const values = new Map<string, string>();
  return {
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      values.set(key, value);
    }),
  };
}

function createMemoryRepository(): MemoryRepository {
  let nextId = 0;
  return createCompanionMemoryRepository({
    storage: createStorage(),
    now: () => Date.parse(NOW),
    idGenerator: () => `phase8-memory-${nextId += 1}`,
  });
}

const LOCAL_INFO: CompanionModelPortInfo = {
  kind: "local",
  provider: "Phase 8 Local Fake",
  target: "本机",
  disclosure: "本地模式：不会发起网络请求。",
};

function fakeModelPort(
  info: CompanionModelPortInfo = LOCAL_INFO,
  replyDraft = "phase8-fake-reply",
): CompanionModelPort {
  const capabilities = Object.freeze({
    textGeneration: true as const,
    structuredOutput: "none" as const,
    cancellation: true,
    usageMetadata: false,
  });
  const adapter: ProviderAdapter = {
    id: info.kind === "local" ? "local" : "phase8-fake-provider",
    protocol: info.kind === "local" ? "local" : "openai-compatible",
    capabilities,
    info,
    generate: async () => ({
      text: replyDraft,
      metadata: { providerId: info.provider },
    }),
  };
  const resolved: ResolvedCompanionModelTurn = {
    adapter,
    info,
    capabilities,
    providerProfileId: adapter.id,
    protocol: adapter.protocol,
    generate: async (_request: HarnessModelRequest): Promise<CompanionModelResponse> => ({
      replyDraft,
    }),
  };
  return {
    info,
    beginTurn: () => resolved,
    generate: resolved.generate,
  };
}

function reminderDatabase(title = "交报告"): TaskDatabase {
  return createTask(EMPTY_TASK_DATABASE, {
    title,
    dueAt: "2026-08-12T07:00:00.000Z",
    schedulePrecision: "datetime",
    remindAt: "2026-08-12T07:00:00.000Z",
  }, "2026-08-11T08:00:00.000Z").database;
}

type AppFixture = {
  runtime: ReturnType<typeof createCompanionAppHarness>;
  taskRepository: CompanionTaskRepository & {
    readonly writes: number;
    setFailWrites(value: boolean): void;
  };
  memoryRepository: MemoryRepository;
  preferences: () => CompanionPreferencesState;
  commits: Array<{ input: CompanionInput; response: CompanionResponse }>;
  fetcher: ReturnType<typeof vi.fn<ProviderHttpFetcher>>;
  setRemoteReply(value: string): void;
};

function profileFor(
  id: "google-gemini" | "custom-provider",
): CompanionProviderProfile {
  const preset = getCompanionProviderProfilePreset(id);
  if (!preset) throw new Error(`missing Provider preset: ${id}`);
  return {
    ...preset,
    endpoint: id === "google-gemini"
      ? "https://phase8.example.test/v1beta"
      : "https://phase8.example.test/v1",
    model: "phase8-model",
  };
}

function createAppFixture(options: {
  remote?: boolean;
  providerId?: "google-gemini" | "custom-provider";
  fallback?: boolean;
  taskDatabase?: TaskDatabase;
  taskRepository?: CompanionTaskRepository & {
    readonly writes: number;
    setFailWrites(value: boolean): void;
  };
  memoryRepository?: MemoryRepository;
  fetcher?: ProviderHttpFetcher;
} = {}): AppFixture {
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
  let remoteReply = "phase8-remote-reply";
  const activePetId = "xiaoju-cat";
  const availablePetIds = ["xiaoju-cat", "ikun"];
  const taskRepository = options.taskRepository ?? createInMemoryCompanionTaskRepository(
    options.taskDatabase ?? EMPTY_TASK_DATABASE,
  );
  const memoryRepository = options.memoryRepository ?? createMemoryRepository();
  const triggerStorage = createStorage();
  const triggerEngine = createProactiveTriggerEngine({
    storage: triggerStorage,
    activePetId,
    availablePetIds,
  });
  const commits: Array<{ input: CompanionInput; response: CompanionResponse }> = [];
  const fetcher = vi.fn<ProviderHttpFetcher>(options.fetcher ?? (async (_url, init) => {
    const parsed = JSON.parse(init.body) as { contents?: unknown };
    const isGemini = Array.isArray(parsed.contents);
    return {
      ok: true,
      status: 200,
      json: async () => isGemini
        ? { candidates: [{ content: { parts: [{ text: remoteReply }] } }] }
        : { choices: [{ message: { content: remoteReply } }] },
    };
  }));
  const responseSink: CompanionResponseSink = {
    commit(nextInput, response, guard) {
      guard.commitIfCurrent(nextInput, response, () => {
        commits.push({ input: nextInput, response });
      });
    },
  };
  const sources: CompanionAppHarnessSources = {
    getProviderProfile: () => options.remote
      ? profileFor(options.providerId ?? "custom-provider")
      : (getCompanionProviderProfilePreset("local")!),
    getProviderCredential: () => options.remote ? REMOTE_CREDENTIAL : null,
    getFallbackToLocal: () => options.fallback === true,
    getActivePetId: () => activePetId,
    getAvailablePetIds: () => availablePetIds,
    getCompanionChatPackage: (petId) => ({
      status: "loaded",
      petId,
      config: {
        openers: [{ text: "喵？" }],
        localReplies: ["phase8-local-reply"],
        style: { maxReplyLength: 120 },
        systemPrompt: "phase8 local soul",
      },
    }),
    getPetSoul: (petId): PetSoulPackage => ({
      status: "loaded",
      petId,
      path: "SOUL.md",
      content: "phase8 local soul",
    }),
    getPreferences: () => settingsRepository.getSnapshot()?.preferences ?? null,
    getMemoryRepository: () => memoryRepository,
    getHistory: () => [],
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
    commits,
    fetcher,
    setRemoteReply: (value) => {
      remoteReply = value;
    },
  };
}

function expectZeroCallDomainResponse(response: CompanionResponse): void {
  expect(response.callCounts).toEqual({ model: 0, external: 0, local: 0, fallback: 0 });
}

describe("Companion Harness Phase 8 fixed acceptance", () => {
  test("Layer 1/2/3: normal chat, task, reminder, confirmation, retry, and cancel keep final text truthful", async () => {
    const fixture = createAppFixture();
    const normal = await fixture.runtime.harness.respond(input({
      requestId: "normal-request",
      sourceMessageId: "normal-message",
      message: "普通陪伴",
    }));
    expect(normal).toMatchObject({
      status: "success",
      text: expect.stringContaining("phase8-local-reply"),
      callCounts: { model: 1, external: 0, local: 1, fallback: 0 },
    });
    expect(fixture.taskRepository.writes).toBe(0);

    const task = await fixture.runtime.harness.respond(input({
      requestId: "task-request",
      sourceMessageId: "task-message",
      message: "明天交报告",
    }));
    expect(task.text).toContain("已经为你创建");
    expect(task.actions).toMatchObject([{ type: "create_task", status: "succeeded" }]);
    expectZeroCallDomainResponse(task);
    expect(fixture.taskRepository.read().tasks).toHaveLength(1);

    const taskRetry = await fixture.runtime.harness.respond(input({
      requestId: "task-retry-request",
      sourceMessageId: "task-message",
      message: "明天交报告",
    }));
    expect(taskRetry.text).toMatch(/没有重复创建|无需/u);
    expect(taskRetry.actions).toMatchObject([{ type: "create_task", status: "duplicate" }]);
    expectZeroCallDomainResponse(taskRetry);
    expect(fixture.taskRepository.writes).toBe(1);

    const reminderFixture = createAppFixture();
    const reminder = await reminderFixture.runtime.harness.respond(input({
      requestId: "reminder-request",
      sourceMessageId: "reminder-message",
      message: "明天下午三点提醒我交报告",
    }));
    expect(reminder.text).toContain("8/12 15:00");
    expect(reminder.actions).toMatchObject([{ type: "create_reminder", status: "succeeded" }]);
    expectZeroCallDomainResponse(reminder);
    expect(reminderFixture.taskRepository.read().reminders).toHaveLength(1);
    expect(reminderFixture.taskRepository.read().reminderInstances).toHaveLength(1);

    const confirmationFixture = createAppFixture();
    const pending = await confirmationFixture.runtime.harness.respond(input({
      requestId: "confirm-request",
      sourceMessageId: "confirm-message",
      message: "明天发布上线",
    }));
    expect(pending.text).not.toContain("已经为你创建");
    expect(pending.actions).toMatchObject([{ status: "confirmation_required" }]);
    expectZeroCallDomainResponse(pending);
    expect(confirmationFixture.taskRepository.writes).toBe(0);

    const cancelled = await confirmationFixture.runtime.harness.respond(input({
      requestId: "confirm-cancel-request",
      sourceMessageId: "confirm-cancel-message",
      message: "取消",
    }));
    expect(cancelled.text).toBe("好，我不记这条。");
    expect(cancelled.actions).toEqual([]);
    expectZeroCallDomainResponse(cancelled);
    expect(confirmationFixture.taskRepository.writes).toBe(0);
  });

  test("Layer 2: create, complete, reschedule, and forget use local domain facts only", async () => {
    const fixture = createAppFixture({ taskDatabase: reminderDatabase() });
    const updated = await fixture.runtime.harness.respond(input({
      requestId: "update-request",
      sourceMessageId: "update-message",
      message: "把交报告提醒改到明天下午四点",
    }));
    expect(updated.text).toContain("8/12 16:00");
    expect(updated.actions).toMatchObject([{ type: "update_reminder", status: "succeeded" }]);
    expectZeroCallDomainResponse(updated);
    expect(fixture.taskRepository.read().reminders[0]?.remindAt).toBe("2026-08-12T08:00:00.000Z");
    expect(fixture.taskRepository.read().reminderInstances).toHaveLength(2);

    const completed = await fixture.runtime.harness.respond(input({
      requestId: "complete-request",
      sourceMessageId: "complete-message",
      message: "完成任务：交报告",
    }));
    expect(completed.text).toContain("已经完成");
    expect(completed.actions).toMatchObject([{ type: "complete_task", status: "succeeded" }]);
    expectZeroCallDomainResponse(completed);
    expect(fixture.taskRepository.read().tasks[0]?.status).toBe("completed");
    expect(fixture.taskRepository.read().reminders[0]?.status).toBe("completed");

    const memoryFixture = createAppFixture();
    const remembered = await memoryFixture.runtime.harness.respond(input({
      requestId: "remember-request",
      sourceMessageId: "remember-message",
      message: "我喜欢桂花茶，请记住",
    }));
    expect(remembered.text).toContain("已经记住");
    expect(remembered.memory).toMatchObject({ status: "succeeded", acceptedCount: 1 });
    expectZeroCallDomainResponse(remembered);
    expect(memoryFixture.memoryRepository.list()).toHaveLength(1);

    const forgotten = await memoryFixture.runtime.harness.respond(input({
      requestId: "forget-request",
      sourceMessageId: "forget-message",
      message: "忘掉刚才这条",
    }));
    expect(forgotten.text).toBe("好，我忘掉刚才那条。");
    expect(forgotten.forget).toMatchObject({ status: "succeeded" });
    expectZeroCallDomainResponse(forgotten);
    expect(memoryFixture.memoryRepository.list().filter((entry) => entry.status === "active")).toEqual([]);
  });

  test("Layer 2: preference, conflict correction, and proactive preference do not enter the ModelPort", async () => {
    const fixture = createAppFixture();
    const preference = await fixture.runtime.harness.respond(input({
      requestId: "preference-request",
      sourceMessageId: "preference-message",
      message: "以后叫我阿星",
    }));
    expect(preference.text).toContain("这个称呼");
    expect(preference.preference).toMatchObject({ status: "succeeded" });
    expectZeroCallDomainResponse(preference);
    expect(fixture.preferences().preferences).toHaveLength(1);

    const memoryFixture = createAppFixture();
    const first = await memoryFixture.runtime.harness.respond(input({
      requestId: "conflict-first-request",
      sourceMessageId: "conflict-first-message",
      message: "我喜欢香菜，请记住",
    }));
    const second = await memoryFixture.runtime.harness.respond(input({
      requestId: "conflict-second-request",
      sourceMessageId: "conflict-second-message",
      message: "我不喜欢香菜，请记住",
    }));
    expect(first.text).toContain("已经记住");
    expect(second.text).toContain("已经记住");
    expectZeroCallDomainResponse(first);
    expectZeroCallDomainResponse(second);
    expect(memoryFixture.memoryRepository.list().filter((entry) => entry.status === "active")).toMatchObject([
      [{ content: "用户不喜欢香菜", status: "active" }][0],
    ]);

    const proactive = createAppFixture({ taskDatabase: reminderDatabase() });
    const task = proactive.taskRepository.read().tasks[0]!;
    const reminder = proactive.taskRepository.read().reminders[0]!;
    const instance = proactive.taskRepository.read().reminderInstances[0]!;
    const engine = createProactiveTriggerEngine({
      storage: createStorage(),
      activePetId: "xiaoju-cat",
      availablePetIds: ["xiaoju-cat", "ikun"],
    });
    const candidate: ProactiveTaskCandidate = {
      taskId: task.id,
      reminderId: reminder.id,
      reminderInstanceId: instance.id,
      title: task.title,
      priority: task.priority,
      taskStatus: task.status,
      deletedAt: task.deletedAt,
      scheduledAt: NOW,
      triggeredAt: NOW,
      status: "triggered",
    };
    const evaluation = engine.evaluateEligibility([candidate], new Date(NOW));
    const eligible = evaluation.eligibleDeliveries[0]!;
    const reservation = engine.reserveDelivery(eligible.decision, eligible.candidates, new Date(NOW));
    expect(reservation.status).toBe("reserved");
    if (reservation.status !== "reserved") return;
    expect(engine.confirmDelivery(reservation, eligible.candidates, new Date(NOW)).status).toBe("confirmed");

    const preferenceService = createCompanionProactivePreferenceService({
      repository: proactive.taskRepository,
      triggerEngine: engine,
      activePetId: "xiaoju-cat",
      availablePetIds: ["xiaoju-cat", "ikun"],
    });
    const response = await createCompanionHarness({
      modelPort: fakeModelPort(),
      taskRepository: proactive.taskRepository,
      proactivePreferenceService: preferenceService,
    }).respond(input({
      requestId: "proactive-preference-request",
      sourceMessageId: "proactive-preference-message",
      message: "别再提醒这件事",
    }));
    expect(response.text).toContain("已经停止提醒");
    expect(response.proactivePreference).toMatchObject({ action: "mute", status: "succeeded" });
    expectZeroCallDomainResponse(response);
  });

  test("Layer 2: stop and supersede prevent stale UI commits while preserving local facts", async () => {
    const releases: Array<(value: CompanionModelResponse) => void> = [];
    let calls = 0;
    const model = fakeModelPort({
      kind: "remote",
      provider: "phase8-delayed-remote",
      target: "phase8-delayed-remote",
      disclosure: "remote fixture",
    });
    const delayed: CompanionModelPort = {
      ...model,
      beginTurn: () => ({
        ...model.beginTurn(),
        providerProfileId: "phase8-delayed",
        protocol: "openai-compatible",
        generate: async () => {
          calls += 1;
          return new Promise<CompanionModelResponse>((resolve) => {
            releases.push(resolve);
          });
        },
      }),
    };
    const commits: string[] = [];
    const repository = createInMemoryCompanionTaskRepository();
    const harness = createCompanionHarness({
      modelPort: delayed,
      taskRepository: repository,
      responseSink: {
        commit: (_input, response, guard) => {
          guard.commitIfCurrent(_input, response, () => commits.push(response.text ?? ""));
        },
      },
    });

    const stoppedPromise = harness.respond(input({
      requestId: "stop-request",
      sourceMessageId: "stop-message",
      message: "普通陪伴",
    }));
    await Promise.resolve();
    harness.cancel("phase8-session-1", "stop-request");
    releases.shift()!({ replyDraft: "不应提交的停止回复" });
    const stopped = await stoppedPromise;
    expect(stopped.status).toBe("cancelled");
    expect(stopped.text).toBeNull();
    expect(stopped.committed).toBe(false);
    expect(commits).toEqual([]);
    expect(repository.writes).toBe(0);

    const supersededFirst = harness.respond(input({
      requestId: "superseded-first",
      sourceMessageId: "superseded-first-message",
      message: "第一条普通聊天",
    }));
    await Promise.resolve();
    const supersededSecond = harness.respond(input({
      requestId: "superseded-second",
      sourceMessageId: "superseded-second-message",
      message: "第二条普通聊天",
    }));
    await Promise.resolve();
    releases.shift()!({ replyDraft: "不应提交的第一条回复" });
    await Promise.resolve();
    releases.shift()!({ replyDraft: "第二条回复" });
    const [firstResult, secondResult] = await Promise.all([supersededFirst, supersededSecond]);
    expect(firstResult.status).toBe("discarded");
    expect(firstResult.text).toBeNull();
    expect(secondResult.text).toBe("第二条回复");
    expect(secondResult.committed).toBe(true);
    expect(commits).toEqual(["第二条回复"]);
    expect(calls).toBe(3);
  });

  test("fixed Chinese Task/Reminder corpus produces a machine-verifiable >=95% report", async () => {
    type CorpusCase = {
      name: string;
      message: string;
      action: string;
      initial: TaskDatabase;
      expectedText: string;
      verifyFact: (database: TaskDatabase) => boolean;
    };
    const corpus: CorpusCase[] = [
      { name: "create-task-report", message: "明天交报告", action: "create_task", initial: EMPTY_TASK_DATABASE, expectedText: "待办", verifyFact: (db) => db.tasks.length === 1 },
      { name: "create-task-milk", message: "后天买牛奶", action: "create_task", initial: EMPTY_TASK_DATABASE, expectedText: "待办", verifyFact: (db) => db.tasks.length === 1 },
      { name: "create-task-desk", message: "明天整理桌面", action: "create_task", initial: EMPTY_TASK_DATABASE, expectedText: "待办", verifyFact: (db) => db.tasks.length === 1 },
      { name: "create-task-speech", message: "下周一准备演讲", action: "create_task", initial: EMPTY_TASK_DATABASE, expectedText: "待办", verifyFact: (db) => db.tasks.length === 1 },
      { name: "create-reminder-report", message: "明天下午三点提醒我交报告", action: "create_reminder", initial: EMPTY_TASK_DATABASE, expectedText: "提醒", verifyFact: (db) => db.reminders.length === 1 && db.reminderInstances.length === 1 },
      { name: "create-reminder-milk", message: "明天早上八点提醒我买牛奶", action: "create_reminder", initial: EMPTY_TASK_DATABASE, expectedText: "提醒", verifyFact: (db) => db.reminders.length === 1 && db.reminderInstances.length === 1 },
      { name: "create-reminder-call", message: "今天晚上十一点提醒我回复电话", action: "create_reminder", initial: EMPTY_TASK_DATABASE, expectedText: "提醒", verifyFact: (db) => db.reminders.length === 1 && db.reminderInstances.length === 1 },
      { name: "create-reminder-meeting", message: "下周一上午十点提醒我开会", action: "create_reminder", initial: EMPTY_TASK_DATABASE, expectedText: "提醒", verifyFact: (db) => db.reminders.length === 1 && db.reminderInstances.length === 1 },
      { name: "complete-report", message: "完成任务：交报告", action: "complete_task", initial: reminderDatabase(), expectedText: "已经完成", verifyFact: (db) => db.tasks[0]?.status === "completed" },
      { name: "complete-milk", message: "完成买牛奶", action: "complete_task", initial: reminderDatabase("买牛奶"), expectedText: "已经完成", verifyFact: (db) => db.tasks[0]?.status === "completed" },
      { name: "update-report", message: "把交报告提醒改到明天下午四点", action: "update_reminder", initial: reminderDatabase(), expectedText: "提醒改到", verifyFact: (db) => db.reminders[0]?.remindAt === "2026-08-12T08:00:00.000Z" },
      { name: "update-milk", message: "把买牛奶提醒改到明天早上九点", action: "update_reminder", initial: reminderDatabase("买牛奶"), expectedText: "提醒改到", verifyFact: (db) => db.reminders[0]?.remindAt === "2026-08-12T01:00:00.000Z" },
      { name: "cancel-report", message: "取消任务：交报告", action: "cancel_task", initial: reminderDatabase(), expectedText: "已经取消", verifyFact: (db) => db.tasks[0]?.status === "cancelled" },
      { name: "cancel-milk", message: "取消买牛奶", action: "cancel_task", initial: reminderDatabase("买牛奶"), expectedText: "已经取消", verifyFact: (db) => db.tasks[0]?.status === "cancelled" },
      { name: "postpone-report", message: "延期交报告到明天下午四点", action: "postpone_task", initial: reminderDatabase(), expectedText: "延期到", verifyFact: (db) => db.tasks[0]?.dueAt === "2026-08-12T08:00:00.000Z" },
      { name: "postpone-milk", message: "延期买牛奶到明天早上九点", action: "postpone_task", initial: reminderDatabase("买牛奶"), expectedText: "延期到", verifyFact: (db) => db.tasks[0]?.dueAt === "2026-08-12T01:00:00.000Z" },
      { name: "reschedule-report", message: "把交报告改到明天下午四点", action: "reschedule_task", initial: reminderDatabase(), expectedText: "改期到", verifyFact: (db) => db.tasks[0]?.dueAt === "2026-08-12T08:00:00.000Z" },
      { name: "reschedule-milk", message: "把买牛奶改到明天早上九点", action: "reschedule_task", initial: reminderDatabase("买牛奶"), expectedText: "改期到", verifyFact: (db) => db.tasks[0]?.dueAt === "2026-08-12T01:00:00.000Z" },
      { name: "create-task-form", message: "明天下午四点提交表格", action: "create_task", initial: EMPTY_TASK_DATABASE, expectedText: "待办", verifyFact: (db) => db.tasks.length === 1 },
      { name: "create-task-test", message: "下周五完成测试", action: "create_task", initial: EMPTY_TASK_DATABASE, expectedText: "待办", verifyFact: (db) => db.tasks.length === 1 },
    ];

    const rows: Array<Record<string, unknown>> = [];
    for (const [index, testCase] of corpus.entries()) {
      const repository = createInMemoryCompanionTaskRepository(testCase.initial);
      const harness = createCompanionHarness({
        modelPort: fakeModelPort(),
        taskRepository: repository,
      });
      const response = await harness.respond(input({
        requestId: `corpus-request-${index}`,
        sourceMessageId: `corpus-message-${index}`,
        message: testCase.message,
      }));
      const action = response.actions[0];
      rows.push({
        name: testCase.name,
        action: action?.type ?? null,
        actionStatus: action?.status ?? null,
        finalTextPresent: Boolean(response.text?.includes(testCase.expectedText)),
        domainFactPresent: testCase.verifyFact(repository.read()),
        externalCalls: response.callCounts.external,
        writes: repository.writes,
      });
    }
    const passed = rows.filter((row, index) =>
      row.action === corpus[index]?.action
      && row.actionStatus === "succeeded"
      && row.finalTextPresent === true
      && row.domainFactPresent === true
      && row.externalCalls === 0
      && row.writes === 1,
    );
    const report = {
      corpusVersion: "phase8-cn-task-reminder-v1",
      total: rows.length,
      passed: passed.length,
      failed: rows.length - passed.length,
      successRate: passed.length / rows.length,
      rows,
    };
    expect(report.total).toBe(20);
    expect(report.successRate).toBeGreaterThanOrEqual(0.95);
    expect(report.failed).toBe(0);
    expect(report.rows).toHaveLength(report.total);
  });

  test.each(["google-gemini", "custom-provider"] as const)(
    "remote zero-out matrix for %s excludes Task/Reminder projections, tombstones, outbox, and credentials",
    async (providerId) => {
      const baseDatabase = reminderDatabase("TASK_ZERO_OUT_TITLE");
      const sentinelDatabase: TaskDatabase = {
        ...baseDatabase,
        tasks: baseDatabase.tasks.map((task) => ({
          ...task,
          note: "TASK_PROJECTION_ZERO_OUT",
        })),
        reminders: baseDatabase.reminders.map((reminder) => ({
          ...reminder,
          id: "REMINDER_ZERO_OUT",
        })),
        reminderInstances: baseDatabase.reminderInstances.map((instance) => ({
          ...instance,
          id: "REMINDER_INSTANCE_ZERO_OUT",
          reminderId: "REMINDER_ZERO_OUT",
        })),
      };
      const taskRepository: AppFixture["taskRepository"] = {
        read: vi.fn(() => sentinelDatabase),
        write: vi.fn(() => false),
        get writes() {
          return 0;
        },
        setFailWrites: () => {},
      };
      const storage = createStorage();
      const memoryRepository = createCompanionMemoryRepository({ storage, now: () => Date.parse(NOW) });
      memoryRepository.save({
        scope: "global",
        type: "fact",
        content: "MEMORY_ZERO_OUT_CONTENT",
        source: "explicit",
        evidence: "MEMORY_ZERO_OUT_EVIDENCE",
        sourceMessageId: "memory-zero-out-message",
        confidence: 1,
        expiresAt: null,
        status: "active",
        supersedesId: null,
      });
      const fixture = createAppFixture({
        remote: true,
        providerId,
        taskRepository,
        memoryRepository,
      });
      const response = await fixture.runtime.harness.respond(input({
        requestId: `zero-out-${providerId}`,
        sourceMessageId: `zero-out-message-${providerId}`,
        message: "我想和你聊聊天气",
      }));
      expect(response).toMatchObject({
        status: "success",
        callCounts: { model: 1, external: 1, local: 0, fallback: 0 },
      });
      const body = String(fixture.fetcher.mock.calls[0]?.[0] ?? "")
        + String(fixture.fetcher.mock.calls[0]?.[1]?.body ?? "");
      expect(body).not.toContain(REMOTE_CREDENTIAL);
      for (const sentinel of [
        "TASK_ZERO_OUT_TITLE",
        "TASK_PROJECTION_ZERO_OUT",
        "TASK_TOMBSTONE_ZERO_OUT",
        "REMINDER_ZERO_OUT",
        "REMINDER_INSTANCE_ZERO_OUT",
        "OUTBOX_ZERO_OUT",
        "CURRENT_TIME_ZERO_OUT",
        "TIMEZONE_ZERO_OUT",
        "MEMORY_ZERO_OUT_CONTENT",
        "MEMORY_ZERO_OUT_EVIDENCE",
      ]) {
        expect(body).not.toContain(sentinel);
      }
      expect(fixture.fetcher).toHaveBeenCalledTimes(1);
      expect(taskRepository.read).not.toHaveBeenCalled();
      expect(memoryRepository.list()).toHaveLength(1);
    },
  );

  test("remote sensitive input, 401/403/429/5xx/network/malformed, and fallback are classified without retry or secret echo", async () => {
    const sensitive = createAppFixture({ remote: true });
    const sensitiveResponse = await sensitive.runtime.harness.respond(input({
      requestId: "sensitive-request",
      sourceMessageId: "sensitive-message",
      message: "我的密码是 PHASE8_SECRET_INPUT_SENTINEL",
    }));
    expect(sensitiveResponse.status).toBe("error");
    expect(sensitiveResponse.error?.kind).toBe("content-safety");
    expect(sensitiveResponse.text).toBeNull();
    expect(sensitive.fetcher).not.toHaveBeenCalled();
    expect(JSON.stringify(sensitiveResponse)).not.toContain("PHASE8_SECRET_INPUT_SENTINEL");

    const errorCases = [
      [401, "authentication"],
      [403, "authentication"],
      [429, "rate-limit"],
      [500, "server"],
    ] as const;
    for (const [status, kind] of errorCases) {
      const fixture = createAppFixture({
        remote: true,
        fetcher: async () => ({
          ok: false,
          status,
          json: async () => ({ error: { message: "PHASE8_PROVIDER_DETAIL_SENTINEL" } }),
        }),
      });
      const response = await fixture.runtime.harness.respond(input({
        requestId: `error-${status}-request`,
        sourceMessageId: `error-${status}-message`,
        message: "普通远程聊天",
      }));
      expect(response.status).toBe("error");
      expect(response.error?.kind).toBe(kind);
      expect(response.callCounts).toEqual({ model: 1, external: 1, local: 0, fallback: 0 });
      expect(fixture.fetcher).toHaveBeenCalledTimes(1);
      expect(JSON.stringify(response)).not.toContain("PHASE8_PROVIDER_DETAIL_SENTINEL");
    }

    const malformed = createAppFixture({
      remote: true,
      fetcher: async () => ({ ok: true, status: 200, json: async () => ({ choices: [] }) }),
    });
    const malformedResponse = await malformed.runtime.harness.respond(input({
      requestId: "malformed-request",
      sourceMessageId: "malformed-message",
      message: "普通远程聊天",
    }));
    expect(malformedResponse.status).toBe("error");
    expect(malformedResponse.error?.kind).toBe("malformed-response");
    expect(malformed.fetcher).toHaveBeenCalledTimes(1);

    const network = createAppFixture({
      remote: true,
      fetcher: async () => {
        throw new Error("PHASE8_NETWORK_DETAIL_SENTINEL");
      },
    });
    const networkResponse = await network.runtime.harness.respond(input({
      requestId: "network-request",
      sourceMessageId: "network-message",
      message: "普通远程聊天",
    }));
    expect(networkResponse.error?.kind).toBe("network");
    expect(network.fetcher).toHaveBeenCalledTimes(1);
    expect(JSON.stringify(networkResponse)).not.toContain("PHASE8_NETWORK_DETAIL_SENTINEL");

    const fallback = createAppFixture({
      remote: true,
      fallback: true,
      fetcher: async () => {
        throw new Error("fallback-network-detail");
      },
    });
    const fallbackResponse = await fallback.runtime.harness.respond(input({
      requestId: "fallback-request",
      sourceMessageId: "fallback-message",
      message: "普通远程聊天",
    }));
    expect(fallbackResponse).toMatchObject({
      status: "degraded",
      text: expect.stringContaining("phase8-local-reply"),
      callCounts: { model: 2, external: 1, local: 1, fallback: 1 },
      degradedFrom: "network",
    });
    expect(fallback.fetcher).toHaveBeenCalledTimes(1);
    expect(JSON.stringify(fallbackResponse)).not.toContain(REMOTE_CREDENTIAL);
  });

  test("remote structured candidates cannot override local domain facts, and observability remains allowlisted", async () => {
    const fixture = createAppFixture({ remote: true });
    fixture.setRemoteReply(JSON.stringify({
      replyDraft: "模型声称已经创建",
      actions: [{
        sourceMessageId: "provider-lie-message",
        intent: "explicit",
        type: "create_task",
        payload: { title: "PROVIDER_LIE_TASK_TITLE" },
      }],
    }));
    const response = await fixture.runtime.harness.respond(input({
      requestId: "provider-lie-request",
      sourceMessageId: "provider-lie-message",
      message: "普通远程聊天",
    }));
    expect(response.actions).toMatchObject([{ status: "rejected", errorCode: "missing-local-evidence" }]);
    expect(response.text).not.toContain("已经为你创建");
    expect(fixture.taskRepository.writes).toBe(0);
    expect(fixture.fetcher).toHaveBeenCalledTimes(1);
    expect(JSON.stringify(response)).not.toContain("PROVIDER_LIE_TASK_TITLE");
    expect(JSON.stringify(fixture.runtime.observability)).not.toContain(REMOTE_CREDENTIAL);
  });

  test("proactive events forward opaque local events without resolving ModelPort", async () => {
    const recorder = createCompanionObservationRecorder();
    const service = { handleEvent: vi.fn(async (_event: CompanionEvent) => undefined) };
    const model = {
      ...fakeModelPort({
        kind: "remote",
        provider: "phase8-proactive-remote",
        target: "phase8-proactive-remote",
        disclosure: "remote fixture",
      }),
      beginTurn: vi.fn(() => {
        throw new Error("proactive must not resolve model");
      }),
    } satisfies CompanionModelPort;
    const harness = createCompanionHarness({
      modelPort: model,
      proactiveEventService: service,
      observability: recorder,
    });
    await harness.handleEvent({
      id: "phase8-event-1",
      type: "TASK_DUE_SOON",
      taskId: "task-opaque-1",
      minutesLeft: 10,
    });
    await harness.handleEvent({ id: "phase8-invalid-event", type: "NOT_ALLOWED" } as never);
    expect(service.handleEvent).toHaveBeenCalledTimes(1);
    expect(model.beginTurn).not.toHaveBeenCalled();
    expect(recorder.snapshot()).toEqual([
      { kind: "proactive", eventType: "TASK_DUE_SOON", decision: "forwarded" },
      { kind: "proactive", eventType: "unknown", decision: "invalid" },
    ]);
  });
});
