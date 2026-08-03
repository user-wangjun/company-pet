import { describe, expect, test } from "vitest";
import { buildPetWindowLayout } from "./petWindowLayout";

const petVisibleBounds = { x: 40, y: 108, width: 85, height: 100 };

describe("compact pet window layout", () => {
  test("shrinks the no-bubble window to the visible pet footprint", () => {
    expect(buildPetWindowLayout(petVisibleBounds)).toEqual({
      windowSize: { width: 101, height: 116 },
      petViewport: { x: -32, y: -100, width: 165, height: 215 },
      bubbleCenterX: 50.5,
      bubbleBottom: 109,
      petHitArea: { x: 5, y: 5, width: 91, height: 106 },
    });
  });

  test("expands around a measured bubble while preserving the pet anchor", () => {
    const layout = buildPetWindowLayout(petVisibleBounds, {
      width: 154,
      height: 31,
      tailHeight: 8,
    });

    expect(layout.windowSize).toEqual({ width: 171, height: 148 });
    expect(layout.petViewport).toEqual({
      x: 3,
      y: -68,
      width: 165,
      height: 215,
    });
    expect(layout.bubbleCenterX).toBe(85.5);
    expect(layout.bubbleBottom).toBe(109);
  });

  test("allows a tall chat area to extend above the original pet window", () => {
    const layout = buildPetWindowLayout(petVisibleBounds, {
      width: 154,
      height: 180,
    });

    expect(layout.windowSize.height).toBe(297);
    expect(layout.petViewport.y).toBe(81);
    expect(layout.bubbleBottom).toBe(109);
  });
});
