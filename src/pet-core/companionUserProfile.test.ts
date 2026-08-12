import { describe, expect, test, vi } from "vitest";
import {
  COMPANION_USER_PROFILE_STORAGE_KEY,
  EMPTY_COMPANION_USER_PROFILE,
  parseCompanionUserProfile,
  readCompanionUserProfile,
  validateCompanionUserProfile,
  writeCompanionUserProfile,
} from "./companionUserProfile";

function storage(initial: string | null = null) {
  let value = initial;
  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((_key: string, next: string) => {
      value = next;
    }),
  };
}

describe("companion user profile", () => {
  test("validates and round-trips local profile fields", () => {
    const store = storage();
    const profile = {
      nickname: "阿星",
      gender: "prefer-not-to-say" as const,
      email: "hello@example.com",
      phone: "+86 138 0000 0000",
    };

    expect(validateCompanionUserProfile(profile)).toBeNull();
    expect(writeCompanionUserProfile(profile, store, vi.fn())).toBe(true);
    expect(store.setItem).toHaveBeenCalledWith(
      COMPANION_USER_PROFILE_STORAGE_KEY,
      JSON.stringify(profile),
    );
    expect(readCompanionUserProfile(store, vi.fn())).toEqual(profile);
  });

  test("rejects malformed contact fields without exposing their values", () => {
    expect(validateCompanionUserProfile({
      ...EMPTY_COMPANION_USER_PROFILE,
      email: "not-an-email",
    })).toBe("邮箱格式不正确。");
    expect(validateCompanionUserProfile({
      ...EMPTY_COMPANION_USER_PROFILE,
      phone: "123",
    })).toBe("电话格式不正确。");

    const warn = vi.fn();
    const store = storage();
    expect(writeCompanionUserProfile({
      ...EMPTY_COMPANION_USER_PROFILE,
      nickname: "sk-proj-profile-test-value",
    }, store, warn)).toBe(false);
    expect(warn).toHaveBeenCalledWith(
      "[companion-user-profile] Rejected invalid local profile",
    );
    expect(store.setItem).not.toHaveBeenCalled();
    expect(JSON.stringify(warn.mock.calls)).not.toContain("sk-proj-profile-test-value");
  });

  test("fails closed for malformed stored data", () => {
    expect(parseCompanionUserProfile("not-json")).toEqual(EMPTY_COMPANION_USER_PROFILE);
    expect(parseCompanionUserProfile(JSON.stringify({
      nickname: "阿星",
      gender: "unknown",
      email: "hello@example.com",
      phone: "+86 138 0000 0000",
    }))).toEqual(EMPTY_COMPANION_USER_PROFILE);
  });
});
