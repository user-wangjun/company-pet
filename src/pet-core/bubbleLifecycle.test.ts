import { describe, expect, it } from "vitest";
import {
  PLATFORM_FEEDBACK_BUBBLE_MS,
  expireBubbleText,
} from "./bubbleLifecycle";

describe("transient platform feedback bubbles", () => {
  it("expires the feedback that scheduled the timer", () => {
    expect(expireBubbleText("任务已取消", "任务已取消")).toBeNull();
    expect(PLATFORM_FEEDBACK_BUBBLE_MS).toBe(5_000);
  });

  it("does not let an older timer clear a newer bubble", () => {
    expect(expireBubbleText("睡眠提醒", "任务已取消")).toBe("睡眠提醒");
    expect(expireBubbleText(null, "任务已取消")).toBeNull();
  });
});
