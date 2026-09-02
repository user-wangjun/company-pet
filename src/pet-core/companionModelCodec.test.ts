import { describe, expect, test } from "vitest";
import {
  CompanionModelCodecError,
  MAX_COMPANION_ACTION_CANDIDATES,
  MAX_COMPANION_MEMORY_CANDIDATES,
  MAX_COMPANION_REPLY_DRAFT_LENGTH,
  COMPANION_MODEL_RESPONSE_SCHEMA,
  decodeCompanionModelResponse,
  encodeCompanionModelRequest,
  normalizeCompanionMemoryCandidate,
  selectCompanionModelCodecOutput,
} from "./companionModelCodec";
import { assembleCompanionContext } from "./companionContext";
import type {
  ProviderCapabilities,
  ProviderGenerateResponse,
} from "./companionProviderAdapter";

const capabilities = (
  structuredOutput: ProviderCapabilities["structuredOutput"],
): ProviderCapabilities => ({
  textGeneration: true,
  structuredOutput,
  cancellation: true,
  usageMetadata: true,
});

function context() {
  return assembleCompanionContext({
    petId: "xiaoju-cat",
    userInput: "当前输入保留",
    systemPrompt: "legacy prompt",
    history: [
      { id: "h1", speaker: "user", text: "历史用户消息" },
      { id: "h2", speaker: "pet", text: "历史宠物消息" },
    ],
  });
}

function providerResponse(overrides: Partial<ProviderGenerateResponse> = {}): ProviderGenerateResponse {
  return {
    text: "TEXT_REPLY",
    metadata: {
      providerId: "provider-id",
      model: "model-id",
      usage: { inputTokens: 3, outputTokens: 2 },
    },
    ...overrides,
  };
}

describe("Harness-owned Companion Model Codec", () => {
  test("encodes only trusted system/history/current input through exhaustive mapping", () => {
    const request = encodeCompanionModelRequest(
      context(),
      capabilities("none"),
      { timeoutMs: 500 },
    );

    expect(request).toMatchObject({
      system: expect.stringContaining("legacy prompt"),
      messages: [
        { role: "user", content: "历史用户消息" },
        { role: "assistant", content: "历史宠物消息" },
        { role: "user", content: "当前输入保留" },
      ],
      output: { format: "text" },
      timeoutMs: 500,
    });
    expect(request.system).not.toContain("xiaoju-cat");
    expect(JSON.stringify(request)).not.toContain("epoch-1");
    expect(JSON.stringify(request)).not.toContain("contextEpoch");
    expect(JSON.stringify(request)).not.toContain("requestId");
    expect(JSON.stringify(request)).not.toContain("timezone");
    expect(JSON.stringify(request)).not.toContain("utcOffsetMinutes");
  });

  test("selects text, json_object, or json_schema only from generic capabilities", () => {
    expect(selectCompanionModelCodecOutput(capabilities("none"))).toEqual({
      mode: "text",
      output: { format: "text" },
    });
    expect(selectCompanionModelCodecOutput(capabilities("json_object"))).toEqual({
      mode: "json_object",
      output: { format: "json_object" },
    });
    expect(selectCompanionModelCodecOutput(capabilities("json_schema"))).toEqual({
      mode: "json_schema",
      output: {
        format: "json_schema",
        name: "companion_response",
        schema: COMPANION_MODEL_RESPONSE_SCHEMA,
      },
    });
    expect(COMPANION_MODEL_RESPONSE_SCHEMA.properties.memoryCandidates).toMatchObject({
      type: "array",
      maxItems: MAX_COMPANION_MEMORY_CANDIDATES,
      items: {
        type: "object",
        additionalProperties: false,
      },
    });
    expect(COMPANION_MODEL_RESPONSE_SCHEMA.properties.memoryCandidates.items.required).toEqual(
      expect.arrayContaining([
        "source",
        "evidence",
        "sourceMessageId",
        "scope",
        "category",
        "lifetime",
        "expiresAt",
        "confidence",
        "importance",
        "explicitness",
        "confirmationStatus",
      ]),
    );
  });

  test("text-only response never guesses Action or Memory from ordinary text", () => {
    const response = decodeCompanionModelResponse({
      ...providerResponse(),
      structured: {
        replyDraft: "SHOULD_NOT_BE_PARSED",
        actions: [{ type: "create_task" }],
      },
    }, {
      mode: "text",
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
    });

    expect(response).toMatchObject({
      replyDraft: "TEXT_REPLY",
      actions: [],
      memoryCandidates: [],
      metadata: {
        provider: "provider-id",
        model: "model-id",
        usage: { inputTokens: 3, outputTokens: 2 },
      },
    });
  });

  test("strictly decodes a valid Envelope, drops unknown fields and invalid candidates", () => {
    const response = decodeCompanionModelResponse(providerResponse({
      text: "fallback text",
      structured: {
        replyDraft: "结构化回复",
        extraField: "DROP_ME",
        actions: [
          {
            sourceMessageId: "message-1",
            intent: "explicit",
            type: "create_task",
            payload: {
              title: "明天交报告",
              dueAt: "2026-08-12T09:00:00.000Z",
              taskId: "TASK_ID_MUST_DROP",
            },
          },
          {
            sourceMessageId: "message-1",
            intent: "explicit",
            type: "unknown_action",
            payload: { value: "UNKNOWN_ACTION_DROP" },
          },
          {
            sourceMessageId: "other-message",
            intent: "explicit",
            type: "create_task",
            payload: { title: "WRONG_SOURCE_DROP" },
          },
        ],
        memoryCandidates: [
          {
            scope: "global",
            type: "preference",
            category: "preference",
            lifetime: "stable",
            content: "用户喜欢桂花茶",
            source: "explicit",
            evidence: "用户明确表达",
            sourceMessageId: "message-1",
            confidence: 0.9,
            importance: 0.8,
            explicitness: "explicit",
            confirmationStatus: "not_required",
            expiresAt: null,
            requiresConfirmation: false,
            confirmed: true,
          },
          {
            scope: "pet:other-cat",
            type: "relationship",
            category: "shared_experience",
            lifetime: "stable",
            content: "OTHER_PET_DROP",
            source: "confirmed",
            evidence: "证据",
            sourceMessageId: "message-1",
            confidence: 0.9,
            importance: 0.8,
            explicitness: "inferred",
            confirmationStatus: "confirmed",
            expiresAt: null,
            requiresConfirmation: false,
            confirmed: true,
          },
          {
            scope: "pet:xiaoju-cat",
            type: "fact",
            category: "profile",
            lifetime: "stable",
            content: "INVALID_CONFIDENCE_DROP",
            source: "confirmed",
            evidence: "证据",
            sourceMessageId: "message-1",
            confidence: 2,
            importance: 0.8,
            explicitness: "inferred",
            confirmationStatus: "confirmed",
            expiresAt: null,
            requiresConfirmation: false,
            confirmed: true,
          },
          {
            scope: "global",
            type: "preference",
            category: "preference",
            lifetime: "stable",
            content: "UNKNOWN_FIELD_DROP",
            source: "inferred",
            evidence: "证据",
            sourceMessageId: "message-1",
            confidence: 0.5,
            importance: 0.5,
            explicitness: "inferred",
            confirmationStatus: "requires_confirmation",
            expiresAt: null,
            requiresConfirmation: true,
            confirmed: false,
            unknownField: "DROP_CANDIDATE",
          },
        ],
      },
    }), {
      mode: "json_schema",
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
    });

    expect(response.replyDraft).toBe("结构化回复");
    expect(response.actions).toEqual([{
      sourceMessageId: "message-1",
      intent: "explicit",
      type: "create_task",
      payload: {
        title: "明天交报告",
        dueAt: "2026-08-12T09:00:00.000Z",
      },
    }]);
    expect(response.memoryCandidates).toEqual([{
      scope: "global",
      type: "preference",
      category: "preference",
      lifetime: "stable",
      content: "用户喜欢桂花茶",
      source: "explicit",
      evidence: "用户明确表达",
      sourceMessageId: "message-1",
      confidence: 0.9,
      importance: 0.8,
      explicitness: "explicit",
      confirmationStatus: "not_required",
      expiresAt: null,
      requiresConfirmation: false,
      confirmed: true,
    }]);
    expect(JSON.stringify(response)).not.toContain("DROP_ME");
    expect(JSON.stringify(response)).not.toContain("OTHER_PET_DROP");
    expect(JSON.stringify(response)).not.toContain("DROP_CANDIDATE");
    expect(response.invalidMemoryCandidateIndexes).toEqual([1, 2, 3]);
    expect(response.invalidMemoryCandidateCount).toBe(3);
  });

  test("enforces candidate count, field limits, enums, and confidence bounds", () => {
    const actions = Array.from({ length: MAX_COMPANION_ACTION_CANDIDATES + 2 }, (_, index) => ({
      sourceMessageId: "message-1",
      intent: "implicit",
      type: "complete_task",
      payload: { reference: `task-${index}` },
    }));
    const memoryCandidates = Array.from({ length: MAX_COMPANION_MEMORY_CANDIDATES + 2 }, (_, index) => ({
      scope: "global",
      type: "fact",
      category: "goal",
      lifetime: "stable",
      content: `fact-${index}`,
      source: "inferred",
      evidence: "evidence",
      sourceMessageId: "message-1",
      confidence: 0.5,
      importance: 0.5,
      explicitness: "inferred",
      confirmationStatus: "requires_confirmation",
      expiresAt: null,
      requiresConfirmation: true,
      confirmed: false,
    }));
    const response = decodeCompanionModelResponse(providerResponse({
      structured: { replyDraft: "bounded", actions, memoryCandidates },
    }), {
      mode: "json_object",
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
    });

    expect(response.actions).toHaveLength(MAX_COMPANION_ACTION_CANDIDATES);
    expect(response.memoryCandidates).toHaveLength(MAX_COMPANION_MEMORY_CANDIDATES);
  });

  test("rejects malformed or overlong Memory expiration fields", () => {
    const response = decodeCompanionModelResponse(providerResponse({
      structured: {
        replyDraft: "安全回复",
        memoryCandidates: [
          {
            scope: "global",
            type: "fact",
            category: "profile",
            lifetime: "temporal",
            content: "有效内容",
            source: "confirmed",
            evidence: "用户确认",
            sourceMessageId: "message-1",
            confidence: 0.8,
            importance: 0.8,
            explicitness: "inferred",
            confirmationStatus: "confirmed",
            expiresAt: "",
            requiresConfirmation: false,
            confirmed: true,
          },
          {
            scope: "global",
            type: "fact",
            category: "profile",
            lifetime: "temporal",
            content: "另一个有效内容",
            source: "confirmed",
            evidence: "用户确认",
            sourceMessageId: "message-1",
            confidence: 0.8,
            importance: 0.8,
            explicitness: "inferred",
            confirmationStatus: "confirmed",
            expiresAt: "2026-08-11T00:00:00.000Z".repeat(50),
            requiresConfirmation: false,
            confirmed: true,
          },
        ],
      },
    }), {
      mode: "json_object",
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
    });

    expect(response.memoryCandidates).toEqual([]);
  });

  test("fails closed for category/type mismatch, contradictory confirmation, and non-finite numbers", () => {
    const base = {
      scope: "global",
      type: "fact",
      category: "profile",
      lifetime: "stable",
      content: "安全候选",
      source: "inferred",
      evidence: "模型候选",
      sourceMessageId: "message-1",
      confidence: 0.5,
      importance: 0.5,
      explicitness: "inferred",
      confirmationStatus: "requires_confirmation",
      expiresAt: null,
      requiresConfirmation: true,
      confirmed: false,
    } as const;
    expect(normalizeCompanionMemoryCandidate({
      ...base,
      type: "preference",
    }, {
      mode: "json_object",
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
    })).toBeNull();
    expect(normalizeCompanionMemoryCandidate({
      ...base,
      requiresConfirmation: false,
      confirmed: false,
    }, {
      mode: "json_object",
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
    })).toBeNull();
    expect(normalizeCompanionMemoryCandidate({
      ...base,
      confidence: Number.NaN,
    }, {
      mode: "json_object",
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
    })).toBeNull();
    expect(normalizeCompanionMemoryCandidate({
      ...base,
      importance: Number.POSITIVE_INFINITY,
    }, {
      mode: "json_object",
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
    })).toBeNull();
  });

  test("falls back to safe text for malformed structured payload without another call", () => {
    expect(decodeCompanionModelResponse(providerResponse({
      text: "安全文本 fallback",
      structured: { replyDraft: "结构化回复", actions: "not-an-array" },
    }), {
      mode: "json_schema",
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
    })).toEqual({
      replyDraft: "安全文本 fallback",
      actions: [],
      memoryCandidates: [],
      metadata: {
        provider: "provider-id",
        model: "model-id",
        usage: { inputTokens: 3, outputTokens: 2 },
      },
    });
  });

  test("fails closed for an overlong reply or when no safe payload exists", () => {
    const long = "A".repeat(MAX_COMPANION_REPLY_DRAFT_LENGTH + 100);
    expect(() => decodeCompanionModelResponse(providerResponse({ text: long }), {
      mode: "text",
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
    })).toThrow(CompanionModelCodecError);
    expect(() => decodeCompanionModelResponse({
      text: undefined,
      metadata: { providerId: "provider-id" },
    }, {
      mode: "json_object",
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
    })).toThrow(CompanionModelCodecError);
  });

  test("does not expose proactive preference controls in the model Action contract", () => {
    expect(JSON.stringify(COMPANION_MODEL_RESPONSE_SCHEMA)).not.toContain("switch_pet");
    expect(decodeCompanionModelResponse(providerResponse({
      structured: {
        replyDraft: "安全回复",
        actions: [{
          sourceMessageId: "message-1",
          intent: "explicit",
          type: "switch_pet",
          payload: { reference: "交报告" },
        }],
      },
    }), {
      mode: "json_object",
      sourceMessageId: "message-1",
      petId: "xiaoju-cat",
    }).actions).toEqual([]);
  });

  test.each(["cancel_task", "postpone_task", "reschedule_task"] as const)(
    "keeps local compatibility Action %s out of the Model Envelope",
    (type) => {
      expect(JSON.stringify(COMPANION_MODEL_RESPONSE_SCHEMA)).not.toContain(type);
      const payload = type === "cancel_task"
        ? { reference: "本地目标" }
        : { reference: "本地目标", dueAt: "2026-08-12T08:00:00.000Z" };
      expect(decodeCompanionModelResponse(providerResponse({
        structured: {
          replyDraft: "安全回复",
          actions: [{
            sourceMessageId: "message-1",
            intent: "explicit",
            type,
            payload,
          }],
        },
      }), {
        mode: "json_object",
        sourceMessageId: "message-1",
        petId: "xiaoju-cat",
      }).actions).toEqual([]);
    },
  );

  test("does not accept an untrusted context for encoding", () => {
    expect(() => encodeCompanionModelRequest({
      petId: "xiaoju-cat",
      systemInstruction: "HAND_WRITTEN_SYSTEM",
      history: [],
      userInput: "安全输入",
    }, capabilities("none"), { timeoutMs: 100 })).toThrow(CompanionModelCodecError);
  });
});
