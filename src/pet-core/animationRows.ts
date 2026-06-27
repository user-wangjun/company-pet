import type { PetAnimationSpec } from "./petInteractionManifest";

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
