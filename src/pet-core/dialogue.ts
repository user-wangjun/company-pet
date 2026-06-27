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

export const NEUTRAL_PET_DIALOGUES: Required<PetDialogues> = {
  idle: "我会在这里陪着你。",
  singleClick: "收到。",
  doubleClick: "一起活动一下。",
  water: "该喝杯水了，休息一下再继续。",
  eyeCare: "看看远处，让眼睛休息一下。",
  meal: "到饭点了，先好好吃饭。",
  sleep: "时间不早了，今天先休息。",
};

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
    return fallbackText ?? NEUTRAL_PET_DIALOGUES[event];
  }

  if (dialoguePackage.status === "failed") {
    return NEUTRAL_PET_DIALOGUES[event];
  }

  const text = dialoguePackage.dialogues[event]?.trim();
  if (!text) {
    warn(
      `[pet-dialogue] Missing "${event}" dialogue for ${dialoguePackage.petId}`,
    );
    return fallbackText ?? NEUTRAL_PET_DIALOGUES[event];
  }

  return text;
}

export function getTimedPetDialogueEvent(hour: number): PetDialogueEvent {
  if (
    (hour >= 8 && hour < 9) ||
    (hour >= 11 && hour < 12) ||
    (hour >= 18 && hour < 19)
  ) {
    return "meal";
  }

  if (hour >= 23 || hour < 6) {
    return "sleep";
  }

  return "idle";
}

export function getAmbientPetDialogueEvent(
  configuredIdleEvent: PetDialogueEvent | undefined,
  hour: number,
): PetDialogueEvent {
  const timedEvent = getTimedPetDialogueEvent(hour);

  return timedEvent === "idle" ? configuredIdleEvent ?? "idle" : timedEvent;
}

export function getAmbientPetDialogueRefresh(
  currentText: string | null,
  previousAmbientText: string | null,
  nextAmbientText: string | null,
): string | null {
  if (previousAmbientText === null) return null;
  if (currentText !== previousAmbientText) return null;
  if (nextAmbientText === previousAmbientText) return null;

  return nextAmbientText;
}
