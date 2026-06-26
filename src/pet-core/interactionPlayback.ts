import type {
  PetActionSpec,
  PetAnimationSpec,
  PetSequenceSpec,
  ResolvedPetInteractionManifest,
} from "./petInteractionManifest";

export type PetPlaybackStep = PetActionSpec & {
  startAfterMs: number;
};

export function resolveActionPlaybackSteps(
  action: PetActionSpec | PetSequenceSpec,
): PetPlaybackStep[] {
  if ("sequence" in action) {
    return action.sequence.map((step) => ({ ...step }));
  }

  return [{ ...action, startAfterMs: 0 }];
}

export function getInteractionAnimationSpec(
  manifest: ResolvedPetInteractionManifest,
  animationName: string,
): PetAnimationSpec {
  const spec = manifest.animations[animationName];
  if (!spec) {
    throw new Error(`Unknown interaction animation "${animationName}"`);
  }

  return spec;
}
