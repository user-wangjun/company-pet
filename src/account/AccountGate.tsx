import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import {
  loginPreviewAccount,
  logoutPreviewAccount,
  readPreviewSession,
  registerPreviewAccount,
  type PreviewAccount,
} from "./previewAuth";
import {
  isFirebaseAuthConfigured,
  loginFirebaseAccount,
  logoutFirebaseAccount,
  refreshFirebaseAccount,
  registerFirebaseAccount,
  resendFirebaseVerification,
  subscribeToFirebaseAuth,
  toFirebaseAccount,
  type FirebaseAccount,
  type FirebaseAuthUser,
} from "./firebaseAuth";
import type { AccountPetMood } from "./accountPetParameters";
import { AccountPetPuppet } from "./AccountPetPuppet";
import "./account.css";

type AuthMode = "login" | "register";
type RegistrationAuthState = "idle" | "pending" | "sent" | "failed";

const RESEND_COOLDOWN_SECONDS = 60;
const VERIFICATION_REQUEST_ACCEPTED_MESSAGE =
  "Firebase 已接受发送请求，请检查收件箱、垃圾邮件和广告邮件。";

type AccountContextValue = {
  account: PreviewAccount | FirebaseAccount;
  signOut: () => void;
};

const PET_EYE_ANCHORS = {
  left: { x: 203.5 / 555, y: 276 / 775 },
  right: { x: 318.5 / 555, y: 276 / 775 },
} as const;

const PET_EYE_GEOMETRY = {
  eyeWidth: 67 / 555,
  eyeHeight: 72 / 775,
  pupilWidth: 29 / 555,
  pupilHeight: 44 / 775,
} as const;

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));

const AccountContext = createContext<AccountContextValue | null>(null);

export function useAccountSession(): AccountContextValue {
  const context = useContext(AccountContext);
  if (!context) throw new Error("useAccountSession must be used inside AccountGate");
  return context;
}

export function AccountGate({ children }: { children: ReactNode }) {
  const firebaseAuthEnabled = isFirebaseAuthConfigured();
  const introRef = useRef<HTMLElement>(null);
  const registrationAuthStateRef = useRef<RegistrationAuthState>("idle");
  const [account, setAccount] = useState<PreviewAccount | FirebaseAccount | null>(
    () => firebaseAuthEnabled ? null : readPreviewSession(),
  );
  const [pendingVerificationUser, setPendingVerificationUser] = useState<FirebaseAuthUser | null>(null);
  const [verificationMessage, setVerificationMessage] = useState<string | null>(null);
  const [resendCooldownSeconds, setResendCooldownSeconds] = useState(0);
  const [mode, setMode] = useState<AuthMode>(
    () => "login",
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [petMood, setPetMood] = useState<AccountPetMood>("idle");

  useEffect(() => {
    if (!firebaseAuthEnabled) return;

    const unsubscribe = subscribeToFirebaseAuth((user) => {
      if (!user) {
        setAccount(null);
        setPendingVerificationUser(null);
        return;
      }

      if (user.emailVerified) {
        registrationAuthStateRef.current = "idle";
        setAccount(toFirebaseAccount(user));
        setPendingVerificationUser(null);
        setVerificationMessage(null);
      } else {
        setAccount(null);
        // createUserWithEmailAndPassword changes Firebase's current user
        // before sendEmailVerification resolves. Do not show the verification
        // screen from the auth observer until the explicit send request has
        // succeeded; otherwise a failed send can look like a delivered mail.
        if (
          registrationAuthStateRef.current === "pending"
          || registrationAuthStateRef.current === "failed"
        ) {
          return;
        }
        setPendingVerificationUser(user);
      }
    });

    return () => unsubscribe?.();
  }, [firebaseAuthEnabled]);

  useEffect(() => {
    if (resendCooldownSeconds <= 0) return;

    const timeoutId = window.setTimeout(() => {
      setResendCooldownSeconds((seconds) => Math.max(0, seconds - 1));
    }, 1000);

    return () => window.clearTimeout(timeoutId);
  }, [resendCooldownSeconds]);

  const handlePetClick = () => {
    // Optional interactive response if needed
  };

  const movePetGaze = (event: ReactPointerEvent<HTMLElement>) => {
    const intro = introRef.current;
    if (!intro) return;
    if (event.pointerType === "touch") return;
    const pet = intro.querySelector<HTMLElement>(".account-layered-pet");
    if (!pet) return;

    const interactionBounds = event.currentTarget.getBoundingClientRect();
    const petBounds = pet.getBoundingClientRect();
    // Use the whole account surface as the gaze field. The pet is in the
    // left scene, but the pointer can be anywhere over the right card too;
    // basing the radius only on the pet made that entire area clamp to one
    // direction (or never reach this handler before it was moved to <main>).
    const focusRadiusX = Math.max(100, petBounds.width * 0.62, interactionBounds.width * 0.42);
    const focusRadiusY = Math.max(58, petBounds.height * 0.18, interactionBounds.height * 0.5);
    const pupilTravelX = Math.min(
      4.5,
      Math.max(1, petBounds.width * (PET_EYE_GEOMETRY.eyeWidth - PET_EYE_GEOMETRY.pupilWidth) / 2),
    );
    const pupilTravelY = Math.min(
      3.5,
      Math.max(1, petBounds.height * (PET_EYE_GEOMETRY.eyeHeight - PET_EYE_GEOMETRY.pupilHeight) / 2),
    );

    for (const [side, anchor] of Object.entries(PET_EYE_ANCHORS)) {
      const eyeX = petBounds.left + petBounds.width * anchor.x;
      const eyeY = petBounds.top + petBounds.height * anchor.y;
      const normalizedX = (event.clientX - eyeX) / focusRadiusX;
      const normalizedY = (event.clientY - eyeY) / focusRadiusY;
      const normalizedDistance = Math.hypot(normalizedX, normalizedY);
      const radialScale = normalizedDistance > 1 ? 1 / normalizedDistance : 1;
      const pupilX = clamp(normalizedX * radialScale * pupilTravelX, -pupilTravelX, pupilTravelX);
      const pupilY = clamp(normalizedY * radialScale * pupilTravelY, -pupilTravelY, pupilTravelY);
      intro.style.setProperty(`--pupil-${side}-x`, `${pupilX}px`);
      intro.style.setProperty(`--pupil-${side}-y`, `${pupilY}px`);
    }

    intro.classList.add("has-pet-gaze");
  };

  const resetPetGaze = () => {
    const intro = introRef.current;
    if (!intro) return;
    intro.style.setProperty("--pupil-left-x", "0px");
    intro.style.setProperty("--pupil-left-y", "0px");
    intro.style.setProperty("--pupil-right-x", "0px");
    intro.style.setProperty("--pupil-right-y", "0px");
    intro.classList.remove("has-pet-gaze");
  };

  const switchMode = (nextMode: AuthMode) => {
    if (firebaseAuthEnabled && pendingVerificationUser) {
      void logoutFirebaseAccount();
    }
    registrationAuthStateRef.current = "idle";
    setMode(nextMode);
    setPetMood("idle");
    setPassword("");
    setConfirmPassword("");
    setError(null);
    setVerificationMessage(null);
    setResendCooldownSeconds(0);
    setPendingVerificationUser(null);
  };

  const checkFirebaseVerification = async () => {
    if (!pendingVerificationUser || submitting) return;
    setSubmitting(true);
    setError(null);
    const result = await refreshFirebaseAccount(pendingVerificationUser);
    setSubmitting(false);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    if (!result.account.emailVerified) {
      setError("还没有检测到验证完成，请先点击邮件中的验证链接");
      return;
    }

    setPendingVerificationUser(null);
    setVerificationMessage(null);
    setResendCooldownSeconds(0);
    setAccount(result.account);
  };

  const resendFirebaseVerificationEmail = async () => {
    if (!pendingVerificationUser || submitting || resendCooldownSeconds > 0) return;
    setSubmitting(true);
    setError(null);
    setVerificationMessage(null);
    const result = await resendFirebaseVerification(pendingVerificationUser);
    setSubmitting(false);

    if (!result.ok) {
      if (result.code === "auth/too-many-requests" || result.code === "auth/quota-exceeded") {
        setResendCooldownSeconds(RESEND_COOLDOWN_SECONDS);
      }
      setError(result.error);
      return;
    }

    setResendCooldownSeconds(RESEND_COOLDOWN_SECONDS);
    setVerificationMessage(VERIFICATION_REQUEST_ACCEPTED_MESSAGE);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);

    if (firebaseAuthEnabled) {
      if (mode === "register") {
        registrationAuthStateRef.current = "pending";
      }
      const result = mode === "register"
        ? await registerFirebaseAccount(email, password, confirmPassword)
        : await loginFirebaseAccount(email, password);

      if (mode === "register") {
        registrationAuthStateRef.current = result.ok ? "sent" : "failed";
      }

      setSubmitting(false);
      if (!result.ok) {
        setError(result.error);
        return;
      }

      setPassword("");
      setConfirmPassword("");
      if (!result.account.emailVerified) {
        setPendingVerificationUser(result.user);
        setResendCooldownSeconds(0);
        setVerificationMessage(VERIFICATION_REQUEST_ACCEPTED_MESSAGE);
        return;
      }

      setAccount(result.account);
      return;
    }

    const result = mode === "register"
      ? await registerPreviewAccount({ email, password, confirmPassword })
      : await loginPreviewAccount(email, password);

    setSubmitting(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }

    setPassword("");
    setConfirmPassword("");
    setAccount(result.account);
  };

  if (account) {
    return (
      <AccountContext.Provider
        value={{
          account,
          signOut: () => {
            if (firebaseAuthEnabled) {
              void logoutFirebaseAccount();
            } else {
              logoutPreviewAccount();
            }
            registrationAuthStateRef.current = "idle";
            setAccount(null);
            setMode("login");
          },
        }}
      >
        {children}
      </AccountContext.Provider>
    );
  }

  return (
    <main
      className="account-gate"
      onPointerMove={movePetGaze}
      onPointerLeave={resetPetGaze}
    >
      <section
        className={`account-intro is-${petMood}-mood`}
        aria-label="愈心桌宠陪伴入口"
        ref={introRef}
      >
        {/* Warm desk scene with a small, responsive universe of its own. */}
        <AccountPetPuppet
          mood={petMood}
          onPetClick={handlePetClick}
        />

        <div className="account-brand">
          <div className="account-brand-mark" aria-hidden="true">✦</div>
          <div>
            <strong>愈心桌宠</strong>
            <span>YUXIN DESKTOP PET</span>
          </div>
        </div>

        <div className="account-intro-copy">
          <span>A QUIET DESK FOR TWO</span>
          <h1>回到桌边，<br />小橘在灯下等你</h1>
          <p>登录后，继续你的桌面陪伴。</p>
        </div>

        <div className="account-stage-footer" aria-hidden="true">
          <span className="account-live-indicator-dot" />
          <span>小橘在灯下等你</span>
        </div>
      </section>

      <section className="account-card" aria-labelledby="account-title">
        <div className="account-card-paw" aria-hidden="true"><i /><i /><i /><i /></div>
        <div className="account-mode-switch" aria-label="账号操作">
          <button className={mode === "login" ? "is-active" : ""} type="button" onClick={() => switchMode("login")}><span aria-hidden="true">回</span>登录</button>
          <button className={mode === "register" ? "is-active" : ""} type="button" onClick={() => switchMode("register")}><span aria-hidden="true">✦</span>注册</button>
        </div>

        <header>
          <p><span>{mode === "login" ? "WELCOME HOME" : "A NEW FRIEND"}</span>{mode === "login" ? "回到小橘身边" : firebaseAuthEnabled ? "创建账号" : "创建预览账号"}</p>
          <h2 id="account-title">{mode === "login" ? "回到小橘身边" : "第一次见面，请多关照"}</h2>
          <p className="account-card-lede">
            {mode === "login" ? "登录后继续被小橘陪伴。" : "创建账号，给自己留一块温柔的桌面空间。"}
          </p>
        </header>

        {pendingVerificationUser ? (
          <div className="account-verification-pending" aria-label="邮箱验证">
            <p className="account-verification-kicker">CHECK YOUR INBOX</p>
            <h3>请验证你的邮箱</h3>
            <p>我们已经把验证链接发送到：</p>
            <strong>{pendingVerificationUser.email}</strong>
            <p>点击邮件中的链接后，回到这里刷新验证状态即可进入桌宠。</p>
            {verificationMessage && <p className="account-verification-message">{verificationMessage}</p>}
            {error && <p className="account-error" role="alert">{error}</p>}
            <button className="account-submit" disabled={submitting} type="button" onClick={() => void checkFirebaseVerification()}>
              <span>{submitting ? "检查中…" : "我已完成验证"}</span>
              {!submitting && <i aria-hidden="true">→</i>}
            </button>
            <button
              className="account-verification-resend"
              disabled={submitting || resendCooldownSeconds > 0}
              type="button"
              onClick={() => void resendFirebaseVerificationEmail()}
            >
              {resendCooldownSeconds > 0
                ? `请等待 ${resendCooldownSeconds} 秒后重试`
                : "重新发送验证邮件"}
            </button>
          </div>
        ) : (
        <form onSubmit={submit}>
          <label>
            <span>邮箱</span>
            <input
              autoComplete="email"
              inputMode="email"
              placeholder="name@example.com"
              required
              type="email"
              value={email}
              onPointerDown={() => setPetMood("email")}
              onFocus={() => setPetMood("email")}
              onBlur={() => setPetMood("idle")}
              onChange={(event) => setEmail(event.currentTarget.value)}
            />
          </label>
          <label>
            <span>密码</span>
            <input
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              minLength={8}
              placeholder={mode === "register" ? "至少 8 个字符" : "请输入密码"}
              required
              type="password"
              value={password}
              onPointerDown={() => setPetMood("password")}
              onFocus={() => setPetMood("password")}
              onBlur={() => setPetMood("idle")}
              onChange={(event) => setPassword(event.currentTarget.value)}
            />
          </label>
          {mode === "register" && firebaseAuthEnabled && (
            <>
              <label>
                <span>确认密码</span>
                <input
                  autoComplete="new-password"
                  minLength={8}
                  placeholder="请再次输入密码"
                  required
                  type="password"
                  value={confirmPassword}
                  onPointerDown={() => setPetMood("password")}
                  onFocus={() => setPetMood("password")}
                  onBlur={() => setPetMood("idle")}
                  onChange={(event) => setConfirmPassword(event.currentTarget.value)}
                />
              </label>
              <div className="account-verification-reserved" aria-label="邮箱验证说明">
                <div>
                  <span>邮箱验证</span>
                  <small>注册后发送</small>
                </div>
                <p>注册后会发送验证链接，验证邮箱后才能进入桌宠。</p>
              </div>
            </>
          )}
          {mode === "register" && !firebaseAuthEnabled && (
            <>
              <label>
                <span>确认密码</span>
                <input
                  autoComplete="new-password"
                  minLength={8}
                  placeholder="请再次输入密码"
                  required
                  type="password"
                  value={confirmPassword}
                  onPointerDown={() => setPetMood("password")}
                  onFocus={() => setPetMood("password")}
                  onBlur={() => setPetMood("idle")}
                  onChange={(event) => setConfirmPassword(event.currentTarget.value)}
                />
              </label>
              <div className="account-verification-reserved" aria-label="邮箱验证预留">
                <div>
                  <span>邮箱验证码</span>
                  <small>暂未启用</small>
                </div>
                <div className="account-verification-input">
                  <input aria-label="邮箱验证码" disabled placeholder="接入邮件服务后启用" />
                  <button disabled type="button">发送验证码</button>
                </div>
              </div>
            </>
          )}

          {error && <p className="account-error" role="alert">{error}</p>}

          <button className="account-submit" disabled={submitting} type="submit">
            <span>{submitting ? "请稍候…" : mode === "login" ? "登录，回到小橘身边" : firebaseAuthEnabled ? "注册并验证邮箱" : "注册并进入"}</span>
            {!submitting && <i aria-hidden="true">→</i>}
          </button>
        </form>
        )}

        <footer>
          <span><i aria-hidden="true">●</i> {firebaseAuthEnabled ? "邮箱验证由 Firebase 发送，当前不启用短信" : "当前为网页预览账号，数据安心留在本机"}</span>
          <button type="button" onClick={() => switchMode(mode === "login" ? "register" : "login")}>
            {mode === "login" ? "还没有账号？去注册" : "已经注册？去登录"}
          </button>
        </footer>
      </section>
    </main>
  );
}
