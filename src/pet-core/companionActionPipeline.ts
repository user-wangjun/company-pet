import {
  completeTask,
  createTask,
  readTaskDatabase,
  updateTask,
  writeTaskDatabase,
  EMPTY_TASK_DATABASE,
} from "../task-core/taskStore";
import type {
  TaskDatabase,
  TaskDraft,
} from "../task-core/types";
import {
  applyCompanionTaskOperationToDatabase,
} from "./companionTaskOperations";
import {
  canAutoCreateTask,
  findTaskReference,
  normalizeTaskTitle,
  taskDraftFromCandidate,
  type TaskCandidate,
  type TaskOperationCandidate,
} from "./companionTaskExtractor";
import {
  resolveCompanionChatPipelineRoute,
  type CompanionChatPipelineRoute,
} from "./companionChatPipeline";
import { toLegacyTaskExtractorTimezoneOffsetMinutes } from "./companionTaskTimezone";
import type {
  ActionCandidate,
  ActionExecutionResult,
  CompanionActionCandidate,
  CompanionActionConfirmationProof,
  CompanionActionService,
  CompanionActionType,
  CompanionInput,
  CompanionProactivePreferenceRequest,
  CompanionTaskRepository,
  LocalCompatibilityActionCandidate,
} from "./companionHarnessTypes";
import {
  authorizeCompanionAction,
  buildActionIdempotencyKey,
} from "./companionActionPolicy";
import type {
  ActionHandlerContext,
  CompanionActionHandler,
  LocalActionEvidence,
  LocalRequestHints,
} from "./companionActionTypes";
import { containsSensitiveCompanionText } from "./companionPrivacy";

const DATE_ONLY_PATTERN = /^\d{4}-\d{2}-\d{2}$/u;
const MAX_SAFE_DISPLAY_LENGTH = 120;

function safeDisplay(value: string | null | undefined): string | null {
  if (!value || containsSensitiveCompanionText(value)) return null;
  const normalized = value.trim();
  if (!normalized) return null;
  const characters = Array.from(normalized);
  return characters.length <= MAX_SAFE_DISPLAY_LENGTH
    ? normalized
    : `${characters.slice(0, MAX_SAFE_DISPLAY_LENGTH - 1).join("")}…`;
}

function displayTime(value: string | null | undefined, timezone: string | null | undefined): string | null {
  const safe = safeDisplay(value);
  if (!safe) return null;
  if (DATE_ONLY_PATTERN.test(safe)) return safe;
  const timestamp = Date.parse(safe);
  if (!Number.isFinite(timestamp)) return safe;
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      timeZone: timezone || undefined,
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(timestamp));
  } catch {
    return safe;
  }
}

function localActionResult(
  type: CompanionActionType,
  status: ActionExecutionResult["status"],
  errorCode?: string,
  displayData?: Record<string, string>,
): ActionExecutionResult {
  return {
    type,
    status,
    ...(errorCode ? { errorCode } : {}),
    ...(displayData ? { displayData } : {}),
  };
}

function cancelledResult(candidate: CompanionActionCandidate): ActionExecutionResult {
  return localActionResult(candidate.type, "cancelled", "turn-invalidated");
}

function buildEvidence(
  input: CompanionInput,
  actionType: CompanionActionType,
  explicitness: LocalActionEvidence["explicitness"],
  evidence: string,
  target: string | null,
  dueAt: string | null,
    triggerAt: string | null,
  timezone: string | null,
  requiresConfirmation: boolean,
  riskLevel: LocalActionEvidence["riskLevel"],
): LocalActionEvidence {
  const normalizedTarget = target ? normalizeTaskTitle(target) || null : null;
  return {
    sourceMessageId: input.sourceMessageId,
    explicitness,
    evidence,
    normalizedTarget,
    dueAt,
    triggerAt,
    timezone,
    utcOffsetMinutes: input.utcOffsetMinutes,
    actionType,
    idempotencyKey: buildActionIdempotencyKey(
      input,
      actionType,
      normalizedTarget ?? "none",
      triggerAt ?? dueAt,
    ),
    requiresConfirmation,
    riskLevel,
  };
}

function actionForTaskCandidate(input: CompanionInput, candidate: TaskCandidate): ActionCandidate {
  if (candidate.reminderRequested) {
    return {
      sourceMessageId: input.sourceMessageId,
      intent: "explicit",
      type: "create_reminder",
      payload: {
        title: candidate.title,
        // An incomplete local parse uses the current-time sentinel only to
        // produce a confirmation/rejection result. Policy never authorizes it.
        triggerAt: candidate.remindAt ?? candidate.dueAt ?? input.currentTime,
        timezone: candidate.timezone ?? input.timezone,
      },
    };
  }
  return {
    sourceMessageId: input.sourceMessageId,
    intent: "explicit",
    type: "create_task",
    payload: {
      title: candidate.title,
      ...(candidate.dueAt ? { dueAt: candidate.dueAt } : {}),
    },
  };
}

function actionForTaskOperation(
  input: CompanionInput,
  operation: TaskOperationCandidate,
): CompanionActionCandidate {
  if (operation.operation === "complete") {
    return {
      sourceMessageId: input.sourceMessageId,
      intent: "explicit",
      type: "complete_task",
      payload: { reference: operation.targetTitle },
    };
  }
  if (operation.operation === "cancel") {
    return {
      sourceMessageId: input.sourceMessageId,
      type: "cancel_task",
      payload: { reference: operation.targetTitle },
    };
  }
  // A reschedule request that explicitly names the reminder is the formal
  // local update_reminder action. Plain task reschedules remain the existing
  // local compatibility action.
  if (operation.operation === "reschedule" && /提醒/u.test(input.message)) {
    return {
      sourceMessageId: input.sourceMessageId,
      intent: "explicit",
      type: "update_reminder",
      payload: {
        reference: operation.targetTitle,
        triggerAt: operation.remindAt ?? operation.dueAt ?? input.currentTime,
        timezone: operation.timezone ?? input.timezone,
      },
    };
  }
  const type = operation.operation === "postpone" ? "postpone_task" : "reschedule_task";
  return {
    sourceMessageId: input.sourceMessageId,
    type,
    payload: {
      reference: operation.targetTitle,
      dueAt: operation.dueAt ?? input.currentTime,
      ...(operation.remindAt ? { remindAt: operation.remindAt } : {}),
    },
  };
}

function hintsForRoute(
  input: CompanionInput,
  route: CompanionChatPipelineRoute,
): LocalRequestHints {
  if (route.kind === "task-candidate") {
    const action = actionForTaskCandidate(input, route.candidate);
    return {
      route,
      localOwned: true,
      action,
      evidence: buildEvidence(
        input,
        action.type,
        route.candidate.explicitness,
        route.candidate.evidence,
        route.candidate.title,
        route.candidate.dueAt,
        route.candidate.remindAt,
        route.candidate.timezone ?? input.timezone,
        !canAutoCreateTask(route.candidate),
        route.candidate.riskLevel,
      ),
      proactivePreference: null,
      memoryCandidate: null,
      preference: null,
      forget: false,
    };
  }
  if (route.kind === "task-operation") {
    const action = actionForTaskOperation(input, route.operation);
    return {
      route,
      localOwned: true,
      action,
      evidence: buildEvidence(
        input,
        action.type,
        route.operation.explicitness,
        route.operation.evidence,
        route.operation.targetTitle,
        route.operation.dueAt,
        route.operation.remindAt,
        route.operation.timezone ?? input.timezone,
        route.operation.needsConfirmation,
        "low",
      ),
      proactivePreference: null,
      memoryCandidate: null,
      preference: null,
      forget: false,
    };
  }
  if (route.kind === "proactive") {
    const proactivePreference: CompanionProactivePreferenceRequest = {
      sourceMessageId: input.sourceMessageId,
      action: route.command.action,
      targetTitle: route.command.targetTitle,
    };
    return {
      route,
      localOwned: true,
      action: null,
      evidence: null,
      proactivePreference,
      memoryCandidate: null,
      preference: null,
      forget: false,
    };
  }
  if (route.kind === "memory") {
    return {
      route,
      localOwned: true,
      action: null,
      evidence: null,
      proactivePreference: null,
      memoryCandidate: route.candidate,
      preference: null,
      forget: false,
    };
  }
  if (route.kind === "preference") {
    return {
      route,
      localOwned: true,
      action: null,
      evidence: null,
      proactivePreference: null,
      memoryCandidate: null,
      preference: {
        sourceMessageId: input.sourceMessageId,
        preference: route.extraction.preference,
      },
      forget: false,
    };
  }
  if (route.kind === "forget") {
    return {
      route,
      localOwned: true,
      action: null,
      evidence: null,
      proactivePreference: null,
      memoryCandidate: null,
      preference: null,
      forget: true,
    };
  }
  return {
    route,
    localOwned: false,
    action: null,
    evidence: null,
    proactivePreference: null,
    memoryCandidate: null,
    preference: null,
    forget: false,
  };
}

export function buildLocalRequestHints(input: CompanionInput): LocalRequestHints {
  const route = resolveCompanionChatPipelineRoute({
    text: input.message,
    sourceMessageId: input.sourceMessageId,
    petId: input.petId,
    taskOptions: {
      now: input.currentTime,
      timezone: input.timezone,
      // TaskExtractorOptions retains the legacy Date#getTimezoneOffset
      // convention (UTC minus local); CompanionInput is local minus UTC.
      timezoneOffsetMinutes: toLegacyTaskExtractorTimezoneOffsetMinutes(input.utcOffsetMinutes),
    },
  });
  return hintsForRoute(input, route);
}

export function createCompanionTaskRepository(
  storage?: Parameters<typeof writeTaskDatabase>[1],
): CompanionTaskRepository {
  return {
    read: () => readTaskDatabase(storage),
    write: (database) => writeTaskDatabase(database, storage),
  };
}

export function createInMemoryCompanionTaskRepository(
  initial: TaskDatabase = EMPTY_TASK_DATABASE,
  options: { failWrites?: boolean } = {},
): CompanionTaskRepository & { readonly writes: number; setFailWrites(value: boolean): void } {
  let current = initial;
  let writes = 0;
  let failWrites = options.failWrites ?? false;
  return {
    read: () => current,
    write: (database) => {
      if (failWrites) return false;
      writes += 1;
      current = database;
      return true;
    },
    get writes() {
      return writes;
    },
    setFailWrites(value: boolean) {
      failWrites = value;
    },
  };
}

function taskCandidateFromAction(
  input: CompanionInput,
  evidence: LocalActionEvidence,
  title: string,
  dueAt: string | null,
  remindAt: string | null,
): TaskCandidate {
  return {
    title,
    dueAt,
    schedulePrecision: dueAt && !DATE_ONLY_PATTERN.test(dueAt) ? "datetime" : "date",
    remindAt,
    timezone: evidence.timezone ?? input.timezone,
    // This object crosses back into the legacy TaskCandidate contract.
    timezoneOffsetMinutes: toLegacyTaskExtractorTimezoneOffsetMinutes(input.utcOffsetMinutes),
    sourceMessageId: input.sourceMessageId,
    evidence: evidence.evidence,
    confidence: 1,
    riskLevel: "low",
    explicitness: "explicit",
    needsConfirmation: false,
    confirmationReason: null,
    reminderRequested: Boolean(remindAt),
  };
}

function beforeWrite(context: ActionHandlerContext, candidate: CompanionActionCandidate): ActionExecutionResult | null {
  return context.signal.aborted || !context.isCurrent() ? cancelledResult(candidate) : null;
}

function writeResult(
  context: ActionHandlerContext,
  candidate: CompanionActionCandidate,
  database: TaskDatabase,
  successData: { resourceId?: string; displayData?: Record<string, string> },
): ActionExecutionResult {
  const cancelled = beforeWrite(context, candidate);
  if (cancelled) return cancelled;
  try {
    if (!context.repository.write(database)) {
      return localActionResult(candidate.type, "failed", "task-database-write-failed");
    }
  } catch {
    return localActionResult(candidate.type, "failed", "task-database-write-threw");
  }
  return {
    ...localActionResult(candidate.type, "succeeded", undefined, successData.displayData),
    ...(successData.resourceId ? { resourceId: successData.resourceId } : {}),
  };
}

export class CreateTaskHandler implements CompanionActionHandler {
  readonly type = "create_task" as const;

  execute(candidate: CompanionActionCandidate, context: ActionHandlerContext): ActionExecutionResult {
    if (candidate.type !== this.type) return localActionResult(this.type, "failed", "handler-type-mismatch");
    const taskCandidate = taskCandidateFromAction(
      context.input,
      context.evidence,
      candidate.payload.title,
      candidate.payload.dueAt ?? context.evidence.dueAt,
      null,
    );
    let created: { database: TaskDatabase; task: import("../task-core/types").Task };
    try {
      const draft = taskDraftFromCandidate(taskCandidate, context.input.petId);
      created = createTask(context.database, draft, context.input.currentTime);
    } catch {
      return localActionResult(this.type, "failed", "create-task-threw");
    }
    const title = safeDisplay(created.task.title);
    return writeResult(context, candidate, created.database, {
      resourceId: created.task.id,
      ...(title ? { displayData: { title } } : {}),
    });
  }
}

export class CreateReminderHandler implements CompanionActionHandler {
  readonly type = "create_reminder" as const;

  execute(candidate: CompanionActionCandidate, context: ActionHandlerContext): ActionExecutionResult {
    if (candidate.type !== this.type) return localActionResult(this.type, "failed", "handler-type-mismatch");
    const taskCandidate = taskCandidateFromAction(
      context.input,
      context.evidence,
      candidate.payload.title,
      context.evidence.dueAt,
      candidate.payload.triggerAt,
    );
    let created: { database: TaskDatabase; task: import("../task-core/types").Task };
    try {
      const draft: TaskDraft = taskDraftFromCandidate(taskCandidate, context.input.petId);
      created = createTask(context.database, draft, context.input.currentTime);
    } catch {
      return localActionResult(this.type, "failed", "create-reminder-threw");
    }
    const reminder = created.database.reminders.find((item) => item.taskId === created.task.id);
    const title = safeDisplay(created.task.title);
    const triggerTime = displayTime(candidate.payload.triggerAt, candidate.payload.timezone);
    return writeResult(context, candidate, created.database, {
      resourceId: reminder?.id ?? created.task.id,
      ...(title || triggerTime
        ? {
            displayData: {
              ...(title ? { title } : {}),
              ...(triggerTime ? { triggerTime } : {}),
            },
          }
        : {}),
    });
  }
}

export class CompleteTaskHandler implements CompanionActionHandler {
  readonly type = "complete_task" as const;

  execute(candidate: CompanionActionCandidate, context: ActionHandlerContext): ActionExecutionResult {
    if (candidate.type !== this.type) return localActionResult(this.type, "failed", "handler-type-mismatch");
    const database = context.repository.read();
    const match = findTaskReference(database, candidate.payload.reference);
    if (match.status === "not_found") return localActionResult(this.type, "not_found", "target-not-found");
    if (match.status === "ambiguous" || !match.task) return localActionResult(this.type, "ambiguous", "multiple-targets");
    const next = completeTask(database, match.task.id, context.input.currentTime);
    if (next === database) return localActionResult(this.type, "duplicate", "unchanged");
    const title = safeDisplay(match.task.title);
    return writeResult(context, candidate, next, {
      resourceId: match.task.id,
      ...(title ? { displayData: { title } } : {}),
    });
  }
}

export class UpdateReminderHandler implements CompanionActionHandler {
  readonly type = "update_reminder" as const;

  execute(candidate: CompanionActionCandidate, context: ActionHandlerContext): ActionExecutionResult {
    if (candidate.type !== this.type) return localActionResult(this.type, "failed", "handler-type-mismatch");
    const database = context.repository.read();
    const match = findTaskReference(database, candidate.payload.reference);
    if (match.status === "not_found") return localActionResult(this.type, "not_found", "target-not-found");
    if (match.status === "ambiguous" || !match.task) return localActionResult(this.type, "ambiguous", "multiple-targets");
    const reminder = database.reminders.find((item) =>
      item.taskId === match.task!.id
      && item.status === "active"
      && !item.deletedAt,
    );
    if (!reminder) return localActionResult(this.type, "not_found", "active-reminder-not-found");
    let next: TaskDatabase;
    try {
      next = updateTask(database, match.task.id, { remindAt: candidate.payload.triggerAt }, context.input.currentTime);
    } catch {
      return localActionResult(this.type, "failed", "update-reminder-threw");
    }
    if (next === database) return localActionResult(this.type, "duplicate", "unchanged");
    const title = safeDisplay(match.task.title);
    const triggerTime = displayTime(candidate.payload.triggerAt, candidate.payload.timezone);
    return writeResult(context, candidate, next, {
      resourceId: reminder.id,
      ...(title || triggerTime
        ? {
            displayData: {
              ...(title ? { title } : {}),
              ...(triggerTime ? { triggerTime } : {}),
            },
          }
        : {}),
    });
  }
}

function localOperationFromCandidate(
  candidate: LocalCompatibilityActionCandidate,
  context: ActionHandlerContext,
): TaskOperationCandidate {
  const operation = candidate.type === "cancel_task"
    ? "cancel"
    : candidate.type === "postpone_task"
      ? "postpone"
      : "reschedule";
  return {
    operation,
    targetTitle: candidate.payload.reference,
    dueAt: "dueAt" in candidate.payload && candidate.payload.dueAt ? candidate.payload.dueAt : null,
    schedulePrecision: "dueAt" in candidate.payload && candidate.payload.dueAt && !DATE_ONLY_PATTERN.test(candidate.payload.dueAt)
      ? "datetime"
      : "date",
    remindAt: "remindAt" in candidate.payload ? candidate.payload.remindAt ?? null : null,
    timezone: context.input.timezone,
    // TaskOperationCandidate uses the legacy Task Extractor offset sign.
    timezoneOffsetMinutes: toLegacyTaskExtractorTimezoneOffsetMinutes(context.input.utcOffsetMinutes),
    sourceMessageId: context.input.sourceMessageId,
    evidence: context.evidence.evidence,
    explicitness: context.evidence.explicitness,
    confidence: 1,
    needsConfirmation: context.evidence.requiresConfirmation,
    confirmationReason: context.evidence.requiresConfirmation ? "需要确认后再修改。" : null,
  };
}

class LocalTaskOperationHandler implements CompanionActionHandler {
  constructor(
    readonly type: "cancel_task" | "postpone_task" | "reschedule_task",
  ) {}

  execute(candidate: CompanionActionCandidate, context: ActionHandlerContext): ActionExecutionResult {
    if (candidate.type !== this.type) return localActionResult(this.type, "failed", "handler-type-mismatch");
    const database = context.repository.read();
    const operationResult = applyCompanionTaskOperationToDatabase(
      database,
      localOperationFromCandidate(candidate, context),
      context.input.currentTime,
    );
    if (operationResult.status === "not_found") return localActionResult(this.type, "not_found", "target-not-found");
    if (operationResult.status === "ambiguous") return localActionResult(this.type, "ambiguous", "multiple-targets");
    if (operationResult.status === "needs_schedule") return localActionResult(this.type, "confirmation_required", "schedule-confirmation-required");
    if (operationResult.status === "unchanged") return localActionResult(this.type, "duplicate", "unchanged");
    const title = safeDisplay(operationResult.task.title);
    const triggerTime = "dueAt" in candidate.payload
      ? displayTime(candidate.payload.dueAt, context.input.timezone)
      : null;
    return writeResult(context, candidate, operationResult.database, {
      resourceId: operationResult.task.id,
      ...(title || triggerTime
        ? {
            displayData: {
              ...(title ? { title } : {}),
              ...(triggerTime ? { triggerTime } : {}),
            },
          }
        : {}),
    });
  }
}

function equivalentAction(left: CompanionActionCandidate, right: CompanionActionCandidate): boolean {
  if (left.type !== right.type) return false;
  const leftPayload = left.payload;
  const rightPayload = right.payload;
  if ("title" in leftPayload && "title" in rightPayload) {
    return normalizeTaskTitle(leftPayload.title) === normalizeTaskTitle(rightPayload.title)
      && ("dueAt" in leftPayload ? leftPayload.dueAt : "triggerAt" in leftPayload ? leftPayload.triggerAt : null)
        === ("dueAt" in rightPayload ? rightPayload.dueAt : "triggerAt" in rightPayload ? rightPayload.triggerAt : null);
  }
  if ("reference" in leftPayload && "reference" in rightPayload) {
    return normalizeTaskTitle(leftPayload.reference) === normalizeTaskTitle(rightPayload.reference)
      && ("triggerAt" in leftPayload ? leftPayload.triggerAt : "dueAt" in leftPayload ? leftPayload.dueAt : null)
        === ("triggerAt" in rightPayload ? rightPayload.triggerAt : "dueAt" in rightPayload ? rightPayload.dueAt : null);
  }
  return false;
}

export class CompanionActionPipeline implements CompanionActionService {
  private readonly idempotency = new Map<string, ActionExecutionResult>();
  private readonly handlers: ReadonlyMap<CompanionActionType, CompanionActionHandler>;
  private serial: Promise<void> = Promise.resolve();

  constructor(
    private readonly repository: CompanionTaskRepository = createCompanionTaskRepository(),
  ) {
    this.handlers = new Map<CompanionActionType, CompanionActionHandler>([
      ["create_task", new CreateTaskHandler()],
      ["create_reminder", new CreateReminderHandler()],
      ["complete_task", new CompleteTaskHandler()],
      ["update_reminder", new UpdateReminderHandler()],
      ["cancel_task", new LocalTaskOperationHandler("cancel_task")],
      ["postpone_task", new LocalTaskOperationHandler("postpone_task")],
      ["reschedule_task", new LocalTaskOperationHandler("reschedule_task")],
    ]);
  }

  process(
    input: CompanionInput,
    candidates: readonly CompanionActionCandidate[],
    signal: AbortSignal,
    confirmation?: CompanionActionConfirmationProof,
  ): Promise<readonly ActionExecutionResult[]> {
    const work = () => this.processSerial(input, candidates, signal, confirmation);
    const next = this.serial.then(work, work);
    this.serial = next.then(() => undefined, () => undefined);
    return next;
  }

  private async processSerial(
    input: CompanionInput,
    candidates: readonly CompanionActionCandidate[],
    signal: AbortSignal,
    confirmation?: CompanionActionConfirmationProof,
  ): Promise<readonly ActionExecutionResult[]> {
    const hints = buildLocalRequestHints(input);
    const results: ActionExecutionResult[] = [];
    let localOwnerSeen = false;
    for (const candidate of candidates) {
      if (signal.aborted) {
        results.push(cancelledResult(candidate));
        continue;
      }
      if (hints.localOwned && hints.action && !equivalentAction(candidate, hints.action)) {
        results.push(localActionResult(candidate.type, "duplicate", "local-route-owns-input"));
        continue;
      }
      if (hints.localOwned && hints.action && equivalentAction(candidate, hints.action) && localOwnerSeen) {
        results.push(localActionResult(candidate.type, "duplicate", "local-route-owns-input"));
        continue;
      }
      if (hints.localOwned && hints.action && equivalentAction(candidate, hints.action)) localOwnerSeen = true;
      const database = this.repository.read();
      const decision = authorizeCompanionAction({
        input,
        candidate,
        evidence: hints.localOwned && hints.action && equivalentAction(candidate, hints.action)
          ? hints.evidence
          : null,
        database,
        signal,
        isCurrent: () => !signal.aborted,
        idempotency: this.idempotency,
        confirmation,
      });
      if (decision.status === "rejected") {
        results.push(decision.result);
        continue;
      }
      const handler = this.handlers.get(decision.action.type);
      if (!handler) {
        results.push(localActionResult(decision.action.type, "rejected", "action-not-allowed"));
        continue;
      }
      let execution: ActionExecutionResult;
      try {
        execution = await handler.execute(decision.action, {
          input,
          database,
          repository: this.repository,
          evidence: decision.evidence,
          signal,
          isCurrent: () => !signal.aborted,
        });
      } catch {
        execution = localActionResult(decision.action.type, "failed", "handler-threw");
      }
      results.push(execution);
      if (execution.status === "succeeded") {
        // A successful idempotency mark is intentionally made only after the
        // repository write returned true.
        this.idempotency.set(decision.idempotencyKey, execution);
      }
    }
    return results;
  }
}

export function createCompanionActionService(
  repository?: CompanionTaskRepository,
): CompanionActionService {
  return new CompanionActionPipeline(repository);
}
