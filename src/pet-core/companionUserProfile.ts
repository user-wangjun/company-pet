import {
  containsSensitiveCompanionProfileValue,
  containsSensitiveCompanionText,
} from "./companionPrivacy";

export const COMPANION_USER_PROFILE_STORAGE_KEY =
  "yuxin-companion-user-profile-v1";

export const COMPANION_USER_GENDERS = [
  "unspecified",
  "female",
  "male",
  "non-binary",
  "prefer-not-to-say",
] as const;

export type CompanionUserGender = (typeof COMPANION_USER_GENDERS)[number];

export type CompanionUserProfile = {
  nickname: string;
  gender: CompanionUserGender;
  email: string;
  phone: string;
};

export type CompanionUserProfileActionResult = {
  ok: boolean;
  message: string;
};

/**
 * The only profile-shaped value that may be projected to a remote context.
 * This is deliberately a new, reduced value object rather than the complete
 * local CompanionUserProfile.
 */
export type CompanionUserProfileRemoteProjection = {
  id: "global.nickname";
  scope: "global";
  category: "userProfile";
  key: "nickname";
  value: string;
  source: "explicit";
};

type StorageLike = Pick<Storage, "getItem" | "setItem">;

export const EMPTY_COMPANION_USER_PROFILE: CompanionUserProfile = {
  nickname: "",
  gender: "unspecified",
  email: "",
  phone: "",
};

/**
 * Project only the user-authorized nickname. Gender, email, and phone are
 * intentionally read only to normalize the local profile and are never
 * copied into the returned object, logs, metadata, or error text.
 */
export function projectCompanionUserProfileForRemote(
  input: CompanionUserProfile | Partial<CompanionUserProfile> | null | undefined,
): CompanionUserProfileRemoteProjection | null {
  const nickname = typeof input?.nickname === "string"
    ? input.nickname.trim()
    : "";
  if (!nickname || nickname.length > 32) return null;
  if (
    containsSensitiveCompanionText(nickname)
    || containsSensitiveCompanionProfileValue(nickname)
  ) {
    return null;
  }
  return {
    id: "global.nickname",
    scope: "global",
    category: "userProfile",
    key: "nickname",
    value: nickname,
    source: "explicit",
  };
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/u;
const PHONE_PATTERN = /^\+?[0-9][0-9\s().-]{5,22}$/u;

function isCompanionUserGender(value: unknown): value is CompanionUserGender {
  return typeof value === "string" && (COMPANION_USER_GENDERS as readonly string[]).includes(value);
}

function isSafeProfileText(value: string): boolean {
  return !containsSensitiveCompanionText(value);
}

function isValidPhone(value: string): boolean {
  if (!PHONE_PATTERN.test(value)) return false;
  const digits = value.replace(/\D/gu, "");
  return digits.length >= 7 && digits.length <= 20;
}

export function normalizeCompanionUserProfile(
  input: Partial<CompanionUserProfile> | null | undefined,
): CompanionUserProfile {
  return {
    nickname: typeof input?.nickname === "string" ? input.nickname.trim() : "",
    gender: isCompanionUserGender(input?.gender) ? input.gender : "unspecified",
    email: typeof input?.email === "string" ? input.email.trim() : "",
    phone: typeof input?.phone === "string" ? input.phone.trim() : "",
  };
}

export function validateCompanionUserProfile(
  input: CompanionUserProfile,
): string | null {
  const profile = normalizeCompanionUserProfile(input);
  if (profile.nickname.length > 32) return "昵称最多填写 32 个字符。";
  if (!isSafeProfileText(profile.nickname)) return "昵称中包含不适合保存的敏感内容。";

  if (profile.email.length > 254 || (profile.email && !EMAIL_PATTERN.test(profile.email))) {
    return "邮箱格式不正确。";
  }
  if (profile.email && !isSafeProfileText(profile.email)) {
    return "邮箱内容不适合保存。";
  }

  if (profile.phone && !isValidPhone(profile.phone)) {
    return "电话格式不正确。";
  }
  if (profile.phone && !isSafeProfileText(profile.phone)) {
    return "电话内容不适合保存。";
  }

  return null;
}

export function isCompanionUserProfileSafe(
  input: CompanionUserProfile,
): boolean {
  return validateCompanionUserProfile(input) === null;
}

export function parseCompanionUserProfile(
  value: string | null,
): CompanionUserProfile {
  if (!value) return EMPTY_COMPANION_USER_PROFILE;

  try {
    const parsed = JSON.parse(value) as Partial<CompanionUserProfile>;
    if (
      !parsed ||
      typeof parsed !== "object" ||
      (parsed.nickname !== undefined && typeof parsed.nickname !== "string") ||
      (parsed.email !== undefined && typeof parsed.email !== "string") ||
      (parsed.phone !== undefined && typeof parsed.phone !== "string") ||
      (parsed.gender !== undefined && !isCompanionUserGender(parsed.gender))
    ) {
      return EMPTY_COMPANION_USER_PROFILE;
    }
    const profile = normalizeCompanionUserProfile(parsed);
    return isCompanionUserProfileSafe(profile)
      ? profile
      : EMPTY_COMPANION_USER_PROFILE;
  } catch {
    return EMPTY_COMPANION_USER_PROFILE;
  }
}

export function readCompanionUserProfile(
  storage: StorageLike = window.localStorage,
  warn: (message: string) => void = console.warn,
): CompanionUserProfile {
  try {
    return parseCompanionUserProfile(
      storage.getItem(COMPANION_USER_PROFILE_STORAGE_KEY),
    );
  } catch {
    warn("[companion-user-profile] Failed to read local profile");
    return EMPTY_COMPANION_USER_PROFILE;
  }
}

export function writeCompanionUserProfile(
  input: CompanionUserProfile,
  storage: StorageLike = window.localStorage,
  warn: (message: string) => void = console.warn,
): boolean {
  const profile = normalizeCompanionUserProfile(input);
  if (!isCompanionUserProfileSafe(profile)) {
    warn("[companion-user-profile] Rejected invalid local profile");
    return false;
  }

  try {
    storage.setItem(
      COMPANION_USER_PROFILE_STORAGE_KEY,
      JSON.stringify(profile),
    );
    return true;
  } catch {
    warn("[companion-user-profile] Failed to write local profile");
    return false;
  }
}
