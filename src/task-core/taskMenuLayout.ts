import type { Bounds } from "../pet-core/interaction";
import {
  getWindowPositionForPhysicalPetAnchor,
  type PetViewport,
  type PhysicalPetAnchor,
  type WindowSize,
  type WorkArea,
} from "../pet-core/platform";
import { PET_WINDOW_HEIGHT, PET_WINDOW_WIDTH } from "../pet-core/visual";

export type TaskMenuPlacement = "right" | "left";

export type TaskMenuLayout = {
  placement: TaskMenuPlacement;
  windowSize: WindowSize;
  petViewport: PetViewport;
  menuPosition: {
    x: number;
    y: number;
  };
};

export type TaskMenuPlacementContext = {
  anchor: PhysicalPetAnchor;
  scaleFactor: number;
  workArea: WorkArea;
};

export const TASK_MENU_GAP_PX = 12;
export const TASK_MENU_WIDTH = 174;
export const TASK_MENU_HEIGHT = 204;

export function buildTaskMenuLayout(
  petVisibleBounds: Bounds,
  placement: TaskMenuPlacement,
): TaskMenuLayout {
  const menuTop = Math.max(
    0,
    Math.round(
      petVisibleBounds.y +
        petVisibleBounds.height / 2 -
        TASK_MENU_HEIGHT / 2,
    ),
  );
  const menuLeft = placement === "right"
    ? Math.round(petVisibleBounds.x + petVisibleBounds.width + TASK_MENU_GAP_PX)
    : 0;
  const petViewportX = placement === "right"
    ? 0
    : Math.round(TASK_MENU_WIDTH + TASK_MENU_GAP_PX - petVisibleBounds.x);
  const windowWidth = placement === "right"
    ? menuLeft + TASK_MENU_WIDTH
    : petViewportX + PET_WINDOW_WIDTH;
  const windowHeight = Math.max(PET_WINDOW_HEIGHT, menuTop + TASK_MENU_HEIGHT);

  return {
    placement,
    windowSize: { width: windowWidth, height: windowHeight },
    petViewport: {
      x: petViewportX,
      y: 0,
      width: PET_WINDOW_WIDTH,
      height: PET_WINDOW_HEIGHT,
    },
    menuPosition: {
      x: menuLeft,
      y: menuTop,
    },
  };
}

function taskMenuLayoutFits(
  layout: TaskMenuLayout,
  context: TaskMenuPlacementContext,
): boolean {
  return getTaskMenuHorizontalOverflow(layout, context) === 0;
}

function getTaskMenuHorizontalOverflow(
  layout: TaskMenuLayout,
  context: TaskMenuPlacementContext,
): number {
  const position = getWindowPositionForPhysicalPetAnchor(
    context.anchor,
    layout.petViewport,
    context.scaleFactor,
  );
  const width = Math.round(layout.windowSize.width * context.scaleFactor);
  const workAreaRight = context.workArea.position.x + context.workArea.size.width;
  const leftOverflow = Math.max(0, context.workArea.position.x - position.x);
  const rightOverflow = Math.max(0, position.x + width - workAreaRight);

  return leftOverflow + rightOverflow;
}

export function chooseTaskMenuPlacement(
  petVisibleBounds: Bounds,
  context: TaskMenuPlacementContext | null,
  preferredPlacement: TaskMenuPlacement = "right",
): TaskMenuPlacement {
  if (!context) return preferredPlacement;
  const alternatePlacement = preferredPlacement === "right" ? "left" : "right";
  const preferredLayout = buildTaskMenuLayout(
    petVisibleBounds,
    preferredPlacement,
  );
  if (taskMenuLayoutFits(preferredLayout, context)) return preferredPlacement;

  const alternateLayout = buildTaskMenuLayout(
    petVisibleBounds,
    alternatePlacement,
  );
  if (taskMenuLayoutFits(alternateLayout, context)) return alternatePlacement;

  // When the pet is close to an edge, both expanded footprints may overflow
  // slightly. Pick the side that needs the least clamping so the pet does not
  // jump across the desktop just because the menu opened.
  return getTaskMenuHorizontalOverflow(alternateLayout, context) <
    getTaskMenuHorizontalOverflow(preferredLayout, context)
    ? alternatePlacement
    : preferredPlacement;
}
