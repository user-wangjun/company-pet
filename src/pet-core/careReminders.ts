import type { PetReminderKind } from "./petInteractionManifest";

export const CARE_REMINDER_STORAGE_KEY = "yuxin-care-reminders-v1";

export type CareReminderState = {
  deliveredKeys: string[];
};

export type CareReminderStorage = Pick<Storage, "getItem" | "setItem">;

export type TimedCareReminder = {
  kind: Extract<PetReminderKind, "meal" | "sleep">;
  key: string;
};

export type DueCareReminder =
  | {
      kind: Extract<PetReminderKind, "meal" | "sleep">;
      deliveredKey: string;
      source: "timed";
    }
  | {
      kind: Extract<PetReminderKind, "eyeCare" | "water">;
      source: "random";
    };

export type CareReminderSchedule = {
  now: number;
  deliveredKeys: string[];
  nextEyeCareTime: number;
  nextWaterCareTime: number;
};

function dateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function sleepDate(date: Date): Date {
  if (date.getHours() >= 6) return date;
  const previous = new Date(date);
  previous.setDate(previous.getDate() - 1);
  return previous;
}

export function selectTimedCareReminder(
  date: Date,
  deliveredKeys: string[],
): TimedCareReminder | null {
  const hour = date.getHours();
  let reminder: TimedCareReminder | null = null;

  if (hour >= 7 && hour < 9) {
    reminder = { kind: "meal", key: `${dateKey(date)}:meal-breakfast` };
  } else if (hour >= 11 && hour < 13) {
    reminder = { kind: "meal", key: `${dateKey(date)}:meal-lunch` };
  } else if (hour >= 18 && hour < 20) {
    reminder = { kind: "meal", key: `${dateKey(date)}:meal-dinner` };
  } else if (hour >= 23 || hour < 6) {
    reminder = { kind: "sleep", key: `${dateKey(sleepDate(date))}:sleep` };
  }

  return reminder && !deliveredKeys.includes(reminder.key) ? reminder : null;
}

export function selectDueCareReminder({
  now,
  deliveredKeys,
  nextEyeCareTime,
  nextWaterCareTime,
}: CareReminderSchedule): DueCareReminder | null {
  const timedReminder = selectTimedCareReminder(new Date(now), deliveredKeys);

  if (timedReminder) {
    return {
      kind: timedReminder.kind,
      deliveredKey: timedReminder.key,
      source: "timed",
    };
  }

  if (now >= nextEyeCareTime) {
    return {
      kind: "eyeCare",
      source: "random",
    };
  }

  if (now >= nextWaterCareTime) {
    return {
      kind: "water",
      source: "random",
    };
  }

  return null;
}

export function markCareReminderDelivered(
  deliveredKeys: string[],
  key: string,
): string[] {
  return deliveredKeys.includes(key) ? deliveredKeys : [...deliveredKeys, key];
}

export function readCareReminderState(
  storage: CareReminderStorage | null =
    typeof window === "undefined" ? null : window.localStorage,
): CareReminderState {
  if (!storage) return { deliveredKeys: [] };

  try {
    const value = JSON.parse(storage.getItem(CARE_REMINDER_STORAGE_KEY) ?? "");
    return {
      deliveredKeys: Array.isArray(value?.deliveredKeys)
        ? [
            ...new Set<string>(
              value.deliveredKeys.filter(
                (key: unknown): key is string => typeof key === "string",
              ),
            ),
          ]
        : [],
    };
  } catch {
    return { deliveredKeys: [] };
  }
}

export function writeCareReminderState(
  state: CareReminderState,
  storage: CareReminderStorage | null =
    typeof window === "undefined" ? null : window.localStorage,
): boolean {
  if (!storage) return false;

  try {
    storage.setItem(CARE_REMINDER_STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}
