import { invoke } from "@tauri-apps/api/core";
import { emitTo, listen, type Event, type UnlistenFn } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import type {
  ClientTransportState,
  CompanionUserSettingsOwner,
  CompanionUserSettingsRepository,
  OwnerVersion,
  SettingsCommand,
  SettingsCommandResult,
  SettingsInitialization,
  SettingsOwnerState,
  SettingsTransportProjection,
  SettingsUnavailableReason,
} from "./companionUserSettingsRepository";

export const COMPANION_USER_SETTINGS_COMMAND_EVENT = "companion-settings-command";
export const COMPANION_USER_SETTINGS_RESULT_EVENT = "companion-settings-result";
export const COMPANION_USER_SETTINGS_SNAPSHOT_EVENT = "companion-settings-snapshot";

export type CompanionUserSettingsOwnerBridgeEmission = {
  targetWindow: string;
  event:
    | typeof COMPANION_USER_SETTINGS_RESULT_EVENT
    | typeof COMPANION_USER_SETTINGS_SNAPSHOT_EVENT;
  payload: unknown;
};

export type CompanionUserSettingsOwnerBridgeLifecycle = {
  commandListeners: number;
  ownerSubscriptions: number;
};

export type CompanionUserSettingsOwnerBridgeOptions = {
  responseTarget?: string;
  onEmit?: (emission: CompanionUserSettingsOwnerBridgeEmission) => void;
  onLifecycle?: (lifecycle: CompanionUserSettingsOwnerBridgeLifecycle) => void;
};

export type CompanionUserSettingsBridgeDiagnostics = {
  resultListeners: number;
  snapshotListeners: number;
  pendingWaiters: number;
  queuedSignals: number;
  automaticRunner: number;
  automaticReconcileCount: number;
  queuedExplicitRetry: number;
  businessCommandCount: number;
  lifecycleGeneration: number;
};

const SETTINGS_TRACE_ENABLED = Boolean(
  import.meta.env.DEV
  && typeof window !== "undefined"
  && "__TAURI_INTERNALS__" in window,
);
const SETTINGS_TRACE_EVENT_PREFIX = import.meta.env.DEV
  ? ["settings", "trace"].join("_") + ":"
  : "";

function redactTraceId(value: string | undefined): string | undefined {
  return value ? `…${value.slice(-8)}` : undefined;
}

function traceSettings(
  event: string,
  fields: Record<string, string | number | boolean | undefined>,
): void {
  if (!SETTINGS_TRACE_ENABLED) return;
  const payload = Object.fromEntries(
    Object.entries(fields).filter(([, value]) => value !== undefined),
  );
  void invoke("record_interaction", {
    event: `${SETTINGS_TRACE_EVENT_PREFIX}${event}:${JSON.stringify(payload)}`,
  }).catch(() => {});
}

function ownerTraceFields(initialization: SettingsOwnerState): Record<string, string | number> {
  return {
    status: initialization.status,
    ownerEpoch: redactTraceId(initialization.ownerEpoch) ?? "none",
    stateSeq: initialization.stateSeq,
    dataRevision: initialization.dataRevision,
  };
}

function initializationTraceFields(
  next: SettingsInitialization,
): Record<string, string | number> {
  if ("ownerEpoch" in next) {
    return ownerTraceFields(next);
  }
  return {
    status: next.status,
    reason: next.reason,
    transportState: next.transportState,
  };
}

type SettingsBridgeRequest = {
  kind: "initialize" | "command";
  correlationId: string;
  sourceWindow: string;
  expectedOwnerEpoch?: string;
  command?: SettingsCommand;
};

type SettingsBridgeResponse = {
  correlationId: string;
  initialization?: SettingsOwnerState;
  result?: SettingsCommandResult;
};

type SettingsBridgeSnapshot = {
  initialization: SettingsOwnerState;
};

type SettingsBridgeWaiter = {
  kind: "initialize" | "command";
  lifecycleGeneration: number;
  resolve: (outcome: SettingsBridgeRequestOutcome) => void;
};

type SettingsBridgeRequestOutcome =
  | { kind: "response"; response: SettingsBridgeResponse }
  | { kind: "timeout" }
  | { kind: "cancelled"; initialization: SettingsInitialization };

type InitializationSource = "handshake" | "snapshot" | "command";

type PendingSignal = {
  key: string;
  initialization?: SettingsOwnerState;
  version?: OwnerVersion;
};

type ApplyResult = {
  initialization: SettingsInitialization;
  accepted: boolean;
  stale: boolean;
};

type LifecyclePromise<T> = {
  generation: number;
  promise: Promise<T>;
};

type QueuedExplicitRetry = {
  generation: number;
  promise: Promise<SettingsInitialization>;
  resolve: (initialization: SettingsInitialization) => void;
};

function cloneInitialization(initialization: SettingsInitialization): SettingsInitialization {
  return initialization.status === "ready"
    ? {
        ...initialization,
        snapshot: {
          profile: { ...initialization.snapshot.profile },
          preferences: {
            preferences: initialization.snapshot.preferences.preferences.map((preference) => ({ ...preference })),
            recentPreferenceId: initialization.snapshot.preferences.recentPreferenceId,
          },
        },
      }
    : { ...initialization };
}

function cloneOwnerState(initialization: SettingsOwnerState): SettingsOwnerState {
  return cloneInitialization(initialization) as SettingsOwnerState;
}

function isSettingsOwnerState(value: unknown): value is SettingsOwnerState {
  if (typeof value !== "object" || value === null) return false;
  const state = value as {
    status?: unknown;
    ownerEpoch?: unknown;
    stateSeq?: unknown;
    dataRevision?: unknown;
    issuedAt?: unknown;
    reason?: unknown;
    generation?: unknown;
    revision?: unknown;
    snapshot?: unknown;
  };
  if (state.status !== "ready" && state.status !== "blocked") return false;
  if (typeof state.ownerEpoch !== "string"
    || typeof state.stateSeq !== "string"
    || typeof state.dataRevision !== "string"
    || typeof state.issuedAt !== "number") return false;
  if (state.status === "blocked") return typeof state.reason === "string";
  return typeof state.generation === "string"
    && typeof state.revision === "string"
    && typeof state.snapshot === "object"
    && state.snapshot !== null;
}

function isSettingsCommand(value: unknown): value is SettingsCommand {
  if (typeof value !== "object" || value === null) return false;
  const command = value as Partial<SettingsCommand>;
  return typeof command.type === "string"
    && typeof command.correlationId === "string"
    && typeof command.expectedGeneration === "string"
    && typeof command.expectedRevision === "string"
    && (command.expectedOwnerEpoch === undefined || typeof command.expectedOwnerEpoch === "string")
    && (command.expectedStateSeq === undefined || typeof command.expectedStateSeq === "string")
    && (command.expectedDataRevision === undefined || typeof command.expectedDataRevision === "string")
    && (
      command.type === "updateProfile"
      || command.type === "upsertPreference"
      || command.type === "deletePreference"
    );
}

function isSettingsBridgeRequest(value: unknown): value is SettingsBridgeRequest {
  if (typeof value !== "object" || value === null) return false;
  const request = value as Partial<SettingsBridgeRequest>;
  return (request.kind === "initialize" || request.kind === "command")
    && typeof request.correlationId === "string"
    && typeof request.sourceWindow === "string"
    && (request.expectedOwnerEpoch === undefined || typeof request.expectedOwnerEpoch === "string")
    && (request.kind === "initialize" || isSettingsCommand(request.command));
}

function nextCorrelationId(): string {
  return `settings-bridge-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function compareRevision(left: string, right: string): number {
  const leftNumber = Number.parseInt(left, 10);
  const rightNumber = Number.parseInt(right, 10);
  if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
    return leftNumber - rightNumber;
  }
  return left === right ? 0 : left < right ? -1 : 1;
}

function ownerVersionOf(initialization: SettingsOwnerState): OwnerVersion | null {
  if (typeof initialization.ownerEpoch !== "string"
    || typeof initialization.stateSeq !== "string"
    || typeof initialization.dataRevision !== "string") return null;
  return {
    ownerEpoch: initialization.ownerEpoch,
    stateSeq: initialization.stateSeq,
    dataRevision: initialization.dataRevision,
  };
}

function compareSameEpochVersion(left: OwnerVersion, right: OwnerVersion): number {
  const state = compareRevision(left.stateSeq, right.stateSeq);
  return state === 0
    ? compareRevision(left.dataRevision, right.dataRevision)
    : state;
}

function sameVersion(left: OwnerVersion, right: OwnerVersion): boolean {
  return left.ownerEpoch === right.ownerEpoch
    && left.stateSeq === right.stateSeq
    && left.dataRevision === right.dataRevision;
}

function sameOwnerState(left: SettingsOwnerState, right: SettingsOwnerState): boolean {
  const leftVersion = ownerVersionOf(left);
  const rightVersion = ownerVersionOf(right);
  if (!leftVersion || !rightVersion || !sameVersion(leftVersion, rightVersion)) return false;
  if (left.status !== right.status) return false;
  if (left.status === "blocked" && right.status === "blocked") {
    return left.reason === right.reason;
  }
  if (left.status !== "ready" || right.status !== "ready") return false;
  return left.snapshot.profile.nickname === right.snapshot.profile.nickname
    && left.snapshot.profile.gender === right.snapshot.profile.gender
    && left.snapshot.profile.email === right.snapshot.profile.email
    && left.snapshot.profile.phone === right.snapshot.profile.phone
    && left.snapshot.preferences.recentPreferenceId === right.snapshot.preferences.recentPreferenceId
    && left.snapshot.preferences.preferences.length === right.snapshot.preferences.preferences.length
    && left.snapshot.preferences.preferences.every((preference, index) => {
      const other = right.snapshot.preferences.preferences[index];
      return other !== undefined
        && preference.id === other.id
        && preference.scope === other.scope
        && preference.category === other.category
        && preference.key === other.key
        && preference.value === other.value
        && preference.source === other.source;
    });
}

function legacySignalKey(initialization: SettingsOwnerState): string {
  return `legacy:${initialization.status}:${initialization.status === "blocked" ? initialization.reason : "ready"}:${initialization.issuedAt}`;
}

function transportProjection(
  status: SettingsTransportProjection["transportState"],
): SettingsTransportProjection {
  return {
    status: "blocked",
    reason: status === "bridge-timeout"
      ? "bridge-timeout"
      : status === "owner-unavailable"
      ? "owner-unavailable"
      : "not-ready",
    transportState: status,
    issuedAt: 0,
  };
}

export async function startCompanionUserSettingsOwnerBridge(
  owner: CompanionUserSettingsOwner,
  options: CompanionUserSettingsOwnerBridgeOptions = {},
): Promise<() => void> {
  const responseTarget = options.responseTarget ?? "main";
  let stopped = false;
  traceSettings("owner_bridge_start", {
    window: responseTarget,
    commandListeners: 1,
    ownerSubscriptions: 1,
  });
  try {
    options.onLifecycle?.({ commandListeners: 1, ownerSubscriptions: 1 });
  } catch {
    // DEV diagnostics must never affect the transport lifecycle.
  }
  const unlisten = await listen<SettingsBridgeRequest>(
    COMPANION_USER_SETTINGS_COMMAND_EVENT,
    async (event: Event<SettingsBridgeRequest>) => {
      if (stopped) return;
      const request = event.payload;
      if (!isSettingsBridgeRequest(request)) return;
      const target = request.sourceWindow.trim();
      if (!target || target === responseTarget) return;
      traceSettings("owner_command_received", {
        window: responseTarget,
        targetWindow: target,
        kind: request.kind,
        correlationId: redactTraceId(request.correlationId),
        commandType: request.command?.type,
        expectedOwnerEpoch: redactTraceId(request.expectedOwnerEpoch),
      });

      try {
        if (request.kind === "initialize") {
          const initialization = await owner.initialize();
          if (stopped) return;
          traceSettings("owner_initialize_result", {
            window: responseTarget,
            targetWindow: target,
            correlationId: redactTraceId(request.correlationId),
            ...ownerTraceFields(initialization),
          });
          const response: SettingsBridgeResponse = {
            correlationId: request.correlationId,
            initialization,
          };
          try {
            options.onEmit?.({
              targetWindow: target,
              event: COMPANION_USER_SETTINGS_RESULT_EVENT,
              payload: response,
            });
          } catch {
            // DEV diagnostics must never affect the transport lifecycle.
          }
          await emitTo<SettingsBridgeResponse>(target, COMPANION_USER_SETTINGS_RESULT_EVENT, response);
          return;
        }

        const result = await owner.execute(request.command!);
        if (stopped) return;
        traceSettings("owner_command_result", {
          window: responseTarget,
          targetWindow: target,
          correlationId: redactTraceId(request.correlationId),
          result: result.ok ? "ok" : result.reason,
          ...(result.ok
            ? {
                ownerEpoch: redactTraceId(result.ownerEpoch),
                stateSeq: result.stateSeq,
                dataRevision: result.dataRevision,
              }
            : {}),
        });
        const response: SettingsBridgeResponse = {
          correlationId: request.correlationId,
          result,
        };
        try {
          options.onEmit?.({
            targetWindow: target,
            event: COMPANION_USER_SETTINGS_RESULT_EVENT,
            payload: response,
          });
        } catch {
          // DEV diagnostics must never affect the transport lifecycle.
        }
        await emitTo<SettingsBridgeResponse>(target, COMPANION_USER_SETTINGS_RESULT_EVENT, response);
      } catch {
        // The bridge is best-effort transport. The platform client will
        // surface owner-unavailable/timeout and keep its last committed view.
      }
    },
  );
  const unsubscribe = owner.subscribe((initialization) => {
    if (stopped) return;
    traceSettings("owner_snapshot_emit", {
      window: responseTarget,
      targetWindow: "platform",
      ...ownerTraceFields(initialization),
    });
    const payload: SettingsBridgeSnapshot = { initialization };
    try {
      options.onEmit?.({
        targetWindow: "platform",
        event: COMPANION_USER_SETTINGS_SNAPSHOT_EVENT,
        payload,
      });
    } catch {
      // DEV diagnostics must never affect the transport lifecycle.
    }
    void emitTo<SettingsBridgeSnapshot>(
      "platform",
      COMPANION_USER_SETTINGS_SNAPSHOT_EVENT,
      payload,
    ).catch(() => {});
  });
  const initialSnapshot: SettingsBridgeSnapshot = {
    initialization: owner.getInitialization(),
  };
  try {
    options.onEmit?.({
      targetWindow: "platform",
      event: COMPANION_USER_SETTINGS_SNAPSHOT_EVENT,
      payload: initialSnapshot,
    });
  } catch {
    // DEV diagnostics must never affect the transport lifecycle.
  }
  void emitTo<SettingsBridgeSnapshot>(
    "platform",
    COMPANION_USER_SETTINGS_SNAPSHOT_EVENT,
    initialSnapshot,
  ).catch(() => {});
  return () => {
    stopped = true;
    traceSettings("owner_bridge_stop", {
      window: responseTarget,
      commandListeners: 0,
      ownerSubscriptions: 0,
    });
    try {
      options.onLifecycle?.({ commandListeners: 0, ownerSubscriptions: 0 });
    } catch {
      // DEV diagnostics must never affect the transport lifecycle.
    }
    unsubscribe();
    unlisten();
  };
}

export function createCompanionUserSettingsBridge(options: {
  ownerWindow?: string;
  responseTimeoutMs?: number;
  sourceWindow?: string;
} = {}): CompanionUserSettingsRepository & {
  getDiagnostics: () => CompanionUserSettingsBridgeDiagnostics;
} {
  const ownerWindow = options.ownerWindow ?? "main";
  const responseTimeoutMs = options.responseTimeoutMs ?? 1500;
  const sourceWindow = options.sourceWindow ?? (() => {
    try {
      return getCurrentWindow().label;
    } catch {
      return "platform";
    }
  })();
  const listeners = new Set<(initialization: SettingsInitialization) => void>();
  const waiters = new Map<string, SettingsBridgeWaiter>();
  const pendingSignals = new Map<string, PendingSignal>();
  const retiredEpochs = new Set<string>();
  const consumedLegacySignals = new Set<string>();
  let syncedOwnerState: SettingsOwnerState | null = null;
  let initialization: SettingsInitialization = transportProjection("not-ready");
  let transportState: ClientTransportState = { status: "not-ready" };
  let listenerReady: Promise<readonly UnlistenFn[]> = Promise.resolve([]);
  let listenerCleanup: Promise<void> = Promise.resolve();
  let listenerGeneration = 0;
  let attachedListeners = 0;
  let automaticReconcileCount = 0;
  let businessCommandCount = 0;
  let sequence = 0;
  let lifecycleGeneration = 1;
  let stopped = false;
  let explicitHandshakeInFlight: LifecyclePromise<SettingsInitialization> | null = null;
  let queuedExplicitRetry: QueuedExplicitRetry | null = null;
  let reconcileInFlight: LifecyclePromise<SettingsInitialization> | null = null;
  let reconcileExpectedOwnerEpoch: { generation: number; ownerEpoch: string } | undefined;
  const cancelledLifecycleSnapshots = new Map<number, SettingsInitialization>();

  const isActiveLifecycle = (generation: number): boolean =>
    !stopped && generation === lifecycleGeneration;

  const cancelledOutcome = (
    generation: number,
    fallback?: SettingsInitialization,
  ): SettingsBridgeRequestOutcome => ({
    kind: "cancelled",
    initialization: cloneInitialization(
      cancelledLifecycleSnapshots.get(generation) ?? fallback ?? initialization,
    ),
  });

  const notify = (next: SettingsInitialization) => {
    const snapshot = cloneInitialization(next);
    traceSettings("client_notify", {
      window: sourceWindow,
      lifecycleGeneration,
      uiListeners: listeners.size,
      ...initializationTraceFields(snapshot),
    });
    for (const listener of listeners) {
      try {
        listener(snapshot);
      } catch {
        // A UI listener cannot invalidate the already accepted Owner state.
      }
    }
  };

  const setTransportConnecting = (
    correlationId: string,
    expectedOwnerEpoch: string | undefined,
    generation: number,
  ) => {
    if (!isActiveLifecycle(generation)) return;
    transportState = {
      status: "connecting",
      correlationId,
      ...(expectedOwnerEpoch ? { expectedOwnerEpoch } : {}),
    };
  };

  const applyTransportFailure = (
    reason: "bridge-timeout" | "owner-unavailable",
    generation: number,
  ): SettingsInitialization => {
    if (!isActiveLifecycle(generation)) return cloneInitialization(initialization);
    transportState = {
      status: reason,
      ...(syncedOwnerState ? { ownerEpoch: syncedOwnerState.ownerEpoch } : {}),
    };
    initialization = transportProjection(reason);
    traceSettings("client_transport_failure", {
      window: sourceWindow,
      lifecycleGeneration: generation,
      reason,
      ownerEpoch: redactTraceId(syncedOwnerState?.ownerEpoch),
    });
    notify(initialization);
    return cloneInitialization(initialization);
  };

  const applyOwnerState = (
    next: SettingsOwnerState,
    source: InitializationSource,
    expectedOwnerEpoch?: string,
    generation = lifecycleGeneration,
  ): ApplyResult => {
    if (!isActiveLifecycle(generation)) {
      return { initialization: cloneInitialization(initialization), accepted: false, stale: false };
    }
    const nextVersion = ownerVersionOf(next);
    if (!nextVersion) return { initialization: cloneInitialization(initialization), accepted: false, stale: true };
    if (expectedOwnerEpoch && nextVersion.ownerEpoch !== expectedOwnerEpoch) {
      return { initialization: cloneInitialization(initialization), accepted: false, stale: true };
    }
    if (retiredEpochs.has(nextVersion.ownerEpoch)) {
      return { initialization: cloneInitialization(initialization), accepted: false, stale: true };
    }

    const current = syncedOwnerState;
    if (current) {
      const currentVersion = ownerVersionOf(current)!;
      if (source === "handshake" && !expectedOwnerEpoch) {
        if (reconcileExpectedOwnerEpoch?.generation === generation
          && nextVersion.ownerEpoch !== reconcileExpectedOwnerEpoch.ownerEpoch) {
          return { initialization: cloneInitialization(initialization), accepted: false, stale: true };
        }
        const pendingEpochs = new Set(
          [...pendingSignals.values()]
            .map((pending) => pending.version?.ownerEpoch)
            .filter((epoch): epoch is string => Boolean(epoch)),
        );
        // A response from a request issued before a different Owner signal
        // was observed is not allowed to win that epoch race. The matching
        // expectedOwnerEpoch reconcile is the only takeover authority.
        if (pendingEpochs.size > 0 && !pendingEpochs.has(nextVersion.ownerEpoch)) {
          return { initialization: cloneInitialization(initialization), accepted: false, stale: true };
        }
      }
      if (nextVersion.ownerEpoch === currentVersion.ownerEpoch) {
        if (compareRevision(nextVersion.dataRevision, currentVersion.dataRevision) < 0
          || compareSameEpochVersion(nextVersion, currentVersion) < 0) {
          return { initialization: cloneInitialization(initialization), accepted: false, stale: true };
        }
        if (sameVersion(nextVersion, currentVersion)) {
          if (!sameOwnerState(next, current)) {
            return { initialization: cloneInitialization(initialization), accepted: false, stale: true };
          }
          const restored = transportState.status !== "synced";
          transportState = {
            status: "synced",
            ownerEpoch: currentVersion.ownerEpoch,
            stateSeq: currentVersion.stateSeq,
            dataRevision: currentVersion.dataRevision,
          };
          if (restored) {
            initialization = cloneOwnerState(current);
            notify(initialization);
          }
          return { initialization: cloneInitialization(initialization), accepted: true, stale: false };
        }
      } else if (source !== "handshake") {
        return { initialization: cloneInitialization(initialization), accepted: false, stale: true };
      } else {
        retiredEpochs.add(currentVersion.ownerEpoch);
        for (const pending of pendingSignals.values()) {
          if (pending.version && pending.version.ownerEpoch !== nextVersion.ownerEpoch) {
            retiredEpochs.add(pending.version.ownerEpoch);
          }
        }
      }
    } else if (source === "command") {
      return { initialization: cloneInitialization(initialization), accepted: false, stale: true };
    } else if (source === "handshake") {
      for (const pending of pendingSignals.values()) {
        if (pending.version && pending.version.ownerEpoch !== nextVersion.ownerEpoch) {
          retiredEpochs.add(pending.version.ownerEpoch);
        }
      }
    }

    const previousWasSynced = transportState.status === "synced";
    syncedOwnerState = cloneOwnerState(next);
    transportState = {
      status: "synced",
      ownerEpoch: nextVersion.ownerEpoch,
      stateSeq: nextVersion.stateSeq,
      dataRevision: nextVersion.dataRevision,
    };
    initialization = cloneOwnerState(syncedOwnerState);
    if (!current || !sameOwnerState(current, syncedOwnerState) || !previousWasSynced) {
      notify(initialization);
    }
    return { initialization: cloneInitialization(initialization), accepted: true, stale: false };
  };

  const failed = (
    command: SettingsCommand,
    reason: SettingsUnavailableReason,
  ): SettingsCommandResult => ({
    ok: false,
    reason,
    correlationId: command.correlationId,
  });

  const request = async (
    kind: "initialize" | "command",
    command?: SettingsCommand,
    expectedOwnerEpoch?: string,
    generation = lifecycleGeneration,
  ): Promise<SettingsBridgeRequestOutcome> => {
    const fallback = cloneInitialization(initialization);
    if (!isActiveLifecycle(generation)) return cancelledOutcome(generation, fallback);
    const listenerForGeneration = listenerReady;
    try {
      await listenerForGeneration;
    } catch {
      return isActiveLifecycle(generation)
        ? { kind: "timeout" }
        : cancelledOutcome(generation, fallback);
    }
    if (!isActiveLifecycle(generation)) return cancelledOutcome(generation, fallback);
    const correlationId = command?.correlationId ?? `${nextCorrelationId()}-${sequence++}`;
    const payload: SettingsBridgeRequest = {
      kind,
      correlationId,
      sourceWindow,
      ...(expectedOwnerEpoch ? { expectedOwnerEpoch } : {}),
      ...(command ? { command } : {}),
    };
    if (kind === "initialize") {
      setTransportConnecting(correlationId, expectedOwnerEpoch, generation);
    } else {
      businessCommandCount += 1;
    }
    traceSettings("client_command_emit", {
      window: sourceWindow,
      targetWindow: ownerWindow,
      lifecycleGeneration: generation,
      kind,
      correlationId: redactTraceId(correlationId),
      commandType: command?.type,
      expectedOwnerEpoch: redactTraceId(expectedOwnerEpoch),
    });
    return new Promise<SettingsBridgeRequestOutcome>((resolve) => {
      let settled = false;
      const finish = (outcome: SettingsBridgeRequestOutcome) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (waiters.get(correlationId)?.lifecycleGeneration === generation) {
          waiters.delete(correlationId);
        }
        resolve(outcome);
      };
      const timer = setTimeout(() => {
        finish({ kind: "timeout" });
      }, responseTimeoutMs);
      waiters.set(correlationId, {
        kind,
        lifecycleGeneration: generation,
        resolve: (outcome) => finish(outcome),
      });
      void emitTo(ownerWindow, COMPANION_USER_SETTINGS_COMMAND_EVENT, payload).catch(() => {
        finish({ kind: "timeout" });
      });
    });
  };

  const consumePendingThrough = (version: OwnerVersion | undefined, selectedKey?: string) => {
    if (selectedKey) pendingSignals.delete(selectedKey);
    for (const [key, pending] of pendingSignals) {
      if (!pending.version) {
        pendingSignals.delete(key);
        consumedLegacySignals.add(key);
        continue;
      }
      if (!version) continue;
      if (pending.version.ownerEpoch === version.ownerEpoch
        && compareSameEpochVersion(pending.version, version) <= 0) {
        pendingSignals.delete(key);
      } else if (retiredEpochs.has(pending.version.ownerEpoch)) {
        pendingSignals.delete(key);
      }
    }
  };

  const discardPendingVersion = (version: OwnerVersion, selectedKey?: string) => {
    if (selectedKey) pendingSignals.delete(selectedKey);
    for (const [key, pending] of pendingSignals) {
      if (pending.version && sameVersion(pending.version, version)) pendingSignals.delete(key);
    }
  };

  const selectPendingSignal = (): PendingSignal | null => {
    const values = [...pendingSignals.values()];
    if (values.length === 0) return null;
    let selected = values[0]!;
    for (const candidate of values.slice(1)) {
      if (!candidate.version || !selected.version) {
        selected = candidate;
        continue;
      }
      if (candidate.version.ownerEpoch === selected.version.ownerEpoch) {
        if (compareSameEpochVersion(candidate.version, selected.version) > 0) selected = candidate;
        continue;
      }
      if (syncedOwnerState && candidate.version.ownerEpoch !== syncedOwnerState.ownerEpoch
        && selected.version.ownerEpoch === syncedOwnerState.ownerEpoch) {
        selected = candidate;
        continue;
      }
      // For two unseen epochs, the latest observed signal is the only safe
      // candidate; the matched response, not issuedAt, decides takeover.
      selected = candidate;
    }
    return selected;
  };

  const hasNewPendingSignal = (): boolean => {
    const currentVersion = syncedOwnerState ? ownerVersionOf(syncedOwnerState) : null;
    for (const pending of pendingSignals.values()) {
      if (!pending.version) return true;
      if (retiredEpochs.has(pending.version.ownerEpoch)) continue;
      if (!currentVersion || pending.version.ownerEpoch !== currentVersion.ownerEpoch) return true;
      if (compareRevision(pending.version.dataRevision, currentVersion.dataRevision) < 0) continue;
      if (compareSameEpochVersion(pending.version, currentVersion) > 0) return true;
    }
    return false;
  };

  const hasPendingOwnerEpochTakeover = (): boolean => {
    const currentEpoch = syncedOwnerState?.ownerEpoch;
    return [...pendingSignals.values()].some((pending) =>
      Boolean(pending.version)
      && (!currentEpoch || pending.version!.ownerEpoch !== currentEpoch),
    );
  };

  const runExplicitHandshake = async (
    generation: number,
  ): Promise<SettingsInitialization> => {
    const outcome = await request("initialize", undefined, undefined, generation);
    if (outcome.kind === "cancelled" || !isActiveLifecycle(generation)) {
      return outcome.kind === "cancelled"
        ? outcome.initialization
        : cloneInitialization(initialization);
    }
    if (outcome.kind === "timeout") {
      return applyTransportFailure("bridge-timeout", generation);
    }
    if (!outcome.response.initialization) {
      return applyTransportFailure("owner-unavailable", generation);
    }
    const applied = applyOwnerState(outcome.response.initialization, "handshake", undefined, generation);
    if (applied.accepted && isActiveLifecycle(generation)) {
      consumePendingThrough(ownerVersionOf(outcome.response.initialization) ?? undefined);
    }
    return applied.initialization;
  };

  const startExplicitHandshake = (
    generation = lifecycleGeneration,
  ): Promise<SettingsInitialization> => {
    if (!isActiveLifecycle(generation)) {
      return Promise.resolve(cloneInitialization(initialization));
    }
    if (explicitHandshakeInFlight?.generation === generation) {
      return explicitHandshakeInFlight.promise;
    }
    const run = runExplicitHandshake(generation);
    let slot!: LifecyclePromise<SettingsInitialization>;
    slot = {
      generation,
      promise: run.finally(() => {
        if (explicitHandshakeInFlight !== slot || lifecycleGeneration !== generation) return;
        explicitHandshakeInFlight = null;
        if (isActiveLifecycle(generation) && !queuedExplicitRetry && hasNewPendingSignal()) {
          ensureAutoReconcile();
        }
      }),
    };
    explicitHandshakeInFlight = slot;
    return slot.promise;
  };

  const startQueuedExplicitRetry = () => {
    const queued = queuedExplicitRetry;
    if (!queued || queued.generation !== lifecycleGeneration) return;
    queuedExplicitRetry = null;
    if (!isActiveLifecycle(queued.generation)) {
      queued.resolve(cloneInitialization(initialization));
      return;
    }
    void startExplicitHandshake(queued.generation).then(
      queued.resolve,
      () => queued.resolve(cloneInitialization(initialization)),
    );
  };

  const queueExplicitRetry = (
    generation: number,
  ): Promise<SettingsInitialization> => {
    if (queuedExplicitRetry?.generation === generation) return queuedExplicitRetry.promise;
    if (reconcileInFlight?.generation !== generation) return startExplicitHandshake(generation);
    let resolve!: (initialization: SettingsInitialization) => void;
    const promise = new Promise<SettingsInitialization>((nextResolve) => {
      resolve = nextResolve;
    });
    queuedExplicitRetry = { generation, promise, resolve };
    return promise;
  };

  const runAutoReconcile = async (
    generation: number,
  ): Promise<SettingsInitialization> => {
    while (isActiveLifecycle(generation)) {
      const selected = selectPendingSignal();
      if (!selected) return cloneInitialization(initialization);
      pendingSignals.delete(selected.key);
      const expectedOwnerEpoch = selected.version?.ownerEpoch;
      reconcileExpectedOwnerEpoch = expectedOwnerEpoch
        ? { generation, ownerEpoch: expectedOwnerEpoch }
        : undefined;
      const outcome = await request("initialize", undefined, expectedOwnerEpoch, generation);
      if (outcome.kind === "cancelled" || !isActiveLifecycle(generation)) {
        return outcome.kind === "cancelled"
          ? outcome.initialization
          : cloneInitialization(initialization);
      }
      if (outcome.kind === "timeout") {
        applyTransportFailure("bridge-timeout", generation);
        return cloneInitialization(initialization);
      }
      if (!outcome.response.initialization) {
        applyTransportFailure("owner-unavailable", generation);
        return cloneInitialization(initialization);
      }

      const applied = applyOwnerState(
        outcome.response.initialization,
        "handshake",
        expectedOwnerEpoch,
        generation,
      );
      // The attempted signal is consumed by this correlation. A late duplicate
      // with the same version is therefore absorbed even when the result won
      // the event race. A genuinely newer signal remains pending for one next
      // bounded reconcile pass.
      if (!isActiveLifecycle(generation)) return cloneInitialization(initialization);
      if (selected.version && outcome.response.initialization.ownerEpoch === selected.version.ownerEpoch) {
        consumePendingThrough(selected.version);
      } else if (!selected.version) {
        consumePendingThrough(undefined, selected.key);
      }
      if (!applied.accepted && selected.version) {
        // Do not retry a mismatched or stale response forever. A future signal
        // can schedule another explicit correlation, but this attempt is done.
        discardPendingVersion(selected.version, selected.key);
      }
      if (queuedExplicitRetry?.generation === generation) return cloneInitialization(initialization);
      if (!hasNewPendingSignal()) return cloneInitialization(initialization);
    }
    return cloneInitialization(initialization);
  };

  const ensureAutoReconcile = () => {
    const generation = lifecycleGeneration;
    if (
      !isActiveLifecycle(generation)
      || reconcileInFlight?.generation === generation
      || queuedExplicitRetry?.generation === generation
      || !hasNewPendingSignal()
      || (explicitHandshakeInFlight?.generation === generation && !hasPendingOwnerEpochTakeover())
    ) return;
    const run = runAutoReconcile(generation);
    automaticReconcileCount += 1;
    let slot!: LifecyclePromise<SettingsInitialization>;
    slot = {
      generation,
      promise: run.finally(() => {
        if (reconcileInFlight !== slot || lifecycleGeneration !== generation) return;
        reconcileInFlight = null;
        reconcileExpectedOwnerEpoch = undefined;
        if (queuedExplicitRetry?.generation === generation) {
          startQueuedExplicitRetry();
        } else if (isActiveLifecycle(generation) && hasNewPendingSignal()) {
          ensureAutoReconcile();
        }
      }),
    };
    reconcileInFlight = slot;
  };

  const enqueueSignal = (next: SettingsOwnerState) => {
    const version = ownerVersionOf(next);
    if (!version) {
      const key = legacySignalKey(next);
      if (consumedLegacySignals.has(key)) return;
      pendingSignals.set(key, { key, initialization: cloneOwnerState(next) });
      ensureAutoReconcile();
      return;
    }
    if (retiredEpochs.has(version.ownerEpoch)) return;
    if (syncedOwnerState) {
      const current = ownerVersionOf(syncedOwnerState)!;
      if (version.ownerEpoch === current.ownerEpoch) {
        if (compareRevision(version.dataRevision, current.dataRevision) < 0
          || compareSameEpochVersion(version, current) <= 0) return;
      }
    }
    const key = `${version.ownerEpoch}:${version.stateSeq}:${version.dataRevision}`;
    pendingSignals.set(key, { key, initialization: cloneOwnerState(next), version });
    ensureAutoReconcile();
  };

  const initialize = (): Promise<SettingsInitialization> => {
    const generation = lifecycleGeneration;
    if (!isActiveLifecycle(generation)) return Promise.resolve(cloneInitialization(initialization));
    if (explicitHandshakeInFlight?.generation === generation) return explicitHandshakeInFlight.promise;
    if (queuedExplicitRetry?.generation === generation) return queuedExplicitRetry.promise;
    if (reconcileInFlight?.generation === generation) return queueExplicitRetry(generation);
    return startExplicitHandshake(generation);
  };

  const handleResultEvent = (
    event: Event<SettingsBridgeResponse>,
    generation: number,
  ) => {
    if (!isActiveLifecycle(generation)) return;
    const response = event.payload;
    if (!response || typeof response.correlationId !== "string") return;
    const waiter = waiters.get(response.correlationId);
    traceSettings("client_result_received", {
      window: sourceWindow,
      lifecycleGeneration: generation,
      correlationId: redactTraceId(response.correlationId),
      matched: Boolean(waiter && waiter.lifecycleGeneration === generation),
      waiterKind: waiter?.kind,
      result: response.result ? (response.result.ok ? "ok" : response.result.reason) : undefined,
      ...(response.initialization ? initializationTraceFields(response.initialization) : {}),
    });
    if (!waiter || waiter.lifecycleGeneration !== generation) return;
    waiters.delete(response.correlationId);
    let resolvedResponse = response;
    if (waiter.kind === "command" && response.result?.ok) {
      const result = response.result;
      const current = syncedOwnerState;
      const resultState: SettingsOwnerState = {
        status: "ready",
        snapshot: result.snapshot,
        generation: result.generation,
        revision: result.revision,
        ownerEpoch: result.ownerEpoch,
        stateSeq: result.stateSeq,
        dataRevision: result.dataRevision,
        issuedAt: current?.issuedAt ?? 0,
      };
      const applied = applyOwnerState(resultState, "command", undefined, generation);
      if (applied.stale || !applied.accepted) {
        resolvedResponse = {
          ...response,
          result: {
            ok: false,
            reason: "stale-revision",
            correlationId: result.correlationId,
          },
        };
      }
    } else if (waiter.kind === "command" && response.initialization) {
      applyOwnerState(response.initialization, "command", undefined, generation);
    }
    waiter.resolve({ kind: "response", response: resolvedResponse });
  };

  const handleSnapshotEvent = (
    event: Event<SettingsBridgeSnapshot>,
    generation: number,
  ) => {
    if (!isActiveLifecycle(generation)) return;
    const next = event.payload?.initialization;
    if (!isSettingsOwnerState(next)) return;
    traceSettings("client_snapshot_received", {
      window: sourceWindow,
      lifecycleGeneration: generation,
      ...ownerTraceFields(next),
    });
    enqueueSignal(next);
  };

  const installListeners = (generation: number) => {
    const listenerToken = ++listenerGeneration;
    const installation = listenerCleanup.then(async () => {
      if (!isActiveLifecycle(generation) || listenerToken !== listenerGeneration) {
        return [] as readonly UnlistenFn[];
      }
      const unlisteners = await Promise.all([
        listen<SettingsBridgeResponse>(
          COMPANION_USER_SETTINGS_RESULT_EVENT,
          (event) => handleResultEvent(event, generation),
        ),
        listen<SettingsBridgeSnapshot>(
          COMPANION_USER_SETTINGS_SNAPSHOT_EVENT,
          (event) => handleSnapshotEvent(event, generation),
        ),
      ]);
      if (!isActiveLifecycle(generation) || listenerToken !== listenerGeneration) {
        for (const unlisten of unlisteners) unlisten();
        return [] as readonly UnlistenFn[];
      }
      traceSettings("client_listeners_attached", {
        window: sourceWindow,
        lifecycleGeneration: generation,
        resultListeners: 1,
        snapshotListeners: 1,
      });
      attachedListeners = 1;
      return unlisteners;
    });
    listenerReady = installation;
  };

  const detachListeners = () => {
    const pendingInstallation = listenerReady;
    listenerReady = Promise.resolve([]);
    listenerGeneration += 1;
    attachedListeners = 0;
    const cleanup = pendingInstallation.then((unlisteners) => {
      for (const unlisten of unlisteners) unlisten();
    }).catch(() => {});
    listenerCleanup = listenerCleanup.then(() => cleanup);
  };

  const start = () => {
    if (!stopped) return;
    lifecycleGeneration += 1;
    stopped = false;
    reconcileExpectedOwnerEpoch = undefined;
    traceSettings("client_start", {
      window: sourceWindow,
      lifecycleGeneration,
    });
    installListeners(lifecycleGeneration);
  };

  installListeners(lifecycleGeneration);

  const stop = () => {
    if (stopped) return;
    const stoppedGeneration = lifecycleGeneration;
    const safeInitialization = cloneInitialization(initialization);
    traceSettings("client_stop", {
      window: sourceWindow,
      lifecycleGeneration: stoppedGeneration,
      resultListeners: 0,
      snapshotListeners: 0,
      pendingWaiters: waiters.size,
      ...initializationTraceFields(safeInitialization),
    });
    cancelledLifecycleSnapshots.set(stoppedGeneration, safeInitialization);
    lifecycleGeneration += 1;
    stopped = true;
    pendingSignals.clear();
    listeners.clear();
    explicitHandshakeInFlight = null;
    reconcileInFlight = null;
    reconcileExpectedOwnerEpoch = undefined;
    for (const [correlationId, waiter] of waiters) {
      waiters.delete(correlationId);
      waiter.resolve({ kind: "cancelled", initialization: safeInitialization });
    }
    if (queuedExplicitRetry) {
      const queued = queuedExplicitRetry;
      queuedExplicitRetry = null;
      queued.resolve(safeInitialization);
    }
    detachListeners();
  };

  return {
    getInitialization: () => cloneInitialization(initialization),
    getTransportState: () => ({ ...transportState }),
    getDiagnostics: (): CompanionUserSettingsBridgeDiagnostics => ({
      resultListeners: attachedListeners,
      snapshotListeners: attachedListeners,
      pendingWaiters: waiters.size,
      queuedSignals: pendingSignals.size,
      automaticRunner: reconcileInFlight?.generation === lifecycleGeneration ? 1 : 0,
      automaticReconcileCount,
      queuedExplicitRetry: queuedExplicitRetry?.generation === lifecycleGeneration ? 1 : 0,
      businessCommandCount,
      lifecycleGeneration,
    }),
    start,
    stop,
    getSnapshot: () => initialization.status === "ready" && syncedOwnerState?.status === "ready"
      ? {
          profile: { ...syncedOwnerState.snapshot.profile },
          preferences: {
            preferences: syncedOwnerState.snapshot.preferences.preferences.map((preference) => ({ ...preference })),
            recentPreferenceId: syncedOwnerState.snapshot.preferences.recentPreferenceId,
          },
          generation: syncedOwnerState.generation,
          revision: syncedOwnerState.revision,
          ownerEpoch: syncedOwnerState.ownerEpoch,
          stateSeq: syncedOwnerState.stateSeq,
          dataRevision: syncedOwnerState.dataRevision,
        }
      : null,
    initialize,
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    updateProfile: async (patch, expected, correlationId) => {
      const command: SettingsCommand = {
        type: "updateProfile",
        patch,
        ...expected,
        correlationId,
      };
      if (initialization.status !== "ready") return failed(command, initialization.reason);
      const outcome = await request("command", command);
      if (outcome.kind === "cancelled") {
        return failed(command, "owner-unavailable");
      }
      if (outcome.kind === "timeout") return failed(command, "bridge-timeout");
      if (!outcome.response.result) return failed(command, "owner-unavailable");
      return outcome.response.result;
    },
    upsertPreference: async (preference, expected, correlationId) => {
      const command: SettingsCommand = {
        type: "upsertPreference",
        preference,
        ...expected,
        correlationId,
      };
      if (initialization.status !== "ready") return failed(command, initialization.reason);
      const outcome = await request("command", command);
      if (outcome.kind === "cancelled") {
        return failed(command, "owner-unavailable");
      }
      if (outcome.kind === "timeout") return failed(command, "bridge-timeout");
      if (!outcome.response.result) return failed(command, "owner-unavailable");
      return outcome.response.result;
    },
    deletePreference: async (id, expected, correlationId) => {
      const command: SettingsCommand = {
        type: "deletePreference",
        id,
        ...expected,
        correlationId,
      };
      if (initialization.status !== "ready") return failed(command, initialization.reason);
      const outcome = await request("command", command);
      if (outcome.kind === "cancelled") {
        return failed(command, "owner-unavailable");
      }
      if (outcome.kind === "timeout") return failed(command, "bridge-timeout");
      if (!outcome.response.result) return failed(command, "owner-unavailable");
      return outcome.response.result;
    },
  };
}
