import {
  extractCompanionMemoryCandidate,
  type CompanionMemoryCandidate,
} from "./companionMemory";
import {
  extractCompanionPreference,
  isForgetRecentPreferenceRequest,
  type CompanionPreferenceExtraction,
} from "./companionPreferences";
import {
  extractTaskCandidate,
  extractTaskOperation,
  type TaskCandidate,
  type TaskExtractorOptions,
  type TaskOperationCandidate,
} from "./companionTaskExtractor";
import {
  parseProactivePreferenceCommand,
  type ProactivePreferenceCommand,
} from "./proactiveTriggerEngine";

export type CompanionChatPipelineRoute =
  | { kind: "pending-task-confirmation" }
  | { kind: "proactive"; command: ProactivePreferenceCommand }
  | { kind: "task-operation"; operation: TaskOperationCandidate }
  | { kind: "task-candidate"; candidate: TaskCandidate }
  | { kind: "forget" }
  | { kind: "preference"; extraction: CompanionPreferenceExtraction }
  | { kind: "memory"; candidate: CompanionMemoryCandidate }
  | { kind: "provider" };

/**
 * The App uses this single route decision before performing side effects.
 * Keeping the order here makes Task, Preference, Memory, forget, and Provider
 * branches testable even while the product-level chat entry remains disabled.
 */
export function resolveCompanionChatPipelineRoute(input: {
  text: string;
  sourceMessageId: string;
  petId: string;
  taskOptions?: TaskExtractorOptions;
  hasPendingTaskCandidate?: boolean;
}): CompanionChatPipelineRoute {
  if (input.hasPendingTaskCandidate) return { kind: "pending-task-confirmation" };

  const proactive = parseProactivePreferenceCommand(input.text);
  if (proactive) return { kind: "proactive", command: proactive };

  const operation = extractTaskOperation(
    input.text,
    input.sourceMessageId,
    input.taskOptions,
  );
  if (operation) return { kind: "task-operation", operation };

  const task = extractTaskCandidate(
    input.text,
    input.sourceMessageId,
    input.taskOptions,
  );
  if (task) return { kind: "task-candidate", candidate: task };

  if (isForgetRecentPreferenceRequest(input.text)) return { kind: "forget" };

  const preference = extractCompanionPreference(input.text);
  if (preference) return { kind: "preference", extraction: preference };

  const memory = extractCompanionMemoryCandidate(
    input.text,
    input.sourceMessageId,
    input.petId,
  );
  if (memory) return { kind: "memory", candidate: memory };

  return { kind: "provider" };
}
