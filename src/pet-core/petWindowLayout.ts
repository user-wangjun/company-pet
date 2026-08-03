import type { Bounds } from "./interaction";
import type { PetViewport, WindowSize } from "./platform";
import {
  PET_BUBBLE_BOTTOM_PX,
  PET_WINDOW_HEIGHT,
  PET_WINDOW_WIDTH,
} from "./visual";

export type PetBubbleSize = {
  width: number;
  height: number;
  tailHeight?: number;
};

export type PetWindowLayout = {
  windowSize: WindowSize;
  petViewport: PetViewport;
  bubbleCenterX: number;
  bubbleBottom: number;
  petHitArea: Bounds;
};

const WINDOW_PADDING_PX = 8;
const HIT_AREA_PADDING_PX = 3;

function finitePositive(value: number, fallback: number): number {
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function expandBounds(bounds: Bounds, padding: number): Bounds {
  return {
    x: bounds.x - padding,
    y: bounds.y - padding,
    width: bounds.width + padding * 2,
    height: bounds.height + padding * 2,
  };
}

/**
 * Builds a compact native-window footprint around the pet and any visible
 * bubble. Coordinates are kept relative to the old 165x215 pet design so the
 * sprite can be cropped without changing its screen-space pose.
 */
export function buildPetWindowLayout(
  petVisibleBounds: Bounds,
  bubble: PetBubbleSize | null = null,
): PetWindowLayout {
  const petBounds = {
    x: Number.isFinite(petVisibleBounds.x) ? petVisibleBounds.x : 0,
    y: Number.isFinite(petVisibleBounds.y) ? petVisibleBounds.y : 0,
    width: finitePositive(petVisibleBounds.width, 1),
    height: finitePositive(petVisibleBounds.height, 1),
  };
  const bubbleWidth = bubble ? finitePositive(bubble.width, 1) : 0;
  const bubbleHeight = bubble ? finitePositive(bubble.height, 1) : 0;
  const bubbleTailHeight = bubble
    ? Math.max(0, Number.isFinite(bubble.tailHeight) ? bubble.tailHeight ?? 0 : 0)
    : 0;
  const bubbleBox = bubble
    ? {
        x: PET_WINDOW_WIDTH / 2 - bubbleWidth / 2,
        y: PET_WINDOW_HEIGHT - PET_BUBBLE_BOTTOM_PX - bubbleHeight,
        width: bubbleWidth,
        height: bubbleHeight + bubbleTailHeight,
      }
    : null;

  const contentLeft = Math.min(
    petBounds.x,
    bubbleBox?.x ?? Number.POSITIVE_INFINITY,
  );
  const contentTop = Math.min(
    petBounds.y,
    bubbleBox?.y ?? Number.POSITIVE_INFINITY,
  );
  const contentRight = Math.max(
    petBounds.x + petBounds.width,
    bubbleBox ? bubbleBox.x + bubbleBox.width : Number.NEGATIVE_INFINITY,
  );
  const contentBottom = Math.max(
    petBounds.y + petBounds.height,
    bubbleBox ? bubbleBox.y + bubbleBox.height : Number.NEGATIVE_INFINITY,
  );

  const left = Math.floor(contentLeft - WINDOW_PADDING_PX);
  const top = Math.floor(contentTop - WINDOW_PADDING_PX);
  const right = Math.ceil(contentRight + WINDOW_PADDING_PX);
  const bottom = Math.ceil(contentBottom + WINDOW_PADDING_PX);
  const windowSize = {
    width: Math.max(1, right - left),
    height: Math.max(1, bottom - top),
  };
  const hitArea = expandBounds(petBounds, HIT_AREA_PADDING_PX);

  return {
    windowSize,
    petViewport: {
      x: -left,
      y: -top,
      width: PET_WINDOW_WIDTH,
      height: PET_WINDOW_HEIGHT,
    },
    bubbleCenterX: PET_WINDOW_WIDTH / 2 - left,
    bubbleBottom: bottom - (PET_WINDOW_HEIGHT - PET_BUBBLE_BOTTOM_PX),
    petHitArea: {
      x: hitArea.x - left,
      y: hitArea.y - top,
      width: hitArea.width,
      height: hitArea.height,
    },
  };
}
