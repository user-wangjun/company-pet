import type {
  PetAnimationSpec,
  PetDirectionMode,
  PetFacing,
} from "./petInteractionManifest";
import type { PetViewport, WindowPosition } from "./platform";

export const PET_VISUAL_SCALE = 0.46;
export const PET_WINDOW_WIDTH = 165;
export const PET_WINDOW_HEIGHT = 215;
export const PET_BUBBLE_BOTTOM_PX = 108;
export const PET_BASELINE_INSET_PX = 6;

export function getPetCanvasPosition(
  petViewport: PetViewport,
  canvasOrigin: WindowPosition,
  offset: { x: number; y: number } = { x: 0, y: 0 },
): WindowPosition {
  return {
    x:
      petViewport.x -
      canvasOrigin.x +
      petViewport.width / 2 +
      offset.x,
    y:
      petViewport.y -
      canvasOrigin.y +
      petViewport.height -
      PET_BASELINE_INSET_PX +
      offset.y,
  };
}

export function getPetAnimationTransform(
  spec: PetAnimationSpec,
  facing: PetFacing,
  directionMode: PetDirectionMode | "mirror-right" | "none" = "none",
): {
  scaleX: number;
  scaleY: number;
  offsetX: number;
  offsetY: number;
} {
  const visualScale = PET_VISUAL_SCALE * (spec.scale ?? 1);
  const mirror =
    (directionMode === "mirror-left" && facing === "left") ||
    (directionMode === "mirror-right" && facing === "right");
  return {
    scaleX: mirror ? -visualScale : visualScale,
    scaleY: visualScale,
    offsetX: spec.offsetX ?? 0,
    offsetY: spec.offsetY ?? 0,
  };
}
