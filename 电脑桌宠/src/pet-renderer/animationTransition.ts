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

export interface FrameBlendInput {
  elapsedMs: number;
  frameDurationMs: number;
  frames: number;
  loop: boolean;
  blendWindowRatio?: number;
  frameSequence?: number[];
}

export interface FrameBlend {
  currentFrame: number;
  nextFrame: number;
  alpha: number;
}

export function getFrameBlend(input: FrameBlendInput): FrameBlend {
  const frameSequence = normalizeFrameSequence(input.frameSequence);
  const frames = frameSequence?.length ?? Math.max(1, input.frames);
  const frameDurationMs = Math.max(1, input.frameDurationMs);
  const blendWindowRatio = clamp(input.blendWindowRatio ?? 0.32, 0.01, 1);
  const blendStart = 1 - blendWindowRatio;
  const rawFrame = Math.floor(input.elapsedMs / frameDurationMs);
  const localProgress = (input.elapsedMs % frameDurationMs) / frameDurationMs;
  const currentFrameIndex = input.loop ? rawFrame % frames : Math.min(rawFrame, frames - 1);
  const nextFrameIndex = input.loop ? (currentFrameIndex + 1) % frames : Math.min(currentFrameIndex + 1, frames - 1);
  const currentFrame = frameSequence?.[currentFrameIndex] ?? currentFrameIndex;
  const nextFrame = frameSequence?.[nextFrameIndex] ?? nextFrameIndex;

  if (currentFrame === nextFrame) {
    return {
      currentFrame,
      nextFrame,
      alpha: 0,
    };
  }

  return {
    currentFrame,
    nextFrame,
    alpha: localProgress < blendStart ? 0 : smoothStep((localProgress - blendStart) / blendWindowRatio),
  };
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

function smoothStep(progress: number) {
  const clamped = clamp(progress, 0, 1);
  return clamped * clamped * (3 - 2 * clamped);
}

function normalizeFrameSequence(frameSequence: number[] | undefined) {
  if (!frameSequence?.length) {
    return undefined;
  }

  return frameSequence.filter((frame) => Number.isInteger(frame) && frame >= 0);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}
