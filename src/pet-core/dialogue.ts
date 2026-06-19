import { resolvePetAssetUrl, type PetManifest } from "./petAssets";

export const PET_DIALOGUE_EVENTS = [
  "idle",
  "singleClick",
  "doubleClick",
  "water",
  "eyeCare",
  "meal",
  "sleep",
] as const;

export type PetDialogueEvent = (typeof PET_DIALOGUE_EVENTS)[number];
export type PetDialogues = Partial<Record<PetDialogueEvent, string>>;

export type PetDialoguePackage =
  | { status: "not-configured"; petId: string }
  | { status: "loaded"; petId: string; dialogues: PetDialogues }
  | { status: "failed"; petId: string };

type DialogueResponse = {
  ok: boolean;
  status: number;
  json: () => Promise<unknown>;
};

export type DialogueFetcher = (url: string) => Promise<DialogueResponse>;
export type DialogueWarning = (message: string, error?: unknown) => void;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parsePetDialogues(value: unknown): PetDialogues {
  if (!isRecord(value)) {
    throw new Error("Dialogue package must be a JSON object");
  }

  return Object.fromEntries(
    PET_DIALOGUE_EVENTS.flatMap((event) => {
      const text = value[event];
      return typeof text === "string" ? [[event, text]] : [];
    }),
  ) as PetDialogues;
}

export async function loadPetDialoguePackage(
  manifest: PetManifest,
  fetchDialogue: DialogueFetcher = (url) => fetch(url),
  warn: DialogueWarning = console.warn,
): Promise<PetDialoguePackage> {
  if (!manifest.dialoguesPath) {
    return { status: "not-configured", petId: manifest.id };
  }

  const url = resolvePetAssetUrl(manifest.id, manifest.dialoguesPath);

  try {
    const response = await fetchDialogue(url);
    if (!response.ok) {
      throw new Error(`Dialogue request failed: ${response.status}`);
    }

    return {
      status: "loaded",
      petId: manifest.id,
      dialogues: parsePetDialogues(await response.json()),
    };
  } catch (error) {
    warn(`[pet-dialogue] Failed to load ${url}`, error);
    return { status: "failed", petId: manifest.id };
  }
}

export function resolvePetDialogue(
  dialoguePackage: PetDialoguePackage,
  event: PetDialogueEvent,
  fallbackText: string | null,
  warn: DialogueWarning = console.warn,
): string | null {
  if (dialoguePackage.status === "not-configured") {
    return fallbackText;
  }

  if (dialoguePackage.status === "failed") {
    return null;
  }

  const text = dialoguePackage.dialogues[event]?.trim();
  if (!text) {
    warn(
      `[pet-dialogue] Missing "${event}" dialogue for ${dialoguePackage.petId}`,
    );
    return null;
  }

  return text;
}

export function getTimedPetDialogueEvent(hour: number): PetDialogueEvent {
  if (
    (hour >= 7 && hour < 9) ||
    (hour >= 11 && hour < 13) ||
    (hour >= 18 && hour < 20)
  ) {
    return "meal";
  }

  if (hour >= 23 || hour < 6) {
    return "sleep";
  }

  return "idle";
}
