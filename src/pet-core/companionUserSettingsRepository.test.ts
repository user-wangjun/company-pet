import { describe, expect, test, vi } from "vitest";
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
  createCompanionForgetService,
  createCompanionPreferenceService,
  type CompanionPreferenceCommandStore,
} from "./companionLocalDataService";
import { createCompanionMemoryRepository } from "./companionMemory";
import type { CompanionInput } from "./companionHarnessTypes";
import {
  COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY,
  COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
  type CompanionUserProfileSyncStorage,
} from "./companionUserProfileSync";
import {
  createCompanionUserSettingsOwner,
  createCompanionUserSettingsRepository,
  type CompanionUserSettingsRepository,
  type SettingsExpectedVersion,
} from "./companionUserSettingsRepository";

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

function seededPreferences(): CompanionPreferencesState {
  return {
    preferences: [
      nicknamePreference("旧昵称"),
      replyStylePreference("short-and-soft"),
    ],
    recentPreferenceId: "global.replyStyle",
  };
}

function createStorage() {
  const profile: CompanionUserProfile = {
    ...EMPTY_COMPANION_USER_PROFILE,
    email: "old@example.com",
    phone: "13800138000",
  };
  const preferences = seededPreferences();
  const values = new Map<string, string>([
    [COMPANION_USER_PROFILE_STORAGE_KEY, JSON.stringify(profile)],
    [COMPANION_PREFERENCES_STORAGE_KEY, JSON.stringify(preferences)],
    [COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY, JSON.stringify({
      schemaVersion: 1,
      state: "preference-authoritative",
    })],
  ]);
  const failedReads = new Set<string>();
  let readsBlocked = false;
  const storage: CompanionUserProfileSyncStorage = {
    getItem: vi.fn((key: string) => {
      if (readsBlocked) throw new Error(`persistent read failure: ${key}`);
      if (failedReads.delete(key)) throw new Error(`read failure: ${key}`);
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
    failNextRead: (key: string) => failedReads.add(key),
    setReadsBlocked: (value: boolean) => { readsBlocked = value; },
    raw: (key: string) => values.get(key) ?? null,
    writeCount: () => (storage.setItem as ReturnType<typeof vi.fn>).mock.calls.length,
  };
}

function commandInput(overrides: Partial<CompanionInput> = {}): CompanionInput {
  return {
    requestId: "settings-repair-request",
    sessionId: "settings-repair-session",
    sourceMessageId: "settings-repair-message",
    userId: "local-user",
    petId: "xiaoju-cat",
    message: "以后叫我新昵称",
    currentTime: "2026-08-14T00:00:00.000Z",
    timezone: "Asia/Shanghai",
    utcOffsetMinutes: 480,
    source: "chat",
    ...overrides,
  };
}

function expectedVersion(repository: CompanionUserSettingsRepository): SettingsExpectedVersion {
  const snapshot = repository.getSnapshot();
  if (!snapshot) throw new Error("settings repository is not ready in test");
  return {
    expectedGeneration: snapshot.generation,
    expectedRevision: snapshot.revision,
    expectedOwnerEpoch: snapshot.ownerEpoch,
    expectedStateSeq: snapshot.stateSeq,
    expectedDataRevision: snapshot.dataRevision,
  };
}

function preferenceCommandStore(
  repository: CompanionUserSettingsRepository,
): CompanionPreferenceCommandStore {
  return {
    read: repository.getSnapshot,
    upsert: repository.upsertPreference,
    delete: repository.deletePreference,
  };
}

function createMemoryRepository() {
  const values = new Map<string, string>();
  return createCompanionMemoryRepository({
    storage: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => { values.set(key, value); },
    },
    now: () => Date.parse("2026-08-14T00:00:00.000Z"),
  });
}

function saveActiveMemory(repository: ReturnType<typeof createMemoryRepository>, id: string) {
  repository.save({
    id,
    scope: "global",
    type: "preference",
    content: "安全的旧 Memory",
    source: "explicit",
    evidence: "用户明确输入",
    sourceMessageId: "settings-repair-memory",
    confidence: 1,
    expiresAt: null,
    status: "active",
    supersedesId: null,
  });
}

describe("companion user settings Repository/Owner", () => {
  test("P0-1: a one-time read error blocks Settings and all dependent writes", async () => {
    const cases = [
      [COMPANION_USER_PROFILE_STORAGE_KEY, "read-failed"],
      [COMPANION_PREFERENCES_STORAGE_KEY, "read-failed"],
      [COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY, "read-failed"],
      [COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY, "recovery-blocked"],
    ] as const;

    for (const [key, reason] of cases) {
      const fixture = createStorage();
      fixture.failNextRead(key);
      const owner = createCompanionUserSettingsOwner(fixture.storage);
      const repository = createCompanionUserSettingsRepository({ owner });
      const initial = repository.getInitialization();
      expect(initial).toMatchObject({ status: "blocked", reason });
      expect(repository.getSnapshot()).toBeNull();

      const committedSnapshots: unknown[] = [];
      repository.subscribe((next) => committedSnapshots.push(next));
      const settingsResult = await repository.updateProfile(
        { email: "must-not-overwrite@example.com" },
        {
          expectedGeneration: "missing-generation",
          expectedRevision: "0",
        },
        `blocked-settings-${key}`,
      );
      expect(settingsResult).toEqual({
        ok: false,
        reason,
        correlationId: `blocked-settings-${key}`,
      });

      const preferenceService = createCompanionPreferenceService(preferenceCommandStore(repository));
      const preferenceResult = await preferenceService.process(
        commandInput({
          requestId: `blocked-preference-${key}`,
          sourceMessageId: `blocked-preference-${key}`,
        }),
        {
          sourceMessageId: `blocked-preference-${key}`,
          preference: nicknamePreference("harness-must-not-write"),
        },
        new AbortController().signal,
      );
      expect(preferenceResult.status).toBe("failed");

      const memoryRepository = createMemoryRepository();
      saveActiveMemory(memoryRepository, `blocked-memory-${key}`);
      const forgetService = createCompanionForgetService({
        preferences: preferenceCommandStore(repository),
        memoryRepository,
      });
      const forgetResult = await forgetService.process(
        commandInput({
          requestId: `blocked-forget-${key}`,
          sourceMessageId: `blocked-forget-${key}`,
          message: "忘掉刚才这条",
        }),
        new AbortController().signal,
      );
      expect(forgetResult.status).toBe("failed");
      expect(memoryRepository.list()[0]?.status).toBe("active");
      expect(committedSnapshots).toEqual([]);
      expect(fixture.writeCount()).toBe(0);

      const restarted = createCompanionUserSettingsOwner(fixture.storage);
      const restartedSnapshot = restarted.getSnapshot();
      expect(restarted.getInitialization().status).toBe("ready");
      expect(restartedSnapshot?.profile.email).toBe(fixture.profile.email);
      expect(restartedSnapshot?.preferences).toEqual(fixture.preferences);
      expect(fixture.raw(COMPANION_USER_PROFILE_STORAGE_KEY)).toBe(
        JSON.stringify(fixture.profile),
      );
    }
  });

  test("P0-2: stale clients fail closed and preserve the newer Profile commit", async () => {
    const fixture = createStorage();
    const owner = createCompanionUserSettingsOwner(fixture.storage);
    const clientA = createCompanionUserSettingsRepository({ owner });
    const clientB = createCompanionUserSettingsRepository({ owner });
    const expectedA = expectedVersion(clientA);
    const expectedB = expectedVersion(clientB);

    const profileResult = await clientA.updateProfile(
      { email: "a@example.com", nickname: "A的新昵称" },
      expectedA,
      "profile-a",
    );
    expect(profileResult.ok).toBe(true);

    const preferenceResult = await clientB.upsertPreference(
      replyStylePreference("B的新风格"),
      expectedB,
      "preference-b-stale",
    );
    expect(preferenceResult).toEqual({
      ok: false,
      reason: "stale-revision",
      correlationId: "preference-b-stale",
    });

    const final = owner.getSnapshot();
    expect(final?.profile.email).toBe("a@example.com");
    expect(final?.profile.nickname).toBe("A的新昵称");
    expect(final?.preferences.preferences.find((item) => item.id === "global.replyStyle")?.value)
      .toBe("short-and-soft");
  });

  test("P0-2 reverse order: a stale Profile command cannot erase a newer Preference commit", async () => {
    const fixture = createStorage();
    const owner = createCompanionUserSettingsOwner(fixture.storage);
    const clientA = createCompanionUserSettingsRepository({ owner });
    const clientB = createCompanionUserSettingsRepository({ owner });
    const expectedA = expectedVersion(clientA);
    const expectedB = expectedVersion(clientB);

    const preferenceResult = await clientB.upsertPreference(
      replyStylePreference("B的新风格"),
      expectedB,
      "preference-b",
    );
    expect(preferenceResult.ok).toBe(true);

    const profileResult = await clientA.updateProfile(
      { email: "a@example.com", nickname: "A的新昵称" },
      expectedA,
      "profile-a-stale",
    );
    expect(profileResult).toEqual({
      ok: false,
      reason: "stale-revision",
      correlationId: "profile-a-stale",
    });

    const final = owner.getSnapshot();
    expect(final?.profile.email).toBe("old@example.com");
    expect(final?.profile.nickname).toBe("旧昵称");
    expect(final?.preferences.preferences.find((item) => item.id === "global.replyStyle")?.value)
      .toBe("B的新风格");
  });

  test("P0-2 stale deletion and same-field conflicts cannot report two successful writes", async () => {
    const fixture = createStorage();
    const owner = createCompanionUserSettingsOwner(fixture.storage);
    const clientA = createCompanionUserSettingsRepository({ owner });
    const clientB = createCompanionUserSettingsRepository({ owner });
    const expectedA = expectedVersion(clientA);
    const expectedB = expectedVersion(clientB);

    const first = await clientA.upsertPreference(
      replyStylePreference("A的新风格"),
      expectedA,
      "preference-a",
    );
    expect(first.ok).toBe(true);
    const staleDelete = await clientB.deletePreference(
      "global.nickname",
      expectedB,
      "delete-stale",
    );
    expect(staleDelete).toEqual({
      ok: false,
      reason: "stale-revision",
      correlationId: "delete-stale",
    });

    const second = await clientB.upsertPreference(
      replyStylePreference("B的新风格"),
      expectedB,
      "preference-b-same-field-stale",
    );
    expect(second.ok).toBe(false);
    expect(owner.getSnapshot()?.preferences.preferences.find((item) => item.id === "global.replyStyle")?.value)
      .toBe("A的新风格");
  });

  test("P0-2 owner restart changes generation and invalidates an old client", async () => {
    const fixture = createStorage();
    const firstOwner = createCompanionUserSettingsOwner(fixture.storage);
    const staleClient = createCompanionUserSettingsRepository({ owner: firstOwner });
    const staleExpected = expectedVersion(staleClient);
    const firstCommit = await staleClient.updateProfile(
      { email: "first@example.com" },
      staleExpected,
      "first-owner-commit",
    );
    expect(firstCommit.ok).toBe(true);

    const restartedOwner = createCompanionUserSettingsOwner(fixture.storage);
    const restartedRepository = createCompanionUserSettingsRepository({ owner: restartedOwner });
    const restartedExpected = expectedVersion(restartedRepository);
    const restartCommit = await restartedRepository.updateProfile(
      { phone: "13900000000" },
      restartedExpected,
      "restarted-owner-commit",
    );
    expect(restartCommit.ok).toBe(true);

    const staleResult = await staleClient.updateProfile(
      { email: "stale-overwrite@example.com" },
      staleExpected,
      "old-client-after-restart",
    );
    expect(staleResult).toEqual({
      ok: false,
      reason: "stale-revision",
      correlationId: "old-client-after-restart",
    });
    expect(restartedOwner.getSnapshot()?.profile).toMatchObject({
      email: "first@example.com",
      phone: "13900000000",
    });
  });

  test("Owner Protocol V2 separates stateSeq from dataRevision and suppresses unchanged retries", async () => {
    const fixture = createStorage();
    const owner = createCompanionUserSettingsOwner(fixture.storage, {
      ownerEpoch: "owner-epoch-v2",
      issuedAt: 1000,
    });
    const notifications: Array<ReturnType<typeof owner.getInitialization>> = [];
    owner.subscribe((next) => notifications.push(next));

    const initial = owner.getInitialization();
    expect(initial).toMatchObject({
      status: "ready",
      ownerEpoch: "owner-epoch-v2",
      stateSeq: "0",
      dataRevision: "0",
      generation: "owner-epoch-v2",
      revision: "0",
    });

    const unchangedReady = await owner.initialize();
    expect(unchangedReady).toMatchObject({
      status: "ready",
      ownerEpoch: "owner-epoch-v2",
      stateSeq: "0",
      dataRevision: "0",
    });
    expect(notifications).toHaveLength(0);

    fixture.setReadsBlocked(true);
    const blocked = await owner.initialize();
    expect(blocked).toMatchObject({
      status: "blocked",
      reason: "recovery-blocked",
      ownerEpoch: "owner-epoch-v2",
      stateSeq: "1",
      dataRevision: "0",
      lastKnownDataRevision: "0",
    });
    expect(owner.getSnapshot()).toBeNull();
    expect(notifications).toHaveLength(1);

    const unchangedBlocked = await owner.initialize();
    expect(unchangedBlocked).toEqual(blocked);
    expect(notifications).toHaveLength(1);

    fixture.setReadsBlocked(false);
    const recovered = await owner.initialize();
    expect(recovered).toMatchObject({
      status: "ready",
      ownerEpoch: "owner-epoch-v2",
      stateSeq: "2",
      dataRevision: "0",
    });
    expect(notifications).toHaveLength(2);

    const staleStateCommand = await owner.execute({
      type: "updateProfile",
      patch: { email: "stale-state-must-not-write@example.com" },
      expectedGeneration: initial.generation,
      expectedRevision: initial.revision,
      expectedOwnerEpoch: initial.ownerEpoch,
      expectedStateSeq: initial.stateSeq,
      expectedDataRevision: initial.dataRevision,
      correlationId: "v2-stale-state",
    });
    expect(staleStateCommand).toEqual({
      ok: false,
      reason: "stale-revision",
      correlationId: "v2-stale-state",
    });

    const committed = await owner.execute({
      type: "updateProfile",
      patch: { email: "v2-commit@example.com" },
      expectedGeneration: recovered.generation,
      expectedRevision: recovered.revision,
      expectedOwnerEpoch: recovered.ownerEpoch,
      expectedStateSeq: recovered.stateSeq,
      expectedDataRevision: recovered.dataRevision,
      correlationId: "v2-commit",
    });
    expect(committed).toMatchObject({
      ok: true,
      ownerEpoch: "owner-epoch-v2",
      stateSeq: "3",
      dataRevision: "1",
      generation: "owner-epoch-v2",
      revision: "1",
    });
    expect(notifications).toHaveLength(3);
  });

  test("correlation replay returns the committed result without a second write", async () => {
    const fixture = createStorage();
    const owner = createCompanionUserSettingsOwner(fixture.storage);
    const repository = createCompanionUserSettingsRepository({ owner });
    const expected = expectedVersion(repository);
    const first = await repository.upsertPreference(
      replyStylePreference("一次提交"),
      expected,
      "replay-correlation",
    );
    const writesAfterFirst = fixture.writeCount();
    const replay = await repository.upsertPreference(
      replyStylePreference("一次提交"),
      expected,
      "replay-correlation",
    );
    expect(replay).toEqual(first);
    expect(fixture.writeCount()).toBe(writesAfterFirst);
  });
});
