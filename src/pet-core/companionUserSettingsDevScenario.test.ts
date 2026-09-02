import { describe, expect, test, vi } from "vitest";
import { startCompanionUserSettingsDevScenario } from "./companionUserSettingsDevScenario";
import type {
  CompanionUserSettingsOwner,
  CompanionUserSettingsRepository,
} from "./companionUserSettingsRepository";

describe("Companion User Settings DEV scenario guard", () => {
  test("does not activate without the exact DEV scenario marker", () => {
    const startOwnerBridge = vi.fn();
    const createOwner = vi.fn();
    const cleanup = startCompanionUserSettingsDevScenario({
      repository: {} as CompanionUserSettingsRepository,
      isPlatformWindow: false,
      isTauriRuntime: true,
      owner: {} as CompanionUserSettingsOwner,
      createOwner,
      startOwnerBridge,
      ownerBridgeEvents: [],
    });

    cleanup();

    expect(startOwnerBridge).not.toHaveBeenCalled();
    expect(createOwner).not.toHaveBeenCalled();
  });
});
