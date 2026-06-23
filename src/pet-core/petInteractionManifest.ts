import type { PetDialogueEvent } from "./dialogue";

export type PetFacing = "left" | "right";
export type PetReminderKind = "eyeCare" | "water" | "meal" | "sleep";
export type PetDirectionMode = "rows" | "mirror-left";
export type PetDesktopIconPositioning = "wrap" | "peek";

export type PetAnimationSpec = {
  row: number;
  frames: number;
  speed: number;
  loop: boolean;
  visualClass: "ordinary" | "pose-change";
  scale?: number;
  offsetX?: number;
  offsetY?: number;
  spritesheetPath?: string;
  finishFramePath?: string;
};

export type PetActionSpec = {
  animation: string;
  durationMs?: number;
  sound?: string;
  dialogueEvent?: PetDialogueEvent;
  bubbleText?: string;
};

export type PetSequenceStep = PetActionSpec & {
  startAfterMs: number;
};

export type PetSequenceSpec = {
  sequence: PetSequenceStep[];
};

export type PetDragSpec = {
  directionMode: PetDirectionMode;
  right: string;
  left: string;
  takeoffFrame?: number;
  loopStartFrame?: number;
  loopFrameCount?: number;
  landingApproachFrame?: number;
  landingFrame?: number;
  landingTransitionSpeed?: number;
  landingHoldMs?: number;
};

export type PetHoverSpec =
  | { enabled: false }
  | { enabled: true; action: PetActionSpec | PetSequenceSpec };

export type PetDesktopIconSpec =
  | { enabled: false }
  | {
      enabled: true;
      action: PetActionSpec;
      positioning: PetDesktopIconPositioning;
      allowedSide: "any" | "left" | "right";
    };

export type PetInteractionManifestSource = {
  id: string;
  animations?: Record<string, PetAnimationSpec>;
  interactions?: {
    idle?: PetActionSpec;
    singleClick?: PetActionSpec | PetSequenceSpec;
    doubleClick?: PetActionSpec | PetSequenceSpec;
    drag?: PetDragSpec;
    hover?: PetHoverSpec;
    desktopIcon?: PetDesktopIconSpec;
    reminders?: Partial<Record<PetReminderKind, PetActionSpec>>;
    idleQuirks?: PetActionSpec[];
  };
};

export type ResolvedPetInteractionManifest = {
  animations: Record<string, PetAnimationSpec>;
  idle: PetActionSpec;
  singleClick: PetActionSpec | PetSequenceSpec;
  doubleClick: PetActionSpec | PetSequenceSpec;
  drag: PetDragSpec;
  hover: PetHoverSpec;
  desktopIcon: PetDesktopIconSpec;
  reminders: Record<PetReminderKind, PetActionSpec>;
  idleQuirks: PetActionSpec[];
};

const REQUIRED_REMINDERS: PetReminderKind[] = [
  "eyeCare",
  "water",
  "meal",
  "sleep",
];

function requireAction(
  value: PetActionSpec | PetSequenceSpec | undefined,
  field: string,
): PetActionSpec | PetSequenceSpec {
  if (!value) throw new Error(`Missing interactions.${field}`);
  return value;
}

export function resolvePetInteractionManifest(
  source: PetInteractionManifestSource,
  warn: (message: string) => void = console.warn,
): ResolvedPetInteractionManifest {
  const animations = source.animations ?? {};
  const interactions = source.interactions ?? {};
  const idle = requireAction(interactions.idle, "idle") as PetActionSpec;
  const drag = interactions.drag;
  if (!drag) throw new Error("Missing interactions.drag");

  const reminders = Object.fromEntries(
    REQUIRED_REMINDERS.map((kind) => {
      const action = interactions.reminders?.[kind];
      if (!action) throw new Error(`Missing interactions.reminders.${kind}`);
      return [kind, action];
    }),
  ) as Record<PetReminderKind, PetActionSpec>;

  const hover: PetHoverSpec = interactions.hover?.enabled
    ? {
        enabled: true,
        action: requireAction(interactions.hover.action, "hover.action"),
      }
    : { enabled: false };

  let desktopIcon: PetDesktopIconSpec =
    interactions.desktopIcon ?? { enabled: false };
  if (desktopIcon.enabled && !desktopIcon.action) {
    warn(
      `[pet-interactions] ${source.id} disabled invalid desktopIcon.action`,
    );
    desktopIcon = { enabled: false };
  }

  return {
    animations,
    idle,
    singleClick: requireAction(interactions.singleClick, "singleClick"),
    doubleClick: requireAction(interactions.doubleClick, "doubleClick"),
    drag,
    hover,
    desktopIcon,
    reminders,
    idleQuirks: interactions.idleQuirks ?? [],
  };
}
