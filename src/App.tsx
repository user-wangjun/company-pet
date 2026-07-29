import { useEffect, useMemo, useRef, useState } from "react";
import type {
  CSSProperties,
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent,
} from "react";
import { invoke } from "@tauri-apps/api/core";
import {
  currentMonitor,
  getCurrentWindow,
  LogicalSize,
  primaryMonitor,
  PhysicalPosition,
  type Monitor,
} from "@tauri-apps/api/window";
import { listen } from "@tauri-apps/api/event";
import {
  isPermissionGranted as isNativeNotificationPermissionGranted,
  removeActive as removeActiveNotifications,
  requestPermission as requestNativeNotificationPermission,
  sendNotification as sendNativeNotification,
} from "@tauri-apps/plugin-notification";
import {
  AnimatedSprite,
  Application,
  Assets,
  Rectangle,
  Texture,
} from "pixi.js";
import "./App.css";
import { LetterReader } from "./platform-mail/LetterReader";
import { MailboxPanel } from "./platform-mail/MailboxPanel";
import {
  BUILT_IN_LETTERS,
  CARE_REMINDER_LETTER_ID,
  WELCOME_LETTER_ID,
  deleteReadLetters,
  getUnreadCount,
  markAllLettersRead,
  markLetterRead,
  readMailboxState,
  receiveLetter,
  shouldShowFirstUseLetter,
  writeMailboxState,
  type MailboxState,
  type PlatformLetter,
} from "./platform-mail/mailbox";
import type { LetterOpenMode } from "./platform-mail/letterExperience";
import MarketingPage from "./marketing/MarketingPage";
import { isMarketingRoute } from "./marketing/marketingContent";
import type {
  DesktopIconBounds,
  DesktopIconInteractionState,
} from "./pet-core/interaction";
import {
  HOVER_EAT_DELAY_MS,
  findDesktopIconTarget,
  getDesktopIconBumpWindowPosition,
  formatDesktopIconBubbleText,
  formatDesktopIconWrapBubbleText,
  getDesktopIconWrapWindowPosition,
  getDraggedWindowPosition,
  isPrimaryButtonPressed,
  isPointerCancellation,
  resolveDragAnimationName,
  shouldStartDrag,
  shouldTriggerHoverEat,
  updateDesktopIconInteraction,
} from "./pet-core/interaction";
import {
  buildAnimationFrameRects,
} from "./pet-core/animationRows";
import {
  createDragDirectionState,
  updateDragDirection,
  type DragDirectionState,
} from "./pet-core/dragDirection";
import {
  getPetAnimationTransform,
  PET_BUBBLE_BOTTOM_PX,
} from "./pet-core/visual";
import {
  APP_DISPLAY_NAME,
  clampWindowPositionToWorkArea,
  getPhysicalPetAnchor,
  getInitialPetWindowPosition,
  getWindowPositionForPhysicalPetAnchor,
  PLATFORM_START_OPEN,
  PLATFORM_START_SECTION,
  type PetViewport,
  type PhysicalPetAnchor,
  type WorkArea,
  type WindowPosition,
  type WindowSize,
} from "./pet-core/platform";
import {
  chooseInitialPetId,
  createPetCatalog,
  DEFAULT_PET_ID,
  getPetIndexUrl,
  getPetManifestUrl,
  type PetCatalogItem,
  type PetManifest,
  resolvePetAssetUrl,
} from "./pet-core/petAssets";
import {
  loadPetDialoguePackage,
  resolvePetDialogue,
  type PetDialogueEvent,
  type PetDialoguePackage,
} from "./pet-core/dialogue";
import {
  createPetSoundPlayer,
  type PetSoundPlayer,
} from "./pet-core/sound";
import { CompanionChatBubble } from "./pet-core/CompanionChatBubble";
import {
  loadPetCompanionChatPackage,
  resolveCompanionChatPackage,
  type CompanionChatPackage,
} from "./pet-core/companionChat";
import {
  INACTIVE_COMPANION_CHAT,
  createLocalCompanionChatProvider,
  exitCompanionChat,
  receiveCompanionReply,
  sendCompanionMessage,
  shouldAutoExitCompanionChat,
  stopCompanionReply,
  updateCompanionDraft,
  type CompanionChatState,
} from "./pet-core/companionChatRuntime";
import {
  deleteRecentPreference,
  extractCompanionPreference,
  isForgetRecentPreferenceRequest,
  readCompanionPreferences,
  upsertCompanionPreference,
  writeCompanionPreferences,
  type CompanionPreferencesState,
} from "./pet-core/companionPreferences";
import {
  markCareReminderDelivered,
  readCareReminderState,
  selectDueCareReminder,
  selectTimedCareReminder,
  unmarkCareReminderDelivered,
  writeCareReminderState,
  type CareReminderKind,
  type CareReminderState,
  type CareReminderSettings as CareReminderSettingsValue,
} from "./pet-core/careReminders";
import {
  createLatestWindowLayoutScheduler,
  revealHiddenPetForCareReminder,
  shouldResizeReminderWindow,
  shouldUseExpandedReminderWindow,
} from "./pet-core/careReminderWindow";
import {
  PLATFORM_FEEDBACK_BUBBLE_MS,
  expireBubbleText,
} from "./pet-core/bubbleLifecycle";
import {
  getInteractionAnimationSpec,
  resolveActionPlaybackSteps,
} from "./pet-core/interactionPlayback";
import {
  resolvePetInteractionManifest,
  type PetActionSpec,
  type PetAnimationSpec,
  type PetDirectionMode,
  type PetFacing,
  type PetSequenceSpec,
  type ResolvedPetInteractionManifest,
} from "./pet-core/petInteractionManifest";
import {
  checkForLatestRelease,
  getCurrentAppVersion,
  type UpdateCheckResult,
} from "./pet-update/updateCheck";
import { UpdateDialog } from "./pet-update/UpdateDialog";
import { startInstallerUpdate } from "./pet-update/installUpdate";
import {
  loadTaskFeedbackPackage,
  resolveTaskFeedback,
  type TaskFeedbackPackage,
  type TaskFeedbackScene,
} from "./pet-core/taskFeedback";
import { QuickCreateTask } from "./task-core/QuickCreateTask";
import { TaskContextMenu } from "./task-core/TaskContextMenu";
import { TaskReminderStack } from "./task-core/TaskReminderStack";
import { TaskWorkspace } from "./task-core/TaskWorkspace";
import {
  completeReminderInstance,
  closeMissedReminderSummary,
  createTask,
  dismissReminderInstance,
  getActiveTriggeredReminders,
  markUnattendedReminders,
  purgeExpiredTrash,
  readTaskDatabase,
  reconcileTaskTimezone,
  recordTaskMetric,
  snoozeReminderInstance,
  triggerDueReminders,
  writeTaskDatabase,
  updateTaskSettings,
} from "./task-core/taskStore";
import { selectTasks, type TaskListView } from "./task-core/taskQueries";
import type { TaskDatabase, TaskDraft, TriggeredReminder } from "./task-core/types";
import "./task-core/task-ui.css";
const CURRENT_PET_STORAGE_KEY = "desktop-pet.currentPetId";
const PET_WINDOW_SIZE = { width: 165, height: 215 };
const PET_REMINDER_WINDOW_SIZE = { width: 240, height: 450 };
const PLATFORM_PANEL_WIDTH = 860;
const PLATFORM_PET_RAIL_WIDTH = PET_WINDOW_SIZE.width + 12;
const PLATFORM_PET_INSET_PX = 6;
const PLATFORM_WINDOW_SIZE = {
  width: PLATFORM_PANEL_WIDTH + PLATFORM_PET_RAIL_WIDTH,
  height: 590,
};
const QUICK_CREATE_WINDOW_SIZE = { width: 390, height: 290 };

type PetIndex = {
  pets: string[];
};

function randomInRange(min: number, max: number): number {
  return Math.random() * (max - min) + min;
}

const CELL_WIDTH = 192;
const CELL_HEIGHT = 208;

type AnimationName = string;
type AvailableUpdate = Extract<UpdateCheckResult, { status: "available" }>;
type PressSource = "pointer" | "mouse";
type TauriWindow = ReturnType<typeof getCurrentWindow>;
type WindowMode = "platform" | "pet" | "quick-create";
type AppliedWindowLayout = {
  mode: WindowMode;
  logicalSize: WindowSize;
  position: WindowPosition;
};
type PhysicalPetPlacement = {
  anchor: PhysicalPetAnchor;
  scaleFactor: number;
  workArea: WorkArea;
};
type OpenPlatformPayload = {
  resetPetPosition?: boolean;
};
type ActiveCareReminderPrompt =
  | {
      source: "timed";
      kind: Extract<CareReminderKind, "meal" | "sleep">;
      deliveredKey: string;
    }
  | {
      source: "random";
      kind: Extract<CareReminderKind, "wellness">;
      expiresAt: number;
    };

const CARE_REMINDER_SNOOZE_MS = 10 * 60 * 1000;
const RANDOM_REMINDER_PROMPT_MS = 2 * 60 * 1000;

function getPetViewportForLayout(
  mode: WindowMode,
  logicalSize: WindowSize,
): PetViewport {
  if (mode === "platform") {
    return {
      x: logicalSize.width - PLATFORM_PET_INSET_PX - PET_WINDOW_SIZE.width,
      y: logicalSize.height - PET_WINDOW_SIZE.height,
      width: PET_WINDOW_SIZE.width,
      height: PET_WINDOW_SIZE.height,
    };
  }

  if (mode === "quick-create") {
    return {
      x: logicalSize.width - PET_WINDOW_SIZE.width,
      y: logicalSize.height - PET_WINDOW_SIZE.height,
      width: PET_WINDOW_SIZE.width,
      height: PET_WINDOW_SIZE.height,
    };
  }

  if (!isSameWindowSize(logicalSize, PET_WINDOW_SIZE)) {
    return {
      x: logicalSize.width - PET_WINDOW_SIZE.width,
      y: logicalSize.height - PET_WINDOW_SIZE.height,
      width: PET_WINDOW_SIZE.width,
      height: PET_WINDOW_SIZE.height,
    };
  }

  return {
    x: 0,
    y: 0,
    width: logicalSize.width,
    height: logicalSize.height,
  };
}

function isSameWindowSize(left: WindowSize, right: WindowSize): boolean {
  return left.width === right.width && left.height === right.height;
}

function isTauriRuntime(): boolean {
  return (
    typeof window !== "undefined" &&
    "__TAURI_INTERNALS__" in window
  );
}

async function loadPetManifest(petId = DEFAULT_PET_ID): Promise<PetManifest> {
  const response = await fetch(getPetManifestUrl(petId));

  if (!response.ok) {
    throw new Error(`Failed to load pet manifest: ${response.status}`);
  }

  return response.json() as Promise<PetManifest>;
}

function readSavedPetId(): string | null {
  try {
    return window.localStorage.getItem(CURRENT_PET_STORAGE_KEY);
  } catch {
    return null;
  }
}

function saveSelectedPetId(petId: string): void {
  try {
    window.localStorage.setItem(CURRENT_PET_STORAGE_KEY, petId);
  } catch {
    // Persisting the choice is best effort; the active in-memory pet still changes.
  }
}

function getOptionalCurrentWindow(): TauriWindow | null {
  if (!isTauriRuntime()) return null;

  try {
    return getCurrentWindow();
  } catch {
    return null;
  }
}

function recordInteraction(event: string): Promise<unknown> {
  return invoke("record_interaction", { event }).catch(() => {});
}

function localDateKey(date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function notificationIdForInstance(instanceId: string): number {
  let hash = 0;
  for (let index = 0; index < instanceId.length; index += 1) {
    hash = (Math.imul(31, hash) + instanceId.charCodeAt(index)) | 0;
  }
  return Math.abs(hash || 1);
}

function listenToAppEvent<T = undefined>(
  event: string,
  handler: (payload: T) => void,
): Promise<() => void> {
  if (!isTauriRuntime()) {
    return Promise.resolve(() => {});
  }

  try {
    return listen<T>(event, (appEvent) => handler(appEvent.payload)).catch(
      () => () => {},
    );
  } catch {
    return Promise.resolve(() => {});
  }
}

async function getPlacementMonitor(): Promise<Monitor | null> {
  return (
    (await currentMonitor().catch(() => null)) ??
    (await primaryMonitor().catch(() => null))
  );
}

function getPhysicalWindowSize(
  logicalSize: WindowSize,
  monitor: Monitor,
): WindowSize {
  const scaleFactor = monitor.scaleFactor > 0 ? monitor.scaleFactor : 1;

  return {
    width: Math.round(logicalSize.width * scaleFactor),
    height: Math.round(logicalSize.height * scaleFactor),
  };
}

async function setWindowSize(
  appWindow: TauriWindow,
  size: WindowSize,
): Promise<void> {
  await appWindow.setSize(new LogicalSize(size.width, size.height));
}

async function setWindowPosition(
  appWindow: TauriWindow,
  position: WindowPosition,
): Promise<void> {
  await appWindow.setPosition(new PhysicalPosition(position.x, position.y));
}

function DesktopPetApp() {
  const pixiHost = useRef<HTMLDivElement>(null);
  const spriteRef = useRef<AnimatedSprite | null>(null);
  const animationsRef = useRef<Record<AnimationName, Texture[]> | null>(null);
  const animationSpecsRef = useRef<Record<AnimationName, PetAnimationSpec> | null>(null);
  const interactionManifestRef = useRef<ResolvedPetInteractionManifest | null>(null);
  const soundPlayerRef = useRef<PetSoundPlayer | null>(null);
  const systemTaskNotifications = useRef<Map<string, Notification>>(new Map());
  const nativeTaskNotifications = useRef<Map<string, number>>(new Map());
  const customTaskNotifications = useRef<Set<string>>(new Set());
  const missedSummaryNotificationId = useRef<string | null>(null);
  const recentTaskCompletion = useRef({ count: 0, lastAt: 0 });
  const returnToIdleTimer = useRef<number | null>(null);
  const transientBubbleTimer = useRef<number | null>(null);
  const hoverEatTimer = useRef<number | null>(null);
  const iconHugClickThroughTimer = useRef<number | null>(null);
  const iconHugLockedUntil = useRef(0);
  const desktopIconProbeTimer = useRef<number | null>(null);
  const desktopIconProbeInFlight = useRef(false);
  const desktopIconProbeFailed = useRef(false);
  const desktopIconProbeSucceeded = useRef(false);
  const hoverStartedAt = useRef<number | null>(null);
  const desktopIconState = useRef<DesktopIconInteractionState>({
    activeIconKey: null,
    firstSeenAt: null,
    lastTriggeredAt: null,
  });
  const pointerState = useRef<{
    source: PressSource;
    dragging: boolean;
    pointerId: number;
    x: number;
    y: number;
    screenX: number;
    screenY: number;
    currentX: number;
    currentY: number;
    currentScreenX: number;
    currentScreenY: number;
    windowX?: number;
    windowY?: number;
    scaleFactor?: number;
    dragDirection?: DragDirectionState;
  } | null>(null);
  const lastPointerEventAt = useRef(0);
  const clickCount = useRef(0);
  const clickTimer = useRef<number | null>(null);
  const careReminderState = useRef<CareReminderState>(readCareReminderState());
  const [careReminderSettings, setCareReminderSettings] = useState(careReminderState.current.settings);
  const [careReminderNoticeDismissed, setCareReminderNoticeDismissed] = useState(careReminderState.current.systemPopupNoticeDismissed);
  const nextWellnessTime = useRef(Date.now() + careReminderState.current.settings.wellness.intervalMinutes * 60 * 1000);
  const timedCareSnoozedUntil = useRef(0);
  const nextIdleQuirkTime = useRef(Date.now() + randomInRange(20, 30) * 1000);
  const currentAnimation = useRef<AnimationName>("idle");
  const currentFacing = useRef<PetFacing>("right");
  const playbackToken = useRef(0);
  const [bubbleText, setBubbleText] = useState<string | null>(null);
  const careReminderPromptRef = useRef<ActiveCareReminderPrompt | null>(null);
  const [careReminderPrompt, setCareReminderPrompt] =
    useState<ActiveCareReminderPrompt | null>(null);
  const [isPlatformOpen, setIsPlatformOpen] = useState(PLATFORM_START_OPEN);
  const [isTaskMenuOpen, setIsTaskMenuOpen] = useState(false);
  const [isQuickCreateOpen, setIsQuickCreateOpen] = useState(false);
  const [platformSection, setPlatformSection] = useState<"tasks" | "pets">(PLATFORM_START_SECTION);
  const [taskListView, setTaskListView] = useState<TaskListView>("today");
  const [taskDetailId, setTaskDetailId] = useState<string | null>(null);
  const [hiddenTaskReminderIds, setHiddenTaskReminderIds] = useState<Set<string>>(() => new Set());
  const [taskDatabase, setTaskDatabase] = useState<TaskDatabase>(() => {
    const stored = readTaskDatabase();
    const timezoneAdjusted = reconcileTaskTimezone(stored);
    const purged = purgeExpiredTrash(timezoneAdjusted);
    if (purged !== stored) writeTaskDatabase(purged);
    return purged;
  });
  const [availablePetIds, setAvailablePetIds] = useState<string[]>([
    DEFAULT_PET_ID,
  ]);
  const [petManifestsById, setPetManifestsById] = useState<
    Record<string, PetManifest>
  >({});
  const [petDialoguesById, setPetDialoguesById] = useState<
    Record<string, PetDialoguePackage>
  >({});
  const [petCompanionChatsById, setPetCompanionChatsById] = useState<
    Record<string, CompanionChatPackage>
  >({});
  const [petTaskFeedbackById, setPetTaskFeedbackById] = useState<
    Record<string, TaskFeedbackPackage>
  >({});
  const [companionChatState, setCompanionChatState] =
    useState<CompanionChatState>(INACTIVE_COMPANION_CHAT);
  const companionChatStateRef = useRef<CompanionChatState>(INACTIVE_COMPANION_CHAT);
  const companionPreferencesRef = useRef<CompanionPreferencesState>(
    readCompanionPreferences(),
  );
  const [activePetId, setActivePetId] = useState(DEFAULT_PET_ID);
  const windowMode = useRef<WindowMode>(isPlatformOpen ? "platform" : "pet");
  const appliedWindowLayout = useRef<AppliedWindowLayout | null>(null);
  const physicalPetPlacement = useRef<PhysicalPetPlacement | null>(null);
  const windowLayoutScheduler = useRef(createLatestWindowLayoutScheduler());
  const resetPetPositionOnNextOpen = useRef(true);
  const mailboxButtonRef = useRef<HTMLButtonElement>(null);
  const initialMailboxStateRef = useRef<MailboxState | null>(null);
  const initialMailboxState =
    initialMailboxStateRef.current ?? readMailboxState();
  initialMailboxStateRef.current = initialMailboxState;
  const [mailboxState, setMailboxState] = useState<MailboxState>(
    initialMailboxState,
  );
  const [isMailboxOpen, setIsMailboxOpen] = useState(false);
  const [activeLetterId, setActiveLetterId] = useState<string | null>(() =>
    shouldShowFirstUseLetter(initialMailboxState)
      ? WELCOME_LETTER_ID
      : null,
  );
  const [letterOpenMode, setLetterOpenMode] =
    useState<LetterOpenMode>("first-use");
  const [isMailboxReceiving, setIsMailboxReceiving] = useState(false);
  const [pendingUpdate, setPendingUpdate] = useState<AvailableUpdate | null>(null);
  const [, setIsCheckingUpdate] = useState(false);
  const updateCheckInFlight = useRef(false);
  const petCatalog = useMemo(
    () => createPetCatalog(availablePetIds, petManifestsById, activePetId),
    [activePetId, availablePetIds, petManifestsById],
  );
  const activePet = petCatalog.find((pet) => pet.id === activePetId);
  const activePetManifest = petManifestsById[activePetId];
  const dailyReviewSpeakerTexts = useMemo(
    () => ({
      at_least_half: resolveTaskFeedback(petTaskFeedbackById[activePetId], "dailyReviewAtLeastHalf", "今天完成了不少，辛苦了。", () => 0).text,
      below_half: resolveTaskFeedback(petTaskFeedbackById[activePetId], "dailyReviewBelowHalf", "今天已经迈出了一步，剩下的我们慢慢来。", () => 0).text,
      zero: resolveTaskFeedback(petTaskFeedbackById[activePetId], "dailyReviewZero", "今天还没有留下完成记录，明天我们从一件小事开始吧。", () => 0).text,
    }),
    [activePetId, petTaskFeedbackById],
  );
  const visibleUnreadCount = getUnreadCount(BUILT_IN_LETTERS, mailboxState);
  const activeLetter =
    BUILT_IN_LETTERS.find((letter) => letter.id === activeLetterId) ?? null;
  const activeTaskReminders = useMemo(
    () => getActiveTriggeredReminders(taskDatabase),
    [taskDatabase],
  );
  const visibleTaskReminders = useMemo(
    () => activeTaskReminders.filter(({ instance }) => {
      if (hiddenTaskReminderIds.has(instance.id)) return false;
      if (!instance.triggeredAt) return true;
      return Date.now() - new Date(instance.triggeredAt).getTime() < taskDatabase.settings.bubbleDurationMinutes * 60 * 1000;
    }),
    [activeTaskReminders, hiddenTaskReminderIds, taskDatabase.settings.bubbleDurationMinutes],
  );
  const isReminderWindowExpanded = shouldUseExpandedReminderWindow(
    visibleTaskReminders.length,
    careReminderPrompt !== null,
  );

  useEffect(() => {
    const activeIds = new Set(taskDatabase.reminderInstances
      .filter((instance) => ["triggered", "missed"].includes(instance.status))
      .map((instance) => instance.id));
    for (const [instanceId, notification] of systemTaskNotifications.current) {
      if (activeIds.has(instanceId)) continue;
      notification.close();
      systemTaskNotifications.current.delete(instanceId);
    }
    for (const [instanceId, notificationId] of nativeTaskNotifications.current) {
      if (activeIds.has(instanceId)) continue;
      void removeActiveNotifications([{ id: notificationId }]).catch(() => {});
      nativeTaskNotifications.current.delete(instanceId);
    }
    for (const instanceId of customTaskNotifications.current) {
      if (activeIds.has(instanceId)) continue;
      void invoke("clear_task_notification", { instanceId }).catch(() => {});
      customTaskNotifications.current.delete(instanceId);
    }
  }, [taskDatabase]);

  const commitTaskDatabase = (next: TaskDatabase, feedback?: string) => {
    const completedDelta = next.history.filter((entry) => entry.type === "completed").length
      - taskDatabase.history.filter((entry) => entry.type === "completed").length;
    const postponedDelta = next.history.filter((entry) => entry.type === "postponed").length
      - taskDatabase.history.filter((entry) => entry.type === "postponed").length;
    const createdDelta = next.tasks.length - taskDatabase.tasks.length;
    const nextActiveInstanceIds = new Set(next.reminderInstances
      .filter((instance) => ["triggered", "missed"].includes(instance.status))
      .map((instance) => instance.id));
    for (const instance of taskDatabase.reminderInstances) {
      if (!["triggered", "missed"].includes(instance.status) || nextActiveInstanceIds.has(instance.id)) continue;
      systemTaskNotifications.current.get(instance.id)?.close();
      if (isTauriRuntime()) void invoke("clear_task_notification", { instanceId: instance.id }).catch(() => {});
      customTaskNotifications.current.delete(instance.id);
    }
    writeTaskDatabase(next);
    setTaskDatabase(next);
    if (feedback) showTransientBubbleText(feedback);
    const resolved = getActiveInteractionManifest();
    if (!resolved) return;
    if (completedDelta > 0) {
      const now = Date.now();
      recentTaskCompletion.current = {
        count: now - recentTaskCompletion.current.lastAt <= 5000
          ? recentTaskCompletion.current.count + completedDelta
          : completedDelta,
        lastAt: now,
      };
      const multiple = recentTaskCompletion.current.count > 1;
      playTaskFeedback(
        multiple ? "taskCompletionBurst" : "taskCompleted",
        multiple ? `连续完成了 ${recentTaskCompletion.current.count} 件，真不错。` : "做完啦，已经替你收好了。",
        resolved.doubleClick,
      );
    } else if (createdDelta > 0) {
      playTaskFeedback("taskCreated", feedback ?? "已经替你记好啦。", resolved.singleClick);
    } else if (postponedDelta > 0) {
      playTaskFeedback("taskRescheduled", feedback ?? "时间已经重新安排好。", resolved.idle);
    }
  };

  if (soundPlayerRef.current === null) {
    soundPlayerRef.current = createPetSoundPlayer({ enabled: false });
  }

  const checkForUpdates = async (manual = true) => {
    if (updateCheckInFlight.current) return;

    updateCheckInFlight.current = true;
    setIsCheckingUpdate(true);
    setPendingUpdate(null);

    if (manual) {
      setBubbleText("正在检查更新中……");
    }

    try {
      const currentVersion = await getCurrentAppVersion();
      const result = await checkForLatestRelease(currentVersion);

      if (result.status === "available") {
        recordInteraction("update_available");
        setPendingUpdate(result);
        setBubbleText(`发现新版本 ${result.latestVersion}，点“下载并安装”会自动安装。`);
        return;
      }

      if (manual) {
        setBubbleText(
          result.status === "current"
            ? "当前已经是最新版本。"
            : result.message,
        );
      }
    } finally {
      updateCheckInFlight.current = false;
      setIsCheckingUpdate(false);
    }
  };

  const confirmPendingUpdate = () => {
    const update = pendingUpdate;
    setPendingUpdate(null);
    if (!update) return;

    recordInteraction("update_installer_download");
    setBubbleText("正在下载安装包，下载完成后会自动打开安装程序。");
    void startInstallerUpdate(update.downloadUrl)
      .then(() => {
        setBubbleText("安装包已打开，请按提示完成安装。");
      })
      .catch(() => {
        setBubbleText("下载安装包失败，请稍后再试。");
      });
  };

  const cancelPendingUpdate = () => {
    setPendingUpdate(null);
    clearDefaultBubbleText();
  };

  useEffect(() => {
    companionChatStateRef.current = companionChatState;
  }, [companionChatState]);
  useEffect(() => {
    let soundEnabled = false;

    const unlistenUpdatePromise = listenToAppEvent("check-update", () => {
      void checkForUpdates(true);
    });
    const unlistenPlatformPromise = listenToAppEvent<OpenPlatformPayload>(
      "open-platform",
      (payload) => {
        if (payload?.resetPetPosition) {
          resetPetPositionOnNextOpen.current = true;
        }
        setIsPlatformOpen(true);
        recordInteraction("platform_open_from_tray");
      },
    );
    const unlistenSoundPromise = listenToAppEvent("toggle-sound", () => {
      soundEnabled = !soundEnabled;
      soundPlayerRef.current?.setEnabled(soundEnabled);
      recordInteraction(soundEnabled ? "sound_enabled" : "sound_disabled");
    });
    const unlistenQuickTaskPromise = listenToAppEvent("open-task-quick-create", () => {
      openQuickTaskCreate();
    });
    const unlistenTodayTasksPromise = listenToAppEvent("open-task-today", () => {
      openTaskPlatform("today");
    });
    const unlistenTaskRemindersPromise = listenToAppEvent("open-task-reminders", () => {
      openTaskPlatform("upcoming");
    });
    const unlistenTaskWakeupPromise = listenToAppEvent("task-scheduler-wakeup", () => {
      window.dispatchEvent(new Event("task-scheduler-wakeup"));
    });
    const handleTaskNotificationAction = ({ instanceId, action }: { instanceId: string; action: string }) => {
        if (action === "summary-detail") {
          openTaskPlatform("today");
          return;
        }
        if (action === "summary-close") {
          void invoke("clear_task_notification", { instanceId }).catch(() => {});
          const next = closeMissedReminderSummary(readTaskDatabase());
          writeTaskDatabase(next);
          setTaskDatabase(next);
          return;
        }
        if (action === "detail") {
          const instance = readTaskDatabase().reminderInstances.find((item) => item.id === instanceId);
          openTaskPlatform("today", instance?.taskId ?? null);
          return;
        }
        const current = readTaskDatabase();
        let next = current;
        if (action === "complete") next = completeReminderInstance(current, instanceId);
        if (action === "snooze-10") next = snoozeReminderInstance(current, instanceId, 10);
        if (action === "snooze-30") next = snoozeReminderInstance(current, instanceId, 30);
        if (action === "snooze-60") next = snoozeReminderInstance(current, instanceId, 60);
        if (action === "dismiss") next = dismissReminderInstance(current, instanceId);
        if (next === current) return;
        next = recordTaskMetric(next, "system_notification_action");
        writeTaskDatabase(next);
        setTaskDatabase(next);
        customTaskNotifications.current.delete(instanceId);
      };
    const unlistenTaskNotificationActionPromise = listenToAppEvent<{ instanceId: string; action: string }>(
      "task-notification-action",
      handleTaskNotificationAction,
    );

    if (isTauriRuntime()) {
      void invoke<Array<{ instanceId: string; action: string }>>("get_initial_task_notification_actions")
        .then((actions) => actions.forEach(handleTaskNotificationAction))
        .catch(() => {});
      void invoke<boolean>("is_task_scheduler_wakeup").then((isWakeup) => {
        if (!isWakeup) return;
        setIsPlatformOpen(false);
        setIsQuickCreateOpen(false);
        window.dispatchEvent(new Event("task-scheduler-wakeup"));
      }).catch(() => {});
    }

    return () => {
      void unlistenUpdatePromise.then((unlisten) => unlisten());
      void unlistenPlatformPromise.then((unlisten) => unlisten());
      void unlistenSoundPromise.then((unlisten) => unlisten());
      void unlistenQuickTaskPromise.then((unlisten) => unlisten());
      void unlistenTodayTasksPromise.then((unlisten) => unlisten());
      void unlistenTaskRemindersPromise.then((unlisten) => unlisten());
      void unlistenTaskWakeupPromise.then((unlisten) => unlisten());
      void unlistenTaskNotificationActionPromise.then((unlisten) => unlisten());
    };
  }, []);

  useEffect(() => {
    if (!isTauriRuntime()) return;
    const schedules = (taskDatabase.settings.backgroundReminders ? taskDatabase.reminderInstances : [])
      .filter((instance) => instance.status === "scheduled")
      .map((instance) => ({ instanceId: instance.id, scheduledAt: instance.scheduledAt }));
    void invoke("sync_task_schedules", { schedules }).catch(() => {
      recordInteraction("task_schedule_sync_failed");
    });
  }, [taskDatabase.reminderInstances, taskDatabase.settings.backgroundReminders]);

  useEffect(() => {
    let disposed = false;

    const loadPetCatalog = async () => {
      try {
        const indexResponse = await fetch(getPetIndexUrl());

        if (!indexResponse.ok) {
          throw new Error(`Failed to load pet index: ${indexResponse.status}`);
        }

        const index = (await indexResponse.json()) as PetIndex;
        const petIds =
          Array.isArray(index.pets) && index.pets.length > 0
            ? index.pets
            : [DEFAULT_PET_ID];
        const manifestEntries = await Promise.all(
          petIds.map(async (petId) => [petId, await loadPetManifest(petId)] as const),
        );
        const manifests = Object.fromEntries(manifestEntries);
        const dialogueEntries = await Promise.all(
          manifestEntries.map(
            async ([petId, manifest]) =>
              [petId, await loadPetDialoguePackage(manifest)] as const,
          ),
        );
        const companionChatEntries = await Promise.all(
          manifestEntries.map(
            async ([petId, manifest]) =>
              [petId, await loadPetCompanionChatPackage(manifest)] as const,
          ),
        );
        const taskFeedbackEntries = await Promise.all(
          manifestEntries.map(
            async ([petId, manifest]) =>
              [petId, await loadTaskFeedbackPackage(manifest)] as const,
          ),
        );
        const initialPetId = chooseInitialPetId(petIds, readSavedPetId());

        if (disposed) return;
        setAvailablePetIds(petIds);
        setPetManifestsById(manifests);
        setPetDialoguesById(Object.fromEntries(dialogueEntries));
        setPetCompanionChatsById(Object.fromEntries(companionChatEntries));
        setPetTaskFeedbackById(Object.fromEntries(taskFeedbackEntries));
        setActivePetId(initialPetId);
      } catch {
        const fallbackManifest = await loadPetManifest(DEFAULT_PET_ID).catch(
          () => null,
        );

        if (disposed || !fallbackManifest) return;
        const fallbackDialogues = await loadPetDialoguePackage(fallbackManifest);
        const fallbackCompanionChat =
          await loadPetCompanionChatPackage(fallbackManifest);
        const fallbackTaskFeedback = await loadTaskFeedbackPackage(fallbackManifest);
        if (disposed) return;
        setAvailablePetIds([DEFAULT_PET_ID]);
        setPetManifestsById({ [DEFAULT_PET_ID]: fallbackManifest });
        setPetDialoguesById({ [DEFAULT_PET_ID]: fallbackDialogues });
        setPetCompanionChatsById({ [DEFAULT_PET_ID]: fallbackCompanionChat });
        setPetTaskFeedbackById({ [DEFAULT_PET_ID]: fallbackTaskFeedback });
        setActivePetId(DEFAULT_PET_ID);
      }
    };

    void loadPetCatalog();

    return () => {
      disposed = true;
    };
  }, []);

  useEffect(() => {
    soundPlayerRef.current?.setManifest(activePetId, activePetManifest?.sounds);

    return () => {
      soundPlayerRef.current?.clear();
    };
  }, [activePetId, activePetManifest]);

  useEffect(() => {
    if (isPlatformOpen || isQuickCreateOpen) return;
    const today = localDateKey();
    if (taskDatabase.settings.lastOverduePromptDate === today) return;
    const overdue = selectTasks(taskDatabase, "overdue");
    if (overdue.length === 0) return;
    const next = updateTaskSettings(taskDatabase, { lastOverduePromptDate: today });
    writeTaskDatabase(next);
    setTaskDatabase(next);
    const resolved = getActiveInteractionManifest();
    if (resolved) playTaskFeedback(
      "taskOverdue",
      overdue.length === 1 ? `还有「${overdue[0].title}」在等你，有空时看看就好。` : `今天有 ${overdue.length} 件过期事项，有空时慢慢看看。`,
      resolved.reminders.eyeCare,
    );
  }, [activePetId, isPlatformOpen, isQuickCreateOpen, taskDatabase]);

  useEffect(() => {
    clearDefaultBubbleText();
  }, [activePetId, petDialoguesById]);

  const getInitialPhysicalPetPlacement = (
    monitor: Monitor,
  ): PhysicalPetPlacement => {
    const initialPosition = getInitialPetWindowPosition(
      monitor.workArea,
      getPhysicalWindowSize(PET_WINDOW_SIZE, monitor),
    );

    return {
      anchor: getPhysicalPetAnchor(
        initialPosition,
        getPetViewportForLayout("pet", PET_WINDOW_SIZE),
        monitor.scaleFactor,
      ),
      scaleFactor: monitor.scaleFactor,
      workArea: monitor.workArea,
    };
  };

  const applyAnchoredWindowLayout = async (
    appWindow: TauriWindow,
    mode: WindowMode,
    logicalSize: WindowSize,
    shouldResetPetAnchor: boolean,
  ) => {
    const previousLayout = appliedWindowLayout.current;
    if (
      previousLayout?.mode === mode &&
      isSameWindowSize(previousLayout.logicalSize, logicalSize) &&
      !shouldResetPetAnchor
    ) {
      return;
    }

    const monitor = await getPlacementMonitor();
    const currentPosition = await appWindow.outerPosition().catch(() => null);

    if (previousLayout?.mode === "pet" && currentPosition && monitor) {
      const petWasMoved =
        currentPosition.x !== previousLayout.position.x ||
        currentPosition.y !== previousLayout.position.y;
      if (petWasMoved || physicalPetPlacement.current === null) {
        physicalPetPlacement.current = {
          anchor: getPhysicalPetAnchor(
            currentPosition,
            getPetViewportForLayout("pet", previousLayout.logicalSize),
            monitor.scaleFactor,
          ),
          scaleFactor: monitor.scaleFactor,
          workArea: monitor.workArea,
        };
      }
    }

    if (monitor && (shouldResetPetAnchor || physicalPetPlacement.current === null)) {
      physicalPetPlacement.current = getInitialPhysicalPetPlacement(monitor);
    }

    await setWindowSize(appWindow, logicalSize);

    const placement = physicalPetPlacement.current;
    if (!placement) {
      if (currentPosition) {
        appliedWindowLayout.current = {
          mode,
          logicalSize,
          position: currentPosition,
        };
      }
      return;
    }

    const anchoredPosition = getWindowPositionForPhysicalPetAnchor(
      placement.anchor,
      getPetViewportForLayout(mode, logicalSize),
      placement.scaleFactor,
    );
    const shouldKeepEntireWindowInWorkArea =
      mode !== "pet" || shouldResizeReminderWindow(PET_WINDOW_SIZE, logicalSize);
    const desiredPosition = shouldKeepEntireWindowInWorkArea
      ? clampWindowPositionToWorkArea(
          anchoredPosition,
          {
            width: Math.round(logicalSize.width * placement.scaleFactor),
            height: Math.round(logicalSize.height * placement.scaleFactor),
          },
          placement.workArea,
        )
      : anchoredPosition;

    await setWindowPosition(appWindow, desiredPosition);
    const appliedPosition = await appWindow.outerPosition().catch(
      () => desiredPosition,
    );
    appliedWindowLayout.current = {
      mode,
      logicalSize,
      position: appliedPosition,
    };
  };

  useEffect(() => {
    const appWindow = getOptionalCurrentWindow();
    if (!appWindow) return;

    const nextMode: WindowMode = isPlatformOpen
      ? "platform"
      : isQuickCreateOpen
        ? "quick-create"
        : "pet";
    windowMode.current = nextMode;

    const shouldResetPetAnchor = resetPetPositionOnNextOpen.current;
    const desiredSize = nextMode === "platform"
      ? PLATFORM_WINDOW_SIZE
      : nextMode === "quick-create"
        ? QUICK_CREATE_WINDOW_SIZE
        : isReminderWindowExpanded
          ? PET_REMINDER_WINDOW_SIZE
          : PET_WINDOW_SIZE;
    const failureEvent = nextMode === "platform"
      ? "platform_layout_failed"
      : nextMode === "quick-create"
        ? "quick_create_layout_failed"
        : "pet_layout_failed";

    void windowLayoutScheduler.current.schedule(async () => {
      await applyAnchoredWindowLayout(
        appWindow,
        nextMode,
        desiredSize,
        shouldResetPetAnchor,
      );
      if (shouldResetPetAnchor) {
        resetPetPositionOnNextOpen.current = false;
      }
    }).catch(() => {
      recordInteraction(failureEvent);
    });
  }, [
    careReminderPrompt,
    isPlatformOpen,
    isQuickCreateOpen,
    visibleTaskReminders.length,
  ]);

  const stopPlatformEvent = (
    event: ReactMouseEvent<HTMLElement> | ReactPointerEvent<HTMLElement>,
  ) => {
    event.stopPropagation();
  };

  const startPlatformWindowDrag = (
    event: ReactPointerEvent<HTMLElement>,
  ) => {
    if (event.button !== 0) return;

    event.stopPropagation();
    const appWindow = getOptionalCurrentWindow();
    if (!appWindow) return;

    void appWindow.startDragging().catch(() => {});
  };

  const closePlatform = (
    event: ReactMouseEvent<HTMLButtonElement> | ReactPointerEvent<HTMLButtonElement>,
  ) => {
    event.stopPropagation();
    clearDefaultBubbleText();
    setIsPlatformOpen(false);
    recordInteraction("platform_close");
  };

  const openTaskPlatform = (view: TaskListView = "today", taskId: string | null = null) => {
    setTaskListView(view);
    setTaskDetailId(taskId);
    setPlatformSection("tasks");
    setIsQuickCreateOpen(false);
    setIsPlatformOpen(true);
    recordInteraction(`task_platform_open_${view}`);
  };

  const openPetPlatform = () => {
    setPlatformSection("pets");
    setIsQuickCreateOpen(false);
    setIsPlatformOpen(true);
  };

  const openQuickTaskCreate = () => {
    setIsTaskMenuOpen(false);
    setIsPlatformOpen(false);
    setIsQuickCreateOpen(true);
    recordInteraction("task_quick_create_open");
  };

  const createQuickTask = (draft: TaskDraft) => {
    const created = createTask(taskDatabase, draft);
    commitTaskDatabase(recordTaskMetric(created.database, "quick_create_used"));
    setIsQuickCreateOpen(false);
    recordInteraction("task_quick_created");
  };

  const showSystemTaskNotification = async ({ task, instance }: TriggeredReminder) => {
    if (isTauriRuntime()) {
      const body = `计划时间 ${new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(new Date(instance.scheduledAt))}`;
      const shownByCustomBridge = await invoke("show_task_notification", {
        instanceId: instance.id,
        title: `待办提醒 · ${task.title}`,
        body,
        soundMode: taskDatabase.settings.notificationSound,
      }).then(() => true).catch(() => false);
      if (shownByCustomBridge) {
        customTaskNotifications.current.add(instance.id);
        return;
      }
      let permissionGranted = await isNativeNotificationPermissionGranted().catch(() => false);
      if (!permissionGranted) {
        permissionGranted = (await requestNativeNotificationPermission().catch(() => "denied")) === "granted";
      }
      if (!permissionGranted) return;
      const stillActive = readTaskDatabase().reminderInstances.some(
        (item) => item.id === instance.id && ["triggered", "missed"].includes(item.status),
      );
      if (!stillActive) return;
      const id = notificationIdForInstance(instance.id);
      sendNativeNotification({
        id,
        title: `待办提醒 · ${task.title}`,
        body: `计划时间 ${new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(new Date(instance.scheduledAt))}\n打开愈心桌宠可完成或延后提醒`,
        autoCancel: true,
      });
      nativeTaskNotifications.current.set(instance.id, id);
      return;
    }
    if (!("Notification" in window)) return;
    let permission = Notification.permission;
    if (permission === "default") {
      permission = await Notification.requestPermission().catch(() => "denied" as NotificationPermission);
    }
    if (permission !== "granted") return;
    const stillActive = readTaskDatabase().reminderInstances.some(
      (item) => item.id === instance.id && ["triggered", "missed"].includes(item.status),
    );
    if (!stillActive) return;
    const notification = new Notification(`待办提醒 · ${task.title}`, {
      body: `计划时间 ${new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(new Date(instance.scheduledAt))}\n点击查看详情`,
      tag: instance.id,
      requireInteraction: true,
    });
    notification.onclick = () => {
      openTaskPlatform("today", task.id);
      notification.close();
    };
    notification.onclose = () => systemTaskNotifications.current.delete(instance.id);
    systemTaskNotifications.current.set(instance.id, notification);
  };

  const showSystemTaskSummaryNotification = async (count: number) => {
    if (!isTauriRuntime()) return;
    const summaryId = `missed-${Date.now()}`;
    const shown = await invoke("show_task_summary_notification", {
      summaryId,
      count,
      soundMode: taskDatabase.settings.notificationSound,
    }).then(() => true).catch(() => false);
    if (shown) {
      customTaskNotifications.current.add(summaryId);
      missedSummaryNotificationId.current = summaryId;
    }
  };

  const showSystemCareNotification = async (kind: CareReminderKind) => {
    const setting = careReminderState.current.settings[kind];
    if (!setting.enabled) return;
    const copy: Record<CareReminderKind, { title: string; body: string }> = {
      wellness: { title: "休息与喝水", body: "看看远处放松眼睛，也记得喝口水。" },
      meal: { title: "用餐提醒", body: "到你设置的用餐时间啦。" },
      sleep: { title: "睡眠提醒", body: "到你计划的入睡时间啦。" },
    };
    if (isTauriRuntime()) {
      let granted = await isNativeNotificationPermissionGranted().catch(() => false);
      if (!granted) granted = (await requestNativeNotificationPermission().catch(() => "denied")) === "granted";
      if (granted) sendNativeNotification({ ...copy[kind], autoCancel: true });
      return;
    }
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification(copy[kind].title, { body: copy[kind].body, tag: `care-${kind}` });
    }
  };

  const completeTaskReminder = (_taskId: string, instanceId: string) => {
    const next = completeReminderInstance(taskDatabase, instanceId);
    if (next === taskDatabase) return;
    commitTaskDatabase(next);
    systemTaskNotifications.current.get(instanceId)?.close();
    const nativeId = nativeTaskNotifications.current.get(instanceId);
    if (nativeId !== undefined) {
      void removeActiveNotifications([{ id: nativeId }]).catch(() => {});
      nativeTaskNotifications.current.delete(instanceId);
    }
    recordInteraction("task_reminder_completed");
  };

  const snoozeTaskReminder = (instanceId: string) => {
    const next = snoozeReminderInstance(taskDatabase, instanceId, 10);
    if (next === taskDatabase) return;
    commitTaskDatabase(next);
    systemTaskNotifications.current.get(instanceId)?.close();
    const nativeId = nativeTaskNotifications.current.get(instanceId);
    if (nativeId !== undefined) {
      void removeActiveNotifications([{ id: nativeId }]).catch(() => {});
      nativeTaskNotifications.current.delete(instanceId);
    }
    const snoozeCount = next.reminderInstances.find((instance) => instance.id === instanceId)?.snoozeCount ?? 0;
    const nextInstance = next.reminderInstances.find((instance) => instance.snoozedFrom === instanceId);
    const effectiveSnoozeCount = nextInstance?.snoozeCount ?? snoozeCount;
    const resolved = getActiveInteractionManifest();
    if (resolved) playTaskFeedback(
      effectiveSnoozeCount >= 5 ? "repeatedSnooze" : "reminderSnoozed",
      effectiveSnoozeCount >= 5
        ? "已经延后好几次啦，要不要打开详情重新安排一下？"
        : "好，10分钟后再轻轻提醒你。",
      resolved.idle,
    );
    recordInteraction("task_reminder_snoozed");
  };

  const commitMailboxState = (
    update: (state: MailboxState) => MailboxState,
  ) => {
    setMailboxState((current) => {
      const next = update(current);
      writeMailboxState(next);
      return next;
    });
  };

  const openMailbox = () => {
    setIsMailboxOpen(true);
    recordInteraction("mailbox_open");
  };

  const openMailboxLetter = (letter: PlatformLetter) => {
    setIsMailboxOpen(false);
    setLetterOpenMode("mailbox");
    setActiveLetterId(letter.id);
    recordInteraction("mailbox_letter_open");
  };

  const markMailboxLetterRead = (letterId: string) => {
    commitMailboxState((state) => markLetterRead(state, letterId));
    recordInteraction("mailbox_letter_read");
  };

  const markMailboxRead = () => {
    commitMailboxState((state) =>
      markAllLettersRead(state, BUILT_IN_LETTERS),
    );
    recordInteraction("mailbox_mark_all_read");
  };

  const deleteMailboxRead = () => {
    commitMailboxState((state) =>
      deleteReadLetters(state, BUILT_IN_LETTERS),
    );
    recordInteraction("mailbox_delete_read");
  };

  const finishStoringLetter = () => {
    setActiveLetterId(null);
    setIsMailboxReceiving(true);
    window.setTimeout(() => setIsMailboxReceiving(false), 760);
    recordInteraction("mailbox_letter_stored");
  };

  const selectPet = (pet: PetCatalogItem) => {
    if (pet.id === activePetId) return;

    setCompanionChatState((current) => exitCompanionChat(current));
    saveSelectedPetId(pet.id);
    setActivePetId(pet.id);
    clearDefaultBubbleText();
    recordInteraction("platform_pet_selected");
  };

  const playPetSound = (eventName: string | undefined) => {
    if (!eventName) return;
    soundPlayerRef.current?.play(eventName);
  };

  const playTaskNotificationSound = () => {
    const { notificationSound, customNotificationSoundDataUrl } = taskDatabase.settings;
    if (notificationSound === "off" || notificationSound === "system") return;
    if (notificationSound === "pet") {
      playPetSound("taskDue");
      return;
    }
    if (notificationSound === "custom" && customNotificationSoundDataUrl) {
      void new Audio(customNotificationSoundDataUrl).play().catch(() => {});
      return;
    }
    if (notificationSound === "gentle") {
      const audio = new Audio("data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAA=");
      void audio.play().catch(() => {});
    }
  };

  const getDialoguePackageForPet = (petId: string): PetDialoguePackage => {
    const loaded = petDialoguesById[petId];
    if (loaded) return loaded;

    return petManifestsById[petId]?.dialoguesPath
      ? { status: "failed", petId }
      : { status: "not-configured", petId };
  };

  const getCompanionChatPackageForPet = (petId: string): CompanionChatPackage => {
    const loaded = petCompanionChatsById[petId];
    if (loaded) return loaded;

    return petManifestsById[petId]?.companionChatPath
      ? { status: "failed", petId }
      : { status: "not-configured", petId };
  };

  const stopCompanionChatReply = () => {
    setCompanionChatState((current) => stopCompanionReply(current));
    recordInteraction("companion_chat_stop");
  };

  const updateCompanionDraftText = (draft: string) => {
    setCompanionChatState((current) => updateCompanionDraft(current, draft));
  };

  const sendCompanionChatMessage = () => {
    const config = resolveCompanionChatPackage(
      getCompanionChatPackageForPet(activePetId),
    );
    const sent = sendCompanionMessage(companionChatStateRef.current);
    setCompanionChatState(sent);
    if (sent.mode !== "active" || !sent.pendingUserMessage) return;

    const { id, text } = sent.pendingUserMessage;
    window.setTimeout(() => {
      if (
        companionChatStateRef.current.mode !== "active" ||
        companionChatStateRef.current.pendingRequestId !== id
      ) {
        return;
      }

      if (isForgetRecentPreferenceRequest(text)) {
        const nextPreferences = deleteRecentPreference(
          companionPreferencesRef.current,
        );
        companionPreferencesRef.current = nextPreferences;
        writeCompanionPreferences(nextPreferences);
        setCompanionChatState((current) =>
          receiveCompanionReply(current, "好，我忘掉刚才那条。"),
        );
        return;
      }

      const extraction = extractCompanionPreference(text);
      if (extraction) {
        const nextPreferences = upsertCompanionPreference(
          companionPreferencesRef.current,
          extraction.preference,
        );
        companionPreferencesRef.current = nextPreferences;
        writeCompanionPreferences(nextPreferences);
        setCompanionChatState((current) =>
          receiveCompanionReply(current, extraction.feedback),
        );
        return;
      }

      void createLocalCompanionChatProvider(config)
        .send({
          text,
          preferences: companionPreferencesRef.current.preferences,
        })
        .then((reply) => {
          setCompanionChatState((current) =>
            current.mode === "active" && current.pendingRequestId === id
              ? receiveCompanionReply(current, reply.text)
              : current,
          );
        });
    }, 240);
  };

  const exitActiveCompanionChat = () => {
    setCompanionChatState((current) => exitCompanionChat(current));
    clearDefaultBubbleText();
  };

  const getBubbleTextForPet = (
    petId: string,
    event: PetDialogueEvent,
    fallbackText: string | null,
  ) =>
    resolvePetDialogue(
      getDialoguePackageForPet(petId),
      event,
      fallbackText,
    );

  const getResolvedInteractionsForPet = (
    petId: string,
  ): ResolvedPetInteractionManifest | null => {
    const manifest = petManifestsById[petId];
    return manifest ? resolvePetInteractionManifest(manifest) : null;
  };

  const clearTransientBubbleTimer = () => {
    if (transientBubbleTimer.current === null) return;
    window.clearTimeout(transientBubbleTimer.current);
    transientBubbleTimer.current = null;
  };

  const clearDefaultBubbleText = () => {
    clearTransientBubbleTimer();
    setBubbleText(null);
  };

  const showTransientBubbleText = (
    text: string,
    durationMs = PLATFORM_FEEDBACK_BUBBLE_MS,
  ) => {
    clearTransientBubbleTimer();
    setBubbleText(text);
    transientBubbleTimer.current = window.setTimeout(() => {
      transientBubbleTimer.current = null;
      setBubbleText((current) => expireBubbleText(current, text));
    }, durationMs);
  };

  useEffect(() => {
    if (companionChatState.mode !== "active") return undefined;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") exitActiveCompanionChat();
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [companionChatState.mode]);

  useEffect(() => {
    if (!isTaskMenuOpen) return undefined;
    const close = (event: PointerEvent) => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target?.closest(".pet-task-menu")) setIsTaskMenuOpen(false);
    };
    window.addEventListener("pointerdown", close);
    return () => window.removeEventListener("pointerdown", close);
  }, [isTaskMenuOpen]);

  useEffect(() => {
    if (companionChatState.mode !== "active") return undefined;

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest(".companion-chat,.pet-hit-area,.pet-canvas")) return;
      exitActiveCompanionChat();
    };

    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [companionChatState.mode]);

  useEffect(() => {
    if (companionChatState.mode !== "active") return undefined;

    const timer = window.setInterval(() => {
      setCompanionChatState((current) =>
        shouldAutoExitCompanionChat(current) ? exitCompanionChat(current) : current,
      );
    }, 1000);

    return () => window.clearInterval(timer);
  }, [companionChatState.mode]);

  const setActiveCareReminderPrompt = (
    prompt: ActiveCareReminderPrompt | null,
  ) => {
    careReminderPromptRef.current = prompt;
    setCareReminderPrompt(prompt);
  };

  const completeTimedCareReminder = (deliveredKey: string) => {
    const nextDeliveredKeys = markCareReminderDelivered(
      careReminderState.current.deliveredKeys,
      deliveredKey,
    );
    careReminderState.current = { ...careReminderState.current, deliveredKeys: nextDeliveredKeys };
    writeCareReminderState(careReminderState.current);
  };

  const reopenTimedCareReminder = (deliveredKey: string) => {
    const nextDeliveredKeys = unmarkCareReminderDelivered(
      careReminderState.current.deliveredKeys,
      deliveredKey,
    );
    careReminderState.current = { ...careReminderState.current, deliveredKeys: nextDeliveredKeys };
    writeCareReminderState(careReminderState.current);
  };

  const saveCareReminderSettings = (settings: CareReminderSettingsValue) => {
    careReminderState.current = { ...careReminderState.current, settings };
    writeCareReminderState(careReminderState.current);
    setCareReminderSettings(settings);
    const now = Date.now();
    nextWellnessTime.current = now + settings.wellness.intervalMinutes * 60 * 1000;
    recordInteraction("care_reminder_settings_updated");
  };

  const dismissCareReminderDisableNotice = () => {
    careReminderState.current = { ...careReminderState.current, systemPopupNoticeDismissed: true };
    writeCareReminderState(careReminderState.current);
    setCareReminderNoticeDismissed(true);
    commitMailboxState((state) => receiveLetter(state, CARE_REMINDER_LETTER_ID));
    recordInteraction("care_reminder_disable_notice_dismissed");
  };

  const clearCareReminderPrompt = () => {
    setActiveCareReminderPrompt(null);
    clearDefaultBubbleText();
    playIdleAnimation();
  };

  const confirmCareReminderPrompt = () => {
    const prompt = careReminderPromptRef.current;
    if (!prompt) return;

    recordInteraction(`${prompt.kind}_care_confirmed`);
    if (prompt.source === "timed") {
      completeTimedCareReminder(prompt.deliveredKey);
      timedCareSnoozedUntil.current = 0;
    }

    clearCareReminderPrompt();
  };

  const snoozeCareReminderPrompt = () => {
    const prompt = careReminderPromptRef.current;
    if (prompt?.source !== "timed") return;

    reopenTimedCareReminder(prompt.deliveredKey);
    timedCareSnoozedUntil.current = Date.now() + CARE_REMINDER_SNOOZE_MS;
    recordInteraction(`${prompt.kind}_care_snoozed`);
    clearCareReminderPrompt();
  };

  const clearHoverEatTimer = () => {
    if (hoverEatTimer.current !== null) {
      window.clearTimeout(hoverEatTimer.current);
      hoverEatTimer.current = null;
    }
    hoverStartedAt.current = null;
  };

  const restoreCursorEvents = () => {
    if (iconHugClickThroughTimer.current !== null) {
      window.clearTimeout(iconHugClickThroughTimer.current);
      iconHugClickThroughTimer.current = null;
    }

    const appWindow = getOptionalCurrentWindow();
    if (!appWindow) return;

    void appWindow
      .setIgnoreCursorEvents(false)
      .then(() => {
        recordInteraction("desktop_icon_click_through_off");
      })
      .catch(() => {
        recordInteraction("desktop_icon_click_through_restore_failed");
      });
  };

  const getActiveInteractionManifest = () =>
    interactionManifestRef.current ?? getResolvedInteractionsForPet(activePetId);

  const getAnimationSpec = (name: AnimationName): PetAnimationSpec | null => {
    const specs = animationSpecsRef.current;
    return specs?.[name] ?? null;
  };

  const getAnimationDirectionMode = (
    name: AnimationName,
  ): PetDirectionMode | "none" => {
    const resolved = getActiveInteractionManifest();
    if (!resolved) return "none";
    return name === resolved.drag.left || name === resolved.drag.right
      ? resolved.drag.directionMode
      : "none";
  };

  const markAnimationState = (name: AnimationName) => {
    const host = pixiHost.current;
    if (!host) return;
    host.dataset.currentAnimation = name;
    host.dataset.currentFacing = currentFacing.current;
  };

  const applySpriteVisual = (sprite: AnimatedSprite, name: AnimationName) => {
    const spec = getAnimationSpec(name);
    if (!spec) return;

    const transform = getPetAnimationTransform(
      spec,
      currentFacing.current,
      getAnimationDirectionMode(name),
    );
    sprite.scale.set(transform.scaleX, transform.scaleY);
  };

  const playAnimation = (name: AnimationName) => {
    const sprite = spriteRef.current;
    const animations = animationsRef.current;
    const spec = getAnimationSpec(name);
    if (!sprite || !animations || !spec || !animations[name]) return false;

    currentAnimation.current = name;
    markAnimationState(name);
    sprite.onComplete = undefined;
    sprite.textures = animations[name];
    sprite.animationSpeed = spec.speed;
    sprite.loop = spec.loop;
    applySpriteVisual(sprite, name);
    sprite.gotoAndPlay(0);
    return true;
  };

  const playIdleAnimation = () => {
    const resolved = getActiveInteractionManifest();
    const idleAnimation = resolved?.idle.animation ?? "idle";
    playAnimation(idleAnimation);
  };

  const scheduleReturnToIdle = (
    returnAfterMs: number | undefined,
    resumeHoverAfterReturn = true,
    expectedToken = playbackToken.current,
  ) => {
    if (returnToIdleTimer.current !== null) {
      window.clearTimeout(returnToIdleTimer.current);
      returnToIdleTimer.current = null;
    }

    if (!returnAfterMs || returnAfterMs <= 0) return;

    returnToIdleTimer.current = window.setTimeout(() => {
      if (expectedToken !== playbackToken.current) return;
      returnToIdleTimer.current = null;
      if (!careReminderPromptRef.current) {
        clearDefaultBubbleText();
      }
      playIdleAnimation();
      if (resumeHoverAfterReturn) {
        scheduleHoverEat();
      }
    }, returnAfterMs);
  };

  const setBubbleFromAction = (action: PetActionSpec) => {
    setBubbleText(
      action.dialogueEvent
        ? getBubbleTextForPet(
            activePetId,
            action.dialogueEvent,
            action.bubbleText ?? null,
          )
        : action.bubbleText ?? null,
    );
  };

  const playManifestAction = (
    action: PetActionSpec | PetSequenceSpec,
    resumeHoverAfterReturn = true,
    keepCareReminderPrompt = false,
  ) => {
    if (!keepCareReminderPrompt) {
      setActiveCareReminderPrompt(null);
    }

    if (returnToIdleTimer.current !== null) {
      window.clearTimeout(returnToIdleTimer.current);
      returnToIdleTimer.current = null;
    }

    const token = playbackToken.current + 1;
    playbackToken.current = token;
    const steps = resolveActionPlaybackSteps(action);
    let totalDurationMs = 0;

    for (const step of steps) {
      totalDurationMs = Math.max(
        totalDurationMs,
        step.startAfterMs + (step.durationMs ?? 0),
      );

      const playStep = () => {
        if (token !== playbackToken.current) return;
        setBubbleFromAction(step);
        playPetSound(step.sound);
        playAnimation(step.animation);
      };

      if (step.startAfterMs <= 0) {
        playStep();
      } else {
        window.setTimeout(playStep, step.startAfterMs);
      }
    }

    scheduleReturnToIdle(totalDurationMs, resumeHoverAfterReturn, token);
  };

  const playTaskFeedback = (
    scene: TaskFeedbackScene,
    fallbackText: string,
    fallbackAction: PetActionSpec | PetSequenceSpec,
  ) => {
    const feedback = resolveTaskFeedback(
      petTaskFeedbackById[activePetId],
      scene,
      fallbackText,
    );
    const configuredAnimation = feedback.action && animationsRef.current?.[feedback.action]
      ? feedback.action
      : feedback.fallbackAction && animationsRef.current?.[feedback.fallbackAction]
        ? feedback.fallbackAction
        : null;
    const action: PetActionSpec | PetSequenceSpec = configuredAnimation
      ? { animation: configuredAnimation, durationMs: feedback.durationMs, bubbleText: feedback.text }
      : "sequence" in fallbackAction
        ? {
            sequence: fallbackAction.sequence.map((step, index) => index === 0
              ? { ...step, dialogueEvent: undefined, bubbleText: feedback.text }
              : step),
          }
        : { ...fallbackAction, dialogueEvent: undefined, bubbleText: feedback.text };
    playManifestAction(action, false);
  };

  const handleClicks = () => {
    const currentCount = clickCount.current;
    clickCount.current = 0;
    clickTimer.current = null;

    const resolved = getActiveInteractionManifest();
    if (!resolved) return;

    if (currentCount === 1) {
      recordInteraction("click");
      playManifestAction(resolved.singleClick, false);
      return;
    }

    if (currentCount === 2) {
      recordInteraction("double_click");
      playManifestAction(resolved.doubleClick, false);
    }
  };

  const scheduleHoverEat = () => {
    const resolved = getActiveInteractionManifest();
    if (
      pointerState.current ||
      hoverEatTimer.current !== null ||
      resolved?.hover.enabled !== true
    ) {
      return;
    }

    const startedAt = Date.now();
    hoverStartedAt.current = startedAt;
    hoverEatTimer.current = window.setTimeout(() => {
      hoverEatTimer.current = null;

      if (
        shouldTriggerHoverEat({
          hoverStartedAt: startedAt,
          now: Date.now(),
          isDragging: Boolean(pointerState.current?.dragging),
        })
      ) {
        const latestResolved = getActiveInteractionManifest();
        if (latestResolved?.hover.enabled === true) {
          recordInteraction("hover_eat");
          playManifestAction(latestResolved.hover.action);
        }
      }
    }, HOVER_EAT_DELAY_MS);
  };

  const getDragFramePlan = (animationName: AnimationName) => {
    const resolved = getActiveInteractionManifest();
    const animations = animationsRef.current;
    if (!resolved || !animations) return null;

    const drag = resolved.drag;
    const frames = animations[animationName];
    if (!frames) return null;

    const hasPlan =
      drag.takeoffFrame !== undefined &&
      drag.loopStartFrame !== undefined &&
      drag.loopFrameCount !== undefined &&
      drag.landingApproachFrame !== undefined &&
      drag.landingFrame !== undefined;
    if (!hasPlan) return null;

    const takeoffFrame = frames[drag.takeoffFrame!];
    const loopFrames = frames.slice(
      drag.loopStartFrame!,
      drag.loopStartFrame! + drag.loopFrameCount!,
    );
    const landingFrames = [
      frames[drag.landingApproachFrame!],
      frames[drag.landingFrame!],
    ];

    if (
      !takeoffFrame ||
      loopFrames.length !== drag.loopFrameCount ||
      landingFrames.some((frame) => frame === undefined)
    ) {
      return null;
    }

    return {
      takeoffFrame,
      loopFrames,
      frames,
      landingFrames: landingFrames as Texture[],
      landingTransitionSpeed: drag.landingTransitionSpeed ?? 0.25,
      landingHoldMs: drag.landingHoldMs ?? 900,
    };
  };

  const playDragLoopAnimation = (
    animationName: AnimationName,
    includeTakeoff: boolean,
  ) => {
    const sprite = spriteRef.current;
    const plan = getDragFramePlan(animationName);
    const spec = getAnimationSpec(animationName);
    if (!sprite || !plan || !spec) {
      playAnimation(animationName);
      return;
    }

    currentAnimation.current = animationName;
    markAnimationState(animationName);
    sprite.onComplete = undefined;
    sprite.textures = includeTakeoff
      ? [plan.takeoffFrame, ...plan.loopFrames]
      : plan.loopFrames;
    sprite.animationSpeed = spec.speed;
    sprite.loop = !includeTakeoff;
    applySpriteVisual(sprite, animationName);
    sprite.onComplete = includeTakeoff
      ? () => {
          if (spriteRef.current !== sprite || !pointerState.current?.dragging) return;
          sprite.onComplete = undefined;
          sprite.textures = plan.loopFrames;
          sprite.animationSpeed = spec.speed;
          sprite.loop = true;
          sprite.gotoAndPlay(0);
        }
      : undefined;
    sprite.gotoAndPlay(0);
  };

  const playDragStartInteraction = () => {
    const resolved = getActiveInteractionManifest();
    if (!resolved) return;

    playbackToken.current += 1;

    if (returnToIdleTimer.current !== null) {
      window.clearTimeout(returnToIdleTimer.current);
      returnToIdleTimer.current = null;
    }

    setBubbleText(null);
    playPetSound("drag");
    const animationName = resolveDragAnimationName(
      resolved.drag,
      currentFacing.current,
    );
    playDragLoopAnimation(animationName, true);
  };

  const playDragEndInteraction = () => {
    const resolved = getActiveInteractionManifest();
    const sprite = spriteRef.current;
    if (!resolved || !sprite) {
      playbackToken.current += 1;
      playIdleAnimation();
      return;
    }

    const token = playbackToken.current + 1;
    playbackToken.current = token;
    const animationName = resolveDragAnimationName(
      resolved.drag,
      currentFacing.current,
    );
    const plan = getDragFramePlan(animationName);
    playPetSound("drag_end");

    if (!plan) {
      playAnimation(animationName);
      scheduleReturnToIdle(resolved.drag.landingHoldMs ?? 900, true, token);
      return;
    }

    if (returnToIdleTimer.current !== null) {
      window.clearTimeout(returnToIdleTimer.current);
      returnToIdleTimer.current = null;
    }

    currentAnimation.current = animationName;
    markAnimationState(animationName);
    sprite.onComplete = undefined;
    sprite.textures = [sprite.texture, ...plan.landingFrames];
    sprite.animationSpeed = plan.landingTransitionSpeed;
    sprite.loop = false;
    applySpriteVisual(sprite, animationName);
    sprite.onComplete = () => {
      if (
        spriteRef.current !== sprite ||
        currentAnimation.current !== animationName ||
        token !== playbackToken.current
      ) {
        return;
      }
      sprite.onComplete = undefined;
      scheduleReturnToIdle(plan.landingHoldMs, true, token);
    };
    sprite.gotoAndPlay(0);
  };

  const markPointerEvent = () => {
    lastPointerEventAt.current = Date.now();
  };

  const shouldUseMouseFallback = () => {
    return Date.now() - lastPointerEventAt.current > 700;
  };
  const startPress = (
    source: PressSource,
    button: number,
    pointerId: number,
    clientX: number,
    clientY: number,
    screenX: number,
    screenY: number,
  ) => {
    if (button !== 0 || pointerState.current) return false;
    if (companionChatStateRef.current.mode === "active") {
      stopCompanionChatReply();
      return false;
    }

    recordInteraction(source === "pointer" ? "pointer_down" : "mouse_down");
    clearHoverEatTimer();
    restoreCursorEvents();
    pointerState.current = {
      source,
      dragging: false,
      pointerId,
      x: clientX,
      y: clientY,
      screenX,
      screenY,
      currentX: clientX,
      currentY: clientY,
      currentScreenX: screenX,
      currentScreenY: screenY,
    };

    const appWindow = getOptionalCurrentWindow();
    if (!appWindow) return true;

    void Promise.all([appWindow.outerPosition(), appWindow.scaleFactor()])
      .then(([position, scaleFactor]) => {
        const pointer = pointerState.current;
        if (!pointer || pointer.pointerId !== pointerId) return;

        pointer.windowX = position.x;
        pointer.windowY = position.y;
        pointer.scaleFactor = scaleFactor;
        if (pointer.dragging) {
          movePress(
            pointer.currentX,
            pointer.currentY,
            pointer.currentScreenX,
            pointer.currentScreenY,
          );
        }
      })
      .catch((err) => {
        const errMsg = err instanceof Error ? err.message : String(err);
        console.error("Window metrics failed:", err);
        recordInteraction(`window_metrics_failed: ${errMsg}`);
        setBubbleText(`坐标获取失败喵：${errMsg}`);
        pointerState.current = null;
      });

    return true;
  };

  const movePress = (clientX: number, clientY: number, screenX: number, screenY: number) => {
    const pointer = pointerState.current;
    if (!pointer) {
      scheduleHoverEat();
      return;
    }

    pointer.currentX = clientX;
    pointer.currentY = clientY;
    pointer.currentScreenX = screenX;
    pointer.currentScreenY = screenY;

    if (
      !pointer.dragging &&
      shouldStartDrag({
        startX: pointer.x,
        startY: pointer.y,
        x: clientX,
        y: clientY,
      })
    ) {
      pointer.dragging = true;
      clearHoverEatTimer();
      const dragDirection = updateDragDirection(
        createDragDirectionState(currentFacing.current, pointer.screenX),
        screenX,
        pointer.scaleFactor ?? 1,
      );
      pointer.dragDirection = dragDirection;
      currentFacing.current = dragDirection.facing;
      recordInteraction("drag_start");
      playDragStartInteraction();
    }

    if (pointer.dragging) {
      const nextDirection = updateDragDirection(
        pointer.dragDirection ??
          createDragDirectionState(currentFacing.current, pointer.screenX),
        screenX,
        pointer.scaleFactor ?? 1,
      );
      const facingChanged = nextDirection.facing !== currentFacing.current;
      pointer.dragDirection = nextDirection;
      currentFacing.current = nextDirection.facing;

      if (facingChanged) {
        const resolved = getActiveInteractionManifest();
        if (resolved) {
          playDragLoopAnimation(
            resolveDragAnimationName(resolved.drag, nextDirection.facing),
            false,
          );
        }
      }
    }

    if (
      !pointer.dragging ||
      pointer.windowX === undefined ||
      pointer.windowY === undefined ||
      pointer.scaleFactor === undefined
    ) {
      return;
    }

    const position = getDraggedWindowPosition({
      startPointerX: pointer.screenX,
      startPointerY: pointer.screenY,
      pointerX: screenX,
      pointerY: screenY,
      startWindowX: pointer.windowX,
      startWindowY: pointer.windowY,
      scaleFactor: pointer.scaleFactor,
    });

    const appWindow = getOptionalCurrentWindow();
    if (!appWindow) return;

    void appWindow
      .setPosition(new PhysicalPosition(position.x, position.y))
      .catch((err) => {
        const errMsg = err instanceof Error ? err.message : String(err);
        console.error("Set position failed:", err);
        recordInteraction(`set_position_failed: ${errMsg}`);
        setBubbleText(`移动窗口失败喵：${errMsg}`);
      });
  };

  const finishPress = (source: PressSource) => {
    const pointer = pointerState.current;
    if (!pointer || pointer.source !== source) return;

    pointerState.current = null;

    if (!pointer.dragging) {
      clickCount.current += 1;
      if (clickTimer.current !== null) {
        window.clearTimeout(clickTimer.current);
      }
      clickTimer.current = window.setTimeout(handleClicks, 250);
      return;
    }

    recordInteraction("drag_end");
    playDragEndInteraction();
    window.setTimeout(probeDesktopIconInteraction, 250);
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLElement>) => {
    markPointerEvent();
    if (event.button === 2) {
      event.preventDefault();
      return;
    }
    if (
      startPress(
        "pointer",
        event.button,
        event.pointerId,
        event.clientX,
        event.clientY,
        event.screenX,
        event.screenY,
      )
    ) {
      event.preventDefault();
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLElement>) => {
    markPointerEvent();
    if (
      pointerState.current?.source === "pointer" &&
      !isPrimaryButtonPressed(event.buttons)
    ) {
      return;
    }
    movePress(event.clientX, event.clientY, event.screenX, event.screenY);
  };

  const handlePointerUp = (event: ReactPointerEvent<HTMLElement>) => {
    markPointerEvent();
    const pointer = pointerState.current;
    if (pointer?.source === "pointer" && event.currentTarget.hasPointerCapture(pointer.pointerId)) {
      event.currentTarget.releasePointerCapture(pointer.pointerId);
    }
    finishPress("pointer");
  };

  const handleMouseDown = (event: ReactMouseEvent<HTMLElement>) => {
    if (event.button === 2) {
      event.preventDefault();
      return;
    }

    if (!shouldUseMouseFallback()) return;

    if (
      startPress(
        "mouse",
        event.button,
        -1,
        event.clientX,
        event.clientY,
        event.screenX,
        event.screenY,
      )
    ) {
      event.preventDefault();
    }
  };

  const handleMouseMove = (event: ReactMouseEvent<HTMLElement>) => {
    if (!shouldUseMouseFallback() && pointerState.current?.source === "pointer") return;
    if (
      pointerState.current?.source === "mouse" &&
      !isPrimaryButtonPressed(event.buttons)
    ) {
      return;
    }
    movePress(event.clientX, event.clientY, event.screenX, event.screenY);
  };

  const handleMouseUp = () => {
    if (!shouldUseMouseFallback() && pointerState.current?.source !== "mouse") return;
    finishPress("mouse");
  };

  const handleContextMenu = (event: ReactMouseEvent<HTMLElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsTaskMenuOpen(true);
    recordInteraction("task_context_menu_open");
  };

  const handlePointerEnter = () => {
    markPointerEvent();
    scheduleHoverEat();
  };

  const handlePointerLeave = () => {
    markPointerEvent();
    clearHoverEatTimer();
  };

  const handleMouseEnter = () => {
    scheduleHoverEat();
  };

  const handleMouseLeave = () => {
    clearHoverEatTimer();
  };

  const handlePointerInterruption = (event: ReactPointerEvent<HTMLElement>) => {
    markPointerEvent();
    if (!isPointerCancellation(event.type)) return;

    pointerState.current = null;
    recordInteraction("pointer_cancel");
    clearHoverEatTimer();
    clearDefaultBubbleText();
    playIdleAnimation();
  };

  const scheduleNextRandomCareReminder = (nowTimestamp: number) => {
    const setting = careReminderState.current.settings.wellness;
    nextWellnessTime.current = nowTimestamp + setting.intervalMinutes * 60 * 1000;
  };

  const postponeOverdueRandomCareReminders = (nowTimestamp: number) => {
    if (nowTimestamp >= nextWellnessTime.current) {
      scheduleNextRandomCareReminder(nowTimestamp);
    }
  };

  const playCareReminder = (
    kind: CareReminderKind,
    deliveredKey?: string,
  ) => {
    void revealHiddenPetForCareReminder(getOptionalCurrentWindow()).catch(() => {
      recordInteraction("care_reminder_window_show_failed");
    });
    void showSystemCareNotification(kind);
    const resolved = getActiveInteractionManifest();
    if (!resolved) {
      if (deliveredKey) completeTimedCareReminder(deliveredKey);
      return false;
    }

    recordInteraction(`${kind}_care_reminder`);
    const reminderAction = resolved.reminders[kind === "wellness" ? "eyeCare" : kind];
    playManifestAction(reminderAction, false, true);

    if (deliveredKey) {
      completeTimedCareReminder(deliveredKey);
    }

    return true;
  };

  useEffect(() => {
    const scan = () => {
      const stored = readTaskDatabase();
      const timezoneAdjusted = reconcileTaskTimezone(stored);
      const aged = markUnattendedReminders(timezoneAdjusted, new Date(), timezoneAdjusted.settings.bubbleDurationMinutes * 60 * 1000);
      const result = triggerDueReminders(aged);
      if (result.triggered.length === 0) {
        if (aged !== stored) {
          writeTaskDatabase(aged);
          setTaskDatabase(aged);
        }
        return;
      }
      writeTaskDatabase(result.database);
      setTaskDatabase(result.database);

      const shouldSummarize = result.triggered.length > 1
        && result.triggered.every(({ instance }) => instance.status === "missed");
      if (shouldSummarize) {
        void showSystemTaskSummaryNotification(result.triggered.length);
      } else {
        for (const due of result.triggered) void showSystemTaskNotification(due);
      }
      playTaskNotificationSound();
      if (!isPlatformOpen && !isQuickCreateOpen) {
        const resolved = getActiveInteractionManifest();
        if (resolved) {
          const multiple = result.triggered.length > 1;
          playTaskFeedback(
            multiple ? "taskBurst" : "taskDue",
            multiple
              ? `你有 ${result.triggered.length} 条提醒，我们一件一件来。`
              : `该做「${result.triggered[0]?.task.title ?? "这件事"}」啦。`,
            resolved.reminders.eyeCare,
          );
        }
      }
      recordInteraction("task_reminder_triggered");
    };

    scan();
    const timer = window.setInterval(scan, 15_000);
    const rescan = () => scan();
    window.addEventListener("focus", rescan);
    window.addEventListener("task-scheduler-wakeup", rescan);
    document.addEventListener("visibilitychange", rescan);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", rescan);
      window.removeEventListener("task-scheduler-wakeup", rescan);
      document.removeEventListener("visibilitychange", rescan);
    };
  }, [activePetId, isPlatformOpen, isQuickCreateOpen, petTaskFeedbackById, taskDatabase.settings.notificationSound, taskDatabase.settings.customNotificationSoundDataUrl]);

  const playDesktopIconAction = (
    action: PetActionSpec,
    bubbleText: string,
    resumeHoverAfterReturn = false,
  ) => {
    const token = playbackToken.current + 1;
    playbackToken.current = token;
    setBubbleText(bubbleText);
    playPetSound(action.sound);
    playAnimation(action.animation);
    scheduleReturnToIdle(action.durationMs, resumeHoverAfterReturn, token);
  };

  const probeDesktopIconInteraction = () => {
    if (windowMode.current !== "pet") return;
    const resolved = getActiveInteractionManifest();
    if (!resolved) return;

    const nowTimestamp = Date.now();
    const activePrompt = careReminderPromptRef.current;
    if (activePrompt) {
      if (
        activePrompt.source === "random" &&
        nowTimestamp >= activePrompt.expiresAt
      ) {
        clearCareReminderPrompt();
      } else if (
        activePrompt.source === "timed" &&
        selectTimedCareReminder(new Date(nowTimestamp), [], careReminderState.current.settings)?.key !==
          activePrompt.deliveredKey
      ) {
        timedCareSnoozedUntil.current = 0;
        clearCareReminderPrompt();
      }
      return;
    }

    if (pointerState.current) {
      nextWellnessTime.current = Math.max(nextWellnessTime.current, nowTimestamp + 30000);
    } else if (returnToIdleTimer.current === null) {
      const dueReminder = selectDueCareReminder({
        now: nowTimestamp,
        deliveredKeys: careReminderState.current.deliveredKeys,
        nextWellnessTime: nextWellnessTime.current,
        timedSnoozedUntil: timedCareSnoozedUntil.current,
        settings: careReminderState.current.settings,
      });

      if (dueReminder?.source === "random") {
        scheduleNextRandomCareReminder(nowTimestamp);
      }

      if (
        dueReminder &&
        playCareReminder(
          dueReminder.kind,
          dueReminder.source === "timed" ? dueReminder.deliveredKey : undefined,
        )
      ) {
        if (dueReminder.source === "timed") {
          setActiveCareReminderPrompt({
            source: "timed",
            kind: dueReminder.kind,
            deliveredKey: dueReminder.deliveredKey,
          });
        } else if (dueReminder.source === "random") {
          setActiveCareReminderPrompt({
            source: "random",
            kind: dueReminder.kind,
            expiresAt: nowTimestamp + RANDOM_REMINDER_PROMPT_MS,
          });
        }

        if (dueReminder.source === "timed") {
          postponeOverdueRandomCareReminders(nowTimestamp);
        }
        return;
      }

    }

    if (
      desktopIconProbeInFlight.current ||
      pointerState.current?.dragging ||
      returnToIdleTimer.current !== null
    ) {
      return;
    }
    if (
      resolved.desktopIcon.enabled &&
      currentAnimation.current === resolved.desktopIcon.action.animation
    ) {
      return;
    }

    if (pointerState.current || Date.now() < iconHugLockedUntil.current) {
      nextIdleQuirkTime.current = Math.max(nextIdleQuirkTime.current, nowTimestamp + 20000);
    } else if (nowTimestamp >= nextIdleQuirkTime.current) {
      const quirks = resolved.idleQuirks;
      if (quirks.length > 0 && Math.random() < 0.15) {
        const chosen = quirks[Math.floor(Math.random() * quirks.length)];
        if (chosen) {
          recordInteraction("idle_quirk_triggered");
          playManifestAction(chosen, false);
          nextIdleQuirkTime.current = nowTimestamp + randomInRange(25, 45) * 1000;
          return;
        }
      }
      nextIdleQuirkTime.current = quirks.length > 0
        ? nowTimestamp + 5000
        : nowTimestamp + randomInRange(25, 45) * 1000;
    }

    if (Date.now() < iconHugLockedUntil.current) return;
    if (resolved.desktopIcon.enabled !== true) return;

    const desktopIcon = resolved.desktopIcon;
    desktopIconProbeInFlight.current = true;
    const appWindow = getOptionalCurrentWindow();
    if (!appWindow) {
      desktopIconProbeInFlight.current = false;
      return;
    }

    void Promise.all([
      invoke<boolean>("is_point_on_desktop", { x: 82, y: 172 }),
      invoke<DesktopIconBounds[]>("get_desktop_icons"),
      appWindow.outerPosition(),
      appWindow.outerSize(),
      appWindow.scaleFactor(),
    ])
      .then(([isOnDesktop, icons, position, size, scaleFactor]) => {
        if (!isOnDesktop) return;

        const target = findDesktopIconTarget(
          {
            x: position.x,
            y: position.y,
            width: size.width,
            height: size.height,
          },
          icons,
          undefined,
          desktopIcon.allowedSide === "right" ? { side: "right" } : {},
        );
        const result = updateDesktopIconInteraction({
          now: Date.now(),
          state: desktopIconState.current,
          target,
        });
        const previousIconKey = desktopIconState.current.activeIconKey;

        desktopIconState.current = result.nextState;

        if (!desktopIconProbeSucceeded.current) {
          desktopIconProbeSucceeded.current = true;
          recordInteraction("desktop_icon_probe_ok");
        }

        if (result.target && previousIconKey !== result.target.key) {
          recordInteraction("desktop_icon_near");
        }

        if (!result.shouldInteract || !result.target) return;
        if (returnToIdleTimer.current !== null) return;

        const iconTarget = result.target;
        clearHoverEatTimer();
        recordInteraction("desktop_icon_interact");

        if (desktopIcon.positioning === "peek") {
          const durationMs = desktopIcon.action.durationMs ?? 1800;
          iconHugLockedUntil.current = Date.now() + durationMs + 1000;
          const bumpPosition = getDesktopIconBumpWindowPosition(
            iconTarget,
            size,
            scaleFactor,
          );

          void appWindow
            .setPosition(new PhysicalPosition(bumpPosition.x, bumpPosition.y))
            .then(() => {
              recordInteraction("desktop_icon_peek");
              playDesktopIconAction(
                desktopIcon.action,
                formatDesktopIconBubbleText(iconTarget.title),
              );
            })
            .catch(() => {
              recordInteraction("desktop_icon_peek_failed");
            });
          return;
        }

        const durationMs = desktopIcon.action.durationMs ?? 5600;
        iconHugLockedUntil.current = Date.now() + durationMs + 1000;
        setBubbleText(formatDesktopIconBubbleText(iconTarget.title));
        const wrapPosition = getDesktopIconWrapWindowPosition(iconTarget, size, scaleFactor);
        void appWindow
          .setPosition(new PhysicalPosition(wrapPosition.x, wrapPosition.y))
          .then(() => appWindow.setIgnoreCursorEvents(true))
          .then(() => {
            recordInteraction("desktop_icon_wrap");
            recordInteraction("desktop_icon_click_through_on");
            playDesktopIconAction(
              desktopIcon.action,
              formatDesktopIconWrapBubbleText(iconTarget.title),
            );
            if (iconHugClickThroughTimer.current !== null) {
              window.clearTimeout(iconHugClickThroughTimer.current);
            }
            iconHugClickThroughTimer.current = window.setTimeout(() => {
              restoreCursorEvents();
            }, durationMs);
          })
          .catch(() => {
            recordInteraction("desktop_icon_wrap_failed");
          });
      })
      .catch(() => {
        if (desktopIconProbeFailed.current) return;
        desktopIconProbeFailed.current = true;
        recordInteraction("desktop_icon_probe_failed");
      })
      .finally(() => {
        desktopIconProbeInFlight.current = false;
      });
  };

  useEffect(() => {
    const host = pixiHost.current;
    if (!host) return;

    let disposed = false;
    let initialized = false;
    let destroyed = false;
    const app = new Application();

    const destroyApp = () => {
      if (!initialized || destroyed) return;
      destroyed = true;
      app.destroy({ removeView: true }, { children: true });
    };

    void app
      .init({
        backgroundAlpha: 0,
        antialias: true,
        autoDensity: true,
        resizeTo: host,
        resolution: Math.min(window.devicePixelRatio || 1, 2),
      })
      .then(async () => {
        initialized = true;

        if (disposed) {
          destroyApp();
          return;
        }

        host.appendChild(app.canvas);

        const petId = activePetId;
        const manifest = await loadPetManifest(petId);
        const resolvedInteractions = resolvePetInteractionManifest(manifest);
        const textureCache = new Map<string, Texture>();
        const loadTexture = async (path: string) => {
          const cached = textureCache.get(path);
          if (cached) return cached;

          const texture = await Assets.load<Texture>(
            resolvePetAssetUrl(petId, path),
          );
          textureCache.set(path, texture);
          return texture;
        };

        const animationEntries = await Promise.all(
          Object.entries(resolvedInteractions.animations).map(
            async ([animationName, spec]) => {
              const texture = await loadTexture(
                spec.spritesheetPath ?? manifest.spritesheetPath,
              );
              const frames = buildAnimationFrameRects(
                spec,
                CELL_WIDTH,
                CELL_HEIGHT,
              ).map(
                (frame) =>
                  new Texture({
                    source: texture.source,
                    frame: new Rectangle(
                      frame.x,
                      frame.y,
                      frame.width,
                      frame.height,
                    ),
                  }),
              );

              if (spec.finishFramePath) {
                frames.push(await loadTexture(spec.finishFramePath));
              }

              return [animationName, frames] as const;
            },
          ),
        );

        if (disposed) {
          destroyApp();
          return;
        }

        const animations = Object.fromEntries(animationEntries) as Record<
          AnimationName,
          Texture[]
        >;
        const idleAnimationName = resolvedInteractions.idle.animation;
        const idleAnimation = getInteractionAnimationSpec(
          resolvedInteractions,
          idleAnimationName,
        );
        const sprite = new AnimatedSprite({
          textures: animations[idleAnimationName],
          animationSpeed: idleAnimation.speed,
          autoPlay: true,
          loop: idleAnimation.loop,
        });

        animationsRef.current = animations;
        animationSpecsRef.current = resolvedInteractions.animations;
        interactionManifestRef.current = resolvedInteractions;
        currentAnimation.current = idleAnimationName;
        currentFacing.current = "right";
        markAnimationState(idleAnimationName);
        desktopIconState.current = {
          activeIconKey: null,
          firstSeenAt: null,
          lastTriggeredAt: null,
        };
        spriteRef.current = sprite;
        sprite.anchor.set(0.5, 1);
        applySpriteVisual(sprite, idleAnimationName);
        sprite.x = app.screen.width / 2;
        sprite.y = app.screen.height - 6;
        app.stage.addChild(sprite);

        host.dataset.petLoaded = "true";
        host.dataset.petId = manifest.id;
        host.dataset.spriteSource = manifest.spritesheetPath;
        host.dataset.animationCount = String(animationEntries.length);
        host.dataset.desktopIconEnabled = String(resolvedInteractions.desktopIcon.enabled);
        recordInteraction("app_ready");
        desktopIconProbeTimer.current = window.setInterval(
          probeDesktopIconInteraction,
          1200,
        );

        app.ticker.add(() => {
          const spec = getAnimationSpec(currentAnimation.current);
          const transform = spec
            ? getPetAnimationTransform(
                spec,
                currentFacing.current,
                getAnimationDirectionMode(currentAnimation.current),
              )
            : { offsetX: 0, offsetY: 0 };
          sprite.x = app.screen.width / 2 + transform.offsetX;
          sprite.y = app.screen.height - 6 + transform.offsetY;
        });
      })
      .catch(() => {
        recordInteraction("app_init_failed");
      });

    return () => {
      disposed = true;
      if (returnToIdleTimer.current !== null) {
        window.clearTimeout(returnToIdleTimer.current);
        returnToIdleTimer.current = null;
      }
      clearTransientBubbleTimer();
      clearHoverEatTimer();
      restoreCursorEvents();
      if (desktopIconProbeTimer.current !== null) {
        window.clearInterval(desktopIconProbeTimer.current);
        desktopIconProbeTimer.current = null;
      }
      spriteRef.current = null;
      animationsRef.current = null;
      animationSpecsRef.current = null;
      interactionManifestRef.current = null;
      destroyApp();
    };
  }, [activePetId]);

  return (
    <main
      className={`pet-shell${isPlatformOpen ? " platform-open" : ""}${isQuickCreateOpen ? " quick-create-open" : ""}${!isPlatformOpen && !isQuickCreateOpen && isReminderWindowExpanded ? " reminder-open" : ""}`}
      style={
        {
          "--pet-bubble-bottom": `${PET_BUBBLE_BOTTOM_PX}px`,
          "--platform-pet-inset": `${PLATFORM_PET_INSET_PX}px`,
        } as CSSProperties
      }
      onContextMenu={isPlatformOpen || isQuickCreateOpen ? undefined : handleContextMenu}
      onMouseDown={isPlatformOpen || isQuickCreateOpen ? undefined : handleMouseDown}
      onMouseEnter={isPlatformOpen || isQuickCreateOpen ? undefined : handleMouseEnter}
      onMouseLeave={isPlatformOpen || isQuickCreateOpen ? undefined : handleMouseLeave}
      onMouseMove={isPlatformOpen || isQuickCreateOpen ? undefined : handleMouseMove}
      onMouseUp={isPlatformOpen || isQuickCreateOpen ? undefined : handleMouseUp}
      onPointerDown={isPlatformOpen || isQuickCreateOpen ? undefined : handlePointerDown}
      onPointerEnter={isPlatformOpen || isQuickCreateOpen ? undefined : handlePointerEnter}
      onPointerLeave={isPlatformOpen || isQuickCreateOpen ? undefined : handlePointerLeave}
      onPointerMove={isPlatformOpen || isQuickCreateOpen ? undefined : handlePointerMove}
      onPointerCancel={isPlatformOpen || isQuickCreateOpen ? undefined : handlePointerInterruption}
      onLostPointerCapture={
        isPlatformOpen || isQuickCreateOpen ? undefined : handlePointerInterruption
      }
      onPointerUp={isPlatformOpen || isQuickCreateOpen ? undefined : handlePointerUp}
    >
      <div className="pet-hit-area" aria-hidden="true" />
      <div ref={pixiHost} className="pet-canvas" />
      {companionChatState.mode === "active" && (
        <CompanionChatBubble
          draft={companionChatState.draft}
          isWaiting={companionChatState.pendingRequestId !== null}
          messages={companionChatState.messages}
          onDraftChange={updateCompanionDraftText}
          onSend={sendCompanionChatMessage}
          onStop={stopCompanionChatReply}
        />
      )}
      {companionChatState.mode !== "active" && bubbleText && (
        <div
          className={`bubble${careReminderPrompt ? " has-actions" : ""}`}
          onClick={careReminderPrompt ? stopPlatformEvent : undefined}
          onMouseDown={careReminderPrompt ? stopPlatformEvent : undefined}
          onMouseUp={careReminderPrompt ? stopPlatformEvent : undefined}
          onPointerDown={careReminderPrompt ? stopPlatformEvent : undefined}
          onPointerUp={careReminderPrompt ? stopPlatformEvent : undefined}
        >
          <span className="bubble-text">{bubbleText}</span>
          {careReminderPrompt && (
            <div className="bubble-actions">
              <button
                className="bubble-action"
                type="button"
                onClick={confirmCareReminderPrompt}
              >
                收到啦
              </button>
              {careReminderPrompt.source === "timed" && (
                <button
                  className="bubble-action"
                  type="button"
                  onClick={snoozeCareReminderPrompt}
                >
                  10分钟后提醒
                </button>
              )}
            </div>
          )}
        </div>
      )}
      {!isPlatformOpen && !isQuickCreateOpen && companionChatState.mode !== "active" && (
        <TaskReminderStack
          reminders={visibleTaskReminders}
          onComplete={completeTaskReminder}
          onOpen={(taskId) => openTaskPlatform("today", taskId)}
          onOpenAll={() => {
            openTaskPlatform("today");
            const summaryId = missedSummaryNotificationId.current;
            if (summaryId) void invoke("clear_task_notification", { instanceId: summaryId }).catch(() => {});
            missedSummaryNotificationId.current = null;
          }}
          onCloseSummary={(instanceIds) => {
            setHiddenTaskReminderIds((current) => new Set([...current, ...instanceIds]));
            commitTaskDatabase(closeMissedReminderSummary(readTaskDatabase()));
            const summaryId = missedSummaryNotificationId.current;
            if (summaryId) void invoke("clear_task_notification", { instanceId: summaryId }).catch(() => {});
            missedSummaryNotificationId.current = null;
            recordInteraction("task_missed_summary_closed");
          }}
          onSnooze={snoozeTaskReminder}
        />
      )}
      {!isPlatformOpen && !isQuickCreateOpen && isTaskMenuOpen && (
        <TaskContextMenu
          onClose={() => setIsTaskMenuOpen(false)}
          onOpenPlatform={() => openTaskPlatform("all")}
          onOpenReminders={() => openTaskPlatform("upcoming")}
          onOpenToday={() => openTaskPlatform("today")}
          onOpenSettings={openPetPlatform}
          onQuickCreate={openQuickTaskCreate}
        />
      )}
      {isQuickCreateOpen && (
        <section className="quick-task-overlay" onPointerDown={stopPlatformEvent}>
          <div className="quick-task-panel">
            <header><div><small>快速记录</small><h2>新建待办</h2></div><button type="button" aria-label="关闭" onClick={() => setIsQuickCreateOpen(false)}>×</button></header>
            <QuickCreateTask compact onCancel={() => setIsQuickCreateOpen(false)} onCreate={createQuickTask} />
          </div>
        </section>
      )}
      {isPlatformOpen && (
        <section
          className="platform-panel"
          aria-label="桌宠平台"
          onMouseDown={stopPlatformEvent}
          onPointerDown={stopPlatformEvent}
        >
          <header className="platform-header" onPointerDown={startPlatformWindowDrag}>
            <div>
              <p className="platform-kicker">Desktop Pet Platform</p>
              <h1>{APP_DISPLAY_NAME}</h1>
            </div>
            <div className="platform-header-actions">
              <div className="platform-section-switch" onPointerDown={stopPlatformEvent}>
                <button className={platformSection === "tasks" ? "is-active" : ""} type="button" onClick={() => setPlatformSection("tasks")}>待办</button>
                <button className={platformSection === "pets" ? "is-active" : ""} type="button" onClick={() => setPlatformSection("pets")}>桌宠</button>
              </div>
              <button
                className={`platform-mailbox-button${
                  isMailboxReceiving ? " is-receiving" : ""
                }`}
                ref={mailboxButtonRef}
                type="button"
                aria-label="打开信箱"
                onClick={openMailbox}
                onPointerDown={stopPlatformEvent}
              >
                <span aria-hidden="true">✉</span>
                {visibleUnreadCount > 0 && (
                  <span className="platform-mailbox-badge">
                    {visibleUnreadCount}
                  </span>
                )}
              </button>
              <button
                className="platform-close"
                type="button"
                aria-label="关闭桌宠平台"
                onClick={closePlatform}
                onPointerDown={stopPlatformEvent}
              >
                ×
              </button>
            </div>
          </header>

          {platformSection === "tasks" ? (
            <TaskWorkspace
              database={taskDatabase}
              initialView={taskListView}
              initialSelectedTaskId={taskDetailId}
              onChange={commitTaskDatabase}
              careReminderSettings={careReminderSettings}
              onCareReminderSettingsChange={saveCareReminderSettings}
              careReminderNoticeDismissed={careReminderNoticeDismissed}
              onDismissCareReminderNotice={dismissCareReminderDisableNotice}
              reviewSpeakerName={activePet?.displayName ?? activePetId}
              reviewSpeakerTexts={dailyReviewSpeakerTexts}
              onPreviewPetNotificationSound={() => playPetSound("taskDue")}
            />
          ) : (
            <>
              <div className="platform-status">
                <span>当前显示</span>
                <strong>{activePet?.displayName ?? activePetId}</strong>
                <span>{petCatalog.length} 个桌宠包</span>
              </div>

              <div className="pet-grid">
                {petCatalog.map((pet) => (
                  <article
                    className={`pet-card${pet.isActive ? " is-active" : ""}`}
                    key={pet.id}
                  >
                    <div
                      className={`pet-card-preview is-${pet.previewKind}`}
                      aria-hidden="true"
                      style={{ backgroundImage: `url(${pet.previewUrl})` }}
                    />
                    <div className="pet-card-body">
                      <div className="pet-card-title-row">
                        <h2>{pet.displayName}</h2>
                        <span>{pet.id}</span>
                      </div>
                      <p>{pet.description}</p>
                      <button
                        className="pet-card-action"
                        type="button"
                        disabled={pet.isActive}
                        onClick={() => selectPet(pet)}
                      >
                        {pet.isActive ? "使用中" : "启用"}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </>
          )}

          {isMailboxOpen && (
            <MailboxPanel
              letters={BUILT_IN_LETTERS}
              state={mailboxState}
              onClose={() => setIsMailboxOpen(false)}
              onDeleteRead={deleteMailboxRead}
              onMarkAllRead={markMailboxRead}
              onOpenLetter={openMailboxLetter}
            />
          )}

          {activeLetter && (
            <LetterReader
              key={`${activeLetter.id}-${letterOpenMode}`}
              letter={activeLetter}
              mailboxTargetRef={mailboxButtonRef}
              mode={letterOpenMode}
              onRead={markMailboxLetterRead}
              onStored={finishStoringLetter}
            />
          )}
        </section>
      )}
      {pendingUpdate && (
        <UpdateDialog
          currentVersion={pendingUpdate.currentVersion}
          latestVersion={pendingUpdate.latestVersion}
          onCancel={cancelPendingUpdate}
          onConfirm={confirmPendingUpdate}
        />
      )}
    </main>
  );
}

function App() {
  const pathname =
    typeof window === "undefined" ? "/" : window.location.pathname;

  if (isMarketingRoute(pathname)) {
    return <MarketingPage />;
  }

  return <DesktopPetApp />;
}

export default App;
