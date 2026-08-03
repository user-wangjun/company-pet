import {
  isSafePetRelativePath,
  resolvePetAssetUrl,
  type PetManifest,
} from "./petAssets";

export const DEFAULT_PET_SOUL_PATH = "SOUL.md";
export const MAX_PET_SOUL_CHARACTERS = 4_000;
export const NEUTRAL_PET_SOUL =
  "当前宠物没有额外的人格设定。保持温和、简短、尊重隐私的陪伴，不声称拥有未提供的能力。";

export type PetSoulFailureReason =
  | "invalid-path"
  | "missing"
  | "read-failed"
  | "empty"
  | "too-long";

export type PetSoulPackage =
  | {
      status: "not-configured";
      petId: string;
    }
  | {
      status: "loaded";
      petId: string;
      path: string;
      content: string;
    }
  | {
      status: "failed";
      petId: string;
      path: string;
      reason: PetSoulFailureReason;
    };

export type PetSoulResponse = {
  ok: boolean;
  status: number;
  text: () => Promise<string>;
};

export type PetSoulFetcher = (url: string) => Promise<PetSoulResponse>;
export type PetSoulWarning = (message: string, error?: unknown) => void;

function normalizeSoulContent(value: string): string {
  return value.replace(/\r\n?/g, "\n").trim();
}

function createFailure(
  manifest: PetManifest,
  path: string,
  reason: PetSoulFailureReason,
): PetSoulPackage {
  return {
    status: "failed",
    petId: manifest.id,
    path,
    reason,
  };
}

export async function loadPetSoulPackage(
  manifest: PetManifest,
  fetchSoul: PetSoulFetcher = (url) => fetch(url),
  warn: PetSoulWarning = console.warn,
): Promise<PetSoulPackage> {
  if (manifest.soulPath === undefined) {
    return { status: "not-configured", petId: manifest.id };
  }

  const soulPath = manifest.soulPath;
  if (typeof soulPath !== "string" || !isSafePetRelativePath(soulPath)) {
    const error = new Error("Soul path must stay inside the pet package");
    warn(`[pet-soul] Rejected unsafe path for ${manifest.id}: ${soulPath}`, error);
    return createFailure(manifest, soulPath, "invalid-path");
  }

  const url = resolvePetAssetUrl(manifest.id, soulPath);
  try {
    const response = await fetchSoul(url);
    if (!response.ok) {
      const reason: PetSoulFailureReason =
        response.status === 404 ? "missing" : "read-failed";
      throw Object.assign(new Error(`Soul request failed: ${response.status}`), {
        reason,
      });
    }

    const content = normalizeSoulContent(await response.text());
    if (!content) {
      const error = new Error("Soul file is empty");
      warn(`[pet-soul] Empty Soul for ${manifest.id}: ${url}`, error);
      return createFailure(manifest, soulPath, "empty");
    }

    if (Array.from(content).length > MAX_PET_SOUL_CHARACTERS) {
      const error = new Error(
        `Soul exceeds ${MAX_PET_SOUL_CHARACTERS} characters`,
      );
      warn(`[pet-soul] Soul is too long for ${manifest.id}: ${url}`, error);
      return createFailure(manifest, soulPath, "too-long");
    }

    return {
      status: "loaded",
      petId: manifest.id,
      path: soulPath,
      content,
    };
  } catch (error) {
    const reason =
      typeof error === "object" &&
      error !== null &&
      "reason" in error &&
      (error.reason === "missing" || error.reason === "read-failed")
        ? error.reason
        : "read-failed";
    warn(`[pet-soul] Failed to load ${url}`, error);
    return createFailure(manifest, soulPath, reason);
  }
}

export function resolvePetSoulPackage(
  soulPackage: PetSoulPackage | undefined,
): string {
  return soulPackage?.status === "loaded"
    ? soulPackage.content
    : NEUTRAL_PET_SOUL;
}
