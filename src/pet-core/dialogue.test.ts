import { describe, expect, test, vi } from "vitest";
import dsDialogues from "../../public/pets/ds/dialogues.json";
import dsManifest from "../../public/pets/ds/pet.json";
import ikunDialogues from "../../public/pets/ikun/dialogues.json";
import ikunManifest from "../../public/pets/ikun/pet.json";
import suanBirdDialogues from "../../public/pets/suan-bird/dialogues.json";
import suanBirdManifest from "../../public/pets/suan-bird/pet.json";
import xiaojuDialogues from "../../public/pets/xiaoju-cat/dialogues.json";
import xiaojuManifest from "../../public/pets/xiaoju-cat/pet.json";
import {
  getTimedPetDialogueEvent,
  loadPetDialoguePackage,
  NEUTRAL_PET_DIALOGUES,
  PET_DIALOGUE_EVENTS,
  resolvePetDialogue,
  type PetDialoguePackage,
} from "./dialogue";
import type { PetManifest } from "./petAssets";

const xiaojuPetManifest: PetManifest = xiaojuManifest as PetManifest;
const ikunPetManifest: PetManifest = ikunManifest as PetManifest;
const dsPetManifest: PetManifest = dsManifest as PetManifest;
const suanBirdPetManifest: PetManifest = suanBirdManifest as PetManifest;

const noDialogueManifest: PetManifest = {
  id: "test-pet",
  displayName: "测试宠物",
  description: "test",
  spritesheetPath: "spritesheet.webp",
  animations: {
    idle: {
      row: 0,
      frames: 6,
      speed: 0.05,
      loop: true,
      visualClass: "ordinary",
    },
  },
  interactions: {
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
  },
};

const builtInDialoguePackages = [
  ["xiaoju-cat", xiaojuDialogues],
  ["ikun", ikunDialogues],
  ["ds", dsDialogues],
  ["suan-bird", suanBirdDialogues],
] as const;

describe("pet dialogue packages", () => {
  test("loads configured dialogue files from the active pet package", async () => {
    const fetchDialogue = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => dsDialogues,
    }));

    const result = await loadPetDialoguePackage(dsPetManifest, fetchDialogue);

    expect(fetchDialogue).toHaveBeenCalledWith("/pets/ds/dialogues.json");
    expect(result).toEqual({
      status: "loaded",
      petId: "ds",
      dialogues: dsDialogues,
    });
  });

  test("loads xiaoju and ikun dialogue files from their pet packages", async () => {
    const fetchDialogue = vi.fn(async (url: string) => ({
      ok: true,
      status: 200,
      json: async () =>
        url.includes("xiaoju-cat") ? xiaojuDialogues : ikunDialogues,
    }));

    await expect(
      loadPetDialoguePackage(xiaojuPetManifest, fetchDialogue),
    ).resolves.toEqual({
      status: "loaded",
      petId: "xiaoju-cat",
      dialogues: xiaojuDialogues,
    });
    await expect(
      loadPetDialoguePackage(ikunPetManifest, fetchDialogue),
    ).resolves.toEqual({
      status: "loaded",
      petId: "ikun",
      dialogues: ikunDialogues,
    });
    expect(fetchDialogue).toHaveBeenCalledWith(
      "/pets/xiaoju-cat/dialogues.json",
    );
    expect(fetchDialogue).toHaveBeenCalledWith("/pets/ikun/dialogues.json");
  });

  test.each(builtInDialoguePackages)(
    "%s declares every approved dialogue event",
    (_petId, dialogues) => {
      expect(Object.keys(dialogues).sort()).toEqual(
        [...PET_DIALOGUE_EVENTS].sort(),
      );
    },
  );

  test("keeps fallback copy only for pets without a dialogue package", async () => {
    const fetchDialogue = vi.fn();
    const result = await loadPetDialoguePackage(noDialogueManifest, fetchDialogue);

    expect(fetchDialogue).not.toHaveBeenCalled();
    expect(resolvePetDialogue(result, "idle", "legacy fallback")).toBe(
      "legacy fallback",
    );
    expect(resolvePetDialogue(result, "water", null)).toBe(
      NEUTRAL_PET_DIALOGUES.water,
    );
  });

  test("does not cross-pet fallback when a configured package fails", async () => {
    const warn = vi.fn();
    const result = await loadPetDialoguePackage(
      dsPetManifest,
      async () => ({ ok: false, status: 404, json: async () => ({}) }),
      warn,
    );

    expect(result).toEqual({ status: "failed", petId: "ds" });
    expect(resolvePetDialogue(result, "idle", "小橘 fallback", warn)).toBe(
      NEUTRAL_PET_DIALOGUES.idle,
    );
    expect(warn).toHaveBeenCalled();
  });

  test("treats invalid json shapes as a failed configured package", async () => {
    const warn = vi.fn();
    const result = await loadPetDialoguePackage(
      dsPetManifest,
      async () => ({ ok: true, status: 200, json: async () => [] }),
      warn,
    );

    expect(result).toEqual({ status: "failed", petId: "ds" });
    expect(resolvePetDialogue(result, "idle", "fallback", warn)).toBe(
      NEUTRAL_PET_DIALOGUES.idle,
    );
    expect(warn).toHaveBeenCalled();
  });

  test("uses fallback or neutral copy for a missing or empty configured event", () => {
    const warn = vi.fn();
    const dialoguePackage: PetDialoguePackage = {
      status: "loaded",
      petId: "ds",
      dialogues: { idle: "  " },
    };

    expect(resolvePetDialogue(dialoguePackage, "idle", "fallback", warn)).toBe(
      "fallback",
    );
    expect(
      resolvePetDialogue(dialoguePackage, "singleClick", null, warn),
    ).toBe(NEUTRAL_PET_DIALOGUES.singleClick);
    expect(warn).toHaveBeenCalledTimes(2);
  });

  test("maps existing meal and sleep hours without adding timers", () => {
    for (const hour of [7, 8, 11, 12, 18, 19]) {
      expect(getTimedPetDialogueEvent(hour)).toBe("meal");
    }
    for (const hour of [23, 0, 1, 5]) {
      expect(getTimedPetDialogueEvent(hour)).toBe("sleep");
    }
    for (const hour of [6, 9, 13, 14, 20, 22]) {
      expect(getTimedPetDialogueEvent(hour)).toBe("idle");
    }
  });

  test("keeps all approved ds lines free of xiaoju copy", () => {
    const combined = Object.values(dsDialogues).join("\n");

    expect(combined).not.toMatch(/小橘|喵|鱼！|吃到了。/);
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

  test("keeps approved pet-specific reminder copy", () => {
    expect(suanBirdDialogues.doubleClick).toBe("蒜鸟蒜鸟，都不yong易；");
    expect(xiaojuDialogues.water).toContain("喝杯水");
    expect(ikunDialogues.eyeCare).toContain("注意休息");
    expect(suanBirdPetManifest.dialoguesPath).toBe("dialogues.json");
  });
});
