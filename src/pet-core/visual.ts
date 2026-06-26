import type { RuntimeAnimationName } from "./interaction";
import type { PetManifest } from "./petAssets";
import type {
  PetAnimationSpec,
  PetDirectionMode,
  PetFacing,
} from "./petInteractionManifest";

export const PET_VISUAL_SCALE = 0.46;
export const PET_WINDOW_WIDTH = 165;
export const PET_WINDOW_HEIGHT = 215;
export const PET_BUBBLE_BOTTOM_PX = 108;
export const PET_ICON_HUG_SPRITESHEET_PATH = "icon-hug.webp";

export function getPetAnimationVisualScale(
  manifest: Pick<PetManifest, "animationScales"> | null | undefined,
  animationName: RuntimeAnimationName,
): number {
  const multiplier = manifest?.animationScales?.[animationName];

  if (typeof multiplier !== "number" || !Number.isFinite(multiplier)) {
    return PET_VISUAL_SCALE;
  }

  if (multiplier <= 0) {
    return PET_VISUAL_SCALE;
  }

  return PET_VISUAL_SCALE * multiplier;
}
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
