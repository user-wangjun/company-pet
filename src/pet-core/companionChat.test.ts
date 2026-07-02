import { describe, expect, test, vi } from "vitest";
import {
  NEUTRAL_COMPANION_CHAT,
  chooseCompanionChatCue,
  loadPetCompanionChatPackage,
  resolveCompanionChatPackage,
  type CompanionChatConfig,
} from "./companionChat";
import type { PetManifest } from "./petAssets";

const manifest: PetManifest = {
  id: "xiaoju-cat",
  displayName: "小橘",
  description: "test",
  spritesheetPath: "spritesheet.png",
  companionChatPath: "companion-chat.json",
  animations: {
    idle: { row: 0, frames: 1, speed: 0.1, loop: true, visualClass: "ordinary" },
  },
  interactions: {
    idle: { animation: "idle" },
    singleClick: { animation: "idle", durationMs: 1000 },
    doubleClick: { animation: "idle", durationMs: 1000 },
    drag: { directionMode: "rows", right: "idle", left: "idle" },
    reminders: {
      eyeCare: { animation: "idle", durationMs: 1000 },
      water: { animation: "idle", durationMs: 1000 },
      meal: { animation: "idle", durationMs: 1000 },
      sleep: { animation: "idle", durationMs: 1000 },
    },
  },
};

const config: CompanionChatConfig = {
  openers: [
    { text: "喵？", sound: "chatOpenMew", weight: 2 },
    { text: "mew~", sound: "chatOpenMewSoft", weight: 1 },
  ],
  localReplies: ["嗯，我听着。", "慢慢说，我陪你。"],
};

describe("pet companion chat packages", () => {
  test("loads companion chat config from the active pet package", async () => {
    const fetchConfig = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => config,
    }));

    await expect(loadPetCompanionChatPackage(manifest, fetchConfig)).resolves.toEqual({
      status: "loaded",
      petId: "xiaoju-cat",
      config,
    });
    expect(fetchConfig).toHaveBeenCalledWith("/pets/xiaoju-cat/companion-chat.json");
  });

  test("falls back to neutral config when no package is configured", async () => {
    const result = await loadPetCompanionChatPackage({
      ...manifest,
      companionChatPath: undefined,
    });

    expect(resolveCompanionChatPackage(result)).toEqual(NEUTRAL_COMPANION_CHAT);
  });

  test("rejects full greeting sentences as openers", async () => {
    const warn = vi.fn();
    const result = await loadPetCompanionChatPackage(
      manifest,
      async () => ({
        ok: true,
        status: 200,
        json: async () => ({
          openers: [{ text: "我在呢，怎么啦？" }],
          localReplies: ["嗯。"],
        }),
      }),
      warn,
    );

    expect(result).toEqual({ status: "failed", petId: "xiaoju-cat" });
    expect(warn).toHaveBeenCalled();
  });

  test("chooses weighted opener cues deterministically", () => {
    expect(chooseCompanionChatCue(config.openers, () => 0).text).toBe("喵？");
    expect(chooseCompanionChatCue(config.openers, () => 0.66).text).toBe("喵？");
    expect(chooseCompanionChatCue(config.openers, () => 0.99).text).toBe("mew~");
  });
});
