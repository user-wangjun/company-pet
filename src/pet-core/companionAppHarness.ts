import {
  generateLocalCompanionReply,
  resolveCompanionChatPackage,
  type CompanionChatPackage,
} from "./companionChat";
import type { CompanionChatMessage } from "./companionChatRuntime";
import {
  createCompanionContextBuilder,
  type CompanionContextBuilder,
} from "./companionContext";
import { createCompanionHarness } from "./companionHarness";
import type {
  CompanionHarness,
  CompanionResponseSink,
  CompanionTaskRepository,
} from "./companionHarnessTypes";
import {
  createCompanionActionService,
} from "./companionActionPipeline";
import {
  createCompanionForgetService,
  createCompanionPreferenceService,
} from "./companionLocalDataService";
import type { CompanionPreferencesState } from "./companionPreferences";
import type { CompanionUserSettingsRepository } from "./companionUserSettingsRepository";
import {
  createCompanionModelPort,
  type CompanionModelPort,
  type HarnessModelRequest,
} from "./companionModelPort";
import {
  createCompanionProviderResolver,
} from "./companionProviderResolver";
import {
  getCompanionProviderProfilePreset,
  type CompanionProviderProfile,
} from "./companionProviderConfig";
import {
  createCompanionProactivePreferenceService,
} from "./companionProactivePreference";
import type { MemoryRepository } from "./companionMemory";
import type { PetSoulPackage } from "./petSoul";
import type {
  ProactiveTaskPreferencePatch,
  ProactiveTriggerEngine,
} from "./proactiveTriggerEngine";
import type { ProviderHttpFetcher } from "./companionProviderAdapter";
import {
  createCompanionObservationRecorder,
  type CompanionObservationRecorder,
  type CompanionObservability,
} from "./companionObservability";

export const COMPANION_LOCAL_USER_ID = "local-user";

export type CompanionAppHarnessSources = {
  getProviderProfile: () => CompanionProviderProfile;
  getProviderCredential: () => string | null;
  getFallbackToLocal: () => boolean;
  getActivePetId: () => string;
  getAvailablePetIds: () => readonly string[];
  getCompanionChatPackage: (petId: string) => CompanionChatPackage;
  getPetSoul: (petId: string) => PetSoulPackage | undefined;
  getPreferences: () => CompanionPreferencesState | null;
  getMemoryRepository: () => MemoryRepository;
  getHistory: (input: {
    petId: string;
    sessionId: string;
    sourceMessageId?: string;
    contextEpoch?: number;
  }) => readonly CompanionChatMessage[];
  taskRepository: CompanionTaskRepository;
  getProactiveTriggerEngine: () => Pick<
    ProactiveTriggerEngine,
    "getState" | "getLastDeliveryContext" | "setTaskPreference"
  >;
  settingsRepository: CompanionUserSettingsRepository;
  responseSink: CompanionResponseSink;
  observability?: CompanionObservability;
  fetcher?: ProviderHttpFetcher;
  verifiedCapabilities?: Partial<import("./companionProviderAdapter").ProviderCapabilities>;
};

export type CompanionAppHarnessRuntime = {
  harness: CompanionHarness;
  modelPort: CompanionModelPort;
  localFallbackModelPort: CompanionModelPort;
  contextBuilder: CompanionContextBuilder;
  observability: CompanionObservationRecorder | CompanionObservability;
};

function localGeneration(
  sources: CompanionAppHarnessSources,
  request: HarnessModelRequest,
): string {
  const config = resolveCompanionChatPackage(
    sources.getCompanionChatPackage(request.input.petId),
  );
  const history = request.context.history.map((message) => ({
    speaker: message.speaker,
    text: message.text,
  }));
  return generateLocalCompanionReply(config, {
    message: request.input.message,
    systemInstruction: request.context.systemInstruction,
    history,
  });
}

function localProfile(): CompanionProviderProfile {
  return getCompanionProviderProfilePreset("local") ?? {
    id: "local",
    displayName: "本地陪伴",
    protocol: "local",
    endpoint: "",
    model: "local",
    credentialRef: null,
  };
}

function createDynamicPreferenceEngine(
  sources: CompanionAppHarnessSources,
): Pick<ProactiveTriggerEngine, "getState" | "getLastDeliveryContext" | "setTaskPreference"> {
  return {
    getState: (now = new Date()) => sources.getProactiveTriggerEngine().getState(now),
    getLastDeliveryContext: (now = new Date()) =>
      sources.getProactiveTriggerEngine().getLastDeliveryContext(now),
    setTaskPreference: (
      taskId: string,
      patch: ProactiveTaskPreferencePatch,
      now = new Date(),
    ) => sources.getProactiveTriggerEngine().setTaskPreference(taskId, patch, now),
  };
}

function createProviderModelPort(
  sources: CompanionAppHarnessSources,
  profile: CompanionProviderProfile | (() => CompanionProviderProfile),
  credential: string | null | (() => string | null),
): CompanionModelPort {
  const resolver = createCompanionProviderResolver({
    profile,
    credential,
    fetcher: sources.fetcher,
    verifiedCapabilities: sources.verifiedCapabilities,
  });
  return createCompanionModelPort({
    resolver,
    info: {
      kind: "local",
      provider: "本地 Provider",
      target: "本机",
      disclosure: "本地模式：不会发起网络请求。",
    },
    localGenerate: (request) => localGeneration(sources, request),
  });
}

export function createCompanionAppHarness(
  sources: CompanionAppHarnessSources,
): CompanionAppHarnessRuntime {
  const observability = sources.observability ?? createCompanionObservationRecorder();
  const contextBuilder = createCompanionContextBuilder({
    soul: ({ petId }) => sources.getPetSoul(petId),
    preferences: () => sources.getPreferences()?.preferences ?? [],
    memoryRepository: sources.getMemoryRepository(),
    history: ({ petId, sessionId, sourceMessageId, contextEpoch }) =>
      sources.getHistory({ petId, sessionId, sourceMessageId, contextEpoch }),
    systemPrompt: ({ petId }) =>
      resolveCompanionChatPackage(sources.getCompanionChatPackage(petId)).systemPrompt,
    style: ({ petId }) =>
      resolveCompanionChatPackage(sources.getCompanionChatPackage(petId)).style,
    now: () => Date.now(),
  });

  const modelPort = createProviderModelPort(
    sources,
    sources.getProviderProfile,
    sources.getProviderCredential,
  );
  const localFallbackModelPort = createProviderModelPort(
    sources,
    localProfile(),
    null,
  );
  const proactivePreferenceService = createCompanionProactivePreferenceService({
    repository: sources.taskRepository,
    triggerEngine: createDynamicPreferenceEngine(sources),
    availablePetIds: () => sources.getAvailablePetIds(),
    activePetId: () => sources.getActivePetId(),
  });
  const preferences = {
    read: () => sources.settingsRepository.getSnapshot(),
    upsert: (
      preference: import("./companionPreferences").CompanionPreference,
      expected: import("./companionUserSettingsRepository").SettingsExpectedVersion,
      correlationId: string,
    ) => sources.settingsRepository.upsertPreference(preference, expected, correlationId),
    delete: (
      id: string,
      expected: import("./companionUserSettingsRepository").SettingsExpectedVersion,
      correlationId: string,
    ) => sources.settingsRepository.deletePreference(id, expected, correlationId),
  };

  const harness = createCompanionHarness({
    modelPort,
    localFallbackModelPort,
    contextBuilder,
    actionService: createCompanionActionService(sources.taskRepository),
    proactivePreferenceService,
    preferenceService: createCompanionPreferenceService(preferences),
    forgetService: createCompanionForgetService({
      preferences,
      memoryRepository: sources.getMemoryRepository(),
    }),
    memoryRepository: sources.getMemoryRepository(),
    responseSink: sources.responseSink,
    fallbackToLocal: sources.getFallbackToLocal,
    observability,
  });

  return {
    harness,
    modelPort,
    localFallbackModelPort,
    contextBuilder,
    observability,
  };
}
