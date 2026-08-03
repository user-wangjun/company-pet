import { describe, expect, test, vi } from "vitest";
import type { PetManifest } from "./petAssets";
import {
  DEFAULT_PET_SOUL_PATH,
  MAX_PET_SOUL_CHARACTERS,
  NEUTRAL_PET_SOUL,
  loadPetSoulPackage,
  resolvePetSoulPackage,
} from "./petSoul";

const manifest = (id: string, soulPath?: string): PetManifest =>
  ({
    id,
    displayName: id,
    description: "test pet",
    spritesheetPath: "spritesheet.png",
    soulPath,
    animations: {
      idle: {
        row: 0,
        frames: 1,
        speed: 0.1,
        loop: true,
        visualClass: "ordinary",
      },
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
  }) as PetManifest;

function response(content: string, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => content,
  };
}

describe("pet Soul packages", () => {
  test("loads Soul from a relative path inside the active pet package", async () => {
    const fetchSoul = vi.fn(async (_url: string) =>
      response("# Identity\n\nA quiet test pet."),
    );

    const result = await loadPetSoulPackage(
      manifest("xiaoju-cat", DEFAULT_PET_SOUL_PATH),
      fetchSoul,
    );

    expect(result).toMatchObject({
      status: "loaded",
      petId: "xiaoju-cat",
      path: "SOUL.md",
      content: "# Identity\n\nA quiet test pet.",
    });
    expect(fetchSoul).toHaveBeenCalledWith("/pets/xiaoju-cat/SOUL.md");
  });

  test.each([
    "%2e%2e/ikun/SOUL.md",
    "",
    "C:/outside/SOUL.md",
  ])("rejects traversal and illegal path %s before reading", async (soulPath) => {
    const fetchSoul = vi.fn(async () => response("should not load"));
    const warn = vi.fn();

    const result = await loadPetSoulPackage(
      manifest("xiaoju-cat", soulPath),
      fetchSoul,
      warn,
    );

    expect(result).toMatchObject({
      status: "failed",
      petId: "xiaoju-cat",
      reason: "invalid-path",
    });
    expect(resolvePetSoulPackage(result)).toBe(NEUTRAL_PET_SOUL);
    expect(fetchSoul).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalled();
  });

  test.each([
    ["missing", "missing"],
    ["read failure", "read-failed"],
    ["too long", "too-long"],
  ])("uses neutral fallback for %s Soul", async (label, reason) => {
    const warn = vi.fn();
    const fetchSoul = vi.fn(async () => {
      if (label === "missing") return response("", 404);
      if (label === "read failure") throw new Error("network down");
      return response("x".repeat(MAX_PET_SOUL_CHARACTERS + 1));
    });

    const result = await loadPetSoulPackage(
      manifest("xiaoju-cat", DEFAULT_PET_SOUL_PATH),
      fetchSoul,
      warn,
    );

    expect(result).toMatchObject({ status: "failed", reason });
    expect(resolvePetSoulPackage(result)).toBe(NEUTRAL_PET_SOUL);
    expect(warn).toHaveBeenCalled();
  });

  test("keeps different pet Souls isolated", async () => {
    const xiaoju = await loadPetSoulPackage(
      manifest("xiaoju-cat", DEFAULT_PET_SOUL_PATH),
      async () => response("小橘只在自己的包里。"),
    );
    const ikun = await loadPetSoulPackage(
      manifest("ikun", DEFAULT_PET_SOUL_PATH),
      async () => response("ikun 只在自己的包里。"),
    );

    expect(resolvePetSoulPackage(xiaoju)).toContain("小橘");
    expect(resolvePetSoulPackage(xiaoju)).not.toContain("ikun");
    expect(resolvePetSoulPackage(ikun)).toContain("ikun");
    expect(resolvePetSoulPackage(ikun)).not.toContain("小橘");
  });

  test("uses neutral fallback when a pet has no Soul path", async () => {
    const fetchSoul = vi.fn(async () => response("should not load"));

    const result = await loadPetSoulPackage(manifest("ikun"), fetchSoul);

    expect(result).toEqual({ status: "not-configured", petId: "ikun" });
    expect(resolvePetSoulPackage(result)).toBe(NEUTRAL_PET_SOUL);
    expect(fetchSoul).not.toHaveBeenCalled();
  });
});
