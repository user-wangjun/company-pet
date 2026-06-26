import { describe, expect, test } from "vitest";
import ds from "../../public/pets/ds/pet.json";
import xiaoju from "../../public/pets/xiaoju-cat/pet.json";
import {
  getInteractionAnimationSpec,
  resolveActionPlaybackSteps,
} from "./interactionPlayback";
import { resolvePetInteractionManifest } from "./petInteractionManifest";

describe("pet interaction playback plans", () => {
  test("expands manifest sequences into timed playback steps", () => {
    const manifest = resolvePetInteractionManifest(xiaoju);

    expect(resolveActionPlaybackSteps(manifest.doubleClick)).toEqual([
      {
        animation: "fishChase",
        startAfterMs: 0,
        durationMs: 950,
        sound: "fishChase",
        dialogueEvent: "doubleClick",
      },
      {
        animation: "fishEat",
        startAfterMs: 950,
        durationMs: 1300,
        sound: "fishEat",
        dialogueEvent: "doubleClick",
      },
    ]);
  });

  test("wraps simple actions into a single immediate playback step", () => {
    const manifest = resolvePetInteractionManifest(ds);

    expect(resolveActionPlaybackSteps(manifest.singleClick)).toEqual([
      {
        animation: "singleClick",
        startAfterMs: 0,
        durationMs: 1200,
        dialogueEvent: "singleClick",
      },
    ]);
  });

  test("returns the animation spec that controls frame slicing and visual scale", () => {
    const manifest = resolvePetInteractionManifest(ds);

    expect(getInteractionAnimationSpec(manifest, "dragLeft")).toMatchObject({
      row: 2,
      frames: 8,
      scale: 1.1,
      visualClass: "pose-change",
    });
  });

  test("rejects unknown playback animation names before the renderer uses them", () => {
    const manifest = resolvePetInteractionManifest(ds);

    expect(() => getInteractionAnimationSpec(manifest, "missing")).toThrow(
      'Unknown interaction animation "missing"',
    );
  });
});
