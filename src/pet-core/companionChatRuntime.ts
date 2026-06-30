import {
  chooseCompanionChatCue,
  type CompanionChatConfig,
} from "./companionChat";
import type { CompanionPreference } from "./companionPreferences";

export type CompanionChatMessage = {
  id: string;
  speaker: "pet" | "user";
  text: string;
  sound?: string;
};

export type CompanionChatState =
  | { mode: "inactive" }
  | {
      mode: "active";
      messages: CompanionChatMessage[];
      draft: string;
      pendingRequestId: string | null;
      pendingUserMessage: CompanionChatMessage | null;
      lastActiveAt: number;
    };

export const INACTIVE_COMPANION_CHAT: CompanionChatState = { mode: "inactive" };
const AUTO_EXIT_MS = 90_000;

function messageId(now: number, index: number): string {
  return `${now}-${index}`;
}

export function enterCompanionChat(
  config: CompanionChatConfig,
  now = Date.now(),
  random: () => number = Math.random,
): CompanionChatState {
  const cue = chooseCompanionChatCue(config.openers, random);
  return {
    mode: "active",
    messages: [
      {
        id: messageId(now, 0),
        speaker: "pet",
        text: cue.text,
        sound: cue.sound,
      },
    ],
    draft: "",
    pendingRequestId: null,
    pendingUserMessage: null,
    lastActiveAt: now,
  };
}

export function updateCompanionDraft(
  state: CompanionChatState,
  draft: string,
): CompanionChatState {
  return state.mode === "active" ? { ...state, draft } : state;
}

export function sendCompanionMessage(
  state: CompanionChatState,
  now = Date.now(),
): CompanionChatState {
  if (state.mode !== "active") return state;
  const text = state.draft.trim();
  if (!text || state.pendingRequestId) return state;

  const message = {
    id: messageId(now, state.messages.length),
    speaker: "user" as const,
    text,
  };
  return {
    ...state,
    messages: [...state.messages, message],
    draft: "",
    pendingRequestId: message.id,
    pendingUserMessage: message,
    lastActiveAt: now,
  };
}

export function stopCompanionReply(state: CompanionChatState): CompanionChatState {
  if (state.mode !== "active" || !state.pendingUserMessage) return state;
  return {
    ...state,
    messages: state.messages.filter(
      (message) => message.id !== state.pendingUserMessage?.id,
    ),
    draft: state.pendingUserMessage.text,
    pendingRequestId: null,
    pendingUserMessage: null,
    lastActiveAt: Date.now(),
  };
}

export function receiveCompanionReply(
  state: CompanionChatState,
  text: string,
  now = Date.now(),
): CompanionChatState {
  if (state.mode !== "active") return state;
  return {
    ...state,
    messages: [
      ...state.messages,
      {
        id: messageId(now, state.messages.length),
        speaker: "pet",
        text,
      },
    ],
    pendingRequestId: null,
    pendingUserMessage: null,
    lastActiveAt: now,
  };
}

export function shouldAutoExitCompanionChat(
  state: CompanionChatState,
  now = Date.now(),
): boolean {
  return (
    state.mode === "active" &&
    !state.pendingRequestId &&
    !state.draft.trim() &&
    now - state.lastActiveAt > AUTO_EXIT_MS
  );
}

export function exitCompanionChat(_state: CompanionChatState): CompanionChatState {
  return INACTIVE_COMPANION_CHAT;
}

export function createLocalCompanionChatProvider(
  config: CompanionChatConfig,
  random: () => number = Math.random,
) {
  return {
    async send(_input: { text: string; preferences?: CompanionPreference[] }) {
      const replies = config.localReplies.length
        ? config.localReplies
        : ["嗯，我听着。"];
      return { text: replies[Math.floor(random() * replies.length)] };
    },
  };
}
