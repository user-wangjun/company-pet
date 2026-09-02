import { beforeEach, describe, expect, test, vi } from "vitest";
import type { User } from "firebase/auth";

const firebaseMocks = vi.hoisted(() => ({
  app: { name: "firebase-test-app" },
  auth: { name: "firebase-test-auth" },
  getApp: vi.fn(),
  getApps: vi.fn(),
  initializeApp: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  getAuth: vi.fn(),
  onAuthStateChanged: vi.fn(),
  reload: vi.fn(),
  sendEmailVerification: vi.fn(),
  signInWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("firebase/app", () => ({
  getApp: firebaseMocks.getApp,
  getApps: firebaseMocks.getApps,
  initializeApp: firebaseMocks.initializeApp,
}));

vi.mock("firebase/auth", () => ({
  createUserWithEmailAndPassword: firebaseMocks.createUserWithEmailAndPassword,
  getAuth: firebaseMocks.getAuth,
  onAuthStateChanged: firebaseMocks.onAuthStateChanged,
  reload: firebaseMocks.reload,
  sendEmailVerification: firebaseMocks.sendEmailVerification,
  signInWithEmailAndPassword: firebaseMocks.signInWithEmailAndPassword,
  signOut: firebaseMocks.signOut,
}));

for (const key of [
  "VITE_FIREBASE_API_KEY",
  "VITE_FIREBASE_AUTH_DOMAIN",
  "VITE_FIREBASE_PROJECT_ID",
  "VITE_FIREBASE_STORAGE_BUCKET",
  "VITE_FIREBASE_MESSAGING_SENDER_ID",
  "VITE_FIREBASE_APP_ID",
]) {
  vi.stubEnv(key, `test-${key.toLowerCase()}`);
}

const {
  describeFirebaseError,
  getFirebaseErrorCode,
  refreshFirebaseAccount,
  registerFirebaseAccount,
  resendFirebaseVerification,
} = await import("./firebaseAuth");

function createUser(emailVerified = false): User {
  return {
    uid: "firebase-test-user",
    email: "Test.User@Example.com",
    emailVerified,
    metadata: { creationTime: "2026-08-21T00:00:00.000Z" },
  } as User;
}

beforeEach(() => {
  vi.clearAllMocks();
  firebaseMocks.getApps.mockReturnValue([]);
  firebaseMocks.initializeApp.mockReturnValue(firebaseMocks.app);
  firebaseMocks.getApp.mockReturnValue(firebaseMocks.app);
  firebaseMocks.getAuth.mockReturnValue(firebaseMocks.auth);
  firebaseMocks.sendEmailVerification.mockResolvedValue(undefined);
  firebaseMocks.reload.mockResolvedValue(undefined);
});

describe("firebaseAuth verification flow", () => {
  test("registers through Firebase and sends the verification request", async () => {
    const user = createUser();
    firebaseMocks.createUserWithEmailAndPassword.mockResolvedValue({ user });

    const result = await registerFirebaseAccount(
      " Test.User@Example.com ",
      "password-for-test",
      "password-for-test",
    );

    expect(firebaseMocks.createUserWithEmailAndPassword).toHaveBeenCalledWith(
      firebaseMocks.auth,
      "test.user@example.com",
      "password-for-test",
    );
    expect(firebaseMocks.sendEmailVerification).toHaveBeenCalledWith(user);
    expect(result).toMatchObject({
      ok: true,
      account: { provider: "firebase", email: "test.user@example.com", emailVerified: false },
    });
  });

  test("keeps the send-verification stage when account creation succeeds but email sending fails", async () => {
    const user = createUser();
    firebaseMocks.createUserWithEmailAndPassword.mockResolvedValue({ user });
    firebaseMocks.sendEmailVerification.mockRejectedValue({
      code: "auth/unauthorized-domain",
      message: "secret-email@example.com apiKey=secret-api-key token=secret-token",
    });

    const result = await registerFirebaseAccount(
      "user@example.com",
      "password-for-test",
      "password-for-test",
    );

    expect(result).toMatchObject({
      ok: false,
      stage: "send-verification",
      code: "auth/unauthorized-domain",
    });
    if (result.ok) throw new Error("expected send-verification to fail");
    expect(result.error).toContain("授权");
    expect(result.error).not.toContain("secret-email@example.com");
    expect(result.error).not.toContain("secret-api-key");
    expect(result.error).not.toContain("secret-token");
  });

  test("resends through the same Firebase sendEmailVerification API", async () => {
    const user = createUser();

    const result = await resendFirebaseVerification(user);

    expect(firebaseMocks.sendEmailVerification).toHaveBeenCalledTimes(1);
    expect(firebaseMocks.sendEmailVerification).toHaveBeenCalledWith(user);
    expect(result).toEqual({ ok: true });
  });

  test("reports resend rate limiting with its own stage and no automatic retry", async () => {
    const user = createUser();
    firebaseMocks.sendEmailVerification.mockRejectedValue({ code: "auth/too-many-requests" });

    const result = await resendFirebaseVerification(user);

    expect(result).toMatchObject({
      ok: false,
      stage: "resend-verification",
      code: "auth/too-many-requests",
    });
    if (result.ok) throw new Error("expected resend-verification to fail");
    expect(result.error).toContain("稍后再试");
    expect(firebaseMocks.sendEmailVerification).toHaveBeenCalledTimes(1);
  });

  test("reloads the Firebase user before deciding that verification is complete", async () => {
    const user = createUser(false);
    firebaseMocks.reload.mockImplementation(async (candidate: User) => {
      (candidate as unknown as { emailVerified: boolean }).emailVerified = true;
    });

    const result = await refreshFirebaseAccount(user);

    expect(firebaseMocks.reload).toHaveBeenCalledWith(user);
    expect(result).toMatchObject({
      ok: true,
      account: { email: "test.user@example.com", emailVerified: true },
    });
  });
});

describe("firebase error diagnostics", () => {
  test.each([
    ["auth/operation-not-allowed", "未启用邮箱/密码"],
    ["auth/email-already-in-use", "已经注册"],
    ["auth/invalid-email", "有效的邮箱"],
    ["auth/weak-password", "密码强度不足"],
    ["auth/too-many-requests", "请求过于频繁"],
    ["auth/quota-exceeded", "邮件发送额度"],
    ["auth/invalid-sender", "发件人配置"],
    ["auth/invalid-message-payload", "邮件模板配置"],
    ["auth/unauthorized-domain", "网页地址未获 Firebase 授权"],
    ["auth/invalid-continue-uri", "跳转地址无效"],
    ["auth/network-request-failed", "网络连接失败"],
    ["auth/invalid-api-key", "API Key 无效"],
    ["auth/app-not-authorized", "应用未获 Firebase 授权"],
    ["auth/user-disabled", "账号已被 Firebase 禁用"],
  ])("maps %s to an actionable Chinese message", (code, expectedMessage) => {
    expect(describeFirebaseError({ code })).toContain(expectedMessage);
  });

  test("keeps unknown Firebase errors generic and exposes only a sanitized code", () => {
    const secret = "password=secret apiKey=secret-key token=secret-token user@example.com";
    const error = { code: "auth/custom-diagnostic-code", message: secret };

    expect(getFirebaseErrorCode(error)).toBe("auth/custom-diagnostic-code");
    expect(describeFirebaseError(error)).toBe("Firebase 账号服务暂时不可用，请稍后再试");
    expect(describeFirebaseError(error)).not.toContain(secret);
    expect(getFirebaseErrorCode({ code: secret })).toBe("unknown");
  });
});
