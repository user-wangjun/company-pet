import { describe, expect, test, vi } from "vitest";
import {
  COMPANION_PREFERENCES_STORAGE_KEY,
  EMPTY_COMPANION_PREFERENCES,
  deleteRecentPreference,
  extractCompanionPreference,
  isForgetRecentPreferenceRequest,
  parseCompanionPreferences,
  readCompanionPreferences,
  upsertCompanionPreference,
  writeCompanionPreferences,
} from "./companionPreferences";

function storage(initial: string | null = null) {
  let value = initial;
  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((_key: string, next: string) => {
      value = next;
    }),
  };
}

describe("companion preferences", () => {
  test("extracts explicit nickname preferences with feedback", () => {
    expect(extractCompanionPreference("以后叫我阿星")).toEqual({
      preference: {
        id: "global.nickname",
        scope: "global",
        category: "userProfile",
        key: "nickname",
        value: "阿星",
        source: "explicit",
      },
      feedback: "好呀，我以后叫你阿星。",
    });
  });

  test("extracts quiet and short reply style preferences", () => {
    expect(extractCompanionPreference("回答短一点，别太严肃")?.preference).toMatchObject({
      id: "global.replyStyle",
      value: "short-and-soft",
    });
    expect(extractCompanionPreference("我喜欢安静一点")?.preference).toMatchObject({
      id: "global.companionStyle",
      source: "inferred",
      value: "quiet",
    });
  });

  test("stores health input as care preference instead of diagnosis", () => {
    const result = extractCompanionPreference("我有偏头痛，提醒我少盯屏幕");

    expect(result?.preference).toMatchObject({
      id: "global.eyeCare",
      category: "reminderPreferences",
      value: "reduce-screen-staring",
    });
    expect(JSON.stringify(result)).not.toContain("偏头痛");
  });

  test("ignores uncertain and sensitive inputs", () => {
    expect(extractCompanionPreference("今天好累")).toBeNull();
    expect(extractCompanionPreference("我的身份证号是 123")).toBeNull();
  });

  test("can forget the recent preference", () => {
    expect(isForgetRecentPreferenceRequest("忘掉这个")).toBe(true);
    expect(isForgetRecentPreferenceRequest("别记这个")).toBe(true);
    expect(isForgetRecentPreferenceRequest("你好呀")).toBe(false);
  });

  test("reads, writes, upserts, repairs, and deletes preferences", () => {
    const store = storage();
    const warn = vi.fn();
    const preference = extractCompanionPreference("以后叫我阿星")!.preference;
    const state = upsertCompanionPreference(EMPTY_COMPANION_PREFERENCES, preference);

    expect(writeCompanionPreferences(state, store, warn)).toBe(true);
    expect(store.setItem).toHaveBeenCalledWith(
      COMPANION_PREFERENCES_STORAGE_KEY,
      JSON.stringify(state),
    );
    expect(readCompanionPreferences(store, warn)).toEqual(state);
    expect(deleteRecentPreference(state)).toEqual({
      preferences: [],
      recentPreferenceId: null,
    });
    expect(parseCompanionPreferences("not-json")).toEqual(EMPTY_COMPANION_PREFERENCES);
  });
});
