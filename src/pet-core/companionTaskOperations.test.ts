import { describe, expect, it } from "vitest";
import { extractTaskOperation } from "./companionTaskExtractor";
import { applyCompanionTaskOperationToDatabase } from "./companionTaskOperations";
import {
  cancelTask,
  completeTask,
  createTask,
  EMPTY_TASK_DATABASE,
} from "../task-core/taskStore";

const NOW = "2026-08-02T12:00:00.000Z";
const OPTIONS = { now: NOW, timezoneOffsetMinutes: 0, timezone: "UTC" };

describe("companion task operation integration", () => {
  it("completes a task through the chat operation path without dueAt", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "整理报告",
      dueAt: null,
    }, NOW);
    const operation = extractTaskOperation("完成整理报告", "message-complete", OPTIONS);

    expect(operation).not.toBeNull();
    const result = applyCompanionTaskOperationToDatabase(created.database, operation!, NOW);

    expect(result.status).toBe("applied");
    expect(result.database.tasks.find((task) => task.id === created.task.id)?.status).toBe("completed");
  });

  it("cancels a task through the chat operation path without dueAt", () => {
    const created = createTask(EMPTY_TASK_DATABASE, {
      title: "整理报告",
      dueAt: null,
    }, NOW);
    const operation = extractTaskOperation("取消整理报告", "message-cancel", OPTIONS);

    expect(operation).not.toBeNull();
    const result = applyCompanionTaskOperationToDatabase(created.database, operation!, NOW);

    expect(result.status).toBe("applied");
    expect(result.database.tasks.find((task) => task.id === created.task.id)?.status).toBe("cancelled");
  });

  it("still requires a new time for postpone and reschedule", () => {
    const created = createTask(EMPTY_TASK_DATABASE, { title: "整理报告" }, NOW);
    const postpone = extractTaskOperation("延期整理报告到以后", "message-postpone", OPTIONS);
    const reschedule = extractTaskOperation("把整理报告改到以后", "message-reschedule", OPTIONS);

    expect(postpone).toMatchObject({ operation: "postpone", needsConfirmation: true, dueAt: null });
    expect(reschedule).toMatchObject({ operation: "reschedule", needsConfirmation: true, dueAt: null });
    expect(applyCompanionTaskOperationToDatabase(created.database, postpone!, NOW).status).toBe("needs_schedule");
    expect(applyCompanionTaskOperationToDatabase(created.database, reschedule!, NOW).status).toBe("needs_schedule");
  });

  it("does not mutate terminal operations when task store rejects them", () => {
    const completed = createTask(EMPTY_TASK_DATABASE, { title: "已完成" }, NOW);
    const completedDatabase = completeTask(completed.database, completed.task.id, NOW);
    const cancelled = createTask(completedDatabase, { title: "已取消" }, NOW);
    const cancelledDatabase = cancelTask(cancelled.database, cancelled.task.id, NOW);

    const completeOperation = extractTaskOperation("完成已完成", "message-complete-terminal", OPTIONS)!;
    const cancelOperation = extractTaskOperation("取消已取消", "message-cancel-terminal", OPTIONS)!;

    expect(applyCompanionTaskOperationToDatabase(cancelledDatabase, completeOperation, NOW).status).toBe("not_found");
    expect(applyCompanionTaskOperationToDatabase(cancelledDatabase, cancelOperation, NOW).status).toBe("not_found");
  });
});
