import { describe, expect, test } from "vitest";
import {
  INACTIVE_COMPANION_CHAT,
  createLocalCompanionChatProvider,
  createLocalCompanionChatFallbackProvider,
  enterCompanionChat,
  exitCompanionChat,
  receiveCompanionReply,
  sendCompanionMessage,
  shouldAutoExitCompanionChat,
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
});
