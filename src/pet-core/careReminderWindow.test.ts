import { describe, expect, it, vi } from "vitest";
import {
  createLatestWindowLayoutScheduler,
  revealHiddenPetForCareReminder,
  shouldResizeReminderWindow,
  shouldUseExpandedReminderWindow,
} from "./careReminderWindow";

describe("shouldUseExpandedReminderWindow", () => {
  it("expands for either a task reminder or a care reminder prompt", () => {
    expect(shouldUseExpandedReminderWindow(1, false)).toBe(true);
    expect(shouldUseExpandedReminderWindow(0, true)).toBe(true);
    expect(shouldUseExpandedReminderWindow(0, false)).toBe(false);
  });

  it("only resizes when the logical reminder window size changes", () => {
    expect(shouldResizeReminderWindow(
      { width: 360, height: 360 },
      { width: 360, height: 360 },
    )).toBe(false);
    expect(shouldResizeReminderWindow(
      { width: 360, height: 360 },
      { width: 460, height: 500 },
    )).toBe(true);
    expect(shouldResizeReminderWindow(
      { width: 460, height: 500 },
      { width: 360, height: 360 },
    )).toBe(true);
  });
});

describe("createLatestWindowLayoutScheduler", () => {
  it("serializes window mutations and skips queued layouts superseded by newer state", async () => {
    let announceFirstStarted = () => {};
    let finishFirst = () => {};
    const firstStarted = new Promise<void>((resolve) => {
      announceFirstStarted = resolve;
    });
    const calls: string[] = [];
    const scheduler = createLatestWindowLayoutScheduler();
    const first = scheduler.schedule(async () => {
      calls.push("first:start");
      announceFirstStarted();
      await new Promise<void>((resolve) => {
        finishFirst = resolve;
      });
      calls.push("first:end");
    });

    await firstStarted;
    const stale = scheduler.schedule(async () => {
      calls.push("stale");
    });
    const latest = scheduler.schedule(async () => {
      calls.push("latest");
    });
    finishFirst();

    await expect(first).resolves.toBe(true);
    await expect(stale).resolves.toBe(false);
    await expect(latest).resolves.toBe(true);
    expect(calls).toEqual(["first:start", "first:end", "latest"]);
  });

  it("continues with the latest layout after an earlier mutation fails", async () => {
    const scheduler = createLatestWindowLayoutScheduler();

    await expect(
      scheduler.schedule(async () => {
        throw new Error("resize failed");
      }),
    ).rejects.toThrow("resize failed");
    await expect(scheduler.schedule(async () => {})).resolves.toBe(true);
  });
});

describe("revealHiddenPetForCareReminder", () => {
  it("shows a hidden pet window", async () => {
    const appWindow = {
      isVisible: vi.fn().mockResolvedValue(false),
      show: vi.fn().mockResolvedValue(undefined),
    };

    await expect(revealHiddenPetForCareReminder(appWindow)).resolves.toBe(true);
    expect(appWindow.show).toHaveBeenCalledOnce();
  });

  it("does not disturb an already visible pet window", async () => {
    const appWindow = {
      isVisible: vi.fn().mockResolvedValue(true),
      show: vi.fn().mockResolvedValue(undefined),
    };

    await expect(revealHiddenPetForCareReminder(appWindow)).resolves.toBe(false);
    expect(appWindow.show).not.toHaveBeenCalled();
  });

  it("does nothing in browser preview", async () => {
    await expect(revealHiddenPetForCareReminder(null)).resolves.toBe(false);
  });
});
