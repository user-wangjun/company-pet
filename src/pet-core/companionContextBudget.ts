/**
 * Provider-neutral global context budget.
 *
 * This module deliberately knows nothing about React, Tasks, Reminders,
 * repositories, or provider wire formats. It only packs already-projected
 * text and returns non-sensitive count metadata.
 */

export const DEFAULT_COMPANION_CONTEXT_BUDGET = Object.freeze({
  maxCharacters: 12_000,
  maxEstimatedTokens: 8_000,
});

export type CompanionContextBudgetCategory =
  | "systemInstruction"
  | "userInput"
  | "soul"
  | "preferences"
  | "history"
  | "memories";

export type CompanionContextBudgetCounts = Record<
  CompanionContextBudgetCategory,
  number
>;

export type CompanionContextBudgetTruncationReason =
  | "character-budget"
  | "token-budget"
  | "memory-budget"
  | "history-budget"
  | "preference-budget"
  | "soul-budget"
  | "system-instruction-budget"
  | "required-content-over-budget";

export type CompanionContextBudgetMetadata = {
  maxCharacters: number;
  maxEstimatedTokens: number;
  actualCharacters: number;
  estimatedTokens: number;
  wasTruncated: boolean;
  retainedCounts: CompanionContextBudgetCounts;
  discardedCounts: CompanionContextBudgetCounts;
  truncationReasons: readonly CompanionContextBudgetTruncationReason[];
};

export type CompanionContextBudgetLimits = {
  maxCharacters?: number;
  maxEstimatedTokens?: number;
};

export type CompanionContextBudgetSelection<
  T extends { text: string },
> = {
  requiredSystemInstruction: string;
  optionalSystemInstruction: string;
  soul: string;
  preferences: readonly string[];
  history: readonly T[];
  memories: readonly string[];
};

export type CompanionContextBudgetRenderResult<T extends { text: string }> = {
  systemInstruction: string;
  history: readonly T[];
};

export type CompanionContextBudgetInput<T extends { text: string }> = {
  requiredSystemInstruction: string;
  optionalSystemInstruction?: string;
  userInput: string;
  soul?: string;
  preferences?: readonly string[];
  history?: readonly T[];
  memories?: readonly string[];
  /** Counts removed by an earlier privacy/scope/status projection. */
  initiallyDiscardedCounts?: Partial<CompanionContextBudgetCounts>;
  render: (
    selection: CompanionContextBudgetSelection<T>,
  ) => CompanionContextBudgetRenderResult<T>;
};

export type CompanionContextBudgetOutput<T extends { text: string }> = {
  systemInstruction: string;
  userInput: string;
  soul: string;
  preferences: readonly string[];
  history: readonly T[];
  memories: readonly string[];
  metadata: CompanionContextBudgetMetadata;
};

function emptyCounts(): CompanionContextBudgetCounts {
  return {
    systemInstruction: 0,
    userInput: 0,
    soul: 0,
    preferences: 0,
    history: 0,
    memories: 0,
  };
}

function normalizeLimit(value: number | undefined, fallback: number): number {
  if (value === undefined) return fallback;
  if (!Number.isFinite(value)) return fallback;
  return Math.max(0, Math.floor(value));
}

function normalizeLimits(
  limits: CompanionContextBudgetLimits = {},
): Required<CompanionContextBudgetLimits> {
  return {
    maxCharacters: normalizeLimit(
      limits.maxCharacters,
      DEFAULT_COMPANION_CONTEXT_BUDGET.maxCharacters,
    ),
    maxEstimatedTokens: normalizeLimit(
      limits.maxEstimatedTokens,
      DEFAULT_COMPANION_CONTEXT_BUDGET.maxEstimatedTokens,
    ),
  };
}

function addCount(
  counts: CompanionContextBudgetCounts,
  category: CompanionContextBudgetCategory,
  amount = 1,
): void {
  counts[category] += amount;
}

function cloneCounts(
  counts: Partial<CompanionContextBudgetCounts> | undefined,
): CompanionContextBudgetCounts {
  const result = emptyCounts();
  for (const category of Object.keys(result) as CompanionContextBudgetCategory[]) {
    const value = counts?.[category];
    if (typeof value === "number" && Number.isFinite(value)) {
      result[category] = Math.max(0, Math.floor(value));
    }
  }
  return result;
}

/** Counts Unicode code points instead of UTF-16 code units. */
export function countCompanionCodePoints(value: string): number {
  return Array.from(value).length;
}

/**
 * Conservative, deterministic provider-neutral proxy. UTF-8 byte count is
 * intentionally used instead of pretending that one Unicode code point is
 * one token or reproducing a provider tokenizer. It is a budgeting upper
 * bound-style proxy: exact provider token usage may be lower or different.
 */
export function estimateCompanionTokens(value: string): number {
  return new TextEncoder().encode(value).length;
}

function measureText(values: readonly string[]): {
  characters: number;
  estimatedTokens: number;
} {
  return values.reduce(
    (total, value) => ({
      characters: total.characters + countCompanionCodePoints(value),
      estimatedTokens: total.estimatedTokens + estimateCompanionTokens(value),
    }),
    { characters: 0, estimatedTokens: 0 },
  );
}

function measureSelection<T extends { text: string }>(
  input: CompanionContextBudgetInput<T>,
  selection: CompanionContextBudgetSelection<T>,
): {
  rendered: CompanionContextBudgetRenderResult<T>;
  characters: number;
  estimatedTokens: number;
} {
  const rendered = input.render(selection);
  const measured = measureText([
    rendered.systemInstruction,
    input.userInput,
    ...rendered.history.map((message) => message.text),
  ]);
  return { rendered, ...measured };
}

function isOverBudget(
  measured: { characters: number; estimatedTokens: number },
  limits: Required<CompanionContextBudgetLimits>,
): boolean {
  return measured.characters > limits.maxCharacters
    || measured.estimatedTokens > limits.maxEstimatedTokens;
}

function addBudgetReasons(
  reasons: Set<CompanionContextBudgetTruncationReason>,
  measured: { characters: number; estimatedTokens: number },
  limits: Required<CompanionContextBudgetLimits>,
): void {
  if (measured.characters > limits.maxCharacters) reasons.add("character-budget");
  if (measured.estimatedTokens > limits.maxEstimatedTokens) reasons.add("token-budget");
}

function retainedCounts<T extends { text: string }>(
  selection: CompanionContextBudgetSelection<T>,
  rendered: CompanionContextBudgetRenderResult<T>,
  userInput: string,
): CompanionContextBudgetCounts {
  return {
    systemInstruction: rendered.systemInstruction ? 1 : 0,
    userInput: userInput ? 1 : 0,
    soul: selection.soul ? 1 : 0,
    preferences: selection.preferences.length,
    history: rendered.history.length,
    memories: selection.memories.length,
  };
}

function makeMetadata<T extends { text: string }>(
  limits: Required<CompanionContextBudgetLimits>,
  selection: CompanionContextBudgetSelection<T>,
  rendered: CompanionContextBudgetRenderResult<T>,
  measured: { characters: number; estimatedTokens: number },
  discardedCounts: CompanionContextBudgetCounts,
  reasons: Set<CompanionContextBudgetTruncationReason>,
  userInput: string,
): CompanionContextBudgetMetadata {
  addBudgetReasons(reasons, measured, limits);
  return {
    maxCharacters: limits.maxCharacters,
    maxEstimatedTokens: limits.maxEstimatedTokens,
    actualCharacters: measured.characters,
    estimatedTokens: measured.estimatedTokens,
    wasTruncated: reasons.size > 0,
    retainedCounts: retainedCounts(selection, rendered, userInput),
    discardedCounts: { ...discardedCounts },
    truncationReasons: [...reasons],
  };
}

function clipCodePoints(value: string, count: number): string {
  const points = Array.from(value);
  if (count >= points.length) return value;
  if (count <= 0) return "";
  if (count === 1) return "…";
  return `${points.slice(0, count - 1).join("")}…`;
}

function trimSoulToFit<T extends { text: string }>(
  input: CompanionContextBudgetInput<T>,
  selection: CompanionContextBudgetSelection<T>,
  limits: Required<CompanionContextBudgetLimits>,
): { selection: CompanionContextBudgetSelection<T>; measured: ReturnType<typeof measureSelection<T>> } {
  const original = selection.soul;
  const length = countCompanionCodePoints(original);
  let low = 0;
  let high = length;
  let best = "";

  while (low <= high) {
    const middle = Math.floor((low + high) / 2);
    const candidate = clipCodePoints(original, middle);
    const candidateSelection = { ...selection, soul: candidate };
    const measured = measureSelection(input, candidateSelection);
    if (!isOverBudget(measured, limits)) {
      best = candidate;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }

  const nextSelection = { ...selection, soul: best };
  return { selection: nextSelection, measured: measureSelection(input, nextSelection) };
}

export class CompanionContextBudgetError extends Error {
  readonly metadata: CompanionContextBudgetMetadata;
  readonly reason = "required-content-over-budget" as const;

  constructor(metadata: CompanionContextBudgetMetadata) {
    super("Required companion context exceeds the hard budget; remote generation was blocked.");
    this.name = "CompanionContextBudgetError";
    this.metadata = metadata;
  }
}

/**
 * Packs a structured context using the fixed priority:
 * safety/system + current input > Soul > preferences > recent history >
 * confirmed Memory. Memory is removed first, then older history, then lower
 * risk preference projection; a Soul is only clipped at a code-point boundary.
 */
export function applyCompanionContextBudget<T extends { text: string }>(
  input: CompanionContextBudgetInput<T>,
  limits: CompanionContextBudgetLimits = {},
): CompanionContextBudgetOutput<T> {
  const normalizedLimits = normalizeLimits(limits);
  const discardedCounts = cloneCounts(input.initiallyDiscardedCounts);
  const reasons = new Set<CompanionContextBudgetTruncationReason>();

  let selection: CompanionContextBudgetSelection<T> = {
    requiredSystemInstruction: input.requiredSystemInstruction,
    optionalSystemInstruction: input.optionalSystemInstruction ?? "",
    soul: input.soul ?? "",
    preferences: [...(input.preferences ?? [])],
    history: [...(input.history ?? [])],
    memories: [...(input.memories ?? [])],
  };

  let measured = measureSelection(input, selection);
  const requiredSelection: CompanionContextBudgetSelection<T> = {
    ...selection,
    optionalSystemInstruction: "",
    soul: "",
    preferences: [],
    history: [],
    memories: [],
  };
  const requiredMeasured = measureSelection(input, requiredSelection);
  if (isOverBudget(requiredMeasured, normalizedLimits)) {
    reasons.add("required-content-over-budget");
    const metadata = makeMetadata(
      normalizedLimits,
      requiredSelection,
      requiredMeasured.rendered,
      requiredMeasured,
      {
        ...discardedCounts,
        soul: discardedCounts.soul + (selection.soul ? 1 : 0),
        preferences: discardedCounts.preferences + selection.preferences.length,
        history: discardedCounts.history + selection.history.length,
        memories: discardedCounts.memories + selection.memories.length,
        systemInstruction: discardedCounts.systemInstruction
          + (selection.optionalSystemInstruction ? 1 : 0),
      },
      reasons,
      input.userInput,
    );
    throw new CompanionContextBudgetError(metadata);
  }

  addBudgetReasons(reasons, measured, normalizedLimits);
  while (isOverBudget(measured, normalizedLimits)) {
    if (selection.memories.length > 0) {
      selection = {
        ...selection,
        memories: selection.memories.slice(0, -1),
      };
      addCount(discardedCounts, "memories");
      reasons.add("memory-budget");
    } else if (selection.history.length > 0) {
      // History arrives in original chronological order. Remove from the
      // front so the newest retained messages stay in original order.
      selection = {
        ...selection,
        history: selection.history.slice(1),
      };
      addCount(discardedCounts, "history");
      reasons.add("history-budget");
    } else if (selection.preferences.length > 0) {
      selection = {
        ...selection,
        preferences: selection.preferences.slice(0, -1),
      };
      addCount(discardedCounts, "preferences");
      reasons.add("preference-budget");
    } else if (selection.optionalSystemInstruction) {
      selection = { ...selection, optionalSystemInstruction: "" };
      addCount(discardedCounts, "systemInstruction");
      reasons.add("system-instruction-budget");
    } else if (selection.soul) {
      const trimmed = trimSoulToFit(input, selection, normalizedLimits);
      if (trimmed.selection.soul === selection.soul) {
        selection = { ...selection, soul: "" };
        addCount(discardedCounts, "soul");
      } else if (trimmed.selection.soul.length === 0) {
        selection = { ...selection, soul: "" };
        addCount(discardedCounts, "soul");
      } else {
        selection = trimmed.selection;
        addCount(discardedCounts, "soul");
      }
      reasons.add("soul-budget");
    } else {
      // This can only happen when the protected system block plus current
      // input exceeds the limits. Keep the fail-closed behavior explicit.
      reasons.add("required-content-over-budget");
      const failedMetadata = makeMetadata(
        normalizedLimits,
        selection,
        measured.rendered,
        measured,
        discardedCounts,
        reasons,
        input.userInput,
      );
      throw new CompanionContextBudgetError(failedMetadata);
    }
    measured = measureSelection(input, selection);
  }

  const metadata = makeMetadata(
    normalizedLimits,
    selection,
    measured.rendered,
    measured,
    discardedCounts,
    reasons,
    input.userInput,
  );
  return {
    systemInstruction: measured.rendered.systemInstruction,
    userInput: input.userInput,
    soul: selection.soul,
    preferences: selection.preferences,
    history: measured.rendered.history,
    memories: selection.memories,
    metadata,
  };
}

/**
 * Final provider-neutral guard for callers that already have a rendered
 * context. It can remove only older history; an oversized system block or
 * current input fails closed rather than clipping protected content.
 */
export function enforceCompanionContextBudget<T extends { text: string }>(
  context: {
    systemInstruction: string;
    userInput: string;
    history: readonly T[];
  },
  limits: CompanionContextBudgetLimits = {},
): {
  systemInstruction: string;
  userInput: string;
  history: readonly T[];
  metadata: CompanionContextBudgetMetadata;
} {
  const result = applyCompanionContextBudget(
    {
      requiredSystemInstruction: context.systemInstruction,
      userInput: context.userInput,
      history: context.history,
      render: (selection) => ({
        systemInstruction: selection.requiredSystemInstruction,
        history: selection.history,
      }),
    },
    limits,
  );
  return {
    systemInstruction: result.systemInstruction,
    userInput: result.userInput,
    history: result.history,
    metadata: result.metadata,
  };
}
