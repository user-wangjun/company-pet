export const CARE_REMINDER_STORAGE_KEY = "yuxin-care-reminders-v1";
const CARE_REMINDER_DEFAULTS_VERSION = 4;

export type CareReminderKind = "wellness" | "meal" | "sleep";

export type CareReminderSettings = {
  wellness: { enabled: boolean; intervalMinutes: number };
  meal: { enabled: boolean; breakfastTime: string; lunchTime: string; dinnerTime: string };
  sleep: { enabled: boolean; bedtime: string };
};

export const DEFAULT_CARE_REMINDER_SETTINGS: CareReminderSettings = {
  wellness: { enabled: false, intervalMinutes: 40 },
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
  kind: Extract<CareReminderKind, "meal" | "sleep">;
  key: string;
};

export type DueCareReminder =
  | {
      kind: Extract<CareReminderKind, "meal" | "sleep">;
      deliveredKey: string;
      source: "timed";
    }
  | {
      kind: Extract<CareReminderKind, "wellness">;
      source: "random";
    };

export type CareReminderSchedule = {
  now: number;
  deliveredKeys: string[];
  nextWellnessTime: number;
  timedSnoozedUntil?: number;
  settings?: CareReminderSettings;
};

type LegacyWellnessSetting = {
  enabled?: unknown;
  intervalMinutes?: unknown;
};

type CareReminderSettingsSource = {
  wellness?: LegacyWellnessSetting;
  eyeCare?: LegacyWellnessSetting;
  water?: LegacyWellnessSetting;
  meal?: Partial<CareReminderSettings["meal"]>;
  sleep?: Partial<CareReminderSettings["sleep"]>;
};

function validTime(value: unknown, fallback: string): string {
  return typeof value === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(value) ? value : fallback;
}

function validInterval(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 15 && value <= 240
    ? Math.round(value)
    : fallback;
}

function legacyWellnessInterval(
  eyeCare: LegacyWellnessSetting | undefined,
  water: LegacyWellnessSetting | undefined,
  fallback: number,
): number {
  const eyeCareInterval = validInterval(eyeCare?.intervalMinutes, Number.NaN);
  const waterInterval = validInterval(water?.intervalMinutes, Number.NaN);
  const enabledIntervals = [
    eyeCare?.enabled === true ? eyeCareInterval : Number.NaN,
    water?.enabled === true ? waterInterval : Number.NaN,
  ].filter(Number.isFinite);

  // When both legacy switches were enabled with different values, retain the
  // quieter (longer) valid interval rather than increasing reminder frequency.
  if (enabledIntervals.length > 0) return Math.max(...enabledIntervals);
  if (Number.isFinite(eyeCareInterval)) return eyeCareInterval;
  if (Number.isFinite(waterInterval)) return waterInterval;
  return fallback;
}

export function normalizeCareReminderSettings(value: unknown): CareReminderSettings {
  const defaults = DEFAULT_CARE_REMINDER_SETTINGS;
  const source = value && typeof value === "object"
    ? value as CareReminderSettingsSource
    : undefined;
  const hasWellnessSetting = source?.wellness && typeof source.wellness === "object";
  const wellnessEnabled = hasWellnessSetting
    ? source.wellness?.enabled === true
    : source?.eyeCare?.enabled === true || source?.water?.enabled === true;
  const wellnessInterval = hasWellnessSetting
    ? validInterval(source.wellness?.intervalMinutes, defaults.wellness.intervalMinutes)
    : legacyWellnessInterval(source?.eyeCare, source?.water, defaults.wellness.intervalMinutes);
  return {
    wellness: {
      enabled: wellnessEnabled,
      intervalMinutes: wellnessInterval,
    },
    meal: {
      enabled: typeof source?.meal?.enabled === "boolean" ? source.meal.enabled : defaults.meal.enabled,
      breakfastTime: validTime(source?.meal?.breakfastTime, defaults.meal.breakfastTime),
      lunchTime: validTime(source?.meal?.lunchTime, defaults.meal.lunchTime),
      dinnerTime: validTime(source?.meal?.dinnerTime, defaults.meal.dinnerTime),
    },
    sleep: {
      enabled: typeof source?.sleep?.enabled === "boolean" ? source.sleep.enabled : defaults.sleep.enabled,
      bedtime: validTime(source?.sleep?.bedtime, defaults.sleep.bedtime),
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
  nextWellnessTime,
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

  if (now >= nextWellnessTime) {
    return {
      kind: "wellness",
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
