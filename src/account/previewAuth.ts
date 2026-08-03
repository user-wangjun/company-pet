export const PREVIEW_ACCOUNT_STORAGE_KEY = "yuxin.preview-accounts.v1";
export const PREVIEW_SESSION_STORAGE_KEY = "yuxin.preview-session.v1";

const PASSWORD_HASH_ITERATIONS = 120_000;

export type PreviewAccount = {
  email: string;
  emailVerified: boolean;
  createdAt: string;
  passwordSalt: string;
  passwordHash: string;
  passwordHashIterations: number;
};

type PreviewAccountStore = {
  schemaVersion: 1;
  accounts: PreviewAccount[];
};

export type PreviewSession = {
  email: string;
  signedInAt: string;
};

export type PreviewAuthStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export type RegisterPreviewAccountInput = {
  email: string;
  password: string;
  confirmPassword: string;
};

export type PreviewAuthResult =
  | { ok: true; account: PreviewAccount }
  | { ok: false; error: string };

function browserStorage(): PreviewAuthStorage | null {
  if (typeof window === "undefined") return null;

  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function normalizeAccountEmail(email: string): string {
  return email.trim().toLowerCase();
}

export function validateRegistrationInput(input: RegisterPreviewAccountInput): string | null {
  const email = normalizeAccountEmail(input.email);
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return "请输入有效的邮箱地址";
  if (input.password.length < 8) return "密码至少需要 8 个字符";
  if (input.password !== input.confirmPassword) return "两次输入的密码不一致";
  return null;
}

function readAccountStore(storage: PreviewAuthStorage | null = browserStorage()): PreviewAccountStore {
  if (!storage) return { schemaVersion: 1, accounts: [] };

  try {
    const parsed = JSON.parse(storage.getItem(PREVIEW_ACCOUNT_STORAGE_KEY) ?? "") as Partial<PreviewAccountStore>;
    if (parsed.schemaVersion !== 1 || !Array.isArray(parsed.accounts)) {
      return { schemaVersion: 1, accounts: [] };
    }

    return {
      schemaVersion: 1,
      accounts: parsed.accounts.filter((account): account is PreviewAccount => (
        typeof account?.email === "string"
        && typeof account?.passwordHash === "string"
        && typeof account?.passwordSalt === "string"
        && typeof account?.passwordHashIterations === "number"
      )),
    };
  } catch {
    return { schemaVersion: 1, accounts: [] };
  }
}

function writeAccountStore(store: PreviewAccountStore, storage: PreviewAuthStorage): void {
  storage.setItem(PREVIEW_ACCOUNT_STORAGE_KEY, JSON.stringify(store));
}

function bytesToHex(bytes: Uint8Array): string {
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function hexToBytes(value: string): Uint8Array<ArrayBuffer> {
  const bytes = new Uint8Array(value.length / 2);
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = Number.parseInt(value.slice(index * 2, index * 2 + 2), 16);
  }
  return bytes;
}

async function hashPassword(
  password: string,
  salt: string,
  iterations: number,
  cryptoApi: Crypto,
): Promise<string> {
  const passwordKey = await cryptoApi.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = await cryptoApi.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt: hexToBytes(salt), iterations },
    passwordKey,
    256,
  );
  return bytesToHex(new Uint8Array(bits));
}

function writeSession(account: PreviewAccount, storage: PreviewAuthStorage): void {
  const session: PreviewSession = {
    email: account.email,
    signedInAt: new Date().toISOString(),
  };
  storage.setItem(PREVIEW_SESSION_STORAGE_KEY, JSON.stringify(session));
}

export function hasPreviewAccounts(storage: PreviewAuthStorage | null = browserStorage()): boolean {
  return readAccountStore(storage).accounts.length > 0;
}

export function readPreviewSession(storage: PreviewAuthStorage | null = browserStorage()): PreviewAccount | null {
  if (!storage) return null;

  try {
    const session = JSON.parse(storage.getItem(PREVIEW_SESSION_STORAGE_KEY) ?? "") as Partial<PreviewSession>;
    if (typeof session.email !== "string") return null;
    return readAccountStore(storage).accounts.find((account) => account.email === session.email) ?? null;
  } catch {
    return null;
  }
}

export async function registerPreviewAccount(
  input: RegisterPreviewAccountInput,
  storage: PreviewAuthStorage | null = browserStorage(),
  cryptoApi: Crypto | undefined = globalThis.crypto,
): Promise<PreviewAuthResult> {
  const validationError = validateRegistrationInput(input);
  if (validationError) return { ok: false, error: validationError };
  if (!storage || !cryptoApi?.subtle) return { ok: false, error: "当前环境无法安全保存预览账号" };

  const email = normalizeAccountEmail(input.email);
  const store = readAccountStore(storage);
  if (store.accounts.some((account) => account.email === email)) {
    return { ok: false, error: "该邮箱已经注册，请直接登录" };
  }

  const saltBytes = new Uint8Array(16);
  cryptoApi.getRandomValues(saltBytes);
  const passwordSalt = bytesToHex(saltBytes);
  const account: PreviewAccount = {
    email,
    emailVerified: false,
    createdAt: new Date().toISOString(),
    passwordSalt,
    passwordHash: await hashPassword(input.password, passwordSalt, PASSWORD_HASH_ITERATIONS, cryptoApi),
    passwordHashIterations: PASSWORD_HASH_ITERATIONS,
  };

  writeAccountStore({ ...store, accounts: [...store.accounts, account] }, storage);
  writeSession(account, storage);
  return { ok: true, account };
}

export async function loginPreviewAccount(
  emailInput: string,
  password: string,
  storage: PreviewAuthStorage | null = browserStorage(),
  cryptoApi: Crypto | undefined = globalThis.crypto,
): Promise<PreviewAuthResult> {
  if (!storage || !cryptoApi?.subtle) return { ok: false, error: "当前环境无法读取预览账号" };
  const email = normalizeAccountEmail(emailInput);
  const account = readAccountStore(storage).accounts.find((candidate) => candidate.email === email);
  if (!account || !password) return { ok: false, error: "邮箱或密码不正确" };

  const passwordHash = await hashPassword(
    password,
    account.passwordSalt,
    account.passwordHashIterations,
    cryptoApi,
  );
  if (passwordHash !== account.passwordHash) return { ok: false, error: "邮箱或密码不正确" };

  writeSession(account, storage);
  return { ok: true, account };
}

export function logoutPreviewAccount(storage: PreviewAuthStorage | null = browserStorage()): void {
  storage?.removeItem(PREVIEW_SESSION_STORAGE_KEY);
}
