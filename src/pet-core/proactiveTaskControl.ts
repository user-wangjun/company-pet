import type { Task, TaskDatabase } from "../task-core/types";
import { findTaskReference } from "./companionTaskExtractor";
import type { ProactivePreferenceCommand } from "./proactiveTriggerEngine";
import type { ProactiveTaskDeliveryContext } from "./proactiveExpressionGate";
import { normalizeProactiveTaskTarget } from "./proactiveTriggerEngine";

export const PROACTIVE_TASK_CONTEXT_MAX_AGE_MS = 24 * 60 * 60 * 1000;

export type ProactiveTaskControlResolution =
  | { status: "resolved"; task: Task; source: "context" | "title" }
  | { status: "needs-title"; reason: "missing-context" | "ambiguous-context" | "stale-context" }
  | { status: "not-found"; targetTitle: string }
  | { status: "ambiguous"; targetTitle: string };

function isActiveTask(task: Task): boolean {
  return !task.deletedAt && !["completed", "cancelled"].includes(task.status);
}

function isRecentContext(
  context: ProactiveTaskDeliveryContext,
  now: Date,
  maxAgeMs: number,
): boolean {
  const deliveredAt = Date.parse(context.deliveredAt);
  return Number.isFinite(deliveredAt)
    && deliveredAt <= now.getTime()
    && now.getTime() - deliveredAt <= maxAgeMs;
}

export function resolveProactiveTaskControlTarget(
  command: ProactivePreferenceCommand,
  database: TaskDatabase,
  context: ProactiveTaskDeliveryContext | null,
  now = new Date(),
  maxAgeMs = PROACTIVE_TASK_CONTEXT_MAX_AGE_MS,
): ProactiveTaskControlResolution {
  const explicitTitle = command.targetTitle
    ? normalizeProactiveTaskTarget(command.targetTitle)
    : "";
  if (explicitTitle) {
    const match = findTaskReference(database, explicitTitle);
    if (match.status === "not_found") return { status: "not-found", targetTitle: explicitTitle };
    if (match.status === "ambiguous" || !match.task) {
      return { status: "ambiguous", targetTitle: explicitTitle };
    }
    return { status: "resolved", task: match.task, source: "title" };
  }

  if (!context) return { status: "needs-title", reason: "missing-context" };
  if (context.taskIds.length !== 1 || context.taskTitles.length !== 1) {
    return { status: "needs-title", reason: "ambiguous-context" };
  }
  if (!isRecentContext(context, now, maxAgeMs)) {
    return { status: "needs-title", reason: "stale-context" };
  }

  const task = database.tasks.find((candidate) => candidate.id === context.taskIds[0]);
  if (!task || !isActiveTask(task)) {
    return { status: "needs-title", reason: "stale-context" };
  }
  return { status: "resolved", task, source: "context" };
}
