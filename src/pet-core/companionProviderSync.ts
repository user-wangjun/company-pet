import { emit, listen, type Event } from "@tauri-apps/api/event";
import type {
  CompanionProviderHydratedState,
} from "./companionProviderConfig";

export const COMPANION_PROVIDER_CHANGED_EVENT = "companion-provider-changed";

/**
 * Cross-window Provider changes are a notification only. The authoritative
 * settings and credential are deliberately absent; receivers hydrate them
 * from the ordinary settings store and secure store.
 */
export type CompanionProviderSyncNotice = {
  version: 1;
  sourceWindow: string;
  changeId: string;
};

export type CompanionProviderSyncTransport = {
  listen: (
    event: string,
    handler: (event: { payload: unknown }) => void,
  ) => Promise<() => void>;
  emit: (
    event: string,
    payload: CompanionProviderSyncNotice,
  ) => Promise<void>;
};

export type CompanionProviderSyncCoordinator = {
  start(): Promise<void>;
  stop(): void;
  hydrateFromAuthority(): Promise<void>;
  applyLocalState(next: CompanionProviderHydratedState): void;
  publishChange(): Promise<void>;
  waitForSettled(): Promise<void>;
};

export type CompanionProviderSyncCoordinatorOptions = {
  sourceWindow: string;
  initial: CompanionProviderHydratedState;
  hydrate: () => Promise<CompanionProviderHydratedState>;
  onState: (next: CompanionProviderHydratedState) => void;
  onProviderChanged: () => void;
  onListenerAttached?: (activeCount: number) => void;
  onListenerDetached?: (activeCount: number) => void;
  onSyncNotified?: () => void;
  onHydrated?: () => void;
  transport?: CompanionProviderSyncTransport;
};

const defaultTransport: CompanionProviderSyncTransport = {
  listen: async (event, handler) => {
    const unlisten = await listen<unknown>(event, (payload: Event<unknown>) => {
      handler({ payload: payload.payload });
    });
    return unlisten;
  },
  emit: async (event, payload) => {
    await emit(event, payload);
  },
};

function isNonEmptyBoundedString(value: unknown, maxLength: number): value is string {
  return typeof value === "string"
    && value.trim().length > 0
    && value.length <= maxLength;
}

export function isCompanionProviderSyncNotice(
  value: unknown,
): value is CompanionProviderSyncNotice {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  const keys = Object.keys(record).sort();
  if (keys.join("|") !== "changeId|sourceWindow|version") return false;
  return record.version === 1
    && isNonEmptyBoundedString(record.sourceWindow, 32)
    && isNonEmptyBoundedString(record.changeId, 128);
}

function nextChangeId(sourceWindow: string): string {
  const random = typeof globalThis.crypto?.randomUUID === "function"
    ? globalThis.crypto.randomUUID()
    : Math.random().toString(36).slice(2);
  return `provider-change-${sourceWindow}-${random}`;
}

/**
 * Coordinates the non-secret event seam and the async authoritative hydrate.
 * A monotonically increasing generation makes every older hydrate harmless
 * after a newer local or external Provider change has been observed.
 */
export function createCompanionProviderSyncCoordinator(
  options: CompanionProviderSyncCoordinatorOptions,
): CompanionProviderSyncCoordinator {
  const transport = options.transport ?? defaultTransport;
  let stopped = false;
  let started = false;
  let startPromise: Promise<void> | null = null;
  let listenerPromise: Promise<() => void> | null = null;
  let unlisten: (() => void) | null = null;
  let pendingListener: Promise<() => void> | null = null;
  let lifecycle = 0;
  let generation = 0;
  let settled: Promise<void> = Promise.resolve();

  const hydrateFromAuthority = (): Promise<void> => {
    if (stopped) return Promise.resolve();
    const token = ++generation;
    const hydration = Promise.resolve().then(options.hydrate);
    const outcome = hydration.then(
      (next) => {
        if (stopped || token !== generation) return;
        options.onState(next);
        try {
          options.onHydrated?.();
        } catch {
          // Observability must never change Provider synchronization behavior.
        }
      },
      () => {
        // Keep the last known state. A failed secure-store read must not
        // replace it with an empty or guessed Provider configuration.
      },
    );
    settled = outcome;
    return outcome;
  };

  const handleNotice = (payload: unknown): void => {
    if (stopped || !isCompanionProviderSyncNotice(payload)) return;
    if (payload.sourceWindow === options.sourceWindow) return;
    // Cancel before hydrate so no pending Turn can resolve against the old
    // Provider snapshot while the authoritative read is in flight.
    options.onProviderChanged();
    void hydrateFromAuthority();
  };

  const start = (): Promise<void> => {
    if (started) return startPromise ?? Promise.resolve();
    stopped = false;
    started = true;
    const startLifecycle = ++lifecycle;
    startPromise = (async () => {
      const listener = transport.listen(
        COMPANION_PROVIDER_CHANGED_EVENT,
        (event) => handleNotice(event.payload),
      );
      listenerPromise = listener;
      pendingListener = listener;
      const nextUnlisten = await listener;
      if (pendingListener === listener) pendingListener = null;
      if (stopped || !started || startLifecycle !== lifecycle) return;
      unlisten = nextUnlisten;
      try {
        options.onListenerAttached?.(1);
      } catch {
        // Observability must never change Provider synchronization behavior.
      }
      await hydrateFromAuthority();
    })().finally(() => {
      if (listenerPromise === pendingListener) listenerPromise = null;
    });
    return startPromise;
  };

  const stop = (): void => {
    if (!started && stopped) return;
    stopped = true;
    started = false;
    lifecycle += 1;
    startPromise = null;
    generation += 1;
    if (unlisten) {
      unlisten();
      unlisten = null;
      try {
        options.onListenerDetached?.(0);
      } catch {
        // Observability must never change Provider synchronization behavior.
      }
    } else if (pendingListener) {
      const listener = pendingListener;
      pendingListener = null;
      void listener.then((lateUnlisten) => {
        lateUnlisten();
        try {
          options.onListenerDetached?.(0);
        } catch {
          // Observability must never change Provider synchronization behavior.
        }
      }).catch(() => {});
    }
  };

  const applyLocalState = (next: CompanionProviderHydratedState): void => {
    if (stopped) return;
    generation += 1;
    options.onProviderChanged();
    options.onState(next);
    settled = Promise.resolve();
  };

  const publishChange = async (): Promise<void> => {
    if (stopped) return;
    const notice: CompanionProviderSyncNotice = {
      version: 1,
      sourceWindow: options.sourceWindow,
      changeId: nextChangeId(options.sourceWindow),
    };
    await transport.emit(COMPANION_PROVIDER_CHANGED_EVENT, notice);
    try {
      options.onSyncNotified?.();
    } catch {
      // Observability must never change Provider synchronization behavior.
    }
  };

  return {
    start,
    stop,
    hydrateFromAuthority,
    applyLocalState,
    publishChange,
    waitForSettled: () => settled,
  };
}
