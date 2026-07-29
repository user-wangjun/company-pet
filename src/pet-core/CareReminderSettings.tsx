import { useRef, useState } from "react";
import type { CareReminderSettings as Settings } from "./careReminders";
import "./care-reminder-settings.css";

type Props = {
  settings: Settings;
  onChange: (settings: Settings) => void;
  embedded?: boolean;
  disableNoticeDismissed?: boolean;
  onDismissDisableNotice?: () => void;
};

const eyeIntervals = [20, 30, 40, 45, 60, 90];

function Toggle({ checked, label, onChange }: { checked: boolean; label: string; onChange: (checked: boolean) => void }) {
  return (
    <label className="care-setting-toggle">
      <span>{label}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.currentTarget.checked)} />
      <i aria-hidden="true" />
    </label>
  );
}

export function CareReminderSettings({ settings, onChange, embedded = false, disableNoticeDismissed = false, onDismissDisableNotice = () => {} }: Props) {
  const [noticeOpen, setNoticeOpen] = useState(false);
  const noticeRef = useRef<HTMLElement>(null);
  const patch = <K extends keyof Settings>(key: K, value: Partial<Settings[K]>) => {
    onChange({ ...settings, [key]: { ...settings[key], ...value } });
  };
  const toggleSystemPopup = <K extends keyof Settings>(key: K, enabled: boolean) => {
    patch(key, { enabled } as Partial<Settings[K]>);
    if (!enabled && !disableNoticeDismissed) setNoticeOpen(true);
  };
  const patchWellness = (value: Partial<Settings["wellness"]>) => {
    patch("wellness", value);
  };
  const systemPopupCount = Number(settings.wellness.enabled) + Number(settings.meal.enabled) + Number(settings.sleep.enabled);

  return (
    <section className={`care-settings-page${embedded ? " is-embedded" : ""}`} aria-label="关怀提醒设置">
      <header className="care-settings-header">
        <div><p>关怀提醒</p><h2>按你的节奏，温柔提醒</h2><span>频率和时间控制桌宠提醒；右侧开关只控制系统弹窗。</span></div>
        <div className="care-settings-summary"><b>{systemPopupCount}</b><span>项系统弹窗</span></div>
      </header>

      <div className="care-settings-grid">
        <article className={`care-setting-card is-eye${settings.wellness.enabled ? " is-enabled" : ""}`}>
          <header><span className="care-setting-icon">◉</span><div><h3>护眼与喝水</h3><p>定时看看远处、活动一下，再补充一点水分</p></div><Toggle label="护眼与喝水系统弹窗" checked={settings.wellness.enabled} onChange={(enabled) => { patchWellness({ enabled }); if (!enabled && !disableNoticeDismissed) setNoticeOpen(true); }} /></header>
          <label>桌宠提醒频率<select value={settings.wellness.intervalMinutes} onChange={(event) => patchWellness({ intervalMinutes: Number(event.target.value) })}>{eyeIntervals.map((minutes) => <option key={minutes} value={minutes}>每 {minutes} 分钟</option>)}</select></label>
        </article>

        <article className={`care-setting-card is-meal${settings.meal.enabled ? " is-enabled" : ""}`}>
          <header><span className="care-setting-icon">♨</span><div><h3>用餐提醒</h3><p>分别设置早餐、午餐和晚餐时间</p></div><Toggle label="用餐提醒系统弹窗" checked={settings.meal.enabled} onChange={(enabled) => toggleSystemPopup("meal", enabled)} /></header>
          <div className="care-setting-times">
            <label>早餐<input aria-label="早餐时间" type="time" value={settings.meal.breakfastTime} onChange={(event) => patch("meal", { breakfastTime: event.currentTarget.value })} /></label>
            <label>午餐<input aria-label="午餐时间" type="time" value={settings.meal.lunchTime} onChange={(event) => patch("meal", { lunchTime: event.currentTarget.value })} /></label>
            <label>晚餐<input aria-label="晚餐时间" type="time" value={settings.meal.dinnerTime} onChange={(event) => patch("meal", { dinnerTime: event.currentTarget.value })} /></label>
          </div>
        </article>

        <article className={`care-setting-card is-sleep${settings.sleep.enabled ? " is-enabled" : ""}`}>
          <header><span className="care-setting-icon">☾</span><div><h3>睡眠提醒</h3><p>到你的睡觉时间，再轻轻提醒一次</p></div><Toggle label="睡眠提醒系统弹窗" checked={settings.sleep.enabled} onChange={(enabled) => toggleSystemPopup("sleep", enabled)} /></header>
          <label>计划入睡时间<input aria-label="计划入睡时间" type="time" value={settings.sleep.bedtime} onChange={(event) => patch("sleep", { bedtime: event.currentTarget.value })} /></label>
        </article>
      </div>

      <footer className="care-settings-note"><span>桌宠提醒始终保留</span><p>关闭卡片右侧开关只会关闭系统通知弹窗，不会关闭桌宠动作和气泡；用餐和睡眠每天只提示一次。</p></footer>
      {noticeOpen && <div className="care-disable-notice-backdrop" onMouseDown={() => setNoticeOpen(false)}>
        <section ref={noticeRef} className="care-disable-notice" role="dialog" aria-modal="true" aria-labelledby="care-disable-notice-title" onMouseDown={(event) => event.stopPropagation()}>
          <span className="care-disable-notice-mark" aria-hidden="true">♡</span>
          <h3 id="care-disable-notice-title">我们仍会陪你照顾自己</h3>
          <p>可能是因为弹窗经常提醒导致影响您的体验了，很抱歉。</p>
          <p>但此次关闭只能影响弹窗关闭，我们还是希望您能时常爱惜自己的身体，毕竟人生还长，风景很美！</p>
          <small>——望星科技 × 知了</small>
          <div><button type="button" onClick={() => { onDismissDisableNotice(); setNoticeOpen(false); }}>以后不再提醒</button><button className="is-primary" type="button" autoFocus onClick={() => setNoticeOpen(false)}>关闭</button></div>
        </section>
      </div>}
    </section>
  );
}
