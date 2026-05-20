export interface TransitionAlpha {
  incoming: number;
  outgoing: number;
}

export function getTransitionAlpha(elapsedMs: number, durationMs: number): TransitionAlpha {
  if (durationMs <= 0) {
    return { incoming: 1, outgoing: 0 };
  }

  const progress = clamp(elapsedMs / durationMs, 0, 1);
  const eased = progress * progress * (3 - 2 * progress);
  return {
    incoming: eased,
    outgoing: 1 - eased,
  };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}
