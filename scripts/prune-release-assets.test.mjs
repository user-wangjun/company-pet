import { afterEach, describe, expect, it } from "vitest";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { pruneReleaseAssets } from "./prune-release-assets.mjs";

const temporaryDirectories = [];

function writeFixtureFile(root, path, contents = "fixture") {
  const filePath = join(root, path);
  mkdirSync(dirname(filePath), { recursive: true });
  writeFileSync(filePath, contents);
}

afterEach(() => {
  for (const directory of temporaryDirectories.splice(0)) {
    rmSync(directory, { recursive: true, force: true });
  }
});

describe("pruneReleaseAssets", () => {
  it("keeps registered manifest assets and removes development-only files", () => {
    const distDirectory = mkdtempSync(join(tmpdir(), "pet-release-prune-"));
    temporaryDirectories.push(distDirectory);

    writeFixtureFile(distDirectory, "pets/index.json", JSON.stringify({ pets: ["test-pet"] }));
    writeFixtureFile(
      distDirectory,
      "pets/test-pet/pet.json",
      JSON.stringify({
        id: "test-pet",
        spritesheetPath: "spritesheet.png",
        sounds: { click: [{ path: "sounds/click.ogg" }] },
      }),
    );
    writeFixtureFile(distDirectory, "pets/test-pet/spritesheet.png");
    writeFixtureFile(distDirectory, "pets/test-pet/sounds/click.ogg");
    writeFixtureFile(distDirectory, "pets/test-pet/qa/contact-sheet.png");
    writeFixtureFile(distDirectory, "pets/unregistered/pet.json");
    writeFixtureFile(distDirectory, "vendor/live2d-cubism-core/live2dcubismcore.min.js");
    writeFixtureFile(distDirectory, "marketing-assets/healing-world-v2.png");
    writeFixtureFile(distDirectory, "marketing-assets/marketing-morning.png");

    pruneReleaseAssets(distDirectory);

    expect(existsSync(join(distDirectory, "pets/test-pet/spritesheet.png"))).toBe(true);
    expect(existsSync(join(distDirectory, "pets/test-pet/sounds/click.ogg"))).toBe(true);
    expect(existsSync(join(distDirectory, "pets/test-pet/qa"))).toBe(false);
    expect(existsSync(join(distDirectory, "pets/unregistered"))).toBe(false);
    expect(existsSync(join(distDirectory, "vendor/live2d-cubism-core"))).toBe(false);
    expect(existsSync(join(distDirectory, "marketing-assets/healing-world-v2.png"))).toBe(true);
    expect(existsSync(join(distDirectory, "marketing-assets/marketing-morning.png"))).toBe(false);
  });
});
