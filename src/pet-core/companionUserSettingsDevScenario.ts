import { invoke } from "@tauri-apps/api/core";
import { emitTo, listen, type UnlistenFn } from "@tauri-apps/api/event";
import {
  COMPANION_USER_SETTINGS_RESULT_EVENT,
  COMPANION_USER_SETTINGS_SNAPSHOT_EVENT,
  type CompanionUserSettingsBridgeDiagnostics,
  type CompanionUserSettingsOwnerBridgeEmission,
  type CompanionUserSettingsOwnerBridgeLifecycle,
  type CompanionUserSettingsOwnerBridgeOptions,
} from "./companionUserSettingsBridge";
import type {
  CompanionUserSettingsOwner,
  CompanionUserSettingsRepository,
  SettingsInitialization,
  SettingsOwnerState,
} from "./companionUserSettingsRepository";

const DEV_SCENARIO_ENV = "VITE_XIAOJU_SETTINGS_F_OWNER_TAKEOVER_SCENARIO";
const DEV_SCENARIO_RUN_ENV = "VITE_XIAOJU_SETTINGS_F_OWNER_TAKEOVER_RUN_ID";
const DEV_SCENARIO_ID = "r4-f-owner-takeover";
const DEV_SCENARIO_CONTROL_EVENT = "xiaoju-dev-settings-f-control";
const DEV_SCENARIO_REPORT_EVENT = "xiaoju-dev-settings-f-report";
const DEV_SCENARIO_LOG_PREFIX = "f_owner_takeover";

type BridgeWithDiagnostics = CompanionUserSettingsRepository & {
  getDiagnostics?: () => CompanionUserSettingsBridgeDiagnostics;
};

type ScenarioOwnerFactory = (options: {
  ownerEpoch: string;
  issuedAt: number;
}) => CompanionUserSettingsOwner;

type ScenarioStartOwnerBridge = (
  owner: CompanionUserSettingsOwner,
  options?: CompanionUserSettingsOwnerBridgeOptions,
) => Promise<() => void>;

export type CompanionUserSettingsDevScenarioOptions = {
  repository: CompanionUserSettingsRepository;
  isPlatformWindow: boolean;
  isTauriRuntime: boolean;
  owner: CompanionUserSettingsOwner | null;
  createOwner?: ScenarioOwnerFactory;
  startOwnerBridge?: ScenarioStartOwnerBridge;
  getOwnerBridgeStop?: () => (() => void) | null;
  getOwnerBridgeLifecycle?: () => CompanionUserSettingsOwnerBridgeLifecycle;
  ownerBridgeEvents?: CompanionUserSettingsOwnerBridgeEmission[];
};

type ScenarioControl = {
  runId: string;
  requestId: string;
  action:
    | "probe"
    | "initialize-a"
    | "settle"
    | "initialize-b"
    | "inspect"
    | "stop-client"
    | "shutdown";
};

type ScenarioReport = {
  runId: string;
  requestId: string;
  action: ScenarioControl["action"];
  state: SafeState;
};

type SafeState = {
  status: SettingsInitialization["status"];
  transport: string;
  ownerEpochSuffix: string | null;
  stateSeq: string | null;
  dataRevision: string | null;
  issuedAt: number | null;
  snapshotPresent: boolean;
  projectionMatchesBaseline: boolean | null;
  blockedProjectionCount: number;
  resultListeners: number;
  snapshotListeners: number;
  pendingWaiters: number;
  queuedSignals: number;
  automaticRunner: number;
  automaticReconcileCount: number;
  queuedExplicitRetry: number;
  businessCommandCount: number;
};

type SettingsSnapshot = ReturnType<CompanionUserSettingsRepository["getSnapshot"]>;

type CapturedResult = {
  correlationId: string;
  initialization: SettingsOwnerState;
};

type CapturedSnapshot = {
  initialization: SettingsOwnerState;
};

class ScenarioUnavailableError extends Error {}

class ScenarioAssertionError extends Error {}

function scenarioEnabled(): boolean {
  return Boolean(
    import.meta.env.DEV
    && import.meta.env[DEV_SCENARIO_ENV] === DEV_SCENARIO_ID,
  );
}

function suffix(value: string | undefined): string | null {
  return value ? `…${value.slice(-8)}` : null;
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function sameBusinessSnapshot(
  left: ReturnType<CompanionUserSettingsRepository["getSnapshot"]>,
  right: ReturnType<CompanionUserSettingsRepository["getSnapshot"]>,
): boolean {
  if (!left || !right) return left === right;
  return JSON.stringify({
    profile: left.profile,
    preferences: left.preferences,
  }) === JSON.stringify({
    profile: right.profile,
    preferences: right.preferences,
  });
}

function safeStateEqual(left: SafeState, right: SafeState): boolean {
  return left.status === right.status
    && left.transport === right.transport
    && left.ownerEpochSuffix === right.ownerEpochSuffix
    && left.stateSeq === right.stateSeq
    && left.dataRevision === right.dataRevision
    && left.snapshotPresent === right.snapshotPresent
    && left.projectionMatchesBaseline === right.projectionMatchesBaseline;
}

function compactState(state: SafeState): Record<string, string | number | boolean | null> {
  return {
    status: state.status,
    transport: state.transport,
    ownerEpochSuffix: state.ownerEpochSuffix,
    stateSeq: state.stateSeq,
    dataRevision: state.dataRevision,
    issuedAt: state.issuedAt,
    snapshotPresent: state.snapshotPresent,
    projectionMatchesBaseline: state.projectionMatchesBaseline,
    resultListeners: state.resultListeners,
    snapshotListeners: state.snapshotListeners,
    pendingWaiters: state.pendingWaiters,
    queuedSignals: state.queuedSignals,
    automaticRunner: state.automaticRunner,
    automaticReconcileCount: state.automaticReconcileCount,
    queuedExplicitRetry: state.queuedExplicitRetry,
    businessCommandCount: state.businessCommandCount,
  };
}

function readyInitialization(value: unknown): SettingsOwnerState | null {
  if (typeof value !== "object" || value === null) return null;
  const candidate = value as { initialization?: unknown };
  const initialization = candidate.initialization;
  if (typeof initialization !== "object" || initialization === null) return null;
  const state = initialization as Partial<SettingsOwnerState>;
  return state.status === "ready"
    && typeof state.ownerEpoch === "string"
    && typeof state.stateSeq === "string"
    && typeof state.dataRevision === "string"
    && typeof state.issuedAt === "number"
    && typeof state.snapshot === "object"
    && state.snapshot !== null
    ? initialization as SettingsOwnerState
    : null;
}

function capturedResult(value: unknown): CapturedResult | null {
  if (typeof value !== "object" || value === null) return null;
  const candidate = value as { correlationId?: unknown; initialization?: unknown };
  const initialization = readyInitialization({ initialization: candidate.initialization });
  return typeof candidate.correlationId === "string" && initialization?.status === "ready"
    ? { correlationId: candidate.correlationId, initialization }
    : null;
}

function capturedSnapshot(value: unknown): CapturedSnapshot | null {
  const initialization = readyInitialization(value);
  return initialization ? { initialization } : null;
}

function blockedFrom(oldState: SettingsOwnerState): SettingsOwnerState {
  return {
    status: "blocked",
    reason: "recovery-blocked",
    generation: oldState.generation,
    revision: "999",
    ownerEpoch: oldState.ownerEpoch,
    stateSeq: "999",
    dataRevision: "999",
    lastKnownDataRevision: oldState.dataRevision,
    issuedAt: oldState.issuedAt,
  };
}

function staleReadyState(oldState: SettingsOwnerState): SettingsOwnerState {
  if (oldState.status !== "ready") throw new ScenarioUnavailableError();
  return {
    ...cloneJson(oldState),
    revision: "999",
    stateSeq: "999",
    dataRevision: "999",
    snapshot: {
      ...cloneJson(oldState.snapshot),
      profile: {
        ...cloneJson(oldState.snapshot.profile),
        email: "__stale-owner-f-sentinel__",
      },
    },
  };
}

function safeDiagnostics(repository: CompanionUserSettingsRepository): CompanionUserSettingsBridgeDiagnostics {
  const diagnostics = (repository as BridgeWithDiagnostics).getDiagnostics?.();
  if (!diagnostics) throw new ScenarioUnavailableError();
  return diagnostics;
}

function createLogger() {
  let chain = Promise.resolve();
  return (operation: string, fields: Record<string, unknown> = {}): Promise<void> => {
    chain = chain.then(async () => {
      const safeFields = Object.fromEntries(
        Object.entries(fields).filter(([, value]) => value !== undefined),
      );
      await invoke("record_interaction", {
        event: `${DEV_SCENARIO_LOG_PREFIX}:${operation}:${JSON.stringify(safeFields)}`,
      }).catch(() => {});
    });
    return chain;
  };
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function settle(): Promise<void> {
  await Promise.resolve();
  await delay(0);
  await Promise.resolve();
  await delay(0);
}

function makeRequestId(runId: string, sequence: number): string {
  return `${runId}-request-${sequence}`;
}

function startPlatformScenario(
  options: CompanionUserSettingsDevScenarioOptions,
  runId: string,
  logger: ReturnType<typeof createLogger>,
): () => void {
  const repository = options.repository;
  let disposed = false;
  let baseline: SettingsSnapshot = null;
  let blockedProjectionCount = 0;
  let unlisten: UnlistenFn | undefined;
  const unsubscribe = repository.subscribe((initialization) => {
    if (!baseline || disposed) return;
    if (initialization.status === "blocked") blockedProjectionCount += 1;
  });

  const readState = (): SafeState => {
    const initialization = repository.getInitialization();
    const snapshot = repository.getSnapshot();
    const diagnostics = safeDiagnostics(repository);
    const transport = repository.getTransportState?.();
    const ownerState = "ownerEpoch" in initialization ? initialization : null;
    return {
      status: initialization.status,
      transport: transport?.status ?? "unknown",
      ownerEpochSuffix: ownerState ? suffix(ownerState.ownerEpoch) : null,
      stateSeq: ownerState?.stateSeq ?? null,
      dataRevision: ownerState?.dataRevision ?? null,
      issuedAt: ownerState?.issuedAt ?? null,
      snapshotPresent: Boolean(snapshot),
      projectionMatchesBaseline: baseline ? sameBusinessSnapshot(snapshot, baseline) : null,
      blockedProjectionCount,
      ...diagnostics,
    };
  };

  const report = async (
    requestId: string,
    action: ScenarioControl["action"],
  ): Promise<void> => {
    await emitTo<ScenarioReport>("main", DEV_SCENARIO_REPORT_EVENT, {
      runId,
      requestId,
      action,
      state: readState(),
    }).catch(() => {});
  };

  const handleControl = async (control: ScenarioControl): Promise<void> => {
    if (disposed || control.runId !== runId) return;
    if (control.action === "initialize-a" || control.action === "initialize-b") {
      const initialized = await repository.initialize();
      if (control.action === "initialize-b" && initialized.status === "ready") {
        baseline = cloneJson(repository.getSnapshot());
        blockedProjectionCount = 0;
      }
    } else if (control.action === "settle") {
      await settle();
    } else if (control.action === "stop-client") {
      repository.stop?.();
      await settle();
    } else if (control.action === "shutdown") {
      await report(control.requestId, control.action);
      disposed = true;
      unsubscribe();
      unlisten?.();
      return;
    }
    await report(control.requestId, control.action);
  };

  void (async () => {
    unlisten = await listen<ScenarioControl>(
      DEV_SCENARIO_CONTROL_EVENT,
      (event) => {
        void handleControl(event.payload);
      },
    );
    await logger("platform-listening", { runId });
  })();

  return () => {
    if (disposed) return;
    disposed = true;
    repository.stop?.();
    unsubscribe();
    unlisten?.();
  };
}

async function runMainScenario(
  options: CompanionUserSettingsDevScenarioOptions,
  runId: string,
  logger: ReturnType<typeof createLogger>,
  isDisposed: () => boolean,
): Promise<void> {
  if (!options.owner || !options.createOwner || !options.startOwnerBridge
    || !options.getOwnerBridgeStop || !options.ownerBridgeEvents) {
    throw new ScenarioUnavailableError();
  }

  const reports = new Map<string, (report: ScenarioReport) => void>();
  let requestSequence = 0;
  let unlistenReports: UnlistenFn | undefined;
  let stopB: (() => void) | undefined;
  let platformShutdown = false;
  let bLifecycle: CompanionUserSettingsOwnerBridgeLifecycle = {
    commandListeners: 0,
    ownerSubscriptions: 0,
  };

  const waitForReport = (requestId: string): Promise<ScenarioReport> => new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reports.delete(requestId);
      reject(new ScenarioUnavailableError());
    }, 1500);
    reports.set(requestId, (report) => {
      clearTimeout(timer);
      resolve(report);
    });
  });

  const sendControl = async (
    action: ScenarioControl["action"],
    attempts = 24,
  ): Promise<ScenarioReport> => {
    let lastError: unknown;
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      if (isDisposed()) throw new ScenarioUnavailableError();
      const requestId = makeRequestId(runId, ++requestSequence);
      const reportPromise = waitForReport(requestId);
      try {
        await emitTo<ScenarioControl>("platform", DEV_SCENARIO_CONTROL_EVENT, {
          runId,
          requestId,
          action,
        });
        return await reportPromise;
      } catch (error) {
        reports.delete(requestId);
        lastError = error;
        await delay(250);
      }
    }
    throw lastError ?? new ScenarioUnavailableError();
  };

  const inject = async (event: string, payload: unknown): Promise<void> => {
    await emitTo("platform", event, payload);
  };

  try {
    await logger("run-start", {
    runId,
    currentSourceCommand: "npm run tauri dev -- --no-watch",
    mainWindow: "main",
    platformWindow: "platform",
    });

  unlistenReports = await listen<ScenarioReport>(
    DEV_SCENARIO_REPORT_EVENT,
    (event) => {
      const report = event.payload;
      if (report?.runId !== runId || typeof report.requestId !== "string") return;
      reports.get(report.requestId)?.(report);
      reports.delete(report.requestId);
    },
  );

  const probe = await sendControl("probe");
  await logger("platform-controller-ready", {
    status: probe.state.status,
    resultListeners: probe.state.resultListeners,
    snapshotListeners: probe.state.snapshotListeners,
  });

  const initial = await sendControl("initialize-a");
  if (initial.state.status !== "ready" || !initial.state.ownerEpochSuffix) {
    throw new ScenarioUnavailableError();
  }
  const ownerAInitialization = options.owner.getInitialization();
  if (ownerAInitialization.status !== "ready") throw new ScenarioUnavailableError();
  const issuedAtA = ownerAInitialization.issuedAt;
  await logger("owner-a-ready", {
    ownerEpochSuffix: suffix(ownerAInitialization.ownerEpoch),
    stateSeq: ownerAInitialization.stateSeq,
    dataRevision: ownerAInitialization.dataRevision,
    issuedAtA,
    resultListeners: initial.state.resultListeners,
    snapshotListeners: initial.state.snapshotListeners,
    pendingWaiters: initial.state.pendingWaiters,
    queuedSignals: initial.state.queuedSignals,
    automaticRunner: initial.state.automaticRunner,
    businessCommandCount: initial.state.businessCommandCount,
  });

  const oldResultEmission = [...options.ownerBridgeEvents]
    .reverse()
    .find((emission) => emission.event === COMPANION_USER_SETTINGS_RESULT_EVENT
      && capturedResult(emission.payload));
  const oldSnapshotEmission = [...options.ownerBridgeEvents]
    .reverse()
    .find((emission) => emission.event === COMPANION_USER_SETTINGS_SNAPSHOT_EVENT
      && capturedSnapshot(emission.payload));
  const oldResult = capturedResult(oldResultEmission?.payload);
  const oldSnapshot = capturedSnapshot(oldSnapshotEmission?.payload);
  if (!oldResult || !oldSnapshot) throw new ScenarioUnavailableError();
  const oldReadyState = oldResult.initialization;
  const oldReadyResultPayload = {
    correlationId: oldResult.correlationId,
    initialization: staleReadyState(oldResult.initialization),
  };
  const oldReadySnapshotPayload = {
    initialization: staleReadyState(oldSnapshot.initialization),
  };
  const oldBlockedState = blockedFrom(oldReadyState);
  const oldBlockedSnapshotPayload = { initialization: oldBlockedState };
  const oldBlockedResultPayload = {
    correlationId: oldResult.correlationId,
    initialization: oldBlockedState,
  };

  const stopA = options.getOwnerBridgeStop();
  if (!stopA) throw new ScenarioUnavailableError();
  stopA();
  await settle();
  const ownerAStopLifecycle = options.getOwnerBridgeLifecycle?.() ?? {
    commandListeners: 0,
    ownerSubscriptions: 0,
  };
  await logger("owner-a-stopped", {
    commandListeners: ownerAStopLifecycle.commandListeners,
    ownerSubscriptions: ownerAStopLifecycle.ownerSubscriptions,
  });
  if (ownerAStopLifecycle.commandListeners !== 0 || ownerAStopLifecycle.ownerSubscriptions !== 0) {
    throw new ScenarioAssertionError();
  }

  const ownerEpochB = `f-owner-b-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const issuedAtB = issuedAtA - 1;
  const ownerB = options.createOwner({ ownerEpoch: ownerEpochB, issuedAt: issuedAtB });
  stopB = await options.startOwnerBridge(ownerB, {
    responseTarget: "main",
    onLifecycle: (lifecycle) => { bLifecycle = lifecycle; },
  });
  await sendControl("settle");
  const initializedB = await sendControl("initialize-b");
  if (initializedB.state.status !== "ready"
    || initializedB.state.ownerEpochSuffix !== suffix(ownerEpochB)) {
    throw new ScenarioAssertionError();
  }
  const issuedAtRollback = issuedAtB < issuedAtA;
  await logger("owner-b-takeover", {
    ownerEpochASuffix: suffix(oldReadyState.ownerEpoch),
    ownerEpochBSuffix: suffix(ownerEpochB),
    ownerEpochsDiffer: oldReadyState.ownerEpoch !== ownerEpochB,
    issuedAtA,
    issuedAtB,
    issuedAtBLessThanA: issuedAtRollback,
    status: initializedB.state.status,
    stateSeq: initializedB.state.stateSeq,
    dataRevision: initializedB.state.dataRevision,
    resultListeners: initializedB.state.resultListeners,
    snapshotListeners: initializedB.state.snapshotListeners,
    pendingWaiters: initializedB.state.pendingWaiters,
    queuedSignals: initializedB.state.queuedSignals,
    automaticRunner: initializedB.state.automaticRunner,
    automaticReconcileCount: initializedB.state.automaticReconcileCount,
    businessCommandCount: initializedB.state.businessCommandCount,
  });
  if (!issuedAtRollback) throw new ScenarioAssertionError();

  const injections: Array<{ name: string; events: Array<{ type: string; payload: unknown }> }> = [
    {
      name: "late-ready-snapshot",
      events: [{ type: COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, payload: oldReadySnapshotPayload }],
    },
    {
      name: "late-blocked-snapshot",
      events: [{ type: COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, payload: oldBlockedSnapshotPayload }],
    },
    {
      name: "late-ready-initialize-result",
      events: [{ type: COMPANION_USER_SETTINGS_RESULT_EVENT, payload: oldReadyResultPayload }],
    },
    {
      name: "late-blocked-initialize-result",
      events: [{ type: COMPANION_USER_SETTINGS_RESULT_EVENT, payload: oldBlockedResultPayload }],
    },
    {
      name: "duplicate-result",
      events: [
        { type: COMPANION_USER_SETTINGS_RESULT_EVENT, payload: oldReadyResultPayload },
        { type: COMPANION_USER_SETTINGS_RESULT_EVENT, payload: oldReadyResultPayload },
      ],
    },
    {
      name: "duplicate-snapshot",
      events: [
        { type: COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, payload: oldReadySnapshotPayload },
        { type: COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, payload: oldReadySnapshotPayload },
      ],
    },
    {
      name: "result-before-snapshot",
      events: [
        { type: COMPANION_USER_SETTINGS_RESULT_EVENT, payload: oldReadyResultPayload },
        { type: COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, payload: oldReadySnapshotPayload },
      ],
    },
    {
      name: "snapshot-before-result",
      events: [
        { type: COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, payload: oldReadySnapshotPayload },
        { type: COMPANION_USER_SETTINGS_RESULT_EVENT, payload: oldReadyResultPayload },
      ],
    },
  ];

  for (const injection of injections) {
    const before = (await sendControl("inspect")).state;
    for (const event of injection.events) await inject(event.type, event.payload);
    const after = (await sendControl("settle")).state;
    const equal = safeStateEqual(before, after);
    await logger("late-event-injection", {
      eventType: injection.name,
      transportEventOrder: injection.events.map((event) => event.type).join(" then "),
      authorityEqual: before.ownerEpochSuffix === after.ownerEpochSuffix,
      statusEqual: before.status === after.status,
      stateSeqEqual: before.stateSeq === after.stateSeq,
      dataRevisionEqual: before.dataRevision === after.dataRevision,
      projectionEqual: before.projectionMatchesBaseline === after.projectionMatchesBaseline,
      stateEqual: equal,
      before: compactState(before),
      after: compactState(after),
    });
    if (!equal || after.status !== "ready" || after.blockedProjectionCount !== 0) {
      throw new ScenarioAssertionError();
    }
  }

  const drained = (await sendControl("settle")).state;
  await logger("bounded-drain", {
    pendingWaiters: drained.pendingWaiters,
    queuedSignals: drained.queuedSignals,
    automaticRunner: drained.automaticRunner,
    automaticReconcileCount: drained.automaticReconcileCount,
    resultListeners: drained.resultListeners,
    snapshotListeners: drained.snapshotListeners,
    businessCommandCount: drained.businessCommandCount,
  });
  if (drained.pendingWaiters !== 0 || drained.queuedSignals !== 0 || drained.automaticRunner !== 0
    || drained.resultListeners !== 1 || drained.snapshotListeners !== 1
    || drained.businessCommandCount !== 0) {
    throw new ScenarioAssertionError();
  }

  const stoppedClient = (await sendControl("stop-client")).state;
  await logger("client-stopped", {
    resultListeners: stoppedClient.resultListeners,
    snapshotListeners: stoppedClient.snapshotListeners,
    pendingWaiters: stoppedClient.pendingWaiters,
    queuedSignals: stoppedClient.queuedSignals,
    automaticRunner: stoppedClient.automaticRunner,
    businessCommandCount: stoppedClient.businessCommandCount,
  });
  if (stoppedClient.resultListeners !== 0 || stoppedClient.snapshotListeners !== 0
    || stoppedClient.pendingWaiters !== 0 || stoppedClient.queuedSignals !== 0
    || stoppedClient.automaticRunner !== 0) {
    throw new ScenarioAssertionError();
  }

  const beforePostStop = stoppedClient;
  await inject(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, oldBlockedSnapshotPayload);
  const afterPostStop = (await sendControl("inspect")).state;
  const postStopEqual = safeStateEqual(beforePostStop, afterPostStop);
  await logger("late-event-after-client-stop", {
    eventType: "companion-settings-snapshot",
    authorityEqual: beforePostStop.ownerEpochSuffix === afterPostStop.ownerEpochSuffix,
    statusEqual: beforePostStop.status === afterPostStop.status,
    stateSeqEqual: beforePostStop.stateSeq === afterPostStop.stateSeq,
    dataRevisionEqual: beforePostStop.dataRevision === afterPostStop.dataRevision,
    stateEqual: postStopEqual,
    resultListeners: afterPostStop.resultListeners,
    snapshotListeners: afterPostStop.snapshotListeners,
    pendingWaiters: afterPostStop.pendingWaiters,
    queuedSignals: afterPostStop.queuedSignals,
    automaticRunner: afterPostStop.automaticRunner,
  });
  if (!postStopEqual) throw new ScenarioAssertionError();

  await sendControl("shutdown");
  platformShutdown = true;
  stopB?.();
  stopB = undefined;
  await settle();
  await logger("final-cleanup", {
    resultListeners: stoppedClient.resultListeners,
    snapshotListeners: stoppedClient.snapshotListeners,
    commandListeners: bLifecycle.commandListeners,
    ownerSubscriptions: bLifecycle.ownerSubscriptions,
    pendingWaiters: afterPostStop.pendingWaiters,
    queuedSignals: afterPostStop.queuedSignals,
    automaticRunner: afterPostStop.automaticRunner,
    businessCommandCount: afterPostStop.businessCommandCount,
  });
  if (bLifecycle.commandListeners !== 0 || bLifecycle.ownerSubscriptions !== 0) {
    throw new ScenarioAssertionError();
  }
  await logger("f-result", {
    gate: "F",
    status: "PASS",
    overallVerdict: "TAURI_SETTINGS_PARTIAL",
    hStatus: "UNVERIFIED",
  });
  } finally {
    if (unlistenReports && !platformShutdown) {
      try {
        await sendControl("stop-client", 1);
        await sendControl("shutdown", 1);
      } catch {
        // Cleanup is best-effort after a failed scenario transport step.
      }
    }
    if (unlistenReports) unlistenReports();
    unlistenReports = undefined;
    reports.clear();
    if (stopB) {
      stopB();
      stopB = undefined;
    }
  }
}

export function startCompanionUserSettingsDevScenario(
  options: CompanionUserSettingsDevScenarioOptions,
): () => void {
  if (!scenarioEnabled() || !options.isTauriRuntime) return () => {};

  let disposed = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let stopInternal: (() => void) | undefined;
  const runId = import.meta.env[DEV_SCENARIO_RUN_ENV]
    || `f-owner-takeover-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const logger = createLogger();

  const run = async () => {
    if (disposed) return;
    if (options.isPlatformWindow) {
      stopInternal = startPlatformScenario(options, runId, logger);
      return;
    }
    try {
      await runMainScenario(options, runId, logger, () => disposed);
    } catch (error) {
      await logger("f-result", {
        gate: "F",
        status: error instanceof ScenarioAssertionError
          ? "TAURI_SETTINGS_REJECTED"
          : "UNVERIFIED",
        overallVerdict: error instanceof ScenarioAssertionError
          ? "TAURI_SETTINGS_REJECTED"
          : "TAURI_SETTINGS_PARTIAL",
        failureKind: error instanceof ScenarioAssertionError ? "functional" : "injection-unavailable",
      });
    } finally {
      options.ownerBridgeEvents?.splice(0);
      stopInternal?.();
    }
  };

  // React StrictMode performs an immediate setup/cleanup replay. Deferring
  // activation by one task lets that replay cancel the first attempt without
  // creating a second Owner or Settings lifecycle.
  timer = setTimeout(() => {
    timer = undefined;
    void run();
  }, 0);

  return () => {
    disposed = true;
    if (timer !== undefined) clearTimeout(timer);
    stopInternal?.();
  };
}
