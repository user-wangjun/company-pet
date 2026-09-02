// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { AccountGate } from "./AccountGate";
import type { FirebaseAccount, FirebaseAuthUser } from "./firebaseAuth";

const firebaseMocks = vi.hoisted(() => ({
  isFirebaseAuthConfigured: vi.fn(() => true),
  loginFirebaseAccount: vi.fn(),
  logoutFirebaseAccount: vi.fn(),
  refreshFirebaseAccount: vi.fn(),
  registerFirebaseAccount: vi.fn(),
  resendFirebaseVerification: vi.fn(),
  subscribeToFirebaseAuth: vi.fn(),
  toFirebaseAccount: vi.fn(),
}));

vi.mock("./firebaseAuth", () => firebaseMocks);

function createUser(emailVerified = false): FirebaseAuthUser {
  return {
    uid: "account-gate-test-user",
    email: "user@example.com",
    emailVerified,
    metadata: { creationTime: "2026-08-21T00:00:00.000Z" },
  } as unknown as FirebaseAuthUser;
}

function createAccount(user: FirebaseAuthUser): FirebaseAccount {
  return {
    provider: "firebase",
    uid: user.uid,
    email: user.email ?? "",
    emailVerified: user.emailVerified,
    createdAt: user.metadata.creationTime ?? "2026-08-21T00:00:00.000Z",
  };
}

function findButton(container: HTMLElement, text: string): HTMLButtonElement {
  const button = [...container.querySelectorAll("button")]
    .find((candidate) => {
      const label = candidate.textContent?.trim();
      return label === text
        || label === `✦${text}`
        || label === `回${text}`
        || label === `${text}→`;
    });
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error(`button not found: ${text}`);
  }
  return button;
}

async function click(button: HTMLButtonElement): Promise<void> {
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await Promise.resolve();
  });
}

async function submitForm(container: HTMLElement): Promise<void> {
  const form = container.querySelector("form");
  if (!form) throw new Error("account form not found");

  await act(async () => {
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await Promise.resolve();
  });
}

describe("AccountGate Firebase verification UI", () => {
  let container: HTMLDivElement;
  let root: Root;
  let authStateCallback: ((user: FirebaseAuthUser | null) => void) | null;

  beforeEach(() => {
    vi.clearAllMocks();
    firebaseMocks.isFirebaseAuthConfigured.mockReturnValue(true);
    authStateCallback = null;
    firebaseMocks.subscribeToFirebaseAuth.mockImplementation((callback) => {
      authStateCallback = callback as (user: FirebaseAuthUser | null) => void;
      return vi.fn();
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  async function renderGate(): Promise<void> {
    await act(async () => {
      root.render(
        <AccountGate>
          <div data-testid="signed-in">已进入桌宠</div>
        </AccountGate>,
      );
    });
  }

  async function registerWithResult(result: unknown): Promise<FirebaseAuthUser> {
    const user = createUser();
    const account = createAccount(user);
    firebaseMocks.registerFirebaseAccount.mockResolvedValue(result ?? {
      ok: true,
      user,
      account,
    });

    await renderGate();
    await click(findButton(container, "注册"));
    await submitForm(container);
    return user;
  }

  test("shows the verification page only after the Firebase registration request succeeds", async () => {
    const user = createUser();
    const account = createAccount(user);
    firebaseMocks.registerFirebaseAccount.mockResolvedValue({ ok: true, user, account });

    await renderGate();
    await click(findButton(container, "注册"));
    await submitForm(container);

    expect(firebaseMocks.registerFirebaseAccount).toHaveBeenCalledTimes(1);
    expect(firebaseMocks.resendFirebaseVerification).not.toHaveBeenCalled();
    expect(container.textContent).toContain("请验证你的邮箱");
    expect(container.textContent).toContain("Firebase 已接受发送请求，请检查收件箱、垃圾邮件和广告邮件。");
    expect(container.textContent).not.toContain("已送达");
  });

  test("shows the send-verification error instead of claiming that mail was sent", async () => {
    await registerWithResult({
      ok: false,
      error: "当前网页地址未获 Firebase 授权，请检查授权域名",
      stage: "send-verification",
      code: "auth/unauthorized-domain",
    });

    expect(container.querySelector("[role=alert]")?.textContent).toContain("授权域名");
    expect(container.textContent).not.toContain("请验证你的邮箱");
  });

  test("does not let the auth observer open verification UI before a failed send resolves", async () => {
    const user = createUser();
    firebaseMocks.registerFirebaseAccount.mockImplementation(async () => {
      authStateCallback?.(user);
      return {
        ok: false,
        error: "验证邮件请求失败",
        stage: "send-verification",
        code: "auth/invalid-sender",
      };
    });

    await renderGate();
    await click(findButton(container, "注册"));
    await submitForm(container);

    expect(container.textContent).not.toContain("请验证你的邮箱");
    expect(container.querySelector("[role=alert]")?.textContent).toContain("验证邮件请求失败");
  });

  test("resends on click, shows the accepted-request message, and starts a 60 second cooldown", async () => {
    const user = await registerWithResult(null);
    firebaseMocks.resendFirebaseVerification.mockResolvedValue({ ok: true });

    await click(findButton(container, "重新发送验证邮件"));

    expect(firebaseMocks.resendFirebaseVerification).toHaveBeenCalledWith(user);
    expect(container.textContent).toContain("Firebase 已接受发送请求，请检查收件箱、垃圾邮件和广告邮件。");
    expect(container.textContent).toContain("请等待 60 秒后重试");
    expect(findButton(container, "请等待 60 秒后重试").disabled).toBe(true);
  });

  test("shows rate limiting, does not retry automatically, and keeps the resend cooldown", async () => {
    await registerWithResult(null);
    firebaseMocks.resendFirebaseVerification.mockResolvedValue({
      ok: false,
      error: "请求过于频繁，Firebase 暂时限制了操作，请稍后再试；不会自动重试",
      stage: "resend-verification",
      code: "auth/too-many-requests",
    });

    await click(findButton(container, "重新发送验证邮件"));

    expect(firebaseMocks.resendFirebaseVerification).toHaveBeenCalledTimes(1);
    expect(container.querySelector("[role=alert]")?.textContent).toContain("稍后再试");
    expect(container.textContent).toContain("不会自动重试");
    expect(container.textContent).toContain("请等待 60 秒后重试");
  });

  test("uses reload result to enter the app only after emailVerified becomes true", async () => {
    const user = await registerWithResult(null);
    const verifiedAccount = createAccount({ ...user, emailVerified: true });
    firebaseMocks.refreshFirebaseAccount.mockResolvedValue({
      ok: true,
      user,
      account: verifiedAccount,
    });

    await click(findButton(container, "我已完成验证"));

    expect(firebaseMocks.refreshFirebaseAccount).toHaveBeenCalledWith(user);
    expect(container.querySelector("[data-testid=signed-in]")?.textContent).toBe("已进入桌宠");
  });
});
