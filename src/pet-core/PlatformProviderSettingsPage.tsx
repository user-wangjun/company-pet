import { CompanionProviderSettings } from "./CompanionProviderSettings";
import { CompanionUserProfileSettings } from "./CompanionUserProfileSettings";
import type { CompanionChatProviderInfo } from "./companionChatRuntime";
import type {
  CompanionProviderActionResult,
  CompanionProviderSettings as CompanionProviderSettingsValue,
} from "./companionProviderConfig";
import type {
  CompanionUserProfile,
  CompanionUserProfileActionResult,
} from "./companionUserProfile";
import type { SettingsInitialization } from "./companionUserSettingsRepository";
import type { CompanionProviderModelsActionResult } from "./companionProviderModels";
import type { BundledOllamaPullProgress } from "./CompanionOllamaPullProgress";

export type PlatformProviderSettingsPageProps = {
  userProfile: CompanionUserProfile | null;
  userProfileSettings?: SettingsInitialization;
  onUserProfileSettingsRetry?: () => void;
  onUserProfileSave: (
    profile: CompanionUserProfile,
  ) => CompanionUserProfileActionResult | Promise<CompanionUserProfileActionResult>;
  settings: CompanionProviderSettingsValue;
  providerInfo: CompanionChatProviderInfo;
  onProviderChange?: (
    profileId: CompanionProviderSettingsValue["id"],
    current: CompanionProviderSettingsValue,
  ) => CompanionProviderSettingsValue | Promise<CompanionProviderSettingsValue>;
  onTest: (
    settings: CompanionProviderSettingsValue,
    credential?: string,
  ) => CompanionProviderActionResult | Promise<CompanionProviderActionResult>;
  onSave: (
    settings: CompanionProviderSettingsValue,
    credential?: string,
  ) => CompanionProviderActionResult | Promise<CompanionProviderActionResult>;
  onFetchModels?: (
    settings: CompanionProviderSettingsValue,
    credential?: string,
  ) => CompanionProviderModelsActionResult | Promise<CompanionProviderModelsActionResult>;
  onClear?: (
    settings: CompanionProviderSettingsValue,
  ) => CompanionProviderActionResult | Promise<CompanionProviderActionResult>;
  ollamaPullProgress?: BundledOllamaPullProgress | null;
};

export function PlatformProviderSettingsPage({
  userProfile,
  userProfileSettings,
  onUserProfileSettingsRetry,
  onUserProfileSave,
  settings,
  providerInfo,
  onProviderChange,
  onTest,
  onSave,
  onFetchModels,
  onClear,
  ollamaPullProgress,
}: PlatformProviderSettingsPageProps) {
  return (
    <section className="platform-provider-settings-page" aria-label="设置">
      <header className="platform-page-heading">
        <div>
          <span>设置</span>
          <h2>设置中心</h2>
        </div>
        <p>个人信息、模型服务和后续设置都集中在这里。</p>
      </header>

      <CompanionUserProfileSettings
        profile={userProfile}
        settings={userProfileSettings}
        onRetry={onUserProfileSettingsRetry}
        onSave={onUserProfileSave}
      />

      <div className="platform-provider-settings-note">
        <div>
          <span>陪伴边界</span>
          <strong>Provider 只负责模型接入</strong>
          <p>确定性任务、Memory、Soul、主动提醒和当前宠物身份仍由本机逻辑管理。</p>
        </div>
        <span className={`platform-provider-settings-note-status is-${providerInfo.kind}`}>
          接入方式：{providerInfo.kind === "remote" ? "远程" : "本地"}
        </span>
      </div>

      <CompanionProviderSettings
        settings={settings}
        providerInfo={providerInfo}
        onProviderChange={onProviderChange}
        onTest={onTest}
        onSave={onSave}
        onFetchModels={onFetchModels}
        onClear={onClear}
        ollamaPullProgress={ollamaPullProgress}
      />
    </section>
  );
}
