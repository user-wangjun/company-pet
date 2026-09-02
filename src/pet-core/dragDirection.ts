import type { PetFacing } from "./petInteractionManifest";

export const DRAG_DIRECTION_THRESHOLD_LOGICAL_PX = 8;

export type DragDirectionState = {
  facing: PetFacing;
  anchorPhysicalX: number;
};

export function shouldReturnToIdleImmediatelyAfterDragLanding(
  landingHoldMs: number | undefined,
): boolean {
  return landingHoldMs !== undefined && Number.isFinite(landingHoldMs) && landingHoldMs <= 0;
}

export function resolveDragLandingIdleStartFrame(
  landingEndsOnIdleFirst: boolean | undefined,
  idleFrameCount: number,
  configuredStartFrame?: number,
): number {
  if (configuredStartFrame !== undefined && idleFrameCount > 0) {
    const safeConfiguredStartFrame = Number.isFinite(configuredStartFrame)
      ? Math.max(0, Math.floor(configuredStartFrame))
      : 0;
    return Math.min(safeConfiguredStartFrame, idleFrameCount - 1);
  }
  return landingEndsOnIdleFirst === true && idleFrameCount > 1 ? 1 : 0;
}

export function resolveDragLoopFrameIndex(
  currentFrame: number,
  previousTextureCount: number,
  takeoffFrameCount: number,
  loopFrameCount: number,
): number {
  if (loopFrameCount <= 0 || !Number.isFinite(loopFrameCount)) return 0;

  const safeCurrentFrame = Number.isFinite(currentFrame)
    ? Math.max(0, Math.floor(currentFrame))
    : 0;
  const safeTextureCount = Number.isFinite(previousTextureCount)
    ? Math.max(0, Math.floor(previousTextureCount))
    : 0;
  const safeTakeoffFrameCount = Number.isFinite(takeoffFrameCount)
    ? Math.max(0, Math.floor(takeoffFrameCount))
    : 0;
  const loopOffset =
    safeTextureCount > loopFrameCount
      ? Math.max(0, safeCurrentFrame - safeTakeoffFrameCount)
      : safeCurrentFrame;

  return ((loopOffset % loopFrameCount) + loopFrameCount) % loopFrameCount;
}

export function createDragDirectionState(
  facing: PetFacing,
  pointerPhysicalX: number,
): DragDirectionState {
  return { facing, anchorPhysicalX: pointerPhysicalX };
}

export function updateDragDirection(
  state: DragDirectionState,
  pointerPhysicalX: number,
  scaleFactor: number,
): DragDirectionState {
  const safeScaleFactor = scaleFactor > 0 ? scaleFactor : 1;
  const logicalDelta =
    (pointerPhysicalX - state.anchorPhysicalX) / safeScaleFactor;

  if (Math.abs(logicalDelta) < DRAG_DIRECTION_THRESHOLD_LOGICAL_PX) {
    return state;
  }

  return {
    facing: logicalDelta < 0 ? "left" : "right",
    anchorPhysicalX: pointerPhysicalX,
  };
}
