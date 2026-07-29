import type {
  Reminder,
  ReminderInstance,
  RepeatRule,
  RepeatType,
  Task,
  TaskDatabase,
  TaskDraft,
  TaskUpdate,
  TaskSettings,
  TaskHistoryEntry,
  TriggeredReminder,
} from "./types";

export const TASK_DATABASE_STORAGE_KEY = "yuxin.tasks.v1";

export const EMPTY_TASK_DATABASE: TaskDatabase = {
  schemaVersion: 2,
  tasks: [],
  reminders: [],
  reminderInstances: [],
  history: [],
  metrics: {},
  settings: {
    notificationSound: "system",
    customNotificationSoundName: null,
    customNotificationSoundDataUrl: null,
    customNotificationSoundDurationMs: null,
    backgroundReminders: true,
    bubbleDurationMinutes: 5,
    dailyReview: true,
    timezoneOffsetMinutes: new Date().getTimezoneOffset(),
    lastOverduePromptDate: null,
  },
};

function makeId(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function recordTaskMetric(
  database: TaskDatabase,
  event: string,
  amount = 1,
): TaskDatabase {
  return {
    ...database,
    metrics: {
      ...database.metrics,
      [event]: (database.metrics[event] ?? 0) + amount,
    },
  };
}

function toIso(now: Date | string): string {
  return typeof now === "string" ? new Date(now).toISOString() : now.toISOString();
}

const DATE_ONLY_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

function precisionForValue(value: string | null | undefined): Task["schedulePrecision"] {
  return value && !DATE_ONLY_PATTERN.test(value) ? "datetime" : "date";
}

export function toLocalDateKey(date: Date | string = new Date()): string {
  const value = typeof date === "string" ? new Date(date) : date;
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function scheduledLocalDate(value: string | null): string | null {
  if (!value) return null;
  if (DATE_ONLY_PATTERN.test(value)) return value;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : toLocalDateKey(date);
}

export function scheduledTime(value: string | null): number {
  if (!value) return Number.MAX_SAFE_INTEGER;
  if (DATE_ONLY_PATTERN.test(value)) {
    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day).getTime();
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? Number.MAX_SAFE_INTEGER : date.getTime();
}

function normalizeScheduledValue(
  value: string | null | undefined,
  precision: Task["schedulePrecision"],
): string | null {
  if (!value) return null;
  if (precision === "date") {
    if (DATE_ONLY_PATTERN.test(value)) return value;
    return toLocalDateKey(value);
  }
  return toIso(value);
}

function cloneEmptyDatabase(): TaskDatabase {
  return { ...EMPTY_TASK_DATABASE, tasks: [], reminders: [], reminderInstances: [], history: [], metrics: {}, settings: { ...EMPTY_TASK_DATABASE.settings } };
}

function getDefaultStorage(): Storage | null {
  try {
    return typeof globalThis !== "undefined" ? globalThis.localStorage ?? null : null;
  } catch {
    return null;
  }
}

function normalizeTaskSettings(value: Partial<TaskSettings> | undefined): TaskSettings {
  const defaults = EMPTY_TASK_DATABASE.settings;
  const sounds: TaskSettings["notificationSound"][] = ["system", "gentle", "pet", "custom", "off"];
  const durations: TaskSettings["bubbleDurationMinutes"][] = [1, 3, 5, 10];
  return {
    notificationSound: sounds.includes(value?.notificationSound as TaskSettings["notificationSound"])
      ? value!.notificationSound as TaskSettings["notificationSound"]
      : defaults.notificationSound,
    customNotificationSoundName: typeof value?.customNotificationSoundName === "string" ? value.customNotificationSoundName : null,
    customNotificationSoundDataUrl: typeof value?.customNotificationSoundDataUrl === "string" && value.customNotificationSoundDataUrl.startsWith("data:audio/") ? value.customNotificationSoundDataUrl : null,
    customNotificationSoundDurationMs: Number.isFinite(value?.customNotificationSoundDurationMs) ? value!.customNotificationSoundDurationMs! : null,
    backgroundReminders: typeof value?.backgroundReminders === "boolean" ? value.backgroundReminders : defaults.backgroundReminders,
    bubbleDurationMinutes: durations.includes(value?.bubbleDurationMinutes as TaskSettings["bubbleDurationMinutes"])
      ? value!.bubbleDurationMinutes as TaskSettings["bubbleDurationMinutes"]
      : defaults.bubbleDurationMinutes,
    dailyReview: typeof value?.dailyReview === "boolean" ? value.dailyReview : defaults.dailyReview,
    timezoneOffsetMinutes: Number.isFinite(value?.timezoneOffsetMinutes) ? value!.timezoneOffsetMinutes! : defaults.timezoneOffsetMinutes,
    lastOverduePromptDate: typeof value?.lastOverduePromptDate === "string" || value?.lastOverduePromptDate === null
      ? value.lastOverduePromptDate
      : defaults.lastOverduePromptDate,
  };
}

export function readTaskDatabase(storage: Pick<Storage, "getItem"> | null = getDefaultStorage()): TaskDatabase {
  if (!storage) return cloneEmptyDatabase();
  try {
    const raw = storage.getItem(TASK_DATABASE_STORAGE_KEY);
    if (!raw) return cloneEmptyDatabase();
    const parsed = JSON.parse(raw) as { schemaVersion?: number } & Partial<Omit<TaskDatabase, "schemaVersion">>;
    if (parsed.schemaVersion !== 1 && parsed.schemaVersion !== 2) return cloneEmptyDatabase();
    const rawTasks = Array.isArray(parsed.tasks) ? parsed.tasks : [];
    const normalizedTasks: Task[] = rawTasks.map((rawTask) => {
      const task = rawTask as Partial<Task> & Pick<Task, "id" | "title">;
      const kind = task.kind === "long_term" || task.kind === "milestone" ? task.kind : "single";
      const precision = task.schedulePrecision === "date" || task.schedulePrecision === "datetime"
        ? task.schedulePrecision
        : precisionForValue(task.dueAt);
      const normalizedDueAt = normalizeScheduledValue(task.dueAt, precision);
      return {
        ...task,
        kind,
        parentTaskId: typeof task.parentTaskId === "string" ? task.parentTaskId : null,
        startAt: normalizeScheduledValue(task.startAt, precisionForValue(task.startAt)),
        dueAt: normalizedDueAt ?? (kind === "single" ? scheduledLocalDate(task.createdAt ?? null) : null),
        schedulePrecision: normalizedDueAt ? precision : kind === "single" ? "date" : precision,
        attachmentRefs: Array.isArray(task.attachmentRefs) ? task.attachmentRefs : [],
        archivedAt: typeof task.archivedAt === "string" ? task.archivedAt : null,
        archiveReason: task.archiveReason === "parent_completed" ? "parent_completed" : null,
      } as Task;
    });
    const timelineParentIds = new Set(normalizedTasks.filter((task) => task.kind !== "milestone").map((task) => task.id));
    const tasks = normalizedTasks.map((task) => {
      if (task.kind !== "milestone" || (task.parentTaskId && timelineParentIds.has(task.parentTaskId))) return task;
      console.warn(`[task-store] orphan milestone ${task.id} was migrated to a single task`);
      return { ...task, kind: "single" as const, parentTaskId: null };
    });
    return {
      schemaVersion: 2,
      tasks,
      reminders: Array.isArray(parsed.reminders) ? parsed.reminders : [],
      reminderInstances: Array.isArray(parsed.reminderInstances) ? parsed.reminderInstances : [],
      history: Array.isArray(parsed.history) ? parsed.history : [],
      metrics: parsed.metrics && typeof parsed.metrics === "object" ? parsed.metrics : {},
      settings: normalizeTaskSettings(parsed.settings && typeof parsed.settings === "object" ? parsed.settings : undefined),
    };
  } catch {
    return cloneEmptyDatabase();
  }
}

export function writeTaskDatabase(
  database: TaskDatabase,
  storage: Pick<Storage, "setItem"> | null = getDefaultStorage(),
): void {
  if (!storage) return;
  storage.setItem(TASK_DATABASE_STORAGE_KEY, JSON.stringify(database));
}

export function updateTaskSettings(database: TaskDatabase, patch: Partial<TaskSettings>): TaskDatabase {
  return recordTaskMetric({
    ...database,
    settings: { ...database.settings, ...patch },
  }, "settings_updated");
}

export function reconcileTaskTimezone(
  database: TaskDatabase,
  timezoneOffsetMinutes = new Date().getTimezoneOffset(),
  now: Date | string = new Date(),
): TaskDatabase {
  const previousOffset = database.settings.timezoneOffsetMinutes;
  if (!Number.isFinite(previousOffset) || previousOffset === timezoneOffsetMinutes) return database;
  const deltaMs = (timezoneOffsetMinutes - previousOffset) * 60_000;
  const nowIso = toIso(now);
  const shift = (iso: string) => new Date(new Date(iso).getTime() + deltaMs).toISOString();
  return recordTaskMetric({
    ...database,
    settings: { ...database.settings, timezoneOffsetMinutes },
    reminders: database.reminders.map((reminder) => reminder.status === "active" && !reminder.deletedAt
      ? { ...reminder, remindAt: shift(reminder.remindAt), updatedAt: nowIso, version: reminder.version + 1 }
      : reminder),
    reminderInstances: database.reminderInstances.map((instance) => instance.status === "scheduled"
      ? { ...instance, scheduledAt: shift(instance.scheduledAt), updatedAt: nowIso }
      : instance),
  }, "timezone_reconciled");
}

function createReminderInstance(
  reminder: Reminder,
  nowIso: string,
  scheduledAt = reminder.remindAt,
  snoozedFrom: string | null = null,
): ReminderInstance {
  return {
    id: makeId("instance"),
    reminderId: reminder.id,
    taskId: reminder.taskId,
    scheduledAt,
    triggeredAt: null,
    snoozedFrom,
    snoozeCount: reminder.snoozeCount,
    dismissedAt: null,
    handledAt: null,
    status: "scheduled",
    createdAt: nowIso,
    updatedAt: nowIso,
  };
}

function sanitizeAttachmentRefs(values: string[] | undefined): string[] {
  const refs = (values ?? []).map((value) => value.trim()).filter(Boolean);
  if (refs.length > 10) throw new Error("附件引用不能超过10个");
  if (refs.some((value) => value.length > 500)) throw new Error("单个附件引用不能超过500个字符");
  return [...new Set(refs)];
}

export function createTask(
  database: TaskDatabase,
  draft: TaskDraft,
  now: Date | string = new Date(),
): { database: TaskDatabase; task: Task } {
  const title = draft.title.trim();
  if (!title) throw new Error("待办标题不能为空");
  if (title.length > 100) throw new Error("待办标题不能超过100个字符");
  if ((draft.note ?? "").length > 2000) throw new Error("备注不能超过2000个字符");

  const nowIso = toIso(now);
  const kind = draft.kind ?? "single";
  const schedulePrecision = draft.schedulePrecision
    ?? (draft.dueAt && !DATE_ONLY_PATTERN.test(draft.dueAt) ? "datetime" : "date");
  if (kind === "milestone" && (!draft.parentTaskId || !draft.dueAt)) {
    throw new Error("日期节点必须属于一个任务并设置日期");
  }
  if (kind === "milestone" && (draft.repeatType ?? "none") !== "none") {
    throw new Error("日期节点暂不支持重复规则");
  }
  if (kind === "milestone") {
    const parent = database.tasks.find((task) => task.id === draft.parentTaskId && task.kind !== "milestone" && !task.deletedAt);
    if (!parent) throw new Error("日期节点的父任务不存在");
    const milestoneDate = scheduledLocalDate(draft.dueAt ?? null);
    const parentDay = scheduledLocalDate(parent.dueAt) ?? scheduledLocalDate(parent.createdAt);
    const startDate = parent.kind === "single" ? parentDay : scheduledLocalDate(parent.startAt) ?? scheduledLocalDate(parent.createdAt);
    const endDate = parent.kind === "single" ? parentDay : scheduledLocalDate(parent.dueAt);
    if (!milestoneDate || (startDate && milestoneDate < startDate) || (endDate && milestoneDate > endDate)) {
      throw new Error("节点日期必须位于任务的开始和结束日期之间");
    }
  }
  const defaultDueAt = kind === "single" ? toLocalDateKey(nowIso) : null;
  const task: Task = {
    id: makeId("task"),
    title,
    note: draft.note?.trim() ?? "",
    status: "pending",
    priority: draft.priority ?? "normal",
    projectId: draft.projectId?.trim() || "uncategorized",
    dueAt: normalizeScheduledValue(draft.dueAt ?? defaultDueAt, schedulePrecision),
    kind,
    parentTaskId: kind === "milestone" ? draft.parentTaskId ?? null : null,
    startAt: kind === "long_term"
      ? normalizeScheduledValue(
        draft.startAt ?? toLocalDateKey(nowIso),
        precisionForValue(draft.startAt),
      )
      : null,
    schedulePrecision,
    includeToday: draft.includeToday ?? false,
    attachmentRefs: sanitizeAttachmentRefs(draft.attachmentRefs),
    completedAt: null,
    cancelledAt: null,
    postponedCount: 0,
    createdAt: nowIso,
    updatedAt: nowIso,
    deletedAt: null,
    archivedAt: null,
    archiveReason: null,
    version: 1,
    sourceDeviceId: "local",
  };

  const next: TaskDatabase = recordTaskMetric({
    ...database,
    tasks: [...database.tasks, task],
  }, "task_created");

  let result = next;
  if (draft.remindAt) {
    const reminder: Reminder = {
      id: makeId("reminder"),
      taskId: task.id,
      remindAt: toIso(draft.remindAt),
      repeatType: kind === "milestone" ? "none" : draft.repeatType ?? "none",
      repeatRule: kind === "milestone" ? null : draft.repeatRule ?? null,
      status: "active",
      snoozeCount: 0,
      createdAt: nowIso,
      updatedAt: nowIso,
      deletedAt: null,
      version: 1,
    };
    result = {
      ...next,
      reminders: [...next.reminders, reminder],
      reminderInstances: [...next.reminderInstances, createReminderInstance(reminder, nowIso)],
    };
  }

  for (const milestone of kind === "long_term" ? draft.milestones ?? [] : []) {
    const milestoneDate = scheduledLocalDate(milestone.dueAt);
    const startDate = scheduledLocalDate(task.startAt);
    const endDate = scheduledLocalDate(task.dueAt);
    if (!milestone.title.trim() || !milestoneDate) throw new Error("每个节点都需要标题和日期");
    if ((startDate && milestoneDate < startDate) || (endDate && milestoneDate > endDate)) {
      throw new Error("节点日期超出长期任务周期，请先调整节点或周期");
    }
    const created = createTask(result, {
      title: milestone.title,
      kind: "milestone",
      parentTaskId: task.id,
      dueAt: milestone.dueAt,
      schedulePrecision: milestone.schedulePrecision ?? "date",
      remindAt: milestone.remindAt ?? null,
      priority: draft.priority,
      projectId: draft.projectId,
    }, nowIso);
    result = created.database;
  }
  return { database: result, task };
}

function hasOwn(value: object, key: PropertyKey): boolean {
  return Object.prototype.hasOwnProperty.call(value, key);
}

export function updateTask(
  database: TaskDatabase,
  taskId: string,
  patch: TaskUpdate,
  now: Date | string = new Date(),
): TaskDatabase {
  const current = database.tasks.find((task) => task.id === taskId);
  if (!current || current.deletedAt) return database;

  const title = hasOwn(patch, "title") ? patch.title?.trim() ?? "" : current.title;
  const note = hasOwn(patch, "note") ? patch.note?.trim() ?? "" : current.note;
  if (!title) throw new Error("待办标题不能为空");
  if (title.length > 100) throw new Error("待办标题不能超过100个字符");
  if (note.length > 2000) throw new Error("备注不能超过2000个字符");

  const nowIso = toIso(now);
  const nextKind = patch.kind ?? current.kind;
  const nextSchedulePrecision = hasOwn(patch, "dueAt")
    ? patch.schedulePrecision ?? precisionForValue(patch.dueAt)
    : patch.schedulePrecision ?? current.schedulePrecision;
  const patchedDueAt = hasOwn(patch, "dueAt")
    ? normalizeScheduledValue(patch.dueAt, nextSchedulePrecision)
    : current.dueAt;
  const updatedTask: Task = {
    ...current,
    title,
    note,
    priority: patch.priority ?? current.priority,
    projectId: hasOwn(patch, "projectId") ? patch.projectId?.trim() || "uncategorized" : current.projectId,
    kind: nextKind,
    parentTaskId: current.kind === "milestone" && hasOwn(patch, "parentTaskId") ? patch.parentTaskId ?? null : current.parentTaskId,
    startAt: current.kind === "long_term" && hasOwn(patch, "startAt")
      ? normalizeScheduledValue(patch.startAt, precisionForValue(patch.startAt))
      : current.startAt,
    schedulePrecision: nextSchedulePrecision,
    dueAt: patchedDueAt ?? (nextKind === "single" ? scheduledLocalDate(current.createdAt) : null),
    includeToday: patch.includeToday ?? current.includeToday,
    attachmentRefs: hasOwn(patch, "attachmentRefs") ? sanitizeAttachmentRefs(patch.attachmentRefs) : current.attachmentRefs,
    updatedAt: nowIso,
    version: current.version + 1,
  };

  let reminders = database.reminders;
  let reminderInstances = database.reminderInstances;
  if (hasOwn(patch, "remindAt")) {
    const activeReminder = database.reminders.find(
      (reminder) => reminder.taskId === taskId && reminder.status === "active" && !reminder.deletedAt,
    );
    reminderInstances = database.reminderInstances.map((instance) =>
      instance.taskId === taskId && ["scheduled", "triggered", "missed"].includes(instance.status)
        ? { ...instance, status: "cancelled" as const, handledAt: nowIso, updatedAt: nowIso }
        : instance,
    );

    if (!patch.remindAt) {
      reminders = database.reminders.map((reminder) =>
        reminder.taskId === taskId && reminder.status === "active"
          ? { ...reminder, status: "cancelled" as const, updatedAt: nowIso, version: reminder.version + 1 }
          : reminder,
      );
    } else if (activeReminder) {
      const updatedReminder: Reminder = {
        ...activeReminder,
        remindAt: toIso(patch.remindAt),
        repeatType: patch.repeatType ?? activeReminder.repeatType,
        repeatRule: hasOwn(patch, "repeatRule") ? patch.repeatRule ?? null : activeReminder.repeatRule,
        updatedAt: nowIso,
        version: activeReminder.version + 1,
      };
      reminders = database.reminders.map((reminder) =>
        reminder.id === activeReminder.id ? updatedReminder : reminder,
      );
      reminderInstances = [
        ...reminderInstances,
        createReminderInstance(updatedReminder, nowIso),
      ];
    } else {
      const reminder: Reminder = {
        id: makeId("reminder"),
        taskId,
        remindAt: toIso(patch.remindAt),
        repeatType: patch.repeatType ?? "none",
        repeatRule: patch.repeatRule ?? null,
        status: "active",
        snoozeCount: 0,
        createdAt: nowIso,
        updatedAt: nowIso,
        deletedAt: null,
        version: 1,
      };
      reminders = [...database.reminders, reminder];
      reminderInstances = [
        ...reminderInstances,
        createReminderInstance(reminder, nowIso),
      ];
    }
  } else if (hasOwn(patch, "repeatType") || hasOwn(patch, "repeatRule")) {
    reminders = database.reminders.map((reminder) =>
      reminder.taskId === taskId && reminder.status === "active"
        ? {
            ...reminder,
            repeatType: patch.repeatType ?? reminder.repeatType,
            repeatRule: hasOwn(patch, "repeatRule") ? patch.repeatRule ?? null : reminder.repeatRule,
            updatedAt: nowIso,
            version: reminder.version + 1,
          }
        : reminder,
    );
  }

  return recordTaskMetric({
    ...database,
    tasks: database.tasks.map((task) => task.id === taskId ? updatedTask : task),
    reminders,
    reminderInstances,
  }, "task_updated");
}

export function syncLongTermMilestones(
  database: TaskDatabase,
  parentTaskId: string,
  drafts: NonNullable<TaskDraft["milestones"]>,
  now: Date | string = new Date(),
): TaskDatabase {
  const parent = database.tasks.find((task) => task.id === parentTaskId && task.kind === "long_term" && !task.deletedAt);
  if (!parent) return database;
  const nowIso = toIso(now);
  const start = scheduledLocalDate(parent.startAt);
  const end = scheduledLocalDate(parent.dueAt);
  for (const draft of drafts) {
    const date = scheduledLocalDate(draft.dueAt);
    if (!draft.title.trim() || !date) throw new Error("每个节点都需要标题和日期");
    if ((start && date < start) || (end && date > end)) throw new Error("节点日期超出长期任务周期，请先调整节点或周期");
  }
  const existing = database.tasks.filter((task) => task.parentTaskId === parentTaskId && !task.deletedAt);
  const retainedIds = new Set(drafts.flatMap((draft) => draft.id ? [draft.id] : []));
  let next = database;
  for (const task of existing) {
    if (!retainedIds.has(task.id)) next = softDeleteTask(next, task.id, nowIso);
  }
  for (const draft of drafts) {
    if (draft.id && existing.some((task) => task.id === draft.id)) {
      next = updateTask(next, draft.id, {
        title: draft.title,
        dueAt: draft.dueAt,
        schedulePrecision: draft.schedulePrecision ?? "date",
        remindAt: draft.remindAt ?? null,
        repeatType: "none",
        repeatRule: null,
      }, nowIso);
    } else {
      next = createTask(next, {
        title: draft.title,
        kind: "milestone",
        parentTaskId,
        dueAt: draft.dueAt,
        schedulePrecision: draft.schedulePrecision ?? "date",
        remindAt: draft.remindAt ?? null,
        priority: parent.priority,
        projectId: parent.projectId,
      }, nowIso).database;
    }
  }
  return next;
}

function historyEntry(
  taskId: string,
  type: TaskHistoryEntry["type"],
  nowIso: string,
  fromAt: string | null = null,
  toAt: string | null = null,
): TaskHistoryEntry {
  return { id: makeId("history"), taskId, type, fromAt, toAt, createdAt: nowIso };
}

function isRecurring(reminder: Reminder | undefined): boolean {
  return Boolean(reminder && reminder.repeatType !== "none");
}

function nextCustomWeekday(date: Date, weekdays: number[]): Date {
  const unique = [...new Set(weekdays)].filter((day) => day >= 0 && day <= 6);
  for (let offset = 1; offset <= 7; offset += 1) {
    const candidate = new Date(date);
    candidate.setDate(candidate.getDate() + offset);
    if (unique.includes(candidate.getDay())) return candidate;
  }
  const fallback = new Date(date);
  fallback.setDate(fallback.getDate() + 7);
  return fallback;
}

export function getNextOccurrence(
  iso: string,
  repeatType: RepeatType,
  repeatRule: RepeatRule | null,
): string {
  const next = new Date(iso);
  if (repeatType === "daily") next.setDate(next.getDate() + 1);
  if (repeatType === "weekly") next.setDate(next.getDate() + 7);
  if (repeatType === "custom") {
    return nextCustomWeekday(next, repeatRule?.weekdays ?? []).toISOString();
  }
  return next.toISOString();
}

export function getNextOccurrenceAfter(
  iso: string,
  repeatType: RepeatType,
  repeatRule: RepeatRule | null,
  after: Date | string,
): string {
  const afterMs = new Date(after).getTime();
  let next = getNextOccurrence(iso, repeatType, repeatRule);
  let guard = 0;
  while (new Date(next).getTime() <= afterMs && guard < 4000) {
    next = getNextOccurrence(next, repeatType, repeatRule);
    guard += 1;
  }
  return next;
}

export function completeTask(
  database: TaskDatabase,
  taskId: string,
  now: Date | string = new Date(),
): TaskDatabase {
  const nowIso = toIso(now);
  const currentTask = database.tasks.find((task) => task.id === taskId);
  if (!currentTask || currentTask.deletedAt || ["completed", "cancelled"].includes(currentTask.status)) {
    return database;
  }
  const reminder = database.reminders.find(
    (item) => item.taskId === taskId && item.status === "active" && !item.deletedAt,
  );
  const recurring = isRecurring(reminder);
  const childIds = new Set(database.tasks.filter((task) => task.parentTaskId === taskId && !task.deletedAt).map((task) => task.id));
  const tasks = database.tasks.map((task) => {
    if (childIds.has(task.id) && !["completed", "cancelled"].includes(task.status)) {
      return {
        ...task,
        status: "cancelled" as const,
        cancelledAt: nowIso,
        archivedAt: nowIso,
        archiveReason: "parent_completed" as const,
        updatedAt: nowIso,
        version: task.version + 1,
      };
    }
    if (task.id !== taskId) return task;
    if (!recurring) {
      return { ...task, status: "completed" as const, completedAt: nowIso, updatedAt: nowIso, version: task.version + 1 };
    }
    const nextDueAt = task.dueAt && reminder
      ? getNextOccurrenceAfter(task.dueAt, reminder.repeatType, reminder.repeatRule, nowIso)
      : task.dueAt;
    return { ...task, status: "pending" as const, completedAt: null, dueAt: nextDueAt, updatedAt: nowIso, version: task.version + 1 };
  });

  const instances = database.reminderInstances.map((instance) =>
    (instance.taskId === taskId || childIds.has(instance.taskId)) && ["scheduled", "triggered", "missed"].includes(instance.status)
      ? { ...instance, status: "completed" as const, handledAt: nowIso, updatedAt: nowIso }
      : instance,
  );
  let reminders = database.reminders;
  let reminderInstances = instances;
  if (reminder && recurring) {
    const nextAt = getNextOccurrenceAfter(reminder.remindAt, reminder.repeatType, reminder.repeatRule, nowIso);
    const nextReminder = { ...reminder, remindAt: nextAt, updatedAt: nowIso, version: reminder.version + 1 };
    reminders = database.reminders.map((item) => item.id === reminder.id ? nextReminder : item);
    reminderInstances = [...instances, createReminderInstance(nextReminder, nowIso)];
  } else {
    reminders = database.reminders.map((item) =>
      (item.taskId === taskId || childIds.has(item.taskId)) && item.status === "active"
        ? { ...item, status: "completed" as const, updatedAt: nowIso, version: item.version + 1 }
        : item,
    );
  }
  return recordTaskMetric({
    ...database,
    tasks,
    reminders,
    reminderInstances,
    history: [...database.history, historyEntry(taskId, "completed", nowIso)],
  }, "task_completed");
}

export function completeReminderInstance(
  database: TaskDatabase,
  instanceId: string,
  now: Date | string = new Date(),
): TaskDatabase {
  const instance = database.reminderInstances.find((item) => item.id === instanceId);
  if (!instance || !["triggered", "missed"].includes(instance.status)) return database;
  return completeTask(database, instance.taskId, now);
}

export function setTaskInProgress(database: TaskDatabase, taskId: string, now: Date | string = new Date()): TaskDatabase {
  const nowIso = toIso(now);
  const current = database.tasks.find((task) => task.id === taskId);
  if (!current || current.deletedAt || current.status !== "pending") return database;
  return recordTaskMetric({
    ...database,
    tasks: database.tasks.map((task) => task.id === taskId
      ? { ...task, status: "in_progress", updatedAt: nowIso, version: task.version + 1 }
      : task),
  }, "task_started");
}

export function postponeTask(
  database: TaskDatabase,
  taskId: string,
  dueAt: string,
  remindAt: string | null,
  now: Date | string = new Date(),
): TaskDatabase {
  const nowIso = toIso(now);
  const task = database.tasks.find((item) => item.id === taskId);
  if (!task || task.deletedAt || ["completed", "cancelled"].includes(task.status)) return database;
  const nextDueAt = normalizeScheduledValue(dueAt, task.schedulePrecision) ?? task.dueAt;
  let reminders = database.reminders;
  let instances = database.reminderInstances;
  if (remindAt) {
    const reminder = database.reminders.find((item) => item.taskId === taskId && item.status === "active");
    if (reminder) {
      const updated = { ...reminder, remindAt: toIso(remindAt), updatedAt: nowIso, version: reminder.version + 1 };
      reminders = database.reminders.map((item) => item.id === reminder.id ? updated : item);
      instances = [
        ...database.reminderInstances.map((instance) =>
          instance.reminderId === reminder.id && ["scheduled", "triggered", "missed"].includes(instance.status)
            ? { ...instance, status: "cancelled" as const, handledAt: nowIso, updatedAt: nowIso }
            : instance,
        ),
        createReminderInstance(updated, nowIso),
      ];
    }
  }
  return recordTaskMetric({
    ...database,
    tasks: database.tasks.map((item) => item.id === taskId ? {
      ...item,
      status: "pending",
      dueAt: nextDueAt,
      postponedCount: item.postponedCount + 1,
      updatedAt: nowIso,
      version: item.version + 1,
    } : item),
    reminders,
    reminderInstances: instances,
    history: [...database.history, historyEntry(taskId, "postponed", nowIso, task?.dueAt ?? null, nextDueAt)],
  }, "task_postponed");
}

export function cancelTask(database: TaskDatabase, taskId: string, now: Date | string = new Date()): TaskDatabase {
  const nowIso = toIso(now);
  const current = database.tasks.find((task) => task.id === taskId);
  if (!current || current.deletedAt || ["completed", "cancelled"].includes(current.status)) return database;
  const affectedIds = new Set([
    taskId,
    ...database.tasks.filter((task) => task.parentTaskId === taskId && !task.deletedAt && !["completed", "cancelled"].includes(task.status)).map((task) => task.id),
  ]);
  return recordTaskMetric({
    ...database,
    tasks: database.tasks.map((task) => affectedIds.has(task.id) ? {
      ...task, status: "cancelled", cancelledAt: nowIso, updatedAt: nowIso, version: task.version + 1,
    } : task),
    reminders: database.reminders.map((reminder) => affectedIds.has(reminder.taskId) && reminder.status === "active"
      ? { ...reminder, status: "cancelled", updatedAt: nowIso, version: reminder.version + 1 }
      : reminder),
    reminderInstances: database.reminderInstances.map((instance) => affectedIds.has(instance.taskId) && ["scheduled", "triggered", "missed"].includes(instance.status)
      ? { ...instance, status: "cancelled", handledAt: nowIso, updatedAt: nowIso }
      : instance),
    history: [...database.history, historyEntry(taskId, "cancelled", nowIso)],
  }, "task_cancelled");
}

export function softDeleteTask(database: TaskDatabase, taskId: string, now: Date | string = new Date()): TaskDatabase {
  const nowIso = toIso(now);
  const root = database.tasks.find((task) => task.id === taskId);
  if (!root || root.deletedAt) return database;
  const affectedIds = new Set([
    taskId,
    ...database.tasks.filter((task) => task.parentTaskId === taskId && !task.deletedAt).map((task) => task.id),
  ]);
  return recordTaskMetric({
    ...database,
    tasks: database.tasks.map((task) => {
      if (!affectedIds.has(task.id)) return task;
      const preserveCompletedChild = task.id !== taskId && task.status === "completed";
      return {
        ...task,
        status: preserveCompletedChild ? "completed" : "cancelled",
        cancelledAt: preserveCompletedChild ? task.cancelledAt : nowIso,
        deletedAt: nowIso,
        updatedAt: nowIso,
        version: task.version + 1,
      };
    }),
    reminders: database.reminders.map((reminder) => affectedIds.has(reminder.taskId) && reminder.status === "active"
      ? { ...reminder, status: "cancelled", updatedAt: nowIso, version: reminder.version + 1 }
      : reminder),
    reminderInstances: database.reminderInstances.map((instance) => affectedIds.has(instance.taskId) && ["scheduled", "triggered", "missed"].includes(instance.status)
      ? { ...instance, status: "cancelled", handledAt: nowIso, updatedAt: nowIso }
      : instance),
  }, "task_deleted");
}

export function restoreTask(database: TaskDatabase, taskId: string, now: Date | string = new Date()): TaskDatabase {
  const nowIso = toIso(now);
  const task = database.tasks.find((item) => item.id === taskId);
  if (!task || (!task.deletedAt && !["completed", "cancelled"].includes(task.status))) return database;

  const restoredTaskIds = new Set([
    taskId,
    ...database.tasks.filter((item) => item.parentTaskId === taskId && (Boolean(item.deletedAt) || item.status === "cancelled")).map((item) => item.id),
  ]);
  const restorableReminders = database.reminders
    .filter((reminder) => restoredTaskIds.has(reminder.taskId) && reminder.status === "cancelled" && !reminder.deletedAt)
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  let reminders = database.reminders;
  let reminderInstances = database.reminderInstances;
  for (const restorableReminder of restorableReminders) {
    let nextAt = restorableReminder.remindAt;
    if (restorableReminder.repeatType !== "none") {
      let guard = 0;
      while (new Date(nextAt).getTime() <= new Date(nowIso).getTime() && guard < 400) {
        nextAt = getNextOccurrence(nextAt, restorableReminder.repeatType, restorableReminder.repeatRule);
        guard += 1;
      }
    }
    if (new Date(nextAt).getTime() > new Date(nowIso).getTime()) {
      const restoredReminder: Reminder = {
        ...restorableReminder,
        remindAt: nextAt,
        status: "active",
        updatedAt: nowIso,
        version: restorableReminder.version + 1,
      };
      reminders = reminders.map((reminder) =>
        reminder.id === restorableReminder.id ? restoredReminder : reminder,
      );
      reminderInstances = [
        ...reminderInstances,
        createReminderInstance(restoredReminder, nowIso),
      ];
    }
  }

  return recordTaskMetric({
    ...database,
    tasks: database.tasks.map((task) => {
      if (!restoredTaskIds.has(task.id)) return task;
      const preserveCompletedChild = task.id !== taskId && task.status === "completed";
      return {
        ...task,
        status: preserveCompletedChild ? "completed" : "pending",
        completedAt: preserveCompletedChild ? task.completedAt : null,
        cancelledAt: null,
        deletedAt: null,
        archivedAt: null,
        archiveReason: null,
        updatedAt: nowIso,
        version: task.version + 1,
      };
    }),
    reminders,
    reminderInstances,
    history: [...database.history, historyEntry(taskId, "restored", nowIso)],
  }, "task_restored");
}

export function purgeExpiredTrash(
  database: TaskDatabase,
  now: Date | string = new Date(),
  retentionDays = 30,
): TaskDatabase {
  const cutoff = new Date(toIso(now)).getTime() - retentionDays * 24 * 60 * 60 * 1000;
  const expiredTaskIds = new Set(
    database.tasks
      .filter((task) => task.deletedAt && new Date(task.deletedAt).getTime() <= cutoff)
      .map((task) => task.id),
  );
  for (const task of database.tasks) {
    if (task.parentTaskId && expiredTaskIds.has(task.parentTaskId)) expiredTaskIds.add(task.id);
  }
  if (expiredTaskIds.size === 0) return database;
  return recordTaskMetric({
    ...database,
    tasks: database.tasks.filter((task) => !expiredTaskIds.has(task.id)),
    reminders: database.reminders.filter((reminder) => !expiredTaskIds.has(reminder.taskId)),
    reminderInstances: database.reminderInstances.filter((instance) => !expiredTaskIds.has(instance.taskId)),
    history: database.history.filter((entry) => !expiredTaskIds.has(entry.taskId)),
  }, "trash_purged", expiredTaskIds.size);
}

export function permanentlyDeleteTask(database: TaskDatabase, taskId: string): TaskDatabase {
  const task = database.tasks.find((item) => item.id === taskId);
  if (!task?.deletedAt) return database;
  const taskIds = new Set([
    taskId,
    ...database.tasks.filter((item) => item.parentTaskId === taskId).map((item) => item.id),
  ]);
  return recordTaskMetric({
    ...database,
    tasks: database.tasks.filter((item) => !taskIds.has(item.id)),
    reminders: database.reminders.filter((reminder) => !taskIds.has(reminder.taskId)),
    reminderInstances: database.reminderInstances.filter((instance) => !taskIds.has(instance.taskId)),
    history: database.history.filter((entry) => !taskIds.has(entry.taskId)),
  }, "trash_deleted_permanently");
}

export function triggerDueReminders(
  database: TaskDatabase,
  now: Date | string = new Date(),
  missedAfterMs = 2 * 60 * 60 * 1000,
): { database: TaskDatabase; triggered: TriggeredReminder[] } {
  const nowIso = toIso(now);
  const nowMs = new Date(nowIso).getTime();
  const triggeredInstances: ReminderInstance[] = [];
  const reminderInstances = database.reminderInstances.map((instance) => {
    if (instance.status !== "scheduled" || new Date(instance.scheduledAt).getTime() > nowMs) return instance;
    const lateBy = nowMs - new Date(instance.scheduledAt).getTime();
    const updated: ReminderInstance = {
      ...instance,
      status: lateBy > missedAfterMs ? "missed" : "triggered",
      triggeredAt: nowIso,
      updatedAt: nowIso,
    };
    triggeredInstances.push(updated);
    return updated;
  });
  let next = { ...database, reminderInstances };
  const missedCount = triggeredInstances.filter((instance) => instance.status === "missed").length;
  const triggeredCount = triggeredInstances.length - missedCount;
  if (triggeredCount > 0) next = recordTaskMetric(next, "reminder_triggered", triggeredCount);
  if (missedCount > 0) next = recordTaskMetric(next, "reminder_missed", missedCount);
  const triggered = triggeredInstances.flatMap((instance) => {
    const task = next.tasks.find((item) => item.id === instance.taskId && !item.deletedAt);
    const reminder = next.reminders.find((item) => item.id === instance.reminderId && item.status === "active");
    return task && reminder && !["completed", "cancelled"].includes(task.status)
      ? [{ task: { ...task, ...(instance.taskOverrides ?? {}) }, reminder, instance }]
      : [];
  });
  return { database: next, triggered };
}

export function markUnattendedReminders(
  database: TaskDatabase,
  now: Date | string = new Date(),
  bubbleDurationMs = 5 * 60 * 1000,
): TaskDatabase {
  const nowIso = toIso(now);
  const nowMs = new Date(nowIso).getTime();
  let changed = 0;
  const reminderInstances = database.reminderInstances.map((instance) => {
    if (instance.status !== "triggered" || !instance.triggeredAt) return instance;
    if (nowMs - new Date(instance.triggeredAt).getTime() < bubbleDurationMs) return instance;
    changed += 1;
    return { ...instance, status: "missed" as const, updatedAt: nowIso };
  });
  if (changed === 0) return database;
  return recordTaskMetric({ ...database, reminderInstances }, "reminder_unattended", changed);
}

export function snoozeReminderInstance(
  database: TaskDatabase,
  instanceId: string,
  minutes: number,
  now: Date | string = new Date(),
): TaskDatabase {
  const nowIso = toIso(now);
  const instance = database.reminderInstances.find((item) => item.id === instanceId);
  if (!instance || !["triggered", "missed"].includes(instance.status)) return database;
  const reminder = database.reminders.find((item) => item.id === instance.reminderId);
  if (!reminder) return database;
  const scheduledAt = new Date(new Date(nowIso).getTime() + minutes * 60_000).toISOString();
  const nextReminder = {
    ...reminder,
    remindAt: reminder.repeatType === "none" ? scheduledAt : reminder.remindAt,
    snoozeCount: reminder.snoozeCount + 1,
    updatedAt: nowIso,
    version: reminder.version + 1,
  };
  return recordTaskMetric({
    ...database,
    reminders: database.reminders.map((item) => item.id === reminder.id ? nextReminder : item),
    reminderInstances: [
      ...database.reminderInstances.map((item) => item.id === instanceId ? {
        ...item, status: "snoozed" as const, handledAt: nowIso, updatedAt: nowIso,
      } : item),
      { ...createReminderInstance(nextReminder, nowIso, scheduledAt, instance.id), taskOverrides: instance.taskOverrides },
    ],
  }, "reminder_snoozed");
}

export function rescheduleReminderInstance(
  database: TaskDatabase,
  instanceId: string,
  scheduledAt: string,
  now: Date | string = new Date(),
  taskOverrides?: TaskUpdate,
): TaskDatabase {
  const nowIso = toIso(now);
  const instance = database.reminderInstances.find((item) => item.id === instanceId);
  if (!instance || !["scheduled", "triggered", "missed"].includes(instance.status)) return database;
  const reminder = database.reminders.find((item) => item.id === instance.reminderId && item.status === "active");
  if (!reminder || reminder.repeatType === "none") return database;
  const nextAt = toIso(scheduledAt);
  return recordTaskMetric({
    ...database,
    reminderInstances: [
      ...database.reminderInstances.map((item) => item.id === instanceId
        ? { ...item, status: "cancelled" as const, handledAt: nowIso, updatedAt: nowIso }
        : item),
      { ...createReminderInstance(reminder, nowIso, nextAt, instance.id), taskOverrides },
    ],
  }, "recurring_instance_rescheduled");
}

export function dismissReminderInstance(database: TaskDatabase, instanceId: string, now: Date | string = new Date()): TaskDatabase {
  const nowIso = toIso(now);
  const instance = database.reminderInstances.find((item) => item.id === instanceId);
  if (!instance || !["scheduled", "triggered", "missed"].includes(instance.status)) return database;
  const reminder = database.reminders.find((item) => item.id === instance.reminderId);
  if (!reminder || reminder.status !== "active") return database;
  const recurring = reminder.repeatType !== "none";
  const nextReminder: Reminder = recurring
    ? {
        ...reminder,
        remindAt: getNextOccurrenceAfter(reminder.remindAt, reminder.repeatType, reminder.repeatRule, nowIso),
        updatedAt: nowIso,
        version: reminder.version + 1,
      }
    : { ...reminder, status: "dismissed", updatedAt: nowIso, version: reminder.version + 1 };
  return recordTaskMetric({
    ...database,
    reminders: database.reminders.map((item) => item.id === reminder.id ? nextReminder : item),
    reminderInstances: [
      ...database.reminderInstances.map((item) => item.id === instanceId
        ? { ...item, status: "dismissed" as const, dismissedAt: nowIso, handledAt: nowIso, updatedAt: nowIso }
        : item),
      ...(recurring ? [createReminderInstance(nextReminder, nowIso)] : []),
    ],
  }, "reminder_dismissed");
}

export function closeMissedReminderSummary(database: TaskDatabase, now: Date | string = new Date()): TaskDatabase {
  const nowIso = toIso(now);
  let changed = 0;
  const reminderInstances = database.reminderInstances.map((instance) => {
    if (instance.status !== "missed" || instance.summaryClosedAt) return instance;
    changed += 1;
    return { ...instance, summaryClosedAt: nowIso, updatedAt: nowIso };
  });
  return changed > 0
    ? recordTaskMetric({ ...database, reminderInstances }, "missed_summary_closed")
    : database;
}

export function getActiveTriggeredReminders(database: TaskDatabase): TriggeredReminder[] {
  return database.reminderInstances
    .filter((instance) => ["triggered", "missed"].includes(instance.status) && !instance.summaryClosedAt)
    .flatMap((instance) => {
      const task = database.tasks.find((item) => item.id === instance.taskId && !item.deletedAt);
      const reminder = database.reminders.find((item) => item.id === instance.reminderId && item.status === "active");
      return task && reminder && !["completed", "cancelled"].includes(task.status)
        ? [{ task: { ...task, ...(instance.taskOverrides ?? {}) }, reminder, instance }]
        : [];
    })
    .sort((a, b) => {
      const priority = { high: 0, normal: 1, low: 2 };
      return priority[a.task.priority] - priority[b.task.priority]
        || new Date(a.instance.scheduledAt).getTime() - new Date(b.instance.scheduledAt).getTime();
    });
}

export function isSameLocalDay(iso: string | null, date = new Date()): boolean {
  if (!iso) return false;
  if (DATE_ONLY_PATTERN.test(iso)) return iso === toLocalDateKey(date);
  const value = new Date(iso);
  return value.getFullYear() === date.getFullYear()
    && value.getMonth() === date.getMonth()
    && value.getDate() === date.getDate();
}
