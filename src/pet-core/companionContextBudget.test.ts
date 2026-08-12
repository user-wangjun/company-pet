import { describe, expect, test } from "vitest";
import {
  applyCompanionContextBudget,
  CompanionContextBudgetError,
  countCompanionCodePoints,
  estimateCompanionTokens,
  type CompanionContextBudgetInput,
} from "./companionContextBudget";

type TestMessage = { id: string; text: string };

function budgetInput(
  overrides: Partial<CompanionContextBudgetInput<TestMessage>> = {},
): CompanionContextBudgetInput<TestMessage> {
  return {
    requiredSystemInstruction: "SAFETY_RULES",
    optionalSystemInstruction: "OPTIONAL_STYLE",
    userInput: "CURRENT_USER_INPUT",
    soul: "SOUL_CONTENT",
    preferences: ["PREFERENCE_A", "PREFERENCE_B"],
    history: [
      { id: "h0", text: "HISTORY_0" },
      { id: "h1", text: "HISTORY_1" },
      { id: "h2", text: "HISTORY_2" },
      { id: "h3", text: "HISTORY_3" },
    ],
    memories: ["MEMORY_0", "MEMORY_1", "MEMORY_2"],
    render: (selection) => ({
      systemInstruction: [
        selection.requiredSystemInstruction,
        selection.optionalSystemInstruction,
        `SOUL=${selection.soul}`,
        `PREF=${selection.preferences.join(",")}`,
        `MEM=${selection.memories.join(",")}`,
      ].join("|"),
      history: selection.history,
    }),
    ...overrides,
  };
}

describe("global Companion Context Budget", () => {
  test("counts CJK and emoji by Unicode code point, not UTF-16 units", () => {
    const value = "A你🙂";
    expect(countCompanionCodePoints(value)).toBe(3);
    expect(estimateCompanionTokens("A")).toBe(1);
    expect(estimateCompanionTokens("你")).toBe(3);
    expect(estimateCompanionTokens("🙂")).toBe(4);
    expect(estimateCompanionTokens(value)).toBe(8);
    expect(countCompanionCodePoints("e\u0301")).toBe(2);
    expect(estimateCompanionTokens("e\u0301")).toBe(3);
    expect(estimateCompanionTokens("A".repeat(64))).toBe(64);
    expect(estimateCompanionTokens("A你🙂e\u0301")).toBe(11);
    expect(estimateCompanionTokens(value)).toBe(estimateCompanionTokens(value));
  });

  test("applies character and conservative token dimensions independently", () => {
    const result = applyCompanionContextBudget(
      budgetInput({
        optionalSystemInstruction: "",
        soul: "你🙂".repeat(20),
        preferences: [],
        history: [],
        memories: [],
      }),
      { maxCharacters: 1_000, maxEstimatedTokens: 64 },
    );

    expect(result.metadata.actualCharacters).toBeLessThanOrEqual(1_000);
    expect(result.metadata.estimatedTokens).toBeLessThanOrEqual(64);
    expect(result.metadata.truncationReasons).toContain("token-budget");
    expect(result.metadata.truncationReasons).toContain("soul-budget");
  });

  test("keeps the final rendered context within both global limits", () => {
    const result = applyCompanionContextBudget(
      budgetInput({
        soul: "灵魂🙂".repeat(20),
        history: Array.from({ length: 10 }, (_, index) => ({
          id: `h${index}`,
          text: `历史消息🙂${index}`,
        })),
        memories: Array.from({ length: 10 }, (_, index) => `记忆${index}`),
      }),
      { maxCharacters: 180, maxEstimatedTokens: 180 },
    );

    expect(result.metadata.actualCharacters).toBeLessThanOrEqual(180);
    expect(result.metadata.estimatedTokens).toBeLessThanOrEqual(180);
    expect(result.metadata.wasTruncated).toBe(true);
  });

  test("is deterministic for the same Unicode input", () => {
    const input = budgetInput({
      soul: "小橘🙂".repeat(10),
      history: Array.from({ length: 8 }, (_, index) => ({
        id: `h${index}`,
        text: `消息 ${index}`,
      })),
    });
    expect(applyCompanionContextBudget(input, {
      maxCharacters: 160,
      maxEstimatedTokens: 160,
    })).toEqual(applyCompanionContextBudget(input, {
      maxCharacters: 160,
      maxEstimatedTokens: 160,
    }));
  });

  test("never drops the protected safety block or current user input", () => {
    const result = applyCompanionContextBudget(
      budgetInput({
        requiredSystemInstruction: "PLATFORM_SAFETY_NEVER_DROP",
        userInput: "CURRENT_INPUT_NEVER_DROP",
        soul: "SOUL_LOW_PRIORITY".repeat(20),
        memories: Array.from({ length: 8 }, (_, index) => `MEMORY_LOW_${index}`),
      }),
      { maxCharacters: 120, maxEstimatedTokens: 120 },
    );

    expect(result.systemInstruction).toContain("PLATFORM_SAFETY_NEVER_DROP");
    expect(result.userInput).toBe("CURRENT_INPUT_NEVER_DROP");
    expect(result.metadata.retainedCounts.userInput).toBe(1);
  });

  test("fails closed when protected safety plus current input exceed the hard budget", () => {
    const input = budgetInput({
      requiredSystemInstruction: "SAFETY_已经超过硬预算".repeat(20),
      userInput: "CURRENT_INPUT_仍然必须保留".repeat(20),
    });

    expect(() => applyCompanionContextBudget(input, {
      maxCharacters: 40,
      maxEstimatedTokens: 40,
    })).toThrow(CompanionContextBudgetError);

    try {
      applyCompanionContextBudget(input, {
        maxCharacters: 40,
        maxEstimatedTokens: 40,
      });
    } catch (error) {
      expect(error).toBeInstanceOf(CompanionContextBudgetError);
      const metadata = (error as CompanionContextBudgetError).metadata;
      expect(metadata.truncationReasons).toContain("required-content-over-budget");
      expect(JSON.stringify(metadata)).not.toContain("SAFETY_已经超过硬预算");
      expect(JSON.stringify(metadata)).not.toContain("CURRENT_INPUT_仍然必须保留");
    }
  });

  test("drops Memory before older history and keeps retained history ordered", () => {
    const result = applyCompanionContextBudget(
      budgetInput({
        optionalSystemInstruction: "",
        soul: "S",
        preferences: [],
        memories: ["MEMORY_FIRST", "MEMORY_LAST"],
        history: [
          { id: "h0", text: "HISTORY_OLD" },
          { id: "h1", text: "HISTORY_MIDDLE" },
          { id: "h2", text: "HISTORY_NEW" },
        ],
      }),
      { maxCharacters: 60, maxEstimatedTokens: 60 },
    );

    expect(result.metadata.truncationReasons).toContain("memory-budget");
    expect(result.metadata.truncationReasons).toContain("history-budget");
    expect(result.memories).toEqual([]);
    expect(result.history.map((item) => item.id)).toEqual(["h2"]);
    expect(result.history.map((item) => item.id)).toEqual(
      [...result.history]
        .map((item) => item.id)
        .sort((left, right) => left.localeCompare(right)),
    );
  });

  test("clips Soul only at a deterministic code-point boundary", () => {
    const result = applyCompanionContextBudget(
      budgetInput({
        optionalSystemInstruction: "",
        preferences: [],
        history: [],
        memories: [],
        soul: "🙂你".repeat(40),
      }),
      { maxCharacters: 88, maxEstimatedTokens: 88 },
    );

    expect(result.metadata.truncationReasons).toContain("soul-budget");
    expect(result.soul.endsWith("…")).toBe(true);
    expect([...result.soul].join("")).toBe(result.soul);
    expect(result.metadata.actualCharacters).toBeLessThanOrEqual(88);
  });

  test("metadata contains counts and enums only, never discarded text", () => {
    const result = applyCompanionContextBudget(
      budgetInput({
        memories: ["DISCARDED_MEMORY_SECRET_SENTINEL"],
        history: [{ id: "h0", text: "DISCARDED_HISTORY_SENTINEL" }],
      }),
      { maxCharacters: 80, maxEstimatedTokens: 80 },
    );

    const metadata = JSON.stringify(result.metadata);
    expect(metadata).not.toContain("DISCARDED_MEMORY_SECRET_SENTINEL");
    expect(metadata).not.toContain("DISCARDED_HISTORY_SENTINEL");
    expect(result.metadata.discardedCounts.memories).toBeGreaterThan(0);
    expect(result.metadata.truncationReasons.every((reason) => typeof reason === "string")).toBe(true);
    expect(Object.keys(result.metadata).sort()).toEqual([
      "actualCharacters",
      "discardedCounts",
      "estimatedTokens",
      "maxCharacters",
      "maxEstimatedTokens",
      "retainedCounts",
      "truncationReasons",
      "wasTruncated",
    ]);
  });
});
