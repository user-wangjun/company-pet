import { describe, expect, it } from "vitest";
import { extractCompanionMemoryCandidate } from "./companionMemory";
import { createTask, EMPTY_TASK_DATABASE } from "../task-core/taskStore";
import {
  parseProactivePreferenceCommand,
  type ProactivePreferenceCommand,
} from "./proactiveTriggerEngine";
import {
  resolveProactiveTaskControlTarget,
  type ProactiveTaskControlResolution,
} from "./proactiveTaskControl";
import type { ProactiveTaskDeliveryContext } from "./proactiveExpressionGate";

const NOW = new Date("2026-08-02T12:00:00.000Z");

function taskDatabase() {
  return createTask(
    EMPTY_TASK_DATABASE,
    { title: "交报告", dueAt: "2026-08-03", schedulePrecision: "date" },
    "2026-08-02T08:00:00.000Z",
  ).database;
}

function context(overrides: Partial<ProactiveTaskDeliveryContext> = {}): ProactiveTaskDeliveryContext {
  return {
    candidateKey: "task-1|2026-08-02T08:00:00.000Z",
    taskIds: [taskDatabase().tasks[0]?.id ?? "missing"],
    taskTitles: ["交报告"],
    petId: "xiaoju-cat",
    deliveredAt: "2026-08-02T11:30:00.000Z",
    ...overrides,
  };
}

function command(text: string): ProactivePreferenceCommand {
  const parsed = parseProactivePreferenceCommand(text);
  if (!parsed) throw new Error(`Expected proactive command: ${text}`);
  return parsed;
}

function expectResolved(result: ProactiveTaskControlResolution) {
  expect(result.status).toBe("resolved");
  if (result.status !== "resolved") throw new Error("expected resolved target");
  return result;
}

describe("proactive task control chat boundary", () => {
  it.each([
    ["别再提醒这件事", "mute"],
    ["少提醒一点", "reduce"],
    ["换一只宠物提醒", "switch_pet"],
  ] as const)("binds an untitled %s command to the recent proactive task", (text, action) => {
    const database = taskDatabase();
    const result = expectResolved(
      resolveProactiveTaskControlTarget(
        command(text),
        database,
        context({ taskIds: [database.tasks[0]!.id] }),
        NOW,
      ),
    );

    expect(result).toMatchObject({ source: "context", task: { id: database.tasks[0]!.id } });
    expect(command(text).action).toBe(action);
  });

  it("requires a task title when there is no reliable proactive context", () => {
    const result = resolveProactiveTaskControlTarget(
      command("少提醒一点"),
      taskDatabase(),
      null,
      NOW,
    );

    expect(result).toEqual({ status: "needs-title", reason: "missing-context" });
  });

  it("does not guess when the last proactive delivery aggregated multiple tasks", () => {
    const database = taskDatabase();
    const result = resolveProactiveTaskControlTarget(
      command("别再提醒这件事"),
      database,
      context({
        taskIds: [database.tasks[0]!.id, "task-2"],
        taskTitles: ["交报告", "交报告给老板"],
      }),
      NOW,
    );

    expect(result).toEqual({ status: "needs-title", reason: "ambiguous-context" });
  });

  it("still resolves an explicit title without proactive context", () => {
    const database = taskDatabase();
    const result = expectResolved(
      resolveProactiveTaskControlTarget(
        command("换一只宠物提醒交报告"),
        database,
        null,
        NOW,
      ),
    );

    expect(result).toMatchObject({ source: "title", task: { title: "交报告" } });
  });

  it("does not route reminder controls into ordinary Memory", () => {
    expect(extractCompanionMemoryCandidate(
      "别再提醒这件事",
      "message-control",
      "xiaoju-cat",
    )).toBeNull();
    expect(extractCompanionMemoryCandidate(
      "少提醒一点",
      "message-control-2",
      "xiaoju-cat",
    )).toBeNull();
  });
});
