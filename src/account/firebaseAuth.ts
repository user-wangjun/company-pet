import { getApp, getApps, initializeApp, type FirebaseApp, type FirebaseOptions } from "firebase/app";
import {
  createUserWithEmailAndPassword,
  getAuth,
  onAuthStateChanged,
  reload,
  sendEmailVerification,
  signInWithEmailAndPassword,
  signOut,
  type Auth,
  type Unsubscribe,
  type User,
  type UserCredential,
} from "firebase/auth";
import { normalizeAccountEmail, validateRegistrationInput } from "./previewAuth";

const firebaseConfig: FirebaseOptions = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY ?? "",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ?? "",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID ?? "",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET ?? "",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID ?? "",
  appId: import.meta.env.VITE_FIREBASE_APP_ID ?? "",
};

const REQUIRED_CONFIG_KEYS: Array<keyof FirebaseOptions> = [
  "apiKey",
  "authDomain",
  "projectId",
  "appId",
];

export type FirebaseAuthUser = User;

export type FirebaseAccount = {
  provider: "firebase";
  uid: string;
  email: string;
  emailVerified: boolean;
  createdAt: string;
};

export type FirebaseAuthStage =
  | "create-user"
  | "send-verification"
  | "resend-verification"
  | "reload-verification"
  | "sign-in";

export type FirebaseAuthFailure = {
  ok: false;
  error: string;
  stage: FirebaseAuthStage;
  /** A sanitized Firebase error code, never the raw Firebase error object. */
  code: string;
};

export type FirebaseAuthResult =
  | { ok: true; account: FirebaseAccount; user: User }
  | FirebaseAuthFailure;

export type FirebaseVerificationResult =
  | { ok: true }
  | FirebaseAuthFailure;

function hasRequiredConfig(): boolean {
  return REQUIRED_CONFIG_KEYS.every((key) => {
    const value = firebaseConfig[key];
    return typeof value === "string" && value.trim().length > 0;
  });
}

export function isFirebaseAuthConfigured(): boolean {
  return hasRequiredConfig();
}

function getFirebaseApp(): FirebaseApp {
  if (!hasRequiredConfig()) {
    throw new Error("Firebase 尚未配置，请先设置 VITE_FIREBASE_* 环境变量");
  }

  return getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
}

export function getFirebaseAuth(): Auth | null {
  if (!hasRequiredConfig()) return null;
  return getAuth(getFirebaseApp());
}

export function subscribeToFirebaseAuth(
  onChange: (user: User | null) => void,
): Unsubscribe | null {
  const auth = getFirebaseAuth();
  return auth ? onAuthStateChanged(auth, onChange) : null;
}

export function toFirebaseAccount(user: User): FirebaseAccount {
  return {
    provider: "firebase",
    uid: user.uid,
    email: normalizeAccountEmail(user.email ?? ""),
    emailVerified: user.emailVerified,
    createdAt: user.metadata.creationTime ?? new Date().toISOString(),
  };
}

function firebaseErrorCode(error: unknown): string {
  if (!error || typeof error !== "object") return "";
  const code = (error as { code?: unknown }).code;
  return typeof code === "string" ? code : "";
}

export function getFirebaseErrorCode(error: unknown): string {
  const code = firebaseErrorCode(error).trim().toLowerCase();
  return /^auth\/[a-z0-9-]{1,80}$/.test(code) ? code : "unknown";
}

export function describeFirebaseError(error: unknown): string {
  switch (getFirebaseErrorCode(error)) {
    case "auth/email-already-in-use":
      return "该邮箱已经注册，请直接登录";
    case "auth/invalid-credential":
    case "auth/invalid-login-credentials":
    case "auth/user-not-found":
    case "auth/wrong-password":
      return "邮箱或密码不正确";
    case "auth/weak-password":
      return "密码强度不足，请使用至少 8 个字符";
    case "auth/invalid-email":
      return "请输入有效的邮箱地址";
    case "auth/operation-not-allowed":
      return "Firebase 尚未启用邮箱/密码登录，请在控制台开启该方式";
    case "auth/too-many-requests":
      return "请求过于频繁，Firebase 暂时限制了操作，请稍后再试；不会自动重试";
    case "auth/quota-exceeded":
      return "Firebase 邮件发送额度或项目配额已达到限制，请稍后再试；不会自动重试";
    case "auth/invalid-sender":
      return "Firebase 验证邮件的发件人配置无效，请检查 Authentication → Templates → Email address verification";
    case "auth/invalid-message-payload":
      return "Firebase 验证邮件模板配置无效，请检查 Authentication → Templates → Email address verification";
    case "auth/unauthorized-domain":
      return "当前网页地址未获 Firebase 授权，请在 Authentication → Settings → Authorized domains 中添加当前主机名；localhost 与 127.0.0.1 需要分别确认";
    case "auth/invalid-continue-uri":
      return "验证邮件的跳转地址无效，请检查是否存在过期或错误的自定义 continue URL";
    case "auth/network-request-failed":
      return "网络连接失败，请检查网络后重试";
    case "auth/invalid-api-key":
      return "Firebase Web 配置中的 API Key 无效，请从 Firebase 控制台重新核对 Web App 配置";
    case "auth/app-not-authorized":
      return "当前应用未获 Firebase 授权，请核对 Web App 配置和授权域名";
    case "auth/user-disabled":
      return "该账号已被 Firebase 禁用，请联系项目管理员处理";
    case "auth/requires-recent-login":
      return "为了保护账号，请重新登录后再操作";
    case "auth/missing-email":
      return "请输入邮箱地址";
    default:
      return "Firebase 账号服务暂时不可用，请稍后再试";
  }
}

function createFirebaseFailure(
  stage: FirebaseAuthStage,
  error: unknown,
  messageOverride?: string,
  codeOverride?: string,
): FirebaseAuthFailure {
  const code = codeOverride ?? getFirebaseErrorCode(error);
  if (import.meta.env.DEV) {
    // Deliberately log only the stage and sanitized code. Firebase errors may
    // carry request, account, or credential details in their message/object.
    console.warn(`[Firebase Auth] ${stage}: ${code}`);
  }
  return {
    ok: false,
    error: messageOverride ?? describeFirebaseError(error),
    stage,
    code,
  };
}

export async function registerFirebaseAccount(
  emailInput: string,
  password: string,
  confirmPassword: string,
): Promise<FirebaseAuthResult> {
  const validationError = validateRegistrationInput({ email: emailInput, password, confirmPassword });
  if (validationError) {
    return {
      ok: false,
      error: validationError,
      stage: "create-user",
      code: "client-validation",
    };
  }

  let auth: Auth | null;
  try {
    auth = getFirebaseAuth();
  } catch (error) {
    return createFirebaseFailure("create-user", error);
  }
  if (!auth) {
    return createFirebaseFailure(
      "create-user",
      new Error("Firebase 尚未配置"),
      "Firebase 尚未配置，请先设置 VITE_FIREBASE_* 环境变量",
      "configuration",
    );
  }

  let credentials: UserCredential;
  try {
    credentials = await createUserWithEmailAndPassword(
      auth,
      normalizeAccountEmail(emailInput),
      password,
    );
  } catch (error) {
    return createFirebaseFailure("create-user", error);
  }

  try {
    await sendEmailVerification(credentials.user);
  } catch (error) {
    return createFirebaseFailure("send-verification", error);
  }

  return {
    ok: true,
    user: credentials.user,
    account: toFirebaseAccount(credentials.user),
  };
}

export async function loginFirebaseAccount(
  emailInput: string,
  password: string,
): Promise<FirebaseAuthResult> {
  const email = normalizeAccountEmail(emailInput);
  if (!email || !password) {
    return {
      ok: false,
      error: "请输入邮箱和密码",
      stage: "sign-in",
      code: "client-validation",
    };
  }

  let auth: Auth | null;
  try {
    auth = getFirebaseAuth();
  } catch (error) {
    return createFirebaseFailure("sign-in", error);
  }
  if (!auth) {
    return createFirebaseFailure(
      "sign-in",
      new Error("Firebase 尚未配置"),
      "Firebase 尚未配置，请先设置 VITE_FIREBASE_* 环境变量",
      "configuration",
    );
  }

  try {
    const credentials = await signInWithEmailAndPassword(auth, email, password);
    return {
      ok: true,
      user: credentials.user,
      account: toFirebaseAccount(credentials.user),
    };
  } catch (error) {
    return createFirebaseFailure("sign-in", error);
  }
}

export async function resendFirebaseVerification(
  user: User,
): Promise<FirebaseVerificationResult> {
  try {
    await sendEmailVerification(user);
    return { ok: true };
  } catch (error) {
    return createFirebaseFailure("resend-verification", error);
  }
}

export async function refreshFirebaseAccount(
  user: User,
): Promise<FirebaseAuthResult> {
  try {
    await reload(user);
    return { ok: true, user, account: toFirebaseAccount(user) };
  } catch (error) {
    return createFirebaseFailure("reload-verification", error);
  }
}

export async function logoutFirebaseAccount(): Promise<void> {
  const auth = getFirebaseAuth();
  if (auth) await signOut(auth);
}
