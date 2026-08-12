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

function evaluateAndConfirm(
  triggerEngine: ReturnType<typeof createProactiveTriggerEngine>,
  candidates: readonly ProactiveTaskCandidate[],
  now: Date,
) {
  const evaluation = triggerEngine.evaluateEligibility(candidates, now);
  const eligible = evaluation.eligibleDeliveries[0];
  if (!eligible) return { evaluation, confirmation: null };
  const reservation = triggerEngine.reserveDelivery(eligible.decision, eligible.candidates, now);
  expect(reservation.status).toBe("reserved");
  const confirmation = triggerEngine.confirmDelivery(reservation, eligible.candidates, now);
  expect(confirmation.status).toBe("confirmed");
  return { evaluation, confirmation };
}

describe("provider-independent proactive trigger engine", () => {
  it("delivers the same task at most once in one time window", () => {
    const stateStorage = storage();
    const triggerEngine = engine(stateStorage);
    const first = candidate("task-1", "交报告", at(8));

    const { evaluation: firstEvaluation } = evaluateAndConfirm(triggerEngine, [first], at(8));
    const secondEvaluation = triggerEngine.evaluateEligibility([first], at(8, 5));

    expect(firstEvaluation.eligibleDeliveries).toHaveLength(1);
    expect(firstEvaluation.decisions[0]).toMatchObject({ result: "send", actualDelivery: false, deliveryStatus: "allowed" });
    expect(secondEvaluation.decisions[0]).toMatchObject({
      result: "suppress",
      reason: "already-delivered",
      actualDelivery: false,
    });
  });

  it("keeps the App legacy deliveries projection while transactional evaluation stays truthful", () => {
    const legacyEngine = engine(storage());
    const legacyEvaluation = legacyEngine.evaluate([
      candidate("legacy-app", "交报告", at(8)),
    ], at(8));

    expect(legacyEvaluation.deliveries).toHaveLength(1);
    expect(legacyEvaluation.deliveries[0]?.decision).toMatchObject({
      result: "send",
      actualDelivery: true,
      deliveryStatus: "delivered",
    });
    expect(legacyEngine.getLastDeliveryContext(at(8))).toMatchObject({
      taskIds: ["legacy-app"],
    });

    const transactionalEngine = engine(storage());
    const transactionalEvaluation = transactionalEngine.evaluateEligibility([
      candidate("transactional-only", "浇花", at(8)),
    ], at(8));

    expect(transactionalEvaluation.eligibleDeliveries).toHaveLength(1);
    expect(transactionalEvaluation.deliveries).toHaveLength(0);
    expect(transactionalEvaluation.eligibleDeliveries[0]?.decision.actualDelivery).toBe(false);
    expect(transactionalEngine.getLastDeliveryContext(at(8))).toBeNull();
  });

  it("suppresses a candidate during quiet hours", () => {
    const stateStorage = storage();
    const triggerEngine = createProactiveTriggerEngine({
      storage: stateStorage,
      activePetId: "xiaoju-cat",
      quietHours: { startTime: "23:00", endTime: "07:00" },
    });

    const evaluation = triggerEngine.evaluateEligibility([candidate("task-quiet", "睡觉", at(23, 30))], at(23, 30));

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

    expect(triggerEngine.evaluateEligibility([task], at(23, 30)).decisions[0].reason).toBe("quiet-hours");
    expect(triggerEngine.evaluateEligibility([task], new Date(2026, 7, 3, 8, 0, 0, 0)).decisions[0].result).toBe("send");
  });

  it("suppresses after the user-level daily limit", () => {
    const stateStorage = storage();
    const triggerEngine = createProactiveTriggerEngine({
      storage: stateStorage,
      activePetId: "xiaoju-cat",
      dailyLimit: 1,
      quietHours: QUIET_DISABLED,
    });

    evaluateAndConfirm(triggerEngine, [candidate("task-limit-1", "交报告", at(8))], at(8));
    const evaluation = triggerEngine.evaluateEligibility([candidate("task-limit-2", "浇花", at(9))], at(9));

    expect(evaluation.decisions[0]).toMatchObject({ result: "suppress", reason: "daily-limit" });
  });

  it("persists delivery, ignore, delivery, ignore, and then applies backoff", () => {
    const stateStorage = storage();
    const triggerEngine = engine(stateStorage);
    const first = candidate("task-ignore", "整理报告", at(8));
    const { evaluation: firstEvaluation } = evaluateAndConfirm(triggerEngine, [first], at(8));
    expect(firstEvaluation.decisions[0]).toMatchObject({ result: "send", actualDelivery: false, deliveryStatus: "allowed" });
    triggerEngine.recordIgnored(first.taskId, at(8, 1));

    const second = candidate("task-ignore", "整理报告", at(12, 1), {
      reminderInstanceId: "instance-ignore-second",
    });
    const { evaluation: secondEvaluation } = evaluateAndConfirm(triggerEngine, [second], at(12, 1));
    expect(secondEvaluation.decisions[0]).toMatchObject({ result: "send", actualDelivery: false, deliveryStatus: "allowed" });
    triggerEngine.recordIgnored(second.taskId, at(12, 2));

    const evaluation = triggerEngine.evaluateEligibility([
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

    const { evaluation, confirmation } = evaluateAndConfirm(triggerEngine, tasks, at(8));

    expect(evaluation.eligibleDeliveries).toHaveLength(1);
    expect(evaluation.eligibleDeliveries[0].decision.result).toBe("aggregate");
    expect(evaluation.eligibleDeliveries[0].decision.aggregatedTaskIds).toEqual(expect.arrayContaining([
      "task-aggregate-1",
      "task-aggregate-2",
    ]));
    expect(evaluation.decisions.filter((decision) => decision.actualDelivery)).toHaveLength(0);
    expect(confirmation?.decisions.filter((decision) => decision.actualDelivery)).toHaveLength(1);
    expect(evaluation.decisions.find((decision) => decision.taskId === "task-aggregate-2")?.reason).toBe("aggregated");
  });

  it("does not generate delivery for completed, cancelled, or deleted tasks", () => {
    const triggerEngine = engine(storage());
    const evaluation = triggerEngine.evaluateEligibility([
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
    evaluateAndConfirm(firstEngine, [first], at(8));

    const restartedEngine = createProactiveTriggerEngine({
      storage: stateStorage,
      activePetId: "xiaoju-cat",
      dailyLimit: 2,
      quietHours: QUIET_DISABLED,
    });
    const nextWindow = restartedEngine.evaluateEligibility([
      candidate("task-restart", "复习", at(9), { reminderInstanceId: "instance-restart-next" }),
    ], at(9));
    const duplicate = restartedEngine.evaluateEligibility([first], at(9, 1));

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
    evaluateAndConfirm(firstEngine, [candidate("task-daily-restart-1", "背单词", at(8))], at(8));

    const restartedEngine = createProactiveTriggerEngine({
      storage: stateStorage,
      activePetId: "xiaoju-cat",
      dailyLimit: 1,
      quietHours: QUIET_DISABLED,
    });
    const evaluation = restartedEngine.evaluateEligibility([
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
    const first = evaluateAndConfirm(triggerEngine, [muted, reduced], at(8)).evaluation;
    const reducedLater = triggerEngine.evaluateEligibility([
      { ...reduced, reminderInstanceId: "instance-reduced-next", scheduledAt: at(9).toISOString() },
    ], at(9));

    expect(first.decisions.find((decision) => decision.taskId === muted.taskId)).toMatchObject({
      result: "suppress",
      reason: "muted-task",
    });
    expect(first.decisions.find((decision) => decision.taskId === reduced.taskId)?.result).toBe("send");
    expect(reducedLater.decisions[0]).toMatchObject({ result: "delay", reason: "reduced-frequency" });
  });

  it("throws instead of returning a candidate when preference persistence is rejected", () => {
    const stateStorage: ProactiveExpressionStorage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(() => {
        throw new Error("storage quota exceeded");
      }),
    };
    const triggerEngine = engine(stateStorage);

    expect(() => triggerEngine.setTaskPreference("task-writer", { mode: "muted" }, at(7)))
      .toThrow("Failed to persist proactive task preference.");
    expect(stateStorage.setItem).toHaveBeenCalledTimes(1);
  });

  it("uses one selected pet and switching pet changes delivery only", () => {
    const stateStorage = storage();
    const triggerEngine = engine(stateStorage);
    const first = candidate("task-pet", "买牛奶", at(8));
    triggerEngine.setTaskPreference(first.taskId, { preferredPetId: "black-cat" }, at(7));

    const { evaluation, confirmation } = evaluateAndConfirm(triggerEngine, [first], at(8));
    const duplicate = triggerEngine.evaluateEligibility([
      candidate("task-pet", "买牛奶", at(8), { reminderInstanceId: "instance-pet-next" }),
    ], at(8, 1));

    expect(evaluation.decisions[0]).toMatchObject({ taskId: "task-pet", petId: "black-cat", result: "send" });
    expect(evaluation.eligibleDeliveries).toHaveLength(1);
    expect(confirmation?.status).toBe("confirmed");
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
