import type { CSSProperties } from "react";
import type { TaskMenuPlacement } from "./taskMenuLayout";

type Props = {
  placement: TaskMenuPlacement;
  style?: CSSProperties;
  onClose: () => void;
  onHidePet: () => void;
  onOpenReminders: () => void;
  onOpenSettings: () => void;
  onOpenToday: () => void;
  onOpenChat: () => void;
  onQuickCreate: () => void;
};

type IconName = "today" | "new" | "chat" | "reminder" | "settings" | "hide";

function MenuIcon({ name }: { name: IconName }) {
  if (name === "today") {
    return (
      <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        <rect x="3" y="3.5" width="10" height="10" rx="2" />
        <path d="M5 2.5v2M11 2.5v2M3.5 6.2h9" />
        <path d="m5.4 9.4 1.6 1.6 3.5-3.6" />
      </svg>
    );
  }

  if (name === "new") {
    return (
      <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        <rect x="3" y="3" width="10" height="10" rx="3" />
        <path d="M8 5.2v5.6M5.2 8h5.6" />
      </svg>
    );
  }

  if (name === "reminder") {
    return (
      <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        <circle cx="8" cy="8.4" r="4.8" />
        <path d="M8 5.8v2.8l2 1.2M4.6 2.7 3.1 4.1M11.4 2.7l1.5 1.4" />
      </svg>
    );
  }

  if (name === "chat") {
    return (
      <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        <path d="M3 3.5h10v7H7l-3.2 2v-2H3z" />
        <path d="M5.3 6.4h5.4M5.3 8.3h3.7" />
      </svg>
    );
  }

  if (name === "settings") {
    return (
      <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        <circle cx="8" cy="8" r="2.4" />
        <path d="M8 2.8v1.4M8 11.8v1.4M4.3 4.3l1 1M10.7 10.7l1 1M2.8 8h1.4M11.8 8h1.4M4.3 11.7l1-1M10.7 5.3l1-1" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d="M2.7 8.1s1.9-3.2 5.3-3.2c3.3 0 5.3 3.2 5.3 3.2s-1.2 2-3.4 2.8" />
      <path d="M7 10.8c-2.7-.5-4.3-2.7-4.3-2.7M3 3l10 10" />
      <path d="M6.8 6.3a2.2 2.2 0 0 1 2.9 2.9" />
    </svg>
  );
}

export function TaskContextMenu(props: Props) {
  const choose = (action: () => void) => () => {
    props.onClose();
    action();
  };

  return (
    <div
      className={`pet-task-menu is-${props.placement}`}
      role="menu"
      aria-label="任务快捷菜单"
      data-placement={props.placement}
      style={props.style}
      onContextMenu={(event) => event.preventDefault()}
      onKeyDown={(event) => {
        if (event.key !== "Escape") return;
        event.stopPropagation();
        props.onClose();
      }}
      onPointerDown={(event) => event.stopPropagation()}
    >
      <button className="is-primary" role="menuitem" type="button" onClick={choose(props.onOpenToday)} autoFocus>
        <MenuIcon name="today" />
        <span>今日任务</span>
      </button>
      <button className="is-primary" role="menuitem" type="button" onClick={choose(props.onQuickCreate)}>
        <MenuIcon name="new" />
        <span>新建任务</span>
      </button>
      <button className="is-primary" role="menuitem" type="button" onClick={choose(props.onOpenChat)}>
        <MenuIcon name="chat" />
        <span>陪我聊聊</span>
      </button>
      <span className="pet-task-menu-divider" role="presentation" />
      <button role="menuitem" type="button" onClick={choose(props.onOpenReminders)}>
        <MenuIcon name="reminder" />
        <span>快捷提醒</span>
      </button>
      <span className="pet-task-menu-divider" role="presentation" />
      <button className="is-muted" role="menuitem" type="button" onClick={choose(props.onOpenSettings)}>
        <MenuIcon name="settings" />
        <span>设置</span>
      </button>
      <button className="is-muted" role="menuitem" type="button" onClick={choose(props.onHidePet)}>
        <MenuIcon name="hide" />
        <span>暂时隐藏桌宠</span>
      </button>
    </div>
  );
}
