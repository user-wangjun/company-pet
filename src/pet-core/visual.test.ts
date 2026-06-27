import { describe, expect, test } from "vitest";
import {
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
});
