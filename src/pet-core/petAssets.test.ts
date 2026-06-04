import { describe, expect, test } from "vitest";
import ikunActionBoard from "../../public/pets/ikun/action-board.json";
import ikunActions from "../../public/pets/ikun/actions.json";
import ikunManifest from "../../public/pets/ikun/pet.json";
import ikunMotionReview from "../../public/pets/ikun/qa/motion-review.json";
import ikunRig from "../../public/pets/ikun/rig.json";
import dsManifest from "../../public/pets/ds/pet.json";
import builtInPetManifest from "../../public/pets/xiaoju-cat/pet.json";
import petIndex from "../../public/pets/index.json";
import {
  DEFAULT_PET_ID,
  chooseInitialPetId,
  createPetCatalog,
  getPetBasePath,
  getPetIndexUrl,
  getPetManifestUrl,
  resolvePetAssetUrl,
} from "./petAssets";
import type { PetManifest } from "./petAssets";

describe("pet asset paths", () => {
  test("uses xiaoju-cat as the built-in pet package", () => {
    expect(DEFAULT_PET_ID).toBe("xiaoju-cat");
    expect(getPetIndexUrl()).toBe("/pets/index.json");
    expect(getPetBasePath(DEFAULT_PET_ID)).toBe("/pets/xiaoju-cat");
    expect(getPetManifestUrl(DEFAULT_PET_ID)).toBe(
      "/pets/xiaoju-cat/pet.json",
    );
  });

  test("resolves package files under public/pets by pet id", () => {
    expect(resolvePetAssetUrl("xiaoju-cat", "spritesheet.webp")).toBe(
      "/pets/xiaoju-cat/spritesheet.webp",
    );
    expect(resolvePetAssetUrl("xiaoju-cat", "nested/preview.png")).toBe(
      "/pets/xiaoju-cat/nested/preview.png",
    );
  });

  test("keeps sound cue paths relative to the active pet package", () => {
    expect(resolvePetAssetUrl("xiaoju-cat", "sounds/tickle-hm-1.wav")).toBe(
      "/pets/xiaoju-cat/sounds/tickle-hm-1.wav",
    );
    expect(resolvePetAssetUrl("xiaoju-cat", "\\sounds\\drag-meow-1.wav")).toBe(
      "/pets/xiaoju-cat/sounds/drag-meow-1.wav",
    );
  });

  test("allows pet manifests to declare optional sound cues", () => {
    const manifest: PetManifest = {
      id: "xiaoju-cat",
      displayName: "小橘",
      description: "一只橘黄色毛绒小猫咪。",
      spritesheetPath: "spritesheet-scruff.webp",
      sounds: {
        tickle: [
          { path: "sounds/tickle-hm-1.wav", volume: 0.45 },
          { path: "sounds/tickle-hmph-1.wav" },
        ],
      },
    };

    expect(manifest.sounds?.tickle).toEqual([
      { path: "sounds/tickle-hm-1.wav", volume: 0.45 },
      { path: "sounds/tickle-hmph-1.wav" },
    ]);
  });

  test("keeps the built-in pet package in the public assets tree", () => {
    expect(petIndex.pets).toContain(DEFAULT_PET_ID);
    expect(builtInPetManifest.id).toBe(DEFAULT_PET_ID);
    expect(builtInPetManifest.spritesheetPath).toBe("spritesheet-scruff.webp");
  });

  test("declares ikun as a second isolated pet package", () => {
    expect(petIndex.pets).toContain("ikun");
    expect(ikunManifest.id).toBe("ikun");
    expect(ikunManifest.spritesheetPath).toBe("spritesheet.webp");
    expect(ikunManifest.previewPath).toBe("preview.png");
    expect(ikunManifest.actionsPath).toBe("actions.json");
    expect(ikunManifest.rigPath).toBe("rig.json");
    expect(ikunManifest.actionBoardPath).toBe("action-board.json");
    expect(resolvePetAssetUrl("ikun", ikunManifest.spritesheetPath)).toBe(
      "/pets/ikun/spritesheet.webp",
    );
    expect(resolvePetAssetUrl("ikun", "icon-hug.webp")).toBe(
      "/pets/ikun/icon-hug.webp",
    );
    expect(resolvePetAssetUrl("ikun", ikunManifest.actionsPath)).toBe(
      "/pets/ikun/actions.json",
    );
    expect(resolvePetAssetUrl("ikun", ikunManifest.rigPath)).toBe(
      "/pets/ikun/rig.json",
    );
    expect(resolvePetAssetUrl("ikun", ikunManifest.actionBoardPath)).toBe(
      "/pets/ikun/action-board.json",
    );
  });

  test("declares ds as a third isolated pet package", () => {
    expect(petIndex.pets).toContain("ds");
    expect(dsManifest.id).toBe("ds");
    expect(dsManifest.spritesheetPath).toBe("spritesheet.webp");
    expect(dsManifest.previewPath).toBe("preview.png");
    expect(resolvePetAssetUrl("ds", dsManifest.spritesheetPath)).toBe(
      "/pets/ds/spritesheet.webp",
    );
    expect(resolvePetAssetUrl("ds", dsManifest.previewPath)).toBe(
      "/pets/ds/preview.png",
    );
  });

  test("documents the route 1 v11 ikun action rows before runtime assignment", () => {
    expect(ikunActions.cell).toEqual({
      width: 192,
      height: 208,
      columns: 8,
      rows: 9,
    });
    expect(ikunActions.version).toBe(11);
    expect(ikunActions.revisionNotes).toContain(
      "Route 1 v11: row 1 tieshankao uses references/tieshankao-ref.jpg, row 3 bie-ganmao uses references/bie-ganmao-ref.jpg with no bubble, and row 7 step-back uses references/step-back-ref.jpg.",
    );
    expect(ikunActions.sourceVideo.url).toBe(
      "https://www.bilibili.com/video/BV1ct4y1n7t9/",
    );
    expect(ikunActions.series.map((series) => series.id)).toEqual([
      "intro-no-ball",
      "body-hit-no-ball",
      "back-view-no-ball",
      "gesture-no-ball",
      "basketball-under-leg",
      "chorus-dance-no-ball",
      "basketball-throw",
      "basketball-step-back",
    ]);
    expect(ikunActions.actions.map((action) => action.id)).toEqual([
      "ready-idle",
      "tieshankao",
      "back-turn-no-ball",
      "bie-ganmao",
      "under-leg-dribble",
      "ji-ni-tai-mei-dance",
      "throw-basketball",
      "step-back",
      "practice-finish",
    ]);

    for (const action of ikunActions.actions) {
      expect(action.row).toBeGreaterThanOrEqual(0);
      expect(action.row).toBeLessThan(ikunActions.cell.rows);
      expect(action.frames).toBeGreaterThan(0);
      expect(action.frames).toBeLessThanOrEqual(ikunActions.cell.columns);
      expect(action.sourceTimes ?? action.prototypeFrames).toHaveLength(
        action.frames,
      );
      expect(ikunActions.series.some((series) => series.id === action.seriesId)).toBe(
        true,
      );
    }

    const basketballModes = Object.fromEntries(
      ikunActions.actions.map((action) => [action.id, action.basketball.mode]),
    );

    expect(basketballModes).toMatchObject({
      "ready-idle": "none",
      "tieshankao": "none",
      "back-turn-no-ball": "none",
      "bie-ganmao": "none",
      "under-leg-dribble": "all",
      "ji-ni-tai-mei-dance": "none",
      "throw-basketball": "mixed",
      "step-back": "all",
      "practice-finish": "none",
    });
    expect(
      ikunActions.actions.find((action) => action.id === "throw-basketball")
        ?.basketball,
    ).toMatchObject({
      mode: "mixed",
      frames: [0, 1, 2, 3],
      absentFrames: [4, 5, 6, 7],
    });
    const implementedUnderLegAction = ikunActions.actions.find(
      (action) => action.id === "under-leg-dribble",
    );
    const implementedBackAction = ikunActions.actions.find(
      (action) => action.id === "back-turn-no-ball",
    );

    expect(implementedUnderLegAction).toBeDefined();
    expect(implementedBackAction).toBeDefined();
    expect(
      (implementedUnderLegAction?.basketball.statesByFrame ?? []).map(
        (frame) => frame.state,
      ),
    ).toContain("under-leg");
    expect(implementedBackAction?.view).toBe("back");

    const motionStatuses = Object.fromEntries(
      ikunActions.actions.map((action) => [action.id, action.motionStatus]),
    );

    expect(motionStatuses).toMatchObject({
      "ready-idle": "usable",
      "tieshankao": "planned-route1-v11",
      "back-turn-no-ball": "repaired-first-pass",
      "bie-ganmao": "planned-route1-v11",
      "under-leg-dribble": "implemented-first-pass",
      "ji-ni-tai-mei-dance": "implemented-first-pass-cleanup",
      "throw-basketball": "repaired-first-pass",
      "step-back": "planned-route1-v11",
      "practice-finish": "usable",
    });

    const referenceMatches = Object.fromEntries(
      ikunActions.actions.map((action) => [action.id, action.referenceMatch]),
    );

    expect(referenceMatches).toMatchObject({
      tieshankao: "route1-reference-tieshankao-ref",
      "bie-ganmao": "route1-reference-bie-ganmao-ref-no-bubble",
      "step-back": "route1-reference-step-back-ref",
    });
    expect(
      ikunActions.actions.find((action) => action.id === "step-back")
        ?.basketball.statesByFrame?.[2],
    ).toMatchObject({
      frame: 2,
      state: "controlled-high",
      rotationDegrees: 90,
    });
  });

  test("documents the ikun rig and next motion board", () => {
    expect(ikunRig.version).toBe(2);
    expect(ikunRig.status).toBe("route1-v11-no-bubble");
    expect(ikunRig.route1References).toMatchObject({
      tieshankao: "references/tieshankao-ref.jpg",
      bieGanmao: "references/bie-ganmao-ref.jpg",
      stepBack: "references/step-back-ref.jpg",
      characterViews: "references/character-views-ref.png",
    });
    expect(ikunRig.sourceImages.characterViews).toBe(
      "references/character-views-ref.png",
    );
    expect(ikunRig.propRules.basketball).toMatchObject({
      isWholeProp: true,
      fragmentationAllowed: false,
      canPassUnderLeg: true,
      canBeThrown: true,
    });
    expect(ikunRig.constraints.map((constraint) => constraint.id)).toEqual([
      "series-continuity",
      "back-view-only",
      "basketball-source-truth",
      "whole-ball",
    ]);
    expect(ikunRig.joints.map((joint) => joint.id)).toEqual([
      "root",
      "spine",
      "neck",
      "left-shoulder",
      "left-elbow",
      "left-wrist",
      "right-shoulder",
      "right-elbow",
      "right-wrist",
      "left-hip",
      "left-knee",
      "left-ankle",
      "right-hip",
      "right-knee",
      "right-ankle",
      "basketball-prop",
    ]);

    expect(
      ikunActionBoard.currentAtlasRows.map((row) => [
        row.row,
        row.seriesId,
        row.basketball,
      ]),
    ).toEqual([
      [0, "intro-no-ball", "none"],
      [1, "body-hit-no-ball", "none"],
      [2, "back-view-no-ball", "none"],
      [3, "gesture-no-ball", "none"],
      [4, "basketball-under-leg", "all"],
      [5, "chorus-dance-no-ball", "none"],
      [6, "basketball-throw", "mixed"],
      [7, "basketball-step-back", "all"],
      [8, "gesture-no-ball", "none"],
    ]);

    expect(ikunActionBoard.plannedSimpleActions.map((action) => action.id)).toEqual([
      "tieshankao",
      "under-leg-dribble",
      "step-back",
      "throw-basketball",
    ]);
    const underLegAction = ikunActionBoard.plannedSimpleActions.find(
      (action) => action.id === "under-leg-dribble",
    );
    const throwAction = ikunActionBoard.plannedSimpleActions.find(
      (action) => action.id === "throw-basketball",
    );

    expect(underLegAction).toBeDefined();
    expect(throwAction).toBeDefined();
    expect(
      (underLegAction?.basketball.statesByFrame ?? []).map(
        (frame) => frame.state,
      ),
    ).toContain("under-leg");
    expect(throwAction?.basketball).toMatchObject({
      mode: "mixed",
      absentFrames: [4, 5, 6, 7],
    });
    expect(
      ikunActionBoard.plannedSimpleActions.map((action) => action.status),
    ).toEqual([
      "planned-route1-v11",
      "implemented-first-pass",
      "planned-route1-v11",
      "repaired-first-pass",
    ]);

    expect(ikunMotionReview.source).toBe(
      "route1-v11-no-bubble-character-views",
    );
    expect(ikunMotionReview.rows).toHaveLength(9);
    for (const row of ikunMotionReview.rows) {
      expect(row.frames).toHaveLength(8);
    }
    expect(ikunMotionReview.referenceUpdates).toContainEqual({
      row: 1,
      action: "tieshankao",
      reference: "references/tieshankao-ref.jpg",
      characterViews: "references/character-views-ref.png",
      basketball: "none",
    });
    expect(ikunMotionReview.referenceUpdates).toContainEqual({
      row: 3,
      action: "bie-ganmao",
      reference: "references/bie-ganmao-ref.jpg",
      characterViews: "references/character-views-ref.png",
      basketball: "none",
      bubble: "none",
    });
    expect(ikunMotionReview.referenceUpdates).toContainEqual({
      row: 7,
      action: "step-back",
      reference: "references/step-back-ref.jpg",
      characterViews: "references/character-views-ref.png",
      basketball: "one-complete-ball-per-frame",
    });
    expect(ikunMotionReview.notes).toContain(
      "Rows 1, 3, and 7 were replaced from route1-v11 decoded strips.",
    );
  });

  test("declares built-in xiaoju sound files with relative package paths", () => {
    const sounds = builtInPetManifest.sounds ?? {};

    expect(Object.keys(sounds).sort()).toEqual([
      "care_reminder",
      "crouchAlert",
      "drag",
      "drag_end",
      "fishChase",
      "fishEat",
      "gnawFish",
      "hugFish",
      "iconHug",
      "idle",
      "tickle",
    ]);

    for (const cues of Object.values(sounds)) {
      expect(cues.length).toBeGreaterThanOrEqual(2);
      for (const cue of cues) {
        expect(cue.path.startsWith("sounds/")).toBe(true);
        expect(cue.path.includes("\\")).toBe(false);
        expect(cue.path.includes(":")).toBe(false);
      }
    }
  });

  test("builds platform catalog items from pet manifests", () => {
    expect(
      createPetCatalog(
        [DEFAULT_PET_ID],
        { [DEFAULT_PET_ID]: builtInPetManifest },
        DEFAULT_PET_ID,
      ),
    ).toMatchObject([
      {
        id: DEFAULT_PET_ID,
        displayName: "小橘",
        description:
          "一只橘黄色毛绒小猫咪，会睡觉、抓鱼、吃鱼、跳来跳去，也会陪你等结果。",
        spritesheetPath: "spritesheet-scruff.webp",
        manifestUrl: "/pets/xiaoju-cat/pet.json",
        previewUrl: "/pets/xiaoju-cat/spritesheet-scruff.webp",
        isActive: true,
      },
    ]);
  });

  test("chooses a valid saved pet before falling back to the default pet", () => {
    expect(chooseInitialPetId(["xiaoju-cat", "sleepy-bunny"], "sleepy-bunny")).toBe(
      "sleepy-bunny",
    );
    expect(chooseInitialPetId(["xiaoju-cat", "sleepy-bunny"], "missing")).toBe(
      DEFAULT_PET_ID,
    );
    expect(chooseInitialPetId(["sleepy-bunny"], "missing")).toBe(
      "sleepy-bunny",
    );
  });
});
