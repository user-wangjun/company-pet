import { resolvePetAssetUrl, type PetManifest } from "./petAssets";

export type CompanionChatCue = {
  text: string;
  sound?: string;
  weight?: number;
};

export type CompanionChatConfig = {
  openers: CompanionChatCue[];
  localReplies: string[];
};

export type CompanionChatPackage =
  | { status: "not-configured"; petId: string }
  | { status: "loaded"; petId: string; config: CompanionChatConfig }
  | { status: "failed"; petId: string };

type CompanionChatResponse = {
  ok: boolean;
  status: number;
  json: () => Promise<unknown>;
};

export type CompanionChatFetcher = (
  url: string,
) => Promise<CompanionChatResponse>;

export const NEUTRAL_COMPANION_CHAT: CompanionChatConfig = {
  openers: [{ text: "嗯？", weight: 1 }],
  localReplies: ["嗯，我听着。", "慢慢说，我陪你。"],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown, field: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(`Invalid ${field}`);
  }
  return value.trim();
}

function parseCue(value: unknown): CompanionChatCue {
  const source = isRecord(value) ? value : { text: value };
  const cueText = text(source.text, "opener text");
  if (cueText.length > 8 || /[，。！？!?]/.test(cueText.slice(0, -1))) {
    throw new Error("Companion opener must be a short cue");
  }

  return {
    text: cueText,
    sound: source.sound === undefined ? undefined : text(source.sound, "opener sound"),
    weight:
      typeof source.weight === "number" && source.weight > 0
        ? source.weight
        : 1,
  };
}

function parseConfig(value: unknown): CompanionChatConfig {
  if (!isRecord(value)) throw new Error("Companion chat config must be an object");
  if (!Array.isArray(value.openers) || value.openers.length === 0) {
    throw new Error("Missing companion openers");
  }
  if (!Array.isArray(value.localReplies) || value.localReplies.length === 0) {
    throw new Error("Missing companion replies");
  }

  return {
    openers: value.openers.map(parseCue),
    localReplies: value.localReplies.map((reply) => text(reply, "reply")),
  };
}

export async function loadPetCompanionChatPackage(
  manifest: PetManifest,
  fetchConfig: CompanionChatFetcher = (url) => fetch(url),
  warn: (message: string, error?: unknown) => void = console.warn,
): Promise<CompanionChatPackage> {
  if (!manifest.companionChatPath) {
    return { status: "not-configured", petId: manifest.id };
  }

  const url = resolvePetAssetUrl(manifest.id, manifest.companionChatPath);
  try {
    const response = await fetchConfig(url);
    if (!response.ok) throw new Error(`Request failed: ${response.status}`);
    return {
      status: "loaded",
      petId: manifest.id,
      config: parseConfig(await response.json()),
    };
  } catch (error) {
    warn(`[pet-companion-chat] Failed to load ${url}`, error);
    return { status: "failed", petId: manifest.id };
  }
}

export function resolveCompanionChatPackage(
  companionPackage: CompanionChatPackage,
): CompanionChatConfig {
  return companionPackage.status === "loaded"
    ? companionPackage.config
    : NEUTRAL_COMPANION_CHAT;
}

export function chooseCompanionChatCue(
  cues: CompanionChatCue[],
  random: () => number = Math.random,
): CompanionChatCue {
  const available = cues.length > 0 ? cues : NEUTRAL_COMPANION_CHAT.openers;
  const total = available.reduce((sum, cue) => sum + (cue.weight ?? 1), 0);
  let cursor = random() * total;

  for (const cue of available) {
    cursor -= cue.weight ?? 1;
    if (cursor <= 0) return cue;
  }

  return available[available.length - 1];
}
