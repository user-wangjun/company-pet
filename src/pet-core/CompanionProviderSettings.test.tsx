import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import { CompanionProviderSettings, applyCompanionProviderProtocol } from "./CompanionProviderSettings";
import {
  getCompanionProviderProfilePreset,
  getCompanionProviderStatusInfo,
  normalizeCompanionProviderSettings,
} from "./companionProviderConfig";

describe("CompanionProviderSettings", () => {
  test("renders neutral profile, protocol, endpoint, model, credential, status, and actions", () => {
    const settings = normalizeCompanionProviderSettings({
      ...getCompanionProviderProfilePreset("custom-provider"),
      credentialConfigured: true,
    });
    const html = renderToStaticMarkup(
      <CompanionProviderSettings
        settings={settings}
        providerInfo={getCompanionProviderStatusInfo(settings)}
        onTest={vi.fn()}
        onSave={vi.fn()}
        onClear={vi.fn()}
      />,
    );

    expect(html).toContain("Provider Profile");
    expect(html).toContain("Provider 名称");
    expect(html).toContain("Provider 协议");
    expect(html).toContain("openai-compatible");
    expect(html).toContain("Endpoint");
    expect(html).toContain("Model");
    expect(html).toContain("API Key");
    expect(html).toContain("当前使用：自定义 Provider");
    expect(html).toContain("测试连接");
    expect(html).toContain("保存并使用");
    expect(html).toContain("清除已保存 API Key");
    expect(html).not.toContain("unit-secret");
  });

  test("protocol switching changes defaults without moving the pet or domain data", () => {
    const current = normalizeCompanionProviderSettings({
      ...getCompanionProviderProfilePreset("google-gemini"),
      displayName: "我的模型",
      credentialConfigured: true,
    });
    const switched = applyCompanionProviderProtocol(current, "openai-compatible");

    expect(switched).toMatchObject({
      id: "google-gemini",
      displayName: "我的模型",
      protocol: "openai-compatible",
      endpoint: current.endpoint,
      model: current.model,
      credentialRef: "google-gemini",
      credentialConfigured: true,
    });
  });

  test("switching to local clears only provider connectivity metadata", () => {
    const remote = normalizeCompanionProviderSettings({
      ...getCompanionProviderProfilePreset("custom-provider"),
      credentialConfigured: true,
    });
    const local = applyCompanionProviderProtocol(remote, "local");
    expect(local).toMatchObject({
      id: "local",
      protocol: "local",
      endpoint: "",
      model: "local",
      credentialRef: null,
      credentialConfigured: false,
    });
  });
});
