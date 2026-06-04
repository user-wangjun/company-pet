export const DRAG_THRESHOLD_PX = 6;
export const HOVER_EAT_DELAY_MS = 800;
export const DESKTOP_ICON_INTERACTION_DISTANCE_PX = 38;
export const DESKTOP_ICON_INTERACTION_DELAY_MS = 5000;
export const DESKTOP_ICON_INTERACTION_COOLDOWN_MS = 15000;


type DragThresholdInput = {
  startX: number;
  startY: number;
  x: number;
  y: number;
};

type DragWindowPositionInput = {
  startPointerX: number;
  startPointerY: number;
  pointerX: number;
  pointerY: number;
  startWindowX: number;
  startWindowY: number;
  scaleFactor: number;
};

type HoverEatInput = {
  hoverStartedAt: number;
  now: number;
  isDragging: boolean;
};

export type Bounds = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type DesktopIconBounds = Bounds & {
  title: string;
};

export type DesktopIconTarget = DesktopIconBounds & {
  key: string;
  distance: number;
};

export type DesktopIconInteractionState = {
  activeIconKey: string | null;
  firstSeenAt: number | null;
  lastTriggeredAt: number | null;
};

export type RuntimeAnimationName =
  | "idle"
  | "drag"
  | "tickle"
  | "fishChase"
  | "fishEat"
  | "iconHug"
  | "crouchAlert"
  | "hugFish"
  | "gnawFish";

export type RuntimeSoundEvent =
  | RuntimeAnimationName
  | "drag_end"
  | "care_reminder";

export type PetInteractionAction = {
  animation: RuntimeAnimationName;
  sound: RuntimeSoundEvent;
  bubbleText: string;
  durationMs?: number;
};

export type PetSequenceAction = {
  sequence: "hover-fish";
};

type DesktopIconTargetOptions = {
  side?: "any" | "right";
};

type DesktopIconInteractionInput = {
  now: number;
  state: DesktopIconInteractionState;
  target: DesktopIconTarget | null;
};

export function shouldStartDrag(
  input: DragThresholdInput,
  threshold = DRAG_THRESHOLD_PX,
): boolean {
  return Math.hypot(input.x - input.startX, input.y - input.startY) >= threshold;
}

export function isPrimaryButtonPressed(buttons: number): boolean {
  return (buttons & 1) === 1;
}

export function getDraggedWindowPosition(
  input: DragWindowPositionInput,
): { x: number; y: number } {
  return {
    x: Math.round(
      input.startWindowX +
        (input.pointerX - input.startPointerX) * input.scaleFactor,
    ),
    y: Math.round(
      input.startWindowY +
        (input.pointerY - input.startPointerY) * input.scaleFactor,
    ),
  };
}

export function shouldTriggerHoverEat(input: HoverEatInput): boolean {
  return (
    !input.isDragging &&
    input.now - input.hoverStartedAt >= HOVER_EAT_DELAY_MS
  );
}

export function isPointerCancellation(eventType: string): boolean {
  return eventType === "pointercancel";
}

export function getPetContextMenuAction(): "keep-open" {
  return "keep-open";
}

export function getHoverFishAnimationSequence(): ["fishChase", "fishEat"] {
  return ["fishChase", "fishEat"];
}

export function getDesktopIconHugAnimationName(): "iconHug" {
  return "iconHug";
}

const IKUN_PET_ID = "ikun";
const IKUN_IDLE_BUBBLE = "中分头，背带裤，我是ikun你记住";
const IKUN_CARE_REMINDER_BUBBLE = "ikun们，看很久电脑了，要注意休息";

function isIkunPet(petId: string): boolean {
  return petId === IKUN_PET_ID;
}

export function getPetIdleAnimationName(petId: string): RuntimeAnimationName {
  return isIkunPet(petId) ? "crouchAlert" : "idle";
}

export function getPetIdleBubbleText(
  petId: string,
  fallbackBubbleText: string,
): string {
  return isIkunPet(petId) ? IKUN_IDLE_BUBBLE : fallbackBubbleText;
}

export function getPetDragStartAction(petId: string): PetInteractionAction {
  if (isIkunPet(petId)) {
    return {
      animation: "fishChase",
      sound: "fishChase",
      bubbleText: "后撤步。",
    };
  }

  return {
    animation: "drag",
    sound: "drag",
    bubbleText: "喵？！你要带我去哪？",
  };
}

export function getPetDragEndAction(petId: string): PetInteractionAction {
  if (isIkunPet(petId)) {
    return {
      animation: "crouchAlert",
      sound: "drag_end",
      bubbleText: IKUN_IDLE_BUBBLE,
      durationMs: 900,
    };
  }

  return {
    animation: "idle",
    sound: "drag_end",
    bubbleText: "放这儿也行。",
    durationMs: 900,
  };
}

export function getPetClickAction(
  petId: string,
  clickCount: number,
): PetInteractionAction | PetSequenceAction | null {
  if (isIkunPet(petId)) {
    if (clickCount === 1) {
      return {
        animation: "gnawFish",
        sound: "gnawFish",
        bubbleText: "丢球。",
        durationMs: 1300,
      };
    }

    if (clickCount === 2) {
      return {
        animation: "fishEat",
        sound: "fishEat",
        bubbleText: "练习收尾。",
        durationMs: 1300,
      };
    }

    return null;
  }

  if (clickCount === 1) {
    return {
      animation: "tickle",
      sound: "tickle",
      bubbleText: "哼，还行。",
      durationMs: 1000,
    };
  }

  if (clickCount === 2) {
    return { sequence: "hover-fish" };
  }

  return null;
}

export function getPetHoverEatingAction(
  petId: string,
): PetSequenceAction | null {
  return isIkunPet(petId) ? null : { sequence: "hover-fish" };
}

export function getPetCareReminderAction(
  petId: string,
): PetInteractionAction | null {
  if (!isIkunPet(petId)) return null;

  return {
    animation: "tickle",
    sound: "care_reminder",
    bubbleText: IKUN_CARE_REMINDER_BUBBLE,
    durationMs: 8000,
  };
}

export function getPetDesktopIconInteractionAction(
  petId: string,
): PetInteractionAction {
  if (isIkunPet(petId)) {
    return {
      animation: "drag",
      sound: "drag",
      bubbleText: "姬霓太美",
      durationMs: 1800,
    };
  }

  return {
    animation: "iconHug",
    sound: "iconHug",
    bubbleText: "抱住了",
  };
}

export function getDesktopIconKey(icon: DesktopIconBounds): string {
  return `${icon.title}:${icon.x}:${icon.y}:${icon.width}:${icon.height}`;
}

function getPetIconAnchor(petBounds: Bounds): { x: number; y: number } {
  return {
    x: petBounds.x + petBounds.width / 2,
    y: petBounds.y + petBounds.height * 0.72,
  };
}

function getPointToBoundsDistance(
  point: { x: number; y: number },
  bounds: Bounds,
): number {
  const dx = Math.max(bounds.x - point.x, 0, point.x - (bounds.x + bounds.width));
  const dy = Math.max(bounds.y - point.y, 0, point.y - (bounds.y + bounds.height));

  return Math.hypot(dx, dy);
}

export function findDesktopIconTarget(
  petBounds: Bounds,
  icons: DesktopIconBounds[],
  maxDistance = DESKTOP_ICON_INTERACTION_DISTANCE_PX,
  options: DesktopIconTargetOptions = {},
): DesktopIconTarget | null {
  const anchor = getPetIconAnchor(petBounds);
  let closest: DesktopIconTarget | null = null;

  for (const icon of icons) {
    if (options.side === "right" && !isIconRightOfPet(petBounds, icon)) {
      continue;
    }

    const distance = getPointToBoundsDistance(anchor, icon);
    if (distance > maxDistance) continue;

    const target = {
      ...icon,
      key: getDesktopIconKey(icon),
      distance,
    };

    if (!closest || target.distance < closest.distance) {
      closest = target;
    }
  }

  return closest;
}

function isIconRightOfPet(petBounds: Bounds, icon: DesktopIconBounds): boolean {
  const petCenterX = petBounds.x + petBounds.width / 2;
  const iconCenterX = icon.x + icon.width / 2;

  return iconCenterX >= petCenterX;
}

export function updateDesktopIconInteraction({
  now,
  state,
  target,
}: DesktopIconInteractionInput): {
  nextState: DesktopIconInteractionState;
  shouldInteract: boolean;
  target: DesktopIconTarget | null;
} {
  if (!target) {
    return {
      shouldInteract: false,
      target: null,
      nextState: {
        activeIconKey: null,
        firstSeenAt: null,
        lastTriggeredAt: state.lastTriggeredAt,
      },
    };
  }

  const isSameIcon = state.activeIconKey === target.key;
  const firstSeenAt = isSameIcon && state.firstSeenAt !== null ? state.firstSeenAt : now;
  const waitedLongEnough = now - firstSeenAt >= DESKTOP_ICON_INTERACTION_DELAY_MS;
  const cooledDown =
    state.lastTriggeredAt === null ||
    now - state.lastTriggeredAt >= DESKTOP_ICON_INTERACTION_COOLDOWN_MS;
  const shouldInteract = waitedLongEnough && cooledDown;

  return {
    shouldInteract,
    target,
    nextState: {
      activeIconKey: target.key,
      firstSeenAt,
      lastTriggeredAt: shouldInteract ? now : state.lastTriggeredAt,
    },
  };
}

export function formatDesktopIconBubbleText(title: string): string {
  const cleanTitle = title.trim();
  if (!cleanTitle) return "拍拍这个图标。";

  const shortTitle =
    cleanTitle.length > 13 ? `${cleanTitle.slice(0, 13).trim()}…` : cleanTitle;

  return `拍拍 ${shortTitle}`;
}

export function getDesktopIconWrapWindowPosition(
  icon: DesktopIconBounds,
  _windowSize: { width: number; height: number },
  scaleFactor = 1,
): { x: number; y: number } {
  const artworkBounds = getDesktopIconArtworkBounds(icon);
  return {
    x: Math.round(artworkBounds.x - 51 * scaleFactor),
    y: Math.round(artworkBounds.y - 101 * scaleFactor),
  };
}

export function getDesktopIconBumpWindowPosition(
  icon: DesktopIconBounds,
  _windowSize: { width: number; height: number },
  scaleFactor = 1,
): { x: number; y: number } {
  const artworkBounds = getDesktopIconArtworkBounds(icon);
  return {
    x: Math.round(artworkBounds.x - 132 * scaleFactor),
    y: Math.round(artworkBounds.y - 100 * scaleFactor),
  };
}

export function getDesktopIconArtworkBounds(icon: DesktopIconBounds): Bounds {
  const standardHeight = icon.width * (82 / 74);
  const size = Math.max(
    1,
    Math.round(Math.min(icon.width * 0.72, standardHeight * 0.62)),
  );

  return {
    x: Math.round(icon.x + (icon.width - size) / 2),
    y: Math.round(icon.y + standardHeight * 0.08),
    width: size,
    height: size,
  };
}

export function getDesktopIconHugLayerBounds(
  icon: DesktopIconBounds,
  windowPosition: { x: number; y: number },
  scaleFactor: number,
): Bounds {
  const safeScaleFactor = scaleFactor > 0 ? scaleFactor : 1;
  const artworkBounds = getDesktopIconArtworkBounds(icon);

  return {
    x: Math.round((artworkBounds.x - windowPosition.x) / safeScaleFactor),
    y: Math.round((artworkBounds.y - windowPosition.y) / safeScaleFactor),
    width: Math.round(artworkBounds.width / safeScaleFactor),
    height: Math.round(artworkBounds.height / safeScaleFactor),
  };
}

export function formatDesktopIconWrapBubbleText(_title: string): string {
  return "抱住了";
}
