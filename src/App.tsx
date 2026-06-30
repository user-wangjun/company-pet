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
  WELCOME_LETTER_ID,
  deleteReadLetters,
  getUnreadCount,
  markAllLettersRead,
  markLetterRead,
  readMailboxState,
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
  updateDragDirection,
  type DragDirectionState,
} from "./pet-core/dragDirection";
import {
  getPetAnimationTransform,
  PET_BUBBLE_BOTTOM_PX,
} from "./pet-core/visual";
import {
  APP_DISPLAY_NAME,
  getCenteredWindowPosition,
  getInitialPetWindowPosition,
  PLATFORM_START_OPEN,
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
  getAmbientPetDialogueRefresh,
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
  enterCompanionChat,
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
  writeCareReminderState,
  type CareReminderState,
} from "./pet-core/careReminders";
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
  type PetReminderKind,
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
const CURRENT_PET_STORAGE_KEY = "desktop-pet.currentPetId";
const PET_WINDOW_SIZE = { width: 165, height: 215 };
const PLATFORM_WINDOW_SIZE = { width: 860, height: 590 };

type PetIndex = {
  pets: string[];
};

function getTimedDefaultBubble(): string {
  const hour = new Date().getHours();
  if (hour >= 8 && hour < 9) return "早上好！吃过早饭了吗？来个热腾腾的包子吧~ 🐾";
  if (hour >= 11 && hour < 12) return "咕噜噜……到饭点啦，中午吃什么好呢？多加个鸡腿喵！🍗";
  if (hour >= 13 && hour < 14) return "哈啊……好困，我们一起眯一会儿午觉吧。💤";
  if (hour >= 18 && hour < 19) return "天黑啦，该去吃晚饭啦！今天也要好好犒劳自己喵~ 🌟";
  if (hour >= 23 || hour < 6) return "唔……夜深了，快去睡觉吧，熬夜太伤身体了，小橘会心疼的喵💤";
  return "我先睡一会儿。";
}

function randomInRange(min: number, max: number): number {
  return Math.random() * (max - min) + min;
}

const CELL_WIDTH = 192;
const CELL_HEIGHT = 208;

type AnimationName = string;
type AvailableUpdate = Extract<UpdateCheckResult, { status: "available" }>;
type PressSource = "pointer" | "mouse";
type TauriWindow = ReturnType<typeof getCurrentWindow>;
type WindowMode = "platform" | "pet";
type OpenPlatformPayload = {
  resetPetPosition?: boolean;
};
type ActiveCareReminderPrompt =
  | {
      source: "timed";
      kind: Extract<PetReminderKind, "meal">;
      deliveredKey: string;
    }
  | {
      source: "random";
      kind: Extract<PetReminderKind, "eyeCare" | "water">;
      expiresAt: number;
    };

const MEAL_REMINDER_SNOOZE_MS = 10 * 60 * 1000;
const RANDOM_REMINDER_PROMPT_MS = 60 * 1000;

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
  const returnToIdleTimer = useRef<number | null>(null);
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
  const lastSecondaryClickAt = useRef<number | null>(null);
  const clickCount = useRef(0);
  const clickTimer = useRef<number | null>(null);
  const nextEyeCareTime = useRef(Date.now() + randomInRange(30, 50) * 60 * 1000);
  const nextWaterCareTime = useRef(Date.now() + randomInRange(60, 90) * 60 * 1000);
  const careReminderState = useRef<CareReminderState>(readCareReminderState());
  const timedCareSnoozedUntil = useRef(0);
  const nextIdleQuirkTime = useRef(Date.now() + randomInRange(20, 30) * 1000);
  const currentAnimation = useRef<AnimationName>("idle");
  const currentFacing = useRef<PetFacing>("right");
  const playbackToken = useRef(0);
  const [bubbleText, setBubbleText] = useState<string | null>(
    getTimedDefaultBubble(),
  );
  const latestBubbleText = useRef<string | null>(bubbleText);
  const ambientBubbleText = useRef<string | null>(null);
  const careReminderPromptRef = useRef<ActiveCareReminderPrompt | null>(null);
  const [careReminderPrompt, setCareReminderPrompt] =
    useState<ActiveCareReminderPrompt | null>(null);
  const [isPlatformOpen, setIsPlatformOpen] = useState(PLATFORM_START_OPEN);
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
  const [companionChatState, setCompanionChatState] =
    useState<CompanionChatState>(INACTIVE_COMPANION_CHAT);
  const companionChatStateRef = useRef<CompanionChatState>(INACTIVE_COMPANION_CHAT);
  const companionPreferencesRef = useRef<CompanionPreferencesState>(
    readCompanionPreferences(),
  );
  const [activePetId, setActivePetId] = useState(DEFAULT_PET_ID);
  const windowMode = useRef<WindowMode>(isPlatformOpen ? "platform" : "pet");
  const resetPetPositionOnNextOpen = useRef(true);
  const lastPetWindowPosition = useRef<WindowPosition | null>(null);
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
  const visibleUnreadCount = getUnreadCount(BUILT_IN_LETTERS, mailboxState);
  const activeLetter =
    BUILT_IN_LETTERS.find((letter) => letter.id === activeLetterId) ?? null;

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
    setDefaultBubbleText();
  };

  useEffect(() => {
    latestBubbleText.current = bubbleText;
  }, [bubbleText]);

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

    return () => {
      void unlistenUpdatePromise.then((unlisten) => unlisten());
      void unlistenPlatformPromise.then((unlisten) => unlisten());
      void unlistenSoundPromise.then((unlisten) => unlisten());
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
        const initialPetId = chooseInitialPetId(petIds, readSavedPetId());

        if (disposed) return;
        setAvailablePetIds(petIds);
        setPetManifestsById(manifests);
        setPetDialoguesById(Object.fromEntries(dialogueEntries));
        setPetCompanionChatsById(Object.fromEntries(companionChatEntries));
        setActivePetId(initialPetId);
      } catch {
        const fallbackManifest = await loadPetManifest(DEFAULT_PET_ID).catch(
          () => null,
        );

        if (disposed || !fallbackManifest) return;
        const fallbackDialogues = await loadPetDialoguePackage(fallbackManifest);
        const fallbackCompanionChat =
          await loadPetCompanionChatPackage(fallbackManifest);
        if (disposed) return;
        setAvailablePetIds([DEFAULT_PET_ID]);
        setPetManifestsById({ [DEFAULT_PET_ID]: fallbackManifest });
        setPetDialoguesById({ [DEFAULT_PET_ID]: fallbackDialogues });
        setPetCompanionChatsById({ [DEFAULT_PET_ID]: fallbackCompanionChat });
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
    setDefaultBubbleTextForPet(activePetId);
  }, [activePetId, petDialoguesById]);

  const applyPlatformWindowLayout = async (
    appWindow: TauriWindow,
    shouldCapturePetPosition: boolean,
  ) => {
    if (shouldCapturePetPosition) {
      const position = await appWindow.outerPosition().catch(() => null);
      if (position) {
        lastPetWindowPosition.current = { x: position.x, y: position.y };
      }
    }

    const monitor = await getPlacementMonitor();
    await setWindowSize(appWindow, PLATFORM_WINDOW_SIZE);

    if (!monitor) return;

    await setWindowPosition(
      appWindow,
      getCenteredWindowPosition(
        monitor.workArea,
        getPhysicalWindowSize(PLATFORM_WINDOW_SIZE, monitor),
      ),
    );
  };

  const applyPetWindowLayout = async (
    appWindow: TauriWindow,
    shouldUseInitialPosition: boolean,
  ) => {
    await setWindowSize(appWindow, PET_WINDOW_SIZE);

    if (!shouldUseInitialPosition) {
      if (lastPetWindowPosition.current) {
        await setWindowPosition(appWindow, lastPetWindowPosition.current);
      }
      return;
    }

    const monitor = await getPlacementMonitor();
    if (!monitor) return;

    await setWindowPosition(
      appWindow,
      getInitialPetWindowPosition(
        monitor.workArea,
        getPhysicalWindowSize(PET_WINDOW_SIZE, monitor),
      ),
    );
  };

  useEffect(() => {
    const appWindow = getOptionalCurrentWindow();
    if (!appWindow) return;

    const nextMode: WindowMode = isPlatformOpen ? "platform" : "pet";
    const previousMode = windowMode.current;
    windowMode.current = nextMode;

    if (nextMode === "platform") {
      void applyPlatformWindowLayout(
        appWindow,
        previousMode === "pet",
      ).catch(() => {
        recordInteraction("platform_layout_failed");
      });
      return;
    }

    const shouldUseInitialPosition = resetPetPositionOnNextOpen.current;
    resetPetPositionOnNextOpen.current = false;

    void applyPetWindowLayout(appWindow, shouldUseInitialPosition).catch(() => {
      recordInteraction("pet_layout_failed");
    });
  }, [isPlatformOpen]);

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
    setIsPlatformOpen(false);
    recordInteraction("platform_close");
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
    setDefaultBubbleTextForPet(pet.id);
    recordInteraction("platform_pet_selected");
  };

  const playPetSound = (eventName: string | undefined) => {
    if (!eventName) return;
    soundPlayerRef.current?.play(eventName);
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

  const startCompanionChat = () => {
    const config = resolveCompanionChatPackage(
      getCompanionChatPackageForPet(activePetId),
    );
    const next = enterCompanionChat(config);
    setActiveCareReminderPrompt(null);
    setBubbleText(null);
    setCompanionChatState(next);
    playPetSound(next.mode === "active" ? next.messages[0]?.sound : undefined);
    recordInteraction("companion_chat_open");
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
    setDefaultBubbleText();
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

  const getDefaultBubbleTextForPet = (petId: string) => {
    const resolved = getResolvedInteractionsForPet(petId);
    const idle = resolved?.idle;
    const nowTimestamp = Date.now();
    const timedReminder = selectTimedCareReminder(
      new Date(nowTimestamp),
      careReminderState.current.deliveredKeys,
    );
    const dialogueEvent =
      timedReminder && nowTimestamp >= timedCareSnoozedUntil.current
        ? timedReminder.kind
        : idle?.dialogueEvent ?? "idle";

    return getBubbleTextForPet(
      petId,
      dialogueEvent,
      idle?.bubbleText ?? getTimedDefaultBubble(),
    );
  };

  const getDefaultBubbleText = () => getDefaultBubbleTextForPet(activePetId);

  const setDefaultBubbleTextForPet = (petId: string) => {
    const nextText = getDefaultBubbleTextForPet(petId);
    ambientBubbleText.current = nextText;
    setBubbleText(nextText);
  };

  const setDefaultBubbleText = () => {
    setDefaultBubbleTextForPet(activePetId);
  };

  const refreshAmbientBubbleText = () => {
    const nextAmbientText = getDefaultBubbleText();
    const refreshedText = getAmbientPetDialogueRefresh(
      latestBubbleText.current,
      ambientBubbleText.current,
      nextAmbientText,
    );

    if (refreshedText === null) return;

    ambientBubbleText.current = refreshedText;
    setBubbleText(refreshedText);
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
    careReminderState.current = { deliveredKeys: nextDeliveredKeys };
    writeCareReminderState(careReminderState.current);
  };

  const clearCareReminderPrompt = () => {
    setActiveCareReminderPrompt(null);
    setDefaultBubbleText();
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

    timedCareSnoozedUntil.current = Date.now() + MEAL_REMINDER_SNOOZE_MS;
    recordInteraction("meal_care_snoozed");
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
        setDefaultBubbleText();
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
  const handleSecondaryPress = () => {
    const click = registerSecondaryClick(lastSecondaryClickAt.current, Date.now());
    lastSecondaryClickAt.current = click.lastClickAt;

    if (!click.triggered) {
      recordInteraction("secondary_click_armed");
      return;
    }

    recordInteraction("secondary_double_click_companion_chat");
    startCompanionChat();
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
      handleSecondaryPress();
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
      if (!shouldUseMouseFallback()) return;
      handleSecondaryPress();
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
    setDefaultBubbleText();
    playIdleAnimation();
  };

  const scheduleNextRandomCareReminder = (
    kind: Extract<PetReminderKind, "eyeCare" | "water">,
    nowTimestamp: number,
  ) => {
    if (kind === "eyeCare") {
      nextEyeCareTime.current = nowTimestamp + randomInRange(30, 50) * 60 * 1000;
      return;
    }

    nextWaterCareTime.current = nowTimestamp + randomInRange(60, 90) * 60 * 1000;
  };

  const postponeOverdueRandomCareReminders = (nowTimestamp: number) => {
    if (nowTimestamp >= nextEyeCareTime.current) {
      scheduleNextRandomCareReminder("eyeCare", nowTimestamp);
    }

    if (nowTimestamp >= nextWaterCareTime.current) {
      scheduleNextRandomCareReminder("water", nowTimestamp);
    }
  };

  const playCareReminder = (
    kind: PetReminderKind,
    deliveredKey?: string,
    markDelivered = true,
  ) => {
    const resolved = getActiveInteractionManifest();
    if (!resolved) return false;

    recordInteraction(`${kind}_care_reminder`);
    playManifestAction(resolved.reminders[kind], false, true);

    if (deliveredKey && markDelivered) {
      completeTimedCareReminder(deliveredKey);
    }

    return true;
  };

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
        selectTimedCareReminder(new Date(nowTimestamp), [])?.key !==
          activePrompt.deliveredKey
      ) {
        timedCareSnoozedUntil.current = 0;
        clearCareReminderPrompt();
      }
      return;
    }

    if (pointerState.current) {
      nextEyeCareTime.current = Math.max(nextEyeCareTime.current, nowTimestamp + 30000);
      nextWaterCareTime.current = Math.max(nextWaterCareTime.current, nowTimestamp + 30000);
    } else if (returnToIdleTimer.current === null) {
      const dueReminder = selectDueCareReminder({
        now: nowTimestamp,
        deliveredKeys: careReminderState.current.deliveredKeys,
        nextEyeCareTime: nextEyeCareTime.current,
        nextWaterCareTime: nextWaterCareTime.current,
        timedSnoozedUntil: timedCareSnoozedUntil.current,
      });

      if (dueReminder?.source === "random") {
        scheduleNextRandomCareReminder(dueReminder.kind, nowTimestamp);
      }

      if (
        dueReminder &&
        playCareReminder(
          dueReminder.kind,
          dueReminder.source === "timed" ? dueReminder.deliveredKey : undefined,
          dueReminder.source !== "timed" || dueReminder.kind !== "meal",
        )
      ) {
        if (dueReminder.source === "timed" && dueReminder.kind === "meal") {
          setActiveCareReminderPrompt({
            source: "timed",
            kind: "meal",
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

      refreshAmbientBubbleText();
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
    if (!host || isPlatformOpen) return;

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
  }, [activePetId, isPlatformOpen]);

  return (
    <main
      className={`pet-shell${isPlatformOpen ? " platform-open" : ""}`}
      style={
        { "--pet-bubble-bottom": `${PET_BUBBLE_BOTTOM_PX}px` } as CSSProperties
      }
      onContextMenu={isPlatformOpen ? undefined : handleContextMenu}
      onMouseDown={isPlatformOpen ? undefined : handleMouseDown}
      onMouseEnter={isPlatformOpen ? undefined : handleMouseEnter}
      onMouseLeave={isPlatformOpen ? undefined : handleMouseLeave}
      onMouseMove={isPlatformOpen ? undefined : handleMouseMove}
      onMouseUp={isPlatformOpen ? undefined : handleMouseUp}
      onPointerDown={isPlatformOpen ? undefined : handlePointerDown}
      onPointerEnter={isPlatformOpen ? undefined : handlePointerEnter}
      onPointerLeave={isPlatformOpen ? undefined : handlePointerLeave}
      onPointerMove={isPlatformOpen ? undefined : handlePointerMove}
      onPointerCancel={isPlatformOpen ? undefined : handlePointerInterruption}
      onLostPointerCapture={
        isPlatformOpen ? undefined : handlePointerInterruption
      }
      onPointerUp={isPlatformOpen ? undefined : handlePointerUp}
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
                {careReminderPrompt.source === "timed" ? "收到啦" : "确定"}
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
