import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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
import { emit, listen } from "@tauri-apps/api/event";
import { getAllWebviewWindows } from "@tauri-apps/api/webviewWindow";
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
import { isAccountRoute, isMarketingRoute } from "./marketing/marketingContent";
import { AccountGate } from "./account/AccountGate";
import type {
  DesktopIconBounds,
  DesktopIconInteractionState,
} from "./pet-core/interaction";
import {
  HOVER_EAT_DELAY_MS,
  SECONDARY_DOUBLE_CLICK_MS,
  findDesktopIconTarget,
  getDesktopIconBumpWindowPosition,
  formatDesktopIconBubbleText,
  formatDesktopIconWrapBubbleText,
  getDesktopIconWrapWindowPosition,
  getDraggedWindowPosition,
  isPrimaryButtonPressed,
  isPointerCancellation,
  registerSecondaryClick,
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
  resolveDragLandingIdleStartFrame,
  resolveDragLoopFrameIndex,
  shouldReturnToIdleImmediatelyAfterDragLanding,
  updateDragDirection,
  type DragDirectionState,
} from "./pet-core/dragDirection";
import {
  getPetCanvasPosition,
  getPetAnimationTransform,
  PET_BUBBLE_BOTTOM_PX,
} from "./pet-core/visual";
import {
  clampWindowPositionToWorkArea,
  getPhysicalPetAnchor,
  getInitialPetWindowPosition,
  getWindowPositionForPhysicalPetAnchor,
  PLATFORM_START_OPEN,
  PLATFORM_START_SECTION,
  resolvePlatformSectionAfterCompanionExit,
  resolveRenderedPlatformSection,
  type CompanionExitReason,
  type PlatformSection,
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
  type BundledOllamaPullProgress,
} from "./pet-core/CompanionOllamaPullProgress";
import { PlatformCompanionChatPage } from "./pet-core/PlatformCompanionChatPage";
import { PlatformProviderSettingsPage } from "./pet-core/PlatformProviderSettingsPage";
import { revealDedicatedPlatformWindow as revealPlatformWindow } from "./pet-core/dedicatedPlatformWindow";
import {
  loadPetCompanionChatPackage,
  resolveCompanionChatPackage,
  type CompanionChatPackage,
} from "./pet-core/companionChat";
import {
  CompanionChatProviderError,
  createCompanionChatProvider,
} from "./pet-core/companionChatProvider";
import { ProviderAdapterError } from "./pet-core/companionProviderAdapter";
import {
  INACTIVE_COMPANION_CHAT,
  LOCAL_COMPANION_CHAT_PROVIDER_INFO,
  receiveCompanionReply,
  enterCompanionChat,
  retryCompanionMessage,
  sendCompanionMessage,
  stopCompanionReply,
  startCompanionContextEpoch,
  updateCompanionDraft,
  type CompanionChatProviderInfo,
  type CompanionChatState,
} from "./pet-core/companionChatRuntime";
import {
  isExplicitCompanionTopicChange,
} from "./pet-core/companionContextEpoch";
import {
  type CompanionPreferencesState,
} from "./pet-core/companionPreferences";
import {
  normalizeCompanionUserProfile,
  validateCompanionUserProfile,
  type CompanionUserProfile,
  type CompanionUserProfileActionResult,
} from "./pet-core/companionUserProfile";
import {
  createCompanionUserSettingsOwner,
  createCompanionUserSettingsRepository,
  type CompanionUserSettingsRepository,
  type CompanionUserSettingsOwner,
} from "./pet-core/companionUserSettingsRepository";
import {
  clearCompanionUserSettingsDevFault,
  createCompanionUserSettingsDevStorage,
} from "./pet-core/companionUserSettingsDevFault";
import {
  createCompanionUserSettingsBridge,
  startCompanionUserSettingsOwnerBridge,
  type CompanionUserSettingsOwnerBridgeEmission,
  type CompanionUserSettingsOwnerBridgeLifecycle,
} from "./pet-core/companionUserSettingsBridge";
import { startCompanionUserSettingsRuntime } from "./pet-core/companionUserSettingsRuntime";
import {
  clearCompanionProviderCredentialWithSecureStore,
  readCompanionProviderCredential,
  readCompanionProviderSettings,
  readCompanionProviderSettingsStateWithSecureStore,
  getCompanionProviderProfilePreset,
  getCompanionProviderLabel,
  getCompanionProviderStatusInfo,
  isLocalCompanionProviderProtocol,
  normalizeCompanionProviderSettings,
  validateCompanionProviderSettings,
  writeCompanionProviderSettingsWithSecureStore,
  type CompanionProviderActionResult,
  type CompanionProviderId,
  type CompanionProviderSettings,
} from "./pet-core/companionProviderConfig";
import {
  fetchCompanionProviderModels as fetchUpstreamCompanionProviderModels,
  getCompanionProviderModelListUrl,
  type CompanionProviderModelsActionResult,
} from "./pet-core/companionProviderModels";
import {
  createCompanionProviderSyncCoordinator,
  type CompanionProviderSyncCoordinator,
} from "./pet-core/companionProviderSync";
import {
  createCompanionProviderWindowLifecycle,
  type CompanionProviderWindowLifecycle,
} from "./pet-core/companionProviderWindowLifecycle";
import { shouldRecordProviderFallback } from "./pet-core/companionObservability";
import {
  createCompanionMemoryRepository,
  type MemoryRepository,
} from "./pet-core/companionMemory";
import {
  loadPetSoulPackage,
  type PetSoulPackage,
} from "./pet-core/petSoul";
import {
  autoExitCompanionTaskChat,
  exitCompanionTaskChat,
} from "./pet-core/companionTaskSession";
import {
  COMPANION_LOCAL_USER_ID,
  createCompanionAppHarness,
  type CompanionAppHarnessRuntime,
} from "./pet-core/companionAppHarness";
import {
  createProactiveTaskCandidate,
  createProactiveTriggerEngine,
  selectProactiveTaskCandidates,
  type ProactiveTaskCandidate,
  type ProactiveTriggerDecision,
} from "./pet-core/proactiveTriggerEngine";
import {
  canRenderProactiveTaskDelivery,
  planProactiveTaskDeliveryRoute,
  resolveProactiveTaskDelivery,
  type ProactiveTaskDelivery,
} from "./pet-core/proactiveDelivery";
import {
  CARE_REMINDER_STORAGE_KEY,
  getNextCareReminderWakeSchedules,
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
  DEFAULT_PET_VISIBLE_BOUNDS,
  measurePetVisibleBounds,
} from "./pet-core/petVisibleBounds";
import {
  buildPetWindowLayout,
  getPetReminderWindowSize,
  type PetBubbleSize,
} from "./pet-core/petWindowLayout";
import {
  PLATFORM_FEEDBACK_BUBBLE_MS,
  expireBubbleText,
  getBubbleTextAfterPetMovement,
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
import {
  buildTaskMenuLayout,
  chooseTaskMenuPlacement,
  type TaskMenuPlacement,
} from "./task-core/taskMenuLayout";
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
  TASK_DATABASE_STORAGE_KEY,
  triggerDueReminders,
  writeTaskDatabase,
  updateTaskSettings,
} from "./task-core/taskStore";
import { selectTasks, type TaskListView } from "./task-core/taskQueries";
import type {
  InterfaceFontSize,
  Task,
  TaskDatabase,
  TaskDraft,
  TriggeredReminder,
} from "./task-core/types";
import { createLocalRepository } from "./storage/localRepository";
import "./task-core/task-ui.css";
const CURRENT_PET_STORAGE_KEY = "desktop-pet.currentPetId";
const LOCAL_SETTINGS_REPOSITORY = createLocalRepository();
const PET_WINDOW_SIZE = { width: 165, height: 215 };
const PET_REMINDER_WINDOW_SIZE = { width: 240, height: 450 };
const PLATFORM_PANEL_WIDTH = 860;
const PLATFORM_PET_INSET_PX = 6;
const PLATFORM_WINDOW_SIZE = {
  width: PLATFORM_PANEL_WIDTH,
  height: 590,
};
const QUICK_CREATE_WINDOW_SIZE = { width: 390, height: 290 };
const STARTUP_WINDOW_REVEAL_FALLBACK_MS = 8_000;
const COMPANION_CHAT_OPENED_EVENT = "companion-chat-opened";

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
type WindowMode = "platform" | "pet" | "quick-create" | "task-menu";
type AppliedWindowLayout = {
  mode: WindowMode;
  logicalSize: WindowSize;
  position: WindowPosition;
  petViewport: PetViewport;
};
type PhysicalPetPlacement = {
  anchor: PhysicalPetAnchor;
  scaleFactor: number;
  workArea: WorkArea;
};
type OpenPlatformPayload = {
  resetPetPosition?: boolean;
};
type PlatformNavigationPayload = {
  section: PlatformSection | "quick-create";
  view?: TaskListView;
  taskId?: string | null;
};
type CompanionChatSurfacePayload = {
  surface: "pet" | "platform";
};
type PetSelectedPayload = {
  petId: string;
};
type TaskSchedulerWakeupPayload = {
  careKind?: string | null;
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
type QueuedProactiveDelivery = {
  key: string;
  decision: ProactiveTriggerDecision;
  candidates: ProactiveTaskCandidate[];
};

const CARE_REMINDER_SNOOZE_MS = 10 * 60 * 1000;
const RANDOM_REMINDER_PROMPT_MS = 2 * 60 * 1000;

function getPetViewportForLayout(
  mode: WindowMode,
  logicalSize: WindowSize,
  petViewportOverride: PetViewport | null = null,
): PetViewport {
  if (petViewportOverride) return petViewportOverride;

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

function isSamePetViewport(left: PetViewport, right: PetViewport): boolean {
  return (
    left.x === right.x &&
    left.y === right.y &&
    left.width === right.width &&
    left.height === right.height
  );
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
  return LOCAL_SETTINGS_REPOSITORY.readValue(CURRENT_PET_STORAGE_KEY)?.trim() || null;
}

function saveSelectedPetId(petId: string): void {
  LOCAL_SETTINGS_REPOSITORY.writeValue(CURRENT_PET_STORAGE_KEY, petId);
}

function getOptionalCurrentWindow(): TauriWindow | null {
  if (!isTauriRuntime()) return null;

  try {
    return getCurrentWindow();
  } catch {
    return null;
  }
}

function isDedicatedPlatformWindow(): boolean {
  if (getOptionalCurrentWindow()?.label === "platform") return true;
  if (isTauriRuntime() || typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("window") === "platform";
}

async function revealDedicatedPlatformWindow(): Promise<void> {
  if (!isTauriRuntime()) return;
  const windows = await getAllWebviewWindows();
  const platformWindow = windows.find((candidate) => candidate.label === "platform");
  if (!platformWindow) throw new Error("platform window is unavailable");

  await revealPlatformWindow(platformWindow);
}

function recordInteraction(event: string): Promise<unknown> {
  return invoke("record_interaction", { event }).catch(() => {});
}

type ChatObservationEvent =
  | "chat_request_started"
  | "chat_stop_clicked"
  | "chat_turn_cancelled"
  | "chat_fallback_started"
  | "chat_result_committed"
  | "chat_result_discarded"
  | "provider_listener_attached"
  | "provider_listener_detached"
  | "provider_sync_notified"
  | "provider_hydrated"
  | "pet_switched"
  | "confirmation_started"
  | "confirmation_committed"
  | "domain_write_committed"
  | "memory_save_committed"
  | "memory_forget_committed";

type ChatObservationFields = {
  httpStatus?: number;
  listenerCount?: number;
  callCount?: number;
  commitCount?: number;
  writeCount?: number;
  cancelled?: boolean;
  fallback?: boolean;
  lateDiscarded?: boolean;
};

function recordChatObservation(
  event: ChatObservationEvent,
  fields: ChatObservationFields = {},
): Promise<unknown> {
  const currentWindow = getOptionalCurrentWindow();
  if (!currentWindow) return Promise.resolve();
  return invoke("record_interaction", {
    event: `chat_observation:${JSON.stringify({
      windowLabel: currentWindow.label,
      event,
      ...fields,
    })}`,
  }).catch(() => {});
}

function localDateKey(date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function getPlatformGreeting(date = new Date()): string {
  const hour = date.getHours();
  if (hour < 6) return "夜深了";
  if (hour < 11) return "早上好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
}

function formatPlatformDate(date = new Date()): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(date);
}

function formatHomeTaskSchedule(task: Task): string {
  if (!task.dueAt) return "随时";
  if (task.schedulePrecision === "date") {
    return localDateKey(new Date()) === task.dueAt
      ? "今天"
      : task.dueAt.slice(5).replace("-", "/");
  }

  const dueAt = new Date(task.dueAt);
  if (Number.isNaN(dueAt.getTime())) return "待安排";
  const isToday = localDateKey(dueAt) === localDateKey();
  return new Intl.DateTimeFormat(
    "zh-CN",
    isToday
      ? { hour: "2-digit", minute: "2-digit" }
      : { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" },
  ).format(dueAt);
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
  const isPlatformWindow = isDedicatedPlatformWindow();
  const shellRef = useRef<HTMLElement>(null);
  const pixiHost = useRef<HTMLDivElement>(null);
  const startupPetReady = useRef(false);
  const startupLayoutReady = useRef(false);
  const startupWindowRevealed = useRef(false);
  const startupRevealTimer = useRef<number | null>(null);
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
  // A pointer released after dragging is still physically over the moving
  // pet window. Do not reinterpret that same pointer as a fresh hover until
  // it leaves the pet surface; otherwise hover fish can interrupt landing.
  const hoverSuppressedByDrag = useRef(false);
  const dragHoverSuppressionTimer = useRef<number | null>(null);
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
  const lastSecondaryClickAt = useRef<number | null>(null);
  const secondaryClickResetTimer = useRef<number | null>(null);
  const initialCareReminderState = readCareReminderState();
  const careReminderState = useRef<CareReminderState>(initialCareReminderState);
  const [careReminderSettings, setCareReminderSettings] = useState(careReminderState.current.settings);
  const [careReminderNoticeDismissed, setCareReminderNoticeDismissed] = useState(careReminderState.current.systemPopupNoticeDismissed);
  const nextWellnessTime = useRef(
    initialCareReminderState.nextWellnessTime ??
      Date.now() + careReminderState.current.settings.wellness.intervalMinutes * 60 * 1000,
  );
  const [careReminderScheduleRevision, setCareReminderScheduleRevision] = useState(0);
  const timedCareSnoozedUntil = useRef(0);
  const nextIdleQuirkTime = useRef(Date.now() + randomInRange(20, 30) * 1000);
  const currentAnimation = useRef<AnimationName>("idle");
  const currentFacing = useRef<PetFacing>("right");
  // Drag textures use full transparent 192x208 cells. Keep the character's
  // contact line fixed while its silhouette changes; the values are source
  // texture pixels and are converted through the active visual scale below.
  const dragTextureStartFrame = useRef<number | null>(null);
  const idleFollowsDragDirection = useRef(false);
  const playbackToken = useRef(0);
  const [bubbleText, setBubbleText] = useState<string | null>(null);
  const careReminderPromptRef = useRef<ActiveCareReminderPrompt | null>(null);
  const [careReminderPrompt, setCareReminderPrompt] =
    useState<ActiveCareReminderPrompt | null>(null);
  const [isPlatformOpen, setIsPlatformOpen] = useState(
    isTauriRuntime() ? isPlatformWindow : PLATFORM_START_OPEN,
  );
  const [isTaskMenuOpen, setIsTaskMenuOpen] = useState(false);
  const [isQuickCreateOpen, setIsQuickCreateOpen] = useState(false);
  const [isPlatformMaximized, setIsPlatformMaximized] = useState(false);
  const [platformSection, setPlatformSection] = useState<PlatformSection>(
    PLATFORM_START_SECTION,
  );
  const [taskListView, setTaskListView] = useState<TaskListView>("today");
  const [taskDetailId, setTaskDetailId] = useState<string | null>(null);
  const [hiddenTaskReminderIds, setHiddenTaskReminderIds] = useState<Set<string>>(() => new Set());
  const [taskDatabase, setTaskDatabase] = useState<TaskDatabase>(() => {
    const stored = readTaskDatabase();
    const timezoneAdjusted = reconcileTaskTimezone(stored);
    const purged = purgeExpiredTrash(timezoneAdjusted);
    if (purged === stored) return stored;
    return writeTaskDatabase(purged) ? purged : stored;
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
  const [petSoulsById, setPetSoulsById] = useState<
    Record<string, PetSoulPackage>
  >({});
  const [petTaskFeedbackById, setPetTaskFeedbackById] = useState<
    Record<string, TaskFeedbackPackage>
  >({});
  const [petVisibleBounds, setPetVisibleBounds] = useState(DEFAULT_PET_VISIBLE_BOUNDS);
  const [petBubbleSize, setPetBubbleSize] = useState<PetBubbleSize | null>(null);
  const [taskMenuPlacement, setTaskMenuPlacement] = useState<TaskMenuPlacement>("right");
  const [companionChatState, setCompanionChatState] =
    useState<CompanionChatState>(INACTIVE_COMPANION_CHAT);
  const [companionChatProviderInfo, setCompanionChatProviderInfo] =
    useState<CompanionChatProviderInfo>(LOCAL_COMPANION_CHAT_PROVIDER_INFO);
  const [ollamaPullProgress, setOllamaPullProgress] =
    useState<BundledOllamaPullProgress | null>(null);
  const [companionProviderSettings, setCompanionProviderSettings] =
    useState<CompanionProviderSettings>(() => readCompanionProviderSettings());
  const companionUserSettingsOwnerRef = useRef<CompanionUserSettingsOwner | null>(null);
  const companionUserSettingsRepositoryRef = useRef<CompanionUserSettingsRepository | null>(null);
  const companionUserSettingsStorageRef = useRef<
    Parameters<typeof createCompanionUserSettingsOwner>[0] | null
  >(null);
  const companionUserSettingsOwnerFactoryRef = useRef<((options: {
    ownerEpoch: string;
    issuedAt: number;
  }) => CompanionUserSettingsOwner) | null>(null);
  const companionUserSettingsOwnerBridgeStopRef = useRef<(() => void) | null>(null);
  const companionUserSettingsOwnerBridgeLifecycleRef = useRef<CompanionUserSettingsOwnerBridgeLifecycle>({
    commandListeners: 0,
    ownerSubscriptions: 0,
  });
  const companionUserSettingsOwnerBridgeEventsRef = useRef<CompanionUserSettingsOwnerBridgeEmission[]>([]);
  if (companionUserSettingsRepositoryRef.current === null) {
    if (isPlatformWindow && isTauriRuntime()) {
      companionUserSettingsRepositoryRef.current = createCompanionUserSettingsBridge();
    } else {
      const storage = createCompanionUserSettingsDevStorage(window.localStorage);
      companionUserSettingsStorageRef.current = storage;
      companionUserSettingsOwnerRef.current = createCompanionUserSettingsOwner(storage);
      companionUserSettingsOwnerFactoryRef.current = (options) =>
        createCompanionUserSettingsOwner(storage, options);
      companionUserSettingsRepositoryRef.current = createCompanionUserSettingsRepository({
        owner: companionUserSettingsOwnerRef.current,
      });
    }
  }
  const companionUserSettingsRepository = companionUserSettingsRepositoryRef.current!;
  const [companionSettingsInitialization, setCompanionSettingsInitialization] = useState(
    () => companionUserSettingsRepository.getInitialization(),
  );
  const [companionUserProfile, setCompanionUserProfile] = useState<CompanionUserProfile | null>(
    () => companionUserSettingsRepository.getSnapshot()?.profile ?? null,
  );
  const companionUserProfileRef = useRef<CompanionUserProfile | null>(companionUserProfile);
  companionUserProfileRef.current = companionUserProfile;
  const companionChatStateRef = useRef<CompanionChatState>(INACTIVE_COMPANION_CHAT);
  const commitCompanionChatState = (
    next: CompanionChatState | ((current: CompanionChatState) => CompanionChatState),
  ) => {
    const current = companionChatStateRef.current;
    const resolved = typeof next === "function" ? next(current) : next;
    companionChatStateRef.current = resolved;
    setCompanionChatState(resolved);
  };
  const companionProviderCredentialRef = useRef<string | null>(null);
  const companionChatAbortControllerRef = useRef<AbortController | null>(null);
  const companionSessionIdRef = useRef<string | null>(null);
  const companionRequestSequenceRef = useRef(0);
  const companionAttemptRef = useRef<{
    sessionId: string;
    requestId: string;
    sourceMessageId: string;
    petId: string;
    controller: AbortController;
  } | null>(null);
  const companionConfirmationPendingRef = useRef(false);
  const companionProviderSettingsRef = useRef<CompanionProviderSettings>(
    companionProviderSettings,
  );
  const companionProviderHydrationPromiseRef = useRef<Promise<void>>(Promise.resolve());
  const companionProviderSyncRef = useRef<CompanionProviderSyncCoordinator | null>(null);
  const companionProviderWindowLifecycleRef = useRef<CompanionProviderWindowLifecycle | null>(null);
  const waitForCompanionProviderState = () =>
    companionProviderSyncRef.current?.waitForSettled() ??
    companionProviderHydrationPromiseRef.current;
  const companionPreferencesRef = useRef<CompanionPreferencesState | null>(
    companionUserSettingsRepository.getSnapshot()?.preferences ?? null,
  );
  const applyCompanionSettingsInitialization = (
    initialization: ReturnType<CompanionUserSettingsRepository["getInitialization"]>,
  ) => {
    setCompanionSettingsInitialization(initialization);
    if (initialization.status === "ready") {
      const nextProfile = initialization.snapshot.profile;
      const nextPreferences = initialization.snapshot.preferences;
      companionUserProfileRef.current = nextProfile;
      companionPreferencesRef.current = nextPreferences;
      setCompanionUserProfile(nextProfile);
    } else {
      companionUserProfileRef.current = null;
      companionPreferencesRef.current = null;
      setCompanionUserProfile(null);
    }
  };

  useEffect(() => {
    return startCompanionUserSettingsRuntime({
      repository: companionUserSettingsRepository,
      owner: companionUserSettingsOwnerRef.current,
      isPlatformWindow,
      isTauriRuntime: isTauriRuntime(),
      applyInitialization: applyCompanionSettingsInitialization,
      startOwnerBridge: startCompanionUserSettingsOwnerBridge,
      ownerBridgeOptions: !isPlatformWindow
        ? {
            onEmit: (emission) => {
              if (import.meta.env.DEV) {
                companionUserSettingsOwnerBridgeEventsRef.current.push(emission);
              }
            },
            onLifecycle: (lifecycle) => {
              companionUserSettingsOwnerBridgeLifecycleRef.current = lifecycle;
            },
          }
        : undefined,
      onOwnerBridgeStarted: (stop) => {
        companionUserSettingsOwnerBridgeStopRef.current = stop;
      },
    });
  }, [companionUserSettingsRepository, isPlatformWindow]);
  useEffect(() => {
    if (!import.meta.env.DEV) return undefined;
    let disposed = false;
    let cleanup = () => {};
    void import("./pet-core/companionUserSettingsDevScenario").then((module) => {
      if (disposed) return;
      cleanup = module.startCompanionUserSettingsDevScenario({
        repository: companionUserSettingsRepository,
        isPlatformWindow,
        isTauriRuntime: isTauriRuntime(),
        owner: companionUserSettingsOwnerRef.current,
        createOwner: companionUserSettingsOwnerFactoryRef.current ?? undefined,
        startOwnerBridge: startCompanionUserSettingsOwnerBridge,
        getOwnerBridgeStop: () => companionUserSettingsOwnerBridgeStopRef.current,
        getOwnerBridgeLifecycle: () => companionUserSettingsOwnerBridgeLifecycleRef.current,
        ownerBridgeEvents: companionUserSettingsOwnerBridgeEventsRef.current,
      });
    });
    return () => {
      disposed = true;
      cleanup();
    };
  }, [companionUserSettingsRepository, isPlatformWindow]);
  const [companionMemoryRepository] = useState<MemoryRepository>(() =>
    createCompanionMemoryRepository(),
  );
  const proactiveDeliveryOutcomeRef = useRef(new Map<string, string>());
  const pendingProactiveDeliveriesRef = useRef<QueuedProactiveDelivery[]>([]);
  const pendingProactiveDeliveryKeysRef = useRef(new Set<string>());
  const [activePetId, setActivePetId] = useState(DEFAULT_PET_ID);
  const activePetIdRef = useRef(DEFAULT_PET_ID);
  const proactiveTriggerEngine = useMemo(
    () => createProactiveTriggerEngine({
      activePetId,
      availablePetIds,
    }),
    [activePetId, availablePetIds],
  );
  const taskDatabaseRef = useRef(taskDatabase);
  const availablePetIdsRef = useRef(availablePetIds);
  const petManifestsByIdRef = useRef(petManifestsById);
  const petCompanionChatsByIdRef = useRef(petCompanionChatsById);
  const petSoulsByIdRef = useRef(petSoulsById);
  const proactiveTriggerEngineRef = useRef(proactiveTriggerEngine);
  taskDatabaseRef.current = taskDatabase;
  availablePetIdsRef.current = availablePetIds;
  petManifestsByIdRef.current = petManifestsById;
  petCompanionChatsByIdRef.current = petCompanionChatsById;
  petSoulsByIdRef.current = petSoulsById;
  proactiveTriggerEngineRef.current = proactiveTriggerEngine;
  activePetIdRef.current = activePetId;
  const petWindowLayout = useMemo(
    () => buildPetWindowLayout(petVisibleBounds, petBubbleSize),
    [petBubbleSize, petVisibleBounds],
  );
  const windowMode = useRef<WindowMode>(isPlatformOpen ? "platform" : "pet");
  const appliedWindowLayout = useRef<AppliedWindowLayout | null>(null);
  const physicalPetPlacement = useRef<PhysicalPetPlacement | null>(null);
  const petViewportRef = useRef<PetViewport>(
    petWindowLayout.petViewport,
  );
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
  const companionChatSurface: CompanionChatSurfacePayload["surface"] =
    isPlatformWindow ? "platform" : "pet";
  const renderedPlatformSection = resolveRenderedPlatformSection(
    platformSection,
    companionChatState.mode,
  );

  const companionTaskRepositoryRef = useRef<{
    read: () => TaskDatabase;
    write: (database: TaskDatabase) => boolean;
  } | null>(null);
  if (companionTaskRepositoryRef.current === null) {
    companionTaskRepositoryRef.current = {
      read: () => readTaskDatabase(),
      write: (database) => {
        let written = false;
        try {
          written = writeTaskDatabase(database);
        } catch {
          written = false;
        }
        if (written) {
          taskDatabaseRef.current = database;
          setTaskDatabase(database);
        }
        return written;
      },
    };
  }

  const companionAppHarnessRef = useRef<CompanionAppHarnessRuntime | null>(null);
  if (companionAppHarnessRef.current === null) {
    companionAppHarnessRef.current = createCompanionAppHarness({
      getProviderProfile: () => companionProviderSettingsRef.current,
      getProviderCredential: () => companionProviderCredentialRef.current,
      getFallbackToLocal: () => companionProviderSettingsRef.current.fallbackToLocal,
      getActivePetId: () => activePetIdRef.current,
      getAvailablePetIds: () => availablePetIdsRef.current,
      getCompanionChatPackage: (petId) =>
        petCompanionChatsByIdRef.current[petId]
        ?? { status: "not-configured", petId },
      getPetSoul: (petId) => petSoulsByIdRef.current[petId],
      getPreferences: () => companionPreferencesRef.current,
      getMemoryRepository: () => companionMemoryRepository,
      getHistory: ({ petId, sessionId, sourceMessageId, contextEpoch }) => {
        const state = companionChatStateRef.current;
        if (
          state.mode !== "active"
          || activePetIdRef.current !== petId
          || companionSessionIdRef.current !== sessionId
        ) return [];
        return state.messages.filter((message) =>
          message.id !== sourceMessageId
          && (contextEpoch === undefined || message.contextEpoch === contextEpoch),
        );
      },
      taskRepository: companionTaskRepositoryRef.current,
      getProactiveTriggerEngine: () => proactiveTriggerEngineRef.current,
      settingsRepository: companionUserSettingsRepository,
      responseSink: {
        commit: (input, response, guard) => {
          const current = companionChatStateRef.current;
          if (
            current.mode !== "active"
            || activePetIdRef.current !== input.petId
            || companionSessionIdRef.current !== input.sessionId
            || current.pendingRequestId !== input.sourceMessageId
          ) {
            void recordChatObservation("chat_result_discarded", {
              callCount: response.callCounts.model,
              commitCount: 0,
              lateDiscarded: true,
            });
            return;
          }
          const domainWriteCount = response.actions.filter(
            (action) => action.status === "succeeded",
          ).length;
          const memoryWriteCount = response.memory.acceptedCount;
          const forgetWriteCount = response.forget?.status === "succeeded" ? 1 : 0;
          const needsConfirmation = response.actions.some(
            (action) => action.status === "confirmation_required",
          ) || response.memory.decisions.some(
            (decision) => decision.status === "confirmation_required",
          );
          const committed = guard.commitIfCurrent(input, response, () => {
            setCompanionChatProviderInfo(response.provider);
            commitCompanionChatState((state) =>
              state.mode === "active"
              && activePetIdRef.current === input.petId
              && companionSessionIdRef.current === input.sessionId
              && state.pendingRequestId === input.sourceMessageId
                ? receiveCompanionReply(
                    state,
                    response.text ?? "这次没有可显示的回复。",
                  )
                : state,
            );
          });
          if (!committed) {
            void recordChatObservation("chat_result_discarded", {
              callCount: response.callCounts.model,
              commitCount: 0,
              lateDiscarded: true,
            });
            return;
          }
          if (shouldRecordProviderFallback(response)) {
            void recordChatObservation("chat_fallback_started", {
              callCount: response.callCounts.model,
              fallback: true,
            });
          }
          if (needsConfirmation && !companionConfirmationPendingRef.current) {
            companionConfirmationPendingRef.current = true;
            void recordChatObservation("confirmation_started", { writeCount: 0 });
          }
          if (domainWriteCount > 0) {
            void recordChatObservation("domain_write_committed", {
              writeCount: domainWriteCount,
              commitCount: 1,
            });
          }
          if (memoryWriteCount > 0) {
            void recordChatObservation("memory_save_committed", {
              writeCount: memoryWriteCount,
              commitCount: 1,
            });
          }
          if (forgetWriteCount > 0) {
            void recordChatObservation("memory_forget_committed", {
              writeCount: forgetWriteCount,
              commitCount: 1,
            });
          }
          if (companionConfirmationPendingRef.current && domainWriteCount > 0) {
            companionConfirmationPendingRef.current = false;
            void recordChatObservation("confirmation_committed", {
              writeCount: domainWriteCount,
              commitCount: 1,
            });
          }
          void recordChatObservation("chat_result_committed", {
            callCount: response.callCounts.model,
            commitCount: 1,
            writeCount: domainWriteCount + memoryWriteCount + forgetWriteCount,
            fallback: response.degraded,
            cancelled: false,
          });
        },
      },
    });
  }
  const companionAppHarness = companionAppHarnessRef.current!;

  const revealStartupWindow = (reason: string) => {
    if (startupWindowRevealed.current) return;
    const appWindow = getOptionalCurrentWindow();
    if (!appWindow) return;

    startupWindowRevealed.current = true;
    if (startupRevealTimer.current !== null) {
      window.clearTimeout(startupRevealTimer.current);
      startupRevealTimer.current = null;
    }
    void appWindow.show()
      .then(() => recordInteraction(reason))
      .catch(() => {
        startupWindowRevealed.current = false;
        recordInteraction("startup_window_reveal_failed");
      });
  };

  const revealStartupWindowIfReady = () => {
    if (!startupPetReady.current || !startupLayoutReady.current) return;
    revealStartupWindow("startup_window_revealed_with_pet");
  };

  const refreshCareReminderState = (next = readCareReminderState()) => {
    careReminderState.current = next;
    setCareReminderSettings(next.settings);
    setCareReminderNoticeDismissed(next.systemPopupNoticeDismissed);
    nextWellnessTime.current =
      next.nextWellnessTime ??
      Date.now() + next.settings.wellness.intervalMinutes * 60 * 1000;
    setCareReminderScheduleRevision((revision) => revision + 1);
  };

  const broadcastCareReminderState = () => {
    if (isTauriRuntime()) {
      void emit("care-reminder-state-updated", {}).catch(() => {});
    }
  };

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
  const homeTodayTasks = useMemo(
    () => selectTasks(taskDatabase, "today"),
    [taskDatabase],
  );
  const homeCompletedCount = useMemo(
    () => taskDatabase.history.filter(
      (entry) =>
        entry.type === "completed"
        && localDateKey(new Date(entry.createdAt)) === localDateKey(),
    ).length,
    [taskDatabase.history],
  );
  const homeTaskPreview = homeTodayTasks.slice(0, 3);
  const homePetMessage = homeTodayTasks.length > 0
    ? `今天有 ${homeTodayTasks.length} 件事，我会在桌面上陪着你慢慢完成。`
    : "今天还很轻盈。想做什么时，先从一件小事开始就好。";
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
  const taskMenuLayout = useMemo(
    () => buildTaskMenuLayout(petVisibleBounds, taskMenuPlacement),
    [petVisibleBounds, taskMenuPlacement],
  );

  useEffect(() => {
    if (isPlatformWindow) return;
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
  }, [isPlatformWindow, taskDatabase]);

  const TASK_DATABASE_WRITE_FAILURE_FEEDBACK = "我暂时没能保存这次待办变更，再试一次好吗？";

  const commitTaskDatabase = (next: TaskDatabase, feedback?: string): boolean => {
    const completedDelta = next.history.filter((entry) => entry.type === "completed").length
      - taskDatabase.history.filter((entry) => entry.type === "completed").length;
    const postponedDelta = next.history.filter((entry) => entry.type === "postponed").length
      - taskDatabase.history.filter((entry) => entry.type === "postponed").length;
    const createdDelta = next.tasks.length - taskDatabase.tasks.length;
    const nextActiveInstanceIds = new Set(next.reminderInstances
      .filter((instance) => ["triggered", "missed"].includes(instance.status))
      .map((instance) => instance.id));
    if (!writeTaskDatabase(next)) {
      showTransientBubbleText(TASK_DATABASE_WRITE_FAILURE_FEEDBACK);
      return false;
    }
    for (const instance of taskDatabase.reminderInstances) {
      if (!["triggered", "missed"].includes(instance.status) || nextActiveInstanceIds.has(instance.id)) continue;
      systemTaskNotifications.current.get(instance.id)?.close();
      if (isTauriRuntime()) void invoke("clear_task_notification", { instanceId: instance.id }).catch(() => {});
      customTaskNotifications.current.delete(instance.id);
    }
    setTaskDatabase(next);
    if (feedback) showTransientBubbleText(feedback);
    const resolved = getActiveInteractionManifest();
    if (!resolved) return true;
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
    return true;
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
    if (!isTauriRuntime()) {
      let cancelled = false;
      const hydration = readCompanionProviderSettingsStateWithSecureStore()
        .then(({ settings, credential }) => {
          if (cancelled) return;
          companionProviderCredentialRef.current = credential;
          companionProviderSettingsRef.current = settings;
          setCompanionProviderSettings(settings);
        })
        .catch(() => {
          // Keep the non-secret metadata loaded from ordinary settings. A later
          // save will surface the secure-store error without exposing the Key.
        });
      companionProviderHydrationPromiseRef.current = hydration;
      return () => {
        cancelled = true;
      };
    }

    const sourceWindow = getOptionalCurrentWindow()?.label ??
      (isPlatformWindow ? "platform" : "main");
    const coordinator = createCompanionProviderSyncCoordinator({
      sourceWindow,
      initial: {
        settings: companionProviderSettingsRef.current,
        credential: companionProviderCredentialRef.current,
      },
      hydrate: readCompanionProviderSettingsStateWithSecureStore,
      onState: ({ settings, credential }) => {
        companionProviderCredentialRef.current = credential;
        companionProviderSettingsRef.current = settings;
        setCompanionProviderSettings(settings);
        setCompanionChatProviderInfo(getCompanionProviderStatusInfo(settings));
      },
      onProviderChanged: () => cancelCompanionChatTurn(),
      onListenerAttached: (listenerCount) => {
        void recordChatObservation("provider_listener_attached", { listenerCount });
      },
      onListenerDetached: (listenerCount) => {
        void recordChatObservation("provider_listener_detached", { listenerCount });
      },
      onSyncNotified: () => {
        void recordChatObservation("provider_sync_notified");
      },
      onHydrated: () => {
        void recordChatObservation("provider_hydrated", { listenerCount: 1 });
      },
    });
    const windowLifecycle = createCompanionProviderWindowLifecycle(coordinator);
    companionProviderSyncRef.current = coordinator;
    companionProviderWindowLifecycleRef.current = windowLifecycle;
    const hydration = windowLifecycle.start().catch(() => {
      // Keep the locally loaded metadata if the event bridge is unavailable.
    });
    companionProviderHydrationPromiseRef.current = hydration;
    return () => {
      windowLifecycle.stop();
      if (companionProviderSyncRef.current === coordinator) {
        companionProviderSyncRef.current = null;
      }
      if (companionProviderWindowLifecycleRef.current === windowLifecycle) {
        companionProviderWindowLifecycleRef.current = null;
      }
    };
  }, [isPlatformWindow]);
  useEffect(() => {
    companionProviderSettingsRef.current = companionProviderSettings;
    setCompanionChatProviderInfo(getCompanionProviderStatusInfo(companionProviderSettings));
  }, [companionProviderSettings]);
  useEffect(() => {
    cancelCompanionChatTurn();
    activePetIdRef.current = activePetId;
    setCompanionChatProviderInfo(
      getCompanionProviderStatusInfo(companionProviderSettingsRef.current),
    );
    const exited = exitCompanionTaskChat(
      companionChatStateRef.current,
      null,
    );
    commitCompanionChatState(exited.state);
    if (isPlatformWindow && companionChatStateRef.current.mode === "active") {
      setPlatformSection(resolvePlatformSectionAfterCompanionExit("pet-switch"));
    }
  }, [activePetId]);
  useEffect(() => {
    let soundEnabled = false;

    const unlistenUpdatePromise = listenToAppEvent("check-update", () => {
      if (isPlatformWindow) return;
      void checkForUpdates(true);
    });
    const unlistenPlatformPromise = listenToAppEvent<OpenPlatformPayload>(
      "open-platform",
      (payload) => {
        if (payload?.resetPetPosition) {
          resetPetPositionOnNextOpen.current = true;
        }
        if (isPlatformWindow) {
          const lifecycle = companionProviderWindowLifecycleRef.current;
          if (lifecycle) void lifecycle.start().catch(() => {});
          setIsQuickCreateOpen(false);
          setIsPlatformOpen(true);
        } else {
          void revealDedicatedPlatformWindow().catch(() => {
            recordInteraction("platform_window_show_failed");
          });
        }
        recordInteraction("platform_open_from_tray");
      },
    );
    const unlistenPlatformNavigationPromise =
      listenToAppEvent<PlatformNavigationPayload>(
        "platform-navigation",
        (payload) => {
          if (!isPlatformWindow) return;
          const lifecycle = companionProviderWindowLifecycleRef.current;
          if (lifecycle) void lifecycle.start().catch(() => {});
          if (payload.section === "quick-create") {
            setIsPlatformOpen(false);
            setIsQuickCreateOpen(true);
            return;
          }
          setTaskListView(payload.view ?? "today");
          setTaskDetailId(payload.taskId ?? null);
          if (payload.section === "chat") {
            void openPlatformCompanionChat();
            setIsQuickCreateOpen(false);
            setIsPlatformOpen(true);
            return;
          }
          if (companionChatStateRef.current.mode === "active") {
            exitActiveCompanionChat(false, "navigation");
          }
          setPlatformSection(
            resolvePlatformSectionAfterCompanionExit("navigation", payload.section),
          );
          setIsQuickCreateOpen(false);
          setIsPlatformOpen(true);
        },
      );
    const unlistenPetSelectedPromise = listenToAppEvent<PetSelectedPayload>(
      "pet-selected",
      ({ petId }) => {
        saveSelectedPetId(petId);
        activePetIdRef.current = petId;
        setActivePetId(petId);
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
    const unlistenTaskWakeupPromise = listenToAppEvent<TaskSchedulerWakeupPayload>("task-scheduler-wakeup", (payload) => {
      if (isPlatformWindow) return;
      if (payload?.careKind === "wellness") {
        nextWellnessTime.current = Date.now();
      }
      window.dispatchEvent(new CustomEvent("task-scheduler-wakeup", { detail: payload }));
    });
    const unlistenCareReminderStatePromise = listenToAppEvent(
      "care-reminder-state-updated",
      () => refreshCareReminderState(),
    );
    const handleTaskNotificationAction = ({ instanceId, action }: { instanceId: string; action: string }) => {
        if (isPlatformWindow) return;
        if (action === "summary-detail") {
          openTaskPlatform("today");
          return;
        }
        if (action === "summary-close") {
          const next = closeMissedReminderSummary(readTaskDatabase());
          if (!writeTaskDatabase(next)) return;
          setTaskDatabase(next);
          void invoke("clear_task_notification", { instanceId }).catch(() => {});
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
        if (!writeTaskDatabase(next)) return;
        setTaskDatabase(next);
        customTaskNotifications.current.delete(instanceId);
      };
    const unlistenTaskNotificationActionPromise = listenToAppEvent<{ instanceId: string; action: string }>(
      "task-notification-action",
      handleTaskNotificationAction,
    );
    let ollamaPullClearTimer: number | null = null;
    const unlistenOllamaPullPromise = listenToAppEvent<BundledOllamaPullProgress>(
      "ollama-pull-progress",
      (progress) => {
        if (!progress?.model?.trim()) return;
        if (ollamaPullClearTimer !== null) {
          window.clearTimeout(ollamaPullClearTimer);
          ollamaPullClearTimer = null;
        }
        setOllamaPullProgress(progress);
        if (progress.done) {
          ollamaPullClearTimer = window.setTimeout(() => {
            setOllamaPullProgress(null);
            ollamaPullClearTimer = null;
          }, 2200);
        }
      },
    );

    if (isTauriRuntime() && !isPlatformWindow) {
      void invoke<Array<{ instanceId: string; action: string }>>("get_initial_task_notification_actions")
        .then((actions) => actions.forEach(handleTaskNotificationAction))
        .catch(() => {});
      void invoke<boolean>("is_task_scheduler_wakeup").then((isWakeup) => {
        if (!isWakeup) return;
        setIsPlatformOpen(false);
        setIsQuickCreateOpen(false);
        void invoke<string | null>("get_task_scheduler_wakeup_kind")
          .catch(() => null)
          .then((careKind) => {
            if (careKind === "wellness") {
              nextWellnessTime.current = Date.now();
            }
            window.dispatchEvent(new CustomEvent("task-scheduler-wakeup", { detail: { careKind } }));
          });
      }).catch(() => {});
    }

    return () => {
      void unlistenUpdatePromise.then((unlisten) => unlisten());
      void unlistenPlatformPromise.then((unlisten) => unlisten());
      void unlistenPlatformNavigationPromise.then((unlisten) => unlisten());
      void unlistenPetSelectedPromise.then((unlisten) => unlisten());
      void unlistenSoundPromise.then((unlisten) => unlisten());
      void unlistenQuickTaskPromise.then((unlisten) => unlisten());
      void unlistenTodayTasksPromise.then((unlisten) => unlisten());
      void unlistenTaskRemindersPromise.then((unlisten) => unlisten());
      void unlistenTaskWakeupPromise.then((unlisten) => unlisten());
      void unlistenCareReminderStatePromise.then((unlisten) => unlisten());
      void unlistenTaskNotificationActionPromise.then((unlisten) => unlisten());
      void unlistenOllamaPullPromise.then((unlisten) => unlisten());
      if (ollamaPullClearTimer !== null) {
        window.clearTimeout(ollamaPullClearTimer);
      }
    };
  }, [isPlatformWindow]);

  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (event.key === TASK_DATABASE_STORAGE_KEY) {
        setTaskDatabase(readTaskDatabase());
      }
      if (event.key === CURRENT_PET_STORAGE_KEY) {
        const nextPetId = readSavedPetId() ?? DEFAULT_PET_ID;
        activePetIdRef.current = nextPetId;
        setActivePetId(nextPetId);
      }
      if (event.key === CARE_REMINDER_STORAGE_KEY) {
        refreshCareReminderState();
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  useEffect(() => {
    if (!isPlatformWindow) return;

    const unlistenPetReady = listenToAppEvent("startup-pet-ready", () => {
      startupPetReady.current = true;
      revealStartupWindowIfReady();
    });

    return () => {
      void unlistenPetReady.then((unlisten) => unlisten());
    };
  }, [isPlatformWindow]);

  useEffect(() => {
    if (!isPlatformWindow) return;
    const appWindow = getOptionalCurrentWindow();
    if (!appWindow) return;

    let disposed = false;
    const syncMaximizedState = () => {
      void appWindow.isMaximized()
        .then((maximized) => {
          if (!disposed) setIsPlatformMaximized(maximized);
        })
        .catch(() => {});
    };

    syncMaximizedState();
    const unlistenResize = appWindow.onResized(syncMaximizedState);

    return () => {
      disposed = true;
      void unlistenResize.then((unlisten) => unlisten()).catch(() => {});
    };
  }, [isPlatformWindow]);

  useEffect(() => {
    if (!isTauriRuntime() || isPlatformWindow) return;
    const taskSchedules = (taskDatabase.settings.backgroundReminders ? taskDatabase.reminderInstances : [])
      .filter((instance) => instance.status === "scheduled")
      .map((instance) => ({ instanceId: instance.id, scheduledAt: instance.scheduledAt }));
    const careSchedules = getNextCareReminderWakeSchedules(
      new Date(),
      careReminderSettings,
      nextWellnessTime.current,
    ).map(({ id, scheduledAt, wakeKind }) => ({
      instanceId: id,
      scheduledAt,
      wakeKind,
    }));
    const schedules = [...taskSchedules, ...careSchedules];
    void invoke("sync_task_schedules", { schedules }).catch(() => {
      recordInteraction("task_schedule_sync_failed");
    });
  }, [
    isPlatformWindow,
    taskDatabase.reminderInstances,
    taskDatabase.settings.backgroundReminders,
    careReminderSettings,
    careReminderScheduleRevision,
  ]);

  useEffect(() => {
    if (!isTauriRuntime()) return;

    startupRevealTimer.current = window.setTimeout(() => {
      revealStartupWindow("startup_window_reveal_fallback");
    }, STARTUP_WINDOW_REVEAL_FALLBACK_MS);

    return () => {
      if (startupRevealTimer.current !== null) {
        window.clearTimeout(startupRevealTimer.current);
        startupRevealTimer.current = null;
      }
    };
  }, []);

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
        const soulEntries = await Promise.all(
          manifestEntries.map(
            async ([petId, manifest]) =>
              [petId, await loadPetSoulPackage(manifest)] as const,
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
        setPetSoulsById(Object.fromEntries(soulEntries));
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
        const fallbackSoul = await loadPetSoulPackage(fallbackManifest);
        const fallbackTaskFeedback = await loadTaskFeedbackPackage(fallbackManifest);
        if (disposed) return;
        setAvailablePetIds([DEFAULT_PET_ID]);
        setPetManifestsById({ [DEFAULT_PET_ID]: fallbackManifest });
        setPetDialoguesById({ [DEFAULT_PET_ID]: fallbackDialogues });
        setPetCompanionChatsById({ [DEFAULT_PET_ID]: fallbackCompanionChat });
        setPetSoulsById({ [DEFAULT_PET_ID]: fallbackSoul });
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
    if (!activePetManifest) {
      setPetVisibleBounds(DEFAULT_PET_VISIBLE_BOUNDS);
      return undefined;
    }

    let cancelled = false;
    void measurePetVisibleBounds(activePetManifest).then((bounds) => {
      if (!cancelled) setPetVisibleBounds(bounds);
    });

    return () => {
      cancelled = true;
    };
  }, [activePetManifest]);

  useLayoutEffect(() => {
    const shell = shellRef.current;
    if (!shell || isPlatformWindow) return undefined;

    const bubbleElement = shell.querySelector<HTMLElement>(
      ".companion-chat, .bubble",
    );
    if (!bubbleElement) {
      setPetBubbleSize(null);
      return undefined;
    }

    const hasTail = bubbleElement.classList.contains("bubble");
    const updateBubbleSize = () => {
      const rect = bubbleElement.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) {
        setPetBubbleSize(null);
        return;
      }

      const next: PetBubbleSize = {
        width: Math.ceil(rect.width),
        height: Math.ceil(rect.height),
        tailHeight: hasTail ? 8 : 0,
      };
      setPetBubbleSize((current) =>
        current &&
        current.width === next.width &&
        current.height === next.height &&
        current.tailHeight === next.tailHeight
          ? current
          : next,
      );
    };

    updateBubbleSize();
    if (typeof ResizeObserver === "undefined") return undefined;

    const observer = new ResizeObserver(updateBubbleSize);
    observer.observe(bubbleElement);
    return () => observer.disconnect();
  }, [
    activePetId,
    bubbleText,
    careReminderPrompt,
    companionChatState.mode === "active" ? companionChatState.draft : "",
    companionChatState.mode === "active" ? companionChatState.messages.length : 0,
    companionChatState.mode,
    isPlatformOpen,
    isQuickCreateOpen,
    isReminderWindowExpanded,
    isTaskMenuOpen,
    isPlatformWindow,
  ]);

  useEffect(() => {
    if (isPlatformWindow) return;
    if (isPlatformOpen || isQuickCreateOpen) return;
    const today = localDateKey();
    if (taskDatabase.settings.lastOverduePromptDate === today) return;
    const overdue = selectTasks(taskDatabase, "overdue");
    if (overdue.length === 0) return;
    const next = updateTaskSettings(taskDatabase, { lastOverduePromptDate: today });
    if (!writeTaskDatabase(next)) return;
    setTaskDatabase(next);
    const resolved = getActiveInteractionManifest();
    if (resolved) playTaskFeedback(
      "taskOverdue",
      overdue.length === 1 ? `还有「${overdue[0].title}」在等你，有空时看看就好。` : `今天有 ${overdue.length} 件过期事项，有空时慢慢看看。`,
      resolved.reminders.eyeCare,
    );
  }, [activePetId, isPlatformOpen, isPlatformWindow, isQuickCreateOpen, taskDatabase]);

  useEffect(() => {
    clearDefaultBubbleText();
  }, [activePetId, petDialoguesById]);

  const getInitialPhysicalPetPlacement = (
    monitor: Monitor,
  ): PhysicalPetPlacement => {
    const initialPosition = getInitialPetWindowPosition(
      monitor.workArea,
      getPhysicalWindowSize(petWindowLayout.windowSize, monitor),
    );

    return {
      anchor: getPhysicalPetAnchor(
        initialPosition,
        petWindowLayout.petViewport,
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
    petViewportOverride: PetViewport | null = null,
    isLatestLayout: () => boolean = () => true,
  ) => {
    if (!isLatestLayout()) return;

    const petViewport = getPetViewportForLayout(
      mode,
      logicalSize,
      petViewportOverride,
    );
    const previousLayout = appliedWindowLayout.current;
    if (
      previousLayout?.mode === mode &&
      isSameWindowSize(previousLayout.logicalSize, logicalSize) &&
      isSamePetViewport(previousLayout.petViewport, petViewport) &&
      !shouldResetPetAnchor
    ) {
      return;
    }

    const monitor = await getPlacementMonitor();
    if (!isLatestLayout()) return;
    const currentPosition = await appWindow.outerPosition().catch(() => null);
    if (!isLatestLayout()) return;

    if (previousLayout?.mode === "pet" && currentPosition && monitor) {
      const petWasMoved =
        currentPosition.x !== previousLayout.position.x ||
        currentPosition.y !== previousLayout.position.y;
      if (petWasMoved || physicalPetPlacement.current === null) {
        physicalPetPlacement.current = {
          anchor: getPhysicalPetAnchor(
            currentPosition,
            previousLayout.petViewport,
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

    // Tauri resize and position calls are separate native mutations. Keep the
    // renderer's viewport current first, and never let an obsolete layout
    // continue with the next mutation after a newer request has started.
    petViewportRef.current = petViewport;
    const shouldResizeWindow =
      previousLayout === null ||
      !isSameWindowSize(previousLayout.logicalSize, logicalSize);
    if (shouldResizeWindow) {
      if (!isLatestLayout()) return;
      await setWindowSize(appWindow, logicalSize);
      if (!isLatestLayout()) return;
    }

    const placement = physicalPetPlacement.current;
    if (!placement) {
      if (currentPosition && isLatestLayout()) {
        appliedWindowLayout.current = {
          mode,
          logicalSize,
          position: currentPosition,
          petViewport,
        };
      }
      return;
    }

    const anchoredPosition = getWindowPositionForPhysicalPetAnchor(
      placement.anchor,
      petViewport,
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

    if (!isLatestLayout()) return;
    const shouldMoveWindow =
      currentPosition === null ||
      currentPosition.x !== desiredPosition.x ||
      currentPosition.y !== desiredPosition.y;
    if (shouldMoveWindow) {
      await setWindowPosition(appWindow, desiredPosition);
      if (!isLatestLayout()) return;
    }
    const appliedPosition = await appWindow.outerPosition().catch(
      () => desiredPosition,
    );
    if (!isLatestLayout()) return;
    appliedWindowLayout.current = {
      mode,
      logicalSize,
      position: appliedPosition,
      petViewport,
    };
  };

  useEffect(() => {
    const appWindow = getOptionalCurrentWindow();
    if (!appWindow) return;

    if (isPlatformWindow) {
      windowMode.current = "platform";
      startupLayoutReady.current = true;
      revealStartupWindowIfReady();
      return;
    }

    const nextMode: WindowMode = isPlatformOpen
      ? "platform"
      : isQuickCreateOpen
        ? "quick-create"
        : isTaskMenuOpen
          ? "task-menu"
          : "pet";
    windowMode.current = nextMode;

    const shouldResetPetAnchor = resetPetPositionOnNextOpen.current;
    const desiredSize = nextMode === "platform"
      ? PLATFORM_WINDOW_SIZE
      : nextMode === "quick-create"
          ? QUICK_CREATE_WINDOW_SIZE
          : nextMode === "task-menu"
            ? taskMenuLayout.windowSize
            : isReminderWindowExpanded
            ? getPetReminderWindowSize(petBubbleSize, PET_REMINDER_WINDOW_SIZE)
            : petWindowLayout.windowSize;
    const failureEvent = nextMode === "platform"
      ? "platform_layout_failed"
      : nextMode === "quick-create"
        ? "quick_create_layout_failed"
        : nextMode === "task-menu"
          ? "task_menu_layout_failed"
          : "pet_layout_failed";
    const petViewportOverride = nextMode === "task-menu"
      ? taskMenuLayout.petViewport
      : nextMode === "pet" && !isReminderWindowExpanded
        ? petWindowLayout.petViewport
        : null;

    void windowLayoutScheduler.current
      .schedule(async (isLatestLayout) => {
        await applyAnchoredWindowLayout(
          appWindow,
          nextMode,
          desiredSize,
          shouldResetPetAnchor,
          petViewportOverride,
          isLatestLayout,
        );
        if (shouldResetPetAnchor && isLatestLayout()) {
          resetPetPositionOnNextOpen.current = false;
        }
      })
      .then((applied) => {
        if (!applied) return;
        startupLayoutReady.current = true;
        revealStartupWindowIfReady();
      })
      .catch(() => {
        recordInteraction(failureEvent);
      });
  }, [
    careReminderPrompt,
    isPlatformOpen,
    isPlatformWindow,
    isQuickCreateOpen,
    isTaskMenuOpen,
    petBubbleSize,
    petWindowLayout,
    taskMenuLayout,
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

  const minimizePlatformWindow = (
    event: ReactMouseEvent<HTMLButtonElement>,
  ) => {
    event.stopPropagation();
    const appWindow = getOptionalCurrentWindow();
    if (!appWindow || !isPlatformWindow) return;

    void appWindow.minimize().then(
      () => recordInteraction("platform_window_minimized"),
      () => recordInteraction("platform_window_minimize_failed"),
    );
  };

  const togglePlatformWindowMaximize = (
    event: ReactMouseEvent<HTMLButtonElement>,
  ) => {
    event.stopPropagation();
    const appWindow = getOptionalCurrentWindow();
    if (!appWindow || !isPlatformWindow) return;

    void appWindow.toggleMaximize()
      .then(() => appWindow.isMaximized())
      .then((maximized) => {
        setIsPlatformMaximized(maximized);
        recordInteraction(
          maximized
            ? "platform_window_maximized"
            : "platform_window_restored",
        );
      })
      .catch(() => {
        recordInteraction("platform_window_maximize_failed");
      });
  };

  const requestPlatformNavigation = (
    payload: PlatformNavigationPayload,
  ) => {
    void revealDedicatedPlatformWindow()
      .then(() => emit("platform-navigation", payload))
      .then(
        () =>
          new Promise<void>((resolve) => {
            window.setTimeout(resolve, 120);
          }),
      )
      .then(() => revealDedicatedPlatformWindow())
      .catch(() => {
        recordInteraction("platform_window_show_failed");
      });
  };

  const closePlatform = (
    event: ReactMouseEvent<HTMLButtonElement> | ReactPointerEvent<HTMLButtonElement>,
  ) => {
    event.stopPropagation();
    if (companionChatStateRef.current.mode === "active") {
      exitActiveCompanionChat(true, "close");
    }
    clearDefaultBubbleText();
    if (isPlatformWindow) {
      companionProviderWindowLifecycleRef.current?.stop();
      void getOptionalCurrentWindow()?.hide().catch(() => {
        recordInteraction("platform_window_hide_failed");
      });
      recordInteraction("platform_close");
      return;
    }
    setIsPlatformOpen(false);
    recordInteraction("platform_close");
  };

  const openTaskPlatform = (view: TaskListView = "today", taskId: string | null = null) => {
    if (!isPlatformWindow && isTauriRuntime()) {
      requestPlatformNavigation({
        section: "tasks",
        view,
        taskId,
      });
      recordInteraction(`task_platform_open_${view}`);
      return;
    }
    setTaskListView(view);
    setTaskDetailId(taskId);
    setPlatformSection("tasks");
    setIsQuickCreateOpen(false);
    setIsPlatformOpen(true);
    recordInteraction(`task_platform_open_${view}`);
  };

  const openTaskMenu = () => {
    const placement = chooseTaskMenuPlacement(
      petVisibleBounds,
      physicalPetPlacement.current,
      "right",
    );
    setTaskMenuPlacement(placement);
    setIsTaskMenuOpen(true);
    recordInteraction("task_context_menu_open");
  };

  const closeTaskMenu = () => {
    lastSecondaryClickAt.current = null;
    if (secondaryClickResetTimer.current !== null) {
      window.clearTimeout(secondaryClickResetTimer.current);
      secondaryClickResetTimer.current = null;
    }
    setIsTaskMenuOpen(false);
  };

  const hidePetTemporarily = () => {
    setIsTaskMenuOpen(false);
    const appWindow = getOptionalCurrentWindow();
    if (!appWindow) {
      recordInteraction("pet_temporary_hide_noop");
      return;
    }

    void appWindow.hide().then(
      () => recordInteraction("pet_temporary_hidden"),
      () => recordInteraction("pet_temporary_hide_failed"),
    );
  };

  const openQuickTaskCreate = () => {
    setIsTaskMenuOpen(false);
    if (!isPlatformWindow && isTauriRuntime()) {
      requestPlatformNavigation({ section: "quick-create" });
      recordInteraction("task_quick_create_open");
      return;
    }
    setIsPlatformOpen(false);
    setIsQuickCreateOpen(true);
    recordInteraction("task_quick_create_open");
  };

  const closeQuickTaskCreate = () => {
    setIsQuickCreateOpen(false);
    if (isPlatformWindow) {
      void getOptionalCurrentWindow()?.hide().catch(() => {
        recordInteraction("platform_window_hide_failed");
      });
    }
  };

  const createQuickTask = (draft: TaskDraft) => {
    const created = createTask(taskDatabase, draft);
    if (!commitTaskDatabase(recordTaskMetric(created.database, "quick_create_used"))) return;
    closeQuickTaskCreate();
    recordInteraction("task_quick_created");
  };

  const createHomeTask = (draft: TaskDraft) => {
    const created = createTask(taskDatabase, draft);
    if (!commitTaskDatabase(
      recordTaskMetric(created.database, "quick_create_used"),
      `已记下「${created.task.title}」`,
    )) return;
    recordInteraction("platform_home_task_created");
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
      const shownByCustomBridge = await invoke("show_care_notification", {
        kind,
        title: copy[kind].title,
        body: copy[kind].body,
      }).then(() => true).catch(() => false);
      if (shownByCustomBridge) {
        void recordInteraction("care_system_notification_shown");
        return;
      }
      let granted = await isNativeNotificationPermissionGranted().catch(() => false);
      if (!granted) granted = (await requestNativeNotificationPermission().catch(() => "denied")) === "granted";
      if (!granted) {
        void recordInteraction("care_system_notification_permission_denied");
        return;
      }
      let sent = false;
      try {
        sendNativeNotification({
          id: notificationIdForInstance(`care-${kind}`),
          ...copy[kind],
          autoCancel: true,
        });
        sent = true;
      } catch {
        sent = false;
      }
      void recordInteraction(sent ? "care_system_notification_shown" : "care_system_notification_failed");
      return;
    }
    if (!("Notification" in window)) return;
    let permission = Notification.permission;
    if (permission === "default") {
      permission = await Notification.requestPermission().catch(() => "denied" as NotificationPermission);
    }
    if (permission !== "granted") return;
    new Notification(copy[kind].title, { body: copy[kind].body, tag: `care-${kind}` });
  };

  const markProactiveTaskEngaged = (taskId: string) => {
    for (const [deliveryKey, deliveredTaskId] of proactiveDeliveryOutcomeRef.current) {
      if (deliveredTaskId === taskId) proactiveDeliveryOutcomeRef.current.delete(deliveryKey);
    }
    proactiveTriggerEngine.recordEngaged(taskId);
  };

  const completeTaskReminder = (taskId: string, instanceId: string) => {
    const next = completeReminderInstance(taskDatabase, instanceId);
    if (next === taskDatabase) return;
    if (!commitTaskDatabase(next)) return;
    markProactiveTaskEngaged(taskId);
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
    const taskId = taskDatabase.reminderInstances.find((instance) => instance.id === instanceId)?.taskId;
    if (!commitTaskDatabase(next)) return;
    if (taskId) markProactiveTaskEngaged(taskId);
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

    if (companionChatStateRef.current.mode === "active") {
      exitActiveCompanionChat(false, "pet-switch");
    }
    activePetIdRef.current = pet.id;
    saveSelectedPetId(pet.id);
    setActivePetId(pet.id);
    if (isTauriRuntime()) {
      void emit("pet-selected", { petId: pet.id });
    }
    clearDefaultBubbleText();
    if (isPlatformWindow) {
      setPlatformSection(resolvePlatformSectionAfterCompanionExit("pet-switch"));
    }
    void recordChatObservation("pet_switched");
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

  const cancelCompanionChatTurn = () => {
    const attempt = companionAttemptRef.current;
    const hadAttempt = attempt !== null;
    attempt?.controller.abort();
    companionChatAbortControllerRef.current?.abort();
    companionChatAbortControllerRef.current = null;
    const sessionId = companionSessionIdRef.current;
    if (sessionId) {
      companionAppHarness.harness.cancel(sessionId, attempt?.requestId);
    }
    companionAttemptRef.current = null;
    companionConfirmationPendingRef.current = false;
    if (hadAttempt) {
      void recordChatObservation("chat_turn_cancelled", {
        cancelled: true,
        lateDiscarded: true,
      });
    }
  };

  useEffect(() => () => {
    cancelCompanionChatTurn();
  }, []);

  const notifyCompanionChatOpened = () => {
    if (!isTauriRuntime()) return;
    void emit(COMPANION_CHAT_OPENED_EVENT, {
      surface: companionChatSurface,
    } satisfies CompanionChatSurfacePayload).catch(() => {});
  };

  const resolveCompanionProviderCredentialForAction = async (
    input: CompanionProviderSettings,
    suppliedCredential?: string,
  ): Promise<string | null> => {
    const settings = normalizeCompanionProviderSettings(input);
    if (isLocalCompanionProviderProtocol(settings.protocol)) return null;
    if (suppliedCredential?.trim()) return suppliedCredential.trim();
    if (!settings.credentialConfigured) return null;
    return readCompanionProviderCredential(settings);
  };

  const loadCompanionProviderDraft = async (
    provider: CompanionProviderId,
    current: CompanionProviderSettings,
  ): Promise<CompanionProviderSettings> => {
    await waitForCompanionProviderState();
    const preset = getCompanionProviderProfilePreset(provider);
    const next = normalizeCompanionProviderSettings(
      preset
        ? { ...preset, fallbackToLocal: current.fallbackToLocal }
        : {
            ...current,
            id: provider,
            credentialRef: provider === "local" ? null : provider,
          },
    );
    const credential = await readCompanionProviderCredential(next);
    return {
      ...next,
      credentialConfigured: Boolean(credential),
    };
  };

  const saveCompanionUserProfile = async (
    input: CompanionUserProfile,
  ): Promise<CompanionUserProfileActionResult> => {
    const profile = normalizeCompanionUserProfile(input);
    const validationError = validateCompanionUserProfile(profile);
    if (validationError) return { ok: false, message: validationError };

    const current = companionUserSettingsRepository.getSnapshot();
    if (!current) {
      return { ok: false, message: "本机设置当前不可读取，已保留原资料；请重新读取后再保存。" };
    }
    const result = await companionUserSettingsRepository.updateProfile(
      {
        nickname: profile.nickname,
        gender: profile.gender,
        email: profile.email,
        phone: profile.phone,
      },
      {
        expectedGeneration: current.generation,
        expectedRevision: current.revision,
        expectedOwnerEpoch: current.ownerEpoch,
        expectedStateSeq: current.stateSeq,
        expectedDataRevision: current.dataRevision,
      },
      `settings-profile:${Date.now()}`,
    );
    if (!result.ok) {
      const message = result.reason === "stale-revision"
        ? "设置已在另一个窗口更新，请重新读取后再保存。"
        : result.reason === "not-ready"
        || result.reason === "recovery-blocked"
        || result.reason === "owner-unavailable"
        || result.reason === "bridge-timeout"
        || result.reason === "read-failed"
        || result.reason === "invalid-storage"
        ? "本机设置当前不可读取，已保留原资料；请重新读取后再保存。"
        : "个人信息暂时没有保存成功，请稍后再试。";
      return { ok: false, message };
    }
    companionUserProfileRef.current = result.snapshot.profile;
    companionPreferencesRef.current = result.snapshot.preferences;
    setCompanionUserProfile(result.snapshot.profile);
    setCompanionSettingsInitialization({
      status: "ready",
      snapshot: result.snapshot,
      generation: result.generation,
      revision: result.revision,
      ownerEpoch: result.ownerEpoch,
      stateSeq: result.stateSeq,
      dataRevision: result.dataRevision,
      issuedAt: companionSettingsInitialization.status === "ready"
        ? companionSettingsInitialization.issuedAt
        : Date.now(),
    });
    if (!result.applied && current.profile.email === profile.email && current.profile.phone === profile.phone) {
      return { ok: true, message: "个人信息没有新的变化。" };
    }
    return { ok: true, message: "个人信息已保存在本机。" };
  };

  const saveCompanionProviderSettings = async (
    input: CompanionProviderSettings,
    suppliedCredential?: string,
  ): Promise<CompanionProviderActionResult> => {
    await waitForCompanionProviderState();
    try {
      const settings = normalizeCompanionProviderSettings(input);
      const credential = await resolveCompanionProviderCredentialForAction(
        settings,
        suppliedCredential,
      );
      const validationError = validateCompanionProviderSettings(settings, credential);
      if (validationError) return { ok: false, message: validationError };
      if (!(await writeCompanionProviderSettingsWithSecureStore(settings, { credential }))) {
        return { ok: false, message: "系统安全存储暂时不可用，凭据没有保存好。" };
      }

      const saved = { ...settings, credentialConfigured: Boolean(credential) };
      const sync = companionProviderSyncRef.current;
      if (sync) {
        sync.applyLocalState({ settings: saved, credential });
        void sync.publishChange().catch(() => {});
      } else {
        companionProviderCredentialRef.current = credential;
        companionProviderSettingsRef.current = saved;
        cancelCompanionChatTurn();
        setCompanionProviderSettings(saved);
        setCompanionChatProviderInfo(getCompanionProviderStatusInfo(saved));
      }
      recordInteraction("companion_provider_saved");
      return {
        ok: true,
        message: `已保存并使用${getCompanionProviderLabel(saved.id, saved.displayName)}。`,
      };
    } catch {
      return { ok: false, message: "系统安全存储暂时不可用，凭据没有保存好。" };
    }
  };

  const clearCompanionProviderApiKey = async (
    input: CompanionProviderSettings,
  ): Promise<CompanionProviderActionResult> => {
    await waitForCompanionProviderState();
    const settings = normalizeCompanionProviderSettings(input);
    if (isLocalCompanionProviderProtocol(settings.protocol)) {
      return { ok: true, message: "本地陪伴不需要 API Key。" };
    }

    try {
      if (!(await clearCompanionProviderCredentialWithSecureStore(settings))) {
        return { ok: false, message: "系统安全存储不可用，凭据没有清除好。" };
      }
      const cleared = normalizeCompanionProviderSettings({
        ...settings,
        credentialConfigured: false,
      });
      const sync = companionProviderSyncRef.current;
      if (sync) {
        sync.applyLocalState({ settings: cleared, credential: null });
        void sync.publishChange().catch(() => {});
      } else {
        companionProviderCredentialRef.current = null;
        companionProviderSettingsRef.current = cleared;
        cancelCompanionChatTurn();
        setCompanionProviderSettings(cleared);
        setCompanionChatProviderInfo(getCompanionProviderStatusInfo(cleared));
      }
      recordInteraction("companion_provider_key_cleared");
      return {
        ok: true,
        message: `已清除${getCompanionProviderLabel(settings.id, settings.displayName)}的 API Key。`,
      };
    } catch {
      return { ok: false, message: "系统安全存储不可用，凭据没有清除好。" };
    }
  };

  const fetchCompanionProviderModelsForSettings = async (
    input: CompanionProviderSettings,
    suppliedCredential?: string,
  ): Promise<CompanionProviderModelsActionResult> => {
    let requestUrl: string | null = null;
    try {
      await waitForCompanionProviderState();
      const settings = normalizeCompanionProviderSettings(input);
      const credential = await resolveCompanionProviderCredentialForAction(
        settings,
        suppliedCredential,
      );
      const validationError = validateCompanionProviderSettings(
        settings,
        credential,
        { allowEmptyModel: true },
      );
      if (validationError) return { ok: false, message: validationError };
      requestUrl = getCompanionProviderModelListUrl(settings);
      const result = await fetchUpstreamCompanionProviderModels(settings, credential);
      recordInteraction("companion_provider_models_fetched");
      return {
        ok: true,
        message: `已从 ${requestUrl} 获取 ${result.models.length} 个模型，请选择后保存。`,
        models: result.models,
      };
    } catch (error) {
      if (error instanceof ProviderAdapterError) {
        const target = requestUrl ? `（目标地址：${requestUrl}）` : "";
        const status = error.status ? ` HTTP ${error.status}` : "";
        return { ok: false, message: `${error.userMessage}${status}${target}` };
      }
      return {
        ok: false,
        message: requestUrl
          ? `上游模型列表暂时没有获取成功（目标地址：${requestUrl}），请检查 Endpoint 和网络。`
          : "上游模型列表暂时没有获取成功，请检查 Endpoint 和网络。",
      };
    }
  };

  const testCompanionProvider = async (
    input: CompanionProviderSettings,
    suppliedCredential?: string,
  ): Promise<CompanionProviderActionResult> => {
    try {
      await waitForCompanionProviderState();
      const settings = normalizeCompanionProviderSettings(input);
      const credential = await resolveCompanionProviderCredentialForAction(
        settings,
        suppliedCredential,
      );
      const validationError = validateCompanionProviderSettings(settings, credential);
      if (validationError) return { ok: false, message: validationError };
      if (settings.protocol === "local") {
        return { ok: true, message: "本地陪伴可用，不需要网络连接。" };
      }

      const config = resolveCompanionChatPackage(getCompanionChatPackageForPet(activePetId));
      const provider = createCompanionChatProvider(config, {
        profile: settings,
        credential,
      });
      await provider.send({
        petId: activePetId,
        text: "请只回复“连接成功”。",
      });
      return {
        ok: true,
        message: `${getCompanionProviderLabel(settings.id, settings.displayName)}连接成功，可以开始聊天了。`,
      };
    } catch (error) {
      return {
        ok: false,
        message: error instanceof CompanionChatProviderError
          ? error.userMessage
          : "聊天服务暂时没接上，请检查 API Endpoint 和网络连接。",
      };
    }
  };

  const openCompanionChat = async () => {
    await waitForCompanionProviderState();
    if (companionChatStateRef.current.mode === "active") {
      notifyCompanionChatOpened();
      recordInteraction("companion_chat_open");
      return;
    }
    lastSecondaryClickAt.current = null;
    if (secondaryClickResetTimer.current !== null) {
      window.clearTimeout(secondaryClickResetTimer.current);
      secondaryClickResetTimer.current = null;
    }
    companionSessionIdRef.current = `companion-session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setIsTaskMenuOpen(false);
    // A new active companionship starts a fresh bounded Provider context. The
    // previous record is read-only UI state and is intentionally not restored.
    const config = resolveCompanionChatPackage(getCompanionChatPackageForPet(activePetId));
    commitCompanionChatState(enterCompanionChat(config));
    setCompanionChatProviderInfo(getCompanionProviderStatusInfo(companionProviderSettingsRef.current));
    notifyCompanionChatOpened();
    recordInteraction("companion_chat_open");
  };

  const openPlatformCompanionChat = async () => {
    await openCompanionChat();
    setPlatformSection("chat");
  };

  const stopCompanionChatReply = () => {
    if (companionAttemptRef.current) {
      void recordChatObservation("chat_stop_clicked", { cancelled: true });
    }
    cancelCompanionChatTurn();
    commitCompanionChatState((current) => stopCompanionReply(current));
    recordInteraction("companion_chat_stop");
  };

  const updateCompanionDraftText = (draft: string) => {
    commitCompanionChatState((current) => updateCompanionDraft(current, draft));
  };

  const sendCompanionChatMessage = (stateOverride?: CompanionChatState) => {
    const petId = activePetIdRef.current;
    const stateForSend = stateOverride ?? companionChatStateRef.current;
    const currentState = stateForSend.mode === "active"
      && !stateOverride
      && isExplicitCompanionTopicChange(stateForSend.draft)
      ? startCompanionContextEpoch(stateForSend)
      : stateForSend;
    const sent = sendCompanionMessage(currentState);
    commitCompanionChatState(sent);
    if (sent.mode !== "active" || !sent.pendingUserMessage) return;

    const { id, text } = sent.pendingUserMessage;
    const sessionId = companionSessionIdRef.current;
    if (!sessionId) return;
    const requestId = `companion-request-${Date.now()}-${++companionRequestSequenceRef.current}`;
    const abortController = new AbortController();
    const input = {
      requestId,
      sessionId,
      sourceMessageId: id,
      userId: COMPANION_LOCAL_USER_ID,
      petId,
      message: text,
      currentTime: new Date().toISOString(),
      timezone: (() => {
        try {
          return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
        } catch {
          return "UTC";
        }
      })(),
      utcOffsetMinutes: -new Date().getTimezoneOffset(),
      source: "chat" as const,
      contextEpoch: sent.contextEpoch,
      signal: abortController.signal,
    };
    companionAttemptRef.current = {
      sessionId,
      requestId,
      sourceMessageId: id,
      petId,
      controller: abortController,
    };
    companionChatAbortControllerRef.current = abortController;
    void recordChatObservation("chat_request_started");
    window.setTimeout(() => {
      if (
        activePetIdRef.current !== petId ||
        companionChatStateRef.current.mode !== "active" ||
        companionChatStateRef.current.pendingRequestId !== id
        || companionSessionIdRef.current !== sessionId
        || companionAttemptRef.current?.requestId !== requestId
      ) {
        return;
      }
      void waitForCompanionProviderState().then(() => {
        if (
          activePetIdRef.current !== petId ||
          companionChatStateRef.current.mode !== "active" ||
          companionChatStateRef.current.pendingRequestId !== id ||
          companionSessionIdRef.current !== sessionId ||
          companionAttemptRef.current?.requestId !== requestId
        ) {
          return;
        }
        return companionAppHarness.harness.respond(input);
      }).then((response) => {
        if (!response) return;
        if (companionAttemptRef.current?.requestId === requestId) {
          companionAttemptRef.current = null;
        if (companionChatAbortControllerRef.current === abortController) {
            companionChatAbortControllerRef.current = null;
          }
        }
        if (response.status === "discarded" || response.error?.kind === "stale-turn") {
          void recordChatObservation("chat_result_discarded", {
            callCount: response.callCounts.model,
            commitCount: 0,
            lateDiscarded: true,
          });
          return;
        }
        if (response.status !== "error" || response.error?.kind === "cancelled") {
          return;
        }
        if (
          activePetIdRef.current !== petId
          || companionSessionIdRef.current !== sessionId
          || companionChatStateRef.current.mode !== "active"
          || companionChatStateRef.current.pendingRequestId !== id
        ) return;
        setCompanionChatProviderInfo(response.provider);
        const message = response.error?.message ?? "聊天服务暂时没接上，稍后再试。";
        commitCompanionChatState((current) =>
          current.mode === "active" && current.pendingRequestId === id
            ? receiveCompanionReply(current, message, Date.now(), "error")
            : current,
        );
      }).catch(() => {
        if (
          activePetIdRef.current !== petId
          || companionSessionIdRef.current !== sessionId
          || companionChatStateRef.current.mode !== "active"
          || companionChatStateRef.current.pendingRequestId !== id
          || abortController.signal.aborted
        ) return;
        commitCompanionChatState((current) =>
          current.mode === "active" && current.pendingRequestId === id
            ? receiveCompanionReply(current, "聊天服务暂时没接上，稍后再试。", Date.now(), "error")
            : current,
        );
      });
    }, 240);
  };

  const retryCompanionChatMessage = () => {
    const retried = retryCompanionMessage(companionChatStateRef.current);
    if (retried.mode !== "active" || !retried.pendingUserMessage) return;
    sendCompanionChatMessage(retried);
    recordInteraction("companion_chat_retry");
  };

  const exitActiveCompanionChat = (
    returnToHome = isPlatformWindow,
    reason: CompanionExitReason = "return",
  ) => {
    cancelCompanionChatTurn();
    const exited = exitCompanionTaskChat(
      companionChatStateRef.current,
      null,
    );
    commitCompanionChatState(exited.state);
    companionSessionIdRef.current = null;
    setCompanionChatProviderInfo(
      getCompanionProviderStatusInfo(companionProviderSettingsRef.current),
    );
    clearDefaultBubbleText();
    if (returnToHome && isPlatformWindow) {
      setPlatformSection(resolvePlatformSectionAfterCompanionExit(reason));
    }
  };

  useEffect(() => {
    if (!isTauriRuntime()) return undefined;

    const unlistenPromise = listenToAppEvent<CompanionChatSurfacePayload>(
      COMPANION_CHAT_OPENED_EVENT,
      ({ surface }) => {
        if (
          surface === companionChatSurface ||
          companionChatStateRef.current.mode !== "active"
        ) {
          return;
        }

        exitActiveCompanionChat(true, "mutual-surface");
      },
    );

    return () => {
      void unlistenPromise.then((unlisten) => unlisten());
    };
  }, [companionChatSurface, isPlatformWindow]);

  const closePlatformCompanionChatPage = () => {
    exitActiveCompanionChat(true, "back");
  };

  const navigatePlatformSection = (section: PlatformSection) => {
    if (section !== "chat" && companionChatStateRef.current.mode === "active") {
      // The requested destination owns the navigation state; the active chat
      // must still be torn down before rendering that destination.
      exitActiveCompanionChat(false, "navigation");
      setPlatformSection(
        resolvePlatformSectionAfterCompanionExit("navigation", section),
      );
      return;
    }
    setPlatformSection(section);
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

  const updateBubbleAfterPetMovement = () => {
    clearTransientBubbleTimer();
    setBubbleText((currentText) =>
      getBubbleTextAfterPetMovement(
        currentText,
        careReminderPromptRef.current !== null,
      ),
    );
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
      if (event.key === "Escape") exitActiveCompanionChat(true, "escape");
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [companionChatState.mode]);

  useEffect(() => {
    if (!isTaskMenuOpen) return undefined;
    const close = (event: PointerEvent) => {
      const target = event.target instanceof Element ? event.target : null;
      if (!target?.closest(".pet-task-menu")) closeTaskMenu();
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeTaskMenu();
    };
    window.addEventListener("pointerdown", close);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("pointerdown", close);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [isTaskMenuOpen]);

  useEffect(() => {
    if (companionChatState.mode !== "active") return undefined;

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest(".companion-chat,.platform-companion-chat-record-backdrop,.platform-companion-chat-record-drawer,.platform-companion-chat-room,.platform-companion-chat-room-shell,.pet-hit-area,.pet-canvas")) return;
      exitActiveCompanionChat(true, "outside");
    };

    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [companionChatState.mode]);

  useEffect(() => {
    if (companionChatState.mode !== "active") return undefined;

    const timer = window.setInterval(() => {
      const exited = autoExitCompanionTaskChat(
        companionChatStateRef.current,
        null,
      );
      if (!exited.exited) return;
      exitActiveCompanionChat(true, "idle");
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
    broadcastCareReminderState();
    setCareReminderScheduleRevision((revision) => revision + 1);
  };

  const reopenTimedCareReminder = (deliveredKey: string) => {
    const nextDeliveredKeys = unmarkCareReminderDelivered(
      careReminderState.current.deliveredKeys,
      deliveredKey,
    );
    careReminderState.current = { ...careReminderState.current, deliveredKeys: nextDeliveredKeys };
    writeCareReminderState(careReminderState.current);
    broadcastCareReminderState();
    setCareReminderScheduleRevision((revision) => revision + 1);
  };

  const saveCareReminderSettings = (settings: CareReminderSettingsValue) => {
    const now = Date.now();
    careReminderState.current = {
      ...careReminderState.current,
      settings,
      nextWellnessTime: now + settings.wellness.intervalMinutes * 60 * 1000,
    };
    writeCareReminderState(careReminderState.current);
    setCareReminderSettings(settings);
    nextWellnessTime.current = now + settings.wellness.intervalMinutes * 60 * 1000;
    setCareReminderScheduleRevision((revision) => revision + 1);
    broadcastCareReminderState();
    recordInteraction("care_reminder_settings_updated");
  };

  const dismissCareReminderDisableNotice = () => {
    careReminderState.current = { ...careReminderState.current, systemPopupNoticeDismissed: true };
    writeCareReminderState(careReminderState.current);
    setCareReminderNoticeDismissed(true);
    commitMailboxState((state) => receiveLetter(state, CARE_REMINDER_LETTER_ID));
    broadcastCareReminderState();
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

  const releaseDragHoverSuppression = () => {
    if (dragHoverSuppressionTimer.current !== null) {
      window.clearTimeout(dragHoverSuppressionTimer.current);
      dragHoverSuppressionTimer.current = null;
    }
    hoverSuppressedByDrag.current = false;
  };

  const holdHoverAfterDrag = () => {
    if (dragHoverSuppressionTimer.current !== null) {
      window.clearTimeout(dragHoverSuppressionTimer.current);
    }
    hoverSuppressedByDrag.current = true;
    dragHoverSuppressionTimer.current = window.setTimeout(() => {
      dragHoverSuppressionTimer.current = null;
      hoverSuppressedByDrag.current = false;
    }, 1400);
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
  ): PetDirectionMode | "mirror-right" | "none" => {
    const resolved = getActiveInteractionManifest();
    if (!resolved) return "none";
    if (
      name === resolved.idle.animation &&
      idleFollowsDragDirection.current &&
      resolved.drag.landingIdleFollowsDragDirection === true
    ) {
      return "mirror-right";
    }
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

  const getDragFrameOffsetY = (
    sprite: AnimatedSprite,
    name: AnimationName,
    scaleY: number,
  ) => {
    const resolved = getActiveInteractionManifest();
    const frameOffsets = resolved?.drag.frameOffsetY;
    const startFrame = dragTextureStartFrame.current;
    if (
      !frameOffsets ||
      startFrame === null ||
      (name !== resolved?.drag.left && name !== resolved?.drag.right)
    ) {
      return 0;
    }

    const localFrame = Math.max(0, Math.floor(sprite.currentFrame));
    const globalFrame = startFrame + localFrame;
    return (frameOffsets[globalFrame] ?? 0) * scaleY;
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

  const playAnimation = (name: AnimationName, startFrame = 0) => {
    const sprite = spriteRef.current;
    const animations = animationsRef.current;
    const spec = getAnimationSpec(name);
    if (!sprite || !animations || !spec || !animations[name]) return false;

    const resolved = getActiveInteractionManifest();
    if (name !== resolved?.idle.animation) {
      idleFollowsDragDirection.current = false;
    }

    dragTextureStartFrame.current = null;
    currentAnimation.current = name;
    markAnimationState(name);
    sprite.onComplete = undefined;
    sprite.textures = animations[name];
    sprite.animationSpeed = spec.speed;
    sprite.loop = spec.loop;
    applySpriteVisual(sprite, name);
    const firstFrame = Math.max(0, Math.min(startFrame, animations[name].length - 1));
    sprite.gotoAndPlay(firstFrame);
    return true;
  };

  const playIdleAnimation = (
    startFrame = 0,
    followDragDirection = false,
  ) => {
    const resolved = getActiveInteractionManifest();
    const idleAnimation = resolved?.idle.animation ?? "idle";
    idleFollowsDragDirection.current =
      followDragDirection &&
      resolved?.drag.landingIdleFollowsDragDirection === true;
    playAnimation(idleAnimation, startFrame);
  };

  const scheduleReturnToIdle = (
    returnAfterMs: number | undefined,
    resumeHoverAfterReturn = true,
    expectedToken = playbackToken.current,
    idleStartFrame = 0,
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
      playIdleAnimation(idleStartFrame);
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

  const queueProactiveDelivery = (
    decision: ProactiveTriggerDecision,
    candidates: ProactiveTaskCandidate[],
  ) => {
    const taskIds = decision.aggregatedTaskIds ?? [decision.taskId];
    const key = `${decision.candidateKey}:${taskIds.join("|")}`;
    if (pendingProactiveDeliveryKeysRef.current.has(key)) return;
    pendingProactiveDeliveryKeysRef.current.add(key);
    pendingProactiveDeliveriesRef.current.push({ key, decision, candidates });
  };

  const recordProactiveDeliveryOutcome = (
    deliveryKey: string,
    delivery: ProactiveTaskDelivery,
  ) => {
    for (const taskId of delivery.taskIds) {
      const outcomeKey = `${deliveryKey}:${taskId}`;
      proactiveDeliveryOutcomeRef.current.set(outcomeKey, taskId);
      window.setTimeout(() => {
        if (proactiveDeliveryOutcomeRef.current.get(outcomeKey) !== taskId) return;
        proactiveDeliveryOutcomeRef.current.delete(outcomeKey);
        proactiveTriggerEngine.recordIgnored(taskId);
      }, delivery.durationMs);
    }
  };

  const flushProactiveDeliveries = () => {
    if (isPlatformWindow || isPlatformOpen || isQuickCreateOpen || isTaskMenuOpen) return;

    while (pendingProactiveDeliveriesRef.current.length > 0) {
      const queued = pendingProactiveDeliveriesRef.current[0];
      const route = planProactiveTaskDeliveryRoute(
        queued.decision,
        activePetId,
        availablePetIds,
      );
      if (route.status === "unavailable") {
        pendingProactiveDeliveriesRef.current.shift();
        pendingProactiveDeliveryKeysRef.current.delete(queued.key);
        recordInteraction("task_proactive_delivery_unavailable");
        continue;
      }
      if (route.status === "switch") {
        const targetPet = petCatalog.find((pet) => pet.id === route.targetPetId);
        if (!targetPet) return;
        selectPet(targetPet);
        recordInteraction("task_proactive_pet_switch");
        return;
      }

      const resolved = getActiveInteractionManifest();
      if (!resolved || !animationsRef.current) return;
      const resolvedDelivery = resolveProactiveTaskDelivery(
        queued.decision,
        queued.candidates,
        petTaskFeedbackById[route.targetPetId],
      );
      if (!canRenderProactiveTaskDelivery(resolvedDelivery, activePetId)) return;

      pendingProactiveDeliveriesRef.current.shift();
      pendingProactiveDeliveryKeysRef.current.delete(queued.key);
      playTaskFeedback(
        resolvedDelivery.scene,
        resolvedDelivery.text,
        resolved.reminders.eyeCare,
      );
      recordProactiveDeliveryOutcome(queued.key, resolvedDelivery);
    }
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
      hoverSuppressedByDrag.current ||
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

      // A drag can finish while the pointer is still over the moving pet
      // window. Re-check the suppression at execution time so a timer that
      // raced with drag start cannot interrupt landing with hover fish.
      // The press may still be below the drag threshold. Treat any active
      // pointer as a drag candidate so a pre-existing hover timer cannot
      // fire between pointer-down and the first drag move.
      const activePointer = pointerState.current;
      if (hoverSuppressedByDrag.current || activePointer) return;

      if (
        shouldTriggerHoverEat({
          hoverStartedAt: startedAt,
          now: Date.now(),
          isDragging: false,
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

    const hasTakeoffRange =
      drag.takeoffStartFrame !== undefined &&
      drag.takeoffFrameCount !== undefined;
    const hasTakeoffFrame = drag.takeoffFrame !== undefined;
    const hasLandingRange =
      drag.landingStartFrame !== undefined &&
      drag.landingFrameCount !== undefined;
    const hasLandingFrames =
      drag.landingApproachFrame !== undefined &&
      drag.landingFrame !== undefined;
    const hasPlan =
      (hasTakeoffRange || hasTakeoffFrame) &&
      drag.loopStartFrame !== undefined &&
      drag.loopFrameCount !== undefined &&
      (hasLandingRange || hasLandingFrames);
    if (!hasPlan) return null;

    const takeoffFrames = hasTakeoffRange
      ? frames.slice(
          drag.takeoffStartFrame!,
          drag.takeoffStartFrame! + drag.takeoffFrameCount!,
        )
      : [frames[drag.takeoffFrame!]];
    const loopFrames = frames.slice(
      drag.loopStartFrame!,
      drag.loopStartFrame! + drag.loopFrameCount!,
    );
    const landingFrames = hasLandingRange
      ? frames.slice(
          drag.landingStartFrame!,
          drag.landingStartFrame! + drag.landingFrameCount!,
        )
      : [
          frames[drag.landingApproachFrame!],
          frames[drag.landingFrame!],
        ];

    if (
      takeoffFrames.some((frame) => frame === undefined) ||
      loopFrames.length !== drag.loopFrameCount ||
      landingFrames.length === 0 ||
      landingFrames.some((frame) => frame === undefined)
    ) {
      return null;
    }

    return {
      takeoffFrames: takeoffFrames as Texture[],
      loopFrames,
      frames,
      landingFrames: landingFrames as Texture[],
      landingTransitionSpeed: drag.landingTransitionSpeed ?? 0.25,
      landingHoldMs: drag.landingHoldMs ?? 900,
      landingEndsOnIdleFirst: drag.landingEndsOnIdleFirst ?? false,
      landingIdleStartFrame: drag.landingIdleStartFrame,
      landingIdleFollowsDragDirection:
        drag.landingIdleFollowsDragDirection ?? false,
    };
  };

  const playDragLoopAnimation = (
    animationName: AnimationName,
    includeTakeoff: boolean,
  ) => {
    const sprite = spriteRef.current;
    const resolved = getActiveInteractionManifest();
    const plan = getDragFramePlan(animationName);
    const spec = getAnimationSpec(animationName);
    if (!resolved || !sprite || !plan || !spec) {
      playAnimation(animationName);
      return;
    }

    currentAnimation.current = animationName;
    markAnimationState(animationName);
    const previousTextureCount = sprite.textures.length;
    const previousFrame = sprite.currentFrame;
    const dragTextureStart = includeTakeoff
      ? resolved.drag.takeoffStartFrame ?? 0
      : resolved.drag.loopStartFrame ?? plan.takeoffFrames.length;
    dragTextureStartFrame.current = dragTextureStart;
    const loopStartFrame = includeTakeoff
      ? 0
      : resolveDragLoopFrameIndex(
          previousFrame,
          previousTextureCount,
          plan.takeoffFrames.length,
          plan.loopFrames.length,
        );
    sprite.onComplete = undefined;
    sprite.textures = includeTakeoff
      ? [...plan.takeoffFrames, ...plan.loopFrames]
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
          dragTextureStartFrame.current =
            resolved.drag.loopStartFrame ?? plan.takeoffFrames.length;
          sprite.gotoAndPlay(0);
        }
      : undefined;
    sprite.gotoAndPlay(loopStartFrame);
  };

  const playDragStartInteraction = () => {
    const resolved = getActiveInteractionManifest();
    if (!resolved) return;

    playbackToken.current += 1;

    if (returnToIdleTimer.current !== null) {
      window.clearTimeout(returnToIdleTimer.current);
      returnToIdleTimer.current = null;
    }

    updateBubbleAfterPetMovement();
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

    const idleAnimation = getAnimationSpec(resolved.idle.animation);
    const idleStartFrame = resolveDragLandingIdleStartFrame(
      plan.landingEndsOnIdleFirst,
      idleAnimation?.frames ?? 0,
      plan.landingIdleStartFrame,
    );

    currentAnimation.current = animationName;
    markAnimationState(animationName);
    sprite.onComplete = undefined;
    sprite.textures = plan.landingFrames;
    sprite.animationSpeed = plan.landingTransitionSpeed;
    sprite.loop = false;
    dragTextureStartFrame.current =
      resolved.drag.landingStartFrame ??
      resolved.drag.landingApproachFrame ??
      (resolved.drag.loopStartFrame ?? plan.takeoffFrames.length) +
        plan.loopFrames.length;
    applySpriteVisual(sprite, animationName);
    // The landing bridge ends on the same visual scale as idle. This keeps
    // the final landing texture and idle's first texture on one render scale.
    applySpriteVisual(sprite, resolved.idle.animation);
    sprite.onComplete = () => {
      if (
        spriteRef.current !== sprite ||
        currentAnimation.current !== animationName ||
        token !== playbackToken.current
      ) {
        return;
      }
      sprite.onComplete = undefined;
      if (shouldReturnToIdleImmediatelyAfterDragLanding(plan.landingHoldMs)) {
        if (!careReminderPromptRef.current) {
          clearDefaultBubbleText();
        }
        playIdleAnimation(
          idleStartFrame,
          plan.landingIdleFollowsDragDirection,
        );
        // Do not treat the release pointer, which is still over the pet
        // window, as a fresh hover. A real leave/re-enter can schedule it.
        return;
      }
      scheduleReturnToIdle(plan.landingHoldMs, true, token, idleStartFrame);
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
      if (dragHoverSuppressionTimer.current !== null) {
        window.clearTimeout(dragHoverSuppressionTimer.current);
        dragHoverSuppressionTimer.current = null;
      }
      hoverSuppressedByDrag.current = true;
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

    const currentPlacement = physicalPetPlacement.current;
    if (currentPlacement) {
      physicalPetPlacement.current = {
        anchor: getPhysicalPetAnchor(
          position,
          petViewportRef.current,
          pointer.scaleFactor,
        ),
        scaleFactor: pointer.scaleFactor,
        workArea: currentPlacement.workArea,
      };
    }

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
    // Moving the transparent window causes a leave/enter pair while the
    // release pointer is still over the pet. Keep hover actions out of the
    // zero-hold landing bridge until that transient window movement settles.
    holdHoverAfterDrag();
    playDragEndInteraction();
    // The periodic probe is sufficient after a drag. Running an immediate
    // probe here can move/resize the pet window while landing is still
    // visible and turns release into a desktop-icon interaction.
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
      finishPress("pointer");
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
    if (pointerState.current?.source === "pointer") {
      if (!isPrimaryButtonPressed(event.buttons)) {
        finishPress("pointer");
        return;
      }

      if (!shouldUseMouseFallback()) return;
      movePress(event.clientX, event.clientY, event.screenX, event.screenY);
      return;
    }

    if (
      pointerState.current?.source === "mouse" &&
      !isPrimaryButtonPressed(event.buttons)
    ) {
      finishPress("mouse");
      return;
    }
    movePress(event.clientX, event.clientY, event.screenX, event.screenY);
  };

  const handleMouseUp = () => {
    if (pointerState.current?.source === "pointer") {
      if (shouldUseMouseFallback()) finishPress("pointer");
      return;
    }

    if (!shouldUseMouseFallback() && pointerState.current?.source !== "mouse") return;
    finishPress("mouse");
  };

  const handleContextMenu = (event: ReactMouseEvent<HTMLElement>) => {
    event.preventDefault();
    event.stopPropagation();
    if (companionChatStateRef.current.mode === "active") return;

    const secondaryClick = registerSecondaryClick(
      lastSecondaryClickAt.current,
      Date.now(),
    );
    if (secondaryClickResetTimer.current !== null) {
      window.clearTimeout(secondaryClickResetTimer.current);
      secondaryClickResetTimer.current = null;
    }
    if (secondaryClick.triggered) {
      lastSecondaryClickAt.current = null;
      openCompanionChat();
      return;
    }
    lastSecondaryClickAt.current = secondaryClick.lastClickAt;
    secondaryClickResetTimer.current = window.setTimeout(() => {
      lastSecondaryClickAt.current = null;
      secondaryClickResetTimer.current = null;
    }, SECONDARY_DOUBLE_CLICK_MS);
    openTaskMenu();
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
    updateBubbleAfterPetMovement();
    playIdleAnimation();
  };

  const handleLostPointerCapture = () => {
    markPointerEvent();
    if (pointerState.current?.source !== "pointer") return;

    finishPress("pointer");
  };

  const scheduleNextRandomCareReminder = (nowTimestamp: number) => {
    const setting = careReminderState.current.settings.wellness;
    const nextTime = nowTimestamp + setting.intervalMinutes * 60 * 1000;
    nextWellnessTime.current = nextTime;
    careReminderState.current = {
      ...careReminderState.current,
      nextWellnessTime: nextTime,
    };
    writeCareReminderState(careReminderState.current);
    broadcastCareReminderState();
    setCareReminderScheduleRevision((revision) => revision + 1);
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
    if (isPlatformWindow) return;
    const scan = () => {
      const stored = readTaskDatabase();
      const timezoneAdjusted = reconcileTaskTimezone(stored);
      const aged = markUnattendedReminders(timezoneAdjusted, new Date(), timezoneAdjusted.settings.bubbleDurationMinutes * 60 * 1000);
      const result = triggerDueReminders(aged);
      const deliverProactiveCandidates = (candidates: ReturnType<typeof createProactiveTaskCandidate>[]) => {
        if (isPlatformOpen || isQuickCreateOpen || candidates.length === 0 || !activePetManifest) return;
        // Formal task reminders keep their existing native/stack delivery below.
        // The engine owns only the additional proactive pet expression channel.
        const proactive = proactiveTriggerEngine.evaluate(candidates);
        for (const delivery of proactive.deliveries) {
          queueProactiveDelivery(delivery.decision, delivery.candidates);
        }
        flushProactiveDeliveries();
      };
      if (result.triggered.length === 0) {
        let persisted = true;
        if (aged !== stored) {
          persisted = writeTaskDatabase(aged);
          if (persisted) setTaskDatabase(aged);
        }
        if (!persisted) return;
        deliverProactiveCandidates(selectProactiveTaskCandidates(aged));
        return;
      }
      if (!writeTaskDatabase(result.database)) return;
      setTaskDatabase(result.database);

      const shouldSummarize = result.triggered.length > 1
        && result.triggered.every(({ instance }) => instance.status === "missed");
      if (shouldSummarize) {
        void showSystemTaskSummaryNotification(result.triggered.length);
      } else {
        for (const due of result.triggered) void showSystemTaskNotification(due);
      }
      playTaskNotificationSound();
      deliverProactiveCandidates(result.triggered.map((due) => createProactiveTaskCandidate(due)));
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
  }, [activePetId, activePetManifest, isPlatformOpen, isPlatformWindow, isQuickCreateOpen, petTaskFeedbackById, proactiveTriggerEngine, taskDatabase.settings.notificationSound, taskDatabase.settings.customNotificationSoundDataUrl]);

  useEffect(() => {
    flushProactiveDeliveries();
  }, [activePetId, availablePetIds, isPlatformOpen, isPlatformWindow, isQuickCreateOpen, isTaskMenuOpen, petTaskFeedbackById]);

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
    // A zero-hold drag landing has no returnToIdleTimer. Keep the desktop-icon
    // probe out of that short release window as well, otherwise an async probe
    // can replace the landing animation before it reaches canonical idle.
    if (hoverSuppressedByDrag.current) return;
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
        // The probe may have started just before a drag. Re-check the drag
        // release suppression before allowing its async result to interrupt
        // the landing bridge.
        if (
          hoverSuppressedByDrag.current ||
          pointerState.current?.dragging ||
          returnToIdleTimer.current !== null
        ) {
          return;
        }
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
    if (isPlatformWindow) return;
    const host = pixiHost.current;
    const manifest = activePetManifest;
    if (!host || !manifest) return;

    let disposed = false;
    let initialized = false;
    let destroyed = false;
    const app = new Application();
    const getCanvasOrigin = (petViewport: PetViewport): WindowPosition =>
      isTauriRuntime()
        ? { x: host.offsetLeft, y: host.offsetTop }
        : { x: petViewport.x, y: petViewport.y };

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

        const petId = manifest.id;
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
        const initialSpritePosition = getPetCanvasPosition(
          petViewportRef.current,
          getCanvasOrigin(petViewportRef.current),
        );
        sprite.position.set(initialSpritePosition.x, initialSpritePosition.y);
        app.stage.addChild(sprite);
        app.renderer.render(app.stage);
        startupPetReady.current = true;
        revealStartupWindowIfReady();
        if (isTauriRuntime()) {
          void emit("startup-pet-ready");
        }

        host.dataset.petLoaded = "true";
        host.dataset.petId = manifest.id;
        host.dataset.spriteSource = manifest.spritesheetPath;
        host.dataset.animationCount = String(animationEntries.length);
        host.dataset.desktopIconEnabled = String(resolvedInteractions.desktopIcon.enabled);
        recordInteraction("app_ready");
        window.setTimeout(flushProactiveDeliveries, 0);
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
            : { offsetX: 0, offsetY: 0, scaleY: 0 };
          const dragFrameOffsetY = getDragFrameOffsetY(
            sprite,
            currentAnimation.current,
            transform.scaleY ?? 0,
          );
          const petViewport = petViewportRef.current;
          const spritePosition = getPetCanvasPosition(
            petViewport,
            getCanvasOrigin(petViewport),
            {
              x: transform.offsetX,
              y: transform.offsetY + dragFrameOffsetY,
            },
          );
          sprite.position.set(spritePosition.x, spritePosition.y);
        });
      })
      .catch(() => {
        recordInteraction("app_init_failed");
        revealStartupWindow("startup_window_revealed_after_pet_failure");
      });

    return () => {
      disposed = true;
      if (returnToIdleTimer.current !== null) {
        window.clearTimeout(returnToIdleTimer.current);
        returnToIdleTimer.current = null;
      }
      clearTransientBubbleTimer();
      clearHoverEatTimer();
      releaseDragHoverSuppression();
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
  }, [activePetId, activePetManifest, isPlatformWindow]);

  const isPetInteractionLocked =
    isPlatformOpen || isQuickCreateOpen || isTaskMenuOpen;
  const usesDynamicPetWindow =
    isTauriRuntime() &&
    !isPlatformWindow &&
    !isPlatformOpen &&
    !isQuickCreateOpen &&
    !isTaskMenuOpen &&
    !isReminderWindowExpanded;
  const shellStyle = {
    "--pet-bubble-bottom": `${usesDynamicPetWindow ? petWindowLayout.bubbleBottom : PET_BUBBLE_BOTTOM_PX}px`,
    "--pet-bubble-center-x": usesDynamicPetWindow
      ? `${petWindowLayout.bubbleCenterX}px`
      : "50%",
    "--pet-hit-left": usesDynamicPetWindow
      ? `${petWindowLayout.petHitArea.x}px`
      : "24px",
    "--pet-hit-top": usesDynamicPetWindow
      ? `${petWindowLayout.petHitArea.y}px`
      : "118px",
    "--pet-hit-width": usesDynamicPetWindow
      ? `${petWindowLayout.petHitArea.width}px`
      : "117px",
    "--pet-hit-height": usesDynamicPetWindow
      ? `${petWindowLayout.petHitArea.height}px`
      : "91px",
    "--platform-pet-inset": `${PLATFORM_PET_INSET_PX}px`,
  } as CSSProperties;

  return (
    <main
      ref={shellRef}
      className={`pet-shell${isPlatformWindow ? " platform-window" : ""}${isPlatformOpen ? " platform-open" : ""}${isQuickCreateOpen ? " quick-create-open" : ""}${isTaskMenuOpen ? " task-menu-open" : ""}${!isPlatformOpen && !isQuickCreateOpen && !isTaskMenuOpen && isReminderWindowExpanded ? " reminder-open" : ""}`}
      data-ui-font-size={taskDatabase.settings.interfaceFontSize as InterfaceFontSize}
      style={shellStyle}
    >
      {!isPlatformWindow && (
        <>
          <div
            className="pet-hit-area"
            aria-hidden="true"
            onContextMenu={isPetInteractionLocked ? undefined : handleContextMenu}
            onMouseDown={isPetInteractionLocked ? undefined : handleMouseDown}
            onMouseEnter={isPetInteractionLocked ? undefined : handleMouseEnter}
            onMouseLeave={isPetInteractionLocked ? undefined : handleMouseLeave}
            onMouseMove={isPetInteractionLocked ? undefined : handleMouseMove}
            onMouseUp={isPetInteractionLocked ? undefined : handleMouseUp}
            onPointerDown={isPetInteractionLocked ? undefined : handlePointerDown}
            onPointerEnter={isPetInteractionLocked ? undefined : handlePointerEnter}
            onPointerLeave={isPetInteractionLocked ? undefined : handlePointerLeave}
            onPointerMove={isPetInteractionLocked ? undefined : handlePointerMove}
            onPointerCancel={
              isPetInteractionLocked ? undefined : handlePointerInterruption
            }
            onLostPointerCapture={
              isPetInteractionLocked ? undefined : handleLostPointerCapture
            }
            onPointerUp={isPetInteractionLocked ? undefined : handlePointerUp}
          />
          <div ref={pixiHost} className="pet-canvas" />
        </>
      )}
      {!isPlatformOpen && !isTaskMenuOpen && companionChatState.mode === "active" && (
        <CompanionChatBubble
          draft={companionChatState.draft}
          isWaiting={companionChatState.pendingRequestId !== null}
          messages={companionChatState.messages}
          providerInfo={companionChatProviderInfo}
          ollamaPullProgress={
            companionProviderSettings.protocol === "ollama-local"
              ? ollamaPullProgress
              : null
          }
          onDraftChange={updateCompanionDraftText}
          onSend={sendCompanionChatMessage}
          onStop={stopCompanionChatReply}
        />
      )}
      {!isTaskMenuOpen && companionChatState.mode !== "active" && bubbleText && (
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
      {!isPlatformOpen && !isQuickCreateOpen && !isTaskMenuOpen && companionChatState.mode !== "active" && (
        <TaskReminderStack
          reminders={visibleTaskReminders}
          onComplete={completeTaskReminder}
          onOpen={(taskId) => {
            markProactiveTaskEngaged(taskId);
            openTaskPlatform("today", taskId);
          }}
          onOpenAll={() => {
            openTaskPlatform("today");
            const summaryId = missedSummaryNotificationId.current;
            if (summaryId) void invoke("clear_task_notification", { instanceId: summaryId }).catch(() => {});
            missedSummaryNotificationId.current = null;
          }}
          onCloseSummary={(instanceIds) => {
            if (!commitTaskDatabase(closeMissedReminderSummary(readTaskDatabase()))) return;
            setHiddenTaskReminderIds((current) => new Set([...current, ...instanceIds]));
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
          onClose={closeTaskMenu}
          placement={taskMenuLayout.placement}
          style={{
            left: taskMenuLayout.menuPosition.x,
            top: taskMenuLayout.menuPosition.y,
          }}
          onOpenReminders={() => openTaskPlatform("upcoming")}
          onOpenToday={() => openTaskPlatform("today")}
          onOpenSettings={() => openTaskPlatform("settings")}
          onOpenChat={openCompanionChat}
          onQuickCreate={openQuickTaskCreate}
          onHidePet={hidePetTemporarily}
        />
      )}
      {isQuickCreateOpen && (
        <section className="quick-task-overlay" onPointerDown={stopPlatformEvent}>
          <div className="quick-task-panel">
            <header><div><small>快速记录</small><h2>新建待办</h2></div><button type="button" aria-label="关闭" onClick={closeQuickTaskCreate}>×</button></header>
            <QuickCreateTask compact onCancel={closeQuickTaskCreate} onCreate={createQuickTask} />
          </div>
        </section>
      )}
      {isPlatformOpen && (!isTauriRuntime() || isPlatformWindow) && (
        <section
          className="platform-panel"
          aria-label="桌宠平台"
          onMouseDown={stopPlatformEvent}
          onPointerDownCapture={(event) => {
            if (
              platformSection === "chat"
              && companionChatStateRef.current.mode === "active"
            ) {
              const target = event.target instanceof Element ? event.target : null;
              const isInsideCompanionSurface = Boolean(
                target?.closest(
                  ".platform-companion-chat-room-shell,.platform-companion-chat-record-backdrop,.platform-companion-chat-record-drawer",
                ),
              );
              if (!isInsideCompanionSurface) exitActiveCompanionChat(true, "outside");
            }
          }}
          onPointerDown={stopPlatformEvent}
        >
          <header className="platform-header" onPointerDown={startPlatformWindowDrag}>
            <div className="platform-brand">
              <span className="platform-brand-mark" aria-hidden="true">愈</span>
              <div>
                <h1>愈心</h1>
                <p>{activePet?.displayName ?? "小伙伴"}正在桌面陪伴</p>
              </div>
            </div>
            <nav
              className="platform-navigation"
              aria-label="主功能"
              onPointerDown={stopPlatformEvent}
            >
              <button
                aria-current={renderedPlatformSection === "home" ? "page" : undefined}
                className={renderedPlatformSection === "home" ? "is-active" : ""}
                type="button"
                onClick={() => navigatePlatformSection("home")}
              >
                首页
              </button>
              <button
                aria-current={renderedPlatformSection === "chat" ? "page" : undefined}
                className={renderedPlatformSection === "chat" ? "is-active" : ""}
                type="button"
                onClick={() => {
                  if (
                    renderedPlatformSection !== "chat"
                    || companionChatState.mode !== "active"
                  ) {
                    void openPlatformCompanionChat();
                  }
                }}
              >
                陪伴
              </button>
              <button
                aria-current={renderedPlatformSection === "settings" ? "page" : undefined}
                className={renderedPlatformSection === "settings" ? "is-active" : ""}
                type="button"
                onClick={() => navigatePlatformSection("settings")}
              >
                设置
              </button>
              <button
                aria-current={renderedPlatformSection === "tasks" ? "page" : undefined}
                className={renderedPlatformSection === "tasks" ? "is-active" : ""}
                type="button"
                onClick={() => navigatePlatformSection("tasks")}
              >
                待办
              </button>
              <button
                aria-current={renderedPlatformSection === "pets" ? "page" : undefined}
                className={renderedPlatformSection === "pets" ? "is-active" : ""}
                type="button"
                onClick={() => navigatePlatformSection("pets")}
              >
                桌宠
              </button>
            </nav>
            <div className="platform-header-actions">
              <button
                className="platform-companion-chip"
                type="button"
                onClick={() => navigatePlatformSection("pets")}
                onPointerDown={stopPlatformEvent}
              >
                <span
                  className={`platform-companion-avatar is-${activePet?.previewKind ?? "image"}`}
                  aria-hidden="true"
                  style={activePet ? { backgroundImage: `url(${activePet.previewUrl})` } : undefined}
                />
                <span>
                  <strong>{activePet?.displayName ?? "伙伴"}</strong>
                  <small>陪伴中</small>
                </span>
              </button>
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
                <svg viewBox="0 0 20 20" aria-hidden="true">
                  <path d="M3.5 5.5h13v9h-13z" />
                  <path d="m4.3 6.3 5.7 4.4 5.7-4.4" />
                </svg>
                {visibleUnreadCount > 0 && (
                  <span className="platform-mailbox-badge">
                    {visibleUnreadCount}
                  </span>
                )}
              </button>
              <div className="platform-window-controls" onPointerDown={stopPlatformEvent}>
                {isPlatformWindow && (
                  <>
                    <button
                      className="platform-window-control"
                      type="button"
                      aria-label="最小化窗口"
                      title="最小化"
                      onClick={minimizePlatformWindow}
                    >
                      <svg viewBox="0 0 16 16" aria-hidden="true">
                        <path d="M3 8.5h10" />
                      </svg>
                    </button>
                    <button
                      className="platform-window-control"
                      type="button"
                      aria-label={isPlatformMaximized ? "还原窗口" : "最大化窗口"}
                      title={isPlatformMaximized ? "还原" : "最大化"}
                      onClick={togglePlatformWindowMaximize}
                    >
                      <svg viewBox="0 0 16 16" aria-hidden="true">
                        {isPlatformMaximized ? (
                          <>
                            <path d="M5.5 3.5h7v7" />
                            <rect x="3.5" y="5.5" width="7" height="7" rx="0.8" />
                          </>
                        ) : (
                          <rect x="3.5" y="3.5" width="9" height="9" rx="0.8" />
                        )}
                      </svg>
                    </button>
                  </>
                )}
                <button
                  className="platform-window-control platform-close"
                  type="button"
                  aria-label="关闭桌宠平台"
                  title="关闭"
                  onClick={closePlatform}
                >
                  <svg viewBox="0 0 16 16" aria-hidden="true">
                    <path d="m4 4 8 8M12 4l-8 8" />
                  </svg>
                </button>
              </div>
            </div>
          </header>

          {renderedPlatformSection === "chat" && companionChatState.mode === "active" ? (
            <PlatformCompanionChatPage
              draft={companionChatState.draft}
              isWaiting={companionChatState.pendingRequestId !== null}
              messages={companionChatState.messages}
              petName={activePet?.displayName ?? "小伙伴"}
              petPreviewKind={activePet?.previewKind}
              petPreviewUrl={activePet?.previewUrl}
              providerInfo={companionChatProviderInfo}
              ollamaPullProgress={
                companionProviderSettings.protocol === "ollama-local"
                  ? ollamaPullProgress
                  : null
              }
              onBack={closePlatformCompanionChatPage}
              onClose={closePlatformCompanionChatPage}
              onRetry={retryCompanionChatMessage}
              onDraftChange={updateCompanionDraftText}
              onSend={sendCompanionChatMessage}
              onStop={stopCompanionChatReply}
            />
          ) : renderedPlatformSection === "home" ? (
            <section className="platform-home" aria-label="首页">
              <header className="platform-home-intro">
                <div>
                  <span>{formatPlatformDate()}</span>
                  <h2>{getPlatformGreeting()}，今天也慢慢来</h2>
                  <p>把要做的事安稳放在这里，桌面上的小伙伴会继续陪着你。</p>
                </div>
                <button type="button" onClick={() => setPlatformSection("pets")}>
                  <i aria-hidden="true" />
                  <span>
                    <strong>{activePet?.displayName ?? "小伙伴"}</strong>
                    <small>正在桌面陪伴</small>
                  </span>
                </button>
              </header>

              <div className="platform-home-grid">
                <section className="platform-home-main-card">
                  <div className="platform-home-quick">
                    <div>
                      <span>快速记录</span>
                      <strong>先记下一件小事</strong>
                    </div>
                    <QuickCreateTask compact onCreate={createHomeTask} />
                  </div>

                  <div className="platform-home-agenda">
                    <header>
                      <div>
                        <span>今日安排</span>
                        <strong>
                          {homeTodayTasks.length > 0
                            ? `${homeTodayTasks.length} 件事在等你`
                            : "今天还很轻盈"}
                        </strong>
                      </div>
                      <button type="button" onClick={() => openTaskPlatform("today")}>
                        查看全部
                      </button>
                    </header>
                    {homeTaskPreview.length > 0 ? (
                      <div className="platform-home-task-list">
                        {homeTaskPreview.map((task) => (
                          <button
                            className={`is-${task.priority}`}
                            key={task.id}
                            type="button"
                            onClick={() => openTaskPlatform("today", task.id)}
                          >
                            <span aria-hidden="true" />
                            <strong>{task.title}</strong>
                            <small>{formatHomeTaskSchedule(task)}</small>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <div className="platform-home-empty">
                        <span aria-hidden="true">✓</span>
                        <div>
                          <strong>没有必须赶着完成的事</strong>
                          <p>给自己留一点空白，也是一种安排。</p>
                        </div>
                      </div>
                    )}
                  </div>
                </section>

                <aside className="platform-home-companion-card">
                  <div className="platform-home-note">
                    <div>
                      <span
                        className={`platform-home-note-avatar is-${activePet?.previewKind ?? "image"}`}
                        aria-hidden="true"
                        style={activePet ? { backgroundImage: `url(${activePet.previewUrl})` } : undefined}
                      />
                      <span>
                        <small>{activePet?.displayName ?? "小伙伴"}的话</small>
                        <strong>我在桌面上呢</strong>
                      </span>
                    </div>
                    <blockquote>“{homePetMessage}”</blockquote>
                  </div>

                  <button
                    className="platform-home-chat-button"
                    type="button"
                    onClick={() => void openPlatformCompanionChat()}
                  >
                    <span aria-hidden="true">◌</span>
                    <span>
                      <strong>去陪{activePet?.displayName ?? "小伙伴"}坐一会儿</strong>
                      <small>去陪它安静坐一会儿</small>
                    </span>
                    <b aria-hidden="true">›</b>
                  </button>

                  <div className="platform-home-stats" aria-label="今日进度">
                    <div>
                      <strong>{homeCompletedCount}</strong>
                      <span>今日完成</span>
                    </div>
                    <div>
                      <strong>{homeTodayTasks.length}</strong>
                      <span>仍待安排</span>
                    </div>
                  </div>

                  <button
                    className="platform-home-mail"
                    type="button"
                    onClick={openMailbox}
                  >
                    <span aria-hidden="true">
                      <svg viewBox="0 0 20 20">
                        <path d="M3.5 5.5h13v9h-13z" />
                        <path d="m4.3 6.3 5.7 4.4 5.7-4.4" />
                      </svg>
                    </span>
                    <span>
                      <strong>{visibleUnreadCount > 0 ? `${visibleUnreadCount} 封信还没读` : "信箱很安静"}</strong>
                      <small>{visibleUnreadCount > 0 ? "去看看伙伴带来的消息" : "新的消息会轻轻出现在这里"}</small>
                    </span>
                    <b aria-hidden="true">›</b>
                  </button>
                </aside>
              </div>
            </section>
          ) : renderedPlatformSection === "settings" ? (
            <PlatformProviderSettingsPage
              userProfile={companionUserProfile}
              userProfileSettings={companionSettingsInitialization}
              onUserProfileSettingsRetry={() => {
                clearCompanionUserSettingsDevFault();
                void companionUserSettingsRepository.initialize().then(applyCompanionSettingsInitialization);
              }}
              onUserProfileSave={saveCompanionUserProfile}
              settings={companionProviderSettings}
              providerInfo={companionChatProviderInfo}
              ollamaPullProgress={
                companionProviderSettings.protocol === "ollama-local"
                  ? ollamaPullProgress
                  : null
              }
              onProviderChange={loadCompanionProviderDraft}
              onTest={testCompanionProvider}
              onSave={saveCompanionProviderSettings}
              onFetchModels={fetchCompanionProviderModelsForSettings}
              onClear={clearCompanionProviderApiKey}
            />
          ) : renderedPlatformSection === "tasks" ? (
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
              companionMemoryRepository={companionMemoryRepository}
              companionMemoryPetId={activePetId}
            />
          ) : (
            <section className="platform-pets" aria-label="伙伴选择">
              <header className="platform-page-heading">
                <div>
                  <span>我的伙伴</span>
                  <h2>选择陪在桌面上的小伙伴</h2>
                </div>
                <p>{petCatalog.length} 位伙伴已经来到这里</p>
              </header>

              <div className="platform-pet-library">
                <header>
                  <strong>全部伙伴</strong>
                  <span>当前伙伴排在第一位，更换后会自动轮换</span>
                </header>
                <div className="pet-grid">
                  {[
                    ...petCatalog.filter((pet) => pet.isActive),
                    ...petCatalog.filter((pet) => !pet.isActive),
                  ].map((pet) => (
                    <article
                      aria-current={pet.isActive ? "true" : undefined}
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
                          {pet.isActive && <span>当前伙伴</span>}
                        </div>
                        <p>{pet.description}</p>
                        <div className="pet-card-footer">
                          {pet.isActive ? (
                            <span className="pet-card-status"><i /> 陪伴中</span>
                          ) : (
                            <button
                              className="pet-card-action"
                              type="button"
                              onClick={() => selectPet(pet)}
                            >
                              换成它
                            </button>
                          )}
                        </div>
                      </div>
                    </article>
                  ))}
                  {petCatalog.length === 0 && (
                    <div className="platform-pet-empty">
                      新伙伴来到这里后，会出现在这张名单中。
                    </div>
                  )}
                </div>
              </div>
            </section>
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

  if (isAccountRoute(pathname)) {
    return (
      <AccountGate>
        <DesktopPetApp />
      </AccountGate>
    );
  }

  return <DesktopPetApp />;
}

export default App;
