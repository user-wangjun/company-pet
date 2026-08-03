import { describe, expect, test, vi } from "vitest";
import {
  DEFAULT_GEMINI_COMPANION_API_BASE_URL,
  DEFAULT_GEMINI_COMPANION_MODEL,
  CompanionChatProviderError,
  createCompanionChatProvider,
  createGeminiCompanionChatProvider,
  isOfficialGoogleGeminiEndpoint,
  normalizeGeminiApiBaseUrl,
  resolveGeminiCompanionConnection,
  type CompanionChatHttpResponse,
} from "./companionChatProvider";
import type { CompanionChatConfig } from "./companionChat";
import { assembleCompanionContext } from "./companionContext";
import type { MemoryEntry } from "./companionMemory";

const config: CompanionChatConfig = {
  openers: [{ text: "喵？" }],
  localReplies: ["嗯，我听着。"],
  style: { tone: "quiet-companion", maxReplyLength: 24 },
};

function response(payload: unknown, status = 200): CompanionChatHttpResponse {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  };
}

describe("companion chat providers", () => {
  test("normalizes the shared Google Gemini API endpoint", () => {
    expect(normalizeGeminiApiBaseUrl()).toBe(
      DEFAULT_GEMINI_COMPANION_API_BASE_URL,
    );
    expect(
      normalizeGeminiApiBaseUrl(
        "https://generativelanguage.googleapis.com/v1beta/models/",
      ),
    ).toBe(DEFAULT_GEMINI_COMPANION_API_BASE_URL);
    expect(
      isOfficialGoogleGeminiEndpoint(
        "https://generativelanguage.googleapis.com/v1beta/",
      ),
    ).toBe(true);
    expect(isOfficialGoogleGeminiEndpoint("https://aistudio.google.com/")).toBe(
      false,
    );
    expect(normalizeGeminiApiBaseUrl("http://localhost:8787/v1beta")).toBe(
      "http://localhost:8787/v1beta",
    );
    expect(() => normalizeGeminiApiBaseUrl("http://remote.example/v1beta")).toThrow(
      "自定义聊天服务必须使用 HTTPS",
    );
  });

  test("keeps AI Studio and Google Cloud as metadata under one Google backend", () => {
    expect(
      resolveGeminiCompanionConnection({
        apiKey: "  test-key  ",
        keySource: "ai-studio",
      }),
    ).toMatchObject({
      backend: "google-gemini",
      apiKey: "test-key",
      endpoint: DEFAULT_GEMINI_COMPANION_API_BASE_URL,
      model: DEFAULT_GEMINI_COMPANION_MODEL,
      keySource: "ai-studio",
    });
    expect(
      resolveGeminiCompanionConnection({ apiKey: "test-key" }).keySource,
    ).toBe("unknown");
  });

  test("uses the local provider when no Gemini key is configured", async () => {
    const fetcher = vi.fn(async () => response({}));
    const provider = createCompanionChatProvider(config, {
      endpoint: "https://custom.example/v1beta",
      fetcher,
      random: () => 0,
    });

    await expect(
      provider.send({ text: "今天还行" }),
    ).resolves.toEqual({ text: "嗯，我听着。" });
    expect(provider.info).toMatchObject({
      kind: "local",
      provider: "本地 Provider",
      target: "本机",
    });
    expect(fetcher).not.toHaveBeenCalled();
  });

  test("treats empty and whitespace-only keys as local mode", () => {
    const fetcher = vi.fn(async () => response({}));
    for (const apiKey of [undefined, null, "", "   \n\t"]) {
      const provider = createCompanionChatProvider(config, { apiKey, fetcher });
      expect(provider.info).toMatchObject({ kind: "local", provider: "本地 Provider" });
    }
    expect(fetcher).not.toHaveBeenCalled();
  });

  test("resolves the remote disclosure before the first fetch", async () => {
    const fetcher = vi.fn(async () =>
      response({ candidates: [{ content: { parts: [{ text: "我在。" }] } }] }),
    );
    const provider = createCompanionChatProvider(config, {
      apiKey: "test-key",
      fetcher,
    });

    expect(provider.info).toMatchObject({
      kind: "remote",
      provider: "Google Gemini",
      target: DEFAULT_GEMINI_COMPANION_API_BASE_URL,
    });
    expect(fetcher).not.toHaveBeenCalled();
    await provider.send({ text: "你好" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  test("sends a short conversation to Gemini and reads the model reply", async () => {
    const fetcher = vi.fn(async (_url: string, _init: { body: string }) =>
      response({
        candidates: [
          { content: { parts: [{ text: "那就慢慢来，我在这里陪你。" }] } },
        ],
      }),
    );
    const provider = createGeminiCompanionChatProvider({
      apiKey: "test-key",
      config,
      fetcher,
    });

    await expect(
      provider.send({
        text: "今天有点累",
        history: [
          { id: "opener", speaker: "pet", text: "喵？" },
          { id: "user-1", speaker: "user", text: "你好" },
          { id: "pet-1", speaker: "pet", text: "我在呢" },
        ],
      }),
    ).resolves.toEqual({ text: "那就慢慢来，我在这里陪你。" });

    expect(fetcher).toHaveBeenCalledTimes(1);
    const [, init] = fetcher.mock.calls[0];
    const body = JSON.parse(init.body) as {
      system_instruction: { parts: Array<{ text: string }> };
      contents: Array<{ role: string; parts: Array<{ text: string }> }>;
      generationConfig: { maxOutputTokens: number };
    };
    expect(body.contents).toEqual([
      { role: "user", parts: [{ text: "你好" }] },
      { role: "model", parts: [{ text: "我在呢" }] },
      { role: "user", parts: [{ text: "今天有点累" }] },
    ]);
    expect(body.generationConfig.maxOutputTokens).toBe(48);
    expect(body.system_instruction.parts[0].text).toContain(
      "平台安全与隐私规则",
    );
    expect(fetcher.mock.calls[0][1]).toMatchObject({
      method: "POST",
      headers: {
        "x-goog-api-key": "test-key",
      },
    });
    expect(provider.info).toMatchObject({
      kind: "remote",
      provider: "Google Gemini",
      target: DEFAULT_GEMINI_COMPANION_API_BASE_URL,
    });
    expect(JSON.stringify(provider.info)).not.toContain("test-key");
  });

  test("injects existing preferences and preserves companion systemPrompt", async () => {
    const fetcher = vi.fn(async (_url: string, _init: { body: string }) =>
      response({
        candidates: [{ content: { parts: [{ text: "我在。" }] } }],
      }),
    );
    const provider = createGeminiCompanionChatProvider({
      apiKey: "test-key",
      config: { ...config, systemPrompt: "旧版陪伴提示仍然有效。" },
      fetcher,
    });

    await provider.send({
      text: "今天还行",
      preferences: [
        {
          id: "global.nickname",
          scope: "global",
          category: "userProfile",
          key: "nickname",
          value: "小主人",
          source: "explicit",
        },
      ],
    });

    const [, init] = fetcher.mock.calls[0];
    const body = JSON.parse(init.body) as {
      system_instruction: { parts: Array<{ text: string }> };
    };
    expect(body.system_instruction.parts[0].text).toContain(
      "旧版陪伴提示仍然有效。",
    );
    expect(body.system_instruction.parts[0].text).toContain(
      "nickname: 小主人",
    );
  });

  test("uses the caller's active pet id when assembling a fallback context", async () => {
    const fetcher = vi.fn(async (_url: string, _init: { body: string }) =>
      response({
        candidates: [{ content: { parts: [{ text: "我记得呀。" }] } }],
      }),
    );
    const provider = createGeminiCompanionChatProvider({
      apiKey: "test-key",
      config,
      fetcher,
    });

    await provider.send({ text: "桂花茶", petId: "xiaoju-cat" });

    const [, init] = fetcher.mock.calls[0];
    const body = JSON.parse(init.body) as {
      system_instruction: { parts: Array<{ text: string }> };
    };
    expect(body.system_instruction.parts[0].text).toContain(
      "当前宠物 ID：xiaoju-cat",
    );
    expect(body.system_instruction.parts[0].text).not.toContain(
      "当前宠物 ID：unknown",
    );
  });

  test("sends an assembled pet Soul to Gemini without changing the provider contract", async () => {
    const fetcher = vi.fn(async (_url: string, _init: { body: string }) =>
      response({
        candidates: [{ content: { parts: [{ text: "喵，我在。" }] } }],
      }),
    );
    const provider = createGeminiCompanionChatProvider({
      apiKey: "test-key",
      config,
      fetcher,
    });
    const context = assembleCompanionContext({
      petId: "xiaoju-cat",
      userInput: "你好",
      soul: {
        status: "loaded",
        petId: "xiaoju-cat",
        path: "SOUL.md",
        content: "我是小橘，只在这里安静陪伴。",
      },
    });

    await expect(provider.send({ text: "你好", context })).resolves.toEqual({
      text: "喵，我在。",
    });

    const [, init] = fetcher.mock.calls[0];
    const body = JSON.parse(init.body) as {
      system_instruction: { parts: Array<{ text: string }> };
    };
    expect(body.system_instruction.parts[0].text).toContain(
      "我是小橘，只在这里安静陪伴。",
    );
  });

  test("does not send sensitive input to the remote provider", async () => {
    const fetcher = vi.fn(async () => response({}));
    const provider = createGeminiCompanionChatProvider({
      apiKey: "test-key",
      config,
      fetcher,
    });

    await expect(
      provider.send({ text: "我的身份证号是 123" }),
    ).resolves.toEqual({
      text: "这类隐私我们先不发到云端，好吗？我可以安静陪着你。",
    });
    expect(fetcher).not.toHaveBeenCalled();
  });

  test.each([
    "my password is never-send-this",
    "Bearer abcdefghijklmnop",
    "sk-proj-12345678901234567890",
    "ghp_12345678901234567890",
    "github_pat_12345678901234567890",
    "xoxb-12345678901234567890",
    "AIza123456789012345678901234567890",
    "my medical diagnosis is never-send-this",
    "我有糖尿病",
    "I have diabetes",
    "I take metformin every day",
    "我通常吃二甲双胍，请记住。",
    "123 Main Street, Springfield",
    "明天下午三点提醒我去朝阳区建国路1号",
    "我住在北京市朝阳区建国路1号",
  ])("does not call a remote fetcher for sensitive input: %s", async (text) => {
    const fetcher = vi.fn(async () => response({}));
    const provider = createGeminiCompanionChatProvider({
      apiKey: "test-key",
      config,
      fetcher,
    });

    await expect(provider.send({ text })).resolves.toEqual({
      text: "这类隐私我们先不发到云端，好吗？我可以安静陪着你。",
    });
    expect(fetcher).not.toHaveBeenCalled();
  });

  test("blocks common English sensitive input before calling a remote fetcher", async () => {
    const fetcher = vi.fn(async () => response({}));
    const provider = createGeminiCompanionChatProvider({
      apiKey: "test-key",
      config,
      fetcher,
    });

    await expect(
      provider.send({ text: "my password is never-send-this" }),
    ).resolves.toEqual({
      text: "这类隐私我们先不发到云端，好吗？我可以安静陪着你。",
    });
    expect(fetcher).not.toHaveBeenCalled();
  });

  test("removes a sensitive history message while retaining safe history", async () => {
    const fetcher = vi.fn(async (_url: string, _init: { body: string }) =>
      response({ candidates: [{ content: { parts: [{ text: "我在呢。" }] } }] }),
    );
    const provider = createGeminiCompanionChatProvider({
      apiKey: "test-key",
      config,
      fetcher,
    });
    const sensitiveHistory = "my password is never-send-history";

    await provider.send({
      text: "今天还行",
      history: [
        { id: "safe", speaker: "user", text: "安全的历史消息" },
        { id: "sensitive", speaker: "user", text: sensitiveHistory },
      ],
    });

    const body = JSON.parse(fetcher.mock.calls[0][1].body) as {
      contents: Array<{ parts: Array<{ text: string }> }>;
    };
    const serialized = JSON.stringify(body);
    expect(serialized).not.toContain(sensitiveHistory);
    expect(serialized).toContain("安全的历史消息");
    expect(body.contents).toEqual([
      { role: "user", parts: [{ text: "安全的历史消息" }] },
      { role: "user", parts: [{ text: "今天还行" }] },
    ]);
  });

  test("filters sensitive Memory, Preference, and Evidence fields from the request", async () => {
    const fetcher = vi.fn(async (_url: string, _init: { body: string }) =>
      response({ candidates: [{ content: { parts: [{ text: "我在呢。" }] } }] }),
    );
    const provider = createGeminiCompanionChatProvider({
      apiKey: "test-key",
      config,
      fetcher,
    });
    const sensitivePreference = "my api key is never-send-preference";
    const sensitiveEvidence = "my medical diagnosis is never-send-evidence";
    const sensitiveMemory: MemoryEntry = {
      id: "sensitive-memory",
      scope: "global",
      type: "fact",
      content: "这条 Memory 的内容不应进入远程请求",
      source: "explicit",
      evidence: sensitiveEvidence,
      sourceMessageId: "memory-message",
      confidence: 0.9,
      createdAt: "2026-08-01T10:00:00.000Z",
      updatedAt: "2026-08-01T10:00:00.000Z",
      expiresAt: null,
      status: "active",
      supersedesId: null,
      deletedAt: null,
    };

    await provider.send({
      text: "今天还行",
      preferences: [
        {
          id: "global.nickname",
          scope: "global",
          category: "userProfile",
          key: "nickname",
          value: sensitivePreference,
          source: "explicit",
        },
      ],
      memories: [sensitiveMemory],
    });

    const body = JSON.parse(fetcher.mock.calls[0][1].body) as {
      system_instruction: { parts: Array<{ text: string }> };
    };
    const serialized = JSON.stringify(body);
    expect(serialized).not.toContain(sensitivePreference);
    expect(serialized).not.toContain(sensitiveEvidence);
    expect(serialized).not.toContain(sensitiveMemory.content);
  });

  test.each([
    ["Google Gemini", undefined],
    ["custom Gemini", "https://custom.example/v1beta"],
  ])("applies the same remote filter to %s", async (_label, endpoint) => {
    const fetcher = vi.fn(async (_url: string, _init: { body: string }) =>
      response({ candidates: [{ content: { parts: [{ text: "我在呢。" }] } }] }),
    );
    const provider = createGeminiCompanionChatProvider({
      apiKey: "test-key",
      config,
      endpoint,
      fetcher,
    });
    const sensitiveHistory = "my private key is never-send-provider-specific";

    await provider.send({
      text: "安全输入",
      history: [{ id: "sensitive", speaker: "user", text: sensitiveHistory }],
    });

    const body = JSON.parse(fetcher.mock.calls[0][1].body) as unknown;
    expect(JSON.stringify(body)).not.toContain(sensitiveHistory);
    expect(provider.info.kind).toBe("remote");
  });

  test("maps quota and auth failures to companion-friendly replies", async () => {
    const provider = createGeminiCompanionChatProvider({
      apiKey: "test-key",
      config,
      fetcher: async () =>
        response({ error: { message: "quota exceeded" } }, 429),
    });

    const request = provider.send({ text: "你好" });
    await expect(request).rejects.toBeInstanceOf(
      CompanionChatProviderError,
    );
    await expect(request).rejects.toMatchObject({
      status: 429,
      userMessage: "聊天额度刚刚用完啦，等一会儿再试。",
    });
    expect(DEFAULT_GEMINI_COMPANION_MODEL).toBe("gemini-2.5-flash");
  });

  test("does not surface a credential from a network error or model reply", async () => {
    const leakedKey = "sk-proj-12345678901234567890";
    const failingProvider = createGeminiCompanionChatProvider({
      apiKey: leakedKey,
      config,
      fetcher: async () => {
        throw new Error(`request failed with ${leakedKey}`);
      },
    });
    await expect(failingProvider.send({ text: "你好" })).rejects.toMatchObject({
      userMessage: "聊天服务暂时没接上，稍后再试。",
    });

    const echoProvider = createGeminiCompanionChatProvider({
      apiKey: leakedKey,
      config,
      fetcher: async () => response({
        candidates: [{ content: { parts: [{ text: leakedKey }] } }],
      }),
    });
    await expect(echoProvider.send({ text: "你好" })).resolves.toEqual({
      text: "这类隐私我们先不发到云端，好吗？我可以安静陪着你。",
    });
  });
});
