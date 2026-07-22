import {
  existsSync,
  readFileSync,
  readdirSync,
  rmSync,
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

function prunePetPackages(distDirectory) {
  const petsDirectory = join(distDirectory, "pets");
  const registryPath = join(petsDirectory, "index.json");
  if (!existsSync(registryPath)) return;

  const registry = JSON.parse(readFileSync(registryPath, "utf8"));
  const registeredPetIds = new Set(registry.pets ?? []);

  for (const entry of readdirSync(petsDirectory, { withFileTypes: true })) {
    if (entry.isDirectory() && !registeredPetIds.has(entry.name)) {
      rmSync(join(petsDirectory, entry.name), { recursive: true, force: true });
    }
  }

  for (const petId of registeredPetIds) {
    const petDirectory = join(petsDirectory, petId);
    const manifestPath = join(petDirectory, "pet.json");
    if (!existsSync(manifestPath)) {
      throw new Error(`Missing manifest for built-in pet: ${petId}`);
    }

    const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
    const filesToKeep = collectManifestAssetPaths(manifest);
    filesToKeep.add("pet.json");

    for (const assetPath of filesToKeep) {
      if (!existsSync(join(petDirectory, assetPath))) {
        throw new Error(`Missing manifest asset for ${petId}: ${assetPath}`);
      }
    }

    for (const filePath of listFiles(petDirectory)) {
      const packagePath = toPosixPath(relative(petDirectory, filePath));
      if (!filesToKeep.has(packagePath)) rmSync(filePath, { force: true });
    }

    removeEmptyDirectories(petDirectory);
  }
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
  const deferredVendorDirectory = join(distDirectory, "vendor/live2d-cubism-core");
  if (existsSync(deferredVendorDirectory)) {
    rmSync(deferredVendorDirectory, { recursive: true, force: true });
  }

  prunePetPackages(distDirectory);
  pruneMarketingAssets(distDirectory);
}

const invokedPath = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : "";
if (invokedPath === import.meta.url) pruneReleaseAssets();
