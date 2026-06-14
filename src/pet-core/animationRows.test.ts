import { describe, expect, test } from "vitest";
import { ANIMATION_ROWS, appendPetAnimationFinishFrame } from "./animationRows";

describe("runtime animation row mapping", () => {
  test("maps ikun action rows to complete runtime frame ranges", () => {
    expect(ANIMATION_ROWS).toMatchObject({
      idle: { row: 0, frames: 6, loop: true },
      drag: { row: 1, frames: 8, loop: true },
      tickle: { row: 3, frames: 8, loop: false },
      fishChase: { row: 7, frames: 8, loop: true },
      fishEat: { row: 8, frames: 6, loop: false },
      iconHug: { row: 0, frames: 6, loop: false },
      crouchAlert: { row: 4, frames: 8, loop: true },
      hugFish: { row: 5, frames: 8, loop: true },
      gnawFish: { row: 6, frames: 8, loop: false },
    });
  });

  test("makes dragging only slightly faster than the previous cadence", () => {
    expect(ANIMATION_ROWS.drag.speed).toBe(0.2);
  });

  test("appends the independent finish frame only to ikun single-click throw", () => {
    const atlasFrames = ["09", "10", "11", "12", "13", "14", "15", "16"];

    expect(
      appendPetAnimationFinishFrame(
        "ikun",
        "gnawFish",
        atlasFrames,
        "17-no-ball",
      ),
    ).toEqual([...atlasFrames, "17-no-ball"]);
    expect(
      appendPetAnimationFinishFrame(
        "xiaoju-cat",
        "gnawFish",
        atlasFrames,
        "17-no-ball",
      ),
    ).toEqual(atlasFrames);
    expect(
      appendPetAnimationFinishFrame(
        "ikun",
        "idle",
        atlasFrames,
        "17-no-ball",
      ),
    ).toEqual(atlasFrames);
    expect(
      appendPetAnimationFinishFrame("ikun", "gnawFish", atlasFrames, null),
    ).toEqual(atlasFrames);
  });
});
