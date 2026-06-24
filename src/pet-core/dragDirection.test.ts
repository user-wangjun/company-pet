import { describe, expect, test } from "vitest";
import {
  createDragDirectionState,
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
});
