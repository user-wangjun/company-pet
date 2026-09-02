import { describe, expect, test } from "vitest";
import { buildLocalRequestHints } from "./companionActionPipeline";
import { resolveCompanionChatPipelineRoute } from "./companionChatPipeline";
import type { CompanionInput } from "./companionHarnessTypes";

const options = {
  now: "2026-08-02T12:00:00.000Z",
  timezoneOffsetMinutes: 0,
  timezone: "UTC",
};

const ordinaryQuietExpressions = [
  "我今天有点累，想安静坐一会儿。",
  "这里很安静。",
  "今晚想安静待一会儿。",
  "你安静陪我坐一会儿就好。",
  "窗外很安静，月光也很好看。",
  "我想听你陪我安静聊两句。",
  "这是一次功能测试。请用两句简短中文回应：我今天有点累，想安静坐一会儿。不要创建任务、提醒或记忆。",
] as const;

const persistentQuietPreferences = [
  "以后请安静一点陪我。",
  "今后少打扰我。",
  "从现在起陪伴时别太吵。",
  "记住，以后陪我时安静一些。",
] as const;

function chatInput(message: string): CompanionInput {
  return {
    requestId: `request-${message}`,
    sessionId: "session-quiet-routing",
    sourceMessageId: `message-${message}`,
    userId: "local-user",
    petId: "xiaoju-cat",
    message,
    currentTime: "2026-08-02T12:00:00.000Z",
    timezone: "Asia/Shanghai",
    utcOffsetMinutes: 480,
    source: "chat",
  };
}

describe("companion chat send pipeline", () => {
  test("routes task input before preference, memory, and provider", () => {
    const route = resolveCompanionChatPipelineRoute({
      text: "明天下午三点提醒我交报告。",
      sourceMessageId: "message-task",
      petId: "xiaoju-cat",
      taskOptions: options,
    });

    expect(route.kind).toBe("task-candidate");
    if (route.kind === "task-candidate") {
      expect(route.candidate.title).toBe("交报告");
    }
  });

  test("routes nickname to Preference only, including terminal punctuation", () => {
    const route = resolveCompanionChatPipelineRoute({
      text: "以后叫我阿星。",
      sourceMessageId: "message-nickname",
      petId: "xiaoju-cat",
      taskOptions: options,
    });

    expect(route.kind).toBe("preference");
  });

  test("routes postposed remember language to Memory after Preference", () => {
    const route = resolveCompanionChatPipelineRoute({
      text: "我喜欢桂花茶，请记住。",
      sourceMessageId: "message-memory",
      petId: "xiaoju-cat",
      taskOptions: options,
    });

    expect(route.kind).toBe("memory");
    if (route.kind === "memory") {
      expect(route.candidate.content).toBe("用户喜欢桂花茶");
    }
  });

  test("routes forget before ordinary provider handling and accepts punctuation", () => {
    expect(resolveCompanionChatPipelineRoute({
      text: "忘掉刚才那条。",
      sourceMessageId: "message-forget",
      petId: "xiaoju-cat",
      taskOptions: options,
    }).kind).toBe("forget");
  });

  test("uses Provider only when no domain branch claims the message", () => {
    expect(resolveCompanionChatPipelineRoute({
      text: "今天有点累。",
      sourceMessageId: "message-chat",
      petId: "xiaoju-cat",
      taskOptions: options,
    }).kind).toBe("provider");
  });

  test.each(ordinaryQuietExpressions)(
    "routes ordinary quiet expression to Provider with no local candidates: %s",
    (text) => {
      const route = resolveCompanionChatPipelineRoute({
        text,
        sourceMessageId: "message-ordinary-quiet",
        petId: "xiaoju-cat",
        taskOptions: options,
      });
      const hints = buildLocalRequestHints(chatInput(text));

      expect(route).toEqual({ kind: "provider" });
      expect(hints.route).toEqual({ kind: "provider" });
      expect(hints.localOwned).toBe(false);
      expect(hints.action).toBeNull();
      expect(hints.memoryCandidate).toBeNull();
      expect(hints.preference).toBeNull();
      expect(hints.forget).toBe(false);
    },
  );

  test.each(persistentQuietPreferences)(
    "routes explicit persistent quiet preference to local Preference: %s",
    (text) => {
      const route = resolveCompanionChatPipelineRoute({
        text,
        sourceMessageId: "message-persistent-quiet",
        petId: "xiaoju-cat",
        taskOptions: options,
      });

      expect(route.kind).toBe("preference");
      if (route.kind !== "preference") return;
      expect(route.extraction.preference).toMatchObject({
        id: "global.companionStyle",
        value: "quiet",
        source: "explicit",
      });
      const hints = buildLocalRequestHints(chatInput(text));
      expect(hints.localOwned).toBe(true);
      expect(hints.preference?.preference).toMatchObject({
        id: "global.companionStyle",
        value: "quiet",
        source: "explicit",
      });
    },
  );

  test("keeps pending task confirmation ahead of every new extraction", () => {
    expect(resolveCompanionChatPipelineRoute({
      text: "确认",
      sourceMessageId: "message-confirm",
      petId: "xiaoju-cat",
      taskOptions: options,
      hasPendingTaskCandidate: true,
    }).kind).toBe("pending-task-confirmation");
  });
});
