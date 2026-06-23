import { describe, expect, test } from "vitest";
import ds from "../../public/pets/ds/pet.json";
import ikun from "../../public/pets/ikun/pet.json";
import suanBird from "../../public/pets/suan-bird/pet.json";
import xiaoju from "../../public/pets/xiaoju-cat/pet.json";
import {
  resolvePetInteractionManifest,
  type PetActionSpec,
  type PetInteractionManifestSource,
  type PetSequenceSpec,
} from "./petInteractionManifest";

const builtInManifests = [
  ["xiaoju-cat", xiaoju],
  ["ikun", ikun],
  ["ds", ds],
  ["suan-bird", suanBird],
] as const;

const resolve = (source: unknown) =>
  resolvePetInteractionManifest(source as PetInteractionManifestSource);

function isSequence(
  action: PetActionSpec | PetSequenceSpec,
): action is PetSequenceSpec {
  return "sequence" in action;
}

describe("pet interaction manifests", () => {
  test.each(builtInManifests)(
    "%s declares every required interaction",
    (_id, manifest) => {
      const resolved = resolve(manifest);

      expect(resolved.idle).toBeDefined();
      expect(resolved.singleClick).toBeDefined();
      expect(resolved.doubleClick).toBeDefined();
      expect(resolved.drag).toBeDefined();
      expect(Object.keys(resolved.reminders).sort()).toEqual([
        "eyeCare",
        "meal",
        "sleep",
        "water",
      ]);
    },
  );

  test.each([
    ["idle", { idle: undefined }],
    ["singleClick", { singleClick: undefined }],
    ["doubleClick", { doubleClick: undefined }],
    ["drag", { drag: undefined }],
  ])("rejects a manifest missing %s", (field, override) => {
    const source = structuredClone(xiaoju) as PetInteractionManifestSource;
    Object.assign(source.interactions!, override);

    expect(() => resolve(source)).toThrow(`Missing interactions.${field}`);
  });

  test.each(["eyeCare", "water", "meal", "sleep"] as const)(
    "rejects a manifest missing the %s reminder",
    (kind) => {
      const source = structuredClone(xiaoju) as PetInteractionManifestSource;
      delete source.interactions?.reminders?.[kind];

      expect(() => resolve(source)).toThrow(
        `Missing interactions.reminders.${kind}`,
      );
    },
  );

  test("enables only the approved optional capabilities", () => {
    expect(resolve(xiaoju).hover.enabled).toBe(true);
    expect(resolve(ds).hover.enabled).toBe(false);
    expect(resolve(ikun).hover.enabled).toBe(false);
    expect(resolve(suanBird).hover.enabled).toBe(false);

    expect(resolve(xiaoju).desktopIcon.enabled).toBe(true);
    expect(resolve(ds).desktopIcon.enabled).toBe(true);
    expect(resolve(ikun).desktopIcon).toEqual({ enabled: false });
    expect(resolve(suanBird).desktopIcon).toEqual({ enabled: false });
  });

  test("defaults omitted optional capabilities to disabled", () => {
    const source = structuredClone(xiaoju) as PetInteractionManifestSource;
    delete source.interactions?.hover;
    delete source.interactions?.desktopIcon;

    expect(resolve(source).hover).toEqual({ enabled: false });
    expect(resolve(source).desktopIcon).toEqual({ enabled: false });
  });

  test("declares effective frame counts instead of transparent cells", () => {
    expect(resolve(xiaoju).animations.tickle.frames).toBe(4);
    expect(resolve(xiaoju).animations.fishChase.frames).toBe(6);
  });

  test("declares real left and right drag rows where available", () => {
    expect(resolve(xiaoju).drag).toMatchObject({
      directionMode: "rows",
      right: "dragRight",
      left: "dragLeft",
    });
    expect(resolve(ds).drag).toMatchObject({
      directionMode: "rows",
      right: "dragRight",
      left: "dragLeft",
    });
    expect(resolve(suanBird).drag).toMatchObject({
      directionMode: "rows",
      right: "dragRight",
      left: "dragLeft",
    });
    expect(resolve(ikun).drag).toMatchObject({
      directionMode: "mirror-left",
      right: "drag",
      left: "drag",
    });
  });

  test("declares the approved suan-bird drag lifecycle", () => {
    expect(resolve(suanBird).drag).toMatchObject({
      takeoffFrame: 0,
      loopStartFrame: 1,
      loopFrameCount: 6,
      landingApproachFrame: 6,
      landingFrame: 7,
      landingTransitionSpeed: 0.25,
      landingHoldMs: 350,
    });
  });

  test("preserves xiaoju's existing idle quirks", () => {
    expect(resolve(xiaoju).idleQuirks.map((quirk) => quirk.bubbleText)).toEqual([
      "（砸嘴）……梦见超大金枪鱼了喵 🐟",
      "（幸福地翻个身）~ 换个姿势继续睡喵…… 🐾",
      "（亲昵地蹭了蹭）……主人工作辛苦啦，小橘陪着你喵 💤",
      "（趴下警觉喵喵叫）~ 好像有大鱼的气味？🐾",
      "（抱着小鱼撒娇）~ 嘿嘿，这只小鱼是橘橘的宝贝！🐟",
      "（美滋滋地坐着嚼鱼）~ 金枪鱼味儿的玩具鱼，真香！🐾",
    ]);
  });

  test.each(builtInManifests)(
    "%s gives finite looped actions an explicit duration",
    (_id, manifest) => {
      const resolved = resolve(manifest);
      const finiteActions: Array<PetActionSpec | PetSequenceSpec> = [
        resolved.singleClick,
        resolved.doubleClick,
        ...Object.values(resolved.reminders),
        ...resolved.idleQuirks,
      ];

      if (resolved.hover.enabled) finiteActions.push(resolved.hover.action);
      if (resolved.desktopIcon.enabled) {
        finiteActions.push(resolved.desktopIcon.action);
      }

      for (const actionOrSequence of finiteActions) {
        const actions = isSequence(actionOrSequence)
          ? actionOrSequence.sequence
          : [actionOrSequence];

        for (const action of actions) {
          if (resolved.animations[action.animation]?.loop) {
            expect(action.durationMs, action.animation).toBeGreaterThan(0);
          }
        }
      }
    },
  );

  test("disables invalid optional desktop icon behavior", () => {
    const warnings: string[] = [];
    const malformed = {
      id: "broken",
      animations: {},
      interactions: {
        idle: { animation: "idle" },
        singleClick: { animation: "idle" },
        doubleClick: { animation: "idle" },
        drag: {
          directionMode: "rows",
          right: "idle",
          left: "idle",
        },
        reminders: {
          eyeCare: { animation: "idle" },
          water: { animation: "idle" },
          meal: { animation: "idle" },
          sleep: { animation: "idle" },
        },
        desktopIcon: { enabled: true },
      },
    } as unknown as PetInteractionManifestSource;

    expect(
      resolvePetInteractionManifest(
        malformed,
        (message) => warnings.push(message),
      ).desktopIcon,
    ).toEqual({ enabled: false });
    expect(warnings).toEqual([
      "[pet-interactions] broken disabled invalid desktopIcon.action",
    ]);
  });
});
