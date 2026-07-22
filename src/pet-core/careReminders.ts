import type { PetReminderKind } from "./petInteractionManifest";

export const CARE_REMINDER_STORAGE_KEY = "yuxin-care-reminders-v1";
const CARE_REMINDER_DEFAULTS_VERSION = 3;

export type CareReminderSettings = {
  eyeCare: { enabled: boolean; intervalMinutes: number };
  water: { enabled: boolean; intervalMinutes: number };
  meal: { enabled: boolean; breakfastTime: string; lunchTime: string; dinnerTime: string };
  sleep: { enabled: boolean; bedtime: string };
};

export const DEFAULT_CARE_REMINDER_SETTINGS: CareReminderSettings = {
  eyeCare: { enabled: false, intervalMinutes: 40 },
  water: { enabled: false, intervalMinutes: 40 },
  meal: { enabled: true, breakfastTime: "08:00", lunchTime: "12:00", dinnerTime: "18:00" },
  sleep: { enabled: true, bedtime: "23:00" },
};

export type CareReminderState = {
  defaultsVersion: number;
  deliveredKeys: string[];
  settings: CareReminderSettings;
  systemPopupNoticeDismissed: boolean;
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
  timedSnoozedUntil?: number;
  settings?: CareReminderSettings;
};

function validTime(value: unknown, fallback: string): string {
  return typeof value === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(value) ? value : fallback;
}

function validInterval(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 15 && value <= 240
    ? Math.round(value)
    : fallback;
}

export function normalizeCareReminderSettings(value: Partial<CareReminderSettings> | undefined): CareReminderSettings {
  const defaults = DEFAULT_CARE_REMINDER_SETTINGS;
  const wellnessEnabled = value?.eyeCare?.enabled === true || value?.water?.enabled === true;
  const wellnessInterval = validInterval(value?.eyeCare?.intervalMinutes, defaults.eyeCare.intervalMinutes);
  return {
    eyeCare: {
      enabled: wellnessEnabled,
      intervalMinutes: wellnessInterval,
    },
    water: {
      enabled: wellnessEnabled,
      intervalMinutes: wellnessInterval,
    },
    meal: {
      enabled: typeof value?.meal?.enabled === "boolean" ? value.meal.enabled : defaults.meal.enabled,
      breakfastTime: validTime(value?.meal?.breakfastTime, defaults.meal.breakfastTime),
      lunchTime: validTime(value?.meal?.lunchTime, defaults.meal.lunchTime),
      dinnerTime: validTime(value?.meal?.dinnerTime, defaults.meal.dinnerTime),
    },
    sleep: {
      enabled: typeof value?.sleep?.enabled === "boolean" ? value.sleep.enabled : defaults.sleep.enabled,
      bedtime: validTime(value?.sleep?.bedtime, defaults.sleep.bedtime),
    },
  };
}

function dateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function minutesOfDay(value: string): number {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

function minutesSince(now: number, target: number): number {
  return (now - target + 24 * 60) % (24 * 60);
}

export function selectTimedCareReminder(
  date: Date,
  deliveredKeys: string[],
  settings: CareReminderSettings = DEFAULT_CARE_REMINDER_SETTINGS,
): TimedCareReminder | null {
  const nowMinutes = date.getHours() * 60 + date.getMinutes();
  let reminder: TimedCareReminder | null = null;
  const mealSlots = [
    ["breakfast", settings.meal.breakfastTime, 120],
    ["lunch", settings.meal.lunchTime, 180],
    ["dinner", settings.meal.dinnerTime, 180],
  ] as const;
  const slot = mealSlots.find(([, time, window]) => minutesSince(nowMinutes, minutesOfDay(time)) < window);
  if (slot) reminder = { kind: "meal", key: `${dateKey(date)}:meal-${slot[0]}` };
  if (!reminder) {
    const sinceBedtime = minutesSince(nowMinutes, minutesOfDay(settings.sleep.bedtime));
    if (sinceBedtime < 420) {
      const bedtimeDate = new Date(date.getTime() - sinceBedtime * 60_000);
      reminder = { kind: "sleep", key: `${dateKey(bedtimeDate)}:sleep` };
    }
  }

  return reminder && !deliveredKeys.includes(reminder.key) ? reminder : null;
}

export function selectDueCareReminder({
  now,
  deliveredKeys,
  nextEyeCareTime,
  timedSnoozedUntil = 0,
  settings = DEFAULT_CARE_REMINDER_SETTINGS,
}: CareReminderSchedule): DueCareReminder | null {
  const timedReminder = selectTimedCareReminder(new Date(now), deliveredKeys, settings);

  if (timedReminder && now >= timedSnoozedUntil) {
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

  return null;
}

export function markCareReminderDelivered(
  deliveredKeys: string[],
  key: string,
): string[] {
  return deliveredKeys.includes(key) ? deliveredKeys : [...deliveredKeys, key];
}

export function unmarkCareReminderDelivered(
  deliveredKeys: string[],
  key: string,
): string[] {
  return deliveredKeys.filter((deliveredKey) => deliveredKey !== key);
}

export function readCareReminderState(
  storage: CareReminderStorage | null =
    typeof window === "undefined" ? null : window.localStorage,
): CareReminderState {
  if (!storage) return { defaultsVersion: CARE_REMINDER_DEFAULTS_VERSION, deliveredKeys: [], settings: normalizeCareReminderSettings(undefined), systemPopupNoticeDismissed: false };

  try {
    const value = JSON.parse(storage.getItem(CARE_REMINDER_STORAGE_KEY) ?? "");
    let settings = normalizeCareReminderSettings(value?.settings);
    if (
      (typeof value?.defaultsVersion !== "number" || value.defaultsVersion < 2) &&
      settings.meal.lunchTime === "11:00"
    ) {
      settings = {
        ...settings,
        meal: { ...settings.meal, lunchTime: DEFAULT_CARE_REMINDER_SETTINGS.meal.lunchTime },
      };
    }

    return {
      defaultsVersion: CARE_REMINDER_DEFAULTS_VERSION,
      deliveredKeys: Array.isArray(value?.deliveredKeys)
        ? [
            ...new Set<string>(
              value.deliveredKeys.filter(
                (key: unknown): key is string => typeof key === "string",
              ),
            ),
          ]
        : [],
      settings,
      systemPopupNoticeDismissed: value?.systemPopupNoticeDismissed === true,
    };
  } catch {
    return { defaultsVersion: CARE_REMINDER_DEFAULTS_VERSION, deliveredKeys: [], settings: normalizeCareReminderSettings(undefined), systemPopupNoticeDismissed: false };
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
