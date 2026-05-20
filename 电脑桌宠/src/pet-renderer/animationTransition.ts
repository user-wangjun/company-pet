export interface TransitionAlpha {
  incoming: number;
  outgoing: number;
}

export interface TransitionSpritePose {
  alpha: number;
  x: number;
  y: number;
  scaleX: number;
  scaleY: number;
}

export interface TransitionPose {
  incoming: TransitionSpritePose;
  outgoing: TransitionSpritePose;
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

export function getTransitionPose(elapsedMs: number, durationMs: number): TransitionPose {
  if (durationMs <= 0) {
    return {
      incoming: settledPose(1),
      outgoing: settledPose(0),
    };
  }

  const progress = clamp(elapsedMs / durationMs, 0, 1);
  const alpha = getTransitionAlpha(elapsedMs, durationMs);
  const bodyArc = Math.sin(Math.PI * progress);

  if (progress >= 1) {
    return {
      incoming: settledPose(1),
      outgoing: settledPose(0),
    };
  }

  return {
    incoming: {
      alpha: alpha.incoming,
      x: 0,
      y: 7 * (1 - alpha.incoming) - 5 * bodyArc,
      scaleX: 1 + 0.035 * bodyArc,
      scaleY: 1 - 0.026 * bodyArc,
    },
    outgoing: {
      alpha: alpha.outgoing,
      x: 0,
      y: 3 * bodyArc,
      scaleX: 1 + 0.014 * bodyArc,
      scaleY: 1 - 0.01 * bodyArc,
    },
  };
}

function settledPose(alpha: number): TransitionSpritePose {
  return {
    alpha,
    x: 0,
    y: 0,
    scaleX: 1,
    scaleY: 1,
  };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}
