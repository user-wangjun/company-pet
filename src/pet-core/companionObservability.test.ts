import { describe, expect, test, vi } from "vitest";
import { CompanionChatProviderError } from "./companionChatProvider";
import {
  createCompanionObservationRecorder,
  shouldRecordProviderFallback,
} from "./companionObservability";
import type { CompanionObservability } from "./companionObservability";
import { createCompanionHarness } from "./companionHarness";
import { createInMemoryCompanionTaskRepository } from "./companionActionPipeline";
import type {
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
import type { ProviderAdapter } from "./companionProviderAdapter";
import { createTask, EMPTY_TASK_DATABASE } from "../task-core/taskStore";

const SENTINELS = {
  prompt: "OBS_PROMPT_SENTINEL",
  userMessage: "OBS_USER_MESSAGE_SENTINEL",
  conversation: "OBS_CONVERSATION_SENTINEL",
  memoryContent: "OBS_MEMORY_CONTENT_SENTINEL",
  memoryEvidence: "OBS_MEMORY_EVIDENCE_SENTINEL",
  taskTitle: "OBS_TASK_TITLE_SENTINEL",
  taskNote: "OBS_TASK_NOTE_SENTINEL",
  reminder: "OBS_REMINDER_SENTINEL",
  apiKey: "OBS_API_KEY_SENTINEL",
  authorization: "OBS_AUTHORIZATION_SENTINEL",
  providerBody: "OBS_PROVIDER_BODY_SENTINEL",
  modelReply: "OBS_MODEL_REPLY_SENTINEL",
  observerError: "OBS_OBSERVER_ERROR_SENTINEL",
};

const LOCAL_INFO: CompanionModelPortInfo = {
  kind: "local",
  provider: "Test Local",
  target: "本机",
  disclosure: "本地测试 Provider",
};

function input(overrides: Partial<CompanionInput> = {}): CompanionInput {
  return {
    requestId: "observability-request",
    sessionId: "observability-session",
    sourceMessageId: "observability-message",
    userId: "local-user",
    petId: "xiaoju-cat",
    message: "普通陪伴",
    currentTime: "2026-08-13T12:00:00.000Z",
    timezone: "Asia/Shanghai",
    utcOffsetMinutes: 480,
    source: "chat",
    ...overrides,
  };
}

function localModelPort(response: CompanionModelResponse = { replyDraft: "安全成功回复" }): CompanionModelPort {
  const capabilities = Object.freeze({
    textGeneration: true as const,
    structuredOutput: "none" as const,
    cancellation: true,
    usageMetadata: false,
  });
  const adapter: ProviderAdapter = {
    id: "test-local",
    protocol: "local",
    capabilities,
    info: LOCAL_INFO,
    generate: async () => ({ text: "unused", metadata: { providerId: "test-local" } }),
  };
  const generate = async (_request: HarnessModelRequest): Promise<CompanionModelResponse> => response;
  const resolved: ResolvedCompanionModelTurn = {
    adapter,
    info: LOCAL_INFO,
    capabilities,
    providerProfileId: "test-local",
    protocol: "local",
    generate,
  };
  return {
    info: LOCAL_INFO,
    beginTurn: () => resolved,
    generate,
  };
}

function throwingObservability(): CompanionObservability {
  const error = new Error(SENTINELS.observerError);
  return {
    recordTurn: () => {
      throw error;
    },
    recordProactive: () => {
      throw error;
    },
  };
}

const LOCAL_ACTION_TITLE = "OBS_LOCAL_ACTION_TITLE";

function withLocalActionTarget() {
  return createTask(EMPTY_TASK_DATABASE, {
    title: LOCAL_ACTION_TITLE,
    dueAt: "2026-08-12T07:00:00.000Z",
    schedulePrecision: "datetime",
    remindAt: "2026-08-12T07:00:00.000Z",
  }, "2026-08-11T10:00:00.000Z").database;
}

describe("Companion Harness observability", () => {
  test("does not label confirmation-required domain work as Provider fallback", () => {
    expect(shouldRecordProviderFallback({ degraded: true })).toBe(false);
    expect(shouldRecordProviderFallback({ degraded: true, degradedFrom: "network" })).toBe(true);
    expect(shouldRecordProviderFallback({ degraded: false, degradedFrom: "network" })).toBe(false);
  });

  test("records all local compatibility Action types with only type and status", () => {
    const recorder = createCompanionObservationRecorder();
    recorder.recordTurn({
      requestId: "local-action-allowlist-request",
      providerProfileId: "local",
      protocol: "local",
      latencyMs: 1,
      callCounts: { model: 0, external: 0, local: 0, fallback: 0 },
      actions: [
        { type: "cancel_task", status: "succeeded", payload: "OBS_ACTION_PAYLOAD" } as never,
        { type: "postpone_task", status: "succeeded", title: LOCAL_ACTION_TITLE } as never,
        { type: "reschedule_task", status: "succeeded", reference: "OBS_TASK_REFERENCE" } as never,
      ],
      memory: {
        candidateCount: 0,
        acceptedCount: 0,
        rejectedCount: 0,
        status: "not-requested",
      },
      responseStatus: "success",
    });

    const snapshot = recorder.snapshot();
    expect(snapshot).toEqual([expect.objectContaining({
      actions: [
        { type: "cancel_task", status: "succeeded" },
        { type: "postpone_task", status: "succeeded" },
        { type: "reschedule_task", status: "succeeded" },
      ],
    })]);
    const output = JSON.stringify(snapshot);
    expect(output).not.toContain("OBS_ACTION_PAYLOAD");
    expect(output).not.toContain(LOCAL_ACTION_TITLE);
    expect(output).not.toContain("OBS_TASK_REFERENCE");
  });

  test.each([
    ["cancel_task", "取消任务：OBS_LOCAL_ACTION_TITLE"],
    ["postpone_task", "延期OBS_LOCAL_ACTION_TITLE到明天下午四点"],
    ["reschedule_task", "把OBS_LOCAL_ACTION_TITLE改到明天下午四点"],
  ] as const)("records %s from the real local Harness route", async (expectedType, message) => {
    const recorder = createCompanionObservationRecorder();
    const model = localModelPort();
    const beginTurn = vi.spyOn(model, "beginTurn");
    const observedRepository = createInMemoryCompanionTaskRepository(withLocalActionTarget());
    const baselineRepository = createInMemoryCompanionTaskRepository(withLocalActionTarget());
    const request = input({
      message,
      requestId: `local-${expectedType}-request`,
      sourceMessageId: `local-${expectedType}-message`,
    });

    const baseline = await createCompanionHarness({
      modelPort: localModelPort(),
      taskRepository: baselineRepository,
    }).respond(request);
    const observed = await createCompanionHarness({
      modelPort: model,
      taskRepository: observedRepository,
      observability: recorder,
    }).respond(request);

    expect(observed.status).toBe(baseline.status);
    expect(observed.text).toBe(baseline.text);
    expect(observed.actions).toEqual(expect.arrayContaining([
      expect.objectContaining({ type: expectedType, status: "succeeded" }),
    ]));
    expect(observed.callCounts).toEqual({ model: 0, external: 0, local: 0, fallback: 0 });
    expect(beginTurn).not.toHaveBeenCalled();
    expect(recorder.snapshot()).toEqual([expect.objectContaining({
      kind: "turn",
      actions: [{ type: expectedType, status: "succeeded" }],
      callCounts: { model: 0, external: 0, local: 0, fallback: 0 },
      responseStatus: observed.status,
    })]);
    const observationOutput = JSON.stringify(recorder.snapshot());
    expect(observationOutput).not.toContain(LOCAL_ACTION_TITLE);
    expect(observationOutput).not.toContain("2026-08-12");
  });

  test("emits only the typed allowlist and never stores sensitive sentinels", () => {
    const recorder = createCompanionObservationRecorder();
    const hostileIdentifier = Object.values(SENTINELS).join("|");

    recorder.recordTurn({
      requestId: hostileIdentifier,
      providerProfileId: hostileIdentifier,
      protocol: hostileIdentifier,
      latencyMs: 17.8,
      callCounts: { model: 2, external: 1, local: 1, fallback: 1 },
      actions: [{
        type: hostileIdentifier,
        status: hostileIdentifier,
      }],
      memory: {
        candidateCount: 2,
        acceptedCount: 1,
        rejectedCount: 1,
        status: hostileIdentifier,
      },
      responseStatus: hostileIdentifier,
      errorKind: hostileIdentifier,
    });
    recorder.recordProactive({
      eventType: hostileIdentifier,
      decision: "forwarded",
    });

    const output = JSON.stringify(recorder.snapshot());
    for (const sentinel of Object.values(SENTINELS)) {
      expect(output).not.toContain(sentinel);
    }
    expect(recorder.snapshot()).toEqual([
      expect.objectContaining({
        kind: "turn",
        protocol: "unknown",
        providerProfileId: expect.stringMatching(/^profile-[0-9a-f]{8}$/u),
        requestId: expect.stringMatching(/^request-[0-9a-f]{8}$/u),
        actions: [{ type: "unknown", status: "unknown" }],
        memory: {
          candidateCount: 2,
          acceptedCount: 1,
          rejectedCount: 1,
          status: "unknown",
        },
        responseStatus: "error",
        errorKind: "unknown",
      }),
      { kind: "proactive", eventType: "unknown", decision: "forwarded" },
    ]);
  });

  test("records real Harness turns and proactive events without exposing response text", async () => {
    const recorder = createCompanionObservationRecorder();
    recorder.recordTurn({
      requestId: "opaque-request",
      providerProfileId: "custom-provider",
      protocol: "openai-compatible",
      latencyMs: 4,
      callCounts: { model: 1, external: 1, local: 0, fallback: 0 },
      actions: [{ type: "create_task", status: "succeeded" }],
      memory: {
        candidateCount: 1,
        acceptedCount: 1,
        rejectedCount: 0,
        status: "succeeded",
      },
      responseStatus: "success",
    });
    recorder.recordProactive({ eventType: "TASK_DUE_SOON", decision: "forwarded" });

    const [turn, event] = recorder.snapshot();
    expect(turn).toMatchObject({
      kind: "turn",
      protocol: "openai-compatible",
      actions: [{ type: "create_task", status: "succeeded" }],
    });
    expect(event).toEqual({
      kind: "proactive",
      eventType: "TASK_DUE_SOON",
      decision: "forwarded",
    });
    expect(JSON.stringify(recorder.snapshot())).not.toContain(SENTINELS.modelReply);
  });

  test("is wired to the Harness lifecycle for turns and proactive events", async () => {
    const recorder = createCompanionObservationRecorder();
    const info: CompanionModelPortInfo = {
      kind: "local",
      provider: "本地 Provider",
      target: "本机",
      disclosure: "本地",
    };
    const capabilities = Object.freeze({
      textGeneration: true as const,
      structuredOutput: "none" as const,
      cancellation: true,
      usageMetadata: false,
    });
    const adapter: ProviderAdapter = {
      id: "local",
      protocol: "local",
      capabilities,
      info,
      generate: async () => ({ text: "不应走 Adapter", metadata: { providerId: "local" } }),
    };
    const resolved: ResolvedCompanionModelTurn = {
      adapter,
      info,
      capabilities,
      providerProfileId: "local",
      protocol: "local",
      generate: async (_request: HarnessModelRequest): Promise<CompanionModelResponse> => ({
        replyDraft: "安全本地回复",
      }),
    };
    const modelPort: CompanionModelPort = {
      info,
      beginTurn: () => resolved,
      generate: resolved.generate,
    };
    const input: CompanionInput = {
      requestId: "runtime-observation-request",
      sessionId: "runtime-observation-session",
      sourceMessageId: "runtime-observation-message",
      userId: "local-user",
      petId: "xiaoju-cat",
      message: "普通陪伴",
      currentTime: "2026-08-13T12:00:00.000Z",
      timezone: "Asia/Shanghai",
      utcOffsetMinutes: 480,
      source: "chat",
    };

    const response = await createCompanionHarness({
      modelPort,
      observability: recorder,
    }).respond(input);
    expect(response.status).toBe("success");
    const snapshot = recorder.snapshot();
    expect(snapshot).toHaveLength(1);
    expect(snapshot[0]).toMatchObject({
      kind: "turn",
      protocol: "local",
      callCounts: { model: 1, external: 0, local: 1, fallback: 0 },
      responseStatus: "success",
    });
  });

  test("does not reject a successful response when recordTurn throws", async () => {
    const response = await createCompanionHarness({
      modelPort: localModelPort({ replyDraft: "成功文案不应被观测器改写" }),
      observability: throwingObservability(),
    }).respond(input());

    expect(response).toMatchObject({
      status: "success",
      text: "成功文案不应被观测器改写",
    });
    expect(JSON.stringify(response)).not.toContain(SENTINELS.observerError);
  });

  test("keeps a committed ResponseSink at exactly one commit when recordTurn throws", async () => {
    const commits: string[] = [];
    const responseSink: CompanionResponseSink = {
      commit(nextInput, response, guard) {
        guard.commitIfCurrent(nextInput, response, () => {
          commits.push(response.text ?? "");
        });
      },
    };

    const response = await createCompanionHarness({
      modelPort: localModelPort(),
      responseSink,
      observability: throwingObservability(),
    }).respond(input());

    expect(response.status).toBe("success");
    expect(response.committed).toBe(true);
    expect(commits).toEqual(["安全成功回复"]);
  });

  test("keeps successful Action and Memory facts and final prose unchanged", async () => {
    const actionService: CompanionActionService = {
      process: vi.fn(async (_input: CompanionInput, candidates: readonly CompanionActionCandidate[]) => candidates.map((candidate) => ({
        type: candidate.type,
        status: "succeeded" as const,
      }))),
    };
    const actionInput = input({
      requestId: "action-observation-request",
      sourceMessageId: "action-observation-message",
      message: "明天下午三点提醒我交报告",
    });
    const actionBaseline = await createCompanionHarness({
      modelPort: localModelPort(),
      actionService,
    }).respond(actionInput);
    const actionObserved = await createCompanionHarness({
      modelPort: localModelPort(),
      actionService,
      observability: throwingObservability(),
    }).respond(actionInput);

    expect(actionObserved).toMatchObject({
      status: actionBaseline.status,
      text: actionBaseline.text,
      actions: actionBaseline.actions,
    });
    expect(actionObserved.text).toContain("提醒");
    expect(actionObserved.actions).toEqual([{ type: "create_reminder", status: "succeeded" }]);

    const memoryService: CompanionMemoryService = {
      process: vi.fn(async (_input: CompanionInput, candidates: readonly MemoryCandidate[]) => ({
        status: "succeeded" as const,
        acceptedCount: candidates.length,
        rejectedCount: 0,
        decisions: candidates.map((_, index) => ({ index, status: "inserted" as const })),
      })),
    };
    const memoryInput = input({
      requestId: "memory-observation-request",
      sourceMessageId: "memory-observation-message",
      message: "我喜欢桂花茶，请记住",
    });
    const memoryBaseline = await createCompanionHarness({
      modelPort: localModelPort(),
      memoryService,
    }).respond(memoryInput);
    const memoryObserved = await createCompanionHarness({
      modelPort: localModelPort(),
      memoryService,
      observability: throwingObservability(),
    }).respond(memoryInput);

    expect(memoryObserved).toMatchObject({
      status: memoryBaseline.status,
      text: memoryBaseline.text,
      memory: memoryBaseline.memory,
    });
    expect(memoryObserved.text).toContain("记住");
    expect(JSON.stringify(memoryObserved)).not.toContain(SENTINELS.observerError);
  });

  test("does not cover a Provider or domain failure with an observation failure", async () => {
    const provider: CompanionModelPort = {
      ...localModelPort(),
      info: { ...LOCAL_INFO, kind: "remote", provider: "Test Remote" },
      beginTurn: () => {
        throw new CompanionChatProviderError("provider failure", "network");
      },
    };
    const providerResponse = await createCompanionHarness({
      modelPort: provider,
      observability: throwingObservability(),
    }).respond(input());
    expect(providerResponse.status).toBe("error");
    expect(providerResponse.error?.kind).toBe("network");
    expect(JSON.stringify(providerResponse)).not.toContain(SENTINELS.observerError);

    const domainService: CompanionActionService = {
      process: vi.fn(async () => {
        throw new Error("domain failure");
      }),
    };
    const domainResponse = await createCompanionHarness({
      modelPort: localModelPort(),
      actionService: domainService,
      observability: throwingObservability(),
    }).respond(input({
      requestId: "domain-observation-request",
      sourceMessageId: "domain-observation-message",
      message: "明天下午三点提醒我交报告",
    }));
    expect(domainResponse.status).toBe("degraded");
    expect(domainResponse.actions).toEqual([{
      type: "create_reminder",
      status: "failed",
      errorCode: "action-service-threw",
    }]);
    expect(domainResponse.text).not.toContain("已创建");
  });

  test("keeps proactive delivery successful and at-most-once when recordProactive throws", async () => {
    const service = { handleEvent: vi.fn(async () => undefined) };
    const harness = createCompanionHarness({
      modelPort: localModelPort(),
      proactiveEventService: service,
      observability: throwingObservability(),
    });

    await expect(harness.handleEvent({
      id: "observability-event-success",
      type: "TASK_DUE_SOON",
      taskId: "opaque-task",
      minutesLeft: 5,
    })).resolves.toBeUndefined();
    expect(service.handleEvent).toHaveBeenCalledTimes(1);
  });

  test("isolates observer failures in invalid, missing-service, and service-error event branches", async () => {
    const invalidHarness = createCompanionHarness({
      modelPort: localModelPort(),
      observability: throwingObservability(),
    });
    await expect(invalidHarness.handleEvent({ id: "invalid", type: "NOT_ALLOWED" } as never))
      .resolves.toBeUndefined();

    const missingServiceHarness = createCompanionHarness({
      modelPort: localModelPort(),
      observability: throwingObservability(),
    });
    await expect(missingServiceHarness.handleEvent({
      id: "missing-service",
      type: "TASK_DUE_SOON",
      taskId: "opaque-task",
      minutesLeft: 1,
    })).resolves.toBeUndefined();

    const failingService = {
      handleEvent: vi.fn(async () => {
        throw new Error("service failure");
      }),
    };
    const failingServiceHarness = createCompanionHarness({
      modelPort: localModelPort(),
      proactiveEventService: failingService,
      observability: throwingObservability(),
    });
    await expect(failingServiceHarness.handleEvent({
      id: "service-error",
      type: "TASK_DUE_SOON",
      taskId: "opaque-task",
      minutesLeft: 1,
    })).resolves.toBeUndefined();
    expect(failingService.handleEvent).toHaveBeenCalledTimes(1);
  });
});
