export type PresenceMode = 'solid' | 'passive' | 'materializing' | 'dragging';
export type ForcedPresenceMode = 'auto' | 'solid' | 'passive';

export interface PresenceInput {
  isDragging: boolean;
  nearbyObstructionScore: number;
  hoverMs: number;
  forcedMode: ForcedPresenceMode;
  denseThreshold?: number;
  materializeHoverMs?: number;
}

export function decidePresenceMode(input: PresenceInput): PresenceMode {
  if (input.isDragging) {
    return 'dragging';
  }

  if (input.forcedMode === 'solid' || input.forcedMode === 'passive') {
    return input.forcedMode;
  }

  const materializeHoverMs = input.materializeHoverMs ?? 5000;
  if (input.hoverMs >= materializeHoverMs) {
    return 'materializing';
  }

  const denseThreshold = input.denseThreshold ?? 70;
  if (input.nearbyObstructionScore >= denseThreshold) {
    return 'passive';
  }

  return 'solid';
}
