import type { PetManifest } from "./petAssets";
import { resolvePetAssetUrl } from "./petAssets";

export type TaskFeedbackScene =
  | "taskCreated"
  | "taskDue"
  | "taskCompleted"
  | "taskCompletionBurst"
  | "reminderSnoozed"
  | "repeatedSnooze"
  | "taskRescheduled"
  | "taskBurst"
  | "taskOverdue"
  | "dailyReview"
  | "dailyReviewAtLeastHalf"
  | "dailyReviewBelowHalf"
  | "dailyReviewZero";

export type TaskFeedbackEntry = {
  texts: string[];
  action?: string;
  fallbackAction?: string;
  durationMs?: number;
};

export type TaskFeedbackConfig = {
  version: 1;
  scenes: Partial<Record<TaskFeedbackScene, TaskFeedbackEntry>>;
};

export type TaskFeedbackPackage =
  | { status: "ready"; petId: string; config: TaskFeedbackConfig }
  | { status: "not-configured" | "failed"; petId: string };

export async function loadTaskFeedbackPackage(manifest: PetManifest): Promise<TaskFeedbackPackage> {
  if (!manifest.taskFeedbackPath) return { status: "not-configured", petId: manifest.id };
  try {
    const response = await fetch(resolvePetAssetUrl(manifest.id, manifest.taskFeedbackPath));
    if (!response.ok) return { status: "failed", petId: manifest.id };
    const config = await response.json() as TaskFeedbackConfig;
    if (config.version !== 1 || typeof config.scenes !== "object") {
      return { status: "failed", petId: manifest.id };
    }
    return { status: "ready", petId: manifest.id, config };
  } catch {
    return { status: "failed", petId: manifest.id };
  }
}

export function resolveTaskFeedback(
  packageState: TaskFeedbackPackage | undefined,
  scene: TaskFeedbackScene,
  fallbackText: string,
  random = Math.random,
): { text: string; action?: string; fallbackAction?: string; durationMs: number } {
  const entry = packageState?.status === "ready"
    ? packageState.config.scenes[scene]
      ?? (scene === "dailyReviewAtLeastHalf" ? packageState.config.scenes.dailyReview : undefined)
    : undefined;
  const texts = entry?.texts.filter((text) => text.trim()) ?? [];
  return {
    text: texts.length > 0 ? texts[Math.floor(random() * texts.length)] ?? fallbackText : fallbackText,
    action: entry?.action,
    fallbackAction: entry?.fallbackAction,
    durationMs: entry?.durationMs ?? 2200,
  };
}
