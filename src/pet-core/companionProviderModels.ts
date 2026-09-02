import { invoke } from "@tauri-apps/api/core";
import {
  ProviderAdapterError,
  type ProviderAdapterErrorKind,
} from "./companionProviderAdapter";
import {
  isLocalCompanionProviderProtocol,
  normalizeCompanionProviderEndpoint,
  normalizeCompanionProviderModelIds,
  type CompanionProviderSettings,
} from "./companionProviderConfig";

export type CompanionProviderModelListHttpResponse = {
  ok: boolean;
  status: number;
  json: () => Promise<unknown>;
};

export type CompanionProviderModelListHttpRequestInit = {
  method: "GET";
  headers: Record<string, string>;
  signal?: AbortSignal;
};

export type CompanionProviderModelListFetcher = (
  url: string,
  init: CompanionProviderModelListHttpRequestInit,
) => Promise<CompanionProviderModelListHttpResponse>;

export type CompanionProviderModelListResult = {
  models: string[];
};

export type CompanionProviderModelsActionResult = {
  ok: boolean;
  message: string;
  models?: string[];
};

const DEFAULT_MODEL_LIST_TIMEOUT_MS = 15_000;

type NativeCompanionProviderModelListResponse = {
  status: number;
  payload: unknown;
};

const browserFetcher: CompanionProviderModelListFetcher = (url, init) =>
  fetch(url, init).then((response) => ({
    ok: response.ok,
    status: response.status,
    json: () => response.json() as Promise<unknown>,
  }));

function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function createNativeFetcher(
  protocol: CompanionProviderSettings["protocol"],
  credential: string,
): CompanionProviderModelListFetcher {
  return async (url) => {
    const response = protocol === "ollama-local"
      ? await invoke<NativeCompanionProviderModelListResponse>(
          "fetch_bundled_ollama_models",
          {},
        )
      : await invoke<NativeCompanionProviderModelListResponse>(
          "fetch_companion_provider_models",
          { protocol, url, credential },
        );
    return {
      ok: response.status >= 200 && response.status < 300,
      status: response.status,
      json: async () => response.payload,
    };
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function classifyHttpError(status: number): ProviderAdapterError {
  let kind: ProviderAdapterErrorKind = "remote";
  let message = "上游模型列表返回了未识别的错误。";
  if (status === 401 || status === 403) {
    kind = "authentication";
    message = "上游模型列表鉴权失败，请检查 API Key。";
  } else if (status === 404 || status === 405) {
    kind = "unsupported";
    message = "上游没有提供兼容的 /models 模型列表接口，可以继续手动填写 Model。";
  } else if (status === 408 || status === 504) {
    kind = "timeout";
    message = "上游模型列表响应超时，请稍后重试。";
  } else if (status === 429) {
    kind = "rate-limit";
    message = "上游模型列表请求受限，请稍后重试。";
  } else if (status >= 500) {
    kind = "server";
    message = "上游模型列表服务暂时不可用。";
  }
  return new ProviderAdapterError(message, kind, status);
}

function timeoutError(): ProviderAdapterError {
  return new ProviderAdapterError("获取模型列表超时，请检查上游地址和网络。", "timeout");
}

function cancelledError(): ProviderAdapterError {
  return new ProviderAdapterError("获取模型列表已取消。", "cancelled");
}

type ProviderModelListJsonResult = {
  response: CompanionProviderModelListHttpResponse;
  payload: unknown;
};

async function fetchJsonWithTimeout(
  fetcher: CompanionProviderModelListFetcher,
  url: string,
  init: Omit<CompanionProviderModelListHttpRequestInit, "signal">,
  parentSignal: AbortSignal | undefined,
  timeoutMs: number,
): Promise<ProviderModelListJsonResult> {
  const controller = new AbortController();
  let timeoutHandle: ReturnType<typeof setTimeout> | null = null;
  let onParentAbort: (() => void) | null = null;
  let timedOut = false;

  const timeoutPromise = new Promise<never>((_, reject) => {
    timeoutHandle = setTimeout(() => {
      timedOut = true;
      controller.abort();
      reject(timeoutError());
    }, Math.max(1, timeoutMs));
  });

  const parentAbortPromise = new Promise<never>((_, reject) => {
    onParentAbort = () => {
      controller.abort();
      reject(cancelledError());
    };
    if (parentSignal?.aborted) {
      onParentAbort();
      return;
    }
    parentSignal?.addEventListener("abort", onParentAbort, { once: true });
  });

  try {
    let response: CompanionProviderModelListHttpResponse;
    try {
      response = await Promise.race([
        fetcher(url, { ...init, signal: controller.signal }),
        timeoutPromise,
        parentAbortPromise,
      ]);
    } catch (error) {
      if (error instanceof ProviderAdapterError) throw error;
      if (parentSignal?.aborted) throw cancelledError();
      if (timedOut) throw timeoutError();
      throw new ProviderAdapterError("获取上游模型列表失败，请检查网络。", "network");
    }

    let payload: unknown = null;
    try {
      payload = await Promise.race([
        response.json(),
        timeoutPromise,
        parentAbortPromise,
      ]);
    } catch (error) {
      if (error instanceof ProviderAdapterError) throw error;
      if (parentSignal?.aborted) throw cancelledError();
      if (timedOut) throw timeoutError();
      if (response.ok) {
        throw new ProviderAdapterError(
          "上游模型列表响应不是可识别的 JSON。",
          "malformed-response",
          response.status,
        );
      }
    }

    return { response, payload };
  } finally {
    if (timeoutHandle !== null) clearTimeout(timeoutHandle);
    if (parentSignal && onParentAbort) {
      parentSignal.removeEventListener("abort", onParentAbort);
    }
    controller.abort();
  }
}

function modelArrayFromPayload(value: unknown): readonly unknown[] | null {
  if (Array.isArray(value)) return value;
  if (!isRecord(value)) return null;
  if (Array.isArray(value.data)) return value.data;
  if (Array.isArray(value.models)) return value.models;
  return null;
}

function modelIdFromValue(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (!isRecord(value)) return null;
  const candidate = typeof value.id === "string"
    ? value.id
    : typeof value.name === "string"
      ? value.name
      : typeof value.model === "string"
        ? value.model
        : null;
  if (!candidate) return null;
  return candidate.replace(/^models\//u, "");
}

export function parseCompanionProviderModelList(value: unknown): string[] {
  const candidates = modelArrayFromPayload(value);
  if (!candidates) return [];
  return normalizeCompanionProviderModelIds(
    candidates.map(modelIdFromValue),
  );
}

export function getCompanionProviderModelListUrl(
  settings: CompanionProviderSettings,
): string {
  if (settings.protocol === "local") {
    throw new ProviderAdapterError("本地 Provider 不需要获取模型列表。", "unsupported");
  }
  if (settings.protocol === "ollama-local") return "内置 Ollama（本机）/api/tags";
  try {
    const endpoint = normalizeCompanionProviderEndpoint(
      settings.protocol,
      settings.endpoint,
    );
    const url = new URL(endpoint);
    const pathname = url.pathname.replace(/\/+$/u, "");
    if (pathname.endsWith("/models")) return url.toString().replace(/\/$/u, "");
    url.pathname = `${pathname}/models`;
    return url.toString().replace(/\/$/u, "");
  } catch (error) {
    if (error instanceof ProviderAdapterError) throw error;
    throw new ProviderAdapterError(
      error instanceof Error ? error.message : "聊天服务地址无效。",
      "configuration",
    );
  }
}

export async function fetchCompanionProviderModels(
  settings: CompanionProviderSettings,
  credential: string | null | undefined,
  options: {
    fetcher?: CompanionProviderModelListFetcher;
    signal?: AbortSignal;
    timeoutMs?: number;
  } = {},
): Promise<CompanionProviderModelListResult> {
  if (settings.protocol === "local") {
    throw new ProviderAdapterError("本地 Provider 不需要获取模型列表。", "unsupported");
  }
  const secret = credential?.trim() ?? "";
  if (!isLocalCompanionProviderProtocol(settings.protocol) && !secret) {
    throw new ProviderAdapterError("远程 Provider 凭据未配置。", "configuration");
  }
  const url = getCompanionProviderModelListUrl(settings);
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(settings.protocol === "ollama-local"
      ? {}
      : settings.protocol === "gemini-native"
        ? { "x-goog-api-key": secret }
        : { Authorization: `Bearer ${secret}` }),
  };
  const fetcher = options.fetcher
    ?? (isTauriRuntime() ? createNativeFetcher(settings.protocol, secret) : browserFetcher);
  const { response, payload } = await fetchJsonWithTimeout(
    fetcher,
    url,
    { method: "GET", headers },
    options.signal,
    options.timeoutMs ?? DEFAULT_MODEL_LIST_TIMEOUT_MS,
  );
  if (!response.ok) throw classifyHttpError(response.status);

  const models = parseCompanionProviderModelList(payload);
  if (models.length === 0) {
    throw new ProviderAdapterError(
      "上游模型列表为空或格式不受支持，可以继续手动填写 Model。",
      "malformed-response",
      response.status,
    );
  }
  return { models };
}
