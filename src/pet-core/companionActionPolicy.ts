import { containsSensitiveCompanionText } from "./companionPrivacy";
import type {
  ActionExecutionResult,
  ActionExecutionStatus,
  ActionCandidate,
  CompanionActionCandidate,
  CompanionActionType,
  CompanionInput,
  LocalCompatibilityActionCandidate,
} from "./companionHarnessTypes";
import type { ActionPolicyContext, ActionPolicyDecision, LocalActionEvidence } from "./companionActionTypes";
import {
  findDuplicateTask,
  findTaskReference,
  getTaskCandidateDedupKey,
  normalizeTaskTitle,
  type TaskCandidate,
} from "./companionTaskExtractor";
import { currentLocalDateKeyFromUtcOffset, toLegacyTaskExtractorTimezoneOffsetMinutes } from "./companionTaskTimezone";
import type { Task, TaskDatabase } from "../task-core/types";

const FORBIDDEN_PROVIDER_ID_FIELDS = new Set(["taskId", "reminderId", "instanceId"]);
const DATE_ONLY_PATTERN = /^\d{4}-\d{2}-\d{2}$/u;
const MAX_SOURCE_MESSAGE_ID_LENGTH = 160;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function boundedString(value: unknown, maxLength = 240): value is string {
  return typeof value === "string"
    && value.trim().length > 0
    && Array.from(value.trim()).length <= maxLength;
}

function hasAllowedPayloadFields(
  type: CompanionActionType,
  payload: Record<string, unknown>,
): boolean {
  const allowed = type === "create_task"
    ? new Set(["title", "dueAt"])
    : type === "create_reminder"
      ? new Set(["title", "triggerAt", "timezone"])
      : type === "complete_task" || type === "cancel_task"
        ? new Set(["reference"])
        : type === "update_reminder"
          ? new Set(["reference", "triggerAt", "timezone"])
          : new Set(["reference", "dueAt", "remindAt"]);
  return Object.keys(payload).every((key) => allowed.has(key));
}

function knownModelActionType(value: unknown): value is ActionCandidate["type"] {
  return value === "create_task"
    || value === "create_reminder"
    || value === "complete_task"
    || value === "update_reminder";
}

function knownLocalActionType(value: unknown): value is LocalCompatibilityActionCandidate["type"] {
  return value === "cancel_task"
    || value === "postpone_task"
    || value === "reschedule_task";
}

function hasOnlySafePayloadFields(payload: Record<string, unknown>): boolean {
  return !Object.keys(payload).some((key) => FORBIDDEN_PROVIDER_ID_FIELDS.has(key));
}

export function isFormalCompanionActionCandidate(
  value: unknown,
): value is ActionCandidate {
  if (!isRecord(value)
    || !boundedString(value.sourceMessageId, MAX_SOURCE_MESSAGE_ID_LENGTH)
    || (value.intent !== "explicit" && value.intent !== "implicit")
    || !knownModelActionType(value.type)
    || !isRecord(value.payload)
    || !hasOnlySafePayloadFields(value.payload)
    || !hasAllowedPayloadFields(value.type, value.payload)) return false;

  const payload = value.payload;
  if (value.type === "create_task") {
    return boundedString(payload.title)
      && (payload.dueAt === undefined || boundedString(payload.dueAt));
  }
  if (value.type === "create_reminder") {
    return boundedString(payload.title)
      && boundedString(payload.triggerAt)
      && boundedString(payload.timezone);
  }
  if (value.type === "complete_task") {
    return boundedString(payload.reference);
  }
  return boundedString(payload.reference)
    && boundedString(payload.triggerAt)
    && boundedString(payload.timezone);
}

export function isLocalCompatibilityActionCandidate(
  value: unknown,
): value is LocalCompatibilityActionCandidate {
  if (!isRecord(value)
    || !boundedString(value.sourceMessageId, MAX_SOURCE_MESSAGE_ID_LENGTH)
    || !knownLocalActionType(value.type)
    || !isRecord(value.payload)
    || !hasOnlySafePayloadFields(value.payload)
    || !hasAllowedPayloadFields(value.type, value.payload)) return false;
  const payload = value.payload;
  if (value.type === "cancel_task") return boundedString(payload.reference);
  return boundedString(payload.reference)
    && boundedString(payload.dueAt)
    && (payload.remindAt === undefined || boundedString(payload.remindAt));
}

function candidateType(value: CompanionActionCandidate): CompanionActionType {
  return value.type;
}

function result(
  candidate: CompanionActionCandidate,
  status: ActionExecutionStatus,
  errorCode?: string,
  displayData?: Record<string, string>,
): ActionExecutionResult {
  return {
    type: candidateType(candidate),
    status,
    ...(errorCode ? { errorCode } : {}),
    ...(displayData ? { displayData } : {}),
  };
}

function normalizedTime(value: string | null | undefined): string | null {
  if (!value || !value.trim()) return null;
  const trimmed = value.trim();
  if (DATE_ONLY_PATTERN.test(trimmed)) return `date:${trimmed}`;
  const parsed = Date.parse(trimmed);
  return Number.isFinite(parsed) ? `minute:${Math.floor(parsed / 60_000)}` : null;
}

function sameTime(left: string | null | undefined, right: string | null | undefined): boolean {
  const normalizedLeft = normalizedTime(left);
  const normalizedRight = normalizedTime(right);
  return normalizedLeft !== null && normalizedLeft === normalizedRight;
}

function currentLocalDateKey(input: CompanionInput): string {
  // CompanionInput uses local time minus UTC. Keep this convention local to
  // policy; it must not be passed through the legacy Task Extractor sign.
  return currentLocalDateKeyFromUtcOffset(input.currentTime, input.utcOffsetMinutes);
}

function isFutureTime(
  value: string | null | undefined,
  input: CompanionInput,
  allowDateOnly: boolean,
): "valid" | "past" | "invalid" {
  if (!boundedString(value)) return "invalid";
  const trimmed = value.trim();
  if (DATE_ONLY_PATTERN.test(trimmed)) {
    if (!allowDateOnly) return "invalid";
    return trimmed >= currentLocalDateKey(input) ? "valid" : "past";
  }
  const timestamp = Date.parse(trimmed);
  const current = Date.parse(input.currentTime);
  if (!Number.isFinite(timestamp) || !Number.isFinite(current)) return "invalid";
  return timestamp > current ? "valid" : "past";
}

function validTimezone(value: string | null | undefined, input: CompanionInput): boolean {
  if (!boundedString(value) || value.trim() !== input.timezone.trim()) return false;
  if (value.trim() === "local") return true;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: value.trim() }).format();
    return true;
  } catch {
    return false;
  }
}

function candidateTarget(candidate: CompanionActionCandidate): string | null {
  if (candidate.type === "create_task" || candidate.type === "create_reminder") {
    return candidate.payload.title;
  }
  return candidate.payload.reference;
}

function candidateTime(candidate: CompanionActionCandidate): string | null {
  if (candidate.type === "create_task") return candidate.payload.dueAt ?? null;
  if (candidate.type === "create_reminder" || candidate.type === "update_reminder") {
    return candidate.payload.triggerAt;
  }
  if (candidate.type === "postpone_task" || candidate.type === "reschedule_task") {
    return candidate.payload.dueAt;
  }
  return null;
}

function candidateTimezone(candidate: CompanionActionCandidate): string | null {
  if (candidate.type === "create_reminder" || candidate.type === "update_reminder") {
    return candidate.payload.timezone;
  }
  return null;
}

function isTerminalTask(task: Task): boolean {
  return Boolean(task.deletedAt) || task.status === "completed" || task.status === "cancelled";
}

function terminalReference(database: TaskDatabase, reference: string): Task | null {
  const match = findTaskReference(database, reference, true);
  return match.status === "found" && match.task && isTerminalTask(match.task)
    ? match.task
    : null;
}

function duplicateForCreate(
  database: TaskDatabase,
  candidate: ActionCandidate,
  evidence: LocalActionEvidence,
): Task | null {
  const title = candidate.type === "create_task" || candidate.type === "create_reminder"
    ? candidate.payload.title
    : "";
  const dueAt = candidate.type === "create_task"
    ? candidate.payload.dueAt ?? null
    : evidence.dueAt;
  const duplicateCandidate: TaskCandidate = {
    title,
    dueAt,
    schedulePrecision: dueAt && !DATE_ONLY_PATTERN.test(dueAt) ? "datetime" : "date",
    remindAt: candidate.type === "create_reminder" ? candidate.payload.triggerAt : null,
    timezone: evidence.timezone ?? undefined,
    // duplicateForCreate builds a legacy TaskCandidate at the Harness
    // boundary, so it needs the old Date#getTimezoneOffset sign.
    timezoneOffsetMinutes: toLegacyTaskExtractorTimezoneOffsetMinutes(evidence.utcOffsetMinutes),
    sourceMessageId: evidence.sourceMessageId,
    evidence: evidence.evidence,
    confidence: 1,
    riskLevel: "low",
    explicitness: "explicit",
    needsConfirmation: false,
    confirmationReason: null,
    reminderRequested: candidate.type === "create_reminder",
  };
  if (!getTaskCandidateDedupKey(duplicateCandidate)) return null;
  const duplicateTask = findDuplicateTask(database, duplicateCandidate);
  if (candidate.type === "create_task") return duplicateTask;
  if (candidate.type !== "create_reminder") return null;
  if (!duplicateTask) return null;
  return database.tasks.find((task) => {
    if (task.id !== duplicateTask.id) return false;
    return database.reminders.some((reminder) =>
      reminder.taskId === task.id
      && reminder.status === "active"
      && !reminder.deletedAt
      && sameTime(reminder.remindAt, candidate.payload.triggerAt),
    );
  }) ?? null;
}

function normalizedIdempotencyKey(
  input: CompanionInput,
  candidate: CompanionActionCandidate,
): string {
  const target = normalizeTaskTitle(candidateTarget(candidate) ?? "") || "none";
  const time = normalizedTime(candidateTime(candidate)) ?? "none";
  return [input.sessionId, input.sourceMessageId, candidate.type, target, time].join("|");
}

function matchesEvidence(
  input: CompanionInput,
  candidate: CompanionActionCandidate,
  evidence: LocalActionEvidence,
): boolean {
  if (evidence.sourceMessageId !== input.sourceMessageId) return false;
  if (evidence.actionType !== candidate.type) return false;
  const target = candidateTarget(candidate);
  if (!target || !evidence.normalizedTarget) return false;
  if (normalizeTaskTitle(target) !== evidence.normalizedTarget) return false;
  if (candidate.type === "create_task") {
    return Boolean(candidate.payload.dueAt)
      && sameTime(candidate.payload.dueAt, evidence.dueAt);
  }
  if (candidate.type === "create_reminder" || candidate.type === "update_reminder") {
    return sameTime(candidate.payload.triggerAt, evidence.triggerAt)
      && candidateTimezone(candidate) === evidence.timezone;
  }
  if (candidate.type === "postpone_task" || candidate.type === "reschedule_task") {
    return sameTime(candidate.payload.dueAt, evidence.dueAt)
      && (!candidate.payload.remindAt || sameTime(candidate.payload.remindAt, evidence.triggerAt));
  }
  return true;
}

function actionNeedsConfirmation(evidence: LocalActionEvidence, candidate: CompanionActionCandidate): boolean {
  const modelIntent = "intent" in candidate ? candidate.intent : "explicit";
  return modelIntent !== "explicit"
    || evidence.explicitness !== "explicit"
    || evidence.requiresConfirmation
    || evidence.riskLevel !== "low";
}

function referenceMatch(
  database: TaskDatabase,
  reference: string,
): { task: Task | null; status: "found" | "not_found" | "ambiguous" } {
  const match = findTaskReference(database, reference);
  return match;
}

function assertTarget(
  database: TaskDatabase,
  candidate: CompanionActionCandidate,
): ActionExecutionResult | null {
  if (candidate.type === "create_task" || candidate.type === "create_reminder") return null;
  const match = referenceMatch(database, candidate.payload.reference);
  if (match.status === "ambiguous") return result(candidate, "ambiguous", "multiple-targets");
  if (match.status === "not_found" || !match.task) {
    return terminalReference(database, candidate.payload.reference)
      ? result(candidate, "rejected", "terminal-target")
      : result(candidate, "not_found", "target-not-found");
  }
  if (isTerminalTask(match.task)) return result(candidate, "rejected", "terminal-target");
  if (candidate.type === "update_reminder") {
    const reminders = database.reminders.filter((reminder) =>
      reminder.taskId === match.task!.id
      && reminder.status === "active"
      && !reminder.deletedAt,
    );
    if (reminders.length === 0) return result(candidate, "not_found", "active-reminder-not-found");
    if (reminders.length > 1) return result(candidate, "ambiguous", "multiple-active-reminders");
  }
  return null;
}

/**
 * Authorizes a candidate against freshly rebuilt local evidence and a fresh
 * TaskDatabase snapshot. It never trusts model intent, evidence, or IDs.
 */
export function authorizeCompanionAction(
  context: ActionPolicyContext,
): ActionPolicyDecision {
  const { input, candidate, evidence, database, signal } = context;
  const action = candidate as unknown;
  if (signal.aborted || !context.isCurrent()) {
    return { status: "rejected", result: result(candidate, "cancelled", "turn-invalidated") };
  }
  if (!isFormalCompanionActionCandidate(action) && !isLocalCompatibilityActionCandidate(action)) {
    return { status: "rejected", result: result(candidate, "rejected", "invalid-action-schema") };
  }
  if (candidate.sourceMessageId !== input.sourceMessageId) {
    return { status: "rejected", result: result(candidate, "rejected", "source-message-mismatch") };
  }
  const rawPayload = (candidate as unknown as { payload?: unknown }).payload;
  if (!isRecord(rawPayload) || !hasOnlySafePayloadFields(rawPayload)) {
    return { status: "rejected", result: result(candidate, "rejected", "forbidden-local-id") };
  }
  if (
    containsSensitiveCompanionText(input.message)
    || Object.values(rawPayload).some((value) => typeof value === "string" && containsSensitiveCompanionText(value))
    || (evidence?.evidence ? containsSensitiveCompanionText(evidence.evidence) : false)
  ) {
    return { status: "rejected", result: result(candidate, "rejected", "sensitive-content") };
  }
  if (!evidence) {
    return { status: "rejected", result: result(candidate, "rejected", "missing-local-evidence") };
  }
  if (actionNeedsConfirmation(evidence, candidate)) {
    return { status: "rejected", result: result(candidate, "confirmation_required", "explicit-confirmation-required") };
  }
  if (!matchesEvidence(input, candidate, evidence)) {
    return { status: "rejected", result: result(candidate, "rejected", "local-evidence-mismatch") };
  }

  const timezone = candidateTimezone(candidate);
  if (timezone !== null && !validTimezone(timezone, input)) {
    return { status: "rejected", result: result(candidate, "rejected", "timezone-mismatch") };
  }
  const time = candidateTime(candidate);
  const timeCheck = isFutureTime(
    time,
    input,
    candidate.type === "create_task" || candidate.type === "postpone_task" || candidate.type === "reschedule_task",
  );
  if (candidate.type !== "complete_task" && candidate.type !== "cancel_task" && timeCheck !== "valid") {
    return {
      status: "rejected",
      result: result(candidate, timeCheck === "past" ? "rejected" : "confirmation_required", timeCheck === "past" ? "past-time" : "invalid-time"),
    };
  }
  if ((candidate.type === "create_reminder" || candidate.type === "update_reminder")
    && (!evidence.triggerAt || !sameTime(time, evidence.triggerAt))) {
    return { status: "rejected", result: result(candidate, "rejected", "trigger-time-mismatch") };
  }

  const idempotencyKey = normalizedIdempotencyKey(input, candidate);
  const previous = context.idempotency.get(idempotencyKey);
  if (previous?.status === "succeeded") {
    return {
      status: "rejected",
      result: {
        ...previous,
        status: "duplicate",
        errorCode: "idempotent-retry",
      },
    };
  }

  const targetResult = assertTarget(database, candidate);
  if (targetResult) return { status: "rejected", result: targetResult };

  if (candidate.type === "create_task" || candidate.type === "create_reminder") {
    const duplicate = duplicateForCreate(database, candidate, evidence);
    if (duplicate) {
      return {
        status: "rejected",
        result: result(candidate, "duplicate", "duplicate-task-or-reminder", {
          title: duplicate.title,
        }),
      };
    }
  }

  return {
    status: "authorized",
    action: candidate,
    evidence,
    idempotencyKey,
  };
}

export function buildActionIdempotencyKey(
  input: CompanionInput,
  actionType: CompanionActionType,
  normalizedTarget: string,
  normalizedActionTime: string | null,
): string {
  return [
    input.sessionId,
    input.sourceMessageId,
    actionType,
    normalizeTaskTitle(normalizedTarget) || "none",
    normalizedTime(normalizedActionTime) ?? "none",
  ].join("|");
}
