import type { RuntimeAnimationName } from "./interaction";

export type AnimationRowSpec = {
  row: number;
  frames: number;
  speed: number;
  loop: boolean;
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

export function getPetAnimationRowSpec(
  petId: string,
  animationName: RuntimeAnimationName,
): AnimationRowSpec {
  const defaultSpec = ANIMATION_ROWS[animationName];

  if (petId === "ikun" && animationName === "fishEat") {
    return { ...defaultSpec, frames: 8 };
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
