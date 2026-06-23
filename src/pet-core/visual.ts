import type { RuntimeAnimationName } from "./interaction";
import type { PetManifest } from "./petAssets";

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
