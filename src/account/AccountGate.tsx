import {
  createContext,
  useContext,
  useRef,
  useState,
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import {
  hasPreviewAccounts,
  loginPreviewAccount,
  logoutPreviewAccount,
  readPreviewSession,
  registerPreviewAccount,
  type PreviewAccount,
} from "./previewAuth";
import type { AccountPetMood } from "./accountPetParameters";
import { AccountPetPuppet } from "./AccountPetPuppet";
import "./account.css";

type AuthMode = "login" | "register";

type AccountContextValue = {
  account: PreviewAccount;
  signOut: () => void;
};

const AccountContext = createContext<AccountContextValue | null>(null);

export function useAccountSession(): AccountContextValue {
  const context = useContext(AccountContext);
  if (!context) throw new Error("useAccountSession must be used inside AccountGate");
  return context;
}

export function AccountGate({ children }: { children: ReactNode }) {
  const introRef = useRef<HTMLElement>(null);
  const pointerRef = useRef({ x: 0, y: 0 });
  const [account, setAccount] = useState<PreviewAccount | null>(() => readPreviewSession());
  const [mode, setMode] = useState<AuthMode>(() => hasPreviewAccounts() ? "login" : "register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [petMood, setPetMood] = useState<AccountPetMood>("idle");

  const movePetGaze = (event: ReactPointerEvent<HTMLElement>) => {
    const intro = introRef.current;
    if (!intro) return;
    const bounds = intro.getBoundingClientRect();
    const lookX = Math.max(-1, Math.min(1, ((event.clientX - bounds.left) / bounds.width) * 2 - 1));
    const lookY = Math.max(-1, Math.min(1, ((event.clientY - bounds.top) / bounds.height) * 2 - 1));
    pointerRef.current = { x: lookX, y: lookY };
    intro.style.setProperty("--gaze-x", `${lookX * 1.4}px`);
    intro.style.setProperty("--gaze-y", `${lookY}px`);
    intro.style.setProperty("--scene-x", `${lookX * 1.2}px`);
    intro.style.setProperty("--scene-y", `${lookY * .8}px`);
    intro.style.setProperty("--bubble-tilt", `${lookX * .45}deg`);
    intro.style.setProperty("--pupil-x", `${lookX * 6}px`);
    intro.style.setProperty("--pupil-y", `${lookY * 4}px`);
  };

  const resetPetGaze = () => {
    const intro = introRef.current;
    if (!intro) return;
    intro.style.setProperty("--gaze-x", "0px");
    intro.style.setProperty("--gaze-y", "0px");
    intro.style.setProperty("--scene-x", "0px");
    intro.style.setProperty("--scene-y", "0px");
    intro.style.setProperty("--bubble-tilt", "0deg");
    intro.style.setProperty("--pupil-x", "0px");
    intro.style.setProperty("--pupil-y", "0px");
    pointerRef.current = { x: 0, y: 0 };
  };

  const switchMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setPetMood("idle");
    setPassword("");
    setConfirmPassword("");
    setError(null);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);

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
            logoutPreviewAccount();
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
    <main className="account-gate">
      <section
        className={`account-intro is-${petMood}-mood`}
        aria-label="愈心桌宠账号介绍"
        ref={introRef}
        onPointerMove={movePetGaze}
        onPointerLeave={resetPetGaze}
      >
        <div className="account-pet-stage" aria-hidden="true">
          <AccountPetPuppet mood={petMood} pointer={pointerRef} />
        </div>
        <div className="account-world-vignette" aria-hidden="true" />
        <div className="account-brand">
          <div className="account-brand-mark" aria-hidden="true">愈</div>
          <div><strong>愈心桌宠</strong><span>YUXIN DESKTOP PET</span></div>
        </div>
        <div className="account-hero-copy">
          <p>WELCOME HOME</p>
          <h1>小橘一直<br />在等你。</h1>
          <span>把待办交给我，把今天留给你。</span>
        </div>
        <div className="account-pet-speech" aria-hidden="true">
          <span>{petMood === "password"
            ? "放心输入吧，我捂好眼睛，绝对不偷看喵！"
            : petMood === "email"
              ? "我在认真记住你呀～ 很快就是朋友啦！"
              : mode === "login"
                ? "你回来啦？我有乖乖等你喵。"
                : "第一次见面！以后让我陪着你吧。"}</span>
          <i />
        </div>
        <div className="account-gaze-hint" aria-hidden="true">
          <span>↗</span> 点一下输入框，看看小橘的反应
        </div>
        <div className="account-stars" aria-hidden="true">
          <i /><i /><i /><i /><i /><i />
        </div>
      </section>

      <section className="account-card" aria-labelledby="account-title">
        <div className="account-card-paw" aria-hidden="true"><i /><i /><i /><i /></div>
        <div className="account-mode-switch" aria-label="账号操作">
          <button className={mode === "login" ? "is-active" : ""} type="button" onClick={() => switchMode("login")}><span>⌂</span>登录</button>
          <button className={mode === "register" ? "is-active" : ""} type="button" onClick={() => switchMode("register")}><span>＋</span>注册</button>
        </div>

        <header>
          <p><span>{mode === "login" ? "WELCOME BACK" : "NEW FRIEND"}</span>{mode === "login" ? "欢迎回来" : "创建预览账号"}</p>
          <h2 id="account-title">{mode === "login" ? "继续你的陪伴时光" : "第一次见面，请多关照"}</h2>
        </header>

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
          {mode === "register" && (
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
            <span>{submitting ? "请稍候…" : mode === "login" ? "登录并进入" : "注册并进入"}</span>
            {!submitting && <i aria-hidden="true">→</i>}
          </button>
        </form>

        <footer>
          <span><i aria-hidden="true">●</i> 当前为网页预览账号，数据安心留在本机</span>
          <button type="button" onClick={() => switchMode(mode === "login" ? "register" : "login")}>
            {mode === "login" ? "还没有账号？去注册" : "已经注册？去登录"}
          </button>
        </footer>
      </section>
    </main>
  );
}
