import { describe, expect, test, vi } from "vitest";
import {
  EMPTY_COMPANION_PREFERENCES,
  extractCompanionPreference,
  upsertCompanionPreference,
  type CompanionPreferencesState,
} from "./companionPreferences";
import {
  createCompanionMemoryRepository,
  type MemoryEntryInput,
} from "./companionMemory";
import { forgetRecentCompanionData } from "./companionForget";

const NOW = Date.parse("2026-08-02T12:00:00.000Z");

function memoryInput(
  id: string,
  scope: MemoryEntryInput["scope"],
): MemoryEntryInput {
  return {
    id,
    scope,
    type: "preference",
    content: "用户喜欢桂花茶",
    source: "explicit",
    evidence: "我喜欢桂花茶，请记住。",
    sourceMessageId: `message-${id}`,
    confidence: 0.98,
    expiresAt: null,
    status: "active",
    supersedesId: null,
  };
}

function forgetInput(
  preferences: CompanionPreferencesState,
  repository: ReturnType<typeof createCompanionMemoryRepository>,
  persistPreferences: (state: CompanionPreferencesState) => boolean,
  recentMemoryId: string | null = null,
) {
  return forgetRecentCompanionData({
    preferences,
    memoryRepository: repository,
    recentMemoryId,
    petId: "xiaoju-cat",
    persistPreferences,
  });
}

describe("companion forget boundary", () => {
  test("reports an honest no-op when there is no recent data", () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const persistPreferences = vi.fn(() => true);

    const result = forgetInput(
      EMPTY_COMPANION_PREFERENCES,
      repository,
      persistPreferences,
    );

    expect(result.feedback).toBe("最近没有可删除的偏好或 Memory。");
    expect(result.deletedPreference).toBe(false);
    expect(result.deletedMemory).toBe(false);
    expect(persistPreferences).not.toHaveBeenCalled();
  });

  test("deletes the latest preference and memory through their real boundaries", () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    const memory = repository.save(memoryInput("memory-tea", "global"));
    const preference = extractCompanionPreference("以后叫我阿星")!.preference;
    const preferences = upsertCompanionPreference(
      EMPTY_COMPANION_PREFERENCES,
      preference,
    );
    const persistPreferences = vi.fn(() => true);

    const result = forgetInput(
      preferences,
      repository,
      persistPreferences,
      memory?.id ?? null,
    );

    expect(result.feedback).toBe("好，我忘掉刚才那条。");
    expect(result.deletedPreference).toBe(true);
    expect(result.deletedMemory).toBe(true);
    expect(result.preferences).toEqual(EMPTY_COMPANION_PREFERENCES);
    expect(persistPreferences).toHaveBeenCalledWith(EMPTY_COMPANION_PREFERENCES);
    expect(repository.get("memory-tea")).toMatchObject({
      status: "deleted",
      content: "（已删除）",
      evidence: "（已删除）",
    });
  });

  test("does not delete a memory belonging to another pet", () => {
    const repository = createCompanionMemoryRepository({ now: () => NOW });
    repository.save(memoryInput("other-memory", "pet:other-pet"));
    repository.save(memoryInput("current-memory", "pet:xiaoju-cat"));
    const persistPreferences = vi.fn(() => true);

    const result = forgetInput(
      EMPTY_COMPANION_PREFERENCES,
      repository,
      persistPreferences,
    );

    expect(result.deletedMemory).toBe(true);
    expect(repository.get("current-memory")?.status).toBe("deleted");
    expect(repository.get("other-memory")?.status).toBe("active");
  });
});
