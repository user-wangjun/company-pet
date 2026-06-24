import { describe, expect, test } from "vitest";
import {
  completeInteraction,
  createInteractionRuntime,
  requestInteraction,
  setInteractionFacing,
} from "./interactionRuntime";

describe("pet interaction runtime", () => {
  test("allows a direct click to preempt desktop icon work", () => {
    const idle = createInteractionRuntime("right");
    const icon = requestInteraction(idle, {
      kind: "desktopIcon",
      interruptible: true,
    });
    const click = requestInteraction(icon.state, {
      kind: "singleClick",
      interruptible: true,
    });

    expect(icon.decision).toBe("start");
    expect(click.decision).toBe("start");
    expect(click.state.active.kind).toBe("singleClick");
    expect(click.state.active.token).toBeGreaterThan(icon.state.active.token);
    expect(click.state.active.facing).toBe("right");
  });

  test("queues a care reminder while a click is active", () => {
    const click = requestInteraction(createInteractionRuntime("right"), {
      kind: "singleClick",
      interruptible: true,
    });
    const reminder = requestInteraction(click.state, {
      kind: "careReminder",
      interruptible: true,
      payloadKey: "2026-06-23:meal-lunch",
      reminderKind: "meal",
    });

    expect(reminder.decision).toBe("queue");
    expect(reminder.state.active.kind).toBe("singleClick");
    expect(reminder.state.queued).toMatchObject({
      kind: "careReminder",
      payloadKey: "2026-06-23:meal-lunch",
      reminderKind: "meal",
    });
  });

  test("rejects stale completion callbacks", () => {
    const first = requestInteraction(createInteractionRuntime("right"), {
      kind: "idleQuirk",
      interruptible: true,
    });
    const second = requestInteraction(first.state, {
      kind: "doubleClick",
      interruptible: true,
    });

    expect(
      completeInteraction(second.state, first.state.active.token),
    ).toEqual({
      decision: "stale",
      state: second.state,
    });
  });

  test("starts a queued reminder after the active action completes", () => {
    const click = requestInteraction(createInteractionRuntime("left"), {
      kind: "singleClick",
      interruptible: true,
    });
    const queued = requestInteraction(click.state, {
      kind: "careReminder",
      interruptible: true,
      payloadKey: "water",
      reminderKind: "water",
    });
    const completed = completeInteraction(
      queued.state,
      queued.state.active.token,
    );

    expect(completed.decision).toBe("start-queued");
    expect(completed.state.active.kind).toBe("careReminder");
    expect(completed.state.active.facing).toBe("left");
    expect(completed.state.active.payloadKey).toBe("water");
    expect(completed.state.active.reminderKind).toBe("water");
    expect(completed.state.queued).toBeNull();
  });

  test("does not replace a non-interruptible update prompt with drag", () => {
    const prompt = requestInteraction(createInteractionRuntime("right"), {
      kind: "updatePrompt",
      interruptible: false,
    });
    const drag = requestInteraction(prompt.state, {
      kind: "drag",
      interruptible: true,
    });

    expect(drag.decision).toBe("ignore");
    expect(drag.state.active.kind).toBe("updatePrompt");
    expect(drag.state.active.interruptible).toBe(false);
  });

  test("keeps only the latest queued care reminder", () => {
    const click = requestInteraction(createInteractionRuntime("right"), {
      kind: "doubleClick",
      interruptible: true,
    });
    const first = requestInteraction(click.state, {
      kind: "careReminder",
      interruptible: true,
      payloadKey: "first",
      reminderKind: "water",
    });
    const second = requestInteraction(first.state, {
      kind: "careReminder",
      interruptible: true,
      payloadKey: "second",
      reminderKind: "meal",
    });

    expect(second.decision).toBe("queue");
    expect(second.state.queued?.payloadKey).toBe("second");
    expect(second.state.queued?.reminderKind).toBe("meal");
  });

  test("updates facing without changing token priority or queue", () => {
    const click = requestInteraction(createInteractionRuntime("right"), {
      kind: "singleClick",
      interruptible: true,
    });
    const queued = requestInteraction(click.state, {
      kind: "careReminder",
      interruptible: true,
      payloadKey: "queued",
      reminderKind: "eyeCare",
    });
    const updated = setInteractionFacing(queued.state, "left");

    expect(updated.active.facing).toBe("left");
    expect(updated.active.token).toBe(queued.state.active.token);
    expect(updated.active.priority).toBe(queued.state.active.priority);
    expect(updated.queued).toEqual(queued.state.queued);
  });
});
