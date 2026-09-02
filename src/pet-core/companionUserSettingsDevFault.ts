import type { CompanionUserProfileSyncStorage } from "./companionUserProfileSync";

const DEV_SETTINGS_FAULT_STORAGE_KEY = "__yuxin_companion_settings_dev_fault__";
const DEV_SETTINGS_READ_FAULT = "read";

function isDevReadFaultRequested(): boolean {
  return import.meta.env.DEV
    && import.meta.env.VITE_XIAOJU_SETTINGS_FAULT === DEV_SETTINGS_READ_FAULT;
}

/**
 * A development-only, session-scoped read fault for real Owner recovery checks.
 * The marker is deliberately isolated from Profile/Preferences keys and is
 * removed by the explicit retry action before the unrestricted reread.
 */
export function createCompanionUserSettingsDevStorage(
  storage: CompanionUserProfileSyncStorage,
): CompanionUserProfileSyncStorage {
  if (!isDevReadFaultRequested()) return storage;

  try {
    if (storage.getItem(DEV_SETTINGS_FAULT_STORAGE_KEY) !== DEV_SETTINGS_READ_FAULT) {
      storage.setItem(DEV_SETTINGS_FAULT_STORAGE_KEY, DEV_SETTINGS_READ_FAULT);
    }
  } catch {
    // The actual settings read below remains fail-closed if storage is already
    // unavailable; this marker is only a test control, never user data.
  }

  return {
    getItem: (key) => {
      if (
        isDevReadFaultRequested()
        && storage.getItem(DEV_SETTINGS_FAULT_STORAGE_KEY) === DEV_SETTINGS_READ_FAULT
      ) {
        throw new Error("DEV-only Companion settings read fault");
      }
      return storage.getItem(key);
    },
    setItem: (key, value) => storage.setItem(key, value),
    ...(storage.removeItem
      ? { removeItem: (key: string) => storage.removeItem!(key) }
      : {}),
  };
}

export function clearCompanionUserSettingsDevFault(): void {
  if (!import.meta.env.DEV || typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(DEV_SETTINGS_FAULT_STORAGE_KEY);
  } catch {
    // The retry path still performs its normal unrestricted reread attempt.
  }
}
