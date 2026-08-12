import { afterEach, describe, expect, test, vi } from "vitest";
import {
  CompanionChatProviderError,
  DEFAULT_COMPANION_PROVIDER_TIMEOUT_MS,
} from "./companionChatProvider";
import { LOCAL_COMPANION_CHAT_FALLBACK_DISCLOSURE } from "./companionChatRuntime";
import { createCompanionModelPort } from "./companionModelPort";
import {
  createCompanionHarness,
  type CompanionHarnessDependencies,
} from "./companionHarness";
import type {
  ActionCandidate,
  CompanionActionService,
  CompanionActionCandidate,
  CompanionInput,
  CompanionMemoryService,
  CompanionModelResponse,
  CompanionResponseSink,
  MemoryCandidate,
} from "./companionHarnessTypes";
import type {
  CompanionModelPort,
  CompanionModelPortInfo,
  HarnessModelRequest,
  ResolvedCompanionModelTurn,
} from "./companionModelPort";
import type {
  ProviderAdapter,
  ProviderGenerateRequest,
  ProviderGenerateResponse,
  ProviderHttpFetcher,
} from "./companionProviderAdapter";
import { createOpenAiCompatibleProviderAdapter } from "./companionProviderAdapter";

const REMOTE_INFO: CompanionModelPortInfo = {
  kind: "remote",
  provider: "Fake Remote",
  target: "https://fake.remote.test",
  disclosure: "远程模式：本轮请求由已配置的远程 Provider 处理。",
};

const LOCAL_INFO: CompanionModelPortInfo = {
  kind: "local",
  provider: "Fake Local",
  target: "本机",
  disclosure: "本地模式：不会发起网络请求。",
};

type FakeHandler = (
  request: HarnessModelRequest,
  callNumber: number,
) => Promise<unknown>;

class FakeModelPort implements CompanionModelPort {
  readonly calls: HarnessModelRequest[] = [];

  constructor(
    readonly info: CompanionModelPortInfo,
    private readonly handler: FakeHandler,
  ) {}

  beginTurn(): ResolvedCompanionModelTurn {
    const info = Object.freeze({ ...this.info });
    const capabilities = Object.freeze({
      textGeneration: true as const,
      structuredOutput: "none" as const,
      cancellation: true,
      usageMetadata: false,
    });
    const adapter: ProviderAdapter = {
      id: info.provider,
      protocol: info.kind === "local" ? "local" : "openai-compatible",
      capabilities,
      info,
      generate: async () => ({
        text: "unused fake adapter response",
        metadata: { providerId: info.provider },
      }),
    };
    return Object.freeze({
      adapter,
      info,
      capabilities,
      generate: (request: HarnessModelRequest) => this.generate(request),
    });
  }

  generate(request: HarnessModelRequest): Promise<CompanionModelResponse> {
    this.calls.push(request);
    return this.handler(request, this.calls.length) as Promise<CompanionModelResponse>;
  }
}

function input(overrides: Partial<CompanionInput> = {}): CompanionInput {
  return {
    requestId: "request-1",
    sessionId: "session-1",
    sourceMessageId: "message-1",
    userId: "local-user",
    petId: "xiaoju-cat",
    message: "今天还行",
    currentTime: "2026-08-11T12:00:00.000Z",
    timezone: "Asia/Shanghai",
    utcOffsetMinutes: 480,
    source: "chat",
    ...overrides,
  };
}

function modelResponse(replyDraft = "我在听。") {
  return { replyDraft };
}

function actionCandidate(sourceMessageId: string): ActionCandidate {
  return {
    sourceMessageId,
    intent: "explicit",
    type: "create_task",
    payload: { title: "测试待办", dueAt: "2026-08-12" },
  };
}

function memoryCandidate(sourceMessageId: string): MemoryCandidate {
  return {
    scope: "global",
    type: "preference",
    category: "preference",
    lifetime: "stable",
    content: "用户喜欢桂花茶",
    source: "explicit",
    evidence: "用户明确表达",
    sourceMessageId,
    confidence: 0.9,
    importance: 0.8,
    explicitness: "explicit",
    confirmationStatus: "not_required",
    expiresAt: null,
    requiresConfirmation: false,
    confirmed: true,
  };
}

function createDomainSpies() {
  const actionCalls: Array<{
    input: CompanionInput;
    candidates: readonly CompanionActionCandidate[];
    signal: AbortSignal;
  }> = [];
  const memoryCalls: Array<{
    input: CompanionInput;
    candidates: readonly MemoryCandidate[];
    signal: AbortSignal;
  }> = [];
  const commits: Array<{ input: CompanionInput; text: string | null }> = [];

  const actionService: CompanionActionService = {
    async process(nextInput, candidates, signal) {
      actionCalls.push({ input: nextInput, candidates, signal });
      return candidates.map((candidate) => ({
        type: candidate.type,
        status: "succeeded" as const,
      }));
    },
  };
  const memoryService: CompanionMemoryService = {
    async process(nextInput, candidates, signal) {
      memoryCalls.push({ input: nextInput, candidates, signal });
      return {
        status: "succeeded",
        acceptedCount: candidates.length,
        rejectedCount: 0,
        decisions: candidates.map((_, index) => ({
          index,
          status: "inserted" as const,
        })),
      };
    },
  };
  const responseSink: CompanionResponseSink = {
    commit(nextInput, response, guard) {
      guard.commitIfCurrent(nextInput, response, () => {
        commits.push({ input: nextInput, text: response.text });
      });
    },
  };

  return { actionCalls, memoryCalls, commits, actionService, memoryService, responseSink };
}

function createHarness(
  modelPort: CompanionModelPort,
  overrides: Partial<CompanionHarnessDependencies> = {},
) {
  return createCompanionHarness({
    modelPort,
    ...overrides,
  });
}

function snapshotAdapter(
  info: CompanionModelPortInfo,
  generate: (request: ProviderGenerateRequest) => Promise<ProviderGenerateResponse>,
): ProviderAdapter {
  const capabilities: ProviderAdapter["capabilities"] = {
    textGeneration: true,
    structuredOutput: "none",
    cancellation: true,
    usageMetadata: false,
  };
  return {
    id: info.provider,
    protocol: info.kind === "local" ? "local" : "openai-compatible",
    capabilities,
    info,
    generate,
  };
}

function snapshotPort(
  initialInfo: CompanionModelPortInfo,
  selected: () => ProviderAdapter,
) {
  const resolver = { resolve: vi.fn(selected) };
  const port = createCompanionModelPort({ resolver, info: initialInfo });
  return { port, resolver: resolver.resolve };
}

async function flushMicrotasks() {
  for (let index = 0; index < 6; index += 1) {
    await Promise.resolve();
  }
}

afterEach(() => {
  vi.useRealTimers();
});

describe("Companion Harness Phase 1", () => {
  test("completes remote plain text with exactly one external model call", async () => {
    const model = new FakeModelPort(REMOTE_INFO, async () => modelResponse("远程回复"));
    const domains = createDomainSpies();
    const response = await createHarness(model, domains).respond(input());

    expect(response).toMatchObject({
      status: "success",
      text: "远程回复",
      canCommit: true,
      degraded: false,
      callCounts: { model: 1, external: 1, local: 0, fallback: 0 },
    });
    expect(model.calls).toHaveLength(1);
    expect(domains.actionCalls).toHaveLength(0);
    expect(domains.memoryCalls).toHaveLength(0);
  });

  test("completes local plain text with zero external calls", async () => {
    const model = new FakeModelPort(LOCAL_INFO, async () => modelResponse("本地回复"));
    const response = await createHarness(model).respond(input());

    expect(response).toMatchObject({
      status: "success",
      text: "本地回复",
      callCounts: { model: 1, external: 0, local: 1, fallback: 0 },
      provider: LOCAL_INFO,
    });
    expect(model.calls).toHaveLength(1);
  });

  test("uses the Provider selected immediately before the Turn: Local to Remote", async () => {
    let selected: "local" | "remote" = "local";
    const localGenerate = vi.fn(async () => ({
      text: "不应走本地",
      metadata: { providerId: "local" },
    }));
    const remoteGenerate = vi.fn(async () => ({
      text: "REMOTE_SNAPSHOT_OK",
      metadata: { providerId: "remote" },
    }));
    const local = snapshotAdapter(LOCAL_INFO, localGenerate);
    const remote = snapshotAdapter(REMOTE_INFO, remoteGenerate);
    const { port, resolver } = snapshotPort(LOCAL_INFO, () => (
      selected === "local" ? local : remote
    ));
    selected = "remote";

    const response = await createHarness(port).respond(input());

    expect(resolver).toHaveBeenCalledTimes(1);
    expect(response).toMatchObject({
      status: "success",
      text: "REMOTE_SNAPSHOT_OK",
      provider: REMOTE_INFO,
      providerDisclosure: REMOTE_INFO.disclosure,
      callCounts: { model: 1, external: 1, local: 0, fallback: 0 },
    });
    expect(remoteGenerate).toHaveBeenCalledTimes(1);
    expect(localGenerate).not.toHaveBeenCalled();
  });

  test("uses the Provider selected immediately before the Turn: Remote to Local", async () => {
    let selected: "local" | "remote" = "remote";
    const remoteFetch = vi.fn();
    const remoteGenerate = vi.fn(async () => {
      remoteFetch();
      return { text: "不应走远程", metadata: { providerId: "remote" } };
    });
    const localGenerate = vi.fn(async () => ({
      text: "LOCAL_SNAPSHOT_OK",
      metadata: { providerId: "local" },
    }));
    const remote = snapshotAdapter(REMOTE_INFO, remoteGenerate);
    const local = snapshotAdapter(LOCAL_INFO, localGenerate);
    const { port, resolver } = snapshotPort(REMOTE_INFO, () => (
      selected === "remote" ? remote : local
    ));
    selected = "local";

    const response = await createHarness(port).respond(input());

    expect(resolver).toHaveBeenCalledTimes(1);
    expect(response).toMatchObject({
      status: "success",
      text: "LOCAL_SNAPSHOT_OK",
      provider: LOCAL_INFO,
      providerDisclosure: LOCAL_INFO.disclosure,
      callCounts: { model: 1, external: 0, local: 1, fallback: 0 },
    });
    expect(localGenerate).toHaveBeenCalledTimes(1);
    expect(remoteGenerate).not.toHaveBeenCalled();
    expect(remoteFetch).not.toHaveBeenCalled();
  });

  test("holds the Turn snapshot across a mid-Turn Provider switch and uses the new Provider next Turn", async () => {
    let selected: "local" | "remote" = "remote";
    let releaseRemote!: (response: ProviderGenerateResponse) => void;
    const remoteResult = new Promise<ProviderGenerateResponse>((resolve) => {
      releaseRemote = resolve;
    });
    const remoteGenerate = vi.fn(async () => remoteResult);
    const localGenerate = vi.fn(async () => ({
      text: "NEXT_LOCAL_OK",
      metadata: { providerId: "local" },
    }));
    const remote = snapshotAdapter(REMOTE_INFO, remoteGenerate);
    const local = snapshotAdapter(LOCAL_INFO, localGenerate);
    const { port, resolver } = snapshotPort(REMOTE_INFO, () => (
      selected === "remote" ? remote : local
    ));
    const harness = createHarness(port);

    const first = harness.respond(input());
    await flushMicrotasks();
    expect(remoteGenerate).toHaveBeenCalledTimes(1);

    selected = "local";
    releaseRemote({ text: "CURRENT_REMOTE_OK", metadata: { providerId: "remote" } });
    const firstResponse = await first;
    const secondResponse = await harness.respond(input({
      requestId: "request-2",
      sourceMessageId: "message-2",
      message: "下一轮输入",
    }));

    expect(firstResponse).toMatchObject({
      status: "success",
      text: "CURRENT_REMOTE_OK",
      provider: REMOTE_INFO,
      callCounts: { external: 1, local: 0 },
    });
    expect(secondResponse).toMatchObject({
      status: "success",
      text: "NEXT_LOCAL_OK",
      provider: LOCAL_INFO,
      callCounts: { external: 0, local: 1 },
    });
    expect(remoteGenerate).toHaveBeenCalledTimes(1);
    expect(localGenerate).toHaveBeenCalledTimes(1);
    expect(resolver).toHaveBeenCalledTimes(2);
  });

  test("keeps concurrent Sessions on independent Provider snapshots", async () => {
    let selected: "local" | "remote" = "remote";
    let releaseRemote!: (response: ProviderGenerateResponse) => void;
    const remoteResult = new Promise<ProviderGenerateResponse>((resolve) => {
      releaseRemote = resolve;
    });
    const remoteGenerate = vi.fn(async () => remoteResult);
    const localGenerate = vi.fn(async () => ({
      text: "CONCURRENT_LOCAL_OK",
      metadata: { providerId: "local" },
    }));
    const remote = snapshotAdapter(REMOTE_INFO, remoteGenerate);
    const local = snapshotAdapter(LOCAL_INFO, localGenerate);
    const { port } = snapshotPort(REMOTE_INFO, () => (
      selected === "remote" ? remote : local
    ));
    const harness = createHarness(port);

    const remoteTurn = harness.respond(input({ sessionId: "remote-session" }));
    await flushMicrotasks();
    selected = "local";
    const localTurn = harness.respond(input({
      requestId: "request-local",
      sessionId: "local-session",
      sourceMessageId: "message-local",
      message: "本地并发输入",
    }));

    const localResponse = await localTurn;
    releaseRemote({ text: "CONCURRENT_REMOTE_OK", metadata: { providerId: "remote" } });
    const remoteResponse = await remoteTurn;

    expect(remoteResponse).toMatchObject({
      status: "success",
      text: "CONCURRENT_REMOTE_OK",
      provider: REMOTE_INFO,
      providerDisclosure: REMOTE_INFO.disclosure,
      callCounts: { external: 1, local: 0 },
    });
    expect(localResponse).toMatchObject({
      status: "success",
      text: "CONCURRENT_LOCAL_OK",
      provider: LOCAL_INFO,
      providerDisclosure: LOCAL_INFO.disclosure,
      callCounts: { external: 0, local: 1 },
    });
    expect(remoteGenerate).toHaveBeenCalledTimes(1);
    expect(localGenerate).toHaveBeenCalledTimes(1);
  });

  test("resolves a Local fallback snapshot only after Remote failure and discloses it", async () => {
    const remoteGenerate = vi.fn(async () => {
      throw new CompanionChatProviderError("暂时不可用", "network");
    });
    const localGenerate = vi.fn(async () => ({
      text: "FALLBACK_LOCAL_OK",
      metadata: { providerId: "local" },
    }));
    const primary = snapshotPort(REMOTE_INFO, () => (
      snapshotAdapter(REMOTE_INFO, remoteGenerate)
    )).port;
    const fallback = snapshotPort(LOCAL_INFO, () => (
      snapshotAdapter(LOCAL_INFO, localGenerate)
    )).port;

    const response = await createHarness(primary, {
      localFallbackModelPort: fallback,
      fallbackToLocal: true,
    }).respond(input());

    expect(response).toMatchObject({
      status: "degraded",
      text: "FALLBACK_LOCAL_OK",
      degraded: true,
      degradedFrom: "network",
      provider: {
        ...LOCAL_INFO,
        disclosure: LOCAL_COMPANION_CHAT_FALLBACK_DISCLOSURE,
      },
      providerDisclosure: LOCAL_COMPANION_CHAT_FALLBACK_DISCLOSURE,
      callCounts: { model: 2, external: 1, local: 1, fallback: 1 },
    });
    expect(remoteGenerate).toHaveBeenCalledTimes(1);
    expect(localGenerate).toHaveBeenCalledTimes(1);
  });

  test("fails closed for sensitive, untrusted, and mismatched Context before Adapter or fetch", async () => {
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

    const sensitive = await createHarness(port).respond(input({
      message: "my password is NEVER_SEND_PASSWORD",
    }));
    const untrusted = await createHarness(port, {
      contextBuilder: {
        build: () => ({
          petId: "xiaoju-cat",
          systemInstruction: "LOCAL_TASK_PROJECTION_MUST_NEVER_LEAVE",
          history: [],
          userInput: "安全输入",
        }),
      },
    }).respond(input({ message: "安全输入", requestId: "request-untrusted" }));
    expect(sensitive).toMatchObject({
      status: "error",
      error: { kind: "content-safety" },
      callCounts: { model: 0, external: 0, local: 0, fallback: 0 },
    });
    expect(untrusted).toMatchObject({
      status: "error",
      error: { kind: "configuration" },
      callCounts: { model: 0, external: 0, local: 0, fallback: 0 },
    });
    expect(adapter.generate).toHaveBeenCalledTimes(0);
    expect(fetcher).toHaveBeenCalledTimes(0);
    const serialized = JSON.stringify({ sensitive, untrusted });
    expect(serialized).not.toContain("NEVER_SEND_PASSWORD");
    expect(serialized).not.toContain("LOCAL_TASK_PROJECTION_MUST_NEVER_LEAVE");
    expect(serialized).not.toContain("SECRET_SENTINEL");
  });

  test("allows ordinary chat without Action or Memory candidates and does not invoke domain services", async () => {
    const model = new FakeModelPort(REMOTE_INFO, async () => modelResponse());
    const domains = createDomainSpies();
    const response = await createHarness(model, domains).respond(input());

    expect(response.status).toBe("success");
    expect(response.actions).toEqual([]);
    expect(response.memory).toMatchObject({
      status: "not-requested",
      acceptedCount: 0,
      rejectedCount: 0,
      decisions: [],
    });
    expect(domains.actionCalls).toHaveLength(0);
    expect(domains.memoryCalls).toHaveLength(0);
  });

  test("does not call the Model Port or domain services when the request starts cancelled", async () => {
    const controller = new AbortController();
    controller.abort();
    const model = new FakeModelPort(REMOTE_INFO, async () => modelResponse());
    const domains = createDomainSpies();
    const response = await createHarness(model, domains).respond(
      input({ signal: controller.signal }),
    );

    expect(response.status).toBe("cancelled");
    expect(response.canCommit).toBe(false);
    expect(response.callCounts).toEqual({ model: 0, external: 0, local: 0, fallback: 0 });
    expect(model.calls).toHaveLength(0);
    expect(domains.actionCalls).toHaveLength(0);
    expect(domains.memoryCalls).toHaveLength(0);
    expect(domains.commits).toHaveLength(0);
  });

  test("propagates cancellation while waiting and drops the late Model response", async () => {
    let resolveModel!: (value: unknown) => void;
    const lateResponse = new Promise<unknown>((resolve) => {
      resolveModel = resolve;
    });
    const model = new FakeModelPort(REMOTE_INFO, async () => lateResponse);
    const domains = createDomainSpies();
    const controller = new AbortController();
    const pending = createHarness(model, domains).respond(input({ signal: controller.signal }));
    await flushMicrotasks();

    expect(model.calls).toHaveLength(1);
    controller.abort();
    const response = await pending;
    expect(response.status).toBe("cancelled");
    expect(response.canCommit).toBe(false);
    expect(model.calls[0]?.signal?.aborted).toBe(true);
    expect(domains.actionCalls).toHaveLength(0);
    expect(domains.memoryCalls).toHaveLength(0);
    expect(domains.commits).toHaveLength(0);

    resolveModel({
      ...modelResponse("迟到回复"),
      actions: [actionCandidate("message-1")],
      memoryCandidates: [memoryCandidate("message-1")],
    });
    await flushMicrotasks();
    expect(domains.actionCalls).toHaveLength(0);
    expect(domains.memoryCalls).toHaveLength(0);
    expect(domains.commits).toHaveLength(0);
  });

  test("discards a late result when a newer Turn replaces the same session", async () => {
    let resolveFirst!: (value: unknown) => void;
    const firstResponse = new Promise<unknown>((resolve) => {
      resolveFirst = resolve;
    });
    const model = new FakeModelPort(REMOTE_INFO, async (_request, callNumber) =>
      callNumber === 1 ? firstResponse : modelResponse("新 Turn 回复"));
    const domains = createDomainSpies();
    const harness = createHarness(model, domains);
    const firstInput = input();
    const first = harness.respond(firstInput);
    await flushMicrotasks();

    const secondInput = input({
      requestId: "request-2",
      sourceMessageId: "message-2",
      message: "新消息",
    });
    const second = harness.respond(secondInput);
    const secondResponse = await second;
    expect(secondResponse.status).toBe("success");

    resolveFirst({
      ...modelResponse("旧 Turn 迟到"),
      actions: [actionCandidate(firstInput.sourceMessageId)],
      memoryCandidates: [memoryCandidate(firstInput.sourceMessageId)],
    });
    const firstResponseValue = await first;

    expect(firstResponseValue.status).toBe("discarded");
    expect(firstResponseValue.canCommit).toBe(false);
    expect(model.calls[0]?.signal?.aborted).toBe(true);
    expect(domains.actionCalls).toHaveLength(0);
    expect(domains.memoryCalls).toHaveLength(0);
    expect(domains.commits).toHaveLength(1);
    expect(domains.commits[0]?.input.sourceMessageId).toBe(secondInput.sourceMessageId);
  });

  test("uses the shared 15 second timeout semantics and classifies timeout", async () => {
    vi.useFakeTimers();
    const model = new FakeModelPort(REMOTE_INFO, async () => new Promise(() => {}));
    const pending = createHarness(model, { fallbackToLocal: false }).respond(input());
    await flushMicrotasks();
    expect(model.calls).toHaveLength(1);

    await vi.advanceTimersByTimeAsync(DEFAULT_COMPANION_PROVIDER_TIMEOUT_MS - 1);
    expect(model.calls[0]?.signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    const response = await pending;

    expect(response).toMatchObject({
      status: "error",
      canCommit: false,
      error: { kind: "timeout" },
      callCounts: { model: 1, external: 1, local: 0, fallback: 0 },
    });
    expect(model.calls[0]?.signal?.aborted).toBe(true);
  });

  test("rejects a missing or malformed model reply without a successful result", async () => {
    const model = new FakeModelPort(REMOTE_INFO, async () => ({ actions: [] }));
    const domains = createDomainSpies();
    const response = await createHarness(model, domains).respond(input());

    expect(response).toMatchObject({
      status: "error",
      canCommit: false,
      text: null,
      error: { kind: "malformed-response" },
      callCounts: { model: 1, external: 1, local: 0, fallback: 0 },
    });
    expect(domains.commits).toHaveLength(0);
  });

  test.each([
    121,
    2_000,
  ])("preserves a safe ordinary reply of %i characters through the Harness", async (length) => {
    const draft = "长".repeat(length);
    const model = new FakeModelPort(REMOTE_INFO, async () => modelResponse(draft));
    const response = await createHarness(model).respond(input());

    expect(response.status).toBe("success");
    expect(response.text).toBe(draft);
    expect(response.actions).toEqual([]);
    expect(response.callCounts).toMatchObject({ model: 1, external: 1 });
  });

  test("fails closed when a direct Model Port reply exceeds the Harness limit", async () => {
    const model = new FakeModelPort(REMOTE_INFO, async () => modelResponse("长".repeat(2_001)));
    const response = await createHarness(model, { fallbackToLocal: false }).respond(input());

    expect(response).toMatchObject({
      status: "error",
      text: null,
      canCommit: false,
      error: { kind: "malformed-response" },
      callCounts: { model: 1, external: 1, local: 0, fallback: 0 },
    });
  });

  test("classifies an ordinary Model Port failure instead of returning success", async () => {
    const model = new FakeModelPort(REMOTE_INFO, async () => {
      throw new CompanionChatProviderError("服务端失败", "server", 503);
    });
    const response = await createHarness(model).respond(input());

    expect(response).toMatchObject({
      status: "error",
      canCommit: false,
      error: { kind: "server", message: "服务端失败", status: 503 },
      callCounts: { model: 1, external: 1, local: 0, fallback: 0 },
    });
  });

  test("performs at most one disclosed local fallback after a remote failure", async () => {
    const remote = new FakeModelPort(REMOTE_INFO, async () => {
      throw new CompanionChatProviderError("暂时不可用", "network");
    });
    const localFallbackInfo: CompanionModelPortInfo = {
      ...LOCAL_INFO,
      disclosure: LOCAL_COMPANION_CHAT_FALLBACK_DISCLOSURE,
    };
    const localFallback = new FakeModelPort(
      localFallbackInfo,
      async () => modelResponse("本地降级回复"),
    );
    const response = await createHarness(remote, {
      localFallbackModelPort: localFallback,
      fallbackToLocal: true,
    }).respond(input());

    expect(response).toMatchObject({
      status: "degraded",
      text: "本地降级回复",
      degraded: true,
      degradedFrom: "network",
      provider: localFallbackInfo,
      providerDisclosure: LOCAL_COMPANION_CHAT_FALLBACK_DISCLOSURE,
      error: { kind: "network" },
      callCounts: { model: 2, external: 1, local: 1, fallback: 1 },
    });
    expect(remote.calls).toHaveLength(1);
    expect(localFallback.calls).toHaveLength(1);
  });

  test("fails closed when the configured fallback is remote and never calls it", async () => {
    const remote = new FakeModelPort(REMOTE_INFO, async () => {
      throw new CompanionChatProviderError("暂时不可用", "network");
    });
    const invalidRemoteFallback = new FakeModelPort(
      REMOTE_INFO,
      async () => modelResponse("不应出现"),
    );

    const response = await createHarness(remote, {
      localFallbackModelPort: invalidRemoteFallback,
      fallbackToLocal: true,
    }).respond(input());

    expect(response.status).toBe("error");
    expect(response.degraded).toBe(false);
    expect(response.degradedFrom).toBe("network");
    expect(response.error).toMatchObject({ kind: "configuration" });
    expect(response.callCounts.external).toBe(1);
    expect(response.callCounts.fallback).toBe(0);
    expect(remote.calls).toHaveLength(1);
    expect(invalidRemoteFallback.calls).toHaveLength(0);
  });

  test("does not call the same remote Port twice when it is wired as fallback", async () => {
    const remote = new FakeModelPort(REMOTE_INFO, async () => {
      throw new CompanionChatProviderError("暂时不可用", "network");
    });

    const response = await createHarness(remote, {
      localFallbackModelPort: remote,
      fallbackToLocal: true,
    }).respond(input());

    expect(response.status).not.toBe("success");
    expect(response.callCounts.external).toBe(1);
    expect(remote.calls).toHaveLength(1);
  });

  test("always uses the explicit fallback disclosure for a normal local Port", async () => {
    const remote = new FakeModelPort(REMOTE_INFO, async () => {
      throw new CompanionChatProviderError("暂时不可用", "network");
    });
    const localFallback = new FakeModelPort(
      LOCAL_INFO,
      async () => modelResponse("本地降级回复"),
    );

    const response = await createHarness(remote, {
      localFallbackModelPort: localFallback,
      fallbackToLocal: true,
    }).respond(input());

    expect(response.status).toBe("degraded");
    expect(response.providerDisclosure).toBe(LOCAL_COMPANION_CHAT_FALLBACK_DISCLOSURE);
    expect(response.callCounts).toMatchObject({ external: 1, local: 1, fallback: 1 });
  });

  test("never starts local fallback for cancellation", async () => {
    const controller = new AbortController();
    const remote = new FakeModelPort(REMOTE_INFO, async () => new Promise(() => {}));
    const localFallback = new FakeModelPort(LOCAL_INFO, async () => modelResponse("不应出现"));
    const pending = createHarness(remote, {
      localFallbackModelPort: localFallback,
    }).respond(input({ signal: controller.signal }));
    await flushMicrotasks();

    controller.abort();
    const response = await pending;
    expect(response.status).toBe("cancelled");
    expect(response.callCounts).toMatchObject({ external: 1, local: 0, fallback: 0 });
    expect(localFallback.calls).toHaveLength(0);
  });

  test("drops malformed or cross-message candidates without invoking domain services", async () => {
    const model = new FakeModelPort(REMOTE_INFO, async () => ({
      replyDraft: "普通回复",
      actions: [
        { sourceMessageId: "other-message", intent: "explicit", type: "wrong" },
        { sourceMessageId: "message-1", intent: "unknown", type: "invalid" },
      ],
      memoryCandidates: [memoryCandidate("other-message")],
    }));
    const domains = createDomainSpies();
    const response = await createHarness(model, domains).respond(input());

    expect(response.status).toBe("success");
    expect(response.actions).toEqual([]);
    expect(response.memory).toMatchObject({
      status: "ignored",
      acceptedCount: 0,
      rejectedCount: 1,
      decisions: [{ status: "rejected", errorCode: "invalid-candidate" }],
    });
    expect(domains.actionCalls).toHaveLength(0);
    expect(domains.memoryCalls).toHaveLength(0);
  });

  test("does not submit a response whose echoed identity belongs to another session", async () => {
    const model = new FakeModelPort(REMOTE_INFO, async () => ({
      ...modelResponse("错 session 的回复"),
      identity: {
        requestId: "request-1",
        sessionId: "other-session",
        sourceMessageId: "message-1",
        userId: "local-user",
        petId: "xiaoju-cat",
      },
      actions: [actionCandidate("message-1")],
    }));
    const domains = createDomainSpies();
    const response = await createHarness(model, domains).respond(input());

    expect(response.status).toBe("discarded");
    expect(response.identity.sessionId).toBe("session-1");
    expect(response.canCommit).toBe(false);
    expect(domains.actionCalls).toHaveLength(0);
    expect(domains.memoryCalls).toHaveLength(0);
    expect(domains.commits).toHaveLength(0);
  });

  test("finalizes Action Domain failure as an honest local reply", async () => {
    const model = new FakeModelPort(REMOTE_INFO, async () => ({
      ...modelResponse("已经完成了。"),
      actions: [actionCandidate("message-1")],
    }));
    const actionService: CompanionActionService = {
      async process() {
        throw new Error("fake domain failure");
      },
    };
    const domains = createDomainSpies();
    const response = await createHarness(model, {
      actionService,
      responseSink: domains.responseSink,
    }).respond(input());

    expect(response).toMatchObject({
      status: "degraded",
      canCommit: true,
      error: { kind: "domain" },
      callCounts: { model: 1, external: 1, local: 0, fallback: 0 },
    });
    expect(response.text).not.toContain("已经完成");
    expect(domains.commits).toHaveLength(1);
  });

  test("retains a completed domain result if cancellation arrives after the write", async () => {
    let releaseAction!: () => void;
    const actionGate = new Promise<void>((resolve) => {
      releaseAction = resolve;
    });
    const model = new FakeModelPort(REMOTE_INFO, async () => ({
      ...modelResponse("动作草稿"),
      actions: [actionCandidate("message-1")],
    }));
    const domains = createDomainSpies();
    const actionService: CompanionActionService = {
      async process(nextInput, candidates, signal) {
        domains.actionCalls.push({ input: nextInput, candidates, signal });
        await actionGate;
        return candidates.map((candidate) => ({
          type: candidate.type,
          status: "succeeded" as const,
        }));
      },
    };
    const controller = new AbortController();
    const harness = createHarness(model, {
      actionService,
      responseSink: domains.responseSink,
    });
    const pending = harness.respond(input({ signal: controller.signal }));
    await flushMicrotasks();
    expect(domains.actionCalls).toHaveLength(1);

    controller.abort();
    releaseAction();
    const response = await pending;

    expect(response.status).toBe("cancelled");
    expect(response.canCommit).toBe(false);
    expect(response.actions).toEqual([{ type: "create_task", status: "succeeded" }]);
    expect(domains.commits).toHaveLength(0);
  });

  test("does not let a superseded async Sink commit the old Turn", async () => {
    let releaseFirstSink!: () => void;
    let sinkEntered!: () => void;
    const firstSinkGate = new Promise<void>((resolve) => {
      releaseFirstSink = resolve;
    });
    const firstSinkStarted = new Promise<void>((resolve) => {
      sinkEntered = resolve;
    });
    const commits: string[] = [];
    const responseSink: CompanionResponseSink = {
      async commit(nextInput, response, guard) {
        if (nextInput.sourceMessageId === "message-1") {
          sinkEntered();
          await firstSinkGate;
        }
        guard.commitIfCurrent(nextInput, response, () => {
          commits.push(`${nextInput.sourceMessageId}:${response.text}`);
        });
      },
    };
    const model = new FakeModelPort(REMOTE_INFO, async (_request, callNumber) =>
      modelResponse(callNumber === 1 ? "旧回复" : "新回复"),
    );
    const harness = createHarness(model, { responseSink });
    const first = harness.respond(input());
    await firstSinkStarted;

    const second = harness.respond(input({
      requestId: "request-2",
      sourceMessageId: "message-2",
      message: "新消息",
    }));
    const secondResponse = await second;
    expect(secondResponse.status).toBe("success");
    expect(commits).toEqual(["message-2:新回复"]);

    releaseFirstSink();
    const firstResponse = await first;
    expect(firstResponse.status).toBe("discarded");
    expect(firstResponse.canCommit).toBe(false);
    expect(firstResponse.committed).toBe(false);
    expect(commits).toEqual(["message-2:新回复"]);
  });

  test("commits a normal synchronous Sink exactly once and reports committed", async () => {
    const model = new FakeModelPort(REMOTE_INFO, async () => modelResponse("正常回复"));
    const domains = createDomainSpies();
    const response = await createHarness(model, {
      responseSink: domains.responseSink,
    }).respond(input());

    expect(response.status).toBe("success");
    expect(response.canCommit).toBe(true);
    expect(response.committed).toBe(true);
    expect(domains.commits).toHaveLength(1);
  });

  test("returns cancelled and prevents a Sink commit when cancel happens while it waits", async () => {
    let releaseSink!: () => void;
    let sinkEntered!: () => void;
    const sinkGate = new Promise<void>((resolve) => {
      releaseSink = resolve;
    });
    const sinkStarted = new Promise<void>((resolve) => {
      sinkEntered = resolve;
    });
    const commits: string[] = [];
    const responseSink: CompanionResponseSink = {
      async commit(nextInput, response, guard) {
        sinkEntered();
        await sinkGate;
        guard.commitIfCurrent(nextInput, response, () => commits.push(`${nextInput.sourceMessageId}:${response.text}`));
      },
    };
    const model = new FakeModelPort(REMOTE_INFO, async () => modelResponse("等待中的回复"));
    const controller = new AbortController();
    const harness = createHarness(model, { responseSink });
    const pending = harness.respond(input({ signal: controller.signal }));
    await sinkStarted;

    controller.abort();
    const response = await pending;
    expect(response.status).toBe("cancelled");
    expect(response.canCommit).toBe(false);
    expect(response.committed).toBe(false);
    expect(commits).toEqual([]);

    releaseSink();
    await flushMicrotasks();
    expect(commits).toEqual([]);
  });

  test("does not sink a late Memory result after cancellation", async () => {
    let releaseMemory!: () => void;
    const memoryGate = new Promise<void>((resolve) => {
      releaseMemory = resolve;
    });
    const domains = createDomainSpies();
    const memoryService: CompanionMemoryService = {
      async process(nextInput, candidates, signal) {
        domains.memoryCalls.push({ input: nextInput, candidates, signal });
        await memoryGate;
        return {
          status: "succeeded",
          acceptedCount: candidates.length,
          rejectedCount: 0,
          decisions: candidates.map((_, index) => ({
            index,
            status: "inserted" as const,
          })),
        };
      },
    };
    const model = new FakeModelPort(REMOTE_INFO, async () => ({
      ...modelResponse("Memory 等待中"),
      memoryCandidates: [memoryCandidate("message-1")],
    }));
    const controller = new AbortController();
    const harness = createHarness(model, {
      memoryService,
      responseSink: domains.responseSink,
    });
    const pending = harness.respond(input({ signal: controller.signal }));
    await flushMicrotasks();
    expect(domains.memoryCalls).toHaveLength(1);

    controller.abort();
    releaseMemory();
    const response = await pending;
    expect(response.status).toBe("cancelled");
    expect(domains.commits).toHaveLength(0);

    await flushMicrotasks();
    expect(domains.commits).toHaveLength(0);
  });

  test("does not call the Model Port when ContextBuilder is cancelled", async () => {
    let releaseBuilder!: () => void;
    const builderGate = new Promise<void>((resolve) => {
      releaseBuilder = resolve;
    });
    const contextBuilder = {
      async build(_input: CompanionInput, signal: AbortSignal) {
        await builderGate;
        if (signal.aborted) throw new Error("context build cancelled");
        return {
          petId: "xiaoju-cat",
          systemInstruction: "safe",
          history: [],
          userInput: "今天还行",
        };
      },
    };
    const controller = new AbortController();
    const model = new FakeModelPort(REMOTE_INFO, async () => modelResponse());
    const pending = createHarness(model, { contextBuilder }).respond(
      input({ signal: controller.signal }),
    );
    await flushMicrotasks();
    controller.abort();
    releaseBuilder();

    const response = await pending;
    expect(response.status).toBe("cancelled");
    expect(response.callCounts.model).toBe(0);
    expect(response.callCounts.external).toBe(0);
    expect(model.calls).toHaveLength(0);
  });

  test("blocks a sensitive remote Turn before any Model Port call", async () => {
    const model = new FakeModelPort(REMOTE_INFO, async () => modelResponse("不应调用"));
    const response = await createHarness(model).respond(input({
      message: "my password is NEVER_SEND_PASSWORD",
    }));

    expect(response.status).toBe("error");
    expect(response.error?.kind).toBe("content-safety");
    expect(response.callCounts).toEqual({ model: 0, external: 0, local: 0, fallback: 0 });
    expect(model.calls).toHaveLength(0);
  });

  test("keeps Memory failure explicit and does not claim normal success", async () => {
    const model = new FakeModelPort(REMOTE_INFO, async () => ({
      ...modelResponse("我先陪你聊着。"),
      memoryCandidates: [memoryCandidate("message-1")],
    }));
    const memoryService: CompanionMemoryService = {
      async process() {
        throw new Error("fake memory failure");
      },
    };
    const response = await createHarness(model, { memoryService }).respond(input());

    expect(response).toMatchObject({
      status: "degraded",
      text: expect.stringContaining("Memory 没有保存成功"),
      canCommit: true,
      memory: {
        status: "failed",
        acceptedCount: 0,
        rejectedCount: 1,
      },
    });
    expect(response.text).toContain("Memory 没有保存成功");
  });

  test("passes the full Turn identity to the Model Port and preserves it in the response", async () => {
    const model = new FakeModelPort(LOCAL_INFO, async () => modelResponse());
    const requested = input({
      requestId: "request-identity",
      sessionId: "session-identity",
      sourceMessageId: "message-identity",
      userId: "user-identity",
      petId: "sleepy-bunny",
    });
    const response = await createHarness(model).respond(requested);

    expect(model.calls[0]?.input).toMatchObject({
      requestId: requested.requestId,
      sessionId: requested.sessionId,
      sourceMessageId: requested.sourceMessageId,
      userId: requested.userId,
      petId: requested.petId,
    });
    expect(response.identity).toEqual({
      requestId: "request-identity",
      sessionId: "session-identity",
      sourceMessageId: "message-identity",
      userId: "user-identity",
      petId: "sleepy-bunny",
    });
  });

  test("cancel(sessionId, requestId) only cancels the matching active Turn", async () => {
    const model = new FakeModelPort(LOCAL_INFO, async () => new Promise(() => {}));
    const harness = createHarness(model, { timeoutMs: 30_000 });
    const pending = harness.respond(input());
    await flushMicrotasks();

    harness.cancel("session-1", "other-request");
    await flushMicrotasks();
    expect(model.calls[0]?.signal?.aborted).toBe(false);
    harness.cancel("session-1", "request-1");
    const response = await pending;

    expect(response.status).toBe("cancelled");
    expect(response.callCounts).toMatchObject({ model: 1, local: 1, external: 0 });
    expect(model.calls[0]?.signal?.aborted).toBe(true);
  });
});
