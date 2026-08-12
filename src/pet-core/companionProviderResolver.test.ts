import { describe, expect, test, vi } from "vitest";
import {
  ProviderAdapterError,
  type ProviderGenerateRequest,
  type ProviderHttpFetcher,
} from "./companionProviderAdapter";
import {
  createCompanionProviderResolver,
} from "./companionProviderResolver";
import {
  getCompanionProviderProfilePreset,
  normalizeCompanionProviderSettings,
  type CompanionProviderProfile,
} from "./companionProviderConfig";

function profile(
  protocol: "local" | "gemini-native" | "openai-compatible",
  overrides: Partial<CompanionProviderProfile> = {},
): CompanionProviderProfile {
  const preset = getCompanionProviderProfilePreset(
    protocol === "local"
      ? "local"
      : protocol === "gemini-native"
        ? "google-gemini"
        : "custom-provider",
  )!;
  return normalizeCompanionProviderSettings({
    ...preset,
    ...overrides,
    protocol,
  });
}

function request(overrides: Partial<ProviderGenerateRequest> = {}): ProviderGenerateRequest {
  return {
    model: "request-model",
    system: "system",
    messages: [{ role: "user", content: "hello" }],
    output: { format: "text" },
    timeoutMs: 100,
    ...overrides,
  };
}

function textFetcher(text = "reply"): ProviderHttpFetcher {
  return vi.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      choices: [{ message: { content: text } }],
      candidates: [{ content: { parts: [{ text }] } }],
    }),
  }));
}

describe("ProviderResolver", () => {
  test("resolves local without credential and keeps it text-only", async () => {
    const resolver = createCompanionProviderResolver({ profile: profile("local") });
    const adapter = resolver.resolve();
    expect(adapter.protocol).toBe("local");
    expect(adapter.info.kind).toBe("local");
    expect(adapter.capabilities).toMatchObject({
      textGeneration: true,
      structuredOutput: "none",
    });
    await expect(adapter.generate(request())).resolves.toHaveProperty("text");
  });

  test.each(["gemini-native", "openai-compatible"] as const)(
    "resolves %s by protocol and does not guess structured output",
    async (protocol) => {
      const fetcher = textFetcher();
      const adapter = createCompanionProviderResolver({
        profile: profile(protocol, {
          id: `${protocol}-profile`,
          displayName: "provider-name-that-is-not-a-capability",
          model: "model-name-that-is-not-a-capability",
          endpoint: protocol === "gemini-native"
            ? "https://generativelanguage.googleapis.com/v1beta"
            : "https://models.example/v1",
        }),
        credential: "SECRET_SENTINEL",
        fetcher,
      }).resolve();

      expect(adapter.protocol).toBe(protocol);
      expect(adapter.capabilities.structuredOutput).toBe("none");
      await expect(adapter.generate(request())).resolves.toHaveProperty("text", "reply");
      expect(fetcher).toHaveBeenCalledTimes(1);
    },
  );

  test("only advertises Gemini structured output when explicitly verified", () => {
    const resolver = createCompanionProviderResolver({
      profile: profile("gemini-native"),
      credential: "SECRET_SENTINEL",
      verifiedCapabilities: {
        structuredOutput: "json_object",
        cancellation: true,
      },
    });
    expect(resolver.resolve().capabilities).toMatchObject({
      structuredOutput: "json_object",
      cancellation: true,
    });
  });

  test("fails closed for unknown protocol and never auto-switches", () => {
    const fetcher = textFetcher();
    const unknown = normalizeCompanionProviderSettings({
      id: "unknown-profile",
      displayName: "Unknown",
      protocol: "future-protocol",
      endpoint: "https://models.example/v1",
      model: "future-model",
      credentialRef: "unknown-profile",
    });
    const resolver = createCompanionProviderResolver({
      profile: unknown,
      credential: "SECRET_SENTINEL",
      fetcher,
    });
    expect(() => resolver.resolve()).toThrowError(
      expect.objectContaining({ kind: "unsupported" }),
    );
    expect(fetcher).not.toHaveBeenCalled();
  });

  test("reads the selected profile at resolve time without selecting a fallback", () => {
    let selected = profile("openai-compatible", { id: "first-profile" });
    const resolver = createCompanionProviderResolver({
      profile: () => selected,
      credential: "SECRET_SENTINEL",
    });
    expect(resolver.resolve().id).toBe("first-profile");
    selected = profile("gemini-native", { id: "second-profile" });
    expect(resolver.resolve().id).toBe("second-profile");
    expect(resolver.resolve().protocol).toBe("gemini-native");
  });

  test("credential is not returned in adapter info, metadata, or errors", async () => {
    const fetcher = vi.fn<ProviderHttpFetcher>(async () => ({
      ok: false,
      status: 401,
      json: async () => ({ error: { message: "SECRET_SENTINEL" } }),
    }));
    const adapter = createCompanionProviderResolver({
      profile: profile("openai-compatible"),
      credential: "SECRET_SENTINEL",
      fetcher,
    }).resolve();
    expect(JSON.stringify(adapter.info)).not.toContain("SECRET_SENTINEL");
    const result = adapter.generate(request());
    await expect(result).rejects.toBeInstanceOf(ProviderAdapterError);
    await expect(result).rejects.not.toHaveProperty(
      "message",
      expect.stringContaining("SECRET_SENTINEL"),
    );
  });

  test("does not echo a secure-store error or sentinel during resolve", () => {
    const resolver = createCompanionProviderResolver({
      profile: profile("openai-compatible"),
      credential: () => {
        throw new Error("secure store failed: SECRET_SENTINEL");
      },
    });

    expect(() => resolver.resolve()).toThrowError(
      expect.objectContaining({ kind: "configuration" }),
    );
    try {
      resolver.resolve();
    } catch (error) {
      expect(error).toBeInstanceOf(ProviderAdapterError);
      expect(String((error as Error).message)).not.toContain("SECRET_SENTINEL");
      expect(String((error as Error).stack)).not.toContain("SECRET_SENTINEL");
    }
  });
});
