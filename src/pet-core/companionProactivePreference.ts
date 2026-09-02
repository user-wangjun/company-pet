import type {
  CompanionProactivePreferenceExecutionResult,
  CompanionProactivePreferenceRequest,
  CompanionProactivePreferenceService,
  CompanionTaskRepository,
  CompanionInput,
} from "./companionHarnessTypes";
import {
  resolveProactiveTaskControlTarget,
  type ProactiveTaskControlResolution,
} from "./proactiveTaskControl";
import type { ProactiveTriggerEngine } from "./proactiveTriggerEngine";
import type { ProactiveTaskPreferencePatch } from "./proactiveTriggerEngine";
import { containsSensitiveCompanionText } from "./companionPrivacy";

type PreferenceEngine = Pick<
  ProactiveTriggerEngine,
  "getState" | "getLastDeliveryContext" | "setTaskPreference"
>;

export interface CompanionProactivePreferenceServiceOptions {
  repository: CompanionTaskRepository;
  triggerEngine: PreferenceEngine;
  /** The pets that can actually receive the next proactive delivery. */
  availablePetIds?: readonly string[] | (() => readonly string[]);
  /** Used to choose the next pet when no delivery context is available. */
  activePetId?: string | (() => string);
}

function result(
  request: CompanionProactivePreferenceRequest,
  status: CompanionProactivePreferenceExecutionResult["status"],
  errorCode?: string,
  displayData?: Record<string, string>,
): CompanionProactivePreferenceExecutionResult {
  return {
    type: "proactive_preference",
    action: request.action,
    status,
    ...(errorCode ? { errorCode } : {}),
    ...(displayData ? { displayData } : {}),
  };
}

function safeTaskDisplayTitle(value: string): Record<string, string> | undefined {
  const normalized = value.trim();
  if (!normalized || containsSensitiveCompanionText(normalized)) return undefined;
  const title = Array.from(normalized).slice(0, 120).join("");
  return title ? { title } : undefined;
}

function nowFromInput(input: CompanionInput): Date | null {
  const timestamp = Date.parse(input.currentTime);
  return Number.isFinite(timestamp) ? new Date(timestamp) : null;
}

function isActiveTask(task: { deletedAt: string | null; status: string }): boolean {
  return !task.deletedAt && task.status !== "completed" && task.status !== "cancelled";
}

function resolutionFailure(
  request: CompanionProactivePreferenceRequest,
  resolution: Exclude<ProactiveTaskControlResolution, { status: "resolved" }>,
): CompanionProactivePreferenceExecutionResult {
  if (resolution.status === "not-found") {
    return result(request, "not_found", "target-not-found");
  }
  if (resolution.status === "ambiguous") {
    return result(request, "ambiguous", "multiple-targets");
  }
  if (resolution.reason === "ambiguous-context") {
    return result(request, "ambiguous", "ambiguous-recent-delivery");
  }
  return result(
    request,
    "confirmation_required",
    resolution.reason === "stale-context" ? "stale-recent-delivery" : "missing-target",
  );
}

function preferenceFor(
  state: ReturnType<PreferenceEngine["getState"]>,
  taskId: string,
): { mode: "normal" | "muted" | "reduced"; preferredPetId: string | null } {
  return state.taskState?.preferences[taskId] ?? {
    mode: "normal",
    preferredPetId: null,
  };
}

function samePreference(
  current: ReturnType<typeof preferenceFor>,
  action: CompanionProactivePreferenceRequest["action"],
  patch: ProactiveTaskPreferencePatch,
): boolean {
  if (action === "mute") return current.mode === patch.mode;
  if (action === "reduce") return current.mode === patch.mode;
  return current.preferredPetId === (patch.preferredPetId ?? null);
}

function nextPet(
  currentPetId: string,
  preferredPetId: string | null,
  availablePetIds: readonly string[],
): string | null {
  const pets = [...new Set(availablePetIds.filter((petId) => petId.trim()))];
  const switchable = pets.filter((petId) => petId !== currentPetId);
  if (!switchable.length) return null;

  // A retry of the same command keeps the already selected other pet as the
  // effective result. A genuinely new command after the UI has switched pets
  // can then select the next available pet.
  if (preferredPetId && preferredPetId !== currentPetId && switchable.includes(preferredPetId)) {
    return preferredPetId;
  }

  const start = Math.max(0, pets.indexOf(currentPetId));
  for (let offset = 1; offset <= pets.length; offset += 1) {
    const candidate = pets[(start + offset) % pets.length];
    if (candidate && candidate !== currentPetId) return candidate;
  }
  return switchable[0] ?? null;
}

function buildPatch(
  request: CompanionProactivePreferenceRequest,
  current: ReturnType<typeof preferenceFor>,
  currentPetId: string,
  availablePetIds: readonly string[],
): { patch: ProactiveTaskPreferencePatch; preferredPetId: string | null } | {
  result: CompanionProactivePreferenceExecutionResult;
} {
  if (request.action === "mute") {
    return { patch: { mode: "muted" }, preferredPetId: current.preferredPetId };
  }
  if (request.action === "reduce") {
    return { patch: { mode: "reduced" }, preferredPetId: current.preferredPetId };
  }

  const preferredPetId = nextPet(currentPetId, current.preferredPetId, availablePetIds);
  if (!preferredPetId) {
    return {
      result: result(request, "confirmation_required", "no-switchable-pet"),
    };
  }
  return { patch: { preferredPetId }, preferredPetId };
}

function preferenceMatches(
  state: ReturnType<PreferenceEngine["getState"]>,
  taskId: string,
  request: CompanionProactivePreferenceRequest,
  patch: ProactiveTaskPreferencePatch,
): boolean {
  return samePreference(preferenceFor(state, taskId), request.action, patch);
}

export function createCompanionProactivePreferenceService(
  options: CompanionProactivePreferenceServiceOptions,
): CompanionProactivePreferenceService {
  return {
    async process(
      input,
      request,
      signal,
    ): Promise<CompanionProactivePreferenceExecutionResult> {
      if (signal.aborted || input.signal?.aborted) {
        return result(request, "cancelled", "turn-invalidated");
      }
      if (request.sourceMessageId !== input.sourceMessageId) {
        return result(request, "rejected", "source-message-mismatch");
      }

      const now = nowFromInput(input);
      if (!now) return result(request, "failed", "invalid-current-time");

      let database: ReturnType<CompanionTaskRepository["read"]>;
      let state: ReturnType<PreferenceEngine["getState"]>;
      let recentContext: ReturnType<PreferenceEngine["getLastDeliveryContext"]>;
      try {
        database = options.repository.read();
        state = options.triggerEngine.getState(now);
        recentContext = options.triggerEngine.getLastDeliveryContext(now);
      } catch {
        return result(request, "failed", "proactive-preference-read-failed");
      }

      const resolution = resolveProactiveTaskControlTarget(
        {
          action: request.action,
          targetTitle: request.targetTitle,
        },
        database,
        recentContext,
        now,
      );
      if (resolution.status !== "resolved") return resolutionFailure(request, resolution);
      if (!isActiveTask(resolution.task)) {
        return result(request, "not_found", "target-not-active");
      }

      const displayData = safeTaskDisplayTitle(resolution.task.title);
      const current = preferenceFor(state, resolution.task.id);
      const currentPetId = recentContext?.petId
        ?? (typeof options.activePetId === "function" ? options.activePetId() : options.activePetId)
        ?? input.petId;
      const availablePetIds = typeof options.availablePetIds === "function"
        ? options.availablePetIds()
        : options.availablePetIds ?? [];
      const patchResult = buildPatch(request, current, currentPetId, availablePetIds);
      if ("result" in patchResult) return patchResult.result;
      const { patch, preferredPetId } = patchResult;

      if (samePreference(current, request.action, patch)) {
        return result(request, "duplicate", "preference-unchanged", displayData);
      }
      if (signal.aborted || input.signal?.aborted) {
        return result(request, "cancelled", "turn-invalidated", displayData);
      }

      let persistedState: ReturnType<PreferenceEngine["setTaskPreference"]>;
      try {
        // The existing Trigger Engine remains the sole preference writer.
        // Its contract is to return only after writeProactiveExpressionState()
        // confirms persistence, and to throw when persistence is not confirmed.
        persistedState = options.triggerEngine.setTaskPreference(resolution.task.id, patch, now);
      } catch {
        return result(request, "failed", "proactive-preference-write-threw", displayData);
      }

      const persisted = preferenceMatches(
        persistedState,
        resolution.task.id,
        request,
        patch,
      );
      if (!persisted) {
        return result(request, "failed", "proactive-preference-write-failed", displayData);
      }

      // A late cancellation must preserve the domain fact established by the
      // successful writer. The Harness will discard the UI commit separately.
      if (signal.aborted || input.signal?.aborted) {
        // The writer has already established the domain fact. A late abort
        // prevents the Harness/UI commit, but must not erase that fact.
        return result(
          request,
          "succeeded",
          undefined,
          request.action === "switch_pet" && preferredPetId
            ? { ...(displayData ?? {}), preferredPetId }
            : displayData,
        );
      }

      // A live turn gets a defensive read-back. A read failure cannot undo a
      // writer result that already confirmed persistence; a concrete mismatch
      // remains a failed write rather than a success.
      let verifiedState: ReturnType<PreferenceEngine["getState"]>;
      try {
        verifiedState = options.triggerEngine.getState(now);
      } catch {
        // The writer-confirmed state is still the best available fact when a
        // later verification read is unavailable.
        return result(
          request,
          "succeeded",
          undefined,
          request.action === "switch_pet" && preferredPetId
            ? { ...(displayData ?? {}), preferredPetId }
            : displayData,
        );
      }
      if (!preferenceMatches(verifiedState, resolution.task.id, request, patch)) {
        return result(request, "failed", "proactive-preference-write-failed", displayData);
      }

      return result(
        request,
        "succeeded",
        undefined,
        request.action === "switch_pet" && preferredPetId
          ? { ...(displayData ?? {}), preferredPetId }
          : displayData,
      );
    },
  };
}
