import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import type { CompanionChatMessage, CompanionChatProviderInfo } from "./companionChatRuntime";
import { LOCAL_COMPANION_CHAT_PROVIDER_INFO } from "./companionChatRuntime";
import { PlatformCompanionChatDrawer } from "./PlatformCompanionChatDrawer";
import {
  CompanionOllamaPullProgress,
  type BundledOllamaPullProgress,
} from "./CompanionOllamaPullProgress";

export type PlatformCompanionChatPageProps = {
  petName: string;
  petPreviewUrl?: string;
  petPreviewKind?: "image" | "spritesheet";
  messages: CompanionChatMessage[];
  draft: string;
  isWaiting: boolean;
  providerInfo?: CompanionChatProviderInfo;
  ollamaPullProgress?: BundledOllamaPullProgress | null;
  onDraftChange: (draft: string) => void;
  onSend: () => void;
  onStop: () => void;
  onClose: () => void;
  onBack?: () => void;
  onRetry?: () => void;
};

function CompanionChatMessages({
  messages,
  isWaiting,
  copiedMessageId,
  onRetry,
  onCopy,
}: {
  messages: CompanionChatMessage[];
  isWaiting: boolean;
  copiedMessageId: string | null;
  onRetry?: () => void;
  onCopy: (message: CompanionChatMessage) => void;
}) {
  const lastMessage = messages[messages.length - 1];
  const canRetry = Boolean(
    onRetry
      && !isWaiting
      && lastMessage?.speaker === "pet"
      && messages.some((message) => message.speaker === "user"),
  );

  if (messages.length === 0) {
    return (
      <div className="platform-companion-chat-empty" role="status">
        <span aria-hidden="true">◌</span>
        <strong>想和我说点什么吗？</strong>
        <p>不用想得很完整，想到哪里就说到哪里。</p>
      </div>
    );
  }

  return messages.map((message) => (
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
        <button type="button" onClick={() => onCopy(message)}>
          {copiedMessageId === message.id ? "已复制" : "复制"}
        </button>
        {canRetry && message.id === lastMessage?.id ? (
          <button type="button" onClick={onRetry}>
            再试一次
          </button>
        ) : null}
      </div>
    </div>
  ));
}

function CompanionRoomScene() {
  return (
    <div className="platform-companion-chat-room-scene" aria-label="陪伴房卧室场景">
      <div className="platform-companion-chat-room-scene-glow" aria-hidden="true" />
      <div className="platform-companion-chat-room-hotspot is-window" aria-hidden="true" />
      <div className="platform-companion-chat-room-hotspot is-bed" aria-hidden="true" />
    </div>
  );
}

function CompanionRoomPet({
  petName,
  petPreviewUrl,
  petPreviewKind,
}: Pick<
  PlatformCompanionChatPageProps,
  "petName" | "petPreviewUrl" | "petPreviewKind"
>) {
  return (
    <div className="platform-companion-chat-room-pet-layer" aria-hidden="true">
      <div className="platform-companion-chat-room-pet-shadow" aria-hidden="true" />
      <div
        className={`platform-companion-chat-room-pet is-${petPreviewKind}`}
        role="img"
        aria-label={`${petName}在陪伴房里`}
        style={petPreviewUrl ? { backgroundImage: `url(${petPreviewUrl})` } : undefined}
      />
    </div>
  );
}

export function PlatformCompanionChatPage({
  petName,
  petPreviewUrl,
  petPreviewKind = "image",
  messages,
  draft,
  isWaiting,
  providerInfo = LOCAL_COMPANION_CHAT_PROVIDER_INFO,
  ollamaPullProgress,
  onDraftChange,
  onSend,
  onStop,
  onClose,
  onBack,
  onRetry,
}: PlatformCompanionChatPageProps) {
  const messagesRef = useRef<HTMLDivElement>(null);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [isRecordOpen, setIsRecordOpen] = useState(false);

  useEffect(() => {
    const container = messagesRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [messages]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSend();
  };

  const handleInputKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    if (!isWaiting && draft.trim()) onSend();
  };

  const copyMessage = async (message: CompanionChatMessage) => {
    if (typeof navigator === "undefined" || !navigator.clipboard?.writeText) return;
    try {
      await navigator.clipboard.writeText(message.text);
      setCopiedMessageId(message.id);
      window.setTimeout(() => {
        setCopiedMessageId((current) => (current === message.id ? null : current));
      }, 1600);
    } catch {
      // Clipboard permissions are optional; the companion room remains usable.
    }
  };

  // The room keeps only a small live preview. The complete visible record is
  // available from the read-only drawer and is never a second input surface.
  const visibleMessages = messages.slice(-3);
  const messageList = (
    <CompanionChatMessages
      messages={visibleMessages}
      isWaiting={isWaiting}
      copiedMessageId={copiedMessageId}
      onRetry={onRetry}
      onCopy={(message) => void copyMessage(message)}
    />
  );

  return (
    <div
      className="platform-companion-chat-room-shell"
      onPointerDown={(event) => event.stopPropagation()}
    >
      <section
        className="platform-companion-chat-room"
        aria-label={`${petName}陪伴房`}
        onPointerDown={(event) => event.stopPropagation()}
      >
        <header className="platform-companion-chat-header platform-companion-chat-room-header">
          <div className="platform-companion-chat-room-leading">
            <button
              className="platform-companion-chat-back"
              type="button"
              aria-label="返回首页"
              onClick={onBack ?? onClose}
            >
              <span aria-hidden="true">‹</span>
              返回首页
            </button>
            <div className="platform-companion-chat-identity">
              <span
                className={`platform-companion-chat-avatar is-${petPreviewKind}`}
                aria-hidden="true"
                style={petPreviewUrl ? { backgroundImage: `url(${petPreviewUrl})` } : undefined}
              />
              <div>
                <span className="platform-companion-chat-room-kicker">陪伴房</span>
                <strong>{petName}</strong>
                <span>
                  <i className="platform-companion-chat-status-dot" aria-hidden="true" />
                  陪伴中 · {isWaiting ? "正在回复" : "安静陪伴"}
                </span>
              </div>
            </div>
          </div>

          <div className="platform-companion-chat-header-actions platform-companion-chat-room-actions">
            <button
              className="platform-companion-chat-record-toggle"
              type="button"
              onClick={() => setIsRecordOpen(true)}
            >
              本次陪伴记录
            </button>
            <button
              className="platform-companion-chat-close"
              type="button"
              aria-label="关闭陪伴"
              onClick={onClose}
            >
              ×
            </button>
          </div>
        </header>

        <div
          className={`platform-companion-chat-provider platform-companion-chat-room-provider is-${providerInfo.kind}`}
          role="status"
          title={providerInfo.disclosure}
        >
          <div>
            <i className="platform-companion-chat-provider-dot" aria-hidden="true" />
            <strong>{providerInfo.provider}</strong>
            <span>{providerInfo.target}</span>
          </div>
          <small>{providerInfo.disclosure}</small>
        </div>
        <CompanionOllamaPullProgress progress={ollamaPullProgress} />

        <div className="platform-companion-chat-room-body">
          <CompanionRoomScene />
          <CompanionRoomPet
            petName={petName}
            petPreviewUrl={petPreviewUrl}
            petPreviewKind={petPreviewKind}
          />
          <div className="platform-companion-chat-room-content">
            <div
              className="platform-companion-chat-messages platform-companion-chat-room-messages"
              ref={messagesRef}
            >
              {messageList}
            </div>
          </div>
        </div>

        <form className="platform-companion-chat-input platform-companion-chat-room-input" onSubmit={submit}>
          <div className="platform-companion-chat-input-field">
            <textarea
              aria-label="陪伴房聊天输入"
              placeholder="在陪伴房里轻轻说一句…"
              rows={2}
              value={draft}
              onChange={(event) => onDraftChange(event.currentTarget.value)}
              onKeyDown={handleInputKeyDown}
            />
            <small>Enter 发送 · Shift+Enter 换行</small>
          </div>
          {isWaiting ? (
            <button type="button" onClick={(event) => {
              // The same form slot becomes a submit button after stopping;
              // prevent the click's default action before that synchronous
              // replacement can submit the form a second time.
              event.preventDefault();
              onStop();
            }}>
              停止
            </button>
          ) : (
            <button type="submit" disabled={!draft.trim()}>
              发送
            </button>
          )}
        </form>
      </section>

      {isRecordOpen ? (
        <PlatformCompanionChatDrawer
          petName={petName}
          messages={messages}
          providerInfo={providerInfo}
          onClose={() => setIsRecordOpen(false)}
        />
      ) : null}
    </div>
  );
}
