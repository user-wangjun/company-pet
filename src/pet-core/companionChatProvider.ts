import {
  createLocalCompanionChatProvider,
  type CompanionChatProviderInfo,
  type CompanionChatProvider,
  type CompanionChatProviderReply,
} from "./companionChatRuntime";
import type { CompanionChatConfig } from "./companionChat";
import {
  assembleCompanionContext,
  filterCompanionContextForRemote,
  type CompanionChatContext,
} from "./companionContext";
import {
  containsSensitiveCompanionText,
  REMOTE_SENSITIVE_INPUT_REPLY,
} from "./companionPrivacy";

export const DEFAULT_GEMINI_COMPANION_MODEL = "gemini-2.5-flash";
const DEFAULT_MAX_REPLY_LENGTH = 36;

export type CompanionChatHttpResponse = {
  ok: boolean;
  status: number;
  json: () => Promise<unknown>;
};

export type CompanionChatHttpFetcher = (
  url: string,
  init: {
    method: "POST";
    headers: Record<string, string>;
    body: string;
  },
) => Promise<CompanionChatHttpResponse>;

export const DEFAULT_GEMINI_COMPANION_API_BASE_URL =
  "https://generativelanguage.googleapis.com/v1beta";

export type GoogleGeminiKeySource = "ai-studio" | "google-cloud" | "unknown";

export type GeminiCompanionBackend = "google-gemini" | "custom-gemini";

export type GeminiCompanionConnection = {
  backend: GeminiCompanionBackend;
  apiKey: string;
  endpoint: string;
  model: string;
  keySource: GoogleGeminiKeySource;
};

export type GeminiCompanionChatOptions = {
  apiKey: string;
  config: CompanionChatConfig;
  model?: string;
  endpoint?: string;
  keySource?: GoogleGeminiKeySource;
  fetcher?: CompanionChatHttpFetcher;
};

export type CompanionChatProviderOptions = {
  apiKey?: string | null;
  model?: string;
  endpoint?: string;
  keySource?: GoogleGeminiKeySource;
  fetcher?: CompanionChatHttpFetcher;
  random?: () => number;
};

export class CompanionChatProviderError extends Error {
  readonly status: number | undefined;
  readonly userMessage: string;

  constructor(userMessage: string, status?: number) {
    super(userMessage);
    this.name = "CompanionChatProviderError";
    this.status = status;
    this.userMessage = userMessage;
  }
}

const defaultFetcher: CompanionChatHttpFetcher = (url, init) =>
  fetch(url, init).then((response) => ({
    ok: response.ok,
    status: response.status,
    json: () => response.json() as Promise<unknown>,
  }));

export function normalizeGeminiApiBaseUrl(endpoint?: string): string {
  const candidate = endpoint?.trim() || DEFAULT_GEMINI_COMPANION_API_BASE_URL;

  let url: URL;
  try {
    url = new URL(candidate);
  } catch {
    throw new CompanionChatProviderError("聊天服务地址无效。请检查 API 地址。");
  }

  if (
    (url.protocol !== "https:" && url.protocol !== "http:") ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  ) {
    throw new CompanionChatProviderError("聊天服务地址无效。请检查 API 地址。");
  }

  const hostname = url.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  const isLoopback = hostname === "localhost"
    || hostname === "127.0.0.1"
    || hostname === "::1";
  if (url.protocol === "http:" && !isLoopback) {
    throw new CompanionChatProviderError(
      "自定义聊天服务必须使用 HTTPS；仅允许明确的本机 loopback 地址使用 HTTP。",
    );
  }

  let pathname = url.pathname.replace(/\/+$/, "");
  if (!pathname) pathname = "/v1beta";
  if (pathname.endsWith("/models")) {
    pathname = pathname.slice(0, -"/models".length) || "/v1beta";
  }

  return `${url.origin}${pathname}`;
}

export function isOfficialGoogleGeminiEndpoint(endpoint?: string): boolean {
  try {
    const normalized = normalizeGeminiApiBaseUrl(endpoint);
    const url = new URL(normalized);
    return (
      url.origin === "https://generativelanguage.googleapis.com" &&
      (url.pathname === "/v1" || url.pathname === "/v1beta")
    );
  } catch {
    return false;
  }
}

export function resolveGeminiCompanionConnection({
  apiKey,
  endpoint,
  model = DEFAULT_GEMINI_COMPANION_MODEL,
  keySource = "unknown",
}: {
  apiKey: string;
  endpoint?: string;
  model?: string;
  keySource?: GoogleGeminiKeySource;
}): GeminiCompanionConnection {
  const normalizedKey = apiKey.trim();
  if (!normalizedKey) {
    throw new CompanionChatProviderError("聊天服务的 Key 还没有配置好。");
  }

  const normalizedModel = model.trim() || DEFAULT_GEMINI_COMPANION_MODEL;
  const normalizedEndpoint = normalizeGeminiApiBaseUrl(endpoint);

  return {
    backend: isOfficialGoogleGeminiEndpoint(normalizedEndpoint)
      ? "google-gemini"
      : "custom-gemini",
    apiKey: normalizedKey,
    endpoint: normalizedEndpoint,
    model: normalizedModel,
    keySource,
  };
}

function getRemoteProviderInfo(
  connection: GeminiCompanionConnection,
): CompanionChatProviderInfo {
  const provider =
    connection.backend === "google-gemini"
      ? "Google Gemini"
      : "自定义 Gemini Provider";

  return {
    kind: "remote",
    provider,
    target: connection.endpoint,
    disclosure:
      "远程模式：本轮必要上下文会发送到远程 AI 服务。本应用不会主动保存完整原始聊天记录；服务商的数据保留、训练和区域政策不由本应用保证，请以服务商当前条款为准。",
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readErrorMessage(value: unknown): string | null {
  if (!isRecord(value) || !isRecord(value.error)) return null;
  return typeof value.error.message === "string" ? value.error.message : null;
}

function readGeminiText(value: unknown): string | null {
  if (!isRecord(value) || !Array.isArray(value.candidates)) return null;

  for (const candidate of value.candidates) {
    if (!isRecord(candidate) || !isRecord(candidate.content)) continue;
    const parts = candidate.content.parts;
    if (!Array.isArray(parts)) continue;
    const text = parts
      .filter(
        (part): part is Record<string, unknown> =>
          isRecord(part) && typeof part.text === "string",
      )
      .map((part) => String(part.text).trim())
      .filter(Boolean)
      .join(" ");
    if (text) return text;
  }

  return null;
}

function clampReply(text: string, maxLength: number): string {
  const normalized = text.replace(/```[\s\S]*?```/g, "").replace(/\s+/g, " ").trim();
  if (normalized.length <= maxLength) return normalized;
  return `${Array.from(normalized).slice(0, Math.max(1, maxLength - 1)).join("")}…`;
}

function buildContents(context: CompanionChatContext) {
  return [
    ...context.history.map((message) => ({
      role: message.speaker === "user" ? "user" : "model",
      parts: [{ text: message.text }],
    })),
    {
      role: "user",
      parts: [{ text: context.userInput }],
    },
  ];
}

function getUserFacingError(status: number, detail: string | null): string {
  if (status === 401 || status === 403) {
    return "聊天服务的 Key 还没有配置好。";
  }
  if (status === 429) {
    return "聊天额度刚刚用完啦，等一会儿再试。";
  }
  if (status >= 500) {
    return "聊天服务暂时没接上，稍后再试。";
  }
  if (detail?.toLowerCase().includes("safety")) {
    return "这句话我先不接着展开，我们换个轻松的话题吧。";
  }
  return "我刚才没听清，再说一次好吗？";
}

export function createGeminiCompanionChatProvider({
  apiKey,
  config,
  model = DEFAULT_GEMINI_COMPANION_MODEL,
  endpoint,
  keySource,
  fetcher = defaultFetcher,
}: GeminiCompanionChatOptions): CompanionChatProvider {
  const connection = resolveGeminiCompanionConnection({
    apiKey,
    endpoint,
    model,
    keySource,
  });

  return {
    info: getRemoteProviderInfo(connection),
    async send(input): Promise<CompanionChatProviderReply> {
      if (containsSensitiveCompanionText(input.text)) {
        return {
          text: REMOTE_SENSITIVE_INPUT_REPLY,
        };
      }

      const context =
        input.context?.userInput === input.text
          ? input.context
          : assembleCompanionContext({
              petId: input.petId ?? input.context?.petId ?? "unknown",
              userInput: input.text,
              history: input.history,
              preferences: input.preferences,
              memories: input.memories,
              systemPrompt: config.systemPrompt,
              style: config.style,
            });
      const remoteContext = filterCompanionContextForRemote({
        ...context,
        userInput: input.text,
      });

      let response: CompanionChatHttpResponse;
      try {
        response = await fetcher(
          `${connection.endpoint}/models/${encodeURIComponent(connection.model)}:generateContent`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "x-goog-api-key": connection.apiKey,
            },
            body: JSON.stringify({
              system_instruction: {
                parts: [{ text: remoteContext.systemInstruction }],
              },
              contents: buildContents(remoteContext),
              generationConfig: {
                temperature: 0.8,
                maxOutputTokens: Math.min(
                  256,
                  Math.max(48, (config.style?.maxReplyLength ?? DEFAULT_MAX_REPLY_LENGTH) * 2),
                ),
              },
            }),
          },
        );
      } catch (error) {
        if (error instanceof CompanionChatProviderError) throw error;
        throw new CompanionChatProviderError("聊天服务暂时没接上，稍后再试。");
      }

      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new CompanionChatProviderError(
          getUserFacingError(response.status, readErrorMessage(payload)),
          response.status,
        );
      }

      const reply = readGeminiText(payload);
      if (!reply) {
        throw new CompanionChatProviderError("我刚才没听清，再说一次好吗？");
      }
      if (containsSensitiveCompanionText(reply)) {
        return { text: REMOTE_SENSITIVE_INPUT_REPLY };
      }

      return {
        text: clampReply(
          reply,
          config.style?.maxReplyLength ?? DEFAULT_MAX_REPLY_LENGTH,
        ),
      };
    },
  };
}

export function createCompanionChatProvider(
  config: CompanionChatConfig,
  options: CompanionChatProviderOptions = {},
): CompanionChatProvider {
  if (options.apiKey?.trim()) {
    return createGeminiCompanionChatProvider({
      apiKey: options.apiKey,
      config,
      model: options.model,
      endpoint: options.endpoint,
      keySource: options.keySource,
      fetcher: options.fetcher,
    });
  }

  return createLocalCompanionChatProvider(config, options.random);
}
