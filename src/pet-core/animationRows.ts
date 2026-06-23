import type { RuntimeAnimationName } from "./interaction";

export type AnimationRowSpec = {
  row: number;
  frames: number;
  speed: number;
  loop: boolean;
};

export type DragFramePlan = {
  takeoffFrame: number;
  loopStartFrame: number;
  loopFrameCount: number;
  landingApproachFrame: number;
  landingFrame: number;
  landingTransitionSpeed: number;
};

export const ANIMATION_ROWS = {
  idle: { row: 0, frames: 6, speed: 0.05, loop: true },
  drag: { row: 1, frames: 8, speed: 0.2, loop: true },
  tickle: { row: 3, frames: 8, speed: 0.16, loop: false },
  fishChase: { row: 7, frames: 8, speed: 0.18, loop: true },
  fishEat: { row: 8, frames: 6, speed: 0.14, loop: false },
  iconHug: { row: 0, frames: 6, speed: 0.08, loop: false },
  crouchAlert: { row: 4, frames: 8, speed: 0.12, loop: true },
  hugFish: { row: 5, frames: 8, speed: 0.12, loop: true },
  gnawFish: { row: 6, frames: 8, speed: 0.14, loop: false },
} as const satisfies Record<RuntimeAnimationName, AnimationRowSpec>;

export function getPetDragFramePlan(petId: string): DragFramePlan | null {
  if (petId !== "suan-bird") return null;

  return {
    takeoffFrame: 0,
    loopStartFrame: 1,
    loopFrameCount: 6,
    landingApproachFrame: 6,
    landingFrame: 7,
    landingTransitionSpeed: 0.25,
  };
}

export function buildPetDragLandingFrames<T>(
  currentFrame: T,
  dragFrames: T[],
  plan: DragFramePlan | null,
): T[] | null {
  if (!plan) return null;

  const approachFrame = dragFrames[plan.landingApproachFrame];
  const landingFrame = dragFrames[plan.landingFrame];
  if (approachFrame === undefined || landingFrame === undefined) return null;

  return [currentFrame, approachFrame, landingFrame];
}

export function getPetAnimationRowSpec(
  petId: string,
  animationName: RuntimeAnimationName,
): AnimationRowSpec {
  const defaultSpec = ANIMATION_ROWS[animationName];

  if (petId === "ikun" && animationName === "fishEat") {
    return { ...defaultSpec, frames: 8 };
  }

  if (petId === "suan-bird" && animationName === "fishChase") {
    return { ...defaultSpec, loop: false };
  }

  return defaultSpec;
}

export function appendPetAnimationFinishFrame<T>(
  petId: string,
  animationName: RuntimeAnimationName,
  atlasFrames: T[],
  finishFrame: T | null,
): T[] {
  if (
    petId === "ikun" &&
    animationName === "gnawFish" &&
    finishFrame !== null
  ) {
    return [...atlasFrames, finishFrame];
  }

  return atlasFrames;
}
