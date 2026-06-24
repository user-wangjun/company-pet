import type { PetFacing, PetReminderKind } from "./petInteractionManifest";

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

export type PetInteractionRequest = {
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

export type PetInteractionRuntimeState = {
  nextToken: number;
  active: ActivePetInteraction;
  queued: PetInteractionRequest | null;
};

export type InteractionRequest = PetInteractionRequest;
export type InteractionRuntimeState = PetInteractionRuntimeState;
export type PetInteractionRequestDecision = "start" | "queue" | "ignore";
export type PetInteractionCompletionDecision = "idle" | "start-queued" | "stale";

const INTERACTION_PRIORITY: Record<PetInteractionKind, number> = {
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

function toActiveInteraction(
  state: PetInteractionRuntimeState,
  request: PetInteractionRequest,
): ActivePetInteraction {
  return {
    token: state.nextToken,
    kind: request.kind,
    priority: INTERACTION_PRIORITY[request.kind],
    phase: "enter",
    facing: state.active.facing,
    interruptible: request.interruptible,
    payloadKey: request.payloadKey,
    reminderKind: request.reminderKind,
  };
}

function startInteraction(
  state: PetInteractionRuntimeState,
  request: PetInteractionRequest,
): PetInteractionRuntimeState {
  return {
    nextToken: state.nextToken + 1,
    active: toActiveInteraction(state, request),
    queued: state.queued,
  };
}

function startIdle(state: PetInteractionRuntimeState): PetInteractionRuntimeState {
  return {
    nextToken: state.nextToken + 1,
    active: {
      token: state.nextToken,
      kind: "idle",
      priority: INTERACTION_PRIORITY.idle,
      phase: "loop",
      facing: state.active.facing,
      interruptible: true,
    },
    queued: null,
  };
}

export function createInteractionRuntime(
  facing: PetFacing,
): PetInteractionRuntimeState {
  return {
    nextToken: 1,
    active: {
      token: 0,
      kind: "idle",
      priority: INTERACTION_PRIORITY.idle,
      phase: "loop",
      facing,
      interruptible: true,
    },
    queued: null,
  };
}

export function requestInteraction(
  state: PetInteractionRuntimeState,
  request: PetInteractionRequest,
): {
  decision: PetInteractionRequestDecision;
  state: PetInteractionRuntimeState;
} {
  const requestPriority = INTERACTION_PRIORITY[request.kind];

  if (requestPriority >= state.active.priority && state.active.interruptible) {
    return {
      decision: "start",
      state: startInteraction(state, request),
    };
  }

  if (request.kind === "careReminder") {
    return {
      decision: "queue",
      state: {
        ...state,
        queued: request,
      },
    };
  }

  return {
    decision: "ignore",
    state,
  };
}

export function completeInteraction(
  state: PetInteractionRuntimeState,
  token: number,
): {
  decision: PetInteractionCompletionDecision;
  state: PetInteractionRuntimeState;
} {
  if (token !== state.active.token) {
    return {
      decision: "stale",
      state,
    };
  }

  if (state.queued) {
    return {
      decision: "start-queued",
      state: startInteraction({ ...state, queued: null }, state.queued),
    };
  }

  return {
    decision: "idle",
    state: startIdle(state),
  };
}

export function setInteractionFacing(
  state: PetInteractionRuntimeState,
  facing: PetFacing,
): PetInteractionRuntimeState {
  return {
    ...state,
    active: {
      ...state.active,
      facing,
    },
  };
}
