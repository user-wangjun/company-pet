import type {
  ActionExecutionStatus,
  CompanionActionType,
  CompanionCallCounts,
  CompanionResponse,
  CompanionResponseStatus,
  MemoryPolicyStatus,
} from "./companionHarnessTypes";

export type CompanionObservationErrorKind =
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
  | "remote"
  | "domain"
  | "invalid-input"
  | "stale-turn"
  | "unknown";

export type CompanionSafeActionObservation = {
  type: CompanionActionType | "unknown";
  status: ActionExecutionStatus | "unknown";
};

export type CompanionTurnObservation = {
  kind: "turn";
  requestId: string;
  providerProfileId: string;
  protocol: "local" | "ollama-local" | "gemini-native" | "openai-compatible" | "unknown";
  latencyMs: number;
  callCounts: CompanionCallCounts;
  actions: readonly CompanionSafeActionObservation[];
  memory: {
    candidateCount: number;
    acceptedCount: number;
    rejectedCount: number;
    status: MemoryPolicyStatus | "unknown";
  };
  responseStatus: CompanionResponseStatus;
  errorKind?: CompanionObservationErrorKind;
};

export type CompanionProactiveObservation = {
  kind: "proactive";
  eventType: "REMINDER_DUE" | "TASK_DUE_SOON" | "unknown";
  decision: "forwarded" | "invalid" | "service-error";
};

export type CompanionObservation =
  | CompanionTurnObservation
  | CompanionProactiveObservation;

export type CompanionTurnObservationInput = {
  requestId: string;
  providerProfileId?: string;
  protocol?: string;
  latencyMs: number;
  callCounts: CompanionCallCounts;
  actions: readonly Readonly<{ type: string; status: string }>[];
  memory: {
    candidateCount: number;
    acceptedCount: number;
    rejectedCount: number;
    status: string;
  };
  responseStatus: string;
  errorKind?: string;
};

export type CompanionProactiveObservationInput = {
  eventType: string;
  decision: "forwarded" | "invalid" | "service-error";
};

export interface CompanionObservability {
  recordTurn(input: CompanionTurnObservationInput): void;
  recordProactive(input: CompanionProactiveObservationInput): void;
}

export type CompanionObservationRecorder = CompanionObservability & {
  snapshot(): readonly CompanionObservation[];
};

/**
 * A degraded response can describe a domain result that needs confirmation or
 * failed to write; only a response carrying the Harness provider error marker
 * represents an actual Provider-to-local fallback.
 */
export function shouldRecordProviderFallback(
  response: Pick<CompanionResponse, "degraded" | "degradedFrom">,
): boolean {
  return response.degraded === true && response.degradedFrom !== undefined;
}

const ACTION_TYPES = new Set<CompanionActionType>([
  "create_task",
  "create_reminder",
  "complete_task",
  "update_reminder",
  "cancel_task",
  "postpone_task",
  "reschedule_task",
]);
const ACTION_STATUSES = new Set<ActionExecutionStatus>([
  "succeeded",
  "duplicate",
  "not_found",
  "ambiguous",
  "confirmation_required",
  "rejected",
  "failed",
  "cancelled",
]);
const MEMORY_STATUSES = new Set<MemoryPolicyStatus>([
  "not-requested",
  "succeeded",
  "ignored",
  "failed",
  "cancelled",
]);
const ERROR_KINDS = new Set<CompanionObservationErrorKind>([
  "configuration",
  "unsupported",
  "authentication",
  "rate-limit",
  "timeout",
  "cancelled",
  "network",
  "server",
  "malformed-response",
  "content-safety",
  "remote",
  "domain",
  "invalid-input",
  "stale-turn",
  "unknown",
]);

function opaqueValue(value: unknown, prefix: string): string {
  const text = typeof value === "string" ? value : "";
  let hash = 2_166_136_261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16_777_619);
  }
  return `${prefix}${(hash >>> 0).toString(16).padStart(8, "0")}`;
}

function safeProtocol(value: unknown): CompanionTurnObservation["protocol"] {
  return value === "local"
    || value === "ollama-local"
    || value === "gemini-native"
    || value === "openai-compatible"
    ? value
    : "unknown";
}

function safeActionType(value: unknown): CompanionSafeActionObservation["type"] {
  return typeof value === "string" && ACTION_TYPES.has(value as CompanionActionType)
    ? value as CompanionActionType
    : "unknown";
}

function safeActionStatus(value: unknown): CompanionSafeActionObservation["status"] {
  return typeof value === "string" && ACTION_STATUSES.has(value as ActionExecutionStatus)
    ? value as ActionExecutionStatus
    : "unknown";
}

function safeMemoryStatus(value: unknown): CompanionTurnObservation["memory"]["status"] {
  return typeof value === "string" && MEMORY_STATUSES.has(value as MemoryPolicyStatus)
    ? value as MemoryPolicyStatus
    : "unknown";
}

function safeErrorKind(value: unknown): CompanionObservationErrorKind {
  return typeof value === "string" && ERROR_KINDS.has(value as CompanionObservationErrorKind)
    ? value as CompanionObservationErrorKind
    : "unknown";
}

function safeCount(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? Math.floor(value)
    : 0;
}

function safeLatency(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? Math.min(Math.floor(value), 86_400_000)
    : 0;
}

function safeResponseStatus(value: unknown): CompanionResponseStatus {
  return value === "success"
    || value === "degraded"
    || value === "error"
    || value === "cancelled"
    || value === "discarded"
    ? value
    : "error";
}

function safeCallCounts(value: CompanionCallCounts): CompanionCallCounts {
  return {
    model: safeCount(value.model),
    external: safeCount(value.external),
    local: safeCount(value.local),
    fallback: safeCount(value.fallback),
  };
}

function safeEventType(value: unknown): CompanionProactiveObservation["eventType"] {
  return value === "REMINDER_DUE" || value === "TASK_DUE_SOON" ? value : "unknown";
}

/**
 * Creates an in-memory, bounded observation sink. Every output field is
 * constructed from an allowlist; this API never accepts a prompt, response
 * body, message, Memory entry, Task projection, credential, or raw error.
 */
export function createCompanionObservationRecorder(
  maxEntries = 256,
): CompanionObservationRecorder {
  const entries: CompanionObservation[] = [];
  const limit = Math.max(1, Math.floor(maxEntries));

  return {
    recordTurn(input) {
      const observation: CompanionTurnObservation = {
        kind: "turn",
        requestId: opaqueValue(input.requestId, "request-"),
        providerProfileId: opaqueValue(input.providerProfileId ?? "unknown", "profile-"),
        protocol: safeProtocol(input.protocol),
        latencyMs: safeLatency(input.latencyMs),
        callCounts: safeCallCounts(input.callCounts),
        actions: input.actions.map((action) => ({
          type: safeActionType(action.type),
          status: safeActionStatus(action.status),
        })),
        memory: {
          candidateCount: safeCount(input.memory.candidateCount),
          acceptedCount: safeCount(input.memory.acceptedCount),
          rejectedCount: safeCount(input.memory.rejectedCount),
          status: safeMemoryStatus(input.memory.status),
        },
        responseStatus: safeResponseStatus(input.responseStatus),
        ...(input.errorKind === undefined ? {} : { errorKind: safeErrorKind(input.errorKind) }),
      };
      entries.push(observation);
      if (entries.length > limit) entries.splice(0, entries.length - limit);
    },
    recordProactive(input) {
      const observation: CompanionProactiveObservation = {
        kind: "proactive",
        eventType: safeEventType(input.eventType),
        decision: input.decision,
      };
      entries.push(observation);
      if (entries.length > limit) entries.splice(0, entries.length - limit);
    },
    snapshot() {
      return entries.map((entry) => entry.kind === "turn"
        ? {
            ...entry,
            callCounts: { ...entry.callCounts },
            actions: entry.actions.map((action) => ({ ...action })),
            memory: { ...entry.memory },
          }
        : { ...entry });
    },
  };
}

export const NOOP_COMPANION_OBSERVABILITY: CompanionObservability = {
  recordTurn: () => {},
  recordProactive: () => {},
};
