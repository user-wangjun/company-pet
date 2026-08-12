import {
  CompanionChatProviderError,
  DEFAULT_COMPANION_PROVIDER_TIMEOUT_MS,
} from "./companionChatProvider";
import type { CompanionChatProviderErrorKind } from "./companionChatProvider";
import {
  LOCAL_COMPANION_CHAT_FALLBACK_DISCLOSURE,
  shouldFallbackToLocalCompanion,
} from "./companionChatRuntime";
import type {
  CompanionCallCounts,
  CompanionHarness,
  CompanionHarnessDependencies,
  CompanionHarnessError,
  CompanionEvent,
  CompanionInput,
  CompanionModelResponse,
  CompanionResponse,
  CompanionResponseStatus,
  CompanionResponseCommitGuard,
  CompanionTurnIdentity,
  CompanionActionCandidate,
  ActionExecutionResult,
  MemoryCandidate,
  MemoryPolicyResult,
  CompanionProactivePreferenceExecutionResult,
} from "./companionHarnessTypes";
import { parseCompanionEvent } from "./companionProactiveEvent";
import type {
  CompanionModelPortInfo,
  HarnessModelRequest,
  ResolvedCompanionModelTurn,
} from "./companionModelPort";
import {
  containsSensitiveCompanionText,
  REMOTE_SENSITIVE_INPUT_REPLY,
} from "./companionPrivacy";
import {
  CompanionContextPrivacyError,
  CompanionContextTrustError,
  assembleCompanionContext,
  filterCompanionContextForRemote,
} from "./companionContext";
import { CompanionContextBudgetError } from "./companionContextBudget";
import {
  normalizeCompanionActionCandidate,
  normalizeCompanionMemoryCandidate,
} from "./companionModelCodec";
import { createCompanionMemoryRepository } from "./companionMemory";
import { createCompanionMemoryService } from "./companionMemoryPolicy";
import {
  buildLocalRequestHints,
  createCompanionActionService,
} from "./companionActionPipeline";
import { finalizeCompanionResponse } from "./companionResponseFinalizer";

const DEFAULT_DOMAIN_FAILURE_MESSAGE = "这次操作没有完成，请稍后再试。";
const DEFAULT_INVALID_INPUT_MESSAGE = "这次消息还没有准备好，请再试一次。";
const DEFAULT_STALE_MESSAGE = "这次回复已经过期，不会继续提交。";
const DEFAULT_CANCELLED_MESSAGE = "这次回复已停止。";
const DEFAULT_MALFORMED_RESPONSE_MESSAGE = "聊天服务返回了无法识别的回复。";
const MAX_REPLY_DRAFT_LENGTH = 2_000;

type TurnInvalidationReason = "cancelled" | "superseded";

type ActiveTurn = {
  identity: CompanionTurnIdentity;
  input: CompanionInput;
  controller: AbortController;
  primaryTurn: ResolvedCompanionModelTurn | null;
  providerInfo: CompanionModelPortInfo;
  active: boolean;
  reason: TurnInvalidationReason | null;
  fallbackAttempted: boolean;
};

type ModelAttemptResult =
  | { kind: "response"; value: unknown }
  | { kind: "error"; error: CompanionChatProviderError };

type ModelDecodeResult =
  | { kind: "response"; value: CompanionModelResponse }
  | { kind: "error"; error: CompanionChatProviderError }
  | { kind: "stale" };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isInputSource(value: unknown): value is CompanionInput["source"] {
  return value === "chat" || value === "quick_input";
}

function createIdentity(input: CompanionInput): CompanionTurnIdentity {
  return {
    requestId: input.requestId,
    sessionId: input.sessionId,
    sourceMessageId: input.sourceMessageId,
    userId: input.userId,
    petId: input.petId,
  };
}

function sameIdentity(
  left: CompanionTurnIdentity,
  right: CompanionTurnIdentity,
): boolean {
  return left.requestId === right.requestId
    && left.sessionId === right.sessionId
    && left.sourceMessageId === right.sourceMessageId
    && left.userId === right.userId
    && left.petId === right.petId;
}

function validateInput(input: CompanionInput): string | null {
  const requiredStrings: Array<[string, unknown]> = [
    ["requestId", input.requestId],
    ["sessionId", input.sessionId],
    ["sourceMessageId", input.sourceMessageId],
    ["userId", input.userId],
    ["petId", input.petId],
    ["message", input.message],
    ["currentTime", input.currentTime],
    ["timezone", input.timezone],
  ];
  const missing = requiredStrings.find(([, value]) => !nonEmptyString(value));
  if (missing) return `${missing[0]} is required`;
  if (!Number.isFinite(input.utcOffsetMinutes)) return "utcOffsetMinutes is invalid";
  if (!Number.isFinite(Date.parse(input.currentTime))) return "currentTime is invalid";
  if (!isInputSource(input.source)) return "source is invalid";
  return null;
}

function emptyCallCounts(): CompanionCallCounts {
  return { model: 0, external: 0, local: 0, fallback: 0 };
}

function defaultContext(input: CompanionInput) {
  return {
    petId: input.petId,
    systemInstruction: "",
    history: [],
    userInput: input.message,
  };
}

function providerInfoWithFallbackDisclosure(
  resolvedTurn: ResolvedCompanionModelTurn,
  isFallback: boolean,
): CompanionModelPortInfo {
  if (!isFallback || resolvedTurn.info.kind !== "local") return resolvedTurn.info;
  return {
    ...resolvedTurn.info,
    disclosure: LOCAL_COMPANION_CHAT_FALLBACK_DISCLOSURE,
  };
}

function normalizeProviderError(error: unknown): CompanionChatProviderError {
  if (error instanceof CompanionChatProviderError) return error;
  return new CompanionChatProviderError(
    "聊天服务暂时没接上，稍后再试。",
    "network",
  );
}

function malformedResponseError(): CompanionChatProviderError {
  return new CompanionChatProviderError(
    DEFAULT_MALFORMED_RESPONSE_MESSAGE,
    "malformed-response",
  );
}

function cancelledProviderError(): CompanionChatProviderError {
  return new CompanionChatProviderError(DEFAULT_CANCELLED_MESSAGE, "cancelled");
}

function timeoutProviderError(): CompanionChatProviderError {
  return new CompanionChatProviderError(
    "聊天服务响应超时，稍后再试。",
    "timeout",
  );
}

function remoteCallLimitError(): CompanionChatProviderError {
  return new CompanionChatProviderError(
    "本轮远程调用已达到上限，未继续发起远程请求。",
    "configuration",
  );
}

function invalidLocalFallbackError(): CompanionChatProviderError {
  return new CompanionChatProviderError(
    "本地降级配置无效，未继续发起远程请求。",
    "configuration",
  );
}

function contextBuildError(error: unknown): CompanionHarnessError {
  if (error instanceof CompanionContextPrivacyError) {
    return {
      kind: "content-safety",
      message: REMOTE_SENSITIVE_INPUT_REPLY,
    };
  }
  if (
    error instanceof CompanionContextTrustError
    || error instanceof CompanionContextBudgetError
  ) {
    return {
      kind: "configuration",
      message: "远程模型请求配置无效，未发送请求。",
    };
  }
  return domainError();
}

function domainError(message = DEFAULT_DOMAIN_FAILURE_MESSAGE): CompanionHarnessError {
  return { kind: "domain", message };
}

function hasValidIdentity(value: unknown): value is CompanionTurnIdentity {
  return isRecord(value)
    && nonEmptyString(value.requestId)
    && nonEmptyString(value.sessionId)
    && nonEmptyString(value.sourceMessageId)
    && nonEmptyString(value.userId)
    && nonEmptyString(value.petId);
}

function decodeModelResponse(
  raw: unknown,
  identity: CompanionTurnIdentity,
): ModelDecodeResult {
  if (!isRecord(raw) || !nonEmptyString(raw.replyDraft)) {
    return { kind: "error", error: malformedResponseError() };
  }
  if (Array.from(raw.replyDraft).length > MAX_REPLY_DRAFT_LENGTH) {
    return { kind: "error", error: malformedResponseError() };
  }
  if (raw.identity !== undefined) {
    if (!hasValidIdentity(raw.identity) || !sameIdentity(raw.identity, identity)) {
      return { kind: "stale" };
    }
  }
  if (raw.actions !== undefined && !Array.isArray(raw.actions)) {
    return { kind: "error", error: malformedResponseError() };
  }
  if (raw.memoryCandidates !== undefined && !Array.isArray(raw.memoryCandidates)) {
    return { kind: "error", error: malformedResponseError() };
  }

  const actions = (raw.actions ?? [])
    .map((candidate) => normalizeCompanionActionCandidate(candidate, identity.sourceMessageId))
    .filter((candidate): candidate is NonNullable<typeof candidate> => candidate !== null);
  const candidateValues = (raw.memoryCandidates ?? []).slice(0, 4);
  const normalizedMemoryCandidates = candidateValues.map((candidate, index) => ({
    index: Array.isArray(raw.memoryCandidateIndexes)
      && Number.isInteger(raw.memoryCandidateIndexes[index])
      && raw.memoryCandidateIndexes[index] >= 0
      && raw.memoryCandidateIndexes[index] < 4
      ? raw.memoryCandidateIndexes[index]
      : index,
    candidate: normalizeCompanionMemoryCandidate(candidate, {
      mode: "json_object",
      sourceMessageId: identity.sourceMessageId,
      petId: identity.petId,
    }),
  }));
  const memoryCandidates = normalizedMemoryCandidates
    .map(({ candidate }) => candidate)
    .filter((candidate): candidate is MemoryCandidate => candidate !== null);
  const invalidMemoryCandidateIndexes = normalizedMemoryCandidates
    .filter(({ candidate: normalized }) => normalized === null)
    .map(({ index }) => index);
  const predecodedInvalidIndexes = Array.isArray(raw.invalidMemoryCandidateIndexes)
    ? raw.invalidMemoryCandidateIndexes.filter((index): index is number =>
        Number.isInteger(index) && index >= 0 && index < 4,
      )
    : [];
  const allInvalidMemoryCandidateIndexes = [...new Set([
    ...predecodedInvalidIndexes,
    ...invalidMemoryCandidateIndexes,
  ])].sort((left, right) => left - right);

  return {
    kind: "response",
    value: {
      replyDraft: raw.replyDraft.trim(),
      ...(actions.length ? { actions } : {}),
      ...(memoryCandidates.length ? { memoryCandidates } : {}),
      ...(allInvalidMemoryCandidateIndexes.length > 0
        ? {
            invalidMemoryCandidateCount: allInvalidMemoryCandidateIndexes.length,
            invalidMemoryCandidateIndexes: allInvalidMemoryCandidateIndexes,
          }
        : {}),
      ...(memoryCandidates.length > 0
        ? {
            memoryCandidateIndexes: normalizedMemoryCandidates
              .filter(({ candidate: normalized }) => normalized !== null)
              .map(({ index }) => index),
          }
        : {}),
      ...(isRecord(raw.metadata) && nonEmptyString(raw.metadata.provider)
        ? {
            metadata: {
              provider: raw.metadata.provider,
              ...(nonEmptyString(raw.metadata.model)
                ? { model: raw.metadata.model }
                : {}),
            },
          }
        : {}),
    },
  };
}

function createMemoryResult(): MemoryPolicyResult {
  return {
    status: "not-requested",
    acceptedCount: 0,
    rejectedCount: 0,
    decisions: [],
  };
}

function cancelledMemoryResult(candidateCount: number): MemoryPolicyResult {
  return {
    status: "cancelled",
    acceptedCount: 0,
    rejectedCount: candidateCount,
    decisions: Array.from({ length: candidateCount }, (_, index) => ({
      index,
      status: "cancelled" as const,
      errorCode: "turn-invalidated",
    })),
    errorCode: "turn-invalidated",
  };
}

function hasActionFailure(results: readonly ActionExecutionResult[]): boolean {
  return results.some((result) => result.status !== "succeeded");
}

function responseStatusForMemory(
  memory: MemoryPolicyResult,
): CompanionResponseStatus {
  return memory.status === "failed" ? "degraded" : "success";
}

function mergeMemoryPolicyResults(
  rejectedResult: MemoryPolicyResult,
  processedResult: MemoryPolicyResult,
  processedCandidateIndexes: readonly number[] | undefined,
): MemoryPolicyResult {
  const remappedDecisions = processedResult.decisions.map((decision) => ({
    ...decision,
    index: processedCandidateIndexes?.[decision.index] ?? decision.index,
  }));
  const decisions = [...rejectedResult.decisions, ...remappedDecisions]
    .sort((left, right) => left.index - right.index);
  const status = rejectedResult.status === "failed" || processedResult.status === "failed"
    ? "failed"
    : rejectedResult.status === "cancelled" || processedResult.status === "cancelled"
    ? "cancelled"
    : processedResult.acceptedCount > 0 || processedResult.status === "succeeded"
    ? "succeeded"
    : "ignored";

  return {
    status,
    acceptedCount: processedResult.acceptedCount,
    rejectedCount: rejectedResult.rejectedCount + processedResult.rejectedCount,
    decisions,
    ...(processedResult.errorCode ?? rejectedResult.errorCode
      ? { errorCode: processedResult.errorCode ?? rejectedResult.errorCode }
      : {}),
  };
}

export class CompanionHarnessImpl implements CompanionHarness {
  private readonly activeTurns = new Map<string, ActiveTurn>();
  private readonly timeoutMs: number;
  private readonly dependencies: CompanionHarnessDependencies;

  constructor(dependencies: CompanionHarnessDependencies) {
    this.dependencies = {
      ...dependencies,
      actionService: dependencies.actionService
        ?? createCompanionActionService(dependencies.taskRepository),
      memoryService: dependencies.memoryService
        ?? createCompanionMemoryService(
          dependencies.memoryRepository ?? createCompanionMemoryRepository(),
          dependencies.memoryConfirmationVerifier
            ? { confirmationVerifier: dependencies.memoryConfirmationVerifier }
            : {},
        ),
    };
    this.timeoutMs = Math.max(
      1,
      dependencies.timeoutMs ?? DEFAULT_COMPANION_PROVIDER_TIMEOUT_MS,
    );
  }

  cancel(sessionId: string, requestId?: string): void {
    const turn = this.activeTurns.get(sessionId);
    if (!turn || (requestId !== undefined && turn.identity.requestId !== requestId)) return;
    this.invalidateTurn(turn, "cancelled");
    this.activeTurns.delete(sessionId);
  }

  /**
   * Proactive events are a separate local-expression path. They never create
   * a chat Turn, build remote Context, invoke ModelPort, run Action/Memory, or
   * call ResponseFinalizer. Formal notifications and TaskReminderStack remain
   * the existing Reminder/Stack owners; this dependency can only append one
   * non-operational pet expression.
   */
  async handleEvent(event: CompanionEvent): Promise<void> {
    const parsed = parseCompanionEvent(event);
    if (!parsed || !this.dependencies.proactiveEventService) return;
    try {
      await this.dependencies.proactiveEventService.handleEvent(parsed);
    } catch {
      // A void event API cannot report a sink failure. The service owns the
      // durable reservation/confirmation boundary and must fail closed.
    }
  }

  async respond(input: CompanionInput): Promise<CompanionResponse> {
    const identity = createIdentity(input);
    const counts = emptyCallCounts();
    const primaryPort = this.dependencies.modelPort;
    const invalidInput = validateInput(input);
    if (invalidInput) {
      return this.errorResponse(
        identity,
        primaryPort.info,
        counts,
        {
          kind: "invalid-input",
          message: DEFAULT_INVALID_INPUT_MESSAGE,
        },
      );
    }
    const localHints = buildLocalRequestHints(input);
    if (input.signal?.aborted) {
      const response = this.cancelledResponse(
        identity,
        primaryPort.info,
        counts,
        localHints.proactivePreference
          ? {
              type: "proactive_preference",
              action: localHints.proactivePreference.action,
              status: "cancelled",
              errorCode: "turn-invalidated",
            }
          : undefined,
      );
      return localHints.action
        ? {
            ...response,
            actions: [{
              type: localHints.action.type,
              status: "cancelled",
              errorCode: "turn-invalidated",
            }],
          }
        : localHints.memoryCandidate
          ? {
              ...response,
              memory: cancelledMemoryResult(1),
            }
        : response;
    }

    // Deterministic Task/Reminder routes own the input before any Provider
    // snapshot is resolved. This is the Phase 4 zero-call boundary.
    if (localHints.localOwned && localHints.proactivePreference) {
      return await this.respondWithLocalProactivePreference(
        input,
        identity,
        counts,
        localHints.proactivePreference,
      );
    }
    if (localHints.localOwned && localHints.action) {
      return await this.respondWithLocalAction(input, identity, counts, localHints.action);
    }
    if (localHints.localOwned && localHints.memoryCandidate) {
      return await this.respondWithLocalMemory(
        input,
        identity,
        counts,
        localHints.memoryCandidate,
      );
    }

    let primaryTurn: ResolvedCompanionModelTurn;
    try {
      // This is the only primary Provider resolution for this Turn. All
      // privacy, Context, counting, error and response decisions below use
      // this immutable snapshot.
      primaryTurn = primaryPort.beginTurn();
    } catch (error) {
      const providerError = normalizeProviderError(error);
      return this.errorResponse(
        identity,
        primaryPort.info,
        counts,
        {
          kind: providerError.kind,
          message: providerError.userMessage,
          status: providerError.status,
        },
      );
    }

    if (primaryTurn.info.kind === "remote" && containsSensitiveCompanionText(input.message)) {
      return this.errorResponse(
        identity,
        primaryTurn.info,
        counts,
        {
          kind: "content-safety",
          message: REMOTE_SENSITIVE_INPUT_REPLY,
        },
      );
    }

    const previousTurn = this.activeTurns.get(input.sessionId);
    if (previousTurn) this.invalidateTurn(previousTurn, "superseded");

    const controller = new AbortController();
    const turn: ActiveTurn = {
      identity,
      input,
      controller,
      primaryTurn,
      providerInfo: primaryTurn.info,
      active: true,
      reason: null,
      fallbackAttempted: false,
    };
    this.activeTurns.set(input.sessionId, turn);
    const onInputAbort = () => this.invalidateTurn(turn, "cancelled");
    input.signal?.addEventListener("abort", onInputAbort, { once: true });

    try {
      let context;
      try {
        context = await (this.dependencies.contextBuilder?.build(input, controller.signal)
          ?? (primaryTurn.info.kind === "remote"
            ? assembleCompanionContext({
                petId: input.petId,
                userInput: input.message,
              })
            : defaultContext(input)));
        if (primaryTurn.info.kind === "remote") {
          context = filterCompanionContextForRemote(context);
        }
      } catch (error) {
        if (!this.isCurrentTurn(turn)) return this.invalidationResponse(turn, counts);
        return this.errorResponse(
          identity,
          primaryTurn.info,
          counts,
          contextBuildError(error),
        );
      }
      if (!this.isCurrentTurn(turn)) return this.invalidationResponse(turn, counts);

      const modelRequest: HarnessModelRequest = {
        input,
        context,
        signal: controller.signal,
      };
      const primaryAttempt = await this.runModelAttempt(
        turn,
        primaryTurn,
        modelRequest,
        counts,
        false,
      );
      if (!this.isCurrentTurn(turn)) return this.invalidationResponse(turn, counts);

      let primaryError: CompanionChatProviderError | undefined;
      let decoded: ModelDecodeResult | undefined;
      if (primaryAttempt.kind === "error") {
        primaryError = primaryAttempt.error;
      } else {
        decoded = decodeModelResponse(primaryAttempt.value, identity);
        if (decoded.kind === "stale") return this.discardedResponse(turn, counts);
        if (decoded.kind === "error") primaryError = decoded.error;
      }

      let selectedTurn = primaryTurn;
      let selectedResponse: CompanionModelResponse | undefined =
        decoded?.kind === "response" ? decoded.value : undefined;
      let degradedFrom: CompanionChatProviderErrorKind | undefined;
      let degraded = false;

      if (!selectedResponse && primaryError) {
        degradedFrom = primaryError.kind;
        const fallbackPort = this.dependencies.localFallbackModelPort;
        const fallbackEnabled = this.dependencies.fallbackToLocal !== false;
        const canFallback = fallbackPort !== undefined
          && shouldFallbackToLocalCompanion(primaryTurn.info, fallbackEnabled)
          && primaryError.kind !== "cancelled"
          && !turn.fallbackAttempted
          && this.isCurrentTurn(turn);
        if (canFallback) {
          let fallbackTurn: ResolvedCompanionModelTurn;
          try {
            // A fallback is resolved only after the primary Remote snapshot
            // has failed. It gets its own immutable, one-time snapshot.
            fallbackTurn = fallbackPort.beginTurn();
          } catch (error) {
            const fallbackError = normalizeProviderError(error);
            return this.errorResponse(
              identity,
              primaryTurn.info,
              counts,
              {
                kind: fallbackError.kind,
                message: fallbackError.userMessage,
                status: fallbackError.status,
              },
              false,
              primaryError.kind,
            );
          }
          if (fallbackTurn.info.kind !== "local") {
            return this.errorResponse(
              identity,
              primaryTurn.info,
              counts,
              {
                kind: "configuration",
                message: invalidLocalFallbackError().userMessage,
              },
              false,
              primaryError.kind,
            );
          }
          turn.fallbackAttempted = true;
          const fallbackAttempt = await this.runModelAttempt(
            turn,
            fallbackTurn,
            modelRequest,
            counts,
            true,
          );
          if (!this.isCurrentTurn(turn)) return this.invalidationResponse(turn, counts);
          if (fallbackAttempt.kind === "error") {
            return this.errorResponse(
              identity,
              providerInfoWithFallbackDisclosure(fallbackTurn, true),
              counts,
              {
                kind: fallbackAttempt.error.kind,
                message: fallbackAttempt.error.userMessage,
                status: fallbackAttempt.error.status,
              },
              true,
              primaryError.kind,
            );
          }
          const fallbackDecoded = decodeModelResponse(fallbackAttempt.value, identity);
          if (fallbackDecoded.kind === "stale") return this.discardedResponse(turn, counts);
          if (fallbackDecoded.kind === "error") {
            return this.errorResponse(
              identity,
              providerInfoWithFallbackDisclosure(fallbackTurn, true),
              counts,
              {
                kind: fallbackDecoded.error.kind,
                message: fallbackDecoded.error.userMessage,
                status: fallbackDecoded.error.status,
              },
              true,
              primaryError.kind,
            );
          }
          selectedTurn = fallbackTurn;
          selectedResponse = fallbackDecoded.value;
          degraded = true;
        } else {
          return this.errorResponse(
            identity,
            primaryTurn.info,
            counts,
            {
              kind: primaryError.kind,
              message: primaryError.userMessage,
              status: primaryError.status,
            },
          );
        }
      }

      if (!selectedResponse) {
        return this.errorResponse(
          identity,
          selectedTurn.info,
          counts,
          domainError(),
        );
      }
      return await this.finishResponse(
        turn,
        selectedTurn,
        selectedResponse,
        counts,
        degraded,
        degradedFrom,
        primaryError
          ? {
              kind: primaryError.kind,
              message: primaryError.userMessage,
              status: primaryError.status,
            }
          : undefined,
      );
    } finally {
      input.signal?.removeEventListener("abort", onInputAbort);
      if (this.activeTurns.get(input.sessionId) === turn) {
        this.activeTurns.delete(input.sessionId);
      }
    }
  }

  private async respondWithLocalAction(
    input: CompanionInput,
    identity: CompanionTurnIdentity,
    counts: CompanionCallCounts,
    candidate: CompanionActionCandidate,
  ): Promise<CompanionResponse> {
    const previousTurn = this.activeTurns.get(input.sessionId);
    if (previousTurn) this.invalidateTurn(previousTurn, "superseded");

    const controller = new AbortController();
    const turn: ActiveTurn = {
      identity,
      input,
      controller,
      primaryTurn: null,
      providerInfo: this.dependencies.modelPort.info,
      active: true,
      reason: null,
      fallbackAttempted: false,
    };
    this.activeTurns.set(input.sessionId, turn);
    const onInputAbort = () => this.invalidateTurn(turn, "cancelled");
    input.signal?.addEventListener("abort", onInputAbort, { once: true });

    try {
      if (!this.isCurrentTurn(turn)) return this.invalidationResponse(turn, counts);
      let actionResults: readonly ActionExecutionResult[];
      try {
        actionResults = await this.dependencies.actionService!.process(
          input,
          [candidate],
          controller.signal,
        );
      } catch {
        actionResults = [{
          type: candidate.type,
          status: "failed",
          errorCode: "action-service-threw",
        }];
      }
      if (!this.isCurrentTurn(turn)) {
        return this.invalidationResponse(turn, counts, actionResults);
      }
      return await this.finishResponse(
        turn,
        undefined,
        { replyDraft: "", actions: [] },
        counts,
        false,
        undefined,
        undefined,
        actionResults,
        [candidate],
      );
    } finally {
      input.signal?.removeEventListener("abort", onInputAbort);
      if (this.activeTurns.get(input.sessionId) === turn) {
        this.activeTurns.delete(input.sessionId);
      }
    }
  }

  private async respondWithLocalMemory(
    input: CompanionInput,
    identity: CompanionTurnIdentity,
    counts: CompanionCallCounts,
    candidate: MemoryCandidate,
  ): Promise<CompanionResponse> {
    const previousTurn = this.activeTurns.get(input.sessionId);
    if (previousTurn) this.invalidateTurn(previousTurn, "superseded");

    const controller = new AbortController();
    const turn: ActiveTurn = {
      identity,
      input,
      controller,
      primaryTurn: null,
      providerInfo: this.dependencies.modelPort.info,
      active: true,
      reason: null,
      fallbackAttempted: false,
    };
    this.activeTurns.set(input.sessionId, turn);
    const onInputAbort = () => this.invalidateTurn(turn, "cancelled");
    input.signal?.addEventListener("abort", onInputAbort, { once: true });

    try {
      if (!this.isCurrentTurn(turn)) return this.invalidationResponse(turn, counts);
      let memory: MemoryPolicyResult;
      try {
        memory = await this.dependencies.memoryService!.process(
          input,
          [candidate],
          controller.signal,
        );
      } catch {
        memory = {
          status: "failed",
          acceptedCount: 0,
          rejectedCount: 1,
          decisions: [{ index: 0, status: "failed", errorCode: "memory-service-threw" }],
          errorCode: "memory-service-threw",
        };
      }
      if (!this.isCurrentTurn(turn)) {
        return this.invalidationResponse(turn, counts, [], memory);
      }
      return await this.finishResponse(
        turn,
        undefined,
        { replyDraft: "", actions: [] },
        counts,
        false,
        undefined,
        undefined,
        [],
        undefined,
        undefined,
        memory,
      );
    } finally {
      input.signal?.removeEventListener("abort", onInputAbort);
      if (this.activeTurns.get(input.sessionId) === turn) {
        this.activeTurns.delete(input.sessionId);
      }
    }
  }

  private async respondWithLocalProactivePreference(
    input: CompanionInput,
    identity: CompanionTurnIdentity,
    counts: CompanionCallCounts,
    request: import("./companionHarnessTypes").CompanionProactivePreferenceRequest,
  ): Promise<CompanionResponse> {
    const previousTurn = this.activeTurns.get(input.sessionId);
    if (previousTurn) this.invalidateTurn(previousTurn, "superseded");

    const controller = new AbortController();
    const turn: ActiveTurn = {
      identity,
      input,
      controller,
      primaryTurn: null,
      providerInfo: this.dependencies.modelPort.info,
      active: true,
      reason: null,
      fallbackAttempted: false,
    };
    this.activeTurns.set(input.sessionId, turn);
    const onInputAbort = () => this.invalidateTurn(turn, "cancelled");
    input.signal?.addEventListener("abort", onInputAbort, { once: true });

    try {
      if (!this.isCurrentTurn(turn)) return this.invalidationResponse(turn, counts);
      let preference: CompanionProactivePreferenceExecutionResult;
      if (!this.dependencies.proactivePreferenceService) {
        preference = {
          type: "proactive_preference",
          action: request.action,
          status: "failed",
          errorCode: "proactive-preference-service-not-configured",
        };
      } else {
        try {
          preference = await this.dependencies.proactivePreferenceService.process(
            input,
            request,
            controller.signal,
          );
        } catch {
          preference = {
            type: "proactive_preference",
            action: request.action,
            status: "failed",
            errorCode: "proactive-preference-service-threw",
          };
        }
      }
      if (!this.isCurrentTurn(turn)) {
        return this.invalidationResponse(turn, counts, [], createMemoryResult(), preference);
      }
      return await this.finishResponse(
        turn,
        undefined,
        { replyDraft: "", actions: [] },
        counts,
        false,
        undefined,
        undefined,
        [],
        undefined,
        preference,
      );
    } finally {
      input.signal?.removeEventListener("abort", onInputAbort);
      if (this.activeTurns.get(input.sessionId) === turn) {
        this.activeTurns.delete(input.sessionId);
      }
    }
  }

  private invalidateTurn(turn: ActiveTurn, reason: TurnInvalidationReason): void {
    if (!turn.active) return;
    turn.active = false;
    turn.reason = reason;
    turn.controller.abort();
  }

  private isCurrentTurn(turn: ActiveTurn): boolean {
    return turn.active
      && this.activeTurns.get(turn.identity.sessionId) === turn
      && !turn.controller.signal.aborted
      && !turn.input.signal?.aborted;
  }

  private async runModelAttempt(
    turn: ActiveTurn,
    resolvedTurn: ResolvedCompanionModelTurn,
    request: HarnessModelRequest,
    counts: CompanionCallCounts,
    isFallback: boolean,
  ): Promise<ModelAttemptResult> {
    if (!this.isCurrentTurn(turn)) {
      return { kind: "error", error: cancelledProviderError() };
    }

    // This is the final generic model-attempt boundary. Even if a caller
    // wires a fallback with the wrong metadata, a second remote generate()
    // must fail closed before the port is invoked or counted.
    if (resolvedTurn.info.kind === "remote" && counts.external >= 1) {
      return { kind: "error", error: remoteCallLimitError() };
    }

    counts.model += 1;
    if (resolvedTurn.info.kind === "remote") counts.external += 1;
    else counts.local += 1;
    if (isFallback) counts.fallback += 1;

    const attemptController = new AbortController();
    let settleAttempt: ((result: ModelAttemptResult) => void) | null = null;
    const onTurnAbort = () => {
      attemptController.abort();
      settleAttempt?.({ kind: "error", error: cancelledProviderError() });
    };
    let timeoutHandle: ReturnType<typeof setTimeout> | null = null;
    let settled = false;

    return await new Promise<ModelAttemptResult>((resolve) => {
      const settle = (result: ModelAttemptResult) => {
        if (settled) return;
        settled = true;
        if (timeoutHandle !== null) clearTimeout(timeoutHandle);
        turn.controller.signal.removeEventListener("abort", onTurnAbort);
        attemptController.abort();
        resolve(result);
      };
      settleAttempt = settle;
      turn.controller.signal.addEventListener("abort", onTurnAbort, { once: true });

      if (!this.isCurrentTurn(turn)) {
        settle({ kind: "error", error: cancelledProviderError() });
        return;
      }

      timeoutHandle = setTimeout(() => {
        attemptController.abort();
        settle({ kind: "error", error: timeoutProviderError() });
      }, this.timeoutMs);

      let generated: Promise<unknown>;
      try {
        generated = resolvedTurn.generate({
          ...request,
          signal: attemptController.signal,
        }) as Promise<unknown>;
      } catch (error) {
        settle({ kind: "error", error: normalizeProviderError(error) });
        return;
      }

      Promise.resolve(generated).then(
        (value) => settle({ kind: "response", value }),
        (error: unknown) => settle({ kind: "error", error: normalizeProviderError(error) }),
      );
    });
  }

  private async finishResponse(
    turn: ActiveTurn,
    resolvedTurn: ResolvedCompanionModelTurn | undefined,
    modelResponse: CompanionModelResponse,
    counts: CompanionCallCounts,
    providerDegraded: boolean,
    degradedFrom?: CompanionChatProviderErrorKind,
    degradedError?: CompanionHarnessError,
    precomputedActionResults?: readonly ActionExecutionResult[],
    actionCandidatesOverride?: readonly CompanionActionCandidate[],
    proactivePreference?: CompanionProactivePreferenceExecutionResult,
    precomputedMemory?: MemoryPolicyResult,
  ): Promise<CompanionResponse> {
    if (!this.isCurrentTurn(turn)) return this.invalidationResponse(turn, counts);

    const actionCandidates = actionCandidatesOverride ?? modelResponse.actions ?? [];
    const memoryCandidates = modelResponse.memoryCandidates ?? [];
    let actionResults: readonly ActionExecutionResult[] = precomputedActionResults ?? [];
    let memory = precomputedMemory ?? createMemoryResult();
    if (
      precomputedMemory === undefined
      && modelResponse.invalidMemoryCandidateIndexes
      && modelResponse.invalidMemoryCandidateIndexes.length > 0
    ) {
      memory = {
        status: "ignored",
        acceptedCount: 0,
        rejectedCount: modelResponse.invalidMemoryCandidateIndexes.length,
        decisions: modelResponse.invalidMemoryCandidateIndexes.map((index) => ({
          index,
          status: "rejected" as const,
          errorCode: "invalid-candidate",
        })),
      };
    }
    let domainDegraded = false;

    if (actionCandidates.length > 0 && precomputedActionResults === undefined) {
      if (!this.isCurrentTurn(turn)) {
        return this.invalidationResponse(turn, counts, actionResults, memory);
      }
      if (!this.dependencies.actionService) {
        actionResults = actionCandidates.map((candidate) => ({
          type: candidate.type,
          status: "failed" as const,
          errorCode: "action-service-not-configured",
        }));
      } else {
        try {
          actionResults = await this.dependencies.actionService.process(
            turn.input,
            actionCandidates,
            turn.controller.signal,
          );
        } catch {
          if (!this.isCurrentTurn(turn)) {
            return this.invalidationResponse(turn, counts, actionResults, memory);
          }
          actionResults = actionCandidates.map((candidate) => ({
            type: candidate.type,
            status: "failed" as const,
            errorCode: "action-service-threw",
          }));
        }
      }
      if (actionResults.length === 0) {
        actionResults = actionCandidates.map((candidate) => ({
          type: candidate.type,
          status: "failed" as const,
          errorCode: "action-result-missing",
        }));
      }
      if (!this.isCurrentTurn(turn)) {
        return this.invalidationResponse(turn, counts, actionResults, memory);
      }
    }

    if (memoryCandidates.length > 0 && precomputedMemory === undefined) {
      if (!this.isCurrentTurn(turn)) {
        return this.invalidationResponse(turn, counts, actionResults, memory);
      }
      try {
        const processedMemory = await this.dependencies.memoryService!.process(
          turn.input,
          memoryCandidates,
          turn.controller.signal,
        );
        memory = modelResponse.invalidMemoryCandidateIndexes?.length
          ? mergeMemoryPolicyResults(
              memory,
              processedMemory,
              modelResponse.memoryCandidateIndexes,
            )
          : processedMemory;
      } catch {
        const failedMemory: MemoryPolicyResult = {
          status: "failed",
          acceptedCount: 0,
          rejectedCount: memoryCandidates.length,
          decisions: memoryCandidates.map((_, index) => ({
            index,
            status: "failed" as const,
            errorCode: "memory-service-failed",
          })),
          errorCode: "memory-service-failed",
        };
        memory = modelResponse.invalidMemoryCandidateIndexes?.length
          ? mergeMemoryPolicyResults(
              memory,
              failedMemory,
              modelResponse.memoryCandidateIndexes,
            )
          : failedMemory;
      }
      if (!this.isCurrentTurn(turn)) {
        return this.invalidationResponse(turn, counts, actionResults, memory);
      }
    }
    domainDegraded = memory.status === "failed";

    const actionDegraded = actionCandidates.length > 0 && hasActionFailure(actionResults);
    const proactivePreferenceDegraded = proactivePreference !== undefined
      && proactivePreference.status !== "succeeded"
      && proactivePreference.status !== "duplicate";
    const responseStatus = providerDegraded || domainDegraded || actionDegraded || proactivePreferenceDegraded
      ? "degraded"
      : responseStatusForMemory(memory);
    const responseError = degradedError
      ?? (actionDegraded
        ? domainError("本轮操作没有全部按请求完成，下面是本地事实结果。")
        : proactivePreferenceDegraded
        ? domainError("主动提醒偏好没有按请求完成，下面是本地事实结果。")
        : memory.status === "failed"
        ? domainError("Memory 没有保存成功，本轮聊天仍已保留。")
        : undefined);
    const provider = resolvedTurn
      ? providerInfoWithFallbackDisclosure(resolvedTurn, providerDegraded)
      : turn.providerInfo;
    const response: CompanionResponse = {
      identity: turn.identity,
      status: responseStatus,
      text: finalizeCompanionResponse({
        replyDraft: modelResponse.replyDraft,
        actions: actionResults,
        memory,
        ...(proactivePreference ? { proactivePreference } : {}),
      }),
      provider,
      providerDisclosure: provider.disclosure,
      degraded: responseStatus === "degraded",
      canCommit: true,
      committed: false,
      actions: actionResults,
      ...(proactivePreference ? { proactivePreference } : {}),
      memory,
      callCounts: counts,
      ...(responseError ? { error: responseError } : {}),
      ...(degradedFrom ? { degradedFrom } : {}),
    };

    if (!this.dependencies.responseSink) return response;
    if (!this.isCurrentTurn(turn)) {
      return this.invalidationResponse(turn, counts, actionResults, memory, proactivePreference);
    }
    const commitGuard = this.createResponseCommitGuard(turn);
    let resolveInvalidation: (() => void) | null = null;
    const invalidationPromise = new Promise<"invalidated">((resolve) => {
      resolveInvalidation = () => resolve("invalidated");
      if (!this.isCurrentTurn(turn)) resolveInvalidation();
      else turn.controller.signal.addEventListener("abort", resolveInvalidation, { once: true });
    });
    const commitPromise = Promise.resolve()
      .then(() => this.dependencies.responseSink!.commit(turn.input, response, commitGuard))
      .then(
        () => ({ kind: "completed" as const }),
        (error: unknown) => ({ kind: "error" as const, error }),
      );
    const commitOutcome = await Promise.race([commitPromise, invalidationPromise]);
    if (resolveInvalidation) {
      turn.controller.signal.removeEventListener("abort", resolveInvalidation);
    }
    if (commitOutcome === "invalidated") {
      return this.invalidationResponse(turn, counts, actionResults, memory, proactivePreference);
    }
    if (commitOutcome.kind === "error") {
      return this.errorResponse(
        turn.identity,
        response.provider,
        counts,
        domainError(),
        response.degraded,
        degradedFrom,
        actionResults,
        memory,
        proactivePreference,
      );
    }
    // A sink may have waited asynchronously. A check before commit is not
    // enough; the Harness checks the Turn again after the sink returns and
    // only reports a commit if the guard recorded an actual guarded mutation.
    if (!this.isCurrentTurn(turn)) {
      return this.invalidationResponse(turn, counts, actionResults, memory, proactivePreference);
    }
    if (!commitGuard.committed) {
      return this.errorResponse(
        turn.identity,
        response.provider,
        counts,
        domainError("响应 Sink 没有通过有效性门禁提交。"),
        response.degraded,
        degradedFrom,
        actionResults,
        memory,
        proactivePreference,
      );
    }
    return { ...response, committed: true };
  }

  private createResponseCommitGuard(turn: ActiveTurn): CompanionResponseCommitGuard {
    let committed = false;
    return {
      identity: turn.identity,
      signal: turn.controller.signal,
      get committed() {
        return committed;
      },
      isCurrent: () => this.isCurrentTurn(turn),
      isCurrentFor: (input, response) => this.isCurrentTurn(turn)
        && sameIdentity(turn.identity, createIdentity(input))
        && sameIdentity(turn.identity, response.identity),
      commitIfCurrent: (input, response, mutation) => {
        if (committed || !this.isCurrentTurn(turn)) return false;
        if (!sameIdentity(turn.identity, createIdentity(input))) return false;
        if (!sameIdentity(turn.identity, response.identity)) return false;
        // Mark before invoking the mutation so a re-entrant sink cannot
        // submit the same response twice. A throwing mutation is still not
        // safe to retry because it may have partially mutated its target.
        committed = true;
        mutation();
        return true;
      },
    };
  }

  private errorResponse(
    identity: CompanionTurnIdentity,
    provider: CompanionModelPortInfo,
    counts: CompanionCallCounts,
    error: CompanionHarnessError,
    degraded = false,
    degradedFrom?: CompanionChatProviderErrorKind,
    actions: readonly ActionExecutionResult[] = [],
    memory: MemoryPolicyResult = createMemoryResult(),
    proactivePreference?: CompanionProactivePreferenceExecutionResult,
  ): CompanionResponse {
    const status: CompanionResponseStatus = "error";
    return {
      identity,
      status,
      text: null,
      provider,
      providerDisclosure: provider.disclosure,
      degraded,
      canCommit: false,
      committed: false,
      actions,
      ...(proactivePreference ? { proactivePreference } : {}),
      memory,
      callCounts: counts,
      error,
      ...(degradedFrom ? { degradedFrom } : {}),
    };
  }

  private cancelledResponse(
    identity: CompanionTurnIdentity,
    provider: CompanionModelPortInfo,
    counts: CompanionCallCounts,
    proactivePreference?: CompanionProactivePreferenceExecutionResult,
  ): CompanionResponse {
    return {
      identity,
      status: "cancelled",
      text: null,
      provider,
      providerDisclosure: provider.disclosure,
      degraded: false,
      canCommit: false,
      committed: false,
      actions: [],
      ...(proactivePreference ? { proactivePreference } : {}),
      memory: createMemoryResult(),
      callCounts: counts,
      error: { kind: "cancelled", message: DEFAULT_CANCELLED_MESSAGE },
    };
  }

  private discardedResponse(
    turn: ActiveTurn,
    counts: CompanionCallCounts,
    actions: readonly ActionExecutionResult[] = [],
    memory: MemoryPolicyResult = createMemoryResult(),
    proactivePreference?: CompanionProactivePreferenceExecutionResult,
  ): CompanionResponse {
    return {
      identity: turn.identity,
      status: "discarded",
      text: null,
      provider: turn.providerInfo,
      providerDisclosure: turn.providerInfo.disclosure,
      degraded: false,
      canCommit: false,
      committed: false,
      actions,
      ...(proactivePreference ? { proactivePreference } : {}),
      memory,
      callCounts: counts,
      error: { kind: "stale-turn", message: DEFAULT_STALE_MESSAGE },
    };
  }

  private invalidationResponse(
    turn: ActiveTurn,
    counts: CompanionCallCounts,
    actions: readonly ActionExecutionResult[] = [],
    memory: MemoryPolicyResult = createMemoryResult(),
    proactivePreference?: CompanionProactivePreferenceExecutionResult,
  ): CompanionResponse {
    if (turn.reason === "cancelled" || turn.input.signal?.aborted) {
      const response = this.cancelledResponse(turn.identity, turn.providerInfo, counts, proactivePreference);
      return { ...response, actions, memory };
    }
    return this.discardedResponse(turn, counts, actions, memory, proactivePreference);
  }
}

export function createCompanionHarness(
  dependencies: CompanionHarnessDependencies,
): CompanionHarness {
  return new CompanionHarnessImpl(dependencies);
}

export type { CompanionHarnessDependencies } from "./companionHarnessTypes";
