import { selectActiveLongTermTasks, selectTasks, type LongTermTaskProgress } from "./taskQueries";
import { isSameLocalDay, scheduledLocalDate, toLocalDateKey } from "./taskStore";
import type { Task, TaskDatabase, TaskHistoryEntry } from "./types";

export type DailyReviewTone = "at_least_half" | "below_half" | "zero";

export type DailyReviewTask = Pick<Task, "id" | "title" | "priority" | "projectId" | "dueAt" | "kind" | "parentTaskId">;

export type DailyReviewCompletion = { entry: TaskHistoryEntry; task: DailyReviewTask };

export type DailyTaskReview = {
  completedCount: number;
  effectiveItemCount: number;
  completionRate: number | null;
  completionLabel: string;
  postponedCount: number;
  cancelledCount: number;
  overdueCount: number;
  remainingTodayCount: number;
  tone: DailyReviewTone;
  headline: string;
  completedTasks: DailyReviewCompletion[];
  tomorrowFocus: DailyReviewTask[];
  projectHighlights: Array<{ projectId: string; count: number }>;
  longTermProgress: LongTermTaskProgress[];
  completedLongTermTasks: DailyReviewTask[];
};

function uniqueTasks(tasks: Task[]): Task[] {
  const seen = new Set<string>();
  return tasks.filter((task) => !seen.has(task.id) && Boolean(seen.add(task.id)));
}

function taskSnapshot(task: Task): DailyReviewTask {
  return { id: task.id, title: task.title, priority: task.priority, projectId: task.projectId, dueAt: task.dueAt, kind: task.kind, parentTaskId: task.parentTaskId };
}

function getReviewTone(completedCount: number, effectiveItemCount: number): DailyReviewTone {
  if (completedCount === 0 || effectiveItemCount === 0) return "zero";
  return completedCount / effectiveItemCount >= 0.5 ? "at_least_half" : "below_half";
}

function getHeadline(completedCount: number, effectiveItemCount: number, tone: DailyReviewTone): string {
  if (effectiveItemCount === 0) return "今天暂无明确安排，按自己的节奏收尾就好。";
  if (tone === "at_least_half") return `今天完成 ${completedCount} / ${effectiveItemCount} 项，已经推进了不少。`;
  if (tone === "below_half") return `今天完成 ${completedCount} / ${effectiveItemCount} 项，迈出的每一步都算数。`;
  return `今天有 ${effectiveItemCount} 项安排，还没有留下完成记录。`;
}

export function buildDailyTaskReview(database: TaskDatabase, now = new Date()): DailyTaskReview {
  const todayHistory = database.history.filter((entry) => isSameLocalDay(entry.createdAt, now));
  const taskById = new Map(database.tasks.map((task) => [task.id, task]));
  const eligible = (task: Task | undefined) => Boolean(task && task.kind !== "long_term" && !task.deletedAt && task.status !== "cancelled");
  const plannedEligible = (task: Task | undefined) => Boolean(eligible(task) && task!.status !== "completed");

  const completedTasks = todayHistory
    .filter((entry) => entry.type === "completed")
    .flatMap((entry) => {
      const task = taskById.get(entry.taskId);
      return eligible(task) ? [{ entry, task: taskSnapshot(task!) }] : [];
    })
    .sort((a, b) => b.entry.createdAt.localeCompare(a.entry.createdAt));

  const effectiveIds = new Set<string>();
  for (const task of database.tasks) {
    if (!plannedEligible(task)) continue;
    if (isSameLocalDay(task.dueAt, now) || task.includeToday) effectiveIds.add(task.id);
  }
  for (const instance of database.reminderInstances) {
    const task = taskById.get(instance.taskId);
    if (plannedEligible(task) && isSameLocalDay(instance.scheduledAt, now)) effectiveIds.add(instance.taskId);
  }
  for (const completion of completedTasks) effectiveIds.add(completion.task.id);
  for (const entry of todayHistory.filter((item) => item.type === "postponed")) {
    const task = taskById.get(entry.taskId);
    if (plannedEligible(task) && (isSameLocalDay(entry.fromAt, now) || task!.includeToday)) effectiveIds.add(entry.taskId);
  }

  const completedIds = new Set(completedTasks.map(({ task }) => task.id));
  const completedCount = [...completedIds].filter((id) => effectiveIds.has(id)).length;
  const effectiveItemCount = effectiveIds.size;
  const completionRate = effectiveItemCount > 0 ? completedCount / effectiveItemCount : null;
  const tone = getReviewTone(completedCount, effectiveItemCount);

  const overdue = selectTasks(database, "overdue", now);
  const remainingToday = selectTasks(database, "today", now);
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const tomorrowKey = toLocalDateKey(tomorrow);
  const tomorrowTasks = database.tasks.filter((task) => plannedEligible(task) && scheduledLocalDate(task.dueAt) === tomorrowKey);
  const tomorrowFocus = uniqueTasks([...overdue, ...remainingToday, ...tomorrowTasks]).slice(0, 3).map(taskSnapshot);

  const projectCounts = new Map<string, number>();
  for (const { task } of completedTasks) projectCounts.set(task.projectId, (projectCounts.get(task.projectId) ?? 0) + 1);
  for (const task of remainingToday) projectCounts.set(task.projectId, (projectCounts.get(task.projectId) ?? 0) + 1);

  const completedLongTermTasks = todayHistory
    .filter((entry) => entry.type === "completed")
    .flatMap((entry) => {
      const task = taskById.get(entry.taskId);
      return task?.kind === "long_term" ? [taskSnapshot(task)] : [];
    });

  return {
    completedCount,
    effectiveItemCount,
    completionRate,
    completionLabel: completionRate === null ? "暂无今日任务" : `${Math.round(completionRate * 100)}%`,
    postponedCount: todayHistory.filter((entry) => entry.type === "postponed").length,
    cancelledCount: todayHistory.filter((entry) => entry.type === "cancelled").length,
    overdueCount: overdue.length,
    remainingTodayCount: remainingToday.length,
    tone,
    headline: getHeadline(completedCount, effectiveItemCount, tone),
    completedTasks: completedTasks.slice(0, 3),
    tomorrowFocus,
    projectHighlights: [...projectCounts.entries()].map(([projectId, count]) => ({ projectId, count })).sort((a, b) => b.count - a.count || a.projectId.localeCompare(b.projectId)).slice(0, 3),
    longTermProgress: selectActiveLongTermTasks(database, now),
    completedLongTermTasks,
  };
}

export function formatProjectName(projectId: string): string {
  return projectId === "uncategorized" ? "未分类" : projectId;
}
