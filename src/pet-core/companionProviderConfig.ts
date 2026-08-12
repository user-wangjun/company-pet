import { invoke } from "@tauri-apps/api/core";
import {
  LOCAL_COMPANION_CHAT_PROVIDER_INFO,
  type CompanionChatProviderInfo,
} from "./companionChatRuntime";

export const COMPANION_PROVIDER_SETTINGS_STORAGE_KEY =
  "yuxin-companion-provider-settings-v2";
export const LEGACY_COMPANION_PROVIDER_SETTINGS_STORAGE_KEY =
  "yuxin-companion-provider-settings-v1";

export const DEFAULT_GEMINI_COMPANION_MODEL = "gemini-2.5-flash";
export const DEFAULT_OPENAI_COMPATIBLE_MODEL = "gpt-4o-mini";
export const DEFAULT_GEMINI_COMPANION_API_BASE_URL =
  "https://generativelanguage.googleapis.com/v1beta";
export const DEFAULT_OPENAI_COMPATIBLE_API_BASE_URL = "https://api.openai.com/v1";

export const REMOTE_COMPANION_CHAT_DISCLOSURE =
  "远程模式：本轮必要上下文会发送到远程 AI 服务。本应用不会主动保存完整原始聊天记录；服务商的数据保留、训练和区域政策不由本应用保证，请以服务商当前条款为准。";

export const COMPANION_PROVIDER_PROTOCOLS = [
  "local",
  "gemini-native",
  "openai-compatible",
] as const;

export type SupportedCompanionProviderProtocol =
  (typeof COMPANION_PROVIDER_PROTOCOLS)[number];

/**
 * Protocol is deliberately open-ended at the profile boundary. Unknown
 * values are retained so they fail visibly during validation instead of
 * silently becoming a different remote service.
 */
export type CompanionProviderProtocol = SupportedCompanionProviderProtocol | string;

/** Stable profile ids are user/configuration data, not a vendor enum. */
export type CompanionProviderProfileId = string;
/** Kept as a compatibility alias for callers that used the old name. */
export type CompanionProviderId = CompanionProviderProfileId;
export type CompanionProviderCredentialRef = string;

export type CompanionProviderProfile = {
  id: CompanionProviderProfileId;
  displayName: string;
  protocol: CompanionProviderProtocol;
  endpoint: string;
  model: string;
  credentialRef: CompanionProviderCredentialRef | null;
};

export type CompanionProviderSettings = CompanionProviderProfile & {
  fallbackToLocal: boolean;
  /** Metadata only. The secret itself is kept outside this object. */
  credentialConfigured: boolean;
};

export type CompanionProviderSettingsStorage = Pick<
  Storage,
  "getItem" | "setItem"
>;

export type CompanionProviderSecureStore = {
  get: (
    profileId: CompanionProviderProfileId,
    credentialRef: CompanionProviderCredentialRef,
  ) => Promise<string | null>;
  set: (
    profileId: CompanionProviderProfileId,
    credentialRef: CompanionProviderCredentialRef,
    secret: string,
  ) => Promise<void>;
  clear: (
    profileId: CompanionProviderProfileId,
    credentialRef: CompanionProviderCredentialRef,
  ) => Promise<void>;
};

export type CompanionProviderActionResult = {
  ok: boolean;
  message: string;
};

export type CompanionProviderHydratedState = {
  settings: CompanionProviderSettings;
  /** Ephemeral runtime secret; never part of settings or persistence. */
  credential: string | null;
};

export const COMPANION_PROVIDER_PROTOCOL_LABELS: Record<string, string> = {
  local: "local（本地）",
  "gemini-native": "gemini-native（原生协议）",
  "openai-compatible": "openai-compatible（兼容协议）",
};

export const COMPANION_PROVIDER_PROTOCOL_DESCRIPTIONS: Record<string, string> = {
  local: "只在本机生成回复，不发起网络请求。",
  "gemini-native": "使用 Gemini 原生 generateContent 协议；Google Gemini 是其中一个预设。",
  "openai-compatible": "使用通用 chat/completions 兼容协议，不代表任何一家供应商。",
};

const PROVIDER_PROFILE_PRESETS: Record<string, CompanionProviderProfile> = {
  local: {
    id: "local",
    displayName: "本地陪伴",
    protocol: "local",
    endpoint: "",
    model: "local",
    credentialRef: null,
  },
  "google-gemini": {
    id: "google-gemini",
    displayName: "Google Gemini",
    protocol: "gemini-native",
    endpoint: DEFAULT_GEMINI_COMPANION_API_BASE_URL,
    model: DEFAULT_GEMINI_COMPANION_MODEL,
    credentialRef: "google-gemini",
  },
  "custom-provider": {
    id: "custom-provider",
    displayName: "自定义 Provider",
    protocol: "openai-compatible",
    endpoint: DEFAULT_OPENAI_COMPATIBLE_API_BASE_URL,
    model: DEFAULT_OPENAI_COMPATIBLE_MODEL,
    credentialRef: "custom-provider",
  },
  // Legacy id retained only so old metadata and keyring accounts remain
  // addressable. Its UI label is generic and its protocol can be changed.
  "custom-gemini": {
    id: "custom-gemini",
    displayName: "自定义 Provider",
    protocol: "gemini-native",
    endpoint: "",
    model: DEFAULT_GEMINI_COMPANION_MODEL,
    credentialRef: "custom-gemini",
  },
};

export const COMPANION_PROVIDER_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(PROVIDER_PROFILE_PRESETS).map(([id, profile]) => [id, profile.displayName]),
);

const fallbackSettingsValues = new Map<string, string>();
const defaultSecureStore = createDefaultCompanionProviderSecureStore();

export function getCompanionProviderProfilePreset(
  id: CompanionProviderProfileId,
): CompanionProviderProfile | null {
  const preset = PROVIDER_PROFILE_PRESETS[id];
  return preset ? { ...preset } : null;
}

export function getCompanionProviderProfilePresets(): CompanionProviderProfile[] {
  return Object.values(PROVIDER_PROFILE_PRESETS).map((profile) => ({ ...profile }));
}

export function getDefaultEndpointForProtocol(protocol: CompanionProviderProtocol): string {
  if (protocol === "local") return "";
  if (protocol === "gemini-native") return DEFAULT_GEMINI_COMPANION_API_BASE_URL;
  if (protocol === "openai-compatible") return DEFAULT_OPENAI_COMPATIBLE_API_BASE_URL;
  return "";
}

export function getDefaultModelForProtocol(protocol: CompanionProviderProtocol): string {
  if (protocol === "local") return "local";
  if (protocol === "gemini-native") return DEFAULT_GEMINI_COMPANION_MODEL;
  if (protocol === "openai-compatible") return DEFAULT_OPENAI_COMPATIBLE_MODEL;
  return "";
}

export function getCompanionProviderProtocolLabel(protocol: CompanionProviderProtocol): string {
  return COMPANION_PROVIDER_PROTOCOL_LABELS[protocol]
    ?? (protocol.trim() ? protocol : "未知协议");
}

export function getCompanionProviderProtocolDescription(
  protocol: CompanionProviderProtocol,
): string {
  return COMPANION_PROVIDER_PROTOCOL_DESCRIPTIONS[protocol]
    ?? "当前协议未被支持；保存或连接测试会安全失败。";
}

export function isSupportedCompanionProviderProtocol(
  protocol: CompanionProviderProtocol,
): protocol is SupportedCompanionProviderProtocol {
  return (COMPANION_PROVIDER_PROTOCOLS as readonly string[]).includes(protocol);
}

export function isValidCompanionProviderProfileId(value: unknown): value is string {
  return typeof value === "string"
    && /^[a-z0-9][a-z0-9._-]{0,63}$/.test(value.trim());
}

export function isValidCompanionProviderCredentialRef(value: unknown): value is string {
  return typeof value === "string"
    && /^[a-z0-9][a-z0-9._-]{0,95}$/.test(value.trim());
}

function isLoopbackHostname(hostname: string): boolean {
  const normalized = hostname.toLowerCase().replace(/^\[|\]$/g, "");
  return normalized === "localhost"
    || normalized === "127.0.0.1"
    || normalized === "::1";
}

function normalizeHttpEndpoint(
  endpoint: string | undefined,
  defaultPath: string,
  stripSuffix: string,
): string {
  const candidate = endpoint?.trim();
  if (!candidate) return "";

  let url: URL;
  try {
    url = new URL(candidate);
  } catch {
    throw new Error("聊天服务地址无效。请检查 Endpoint。");
  }

  if (
    (url.protocol !== "https:" && url.protocol !== "http:")
    || url.username
    || url.password
    || url.search
    || url.hash
  ) {
    throw new Error("聊天服务地址无效。Endpoint 不能包含凭据、查询参数或片段。");
  }
  if (url.protocol === "http:" && !isLoopbackHostname(url.hostname)) {
    throw new Error("远程聊天服务必须使用 HTTPS；仅允许本机 loopback 地址使用 HTTP。");
  }

  let pathname = url.pathname.replace(/\/+$/, "");
  if (!pathname) pathname = defaultPath;
  if (pathname.endsWith(stripSuffix)) {
    pathname = pathname.slice(0, -stripSuffix.length).replace(/\/+$/, "") || defaultPath;
  }
  return `${url.origin}${pathname}`;
}

export function normalizeCompanionProviderEndpoint(
  protocol: CompanionProviderProtocol,
  endpoint?: string,
): string {
  if (protocol === "local") return "";
  if (protocol === "gemini-native") {
    return normalizeHttpEndpoint(
      endpoint || DEFAULT_GEMINI_COMPANION_API_BASE_URL,
      "/v1beta",
      "/models",
    );
  }
  if (protocol === "openai-compatible") {
    return normalizeHttpEndpoint(
      endpoint || DEFAULT_OPENAI_COMPATIBLE_API_BASE_URL,
      "/v1",
      "/chat/completions",
    );
  }
  throw new Error(`不支持的聊天协议：${protocol || "未填写"}。`);
}

export function redactCompanionProviderEndpoint(endpoint: string): string {
  if (!endpoint.trim()) return "未配置 Endpoint";
  try {
    const url = new URL(endpoint);
    return `${url.origin}${url.pathname.replace(/\/+$/, "")}`;
  } catch {
    return "已配置 Endpoint";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asTrimmedString(value: unknown): string | undefined {
  return typeof value === "string" ? value.trim() : undefined;
}

function legacyProtocol(provider: string | undefined): CompanionProviderProtocol | undefined {
  if (provider === "local") return "local";
  if (provider === "google-gemini" || provider === "custom-gemini") {
    return "gemini-native";
  }
  return undefined;
}

function defaultProfileForId(id: string): CompanionProviderProfile {
  return getCompanionProviderProfilePreset(id)
    ?? {
      id,
      displayName: id || "Provider",
      protocol: id === "local" ? "local" : "openai-compatible",
      endpoint: getDefaultEndpointForProtocol(id === "local" ? "local" : "openai-compatible"),
      model: getDefaultModelForProtocol(id === "local" ? "local" : "openai-compatible"),
      credentialRef: id === "local" ? null : id || null,
    };
}

export const DEFAULT_COMPANION_PROVIDER_SETTINGS: CompanionProviderSettings = {
  ...defaultProfileForId("local"),
  fallbackToLocal: true,
  credentialConfigured: false,
};

export function normalizeCompanionProviderSettings(
  input: Partial<CompanionProviderSettings> & {
    provider?: unknown;
    apiKey?: unknown;
    apiKeyConfigured?: unknown;
  } | null | undefined,
): CompanionProviderSettings {
  const source = (input ?? {}) as Record<string, unknown>;
  const legacyId = asTrimmedString(source.provider);
  const rawId = asTrimmedString(source.id) ?? legacyId ?? DEFAULT_COMPANION_PROVIDER_SETTINGS.id;
  const id = rawId || DEFAULT_COMPANION_PROVIDER_SETTINGS.id;
  const preset = defaultProfileForId(id);
  const protocol = asTrimmedString(source.protocol)
    ?? legacyProtocol(legacyId)
    ?? preset.protocol;
  const displayName = asTrimmedString(source.displayName) || preset.displayName;
  const endpoint = typeof source.endpoint === "string"
    ? source.endpoint.trim()
    : preset.endpoint || getDefaultEndpointForProtocol(protocol);
  const model = typeof source.model === "string"
    ? source.model.trim()
    : preset.model || getDefaultModelForProtocol(protocol);
  const rawCredentialRef = source.credentialRef;
  const credentialRef = rawCredentialRef === null
    ? null
    : typeof rawCredentialRef === "string"
      ? rawCredentialRef.trim()
      : protocol === "local" || id === "local"
        ? null
        : id;

  return {
    id,
    displayName,
    protocol,
    endpoint,
    model,
    credentialRef,
    fallbackToLocal: source.fallbackToLocal !== false,
    credentialConfigured: source.credentialConfigured === true
      || source.apiKeyConfigured === true,
  };
}

function readStoredSettingsRaw(
  storage: CompanionProviderSettingsStorage | null,
): string | null {
  try {
    return storage?.getItem(COMPANION_PROVIDER_SETTINGS_STORAGE_KEY)
      ?? storage?.getItem(LEGACY_COMPANION_PROVIDER_SETTINGS_STORAGE_KEY)
      ?? fallbackSettingsValues.get(COMPANION_PROVIDER_SETTINGS_STORAGE_KEY)
      ?? fallbackSettingsValues.get(LEGACY_COMPANION_PROVIDER_SETTINGS_STORAGE_KEY)
      ?? null;
  } catch {
    return fallbackSettingsValues.get(COMPANION_PROVIDER_SETTINGS_STORAGE_KEY)
      ?? fallbackSettingsValues.get(LEGACY_COMPANION_PROVIDER_SETTINGS_STORAGE_KEY)
      ?? null;
  }
}

function writeStoredSettingsRaw(
  value: string,
  storage: CompanionProviderSettingsStorage | null,
): boolean {
  try {
    if (storage) {
      storage.setItem(COMPANION_PROVIDER_SETTINGS_STORAGE_KEY, value);
    } else {
      fallbackSettingsValues.set(COMPANION_PROVIDER_SETTINGS_STORAGE_KEY, value);
    }
    return true;
  } catch {
    return false;
  }
}

function parsePersistedSettings(raw: string | null): Record<string, unknown> {
  if (!raw) return {};
  try {
    const parsed: unknown = JSON.parse(raw);
    return isRecord(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

export function parseCompanionProviderSettings(
  raw: string | null,
): CompanionProviderSettings {
  const parsed = parsePersistedSettings(raw);
  const legacyId = asTrimmedString(parsed.provider);
  const isLegacy = !asTrimmedString(parsed.protocol) && Boolean(legacyId);
  const endpoint = typeof parsed.endpoint === "string"
    ? parsed.endpoint
    : isLegacy && legacyId === "custom-gemini"
      ? ""
      : undefined;
  const model = typeof parsed.model === "string" ? parsed.model : undefined;
  return normalizeCompanionProviderSettings({
    id: asTrimmedString(parsed.id) ?? legacyId,
    displayName: asTrimmedString(parsed.displayName),
    protocol: asTrimmedString(parsed.protocol) ?? legacyProtocol(legacyId),
    endpoint,
    model,
    credentialRef: typeof parsed.credentialRef === "string"
      ? parsed.credentialRef
      : undefined,
    fallbackToLocal: parsed.fallbackToLocal === false ? false : true,
    credentialConfigured:
      parsed.credentialConfigured === true || parsed.apiKeyConfigured === true,
  });
}

export function readCompanionProviderSettings(
  storage: CompanionProviderSettingsStorage | null = getDefaultSettingsStorage(),
): CompanionProviderSettings {
  return parseCompanionProviderSettings(readStoredSettingsRaw(storage));
}

function serializeCompanionProviderSettings(
  settings: CompanionProviderSettings,
): string {
  const normalized = normalizeCompanionProviderSettings(settings);
  return JSON.stringify({
    version: 2,
    id: normalized.id,
    displayName: normalized.displayName,
    protocol: normalized.protocol,
    endpoint: normalized.endpoint,
    model: normalized.model,
    credentialRef: normalized.credentialRef,
    fallbackToLocal: normalized.fallbackToLocal,
    credentialConfigured: normalized.credentialConfigured,
  });
}

/** Writes non-secret profile metadata only. */
export function writeCompanionProviderSettings(
  settings: CompanionProviderSettings,
  storage: CompanionProviderSettingsStorage | null = getDefaultSettingsStorage(),
): boolean {
  return writeStoredSettingsRaw(
    serializeCompanionProviderSettings(settings),
    storage,
  );
}

function getDefaultSettingsStorage(): CompanionProviderSettingsStorage | null {
  try {
    if (typeof globalThis !== "undefined" && globalThis.localStorage) {
      return globalThis.localStorage;
    }
  } catch {
    // Browser storage may be unavailable in a preview or privacy-restricted WebView.
  }
  return null;
}

function createDefaultCompanionProviderSecureStore(): CompanionProviderSecureStore {
  const memoryStore = createMemoryCompanionProviderSecureStore();
  return {
    get: (profileId, credentialRef) => isTauriRuntime()
      ? invoke<string | null>("get_companion_provider_credential", {
          profileId,
          credentialRef,
        })
      : memoryStore.get(profileId, credentialRef),
    set: (profileId, credentialRef, secret) => isTauriRuntime()
      ? invoke("set_companion_provider_credential", {
          profileId,
          credentialRef,
          secret,
        })
      : memoryStore.set(profileId, credentialRef, secret),
    clear: (profileId, credentialRef) => isTauriRuntime()
      ? invoke("clear_companion_provider_credential", {
          profileId,
          credentialRef,
        })
      : memoryStore.clear(profileId, credentialRef),
  };
}

function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export function createMemoryCompanionProviderSecureStore(
  initialValues: Record<string, string> = {},
): CompanionProviderSecureStore {
  const values = new Map<string, string>();
  for (const [credentialRef, value] of Object.entries(initialValues)) {
    if (isValidCompanionProviderCredentialRef(credentialRef) && value.trim()) {
      values.set(credentialRef, value.trim());
    }
  }

  return {
    get: async (_profileId, credentialRef) => values.get(credentialRef) ?? null,
    set: async (_profileId, credentialRef, secret) => {
      if (!isValidCompanionProviderCredentialRef(credentialRef)) {
        throw new Error("credentialRef 无效。");
      }
      values.set(credentialRef, secret.trim());
    },
    clear: async (_profileId, credentialRef) => {
      values.delete(credentialRef);
    },
  };
}

export function getDefaultCompanionProviderSecureStore(): CompanionProviderSecureStore {
  return defaultSecureStore;
}

export async function readCompanionProviderCredential(
  settings: CompanionProviderSettings,
  secureStore: CompanionProviderSecureStore = defaultSecureStore,
): Promise<string | null> {
  const normalized = normalizeCompanionProviderSettings(settings);
  if (normalized.protocol === "local" || !normalized.credentialRef) return null;
  if (!isValidCompanionProviderProfileId(normalized.id)
    || !isValidCompanionProviderCredentialRef(normalized.credentialRef)) {
    return null;
  }
  const value = await secureStore.get(normalized.id, normalized.credentialRef);
  return value?.trim() || null;
}

export async function readCompanionProviderSettingsStateWithSecureStore(
  storage: CompanionProviderSettingsStorage | null = getDefaultSettingsStorage(),
  secureStore: CompanionProviderSecureStore = defaultSecureStore,
): Promise<CompanionProviderHydratedState> {
  const settings = readCompanionProviderSettings(storage);
  const credential = await readCompanionProviderCredential(settings, secureStore);
  return {
    settings: {
      ...settings,
      credentialConfigured: Boolean(credential),
    },
    credential,
  };
}

export async function readCompanionProviderSettingsWithSecureStore(
  storage: CompanionProviderSettingsStorage | null = getDefaultSettingsStorage(),
  secureStore: CompanionProviderSecureStore = defaultSecureStore,
): Promise<CompanionProviderSettings> {
  return (await readCompanionProviderSettingsStateWithSecureStore(storage, secureStore)).settings;
}

export type CompanionProviderSecureWriteOptions = {
  /** New secret supplied by the user; omitted means preserve an existing one. */
  credential?: string | null;
  storage?: CompanionProviderSettingsStorage | null;
  secureStore?: CompanionProviderSecureStore;
};

export async function writeCompanionProviderSettingsWithSecureStore(
  settings: CompanionProviderSettings,
  options: CompanionProviderSecureWriteOptions = {},
): Promise<boolean> {
  const storage = options.storage ?? getDefaultSettingsStorage();
  const secureStore = options.secureStore ?? defaultSecureStore;
  const normalized = normalizeCompanionProviderSettings(settings);

  if (validateCompanionProviderProfile(normalized) !== null) {
    return false;
  }

  let credential: string | null = null;
  try {
    if (normalized.protocol !== "local" && normalized.credentialRef) {
      if (options.credential !== undefined) {
        credential = options.credential?.trim() || null;
      } else if (normalized.credentialConfigured) {
        credential = await readCompanionProviderCredential(normalized, secureStore);
      }

      if (credential) {
        await secureStore.set(normalized.id, normalized.credentialRef, credential);
      } else {
        await secureStore.clear(normalized.id, normalized.credentialRef);
      }
    }
  } catch {
    return false;
  }

  return writeStoredSettingsRaw(
    serializeCompanionProviderSettings({
      ...normalized,
      credentialConfigured: Boolean(credential),
    }),
    storage,
  );
}

export async function clearCompanionProviderCredentialWithSecureStore(
  settings: CompanionProviderSettings,
  storage: CompanionProviderSettingsStorage | null = getDefaultSettingsStorage(),
  secureStore: CompanionProviderSecureStore = defaultSecureStore,
): Promise<boolean> {
  const normalized = normalizeCompanionProviderSettings(settings);
  if (normalized.protocol === "local") return true;
  if (!normalized.credentialRef
    || !isValidCompanionProviderProfileId(normalized.id)
    || !isValidCompanionProviderCredentialRef(normalized.credentialRef)) {
    return false;
  }

  try {
    await secureStore.clear(normalized.id, normalized.credentialRef);
  } catch {
    return false;
  }

  return writeStoredSettingsRaw(
    serializeCompanionProviderSettings({
      ...normalized,
      credentialConfigured: false,
    }),
    storage,
  );
}

export function getCompanionProviderLabel(
  id: CompanionProviderProfileId,
  displayName?: string,
): string {
  return displayName?.trim() || COMPANION_PROVIDER_LABELS[id] || id || "Provider";
}

export function getCompanionProviderStatusInfo(
  settings: CompanionProviderSettings,
): CompanionChatProviderInfo {
  const normalized = normalizeCompanionProviderSettings(settings);
  if (normalized.protocol === "local") return LOCAL_COMPANION_CHAT_PROVIDER_INFO;
  return {
    kind: "remote",
    provider: getCompanionProviderLabel(normalized.id, normalized.displayName),
    target: redactCompanionProviderEndpoint(normalized.endpoint),
    disclosure: `${REMOTE_COMPANION_CHAT_DISCLOSURE} 当前协议：${getCompanionProviderProtocolLabel(normalized.protocol)}。`,
  };
}

export function validateCompanionProviderProfile(
  input: CompanionProviderProfile,
): string | null {
  const settings = normalizeCompanionProviderSettings(input);
  if (!isValidCompanionProviderProfileId(settings.id)) {
    return "Provider Profile ID 只能包含小写字母、数字、点、下划线和连字符。";
  }
  if (!settings.displayName.trim()) return "Provider 名称不能为空。";
  if (!settings.protocol.trim()) return "协议不能为空。";
  if (!isSupportedCompanionProviderProtocol(settings.protocol)) {
    return `不支持的聊天协议：${settings.protocol}。`;
  }
  if (settings.protocol === "local") {
    if (settings.credentialRef !== null) return "本地 Provider 不需要 credentialRef。";
    return null;
  }
  if (!isValidCompanionProviderCredentialRef(settings.credentialRef)) {
    return "credentialRef 无效，只能包含小写字母、数字、点、下划线和连字符。";
  }
  if (!settings.model.trim()) return "Model 不能为空。";
  if (settings.model.length > 160 || /[\r\n]/.test(settings.model)) {
    return "Model 格式无效。";
  }
  if (!settings.endpoint.trim()) return "远程 Provider 需要填写 Endpoint。";
  try {
    normalizeCompanionProviderEndpoint(settings.protocol, settings.endpoint);
  } catch (error) {
    return error instanceof Error ? error.message : "Endpoint 无效。";
  }
  return null;
}

export function validateCompanionProviderSettings(
  input: CompanionProviderSettings,
  credential?: string | null,
): string | null {
  const settings = normalizeCompanionProviderSettings(input);
  const profileError = validateCompanionProviderProfile(settings);
  if (profileError) return profileError;
  if (settings.protocol !== "local"
    && !settings.credentialConfigured
    && !credential?.trim()) {
    return "聊天服务的凭据还没有配置好，请先填写凭据。";
  }
  return null;
}
