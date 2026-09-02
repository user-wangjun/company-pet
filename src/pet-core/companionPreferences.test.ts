import { describe, expect, test, vi } from "vitest";
import {
  COMPANION_PREFERENCES_STORAGE_KEY,
  EMPTY_COMPANION_PREFERENCES,
  deleteRecentPreference,
  extractCompanionPreference,
  hasExplicitQuietCompanionPreferenceChange,
  hasPersistentCompanionPreferenceScope,
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
    expect(extractCompanionPreference("以后叫我阿星。")?.preference).toEqual(
      extractCompanionPreference("以后叫我阿星")?.preference,
    );
  });

  test("extracts short reply style and only explicit persistent quiet preferences", () => {
    expect(extractCompanionPreference("回答短一点，别太严肃")?.preference).toMatchObject({
      id: "global.replyStyle",
      value: "short-and-soft",
    });
    expect(extractCompanionPreference("以后请安静一点陪我")?.preference).toMatchObject({
      id: "global.companionStyle",
      source: "explicit",
      value: "quiet",
    });
  });

  test("keeps persistent scope and explicit quiet-change intent independently testable", () => {
    expect(hasPersistentCompanionPreferenceScope("我今天有点累，想安静坐一会儿。")).toBe(false);
    expect(hasExplicitQuietCompanionPreferenceChange("我今天有点累，想安静坐一会儿。")).toBe(false);
    expect(hasPersistentCompanionPreferenceScope("以后请安静一点陪我")).toBe(true);
    expect(hasExplicitQuietCompanionPreferenceChange("以后请安静一点陪我")).toBe(true);
    expect(hasPersistentCompanionPreferenceScope("以后陪我")).toBe(true);
    expect(hasExplicitQuietCompanionPreferenceChange("以后陪我")).toBe(false);
  });

  test.each([
    "我今天有点累，想安静坐一会儿。",
    "这里很安静。",
    "今晚想安静待一会儿。",
    "你安静陪我坐一会儿就好。",
    "窗外很安静，月光也很好看。",
    "我想听你陪我安静聊两句。",
    "这是一次功能测试。请用两句简短中文回应：我今天有点累，想安静坐一会儿。不要创建任务、提醒或记忆。",
  ])("does not persist ordinary quiet expression: %s", (text) => {
    expect(extractCompanionPreference(text)).toBeNull();
  });

  test.each([
    "以后请安静一点陪我。",
    "今后少打扰我。",
    "从现在起陪伴时别太吵。",
    "记住，以后陪我时安静一些。",
  ])("extracts an explicit persistent quiet preference: %s", (text) => {
    expect(extractCompanionPreference(text)?.preference).toMatchObject({
      id: "global.companionStyle",
      scope: "global",
      category: "userProfile",
      key: "companionStyle",
      value: "quiet",
      source: "explicit",
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
    expect(isForgetRecentPreferenceRequest("忘掉刚才那条。")).toBe(true);
    expect(isForgetRecentPreferenceRequest("你好呀")).toBe(false);
  });

  test("rejects sensitive values at the preference write boundary", () => {
    const store = storage();
    const warn = vi.fn();
    const state = upsertCompanionPreference(EMPTY_COMPANION_PREFERENCES, {
      id: "global.nickname",
      scope: "global",
      category: "userProfile",
      key: "nickname",
      value: "my password is never-save",
      source: "explicit",
    });

    expect(state).toEqual(EMPTY_COMPANION_PREFERENCES);
    expect(writeCompanionPreferences({
      preferences: [{
        id: "global.nickname",
        scope: "global",
        category: "userProfile",
        key: "nickname",
        value: "sk-proj-12345678901234567890",
        source: "explicit",
      }],
      recentPreferenceId: "global.nickname",
    }, store, warn)).toBe(false);
    expect(store.setItem).not.toHaveBeenCalled();
    expect(warn).toHaveBeenCalledWith(
      "[companion-preferences] Rejected sensitive preference state",
    );

    expect(writeCompanionPreferences({
      preferences: [],
      recentPreferenceId: "sk-proj-12345678901234567890",
    }, store, warn)).toBe(false);
    expect(store.setItem).toHaveBeenCalledTimes(0);
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
