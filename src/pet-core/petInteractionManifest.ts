import type { PetDialogueEvent } from "./dialogue";

export type PetFacing = "left" | "right";
export type PetReminderKind = "eyeCare" | "water" | "meal" | "sleep";
export type PetDirectionMode = "rows" | "mirror-left";
export type PetDesktopIconPositioning = "wrap" | "peek";
export type PetDesktopIconAllowedSide = "any" | "left" | "right";

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
      allowedSide: PetDesktopIconAllowedSide;
    };

export type PetManifestInteractions = {
  idle: PetActionSpec;
  singleClick: PetActionSpec | PetSequenceSpec;
  doubleClick: PetActionSpec | PetSequenceSpec;
  drag: PetDragSpec;
  reminders: Record<PetReminderKind, PetActionSpec>;
  hover?: PetHoverSpec;
  desktopIcon?: PetDesktopIconSpec;
  idleQuirks?: PetActionSpec[];
};

type PetHoverSource = {
  enabled?: boolean;
  action?: PetActionSpec | PetSequenceSpec;
};

export type PetDesktopIconSource = {
  enabled?: boolean;
  action?: PetActionSpec;
  positioning?: string;
  allowedSide?: string;
};

type PetInteractionSource = {
  idle?: PetActionSpec;
  singleClick?: PetActionSpec | PetSequenceSpec;
  doubleClick?: PetActionSpec | PetSequenceSpec;
  drag?: PetDragSpec;
  hover?: PetHoverSource;
  desktopIcon?: PetDesktopIconSource;
  reminders?: Partial<Record<PetReminderKind, PetActionSpec>>;
  idleQuirks?: PetActionSpec[];
};

export type PetInteractionManifestSource = {
  id: string;
  animations?: Record<string, PetAnimationSpec>;
  interactions?: PetInteractionSource;
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

function isSequenceSpec(
  value: PetActionSpec | PetSequenceSpec,
): value is PetSequenceSpec {
  return "sequence" in value;
}

function validateAction(
  action: PetActionSpec,
  field: string,
  animations: Record<string, PetAnimationSpec>,
  finite: boolean,
): PetActionSpec {
  const animation = animations[action.animation];
  if (!animation) {
    throw new Error(
      `Unknown animation "${action.animation}" at interactions.${field}.animation`,
    );
  }

  if (
    finite &&
    animation.loop &&
    (!Number.isFinite(action.durationMs) || (action.durationMs ?? 0) <= 0)
  ) {
    throw new Error(
      `Missing positive durationMs for loop animation at interactions.${field}`,
    );
  }

  return action;
}

function validateActionOrSequence(
  action: PetActionSpec | PetSequenceSpec,
  field: string,
  animations: Record<string, PetAnimationSpec>,
): PetActionSpec | PetSequenceSpec {
  if (!isSequenceSpec(action)) {
    return validateAction(action, field, animations, true);
  }

  if (action.sequence.length === 0) {
    throw new Error(`Empty sequence at interactions.${field}.sequence`);
  }

  action.sequence.forEach((step, index) => {
    validateAction(step, `${field}.sequence[${index}]`, animations, true);
  });

  return action;
}

function disableDesktopIcon(
  petId: string,
  field: string,
  warn: (message: string) => void,
): PetDesktopIconSpec {
  warn(`[pet-interactions] ${petId} disabled invalid desktopIcon.${field}`);
  return { enabled: false };
}

function isDesktopIconPositioning(
  value: string | undefined,
): value is PetDesktopIconPositioning {
  return value === "wrap" || value === "peek";
}

function isDesktopIconAllowedSide(
  value: string | undefined,
): value is PetDesktopIconAllowedSide {
  return value === "any" || value === "left" || value === "right";
}

function resolveDesktopIcon(
  petId: string,
  source: PetDesktopIconSource | undefined,
  animations: Record<string, PetAnimationSpec>,
  warn: (message: string) => void,
): PetDesktopIconSpec {
  if (!source?.enabled) return { enabled: false };

  if (!source.action) {
    return disableDesktopIcon(petId, "action", warn);
  }

  const animation = animations[source.action.animation];
  if (!animation) {
    return disableDesktopIcon(petId, "action.animation", warn);
  }

  if (!isDesktopIconPositioning(source.positioning)) {
    return disableDesktopIcon(petId, "positioning", warn);
  }

  if (!isDesktopIconAllowedSide(source.allowedSide)) {
    return disableDesktopIcon(petId, "allowedSide", warn);
  }

  if (
    animation.loop &&
    (!Number.isFinite(source.action.durationMs) ||
      (source.action.durationMs ?? 0) <= 0)
  ) {
    return disableDesktopIcon(petId, "action.durationMs", warn);
  }

  return {
    enabled: true,
    action: source.action,
    positioning: source.positioning,
    allowedSide: source.allowedSide,
  };
}

export function resolvePetInteractionManifest(
  source: PetInteractionManifestSource,
  warn: (message: string) => void = console.warn,
): ResolvedPetInteractionManifest {
  const animations = source.animations ?? {};
  if (Object.keys(animations).length === 0) {
    throw new Error("Missing animations");
  }

  const interactions = source.interactions ?? {};
  const idle = requireAction(interactions.idle, "idle") as PetActionSpec;
  validateAction(idle, "idle", animations, false);

  const singleClick = validateActionOrSequence(
    requireAction(interactions.singleClick, "singleClick"),
    "singleClick",
    animations,
  );
  const doubleClick = validateActionOrSequence(
    requireAction(interactions.doubleClick, "doubleClick"),
    "doubleClick",
    animations,
  );

  const drag = interactions.drag;
  if (!drag) throw new Error("Missing interactions.drag");
  validateAction({ animation: drag.right }, "drag.right", animations, false);
  validateAction({ animation: drag.left }, "drag.left", animations, false);

  const reminders = Object.fromEntries(
    REQUIRED_REMINDERS.map((kind) => {
      const action = interactions.reminders?.[kind];
      if (!action) throw new Error(`Missing interactions.reminders.${kind}`);
      validateAction(action, `reminders.${kind}`, animations, true);
      return [kind, action];
    }),
  ) as Record<PetReminderKind, PetActionSpec>;

  const hover: PetHoverSpec = interactions.hover?.enabled
    ? {
        enabled: true,
        action: validateActionOrSequence(
          requireAction(interactions.hover.action, "hover.action"),
          "hover.action",
          animations,
        ),
      }
    : { enabled: false };

  const desktopIcon = resolveDesktopIcon(
    source.id,
    interactions.desktopIcon,
    animations,
    warn,
  );

  const idleQuirks = (interactions.idleQuirks ?? []).map((action, index) =>
    validateAction(action, `idleQuirks[${index}]`, animations, true),
  );

  return {
    animations,
    idle,
    singleClick,
    doubleClick,
    drag,
    hover,
    desktopIcon,
    reminders,
    idleQuirks,
  };
}
