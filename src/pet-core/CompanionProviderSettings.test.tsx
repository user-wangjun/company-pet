// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import { CompanionProviderSettings, applyCompanionProviderProtocol } from "./CompanionProviderSettings";
import {
  DEFAULT_BUNDLED_OLLAMA_MODEL,
  getCompanionProviderProfilePreset,
  getCompanionProviderStatusInfo,
  normalizeCompanionProviderSettings,
} from "./companionProviderConfig";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

async function setInputValue(input: HTMLInputElement, value: string): Promise<void> {
  await act(async () => {
    const valueSetter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )?.set;
    if (!valueSetter) throw new Error("input value setter not available");
    valueSetter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

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

  test("switching to bundled Ollama selects the default local model without credentials", () => {
    const remote = normalizeCompanionProviderSettings({
      ...getCompanionProviderProfilePreset("custom-provider"),
      credentialConfigured: true,
    });
    const ollama = applyCompanionProviderProtocol(remote, "ollama-local");

    expect(ollama).toMatchObject({
      id: "bundled-ollama",
      displayName: "内置本地模型（Ollama）",
      protocol: "ollama-local",
      endpoint: "",
      model: DEFAULT_BUNDLED_OLLAMA_MODEL,
      credentialRef: null,
      credentialConfigured: false,
    });
  });

  test("renders bundled Ollama instructions without cloud credential fields", () => {
    const settings = normalizeCompanionProviderSettings(
      getCompanionProviderProfilePreset("bundled-ollama"),
    );
    const html = renderToStaticMarkup(
      <CompanionProviderSettings
        settings={settings}
        providerInfo={getCompanionProviderStatusInfo(settings)}
        onTest={vi.fn()}
        onSave={vi.fn()}
        onFetchModels={vi.fn()}
      />,
    );

    expect(html).toContain("内置 Ollama 模式");
    expect(html).toContain("扫描已下载模型");
    expect(html).not.toContain("API Key");
    expect(html).not.toContain("Endpoint");
  });

  test("switching from local to a remote protocol leaves examples as placeholders", () => {
    const local = normalizeCompanionProviderSettings(
      getCompanionProviderProfilePreset("local"),
    );
    const remote = applyCompanionProviderProtocol(local, "openai-compatible");

    expect(remote).toMatchObject({
      id: "custom-provider",
      displayName: "",
      protocol: "openai-compatible",
      endpoint: "",
      model: "",
      credentialRef: "custom-provider",
      credentialConfigured: false,
    });
  });

  test("keeps explicitly cleared fields empty across a settings re-projection", async () => {
    const settings = normalizeCompanionProviderSettings({
      ...getCompanionProviderProfilePreset("custom-provider"),
      displayName: "工作 Provider",
      endpoint: "https://models.example/v1",
      model: "chat-model",
      credentialConfigured: false,
    });
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    const render = (nextSettings = settings) => (
      <CompanionProviderSettings
        settings={nextSettings}
        providerInfo={getCompanionProviderStatusInfo(nextSettings)}
        onTest={vi.fn()}
        onSave={vi.fn()}
      />
    );

    try {
      await act(async () => root.render(render()));
      const nameInput = container.querySelector<HTMLInputElement>(
        'input[aria-label="Provider 名称"]',
      );
      const modelInput = container.querySelector<HTMLInputElement>(
        'input[aria-label="Provider Model"]',
      );
      const endpointInput = container.querySelector<HTMLInputElement>(
        'input[aria-label="Provider Endpoint"]',
      );
      if (!nameInput || !modelInput || !endpointInput) {
        throw new Error("provider inputs not mounted");
      }

      expect(nameInput.value).toBe("工作 Provider");
      expect(modelInput.value).toBe("chat-model");
      expect(endpointInput.value).toBe("https://models.example/v1");
      await setInputValue(nameInput, "");
      await setInputValue(modelInput, "");
      await setInputValue(endpointInput, "");
      await act(async () => root.render(render({ ...settings })));

      expect(nameInput.value).toBe("");
      expect(modelInput.value).toBe("");
      expect(endpointInput.value).toBe("");
      expect(nameInput.placeholder).toBe("自定义 Provider");
      expect(modelInput.placeholder).toBe("gpt-4o-mini");
      expect(endpointInput.placeholder).toBe("https://api.openai.com/v1");
    } finally {
      await act(async () => root.unmount());
      container.remove();
    }
  });

  test("renders persisted custom defaults as placeholders and materializes them for actions", async () => {
    const settings = normalizeCompanionProviderSettings({
      ...getCompanionProviderProfilePreset("custom-provider"),
      credentialConfigured: true,
    });
    const onTest = vi.fn().mockResolvedValue({ ok: true, message: "连接成功" });
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      await act(async () => {
        root.render(
          <CompanionProviderSettings
            settings={settings}
            providerInfo={getCompanionProviderStatusInfo(settings)}
            onTest={onTest}
            onSave={vi.fn()}
          />,
        );
      });
      expect(container.querySelector<HTMLInputElement>(
        'input[aria-label="Provider 名称"]',
      )?.value).toBe("");
      expect(container.querySelector<HTMLInputElement>(
        'input[aria-label="Provider Model"]',
      )?.value).toBe("");
      expect(container.querySelector<HTMLInputElement>(
        'input[aria-label="Provider Endpoint"]',
      )?.value).toBe("");

      const testButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button"))
        .find((button) => button.textContent === "测试连接");
      if (!testButton) throw new Error("test connection button not mounted");
      await act(async () => {
        testButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        await Promise.resolve();
      });

      expect(onTest).toHaveBeenCalledWith(expect.objectContaining({
        id: "custom-provider",
        displayName: "自定义 Provider",
        endpoint: "https://api.openai.com/v1",
        model: "gpt-4o-mini",
      }), undefined);
    } finally {
      await act(async () => root.unmount());
      container.remove();
    }
  });

  test("shows a newly selected custom profile as placeholders instead of filled examples", async () => {
    const settings = normalizeCompanionProviderSettings(
      getCompanionProviderProfilePreset("local"),
    );
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      await act(async () => {
        root.render(
          <CompanionProviderSettings
            settings={settings}
            providerInfo={getCompanionProviderStatusInfo(settings)}
            onTest={vi.fn()}
            onSave={vi.fn()}
          />,
        );
      });
      const profileSelect = container.querySelector<HTMLSelectElement>(
        'select[aria-label="Provider Profile"]',
      );
      if (!profileSelect) throw new Error("provider profile select not mounted");

      await act(async () => {
        const valueSetter = Object.getOwnPropertyDescriptor(
          HTMLSelectElement.prototype,
          "value",
        )?.set;
        if (!valueSetter) throw new Error("select value setter not available");
        valueSetter.call(profileSelect, "custom-provider");
        profileSelect.dispatchEvent(new Event("change", { bubbles: true }));
        await Promise.resolve();
      });

      expect(container.querySelector<HTMLInputElement>(
        'input[aria-label="Provider 名称"]',
      )?.value).toBe("");
      expect(container.querySelector<HTMLInputElement>(
        'input[aria-label="Provider Model"]',
      )?.value).toBe("");
      expect(container.querySelector<HTMLInputElement>(
        'input[aria-label="Provider Endpoint"]',
      )?.value).toBe("");
    } finally {
      await act(async () => root.unmount());
      container.remove();
    }
  });

  test("fetches and exposes multiple upstream models while keeping manual input available", async () => {
    const settings = normalizeCompanionProviderSettings({
      ...getCompanionProviderProfilePreset("custom-provider"),
      displayName: "工作 Provider",
      endpoint: "https://models.example/v1",
      model: "manual-model",
      credentialConfigured: true,
    });
    const onFetchModels = vi.fn().mockResolvedValue({
      ok: true,
      message: "已从上游获取 2 个模型，请选择后保存。",
      models: ["qwen-plus", "deepseek-chat"],
    });
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      await act(async () => {
        root.render(
          <CompanionProviderSettings
            settings={settings}
            providerInfo={getCompanionProviderStatusInfo(settings)}
            onTest={vi.fn()}
            onSave={vi.fn()}
            onFetchModels={onFetchModels}
          />,
        );
      });
      const fetchButton = Array.from(container.querySelectorAll<HTMLButtonElement>("button"))
        .find((button) => button.textContent === "获取模型");
      if (!fetchButton) throw new Error("fetch models button not mounted");

      await act(async () => {
        fetchButton.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        await Promise.resolve();
      });

      expect(onFetchModels).toHaveBeenCalledWith(expect.objectContaining({
        endpoint: "https://models.example/v1",
        model: "manual-model",
      }), undefined);
      expect(container.querySelector<HTMLInputElement>(
        'input[aria-label="Provider Model"]',
      )?.value).toBe("manual-model");
      const availableModels = container.querySelector<HTMLSelectElement>(
        'select[aria-label="Provider 可用模型"]',
      );
      expect(availableModels?.options).toHaveLength(4);
      expect(Array.from(availableModels?.options ?? []).map((option) => option.value))
        .toEqual(["", "manual-model", "qwen-plus", "deepseek-chat"]);

      await act(async () => {
        const valueSetter = Object.getOwnPropertyDescriptor(
          HTMLSelectElement.prototype,
          "value",
        )?.set;
        if (!valueSetter || !availableModels) throw new Error("model select unavailable");
        valueSetter.call(availableModels, "deepseek-chat");
        availableModels.dispatchEvent(new Event("change", { bubbles: true }));
        await Promise.resolve();
      });
      expect(container.querySelector<HTMLInputElement>(
        'input[aria-label="Provider Model"]',
      )?.value).toBe("deepseek-chat");
    } finally {
      await act(async () => root.unmount());
      container.remove();
    }
  });
});
