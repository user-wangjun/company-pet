export type LetterOpenMode = "first-use" | "mailbox";

export type LetterPhase =
  | "sealed"
  | "opening"
  | "open"
  | "folding"
  | "inserting"
  | "sealing"
  | "flying"
  | "stored";

export const LETTER_PHASE_DELAYS_MS = {
  opening: 1100,
  folding: 560,
  inserting: 520,
  sealing: 420,
  flying: 760,
} as const;

type AutomaticLetterPhase = keyof typeof LETTER_PHASE_DELAYS_MS;

export function getInitialLetterPhase(mode: LetterOpenMode): LetterPhase {
  return mode === "first-use" ? "sealed" : "open";
}

export function getNextAutomaticLetterPhase(
  phase: LetterPhase,
): LetterPhase | null {
  if (phase === "opening") return "open";
  if (phase === "folding") return "inserting";
  if (phase === "inserting") return "sealing";
  if (phase === "sealing") return "flying";
  if (phase === "flying") return "stored";
  return null;
}

export function getLetterPhaseDelay(
  phase: LetterPhase,
  reduceMotion: boolean,
): number {
  if (!(phase in LETTER_PHASE_DELAYS_MS)) return 0;

  return reduceMotion
    ? 30
    : LETTER_PHASE_DELAYS_MS[phase as AutomaticLetterPhase];
}

export function isLetterBusy(phase: LetterPhase): boolean {
  return phase !== "sealed" && phase !== "open";
}
