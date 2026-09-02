import { useEffect, useRef, useState } from "react";
import {
  EMPTY_COMPANION_USER_PROFILE,
  COMPANION_USER_GENDERS,
  normalizeCompanionUserProfile,
  type CompanionUserGender,
  type CompanionUserProfile,
  type CompanionUserProfileActionResult,
} from "./companionUserProfile";
import type { SettingsInitialization } from "./companionUserSettingsRepository";

type CompanionUserProfileSettingsProps = {
  profile: CompanionUserProfile | null;
  settings?: SettingsInitialization;
  onRetry?: () => void;
  onSave: (
    profile: CompanionUserProfile,
  ) => CompanionUserProfileActionResult | Promise<CompanionUserProfileActionResult>;
};

const genderOptions: ReadonlyArray<{ value: CompanionUserGender; label: string }> = [
  { value: "unspecified", label: "暂不填写" },
  { value: "female", label: "女" },
  { value: "male", label: "男" },
  { value: "non-binary", label: "非二元" },
  { value: "prefer-not-to-say", label: "不透露" },
];

export type CompanionUserProfileSaveLifecycle = {
  id: number;
  baseProfile: CompanionUserProfile;
  submittedProfile: CompanionUserProfile;
  result: CompanionUserProfileActionResult | null;
};

export type CompanionUserProfileDraftSyncOptions = {
  blocked?: boolean;
  clearFeedback?: boolean;
  saveLifecycle?: CompanionUserProfileSaveLifecycle | null;
};

export type CompanionUserProfileDraftSyncResult = {
  draft: CompanionUserProfile;
  feedback: CompanionUserProfileActionResult | null;
  saveLifecycleValid: boolean;
};

type CompanionUserProfileSaveAttempt = CompanionUserProfileSaveLifecycle & {
  draftRevisionAtSubmit: number;
  feedbackAllowed: boolean;
  lifecycleGeneration: number;
};

function sameCompanionUserProfile(
  left: CompanionUserProfile,
  right: CompanionUserProfile,
): boolean {
  return left.nickname === right.nickname
    && left.gender === right.gender
    && left.email === right.email
    && left.phone === right.phone;
}

export function synchronizeCompanionUserProfileDraft(
  profile: CompanionUserProfile | null,
  feedback: CompanionUserProfileActionResult | null,
  options: CompanionUserProfileDraftSyncOptions = {},
): CompanionUserProfileDraftSyncResult {
  const draft = normalizeCompanionUserProfile(profile ?? EMPTY_COMPANION_USER_PROFILE);
  const saveLifecycle = options.saveLifecycle ?? null;
  const blocked = options.blocked === true || profile === null;
  const isAssociatedProfile = saveLifecycle !== null
    && (sameCompanionUserProfile(draft, saveLifecycle.baseProfile)
      || sameCompanionUserProfile(draft, saveLifecycle.submittedProfile));

  return {
    draft,
    feedback: !blocked
      && !options.clearFeedback
      && isAssociatedProfile
      && saveLifecycle?.result !== null
      ? feedback
      : null,
    saveLifecycleValid: !blocked && !options.clearFeedback && isAssociatedProfile,
  };
}

export function CompanionUserProfileSettings({
  profile,
  settings,
  onRetry,
  onSave,
}: CompanionUserProfileSettingsProps) {
  const [draft, setDraft] = useState(() => normalizeCompanionUserProfile(profile ?? EMPTY_COMPANION_USER_PROFILE));
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<CompanionUserProfileActionResult | null>(null);
  const draftRef = useRef(draft);
  const draftRevisionRef = useRef(0);
  const draftDirtyRef = useRef(false);
  const saveLifecycleSequenceRef = useRef(0);
  const saveLifecycleRef = useRef<CompanionUserProfileSaveAttempt | null>(null);
  const requestInFlightRef = useRef<CompanionUserProfileSaveAttempt | null>(null);
  const lifecycleGenerationRef = useRef(0);
  const mountedRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      lifecycleGenerationRef.current += 1;
    };
  }, []);

  useEffect(() => {
    const requestInFlight = requestInFlightRef.current;
    const saveAttempt = saveLifecycleRef.current;
    const isBlocked = profile === null || settings?.status === "blocked";

    if (isBlocked) {
      if (saveAttempt) {
        saveAttempt.feedbackAllowed = false;
        if (requestInFlight !== saveAttempt) {
          saveLifecycleRef.current = null;
        }
      }
      setFeedback(null);
      setBusy(requestInFlight !== null);
      return;
    }

    const nextProfile = normalizeCompanionUserProfile(profile);
    if (!saveAttempt) {
      if (!draftDirtyRef.current) {
        draftRef.current = nextProfile;
        setDraft(nextProfile);
      }
      setFeedback(null);
      setBusy(requestInFlight !== null);
      return;
    }

    const isSubmittedProjection = sameCompanionUserProfile(
      nextProfile,
      saveAttempt.submittedProfile,
    );
    const isBaseProjection = sameCompanionUserProfile(
      nextProfile,
      saveAttempt.baseProfile,
    );

    if (draftDirtyRef.current) {
      saveAttempt.feedbackAllowed = false;
      setFeedback(null);
    } else if (isSubmittedProjection) {
      draftRef.current = nextProfile;
      setDraft(nextProfile);
      if (saveAttempt.result !== null && saveAttempt.feedbackAllowed) {
        setFeedback(saveAttempt.result);
      }
    } else if (!isBaseProjection) {
      saveAttempt.feedbackAllowed = false;
      if (requestInFlight === null) {
        saveLifecycleRef.current = null;
        draftRef.current = nextProfile;
        setDraft(nextProfile);
      }
      setFeedback(null);
    }
    setBusy(requestInFlight !== null);
  }, [profile, settings?.status]);

  const updateDraft = (patch: Partial<CompanionUserProfile>) => {
    const nextDraft = normalizeCompanionUserProfile({ ...draftRef.current, ...patch });
    draftRef.current = nextDraft;
    draftRevisionRef.current += 1;
    draftDirtyRef.current = true;
    const saveAttempt = saveLifecycleRef.current;
    if (saveAttempt && requestInFlightRef.current === saveAttempt) {
      saveAttempt.feedbackAllowed = false;
    } else {
      saveLifecycleRef.current = null;
    }
    setFeedback(null);
    setDraft(nextDraft);
  };

  const save = () => {
    if (!profile || settings?.status === "blocked" || requestInFlightRef.current !== null) return;
    const submittedProfile = normalizeCompanionUserProfile(draftRef.current);
    const lifecycle: CompanionUserProfileSaveAttempt = {
      id: saveLifecycleSequenceRef.current + 1,
      baseProfile: normalizeCompanionUserProfile(profile),
      submittedProfile,
      result: null,
      draftRevisionAtSubmit: draftRevisionRef.current,
      feedbackAllowed: true,
      lifecycleGeneration: lifecycleGenerationRef.current,
    };
    saveLifecycleSequenceRef.current = lifecycle.id;
    saveLifecycleRef.current = lifecycle;
    requestInFlightRef.current = lifecycle;
    draftDirtyRef.current = false;
    setBusy(true);
    setFeedback(null);

    void (async () => {
      try {
        const result = await onSave(submittedProfile);
        if (requestInFlightRef.current !== lifecycle) return;
        lifecycle.result = result;
        if (
          lifecycle.feedbackAllowed
          && lifecycle.lifecycleGeneration === lifecycleGenerationRef.current
          && draftRevisionRef.current === lifecycle.draftRevisionAtSubmit
        ) {
          setFeedback(result);
        }
      } catch {
        if (requestInFlightRef.current !== lifecycle) return;
        const result = { ok: false, message: "个人信息暂时没有保存成功，请稍后再试。" };
        lifecycle.result = result;
        if (
          lifecycle.feedbackAllowed
          && lifecycle.lifecycleGeneration === lifecycleGenerationRef.current
          && draftRevisionRef.current === lifecycle.draftRevisionAtSubmit
        ) {
          setFeedback(result);
        }
      } finally {
        if (requestInFlightRef.current === lifecycle) {
          requestInFlightRef.current = null;
          if (!lifecycle.feedbackAllowed || lifecycle.result === null) {
            saveLifecycleRef.current = null;
          }
          if (
            mountedRef.current
            && lifecycle.lifecycleGeneration === lifecycleGenerationRef.current
          ) {
            setBusy(false);
          }
        }
      }
    })();
  };

  if (!profile || settings?.status === "blocked") {
    const reason = settings?.status === "blocked" ? settings.reason : "not-ready";
    const message = reason === "owner-unavailable" || reason === "bridge-timeout"
      ? "主窗口暂时不可用，个人信息仍未读取。"
      : reason === "recovery-blocked"
      ? "本机设置正在等待恢复，个人信息仍未读取。"
      : "本机设置读取失败，原有资料未被当作空资料。";
    return (
      <section className="companion-user-profile-settings" aria-label="个人信息">
        <header className="companion-user-profile-settings-header">
          <div>
            <span>个人信息</span>
            <h3>关于你</h3>
            <p role="alert">{message}</p>
          </div>
        </header>
        {onRetry && (
          <div className="companion-user-profile-actions">
            <button type="button" className="is-primary" onClick={onRetry}>
              重新读取本机设置
            </button>
          </div>
        )}
      </section>
    );
  }

  return (
    <section className="companion-user-profile-settings" aria-label="个人信息">
      <header className="companion-user-profile-settings-header">
        <div>
          <span>个人信息</span>
          <h3>关于你</h3>
          <p>这些内容只用于本机设置；邮箱和电话不会进入聊天上下文或发送给 Provider。</p>
        </div>
      </header>

      <div className="companion-user-profile-form">
        <label className="companion-user-profile-field">
          <strong>昵称</strong>
          <input
            aria-label="用户昵称"
            value={draft.nickname}
            maxLength={32}
            placeholder="例如：阿星"
            onChange={(event) => updateDraft({ nickname: event.currentTarget.value })}
          />
          <small>保存后会同步为当前陪伴使用的称呼。</small>
        </label>

        <label className="companion-user-profile-field">
          <strong>性别</strong>
          <select
            aria-label="用户性别"
            value={draft.gender}
            onChange={(event) => updateDraft({ gender: event.currentTarget.value as CompanionUserGender })}
          >
            {genderOptions
              .filter((option) => (COMPANION_USER_GENDERS as readonly string[]).includes(option.value))
              .map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
          </select>
          <small>不填写也不会影响陪伴功能。</small>
        </label>

        <label className="companion-user-profile-field">
          <strong>邮箱</strong>
          <input
            aria-label="用户邮箱"
            type="email"
            autoComplete="email"
            value={draft.email}
            placeholder="可选"
            onChange={(event) => updateDraft({ email: event.currentTarget.value })}
          />
        </label>

        <label className="companion-user-profile-field">
          <strong>电话</strong>
          <input
            aria-label="用户电话"
            type="tel"
            autoComplete="tel"
            value={draft.phone}
            placeholder="可选"
            onChange={(event) => updateDraft({ phone: event.currentTarget.value })}
          />
        </label>
      </div>

      {feedback && (
        <p className={`companion-user-profile-feedback is-${feedback.ok ? "success" : "error"}`} role={feedback.ok ? "status" : "alert"}>
          {feedback.message}
        </p>
      )}

      <div className="companion-user-profile-actions">
        <button type="button" className="is-primary" disabled={busy} onClick={save}>
          {busy ? "保存中…" : "保存个人信息"}
        </button>
      </div>
    </section>
  );
}
