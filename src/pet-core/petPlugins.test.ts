import { afterEach, expect, test, vi } from "vitest";
import { clearPetPluginBaseUrls, getPetManifestUrl, registerPetPluginBaseUrl, resolvePetAssetUrl } from "./petAssets";
import { loadPetPlugins } from "./petPlugins";
import spriteManifest from "../../public/pets/ds/pet.json";

const native = vi.hoisted(() => ({ invoke: vi.fn(), convertFileSrc: vi.fn((id: string) => `http://pet-plugin.localhost/${id}`) }));
vi.mock("@tauri-apps/api/core", () => native);
afterEach(() => { clearPetPluginBaseUrls(); vi.unstubAllGlobals(); vi.clearAllMocks(); });

test("loads installed roles using plugin URLs, rejects built-in collisions and isolates bad plugins", async () => {
  native.invoke.mockResolvedValue({ pets: ["ds", "test-human", "broken"], errors: [] });
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({
    ok: true, json: async () => url.includes("test-human") ? { ...spriteManifest, id: "test-human", kind: "human" } : { id: "wrong" },
  })));
  const loaded = await loadPetPlugins(["ds"], true, false);
  expect(loaded.manifests.map(pet => pet.id)).toEqual(["test-human"]);
  expect(loaded.errors).toHaveLength(2);
  expect(getPetManifestUrl("ds")).toBe("/pets/ds/pet.json");
  expect(resolvePetAssetUrl("test-human", "preview.png")).toBe("http://pet-plugin.localhost/test-human/preview.png");
});

test("production never discovers private workspace packages and removed plugins lose their URL mapping", async () => {
  registerPetPluginBaseUrl("test-human", "http://pet-plugin.localhost/test-human");
  const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
  expect(await loadPetPlugins(["ds"], false, false)).toEqual({ manifests: [], errors: [] });
  expect(fetcher).not.toHaveBeenCalled();
  expect(getPetManifestUrl("test-human")).toBe("/pets/test-human/pet.json");
});

test("rejects external servers and mismatched package URL roots", () => {
  for (const url of ["https://example.com/test-human", "http://pet-plugin.localhost/other", "http://pet-plugin.localhost/test-human?file=secret"]) {
    expect(() => registerPetPluginBaseUrl("test-human", url)).toThrow();
  }
});
