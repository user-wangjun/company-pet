import type {
  PetAnimationSpec,
  PetDirectionMode,
  PetFacing,
} from "./petInteractionManifest";

export const PET_VISUAL_SCALE = 0.46;
export const PET_WINDOW_WIDTH = 165;
export const PET_WINDOW_HEIGHT = 215;
export const PET_BUBBLE_BOTTOM_PX = 108;

export function getPetAnimationTransform(
  spec: PetAnimationSpec,
  facing: PetFacing,
  directionMode: PetDirectionMode | "none" = "none",
): {
  scaleX: number;
  scaleY: number;
  offsetX: number;
  offsetY: number;
} {
  const visualScale = PET_VISUAL_SCALE * (spec.scale ?? 1);
  const mirror = directionMode === "mirror-left" && facing === "left";
  return {
    scaleX: mirror ? -visualScale : visualScale,
    scaleY: visualScale,
    offsetX: spec.offsetX ?? 0,
    offsetY: spec.offsetY ?? 0,
  };
}
