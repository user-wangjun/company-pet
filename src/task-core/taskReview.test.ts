import { describe, expect, it } from "vitest";
import { completeTask, createTask, EMPTY_TASK_DATABASE, postponeTask } from "./taskStore";
import { buildDailyTaskReview, formatProjectName } from "./taskReview";

describe("daily task review", () => {
  it("summarizes today's completed and postponed work", () => {
    const today = "2026-07-18T10:00:00.000Z";
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "写今日回顾",
      includeToday: true,
      priority: "high",
      dueAt: "2026-07-18T12:00:00.000Z",
      projectId: "产品",
    }, "2026-07-18T08:00:00.000Z");
    const completed = completeTask(created.database, created.task.id, today);
    const second = createTask(completed, {
      title: "补提醒测试",
      includeToday: true,
      priority: "normal",
      projectId: "工程",
    }, "2026-07-18T09:00:00.000Z");
    const postponed = postponeTask(
      second.database,
      second.task.id,
      "2026-07-19T09:00:00.000Z",
      null,
      "2026-07-18T11:00:00.000Z",
    );

    const review = buildDailyTaskReview(postponed, new Date(today));

    expect(review.completedCount).toBe(1);
    expect(review.postponedCount).toBe(1);
    expect(review.completedTasks[0].task.title).toBe("写今日回顾");
    expect(review.tomorrowFocus[0].title).toBe("补提醒测试");
    expect(review.projectHighlights).toEqual([
      { projectId: "产品", count: 1 },
      { projectId: "工程", count: 1 },
    ]);
  });

  it("uses the zero tier and a no-task label when there is no task activity", () => {
    const review = buildDailyTaskReview(
      EMPTY_TASK_DATABASE,
      new Date("2026-07-18T10:00:00.000Z"),
    );

    expect(review.tone).toBe("zero");
    expect(review.completionLabel).toBe("暂无今日任务");
    expect(review.completionRate).toBeNull();
  });

  it.each([
    [1, 2, "at_least_half"],
    [2, 5, "below_half"],
    [0, 3, "zero"],
  ] as const)("classifies %i/%i as %s", (completedCount, total, tone) => {
    let database = EMPTY_TASK_DATABASE;
    for (let index = 0; index < total; index += 1) {
      const created = createTask(database, { title: `事项${index}`, dueAt: "2026-07-18", schedulePrecision: "date" }, "2026-07-18T01:00:00.000Z");
      database = created.database;
      if (index < completedCount) database = completeTask(database, created.task.id, "2026-07-18T10:00:00.000Z");
    }
    const review = buildDailyTaskReview(database, new Date("2026-07-18T12:00:00.000Z"));
    expect(review.tone).toBe(tone);
    expect(review.completedCount).toBe(completedCount);
    expect(review.effectiveItemCount).toBe(total);
  });

  it("deduplicates repeated postponements and excludes cancelled and long-term parents", () => {
    const parent = createTask(EMPTY_TASK_DATABASE, { title: "毕业论文", kind: "long_term", startAt: "2026-07-01", dueAt: "2026-07-30" }, "2026-07-18T01:00:00.000Z");
    const item = createTask(parent.database, { title: "今天执行", dueAt: "2026-07-18", schedulePrecision: "date" }, "2026-07-18T01:01:00.000Z");
    const once = postponeTask(item.database, item.task.id, "2026-07-19", null, "2026-07-18T02:00:00.000Z");
    const twice = postponeTask(once, item.task.id, "2026-07-20", null, "2026-07-18T03:00:00.000Z");
    const review = buildDailyTaskReview(twice, new Date("2026-07-18T12:00:00.000Z"));
    expect(review.effectiveItemCount).toBe(1);
    expect(review.postponedCount).toBe(2);
  });

  it("formats uncategorized project names for display", () => {
    expect(formatProjectName("uncategorized")).toBe("未分类");
    expect(formatProjectName("学习")).toBe("学习");
  });
});
