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
import { openUrl } from "@tauri-apps/plugin-opener";
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
  PetInteractionAction,
  RuntimeAnimationName,
} from "./pet-core/interaction";
import {
  HOVER_EAT_DELAY_MS,
  findDesktopIconTarget,
  getDesktopIconBumpWindowPosition,
  formatDesktopIconBubbleText,
  formatDesktopIconWrapBubbleText,
  getDesktopIconWrapWindowPosition,
  getHoverFishAnimationSequence,
  getPetCareReminderAction,
  getPetClickAction,
  getPetContextMenuAction,
  getPetDesktopIconInteractionAction,
  getPetDragEndAction,
  getPetDragStartAction,
  getPetHoverEatingAction,
  getPetIdleAnimationName,
  getPetIdleBubbleText,
  getPetIdleQuirkActions,
  getTimedPetCareReminder,
  getDraggedWindowPosition,
  isPrimaryButtonPressed,
  isPointerCancellation,
  shouldStartDrag,
  shouldResumeHoverAfterInteraction,
  shouldTriggerHoverEat,
  updateDesktopIconInteraction,
} from "./pet-core/interaction";
import {
  ANIMATION_ROWS,
  appendPetAnimationFinishFrame,
  buildPetDragLandingFrames,
  getPetAnimationRowSpec,
  getPetDragFramePlan,
} from "./pet-core/animationRows";
import {
  getPetAnimationVisualScale,
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
  getPetIconHugSpritesheetPath,
  getPetThrowFinishPath,
  getPetIndexUrl,
  getPetManifestUrl,
  type PetCatalogItem,
  type PetManifest,
  resolvePetAssetUrl,
} from "./pet-core/petAssets";
import {
  getTimedPetDialogueEvent,
  loadPetDialoguePackage,
  resolvePetDialogue,
  type PetDialogueEvent,
  type PetDialoguePackage,
} from "./pet-core/dialogue";
import {
  createPetSoundPlayer,
  type PetSoundEvent,
  type PetSoundPlayer,
} from "./pet-core/sound";

const GITHUB_RELEASE_API = "https://api.github.com/repos/user-wangjun/company-pet/releases/latest";
const CURRENT_PET_STORAGE_KEY = "desktop-pet.currentPetId";
const PET_WINDOW_SIZE = { width: 165, height: 215 };
const PLATFORM_WINDOW_SIZE = { width: 860, height: 590 };

type PetIndex = {
  pets: string[];
};

function getTimedDefaultBubble(): string {
  const hour = new Date().getHours();
  if (hour >= 7 && hour < 9) return "早上好！吃过早饭了吗？来个热腾腾的包子吧~ 🐾";
  if (hour >= 11 && hour < 13) return "咕噜噜……到饭点啦，中午吃什么好呢？多加个鸡腿喵！🍗";
  if (hour >= 13 && hour < 14) return "哈啊……好困，我们一起眯一会儿午觉吧。💤";
  if (hour >= 18 && hour < 20) return "天黑啦，该去吃晚饭啦！今天也要好好犒劳自己喵~ 🌟";
  if (hour >= 23 || hour < 6) return "唔……夜深了，快去睡觉吧，熬夜太伤身体了，小橘会心疼的喵💤";
  return "我先睡一会儿。";
}

function randomInRange(min: number, max: number): number {
  return Math.random() * (max - min) + min;
}

const CELL_WIDTH = 192;
const CELL_HEIGHT = 208;

type AnimationName = RuntimeAnimationName;
type PressSource = "pointer" | "mouse";
type TauriWindow = ReturnType<typeof getCurrentWindow>;
type WindowMode = "platform" | "pet";
type OpenPlatformPayload = {
  resetPetPosition?: boolean;
};

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

function sliceRowFrames(
  texture: Texture,
  row: number,
  frames: number,
): Texture[] {
  return Array.from(
    { length: frames },
    (_, frameIndex) =>
      new Texture({
        source: texture.source,
        frame: new Rectangle(
          frameIndex * CELL_WIDTH,
          row * CELL_HEIGHT,
          CELL_WIDTH,
          CELL_HEIGHT,
        ),
      }),
  );
}

function DesktopPetApp() {
  const pixiHost = useRef<HTMLDivElement>(null);
  const spriteRef = useRef<AnimatedSprite | null>(null);
  const animationsRef = useRef<Record<AnimationName, Texture[]> | null>(null);
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
  } | null>(null);
  const lastPointerEventAt = useRef(0);
  const clickCount = useRef(0);
  const clickTimer = useRef<number | null>(null);
  const nextEyeCareTime = useRef(Date.now() + randomInRange(30, 50) * 60 * 1000);
  const nextWaterCareTime = useRef(Date.now() + randomInRange(60, 90) * 60 * 1000);
  const lastTimedCareReminderKey = useRef<string | null>(null);
  const nextIdleQuirkTime = useRef(Date.now() + randomInRange(20, 30) * 1000);
  const currentAnimation = useRef<AnimationName>("idle");
  const [bubbleText, setBubbleText] = useState<string | null>(
    getTimedDefaultBubble(),
  );
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

  const checkForUpdates = async (manual = false) => {
    try {
      if (manual) {
        setBubbleText("正在检查更新中，喵... 🔍");
      }
      const response = await fetch(GITHUB_RELEASE_API);
      if (!response.ok) {
        if (manual) {
          setBubbleText("检查更新失败喵，网络似乎有些问题 😿");
        }
        return;
      }
      const data = await response.json();
      const latestVersion = data.tag_name;
      const currentVersion = "v0.1.0";
      if (latestVersion && latestVersion !== currentVersion) {
        setBubbleText(`发现新版本 ${latestVersion} 喵！正在为你打开升级网页... 🎈`);
        setTimeout(() => {
          void openUrl("https://github.com/user-wangjun/company-pet/releases/latest").catch(() => {});
        }, 1500);
      } else {
        if (manual) {
          setBubbleText("当前已经是最新版本啦喵！橘橘很满足~ 🐾");
        }
      }
    } catch {
      if (manual) {
        setBubbleText("检查更新失败喵，请稍后再试！😿");
      }
    }
  };

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

    // 启动 3 秒后进行一次静默的自动更新检测
    const startupTimer = window.setTimeout(() => {
      void checkForUpdates(false);
    }, 3000);

    return () => {
      window.clearTimeout(startupTimer);
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
        const initialPetId = chooseInitialPetId(petIds, readSavedPetId());

        if (disposed) return;
        setAvailablePetIds(petIds);
        setPetManifestsById(manifests);
        setPetDialoguesById(Object.fromEntries(dialogueEntries));
        setActivePetId(initialPetId);
      } catch {
        const fallbackManifest = await loadPetManifest(DEFAULT_PET_ID).catch(
          () => null,
        );

        if (disposed || !fallbackManifest) return;
        const fallbackDialogues = await loadPetDialoguePackage(fallbackManifest);
        if (disposed) return;
        setAvailablePetIds([DEFAULT_PET_ID]);
        setPetManifestsById({ [DEFAULT_PET_ID]: fallbackManifest });
        setPetDialoguesById({ [DEFAULT_PET_ID]: fallbackDialogues });
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
    setBubbleText(getDefaultBubbleTextForPet(activePetId));
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

    saveSelectedPetId(pet.id);
    setActivePetId(pet.id);
    setBubbleText(getDefaultBubbleTextForPet(pet.id));
    recordInteraction("platform_pet_selected");
  };

  const playPetSound = (eventName: PetSoundEvent) => {
    soundPlayerRef.current?.play(eventName);
  };

  const getDialoguePackageForPet = (petId: string): PetDialoguePackage => {
    const loaded = petDialoguesById[petId];
    if (loaded) return loaded;

    return petManifestsById[petId]?.dialoguesPath
      ? { status: "failed", petId }
      : { status: "not-configured", petId };
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

  const getDefaultBubbleTextForPet = (petId: string) =>
    getBubbleTextForPet(
      petId,
      getTimedPetDialogueEvent(new Date().getHours()),
      getPetIdleBubbleText(petId, getTimedDefaultBubble()),
    );

  const getDefaultBubbleText = () => getDefaultBubbleTextForPet(activePetId);

  const playInteractionAction = (
    action: PetInteractionAction,
    dialogueEvent?: PetDialogueEvent,
    resumeHoverAfterReturn = true,
  ) => {
    setBubbleText(
      dialogueEvent
        ? getBubbleTextForPet(
            activePetId,
            dialogueEvent,
            action.bubbleText ?? null,
          )
        : action.bubbleText ?? null,
    );
    playPetSound(action.sound);
    playAnimation(action.animation, action.durationMs, resumeHoverAfterReturn);
  };

  const handleClicks = () => {
    const currentCount = clickCount.current;
    clickCount.current = 0;
    clickTimer.current = null;

    const clickAction = getPetClickAction(activePetId, currentCount);
    if (clickAction) {
      if (currentCount === 1) {
        recordInteraction("click");
      } else if (currentCount === 2) {
        recordInteraction("double_click");
      }

      if ("sequence" in clickAction) {
        playHoverFishSequence();
      } else {
        playInteractionAction(
          clickAction,
          currentCount === 1
            ? "singleClick"
            : currentCount === 2
              ? "doubleClick"
              : undefined,
          shouldResumeHoverAfterInteraction("click"),
        );
      }
      return;
    }

    if (currentCount >= 3) {
      // 三击：检查更新
      recordInteraction("triple_click");
      void checkForUpdates(true);
    }
  };

  const clearHoverEatTimer = () => {
    if (hoverEatTimer.current !== null) {
      window.clearTimeout(hoverEatTimer.current);
      hoverEatTimer.current = null;
    }
    hoverStartedAt.current = null;
  };

  const scheduleHoverEat = () => {
    if (pointerState.current || hoverEatTimer.current !== null) return;

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
        const hoverEatingAction = getPetHoverEatingAction(activePetId);
        if (hoverEatingAction?.sequence === "hover-fish") {
          recordInteraction("hover_eat");
          playHoverFishSequence();
        }
      }
    }, HOVER_EAT_DELAY_MS);
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

  const playAnimation = (
    name: AnimationName,
    returnAfterMs?: number,
    resumeHoverAfterReturn = true,
  ) => {
    const sprite = spriteRef.current;
    const animations = animationsRef.current;
    if (!sprite || !animations) return false;

    currentAnimation.current = name;

    if (returnToIdleTimer.current !== null) {
      window.clearTimeout(returnToIdleTimer.current);
      returnToIdleTimer.current = null;
    }

    const animation = getPetAnimationRowSpec(activePetId, name);
    sprite.onComplete = undefined;
    sprite.textures = animations[name];
    sprite.animationSpeed = animation.speed;
    sprite.loop = animation.loop;
    sprite.scale.set(getPetAnimationVisualScale(activePetManifest, name));
    sprite.gotoAndPlay(0);

    if (returnAfterMs) {
      returnToIdleTimer.current = window.setTimeout(() => {
        setBubbleText(getDefaultBubbleText());
        playAnimation(getPetIdleAnimationName(activePetId));
        if (resumeHoverAfterReturn) {
          scheduleHoverEat();
        }
      }, returnAfterMs);
    }

    return true;
  };

  const getDragFramesForPlan = () => {
    const animations = animationsRef.current;
    const plan = getPetDragFramePlan(activePetId);
    if (!animations || !plan) return null;

    const dragFrames = animations.drag;
    const takeoffFrame = dragFrames[plan.takeoffFrame];
    const loopFrames = dragFrames.slice(
      plan.loopStartFrame,
      plan.loopStartFrame + plan.loopFrameCount,
    );
    const landingFrames = takeoffFrame
      ? buildPetDragLandingFrames(takeoffFrame, dragFrames, plan)
      : null;

    if (
      !takeoffFrame ||
      !landingFrames ||
      loopFrames.length !== plan.loopFrameCount
    ) {
      return null;
    }

    return { takeoffFrame, loopFrames, dragFrames, plan };
  };

  const playDragStartInteraction = (action: PetInteractionAction) => {
    const sprite = spriteRef.current;
    const dragFrames = getDragFramesForPlan();
    if (!sprite || action.animation !== "drag" || !dragFrames) {
      playInteractionAction(action);
      return;
    }

    if (returnToIdleTimer.current !== null) {
      window.clearTimeout(returnToIdleTimer.current);
      returnToIdleTimer.current = null;
    }

    setBubbleText(action.bubbleText ?? null);
    playPetSound(action.sound);
    currentAnimation.current = "drag";

    const animation = getPetAnimationRowSpec(activePetId, "drag");
    sprite.onComplete = undefined;
    sprite.textures = [dragFrames.takeoffFrame, ...dragFrames.loopFrames];
    sprite.animationSpeed = animation.speed;
    sprite.loop = false;
    sprite.scale.set(getPetAnimationVisualScale(activePetManifest, "drag"));
    sprite.onComplete = () => {
      if (spriteRef.current !== sprite || !pointerState.current?.dragging) return;

      sprite.onComplete = undefined;
      sprite.textures = dragFrames.loopFrames;
      sprite.animationSpeed = animation.speed;
      sprite.loop = true;
      sprite.gotoAndPlay(0);
    };
    sprite.gotoAndPlay(0);
  };

  const playDragEndInteraction = (action: PetInteractionAction) => {
    const sprite = spriteRef.current;
    const dragFrames = getDragFramesForPlan();
    const landingFrames =
      sprite && dragFrames
        ? buildPetDragLandingFrames(
            sprite.texture,
            dragFrames.dragFrames,
            dragFrames.plan,
          )
        : null;
    if (
      !sprite ||
      action.animation !== "drag" ||
      !dragFrames ||
      !landingFrames
    ) {
      playInteractionAction(action);
      return;
    }

    if (returnToIdleTimer.current !== null) {
      window.clearTimeout(returnToIdleTimer.current);
      returnToIdleTimer.current = null;
    }

    setBubbleText(action.bubbleText ?? null);
    playPetSound(action.sound);
    currentAnimation.current = "drag";

    sprite.onComplete = undefined;
    sprite.textures = landingFrames;
    sprite.animationSpeed = dragFrames.plan.landingTransitionSpeed;
    sprite.loop = false;
    sprite.scale.set(getPetAnimationVisualScale(activePetManifest, "drag"));
    sprite.onComplete = () => {
      if (spriteRef.current !== sprite || currentAnimation.current !== "drag") {
        return;
      }

      sprite.onComplete = undefined;
      const returnToIdle = () => {
        setBubbleText(getDefaultBubbleText());
        playAnimation(getPetIdleAnimationName(activePetId));
        if (shouldResumeHoverAfterInteraction("drag")) {
          scheduleHoverEat();
        }
      };

      if (action.durationMs) {
        returnToIdleTimer.current = window.setTimeout(
          returnToIdle,
          action.durationMs,
        );
      } else {
        returnToIdle();
      }
    };
    sprite.gotoAndPlay(0);
  };
  const playHoverFishSequence = () => {
    const [chaseAnimation, eatAnimation] = getHoverFishAnimationSequence();

    if (returnToIdleTimer.current !== null) {
      window.clearTimeout(returnToIdleTimer.current);
      returnToIdleTimer.current = null;
    }

    setBubbleText(
      getBubbleTextForPet(activePetId, "doubleClick", "鱼！"),
    );
    recordInteraction("fish_chase");
    playPetSound("fishChase");
    playAnimation(chaseAnimation);

    returnToIdleTimer.current = window.setTimeout(() => {
      setBubbleText(
        getBubbleTextForPet(activePetId, "doubleClick", "吃到了。"),
      );
      recordInteraction("fish_eat");
      playPetSound("fishEat");
      playAnimation(eatAnimation);

      returnToIdleTimer.current = window.setTimeout(() => {
        setBubbleText(getDefaultBubbleText());
        playAnimation(getPetIdleAnimationName(activePetId));
      }, 1300);
    }, 950);
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
      recordInteraction("drag_start");
      playDragStartInteraction(getPetDragStartAction(activePetId));
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
    playDragEndInteraction(getPetDragEndAction(activePetId));
    window.setTimeout(probeDesktopIconInteraction, 250);
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLElement>) => {
    markPointerEvent();
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
    if (getPetContextMenuAction() === "keep-open") {
      recordInteraction("context_menu");
      setBubbleText(getBubbleTextForPet(activePetId, "idle", "喵？"));
      playAnimation(getPetIdleAnimationName(activePetId), 900);
    }
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
    setBubbleText(getDefaultBubbleText());
    playAnimation(getPetIdleAnimationName(activePetId));
  };

  const probeDesktopIconInteraction = () => {
    if (desktopIconProbeInFlight.current || pointerState.current?.dragging) return;
    if (currentAnimation.current === "iconHug") return;

    // 随机健康关怀（喝水与眼疲劳）检测
    const nowTimestamp = Date.now();
    if (pointerState.current) {
      // 拖拽点击时，向后推迟提醒 30 秒，避免干扰
      nextEyeCareTime.current = Math.max(nextEyeCareTime.current, nowTimestamp + 30000);
      nextWaterCareTime.current = Math.max(nextWaterCareTime.current, nowTimestamp + 30000);
    } else if (nowTimestamp >= nextEyeCareTime.current) {
      recordInteraction("eye_care_reminder");
      const careAction = getPetCareReminderAction(activePetId, "eyeCare");
      if (careAction) {
        playInteractionAction(careAction, "eyeCare");
      } else {
        setBubbleText("看屏幕太久啦，陪小橘眺望一下窗外，放松一下眼睛吧~ 👀");
        playPetSound("care_reminder");
        playAnimation("idle", 8000); // 维持 8 秒
      }
      nextEyeCareTime.current = nowTimestamp + randomInRange(30, 50) * 60 * 1000;
      return; // 触发提醒，推迟本次吸附检测
    } else if (nowTimestamp >= nextWaterCareTime.current) {
      recordInteraction("water_care_reminder");
      const careAction = getPetCareReminderAction(activePetId, "water");
      if (careAction) {
        playInteractionAction(careAction, "water");
      } else {
        setBubbleText("（吸溜）主人，该喝杯水润润嗓子啦，不要一直盯着屏幕喵！🥛");
        playPetSound("care_reminder");
        playAnimation("fishChase", 8000); // 追着鱼玩去喝水，维持 8 秒
      }
      nextWaterCareTime.current = nowTimestamp + randomInRange(60, 90) * 60 * 1000;
      return; // 触发提醒，推迟本次吸附检测
    }

    if (!pointerState.current) {
      const timedReminder = getTimedPetCareReminder(
        new Date(nowTimestamp),
        lastTimedCareReminderKey.current,
      );

      if (timedReminder) {
        const careAction = getPetCareReminderAction(activePetId, timedReminder.kind);
        if (careAction) {
          recordInteraction(`${timedReminder.kind}_care_reminder`);
          lastTimedCareReminderKey.current = timedReminder.key;
          playInteractionAction(careAction, timedReminder.kind);
          return;
        }
      }
    }

    // 随机待机小动作检测
    if (pointerState.current || Date.now() < iconHugLockedUntil.current) {
      // 拖拽、点击、或者抱着图标时，推迟小动作检测
      nextIdleQuirkTime.current = Math.max(nextIdleQuirkTime.current, nowTimestamp + 20000);
    } else if (nowTimestamp >= nextIdleQuirkTime.current) {
      const quirkRandom = Math.random();
      // 15% 概率触发，若未触发，仅推迟 5 秒再次检测
      if (getPetIdleAnimationName(activePetId) !== "idle") {
        nextIdleQuirkTime.current = nowTimestamp + randomInRange(25, 45) * 1000;
      } else if (quirkRandom < 0.15) {
        recordInteraction("idle_quirk_triggered");
        const quirks = getPetIdleQuirkActions(activePetId);
        const chosen = quirks[Math.floor(Math.random() * quirks.length)];
        setBubbleText(
          getBubbleTextForPet(activePetId, "idle", chosen.text ?? null),
        );
        playPetSound(chosen.sound);
        playAnimation(chosen.animation, chosen.duration);
        nextIdleQuirkTime.current = nowTimestamp + randomInRange(25, 45) * 1000;
        return; // 触发微动作，推迟本次桌面图标探测
      } else {
        nextIdleQuirkTime.current = nowTimestamp + 5000; // 未触发，5秒后再次判断
      }
    }

    if (Date.now() < iconHugLockedUntil.current) return;

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
        if (!isOnDesktop) {
          return;
        }

        const desktopIconAction = getPetDesktopIconInteractionAction(activePetId);
        const target = findDesktopIconTarget(
          {
            x: position.x,
            y: position.y,
            width: size.width,
            height: size.height,
          },
          icons,
          undefined,
          desktopIconAction.animation === "drag" ? { side: "right" } : {},
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

        const iconTarget = result.target;
        clearHoverEatTimer();
        recordInteraction("desktop_icon_interact");

        if (desktopIconAction.animation !== "iconHug") {
          iconHugLockedUntil.current =
            Date.now() + (desktopIconAction.durationMs ?? 1800) + 1000;
          const bumpPosition = getDesktopIconBumpWindowPosition(
            iconTarget,
            size,
            scaleFactor,
          );

          void appWindow
            .setPosition(new PhysicalPosition(bumpPosition.x, bumpPosition.y))
            .then(() => {
              recordInteraction("desktop_icon_shoulder_hit");
              playInteractionAction(desktopIconAction);
            })
            .catch(() => {
              recordInteraction("desktop_icon_shoulder_hit_failed");
            });
          return;
        }

        iconHugLockedUntil.current = Date.now() + 6500;
        setBubbleText(formatDesktopIconBubbleText(iconTarget.title));
        const wrapPosition = getDesktopIconWrapWindowPosition(iconTarget, size, scaleFactor);
        void appWindow
          .setPosition(new PhysicalPosition(wrapPosition.x, wrapPosition.y))
          .then(() => appWindow.setIgnoreCursorEvents(true))
          .then(() => {
            recordInteraction("desktop_icon_wrap");
            recordInteraction("desktop_icon_click_through_on");
            setBubbleText(formatDesktopIconWrapBubbleText(iconTarget.title));
            recordInteraction("desktop_icon_hug_pose");
            playPetSound(desktopIconAction.sound);
            if (playAnimation(desktopIconAction.animation)) {
              recordInteraction("desktop_icon_custom_hug_sprite");
            } else {
              recordInteraction("desktop_icon_custom_hug_sprite_missing");
            }
            if (iconHugClickThroughTimer.current !== null) {
              window.clearTimeout(iconHugClickThroughTimer.current);
            }
            iconHugClickThroughTimer.current = window.setTimeout(() => {
              restoreCursorEvents();
            }, 5600);
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
        const spritesheetUrl = resolvePetAssetUrl(
          petId,
          manifest.spritesheetPath,
        );
        const iconHugSpritesheetUrl = resolvePetAssetUrl(
          petId,
          getPetIconHugSpritesheetPath(manifest),
        );
        const throwFinishPath = getPetThrowFinishPath(manifest);
        const throwFinishUrl = throwFinishPath
          ? resolvePetAssetUrl(petId, throwFinishPath)
          : null;
        const [texture, iconHugTexture, throwFinishTexture] = await Promise.all([
          Assets.load<Texture>(spritesheetUrl),
          Assets.load<Texture>(iconHugSpritesheetUrl),
          throwFinishUrl
            ? Assets.load<Texture>(throwFinishUrl)
            : Promise.resolve<Texture | null>(null),
        ]);

        if (disposed) {
          destroyApp();
          return;
        }

        const fishEatAnimation = getPetAnimationRowSpec(petId, "fishEat");
        const fishEatFrames = sliceRowFrames(
          texture,
          fishEatAnimation.row,
          fishEatAnimation.frames,
        );
        const animations: Record<AnimationName, Texture[]> = {
          idle: sliceRowFrames(
            texture,
            ANIMATION_ROWS.idle.row,
            ANIMATION_ROWS.idle.frames,
          ),
          drag: sliceRowFrames(
            texture,
            ANIMATION_ROWS.drag.row,
            ANIMATION_ROWS.drag.frames,
          ),
          tickle: sliceRowFrames(
            texture,
            ANIMATION_ROWS.tickle.row,
            ANIMATION_ROWS.tickle.frames,
          ),
          fishChase: sliceRowFrames(
            texture,
            ANIMATION_ROWS.fishChase.row,
            ANIMATION_ROWS.fishChase.frames,
          ),
          fishEat: fishEatFrames,
          iconHug: sliceRowFrames(
            iconHugTexture,
            ANIMATION_ROWS.iconHug.row,
            ANIMATION_ROWS.iconHug.frames,
          ),
          crouchAlert: sliceRowFrames(
            texture,
            ANIMATION_ROWS.crouchAlert.row,
            ANIMATION_ROWS.crouchAlert.frames,
          ),
          hugFish: sliceRowFrames(
            texture,
            ANIMATION_ROWS.hugFish.row,
            ANIMATION_ROWS.hugFish.frames,
          ),
          gnawFish: appendPetAnimationFinishFrame(
            petId,
            "gnawFish",
            sliceRowFrames(
              texture,
              ANIMATION_ROWS.gnawFish.row,
              ANIMATION_ROWS.gnawFish.frames,
            ),
            throwFinishTexture,
          ),
        };
        animationsRef.current = animations;
        const idleAnimationName = getPetIdleAnimationName(petId);
        const idleAnimation = getPetAnimationRowSpec(petId, idleAnimationName);
        const sprite = new AnimatedSprite({
          textures: animations[idleAnimationName],
          animationSpeed: idleAnimation.speed,
          autoPlay: true,
          loop: idleAnimation.loop,
        });

        currentAnimation.current = idleAnimationName;
        spriteRef.current = sprite;
        sprite.anchor.set(0.5, 1);
        sprite.scale.set(getPetAnimationVisualScale(manifest, idleAnimationName));
        sprite.x = app.screen.width / 2;
        sprite.y = app.screen.height - 6;
        app.stage.addChild(sprite);

        host.dataset.petLoaded = "true";
        host.dataset.petId = manifest.id;
        host.dataset.spriteSource = manifest.spritesheetPath;
        host.dataset.iconHugSource = getPetIconHugSpritesheetPath(manifest);
        host.dataset.throwFinishSource = throwFinishPath ?? "";
        recordInteraction("app_ready");
        desktopIconProbeTimer.current = window.setInterval(
          probeDesktopIconInteraction,
          1200,
        );

        app.ticker.add(() => {
          sprite.x = app.screen.width / 2;
          sprite.y = app.screen.height - 6;
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
      {bubbleText && <div className="bubble">{bubbleText}</div>}
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
