import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import { PlatformCompanionChatDrawer } from "./PlatformCompanionChatDrawer";
import { PlatformCompanionChatPage } from "./PlatformCompanionChatPage";

const callbacks = {
  onDraftChange: vi.fn(),
  onSend: vi.fn(),
  onStop: vi.fn(),
  onClose: vi.fn(),
  onBack: vi.fn(),
  onRetry: vi.fn(),
};

describe("PlatformCompanionChatDrawer", () => {
  test("renders the current companion record as a read-only secondary surface", () => {
    const html = renderToStaticMarkup(
      <PlatformCompanionChatDrawer
        petName="ikun"
        messages={[
          { id: "pet-1", speaker: "pet", text: "我在呢。" },
          { id: "user-1", speaker: "user", text: "今天有点累" },
          {
            id: "error-1",
            speaker: "pet",
            text: "聊天服务暂时没接上，稍后再试。",
            status: "error",
          },
        ]}
        onClose={callbacks.onClose}
      />,
    );

    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-label="ikun本次陪伴记录"');
    expect(html).toContain("本次陪伴记录");
    expect(html).toContain("只读查看");
    expect(html).toContain("复制");
    expect(html).toContain("发送失败");
    expect(html).not.toContain("<textarea");
    expect(html).not.toContain("<input");
    expect(html).not.toContain(">发送<");
    expect(html).not.toContain(">停止<");
    expect(html).not.toContain(">再试一次<");
    expect(html).not.toContain("新聊天");
    expect(html).not.toContain("最近陪伴");
  });

  test("renders an empty read-only record without any chat controls", () => {
    const html = renderToStaticMarkup(
      <PlatformCompanionChatDrawer
        petName="ikun"
        messages={[]}
        onClose={callbacks.onClose}
      />,
    );

    expect(html).toContain("这次还没有留下消息");
    expect(html).toContain("关闭本次陪伴记录");
    expect(html).not.toContain("<form");
    expect(html).not.toContain("<textarea");
    expect(html).not.toContain(">发送<");
    expect(html).not.toContain(">停止<");
    expect(html).not.toContain(">重试<");
  });

  test("renders one default companion room and exposes the record entry", () => {
    const html = renderToStaticMarkup(
      <PlatformCompanionChatPage
        petName="ikun"
        messages={[{ id: "pet-1", speaker: "pet", text: "我在呢。" }]}
        draft=""
        isWaiting={false}
        {...callbacks}
      />,
    );

    expect(html).toContain('aria-label="ikun陪伴房"');
    expect(html).toContain("platform-companion-chat-room-shell");
    expect(html).toContain("platform-companion-chat-room");
    expect(html).toContain("platform-companion-chat-room-scene");
    expect(html).toContain("platform-companion-chat-room-pet");
    expect(html).toContain("本次陪伴记录");
    expect(html).toContain("陪伴房聊天输入");
    expect(html).toContain("发送");
    expect(html).not.toContain("聊天模式");
    expect(html).not.toContain("页面");
    expect(html).not.toContain("platform-companion-chat-mode-switch");
    expect(html).not.toContain("initialViewMode");
  });

  test("keeps the active room input separate from the read-only record", () => {
    const html = renderToStaticMarkup(
      <PlatformCompanionChatPage
        petName="ikun"
        messages={[
          { id: "pet-1", speaker: "pet", text: "我在呢。" },
          { id: "user-1", speaker: "user", text: "今天有点累" },
        ]}
        draft="今天有点累"
        isWaiting={true}
        {...callbacks}
      />,
    );

    expect(html).toContain("<textarea");
    expect(html).toContain("停止");
    expect(html).toContain("本次陪伴记录");
    expect(html).not.toContain("传统聊天页");
    expect(html).not.toContain("页面模式");
  });
});
