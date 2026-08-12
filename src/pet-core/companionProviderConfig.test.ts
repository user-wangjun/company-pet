import { describe, expect, test } from "vitest";
import {
  COMPANION_PROVIDER_SETTINGS_STORAGE_KEY,
  DEFAULT_COMPANION_PROVIDER_SETTINGS,
  LEGACY_COMPANION_PROVIDER_SETTINGS_STORAGE_KEY,
  clearCompanionProviderCredentialWithSecureStore,
  createMemoryCompanionProviderSecureStore,
  getCompanionProviderProfilePreset,
  getCompanionProviderStatusInfo,
  normalizeCompanionProviderSettings,
  parseCompanionProviderSettings,
  readCompanionProviderSettings,
  readCompanionProviderSettingsStateWithSecureStore,
  validateCompanionProviderProfile,
  validateCompanionProviderSettings,
  writeCompanionProviderSettings,
  writeCompanionProviderSettingsWithSecureStore,
} from "./companionProviderConfig";

function createStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    values,
  };
}

describe("provider-neutral profile configuration", () => {
  test("uses an explicit local profile as the default", () => {
    const storage = createStorage();
    expect(readCompanionProviderSettings(storage)).toEqual(
      DEFAULT_COMPANION_PROVIDER_SETTINGS,
    );
    expect(DEFAULT_COMPANION_PROVIDER_SETTINGS).toMatchObject({
      id: "local",
      displayName: "本地陪伴",
      protocol: "local",
      endpoint: "",
      model: "local",
      credentialRef: null,
    });
  });

  test("keeps profile metadata separate from the ephemeral credential", () => {
    const profile = normalizeCompanionProviderSettings({
      id: "work-model",
      displayName: "工作模型",
      protocol: "openai-compatible",
      endpoint: "https://models.example/v1",
      model: "chat-model",
      credentialRef: "work-model",
      credentialConfigured: true,
    });

    expect(profile).toMatchObject({
      id: "work-model",
      displayName: "工作模型",
      protocol: "openai-compatible",
      endpoint: "https://models.example/v1",
      model: "chat-model",
      credentialRef: "work-model",
      credentialConfigured: true,
    });
    expect(Object.prototype.hasOwnProperty.call(profile, "apiKey")).toBe(false);
  });

  test("reads legacy Google and custom profiles without changing their credential references", () => {
    const google = parseCompanionProviderSettings(JSON.stringify({
      provider: "google-gemini",
      model: "gemini-legacy",
      credentialConfigured: true,
    }));
    const custom = parseCompanionProviderSettings(JSON.stringify({
      provider: "custom-gemini",
      endpoint: "https://legacy.example/v1beta",
      model: "legacy-model",
      credentialConfigured: true,
    }));

    expect(google).toMatchObject({
      id: "google-gemini",
      protocol: "gemini-native",
      credentialRef: "google-gemini",
      credentialConfigured: true,
    });
    expect(custom).toMatchObject({
      id: "custom-gemini",
      displayName: "自定义 Provider",
      protocol: "gemini-native",
      endpoint: "https://legacy.example/v1beta",
      credentialRef: "custom-gemini",
      credentialConfigured: true,
    });
  });

  test("writes only v2 non-secret metadata and leaves the legacy record intact", () => {
    const legacyRaw = JSON.stringify({
      provider: "google-gemini",
      credentialConfigured: true,
    });
    const storage = createStorage({
      [LEGACY_COMPANION_PROVIDER_SETTINGS_STORAGE_KEY]: legacyRaw,
    });
    const secret = "unit-secret";
    const profile = normalizeCompanionProviderSettings({
      ...getCompanionProviderProfilePreset("google-gemini"),
      credentialConfigured: true,
    });

    expect(writeCompanionProviderSettings(profile, storage)).toBe(true);
    const raw = storage.values.get(COMPANION_PROVIDER_SETTINGS_STORAGE_KEY) ?? "";
    expect(raw).not.toContain(secret);
    expect(raw).not.toContain("apiKey");
    expect(JSON.parse(raw)).toMatchObject({
      version: 2,
      id: "google-gemini",
      protocol: "gemini-native",
      credentialRef: "google-gemini",
    });
    expect(storage.values.get(LEGACY_COMPANION_PROVIDER_SETTINGS_STORAGE_KEY)).toBe(legacyRaw);
  });

  test("uses generic secure storage for multiple profile and credential references", async () => {
    const storage = createStorage();
    const secureStore = createMemoryCompanionProviderSecureStore();
    const google = normalizeCompanionProviderSettings({
      ...getCompanionProviderProfilePreset("google-gemini"),
      credentialConfigured: true,
    });
    const custom = normalizeCompanionProviderSettings({
      ...getCompanionProviderProfilePreset("custom-provider"),
      credentialConfigured: true,
    });

    await expect(writeCompanionProviderSettingsWithSecureStore(google, {
      credential: "google-unit-secret",
      storage,
      secureStore,
    })).resolves.toBe(true);
    await expect(writeCompanionProviderSettingsWithSecureStore(custom, {
      credential: "custom-unit-secret",
      storage,
      secureStore,
    })).resolves.toBe(true);

    const state = await readCompanionProviderSettingsStateWithSecureStore(storage, secureStore);
    expect(state.settings.id).toBe("custom-provider");
    expect(state.settings.credentialConfigured).toBe(true);
    expect(state.credential).toBe("custom-unit-secret");
    expect(await secureStore.get("google-gemini", "google-gemini")).toBe("google-unit-secret");
    expect(await secureStore.get("custom-provider", "custom-provider")).toBe("custom-unit-secret");

    await expect(clearCompanionProviderCredentialWithSecureStore(google, storage, secureStore))
      .resolves.toBe(true);
    expect(await secureStore.get("google-gemini", "google-gemini")).toBeNull();
    expect(await secureStore.get("custom-provider", "custom-provider")).toBe("custom-unit-secret");
    expect(JSON.stringify(storage.values)).not.toContain("google-unit-secret");
    expect(JSON.stringify(storage.values)).not.toContain("custom-unit-secret");
  });

  test("migrates old credential accounts by reading the unchanged account name", async () => {
    const storage = createStorage({
      [LEGACY_COMPANION_PROVIDER_SETTINGS_STORAGE_KEY]: JSON.stringify({
        provider: "custom-gemini",
        endpoint: "https://legacy.example/v1beta",
        credentialConfigured: true,
      }),
    });
    const secureStore = createMemoryCompanionProviderSecureStore({
      "custom-gemini": "legacy-unit-secret",
    });

    const state = await readCompanionProviderSettingsStateWithSecureStore(storage, secureStore);
    expect(state.settings).toMatchObject({
      id: "custom-gemini",
      protocol: "gemini-native",
      credentialRef: "custom-gemini",
      credentialConfigured: true,
    });
    expect(state.credential).toBe("legacy-unit-secret");
    expect(storage.values.has(LEGACY_COMPANION_PROVIDER_SETTINGS_STORAGE_KEY)).toBe(true);
  });

  test("rejects invalid ids, refs, protocols, endpoints, and missing remote credentials", () => {
    expect(validateCompanionProviderProfile({
      ...getCompanionProviderProfilePreset("custom-provider")!,
      id: "../secret",
    })).toContain("Profile ID");
    expect(validateCompanionProviderProfile({
      ...getCompanionProviderProfilePreset("custom-provider")!,
      credentialRef: "provider:secret",
    })).toContain("credentialRef");
    expect(validateCompanionProviderProfile({
      ...getCompanionProviderProfilePreset("custom-provider")!,
      protocol: "future-protocol",
    })).toContain("不支持");
    expect(validateCompanionProviderProfile({
      ...getCompanionProviderProfilePreset("custom-provider")!,
      endpoint: "https://models.example/v1?token=hidden",
    })).toContain("查询参数");
    expect(validateCompanionProviderSettings({
      ...DEFAULT_COMPANION_PROVIDER_SETTINGS,
      ...getCompanionProviderProfilePreset("custom-provider")!,
      credentialConfigured: false,
    })).toContain("凭据");
    expect(validateCompanionProviderSettings({
      ...DEFAULT_COMPANION_PROVIDER_SETTINGS,
      ...getCompanionProviderProfilePreset("custom-provider")!,
      credentialConfigured: false,
    }, "unit-secret")).toBeNull();
  });

  test("status disclosure is local or remote without exposing credentials", () => {
    const localInfo = getCompanionProviderStatusInfo(DEFAULT_COMPANION_PROVIDER_SETTINGS);
    const remote = normalizeCompanionProviderSettings({
      ...getCompanionProviderProfilePreset("custom-provider"),
      credentialConfigured: true,
    });
    const remoteInfo = getCompanionProviderStatusInfo(remote);

    expect(localInfo).toMatchObject({ kind: "local", target: "本机" });
    expect(remoteInfo).toMatchObject({
      kind: "remote",
      provider: "自定义 Provider",
      target: "https://api.openai.com/v1",
    });
    expect(JSON.stringify(remoteInfo)).not.toContain("unit-secret");
  });
});
