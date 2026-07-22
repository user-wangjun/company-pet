import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { createTask, triggerDueReminders } from "./taskStore";
import { EMPTY_TASK_DATABASE } from "./taskStore";
import { TaskReminderStack } from "./TaskReminderStack";

const handlers = {
  onComplete: vi.fn(), onOpen: vi.fn(), onOpenAll: vi.fn(), onCloseSummary: vi.fn(), onSnooze: vi.fn(),
};

describe("TaskReminderStack", () => {
  it("shows only completion and ten-minute snooze on a normal task bubble", () => {
    const created = createTask(EMPTY_TASK_DATABASE, { title: "喝水", remindAt: "2026-07-13T10:00:00.000Z" }, "2026-07-13T09:00:00.000Z");
    const triggered = triggerDueReminders(created.database, "2026-07-13T10:00:00.000Z");
    const html = renderToStaticMarkup(<TaskReminderStack reminders={triggered.triggered} {...handlers} />);
    expect(html).toContain("已完成");
    expect(html).toContain("延后10分钟");
    expect(html).not.toContain("取消任务");
  });

  it("summarizes multiple missed reminders instead of rendering a card burst", () => {
    const first = createTask(EMPTY_TASK_DATABASE, { title: "任务一", remindAt: "2026-07-13T08:00:00.000Z" }, "2026-07-13T07:00:00.000Z");
    const second = createTask(first.database, { title: "任务二", remindAt: "2026-07-13T08:10:00.000Z" }, "2026-07-13T07:01:00.000Z");
    const triggered = triggerDueReminders(second.database, "2026-07-13T12:00:00.000Z");
    const html = renderToStaticMarkup(<TaskReminderStack reminders={triggered.triggered} {...handlers} />);
    expect(html).toContain("错过了 2 条提醒");
    expect(html).toContain("查看全部");
    expect(html).toContain("关闭");
    expect(html).not.toContain("任务一");
  });
});
