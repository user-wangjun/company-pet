import { describe, expect, test } from "vitest";
import type { PetAnimationSpec } from "./petInteractionManifest";
import {
  ANIMATION_ROWS,
  appendPetAnimationFinishFrame,
  buildAnimationFrameRects,
  buildDragLandingFrameIndexes,
  buildPetDragLandingFrames,
  getPetDragFramePlan,
  getPetAnimationRowSpec,
} from "./animationRows";

describe("runtime animation row mapping", () => {
  test("builds only declared effective frame rectangles", () => {
    const spec: PetAnimationSpec = {
      row: 3,
      frames: 4,
      speed: 0.16,
      loop: false,
      visualClass: "ordinary",
    };

    expect(buildAnimationFrameRects(spec, 192, 208)).toEqual([
      { x: 0, y: 624, width: 192, height: 208 },
      { x: 192, y: 624, width: 192, height: 208 },
      { x: 384, y: 624, width: 192, height: 208 },
      { x: 576, y: 624, width: 192, height: 208 },
    ]);
  });

  test("builds drag landing indexes without pet-id branches", () => {
    expect(
      buildDragLandingFrameIndexes({
        currentFrame: 4,
        approachFrame: 6,
        landingFrame: 7,
      }),
    ).toEqual([4, 6, 7]);
  });
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
  test("uses suan-bird drag frames as takeoff, flight loop, and landing", () => {
    expect(getPetDragFramePlan("suan-bird")).toEqual({
      takeoffFrame: 0,
      loopStartFrame: 1,
      loopFrameCount: 6,
      landingApproachFrame: 6,
      landingFrame: 7,
      landingTransitionSpeed: 0.25,
    });
    expect(getPetDragFramePlan("xiaoju-cat")).toBeNull();
  });

  test("builds a smooth suan-bird landing sequence from the current flight pose", () => {
    const plan = getPetDragFramePlan("suan-bird");

    expect(
      buildPetDragLandingFrames(
        "current-flight",
        [
          "takeoff",
          "flight-2",
          "flight-3",
          "flight-4",
          "flight-5",
          "flight-6",
          "flight-7",
          "landing",
        ],
        plan,
      ),
    ).toEqual(["current-flight", "flight-7", "landing"]);
  });

  test("plays the suan-bird double-click row once", () => {
    expect(getPetAnimationRowSpec("suan-bird", "fishChase")).toMatchObject({
      row: 7,
      frames: 8,
      loop: false,
    });
  });

  test("plays the ikun double-click jump row with all 8 atlas frames", () => {
    expect(getPetAnimationRowSpec("ikun", "fishEat")).toMatchObject({
      row: 8,
      frames: 8,
      loop: false,
    });
    expect(getPetAnimationRowSpec("xiaoju-cat", "fishEat")).toMatchObject({
      row: 8,
      frames: 6,
      loop: false,
    });
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
