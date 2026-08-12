import { useEffect, useRef, useState } from "react";
import type {
  CompanionChatMessage,
  CompanionChatProviderInfo,
} from "./companionChatRuntime";
import { LOCAL_COMPANION_CHAT_PROVIDER_INFO } from "./companionChatRuntime";

export type PlatformCompanionChatRecordProps = {
  petName: string;
  messages: CompanionChatMessage[];
  providerInfo?: CompanionChatProviderInfo;
  onClose: () => void;
};

/**
 * The old platform chat drawer is now a read-only record surface. Sending is
 * intentionally owned by the companion room, so this surface cannot create a
 * second chat mode by accident.
 */
export function PlatformCompanionChatDrawer({
  petName,
  messages,
  providerInfo = LOCAL_COMPANION_CHAT_PROVIDER_INFO,
  onClose,
}: PlatformCompanionChatRecordProps) {
  const messagesRef = useRef<HTMLDivElement>(null);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);

  useEffect(() => {
    const container = messagesRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [messages]);

  const copyMessage = async (message: CompanionChatMessage) => {
    if (typeof navigator === "undefined" || !navigator.clipboard?.writeText) return;
    try {
      await navigator.clipboard.writeText(message.text);
      setCopiedMessageId(message.id);
      window.setTimeout(() => {
        setCopiedMessageId((current) => (current === message.id ? null : current));
      }, 1600);
    } catch {
      // Clipboard permissions are optional; the record itself remains usable.
    }
  };

  return (
    <div
      className="platform-companion-chat-record-backdrop"
      role="presentation"
      onPointerDown={(event) => {
        event.stopPropagation();
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="platform-companion-chat-record-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={`${petName}本次陪伴记录`}
        onPointerDown={(event) => event.stopPropagation()}
      >
        <header className="platform-companion-chat-header">
          <div className="platform-companion-chat-identity">
            <div>
              <span className="platform-companion-chat-record-kicker">本次陪伴记录</span>
              <strong>{petName}</strong>
              <span>只读查看 · 不会开启新的聊天</span>
            </div>
          </div>
          <button
            className="platform-companion-chat-close"
            type="button"
            aria-label="关闭本次陪伴记录"
            onClick={onClose}
          >
            ×
          </button>
        </header>

        <div className={`platform-companion-chat-provider is-${providerInfo.kind}`} role="status">
          <div>
            <strong>{providerInfo.provider}</strong>
            <span>{providerInfo.target}</span>
          </div>
          <small>{providerInfo.disclosure}</small>
        </div>

        <div className="platform-companion-chat-messages platform-companion-chat-record-messages" ref={messagesRef}>
          {messages.length === 0 ? (
            <div className="platform-companion-chat-empty" role="status">
              <span aria-hidden="true">◌</span>
              <strong>这次还没有留下消息</strong>
              <p>回到陪伴房后，想说的话会出现在这里。</p>
            </div>
          ) : (
            messages.map((message) => (
              <div
                className={`platform-companion-message-row is-${message.speaker}`}
                key={message.id}
              >
                <div
                  className={`platform-companion-message is-${message.speaker}${message.status === "error" ? " is-error" : ""}`}
                  role={message.status === "error" ? "alert" : undefined}
                >
                  {message.text}
                </div>
                <div className="platform-companion-message-actions">
                  {message.status === "error" ? (
                    <span className="platform-companion-message-error-label">发送失败</span>
                  ) : null}
                  <button type="button" onClick={() => void copyMessage(message)}>
                    {copiedMessageId === message.id ? "已复制" : "复制"}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
