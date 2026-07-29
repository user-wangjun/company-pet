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
    expect(DEFAULT_CARE_REMINDER_SETTINGS.wellness.enabled).toBe(false);
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
        nextWellnessTime: 0,
        timedSnoozedUntil: lunchTime + 10 * 60 * 1000,
      }),
    ).toEqual({
      kind: "wellness",
      source: "random",
    });
    expect(
      selectDueCareReminder({
        now: lunchTime + 10 * 60 * 1000,
        deliveredKeys: [],
        nextWellnessTime: 0,
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
        nextWellnessTime: Number.POSITIVE_INFINITY,
        timedSnoozedUntil: new Date(2026, 5, 23, 15, 0).getTime(),
      }),
    ).toBeNull();
  });

  test("prioritizes sleep over overdue random care reminders", () => {
    expect(
      selectDueCareReminder({
        now: new Date(2026, 5, 23, 23, 0).getTime(),
        deliveredKeys: [],
        nextWellnessTime: 0,
      }),
    ).toEqual({
      kind: "sleep",
      deliveredKey: "2026-06-23:sleep",
      source: "timed",
    });
  });

  test("confirms and snoozes sleep prompts without duplicating the delivered key", () => {
    const bedtime = new Date(2026, 5, 23, 23, 0).getTime();
    const first = selectDueCareReminder({
      now: bedtime,
      deliveredKeys: [],
      nextWellnessTime: Number.POSITIVE_INFINITY,
    });
    expect(first).toEqual({
      kind: "sleep",
      deliveredKey: "2026-06-23:sleep",
      source: "timed",
    });
    if (!first || first.source !== "timed") throw new Error("expected timed sleep reminder");

    const provisionallyDelivered = markCareReminderDelivered([], first.deliveredKey);
    expect(selectTimedCareReminder(new Date(bedtime + 60_000), provisionallyDelivered)).toBeNull();

    const reopened = unmarkCareReminderDelivered(provisionallyDelivered, first.deliveredKey);
    expect(selectDueCareReminder({
      now: bedtime + 9 * 60_000,
      deliveredKeys: reopened,
      nextWellnessTime: Number.POSITIVE_INFINITY,
      timedSnoozedUntil: bedtime + 10 * 60_000,
    })).toBeNull();
    const repeated = selectDueCareReminder({
      now: bedtime + 10 * 60_000,
      deliveredKeys: reopened,
      nextWellnessTime: Number.POSITIVE_INFINITY,
      timedSnoozedUntil: bedtime + 10 * 60_000,
    });
    expect(repeated).toMatchObject({ kind: "sleep", deliveredKey: first.deliveredKey });

    const confirmed = markCareReminderDelivered(reopened, first.deliveredKey);
    expect(markCareReminderDelivered(confirmed, first.deliveredKey)).toEqual(confirmed);
  });

  test("selects the combined eye-care and water reminder when no timed reminder is due", () => {
    expect(
      selectDueCareReminder({
        now: new Date(2026, 5, 23, 21, 0).getTime(),
        deliveredKeys: [],
        nextWellnessTime: 0,
      }),
    ).toEqual({
      kind: "wellness",
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

  test.each([
    [{ enabled: false, intervalMinutes: 60 }, { enabled: false, intervalMinutes: 75 }, false, 60],
    [{ enabled: true, intervalMinutes: 60 }, { enabled: false, intervalMinutes: 75 }, true, 60],
    [{ enabled: false, intervalMinutes: 60 }, { enabled: true, intervalMinutes: 75 }, true, 75],
    [{ enabled: true, intervalMinutes: 45 }, { enabled: true, intervalMinutes: 75 }, true, 75],
  ])(
    "migrates legacy eyeCare=%j and water=%j into one wellness setting",
    (eyeCare, water, enabled, intervalMinutes) => {
      const target = storage(JSON.stringify({
        defaultsVersion: 3,
        deliveredKeys: [],
        settings: {
          eyeCare,
          water,
          meal: DEFAULT_CARE_REMINDER_SETTINGS.meal,
          sleep: DEFAULT_CARE_REMINDER_SETTINGS.sleep,
        },
      }));

      const migrated = readCareReminderState(target);
      expect(migrated.settings).toEqual({
        wellness: { enabled, intervalMinutes },
        meal: DEFAULT_CARE_REMINDER_SETTINGS.meal,
        sleep: DEFAULT_CARE_REMINDER_SETTINGS.sleep,
      });
      expect(migrated.settings).not.toHaveProperty("eyeCare");
      expect(migrated.settings).not.toHaveProperty("water");
    },
  );

  test("prefers the current wellness field and writes no legacy dead settings", () => {
    const target = storage(JSON.stringify({
      defaultsVersion: 4,
      deliveredKeys: [],
      settings: {
        wellness: { enabled: true, intervalMinutes: 90 },
        eyeCare: { enabled: false, intervalMinutes: 20 },
        water: { enabled: false, intervalMinutes: 20 },
        meal: DEFAULT_CARE_REMINDER_SETTINGS.meal,
        sleep: DEFAULT_CARE_REMINDER_SETTINGS.sleep,
      },
    }));

    const state = readCareReminderState(target);
    expect(state.settings.wellness).toEqual({ enabled: true, intervalMinutes: 90 });
    expect(writeCareReminderState(state, target)).toBe(true);
    const serialized = target.getItem(CARE_REMINDER_STORAGE_KEY) ?? "";
    expect(serialized).toContain('"wellness"');
    expect(serialized).not.toContain('"eyeCare"');
    expect(serialized).not.toContain('"water"');
  });

  test("repairs invalid storage and writes the versioned key", () => {
    const target = storage("not-json");

    expect(readCareReminderState(target)).toEqual({ defaultsVersion: 4, deliveredKeys: [], settings: DEFAULT_CARE_REMINDER_SETTINGS, systemPopupNoticeDismissed: false });
    expect(
      writeCareReminderState(
        { defaultsVersion: 4, deliveredKeys: ["2026-06-23:meal-lunch"], settings: DEFAULT_CARE_REMINDER_SETTINGS, systemPopupNoticeDismissed: false },
        target,
      ),
    ).toBe(true);
    expect(target.setItem).toHaveBeenCalledWith(
      CARE_REMINDER_STORAGE_KEY,
      JSON.stringify({ defaultsVersion: 4, deliveredKeys: ["2026-06-23:meal-lunch"], settings: DEFAULT_CARE_REMINDER_SETTINGS, systemPopupNoticeDismissed: false }),
    );
  });

  test("repairs malformed delivered keys in storage", () => {
    const target = storage(
      JSON.stringify({
        deliveredKeys: ["2026-06-23:meal-lunch", 1, null, "2026-06-23:sleep"],
      }),
    );

    expect(readCareReminderState(target)).toEqual({
      defaultsVersion: 4,
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

    expect(writeCareReminderState({ defaultsVersion: 4, deliveredKeys: ["x"], settings: DEFAULT_CARE_REMINDER_SETTINGS, systemPopupNoticeDismissed: false }, target)).toBe(
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

  test("uses personalized meal, sleep, and combined wellness settings", () => {
    const settings = {
      ...DEFAULT_CARE_REMINDER_SETTINGS,
      wellness: { enabled: true, intervalMinutes: 45 },
      meal: { ...DEFAULT_CARE_REMINDER_SETTINGS.meal, breakfastTime: "09:30" },
      sleep: { enabled: true, bedtime: "00:30" },
    };
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 9, 45), [], settings)?.key).toBe("2026-06-23:meal-breakfast");
    expect(selectTimedCareReminder(new Date(2026, 5, 24, 1, 0), [], settings)?.key).toBe("2026-06-24:sleep");
    expect(selectDueCareReminder({ now: new Date(2026, 5, 23, 16, 0).getTime(), deliveredKeys: [], nextWellnessTime: 0, settings })).toEqual({ kind: "wellness", source: "random" });
  });

  test("system-popup switches never disable pet care reminders", () => {
    const settings = {
      wellness: { enabled: false, intervalMinutes: 75 },
      meal: { ...DEFAULT_CARE_REMINDER_SETTINGS.meal, enabled: false },
      sleep: { ...DEFAULT_CARE_REMINDER_SETTINGS.sleep, enabled: false },
    };
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 12, 0), [], settings)?.kind).toBe("meal");
    expect(selectDueCareReminder({ now: new Date(2026, 5, 23, 16, 0).getTime(), deliveredKeys: [], nextWellnessTime: 0, settings })).toEqual({ kind: "wellness", source: "random" });
  });
});
