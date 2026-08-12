import { describe, expect, test, vi } from "vitest";
import {
  ProviderAdapterError,
  createGeminiNativeProviderAdapter,
  createLocalProviderAdapter,
  createOpenAiCompatibleProviderAdapter,
  type ProviderGenerateRequest,
  type ProviderHttpFetcher,
} from "./companionProviderAdapter";

function response(payload: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  };
}

function textRequest(overrides: Partial<ProviderGenerateRequest> = {}): ProviderGenerateRequest {
  return {
    model: "generic-model",
    system: "SYSTEM_ONLY",
    messages: [
      { role: "user", content: "USER_MESSAGE" },
      { role: "assistant", content: "ASSISTANT_MESSAGE" },
    ],
    output: { format: "text" },
    timeoutMs: 200,
    generation: { temperature: 0.2, maxOutputTokens: 64 },
    ...overrides,
  };
}

describe("domain-neutral Provider Adapter contract", () => {
  test("keeps the Adapter module free of Harness and desktop-pet domain imports", () => {
    const sourceMap = import.meta.glob("./companionProviderAdapter.ts", {
      query: "?raw",
      import: "default",
      eager: true,
    }) as Record<string, string>;
    const source = sourceMap["./companionProviderAdapter.ts"] ?? "";
    expect(source).toMatch(/export type ProviderGenerateRequest/);
    for (const forbiddenImport of [
      "companionHarnessTypes",
      "companionModelPort",
      "companionModelCodec",
      "companionContext",
      "companionMemory",
      "petSoul",
      "task-core",
    ]) {
      expect(source).not.toMatch(new RegExp(`from\\s+[\"'].*${forbiddenImport}`));
    }
    for (const forbiddenDomainName of [
      "ActionCandidate",
      "MemoryCandidate",
      "CompanionModelResponse",
      "ReminderInstance",
      "taskContext",
      "memoryExtraction",
      "actionCandidates",
      "memoryCandidates",
    ]) {
      expect(source).not.toContain(forbiddenDomainName);
    }
  });

  test("maps the generic request to Gemini-native without leaking domain fields", async () => {
    const fetcher = vi.fn<ProviderHttpFetcher>(async () => response({
      candidates: [{ content: { parts: [{ text: "GEMINI_TEXT" }] } }],
    }));
    const adapter = createGeminiNativeProviderAdapter({
      id: "google-gemini",
      endpoint: "https://generativelanguage.googleapis.com/v1beta",
      model: "gemini-test",
      credential: "SECRET_SENTINEL",
      fetcher,
      capabilities: { cancellation: true, usageMetadata: true },
    });

    await expect(adapter.generate(textRequest())).resolves.toMatchObject({
      text: "GEMINI_TEXT",
      metadata: { providerId: "google-gemini", model: "generic-model" },
    });
    expect(adapter.capabilities).toEqual({
      textGeneration: true,
      structuredOutput: "none",
      cancellation: true,
      usageMetadata: true,
    });
    const [url, init] = fetcher.mock.calls[0]!;
    const body = JSON.parse(init.body) as Record<string, unknown>;
    expect(url).toBe(
      "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent",
    );
    expect(body.system_instruction).toEqual({ parts: [{ text: "SYSTEM_ONLY" }] });
    expect(body.contents).toEqual([
      { role: "user", parts: [{ text: "USER_MESSAGE" }] },
      { role: "model", parts: [{ text: "ASSISTANT_MESSAGE" }] },
    ]);
    expect(JSON.stringify(body)).not.toContain("SECRET_SENTINEL");
    expect(JSON.stringify(body)).not.toContain("Task");
    expect(JSON.stringify(body)).not.toContain("Memory");
  });

  test("maps the generic request to OpenAI-compatible chat/completions", async () => {
    const fetcher = vi.fn<ProviderHttpFetcher>(async () => response({
      choices: [{ message: { content: "OPENAI_TEXT" } }],
      usage: { prompt_tokens: 11, completion_tokens: 7 },
    }));
    const adapter = createOpenAiCompatibleProviderAdapter({
      id: "custom-provider",
      endpoint: "https://models.example/v1",
      model: "chat-model",
      credential: "SECRET_SENTINEL",
      fetcher,
      capabilities: { usageMetadata: true },
    });

    await expect(adapter.generate(textRequest())).resolves.toMatchObject({
      text: "OPENAI_TEXT",
      metadata: {
        providerId: "custom-provider",
        model: "generic-model",
        usage: { inputTokens: 11, outputTokens: 7 },
      },
    });
    const [url, init] = fetcher.mock.calls[0]!;
    const body = JSON.parse(init.body) as Record<string, unknown>;
    expect(url).toBe("https://models.example/v1/chat/completions");
    expect(body.messages).toEqual([
      { role: "system", content: "SYSTEM_ONLY" },
      { role: "user", content: "USER_MESSAGE" },
      { role: "assistant", content: "ASSISTANT_MESSAGE" },
    ]);
    expect(body).not.toHaveProperty("response_format");
    expect(JSON.stringify(body)).not.toContain("SECRET_SENTINEL");
  });

  test("does not guess structured support from provider name, endpoint, or model", async () => {
    const fetcher = vi.fn<ProviderHttpFetcher>(async () => response({
      choices: [{ message: { content: "{}" } }],
    }));
    const adapter = createOpenAiCompatibleProviderAdapter({
      id: "structured-looking-provider",
      endpoint: "https://structured.example/v1",
      model: "json-schema-model",
      credential: "SECRET_SENTINEL",
      fetcher,
    });

    expect(adapter.capabilities.structuredOutput).toBe("none");
    await expect(adapter.generate(textRequest({ output: { format: "json_object" } })))
      .rejects.toMatchObject({ kind: "unsupported" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  test("sends structured fields only when explicitly verified", async () => {
    const fetcher = vi.fn<ProviderHttpFetcher>(async () => response({
      choices: [{ message: { content: JSON.stringify({ replyDraft: "JSON_OK" }) } }],
    }));
    const adapter = createOpenAiCompatibleProviderAdapter({
      id: "verified-json-provider",
      endpoint: "https://models.example/v1",
      model: "chat-model",
      credential: "SECRET_SENTINEL",
      fetcher,
      capabilities: { structuredOutput: "json_schema" },
    });
    await expect(adapter.generate(textRequest({
      output: {
        format: "json_schema",
        name: "response-envelope",
        schema: { type: "object", properties: { replyDraft: { type: "string" } } },
      },
    }))).resolves.toMatchObject({ structured: { replyDraft: "JSON_OK" } });
    const [, init] = fetcher.mock.calls[0]!;
    const body = JSON.parse(init.body) as Record<string, unknown>;
    expect(body.response_format).toEqual({
      type: "json_schema",
      json_schema: {
        name: "response-envelope",
        schema: { type: "object", properties: { replyDraft: { type: "string" } } },
        strict: true,
      },
    });
  });

  test("local adapter is text-only and never calls a fetcher", async () => {
    const local = createLocalProviderAdapter({
      id: "local",
      localGenerate: () => "LOCAL_TEXT",
    });
    await expect(local.generate(textRequest())).resolves.toEqual({
      text: "LOCAL_TEXT",
      metadata: { providerId: "local", model: "generic-model" },
    });
    expect(local.info.kind).toBe("local");
    expect(local.capabilities.structuredOutput).toBe("none");
  });

  test("covers cancellation and timeout without retrying", async () => {
    const hanging = vi.fn<ProviderHttpFetcher>(() => new Promise(() => {}));
    const adapter = createOpenAiCompatibleProviderAdapter({
      id: "cancel-provider",
      endpoint: "https://models.example/v1",
      model: "chat-model",
      credential: "SECRET_SENTINEL",
      fetcher: hanging,
      timeoutMs: 10,
    });
    const controller = new AbortController();
    const request = adapter.generate(textRequest({ signal: controller.signal }));
    controller.abort();
    await expect(request).rejects.toMatchObject({ kind: "cancelled" });
    expect(hanging).toHaveBeenCalledTimes(1);

    const timeoutRequest = adapter.generate(textRequest({ timeoutMs: 10 }));
    await expect(timeoutRequest).rejects.toMatchObject({ kind: "timeout" });
    expect(hanging).toHaveBeenCalledTimes(2);
  });

  test("keeps the transport signal alive while response.json() consumes the body", async () => {
    let signalAbortedDuringJson: boolean | undefined;
    const fetcher = vi.fn<ProviderHttpFetcher>(async (_url, init) => ({
      ok: true,
      status: 200,
      json: async () => {
        signalAbortedDuringJson = init.signal?.aborted;
        return { choices: [{ message: { content: "REMOTE_OK" } }] };
      },
    }));
    const adapter = createOpenAiCompatibleProviderAdapter({
      id: "body-lifecycle-provider",
      endpoint: "https://models.example/v1",
      model: "chat-model",
      credential: "SECRET_SENTINEL",
      fetcher,
      timeoutMs: 100,
    });

    await expect(adapter.generate(textRequest())).resolves.toMatchObject({
      text: "REMOTE_OK",
    });
    expect(signalAbortedDuringJson).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  test("allows a delayed response body to finish before timeout", async () => {
    vi.useFakeTimers();
    try {
      let releaseBody!: () => void;
      const body = new Promise<unknown>((resolve) => {
        releaseBody = () => resolve({ choices: [{ message: { content: "DELAYED_OK" } }] });
      });
      const fetcher = vi.fn<ProviderHttpFetcher>(async () => ({
        ok: true,
        status: 200,
        json: async () => body,
      }));
      const adapter = createOpenAiCompatibleProviderAdapter({
        id: "delayed-body-provider",
        endpoint: "https://models.example/v1",
        model: "chat-model",
        credential: "SECRET_SENTINEL",
        fetcher,
        timeoutMs: 50,
      });

      const pending = adapter.generate(textRequest({ timeoutMs: 50 }));
      await vi.advanceTimersByTimeAsync(20);
      releaseBody();
      await expect(pending).resolves.toMatchObject({ text: "DELAYED_OK" });
      expect(fetcher).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  test("times out when response.json() never settles and does not retry", async () => {
    vi.useFakeTimers();
    try {
      let releaseBody!: () => void;
      const body = new Promise<unknown>((resolve) => {
        releaseBody = () => resolve({ choices: [{ message: { content: "LATE" } }] });
      });
      const fetcher = vi.fn<ProviderHttpFetcher>(async () => ({
        ok: true,
        status: 200,
        json: async () => body,
      }));
      const adapter = createOpenAiCompatibleProviderAdapter({
        id: "hanging-body-provider",
        endpoint: "https://models.example/v1",
        model: "chat-model",
        credential: "SECRET_SENTINEL",
        fetcher,
        timeoutMs: 10,
      });

      const pending = adapter.generate(textRequest({ timeoutMs: 10 }));
      const rejection = expect(pending).rejects.toMatchObject({ kind: "timeout" });
      await vi.advanceTimersByTimeAsync(10);
      await rejection;
      expect(fetcher).toHaveBeenCalledTimes(1);
      releaseBody();
    } finally {
      vi.useRealTimers();
    }
  });

  test("returns cancelled when the parent aborts while response.json() is pending", async () => {
    let releaseBody!: () => void;
    const body = new Promise<unknown>((resolve) => {
      releaseBody = () => resolve({ choices: [{ message: { content: "LATE" } }] });
    });
    const fetcher = vi.fn<ProviderHttpFetcher>(async () => ({
      ok: true,
      status: 200,
      json: async () => body,
    }));
    const adapter = createOpenAiCompatibleProviderAdapter({
      id: "cancelled-body-provider",
      endpoint: "https://models.example/v1",
      model: "chat-model",
      credential: "SECRET_SENTINEL",
      fetcher,
      timeoutMs: 100,
    });
    const controller = new AbortController();
    const pending = adapter.generate(textRequest({ signal: controller.signal }));
    await Promise.resolve();
    await Promise.resolve();
    controller.abort();

    await expect(pending).rejects.toMatchObject({ kind: "cancelled" });
    expect(fetcher).toHaveBeenCalledTimes(1);
    releaseBody();
  });

  test("classifies a successful response body parse failure without exposing the parser error", async () => {
    const fetcher = vi.fn<ProviderHttpFetcher>(async () => ({
      ok: true,
      status: 200,
      json: async () => {
        throw new Error("SECRET_SENTINEL parser detail");
      },
    }));
    const adapter = createOpenAiCompatibleProviderAdapter({
      id: "malformed-body-provider",
      endpoint: "https://models.example/v1",
      model: "chat-model",
      credential: "SECRET_SENTINEL",
      fetcher,
    });

    const result = adapter.generate(textRequest());
    await expect(result).rejects.toMatchObject({ kind: "malformed-response" });
    await expect(result).rejects.not.toHaveProperty(
      "message",
      expect.stringContaining("SECRET_SENTINEL"),
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  test.each([401, 403, 429, 500])(
    "keeps HTTP %s classification when the error body is not JSON",
    async (status) => {
      const fetcher = vi.fn<ProviderHttpFetcher>(async () => ({
        ok: false,
        status,
        json: async () => {
          throw new Error("SECRET_SENTINEL error body");
        },
      }));
      const adapter = createOpenAiCompatibleProviderAdapter({
        id: "malformed-error-body-provider",
        endpoint: "https://models.example/v1",
        model: "chat-model",
        credential: "SECRET_SENTINEL",
        fetcher,
      });

      await expect(adapter.generate(textRequest())).rejects.toMatchObject({
        status,
        kind: status === 401 || status === 403
          ? "authentication"
          : status === 429
            ? "rate-limit"
            : "server",
      });
      expect(fetcher).toHaveBeenCalledTimes(1);
    },
  );

  test.each([401, 403, 429, 500])("classifies HTTP %s without exposing response detail", async (status) => {
    const fetcher = vi.fn<ProviderHttpFetcher>(async () => response({
      error: { message: "SECRET_SENTINEL" },
    }, status));
    const adapter = createOpenAiCompatibleProviderAdapter({
      id: "error-provider",
      endpoint: "https://models.example/v1",
      model: "chat-model",
      credential: "SECRET_SENTINEL",
      fetcher,
    });
    const result = adapter.generate(textRequest());
    await expect(result).rejects.toBeInstanceOf(ProviderAdapterError);
    await expect(result).rejects.not.toHaveProperty("message", expect.stringContaining("SECRET_SENTINEL"));
    await expect(result).rejects.toHaveProperty("status", status);
  });

  test("classifies network and malformed responses safely", async () => {
    const network = createOpenAiCompatibleProviderAdapter({
      id: "network-provider",
      endpoint: "https://models.example/v1",
      model: "chat-model",
      credential: "SECRET_SENTINEL",
      fetcher: vi.fn<ProviderHttpFetcher>(async () => {
        throw new Error("SECRET_SENTINEL network detail");
      }),
    });
    await expect(network.generate(textRequest())).rejects.toMatchObject({ kind: "network" });
    await expect(network.generate(textRequest())).rejects.not.toHaveProperty(
      "message",
      expect.stringContaining("SECRET_SENTINEL"),
    );

    const malformed = createOpenAiCompatibleProviderAdapter({
      id: "malformed-provider",
      endpoint: "https://models.example/v1",
      model: "chat-model",
      credential: "SECRET_SENTINEL",
      fetcher: vi.fn<ProviderHttpFetcher>(async () => response({ choices: [] })),
    });
    await expect(malformed.generate(textRequest())).rejects.toMatchObject({
      kind: "malformed-response",
    });
  });
});
