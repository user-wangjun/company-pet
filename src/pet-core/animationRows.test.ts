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

  test("maps the xiaoju 24-frame production strips to row zero", () => {
    const spec: PetAnimationSpec = {
      row: 0,
      frames: 24,
      speed: 0.96,
      loop: false,
      visualClass: "ordinary",
      scale: 0.84,
      spritesheetPath: "tickle-24.png",
    };

    const rects = buildAnimationFrameRects(spec, 192, 208);

    expect(rects).toHaveLength(24);
    expect(rects[0]).toEqual({ x: 0, y: 0, width: 192, height: 208 });
    expect(rects[23]).toEqual({ x: 4416, y: 0, width: 192, height: 208 });
  });
});
