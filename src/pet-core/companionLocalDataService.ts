import {
  isCompanionPreferenceSafe,
  type CompanionPreference,
} from "./companionPreferences";
import type { MemoryRepository } from "./companionMemory";
import type {
  CompanionForgetExecutionResult,
  CompanionForgetService,
  CompanionInput,
  CompanionPreferenceExecutionResult,
  CompanionPreferenceRequest,
  CompanionPreferenceService,
} from "./companionHarnessTypes";
import type {
  CompanionUserSettingsSnapshot,
  SettingsCommandResult,
  SettingsExpectedVersion,
} from "./companionUserSettingsRepository";

export type CompanionPreferenceCommandStore = {
  read(): (CompanionUserSettingsSnapshot & {
    generation: string;
    revision: string;
    ownerEpoch: string;
    stateSeq: string;
    dataRevision: string;
  }) | null;
  upsert(
    preference: CompanionPreference,
    expected: SettingsExpectedVersion,
    correlationId: string,
  ): Promise<SettingsCommandResult>;
  delete(
    id: string,
    expected: SettingsExpectedVersion,
    correlationId: string,
  ): Promise<SettingsCommandResult>;
};

function preferenceResult(
  status: CompanionPreferenceExecutionResult["status"],
  errorCode?: string,
  key?: string,
): CompanionPreferenceExecutionResult {
  return {
    type: "preference",
    status,
    ...(errorCode ? { errorCode } : {}),
    ...(key ? { displayData: { key } } : {}),
  };
}

function samePreference(left: CompanionPreference, right: CompanionPreference): boolean {
  return left.id === right.id
    && left.scope === right.scope
    && left.category === right.category
    && left.key === right.key
    && left.value === right.value
    && left.source === right.source;
}

export function createCompanionPreferenceService(
  store: CompanionPreferenceCommandStore,
): CompanionPreferenceService {
  return {
    async process(
      input: CompanionInput,
      request: CompanionPreferenceRequest,
      signal: AbortSignal,
    ): Promise<CompanionPreferenceExecutionResult> {
      if (signal.aborted || input.signal?.aborted) {
        return preferenceResult("cancelled", "turn-invalidated", request.preference.key);
      }
      if (request.sourceMessageId !== input.sourceMessageId) {
        return preferenceResult("failed", "source-message-mismatch", request.preference.key);
      }
      if (!isCompanionPreferenceSafe(request.preference)) {
        return preferenceResult("failed", "unsafe-preference", request.preference.key);
      }

      const current = store.read();
      if (!current) return preferenceResult("failed", "not-ready", request.preference.key);
      const existing = current.preferences.preferences.find((item) => item.id === request.preference.id);
      if (existing && samePreference(existing, request.preference)) {
        return preferenceResult("duplicate", "preference-unchanged", request.preference.key);
      }
      if (signal.aborted || input.signal?.aborted) {
        return preferenceResult("cancelled", "turn-invalidated", request.preference.key);
      }

      let result: SettingsCommandResult;
      try {
        result = await store.upsert(
          request.preference,
          {
            expectedGeneration: current.generation,
            expectedRevision: current.revision,
            expectedOwnerEpoch: current.ownerEpoch,
            expectedStateSeq: current.stateSeq,
            expectedDataRevision: current.dataRevision,
          },
          `${input.requestId}:preference:${request.preference.id}`,
        );
      } catch {
        return preferenceResult("failed", "preference-write-threw", request.preference.key);
      }
      if (!result.ok) return preferenceResult("failed", result.reason, request.preference.key);
      return result.applied
        ? preferenceResult("succeeded", undefined, request.preference.key)
        : preferenceResult("duplicate", "preference-unchanged", request.preference.key);
    },
  };
}

export type CompanionForgetServiceOptions = {
  preferences: CompanionPreferenceCommandStore;
  memoryRepository: MemoryRepository;
  recentMemoryId?: () => string | null;
};

function forgetResult(
  status: CompanionForgetExecutionResult["status"],
  errorCode?: string,
): CompanionForgetExecutionResult {
  return {
    type: "forget",
    status,
    ...(errorCode ? { errorCode } : {}),
  };
}

export function createCompanionForgetService(
  options: CompanionForgetServiceOptions,
): CompanionForgetService {
  return {
    async process(
      input: CompanionInput,
      signal: AbortSignal,
    ): Promise<CompanionForgetExecutionResult> {
      if (signal.aborted || input.signal?.aborted) {
        return forgetResult("cancelled", "turn-invalidated");
      }

      const settings = options.preferences.read();
      if (!settings) return forgetResult("failed", "not-ready");

      let remembered;
      try {
        const recentMemoryId = options.recentMemoryId?.() ?? null;
        const recent = recentMemoryId ? options.memoryRepository.get(recentMemoryId) : null;
        remembered = recent
          && recent.status === "active"
          && (recent.scope === "global" || recent.scope === `pet:${input.petId}`)
          ? recent
          : options.memoryRepository.list().find(
              (entry) => entry.status === "active"
                && (entry.scope === "global" || entry.scope === `pet:${input.petId}`),
            );
      } catch {
        return forgetResult("failed", "forget-read-failed");
      }

      // Both domains are readable before any deletion starts. This is the
      // fail-closed boundary for blocked Settings: Memory must not be deleted
      // just because a stale Preferences projection looked empty.
      if (signal.aborted || input.signal?.aborted) {
        return forgetResult("cancelled", "turn-invalidated");
      }

      let deletedPreference = false;
      if (settings.preferences.recentPreferenceId) {
        let preferenceResultValue: SettingsCommandResult;
        try {
          preferenceResultValue = await options.preferences.delete(
            settings.preferences.recentPreferenceId,
            {
              expectedGeneration: settings.generation,
              expectedRevision: settings.revision,
              expectedOwnerEpoch: settings.ownerEpoch,
              expectedStateSeq: settings.stateSeq,
              expectedDataRevision: settings.dataRevision,
            },
            `${input.requestId}:forget:preference:${settings.preferences.recentPreferenceId}`,
          );
        } catch {
          return forgetResult("failed", "forget-preference-write-failed");
        }
        if (!preferenceResultValue.ok) {
          return forgetResult("failed", preferenceResultValue.reason);
        }
        deletedPreference = preferenceResultValue.applied;
      }

      let deletedMemory = false;
      if (remembered) {
        try {
          deletedMemory = Boolean(options.memoryRepository.delete(remembered.id));
        } catch {
          return forgetResult("failed", "forget-memory-write-failed");
        }
        if (!deletedMemory) return forgetResult("failed", "forget-memory-write-failed");
      }
      if (!deletedPreference && !deletedMemory) {
        return forgetResult("noop", "nothing-to-forget");
      }
      return forgetResult("succeeded");
    },
  };
}
