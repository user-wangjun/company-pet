import type { TaskFeedbackPackage, TaskFeedbackScene } from "./taskFeedback";
import { resolveTaskFeedback } from "./taskFeedback";
import type {
  ProactiveTaskCandidate,
  ProactiveTriggerDecision,
} from "./proactiveTriggerEngine";

export type ProactiveTaskDelivery = {
  petId: string;
  scene: TaskFeedbackScene;
  text: string;
  durationMs: number;
  taskIds: string[];
};

export type ProactiveTaskDeliveryRoute =
  | {
      status: "deliver" | "switch";
      activePetId: string;
      targetPetId: string;
    }
  | {
      status: "unavailable";
      activePetId: string;
      targetPetId: string;
    };

/**
 * A proactive delivery is rendered only by the pet selected by the engine.
 * With one visible pet window, a different target is an explicit pet switch,
 * never a fallback bubble rendered by the current pet.
 */
export function planProactiveTaskDeliveryRoute(
  decision: ProactiveTriggerDecision,
  activePetId: string,
  availablePetIds: readonly string[] = [decision.petId],
): ProactiveTaskDeliveryRoute {
  if (!availablePetIds.includes(decision.petId)) {
    return {
      status: "unavailable",
      activePetId,
      targetPetId: decision.petId,
    };
  }
  return {
    status: decision.petId === activePetId ? "deliver" : "switch",
    activePetId,
    targetPetId: decision.petId,
  };
}

export function canRenderProactiveTaskDelivery(
  delivery: ProactiveTaskDelivery,
  activePetId: string,
): boolean {
  return delivery.petId === activePetId;
}

export function resolveProactiveTaskDelivery(
  decision: ProactiveTriggerDecision,
  candidates: readonly ProactiveTaskCandidate[],
  packageState: TaskFeedbackPackage | undefined,
): ProactiveTaskDelivery {
  const taskIds = decision.aggregatedTaskIds ?? [decision.taskId];
  const firstTask = candidates.find((candidate) => candidate.taskId === decision.taskId);
  const scene: TaskFeedbackScene = decision.result === "aggregate" ? "taskBurst" : "taskDue";
  const fallbackText = decision.result === "aggregate"
    ? `有 ${taskIds.length} 件事需要留意，我们一件一件来。`
    : `该做「${firstTask?.title ?? "这件事"}」啦。`;
  const feedback = resolveTaskFeedback(packageState, scene, fallbackText, () => 0);
  return {
    petId: decision.petId,
    scene,
    text: feedback.text,
    durationMs: feedback.durationMs,
    taskIds,
  };
}
