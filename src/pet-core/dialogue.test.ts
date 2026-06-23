import { describe, expect, test, vi } from "vitest";
import dsDialogues from "../../public/pets/ds/dialogues.json";
import dsManifest from "../../public/pets/ds/pet.json";
import suanBirdDialogues from "../../public/pets/suan-bird/dialogues.json";
import {
  getTimedPetDialogueEvent,
  loadPetDialoguePackage,
  resolvePetDialogue,
  type PetDialoguePackage,
} from "./dialogue";
import type { PetManifest } from "./petAssets";

const xiaojuManifest: PetManifest = {
  id: "xiaoju-cat",
  displayName: "小橘",
  description: "test",
  spritesheetPath: "spritesheet.webp",
};

describe("pet dialogue packages", () => {
  test("loads configured dialogue files from the active pet package", async () => {
    const fetchDialogue = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => dsDialogues,
    }));

    const result = await loadPetDialoguePackage(dsManifest, fetchDialogue);

    expect(fetchDialogue).toHaveBeenCalledWith("/pets/ds/dialogues.json");
    expect(result).toEqual({
      status: "loaded",
      petId: "ds",
      dialogues: dsDialogues,
    });
  });

  test("keeps fallback copy only for pets without a dialogue package", async () => {
    const fetchDialogue = vi.fn();
    const result = await loadPetDialoguePackage(xiaojuManifest, fetchDialogue);

    expect(fetchDialogue).not.toHaveBeenCalled();
    expect(resolvePetDialogue(result, "idle", "legacy fallback")).toBe(
      "legacy fallback",
    );
  });

  test("does not cross-pet fallback when a configured package fails", async () => {
    const warn = vi.fn();
    const result = await loadPetDialoguePackage(
      dsManifest,
      async () => ({ ok: false, status: 404, json: async () => ({}) }),
      warn,
    );

    expect(result).toEqual({ status: "failed", petId: "ds" });
    expect(resolvePetDialogue(result, "idle", "小橘 fallback", warn)).toBeNull();
    expect(warn).toHaveBeenCalled();
  });

  test("treats invalid json shapes as a failed configured package", async () => {
    const warn = vi.fn();
    const result = await loadPetDialoguePackage(
      dsManifest,
      async () => ({ ok: true, status: 200, json: async () => [] }),
      warn,
    );

    expect(result).toEqual({ status: "failed", petId: "ds" });
    expect(resolvePetDialogue(result, "idle", "fallback", warn)).toBeNull();
    expect(warn).toHaveBeenCalled();
  });

  test("returns no bubble for a missing or empty configured event", () => {
    const warn = vi.fn();
    const dialoguePackage: PetDialoguePackage = {
      status: "loaded",
      petId: "ds",
      dialogues: { idle: "  " },
    };

    expect(resolvePetDialogue(dialoguePackage, "idle", "fallback", warn)).toBeNull();
    expect(
      resolvePetDialogue(dialoguePackage, "singleClick", "fallback", warn),
    ).toBeNull();
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
    expect(Object.keys(dsDialogues).sort()).toEqual(
      [
        "doubleClick",
        "eyeCare",
        "idle",
        "meal",
        "singleClick",
        "sleep",
        "water",
      ].sort(),
    );
  });
  test("keeps the approved suan-bird double-click line in its pet package", () => {
    expect(suanBirdDialogues.doubleClick).toBe("蒜鸟蒜鸟，都不yong易；");
  });
});
