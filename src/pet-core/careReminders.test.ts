import { describe, expect, test, vi } from "vitest";
import {
  CARE_REMINDER_STORAGE_KEY,
  markCareReminderDelivered,
  readCareReminderState,
  selectDueCareReminder,
  selectTimedCareReminder,
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
  test("selects each meal slot and one overnight sleep slot", () => {
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 7, 30), [])).toEqual({
      kind: "meal",
      key: "2026-06-23:meal-breakfast",
    });
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 12, 0), [])).toEqual({
      kind: "meal",
      key: "2026-06-23:meal-lunch",
    });
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 19, 0), [])).toEqual({
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
      selectTimedCareReminder(new Date(2026, 5, 23, 12, 30), delivered),
    ).toBeNull();
  });

  test("does not create reminders outside approved time windows", () => {
    for (const hour of [6, 9, 10, 13, 17, 20, 22]) {
      expect(
        selectTimedCareReminder(new Date(2026, 5, 23, hour, 0), []),
      ).toBeNull();
    }
  });

  test("prioritizes sleep over overdue random care reminders", () => {
    expect(
      selectDueCareReminder({
        now: new Date(2026, 5, 23, 23, 0).getTime(),
        deliveredKeys: [],
        nextEyeCareTime: 0,
        nextWaterCareTime: 0,
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
        nextWaterCareTime: 0,
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
  });

  test("repairs invalid storage and writes the versioned key", () => {
    const target = storage("not-json");

    expect(readCareReminderState(target)).toEqual({ deliveredKeys: [] });
    expect(
      writeCareReminderState(
        { deliveredKeys: ["2026-06-23:meal-lunch"] },
        target,
      ),
    ).toBe(true);
    expect(target.setItem).toHaveBeenCalledWith(
      CARE_REMINDER_STORAGE_KEY,
      JSON.stringify({ deliveredKeys: ["2026-06-23:meal-lunch"] }),
    );
  });

  test("repairs malformed delivered keys in storage", () => {
    const target = storage(
      JSON.stringify({
        deliveredKeys: ["2026-06-23:meal-lunch", 1, null, "2026-06-23:sleep"],
      }),
    );

    expect(readCareReminderState(target)).toEqual({
      deliveredKeys: ["2026-06-23:meal-lunch", "2026-06-23:sleep"],
    });
  });

  test("reports write failure when storage throws", () => {
    const target: CareReminderStorage = {
      getItem: vi.fn(),
      setItem: vi.fn(() => {
        throw new Error("blocked");
      }),
    };

    expect(writeCareReminderState({ deliveredKeys: ["x"] }, target)).toBe(
      false,
    );
  });
});
