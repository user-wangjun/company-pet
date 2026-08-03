import { describe, expect, it, vi } from "vitest";
import type { ProactiveExpressionStorage } from "./proactiveExpressionGate";
import {
  createProactiveTriggerEngine,
  parseProactivePreferenceCommand,
  taskCandidateFromTask,
  type ProactiveTaskCandidate,
} from "./proactiveTriggerEngine";

const QUIET_DISABLED = { startTime: "00:00", endTime: "00:01" };

function storage(): ProactiveExpressionStorage {
  let value: string | null = null;
  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((_key, nextValue) => {
      value = nextValue;
    }),
  };
}

function at(hour: number, minute = 0): Date {
  return new Date(2026, 7, 2, hour, minute, 0, 0);
}

function candidate(
  taskId: string,
  title: string,
  scheduledAt: Date,
  overrides: Partial<ProactiveTaskCandidate> = {},
): ProactiveTaskCandidate {
  return {
    taskId,
    reminderId: `reminder-${taskId}`,
    reminderInstanceId: `instance-${taskId}`,
    title,
    priority: "normal",
    taskStatus: "pending",
    deletedAt: null,
    scheduledAt: scheduledAt.toISOString(),
    triggeredAt: scheduledAt.toISOString(),
    status: "triggered",
    ...overrides,
  };
}

function engine(
  storageValue: ProactiveExpressionStorage,
  activePetId = "xiaoju-cat",
  availablePetIds = ["xiaoju-cat", "black-cat"],
) {
  return createProactiveTriggerEngine({
    storage: storageValue,
    activePetId,
    availablePetIds,
    quietHours: QUIET_DISABLED,
  });
}

describe("provider-independent proactive trigger engine", () => {
  it("delivers the same task at most once in one time window", () => {
    const stateStorage = storage();
    const triggerEngine = engine(stateStorage);
    const first = candidate("task-1", "交报告", at(8));

    const firstEvaluation = triggerEngine.evaluate([first], at(8));
    const secondEvaluation = triggerEngine.evaluate([first], at(8, 5));

    expect(firstEvaluation.deliveries).toHaveLength(1);
    expect(firstEvaluation.decisions[0]).toMatchObject({ result: "send", actualDelivery: true });
    expect(secondEvaluation.decisions[0]).toMatchObject({
      result: "suppress",
      reason: "already-delivered",
      actualDelivery: false,
    });
  });

  it("suppresses a candidate during quiet hours", () => {
    const stateStorage = storage();
    const triggerEngine = createProactiveTriggerEngine({
      storage: stateStorage,
      activePetId: "xiaoju-cat",
      quietHours: { startTime: "23:00", endTime: "07:00" },
    });

    const evaluation = triggerEngine.evaluate([candidate("task-quiet", "睡觉", at(23, 30))], at(23, 30));

    expect(evaluation.decisions[0]).toMatchObject({
      result: "suppress",
      reason: "quiet-hours",
      nextEligibleAt: null,
    });
  });

  it("keeps a quiet-hour candidate eligible for a later scheduler re-evaluation", () => {
    const stateStorage = storage();
    const triggerEngine = createProactiveTriggerEngine({
      storage: stateStorage,
      activePetId: "xiaoju-cat",
      quietHours: { startTime: "23:00", endTime: "07:00" },
    });
    const task = candidate("task-recheck", "睡觉", at(23, 30));

    expect(triggerEngine.evaluate([task], at(23, 30)).decisions[0].reason).toBe("quiet-hours");
    expect(triggerEngine.evaluate([task], new Date(2026, 7, 3, 8, 0, 0, 0)).decisions[0].result).toBe("send");
  });

  it("suppresses after the user-level daily limit", () => {
    const stateStorage = storage();
    const triggerEngine = createProactiveTriggerEngine({
      storage: stateStorage,
      activePetId: "xiaoju-cat",
      dailyLimit: 1,
      quietHours: QUIET_DISABLED,
    });

    expect(triggerEngine.evaluate([candidate("task-limit-1", "交报告", at(8))], at(8)).decisions[0].result).toBe("send");
    const evaluation = triggerEngine.evaluate([candidate("task-limit-2", "浇花", at(9))], at(9));

    expect(evaluation.decisions[0]).toMatchObject({ result: "suppress", reason: "daily-limit" });
  });

  it("persists delivery, ignore, delivery, ignore, and then applies backoff", () => {
    const stateStorage = storage();
    const triggerEngine = engine(stateStorage);
    const first = candidate("task-ignore", "整理报告", at(8));
    const firstEvaluation = triggerEngine.evaluate([first], at(8));
    expect(firstEvaluation.decisions[0]).toMatchObject({ result: "send", actualDelivery: true });
    triggerEngine.recordIgnored(first.taskId, at(8, 1));

    const second = candidate("task-ignore", "整理报告", at(12, 1), {
      reminderInstanceId: "instance-ignore-second",
    });
    const secondEvaluation = triggerEngine.evaluate([second], at(12, 1));
    expect(secondEvaluation.decisions[0]).toMatchObject({ result: "send", actualDelivery: true });
    triggerEngine.recordIgnored(second.taskId, at(12, 2));

    const evaluation = triggerEngine.evaluate([
      candidate("task-ignore", "整理报告", at(16, 1), { reminderInstanceId: "instance-ignore-next" }),
    ], at(16, 1));

    expect(evaluation.decisions[0]).toMatchObject({ result: "delay", reason: "ignored-backoff" });
    expect(evaluation.decisions[0].nextEligibleAt).not.toBeNull();
  });

  it("aggregates close, similar tasks into one actual delivery", () => {
    const triggerEngine = engine(storage());
    const tasks = [
      candidate("task-aggregate-1", "交报告", at(8)),
      candidate("task-aggregate-2", "交报告给老板", at(8, 20)),
    ];

    const evaluation = triggerEngine.evaluate(tasks, at(8));

    expect(evaluation.deliveries).toHaveLength(1);
    expect(evaluation.deliveries[0].decision.result).toBe("aggregate");
    expect(evaluation.deliveries[0].decision.aggregatedTaskIds).toEqual(expect.arrayContaining([
      "task-aggregate-1",
      "task-aggregate-2",
    ]));
    expect(evaluation.decisions.filter((decision) => decision.actualDelivery)).toHaveLength(1);
    expect(evaluation.decisions.find((decision) => decision.taskId === "task-aggregate-2")?.reason).toBe("aggregated");
  });

  it("does not generate delivery for completed, cancelled, or deleted tasks", () => {
    const triggerEngine = engine(storage());
    const evaluation = triggerEngine.evaluate([
      candidate("task-completed", "已完成", at(8), { taskStatus: "completed" }),
      candidate("task-cancelled", "已取消", at(8), { taskStatus: "cancelled" }),
      candidate("task-deleted", "已删除", at(8), { deletedAt: at(7).toISOString() }),
    ], at(8));

    expect(evaluation.deliveries).toHaveLength(0);
    expect(evaluation.decisions).toHaveLength(3);
    expect(evaluation.decisions.every((decision) => decision.reason === "task-not-active")).toBe(true);
  });

  it("persists cooldown, count limits, idempotency, and explanations across restart", () => {
    const stateStorage = storage();
    const firstEngine = createProactiveTriggerEngine({
      storage: stateStorage,
      activePetId: "xiaoju-cat",
      dailyLimit: 2,
      quietHours: QUIET_DISABLED,
    });
    const first = candidate("task-restart", "复习", at(8));
    firstEngine.evaluate([first], at(8));

    const restartedEngine = createProactiveTriggerEngine({
      storage: stateStorage,
      activePetId: "xiaoju-cat",
      dailyLimit: 2,
      quietHours: QUIET_DISABLED,
    });
    const nextWindow = restartedEngine.evaluate([
      candidate("task-restart", "复习", at(9), { reminderInstanceId: "instance-restart-next" }),
    ], at(9));
    const duplicate = restartedEngine.evaluate([first], at(9, 1));

    expect(nextWindow.decisions[0]).toMatchObject({ result: "delay", reason: "task-cooldown" });
    expect(duplicate.decisions[0]).toMatchObject({ result: "suppress", reason: "already-delivered" });
    expect(nextWindow.decisions[0].explanation).toContain("冷却");
    expect(restartedEngine.getState(at(9)).bubbleCounts.task_reminder).toBe(1);
  });

  it("persists the daily limit across restart", () => {
    const stateStorage = storage();
    const firstEngine = createProactiveTriggerEngine({
      storage: stateStorage,
      activePetId: "xiaoju-cat",
      dailyLimit: 1,
      quietHours: QUIET_DISABLED,
    });
    firstEngine.evaluate([candidate("task-daily-restart-1", "背单词", at(8))], at(8));

    const restartedEngine = createProactiveTriggerEngine({
      storage: stateStorage,
      activePetId: "xiaoju-cat",
      dailyLimit: 1,
      quietHours: QUIET_DISABLED,
    });
    const evaluation = restartedEngine.evaluate([
      candidate("task-daily-restart-2", "浇花", at(10)),
    ], at(10));

    expect(evaluation.decisions[0]).toMatchObject({ result: "suppress", reason: "daily-limit" });
  });

  it("persists mute and reduced-frequency controls without changing task facts", () => {
    const stateStorage = storage();
    const triggerEngine = engine(stateStorage);
    const muted = candidate("task-muted", "买牛奶", at(8));
    const reduced = candidate("task-reduced", "整理房间", at(8));

    triggerEngine.setTaskPreference(muted.taskId, { mode: "muted" }, at(7));
    triggerEngine.setTaskPreference(reduced.taskId, { mode: "reduced" }, at(7));
    const first = triggerEngine.evaluate([muted, reduced], at(8));
    const reducedLater = triggerEngine.evaluate([
      { ...reduced, reminderInstanceId: "instance-reduced-next", scheduledAt: at(9).toISOString() },
    ], at(9));

    expect(first.decisions.find((decision) => decision.taskId === muted.taskId)).toMatchObject({
      result: "suppress",
      reason: "muted-task",
    });
    expect(first.decisions.find((decision) => decision.taskId === reduced.taskId)?.result).toBe("send");
    expect(reducedLater.decisions[0]).toMatchObject({ result: "delay", reason: "reduced-frequency" });
  });

  it("uses one selected pet and switching pet changes delivery only", () => {
    const stateStorage = storage();
    const triggerEngine = engine(stateStorage);
    const first = candidate("task-pet", "买牛奶", at(8));
    triggerEngine.setTaskPreference(first.taskId, { preferredPetId: "black-cat" }, at(7));

    const evaluation = triggerEngine.evaluate([first], at(8));
    const duplicate = triggerEngine.evaluate([
      candidate("task-pet", "买牛奶", at(8), { reminderInstanceId: "instance-pet-next" }),
    ], at(8, 1));

    expect(evaluation.decisions[0]).toMatchObject({ taskId: "task-pet", petId: "black-cat", result: "send" });
    expect(evaluation.deliveries).toHaveLength(1);
    expect(triggerEngine.getLastDeliveryContext(at(8))).toMatchObject({
      taskIds: ["task-pet"],
      taskTitles: ["买牛奶"],
      petId: "black-cat",
    });
    expect(duplicate.deliveries).toHaveLength(0);
    expect(duplicate.decisions[0].reason).toBe("already-delivered");
  });

  it("parses the three user controls without making them task copies", () => {
    expect(parseProactivePreferenceCommand("别再提醒这件事")).toEqual({ action: "mute", targetTitle: null });
    expect(parseProactivePreferenceCommand("少提醒一点")).toEqual({ action: "reduce", targetTitle: null });
    expect(parseProactivePreferenceCommand("换一只宠物提醒")).toEqual({ action: "switch_pet", targetTitle: null });
    expect(parseProactivePreferenceCommand("少提醒一点交报告")).toEqual({ action: "reduce", targetTitle: "交报告" });
    expect(parseProactivePreferenceCommand("换一只宠物提醒交报告")).toEqual({ action: "switch_pet", targetTitle: "交报告" });
    expect(taskCandidateFromTask(
      { id: "task-1", title: "交报告", priority: "normal", status: "pending", deletedAt: null },
      { id: "reminder-1" },
      { id: "instance-1", scheduledAt: at(8).toISOString(), triggeredAt: at(8).toISOString(), status: "triggered" },
    ).taskId).toBe("task-1");
  });
});
