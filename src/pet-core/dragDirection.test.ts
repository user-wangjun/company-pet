import { describe, expect, test } from "vitest";
import {
  createDragDirectionState,
  resolveDragLandingIdleStartFrame,
  resolveDragLoopFrameIndex,
  shouldReturnToIdleImmediatelyAfterDragLanding,
  updateDragDirection,
} from "./dragDirection";

describe("drag direction", () => {
  test("turns right after eight logical pixels", () => {
    const state = createDragDirectionState("left", 100);

    expect(updateDragDirection(state, 107, 1).facing).toBe("left");
    expect(updateDragDirection(state, 108, 1).facing).toBe("right");
  });

  test("turns left after eight logical pixels", () => {
    const state = createDragDirectionState("right", 100);

    expect(updateDragDirection(state, 92, 1).facing).toBe("left");
  });

  test("converts physical movement to logical movement on high DPI", () => {
    const state = createDragDirectionState("left", 200);

    expect(updateDragDirection(state, 215, 2).facing).toBe("left");
    expect(updateDragDirection(state, 216, 2).facing).toBe("right");
  });

  test("keeps the last facing during vertical or jitter movement", () => {
    const state = createDragDirectionState("right", 100);
    const jitter = updateDragDirection(state, 96, 1);

    expect(jitter.facing).toBe("right");
    expect(jitter.anchorPhysicalX).toBe(100);
  });

  test("uses a safe scale factor when the reported scale is invalid", () => {
    const state = createDragDirectionState("left", 100);

    expect(updateDragDirection(state, 108, 0).facing).toBe("right");
    expect(updateDragDirection(state, 92, -1).facing).toBe("left");
  });

  test("preserves loop phase when switching direction during the loop", () => {
    expect(resolveDragLoopFrameIndex(7, 14, 5, 14)).toBe(7);
  });

  test("maps the combined takeoff texture list into its loop phase", () => {
    expect(resolveDragLoopFrameIndex(10, 19, 5, 14)).toBe(5);
  });

  test("starts at the first loop frame when direction changes during takeoff", () => {
    expect(resolveDragLoopFrameIndex(3, 19, 5, 14)).toBe(0);
  });

  test("returns to idle immediately when drag landing hold is zero", () => {
    expect(shouldReturnToIdleImmediatelyAfterDragLanding(0)).toBe(true);
    expect(shouldReturnToIdleImmediatelyAfterDragLanding(1)).toBe(false);
    expect(shouldReturnToIdleImmediatelyAfterDragLanding(undefined)).toBe(false);
  });

  test("skips the duplicated idle first frame after an explicit landing handoff", () => {
    expect(resolveDragLandingIdleStartFrame(true, 24)).toBe(1);
    expect(resolveDragLandingIdleStartFrame(false, 24)).toBe(0);
    expect(resolveDragLandingIdleStartFrame(true, 1)).toBe(0);
  });

  test("uses the first non-repeated idle frame when the handoff declares it", () => {
    expect(resolveDragLandingIdleStartFrame(true, 24, 8)).toBe(8);
    expect(resolveDragLandingIdleStartFrame(true, 24, 99)).toBe(23);
  });

});
