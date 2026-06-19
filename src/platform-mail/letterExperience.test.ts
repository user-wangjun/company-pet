import { describe, expect, test } from "vitest";
import {
  LETTER_PHASE_DELAYS_MS,
  getInitialLetterPhase,
  getLetterPhaseDelay,
  getNextAutomaticLetterPhase,
  isLetterBusy,
  type LetterPhase,
} from "./letterExperience";

describe("letter experience phases", () => {
  test("starts first use sealed and mailbox reading already open", () => {
    expect(getInitialLetterPhase("first-use")).toBe("sealed");
    expect(getInitialLetterPhase("mailbox")).toBe("open");
  });

  test("opens and stores in the approved order", () => {
    const openingOrder: LetterPhase[] = ["opening", "open"];
    const closingOrder: LetterPhase[] = [
      "folding",
      "inserting",
      "sealing",
      "flying",
      "stored",
    ];

    expect(getNextAutomaticLetterPhase("opening")).toBe(openingOrder[1]);
    expect(getNextAutomaticLetterPhase("folding")).toBe(closingOrder[1]);
    expect(getNextAutomaticLetterPhase("inserting")).toBe(closingOrder[2]);
    expect(getNextAutomaticLetterPhase("sealing")).toBe(closingOrder[3]);
    expect(getNextAutomaticLetterPhase("flying")).toBe(closingOrder[4]);
    expect(getNextAutomaticLetterPhase("sealed")).toBeNull();
    expect(getNextAutomaticLetterPhase("open")).toBeNull();
  });

  test("uses explicit normal and reduced-motion durations", () => {
    expect(LETTER_PHASE_DELAYS_MS).toEqual({
      opening: 1100,
      folding: 560,
      inserting: 520,
      sealing: 420,
      flying: 760,
    });
    expect(getLetterPhaseDelay("folding", false)).toBe(560);
    expect(getLetterPhaseDelay("folding", true)).toBe(30);
  });

  test("only settled states accept another user action", () => {
    expect(isLetterBusy("sealed")).toBe(false);
    expect(isLetterBusy("open")).toBe(false);
    expect(isLetterBusy("opening")).toBe(true);
    expect(isLetterBusy("folding")).toBe(true);
    expect(isLetterBusy("stored")).toBe(true);
  });
});
