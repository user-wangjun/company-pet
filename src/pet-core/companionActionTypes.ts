import type {
  ActionCandidate,
  CompanionActionCandidate,
  CompanionActionConfirmationProof,
  CompanionActionType,
  CompanionInput,
  CompanionPreferenceRequest,
  CompanionProactivePreferenceRequest,
  CompanionLocalActionType,
  CompanionTaskRepository,
  LocalCompatibilityActionCandidate,
  MemoryCandidate,
} from "./companionHarnessTypes";
import type { CompanionChatPipelineRoute } from "./companionChatPipeline";
import type {
  TaskCandidateExplicitness,
  TaskCandidateRiskLevel,
} from "./companionTaskExtractor";

export type { CompanionTaskRepository } from "./companionHarnessTypes";

/**
 * Evidence produced from the current user message by the deterministic local
 * extractor. Model text, model intent and model-repeated evidence never fill
 * this contract.
 */
export interface LocalActionEvidence {
  sourceMessageId: string;
  explicitness: TaskCandidateExplicitness;
  evidence: string;
  normalizedTarget: string | null;
  dueAt: string | null;
  triggerAt: string | null;
  timezone: string | null;
  /** CompanionInput convention: local time minus UTC; adapt before legacy TaskExtractor use. */
  utcOffsetMinutes: number;
  actionType: CompanionActionType;
  idempotencyKey: string;
  requiresConfirmation: boolean;
  riskLevel: TaskCandidateRiskLevel;
}

export interface LocalRequestHints {
  route: CompanionChatPipelineRoute;
  localOwned: boolean;
  action: CompanionActionCandidate | null;
  memoryCandidate: MemoryCandidate | null;
  evidence: LocalActionEvidence | null;
  proactivePreference: CompanionProactivePreferenceRequest | null;
  preference: CompanionPreferenceRequest | null;
  forget: boolean;
}

export interface ActionPolicyContext {
  input: CompanionInput;
  candidate: CompanionActionCandidate;
  evidence: LocalActionEvidence | null;
  database: import("../task-core/types").TaskDatabase;
  signal: AbortSignal;
  isCurrent: () => boolean;
  idempotency: ReadonlyMap<string, import("./companionHarnessTypes").ActionExecutionResult>;
  confirmation?: CompanionActionConfirmationProof;
}

export type ActionPolicyDecision =
  | {
      status: "authorized";
      action: CompanionActionCandidate;
      evidence: LocalActionEvidence;
      idempotencyKey: string;
    }
  | {
      status: "rejected";
      result: import("./companionHarnessTypes").ActionExecutionResult;
    };

export interface ActionHandlerContext {
  input: CompanionInput;
  database: import("../task-core/types").TaskDatabase;
  repository: CompanionTaskRepository;
  evidence: LocalActionEvidence;
  signal: AbortSignal;
  isCurrent: () => boolean;
}

export interface CompanionActionHandler {
  readonly type: CompanionActionType;
  execute(
    candidate: CompanionActionCandidate,
    context: ActionHandlerContext,
  ): Promise<import("./companionHarnessTypes").ActionExecutionResult> | import("./companionHarnessTypes").ActionExecutionResult;
}

export type FormalActionCandidate = ActionCandidate;
export type LocalActionCandidate = LocalCompatibilityActionCandidate;
export type { CompanionActionCandidate, CompanionActionType, CompanionLocalActionType };
