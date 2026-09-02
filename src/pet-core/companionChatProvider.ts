import { invoke } from "@tauri-apps/api/core";
import {
  createLocalCompanionChatFallbackProvider,
  createLocalCompanionChatProvider,
  type CompanionChatProvider,
  type CompanionChatProviderInfo,
  type CompanionChatProviderInput,
  type CompanionChatProviderReply,
} from "./companionChatRuntime";
import type { CompanionChatConfig } from "./companionChat";
import {
  CompanionModelCodecError,
  encodeCompanionModelRequest,
} from "./companionModelCodec";
import {
  ProviderAdapterError,
  DEFAULT_BUNDLED_OLLAMA_TIMEOUT_MS,
  createGeminiNativeProviderAdapter,
  createOpenAiCompatibleProviderAdapter,
  createOllamaLocalProviderAdapter,
  type ProviderAdapter,
} from "./companionProviderAdapter";
import {
  CompanionContextPrivacyError,
  CompanionContextTrustError,
  assembleCompanionContext,
  filterCompanionContextForRemote,
  isTrustedCompanionChatContext,
  type CompanionChatContext,
} from "./companionContext";
import { CompanionContextBudgetError } from "./companionContextBudget";
import {
  containsSensitiveCompanionText,
  REMOTE_SENSITIVE_INPUT_REPLY,
} from "./companionPrivacy";
import {
  DEFAULT_COMPANION_PROVIDER_SETTINGS,
  getCompanionProviderStatusInfo,
  isSupportedCompanionProviderProtocol,
  normalizeCompanionProviderEndpoint,
  normalizeCompanionProviderSettings,
  validateCompanionProviderProfile,
  type CompanionProviderProfile,
  type CompanionProviderProtocol,
  type SupportedCompanionProviderProtocol,
} from "./companionProviderConfig";

export {
  DEFAULT_GEMINI_COMPANION_API_BASE_URL,
  DEFAULT_GEMINI_COMPANION_MODEL,
  DEFAULT_OPENAI_COMPATIBLE_API_BASE_URL,
  DEFAULT_OPENAI_COMPATIBLE_MODEL,
  normalizeCompanionProviderEndpoint,
} from "./companionProviderConfig";

const DEFAULT_MAX_REPLY_LENGTH = 36;
export const DEFAULT_COMPANION_PROVIDER_TIMEOUT_MS = 15_000;

export type CompanionChatHttpResponse = {
  ok: boolean;
  status: number;
  json: () => Promise<unknown>;
};

export type CompanionChatHttpRequestInit = {
  method: "POST";
  headers: Record<string, string>;
  body: string;
  signal?: AbortSignal;
};

export type CompanionChatHttpFetcher = (
  url: string,
  init: CompanionChatHttpRequestInit,
) => Promise<CompanionChatHttpResponse>;

type NativeCompanionProviderChatResponse = {
  status: number;
  payload: unknown;
};

export type CompanionChatProviderErrorKind =
  | "configuration"
  | "unsupported"
  | "authentication"
  | "rate-limit"
  | "timeout"
  | "cancelled"
  | "network"
  | "server"
  | "malformed-response"
  | "content-safety"
  | "remote";

export class CompanionChatProviderError extends Error {
  readonly status: number | undefined;
  readonly kind: CompanionChatProviderErrorKind;
  readonly userMessage: string;

  constructor(
    userMessage: string,
    kind: CompanionChatProviderErrorKind = "remote",
    status?: number,
  ) {
    super(userMessage);
    this.name = "CompanionChatProviderError";
    this.status = status;
    this.kind = kind;
    this.userMessage = userMessage;
  }
}

const defaultFetcher: CompanionChatHttpFetcher = (url, init) =>
  fetch(url, init).then((response) => ({
    ok: response.ok,
    status: response.status,
    json: () => response.json() as Promise<unknown>,
  }));

function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function createNativeFetcher(
  protocol: Exclude<SupportedCompanionProviderProtocol, "local">,
  credential: string,
): CompanionChatHttpFetcher {
  return async (url, init) => {
    if (init.signal?.aborted) throw new Error("aborted");
    const pending = protocol === "ollama-local"
      ? invoke<NativeCompanionProviderChatResponse>(
          "fetch_bundled_ollama_chat",
          { body: init.body },
        )
      : invoke<NativeCompanionProviderChatResponse>(
          "fetch_companion_provider_chat",
          {
            protocol,
            url,
            credential,
            body: init.body,
          },
        );
    let onAbort: (() => void) | null = null;
    const response = init.signal
      ? await new Promise<NativeCompanionProviderChatResponse>((resolve, reject) => {
          onAbort = () => reject(new Error("aborted"));
          init.signal?.addEventListener("abort", onAbort, { once: true });
          void pending.then(resolve, reject);
        }).finally(() => {
          if (init.signal && onAbort) init.signal.removeEventListener("abort", onAbort);
        })
      : await pending;
    return {
      ok: response.status >= 200 && response.status < 300,
      status: response.status,
      json: async () => response.payload,
    };
  };
}

export type CompanionChatAdapterFactoryOptions = {
  profile: CompanionProviderProfile;
  credential: string;
  config: CompanionChatConfig;
  fetcher: CompanionChatHttpFetcher;
  timeoutMs: number;
  random?: () => number;
};

export type CompanionChatAdapter = {
  protocol: SupportedCompanionProviderProtocol;
  create: (options: CompanionChatAdapterFactoryOptions) => CompanionChatProvider;
};

export type CompanionChatProviderOptions = {
  profile?: CompanionProviderProfile;
  /** Ephemeral credential read from the secure store; never persisted here. */
  credential?: string | null;
  fetcher?: CompanionChatHttpFetcher;
  random?: () => number;
  timeoutMs?: number;
};

function clampReply(text: string, maxLength: number): string {
  const normalized = text.replace(/```[\s\S]*?```/g, "").replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${Array.from(normalized).slice(0, Math.max(1, maxLength - 1)).join("")}…`;
}

function buildRemoteContext(
  input: CompanionChatProviderInput,
  config: CompanionChatConfig,
): CompanionChatContext {
  try {
    let context: CompanionChatContext;
    if (input.context !== undefined) {
      // A caller-provided object is never trusted merely because its
      // userInput happens to match the current text. Only the ContextBuilder
      // runtime marker (and its frozen output) grants remote-send authority.
      if (!isTrustedCompanionChatContext(input.context)) {
        throw new CompanionContextTrustError();
      }
      if (input.context.userInput !== input.text) {
        throw new CompanionContextTrustError();
      }
      if (input.petId !== undefined && input.context.petId !== input.petId) {
        throw new CompanionContextTrustError();
      }
      if (
        input.contextEpoch !== undefined
        && input.context.contextEpoch !== input.contextEpoch
      ) {
        throw new CompanionContextTrustError();
      }
      context = input.context;
    } else {
      context = assembleCompanionContext({
        petId: input.petId ?? "unknown",
        userInput: input.text,
        history: input.history,
        contextEpoch: input.contextEpoch,
        preferences: input.preferences,
        memories: input.memories,
        systemPrompt: config.systemPrompt,
        style: config.style,
      });
    }
    return filterCompanionContextForRemote(context);
  } catch (error) {
    if (error instanceof CompanionContextPrivacyError) {
      throw new CompanionChatProviderError(REMOTE_SENSITIVE_INPUT_REPLY, "content-safety");
    }
    if (error instanceof CompanionContextBudgetError || error instanceof CompanionContextTrustError) {
      throw new CompanionChatProviderError(
        error instanceof CompanionContextTrustError
          ? "远程请求需要由正式 ContextBuilder 构建安全上下文，未发送请求。"
          : "上下文超出安全预算，未发送远程请求。",
        "configuration",
      );
    }
    throw error;
  }
}

function createRemoteInfo(profile: CompanionProviderProfile): CompanionChatProviderInfo {
  return getCompanionProviderStatusInfo({
    ...profile,
    fallbackToLocal: true,
    credentialConfigured: true,
  });
}

function normalizeCompatibilityError(error: unknown): CompanionChatProviderError {
  if (error instanceof CompanionChatProviderError) return error;
  if (error instanceof CompanionModelCodecError) {
    return new CompanionChatProviderError(
      "聊天服务返回了无法识别的回复。",
      "malformed-response",
    );
  }
  if (error instanceof ProviderAdapterError) {
    const messages: Partial<Record<CompanionChatProviderErrorKind, string>> = {
      configuration: "聊天服务配置无效，未发送远程请求。",
      unsupported: "当前 Provider 协议或能力不受支持。",
      authentication: "聊天服务的凭据无效或没有权限，请检查 Provider 设置。",
      "rate-limit": "聊天额度刚刚用完啦，等一会儿再试。",
      timeout: "聊天服务响应超时，稍后再试。",
      cancelled: "这次回复已停止。",
      network: "聊天服务暂时没接上，稍后再试。",
      server: "聊天服务暂时没接上，稍后再试。",
      "malformed-response": "聊天服务返回了无法识别的回复。",
      "content-safety": "这句话我先不接着展开，我们换个轻松的话题吧。",
      remote: "我刚才没听清，再说一次好吗？",
    };
    return new CompanionChatProviderError(
      messages[error.kind] ?? "聊天服务暂时没接上，稍后再试。",
      error.kind,
      error.status,
    );
  }
  return new CompanionChatProviderError(
    "聊天服务暂时没接上，稍后再试。",
    "network",
  );
}

function createRemoteCompatibilityProvider(
  options: CompanionChatAdapterFactoryOptions,
  adapter: ProviderAdapter,
  info: CompanionChatProviderInfo,
): CompanionChatProvider {
  return {
    info,
    async send(input): Promise<CompanionChatProviderReply> {
      if (input.signal?.aborted) {
        throw new CompanionChatProviderError("这次回复已停止。", "cancelled");
      }
      if (containsSensitiveCompanionText(input.text)) {
        return { text: REMOTE_SENSITIVE_INPUT_REPLY };
      }

      try {
        const context = buildRemoteContext(input, options.config);
        const request = encodeCompanionModelRequest(context, adapter.capabilities, {
          timeoutMs: options.timeoutMs,
          temperature: 0.8,
          maxOutputTokens: Math.min(
            256,
            Math.max(48, (options.config.style?.maxReplyLength ?? DEFAULT_MAX_REPLY_LENGTH) * 2),
          ),
        });
        const response = await adapter.generate({
          ...request,
          signal: input.signal,
        });
        if (!response.text) {
          throw new CompanionChatProviderError(
            "聊天服务返回了无法识别的回复。",
            "malformed-response",
          );
        }
        if (containsSensitiveCompanionText(response.text)) {
          return { text: REMOTE_SENSITIVE_INPUT_REPLY };
        }
        return {
          text: clampReply(
            response.text,
            options.config.style?.maxReplyLength ?? DEFAULT_MAX_REPLY_LENGTH,
          ),
        };
      } catch (error) {
        throw normalizeCompatibilityError(error);
      }
    },
  };
}

function createGeminiNativeAdapter(
  options: CompanionChatAdapterFactoryOptions,
): CompanionChatProvider {
  const endpoint = normalizeCompanionProviderEndpoint(
    "gemini-native",
    options.profile.endpoint,
  );
  const info = createRemoteInfo(options.profile);
  const adapter = createGeminiNativeProviderAdapter({
    id: options.profile.id,
    providerLabel: options.profile.displayName,
    endpoint,
    model: options.profile.model,
    credential: options.credential,
    fetcher: options.fetcher,
    timeoutMs: options.timeoutMs,
  });
  return createRemoteCompatibilityProvider(options, adapter, info);
}

function createOpenAiCompatibleAdapter(
  options: CompanionChatAdapterFactoryOptions,
): CompanionChatProvider {
  const endpoint = normalizeCompanionProviderEndpoint(
    "openai-compatible",
    options.profile.endpoint,
  );
  const info = createRemoteInfo(options.profile);
  const adapter = createOpenAiCompatibleProviderAdapter({
    id: options.profile.id,
    providerLabel: options.profile.displayName,
    endpoint,
    model: options.profile.model,
    credential: options.credential,
    fetcher: options.fetcher,
    timeoutMs: options.timeoutMs,
  });
  return createRemoteCompatibilityProvider(options, adapter, info);
}

function createOllamaLocalAdapter(
  options: CompanionChatAdapterFactoryOptions,
): CompanionChatProvider {
  const endpoint = normalizeCompanionProviderEndpoint(
    "ollama-local",
    options.profile.endpoint,
  );
  const info = getCompanionProviderStatusInfo({
    ...options.profile,
    fallbackToLocal: true,
    credentialConfigured: false,
  });
  const adapter = createOllamaLocalProviderAdapter({
    id: options.profile.id,
    providerLabel: options.profile.displayName,
    endpoint,
    model: options.profile.model,
    fetcher: options.fetcher,
    timeoutMs: options.timeoutMs,
  });
  return createRemoteCompatibilityProvider(options, adapter, info);
}

function createLocalAdapter(
  options: CompanionChatAdapterFactoryOptions,
): CompanionChatProvider {
  return createLocalCompanionChatProvider(options.config, options.random);
}

export const COMPANION_CHAT_ADAPTERS: Readonly<
  Record<SupportedCompanionProviderProtocol, CompanionChatAdapter>
> = {
  local: {
    protocol: "local",
    create: createLocalAdapter,
  },
  "ollama-local": {
    protocol: "ollama-local",
    create: createOllamaLocalAdapter,
  },
  "gemini-native": {
    protocol: "gemini-native",
    create: createGeminiNativeAdapter,
  },
  "openai-compatible": {
    protocol: "openai-compatible",
    create: createOpenAiCompatibleAdapter,
  },
};

export function getCompanionChatAdapter(
  protocol: CompanionProviderProtocol,
): CompanionChatAdapter {
  if (!isSupportedCompanionProviderProtocol(protocol)) {
    throw new CompanionChatProviderError(
      `不支持的聊天协议：${protocol || "未填写"}。`,
      "unsupported",
    );
  }
  return COMPANION_CHAT_ADAPTERS[protocol];
}

export function createCompanionChatProvider(
  config: CompanionChatConfig,
  options: CompanionChatProviderOptions = {},
): CompanionChatProvider {
  const profile = normalizeCompanionProviderSettings(
    options.profile ?? DEFAULT_COMPANION_PROVIDER_SETTINGS,
  );
  const profileError = validateCompanionProviderProfile(profile);
  if (profileError) {
    const kind = profileError.startsWith("不支持的聊天协议") ? "unsupported" : "configuration";
    throw new CompanionChatProviderError(profileError, kind);
  }

  const adapter = getCompanionChatAdapter(profile.protocol);
  if (profile.protocol === "local" || profile.protocol === "ollama-local") {
    const timeoutMs = options.timeoutMs
      ?? (profile.protocol === "ollama-local"
        ? DEFAULT_BUNDLED_OLLAMA_TIMEOUT_MS
        : DEFAULT_COMPANION_PROVIDER_TIMEOUT_MS);
    return adapter.create({
      profile,
      credential: "",
      config,
      fetcher: options.fetcher
        ?? (profile.protocol === "ollama-local" && isTauriRuntime()
          ? createNativeFetcher(profile.protocol, "")
          : defaultFetcher),
      timeoutMs,
      random: options.random,
    });
  }

  const credential = options.credential?.trim();
  if (!credential) {
    throw new CompanionChatProviderError(
      "聊天服务的凭据还没有配置好，请先填写凭据。",
      "configuration",
    );
  }

  try {
    const fetcher = options.fetcher
      ?? (isTauriRuntime()
        ? createNativeFetcher(
            profile.protocol as Exclude<SupportedCompanionProviderProtocol, "local">,
            credential,
          )
        : defaultFetcher);
    return adapter.create({
      profile,
      credential,
      config,
      fetcher,
      timeoutMs: options.timeoutMs ?? DEFAULT_COMPANION_PROVIDER_TIMEOUT_MS,
      random: options.random,
    });
  } catch (error) {
    if (error instanceof CompanionChatProviderError) throw error;
    throw new CompanionChatProviderError(
      error instanceof Error ? error.message : "Provider 配置无效。",
      "configuration",
    );
  }
}

/** Explicit adapter entry point retained for focused protocol tests. */
export function createGeminiNativeCompanionChatProvider(options: {
  profile: CompanionProviderProfile;
  credential: string;
  config: CompanionChatConfig;
  fetcher?: CompanionChatHttpFetcher;
  timeoutMs?: number;
}): CompanionChatProvider {
  return createCompanionChatProvider(options.config, {
    profile: { ...options.profile, protocol: "gemini-native" },
    credential: options.credential,
    fetcher: options.fetcher,
    timeoutMs: options.timeoutMs,
  });
}

/** Compatibility alias for code that referred to the old Gemini factory. */
export const createGeminiCompanionChatProvider = createGeminiNativeCompanionChatProvider;

export { createLocalCompanionChatFallbackProvider };
