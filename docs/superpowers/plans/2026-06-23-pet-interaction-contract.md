# Desktop Pet Interaction Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every desktop pet follow one tested interaction contract for idle, clicks, directional dragging, care reminders, optional hover and desktop-icon behavior, and confirmation-gated update checks.

**Architecture:** Move pet-specific animation and capability declarations into each pet package, then drive them through a pure priority/token state machine. Keep Pixi, Tauri window movement, timers, and React rendering as adapters in `App.tsx`; isolate version checking, reminder persistence, drag direction, and update-dialog rendering in focused modules that can be tested without a running Tauri window.

**Tech Stack:** React 19, TypeScript, PixiJS 8, Tauri 2, Vitest, Rust, Pillow-based asset QA

---

## File and Responsibility Map

### New shared platform files

- `src/pet-core/petInteractionManifest.ts`
  - Defines animation, action, sequence, drag, reminder, hover, idle-quirk, and desktop-icon manifest types.
  - Validates and resolves the active pet's declarative interaction configuration.
- `src/pet-core/petInteractionManifest.test.ts`
  - Locks all four built-in manifests to the approved contract and capability matrix.
- `src/pet-core/interactionRuntime.ts`
  - Pure priority, interruption, queue, phase, facing, and stale-token state machine.
- `src/pet-core/interactionRuntime.test.ts`
  - Proves priority ordering, one-item deferral, stale completion rejection, and cleanup.
- `src/pet-core/dragDirection.ts`
  - Pure 8-logical-pixel drag direction hysteresis.
- `src/pet-core/dragDirection.test.ts`
  - Covers left, right, vertical movement, jitter, and high-DPI coordinate conversion.
- `src/pet-core/careReminders.ts`
  - Owns care-reminder time slots and persistent meal/sleep delivery keys.
- `src/pet-core/careReminders.test.ts`
  - Covers all slots, persistence repair, restart behavior, and one-item deferred delivery.
- `src/pet-update/updateCheck.ts`
  - Owns semantic-version comparison, GitHub response parsing, request result types, and current-version lookup.
- `src/pet-update/updateCheck.test.ts`
  - Covers newer/equal/older/malformed releases and failed requests.
- `src/pet-update/UpdateDialog.tsx`
  - Accessible confirmation UI for a discovered update.
- `src/pet-update/UpdateDialog.test.tsx`
  - Static markup tests for version, notes, buttons, and dialog semantics.
- `src/pet-core/atlasValidation.test.ts`
  - Reads generated QA metadata and enforces effective frame counts and visual thresholds.
- `scripts/validate-pet-atlases.py`
  - Calculates alpha bounds, visible-frame counts, scaled dimensions, and baseline ranges.

### Existing shared files to modify

- `src/pet-core/petAssets.ts`
  - Adds the `interactions` and `animations` manifest fields.
  - Stops treating a missing icon-hug path as evidence that icon interaction is supported.
- `src/pet-core/petAssets.test.ts`
  - Verifies package-local paths and new manifest declarations.
- `src/pet-core/interaction.ts`
  - Retains geometric desktop-icon helpers.
  - Removes pet-id action mapping after manifest resolution is active.
- `src/pet-core/interaction.test.ts`
  - Keeps geometry tests; deletes assertions for obsolete pet-id branches.
- `src/pet-core/animationRows.ts`
  - Retains generic frame/landing helpers only.
  - Removes the global per-action row table after manifest migration.
- `src/pet-core/animationRows.test.ts`
  - Tests generic phase helpers and manifest-derived row specs.
- `src/pet-core/dialogue.ts`
  - Continues loading package-local dialogue text; adds neutral fallback behavior.
- `src/pet-core/dialogue.test.ts`
  - Verifies every built-in pet supplies four care-reminder texts or uses neutral fallback.
- `src/pet-core/visual.ts`
  - Resolves manifest scale, offset, and mirror transform.
- `src/pet-core/visual.test.ts`
  - Covers scale, offset, and mirror behavior.
- `src/App.tsx`
  - Adapts pointer, timers, Pixi, Tauri window movement, desktop-icon probes, and update dialog to the pure modules.
  - Removes startup update check, left-triple-click update, pet-id action branches, and shared unowned return timer behavior.
- `src/App.css`
  - Adds compact update-window styles and preserves reduced-motion behavior.

### Pet package files to modify or create

- `public/pets/xiaoju-cat/pet.json`
- `public/pets/xiaoju-cat/dialogues.json` (create)
- `public/pets/xiaoju-cat/icon-hug.webp`
- `public/pets/xiaoju-cat/qa/icon-hug-contact-sheet.png` (create)
- `public/pets/xiaoju-cat/qa/atlas-validation.json` (create)
- `public/pets/xiaoju-cat/README.md` (create)
- `public/pets/ikun/pet.json`
- `public/pets/ikun/dialogues.json` (create)
- `public/pets/ikun/README.md`
- `public/pets/ikun/qa/atlas-validation.json` (update)
- `public/pets/ds/pet.json`
- `public/pets/ds/dialogues.json`
- `public/pets/ds/README.md`
- `public/pets/ds/qa/sprite-build-summary.json`
- `public/pets/suan-bird/pet.json`
- `public/pets/suan-bird/dialogues.json`
- `public/pets/suan-bird/README.md`
- `public/pets/suan-bird/qa/validation.json`

---

### Task 1: Declare the Interaction Contract in Pet Manifests

**Files:**
- Create: `src/pet-core/petInteractionManifest.ts`
- Create: `src/pet-core/petInteractionManifest.test.ts`
- Modify: `src/pet-core/petAssets.ts`
- Modify: `src/pet-core/petAssets.test.ts`
- Modify: `public/pets/xiaoju-cat/pet.json`
- Modify: `public/pets/ikun/pet.json`
- Modify: `public/pets/ds/pet.json`
- Modify: `public/pets/suan-bird/pet.json`

- [ ] **Step 1: Write failing manifest contract tests**

Create `src/pet-core/petInteractionManifest.test.ts` with these assertions:

```ts
import { describe, expect, test } from "vitest";
import ds from "../../public/pets/ds/pet.json";
import ikun from "../../public/pets/ikun/pet.json";
import suanBird from "../../public/pets/suan-bird/pet.json";
import xiaoju from "../../public/pets/xiaoju-cat/pet.json";
import {
  resolvePetInteractionManifest,
  type PetInteractionManifestSource,
} from "./petInteractionManifest";

const resolve = (source: unknown) =>
  resolvePetInteractionManifest(source as PetInteractionManifestSource);

describe("pet interaction manifests", () => {
  test.each([
    ["xiaoju-cat", xiaoju],
    ["ikun", ikun],
    ["ds", ds],
    ["suan-bird", suanBird],
  ])("%s declares every required interaction", (_id, manifest) => {
    const resolved = resolve(manifest);

    expect(resolved.idle).toBeDefined();
    expect(resolved.singleClick).toBeDefined();
    expect(resolved.doubleClick).toBeDefined();
    expect(resolved.drag).toBeDefined();
    expect(Object.keys(resolved.reminders).sort()).toEqual([
      "eyeCare",
      "meal",
      "sleep",
      "water",
    ]);
  });

  test("enables only the approved optional capabilities", () => {
    expect(resolve(xiaoju).hover.enabled).toBe(true);
    expect(resolve(ds).hover.enabled).toBe(false);
    expect(resolve(ikun).hover.enabled).toBe(false);
    expect(resolve(suanBird).hover.enabled).toBe(false);

    expect(resolve(xiaoju).desktopIcon.enabled).toBe(true);
    expect(resolve(ds).desktopIcon.enabled).toBe(true);
    expect(resolve(ikun).desktopIcon.enabled).toBe(false);
    expect(resolve(suanBird).desktopIcon.enabled).toBe(false);
  });

  test("declares effective frame counts instead of transparent cells", () => {
    expect(resolve(xiaoju).animations.tickle.frames).toBe(4);
    expect(resolve(xiaoju).animations.fishChase.frames).toBe(6);
  });

  test("declares real left and right drag rows where available", () => {
    expect(resolve(xiaoju).drag).toMatchObject({
      directionMode: "rows",
      right: "dragRight",
      left: "dragLeft",
    });
    expect(resolve(ds).drag.directionMode).toBe("rows");
    expect(resolve(suanBird).drag.directionMode).toBe("rows");
    expect(resolve(ikun).drag.directionMode).toBe("mirror-left");
  });

  test("disables invalid optional desktop icon behavior", () => {
    const warnings: string[] = [];
    const malformed = {
      id: "broken",
      animations: {},
      interactions: {
        idle: { animation: "idle" },
        singleClick: { animation: "idle" },
        doubleClick: { animation: "idle" },
        drag: {
          directionMode: "rows",
          right: "idle",
          left: "idle",
        },
        reminders: {
          eyeCare: { animation: "idle" },
          water: { animation: "idle" },
          meal: { animation: "idle" },
          sleep: { animation: "idle" },
        },
        desktopIcon: { enabled: true },
      },
    } as unknown as PetInteractionManifestSource;

    expect(
      resolvePetInteractionManifest(
        malformed,
        (message) => warnings.push(message),
      ).desktopIcon,
    ).toEqual({ enabled: false });
    expect(warnings).toEqual([
      "[pet-interactions] broken disabled invalid desktopIcon.action",
    ]);
  });
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
npm test -- src/pet-core/petInteractionManifest.test.ts
```

Expected: FAIL because `petInteractionManifest.ts` and manifest declarations do not exist.

- [ ] **Step 3: Add exact manifest types and resolver**

Create `src/pet-core/petInteractionManifest.ts`:

```ts
import type { PetDialogueEvent } from "./dialogue";

export type PetFacing = "left" | "right";
export type PetReminderKind = "eyeCare" | "water" | "meal" | "sleep";
export type PetDirectionMode = "rows" | "mirror-left";
export type PetDesktopIconPositioning = "wrap" | "peek";

export type PetAnimationSpec = {
  row: number;
  frames: number;
  speed: number;
  loop: boolean;
  visualClass: "ordinary" | "pose-change";
  scale?: number;
  offsetX?: number;
  offsetY?: number;
  spritesheetPath?: string;
  finishFramePath?: string;
};

export type PetActionSpec = {
  animation: string;
  durationMs?: number;
  sound?: string;
  dialogueEvent?: PetDialogueEvent;
  bubbleText?: string;
};

export type PetSequenceStep = PetActionSpec & {
  startAfterMs: number;
};

export type PetSequenceSpec = {
  sequence: PetSequenceStep[];
};

export type PetDragSpec = {
  directionMode: PetDirectionMode;
  right: string;
  left: string;
  takeoffFrame?: number;
  loopStartFrame?: number;
  loopFrameCount?: number;
  landingApproachFrame?: number;
  landingFrame?: number;
  landingTransitionSpeed?: number;
  landingHoldMs?: number;
};

export type PetDesktopIconSpec =
  | { enabled: false }
  | {
      enabled: true;
      action: PetActionSpec;
      positioning: PetDesktopIconPositioning;
      allowedSide: "any" | "left" | "right";
    };

export type PetInteractionManifestSource = {
  id: string;
  animations?: Record<string, PetAnimationSpec>;
  interactions?: {
    idle?: PetActionSpec;
    singleClick?: PetActionSpec | PetSequenceSpec;
    doubleClick?: PetActionSpec | PetSequenceSpec;
    drag?: PetDragSpec;
    hover?: { enabled: boolean; action?: PetActionSpec | PetSequenceSpec };
    desktopIcon?: PetDesktopIconSpec;
    reminders?: Partial<Record<PetReminderKind, PetActionSpec>>;
    idleQuirks?: PetActionSpec[];
  };
};

export type ResolvedPetInteractionManifest = {
  animations: Record<string, PetAnimationSpec>;
  idle: PetActionSpec;
  singleClick: PetActionSpec | PetSequenceSpec;
  doubleClick: PetActionSpec | PetSequenceSpec;
  drag: PetDragSpec;
  hover:
    | { enabled: false }
    | { enabled: true; action: PetActionSpec | PetSequenceSpec };
  desktopIcon: PetDesktopIconSpec;
  reminders: Record<PetReminderKind, PetActionSpec>;
  idleQuirks: PetActionSpec[];
};

const REQUIRED_REMINDERS: PetReminderKind[] = [
  "eyeCare",
  "water",
  "meal",
  "sleep",
];

function requireAction(
  value: PetActionSpec | PetSequenceSpec | undefined,
  field: string,
): PetActionSpec | PetSequenceSpec {
  if (!value) throw new Error(`Missing interactions.${field}`);
  return value;
}

export function resolvePetInteractionManifest(
  source: PetInteractionManifestSource,
  warn: (message: string) => void = console.warn,
): ResolvedPetInteractionManifest {
  const animations = source.animations ?? {};
  const interactions = source.interactions ?? {};
  const idle = requireAction(interactions.idle, "idle") as PetActionSpec;
  const drag = interactions.drag;
  if (!drag) throw new Error("Missing interactions.drag");

  const reminders = Object.fromEntries(
    REQUIRED_REMINDERS.map((kind) => {
      const action = interactions.reminders?.[kind];
      if (!action) throw new Error(`Missing interactions.reminders.${kind}`);
      return [kind, action];
    }),
  ) as Record<PetReminderKind, PetActionSpec>;

  const hover = interactions.hover?.enabled
    ? {
        enabled: true as const,
        action: requireAction(interactions.hover.action, "hover.action"),
      }
    : { enabled: false as const };

  let desktopIcon: PetDesktopIconSpec =
    interactions.desktopIcon ?? { enabled: false };
  if (desktopIcon.enabled && !desktopIcon.action) {
    warn(
      `[pet-interactions] ${source.id} disabled invalid desktopIcon.action`,
    );
    desktopIcon = { enabled: false };
  }

  return {
    animations,
    idle,
    singleClick: requireAction(interactions.singleClick, "singleClick"),
    doubleClick: requireAction(interactions.doubleClick, "doubleClick"),
    drag,
    hover,
    desktopIcon,
    reminders,
    idleQuirks: interactions.idleQuirks ?? [],
  };
}
```

- [ ] **Step 4: Extend `PetManifest`**

Modify `src/pet-core/petAssets.ts`:

```ts
import type {
  PetAnimationSpec,
  PetInteractionManifestSource,
} from "./petInteractionManifest";

export type PetManifest = {
  id: string;
  displayName: string;
  description: string;
  spritesheetPath: string;
  previewPath?: string;
  iconHugSpritesheetPath?: string;
  throwFinishPath?: string;
  actionsPath?: string;
  rigPath?: string;
  actionBoardPath?: string;
  dialoguesPath?: string;
  animations: Record<string, PetAnimationSpec>;
  interactions: NonNullable<PetInteractionManifestSource["interactions"]>;
  sounds?: PetManifestSounds;
};
```

Keep `getPetIconHugSpritesheetPath()` and the existing `RuntimeAnimationName` import temporarily for compatibility. Task 8 removes both helpers plus `animationScales` handling after animation-level paths and transforms are active.

- [ ] **Step 5: Add exact per-pet animation declarations**

Add `animations` and `interactions` to the four `pet.json` files.

For `xiaoju-cat`, declare:

```json
"animations": {
  "idle": { "row": 0, "frames": 6, "speed": 0.05, "loop": true, "visualClass": "pose-change", "scale": 1 },
  "dragRight": { "row": 1, "frames": 8, "speed": 0.2, "loop": true, "visualClass": "ordinary", "scale": 0.83 },
  "dragLeft": { "row": 2, "frames": 8, "speed": 0.2, "loop": true, "visualClass": "ordinary", "scale": 0.83 },
  "tickle": { "row": 3, "frames": 4, "speed": 0.16, "loop": false, "visualClass": "ordinary", "scale": 0.84 },
  "crouchAlert": { "row": 4, "frames": 5, "speed": 0.12, "loop": false, "visualClass": "pose-change", "scale": 1.08 },
  "hugFish": { "row": 5, "frames": 8, "speed": 0.12, "loop": true, "visualClass": "ordinary", "scale": 0.86 },
  "gnawFish": { "row": 6, "frames": 6, "speed": 0.14, "loop": false, "visualClass": "ordinary", "scale": 0.86 },
  "fishChase": { "row": 7, "frames": 6, "speed": 0.18, "loop": true, "visualClass": "pose-change", "scale": 1 },
  "fishEat": { "row": 8, "frames": 6, "speed": 0.14, "loop": false, "visualClass": "ordinary", "scale": 0.84 },
  "iconHug": {
    "row": 0,
    "frames": 6,
    "speed": 0.08,
    "loop": false,
    "visualClass": "ordinary",
    "scale": 0.83,
    "spritesheetPath": "icon-hug.webp"
  }
},
"interactions": {
  "idle": { "animation": "idle", "sound": "idle", "dialogueEvent": "idle" },
  "singleClick": { "animation": "tickle", "durationMs": 1000, "sound": "tickle", "dialogueEvent": "singleClick" },
  "doubleClick": {
    "sequence": [
      { "animation": "fishChase", "startAfterMs": 0, "sound": "fishChase", "dialogueEvent": "doubleClick" },
      { "animation": "fishEat", "startAfterMs": 950, "durationMs": 1300, "sound": "fishEat", "dialogueEvent": "doubleClick" }
    ]
  },
  "drag": { "directionMode": "rows", "right": "dragRight", "left": "dragLeft", "landingHoldMs": 900 },
  "hover": {
    "enabled": true,
    "action": {
      "sequence": [
        { "animation": "fishChase", "startAfterMs": 0, "sound": "fishChase" },
        { "animation": "fishEat", "startAfterMs": 950, "durationMs": 1300, "sound": "fishEat" }
      ]
    }
  },
  "desktopIcon": {
    "enabled": true,
    "action": { "animation": "iconHug", "durationMs": 5600, "sound": "iconHug" },
    "positioning": "wrap",
    "allowedSide": "any"
  },
  "reminders": {
    "eyeCare": { "animation": "idle", "durationMs": 8000, "sound": "care_reminder", "dialogueEvent": "eyeCare" },
    "water": { "animation": "idle", "durationMs": 8000, "sound": "care_reminder", "dialogueEvent": "water" },
    "meal": { "animation": "idle", "durationMs": 5000, "sound": "care_reminder", "dialogueEvent": "meal" },
    "sleep": { "animation": "idle", "durationMs": 8000, "sound": "care_reminder", "dialogueEvent": "sleep" }
  },
  "idleQuirks": [
    { "animation": "fishEat", "durationMs": 2500, "sound": "fishEat", "bubbleText": "（砸嘴）……梦见超大金枪鱼了喵 🐟" },
    { "animation": "tickle", "durationMs": 2000, "sound": "idle", "bubbleText": "（幸福地翻个身）~ 换个姿势继续睡喵…… 🐾" },
    { "animation": "crouchAlert", "durationMs": 2500, "sound": "crouchAlert", "bubbleText": "（趴下警觉喵喵叫）~ 好像有大鱼的气味？🐾" },
    { "animation": "hugFish", "durationMs": 3000, "sound": "hugFish", "bubbleText": "（抱着小鱼撒娇）~ 这只小鱼是橘橘的宝贝！🐟" },
    { "animation": "gnawFish", "durationMs": 2500, "sound": "gnawFish", "bubbleText": "（美滋滋地坐着嚼鱼）~ 玩具鱼真香！🐾" }
  ]
}
```

For `ikun`, merge these exact objects:

```json
"animations": {
  "readyIdle": { "row": 0, "frames": 6, "speed": 0.05, "loop": true, "visualClass": "ordinary", "scale": 1.05 },
  "tieShanKao": { "row": 1, "frames": 8, "speed": 0.2, "loop": false, "visualClass": "ordinary", "scale": 1 },
  "backTurn": { "row": 2, "frames": 8, "speed": 0.16, "loop": false, "visualClass": "ordinary", "scale": 1 },
  "care": { "row": 3, "frames": 8, "speed": 0.16, "loop": false, "visualClass": "ordinary", "scale": 1 },
  "idle": { "row": 4, "frames": 8, "speed": 0.12, "loop": true, "visualClass": "ordinary", "scale": 1 },
  "dance": { "row": 5, "frames": 8, "speed": 0.12, "loop": true, "visualClass": "ordinary", "scale": 1.08 },
  "singleClick": {
    "row": 6,
    "frames": 8,
    "speed": 0.14,
    "loop": false,
    "visualClass": "ordinary",
    "scale": 1.1,
    "finishFramePath": "throw-finish.png"
  },
  "drag": { "row": 7, "frames": 8, "speed": 0.18, "loop": true, "visualClass": "ordinary", "scale": 1.1 },
  "doubleClick": { "row": 8, "frames": 8, "speed": 0.14, "loop": false, "visualClass": "pose-change", "scale": 1.2 }
},
"interactions": {
  "idle": { "animation": "idle", "dialogueEvent": "idle" },
  "singleClick": { "animation": "singleClick", "durationMs": 1300, "dialogueEvent": "singleClick" },
  "doubleClick": { "animation": "doubleClick", "durationMs": 1300, "dialogueEvent": "doubleClick" },
  "drag": { "directionMode": "mirror-left", "right": "drag", "left": "drag", "landingHoldMs": 900 },
  "hover": { "enabled": false },
  "desktopIcon": { "enabled": false },
  "reminders": {
    "eyeCare": { "animation": "care", "durationMs": 8000, "dialogueEvent": "eyeCare" },
    "water": { "animation": "care", "durationMs": 5000, "dialogueEvent": "water" },
    "meal": { "animation": "idle", "durationMs": 5000, "dialogueEvent": "meal" },
    "sleep": { "animation": "idle", "durationMs": 8000, "dialogueEvent": "sleep" }
  },
  "idleQuirks": []
}
```

For `ds`, merge:

```json
"animations": {
  "idle": { "row": 0, "frames": 6, "speed": 0.05, "loop": true, "visualClass": "ordinary", "scale": 1 },
  "dragRight": { "row": 1, "frames": 8, "speed": 0.2, "loop": true, "visualClass": "pose-change", "scale": 1.1 },
  "dragLeft": { "row": 2, "frames": 8, "speed": 0.2, "loop": true, "visualClass": "pose-change", "scale": 1.1 },
  "singleClick": { "row": 3, "frames": 8, "speed": 0.16, "loop": false, "visualClass": "ordinary", "scale": 0.95 },
  "spin": { "row": 4, "frames": 8, "speed": 0.12, "loop": true, "visualClass": "ordinary", "scale": 1 },
  "peek": { "row": 5, "frames": 8, "speed": 0.12, "loop": true, "visualClass": "ordinary", "scale": 1 },
  "yawn": { "row": 6, "frames": 8, "speed": 0.14, "loop": false, "visualClass": "ordinary", "scale": 1.12 },
  "activeJump": { "row": 7, "frames": 8, "speed": 0.18, "loop": true, "visualClass": "pose-change", "scale": 1.1 },
  "happyFinish": { "row": 8, "frames": 6, "speed": 0.14, "loop": false, "visualClass": "ordinary", "scale": 1 }
},
"interactions": {
  "idle": { "animation": "idle", "dialogueEvent": "idle" },
  "singleClick": { "animation": "singleClick", "durationMs": 1200, "dialogueEvent": "singleClick" },
  "doubleClick": {
    "sequence": [
      { "animation": "activeJump", "startAfterMs": 0, "dialogueEvent": "doubleClick" },
      { "animation": "happyFinish", "startAfterMs": 950, "durationMs": 1300, "dialogueEvent": "doubleClick" }
    ]
  },
  "drag": { "directionMode": "rows", "right": "dragRight", "left": "dragLeft", "landingHoldMs": 900 },
  "hover": { "enabled": false },
  "desktopIcon": {
    "enabled": true,
    "action": { "animation": "peek", "durationMs": 2400 },
    "positioning": "peek",
    "allowedSide": "any"
  },
  "reminders": {
    "eyeCare": { "animation": "yawn", "durationMs": 3200, "dialogueEvent": "eyeCare" },
    "water": { "animation": "idle", "durationMs": 5000, "dialogueEvent": "water" },
    "meal": { "animation": "idle", "durationMs": 5000, "dialogueEvent": "meal" },
    "sleep": { "animation": "yawn", "durationMs": 8000, "dialogueEvent": "sleep" }
  },
  "idleQuirks": [
    { "animation": "happyFinish", "durationMs": 2200 },
    { "animation": "spin", "durationMs": 2600 },
    { "animation": "yawn", "durationMs": 3000 },
    { "animation": "peek", "durationMs": 2400 },
    { "animation": "singleClick", "durationMs": 1800 }
  ]
}
```

For `suan-bird`, merge:

```json
"animations": {
  "idle": { "row": 0, "frames": 6, "speed": 0.05, "loop": true, "visualClass": "ordinary", "scale": 1 },
  "dragRight": { "row": 1, "frames": 8, "speed": 0.2, "loop": true, "visualClass": "pose-change", "scale": 1 },
  "dragLeft": { "row": 2, "frames": 8, "speed": 0.2, "loop": true, "visualClass": "pose-change", "scale": 1 },
  "singleClick": { "row": 3, "frames": 8, "speed": 0.16, "loop": false, "visualClass": "pose-change", "scale": 1 },
  "water": { "row": 4, "frames": 8, "speed": 0.12, "loop": false, "visualClass": "ordinary", "scale": 1 },
  "eyeCare": { "row": 5, "frames": 8, "speed": 0.12, "loop": false, "visualClass": "ordinary", "scale": 1 },
  "meal": { "row": 6, "frames": 8, "speed": 0.14, "loop": false, "visualClass": "ordinary", "scale": 1 },
  "doubleClick": { "row": 7, "frames": 8, "speed": 0.18, "loop": false, "visualClass": "pose-change", "scale": 1 },
  "sleep": { "row": 8, "frames": 6, "speed": 0.14, "loop": false, "visualClass": "pose-change", "scale": 1 }
},
"interactions": {
  "idle": { "animation": "idle", "dialogueEvent": "idle" },
  "singleClick": { "animation": "singleClick", "durationMs": 1400, "dialogueEvent": "singleClick" },
  "doubleClick": { "animation": "doubleClick", "durationMs": 2000, "dialogueEvent": "doubleClick" },
  "drag": {
    "directionMode": "rows",
    "right": "dragRight",
    "left": "dragLeft",
    "takeoffFrame": 0,
    "loopStartFrame": 1,
    "loopFrameCount": 6,
    "landingApproachFrame": 6,
    "landingFrame": 7,
    "landingTransitionSpeed": 0.25,
    "landingHoldMs": 350
  },
  "hover": { "enabled": false },
  "desktopIcon": { "enabled": false },
  "reminders": {
    "eyeCare": { "animation": "eyeCare", "durationMs": 3200, "dialogueEvent": "eyeCare" },
    "water": { "animation": "water", "durationMs": 3200, "dialogueEvent": "water" },
    "meal": { "animation": "meal", "durationMs": 3600, "dialogueEvent": "meal" },
    "sleep": { "animation": "sleep", "durationMs": 8000, "dialogueEvent": "sleep" }
  },
  "idleQuirks": []
}
```

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```powershell
npm test -- src/pet-core/petInteractionManifest.test.ts src/pet-core/petAssets.test.ts
```

Expected: both files pass, and all four manifests satisfy the required event contract.

- [ ] **Step 7: Commit**

```powershell
git add -- src/pet-core/petInteractionManifest.ts src/pet-core/petInteractionManifest.test.ts src/pet-core/petAssets.ts src/pet-core/petAssets.test.ts public/pets/xiaoju-cat/pet.json public/pets/ikun/pet.json public/pets/ds/pet.json public/pets/suan-bird/pet.json
git commit -m "feat: declare pet interaction manifests"
```

---

### Task 2: Add the Priority and Token Runtime

**Files:**
- Create: `src/pet-core/interactionRuntime.ts`
- Create: `src/pet-core/interactionRuntime.test.ts`

- [ ] **Step 1: Write failing state-machine tests**

Create `src/pet-core/interactionRuntime.test.ts`:

```ts
import { describe, expect, test } from "vitest";
import {
  completeInteraction,
  createInteractionRuntime,
  requestInteraction,
} from "./interactionRuntime";

describe("pet interaction runtime", () => {
  test("allows direct interaction to preempt a lower priority action", () => {
    const idle = createInteractionRuntime("right");
    const icon = requestInteraction(idle, {
      kind: "desktopIcon",
      interruptible: true,
    });
    const click = requestInteraction(icon.state, {
      kind: "singleClick",
      interruptible: true,
    });

    expect(icon.decision).toBe("start");
    expect(click.decision).toBe("start");
    expect(click.state.active.kind).toBe("singleClick");
    expect(click.state.active.token).toBeGreaterThan(icon.state.active.token);
  });

  test("defers one reminder while a click is active", () => {
    const click = requestInteraction(createInteractionRuntime("right"), {
      kind: "singleClick",
      interruptible: true,
    });
    const reminder = requestInteraction(click.state, {
      kind: "careReminder",
      interruptible: true,
      payloadKey: "2026-06-23:meal-lunch",
      reminderKind: "meal",
    });

    expect(reminder.decision).toBe("queue");
    expect(reminder.state.queued?.kind).toBe("careReminder");
  });

  test("rejects stale completion callbacks", () => {
    const first = requestInteraction(createInteractionRuntime("right"), {
      kind: "idleQuirk",
      interruptible: true,
    });
    const second = requestInteraction(first.state, {
      kind: "doubleClick",
      interruptible: true,
    });

    expect(
      completeInteraction(second.state, first.state.active.token),
    ).toEqual({
      decision: "stale",
      state: second.state,
    });
  });

  test("starts a queued reminder after the active action completes", () => {
    const click = requestInteraction(createInteractionRuntime("left"), {
      kind: "singleClick",
      interruptible: true,
    });
    const queued = requestInteraction(click.state, {
      kind: "careReminder",
      interruptible: true,
      payloadKey: "water",
      reminderKind: "water",
    });
    const completed = completeInteraction(
      queued.state,
      queued.state.active.token,
    );

    expect(completed.decision).toBe("start-queued");
    expect(completed.state.active.kind).toBe("careReminder");
    expect(completed.state.active.facing).toBe("left");
    expect(completed.state.queued).toBeNull();
  });

  test("never lets lower priority work replace an update prompt", () => {
    const prompt = requestInteraction(createInteractionRuntime("right"), {
      kind: "updatePrompt",
      interruptible: false,
    });
    const drag = requestInteraction(prompt.state, {
      kind: "drag",
      interruptible: true,
    });

    expect(drag.decision).toBe("ignore");
    expect(drag.state.active.kind).toBe("updatePrompt");
  });
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
npm test -- src/pet-core/interactionRuntime.test.ts
```

Expected: FAIL because `interactionRuntime.ts` does not exist.

- [ ] **Step 3: Implement the pure runtime**

Create `src/pet-core/interactionRuntime.ts`:

```ts
import type {
  PetFacing,
  PetReminderKind,
} from "./petInteractionManifest";

export type PetInteractionKind =
  | "idle"
  | "idleQuirk"
  | "hover"
  | "desktopIcon"
  | "careReminder"
  | "singleClick"
  | "doubleClick"
  | "drag"
  | "updatePrompt";

export type PetInteractionPhase = "enter" | "loop" | "exit";

export type InteractionRequest = {
  kind: Exclude<PetInteractionKind, "idle">;
  interruptible: boolean;
  payloadKey?: string;
  reminderKind?: PetReminderKind;
};

export type ActivePetInteraction = {
  token: number;
  kind: PetInteractionKind;
  priority: number;
  phase: PetInteractionPhase;
  facing: PetFacing;
  interruptible: boolean;
  payloadKey?: string;
  reminderKind?: PetReminderKind;
};

export type InteractionRuntimeState = {
  nextToken: number;
  active: ActivePetInteraction;
  queued: InteractionRequest | null;
};

const PRIORITY: Record<PetInteractionKind, number> = {
  idle: 0,
  idleQuirk: 100,
  hover: 100,
  desktopIcon: 200,
  careReminder: 300,
  singleClick: 400,
  doubleClick: 400,
  drag: 400,
  updatePrompt: 500,
};

function activate(
  state: InteractionRuntimeState,
  request: InteractionRequest,
): InteractionRuntimeState {
  const token = state.nextToken;
  return {
    nextToken: token + 1,
    queued: state.queued,
    active: {
      token,
      kind: request.kind,
      priority: PRIORITY[request.kind],
      phase: "enter",
      facing: state.active.facing,
      interruptible: request.interruptible,
      payloadKey: request.payloadKey,
      reminderKind: request.reminderKind,
    },
  };
}

export function createInteractionRuntime(
  facing: PetFacing,
): InteractionRuntimeState {
  return {
    nextToken: 1,
    queued: null,
    active: {
      token: 0,
      kind: "idle",
      priority: PRIORITY.idle,
      phase: "loop",
      facing,
      interruptible: true,
    },
  };
}

export function requestInteraction(
  state: InteractionRuntimeState,
  request: InteractionRequest,
): {
  decision: "start" | "queue" | "ignore";
  state: InteractionRuntimeState;
} {
  const requestPriority = PRIORITY[request.kind];
  if (
    requestPriority >= state.active.priority &&
    state.active.interruptible
  ) {
    return { decision: "start", state: activate(state, request) };
  }

  if (request.kind === "careReminder") {
    return {
      decision: "queue",
      state: { ...state, queued: request },
    };
  }

  return { decision: "ignore", state };
}

export function completeInteraction(
  state: InteractionRuntimeState,
  token: number,
): {
  decision: "idle" | "start-queued" | "stale";
  state: InteractionRuntimeState;
} {
  if (state.active.token !== token) {
    return { decision: "stale", state };
  }

  if (state.queued) {
    const queued = state.queued;
    const started = activate({ ...state, queued: null }, queued);
    return { decision: "start-queued", state: started };
  }

  return {
    decision: "idle",
    state: {
      ...state,
      active: {
        token: state.nextToken,
        kind: "idle",
        priority: PRIORITY.idle,
        phase: "loop",
        facing: state.active.facing,
        interruptible: true,
      },
      nextToken: state.nextToken + 1,
      queued: null,
    },
  };
}

export function setInteractionFacing(
  state: InteractionRuntimeState,
  facing: PetFacing,
): InteractionRuntimeState {
  return {
    ...state,
    active: { ...state.active, facing },
  };
}
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
npm test -- src/pet-core/interactionRuntime.test.ts
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```powershell
git add -- src/pet-core/interactionRuntime.ts src/pet-core/interactionRuntime.test.ts
git commit -m "feat: add pet interaction priority runtime"
```

---

### Task 3: Add Directional Drag Hysteresis

**Files:**
- Create: `src/pet-core/dragDirection.ts`
- Create: `src/pet-core/dragDirection.test.ts`
- Modify: `src/pet-core/interaction.ts`
- Modify: `src/pet-core/interaction.test.ts`

- [ ] **Step 1: Write failing direction tests**

Create `src/pet-core/dragDirection.test.ts`:

```ts
import { describe, expect, test } from "vitest";
import {
  createDragDirectionState,
  updateDragDirection,
} from "./dragDirection";

describe("drag direction", () => {
  test("turns right after eight logical pixels", () => {
    const state = createDragDirectionState("left", 100);

    expect(updateDragDirection(state, 107, 1).facing).toBe("left");
    expect(updateDragDirection(state, 108, 1).facing).toBe("right");
  });

  test("turns left after eight logical pixels", () => {
    const state = createDragDirectionState("right", 100);

    expect(updateDragDirection(state, 92, 1).facing).toBe("left");
  });

  test("converts physical movement to logical movement on high DPI", () => {
    const state = createDragDirectionState("left", 200);

    expect(updateDragDirection(state, 215, 2).facing).toBe("left");
    expect(updateDragDirection(state, 216, 2).facing).toBe("right");
  });

  test("keeps the last facing during vertical or jitter movement", () => {
    const state = createDragDirectionState("right", 100);
    const jitter = updateDragDirection(state, 96, 1);

    expect(jitter.facing).toBe("right");
    expect(jitter.anchorPhysicalX).toBe(100);
  });
});
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
npm test -- src/pet-core/dragDirection.test.ts
```

Expected: FAIL because `dragDirection.ts` does not exist.

- [ ] **Step 3: Implement the 8-pixel logical threshold**

Create `src/pet-core/dragDirection.ts`:

```ts
import type { PetFacing } from "./petInteractionManifest";

export const DRAG_DIRECTION_THRESHOLD_LOGICAL_PX = 8;

export type DragDirectionState = {
  facing: PetFacing;
  anchorPhysicalX: number;
};

export function createDragDirectionState(
  facing: PetFacing,
  pointerPhysicalX: number,
): DragDirectionState {
  return { facing, anchorPhysicalX: pointerPhysicalX };
}

export function updateDragDirection(
  state: DragDirectionState,
  pointerPhysicalX: number,
  scaleFactor: number,
): DragDirectionState {
  const safeScaleFactor = scaleFactor > 0 ? scaleFactor : 1;
  const logicalDelta =
    (pointerPhysicalX - state.anchorPhysicalX) / safeScaleFactor;

  if (Math.abs(logicalDelta) < DRAG_DIRECTION_THRESHOLD_LOGICAL_PX) {
    return state;
  }

  return {
    facing: logicalDelta < 0 ? "left" : "right",
    anchorPhysicalX: pointerPhysicalX,
  };
}
```

- [ ] **Step 4: Stop extending pet-id drag action selection**

Task 8 deletes `getPetDragStartAction()` and `getPetDragEndAction()` after manifest drag declarations are wired. Until then, add only a deprecation comment above each existing implementation and delete tests that would encourage adding new pet-id branches:

```ts
/** @deprecated Task 8 replaces this with resolved manifest interactions.drag. */
```

Do not rename or wrap the existing functions in this task; preserving their current bodies keeps the tree green without introducing a second legacy API.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
npm test -- src/pet-core/dragDirection.test.ts src/pet-core/interaction.test.ts
```

Expected: all focused tests pass.

- [ ] **Step 6: Commit**

```powershell
git add -- src/pet-core/dragDirection.ts src/pet-core/dragDirection.test.ts src/pet-core/interaction.ts src/pet-core/interaction.test.ts
git commit -m "feat: track desktop pet drag direction"
```

---

### Task 4: Persist Care Reminder Delivery

**Files:**
- Create: `src/pet-core/careReminders.ts`
- Create: `src/pet-core/careReminders.test.ts`
- Modify: `src/pet-core/dialogue.ts`
- Modify: `src/pet-core/dialogue.test.ts`
- Create: `public/pets/xiaoju-cat/dialogues.json`
- Create: `public/pets/ikun/dialogues.json`
- Modify: `public/pets/ds/dialogues.json`
- Modify: `public/pets/suan-bird/dialogues.json`
- Modify: all four `pet.json` files to include `dialoguesPath`

- [ ] **Step 1: Write failing persistence and slot tests**

Create `src/pet-core/careReminders.test.ts`:

```ts
import { describe, expect, test, vi } from "vitest";
import {
  CARE_REMINDER_STORAGE_KEY,
  markCareReminderDelivered,
  readCareReminderState,
  selectTimedCareReminder,
  writeCareReminderState,
  type CareReminderStorage,
} from "./careReminders";

function storage(initial: string | null = null): CareReminderStorage {
  let value = initial;
  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((_key, nextValue) => {
      value = nextValue;
    }),
  };
}

describe("care reminder persistence", () => {
  test("selects each meal slot and one overnight sleep slot", () => {
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 7, 30), [])).toEqual({
      kind: "meal",
      key: "2026-06-23:meal-breakfast",
    });
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 12, 0), [])).toEqual({
      kind: "meal",
      key: "2026-06-23:meal-lunch",
    });
    expect(selectTimedCareReminder(new Date(2026, 5, 23, 19, 0), [])).toEqual({
      kind: "meal",
      key: "2026-06-23:meal-dinner",
    });
    expect(selectTimedCareReminder(new Date(2026, 5, 24, 1, 0), [])).toEqual({
      kind: "sleep",
      key: "2026-06-23:sleep",
    });
  });

  test("does not redeliver a persisted slot after restart", () => {
    const first = selectTimedCareReminder(
      new Date(2026, 5, 23, 12, 0),
      [],
    );
    const delivered = markCareReminderDelivered([], first!.key);

    expect(
      selectTimedCareReminder(
        new Date(2026, 5, 23, 12, 30),
        delivered,
      ),
    ).toBeNull();
  });

  test("repairs invalid storage and writes the versioned key", () => {
    const target = storage("not-json");

    expect(readCareReminderState(target)).toEqual({ deliveredKeys: [] });
    expect(
      writeCareReminderState(
        { deliveredKeys: ["2026-06-23:meal-lunch"] },
        target,
      ),
    ).toBe(true);
    expect(target.setItem).toHaveBeenCalledWith(
      CARE_REMINDER_STORAGE_KEY,
      JSON.stringify({ deliveredKeys: ["2026-06-23:meal-lunch"] }),
    );
  });
});
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
npm test -- src/pet-core/careReminders.test.ts
```

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement storage and timed selection**

Create `src/pet-core/careReminders.ts`:

```ts
import type { PetReminderKind } from "./petInteractionManifest";

export const CARE_REMINDER_STORAGE_KEY = "yuxin-care-reminders-v1";

export type CareReminderState = {
  deliveredKeys: string[];
};

export type CareReminderStorage = Pick<Storage, "getItem" | "setItem">;

export type TimedCareReminder = {
  kind: Extract<PetReminderKind, "meal" | "sleep">;
  key: string;
};

function dateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function sleepDate(date: Date): Date {
  if (date.getHours() >= 6) return date;
  const previous = new Date(date);
  previous.setDate(previous.getDate() - 1);
  return previous;
}

export function selectTimedCareReminder(
  date: Date,
  deliveredKeys: string[],
): TimedCareReminder | null {
  const hour = date.getHours();
  let reminder: TimedCareReminder | null = null;

  if (hour >= 7 && hour < 9) {
    reminder = { kind: "meal", key: `${dateKey(date)}:meal-breakfast` };
  } else if (hour >= 11 && hour < 13) {
    reminder = { kind: "meal", key: `${dateKey(date)}:meal-lunch` };
  } else if (hour >= 18 && hour < 20) {
    reminder = { kind: "meal", key: `${dateKey(date)}:meal-dinner` };
  } else if (hour >= 23 || hour < 6) {
    reminder = { kind: "sleep", key: `${dateKey(sleepDate(date))}:sleep` };
  }

  return reminder && !deliveredKeys.includes(reminder.key) ? reminder : null;
}

export function markCareReminderDelivered(
  deliveredKeys: string[],
  key: string,
): string[] {
  return deliveredKeys.includes(key) ? deliveredKeys : [...deliveredKeys, key];
}

export function readCareReminderState(
  storage: CareReminderStorage | null =
    typeof window === "undefined" ? null : window.localStorage,
): CareReminderState {
  if (!storage) return { deliveredKeys: [] };
  try {
    const value = JSON.parse(storage.getItem(CARE_REMINDER_STORAGE_KEY) ?? "");
    return {
      deliveredKeys: Array.isArray(value.deliveredKeys)
        ? [...new Set(value.deliveredKeys.filter((key: unknown) => typeof key === "string"))]
        : [],
    };
  } catch {
    return { deliveredKeys: [] };
  }
}

export function writeCareReminderState(
  state: CareReminderState,
  storage: CareReminderStorage | null =
    typeof window === "undefined" ? null : window.localStorage,
): boolean {
  if (!storage) return false;
  try {
    storage.setItem(CARE_REMINDER_STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}
```

- [ ] **Step 4: Add package-local dialogue files**

Create `public/pets/xiaoju-cat/dialogues.json`:

```json
{
  "idle": "我先睡一会儿。",
  "singleClick": "哼，还行。",
  "doubleClick": "鱼！",
  "water": "主人，该喝杯水啦，休息一下再继续喵。",
  "eyeCare": "看屏幕太久啦，看看远处，让眼睛休息一下吧。",
  "meal": "到饭点啦，先好好吃饭，回来再继续。",
  "sleep": "夜深了，早点休息吧，小橘明天继续陪你。"
}
```

Create `public/pets/ikun/dialogues.json`:

```json
{
  "idle": "中分头，背带裤，我是ikun你记住",
  "singleClick": "丢球。",
  "doubleClick": "鸡你太美",
  "water": "休息一下，喝口水再继续。",
  "eyeCare": "ikun们，看很久电脑了，要注意休息",
  "meal": "到饭点了，先补充能量。",
  "sleep": "时间不早了，今天先休息。"
}
```

Keep the existing ds and suan-bird text, and verify both files contain all seven dialogue keys.

- [ ] **Step 5: Add neutral fallback text**

Modify `src/pet-core/dialogue.ts`:

```ts
export const NEUTRAL_PET_DIALOGUES: Required<PetDialogues> = {
  idle: "我会在这里陪着你。",
  singleClick: "收到。",
  doubleClick: "一起活动一下。",
  water: "该喝杯水了，休息一下再继续。",
  eyeCare: "看看远处，让眼睛休息一下。",
  meal: "到饭点了，先好好吃饭。",
  sleep: "时间不早了，今天先休息。",
};
```

Change missing-event resolution to return `fallbackText ?? NEUTRAL_PET_DIALOGUES[event]` rather than `null`.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
npm test -- src/pet-core/careReminders.test.ts src/pet-core/dialogue.test.ts src/pet-core/petAssets.test.ts
```

Expected: all focused tests pass.

- [ ] **Step 7: Commit**

```powershell
git add -- src/pet-core/careReminders.ts src/pet-core/careReminders.test.ts src/pet-core/dialogue.ts src/pet-core/dialogue.test.ts src/pet-core/petAssets.test.ts public/pets/xiaoju-cat/dialogues.json public/pets/ikun/dialogues.json public/pets/ds/dialogues.json public/pets/suan-bird/dialogues.json public/pets/xiaoju-cat/pet.json public/pets/ikun/pet.json
git commit -m "feat: persist complete pet care reminders"
```

---

### Task 5: Build Semantic Update Checking

**Files:**
- Create: `src/pet-update/updateCheck.ts`
- Create: `src/pet-update/updateCheck.test.ts`

- [ ] **Step 1: Write failing update tests**

Create `src/pet-update/updateCheck.test.ts`:

```ts
import { describe, expect, test, vi } from "vitest";
import {
  checkForLatestRelease,
  compareSemanticVersions,
} from "./updateCheck";

describe("update checking", () => {
  test("compares normalized semantic versions", () => {
    expect(compareSemanticVersions("v0.2.3", "0.2.2")).toBe(1);
    expect(compareSemanticVersions("0.2.2", "v0.2.2")).toBe(0);
    expect(compareSemanticVersions("0.2.1", "0.2.2")).toBe(-1);
  });

  test("returns available only for a newer release", async () => {
    const fetchLatest = vi.fn(async () => ({
      tag_name: "v0.2.3",
      body: "Fixes and animation improvements.",
      html_url: "https://github.com/user-wangjun/company-pet/releases/tag/v0.2.3",
    }));

    await expect(
      checkForLatestRelease("0.2.2", fetchLatest),
    ).resolves.toEqual({
      status: "available",
      currentVersion: "0.2.2",
      latestVersion: "0.2.3",
      notes: "Fixes and animation improvements.",
      releaseUrl:
        "https://github.com/user-wangjun/company-pet/releases/tag/v0.2.3",
    });
  });

  test("returns current for equal or older remote releases", async () => {
    await expect(
      checkForLatestRelease("0.2.2", async () => ({
        tag_name: "v0.2.2",
        body: "",
        html_url: "https://example.test/current",
      })),
    ).resolves.toEqual({ status: "current", currentVersion: "0.2.2" });

    await expect(
      checkForLatestRelease("0.2.2", async () => ({
        tag_name: "v0.2.1",
        body: "",
        html_url: "https://example.test/old",
      })),
    ).resolves.toEqual({ status: "current", currentVersion: "0.2.2" });
  });

  test("returns failed for malformed responses", async () => {
    await expect(
      checkForLatestRelease("0.2.2", async () => ({
        tag_name: "latest",
        body: "",
        html_url: "",
      })),
    ).resolves.toMatchObject({ status: "failed" });
  });
});
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
npm test -- src/pet-update/updateCheck.test.ts
```

Expected: FAIL because the update module does not exist.

- [ ] **Step 3: Implement semantic comparison and result types**

Create `src/pet-update/updateCheck.ts`:

```ts
import { getVersion } from "@tauri-apps/api/app";
import packageMetadata from "../../package.json";

export const GITHUB_RELEASE_API =
  "https://api.github.com/repos/user-wangjun/company-pet/releases/latest";
export const GITHUB_RELEASE_PAGE =
  "https://github.com/user-wangjun/company-pet/releases/latest";

type ReleaseResponse = {
  tag_name: string;
  body?: string | null;
  html_url?: string | null;
};

export type UpdateCheckResult =
  | { status: "current"; currentVersion: string }
  | {
      status: "available";
      currentVersion: string;
      latestVersion: string;
      notes: string;
      releaseUrl: string;
    }
  | { status: "failed"; message: string };

function normalizeVersion(version: string): [number, number, number] | null {
  const match = version.trim().match(/^v?(\d+)\.(\d+)\.(\d+)$/i);
  return match
    ? [Number(match[1]), Number(match[2]), Number(match[3])]
    : null;
}

export function compareSemanticVersions(left: string, right: string): number {
  const a = normalizeVersion(left);
  const b = normalizeVersion(right);
  if (!a || !b) throw new Error("Invalid semantic version");

  for (let index = 0; index < a.length; index += 1) {
    if (a[index] !== b[index]) return a[index] > b[index] ? 1 : -1;
  }
  return 0;
}

export async function getCurrentAppVersion(): Promise<string> {
  try {
    return await getVersion();
  } catch {
    return packageMetadata.version;
  }
}

export async function fetchLatestRelease(): Promise<ReleaseResponse> {
  const response = await fetch(GITHUB_RELEASE_API, {
    headers: { Accept: "application/vnd.github+json" },
  });
  if (!response.ok) throw new Error(`GitHub release request: ${response.status}`);
  return response.json() as Promise<ReleaseResponse>;
}

export async function checkForLatestRelease(
  currentVersion: string,
  fetcher: () => Promise<ReleaseResponse> = fetchLatestRelease,
): Promise<UpdateCheckResult> {
  try {
    const release = await fetcher();
    const normalized = normalizeVersion(release.tag_name);
    if (!normalized) return { status: "failed", message: "Invalid release version" };

    const latestVersion = normalized.join(".");
    if (compareSemanticVersions(latestVersion, currentVersion) <= 0) {
      return { status: "current", currentVersion };
    }

    return {
      status: "available",
      currentVersion,
      latestVersion,
      notes: release.body?.trim() || "新版本已发布。",
      releaseUrl: release.html_url?.trim() || GITHUB_RELEASE_PAGE,
    };
  } catch {
    return { status: "failed", message: "检查更新失败，请稍后再试。" };
  }
}
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
npm test -- src/pet-update/updateCheck.test.ts
```

Expected: all update tests pass.

- [ ] **Step 5: Commit**

```powershell
git add -- src/pet-update/updateCheck.ts src/pet-update/updateCheck.test.ts
git commit -m "feat: add semantic release update checks"
```

---

### Task 6: Add the Update Confirmation Dialog

**Files:**
- Create: `src/pet-update/UpdateDialog.tsx`
- Create: `src/pet-update/UpdateDialog.test.tsx`
- Modify: `src/App.css`

- [ ] **Step 1: Write failing component tests**

Create `src/pet-update/UpdateDialog.test.tsx`:

```tsx
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import { UpdateDialog } from "./UpdateDialog";

describe("UpdateDialog", () => {
  test("renders an accessible confirmation with versions and notes", () => {
    const html = renderToStaticMarkup(
      <UpdateDialog
        currentVersion="0.2.2"
        latestVersion="0.2.3"
        notes="Improved pet interactions."
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    expect(html).toContain('role="alertdialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain("当前版本 0.2.2");
    expect(html).toContain("最新版本 0.2.3");
    expect(html).toContain("Improved pet interactions.");
    expect(html).toContain("稍后再说");
    expect(html).toContain("前往下载");
  });
});
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
npm test -- src/pet-update/UpdateDialog.test.tsx
```

Expected: FAIL because the component does not exist.

- [ ] **Step 3: Implement the dialog**

Create `src/pet-update/UpdateDialog.tsx`:

```tsx
type UpdateDialogProps = {
  currentVersion: string;
  latestVersion: string;
  notes: string;
  onCancel: () => void;
  onConfirm: () => void;
};

export function UpdateDialog({
  currentVersion,
  latestVersion,
  notes,
  onCancel,
  onConfirm,
}: UpdateDialogProps) {
  return (
    <div className="update-dialog-overlay" role="presentation">
      <section
        className="update-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="update-dialog-title"
        aria-describedby="update-dialog-description"
      >
        <h2 id="update-dialog-title">发现新版本</h2>
        <p className="update-dialog-versions">
          当前版本 {currentVersion}
          <span aria-hidden="true"> → </span>
          最新版本 {latestVersion}
        </p>
        <p id="update-dialog-description" className="update-dialog-notes">
          {notes}
        </p>
        <div className="update-dialog-actions">
          <button type="button" onClick={onCancel}>
            稍后再说
          </button>
          <button type="button" onClick={onConfirm} autoFocus>
            前往下载
          </button>
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Add compact update-window styles**

Append to `src/App.css`:

```css
.update-dialog-overlay {
  position: absolute;
  z-index: 30;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 18px;
  background: rgba(17, 24, 34, 0.56);
}

.update-dialog {
  width: min(420px, 100%);
  max-height: 250px;
  overflow: auto;
  padding: 24px;
  border: 1px solid rgba(106, 53, 25, 0.2);
  border-radius: 18px;
  background: #fffaf2;
  color: #3a251b;
  box-shadow: 0 22px 56px rgba(22, 13, 8, 0.24);
}

.update-dialog h2,
.update-dialog p {
  margin: 0;
}

.update-dialog-versions {
  margin-top: 10px !important;
  font-weight: 700;
}

.update-dialog-notes {
  margin-top: 12px !important;
  white-space: pre-wrap;
}

.update-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
npm test -- src/pet-update/UpdateDialog.test.tsx
```

Expected: component test passes.

- [ ] **Step 6: Commit**

```powershell
git add -- src/pet-update/UpdateDialog.tsx src/pet-update/UpdateDialog.test.tsx src/App.css
git commit -m "feat: add update confirmation dialog"
```

---

### Task 7: Resolve Animation Frames and Visual Transforms from the Manifest

**Files:**
- Modify: `src/pet-core/animationRows.ts`
- Modify: `src/pet-core/animationRows.test.ts`
- Modify: `src/pet-core/visual.ts`
- Modify: `src/pet-core/visual.test.ts`

- [ ] **Step 1: Replace global-row tests with manifest-spec tests**

Add to `src/pet-core/animationRows.test.ts`:

```ts
import type { PetAnimationSpec } from "./petInteractionManifest";
import {
  buildAnimationFrameRects,
  buildDragLandingFrameIndexes,
} from "./animationRows";

test("builds only declared effective frame rectangles", () => {
  const spec: PetAnimationSpec = {
    row: 3,
    frames: 4,
    speed: 0.16,
    loop: false,
    visualClass: "ordinary",
  };

  expect(buildAnimationFrameRects(spec, 192, 208)).toEqual([
    { x: 0, y: 624, width: 192, height: 208 },
    { x: 192, y: 624, width: 192, height: 208 },
    { x: 384, y: 624, width: 192, height: 208 },
    { x: 576, y: 624, width: 192, height: 208 },
  ]);
});

test("builds the suan-bird landing indexes without pet-id branches", () => {
  expect(
    buildDragLandingFrameIndexes({
      currentFrame: 4,
      approachFrame: 6,
      landingFrame: 7,
    }),
  ).toEqual([4, 6, 7]);
});
```

Add to `src/pet-core/visual.test.ts`:

```ts
import { getPetAnimationTransform } from "./visual";

test("resolves scale, offset, and left mirror from animation specs", () => {
  expect(
    getPetAnimationTransform(
      { row: 1, frames: 8, speed: 0.2, loop: true, visualClass: "ordinary", scale: 0.83, offsetX: 2, offsetY: -3 },
      "left",
      "mirror-left",
    ),
  ).toEqual({
    scaleX: -0.3818,
    scaleY: 0.3818,
    offsetX: 2,
    offsetY: -3,
  });
});
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```powershell
npm test -- src/pet-core/animationRows.test.ts src/pet-core/visual.test.ts
```

Expected: FAIL because the generic resolver functions do not exist.

- [ ] **Step 3: Implement generic frame rectangle helpers**

Replace the global `ANIMATION_ROWS` dependency in `src/pet-core/animationRows.ts` with:

```ts
import type { PetAnimationSpec } from "./petInteractionManifest";

export type AnimationFrameRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export function buildAnimationFrameRects(
  spec: PetAnimationSpec,
  cellWidth: number,
  cellHeight: number,
): AnimationFrameRect[] {
  return Array.from({ length: spec.frames }, (_, index) => ({
    x: index * cellWidth,
    y: spec.row * cellHeight,
    width: cellWidth,
    height: cellHeight,
  }));
}

export function buildDragLandingFrameIndexes(input: {
  currentFrame: number;
  approachFrame: number;
  landingFrame: number;
}): number[] {
  return [input.currentFrame, input.approachFrame, input.landingFrame];
}
```

Retain `appendPetAnimationFinishFrame()` only until Task 8 reads `finishFramePath` from the animation spec, then remove it.

- [ ] **Step 4: Implement visual transform resolution**

Modify `src/pet-core/visual.ts`:

```ts
import type {
  PetAnimationSpec,
  PetDirectionMode,
  PetFacing,
} from "./petInteractionManifest";

export function getPetAnimationTransform(
  spec: PetAnimationSpec,
  facing: PetFacing,
  directionMode: PetDirectionMode | "none" = "none",
): {
  scaleX: number;
  scaleY: number;
  offsetX: number;
  offsetY: number;
} {
  const visualScale = PET_VISUAL_SCALE * (spec.scale ?? 1);
  const mirror = directionMode === "mirror-left" && facing === "left";
  return {
    scaleX: mirror ? -visualScale : visualScale,
    scaleY: visualScale,
    offsetX: spec.offsetX ?? 0,
    offsetY: spec.offsetY ?? 0,
  };
}
```

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```powershell
npm test -- src/pet-core/animationRows.test.ts src/pet-core/visual.test.ts
```

Expected: all focused tests pass.

- [ ] **Step 6: Commit**

```powershell
git add -- src/pet-core/animationRows.ts src/pet-core/animationRows.test.ts src/pet-core/visual.ts src/pet-core/visual.test.ts
git commit -m "refactor: resolve pet animation visuals from manifests"
```

---

### Task 8: Integrate Direct Input, Pixi Playback, and Directional Dragging

**Files:**
- Modify: `src/App.tsx`
- Modify: `src/pet-core/interaction.ts`
- Modify: `src/pet-core/interaction.test.ts`

- [ ] **Step 1: Add failing pure input tests**

Add to `src/pet-core/interaction.test.ts`:

```ts
import {
  registerSecondaryClick,
  resolveDragAnimationName,
} from "./interaction";

test("triggers update only on the second right click", () => {
  const first = registerSecondaryClick(null, 1000);
  expect(first).toEqual({ triggered: false, lastClickAt: 1000 });

  expect(registerSecondaryClick(first.lastClickAt, 1250)).toEqual({
    triggered: true,
    lastClickAt: null,
  });
});

test("does not treat a delayed right click as a double click", () => {
  expect(registerSecondaryClick(1000, 1400)).toEqual({
    triggered: false,
    lastClickAt: 1400,
  });
});

test("resolves directional drag animation names", () => {
  expect(
    resolveDragAnimationName(
      { directionMode: "rows", right: "dragRight", left: "dragLeft" },
      "left",
    ),
  ).toBe("dragLeft");
  expect(
    resolveDragAnimationName(
      { directionMode: "mirror-left", right: "stepBack", left: "stepBack" },
      "left",
    ),
  ).toBe("stepBack");
});
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
npm test -- src/pet-core/interaction.test.ts
```

Expected: FAIL because both helpers are missing.

- [ ] **Step 3: Implement right-double-click and drag-name helpers**

Add to `src/pet-core/interaction.ts`:

```ts
import type { PetDragSpec, PetFacing } from "./petInteractionManifest";

export const SECONDARY_DOUBLE_CLICK_MS = 350;

export function registerSecondaryClick(
  lastClickAt: number | null,
  now: number,
): { triggered: boolean; lastClickAt: number | null } {
  if (
    lastClickAt !== null &&
    now - lastClickAt <= SECONDARY_DOUBLE_CLICK_MS
  ) {
    return { triggered: true, lastClickAt: null };
  }

  return { triggered: false, lastClickAt: now };
}

export function resolveDragAnimationName(
  drag: PetDragSpec,
  facing: PetFacing,
): string {
  return facing === "left" ? drag.left : drag.right;
}
```

- [ ] **Step 4: Replace animation loading in `App.tsx`**

Replace the fixed `animations: Record<AnimationName, Texture[]>` construction with:

```ts
const animations = Object.fromEntries(
  await Promise.all(
    Object.entries(manifest.animations).map(async ([name, spec]) => {
      const sourcePath = spec.spritesheetPath ?? manifest.spritesheetPath;
      const sourceTexture =
        sourcePath === manifest.spritesheetPath
          ? texture
          : await Assets.load<Texture>(resolvePetAssetUrl(petId, sourcePath));
      const frames = buildAnimationFrameRects(spec, CELL_WIDTH, CELL_HEIGHT).map(
        (frame) =>
          new Texture({
            source: sourceTexture.source,
            frame: new Rectangle(
              frame.x,
              frame.y,
              frame.width,
              frame.height,
            ),
          }),
      );

      if (!spec.finishFramePath) return [name, frames] as const;
      const finishTexture = await Assets.load<Texture>(
        resolvePetAssetUrl(petId, spec.finishFramePath),
      );
      return [name, [...frames, finishTexture]] as const;
    }),
  ),
);
```

Change `animationsRef` to:

```ts
const animationsRef = useRef<Record<string, Texture[]> | null>(null);
```

- [ ] **Step 5: Add one runtime-owned animation starter**

At component scope, add stable geometry and timer refs:

```ts
const appScreenCenterX = useRef(0);
const appScreenBottom = useRef(0);
const playbackTimers = useRef(new Set<number>());
```

Update the geometry refs whenever the Pixi renderer is created or resized. Clear every id in `playbackTimers.current` during effect cleanup. After the active manifest is loaded inside the Pixi effect, bind:

```ts
const activeInteractions = resolvePetInteractionManifest(manifest);
```

Replace direct `playAnimation()` ownership with a helper that requires a runtime token:

```ts
const playResolvedAction = (
  token: number,
  action: PetActionSpec,
  facing: PetFacing,
) => {
  if (interactionRuntime.current.active.token !== token) return false;
  const sprite = spriteRef.current;
  const animations = animationsRef.current;
  const spec = activeInteractions.animations[action.animation];
  const textures = animations?.[action.animation];
  if (!sprite || !spec || !textures) return false;

  const transform = getPetAnimationTransform(
    spec,
    facing,
    activeInteractions.drag.directionMode,
  );
  currentAnimation.current = action.animation;
  sprite.onComplete = undefined;
  sprite.textures = textures;
  sprite.animationSpeed = spec.speed;
  sprite.loop = spec.loop;
  sprite.scale.set(transform.scaleX, transform.scaleY);
  sprite.x = appScreenCenterX.current + transform.offsetX;
  sprite.y = appScreenBottom.current - 6 + transform.offsetY;
  sprite.gotoAndPlay(0);
  return true;
};
```

Store screen-center and bottom values in refs updated from the ticker, rather than closing over the Pixi `app` in interaction callbacks.

- [ ] **Step 6: Add token-owned sequence, completion, idle, and drag adapters**

Import `PetSequenceSpec`, then add:

```ts
const scheduleForToken = (
  token: number,
  delayMs: number,
  callback: () => void,
) => {
  const timerId = window.setTimeout(() => {
    playbackTimers.current.delete(timerId);
    if (interactionRuntime.current.active.token !== token) return;
    callback();
  }, delayMs);
  playbackTimers.current.add(timerId);
};

const playIdle = (token: number) => {
  playResolvedAction(
    token,
    activeInteractions.idle,
    interactionRuntime.current.active.facing,
  );
};

const finishInteraction = (token: number) => {
  const completed = completeInteraction(interactionRuntime.current, token);
  interactionRuntime.current = completed.state;
  if (completed.decision === "idle") {
    playIdle(completed.state.active.token);
  }
  // Task 9 handles the only queued request type: care reminders.
};

const armActionCompletion = (token: number, action: PetActionSpec) => {
  const spec = activeInteractions.animations[action.animation];
  if (action.durationMs !== undefined) {
    scheduleForToken(token, action.durationMs, () => finishInteraction(token));
    return;
  }
  if (spec.loop) {
    throw new Error(
      `Looping interaction ${action.animation} requires durationMs`,
    );
  }

  const sprite = spriteRef.current;
  if (!sprite) return;
  sprite.onComplete = () => {
    sprite.onComplete = undefined;
    finishInteraction(token);
  };
};

const playConfiguredInteraction = (
  token: number,
  configured: PetActionSpec | PetSequenceSpec,
) => {
  const steps =
    "sequence" in configured
      ? configured.sequence
      : [{ ...configured, startAfterMs: 0 }];

  steps.forEach((step, index) => {
    scheduleForToken(token, step.startAfterMs, () => {
      if (
        !playResolvedAction(
          token,
          step,
          interactionRuntime.current.active.facing,
        )
      ) {
        finishInteraction(token);
        return;
      }
      if (index === steps.length - 1) armActionCompletion(token, step);
    });
  });
};

const playDragLoopForFacing = (
  facing: PetFacing,
  replayTakeoff = false,
) => {
  const animation = resolveDragAnimationName(activeInteractions.drag, facing);
  if (
    currentAnimation.current === animation &&
    !replayTakeoff
  ) return;
  if (!playResolvedAction(
    interactionRuntime.current.active.token,
    { animation },
    facing,
  )) return;

  const drag = activeInteractions.drag;
  const sprite = spriteRef.current;
  const textures = animationsRef.current?.[animation];
  if (
    !sprite ||
    !textures ||
    drag.loopStartFrame === undefined ||
    drag.loopFrameCount === undefined
  ) return;
  const loopStartFrame = drag.loopStartFrame;
  const loopFrameCount = drag.loopFrameCount;

  const switchToLoop = () => {
    sprite.onFrameChange = undefined;
    sprite.textures = textures.slice(
      loopStartFrame,
      loopStartFrame + loopFrameCount,
    );
    sprite.loop = true;
    sprite.gotoAndPlay(0);
  };

  if (!replayTakeoff) {
    switchToLoop();
    return;
  }
  sprite.loop = false;
  sprite.onFrameChange = (frame) => {
    if (frame >= loopStartFrame) switchToLoop();
  };
  sprite.gotoAndPlay(drag.takeoffFrame ?? 0);
};

const finishDragInteraction = (token: number) => {
  const drag = activeInteractions.drag;
  const sprite = spriteRef.current;
  const animation = resolveDragAnimationName(
    drag,
    interactionRuntime.current.active.facing,
  );
  const textures = animationsRef.current?.[animation];

  if (
    !sprite ||
    !textures ||
    drag.landingApproachFrame === undefined ||
    drag.landingFrame === undefined
  ) {
    finishInteraction(token);
    return;
  }

  sprite.stop();
  sprite.onFrameChange = undefined;
  sprite.textures = [
    sprite.texture,
    textures[drag.landingApproachFrame],
    textures[drag.landingFrame],
  ];
  sprite.animationSpeed = drag.landingTransitionSpeed ?? 0.25;
  sprite.loop = false;
  sprite.onComplete = () => {
    sprite.onComplete = undefined;
    scheduleForToken(
      token,
      drag.landingHoldMs ?? 0,
      () => finishInteraction(token),
    );
  };
  sprite.gotoAndPlay(0);
};
```

Delete the shared `returnToIdleTimer` and every timeout that changes animation state without checking the active token.

- [ ] **Step 7: Wire left click and double click through the runtime**

Replace `getPetClickAction(activePetId, currentCount)` with:

```ts
const request =
  currentCount === 1
    ? { kind: "singleClick" as const, interruptible: true }
    : { kind: "doubleClick" as const, interruptible: true };
const result = requestInteraction(interactionRuntime.current, request);
interactionRuntime.current = result.state;
if (result.decision === "start") {
  playConfiguredInteraction(
    result.state.active.token,
    currentCount === 1
      ? activeInteractions.singleClick
      : activeInteractions.doubleClick,
  );
}
```

- [ ] **Step 8: Wire directional dragging**

Extend pointer state:

```ts
dragDirection?: DragDirectionState;
dragToken?: number;
```

When the pointer crosses the existing drag threshold, request the direct drag interaction once:

```ts
const dragRequest = requestInteraction(interactionRuntime.current, {
  kind: "drag",
  interruptible: true,
});
interactionRuntime.current = dragRequest.state;
if (dragRequest.decision !== "start") return;
pointer.dragToken = dragRequest.state.active.token;
playDragLoopForFacing(
  dragRequest.state.active.facing,
  true,
);
```

At that same transition, initialize direction tracking:

```ts
pointer.dragDirection = createDragDirectionState(
  interactionRuntime.current.active.facing,
  pointer.currentScreenX,
);
```

For each drag move after scale factor is available:

```ts
pointer.dragDirection = updateDragDirection(
  pointer.dragDirection,
  screenX,
  pointer.scaleFactor,
);
interactionRuntime.current = setInteractionFacing(
  interactionRuntime.current,
  pointer.dragDirection.facing,
);
playDragLoopForFacing(pointer.dragDirection.facing);
```

Only replace textures when facing actually changes; do not restart the drag loop for every pointer event.

On pointer release or cancellation, move the window one final time, clear `pointer.dragDirection`, and call:

```ts
if (pointer.dragToken !== undefined) {
  finishDragInteraction(pointer.dragToken);
  pointer.dragToken = undefined;
}
```

This preserves suan-bird's takeoff/loop/landing phases. Pets without declared landing frames hold their last drag frame only until the runtime switches back to idle; no crossfade is used.

- [ ] **Step 9: Wire right double click and remove left triple click**

Add:

```ts
const lastSecondaryClickAt = useRef<number | null>(null);

const handleSecondaryPointerDown = (
  event: ReactPointerEvent<HTMLElement>,
) => {
  const result = registerSecondaryClick(
    lastSecondaryClickAt.current,
    event.timeStamp,
  );
  lastSecondaryClickAt.current = result.lastClickAt;
  if (result.triggered) void beginManualUpdateCheck();
};
```

Call it from `handlePointerDown` when `event.button === 2`. Keep `onContextMenu` only as:

```ts
const handleContextMenu = (event: ReactMouseEvent<HTMLElement>) => {
  event.preventDefault();
};
```

Delete the `currentCount >= 3` update branch.

- [ ] **Step 10: Remove obsolete pet-id action functions**

Delete from `src/pet-core/interaction.ts` and their tests:

- `getPetIdleAnimationName`
- `getPetIdleBubbleText`
- `getPetDragStartAction`
- `getPetDragEndAction`
- `getPetClickAction`
- `getPetHoverEatingAction`
- `getPetCareReminderAction`
- `getPetIdleQuirkActions`
- `getPetDesktopIconInteractionAction`

Keep only shared geometry, pointer, desktop-icon target, and formatting helpers.

Also delete `RuntimeAnimationName`, `animationScales`, and `getPetIconHugSpritesheetPath()` usage. Animation names, scale, offsets, and alternate spritesheet paths now come only from the resolved manifest.

- [ ] **Step 11: Run focused and full frontend tests**

Run:

```powershell
npm test -- src/pet-core/interaction.test.ts src/pet-core/interactionRuntime.test.ts src/pet-core/dragDirection.test.ts src/pet-core/animationRows.test.ts src/pet-core/visual.test.ts
npm test
npm run build
```

Expected: focused tests pass, full test suite passes, and TypeScript/Vite build succeeds.

- [ ] **Step 12: Commit**

```powershell
git add -- src/App.tsx src/pet-core/interaction.ts src/pet-core/interaction.test.ts src/pet-core/animationRows.ts src/pet-core/visual.ts
git commit -m "feat: unify direct desktop pet interactions"
```

---

### Task 9: Integrate Care Reminder Priority and Deferral

**Files:**
- Modify: `src/App.tsx`
- Modify: `src/pet-core/careReminders.test.ts`

- [ ] **Step 1: Add a failing deferred-reminder test**

Add to `src/pet-core/careReminders.test.ts`:

```ts
test("records only the delivered reminder after deferral", () => {
  const delivered: string[] = [];
  const reminder = selectTimedCareReminder(
    new Date(2026, 5, 23, 12, 0),
    delivered,
  );

  expect(reminder?.key).toBe("2026-06-23:meal-lunch");
  expect(delivered).toEqual([]);
  expect(markCareReminderDelivered(delivered, reminder!.key)).toEqual([
    "2026-06-23:meal-lunch",
  ]);
});
```

- [ ] **Step 2: Run the focused test**

Run:

```powershell
npm test -- src/pet-core/careReminders.test.ts
```

Expected: PASS; this locks the rule that persistence occurs on actual playback, not on queueing.

- [ ] **Step 3: Replace reminder checks in `App.tsx`**

Initialize persisted state:

```ts
const careReminderState = useRef(readCareReminderState());
```

When a timed reminder is eligible:

```ts
const reminder = selectTimedCareReminder(
  new Date(nowTimestamp),
  careReminderState.current.deliveredKeys,
);
if (reminder) {
  const result = requestInteraction(interactionRuntime.current, {
    kind: "careReminder",
    interruptible: true,
    payloadKey: reminder.key,
    reminderKind: reminder.kind,
  });
  interactionRuntime.current = result.state;
  if (result.decision === "start") {
    playCareReminder(
      result.state.active.token,
      reminder.kind,
      reminder.key,
    );
    return;
  }
  if (result.decision === "queue") return;
}
```

Add one reminder playback adapter. It persists a timed key only when playback actually starts, resolves the pet-specific dialogue/bubble, and then delegates animation ownership to `playConfiguredInteraction()`:

```ts
const playCareReminder = (
  token: number,
  kind: PetReminderKind,
  key?: string,
) => {
  if (interactionRuntime.current.active.token !== token) return;
  if (key) {
    careReminderState.current = {
      deliveredKeys: markCareReminderDelivered(
        careReminderState.current.deliveredKeys,
        key,
      ),
    };
    writeCareReminderState(careReminderState.current);
  }

  const action = activeInteractions.reminders[kind];
  setBubbleText(
    action.dialogueEvent
      ? getBubbleTextForPet(
          activePetId,
          action.dialogueEvent,
          action.bubbleText ?? null,
        )
      : action.bubbleText ?? null,
  );
  if (action.sound) playPetSound(action.sound);
  playConfiguredInteraction(token, action);
};
```

Use the same runtime request for random eye-care and water reminders, but omit `payloadKey` because their next-fire timestamps already prevent immediate repetition.

- [ ] **Step 4: Start queued reminders after direct actions**

Add the queue adapter:

```ts
const playQueuedInteraction = (active: ActivePetInteraction) => {
  if (active.kind === "careReminder" && active.reminderKind) {
    playCareReminder(
      active.token,
      active.reminderKind,
      active.payloadKey,
    );
  }
};
```

Then replace Task 8's `finishInteraction()` body with:

```ts
const finishInteraction = (token: number) => {
  const completed = completeInteraction(interactionRuntime.current, token);
  interactionRuntime.current = completed.state;
  if (completed.decision === "stale") return;
  if (completed.decision === "start-queued") {
    playQueuedInteraction(completed.state.active);
    return;
  }
  playIdle(completed.state.active.token);
};
```

Random eye-care and water requests must also set `reminderKind` to `"eyeCare"` or `"water"` before they enter the runtime queue.

- [ ] **Step 5: Gate idle quirks and hover**

Before scheduling either:

```ts
if (interactionRuntime.current.active.kind !== "idle") return;
```

Use `activeInteractions.hover.enabled` rather than pet id. Confirm ds, ikun, and suan-bird never schedule hover.

- [ ] **Step 6: Run verification**

Run:

```powershell
npm test -- src/pet-core/careReminders.test.ts src/pet-core/interactionRuntime.test.ts src/pet-core/dialogue.test.ts
npm test
npm run build
```

Expected: all tests and build pass.

- [ ] **Step 7: Commit**

```powershell
git add -- src/App.tsx src/pet-core/careReminders.test.ts
git commit -m "feat: schedule prioritized pet care reminders"
```

---

### Task 10: Gate and Repair Desktop Icon Interactions

**Files:**
- Modify: `src/App.tsx`
- Modify: `src/pet-core/interaction.ts`
- Modify: `src/pet-core/interaction.test.ts`

- [ ] **Step 1: Add failing directional icon-position tests**

Add to `src/pet-core/interaction.test.ts`:

```ts
import { getDesktopIconPeekWindowPosition } from "./interaction";

test("places ds on the opposite side of a left-side icon", () => {
  expect(
    getDesktopIconPeekWindowPosition(
      { title: "Left", x: 100, y: 300, width: 74, height: 82 },
      "left",
      1,
    ),
  ).toEqual({ x: 139, y: 207 });
});

test("places ds on the left of a right-side icon", () => {
  expect(
    getDesktopIconPeekWindowPosition(
      { title: "Right", x: 400, y: 300, width: 74, height: 82 },
      "right",
      1,
    ),
  ).toEqual({ x: 280, y: 207 });
});
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
npm test -- src/pet-core/interaction.test.ts
```

Expected: FAIL because `getDesktopIconPeekWindowPosition()` is missing.

- [ ] **Step 3: Implement directional peek positioning**

Add to `src/pet-core/interaction.ts`:

```ts
export function getDesktopIconPeekWindowPosition(
  icon: DesktopIconBounds,
  iconSide: "left" | "right",
  scaleFactor = 1,
): { x: number; y: number } {
  const artwork = getDesktopIconArtworkBounds(icon);
  return iconSide === "left"
    ? {
        x: Math.round(artwork.x + artwork.width - 24 * scaleFactor),
        y: Math.round(artwork.y - 100 * scaleFactor),
      }
    : {
        x: Math.round(artwork.x - 132 * scaleFactor),
        y: Math.round(artwork.y - 100 * scaleFactor),
      };
}
```

- [ ] **Step 4: Gate probes by capability and idle state**

At the start of `probeDesktopIconInteraction()`:

```ts
const iconConfig = activeInteractions.desktopIcon;
if (!iconConfig.enabled) return;
if (interactionRuntime.current.active.kind !== "idle") return;
if (desktopIconProbeInFlight.current) return;
```

This explicitly disables ikun and suan-bird and prevents icon actions from interrupting reminders or direct actions.

- [ ] **Step 5: Resolve allowed side and positioning from the manifest**

Replace animation-name inference with:

```ts
const target = findDesktopIconTarget(
  petBounds,
  icons,
  undefined,
  iconConfig.allowedSide === "any"
    ? {}
    : { side: iconConfig.allowedSide },
);
```

Extend `DesktopIconTargetOptions.side` to `"any" | "left" | "right"` and update `findDesktopIconTarget()` to filter both directions.

For `positioning: "wrap"`, use `getDesktopIconWrapWindowPosition()`. For `positioning: "peek"`, determine target side relative to the pet and use `getDesktopIconPeekWindowPosition()`.

- [ ] **Step 6: Guarantee cleanup on every exit**

Create one adapter helper in `App.tsx`:

```ts
const finishDesktopIconInteraction = (token: number) => {
  restoreCursorEvents();
  iconHugLockedUntil.current = 0;
  const completed = completeInteraction(interactionRuntime.current, token);
  interactionRuntime.current = completed.state;
  if (completed.decision === "start-queued") {
    playQueuedInteraction(completed.state.active);
  } else {
    playIdle(completed.state.active.token);
  }
};
```

Call this helper after normal completion, positioning failure, asset failure, direct-interaction preemption, pet switch, platform open, and component cleanup.

- [ ] **Step 7: Run focused and Rust tests**

Run:

```powershell
npm test -- src/pet-core/interaction.test.ts src/pet-core/petInteractionManifest.test.ts src/pet-core/interactionRuntime.test.ts
cargo test
```

Expected: all tests pass; Rust still reports 2 passing desktop-icon fixture tests.

- [ ] **Step 8: Commit**

```powershell
git add -- src/App.tsx src/pet-core/interaction.ts src/pet-core/interaction.test.ts
git commit -m "fix: gate and clean up desktop icon interactions"
```

---

### Task 11: Integrate Manual Update Checks and Window Layout

**Files:**
- Modify: `src/App.tsx`
- Modify: `src/pet-core/platform.ts`
- Modify: `src/pet-core/platform.test.ts`

- [ ] **Step 1: Add failing update-window layout tests**

Add to `src/pet-core/platform.test.ts`:

```ts
import { UPDATE_WINDOW_SIZE } from "./platform";

test("uses a compact centered update confirmation window", () => {
  expect(UPDATE_WINDOW_SIZE).toEqual({ width: 460, height: 300 });
});
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
npm test -- src/pet-core/platform.test.ts
```

Expected: FAIL because `UPDATE_WINDOW_SIZE` is missing.

- [ ] **Step 3: Add update window size**

Modify `src/pet-core/platform.ts`:

```ts
export const UPDATE_WINDOW_SIZE: WindowSize = {
  width: 460,
  height: 300,
};
```

- [ ] **Step 4: Replace `checkForUpdates()` in `App.tsx`**

Add state:

```ts
const [updateState, setUpdateState] = useState<
  | { status: "idle" }
  | { status: "checking" }
  | Extract<UpdateCheckResult, { status: "available" }>
>({ status: "idle" });
const updateCheckInFlight = useRef(false);
const updatePromptToken = useRef<number | null>(null);
const modeBeforeUpdate = useRef<WindowMode>("pet");
```

Implement:

```ts
const beginManualUpdateCheck = async () => {
  if (updateCheckInFlight.current) return;
  updateCheckInFlight.current = true;
  setBubbleText("正在检查更新…");

  const currentVersion = await getCurrentAppVersion();
  const result = await checkForLatestRelease(currentVersion);
  updateCheckInFlight.current = false;

  if (result.status === "available") {
    const request = requestInteraction(interactionRuntime.current, {
      kind: "updatePrompt",
      interruptible: false,
    });
    interactionRuntime.current = request.state;
    if (request.decision !== "start") return;
    updatePromptToken.current = request.state.active.token;
    modeBeforeUpdate.current = windowMode.current;
    setUpdateState(result);
    return;
  }

  setBubbleText(
    result.status === "current"
      ? "当前已经是最新版本。"
      : result.message,
  );
};
```

- [ ] **Step 5: Remove startup update checking**

Delete:

```ts
const startupTimer = window.setTimeout(() => {
  void checkForUpdates(false);
}, 3000);
```

and its cleanup. Keep the tray `check-update` event but route it to `beginManualUpdateCheck()`.

- [ ] **Step 6: Add update window layout mode**

Change:

```ts
type WindowMode = "platform" | "pet" | "update";
```

When `updateState.status === "available"`:

- Capture pet position if the prior mode was pet.
- Resize to `UPDATE_WINDOW_SIZE`.
- Center on the current/primary monitor.
- Do not show the platform panel behind the dialog.

On cancel or confirmed URL open:

- Set `updateState` to idle.
- Complete `updatePromptToken.current`, set the ref back to `null`, and resume any queued reminder or idle through the common completion adapter.
- Restore platform size if the prompt came from platform mode.
- Restore pet size and last pet position if it came from pet mode.

- [ ] **Step 7: Render `UpdateDialog` and confirm before opening**

Render:

```tsx
{updateState.status === "available" && (
  <UpdateDialog
    currentVersion={updateState.currentVersion}
    latestVersion={updateState.latestVersion}
    notes={updateState.notes}
    onCancel={closeUpdatePrompt}
    onConfirm={() => {
      void openUrl(updateState.releaseUrl)
        .then(closeUpdatePrompt)
        .catch(() => setBubbleText("无法打开下载页面，请稍后再试。"));
    }}
  />
)}
```

Do not call `openUrl()` before the confirm handler.

- [ ] **Step 8: Run focused and full tests**

Run:

```powershell
npm test -- src/pet-update/updateCheck.test.ts src/pet-update/UpdateDialog.test.tsx src/pet-core/platform.test.ts src/pet-core/interaction.test.ts
npm test
npm run build
```

Expected: all tests and build pass.

- [ ] **Step 9: Commit**

```powershell
git add -- src/App.tsx src/pet-core/platform.ts src/pet-core/platform.test.ts
git commit -m "feat: confirm manual updates before opening releases"
```

---

### Task 12: Repair Xiaoju Icon Art and Generate Atlas QA

**Files:**
- Modify: `public/pets/xiaoju-cat/icon-hug.webp`
- Create: `public/pets/xiaoju-cat/qa/icon-hug-contact-sheet.png`
- Create: `public/pets/xiaoju-cat/qa/atlas-validation.json`
- Create: `public/pets/xiaoju-cat/README.md`
- Create: `scripts/validate-pet-atlases.py`
- Create: `src/pet-core/atlasValidation.test.ts`
- Update: existing QA JSON files under `public/pets/ikun/qa/`, `public/pets/ds/qa/`, and `public/pets/suan-bird/qa/`

- [ ] **Step 1: Write the failing QA metadata test**

Create `src/pet-core/atlasValidation.test.ts`:

```ts
import { describe, expect, test } from "vitest";
import xiaojuValidation from "../../public/pets/xiaoju-cat/qa/atlas-validation.json";

describe("pet atlas validation", () => {
  test("contains no transparent runtime frames", () => {
    expect(xiaojuValidation.emptyRuntimeFrames).toEqual([]);
  });

  test("keeps ordinary action body scale changes within the approved threshold", () => {
    expect(xiaojuValidation.maxOrdinaryBodyScaleDelta).toBeLessThanOrEqual(0.12);
  });

  test("ships a clean six-frame icon hug row", () => {
    expect(xiaojuValidation.iconHug).toMatchObject({
      frames: 6,
      emptyFrames: [],
      edgeArtifactPixels: 0,
    });
  });
});
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
npm test -- src/pet-core/atlasValidation.test.ts
```

Expected: FAIL because xiaoju QA metadata does not exist.

- [ ] **Step 3: Implement the shared Pillow validator**

Create `scripts/validate-pet-atlases.py` with:

```python
from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import median
from PIL import Image

CELL_WIDTH = 192
CELL_HEIGHT = 208
BASE_SCALE = 0.46


def alpha_bounds(cell: Image.Image) -> tuple[int, int, int, int] | None:
    return cell.getchannel("A").getbbox()


def validate(package_dir: Path) -> dict:
    manifest = json.loads((package_dir / "pet.json").read_text(encoding="utf-8"))
    sources: dict[str, Image.Image] = {}
    empty_runtime_frames: list[str] = []
    ordinary_animation_heights: list[float] = []
    icon_hug_result = {
        "frames": 0,
        "emptyFrames": [],
        "edgeArtifactPixels": 0,
    }

    for animation_name, spec in manifest["animations"].items():
        source_path = spec.get("spritesheetPath", manifest["spritesheetPath"])
        source = sources.setdefault(
            source_path,
            Image.open(package_dir / source_path).convert("RGBA"),
        )
        frame_heights: list[float] = []
        for frame in range(spec["frames"]):
            cell = source.crop(
                (
                    frame * CELL_WIDTH,
                    spec["row"] * CELL_HEIGHT,
                    (frame + 1) * CELL_WIDTH,
                    (spec["row"] + 1) * CELL_HEIGHT,
                )
            )
            bounds = alpha_bounds(cell)
            if bounds is None:
                empty_runtime_frames.append(f"{animation_name}:{frame}")
                if animation_name == "iconHug":
                    icon_hug_result["emptyFrames"].append(frame)
                continue
            height = bounds[3] - bounds[1]
            frame_heights.append(height * BASE_SCALE * spec.get("scale", 1))

            if animation_name == "iconHug":
                alpha = cell.getchannel("A")
                border = 3
                edge_pixels = 0
                for y in range(CELL_HEIGHT):
                    for x in range(CELL_WIDTH):
                        if (
                            x < border
                            or y < border
                            or x >= CELL_WIDTH - border
                            or y >= CELL_HEIGHT - border
                        ) and alpha.getpixel((x, y)) > 0:
                            edge_pixels += 1
                icon_hug_result["edgeArtifactPixels"] += edge_pixels

        if frame_heights and spec["visualClass"] == "ordinary":
            ordinary_animation_heights.append(median(frame_heights))
        if animation_name == "iconHug":
            icon_hug_result["frames"] = spec["frames"]

    ordinary_median = median(ordinary_animation_heights)
    max_delta = max(
        abs(height - ordinary_median) / ordinary_median
        for height in ordinary_animation_heights
    )

    return {
        "emptyRuntimeFrames": empty_runtime_frames,
        "maxOrdinaryBodyScaleDelta": round(max_delta, 4),
        "iconHug": icon_hug_result,
    }


if __name__ == "__main__":
    package = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(validate(package), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
```

The validator relies only on the manifest's explicit `visualClass`; do not add pet-id exceptions to the script.

- [ ] **Step 4: Replace the xiaoju icon-hug asset**

Use the installed `hatch-pet` skill, which composes `imagegen`, to rebuild six transparent frames based on the current orange-cat character:

- Keep the cat centered in each 192×208 cell.
- Show forepaws wrapping around an empty central space sized for a desktop icon.
- Do not draw a cardboard box, colored rectangle, text, shadow rectangle, or background.
- Keep all unused pixels fully transparent.
- Preserve the orange tabby face and proportions from the main xiaoju atlas.
- Assemble exactly six frames into a 1152×208 WebP.

Generate `public/pets/xiaoju-cat/qa/icon-hug-contact-sheet.png` with cell boundaries and frame numbers for visual review.

- [ ] **Step 5: Generate QA JSON for every pet**

Run:

```powershell
python scripts/validate-pet-atlases.py public/pets/xiaoju-cat public/pets/xiaoju-cat/qa/atlas-validation.json
python scripts/validate-pet-atlases.py public/pets/ikun public/pets/ikun/qa/atlas-validation.json
python scripts/validate-pet-atlases.py public/pets/ds public/pets/ds/qa/atlas-validation.json
python scripts/validate-pet-atlases.py public/pets/suan-bird public/pets/suan-bird/qa/atlas-validation.json
```

Expected: all four JSON files report no empty runtime frames. Intentional jump, crouch, flight, and sleep families are labeled separately from ordinary size checks.

- [ ] **Step 6: Document package behavior**

Create/update each package README with:

- Effective animation row and frame counts.
- Left/right drag strategy.
- Hover enabled state.
- Desktop icon enabled state.
- Reminder action or idle fallback for all four reminder kinds.
- Any intentional scale/baseline exception.

- [ ] **Step 7: Run QA tests**

Run:

```powershell
npm test -- src/pet-core/atlasValidation.test.ts src/pet-core/petInteractionManifest.test.ts src/pet-core/petAssets.test.ts
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add -- scripts/validate-pet-atlases.py src/pet-core/atlasValidation.test.ts public/pets/xiaoju-cat public/pets/ikun/qa/atlas-validation.json public/pets/ds/qa/atlas-validation.json public/pets/suan-bird/qa/atlas-validation.json public/pets/ikun/README.md public/pets/ds/README.md public/pets/suan-bird/README.md
git commit -m "fix: validate and repair pet animation assets"
```

---

### Task 13: End-to-End Interaction Verification

**Files:**
- Verify: `src/App.tsx`
- Verify: all four `public/pets/<pet-id>/pet.json`
- Verify: all four runtime spritesheets and xiaoju icon-hug spritesheet
- Modify only if verification finds a defect: relevant source, manifest, or pet-local QA file

- [ ] **Step 1: Run the complete automated suite**

Run:

```powershell
npm test
npm run build
cargo test
cargo check
```

Expected:

- All Vitest files pass.
- TypeScript and Vite build succeed.
- Rust reports 2 or more passing tests and no failures.
- Cargo check finishes without errors.

- [ ] **Step 2: Verify browser-preview safety**

Run:

```powershell
npm run dev
```

Open `http://127.0.0.1:1420` in the in-app browser and verify:

- The page loads without Tauri API exceptions.
- All four pets can be selected.
- Update dialog component renders in a fixture-driven preview path.
- ikun and suan-bird do not attempt desktop-icon actions.
- No console errors appear while switching pets.

- [ ] **Step 3: Verify Tauri direct interactions**

Run:

```powershell
npm run tauri -- dev
```

For each pet, record or capture:

1. Idle → single click → idle.
2. Idle → double click → idle.
3. Drag left → correct facing → landing → idle.
4. Drag right → correct facing → landing → idle.
5. A direct interaction preempting an idle quirk.
6. A queued reminder playing once after a direct interaction.

Expected:

- No transparent frames.
- No stale timer returns.
- No unintended body-size pop beyond the approved pose exceptions.
- No direction flicker during small pointer jitter.

- [ ] **Step 4: Verify desktop icon capability matrix on Windows**

Use a visible desktop with at least one icon on each side:

- Xiaoju triggers clean icon wrapping, restores cursor events, returns to idle, and can trigger again after cooldown.
- ds peeks from the correct side, returns to idle, and can trigger again.
- ikun remains idle near icons.
- suan-bird remains idle near icons.

- [ ] **Step 5: Verify manual update flow**

Use an injectable release fixture or temporary local fetch stub:

- One right click does nothing except suppress the system menu.
- Two right clicks within 350ms start one request.
- Repeated double clicks while checking do not start another request.
- A newer version opens the confirmation dialog.
- Cancel restores the previous window mode and position.
- Confirm opens the fixture Release URL and restores the previous window mode.
- Equal and older releases do not show the confirmation dialog.
- Tray menu uses the same flow.
- Startup performs no update request.

- [ ] **Step 6: Verify care reminders**

Use injected clocks and shortened random timers in a development-only fixture:

- Every pet displays eye-care, water, meal, and sleep text.
- Dedicated reminder animations play where declared.
- Idle fallback is used where no relevant animation exists.
- A persisted meal/sleep slot is not repeated after application restart.
- Missed reminders do not replay in a burst.

- [ ] **Step 7: Run final diff and package checks**

Run:

```powershell
git diff --check
git status --short --branch
rg -n '"/pets/|[A-Z]:\\\\' src public/pets --glob '!**/*.webp' --glob '!**/*.png'
```

Expected:

- No whitespace errors.
- Only intended implementation and QA files are modified.
- No new hardcoded pet URLs or absolute Windows asset paths.

- [ ] **Step 8: Commit verification fixes**

If verification required changes, stage the in-scope implementation and QA paths:

```powershell
git add -- src/App.tsx src/App.css src/pet-core src/pet-update scripts/validate-pet-atlases.py public/pets/xiaoju-cat public/pets/ikun public/pets/ds public/pets/suan-bird
git commit -m "fix: complete pet interaction verification"
```

If no verification changes were needed, do not create an empty commit.
