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
  iconHugSpritesheetPath?: string;
  actionsPath?: string;
  rigPath?: string;
  actionBoardPath?: string;
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

export function getPetIconHugSpritesheetPath(manifest: PetManifest): string {
  return manifest.iconHugSpritesheetPath ?? manifest.spritesheetPath;
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
