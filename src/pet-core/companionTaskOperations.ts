import {
  cancelTask,
  completeTask,
  postponeTask,
  updateTask,
} from "../task-core/taskStore";
import type { Task, TaskDatabase } from "../task-core/types";
import {
  findTaskReference,
  type TaskOperationCandidate,
} from "./companionTaskExtractor";

export type CompanionTaskOperationResult =
  | { status: "needs_schedule"; database: TaskDatabase; task: null }
  | { status: "not_found"; database: TaskDatabase; task: null }
  | { status: "ambiguous"; database: TaskDatabase; task: null }
  | { status: "unchanged"; database: TaskDatabase; task: Task }
  | { status: "applied"; database: TaskDatabase; task: Task };

/**
 * Applies a provider-independent companion task operation to the existing
 * task fact source. Only operations that change a schedule require a new
 * dueAt; completing or cancelling a task is valid without one.
 */
export function applyCompanionTaskOperationToDatabase(
  database: TaskDatabase,
  operation: TaskOperationCandidate,
  now: Date | string = new Date(),
): CompanionTaskOperationResult {
  const changesSchedule = operation.operation === "postpone" || operation.operation === "reschedule";
  if (changesSchedule && (operation.needsConfirmation || !operation.dueAt)) {
    return { status: "needs_schedule", database, task: null };
  }

  const match = findTaskReference(database, operation.targetTitle);
  if (match.status === "not_found") return { status: "not_found", database, task: null };
  if (match.status === "ambiguous" || !match.task) {
    return { status: "ambiguous", database, task: null };
  }

  let next = database;
  if (operation.operation === "complete") {
    next = completeTask(database, match.task.id, now);
  } else if (operation.operation === "cancel") {
    next = cancelTask(database, match.task.id, now);
  } else if (operation.operation === "postpone") {
    const reminder = database.reminders.find(
      (item) => item.taskId === match.task?.id && item.status === "active" && !item.deletedAt,
    );
    next = postponeTask(
      database,
      match.task.id,
      operation.dueAt!,
      reminder ? operation.remindAt ?? reminder.remindAt : null,
      now,
    );
  } else {
    const reminder = database.reminders.find(
      (item) => item.taskId === match.task?.id && item.status === "active" && !item.deletedAt,
    );
    next = updateTask(database, match.task.id, {
      dueAt: operation.dueAt,
      schedulePrecision: operation.schedulePrecision,
      ...(reminder ? { remindAt: operation.remindAt ?? reminder.remindAt } : {}),
    }, now);
  }

  return next === database
    ? { status: "unchanged", database, task: match.task }
    : { status: "applied", database: next, task: match.task };
}
