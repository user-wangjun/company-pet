import {
  normalizeCompanionUserProfile,
  isCompanionUserProfileSafe,
  type CompanionUserProfile,
} from "./companionUserProfile";
import {
  COMPANION_PREFERENCES_STORAGE_KEY,
  isCompanionPreferencesStateSafe,
  writeCompanionPreferences,
  type CompanionPreference,
  type CompanionPreferencesState,
} from "./companionPreferences";
import {
  COMPANION_USER_PROFILE_STORAGE_KEY,
  writeCompanionUserProfile,
} from "./companionUserProfile";

export const COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY =
  "yuxin-companion-user-profile-recovery-v1";
export const COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY =
  "yuxin-companion-user-profile-migration-v1";
export const COMPANION_USER_PROFILE_MIGRATION_SCHEMA_VERSION = 1 as const;

export type CompanionUserProfileSyncStorage =
  Pick<Storage, "getItem" | "setItem">
  & Partial<Pick<Storage, "removeItem">>;

export type CompanionUserProfileStorageRead<T> =
  | { status: "missing"; value: T }
  | { status: "present-valid"; value: T }
  | { status: "read-error" | "invalid" };

export type CompanionUserProfileSettingsUnavailableReason =
  | "read-failed"
  | "invalid-storage"
  | "recovery-blocked"
  | "write-failed";

export type CompanionUserProfileMigrationMarker = {
  schemaVersion: typeof COMPANION_USER_PROFILE_MIGRATION_SCHEMA_VERSION;
  state: "preference-authoritative";
};

export type CompanionUserProfileRecoveryRecord = {
  schemaVersion: 1;
  transactionId: string;
  operation: "persist" | "legacy-migration";
  previousProfile: CompanionUserProfile;
  previousPreferences: CompanionPreferencesState;
  nextProfile: CompanionUserProfile;
  nextPreferences: CompanionPreferencesState;
  previousProfileStored: boolean;
  previousPreferencesStored: boolean;
  previousMigrationMarker: CompanionUserProfileMigrationMarker | null;
  nextMigrationMarker: CompanionUserProfileMigrationMarker;
  state: "prepared" | "committed";
};

export type CompanionUserProfilePreferenceStore = {
  writeProfile(profile: CompanionUserProfile): boolean;
  writePreferences(state: CompanionPreferencesState): boolean;
  /** Read-back is required: two-key recovery is not verifiable without it. */
  readProfile: () => CompanionUserProfile;
  readPreferences: () => CompanionPreferencesState;
  /** A single raw read determines presence, value and validity. */
  readProfileSnapshot?: () => CompanionUserProfileStorageRead<CompanionUserProfile>;
  readPreferencesSnapshot?: () => CompanionUserProfileStorageRead<CompanionPreferencesState>;
  profileStoragePresent?: () => boolean;
  preferencesStoragePresent?: () => boolean;
  clearProfile?: () => boolean;
  clearPreferences?: () => boolean;
  readRecoveryRecord?: () => CompanionUserProfileRecoveryRecord | null;
  readRecoverySnapshot?: () => CompanionUserProfileStorageRead<CompanionUserProfileRecoveryRecord | null>;
  recoveryRecordPresent?: () => boolean;
  writeRecoveryRecord?: (record: CompanionUserProfileRecoveryRecord) => boolean;
  clearRecoveryRecord?: () => boolean;
  readMigrationMarker?: () => CompanionUserProfileMigrationMarker | null;
  readMigrationMarkerSnapshot?: () => CompanionUserProfileStorageRead<CompanionUserProfileMigrationMarker | null>;
  migrationMarkerPresent?: () => boolean;
  writeMigrationMarker?: (marker: CompanionUserProfileMigrationMarker) => boolean;
  clearMigrationMarker?: () => boolean;
};

/**
 * Legacy full-state persistence is retained only for the transaction fault
 * matrix. App and Harness must use CompanionUserSettingsRepository commands.
 */
export type CompanionUserProfilePreferencePersistenceForTest = {
  getProfile(): CompanionUserProfile;
  getPreferences(): CompanionPreferencesState;
  persistPreferences(nextPreferences: CompanionPreferencesState): boolean;
  persistProfile(
    profile: CompanionUserProfile,
    preferences: CompanionPreferencesState,
  ): boolean;
};

export type CompanionUserProfileNicknameMigration = {
  profile: CompanionUserProfile;
  preferences: CompanionPreferencesState;
  migrated: boolean;
};

export type CompanionUserProfileStartupState =
  | {
      status: "ready";
      profile: CompanionUserProfile;
      preferences: CompanionPreferencesState;
      migrated: boolean;
      migrationAttempted: boolean;
      migrationFailed: boolean;
      recovery: "none" | "recovered" | "committed";
    }
  | {
      status: "blocked";
      reason: CompanionUserProfileSettingsUnavailableReason;
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

function cloneMarker(
  marker: CompanionUserProfileMigrationMarker | null,
): CompanionUserProfileMigrationMarker | null {
  return marker ? { ...marker } : null;
}

function cloneRecoveryRecord(
  record: CompanionUserProfileRecoveryRecord,
): CompanionUserProfileRecoveryRecord {
  return {
    ...record,
    previousProfile: cloneProfile(record.previousProfile),
    previousPreferences: clonePreferences(record.previousPreferences),
    nextProfile: cloneProfile(record.nextProfile),
    nextPreferences: clonePreferences(record.nextPreferences),
    previousMigrationMarker: cloneMarker(record.previousMigrationMarker),
    nextMigrationMarker: { ...record.nextMigrationMarker },
  };
}

function findNicknamePreference(
  state: CompanionPreferencesState,
): CompanionPreference | undefined {
  return state.preferences.find((preference) =>
    preference.id === "global.nickname"
    && preference.scope === "global"
    && preference.category === "userProfile"
    && preference.key === "nickname"
  );
}

function sameProfile(left: CompanionUserProfile, right: CompanionUserProfile): boolean {
  return left.nickname === right.nickname
    && left.gender === right.gender
    && left.email === right.email
    && left.phone === right.phone;
}

function samePreferences(
  left: CompanionPreferencesState,
  right: CompanionPreferencesState,
): boolean {
  return left.recentPreferenceId === right.recentPreferenceId
    && left.preferences.length === right.preferences.length
    && left.preferences.every((leftPreference, index) => {
      const rightPreference = right.preferences[index];
      return rightPreference !== undefined
        && leftPreference.id === rightPreference.id
        && leftPreference.scope === rightPreference.scope
        && leftPreference.category === rightPreference.category
        && leftPreference.key === rightPreference.key
        && leftPreference.value === rightPreference.value
        && leftPreference.source === rightPreference.source;
    });
}

function sameMarker(
  left: CompanionUserProfileMigrationMarker | null,
  right: CompanionUserProfileMigrationMarker | null,
): boolean {
  return left?.schemaVersion === right?.schemaVersion
    && left?.state === right?.state;
}

function persistedProfile(profile: CompanionUserProfile): CompanionUserProfile {
  return {
    ...normalizeCompanionUserProfile(profile),
    // global.nickname is the only durable nickname fact. The Profile key is
    // deliberately a mirror for the other local fields and never receives a
    // newly entered nickname.
    nickname: "",
  };
}

function profileWithAuthoritativeNickname(
  profile: CompanionUserProfile,
  preferences: CompanionPreferencesState,
): CompanionUserProfile {
  const nicknamePreference = findNicknamePreference(preferences);
  return normalizeCompanionUserProfile({
    ...profile,
    nickname: nicknamePreference?.value ?? "",
  });
}

function marker(): CompanionUserProfileMigrationMarker {
  return {
    schemaVersion: COMPANION_USER_PROFILE_MIGRATION_SCHEMA_VERSION,
    state: "preference-authoritative",
  };
}

function isMarker(value: unknown): value is CompanionUserProfileMigrationMarker {
  return typeof value === "object"
    && value !== null
    && (value as { schemaVersion?: unknown }).schemaVersion === COMPANION_USER_PROFILE_MIGRATION_SCHEMA_VERSION
    && (value as { state?: unknown }).state === "preference-authoritative";
}

function isStoredProfile(value: unknown): value is CompanionUserProfile {
  if (
    typeof value !== "object"
    || value === null
    || typeof (value as { nickname?: unknown }).nickname !== "string"
    || typeof (value as { gender?: unknown }).gender !== "string"
    || typeof (value as { email?: unknown }).email !== "string"
    || typeof (value as { phone?: unknown }).phone !== "string"
  ) return false;
  const normalized = normalizeCompanionUserProfile(value as Partial<CompanionUserProfile>);
  return isCompanionUserProfileSafe(normalized)
    && sameProfile(normalized, value as CompanionUserProfile);
}

function isStoredPreference(value: unknown): value is CompanionPreference {
  if (typeof value !== "object" || value === null) return false;
  const preference = value as Partial<CompanionPreference>;
  return typeof preference.id === "string"
    && typeof preference.scope === "string"
    && (preference.scope === "global" || preference.scope.startsWith("pet:"))
    && typeof preference.category === "string"
    && ["userProfile", "reminderPreferences", "petRelationship"].includes(preference.category)
    && typeof preference.key === "string"
    && typeof preference.value === "string"
    && typeof preference.source === "string"
    && ["explicit", "inferred"].includes(preference.source)
    && isCompanionPreferencesStateSafe({
      preferences: [preference as CompanionPreference],
      recentPreferenceId: null,
    });
}

function isStoredPreferences(value: unknown): value is CompanionPreferencesState {
  return typeof value === "object"
    && value !== null
    && Array.isArray((value as CompanionPreferencesState).preferences)
    && ((value as CompanionPreferencesState).recentPreferenceId === null
      || typeof (value as CompanionPreferencesState).recentPreferenceId === "string")
    && (value as CompanionPreferencesState).preferences.every(isStoredPreference)
    && isCompanionPreferencesStateSafe(value as CompanionPreferencesState)
    && samePreferences(value as CompanionPreferencesState, clonePreferences(value as CompanionPreferencesState));
}

function parseRecoveryRecord(value: string | null): CompanionUserProfileRecoveryRecord | null {
  if (!value) return null;
  try {
    const parsed = JSON.parse(value) as Partial<CompanionUserProfileRecoveryRecord>;
    if (
      !parsed
      || typeof parsed !== "object"
      || parsed.schemaVersion !== 1
      || typeof parsed.transactionId !== "string"
      || !parsed.transactionId
      || (parsed.operation !== "persist" && parsed.operation !== "legacy-migration")
      || (parsed.state !== "prepared" && parsed.state !== "committed")
      || typeof parsed.previousProfileStored !== "boolean"
      || typeof parsed.previousPreferencesStored !== "boolean"
      || !isStoredProfile(parsed.previousProfile)
      || !isStoredProfile(parsed.nextProfile)
      || !isStoredPreferences(parsed.previousPreferences)
      || !isStoredPreferences(parsed.nextPreferences)
      || (parsed.previousMigrationMarker !== null
        && parsed.previousMigrationMarker !== undefined
        && !isMarker(parsed.previousMigrationMarker))
      || !isMarker(parsed.nextMigrationMarker)
    ) return null;

    return cloneRecoveryRecord({
      schemaVersion: 1,
      transactionId: parsed.transactionId,
      operation: parsed.operation,
      previousProfile: normalizeCompanionUserProfile(parsed.previousProfile),
      previousPreferences: clonePreferences(parsed.previousPreferences),
      nextProfile: normalizeCompanionUserProfile(parsed.nextProfile),
      nextPreferences: clonePreferences(parsed.nextPreferences),
      previousProfileStored: parsed.previousProfileStored,
      previousPreferencesStored: parsed.previousPreferencesStored,
      previousMigrationMarker: parsed.previousMigrationMarker
        ? { ...parsed.previousMigrationMarker }
        : null,
      nextMigrationMarker: { ...parsed.nextMigrationMarker },
      state: parsed.state,
    });
  } catch {
    return null;
  }
}

function readProfileStorageSnapshot(
  storage: CompanionUserProfileSyncStorage,
): CompanionUserProfileStorageRead<CompanionUserProfile> {
  let raw: string | null;
  try {
    raw = storage.getItem(COMPANION_USER_PROFILE_STORAGE_KEY);
  } catch {
    return { status: "read-error" };
  }
  if (raw === null) {
    return {
      status: "missing",
      value: normalizeCompanionUserProfile(undefined),
    };
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isStoredProfile(parsed)) return { status: "invalid" };
    return {
      status: "present-valid",
      value: normalizeCompanionUserProfile(parsed),
    };
  } catch {
    return { status: "invalid" };
  }
}

function readPreferencesStorageSnapshot(
  storage: CompanionUserProfileSyncStorage,
): CompanionUserProfileStorageRead<CompanionPreferencesState> {
  let raw: string | null;
  try {
    raw = storage.getItem(COMPANION_PREFERENCES_STORAGE_KEY);
  } catch {
    return { status: "read-error" };
  }
  if (raw === null) {
    return {
      status: "missing",
      value: { preferences: [], recentPreferenceId: null },
    };
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isStoredPreferences(parsed)) return { status: "invalid" };
    return {
      status: "present-valid",
      value: clonePreferences(parsed),
    };
  } catch {
    return { status: "invalid" };
  }
}

function readMigrationMarkerStorageSnapshot(
  storage: CompanionUserProfileSyncStorage,
): CompanionUserProfileStorageRead<CompanionUserProfileMigrationMarker | null> {
  let raw: string | null;
  try {
    raw = storage.getItem(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY);
  } catch {
    return { status: "read-error" };
  }
  if (raw === null) return { status: "missing", value: null };
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isMarker(parsed)) return { status: "invalid" };
    return { status: "present-valid", value: { ...parsed } };
  } catch {
    return { status: "invalid" };
  }
}

function readRecoveryStorageSnapshot(
  storage: CompanionUserProfileSyncStorage,
): CompanionUserProfileStorageRead<CompanionUserProfileRecoveryRecord | null> {
  let raw: string | null;
  try {
    raw = storage.getItem(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY);
  } catch {
    return { status: "read-error" };
  }
  if (raw === null) return { status: "missing", value: null };
  const parsed = parseRecoveryRecord(raw);
  return parsed
    ? { status: "present-valid", value: parsed }
    : { status: "invalid" };
}

function sameRecoveryRecord(
  left: CompanionUserProfileRecoveryRecord | null,
  right: CompanionUserProfileRecoveryRecord,
): boolean {
  return left !== null
    && left.schemaVersion === right.schemaVersion
    && left.transactionId === right.transactionId
    && left.operation === right.operation
    && left.state === right.state
    && left.previousProfileStored === right.previousProfileStored
    && left.previousPreferencesStored === right.previousPreferencesStored
    && sameProfile(left.previousProfile, right.previousProfile)
    && sameProfile(left.nextProfile, right.nextProfile)
    && samePreferences(left.previousPreferences, right.previousPreferences)
    && samePreferences(left.nextPreferences, right.nextPreferences)
    && sameMarker(left.previousMigrationMarker, right.previousMigrationMarker)
    && sameMarker(left.nextMigrationMarker, right.nextMigrationMarker);
}

type UsableStorageRead<T> =
  | { status: "missing"; value: T }
  | { status: "present-valid"; value: T };

function isUsableRead<T>(
  result: CompanionUserProfileStorageRead<T>,
): result is UsableStorageRead<T> {
  return result.status === "missing" || result.status === "present-valid";
}

function normalizeProfileReadResult(
  result: CompanionUserProfileStorageRead<CompanionUserProfile>,
): CompanionUserProfileStorageRead<CompanionUserProfile> {
  if (result.status === "missing") {
    return {
      status: "missing",
      value: normalizeCompanionUserProfile(undefined),
    };
  }
  if (result.status !== "present-valid") return result;
  return isStoredProfile(result.value)
    ? { status: "present-valid", value: normalizeCompanionUserProfile(result.value) }
    : { status: "invalid" };
}

function normalizePreferencesReadResult(
  result: CompanionUserProfileStorageRead<CompanionPreferencesState>,
): CompanionUserProfileStorageRead<CompanionPreferencesState> {
  if (result.status === "missing") {
    return {
      status: "missing",
      value: { preferences: [], recentPreferenceId: null },
    };
  }
  if (result.status !== "present-valid") return result;
  return isStoredPreferences(result.value)
    ? { status: "present-valid", value: clonePreferences(result.value) }
    : { status: "invalid" };
}

function normalizeMarkerReadResult(
  result: CompanionUserProfileStorageRead<CompanionUserProfileMigrationMarker | null>,
): CompanionUserProfileStorageRead<CompanionUserProfileMigrationMarker | null> {
  if (result.status === "missing") return { status: "missing", value: null };
  if (result.status !== "present-valid") return result;
  return isMarker(result.value)
    ? { status: "present-valid", value: { ...result.value } }
    : { status: "invalid" };
}

function normalizeRecoveryReadResult(
  result: CompanionUserProfileStorageRead<CompanionUserProfileRecoveryRecord | null>,
): CompanionUserProfileStorageRead<CompanionUserProfileRecoveryRecord | null> {
  if (result.status === "missing") return { status: "missing", value: null };
  if (result.status !== "present-valid") return result;
  return result.value
    ? { status: "present-valid", value: cloneRecoveryRecord(result.value) }
    : { status: "invalid" };
}

function readProfileSnapshot(
  store: CompanionUserProfilePreferenceStore,
): CompanionUserProfileStorageRead<CompanionUserProfile> {
  try {
    if (store.readProfileSnapshot) {
      return normalizeProfileReadResult(store.readProfileSnapshot());
    }
    const profile = normalizeCompanionUserProfile(store.readProfile());
    const stored = store.profileStoragePresent
      ? store.profileStoragePresent()
      : true;
    if (!stored) {
      return { status: "missing", value: normalizeCompanionUserProfile(undefined) };
    }
    return isStoredProfile(profile)
      ? { status: "present-valid", value: profile }
      : { status: "invalid" };
  } catch {
    return { status: "read-error" };
  }
}

function readPreferencesSnapshot(
  store: CompanionUserProfilePreferenceStore,
): CompanionUserProfileStorageRead<CompanionPreferencesState> {
  try {
    if (store.readPreferencesSnapshot) {
      return normalizePreferencesReadResult(store.readPreferencesSnapshot());
    }
    const preferences = clonePreferences(store.readPreferences());
    const stored = store.preferencesStoragePresent
      ? store.preferencesStoragePresent()
      : true;
    if (!stored) {
      return { status: "missing", value: { preferences: [], recentPreferenceId: null } };
    }
    return isStoredPreferences(preferences)
      ? { status: "present-valid", value: preferences }
      : { status: "invalid" };
  } catch {
    return { status: "read-error" };
  }
}

function readRecoverySnapshot(
  store: CompanionUserProfilePreferenceStore,
): CompanionUserProfileStorageRead<CompanionUserProfileRecoveryRecord | null> {
  try {
    if (store.readRecoverySnapshot) {
      return normalizeRecoveryReadResult(store.readRecoverySnapshot());
    }
    const record = store.readRecoveryRecord?.() ?? null;
    const stored = store.recoveryRecordPresent
      ? store.recoveryRecordPresent()
      : record !== null;
    if (!stored) return { status: "missing", value: null };
    return record
      ? { status: "present-valid", value: cloneRecoveryRecord(record) }
      : { status: "invalid" };
  } catch {
    return { status: "read-error" };
  }
}

function readMigrationMarkerSnapshot(
  store: CompanionUserProfilePreferenceStore,
): CompanionUserProfileStorageRead<CompanionUserProfileMigrationMarker | null> {
  try {
    if (store.readMigrationMarkerSnapshot) {
      return normalizeMarkerReadResult(store.readMigrationMarkerSnapshot());
    }
    const storedMarker = store.readMigrationMarker?.() ?? null;
    const stored = store.migrationMarkerPresent
      ? store.migrationMarkerPresent()
      : storedMarker !== null;
    if (!stored) return { status: "missing", value: null };
    return storedMarker && isMarker(storedMarker)
      ? { status: "present-valid", value: { ...storedMarker } }
      : { status: "invalid" };
  } catch {
    return { status: "read-error" };
  }
}

function safeWriteProfileTarget(
  store: CompanionUserProfilePreferenceStore,
  profile: CompanionUserProfile,
): boolean {
  const target = persistedProfile(profile);
  try {
    if (!store.writeProfile(target)) return false;
    const readBack = readProfileSnapshot(store);
    return readBack.status === "present-valid"
      && sameProfile(readBack.value, target);
  } catch {
    return false;
  }
}

function safeWriteProfileExact(
  store: CompanionUserProfilePreferenceStore,
  profile: CompanionUserProfile,
): boolean {
  const target = normalizeCompanionUserProfile(profile);
  try {
    if (!store.writeProfile(target)) return false;
    const readBack = readProfileSnapshot(store);
    return readBack.status === "present-valid"
      && sameProfile(readBack.value, target);
  } catch {
    return false;
  }
}

function safeWritePreferences(
  store: CompanionUserProfilePreferenceStore,
  preferences: CompanionPreferencesState,
): boolean {
  const target = clonePreferences(preferences);
  try {
    if (!store.writePreferences(target)) return false;
    const readBack = readPreferencesSnapshot(store);
    return readBack.status === "present-valid"
      && samePreferences(readBack.value, target);
  } catch {
    return false;
  }
}

function safeWriteMarker(
  store: CompanionUserProfilePreferenceStore,
  next: CompanionUserProfileMigrationMarker,
): boolean {
  if (!store.writeMigrationMarker) return true;
  try {
    if (!store.writeMigrationMarker(next)) return false;
    const readBack = readMigrationMarkerSnapshot(store);
    return readBack.status === "present-valid"
      && sameMarker(readBack.value, next);
  } catch {
    return false;
  }
}

function safeClearMarker(
  store: CompanionUserProfilePreferenceStore,
): boolean {
  if (!store.clearMigrationMarker) return true;
  try {
    if (!store.clearMigrationMarker()) return false;
    return readMigrationMarkerSnapshot(store).status === "missing";
  } catch {
    return false;
  }
}

function safeClearRecoveryRecord(
  store: CompanionUserProfilePreferenceStore,
): boolean {
  if (!store.clearRecoveryRecord) return true;
  try {
    if (!store.clearRecoveryRecord()) return false;
    return readRecoverySnapshot(store).status === "missing";
  } catch {
    return false;
  }
}

function safeRestoreProfile(
  store: CompanionUserProfilePreferenceStore,
  profile: CompanionUserProfile,
  stored: boolean,
): boolean {
  if (!stored) {
    if (!store.clearProfile) return false;
    try {
      if (!store.clearProfile()) return false;
      return readProfileSnapshot(store).status === "missing";
    } catch {
      return false;
    }
  }
  return safeWriteProfileExact(store, profile);
}

function safeRestorePreferences(
  store: CompanionUserProfilePreferenceStore,
  preferences: CompanionPreferencesState,
  stored: boolean,
): boolean {
  if (!stored) {
    if (!store.clearPreferences) return false;
    try {
      if (!store.clearPreferences()) return false;
      return readPreferencesSnapshot(store).status === "missing";
    } catch {
      return false;
    }
  }
  return safeWritePreferences(store, preferences);
}

function safeRestoreMarker(
  store: CompanionUserProfilePreferenceStore,
  markerValue: CompanionUserProfileMigrationMarker | null,
): boolean {
  if (markerValue) return safeWriteMarker(store, markerValue);
  return safeClearMarker(store);
}

type TransactionSnapshot = {
  profile: CompanionUserProfile;
  preferences: CompanionPreferencesState;
  profileStored: boolean;
  preferencesStored: boolean;
  migrationMarker: CompanionUserProfileMigrationMarker | null;
  migrationMarkerStored: boolean;
  recoveryRecord: CompanionUserProfileRecoveryRecord | null;
  recoveryRecordStored: boolean;
};

type TransactionSnapshotRead =
  | { ok: true; snapshot: TransactionSnapshot }
  | {
      ok: false;
      reason: "read-failed" | "invalid-storage" | "recovery-blocked";
    };

type TransactionResult = {
  ok: boolean;
  cleanupSucceeded: boolean;
  profile: CompanionUserProfile;
  preferences: CompanionPreferencesState;
};

let transactionSequence = 0;

function nextTransactionId(operation: CompanionUserProfileRecoveryRecord["operation"]): string {
  transactionSequence += 1;
  return `companion-profile-${operation}-${Date.now()}-${transactionSequence}`;
}

function writeRecoveryRecordAndVerify(
  store: CompanionUserProfilePreferenceStore,
  record: CompanionUserProfileRecoveryRecord,
): boolean {
  if (!store.writeRecoveryRecord) return true;
  try {
    if (!store.writeRecoveryRecord(cloneRecoveryRecord(record))) return false;
    const readBack = readRecoverySnapshot(store);
    return readBack.status === "present-valid"
      && sameRecoveryRecord(readBack.value, record);
  } catch {
    return false;
  }
}

function restorePreviousSnapshot(
  store: CompanionUserProfilePreferenceStore,
  record: CompanionUserProfileRecoveryRecord,
): boolean {
  const profileRestored = safeRestoreProfile(
    store,
    record.previousProfile,
    record.previousProfileStored,
  );
  const preferencesRestored = safeRestorePreferences(
    store,
    record.previousPreferences,
    record.previousPreferencesStored,
  );
  const markerRestored = safeRestoreMarker(store, record.previousMigrationMarker);
  return profileRestored && preferencesRestored && markerRestored;
}

function executeProfilePreferenceTransaction(
  store: CompanionUserProfilePreferenceStore,
  snapshot: TransactionSnapshot,
  nextProfileInput: CompanionUserProfile,
  nextPreferencesInput: CompanionPreferencesState,
  operation: CompanionUserProfileRecoveryRecord["operation"],
): TransactionResult {
  const nextPreferences = clonePreferences(nextPreferencesInput);
  const nextProfile = profileWithAuthoritativeNickname(
    normalizeCompanionUserProfile(nextProfileInput),
    nextPreferences,
  );
  const nextMarker = marker();
  const prepared: CompanionUserProfileRecoveryRecord = {
    schemaVersion: 1,
    transactionId: nextTransactionId(operation),
    operation,
    previousProfile: cloneProfile(snapshot.profile),
    previousPreferences: clonePreferences(snapshot.preferences),
    nextProfile: cloneProfile(nextProfile),
    nextPreferences: clonePreferences(nextPreferences),
    previousProfileStored: snapshot.profileStored,
    previousPreferencesStored: snapshot.preferencesStored,
    previousMigrationMarker: cloneMarker(snapshot.migrationMarker),
    nextMigrationMarker: nextMarker,
    state: "prepared",
  };

  // The prepared record is the first durable mutation. If it cannot be read
  // back exactly, no business key is touched.
  if (!writeRecoveryRecordAndVerify(store, prepared)) {
    return {
      ok: false,
      cleanupSucceeded: false,
      profile: profileWithAuthoritativeNickname(snapshot.profile, snapshot.preferences),
      preferences: clonePreferences(snapshot.preferences),
    };
  }

  const failAndRestore = (): TransactionResult => {
    const restored = restorePreviousSnapshot(store, prepared);
    if (restored) safeClearRecoveryRecord(store);
    return {
      ok: false,
      cleanupSucceeded: false,
      profile: profileWithAuthoritativeNickname(snapshot.profile, snapshot.preferences),
      preferences: clonePreferences(snapshot.preferences),
    };
  };

  if (!safeWriteProfileTarget(store, nextProfile)) return failAndRestore();
  if (!safeWritePreferences(store, nextPreferences)) return failAndRestore();
  if (!safeWriteMarker(store, nextMarker)) return failAndRestore();

  const committed: CompanionUserProfileRecoveryRecord = {
    ...prepared,
    state: "committed",
  };
  if (!writeRecoveryRecordAndVerify(store, committed)) return failAndRestore();

  return {
    ok: true,
    cleanupSucceeded: safeClearRecoveryRecord(store),
    profile: nextProfile,
    preferences: nextPreferences,
  };
}

type PendingRecoveryResult = {
  present: boolean;
  valid: boolean;
  status: "none" | "recovered" | "committed" | "blocked";
  profile: CompanionUserProfile;
  preferences: CompanionPreferencesState;
};

function resolvePendingRecovery(
  store: CompanionUserProfilePreferenceStore,
  fallbackProfile: CompanionUserProfile,
  fallbackPreferences: CompanionPreferencesState,
): PendingRecoveryResult {
  const recovery = readRecoverySnapshot(store);
  if (recovery.status === "missing") {
    return {
      present: false,
      valid: true,
      status: "none",
      profile: profileWithAuthoritativeNickname(fallbackProfile, fallbackPreferences),
      preferences: clonePreferences(fallbackPreferences),
    };
  }

  if (recovery.status !== "present-valid") {
    // An unreadable recovery record is a hard stop. In particular, do not
    // treat a Profile-only nickname as a legacy candidate in this state.
    return {
      present: true,
      valid: false,
      status: "blocked",
      profile: profileWithAuthoritativeNickname(fallbackProfile, fallbackPreferences),
      preferences: clonePreferences(fallbackPreferences),
    };
  }

  const record = recovery.value;
  if (!record) {
    return {
      present: true,
      valid: false,
      status: "blocked",
      profile: profileWithAuthoritativeNickname(fallbackProfile, fallbackPreferences),
      preferences: clonePreferences(fallbackPreferences),
    };
  }

  if (record.state === "prepared") {
    const restored = restorePreviousSnapshot(store, record);
    if (restored) {
      const cleanupSucceeded = safeClearRecoveryRecord(store);
      return {
        present: !cleanupSucceeded,
        valid: true,
        status: cleanupSucceeded ? "recovered" : "blocked",
        profile: profileWithAuthoritativeNickname(record.previousProfile, record.previousPreferences),
        preferences: clonePreferences(record.previousPreferences),
      };
    }
    return {
      present: true,
      valid: true,
      status: "blocked",
      profile: profileWithAuthoritativeNickname(record.previousProfile, record.previousPreferences),
      preferences: clonePreferences(record.previousPreferences),
    };
  }

  const nextProfile = profileWithAuthoritativeNickname(record.nextProfile, record.nextPreferences);
  const repaired = safeWriteProfileTarget(store, nextProfile)
    && safeWritePreferences(store, record.nextPreferences)
    && safeWriteMarker(store, record.nextMigrationMarker);
  if (!repaired) {
    // A committed record is authoritative, but a failed repair must still
    // stop new writes. Otherwise a caller could start another transaction
    // against a partially repaired pair of business keys and overwrite the
    // only durable proof of the committed state.
    return {
      present: true,
      valid: true,
      status: "blocked",
      profile: nextProfile,
      preferences: clonePreferences(record.nextPreferences),
    };
  }
  const cleanupSucceeded = repaired && safeClearRecoveryRecord(store);
  return {
    present: !cleanupSucceeded,
    valid: true,
    status: cleanupSucceeded ? "committed" : "committed",
    profile: nextProfile,
    preferences: clonePreferences(record.nextPreferences),
  };
}

function currentSnapshot(
  store: CompanionUserProfilePreferenceStore,
): TransactionSnapshotRead {
  const profile = readProfileSnapshot(store);
  const preferences = readPreferencesSnapshot(store);
  const migrationMarker = readMigrationMarkerSnapshot(store);
  const recoveryRecord = readRecoverySnapshot(store);
  if (
    !isUsableRead(profile)
    || !isUsableRead(preferences)
    || !isUsableRead(migrationMarker)
    || !isUsableRead(recoveryRecord)
  ) {
    const reads = [profile, preferences, migrationMarker, recoveryRecord];
    if (!isUsableRead(recoveryRecord)) {
      return { ok: false, reason: "recovery-blocked" };
    }
    if (reads.some((read) => read.status === "invalid")) {
      return { ok: false, reason: "invalid-storage" };
    }
    return { ok: false, reason: "read-failed" };
  }
  return {
    ok: true,
    snapshot: {
      profile: profile.value,
      preferences: preferences.value,
      profileStored: profile.status === "present-valid",
      preferencesStored: preferences.status === "present-valid",
      migrationMarker: migrationMarker.value,
      migrationMarkerStored: migrationMarker.status === "present-valid",
      recoveryRecord: recoveryRecord.value,
      recoveryRecordStored: recoveryRecord.status === "present-valid",
    },
  };
}

export type CompanionUserProfilePreferenceCommittedSnapshot = {
  profile: CompanionUserProfile;
  preferences: CompanionPreferencesState;
};

export type CompanionUserProfilePreferenceCommitResult =
  | ({ ok: true; cleanupSucceeded: boolean } & CompanionUserProfilePreferenceCommittedSnapshot)
  | {
      ok: false;
      reason: CompanionUserProfileSettingsUnavailableReason;
    };

/**
 * The only production-facing full-state transaction boundary. Callers must
 * provide a delta-derived candidate from the Repository; this function reads
 * the authoritative storage snapshot before applying it and never emits a
 * commit callback on failure.
 */
export function commitCompanionUserProfilePreferenceState(
  store: CompanionUserProfilePreferenceStore,
  nextProfile: CompanionUserProfile,
  nextPreferences: CompanionPreferencesState,
): CompanionUserProfilePreferenceCommitResult {
  const pending = resolvePendingRecovery(
    store,
    normalizeCompanionUserProfile(undefined),
    { preferences: [], recentPreferenceId: null },
  );
  if (pending.status === "blocked" || pending.present) {
    return { ok: false, reason: "recovery-blocked" };
  }

  const snapshotResult = currentSnapshot(store);
  if (!snapshotResult.ok) return { ok: false, reason: snapshotResult.reason };
  if (snapshotResult.snapshot.recoveryRecordStored) {
    return { ok: false, reason: "recovery-blocked" };
  }

  const result = executeProfilePreferenceTransaction(
    store,
    snapshotResult.snapshot,
    nextProfile,
    nextPreferences,
    "persist",
  );
  if (!result.ok) {
    const afterFailure = currentSnapshot(store);
    return !afterFailure.ok && afterFailure.reason === "recovery-blocked"
      ? { ok: false, reason: "recovery-blocked" }
      : { ok: false, reason: "write-failed" };
  }
  return {
    ok: true,
    cleanupSucceeded: result.cleanupSucceeded,
    profile: result.profile,
    preferences: result.preferences,
  };
}

/**
 * Preference is the only durable nickname fact. The Profile nickname is a
 * compatibility mirror and is ignored when the Preference is absent, so a
 * stale mirror cannot resurrect a forgotten nickname after restart.
 */
export function resolveCompanionUserProfileFromPreferences(
  profile: CompanionUserProfile,
  preferences: CompanionPreferencesState,
): CompanionUserProfile {
  return profileWithAuthoritativeNickname(profile, preferences);
}

/**
 * Builds a legacy candidate only. Calling this helper never makes the value
 * durable; startup uses the stricter key-presence and marker gate below.
 */
export function migrateLegacyCompanionUserProfileNickname(
  profile: CompanionUserProfile,
  preferences: CompanionPreferencesState,
): CompanionUserProfileNicknameMigration {
  const normalizedProfile = normalizeCompanionUserProfile(profile);
  const currentPreferences = clonePreferences(preferences);
  if (findNicknamePreference(currentPreferences) || !normalizedProfile.nickname) {
    return {
      profile: profileWithAuthoritativeNickname(normalizedProfile, currentPreferences),
      preferences: currentPreferences,
      migrated: false,
    };
  }

  const migratedPreference: CompanionPreference = {
    id: "global.nickname",
    scope: "global",
    category: "userProfile",
    key: "nickname",
    value: normalizedProfile.nickname,
    source: "explicit",
  };
  const migratedPreferences: CompanionPreferencesState = {
    preferences: [...currentPreferences.preferences, migratedPreference],
    recentPreferenceId: migratedPreference.id,
  };
  return {
    profile: profileWithAuthoritativeNickname(normalizedProfile, migratedPreferences),
    preferences: migratedPreferences,
    migrated: true,
  };
}

/**
 * The one startup entry used by App and persistence tests. Recovery is always
 * resolved before the legacy migration gate. A Preference key that exists,
 * even when it has no nickname, is explicit authority and blocks migration.
 */
export function initializeCompanionUserProfileState(
  store: CompanionUserProfilePreferenceStore,
): CompanionUserProfileStartupState {
  const pending = resolvePendingRecovery(
    store,
    normalizeCompanionUserProfile(undefined),
    { preferences: [], recentPreferenceId: null },
  );
  if (pending.status === "blocked") {
    return {
      status: "blocked",
      reason: "recovery-blocked",
    };
  }
  if (pending.present || pending.status !== "none") {
    return {
      status: "ready",
      profile: pending.profile,
      preferences: pending.preferences,
      migrated: false,
      migrationAttempted: false,
      migrationFailed: false,
      recovery: pending.status,
    };
  }

  const snapshotResult = currentSnapshot(store);
  if (!snapshotResult.ok) {
    return {
      status: "blocked",
      reason: snapshotResult.reason,
    };
  }
  const snapshot = snapshotResult.snapshot;
  if (snapshot.recoveryRecordStored) {
    return {
      status: "blocked",
      reason: "recovery-blocked",
    };
  }

  const rawProfile = snapshot.profile;
  const rawPreferences = snapshot.preferences;
  const profileStored = snapshot.profileStored;
  const preferencesStored = snapshot.preferencesStored;
  const storedMarker = snapshot.migrationMarker;
  const markerStored = snapshot.migrationMarkerStored;
  const effectiveProfile = profileWithAuthoritativeNickname(rawProfile, rawPreferences);

  // Existing Preference storage is an explicit no-nickname decision when the
  // nickname entry is missing. This is the deletion/forget fail-closed gate.
  if (preferencesStored || markerStored || storedMarker || !profileStored || !rawProfile.nickname) {
    return {
      status: "ready",
      profile: effectiveProfile,
      preferences: rawPreferences,
      migrated: false,
      migrationAttempted: false,
      migrationFailed: false,
      recovery: "none",
    };
  }

  const migration = migrateLegacyCompanionUserProfileNickname(rawProfile, rawPreferences);
  if (!migration.migrated) {
    return {
      status: "ready",
      profile: effectiveProfile,
      preferences: rawPreferences,
      migrated: false,
      migrationAttempted: false,
      migrationFailed: false,
      recovery: "none",
    };
  }

  const result = executeProfilePreferenceTransaction(
    store,
    {
      profile: rawProfile,
      preferences: rawPreferences,
      profileStored,
      preferencesStored,
      migrationMarker: storedMarker,
      migrationMarkerStored: markerStored,
      recoveryRecord: null,
      recoveryRecordStored: false,
    },
    migration.profile,
    migration.preferences,
    "legacy-migration",
  );
  if (!result.ok) {
    return {
      status: "blocked",
      reason: "write-failed",
    };
  }
  return {
    status: "ready",
    profile: result.profile,
    preferences: result.preferences,
    migrated: true,
    migrationAttempted: true,
    migrationFailed: false,
    recovery: "none",
  };
}

/**
 * Creates the storage adapter used by App. All recovery and migration records
 * are local metadata; they are never projected to Provider, Memory, Task or
 * Observability.
 */
export function createCompanionUserProfilePreferenceStore(
  storage: CompanionUserProfileSyncStorage,
): CompanionUserProfilePreferenceStore {
  return {
    readProfileSnapshot: () => readProfileStorageSnapshot(storage),
    readProfile: () => {
      const result = readProfileStorageSnapshot(storage);
      if (isUsableRead(result)) return result.value;
      throw new Error("companion profile read failed");
    },
    writeProfile: (profile) => writeCompanionUserProfile(profile, storage, () => {}),
    readPreferencesSnapshot: () => readPreferencesStorageSnapshot(storage),
    readPreferences: () => {
      const result = readPreferencesStorageSnapshot(storage);
      if (isUsableRead(result)) return result.value;
      throw new Error("companion preferences read failed");
    },
    writePreferences: (state) => writeCompanionPreferences(state, storage, () => {}),
    profileStoragePresent: () => {
      const result = readProfileStorageSnapshot(storage);
      if (result.status === "missing") return false;
      if (result.status === "present-valid") return true;
      throw new Error("companion profile presence read failed");
    },
    preferencesStoragePresent: () => {
      const result = readPreferencesStorageSnapshot(storage);
      if (result.status === "missing") return false;
      if (result.status === "present-valid") return true;
      throw new Error("companion preferences presence read failed");
    },
    clearProfile: () => {
      try {
        storage.removeItem?.(COMPANION_USER_PROFILE_STORAGE_KEY);
        return storage.removeItem !== undefined;
      } catch {
        return false;
      }
    },
    clearPreferences: () => {
      try {
        storage.removeItem?.(COMPANION_PREFERENCES_STORAGE_KEY);
        return storage.removeItem !== undefined;
      } catch {
        return false;
      }
    },
    readRecoverySnapshot: () => readRecoveryStorageSnapshot(storage),
    readRecoveryRecord: () => {
      const result = readRecoveryStorageSnapshot(storage);
      if (isUsableRead(result)) return result.value;
      throw new Error("companion recovery read failed");
    },
    recoveryRecordPresent: () => {
      const result = readRecoveryStorageSnapshot(storage);
      if (result.status === "missing") return false;
      if (result.status === "present-valid") return true;
      throw new Error("companion recovery presence read failed");
    },
    writeRecoveryRecord: (record) => {
      try {
        storage.setItem(
          COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY,
          JSON.stringify(record),
        );
        return true;
      } catch {
        return false;
      }
    },
    clearRecoveryRecord: () => {
      try {
        storage.removeItem?.(COMPANION_USER_PROFILE_RECOVERY_STORAGE_KEY);
        return storage.removeItem !== undefined;
      } catch {
        return false;
      }
    },
    readMigrationMarkerSnapshot: () => readMigrationMarkerStorageSnapshot(storage),
    readMigrationMarker: () => {
      const result = readMigrationMarkerStorageSnapshot(storage);
      if (isUsableRead(result)) return result.value;
      throw new Error("companion migration marker read failed");
    },
    migrationMarkerPresent: () => {
      const result = readMigrationMarkerStorageSnapshot(storage);
      if (result.status === "missing") return false;
      if (result.status === "present-valid") return true;
      throw new Error("companion migration marker presence read failed");
    },
    writeMigrationMarker: (next) => {
      try {
        storage.setItem(
          COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY,
          JSON.stringify(next),
        );
        return true;
      } catch {
        return false;
      }
    },
    clearMigrationMarker: () => {
      try {
        storage.removeItem?.(COMPANION_USER_PROFILE_MIGRATION_STORAGE_KEY);
        return storage.removeItem !== undefined;
      } catch {
        return false;
      }
    },
  };
}

export function createCompanionUserProfilePreferencePersistenceForTest(
  options: CompanionUserProfilePreferenceStore & {
    initialProfile: CompanionUserProfile;
    initialPreferences: CompanionPreferencesState;
    onCommitted?: (
      profile: CompanionUserProfile,
      preferences: CompanionPreferencesState,
    ) => void;
  },
): CompanionUserProfilePreferencePersistenceForTest {
  let volatileRecoveryRecord: CompanionUserProfileRecoveryRecord | null = null;
  let volatileMigrationMarker: CompanionUserProfileMigrationMarker | null = null;
  const store: CompanionUserProfilePreferenceStore = {
    ...options,
    readRecoveryRecord: options.readRecoveryRecord ?? (() => volatileRecoveryRecord),
    recoveryRecordPresent: options.recoveryRecordPresent ?? (() => volatileRecoveryRecord !== null),
    writeRecoveryRecord: options.writeRecoveryRecord ?? ((record) => {
      volatileRecoveryRecord = cloneRecoveryRecord(record);
      return true;
    }),
    clearRecoveryRecord: options.clearRecoveryRecord ?? (() => {
      volatileRecoveryRecord = null;
      return true;
    }),
    readMigrationMarker: options.readMigrationMarker ?? (() => volatileMigrationMarker),
    migrationMarkerPresent: options.migrationMarkerPresent ?? (() => volatileMigrationMarker !== null),
    writeMigrationMarker: options.writeMigrationMarker ?? ((next) => {
      volatileMigrationMarker = { ...next };
      return true;
    }),
    clearMigrationMarker: options.clearMigrationMarker ?? (() => {
      volatileMigrationMarker = null;
      return true;
    }),
  };

  let profile = profileWithAuthoritativeNickname(
    normalizeCompanionUserProfile(options.initialProfile),
    options.initialPreferences,
  );
  let preferences = clonePreferences(options.initialPreferences);
  const initialRecovery = resolvePendingRecovery(
    store,
    profile,
    preferences,
  );
  if (initialRecovery.valid && initialRecovery.status !== "none") {
    profile = initialRecovery.profile;
    preferences = initialRecovery.preferences;
  }

  const recoverBeforeWrite = (): boolean => {
    const pending = resolvePendingRecovery(store, profile, preferences);
    if (!pending.valid) return false;
    if (pending.status === "committed") {
      profile = pending.profile;
      preferences = pending.preferences;
    } else if (pending.status === "recovered" || pending.status === "blocked") {
      profile = pending.profile;
      preferences = pending.preferences;
      if (pending.status === "blocked" && pending.present) return false;
    }
    if (pending.present) return false;
    return true;
  };

  const persistState = (
    nextProfileInput: CompanionUserProfile,
    nextPreferencesInput: CompanionPreferencesState,
  ): boolean => {
    if (!recoverBeforeWrite()) return false;
    const snapshotResult = currentSnapshot(store);
    if (!snapshotResult.ok || snapshotResult.snapshot.recoveryRecordStored) return false;
    const snapshot = snapshotResult.snapshot;
    const result = executeProfilePreferenceTransaction(
      store,
      snapshot,
      nextProfileInput,
      nextPreferencesInput,
      "persist",
    );
    if (!result.ok) {
      // The failed transaction returns its previous logical snapshot. The
      // callback is intentionally never invoked on this path.
      profile = result.profile;
      preferences = result.preferences;
      return false;
    }
    profile = profileWithAuthoritativeNickname(result.profile, result.preferences);
    preferences = clonePreferences(result.preferences);
    options.onCommitted?.(cloneProfile(profile), clonePreferences(preferences));
    return true;
  };

  return {
    getProfile: () => cloneProfile(profile),
    getPreferences: () => clonePreferences(preferences),
    persistPreferences: (nextPreferences) => persistState(profile, nextPreferences),
    persistProfile: (nextProfile, nextPreferences) => persistState(nextProfile, nextPreferences),
  };
}
