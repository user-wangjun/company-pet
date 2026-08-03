import { describe, expect, it } from "vitest";
import {
  areTaskTitlesSimilar,
  canAutoCreateTask,
  classifyTaskExpression,
  extractTaskCandidate,
  extractTaskOperation,
  findDuplicateTask,
  findTaskReference,
  getPendingTaskCandidateForPet,
  getTaskCandidateDedupKey,
  resolveTaskCandidateConfirmation,
  taskDraftFromCandidate,
} from "./companionTaskExtractor";
import { extractCompanionMemoryCandidate } from "./companionMemory";
import {
  cancelTask,
  completeTask,
  createTask,
  EMPTY_TASK_DATABASE,
} from "../task-core/taskStore";

const NOW = "2026-08-02T12:00:00.000Z";
const OPTIONS = { now: NOW, timezoneOffsetMinutes: 0, timezone: "UTC" };

describe("provider-independent companion task extractor", () => {
  it("extracts a clear reminder with local datetime and creates a real task/reminder", () => {
    const candidate = extractTaskCandidate(
      "明天下午三点提醒我交报告",
      "message-1",
      OPTIONS,
    );

    expect(candidate).toMatchObject({
      title: "交报告",
      dueAt: "2026-08-03T15:00:00.000Z",
      remindAt: "2026-08-03T15:00:00.000Z",
      schedulePrecision: "datetime",
      timezone: "UTC",
      timezoneOffsetMinutes: 0,
      sourceMessageId: "message-1",
      evidence: "明天下午三点提醒我交报告",
      explicitness: "explicit",
      riskLevel: "low",
      needsConfirmation: false,
    });
    expect(candidate && canAutoCreateTask(candidate)).toBe(true);

    const created = createTask(
      EMPTY_TASK_DATABASE,
      taskDraftFromCandidate(candidate!, "xiaoju-cat"),
      NOW,
    );
    expect(created.task).toMatchObject({
      title: "交报告",
      dueAt: "2026-08-03T15:00:00.000Z",
      sourceMessageId: "message-1",
      evidence: "明天下午三点提醒我交报告",
      createdByPetId: "xiaoju-cat",
    });
    expect(created.database.reminders).toHaveLength(1);
    expect(created.database.reminders[0]).toMatchObject({
      taskId: created.task.id,
      remindAt: "2026-08-03T15:00:00.000Z",
      repeatType: "none",
    });
  });

  it("supports date-only task expressions without inventing a same-day reminder", () => {
    const candidate = extractTaskCandidate("记一下周五买牛奶", "message-2", OPTIONS);
    expect(candidate).toMatchObject({
      title: "买牛奶",
      dueAt: "2026-08-07",
      schedulePrecision: "date",
      remindAt: null,
      explicitness: "explicit",
      needsConfirmation: false,
    });
    const created = createTask(
      EMPTY_TASK_DATABASE,
      taskDraftFromCandidate(candidate!, "xiaoju-cat"),
      NOW,
    );
    expect(created.database.reminders).toHaveLength(0);
  });

  it("does not turn vague, negated, hypothetical, or joking language into a candidate", () => {
    const blocked = [
      ["最近该学习了", "vague"],
      ["有空整理一下", "vague"],
      ["别提醒我", "negated"],
      ["不用记", "negated"],
      ["如果明天有空就交报告", "hypothetical"],
      ["哈哈提醒我明天买牛奶", "joking"],
    ] as const;

    for (const [text, classification] of blocked) {
      expect(classifyTaskExpression(text, OPTIONS)).toBe(classification);
      expect(extractTaskCandidate(text, `message-${text}`, OPTIONS)).toBeNull();
    }
  });

  it("routes an ambiguous time into confirmation and never auto-creates it", () => {
    const candidate = extractTaskCandidate("明天三点交报告", "message-ambiguous", OPTIONS);
    expect(candidate).toMatchObject({
      title: "交报告",
      dueAt: "2026-08-03",
      schedulePrecision: "date",
      explicitness: "time_ambiguous",
      needsConfirmation: true,
    });
    expect(candidate && canAutoCreateTask(candidate)).toBe(false);
  });

  it("only sets repeat fields when repetition is explicit", () => {
    const repeated = extractTaskCandidate(
      "每周五下午三点提醒我开会",
      "message-repeat",
      OPTIONS,
    );
    expect(repeated).toMatchObject({
      title: "开会",
      dueAt: "2026-08-07T15:00:00.000Z",
      remindAt: "2026-08-07T15:00:00.000Z",
      repeatType: "custom",
      repeatRule: { weekdays: [5] },
    });
    const created = createTask(
      EMPTY_TASK_DATABASE,
      taskDraftFromCandidate(repeated!, "xiaoju-cat"),
      NOW,
    );
    expect(created.database.reminders[0]?.repeatType).toBe("custom");

    const single = extractTaskCandidate("明天做年度总结", "message-single", OPTIONS);
    expect(single?.repeatType).toBeUndefined();
    expect(single?.repeatRule).toBeUndefined();
  });

  it("deduplicates similar active tasks at the same schedule", () => {
    const existing = createTask(EMPTY_TASK_DATABASE, {
      title: "交报告给老板",
      dueAt: "2026-08-03T15:00:00.000Z",
      remindAt: "2026-08-03T15:00:00.000Z",
    }, NOW);
    const candidate = extractTaskCandidate("明天下午三点提醒我交报告", "message-dup", OPTIONS)!;

    expect(areTaskTitlesSimilar("交报告给老板", candidate.title)).toBe(true);
    expect(findDuplicateTask(existing.database, candidate)?.id).toBe(existing.task.id);
    expect(getTaskCandidateDedupKey(candidate)).toBe("交报告|datetime:29762820");
  });

  it("does not treat completed or cancelled tasks as active duplicates", () => {
    const completed = createTask(EMPTY_TASK_DATABASE, {
      title: "交报告",
      dueAt: "2026-08-03T15:00:00.000Z",
    }, NOW);
    const completedDatabase = completeTask(completed.database, completed.task.id, NOW);
    const cancelled = createTask(completedDatabase, {
      title: "买牛奶",
      dueAt: "2026-08-07",
    }, NOW);
    const cancelledDatabase = cancelTask(cancelled.database, cancelled.task.id, NOW);
    const candidate = extractTaskCandidate("明天下午三点交报告", "message-terminal", OPTIONS)!;
    expect(findDuplicateTask(completedDatabase, candidate)).toBeNull();
    expect(findTaskReference(completedDatabase, "交报告", true)).toMatchObject({
      status: "found",
      task: { status: "completed" },
    });
    expect(findTaskReference(cancelledDatabase, "买牛奶", true)).toMatchObject({
      status: "found",
      task: { status: "cancelled" },
    });
  });

  it("keeps confirmation lightweight and pet-scoped", () => {
    const candidate = extractTaskCandidate("明天三点交报告", "message-confirm", OPTIONS)!;
    const pending = { petId: "xiaoju-cat", candidate };
    expect(getPendingTaskCandidateForPet(pending, "ikun")).toBeNull();
    expect(getPendingTaskCandidateForPet(pending, "xiaoju-cat")).toBe(candidate);
    expect(resolveTaskCandidateConfirmation("确认")).toBe("confirm");
    expect(resolveTaskCandidateConfirmation("好的")).toBe("confirm");
    for (const text of ["不用记", "不用了", "别记", "取消"]) {
      expect(resolveTaskCandidateConfirmation(text)).toBe("cancel");
    }
  });

  it("extracts complete, cancel, postpone, and reschedule operations", () => {
    expect(extractTaskOperation("完成交报告", "message-complete", OPTIONS)).toMatchObject({
      operation: "complete",
      targetTitle: "交报告",
      needsConfirmation: false,
    });
    expect(extractTaskOperation("取消交报告", "message-cancel", OPTIONS)).toMatchObject({
      operation: "cancel",
      targetTitle: "交报告",
    });
    expect(extractTaskOperation("延期交报告到下周一", "message-postpone", OPTIONS)).toMatchObject({
      operation: "postpone",
      targetTitle: "交报告",
      dueAt: "2026-08-03",
    });
    expect(extractTaskOperation("把交报告改到明天下午三点", "message-reschedule", OPTIONS)).toMatchObject({
      operation: "reschedule",
      targetTitle: "交报告",
      dueAt: "2026-08-03T15:00:00.000Z",
      schedulePrecision: "datetime",
    });
  });

  it("keeps task language out of companion memory extraction", () => {
    expect(
      extractCompanionMemoryCandidate("请记下周五买牛奶", "message-task", "xiaoju-cat"),
    ).toBeNull();
  });

  it("rejects every sensitive task expression instead of awaiting confirmation", () => {
    const sensitive = [
      "明天提醒我保存密码 secret-123",
      "明天提醒我使用 Bearer abcdefghijklmnop",
      "明天提醒我处理 API key sk-proj-12345678901234567890",
      "明天提醒我记录身份证号 11010519491231002X",
      "明天提醒我保存护照 E12345678",
      "明天提醒我核对银行卡 6222021234567890123",
      "明天提醒我记录精确地址北京市朝阳区建国路1号",
      "明天提醒我记录 medical diagnosis migraine",
      "明天提醒我记录 my medication is never-save",
      "明天提醒我使用 github_pat_12345678901234567890",
      "明天下午三点提醒我吃二甲双胍",
      "明天下午三点提醒我去朝阳区建国路1号",
    ];

    for (const text of sensitive) {
      expect(classifyTaskExpression(text, OPTIONS)).toBe("not_task");
      expect(extractTaskCandidate(text, `message-${text}`, OPTIONS)).toBeNull();
      expect(extractTaskOperation(`取消${text}`, `operation-${text}`, OPTIONS)).toBeNull();
    }
  });
});
