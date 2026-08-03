import { describe, expect, it } from "vitest";
import { enterCompanionChat, receiveCompanionReply } from "./companionChatRuntime";
import {
  extractTaskCandidate,
  getPendingTaskCandidateForPet,
} from "./companionTaskExtractor";
import { autoExitCompanionTaskChat, exitCompanionTaskChat } from "./companionTaskSession";

const NOW = "2026-08-02T12:00:00.000Z";
const OPTIONS = { now: NOW, timezoneOffsetMinutes: 0, timezone: "UTC" };
const config = { openers: [{ text: "喵？" }], localReplies: [] };

describe("companion task candidate lifecycle", () => {
  it("clears an old candidate when automatic chat timeout exits", () => {
    const chat = receiveCompanionReply(enterCompanionChat(config, 1_000), "收到", 2_000);
    const candidate = extractTaskCandidate("明天三点交报告", "message-timeout", OPTIONS)!;
    const pending = { petId: "xiaoju-cat", candidate };

    const exited = autoExitCompanionTaskChat(chat, pending, 92_002);

    expect(exited.exited).toBe(true);
    expect(exited.pending).toBeNull();
    expect(getPendingTaskCandidateForPet(exited.pending, "xiaoju-cat")).toBeNull();
    expect(getPendingTaskCandidateForPet(pending, "xiaoju-cat")).toBe(candidate);
    expect(getPendingTaskCandidateForPet(exited.pending, "xiaoju-cat")).not.toBe(candidate);
  });

  it.each(["explicit exit", "pet switch", "outside click"])("clears a candidate on %s", () => {
    const chat = enterCompanionChat(config, 1_000);
    const candidate = extractTaskCandidate("明天三点交报告", "message-exit", OPTIONS)!;
    const exited = exitCompanionTaskChat(chat, { petId: "xiaoju-cat", candidate });

    expect(exited.state.mode).toBe("inactive");
    expect(exited.pending).toBeNull();
  });

  it("keeps a candidate while chat remains active and not idle", () => {
    const candidate = extractTaskCandidate("明天三点交报告", "message-active", OPTIONS)!;
    const pending = { petId: "xiaoju-cat", candidate };
    const chat = enterCompanionChat(config, 1_000);

    const result = autoExitCompanionTaskChat(chat, pending, 2_000);

    expect(result.exited).toBe(false);
    expect(result.pending).toBe(pending);
  });
});
