import { isSameLocalDay, scheduledLocalDate, scheduledTime, toLocalDateKey } from "./taskStore";
import type { Task, TaskDatabase } from "./types";

export type TaskListView = "today" | "all" | "upcoming" | "overdue" | "completed" | "cancelled" | "trash" | "settings";

export type LongTermTaskProgress = {
  task: Task;
  completedMilestones: number;
  totalMilestones: number;
  remainingDays: number | null;
  state: "ongoing" | "completed" | "overdue" | "continuous";
};

function active(task: Task): boolean {
  return !task.deletedAt && !["completed", "cancelled"].includes(task.status);
}

export function isTaskOverdue(task: Task, now = new Date()): boolean {
  if (!active(task) || task.kind === "long_term" || !task.dueAt) return false;
  if (task.schedulePrecision === "date") {
    return (scheduledLocalDate(task.dueAt) ?? "") < toLocalDateKey(now);
  }
  return scheduledTime(task.dueAt) < now.getTime();
}

export function getLongTermTaskProgress(
  database: TaskDatabase,
  task: Task,
  now = new Date(),
): LongTermTaskProgress {
  const milestones = database.tasks.filter((item) => item.parentTaskId === task.id && !item.deletedAt);
  const completedMilestones = milestones.filter((item) => item.status === "completed").length;
  const dueDate = scheduledLocalDate(task.dueAt);
  const remainingDays = dueDate
    ? Math.ceil((scheduledTime(dueDate) - scheduledTime(toLocalDateKey(now))) / 86_400_000)
    : null;
  const state = task.status === "completed"
    ? "completed"
    : !dueDate
      ? "continuous"
      : remainingDays !== null && remainingDays < 0
        ? "overdue"
        : "ongoing";
  return { task, completedMilestones, totalMilestones: milestones.length, remainingDays, state };
}

export function selectActiveLongTermTasks(database: TaskDatabase, now = new Date()): LongTermTaskProgress[] {
  return database.tasks
    .filter((task) => task.kind === "long_term" && active(task))
    .map((task) => getLongTermTaskProgress(database, task, now))
    .sort((a, b) => scheduledTime(a.task.dueAt) - scheduledTime(b.task.dueAt));
}

export function selectTasks(database: TaskDatabase, view: TaskListView, now = new Date()): Task[] {
  const nowMs = now.getTime();
  const twoHours = nowMs + 2 * 60 * 60 * 1000;
  const currentInstanceByTask = new Map(
    database.reminderInstances
      .filter((instance) => ["scheduled", "triggered", "missed"].includes(instance.status))
      .sort((a, b) => b.scheduledAt.localeCompare(a.scheduledAt))
      .map((instance) => [instance.taskId, instance]),
  );
  const reminderAt = new Map(
    database.reminders.filter((item) => item.status === "active" && !item.deletedAt)
      .map((item) => [item.taskId, new Date(currentInstanceByTask.get(item.taskId)?.scheduledAt ?? item.remindAt).getTime()]),
  );
  if (view === "settings") return [];
  if (view === "trash") {
    const deletedParents = new Set(database.tasks.filter((task) => task.deletedAt && task.kind !== "milestone").map((task) => task.id));
    return database.tasks
      .filter((task) => Boolean(task.deletedAt) && !(task.parentTaskId && deletedParents.has(task.parentTaskId)))
      .sort((a, b) => (b.deletedAt ?? "").localeCompare(a.deletedAt ?? ""));
  }
  const resolvedTasks = database.tasks.map((task) => ({ ...task, ...(currentInstanceByTask.get(task.id)?.taskOverrides ?? {}) }));
  const visible = resolvedTasks.filter((task) => !task.deletedAt).filter((task) => {
    if (view === "completed") return task.status === "completed";
    if (view === "cancelled") return task.status === "cancelled" && !task.archivedAt;
    if (view === "overdue") return isTaskOverdue(task, now);
    if (view === "upcoming") {
      const at = reminderAt.get(task.id);
      return task.kind !== "long_term" && active(task) && at !== undefined && at >= nowMs && at <= twoHours;
    }
    if (view === "today") {
      if (task.kind === "long_term") return false;
      const hasActiveTriggeredReminder = database.reminderInstances.some(
        (instance) => instance.taskId === task.id && ["triggered", "missed"].includes(instance.status),
      );
      return active(task) && (task.includeToday || isSameLocalDay(task.dueAt, now) || hasActiveTriggeredReminder);
    }
    return task.kind !== "milestone" || Boolean(task.parentTaskId);
  });

  const priority = { high: 0, normal: 1, low: 2 };
  return visible.sort((a, b) => {
    if (view === "today") {
      const aOverdue = isTaskOverdue(a, now);
      const bOverdue = isTaskOverdue(b, now);
      if (aOverdue !== bOverdue) return aOverdue ? -1 : 1;
      const aAllDay = a.schedulePrecision === "date";
      const bAllDay = b.schedulePrecision === "date";
      if (aAllDay !== bAllDay) return aAllDay ? -1 : 1;
      const aReminderDistance = Math.abs((reminderAt.get(a.id) ?? Number.MAX_SAFE_INTEGER) - nowMs);
      const bReminderDistance = Math.abs((reminderAt.get(b.id) ?? Number.MAX_SAFE_INTEGER) - nowMs);
      if (aReminderDistance !== bReminderDistance) return aReminderDistance - bReminderDistance;
    }
    if (priority[a.priority] !== priority[b.priority]) return priority[a.priority] - priority[b.priority];
    return scheduledTime(a.dueAt) - scheduledTime(b.dueAt) || b.createdAt.localeCompare(a.createdAt);
  });
}
