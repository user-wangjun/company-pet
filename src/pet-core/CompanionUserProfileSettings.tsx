import { useEffect, useState } from "react";
import {
  COMPANION_USER_GENDERS,
  normalizeCompanionUserProfile,
  type CompanionUserGender,
  type CompanionUserProfile,
  type CompanionUserProfileActionResult,
} from "./companionUserProfile";

type CompanionUserProfileSettingsProps = {
  profile: CompanionUserProfile;
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

export function CompanionUserProfileSettings({
  profile,
  onSave,
}: CompanionUserProfileSettingsProps) {
  const [draft, setDraft] = useState(() => normalizeCompanionUserProfile(profile));
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<CompanionUserProfileActionResult | null>(null);

  useEffect(() => {
    setDraft(normalizeCompanionUserProfile(profile));
    setFeedback(null);
  }, [profile]);

  const updateDraft = (patch: Partial<CompanionUserProfile>) => {
    setFeedback(null);
    setDraft((current) => normalizeCompanionUserProfile({ ...current, ...patch }));
  };

  const save = async () => {
    setBusy(true);
    setFeedback(null);
    try {
      setFeedback(await onSave(draft));
    } catch {
      setFeedback({ ok: false, message: "个人信息暂时没有保存成功，请稍后再试。" });
    } finally {
      setBusy(false);
    }
  };

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
        <button type="button" className="is-primary" disabled={busy} onClick={() => void save()}>
          {busy ? "保存中…" : "保存个人信息"}
        </button>
      </div>
    </section>
  );
}
