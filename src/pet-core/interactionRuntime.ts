import type {
  PetFacing,
  PetReminderKind,
} from "./petInteractionManifest";

export type PetInteractionKind =
  | "idle"
  | "idleQuirk"
  | "hover"
  | "desktopIcon"
  | "careReminder"
  | "singleClick"
  | "doubleClick"
  | "drag"
  | "updatePrompt";

export type PetInteractionPhase = "enter" | "loop" | "exit";

export type InteractionRequest = {
  kind: Exclude<PetInteractionKind, "idle">;
  interruptible: boolean;
  payloadKey?: string;
  reminderKind?: PetReminderKind;
};

export type ActivePetInteraction = {
  token: number;
  kind: PetInteractionKind;
  priority: number;
  phase: PetInteractionPhase;
  facing: PetFacing;
  interruptible: boolean;
  payloadKey?: string;
  reminderKind?: PetReminderKind;
};

export type InteractionRuntimeState = {
  nextToken: number;
  active: ActivePetInteraction;
  queued: InteractionRequest | null;
};

const PRIORITY: Record<PetInteractionKind, number> = {
  idle: 0,
  idleQuirk: 100,
  hover: 100,
  desktopIcon: 200,
  careReminder: 300,
  singleClick: 400,
  doubleClick: 400,
  drag: 400,
  updatePrompt: 500,
};

function activate(
  state: InteractionRuntimeState,
  request: InteractionRequest,
): InteractionRuntimeState {
  const token = state.nextToken;
  return {
    nextToken: token + 1,
    queued: state.queued,
    active: {
      token,
      kind: request.kind,
      priority: PRIORITY[request.kind],
      phase: "enter",
      facing: state.active.facing,
      interruptible: request.interruptible,
      payloadKey: request.payloadKey,
      reminderKind: request.reminderKind,
    },
  };
}

function activateIdle(state: InteractionRuntimeState): InteractionRuntimeState {
  const token = state.nextToken;
  return {
    nextToken: token + 1,
    queued: null,
    active: {
      token,
      kind: "idle",
      priority: PRIORITY.idle,
      phase: "loop",
      facing: state.active.facing,
      interruptible: true,
    },
  };
}

export function createInteractionRuntime(
  facing: PetFacing,
): InteractionRuntimeState {
  return {
    nextToken: 1,
    queued: null,
    active: {
      token: 0,
      kind: "idle",
      priority: PRIORITY.idle,
      phase: "loop",
      facing,
      interruptible: true,
    },
  };
}

export function requestInteraction(
  state: InteractionRuntimeState,
  request: InteractionRequest,
): {
  decision: "start" | "queue" | "ignore";
  state: InteractionRuntimeState;
} {
  const requestPriority = PRIORITY[request.kind];
  if (
    requestPriority >= state.active.priority &&
    state.active.interruptible
  ) {
    return { decision: "start", state: activate(state, request) };
  }

  if (request.kind === "careReminder") {
    return {
      decision: "queue",
      state: { ...state, queued: request },
    };
  }

  return { decision: "ignore", state };
}

export function completeInteraction(
  state: InteractionRuntimeState,
  token: number,
): {
  decision: "idle" | "start-queued" | "stale";
  state: InteractionRuntimeState;
} {
  if (state.active.token !== token) {
    return { decision: "stale", state };
  }

  if (state.queued) {
    const queued = state.queued;
    const started = activate({ ...state, queued: null }, queued);
    return { decision: "start-queued", state: started };
  }

  return { decision: "idle", state: activateIdle(state) };
}

export function setInteractionFacing(
  state: InteractionRuntimeState,
  facing: PetFacing,
): InteractionRuntimeState {
  return {
    ...state,
    active: { ...state.active, facing },
  };
}
