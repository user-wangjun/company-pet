import { describe, expect, test, vi } from "vitest";
import { assembleCompanionContext } from "./companionContext";
import {
  createCompanionModelPort,
} from "./companionModelPort";
import {
  ProviderAdapterError,
  createOpenAiCompatibleProviderAdapter,
  type ProviderAdapter,
  type ProviderGenerateRequest,
  type ProviderGenerateResponse,
  type ProviderHttpFetcher,
} from "./companionProviderAdapter";
import type { ProviderResolver } from "./companionProviderResolver";
import type { CompanionInput } from "./companionHarnessTypes";

const input = (overrides: Partial<CompanionInput> = {}): CompanionInput => ({
  requestId: "request-1",
  sessionId: "session-1",
  sourceMessageId: "message-1",
  userId: "local-user",
  petId: "xiaoju-cat",
  message: "当前安全输入，任务二字不能让它被删除。",
  currentTime: "2026-08-11T12:00:00.000Z",
  timezone: "Asia/Shanghai",
  utcOffsetMinutes: 480,
  source: "chat",
  ...overrides,
});

function trustedContext(message = input().message) {
  return assembleCompanionContext({
    petId: "xiaoju-cat",
    userInput: message,
    systemPrompt: "安全 system",
    history: [{ id: "history-1", speaker: "user", text: "安全历史" }],
  });
}

function createFakeAdapter(
  handler: (request: ProviderGenerateRequest) => Promise<ProviderGenerateResponse>,
  capabilities: ProviderAdapter["capabilities"] = {
    textGeneration: true,
    structuredOutput: "none",
    cancellation: true,
    usageMetadata: true,
  },
): ProviderAdapter {
  return {
    id: "fake-provider",
    protocol: "openai-compatible",
    capabilities,
    info: {
      kind: "remote",
      provider: "Fake Provider",
      target: "https://fake.example/v1",
      disclosure: "fake disclosure",
    },
    generate: handler,
  };
}

function resolverFor(adapterValue: ProviderAdapter): ProviderResolver {
  return { resolve: () => adapterValue };
}

describe("Harness-owned CompanionModelPort", () => {
  test("defers resolution until beginTurn and freezes one adapter/info/capabilities snapshot", () => {
    const firstAdapter = createFakeAdapter(async () => ({
      text: "FIRST",
      metadata: { providerId: "first" },
    }));
    const secondAdapter = createFakeAdapter(async () => ({
      text: "SECOND",
      metadata: { providerId: "second" },
    }));
    let selected = firstAdapter;
    const resolver = { resolve: vi.fn(() => selected) };
    const port = createCompanionModelPort({
      resolver,
      info: firstAdapter.info,
    });

    expect(resolver.resolve).not.toHaveBeenCalled();
    const firstTurn = port.beginTurn();
    selected = secondAdapter;
    const secondTurn = port.beginTurn();

    expect(resolver.resolve).toHaveBeenCalledTimes(2);
    expect(firstTurn.adapter).toBe(firstAdapter);
    expect(firstTurn.info).toEqual(firstAdapter.info);
    expect(firstTurn.capabilities).toEqual(firstAdapter.capabilities);
    expect(firstTurn.info.provider).toBe("Fake Provider");
    expect(secondTurn.adapter).toBe(secondAdapter);
    expect(Object.isFrozen(firstTurn)).toBe(true);
    expect(Object.isFrozen(firstTurn.info)).toBe(true);
    expect(Object.isFrozen(firstTurn.capabilities)).toBe(true);
  });

  test("resolves one Adapter, encodes once, calls it once, and decodes text-only", async () => {
    const calls: ProviderGenerateRequest[] = [];
    const model = createFakeAdapter(async (request) => {
      calls.push(request);
      return {
        text: "一次安全回复",
        metadata: { providerId: "fake-provider", model: "fake-model" },
      };
    });
    const port = createCompanionModelPort({
      resolver: resolverFor(model),
      info: model.info,
    });

    const nextInput = input();
    const response = await port.generate({
      input: nextInput,
      context: trustedContext(),
    });

    expect(response).toMatchObject({
      replyDraft: "一次安全回复",
      actions: [],
      memoryCandidates: [],
      metadata: { provider: "fake-provider", model: "fake-model" },
    });
    expect(calls).toHaveLength(1);
    const lastMessage = calls[0]!.messages[calls[0]!.messages.length - 1];
    expect(lastMessage).toEqual({
      role: "user",
      content: nextInput.message,
    });
    expect(JSON.stringify(calls[0])).not.toContain("request-1");
    expect(JSON.stringify(calls[0])).not.toContain("session-1");
    expect(JSON.stringify(calls[0])).not.toContain("message-1");
    expect(JSON.stringify(calls[0])).not.toContain("local-user");
    expect(JSON.stringify(calls[0])).not.toContain("xiaoju-cat");
    expect(JSON.stringify(calls[0])).not.toContain("2026-08-11T12:00:00.000Z");
    expect(JSON.stringify(calls[0])).not.toContain("Asia/Shanghai");
    expect(JSON.stringify(calls[0])).not.toContain("480");
  });

  test("decodes structured candidates and falls back to text without a second Adapter call", async () => {
    const generate = vi.fn(async () => ({
      text: "安全 fallback",
      structured: {
        replyDraft: "结构化但畸形",
        actions: "not-an-array",
      },
      metadata: { providerId: "fake-provider" },
    }));
    const model = createFakeAdapter(generate, {
      textGeneration: true,
      structuredOutput: "json_schema",
      cancellation: true,
      usageMetadata: false,
    });
    const port = createCompanionModelPort({
      resolver: resolverFor(model),
      info: model.info,
    });

    await expect(port.generate({
      input: input(),
      context: trustedContext(),
    })).resolves.toMatchObject({
      replyDraft: "安全 fallback",
      actions: [],
      memoryCandidates: [],
    });
    expect(generate).toHaveBeenCalledTimes(1);
  });

  test("resolves one snapshot but rejects untrusted or mismatched Context before calling Adapter", async () => {
    const generate = vi.fn(async () => ({
      text: "不应调用",
      metadata: { providerId: "fake-provider" },
    }));
    const model = createFakeAdapter(generate);
    const resolver = { resolve: vi.fn(() => model) };
    const port = createCompanionModelPort({
      resolver,
      info: model.info,
    });
    const forged = {
      petId: "xiaoju-cat",
      systemInstruction: "LOCAL_TASK_PROJECTION_MUST_NEVER_LEAVE",
      history: [],
      userInput: input().message,
    } as unknown as ReturnType<typeof trustedContext>;

    await expect(port.generate({ input: input(), context: forged })).rejects.toMatchObject({
      kind: "configuration",
    });
    expect(resolver.resolve).toHaveBeenCalledTimes(1);
    expect(generate).not.toHaveBeenCalled();

    await expect(port.generate({
      input: input({ message: "changed" }),
      context: trustedContext(),
    })).rejects.toMatchObject({ kind: "configuration" });
    expect(resolver.resolve).toHaveBeenCalledTimes(2);
  });

  test("rejects a trusted Context bound to another pet or context epoch", async () => {
    const generate = vi.fn(async () => ({
      text: "不应调用",
      metadata: { providerId: "fake-provider" },
    }));
    const model = createFakeAdapter(generate);
    const resolver = { resolve: vi.fn(() => model) };
    const port = createCompanionModelPort({
      resolver,
      info: model.info,
    });
    const context = assembleCompanionContext({
      petId: "xiaoju-cat",
      userInput: input().message,
      contextEpoch: 1,
      history: [{ id: "pet-a", speaker: "user", text: "只属于小橘" }],
    });

    await expect(port.generate({
      input: input({ petId: "other-cat", contextEpoch: 1 }),
      context,
    })).rejects.toMatchObject({ kind: "configuration" });
    await expect(port.generate({
      input: input({ contextEpoch: 2 }),
      context,
    })).rejects.toMatchObject({ kind: "configuration" });
    expect(resolver.resolve).toHaveBeenCalledTimes(2);
    expect(generate).not.toHaveBeenCalled();
  });

  test("fails closed before Adapter and fetch for untrusted or mismatched Context", async () => {
    const fetcher = vi.fn<ProviderHttpFetcher>(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ choices: [{ message: { content: "SHOULD_NOT_RETURN" } }] }),
    }));
    const rawAdapter = createOpenAiCompatibleProviderAdapter({
      id: "fail-closed-provider",
      endpoint: "https://models.example/v1",
      model: "chat-model",
      credential: "SECRET_SENTINEL",
      fetcher,
    });
    const adapter: ProviderAdapter = {
      ...rawAdapter,
      generate: vi.fn(rawAdapter.generate),
    };
    const port = createCompanionModelPort({
      resolver: { resolve: () => adapter },
      info: adapter.info,
    });
    const turn = port.beginTurn();
    const forged = {
      petId: "xiaoju-cat",
      systemInstruction: "LOCAL_TASK_PROJECTION_MUST_NEVER_LEAVE",
      history: [],
      userInput: input().message,
    } as unknown as ReturnType<typeof trustedContext>;
    const trusted = trustedContext();

    await expect(turn.generate({ input: input(), context: forged })).rejects.toMatchObject({
      kind: "configuration",
    });
    await expect(turn.generate({
      input: input({ petId: "other-cat" }),
      context: trusted,
    })).rejects.toMatchObject({ kind: "configuration" });
    await expect(turn.generate({
      input: input({ contextEpoch: 2 }),
      context: assembleCompanionContext({
        petId: "xiaoju-cat",
        userInput: input().message,
        contextEpoch: 1,
      }),
    })).rejects.toMatchObject({ kind: "configuration" });

    expect(adapter.generate).not.toHaveBeenCalled();
    expect(fetcher).not.toHaveBeenCalled();
    const serialized = JSON.stringify({ forged, trusted });
    expect(serialized).not.toContain("SECRET_SENTINEL");
  });

  test("allows an untrusted Context on the local path without any external call", async () => {
    const generate = vi.fn(async (request: ProviderGenerateRequest) => ({
      text: request.messages[0]?.content === "本地输入" ? "LOCAL_OK" : "WRONG_INPUT",
      metadata: { providerId: "local" },
    }));
    const local: ProviderAdapter = {
      id: "local",
      protocol: "local",
      capabilities: {
        textGeneration: true,
        structuredOutput: "none",
        cancellation: true,
        usageMetadata: false,
      },
      info: {
        kind: "local",
        provider: "Local",
        target: "本机",
        disclosure: "local",
      },
      generate,
    };
    const port = createCompanionModelPort({
      resolver: resolverFor(local),
      info: local.info,
    });
    const forged = {
      petId: "xiaoju-cat",
      systemInstruction: "HAND_WRITTEN_LOCAL_CONTEXT",
      history: [],
      userInput: "本地输入",
    } as unknown as ReturnType<typeof trustedContext>;

    await expect(port.generate({
      input: input({ message: "本地输入" }),
      context: forged,
    })).resolves.toMatchObject({ replyDraft: "LOCAL_OK" });
    expect(generate).toHaveBeenCalledTimes(1);
  });

  test("converts Adapter errors to the existing safe error classification", async () => {
    const model = createFakeAdapter(async () => {
      throw new ProviderAdapterError(
        "Provider 请求频率或额度受限。",
        "rate-limit",
        429,
      );
    });
    const port = createCompanionModelPort({
      resolver: resolverFor(model),
      info: model.info,
    });
    await expect(port.generate({
      input: input(),
      context: trustedContext(),
    })).rejects.toMatchObject({
      kind: "rate-limit",
      status: 429,
    });
  });

  test("pre-aborted Turn performs zero Adapter calls", async () => {
    const generate = vi.fn(async () => ({
      text: "不应调用",
      metadata: { providerId: "fake-provider" },
    }));
    const model = createFakeAdapter(generate);
    const port = createCompanionModelPort({
      resolver: resolverFor(model),
      info: model.info,
    });
    const controller = new AbortController();
    controller.abort();
    await expect(port.generate({
      input: input({ signal: controller.signal }),
      context: trustedContext(),
      signal: controller.signal,
    })).rejects.toMatchObject({ kind: "cancelled" });
    expect(generate).not.toHaveBeenCalled();
  });
});
