import { describe, expect, it } from "vitest";
import {
  canRenderProactiveTaskDelivery,
  planProactiveTaskDeliveryRoute,
  resolveProactiveTaskDelivery,
} from "./proactiveDelivery";
import type { ProactiveTaskCandidate, ProactiveTriggerDecision } from "./proactiveTriggerEngine";

const candidate: ProactiveTaskCandidate = {
  taskId: "task-1",
  reminderId: "reminder-1",
  reminderInstanceId: "instance-1",
  title: "交报告",
  priority: "normal",
  taskStatus: "pending",
  deletedAt: null,
  scheduledAt: "2026-08-02T08:00:00.000Z",
  triggeredAt: "2026-08-02T08:00:00.000Z",
  status: "triggered",
};

const decision: ProactiveTriggerDecision = {
  taskId: "task-1",
  reminderInstanceId: "instance-1",
  candidateKey: "task-1|2026-08-02T08:00:00.000Z",
  result: "send",
  score: 0.68,
  priority: "normal",
  reason: "allowed",
  explanation: "通过门禁",
  nextEligibleAt: null,
  petId: "black-cat",
  actualDelivery: true,
};

describe("proactive task delivery", () => {
  it("keeps pet expression separate from the task fact and uses the selected pet", () => {
    const delivery = resolveProactiveTaskDelivery(decision, [candidate], {
      status: "ready",
      petId: "black-cat",
      config: {
        version: 1,
        scenes: { taskDue: { texts: ["黑猫来提醒你啦。"] } },
      },
    });

    expect(delivery).toMatchObject({ petId: "black-cat", text: "黑猫来提醒你啦。", taskIds: ["task-1"] });
    expect(candidate.title).toBe("交报告");
  });

  it("requires an explicit switch before a non-active preferred pet can deliver", () => {
    const delivery = resolveProactiveTaskDelivery(decision, [candidate], undefined);

    expect(planProactiveTaskDeliveryRoute(decision, "xiaoju-cat", ["xiaoju-cat", "black-cat"])).toEqual({
      status: "switch",
      activePetId: "xiaoju-cat",
      targetPetId: "black-cat",
    });
    expect(canRenderProactiveTaskDelivery(delivery, "xiaoju-cat")).toBe(false);
    expect(canRenderProactiveTaskDelivery(delivery, "black-cat")).toBe(true);
    expect(planProactiveTaskDeliveryRoute(decision, "black-cat", ["xiaoju-cat", "black-cat"]).status).toBe("deliver");
  });

  it("never falls back to an unavailable pet identity", () => {
    expect(planProactiveTaskDeliveryRoute(decision, "xiaoju-cat", ["xiaoju-cat"])).toMatchObject({
      status: "unavailable",
      targetPetId: "black-cat",
    });
  });
});
