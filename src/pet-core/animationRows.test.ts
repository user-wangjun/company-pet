import { describe, expect, test } from "vitest";
import type { PetAnimationSpec } from "./petInteractionManifest";
import { buildAnimationFrameRects } from "./animationRows";

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
});
