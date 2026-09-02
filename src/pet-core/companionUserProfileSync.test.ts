import { describe, expect, test, vi } from "vitest";
import {
  deleteRecentPreference,
  EMPTY_COMPANION_PREFERENCES,
  readCompanionPreferences,
  upsertCompanionPreference,
  writeCompanionPreferences,
  COMPANION_PREFERENCES_STORAGE_KEY,
  type CompanionPreferencesState,
} from "./companionPreferences";
import {
  EMPTY_COMPANION_USER_PROFILE,
  COMPANION_USER_PROFILE_STORAGE_KEY,
  readCompanionUserProfile,
  writeCompanionUserProfile,
  type CompanionUserProfile,
} from "./companionUserProfile";
import {
  COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY,
  COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
  createCompanionUserProfilePreferencePersistenceForTest,
  createCompanionUserProfilePreferenceStore,
  initializeCompanionUserProfileState,
  migrateLegacyCompanionUserProfileNickname,
  resolveCompanionUserProfileFromPreferences,
} from "./companionUserProfileSync";

type LegacyTestStartupState = {
  profile: CompanionUserProfile;
  preferences: CompanionPreferencesState;
  migrated: boolean;
  migrationAttempted: boolean;
  migrationFailed: boolean;
  recovery: "none" | "recovered" | "committed" | "blocked";
};

function legacyTestStartupState(
  startup: ReturnType<typeof initializeCompanionUserProfileState>,
): LegacyTestStartupState {
  if (startup.status === "ready") return startup;
  return {
    profile: { ...EMPTY_COMPANION_USER_PROFILE },
    preferences: clonePreferences(EMPTY_COMPANION_PREFERENCES),
    migrated: false,
    migrationAttempted: false,
    migrationFailed: false,
    recovery: "blocked",
  };
}

function nicknamePreference(value: string) {
  return {
    id: "global.nickname" as const,
    scope: "global" as const,
    category: "userProfile" as const,
    key: "nickname" as const,
    value,
    source: "explicit" as const,
  };
}

function clonePreferences(state: CompanionPreferencesState): CompanionPreferencesState {
  return {
    preferences: state.preferences.map((preference) => ({ ...preference })),
    recentPreferenceId: state.recentPreferenceId,
  };
}

function createFixture(
  initialProfile: CompanionUserProfile = EMPTY_COMPANION_USER_PROFILE,
  initialPreferences: CompanionPreferencesState = EMPTY_COMPANION_PREFERENCES,
) {
  let profile = { ...initialProfile };
  let preferences = clonePreferences(initialPreferences);
  let profileWriteCount = 0;
  let preferencesWriteCount = 0;
  const failedProfileWriteCalls = new Set<number>();
  const failedPreferenceWriteCalls = new Set<number>();
  const commits: Array<{ profile: CompanionUserProfile; preferences: CompanionPreferencesState }> = [];
  const persistence = createCompanionUserProfilePreferencePersistenceForTest({
    initialProfile: profile,
    initialPreferences: preferences,
    readProfile: () => profile,
    readPreferences: () => preferences,
    readProfileSnapshot: () => ({ status: "present-valid" as const, value: { ...profile } }),
    readPreferencesSnapshot: () => ({ status: "present-valid" as const, value: clonePreferences(preferences) }),
    writeProfile: vi.fn((next) => {
      profileWriteCount += 1;
      if (failedProfileWriteCalls.has(profileWriteCount)) return false;
      profile = { ...next };
      return true;
    }),
    writePreferences: vi.fn((next) => {
      preferencesWriteCount += 1;
      if (failedPreferenceWriteCalls.has(preferencesWriteCount)) return false;
      preferences = clonePreferences(next);
      return true;
    }),
    onCommitted: (nextProfile, nextPreferences) => {
      commits.push({
        profile: { ...nextProfile },
        preferences: clonePreferences(nextPreferences),
      });
    },
  });
  return {
    persistence,
    read: () => ({ profile: { ...profile }, preferences: clonePreferences(preferences) }),
    restart: () => createFixture(profile, preferences),
    commits,
    failProfileWriteCall: (call: number) => { failedProfileWriteCalls.add(call); },
    failPreferenceWriteCall: (call: number) => { failedPreferenceWriteCalls.add(call); },
    getWriteCounts: () => ({ profile: profileWriteCount, preferences: preferencesWriteCount }),
  };
}

function renamedPreferences(value: string): CompanionPreferencesState {
  return upsertCompanionPreference(EMPTY_COMPANION_PREFERENCES, nicknamePreference(value));
}

function preferencesWithNicknameAndReplyStyle(
  nickname: string,
  replyStyle: string,
): CompanionPreferencesState {
  return upsertCompanionPreference(renamedPreferences(nickname), {
    id: "global.replyStyle",
    scope: "global",
    category: "userProfile",
    key: "replyStyle",
    value: replyStyle,
    source: "explicit",
  });
}

function createRawStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  const failedReads = new Set<string>();
  return {
    storage: {
      getItem: vi.fn((key: string) => {
        if (failedReads.delete(key)) {
          throw new Error(`injected raw read failure for ${key}`);
        }
        return values.get(key) ?? null;
      }),
      setItem: vi.fn((key: string, value: string) => {
        values.set(key, value);
      }),
      removeItem: vi.fn((key: string) => {
        values.delete(key);
      }),
    },
    raw: (key: string) => values.get(key) ?? null,
    failNextRead: (key: string) => { failedReads.add(key); },
  };
}

function readCurrentAppStartup(storage: ReturnType<typeof createRawStorage>["storage"]) {
  return legacyTestStartupState(
    initializeCompanionUserProfileState(
      createCompanionUserProfilePreferenceStore(storage),
    ),
  );
}

function createDurableProfileFixture(
  initialProfile: CompanionUserProfile,
  initialPreferences: CompanionPreferencesState,
) {
  const raw = createRawStorage({
    [COMPANION_USER_PROFILE_STORAGE_KEY]: JSON.stringify(initialProfile),
    [COMPANION_PREFERENCES_STORAGE_KEY]: JSON.stringify(initialPreferences),
  });
  const store = createCompanionUserProfilePreferenceStore(raw.storage);
  const readProfile = store.readProfile;
  const readPreferences = store.readPreferences;
  const readProfileSnapshot = store.readProfileSnapshot!;
  const readPreferencesSnapshot = store.readPreferencesSnapshot!;
  let profileReadCount = 0;
  let preferencesReadCount = 0;
  let profileSnapshotReadFailureAt: number | null = null;
  let preferencesSnapshotReadFailureAt: number | null = null;
  let profileSnapshotReadFailureTriggered = false;
  let preferencesSnapshotReadFailureTriggered = false;
  const readProfileWithFault = () => {
    profileReadCount += 1;
    if (profileReadCount === profileSnapshotReadFailureAt) {
      profileSnapshotReadFailureAt = null;
      profileSnapshotReadFailureTriggered = true;
      throw new Error("injected profile snapshot read failure");
    }
    return readProfile();
  };
  const readPreferencesWithFault = () => {
    preferencesReadCount += 1;
    if (preferencesReadCount === preferencesSnapshotReadFailureAt) {
      preferencesSnapshotReadFailureAt = null;
      preferencesSnapshotReadFailureTriggered = true;
      throw new Error("injected preferences snapshot read failure");
    }
    return readPreferences();
  };
  store.readProfile = readProfileWithFault;
  store.readProfileSnapshot = () => {
    profileReadCount += 1;
    if (profileReadCount === profileSnapshotReadFailureAt) {
      profileSnapshotReadFailureAt = null;
      profileSnapshotReadFailureTriggered = true;
      throw new Error("injected profile snapshot read failure");
    }
    return readProfileSnapshot();
  };
  store.readPreferences = readPreferencesWithFault;
  store.readPreferencesSnapshot = () => {
    preferencesReadCount += 1;
    if (preferencesReadCount === preferencesSnapshotReadFailureAt) {
      preferencesSnapshotReadFailureAt = null;
      preferencesSnapshotReadFailureTriggered = true;
      throw new Error("injected preferences snapshot read failure");
    }
    return readPreferencesSnapshot();
  };
  const calls = {
    profile: 0,
    preferences: 0,
    recovery: 0,
    marker: 0,
  };
  let commits = 0;
  const failProfile = new Set<number>();
  const failPreferences = new Set<number>();
  const failRecovery = new Set<number>();
  const failMarker = new Set<number>();
  let failRecoveryCleanup = false;
  let failRecoveryReadbackOnce = false;
  let failProfileRestoreReadbackOnce = false;
  const writeProfile = store.writeProfile;
  const writePreferences = store.writePreferences;
  const writeRecoveryRecord = store.writeRecoveryRecord!;
  const writeMigrationMarker = store.writeMigrationMarker!;
  const clearRecoveryRecord = store.clearRecoveryRecord!;
  store.writeProfile = (next) => {
    calls.profile += 1;
    if (failProfile.has(calls.profile)) return false;
    const result = writeProfile(next);
    if (result && failProfileRestoreReadbackOnce && calls.profile > 1) {
      failProfileRestoreReadbackOnce = false;
      raw.failNextRead(COMPANION_USER_PROFILE_STORAGE_KEY);
    }
    return result;
  };
  store.writePreferences = (next) => {
    calls.preferences += 1;
    if (failPreferences.has(calls.preferences)) return false;
    return writePreferences(next);
  };
  store.writeRecoveryRecord = (next) => {
    calls.recovery += 1;
    if (failRecovery.has(calls.recovery)) return false;
    const result = writeRecoveryRecord(next);
    if (result && failRecoveryReadbackOnce) {
      failRecoveryReadbackOnce = false;
      raw.failNextRead(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY);
    }
    return result;
  };
  store.writeMigrationMarker = (next) => {
    calls.marker += 1;
    if (failMarker.has(calls.marker)) return false;
    return writeMigrationMarker(next);
  };
  store.clearRecoveryRecord = () => failRecoveryCleanup ? false : clearRecoveryRecord();

  const persistence = createCompanionUserProfilePreferencePersistenceForTest({
    ...store,
    initialProfile,
    initialPreferences,
    onCommitted: () => {
      commits += 1;
    },
  });
  const snapshot = () => Object.fromEntries(
    [
      COMPANION_USER_PROFILE_STORAGE_KEY,
      COMPANION_PREFERENCES_STORAGE_KEY,
      COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
      COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY,
    ].flatMap((key) => {
      const value = raw.raw(key);
      return value === null ? [] : [[key, value] as const];
    }),
  );
  const restart = () => {
    const fresh = createRawStorage(snapshot());
    const freshStore = createCompanionUserProfilePreferenceStore(fresh.storage);
    const state = legacyTestStartupState(initializeCompanionUserProfileState(freshStore));
    return { ...fresh, store: freshStore, state };
  };
  return {
    raw,
    store,
    persistence,
    calls,
    getCommits: () => commits,
    failProfile,
    failPreferences,
    failRecovery,
    failMarker,
    // The current transaction performs its complete raw snapshot after the
    // recovery preflight. Schedule the next snapshot read so the injected
    // fault is explicitly a transaction snapshot fault, not a startup read
    // fault. The counters make any protocol drift diagnosable.
    failNextProfileSnapshotRead: () => {
      profileSnapshotReadFailureAt = profileReadCount + 1;
    },
    failNextPreferencesSnapshotRead: () => {
      preferencesSnapshotReadFailureAt = preferencesReadCount + 1;
    },
    getReadCounts: () => ({ profile: profileReadCount, preferences: preferencesReadCount }),
    getReadFaults: () => ({
      profile: profileSnapshotReadFailureTriggered,
      preferences: preferencesSnapshotReadFailureTriggered,
    }),
    failRecoveryReadback: () => { failRecoveryReadbackOnce = true; },
    failProfileRestoreReadback: () => { failProfileRestoreReadbackOnce = true; },
    setFailRecoveryCleanup: (value: boolean) => { failRecoveryCleanup = value; },
    restart,
  };
}

function expectNoDurableTransactionWrites(
  fixture: ReturnType<typeof createDurableProfileFixture>,
) {
  const businessKeys = new Set([
    COMPANION_USER_PROFILE_STORAGE_KEY,
    COMPANION_PREFERENCES_STORAGE_KEY,
  ]);
  expect(fixture.raw.storage.setItem.mock.calls.filter(([key]) => businessKeys.has(key))).toHaveLength(0);
  expect(fixture.raw.storage.removeItem.mock.calls.filter(([key]) => businessKeys.has(key))).toHaveLength(0);
  expect(fixture.raw.storage.setItem.mock.calls.filter(([key]) =>
    key === COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
  )).toHaveLength(0);
  expect(fixture.raw.storage.removeItem.mock.calls.filter(([key]) =>
    key === COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
  )).toHaveLength(0);
}

describe("companion profile and Preference consistency", () => {
  test("chat nickname write is immediately visible when settings are opened", () => {
    const fixture = createFixture();
    const nextPreferences = renamedPreferences("阿星");

    expect(fixture.persistence.persistPreferences(nextPreferences)).toBe(true);
    expect(fixture.persistence.getProfile().nickname).toBe("阿星");
    expect(fixture.persistence.getPreferences()).toEqual(nextPreferences);
    expect(fixture.commits).toHaveLength(1);
    // Profile is a compatibility mirror; nickname authority is Preference.
    expect(fixture.read().profile.nickname).toBe("");
    expect(fixture.restart().persistence.getProfile().nickname).toBe("阿星");
  });

  test("saving email after a chat nickname change keeps the authoritative nickname", () => {
    const fixture = createFixture();
    const renamed = renamedPreferences("小星");
    expect(fixture.persistence.persistPreferences(renamed)).toBe(true);

    const nextProfile = {
      ...fixture.persistence.getProfile(),
      email: "hello@example.com",
    };
    expect(fixture.persistence.persistProfile(nextProfile, renamed)).toBe(true);
    expect(fixture.read()).toEqual({
      profile: {
        nickname: "",
        gender: "unspecified",
        email: "hello@example.com",
        phone: "",
      },
      preferences: renamed,
    });
    expect(fixture.restart().persistence.getProfile()).toEqual(fixture.persistence.getProfile());
  });

  test("forget removes the mirrored nickname before settings are reopened or restarted", () => {
    const fixture = createFixture();
    const renamed = renamedPreferences("阿星");
    expect(fixture.persistence.persistPreferences(renamed)).toBe(true);

    const forgotten = deleteRecentPreference(renamed);
    expect(fixture.persistence.persistPreferences(forgotten)).toBe(true);
    expect(fixture.persistence.getProfile().nickname).toBe("");
    expect(fixture.read()).toEqual({
      profile: EMPTY_COMPANION_USER_PROFILE,
      preferences: EMPTY_COMPANION_PREFERENCES,
    });
    expect(fixture.restart().persistence.getProfile().nickname).toBe("");
  });

  test("a failed first Profile write leaves disk, memory, result, and restart unchanged", () => {
    const fixture = createFixture(
      { ...EMPTY_COMPANION_USER_PROFILE, email: "old@example.com" },
      renamedPreferences("旧昵称"),
    );
    fixture.failProfileWriteCall(1);

    const result = fixture.persistence.persistProfile({
      ...fixture.persistence.getProfile(),
      email: "new@example.com",
    }, fixture.persistence.getPreferences());

    expect(result).toBe(false);
    expect(fixture.commits).toHaveLength(0);
    expect(fixture.read().profile.email).toBe("old@example.com");
    expect(fixture.restart().persistence.getProfile()).toEqual(fixture.persistence.getProfile());
  });

  test("a failed Preference write cannot leave a new nickname in Profile", () => {
    const fixture = createFixture();
    fixture.failPreferenceWriteCall(1);

    expect(fixture.persistence.persistPreferences(renamedPreferences("不会保存"))).toBe(false);
    expect(fixture.commits).toHaveLength(0);
    expect(fixture.read()).toEqual({
      profile: EMPTY_COMPANION_USER_PROFILE,
      preferences: EMPTY_COMPANION_PREFERENCES,
    });
    expect(fixture.restart().persistence.getProfile().nickname).toBe("");
  });

  test("checks a failed Preference write and a failed Profile rollback without claiming success", () => {
    const fixture = createFixture();
    expect(fixture.persistence.persistPreferences(renamedPreferences("阿星"))).toBe(true);
    // Delete: Profile clear succeeds, Preference delete fails, Profile restore fails.
    fixture.failPreferenceWriteCall(2);
    fixture.failProfileWriteCall(3);

    const result = fixture.persistence.persistPreferences(deleteRecentPreference(renamedPreferences("阿星")));
    expect(result).toBe(false);
    expect(fixture.commits).toHaveLength(1);
    // The old Preference remains the authoritative restart fact even though
    // the compatibility mirror recovery was rejected.
    expect(fixture.restart().persistence.getProfile().nickname).toBe("阿星");
    expect(fixture.persistence.getProfile().nickname).toBe("阿星");
  });

  test("a failed recovery write keeps the old effective nickname and emits no commit", () => {
    const fixture = createFixture(
      { ...EMPTY_COMPANION_USER_PROFILE, nickname: "旧昵称" },
      renamedPreferences("旧昵称"),
    );
    // The first Profile write is the first write of this transaction. Its
    // failure prevents Preference deletion, so restart must retain the old
    // authoritative value.
    fixture.failProfileWriteCall(1);

    expect(fixture.persistence.persistPreferences(EMPTY_COMPANION_PREFERENCES)).toBe(false);
    expect(fixture.commits).toHaveLength(0);
    expect(fixture.restart().persistence.getProfile().nickname).toBe("旧昵称");
  });

  test("migrates a legacy Profile nickname into the sole Preference authority", () => {
    const legacyProfile = { ...EMPTY_COMPANION_USER_PROFILE, nickname: "旧昵称" };
    const migration = migrateLegacyCompanionUserProfileNickname(
      legacyProfile,
      EMPTY_COMPANION_PREFERENCES,
    );

    expect(migration.migrated).toBe(true);
    expect(migration.preferences).toEqual(renamedPreferences("旧昵称"));
    expect(migration.profile.nickname).toBe("旧昵称");
    expect(resolveCompanionUserProfileFromPreferences(
      legacyProfile,
      migration.preferences,
    ).nickname).toBe("旧昵称");
  });

  test("Preference wins conflicts and an absent Preference never resurrects an old mirror", () => {
    const storedProfile = { ...EMPTY_COMPANION_USER_PROFILE, nickname: "Profile旧昵称" };
    expect(resolveCompanionUserProfileFromPreferences(
      storedProfile,
      renamedPreferences("Preference新昵称"),
    ).nickname).toBe("Preference新昵称");
    expect(resolveCompanionUserProfileFromPreferences(
      storedProfile,
      EMPTY_COMPANION_PREFERENCES,
    ).nickname).toBe("");
  });

  test("failed Profile/Preference save cannot become a success after a full restart", () => {
    const raw = createRawStorage();
    const store = createCompanionUserProfilePreferenceStore(raw.storage);
    let preferenceWriteCalls = 0;
    store.writePreferences = (next) => {
      preferenceWriteCalls += 1;
      if (preferenceWriteCalls === 1) throw new Error("preference write failed");
      return writeCompanionPreferences(next, raw.storage, () => {});
    };
    store.clearProfile = () => false;
    let profileWriteCalls = 0;
    let committed = 0;
    const persistence = createCompanionUserProfilePreferencePersistenceForTest({
      ...store,
      initialProfile: readCompanionUserProfile(raw.storage, () => {}),
      initialPreferences: readCompanionPreferences(raw.storage, () => {}),
      writeProfile: (next) => {
        profileWriteCalls += 1;
        return writeCompanionUserProfile(next, raw.storage, () => {});
      },
      onCommitted: () => {
        committed += 1;
      },
    });
    const nextProfile = {
      ...EMPTY_COMPANION_USER_PROFILE,
      nickname: "本应失败",
      email: "failed@example.com",
      phone: "13800000000",
    };

    expect(persistence.persistProfile(nextProfile, renamedPreferences("本应失败"))).toBe(false);
    expect(committed).toBe(0);
    expect(persistence.getProfile()).toEqual(EMPTY_COMPANION_USER_PROFILE);
    expect(persistence.getPreferences()).toEqual(EMPTY_COMPANION_PREFERENCES);

    // The failed two-key attempt leaves a raw Profile residue because its
    // injected recovery write failed. The next startup must not infer success
    // from that residue or run the legacy migration over it.
    expect(raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY)).not.toContain("本应失败");
    expect(raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY)).toContain("failed@example.com");
    expect(raw.raw(COMPANION_PREFERENCES_STORAGE_KEY)).toBeNull();

    const restartedStorage = createRawStorage({
      [COMPANION_USER_PROFILE_STORAGE_KEY]: raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY) ?? "",
      [COMPANION_PREFERENCES_STORAGE_KEY]: raw.raw(COMPANION_PREFERENCES_STORAGE_KEY) ?? "",
      ["yuxin-companion-user-profile-recovery-v1"]: raw.raw("yuxin-companion-user-profile-recovery-v1") ?? "",
    });
    const restarted = readCurrentAppStartup(restartedStorage.storage);
    expect(restarted.profile).toEqual(EMPTY_COMPANION_USER_PROFILE);
    expect(restarted.preferences).toEqual(EMPTY_COMPANION_PREFERENCES);
    expect(restarted.profile.nickname).toBe("");
    expect(restarted.profile.email).toBe("");
    expect(restarted.profile.phone).toBe("");
  });

  test("a Profile snapshot read failure performs zero writes and preserves the old Profile", () => {
    const oldProfile = {
      ...EMPTY_COMPANION_USER_PROFILE,
      gender: "female" as const,
      email: "old@example.com",
      phone: "13800138000",
    };
    const oldPreferences = preferencesWithNicknameAndReplyStyle("旧昵称", "short-and-soft");
    const fixture = createDurableProfileFixture(oldProfile, oldPreferences);
    const oldMemoryProfile = fixture.persistence.getProfile();
    const oldMemoryPreferences = fixture.persistence.getPreferences();
    const oldProfileRaw = fixture.raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY);
    const oldPreferencesRaw = fixture.raw.raw(COMPANION_PREFERENCES_STORAGE_KEY);

    fixture.failNextProfileSnapshotRead();
    fixture.failPreferences.add(1);

    const result = fixture.persistence.persistProfile(
      { ...oldMemoryProfile, email: "new@example.com" },
      preferencesWithNicknameAndReplyStyle("新昵称", "long-and-warm"),
    );

    expect(fixture.getReadFaults().profile).toBe(true);
    expect(result).toBe(false);
    expect(fixture.getCommits()).toBe(0);
    expect(fixture.persistence.getProfile()).toEqual(oldMemoryProfile);
    expect(fixture.persistence.getPreferences()).toEqual(oldMemoryPreferences);

    expect(fixture.raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY)).toBe(oldProfileRaw);
    expect(fixture.raw.raw(COMPANION_PREFERENCES_STORAGE_KEY)).toBe(oldPreferencesRaw);
    expect(fixture.raw.raw(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY)).toBeNull();
    expect(fixture.raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).toBeNull();

    const businessKeys = new Set([
      COMPANION_USER_PROFILE_STORAGE_KEY,
      COMPANION_PREFERENCES_STORAGE_KEY,
    ]);
    expect(fixture.raw.storage.setItem.mock.calls.filter(([key]) => businessKeys.has(key))).toHaveLength(0);
    expect(fixture.raw.storage.removeItem.mock.calls.filter(([key]) => businessKeys.has(key))).toHaveLength(0);
    expect(fixture.raw.storage.setItem.mock.calls.filter(([key]) =>
      key === COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
    )).toHaveLength(0);
    expect(fixture.raw.storage.removeItem.mock.calls.filter(([key]) =>
      key === COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
    )).toHaveLength(0);

    const restarted = fixture.restart();
    expect(restarted.state.profile).toEqual(oldMemoryProfile);
    expect(restarted.state.preferences).toEqual(oldMemoryPreferences);
    expect(restarted.state.migrated).toBe(false);
    expect(restarted.state.migrationAttempted).toBe(false);
    expect(restarted.state.migrationFailed).toBe(false);
    expect(restarted.state.recovery).toBe("none");
  });

  test("a Preferences snapshot read failure performs zero writes and preserves the old Preferences", () => {
    const oldProfile = {
      ...EMPTY_COMPANION_USER_PROFILE,
      gender: "female" as const,
      email: "old@example.com",
      phone: "13800138000",
    };
    const oldPreferences = preferencesWithNicknameAndReplyStyle("旧昵称", "short-and-soft");
    const fixture = createDurableProfileFixture(oldProfile, oldPreferences);
    const oldMemoryProfile = fixture.persistence.getProfile();
    const oldMemoryPreferences = fixture.persistence.getPreferences();
    const oldProfileRaw = fixture.raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY);
    const oldPreferencesRaw = fixture.raw.raw(COMPANION_PREFERENCES_STORAGE_KEY);

    fixture.failNextPreferencesSnapshotRead();
    fixture.failProfile.add(1);

    const result = fixture.persistence.persistProfile(
      { ...oldMemoryProfile, email: "new@example.com" },
      preferencesWithNicknameAndReplyStyle("新昵称", "long-and-warm"),
    );

    expect(fixture.getReadFaults().preferences).toBe(true);
    expect(result).toBe(false);
    expect(fixture.getCommits()).toBe(0);
    expect(fixture.persistence.getProfile()).toEqual(oldMemoryProfile);
    expect(fixture.persistence.getPreferences()).toEqual(oldMemoryPreferences);

    expect(fixture.raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY)).toBe(oldProfileRaw);
    expect(fixture.raw.raw(COMPANION_PREFERENCES_STORAGE_KEY)).toBe(oldPreferencesRaw);
    expect(fixture.raw.raw(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY)).toBeNull();
    expect(fixture.raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).toBeNull();

    const businessKeys = new Set([
      COMPANION_USER_PROFILE_STORAGE_KEY,
      COMPANION_PREFERENCES_STORAGE_KEY,
    ]);
    expect(fixture.raw.storage.setItem.mock.calls.filter(([key]) => businessKeys.has(key))).toHaveLength(0);
    expect(fixture.raw.storage.removeItem.mock.calls.filter(([key]) => businessKeys.has(key))).toHaveLength(0);
    expect(fixture.raw.storage.setItem.mock.calls.filter(([key]) =>
      key === COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
    )).toHaveLength(0);
    expect(fixture.raw.storage.removeItem.mock.calls.filter(([key]) =>
      key === COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
    )).toHaveLength(0);

    const restarted = fixture.restart();
    expect(restarted.state.profile).toEqual(oldMemoryProfile);
    expect(restarted.state.preferences).toEqual(oldMemoryPreferences);
    expect(restarted.state.migrated).toBe(false);
    expect(restarted.state.migrationAttempted).toBe(false);
    expect(restarted.state.migrationFailed).toBe(false);
    expect(restarted.state.recovery).toBe("none");
  });

  test("raw Profile and Preferences reads fail closed through the App storage adapter", () => {
    const scenarios = [
      {
        key: COMPANION_USER_PROFILE_STORAGE_KEY,
        failForward: (fixture: ReturnType<typeof createDurableProfileFixture>) => {
          fixture.failPreferences.add(1);
        },
      },
      {
        key: COMPANION_PREFERENCES_STORAGE_KEY,
        failForward: (fixture: ReturnType<typeof createDurableProfileFixture>) => {
          fixture.failProfile.add(1);
        },
      },
    ];

    for (const scenario of scenarios) {
      const oldProfile = {
        ...EMPTY_COMPANION_USER_PROFILE,
        gender: "female" as const,
        email: "old@example.com",
        phone: "13800138000",
      };
      const oldPreferences = preferencesWithNicknameAndReplyStyle("旧昵称", "short-and-soft");
      const fixture = createDurableProfileFixture(oldProfile, oldPreferences);
      const oldMemoryProfile = fixture.persistence.getProfile();
      const oldMemoryPreferences = fixture.persistence.getPreferences();
      const oldProfileRaw = fixture.raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY);
      const oldPreferencesRaw = fixture.raw.raw(COMPANION_PREFERENCES_STORAGE_KEY);
      fixture.raw.failNextRead(scenario.key);
      scenario.failForward(fixture);

      expect(fixture.persistence.persistProfile(
        { ...oldMemoryProfile, email: "new@example.com" },
        preferencesWithNicknameAndReplyStyle("新昵称", "long-and-warm"),
      )).toBe(false);
      expect(fixture.getCommits()).toBe(0);
      expect(fixture.persistence.getProfile()).toEqual(oldMemoryProfile);
      expect(fixture.persistence.getPreferences()).toEqual(oldMemoryPreferences);
      expect(fixture.raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY)).toBe(oldProfileRaw);
      expect(fixture.raw.raw(COMPANION_PREFERENCES_STORAGE_KEY)).toBe(oldPreferencesRaw);
      expect(fixture.raw.raw(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY)).toBeNull();
      expect(fixture.raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).toBeNull();
      expectNoDurableTransactionWrites(fixture);

      const restarted = fixture.restart();
      expect(restarted.state.profile).toEqual(oldMemoryProfile);
      expect(restarted.state.preferences).toEqual(oldMemoryPreferences);
      expect(restarted.state.recovery).toBe("none");
      expect(restarted.state.migrationAttempted).toBe(false);
    }
  });

  test("migration marker and recovery presence read errors block a new transaction", () => {
    const scenarios = [
      COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY,
      COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
    ];
    for (const key of scenarios) {
      const oldProfile = {
        ...EMPTY_COMPANION_USER_PROFILE,
        gender: "female" as const,
        email: "old@example.com",
        phone: "13800138000",
      };
      const oldPreferences = preferencesWithNicknameAndReplyStyle("旧昵称", "short-and-soft");
      const fixture = createDurableProfileFixture(oldProfile, oldPreferences);
      const oldMemoryProfile = fixture.persistence.getProfile();
      const oldMemoryPreferences = fixture.persistence.getPreferences();
      const oldProfileRaw = fixture.raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY);
      const oldPreferencesRaw = fixture.raw.raw(COMPANION_PREFERENCES_STORAGE_KEY);
      fixture.raw.failNextRead(key);

      expect(fixture.persistence.persistProfile(
        { ...oldMemoryProfile, email: "new@example.com" },
        preferencesWithNicknameAndReplyStyle("新昵称", "long-and-warm"),
      )).toBe(false);
      expect(fixture.getCommits()).toBe(0);
      expect(fixture.persistence.getProfile()).toEqual(oldMemoryProfile);
      expect(fixture.persistence.getPreferences()).toEqual(oldMemoryPreferences);
      expect(fixture.raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY)).toBe(oldProfileRaw);
      expect(fixture.raw.raw(COMPANION_PREFERENCES_STORAGE_KEY)).toBe(oldPreferencesRaw);
      expect(fixture.raw.raw(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY)).toBeNull();
      expect(fixture.raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).toBeNull();
      expectNoDurableTransactionWrites(fixture);

      const restarted = fixture.restart();
      expect(restarted.state.profile).toEqual(oldMemoryProfile);
      expect(restarted.state.preferences).toEqual(oldMemoryPreferences);
      expect(restarted.state.recovery).toBe("none");
      expect(restarted.state.migrationAttempted).toBe(false);
    }
  });

  test("legacy migration stays inactive when marker or recovery presence is unreadable", () => {
    for (const key of [
      COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY,
      COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
    ]) {
      const legacyProfile = {
        ...EMPTY_COMPANION_USER_PROFILE,
        nickname: "旧版昵称",
      };
      const raw = createRawStorage({
        [COMPANION_USER_PROFILE_STORAGE_KEY]: JSON.stringify(legacyProfile),
      });
      raw.failNextRead(key);

      const state = readCurrentAppStartup(raw.storage);
      expect(state.migrated).toBe(false);
      expect(state.migrationAttempted).toBe(false);
      expect(state.migrationFailed).toBe(false);
      expect(state.recovery).toBe("blocked");
      expect(raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY)).toBe(JSON.stringify(legacyProfile));
      expect(raw.raw(COMPANION_PREFERENCES_STORAGE_KEY)).toBeNull();
      expect(raw.raw(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY)).toBeNull();
      expect(raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).toBeNull();
      expect(raw.storage.setItem).not.toHaveBeenCalled();
      expect(raw.storage.removeItem).not.toHaveBeenCalled();
    }
  });

  test("present malformed Profile or Preferences fail closed instead of becoming empty state", () => {
    const oldProfile = {
      ...EMPTY_COMPANION_USER_PROFILE,
      gender: "female" as const,
      email: "old@example.com",
      phone: "13800138000",
    };
    const oldPreferences = preferencesWithNicknameAndReplyStyle("旧昵称", "short-and-soft");
    const scenarios = [
      {
        key: COMPANION_USER_PROFILE_STORAGE_KEY,
        malformed: JSON.stringify({ ...oldProfile, email: 42 }),
      },
      {
        key: COMPANION_PREFERENCES_STORAGE_KEY,
        malformed: JSON.stringify({ preferences: [{ id: 42 }], recentPreferenceId: null }),
      },
    ];

    for (const scenario of scenarios) {
      const raw = createRawStorage({
        [COMPANION_USER_PROFILE_STORAGE_KEY]: scenario.key === COMPANION_USER_PROFILE_STORAGE_KEY
          ? scenario.malformed
          : JSON.stringify(oldProfile),
        [COMPANION_PREFERENCES_STORAGE_KEY]: scenario.key === COMPANION_PREFERENCES_STORAGE_KEY
          ? scenario.malformed
          : JSON.stringify(oldPreferences),
      });
      const store = createCompanionUserProfilePreferenceStore(raw.storage);
      let commits = 0;
      const persistence = createCompanionUserProfilePreferencePersistenceForTest({
        ...store,
        initialProfile: oldProfile,
        initialPreferences: oldPreferences,
        onCommitted: () => { commits += 1; },
      });
      const oldMemoryProfile = persistence.getProfile();
      const oldMemoryPreferences = persistence.getPreferences();
      const profileRaw = raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY);
      const preferencesRaw = raw.raw(COMPANION_PREFERENCES_STORAGE_KEY);

      expect(persistence.persistProfile(
        { ...oldProfile, email: "new@example.com" },
        preferencesWithNicknameAndReplyStyle("新昵称", "long-and-warm"),
      )).toBe(false);
      expect(commits).toBe(0);
      expect(persistence.getProfile()).toEqual(oldMemoryProfile);
      expect(persistence.getPreferences()).toEqual(oldMemoryPreferences);
      expect(raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY)).toBe(profileRaw);
      expect(raw.raw(COMPANION_PREFERENCES_STORAGE_KEY)).toBe(preferencesRaw);
      expect(raw.raw(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY)).toBeNull();
      expect(raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).toBeNull();
      expect(raw.storage.setItem).not.toHaveBeenCalled();
      expect(raw.storage.removeItem).not.toHaveBeenCalled();

      const restarted = readCurrentAppStartup(raw.storage);
      expect(restarted.migrated).toBe(false);
      expect(restarted.migrationAttempted).toBe(false);
      expect(restarted.recovery).toBe("blocked");
    }
  });

  test("prepared recovery readback failure keeps evidence and touches no business key", () => {
    const oldProfile = {
      ...EMPTY_COMPANION_USER_PROFILE,
      gender: "female" as const,
      email: "old@example.com",
      phone: "13800138000",
    };
    const oldPreferences = preferencesWithNicknameAndReplyStyle("旧昵称", "short-and-soft");
    const fixture = createDurableProfileFixture(oldProfile, oldPreferences);
    const oldMemoryProfile = fixture.persistence.getProfile();
    const oldMemoryPreferences = fixture.persistence.getPreferences();
    const oldProfileRaw = fixture.raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY);
    const oldPreferencesRaw = fixture.raw.raw(COMPANION_PREFERENCES_STORAGE_KEY);
    fixture.failRecoveryReadback();

    expect(fixture.persistence.persistProfile(
      { ...oldMemoryProfile, email: "new@example.com" },
      preferencesWithNicknameAndReplyStyle("新昵称", "long-and-warm"),
    )).toBe(false);
    expect(fixture.getCommits()).toBe(0);
    expect(fixture.persistence.getProfile()).toEqual(oldMemoryProfile);
    expect(fixture.persistence.getPreferences()).toEqual(oldMemoryPreferences);
    expect(fixture.raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY)).toBe(oldProfileRaw);
    expect(fixture.raw.raw(COMPANION_PREFERENCES_STORAGE_KEY)).toBe(oldPreferencesRaw);
    expect(fixture.raw.raw(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY)).toBeNull();
    expect(fixture.raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).not.toBeNull();
    expect(JSON.parse(fixture.raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY) ?? "null").state)
      .toBe("prepared");
    expect(fixture.raw.storage.setItem.mock.calls.filter(([key]) =>
      key === COMPANION_USER_PROFILE_STORAGE_KEY || key === COMPANION_PREFERENCES_STORAGE_KEY,
    )).toHaveLength(0);
    expect(fixture.raw.storage.removeItem.mock.calls.filter(([key]) =>
      key === COMPANION_USER_PROFILE_STORAGE_KEY || key === COMPANION_PREFERENCES_STORAGE_KEY,
    )).toHaveLength(0);

    const restarted = fixture.restart();
    expect(restarted.state.profile).toEqual(oldMemoryProfile);
    expect(restarted.state.preferences).toEqual(oldMemoryPreferences);
    expect(restarted.state.recovery).toBe("recovered");
    expect(restarted.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).toBeNull();
  });

  test("rollback readback failure keeps the prepared recovery record for restart", () => {
    const oldProfile = {
      ...EMPTY_COMPANION_USER_PROFILE,
      gender: "female" as const,
      email: "old@example.com",
      phone: "13800138000",
    };
    const oldPreferences = preferencesWithNicknameAndReplyStyle("旧昵称", "short-and-soft");
    const fixture = createDurableProfileFixture(oldProfile, oldPreferences);
    const oldMemoryProfile = fixture.persistence.getProfile();
    const oldMemoryPreferences = fixture.persistence.getPreferences();
    fixture.failPreferences.add(1);
    fixture.failProfileRestoreReadback();

    expect(fixture.persistence.persistProfile(
      { ...oldMemoryProfile, email: "new@example.com" },
      preferencesWithNicknameAndReplyStyle("新昵称", "long-and-warm"),
    )).toBe(false);
    expect(fixture.getCommits()).toBe(0);
    expect(fixture.persistence.getProfile()).toEqual(oldMemoryProfile);
    expect(fixture.persistence.getPreferences()).toEqual(oldMemoryPreferences);
    expect(fixture.raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).not.toBeNull();
    expect(JSON.parse(fixture.raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY) ?? "null").state)
      .toBe("prepared");

    const restarted = fixture.restart();
    expect(restarted.state.profile).toEqual(oldMemoryProfile);
    expect(restarted.state.preferences).toEqual(oldMemoryPreferences);
    expect(restarted.state.recovery).toBe("recovered");
    expect(restarted.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).toBeNull();
  });

  test("an existing Preference without global.nickname does not revive a deleted Profile nickname", () => {
    const storedProfile = { ...EMPTY_COMPANION_USER_PROFILE, nickname: "已删除但残留" };
    const storedPreferences = upsertCompanionPreference(EMPTY_COMPANION_PREFERENCES, {
      id: "global.replyStyle",
      scope: "global",
      category: "userProfile",
      key: "replyStyle",
      value: "short-and-soft",
      source: "explicit",
    });
    const raw = createRawStorage({
      [COMPANION_USER_PROFILE_STORAGE_KEY]: JSON.stringify(storedProfile),
      [COMPANION_PREFERENCES_STORAGE_KEY]: JSON.stringify(storedPreferences),
    });
    const writesBeforeStartup = raw.storage.setItem.mock.calls.length;

    const firstStart = readCurrentAppStartup(raw.storage);
    expect(firstStart.profile.nickname).toBe("");
    expect(firstStart.preferences).toEqual(storedPreferences);
    expect(raw.raw(COMPANION_PREFERENCES_STORAGE_KEY)).not.toContain("global.nickname");
    expect(raw.storage.setItem.mock.calls.length).toBe(writesBeforeStartup);

    const secondStart = readCurrentAppStartup(raw.storage);
    expect(secondStart.profile.nickname).toBe("");
    expect(secondStart.preferences).toEqual(storedPreferences);
    expect(raw.raw(COMPANION_PREFERENCES_STORAGE_KEY)).not.toContain("global.nickname");
    expect(raw.storage.setItem.mock.calls.length).toBe(writesBeforeStartup);
  });

  test("fails closed when the prepared recovery record cannot be read back", () => {
    const fixture = createDurableProfileFixture(
      { ...EMPTY_COMPANION_USER_PROFILE, email: "old@example.com" },
      renamedPreferences("旧昵称"),
    );
    fixture.failRecovery.add(1);

    expect(fixture.persistence.persistProfile({
      ...fixture.persistence.getProfile(),
      email: "new@example.com",
    }, renamedPreferences("新昵称"))).toBe(false);
    expect(fixture.getCommits()).toBe(0);
    expect(JSON.parse(fixture.raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY) ?? "null")).toEqual({
      ...EMPTY_COMPANION_USER_PROFILE,
      email: "old@example.com",
    });
    expect(JSON.parse(fixture.raw.raw(COMPANION_PREFERENCES_STORAGE_KEY) ?? "null")).toEqual(
      renamedPreferences("旧昵称"),
    );
  });

  test("a first Profile write failure leaves both business keys and memory unchanged", () => {
    const fixture = createDurableProfileFixture(
      { ...EMPTY_COMPANION_USER_PROFILE, email: "old@example.com" },
      renamedPreferences("旧昵称"),
    );
    fixture.failProfile.add(1);

    expect(fixture.persistence.persistProfile({
      ...fixture.persistence.getProfile(),
      email: "new@example.com",
    }, renamedPreferences("新昵称"))).toBe(false);
    expect(fixture.getCommits()).toBe(0);
    expect(fixture.persistence.getProfile().email).toBe("old@example.com");
    expect(fixture.restart().state.profile.email).toBe("old@example.com");
    expect(fixture.restart().state.profile.nickname).toBe("旧昵称");
  });

  test("a first Preference write failure restores the Profile mirror", () => {
    const fixture = createDurableProfileFixture(
      { ...EMPTY_COMPANION_USER_PROFILE, email: "old@example.com" },
      renamedPreferences("旧昵称"),
    );
    fixture.failPreferences.add(1);

    expect(fixture.persistence.persistProfile({
      ...fixture.persistence.getProfile(),
      email: "new@example.com",
    }, renamedPreferences("新昵称"))).toBe(false);
    expect(fixture.getCommits()).toBe(0);
    expect(fixture.restart().state.profile).toEqual({
      ...EMPTY_COMPANION_USER_PROFILE,
      nickname: "旧昵称",
      email: "old@example.com",
    });
  });

  test("Profile success plus Preference failure with failed Profile recovery keeps a prepared record", () => {
    const fixture = createDurableProfileFixture(
      { ...EMPTY_COMPANION_USER_PROFILE, email: "old@example.com" },
      renamedPreferences("旧昵称"),
    );
    fixture.failPreferences.add(1);
    fixture.failProfile.add(2);

    expect(fixture.persistence.persistProfile({
      ...fixture.persistence.getProfile(),
      email: "new@example.com",
    }, renamedPreferences("新昵称"))).toBe(false);
    expect(fixture.getCommits()).toBe(0);
    expect(fixture.raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).not.toBeNull();
    const restarted = fixture.restart();
    expect(restarted.state.profile).toEqual({
      ...EMPTY_COMPANION_USER_PROFILE,
      nickname: "旧昵称",
      email: "old@example.com",
    });
    expect(restarted.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).toBeNull();
    expect(restarted.raw(COMPANION_USER_PROFILE_STORAGE_KEY)).toContain("old@example.com");
    expect(restarted.raw(COMPANION_USER_PROFILE_STORAGE_KEY)).not.toContain("new@example.com");
  });

  test("business keys written but committed marker write failure restores the old snapshot", () => {
    const fixture = createDurableProfileFixture(
      { ...EMPTY_COMPANION_USER_PROFILE, email: "old@example.com" },
      renamedPreferences("旧昵称"),
    );
    fixture.failRecovery.add(2);

    expect(fixture.persistence.persistProfile({
      ...fixture.persistence.getProfile(),
      email: "new@example.com",
    }, renamedPreferences("新昵称"))).toBe(false);
    expect(fixture.getCommits()).toBe(0);
    expect(fixture.restart().state.profile.email).toBe("old@example.com");
    expect(fixture.restart().state.profile.nickname).toBe("旧昵称");
  });

  test("marker write failure does not report a profile save", () => {
    const fixture = createDurableProfileFixture(
      { ...EMPTY_COMPANION_USER_PROFILE, email: "old@example.com" },
      renamedPreferences("旧昵称"),
    );
    fixture.failMarker.add(1);

    expect(fixture.persistence.persistProfile({
      ...fixture.persistence.getProfile(),
      email: "new@example.com",
    }, renamedPreferences("新昵称"))).toBe(false);
    expect(fixture.getCommits()).toBe(0);
    expect(fixture.restart().state.profile.email).toBe("old@example.com");
    expect(fixture.restart().state.profile.nickname).toBe("旧昵称");
  });

  test("committed state survives transaction-record cleanup failure and is adopted once after restart", () => {
    const fixture = createDurableProfileFixture(
      { ...EMPTY_COMPANION_USER_PROFILE, email: "old@example.com" },
      renamedPreferences("旧昵称"),
    );
    fixture.setFailRecoveryCleanup(true);

    expect(fixture.persistence.persistProfile({
      ...fixture.persistence.getProfile(),
      nickname: "新昵称",
      email: "new@example.com",
    }, renamedPreferences("新昵称"))).toBe(true);
    expect(fixture.getCommits()).toBe(1);
    expect(JSON.parse(fixture.raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY) ?? "null").state)
      .toBe("committed");
    expect(fixture.persistence.getProfile()).toEqual({
      ...EMPTY_COMPANION_USER_PROFILE,
      nickname: "新昵称",
      email: "new@example.com",
    });

    const restarted = fixture.restart();
    expect(restarted.state.profile).toEqual(fixture.persistence.getProfile());
    expect(restarted.state.migrated).toBe(false);
    expect(restarted.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).toBeNull();
    expect(restarted.state.preferences).toEqual(renamedPreferences("新昵称"));
  });

  test("a failed recovery remains blocking when another write starts before restart", () => {
    const fixture = createDurableProfileFixture(
      { ...EMPTY_COMPANION_USER_PROFILE, email: "old@example.com" },
      renamedPreferences("旧昵称"),
    );
    fixture.failPreferences.add(1);
    fixture.failProfile.add(2);
    expect(fixture.persistence.persistProfile({
      ...fixture.persistence.getProfile(),
      email: "new@example.com",
    }, renamedPreferences("新昵称"))).toBe(false);

    // The next call first attempts to repair the prepared transaction. Its
    // recovery Profile write is deliberately failed too, so no new save may
    // overwrite the unresolved record.
    fixture.failProfile.add(3);
    expect(fixture.persistence.persistProfile({
      ...fixture.persistence.getProfile(),
      email: "third@example.com",
    }, renamedPreferences("第三次"))).toBe(false);
    expect(fixture.getCommits()).toBe(0);
    expect(fixture.raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).not.toBeNull();
    expect(fixture.persistence.getProfile().email).toBe("old@example.com");
  });

  test("legacy Profile-only data migrates exactly once when the Preference key is absent", () => {
    const raw = createRawStorage({
      [COMPANION_USER_PROFILE_STORAGE_KEY]: JSON.stringify({
        ...EMPTY_COMPANION_USER_PROFILE,
        nickname: "旧版昵称",
      }),
    });
    const first = readCurrentAppStartup(raw.storage);
    expect(first.migrated).toBe(true);
    expect(first.profile.nickname).toBe("旧版昵称");
    expect(JSON.parse(raw.raw(COMPANION_PREFERENCES_STORAGE_KEY) ?? "null")).toEqual(
      renamedPreferences("旧版昵称"),
    );
    expect(JSON.parse(raw.raw(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY) ?? "null")).toEqual({
      schemaVersion: 1,
      state: "preference-authoritative",
    });
    expect(JSON.parse(raw.raw(COMPANION_USER_PROFILE_STORAGE_KEY) ?? "null").nickname).toBe("");

    const second = readCurrentAppStartup(raw.storage);
    expect(second.migrated).toBe(false);
    expect(second.profile.nickname).toBe("旧版昵称");
  });

  test("legacy Preference write failure leaves the nickname inactive", () => {
    const raw = createRawStorage({
      [COMPANION_USER_PROFILE_STORAGE_KEY]: JSON.stringify({
        ...EMPTY_COMPANION_USER_PROFILE,
        nickname: "迁移失败昵称",
      }),
    });
    const store = createCompanionUserProfilePreferenceStore(raw.storage);
    store.writePreferences = () => false;

    const state = initializeCompanionUserProfileState(store);
    expect(state.status).toBe("blocked");
    expect(state.status === "blocked" && state.reason).toBe("write-failed");
    expect(raw.raw(COMPANION_PREFERENCES_STORAGE_KEY)).toBeNull();
    expect(raw.raw(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY)).toBeNull();
  });

  test("legacy migration marker failure leaves both nickname and Preference inactive", () => {
    const raw = createRawStorage({
      [COMPANION_USER_PROFILE_STORAGE_KEY]: JSON.stringify({
        ...EMPTY_COMPANION_USER_PROFILE,
        nickname: "marker失败昵称",
      }),
    });
    const store = createCompanionUserProfilePreferenceStore(raw.storage);
    store.writeMigrationMarker = () => false;

    const state = initializeCompanionUserProfileState(store);
    expect(state.status).toBe("blocked");
    expect(state.status === "blocked" && state.reason).toBe("write-failed");
    expect(raw.raw(COMPANION_PREFERENCES_STORAGE_KEY)).toBeNull();
    expect(raw.raw(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY)).toBeNull();
  });

  test("forget after migration leaves authority evidence and cannot revive the old nickname", () => {
    const raw = createRawStorage({
      [COMPANION_USER_PROFILE_STORAGE_KEY]: JSON.stringify({
        ...EMPTY_COMPANION_USER_PROFILE,
        nickname: "待删除昵称",
      }),
    });
    const store = createCompanionUserProfilePreferenceStore(raw.storage);
    const migrated = legacyTestStartupState(initializeCompanionUserProfileState(store));
    const persistence = createCompanionUserProfilePreferencePersistenceForTest({
      ...store,
      initialProfile: migrated.profile,
      initialPreferences: migrated.preferences,
    });
    expect(persistence.persistPreferences(EMPTY_COMPANION_PREFERENCES)).toBe(true);

    const restarted = readCurrentAppStartup(raw.storage);
    expect(restarted.profile.nickname).toBe("");
    expect(restarted.preferences).toEqual(EMPTY_COMPANION_PREFERENCES);
    expect(restarted.migrated).toBe(false);
    expect(raw.raw(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY)).not.toBeNull();
    expect(readCurrentAppStartup(raw.storage).profile.nickname).toBe("");
  });

  test("a prepared transaction is recovered before a legacy Profile-only migration gate", () => {
    const raw = createRawStorage({
      [COMPANION_USER_PROFILE_STORAGE_KEY]: JSON.stringify({
        ...EMPTY_COMPANION_USER_PROFILE,
        nickname: "legacy-and-transaction",
      }),
    });
    const store = createCompanionUserProfilePreferenceStore(raw.storage);
    let profileWrites = 0;
    const writeProfile = store.writeProfile;
    store.writeProfile = (next) => {
      profileWrites += 1;
      // Migration forward write succeeds; restoring after the Preference
      // failure fails, leaving a prepared record beside the legacy Profile.
      if (profileWrites === 2) return false;
      return writeProfile(next);
    };
    store.writePreferences = () => false;

    const failed = legacyTestStartupState(initializeCompanionUserProfileState(store));
    expect(failed.migrated).toBe(false);
    expect(failed.profile.nickname).toBe("");
    expect(raw.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).not.toBeNull();

    const fresh = createRawStorage(Object.fromEntries(
      [
        COMPANION_USER_PROFILE_STORAGE_KEY,
        COMPANION_PREFERENCES_STORAGE_KEY,
        COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
        COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY,
      ].flatMap((key) => {
        const value = raw.raw(key);
        return value === null ? [] : [[key, value] as const];
      }),
    ));
    const recovered = readCurrentAppStartup(fresh.storage);
    expect(recovered.migrated).toBe(false);
    expect(recovered.profile.nickname).toBe("");
    expect(recovered.recovery).toBe("recovered");
    expect(fresh.raw(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY)).toBeNull();
  });

});
