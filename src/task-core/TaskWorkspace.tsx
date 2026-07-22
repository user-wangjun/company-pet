import { useEffect, useMemo, useRef, useState } from "react";
import { QuickCreateTask, TaskDraftFields } from "./QuickCreateTask";
import { cancelTask, completeTask, createTask, dismissReminderInstance, isSameLocalDay, permanentlyDeleteTask, postponeTask, recordTaskMetric, rescheduleReminderInstance, restoreTask, scheduledLocalDate, scheduledTime, setTaskInProgress, softDeleteTask, syncLongTermMilestones, toLocalDateKey, updateTask, updateTaskSettings } from "./taskStore";
import { getLongTermTaskProgress, selectActiveLongTermTasks, selectTasks, type TaskListView } from "./taskQueries";
import type { Task, TaskDatabase, TaskDraft, TaskHistoryEntry, TaskUpdate } from "./types";
import type { DailyReviewTone } from "./taskReview";
import { TaskReviewPanel } from "./TaskReviewPanel";
import { CareReminderSettings } from "../pet-core/CareReminderSettings";
import { DEFAULT_CARE_REMINDER_SETTINGS, type CareReminderSettings as CareReminderSettingsValue } from "../pet-core/careReminders";
import { NativeScheduleInput } from "./NativeScheduleInput";

type Props = {
  database: TaskDatabase;
  initialView?: TaskListView;
  initialSelectedTaskId?: string | null;
  onChange: (database: TaskDatabase, feedback?: string) => void;
  careReminderSettings?: CareReminderSettingsValue;
  onCareReminderSettingsChange?: (settings: CareReminderSettingsValue) => void;
  careReminderNoticeDismissed?: boolean;
  onDismissCareReminderNotice?: () => void;
  reviewSpeakerName?: string;
  reviewSpeakerTexts?: Partial<Record<DailyReviewTone, string>>;
  onPreviewPetNotificationSound?: () => void;
};

const views: Array<{ id: TaskListView; label: string }> = [
  { id: "today", label: "今日" }, { id: "all", label: "全部" },
  { id: "upcoming", label: "即将提醒" }, { id: "overdue", label: "已过期" },
  { id: "completed", label: "已完成" }, { id: "cancelled", label: "已取消" },
  { id: "trash", label: "回收站" },
  { id: "settings", label: "提醒设置" },
];

type TaskSort = "default" | "created" | "due" | "priority" | "project";
type TodayCompletion = { entry: TaskHistoryEntry; task: Task };
type TodaySection = { id: string; label: string; tasks: Task[]; collapsed?: boolean; completions?: TodayCompletion[] };
type TimelineInsertDraft = { parentTaskId: string; afterTaskId: string | null; title: string; dueAt: string };
type CustomSoundDraft = { name: string; dataUrl: string; durationMs: number };

const CUSTOM_NOTIFICATION_SOUND_MAX_MS = 5000;

function formatDate(iso: string | null): string {
  if (!iso) return "未设置时间";
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso.replace(/-/g, "/");
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

function formatShortDate(iso: string | null): string {
  if (!iso) return "未定";
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) return iso.slice(5).replace("-", "/");
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit" }).format(new Date(iso));
}

function getTimelineBounds(task: Task): { startAt: string; endAt: string | null } {
  const taskDay = scheduledLocalDate(task.dueAt) ?? scheduledLocalDate(task.createdAt) ?? toLocalDateKey();
  if (task.kind === "single") return { startAt: taskDay, endAt: taskDay };
  return {
    startAt: scheduledLocalDate(task.startAt) ?? scheduledLocalDate(task.createdAt) ?? toLocalDateKey(),
    endAt: scheduledLocalDate(task.dueAt),
  };
}

function getDefaultInsertDate(previousAt: string | null, nextAt: string | null): string {
  const previousTime = previousAt ? scheduledTime(previousAt) : Number.NaN;
  const nextTime = nextAt ? scheduledTime(nextAt) : Number.NaN;
  if (Number.isFinite(previousTime) && Number.isFinite(nextTime)) {
    if (nextTime > previousTime) return toLocalDateKey(new Date(previousTime + (nextTime - previousTime) / 2));
    return scheduledLocalDate(previousAt) ?? toLocalDateKey();
  }
  if (Number.isFinite(previousTime)) {
    const value = new Date(previousTime);
    value.setDate(value.getDate() + 1);
    return toLocalDateKey(value);
  }
  return scheduledLocalDate(nextAt) ?? toLocalDateKey();
}

const taskStatusLabel: Record<Task["status"], string> = {
  pending: "待处理",
  in_progress: "进行中",
  completed: "已完成",
  cancelled: "已取消",
};

function getTaskDraft(database: TaskDatabase, task: Task): TaskDraft {
  const reminder = database.reminders.find((item) => item.taskId === task.id && item.status === "active" && !item.deletedAt);
  const recurringReminderId = reminder && reminder.repeatType !== "none" ? reminder.id : null;
  const instance = recurringReminderId
    ? database.reminderInstances.find((item) => item.reminderId === recurringReminderId && ["scheduled", "triggered", "missed"].includes(item.status))
    : undefined;
  const resolvedTask = { ...task, ...(instance?.taskOverrides ?? {}) };
  return {
    title: resolvedTask.title,
    note: resolvedTask.note,
    priority: resolvedTask.priority,
    projectId: resolvedTask.projectId,
    dueAt: resolvedTask.dueAt,
    kind: resolvedTask.kind,
    parentTaskId: resolvedTask.parentTaskId,
    startAt: resolvedTask.startAt,
    schedulePrecision: resolvedTask.schedulePrecision,
    milestones: resolvedTask.kind === "long_term"
      ? database.tasks.filter((item) => item.parentTaskId === resolvedTask.id && !item.deletedAt).map((item) => ({ id: item.id, title: item.title, dueAt: item.dueAt ?? "", schedulePrecision: item.schedulePrecision, remindAt: database.reminders.find((reminder) => reminder.taskId === item.id && reminder.status === "active")?.remindAt ?? null }))
      : [],
    remindAt: instance?.scheduledAt ?? reminder?.remindAt ?? null,
    repeatType: reminder?.repeatType ?? "none",
    repeatRule: reminder?.repeatRule ?? null,
    includeToday: resolvedTask.includeToday,
    attachmentRefs: resolvedTask.attachmentRefs,
  };
}

export function TaskWorkspace({ database, initialView = "today", initialSelectedTaskId = null, onChange, careReminderSettings = DEFAULT_CARE_REMINDER_SETTINGS, onCareReminderSettingsChange = () => {}, careReminderNoticeDismissed = false, onDismissCareReminderNotice = () => {}, reviewSpeakerName, reviewSpeakerTexts, onPreviewPetNotificationSound = () => {} }: Props) {
  const [view, setView] = useState<TaskListView>(initialView);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [isLongTermCreateOpen, setIsLongTermCreateOpen] = useState(false);
  const [isCreatePanelOpen, setIsCreatePanelOpen] = useState(false);
  const [pendingDeleteTask, setPendingDeleteTask] = useState<Task | null>(null);
  const [editDraft, setEditDraft] = useState<TaskDraft | null>(null);
  const [editError, setEditError] = useState("");
  const [sort, setSort] = useState<TaskSort>("default");
  const [expandedTimelineTaskId, setExpandedTimelineTaskId] = useState<string | null>(null);
  const [hoverInsertKey, setHoverInsertKey] = useState<string | null>(null);
  const [insertDraft, setInsertDraft] = useState<TimelineInsertDraft | null>(null);
  const [customSoundError, setCustomSoundError] = useState("");
  const [expandedTodaySections, setExpandedTodaySections] = useState(() => new Set(["overdue", "reminding", "today"]));
  const detailRef = useRef<HTMLElement>(null);
  const detailTitleRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLElement>(null);
  const lastFocusedElement = useRef<HTMLElement | null>(null);
  const tasks = useMemo(() => {
    const selected = selectTasks(database, view).filter((task) => {
      if (view === "trash" || task.kind !== "milestone" || !task.parentTaskId) return true;
      return !database.tasks.some((item) => item.id === task.parentTaskId && item.kind !== "milestone" && !item.deletedAt);
    });
    if (sort === "default" || view === "today" || view === "trash") return selected;
    const priority = { high: 0, normal: 1, low: 2 };
    return [...selected].sort((a, b) => {
      if (sort === "created") return b.createdAt.localeCompare(a.createdAt);
      if (sort === "priority") return priority[a.priority] - priority[b.priority];
      if (sort === "project") return a.projectId.localeCompare(b.projectId, "zh-CN");
      const aDue = a.dueAt ? new Date(a.dueAt).getTime() : Number.MAX_SAFE_INTEGER;
      const bDue = b.dueAt ? new Date(b.dueAt).getTime() : Number.MAX_SAFE_INTEGER;
      return aDue - bDue;
    });
  }, [database, sort, view]);
  const todaySections = useMemo<TodaySection[]>(() => {
    if (view !== "today") return [];
    const isGroupedMilestone = (task: Task) => task.kind === "milestone" && Boolean(task.parentTaskId) && database.tasks.some((item) => item.id === task.parentTaskId && item.kind !== "milestone" && !item.deletedAt);
    const overdue = selectTasks(database, "overdue").filter((task) => !isGroupedMilestone(task));
    const currentIds = new Set(database.reminderInstances
      .filter((instance) => ["triggered", "missed"].includes(instance.status))
      .map((instance) => instance.taskId));
    const nearby = selectTasks(database, "upcoming");
    const reminding = database.tasks.filter((task) => currentIds.has(task.id) && !task.deletedAt && !["completed", "cancelled"].includes(task.status) && !isGroupedMilestone(task));
    const upcoming = [...reminding, ...nearby.filter((task) => !currentIds.has(task.id))]
      .filter((task) => !overdue.some((item) => item.id === task.id));
    const reserved = new Set([...overdue, ...upcoming].map((task) => task.id));
    const today = selectTasks(database, "today").filter((task) => !reserved.has(task.id) && !isGroupedMilestone(task));
    const completions = database.history
      .filter((entry) => entry.type === "completed" && isSameLocalDay(entry.createdAt))
      .flatMap((entry) => {
        const task = database.tasks.find((item) => item.id === entry.taskId && !item.deletedAt);
        return task ? [{ entry, task }] : [];
      });
    return [
      { id: "overdue", label: "过期事项", tasks: overdue },
      { id: "reminding", label: "当前与即将提醒", tasks: upcoming },
      { id: "today", label: "今日待办", tasks: today },
      { id: "done", label: `今日已完成 · ${completions.length}`, tasks: [], completions, collapsed: true },
    ];
  }, [database, view]);
  const longTermProgress = useMemo(() => view === "today" ? selectActiveLongTermTasks(database) : [], [database, view]);
  const selectedReminder = selectedTask
    ? database.reminders.find((reminder) => reminder.taskId === selectedTask.id && reminder.status === "active" && !reminder.deletedAt)
    : undefined;
  const selectedReminderInstance = selectedTask
    ? database.reminderInstances.find((instance) => instance.taskId === selectedTask.id && ["scheduled", "triggered", "missed"].includes(instance.status))
    : undefined;
  const pendingDeleteReminder = pendingDeleteTask
    ? database.reminders.find((reminder) => reminder.taskId === pendingDeleteTask.id && reminder.status === "active" && !reminder.deletedAt)
    : undefined;
  const pendingDeleteReminderInstance = pendingDeleteTask
    ? database.reminderInstances.find((instance) => instance.taskId === pendingDeleteTask.id && ["scheduled", "triggered", "missed"].includes(instance.status))
    : undefined;
  useEffect(() => setView(initialView), [initialView]);
  useEffect(() => {
    const task = initialSelectedTaskId
      ? database.tasks.find((item) => item.id === initialSelectedTaskId) ?? null
      : null;
    setSelectedTask(task);
    setEditDraft(task ? getTaskDraft(database, task) : null);
  }, [database.tasks, initialSelectedTaskId]);
  useEffect(() => {
    const container = pendingDeleteTask ? confirmRef.current : selectedTask ? detailRef.current : null;
    if (!container) return undefined;
    const frame = window.requestAnimationFrame(() => {
      const target = pendingDeleteTask
        ? container.querySelector<HTMLElement>("[data-autofocus]") ?? container.querySelector<HTMLElement>("button")
        : detailTitleRef.current ?? container.querySelector<HTMLElement>("button, input, textarea, select");
      target?.focus();
    });
    const handleModalKeys = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (pendingDeleteTask) setPendingDeleteTask(null);
        else setSelectedTask(null);
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = [...container.querySelectorAll<HTMLElement>("button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex]:not([tabindex='-1'])")]
        .filter((element) => !element.hasAttribute("hidden"));
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", handleModalKeys);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("keydown", handleModalKeys);
    };
  }, [pendingDeleteTask, selectedTask]);
  useEffect(() => {
    if (selectedTask || pendingDeleteTask || !lastFocusedElement.current) return;
    lastFocusedElement.current.focus();
    lastFocusedElement.current = null;
  }, [pendingDeleteTask, selectedTask]);

  const create = (draft: TaskDraft) => {
    const result = createTask(database, draft);
    onChange(recordTaskMetric(result.database, "full_create_used"), `已记录「${result.task.title}」`);
    setIsCreatePanelOpen(false);
  };
  const createLongTerm = (draft: TaskDraft) => {
    create({ ...draft, kind: "long_term" });
    setIsLongTermCreateOpen(false);
  };

  const readCustomSoundFile = (file: File): Promise<CustomSoundDraft> => new Promise((resolve, reject) => {
    if (!file.type.startsWith("audio/")) {
      reject(new Error("请选择音频文件"));
      return;
    }
    const url = URL.createObjectURL(file);
    const audio = new Audio(url);
    audio.preload = "metadata";
    audio.onloadedmetadata = () => {
      const durationMs = Math.round(audio.duration * 1000);
      URL.revokeObjectURL(url);
      if (!Number.isFinite(durationMs) || durationMs <= 0) {
        reject(new Error("无法读取音频时长"));
        return;
      }
      if (durationMs > CUSTOM_NOTIFICATION_SOUND_MAX_MS) {
        reject(new Error("提示音不能超过 5 秒"));
        return;
      }
      const reader = new FileReader();
      reader.onload = () => resolve({ name: file.name, dataUrl: String(reader.result), durationMs });
      reader.onerror = () => reject(new Error("音频读取失败"));
      reader.readAsDataURL(file);
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("无法读取音频文件"));
    };
  });

  const uploadCustomSound = (file: File | undefined) => {
    if (!file) return;
    setCustomSoundError("");
    void readCustomSoundFile(file)
      .then((sound) => {
        onChange(updateTaskSettings(database, {
          notificationSound: "custom",
          customNotificationSoundName: sound.name,
          customNotificationSoundDataUrl: sound.dataUrl,
          customNotificationSoundDurationMs: sound.durationMs,
        }), "自定义提示音已保存");
      })
      .catch((reason) => setCustomSoundError(reason instanceof Error ? reason.message : "音频暂时无法使用"));
  };

  const previewNotificationSound = () => {
    if (database.settings.notificationSound === "pet") {
      onPreviewPetNotificationSound();
      return;
    }
    if (database.settings.notificationSound === "custom" && database.settings.customNotificationSoundDataUrl) {
      void new Audio(database.settings.customNotificationSoundDataUrl).play().catch(() => {});
      return;
    }
    if (database.settings.notificationSound === "gentle") {
      const audio = new Audio("data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=");
      void audio.play().catch(() => {});
    }
  };
  const change = (next: TaskDatabase, feedback?: string) => {
    onChange(next, feedback);
    setSelectedTask(null);
  };

  const openTask = (task: Task) => {
    lastFocusedElement.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setSelectedTask(task);
    setEditDraft(getTaskDraft(database, task));
    setEditError("");
  };

  const saveEdit = () => {
    if (!selectedTask || !editDraft?.title.trim()) return;
    if (editDraft.repeatType === "custom" && (editDraft.repeatRule?.weekdays?.length ?? 0) === 0) return;
    const original = getTaskDraft(database, selectedTask);
    const patch: TaskUpdate = {
      title: editDraft.title,
      note: editDraft.note,
      priority: editDraft.priority,
      projectId: editDraft.projectId,
      dueAt: editDraft.dueAt,
      kind: editDraft.kind,
      parentTaskId: editDraft.parentTaskId,
      startAt: editDraft.startAt,
      schedulePrecision: editDraft.schedulePrecision,
      includeToday: editDraft.includeToday,
      attachmentRefs: editDraft.attachmentRefs,
    };
    if (selectedReminder?.repeatType !== "none" || editDraft.remindAt !== original.remindAt) {
      patch.remindAt = editDraft.remindAt;
      patch.repeatType = editDraft.repeatType;
      patch.repeatRule = editDraft.repeatRule;
    } else {
      if (editDraft.repeatType !== original.repeatType) patch.repeatType = editDraft.repeatType;
      const editedWeekdays = [...(editDraft.repeatRule?.weekdays ?? [])].sort().join(",");
      const originalWeekdays = [...(original.repeatRule?.weekdays ?? [])].sort().join(",");
      if (editedWeekdays !== originalWeekdays) patch.repeatRule = editDraft.repeatRule;
    }
    try {
      let next = updateTask(database, selectedTask.id, patch);
      if ((editDraft.kind ?? selectedTask.kind) === "long_term") {
        next = syncLongTermMilestones(next, selectedTask.id, editDraft.milestones ?? []);
      }
      change(next, `已更新「${editDraft.title.trim()}」`);
    } catch (reason) {
      setEditError(reason instanceof Error ? reason.message : "任务暂时无法保存");
    }
  };

  const completeWithMilestonePrompt = (task: Task) => {
    let next = completeTask(database, task.id);
    let feedback = `完成了「${task.title}」`;
    if (task.kind === "milestone" && task.parentTaskId) {
      const parent = next.tasks.find((item) => item.id === task.parentTaskId && item.kind !== "milestone" && !item.deletedAt);
      const siblings = next.tasks.filter((item) => item.parentTaskId === task.parentTaskId && !item.deletedAt);
      if (parent && siblings.length > 0 && siblings.every((item) => item.status === "completed")) {
        if (window.confirm(`「${parent.title}」的所有节点都已完成。是否也完成这个任务？`)) {
          next = completeTask(next, parent.id);
          feedback = `完成了「${parent.title}」的整个周期`;
        } else {
          feedback = `全部节点已完成，「${parent.title}」仍保持进行中`;
        }
      }
    }
    change(next, feedback);
  };

  const getTimelineParent = (task: Task): Task | null => {
    if (task.kind !== "milestone") return task;
    if (!task.parentTaskId) return null;
    return database.tasks.find((item) => item.id === task.parentTaskId && item.kind !== "milestone" && !item.deletedAt) ?? null;
  };

  const getTimelineMilestones = (parentTaskId: string): Task[] => database.tasks
    .filter((item) => item.parentTaskId === parentTaskId && !item.deletedAt)
    .sort((a, b) => scheduledTime(a.dueAt) - scheduledTime(b.dueAt) || a.createdAt.localeCompare(b.createdAt));

  const getCurrentMilestone = (parentTaskId: string): Task | null => getTimelineMilestones(parentTaskId)
    .find((item) => !["completed", "cancelled"].includes(item.status)) ?? null;

  const startTimelineInsert = (parentTaskId: string, afterTaskId: string | null) => {
    const parent = database.tasks.find((task) => task.id === parentTaskId && task.kind !== "milestone" && !task.deletedAt);
    if (!parent) return;
    const milestones = getTimelineMilestones(parentTaskId);
    const afterIndex = afterTaskId ? milestones.findIndex((item) => item.id === afterTaskId) : -1;
    const previous = afterIndex >= 0 ? milestones[afterIndex] : null;
    const next = milestones[afterIndex + 1] ?? null;
    const bounds = getTimelineBounds(parent);
    setExpandedTimelineTaskId(parentTaskId);
    setInsertDraft({
      parentTaskId,
      afterTaskId,
      title: "",
      dueAt: getDefaultInsertDate(previous?.dueAt ?? bounds.startAt, next?.dueAt ?? bounds.endAt),
    });
  };

  const saveTimelineInsert = () => {
    if (!insertDraft?.title.trim()) return;
    const parent = database.tasks.find((task) => task.id === insertDraft.parentTaskId && task.kind !== "milestone" && !task.deletedAt);
    if (!parent) return;
    const result = createTask(database, {
      title: insertDraft.title,
      kind: "milestone",
      parentTaskId: parent.id,
      dueAt: insertDraft.dueAt,
      schedulePrecision: "date",
      priority: parent.priority,
      projectId: parent.projectId,
    });
    setInsertDraft(null);
    onChange(result.database, `已添加节点「${result.task.title}」`);
  };

  const saveCurrentOccurrence = () => {
    if (!selectedReminderInstance || !editDraft?.remindAt) return;
    change(
      rescheduleReminderInstance(database, selectedReminderInstance.id, editDraft.remindAt, new Date(), {
        title: editDraft.title,
        note: editDraft.note,
        priority: editDraft.priority,
        projectId: editDraft.projectId,
        dueAt: editDraft.dueAt,
        includeToday: editDraft.includeToday,
        attachmentRefs: editDraft.attachmentRefs,
      }),
      "仅本次内容与提醒时间已更新，后续重复规则保持不变",
    );
  };

  const deleteTask = (task: Task) => {
    setPendingDeleteTask(task);
  };

  const renderTimelineInsertForm = (draft: TimelineInsertDraft) => (
    <form className="task-timeline-insert-form" onSubmit={(event) => { event.preventDefault(); saveTimelineInsert(); }}>
      <input aria-label="新节点标题" maxLength={100} placeholder="新节点" value={draft.title} onInput={(event) => setInsertDraft({ ...draft, title: event.currentTarget.value })} />
      <NativeScheduleInput aria-label="新节点日期" type="date" min={getTimelineBounds(database.tasks.find((task) => task.id === draft.parentTaskId)!).startAt} max={getTimelineBounds(database.tasks.find((task) => task.id === draft.parentTaskId)!).endAt ?? undefined} value={draft.dueAt} onCommit={(value) => setInsertDraft({ ...draft, dueAt: value })} />
      <button type="submit" disabled={!draft.title.trim() || !draft.dueAt}>保存</button>
      <button type="button" onClick={() => setInsertDraft(null)}>取消</button>
    </form>
  );

  const renderTimelineInsertZone = (parentTaskId: string, afterTaskId: string | null) => {
    const key = `${parentTaskId}-${afterTaskId ?? "start"}`;
    return (
      <>
        <button
          className="task-timeline-insert-zone"
          type="button"
          aria-label="在这里插入时间节点"
          onClick={() => startTimelineInsert(parentTaskId, afterTaskId)}
          onMouseEnter={() => setHoverInsertKey(key)}
          onMouseLeave={() => setHoverInsertKey((current) => current === key ? null : current)}
        ><span>＋</span></button>
        {insertDraft?.parentTaskId === parentTaskId && insertDraft.afterTaskId === afterTaskId && renderTimelineInsertForm(insertDraft)}
      </>
    );
  };

  const renderTaskTimeline = (parent: Task, currentTaskId: string) => {
    const milestones = getTimelineMilestones(parent.id);
    const bounds = getTimelineBounds(parent);
    const firstInsertKey = `${parent.id}-start`;
    const lastInsertKey = `${parent.id}-${milestones[milestones.length - 1]?.id ?? "start"}`;
    return (
      <div className="task-timeline-panel" aria-label={`${parent.title} 时间节点`}>
        <div className="task-timeline-scroll">
          <article className={`task-timeline-node is-boundary${hoverInsertKey === firstInsertKey ? " is-pushed-up" : ""}`}>
            <time>{formatShortDate(bounds.startAt)}</time>
            <button type="button" onClick={() => openTask(parent)}>开始</button>
            <span>起点</span>
          </article>
          {renderTimelineInsertZone(parent.id, null)}
          {milestones.map((milestone, index) => {
            const insertKey = `${parent.id}-${milestone.id}`;
            const previousInsertKey = `${parent.id}-${index === 0 ? "start" : milestones[index - 1].id}`;
            return (
              <div className="task-timeline-cluster" key={milestone.id}>
                <article className={`task-timeline-node${milestone.id === currentTaskId ? " is-current" : ""}${milestone.status === "completed" ? " is-completed" : ""}${hoverInsertKey === previousInsertKey ? " is-pushed-down" : ""}${hoverInsertKey === insertKey ? " is-pushed-up" : ""}`}>
                  <time>{formatShortDate(milestone.dueAt)}</time>
                  <button type="button" onClick={() => openTask(milestone)}>{milestone.title}</button>
                  <span>{milestone.status === "completed" ? "已完成" : milestone.id === currentTaskId ? "当前" : taskStatusLabel[milestone.status]}</span>
                </article>
                {renderTimelineInsertZone(parent.id, milestone.id)}
              </div>
            );
          })}
          <article className={`task-timeline-node is-boundary is-end${hoverInsertKey === lastInsertKey ? " is-pushed-down" : ""}`}>
            <time>{bounds.endAt ? formatShortDate(bounds.endAt) : "待定"}</time>
            <button type="button" onClick={() => openTask(parent)}>{parent.kind === "single" ? "完成" : "结束"}</button>
            <span>终点</span>
          </article>
        </div>
      </div>
    );
  };

  const renderTaskCard = (task: Task) => {
    const reminder = database.reminders.find((item) => item.taskId === task.id && item.status === "active");
    const isRestorable = Boolean(task.deletedAt) || ["completed", "cancelled"].includes(task.status);
    const timelineParent = getTimelineParent(task);
    const timelineTaskId = timelineParent?.id ?? task.id;
    const hasTimeline = Boolean(timelineParent);
    const isTimelineExpanded = hasTimeline && expandedTimelineTaskId === timelineTaskId;
    const currentMilestone = task.kind === "long_term" ? getCurrentMilestone(task.id) : null;
    const progress = task.kind === "long_term" ? getLongTermTaskProgress(database, task) : null;
    return (
      <article className={`task-card is-${task.priority}${task.deletedAt ? " is-trashed" : ""}${isTimelineExpanded ? " has-timeline" : ""}`} key={task.id}>
        <div className="task-card-row">
          <button
            className={`task-check${isRestorable ? " is-restore" : ""}`}
            type="button"
            aria-label={`${isRestorable ? "恢复" : "完成"} ${task.title}`}
            onClick={() => isRestorable
              ? change(restoreTask(database, task.id), `已恢复「${task.title}」`)
              : completeWithMilestonePrompt(task)}
          >{isRestorable ? "↶" : "✓"}</button>
          <button className="task-card-main" type="button" disabled={Boolean(task.deletedAt)} onClick={() => openTask(task)}>
            <strong>{task.title}</strong>
            <span>{task.deletedAt ? `删除于 ${formatDate(task.deletedAt)}` : task.kind === "long_term" ? `${currentMilestone ? `当前节点：${currentMilestone.title} · ${formatDate(currentMilestone.dueAt)} · ` : ""}${progress?.completedMilestones ?? 0} / ${progress?.totalMilestones ?? 0} 个节点` : `${formatDate(task.dueAt)}${task.kind === "milestone" ? ` · 来自：${database.tasks.find((item) => item.id === task.parentTaskId)?.title ?? "父任务"}` : ""}${reminder ? ` · 提醒 ${formatDate(reminder.remindAt)}` : ""} · ${taskStatusLabel[task.status]}`}</span>
          </button>
          {hasTimeline && !task.deletedAt && (
            <button className="task-timeline-toggle" type="button" aria-expanded={isTimelineExpanded} aria-label={`${isTimelineExpanded ? "收起" : "展开"}${task.kind === "long_term" ? "时间节点" : "时间链"}`} onClick={() => setExpandedTimelineTaskId(isTimelineExpanded ? null : timelineTaskId)}>
              {isTimelineExpanded ? "⌃" : "⌄"}
            </button>
          )}
          {task.deletedAt
            ? <button className="task-purge-button" type="button" onClick={() => deleteTask(task)}>永久删除</button>
            : <span className="task-priority">{task.priority === "high" ? "高" : task.priority === "low" ? "低" : "普通"}</span>}
        </div>
        {isTimelineExpanded && timelineParent && renderTaskTimeline(timelineParent, task.id)}
      </article>
    );
  };

  return (
    <div className="task-workspace">
      <aside className="task-sidebar" inert={selectedTask || pendingDeleteTask || isLongTermCreateOpen ? true : undefined}>
        <div><strong>待办与提醒</strong><span>把今天安稳地放在眼前</span></div>
        <nav>{views.map((item) => <button className={view === item.id ? "is-active" : ""} key={item.id} onClick={() => setView(item.id)}>{item.label}</button>)}</nav>
      </aside>
      <section className="task-main" inert={selectedTask || pendingDeleteTask || isLongTermCreateOpen ? true : undefined}>
        <header className="task-main-header"><div><p>{views.find((item) => item.id === view)?.label}</p><h2>{view === "today" ? "今天，慢慢做好每一件事" : view === "trash" ? "删除的事项会保留30天" : view === "settings" ? "让提醒保持合适的分寸" : "管理你的待办"}</h2></div>{view !== "settings" && <div className="task-header-tools">{view !== "today" && view !== "trash" && <select aria-label="待办排序" value={sort} onChange={(event) => setSort(event.target.value as TaskSort)}><option value="default">默认排序</option><option value="created">创建时间</option><option value="due">截止时间</option><option value="priority">优先级</option><option value="project">项目</option></select>}<span>{tasks.length} 项</span></div>}</header>
        {view !== "trash" && view !== "settings" && <button className="task-add-rail" type="button" aria-label="添加待办" onClick={() => setIsCreatePanelOpen(true)}>＋</button>}
        {view === "settings" && <><section className="task-settings" aria-label="任务提醒设置">
          <section className="task-sound-settings" aria-label="提示音设置"><div><strong>提示音</strong><small>{database.settings.notificationSound === "custom" && database.settings.customNotificationSoundName ? database.settings.customNotificationSoundName : "选择提醒响起时的声音"}</small></div><div className="task-sound-options">{[{ id: "system", label: "系统" }, { id: "gentle", label: "轻柔" }, { id: "pet", label: "宠物" }, { id: "custom", label: "自定义" }, { id: "off", label: "关闭" }].map((item) => <button type="button" key={item.id} className={database.settings.notificationSound === item.id ? "is-active" : ""} onClick={() => onChange(updateTaskSettings(database, { notificationSound: item.id as TaskDatabase["settings"]["notificationSound"] }), "提醒声音设置已保存")}>{item.label}</button>)}</div><div className="task-sound-actions"><label><input type="file" accept="audio/*" onChange={(event) => uploadCustomSound(event.currentTarget.files?.[0])} />上传声音</label><button type="button" disabled={database.settings.notificationSound === "system" || database.settings.notificationSound === "off" || (database.settings.notificationSound === "custom" && !database.settings.customNotificationSoundDataUrl)} onClick={previewNotificationSound}>试听</button></div>{customSoundError && <p role="alert">{customSoundError}</p>}{database.settings.customNotificationSoundDurationMs && <small>自定义声音 {Math.round(database.settings.customNotificationSoundDurationMs / 100) / 10} 秒，最多 5 秒。</small>}</section>
          <label>桌宠气泡停留<select value={database.settings.bubbleDurationMinutes} onChange={(event) => onChange(updateTaskSettings(database, { bubbleDurationMinutes: Number(event.target.value) as TaskDatabase["settings"]["bubbleDurationMinutes"] }), "气泡停留时间已保存")}><option value="1">1分钟</option><option value="3">3分钟</option><option value="5">5分钟</option><option value="10">10分钟</option></select></label>
          <label className="task-setting-toggle"><span><strong>后台提醒</strong><small>退出主界面后仍由系统唤醒提醒</small></span><input type="checkbox" checked={database.settings.backgroundReminders} onChange={(event) => onChange(updateTaskSettings(database, { backgroundReminders: event.currentTarget.checked }), "后台提醒设置已保存")} /></label>
          <label className="task-setting-toggle"><span><strong>今日回顾</strong><small>保留完成、延期和取消的本地统计</small></span><input type="checkbox" checked={database.settings.dailyReview} onChange={(event) => onChange(updateTaskSettings(database, { dailyReview: event.currentTarget.checked }), "今日回顾设置已保存")} /></label>
          <div className="task-local-metrics"><strong>本地使用记录</strong><span>已创建 {database.metrics.task_created ?? 0} 项</span><span>已完成 {database.metrics.task_completed ?? 0} 项</span><span>已延后提醒 {database.metrics.reminder_snoozed ?? 0} 次</span><small>这些数据只保存在本机，不会上传。</small></div>
        </section><CareReminderSettings embedded settings={careReminderSettings} onChange={onCareReminderSettingsChange} disableNoticeDismissed={careReminderNoticeDismissed} onDismissDisableNotice={onDismissCareReminderNotice} /></>}
        {view !== "settings" && <div className="task-list">
          {view === "today" ? <>
          {longTermProgress.length > 0 && <details className="task-section task-long-term-section" open><summary><span>长期任务</span><b>{longTermProgress.length}</b></summary><div>{longTermProgress.map((progress) => renderTaskCard(progress.task))}</div></details>}
          {todaySections.map((section) => (
            <details className="task-section" key={section.id} open={expandedTodaySections.has(section.id)} onToggle={(event) => {
              const isOpen = event.currentTarget.open;
              setExpandedTodaySections((current) => {
                if (current.has(section.id) === isOpen) return current;
                const next = new Set(current);
                if (isOpen) next.add(section.id);
                else next.delete(section.id);
                return next;
              });
            }}>
              <summary><span>{section.label}</span><b>{section.tasks.length}</b></summary>
              <div>{section.tasks.map(renderTaskCard)}{section.completions?.map(({ entry, task }) => <article className="task-completion-row" key={entry.id}><span>✓</span><div><strong>{task.title}</strong><small>{formatDate(entry.createdAt)} 完成</small></div></article>)}{section.tasks.length === 0 && (section.completions?.length ?? 0) === 0 && <p>暂无事项</p>}</div>
            </details>
          ))}</> : <>{tasks.length === 0 && <div className="task-empty"><span>☁</span><strong>这里还很轻盈</strong><p>{view === "trash" ? "回收站里没有事项。" : "写下一件小事，小伙伴会替你记着。"}</p></div>}{tasks.map(renderTaskCard)}</>}
        </div>}
        {view === "today" && database.settings.dailyReview && (
          <TaskReviewPanel
            database={database}
            speakerName={reviewSpeakerName}
            speakerTexts={reviewSpeakerTexts}
          />
        )}
      </section>
      {isLongTermCreateOpen && (
        <div className="task-long-term-create-backdrop" onMouseDown={() => setIsLongTermCreateOpen(false)}>
          <section className="task-long-term-create-panel" role="dialog" aria-modal="true" aria-labelledby="long-term-create-title" onMouseDown={(event) => event.stopPropagation()}>
            <header><div><span>LONG-TERM TASK</span><h3 id="long-term-create-title">新建长期任务</h3></div><button type="button" aria-label="关闭长期任务创建" onClick={() => setIsLongTermCreateOpen(false)}>×</button></header>
            <div className="task-long-term-create-scroll"><QuickCreateTask initialKind="long_term" onCreate={createLongTerm} onCancel={() => setIsLongTermCreateOpen(false)} /></div>
          </section>
        </div>
      )}
      {isCreatePanelOpen && (
        <div className="task-create-backdrop" onMouseDown={() => setIsCreatePanelOpen(false)}>
          <section className="task-create-panel" role="dialog" aria-modal="true" aria-labelledby="task-create-panel-title" onMouseDown={(event) => event.stopPropagation()}>
            <header><div><span>NEW TASK</span><h3 id="task-create-panel-title">添加待办</h3></div><button type="button" aria-label="关闭添加待办" onClick={() => setIsCreatePanelOpen(false)}>×</button></header>
            <div className="task-create-panel-scroll"><QuickCreateTask initialKind="single" onCreate={create} onCancel={() => setIsCreatePanelOpen(false)} onOpenLongTerm={() => { setIsCreatePanelOpen(false); setIsLongTermCreateOpen(true); }} /></div>
          </section>
        </div>
      )}
      {selectedTask && (
        <div className="task-detail-backdrop" onMouseDown={() => setSelectedTask(null)}>
          <section ref={detailRef} className="task-detail" role="dialog" aria-modal="true" aria-labelledby="task-detail-title" aria-hidden={pendingDeleteTask ? true : undefined} inert={pendingDeleteTask ? true : undefined} onMouseDown={(event) => event.stopPropagation()}>
            <header><div><span>{selectedTask.projectId === "uncategorized" ? "未分类" : selectedTask.projectId}</span><h3 id="task-detail-title">{selectedTask.kind === "long_term" ? "长期任务详情" : selectedTask.kind === "milestone" ? "编辑日期节点" : "编辑待办"}</h3></div><button aria-label="关闭任务详情" onClick={() => setSelectedTask(null)}>×</button></header>
            {editDraft && <TaskDraftFields draft={editDraft} onChange={(next) => { setEditDraft(next); setEditError(""); }} titleInputRef={detailTitleRef} lockKind />}
            {editError && <p className="task-form-error" role="alert">{editError}</p>}
            <dl className="task-detail-summary"><div><dt>状态</dt><dd>{taskStatusLabel[selectedTask.status]}</dd></div><div><dt>{selectedTask.kind === "long_term" ? "节点进度" : "延期次数"}</dt><dd>{selectedTask.kind === "long_term" ? `${getLongTermTaskProgress(database, selectedTask).completedMilestones} / ${getLongTermTaskProgress(database, selectedTask).totalMilestones}` : selectedTask.postponedCount}</dd></div>{selectedTask.kind === "milestone" && <div><dt>所属任务</dt><dd>{database.tasks.find((task) => task.id === selectedTask.parentTaskId)?.title ?? "父任务"}</dd></div>}</dl>
            <div className="task-detail-actions">
              <button className="is-primary" disabled={!editDraft?.title.trim() || (editDraft.repeatType === "custom" && (editDraft.repeatRule?.weekdays?.length ?? 0) === 0)} onClick={saveEdit}>{selectedReminder?.repeatType !== "none" ? "修改本次及以后" : "保存修改"}</button>
              {selectedReminder?.repeatType !== "none" && selectedReminderInstance && <button disabled={!editDraft?.remindAt} onClick={saveCurrentOccurrence}>仅修改本次</button>}
              {selectedTask.status !== "completed" && <button onClick={() => completeWithMilestonePrompt(selectedTask)}>{selectedTask.kind === "long_term" ? "完成长期任务" : "完成"}</button>}
              {selectedTask.status === "pending" && <button onClick={() => change(setTaskInProgress(database, selectedTask.id), "已开始处理")}>开始处理</button>}
              {selectedTask.kind !== "long_term" && !["completed", "cancelled"].includes(selectedTask.status) && <button onClick={() => {
                const nextDate = selectedTask.dueAt ? new Date(selectedTask.schedulePrecision === "date" ? `${selectedTask.dueAt}T12:00:00` : selectedTask.dueAt) : new Date();
                nextDate.setDate(nextDate.getDate() + 1);
                const next = selectedTask.schedulePrecision === "date" ? `${nextDate.getFullYear()}-${String(nextDate.getMonth() + 1).padStart(2, "0")}-${String(nextDate.getDate()).padStart(2, "0")}` : nextDate.toISOString();
                const reminder = database.reminders.find((item) => item.taskId === selectedTask.id && item.status === "active");
                const shiftedReminder = reminder
                  ? new Date(new Date(reminder.remindAt).getTime() + 24 * 60 * 60 * 1000).toISOString()
                  : null;
                change(postponeTask(database, selectedTask.id, next, shiftedReminder), "截止和提醒时间已顺延一天");
              }}>延期一天</button>}
              {selectedTask.status === "cancelled" || selectedTask.status === "completed" ? <button onClick={() => change(restoreTask(database, selectedTask.id), "任务已恢复")}>恢复任务</button> : <button onClick={() => change(cancelTask(database, selectedTask.id), "任务已取消")}>取消</button>}
              {database.reminderInstances.some((instance) => instance.taskId === selectedTask.id && ["triggered", "missed"].includes(instance.status)) && <button onClick={() => {
                const instance = database.reminderInstances.find((item) => item.taskId === selectedTask.id && ["triggered", "missed"].includes(item.status));
                if (instance) change(dismissReminderInstance(database, instance.id), "已关闭本次提醒");
              }}>{selectedReminder?.repeatType !== "none" ? "仅删除本次" : "关闭本次提醒"}</button>}
              <button className="is-danger" onClick={() => deleteTask(selectedTask)}>删除</button>
            </div>
          </section>
        </div>
      )}
      {pendingDeleteTask && (
        <div className="task-confirm-backdrop" onMouseDown={() => setPendingDeleteTask(null)}>
          <section ref={confirmRef} className="task-confirm" role="alertdialog" aria-modal="true" aria-labelledby="task-confirm-title" aria-describedby="task-confirm-description" onMouseDown={(event) => event.stopPropagation()}>
            <span aria-hidden="true">⌫</span>
            <h3 id="task-confirm-title">{pendingDeleteTask.deletedAt ? "永久删除？" : "移入回收站？"}</h3>
            <p id="task-confirm-description">{pendingDeleteTask.deletedAt ? `「${pendingDeleteTask.title}」删除后无法恢复。${pendingDeleteTask.kind === "long_term" ? " 它的节点和相关提醒也会一并永久清理。" : ""}` : `「${pendingDeleteTask.title}」会取消相关提醒，并在回收站保留30天。${pendingDeleteTask.kind === "long_term" ? " 它的全部节点会一并进入回收站。" : ""}${pendingDeleteReminder?.repeatType !== "none" ? " 这是重复任务，可仅删除当前一次。" : ""}`}</p>
            <div><button type="button" onClick={() => setPendingDeleteTask(null)}>暂不删除</button>{!pendingDeleteTask.deletedAt && pendingDeleteReminder?.repeatType !== "none" && pendingDeleteReminderInstance && <button type="button" onClick={() => {
              setPendingDeleteTask(null);
              change(dismissReminderInstance(database, pendingDeleteReminderInstance.id), "仅删除了本次，后续重复提醒保留");
            }}>仅删除本次</button>}<button className="is-danger" type="button" autoFocus onClick={() => {
              const task = pendingDeleteTask;
              setPendingDeleteTask(null);
              change(task.deletedAt ? permanentlyDeleteTask(database, task.id) : softDeleteTask(database, task.id), task.deletedAt ? "任务已永久删除" : "任务已移入回收站");
            }} data-autofocus>{pendingDeleteReminder?.repeatType !== "none" && !pendingDeleteTask.deletedAt ? "删除本次及以后" : "确认删除"}</button></div>
          </section>
        </div>
      )}
    </div>
  );
}
