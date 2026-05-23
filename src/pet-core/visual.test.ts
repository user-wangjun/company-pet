import { describe, expect, test } from "vitest";
import {
  PET_VISUAL_SCALE,
  PET_WINDOW_HEIGHT,
  PET_WINDOW_WIDTH,
  PET_ICON_HUG_SPRITESHEET_PATH,
} from "./visual";

describe("desktop pet visual sizing", () => {
  test("uses a smaller body scale for desktop icon interaction checks", () => {
    expect(PET_VISUAL_SCALE).toBeLessThan(1);
    expect(PET_VISUAL_SCALE).toBeCloseTo(0.46);
  });

  test("keeps the transparent window close to the smaller pet body", () => {
    expect(PET_WINDOW_WIDTH).toBe(165);
    expect(PET_WINDOW_HEIGHT).toBe(155);
  });

  test("uses a dedicated desktop icon hug spritesheet", () => {
    expect(PET_ICON_HUG_SPRITESHEET_PATH).toBe("icon-hug.webp");
  });
});
