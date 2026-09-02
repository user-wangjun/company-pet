import { describe, expect, test, vi } from "vitest";
import {
  fetchCompanionProviderModels,
  getCompanionProviderModelListUrl,
  parseCompanionProviderModelList,
  type CompanionProviderModelListFetcher,
} from "./companionProviderModels";
import {
  getCompanionProviderProfilePreset,
  normalizeCompanionProviderSettings,
} from "./companionProviderConfig";

function response(payload: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  };
}

function settings(
  protocol: "openai-compatible" | "gemini-native" | "ollama-local" = "openai-compatible",
) {
  return normalizeCompanionProviderSettings({
    ...getCompanionProviderProfilePreset(protocol === "ollama-local" ? "bundled-ollama" : "custom-provider"),
    protocol,
    endpoint: protocol === "ollama-local"
      ? ""
      : protocol === "gemini-native"
      ? "https://generativelanguage.googleapis.com/v1beta"
      : "https://models.example/v1",
    model: "",
    credentialConfigured: true,
  });
}

describe("companion provider model discovery", () => {
  test("parses OpenAI-compatible and Gemini-shaped model lists", () => {
    expect(parseCompanionProviderModelList({
      object: "list",
      data: [{ id: "model-a" }, { id: "model-b" }, { id: "model-a" }],
    })).toEqual(["model-a", "model-b"]);
    expect(parseCompanionProviderModelList({
      models: [{ name: "models/gemini-2.5-flash" }, { name: "gemini-2.0-flash" }],
    })).toEqual(["gemini-2.5-flash", "gemini-2.0-flash"]);
  });

  test("fetches multiple models from the upstream URL with an ephemeral credential", async () => {
    const fetcher = vi.fn<CompanionProviderModelListFetcher>(async (url, init) => {
      expect(url).toBe("https://models.example/v1/models");
      expect(init.method).toBe("GET");
      expect(init.headers.Authorization).toBe("Bearer SECRET_SENTINEL");
      return response({ data: [{ id: "qwen-plus" }, { id: "deepseek-chat" }] });
    });

    await expect(fetchCompanionProviderModels(settings(), "SECRET_SENTINEL", { fetcher }))
      .resolves.toEqual({ models: ["qwen-plus", "deepseek-chat"] });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  test("uses the Gemini models URL and API-key header without putting the key in the URL", async () => {
    const fetcher = vi.fn<CompanionProviderModelListFetcher>(async (url, init) => {
      expect(url).toBe("https://generativelanguage.googleapis.com/v1beta/models");
      expect(url).not.toContain("SECRET_SENTINEL");
      expect(init.headers["x-goog-api-key"]).toBe("SECRET_SENTINEL");
      return response({ models: [{ name: "models/gemini-2.5-flash" }] });
    });

    await expect(fetchCompanionProviderModels(
      settings("gemini-native"),
      "SECRET_SENTINEL",
      { fetcher },
    )).resolves.toEqual({ models: ["gemini-2.5-flash"] });
  });

  test("accepts an endpoint that already ends in /models", () => {
    expect(getCompanionProviderModelListUrl(normalizeCompanionProviderSettings({
      ...settings(),
      endpoint: "https://models.example/v1/models",
    }))).toBe("https://models.example/v1/models");
  });

  test("lists models from the bundled Ollama runtime without an API key", async () => {
    const fetcher = vi.fn<CompanionProviderModelListFetcher>(async (url, init) => {
      expect(url).toBe("内置 Ollama（本机）/api/tags");
      expect(init.headers.Authorization).toBeUndefined();
      return response({ models: [{ name: "qwen3:0.6b" }, { model: "gemma3:1b" }] });
    });
    const ollama = settings("ollama-local");

    expect(getCompanionProviderModelListUrl(ollama)).toBe("内置 Ollama（本机）/api/tags");
    await expect(fetchCompanionProviderModels(ollama, null, { fetcher }))
      .resolves.toEqual({ models: ["qwen3:0.6b", "gemma3:1b"] });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  test("distinguishes unsupported, malformed, and missing-credential cases without leaking secrets", async () => {
    const unsupported = vi.fn<CompanionProviderModelListFetcher>(async () => response({}, 404));
    await expect(fetchCompanionProviderModels(settings(), "SECRET_SENTINEL", {
      fetcher: unsupported,
    })).rejects.toMatchObject({ kind: "unsupported" });

    const malformed = vi.fn<CompanionProviderModelListFetcher>(async () => response({ data: [] }));
    await expect(fetchCompanionProviderModels(settings(), "SECRET_SENTINEL", {
      fetcher: malformed,
    })).rejects.toMatchObject({ kind: "malformed-response" });

    const network = vi.fn<CompanionProviderModelListFetcher>(async () => {
      throw new Error("SECRET_SENTINEL upstream detail");
    });
    const networkError = await fetchCompanionProviderModels(
      settings(),
      "SECRET_SENTINEL",
      { fetcher: network },
    ).catch((error: unknown) => error);
    expect(networkError).toMatchObject({ kind: "network" });
    expect(String(networkError)).not.toContain("SECRET_SENTINEL");
    await expect(fetchCompanionProviderModels(settings(), null))
      .rejects.toMatchObject({ kind: "configuration" });
  });
});
