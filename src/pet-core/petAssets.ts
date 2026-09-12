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

export type PetKind = "pet" | "human";

type PetManifestCommon = {
  id: string;
  displayName: string;
  description: string;
  kind?: PetKind;
  previewPath?: string;
  dialoguesPath?: string;
  companionChatPath?: string;
  soulPath?: string;
  taskFeedbackPath?: string;
  threeViewPreviewPath?: string;
  roomActorPath?: string;
  interactions: PetManifestInteractions;
  sounds?: PetManifestSounds;
};

export type Rig2dPetSettings = {
  meshPath: string;
  modelPath: string;
  actionsPath: string;
  displayHeight: number;
};

export type PetManifest = PetManifestCommon & (
  | { spritesheetPath: string; rig2d?: undefined; animations: Record<string, PetAnimationSpec> }
  | { rig2d: Rig2dPetSettings; previewPath: string; spritesheetPath?: never; animations?: never; actions: Record<string, {loop: boolean}> }
);
export type PetCatalogItem = PetManifest & {
  kind: PetKind;
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
    /[\u0000-\u001f\u007f]/.test(normalized) ||
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

export function getPetRoomActorUrl(manifest: PetManifest): string | null {
  if (manifest.roomActorPath === undefined) return null;
  if (!/^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(manifest.id)) {
    throw new Error("Invalid room actor pet id");
  }
  if (!isSafePetRelativePath(manifest.roomActorPath)) {
    throw new Error("Invalid room actor path");
  }
  return resolvePetAssetUrl(manifest.id, manifest.roomActorPath);
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
      kind: manifest.kind ?? "pet",
      manifestUrl: getPetManifestUrl(manifest.id),
      previewUrl: resolvePetAssetUrl(
        manifest.id,
        manifest.rig2d ? manifest.previewPath : manifest.previewPath ?? manifest.spritesheetPath,
      ),
      previewKind: manifest.previewPath ? "image" : "spritesheet",
      isActive: manifest.id === activePetId,
    }));
}
