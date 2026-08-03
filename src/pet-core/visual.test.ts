import { describe, expect, test } from "vitest";
import {
  getPetCanvasPosition,
  getPetAnimationTransform,
  PET_VISUAL_SCALE,
  PET_WINDOW_HEIGHT,
  PET_WINDOW_WIDTH,
} from "./visual";

describe("desktop pet visual sizing", () => {
  test("resolves scale, offset, and left mirror from animation specs", () => {
    expect(
      getPetAnimationTransform(
        {
          row: 1,
          frames: 8,
          speed: 0.2,
          loop: true,
          visualClass: "ordinary",
          scale: 0.83,
          offsetX: 2,
          offsetY: -3,
        },
        "left",
        "mirror-left",
      ),
    ).toEqual({
      scaleX: -0.3818,
      scaleY: 0.3818,
      offsetX: 2,
      offsetY: -3,
    });
  });

  test("does not mirror real left/right row animations", () => {
    expect(
      getPetAnimationTransform(
        {
          row: 1,
          frames: 8,
          speed: 0.2,
          loop: true,
          visualClass: "ordinary",
          scale: 1,
        },
        "left",
        "rows",
      ),
    ).toEqual({
      scaleX: PET_VISUAL_SCALE,
      scaleY: PET_VISUAL_SCALE,
      offsetX: 0,
      offsetY: 0,
    });
  });
  test("uses a smaller body scale for desktop icon interaction checks", () => {
    expect(PET_VISUAL_SCALE).toBeLessThan(1);
    expect(PET_VISUAL_SCALE).toBeCloseTo(0.46);
  });

  test("matches the transparent desktop pet window size", () => {
    expect(PET_WINDOW_WIDTH).toBe(165);
    expect(PET_WINDOW_HEIGHT).toBe(215);
  });

  test("converts a window-space pet viewport to canvas-local coordinates", () => {
    const reminderViewport = { x: 75, y: 235, width: 165, height: 215 };

    expect(
      getPetCanvasPosition(reminderViewport, { x: 75, y: 235 }),
    ).toEqual({ x: 82.5, y: 209 });
    expect(
      getPetCanvasPosition(
        { x: 146, y: 0, width: 165, height: 215 },
        { x: 0, y: 0 },
        { x: 2, y: -3 },
      ),
    ).toEqual({ x: 230.5, y: 206 });
  });
});
