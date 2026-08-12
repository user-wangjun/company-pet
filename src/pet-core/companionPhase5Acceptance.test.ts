import { describe, expect, test } from "vitest";
import {
  createCompanionHarness,
} from "./companionHarness";
import {
  createCompanionMemoryRepository,
  type MemoryRepository,
} from "./companionMemory";
import {
  CompanionMemoryPolicy,
} from "./companionMemoryPolicy";
import type {
  ActionCandidate,
  CompanionActionService,
  CompanionInput,
  CompanionMemoryConfirmationVerifier,
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
import type { ProviderAdapter } from "./companionProviderAdapter";

const REMOTE_INFO: CompanionModelPortInfo = {
  kind: "remote",
  provider: "Phase 5 Fake Remote",
  target: "https://phase5.example.test",
  disclosure: "远程模式：本轮请求由已配置的远程 Provider 处理。",
};

const NOW = "2026-08-12T12:00:00.000Z";

function input(overrides: Partial<CompanionInput> = {}): CompanionInput {
  return {
    requestId: "request-1",
    sessionId: "session-1",
    sourceMessageId: "message-1",
    userId: "local-user",
    petId: "xiaoju-cat",
    message: "普通聊天",
    currentTime: NOW,
    timezone: "UTC",
    utcOffsetMinutes: 0,
    source: "chat",
    ...overrides,
  };
}

function candidate(overrides: Partial<MemoryCandidate> = {}): MemoryCandidate {
  return {
    scope: "global",
    type: "preference",
    category: "preference",
    lifetime: "stable",
    content: "用户喜欢桂花茶",
    source: "inferred",
    evidence: "模型候选证据",
    sourceMessageId: "message-1",
    confidence: 1,
    importance: 1,
    explicitness: "inferred",
    confirmationStatus: "requires_confirmation",
    expiresAt: null,
    requiresConfirmation: true,
    confirmed: false,
    ...overrides,
  };
}

function confirmedCandidate(
  sourceMessageId: string,
  overrides: Partial<MemoryCandidate> = {},
): MemoryCandidate {
  return candidate({
    sourceMessageId,
    source: "confirmed",
    confirmationStatus: "confirmed",
    requiresConfirmation: false,
    confirmed: true,
    ...overrides,
  });
}

type ModelHandler = (request: HarnessModelRequest) => Promise<CompanionModelResponse>;

class FakeModelPort implements CompanionModelPort {
  readonly calls: HarnessModelRequest[] = [];
  beginTurns = 0;

  constructor(private readonly handler: ModelHandler) {}

  readonly info = REMOTE_INFO;

  beginTurn(): ResolvedCompanionModelTurn {
    this.beginTurns += 1;
    const capabilities = Object.freeze({
      textGeneration: true as const,
      structuredOutput: "none" as const,
      cancellation: true,
      usageMetadata: false,
    });
    const adapter: ProviderAdapter = {
      id: REMOTE_INFO.provider,
      protocol: "openai-compatible",
      capabilities,
      info: REMOTE_INFO,
      generate: async () => ({
        text: "fake",
        metadata: { providerId: REMOTE_INFO.provider },
      }),
    };
    return {
      adapter,
      info: REMOTE_INFO,
      capabilities,
      generate: async (request) => {
        this.calls.push(request);
        return this.handler(request);
      },
    };
  }

  async generate(request: HarnessModelRequest): Promise<CompanionModelResponse> {
    this.calls.push(request);
    return this.handler(request);
  }
}

function sink(commits: Array<{ status: string; text: string | null }>): CompanionResponseSink {
  return {
    commit(nextInput, response, guard) {
      guard.commitIfCurrent(nextInput, response, () => {
        commits.push({ status: response.status, text: response.text });
      });
    },
  };
}

function verifier(): CompanionMemoryConfirmationVerifier {
  return {
    verify: (nextInput, nextCandidate, candidateId) => ({
      candidateId,
      sourceMessageId: nextCandidate.sourceMessageId,
      confirmationMessageId: nextInput.sourceMessageId,
      sessionId: nextInput.sessionId,
      petId: nextInput.petId,
      status: "confirmed",
    }),
  };
}

function modelCandidate(request: HarnessModelRequest, overrides: Partial<MemoryCandidate> = {}) {
  return candidate({
    sourceMessageId: request.input.sourceMessageId,
    ...overrides,
  });
}

describe("Companion Harness Phase 5 acceptance", () => {
  test("handles explicit local memory with zero Provider begin/generate/external calls", async () => {
    const model = new FakeModelPort(async () => ({ replyDraft: "不应调用模型" }));
    const repository = createCompanionMemoryRepository({ now: () => Date.parse(NOW) });
    const commits: Array<{ status: string; text: string | null }> = [];
    const response = await createCompanionHarness({
      modelPort: model,
      memoryRepository: repository,
      responseSink: sink(commits),
    }).respond(input({
      message: "我喜欢桂花茶，请记住",
      sourceMessageId: "message-explicit",
    }));

    expect(response).toMatchObject({
      status: "success",
      text: "已经记住了。",
      committed: true,
      callCounts: { model: 0, external: 0, local: 0, fallback: 0 },
      memory: {
        status: "succeeded",
        acceptedCount: 1,
        decisions: [{ status: "inserted", scope: "global", type: "preference" }],
      },
    });
    expect(model.calls).toHaveLength(0);
    expect(model.beginTurns).toBe(0);
    expect(repository.list()).toHaveLength(1);
    expect(commits).toHaveLength(1);
  });

  test("does not let a model-created high-confidence candidate save an ordinary emotion", async () => {
    const model = new FakeModelPort(async (request) => ({
      replyDraft: "已经记住了。",
      memoryCandidates: [modelCandidate(request, {
        source: "explicit",
        explicitness: "explicit",
        confirmationStatus: "confirmed",
        requiresConfirmation: false,
        confirmed: true,
        content: "用户是一个永远积极的人",
      })],
    }));
    const repository = createCompanionMemoryRepository({ now: () => Date.parse(NOW) });
    const response = await createCompanionHarness({
      modelPort: model,
      memoryRepository: repository,
    }).respond(input({ message: "我今天好累" }));

    expect(response).toMatchObject({
      status: "success",
      callCounts: { model: 1, external: 1, local: 0, fallback: 0 },
      memory: {
        status: "ignored",
        acceptedCount: 0,
        decisions: [{ status: "confirmation_required" }],
      },
    });
    expect(response.text).toContain("还没有保存");
    expect(response.text).not.toContain("已经记住了");
    expect(repository.list()).toEqual([]);
  });

  test.each([0, 1, 4])("keeps one remote model call for %i memory candidates", async (count) => {
    const model = new FakeModelPort(async (request) => ({
      replyDraft: "普通回复",
      memoryCandidates: Array.from({ length: count }, (_, index) => modelCandidate(request, {
        content: `候选-${index}`,
      })),
    }));
    const response = await createCompanionHarness({
      modelPort: model,
      memoryRepository: createCompanionMemoryRepository({ now: () => Date.parse(NOW) }),
    }).respond(input({ requestId: `request-${count}`, sourceMessageId: `message-${count}` }));

    expect(model.calls).toHaveLength(1);
    expect(model.beginTurns).toBe(1);
    expect(response.callCounts).toMatchObject({ model: 1, external: 1 });
  });

  test("drops an invalid candidate without a second Provider request", async () => {
    const model = new FakeModelPort(async (request) => ({
      replyDraft: "普通回复",
      memoryCandidates: [
        { ...modelCandidate(request), unknownField: "drop" } as unknown as MemoryCandidate,
        modelCandidate(request, { content: "第二个候选" }),
      ],
    }));
    const response = await createCompanionHarness({
      modelPort: model,
      memoryRepository: createCompanionMemoryRepository({ now: () => Date.parse(NOW) }),
    }).respond(input());

    expect(model.calls).toHaveLength(1);
    expect(response.memory.decisions).toEqual([
      expect.objectContaining({ index: 0, status: "rejected", errorCode: "invalid-candidate" }),
      expect.objectContaining({ index: 1, status: "confirmation_required" }),
    ]);
  });

  test("does not replace a successful Action with a Memory failure and uses honest final text", async () => {
    const model = new FakeModelPort(async (request) => ({
      replyDraft: "都已经完成了。",
      actions: [{
        sourceMessageId: request.input.sourceMessageId,
        intent: "explicit",
        type: "create_task",
        payload: { title: "买菜" },
      } as ActionCandidate],
      memoryCandidates: [modelCandidate(request)],
    }));
    const actionService: CompanionActionService = {
      process: async (_input, actions) => actions.map((action) => ({
        type: action.type,
        status: "succeeded" as const,
      })),
    };
    const memoryService: CompanionMemoryService = {
      process: async (_input, candidates) => ({
        status: "failed",
        acceptedCount: 0,
        rejectedCount: candidates.length,
        decisions: candidates.map((_, index) => ({
          index,
          status: "failed" as const,
          errorCode: "memory-save-failed",
        })),
        errorCode: "memory-save-failed",
      }),
    };
    const response = await createCompanionHarness({
      modelPort: model,
      actionService,
      memoryService,
    }).respond(input());

    expect(response).toMatchObject({
      status: "degraded",
      actions: [{ type: "create_task", status: "succeeded" }],
      memory: { status: "failed" },
    });
    expect(response.text).toContain("已经为你创建");
    expect(response.text).toContain("Memory 没有保存成功");
    expect(response.text).not.toContain("都已经完成");
  });

  test("keeps a write-confirmed Memory fact after late abort, suppresses UI, and retries as duplicate", async () => {
    const controller = new AbortController();
    const repository = createCompanionMemoryRepository({ now: () => Date.parse(NOW) });
    const policy = new CompanionMemoryPolicy({
      repository,
      now: () => Date.parse(NOW),
      confirmationVerifier: verifier(),
    });
    let model!: FakeModelPort;
    const memoryService: CompanionMemoryService = {
      process: async (nextInput, candidates, signal) => {
        const result = await policy.process(nextInput, candidates, signal);
        controller.abort();
        return result;
      },
    };
    model = new FakeModelPort(async (request) => ({
      replyDraft: "记住了",
      memoryCandidates: [confirmedCandidate(request.input.sourceMessageId)],
    }));
    const commits: Array<{ status: string; text: string | null }> = [];
    const harness = createCompanionHarness({
      modelPort: model,
      memoryService,
      responseSink: sink(commits),
    });
    const first = await harness.respond(input({ signal: controller.signal }));

    expect(first).toMatchObject({
      status: "cancelled",
      committed: false,
      memory: { status: "succeeded", acceptedCount: 1 },
      callCounts: { model: 1, external: 1 },
    });
    expect(commits).toHaveLength(0);
    expect(repository.list()).toHaveLength(1);

    const retry = await harness.respond(input({
      requestId: "request-retry",
      sourceMessageId: "message-retry",
      message: "再次确认",
    }));
    expect(retry).toMatchObject({
      status: "success",
      memory: {
        status: "ignored",
        decisions: [{ status: "duplicate" }],
      },
    });
    expect(repository.list()).toHaveLength(1);
    expect(model.calls).toHaveLength(2);
  });

  test("keeps a write failure failed when abort arrives at the same boundary", async () => {
    const controller = new AbortController();
    const base = createCompanionMemoryRepository({ now: () => Date.parse(NOW) });
    const failingRepository: MemoryRepository = {
      ...base,
      save: () => null,
    };
    const policy = new CompanionMemoryPolicy({
      repository: failingRepository,
      now: () => Date.parse(NOW),
      confirmationVerifier: verifier(),
    });
    const model = new FakeModelPort(async (request) => ({
      replyDraft: "记住了",
      memoryCandidates: [confirmedCandidate(request.input.sourceMessageId)],
    }));
    const memoryService: CompanionMemoryService = {
      process: async (nextInput, candidates, signal) => {
        const result = await policy.process(nextInput, candidates, signal);
        controller.abort();
        return result;
      },
    };
    const commits: Array<{ status: string; text: string | null }> = [];
    const response = await createCompanionHarness({
      modelPort: model,
      memoryService,
      responseSink: sink(commits),
    }).respond(input({ signal: controller.signal }));

    expect(response).toMatchObject({
      status: "cancelled",
      committed: false,
      memory: { status: "failed", acceptedCount: 0 },
    });
    expect(commits).toHaveLength(0);
    expect(base.list()).toEqual([]);
  });
});
