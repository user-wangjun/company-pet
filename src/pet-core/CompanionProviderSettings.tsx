import { useEffect, useMemo, useState } from "react";
import type { CompanionChatProviderInfo } from "./companionChatRuntime";
import {
  COMPANION_PROVIDER_PROTOCOLS,
  DEFAULT_GEMINI_COMPANION_API_BASE_URL,
  DEFAULT_OPENAI_COMPATIBLE_API_BASE_URL,
  getCompanionProviderProfilePreset,
  getCompanionProviderProtocolDescription,
  getCompanionProviderProtocolLabel,
  getCompanionProviderProfilePresets,
  getDefaultEndpointForProtocol,
  getDefaultModelForProtocol,
  normalizeCompanionProviderSettings,
  type CompanionProviderActionResult,
  type CompanionProviderId,
  type CompanionProviderProtocol,
  type CompanionProviderSettings,
} from "./companionProviderConfig";

type CompanionProviderSettingsProps = {
  settings: CompanionProviderSettings;
  providerInfo: CompanionChatProviderInfo;
  onProviderChange?: (
    profileId: CompanionProviderId,
    current: CompanionProviderSettings,
  ) => CompanionProviderSettings | Promise<CompanionProviderSettings>;
  onTest: (
    settings: CompanionProviderSettings,
    credential?: string,
  ) => CompanionProviderActionResult | Promise<CompanionProviderActionResult>;
  onSave: (
    settings: CompanionProviderSettings,
    credential?: string,
  ) => CompanionProviderActionResult | Promise<CompanionProviderActionResult>;
  onClear?: (
    settings: CompanionProviderSettings,
  ) => CompanionProviderActionResult | Promise<CompanionProviderActionResult>;
};

export function applyCompanionProviderProtocol(
  settings: CompanionProviderSettings,
  protocol: CompanionProviderProtocol,
): CompanionProviderSettings {
  const nextId = protocol === "local"
    ? "local"
    : settings.id === "local"
      ? "custom-provider"
      : settings.id;
  const endpoint = protocol === "local"
    ? ""
    : settings.protocol === "local" || !settings.endpoint.trim()
      ? getDefaultEndpointForProtocol(protocol)
      : settings.endpoint;
  const model = protocol === "local"
    ? "local"
    : settings.protocol === "local" || !settings.model.trim() || settings.model === "local"
      ? getDefaultModelForProtocol(protocol)
      : settings.model;
  return normalizeCompanionProviderSettings({
    ...settings,
    id: nextId,
    displayName: protocol === "local" ? "本地陪伴" : settings.displayName === "本地陪伴"
      ? "自定义 Provider"
      : settings.displayName,
    protocol,
    endpoint,
    model,
    credentialRef: protocol === "local"
      ? null
      : settings.credentialRef ?? (nextId === "local" ? "custom-provider" : nextId),
    credentialConfigured: protocol === "local" ? false : settings.credentialConfigured,
  });
}

const protocolOptions = COMPANION_PROVIDER_PROTOCOLS.map((protocol) => ({
  protocol,
  label: getCompanionProviderProtocolLabel(protocol),
}));

export function CompanionProviderSettings({
  settings,
  providerInfo,
  onProviderChange,
  onTest,
  onSave,
  onClear,
}: CompanionProviderSettingsProps) {
  const [draft, setDraft] = useState(() => normalizeCompanionProviderSettings(settings));
  const [credentialInput, setCredentialInput] = useState("");
  const [busyAction, setBusyAction] = useState<"test" | "save" | "clear" | "profile" | null>(null);
  const [feedback, setFeedback] = useState<CompanionProviderActionResult | null>(null);

  const profileOptions = useMemo(() => {
    const presets = getCompanionProviderProfilePresets()
      .filter((profile) => profile.id !== "custom-gemini");
    if (!presets.some((profile) => profile.id === draft.id)) {
      presets.push({
        id: draft.id,
        displayName: `${draft.displayName}（当前配置）`,
        protocol: draft.protocol,
        endpoint: draft.endpoint,
        model: draft.model,
        credentialRef: draft.credentialRef,
      });
    }
    return presets;
  }, [draft]);

  useEffect(() => {
    setDraft(normalizeCompanionProviderSettings(settings));
    setCredentialInput("");
  }, [settings]);

  const updateDraft = (patch: Partial<CompanionProviderSettings>) => {
    setFeedback(null);
    setDraft((current) => normalizeCompanionProviderSettings({
      ...current,
      ...patch,
    }));
  };

  const runAction = async (
    action: "test" | "save",
    handler: CompanionProviderSettingsProps["onTest"],
  ) => {
    setBusyAction(action);
    setFeedback(null);
    try {
      const result = await handler(draft, credentialInput.trim() || undefined);
      setFeedback(result);
    } catch {
      setFeedback({
        ok: false,
        message: "Provider 操作暂时没有完成，请稍后再试。",
      });
    } finally {
      setBusyAction(null);
    }
  };

  const changeProfile = async (profileId: CompanionProviderId) => {
    if (profileId === draft.id) return;
    setBusyAction("profile");
    setFeedback(null);
    try {
      const preset = getCompanionProviderProfilePreset(profileId);
      const next = onProviderChange
        ? await onProviderChange(profileId, draft)
        : normalizeCompanionProviderSettings({
            ...(preset ?? draft),
            id: profileId,
          });
      setDraft(normalizeCompanionProviderSettings(next));
      setCredentialInput("");
    } catch {
      setFeedback({
        ok: false,
        message: "系统安全存储暂时不可用，请稍后再试。",
      });
    } finally {
      setBusyAction(null);
    }
  };

  const clearCredential = async () => {
    if (!draft.credentialConfigured || !onClear) return;
    setBusyAction("clear");
    setFeedback(null);
    try {
      const result = await onClear(draft);
      setFeedback(result);
      if (result.ok) {
        setDraft(normalizeCompanionProviderSettings({
          ...draft,
          credentialConfigured: false,
        }));
        setCredentialInput("");
      }
    } catch {
      setFeedback({
        ok: false,
        message: "凭据没有清除成功，请稍后再试。",
      });
    } finally {
      setBusyAction(null);
    }
  };

  const isRemote = draft.protocol !== "local";
  const endpointPlaceholder = draft.protocol === "gemini-native"
    ? DEFAULT_GEMINI_COMPANION_API_BASE_URL
    : DEFAULT_OPENAI_COMPATIBLE_API_BASE_URL;

  return (
    <section className="companion-provider-settings" aria-label="聊天 Provider 设置">
      <header className="companion-provider-settings-header">
        <div>
          <span>聊天 Provider</span>
          <h3>选择模型服务</h3>
          <p>Provider 只负责模型接入；Soul、Memory、Task 和宠物身份仍由本机陪伴逻辑管理。</p>
        </div>
        <span className={`companion-provider-status-pill is-${providerInfo.kind}`}>
          <i aria-hidden="true" />
          当前使用：{providerInfo.provider}
        </span>
      </header>

      <div className="companion-provider-form">
        <label className="companion-provider-field">
          <strong>Provider Profile</strong>
          <select
            aria-label="Provider Profile"
            value={draft.id}
            disabled={busyAction !== null}
            onChange={(event) => void changeProfile(event.currentTarget.value)}
          >
            {profileOptions.map((profile) => (
              <option value={profile.id} key={profile.id}>
                {profile.displayName}
              </option>
            ))}
          </select>
          <small>Profile ID：{draft.id}；它是稳定配置标识，不等同于厂商类型。</small>
        </label>

        <label className="companion-provider-field">
          <strong>Provider 名称</strong>
          <input
            aria-label="Provider 名称"
            value={draft.displayName}
            onChange={(event) => updateDraft({ displayName: event.currentTarget.value })}
          />
        </label>

        <label className="companion-provider-field">
          <strong>协议</strong>
          <select
            aria-label="Provider 协议"
            value={draft.protocol}
            onChange={(event) => updateDraft(applyCompanionProviderProtocol(
              draft,
              event.currentTarget.value as CompanionProviderProtocol,
            ))}
          >
            {protocolOptions.map(({ protocol, label }) => (
              <option value={protocol} key={protocol}>{label}</option>
            ))}
          </select>
          <small>{getCompanionProviderProtocolDescription(draft.protocol)}</small>
        </label>

        {isRemote && (
          <>
            <label className="companion-provider-field">
              <strong>Model</strong>
              <input
                aria-label="Provider Model"
                value={draft.model}
                placeholder={draft.protocol === "gemini-native" ? "例如 gemini-2.5-flash" : "例如 gpt-4o-mini"}
                onChange={(event) => updateDraft({ model: event.currentTarget.value })}
              />
            </label>

            <label className="companion-provider-field companion-provider-field-wide">
              <strong>Endpoint</strong>
              <input
                aria-label="Provider Endpoint"
                type="url"
                value={draft.endpoint}
                placeholder={endpointPlaceholder}
                onChange={(event) => updateDraft({ endpoint: event.currentTarget.value })}
              />
              <small>默认值：{endpointPlaceholder}。Endpoint 不能包含查询参数或内嵌凭据；远程地址使用 HTTPS，本机 loopback 可用 HTTP。</small>
            </label>

            <label className="companion-provider-field">
              <strong>API Key</strong>
              <input
                aria-label="Provider API Key"
                type="password"
                autoComplete="new-password"
                value={credentialInput}
                placeholder={draft.credentialConfigured ? "••••••••（已配置，重新输入可替换）" : "填写 API Key"}
                onChange={(event) => setCredentialInput(event.currentTarget.value)}
              />
              <small>输入框只用于本次保存或连接测试；凭据仅进入系统安全存储，不写入普通配置、localStorage 或日志。</small>
              {draft.credentialConfigured && (
                <button
                  className="companion-provider-clear-key"
                  type="button"
                  disabled={busyAction !== null}
                  onClick={() => void clearCredential()}
                >
                  {busyAction === "clear" ? "清除中…" : "清除已保存 API Key"}
                </button>
              )}
            </label>

            <label className="companion-provider-fallback">
              <span>
                <strong>远程服务失败后回退到本地陪伴</strong>
                <small>连接失败、超时、额度不足或鉴权失败时，明确切换为本地回复。</small>
              </span>
              <input
                type="checkbox"
                checked={draft.fallbackToLocal}
                onChange={(event) => updateDraft({ fallbackToLocal: event.currentTarget.checked })}
              />
            </label>

            <p className="companion-provider-disclosure">
              {providerInfo.kind === "remote"
                ? providerInfo.disclosure
                : "远程模式会发送本轮必要上下文到所选服务；请不要在聊天中输入不适合发送到云端的敏感信息。"}
            </p>
          </>
        )}

        {!isRemote && (
          <p className="companion-provider-disclosure">
            本地模式：本次聊天不会发起网络请求，Memory、Task、Soul、主动提醒和确定性意图处理不变。
          </p>
        )}
      </div>

      {feedback && (
        <p className={`companion-provider-feedback is-${feedback.ok ? "success" : "error"}`} role={feedback.ok ? "status" : "alert"}>
          {feedback.message}
        </p>
      )}

      <div className="companion-provider-actions">
        <button
          type="button"
          disabled={busyAction !== null}
          onClick={() => void runAction("test", onTest)}
        >
          {busyAction === "test" ? "测试中…" : "测试连接"}
        </button>
        <button
          className="is-primary"
          type="button"
          disabled={busyAction !== null}
          onClick={() => void runAction("save", onSave)}
        >
          {busyAction === "save" ? "保存中…" : "保存并使用"}
        </button>
      </div>
    </section>
  );
}
