import { describe, expect, test, vi } from "vitest";
import { createCompanionHarness } from "./companionHarness";
import {
  createInMemoryCompanionTaskRepository,
} from "./companionActionPipeline";
import {
  createCompanionProactivePreferenceService,
} from "./companionProactivePreference";
import {
  createProactiveTriggerEngine,
  type ProactiveTaskCandidate,
  type ProactiveTriggerEngine,
} from "./proactiveTriggerEngine";
import type { ProactiveExpressionStorage } from "./proactiveExpressionGate";
import {
  createTask,
  EMPTY_TASK_DATABASE,
} from "../task-core/taskStore";
import type {
  CompanionInput,
  CompanionModelResponse,
  CompanionTaskRepository,
} from "./companionHarnessTypes";
import type {
  CompanionModelPort,
  CompanionModelPortInfo,
  HarnessModelRequest,
  ResolvedCompanionModelTurn,
} from "./companionModelPort";
import type { ProviderAdapter } from "./companionProviderAdapter";

const NOW = new Date("2026-08-11T12:00:00.000Z");
const REMOTE_INFO: CompanionModelPortInfo = {
  kind: "remote",
  provider: "Proactive Preference Fake Remote",
  target: "https://proactive-preference.invalid",
  disclosure: "远程模式",
};

function input(overrides: Partial<CompanionInput> = {}): CompanionInput {
  return {
    requestId: "preference-request-1",
    sessionId: "preference-session-1",
    sourceMessageId: "preference-message-1",
    userId: "local-user",
    petId: "xiaoju-cat",
    message: "别再提醒这件事",
    currentTime: NOW.toISOString(),
    timezone: "Asia/Shanghai",
    utcOffsetMinutes: 480,
    source: "chat",
    ...overrides,
  };
}

function storage(options: { failWrites?: boolean } = {}): ProactiveExpressionStorage & {
  readonly value: string | null;
  readonly getItem: ReturnType<typeof vi.fn>;
  readonly setItem: ReturnType<typeof vi.fn>;
  readonly setFailWrites: (value: boolean) => void;
} {
  let value: string | null = null;
  let failWrites = options.failWrites === true;
  const getItem = vi.fn(() => value);
  const setItem = vi.fn((_key: string, nextValue: string) => {
    if (failWrites) throw new Error("storage write failed");
    value = nextValue;
  });
  return {
    getItem,
    setItem,
    get value() {
      return value;
    },
    setFailWrites(nextValue: boolean) {
      failWrites = nextValue;
    },
  };
}

function storedPreference(
  stateStorage: { readonly value: string | null },
  taskId: string,
): { mode?: string; preferredPetId?: string | null } | undefined {
  if (!stateStorage.value) return undefined;
  const parsed = JSON.parse(stateStorage.value) as {
    taskState?: {
      preferences?: Record<string, { mode?: string; preferredPetId?: string | null }>;
    };
  };
  return parsed.taskState?.preferences?.[taskId];
}

function fakeModel() {
  let beginCalls = 0;
  let generateCalls = 0;
  const capabilities = Object.freeze({
    textGeneration: true as const,
    structuredOutput: "none" as const,
    cancellation: true,
    usageMetadata: false,
  });
  const adapter: ProviderAdapter = {
    id: REMOTE_INFO.provider,
    protocol: "openai-compatible",
    capabilities,
    info: REMOTE_INFO,
    generate: async () => ({
      text: "不应调用 Provider",
      metadata: { providerId: REMOTE_INFO.provider },
    }),
  };
  const resolved: ResolvedCompanionModelTurn = {
    adapter,
    info: REMOTE_INFO,
    capabilities,
    generate: async (_request: HarnessModelRequest): Promise<CompanionModelResponse> => {
      generateCalls += 1;
      return { replyDraft: "不应调用 Provider" };
    },
  };
  const port: CompanionModelPort = {
    info: REMOTE_INFO,
    beginTurn: () => {
      beginCalls += 1;
      return resolved;
    },
    generate: async () => {
      generateCalls += 1;
      return { replyDraft: "不应调用 Provider" };
    },
  };
  return {
    port,
    get beginCalls() {
      return beginCalls;
    },
    get generateCalls() {
      return generateCalls;
    },
  };
}

function taskDatabase(titles: readonly string[] = ["交报告"]): ReturnType<typeof createTask>["database"] {
  return titles.reduce((database, title, index) => createTask(database, {
    title,
    dueAt: `2026-08-${String(12 + index).padStart(2, "0")}T07:00:00.000Z`,
    schedulePrecision: "datetime",
    remindAt: `2026-08-${String(12 + index).padStart(2, "0")}T07:00:00.000Z`,
  }, "2026-08-11T08:00:00.000Z").database, EMPTY_TASK_DATABASE);
}

function deliveryCandidate(
  database: ReturnType<typeof taskDatabase>,
  index: number,
  title = database.tasks[index]!.title,
): ProactiveTaskCandidate {
  const task = database.tasks[index]!;
  const reminder = database.reminders.find((item) => item.taskId === task.id)!;
  const instance = database.reminderInstances.find((item) => item.taskId === task.id)!;
  return {
    taskId: task.id,
    reminderId: reminder.id,
    reminderInstanceId: instance.id,
    title,
    priority: task.priority,
    taskStatus: task.status,
    deletedAt: task.deletedAt,
    scheduledAt: NOW.toISOString(),
    triggeredAt: NOW.toISOString(),
    status: "triggered",
  };
}

function deliveredFixture(options: {
  titles?: readonly string[];
  availablePetIds?: readonly string[];
  deliver?: boolean;
  failWrites?: boolean;
} = {}) {
  const stateStorage = storage({ failWrites: options.failWrites });
  const database = taskDatabase(options.titles);
  const repository = createInMemoryCompanionTaskRepository(database);
  const triggerEngine = createProactiveTriggerEngine({
    storage: stateStorage,
    activePetId: "xiaoju-cat",
    availablePetIds: options.availablePetIds ?? ["xiaoju-cat", "black-cat"],
    quietHours: { startTime: "00:00", endTime: "00:01" },
  });
  if (options.deliver !== false) {
    const candidates = (options.titles ?? ["交报告"])
      .map((_, index) => deliveryCandidate(database, index));
    const evaluation = triggerEngine.evaluateEligibility(candidates, NOW);
    const eligible = evaluation.eligibleDeliveries[0];
    if (!eligible) throw new Error("test fixture expected an eligible delivery");
    const reservation = triggerEngine.reserveDelivery(eligible.decision, eligible.candidates, NOW);
    if (reservation.status !== "reserved") throw new Error("test fixture expected a reservation");
    const confirmation = triggerEngine.confirmDelivery(reservation, eligible.candidates, NOW);
    if (confirmation.status !== "confirmed") throw new Error("test fixture expected a confirmation");
  }
  const preferenceService = createCompanionProactivePreferenceService({
    repository,
    triggerEngine,
    activePetId: "xiaoju-cat",
    availablePetIds: options.availablePetIds ?? ["xiaoju-cat", "black-cat"],
  });
  return { stateStorage, database, repository, triggerEngine, preferenceService };
}

function harnessFor(
  model: ReturnType<typeof fakeModel>,
  repository: CompanionTaskRepository,
  preferenceService?: ReturnType<typeof createCompanionProactivePreferenceService>,
  responseSink?: Parameters<typeof createCompanionHarness>[0]["responseSink"],
) {
  return createCompanionHarness({
    modelPort: model.port,
    taskRepository: repository,
    ...(preferenceService ? { proactivePreferenceService: preferenceService } : {}),
    ...(responseSink ? { responseSink } : {}),
  });
}

describe("Companion Harness Phase 4 proactive preference ownership", () => {
  test.each([
    ["mute", "别再提醒这件事", "已经停止提醒"],
    ["reduce", "少提醒一点", "已经减少"],
    ["switch_pet", "换一只宠物提醒", "另一只宠物"],
  ] as const)("executes %s against the local preference fact source", async (action, message, phrase) => {
    const fixture = deliveredFixture();
    const model = fakeModel();
    const writesBefore = fixture.stateStorage.setItem.mock.calls.length;
    const response = await harnessFor(model, fixture.repository, fixture.preferenceService).respond(input({ message }));

    expect(response.status).toBe("success");
    expect(response.text).toContain(phrase);
    expect(response.actions).toEqual([]);
    expect(response.proactivePreference).toMatchObject({
      type: "proactive_preference",
      action,
      status: "succeeded",
    });
    expect(response.callCounts).toEqual({ model: 0, external: 0, local: 0, fallback: 0 });
    expect(model.beginCalls).toBe(0);
    expect(model.generateCalls).toBe(0);
    expect(fixture.repository.writes).toBe(0);
    expect(fixture.stateStorage.setItem).toHaveBeenCalledTimes(writesBefore + 1);
    expect(fixture.triggerEngine.getState(NOW).taskState?.preferences[fixture.database.tasks[0]!.id]).toMatchObject(
      action === "mute"
        ? { mode: "muted" }
        : action === "reduce"
          ? { mode: "reduced" }
          : { preferredPetId: "black-cat" },
    );
  });

  test("uses one recent delivery context for a unique untitled target and makes retries idempotent", async () => {
    const fixture = deliveredFixture();
    const model = fakeModel();
    const harness = harnessFor(model, fixture.repository, fixture.preferenceService);
    const first = await harness.respond(input({ requestId: "preference-request-1" }));
    const writesAfterFirst = fixture.stateStorage.setItem.mock.calls.length;
    const retry = await harness.respond(input({ requestId: "preference-request-2" }));

    expect(first.proactivePreference).toMatchObject({ status: "succeeded", action: "mute" });
    expect(retry.proactivePreference).toMatchObject({ status: "duplicate", action: "mute" });
    expect(retry.text).toContain("无需重复修改");
    expect(fixture.stateStorage.setItem).toHaveBeenCalledTimes(writesAfterFirst);
    expect(model.beginCalls).toBe(0);
    expect(model.generateCalls).toBe(0);
    expect(retry.callCounts.external).toBe(0);
  });

  test("returns ambiguous for multiple recent targets and confirmation for missing context", async () => {
    const multiple = deliveredFixture({ titles: ["交报告", "交报告给老板"] });
    const multipleModel = fakeModel();
    const multipleWrites = multiple.stateStorage.setItem.mock.calls.length;
    const multipleResponse = await harnessFor(
      multipleModel,
      multiple.repository,
      multiple.preferenceService,
    ).respond(input({ message: "少提醒一点" }));
    expect(multipleResponse.proactivePreference).toMatchObject({
      action: "reduce",
      status: "ambiguous",
    });
    expect(multipleResponse.text).toContain("多个");
    expect(multiple.stateStorage.setItem).toHaveBeenCalledTimes(multipleWrites);
    expect(multipleModel.beginCalls).toBe(0);

    const missing = deliveredFixture({ deliver: false });
    const missingModel = fakeModel();
    const missingResponse = await harnessFor(
      missingModel,
      missing.repository,
      missing.preferenceService,
    ).respond(input({ message: "少提醒一点" }));
    expect(missingResponse.proactivePreference).toMatchObject({
      action: "reduce",
      status: "confirmation_required",
    });
    expect(missingResponse.text).toContain("补充明确");
    expect(missing.stateStorage.setItem).not.toHaveBeenCalled();
    expect(missingModel.beginCalls).toBe(0);
  });

  test("returns not_found for an explicit missing target and confirmation when no pet can switch", async () => {
    const missing = deliveredFixture({ deliver: false });
    const missingModel = fakeModel();
    const missingResponse = await harnessFor(
      missingModel,
      missing.repository,
      missing.preferenceService,
    ).respond(input({ message: "别再提醒不存在的事项" }));
    expect(missingResponse.proactivePreference).toMatchObject({ status: "not_found" });
    expect(missingResponse.text).toContain("没有找到");
    expect(missingModel.beginCalls).toBe(0);

    const noSwitch = deliveredFixture({ availablePetIds: ["xiaoju-cat"] });
    const noSwitchModel = fakeModel();
    const noSwitchWrites = noSwitch.stateStorage.setItem.mock.calls.length;
    const noSwitchResponse = await harnessFor(
      noSwitchModel,
      noSwitch.repository,
      noSwitch.preferenceService,
    ).respond(input({ message: "换一只宠物提醒" }));
    expect(noSwitchResponse.proactivePreference).toMatchObject({ status: "confirmation_required" });
    expect(noSwitchResponse.text).toContain("可切换宠物");
    expect(noSwitch.stateStorage.setItem).toHaveBeenCalledTimes(noSwitchWrites);
    expect(noSwitchModel.beginCalls).toBe(0);
  });

  test("fails closed when the preference service is unavailable", async () => {
    const noService = deliveredFixture();
    const noServiceModel = fakeModel();
    const noServiceResponse = await harnessFor(noServiceModel, noService.repository).respond(input());
    expect(noServiceResponse.proactivePreference).toMatchObject({ status: "failed" });
    expect(noServiceResponse.text).toContain("没有保存成功");
    expect(noServiceModel.beginCalls).toBe(0);
    expect(noServiceModel.generateCalls).toBe(0);
    expect(noServiceResponse.callCounts).toEqual({ model: 0, external: 0, local: 0, fallback: 0 });
  });

  test("matrix A: aborts before the writer without invoking storage or Provider", async () => {
    const cancelled = deliveredFixture();
    const valueBefore = cancelled.stateStorage.value;
    const cancelledWrites = cancelled.stateStorage.setItem.mock.calls.length;
    const setPreference = vi.spyOn(cancelled.triggerEngine, "setTaskPreference");
    const controller = new AbortController();
    controller.abort();
    const cancelledModel = fakeModel();
    const cancelledResponse = await harnessFor(
      cancelledModel,
      cancelled.repository,
      cancelled.preferenceService,
    ).respond(input({ signal: controller.signal }));

    expect(cancelledResponse.status).toBe("cancelled");
    expect(cancelledResponse.error?.kind).toBe("cancelled");
    expect(cancelledResponse.proactivePreference).toMatchObject({
      type: "proactive_preference",
      status: "cancelled",
    });
    expect(cancelledResponse.committed).toBe(false);
    expect(setPreference).not.toHaveBeenCalled();
    expect(cancelled.stateStorage.setItem).toHaveBeenCalledTimes(cancelledWrites);
    expect(cancelled.stateStorage.value).toBe(valueBefore);
    expect(cancelledModel.beginCalls).toBe(0);
    expect(cancelledModel.generateCalls).toBe(0);
  });

  test("matrix B: reports failed when the real storage writer throws", async () => {
    const writeFailure = deliveredFixture();
    const valueBefore = writeFailure.stateStorage.value;
    const writesBefore = writeFailure.stateStorage.setItem.mock.calls.length;
    const setPreference = vi.spyOn(writeFailure.triggerEngine, "setTaskPreference");
    writeFailure.stateStorage.setFailWrites(true);
    const writeFailureModel = fakeModel();
    const writeFailureResponse = await harnessFor(
      writeFailureModel,
      writeFailure.repository,
      writeFailure.preferenceService,
    ).respond(input());

    expect(writeFailureResponse.status).toBe("degraded");
    expect(writeFailureResponse.proactivePreference).toMatchObject({ status: "failed" });
    expect(writeFailureResponse.text).toContain("没有保存成功");
    expect(writeFailureResponse.text).not.toContain("已经停止提醒");
    expect(writeFailureResponse.committed).toBe(false);
    expect(setPreference).toHaveBeenCalledTimes(1);
    expect(writeFailure.stateStorage.setItem).toHaveBeenCalledTimes(writesBefore + 1);
    expect(writeFailure.stateStorage.value).toBe(valueBefore);
    expect(writeFailureModel.beginCalls).toBe(0);
    expect(writeFailureModel.generateCalls).toBe(0);
    expect(writeFailureResponse.callCounts).toEqual({ model: 0, external: 0, local: 0, fallback: 0 });
  });

  test("matrix C: keeps a storage failure failed when the writer aborts in finally", async () => {
    const fixture = deliveredFixture();
    const valueBefore = fixture.stateStorage.value;
    const writesBefore = fixture.stateStorage.setItem.mock.calls.length;
    fixture.stateStorage.setFailWrites(true);
    const callerController = new AbortController();
    const baseEngine = fixture.triggerEngine;
    let writerCalls = 0;
    const abortingEngine: ProactiveTriggerEngine = {
      ...baseEngine,
      setTaskPreference(taskId, patch, now) {
        writerCalls += 1;
        try {
          return baseEngine.setTaskPreference(taskId, patch, now);
        } finally {
          callerController.abort();
        }
      },
    };
    const preferenceService = createCompanionProactivePreferenceService({
      repository: fixture.repository,
      triggerEngine: abortingEngine,
      activePetId: "xiaoju-cat",
      availablePetIds: ["xiaoju-cat", "black-cat"],
    });
    const model = fakeModel();
    const commits: string[] = [];
    const harness = harnessFor(model, fixture.repository, preferenceService, {
      commit: (_input, response, guard) => {
        guard.commitIfCurrent(_input, response, () => commits.push("committed"));
      },
    });
    const response = await harness.respond(input({ signal: callerController.signal }));

    expect(response.status).toBe("cancelled");
    expect(response.proactivePreference).toMatchObject({ status: "failed", action: "mute" });
    expect(response.committed).toBe(false);
    expect(response.text).toBeNull();
    expect(commits).toEqual([]);
    expect(writerCalls).toBe(1);
    expect(fixture.stateStorage.setItem).toHaveBeenCalledTimes(writesBefore + 1);
    expect(fixture.stateStorage.value).toBe(valueBefore);
    expect(response.callCounts).toEqual({ model: 0, external: 0, local: 0, fallback: 0 });
    expect(model.beginCalls).toBe(0);
    expect(model.generateCalls).toBe(0);
  });

  test("matrix D: preserves a confirmed write after late abort and matrix E: retries without another write", async () => {
    const fixture = deliveredFixture();
    const callerController = new AbortController();
    const baseEngine = fixture.triggerEngine;
    let writerCalls = 0;
    const abortingEngine: ProactiveTriggerEngine = {
      ...baseEngine,
      setTaskPreference(taskId, patch, now) {
        writerCalls += 1;
        const state = baseEngine.setTaskPreference(taskId, patch, now);
        callerController.abort();
        return state;
      },
    };
    const preferenceService = createCompanionProactivePreferenceService({
      repository: fixture.repository,
      triggerEngine: abortingEngine,
      activePetId: "xiaoju-cat",
      availablePetIds: ["xiaoju-cat", "black-cat"],
    });
    const model = fakeModel();
    const commits: string[] = [];
    const harness = harnessFor(model, fixture.repository, preferenceService, {
      commit: (_input, response, guard) => {
        guard.commitIfCurrent(_input, response, () => commits.push("committed"));
      },
    });
    const response = await harness.respond(input({ signal: callerController.signal }));

    expect(response.status).toBe("cancelled");
    expect(response.proactivePreference).toMatchObject({ status: "succeeded", action: "mute" });
    expect(response.committed).toBe(false);
    expect(response.text).toBeNull();
    expect(commits).toEqual([]);
    expect(writerCalls).toBe(1);
    expect(response.callCounts).toEqual({ model: 0, external: 0, local: 0, fallback: 0 });
    expect(storedPreference(fixture.stateStorage, fixture.database.tasks[0]!.id)).toMatchObject({
      mode: "muted",
    });
    expect(fixture.triggerEngine.getState(NOW).taskState?.preferences[fixture.database.tasks[0]!.id]).toMatchObject({
      mode: "muted",
    });
    expect(model.beginCalls).toBe(0);
    expect(model.generateCalls).toBe(0);

    const writesAfterFirst = fixture.stateStorage.setItem.mock.calls.length;
    const retry = await harness.respond(input({ requestId: "preference-late-retry" }));
    expect(retry.status).toBe("success");
    expect(retry.proactivePreference).toMatchObject({ status: "duplicate", action: "mute" });
    expect(fixture.stateStorage.setItem).toHaveBeenCalledTimes(writesAfterFirst);
    expect(storedPreference(fixture.stateStorage, fixture.database.tasks[0]!.id)).toMatchObject({
      mode: "muted",
    });
    expect(retry.callCounts).toEqual({ model: 0, external: 0, local: 0, fallback: 0 });
    expect(model.beginCalls).toBe(0);
    expect(model.generateCalls).toBe(0);
  });

  test("matrix F: keeps writer-confirmed success when verification read fails", async () => {
    const fixture = deliveredFixture();
    const baseEngine = fixture.triggerEngine;
    const setPreference = vi.spyOn(baseEngine, "setTaskPreference");
    let getStateCalls = 0;
    const readFailingEngine: ProactiveTriggerEngine = {
      ...baseEngine,
      getState(now) {
        getStateCalls += 1;
        if (getStateCalls > 1) throw new Error("verification read failed");
        return baseEngine.getState(now);
      },
    };
    const preferenceService = createCompanionProactivePreferenceService({
      repository: fixture.repository,
      triggerEngine: readFailingEngine,
      activePetId: "xiaoju-cat",
      availablePetIds: ["xiaoju-cat", "black-cat"],
    });
    const model = fakeModel();
    const response = await harnessFor(model, fixture.repository, preferenceService).respond(input());

    expect(response.status).toBe("success");
    expect(response.proactivePreference).toMatchObject({ status: "succeeded", action: "mute" });
    expect(setPreference).toHaveBeenCalledTimes(1);
    expect(fixture.stateStorage.setItem).toHaveBeenCalledTimes(4);
    expect(storedPreference(fixture.stateStorage, fixture.database.tasks[0]!.id)).toMatchObject({
      mode: "muted",
    });
    expect(fixture.triggerEngine.getState(NOW).taskState?.preferences[fixture.database.tasks[0]!.id]).toMatchObject({
      mode: "muted",
    });
    expect(model.beginCalls).toBe(0);
    expect(model.generateCalls).toBe(0);
  });
});
