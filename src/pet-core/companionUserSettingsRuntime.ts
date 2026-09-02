import type {
  CompanionUserSettingsOwner,
  CompanionUserSettingsRepository,
  SettingsInitialization,
} from "./companionUserSettingsRepository";
import type {
  CompanionUserSettingsOwnerBridgeOptions,
} from "./companionUserSettingsBridge";

export type CompanionUserSettingsRuntimeOptions = {
  repository: CompanionUserSettingsRepository;
  owner: CompanionUserSettingsOwner | null;
  isPlatformWindow: boolean;
  isTauriRuntime: boolean;
  applyInitialization: (initialization: SettingsInitialization) => void;
  startOwnerBridge: (
    owner: CompanionUserSettingsOwner,
    options?: CompanionUserSettingsOwnerBridgeOptions,
  ) => Promise<() => void>;
  ownerBridgeOptions?: CompanionUserSettingsOwnerBridgeOptions;
  onOwnerBridgeStarted?: (stop: () => void) => void;
};

/**
 * Owns the App-level Settings subscription and transport lifecycles. The
 * repository is restarted before each effect setup so React StrictMode can
 * replay setup/cleanup in the same JavaScript context safely.
 */
export function startCompanionUserSettingsRuntime(
  options: CompanionUserSettingsRuntimeOptions,
): () => void {
  let disposed = false;
  options.repository.start?.();
  const unsubscribe = options.repository.subscribe((initialization) => {
    if (!disposed) options.applyInitialization(initialization);
  });
  void options.repository.initialize().then((initialization) => {
    if (!disposed) options.applyInitialization(initialization);
  });

  let stopOwnerBridge: (() => void) | undefined;
  if (!options.isPlatformWindow && options.isTauriRuntime && options.owner) {
    const ownerBridgePromise = options.ownerBridgeOptions
      ? options.startOwnerBridge(options.owner, options.ownerBridgeOptions)
      : options.startOwnerBridge(options.owner);
    void ownerBridgePromise.then((stop) => {
      if (disposed) stop();
      else {
        options.onOwnerBridgeStarted?.(stop);
        stopOwnerBridge = stop;
      }
    }).catch(() => {});
  }

  return () => {
    if (disposed) return;
    disposed = true;
    unsubscribe();
    stopOwnerBridge?.();
    options.repository.stop?.();
  };
}
