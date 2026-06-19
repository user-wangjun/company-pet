export const APP_DISPLAY_NAME = "愈心桌宠";
export const APP_WINDOW_TITLE = APP_DISPLAY_NAME;
export const PLATFORM_START_OPEN = true;
export const INITIAL_WINDOW_MARGIN_PX = 24;

export type WindowSize = {
  width: number;
  height: number;
};

export type WindowPosition = {
  x: number;
  y: number;
};

export type WorkArea = {
  position: WindowPosition;
  size: WindowSize;
};

export function getInitialPetWindowPosition(
  workArea: WorkArea,
  windowSize: WindowSize,
  margin = INITIAL_WINDOW_MARGIN_PX,
): WindowPosition {
  return {
    x: Math.max(
      workArea.position.x,
      workArea.position.x + workArea.size.width - windowSize.width - margin,
    ),
    y: Math.max(
      workArea.position.y,
      workArea.position.y + workArea.size.height - windowSize.height - margin,
    ),
  };
}

export function getCenteredWindowPosition(
  workArea: WorkArea,
  windowSize: WindowSize,
): WindowPosition {
  return {
    x: Math.round(
      workArea.position.x + (workArea.size.width - windowSize.width) / 2,
    ),
    y: Math.round(
      workArea.position.y + (workArea.size.height - windowSize.height) / 2,
    ),
  };
}
