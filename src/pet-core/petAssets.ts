import type {
  PetAnimationSpec,
  PetManifestInteractions,
} from "./petInteractionManifest";

export const DEFAULT_PET_ID = "xiaoju-cat";

const PETS_BASE_PATH = "/pets";
const PET_INDEX_FILE = "index.json";

export type PetSoundCue = {
  path: string;
  volume?: number;
  maxDurationMs?: number;
};

export type PetManifestSounds = Record<string, PetSoundCue[]>;

export type PetManifest = {
  id: string;
  displayName: string;
  description: string;
  spritesheetPath: string;
  previewPath?: string;
  dialoguesPath?: string;
  animations: Record<string, PetAnimationSpec>;
  interactions: PetManifestInteractions;
  sounds?: PetManifestSounds;
};

export type PetCatalogItem = PetManifest & {
  manifestUrl: string;
  previewUrl: string;
  previewKind: "image" | "spritesheet";
  isActive: boolean;
};

function trimSlashes(value: string): string {
  return value.replace(/^\/+|\/+$/g, "");
}

function isSafeDecodedPetRelativePath(value: string): boolean {
  const normalized = value.replace(/\\/g, "/");
  if (
    normalized.trim().length === 0 ||
    normalized.startsWith("/") ||
    normalized.includes("?") ||
    normalized.includes("#") ||
    normalized.includes(":")
  ) {
    return false;
  }

  return normalized
    .split("/")
    .every((segment) => segment !== "." && segment !== "..");
}

export function isSafePetRelativePath(value: string): boolean {
  if (typeof value !== "string" || value.trim().length === 0) return false;

  let decoded = value;
  for (let pass = 0; pass < 10; pass += 1) {
    if (!isSafeDecodedPetRelativePath(decoded)) return false;

    let next: string;
    try {
      next = decodeURIComponent(decoded);
    } catch {
      return false;
    }

    if (next === decoded) return true;
    decoded = next;
  }

  return false;
}

export function getPetBasePath(petId: string): string {
  return `${PETS_BASE_PATH}/${trimSlashes(petId)}`;
}

export function getPetIndexUrl(): string {
  return `${PETS_BASE_PATH}/${PET_INDEX_FILE}`;
}

export function getPetManifestUrl(petId: string): string {
  return `${getPetBasePath(petId)}/pet.json`;
}

export function resolvePetAssetUrl(petId: string, filePath: string): string {
  const normalizedFilePath = trimSlashes(filePath.replace(/\\/g, "/"));
  return `${getPetBasePath(petId)}/${normalizedFilePath}`;
}

export function chooseInitialPetId(
  availablePetIds: string[],
  savedPetId: string | null,
): string {
  if (savedPetId && availablePetIds.includes(savedPetId)) {
    return savedPetId;
  }

  if (availablePetIds.includes(DEFAULT_PET_ID)) {
    return DEFAULT_PET_ID;
  }

  return availablePetIds[0] ?? DEFAULT_PET_ID;
}

export function createPetCatalog(
  petIds: string[],
  manifestsById: Record<string, PetManifest>,
  activePetId: string,
): PetCatalogItem[] {
  return petIds
    .map((petId) => manifestsById[petId])
    .filter((manifest): manifest is PetManifest => Boolean(manifest))
    .map((manifest) => ({
      ...manifest,
      manifestUrl: getPetManifestUrl(manifest.id),
      previewUrl: resolvePetAssetUrl(
        manifest.id,
        manifest.previewPath ?? manifest.spritesheetPath,
      ),
      previewKind: manifest.previewPath ? "image" : "spritesheet",
      isActive: manifest.id === activePetId,
    }));
}
