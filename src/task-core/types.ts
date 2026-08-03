export type TaskStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "cancelled";

export type TaskPriority = "low" | "normal" | "high";
export type TaskKind = "single" | "long_term" | "milestone";
export type SchedulePrecision = "date" | "datetime";
export type RepeatType = "none" | "daily" | "weekly" | "custom";
export type NotificationSoundMode = "system" | "gentle" | "pet" | "custom" | "off";

export type InterfaceFontSize = "standard" | "large" | "extraLarge";
export type ReminderStatus = "active" | "completed" | "dismissed" | "cancelled";
export type ReminderInstanceStatus =
  | "scheduled"
  | "triggered"
  | "completed"
  | "snoozed"
  | "dismissed"
  | "cancelled"
  | "missed";

export type Task = {
  id: string;
  title: string;
  note: string;
  status: TaskStatus;
  priority: TaskPriority;
  projectId: string;
  dueAt: string | null;
  kind: TaskKind;
  parentTaskId: string | null;
  startAt: string | null;
  schedulePrecision: SchedulePrecision;
  includeToday: boolean;
  attachmentRefs: string[];
  completedAt: string | null;
  cancelledAt: string | null;
  postponedCount: number;
  createdAt: string;
  updatedAt: string;
  deletedAt: string | null;
  archivedAt: string | null;
  archiveReason: "parent_completed" | null;
  version: number;
  sourceDeviceId: string;
  /** Optional provenance for tasks created from companion chat. */
  sourceMessageId?: string | null;
  evidence?: string | null;
  /** The pet that surfaced the task; the task itself remains user-scoped. */
  createdByPetId?: string | null;
};

export type RepeatRule = {
  weekdays?: number[];
};

export type Reminder = {
  id: string;
  taskId: string;
  remindAt: string;
  repeatType: RepeatType;
  repeatRule: RepeatRule | null;
  status: ReminderStatus;
  snoozeCount: number;
  createdAt: string;
  updatedAt: string;
  deletedAt: string | null;
  version: number;
};

export type ReminderInstance = {
  id: string;
  reminderId: string;
  taskId: string;
  scheduledAt: string;
  triggeredAt: string | null;
  snoozedFrom: string | null;
  snoozeCount: number;
  dismissedAt: string | null;
  handledAt: string | null;
  status: ReminderInstanceStatus;
  createdAt: string;
  updatedAt: string;
  taskOverrides?: TaskUpdate;
  summaryClosedAt?: string | null;
};

export type TaskHistoryEntry = {
  id: string;
  taskId: string;
  type: "completed" | "postponed" | "cancelled" | "restored";
  fromAt: string | null;
  toAt: string | null;
  createdAt: string;
};

export type TaskSettings = {
  notificationSound: NotificationSoundMode;
  interfaceFontSize: InterfaceFontSize;
  customNotificationSoundName: string | null;
  customNotificationSoundDataUrl: string | null;
  customNotificationSoundDurationMs: number | null;
  backgroundReminders: boolean;
  bubbleDurationMinutes: 1 | 3 | 5 | 10;
  dailyReview: boolean;
  timezoneOffsetMinutes: number;
  lastOverduePromptDate: string | null;
};

export type TaskDatabase = {
  schemaVersion: 2;
  tasks: Task[];
  reminders: Reminder[];
  reminderInstances: ReminderInstance[];
  history: TaskHistoryEntry[];
  metrics: Record<string, number>;
  settings: TaskSettings;
};

export type MilestoneDraft = {
  id?: string;
  title: string;
  dueAt: string;
  schedulePrecision?: SchedulePrecision;
  remindAt?: string | null;
};

export type TaskDraft = {
  title: string;
  note?: string;
  priority?: TaskPriority;
  projectId?: string;
  dueAt?: string | null;
  kind?: TaskKind;
  parentTaskId?: string | null;
  startAt?: string | null;
  schedulePrecision?: SchedulePrecision;
  milestones?: MilestoneDraft[];
  remindAt?: string | null;
  repeatType?: RepeatType;
  repeatRule?: RepeatRule | null;
  includeToday?: boolean;
  attachmentRefs?: string[];
  sourceMessageId?: string | null;
  evidence?: string | null;
  createdByPetId?: string | null;
};

export type TaskUpdate = Partial<TaskDraft>;

export type TriggeredReminder = {
  task: Task;
  reminder: Reminder;
  instance: ReminderInstance;
};
