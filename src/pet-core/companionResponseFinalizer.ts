import type {
  ActionExecutionResult,
  CompanionActionType,
  CompanionForgetExecutionResult,
  CompanionPreferenceExecutionResult,
  CompanionProactivePreferenceExecutionResult,
  MemoryPolicyResult,
} from "./companionHarnessTypes";
import { containsSensitiveCompanionText } from "./companionPrivacy";

const MAX_FINAL_DISPLAY_LENGTH = 120;
const MAX_FINAL_REPLY_LENGTH = 2_000;

export interface CompanionResponseFinalizerInput {
  replyDraft: string | null | undefined;
  actions: readonly ActionExecutionResult[];
  memory?: MemoryPolicyResult;
  proactivePreference?: CompanionProactivePreferenceExecutionResult;
  preference?: CompanionPreferenceExecutionResult;
  forget?: CompanionForgetExecutionResult;
}

function safeDisplay(value: unknown): string | null {
  if (typeof value !== "string" || containsSensitiveCompanionText(value)) return null;
  const normalized = value.trim();
  if (!normalized) return null;
  const characters = Array.from(normalized);
  return characters.length <= MAX_FINAL_DISPLAY_LENGTH
    ? normalized
    : `${characters.slice(0, MAX_FINAL_DISPLAY_LENGTH - 1).join("")}…`;
}

function safeReplyDraft(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  if (!normalized || Array.from(normalized).length > MAX_FINAL_REPLY_LENGTH) return null;
  if (containsSensitiveCompanionText(normalized)) return null;
  return normalized;
}

function actionLabel(type: CompanionActionType): string {
  switch (type) {
    case "create_task": return "待办";
    case "create_reminder": return "提醒";
    case "complete_task": return "任务";
    case "update_reminder": return "提醒";
    case "cancel_task": return "任务";
    case "postpone_task": return "任务";
    case "reschedule_task": return "任务";
  }
}

function targetText(result: ActionExecutionResult): string {
  const title = safeDisplay(result.displayData?.title);
  const reference = safeDisplay(result.displayData?.reference);
  return title ?? reference ?? actionLabel(result.type);
}

function oneResult(result: ActionExecutionResult): string {
  const target = targetText(result);
  const triggerTime = safeDisplay(result.displayData?.triggerTime);
  switch (result.status) {
    case "succeeded":
      if (result.type === "create_reminder") {
        return triggerTime
          ? `已经为你创建“${target}”提醒，时间是 ${triggerTime}。`
          : `已经为你创建“${target}”提醒。`;
      }
      if (result.type === "create_task") return `已经为你创建“${target}”待办。`;
      if (result.type === "complete_task") return `已经完成“${target}”。`;
      if (result.type === "update_reminder") {
        return triggerTime
          ? `已经把“${target}”提醒改到 ${triggerTime}。`
          : `已经更新“${target}”提醒。`;
      }
      if (result.type === "cancel_task") return `已经取消“${target}”任务。`;
      if (result.type === "postpone_task") {
        return triggerTime
          ? `已经把“${target}”任务延期到 ${triggerTime}。`
          : `已经延期“${target}”任务。`;
      }
      return triggerTime
        ? `已经把“${target}”任务改期到 ${triggerTime}。`
        : `已经改期“${target}”任务。`;
    case "duplicate":
      if (result.type === "create_task" || result.type === "create_reminder") {
        return `“${target}”已有记录，没有重复创建。`;
      }
      if (result.type === "complete_task") {
        return `“${target}”任务已经完成，本次无需重复完成。`;
      }
      if (result.type === "update_reminder") {
        return triggerTime
          ? `“${target}”提醒时间未发生变化，已是 ${triggerTime}。`
          : `“${target}”提醒时间未发生变化，无需重复更新。`;
      }
      if (result.type === "cancel_task") {
        return `“${target}”任务已经取消，本次无需重复取消。`;
      }
      if (result.type === "postpone_task") {
        return `“${target}”任务时间没有变化，无需重复延期。`;
      }
      return `“${target}”任务时间没有变化，无需重复改期。`;
    case "not_found":
      return `没有找到要处理的“${target}”。`;
    case "ambiguous":
      return `我找到了多个可能的“${target}”，请说得更具体一些。`;
    case "confirmation_required":
      return `“${target}”还需要你确认具体事项和时间，我暂时没有写入。`;
    case "rejected":
      return `这次没有执行“${target}”，因为请求没有通过本地安全检查。`;
    case "failed":
      return `“${target}”没有处理成功，当前记录没有被确认修改。`;
    case "cancelled":
      return `“${target}”这次操作已停止，没有继续执行。`;
  }
}

function proactivePreferenceTarget(result: CompanionProactivePreferenceExecutionResult): string {
  return safeDisplay(result.displayData?.title) ?? "这项主动提醒";
}

function oneProactivePreferenceResult(
  result: CompanionProactivePreferenceExecutionResult,
): string {
  const target = proactivePreferenceTarget(result);
  switch (result.status) {
    case "succeeded":
      if (result.action === "mute") return `已经停止提醒“${target}”。`;
      if (result.action === "reduce") return `已经减少“${target}”的提醒频率。`;
      return `已经改由另一只宠物提醒“${target}”。`;
    case "duplicate":
      if (result.action === "mute") return `“${target}”已经是停止提醒设置，无需重复修改。`;
      if (result.action === "reduce") return `“${target}”已经是低频提醒设置，无需重复修改。`;
      return `“${target}”已经使用其他宠物提醒，无需重复修改。`;
    case "not_found":
      return `没有找到要调整的“${target}”主动提醒。`;
    case "ambiguous":
      return `我找到了多个可能的“${target}”主动提醒，请说得更具体一些。`;
    case "confirmation_required":
      return `“${target}”还需要你补充明确的提醒目标或可切换宠物，我暂时没有修改。`;
    case "rejected":
      return `这次没有修改“${target}”的主动提醒偏好，因为请求没有通过本地安全检查。`;
    case "failed":
      return `“${target}”的主动提醒偏好没有保存成功，本次没有确认修改。`;
    case "cancelled":
      return `“${target}”的主动提醒偏好调整已停止，没有继续修改。`;
  }
}

function onePreferenceResult(result: CompanionPreferenceExecutionResult): string {
  const labels: Record<string, string> = {
    nickname: "这个称呼",
    replyStyle: "回复风格",
    companionStyle: "陪伴方式",
    eyeCare: "护眼提醒偏好",
  };
  const target = labels[result.displayData?.key ?? ""] ?? "这个偏好";
  switch (result.status) {
    case "succeeded": return `已经记住${target}了。`;
    case "duplicate": return `${target}已经是这样，不需要重复修改。`;
    case "failed": return `${target}没有保存成功，我不会假装已经记住。`;
    case "cancelled": return `${target}的修改已停止，没有继续保存。`;
  }
}

function oneForgetResult(result: CompanionForgetExecutionResult): string {
  switch (result.status) {
    case "succeeded": return "好，我忘掉刚才那条。";
    case "noop": return "最近没有可删除的偏好或 Memory。";
    case "failed": return "我暂时没能完整忘掉这条内容，请稍后再试。";
    case "cancelled": return "这次忘记操作已停止，没有继续修改。";
  }
}

function memoryNotice(memory: MemoryPolicyResult): string | null {
  const decisions = memory.decisions;
  if (decisions.some((item) => item.status === "cancelled")) return null;
  if (decisions.length === 1) {
    switch (decisions[0].status) {
      case "inserted":
      case "superseded":
      case "updated":
        return "已经记住了。";
      case "duplicate":
        return "这条已经记着了。";
      case "confirmation_required":
        return "我还没有保存这条 Memory，请你明确确认后我再记住。";
      case "failed":
        return "Memory 没有保存成功，我不会假装已经记住。";
      case "rejected":
        return "这条信息没有通过本地安全检查，我没有保存。";
      case "expired":
        return "这条信息已经过期，我没有保存。";
      default:
        return null;
    }
  }

  const counts = {
    succeeded: 0,
    duplicate: 0,
    confirmationRequired: 0,
    failed: 0,
    rejected: 0,
    expired: 0,
  };
  for (const item of decisions) {
    switch (item.status) {
      case "inserted":
      case "superseded":
      case "updated":
        counts.succeeded += 1;
        break;
      case "duplicate":
        counts.duplicate += 1;
        break;
      case "confirmation_required":
        counts.confirmationRequired += 1;
        break;
      case "failed":
        counts.failed += 1;
        break;
      case "rejected":
        counts.rejected += 1;
        break;
      case "expired":
        counts.expired += 1;
        break;
      default:
        break;
    }
  }

  const clauses: string[] = [];
  if (counts.succeeded > 0) clauses.push(`已记住 ${counts.succeeded} 条`);
  if (counts.duplicate > 0) clauses.push(`${counts.duplicate} 条已经记着`);
  if (counts.confirmationRequired > 0) {
    clauses.push(`${counts.confirmationRequired} 条尚未保存，需要你确认`);
  }
  if (counts.failed > 0) clauses.push(`${counts.failed} 条保存失败`);
  if (counts.rejected > 0) clauses.push(`${counts.rejected} 条未通过本地安全检查`);
  if (counts.expired > 0) clauses.push(`${counts.expired} 条因已过期而未保存`);
  if (!clauses.length) return null;
  const [first, ...rest] = clauses;
  return `${first}${rest.length ? `；${rest.map((clause) => `另有 ${clause}`).join("；")}` : ""}。`;
}

function memoryWasCancelled(memory: MemoryPolicyResult): boolean {
  return memory.status === "cancelled"
    || memory.decisions.some((item) => item.status === "cancelled");
}

function finalizeMemory(
  replyDraft: string | null | undefined,
  memory: MemoryPolicyResult,
): string | null {
  if (memoryWasCancelled(memory)) return null;
  const notice = memoryNotice(memory);
  // Once a Memory candidate exists, the model draft is not authoritative for
  // whether or what was saved. Returning the local status aggregate alone
  // also prevents candidate content from leaking back through model prose.
  return notice ?? safeReplyDraft(replyDraft);
}

/**
 * Finalizes Action-bearing responses locally. The model draft is deliberately
 * ignored once an Action candidate exists, so a model cannot turn a failed
 * domain write into a successful sentence.
 */
export function finalizeCompanionResponse(
  input: CompanionResponseFinalizerInput,
): string | null {
  if (input.memory && memoryWasCancelled(input.memory)) return null;
  if (input.preference) return onePreferenceResult(input.preference);
  if (input.forget) return oneForgetResult(input.forget);
  if (input.proactivePreference) {
    return oneProactivePreferenceResult(input.proactivePreference);
  }
  if (input.actions.length === 0) {
    if (input.memory && input.memory.decisions.length > 0) {
      return finalizeMemory(input.replyDraft, input.memory);
    }
    return safeReplyDraft(input.replyDraft);
  }
  const actionText = input.actions.length === 1
    ? oneResult(input.actions[0])
    : input.actions.map(oneResult).join("\n");
  const notice = input.memory && input.memory.decisions.length > 0
    ? memoryNotice(input.memory)
    : null;
  return notice ? `${actionText}\n${notice}` : actionText;
}

export const companionResponseFinalizer = {
  finalize: finalizeCompanionResponse,
};
