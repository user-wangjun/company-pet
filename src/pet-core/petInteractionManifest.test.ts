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

const makeValidSource = (): PetInteractionManifestSource =>
  structuredClone(xiaoju) as PetInteractionManifestSource;

const makeRawSource = (): Record<string, unknown> =>
  structuredClone(xiaoju) as Record<string, unknown>;

function getRawObject(
  value: unknown,
  field: string,
): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`Test fixture ${field} is not an object`);
  }
  return value as Record<string, unknown>;
}

function getRawInteractions(
  source: Record<string, unknown>,
): Record<string, unknown> {
  return getRawObject(source.interactions, "interactions");
}

function getRawAnimations(
  source: Record<string, unknown>,
): Record<string, unknown> {
  return getRawObject(source.animations, "animations");
}

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

  test("rejects a manifest without animations", () => {
    const source = makeValidSource();
    source.animations = {};

    expect(() => resolve(source)).toThrow("Missing animations");
  });

  test.each([
    [
      "singleClick=42",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).singleClick = 42;
      },
      "Invalid object at interactions.singleClick",
    ],
    [
      "sequence=null",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).doubleClick = { sequence: null };
      },
      "Expected non-empty array at interactions.doubleClick.sequence",
    ],
    [
      "sequence is not an array",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).doubleClick = { sequence: "steps" };
      },
      "Expected non-empty array at interactions.doubleClick.sequence",
    ],
    [
      "sequence contains a null step",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).doubleClick = { sequence: [null] };
      },
      "Invalid object at interactions.doubleClick.sequence[0]",
    ],
    [
      "sequence step omits startAfterMs",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).doubleClick = {
          sequence: [{ animation: "fishEat", durationMs: 1000 }],
        };
      },
      "Expected finite non-negative number at interactions.doubleClick.sequence[0].startAfterMs",
    ],
    [
      "sequence step has negative startAfterMs",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).doubleClick = {
          sequence: [
            {
              animation: "fishEat",
              durationMs: 1000,
              startAfterMs: -1,
            },
          ],
        };
      },
      "Expected finite non-negative number at interactions.doubleClick.sequence[0].startAfterMs",
    ],
    [
      "idleQuirks is not an array",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).idleQuirks = {};
      },
      "Expected array at interactions.idleQuirks",
    ],
    [
      "reminders is not an object",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).reminders = [];
      },
      "Invalid object at interactions.reminders",
    ],
    [
      "drag is not an object",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).drag = "dragRight";
      },
      "Invalid object at interactions.drag",
    ],
    [
      "animations is not an object",
      (source: Record<string, unknown>) => {
        source.animations = [];
      },
      "Invalid object at animations",
    ],
    [
      "animation spec is not an object",
      (source: Record<string, unknown>) => {
        getRawAnimations(source).idle = 42;
      },
      "Invalid object at animations.idle",
    ],
    [
      "action animation is numeric",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).singleClick = { animation: 42 };
      },
      "Expected non-empty string at interactions.singleClick.animation",
    ],
    [
      "action animation is blank",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).singleClick = { animation: "  " };
      },
      "Expected non-empty string at interactions.singleClick.animation",
    ],
    [
      "action sound is numeric",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).singleClick = {
          animation: "tickle",
          durationMs: 1000,
          sound: 42,
        };
      },
      "Expected non-empty string at interactions.singleClick.sound",
    ],
    [
      "action dialogueEvent is unknown",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).singleClick = {
          animation: "tickle",
          durationMs: 1000,
          dialogueEvent: "wave",
        };
      },
      "Invalid value at interactions.singleClick.dialogueEvent",
    ],
    [
      "hover is not an object",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).hover = [];
      },
      "Invalid object at interactions.hover",
    ],
    [
      "hover enabled is not boolean",
      (source: Record<string, unknown>) => {
        getRawInteractions(source).hover = { enabled: "true" };
      },
      "Expected boolean at interactions.hover.enabled",
    ],
  ] as const)(
    "rejects malformed raw shape: %s",
    (_name, mutate, message) => {
      const source = makeRawSource();
      mutate(source);

      expect(() => resolve(source)).toThrow(message);
    },
  );

  test.each([
    ["row", -1, "Expected non-negative integer at animations.idle.row"],
    ["row", 0.5, "Expected non-negative integer at animations.idle.row"],
    ["frames", 0, "Expected positive integer at animations.idle.frames"],
    ["frames", 1.5, "Expected positive integer at animations.idle.frames"],
    ["speed", 0, "Expected finite positive number at animations.idle.speed"],
    [
      "speed",
      Number.POSITIVE_INFINITY,
      "Expected finite positive number at animations.idle.speed",
    ],
    ["loop", "true", "Expected boolean at animations.idle.loop"],
    [
      "visualClass",
      "special",
      "Invalid value at animations.idle.visualClass",
    ],
    ["scale", 0, "Expected finite positive number at animations.idle.scale"],
    [
      "offsetX",
      Number.NaN,
      "Expected finite number at animations.idle.offsetX",
    ],
    [
      "offsetY",
      Number.POSITIVE_INFINITY,
      "Expected finite number at animations.idle.offsetY",
    ],
    [
      "spritesheetPath",
      "",
      "Expected non-empty relative path at animations.idle.spritesheetPath",
    ],
    [
      "spritesheetPath",
      "/absolute.webp",
      "Expected non-empty relative path at animations.idle.spritesheetPath",
    ],
    [
      "finishFramePath",
      "C:\\finish.png",
      "Expected non-empty relative path at animations.idle.finishFramePath",
    ],
    [
      "spritesheetPath",
      "%2e%2e/ikun/spritesheet.webp",
      "Expected non-empty relative path at animations.idle.spritesheetPath",
    ],
    [
      "spritesheetPath",
      "%252e%252e/ikun/spritesheet.webp",
      "Expected non-empty relative path at animations.idle.spritesheetPath",
    ],
    [
      "finishFramePath",
      "foo%5c..%5cbar",
      "Expected non-empty relative path at animations.idle.finishFramePath",
    ],
  ] as const)(
    "validates animation %s=%s",
    (field, value, message) => {
      const source = makeRawSource();
      getRawObject(getRawAnimations(source).idle, "animations.idle")[field] =
        value;

      expect(() => resolve(source)).toThrow(message);
    },
  );

  test.each([
    [
      "directionMode sideways",
      (drag: Record<string, unknown>) => {
        drag.directionMode = "sideways";
      },
      "Invalid value at interactions.drag.directionMode",
    ],
    [
      "blank right",
      (drag: Record<string, unknown>) => {
        drag.right = "";
      },
      "Expected non-empty string at interactions.drag.right",
    ],
    [
      "takeoffFrame out of range",
      (drag: Record<string, unknown>) => {
        drag.takeoffFrame = 8;
      },
      "Frame index out of range at interactions.drag.takeoffFrame",
    ],
    [
      "negative landingFrame",
      (drag: Record<string, unknown>) => {
        drag.landingFrame = -1;
      },
      "Expected non-negative integer at interactions.drag.landingFrame",
    ],
    [
      "loopFrameCount zero",
      (drag: Record<string, unknown>) => {
        drag.loopFrameCount = 0;
      },
      "Expected positive integer at interactions.drag.loopFrameCount",
    ],
    [
      "loopStartFrame without loopFrameCount",
      (drag: Record<string, unknown>) => {
        drag.loopStartFrame = 1;
        delete drag.loopFrameCount;
      },
      "Missing interactions.drag.loopFrameCount when interactions.drag.loopStartFrame is set",
    ],
    [
      "loopFrameCount without loopStartFrame",
      (drag: Record<string, unknown>) => {
        delete drag.loopStartFrame;
        drag.loopFrameCount = 2;
      },
      "Missing interactions.drag.loopStartFrame when interactions.drag.loopFrameCount is set",
    ],
    [
      "loop lifecycle exceeds frames",
      (drag: Record<string, unknown>) => {
        drag.loopStartFrame = 4;
        drag.loopFrameCount = 5;
      },
      "Drag loop exceeds animation frames at interactions.drag.loopFrameCount",
    ],
    [
      "landingTransitionSpeed zero",
      (drag: Record<string, unknown>) => {
        drag.landingTransitionSpeed = 0;
      },
      "Expected finite positive number at interactions.drag.landingTransitionSpeed",
    ],
    [
      "landingHoldMs negative",
      (drag: Record<string, unknown>) => {
        drag.landingHoldMs = -1;
      },
      "Expected finite non-negative number at interactions.drag.landingHoldMs",
    ],
  ] as const)(
    "validates malformed drag: %s",
    (_name, mutate, message) => {
      const source = makeRawSource();
      const drag = getRawObject(
        getRawInteractions(source).drag,
        "interactions.drag",
      );
      mutate(drag);

      expect(() => resolve(source)).toThrow(message);
    },
  );

  test.each([
    ["idle", (source: PetInteractionManifestSource) => {
      source.interactions!.idle = { animation: "missing" };
    }],
    ["singleClick", (source: PetInteractionManifestSource) => {
      source.interactions!.singleClick = { animation: "missing" };
    }],
    ["doubleClick.sequence[0]", (source: PetInteractionManifestSource) => {
      source.interactions!.doubleClick = {
        sequence: [{ animation: "missing", startAfterMs: 0 }],
      };
    }],
    ["drag.right", (source: PetInteractionManifestSource) => {
      source.interactions!.drag!.right = "missing";
    }],
    ["drag.left", (source: PetInteractionManifestSource) => {
      source.interactions!.drag!.left = "missing";
    }],
    ["reminders.eyeCare", (source: PetInteractionManifestSource) => {
      source.interactions!.reminders!.eyeCare = { animation: "missing" };
    }],
    ["hover.action", (source: PetInteractionManifestSource) => {
      source.interactions!.hover = {
        enabled: true,
        action: { animation: "missing" },
      };
    }],
    ["idleQuirks[0]", (source: PetInteractionManifestSource) => {
      source.interactions!.idleQuirks = [{ animation: "missing" }];
    }],
  ] as const)("rejects an unknown animation in interactions.%s", (field, mutate) => {
    const source = makeValidSource();
    mutate(source);

    expect(() => resolve(source)).toThrow(
      field === "drag.right" || field === "drag.left"
        ? `Unknown animation "missing" at interactions.${field}`
        : `Unknown animation "missing" at interactions.${field}.animation`,
    );
  });

  test("rejects inherited object keys as animation references", () => {
    const source = makeRawSource();
    getRawInteractions(source).singleClick = { animation: "toString" };

    expect(() => resolve(source)).toThrow(
      'Unknown animation "toString" at interactions.singleClick.animation',
    );
  });

  test("rejects an empty sequence", () => {
    const source = makeValidSource();
    source.interactions!.doubleClick = { sequence: [] };

    expect(() => resolve(source)).toThrow(
      "Empty sequence at interactions.doubleClick.sequence",
    );
  });

  test("rejects sequence steps with decreasing startAfterMs", () => {
    const source = makeRawSource();
    getRawInteractions(source).doubleClick = {
      sequence: [
        {
          animation: "fishChase",
          durationMs: 1000,
          startAfterMs: 1000,
        },
        {
          animation: "fishEat",
          durationMs: 1000,
          startAfterMs: 500,
        },
      ],
    };

    expect(() => resolve(source)).toThrow(
      "Expected non-decreasing startAfterMs at interactions.doubleClick.sequence[1].startAfterMs",
    );
  });

  test.each([
    ["singleClick", (source: PetInteractionManifestSource) => {
      source.interactions!.singleClick = { animation: "idle" };
    }],
    ["doubleClick.sequence[0]", (source: PetInteractionManifestSource) => {
      source.interactions!.doubleClick = {
        sequence: [{ animation: "fishChase", startAfterMs: 0 }],
      };
    }],
    ["reminders.eyeCare", (source: PetInteractionManifestSource) => {
      source.interactions!.reminders!.eyeCare = {
        animation: "idle",
        durationMs: 0,
      };
    }],
    ["hover.action", (source: PetInteractionManifestSource) => {
      source.interactions!.hover = {
        enabled: true,
        action: { animation: "fishChase" },
      };
    }],
    ["idleQuirks[0]", (source: PetInteractionManifestSource) => {
      source.interactions!.idleQuirks = [{ animation: "hugFish" }];
    }],
  ] as const)(
    "rejects a finite looped action without positive duration at interactions.%s",
    (field, mutate) => {
      const source = makeValidSource();
      mutate(source);

      expect(() => resolve(source)).toThrow(
        `Missing positive durationMs for loop animation at interactions.${field}`,
      );
    },
  );

  test("warns and disables desktopIcon when enabled is malformed", () => {
    const source = makeRawSource();
    const warnings: string[] = [];
    getRawInteractions(source).desktopIcon = { enabled: "false" };

    expect(
      resolvePetInteractionManifest(
        source as PetInteractionManifestSource,
        (message) => warnings.push(message),
      ).desktopIcon,
    ).toEqual({ enabled: false });
    expect(warnings).toEqual([
      "[pet-interactions] xiaoju-cat disabled invalid desktopIcon.enabled",
    ]);
  });

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

  test.each([
    [
      "object",
      42,
      "[pet-interactions] broken disabled invalid desktopIcon",
    ],
    [
      "action",
      { enabled: true },
      "[pet-interactions] broken disabled invalid desktopIcon.action",
    ],
    [
      "action.animation",
      {
        enabled: true,
        action: { animation: "missing", durationMs: 1000 },
        positioning: "wrap",
        allowedSide: "any",
      },
      "[pet-interactions] broken disabled invalid desktopIcon.action.animation",
    ],
    [
      "positioning",
      {
        enabled: true,
        action: { animation: "iconHug", durationMs: 1000 },
        allowedSide: "any",
      },
      "[pet-interactions] broken disabled invalid desktopIcon.positioning",
    ],
    [
      "allowedSide",
      {
        enabled: true,
        action: { animation: "iconHug", durationMs: 1000 },
        positioning: "wrap",
      },
      "[pet-interactions] broken disabled invalid desktopIcon.allowedSide",
    ],
    [
      "positioning value",
      {
        enabled: true,
        action: { animation: "iconHug", durationMs: 1000 },
        positioning: "slide",
        allowedSide: "any",
      },
      "[pet-interactions] broken disabled invalid desktopIcon.positioning",
    ],
    [
      "allowedSide value",
      {
        enabled: true,
        action: { animation: "iconHug", durationMs: 1000 },
        positioning: "wrap",
        allowedSide: "center",
      },
      "[pet-interactions] broken disabled invalid desktopIcon.allowedSide",
    ],
    [
      "action.durationMs",
      {
        enabled: true,
        action: { animation: "hugFish" },
        positioning: "wrap",
        allowedSide: "any",
      },
      "[pet-interactions] broken disabled invalid desktopIcon.action.durationMs",
    ],
    [
      "action.sound",
      {
        enabled: true,
        action: {
          animation: "iconHug",
          durationMs: 1000,
          sound: 42,
        },
        positioning: "wrap",
        allowedSide: "any",
      },
      "[pet-interactions] broken disabled invalid desktopIcon.action.sound",
    ],
    [
      "action.dialogueEvent",
      {
        enabled: true,
        action: {
          animation: "iconHug",
          durationMs: 1000,
          dialogueEvent: "wave",
        },
        positioning: "wrap",
        allowedSide: "any",
      },
      "[pet-interactions] broken disabled invalid desktopIcon.action.dialogueEvent",
    ],
  ] satisfies ReadonlyArray<readonly [string, unknown, string]>)(
    "warns and disables desktopIcon with invalid %s",
    (_field, desktopIcon, warning) => {
      const warnings: string[] = [];
      const malformed = makeRawSource();
      malformed.id = "broken";
      getRawInteractions(malformed).desktopIcon = desktopIcon;

      expect(
        resolvePetInteractionManifest(
          malformed,
          (message) => warnings.push(message),
        ).desktopIcon,
      ).toEqual({ enabled: false });
      expect(warnings).toEqual([warning]);
    },
  );
});
