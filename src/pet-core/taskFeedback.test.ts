import { describe, expect, it } from "vitest";
import { resolveTaskFeedback, type TaskFeedbackPackage } from "./taskFeedback";

describe("task feedback", () => {
  it("uses package-local scene content with deterministic selection", () => {
    const packageState: TaskFeedbackPackage = { status: "ready", petId: "demo", config: {
      version: 1,
      scenes: { taskCreated: { texts: ["记下啦", "放心交给我"], action: "nod" } },
    } };
    expect(resolveTaskFeedback(packageState, "taskCreated", "已记录", () => 0.9)).toMatchObject({ text: "放心交给我", action: "nod" });
  });

  it("falls back without blocking task behavior", () => {
    expect(resolveTaskFeedback({ status: "failed", petId: "demo" }, "taskDue", "到时间啦").text).toBe("到时间啦");
  });

  it("uses legacy dailyReview copy for the at-least-half tier", () => {
    const packageState: TaskFeedbackPackage = { status: "ready", petId: "demo", config: {
      version: 1,
      scenes: { dailyReview: { texts: ["旧版庆祝文案"] } },
    } };
    expect(resolveTaskFeedback(packageState, "dailyReviewAtLeastHalf", "通用文案").text).toBe("旧版庆祝文案");
    expect(resolveTaskFeedback(packageState, "dailyReviewBelowHalf", "中性鼓励").text).toBe("中性鼓励");
  });
});
