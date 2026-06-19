# DS Dialogue Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give DS an isolated seven-event dialogue package so its idle, click, care, meal, and sleep bubbles never fall back to xiaoju copy.

**Architecture:** Store DS copy in `public/pets/ds/dialogues.json` and expose it through an optional `dialoguesPath` manifest field. Add a focused `src/pet-core/dialogue.ts` loader/resolver that distinguishes unconfigured pets from configured-but-failed packages; wire the existing interaction triggers in `App.tsx` through that resolver while preserving current animation and timing behavior.

**Tech Stack:** React 19, TypeScript 5.8, Vite 7, Vitest 4, Tauri 2 asset loading.

---

## Working Tree Safeguard

The current checkout already contains unrelated uncommitted changes, including changes in
`src/App.tsx`. Before every edit to that file:

1. Re-read the current relevant sections.
2. Apply narrow hunks only; never replace the whole file.
3. Do not revert or reformat unrelated window-layout work.
4. Stage only task-owned files. Do not commit `src/App.tsx` from this dirty checkout unless
   the staged diff has been inspected and contains no unrelated hunks.

## File Map

- Create `public/pets/ds/dialogues.json`: owns the seven approved DS lines.
- Modify `public/pets/ds/pet.json`: declares `dialoguesPath`.
- Modify `src/pet-core/petAssets.ts`: adds the optional manifest field.
- Modify `src/pet-core/petAssets.test.ts`: validates DS package isolation and exact content.
- Create `src/pet-core/dialogue.ts`: owns event types, loading, strict fallback behavior, and time-to-event mapping.
- Create `src/pet-core/dialogue.test.ts`: tests URL resolution, failures, missing keys, timing, and forbidden xiaoju text.
- Modify `src/pet-core/interaction.ts`: removes covered DS copy from action definitions while retaining animations and sounds.
- Modify `src/pet-core/interaction.test.ts`: verifies DS actions no longer embed covered dialogue.
- Modify `src/App.tsx`: loads dialogue packages and connects existing triggers to event keys.

### Task 1: Add The DS Dialogue Package Contract

**Files:**
- Create: `public/pets/ds/dialogues.json`
- Modify: `public/pets/ds/pet.json`
- Modify: `src/pet-core/petAssets.ts:14-26`
- Modify: `src/pet-core/petAssets.test.ts:1-20,107-120`

- [ ] **Step 1: Write the failing package test**

Add the JSON import:

```ts
import dsDialogues from "../../public/pets/ds/dialogues.json";
```

Extend the existing DS package test:

```ts
expect(dsManifest.dialoguesPath).toBe("dialogues.json");
expect(resolvePetAssetUrl("ds", dsManifest.dialoguesPath)).toBe(
  "/pets/ds/dialogues.json",
);
expect(dsDialogues).toEqual({
  idle: "慢慢来，我们一起向前游一点。",
  singleClick: "贴贴一下，我们一起加油吧。",
  doubleClick: "摆摆尾巴，我们一起向前冲一小步！",
  water: "去喝杯水吧，回来后我们再一起继续努力。",
  eyeCare: "看看远处，放松一下眼睛吧，休息好再一起继续。",
  meal: "到吃饭时间啦，先补充能量，回来后我们继续努力。",
  sleep: "今天已经很努力啦，早点休息吧，明天我们再一起出发。",
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
npm test -- src/pet-core/petAssets.test.ts
```

Expected: FAIL because `public/pets/ds/dialogues.json` and `dialoguesPath` do not exist.

- [ ] **Step 3: Add the manifest type and package files**

Add to `PetManifest`:

```ts
dialoguesPath?: string;
```

Add to `public/pets/ds/pet.json`:

```json
"dialoguesPath": "dialogues.json"
```

Create `public/pets/ds/dialogues.json`:

```json
{
  "idle": "慢慢来，我们一起向前游一点。",
  "singleClick": "贴贴一下，我们一起加油吧。",
  "doubleClick": "摆摆尾巴，我们一起向前冲一小步！",
  "water": "去喝杯水吧，回来后我们再一起继续努力。",
  "eyeCare": "看看远处，放松一下眼睛吧，休息好再一起继续。",
  "meal": "到吃饭时间啦，先补充能量，回来后我们继续努力。",
  "sleep": "今天已经很努力啦，早点休息吧，明天我们再一起出发。"
}
```

- [ ] **Step 4: Run the package test**

Run:

```powershell
npm test -- src/pet-core/petAssets.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit the isolated package change**

Only in a clean or isolated execution tree:

```powershell
git add -- public/pets/ds/dialogues.json public/pets/ds/pet.json src/pet-core/petAssets.ts src/pet-core/petAssets.test.ts
git diff --cached --check
git commit -m "feat: add ds dialogue package"
```

### Task 2: Build The Dialogue Loader And Resolver

**Files:**
- Create: `src/pet-core/dialogue.ts`
- Create: `src/pet-core/dialogue.test.ts`

- [ ] **Step 1: Write failing loader and resolver tests**

Create `src/pet-core/dialogue.test.ts`:

```ts
import { describe, expect, test, vi } from "vitest";
import dsDialogues from "../../public/pets/ds/dialogues.json";
import dsManifest from "../../public/pets/ds/pet.json";
import {
  getTimedPetDialogueEvent,
  loadPetDialoguePackage,
  resolvePetDialogue,
  type PetDialoguePackage,
} from "./dialogue";
import type { PetManifest } from "./petAssets";

const xiaojuManifest: PetManifest = {
  id: "xiaoju-cat",
  displayName: "小橘",
  description: "test",
  spritesheetPath: "spritesheet.webp",
};

describe("pet dialogue packages", () => {
  test("loads configured dialogue files from the active pet package", async () => {
    const fetchDialogue = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => dsDialogues,
    }));

    const result = await loadPetDialoguePackage(dsManifest, fetchDialogue);

    expect(fetchDialogue).toHaveBeenCalledWith("/pets/ds/dialogues.json");
    expect(result).toEqual({
      status: "loaded",
      petId: "ds",
      dialogues: dsDialogues,
    });
  });

  test("keeps fallback copy only for pets without a dialogue package", async () => {
    const fetchDialogue = vi.fn();
    const result = await loadPetDialoguePackage(xiaojuManifest, fetchDialogue);

    expect(fetchDialogue).not.toHaveBeenCalled();
    expect(resolvePetDialogue(result, "idle", "legacy fallback")).toBe(
      "legacy fallback",
    );
  });

  test("does not cross-pet fallback when a configured package fails", async () => {
    const warn = vi.fn();
    const result = await loadPetDialoguePackage(
      dsManifest,
      async () => ({ ok: false, status: 404, json: async () => ({}) }),
      warn,
    );

    expect(result).toEqual({ status: "failed", petId: "ds" });
    expect(resolvePetDialogue(result, "idle", "小橘 fallback", warn)).toBeNull();
    expect(warn).toHaveBeenCalled();
  });

  test("treats invalid json shapes as a failed configured package", async () => {
    const warn = vi.fn();
    const result = await loadPetDialoguePackage(
      dsManifest,
      async () => ({ ok: true, status: 200, json: async () => [] }),
      warn,
    );

    expect(result).toEqual({ status: "failed", petId: "ds" });
    expect(resolvePetDialogue(result, "idle", "fallback", warn)).toBeNull();
    expect(warn).toHaveBeenCalled();
  });

  test("returns no bubble for a missing or empty configured event", () => {
    const warn = vi.fn();
    const dialoguePackage: PetDialoguePackage = {
      status: "loaded",
      petId: "ds",
      dialogues: { idle: "  " },
    };

    expect(resolvePetDialogue(dialoguePackage, "idle", "fallback", warn)).toBeNull();
    expect(
      resolvePetDialogue(dialoguePackage, "singleClick", "fallback", warn),
    ).toBeNull();
    expect(warn).toHaveBeenCalledTimes(2);
  });

  test("maps existing meal and sleep hours without adding timers", () => {
    for (const hour of [7, 8, 11, 12, 18, 19]) {
      expect(getTimedPetDialogueEvent(hour)).toBe("meal");
    }
    for (const hour of [23, 0, 1, 5]) {
      expect(getTimedPetDialogueEvent(hour)).toBe("sleep");
    }
    for (const hour of [6, 9, 13, 14, 20, 22]) {
      expect(getTimedPetDialogueEvent(hour)).toBe("idle");
    }
  });

  test("keeps all approved ds lines free of xiaoju copy", () => {
    const combined = Object.values(dsDialogues).join("\n");

    expect(combined).not.toMatch(/小橘|喵|鱼！|吃到了。/);
    expect(Object.keys(dsDialogues).sort()).toEqual(
      [
        "doubleClick",
        "eyeCare",
        "idle",
        "meal",
        "singleClick",
        "sleep",
        "water",
      ].sort(),
    );
  });
});
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:

```powershell
npm test -- src/pet-core/dialogue.test.ts
```

Expected: FAIL because `src/pet-core/dialogue.ts` does not exist.

- [ ] **Step 3: Implement the loader and resolver**

Create `src/pet-core/dialogue.ts`:

```ts
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
```

- [ ] **Step 4: Run the dialogue tests**

Run:

```powershell
npm test -- src/pet-core/dialogue.test.ts
```

Expected: PASS with 7 tests.

- [ ] **Step 5: Commit the runtime module**

Only in a clean or isolated execution tree:

```powershell
git add -- src/pet-core/dialogue.ts src/pet-core/dialogue.test.ts
git diff --cached --check
git commit -m "feat: load pet dialogue packages"
```

### Task 3: Route Existing DS Triggers Through The Package

**Files:**
- Modify: `src/pet-core/interaction.ts:69-85,221-261,286-341`
- Modify: `src/pet-core/interaction.test.ts:149-230`
- Modify: `src/App.tsx:28-91,286-303,376-431,535-575,593-615,654-689,951-1000,1312-1315`

- [ ] **Step 1: Update interaction tests to reject embedded covered DS copy**

Change the DS single-click expectation to:

```ts
expect(getPetClickAction("ds", 1)).toEqual({
  animation: "tickle",
  sound: "tickle",
  durationMs: 1200,
});
```

Change the DS care expectation to:

```ts
expect(getPetCareReminderAction("ds")).toEqual({
  animation: "gnawFish",
  sound: "care_reminder",
  durationMs: 3200,
});
```

For each DS idle quirk, assert that it has no `text` property:

```ts
for (const action of getPetIdleQuirkActions("ds")) {
  expect(action).not.toHaveProperty("text");
}
```

Keep the existing animation, sound, and duration assertions.

- [ ] **Step 2: Run interaction tests to verify they fail**

Run:

```powershell
npm test -- src/pet-core/interaction.test.ts
```

Expected: FAIL because DS actions still contain the old embedded text.

- [ ] **Step 3: Remove covered DS copy from interaction action definitions**

Make text optional:

```ts
export type PetInteractionAction = {
  animation: RuntimeAnimationName;
  sound: RuntimeSoundEvent;
  bubbleText?: string;
  durationMs?: number;
};

export type PetIdleQuirkAction = {
  text?: string;
  animation: RuntimeAnimationName;
  sound: RuntimeSoundEvent;
  duration: number;
};
```

Remove `bubbleText` from DS single-click and care actions. Remove `text` from each DS idle
quirk object. Keep their current animation, sound, and duration values unchanged.

- [ ] **Step 4: Add dialogue package state and loading to `App.tsx`**

Import:

```ts
import {
  getTimedPetDialogueEvent,
  loadPetDialoguePackage,
  resolvePetDialogue,
  type PetDialogueEvent,
  type PetDialoguePackage,
} from "./pet-core/dialogue";
```

Change bubble state and add package state:

```ts
const [bubbleText, setBubbleText] = useState<string | null>(
  getTimedDefaultBubble(),
);
const [petDialoguesById, setPetDialoguesById] = useState<
  Record<string, PetDialoguePackage>
>({});
```

After loading manifests, load each package before exposing the catalog:

```ts
const dialogueEntries = await Promise.all(
  manifestEntries.map(async ([petId, manifest]) => [
    petId,
    await loadPetDialoguePackage(manifest),
  ] as const),
);

if (disposed) return;
setAvailablePetIds(petIds);
setPetManifestsById(manifests);
setPetDialoguesById(Object.fromEntries(dialogueEntries));
setActivePetId(initialPetId);
```

Do not fetch dialogue files in the pet-selection handler. Publishing manifests and dialogue
packages together after `Promise.all` means a later pet switch reads an already keyed package
and an older asynchronous result cannot overwrite the active pet's dialogue.

In the default-manifest catch branch, also call `loadPetDialoguePackage(fallbackManifest)`
and store it under `DEFAULT_PET_ID`.

- [ ] **Step 5: Add strict per-pet resolution helpers**

Inside `DesktopPetApp`, add:

```ts
const getDialoguePackageForPet = (petId: string): PetDialoguePackage => {
  const loaded = petDialoguesById[petId];
  if (loaded) return loaded;

  return petManifestsById[petId]?.dialoguesPath
    ? { status: "failed", petId }
    : { status: "not-configured", petId };
};

const getBubbleTextForPet = (
  petId: string,
  event: PetDialogueEvent,
  fallbackText: string | null,
) =>
  resolvePetDialogue(
    getDialoguePackageForPet(petId),
    event,
    fallbackText,
  );

const getDefaultBubbleTextForPet = (petId: string) =>
  getBubbleTextForPet(
    petId,
    getTimedPetDialogueEvent(new Date().getHours()),
    getPetIdleBubbleText(petId, getTimedDefaultBubble()),
  );
```

Update the active-pet effect to depend on dialogue state:

```ts
useEffect(() => {
  setBubbleText(getDefaultBubbleTextForPet(activePetId));
}, [activePetId, petDialoguesById]);
```

Update `selectPet` and `getDefaultBubbleText()` to use `getDefaultBubbleTextForPet`.

- [ ] **Step 6: Connect single click, double click, and hover sequence**

Allow an optional event override:

```ts
const playInteractionAction = (
  action: PetInteractionAction,
  dialogueEvent?: PetDialogueEvent,
) => {
  setBubbleText(
    dialogueEvent
      ? getBubbleTextForPet(
          activePetId,
          dialogueEvent,
          action.bubbleText ?? null,
        )
      : action.bubbleText ?? null,
  );
  playPetSound(action.sound);
  playAnimation(action.animation, action.durationMs);
};
```

For single click:

```ts
playInteractionAction(clickAction, currentCount === 1 ? "singleClick" : undefined);
```

In `playHoverFishSequence`, resolve `doubleClick` separately for both legacy phases:

```ts
setBubbleText(
  getBubbleTextForPet(activePetId, "doubleClick", "鱼！"),
);
```

Then:

```ts
setBubbleText(
  getBubbleTextForPet(activePetId, "doubleClick", "吃到了。"),
);
```

Configured DS therefore displays the same approved line through both animation phases.
Unconfigured pets retain their current two-phase copy. A failed configured package displays
no bubble.

- [ ] **Step 7: Connect care and idle triggers**

For eye care:

```ts
playInteractionAction(careAction, "eyeCare");
```

For water:

```ts
playInteractionAction(careAction, "water");
```

For idle quirks:

```ts
setBubbleText(
  getBubbleTextForPet(activePetId, "idle", chosen.text ?? null),
);
```

The existing animation choice, sound, reminder intervals, and durations remain unchanged.
Meal and sleep use `getTimedPetDialogueEvent()` whenever the default bubble is restored;
no new timer is introduced.

- [ ] **Step 8: Hide the bubble when strict resolution returns no text**

Change rendering to:

```tsx
{bubbleText && <div className="bubble">{bubbleText}</div>}
```

- [ ] **Step 9: Run focused tests and build**

Run:

```powershell
npm test -- src/pet-core/petAssets.test.ts src/pet-core/dialogue.test.ts src/pet-core/interaction.test.ts
npm run build
```

Expected: all focused tests PASS and TypeScript/Vite build succeeds.

- [ ] **Step 10: Inspect the overlapping `App.tsx` diff**

Run:

```powershell
git diff -- src/App.tsx
git diff --check
```

Expected:

- Existing monitor/window-layout changes are still present and unchanged.
- New hunks only add dialogue loading and event routing.
- No whitespace errors.

- [ ] **Step 11: Commit only if unrelated `App.tsx` hunks can be excluded**

In an isolated worktree, commit normally:

```powershell
git add -- src/App.tsx src/pet-core/interaction.ts src/pet-core/interaction.test.ts
git diff --cached --check
git commit -m "feat: route ds bubbles through dialogue package"
```

In the current dirty checkout, do not stage the whole `src/App.tsx` if doing so would include
pre-existing window-layout changes. Leave the implementation uncommitted and report that
constraint instead of capturing unrelated work.

### Task 4: Full Regression Verification

**Files:**
- Verify only; no planned source changes.

- [ ] **Step 1: Run the complete frontend test suite**

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

Expected: TypeScript compilation and Vite production build succeed.

- [ ] **Step 3: Verify package isolation and forbidden copy**

Run:

```powershell
rg -n '"dialoguesPath"|"singleClick"|"doubleClick"|"eyeCare"|"meal"|"sleep"' public/pets/ds src/pet-core
rg -n '小橘|喵|鱼！|吃到了。' public/pets/ds/dialogues.json
```

Expected:

- The first command finds the DS package and runtime contract.
- The second command returns no matches.
- Switching between `xiaoju-cat`, `ikun`, and `ds` only selects entries keyed by that pet id;
  no per-switch fetch remains that could publish stale copy.

- [ ] **Step 4: Review final scope**

Run:

```powershell
git status --short
git diff --stat
git diff --check
```

Expected:

- DS dialogue changes are limited to the files listed in this plan.
- Pre-existing ikun, Tauri, release, package, and window-layout changes remain intact.
- No generated installers, spritesheets, or unrelated assets were changed by this task.
