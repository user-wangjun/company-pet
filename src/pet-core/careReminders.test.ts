import { describe, expect, test, vi } from "vitest";
import {
  CARE_REMINDER_STORAGE_KEY,
  DEFAULT_CARE_REMINDER_SETTINGS,
  markCareReminderDelivered,
  readCareReminderState,
  selectDueCareReminder,
  selectTimedCareReminder,
  unmarkCareReminderDelivered,
  writeCareReminderState,
  type CareReminderStorage,
} from "./careReminders";

function storage(initial: string | null = null): CareReminderStorage {
  let value = initial;
  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((_key, nextValue) => {
      value = nextValue;
    }),
  };
}

describe("care reminder persistence", () => {
  test("defaults to meal and sleep system popups only", () => {
    expect(DEFAULT_CARE_REMINDER_SETTINGS.eyeCare.enabled).toBe(false);
    expect(DEFAULT_CARE_REMINDER_SETTINGS.water.enabled).toBe(false);
    expect(DEFAULT_CARE_REMINDER_SETTINGS.meal.enabled).toBe(true);
    expect(DEFAULT_CARE_REMINDER_SETTINGS.meal.lunchTime).toBe("12:00");
    expect(DEFAULT_CARE_REMINDER_SETTINGS.sleep.enabled).toBe(true);
  });

  test("selects each meal slot and one overnight sleep slot", () => {
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 8, 30), [])).toEqual({
      kind: "meal",
      key: "2026-06-23:meal-breakfast",
    });
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 12, 0), [])).toEqual({
      kind: "meal",
      key: "2026-06-23:meal-lunch",
    });
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 13, 44), [])).toEqual({
      kind: "meal",
      key: "2026-06-23:meal-lunch",
    });
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 18, 30), [])).toEqual({
      kind: "meal",
      key: "2026-06-23:meal-dinner",
    });
    expect(selectTimedCareReminder(new Date(2026, 5, 24, 1, 0), [])).toEqual({
      kind: "sleep",
      key: "2026-06-23:sleep",
    });
  });

  test("does not redeliver a persisted slot after restart", () => {
    const first = selectTimedCareReminder(
      new Date(2026, 5, 23, 12, 0),
      [],
    );
    const delivered = markCareReminderDelivered([], first!.key);

    expect(
      selectTimedCareReminder(new Date(2026, 5, 23, 12, 15), delivered),
    ).toBeNull();
  });

  test("does not create reminders outside approved time windows", () => {
    for (const hour of [6, 7, 10, 11, 15, 17, 21, 22]) {
      expect(
        selectTimedCareReminder(new Date(2026, 5, 23, hour, 0), []),
      ).toBeNull();
    }
  });

  test("holds meal reminders until the 10-minute snooze ends inside the meal window", () => {
    const lunchTime = new Date(2026, 5, 23, 12, 0).getTime();

    expect(
      selectDueCareReminder({
        now: lunchTime,
        deliveredKeys: [],
        nextEyeCareTime: 0,
        timedSnoozedUntil: lunchTime + 10 * 60 * 1000,
      }),
    ).toEqual({
      kind: "eyeCare",
      source: "random",
    });
    expect(
      selectDueCareReminder({
        now: lunchTime + 10 * 60 * 1000,
        deliveredKeys: [],
        nextEyeCareTime: 0,
        timedSnoozedUntil: lunchTime + 10 * 60 * 1000,
      }),
    ).toEqual({
      kind: "meal",
      deliveredKey: "2026-06-23:meal-lunch",
      source: "timed",
    });
    expect(
      selectDueCareReminder({
        now: new Date(2026, 5, 23, 15, 0).getTime(),
        deliveredKeys: [],
        nextEyeCareTime: Number.POSITIVE_INFINITY,
        timedSnoozedUntil: new Date(2026, 5, 23, 15, 0).getTime(),
      }),
    ).toBeNull();
  });

  test("prioritizes sleep over overdue random care reminders", () => {
    expect(
      selectDueCareReminder({
        now: new Date(2026, 5, 23, 23, 0).getTime(),
        deliveredKeys: [],
        nextEyeCareTime: 0,
      }),
    ).toEqual({
      kind: "sleep",
      deliveredKey: "2026-06-23:sleep",
      source: "timed",
    });
  });

  test("selects overdue random reminders only when no timed reminder is due", () => {
    expect(
      selectDueCareReminder({
        now: new Date(2026, 5, 23, 21, 0).getTime(),
        deliveredKeys: [],
        nextEyeCareTime: 0,
      }),
    ).toEqual({
      kind: "eyeCare",
      source: "random",
    });
  });

  test("deduplicates delivered keys without reordering existing entries", () => {
    expect(markCareReminderDelivered(["a", "b", "a"], "b")).toEqual([
      "a",
      "b",
      "a",
    ]);
    expect(markCareReminderDelivered(["a"], "b")).toEqual(["a", "b"]);
    expect(unmarkCareReminderDelivered(["a", "b", "a"], "a")).toEqual(["b"]);
  });

  test("migrates the old 11:00 lunch default without overwriting later custom times", () => {
    const legacy = storage(JSON.stringify({
      deliveredKeys: [],
      settings: {
        ...DEFAULT_CARE_REMINDER_SETTINGS,
        meal: { ...DEFAULT_CARE_REMINDER_SETTINGS.meal, lunchTime: "11:00" },
      },
      systemPopupNoticeDismissed: false,
    }));
    expect(readCareReminderState(legacy).settings.meal.lunchTime).toBe("12:00");

    const current = storage(JSON.stringify({
      defaultsVersion: 2,
      deliveredKeys: [],
      settings: {
        ...DEFAULT_CARE_REMINDER_SETTINGS,
        meal: { ...DEFAULT_CARE_REMINDER_SETTINGS.meal, lunchTime: "11:00" },
      },
      systemPopupNoticeDismissed: false,
    }));
    expect(readCareReminderState(current).settings.meal.lunchTime).toBe("11:00");
  });

  test("repairs invalid storage and writes the versioned key", () => {
    const target = storage("not-json");

    expect(readCareReminderState(target)).toEqual({ defaultsVersion: 3, deliveredKeys: [], settings: DEFAULT_CARE_REMINDER_SETTINGS, systemPopupNoticeDismissed: false });
    expect(
      writeCareReminderState(
        { defaultsVersion: 3, deliveredKeys: ["2026-06-23:meal-lunch"], settings: DEFAULT_CARE_REMINDER_SETTINGS, systemPopupNoticeDismissed: false },
        target,
      ),
    ).toBe(true);
    expect(target.setItem).toHaveBeenCalledWith(
      CARE_REMINDER_STORAGE_KEY,
      JSON.stringify({ defaultsVersion: 3, deliveredKeys: ["2026-06-23:meal-lunch"], settings: DEFAULT_CARE_REMINDER_SETTINGS, systemPopupNoticeDismissed: false }),
    );
  });

  test("repairs malformed delivered keys in storage", () => {
    const target = storage(
      JSON.stringify({
        deliveredKeys: ["2026-06-23:meal-lunch", 1, null, "2026-06-23:sleep"],
      }),
    );

    expect(readCareReminderState(target)).toEqual({
      defaultsVersion: 3,
      deliveredKeys: ["2026-06-23:meal-lunch", "2026-06-23:sleep"],
      settings: DEFAULT_CARE_REMINDER_SETTINGS,
      systemPopupNoticeDismissed: false,
    });
  });

  test("reports write failure when storage throws", () => {
    const target: CareReminderStorage = {
      getItem: vi.fn(),
      setItem: vi.fn(() => {
        throw new Error("blocked");
      }),
    };

    expect(writeCareReminderState({ defaultsVersion: 3, deliveredKeys: ["x"], settings: DEFAULT_CARE_REMINDER_SETTINGS, systemPopupNoticeDismissed: false }, target)).toBe(
      false,
    );
  });

  test("persists the choice to hide the system-popup explanation", () => {
    const target = storage(JSON.stringify({
      deliveredKeys: [],
      settings: DEFAULT_CARE_REMINDER_SETTINGS,
      systemPopupNoticeDismissed: true,
    }));
    expect(readCareReminderState(target).systemPopupNoticeDismissed).toBe(true);
  });

  test("uses personalized meal, sleep, water, and eye-care settings", () => {
    const settings = {
      ...DEFAULT_CARE_REMINDER_SETTINGS,
      eyeCare: { enabled: false, intervalMinutes: 60 },
      water: { enabled: true, intervalMinutes: 45 },
      meal: { ...DEFAULT_CARE_REMINDER_SETTINGS.meal, breakfastTime: "09:30" },
      sleep: { enabled: true, bedtime: "00:30" },
    };
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 9, 45), [], settings)?.key).toBe("2026-06-23:meal-breakfast");
    expect(selectTimedCareReminder(new Date(2026, 5, 24, 1, 0), [], settings)?.key).toBe("2026-06-24:sleep");
    expect(selectDueCareReminder({ now: new Date(2026, 5, 23, 16, 0).getTime(), deliveredKeys: [], nextEyeCareTime: 0, settings })).toEqual({ kind: "eyeCare", source: "random" });
  });

  test("system-popup switches never disable pet care reminders", () => {
    const settings = {
      eyeCare: { enabled: false, intervalMinutes: 40 },
      water: { enabled: false, intervalMinutes: 75 },
      meal: { ...DEFAULT_CARE_REMINDER_SETTINGS.meal, enabled: false },
      sleep: { ...DEFAULT_CARE_REMINDER_SETTINGS.sleep, enabled: false },
    };
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 12, 0), [], settings)?.kind).toBe("meal");
    expect(selectDueCareReminder({ now: new Date(2026, 5, 23, 16, 0).getTime(), deliveredKeys: [], nextEyeCareTime: 0, settings })).toEqual({ kind: "eyeCare", source: "random" });
  });
});
