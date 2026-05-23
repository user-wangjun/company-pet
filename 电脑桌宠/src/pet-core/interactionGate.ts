import type { PresenceMode } from './presence';
import type { Point, Rect } from './perchPlanner';

export type DesktopSurface = 'desktop' | 'foreground-window' | 'unknown';

export interface DesktopInteractionContext {
  surface: DesktopSurface;
  foregroundWindowRect?: Rect;
  allowUnknown?: boolean;
}

export type InteractionGateReason =
  | 'desktop'
  | 'unknown-allowed'
  | 'outside-pet'
  | 'passive'
  | 'foreground-window'
  | 'unknown-surface';

export interface PetInteractionGateInput {
  pointer: Point;
  petRect: Rect;
  presence: PresenceMode;
  desktopContext?: DesktopInteractionContext;
}

export interface PetInteractionGateDecision {
  canStart: boolean;
  reason: InteractionGateReason;
}

export function canStartPetInteraction(input: PetInteractionGateInput): PetInteractionGateDecision {
  if (!containsPoint(input.petRect, input.pointer)) {
    return { canStart: false, reason: 'outside-pet' };
  }

  if (input.presence === 'passive') {
    return { canStart: false, reason: 'passive' };
  }

  const desktopContext = input.desktopContext ?? { surface: 'unknown', allowUnknown: true };
  if (desktopContext.surface === 'desktop') {
    return { canStart: true, reason: 'desktop' };
  }

  if (desktopContext.surface === 'foreground-window') {
    return { canStart: false, reason: 'foreground-window' };
  }

  if (desktopContext.allowUnknown === false) {
    return { canStart: false, reason: 'unknown-surface' };
  }

  return { canStart: true, reason: 'unknown-allowed' };
}

function containsPoint(rect: Rect, point: Point) {
  return point.x >= rect.x && point.x <= rect.x + rect.width && point.y >= rect.y && point.y <= rect.y + rect.height;
}
