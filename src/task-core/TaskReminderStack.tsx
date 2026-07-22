import type { TriggeredReminder } from "./types";

type Props = {
  reminders: TriggeredReminder[];
  onComplete: (taskId: string, instanceId: string) => void;
  onOpen: (taskId: string) => void;
  onOpenAll: () => void;
  onCloseSummary: (instanceIds: string[]) => void;
  onSnooze: (instanceId: string) => void;
};

function timeLabel(iso: string): string {
  return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

export function TaskReminderStack({ reminders, onComplete, onOpen, onOpenAll, onCloseSummary, onSnooze }: Props) {
  if (reminders.length === 0) return null;
  const isMissedSummary = reminders.length > 1 && reminders.every(({ instance }) => instance.status === "missed");
  if (isMissedSummary) {
    return (
      <section className="task-reminder-region" aria-label="错过提醒汇总" onPointerDown={(event) => event.stopPropagation()}>
        <article className="task-reminder-card task-reminder-summary">
          <div className="task-reminder-main"><strong>你离开期间错过了 {reminders.length} 条提醒</strong><span>未处理事项已经放进今日页面</span></div>
          <div className="task-reminder-actions">
            <button type="button" onClick={onOpenAll}>查看全部</button>
            <button type="button" onClick={() => onCloseSummary(reminders.map(({ instance }) => instance.id))}>关闭</button>
          </div>
        </article>
      </section>
    );
  }
  return (
    <section className="task-reminder-region" aria-label="任务提醒" onPointerDown={(event) => event.stopPropagation()}>
      <div className="task-reminder-list">
        {reminders.map(({ task, instance }) => (
          <article className={`task-reminder-card is-${task.priority}`} key={instance.id}>
            <button className="task-reminder-main" type="button" onClick={() => onOpen(task.id)}>
              <strong>{task.title}</strong>
              <span>{instance.status === "missed" ? "已错过 · " : ""}{timeLabel(instance.scheduledAt)}</span>
            </button>
            <div className="task-reminder-actions">
              <button type="button" onClick={() => onComplete(task.id, instance.id)}>已完成</button>
              <button type="button" onClick={() => onSnooze(instance.id)}>延后10分钟</button>
            </div>
          </article>
        ))}
      </div>
      {reminders.length > 3 && <p>还有 {reminders.length - 3} 条提醒</p>}
    </section>
  );
}
