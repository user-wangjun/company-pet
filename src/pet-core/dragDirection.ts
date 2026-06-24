import type { PetFacing } from "./petInteractionManifest";

export const DRAG_DIRECTION_THRESHOLD_LOGICAL_PX = 8;

export type DragDirectionState = {
  facing: PetFacing;
  anchorPhysicalX: number;
};

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
