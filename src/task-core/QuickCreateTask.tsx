import { useEffect, useId, useRef, useState } from "react";
import { toLocalDateKey } from "./taskStore";
import type { MilestoneDraft, RepeatType, SchedulePrecision, TaskDraft } from "./types";
import { NativeScheduleInput } from "./NativeScheduleInput";

type Props = {
  compact?: boolean;
  initialKind?: "single" | "long_term";
  onCancel?: () => void;
  onCreate: (draft: TaskDraft) => void;
  onOpenLongTerm?: () => void;
};
export type TaskDraftFieldsProps = { draft: TaskDraft; onChange: (draft: TaskDraft) => void; titleInputRef?: React.RefObject<HTMLInputElement | null>; showTitle?: boolean; lockKind?: boolean; hideKindLabel?: boolean };

const weekdays = [
  { value: 1, label: "一" }, { value: 2, label: "二" }, { value: 3, label: "三" },
  { value: 4, label: "四" }, { value: 5, label: "五" }, { value: 6, label: "六" }, { value: 0, label: "日" },
];

export const EMPTY_TASK_DRAFT: TaskDraft = {
  title: "", note: "", kind: "single", startAt: null, dueAt: null, schedulePrecision: "date",
  milestones: [], priority: "normal", projectId: "uncategorized", remindAt: null,
  repeatType: "none", repeatRule: null, includeToday: false, attachmentRefs: [],
};

function createEmptyDraft(kind: "single" | "long_term" = "single"): TaskDraft {
  return kind === "long_term"
    ? { ...EMPTY_TASK_DRAFT, kind, startAt: toLocalDateKey(), dueAt: null, milestones: [], attachmentRefs: [] }
    : { ...EMPTY_TASK_DRAFT, kind, dueAt: toLocalDateKey(), milestones: [], attachmentRefs: [] };
}

export function toDateTimeLocal(iso: string | null | undefined): string {
  if (!iso) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return `${iso}T00:00`;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function toIsoOrNull(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function scheduledDateValue(value: string | null | undefined): string {
  return toDateTimeLocal(value).slice(0, 10);
}

export function scheduledTimeValue(
  value: string | null | undefined,
  precision: SchedulePrecision,
): string {
  return precision === "datetime" ? toDateTimeLocal(value).slice(11, 16) : "";
}

export function buildScheduledValue(
  dateValue: string,
  timeValue: string,
): { dueAt: string | null; schedulePrecision: SchedulePrecision } {
  if (!dateValue) return { dueAt: null, schedulePrecision: "date" };
  if (!timeValue) return { dueAt: dateValue, schedulePrecision: "date" };
  return {
    dueAt: toIsoOrNull(`${dateValue}T${timeValue}`),
    schedulePrecision: "datetime",
  };
}

function milestoneReminder(dueAt: string, precision: SchedulePrecision, minutesBefore: number | null): string | null {
  if (minutesBefore === null || precision !== "datetime") return null;
  const due = new Date(dueAt);
  return Number.isNaN(due.getTime()) ? null : new Date(due.getTime() - minutesBefore * 60_000).toISOString();
}

export function TaskDraftFields({ draft, onChange, titleInputRef, showTitle = true, lockKind = false, hideKindLabel = false }: TaskDraftFieldsProps) {
  const id = useId();
  const kind = draft.kind ?? "single";
  const precision = draft.schedulePrecision ?? "date";
  const repeatType = draft.repeatType ?? "none";
  const repeatWeekdays = draft.repeatRule?.weekdays ?? [];
  const set = <K extends keyof TaskDraft>(key: K, value: TaskDraft[K]) => onChange({ ...draft, [key]: value });
  const setReminder = (value: string) => {
    const remindAt = toIsoOrNull(value);
    onChange({ ...draft, remindAt, ...(remindAt ? {} : { repeatType: "none", repeatRule: null }) });
  };
  const setRepeat = (value: RepeatType) => onChange({ ...draft, repeatType: value, repeatRule: value === "custom" ? { weekdays: repeatWeekdays } : null });
  const toggleWeekday = (weekday: number) => set("repeatRule", { weekdays: repeatWeekdays.includes(weekday) ? repeatWeekdays.filter((item) => item !== weekday) : [...repeatWeekdays, weekday] });
  const setRelativeReminder = (minutesBefore: number) => {
    if (!draft.dueAt || precision !== "datetime") return;
    const remindAt = new Date(new Date(draft.dueAt).getTime() - minutesBefore * 60_000).toISOString();
    onChange({ ...draft, remindAt });
  };
  const changeKind = (nextKind: "single" | "long_term") => onChange(nextKind === "long_term"
    ? { ...draft, kind: nextKind, startAt: draft.startAt ?? toLocalDateKey(), dueAt: null, schedulePrecision: "date", remindAt: null, repeatType: "none", repeatRule: null, includeToday: false, milestones: draft.milestones ?? [] }
    : { ...draft, kind: nextKind, startAt: null, dueAt: toLocalDateKey(), schedulePrecision: "date", milestones: [] });
  const setTaskSchedule = (dateValue: string, timeValue: string) => {
    const schedule = buildScheduledValue(dateValue, timeValue);
    onChange({
      ...draft,
      ...schedule,
      ...(schedule.schedulePrecision === "date"
        ? { remindAt: null, repeatType: "none" as const, repeatRule: null }
        : {}),
    });
  };
  const setTaskDate = (value: string) => setTaskSchedule(
    value,
    scheduledTimeValue(draft.dueAt, precision),
  );
  const setTaskTime = (value: string) => setTaskSchedule(
    scheduledDateValue(draft.dueAt) || toLocalDateKey(),
    value,
  );
  const updateMilestone = (index: number, patch: Partial<MilestoneDraft>) => set("milestones", (draft.milestones ?? []).map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  const addMilestone = () => set("milestones", [...(draft.milestones ?? []), { title: "", dueAt: draft.startAt ?? toLocalDateKey(), schedulePrecision: "date", remindAt: null }]);

  return (
    <div className="task-fields">
      {showTitle && <label className="task-field is-wide" htmlFor={`${id}-title`}>标题<input id={`${id}-title`} ref={titleInputRef} aria-label="待办标题" maxLength={100} placeholder="写下要做的事" value={draft.title} onInput={(event) => set("title", event.currentTarget.value)} /></label>}
      {!hideKindLabel && (lockKind || kind === "milestone" ? <div className="task-kind-label is-wide">{kind === "long_term" ? "长期任务" : kind === "milestone" ? "日期节点 · 不支持重复规则" : "当天任务"}</div> : <fieldset className="task-kind-switch is-wide"><legend>任务类型</legend><div>
        <button type="button" aria-pressed={kind === "single"} onClick={() => changeKind("single")}>当天任务</button>
        <button type="button" aria-pressed={kind === "long_term"} onClick={() => changeKind("long_term")}>长期任务</button>
      </div></fieldset>)}
      <label className="task-field is-wide" htmlFor={`${id}-note`}>备注<textarea id={`${id}-note`} maxLength={2000} placeholder="补充一些细节（可选）" value={draft.note ?? ""} onInput={(event) => set("note", event.currentTarget.value)} /></label>
      <label className="task-field is-wide" htmlFor={`${id}-attachments`}>附件引用<textarea id={`${id}-attachments`} aria-label="附件引用" placeholder="每行一个文件路径或链接（最多10个）" value={(draft.attachmentRefs ?? []).join("\n")} onInput={(event) => set("attachmentRefs", event.currentTarget.value.split(/\r?\n/).slice(0, 10))} /></label>

      {kind === "long_term" ? <>
        <label className="task-field" htmlFor={`${id}-start`}>开始日期<NativeScheduleInput id={`${id}-start`} type="date" value={(draft.startAt ?? "").slice(0, 10)} onCommit={(value) => set("startAt", value || null)} /></label>
        <label className="task-field" htmlFor={`${id}-long-due`}>截止日期（可选）<NativeScheduleInput id={`${id}-long-due`} type="date" value={(draft.dueAt ?? "").slice(0, 10)} onCommit={(value) => set("dueAt", value || null)} /></label>
        <fieldset className="task-milestone-editor is-wide"><legend>日期节点</legend>
          <div className="task-milestone-list">{(draft.milestones ?? []).map((milestone, index) => {
            const milestonePrecision = milestone.schedulePrecision ?? "date";
            const reminderMinutes = milestone.remindAt && milestonePrecision === "datetime" ? Math.round((new Date(milestone.dueAt).getTime() - new Date(milestone.remindAt).getTime()) / 60_000) : null;
            const milestoneDate = scheduledDateValue(milestone.dueAt);
            const milestoneTime = scheduledTimeValue(milestone.dueAt, milestonePrecision);
            const setMilestoneSchedule = (dateValue: string, timeValue: string) => {
              const schedule = buildScheduledValue(dateValue, timeValue);
              updateMilestone(index, {
                dueAt: schedule.dueAt ?? "",
                schedulePrecision: schedule.schedulePrecision,
                remindAt: schedule.schedulePrecision === "date" ? null : milestone.remindAt,
              });
            };
            return <div className="task-milestone-row" key={milestone.id ?? index}>
              <input aria-label={`节点 ${index + 1} 标题`} placeholder="节点标题" value={milestone.title} onInput={(event) => updateMilestone(index, { title: event.currentTarget.value })} />
              <NativeScheduleInput aria-label={`节点 ${index + 1} 日期`} type="date" value={milestoneDate} onCommit={(value) => setMilestoneSchedule(value, milestoneTime)} />
              <NativeScheduleInput aria-label={`节点 ${index + 1} 具体时间（可选）`} type="time" value={milestoneTime} onCommit={(value) => setMilestoneSchedule(milestoneDate, value)} />
              <select aria-label={`节点 ${index + 1} 提醒`} disabled={milestonePrecision !== "datetime"} value={reminderMinutes ?? ""} onChange={(event) => updateMilestone(index, { remindAt: milestoneReminder(milestone.dueAt, milestonePrecision, event.target.value === "" ? null : Number(event.target.value)) })}><option value="">不提醒</option><option value="0">到点</option><option value="10">提前10分钟</option><option value="30">提前30分钟</option><option value="60">提前1小时</option><option value="1440">提前1天</option></select>
              <button type="button" aria-label={`删除节点 ${index + 1}`} onClick={() => set("milestones", (draft.milestones ?? []).filter((_, itemIndex) => itemIndex !== index))}>删除</button>
            </div>;
          })}</div>
          <button className="task-add-milestone" type="button" onClick={addMilestone}>＋ 添加节点</button>
        </fieldset>
      </> : <>
        <label className="task-field" htmlFor={`${id}-due-date`}>任务日期 / 截止时间<NativeScheduleInput id={`${id}-due-date`} type="date" value={scheduledDateValue(draft.dueAt)} onCommit={setTaskDate} /></label>
        <label className="task-field" htmlFor={`${id}-due-time`}>具体时间（可选）<NativeScheduleInput id={`${id}-due-time`} type="time" value={scheduledTimeValue(draft.dueAt, precision)} onCommit={setTaskTime} /><small>不填写则按全天任务保存</small></label>
        <label className="task-field" htmlFor={`${id}-remind`}>提醒时间<NativeScheduleInput id={`${id}-remind`} type="datetime-local" disabled={precision !== "datetime"} value={toDateTimeLocal(draft.remindAt)} onCommit={setReminder} />{precision !== "datetime" && <small>填写具体时间后可设置提醒</small>}</label>
        {draft.dueAt && precision === "datetime" && <div className="task-reminder-presets is-wide" aria-label="快捷提醒时间"><span>快捷提醒</span><div>{[{ label: "到点", minutes: 0 }, { label: "提前10分钟", minutes: 10 }, { label: "提前30分钟", minutes: 30 }, { label: "提前1小时", minutes: 60 }, { label: "提前1天", minutes: 1440 }].map((preset) => <button key={preset.minutes} type="button" onClick={() => setRelativeReminder(preset.minutes)}>{preset.label}</button>)}</div></div>}
        {kind === "single" && <label className="task-field" htmlFor={`${id}-repeat`}>重复<select id={`${id}-repeat`} disabled={!draft.remindAt} value={repeatType} onChange={(event) => setRepeat(event.target.value as RepeatType)}><option value="none">不重复</option><option value="daily">每天</option><option value="weekly">每周</option><option value="custom">自定义星期</option></select>{!draft.remindAt && <small>设置提醒后可选择重复方式</small>}</label>}
        {kind === "single" && repeatType === "custom" && <fieldset className="task-weekdays is-wide"><legend>在这些星期重复</legend><div>{weekdays.map((day) => <label key={day.value} className={repeatWeekdays.includes(day.value) ? "is-selected" : ""}><input type="checkbox" checked={repeatWeekdays.includes(day.value)} onChange={() => toggleWeekday(day.value)} /><span>周{day.label}</span></label>)}</div>{repeatWeekdays.length === 0 && <small>请至少选择一天</small>}</fieldset>}
      </>}
      <label className="task-field" htmlFor={`${id}-priority`}>优先级<select id={`${id}-priority`} value={draft.priority ?? "normal"} onChange={(event) => set("priority", event.target.value as TaskDraft["priority"])}><option value="low">低</option><option value="normal">普通</option><option value="high">高</option></select></label>
      <label className="task-field" htmlFor={`${id}-project`}>项目<input id={`${id}-project`} maxLength={60} placeholder="未分类" value={draft.projectId === "uncategorized" ? "" : draft.projectId ?? ""} onInput={(event) => set("projectId", event.currentTarget.value)} /></label>
      {kind === "single" && <label className="task-today-toggle"><input type="checkbox" checked={draft.includeToday ?? false} onChange={(event) => set("includeToday", event.currentTarget.checked)} /><span>加入今天</span></label>}
    </div>
  );
}

function isDraftValid(draft: TaskDraft): boolean {
  return Boolean(draft.title.trim())
    && Boolean(draft.kind === "long_term" ? draft.startAt : draft.dueAt)
    && !(draft.repeatType === "custom" && (draft.repeatRule?.weekdays?.length ?? 0) === 0)
    && (draft.kind !== "long_term" || (draft.milestones ?? []).every((item) => Boolean(item.title.trim() && item.dueAt)));
}

export function QuickCreateTask({ compact = false, initialKind = "single", onCancel, onCreate, onOpenLongTerm }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<TaskDraft>(() => createEmptyDraft(initialKind));
  const [expanded, setExpanded] = useState(!compact);
  const [error, setError] = useState("");
  useEffect(() => inputRef.current?.focus(), []);
  const submit = () => {
    if (!isDraftValid(draft)) return;
    try {
      onCreate({ ...draft, title: draft.title.trim(), projectId: draft.projectId?.trim() || "uncategorized" });
      setDraft(createEmptyDraft(initialKind)); setExpanded(!compact); setError(""); inputRef.current?.focus();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "任务暂时无法保存");
    }
  };
  return <form className={`task-create${compact ? " is-compact" : ""}`} onSubmit={(event) => { event.preventDefault(); submit(); }}>
    <div className={`task-create-title-row${onOpenLongTerm ? " has-long-term" : ""}`}><input ref={inputRef} aria-label="待办标题" maxLength={100} placeholder="写下要做的事，按 Enter 保存" value={draft.title} onInput={(event) => { const title = event.currentTarget.value; setDraft((current) => ({ ...current, title })); }} />{onOpenLongTerm && <button className="task-long-term-create-button" type="button" onClick={onOpenLongTerm}>长期任务</button>}<button className="task-primary-button" type="submit" disabled={!isDraftValid(draft)}>保存</button></div>
    {expanded && <TaskDraftFields draft={draft} onChange={(next) => { setDraft(next); setError(""); }} showTitle={false} lockKind={Boolean(onOpenLongTerm)} hideKindLabel={Boolean(onOpenLongTerm)} />}
    {error && <p className="task-form-error" role="alert">{error}</p>}
    <div className="task-create-footer">{compact && <button className="task-text-button" type="button" onClick={() => setExpanded((value) => !value)}>{expanded ? "收起设置" : "更多设置"}</button>}{onCancel && <button className="task-text-button" type="button" onClick={onCancel}>取消</button>}</div>
  </form>;
}
