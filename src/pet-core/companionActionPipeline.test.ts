import { describe, expect, test } from "vitest";
import {
  createCompanionHarness,
} from "./companionHarness";
import {
  createInMemoryCompanionTaskRepository,
  CompanionActionPipeline,
  UpdateReminderHandler,
} from "./companionActionPipeline";
import { authorizeCompanionAction } from "./companionActionPolicy";
import type { ActionHandlerContext, LocalActionEvidence } from "./companionActionTypes";
import {
  completeTask,
  createTask,
  EMPTY_TASK_DATABASE,
  permanentlyDeleteTask,
  softDeleteTask,
} from "../task-core/taskStore";
import type {
  CompanionInput,
  CompanionModelResponse,
  CompanionTaskRepository,
} from "./companionHarnessTypes";
import type {
  CompanionModelPort,
  CompanionModelPortInfo,
  HarnessModelRequest,
  ResolvedCompanionModelTurn,
} from "./companionModelPort";
import type { ProviderAdapter } from "./companionProviderAdapter";

const REMOTE_INFO: CompanionModelPortInfo = {
  kind: "remote",
  provider: "Phase 4 Fake Remote",
  target: "https://phase4.invalid",
  disclosure: "远程模式",
};

function input(overrides: Partial<CompanionInput> = {}): CompanionInput {
  return {
    requestId: "request-1",
    sessionId: "session-1",
    sourceMessageId: "message-1",
    userId: "local-user",
    petId: "xiaoju-cat",
    message: "明天下午三点提醒我交报告",
    currentTime: "2026-08-11T12:00:00.000Z",
    timezone: "Asia/Shanghai",
    utcOffsetMinutes: 480,
    source: "chat",
    ...overrides,
  };
}

function fakeModel(response: CompanionModelResponse = { replyDraft: "模型草稿" }): {
  port: CompanionModelPort;
  beginCalls: number;
  generateCalls: number;
} {
  let beginCalls = 0;
  let generateCalls = 0;
  const capabilities = Object.freeze({
    textGeneration: true as const,
    structuredOutput: "none" as const,
    cancellation: true,
    usageMetadata: false,
  });
  const adapter: ProviderAdapter = {
    id: REMOTE_INFO.provider,
    protocol: "openai-compatible",
    capabilities,
    info: REMOTE_INFO,
    generate: async () => ({
      text: "unused",
      metadata: { providerId: REMOTE_INFO.provider },
    }),
  };
  const resolved: ResolvedCompanionModelTurn = {
    adapter,
    info: REMOTE_INFO,
    capabilities,
    generate: async (_request: HarnessModelRequest) => {
      generateCalls += 1;
      return response;
    },
  };
  return {
    port: {
      info: REMOTE_INFO,
      beginTurn: () => {
        beginCalls += 1;
        return resolved;
      },
      generate: async () => response,
    },
    get beginCalls() {
      return beginCalls;
    },
    get generateCalls() {
      return generateCalls;
    },
  };
}

function harnessWith(
  repository: CompanionTaskRepository,
  response?: CompanionModelResponse,
) {
  const model = fakeModel(response);
  return {
    model,
    harness: createCompanionHarness({ modelPort: model.port, taskRepository: repository }),
  };
}

function withReminder() {
  return createTask(EMPTY_TASK_DATABASE, {
    title: "交报告",
    dueAt: "2026-08-12T07:00:00.000Z",
    schedulePrecision: "datetime",
    remindAt: "2026-08-12T07:00:00.000Z",
    sourceMessageId: "old-message",
    evidence: "旧本地证据",
  }, "2026-08-11T10:00:00.000Z").database;
}

describe("Companion Harness Phase 4 Action Pipeline", () => {
  test("creates a reminder locally with zero Provider calls and one database write", async () => {
    const repository = createInMemoryCompanionTaskRepository();
    const { harness, model } = harnessWith(repository);

    const response = await harness.respond(input());

    expect(response.status).toBe("success");
    expect(response.actions).toMatchObject([{ type: "create_reminder", status: "succeeded" }]);
    expect(response.text).toContain("交报告");
    expect(response.text).toContain("提醒");
    expect(response.callCounts).toEqual({ model: 0, external: 0, local: 0, fallback: 0 });
    expect(model.beginCalls).toBe(0);
    expect(model.generateCalls).toBe(0);
    expect(repository.writes).toBe(1);
    expect(repository.read().tasks).toHaveLength(1);
    expect(repository.read().reminders).toHaveLength(1);
    expect(repository.read().reminderInstances).toHaveLength(1);
  });

  test("creates a plain Task locally without creating a Reminder", async () => {
    const repository = createInMemoryCompanionTaskRepository();
    const { harness, model } = harnessWith(repository);
    const response = await harness.respond(input({
      message: "明天交报告",
      sourceMessageId: "task-message",
      requestId: "task-request",
    }));

    expect(response.actions).toMatchObject([{ type: "create_task", status: "succeeded" }]);
    expect(response.text).toContain("待办");
    expect(repository.read().tasks).toHaveLength(1);
    expect(repository.read().reminders).toHaveLength(0);
    expect(model.beginCalls).toBe(0);
    expect(response.callCounts.external).toBe(0);
    expect(repository.writes).toBe(1);
  });

  test("keeps vague and past reminders local, honest, and database-neutral", async () => {
    const vagueRepository = createInMemoryCompanionTaskRepository();
    const vague = harnessWith(vagueRepository);
    const vagueResponse = await vague.harness.respond(input({
      message: "有空提醒我交报告",
      sourceMessageId: "vague-message",
      requestId: "vague-request",
    }));

    expect(vagueResponse.actions).toMatchObject([{ status: "confirmation_required" }]);
    expect(vagueResponse.text).toContain("确认");
    expect(vagueRepository.writes).toBe(0);
    expect(vague.model.beginCalls).toBe(0);

    const pastRepository = createInMemoryCompanionTaskRepository();
    const past = harnessWith(pastRepository);
    const pastResponse = await past.harness.respond(input({
      message: "2026年8月10日下午三点提醒我交报告",
      sourceMessageId: "past-message",
      requestId: "past-request",
    }));

    expect(pastResponse.actions).toMatchObject([{ status: "rejected", errorCode: "past-time" }]);
    expect(pastRepository.writes).toBe(0);
    expect(past.model.beginCalls).toBe(0);
  });

  test("retries and concurrent equivalent reminders are idempotent", async () => {
    const repository = createInMemoryCompanionTaskRepository();
    const { harness } = harnessWith(repository);
    const first = await harness.respond(input());
    const retry = await harness.respond(input({ requestId: "request-2" }));
    const secondSession = harness.respond(input({
      requestId: "request-3",
      sessionId: "session-2",
      sourceMessageId: "message-2",
    }));
    const thirdSession = harness.respond(input({
      requestId: "request-4",
      sessionId: "session-3",
      sourceMessageId: "message-3",
    }));
    const [second, third] = await Promise.all([secondSession, thirdSession]);

    expect(first.actions[0]?.status).toBe("succeeded");
    expect(retry.actions[0]?.status).toBe("duplicate");
    expect(second.actions[0]?.status).toBe("duplicate");
    expect(third.actions[0]?.status).toBe("duplicate");
    expect(repository.writes).toBe(1);
    expect(repository.read().tasks).toHaveLength(1);
    expect(repository.read().reminders).toHaveLength(1);
    expect(repository.read().reminderInstances).toHaveLength(1);
  });

  test("completes only the unique active task and never trusts a model id", async () => {
    const repository = createInMemoryCompanionTaskRepository(withReminder());
    const { harness, model } = harnessWith(repository);
    const response = await harness.respond(input({
      message: "完成任务：交报告",
      sourceMessageId: "complete-message",
      requestId: "complete-request",
    }));

    expect(response.actions).toMatchObject([{ type: "complete_task", status: "succeeded" }]);
    expect(repository.read().tasks[0]?.status).toBe("completed");
    expect(model.beginCalls).toBe(0);

    const modelRepository = createInMemoryCompanionTaskRepository(withReminder());
    const modelResponse: CompanionModelResponse = {
      replyDraft: "已经完成了。",
      actions: [{
        sourceMessageId: "model-message",
        intent: "explicit",
        type: "complete_task",
        payload: { reference: "task-fake-id" },
      }],
    };
    const modelHarness = harnessWith(modelRepository, modelResponse);
    const modelResult = await modelHarness.harness.respond(input({
      message: "你好，今天怎么样",
      sourceMessageId: "model-message",
      requestId: "model-request",
    }));
    expect(modelResult.actions).toMatchObject([{ status: "rejected", errorCode: "missing-local-evidence" }]);
    expect(modelResult.text).not.toContain("已经完成");
    expect(modelRepository.writes).toBe(0);
  });

  test("does not modify the database for missing, ambiguous, terminal, or deleted targets", async () => {
    const missingRepository = createInMemoryCompanionTaskRepository(withReminder());
    const missing = harnessWith(missingRepository);
    const missingResponse = await missing.harness.respond(input({
      message: "完成任务：不存在的事项",
      sourceMessageId: "missing-target",
      requestId: "missing-target-request",
    }));
    expect(missingResponse.actions).toMatchObject([{ status: "not_found" }]);
    expect(missingRepository.writes).toBe(0);

    const first = createTask(EMPTY_TASK_DATABASE, {
      title: "交报告",
      dueAt: "2026-08-12",
      sourceMessageId: "first",
    }, "2026-08-11T10:00:00.000Z");
    const ambiguousDatabase = createTask(first.database, {
      title: "交报告",
      dueAt: "2026-08-13",
      sourceMessageId: "second",
    }, "2026-08-11T10:00:00.000Z").database;
    const ambiguousRepository = createInMemoryCompanionTaskRepository(ambiguousDatabase);
    const ambiguous = harnessWith(ambiguousRepository);
    const ambiguousResponse = await ambiguous.harness.respond(input({
      message: "完成任务：交报告",
      sourceMessageId: "ambiguous-target",
      requestId: "ambiguous-target-request",
    }));
    expect(ambiguousResponse.actions).toMatchObject([{ status: "ambiguous" }]);
    expect(ambiguousRepository.writes).toBe(0);

    const terminalBase = withReminder();
    const actualTerminal = completeTask(terminalBase, terminalBase.tasks[0]!.id, "2026-08-11T13:00:00.000Z");
    const terminalRepository = createInMemoryCompanionTaskRepository(actualTerminal);
    const terminal = harnessWith(terminalRepository);
    const terminalResponse = await terminal.harness.respond(input({
      message: "完成任务：交报告",
      sourceMessageId: "terminal-target",
      requestId: "terminal-target-request",
    }));
    expect(terminalResponse.actions).toMatchObject([{ status: "rejected", errorCode: "terminal-target" }]);
    expect(terminalRepository.writes).toBe(0);

    const softBase = withReminder();
    const softDeleted = softDeleteTask(softBase, softBase.tasks[0]!.id, "2026-08-11T13:00:00.000Z");
    const softRepository = createInMemoryCompanionTaskRepository(softDeleted);
    const soft = harnessWith(softRepository);
    const softResponse = await soft.harness.respond(input({
      message: "完成任务：交报告",
      sourceMessageId: "soft-deleted-target",
      requestId: "soft-deleted-target-request",
    }));
    expect(softResponse.actions).toMatchObject([{ status: "not_found" }]);
    expect(softRepository.writes).toBe(0);

    const purged = permanentlyDeleteTask(softDeleted, softDeleted.tasks[0]!.id);
    const physicalRepository = createInMemoryCompanionTaskRepository(purged);
    const physical = harnessWith(physicalRepository);
    const physicalResponse = await physical.harness.respond(input({
      message: "完成任务：交报告",
      sourceMessageId: "physical-deleted-target",
      requestId: "physical-deleted-target-request",
    }));
    expect(physicalResponse.actions).toMatchObject([{ status: "not_found" }]);
    expect(physicalRepository.writes).toBe(0);
  });

  test("updates an active reminder locally without creating a second task", async () => {
    const repository = createInMemoryCompanionTaskRepository(withReminder());
    const { harness, model } = harnessWith(repository);
    const response = await harness.respond(input({
      message: "把交报告改到明天下午四点",
      sourceMessageId: "update-message",
      requestId: "update-request",
    }));

    expect(response.actions).toMatchObject([{ type: "reschedule_task", status: "succeeded" }]);
    expect(response.text).toContain("已经把");
    expect(response.text).toContain("任务改期");
    expect(repository.read().tasks).toHaveLength(1);
    expect(repository.read().reminders).toHaveLength(1);
    expect(repository.read().reminderInstances).toHaveLength(2);
    expect(model.beginCalls).toBe(0);
    expect(repository.writes).toBe(1);
  });

  test("authorizes and executes the strict update_reminder Handler from local evidence", async () => {
    const repository = createInMemoryCompanionTaskRepository(withReminder());
    const requested = input({
      message: "把交报告提醒改到明天下午四点",
      sourceMessageId: "strict-update-message",
      requestId: "strict-update-request",
    });
    const candidate = {
      sourceMessageId: requested.sourceMessageId,
      intent: "explicit" as const,
      type: "update_reminder" as const,
      payload: {
        reference: "交报告",
        triggerAt: "2026-08-12T08:00:00.000Z",
        timezone: requested.timezone,
      },
    };
    const evidence: LocalActionEvidence = {
      sourceMessageId: requested.sourceMessageId,
      explicitness: "explicit",
      evidence: requested.message,
      normalizedTarget: "交报告",
      dueAt: "2026-08-12T07:00:00.000Z",
      triggerAt: "2026-08-12T08:00:00.000Z",
      timezone: requested.timezone,
      utcOffsetMinutes: requested.utcOffsetMinutes,
      actionType: "update_reminder",
      idempotencyKey: "strict-update-key",
      requiresConfirmation: false,
      riskLevel: "low",
    };
    const decision = authorizeCompanionAction({
      input: requested,
      candidate,
      evidence,
      database: repository.read(),
      signal: new AbortController().signal,
      isCurrent: () => true,
      idempotency: new Map(),
    });
    expect(decision.status).toBe("authorized");
    if (decision.status !== "authorized") return;
    const context: ActionHandlerContext = {
      input: requested,
      database: repository.read(),
      repository,
      evidence,
      signal: new AbortController().signal,
      isCurrent: () => true,
    };
    const result = await new UpdateReminderHandler().execute(decision.action, context);
    expect(result).toMatchObject({ type: "update_reminder", status: "succeeded" });
    expect(repository.writes).toBe(1);
    expect(repository.read().tasks).toHaveLength(1);
    expect(repository.read().reminders[0]?.remindAt).toBe("2026-08-12T08:00:00.000Z");
  });

  test("overwrites model success when the domain write fails", async () => {
    const repository = createInMemoryCompanionTaskRepository(EMPTY_TASK_DATABASE, { failWrites: true });
    const { harness, model } = harnessWith(repository);
    const response = await harness.respond(input({
      sourceMessageId: "write-failure-message",
      requestId: "write-failure-request",
    }));

    expect(response.actions).toMatchObject([{ type: "create_reminder", status: "failed" }]);
    expect(response.text).not.toContain("已经为你创建");
    expect(response.text).toContain("没有处理成功");
    expect(response.canCommit).toBe(true);
    expect(model.beginCalls).toBe(0);
    expect(repository.read().tasks).toHaveLength(0);
  });

  test("does not execute a second action after a cancellation boundary", async () => {
    const repository = createInMemoryCompanionTaskRepository();
    const pipeline = new CompanionActionPipeline(repository);
    const controller = new AbortController();
    controller.abort();
    const result = await pipeline.process(input(), [{
      sourceMessageId: "message-1",
      intent: "explicit",
      type: "create_reminder",
      payload: {
        title: "交报告",
        triggerAt: "2026-08-12T07:00:00.000Z",
        timezone: "Asia/Shanghai",
      },
    }], controller.signal);

    expect(result).toEqual([{ type: "create_reminder", status: "cancelled", errorCode: "turn-invalidated" }]);
    expect(repository.writes).toBe(0);
  });

  test("keeps a real write after cancellation but suppresses the late UI commit", async () => {
    const controller = new AbortController();
    let current = EMPTY_TASK_DATABASE;
    let writes = 0;
    const repository: CompanionTaskRepository = {
      read: () => current,
      write: (database) => {
        current = database;
        writes += 1;
        controller.abort();
        return true;
      },
    };
    const { harness } = harnessWith(repository);
    const response = await harness.respond(input({ signal: controller.signal }));

    expect(response.status).toBe("cancelled");
    expect(response.actions).toMatchObject([{ type: "create_reminder", status: "succeeded" }]);
    expect(writes).toBe(1);
    expect(current.tasks).toHaveLength(1);
    expect(current.reminders).toHaveLength(1);
    expect(response.committed).toBe(false);
  });
});
