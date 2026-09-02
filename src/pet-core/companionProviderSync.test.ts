import { describe, expect, test } from "vitest";
import type {
  CompanionProviderHydratedState,
  CompanionProviderSettings,
} from "./companionProviderConfig";
import {
  COMPANION_PROVIDER_CHANGED_EVENT,
  createCompanionProviderSyncCoordinator,
  type CompanionProviderSyncNotice,
} from "./companionProviderSync";
import { createCompanionProviderWindowLifecycle } from "./companionProviderWindowLifecycle";

const LOCAL_SETTINGS: CompanionProviderSettings = {
  id: "local",
  displayName: "本地陪伴",
  protocol: "local",
  endpoint: "",
  model: "local",
  credentialRef: null,
  fallbackToLocal: true,
  credentialConfigured: false,
};

const REMOTE_SETTINGS: CompanionProviderSettings = {
  id: "remote.test",
  displayName: "Loopback",
  protocol: "openai-compatible",
  endpoint: "http://127.0.0.1:43127/v1",
  model: "stub",
  credentialRef: "remote.test",
  fallbackToLocal: false,
  credentialConfigured: true,
};

type BusEvent = { payload: unknown };

function createBus() {
  const listeners = new Set<(event: BusEvent) => void>();
  const emitted: CompanionProviderSyncNotice[] = [];
  return {
    emitted,
    get listenerCount() {
      return listeners.size;
    },
    listen: async (
      event: string,
      handler: (event: BusEvent) => void,
    ) => {
      expect(event).toBe(COMPANION_PROVIDER_CHANGED_EVENT);
      listeners.add(handler);
      return () => listeners.delete(handler);
    },
    emit: async (event: string, payload: CompanionProviderSyncNotice) => {
      expect(event).toBe(COMPANION_PROVIDER_CHANGED_EVENT);
      emitted.push(payload);
      for (const listener of [...listeners]) listener({ payload });
    },
  };
}

function state(
  settings: CompanionProviderSettings,
  credential: string | null,
): CompanionProviderHydratedState {
  return { settings, credential };
}

describe("companion Provider cross-window synchronization", () => {
  test("hydrates the other window from authority without broadcasting a credential", async () => {
    const bus = createBus();
    let authoritative = state(LOCAL_SETTINGS, null);
    const mainStates: CompanionProviderHydratedState[] = [];
    const platformStates: CompanionProviderHydratedState[] = [];
    let mainCancels = 0;
    let platformCancels = 0;
    const main = createCompanionProviderSyncCoordinator({
      sourceWindow: "main",
      initial: authoritative,
      transport: bus,
      hydrate: async () => authoritative,
      onState: (next) => mainStates.push(next),
      onProviderChanged: () => { mainCancels += 1; },
    });
    const platform = createCompanionProviderSyncCoordinator({
      sourceWindow: "platform",
      initial: authoritative,
      transport: bus,
      hydrate: async () => authoritative,
      onState: (next) => platformStates.push(next),
      onProviderChanged: () => { platformCancels += 1; },
    });

    await Promise.all([main.start(), platform.start()]);
    authoritative = state(REMOTE_SETTINGS, "CREDENTIAL_SENTINEL_MUST_NOT_LEAVE_MEMORY");
    main.applyLocalState(authoritative);
    await main.publishChange();
    await platform.waitForSettled();

    expect(platformStates[platformStates.length - 1]).toEqual(authoritative);
    expect(mainCancels).toBe(1);
    expect(platformCancels).toBe(1);
    expect(bus.emitted).toHaveLength(1);
    expect(bus.emitted[0]).toEqual({
      version: 1,
      sourceWindow: "main",
      changeId: expect.any(String),
    });
    expect(JSON.stringify(bus.emitted[0])).not.toContain("CREDENTIAL_SENTINEL");
    expect(bus.listenerCount).toBe(2);

    main.stop();
    platform.stop();
    await Promise.resolve();
    expect(bus.listenerCount).toBe(0);
  });

  test("does not let an older asynchronous hydrate overwrite a newer local Provider", async () => {
    const bus = createBus();
    let resolveOld!: (next: CompanionProviderHydratedState) => void;
    const oldHydrate = new Promise<CompanionProviderHydratedState>((resolve) => {
      resolveOld = resolve;
    });
    const states: CompanionProviderHydratedState[] = [];
    const coordinator = createCompanionProviderSyncCoordinator({
      sourceWindow: "platform",
      initial: state(LOCAL_SETTINGS, null),
      transport: bus,
      hydrate: () => oldHydrate,
      onState: (next) => states.push(next),
      onProviderChanged: () => {},
    });

    const firstHydrate = coordinator.hydrateFromAuthority();
    const newer = state({ ...REMOTE_SETTINGS, id: "newer.test" }, "NEWER_ONLY_IN_MEMORY");
    coordinator.applyLocalState(newer);
    resolveOld(state(REMOTE_SETTINGS, "OLD_MUST_NOT_WIN"));
    await firstHydrate;
    await coordinator.waitForSettled();

    expect(states[states.length - 1]).toEqual(newer);
    expect(JSON.stringify(states)).not.toContain("OLD_MUST_NOT_WIN");
  });

  test("start is idempotent and stop prevents late notifications", async () => {
    const bus = createBus();
    const states: CompanionProviderHydratedState[] = [];
    const coordinator = createCompanionProviderSyncCoordinator({
      sourceWindow: "platform",
      initial: state(LOCAL_SETTINGS, null),
      transport: bus,
      hydrate: async () => state(LOCAL_SETTINGS, null),
      onState: (next) => states.push(next),
      onProviderChanged: () => {},
    });

    await Promise.all([coordinator.start(), coordinator.start()]);
    expect(bus.listenerCount).toBe(1);
    coordinator.stop();
    await bus.emit(COMPANION_PROVIDER_CHANGED_EVENT, {
      version: 1,
      sourceWindow: "main",
      changeId: "late",
    });
    expect(bus.listenerCount).toBe(0);
    expect(states).toHaveLength(1);
  });

  test("platform hide and reopen detach then reattach one Provider listener", async () => {
    const bus = createBus();
    const attached: number[] = [];
    const detached: number[] = [];
    const coordinator = createCompanionProviderSyncCoordinator({
      sourceWindow: "platform",
      initial: state(LOCAL_SETTINGS, null),
      transport: bus,
      hydrate: async () => state(LOCAL_SETTINGS, null),
      onState: () => {},
      onProviderChanged: () => {},
      onListenerAttached: (count) => attached.push(count),
      onListenerDetached: (count) => detached.push(count),
    });
    const lifecycle = createCompanionProviderWindowLifecycle(coordinator);

    await lifecycle.start();
    expect(bus.listenerCount).toBe(1);
    lifecycle.stop();
    await Promise.resolve();
    expect(bus.listenerCount).toBe(0);

    await lifecycle.start();
    expect(bus.listenerCount).toBe(1);
    lifecycle.stop();
    await Promise.resolve();

    expect(bus.listenerCount).toBe(0);
    expect(attached).toEqual([1, 1]);
    expect(detached).toEqual([0, 0]);
  });
});
