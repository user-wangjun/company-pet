import { describe, expect, test } from "vitest";
import {
  PREVIEW_ACCOUNT_STORAGE_KEY,
  PREVIEW_SESSION_STORAGE_KEY,
  hasPreviewAccounts,
  loginPreviewAccount,
  logoutPreviewAccount,
  readPreviewSession,
  registerPreviewAccount,
  validateRegistrationInput,
  type PreviewAuthStorage,
} from "./previewAuth";

function createStorage(): PreviewAuthStorage {
  const values = new Map<string, string>();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
}

describe("preview account auth", () => {
  test("validates email, password length, and matching confirmation", () => {
    expect(validateRegistrationInput({ email: "bad", password: "password1", confirmPassword: "password1" })).toBe("请输入有效的邮箱地址");
    expect(validateRegistrationInput({ email: "user@example.com", password: "short", confirmPassword: "short" })).toBe("密码至少需要 8 个字符");
    expect(validateRegistrationInput({ email: "user@example.com", password: "password1", confirmPassword: "password2" })).toBe("两次输入的密码不一致");
    expect(validateRegistrationInput({ email: "user@example.com", password: "password1", confirmPassword: "password1" })).toBeNull();
  });

  test("registers and restores a local preview session without storing plaintext password", async () => {
    const storage = createStorage();
    const result = await registerPreviewAccount({
      email: " User@Example.com ",
      password: "password1",
      confirmPassword: "password1",
    }, storage);

    expect(result.ok).toBe(true);
    expect(hasPreviewAccounts(storage)).toBe(true);
    expect(readPreviewSession(storage)?.email).toBe("user@example.com");
    expect(storage.getItem(PREVIEW_ACCOUNT_STORAGE_KEY)).not.toContain("password1");
    expect(storage.getItem(PREVIEW_SESSION_STORAGE_KEY)).toContain("user@example.com");
  });

  test("logs in with the registered password and clears only the session on logout", async () => {
    const storage = createStorage();
    await registerPreviewAccount({
      email: "user@example.com",
      password: "password1",
      confirmPassword: "password1",
    }, storage);
    logoutPreviewAccount(storage);

    expect(readPreviewSession(storage)).toBeNull();
    expect((await loginPreviewAccount("user@example.com", "wrong-pass", storage)).ok).toBe(false);
    expect((await loginPreviewAccount("user@example.com", "password1", storage)).ok).toBe(true);
    expect(readPreviewSession(storage)?.emailVerified).toBe(false);
  });
});
