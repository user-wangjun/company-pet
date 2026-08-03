import { containsSensitiveCompanionText } from "./companionPrivacy";

export const COMPANION_PREFERENCES_STORAGE_KEY =
  "yuxin-companion-preferences-v1";

export type CompanionPreference = {
  id: string;
  scope: "global" | `pet:${string}`;
  category: "userProfile" | "reminderPreferences" | "petRelationship";
  key: string;
  value: string;
  source: "explicit" | "inferred";
};

export type CompanionPreferencesState = {
  preferences: CompanionPreference[];
  recentPreferenceId: string | null;
};

export type CompanionPreferenceExtraction = {
  preference: CompanionPreference;
  feedback: string;
};

type StorageLike = Pick<Storage, "getItem" | "setItem">;

export const EMPTY_COMPANION_PREFERENCES: CompanionPreferencesState = {
  preferences: [],
  recentPreferenceId: null,
};

export function isCompanionPreferenceSafe(
  preference: CompanionPreference,
): boolean {
  return [
    preference.id,
    preference.scope,
    preference.category,
    preference.key,
    preference.value,
    preference.source,
  ].every((value) => !containsSensitiveCompanionText(value));
}

export function isCompanionPreferencesStateSafe(
  state: CompanionPreferencesState,
): boolean {
  return (
    !state.recentPreferenceId ||
    !containsSensitiveCompanionText(state.recentPreferenceId)
  ) && state.preferences.every(isCompanionPreferenceSafe);
}

export function extractCompanionPreference(
  text: string,
): CompanionPreferenceExtraction | null {
  const input = text.trim();
  const genericEyeCareRequest = /眼睛|盯屏|看屏幕/u.test(input)
    && /提醒|休息|少/u.test(input);
  // A health detail may route to a generic screen-rest preference, but the
  // detail itself must never be copied into the saved key/value or feedback.
  if (!input || (containsSensitiveCompanionText(input) && !genericEyeCareRequest)) return null;

  const nickname = input.match(
    /^(?:以后|之后)\s*叫我\s*([^，。！？!\s]{1,12})[。！？!?]?$/u,
  )?.[1];
  if (nickname) {
    return {
      preference: {
        id: "global.nickname",
        scope: "global",
        category: "userProfile",
        key: "nickname",
        value: nickname,
        source: "explicit",
      },
      feedback: `好呀，我以后叫你${nickname}。`,
    };
  }

  if (/短一点|少讲|别太严肃|轻松一点/.test(input)) {
    return {
      preference: {
        id: "global.replyStyle",
        scope: "global",
        category: "userProfile",
        key: "replyStyle",
        value: "short-and-soft",
        source: "explicit",
      },
      feedback: "嗯，我记住啦，以后我尽量说短一点、轻一点。",
    };
  }

  if (/安静|别太吵|少打扰/.test(input)) {
    return {
      preference: {
        id: "global.companionStyle",
        scope: "global",
        category: "userProfile",
        key: "companionStyle",
        value: "quiet",
        source: "inferred",
      },
      feedback: "嗯，我记住啦，会安静一点陪你。",
    };
  }

  if (/眼睛|盯屏|看屏幕/.test(input) && /提醒|休息|少/.test(input)) {
    return {
      preference: {
        id: "global.eyeCare",
        scope: "global",
        category: "reminderPreferences",
        key: "eyeCare",
        value: "reduce-screen-staring",
        source: "explicit",
      },
      feedback: "我记住啦，会更注意提醒你休息眼睛。",
    };
  }

  return null;
}

export function isForgetRecentPreferenceRequest(text: string): boolean {
  if (containsSensitiveCompanionText(text)) return false;
  const normalized = text.trim().replace(/[。！？!?]+$/u, "");
  return /(?:忘掉|忘了|忘记|删掉|删除)(?:刚才|最近)?(?:这|那)?(?:个|条|项|件事)?|(?:别记|不要记)(?:这|那)?(?:个|条|项|件事)?/u.test(
    normalized,
  );
}

export function parseCompanionPreferences(value: string | null): CompanionPreferencesState {
  if (!value) return EMPTY_COMPANION_PREFERENCES;

  try {
    const parsed = JSON.parse(value) as Partial<CompanionPreferencesState>;
    if (!Array.isArray(parsed.preferences)) return EMPTY_COMPANION_PREFERENCES;

    const recentPreferenceId =
      typeof parsed.recentPreferenceId === "string" &&
      !containsSensitiveCompanionText(parsed.recentPreferenceId)
        ? parsed.recentPreferenceId
        : null;
    return {
      preferences: parsed.preferences.filter(
        (item): item is CompanionPreference =>
          typeof item === "object" &&
          item !== null &&
          typeof (item as CompanionPreference).id === "string" &&
          typeof (item as CompanionPreference).scope === "string" &&
          typeof (item as CompanionPreference).category === "string" &&
          typeof (item as CompanionPreference).key === "string" &&
          typeof (item as CompanionPreference).value === "string" &&
          typeof (item as CompanionPreference).source === "string" &&
          isCompanionPreferenceSafe(item as CompanionPreference),
      ),
      recentPreferenceId,
    };
  } catch {
    return EMPTY_COMPANION_PREFERENCES;
  }
}

export function readCompanionPreferences(
  storage: StorageLike = window.localStorage,
  warn: (message: string, error?: unknown) => void = console.warn,
): CompanionPreferencesState {
  try {
    return parseCompanionPreferences(
      storage.getItem(COMPANION_PREFERENCES_STORAGE_KEY),
    );
  } catch (error) {
    warn("[companion-preferences] Failed to read preferences", error);
    return EMPTY_COMPANION_PREFERENCES;
  }
}

export function writeCompanionPreferences(
  state: CompanionPreferencesState,
  storage: StorageLike = window.localStorage,
  warn: (message: string, error?: unknown) => void = console.warn,
): boolean {
  if (!isCompanionPreferencesStateSafe(state)) {
    warn("[companion-preferences] Rejected sensitive preference state");
    return false;
  }
  try {
    storage.setItem(COMPANION_PREFERENCES_STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch (error) {
    warn("[companion-preferences] Failed to write preferences", error);
    return false;
  }
}

export function upsertCompanionPreference(
  state: CompanionPreferencesState,
  preference: CompanionPreference,
): CompanionPreferencesState {
  if (!isCompanionPreferenceSafe(preference)) return state;
  return {
    preferences: [
      ...state.preferences.filter((item) => item.id !== preference.id),
      preference,
    ],
    recentPreferenceId: preference.id,
  };
}

export function deleteRecentPreference(
  state: CompanionPreferencesState,
): CompanionPreferencesState {
  if (!state.recentPreferenceId) return state;
  return {
    preferences: state.preferences.filter(
      (item) => item.id !== state.recentPreferenceId,
    ),
    recentPreferenceId: null,
  };
}
