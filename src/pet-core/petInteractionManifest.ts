import { PET_DIALOGUE_EVENTS, type PetDialogueEvent } from "./dialogue";
import { isSafePetRelativePath } from "./petAssets";

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
  enabled?: unknown;
  action?: unknown;
  positioning?: unknown;
  allowedSide?: unknown;
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

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireRecord(value: unknown, field: string): UnknownRecord {
  if (!isRecord(value)) {
    throw new Error(`Invalid object at ${field}`);
  }
  return value;
}

function requireNonEmptyString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(`Expected non-empty string at ${field}`);
  }
  return value;
}

function requireBoolean(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") {
    throw new Error(`Expected boolean at ${field}`);
  }
  return value;
}

function requireNonNegativeInteger(value: unknown, field: string): number {
  if (!Number.isInteger(value) || (value as number) < 0) {
    throw new Error(`Expected non-negative integer at ${field}`);
  }
  return value as number;
}

function requirePositiveInteger(value: unknown, field: string): number {
  if (!Number.isInteger(value) || (value as number) <= 0) {
    throw new Error(`Expected positive integer at ${field}`);
  }
  return value as number;
}

function requireFiniteNumber(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`Expected finite number at ${field}`);
  }
  return value;
}

function requireFinitePositiveNumber(value: unknown, field: string): number {
  if (
    typeof value !== "number" ||
    !Number.isFinite(value) ||
    value <= 0
  ) {
    throw new Error(`Expected finite positive number at ${field}`);
  }
  return value;
}

function requireFiniteNonNegativeNumber(
  value: unknown,
  field: string,
): number {
  if (
    typeof value !== "number" ||
    !Number.isFinite(value) ||
    value < 0
  ) {
    throw new Error(`Expected finite non-negative number at ${field}`);
  }
  return value;
}

function requireRelativePath(value: unknown, field: string): string {
  if (typeof value !== "string" || !isSafePetRelativePath(value)) {
    throw new Error(`Expected non-empty relative path at ${field}`);
  }
  return value;
}

function parseOptionalString(
  value: unknown,
  field: string,
): string | undefined {
  return value === undefined ? undefined : requireNonEmptyString(value, field);
}

function parseOptionalDialogueEvent(
  value: unknown,
  field: string,
): PetDialogueEvent | undefined {
  if (value === undefined) return undefined;
  if (
    typeof value !== "string" ||
    !PET_DIALOGUE_EVENTS.some((event) => event === value)
  ) {
    throw new Error(`Invalid value at ${field}`);
  }
  return value as PetDialogueEvent;
}

function parseOptionalNumber(
  value: unknown,
  field: string,
  parser: (input: unknown, inputField: string) => number,
): number | undefined {
  return value === undefined ? undefined : parser(value, field);
}

function parseOptionalPath(
  value: unknown,
  field: string,
): string | undefined {
  return value === undefined ? undefined : requireRelativePath(value, field);
}

function parseAnimationSpec(value: unknown, field: string): PetAnimationSpec {
  const source = requireRecord(value, field);
  const visualClass = source.visualClass;
  if (visualClass !== "ordinary" && visualClass !== "pose-change") {
    throw new Error(`Invalid value at ${field}.visualClass`);
  }

  return {
    row: requireNonNegativeInteger(source.row, `${field}.row`),
    frames: requirePositiveInteger(source.frames, `${field}.frames`),
    speed: requireFinitePositiveNumber(source.speed, `${field}.speed`),
    loop: requireBoolean(source.loop, `${field}.loop`),
    visualClass,
    scale: parseOptionalNumber(
      source.scale,
      `${field}.scale`,
      requireFinitePositiveNumber,
    ),
    offsetX: parseOptionalNumber(
      source.offsetX,
      `${field}.offsetX`,
      requireFiniteNumber,
    ),
    offsetY: parseOptionalNumber(
      source.offsetY,
      `${field}.offsetY`,
      requireFiniteNumber,
    ),
    spritesheetPath: parseOptionalPath(
      source.spritesheetPath,
      `${field}.spritesheetPath`,
    ),
    finishFramePath: parseOptionalPath(
      source.finishFramePath,
      `${field}.finishFramePath`,
    ),
  };
}

function parseAnimations(value: unknown): Record<string, PetAnimationSpec> {
  if (value === undefined) throw new Error("Missing animations");
  const source = requireRecord(value, "animations");
  const entries = Object.entries(source);
  if (entries.length === 0) throw new Error("Missing animations");

  return Object.fromEntries(
    entries.map(([name, spec]) => [
      requireNonEmptyString(name, "animations key"),
      parseAnimationSpec(spec, `animations.${name}`),
    ]),
  );
}

function getAnimation(
  animations: Record<string, PetAnimationSpec>,
  name: string,
): PetAnimationSpec | undefined {
  return Object.prototype.hasOwnProperty.call(animations, name)
    ? animations[name]
    : undefined;
}

function parseAction(
  value: unknown,
  field: string,
  animations: Record<string, PetAnimationSpec>,
  finite: boolean,
): PetActionSpec {
  const source = requireRecord(value, `interactions.${field}`);
  const animationName = requireNonEmptyString(
    source.animation,
    `interactions.${field}.animation`,
  );

  const animation = getAnimation(animations, animationName);
  if (!animation) {
    throw new Error(
      `Unknown animation "${animationName}" at interactions.${field}.animation`,
    );
  }

  if (
    finite &&
    animation.loop &&
    (source.durationMs === undefined ||
      typeof source.durationMs !== "number" ||
      !Number.isFinite(source.durationMs) ||
      source.durationMs <= 0)
  ) {
    throw new Error(
      `Missing positive durationMs for loop animation at interactions.${field}`,
    );
  }
  const durationMs =
    source.durationMs === undefined
      ? undefined
      : requireFinitePositiveNumber(
          source.durationMs,
          `interactions.${field}.durationMs`,
        );

  return {
    animation: animationName,
    durationMs,
    sound: parseOptionalString(
      source.sound,
      `interactions.${field}.sound`,
    ),
    dialogueEvent: parseOptionalDialogueEvent(
      source.dialogueEvent,
      `interactions.${field}.dialogueEvent`,
    ),
    bubbleText: parseOptionalString(
      source.bubbleText,
      `interactions.${field}.bubbleText`,
    ),
  };
}

function parseActionOrSequence(
  value: unknown,
  field: string,
  animations: Record<string, PetAnimationSpec>,
): PetActionSpec | PetSequenceSpec {
  const source = requireRecord(value, `interactions.${field}`);
  if (!Object.prototype.hasOwnProperty.call(source, "sequence")) {
    return parseAction(source, field, animations, true);
  }

  if (!Array.isArray(source.sequence)) {
    throw new Error(
      `Expected non-empty array at interactions.${field}.sequence`,
    );
  }
  if (source.sequence.length === 0) {
    throw new Error(`Empty sequence at interactions.${field}.sequence`);
  }

  let previousStartAfterMs = -1;
  return {
    sequence: source.sequence.map((step, index) => {
      const stepField = `${field}.sequence[${index}]`;
      const stepSource = requireRecord(step, `interactions.${stepField}`);
      const startAfterMs = requireFiniteNonNegativeNumber(
        stepSource.startAfterMs,
        `interactions.${stepField}.startAfterMs`,
      );
      if (startAfterMs < previousStartAfterMs) {
        throw new Error(
          `Expected non-decreasing startAfterMs at interactions.${stepField}.startAfterMs`,
        );
      }
      previousStartAfterMs = startAfterMs;

      return {
        ...parseAction(stepSource, stepField, animations, true),
        startAfterMs,
      };
    }),
  };
}

function disableDesktopIcon(
  petId: string,
  field: string,
  warn: (message: string) => void,
): PetDesktopIconSpec {
  const path = field ? `desktopIcon.${field}` : "desktopIcon";
  warn(`[pet-interactions] ${petId} disabled invalid ${path}`);
  return { enabled: false };
}

function isDesktopIconPositioning(
  value: unknown,
): value is PetDesktopIconPositioning {
  return value === "wrap" || value === "peek";
}

function isDesktopIconAllowedSide(
  value: unknown,
): value is PetDesktopIconAllowedSide {
  return value === "any" || value === "left" || value === "right";
}

function resolveDesktopIcon(
  petId: string,
  value: unknown,
  animations: Record<string, PetAnimationSpec>,
  warn: (message: string) => void,
): PetDesktopIconSpec {
  if (value === undefined) return { enabled: false };
  if (!isRecord(value)) {
    return disableDesktopIcon(petId, "", warn);
  }
  const source = value;
  if (source.enabled === undefined || source.enabled === false) {
    return { enabled: false };
  }
  if (source.enabled !== true) {
    return disableDesktopIcon(petId, "enabled", warn);
  }

  if (!isRecord(source.action)) {
    return disableDesktopIcon(petId, "action", warn);
  }
  const action = source.action;

  const animationName = action.animation;
  if (typeof animationName !== "string" || animationName.trim().length === 0) {
    return disableDesktopIcon(petId, "action.animation", warn);
  }
  const animation = getAnimation(animations, animationName);
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
    action.durationMs !== undefined &&
    (typeof action.durationMs !== "number" ||
      !Number.isFinite(action.durationMs) ||
      action.durationMs <= 0)
  ) {
    return disableDesktopIcon(petId, "action.durationMs", warn);
  }
  if (animation.loop && action.durationMs === undefined) {
    return disableDesktopIcon(petId, "action.durationMs", warn);
  }
  if (
    action.sound !== undefined &&
    (typeof action.sound !== "string" || action.sound.trim().length === 0)
  ) {
    return disableDesktopIcon(petId, "action.sound", warn);
  }
  if (
    action.dialogueEvent !== undefined &&
    (typeof action.dialogueEvent !== "string" ||
      !PET_DIALOGUE_EVENTS.some((event) => event === action.dialogueEvent))
  ) {
    return disableDesktopIcon(petId, "action.dialogueEvent", warn);
  }
  if (
    action.bubbleText !== undefined &&
    (typeof action.bubbleText !== "string" ||
      action.bubbleText.trim().length === 0)
  ) {
    return disableDesktopIcon(petId, "action.bubbleText", warn);
  }

  return {
    enabled: true,
    action: {
      animation: animationName,
      durationMs: action.durationMs as number | undefined,
      sound: action.sound,
      dialogueEvent: action.dialogueEvent as PetDialogueEvent | undefined,
      bubbleText: action.bubbleText,
    },
    positioning: source.positioning,
    allowedSide: source.allowedSide,
  };
}

function parseRequiredAction(
  source: UnknownRecord,
  key: string,
  animations: Record<string, PetAnimationSpec>,
  finite: boolean,
): PetActionSpec {
  if (source[key] === undefined) {
    throw new Error(`Missing interactions.${key}`);
  }
  return parseAction(source[key], key, animations, finite);
}

function parseRequiredActionOrSequence(
  source: UnknownRecord,
  key: string,
  animations: Record<string, PetAnimationSpec>,
): PetActionSpec | PetSequenceSpec {
  if (source[key] === undefined) {
    throw new Error(`Missing interactions.${key}`);
  }
  return parseActionOrSequence(source[key], key, animations);
}

function parseDrag(
  value: unknown,
  animations: Record<string, PetAnimationSpec>,
): PetDragSpec {
  if (value === undefined) throw new Error("Missing interactions.drag");
  const source = requireRecord(value, "interactions.drag");
  const directionMode = source.directionMode;
  if (directionMode !== "rows" && directionMode !== "mirror-left") {
    throw new Error("Invalid value at interactions.drag.directionMode");
  }

  const right = requireNonEmptyString(
    source.right,
    "interactions.drag.right",
  );
  const left = requireNonEmptyString(source.left, "interactions.drag.left");
  const rightAnimation = getAnimation(animations, right);
  const leftAnimation = getAnimation(animations, left);
  if (!rightAnimation) {
    throw new Error(
      `Unknown animation "${right}" at interactions.drag.right`,
    );
  }
  if (!leftAnimation) {
    throw new Error(
      `Unknown animation "${left}" at interactions.drag.left`,
    );
  }

  const frameCount = Math.min(rightAnimation.frames, leftAnimation.frames);
  const frameFields = [
    "takeoffFrame",
    "loopStartFrame",
    "landingApproachFrame",
    "landingFrame",
  ] as const;
  const frames = Object.fromEntries(
    frameFields.map((key) => {
      const raw = source[key];
      if (raw === undefined) return [key, undefined];
      const frame = requireNonNegativeInteger(
        raw,
        `interactions.drag.${key}`,
      );
      if (frame >= frameCount) {
        throw new Error(
          `Frame index out of range at interactions.drag.${key}`,
        );
      }
      return [key, frame];
    }),
  ) as Pick<
    PetDragSpec,
    | "takeoffFrame"
    | "loopStartFrame"
    | "landingApproachFrame"
    | "landingFrame"
  >;

  const loopFrameCount =
    source.loopFrameCount === undefined
      ? undefined
      : requirePositiveInteger(
          source.loopFrameCount,
          "interactions.drag.loopFrameCount",
        );
  const hasLoopStartFrame = frames.loopStartFrame !== undefined;
  const hasLoopFrameCount = loopFrameCount !== undefined;
  if (hasLoopStartFrame && !hasLoopFrameCount) {
    throw new Error(
      "Missing interactions.drag.loopFrameCount when interactions.drag.loopStartFrame is set",
    );
  }
  if (!hasLoopStartFrame && hasLoopFrameCount) {
    throw new Error(
      "Missing interactions.drag.loopStartFrame when interactions.drag.loopFrameCount is set",
    );
  }
  if (
    loopFrameCount !== undefined &&
    (frames.loopStartFrame ?? 0) + loopFrameCount > frameCount
  ) {
    throw new Error(
      "Drag loop exceeds animation frames at interactions.drag.loopFrameCount",
    );
  }

  return {
    directionMode,
    right,
    left,
    ...frames,
    loopFrameCount,
    landingTransitionSpeed: parseOptionalNumber(
      source.landingTransitionSpeed,
      "interactions.drag.landingTransitionSpeed",
      requireFinitePositiveNumber,
    ),
    landingHoldMs: parseOptionalNumber(
      source.landingHoldMs,
      "interactions.drag.landingHoldMs",
      requireFiniteNonNegativeNumber,
    ),
  };
}

function parseReminders(
  value: unknown,
  animations: Record<string, PetAnimationSpec>,
): Record<PetReminderKind, PetActionSpec> {
  if (value === undefined) {
    throw new Error("Missing interactions.reminders.eyeCare");
  }
  const source = requireRecord(value, "interactions.reminders");
  return Object.fromEntries(
    REQUIRED_REMINDERS.map((kind) => {
      if (source[kind] === undefined) {
        throw new Error(`Missing interactions.reminders.${kind}`);
      }
      return [
        kind,
        parseAction(source[kind], `reminders.${kind}`, animations, true),
      ];
    }),
  ) as Record<PetReminderKind, PetActionSpec>;
}

function parseHover(
  value: unknown,
  animations: Record<string, PetAnimationSpec>,
): PetHoverSpec {
  if (value === undefined) return { enabled: false };
  const source = requireRecord(value, "interactions.hover");
  const enabled = requireBoolean(
    source.enabled,
    "interactions.hover.enabled",
  );
  if (!enabled) return { enabled: false };
  if (source.action === undefined) {
    throw new Error("Missing interactions.hover.action");
  }
  return {
    enabled: true,
    action: parseActionOrSequence(source.action, "hover.action", animations),
  };
}

function parseIdleQuirks(
  value: unknown,
  animations: Record<string, PetAnimationSpec>,
): PetActionSpec[] {
  if (value === undefined) return [];
  if (!Array.isArray(value)) {
    throw new Error("Expected array at interactions.idleQuirks");
  }
  return value.map((action, index) =>
    parseAction(action, `idleQuirks[${index}]`, animations, true),
  );
}

export function resolvePetInteractionManifest(
  value: unknown,
  warn: (message: string) => void = console.warn,
): ResolvedPetInteractionManifest {
  const source = requireRecord(value, "manifest");
  const id = requireNonEmptyString(source.id, "id");
  const animations = parseAnimations(source.animations);
  const interactions =
    source.interactions === undefined
      ? {}
      : requireRecord(source.interactions, "interactions");
  const idle = parseRequiredAction(interactions, "idle", animations, false);
  const singleClick = parseRequiredActionOrSequence(
    interactions,
    "singleClick",
    animations,
  );
  const doubleClick = parseRequiredActionOrSequence(
    interactions,
    "doubleClick",
    animations,
  );
  const drag = parseDrag(interactions.drag, animations);
  const reminders = parseReminders(interactions.reminders, animations);
  const hover = parseHover(interactions.hover, animations);

  const desktopIcon = resolveDesktopIcon(
    id,
    interactions.desktopIcon,
    animations,
    warn,
  );
  const idleQuirks = parseIdleQuirks(interactions.idleQuirks, animations);

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
