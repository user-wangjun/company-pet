import type { FormEvent } from "react";
import type { CompanionChatMessage } from "./companionChatRuntime";

type CompanionChatBubbleProps = {
  messages: CompanionChatMessage[];
  draft: string;
  isWaiting: boolean;
  onDraftChange: (draft: string) => void;
  onSend: () => void;
  onStop: () => void;
};

export function CompanionChatBubble({
  messages,
  draft,
  isWaiting,
  onDraftChange,
  onSend,
  onStop,
}: CompanionChatBubbleProps) {
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSend();
  };

  return (
    <section
      className="companion-chat"
      aria-label="宠物聊天"
      onPointerDown={(event) => event.stopPropagation()}
      onMouseDown={(event) => event.stopPropagation()}
      onClick={(event) => event.stopPropagation()}
    >
      <div className="companion-chat-messages">
        {messages.map((message) => (
          <div
            className={`companion-message is-${message.speaker}`}
            key={message.id}
          >
            {message.text}
          </div>
        ))}
      </div>
      <form className="companion-chat-input-row" onSubmit={submit}>
        <input
          aria-label="聊天输入"
          value={draft}
          onChange={(event) => onDraftChange(event.currentTarget.value)}
        />
        {isWaiting ? (
          <button type="button" onClick={onStop}>
            撤回
          </button>
        ) : (
          <button type="submit" disabled={!draft.trim()}>
            发送
          </button>
        )}
      </form>
    </section>
  );
}
