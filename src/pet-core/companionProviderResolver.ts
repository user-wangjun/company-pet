import { invoke } from "@tauri-apps/api/core";
import {
  createProviderAdapter,
  ProviderAdapterError,
  type ProviderAdapter,
  type ProviderAdapterFactoryOptions,
  type ProviderAdapterErrorKind,
  type ProviderCapabilities,
  type ProviderHttpFetcher,
  type ProviderProtocol,
} from "./companionProviderAdapter";
import {
  isLocalCompanionProviderProtocol,
  normalizeCompanionProviderEndpoint,
  normalizeCompanionProviderSettings,
  validateCompanionProviderProfile,
  type CompanionProviderProfile,
} from "./companionProviderConfig";

type NativeBundledOllamaResponse = {
  status: number;
  payload: unknown;
};

function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function createBundledOllamaFetcher(): ProviderHttpFetcher {
  return async (_url, init) => {
    const response = await invoke<NativeBundledOllamaResponse>(
      "fetch_bundled_ollama_chat",
      { body: init.body },
    );
    return {
      ok: response.status >= 200 && response.status < 300,
      status: response.status,
      json: async () => response.payload,
    };
  };
}

export interface ProviderResolver {
  resolve(): ProviderAdapter;
}

export type CompanionProviderResolverOptions = {
  /** A callback allows the selected profile to be read at Turn start. */
  profile:
    | CompanionProviderProfile
    | (() => CompanionProviderProfile);
  /** Ephemeral credential read from the existing secure boundary. */
  credential?: string | null | (() => string | null);
  fetcher?: ProviderHttpFetcher;
  timeoutMs?: number;
  /** Only explicitly verified generic capabilities are forwarded. */
  verifiedCapabilities?:
    | Partial<ProviderCapabilities>
    | ((profile: CompanionProviderProfile) => Partial<ProviderCapabilities> | undefined);
  localGenerate?: ProviderAdapterFactoryOptions["localGenerate"];
};

function currentProfile(
  value: CompanionProviderResolverOptions["profile"],
): CompanionProviderProfile {
  return typeof value === "function" ? value() : value;
}

function currentCredential(
  value: CompanionProviderResolverOptions["credential"],
): string | null {
  if (typeof value === "function") return value();
  return value ?? null;
}

function resolverError(error: unknown): ProviderAdapterError {
  if (error instanceof ProviderAdapterError) {
    const safeMessages: Partial<Record<ProviderAdapterErrorKind, string>> = {
      configuration: "Provider 配置无效，未发送请求。",
      unsupported: "当前 Provider 协议或能力不受支持。",
      authentication: "Provider 凭据无效或读取失败。",
      cancelled: "Provider 请求已取消。",
      timeout: "Provider 请求超时。",
      network: "Provider 配置读取失败，未发送请求。",
      remote: "Provider 配置读取失败，未发送请求。",
    };
    return new ProviderAdapterError(
      safeMessages[error.kind] ?? "Provider 配置无效，未发送请求。",
      error.kind,
      error.status,
    );
  }
  return new ProviderAdapterError(
    "Provider 配置读取失败，未发送请求。",
    "configuration",
  );
}

function verifiedCapabilities(
  value: CompanionProviderResolverOptions["verifiedCapabilities"],
  profile: CompanionProviderProfile,
): Partial<ProviderCapabilities> | undefined {
  return typeof value === "function" ? value(profile) : value;
}

export function createCompanionProviderResolver(
  options: CompanionProviderResolverOptions,
): ProviderResolver {
  return {
    resolve(): ProviderAdapter {
      try {
        const profile = normalizeCompanionProviderSettings(currentProfile(options.profile));
        const validationError = validateCompanionProviderProfile(profile);
        if (validationError) {
          const kind: ProviderAdapterErrorKind = validationError.startsWith("不支持的聊天协议")
            ? "unsupported"
            : "configuration";
          throw new ProviderAdapterError(validationError, kind);
        }

        const protocol = profile.protocol as ProviderProtocol;
        const endpoint = isLocalCompanionProviderProtocol(protocol)
          ? ""
          : normalizeCompanionProviderEndpoint(protocol, profile.endpoint);
        const credential = currentCredential(options.credential);
        if (!isLocalCompanionProviderProtocol(protocol) && !credential?.trim()) {
          throw new ProviderAdapterError(
            "远程 Provider 凭据未配置。",
            "configuration",
          );
        }
        const fetcher = options.fetcher
          ?? (protocol === "ollama-local" && isTauriRuntime()
            ? createBundledOllamaFetcher()
            : undefined);
        return createProviderAdapter({
          id: profile.id,
          protocol,
          providerLabel: profile.displayName,
          endpoint,
          model: profile.model,
          credential,
          fetcher,
          timeoutMs: options.timeoutMs,
          capabilities: verifiedCapabilities(options.verifiedCapabilities, profile),
          localGenerate: options.localGenerate,
        });
      } catch (error) {
        throw resolverError(error);
      }
    },
  };
}
