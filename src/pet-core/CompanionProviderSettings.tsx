import { useEffect, useMemo, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import type { CompanionChatProviderInfo } from "./companionChatRuntime";
import {
  COMPANION_PROVIDER_PROTOCOLS,
  BUNDLED_OLLAMA_MODELS,
  DEFAULT_GEMINI_COMPANION_API_BASE_URL,
  DEFAULT_OPENAI_COMPATIBLE_API_BASE_URL,
  getCompanionProviderProfilePreset,
  getCompanionProviderProtocolDescription,
  getCompanionProviderProtocolLabel,
  getCompanionProviderProfilePresets,
  getDefaultEndpointForProtocol,
  getDefaultModelForProtocol,
  isLocalCompanionProviderProtocol,
  normalizeCompanionProviderModelIds,
  normalizeCompanionProviderSettings,
  type CompanionProviderActionResult,
  type CompanionProviderId,
  type CompanionProviderProtocol,
  type CompanionProviderSettings,
} from "./companionProviderConfig";
import type { CompanionProviderModelsActionResult } from "./companionProviderModels";
import {
  CompanionOllamaPullProgress,
  type BundledOllamaPullProgress,
} from "./CompanionOllamaPullProgress";

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
  onFetchModels?: (
    settings: CompanionProviderSettings,
    credential?: string,
  ) => CompanionProviderModelsActionResult | Promise<CompanionProviderModelsActionResult>;
  onClear?: (
    settings: CompanionProviderSettings,
  ) => CompanionProviderActionResult | Promise<CompanionProviderActionResult>;
  ollamaPullProgress?: BundledOllamaPullProgress | null;
};

type BundledOllamaStatus = {
  available: boolean;
  running: boolean;
  version: string | null;
};

export function applyCompanionProviderProtocol(
  settings: CompanionProviderSettings,
  protocol: CompanionProviderProtocol,
): CompanionProviderSettings {
  const currentIsLocal = isLocalCompanionProviderProtocol(settings.protocol);
  const targetIsLocal = isLocalCompanionProviderProtocol(protocol);
  const switchedFromLocal = currentIsLocal && !targetIsLocal;
  const nextId = protocol === "local"
    ? "local"
    : protocol === "ollama-local"
      ? "bundled-ollama"
      : currentIsLocal
        ? "custom-provider"
        : settings.id;
  const endpoint = targetIsLocal
    ? ""
    : switchedFromLocal
      ? ""
      : settings.endpoint;
  const model = protocol === "local"
    ? "local"
    : protocol === "ollama-local"
      ? settings.protocol === "ollama-local"
        ? settings.model
        : getDefaultModelForProtocol(protocol)
    : switchedFromLocal || settings.model === "local"
      ? ""
      : settings.model;
  const models = protocol === "local"
    ? ["local"]
    : protocol === "ollama-local"
      ? settings.protocol === "ollama-local"
        ? normalizeCompanionProviderModelIds([
            ...BUNDLED_OLLAMA_MODELS,
            ...(settings.models ?? []),
          ])
        : [...BUNDLED_OLLAMA_MODELS]
    : switchedFromLocal
      ? []
      : settings.models ?? [];
  return normalizeCompanionProviderSettings({
    ...settings,
    id: nextId,
    displayName: protocol === "local"
      ? "本地陪伴"
      : protocol === "ollama-local"
        ? "内置本地模型（Ollama）"
        : switchedFromLocal
          ? ""
          : settings.displayName,
    protocol,
    endpoint,
    model,
    models,
    credentialRef: targetIsLocal
      ? null
      : settings.credentialRef ?? (nextId === "local" ? "custom-provider" : nextId),
    credentialConfigured: targetIsLocal ? false : settings.credentialConfigured,
  });
}

function createCompanionProviderDraft(
  settings: CompanionProviderSettings,
): CompanionProviderSettings {
  const normalized = normalizeCompanionProviderSettings(settings);
  if (normalized.id !== "custom-provider") return normalized;
  const preset = getCompanionProviderProfilePreset("custom-provider");
  const defaultEndpoint = getDefaultEndpointForProtocol(normalized.protocol);
  const defaultModel = getDefaultModelForProtocol(normalized.protocol);
  return {
    ...normalized,
    displayName: normalized.displayName === preset?.displayName
      ? ""
      : normalized.displayName,
    endpoint: defaultEndpoint && normalized.endpoint === defaultEndpoint
      ? ""
      : normalized.endpoint,
    model: defaultModel && normalized.model === defaultModel
      ? ""
      : normalized.model,
  };
}

function materializeCompanionProviderDraft(
  draft: CompanionProviderSettings,
  options: { allowEmptyModel?: boolean } = {},
): CompanionProviderSettings {
  const normalized = normalizeCompanionProviderSettings(draft);
  const preset = getCompanionProviderProfilePreset("custom-provider");
  const model = options.allowEmptyModel
    ? normalized.model.trim()
    : normalized.model.trim() || getDefaultModelForProtocol(normalized.protocol);
  const displayName = normalized.id === "custom-provider"
    ? normalized.displayName.trim() || preset?.displayName
    : normalized.displayName;
  const endpoint = normalized.id === "custom-provider"
    ? normalized.endpoint.trim() || getDefaultEndpointForProtocol(normalized.protocol)
    : normalized.endpoint;
  return normalizeCompanionProviderSettings({
    ...normalized,
    displayName,
    endpoint,
    model,
    models: normalizeCompanionProviderModelIds([
      ...(normalized.models ?? []),
      ...(model ? [model] : []),
    ]),
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
  onFetchModels,
  onClear,
  ollamaPullProgress,
}: CompanionProviderSettingsProps) {
  const [draft, setDraft] = useState(() => createCompanionProviderDraft(settings));
  const [credentialInput, setCredentialInput] = useState("");
  const [busyAction, setBusyAction] = useState<"test" | "save" | "clear" | "profile" | "fetch" | null>(null);
  const [feedback, setFeedback] = useState<CompanionProviderActionResult | null>(null);
  const draftDirtyRef = useRef(false);

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
    if (draftDirtyRef.current) return;
    setDraft(createCompanionProviderDraft(settings));
    setCredentialInput("");
  }, [settings]);

  const updateDraft = (patch: Partial<CompanionProviderSettings>) => {
    draftDirtyRef.current = true;
    setFeedback(null);
    setDraft((current) => ({
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
      const submitted = materializeCompanionProviderDraft(draft);
      const result = await handler(submitted, credentialInput.trim() || undefined);
      setFeedback(result);
      if (action === "save" && result.ok) {
        draftDirtyRef.current = false;
        setDraft(createCompanionProviderDraft({
          ...submitted,
          credentialConfigured: submitted.credentialConfigured || Boolean(credentialInput.trim()),
        }));
        setCredentialInput("");
      }
    } catch {
      setFeedback({
        ok: false,
        message: "Provider 操作暂时没有完成，请稍后再试。",
      });
    } finally {
      setBusyAction(null);
    }
  };

  const fetchModels = async () => {
    if (!onFetchModels) return;
    setBusyAction("fetch");
    setFeedback(null);
    try {
      const submitted = materializeCompanionProviderDraft(draft, {
        allowEmptyModel: true,
      });
      const result = await onFetchModels(
        submitted,
        credentialInput.trim() || undefined,
      );
      setFeedback(result);
      if (result.ok && result.models && result.models.length > 0) {
        const models = normalizeCompanionProviderModelIds(result.models);
        // Never silently replace a manually entered model just because the
        // upstream catalog does not include it; the input remains the escape
        // hatch for gateways with partial or filtered /models responses.
        const selectedModel = submitted.model || models[0] || "";
        draftDirtyRef.current = true;
        setDraft((current) => ({
          ...current,
          model: selectedModel,
          models,
        }));
      }
    } catch {
      setFeedback({
        ok: false,
        message: "模型列表暂时没有获取成功，请检查 Endpoint 和网络。",
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
      draftDirtyRef.current = true;
      setDraft(createCompanionProviderDraft(next));
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
      const result = await onClear(materializeCompanionProviderDraft(draft));
      setFeedback(result);
      if (result.ok) {
        setDraft((current) => ({
          ...current,
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

  const isBundledOllama = draft.protocol === "ollama-local";
  const isRemote = !isLocalCompanionProviderProtocol(draft.protocol);
  const [ollamaStatus, setOllamaStatus] = useState<BundledOllamaStatus | null>(null);
  useEffect(() => {
    if (
      !isBundledOllama
      || typeof window === "undefined"
      || !("__TAURI_INTERNALS__" in window)
    ) {
      setOllamaStatus(null);
      return;
    }
    let cancelled = false;
    void invoke<BundledOllamaStatus>("get_bundled_ollama_status")
      .then((status) => {
        if (!cancelled) setOllamaStatus(status);
      })
      .catch(() => {
        if (!cancelled) {
          setOllamaStatus({ available: false, running: false, version: null });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [isBundledOllama]);
  const modelOptions = useMemo(() => {
    const models = normalizeCompanionProviderModelIds(draft.models);
    const currentModel = draft.model.trim();
    if (currentModel && !models.includes(currentModel)) {
      return [currentModel, ...models];
    }
    return models;
  }, [draft.model, draft.models]);
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
            placeholder="自定义 Provider"
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

        {(isRemote || isBundledOllama) && (
          <>
            <label className="companion-provider-field">
              <strong>{isBundledOllama ? "本地模型" : "Model"}</strong>
              <div className="companion-provider-model-control">
                <input
                  aria-label="Provider Model"
                  list="companion-provider-model-options"
                  value={draft.model}
                  placeholder={getDefaultModelForProtocol(draft.protocol) || "请输入 Model"}
                  onChange={(event) => updateDraft({ model: event.currentTarget.value })}
                />
                {onFetchModels && (
                  <button
                    className="companion-provider-fetch-models"
                    type="button"
                    disabled={busyAction !== null}
                    onClick={() => void fetchModels()}
                  >
                    {busyAction === "fetch"
                      ? "获取中…"
                      : isBundledOllama ? "扫描已下载模型" : "获取模型"}
                  </button>
                )}
              </div>
              <datalist id="companion-provider-model-options">
                {modelOptions.map((model) => <option value={model} key={model} />)}
              </datalist>
              {modelOptions.length > 0 && (
                <select
                  aria-label="Provider 可用模型"
                  value={draft.model}
                  disabled={busyAction !== null}
                  onChange={(event) => updateDraft({ model: event.currentTarget.value })}
                >
                  <option value="">从已获取的模型中选择</option>
                  {modelOptions.map((model) => (
                    <option value={model} key={model}>{model}</option>
                  ))}
                </select>
              )}
              <small>
                  {(draft.models ?? []).length > 0
                  ? isBundledOllama
                    ? `内置提供 ${(draft.models ?? []).length} 个模型；实际调用时按需下载。`
                    : `已获取 ${(draft.models ?? []).length} 个模型；也可以手动填写 Model。`
                  : isBundledOllama
                    ? "模型文件按需下载；点击测试或首次聊天时会自动准备所选模型。"
                    : "填写 Endpoint 和 API Key 后，可从上游 /models 获取模型列表。"}
              </small>
            </label>

            {isRemote && (
              <label className="companion-provider-field companion-provider-field-wide">
              <strong>Endpoint</strong>
              <input
                aria-label="Provider Endpoint"
                type="url"
                value={draft.endpoint}
                placeholder={endpointPlaceholder}
                onChange={(event) => updateDraft({
                  endpoint: event.currentTarget.value,
                  models: [],
                })}
              />
              <small>默认值：{endpointPlaceholder}。Endpoint 不能包含查询参数或内嵌凭据；远程地址使用 HTTPS，本机 loopback 可用 HTTP。</small>
              </label>
            )}

            {isRemote && (
              <label className="companion-provider-field">
              <strong>API Key</strong>
              <input
                aria-label="Provider API Key"
                type="password"
                autoComplete="new-password"
                value={credentialInput}
                placeholder={draft.credentialConfigured ? "••••••••（已配置，重新输入可替换）" : "填写 API Key"}
                onChange={(event) => {
                  draftDirtyRef.current = true;
                  setFeedback(null);
                  setCredentialInput(event.currentTarget.value);
                }}
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
            )}

            {isRemote && (
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
            )}

            {isRemote && (
              <p className="companion-provider-disclosure">
                {providerInfo.kind === "remote"
                  ? providerInfo.disclosure
                  : "远程模式会发送本轮必要上下文到所选服务；请不要在聊天中输入不适合发送到云端的敏感信息。"}
              </p>
            )}
          </>
        )}

        {isBundledOllama && (
          <>
            <p className="companion-provider-disclosure">
              内置 Ollama 模式：应用会自动启动随安装包提供的本地运行时，生成请求留在本机；首次使用模型时需要联网下载模型文件，之后可离线聊天。
              {ollamaStatus && (
                <small>
                  {ollamaStatus.available
                    ? ollamaStatus.running
                      ? `运行时已启动${ollamaStatus.version ? `（${ollamaStatus.version}）` : ""}。`
                      : "运行时已随应用准备好，使用测试或聊天时会自动启动。"
                    : "当前安装包没有找到内置运行时，请重新构建或安装 Windows x64 版本。"}
                </small>
              )}
            </p>
            <CompanionOllamaPullProgress progress={ollamaPullProgress} />
          </>
        )}

        {draft.protocol === "local" && (
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
