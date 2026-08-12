import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import { CompanionChatBubble } from "./CompanionChatBubble";

describe("CompanionChatBubble", () => {
  test("renders bounded message bubbles and the draft input", () => {
    const html = renderToStaticMarkup(
      <CompanionChatBubble
        draft="你好"
        isWaiting={false}
        messages={[
          { id: "1", speaker: "pet", text: "喵？" },
          { id: "2", speaker: "user", text: "今天有点累" },
        ]}
        onDraftChange={vi.fn()}
        onSend={vi.fn()}
        onStop={vi.fn()}
      />,
    );

    expect(html).toContain("companion-chat-messages");
    expect(html).toContain("本地 Provider");
    expect(html).toContain("本地模式：不会发起网络请求");
    expect(html).toContain("喵？");
    expect(html).toContain("今天有点累");
    expect(html).toContain('value="你好"');
  });

  test("shows a stop button while waiting", () => {
    const html = renderToStaticMarkup(
      <CompanionChatBubble
        draft=""
        isWaiting={true}
        messages={[{ id: "1", speaker: "pet", text: "嗯？" }]}
        onDraftChange={vi.fn()}
        onSend={vi.fn()}
        onStop={vi.fn()}
      />,
    );

    expect(html).toContain("撤回");
  });

  test("shows the remote provider, target, and disclosure without credentials", () => {
    const html = renderToStaticMarkup(
      <CompanionChatBubble
        draft=""
        isWaiting={false}
        messages={[{ id: "1", speaker: "pet", text: "嗯？" }]}
        providerInfo={{
          kind: "remote",
          provider: "自定义 Provider",
          target: "https://custom.example/v1beta",
          disclosure:
            "远程模式：本轮必要上下文会发送到远程 AI 服务。",
        }}
        onDraftChange={vi.fn()}
        onSend={vi.fn()}
        onStop={vi.fn()}
      />,
    );

    expect(html).toContain("自定义 Provider");
    expect(html).toContain("https://custom.example/v1beta");
    expect(html).toContain("本轮必要上下文会发送到远程 AI 服务");
  });
});
