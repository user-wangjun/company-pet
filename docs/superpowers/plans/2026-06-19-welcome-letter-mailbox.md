# Welcome Letter Mailbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent platform mailbox with a first-use official welcome letter, the approved envelope/letter animations, bulk read/delete operations, and a permanent welcome letter that future update notices can share.

**Architecture:** Keep letter data, persistence, filtering, and deletion protection in a pure `platform-mail/mailbox.ts` domain module. Keep animation sequencing in a pure `letterExperience.ts` state machine, render the mailbox and reader as focused React components, and limit `App.tsx` to orchestration and callbacks. Use CSS-only envelope artwork and transitions; no pet package or generated image assets are added.

**Tech Stack:** React 19, TypeScript 5.8, CSS animations, Vitest 4, React server rendering tests, browser `localStorage`.

---

## Working Tree Safeguard

The current checkout contains unrelated uncommitted work in `src/App.tsx`,
`src/pet-core/platform.ts`, package version files, Tauri files, ikun assets, and release
installers.

Before every edit:

1. Run `git status --short` and re-read the target section.
2. Use narrow patches only; never replace `src/App.tsx`.
3. Do not modify `package.json` or `package-lock.json`; this plan requires no new package.
4. Never stage `.superpowers/`, `releases/`, pet assets, Tauri files, or unrelated platform
   and dialogue hunks.
5. New mailbox files and the currently clean `src/App.css` may be committed normally.
6. For `src/App.tsx`, stage with `git add -p` only after inspecting every hunk. If the mailbox
   hunks cannot be isolated from pre-existing changes, leave the integration uncommitted and
   report the constraint.

The approved visual prototype used an `860 × 590` platform surface. Formal implementation
must change the `PLATFORM_WINDOW_SIZE` value in `src/App.tsx` from `680 × 520` to
`860 × 590`; this is necessary to preserve the approved 780-pixel letter width and readable
22-pixel text without scrolling.

## File Map

- Create `src/platform-mail/mailbox.ts`: letter catalog, state normalization, persistence,
  read/delete operations, unread count, and permanent-letter protection.
- Create `src/platform-mail/mailbox.test.ts`: domain and storage tests.
- Create `src/platform-mail/letterExperience.ts`: deterministic opening/closing phase
  transitions and reduced-motion durations.
- Create `src/platform-mail/letterExperience.test.ts`: phase and timing tests.
- Create `src/platform-mail/MailboxPanel.tsx`: mailbox trigger/list/bulk-action UI.
- Create `src/platform-mail/LetterReader.tsx`: first-use envelope, letter reader, focus,
  Escape handling, timers, and flight-vector calculation.
- Create `src/platform-mail/mailboxComponents.test.tsx`: server-rendered structural and
  accessibility tests for both React components.
- Modify `src/App.css`: production mailbox, envelope, paper, typography, and animation styles.
- Modify `src/App.tsx`: state orchestration, platform header integration, persistence callbacks,
  and platform size.

### Task 1: Build The Letter Catalog And Persistent Mailbox State

**Files:**
- Create: `src/platform-mail/mailbox.ts`
- Create: `src/platform-mail/mailbox.test.ts`

- [ ] **Step 1: Write the failing mailbox domain tests**

Create `src/platform-mail/mailbox.test.ts`:

```ts
import { describe, expect, test, vi } from "vitest";
import {
  BUILT_IN_LETTERS,
  EMPTY_MAILBOX_STATE,
  MAILBOX_STORAGE_KEY,
  WELCOME_LETTER_ID,
  deleteReadLetters,
  getUnreadCount,
  getVisibleLetters,
  isLetterRead,
  markAllLettersRead,
  markLetterRead,
  parseMailboxState,
  readMailboxState,
  shouldShowFirstUseLetter,
  writeMailboxState,
  type MailboxState,
  type MailboxStorage,
  type PlatformLetter,
} from "./mailbox";

const updateLetter: PlatformLetter = {
  id: "update-0.1.3",
  title: "0.1.3 更新公告",
  sender: "望星科技 × 知了",
  publishedAt: "2026-06-20",
  type: "update",
  paragraphs: ["更新内容。"],
  permanent: false,
};

function createStorage(initialValue: string | null = null): MailboxStorage {
  let value = initialValue;

  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((_key, nextValue) => {
      value = nextValue;
    }),
  };
}

describe("platform mailbox", () => {
  test("ships the approved permanent welcome letter", () => {
    expect(MAILBOX_STORAGE_KEY).toBe("yuxin-mailbox-state-v1");
    expect(WELCOME_LETTER_ID).toBe("welcome-first-meeting");
    expect(BUILT_IN_LETTERS).toEqual([
      {
        id: WELCOME_LETTER_ID,
        title: "致初次相遇的您",
        sender: "望星科技 × 知了",
        publishedAt: "2026-06-19",
        type: "welcome",
        permanent: true,
        paragraphs: [
          "亲爱的用户：",
          "您好！很高兴您可以使用我们的产品。",
          "城市的霓虹伴随着繁华，但是繁复的灯光总是晃眼的，如果您累了，不妨与我们的桌宠嬉戏一下。或许他/她/它不能给您缓解身体的疲劳，但是我们希望，您在某一个瞬间看到我们桌宠的时候，也会噗嗤一笑。所以，来领养一只桌宠吧！希望我们的桌宠能够治愈您的心灵。",
          "生活很累，但也很甜，希望您身体健康，万事如意，平安喜乐。",
        ],
      },
    ]);
  });

  test("keeps first use active until the welcome letter is opened", () => {
    expect(shouldShowFirstUseLetter(EMPTY_MAILBOX_STATE)).toBe(true);

    const readState = markLetterRead(EMPTY_MAILBOX_STATE, WELCOME_LETTER_ID);

    expect(isLetterRead(readState, WELCOME_LETTER_ID)).toBe(true);
    expect(shouldShowFirstUseLetter(readState)).toBe(false);
  });

  test("marks all visible letters read without duplicating ids", () => {
    const letters = [...BUILT_IN_LETTERS, updateLetter];
    const result = markAllLettersRead(
      { readLetterIds: [WELCOME_LETTER_ID], deletedLetterIds: [] },
      letters,
    );

    expect(result.readLetterIds).toEqual([WELCOME_LETTER_ID, updateLetter.id]);
    expect(getUnreadCount(letters, result)).toBe(0);
  });

  test("deletes only read non-permanent letters", () => {
    const letters = [...BUILT_IN_LETTERS, updateLetter];
    const state: MailboxState = {
      readLetterIds: [WELCOME_LETTER_ID, updateLetter.id],
      deletedLetterIds: [],
    };
    const result = deleteReadLetters(state, letters);

    expect(result.deletedLetterIds).toEqual([updateLetter.id]);
    expect(getVisibleLetters(letters, result)).toEqual(BUILT_IN_LETTERS);
    expect(getVisibleLetters(letters, result)).toContainEqual(
      expect.objectContaining({ id: WELCOME_LETTER_ID }),
    );
  });

  test("repairs invalid storage and removes permanent ids from deleted state", () => {
    expect(parseMailboxState("not-json")).toEqual(EMPTY_MAILBOX_STATE);
    expect(
      parseMailboxState(
        JSON.stringify({
          readLetterIds: [WELCOME_LETTER_ID, 3, WELCOME_LETTER_ID],
          deletedLetterIds: [WELCOME_LETTER_ID, updateLetter.id, null],
        }),
      ),
    ).toEqual({
      readLetterIds: [WELCOME_LETTER_ID],
      deletedLetterIds: [updateLetter.id],
    });
  });

  test("reads and writes through the versioned storage key", () => {
    const storage = createStorage(
      JSON.stringify({
        readLetterIds: [WELCOME_LETTER_ID],
        deletedLetterIds: [],
      }),
    );
    const warn = vi.fn();
    const state = readMailboxState(storage, warn);

    expect(storage.getItem).toHaveBeenCalledWith(MAILBOX_STORAGE_KEY);
    expect(state.readLetterIds).toEqual([WELCOME_LETTER_ID]);
    expect(writeMailboxState(state, storage, warn)).toBe(true);
    expect(storage.setItem).toHaveBeenCalledWith(
      MAILBOX_STORAGE_KEY,
      JSON.stringify(state),
    );
    expect(warn).not.toHaveBeenCalled();
  });

  test("falls back in memory when storage throws", () => {
    const storage: MailboxStorage = {
      getItem: vi.fn(() => {
        throw new Error("blocked");
      }),
      setItem: vi.fn(() => {
        throw new Error("blocked");
      }),
    };
    const warn = vi.fn();

    expect(readMailboxState(storage, warn)).toEqual(EMPTY_MAILBOX_STATE);
    expect(writeMailboxState(EMPTY_MAILBOX_STATE, storage, warn)).toBe(false);
    expect(warn).toHaveBeenCalledTimes(2);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
npm test -- src/platform-mail/mailbox.test.ts
```

Expected: FAIL because `src/platform-mail/mailbox.ts` does not exist.

- [ ] **Step 3: Implement the mailbox domain module**

Create `src/platform-mail/mailbox.ts`:

```ts
export type PlatformLetter = {
  id: string;
  title: string;
  sender: string;
  publishedAt: string;
  type: "welcome" | "update";
  paragraphs: string[];
  permanent: boolean;
};

export type MailboxState = {
  readLetterIds: string[];
  deletedLetterIds: string[];
};

export type MailboxStorage = Pick<Storage, "getItem" | "setItem">;
export type MailboxWarning = (message: string, error?: unknown) => void;

export const MAILBOX_STORAGE_KEY = "yuxin-mailbox-state-v1";
export const WELCOME_LETTER_ID = "welcome-first-meeting";
export const EMPTY_MAILBOX_STATE: MailboxState = {
  readLetterIds: [],
  deletedLetterIds: [],
};

export const BUILT_IN_LETTERS: PlatformLetter[] = [
  {
    id: WELCOME_LETTER_ID,
    title: "致初次相遇的您",
    sender: "望星科技 × 知了",
    publishedAt: "2026-06-19",
    type: "welcome",
    permanent: true,
    paragraphs: [
      "亲爱的用户：",
      "您好！很高兴您可以使用我们的产品。",
      "城市的霓虹伴随着繁华，但是繁复的灯光总是晃眼的，如果您累了，不妨与我们的桌宠嬉戏一下。或许他/她/它不能给您缓解身体的疲劳，但是我们希望，您在某一个瞬间看到我们桌宠的时候，也会噗嗤一笑。所以，来领养一只桌宠吧！希望我们的桌宠能够治愈您的心灵。",
      "生活很累，但也很甜，希望您身体健康，万事如意，平安喜乐。",
    ],
  },
];

function uniqueStrings(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.filter((item): item is string => typeof item === "string"))];
}

function permanentLetterIds(): Set<string> {
  return new Set(
    BUILT_IN_LETTERS.filter((letter) => letter.permanent).map(
      (letter) => letter.id,
    ),
  );
}

function normalizeMailboxState(value: unknown): MailboxState {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return { ...EMPTY_MAILBOX_STATE };
  }

  const record = value as Record<string, unknown>;
  const permanentIds = permanentLetterIds();

  return {
    readLetterIds: uniqueStrings(record.readLetterIds),
    deletedLetterIds: uniqueStrings(record.deletedLetterIds).filter(
      (id) => !permanentIds.has(id),
    ),
  };
}

export function parseMailboxState(raw: string | null): MailboxState {
  if (!raw) return { ...EMPTY_MAILBOX_STATE };

  try {
    return normalizeMailboxState(JSON.parse(raw));
  } catch {
    return { ...EMPTY_MAILBOX_STATE };
  }
}

function browserStorage(): MailboxStorage | null {
  if (typeof window === "undefined") return null;

  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readMailboxState(
  storage: MailboxStorage | null = browserStorage(),
  warn: MailboxWarning = console.warn,
): MailboxState {
  if (!storage) return { ...EMPTY_MAILBOX_STATE };

  try {
    return parseMailboxState(storage.getItem(MAILBOX_STORAGE_KEY));
  } catch (error) {
    warn("[mailbox] Failed to read mailbox state", error);
    return { ...EMPTY_MAILBOX_STATE };
  }
}

export function writeMailboxState(
  state: MailboxState,
  storage: MailboxStorage | null = browserStorage(),
  warn: MailboxWarning = console.warn,
): boolean {
  if (!storage) return false;

  try {
    storage.setItem(
      MAILBOX_STORAGE_KEY,
      JSON.stringify(normalizeMailboxState(state)),
    );
    return true;
  } catch (error) {
    warn("[mailbox] Failed to write mailbox state", error);
    return false;
  }
}

export function isLetterRead(state: MailboxState, letterId: string): boolean {
  return state.readLetterIds.includes(letterId);
}

export function shouldShowFirstUseLetter(state: MailboxState): boolean {
  return !isLetterRead(state, WELCOME_LETTER_ID);
}

export function markLetterRead(
  state: MailboxState,
  letterId: string,
): MailboxState {
  if (state.readLetterIds.includes(letterId)) return state;

  return {
    ...state,
    readLetterIds: [...state.readLetterIds, letterId],
  };
}

export function getVisibleLetters(
  letters: PlatformLetter[],
  state: MailboxState,
): PlatformLetter[] {
  const deletedIds = new Set(state.deletedLetterIds);
  return letters.filter((letter) => letter.permanent || !deletedIds.has(letter.id));
}

export function getUnreadCount(
  letters: PlatformLetter[],
  state: MailboxState,
): number {
  return getVisibleLetters(letters, state).filter(
    (letter) => !isLetterRead(state, letter.id),
  ).length;
}

export function markAllLettersRead(
  state: MailboxState,
  letters: PlatformLetter[],
): MailboxState {
  return getVisibleLetters(letters, state).reduce(
    (nextState, letter) => markLetterRead(nextState, letter.id),
    state,
  );
}

export function deleteReadLetters(
  state: MailboxState,
  letters: PlatformLetter[],
): MailboxState {
  const deletableIds = letters
    .filter(
      (letter) =>
        !letter.permanent &&
        isLetterRead(state, letter.id) &&
        !state.deletedLetterIds.includes(letter.id),
    )
    .map((letter) => letter.id);

  if (deletableIds.length === 0) return state;

  return {
    ...state,
    deletedLetterIds: [...state.deletedLetterIds, ...deletableIds],
  };
}

export function canDeleteReadLetters(
  state: MailboxState,
  letters: PlatformLetter[],
): boolean {
  return letters.some(
    (letter) =>
      !letter.permanent &&
      isLetterRead(state, letter.id) &&
      !state.deletedLetterIds.includes(letter.id),
  );
}
```

- [ ] **Step 4: Run the mailbox test**

Run:

```powershell
npm test -- src/platform-mail/mailbox.test.ts
```

Expected: PASS with 7 tests.

- [ ] **Step 5: Commit the isolated mailbox domain**

```powershell
git add -- src/platform-mail/mailbox.ts src/platform-mail/mailbox.test.ts
git diff --cached --check
git commit -m "feat: add persistent platform mailbox state"
```

### Task 2: Build The Deterministic Letter Animation State Machine

**Files:**
- Create: `src/platform-mail/letterExperience.ts`
- Create: `src/platform-mail/letterExperience.test.ts`

- [ ] **Step 1: Write the failing phase tests**

Create `src/platform-mail/letterExperience.test.ts`:

```ts
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
npm test -- src/platform-mail/letterExperience.test.ts
```

Expected: FAIL because `letterExperience.ts` does not exist.

- [ ] **Step 3: Implement the phase module**

Create `src/platform-mail/letterExperience.ts`:

```ts
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
```

- [ ] **Step 4: Run the phase tests**

Run:

```powershell
npm test -- src/platform-mail/letterExperience.test.ts
```

Expected: PASS with 4 tests.

- [ ] **Step 5: Commit the phase module**

```powershell
git add -- src/platform-mail/letterExperience.ts src/platform-mail/letterExperience.test.ts
git diff --cached --check
git commit -m "feat: define welcome letter animation phases"
```

### Task 3: Add The Mailbox And Letter Reader Components

**Files:**
- Create: `src/platform-mail/MailboxPanel.tsx`
- Create: `src/platform-mail/LetterReader.tsx`
- Create: `src/platform-mail/mailboxComponents.test.tsx`

- [ ] **Step 1: Write the failing server-rendered component tests**

Create `src/platform-mail/mailboxComponents.test.tsx`:

```tsx
import { createRef } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import { LetterReader } from "./LetterReader";
import { MailboxPanel } from "./MailboxPanel";
import {
  BUILT_IN_LETTERS,
  EMPTY_MAILBOX_STATE,
  WELCOME_LETTER_ID,
  markLetterRead,
} from "./mailbox";

const welcomeLetter = BUILT_IN_LETTERS[0];

describe("MailboxPanel", () => {
  test("renders unread status, bulk actions, and permanent protection", () => {
    const html = renderToStaticMarkup(
      <MailboxPanel
        letters={BUILT_IN_LETTERS}
        state={EMPTY_MAILBOX_STATE}
        onClose={vi.fn()}
        onDeleteRead={vi.fn()}
        onMarkAllRead={vi.fn()}
        onOpenLetter={vi.fn()}
      />,
    );

    expect(html).toContain('aria-label="信箱"');
    expect(html).toContain("一键已读");
    expect(html).toContain("删除已读");
    expect(html).toContain("致初次相遇的您");
    expect(html).toContain("永久保留");
    expect(html).toContain("未读");
    expect(html).toContain("disabled");
  });

  test("shows an already-read permanent welcome letter without deleting it", () => {
    const state = markLetterRead(EMPTY_MAILBOX_STATE, WELCOME_LETTER_ID);
    const html = renderToStaticMarkup(
      <MailboxPanel
        letters={BUILT_IN_LETTERS}
        state={state}
        onClose={vi.fn()}
        onDeleteRead={vi.fn()}
        onMarkAllRead={vi.fn()}
        onOpenLetter={vi.fn()}
      />,
    );

    expect(html).toContain("已读");
    expect(html).toContain("永久保留");
  });
});

describe("LetterReader", () => {
  test("renders first use as a sealed clickable envelope", () => {
    const html = renderToStaticMarkup(
      <LetterReader
        letter={welcomeLetter}
        mailboxTargetRef={createRef<HTMLButtonElement>()}
        mode="first-use"
        onRead={vi.fn()}
        onStored={vi.fn()}
      />,
    );

    expect(html).toContain("letter-overlay is-sealed");
    expect(html).toContain("点击任意位置 · 拆开这封信");
    expect(html).toContain("letter-wax-seal");
    expect(html).toContain(">愈<");
  });

  test("renders mailbox reading directly as an accessible open letter", () => {
    const html = renderToStaticMarkup(
      <LetterReader
        letter={welcomeLetter}
        mailboxTargetRef={createRef<HTMLButtonElement>()}
        mode="mailbox"
        onRead={vi.fn()}
        onStored={vi.fn()}
      />,
    );

    expect(html).toContain("letter-overlay is-open");
    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain('aria-label="关闭信件"');
    expect(html).toContain("所以，来领养一只桌宠吧！");
  });
});
```

- [ ] **Step 2: Run the component test to verify it fails**

Run:

```powershell
npm test -- src/platform-mail/mailboxComponents.test.tsx
```

Expected: FAIL because both components do not exist.

- [ ] **Step 3: Implement the mailbox panel**

Create `src/platform-mail/MailboxPanel.tsx`:

```tsx
import {
  canDeleteReadLetters,
  getVisibleLetters,
  isLetterRead,
  type MailboxState,
  type PlatformLetter,
} from "./mailbox";

type MailboxPanelProps = {
  letters: PlatformLetter[];
  state: MailboxState;
  onClose: () => void;
  onDeleteRead: () => void;
  onMarkAllRead: () => void;
  onOpenLetter: (letter: PlatformLetter) => void;
};

export function MailboxPanel({
  letters,
  state,
  onClose,
  onDeleteRead,
  onMarkAllRead,
  onOpenLetter,
}: MailboxPanelProps) {
  const visibleLetters = getVisibleLetters(letters, state);
  const hasUnread = visibleLetters.some(
    (letter) => !isLetterRead(state, letter.id),
  );

  return (
    <div className="mailbox-overlay" onClick={onClose}>
      <section
        className="mailbox-panel"
        role="dialog"
        aria-modal="true"
        aria-label="信箱"
        onClick={(event) => event.stopPropagation()}
        onMouseDown={(event) => event.stopPropagation()}
        onPointerDown={(event) => event.stopPropagation()}
      >
        <header className="mailbox-panel-header">
          <div>
            <p>Yuxin Mailbox</p>
            <h2>信箱</h2>
          </div>
          <button type="button" aria-label="关闭信箱" onClick={onClose}>
            ×
          </button>
        </header>

        <div className="mailbox-toolbar">
          <button type="button" disabled={!hasUnread} onClick={onMarkAllRead}>
            一键已读
          </button>
          <button
            type="button"
            disabled={!canDeleteReadLetters(state, visibleLetters)}
            onClick={onDeleteRead}
          >
            删除已读
          </button>
        </div>

        <div className="mailbox-list">
          {visibleLetters.map((letter) => {
            const read = isLetterRead(state, letter.id);

            return (
              <button
                className={`mailbox-letter-row${read ? " is-read" : ""}`}
                type="button"
                key={letter.id}
                onClick={() => onOpenLetter(letter)}
              >
                <span className="mailbox-letter-icon" aria-hidden="true">
                  {read ? "✉" : "✉"}
                </span>
                <span className="mailbox-letter-copy">
                  <strong>{letter.title}</strong>
                  <span>
                    {letter.sender} · {letter.publishedAt}
                  </span>
                </span>
                <span className="mailbox-letter-meta">
                  <span>{read ? "已读" : "未读"}</span>
                  {letter.permanent && <span>永久保留</span>}
                </span>
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Implement the letter reader**

Create `src/platform-mail/LetterReader.tsx`:

```tsx
import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type RefObject,
} from "react";
import {
  getInitialLetterPhase,
  getLetterPhaseDelay,
  getNextAutomaticLetterPhase,
  type LetterOpenMode,
  type LetterPhase,
} from "./letterExperience";
import type { PlatformLetter } from "./mailbox";

type FlightStyle = CSSProperties & {
  "--letter-flight-x": string;
  "--letter-flight-y": string;
};

type LetterReaderProps = {
  letter: PlatformLetter;
  mailboxTargetRef: RefObject<HTMLButtonElement | null>;
  mode: LetterOpenMode;
  onRead: (letterId: string) => void;
  onStored: () => void;
};

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function LetterReader({
  letter,
  mailboxTargetRef,
  mode,
  onRead,
  onStored,
}: LetterReaderProps) {
  const [phase, setPhase] = useState<LetterPhase>(() =>
    getInitialLetterPhase(mode),
  );
  const [flightStyle, setFlightStyle] = useState<FlightStyle>({
    "--letter-flight-x": "0px",
    "--letter-flight-y": "0px",
  });
  const paperRef = useRef<HTMLElement>(null);
  const envelopeRef = useRef<HTMLDivElement>(null);
  const readReportedRef = useRef(false);
  const onReadRef = useRef(onRead);
  const onStoredRef = useRef(onStored);

  useEffect(() => {
    onReadRef.current = onRead;
    onStoredRef.current = onStored;
  }, [onRead, onStored]);

  useEffect(() => {
    if (phase !== "open" || readReportedRef.current) return;

    readReportedRef.current = true;
    onReadRef.current(letter.id);
    paperRef.current?.focus();
  }, [letter.id, phase]);

  useEffect(() => {
    const nextPhase = getNextAutomaticLetterPhase(phase);
    if (!nextPhase) return;

    if (phase === "sealing") {
      const envelope = envelopeRef.current?.getBoundingClientRect();
      const mailbox = mailboxTargetRef.current?.getBoundingClientRect();

      if (envelope && mailbox) {
        setFlightStyle({
          "--letter-flight-x": `${
            mailbox.left +
            mailbox.width / 2 -
            (envelope.left + envelope.width / 2)
          }px`,
          "--letter-flight-y": `${
            mailbox.top +
            mailbox.height / 2 -
            (envelope.top + envelope.height / 2)
          }px`,
        });
      }
    }

    const timeout = window.setTimeout(() => {
      setPhase(nextPhase);
      if (nextPhase === "stored") onStoredRef.current();
    }, getLetterPhaseDelay(phase, prefersReducedMotion()));

    return () => window.clearTimeout(timeout);
  }, [mailboxTargetRef, phase]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && phase === "open") {
        setPhase("folding");
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [phase]);

  const handleOverlayClick = () => {
    if (phase === "sealed") {
      setPhase("opening");
    } else if (phase === "open") {
      setPhase("folding");
    }
  };

  const closeLetter = () => {
    if (phase === "open") setPhase("folding");
  };

  const handleOverlayKeyDown = (
    event: ReactKeyboardEvent<HTMLDivElement>,
  ) => {
    if (
      phase === "sealed" &&
      (event.key === "Enter" || event.key === " ")
    ) {
      event.preventDefault();
      setPhase("opening");
    }
  };

  return (
    <div
      className={`letter-overlay is-${phase}`}
      onClick={handleOverlayClick}
      onKeyDown={handleOverlayKeyDown}
      role={phase === "sealed" ? "button" : undefined}
      aria-label={phase === "sealed" ? "拆开欢迎信" : undefined}
      tabIndex={phase === "sealed" ? 0 : undefined}
    >
      <div
        className="letter-envelope-stage"
        ref={envelopeRef}
        style={flightStyle}
      >
        <div className="letter-envelope-shadow" />
        <article
          className="letter-paper"
          ref={paperRef}
          role={phase === "sealed" ? undefined : "dialog"}
          aria-modal={phase === "sealed" ? undefined : true}
          aria-hidden={phase === "sealed" ? true : undefined}
          aria-labelledby={`letter-title-${letter.id}`}
          tabIndex={-1}
          onClick={(event) => event.stopPropagation()}
        >
          <button
            className="letter-close"
            type="button"
            aria-label="关闭信件"
            onClick={closeLetter}
          >
            ×
          </button>
          <div className="letter-paper-inner">
            <h2 id={`letter-title-${letter.id}`}>{letter.title}</h2>
            <div className="letter-body">
              {letter.paragraphs.map((paragraph, index) => (
                <p
                  className={index === 0 ? "letter-salutation" : undefined}
                  key={`${letter.id}-${index}`}
                >
                  {paragraph}
                </p>
              ))}
              <div className="letter-signature">{letter.sender}</div>
            </div>
          </div>
        </article>
        <div className="letter-envelope-shell">
          <div className="letter-fold-left" />
          <div className="letter-fold-right" />
          <div className="letter-fold-bottom" />
        </div>
        <div className="letter-envelope-flap" />
        <div className="letter-wax-seal" aria-hidden="true">
          愈
        </div>
      </div>
      {phase === "sealed" && (
        <p className="letter-open-hint">点击任意位置 · 拆开这封信</p>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run the component tests**

Run:

```powershell
npm test -- src/platform-mail/mailboxComponents.test.tsx
```

Expected: PASS with 4 tests.

- [ ] **Step 6: Commit the components**

```powershell
git add -- src/platform-mail/MailboxPanel.tsx src/platform-mail/LetterReader.tsx src/platform-mail/mailboxComponents.test.tsx
git diff --cached --check
git commit -m "feat: add mailbox and letter reader components"
```

### Task 4: Add The Approved Envelope, Paper, And Mailbox Styling

**Files:**
- Modify: `src/App.css`

- [ ] **Step 1: Add a failing static style contract test**

Add the two Node imports at the top of
`src/platform-mail/mailboxComponents.test.tsx`, then append the test:

```tsx
// @ts-expect-error Vitest runs in Node while browser source excludes Node types.
import { readFileSync } from "node:fs";
// @ts-expect-error Vitest runs in Node while browser source excludes Node types.
import { resolve } from "node:path";

test("keeps the approved white envelope and top-insertion animation styles", () => {
  const css = readFileSync(resolve("src/App.css"), "utf8");

  expect(css).toContain(".letter-envelope-shell");
  expect(css).toContain(".letter-wax-seal");
  expect(css).toContain(".letter-overlay.is-folding .letter-paper");
  expect(css).toContain(".letter-overlay.is-inserting .letter-paper");
  expect(css).toContain(".letter-overlay.is-sealing .letter-envelope-flap");
  expect(css).toContain(".letter-overlay.is-flying .letter-envelope-stage");
  expect(css).toContain('"STXingkai", "华文行楷"');
  expect(css).toContain("font-size: 22px");
  expect(css).toContain("font-weight: 400");
  expect(css).not.toContain(".letter-body {\n  font-weight: 700");
});
```

- [ ] **Step 2: Run the style contract test to verify it fails**

Run:

```powershell
npm test -- src/platform-mail/mailboxComponents.test.tsx
```

Expected: FAIL because the production CSS selectors do not exist.

- [ ] **Step 3: Append the mailbox and letter CSS**

Append a dedicated `/* Platform mailbox */` section to `src/App.css`. The block must include
the following complete contracts:

```css
/* Platform mailbox */
.platform-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.platform-mailbox-button {
  position: relative;
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid rgba(38, 70, 66, 0.22);
  border-radius: 8px;
  background: #ffffff;
  color: #243f3a;
  cursor: pointer;
}

.platform-mailbox-button:hover {
  background: #e8f1ed;
}

.platform-mailbox-button.is-receiving {
  animation: mailbox-receive 720ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.platform-mailbox-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  display: grid;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  place-items: center;
  border: 2px solid #f4f7f2;
  border-radius: 999px;
  background: #b63b40;
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
}

@keyframes mailbox-receive {
  0%, 100% { transform: scale(1); }
  30% { transform: scale(1.18) rotate(-7deg); }
  55% { transform: scale(0.94) rotate(4deg); }
  78% { transform: scale(1.06) rotate(-2deg); }
}

.mailbox-overlay,
.letter-overlay {
  position: absolute;
  z-index: 30;
  inset: 0;
  background: rgba(25, 37, 33, 0.66);
  backdrop-filter: blur(4px);
}

.mailbox-overlay {
  display: grid;
  place-items: center;
  padding: 28px;
}

.mailbox-panel {
  width: min(720px, 100%);
  max-height: 100%;
  overflow: hidden;
  border: 1px solid rgba(42, 73, 65, 0.18);
  border-radius: 14px;
  background: #f7faf7;
  box-shadow: 0 24px 64px rgba(25, 43, 37, 0.28);
}

.mailbox-panel-header,
.mailbox-toolbar,
.mailbox-letter-row {
  display: flex;
  align-items: center;
}

.mailbox-panel-header {
  justify-content: space-between;
  padding: 18px 20px 14px;
  border-bottom: 1px solid rgba(47, 78, 70, 0.12);
}

.mailbox-panel-header p,
.mailbox-panel-header h2 {
  margin: 0;
}

.mailbox-panel-header p {
  color: #758780;
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.mailbox-panel-header h2 {
  margin-top: 3px;
  color: #1d3e35;
  font-size: 22px;
}

.mailbox-panel-header button,
.mailbox-toolbar button {
  min-height: 34px;
  border: 1px solid rgba(41, 85, 73, 0.18);
  border-radius: 8px;
  background: #ffffff;
  color: #315f53;
  cursor: pointer;
}

.mailbox-panel-header button {
  width: 34px;
  padding: 0;
  font-size: 21px;
}

.mailbox-toolbar {
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
}

.mailbox-toolbar button {
  padding: 0 12px;
}

.mailbox-toolbar button:disabled {
  opacity: 0.45;
  cursor: default;
}

.mailbox-list {
  display: grid;
  gap: 10px;
  max-height: 360px;
  overflow: auto;
  padding: 0 20px 20px;
}

.mailbox-letter-row {
  width: 100%;
  gap: 14px;
  padding: 15px;
  border: 1px solid rgba(43, 75, 67, 0.13);
  border-radius: 10px;
  background: #ffffff;
  color: #28483f;
  text-align: left;
  cursor: pointer;
}

.mailbox-letter-row:not(.is-read) {
  border-color: rgba(182, 59, 64, 0.28);
  box-shadow: 0 7px 20px rgba(69, 49, 45, 0.08);
}

.mailbox-letter-icon {
  font-size: 24px;
}

.mailbox-letter-copy {
  display: grid;
  flex: 1;
  gap: 4px;
}

.mailbox-letter-copy span,
.mailbox-letter-meta {
  color: #70817b;
  font-size: 12px;
}

.mailbox-letter-meta {
  display: grid;
  gap: 5px;
  justify-items: end;
}

.letter-overlay {
  display: grid;
  place-items: center;
  overflow: hidden;
  cursor: default;
}

.letter-overlay.is-sealed {
  cursor: pointer;
}

.letter-envelope-stage {
  --letter-flight-x: 0px;
  --letter-flight-y: 0px;
  position: relative;
  width: 480px;
  height: 292px;
}

.letter-envelope-shadow {
  position: absolute;
  right: -16px;
  bottom: -15px;
  left: 18px;
  height: 55px;
  border-radius: 50%;
  background: rgba(8, 16, 14, 0.3);
  filter: blur(15px);
}

.letter-envelope-shell {
  position: absolute;
  z-index: 5;
  inset: 0;
  overflow: hidden;
  border: 1px solid rgba(120, 130, 127, 0.16);
  background: linear-gradient(165deg, #fff 0%, #fafbf9 60%, #eef1ee 100%);
  box-shadow: 7px 10px 15px rgba(44, 52, 49, 0.12);
}

.letter-fold-left,
.letter-fold-right,
.letter-fold-bottom {
  position: absolute;
  inset: 0;
}

.letter-fold-left {
  background: linear-gradient(145deg, #fff, #f0f3f0);
  clip-path: polygon(0 12%, 0 100%, 50% 55%);
}

.letter-fold-right {
  background: linear-gradient(215deg, #fff, #eef1ee);
  clip-path: polygon(100% 12%, 100% 100%, 50% 55%);
}

.letter-fold-bottom {
  background: linear-gradient(180deg, #fbfcfa, #edf0ed);
  clip-path: polygon(0 100%, 50% 54%, 100% 100%);
}

.letter-envelope-flap {
  position: absolute;
  z-index: 9;
  top: 0;
  left: 0;
  width: 480px;
  height: 177px;
  transform-origin: top center;
  clip-path: polygon(0 0, 100% 0, 50% 100%);
  background: linear-gradient(175deg, #fff, #f0f3f1);
  filter: drop-shadow(0 9px 7px rgba(65, 75, 72, 0.14));
  backface-visibility: hidden;
}

.letter-wax-seal {
  position: absolute;
  z-index: 13;
  top: 132px;
  left: 50%;
  display: grid;
  width: 64px;
  height: 64px;
  place-items: center;
  transform: translate(-50%, -50%) rotate(-7deg);
  border-radius: 48% 52% 45% 55% / 51% 46% 54% 49%;
  background: radial-gradient(circle, #c64a4b 0 48%, #9c2d34 72%, #761d25 100%);
  box-shadow:
    inset 0 0 0 5px rgba(103, 20, 28, 0.18),
    0 6px 11px rgba(52, 16, 19, 0.3);
  color: #f2bbb0;
  font-family: "STXingkai", "华文行楷", "KaiTi", serif;
  font-size: 25px;
}

.letter-paper {
  position: absolute;
  z-index: 4;
  top: 30px;
  left: 50%;
  width: 420px;
  height: 190px;
  min-height: 0;
  overflow: hidden;
  transform: translateX(-50%) translateY(62px);
  border: 1px solid rgba(107, 107, 96, 0.17);
  border-radius: 3px;
  background: #fffef9;
  color: #2f2a23;
}

.letter-paper-inner {
  padding: 34px 46px 30px;
  opacity: 0;
}

.letter-paper h2,
.letter-body {
  font-family: "STXingkai", "华文行楷", "KaiTi", serif;
  font-weight: 400;
  text-rendering: geometricPrecision;
}

.letter-paper h2 {
  margin: 0 0 24px;
  color: #29251f;
  font-size: 34px;
  text-align: center;
  letter-spacing: 0.1em;
}

.letter-body {
  font-size: 22px;
  line-height: 1.65;
  letter-spacing: 0.025em;
}

.letter-body p {
  margin: 0 0 12px;
  text-indent: 2em;
}

.letter-body .letter-salutation {
  text-indent: 0;
}

.letter-signature {
  margin-top: 20px;
  text-align: right;
}

.letter-close {
  position: absolute;
  top: 12px;
  right: 13px;
  z-index: 2;
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #776d60;
  cursor: pointer;
  font-size: 22px;
}

.letter-open-hint {
  position: absolute;
  bottom: 34px;
  left: 50%;
  margin: 0;
  transform: translateX(-50%);
  color: rgba(255, 255, 255, 0.92);
  font-size: 13px;
  letter-spacing: 0.08em;
}

.letter-overlay.is-opening .letter-wax-seal,
.letter-overlay.is-open .letter-wax-seal,
.letter-overlay.is-folding .letter-wax-seal,
.letter-overlay.is-inserting .letter-wax-seal {
  opacity: 0;
}

.letter-overlay.is-opening .letter-envelope-flap,
.letter-overlay.is-open .letter-envelope-flap,
.letter-overlay.is-folding .letter-envelope-flap,
.letter-overlay.is-inserting .letter-envelope-flap {
  z-index: 2;
  transform: rotateX(180deg);
}

.letter-overlay.is-opening .letter-paper,
.letter-overlay.is-open .letter-paper {
  z-index: 25;
  width: 780px;
  height: 550px;
  transform: translateX(-50%) translateY(-159px);
  box-shadow: 0 12px 28px rgba(31, 34, 30, 0.16);
}

.letter-overlay.is-opening .letter-paper {
  transition:
    width 520ms 260ms,
    height 520ms 260ms,
    transform 720ms 260ms,
    box-shadow 320ms 520ms;
}

.letter-overlay.is-opening .letter-envelope-flap {
  transition: transform 680ms;
}

.letter-overlay.is-opening .letter-paper-inner,
.letter-overlay.is-open .letter-paper-inner {
  opacity: 1;
}

.letter-overlay.is-opening .letter-paper-inner {
  transition: opacity 340ms 760ms;
}

.letter-overlay.is-folding .letter-paper {
  z-index: 25;
  width: 420px;
  height: 190px;
  transform: translateX(-50%) translateY(-225px);
  box-shadow: none;
  transition:
    width 500ms,
    height 500ms,
    transform 500ms,
    box-shadow 180ms;
}

.letter-overlay.is-folding .letter-paper-inner,
.letter-overlay.is-inserting .letter-paper-inner,
.letter-overlay.is-sealing .letter-paper-inner,
.letter-overlay.is-flying .letter-paper-inner {
  opacity: 0;
}

.letter-overlay.is-inserting .letter-paper,
.letter-overlay.is-sealing .letter-paper,
.letter-overlay.is-flying .letter-paper {
  z-index: 4;
  width: 420px;
  height: 190px;
  transform: translateX(-50%) translateY(62px);
  box-shadow: none;
}

.letter-overlay.is-inserting .letter-paper {
  transition: transform 460ms cubic-bezier(0.35, 0, 0.2, 1);
}

.letter-overlay.is-sealing .letter-envelope-flap,
.letter-overlay.is-flying .letter-envelope-flap {
  z-index: 9;
  transform: rotateX(0deg);
  transition: transform 360ms cubic-bezier(0.3, 0.1, 0.2, 1);
}

.letter-overlay.is-sealing .letter-wax-seal,
.letter-overlay.is-flying .letter-wax-seal {
  opacity: 1;
  transition: opacity 220ms 220ms;
}

.letter-overlay.is-flying .letter-envelope-stage {
  animation: letter-fly-to-mailbox 760ms cubic-bezier(0.2, 0.75, 0.18, 1)
    forwards;
}

@keyframes letter-fly-to-mailbox {
  0% {
    transform: translate(0, 0) scale(1) rotate(0deg);
    opacity: 1;
  }
  45% {
    transform:
      translate(
        calc(var(--letter-flight-x) * 0.48),
        calc(var(--letter-flight-y) * 0.38)
      )
      scale(0.72)
      rotate(-4deg);
    opacity: 1;
  }
  100% {
    transform:
      translate(var(--letter-flight-x), var(--letter-flight-y))
      scale(0.07)
      rotate(9deg);
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .letter-paper,
  .letter-envelope-flap,
  .letter-wax-seal,
  .letter-envelope-stage,
  .platform-mailbox-button {
    animation-duration: 30ms !important;
    transition-duration: 30ms !important;
    transition-delay: 0ms !important;
  }
}
```

The shell clips every fold internally. Do not recreate the earlier oversized rotated
`.bottom-fold` element that protruded outside the envelope.

- [ ] **Step 4: Run the component and style tests**

Run:

```powershell
npm test -- src/platform-mail/mailboxComponents.test.tsx
```

Expected: PASS with 5 tests.

- [ ] **Step 5: Commit the clean CSS change**

`src/App.css` is currently clean, so it can be staged normally:

```powershell
git add -- src/App.css src/platform-mail/mailboxComponents.test.tsx
git diff --cached --check
git commit -m "feat: style welcome letter and mailbox"
```

### Task 5: Integrate Mailbox State Into The Platform

**Files:**
- Modify: `src/App.tsx:1-110, 286-330, 532-566, 1385-1455`

- [ ] **Step 1: Re-read and snapshot the overlapping file**

Run:

```powershell
git diff -- src/App.tsx
Get-Content src/App.tsx | Select-Object -First 120
Get-Content src/App.tsx | Select-Object -Skip 280 -First 70
Get-Content src/App.tsx | Select-Object -Skip 520 -First 70
Get-Content src/App.tsx | Select-Object -Skip 1370 -First 120
```

Expected: existing dialogue, animation-row, and window-placement changes are visible and
remain untouched.

- [ ] **Step 2: Add imports and the approved platform size**

Add:

```ts
import { MailboxPanel } from "./platform-mail/MailboxPanel";
import { LetterReader } from "./platform-mail/LetterReader";
import {
  BUILT_IN_LETTERS,
  WELCOME_LETTER_ID,
  deleteReadLetters,
  getUnreadCount,
  markAllLettersRead,
  markLetterRead,
  readMailboxState,
  shouldShowFirstUseLetter,
  writeMailboxState,
  type MailboxState,
  type PlatformLetter,
} from "./platform-mail/mailbox";
import type { LetterOpenMode } from "./platform-mail/letterExperience";
```

Change only this existing constant:

```ts
const PLATFORM_WINDOW_SIZE = { width: 860, height: 590 };
```

Do not change the pet window size.

- [ ] **Step 3: Add mailbox refs and state**

Inside `DesktopPetApp`, with the other refs:

```ts
const mailboxButtonRef = useRef<HTMLButtonElement>(null);
const initialMailboxStateRef = useRef<MailboxState | null>(null);
const initialMailboxState =
  initialMailboxStateRef.current ?? readMailboxState();
initialMailboxStateRef.current = initialMailboxState;
```

With the other `useState` calls:

```ts
const [mailboxState, setMailboxState] = useState<MailboxState>(
  initialMailboxState,
);
const [isMailboxOpen, setIsMailboxOpen] = useState(false);
const [activeLetterId, setActiveLetterId] = useState<string | null>(() =>
  shouldShowFirstUseLetter(initialMailboxState)
    ? WELCOME_LETTER_ID
    : null,
);
const [letterOpenMode, setLetterOpenMode] =
  useState<LetterOpenMode>("first-use");
const [isMailboxReceiving, setIsMailboxReceiving] = useState(false);
```

After state declarations:

```ts
const visibleUnreadCount = getUnreadCount(BUILT_IN_LETTERS, mailboxState);
const activeLetter =
  BUILT_IN_LETTERS.find((letter) => letter.id === activeLetterId) ?? null;
```

- [ ] **Step 4: Add state commit and mailbox callbacks**

Place these helpers near `closePlatform` and `selectPet`:

```ts
const commitMailboxState = (
  update: (state: MailboxState) => MailboxState,
) => {
  setMailboxState((current) => {
    const next = update(current);
    writeMailboxState(next);
    return next;
  });
};

const openMailbox = () => {
  setIsMailboxOpen(true);
  recordInteraction("mailbox_open");
};

const openMailboxLetter = (letter: PlatformLetter) => {
  setIsMailboxOpen(false);
  setLetterOpenMode("mailbox");
  setActiveLetterId(letter.id);
  recordInteraction("mailbox_letter_open");
};

const markMailboxLetterRead = (letterId: string) => {
  commitMailboxState((state) => markLetterRead(state, letterId));
  recordInteraction("mailbox_letter_read");
};

const markMailboxRead = () => {
  commitMailboxState((state) =>
    markAllLettersRead(state, BUILT_IN_LETTERS),
  );
  recordInteraction("mailbox_mark_all_read");
};

const deleteMailboxRead = () => {
  commitMailboxState((state) =>
    deleteReadLetters(state, BUILT_IN_LETTERS),
  );
  recordInteraction("mailbox_delete_read");
};

const finishStoringLetter = () => {
  setActiveLetterId(null);
  setIsMailboxReceiving(true);
  window.setTimeout(() => setIsMailboxReceiving(false), 760);
  recordInteraction("mailbox_letter_stored");
};
```

Do not mark the welcome letter read when the app merely renders the sealed envelope.
`LetterReader` calls `markMailboxLetterRead` only after it reaches the open phase.

- [ ] **Step 5: Add the mailbox button to the platform header**

Replace only the current single close button area with:

```tsx
<div className="platform-header-actions">
  <button
    className={`platform-mailbox-button${
      isMailboxReceiving ? " is-receiving" : ""
    }`}
    ref={mailboxButtonRef}
    type="button"
    aria-label="打开信箱"
    onClick={openMailbox}
    onPointerDown={stopPlatformEvent}
  >
    <span aria-hidden="true">✉</span>
    {visibleUnreadCount > 0 && (
      <span className="platform-mailbox-badge">
        {visibleUnreadCount}
      </span>
    )}
  </button>
  <button
    className="platform-close"
    type="button"
    aria-label="关闭桌宠平台"
    onClick={closePlatform}
    onPointerDown={stopPlatformEvent}
  >
    ×
  </button>
</div>
```

- [ ] **Step 6: Render the mailbox and letter reader above platform content**

Inside `.platform-panel`, after the pet grid and before `</section>`:

```tsx
{isMailboxOpen && (
  <MailboxPanel
    letters={BUILT_IN_LETTERS}
    state={mailboxState}
    onClose={() => setIsMailboxOpen(false)}
    onDeleteRead={deleteMailboxRead}
    onMarkAllRead={markMailboxRead}
    onOpenLetter={openMailboxLetter}
  />
)}

{activeLetter && (
  <LetterReader
    key={`${activeLetter.id}-${letterOpenMode}`}
    letter={activeLetter}
    mailboxTargetRef={mailboxButtonRef}
    mode={letterOpenMode}
    onRead={markMailboxLetterRead}
    onStored={finishStoringLetter}
  />
)}
```

The reader must render after the mailbox panel so it has the higher stacking context when a
list item opens a letter.

- [ ] **Step 7: Build to catch TypeScript and hook errors**

Run:

```powershell
npm run build
```

Expected: TypeScript and Vite build PASS.

- [ ] **Step 8: Run focused tests**

Run:

```powershell
npm test -- src/platform-mail/mailbox.test.ts src/platform-mail/letterExperience.test.ts src/platform-mail/mailboxComponents.test.tsx src/pet-core/platform.test.ts
```

Expected: all focused tests PASS. Existing platform-placement tests remain unchanged because
the platform size constant is local to `App.tsx`.

- [ ] **Step 9: Inspect and selectively stage the integration**

Run:

```powershell
git diff --check
git diff -- src/App.tsx
git status --short
```

Expected mailbox-owned `App.tsx` hunks:

- mailbox imports;
- `PLATFORM_WINDOW_SIZE` change to `860 × 590`;
- mailbox refs and state;
- mailbox callbacks;
- header action group;
- mailbox and reader render blocks.

Existing monitor, dialogue, animation-row, and pet behavior hunks must remain unchanged.

Stage interactively:

```powershell
git add -p -- src/App.tsx
git diff --cached -- src/App.tsx
git diff --cached --check
```

If the staged diff contains any unrelated pre-existing line, unstage `src/App.tsx` with:

```powershell
git restore --staged -- src/App.tsx
```

Leave the integration uncommitted and report the dirty-tree constraint. Do not stage the whole
file to force a commit.

- [ ] **Step 10: Commit only if the staged integration is clean**

```powershell
git commit -m "feat: integrate welcome letter mailbox"
```

Skip this commit when Step 9 cannot isolate task-owned hunks.

### Task 6: Full Regression And Visual Verification

**Files:**
- Verify only; no planned source changes.

- [ ] **Step 1: Run the complete frontend suite**

Run:

```powershell
npm test
```

Expected: all tests PASS.

- [ ] **Step 2: Run the production build**

Run:

```powershell
npm run build
```

Expected: TypeScript compilation and Vite production build PASS.

- [ ] **Step 3: Start the development server**

Run in a persistent hidden process:

```powershell
npm run dev
```

Expected: Vite serves the app on `http://127.0.0.1:1420`.

- [ ] **Step 4: Verify the complete browser flow**

Use the in-app browser and clear only the mailbox key before the first-use pass:

```js
localStorage.removeItem("yuxin-mailbox-state-v1");
location.reload();
```

Verify:

1. Platform opens at the approved larger size.
2. White horizontal envelope is centered.
3. Red “愈” wax seal sits at the flap point.
4. Clicking anywhere on the overlay opens the letter.
5. Paper is centered with 22-pixel normal-weight Xingkai/Kaiti fallback text.
6. The exact approved sentence “所以，来领养一只桌宠吧！” is present.
7. Clicking the paper body does not close it.
8. Clicking outside or pressing the close button starts closing once.
9. Paper folds above the envelope, pauses above the opening, then inserts downward.
10. No paper edge or shadow protrudes after insertion.
11. Flap closes, wax seal returns, and the whole envelope flies into the mailbox button.
12. Mailbox button bounces once.
13. Reloading does not auto-show the now-read welcome letter.
14. Mailbox list still contains the permanent welcome letter.
15. “一键已读” and “删除已读” are disabled when there is nothing actionable.

- [ ] **Step 5: Verify the unread persistence and abandoned-first-use cases**

Run two separate checks:

1. Remove `yuxin-mailbox-state-v1`, reload, and close the platform before opening the sealed
   letter. Reload again. Expected: the sealed welcome letter appears again.
2. Remove the key, reload, open the letter, wait until the paper is visible, and reload without
   closing it. Expected: the welcome letter no longer auto-opens because reaching the readable
   state marked it read.

- [ ] **Step 6: Verify existing desktop-pet behavior**

Check:

- pet cards still select pets;
- platform close button still returns to pet mode;
- platform header still drags the native window outside interactive controls;
- desktop pet bubbles, click actions, sounds, and sprite animations remain functional;
- mailbox overlays do not trigger platform drag;
- no files under `public/pets/`, `src-tauri/`, or `releases/` were changed by this feature.

- [ ] **Step 7: Review final scope**

Run:

```powershell
git status --short
git diff --stat
git diff --check
```

Expected feature files:

```text
src/platform-mail/mailbox.ts
src/platform-mail/mailbox.test.ts
src/platform-mail/letterExperience.ts
src/platform-mail/letterExperience.test.ts
src/platform-mail/MailboxPanel.tsx
src/platform-mail/LetterReader.tsx
src/platform-mail/mailboxComponents.test.tsx
src/App.css
src/App.tsx
```

`.superpowers/` remains untracked and must not be staged. Existing unrelated working-tree
changes remain intact.
