import { describe, expect, it } from "vitest";
import {
  EMPTY_TASK_DATABASE,
  completeTask,
  completeReminderInstance,
  closeMissedReminderSummary,
  createTask,
  dismissReminderInstance,
  getActiveTriggeredReminders,
  markUnattendedReminders,
  permanentlyDeleteTask,
  readTaskDatabase,
  reconcileTaskTimezone,
  rescheduleReminderInstance,
  postponeTask,
  purgeExpiredTrash,
  restoreTask,
  softDeleteTask,
  syncLongTermMilestones,
  snoozeReminderInstance,
  triggerDueReminders,
  updateTask,
  updateTaskSettings,
} from "./taskStore";

describe("task store", () => {
  it("creates a title-only task without inventing a reminder", () => {
    const result = createTask(EMPTY_TASK_DATABASE, { title: "  写周报  " }, "2026-07-13T01:00:00.000Z");
    expect(result.task.title).toBe("写周报");
    expect(result.task.status).toBe("pending");
    expect(result.database.reminders).toHaveLength(0);
    expect(result.task.attachmentRefs).toEqual([]);
  });

  it("stores normalized attachment references", () => {
    const result = createTask(EMPTY_TASK_DATABASE, {
      title: "整理资料",
      attachmentRefs: [" C:\\docs\\brief.pdf ", "https://example.test/spec", "C:\\docs\\brief.pdf"],
    }, "2026-07-13T01:00:00.000Z");
    expect(result.task.attachmentRefs).toEqual(["C:\\docs\\brief.pdf", "https://example.test/spec"]);
  });

  it("triggers each reminder instance only once", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "喝水",
      remindAt: "2026-07-13T01:10:00.000Z",
    }, "2026-07-13T01:00:00.000Z");
    const first = triggerDueReminders(created.database, "2026-07-13T01:10:00.000Z");
    const second = triggerDueReminders(first.database, "2026-07-13T01:11:00.000Z");
    expect(first.triggered).toHaveLength(1);
    expect(second.triggered).toHaveLength(0);
    expect(getActiveTriggeredReminders(second.database)).toHaveLength(1);
  });

  it("snoozes an instance without changing its task deadline", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "提交材料",
      dueAt: "2026-07-13T04:00:00.000Z",
      remindAt: "2026-07-13T02:00:00.000Z",
    }, "2026-07-13T01:00:00.000Z");
    const triggered = triggerDueReminders(created.database, "2026-07-13T02:00:00.000Z");
    const instance = triggered.triggered[0].instance;
    const snoozed = snoozeReminderInstance(triggered.database, instance.id, 10, "2026-07-13T02:01:00.000Z");
    expect(snoozed.tasks[0].dueAt).toBe("2026-07-13T04:00:00.000Z");
    expect(snoozed.reminderInstances[snoozed.reminderInstances.length - 1]?.scheduledAt).toBe("2026-07-13T02:11:00.000Z");
  });

  it("records deadline postponement separately", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "复盘",
      dueAt: "2026-07-13T03:00:00.000Z",
    }, "2026-07-13T01:00:00.000Z");
    const postponed = postponeTask(created.database, created.task.id, "2026-07-14T03:00:00.000Z", null, "2026-07-13T02:00:00.000Z");
    expect(postponed.tasks[0].postponedCount).toBe(1);
    expect(postponed.history[postponed.history.length - 1]?.type).toBe("postponed");
  });

  it("advances a recurring task instead of cancelling future reminders", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "站会",
      dueAt: "2026-07-13T02:00:00.000Z",
      remindAt: "2026-07-13T01:55:00.000Z",
      repeatType: "daily",
    }, "2026-07-13T01:00:00.000Z");
    const completed = completeTask(created.database, created.task.id, "2026-07-13T02:00:00.000Z");
    expect(completed.tasks[0].status).toBe("pending");
    expect(completed.reminders[0].status).toBe("active");
    expect(completed.reminderInstances[completed.reminderInstances.length - 1]?.scheduledAt).toBe("2026-07-14T01:55:00.000Z");
  });

  it("does not complete an already handled task twice", () => {
    const created = createTask(EMPTY_TASK_DATABASE, { title: "归档" }, "2026-07-13T01:00:00.000Z");
    const first = completeTask(created.database, created.task.id, "2026-07-13T02:00:00.000Z");
    const second = completeTask(first, created.task.id, "2026-07-13T02:01:00.000Z");
    expect(second).toBe(first);
    expect(second.history).toHaveLength(1);
  });

  it("keeps a recurring template time stable when the current instance is snoozed", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "晨间整理",
      remindAt: "2026-07-13T01:00:00.000Z",
      repeatType: "daily",
    }, "2026-07-13T00:00:00.000Z");
    const triggered = triggerDueReminders(created.database, "2026-07-13T01:00:00.000Z");
    const snoozed = snoozeReminderInstance(triggered.database, triggered.triggered[0].instance.id, 10, "2026-07-13T01:01:00.000Z");
    expect(snoozed.reminders[0].remindAt).toBe("2026-07-13T01:00:00.000Z");
    expect(snoozed.reminderInstances[snoozed.reminderInstances.length - 1].scheduledAt).toBe("2026-07-13T01:11:00.000Z");
  });

  it("handles recurring completion once per reminder instance", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "每日回顾",
      remindAt: "2026-07-13T10:00:00.000Z",
      repeatType: "daily",
    }, "2026-07-13T09:00:00.000Z");
    const triggered = triggerDueReminders(created.database, "2026-07-13T10:00:00.000Z");
    const instanceId = triggered.triggered[0].instance.id;
    const first = completeReminderInstance(triggered.database, instanceId, "2026-07-13T10:01:00.000Z");
    const second = completeReminderInstance(first, instanceId, "2026-07-13T10:02:00.000Z");
    expect(second).toBe(first);
    expect(first.reminders[0].remindAt).toBe("2026-07-14T10:00:00.000Z");
    expect(first.history.filter((entry) => entry.type === "completed")).toHaveLength(1);
  });

  it("skips stale recurring occurrences and schedules strictly in the future", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "每日整理",
      remindAt: "2026-07-13T10:00:00.000Z",
      repeatType: "daily",
    }, "2026-07-13T09:00:00.000Z");
    const triggered = triggerDueReminders(created.database, "2026-07-20T10:00:00.000Z");
    const completed = completeReminderInstance(
      triggered.database,
      triggered.triggered[0].instance.id,
      "2026-07-20T10:01:00.000Z",
    );
    expect(completed.reminders[0].remindAt).toBe("2026-07-21T10:00:00.000Z");
    expect(new Date(completed.reminderInstances[completed.reminderInstances.length - 1].scheduledAt).getTime())
      .toBeGreaterThan(new Date("2026-07-20T10:01:00.000Z").getTime());
  });

  it("replaces the pending reminder instance when a task reminder is edited", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "交设计稿",
      remindAt: "2026-07-13T10:00:00.000Z",
    }, "2026-07-13T09:00:00.000Z");
    const previousInstanceId = created.database.reminderInstances[0].id;
    const updated = updateTask(created.database, created.task.id, {
      title: "交最终设计稿",
      remindAt: "2026-07-13T11:00:00.000Z",
      repeatType: "weekly",
    }, "2026-07-13T09:10:00.000Z");
    expect(updated.tasks[0].title).toBe("交最终设计稿");
    expect(updated.reminders[0].remindAt).toBe("2026-07-13T11:00:00.000Z");
    expect(updated.reminders[0].repeatType).toBe("weekly");
    expect(updated.reminderInstances.find((item) => item.id === previousInstanceId)?.status).toBe("cancelled");
    expect(updated.reminderInstances.filter((item) => item.status === "scheduled")).toHaveLength(1);
  });

  it("dismisses one recurring occurrence and schedules the next occurrence", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "每日服药",
      remindAt: "2026-07-13T10:00:00.000Z",
      repeatType: "daily",
    }, "2026-07-13T09:00:00.000Z");
    const triggered = triggerDueReminders(created.database, "2026-07-13T10:00:00.000Z");
    const dismissed = dismissReminderInstance(
      triggered.database,
      triggered.triggered[0].instance.id,
      "2026-07-13T10:01:00.000Z",
    );
    expect(dismissed.tasks[0].status).toBe("pending");
    expect(dismissed.reminderInstances.find((item) => item.id === triggered.triggered[0].instance.id)?.status).toBe("dismissed");
    expect(dismissed.reminders[0].remindAt).toBe("2026-07-14T10:00:00.000Z");
    expect(dismissed.reminderInstances[dismissed.reminderInstances.length - 1]?.scheduledAt).toBe("2026-07-14T10:00:00.000Z");
  });

  it("reschedules only the current recurring instance without changing its template", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "每周例会",
      remindAt: "2026-07-13T10:00:00.000Z",
      repeatType: "weekly",
    }, "2026-07-13T09:00:00.000Z");
    const instanceId = created.database.reminderInstances[0].id;
    const updated = rescheduleReminderInstance(
      created.database,
      instanceId,
      "2026-07-13T11:30:00.000Z",
      "2026-07-13T09:10:00.000Z",
    );
    expect(updated.reminders[0].remindAt).toBe("2026-07-13T10:00:00.000Z");
    expect(updated.reminderInstances.find((item) => item.id === instanceId)?.status).toBe("cancelled");
    expect(updated.reminderInstances[updated.reminderInstances.length - 1].scheduledAt).toBe("2026-07-13T11:30:00.000Z");
  });

  it("stores task edits on only the current recurring instance", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "模板标题",
      remindAt: "2026-07-13T10:00:00.000Z",
      repeatType: "daily",
    }, "2026-07-13T09:00:00.000Z");
    const instanceId = created.database.reminderInstances[0].id;
    const updated = rescheduleReminderInstance(
      created.database,
      instanceId,
      "2026-07-13T11:00:00.000Z",
      "2026-07-13T09:05:00.000Z",
      { title: "仅今天的标题", note: "仅今天的备注" },
    );
    expect(updated.tasks[0].title).toBe("模板标题");
    expect(updated.reminders[0].remindAt).toBe("2026-07-13T10:00:00.000Z");
    expect(updated.reminderInstances[updated.reminderInstances.length - 1]?.taskOverrides).toMatchObject({ title: "仅今天的标题", note: "仅今天的备注" });
  });

  it("keeps current occurrence overrides after snoozing", () => {
    const created = createTask(EMPTY_TASK_DATABASE, { title: "模板", remindAt: "2026-07-13T10:00:00.000Z", repeatType: "daily" }, "2026-07-13T09:00:00.000Z");
    const changed = rescheduleReminderInstance(created.database, created.database.reminderInstances[0].id, "2026-07-13T10:05:00.000Z", "2026-07-13T09:05:00.000Z", { title: "仅本次" });
    const due = triggerDueReminders(changed, "2026-07-13T10:05:00.000Z");
    const snoozed = snoozeReminderInstance(due.database, due.triggered[0].instance.id, 10, "2026-07-13T10:05:00.000Z");
    expect(snoozed.reminderInstances[snoozed.reminderInstances.length - 1].taskOverrides?.title).toBe("仅本次");
  });

  it("persists closing a missed reminder summary without completing tasks", () => {
    const created = createTask(EMPTY_TASK_DATABASE, { title: "错过事项", remindAt: "2026-07-13T08:00:00.000Z" }, "2026-07-13T07:00:00.000Z");
    const missed = triggerDueReminders(created.database, "2026-07-13T12:00:00.000Z");
    const closed = closeMissedReminderSummary(missed.database, "2026-07-13T12:01:00.000Z");
    expect(closed.tasks[0].status).toBe("pending");
    expect(closed.reminderInstances[0].status).toBe("missed");
    expect(closed.reminderInstances[0].summaryClosedAt).toBe("2026-07-13T12:01:00.000Z");
    expect(getActiveTriggeredReminders(closed)).toHaveLength(0);
  });

  it("deletes only a scheduled recurring occurrence and keeps a future instance", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "每周清单",
      remindAt: "2026-07-13T10:00:00.000Z",
      repeatType: "weekly",
    }, "2026-07-13T09:00:00.000Z");
    const instanceId = created.database.reminderInstances[0].id;
    const dismissed = dismissReminderInstance(created.database, instanceId, "2026-07-13T09:10:00.000Z");
    expect(dismissed.reminderInstances.find((item) => item.id === instanceId)?.status).toBe("dismissed");
    expect(dismissed.reminderInstances[dismissed.reminderInstances.length - 1].scheduledAt).toBe("2026-07-20T10:00:00.000Z");
    expect(dismissed.reminders[0].status).toBe("active");
  });

  it("restores a deleted task and only revives a future one-off reminder", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "预约体检",
      remindAt: "2026-07-15T10:00:00.000Z",
    }, "2026-07-13T09:00:00.000Z");
    const deleted = {
      ...created.database,
      tasks: created.database.tasks.map((task) => ({ ...task, status: "cancelled" as const, deletedAt: "2026-07-13T10:00:00.000Z" })),
      reminders: created.database.reminders.map((reminder) => ({ ...reminder, status: "cancelled" as const })),
    };
    const restored = restoreTask(deleted, created.task.id, "2026-07-14T09:00:00.000Z");
    expect(restored.tasks[0].deletedAt).toBeNull();
    expect(restored.tasks[0].status).toBe("pending");
    expect(restored.reminders[0].status).toBe("active");
    expect(restored.reminderInstances.filter((item) => item.status === "scheduled").length).toBeGreaterThan(0);
  });

  it("purges recycle-bin tasks after thirty days with their dependent records", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "过期回收项",
      remindAt: "2026-06-01T10:00:00.000Z",
    }, "2026-06-01T09:00:00.000Z");
    const trashed = {
      ...created.database,
      tasks: created.database.tasks.map((task) => ({ ...task, deletedAt: "2026-06-01T12:00:00.000Z" })),
    };
    const purged = purgeExpiredTrash(trashed, "2026-07-13T12:00:00.000Z");
    expect(purged.tasks).toHaveLength(0);
    expect(purged.reminders).toHaveLength(0);
    expect(purged.reminderInstances).toHaveLength(0);
    expect(purged.metrics.trash_purged).toBe(1);
  });

  it("permanently deletes a recycle-bin task and its dependent records", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "立刻清理",
      remindAt: "2026-07-13T10:00:00.000Z",
    }, "2026-07-13T09:00:00.000Z");
    const trashed = {
      ...created.database,
      tasks: created.database.tasks.map((task) => ({ ...task, deletedAt: "2026-07-13T09:30:00.000Z" })),
    };
    const deleted = permanentlyDeleteTask(trashed, created.task.id);
    expect(deleted.tasks).toHaveLength(0);
    expect(deleted.reminders).toHaveLength(0);
    expect(deleted.reminderInstances).toHaveLength(0);
    expect(deleted.metrics.trash_deleted_permanently).toBe(1);
  });

  it("records local task and reminder metrics", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "喝水",
      remindAt: "2026-07-13T10:00:00.000Z",
    }, "2026-07-13T09:00:00.000Z");
    const triggered = triggerDueReminders(created.database, "2026-07-13T10:00:00.000Z");
    expect(triggered.database.metrics.task_created).toBe(1);
    expect(triggered.database.metrics.reminder_triggered).toBe(1);
  });

  it("migrates older local task data to default reminder settings", () => {
    const legacy = JSON.stringify({
      schemaVersion: 1,
      tasks: [], reminders: [], reminderInstances: [], history: [], metrics: {},
    });
    const database = readTaskDatabase({ getItem: () => legacy });
    expect(database.settings).toEqual(EMPTY_TASK_DATABASE.settings);
  });

  it("migrates schema v1 tasks without losing linked reminders or history and is idempotent", () => {
    const legacyTask = {
      id: "legacy", title: "旧任务", note: "保留", status: "pending", priority: "normal", projectId: "uncategorized",
      dueAt: "2026-07-18T09:00:00.000Z", includeToday: true, attachmentRefs: [], completedAt: null, cancelledAt: null,
      postponedCount: 0, createdAt: "2026-07-17T09:00:00.000Z", updatedAt: "2026-07-17T09:00:00.000Z", deletedAt: null, version: 1, sourceDeviceId: "local",
    };
    const payload = { schemaVersion: 1, tasks: [legacyTask], reminders: [{ id: "r", taskId: "legacy" }], reminderInstances: [], history: [{ id: "h", taskId: "legacy" }], metrics: {} };
    const migrated = readTaskDatabase({ getItem: () => JSON.stringify(payload) });
    expect(migrated.schemaVersion).toBe(2);
    expect(migrated.tasks[0]).toMatchObject({ kind: "single", parentTaskId: null, startAt: null, schedulePrecision: "datetime", dueAt: legacyTask.dueAt });
    expect(migrated.reminders[0].taskId).toBe("legacy");
    expect(migrated.history[0].taskId).toBe("legacy");
    const again = readTaskDatabase({ getItem: () => JSON.stringify(migrated) });
    expect(again).toEqual(migrated);
  });

  it("degrades an orphan milestone to a single task", () => {
    const created = createTask(EMPTY_TASK_DATABASE, { title: "普通" }, "2026-07-18T01:00:00.000Z");
    const orphan = { ...created.task, kind: "milestone", parentTaskId: "missing" };
    const migrated = readTaskDatabase({ getItem: () => JSON.stringify({ ...created.database, tasks: [orphan] }) });
    expect(migrated.tasks[0]).toMatchObject({ kind: "single", parentTaskId: null });
  });

  it("keeps real timeline milestones under an ordinary task and cascades parent completion", () => {
    const parent = createTask(EMPTY_TASK_DATABASE, { title: "发布网页预览" }, "2026-07-19T01:00:00.000Z");
    const child = createTask(parent.database, {
      title: "检查交互",
      kind: "milestone",
      parentTaskId: parent.task.id,
      dueAt: "2026-07-19",
      schedulePrecision: "date",
    }, "2026-07-19T02:00:00.000Z");
    const reloaded = readTaskDatabase({ getItem: () => JSON.stringify(child.database) });
    expect(reloaded.tasks.find((task) => task.id === child.task.id)).toMatchObject({
      kind: "milestone",
      parentTaskId: parent.task.id,
    });
    const completed = completeTask(reloaded, parent.task.id, "2026-07-19T03:00:00.000Z");
    expect(completed.tasks.find((task) => task.id === child.task.id)).toMatchObject({
      status: "cancelled",
      archiveReason: "parent_completed",
    });
    expect(completed.history.filter((entry) => entry.type === "completed").map((entry) => entry.taskId)).toEqual([parent.task.id]);
    expect(() => createTask(parent.database, {
      title: "跨到次日",
      kind: "milestone",
      parentTaskId: parent.task.id,
      dueAt: "2026-07-20",
    }, "2026-07-19T04:00:00.000Z")).toThrow("节点日期必须位于任务的开始和结束日期之间");
  });

  it("migrates an undated ordinary task onto its own creation day", () => {
    const created = createTask(EMPTY_TASK_DATABASE, { title: "当日任务" }, "2026-07-19T08:00:00.000Z");
    const undated = { ...created.task, dueAt: null, schedulePrecision: "datetime" as const };
    const migrated = readTaskDatabase({ getItem: () => JSON.stringify({ ...created.database, tasks: [undated] }) });
    expect(migrated.tasks[0]).toMatchObject({ dueAt: "2026-07-19", schedulePrecision: "date" });
  });

  it("creates, synchronizes and completes milestones without auto-completing the parent", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "毕业论文", kind: "long_term", startAt: "2026-07-01", dueAt: "2026-07-30",
      milestones: [{ title: "完成初稿", dueAt: "2026-07-12T06:00:00.000Z", schedulePrecision: "datetime", remindAt: "2026-07-12T05:30:00.000Z" }],
    }, "2026-07-01T01:00:00.000Z");
    const milestone = created.database.tasks.find((task) => task.kind === "milestone")!;
    expect(milestone.parentTaskId).toBe(created.task.id);
    expect(created.database.reminders.find((reminder) => reminder.taskId === milestone.id)?.repeatType).toBe("none");
    const completed = completeTask(created.database, milestone.id, "2026-07-10T03:00:00.000Z");
    expect(completed.tasks.find((task) => task.id === created.task.id)?.status).toBe("pending");
    expect(completed.tasks.find((task) => task.id === milestone.id)?.completedAt).toBe("2026-07-10T03:00:00.000Z");
    const synced = syncLongTermMilestones(completed, created.task.id, [{ id: milestone.id, title: "完成终稿", dueAt: "2026-07-20", schedulePrecision: "date" }], "2026-07-10T04:00:00.000Z");
    expect(synced.tasks.find((task) => task.id === milestone.id)?.title).toBe("完成终稿");
  });

  it("preserves exact start and cutoff times for long-term tasks", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "精确周期",
      kind: "long_term",
      startAt: "2026-07-21T01:15:00.000Z",
      dueAt: "2026-07-28T10:45:00.000Z",
      schedulePrecision: "datetime",
    }, "2026-07-20T01:00:00.000Z");
    expect(created.task.startAt).toBe("2026-07-21T01:15:00.000Z");
    expect(created.task.dueAt).toBe("2026-07-28T10:45:00.000Z");

    const updated = updateTask(created.database, created.task.id, {
      startAt: "2026-07-21T02:30:00.000Z",
    }, "2026-07-20T02:00:00.000Z");
    expect(updated.tasks[0].startAt).toBe("2026-07-21T02:30:00.000Z");

    const reloaded = readTaskDatabase({ getItem: () => JSON.stringify(updated) });
    expect(reloaded.tasks[0].startAt).toBe("2026-07-21T02:30:00.000Z");
  });

  it("keeps date-only long-term bounds date-only through create, edit and reload", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "按日期推进",
      kind: "long_term",
      startAt: "2026-07-21",
      dueAt: "2026-07-28",
      schedulePrecision: "date",
    }, "2026-07-20T01:00:00.000Z");
    expect(created.task).toMatchObject({
      startAt: "2026-07-21",
      dueAt: "2026-07-28",
      schedulePrecision: "date",
    });

    const edited = updateTask(created.database, created.task.id, {
      dueAt: "2026-07-29T10:45:00.000Z",
    }, "2026-07-20T02:00:00.000Z");
    expect(edited.tasks[0]).toMatchObject({
      dueAt: "2026-07-29T10:45:00.000Z",
      schedulePrecision: "datetime",
    });

    const restoredToDate = updateTask(edited, created.task.id, {
      dueAt: "2026-07-30",
    }, "2026-07-20T03:00:00.000Z");
    const reloaded = readTaskDatabase({ getItem: () => JSON.stringify(restoredToDate) });
    expect(reloaded.tasks[0]).toMatchObject({
      startAt: "2026-07-21",
      dueAt: "2026-07-30",
      schedulePrecision: "date",
    });
  });

  it("preserves independent start and cutoff precision for mixed long-term bounds", () => {
    const timedStart = createTask(EMPTY_TASK_DATABASE, {
      title: "精确开始",
      kind: "long_term",
      startAt: "2026-07-21T01:15:00.000Z",
      dueAt: "2026-07-28",
      schedulePrecision: "date",
    }, "2026-07-20T01:00:00.000Z").task;
    expect(timedStart).toMatchObject({
      startAt: "2026-07-21T01:15:00.000Z",
      dueAt: "2026-07-28",
      schedulePrecision: "date",
    });

    const timedCutoff = createTask(EMPTY_TASK_DATABASE, {
      title: "精确截止",
      kind: "long_term",
      startAt: "2026-07-21",
      dueAt: "2026-07-28T10:45:00.000Z",
      schedulePrecision: "datetime",
    }, "2026-07-20T01:00:00.000Z").task;
    expect(timedCutoff).toMatchObject({
      startAt: "2026-07-21",
      dueAt: "2026-07-28T10:45:00.000Z",
      schedulePrecision: "datetime",
    });
  });

  it("infers missing legacy schedule precision without changing date-only or datetime values", () => {
    const dateTask = createTask(EMPTY_TASK_DATABASE, {
      title: "旧日期",
      dueAt: "2026-07-21",
      schedulePrecision: "date",
    }, "2026-07-20T01:00:00.000Z").task;
    const datetimeTask = createTask(EMPTY_TASK_DATABASE, {
      title: "旧时间",
      dueAt: "2026-07-21T09:15:00.000Z",
      schedulePrecision: "datetime",
    }, "2026-07-20T01:00:00.000Z").task;
    const { schedulePrecision: _datePrecision, ...legacyDateTask } = dateTask;
    const { schedulePrecision: _datetimePrecision, ...legacyDatetimeTask } = datetimeTask;
    const migrated = readTaskDatabase({
      getItem: () => JSON.stringify({
        ...EMPTY_TASK_DATABASE,
        schemaVersion: 1,
        tasks: [legacyDateTask, legacyDatetimeTask],
      }),
    });

    expect(migrated.tasks[0]).toMatchObject({
      dueAt: "2026-07-21",
      schedulePrecision: "date",
    });
    expect(migrated.tasks[1]).toMatchObject({
      dueAt: "2026-07-21T09:15:00.000Z",
      schedulePrecision: "datetime",
    });
  });

  it("cascades long-term trash, restore and permanent deletion", () => {
    const created = createTask(EMPTY_TASK_DATABASE, { title: "长期", kind: "long_term", startAt: "2026-07-01", milestones: [{ title: "节点", dueAt: "2026-07-18" }] }, "2026-07-01T01:00:00.000Z");
    const completedChild = completeTask(created.database, created.database.tasks.find((task) => task.kind === "milestone")!.id, "2026-07-17T02:00:00.000Z");
    const trashed = softDeleteTask(completedChild, created.task.id, "2026-07-18T02:00:00.000Z");
    expect(trashed.tasks.every((task) => Boolean(task.deletedAt))).toBe(true);
    const restored = restoreTask(trashed, created.task.id, "2026-07-18T03:00:00.000Z");
    expect(restored.tasks.every((task) => !task.deletedAt)).toBe(true);
    expect(restored.tasks.find((task) => task.kind === "milestone")?.status).toBe("completed");
    const trashedAgain = softDeleteTask(restored, created.task.id, "2026-07-18T04:00:00.000Z");
    const removed = permanentlyDeleteTask(trashedAgain, created.task.id);
    expect(removed.tasks).toHaveLength(0);
  });

  it("archives unfinished milestones when a long-term task is completed without forging completion history", () => {
    const created = createTask(EMPTY_TASK_DATABASE, { title: "长期", kind: "long_term", startAt: "2026-07-01", milestones: [{ title: "节点", dueAt: "2026-07-20" }] }, "2026-07-01T01:00:00.000Z");
    const completed = completeTask(created.database, created.task.id, "2026-07-18T04:00:00.000Z");
    const milestone = completed.tasks.find((task) => task.kind === "milestone")!;
    expect(milestone).toMatchObject({ status: "cancelled", archiveReason: "parent_completed" });
    expect(completed.history.filter((entry) => entry.type === "completed").map((entry) => entry.taskId)).toEqual([created.task.id]);
  });

  it("updates reminder preferences locally", () => {
    const updated = updateTaskSettings(EMPTY_TASK_DATABASE, {
      notificationSound: "custom",
      customNotificationSoundName: "ding.wav",
      customNotificationSoundDataUrl: "data:audio/wav;base64,AAAA",
      customNotificationSoundDurationMs: 1200,
      backgroundReminders: false,
      bubbleDurationMinutes: 3,
    });
    expect(updated.settings.notificationSound).toBe("custom");
    expect(updated.settings.customNotificationSoundName).toBe("ding.wav");
    expect(updated.settings.customNotificationSoundDurationMs).toBe(1200);
    expect(updated.settings.backgroundReminders).toBe(false);
    expect(updated.settings.bubbleDurationMinutes).toBe(3);
    expect(updated.metrics.settings_updated).toBe(1);
  });

  it("recalculates pending reminders after a timezone change without touching triggered instances", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "跨时区会议",
      remindAt: "2026-07-13T10:00:00.000Z",
    }, "2026-07-13T09:00:00.000Z");
    const oldOffset = 0;
    const database = { ...created.database, settings: { ...created.database.settings, timezoneOffsetMinutes: oldOffset } };
    const adjusted = reconcileTaskTimezone(database, 60, "2026-07-13T09:30:00.000Z");
    expect(adjusted.reminders[0].remindAt).toBe("2026-07-13T11:00:00.000Z");
    expect(adjusted.reminderInstances[0].scheduledAt).toBe("2026-07-13T11:00:00.000Z");
    expect(adjusted.settings.timezoneOffsetMinutes).toBe(60);
    expect(adjusted.metrics.timezone_reconciled).toBe(1);
  });

  it("marks an ignored task bubble as missed without completing the task", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "稍后处理",
      remindAt: "2026-07-13T10:00:00.000Z",
    }, "2026-07-13T09:00:00.000Z");
    const triggered = triggerDueReminders(created.database, "2026-07-13T10:00:00.000Z");
    const aged = markUnattendedReminders(triggered.database, "2026-07-13T10:05:00.000Z");
    expect(aged.tasks[0].status).toBe("pending");
    expect(aged.reminderInstances[0].status).toBe("missed");
    expect(aged.metrics.reminder_unattended).toBe(1);
  });
});
