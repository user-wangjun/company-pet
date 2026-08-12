import { describe, expect, test } from "vitest";
import { getPhysicalPetAnchor } from "../pet-core/platform";
import {
  buildTaskMenuLayout,
  chooseTaskMenuPlacement,
} from "./taskMenuLayout";

const petVisibleBounds = { x: 40, y: 108, width: 85, height: 100 };
const petViewport = { x: 0, y: 0, width: 165, height: 215 };

describe("task context menu layout", () => {
  test("places the compact menu 12px outside the visible pet edge on the right", () => {
    expect(buildTaskMenuLayout(petVisibleBounds, "right")).toEqual({
      placement: "right",
      windowSize: { width: 311, height: 260 },
      petViewport,
      menuPosition: { x: 137, y: 56 },
    });
  });

  test("flips to the left while preserving the visible-edge gap", () => {
    expect(buildTaskMenuLayout(petVisibleBounds, "left")).toEqual({
      placement: "left",
      windowSize: { width: 311, height: 260 },
      petViewport: { x: 146, y: 0, width: 165, height: 215 },
      menuPosition: { x: 0, y: 56 },
    });
  });

  test("prefers the right side until the work area cannot contain it", () => {
    const centerAnchor = getPhysicalPetAnchor(
      { x: 300, y: 300 },
      petViewport,
      1,
    );
    expect(
      chooseTaskMenuPlacement(petVisibleBounds, {
        anchor: centerAnchor,
        scaleFactor: 1,
        workArea: { position: { x: 0, y: 0 }, size: { width: 1920, height: 1040 } },
      }),
    ).toBe("right");

    const lowerRightAnchor = getPhysicalPetAnchor(
      { x: 1731, y: 801 },
      petViewport,
      1,
    );
    expect(
      chooseTaskMenuPlacement(petVisibleBounds, {
        anchor: lowerRightAnchor,
        scaleFactor: 1,
        workArea: { position: { x: 0, y: 0 }, size: { width: 1920, height: 1040 } },
      }),
    ).toBe("left");
  });

  test("chooses the side with less edge overflow when neither footprint fully fits", () => {
    const compactPetViewport = { x: -32, y: -100, width: 165, height: 215 };
    const anchor = getPhysicalPetAnchor(
      { x: 1795, y: 900 },
      compactPetViewport,
      1,
    );

    expect(
      chooseTaskMenuPlacement(petVisibleBounds, {
        anchor,
        scaleFactor: 1,
        workArea: { position: { x: 0, y: 0 }, size: { width: 1920, height: 1040 } },
      }),
    ).toBe("left");
  });
});
