import type { PetAnimationSpec } from "./petInteractionManifest";

/** Existing platform atlas format, shared by desktop and room compatibility. */
export const LEGACY_SPRITE_CELL_WIDTH = 192;
export const LEGACY_SPRITE_CELL_HEIGHT = 208;

export type AnimationFrameRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export function buildAnimationFrameRects(
  spec: PetAnimationSpec,
  cellWidth: number,
  cellHeight: number,
): AnimationFrameRect[] {
  return Array.from({ length: spec.frames }, (_, index) => ({
    x: index * cellWidth,
    y: spec.row * cellHeight,
    width: cellWidth,
    height: cellHeight,
  }));
}
