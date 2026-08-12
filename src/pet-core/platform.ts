export const APP_DISPLAY_NAME = "愈心桌宠";
export const APP_WINDOW_TITLE = APP_DISPLAY_NAME;
export const PLATFORM_START_OPEN = true;
export const PLATFORM_START_SECTION = "home" as const;
export const INITIAL_WINDOW_MARGIN_PX = 24;

export type PlatformSection = "home" | "tasks" | "pets" | "chat" | "settings";

export type CompanionExitReason =
  | "back"
  | "close"
  | "escape"
  | "outside"
  | "idle"
  | "navigation"
  | "pet-switch"
  | "mutual-surface"
  | "return";

export function resolveRenderedPlatformSection(
  section: PlatformSection,
  companionChatMode: "active" | "inactive",
): PlatformSection {
  return section === "chat" && companionChatMode !== "active"
    ? "home"
    : section;
}

export function resolvePlatformSectionAfterCompanionExit(
  reason: CompanionExitReason,
  requestedSection?: PlatformSection,
): PlatformSection {
  if (reason === "navigation" && requestedSection && requestedSection !== "chat") {
    return requestedSection;
  }

  return "home";
}

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

export type PhysicalPetAnchor = {
  x: number;
  y: number;
};

export type PetViewport = {
  x: number;
  y: number;
  width: number;
  height: number;
};

function safeScaleFactor(scaleFactor: number): number {
  return scaleFactor > 0 ? scaleFactor : 1;
}

export function getPhysicalPetAnchor(
  windowPosition: WindowPosition,
  petViewport: PetViewport,
  scaleFactor: number,
): PhysicalPetAnchor {
  const scale = safeScaleFactor(scaleFactor);

  return {
    x: windowPosition.x + (petViewport.x + petViewport.width / 2) * scale,
    y: windowPosition.y + (petViewport.y + petViewport.height) * scale,
  };
}

export function getWindowPositionForPhysicalPetAnchor(
  anchor: PhysicalPetAnchor,
  petViewport: PetViewport,
  scaleFactor: number,
): WindowPosition {
  const scale = safeScaleFactor(scaleFactor);

  return {
    x: Math.round(anchor.x - (petViewport.x + petViewport.width / 2) * scale),
    y: Math.round(anchor.y - (petViewport.y + petViewport.height) * scale),
  };
}

export function clampWindowPositionToWorkArea(
  position: WindowPosition,
  windowSize: WindowSize,
  workArea: WorkArea,
): WindowPosition {
  const minX = workArea.position.x;
  const minY = workArea.position.y;
  const maxX = minX + Math.max(0, workArea.size.width - windowSize.width);
  const maxY = minY + Math.max(0, workArea.size.height - windowSize.height);

  return {
    x: Math.min(Math.max(position.x, minX), maxX),
    y: Math.min(Math.max(position.y, minY), maxY),
  };
}

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
