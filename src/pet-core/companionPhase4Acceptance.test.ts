import { describe, expect, test } from "vitest";
import { createCompanionHarness } from "./companionHarness";
import {
  buildLocalRequestHints,
  createInMemoryCompanionTaskRepository,
} from "./companionActionPipeline";
import {
  completeTask,
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

const NOW = "2026-08-11T12:00:00.000Z";
const REMOTE_INFO: CompanionModelPortInfo = {
  kind: "remote",
  provider: "Phase 4 Acceptance Fake Remote",
  target: "https://phase4-acceptance.invalid",
  disclosure: "远程模式",
};

function input(overrides: Partial<CompanionInput> = {}): CompanionInput {
  return {
    requestId: "acceptance-request-1",
    sessionId: "acceptance-session-1",
    sourceMessageId: "acceptance-message-1",
    userId: "local-user",
    petId: "xiaoju-cat",
    message: "明天交报告",
    currentTime: NOW,
    timezone: "Asia/Shanghai",
    utcOffsetMinutes: 480,
    source: "chat",
    ...overrides,
  };
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

function databaseWithReminder() {
  return createTask(EMPTY_TASK_DATABASE, {
    title: "交报告",
    dueAt: "2026-08-12T07:00:00.000Z",
    schedulePrecision: "datetime",
    remindAt: "2026-08-12T07:00:00.000Z",
  }, "2026-08-11T08:00:00.000Z").database;
}

type AcceptanceCase = {
  name: string;
  message: string;
  action: string;
  initial: ReturnType<typeof databaseWithReminder>;
  expectedText: string;
  expectedDisplay?: string;
  assertDatabase(database: ReturnType<typeof databaseWithReminder>): void;
};

const cases: AcceptanceCase[] = [
  {
    name: "create_task",
    message: "明天交报告",
    action: "create_task",
    initial: EMPTY_TASK_DATABASE,
    expectedText: "待办",
    assertDatabase: (database) => {
      expect(database.tasks).toHaveLength(1);
      expect(database.reminders).toHaveLength(0);
      expect(database.reminderInstances).toHaveLength(0);
    },
  },
  {
    name: "create_reminder",
    message: "明天下午三点提醒我交报告",
    action: "create_reminder",
    initial: EMPTY_TASK_DATABASE,
    expectedText: "提醒",
    expectedDisplay: "8/12 15:00",
    assertDatabase: (database) => {
      expect(database.tasks).toHaveLength(1);
      expect(database.reminders).toHaveLength(1);
      expect(database.reminders[0]?.remindAt).toBe("2026-08-12T07:00:00.000Z");
      expect(database.reminderInstances).toHaveLength(1);
    },
  },
  {
    name: "complete_task",
    message: "完成任务：交报告",
    action: "complete_task",
    initial: databaseWithReminder(),
    expectedText: "已经完成",
    assertDatabase: (database) => {
      expect(database.tasks[0]?.status).toBe("completed");
      expect(database.reminders[0]?.status).toBe("completed");
      expect(database.reminderInstances[0]?.status).toBe("completed");
    },
  },
  {
    name: "update_reminder",
    message: "把交报告提醒改到明天下午四点",
    action: "update_reminder",
    initial: databaseWithReminder(),
    expectedText: "提醒改到",
    expectedDisplay: "8/12 16:00",
    assertDatabase: (database) => {
      expect(database.tasks).toHaveLength(1);
      expect(database.reminders).toHaveLength(1);
      expect(database.reminders[0]?.remindAt).toBe("2026-08-12T08:00:00.000Z");
      expect(database.reminderInstances).toHaveLength(2);
    },
  },
  {
    name: "cancel_task",
    message: "取消任务：交报告",
    action: "cancel_task",
    initial: databaseWithReminder(),
    expectedText: "已经取消",
    assertDatabase: (database) => {
      expect(database.tasks[0]?.status).toBe("cancelled");
      expect(database.reminders[0]?.status).toBe("cancelled");
      expect(database.reminderInstances[0]?.status).toBe("cancelled");
    },
  },
  {
    name: "postpone_task",
    message: "延期交报告到明天下午四点",
    action: "postpone_task",
    initial: databaseWithReminder(),
    expectedText: "延期到",
    expectedDisplay: "8/12 16:00",
    assertDatabase: (database) => {
      expect(database.tasks[0]?.dueAt).toBe("2026-08-12T08:00:00.000Z");
      expect(database.tasks[0]?.postponedCount).toBe(1);
      expect(database.reminderInstances).toHaveLength(2);
    },
  },
  {
    name: "reschedule_task",
    message: "把交报告改到明天下午四点",
    action: "reschedule_task",
    initial: databaseWithReminder(),
    expectedText: "改期到",
    expectedDisplay: "8/12 16:00",
    assertDatabase: (database) => {
      expect(database.tasks[0]?.dueAt).toBe("2026-08-12T08:00:00.000Z");
      expect(database.reminderInstances).toHaveLength(2);
    },
  },
];

describe("Companion Harness Phase 4 joint Action acceptance", () => {
  test.each(cases)("$name asserts final text, domain fact, calls, idempotency, and write count", async (testCase) => {
    const repository = createInMemoryCompanionTaskRepository(testCase.initial);
    const model = fakeModel();
    const harness = createCompanionHarness({
      modelPort: model.port,
      taskRepository: repository,
    });
    const first = await harness.respond(input({
      message: testCase.message,
      requestId: `${testCase.name}-request-1`,
      sourceMessageId: `${testCase.name}-message-1`,
    }));
    const writesAfterFirst = repository.writes;
    const retry = await harness.respond(input({
      message: testCase.message,
      requestId: `${testCase.name}-request-2`,
      sourceMessageId: `${testCase.name}-message-1`,
    }));

    expect(first.text).toContain(testCase.expectedText);
    if (testCase.expectedDisplay) expect(first.text).toContain(testCase.expectedDisplay);
    expect(first.actions).toHaveLength(1);
    expect(first.actions[0]).toMatchObject({ type: testCase.action, status: "succeeded" });
    expect(first.callCounts).toEqual({ model: 0, external: 0, local: 0, fallback: 0 });
    expect(model.beginCalls).toBe(0);
    expect(model.generateCalls).toBe(0);
    expect(writesAfterFirst).toBe(1);
    testCase.assertDatabase(repository.read());

    expect(retry.actions).toHaveLength(1);
    expect(retry.actions[0]?.type).toBe(testCase.action);
    expect(retry.actions[0]?.status).toBe("duplicate");
    expect(retry.text).toMatch(/无需|没有重复创建|时间未发生变化/u);
    expect(repository.writes).toBe(1);
    expect(retry.callCounts).toEqual({ model: 0, external: 0, local: 0, fallback: 0 });
    expect(model.beginCalls).toBe(0);
    expect(model.generateCalls).toBe(0);
  });

  test.each(cases)("$name does not write before cancellation and blocks late UI commit after a real write", async (testCase) => {
    const cancelledRepository = createInMemoryCompanionTaskRepository(testCase.initial);
    const cancelledModel = fakeModel();
    const controller = new AbortController();
    controller.abort();
    const cancelled = await createCompanionHarness({
      modelPort: cancelledModel.port,
      taskRepository: cancelledRepository,
    }).respond(input({
      message: testCase.message,
      requestId: `${testCase.name}-cancel-before-request`,
      sourceMessageId: `${testCase.name}-cancel-before-message`,
      signal: controller.signal,
    }));
    expect(cancelled.status).toBe("cancelled");
    expect(cancelled.text).toBeNull();
    expect(cancelled.actions).toMatchObject([{ type: testCase.action, status: "cancelled" }]);
    expect(cancelledRepository.writes).toBe(0);
    expect(cancelledModel.beginCalls).toBe(0);
    expect(cancelledModel.generateCalls).toBe(0);

    const lateController = new AbortController();
    let current = testCase.initial;
    let writes = 0;
    const lateRepository: CompanionTaskRepository = {
      read: () => current,
      write: (database) => {
        current = database;
        writes += 1;
        lateController.abort();
        return true;
      },
    };
    const lateModel = fakeModel();
    const commits: string[] = [];
    const lateResponse = await createCompanionHarness({
      modelPort: lateModel.port,
      taskRepository: lateRepository,
      responseSink: {
        commit: (_input, response, guard) => {
          guard.commitIfCurrent(_input, response, () => commits.push("late-commit"));
        },
      },
    }).respond(input({
      message: testCase.message,
      requestId: `${testCase.name}-late-request`,
      sourceMessageId: `${testCase.name}-late-message`,
      signal: lateController.signal,
    }));

    expect(lateResponse.status).toBe("cancelled");
    expect(lateResponse.committed).toBe(false);
    expect(lateResponse.actions).toMatchObject([{ type: testCase.action, status: "succeeded" }]);
    expect(writes).toBe(1);
    expect(commits).toEqual([]);
    expect(lateModel.beginCalls).toBe(0);
    expect(lateModel.generateCalls).toBe(0);
    testCase.assertDatabase(current);
  });

  test("does not treat a model-equivalent Action as a second owner", async () => {
    const repository = createInMemoryCompanionTaskRepository(EMPTY_TASK_DATABASE);
    const model = fakeModel();
    const harness = createCompanionHarness({ modelPort: model.port, taskRepository: repository });
    const response = await harness.respond(input({
      message: "明天下午三点提醒我交报告",
      requestId: "equivalent-request",
      sourceMessageId: "equivalent-message",
    }));

    expect(response.actions).toMatchObject([{ type: "create_reminder", status: "succeeded" }]);
    expect(repository.writes).toBe(1);
    expect(repository.read().tasks).toHaveLength(1);
    expect(repository.read().reminders).toHaveLength(1);
    expect(repository.read().reminderInstances).toHaveLength(1);
    expect(model.beginCalls).toBe(0);
    expect(model.generateCalls).toBe(0);
  });

  test("freezes local date parsing across Shanghai, UTC, and a negative offset", async () => {
    const shanghai = input({
      message: "明天下午四点提醒我交报告",
      requestId: "timezone-shanghai-request",
      sourceMessageId: "timezone-shanghai-message",
    });
    const shanghaiHints = buildLocalRequestHints(shanghai);
    expect(shanghaiHints.route.kind).toBe("task-candidate");
    if (shanghaiHints.route.kind !== "task-candidate") return;
    expect(shanghaiHints.route.candidate).toMatchObject({
      dueAt: "2026-08-12T08:00:00.000Z",
      remindAt: "2026-08-12T08:00:00.000Z",
      timezoneOffsetMinutes: -480,
    });

    const utc = input({
      message: "明天下午四点提醒我交报告",
      currentTime: NOW,
      timezone: "UTC",
      utcOffsetMinutes: 0,
      requestId: "timezone-utc-request",
      sourceMessageId: "timezone-utc-message",
    });
    const utcHints = buildLocalRequestHints(utc);
    expect(utcHints.route.kind).toBe("task-candidate");
    if (utcHints.route.kind !== "task-candidate") return;
    expect(utcHints.route.candidate).toMatchObject({
      dueAt: "2026-08-12T16:00:00.000Z",
      remindAt: "2026-08-12T16:00:00.000Z",
      timezoneOffsetMinutes: 0,
    });

    const losAngelesToday = input({
      message: "今天晚上十一点提醒我买牛奶",
      currentTime: "2026-08-12T06:30:00.000Z",
      timezone: "America/Los_Angeles",
      utcOffsetMinutes: -420,
      requestId: "timezone-la-today-request",
      sourceMessageId: "timezone-la-today-message",
    });
    const todayHints = buildLocalRequestHints(losAngelesToday);
    expect(todayHints.route.kind).toBe("task-candidate");
    if (todayHints.route.kind !== "task-candidate") return;
    expect(todayHints.route.candidate).toMatchObject({
      dueAt: "2026-08-12T06:00:00.000Z",
      remindAt: "2026-08-12T06:00:00.000Z",
      timezoneOffsetMinutes: 420,
    });
    const todayRepository = createInMemoryCompanionTaskRepository();
    const todayResponse = await createCompanionHarness({
      modelPort: fakeModel().port,
      taskRepository: todayRepository,
    }).respond(losAngelesToday);
    expect(todayResponse.actions).toMatchObject([{ status: "rejected", errorCode: "past-time" }]);
    expect(todayRepository.writes).toBe(0);

    const losAngelesDateOnly = input({
      message: "明天交报告",
      currentTime: "2026-08-12T06:30:00.000Z",
      timezone: "America/Los_Angeles",
      utcOffsetMinutes: -420,
      requestId: "timezone-la-date-only-request",
      sourceMessageId: "timezone-la-date-only-message",
    });
    const dateOnlyHints = buildLocalRequestHints(losAngelesDateOnly);
    expect(dateOnlyHints.route.kind).toBe("task-candidate");
    if (dateOnlyHints.route.kind !== "task-candidate") return;
    expect(dateOnlyHints.route.candidate).toMatchObject({
      dueAt: "2026-08-12",
      timezoneOffsetMinutes: 420,
    });
    const dateOnlyRepository = createInMemoryCompanionTaskRepository();
    const dateOnlyResponse = await createCompanionHarness({
      modelPort: fakeModel().port,
      taskRepository: dateOnlyRepository,
    }).respond(losAngelesDateOnly);
    expect(dateOnlyResponse.actions).toMatchObject([{ type: "create_task", status: "succeeded" }]);
    expect(dateOnlyRepository.read().tasks[0]?.dueAt).toBe("2026-08-12");

    const losAngelesTomorrow = input({
      message: "明天早上八点提醒我交报告",
      currentTime: "2026-08-12T06:30:00.000Z",
      timezone: "America/Los_Angeles",
      utcOffsetMinutes: -420,
      requestId: "timezone-la-tomorrow-request",
      sourceMessageId: "timezone-la-tomorrow-message",
    });
    const tomorrowHints = buildLocalRequestHints(losAngelesTomorrow);
    expect(tomorrowHints.route.kind).toBe("task-candidate");
    if (tomorrowHints.route.kind !== "task-candidate") return;
    expect(tomorrowHints.route.candidate).toMatchObject({
      dueAt: "2026-08-12T15:00:00.000Z",
      remindAt: "2026-08-12T15:00:00.000Z",
      timezoneOffsetMinutes: 420,
    });
    const tomorrowRepository = createInMemoryCompanionTaskRepository();
    const tomorrowResponse = await createCompanionHarness({
      modelPort: fakeModel().port,
      taskRepository: tomorrowRepository,
    }).respond(losAngelesTomorrow);
    expect(tomorrowResponse.actions).toMatchObject([{ type: "create_reminder", status: "succeeded" }]);
    expect(tomorrowRepository.read().reminders[0]?.remindAt).toBe("2026-08-12T15:00:00.000Z");
    expect(tomorrowResponse.text).toContain("8/12 8:00");
  });

  test("does not regress the completed Task fact when a duplicate completion is retried", async () => {
    const base = databaseWithReminder();
    const alreadyComplete = completeTask(base, base.tasks[0]!.id, NOW);
    const repository = createInMemoryCompanionTaskRepository(alreadyComplete);
    const model = fakeModel();
    const response = await createCompanionHarness({
      modelPort: model.port,
      taskRepository: repository,
    }).respond(input({
      message: "完成任务：交报告",
      requestId: "completed-retry-request",
      sourceMessageId: "completed-retry-message",
    }));

    expect(response.actions).toMatchObject([{ type: "complete_task", status: "rejected" }]);
    expect(response.text).not.toContain("已经完成“交报告”");
    expect(repository.writes).toBe(0);
    expect(repository.read().tasks[0]?.status).toBe("completed");
    expect(model.beginCalls).toBe(0);
    expect(model.generateCalls).toBe(0);
  });
});
