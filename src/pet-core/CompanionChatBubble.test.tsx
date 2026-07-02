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
});
