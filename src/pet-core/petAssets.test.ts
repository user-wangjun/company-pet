import { describe, expect, test } from "vitest";
import ikunActionBoard from "../../public/pets/ikun/action-board.json";
import ikunDialogues from "../../public/pets/ikun/dialogues.json";
import ikunActions from "../../public/pets/ikun/actions.json";
import ikunManifest from "../../public/pets/ikun/pet.json";
import ikunMotionReview from "../../public/pets/ikun/qa/motion-review.json";
import ikunRig from "../../public/pets/ikun/rig.json";
import dsDialogues from "../../public/pets/ds/dialogues.json";
import dsManifest from "../../public/pets/ds/pet.json";
import suanBirdManifest from "../../public/pets/suan-bird/pet.json";
import xiaojuDialogues from "../../public/pets/xiaoju-cat/dialogues.json";
import builtInPetManifest from "../../public/pets/xiaoju-cat/pet.json";
import petIndex from "../../public/pets/index.json";
import {
  DEFAULT_PET_ID,
  chooseInitialPetId,
  createPetCatalog,
  getPetBasePath,
  getPetIndexUrl,
  getPetManifestUrl,
  isSafePetRelativePath,
  resolvePetAssetUrl,
} from "./petAssets";
import type { PetManifest } from "./petAssets";
import type { PetManifestInteractions } from "./petInteractionManifest";

const xiaojuPetManifest: PetManifest = builtInPetManifest as PetManifest;
const ikunPetManifest: PetManifest = ikunManifest as PetManifest;
const dsPetManifest: PetManifest = dsManifest as PetManifest;
const suanBirdPetManifest: PetManifest = suanBirdManifest as PetManifest;

const builtInManifests: PetManifest[] = [
  xiaojuPetManifest,
  ikunPetManifest,
  dsPetManifest,
  suanBirdPetManifest,
];

const requiredInteractions: PetManifestInteractions = {
  idle: { animation: "idle" },
  singleClick: { animation: "idle", durationMs: 1000 },
  doubleClick: { animation: "idle", durationMs: 1000 },
  drag: {
    directionMode: "rows",
    right: "idle",
    left: "idle",
  },
  reminders: {
    eyeCare: { animation: "idle", durationMs: 1000 },
    water: { animation: "idle", durationMs: 1000 },
    meal: { animation: "idle", durationMs: 1000 },
    sleep: { animation: "idle", durationMs: 1000 },
  },
};

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

  test.each([
    "spritesheet.webp",
    "nested/preview.png",
    "sounds/cat%20meow.ogg",
  ])("accepts safe pet-relative path %s", (path) => {
    expect(isSafePetRelativePath(path)).toBe(true);
  });

  test.each([
    "%2e%2e/ikun/spritesheet.webp",
    "%252e%252e/ikun/spritesheet.webp",
    "foo%5c..%5cbar",
    "nested/./preview.png",
    "nested/%2e/preview.png",
    "nested/preview.png?cache=1",
    "nested/preview.png#frame",
    "https://example.com/pet.webp",
    "C:/pet.webp",
    "%20",
    "%E0%A4%A",
  ])("rejects unsafe pet-relative path %s", (path) => {
    expect(isSafePetRelativePath(path)).toBe(false);
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
      animations: {
        idle: {
          row: 0,
          frames: 6,
          speed: 0.05,
          loop: true,
          visualClass: "pose-change",
        },
      },
      interactions: requiredInteractions,
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
    expect(builtInPetManifest.dialoguesPath).toBe("dialogues.json");
    expect(resolvePetAssetUrl("xiaoju-cat", builtInPetManifest.dialoguesPath)).toBe(
      "/pets/xiaoju-cat/dialogues.json",
    );
    expect(xiaojuDialogues.sleep).toContain("早点休息");
    expect(builtInPetManifest.animations).toBeDefined();
    expect(builtInPetManifest.interactions).toBeDefined();
  });

  test("declares animation and interaction contracts for every built-in pet", () => {
    for (const manifest of builtInManifests) {
      expect(Object.keys(manifest.animations).length).toBeGreaterThan(0);
      expect(manifest.interactions.idle).toBeDefined();
      expect(manifest.interactions.singleClick).toBeDefined();
      expect(manifest.interactions.doubleClick).toBeDefined();
      expect(manifest.interactions.drag).toBeDefined();
      expect(manifest.interactions.reminders).toBeDefined();
    }
  });

  test("keeps every manifest asset path relative to its pet package", () => {
    const visit = (
      manifest: (typeof builtInManifests)[number],
      value: unknown,
      key = "",
    ): void => {
      if (Array.isArray(value)) {
        for (const item of value) visit(manifest, item, key);
        return;
      }

      if (typeof value !== "object" || value === null) {
        if (key.endsWith("Path") && typeof value === "string") {
          expect(
            isSafePetRelativePath(value),
            `${manifest.id}:${key}`,
          ).toBe(true);
          expect(value.includes("\\"), `${manifest.id}:${key}`).toBe(false);
          expect(resolvePetAssetUrl(manifest.id, value)).toBe(
            `/pets/${manifest.id}/${value}`,
          );
        }
        return;
      }

      for (const [childKey, childValue] of Object.entries(value)) {
        visit(manifest, childValue, childKey);
      }
    };

    for (const manifest of builtInManifests) visit(manifest, manifest);
  });

  test("declares ikun as a second isolated pet package", () => {
    expect(petIndex.pets).toContain("ikun");
    expect(ikunManifest.id).toBe("ikun");
    expect(ikunManifest.spritesheetPath).toBe("spritesheet.webp");
    expect(ikunManifest.previewPath).toBe("preview.png");
    expect(ikunManifest.dialoguesPath).toBe("dialogues.json");
    expect(resolvePetAssetUrl("ikun", ikunManifest.spritesheetPath)).toBe(
      "/pets/ikun/spritesheet.webp",
    );
    expect(resolvePetAssetUrl("ikun", "icon-hug.webp")).toBe(
      "/pets/ikun/icon-hug.webp",
    );
    expect(resolvePetAssetUrl("ikun", ikunManifest.dialoguesPath)).toBe(
      "/pets/ikun/dialogues.json",
    );
    expect(ikunDialogues.water).toContain("喝口水");
  });

  test("declares ds as a third isolated pet package", () => {
    expect(petIndex.pets).toContain("ds");
    expect(dsManifest.id).toBe("ds");
    expect(dsManifest.spritesheetPath).toBe("spritesheet.webp");
    expect(dsManifest.previewPath).toBe("preview.png");
    expect(dsManifest.dialoguesPath).toBe("dialogues.json");
    expect(resolvePetAssetUrl("ds", dsManifest.spritesheetPath)).toBe(
      "/pets/ds/spritesheet.webp",
    );
    expect(resolvePetAssetUrl("ds", dsManifest.previewPath)).toBe(
      "/pets/ds/preview.png",
    );
    expect(resolvePetAssetUrl("ds", dsManifest.dialoguesPath)).toBe(
      "/pets/ds/dialogues.json",
    );
    expect(dsDialogues).toEqual({
      idle: "慢慢来，我们一起向前游一点。",
      singleClick: "贴贴一下，我们一起加油吧。",
      doubleClick: "摆摆尾巴，我们一起向前冲一小步！",
      water: "去喝杯水吧，回来后我们再一起继续努力。",
      eyeCare: "看看远处，放松一下眼睛吧，休息好再一起继续。",
      meal: "到吃饭时间啦，先补充能量，回来后我们继续努力。",
      sleep: "今天已经很努力啦，早点休息吧，明天我们再一起出发。",
    });
  });

  test("maps ds drag rows to the matching visual direction", () => {
    expect(dsManifest.animations.dragLeft.row).toBe(1);
    expect(dsManifest.animations.dragRight.row).toBe(2);
    expect(dsManifest.interactions.drag).toMatchObject({
      directionMode: "rows",
      left: "dragLeft",
      right: "dragRight",
    });
  });

  test("declares suan-bird as an isolated pet package", () => {
    expect(petIndex.pets).toContain("suan-bird");
    expect(suanBirdManifest.id).toBe("suan-bird");
    expect(suanBirdManifest.displayName).toBe("蒜鸟");
    expect(suanBirdManifest.spritesheetPath).toBe("spritesheet.webp");
    expect(suanBirdManifest.previewPath).toBe("preview.png");
    expect(suanBirdManifest.dialoguesPath).toBe("dialogues.json");
    expect(resolvePetAssetUrl("suan-bird", suanBirdManifest.spritesheetPath)).toBe(
      "/pets/suan-bird/spritesheet.webp",
    );
    expect(resolvePetAssetUrl("suan-bird", suanBirdManifest.previewPath)).toBe(
      "/pets/suan-bird/preview.png",
    );
    expect(resolvePetAssetUrl("suan-bird", suanBirdManifest.dialoguesPath)).toBe(
      "/pets/suan-bird/dialogues.json",
    );
  });

  test("documents the route 1 v15 ikun action rows and double-click jump", () => {
    expect(ikunActions.cell).toEqual({
      width: 192,
      height: 208,
      columns: 8,
      rows: 9,
    });
    expect(ikunActions.version).toBe(15);
    expect(ikunActions.revisionNotes).toContain(
      "Route 1 v11: row 1 tieshankao uses references/tieshankao-ref.jpg, row 3 bie-ganmao uses references/bie-ganmao-ref.jpg with no bubble, and row 7 step-back uses references/step-back-ref.jpg.",
    );
    expect(ikunActions.revisionNotes).toContain(
      "Route 1 v12: row 4 under-leg-dribble uses references/under-leg-dribble-ref.png as the authoritative 01-08 pose and ball-path standard.",
    );
    expect(ikunActions.revisionNotes).toContain(
      "路线 1 v14：第 6 行 09-16 帧清除脚边白色背景，运行时追加 throw-finish.png 作为无球第 17 帧。",
    );
    expect(ikunActions.revisionNotes).toContain(
      "Route 1 v15: row 8 replaces the old practice-finish double-click action with the user-provided 8-frame jump reference.",
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
      "jump-no-ball",
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
      "jump",
    ]);

    for (const action of ikunActions.actions) {
      expect(action.row).toBeGreaterThanOrEqual(0);
      expect(action.row).toBeLessThan(ikunActions.cell.rows);
      expect(action.frames).toBeGreaterThan(0);
      const atlasFrames =
        "atlasFrames" in action ? action.atlasFrames : action.frames;
      expect(atlasFrames).toBeLessThanOrEqual(ikunActions.cell.columns);
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
      "throw-basketball": "throw-then-disappear",
      "step-back": "all",
      jump: "none",
    });
    expect(
      ikunActions.actions.find((action) => action.id === "throw-basketball")
        ?.basketball,
    ).toMatchObject({
      mode: "throw-then-disappear",
      frames: [0, 1, 2, 3, 4, 5, 6, 7],
      absentFrames: [8],
    });
    expect(
      ikunActions.actions.find((action) => action.id === "throw-basketball"),
    ).toMatchObject({
      sourceImage: "references/throw-09-16-ref.png",
      finishSourceImage: "references/throw-finish-ref.png",
      finishFramePath: "throw-finish.png",
      atlasFrames: 8,
      runtimeFrames: 9,
      sourceFrames: ["09", "10", "11", "12", "13", "14", "15", "16", "17"],
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
    ).toEqual([
      "held-image-left",
      "dribble-image-left-low",
      "center-entry",
      "under-leg-center",
      "emerge-image-left",
      "controlled-image-left-low",
      "center-return",
      "held-image-right",
    ]);
    expect(implementedBackAction?.view).toBe("back");

    const motionStatuses = Object.fromEntries(
      ikunActions.actions.map((action) => [action.id, action.motionStatus]),
    );

    expect(motionStatuses).toMatchObject({
      "ready-idle": "usable",
      "tieshankao": "planned-route1-v11",
      "back-turn-no-ball": "repaired-first-pass",
      "bie-ganmao": "planned-route1-v11",
      "under-leg-dribble": "reference-standard-v12",
      "ji-ni-tai-mei-dance": "implemented-first-pass-cleanup",
      "throw-basketball": "reference-standard-v14",
      "step-back": "planned-route1-v11",
      jump: "reference-standard-v15",
    });

    const referenceMatches = Object.fromEntries(
      ikunActions.actions.map((action) => [action.id, action.referenceMatch]),
    );

    expect(referenceMatches).toMatchObject({
      tieshankao: "route1-reference-tieshankao-ref",
      "bie-ganmao": "route1-reference-bie-ganmao-ref-no-bubble",
      "under-leg-dribble": "route1-reference-under-leg-dribble-ref",
      "throw-basketball": "route1-reference-throw-09-17-finish",
      "step-back": "route1-reference-step-back-ref",
      jump: "user-reference-jump-v15",
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
    expect(ikunRig.status).toBe("route1-v12-under-leg-reference");
    expect(ikunRig.route1References).toMatchObject({
      tieshankao: "references/tieshankao-ref.jpg",
      bieGanmao: "references/bie-ganmao-ref.jpg",
      underLegDribble: "references/under-leg-dribble-ref.png",
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
      [6, "basketball-throw", "all-in-atlas-final-none"],
      [7, "basketball-step-back", "all"],
      [8, "jump-no-ball", "none"],
    ]);

    expect(ikunActionBoard.plannedSimpleActions.map((action) => action.id)).toEqual([
      "tieshankao",
      "under-leg-dribble",
      "step-back",
      "throw-basketball",
      "jump",
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
    ).toEqual([
      "held-image-left",
      "dribble-image-left-low",
      "center-entry",
      "under-leg-center",
      "emerge-image-left",
      "controlled-image-left-low",
      "center-return",
      "held-image-right",
    ]);
    expect(throwAction?.basketball).toMatchObject({
      mode: "throw-then-disappear",
      frames: [0, 1, 2, 3, 4, 5, 6, 7],
      absentFrames: [8],
    });
    expect(throwAction).toMatchObject({
      sourceImage: "references/throw-09-16-ref.png",
      finishSourceImage: "references/throw-finish-ref.png",
      finishFramePath: "throw-finish.png",
      sourceFrames: ["09", "10", "11", "12", "13", "14", "15", "16", "17"],
    });
    expect(
      ikunActionBoard.plannedSimpleActions.map((action) => action.status),
    ).toEqual([
      "planned-route1-v11",
      "reference-standard-v12",
      "planned-route1-v11",
      "reference-standard-v14",
      "reference-standard-v15",
    ]);

    expect(ikunMotionReview.source).toBe("route1-v15-double-click-jump");
    expect(ikunMotionReview.rows).toHaveLength(9);
    for (const row of ikunMotionReview.rows) {
      expect(row.frames).toHaveLength(row.row === 6 ? 9 : 8);
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
      row: 4,
      action: "under-leg-dribble",
      reference: "references/under-leg-dribble-ref.png",
      basketball: "one-complete-ball-per-frame",
      frameOrder: "01-08",
    });
    expect(ikunMotionReview.referenceUpdates).toContainEqual({
      row: 6,
      action: "throw-basketball",
      reference: "references/throw-09-16-ref.png",
      finishReference: "references/throw-finish-ref.png",
      finishFramePath: "throw-finish.png",
      basketball: "frames-09-16-ball-frame-17-none",
      frameOrder: "09-17",
    });
    expect(ikunMotionReview.referenceUpdates).toContainEqual({
      row: 7,
      action: "step-back",
      reference: "references/step-back-ref.jpg",
      characterViews: "references/character-views-ref.png",
      basketball: "one-complete-ball-per-frame",
    });
    expect(ikunMotionReview.referenceUpdates).toContainEqual({
      row: 8,
      action: "jump",
      reference: "references/jump-ref.png",
      basketball: "none",
      frameOrder: "01-08",
      runtimeAnimation: "fishEat",
      trigger: "double-click",
    });
    expect(ikunMotionReview.notes).toContain(
      "Rows 1, 3, and 7 were replaced from route1-v11 decoded strips.",
    );
    expect(ikunMotionReview.notes).toContain(
      "Row 4 was replaced from the user-provided 01-08 under-leg dribble reference and is the idle dribble standard.",
    );
    expect(ikunMotionReview.notes).toContain(
      "Row 8 was replaced from the user-provided 01-08 jump reference and is the ikun double-click action.",
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
        { [DEFAULT_PET_ID]: xiaojuPetManifest },
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
        previewKind: "spritesheet",
        isActive: true,
      },
    ]);

    expect(
      createPetCatalog(
        ["ikun", "ds"],
        {
          ikun: ikunPetManifest,
          ds: dsPetManifest,
        },
        "ds",
      ),
    ).toMatchObject([
      {
        id: "ikun",
        previewUrl: "/pets/ikun/preview.png",
        previewKind: "image",
        isActive: false,
      },
      {
        id: "ds",
        previewUrl: "/pets/ds/preview.png",
        previewKind: "image",
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
