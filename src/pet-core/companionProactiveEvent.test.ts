import { describe, expect, it, vi } from "vitest";
import type { CompanionModelPort } from "./companionModelPort";
import type { CompanionEvent } from "./companionHarnessTypes";
import type { ProactiveExpressionStorage } from "./proactiveExpressionGate";
import type { ProactiveTaskCandidate } from "./proactiveTriggerEngine";
import type { Reminder, ReminderInstance, Task, TriggeredReminder } from "../task-core/types";
import {
  adaptProactiveTaskCandidateToCompanionEvent,
  adaptTriggeredReminderToCompanionEvent,
  createCompanionProactiveEventService,
  isCompanionEvent,
  parseCompanionEvent,
  type CompanionProactiveEventServiceOptions,
} from "./companionProactiveEvent";
import { createCompanionHarness } from "./companionHarness";

const NOW = new Date("2026-08-12T08:00:00.000Z");
const QUIET_DISABLED = { startTime: "00:00", endTime: "00:01" };

function storage(options: { initial?: string | null; failAfterWrites?: number; throwOnWrite?: boolean } = {}) {
  let value = options.initial ?? null;
  let writes = 0;
  const target: ProactiveExpressionStorage = {
    getItem: vi.fn(() => value),
    setItem: vi.fn((_key, nextValue) => {
      writes += 1;
      if (options.throwOnWrite || (options.failAfterWrites !== undefined && writes > options.failAfterWrites)) {
        throw new Error("storage writer failed");
      }
      value = nextValue;
    }),
  };
  return { target, get value() { return value; }, get writes() { return writes; } };
}

function task(
  id = "task-1",
  title = "交报告",
  overrides: Partial<Task> = {},
): Task {
  return {
    id,
    title,
    note: "本地备注 sentinel",
    status: "pending",
    priority: "high",
    projectId: "project-1",
    dueAt: "2026-08-12T09:00:00.000Z",
    kind: "single",
    parentTaskId: null,
    startAt: null,
    schedulePrecision: "datetime",
    includeToday: true,
    attachmentRefs: [],
    completedAt: null,
    cancelledAt: null,
    postponedCount: 0,
    createdAt: "2026-08-11T08:00:00.000Z",
    updatedAt: "2026-08-11T08:00:00.000Z",
    deletedAt: null,
    archivedAt: null,
    archiveReason: null,
    version: 1,
    sourceDeviceId: "device-1",
    ...overrides,
  };
}

function reminder(
  id = "reminder-1",
  taskId = "task-1",
  overrides: Partial<Reminder> = {},
): Reminder {
  return {
    id,
    taskId,
    remindAt: "2026-08-12T08:00:00.000Z",
    repeatType: "none",
    repeatRule: null,
    status: "active",
    snoozeCount: 0,
    createdAt: "2026-08-11T08:00:00.000Z",
    updatedAt: "2026-08-11T08:00:00.000Z",
    deletedAt: null,
    version: 1,
    ...overrides,
  };
}

function instance(
  id = "instance-1",
  taskId = "task-1",
  reminderId = "reminder-1",
  scheduledAt = "2026-08-12T08:00:00.000Z",
  overrides: Partial<ReminderInstance> = {},
): ReminderInstance {
  return {
    id,
    reminderId,
    taskId,
    scheduledAt,
    triggeredAt: "2026-08-12T08:00:00.000Z",
    snoozedFrom: null,
    snoozeCount: 0,
    dismissedAt: null,
    handledAt: null,
    status: "triggered",
    createdAt: "2026-08-11T08:00:00.000Z",
    updatedAt: "2026-08-12T08:00:00.000Z",
    ...overrides,
  };
}

function triggered(
  taskId = "task-1",
  reminderId = `reminder-${taskId}`,
  instanceId = `instance-${taskId}`,
  overrides: Partial<TriggeredReminder> = {},
): TriggeredReminder {
  const baseTask = task(taskId, taskId === "task-1" ? "交报告" : "浇花");
  const baseReminder = reminder(reminderId, taskId);
  const baseInstance = instance(instanceId, taskId, reminderId);
  return {
    task: baseTask,
    reminder: baseReminder,
    instance: baseInstance,
    ...overrides,
  };
}

function dueSoonCandidate(
  taskId = "task-1",
  title = "交报告",
  scheduledAt = "2026-08-12T08:30:00.000Z",
  overrides: Partial<ProactiveTaskCandidate> = {},
): ProactiveTaskCandidate {
  return {
    taskId,
    reminderId: `reminder-${taskId}`,
    reminderInstanceId: `instance-${taskId}`,
    title,
    priority: "high",
    taskStatus: "pending",
    deletedAt: null,
    scheduledAt,
    triggeredAt: null,
    status: "scheduled",
    ...overrides,
  };
}

function readyPackage(petId = "xiaoju-cat") {
  return {
    status: "ready" as const,
    petId,
    config: {
      version: 1 as const,
      scenes: {
        taskDue: { texts: ["本地 taskDue 模板"] },
        taskBurst: { texts: ["本地 taskBurst 模板"] },
      },
    },
  };
}

function fixture(
  overrides: Partial<CompanionProactiveEventServiceOptions> = {},
) {
  const stateStorage = storage();
  const sink = vi.fn(async () => true);
  const candidateByTask = new Map<string, ProactiveTaskCandidate>();
  const reminderByEvent = new Map<string, TriggeredReminder>();
  const options: CompanionProactiveEventServiceOptions = {
    storage: stateStorage.target,
    activePetId: "xiaoju-cat",
    availablePetIds: ["xiaoju-cat", "black-cat"],
    quietHours: QUIET_DISABLED,
    taskCooldownMs: 0,
    reducedTaskCooldownMs: 12 * 60 * 60 * 1000,
    now: () => NOW,
    deliverySink: sink,
    resolveTriggeredReminder: (event) => reminderByEvent.get(event.id) ?? null,
    resolveTaskCandidate: (event) => candidateByTask.get(event.taskId) ?? null,
    getTaskFeedbackPackage: () => readyPackage(),
    ...overrides,
  };
  const service = createCompanionProactiveEventService(options);
  return {
    stateStorage,
    sink: vi.mocked(options.deliverySink),
    candidateByTask,
    reminderByEvent,
    service,
  };
}

function throwingRemoteModel() {
  const beginTurn = vi.fn(() => {
    throw new Error("remote model must not be resolved for proactive events");
  });
  const generate = vi.fn(async () => {
    throw new Error("remote model must not generate for proactive events");
  });
  const model: CompanionModelPort = {
    info: {
      kind: "remote",
      provider: "remote-fixture",
      target: "remote-fixture",
      disclosure: "remote fixture",
    },
    beginTurn,
    generate,
  };
  return { model, beginTurn, generate };
}

describe("CompanionEvent adapters and runtime boundary", () => {
  it("adapts a TriggeredReminder to a stable opaque event without title or chat text", () => {
    const first = triggered();
    const same = triggered();
    const differentInstance = triggered("task-1", "reminder-1", "instance-2");
    const firstEvent = adaptTriggeredReminderToCompanionEvent(first);
    const sameEvent = adaptTriggeredReminderToCompanionEvent(same);
    const differentEvent = adaptTriggeredReminderToCompanionEvent(differentInstance);

    expect(firstEvent).not.toBeNull();
    expect(firstEvent).toEqual(sameEvent);
    expect(firstEvent?.id).not.toContain(first.task.title);
    expect(firstEvent?.id).not.toContain("本地备注 sentinel");
    expect(firstEvent?.id).not.toContain("交报告");
    expect(differentEvent?.id).not.toBe(firstEvent?.id);
    expect(Object.keys(firstEvent ?? {}).sort()).toEqual(["id", "reminderId", "reminderInstanceId", "type"]);
  });

  it("keeps TASK_DUE_SOON id stable while minutesLeft changes and changes it per occurrence", () => {
    const candidate = dueSoonCandidate();
    const atEight = adaptProactiveTaskCandidateToCompanionEvent(candidate, NOW);
    const atEightFive = adaptProactiveTaskCandidateToCompanionEvent(
      candidate,
      new Date("2026-08-12T08:05:00.000Z"),
    );
    const nextOccurrence = adaptProactiveTaskCandidateToCompanionEvent(
      { ...candidate, scheduledAt: "2026-08-13T08:30:00.000Z" },
      new Date("2026-08-13T08:00:00.000Z"),
    );

    expect(atEight).toMatchObject({ type: "TASK_DUE_SOON", minutesLeft: 30 });
    expect(atEightFive).toMatchObject({ type: "TASK_DUE_SOON", minutesLeft: 25 });
    expect(atEight?.id).toBe(atEightFive?.id);
    expect(nextOccurrence?.id).not.toBe(atEight?.id);
  });

  it("fails closed for malformed events and invalid due-soon candidates", () => {
    expect(parseCompanionEvent({ type: "UNKNOWN", id: "event-1" })).toBeNull();
    expect(parseCompanionEvent({
      id: "event-1",
      type: "REMINDER_DUE",
      reminderId: "reminder-1",
    })).toBeNull();
    expect(parseCompanionEvent({
      id: "event-1",
      type: "TASK_DUE_SOON",
      taskId: "task-1",
      minutesLeft: Number.NaN,
    })).toBeNull();
    expect(parseCompanionEvent({
      id: "task title with spaces",
      type: "TASK_DUE_SOON",
      taskId: "task-1",
      minutesLeft: 10,
    })).toBeNull();
    expect(parseCompanionEvent({
      id: "event-1",
      type: "TASK_DUE_SOON",
      taskId: "task-1",
      minutesLeft: 10,
      title: "不允许的正文",
    })).toBeNull();
    expect(isCompanionEvent({
      id: "event-1",
      type: "TASK_DUE_SOON",
      taskId: "task-1",
      minutesLeft: 10,
    })).toBe(true);

    expect(adaptProactiveTaskCandidateToCompanionEvent(
      dueSoonCandidate("done", "已完成", undefined, { taskStatus: "completed" }),
      NOW,
    )).toBeNull();
    expect(adaptProactiveTaskCandidateToCompanionEvent(
      dueSoonCandidate("cancelled", "已取消", undefined, { taskStatus: "cancelled" }),
      NOW,
    )).toBeNull();
    expect(adaptProactiveTaskCandidateToCompanionEvent(
      dueSoonCandidate("deleted", "已删除", undefined, { deletedAt: "2026-08-11T00:00:00.000Z" }),
      NOW,
    )).toBeNull();
    expect(adaptProactiveTaskCandidateToCompanionEvent(
      dueSoonCandidate("past", "已到期", "2026-08-12T07:59:00.000Z"),
      NOW,
    )).toBeNull();
    expect(adaptProactiveTaskCandidateToCompanionEvent(
      dueSoonCandidate("triggered", "伪装到期", undefined, {
        triggeredAt: "2026-08-12T08:00:00.000Z",
      }),
      NOW,
    )).toBeNull();
    expect(adaptProactiveTaskCandidateToCompanionEvent(
      dueSoonCandidate("bad-time", "非法时间", "not-a-time"),
      NOW,
    )).toBeNull();
  });
});

describe("Companion proactive event service", () => {
  it("handles REMINDER_DUE through the local template once and leaves domain facts unchanged", async () => {
    const fixtureValue = fixture();
    const due = triggered();
    const event = adaptTriggeredReminderToCompanionEvent(due)!;
    fixtureValue.reminderByEvent.set(event.id, due);
    const before = JSON.stringify(due);

    const first = await fixtureValue.service.processEvent(event);
    const second = await fixtureValue.service.processEvent(event);

    expect(first).toMatchObject({ status: "delivered", sinkCalled: true, delivered: true });
    expect(second).toMatchObject({ status: "duplicate", sinkCalled: false, delivered: false });
    expect(fixtureValue.sink).toHaveBeenCalledTimes(1);
    expect(fixtureValue.sink.mock.calls[0]?.[0]).toMatchObject({
      event,
      scene: "taskDue",
      text: "本地 taskDue 模板",
      eventIds: [event.id],
    });
    expect(JSON.stringify(due)).toBe(before);
    const state = fixtureValue.service.engine.getState(NOW);
    expect(state.bubbleCounts.task_reminder).toBe(1);
    expect(state.taskState?.deliveredKeys).toEqual([event.id]);
    expect(state.taskState?.decisionLog.filter((entry) => entry.result === "send")).toHaveLength(1);
  });

  it("uses the transactional eligibility API and never consumes legacy deliveries", async () => {
    const fixtureValue = fixture();
    const candidate = dueSoonCandidate("transactional-api", "交报告");
    const event = adaptProactiveTaskCandidateToCompanionEvent(candidate, NOW)!;
    fixtureValue.candidateByTask.set(candidate.taskId, candidate);
    const legacyEvaluate = vi.spyOn(fixtureValue.service.engine, "evaluate");
    const transactionalEvaluate = vi.spyOn(fixtureValue.service.engine, "evaluateEligibility");

    expect((await fixtureValue.service.processEvent(event)).status).toBe("delivered");
    expect(legacyEvaluate).not.toHaveBeenCalled();
    expect(transactionalEvaluate).toHaveBeenCalledTimes(1);
  });

  it("does not scan TaskDatabase for TASK_DUE_SOON and keeps model/action/memory at zero", async () => {
    const fixtureValue = fixture();
    const candidate = dueSoonCandidate();
    const event = adaptProactiveTaskCandidateToCompanionEvent(candidate, NOW)!;
    fixtureValue.candidateByTask.set(candidate.taskId, candidate);
    const model = throwingRemoteModel();
    const actionService = { process: vi.fn() };
    const memoryService = { process: vi.fn() };
    const contextBuilder = { build: vi.fn() };
    const harness = createCompanionHarness({
      modelPort: model.model,
      proactiveEventService: fixtureValue.service,
      actionService,
      memoryService,
      contextBuilder,
    });

    await harness.handleEvent(event);

    expect(fixtureValue.sink).toHaveBeenCalledTimes(1);
    expect(model.beginTurn).not.toHaveBeenCalled();
    expect(model.generate).not.toHaveBeenCalled();
    expect(actionService.process).not.toHaveBeenCalled();
    expect(memoryService.process).not.toHaveBeenCalled();
    expect(contextBuilder.build).not.toHaveBeenCalled();
    expect(fixtureValue.candidateByTask.size).toBe(1);
  });

  it("allows only one sink call for sequential and concurrent duplicates", async () => {
    const fixtureValue = fixture();
    const candidate = dueSoonCandidate();
    const event = adaptProactiveTaskCandidateToCompanionEvent(candidate, NOW)!;
    fixtureValue.candidateByTask.set(candidate.taskId, candidate);

    const [first, second] = await Promise.all([
      fixtureValue.service.processEvent(event),
      fixtureValue.service.processEvent(event),
    ]);
    const third = await fixtureValue.service.processEvent(event);

    expect(fixtureValue.sink).toHaveBeenCalledTimes(1);
    expect([first.status, second.status].filter((status) => status === "delivered")).toHaveLength(1);
    expect(third.status).toBe("duplicate");
    expect(fixtureValue.service.engine.getState(NOW).bubbleCounts.task_reminder).toBe(1);
    expect(fixtureValue.service.engine.getState(NOW).taskState?.decisionLog.filter((entry) => entry.result === "send")).toHaveLength(1);
  });

  it("serializes concurrent distinct events against dailyLimit=1", async () => {
    const fixtureValue = fixture({ dailyLimit: 1 });
    const firstCandidate = dueSoonCandidate("concurrent-limit-1", "写报告", "2026-08-12T08:30:00.000Z");
    const secondCandidate = dueSoonCandidate("concurrent-limit-2", "浇花", "2026-08-12T08:35:00.000Z");
    const firstEvent = adaptProactiveTaskCandidateToCompanionEvent(firstCandidate, NOW)!;
    const secondEvent = adaptProactiveTaskCandidateToCompanionEvent(secondCandidate, NOW)!;
    fixtureValue.candidateByTask.set(firstCandidate.taskId, firstCandidate);
    fixtureValue.candidateByTask.set(secondCandidate.taskId, secondCandidate);

    const results = await Promise.all([
      fixtureValue.service.processEvent(firstEvent),
      fixtureValue.service.processEvent(secondEvent),
    ]);

    expect(results.filter((result) => result.status === "delivered")).toHaveLength(1);
    expect(results.some((result) => result.status === "suppressed" || result.status === "delayed")).toBe(true);
    expect(fixtureValue.sink).toHaveBeenCalledTimes(1);
    expect(fixtureValue.service.engine.getState(NOW).bubbleCounts.task_reminder).toBe(1);
  });

  it("serializes concurrent distinct events against the global bubble cooldown", async () => {
    const fixtureValue = fixture({ dailyLimit: 10 });
    const firstCandidate = dueSoonCandidate("concurrent-cooldown-1", "写报告", "2026-08-12T08:30:00.000Z");
    const secondCandidate = dueSoonCandidate("concurrent-cooldown-2", "浇花", "2026-08-12T08:35:00.000Z");
    const firstEvent = adaptProactiveTaskCandidateToCompanionEvent(firstCandidate, NOW)!;
    const secondEvent = adaptProactiveTaskCandidateToCompanionEvent(secondCandidate, NOW)!;
    fixtureValue.candidateByTask.set(firstCandidate.taskId, firstCandidate);
    fixtureValue.candidateByTask.set(secondCandidate.taskId, secondCandidate);

    const results = await Promise.all([
      fixtureValue.service.processEvent(firstEvent),
      fixtureValue.service.processEvent(secondEvent),
    ]);

    expect(results.filter((result) => result.status === "delivered")).toHaveLength(1);
    expect(results.filter((result) => result.status === "delayed")).toHaveLength(1);
    expect(fixtureValue.sink).toHaveBeenCalledTimes(1);
    expect(fixtureValue.service.engine.getState(NOW).bubbleCounts.task_reminder).toBe(1);
  });

  it("aggregates concurrent similar Harness.handleEvent calls into one taskBurst", async () => {
    const fixtureValue = fixture();
    const firstCandidate = dueSoonCandidate("harness-burst-1", "交报告", "2026-08-12T08:30:00.000Z");
    const secondCandidate = dueSoonCandidate("harness-burst-2", "交报告给老板", "2026-08-12T08:45:00.000Z");
    const firstEvent = adaptProactiveTaskCandidateToCompanionEvent(firstCandidate, NOW)!;
    const secondEvent = adaptProactiveTaskCandidateToCompanionEvent(secondCandidate, NOW)!;
    fixtureValue.candidateByTask.set(firstCandidate.taskId, firstCandidate);
    fixtureValue.candidateByTask.set(secondCandidate.taskId, secondCandidate);
    const model = throwingRemoteModel();
    const harness = createCompanionHarness({
      modelPort: model.model,
      proactiveEventService: fixtureValue.service,
    });

    await Promise.all([
      harness.handleEvent(firstEvent),
      harness.handleEvent(secondEvent),
    ]);

    expect(fixtureValue.sink).toHaveBeenCalledTimes(1);
    expect(fixtureValue.sink.mock.calls[0]?.[0]).toMatchObject({
      scene: "taskBurst",
      eventIds: expect.arrayContaining([firstEvent.id, secondEvent.id]),
    });
    expect(fixtureValue.service.engine.getState(NOW).taskState?.deliveryReceipts[firstEvent.id]?.status).toBe("confirmed");
    expect(fixtureValue.service.engine.getState(NOW).taskState?.deliveryReceipts[secondEvent.id]?.status).toBe("confirmed");
    await harness.handleEvent(firstEvent);
    expect(fixtureValue.sink).toHaveBeenCalledTimes(1);
    expect(model.beginTurn).not.toHaveBeenCalled();
    expect(model.generate).not.toHaveBeenCalled();
  });

  it("survives App Restart and Sleep/Resume using storage rather than an in-memory Set", async () => {
    const firstFixture = fixture();
    const candidate = dueSoonCandidate();
    const event = adaptProactiveTaskCandidateToCompanionEvent(candidate, NOW)!;
    firstFixture.candidateByTask.set(candidate.taskId, candidate);
    await firstFixture.service.processEvent(event);

    const nextCandidate = dueSoonCandidate("task-2", "浇花", "2026-08-12T10:30:00.000Z");
    const nextEvent = adaptProactiveTaskCandidateToCompanionEvent(
      nextCandidate,
      new Date("2026-08-12T10:00:00.000Z"),
    )!;

    const restartedSink = vi.fn(async () => true);
    const restarted = createCompanionProactiveEventService({
      storage: firstFixture.stateStorage.target,
      activePetId: "xiaoju-cat",
      availablePetIds: ["xiaoju-cat"],
      quietHours: QUIET_DISABLED,
      now: () => new Date("2026-08-12T10:00:00.000Z"),
      deliverySink: restartedSink,
      resolveTaskCandidate: (candidateEvent) => candidateEvent.taskId === nextCandidate.taskId
        ? nextCandidate
        : candidate,
      getTaskFeedbackPackage: () => readyPackage(),
    });
    const replay = await restarted.processEvent(event);
    expect(replay.status).toBe("duplicate");
    expect(restartedSink).not.toHaveBeenCalled();

    const next = await restarted.processEvent(nextEvent);
    expect(nextEvent.id).not.toBe(event.id);
    expect(next.status).toBe("delivered");
    expect(restartedSink).toHaveBeenCalledTimes(1);
  });

  it("keeps durable at-most-once receipts after 257 confirmed events and restart", async () => {
    const base = new Date(NOW.getTime() + 10 * 60 * 1000);
    let clock = base;
    const fixtureValue = fixture({
      now: () => clock,
      dailyLimit: 1_000,
      taskCooldownMs: 0,
      reducedTaskCooldownMs: 0,
      aggregationWindowMs: 0,
    });
    const events: CompanionEvent[] = [];
    for (let index = 0; index < 257; index += 1) {
      clock = new Date(base.getTime() + index * 60 * 60 * 1000);
      const candidate = dueSoonCandidate(
        `durable-${index}`,
        `独立事项${index}`,
        new Date(clock.getTime() + 30 * 60 * 1000).toISOString(),
      );
      const event = adaptProactiveTaskCandidateToCompanionEvent(candidate, clock)!;
      events.push(event);
      fixtureValue.candidateByTask.set(candidate.taskId, candidate);
      const result = await fixtureValue.service.processEvent(event);
      expect(result.status, `durable event index ${index}: ${JSON.stringify(result)}`).toBe("delivered");
    }

    const state = fixtureValue.service.engine.getState(clock);
    expect(fixtureValue.sink).toHaveBeenCalledTimes(257);
    expect(state.taskState?.deliveredKeys).toHaveLength(256);
    expect(state.taskState?.deliveredKeys).not.toContain(events[0]!.id);
    expect(state.taskState?.deliveryReceipts[events[0]!.id]).toMatchObject({ status: "confirmed" });
    expect(Object.keys(state.taskState?.deliveryReceipts ?? {})).toHaveLength(257);

    const restartedSink = vi.fn(async () => true);
    const restarted = createCompanionProactiveEventService({
      storage: fixtureValue.stateStorage.target,
      activePetId: "xiaoju-cat",
      availablePetIds: ["xiaoju-cat"],
      quietHours: QUIET_DISABLED,
      dailyLimit: 1_000,
      taskCooldownMs: 0,
      reducedTaskCooldownMs: 0,
      aggregationWindowMs: 0,
      now: () => clock,
      deliverySink: restartedSink,
      resolveTaskCandidate: (event) => fixtureValue.candidateByTask.get(event.taskId) ?? null,
      getTaskFeedbackPackage: () => readyPackage(),
    });
    const replay = await restarted.processEvent(events[0]);

    expect(replay.status).toBe("duplicate");
    expect(restartedSink).not.toHaveBeenCalled();
    expect(Object.keys(restarted.engine.getState(clock).taskState?.deliveryReceipts ?? {})).toHaveLength(257);
  });

  it("prunes only terminally proven receipts and cannot resurrect a live event after restart", async () => {
    let terminallyProven = false;
    const fixtureValue = fixture({ verifyTerminalReceipt: () => terminallyProven });
    const candidate = dueSoonCandidate("prune-live", "终态前事项");
    const event = adaptProactiveTaskCandidateToCompanionEvent(candidate, NOW)!;
    fixtureValue.candidateByTask.set(candidate.taskId, candidate);
    expect((await fixtureValue.service.processEvent(event)).status).toBe("delivered");
    const prune = fixtureValue.service.engine.pruneTerminalReceipts;
    const invalidProof = {
      eventId: event.id,
      authority: "task-reminder-domain",
      status: "live",
    } as unknown as Parameters<typeof prune>[0][number];

    expect(prune([invalidProof])).toBe(false);
    expect(fixtureValue.service.engine.getState(NOW).taskState?.deliveryReceipts[event.id]?.status).toBe("confirmed");

    expect(prune([{
      eventId: event.id,
      authority: "task-reminder-domain",
      status: "terminal",
    }])).toBe(false);
    expect(fixtureValue.service.engine.getState(NOW).taskState?.deliveryReceipts[event.id]?.status).toBe("confirmed");

    terminallyProven = true;
    expect(prune([{
      eventId: event.id,
      authority: "task-reminder-domain",
      status: "terminal",
    }])).toBe(true);
    expect(fixtureValue.service.engine.getState(NOW).taskState?.deliveryReceipts[event.id]).toBeUndefined();
    expect(fixtureValue.service.engine.getState(NOW).taskState?.deliveredKeys).not.toContain(event.id);

    fixtureValue.candidateByTask.delete(candidate.taskId);
    const restartedSink = vi.fn(async () => true);
    const restarted = createCompanionProactiveEventService({
      storage: fixtureValue.stateStorage.target,
      activePetId: "xiaoju-cat",
      availablePetIds: ["xiaoju-cat"],
      quietHours: QUIET_DISABLED,
      now: () => NOW,
      deliverySink: restartedSink,
      resolveTaskCandidate: () => null,
      getTaskFeedbackPackage: () => readyPackage(),
    });
    expect((await restarted.processEvent(event)).status).toBe("unresolved");
    expect(restartedSink).not.toHaveBeenCalled();
  });

  it("keeps aggregation to one taskBurst and marks every member idempotently", async () => {
    const fixtureValue = fixture();
    const firstCandidate = dueSoonCandidate("task-1", "交报告", "2026-08-12T08:30:00.000Z");
    const secondCandidate = dueSoonCandidate("task-2", "交报告给老板", "2026-08-12T08:45:00.000Z");
    const firstEvent = adaptProactiveTaskCandidateToCompanionEvent(firstCandidate, NOW)!;
    const secondEvent = adaptProactiveTaskCandidateToCompanionEvent(secondCandidate, NOW)!;
    fixtureValue.candidateByTask.set(firstCandidate.taskId, firstCandidate);
    fixtureValue.candidateByTask.set(secondCandidate.taskId, secondCandidate);

    const first = await fixtureValue.service.processEvents([firstEvent, secondEvent]);
    expect(fixtureValue.sink).toHaveBeenCalledTimes(1);
    expect(first.filter((result) => result.status === "delivered")).toHaveLength(2);
    expect(fixtureValue.sink.mock.calls[0]?.[0]).toMatchObject({
      scene: "taskBurst",
      eventIds: expect.arrayContaining([firstEvent.id, secondEvent.id]),
    });
    const state = fixtureValue.service.engine.getState(NOW);
    expect(state.bubbleCounts.task_reminder).toBe(1);
    expect(state.taskState?.deliveredKeys).toEqual(expect.arrayContaining([firstEvent.id, secondEvent.id]));

    await fixtureValue.service.processEvents([firstEvent, secondEvent]);
    expect(fixtureValue.sink).toHaveBeenCalledTimes(1);
  });

  it("suppresses DND, disabled, daily limit, cooldown, reduced, muted and ignore backoff without domain writes", async () => {
    const quietFixture = fixture({ quietHours: { startTime: "00:00", endTime: "23:59" } });
    const quietCandidate = dueSoonCandidate("quiet");
    const quietEvent = adaptProactiveTaskCandidateToCompanionEvent(quietCandidate, NOW)!;
    quietFixture.candidateByTask.set(quietCandidate.taskId, quietCandidate);
    expect((await quietFixture.service.processEvent(quietEvent)).status).toBe("suppressed");
    expect(quietFixture.sink).not.toHaveBeenCalled();

    const disabledFixture = fixture({ enabled: false });
    const disabledCandidate = dueSoonCandidate("disabled");
    const disabledEvent = adaptProactiveTaskCandidateToCompanionEvent(disabledCandidate, NOW)!;
    disabledFixture.candidateByTask.set(disabledCandidate.taskId, disabledCandidate);
    expect((await disabledFixture.service.processEvent(disabledEvent)).status).toBe("disabled");
    expect(disabledFixture.sink).not.toHaveBeenCalled();

    const limitedFixture = fixture({ dailyLimit: 1 });
    const firstCandidate = dueSoonCandidate("limit-1", "写报告");
    const firstEvent = adaptProactiveTaskCandidateToCompanionEvent(firstCandidate, NOW)!;
    limitedFixture.candidateByTask.set(firstCandidate.taskId, firstCandidate);
    expect((await limitedFixture.service.processEvent(firstEvent)).status).toBe("delivered");
    const secondCandidate = dueSoonCandidate("limit-2", "浇花", "2026-08-12T08:50:00.000Z");
    const secondEvent = adaptProactiveTaskCandidateToCompanionEvent(secondCandidate, NOW)!;
    limitedFixture.candidateByTask.set(secondCandidate.taskId, secondCandidate);
    expect((await limitedFixture.service.processEvent(secondEvent)).status).toBe("suppressed");
    expect(limitedFixture.sink).toHaveBeenCalledTimes(1);

    const globalCooldownFixture = fixture();
    const globalFirst = dueSoonCandidate("global-1", "写报告", "2026-08-12T08:30:00.000Z");
    const globalSecond = dueSoonCandidate("global-2", "浇花", "2026-08-12T08:45:00.000Z");
    const globalFirstEvent = adaptProactiveTaskCandidateToCompanionEvent(globalFirst, NOW)!;
    const globalSecondEvent = adaptProactiveTaskCandidateToCompanionEvent(globalSecond, NOW)!;
    globalCooldownFixture.candidateByTask.set(globalFirst.taskId, globalFirst);
    globalCooldownFixture.candidateByTask.set(globalSecond.taskId, globalSecond);
    const globalResults = await globalCooldownFixture.service.processEvents([globalFirstEvent, globalSecondEvent]);
    expect(globalCooldownFixture.sink).toHaveBeenCalledTimes(1);
    expect(globalResults.filter((result) => result.status === "delayed")).toHaveLength(1);
    expect(globalResults.filter((result) => result.status === "delivered")).toHaveLength(1);

    const gateFixture = fixture();
    const gateCandidate = dueSoonCandidate("gate");
    const gateEvent = adaptProactiveTaskCandidateToCompanionEvent(gateCandidate, NOW)!;
    gateFixture.candidateByTask.set(gateCandidate.taskId, gateCandidate);
    gateFixture.service.engine.setTaskPreference(gateCandidate.taskId, { mode: "muted" }, new Date("2026-08-12T07:00:00.000Z"));
    const reducedCandidate = dueSoonCandidate("reduced", "整理房间", "2026-08-12T08:35:00.000Z");
    const reducedEvent = adaptProactiveTaskCandidateToCompanionEvent(reducedCandidate, NOW)!;
    gateFixture.candidateByTask.set(reducedCandidate.taskId, reducedCandidate);
    gateFixture.service.engine.setTaskPreference(reducedCandidate.taskId, { mode: "reduced" }, new Date("2026-08-12T07:00:00.000Z"));
    expect((await gateFixture.service.processEvent(gateEvent)).status).toBe("suppressed");
    expect((await gateFixture.service.processEvent(reducedEvent)).status).toBe("delivered");
    const laterCandidate = dueSoonCandidate("reduced", "整理房间", "2026-08-12T08:55:00.000Z", {
      reminderInstanceId: "instance-reduced-next",
    });
    const laterEvent = adaptProactiveTaskCandidateToCompanionEvent(laterCandidate, NOW)!;
    gateFixture.candidateByTask.set(laterCandidate.taskId, laterCandidate);
    expect((await gateFixture.service.processEvent(laterEvent)).status).toBe("delayed");
    gateFixture.service.engine.recordIgnored(reducedCandidate.taskId, new Date("2026-08-12T09:01:00.000Z"));
    expect(gateFixture.service.engine.getState(NOW).taskState?.preferences[reducedCandidate.taskId]?.mode).toBe("reduced");
  });

  it("never falls back to the active pet when the preferred target is unavailable, and permits explicit retry", async () => {
    const unavailable = fixture({ availablePetIds: ["xiaoju-cat"] });
    const candidate = dueSoonCandidate();
    const event = adaptProactiveTaskCandidateToCompanionEvent(candidate, NOW)!;
    unavailable.candidateByTask.set(candidate.taskId, candidate);
    unavailable.service.engine.setTaskPreference(candidate.taskId, { preferredPetId: "black-cat" }, new Date("2026-08-12T07:00:00.000Z"));
    const blocked = await unavailable.service.processEvent(event);
    expect(blocked.status).toBe("unavailable");
    expect(unavailable.sink).not.toHaveBeenCalled();
    expect(unavailable.service.engine.getState(NOW).bubbleCounts.task_reminder).toBe(0);
    expect(unavailable.service.engine.getState(NOW).taskState?.deliveredKeys).toEqual([]);

    const retrySink = vi.fn(async () => true);
    const retry = createCompanionProactiveEventService({
      storage: unavailable.stateStorage.target,
      activePetId: "black-cat",
      availablePetIds: ["xiaoju-cat", "black-cat"],
      quietHours: QUIET_DISABLED,
      now: () => NOW,
      deliverySink: retrySink,
      resolveTaskCandidate: () => candidate,
      getTaskFeedbackPackage: () => readyPackage("black-cat"),
    });
    expect((await retry.processEvent(event)).status).toBe("delivered");
    expect(retrySink).toHaveBeenCalledTimes(1);
  });

  it("routes a preferred available pet through Harness before reserving and sinking", async () => {
    const ensureActivePet = vi.fn(async () => true);
    const fixtureValue = fixture({
      getTaskFeedbackPackage: (petId) => readyPackage(petId),
      ensureActivePet,
    });
    const candidate = dueSoonCandidate("route-success", "交报告");
    const event = adaptProactiveTaskCandidateToCompanionEvent(candidate, NOW)!;
    fixtureValue.candidateByTask.set(candidate.taskId, candidate);
    fixtureValue.service.engine.setTaskPreference(
      candidate.taskId,
      { preferredPetId: "black-cat" },
      new Date("2026-08-12T07:00:00.000Z"),
    );
    const model = throwingRemoteModel();
    const harness = createCompanionHarness({
      modelPort: model.model,
      proactiveEventService: fixtureValue.service,
    });

    await harness.handleEvent(event);

    expect(ensureActivePet).toHaveBeenCalledTimes(1);
    expect(ensureActivePet).toHaveBeenCalledWith("black-cat");
    expect(fixtureValue.sink).toHaveBeenCalledTimes(1);
    expect(fixtureValue.sink.mock.calls[0]?.[0]).toMatchObject({ petId: "black-cat", eventIds: [event.id] });
    expect(fixtureValue.service.engine.getLastDeliveryContext(NOW)?.petId).toBe("black-cat");
    expect(model.beginTurn).not.toHaveBeenCalled();
    expect(model.generate).not.toHaveBeenCalled();
  });

  it.each([
    ["false", async (): Promise<boolean> => false],
    ["throws", async (): Promise<boolean> => { throw new Error("pet route failed"); }],
  ] as const)("does not reserve or sink when the injected pet route %s", async (_label, ensureActivePet) => {
    const fixtureValue = fixture({ ensureActivePet });
    const candidate = dueSoonCandidate(`route-failure-${_label}`, "交报告");
    const event = adaptProactiveTaskCandidateToCompanionEvent(candidate, NOW)!;
    fixtureValue.candidateByTask.set(candidate.taskId, candidate);
    fixtureValue.service.engine.setTaskPreference(
      candidate.taskId,
      { preferredPetId: "black-cat" },
      new Date("2026-08-12T07:00:00.000Z"),
    );

    await fixtureValue.service.handleEvent(event);

    expect(fixtureValue.sink).not.toHaveBeenCalled();
    expect(fixtureValue.service.engine.getLastDeliveryContext(NOW)).toBeNull();
    expect(fixtureValue.service.engine.getState(NOW).taskState?.deliveryReceipts[event.id]).toBeUndefined();
  });

  it("keeps the Harness route fail-closed for an unavailable preferred pet", async () => {
    const fixtureValue = fixture({ availablePetIds: ["xiaoju-cat"] });
    const candidate = dueSoonCandidate("route-unavailable", "交报告");
    const event = adaptProactiveTaskCandidateToCompanionEvent(candidate, NOW)!;
    fixtureValue.candidateByTask.set(candidate.taskId, candidate);
    fixtureValue.service.engine.setTaskPreference(
      candidate.taskId,
      { preferredPetId: "black-cat" },
      new Date("2026-08-12T07:00:00.000Z"),
    );
    const harness = createCompanionHarness({
      modelPort: throwingRemoteModel().model,
      proactiveEventService: fixtureValue.service,
    });

    await harness.handleEvent(event);

    expect(fixtureValue.sink).not.toHaveBeenCalled();
    expect(fixtureValue.service.engine.getLastDeliveryContext(NOW)).toBeNull();
    expect(fixtureValue.service.engine.getState(NOW).taskState?.deliveryReceipts[event.id]).toBeUndefined();
  });

  it.each([
    ["sink-false", "delivery-failed"],
    ["sink-throws", "delivery-failed"],
    ["storage-failed", "storage-failed"],
    ["unavailable", "unavailable"],
    ["switch-required", "switch-required"],
    ["confirmation-failed", "confirmation-failed"],
  ] as const)("never fabricates lastDeliveryContext for %s", async (kind, expectedStatus) => {
    let clock = NOW;
    let storageValue: string | null = null;
    let writes = 0;
    let failStorage = false;
    let failAt = Number.POSITIVE_INFINITY;
    const stateStorage: ProactiveExpressionStorage = {
      getItem: vi.fn(() => storageValue),
      setItem: vi.fn((_key, value) => {
        writes += 1;
        if (failStorage || writes === failAt) throw new Error("storage failure");
        storageValue = value;
      }),
    };
    let sinkMode: "success" | "false" | "throws" = "success";
    const sink = vi.fn(async () => {
      if (sinkMode === "false") return false;
      if (sinkMode === "throws") throw new Error("sink failure");
      return true;
    });
    const fixtureValue = fixture({
      storage: stateStorage,
      now: () => clock,
      dailyLimit: 100,
      taskCooldownMs: 0,
      reducedTaskCooldownMs: 0,
      aggregationWindowMs: 0,
      deliverySink: sink,
      availablePetIds: kind === "unavailable" ? ["xiaoju-cat"] : ["xiaoju-cat", "black-cat"],
    });
    const baselineCandidate = dueSoonCandidate(
      `context-baseline-${kind}`,
      "基础事项",
      new Date(clock.getTime() + 30 * 60 * 1000).toISOString(),
    );
    const baselineEvent = adaptProactiveTaskCandidateToCompanionEvent(baselineCandidate, clock)!;
    fixtureValue.candidateByTask.set(baselineCandidate.taskId, baselineCandidate);
    expect((await fixtureValue.service.processEvent(baselineEvent)).status).toBe("delivered");
    const confirmedContext = fixtureValue.service.engine.getLastDeliveryContext(clock);
    expect(confirmedContext).not.toBeNull();

    clock = new Date(NOW.getTime() + 60 * 60 * 1000);
    const failureCandidate = dueSoonCandidate(
      `context-failure-${kind}`,
      "失败事项",
      new Date(clock.getTime() + 30 * 60 * 1000).toISOString(),
    );
    const failureEvent = adaptProactiveTaskCandidateToCompanionEvent(failureCandidate, clock)!;
    fixtureValue.candidateByTask.set(failureCandidate.taskId, failureCandidate);
    if (kind === "sink-false") sinkMode = "false";
    if (kind === "sink-throws") sinkMode = "throws";
    if (kind === "storage-failed") failStorage = true;
    if (kind === "confirmation-failed") failAt = writes + 3;
    if (kind === "unavailable" || kind === "switch-required") {
      fixtureValue.service.engine.setTaskPreference(
        failureCandidate.taskId,
        { preferredPetId: kind === "unavailable" ? "missing-cat" : "black-cat" },
        clock,
      );
    }

    const failed = await fixtureValue.service.processEvent(failureEvent);

    expect(failed.status).toBe(expectedStatus);
    expect(fixtureValue.service.engine.getLastDeliveryContext(clock)).toEqual(confirmedContext);
    if (kind === "sink-false" || kind === "sink-throws" || kind === "confirmation-failed") {
      expect(sink).toHaveBeenCalledTimes(2);
    } else {
      expect(sink).toHaveBeenCalledTimes(1);
    }
    if (kind === "confirmation-failed") {
      expect(fixtureValue.service.engine.getState(clock).taskState?.deliveryReceipts[failureEvent.id]?.status)
        .toBe("reserved");
    } else {
      expect(fixtureValue.service.engine.getState(clock).taskState?.lastDeliveryContext).toEqual(confirmedContext);
    }
  });

  it("recovers the shared event queue after resolver, sink, and storage throws", async () => {
    const resolverFixture = fixture({
      resolveTaskCandidate: (event) => {
        if (event.taskId === "resolver-throws") throw new Error("resolver failed");
        return resolverFixture.candidateByTask.get(event.taskId) ?? null;
      },
    });
    const resolverBad = dueSoonCandidate("resolver-throws", "坏解析");
    const resolverGood = dueSoonCandidate("resolver-good", "好解析");
    const resolverBadEvent = adaptProactiveTaskCandidateToCompanionEvent(resolverBad, NOW)!;
    const resolverGoodEvent = adaptProactiveTaskCandidateToCompanionEvent(resolverGood, NOW)!;
    resolverFixture.candidateByTask.set(resolverGood.taskId, resolverGood);
    expect((await resolverFixture.service.processEvent(resolverBadEvent)).status).toBe("unresolved");
    expect((await resolverFixture.service.processEvent(resolverGoodEvent)).status).toBe("delivered");
    expect(resolverFixture.sink).toHaveBeenCalledTimes(1);

    let sinkClock = NOW;
    let sinkCalls = 0;
    const sinkFixture = fixture({
      now: () => sinkClock,
      deliverySink: vi.fn(async () => {
        sinkCalls += 1;
        if (sinkCalls === 1) throw new Error("sink failed");
        return true;
      }),
    });
    const sinkBad = dueSoonCandidate("sink-throws", "坏投递");
    const sinkGood = dueSoonCandidate("sink-good", "好投递");
    const sinkBadEvent = adaptProactiveTaskCandidateToCompanionEvent(sinkBad, sinkClock)!;
    sinkFixture.candidateByTask.set(sinkBad.taskId, sinkBad);
    expect((await sinkFixture.service.processEvent(sinkBadEvent)).status).toBe("delivery-failed");
    sinkClock = new Date(NOW.getTime() + 60 * 60 * 1000);
    const sinkGoodEvent = adaptProactiveTaskCandidateToCompanionEvent(
      { ...sinkGood, scheduledAt: new Date(sinkClock.getTime() + 30 * 60 * 1000).toISOString() },
      sinkClock,
    )!;
    sinkFixture.candidateByTask.set(sinkGood.taskId, {
      ...sinkGood,
      scheduledAt: new Date(sinkClock.getTime() + 30 * 60 * 1000).toISOString(),
    });
    expect((await sinkFixture.service.processEvent(sinkGoodEvent)).status).toBe("delivered");
    expect(sinkFixture.sink).toHaveBeenCalledTimes(2);

    let storageValue: string | null = null;
    let failStorage = true;
    const toggledStorage: ProactiveExpressionStorage = {
      getItem: vi.fn(() => storageValue),
      setItem: vi.fn((_key, value) => {
        if (failStorage) throw new Error("storage failed");
        storageValue = value;
      }),
    };
    const storageFixture = fixture({ storage: toggledStorage });
    const storageBad = dueSoonCandidate("storage-throws", "坏存储");
    const storageGood = dueSoonCandidate("storage-good", "好存储", "2026-08-12T09:00:00.000Z");
    const storageBadEvent = adaptProactiveTaskCandidateToCompanionEvent(storageBad, NOW)!;
    const storageGoodEvent = adaptProactiveTaskCandidateToCompanionEvent(storageGood, NOW)!;
    storageFixture.candidateByTask.set(storageBad.taskId, storageBad);
    storageFixture.candidateByTask.set(storageGood.taskId, storageGood);
    expect((await storageFixture.service.processEvent(storageBadEvent)).status).toBe("storage-failed");
    failStorage = false;
    expect((await storageFixture.service.processEvent(storageGoodEvent)).status).toBe("delivered");
    expect(storageFixture.sink).toHaveBeenCalledTimes(1);
  });

  it("fails closed when reservation persistence, sink, or confirmation persistence fails", async () => {
    const noStorage = fixture({ storage: null });
    const noStorageCandidate = dueSoonCandidate("no-storage");
    const noStorageEvent = adaptProactiveTaskCandidateToCompanionEvent(noStorageCandidate, NOW)!;
    noStorage.candidateByTask.set(noStorageCandidate.taskId, noStorageCandidate);
    expect((await noStorage.service.processEvent(noStorageEvent)).status).toBe("storage-failed");
    expect(noStorage.sink).not.toHaveBeenCalled();

    const writerFailure = fixture({ storage: storage({ throwOnWrite: true }).target });
    const writerCandidate = dueSoonCandidate("writer-failure");
    const writerEvent = adaptProactiveTaskCandidateToCompanionEvent(writerCandidate, NOW)!;
    writerFailure.candidateByTask.set(writerCandidate.taskId, writerCandidate);
    expect((await writerFailure.service.processEvent(writerEvent)).status).toBe("storage-failed");
    expect(writerFailure.sink).not.toHaveBeenCalled();

    const sinkFailure = fixture({ deliverySink: vi.fn(async () => false) });
    const sinkCandidate = dueSoonCandidate("sink-failure");
    const sinkEvent = adaptProactiveTaskCandidateToCompanionEvent(sinkCandidate, NOW)!;
    sinkFailure.candidateByTask.set(sinkCandidate.taskId, sinkCandidate);
    const failed = await sinkFailure.service.processEvent(sinkEvent);
    const replay = await sinkFailure.service.processEvent(sinkEvent);
    expect(failed).toMatchObject({ status: "delivery-failed", sinkCalled: true, delivered: false });
    expect(replay.status).toBe("duplicate");
    expect(sinkFailure.sink).toHaveBeenCalledTimes(1);
    expect(sinkFailure.service.engine.getState(NOW).bubbleCounts.task_reminder).toBe(0);
    expect(sinkFailure.service.engine.getState(NOW).taskState?.deliveredKeys).toEqual([]);

    const confirmationStorage = storage({ failAfterWrites: 2 });
    const confirmationFailure = fixture({ storage: confirmationStorage.target });
    const confirmationCandidate = dueSoonCandidate("confirmation-failure");
    const confirmationEvent = adaptProactiveTaskCandidateToCompanionEvent(confirmationCandidate, NOW)!;
    confirmationFailure.candidateByTask.set(confirmationCandidate.taskId, confirmationCandidate);
    const confirmation = await confirmationFailure.service.processEvent(confirmationEvent);
    expect(confirmation).toMatchObject({ status: "confirmation-failed", sinkCalled: true, delivered: false });

    const afterRestartSink = vi.fn(async () => true);
    const afterRestart = createCompanionProactiveEventService({
      storage: confirmationStorage.target,
      activePetId: "xiaoju-cat",
      availablePetIds: ["xiaoju-cat"],
      quietHours: QUIET_DISABLED,
      now: () => NOW,
      deliverySink: afterRestartSink,
      resolveTaskCandidate: () => confirmationCandidate,
      getTaskFeedbackPackage: () => readyPackage(),
    });
    expect((await afterRestart.processEvent(confirmationEvent)).status).toBe("duplicate");
    expect(afterRestartSink).not.toHaveBeenCalled();
  });
});
