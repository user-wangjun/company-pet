/**
 * Domain-neutral provider transport contract.
 *
 * This module deliberately does not import Harness, Companion Context,
 * Memory, Task, Reminder, Soul, or any other desktop-pet domain type. It
 * only maps generic messages and generation options to a protocol.
 */

export type ProviderProtocol =
  | "local"
  | "gemini-native"
  | "openai-compatible";

export type ProviderStructuredOutput =
  | "none"
  | "json_object"
  | "json_schema";

export type ProviderCapabilities = {
  readonly textGeneration: true;
  readonly structuredOutput: ProviderStructuredOutput;
  readonly cancellation: boolean;
  readonly usageMetadata: boolean;
};

export type ProviderMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ProviderOutputFormat =
  | { format: "text" }
  | { format: "json_object" }
  | {
      format: "json_schema";
      name: string;
      schema: unknown;
    };

export type ProviderGenerateRequest = {
  model?: string;
  system?: string;
  messages: readonly ProviderMessage[];
  output: ProviderOutputFormat;
  signal?: AbortSignal;
  timeoutMs: number;
  generation?: {
    temperature?: number;
    maxOutputTokens?: number;
  };
};

export type ProviderUsage = {
  inputTokens?: number;
  outputTokens?: number;
};

export type ProviderGenerateResponse = {
  text?: string;
  structured?: unknown;
  metadata: {
    providerId: string;
    model?: string;
    usage?: ProviderUsage;
  };
};

export type ProviderAdapterInfo = {
  kind: "local" | "remote";
  provider: string;
  target: string;
  disclosure: string;
};

export type ProviderAdapter = {
  readonly id: string;
  readonly protocol: ProviderProtocol;
  readonly capabilities: ProviderCapabilities;
  readonly info: ProviderAdapterInfo;
  generate(request: ProviderGenerateRequest): Promise<ProviderGenerateResponse>;
};

export type ProviderHttpResponse = {
  ok: boolean;
  status: number;
  json: () => Promise<unknown>;
};

export type ProviderHttpRequestInit = {
  method: "POST";
  headers: Record<string, string>;
  body: string;
  signal?: AbortSignal;
};

export type ProviderHttpFetcher = (
  url: string,
  init: ProviderHttpRequestInit,
) => Promise<ProviderHttpResponse>;

export type ProviderAdapterErrorKind =
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

export class ProviderAdapterError extends Error {
  readonly kind: ProviderAdapterErrorKind;
  readonly status: number | undefined;
  readonly userMessage: string;

  constructor(
    userMessage: string,
    kind: ProviderAdapterErrorKind = "remote",
    status?: number,
  ) {
    super(userMessage);
    this.name = "ProviderAdapterError";
    this.kind = kind;
    this.status = status;
    this.userMessage = userMessage;
  }
}

export type ProviderAdapterFactoryOptions = {
  id: string;
  protocol: ProviderProtocol;
  providerLabel?: string;
  endpoint?: string;
  model?: string;
  /** Ephemeral credential. It is captured only by the protocol adapter. */
  credential?: string | null;
  fetcher?: ProviderHttpFetcher;
  timeoutMs?: number;
  /** Capabilities must be explicitly verified by the caller. */
  capabilities?: Partial<ProviderCapabilities>;
  localGenerate?: (
    request: ProviderGenerateRequest,
  ) => string | Promise<string>;
};

const DEFAULT_GENERATION = Object.freeze({
  temperature: 0.8,
  maxOutputTokens: 256,
});

const defaultFetcher: ProviderHttpFetcher = (url, init) =>
  fetch(url, init).then((response) => ({
    ok: response.ok,
    status: response.status,
    json: () => response.json() as Promise<unknown>,
  }));

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number"
    && Number.isFinite(value)
    && value >= 0
    && Number.isInteger(value);
}

function normalizeCapabilities(
  protocol: ProviderProtocol,
  requested: Partial<ProviderCapabilities> | undefined,
): ProviderCapabilities {
  // Local never pretends to provide structured model output, even if a
  // caller accidentally supplies a remote capability override.
  if (protocol === "local") {
    return Object.freeze({
      textGeneration: true,
      structuredOutput: "none",
      cancellation: true,
      usageMetadata: false,
    });
  }
  const structuredOutput = requested?.structuredOutput ?? "none";
  if (
    structuredOutput !== "none"
    && structuredOutput !== "json_object"
    && structuredOutput !== "json_schema"
  ) {
    throw new ProviderAdapterError(
      "Provider structured output capability 无效。",
      "configuration",
    );
  }
  return Object.freeze({
    textGeneration: true,
    structuredOutput,
    cancellation: requested?.cancellation === true,
    usageMetadata: requested?.usageMetadata === true,
  });
}

function providerInfo(
  options: ProviderAdapterFactoryOptions,
  kind: "local" | "remote",
): ProviderAdapterInfo {
  const provider = options.providerLabel?.trim() || options.id;
  if (kind === "local") {
    return {
      kind,
      provider,
      target: "本机",
      disclosure: "本地模式：不会发起网络请求。",
    };
  }
  return {
    kind,
    provider,
    target: options.endpoint?.trim() || "已配置 Endpoint",
    disclosure: "远程模式：本轮必要上下文会发送到当前配置的 Provider。",
  };
}

function assertRequest(
  request: ProviderGenerateRequest,
  capabilities: ProviderCapabilities,
): void {
  if (!Array.isArray(request.messages)) {
    throw new ProviderAdapterError(
      "Provider 请求消息格式无效。",
      "configuration",
    );
  }
  if (!Number.isFinite(request.timeoutMs) || request.timeoutMs <= 0) {
    throw new ProviderAdapterError(
      "Provider 请求超时配置无效。",
      "configuration",
    );
  }
  if (request.output.format === "json_object") {
    if (
      capabilities.structuredOutput !== "json_object"
      && capabilities.structuredOutput !== "json_schema"
    ) {
      throw new ProviderAdapterError(
        "当前 Provider 未验证 JSON structured output，已拒绝请求。",
        "unsupported",
      );
    }
  }
  if (
    request.output.format === "json_schema"
    && capabilities.structuredOutput !== "json_schema"
  ) {
    throw new ProviderAdapterError(
      "当前 Provider 未验证 JSON Schema structured output，已拒绝请求。",
      "unsupported",
    );
  }
}

function providerMetadata(
  id: string,
  model: string | undefined,
  usage: ProviderUsage | undefined,
): ProviderGenerateResponse["metadata"] {
  return {
    providerId: id,
    ...(model ? { model } : {}),
    ...(usage && Object.keys(usage).length > 0 ? { usage } : {}),
  };
}

function parseUsage(
  value: unknown,
  inputKey: string,
  outputKey: string,
): ProviderUsage | undefined {
  if (!isRecord(value)) return undefined;
  const input = isFiniteNonNegativeInteger(value[inputKey])
    ? value[inputKey]
    : undefined;
  const output = isFiniteNonNegativeInteger(value[outputKey])
    ? value[outputKey]
    : undefined;
  if (input === undefined && output === undefined) return undefined;
  return {
    ...(input === undefined ? {} : { inputTokens: input }),
    ...(output === undefined ? {} : { outputTokens: output }),
  };
}

function readErrorDetail(value: unknown): string | null {
  if (!isRecord(value)) return null;
  if (typeof value.error === "string") return value.error;
  if (isRecord(value.error) && typeof value.error.message === "string") {
    return value.error.message;
  }
  return null;
}

function classifyHttpError(status: number, detail: string | null): {
  kind: ProviderAdapterErrorKind;
  message: string;
} {
  if (status === 401 || status === 403) {
    return {
      kind: "authentication",
      message: "Provider 凭据无效或没有权限。",
    };
  }
  if (status === 429) {
    return {
      kind: "rate-limit",
      message: "Provider 请求频率或额度受限。",
    };
  }
  if (status === 408 || status === 504) {
    return {
      kind: "timeout",
      message: "Provider 响应超时。",
    };
  }
  if (status >= 500) {
    return {
      kind: "server",
      message: "Provider 暂时不可用。",
    };
  }
  if (detail?.toLowerCase().includes("safety")) {
    return {
      kind: "content-safety",
      message: "Provider 拒绝了这次内容请求。",
    };
  }
  return {
    kind: "remote",
    message: "Provider 返回了未识别的错误。",
  };
}

function cancelledError(): ProviderAdapterError {
  return new ProviderAdapterError("Provider 请求已取消。", "cancelled");
}

function timeoutError(): ProviderAdapterError {
  return new ProviderAdapterError("Provider 请求超时。", "timeout");
}

type ProviderJsonResult = {
  response: ProviderHttpResponse;
  payload: unknown;
};

/**
 * Own the complete transport lifecycle, including response body consumption.
 * The controller is not aborted when headers arrive; it is cleaned up only
 * after json() settles or the lifecycle is cancelled/timed out.
 */
async function fetchJsonWithTimeout(
  fetcher: ProviderHttpFetcher,
  url: string,
  init: Omit<ProviderHttpRequestInit, "signal">,
  parentSignal: AbortSignal | undefined,
  timeoutMs: number,
): Promise<ProviderJsonResult> {
  const controller = new AbortController();
  let timeoutHandle: ReturnType<typeof setTimeout> | null = null;
  let onParentAbort: (() => void) | null = null;
  let timedOut = false;
  let settled = false;

  const abortPromise = new Promise<never>((_, reject) => {
    onParentAbort = () => {
      if (settled) return;
      controller.abort();
      reject(cancelledError());
    };
    if (parentSignal?.aborted) {
      onParentAbort();
      return;
    }
    parentSignal?.addEventListener("abort", onParentAbort, { once: true });
    timeoutHandle = setTimeout(() => {
      if (settled) return;
      timedOut = true;
      controller.abort();
      reject(timeoutError());
    }, Math.max(1, timeoutMs));
  });

  const consume = (async (): Promise<ProviderJsonResult> => {
    if (parentSignal?.aborted) throw cancelledError();

    let response: ProviderHttpResponse;
    try {
      response = await fetcher(url, { ...init, signal: controller.signal });
    } catch {
      if (parentSignal?.aborted) throw cancelledError();
      if (timedOut) throw timeoutError();
      throw new ProviderAdapterError("Provider 网络请求失败。", "network");
    }

    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      if (parentSignal?.aborted) throw cancelledError();
      if (timedOut) throw timeoutError();
      // Error responses still need their HTTP status classification even when
      // the body is not valid JSON. Successful responses do not.
      if (response.ok) {
        throw new ProviderAdapterError(
          "Provider 返回了无法识别的响应。",
          "malformed-response",
          response.status,
        );
      }
      payload = null;
    }

    return { response, payload };
  })();

  try {
    return await Promise.race([consume, abortPromise]);
  } catch (error) {
    if (error instanceof ProviderAdapterError) throw error;
    if (parentSignal?.aborted) throw cancelledError();
    if (timedOut) throw timeoutError();
    throw new ProviderAdapterError("Provider 网络请求失败。", "network");
  } finally {
    settled = true;
    if (timeoutHandle !== null) clearTimeout(timeoutHandle);
    if (parentSignal && onParentAbort) {
      parentSignal.removeEventListener("abort", onParentAbort);
    }
    controller.abort();
  }
}

function extractGeminiText(value: unknown): string | null {
  if (!isRecord(value) || !Array.isArray(value.candidates)) return null;
  for (const candidate of value.candidates) {
    if (!isRecord(candidate) || !isRecord(candidate.content)) continue;
    if (!Array.isArray(candidate.content.parts)) continue;
    const text = candidate.content.parts
      .filter(
        (part): part is Record<string, unknown> =>
          isRecord(part) && typeof part.text === "string",
      )
      .map((part) => (part.text as string).trim())
      .filter(Boolean)
      .join(" ");
    if (text) return text;
  }
  return null;
}

function extractOpenAiText(value: unknown): string | null {
  if (!isRecord(value) || !Array.isArray(value.choices)) return null;
  for (const choice of value.choices) {
    if (!isRecord(choice) || !isRecord(choice.message)) continue;
    if (typeof choice.message.content === "string" && choice.message.content.trim()) {
      return choice.message.content.trim();
    }
    if (!Array.isArray(choice.message.content)) continue;
    const text = choice.message.content
      .filter(
        (part): part is Record<string, unknown> =>
          isRecord(part) && typeof part.text === "string",
      )
      .map((part) => (part.text as string).trim())
      .filter(Boolean)
      .join(" ");
    if (text) return text;
  }
  return null;
}

function parseJsonText(value: string): unknown | undefined {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return undefined;
  }
}

function mapGeneration(request: ProviderGenerateRequest): Record<string, unknown> {
  const generation = request.generation ?? DEFAULT_GENERATION;
  return {
    ...(generation.temperature === undefined ? {} : { temperature: generation.temperature }),
    ...(generation.maxOutputTokens === undefined
      ? {}
      : { maxOutputTokens: generation.maxOutputTokens }),
  };
}

function buildGeminiBody(request: ProviderGenerateRequest): Record<string, unknown> {
  const generationConfig: Record<string, unknown> = mapGeneration(request);
  if (request.output.format === "json_object" || request.output.format === "json_schema") {
    generationConfig.responseMimeType = "application/json";
  }
  if (request.output.format === "json_schema") {
    generationConfig.responseSchema = request.output.schema;
  }
  return {
    ...(request.system
      ? { system_instruction: { parts: [{ text: request.system }] } }
      : {}),
    contents: request.messages.map((message) => ({
      role: message.role === "assistant" ? "model" : "user",
      parts: [{ text: message.content }],
    })),
    generationConfig,
  };
}

function buildOpenAiBody(request: ProviderGenerateRequest): Record<string, unknown> {
  const messages = [
    ...(request.system
      ? [{ role: "system", content: request.system }]
      : []),
    ...request.messages.map((message) => ({
      role: message.role,
      content: message.content,
    })),
  ];
  const body: Record<string, unknown> = {
    ...(request.model ? { model: request.model } : {}),
    messages,
    ...(request.generation?.temperature === undefined
      ? {}
      : { temperature: request.generation.temperature }),
    ...(request.generation?.maxOutputTokens === undefined
      ? {}
      : { max_tokens: request.generation.maxOutputTokens }),
  };
  if (request.output.format === "json_object") {
    body.response_format = { type: "json_object" };
  } else if (request.output.format === "json_schema") {
    body.response_format = {
      type: "json_schema",
      json_schema: {
        name: request.output.name,
        schema: request.output.schema,
        strict: true,
      },
    };
  }
  return body;
}

function assertRemoteConfiguration(options: ProviderAdapterFactoryOptions): {
  endpoint: string;
  model: string;
  credential: string;
} {
  const endpoint = options.endpoint?.trim() ?? "";
  const model = options.model?.trim() ?? "";
  const credential = options.credential?.trim() ?? "";
  if (!endpoint || !model || !credential) {
    throw new ProviderAdapterError(
      "远程 Provider 配置不完整。",
      "configuration",
    );
  }
  return { endpoint: endpoint.replace(/\/+$/u, ""), model, credential };
}

function createRemoteAdapter(
  options: ProviderAdapterFactoryOptions,
  buildBody: (request: ProviderGenerateRequest) => Record<string, unknown>,
  extractText: (value: unknown) => string | null,
): ProviderAdapter {
  const { endpoint, model, credential } = assertRemoteConfiguration(options);
  const capabilities = normalizeCapabilities(options.protocol, options.capabilities);
  const fetcher = options.fetcher ?? defaultFetcher;
  const requestUrl = options.protocol === "gemini-native"
    ? `${endpoint}/models/${encodeURIComponent(model)}:generateContent`
    : `${endpoint}/chat/completions`;

  return {
    id: options.id,
    protocol: options.protocol,
    capabilities,
    info: providerInfo({ ...options, endpoint }, "remote"),
    async generate(request) {
      assertRequest(request, capabilities);
      if (request.signal?.aborted) throw cancelledError();
      const selectedModel = request.model?.trim() || model;
      const { response, payload } = await fetchJsonWithTimeout(
        fetcher,
        requestUrl,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(options.protocol === "gemini-native"
              ? { "x-goog-api-key": credential }
              : { Authorization: `Bearer ${credential}` }),
          },
          body: JSON.stringify(buildBody({ ...request, model: selectedModel })),
        },
        request.signal,
        request.timeoutMs,
      );
      if (!response.ok) {
        const classified = classifyHttpError(response.status, readErrorDetail(payload));
        throw new ProviderAdapterError(classified.message, classified.kind, response.status);
      }

      const text = extractText(payload);
      if (!text) {
        throw new ProviderAdapterError(
          "Provider 返回了无法识别的响应。",
          "malformed-response",
          response.status,
        );
      }
      const structured = request.output.format === "text"
        ? undefined
        : parseJsonText(text);
      const usage = capabilities.usageMetadata
        ? parseUsage(
            isRecord(payload) ? payload.usageMetadata ?? payload.usage : undefined,
            options.protocol === "gemini-native" ? "promptTokenCount" : "prompt_tokens",
            options.protocol === "gemini-native" ? "candidatesTokenCount" : "completion_tokens",
          )
        : undefined;
      return {
        ...(text ? { text } : {}),
        ...(structured === undefined ? {} : { structured }),
        metadata: providerMetadata(options.id, selectedModel, usage),
      };
    },
  };
}

export function createLocalProviderAdapter(
  options: Omit<ProviderAdapterFactoryOptions, "protocol"> & {
    protocol?: ProviderProtocol;
  } = { id: "local" },
): ProviderAdapter {
  const capabilities = normalizeCapabilities("local", options.capabilities);
  const localGenerate = options.localGenerate
    ?? (() => "嗯，我听着。");
  return {
    id: options.id,
    protocol: "local",
    capabilities,
    info: providerInfo({ ...options, protocol: "local" }, "local"),
    async generate(request) {
      assertRequest(request, capabilities);
      if (request.signal?.aborted) throw cancelledError();
      try {
        const text = await localGenerate(request);
        if (!text.trim()) {
          throw new ProviderAdapterError(
            "Local Provider 返回了空响应。",
            "malformed-response",
          );
        }
        return {
          text,
          metadata: providerMetadata(options.id, request.model, undefined),
        };
      } catch (error) {
        if (error instanceof ProviderAdapterError) throw error;
        throw new ProviderAdapterError("Local Provider 生成失败。", "remote");
      }
    },
  };
}

export function createGeminiNativeProviderAdapter(
  options: Omit<ProviderAdapterFactoryOptions, "protocol">,
): ProviderAdapter {
  return createRemoteAdapter(
    { ...options, protocol: "gemini-native" },
    buildGeminiBody,
    extractGeminiText,
  );
}

export function createOpenAiCompatibleProviderAdapter(
  options: Omit<ProviderAdapterFactoryOptions, "protocol">,
): ProviderAdapter {
  return createRemoteAdapter(
    { ...options, protocol: "openai-compatible" },
    buildOpenAiBody,
    extractOpenAiText,
  );
}

export function createProviderAdapter(
  options: ProviderAdapterFactoryOptions,
): ProviderAdapter {
  if (options.protocol === "local") return createLocalProviderAdapter(options);
  if (options.protocol === "gemini-native") {
    return createGeminiNativeProviderAdapter(options);
  }
  if (options.protocol === "openai-compatible") {
    return createOpenAiCompatibleProviderAdapter(options);
  }
  throw new ProviderAdapterError(
    "未知 Provider 协议，已拒绝自动切换。",
    "unsupported",
  );
}
