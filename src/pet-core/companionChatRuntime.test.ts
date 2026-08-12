import { describe, expect, test } from "vitest";
import {
  INACTIVE_COMPANION_CHAT,
  createLocalCompanionChatProvider,
  createLocalCompanionChatFallbackProvider,
  enterCompanionChat,
  exitCompanionChat,
  receiveCompanionReply,
  retryCompanionMessage,
  sendCompanionMessage,
  shouldFallbackToLocalCompanion,
  shouldAutoExitCompanionChat,
  startCompanionContextEpoch,
  stopCompanionReply,
  updateCompanionDraft,
} from "./companionChatRuntime";
import type { CompanionChatConfig } from "./companionChat";

const config: CompanionChatConfig = {
  openers: [{ text: "喵？", sound: "chatOpenMew" }],
  localReplies: ["嗯，我听着。"],
};

describe("companion chat runtime", () => {
  test("enters with a pet opener cue", () => {
    const state = enterCompanionChat(config, 1000, () => 0);

    expect(state.mode).toBe("active");
    if (state.mode !== "active") throw new Error("Expected active chat");
    expect(state.messages).toMatchObject([
      { speaker: "pet", text: "喵？", sound: "chatOpenMew" },
    ]);
  });

  test("sends a user message and can stop to restore it to draft", () => {
    const active = updateCompanionDraft(enterCompanionChat(config), "写错了");
    const sent = sendCompanionMessage(active, 1200);

    if (sent.mode !== "active") throw new Error("Expected active chat");
    expect(sent.draft).toBe("");
    expect(sent.pendingUserMessage?.text).toBe("写错了");
    expect(sent.messages[sent.messages.length - 1]).toMatchObject({
      speaker: "user",
      text: "写错了",
    });
    expect(stopCompanionReply(sent)).toMatchObject({
      draft: "写错了",
      pendingUserMessage: null,
      pendingRequestId: null,
    });
  });

  test("starts a new internal epoch without removing visible messages", () => {
    const first = sendCompanionMessage(
      updateCompanionDraft(enterCompanionChat(config, 1000), "旧话题"),
      1100,
    );
    if (first.mode !== "active") throw new Error("Expected active chat");

    const replied = receiveCompanionReply(first, "旧话题回复", 1200);
    if (replied.mode !== "active") throw new Error("Expected active chat");
    const nextEpochState = startCompanionContextEpoch(replied);
    if (nextEpochState.mode !== "active") throw new Error("Expected active chat");
    const next = sendCompanionMessage(
      updateCompanionDraft(nextEpochState, "新话题"),
      1300,
    );

    if (next.mode !== "active") throw new Error("Expected active chat");
    expect(next.contextEpoch).not.toBe(first.contextEpoch);
    expect(next.messages.map((message) => message.text)).toEqual([
      "喵？",
      "旧话题",
      "旧话题回复",
      "新话题",
    ]);
    expect(next.messages[1]?.contextEpoch).toBe(first.contextEpoch);
    expect(next.messages[3]?.contextEpoch).toBe(next.contextEpoch);
  });

  test("retries the latest user turn without keeping the previous pet reply", () => {
    const firstTurn = sendCompanionMessage(
      updateCompanionDraft(enterCompanionChat(config, 1000), "第一句话"),
      1200,
    );
    const replied = receiveCompanionReply(firstTurn, "第一句回复", 1300);
    const retried = retryCompanionMessage(replied, 1400);

    if (retried.mode !== "active") throw new Error("Expected active chat");
    expect(retried.messages.map((message) => message.text)).toEqual(["喵？", "第一句话"]);
    expect(retried.pendingUserMessage?.text).toBe("第一句话");
    expect(retried.pendingRequestId).toBe(retried.pendingUserMessage?.id);
  });

  test("exits without restoring the previous record into a new Provider context", () => {
    const active = receiveCompanionReply(
      sendCompanionMessage(
        updateCompanionDraft(enterCompanionChat(config, 1000), "旧话题"),
        1200,
      ),
      "旧话题回复",
      1300,
    );

    expect(exitCompanionChat(active)).toEqual(INACTIVE_COMPANION_CHAT);
    const next = enterCompanionChat(config, 1500);
    if (next.mode !== "active") throw new Error("Expected active chat");
    expect(next.messages.map((message) => message.text)).toEqual(["喵？"]);
    expect(next.messages.map((message) => message.text)).not.toContain("旧话题");
    expect(next.messages.map((message) => message.text)).not.toContain("旧话题回复");
  });

  test("receives a pet reply and exits after idle timeout", () => {
    const sent = sendCompanionMessage(
      updateCompanionDraft(enterCompanionChat(config, 1000), "你好"),
      1500,
    );
    const replied = receiveCompanionReply(sent, "嗯，我听着。", 2000);

    if (replied.mode !== "active") throw new Error("Expected active chat");
    expect(replied.pendingRequestId).toBeNull();
    expect(replied.messages[replied.messages.length - 1]).toMatchObject({
      speaker: "pet",
      text: "嗯，我听着。",
    });
    expect(shouldAutoExitCompanionChat(replied, 2000 + 90_001)).toBe(true);
    expect(exitCompanionChat(replied)).toEqual(INACTIVE_COMPANION_CHAT);
  });

  test("local provider returns configured short replies", async () => {
    await expect(
      createLocalCompanionChatProvider(config, () => 0).send({ text: "今天还行" }),
    ).resolves.toEqual({ text: "嗯，我听着。" });
  });

  test("local provider uses assembled Soul, Preference, and session context", async () => {
    await expect(
      createLocalCompanionChatProvider(
        { ...config, localReplies: ["我在这里。", "慢慢说。"] },
        () => 0,
      ).send({
        text: "继续刚才的话",
        context: {
          petId: "xiaoju-cat",
          systemInstruction: [
            "【当前宠物 Soul｜只读人格资料】",
            "我是小橘，只在这里安静陪伴。",
            "【用户偏好｜低优先级普通参考】",
            "- nickname: 小主人",
          ].join("\n"),
          history: [{ id: "user-1", speaker: "user", text: "刚才那件事" }],
          userInput: "继续刚才的话",
        },
      }),
    ).resolves.toEqual({ text: "小主人，慢慢说。" });
  });

  test("remote failure fallback is disclosed as local and does not retry remotely", async () => {
    const fallback = createLocalCompanionChatFallbackProvider(config, () => 0);

    expect(fallback.info).toMatchObject({ kind: "local", target: "本机" });
    expect(fallback.info.disclosure).toContain("本轮远程服务未接通，已切换为本地回复");
    await expect(fallback.send({ text: "你好" })).resolves.toEqual({
      text: "嗯，我听着。",
    });
  });

  test("keeps a non-fallback provider failure marked for the page retry state", () => {
    const sent = sendCompanionMessage(
      updateCompanionDraft(enterCompanionChat(config, 1000), "请再试一次"),
      1200,
    );
    const errored = receiveCompanionReply(
      sent,
      "聊天服务暂时没接上，稍后再试。",
      1300,
      "error",
    );

    if (errored.mode !== "active") throw new Error("Expected active chat");
    expect(errored.messages[errored.messages.length - 1]).toMatchObject({
      speaker: "pet",
      status: "error",
      text: "聊天服务暂时没接上，稍后再试。",
    });
  });

  test("only falls back when the selected remote setting allows it", () => {
    const remoteInfo = {
      kind: "remote" as const,
      provider: "Google Gemini",
      target: "https://generativelanguage.googleapis.com/v1beta",
      disclosure: "远程模式",
    };
    expect(shouldFallbackToLocalCompanion(remoteInfo, true)).toBe(true);
    expect(shouldFallbackToLocalCompanion(remoteInfo, false)).toBe(false);
    expect(shouldFallbackToLocalCompanion({ ...remoteInfo, kind: "local" }, true)).toBe(false);
  });
});
