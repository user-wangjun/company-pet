import {
  isCompanionPreferenceSafe,
  upsertCompanionPreference,
  type CompanionPreference,
  type CompanionPreferencesState,
} from "./companionPreferences";
import {
  commitCompanionUserProfilePreferenceState,
  createCompanionUserProfilePreferenceStore,
  initializeCompanionUserProfileState,
  type CompanionUserProfilePreferenceCommitResult,
  type CompanionUserProfileSyncStorage,
} from "./companionUserProfileSync";
import {
  normalizeCompanionUserProfile,
  isCompanionUserProfileSafe,
  type CompanionUserProfile,
} from "./companionUserProfile";

export type SettingsUnavailableReason =
  | "not-ready"
  | "stale-revision"
  | "read-failed"
  | "invalid-storage"
  | "recovery-blocked"
  | "write-failed"
  | "bridge-timeout"
  | "owner-unavailable";

export type SettingsOwnerUnavailableReason = Exclude<
  SettingsUnavailableReason,
  "not-ready" | "stale-revision" | "bridge-timeout" | "owner-unavailable"
>;

export type CompanionUserSettingsSnapshot = {
  profile: CompanionUserProfile;
  preferences: CompanionPreferencesState;
};

export type OwnerVersion = {
  ownerEpoch: string;
  stateSeq: string;
  dataRevision: string;
};

export type SettingsOwnerState =
  | {
      status: "ready";
      snapshot: CompanionUserSettingsSnapshot;
      generation: string;
      revision: string;
      ownerEpoch: string;
      stateSeq: string;
      dataRevision: string;
      issuedAt: number;
    }
  | {
      status: "blocked";
      reason: SettingsOwnerUnavailableReason;
      generation: string;
      revision: string;
      ownerEpoch: string;
      stateSeq: string;
      dataRevision: string;
      lastKnownDataRevision: string;
      issuedAt: number;
    };

/**
 * Repository-facing state is intentionally allowed to project transport
 * failures for the existing settings UI. The bridge keeps this projection
 * separate from the versioned OwnerState and never treats these reasons as
 * an Owner-published blocked state.
 */
export type SettingsTransportProjection = {
  status: "blocked";
  reason: "not-ready" | "bridge-timeout" | "owner-unavailable";
  transportState: "not-ready" | "connecting" | "bridge-timeout" | "owner-unavailable";
  issuedAt: number;
};

export type ClientTransportState =
  | { status: "not-ready" }
  | { status: "connecting"; correlationId: string; expectedOwnerEpoch?: string }
  | { status: "owner-unavailable"; ownerEpoch?: string }
  | { status: "bridge-timeout"; ownerEpoch?: string }
  | {
      status: "synced";
      ownerEpoch: string;
      stateSeq: string;
      dataRevision: string;
    };

export type SettingsInitialization = SettingsOwnerState | SettingsTransportProjection;

export type SettingsExpectedVersion = {
  expectedGeneration: string;
  expectedRevision: string;
  expectedOwnerEpoch?: string;
  expectedStateSeq?: string;
  expectedDataRevision?: string;
};

export type SettingsCommand = SettingsExpectedVersion & {
  correlationId: string;
} & (
  | {
      type: "updateProfile";
      patch: Partial<CompanionUserProfile>;
    }
  | {
      type: "upsertPreference";
      preference: CompanionPreference;
    }
  | {
      type: "deletePreference";
      id: string;
    }
);

export type SettingsCommandSuccess = {
  ok: true;
  snapshot: CompanionUserSettingsSnapshot;
  generation: string;
  revision: string;
  ownerEpoch: string;
  stateSeq: string;
  dataRevision: string;
  correlationId: string;
  applied: boolean;
};

export type SettingsCommandResult = SettingsCommandSuccess | {
  ok: false;
  reason: SettingsUnavailableReason;
  correlationId: string;
};

export type CompanionUserSettingsRepository = {
  getInitialization(): SettingsInitialization;
  getTransportState?: () => ClientTransportState;
  start?: () => void;
  stop?: () => void;
  getSnapshot(): (CompanionUserSettingsSnapshot & {
    generation: string;
    revision: string;
    ownerEpoch: string;
    stateSeq: string;
    dataRevision: string;
  }) | null;
  initialize(): Promise<SettingsInitialization>;
  subscribe(listener: (initialization: SettingsInitialization) => void): () => void;
  updateProfile(
    patch: Partial<CompanionUserProfile>,
    expected: SettingsExpectedVersion,
    correlationId: string,
  ): Promise<SettingsCommandResult>;
  upsertPreference(
    preference: CompanionPreference,
    expected: SettingsExpectedVersion,
    correlationId: string,
  ): Promise<SettingsCommandResult>;
  deletePreference(
    id: string,
    expected: SettingsExpectedVersion,
    correlationId: string,
  ): Promise<SettingsCommandResult>;
};

export type CompanionUserSettingsOwner = {
  getInitialization(): SettingsOwnerState;
  getSnapshot(): (CompanionUserSettingsSnapshot & {
    generation: string;
    revision: string;
    ownerEpoch: string;
    stateSeq: string;
    dataRevision: string;
  }) | null;
  initialize(): Promise<SettingsOwnerState>;
  subscribe(listener: (initialization: SettingsOwnerState) => void): () => void;
  execute(command: SettingsCommand): Promise<SettingsCommandResult>;
};

type OwnerState = {
  initialization: SettingsOwnerState;
  snapshot: CompanionUserSettingsSnapshot & {
    generation: string;
    revision: string;
    ownerEpoch: string;
    stateSeq: string;
    dataRevision: string;
  } | null;
  version: OwnerVersion;
};

function cloneProfile(profile: CompanionUserProfile): CompanionUserProfile {
  return { ...profile };
}

function clonePreferences(state: CompanionPreferencesState): CompanionPreferencesState {
  return {
    preferences: state.preferences.map((preference) => ({ ...preference })),
    recentPreferenceId: state.recentPreferenceId,
  };
}

function cloneSnapshot(
  snapshot: CompanionUserSettingsSnapshot,
): CompanionUserSettingsSnapshot {
  return {
    profile: cloneProfile(snapshot.profile),
    preferences: clonePreferences(snapshot.preferences),
  };
}

function cloneInitialization(initialization: SettingsInitialization): SettingsInitialization {
  return initialization.status === "ready"
    ? {
        ...initialization,
        snapshot: cloneSnapshot(initialization.snapshot),
      }
    : { ...initialization };
}

function cloneOwnerInitialization(initialization: SettingsOwnerState): SettingsOwnerState {
  return cloneInitialization(initialization) as SettingsOwnerState;
}

function cloneOwnerSnapshot(
  state: OwnerState,
): CompanionUserSettingsSnapshot & {
  generation: string;
  revision: string;
  ownerEpoch: string;
  stateSeq: string;
  dataRevision: string;
} {
  if (!state.snapshot) throw new Error("owner snapshot is unavailable");
  return {
    ...cloneSnapshot(state.snapshot),
    generation: state.snapshot.generation,
    revision: state.snapshot.revision,
    ownerEpoch: state.snapshot.ownerEpoch,
    stateSeq: state.snapshot.stateSeq,
    dataRevision: state.snapshot.dataRevision,
  };
}

function generationId(): string {
  const random = typeof globalThis.crypto?.randomUUID === "function"
    ? globalThis.crypto.randomUUID()
    : Math.random().toString(36).slice(2);
  return `settings-owner-${random}`;
}

function nextRevision(revision: string): string {
  const parsed = Number.parseInt(revision, 10);
  return Number.isFinite(parsed) ? String(parsed + 1) : "1";
}

function sameProfile(left: CompanionUserProfile, right: CompanionUserProfile): boolean {
  return left.nickname === right.nickname
    && left.gender === right.gender
    && left.email === right.email
    && left.phone === right.phone;
}

function samePreferences(left: CompanionPreferencesState, right: CompanionPreferencesState): boolean {
  return left.recentPreferenceId === right.recentPreferenceId
    && left.preferences.length === right.preferences.length
    && left.preferences.every((preference, index) => {
      const rightPreference = right.preferences[index];
      return rightPreference !== undefined
        && preference.id === rightPreference.id
        && preference.scope === rightPreference.scope
        && preference.category === rightPreference.category
        && preference.key === rightPreference.key
        && preference.value === rightPreference.value
        && preference.source === rightPreference.source;
    });
}

function profilePatch(
  current: CompanionUserProfile,
  patch: Partial<CompanionUserProfile>,
): CompanionUserProfile {
  return normalizeCompanionUserProfile({
    ...current,
    ...patch,
  });
}

function nicknamePreference(value: string): CompanionPreference {
  return {
    id: "global.nickname",
    scope: "global",
    category: "userProfile",
    key: "nickname",
    value,
    source: "explicit",
  };
}

function updateNicknamePreference(
  preferences: CompanionPreferencesState,
  nickname: string,
): CompanionPreferencesState {
  if (nickname) return upsertCompanionPreference(preferences, nicknamePreference(nickname));
  const next = preferences.preferences.filter((preference) => preference.id !== "global.nickname");
  return {
    preferences: next,
    recentPreferenceId: preferences.recentPreferenceId === "global.nickname"
      ? null
      : preferences.recentPreferenceId,
  };
}

function deletePreferenceById(
  preferences: CompanionPreferencesState,
  id: string,
): CompanionPreferencesState {
  const next = preferences.preferences.filter((preference) => preference.id !== id);
  return {
    preferences: next,
    recentPreferenceId: preferences.recentPreferenceId === id
      ? null
      : preferences.recentPreferenceId,
  };
}

function commandFailure(
  command: SettingsCommand,
  reason: SettingsUnavailableReason,
): SettingsCommandResult {
  return { ok: false, reason, correlationId: command.correlationId };
}

function initializationFromStartup(
  startup: ReturnType<typeof initializeCompanionUserProfileState>,
  version: OwnerVersion,
  issuedAt: number,
): SettingsOwnerState {
  if (startup.status === "blocked") {
    return {
      status: "blocked",
      reason: startup.reason,
      generation: version.ownerEpoch,
      revision: version.dataRevision,
      ownerEpoch: version.ownerEpoch,
      stateSeq: version.stateSeq,
      dataRevision: version.dataRevision,
      lastKnownDataRevision: version.dataRevision,
      issuedAt,
    };
  }
  return {
    status: "ready",
    snapshot: {
      profile: cloneProfile(startup.profile),
      preferences: clonePreferences(startup.preferences),
    },
    generation: version.ownerEpoch,
    revision: version.dataRevision,
    ownerEpoch: version.ownerEpoch,
    stateSeq: version.stateSeq,
    dataRevision: version.dataRevision,
    issuedAt,
  };
}

function ownerReason(
  initialization: SettingsOwnerState,
): SettingsUnavailableReason {
  return initialization.status === "blocked"
    ? initialization.reason
    : "not-ready";
}

function commitFailureReason(
  result: CompanionUserProfilePreferenceCommitResult,
): SettingsUnavailableReason {
  return result.ok ? "write-failed" : result.reason;
}

function sameOwnerBusinessState(
  left: SettingsOwnerState,
  right: SettingsOwnerState,
): boolean {
  if (left.status !== right.status) return false;
  if (left.status === "blocked" && right.status === "blocked") {
    return left.reason === right.reason;
  }
  if (left.status !== "ready" || right.status !== "ready") return false;
  return sameProfile(left.snapshot.profile, right.snapshot.profile)
    && samePreferences(left.snapshot.preferences, right.snapshot.preferences);
}

function ownerStateFromStartup(
  startup: ReturnType<typeof initializeCompanionUserProfileState>,
  version: OwnerVersion,
  issuedAt: number,
): OwnerState {
  const initialization = initializationFromStartup(startup, version, issuedAt);
  return {
    initialization,
    snapshot: initialization.status === "ready"
      ? {
          ...cloneSnapshot(initialization.snapshot),
          generation: version.ownerEpoch,
          revision: version.dataRevision,
          ownerEpoch: version.ownerEpoch,
          stateSeq: version.stateSeq,
          dataRevision: version.dataRevision,
        }
      : null,
    version,
  };
}

export function createCompanionUserSettingsOwner(
  storage: CompanionUserProfileSyncStorage,
  options: { generation?: string; ownerEpoch?: string; issuedAt?: number } = {},
): CompanionUserSettingsOwner {
  const store = createCompanionUserProfilePreferenceStore(storage);
  const ownerEpoch = options.ownerEpoch ?? options.generation ?? generationId();
  const issuedAt = options.issuedAt ?? Date.now();
  const listeners = new Set<(initialization: SettingsOwnerState) => void>();
  const completedCommands = new Map<string, SettingsCommandResult>();
  let version: OwnerVersion = {
    ownerEpoch,
    stateSeq: "0",
    dataRevision: "0",
  };
  let state: OwnerState;
  let queue: Promise<unknown> = Promise.resolve();

  const readState = (nextVersion: OwnerVersion): OwnerState => {
    const startup = initializeCompanionUserProfileState(store);
    return ownerStateFromStartup(startup, nextVersion, issuedAt);
  };

  state = readState(version);

  const notify = () => {
    const current = cloneOwnerInitialization(state.initialization);
    for (const listener of listeners) {
      try {
        listener(current);
      } catch {
        // A transport listener must not make the Owner queue fail after the
        // durable state transition has already been accepted.
      }
    }
  };

  const refresh = (): SettingsOwnerState => {
    const candidate = readState(version);
    if (sameOwnerBusinessState(state.initialization, candidate.initialization)) {
      return cloneOwnerInitialization(state.initialization);
    }

    version = {
      ...version,
      stateSeq: nextRevision(version.stateSeq),
    };
    state = {
      ...candidate,
      version,
      initialization: initializationFromStartup(
        candidate.initialization.status === "ready"
          ? {
              status: "ready",
              profile: candidate.initialization.snapshot.profile,
              preferences: candidate.initialization.snapshot.preferences,
              migrated: false,
              migrationAttempted: false,
              migrationFailed: false,
              recovery: "none",
            }
          : {
              status: "blocked",
              reason: candidate.initialization.reason,
            },
        version,
        issuedAt,
      ),
    };
    state.snapshot = state.initialization.status === "ready"
      ? {
          ...cloneSnapshot(state.initialization.snapshot),
          generation: version.ownerEpoch,
          revision: version.dataRevision,
          ownerEpoch: version.ownerEpoch,
          stateSeq: version.stateSeq,
          dataRevision: version.dataRevision,
        }
      : null;
    notify();
    return cloneOwnerInitialization(state.initialization);
  };

  const executeNow = (command: SettingsCommand): SettingsCommandResult => {
    const previous = completedCommands.get(command.correlationId);
    if (previous) return previous;

    if (state.initialization.status !== "ready") {
      const result = commandFailure(command, ownerReason(state.initialization));
      completedCommands.set(command.correlationId, result);
      return result;
    }

    const expectedOwnerEpoch = command.expectedOwnerEpoch ?? command.expectedGeneration;
    const expectedDataRevision = command.expectedDataRevision ?? command.expectedRevision;
    if (
      expectedOwnerEpoch !== state.version.ownerEpoch
      || expectedDataRevision !== state.version.dataRevision
      || (command.expectedStateSeq !== undefined
        && command.expectedStateSeq !== state.version.stateSeq)
    ) {
      const result = commandFailure(command, "stale-revision");
      completedCommands.set(command.correlationId, result);
      return result;
    }

    const current = cloneOwnerSnapshot(state);
    let nextProfile = current.profile;
    let nextPreferences = current.preferences;
    if (command.type === "updateProfile") {
      nextProfile = profilePatch(current.profile, command.patch);
      if (!isCompanionUserProfileSafe(nextProfile)) {
        const result = commandFailure(command, "invalid-storage");
        completedCommands.set(command.correlationId, result);
        return result;
      }
      nextPreferences = updateNicknamePreference(current.preferences, nextProfile.nickname);
    } else if (command.type === "upsertPreference") {
      if (!isCompanionPreferenceSafe(command.preference)) {
        const result = commandFailure(command, "invalid-storage");
        completedCommands.set(command.correlationId, result);
        return result;
      }
      nextPreferences = upsertCompanionPreference(current.preferences, command.preference);
    } else {
      if (!command.id) {
        const result = commandFailure(command, "invalid-storage");
        completedCommands.set(command.correlationId, result);
        return result;
      }
      nextPreferences = deletePreferenceById(current.preferences, command.id);
    }

    if (sameProfile(nextProfile, current.profile) && samePreferences(nextPreferences, current.preferences)) {
      const result: SettingsCommandSuccess = {
        ok: true,
        snapshot: cloneSnapshot(current),
        generation: current.generation,
        revision: current.revision,
        ownerEpoch: current.ownerEpoch,
        stateSeq: current.stateSeq,
        dataRevision: current.dataRevision,
        correlationId: command.correlationId,
        applied: false,
      };
      completedCommands.set(command.correlationId, result);
      return result;
    }

    const committed = commitCompanionUserProfilePreferenceState(
      store,
      nextProfile,
      nextPreferences,
    );
    if (!committed.ok) {
      const refreshed = refresh();
      const result = commandFailure(
        command,
        refreshed.status === "blocked" ? ownerReason(refreshed) : commitFailureReason(committed),
      );
      completedCommands.set(command.correlationId, result);
      return result;
    }

    version = {
      ownerEpoch: state.version.ownerEpoch,
      stateSeq: nextRevision(state.version.stateSeq),
      dataRevision: nextRevision(state.version.dataRevision),
    };
    state = {
      initialization: {
        status: "ready",
        snapshot: {
          profile: cloneProfile(committed.profile),
          preferences: clonePreferences(committed.preferences),
        },
        generation: version.ownerEpoch,
        revision: version.dataRevision,
        ownerEpoch: version.ownerEpoch,
        stateSeq: version.stateSeq,
        dataRevision: version.dataRevision,
        issuedAt,
      },
      snapshot: {
        profile: cloneProfile(committed.profile),
        preferences: clonePreferences(committed.preferences),
        generation: version.ownerEpoch,
        revision: version.dataRevision,
        ownerEpoch: version.ownerEpoch,
        stateSeq: version.stateSeq,
        dataRevision: version.dataRevision,
      },
      version,
    };
    const result: SettingsCommandSuccess = {
      ok: true,
      snapshot: {
        profile: cloneProfile(committed.profile),
        preferences: clonePreferences(committed.preferences),
      },
      generation: version.ownerEpoch,
      revision: version.dataRevision,
      ownerEpoch: version.ownerEpoch,
      stateSeq: version.stateSeq,
      dataRevision: version.dataRevision,
      correlationId: command.correlationId,
      applied: true,
    };
    completedCommands.set(command.correlationId, result);
    if (completedCommands.size > 256) {
      const first = completedCommands.keys().next().value;
      if (first) completedCommands.delete(first);
    }
    notify();
    return result;
  };

  return {
    getInitialization: () => cloneOwnerInitialization(state.initialization),
    getSnapshot: () => state.initialization.status === "ready" ? cloneOwnerSnapshot(state) : null,
    initialize: () => {
      const next = queue.then(() => refresh());
      queue = next.catch(() => undefined);
      return next;
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    execute: (command) => {
      const next = queue.then(() => executeNow(command));
      queue = next.catch(() => undefined);
      return next;
    },
  };
}

const directOwners = new WeakMap<object, CompanionUserSettingsOwner>();

export function createCompanionUserSettingsRepository(options: {
  storage?: CompanionUserProfileSyncStorage;
  owner?: CompanionUserSettingsOwner;
}): CompanionUserSettingsRepository {
  let owner = options.owner;
  if (!owner) {
    if (!options.storage) throw new Error("settings storage is required for a direct Repository");
    const key = options.storage as object;
    owner = directOwners.get(key);
    if (!owner) {
      owner = createCompanionUserSettingsOwner(options.storage);
      directOwners.set(key, owner);
    }
  }

  const resolvedOwner = owner;
  return {
    getInitialization: () => resolvedOwner.getInitialization(),
    getTransportState: () => {
      const current = resolvedOwner.getInitialization();
      return current.status === "ready" || current.status === "blocked"
        ? {
            status: "synced",
            ownerEpoch: current.ownerEpoch,
            stateSeq: current.stateSeq,
            dataRevision: current.dataRevision,
          }
        : { status: "not-ready" };
    },
    stop: () => {},
    getSnapshot: () => resolvedOwner.getSnapshot(),
    initialize: () => resolvedOwner.initialize(),
    subscribe: (listener) => resolvedOwner.subscribe(listener),
    updateProfile: (patch, expected, correlationId) => resolvedOwner.execute({
      type: "updateProfile",
      patch,
      ...expected,
      correlationId,
    }),
    upsertPreference: (preference, expected, correlationId) => resolvedOwner.execute({
      type: "upsertPreference",
      preference,
      ...expected,
      correlationId,
    }),
    deletePreference: (id, expected, correlationId) => resolvedOwner.execute({
      type: "deletePreference",
      id,
      ...expected,
      correlationId,
    }),
  };
}
