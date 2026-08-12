import { describe, expect, test, vi } from "vitest";
import {
  EMPTY_TASK_DATABASE,
  createTask,
  triggerDueReminders,
} from "../task-core/taskStore";
import { selectDueCareReminder } from "./careReminders";
import {
  PROACTIVE_BUBBLE_MIN_INTERVAL_MS,
  PROACTIVE_EVENT_RULES,
  PROACTIVE_EXPRESSION_STORAGE_KEY,
  PROACTIVE_SEMANTIC_EVENTS,
  createProactiveExpressionState,
  createProactiveTaskState,
  evaluateProactiveSemanticEvent,
  isWithinQuietHours,
  normalizeProactiveExpressionState,
  quietHoursFromBedtime,
  readProactiveExpressionState,
  recordProactiveSemanticEventSuccess,
  writeProactiveExpressionState,
  type ProactiveExpressionState,
  type ProactiveExpressionStorage,
  type ProactiveSemanticEvent,
} from "./proactiveExpressionGate";

function at(hour: number, minute = 0, day = 26): Date {
  return new Date(2026, 6, day, hour, minute, 0, 0);
}

function storage(initial: string | null = null): ProactiveExpressionStorage {
  let value = initial;
  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((_key, nextValue) => {
      value = nextValue;
    }),
  };
}

function recordBubble(
  state: ProactiveExpressionState,
  event: ProactiveSemanticEvent,
  now: Date,
): ProactiveExpressionState {
  const decision = evaluateProactiveSemanticEvent({ event, state, now });
  expect(decision.eventAllowed).toBe(true);
  expect(decision.bubbleAllowed).toBe(true);
  return recordProactiveSemanticEventSuccess(decision.state, event, now, true);
}

describe("proactive expression gate", () => {
  test("declares only idle_alive as non-bubble by default", () => {
    expect(PROACTIVE_SEMANTIC_EVENTS.filter(
      (event) => !PROACTIVE_EVENT_RULES[event].producesBubble,
    )).toEqual(["idle_alive"]);
  });

  test("enforces the 45-minute bubble boundary exactly", () => {
    const firstAt = at(8);
    const state = recordBubble(
      createProactiveExpressionState(firstAt),
      "celebrate_big",
      firstAt,
    );
    const beforeBoundary = new Date(firstAt.getTime() + PROACTIVE_BUBBLE_MIN_INTERVAL_MS - 1);
    const atBoundary = new Date(firstAt.getTime() + PROACTIVE_BUBBLE_MIN_INTERVAL_MS);

    expect(evaluateProactiveSemanticEvent({
      event: "celebrate_big",
      state,
      now: beforeBoundary,
    })).toMatchObject({
      eventAllowed: true,
      bubbleAllowed: false,
      reason: "bubble-cooldown",
    });
    expect(evaluateProactiveSemanticEvent({
      event: "celebrate_big",
      state,
      now: atBoundary,
    })).toMatchObject({
      eventAllowed: true,
      bubbleAllowed: true,
      reason: "allowed",
    });
  });

  test("allows three celebrate_small bubbles and makes the fourth action-only", () => {
    let state = createProactiveExpressionState(at(8));
    for (let index = 0; index < 3; index += 1) {
      state = recordBubble(state, "celebrate_small", at(8 + index));
    }

    expect(evaluateProactiveSemanticEvent({
      event: "celebrate_small",
      state,
      now: at(11),
    })).toMatchObject({
      eventAllowed: true,
      bubbleAllowed: false,
      reason: "bubble-daily-limit",
    });
    expect(state.triggerCounts.celebrate_small).toBe(3);
    expect(state.bubbleCounts.celebrate_small).toBe(3);
  });

  test.each([
    "morning_greet",
    "gentle_concern",
    "notice_return",
    "recall_memory",
  ] as const)("%s is limited to one trigger per local day", (event) => {
    const firstAt = at(8);
    const state = recordBubble(createProactiveExpressionState(firstAt), event, firstAt);
    expect(evaluateProactiveSemanticEvent({
      event,
      state,
      now: at(10),
    })).toMatchObject({
      eventAllowed: false,
      bubbleAllowed: false,
      reason: "daily-limit",
    });
  });

  test("celebrate_big has no daily count limit but still obeys cooldown and quiet hours", () => {
    const firstAt = at(8);
    let state = recordBubble(createProactiveExpressionState(firstAt), "celebrate_big", firstAt);
    state = recordBubble(state, "celebrate_big", at(9));
    state = recordBubble(state, "celebrate_big", at(10));
    expect(state.triggerCounts.celebrate_big).toBe(3);
    expect(evaluateProactiveSemanticEvent({
      event: "celebrate_big",
      state,
      now: at(10, 1),
    })).toMatchObject({
      eventAllowed: true,
      bubbleAllowed: false,
      reason: "bubble-cooldown",
    });
    expect(evaluateProactiveSemanticEvent({
      event: "celebrate_big",
      state,
      now: at(23, 30),
    })).toMatchObject({
      eventAllowed: false,
      bubbleAllowed: false,
      reason: "quiet-hours",
    });
  });

  test("idle_alive uses the same quiet-hours gate without consuming bubble cooldown", () => {
    const firstAt = at(8);
    const initial = createProactiveExpressionState(firstAt);
    const decision = evaluateProactiveSemanticEvent({
      event: "idle_alive",
      state: initial,
      now: firstAt,
    });
    expect(decision).toMatchObject({
      eventAllowed: true,
      bubbleAllowed: false,
    });
    const afterIdle = recordProactiveSemanticEventSuccess(
      decision.state,
      "idle_alive",
      firstAt,
      true,
    );
    expect(afterIdle.lastActiveBubbleAt).toBeNull();
    expect(evaluateProactiveSemanticEvent({
      event: "morning_greet",
      state: afterIdle,
      now: at(8, 1),
    }).bubbleAllowed).toBe(true);
    expect(evaluateProactiveSemanticEvent({
      event: "idle_alive",
      state: afterIdle,
      now: at(23, 30),
    }).reason).toBe("quiet-hours");
  });

  test("resets daily counts after local midnight while retaining cross-midnight cooldown", () => {
    const beforeMidnight = at(23, 50);
    const state = recordProactiveSemanticEventSuccess(
      createProactiveExpressionState(beforeMidnight),
      "morning_greet",
      beforeMidnight,
      true,
    );
    const afterMidnight = at(0, 10, 27);
    const normalized = normalizeProactiveExpressionState(state, afterMidnight);

    expect(normalized.currentLocalDate).toBe("2026-07-27");
    expect(normalized.triggerCounts.morning_greet).toBe(0);
    expect(normalized.bubbleCounts.morning_greet).toBe(0);
    expect(evaluateProactiveSemanticEvent({
      event: "morning_greet",
      state: normalized,
      now: afterMidnight,
      quietHours: { startTime: "02:00", endTime: "03:00" },
    })).toMatchObject({
      eventAllowed: false,
      bubbleAllowed: false,
      reason: "bubble-cooldown",
    });
  });

  test("persists counts across restart and continues limiting", () => {
    const now = at(8);
    const target = storage();
    const state = recordBubble(
      createProactiveExpressionState(now),
      "morning_greet",
      now,
    );
    expect(writeProactiveExpressionState(state, target)).toBe(true);
    expect(target.setItem).toHaveBeenCalledWith(
      PROACTIVE_EXPRESSION_STORAGE_KEY,
      JSON.stringify(state),
    );

    const restarted = readProactiveExpressionState(target, at(10));
    expect(restarted.triggerCounts.morning_greet).toBe(1);
    expect(evaluateProactiveSemanticEvent({
      event: "morning_greet",
      state: restarted,
      now: at(10),
    }).reason).toBe("daily-limit");
  });

  test("persists opaque delivery receipts in the existing taskState and migrates legacy keys", () => {
    const now = at(8);
    const base = createProactiveExpressionState(now);
    const taskState = createProactiveTaskState();
    taskState.deliveredKeys = ["legacy-event"];
    taskState.deliveryReceipts = {
      "confirmed-event": {
        status: "confirmed",
        updatedAt: now.toISOString(),
      },
      "blocked-event": {
        status: "blocked",
        updatedAt: now.toISOString(),
      },
    };
    const target = storage();
    expect(writeProactiveExpressionState({ ...base, taskState }, target)).toBe(true);
    const restarted = readProactiveExpressionState(target, now);

    expect(restarted.taskState?.deliveryReceipts).toMatchObject({
      "confirmed-event": { status: "confirmed" },
      "blocked-event": { status: "blocked" },
      "legacy-event": { status: "confirmed" },
    });
    expect(restarted.taskState?.deliveryReservations).toMatchObject({
      "blocked-event": "blocked",
    });
    expect(JSON.stringify(restarted.taskState?.deliveryReceipts)).not.toContain("title");
    expect(JSON.stringify(restarted.taskState?.deliveryReceipts)).not.toContain("note");
  });

  test("fails closed for malformed receipt status or timestamp", () => {
    const now = at(8);
    const base = createProactiveExpressionState(now);
    const taskState = createProactiveTaskState();
    const malformed = {
      ...base,
      taskState: {
        ...taskState,
        deliveryReceipts: {
          "event-1": { status: "active", updatedAt: now.toISOString() },
        },
      },
    };
    const target = storage(JSON.stringify(malformed));
    const restarted = readProactiveExpressionState(target, at(9));

    expect(restarted.conservativeSilenceDate).toBe("2026-07-26");
    expect(restarted.taskState).toBeUndefined();
  });

  test("computes default and custom cross-midnight quiet windows", () => {
    expect(quietHoursFromBedtime("23:00")).toEqual({
      startTime: "23:00",
      endTime: "07:00",
    });
    const custom = quietHoursFromBedtime("01:30");
    expect(custom).toEqual({ startTime: "01:30", endTime: "09:30" });
    expect(isWithinQuietHours(at(23, 30), quietHoursFromBedtime("23:00"))).toBe(true);
    expect(isWithinQuietHours(at(6, 59, 27), quietHoursFromBedtime("23:00"))).toBe(true);
    expect(isWithinQuietHours(at(7, 0, 27), quietHoursFromBedtime("23:00"))).toBe(false);
    expect(isWithinQuietHours(at(1, 29), custom)).toBe(false);
    expect(isWithinQuietHours(at(1, 30), custom)).toBe(true);
    expect(isWithinQuietHours(at(9, 30), custom)).toBe(false);
  });

  test("silences conservatively after system time rollback", () => {
    const future = at(15);
    const state = recordBubble(
      createProactiveExpressionState(future),
      "celebrate_big",
      future,
    );
    const rolledBack = evaluateProactiveSemanticEvent({
      event: "idle_alive",
      state,
      now: at(14),
    });
    expect(rolledBack).toMatchObject({
      eventAllowed: false,
      bubbleAllowed: false,
      reason: "conservative-silence",
    });
    expect(rolledBack.state.conservativeSilenceDate).toBe("2026-07-26");
  });

  test.each([
    "not-json",
    JSON.stringify({ schemaVersion: 99 }),
    JSON.stringify({
      ...createProactiveExpressionState(at(8)),
      triggerCounts: { morning_greet: -1 },
    }),
    JSON.stringify({
      ...createProactiveExpressionState(at(8)),
      lastEvaluatedAt: "not-a-time",
    }),
  ])("treats damaged or unsupported storage as conservative silence", (raw) => {
    const state = readProactiveExpressionState(storage(raw), at(9));
    expect(state.conservativeSilenceDate).toBe("2026-07-26");
    expect(evaluateProactiveSemanticEvent({
      event: "celebrate_big",
      state,
      now: at(9),
    }).reason).toBe("conservative-silence");
  });

  test("blocked events do not mutate state or create a deferred queue", () => {
    const now = at(23, 30);
    const state = createProactiveExpressionState(now);
    const decision = evaluateProactiveSemanticEvent({
      event: "morning_greet",
      state,
      now,
    });
    expect(decision.reason).toBe("quiet-hours");
    expect(decision.state.triggerCounts.morning_greet).toBe(0);
    expect(decision.state.bubbleCounts.morning_greet).toBe(0);
    expect(Object.keys(decision.state).sort()).toEqual([
      "bubbleCounts",
      "conservativeSilenceDate",
      "currentLocalDate",
      "lastActiveBubbleAt",
      "lastEvaluatedAt",
      "schemaVersion",
      "triggerCounts",
    ]);
  });

  test("formal task and care reminders bypass the strictest proactive gate", () => {
    const now = at(23);
    const fullCounts = Object.fromEntries(
      PROACTIVE_SEMANTIC_EVENTS.map((event) => [event, 99]),
    ) as ProactiveExpressionState["triggerCounts"];
    const strictState: ProactiveExpressionState = {
      ...createProactiveExpressionState(now),
      lastActiveBubbleAt: now.toISOString(),
      triggerCounts: fullCounts,
      bubbleCounts: { ...fullCounts },
    };
    expect(evaluateProactiveSemanticEvent({
      event: "recall_memory",
      state: strictState,
      now,
    })).toMatchObject({
      eventAllowed: false,
      bubbleAllowed: false,
      reason: "quiet-hours",
    });

    const taskDatabase = createTask(EMPTY_TASK_DATABASE, {
      title: "正式到期待办",
      dueAt: "2026-07-26T15:00:00.000Z",
      schedulePrecision: "datetime",
      remindAt: "2026-07-26T15:00:00.000Z",
    }, "2026-07-26T14:00:00.000Z").database;
    expect(triggerDueReminders(
      taskDatabase,
      "2026-07-26T15:00:00.000Z",
    ).triggered).toHaveLength(1);

    expect(selectDueCareReminder({
      now: now.getTime(),
      deliveredKeys: [],
      nextWellnessTime: Number.POSITIVE_INFINITY,
    })).toEqual({
      kind: "sleep",
      deliveredKey: "2026-07-26:sleep",
      source: "timed",
    });
  });
});
