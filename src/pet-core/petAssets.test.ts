import { describe, expect, test } from "vitest";
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
