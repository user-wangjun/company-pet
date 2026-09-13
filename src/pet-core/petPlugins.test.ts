import { afterEach, expect, test, vi } from "vitest";
import { clearPetPluginBaseUrls, createPetCatalog, getPetManifestUrl, registerPetPluginBaseUrl, resolvePetAssetUrl } from "./petAssets";
import { loadPetPlugins, loadPetManifestsWithPlugins } from "./petPlugins";
import spriteManifest from "../../public/pets/ds/pet.json";
import petIndex from "../../public/pets/index.json";

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

test.each(["native", "development"])("shows all built-in pets in healing before %s plugin discovery finishes", async (mode) => {
  let finishDiscovery!: (value: { pets: string[]; errors: string[] }) => void;
  const discovery = new Promise<{ pets: string[]; errors: string[] }>(resolve => { finishDiscovery = resolve; });
  native.invoke.mockReturnValue(discovery);
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/local-pets.json") return { ok: true, json: () => discovery };
    const parts = url.split("/");
    const id = parts[parts.length - 2];
    return { ok: true, json: async () => ({ ...spriteManifest, id, kind: id === "test-human" ? "human" : undefined }) };
  }));
  const onCatalog = vi.fn();
  let completed = false;
  const loading = loadPetManifestsWithPlugins(petIndex.pets, mode === "native", mode === "development", onCatalog)
    .then(value => { completed = true; return value; });
  await vi.waitFor(() => expect(onCatalog).toHaveBeenCalledTimes(1));
  expect(completed).toBe(false);
  const entries = onCatalog.mock.calls[0][0];
  const builtIns = createPetCatalog(petIndex.pets, Object.fromEntries(entries), petIndex.pets[0]);
  expect(builtIns.filter(pet => pet.kind === "pet").map(pet => pet.id)).toEqual(petIndex.pets);
  finishDiscovery({ pets: ["test-human"], errors: [] });
  const loaded = await loading;
  const catalog = createPetCatalog(loaded.entries.map(([id]) => id), Object.fromEntries(loaded.entries), petIndex.pets[0]);
  expect(catalog.filter(pet => pet.kind === "pet").map(pet => pet.id)).toEqual(petIndex.pets);
  expect(catalog.filter(pet => pet.kind === "human").map(pet => pet.id)).toEqual(["test-human"]);
});
