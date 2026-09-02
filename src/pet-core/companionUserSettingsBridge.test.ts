import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import {
  COMPANION_PREFERENCES_STORAGE_KEY,
  type CompanionPreference,
  type CompanionPreferencesState,
} from "./companionPreferences";
import {
  EMPTY_COMPANION_USER_PROFILE,
  COMPANION_USER_PROFILE_STORAGE_KEY,
  type CompanionUserProfile,
} from "./companionUserProfile";
import {
  COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY,
  COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
  type CompanionUserProfileSyncStorage,
} from "./companionUserProfileSync";
import {
  createCompanionUserSettingsOwner,
  type CompanionUserSettingsOwner,
  type SettingsCommand,
  type SettingsInitialization,
} from "./companionUserSettingsRepository";
import {
  COMPANION_USER_SETTINGS_COMMAND_EVENT,
  COMPANION_USER_SETTINGS_RESULT_EVENT,
  COMPANION_USER_SETTINGS_SNAPSHOT_EVENT,
  createCompanionUserSettingsBridge,
  startCompanionUserSettingsOwnerBridge,
} from "./companionUserSettingsBridge";

type MockEvent = { payload: unknown };
type MockEventHandler = (event: MockEvent) => unknown;
type PendingEvent = { event: string; payload: unknown };

const eventBus = vi.hoisted(() => {
  const listeners = new Map<string, Set<MockEventHandler>>();
  const delayed: PendingEvent[] = [];
  const delivered: PendingEvent[] = [];
  const rejectedTargets = new Set<string>();
  const delayedEvents = new Set<string>();

  const dispatch = async (event: string, payload: unknown): Promise<void> => {
    delivered.push({ event, payload });
    const handlers = [...(listeners.get(event) ?? [])];
    await Promise.all(handlers.map((handler) => Promise.resolve(handler({ payload }))));
  };

  const listen = vi.fn(async (event: string, handler: MockEventHandler) => {
    const handlers = listeners.get(event) ?? new Set<MockEventHandler>();
    handlers.add(handler);
    listeners.set(event, handlers);
    return () => {
      handlers.delete(handler);
    };
  });

  const emitTo = vi.fn(async (target: string, event: string, payload: unknown) => {
    if (rejectedTargets.has(target)) throw new Error(`emit failed for ${target}`);
    if (delayedEvents.has(event)) {
      delayed.push({ event, payload });
      return;
    }
    await dispatch(event, payload);
  });

  return {
    listen,
    emitTo,
    reset: () => {
      listeners.clear();
      delayed.length = 0;
      delivered.length = 0;
      rejectedTargets.clear();
      delayedEvents.clear();
      listen.mockClear();
      emitTo.mockClear();
    },
    rejectTarget: (target: string) => rejectedTargets.add(target),
    delayEvent: (event: string) => delayedEvents.add(event),
    releaseEvent: (event: string) => delayedEvents.delete(event),
    flushDelayed: async () => {
      const pending = delayed.splice(0);
      for (const item of pending) await dispatch(item.event, item.payload);
    },
    takeDelayed: () => delayed.splice(0),
    queueDelayed: (event: string, payload: unknown) => delayed.push({ event, payload }),
    history: () => [...delivered],
    emitExternal: (event: string, payload: unknown) => dispatch(event, payload),
    count: (event: string) => emitTo.mock.calls.filter((call) => call[1] === event).length,
    listenerCount: (event: string) => listeners.get(event)?.size ?? 0,
    commandPayloads: () => emitTo.mock.calls
      .filter((call) => call[1] === COMPANION_USER_SETTINGS_COMMAND_EVENT)
      .map((call) => call[2] as {
        kind: "initialize" | "command";
        expectedOwnerEpoch?: string;
        correlationId: string;
      }),
  };
});

vi.mock("@tauri-apps/api/event", () => ({
  emitTo: eventBus.emitTo,
  listen: eventBus.listen,
}));

vi.mock("@tauri-apps/api/window", () => ({
  getCurrentWindow: vi.fn(() => ({ label: "platform" })),
}));

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

function replyStylePreference(value: string): CompanionPreference {
  return {
    id: "global.replyStyle",
    scope: "global",
    category: "userProfile",
    key: "replyStyle",
    value,
    source: "explicit",
  };
}

function createStorageFixture() {
  const profile: CompanionUserProfile = {
    ...EMPTY_COMPANION_USER_PROFILE,
    nickname: "",
    email: "old@example.com",
    phone: "13800138000",
  };
  const preferences: CompanionPreferencesState = {
    preferences: [
      nicknamePreference("旧昵称"),
      replyStylePreference("short-and-soft"),
    ],
    recentPreferenceId: "global.replyStyle",
  };
  const values = new Map<string, string>([
    [COMPANION_USER_PROFILE_STORAGE_KEY, JSON.stringify(profile)],
    [COMPANION_PREFERENCES_STORAGE_KEY, JSON.stringify(preferences)],
    [COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY, JSON.stringify({
      schemaVersion: 1,
      state: "preference-authoritative",
    })],
  ]);
  let readsBlocked = false;
  const storage: CompanionUserProfileSyncStorage = {
    getItem: vi.fn((key: string) => {
      if (readsBlocked) throw new Error(`read failure: ${key}`);
      return values.get(key) ?? null;
    }),
    setItem: vi.fn((key: string, value: string) => {
      values.set(key, value);
    }),
    removeItem: vi.fn((key: string) => {
      values.delete(key);
    }),
  };
  return {
    storage,
    profile,
    preferences,
    setReadsBlocked: (value: boolean) => { readsBlocked = value; },
    raw: (key: string) => values.get(key) ?? null,
    writeCount: () => (storage.setItem as ReturnType<typeof vi.fn>).mock.calls.length,
  };
}

function expectReady(initialization: SettingsInitialization) {
  expect(initialization.status).toBe("ready");
  if (initialization.status !== "ready") throw new Error("expected ready settings");
  return initialization;
}

async function settleEvents() {
  await Promise.resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
  await Promise.resolve();
}

function expectedVersion(owner: CompanionUserSettingsOwner) {
  const snapshot = owner.getSnapshot();
  if (!snapshot) throw new Error("owner is not ready in test");
  return {
    expectedGeneration: snapshot.generation,
    expectedRevision: snapshot.revision,
    expectedOwnerEpoch: snapshot.ownerEpoch,
    expectedStateSeq: snapshot.stateSeq,
    expectedDataRevision: snapshot.dataRevision,
  };
}

function updateProfileCommand(
  owner: CompanionUserSettingsOwner,
  correlationId: string,
  patch: Partial<CompanionUserProfile>,
): SettingsCommand {
  return {
    type: "updateProfile",
    patch,
    ...expectedVersion(owner),
    correlationId,
  };
}

async function startPair(
  owner: CompanionUserSettingsOwner,
  responseTimeoutMs = 80,
) {
  const bridge = createCompanionUserSettingsBridge({
    ownerWindow: "main",
    responseTimeoutMs,
    sourceWindow: "platform",
  });
  const stop = await startCompanionUserSettingsOwnerBridge(owner);
  return { bridge, stop };
}

describe("companion user settings typed Bridge", () => {
  beforeEach(() => {
    eventBus.reset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("initial ready handshake uses the real command/result event protocol", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-1",
      issuedAt: 1000,
    });
    const { bridge, stop } = await startPair(owner);

    const initialization = expectReady(await bridge.initialize());

    expect(initialization.generation).toBe("generation-1");
    expect(initialization.revision).toBe("0");
    expect(initialization.snapshot.profile.email).toBe(fixture.profile.email);
    expect(initialization.snapshot.preferences).toEqual(fixture.preferences);
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT)).toBeGreaterThan(0);
    expect(eventBus.count(COMPANION_USER_SETTINGS_RESULT_EVENT)).toBeGreaterThan(0);
    stop();
  });

  test("blocked Owner recovers through a platform retry and preserves all business data", async () => {
    const fixture = createStorageFixture();
    fixture.setReadsBlocked(true);
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-blocked",
      issuedAt: 1000,
    });

    expect((await owner.initialize()).status).toBe("blocked");
    const { bridge, stop } = await startPair(owner);
    const blocked = await bridge.initialize();
    expect(blocked).toMatchObject({ status: "blocked" });
    expect(bridge.getSnapshot()).toBeNull();
    expect(fixture.writeCount()).toBe(0);

    fixture.setReadsBlocked(false);
    const recovered = expectReady(await bridge.initialize());

    expect(recovered.snapshot.profile.email).toBe(fixture.profile.email);
    expect(recovered.snapshot.profile.phone).toBe(fixture.profile.phone);
    expect(recovered.snapshot.preferences).toEqual(fixture.preferences);
    expect(fixture.writeCount()).toBe(0);
    expect(fixture.raw(COMPANION_USER_PROFILE_STORAGE_KEY)).toBe(JSON.stringify(fixture.profile));
    expect(fixture.raw(COMPANION_PREFERENCES_STORAGE_KEY)).toBe(JSON.stringify(fixture.preferences));
    expect(fixture.raw(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY)).toBeTruthy();
    expect(fixture.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).toBeNull();

    const command = await bridge.updateProfile(
      { email: "recovered@example.com" },
      {
        expectedGeneration: recovered.generation,
        expectedRevision: recovered.revision,
      },
      "recovery-profile-command",
    );
    expect(command.ok).toBe(true);
    expect(fixture.writeCount()).toBeGreaterThan(0);
    expect(owner.getSnapshot()?.profile).toMatchObject({
      email: "recovered@example.com",
      phone: fixture.profile.phone,
    });
    expect(owner.getSnapshot()?.preferences.preferences).toEqual(expect.arrayContaining([
      nicknamePreference("旧昵称"),
      replyStylePreference("short-and-soft"),
    ]));
    expect(JSON.parse(fixture.raw(COMPANION_USER_PROFILE_STORAGE_KEY) ?? "null")).toMatchObject({
      email: "recovered@example.com",
      phone: fixture.profile.phone,
    });
    expect(JSON.parse(fixture.raw(COMPANION_PREFERENCES_STORAGE_KEY) ?? "null").preferences)
      .toEqual(expect.arrayContaining([
        nicknamePreference("旧昵称"),
        replyStylePreference("short-and-soft"),
      ]));
    expect(fixture.raw(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY)).toBeTruthy();
    expect(fixture.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).toBeNull();
    stop();
  });

  test("Owner restart with a forward issuedAt establishes the new generation", async () => {
    const fixture = createStorageFixture();
    const owner1 = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-1",
      issuedAt: 1000,
    });
    const { bridge, stop: stop1 } = await startPair(owner1);
    expectReady(await bridge.initialize());
    stop1();

    const owner2 = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-2",
      issuedAt: 2000,
    });
    const { stop: stop2 } = await startPair(owner2);
    const current = expectReady(await bridge.initialize());

    expect(current.generation).toBe("generation-2");
    expect(current.revision).toBe("0");
    stop2();
  });

  test("Owner restart with a clock rollback still establishes the new generation and accepts its command", async () => {
    const fixture = createStorageFixture();
    const owner1 = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-1",
      issuedAt: 1000,
    });
    const { bridge, stop: stop1 } = await startPair(owner1);
    expectReady(await bridge.initialize());
    stop1();

    const owner2 = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-2",
      issuedAt: 900,
    });
    const { stop: stop2 } = await startPair(owner2);
    const current = expectReady(await bridge.initialize());

    expect(current.generation).toBe("generation-2");
    const result = await bridge.updateProfile(
      { phone: "13900000000" },
      { expectedGeneration: current.generation, expectedRevision: current.revision },
      "generation-2-profile",
    );
    expect(result).toMatchObject({
      ok: true,
      generation: "generation-2",
      revision: "1",
      correlationId: "generation-2-profile",
    });
    expect(owner2.getSnapshot()?.profile.phone).toBe("13900000000");
    stop2();
  });

  test("an unsolicited different-generation snapshot cannot replace state before the current Owner handshake", async () => {
    const fixture = createStorageFixture();
    const owner1 = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-1",
      issuedAt: 1000,
    });
    const { bridge, stop } = await startPair(owner1);
    const current = expectReady(await bridge.initialize());
    const commandCount = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);

    await eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, {
      initialization: {
        ...current,
        generation: "unconfirmed-generation",
        ownerEpoch: "unconfirmed-generation",
        stateSeq: "99",
        dataRevision: "99",
        issuedAt: 9000,
        snapshot: {
          ...current.snapshot,
          profile: { ...current.snapshot.profile, email: "rogue@example.com" },
        },
      },
    });
    await settleEvents();

    expect(bridge.getSnapshot()?.generation).toBe("generation-1");
    expect(bridge.getSnapshot()?.profile.email).toBe(fixture.profile.email);
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT)).toBe(commandCount + 1);
    stop();
  });

  test("a late old-generation snapshot cannot roll back a newly established Owner", async () => {
    const fixture = createStorageFixture();
    const owner1 = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-1",
      issuedAt: 1000,
    });
    const { bridge, stop: stop1 } = await startPair(owner1);
    const first = expectReady(await bridge.initialize());
    stop1();

    const owner2 = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-2",
      issuedAt: 900,
    });
    const { stop: stop2 } = await startPair(owner2);
    const second = expectReady(await bridge.initialize());
    expect(second.generation).toBe("generation-2");

    await eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, {
      initialization: {
        ...first,
        revision: "99",
        snapshot: {
          ...first.snapshot,
          profile: { ...first.snapshot.profile, email: "late-old@example.com" },
        },
      },
    });

    expect(bridge.getSnapshot()?.generation).toBe("generation-2");
    expect(bridge.getSnapshot()?.profile.email).not.toBe("late-old@example.com");
    stop2();
  });

  test("a late blocked snapshot from the old Owner cannot clear the newly established Owner", async () => {
    const fixture = createStorageFixture();
    const owner1 = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-1",
      issuedAt: 1000,
    });
    const { bridge, stop: stop1 } = await startPair(owner1);
    const first = expectReady(await bridge.initialize());

    eventBus.delayEvent(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT);
    fixture.setReadsBlocked(true);
    const oldOwnerFailure = await bridge.updateProfile(
      { email: "old-owner-must-not-write@example.com" },
      { expectedGeneration: first.generation, expectedRevision: first.revision },
      "old-owner-blocked-command",
    );
    expect(oldOwnerFailure).toMatchObject({
      ok: false,
      correlationId: "old-owner-blocked-command",
    });
    expect(oldOwnerFailure.ok ? "unexpected-success" : oldOwnerFailure.reason)
      .toBe("recovery-blocked");
    expect(fixture.writeCount()).toBe(0);

    const delayedBlocked = eventBus.takeDelayed();
    expect(delayedBlocked).toHaveLength(1);
    expect((delayedBlocked[0]?.payload as { initialization: SettingsInitialization }).initialization)
      .toMatchObject({ status: "blocked", issuedAt: 1000 });
    eventBus.releaseEvent(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT);
    stop1();

    fixture.setReadsBlocked(false);
    const owner2 = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-2",
      issuedAt: 900,
    });
    const stop2 = await startCompanionUserSettingsOwnerBridge(owner2);
    await new Promise((resolve) => setTimeout(resolve, 0));
    const second = expectReady(bridge.getInitialization());
    expect(second).toMatchObject({
      generation: "generation-2",
      revision: "0",
      snapshot: {
        profile: { email: fixture.profile.email },
        preferences: fixture.preferences,
      },
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    const commandCountBeforeLateSnapshot = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);
    const writesBeforeLateSnapshot = fixture.writeCount();

    await eventBus.emitExternal(
      COMPANION_USER_SETTINGS_SNAPSHOT_EVENT,
      delayedBlocked[0]!.payload,
    );
    await new Promise((resolve) => setTimeout(resolve, 0));
    await Promise.resolve();

    expect(bridge.getInitialization()).toMatchObject({
      status: "ready",
      generation: "generation-2",
      revision: "0",
    });
    expect(bridge.getSnapshot()).toMatchObject({
      generation: "generation-2",
      revision: "0",
      profile: { email: fixture.profile.email, phone: fixture.profile.phone },
      preferences: fixture.preferences,
    });
    expect(bridge.getSnapshot()).not.toBeNull();
    expect(fixture.writeCount()).toBe(writesBeforeLateSnapshot);
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeLateSnapshot);
    stop2();
  });

  test("a late old Owner result cannot win an Owner-epoch takeover race", async () => {
    const fixture = createStorageFixture();
    const owner1 = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-result-old",
      issuedAt: 1000,
    });
    const { bridge, stop: stop1 } = await startPair(owner1);
    const first = expectReady(await bridge.initialize());
    await settleEvents();

    eventBus.delayEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    const oldHandshake = bridge.initialize();
    await settleEvents();
    const oldDelayedResult = eventBus.takeDelayed();
    expect(oldDelayedResult).toHaveLength(1);
    stop1();

    const owner2 = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-result-new",
      issuedAt: 900,
    });
    const stop2 = await startCompanionUserSettingsOwnerBridge(owner2);
    await settleEvents();
    const newDelayedResult = eventBus.takeDelayed();
    expect(newDelayedResult).toHaveLength(1);

    const oldPayload = oldDelayedResult[0]!.payload as {
      correlationId: string;
      initialization: SettingsInitialization;
    };
    if (oldPayload.initialization.status !== "ready") {
      throw new Error("expected old handshake to be ready");
    }
    await eventBus.emitExternal(COMPANION_USER_SETTINGS_RESULT_EVENT, {
      correlationId: oldPayload.correlationId,
      initialization: {
        ...oldPayload.initialization,
        stateSeq: "99",
        dataRevision: "99",
        revision: "99",
        snapshot: {
          ...oldPayload.initialization.snapshot,
          profile: {
            ...oldPayload.initialization.snapshot.profile,
            email: "late-old-result@example.com",
          },
        },
      },
    });
    await oldHandshake;
    expect(bridge.getSnapshot()?.generation).toBe(first.generation);
    expect(bridge.getSnapshot()?.profile.email).toBe(fixture.profile.email);

    eventBus.releaseEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    await eventBus.emitExternal(
      COMPANION_USER_SETTINGS_RESULT_EVENT,
      newDelayedResult[0]!.payload,
    );
    await settleEvents();
    expect(bridge.getSnapshot()?.generation).toBe("generation-result-new");
    expect(bridge.getSnapshot()?.profile.email).toBe(fixture.profile.email);
    stop2();
  });

  test("a blocked snapshot from the current Owner is resolved by a blocked initialize response", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-current-blocked",
      issuedAt: 1000,
    });
    const { bridge, stop } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    await settleEvents();
    const commandCountBeforeFault = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);

    fixture.setReadsBlocked(true);
    const failedWrite = await bridge.updateProfile(
      { email: "blocked-owner-must-not-write@example.com" },
      { expectedGeneration: initial.generation, expectedRevision: initial.revision },
      "current-owner-blocked-command",
    );
    expect(failedWrite.ok).toBe(false);
    expect(fixture.writeCount()).toBe(0);
    await settleEvents();

    const blocked = bridge.getInitialization();
    expect(blocked).toMatchObject({ status: "blocked" });
    expect(bridge.getSnapshot()).toBeNull();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeFault + 2);

    const failedAfterBlocked = await bridge.updateProfile(
      { email: "second-blocked-write-must-not-write@example.com" },
      { expectedGeneration: initial.generation, expectedRevision: initial.revision },
      "blocked-platform-command",
    );
    expect(failedAfterBlocked.ok).toBe(false);
    if (blocked.status !== "blocked" || failedAfterBlocked.ok) {
      throw new Error("expected the platform to remain blocked");
    }
    expect(failedAfterBlocked).toEqual({
      ok: false,
      reason: blocked.reason,
      correlationId: "blocked-platform-command",
    });
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeFault + 2);
    expect(fixture.writeCount()).toBe(0);
    stop();
  });

  test("repeated blocked snapshots share one in-flight initialize handshake", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-blocked-dedupe",
      issuedAt: 1000,
    });
    const { bridge, stop } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    await settleEvents();
    const commandCountBeforeSignals = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);
    eventBus.delayEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    const blockedSignal: SettingsInitialization = {
      status: "blocked",
      reason: "read-failed",
      generation: initial.generation,
      revision: initial.revision,
      ownerEpoch: initial.ownerEpoch,
      stateSeq: "1",
      dataRevision: initial.dataRevision,
      lastKnownDataRevision: initial.dataRevision,
      issuedAt: initial.issuedAt,
    };

    await Promise.all([
      eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, { initialization: blockedSignal }),
      eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, { initialization: blockedSignal }),
      eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, { initialization: blockedSignal }),
    ]);

    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeSignals + 1);
    expect(fixture.writeCount()).toBe(0);
    eventBus.releaseEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    await eventBus.flushDelayed();
    await settleEvents();

    const current = expectReady(bridge.getInitialization());
    expect(current.generation).toBe(initial.generation);
    expect(bridge.getSnapshot()).not.toBeNull();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeSignals + 1);
    expect(fixture.writeCount()).toBe(0);
    stop();
  });

  test("result-before-snapshot consumes one blocked Owner version without a feedback loop", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-result-before-snapshot",
      issuedAt: 1000,
    });
    const { bridge, stop } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    await settleEvents();

    const commandCountBeforeFault = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);
    eventBus.delayEvent(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT);
    fixture.setReadsBlocked(true);

    const failedWrite = await bridge.updateProfile(
      { email: "result-before-snapshot-must-not-write@example.com" },
      { expectedGeneration: initial.generation, expectedRevision: initial.revision },
      "result-before-snapshot-blocked-command",
    );
    expect(failedWrite).toEqual({
      ok: false,
      reason: "recovery-blocked",
      correlationId: "result-before-snapshot-blocked-command",
    });
    expect(fixture.writeCount()).toBe(0);
    const resultCountBeforeAutoReconcile = eventBus.count(COMPANION_USER_SETTINGS_RESULT_EVENT);

    // The failed command produced the first blocked signal. Keep the event
    // delayed so the following initialize result is delivered first.
    const firstBlockedSignal = eventBus.takeDelayed();
    expect(firstBlockedSignal).toHaveLength(1);
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeFault + 1);

    // Deliver the blocked signal without releasing delayed snapshots. This
    // is the real automatic reconcile path through the typed event bridge.
    await eventBus.emitExternal(
      COMPANION_USER_SETTINGS_SNAPSHOT_EVENT,
      firstBlockedSignal[0]!.payload,
    );
    await settleEvents();

    // The correlation-matched blocked result has arrived while the snapshot
    // emitted by that same Owner.initialize() is still queued.
    expect(eventBus.count(COMPANION_USER_SETTINGS_RESULT_EVENT))
      .toBe(resultCountBeforeAutoReconcile + 1);
    const deliveredAfterResult = eventBus.history();
    expect(deliveredAfterResult[deliveredAfterResult.length - 1]?.event)
      .toBe(COMPANION_USER_SETTINGS_RESULT_EVENT);
    expect(bridge.getInitialization()).toMatchObject({ status: "blocked" });

    let pendingSnapshots = eventBus.takeDelayed();
    if (pendingSnapshots.length === 0) {
      // Protocol V2 may correctly suppress an unchanged blocked notification
      // during retry. Still inject one duplicate same-version signal so the
      // result-before-snapshot bridge race remains directly exercised.
      eventBus.queueDelayed(
        COMPANION_USER_SETTINGS_SNAPSHOT_EVENT,
        firstBlockedSignal[0]!.payload,
      );
      pendingSnapshots = eventBus.takeDelayed();
    }
    expect(pendingSnapshots).toHaveLength(1);

    // Release a bounded number of snapshots. The correct protocol consumes
    // the same ownerEpoch/stateSeq once; the old protocol starts another
    // initialize after every result-before-snapshot turn.
    for (let round = 0; round < 4 && pendingSnapshots.length > 0; round += 1) {
      await eventBus.emitExternal(
        pendingSnapshots[0]!.event,
        pendingSnapshots[0]!.payload,
      );
      await settleEvents();
      expect(fixture.writeCount()).toBe(0);
      pendingSnapshots = eventBus.takeDelayed();
      if (pendingSnapshots.length > 0) expect(pendingSnapshots).toHaveLength(1);
    }

    eventBus.releaseEvent(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT);
    expect(pendingSnapshots).toEqual([]);
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeFault + 2);
    expect(bridge.getInitialization()).toMatchObject({ status: "blocked" });
    expect(bridge.getSnapshot()).toBeNull();
    expect(fixture.writeCount()).toBe(0);
    stop();
  });

  test("snapshot-before-result and duplicate signals consume one versioned reconcile", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-snapshot-before-result",
      issuedAt: 1000,
    });
    const { bridge, stop } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    await settleEvents();
    const commandCountBeforeFault = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);

    eventBus.delayEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    fixture.setReadsBlocked(true);
    const ownerFailure = await owner.execute(updateProfileCommand(
      owner,
      "snapshot-before-result-owner-failure",
      { email: "snapshot-before-result-must-not-write@example.com" },
    ));
    expect(ownerFailure).toMatchObject({ ok: false, reason: "recovery-blocked" });
    expect(fixture.writeCount()).toBe(0);
    const blocked = owner.getInitialization();
    if (blocked.status !== "blocked") throw new Error("Owner should be blocked in test");

    await settleEvents();
    const delayedResult = eventBus.takeDelayed();
    expect(delayedResult).toHaveLength(1);
    expect(delayedResult[0]?.payload).toMatchObject({
      initialization: {
        status: "blocked",
        ownerEpoch: blocked.ownerEpoch,
        stateSeq: blocked.stateSeq,
      },
    });
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeFault + 1);

    // The duplicate versioned signal arrives before the correlation result.
    await eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, {
      initialization: blocked,
    });
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeFault + 1);

    eventBus.releaseEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    await eventBus.emitExternal(
      COMPANION_USER_SETTINGS_RESULT_EVENT,
      delayedResult[0]!.payload,
    );
    await settleEvents();

    expect(bridge.getInitialization()).toMatchObject({
      status: "blocked",
      ownerEpoch: initial.ownerEpoch,
      stateSeq: blocked.stateSeq,
      dataRevision: initial.dataRevision,
    });
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeFault + 1);
    expect(fixture.writeCount()).toBe(0);

    // Duplicate result and duplicate signal are both late no-ops.
    await eventBus.emitExternal(
      COMPANION_USER_SETTINGS_RESULT_EVENT,
      delayedResult[0]!.payload,
    );
    await eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, {
      initialization: blocked,
    });
    await settleEvents();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeFault + 1);
    stop();
  });

  test("a blocked Owner re-reads the original Profile and Preferences after recovery", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-blocked-recovery",
      issuedAt: 1000,
    });
    const { bridge, stop } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());

    fixture.setReadsBlocked(true);
    const failedWrite = await bridge.updateProfile(
      { email: "blocked-recovery-must-not-write@example.com" },
      { expectedGeneration: initial.generation, expectedRevision: initial.revision },
      "blocked-recovery-command",
    );
    expect(failedWrite.ok).toBe(false);
    await settleEvents();
    expect(bridge.getSnapshot()).toBeNull();
    expect(fixture.writeCount()).toBe(0);

    fixture.setReadsBlocked(false);
    const recovered = expectReady(await bridge.initialize());
    expect(recovered.generation).toBe(initial.generation);
    expect(recovered.revision).toBe(initial.revision);
    expect(recovered.snapshot.profile).toEqual(initial.snapshot.profile);
    expect(recovered.snapshot.preferences).toEqual(initial.snapshot.preferences);
    expect(bridge.getSnapshot()).toMatchObject({
      generation: initial.generation,
      revision: initial.revision,
      profile: initial.snapshot.profile,
      preferences: initial.snapshot.preferences,
    });
    expect(fixture.writeCount()).toBe(0);
    stop();
  });

  test("same-generation lower revisions are rejected and higher revisions are accepted", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-same",
      issuedAt: 1000,
    });
    const { bridge, stop } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    const committed = await owner.execute(updateProfileCommand(owner, "owner-commit", {
      email: "revision-1@example.com",
    }));
    expect(committed).toMatchObject({ ok: true, revision: "1" });
    await Promise.resolve();

    const lower = {
      ...initial,
      revision: "0",
      snapshot: {
        ...initial.snapshot,
        profile: { ...initial.snapshot.profile, email: "lower@example.com" },
      },
    } satisfies Extract<SettingsInitialization, { status: "ready" }>;
    await eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, { initialization: lower });
    expect(bridge.getSnapshot()?.revision).toBe("1");
    expect(bridge.getSnapshot()?.profile.email).toBe("revision-1@example.com");

    const higher = {
      ...lower,
      revision: "2",
      stateSeq: "2",
      dataRevision: "2",
      snapshot: {
        ...lower.snapshot,
        profile: { ...lower.snapshot.profile, email: "higher@example.com" },
      },
    } satisfies Extract<SettingsInitialization, { status: "ready" }>;
    await eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, { initialization: higher });
    await settleEvents();
    expect(bridge.getSnapshot()?.revision).toBe("1");
    expect(bridge.getSnapshot()?.profile.email).toBe("revision-1@example.com");

    const committedAgain = await owner.execute(updateProfileCommand(owner, "owner-commit-2", {
      email: "revision-2@example.com",
    }));
    expect(committedAgain).toMatchObject({ ok: true, revision: "2", dataRevision: "2" });
    await settleEvents();
    expect(bridge.getSnapshot()?.revision).toBe("2");
    expect(bridge.getSnapshot()?.profile.email).toBe("revision-2@example.com");
    stop();
  });

  test("stale command results fail closed, then a fresh handshake enables a new-version retry", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-stale",
      issuedAt: 1000,
    });
    const { bridge, stop } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    const ownerCommit = await owner.execute(updateProfileCommand(owner, "owner-wins", {
      email: "owner-wins@example.com",
    }));
    expect(ownerCommit).toMatchObject({ ok: true, revision: "1" });
    await Promise.resolve();

    const stale = await bridge.updateProfile(
      { phone: "stale-must-not-write" },
      { expectedGeneration: initial.generation, expectedRevision: initial.revision },
      "stale-command",
    );
    expect(stale).toEqual({
      ok: false,
      reason: "stale-revision",
      correlationId: "stale-command",
    });
    expect(owner.getSnapshot()?.profile.phone).toBe(fixture.profile.phone);

    const refreshed = expectReady(await bridge.initialize());
    expect(refreshed.revision).toBe("1");
    const retried = await bridge.updateProfile(
      { phone: "13900000000" },
      { expectedGeneration: refreshed.generation, expectedRevision: refreshed.revision },
      "fresh-command",
    );
    expect(retried).toEqual({
      ok: true,
      snapshot: expect.any(Object),
      generation: refreshed.generation,
      revision: "2",
      ownerEpoch: refreshed.ownerEpoch,
      stateSeq: "2",
      dataRevision: "2",
      correlationId: "fresh-command",
      applied: true,
    });
    expect(owner.getSnapshot()?.profile.phone).toBe("13900000000");
    stop();
  });

  test("a command result timeout is not reported as success and replay returns the Owner result without a second write", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-timeout",
      issuedAt: 1000,
    });
    const { bridge, stop } = await startPair(owner, 15);
    const initial = expectReady(await bridge.initialize());
    const writesBefore = fixture.writeCount();
    eventBus.delayEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    eventBus.delayEvent(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT);

    const timedOut = await bridge.updateProfile(
      { email: "committed-during-timeout@example.com" },
      { expectedGeneration: initial.generation, expectedRevision: initial.revision },
      "timeout-command",
    );
    expect(timedOut).toEqual({
      ok: false,
      reason: "bridge-timeout",
      correlationId: "timeout-command",
    });
    const writesAfterCommit = fixture.writeCount();
    expect(writesAfterCommit).toBeGreaterThan(writesBefore);
    expect(owner.getSnapshot()?.profile.email).toBe("committed-during-timeout@example.com");

    eventBus.releaseEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    eventBus.releaseEvent(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT);
    await eventBus.flushDelayed();
    expect(bridge.getSnapshot()?.profile.email).toBe("committed-during-timeout@example.com");
    const committed = bridge.getSnapshot();
    if (!committed) throw new Error("committed snapshot was not synchronized");

    const replay = await bridge.updateProfile(
      { email: "committed-during-timeout@example.com" },
      { expectedGeneration: committed.generation, expectedRevision: committed.revision },
      "timeout-command",
    );
    expect(replay).toMatchObject({
      ok: true,
      correlationId: "timeout-command",
      revision: "1",
    });
    expect(fixture.writeCount()).toBe(writesAfterCommit);
    stop();
  });

  test("Owner unavailable or emitTo failure returns a blocked failure with zero business writes", async () => {
    const fixture = createStorageFixture();
    const bridge = createCompanionUserSettingsBridge({
      ownerWindow: "main",
      responseTimeoutMs: 15,
      sourceWindow: "platform",
    });
    eventBus.rejectTarget("main");

    const initialization = await bridge.initialize();
    expect(initialization.status).toBe("blocked");
    expect(bridge.getTransportState?.()).toMatchObject({ status: "bridge-timeout" });
    expect(initialization.status === "blocked" && "ownerEpoch" in initialization).toBe(false);
    expect(["owner-unavailable", "bridge-timeout"]).toContain(
      initialization.status === "blocked" ? initialization.reason : "unexpected",
    );
    const failed = await bridge.updateProfile(
      { email: "must-not-write@example.com" },
      { expectedGeneration: "missing", expectedRevision: "0" },
      "unavailable-command",
    );
    expect(failed).toEqual({
      ok: false,
      reason: "bridge-timeout",
      correlationId: "unavailable-command",
    });
    expect(fixture.writeCount()).toBe(0);
    expect(failed.ok).toBe(false);
  });

  test("duplicate initialize and duplicate snapshots do not create duplicate commands or writes", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-dedupe",
      issuedAt: 1000,
    });
    const { bridge, stop } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    const beforeCommands = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);

    const [first, second] = await Promise.all([bridge.initialize(), bridge.initialize()]);
    expect(first).toEqual(second);
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT)).toBe(beforeCommands + 1);
    expect(fixture.writeCount()).toBe(0);

    await eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, { initialization: initial });
    await eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, { initialization: initial });
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT)).toBe(beforeCommands + 1);
    expect(fixture.writeCount()).toBe(0);
    stop();
  });

  test("stopping the Owner Bridge removes its listeners and subscription", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-stop",
      issuedAt: 1000,
    });
    const { bridge, stop } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    stop();

    const result = await owner.execute(updateProfileCommand(owner, "after-stop", {
      email: "owner-changed-after-stop@example.com",
    }));
    expect(result).toMatchObject({ ok: true, revision: "1" });
    await Promise.resolve();
    expect(bridge.getSnapshot()).toMatchObject({
      generation: initial.generation,
      revision: initial.revision,
      profile: { email: fixture.profile.email },
    });
  });

  test("stopping the platform bridge absorbs late results and snapshots", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      generation: "generation-platform-stop",
      issuedAt: 1000,
    });
    const { bridge, stop: stopOwnerBridge } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    const commandCount = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);
    bridge.stop?.();

    const committed = await owner.execute(updateProfileCommand(owner, "after-platform-stop", {
      email: "late-platform-stop@example.com",
    }));
    expect(committed).toMatchObject({ ok: true, revision: "1" });
    await settleEvents();

    expect(bridge.getSnapshot()).toMatchObject({
      generation: initial.generation,
      revision: initial.revision,
      profile: { email: fixture.profile.email },
    });
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT)).toBe(commandCount);
    stopOwnerBridge();
  });

  test("the platform bridge can restart in the same context with one result and snapshot listener", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      ownerEpoch: "generation-restartable-platform",
      issuedAt: 1000,
    });
    const { bridge, stop: stopOwnerBridge } = await startPair(owner);
    expectReady(await bridge.initialize());
    await settleEvents();
    expect(eventBus.listenerCount(COMPANION_USER_SETTINGS_RESULT_EVENT)).toBe(1);
    expect(eventBus.listenerCount(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT)).toBe(1);

    bridge.stop?.();
    await settleEvents();
    expect(eventBus.listenerCount(COMPANION_USER_SETTINGS_RESULT_EVENT)).toBe(0);
    expect(eventBus.listenerCount(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT)).toBe(0);

    bridge.start?.();
    await settleEvents();
    expect(eventBus.listenerCount(COMPANION_USER_SETTINGS_RESULT_EVENT)).toBe(1);
    expect(eventBus.listenerCount(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT)).toBe(1);
    const commandCount = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);
    expectReady(await bridge.initialize());
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT)).toBe(commandCount + 1);

    bridge.stop?.();
    stopOwnerBridge();
  });

  test("an immediate restart during an in-flight explicit handshake creates a fresh lifecycle-scoped request", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      ownerEpoch: "owner-explicit-restart",
      generation: "owner-explicit-restart",
      issuedAt: 1000,
    });
    const { bridge, stop: stopOwnerBridge } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    await settleEvents();
    const commandCountBeforeRace = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);

    eventBus.delayEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    const first = bridge.initialize();
    await settleEvents();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeRace + 1);
    const delayedFirstResult = eventBus.takeDelayed();
    expect(delayedFirstResult).toHaveLength(1);

    bridge.stop?.();
    bridge.start?.();
    const second = bridge.initialize();
    expect(second).not.toBe(first);

    const firstSettled = await Promise.race([
      first,
      new Promise<null>((resolve) => setTimeout(() => resolve(null), 100)),
    ]);
    expect(firstSettled).not.toBeNull();
    await settleEvents();

    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeRace + 2);
    const restartedCommands = eventBus.commandPayloads().slice(commandCountBeforeRace);
    expect(restartedCommands).toHaveLength(2);
    expect(restartedCommands[0]).toMatchObject({ kind: "initialize" });
    expect(restartedCommands[1]).toMatchObject({ kind: "initialize" });
    expect(restartedCommands[1]?.expectedOwnerEpoch).toBeUndefined();
    const delayedSecondResult = eventBus.takeDelayed();
    expect(delayedSecondResult).toHaveLength(1);

    eventBus.releaseEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    await eventBus.emitExternal(
      COMPANION_USER_SETTINGS_RESULT_EVENT,
      delayedSecondResult[0]!.payload,
    );
    const recovered = expectReady(await second);
    await settleEvents();

    expect(recovered).toMatchObject({
      status: "ready",
      ownerEpoch: initial.ownerEpoch,
      generation: initial.generation,
      revision: initial.revision,
    });

    // The first lifecycle's result is intentionally delivered after the new
    // lifecycle has become ready. It must be a no-op for the current state.
    await eventBus.emitExternal(
      COMPANION_USER_SETTINGS_RESULT_EVENT,
      delayedFirstResult[0]!.payload,
    );
    await settleEvents();

    expect(bridge.getInitialization()).toMatchObject({
      status: "ready",
      ownerEpoch: initial.ownerEpoch,
      generation: initial.generation,
      revision: initial.revision,
    });
    expect(bridge.getSnapshot()).toMatchObject({
      ownerEpoch: initial.ownerEpoch,
      generation: initial.generation,
      revision: initial.revision,
      profile: initial.snapshot.profile,
      preferences: initial.snapshot.preferences,
    });
    expect(eventBus.listenerCount(COMPANION_USER_SETTINGS_RESULT_EVENT)).toBe(1);
    expect(eventBus.listenerCount(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT)).toBe(1);
    expect(fixture.writeCount()).toBe(0);

    bridge.stop?.();
    stopOwnerBridge();
  });

  test("a stopped lifecycle finalizer cannot clear or schedule work in the restarted lifecycle", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      ownerEpoch: "owner-finally-restart",
      generation: "owner-finally-restart",
      issuedAt: 1000,
    });
    const { bridge, stop: stopOwnerBridge } = await startPair(owner);
    await bridge.initialize();
    await settleEvents();
    const commandCountBeforeRace = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);

    eventBus.delayEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    const first = bridge.initialize();
    await settleEvents();
    const delayedFirstResult = eventBus.takeDelayed();
    expect(delayedFirstResult).toHaveLength(1);

    bridge.stop?.();
    bridge.start?.();
    const second = bridge.initialize();
    await settleEvents();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeRace + 2);
    const delayedSecondResult = eventBus.takeDelayed();
    expect(delayedSecondResult).toHaveLength(1);

    await Promise.race([
      first,
      new Promise<null>((resolve) => setTimeout(() => resolve(null), 100)),
    ]);
    await Promise.resolve();

    // If the old finally clears the new slot, this call creates a third
    // initialize command. A live new-lifecycle handshake must be shared.
    const third = bridge.initialize();
    expect(third).toBe(second);
    await settleEvents();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeRace + 2);
    expect(eventBus.takeDelayed()).toEqual([]);

    eventBus.releaseEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    await eventBus.emitExternal(
      COMPANION_USER_SETTINGS_RESULT_EVENT,
      delayedSecondResult[0]!.payload,
    );
    expectReady(await second);
    await eventBus.emitExternal(
      COMPANION_USER_SETTINGS_RESULT_EVENT,
      delayedFirstResult[0]!.payload,
    );
    await settleEvents();

    expect(bridge.getInitialization().status).toBe("ready");
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeRace + 2);
    expect(fixture.writeCount()).toBe(0);
    bridge.stop?.();
    stopOwnerBridge();
  });

  test("restart invalidates an in-flight automatic reconcile and its queued explicit retry", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      ownerEpoch: "owner-automatic-stop-restart",
      generation: "owner-automatic-stop-restart",
      issuedAt: 1000,
    });
    const { bridge, stop: stopOwnerBridge } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    await settleEvents();
    const commandCountBeforeAutomatic = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);

    fixture.setReadsBlocked(true);
    eventBus.delayEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    const blocked = await owner.initialize();
    expect(blocked).toMatchObject({
      status: "blocked",
      ownerEpoch: initial.ownerEpoch,
      stateSeq: "1",
    });
    await settleEvents();
    const automaticCommands = eventBus.commandPayloads().slice(commandCountBeforeAutomatic);
    expect(automaticCommands).toHaveLength(1);
    expect(automaticCommands[0]).toMatchObject({
      kind: "initialize",
      expectedOwnerEpoch: initial.ownerEpoch,
    });
    const delayedAutomaticResult = eventBus.takeDelayed();
    expect(delayedAutomaticResult).toHaveLength(1);
    const delayedAutomaticSnapshot = [...eventBus.history()]
      .reverse()
      .find((entry) => entry.event === COMPANION_USER_SETTINGS_SNAPSHOT_EVENT);
    expect(delayedAutomaticSnapshot).toBeDefined();

    const queued = bridge.initialize();
    await settleEvents();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeAutomatic + 1);

    fixture.setReadsBlocked(false);
    bridge.stop?.();
    const stoppedQueued = await Promise.race([
      queued,
      new Promise<null>((resolve) => setTimeout(() => resolve(null), 100)),
    ]);
    expect(stoppedQueued).not.toBeNull();

    bridge.start?.();
    const second = bridge.initialize();
    await settleEvents();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeAutomatic + 2);
    const restartedCommands = eventBus.commandPayloads().slice(commandCountBeforeAutomatic);
    expect(restartedCommands[1]).toMatchObject({ kind: "initialize" });
    expect(restartedCommands[1]?.expectedOwnerEpoch).toBeUndefined();
    const delayedSecondResult = eventBus.takeDelayed();
    expect(delayedSecondResult).toHaveLength(1);

    eventBus.releaseEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    await eventBus.emitExternal(
      COMPANION_USER_SETTINGS_RESULT_EVENT,
      delayedSecondResult[0]!.payload,
    );
    const recovered = expectReady(await second);
    await settleEvents();
    expect(recovered).toMatchObject({
      status: "ready",
      ownerEpoch: initial.ownerEpoch,
      stateSeq: "2",
      dataRevision: initial.dataRevision,
    });

    // Both messages belong to the invalidated automatic request. The old
    // result has no waiter and the old snapshot is lower than the new state.
    await eventBus.emitExternal(
      COMPANION_USER_SETTINGS_RESULT_EVENT,
      delayedAutomaticResult[0]!.payload,
    );
    await eventBus.emitExternal(
      COMPANION_USER_SETTINGS_SNAPSHOT_EVENT,
      delayedAutomaticSnapshot!.payload,
    );
    await settleEvents();

    expect(bridge.getInitialization()).toMatchObject({
      status: "ready",
      ownerEpoch: initial.ownerEpoch,
      stateSeq: "2",
      dataRevision: initial.dataRevision,
    });
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeAutomatic + 2);
    expect(eventBus.listenerCount(COMPANION_USER_SETTINGS_RESULT_EVENT)).toBe(1);
    expect(eventBus.listenerCount(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT)).toBe(1);
    expect(fixture.writeCount()).toBe(0);

    bridge.stop?.();
    stopOwnerBridge();
  });

  test("an explicit retry queued behind a mismatched automatic reconcile performs one unrestricted Owner reread", async () => {
    const fixture = createStorageFixture();
    fixture.setReadsBlocked(true);
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      ownerEpoch: "owner-a",
      generation: "owner-a",
      issuedAt: 1000,
    });
    const { bridge, stop: stopOwnerBridge } = await startPair(owner);

    const initial = await bridge.initialize();
    expect(initial).toMatchObject({
      status: "blocked",
      ownerEpoch: "owner-a",
      stateSeq: "0",
      dataRevision: "0",
    });
    await settleEvents();

    const commandCountBeforeAutomatic = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);
    eventBus.delayEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    const foreignSignal = {
      ...initial,
      generation: "owner-b",
      ownerEpoch: "owner-b",
      stateSeq: "1",
      dataRevision: "0",
      lastKnownDataRevision: "0",
      issuedAt: 2000,
    };
    await eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, {
      initialization: foreignSignal,
    });
    await settleEvents();

    const automaticCommands = eventBus.commandPayloads().slice(commandCountBeforeAutomatic);
    expect(automaticCommands).toHaveLength(1);
    expect(automaticCommands[0]).toMatchObject({
      kind: "initialize",
      expectedOwnerEpoch: "owner-b",
    });
    const delayedAutomaticResult = eventBus.takeDelayed();
    expect(delayedAutomaticResult).toHaveLength(1);

    fixture.setReadsBlocked(false);
    const retry = bridge.initialize();
    await settleEvents();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeAutomatic + 1);

    eventBus.releaseEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    await eventBus.flushDelayed();
    await settleEvents();

    const recovered = expectReady(await retry);
    const expectedProfile = { ...fixture.profile, nickname: "旧昵称" };
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeAutomatic + 2);
    const addedCommands = eventBus.commandPayloads().slice(commandCountBeforeAutomatic);
    expect(addedCommands).toHaveLength(2);
    expect(addedCommands[1]).toMatchObject({ kind: "initialize" });
    expect(addedCommands[1]?.expectedOwnerEpoch).toBeUndefined();
    expect(recovered).toMatchObject({
      status: "ready",
      ownerEpoch: "owner-a",
      stateSeq: "1",
      dataRevision: "0",
      snapshot: {
        profile: expectedProfile,
        preferences: fixture.preferences,
      },
    });
    expect(bridge.getSnapshot()).toMatchObject({
      ownerEpoch: "owner-a",
      stateSeq: "1",
      dataRevision: "0",
      profile: expectedProfile,
      preferences: fixture.preferences,
    });
    expect(fixture.writeCount()).toBe(0);
    expect(eventBus.takeDelayed()).toEqual([]);

    bridge.stop?.();
    stopOwnerBridge();
  });

  test("three explicit retries queued behind one automatic reconcile share one unrestricted reread", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      ownerEpoch: "owner-a",
      generation: "owner-a",
      issuedAt: 1000,
    });
    const { bridge, stop: stopOwnerBridge } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    await settleEvents();
    const commandCountBeforeAutomatic = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);

    eventBus.delayEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    await eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, {
      initialization: {
        ...initial,
        generation: "owner-b",
        ownerEpoch: "owner-b",
        stateSeq: "1",
        snapshot: {
          ...initial.snapshot,
          profile: { ...initial.snapshot.profile, email: "owner-b@example.com" },
        },
      },
    });
    await settleEvents();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeAutomatic + 1);
    const delayedAutomaticResult = eventBus.takeDelayed();
    expect(delayedAutomaticResult).toHaveLength(1);

    const retries = [bridge.initialize(), bridge.initialize(), bridge.initialize()];
    await settleEvents();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeAutomatic + 1);

    eventBus.releaseEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    await eventBus.emitExternal(
      delayedAutomaticResult[0]!.event,
      delayedAutomaticResult[0]!.payload,
    );
    const automaticCommand = eventBus.commandPayloads()[commandCountBeforeAutomatic];
    expect(automaticCommand?.expectedOwnerEpoch).toBe("owner-b");
    await settleEvents();

    const results = await Promise.all(retries);
    results.forEach((result) => expectReady(result));
    expect(results[0]).toEqual(results[1]);
    expect(results[1]).toEqual(results[2]);
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeAutomatic + 2);
    const addedCommands = eventBus.commandPayloads().slice(commandCountBeforeAutomatic);
    expect(addedCommands[1]?.expectedOwnerEpoch).toBeUndefined();
    expect(fixture.writeCount()).toBe(0);
    expect(eventBus.takeDelayed()).toEqual([]);

    bridge.stop?.();
    stopOwnerBridge();
  });

  test("an explicit blocked-to-ready recovery consumes a signal that arrives before its result", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      ownerEpoch: "owner-recovery-before-result",
      issuedAt: 1000,
    });
    const { bridge, stop: stopOwnerBridge } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    await settleEvents();

    fixture.setReadsBlocked(true);
    const blockedOwnerResult = await owner.execute(updateProfileCommand(
      owner,
      "explicit-recovery-blocked-before-result",
      { email: "must-not-write@example.com" },
    ));
    expect(blockedOwnerResult).toMatchObject({ ok: false, reason: "recovery-blocked" });
    await settleEvents();
    expect(bridge.getInitialization()).toMatchObject({ status: "blocked", stateSeq: "1" });
    const commandCountBeforeExplicit = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);
    fixture.setReadsBlocked(false);

    eventBus.delayEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    const retry = bridge.initialize();
    await settleEvents();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeExplicit + 1);
    const delayedResult = eventBus.takeDelayed();
    expect(delayedResult).toHaveLength(1);

    eventBus.releaseEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    await eventBus.emitExternal(
      delayedResult[0]!.event,
      delayedResult[0]!.payload,
    );
    const recovered = expectReady(await retry);
    await settleEvents();

    expect(recovered).toMatchObject({
      status: "ready",
      ownerEpoch: initial.ownerEpoch,
      stateSeq: "2",
      dataRevision: "0",
    });
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeExplicit + 1);
    expect(eventBus.takeDelayed()).toEqual([]);
    expect(fixture.writeCount()).toBe(0);
    bridge.stop?.();
    stopOwnerBridge();
  });

  test("an explicit blocked-to-ready recovery consumes a result that arrives before its signal", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      ownerEpoch: "owner-recovery-before-signal",
      issuedAt: 1000,
    });
    const { bridge, stop: stopOwnerBridge } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    await settleEvents();

    fixture.setReadsBlocked(true);
    const blockedOwnerResult = await owner.execute(updateProfileCommand(
      owner,
      "explicit-recovery-blocked-before-signal",
      { email: "must-not-write@example.com" },
    ));
    expect(blockedOwnerResult).toMatchObject({ ok: false, reason: "recovery-blocked" });
    await settleEvents();
    expect(bridge.getInitialization()).toMatchObject({ status: "blocked", stateSeq: "1" });
    const commandCountBeforeExplicit = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);
    fixture.setReadsBlocked(false);

    eventBus.delayEvent(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT);
    const retry = bridge.initialize();
    const recovered = expectReady(await retry);
    const delayedSignal = eventBus.takeDelayed();
    expect(delayedSignal).toHaveLength(1);
    eventBus.releaseEvent(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT);
    await eventBus.emitExternal(
      delayedSignal[0]!.event,
      delayedSignal[0]!.payload,
    );
    await settleEvents();

    expect(recovered).toMatchObject({
      status: "ready",
      ownerEpoch: initial.ownerEpoch,
      stateSeq: "2",
      dataRevision: "0",
    });
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeExplicit + 1);
    expect(eventBus.takeDelayed()).toEqual([]);
    expect(fixture.writeCount()).toBe(0);
    bridge.stop?.();
    stopOwnerBridge();
  });

  test("a user retry after automatic recovery still performs one explicit reread", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      ownerEpoch: "owner-automatic-recovery",
      issuedAt: 1000,
    });
    const { bridge, stop: stopOwnerBridge } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    await settleEvents();
    const commandCountBeforeAutomatic = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);

    eventBus.delayEvent(COMPANION_USER_SETTINGS_COMMAND_EVENT);
    fixture.setReadsBlocked(true);
    const blocked = await owner.initialize();
    expect(blocked).toMatchObject({ status: "blocked", stateSeq: "1" });
    await settleEvents();
    const delayedAutomaticCommand = eventBus.takeDelayed();
    expect(delayedAutomaticCommand).toHaveLength(1);
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeAutomatic + 1);

    fixture.setReadsBlocked(false);
    eventBus.delayEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    eventBus.releaseEvent(COMPANION_USER_SETTINGS_COMMAND_EVENT);
    await eventBus.emitExternal(
      delayedAutomaticCommand[0]!.event,
      delayedAutomaticCommand[0]!.payload,
    );
    await settleEvents();
    const delayedAutomaticResult = eventBus.takeDelayed();
    expect(delayedAutomaticResult).toHaveLength(1);
    expect(owner.getInitialization()).toMatchObject({ status: "ready", stateSeq: "2" });

    const retry = bridge.initialize();
    await settleEvents();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeAutomatic + 1);

    eventBus.releaseEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    await eventBus.emitExternal(
      delayedAutomaticResult[0]!.event,
      delayedAutomaticResult[0]!.payload,
    );
    const recovered = expectReady(await retry);
    await settleEvents();

    expect(recovered).toMatchObject({
      status: "ready",
      ownerEpoch: initial.ownerEpoch,
      stateSeq: "2",
      dataRevision: "0",
    });
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeAutomatic + 2);
    const addedCommands = eventBus.commandPayloads().slice(commandCountBeforeAutomatic);
    expect(addedCommands[0]?.expectedOwnerEpoch).toBe(initial.ownerEpoch);
    expect(addedCommands[1]?.expectedOwnerEpoch).toBeUndefined();
    expect(eventBus.takeDelayed()).toEqual([]);
    expect(fixture.writeCount()).toBe(0);
    bridge.stop?.();
    stopOwnerBridge();
  });

  test("stopping while an explicit retry is queued resolves it and absorbs late automatic events", async () => {
    const fixture = createStorageFixture();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      ownerEpoch: "owner-stop-race",
      issuedAt: 1000,
    });
    const { bridge, stop: stopOwnerBridge } = await startPair(owner);
    const initial = expectReady(await bridge.initialize());
    await settleEvents();
    const commandCountBeforeAutomatic = eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT);

    eventBus.delayEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    await eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, {
      initialization: {
        ...initial,
        generation: "owner-stop-foreign",
        ownerEpoch: "owner-stop-foreign",
        stateSeq: "1",
        snapshot: {
          ...initial.snapshot,
          profile: { ...initial.snapshot.profile, email: "late-owner@example.com" },
        },
      },
    });
    await settleEvents();
    expect(eventBus.takeDelayed()).toHaveLength(1);

    const retry = bridge.initialize();
    bridge.stop?.();
    const stoppedRetry = await Promise.race([
      retry,
      new Promise<null>((resolve) => setTimeout(() => resolve(null), 100)),
    ]);
    expect(stoppedRetry).not.toBeNull();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeAutomatic + 1);
    await settleEvents();

    eventBus.releaseEvent(COMPANION_USER_SETTINGS_RESULT_EVENT);
    await eventBus.emitExternal(COMPANION_USER_SETTINGS_SNAPSHOT_EVENT, {
      initialization: {
        ...initial,
        generation: "owner-stop-foreign",
        ownerEpoch: "owner-stop-foreign",
        stateSeq: "2",
        snapshot: initial.snapshot,
      },
    });
    await eventBus.flushDelayed();
    await settleEvents();
    expect(eventBus.count(COMPANION_USER_SETTINGS_COMMAND_EVENT))
      .toBe(commandCountBeforeAutomatic + 1);
    expect(bridge.getSnapshot()).toMatchObject({
      ownerEpoch: initial.ownerEpoch,
      stateSeq: initial.stateSeq,
      dataRevision: initial.dataRevision,
      profile: initial.snapshot.profile,
      preferences: initial.snapshot.preferences,
    });
    stopOwnerBridge();
  });
});
