import type { CompanionProviderSyncCoordinator } from "./companionProviderSync";

export type CompanionProviderWindowLifecycle = {
  start(): Promise<void>;
  stop(): void;
};

/**
 * Keeps the platform window visibility boundary explicit. Hiding the
 * dedicated window must release its event listener; showing it starts one
 * fresh listener and lets the coordinator's idempotence protect against
 * duplicate starts.
 */
export function createCompanionProviderWindowLifecycle(
  coordinator: CompanionProviderSyncCoordinator,
): CompanionProviderWindowLifecycle {
  return {
    start: () => coordinator.start(),
    stop: () => coordinator.stop(),
  };
}
