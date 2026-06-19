import {
  canDeleteReadLetters,
  getUnreadCount,
  getVisibleLetters,
  isLetterRead,
  type MailboxState,
  type PlatformLetter,
} from "./mailbox";

type MailboxPanelProps = {
  letters: PlatformLetter[];
  state: MailboxState;
  onClose: () => void;
  onDeleteRead: () => void;
  onMarkAllRead: () => void;
  onOpenLetter: (letter: PlatformLetter) => void;
};

function getLetterTypeLabel(type: PlatformLetter["type"]): string {
  return type === "welcome" ? "官方来信" : "更新公告";
}

export function MailboxPanel({
  letters,
  state,
  onClose,
  onDeleteRead,
  onMarkAllRead,
  onOpenLetter,
}: MailboxPanelProps) {
  const visibleLetters = getVisibleLetters(letters, state);
  const unreadCount = getUnreadCount(letters, state);
  const canMarkAllRead = unreadCount > 0;
  const canDeleteRead = canDeleteReadLetters(state, letters);

  return (
    <div className="mailbox-panel-backdrop" onMouseDown={(event) => event.stopPropagation()} onPointerDown={(event) => event.stopPropagation()}>
      <section
        className="mailbox-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mailbox-title"
      >
        <header className="mailbox-panel-header">
          <div>
            <p>Yuxin Mailbox</p>
            <h2 id="mailbox-title">信箱</h2>
          </div>
          <button type="button" aria-label="关闭信箱" onClick={onClose}>
            ×
          </button>
        </header>

        <div className="mailbox-toolbar" aria-label={`未读 ${unreadCount}`}>
          <span>未读 {unreadCount}</span>
          <button type="button" disabled={!canMarkAllRead} onClick={onMarkAllRead}>
            一键已读
          </button>
          <button type="button" disabled={!canDeleteRead} onClick={onDeleteRead}>
            删除已读
          </button>
        </div>

        <div className="mailbox-list">
          {visibleLetters.map((letter) => {
            const read = isLetterRead(state, letter.id);

            return (
              <button
                className={`mailbox-letter-row${read ? " is-read" : ""}`}
                key={letter.id}
                type="button"
                onClick={() => onOpenLetter(letter)}
              >
                <span className="mailbox-letter-icon" aria-hidden="true">
                  ✉
                </span>
                <span className="mailbox-letter-copy">
                  <strong>{letter.title}</strong>
                  <span>{letter.sender}</span>
                  <span>{getLetterTypeLabel(letter.type)}</span>
                </span>
                <span className="mailbox-letter-meta">
                  <span>{letter.publishedAt}</span>
                  <span>{read ? "已读" : "未读"}</span>
                  {letter.permanent && <span>永久保留</span>}
                </span>
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}
