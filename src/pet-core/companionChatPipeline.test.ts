import { describe, expect, test } from "vitest";
import { resolveCompanionChatPipelineRoute } from "./companionChatPipeline";

const options = {
  now: "2026-08-02T12:00:00.000Z",
  timezoneOffsetMinutes: 0,
  timezone: "UTC",
};

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
