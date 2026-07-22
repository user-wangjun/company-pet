type Props = {
  onClose: () => void;
  onOpenPlatform: () => void;
  onOpenReminders: () => void;
  onOpenToday: () => void;
  onOpenSettings: () => void;
  onQuickCreate: () => void;
};

export function TaskContextMenu(props: Props) {
  const choose = (action: () => void) => () => { action(); props.onClose(); };
  return (
    <div className="pet-task-menu" role="menu" onContextMenu={(event) => event.preventDefault()} onPointerDown={(event) => event.stopPropagation()}>
      <button role="menuitem" onClick={choose(props.onQuickCreate)}>＋ 新建待办</button>
      <button role="menuitem" onClick={choose(props.onOpenToday)}>◷ 查看今日待办</button>
      <button role="menuitem" onClick={choose(props.onOpenReminders)}>♢ 查看全部提醒</button>
      <button role="menuitem" onClick={choose(props.onQuickCreate)}>✎ 快速记录</button>
      <span />
      <button role="menuitem" onClick={choose(props.onOpenPlatform)}>打开主应用</button>
      <button role="menuitem" onClick={choose(props.onOpenSettings)}>桌宠设置</button>
    </div>
  );
}
