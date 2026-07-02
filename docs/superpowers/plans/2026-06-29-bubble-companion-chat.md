# Bubble Companion Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first version of pet-owned bubble companion chat with right-click double-click entry, on-pet stop/undo, local replies, structured preference memory, and pet-specific opener cues.

**Architecture:** Keep domain logic in small `src/pet-core/` modules, render chat through one focused React component, and integrate with `DesktopPetApp` only at the interaction boundary. Pet-specific opener cues and local replies live in `public/pets/<pet-id>/companion-chat.json`; user preferences live in versioned platform local storage.

**Tech Stack:** React 19, TypeScript, Vitest, Vite, existing Tauri runtime guards, existing pet manifest and sound helpers.

---

## File Structure

- Create: `src/pet-core/companionChat.ts`
  - Loads and parses pet-owned companion chat config.
  - Chooses opener cues and local replies.
  - Resolves optional opener sound cue keys.
- Create: `src/pet-core/companionChat.test.ts`
  - Covers config parsing, pet-relative loading, opener cue rules, local reply fallback, and deterministic selection.
- Create: `src/pet-core/companionPreferences.ts`
  - Stores structured user preferences.
  - Extracts explicit and low-risk inferred preferences from user input.
  - Filters health input into care preferences instead of medical records.
  - Supports deleting the most recent saved preference.
- Create: `src/pet-core/companionPreferences.test.ts`
  - Covers storage parsing, preference extraction, health boundaries, memory feedback text, and storage failure.
- Create: `src/pet-core/companionChatRuntime.ts`
  - Pure chat state machine for entering, sending, receiving, stopping, exiting, and idle timeout.
  - Provides `createLocalCompanionChatProvider`.
- Create: `src/pet-core/companionChatRuntime.test.ts`
  - Covers entry, opener messages, send/stop/undo, receive, exit, idle behavior, and provider output.
- Create: `src/pet-core/CompanionChatBubble.tsx`
  - Displays a bounded bubble list and stable bottom input row.
- Create: `src/pet-core/CompanionChatBubble.test.tsx`
  - Static markup tests for layout, user/pet bubbles, input value, disabled states, and bounded container classes.
- Modify: `src/pet-core/petAssets.ts`
  - Add optional `companionChatPath?: string` to `PetManifest`.
- Modify: `src/pet-core/petAssets.test.ts`
  - Assert built-in companion chat paths are safe and pet-local.
- Modify: `src/pet-core/interaction.test.ts`
  - Rename right-click tests from update-specific wording to generic secondary double-click detection.
- Modify: `src/App.tsx`
  - Load companion chat packages and preferences.
  - Route right-click double-click to chat mode instead of update check.
  - Intercept left-click as `stop` while chat mode is active.
  - Render `CompanionChatBubble`.
  - Keep existing update check reachable from existing app event and platform/tray paths.
- Modify: `src/App.css`
  - Add bounded chat bubble layout, user/pet bubble styles, and fixed input row.
- Create: `public/pets/xiaoju-cat/companion-chat.json`
- Create: `public/pets/ikun/companion-chat.json`
- Create: `public/pets/ds/companion-chat.json`
- Create: `public/pets/suan-bird/companion-chat.json`
- Modify: each built-in `public/pets/<pet-id>/pet.json`
  - Add `"companionChatPath": "companion-chat.json"`.

---

### Task 1: Pet Companion Chat Config Contract

**Files:**
- Create: `src/pet-core/companionChat.ts`
- Create: `src/pet-core/companionChat.test.ts`
- Modify: `src/pet-core/petAssets.ts`

- [ ] **Step 1: Write failing tests for companion chat config loading**

Create `src/pet-core/companionChat.test.ts`:

```ts
import { describe, expect, test, vi } from "vitest";
import {
  chooseCompanionChatCue,
  loadPetCompanionChatPackage,
  NEUTRAL_COMPANION_CHAT,
  resolveCompanionChatPackage,
  type CompanionChatConfig,
} from "./companionChat";
import type { PetManifest } from "./petAssets";

const manifest: PetManifest = {
  id: "xiaoju-cat",
  displayName: "小橘",
  description: "test",
  spritesheetPath: "spritesheet.png",
  companionChatPath: "companion-chat.json",
  animations: {
    idle: { row: 0, frames: 1, speed: 0.1, loop: true, visualClass: "ordinary" },
  },
  interactions: {
    idle: { animation: "idle" },
    singleClick: { animation: "idle", durationMs: 1000 },
    doubleClick: { animation: "idle", durationMs: 1000 },
    drag: { directionMode: "rows", right: "idle", left: "idle" },
    reminders: {
      eyeCare: { animation: "idle", durationMs: 1000 },
      water: { animation: "idle", durationMs: 1000 },
      meal: { animation: "idle", durationMs: 1000 },
      sleep: { animation: "idle", durationMs: 1000 },
    },
  },
};

const config: CompanionChatConfig = {
  openers: [
    { text: "喵？", sound: "chatOpenMew", weight: 2 },
    { text: "mew~", sound: "chatOpenMewSoft", weight: 1 },
  ],
  localReplies: ["嗯，我听着。", "慢慢说，我陪你。"],
  style: { tone: "quiet-companion", maxReplyLength: 36 },
};

describe("pet companion chat packages", () => {
  test("loads companion chat config from the active pet package", async () => {
    const fetchConfig = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => config,
    }));

    await expect(loadPetCompanionChatPackage(manifest, fetchConfig)).resolves.toEqual({
      status: "loaded",
      petId: "xiaoju-cat",
      config,
    });
    expect(fetchConfig).toHaveBeenCalledWith("/pets/xiaoju-cat/companion-chat.json");
  });

  test("falls back to neutral config when no package is configured", async () => {
    const fetchConfig = vi.fn();
    const result = await loadPetCompanionChatPackage(
      { ...manifest, companionChatPath: undefined },
      fetchConfig,
    );

    expect(fetchConfig).not.toHaveBeenCalled();
    expect(resolveCompanionChatPackage(result)).toEqual(NEUTRAL_COMPANION_CHAT);
  });

  test("rejects non-opener full greeting sentences", async () => {
    const warn = vi.fn();
    const result = await loadPetCompanionChatPackage(
      manifest,
      async () => ({
        ok: true,
        status: 200,
        json: async () => ({
          openers: [{ text: "我在呢，怎么啦？" }],
          localReplies: ["嗯。"],
        }),
      }),
      warn,
    );

    expect(result).toEqual({ status: "failed", petId: "xiaoju-cat" });
    expect(warn).toHaveBeenCalled();
  });

  test("chooses weighted opener cues deterministically", () => {
    expect(chooseCompanionChatCue(config.openers, () => 0.0).text).toBe("喵？");
    expect(chooseCompanionChatCue(config.openers, () => 0.66).text).toBe("喵？");
    expect(chooseCompanionChatCue(config.openers, () => 0.99).text).toBe("mew~");
  });
});
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
npm test -- src/pet-core/companionChat.test.ts
```

Expected: FAIL because `src/pet-core/companionChat.ts` does not exist and `PetManifest` does not declare `companionChatPath`.

- [ ] **Step 3: Add `companionChatPath` to `PetManifest`**

Modify `src/pet-core/petAssets.ts`:

```ts
export type PetManifest = {
  id: string;
  displayName: string;
  description: string;
  spritesheetPath: string;
  previewPath?: string;
  dialoguesPath?: string;
  companionChatPath?: string;
  animations: Record<string, PetAnimationSpec>;
  interactions: PetManifestInteractions;
  sounds?: PetManifestSounds;
};
```

- [ ] **Step 4: Implement companion chat config parsing**

Create `src/pet-core/companionChat.ts`:

```ts
import { resolvePetAssetUrl, type PetManifest } from "./petAssets";

export type CompanionChatOpenerCue = {
  text: string;
  sound?: string;
  weight?: number;
};

export type CompanionChatStyle = {
  tone: "quiet-companion";
  maxReplyLength: number;
};

export type CompanionChatConfig = {
  openers: CompanionChatOpenerCue[];
  localReplies: string[];
  style: CompanionChatStyle;
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

export type CompanionChatFetcher = (url: string) => Promise<CompanionChatResponse>;
export type CompanionChatWarning = (message: string, error?: unknown) => void;

export const NEUTRAL_COMPANION_CHAT: CompanionChatConfig = {
  openers: [{ text: "嗯？", weight: 1 }],
  localReplies: ["嗯，我听着。", "慢慢说，我陪你。"],
  style: { tone: "quiet-companion", maxReplyLength: 36 },
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireNonEmptyString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new Error(`Expected non-empty string at ${field}`);
  }
  return value.trim();
}

function isShortOpenerText(text: string): boolean {
  return text.length <= 8 && !/[，。！？!?]/.test(text.slice(0, -1));
}

function parseOpener(value: unknown, field: string): CompanionChatOpenerCue {
  const source = isRecord(value) ? value : { text: value };
  const text = requireNonEmptyString(source.text, `${field}.text`);
  if (!isShortOpenerText(text)) {
    throw new Error(`Expected short onomatopoeia at ${field}.text`);
  }

  const sound =
    source.sound === undefined
      ? undefined
      : requireNonEmptyString(source.sound, `${field}.sound`);
  const weight =
    source.weight === undefined
      ? 1
      : typeof source.weight === "number" && Number.isFinite(source.weight) && source.weight > 0
        ? source.weight
        : (() => {
            throw new Error(`Expected positive weight at ${field}.weight`);
          })();

  return { text, sound, weight };
}

function parseCompanionChatConfig(value: unknown): CompanionChatConfig {
  if (!isRecord(value)) throw new Error("Companion chat package must be an object");
  if (!Array.isArray(value.openers) || value.openers.length === 0) {
    throw new Error("Missing companion chat openers");
  }
  if (!Array.isArray(value.localReplies) || value.localReplies.length === 0) {
    throw new Error("Missing companion chat localReplies");
  }

  const openers = value.openers.map((opener, index) =>
    parseOpener(opener, `openers[${index}]`),
  );
  const localReplies = value.localReplies.map((reply, index) =>
    requireNonEmptyString(reply, `localReplies[${index}]`),
  );

  return {
    openers,
    localReplies,
    style: {
      tone: "quiet-companion",
      maxReplyLength: 36,
    },
  };
}

export async function loadPetCompanionChatPackage(
  manifest: PetManifest,
  fetchConfig: CompanionChatFetcher = (url) => fetch(url),
  warn: CompanionChatWarning = console.warn,
): Promise<CompanionChatPackage> {
  if (!manifest.companionChatPath) {
    return { status: "not-configured", petId: manifest.id };
  }

  const url = resolvePetAssetUrl(manifest.id, manifest.companionChatPath);
  try {
    const response = await fetchConfig(url);
    if (!response.ok) throw new Error(`Companion chat request failed: ${response.status}`);
    return {
      status: "loaded",
      petId: manifest.id,
      config: parseCompanionChatConfig(await response.json()),
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
  cues: CompanionChatOpenerCue[],
  random: () => number = Math.random,
): CompanionChatOpenerCue {
  const available = cues.length > 0 ? cues : NEUTRAL_COMPANION_CHAT.openers;
  const totalWeight = available.reduce((sum, cue) => sum + (cue.weight ?? 1), 0);
  let cursor = random() * totalWeight;

  for (const cue of available) {
    cursor -= cue.weight ?? 1;
    if (cursor <= 0) return cue;
  }

  return available[available.length - 1];
}
```

- [ ] **Step 5: Run the focused tests and verify they pass**

Run:

```powershell
npm test -- src/pet-core/companionChat.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add src/pet-core/companionChat.ts src/pet-core/companionChat.test.ts src/pet-core/petAssets.ts
git commit -m "feat: add pet companion chat config"
```

Expected: commit succeeds.

---

### Task 2: Structured Companion Preferences

**Files:**
- Create: `src/pet-core/companionPreferences.ts`
- Create: `src/pet-core/companionPreferences.test.ts`

- [ ] **Step 1: Write failing tests for preference memory**

Create `src/pet-core/companionPreferences.test.ts`:

```ts
import { describe, expect, test, vi } from "vitest";
import {
  COMPANION_PREFERENCES_STORAGE_KEY,
  EMPTY_COMPANION_PREFERENCES,
  deleteRecentPreference,
  extractCompanionPreference,
  isForgetRecentPreferenceRequest,
  parseCompanionPreferences,
  readCompanionPreferences,
  writeCompanionPreferences,
} from "./companionPreferences";

function createStorage(initialValue: string | null = null) {
  let value = initialValue;
  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((_key: string, nextValue: string) => {
      value = nextValue;
    }),
  };
}

describe("companion preferences", () => {
  test("extracts explicit nickname preferences with feedback", () => {
    expect(extractCompanionPreference("以后叫我阿星", "xiaoju-cat")).toEqual({
      preference: {
        id: "global.nickname",
        scope: "global",
        category: "userProfile",
        key: "nickname",
        value: "阿星",
        source: "explicit",
      },
      feedback: "好呀，我以后叫你阿星。",
    });
  });

  test("extracts quiet style and short reply preferences", () => {
    expect(extractCompanionPreference("回答短一点，别太严肃", "ds")).toEqual({
      preference: {
        id: "global.replyStyle",
        scope: "global",
        category: "userProfile",
        key: "replyStyle",
        value: "short-and-soft",
        source: "explicit",
      },
      feedback: "嗯，我记住啦，以后我尽量说短一点、轻一点。",
    });
  });

  test("stores health input as care preference instead of diagnosis", () => {
    const result = extractCompanionPreference("我有偏头痛，提醒我少盯屏幕", "xiaoju-cat");

    expect(result?.preference).toMatchObject({
      id: "global.eyeCare",
      category: "reminderPreferences",
      key: "eyeCare",
      value: "reduce-screen-staring",
    });
    expect(JSON.stringify(result)).not.toContain("患有偏头痛");
  });

  test("ignores uncertain and sensitive inputs", () => {
    expect(extractCompanionPreference("今天好累", "xiaoju-cat")).toBeNull();
    expect(extractCompanionPreference("我的身份证号是 123", "xiaoju-cat")).toBeNull();
  });

  test("detects natural language requests to forget the recent preference", () => {
    expect(isForgetRecentPreferenceRequest("忘掉这个")).toBe(true);
    expect(isForgetRecentPreferenceRequest("别记这个")).toBe(true);
    expect(isForgetRecentPreferenceRequest("你好呀")).toBe(false);
  });

  test("reads, writes, repairs, and deletes recent preferences", () => {
    const storage = createStorage();
    const warn = vi.fn();
    const state = {
      preferences: [
        {
          id: "global.nickname",
          scope: "global" as const,
          category: "userProfile" as const,
          key: "nickname",
          value: "阿星",
          source: "explicit" as const,
        },
      ],
      recentPreferenceId: "global.nickname",
    };

    expect(writeCompanionPreferences(state, storage, warn)).toBe(true);
    expect(storage.setItem).toHaveBeenCalledWith(
      COMPANION_PREFERENCES_STORAGE_KEY,
      JSON.stringify(state),
    );
    expect(readCompanionPreferences(storage, warn)).toEqual(state);
    expect(deleteRecentPreference(state)).toEqual({
      preferences: [],
      recentPreferenceId: null,
    });
    expect(parseCompanionPreferences("not-json")).toEqual(EMPTY_COMPANION_PREFERENCES);
  });
});
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
npm test -- src/pet-core/companionPreferences.test.ts
```

Expected: FAIL because `src/pet-core/companionPreferences.ts` does not exist.

- [ ] **Step 3: Implement structured preference memory**

Create `src/pet-core/companionPreferences.ts`:

```ts
export const COMPANION_PREFERENCES_STORAGE_KEY = "yuxin-companion-preferences-v1";

export type CompanionPreferenceScope = "global" | `pet:${string}`;
export type CompanionPreferenceCategory =
  | "userProfile"
  | "reminderPreferences"
  | "petRelationship";
export type CompanionPreferenceSource = "explicit" | "inferred";

export type CompanionPreference = {
  id: string;
  scope: CompanionPreferenceScope;
  category: CompanionPreferenceCategory;
  key: string;
  value: string;
  source: CompanionPreferenceSource;
};

export type CompanionPreferencesState = {
  preferences: CompanionPreference[];
  recentPreferenceId: string | null;
};

export type CompanionPreferenceExtraction = {
  preference: CompanionPreference;
  feedback: string;
};

export type CompanionPreferenceStorage = Pick<Storage, "getItem" | "setItem">;
export type CompanionPreferenceWarning = (message: string, error?: unknown) => void;

export const EMPTY_COMPANION_PREFERENCES: CompanionPreferencesState = {
  preferences: [],
  recentPreferenceId: null,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasSensitiveContent(text: string): boolean {
  return /身份证|银行卡|密码|住址|地址|账号|药|病史|检查报告|诊断/.test(text);
}

function normalizeNickname(text: string): string | null {
  const match = text.match(/(?:以后|之后)?叫我([^，。！？!\s]{1,12})/);
  return match?.[1]?.trim() ?? null;
}

export function extractCompanionPreference(
  text: string,
  activePetId: string,
): CompanionPreferenceExtraction | null {
  const trimmed = text.trim();
  if (trimmed.length === 0 || hasSensitiveContent(trimmed)) return null;

  const nickname = normalizeNickname(trimmed);
  if (nickname) {
    return {
      preference: {
        id: "global.nickname",
        scope: "global",
        category: "userProfile",
        key: "nickname",
        value: nickname,
        source: "explicit",
      },
      feedback: `好呀，我以后叫你${nickname}。`,
    };
  }

  if (/短一点|少讲|别太严肃|轻松一点/.test(trimmed)) {
    return {
      preference: {
        id: "global.replyStyle",
        scope: "global",
        category: "userProfile",
        key: "replyStyle",
        value: "short-and-soft",
        source: "explicit",
      },
      feedback: "嗯，我记住啦，以后我尽量说短一点、轻一点。",
    };
  }

  if (/安静|别太吵|少打扰/.test(trimmed)) {
    return {
      preference: {
        id: "global.companionStyle",
        scope: "global",
        category: "userProfile",
        key: "companionStyle",
        value: "quiet",
        source: "inferred",
      },
      feedback: "嗯，我记住啦，会尽量安静一点陪你。",
    };
  }

  if (/眼睛|盯屏|看屏幕/.test(trimmed) && /提醒|休息|少/.test(trimmed)) {
    return {
      preference: {
        id: "global.eyeCare",
        scope: "global",
        category: "reminderPreferences",
        key: "eyeCare",
        value: "reduce-screen-staring",
        source: "explicit",
      },
      feedback: "我记住啦，会多提醒你休息眼睛。",
    };
  }

  if (/只对你|你叫我|我们之间/.test(trimmed)) {
    return {
      preference: {
        id: `pet:${activePetId}.relationship`,
        scope: `pet:${activePetId}`,
        category: "petRelationship",
        key: "relationshipNote",
        value: trimmed.slice(0, 40),
        source: "explicit",
      },
      feedback: "嗯，我记住这是我们之间的小习惯。",
    };
  }

  return null;
}

export function isForgetRecentPreferenceRequest(text: string): boolean {
  return /忘掉这个|忘掉刚才|别记这个|不要记这个/.test(text.trim());
}

export function parseCompanionPreferences(value: string | null): CompanionPreferencesState {
  if (!value) return EMPTY_COMPANION_PREFERENCES;
  try {
    const parsed = JSON.parse(value) as unknown;
    if (!isRecord(parsed) || !Array.isArray(parsed.preferences)) {
      return EMPTY_COMPANION_PREFERENCES;
    }

    const preferences = parsed.preferences.filter((item): item is CompanionPreference => {
      return (
        isRecord(item) &&
        typeof item.id === "string" &&
        typeof item.scope === "string" &&
        typeof item.category === "string" &&
        typeof item.key === "string" &&
        typeof item.value === "string" &&
        (item.source === "explicit" || item.source === "inferred")
      );
    });

    return {
      preferences,
      recentPreferenceId:
        typeof parsed.recentPreferenceId === "string" ? parsed.recentPreferenceId : null,
    };
  } catch {
    return EMPTY_COMPANION_PREFERENCES;
  }
}

export function upsertCompanionPreference(
  state: CompanionPreferencesState,
  preference: CompanionPreference,
): CompanionPreferencesState {
  return {
    preferences: [
      ...state.preferences.filter((existing) => existing.id !== preference.id),
      preference,
    ],
    recentPreferenceId: preference.id,
  };
}

export function deleteRecentPreference(
  state: CompanionPreferencesState,
): CompanionPreferencesState {
  if (!state.recentPreferenceId) return state;
  return {
    preferences: state.preferences.filter(
      (preference) => preference.id !== state.recentPreferenceId,
    ),
    recentPreferenceId: null,
  };
}

export function readCompanionPreferences(
  storage: CompanionPreferenceStorage = window.localStorage,
  warn: CompanionPreferenceWarning = console.warn,
): CompanionPreferencesState {
  try {
    return parseCompanionPreferences(storage.getItem(COMPANION_PREFERENCES_STORAGE_KEY));
  } catch (error) {
    warn("[companion-preferences] Failed to read preferences", error);
    return EMPTY_COMPANION_PREFERENCES;
  }
}

export function writeCompanionPreferences(
  state: CompanionPreferencesState,
  storage: CompanionPreferenceStorage = window.localStorage,
  warn: CompanionPreferenceWarning = console.warn,
): boolean {
  try {
    storage.setItem(COMPANION_PREFERENCES_STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch (error) {
    warn("[companion-preferences] Failed to write preferences", error);
    return false;
  }
}
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```powershell
npm test -- src/pet-core/companionPreferences.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git add src/pet-core/companionPreferences.ts src/pet-core/companionPreferences.test.ts
git commit -m "feat: add companion preference memory"
```

Expected: commit succeeds.

---

### Task 3: Companion Chat Runtime and Local Provider

**Files:**
- Create: `src/pet-core/companionChatRuntime.ts`
- Create: `src/pet-core/companionChatRuntime.test.ts`

- [ ] **Step 1: Write failing runtime tests**

Create `src/pet-core/companionChatRuntime.test.ts`:

```ts
import { describe, expect, test } from "vitest";
import {
  CHAT_IDLE_TIMEOUT_MS,
  createLocalCompanionChatProvider,
  enterCompanionChat,
  exitCompanionChat,
  receiveCompanionReply,
  sendCompanionMessage,
  shouldAutoExitCompanionChat,
  stopCompanionReply,
  updateCompanionDraft,
} from "./companionChatRuntime";
import type { CompanionChatConfig } from "./companionChat";

const config: CompanionChatConfig = {
  openers: [{ text: "喵？", sound: "chatOpenMew", weight: 1 }],
  localReplies: ["嗯，我听着。"],
  style: { tone: "quiet-companion", maxReplyLength: 36 },
};

describe("companion chat runtime", () => {
  test("enters chat with a pet opener cue", () => {
    const state = enterCompanionChat(config, 1000, () => 0);

    expect(state.mode).toBe("active");
    expect(state.messages).toEqual([
      { id: "opener-1000", speaker: "pet", text: "喵？", sound: "chatOpenMew" },
    ]);
    expect(state.draft).toBe("");
  });

  test("sends a user message and keeps it undoable while pending", () => {
    const entered = updateCompanionDraft(enterCompanionChat(config, 1000), "打错了");
    const sent = sendCompanionMessage(entered, 1200);

    expect(sent.draft).toBe("");
    expect(sent.pendingUserMessage?.text).toBe("打错了");
    expect(sent.messages.at(-1)).toMatchObject({ speaker: "user", text: "打错了" });
  });

  test("stop removes pending user bubble and restores draft", () => {
    const sent = sendCompanionMessage(
      updateCompanionDraft(enterCompanionChat(config, 1000), "打错了"),
      1200,
    );

    expect(stopCompanionReply(sent)).toMatchObject({
      draft: "打错了",
      pendingUserMessage: null,
    });
    expect(stopCompanionReply(sent).messages.some((message) => message.text === "打错了")).toBe(false);
  });

  test("receives pet reply and clears undo state", () => {
    const sent = sendCompanionMessage(
      updateCompanionDraft(enterCompanionChat(config, 1000), "你好"),
      1200,
    );
    const received = receiveCompanionReply(sent, "嗯，我听着。", 1500);

    expect(received.pendingUserMessage).toBeNull();
    expect(received.messages.at(-1)).toMatchObject({ speaker: "pet", text: "嗯，我听着。" });
  });

  test("does not auto exit with draft or pending reply", () => {
    const active = updateCompanionDraft(enterCompanionChat(config, 1000), "还没写完");
    expect(shouldAutoExitCompanionChat(active, 1000 + CHAT_IDLE_TIMEOUT_MS + 1)).toBe(false);
    expect(shouldAutoExitCompanionChat(enterCompanionChat(config, 1000), 1000 + CHAT_IDLE_TIMEOUT_MS + 1)).toBe(true);
  });

  test("local provider returns deterministic short replies", async () => {
    const provider = createLocalCompanionChatProvider(config, () => 0);
    await expect(provider.send({ text: "你好", preferences: [] })).resolves.toEqual({
      requestId: "local",
      text: "嗯，我听着。",
    });
    expect(exitCompanionChat(enterCompanionChat(config, 1000))).toMatchObject({
      mode: "inactive",
      messages: [],
    });
  });
});
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
npm test -- src/pet-core/companionChatRuntime.test.ts
```

Expected: FAIL because `src/pet-core/companionChatRuntime.ts` does not exist.

- [ ] **Step 3: Implement pure runtime and local provider**

Create `src/pet-core/companionChatRuntime.ts`:

```ts
import {
  chooseCompanionChatCue,
  type CompanionChatConfig,
  type CompanionChatOpenerCue,
} from "./companionChat";
import type { CompanionPreference } from "./companionPreferences";

export const CHAT_IDLE_TIMEOUT_MS = 90000;
export type CompanionMessageSpeaker = "user" | "pet";

export type CompanionChatMessage = {
  id: string;
  speaker: CompanionMessageSpeaker;
  text: string;
  sound?: string;
};

export type CompanionChatState = {
  mode: "inactive" | "active";
  draft: string;
  messages: CompanionChatMessage[];
  pendingUserMessage: CompanionChatMessage | null;
  pendingRequestId: string | null;
  lastActivityAt: number;
};

export type CompanionChatRequest = {
  text: string;
  preferences: CompanionPreference[];
};

export type CompanionChatResponse = {
  requestId: string;
  text: string;
};

export type CompanionChatProvider = {
  send: (input: CompanionChatRequest) => Promise<CompanionChatResponse>;
  stop: (requestId: string) => void;
};

export const INACTIVE_COMPANION_CHAT: CompanionChatState = {
  mode: "inactive",
  draft: "",
  messages: [],
  pendingUserMessage: null,
  pendingRequestId: null,
  lastActivityAt: 0,
};

function createMessage(
  id: string,
  speaker: CompanionMessageSpeaker,
  text: string,
  sound?: string,
): CompanionChatMessage {
  return sound ? { id, speaker, text, sound } : { id, speaker, text };
}

export function enterCompanionChat(
  config: CompanionChatConfig,
  now = Date.now(),
  random: () => number = Math.random,
): CompanionChatState {
  const opener: CompanionChatOpenerCue = chooseCompanionChatCue(config.openers, random);
  return {
    mode: "active",
    draft: "",
    messages: [createMessage(`opener-${now}`, "pet", opener.text, opener.sound)],
    pendingUserMessage: null,
    pendingRequestId: null,
    lastActivityAt: now,
  };
}

export function updateCompanionDraft(
  state: CompanionChatState,
  draft: string,
  now = Date.now(),
): CompanionChatState {
  return { ...state, draft, lastActivityAt: now };
}

export function sendCompanionMessage(
  state: CompanionChatState,
  now = Date.now(),
): CompanionChatState {
  const text = state.draft.trim();
  if (!text || state.mode !== "active") return state;

  const message = createMessage(`user-${now}`, "user", text);
  return {
    ...state,
    draft: "",
    messages: [...state.messages, message],
    pendingUserMessage: message,
    pendingRequestId: `request-${now}`,
    lastActivityAt: now,
  };
}

export function stopCompanionReply(state: CompanionChatState): CompanionChatState {
  if (!state.pendingUserMessage) return state;
  return {
    ...state,
    draft: state.pendingUserMessage.text,
    messages: state.messages.filter((message) => message.id !== state.pendingUserMessage?.id),
    pendingUserMessage: null,
    pendingRequestId: null,
    lastActivityAt: Date.now(),
  };
}

export function receiveCompanionReply(
  state: CompanionChatState,
  reply: string,
  now = Date.now(),
): CompanionChatState {
  if (state.mode !== "active") return state;
  return {
    ...state,
    messages: [...state.messages, createMessage(`pet-${now}`, "pet", reply)],
    pendingUserMessage: null,
    pendingRequestId: null,
    lastActivityAt: now,
  };
}

export function exitCompanionChat(state: CompanionChatState): CompanionChatState {
  return { ...INACTIVE_COMPANION_CHAT, lastActivityAt: state.lastActivityAt };
}

export function shouldAutoExitCompanionChat(
  state: CompanionChatState,
  now = Date.now(),
): boolean {
  return (
    state.mode === "active" &&
    state.draft.trim().length === 0 &&
    state.pendingRequestId === null &&
    now - state.lastActivityAt >= CHAT_IDLE_TIMEOUT_MS
  );
}

export function createLocalCompanionChatProvider(
  config: CompanionChatConfig,
  random: () => number = Math.random,
): CompanionChatProvider {
  return {
    async send() {
      const index = Math.min(
        Math.floor(random() * config.localReplies.length),
        config.localReplies.length - 1,
      );
      return { requestId: "local", text: config.localReplies[index] };
    },
    stop() {
      return undefined;
    },
  };
}
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```powershell
npm test -- src/pet-core/companionChatRuntime.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```powershell
git add src/pet-core/companionChatRuntime.ts src/pet-core/companionChatRuntime.test.ts
git commit -m "feat: add companion chat runtime"
```

Expected: commit succeeds.

---

### Task 4: Bubble Chat UI Component

**Files:**
- Create: `src/pet-core/CompanionChatBubble.tsx`
- Create: `src/pet-core/CompanionChatBubble.test.tsx`
- Modify: `src/App.css`

- [ ] **Step 1: Write failing static markup tests**

Create `src/pet-core/CompanionChatBubble.test.tsx`:

```tsx
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import { CompanionChatBubble } from "./CompanionChatBubble";

describe("CompanionChatBubble", () => {
  test("renders bounded bubbles and a stable input row", () => {
    const html = renderToStaticMarkup(
      <CompanionChatBubble
        draft="你好"
        messages={[
          { id: "pet-1", speaker: "pet", text: "喵？" },
          { id: "user-1", speaker: "user", text: "我来了" },
        ]}
        isWaiting={false}
        onDraftChange={vi.fn()}
        onSend={vi.fn()}
        onStop={vi.fn()}
      />,
    );

    expect(html).toContain("companion-chat");
    expect(html).toContain("companion-chat-log");
    expect(html).toContain("companion-chat-message is-pet");
    expect(html).toContain("companion-chat-message is-user");
    expect(html).toContain("value=\"你好\"");
    expect(html).toContain("aria-label=\"和桌宠说话\"");
  });

  test("shows stop state while waiting", () => {
    const html = renderToStaticMarkup(
      <CompanionChatBubble
        draft=""
        messages={[{ id: "pet-1", speaker: "pet", text: "喵？" }]}
        isWaiting={true}
        onDraftChange={vi.fn()}
        onSend={vi.fn()}
        onStop={vi.fn()}
      />,
    );

    expect(html).toContain("停止");
    expect(html).toContain("is-waiting");
  });
});
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
npm test -- src/pet-core/CompanionChatBubble.test.tsx
```

Expected: FAIL because `CompanionChatBubble.tsx` does not exist.

- [ ] **Step 3: Implement the component**

Create `src/pet-core/CompanionChatBubble.tsx`:

```tsx
import type { FormEvent } from "react";
import type { CompanionChatMessage } from "./companionChatRuntime";

type CompanionChatBubbleProps = {
  draft: string;
  messages: CompanionChatMessage[];
  isWaiting: boolean;
  onDraftChange: (draft: string) => void;
  onSend: () => void;
  onStop: () => void;
};

export function CompanionChatBubble({
  draft,
  messages,
  isWaiting,
  onDraftChange,
  onSend,
  onStop,
}: CompanionChatBubbleProps) {
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (draft.trim().length > 0 && !isWaiting) onSend();
  };

  return (
    <section className={`companion-chat${isWaiting ? " is-waiting" : ""}`}>
      <div className="companion-chat-log" aria-live="polite">
        {messages.map((message) => (
          <div
            className={`companion-chat-message is-${message.speaker}`}
            key={message.id}
          >
            {message.text}
          </div>
        ))}
      </div>
      <form className="companion-chat-input-row" onSubmit={submit}>
        <input
          aria-label="和桌宠说话"
          value={draft}
          onChange={(event) => onDraftChange(event.currentTarget.value)}
        />
        {isWaiting ? (
          <button type="button" onClick={onStop}>
            停止
          </button>
        ) : (
          <button type="submit" disabled={draft.trim().length === 0}>
            发送
          </button>
        )}
      </form>
    </section>
  );
}
```

- [ ] **Step 4: Add CSS for bounded layout**

Modify `src/App.css` by appending:

```css
.companion-chat {
  position: absolute;
  left: 50%;
  bottom: calc(var(--pet-bubble-bottom) + 22px);
  width: min(280px, calc(100vw - 24px));
  max-height: 210px;
  transform: translateX(-50%);
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 8px;
  pointer-events: auto;
  z-index: 4;
}

.companion-chat-log {
  min-height: 0;
  max-height: 158px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 6px;
}

.companion-chat-message {
  max-width: 86%;
  padding: 7px 10px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.35;
  overflow-wrap: anywhere;
  color: #2b211b;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 6px 18px rgba(48, 35, 26, 0.14);
}

.companion-chat-message.is-pet {
  align-self: flex-start;
}

.companion-chat-message.is-user {
  align-self: flex-end;
  background: rgba(255, 244, 218, 0.96);
}

.companion-chat-input-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 6px;
  padding: 6px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 8px 24px rgba(48, 35, 26, 0.16);
}

.companion-chat-input-row input {
  min-width: 0;
  border: 1px solid rgba(97, 72, 53, 0.22);
  border-radius: 6px;
  padding: 7px 8px;
  font: inherit;
}

.companion-chat-input-row button {
  border: 0;
  border-radius: 6px;
  padding: 0 10px;
  font: inherit;
  color: #fff;
  background: #6d5b4b;
}

.companion-chat-input-row button:disabled {
  opacity: 0.45;
}
```

- [ ] **Step 5: Run component tests**

Run:

```powershell
npm test -- src/pet-core/CompanionChatBubble.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

Run:

```powershell
git add src/pet-core/CompanionChatBubble.tsx src/pet-core/CompanionChatBubble.test.tsx src/App.css
git commit -m "feat: add companion chat bubble UI"
```

Expected: commit succeeds.

---

### Task 5: Built-In Pet Chat Packages

**Files:**
- Create: `public/pets/xiaoju-cat/companion-chat.json`
- Create: `public/pets/ikun/companion-chat.json`
- Create: `public/pets/ds/companion-chat.json`
- Create: `public/pets/suan-bird/companion-chat.json`
- Modify: `public/pets/xiaoju-cat/pet.json`
- Modify: `public/pets/ikun/pet.json`
- Modify: `public/pets/ds/pet.json`
- Modify: `public/pets/suan-bird/pet.json`
- Modify: `src/pet-core/petAssets.test.ts`

- [ ] **Step 1: Add failing asset tests**

Append this test to `src/pet-core/petAssets.test.ts`:

```ts
test("declares companion chat packages for every built-in pet", () => {
  for (const manifest of builtInManifests) {
    expect(manifest.companionChatPath).toBe("companion-chat.json");
    expect(resolvePetAssetUrl(manifest.id, manifest.companionChatPath)).toBe(
      `/pets/${manifest.id}/companion-chat.json`,
    );
  }
});
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```powershell
npm test -- src/pet-core/petAssets.test.ts
```

Expected: FAIL because built-in pet manifests do not declare `companionChatPath`.

- [ ] **Step 3: Add companion chat JSON files**

Create `public/pets/xiaoju-cat/companion-chat.json`:

```json
{
  "openers": [
    { "text": "喵？", "sound": "chatOpenMew", "weight": 2 },
    { "text": "mew~", "sound": "chatOpenMewSoft", "weight": 1 }
  ],
  "localReplies": ["嗯，我听着。", "慢慢说，小橘在这里。", "喵，陪你一会儿。"],
  "style": { "tone": "quiet-companion", "maxReplyLength": 36 }
}
```

Create `public/pets/ds/companion-chat.json`:

```json
{
  "openers": [
    { "text": "咕噜？", "weight": 2 },
    { "text": "呜~", "weight": 1 }
  ],
  "localReplies": ["慢慢说，我们一起听一会儿。", "嗯，我们一点点来。", "我在旁边陪着你。"],
  "style": { "tone": "quiet-companion", "maxReplyLength": 36 }
}
```

Create `public/pets/ikun/companion-chat.json`:

```json
{
  "openers": [
    { "text": "嗯？", "weight": 2 },
    { "text": "哼？", "weight": 1 }
  ],
  "localReplies": ["说吧，我听着。", "先别急，慢慢来。", "可以，继续。"],
  "style": { "tone": "quiet-companion", "maxReplyLength": 36 }
}
```

Create `public/pets/suan-bird/companion-chat.json`:

```json
{
  "openers": [
    { "text": "啾？", "weight": 2 },
    { "text": "咕？", "weight": 1 }
  ],
  "localReplies": ["啾，我在。", "慢慢说，蒜鸟听着。", "嗯，先陪你一会儿。"],
  "style": { "tone": "quiet-companion", "maxReplyLength": 36 }
}
```

- [ ] **Step 4: Add `companionChatPath` to each pet manifest**

Modify each built-in `pet.json` near `dialoguesPath`:

```json
"dialoguesPath": "dialogues.json",
"companionChatPath": "companion-chat.json",
```

- [ ] **Step 5: Run asset and companion config tests**

Run:

```powershell
npm test -- src/pet-core/petAssets.test.ts src/pet-core/companionChat.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

Run:

```powershell
git add public/pets src/pet-core/petAssets.test.ts
git commit -m "feat: add built-in companion chat packages"
```

Expected: commit succeeds.

---

### Task 6: App Integration

**Files:**
- Modify: `src/App.tsx`
- Modify: `src/pet-core/interaction.test.ts`

- [ ] **Step 1: Update right-click interaction test wording**

Modify the first test name in `src/pet-core/interaction.test.ts`:

```ts
test("detects the second right click inside the double-click window", () => {
  const first = registerSecondaryClick(null, 1000);
  expect(first).toEqual({ triggered: false, lastClickAt: 1000 });

  expect(registerSecondaryClick(first.lastClickAt, 1250)).toEqual({
    triggered: true,
    lastClickAt: null,
  });
});
```

- [ ] **Step 2: Run the interaction tests**

Run:

```powershell
npm test -- src/pet-core/interaction.test.ts
```

Expected: PASS.

- [ ] **Step 3: Add imports to `src/App.tsx`**

Add imports:

```ts
import { CompanionChatBubble } from "./pet-core/CompanionChatBubble";
import {
  createLocalCompanionChatProvider,
  enterCompanionChat,
  exitCompanionChat,
  receiveCompanionReply,
  sendCompanionMessage,
  shouldAutoExitCompanionChat,
  stopCompanionReply,
  updateCompanionDraft,
  INACTIVE_COMPANION_CHAT,
  type CompanionChatState,
} from "./pet-core/companionChatRuntime";
import {
  loadPetCompanionChatPackage,
  resolveCompanionChatPackage,
  type CompanionChatPackage,
} from "./pet-core/companionChat";
import {
  deleteRecentPreference,
  extractCompanionPreference,
  isForgetRecentPreferenceRequest,
  readCompanionPreferences,
  upsertCompanionPreference,
  writeCompanionPreferences,
  type CompanionPreferencesState,
} from "./pet-core/companionPreferences";
```

- [ ] **Step 4: Add companion state near existing dialogue state**

Add state in `DesktopPetApp` near `petDialoguesById`:

```ts
const [petCompanionChatsById, setPetCompanionChatsById] = useState<
  Record<string, CompanionChatPackage>
>({});
const [companionChatState, setCompanionChatState] =
  useState<CompanionChatState>(INACTIVE_COMPANION_CHAT);
const companionPreferencesRef = useRef<CompanionPreferencesState>(
  readCompanionPreferences(),
);
```

- [ ] **Step 5: Load companion chat packages with manifests**

In the manifest loading effect, after dialogue entries are loaded, add companion chat entries:

```ts
const companionChatEntries = await Promise.all(
  manifestEntries.map(
    async ([petId, manifest]) =>
      [petId, await loadPetCompanionChatPackage(manifest)] as const,
  ),
);
```

Set state next to `setPetDialoguesById`:

```ts
setPetCompanionChatsById(Object.fromEntries(companionChatEntries));
```

In the fallback branch, load and set default companion chat:

```ts
const fallbackCompanionChat =
  await loadPetCompanionChatPackage(fallbackManifest);
if (disposed) return;
setPetCompanionChatsById({ [DEFAULT_PET_ID]: fallbackCompanionChat });
```

- [ ] **Step 6: Add helper functions in `DesktopPetApp`**

Add helpers near `getDialoguePackageForPet`:

```ts
const getCompanionChatPackageForPet = (petId: string): CompanionChatPackage => {
  const loaded = petCompanionChatsById[petId];
  if (loaded) return loaded;

  return petManifestsById[petId]?.companionChatPath
    ? { status: "failed", petId }
    : { status: "not-configured", petId };
};

const startCompanionChat = () => {
  const config = resolveCompanionChatPackage(getCompanionChatPackageForPet(activePetId));
  const nextState = enterCompanionChat(config);
  setCompanionChatState(nextState);
  const openerSound = nextState.messages[0]?.sound;
  if (openerSound) playPetSound(openerSound);
  recordInteraction("companion_chat_open");
};

const stopCompanionChatReply = () => {
  setCompanionChatState((current) => stopCompanionReply(current));
  recordInteraction("companion_chat_stop");
};
```

- [ ] **Step 7: Replace right-click double-click update with chat entry**

Change `handleSecondaryPress`:

```ts
const handleSecondaryPress = () => {
  const click = registerSecondaryClick(lastSecondaryClickAt.current, Date.now());
  lastSecondaryClickAt.current = click.lastClickAt;

  if (!click.triggered) {
    recordInteraction("secondary_click_armed");
    return;
  }

  recordInteraction("secondary_double_click_companion_chat");
  startCompanionChat();
};
```

- [ ] **Step 8: Intercept left click while chat is active**

At the start of left-button `startPress`, before normal click/drag setup, add:

```ts
if (companionChatState.mode === "active" && button === 0) {
  stopCompanionChatReply();
  return false;
}
```

If direct access to `companionChatState` inside `startPress` causes stale closure behavior, mirror it with a ref:

```ts
const companionChatStateRef = useRef(companionChatState);
useEffect(() => {
  companionChatStateRef.current = companionChatState;
}, [companionChatState]);
```

Then check `companionChatStateRef.current.mode`.

- [ ] **Step 9: Add send and draft handlers**

Add:

```ts
const updateCompanionDraftText = (draft: string) => {
  setCompanionChatState((current) => updateCompanionDraft(current, draft));
};

const sendCompanionChatMessage = () => {
  const config = resolveCompanionChatPackage(getCompanionChatPackageForPet(activePetId));
  let sentState: CompanionChatState | null = null;

  setCompanionChatState((current) => {
    sentState = sendCompanionMessage(current);
    return sentState;
  });

  window.setTimeout(() => {
    if (!sentState?.pendingUserMessage) return;
    const userText = sentState.pendingUserMessage.text;
    const provider = createLocalCompanionChatProvider(config);
    void provider
      .send({
        text: userText,
        preferences: companionPreferencesRef.current.preferences,
      })
      .then((reply) => {
        if (isForgetRecentPreferenceRequest(userText)) {
          const nextPreferences = deleteRecentPreference(companionPreferencesRef.current);
          companionPreferencesRef.current = nextPreferences;
          writeCompanionPreferences(nextPreferences);
          setCompanionChatState((current) =>
            receiveCompanionReply(current, "好，我忘掉刚才那条。"),
          );
          return;
        }

        const extraction = extractCompanionPreference(userText, activePetId);
        if (extraction) {
          const nextPreferences = upsertCompanionPreference(
            companionPreferencesRef.current,
            extraction.preference,
          );
          companionPreferencesRef.current = nextPreferences;
          writeCompanionPreferences(nextPreferences);
          setCompanionChatState((current) =>
            receiveCompanionReply(
              receiveCompanionReply(current, extraction.feedback),
              reply.text,
            ),
          );
          return;
        }

        setCompanionChatState((current) => receiveCompanionReply(current, reply.text));
      });
  }, 0);
};

const exitActiveCompanionChat = () => {
  setCompanionChatState((current) => exitCompanionChat(current));
  setDefaultBubbleText();
};
```

- [ ] **Step 10: Add keyboard, outside click, and idle exit effects**

Add effects:

```ts
useEffect(() => {
  if (companionChatState.mode !== "active") return undefined;

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape") exitActiveCompanionChat();
  };

  window.addEventListener("keydown", onKeyDown);
  return () => window.removeEventListener("keydown", onKeyDown);
}, [companionChatState.mode]);

useEffect(() => {
  if (companionChatState.mode !== "active") return undefined;

  const onPointerDown = (event: PointerEvent) => {
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest(".companion-chat,.pet-hit-area,.pet-canvas")) return;
    exitActiveCompanionChat();
  };

  window.addEventListener("pointerdown", onPointerDown);
  return () => window.removeEventListener("pointerdown", onPointerDown);
}, [companionChatState.mode]);

useEffect(() => {
  if (companionChatState.mode !== "active") return undefined;

  const timer = window.setInterval(() => {
    setCompanionChatState((current) =>
      shouldAutoExitCompanionChat(current) ? exitCompanionChat(current) : current,
    );
  }, 1000);

  return () => window.clearInterval(timer);
}, [companionChatState.mode]);
```

- [ ] **Step 11: Render companion chat UI**

In the pet shell render near the existing bubble block, render chat first:

```tsx
{companionChatState.mode === "active" && (
  <CompanionChatBubble
    draft={companionChatState.draft}
    messages={companionChatState.messages}
    isWaiting={companionChatState.pendingRequestId !== null}
    onDraftChange={updateCompanionDraftText}
    onSend={sendCompanionChatMessage}
    onStop={stopCompanionChatReply}
  />
)}
```

Keep the existing non-chat `bubbleText` block hidden while chat mode is active:

```tsx
{companionChatState.mode !== "active" && bubbleText && (
  <div className={`bubble${careReminderPrompt ? " has-actions" : ""}`}>
    ...
  </div>
)}
```

- [ ] **Step 12: Close chat on pet selection**

In `selectPet`, before changing active pet:

```ts
setCompanionChatState((current) => exitCompanionChat(current));
```

- [ ] **Step 13: Run focused app-adjacent tests**

Run:

```powershell
npm test -- src/pet-core/interaction.test.ts src/pet-core/companionChatRuntime.test.ts src/pet-core/CompanionChatBubble.test.tsx
```

Expected: PASS.

- [ ] **Step 14: Commit Task 6**

Run:

```powershell
git add src/App.tsx src/pet-core/interaction.test.ts
git commit -m "feat: wire companion chat into pet interactions"
```

Expected: commit succeeds.

---

### Task 7: Preference Management Surface

**Files:**
- Create: `src/pet-core/CompanionPreferencesPanel.tsx`
- Create: `src/pet-core/CompanionPreferencesPanel.test.tsx`
- Modify: `src/App.tsx`
- Modify: `src/App.css`

- [ ] **Step 1: Write failing static panel tests**

Create `src/pet-core/CompanionPreferencesPanel.test.tsx`:

```tsx
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import { CompanionPreferencesPanel } from "./CompanionPreferencesPanel";

describe("CompanionPreferencesPanel", () => {
  test("renders saved preferences and delete buttons", () => {
    const html = renderToStaticMarkup(
      <CompanionPreferencesPanel
        preferences={[
          {
            id: "global.nickname",
            scope: "global",
            category: "userProfile",
            key: "nickname",
            value: "阿星",
            source: "explicit",
          },
        ]}
        onClose={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(html).toContain("记忆偏好");
    expect(html).toContain("阿星");
    expect(html).toContain("删除");
  });
});
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
npm test -- src/pet-core/CompanionPreferencesPanel.test.tsx
```

Expected: FAIL because `CompanionPreferencesPanel.tsx` does not exist.

- [ ] **Step 3: Implement the panel**

Create `src/pet-core/CompanionPreferencesPanel.tsx`:

```tsx
import type { CompanionPreference } from "./companionPreferences";

type CompanionPreferencesPanelProps = {
  preferences: CompanionPreference[];
  onClose: () => void;
  onDelete: (id: string) => void;
};

export function CompanionPreferencesPanel({
  preferences,
  onClose,
  onDelete,
}: CompanionPreferencesPanelProps) {
  return (
    <section className="companion-preferences-panel" role="dialog" aria-modal="true">
      <header>
        <h2>记忆偏好</h2>
        <button type="button" aria-label="关闭记忆偏好" onClick={onClose}>
          ×
        </button>
      </header>
      <div className="companion-preferences-list">
        {preferences.length === 0 ? (
          <p>还没有记住偏好。</p>
        ) : (
          preferences.map((preference) => (
            <div className="companion-preference-row" key={preference.id}>
              <span>{preference.value}</span>
              <button type="button" onClick={() => onDelete(preference.id)}>
                删除
              </button>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Add panel state and render path in `App.tsx`**

Add state:

```ts
const [isPreferencesOpen, setIsPreferencesOpen] = useState(false);
const [, forcePreferencesRender] = useState(0);
```

Add delete handler:

```ts
const deleteCompanionPreference = (id: string) => {
  const nextPreferences = {
    preferences: companionPreferencesRef.current.preferences.filter(
      (preference) => preference.id !== id,
    ),
    recentPreferenceId:
      companionPreferencesRef.current.recentPreferenceId === id
        ? null
        : companionPreferencesRef.current.recentPreferenceId,
  };
  companionPreferencesRef.current = nextPreferences;
  writeCompanionPreferences(nextPreferences);
  forcePreferencesRender((value) => value + 1);
};
```

Render inside platform panel actions near mailbox:

```tsx
<button
  className="platform-memory-button"
  type="button"
  aria-label="打开记忆偏好"
  onClick={() => setIsPreferencesOpen(true)}
  onPointerDown={stopPlatformEvent}
>
  记忆
</button>
```

Render panel:

```tsx
{isPreferencesOpen && (
  <CompanionPreferencesPanel
    preferences={companionPreferencesRef.current.preferences}
    onClose={() => setIsPreferencesOpen(false)}
    onDelete={deleteCompanionPreference}
  />
)}
```

- [ ] **Step 5: Add minimal panel CSS**

Append to `src/App.css`:

```css
.companion-preferences-panel {
  position: absolute;
  right: 18px;
  top: 64px;
  width: 260px;
  max-height: 320px;
  overflow: auto;
  border-radius: 8px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 14px 36px rgba(46, 34, 26, 0.18);
  z-index: 8;
}

.companion-preferences-panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.companion-preferences-list {
  display: grid;
  gap: 8px;
}

.companion-preference-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
}
```

- [ ] **Step 6: Run panel tests**

Run:

```powershell
npm test -- src/pet-core/CompanionPreferencesPanel.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit Task 7**

Run:

```powershell
git add src/pet-core/CompanionPreferencesPanel.tsx src/pet-core/CompanionPreferencesPanel.test.tsx src/App.tsx src/App.css
git commit -m "feat: add companion preference panel"
```

Expected: commit succeeds.

---

### Task 8: Final Verification

**Files:**
- Modify only files required to fix verification failures from this task.

- [ ] **Step 1: Run all tests**

Run:

```powershell
npm test
```

Expected: all Vitest tests pass.

- [ ] **Step 2: Run production build**

Run:

```powershell
npm run build
```

Expected: TypeScript and Vite build complete without errors.

- [ ] **Step 3: Run Tauri Rust checks**

Run:

```powershell
Set-Location src-tauri
cargo test
cargo check
Set-Location ..
```

Expected: Rust tests and checks pass.

- [ ] **Step 4: Manual browser preview smoke check**

Run:

```powershell
npm run dev
```

Expected: Vite prints a localhost URL. Open the URL and verify:

- Pet renders.
- Right-click single click does not open a browser context menu.
- Right-click double-click opens chat.
- Opener bubble shows a pet-specific onomatopoeia.
- Input sends a user bubble and a pet reply.
- Left-click pet during pending reply restores the sent text to the input.
- `Esc` closes chat.
- Platform still opens.
- Memory panel opens and can delete a saved preference.

- [ ] **Step 5: Commit verification fixes**

If verification required fixes, run:

```powershell
git add src public
git commit -m "fix: stabilize companion chat verification"
```

Expected: commit succeeds when fixes were made. If no files changed, skip this commit.

---

## Plan Self-Review

- Spec coverage: Tasks cover right-click double-click chat entry, single right-click menu suppression, pet-specific opener cues, optional opener sound playback, bounded bubble flow, stable input row, stop/undo, Esc/outside/idle exit, local provider, preference extraction, preference storage, health care-preference boundary, preference management, pet package config, and update-check handoff.
- Red-flag scan: The plan contains concrete file paths, focused commands, expected results, and code blocks for each code-changing task.
- Type consistency: `CompanionChatConfig`, `CompanionChatPackage`, `CompanionChatState`, `CompanionPreference`, and `PetManifest.companionChatPath` are introduced before later tasks reference them.
