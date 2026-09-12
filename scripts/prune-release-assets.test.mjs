import { afterEach, describe, expect, it } from "vitest";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync, symlinkSync } from "node:fs";
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
  it("removes private pets and their registration from release output while preserving source assets", () => {
    const directory = mkdtempSync(join(tmpdir(), "private-pet-release-")); temporaryDirectories.push(directory);
    const dist = join(directory, "dist");
    const registry = { pets: ["public-pet", "private-human"], privatePets: ["private-human"] };
    writeFixtureFile(directory, "public/pets/index.json", JSON.stringify(registry));
    writeFixtureFile(directory, "public/pets/private-human/model/secret.png", "private-art");
    writeFixtureFile(dist, "pets/index.json", JSON.stringify(registry));
    writeFixtureFile(dist, "pets/public-pet/pet.json", JSON.stringify({ id: "public-pet", spritesheetPath: "sprite.png" }));
    writeFixtureFile(dist, "pets/public-pet/sprite.png");
    writeFixtureFile(dist, "pets/private-human/pet.json", JSON.stringify({ id: "private-human", rig2d: {} }));
    writeFixtureFile(dist, "pets/private-human/model/secret.png", "private-art");
    pruneReleaseAssets(dist);
    expect(JSON.parse(readFileSync(join(dist, "pets/index.json"), "utf8"))).toEqual({ pets: ["public-pet"] });
    expect(existsSync(join(dist, "pets/private-human"))).toBe(false);
    expect(existsSync(join(dist, "pets/public-pet/sprite.png"))).toBe(true);
    expect(readFileSync(join(directory, "public/pets/private-human/model/secret.png"), "utf8")).toBe("private-art");
    expect(JSON.parse(readFileSync(join(directory, "public/pets/index.json"), "utf8"))).toEqual(registry);
    pruneReleaseAssets(dist);
    expect(existsSync(join(dist, "pets/private-human"))).toBe(false);
  });

  it("retains normalized local references and refuses junctions before deleting output", () => {
    const directory = mkdtempSync(join(tmpdir(), "pet-link-check-")); temporaryDirectories.push(directory);
    writeFixtureFile(directory, "pets/index.json", JSON.stringify({ pets: ["test-pet"] }));
    writeFixtureFile(directory, "pets/test-pet/pet.json", JSON.stringify({ id: "test-pet", spritesheetPath: "./sprite.png" }));
    writeFixtureFile(directory, "pets/test-pet/sprite.png");
    pruneReleaseAssets(directory);
    expect(existsSync(join(directory, "pets/test-pet/sprite.png"))).toBe(true);
    writeFixtureFile(directory, "outside/sentinel.png");
    symlinkSync(join(directory, "outside"), join(directory, "pets/unregistered-link"), "junction");
    expect(() => pruneReleaseAssets(directory)).toThrow(/links/);
    expect(existsSync(join(directory, "outside/sentinel.png"))).toBe(true);
    // Remove only the test-created junction before recursive fixture cleanup.
    rmSync(join(directory, "pets/unregistered-link"), { recursive: true });
  });
  it("preserves rig contract-relative meshes, textures, detail layers and real clipping masks", () => {
    const directory = mkdtempSync(join(tmpdir(), "rig-dependencies-")); temporaryDirectories.push(directory);
    writeFixtureFile(directory, "pets/index.json", JSON.stringify({ pets: ["rig-pet"] }));
    const resources = ["room-actor.json", "rig/contract.json", "rig/model.json", "rig/actions.json", "rig/parts/body.json", "rig/parts/mask.json", "rig/textures/body.png", "rig/textures/detail.png", "rig/textures/mask.png"];
    writeFixtureFile(directory, "pets/rig-pet/pet.json", JSON.stringify({ id: "rig-pet", roomActorPath: "room-actor.json", rig2d: { meshPath: resources[1], modelPath: resources[2], actionsPath: resources[3] } }));
    writeFixtureFile(directory, "pets/rig-pet/room-actor.json", JSON.stringify({ schemaVersion: 1, renderer: "rig2d", resources }));
    writeFixtureFile(directory, "pets/rig-pet/rig/contract.json", JSON.stringify({ meshes: [{ path: "parts/body.json" }, { path: "parts/mask.json" }] }));
    writeFixtureFile(directory, "pets/rig-pet/rig/parts/body.json", JSON.stringify({ texture: "../textures/body.png", mask: "unused-authoring-mask.png", isClippingMask: false, clipping: { mask: "mask-node" }, colourDetail: { texture: "../textures/detail.png" } }));
    writeFixtureFile(directory, "pets/rig-pet/rig/parts/mask.json", JSON.stringify({ isClippingMask: true, mask: "../textures/mask.png" }));
    for (const path of resources.filter(path => !["room-actor.json", "rig/contract.json", "rig/parts/body.json", "rig/parts/mask.json"].includes(path))) writeFixtureFile(directory, `pets/rig-pet/${path}`, path.endsWith(".json") ? "{}" : "texture");
    writeFixtureFile(directory, "pets/rig-pet/qa/review.png");
    pruneReleaseAssets(directory);
    for (const path of resources) expect(existsSync(join(directory, `pets/rig-pet/${path}`))).toBe(true);
    expect(existsSync(join(directory, "pets/rig-pet/qa"))).toBe(false);
  });

  it.each(["missing", "undeclared", "encoded", "escape", "qa"])("rejects %s actor dependency before pruning any package or vendor", (problem) => {
    const directory = mkdtempSync(join(tmpdir(), "actor-preflight-")); temporaryDirectories.push(directory);
    writeFixtureFile(directory, "pets/index.json", JSON.stringify({ pets: ["first", "second"] }));
    writeFixtureFile(directory, "pets/first/pet.json", JSON.stringify({ id: "first", spritesheetPath: "sprite.png" }));
    writeFixtureFile(directory, "pets/first/sprite.png"); writeFixtureFile(directory, "pets/first/qa/review.png");
    const asset = problem === "encoded" ? "%252e%252e/outside.png" : problem === "escape" ? "../outside.png" : problem === "qa" ? "qa/review.png" : "sprite.png";
    writeFixtureFile(directory, "pets/second/pet.json", JSON.stringify({ id: "second", spritesheetPath: asset, roomActorPath: "room-actor.json" }));
    writeFixtureFile(directory, "pets/second/room-actor.json", JSON.stringify({ schemaVersion: 1, renderer: "spritesheet", resources: problem === "undeclared" ? ["room-actor.json"] : ["room-actor.json", asset] }));
    if (problem !== "missing") writeFixtureFile(directory, "pets/second/sprite.png");
    writeFixtureFile(directory, "pets/unregistered/pet.json");
    writeFixtureFile(directory, "vendor/live2d-cubism-core/core.js");
    expect(() => pruneReleaseAssets(directory)).toThrow();
    expect(existsSync(join(directory, "pets/first/qa/review.png"))).toBe(true);
    expect(existsSync(join(directory, "pets/unregistered/pet.json"))).toBe(true);
    expect(existsSync(join(directory, "vendor/live2d-cubism-core/core.js"))).toBe(true);
  });

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
