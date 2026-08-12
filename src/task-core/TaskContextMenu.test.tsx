import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { TaskContextMenu } from "./TaskContextMenu";

describe("TaskContextMenu", () => {
  it("keeps the task shortcuts and exposes the explicit companion-chat entry", () => {
    const html = renderToStaticMarkup(
      <TaskContextMenu
        placement="right"
        onClose={vi.fn()}
        onHidePet={vi.fn()}
        onOpenChat={vi.fn()}
        onOpenReminders={vi.fn()}
        onOpenSettings={vi.fn()}
        onOpenToday={vi.fn()}
        onQuickCreate={vi.fn()}
      />,
    );

    expect(html).toContain("今日任务");
    expect(html).toContain("新建任务");
    expect(html).toContain("陪我聊聊");
    expect(html).toContain("快捷提醒");
    expect(html).toContain("提醒设置");
    expect(html).toContain("暂时隐藏桌宠");
  });
});
