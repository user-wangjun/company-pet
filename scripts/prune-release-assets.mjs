import {
  existsSync,
  readFileSync,
  readdirSync,
  lstatSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join, relative, resolve, sep } from "node:path";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const defaultDistDirectory = resolve(scriptDirectory, "../dist");

const marketingAssetsToKeep = new Set([
  "foreground-clouds-v2.png",
  "healing-world-v2.png",
  "planet-earth-v2.png",
  "planet-honey-v2.png",
  "planet-moon-v2.png",
  "universe-backdrop-v2.png",
  "wechat-qrcode.jpg",
]);

function toPosixPath(path) {
  return path.split(sep).join("/");
}

function listFiles(directory) {
  if (!existsSync(directory)) return [];

  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = join(directory, entry.name);
    return entry.isDirectory() ? listFiles(entryPath) : [entryPath];
  });
}

function rejectAssetLinks(directory) {
  if (lstatSync(directory).isSymbolicLink()) throw new Error("Release assets cannot contain links");
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.isSymbolicLink()) throw new Error("Release assets cannot contain links");
    if (entry.isDirectory()) rejectAssetLinks(join(directory, entry.name));
  }
}

function collectManifestAssetPaths(value, key = "", paths = new Set()) {
  if (Array.isArray(value)) {
    for (const item of value) collectManifestAssetPaths(item, key, paths);
    return paths;
  }

  if (value && typeof value === "object") {
    for (const [nestedKey, nestedValue] of Object.entries(value)) {
      collectManifestAssetPaths(nestedValue, nestedKey, paths);
    }
    return paths;
  }

  if (typeof value !== "string" || (key !== "path" && !key.endsWith("Path"))) {
    return paths;
  }

  const normalizedPath = value.replaceAll("\\", "/");
  if (
    normalizedPath.startsWith("/") ||
    /^[a-z]:\//i.test(normalizedPath) ||
    normalizedPath.split("/").includes("..")
  ) {
    throw new Error(`Unsafe pet asset path in manifest: ${value}`);
  }

  paths.add(normalizedPath);
  return paths;
}

function removeEmptyDirectories(directory, preserveRoot = true) {
  if (!existsSync(directory)) return;

  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) removeEmptyDirectories(join(directory, entry.name), false);
  }

  if (!preserveRoot && readdirSync(directory).length === 0) {
    rmSync(directory, { recursive: true, force: true });
  }
}

function planPetPruning(distDirectory) {
  const petsDirectory = join(distDirectory, "pets");
  const registryPath = join(petsDirectory, "index.json");
  if (!existsSync(registryPath)) return () => {};
  rejectAssetLinks(petsDirectory);

  const registry = JSON.parse(readFileSync(registryPath, "utf8"));
  const registeredPetIds = new Set(registry.pets ?? []);
  if (!Array.isArray(registry.pets) || registeredPetIds.size !== registry.pets.length
    || [...registeredPetIds].some(id => typeof id !== "string" || !/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(id))) throw new Error("Invalid pet release registry");
  const privatePetIds = new Set(registry.privatePets ?? []);
  if (registry.privatePets !== undefined && (!Array.isArray(registry.privatePets)
    || privatePetIds.size !== registry.privatePets.length
    || [...privatePetIds].some(id => !registeredPetIds.has(id)))) throw new Error("Invalid private pet registry");
  for (const id of privatePetIds) registeredPetIds.delete(id);
  if (registeredPetIds.size === 0) throw new Error("Release must contain at least one public pet");
  const deletions = [];

  for (const entry of readdirSync(petsDirectory, { withFileTypes: true })) {
    if (entry.isDirectory() && !registeredPetIds.has(entry.name)) {
      deletions.push(...listFiles(join(petsDirectory, entry.name)));
    }
  }

  for (const petId of registeredPetIds) {
    const petDirectory = join(petsDirectory, petId);
    const manifestPath = join(petDirectory, "pet.json");
    if (!existsSync(manifestPath)) {
      throw new Error(`Missing manifest for built-in pet: ${petId}`);
    }

    const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
    if (manifest.id !== petId) throw new Error(`Pet manifest identity mismatch: ${petId}`);
    const filesToKeep = collectManifestAssetPaths(manifest);
    filesToKeep.add("pet.json");
    const resolveReference = (from, value) => {
      if (typeof value !== "string" || !value || /[%\\:?#\u0000-\u001f\u007f]/.test(value) || value.startsWith("/")
        || value.split("/").some(part => !part || part !== "." && part !== ".." && /[. ]$/.test(part))) throw new Error(`Invalid pet release reference: ${value}`);
      const absolute = resolve(petDirectory, dirname(from), value);
      const local = toPosixPath(relative(petDirectory, absolute));
      if (!absolute.startsWith(`${resolve(petDirectory)}${sep}`) || local.split("/").some(part => part.toLowerCase() === "qa")) throw new Error(`Pet release reference escapes runtime package: ${value}`);
      return local;
    };
    const requireFile = (path) => {
      const normalized = resolveReference("pet.json", path);
      let current = resolve(petDirectory);
      if (lstatSync(current).isSymbolicLink()) throw new Error("Pet release package cannot be a link");
      for (const part of normalized.split("/")) {
        current = join(current, part);
        if (!existsSync(current)) throw new Error(`Missing manifest asset for ${petId}: ${path}`);
        if (lstatSync(current).isSymbolicLink()) throw new Error("Pet release asset cannot be a link");
      }
      if (!lstatSync(current).isFile()) throw new Error(`Pet asset must be a file: ${path}`);
      return current;
    };
    const read = (path) => JSON.parse(readFileSync(requireFile(path), "utf8"));
    const runtime = new Set();
    const add = (from, reference) => {
      const path = resolveReference(from, reference); requireFile(path); filesToKeep.add(path); runtime.add(path); return path;
    };
    if (manifest.rig2d) {
      const contractPath = add("pet.json", manifest.rig2d.meshPath);
      add("pet.json", manifest.rig2d.modelPath); add("pet.json", manifest.rig2d.actionsPath);
      const contract = read(contractPath);
      if (!Array.isArray(contract.meshes) || !contract.meshes.length) throw new Error("Invalid rig release contract");
      const visited = new Set();
      for (const entry of contract.meshes) {
        const meshPath = add(contractPath, entry.path);
        if (visited.has(meshPath)) continue;
        visited.add(meshPath);
        const mesh = read(meshPath);
        // clipping.mask is a node id; only an actual mask mesh loads mask as a file.
        add(meshPath, mesh.isClippingMask ? mesh.mask : mesh.texture);
        if (mesh.colourDetail) add(meshPath, mesh.colourDetail.texture);
      }
    } else if (manifest.spritesheetPath) {
      runtime.add(resolveReference("pet.json", manifest.spritesheetPath));
    }
    if (manifest.roomActorPath) {
      const actorPath = add("pet.json", manifest.roomActorPath), actor = read(actorPath);
      if (actor.schemaVersion !== 1 || !Array.isArray(actor.resources)) throw new Error("Invalid room actor release contract");
      if (actor.renderer !== (manifest.rig2d ? "rig2d" : "spritesheet")) throw new Error("Room actor release backend mismatch");
      if (!manifest.rig2d) {
        for (const clip of Object.values(actor.clips ?? {})) {
          const animation = manifest.animations?.[clip.resourceId];
          if (!animation) throw new Error("Missing room actor animation");
          for (const path of [animation.spritesheetPath, animation.finishFramePath]) if (path) runtime.add(resolveReference("pet.json", path));
        }
      }
      const declared = new Set(actor.resources.map(path => resolveReference("pet.json", path)));
      if (declared.size !== actor.resources.length || [...runtime].some(path => !declared.has(path))) throw new Error("Room actor resources omit runtime dependencies");
      for (const path of declared) { requireFile(path); filesToKeep.add(path); }
    }

    for (const assetPath of [...filesToKeep]) {
      requireFile(assetPath);
      const normalized = resolveReference("pet.json", assetPath);
      if (normalized !== assetPath) { filesToKeep.delete(assetPath); filesToKeep.add(normalized); }
    }

    for (const filePath of listFiles(petDirectory)) {
      const packagePath = toPosixPath(relative(petDirectory, filePath));
      if (!filesToKeep.has(packagePath)) deletions.push(filePath);
    }

  }
  return () => {
    for (const file of deletions) {
      if (!resolve(file).startsWith(`${resolve(petsDirectory)}${sep}`)) throw new Error("Pet pruning escapes build output");
      rmSync(file, { force: true });
    }
    removeEmptyDirectories(petsDirectory);
    if (registry.privatePets !== undefined) {
      const { privatePets: _privatePets, ...publicRegistry } = registry;
      writeFileSync(registryPath, `${JSON.stringify({ ...publicRegistry, pets: [...registeredPetIds] }, null, 2)}\n`);
    }
  };
}

function pruneMarketingAssets(distDirectory) {
  const marketingDirectory = join(distDirectory, "marketing-assets");
  for (const filePath of listFiles(marketingDirectory)) {
    const assetPath = toPosixPath(relative(marketingDirectory, filePath));
    if (!marketingAssetsToKeep.has(assetPath)) rmSync(filePath, { force: true });
  }
  removeEmptyDirectories(marketingDirectory);
}

export function pruneReleaseAssets(distDirectory = defaultDistDirectory) {
  const prunePets = planPetPruning(distDirectory);
  const deferredVendorDirectory = join(distDirectory, "vendor/live2d-cubism-core");
  if (existsSync(deferredVendorDirectory)) {
    rmSync(deferredVendorDirectory, { recursive: true, force: true });
  }

  prunePets();
  pruneMarketingAssets(distDirectory);
}

const invokedPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : "";
if (invokedPath === import.meta.url) pruneReleaseAssets();
