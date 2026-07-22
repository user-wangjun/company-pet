import { describe, expect, it } from "vitest";
import { createTask, softDeleteTask, completeTask, rescheduleReminderInstance } from "./taskStore";
import { getLongTermTaskProgress, selectTasks } from "./taskQueries";
import { EMPTY_TASK_DATABASE } from "./taskStore";

describe("task queries", () => {
  it("keeps deleted tasks out of normal lists and exposes them in the recycle bin", () => {
    const created = createTask(EMPTY_TASK_DATABASE, { title: "临时事项" }, "2026-07-13T08:00:00.000Z");
    const deleted = softDeleteTask(created.database, created.task.id, "2026-07-13T09:00:00.000Z");
    expect(selectTasks(deleted, "all")).toHaveLength(0);
    expect(selectTasks(deleted, "trash").map((task) => task.title)).toEqual(["临时事项"]);
  });

  it("selects manually included and due-today tasks for Today without completed tasks", () => {
    const first = createTask(EMPTY_TASK_DATABASE, {
      title: "加入今天",
      includeToday: true,
    }, "2026-07-13T08:00:00.000Z");
    const second = createTask(first.database, {
      title: "今天截止",
      dueAt: "2026-07-13T12:00:00.000Z",
    }, "2026-07-13T08:01:00.000Z");
    const completed = completeTask(second.database, first.task.id, "2026-07-13T09:00:00.000Z");
    expect(selectTasks(completed, "today", new Date("2026-07-13T10:00:00.000Z")).map((task) => task.title)).toEqual(["今天截止"]);
  });

  it("uses current recurring occurrence overrides for Today and upcoming", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "重复模板",
      dueAt: "2026-07-20T12:00:00.000Z",
      remindAt: "2026-07-20T10:00:00.000Z",
      repeatType: "daily",
    }, "2026-07-13T08:00:00.000Z");
    const current = rescheduleReminderInstance(
      created.database,
      created.database.reminderInstances[0].id,
      "2026-07-13T10:30:00.000Z",
      "2026-07-13T08:05:00.000Z",
      { title: "今天这一回", dueAt: "2026-07-13T12:00:00.000Z" },
    );
    const now = new Date("2026-07-13T10:00:00.000Z");
    expect(selectTasks(current, "today", now).map((task) => task.title)).toContain("今天这一回");
    expect(selectTasks(current, "upcoming", now).map((task) => task.title)).toContain("今天这一回");
  });

  it("puts local-date and timed milestones on their chosen day while excluding the parent", () => {
    const parent = createTask(EMPTY_TASK_DATABASE, {
      title: "毕业论文", kind: "long_term", startAt: "2026-07-01", dueAt: "2026-07-30",
      milestones: [
        { title: "全天节点", dueAt: "2026-07-18", schedulePrecision: "date" },
        { title: "定时节点", dueAt: "2026-07-18T06:00:00.000Z", schedulePrecision: "datetime" },
        { title: "未来节点", dueAt: "2026-07-20", schedulePrecision: "date" },
      ],
    }, "2026-07-01T01:00:00.000Z");
    const today = selectTasks(parent.database, "today", new Date("2026-07-18T04:00:00.000Z"));
    expect(today.map((task) => task.title)).toEqual(["全天节点", "定时节点"]);
    expect(today.some((task) => task.kind === "long_term")).toBe(false);
  });

  it("moves an unfinished past milestone to overdue and updates parent progress", () => {
    const parent = createTask(EMPTY_TASK_DATABASE, { title: "长期", kind: "long_term", startAt: "2026-07-01", dueAt: "2026-07-30", milestones: [{ title: "旧节点", dueAt: "2026-07-17" }, { title: "后续", dueAt: "2026-07-20" }] }, "2026-07-01T01:00:00.000Z");
    const overdue = selectTasks(parent.database, "overdue", new Date("2026-07-18T04:00:00.000Z"));
    expect(overdue.map((task) => task.title)).toEqual(["旧节点"]);
    const completed = completeTask(parent.database, parent.database.tasks.find((task) => task.title === "旧节点")!.id, "2026-07-18T05:00:00.000Z");
    expect(getLongTermTaskProgress(completed, completed.tasks.find((task) => task.kind === "long_term")!).completedMilestones).toBe(1);
  });
});
