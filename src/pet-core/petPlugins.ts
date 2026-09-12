import { convertFileSrc, invoke } from "@tauri-apps/api/core";
import { clearPetPluginBaseUrls, getPetManifestUrl, isSafePetRelativePath, registerPetPluginBaseUrl, type PetManifest } from "./petAssets";
import { resolvePetInteractionManifest } from "./petInteractionManifest";

function validatePackagePaths(value: unknown, key = ""): void {
  if (value && typeof value === "object") {
    for (const [childKey, childValue] of Object.entries(value)) validatePackagePaths(childValue, childKey);
  } else if ((key === "path" || key.endsWith("Path")) && (typeof value !== "string" || !isSafePetRelativePath(value))) {
    throw new Error("Plugin manifest path escapes its package");
  }
}

export async function loadPetPlugins(builtInIds: string[], native: boolean, development: boolean) {
  clearPetPluginBaseUrls();
  const errors: string[] = [];
  const candidates = new Map<string, boolean>();
  if (native) {
    try {
      const catalog = await invoke<{ pets: string[]; errors: string[] }>("list_pet_plugins");
      errors.push(...catalog.errors);
      for (const id of catalog.pets) candidates.set(id, true);
    } catch {
      errors.push("无法读取角色插件，请刷新重试。");
    }
  }
  if (development) {
    try {
      const response = await fetch("/local-pets.json");
      if (response.ok) {
        const catalog = await response.json() as { pets: string[] };
        for (const id of catalog.pets) if (!candidates.has(id)) candidates.set(id, false);
      }
    } catch { /* Local development packages are optional. */ }
  }
  const manifests: PetManifest[] = [];
  for (const [id, external] of candidates) {
    if (!/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(id) || builtInIds.includes(id)) {
      errors.push(`插件 ${id} 的编号无效或与内置角色重复。`);
      continue;
    }
    try {
      if (external) registerPetPluginBaseUrl(id, convertFileSrc(id, "pet-plugin"));
      const response = await fetch(getPetManifestUrl(id));
      if (!response.ok) throw new Error("Manifest unavailable");
      const manifest = await response.json() as PetManifest;
      if (manifest.id !== id || !manifest.displayName || !manifest.interactions) throw new Error("Invalid manifest");
      validatePackagePaths(manifest);
      resolvePetInteractionManifest(manifest);
      manifests.push(manifest);
    } catch {
      errors.push(`插件 ${id} 无法加载，请检查角色包。`);
    }
  }
  return { manifests, errors };
}
