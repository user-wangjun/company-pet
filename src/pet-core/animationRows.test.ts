import { describe, expect, test } from "vitest";
import { ANIMATION_ROWS } from "./animationRows";

describe("runtime animation row mapping", () => {
  test("maps ikun action rows to complete runtime frame ranges", () => {
    expect(ANIMATION_ROWS).toMatchObject({
      idle: { row: 0, frames: 6, loop: true },
      drag: { row: 1, frames: 8, loop: true },
      tickle: { row: 3, frames: 8, loop: false },
      fishChase: { row: 7, frames: 8, loop: false },
      fishEat: { row: 8, frames: 6, loop: false },
      iconHug: { row: 0, frames: 6, loop: false },
      crouchAlert: { row: 4, frames: 8, loop: true },
      hugFish: { row: 5, frames: 8, loop: true },
      gnawFish: { row: 6, frames: 8, loop: false },
    });
  });
});
