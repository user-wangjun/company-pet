import { describe, expect, test } from "vitest";
import {
  buildPetWindowLayout,
  getPetReminderWindowSize,
} from "./petWindowLayout";

const petVisibleBounds = { x: 40, y: 108, width: 85, height: 100 };

describe("compact pet window layout", () => {
  test("rig head anchor reserves the full bubble and keeps its tail above the character", () => {
    const bounds = {x: 42, y: 39, width: 81, height: 170};
    const anchor = 215 - bounds.y + 8;
    for (const height of [31, 180, 360]) {
      const layout = buildPetWindowLayout(bounds, {width: 164, height, tailHeight: 8}, anchor);
      const bubbleTop = layout.windowSize.height - layout.bubbleBottom - height;
      const bubbleTailBottom = layout.windowSize.height - layout.bubbleBottom + 8;
      expect(bubbleTop).toBeGreaterThanOrEqual(8);
      expect(bubbleTailBottom).toBe(bounds.y + layout.petViewport.y);
      expect(layout.windowSize.height).toBeGreaterThanOrEqual(height + bounds.height + 24);
      expect(layout.petHitArea.y + layout.petHitArea.height).toBeLessThan(layout.windowSize.height);
    }
    expect(getPetReminderWindowSize({width: 164, height: 360}, {width: 240, height: 450}, anchor)).toEqual({width: 240, height: 552});
  });
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

  test("adds height when an action bubble would reach the reminder window edge", () => {
    expect(
      getPetReminderWindowSize(
        { width: 164, height: 360, tailHeight: 8 },
        { width: 240, height: 450 },
      ),
    ).toEqual({ width: 240, height: 476 });
  });

  test("keeps the normal reminder footprint for short bubbles", () => {
    expect(
      getPetReminderWindowSize(
        { width: 164, height: 180, tailHeight: 8 },
        { width: 240, height: 450 },
      ),
    ).toEqual({ width: 240, height: 450 });
  });
});
