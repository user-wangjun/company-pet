import type { CompanionChatContext } from "./companionContext";
import type { CompanionContextEpoch } from "./companionContextEpoch";
import type { CompanionChatProviderErrorKind } from "./companionChatProvider";
import type {
  CompanionModelPort,
  CompanionModelPortInfo,
} from "./companionModelPort";
import type { MemoryRepository } from "./companionMemory";
import type { TaskDatabase } from "../task-core/types";

export type CompanionModelActionType =
  | "create_task"
  | "create_reminder"
  | "complete_task"
  | "update_reminder";

/**
 * These actions are local compatibility operations. They are intentionally
 * not part of the model Envelope and can only be produced by the local
 * deterministic extractor.
 */
export type CompanionLocalActionType =
  | "cancel_task"
  | "postpone_task"
  | "reschedule_task";

export type CompanionActionType = CompanionModelActionType | CompanionLocalActionType;

type ActionCandidateBase = {
  sourceMessageId: string;
  intent: "explicit" | "implicit";
};

export type ActionCandidate = ActionCandidateBase & (
  | {
      type: "create_task";
      payload: {
        title: string;
        dueAt?: string;
      };
    }
  | {
      type: "create_reminder";
      payload: {
        title: string;
        triggerAt: string;
        timezone: string;
      };
    }
  | {
      type: "complete_task";
      payload: {
        reference: string;
      };
    }
  | {
      type: "update_reminder";
      payload: {
        reference: string;
        triggerAt: string;
        timezone: string;
      };
    }
);

export type LocalCompatibilityActionCandidate = {
  sourceMessageId: string;
} & (
  | {
      type: "cancel_task";
      payload: { reference: string };
    }
  | {
      type: "postpone_task";
      payload: { reference: string; dueAt: string; remindAt?: string };
    }
  | {
      type: "reschedule_task";
      payload: { reference: string; dueAt: string; remindAt?: string };
    }
);

export type CompanionActionCandidate = ActionCandidate | LocalCompatibilityActionCandidate;

/**
 * Proactive preference controls are local domain requests. They stay outside
 * ActionCandidate so the model envelope can never invoke them.
 */
export type CompanionProactivePreferenceAction = "mute" | "reduce" | "switch_pet";

export interface CompanionProactivePreferenceRequest {
  sourceMessageId: string;
  action: CompanionProactivePreferenceAction;
  targetTitle: string | null;
}

export type CompanionInputSource = "chat" | "quick_input";

export interface CompanionInput {
  requestId: string;
  sessionId: string;
  sourceMessageId: string;

  userId: string;
  petId: string;

  message: string;

  currentTime: string;
  timezone: string;
  utcOffsetMinutes: number;

  source: CompanionInputSource;
  contextEpoch?: CompanionContextEpoch;
  signal?: AbortSignal;
}

/**
 * A CompanionEvent is an opaque projection of an already-created local
 * Task/Reminder fact. It deliberately contains no title, message, status or
 * other domain payload that could cross the Provider boundary.
 */
export type CompanionEvent =
  | {
      id: string;
      type: "REMINDER_DUE";
      reminderId: string;
      reminderInstanceId: string;
    }
  | {
      id: string;
      type: "TASK_DUE_SOON";
      taskId: string;
      minutesLeft: number;
    };

export interface CompanionTurnIdentity {
  requestId: string;
  sessionId: string;
  sourceMessageId: string;
  userId: string;
  petId: string;
}

export type MemoryScope = "global" | `pet:${string}`;

export type MemoryType =
  | "fact"
  | "relationship"
  | "episode"
  | "preference";

export type MemoryCandidateCategory =
  | "profile"
  | "person"
  | "project"
  | "goal"
  | "event"
  | "preference"
  | "shared_experience";

export type MemoryCandidateLifetime = "stable" | "temporal";
export type MemoryCandidateExplicitness = "explicit" | "inferred";
export type MemoryCandidateConfirmationStatus =
  | "not_required"
  | "requires_confirmation"
  | "confirmed";

export interface MemoryCandidate {
  scope: MemoryScope;
  type: MemoryType;
  category: MemoryCandidateCategory;
  /** Compatibility alias; when present it must equal `category`. */
  candidateCategory?: MemoryCandidateCategory;
  lifetime: MemoryCandidateLifetime;
  content: string;
  source: "explicit" | "inferred" | "confirmed";
  evidence: string;
  sourceMessageId: string;
  confidence: number;
  importance: number;
  explicitness: MemoryCandidateExplicitness;
  confirmationStatus: MemoryCandidateConfirmationStatus;
  expiresAt: string | null;
  /** Deprecated compatibility fields derived from confirmationStatus. */
  requiresConfirmation?: boolean;
  confirmed?: boolean;
}

export type MemoryCandidateDecisionStatus =
  | "inserted"
  | "duplicate"
  | "confirmation_required"
  | "rejected"
  | "expired"
  | "superseded"
  | "updated"
  | "failed"
  | "cancelled"
  | "ignored";

export interface MemoryCandidateDecision {
  index: number;
  status: MemoryCandidateDecisionStatus;
  scope?: MemoryScope;
  type?: MemoryType;
  resourceId?: string;
  supersedesId?: string;
  errorCode?: string;
}

export interface CompanionMemoryConfirmationProof {
  candidateId: string;
  sourceMessageId: string;
  confirmationMessageId: string;
  sessionId: string;
  petId: string;
  status: "confirmed";
}

export interface CompanionMemoryConfirmationVerifier {
  verify(
    input: CompanionInput,
    candidate: MemoryCandidate,
    candidateId: string,
    signal: AbortSignal,
  ): CompanionMemoryConfirmationProof | null | Promise<CompanionMemoryConfirmationProof | null>;
}

export interface CompanionModelResponse {
  replyDraft: string;
  actions?: readonly ActionCandidate[];
  memoryCandidates?: readonly MemoryCandidate[];
  /** Count of structured candidates rejected by the local Codec. */
  invalidMemoryCandidateCount?: number;
  /** Original indexes of candidates retained/rejected by the local Codec. */
  memoryCandidateIndexes?: readonly number[];
  invalidMemoryCandidateIndexes?: readonly number[];
  metadata?: {
    provider: string;
    model?: string;
    usage?: {
      inputTokens?: number;
      outputTokens?: number;
    };
  };
  /** Optional echo used by fakes and adapters to make misrouting fail closed. */
  identity?: CompanionTurnIdentity;
}

export type ActionExecutionStatus =
  | "succeeded"
  | "duplicate"
  | "not_found"
  | "ambiguous"
  | "confirmation_required"
  | "rejected"
  | "failed"
  | "cancelled";

export interface ActionExecutionResult {
  type: CompanionActionType;
  status: ActionExecutionStatus;
  resourceId?: string;
  errorCode?: string;
  displayData?: Record<string, string>;
}

export interface CompanionProactivePreferenceExecutionResult {
  type: "proactive_preference";
  action: CompanionProactivePreferenceAction;
  status: ActionExecutionStatus;
  errorCode?: string;
  displayData?: Record<string, string>;
}

/** The only fact-source boundary used by the Phase 4 Action Pipeline. */
export interface CompanionTaskRepository {
  read(): TaskDatabase;
  write(database: TaskDatabase): boolean;
}

export type MemoryPolicyStatus =
  | "not-requested"
  | "succeeded"
  | "ignored"
  | "failed"
  | "cancelled";

export interface MemoryPolicyResult {
  status: MemoryPolicyStatus;
  acceptedCount: number;
  rejectedCount: number;
  decisions: readonly MemoryCandidateDecision[];
  errorCode?: string;
}

export interface CompanionCallCounts {
  /** All calls to a model port, including a local fallback call. */
  model: number;
  /** Calls whose port metadata identifies an external/remote provider. */
  external: number;
  /** Calls whose port metadata identifies a local provider. */
  local: number;
  /** Local calls made only after a remote failure. */
  fallback: number;
}

export type CompanionHarnessErrorKind =
  | CompanionChatProviderErrorKind
  | "domain"
  | "invalid-input"
  | "stale-turn";

export interface CompanionHarnessError {
  kind: CompanionHarnessErrorKind;
  message: string;
  status?: number;
}

export type CompanionResponseStatus =
  | "success"
  | "degraded"
  | "error"
  | "cancelled"
  | "discarded";

export interface CompanionResponse {
  identity: CompanionTurnIdentity;
  status: CompanionResponseStatus;
  text: string | null;
  provider: CompanionModelPortInfo;
  providerDisclosure: string;
  degraded: boolean;
  canCommit: boolean;
  committed: boolean;
  actions: readonly ActionExecutionResult[];
  proactivePreference?: CompanionProactivePreferenceExecutionResult;
  memory: MemoryPolicyResult;
  callCounts: CompanionCallCounts;
  error?: CompanionHarnessError;
  degradedFrom?: CompanionChatProviderErrorKind;
}

export interface CompanionContextBuilder {
  build(
    input: CompanionInput,
    signal: AbortSignal,
  ): Promise<CompanionChatContext> | CompanionChatContext;
}

export interface CompanionActionService {
  process(
    input: CompanionInput,
    candidates: readonly CompanionActionCandidate[],
    signal: AbortSignal,
  ): Promise<readonly ActionExecutionResult[]>;
}

export interface CompanionProactivePreferenceService {
  process(
    input: CompanionInput,
    request: CompanionProactivePreferenceRequest,
    signal: AbortSignal,
  ): Promise<CompanionProactivePreferenceExecutionResult>;
}

export interface CompanionMemoryService {
  process(
    input: CompanionInput,
    candidates: readonly MemoryCandidate[],
    signal: AbortSignal,
  ): Promise<MemoryPolicyResult>;
}

export interface CompanionResponseSink {
  /**
   * The sink must perform its final UI/session mutation through
   * `guard.commitIfCurrent(input, response, ...)`. The guard is the Harness-owned last-moment
   * check for request/session/message identity, the active Turn, and abort.
   */
  commit(
    input: CompanionInput,
    response: CompanionResponse,
    guard: CompanionResponseCommitGuard,
  ): Promise<void> | void;
}

export interface CompanionProactiveEventService {
  /** Handles one already-adapted local event without entering a chat Turn. */
  handleEvent(event: CompanionEvent): Promise<void>;
}

export interface CompanionResponseCommitGuard {
  readonly identity: CompanionTurnIdentity;
  readonly signal: AbortSignal;
  readonly committed: boolean;
  isCurrent(): boolean;
  isCurrentFor(input: CompanionInput, response: CompanionResponse): boolean;
  commitIfCurrent(
    input: CompanionInput,
    response: CompanionResponse,
    mutation: () => void,
  ): boolean;
}

export interface CompanionHarnessDependencies {
  modelPort: CompanionModelPort;
  localFallbackModelPort?: CompanionModelPort;
  contextBuilder?: CompanionContextBuilder;
  actionService?: CompanionActionService;
  proactivePreferenceService?: CompanionProactivePreferenceService;
  proactiveEventService?: CompanionProactiveEventService;
  taskRepository?: CompanionTaskRepository;
  memoryService?: CompanionMemoryService;
  memoryRepository?: MemoryRepository;
  memoryConfirmationVerifier?: CompanionMemoryConfirmationVerifier;
  responseSink?: CompanionResponseSink;
  fallbackToLocal?: boolean;
  timeoutMs?: number;
}

export interface CompanionHarness {
  respond(input: CompanionInput): Promise<CompanionResponse>;
  handleEvent(event: CompanionEvent): Promise<void>;
  /** Cancels the current Turn for a session without touching other sessions. */
  cancel(sessionId: string, requestId?: string): void;
}
