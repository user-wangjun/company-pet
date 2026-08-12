import {
  chooseCompanionChatCue,
  type CompanionChatConfig,
} from "./companionChat";
import type { CompanionPreference } from "./companionPreferences";
import type { CompanionChatContext } from "./companionContext";
import type { MemoryEntry } from "./companionMemory";
import {
  createCompanionContextEpoch,
  type CompanionContextEpoch,
} from "./companionContextEpoch";

export type CompanionChatMessage = {
  id: string;
  speaker: "pet" | "user";
  text: string;
  /** Internal only: visible records may contain messages from older epochs. */
  contextEpoch?: CompanionContextEpoch;
  sound?: string;
  status?: "error";
};

export type CompanionChatProviderInput = {
  text: string;
  petId?: string;
  history?: CompanionChatMessage[];
  preferences?: CompanionPreference[];
  memories?: MemoryEntry[];
  context?: CompanionChatContext;
  contextEpoch?: CompanionContextEpoch;
  signal?: AbortSignal;
};

export type CompanionChatProviderReply = {
  text: string;
};

export type CompanionChatProviderInfo = {
  kind: "local" | "remote";
  provider: string;
  target: string;
  disclosure: string;
};

export const LOCAL_COMPANION_CHAT_PROVIDER_INFO: CompanionChatProviderInfo = {
  kind: "local",
  provider: "本地 Provider",
  target: "本机",
  disclosure:
    "本地模式：不会发起网络请求。本应用不会主动保存完整原始聊天记录。",
};

export const LOCAL_COMPANION_CHAT_FALLBACK_DISCLOSURE =
  "本轮远程服务未接通，已切换为本地回复；未继续发起网络请求。";

export type CompanionChatProvider = {
  send(input: CompanionChatProviderInput): Promise<CompanionChatProviderReply>;
  info: CompanionChatProviderInfo;
};

export function shouldFallbackToLocalCompanion(
  providerInfo: CompanionChatProviderInfo,
  fallbackToLocal: boolean,
): boolean {
  return providerInfo.kind === "remote" && fallbackToLocal;
}

export type CompanionChatState =
  | { mode: "inactive" }
  | {
      mode: "active";
      messages: CompanionChatMessage[];
      contextEpoch: CompanionContextEpoch;
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
  const contextEpoch = createCompanionContextEpoch();
  return {
    mode: "active",
    contextEpoch,
    messages: [
      {
        id: messageId(now, 0),
        speaker: "pet",
        text: cue.text,
        sound: cue.sound,
        contextEpoch,
      },
    ],
    draft: "",
    pendingRequestId: null,
    pendingUserMessage: null,
    lastActiveAt: now,
  };
}

/**
 * Starts a fresh model-context boundary while keeping the visible record
 * intact. The next user message is the first message eligible for the new
 * epoch; older visible messages remain read-only companionship history.
 */
export function startCompanionContextEpoch(
  state: CompanionChatState,
): CompanionChatState {
  return state.mode === "active"
    ? { ...state, contextEpoch: createCompanionContextEpoch() }
    : state;
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
    contextEpoch: state.contextEpoch,
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

export function retryCompanionMessage(
  state: CompanionChatState,
  now = Date.now(),
): CompanionChatState {
  if (state.mode !== "active" || state.pendingRequestId) return state;

  let lastUserMessageIndex = -1;
  for (let index = state.messages.length - 1; index >= 0; index -= 1) {
    if (state.messages[index]?.speaker === "user") {
      lastUserMessageIndex = index;
      break;
    }
  }
  if (lastUserMessageIndex < 0) return state;

  const lastUserMessage = state.messages[lastUserMessageIndex];
  return sendCompanionMessage(
    {
      ...state,
      messages: state.messages.slice(0, lastUserMessageIndex),
      draft: lastUserMessage.text,
      pendingRequestId: null,
      pendingUserMessage: null,
    },
    now,
  );
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
  status?: CompanionChatMessage["status"],
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
        contextEpoch: state.contextEpoch,
        status,
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
): CompanionChatProvider {
  return {
    info: LOCAL_COMPANION_CHAT_PROVIDER_INFO,
    async send(input: CompanionChatProviderInput) {
      const replies = config.localReplies.length
        ? config.localReplies
        : ["嗯，我听着。"];
      const context = input.context;
      const systemInstruction = context?.systemInstruction ?? "";
      const hasSoulContext = systemInstruction.includes("【当前宠物 Soul");
      const hasPreferenceContext = systemInstruction.includes("【用户偏好");
      const hasSessionContext = (context?.history ?? []).some(
        (message) => message.speaker === "user",
      );
      const nickname = context
        ? systemInstruction
            .split(/\r?\n/)
            .find((line) => line.trim().startsWith("- nickname:"))
            ?.replace(/^\s*-\s*nickname:\s*/i, "")
            .trim()
        : undefined;
      const contextOffset = Number(hasSoulContext)
        + Number(hasPreferenceContext)
        + Number(hasSessionContext);
      const baseReply = replies[
        (Math.floor(random() * replies.length) + contextOffset) % replies.length
      ];
      const prefix = nickname
        ? `${nickname}，`
        : hasSessionContext
          ? "我还记得刚才聊过的，"
          : hasSoulContext
            ? "我会照着小伙伴的性格陪你，"
            : "";
      const maxReplyLength = config.style?.maxReplyLength ?? 36;
      const text = `${prefix}${baseReply}`.replace(/\s+/g, " ").trim();
      return {
        text: Array.from(text).length <= maxReplyLength
          ? text
          : `${Array.from(text).slice(0, Math.max(1, maxReplyLength - 1)).join("")}…`,
      };
    },
  };
}

export function createLocalCompanionChatFallbackProvider(
  config: CompanionChatConfig,
  random: () => number = Math.random,
): CompanionChatProvider {
  const provider = createLocalCompanionChatProvider(config, random);
  return {
    ...provider,
    info: {
      ...provider.info,
      disclosure: LOCAL_COMPANION_CHAT_FALLBACK_DISCLOSURE,
    },
  };
}
