import {
  exitCompanionChat,
  shouldAutoExitCompanionChat,
  type CompanionChatState,
} from "./companionChatRuntime";
import type { PendingTaskCandidate } from "./companionTaskExtractor";

export type CompanionTaskChatExit = {
  state: CompanionChatState;
  pending: PendingTaskCandidate | null;
  exited: boolean;
};

export function exitCompanionTaskChat(
  state: CompanionChatState,
  _pending: PendingTaskCandidate | null,
): CompanionTaskChatExit {
  return {
    state: exitCompanionChat(state),
    pending: null,
    exited: true,
  };
}

export function autoExitCompanionTaskChat(
  state: CompanionChatState,
  pending: PendingTaskCandidate | null,
  now = Date.now(),
): CompanionTaskChatExit {
  if (!shouldAutoExitCompanionChat(state, now)) {
    return { state, pending, exited: false };
  }
  return exitCompanionTaskChat(state, pending);
}
