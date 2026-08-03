import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { completeTask, createTask, softDeleteTask } from "./taskStore";
import { EMPTY_TASK_DATABASE } from "./taskStore";
import { TaskWorkspace } from "./TaskWorkspace";

describe("TaskWorkspace", () => {
  it("renders the four PRD Today sections", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "今日事项",
      includeToday: true,
    }, new Date());
    const html = renderToStaticMarkup(
      <TaskWorkspace database={created.database} onChange={vi.fn()} />,
    );
    for (const label of ["过期事项", "当前与即将提醒", "今日待办", "今日已完成"]) {
      expect(html).toContain(label);
    }
    expect(html).toContain("今日事项");
  });

  it("renders deleted tasks in the recycle-bin view with restore affordance", () => {
    const created = createTask(EMPTY_TASK_DATABASE, { title: "被删除事项" }, "2026-07-13T08:00:00.000Z");
    const deleted = softDeleteTask(created.database, created.task.id, "2026-07-13T09:00:00.000Z");
    const html = renderToStaticMarkup(
      <TaskWorkspace database={deleted} initialView="trash" onChange={vi.fn()} />,
    );
    expect(html).toContain("被删除事项");
    expect(html).toContain("删除的事项会保留30天");
    expect(html).toContain("恢复 被删除事项");
  });

  it("shows a recurring occurrence in today's completion history while keeping its template pending", () => {
    const now = new Date();
    const remindAt = new Date(now.getTime() - 60_000).toISOString();
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "每日复盘",
      remindAt,
      repeatType: "daily",
    }, new Date(now.getTime() - 120_000));
    const completed = completeTask(created.database, created.task.id, now);
    expect(completed.tasks[0].status).toBe("pending");
    const html = renderToStaticMarkup(
      <TaskWorkspace database={completed} onChange={vi.fn()} />,
    );
    expect(html).toContain("今日已完成 · 1");
    expect(html).toContain("每日复盘");
  });

  it("renders local reminder and sound settings", () => {
    const html = renderToStaticMarkup(
      <TaskWorkspace database={EMPTY_TASK_DATABASE} initialView="settings" onChange={vi.fn()} />,
    );
    expect(html).toContain("提示音");
    expect(html).toContain("界面字体大小");
    expect(html).toContain('option value="extraLarge"');
    expect(html).toContain("系统");
    expect(html).toContain("宠物");
    expect(html).toContain("自定义");
    expect(html).toContain("后台提醒");
    expect(html).toContain("这些数据只保存在本机");
  });

  it("groups long-term milestones under their parent card", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "毕业论文",
      kind: "long_term",
      startAt: "2026-07-01",
      milestones: [{ title: "完成初稿", dueAt: new Date().toISOString(), schedulePrecision: "datetime" }],
    }, "2026-07-01T01:00:00.000Z");
    const html = renderToStaticMarkup(
      <TaskWorkspace database={created.database} onChange={vi.fn()} />,
    );
    expect(html).toContain("长期任务");
    expect(html).toContain("毕业论文");
    expect(html).toContain("当前节点：完成初稿");
    expect(html).not.toContain("来自：毕业论文");
  });

  it("offers a collapsible time chain for ordinary tasks", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "检查桌宠提醒动作与气泡",
    }, "2026-07-19T08:00:00.000Z");
    const html = renderToStaticMarkup(
      <TaskWorkspace database={created.database} initialView="all" onChange={vi.fn()} />,
    );
    expect(html).toContain("展开时间链");
    expect(html).toContain("aria-expanded=\"false\"");
  });
});
