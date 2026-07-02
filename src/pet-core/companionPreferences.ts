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

function sensitive(text: string): boolean {
  return /身份证|银行卡|密码|住址|地址|账号|检查报告|诊断|病史|吃药|用药/.test(text);
}

export function extractCompanionPreference(
  text: string,
): CompanionPreferenceExtraction | null {
  const input = text.trim();
  if (!input || sensitive(input)) return null;

  const nickname = input.match(/(?:以后|之后)?叫我([^，。！？!\s]{1,12})/)?.[1];
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
  return /忘掉这个|别记这个|不要记这个|删掉刚才/.test(text.trim());
}

export function parseCompanionPreferences(value: string | null): CompanionPreferencesState {
  if (!value) return EMPTY_COMPANION_PREFERENCES;

  try {
    const parsed = JSON.parse(value) as Partial<CompanionPreferencesState>;
    if (!Array.isArray(parsed.preferences)) return EMPTY_COMPANION_PREFERENCES;

    return {
      preferences: parsed.preferences.filter(
        (item): item is CompanionPreference =>
          typeof item === "object" &&
          item !== null &&
          typeof (item as CompanionPreference).id === "string" &&
          typeof (item as CompanionPreference).value === "string",
      ),
      recentPreferenceId:
        typeof parsed.recentPreferenceId === "string"
          ? parsed.recentPreferenceId
          : null,
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
