import {
  containsSensitiveCompanionText,
} from "./companionPrivacy";
import {
  isTrustedCompanionChatContext,
  type CompanionChatContext,
} from "./companionContext";
import type {
  ActionCandidate,
  CompanionModelResponse,
  MemoryCandidate,
} from "./companionHarnessTypes";
import type {
  ProviderCapabilities,
  ProviderGenerateRequest,
  ProviderGenerateResponse,
  ProviderOutputFormat,
} from "./companionProviderAdapter";

export const MAX_COMPANION_REPLY_DRAFT_LENGTH = 2_000;
export const MAX_COMPANION_ACTION_CANDIDATES = 4;
export const MAX_COMPANION_MEMORY_CANDIDATES = 4;
export const MAX_COMPANION_ACTION_FIELD_LENGTH = 240;
export const MAX_COMPANION_MEMORY_FIELD_LENGTH = 600;
export const MAX_COMPANION_SCHEMA_NAME_LENGTH = 64;
export const MAX_COMPANION_SOURCE_MESSAGE_ID_LENGTH = 160;

const actionEnvelopeBase = {
  type: "object",
  additionalProperties: false,
  properties: {
    sourceMessageId: {
      type: "string",
      minLength: 1,
      maxLength: MAX_COMPANION_SOURCE_MESSAGE_ID_LENGTH,
    },
    intent: { type: "string", enum: ["explicit", "implicit"] },
  },
} as const;

const actionPayloadSchemas = {
  createTask: {
    type: "object",
    additionalProperties: false,
    properties: {
      title: { type: "string", minLength: 1, maxLength: MAX_COMPANION_ACTION_FIELD_LENGTH },
      dueAt: { type: "string", minLength: 1, maxLength: MAX_COMPANION_ACTION_FIELD_LENGTH },
    },
    required: ["title"],
  },
  createReminder: {
    type: "object",
    additionalProperties: false,
    properties: {
      title: { type: "string", minLength: 1, maxLength: MAX_COMPANION_ACTION_FIELD_LENGTH },
      triggerAt: { type: "string", minLength: 1, maxLength: MAX_COMPANION_ACTION_FIELD_LENGTH },
      timezone: { type: "string", minLength: 1, maxLength: MAX_COMPANION_ACTION_FIELD_LENGTH },
    },
    required: ["title", "triggerAt", "timezone"],
  },
  completeTask: {
    type: "object",
    additionalProperties: false,
    properties: {
      reference: { type: "string", minLength: 1, maxLength: MAX_COMPANION_ACTION_FIELD_LENGTH },
    },
    required: ["reference"],
  },
  updateReminder: {
    type: "object",
    additionalProperties: false,
    properties: {
      reference: { type: "string", minLength: 1, maxLength: MAX_COMPANION_ACTION_FIELD_LENGTH },
      triggerAt: { type: "string", minLength: 1, maxLength: MAX_COMPANION_ACTION_FIELD_LENGTH },
      timezone: { type: "string", minLength: 1, maxLength: MAX_COMPANION_ACTION_FIELD_LENGTH },
    },
    required: ["reference", "triggerAt", "timezone"],
  },
} as const;

const MEMORY_CANDIDATE_CATEGORIES = [
  "profile",
  "person",
  "project",
  "goal",
  "event",
  "preference",
  "shared_experience",
] as const;

const MEMORY_CANDIDATE_TYPES = [
  "fact",
  "relationship",
  "episode",
  "preference",
] as const;

const memoryCandidateSchema = {
  type: "object",
  additionalProperties: false,
  properties: {
    source: { type: "string", enum: ["explicit", "inferred", "confirmed"] },
    evidence: {
      type: "string",
      minLength: 1,
      maxLength: MAX_COMPANION_MEMORY_FIELD_LENGTH,
    },
    sourceMessageId: {
      type: "string",
      minLength: 1,
      maxLength: MAX_COMPANION_SOURCE_MESSAGE_ID_LENGTH,
    },
    scope: {
      type: "string",
      minLength: 1,
      maxLength: MAX_COMPANION_SOURCE_MESSAGE_ID_LENGTH,
    },
    type: { type: "string", enum: MEMORY_CANDIDATE_TYPES },
    category: { type: "string", enum: MEMORY_CANDIDATE_CATEGORIES },
    candidateCategory: { type: "string", enum: MEMORY_CANDIDATE_CATEGORIES },
    lifetime: { type: "string", enum: ["stable", "temporal"] },
    content: {
      type: "string",
      minLength: 1,
      maxLength: MAX_COMPANION_MEMORY_FIELD_LENGTH,
    },
    confidence: { type: "number", minimum: 0, maximum: 1 },
    importance: { type: "number", minimum: 0, maximum: 1 },
    explicitness: { type: "string", enum: ["explicit", "inferred"] },
    confirmationStatus: {
      type: "string",
      enum: ["not_required", "requires_confirmation", "confirmed"],
    },
    expiresAt: {
      oneOf: [
        { type: "null" },
        { type: "string", minLength: 1, maxLength: MAX_COMPANION_MEMORY_FIELD_LENGTH, format: "date-time" },
      ],
    },
    // Kept as a wire compatibility shape only. The codec derives the
    // effective confirmation state from confirmationStatus and rejects a
    // contradictory pair.
    requiresConfirmation: { type: "boolean" },
    confirmed: { type: "boolean" },
  },
  required: [
    "source",
    "evidence",
    "sourceMessageId",
    "scope",
    "type",
    "category",
    "lifetime",
    "content",
    "confidence",
    "importance",
    "explicitness",
    "confirmationStatus",
    "expiresAt",
  ],
} as const;

function actionSchema(
  type: "create_task" | "create_reminder" | "complete_task" | "update_reminder",
  payload: unknown,
) {
  return {
    ...actionEnvelopeBase,
    properties: {
      ...actionEnvelopeBase.properties,
      type: { type: "string", const: type },
      payload,
    },
    required: ["sourceMessageId", "intent", "type", "payload"],
  } as const;
}

export const COMPANION_ACTION_SCHEMAS = Object.freeze([
  actionSchema("create_task", actionPayloadSchemas.createTask),
  actionSchema("create_reminder", actionPayloadSchemas.createReminder),
  actionSchema("complete_task", actionPayloadSchemas.completeTask),
  actionSchema("update_reminder", actionPayloadSchemas.updateReminder),
] as const);

export const COMPANION_MODEL_RESPONSE_SCHEMA = Object.freeze({
  type: "object",
  additionalProperties: false,
  properties: {
    replyDraft: { type: "string", maxLength: MAX_COMPANION_REPLY_DRAFT_LENGTH },
    actions: {
      type: "array",
      maxItems: MAX_COMPANION_ACTION_CANDIDATES,
      items: { oneOf: COMPANION_ACTION_SCHEMAS },
    },
    memoryCandidates: {
      type: "array",
      maxItems: MAX_COMPANION_MEMORY_CANDIDATES,
      items: memoryCandidateSchema,
    },
  },
  required: ["replyDraft"],
});

export type CompanionModelCodecMode = "text" | "json_object" | "json_schema";

export type CompanionModelCodecEncodeOptions = {
  timeoutMs: number;
  temperature?: number;
  maxOutputTokens?: number;
};

export type CompanionModelCodecDecodeOptions = {
  mode: CompanionModelCodecMode;
  sourceMessageId: string;
  petId: string;
};

export class CompanionModelCodecError extends Error {
  readonly kind = "malformed-response" as const;

  constructor(message = "聊天服务返回了无法识别的回复。") {
    super(message);
    this.name = "CompanionModelCodecError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nonEmptyString(value: unknown, maxLength: number): value is string {
  return typeof value === "string"
    && value.trim().length > 0
    && Array.from(value.trim()).length <= maxLength;
}

function boundedString(value: unknown, maxLength: number): string | null {
  if (!nonEmptyString(value, maxLength)) return null;
  return value.trim();
}

function safeReply(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.replace(/```[\s\S]*?```/g, "").replace(/\s+/g, " ").trim();
  if (!normalized || Array.from(normalized).length > MAX_COMPANION_REPLY_DRAFT_LENGTH) return null;
  if (containsSensitiveCompanionText(normalized)) {
    return "我先不复述这类敏感内容，好吗？";
  }
  return normalized;
}

function outputFormatForCapabilities(
  capabilities: ProviderCapabilities,
): { mode: CompanionModelCodecMode; output: ProviderOutputFormat } {
  if (capabilities.structuredOutput === "json_schema") {
    return {
      mode: "json_schema",
      output: {
        format: "json_schema",
        name: "companion_response",
        schema: COMPANION_MODEL_RESPONSE_SCHEMA,
      },
    };
  }
  if (capabilities.structuredOutput === "json_object") {
    return {
      mode: "json_object",
      output: { format: "json_object" },
    };
  }
  return { mode: "text", output: { format: "text" } };
}

function systemForProvider(context: CompanionChatContext, mode: CompanionModelCodecMode): string {
  // `petId` is an internal Harness identity. The ContextBuilder currently
  // includes a human-readable label for the legacy path; the Codec removes it
  // so the new generic request cannot leak the internal id.
  const withoutInternalPetId = context.systemInstruction
    .split(/\r?\n/u)
    .filter((line) => !/^\s*当前宠物 ID\s*[:：]/u.test(line))
    .join("\n")
    .trim();
  if (mode === "text") return withoutInternalPetId;
  return [
    withoutInternalPetId,
    "【模型响应格式】",
    "请返回一个 JSON 对象，只填写已知字段；不要执行动作，不要写入记忆。",
    "replyDraft 是给用户的短回复；actions 与 memoryCandidates 只能是当前输入的候选。",
  ].filter(Boolean).join("\n");
}

export function selectCompanionModelCodecOutput(
  capabilities: ProviderCapabilities,
): { mode: CompanionModelCodecMode; output: ProviderOutputFormat } {
  return outputFormatForCapabilities(capabilities);
}

/**
 * Encode only the trusted Context's exhaustive fields. Turn identity,
 * internal pet id, epoch, time, timezone, signal, and budget metadata never
 * enter the generic ProviderGenerateRequest.
 */
export function encodeCompanionModelRequest(
  context: CompanionChatContext,
  capabilities: ProviderCapabilities,
  options: CompanionModelCodecEncodeOptions,
): ProviderGenerateRequest {
  if (!isTrustedCompanionChatContext(context)) {
    throw new CompanionModelCodecError(
      "远程生成需要由正式 ContextBuilder 构建的受信 Context。",
    );
  }
  const selected = outputFormatForCapabilities(capabilities);
  return {
    system: systemForProvider(context, selected.mode),
    messages: [
      ...context.history.map((message) => ({
        role: message.speaker === "pet" ? ("assistant" as const) : ("user" as const),
        content: message.text,
      })),
      { role: "user", content: context.userInput },
    ],
    output: selected.output,
    timeoutMs: options.timeoutMs,
    generation: {
      ...(options.temperature === undefined ? {} : { temperature: options.temperature }),
      ...(options.maxOutputTokens === undefined
        ? {}
        : { maxOutputTokens: options.maxOutputTokens }),
    },
  };
}

/**
 * Local generation has no remote-send boundary. When a caller has not built
 * a trusted Context, the Model Port may still give a local Adapter the
 * current input only; this keeps the local path at zero external calls.
 */
export function encodeLocalCompanionModelRequest(
  message: string,
  options: CompanionModelCodecEncodeOptions,
): ProviderGenerateRequest {
  return {
    messages: [{ role: "user", content: message }],
    output: { format: "text" },
    timeoutMs: options.timeoutMs,
    generation: {
      ...(options.temperature === undefined ? {} : { temperature: options.temperature }),
      ...(options.maxOutputTokens === undefined
        ? {}
        : { maxOutputTokens: options.maxOutputTokens }),
    },
  };
}

function isKnownActionType(value: unknown): value is ActionCandidate["type"] {
  return value === "create_task"
    || value === "complete_task"
    || value === "create_reminder"
    || value === "update_reminder";
}

export function normalizeCompanionActionCandidate(
  value: unknown,
  sourceMessageId: string,
): ActionCandidate | null {
  if (!isRecord(value)) return null;
  const normalizedSourceMessageId = boundedString(
    value.sourceMessageId,
    MAX_COMPANION_SOURCE_MESSAGE_ID_LENGTH,
  );
  if (!normalizedSourceMessageId || normalizedSourceMessageId !== sourceMessageId) return null;
  if (value.intent !== "explicit" && value.intent !== "implicit") return null;
  if (!isKnownActionType(value.type) || !isRecord(value.payload)) return null;
  const payload = value.payload;
  if (value.type === "create_task") {
    const title = boundedString(payload.title, MAX_COMPANION_ACTION_FIELD_LENGTH);
    const dueAt = payload.dueAt === undefined
      ? undefined
      : boundedString(payload.dueAt, MAX_COMPANION_ACTION_FIELD_LENGTH);
    if (!title || (payload.dueAt !== undefined && !dueAt)) return null;
    return {
      sourceMessageId: normalizedSourceMessageId,
      intent: value.intent,
      type: value.type,
      payload: { title, ...(dueAt ? { dueAt } : {}) },
    };
  }
  if (value.type === "create_reminder") {
    const title = boundedString(payload.title, MAX_COMPANION_ACTION_FIELD_LENGTH);
    const triggerAt = boundedString(payload.triggerAt, MAX_COMPANION_ACTION_FIELD_LENGTH);
    const timezone = boundedString(payload.timezone, MAX_COMPANION_ACTION_FIELD_LENGTH);
    if (!title || !triggerAt || !timezone) return null;
    return {
      sourceMessageId: normalizedSourceMessageId,
      intent: value.intent,
      type: value.type,
      payload: { title, triggerAt, timezone },
    };
  }
  if (value.type === "complete_task") {
    const reference = boundedString(payload.reference, MAX_COMPANION_ACTION_FIELD_LENGTH);
    if (!reference) return null;
    return {
      sourceMessageId: normalizedSourceMessageId,
      intent: value.intent,
      type: value.type,
      payload: { reference },
    };
  }
  const reference = boundedString(payload.reference, MAX_COMPANION_ACTION_FIELD_LENGTH);
  const triggerAt = boundedString(payload.triggerAt, MAX_COMPANION_ACTION_FIELD_LENGTH);
  const timezone = boundedString(payload.timezone, MAX_COMPANION_ACTION_FIELD_LENGTH);
  if (!reference || !triggerAt || !timezone) return null;
  return {
    sourceMessageId: normalizedSourceMessageId,
    intent: value.intent,
    type: value.type,
    payload: { reference, triggerAt, timezone },
  };
}

function isValidIsoDateTime(value: unknown): value is string {
  if (typeof value !== "string" || value.trim() !== value) return false;
  if (Array.from(value).length > MAX_COMPANION_MEMORY_FIELD_LENGTH) return false;
  const match = value.match(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,3})?(Z|[+-](\d{2}):(\d{2}))$/u,
  );
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  const offsetHour = match[8] === undefined ? 0 : Number(match[8]);
  const offsetMinute = match[9] === undefined ? 0 : Number(match[9]);
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1] ?? 0;
  return month >= 1
    && month <= 12
    && day >= 1
    && day <= daysInMonth
    && hour >= 0
    && hour <= 23
    && minute >= 0
    && minute <= 59
    && second >= 0
    && second <= 59
    && offsetHour >= 0
    && offsetHour <= 23
    && offsetMinute >= 0
    && offsetMinute <= 59
    && Number.isFinite(Date.parse(value));
}

export function memoryTypeForCandidateCategory(
  category: unknown,
): MemoryCandidate["type"] | null {
  if (category === "profile" || category === "person" || category === "project" || category === "goal") {
    return "fact";
  }
  if (category === "event") return "episode";
  if (category === "preference") return "preference";
  if (category === "shared_experience") return "relationship";
  return null;
}

const MEMORY_CANDIDATE_KEYS = new Set([
  "source",
  "evidence",
  "sourceMessageId",
  "scope",
  "type",
  "category",
  "candidateCategory",
  "lifetime",
  "content",
  "confidence",
  "importance",
  "explicitness",
  "confirmationStatus",
  "expiresAt",
  "requiresConfirmation",
  "confirmed",
]);

export function normalizeCompanionMemoryCandidate(
  value: unknown,
  options: CompanionModelCodecDecodeOptions,
): MemoryCandidate | null {
  if (!isRecord(value)) return null;
  if ([...Object.keys(value)].some((key) => !MEMORY_CANDIDATE_KEYS.has(key))) return null;
  if (
    !boundedString(value.sourceMessageId, MAX_COMPANION_SOURCE_MESSAGE_ID_LENGTH)
    || value.sourceMessageId !== options.sourceMessageId
  ) return null;
  const scope = value.scope;
  if (scope !== "global" && scope !== `pet:${options.petId}`) return null;
  if (!MEMORY_CANDIDATE_TYPES.includes(value.type as typeof MEMORY_CANDIDATE_TYPES[number])) return null;
  if (!MEMORY_CANDIDATE_CATEGORIES.includes(value.category as typeof MEMORY_CANDIDATE_CATEGORIES[number])) return null;
  if (
    value.candidateCategory !== undefined
    && value.candidateCategory !== value.category
  ) return null;
  if (value.lifetime !== "stable" && value.lifetime !== "temporal") return null;
  if (value.source !== "explicit" && value.source !== "inferred" && value.source !== "confirmed") {
    return null;
  }
  if (value.explicitness !== "explicit" && value.explicitness !== "inferred") return null;
  if (
    value.confirmationStatus !== "not_required"
    && value.confirmationStatus !== "requires_confirmation"
    && value.confirmationStatus !== "confirmed"
  ) return null;
  const content = boundedString(value.content, MAX_COMPANION_MEMORY_FIELD_LENGTH);
  const evidence = boundedString(value.evidence, MAX_COMPANION_MEMORY_FIELD_LENGTH);
  if (!content || !evidence || !("expiresAt" in value)) return null;
  const expiresAt = value.expiresAt === null ? null : value.expiresAt;
  if (expiresAt !== null && !isValidIsoDateTime(expiresAt)) return null;
  if (value.lifetime === "stable" && expiresAt !== null) return null;
  if (value.lifetime === "temporal" && expiresAt === null) return null;
  if (
    containsSensitiveCompanionText(content)
    || containsSensitiveCompanionText(evidence)
    || containsSensitiveCompanionText(value.sourceMessageId)
  ) {
    return null;
  }
  if (
    typeof value.confidence !== "number"
    || !Number.isFinite(value.confidence)
    || value.confidence < 0
    || value.confidence > 1
    || typeof value.importance !== "number"
    || !Number.isFinite(value.importance)
    || value.importance < 0
    || value.importance > 1
  ) return null;
  if (
    (value.requiresConfirmation !== undefined && typeof value.requiresConfirmation !== "boolean")
    || (value.confirmed !== undefined && typeof value.confirmed !== "boolean")
    || ((value.requiresConfirmation === undefined) !== (value.confirmed === undefined))
  ) {
    return null;
  }
  const derivedRequiresConfirmation = value.confirmationStatus === "requires_confirmation";
  const derivedConfirmed = !derivedRequiresConfirmation;
  if (
    value.requiresConfirmation !== undefined
    && (value.requiresConfirmation !== derivedRequiresConfirmation
      || value.confirmed !== derivedConfirmed)
  ) return null;
  if (memoryTypeForCandidateCategory(value.category) !== value.type) return null;
  if (value.category === "shared_experience" && scope !== `pet:${options.petId}`) return null;
  if (value.type === "relationship" && scope !== `pet:${options.petId}`) return null;
  if (
    value.category !== "shared_experience"
    && value.type !== "relationship"
    && scope !== "global"
  ) return null;
  const normalizedScope = scope === "global"
    ? "global" as const
    : `pet:${options.petId}` as const;
  return {
    scope: normalizedScope,
    type: value.type as MemoryCandidate["type"],
    category: value.category as MemoryCandidate["category"],
    ...(value.candidateCategory !== undefined
      ? { candidateCategory: value.candidateCategory as MemoryCandidate["category"] }
      : {}),
    lifetime: value.lifetime,
    content,
    source: value.source,
    evidence,
    sourceMessageId: options.sourceMessageId,
    confidence: value.confidence,
    importance: value.importance,
    explicitness: value.explicitness,
    confirmationStatus: value.confirmationStatus,
    expiresAt,
    requiresConfirmation: derivedRequiresConfirmation,
    confirmed: derivedConfirmed,
  };
}

function metadataForResponse(
  response: ProviderGenerateResponse,
): CompanionModelResponse["metadata"] | undefined {
  if (!isRecord(response.metadata)) return undefined;
  const provider = boundedString(response.metadata.providerId, 160);
  if (!provider) return undefined;
  const model = boundedString(response.metadata.model, 160) ?? undefined;
  const usage = response.metadata.usage;
  const inputTokens = usage?.inputTokens;
  const outputTokens = usage?.outputTokens;
  const safeUsage = inputTokens !== undefined || outputTokens !== undefined
    ? {
        ...(inputTokens !== undefined
          && Number.isInteger(inputTokens)
          && inputTokens >= 0
          ? { inputTokens }
          : {}),
        ...(outputTokens !== undefined
          && Number.isInteger(outputTokens)
          && outputTokens >= 0
          ? { outputTokens }
          : {}),
      }
    : undefined;
  return {
    provider,
    ...(model ? { model } : {}),
    ...(safeUsage && Object.keys(safeUsage).length > 0 ? { usage: safeUsage } : {}),
  };
}

function decodeTextOnly(
  response: ProviderGenerateResponse,
): CompanionModelResponse {
  const replyDraft = safeReply(response.text);
  if (!replyDraft) throw new CompanionModelCodecError();
  return {
    replyDraft,
    actions: [],
    memoryCandidates: [],
    ...(metadataForResponse(response) ? { metadata: metadataForResponse(response) } : {}),
  };
}

function decodeStructuredEnvelope(
  value: unknown,
  options: CompanionModelCodecDecodeOptions,
  response: ProviderGenerateResponse,
): CompanionModelResponse | null {
  if (!isRecord(value)) return null;
  const replyDraft = safeReply(value.replyDraft);
  if (!replyDraft) return null;
  if (value.actions !== undefined && !Array.isArray(value.actions)) return null;
  if (value.memoryCandidates !== undefined && !Array.isArray(value.memoryCandidates)) return null;
  const actions = (value.actions ?? [])
    .slice(0, MAX_COMPANION_ACTION_CANDIDATES)
    .map((candidate) => normalizeCompanionActionCandidate(candidate, options.sourceMessageId))
    .filter((candidate): candidate is ActionCandidate => candidate !== null);
  const candidateValues = (value.memoryCandidates ?? []).slice(0, MAX_COMPANION_MEMORY_CANDIDATES);
  const normalizedMemoryCandidates = candidateValues.map((candidate, index) => ({
    index,
    candidate: normalizeCompanionMemoryCandidate(candidate, options),
  }));
  const memoryCandidates = normalizedMemoryCandidates
    .map(({ candidate }) => candidate)
    .filter((candidate): candidate is MemoryCandidate => candidate !== null);
  const invalidMemoryCandidateIndexes = normalizedMemoryCandidates
    .filter(({ candidate: normalized }) => normalized === null)
    .map(({ index }) => index);
  return {
    replyDraft,
    actions,
    memoryCandidates,
    ...(invalidMemoryCandidateIndexes.length > 0
      ? {
          invalidMemoryCandidateCount: invalidMemoryCandidateIndexes.length,
          invalidMemoryCandidateIndexes,
        }
      : {}),
    ...(memoryCandidates.length > 0
      ? {
          memoryCandidateIndexes: normalizedMemoryCandidates
            .filter(({ candidate: normalized }) => normalized !== null)
            .map(({ index }) => index),
        }
      : {}),
    ...(metadataForResponse(response) ? { metadata: metadataForResponse(response) } : {}),
  };
}

/**
 * Decode without guessing domain candidates from ordinary text. A malformed
 * structured payload may fall back to safe text in the same response, but it
 * never triggers a second Provider call.
 */
export function decodeCompanionModelResponse(
  response: ProviderGenerateResponse,
  options: CompanionModelCodecDecodeOptions,
): CompanionModelResponse {
  if (options.mode === "text") return decodeTextOnly(response);
  const structured = decodeStructuredEnvelope(response.structured, options, response);
  if (structured) return structured;
  const fallbackText = safeReply(response.text);
  if (fallbackText) {
    return {
      replyDraft: fallbackText,
      actions: [],
      memoryCandidates: [],
      ...(metadataForResponse(response) ? { metadata: metadataForResponse(response) } : {}),
    };
  }
  throw new CompanionModelCodecError();
}

export type CompanionModelCodec = {
  encode(
    context: CompanionChatContext,
    capabilities: ProviderCapabilities,
    options: CompanionModelCodecEncodeOptions,
  ): ProviderGenerateRequest;
  decode(
    response: ProviderGenerateResponse,
    options: CompanionModelCodecDecodeOptions,
  ): CompanionModelResponse;
};

export const companionModelCodec: CompanionModelCodec = {
  encode: encodeCompanionModelRequest,
  decode: decodeCompanionModelResponse,
};
