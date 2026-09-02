import { describe, expect, test, vi } from "vitest";
import { startCompanionUserSettingsRuntime } from "./companionUserSettingsRuntime";
import type {
  CompanionUserSettingsOwner,
  CompanionUserSettingsRepository,
  SettingsInitialization,
} from "./companionUserSettingsRepository";

function blockedInitialization(): SettingsInitialization {
  return {
    status: "blocked",
    reason: "not-ready",
    transportState: "not-ready",
    issuedAt: 0,
  };
}

function createRepositoryFixture() {
  const listeners = new Set<(initialization: SettingsInitialization) => void>();
  let resolveInitialize: (initialization: SettingsInitialization) => void = () => {};
  const initialize = vi.fn(() => new Promise<SettingsInitialization>((resolve) => {
    resolveInitialize = resolve;
  }));
  const repository = {
    getInitialization: () => blockedInitialization(),
    getTransportState: () => ({ status: "not-ready" as const }),
    getSnapshot: () => null,
    start: vi.fn(),
    stop: vi.fn(),
    initialize,
    subscribe: vi.fn((listener: (initialization: SettingsInitialization) => void) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    }),
    updateProfile: vi.fn(),
    upsertPreference: vi.fn(),
    deletePreference: vi.fn(),
  } as unknown as CompanionUserSettingsRepository;
  return {
    repository,
    emit: (initialization: SettingsInitialization) => {
      for (const listener of listeners) listener(initialization);
    },
    resolveInitialize: (initialization: SettingsInitialization) => resolveInitialize(initialization),
    activeListenerCount: () => listeners.size,
  };
}

describe("App companion user settings lifecycle", () => {
  test("platform cleanup releases UI subscription and Repository, and late initialization does not update UI", async () => {
    const fixture = createRepositoryFixture();
    const applied: SettingsInitialization[] = [];
    const startOwnerBridge = vi.fn(async () => vi.fn());
    const cleanup = startCompanionUserSettingsRuntime({
      repository: fixture.repository,
      owner: null,
      isPlatformWindow: true,
      isTauriRuntime: true,
      applyInitialization: (initialization) => applied.push(initialization),
      startOwnerBridge,
    });

    expect(fixture.repository.start).toHaveBeenCalledTimes(1);
    expect(fixture.repository.subscribe).toHaveBeenCalledTimes(1);
    expect(fixture.activeListenerCount()).toBe(1);
    fixture.emit(blockedInitialization());
    expect(applied).toHaveLength(1);

    cleanup();
    expect(fixture.repository.stop).toHaveBeenCalledTimes(1);
    expect(fixture.activeListenerCount()).toBe(0);
    expect(startOwnerBridge).not.toHaveBeenCalled();
    fixture.emit(blockedInitialization());
    fixture.resolveInitialize(blockedInitialization());
    await Promise.resolve();
    expect(applied).toHaveLength(1);
  });

  test("main cleanup stops the Owner Bridge, and StrictMode-style same-context restart keeps one listener", async () => {
    const fixture = createRepositoryFixture();
    const applied: SettingsInitialization[] = [];
    const stopOwnerBridge = vi.fn();
    const startOwnerBridge = vi.fn(async () => stopOwnerBridge);
    const owner = {} as CompanionUserSettingsOwner;
    const options = {
      repository: fixture.repository,
      owner,
      isPlatformWindow: false,
      isTauriRuntime: true,
      applyInitialization: (initialization: SettingsInitialization) => applied.push(initialization),
      startOwnerBridge,
    };

    const firstCleanup = startCompanionUserSettingsRuntime(options);
    await Promise.resolve();
    firstCleanup();
    expect(startOwnerBridge).toHaveBeenCalledWith(owner);
    expect(stopOwnerBridge).toHaveBeenCalledTimes(1);
    expect(fixture.repository.stop).toHaveBeenCalledTimes(1);

    const secondCleanup = startCompanionUserSettingsRuntime(options);
    expect(fixture.repository.start).toHaveBeenCalledTimes(2);
    expect(fixture.activeListenerCount()).toBe(1);
    fixture.emit(blockedInitialization());
    expect(applied).toHaveLength(1);
    await Promise.resolve();
    secondCleanup();
    expect(stopOwnerBridge).toHaveBeenCalledTimes(2);
    expect(fixture.activeListenerCount()).toBe(0);
  });
});
