import {
  deleteRecentPreference,
  type CompanionPreferencesState,
} from "./companionPreferences";
import type { MemoryRepository } from "./companionMemory";

export type CompanionForgetResult = {
  preferences: CompanionPreferencesState;
  recentMemoryId: string | null;
  deletedPreference: boolean;
  deletedMemory: boolean;
  persistenceFailed: boolean;
  feedback: string;
};

/**
 * Deletes only the latest active user-level or current-pet item. The helper
 * reports an honest no-op so the UI cannot claim deletion when persistence or
 * lookup did not actually remove anything.
 */
export function forgetRecentCompanionData(input: {
  preferences: CompanionPreferencesState;
  memoryRepository: MemoryRepository;
  recentMemoryId: string | null;
  petId: string;
  persistPreferences: (state: CompanionPreferencesState) => boolean;
  warn?: (message: string) => void;
}): CompanionForgetResult {
  const warn = input.warn ?? console.warn;
  let preferences = input.preferences;
  let deletedPreference = false;
  let persistenceFailed = false;
  const recentPreferenceId = preferences.recentPreferenceId;
  if (
    recentPreferenceId
    && preferences.preferences.some((preference) => preference.id === recentPreferenceId)
  ) {
    const nextPreferences = deleteRecentPreference(preferences);
    if (input.persistPreferences(nextPreferences)) {
      preferences = nextPreferences;
      deletedPreference = true;
    } else persistenceFailed = true;
  }

  let deletedMemory = false;
  try {
    const recent = input.recentMemoryId
      ? input.memoryRepository.get(input.recentMemoryId)
      : null;
    const remembered = recent
      && recent.status === "active"
      && (recent.scope === "global" || recent.scope === `pet:${input.petId}`)
      ? recent
      : input.memoryRepository.list().find(
          (entry) =>
            entry.status === "active"
            && (entry.scope === "global" || entry.scope === `pet:${input.petId}`),
        );
    if (remembered) {
      deletedMemory = Boolean(input.memoryRepository.delete(remembered.id));
      if (!deletedMemory) persistenceFailed = true;
    }
  } catch {
    warn("[companion-memory] Failed to forget recent memory");
    persistenceFailed = true;
  }

  return {
    preferences,
    recentMemoryId: null,
    deletedPreference,
    deletedMemory,
    persistenceFailed,
    feedback: persistenceFailed
      ? "我暂时没能完整忘掉这条内容，请稍后再试。"
      : deletedPreference || deletedMemory
      ? "好，我忘掉刚才那条。"
      : "最近没有可删除的偏好或 Memory。",
  };
}
