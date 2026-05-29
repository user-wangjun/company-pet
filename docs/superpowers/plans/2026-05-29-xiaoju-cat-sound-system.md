# Xiaoju Cat Sound System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a quiet, pet-owned sound system for `xiaoju-cat` so core actions can play short randomized sound cues without hardcoding pet asset paths in platform code.

**Architecture:** Extend the pet manifest with optional sound cues, add a focused `pet-core` sound module for path resolution, random selection, cooldowns, and HTML audio playback, then wire existing `App.tsx` state transitions to named sound events. All audio assets and cue names live inside `public/pets/xiaoju-cat/`; platform code only consumes manifest data through `resolvePetAssetUrl()`.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Tauri WebView, `HTMLAudioElement`, static pet assets under `public/pets/`.

---

## Scope Check

This spec is one subsystem: sound playback for the existing `xiaoju-cat` package. It does not require a new settings panel, pet picker changes, system tray changes, or platform-wide audio UI. The plan includes a small `soundEnabled` / master-volume capable engine so the later settings panel can use it, but no visible settings are added in this pass.

## File Structure

- Modify `src/pet-core/petAssets.ts`
  - Add manifest sound cue types and optional `sounds` field.
  - Keep path resolution generic and pet-id based.
- Modify `src/pet-core/petAssets.test.ts`
  - Verify sound cue paths stay relative to the pet package.
  - Keep catalog tests compatible with manifests that include optional `sounds`.
- Create `src/pet-core/sound.ts`
  - Pure sound cue resolution, cooldown defaults, random cue selection, and a small audio player abstraction.
  - Accept injected `audioFactory`, `random`, and `now` for deterministic tests.
- Create `src/pet-core/sound.test.ts`
  - Cover path resolution, random selection, preloading, cooldown, disabled mode, active-sound interruption, and rejected audio playback.
- Modify `src/App.tsx`
  - Create one pet sound player.
  - Sync it with the active pet manifest.
  - Trigger sound events from existing animation/action transitions.
- Modify `public/pets/xiaoju-cat/pet.json`
  - Add `sounds` entries with relative paths only.
- Create `public/pets/xiaoju-cat/sounds/*.wav`
  - Add deterministic starter cues that satisfy the current behavior and can later be replaced one-for-one by polished `.webm` or `.ogg` assets.

---

### Task 1: Extend Pet Manifest Types And Tests

**Files:**
- Modify: `src/pet-core/petAssets.ts`
- Modify: `src/pet-core/petAssets.test.ts`

- [ ] **Step 1: Write failing tests for sound manifest compatibility**

Update `src/pet-core/petAssets.test.ts` imports to include `type PetManifest`, then add the two tests below inside `describe("pet asset paths", () => { ... })`.

```ts
import type { PetManifest } from "./petAssets";
```

```ts
  test("keeps sound cue paths relative to the active pet package", () => {
    expect(resolvePetAssetUrl("xiaoju-cat", "sounds/tickle-hm-1.wav")).toBe(
      "/pets/xiaoju-cat/sounds/tickle-hm-1.wav",
    );
    expect(resolvePetAssetUrl("xiaoju-cat", "\\sounds\\drag-meow-1.wav")).toBe(
      "/pets/xiaoju-cat/sounds/drag-meow-1.wav",
    );
  });

  test("allows pet manifests to declare optional sound cues", () => {
    const manifest: PetManifest = {
      id: "xiaoju-cat",
      displayName: "小橘",
      description: "一只橘黄色毛绒小猫咪。",
      spritesheetPath: "spritesheet-scruff.webp",
      sounds: {
        tickle: [
          { path: "sounds/tickle-hm-1.wav", volume: 0.45 },
          { path: "sounds/tickle-hmph-1.wav" },
        ],
      },
    };

    expect(manifest.sounds?.tickle).toEqual([
      { path: "sounds/tickle-hm-1.wav", volume: 0.45 },
      { path: "sounds/tickle-hmph-1.wav" },
    ]);
  });
```

Also change the existing catalog assertion from `toEqual([...])` to `toMatchObject([...])` so it remains correct after the built-in manifest later gains `sounds`.

```ts
    expect(
      createPetCatalog(
        [DEFAULT_PET_ID],
        { [DEFAULT_PET_ID]: builtInPetManifest },
        DEFAULT_PET_ID,
      ),
    ).toMatchObject([
      {
        id: DEFAULT_PET_ID,
        displayName: "小橘",
        description:
          "一只橘黄色毛绒小猫咪，会睡觉、抓鱼、吃鱼、跳来跳去，也会陪你等结果。",
        spritesheetPath: "spritesheet-scruff.webp",
        manifestUrl: "/pets/xiaoju-cat/pet.json",
        previewUrl: "/pets/xiaoju-cat/spritesheet-scruff.webp",
        isActive: true,
      },
    ]);
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
npm test -- src/pet-core/petAssets.test.ts
```

Expected: TypeScript/Vitest fails because `PetManifest` does not yet allow `sounds`.

- [ ] **Step 3: Add sound cue types to `petAssets.ts`**

Update `src/pet-core/petAssets.ts` so the manifest types include optional sound cue data.

```ts
export const DEFAULT_PET_ID = "xiaoju-cat";

const PETS_BASE_PATH = "/pets";
const PET_INDEX_FILE = "index.json";

export type PetSoundCue = {
  path: string;
  volume?: number;
};

export type PetManifestSounds = Record<string, PetSoundCue[]>;

export type PetManifest = {
  id: string;
  displayName: string;
  description: string;
  spritesheetPath: string;
  previewPath?: string;
  sounds?: PetManifestSounds;
};
```

Keep the rest of `petAssets.ts` unchanged.

- [ ] **Step 4: Run the focused test and verify it passes**

Run:

```powershell
npm test -- src/pet-core/petAssets.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add -- src/pet-core/petAssets.ts src/pet-core/petAssets.test.ts
git commit -m "feat: extend pet manifest sound metadata"
```

---

### Task 2: Add Tested Sound Selection And Playback Core

**Files:**
- Create: `src/pet-core/sound.ts`
- Create: `src/pet-core/sound.test.ts`

- [ ] **Step 1: Write failing tests for sound rules**

Create `src/pet-core/sound.test.ts` with this content.

```ts
import { describe, expect, test, vi } from "vitest";
import {
  choosePetSoundCue,
  createPetSoundPlayer,
  getPetSoundCooldownMs,
  resolvePetSoundCues,
  type PetAudioElement,
} from "./sound";

type FakeAudio = PetAudioElement & {
  url: string;
  load: ReturnType<typeof vi.fn>;
  pause: ReturnType<typeof vi.fn>;
  play: ReturnType<typeof vi.fn>;
};

function createFakeAudioFactory(created: FakeAudio[]) {
  return (url: string): FakeAudio => {
    const audio: FakeAudio = {
      url,
      preload: "",
      volume: 1,
      currentTime: 9,
      load: vi.fn(),
      pause: vi.fn(),
      play: vi.fn(() => Promise.resolve()),
    };

    created.push(audio);
    return audio;
  };
}

describe("pet sound rules", () => {
  test("resolves sound cue URLs under the active pet package", () => {
    expect(
      resolvePetSoundCues(
        "xiaoju-cat",
        {
          tickle: [
            { path: "sounds/tickle-hm-1.wav", volume: 0.45 },
            { path: "" },
          ],
        },
        "tickle",
      ),
    ).toEqual([
      {
        path: "sounds/tickle-hm-1.wav",
        volume: 0.45,
        url: "/pets/xiaoju-cat/sounds/tickle-hm-1.wav",
      },
    ]);
  });

  test("chooses a deterministic random cue", () => {
    const cues = [
      { path: "sounds/a.wav", url: "/pets/xiaoju-cat/sounds/a.wav" },
      { path: "sounds/b.wav", url: "/pets/xiaoju-cat/sounds/b.wav" },
      { path: "sounds/c.wav", url: "/pets/xiaoju-cat/sounds/c.wav" },
    ];

    expect(choosePetSoundCue(cues, () => 0)?.path).toBe("sounds/a.wav");
    expect(choosePetSoundCue(cues, () => 0.5)?.path).toBe("sounds/b.wav");
    expect(choosePetSoundCue(cues, () => 0.99)?.path).toBe("sounds/c.wav");
    expect(choosePetSoundCue([], () => 0.5)).toBeNull();
  });

  test("preloads all manifest sounds when the active pet changes", () => {
    const created: FakeAudio[] = [];
    const player = createPetSoundPlayer({
      audioFactory: createFakeAudioFactory(created),
    });

    player.setManifest("xiaoju-cat", {
      tickle: [
        { path: "sounds/tickle-hm-1.wav" },
        { path: "sounds/tickle-hmph-1.wav" },
      ],
      drag: [{ path: "sounds/drag-meow-1.wav" }],
    });

    expect(created.map((audio) => audio.url)).toEqual([
      "/pets/xiaoju-cat/sounds/tickle-hm-1.wav",
      "/pets/xiaoju-cat/sounds/tickle-hmph-1.wav",
      "/pets/xiaoju-cat/sounds/drag-meow-1.wav",
    ]);
    expect(created.every((audio) => audio.preload === "auto")).toBe(true);
    expect(created.every((audio) => audio.load.mock.calls.length === 1)).toBe(
      true,
    );
  });

  test("plays one cue, applies volume, respects cooldown, and interrupts active sound", () => {
    const created: FakeAudio[] = [];
    let now = 1000;
    const player = createPetSoundPlayer({
      audioFactory: createFakeAudioFactory(created),
      random: () => 0.99,
      now: () => now,
      masterVolume: 0.5,
    });

    player.setManifest("xiaoju-cat", {
      tickle: [
        { path: "sounds/tickle-hm-1.wav", volume: 0.4 },
        { path: "sounds/tickle-hmph-1.wav", volume: 0.6 },
      ],
    });

    expect(player.play("tickle")).toBe(true);
    expect(created[1].currentTime).toBe(0);
    expect(created[1].volume).toBe(0.3);
    expect(created[1].play).toHaveBeenCalledTimes(1);

    now += 100;
    expect(player.play("tickle")).toBe(false);
    expect(created[1].play).toHaveBeenCalledTimes(1);

    now += getPetSoundCooldownMs("tickle");
    expect(player.play("tickle")).toBe(true);
    expect(created[1].pause).toHaveBeenCalledTimes(1);
    expect(created[1].play).toHaveBeenCalledTimes(2);
  });

  test("skips playback when disabled or when an event has no cues", () => {
    const created: FakeAudio[] = [];
    const player = createPetSoundPlayer({
      audioFactory: createFakeAudioFactory(created),
    });

    player.setManifest("xiaoju-cat", {
      tickle: [{ path: "sounds/tickle-hm-1.wav" }],
    });
    player.setEnabled(false);

    expect(player.play("tickle")).toBe(false);
    player.setEnabled(true);
    expect(player.play("missing")).toBe(false);
  });

  test("handles rejected browser audio playback without throwing", () => {
    const created: FakeAudio[] = [];
    const player = createPetSoundPlayer({
      audioFactory: (url) => {
        const audio = createFakeAudioFactory(created)(url);
        audio.play = vi.fn(() => Promise.reject(new Error("blocked")));
        return audio;
      },
    });

    player.setManifest("xiaoju-cat", {
      tickle: [{ path: "sounds/tickle-hm-1.wav" }],
    });

    expect(() => player.play("tickle")).not.toThrow();
  });
});
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```powershell
npm test -- src/pet-core/sound.test.ts
```

Expected: FAIL because `src/pet-core/sound.ts` does not exist.

- [ ] **Step 3: Implement `src/pet-core/sound.ts`**

Create `src/pet-core/sound.ts` with this content.

```ts
import {
  resolvePetAssetUrl,
  type PetManifestSounds,
  type PetSoundCue,
} from "./petAssets";

export const PET_SOUND_DEFAULT_VOLUME = 0.45;
export const PET_SOUND_DEFAULT_COOLDOWN_MS = 1200;

const PET_SOUND_COOLDOWNS_MS: Record<string, number> = {
  idle: 30000,
  tickle: 1200,
  drag: 2000,
  drag_end: 1200,
  fishChase: 1200,
  fishEat: 1200,
  crouchAlert: 2500,
  hugFish: 2500,
  gnawFish: 2500,
  iconHug: 2500,
  care_reminder: 5000,
};

export type PetSoundEvent =
  | "idle"
  | "tickle"
  | "drag"
  | "drag_end"
  | "fishChase"
  | "fishEat"
  | "crouchAlert"
  | "hugFish"
  | "gnawFish"
  | "iconHug"
  | "care_reminder";

export type ResolvedPetSoundCue = PetSoundCue & {
  url: string;
};

export type PetAudioElement = {
  preload: string;
  volume: number;
  currentTime: number;
  load?: () => void;
  pause: () => void;
  play: () => Promise<void> | void;
};

type PetSoundPlayerOptions = {
  audioFactory?: (url: string) => PetAudioElement;
  random?: () => number;
  now?: () => number;
  masterVolume?: number;
  enabled?: boolean;
};

export type PetSoundPlayer = {
  setManifest: (petId: string, sounds: PetManifestSounds | undefined) => void;
  setEnabled: (nextEnabled: boolean) => void;
  setMasterVolume: (nextVolume: number) => void;
  play: (eventName: string) => boolean;
  clear: () => void;
};

function defaultAudioFactory(url: string): PetAudioElement {
  return new Audio(url);
}

export function getPetSoundCooldownMs(eventName: string): number {
  return PET_SOUND_COOLDOWNS_MS[eventName] ?? PET_SOUND_DEFAULT_COOLDOWN_MS;
}

export function clampPetSoundVolume(volume: number | undefined): number {
  if (volume === undefined || !Number.isFinite(volume)) {
    return PET_SOUND_DEFAULT_VOLUME;
  }

  return Math.min(1, Math.max(0, volume));
}

export function resolvePetSoundCues(
  petId: string,
  sounds: PetManifestSounds | undefined,
  eventName: string,
): ResolvedPetSoundCue[] {
  return (sounds?.[eventName] ?? [])
    .filter((cue) => cue.path.trim().length > 0)
    .map((cue) => ({
      ...cue,
      url: resolvePetAssetUrl(petId, cue.path),
    }));
}

export function choosePetSoundCue(
  cues: ResolvedPetSoundCue[],
  random = Math.random,
): ResolvedPetSoundCue | null {
  if (cues.length === 0) return null;

  const index = Math.min(cues.length - 1, Math.floor(random() * cues.length));
  return cues[index] ?? cues[0];
}

export function createPetSoundPlayer({
  audioFactory = defaultAudioFactory,
  random = Math.random,
  now = Date.now,
  masterVolume: initialMasterVolume = 1,
  enabled: initialEnabled = true,
}: PetSoundPlayerOptions = {}): PetSoundPlayer {
  let petId = "";
  let sounds: PetManifestSounds | undefined;
  let enabled = initialEnabled;
  let masterVolume = clampPetSoundVolume(initialMasterVolume);
  let activeAudio: PetAudioElement | null = null;

  const audioByUrl = new Map<string, PetAudioElement>();
  const lastPlayedAtByEvent = new Map<string, number>();

  const getAudio = (cue: ResolvedPetSoundCue): PetAudioElement => {
    const cached = audioByUrl.get(cue.url);
    if (cached) return cached;

    const audio = audioFactory(cue.url);
    audio.preload = "auto";
    audio.volume = clampPetSoundVolume(cue.volume) * masterVolume;
    audio.load?.();
    audioByUrl.set(cue.url, audio);
    return audio;
  };

  const stopActiveAudio = () => {
    if (!activeAudio) return;
    activeAudio.pause();
    activeAudio = null;
  };

  return {
    setManifest(nextPetId, nextSounds) {
      stopActiveAudio();
      audioByUrl.clear();
      lastPlayedAtByEvent.clear();
      petId = nextPetId;
      sounds = nextSounds;

      if (!sounds) return;

      for (const eventName of Object.keys(sounds)) {
        for (const cue of resolvePetSoundCues(petId, sounds, eventName)) {
          getAudio(cue);
        }
      }
    },

    setEnabled(nextEnabled) {
      enabled = nextEnabled;
      if (!enabled) {
        stopActiveAudio();
      }
    },

    setMasterVolume(nextVolume) {
      masterVolume = clampPetSoundVolume(nextVolume);
    },

    play(eventName) {
      if (!enabled || !petId) return false;

      const playedAt = now();
      const lastPlayedAt = lastPlayedAtByEvent.get(eventName);
      if (
        lastPlayedAt !== undefined &&
        playedAt - lastPlayedAt < getPetSoundCooldownMs(eventName)
      ) {
        return false;
      }

      const cue = choosePetSoundCue(
        resolvePetSoundCues(petId, sounds, eventName),
        random,
      );
      if (!cue) return false;

      const audio = getAudio(cue);
      stopActiveAudio();

      audio.currentTime = 0;
      audio.volume = clampPetSoundVolume(cue.volume) * masterVolume;
      activeAudio = audio;
      lastPlayedAtByEvent.set(eventName, playedAt);

      try {
        const result = audio.play();
        if (result instanceof Promise) {
          result.catch(() => {});
        }
      } catch {
        // Browser audio can be blocked by policy; animation should continue.
      }

      return true;
    },

    clear() {
      stopActiveAudio();
      audioByUrl.clear();
      lastPlayedAtByEvent.clear();
      petId = "";
      sounds = undefined;
    },
  };
}
```

- [ ] **Step 4: Run sound tests and fix only discrepancies in this task**

Run:

```powershell
npm test -- src/pet-core/sound.test.ts
```

Expected: PASS.

- [ ] **Step 5: Run the existing pet asset tests**

Run:

```powershell
npm test -- src/pet-core/petAssets.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add -- src/pet-core/sound.ts src/pet-core/sound.test.ts
git commit -m "feat: add pet sound playback core"
```

---

### Task 3: Wire Sounds Into Existing Xiaoju Actions

**Files:**
- Modify: `src/App.tsx`

- [ ] **Step 1: Add sound imports**

In `src/App.tsx`, add this import near the existing `pet-core` imports.

```ts
import {
  createPetSoundPlayer,
  type PetSoundEvent,
  type PetSoundPlayer,
} from "./pet-core/sound";
```

- [ ] **Step 2: Create one sound player ref**

Inside `function App()`, near the existing refs, add:

```ts
  const soundPlayerRef = useRef<PetSoundPlayer | null>(null);
  if (soundPlayerRef.current === null) {
    soundPlayerRef.current = createPetSoundPlayer();
  }
```

- [ ] **Step 3: Sync the player with the active pet manifest**

After `const activePet = petCatalog.find((pet) => pet.id === activePetId);`, add:

```ts
  const activePetManifest = petManifestsById[activePetId];
```

After the catalog-loading effect, add this effect:

```ts
  useEffect(() => {
    soundPlayerRef.current?.setManifest(activePetId, activePetManifest?.sounds);

    return () => {
      soundPlayerRef.current?.clear();
    };
  }, [activePetId, activePetManifest]);
```

- [ ] **Step 4: Add a local sound trigger helper**

Near the existing `recordInteraction()` helper or before `handleClicks`, add:

```ts
  const playPetSound = (eventName: PetSoundEvent) => {
    soundPlayerRef.current?.play(eventName);
  };
```

- [ ] **Step 5: Trigger sounds from existing interactions**

Apply these targeted changes in `src/App.tsx`.

In the single-click branch of `handleClicks()`:

```ts
      recordInteraction("click");
      setBubbleText("哼，还行。");
      playPetSound("tickle");
      playAnimation("tickle", 1000);
```

In `playHoverFishSequence()` before the chase animation:

```ts
    setBubbleText("鱼！");
    recordInteraction("fish_chase");
    playPetSound("fishChase");
    playAnimation(chaseAnimation);
```

In `playHoverFishSequence()` before the eat animation:

```ts
      setBubbleText("吃到了。");
      recordInteraction("fish_eat");
      playPetSound("fishEat");
      playAnimation(eatAnimation);
```

In `movePress()`, inside the block that starts dragging:

```ts
      pointer.dragging = true;
      clearHoverEatTimer();
      recordInteraction("drag_start");
      setBubbleText("喵？！你要带我去哪？");
      playPetSound("drag");
      playAnimation("drag");
```

In `finishPress()`, when drag ends:

```ts
    recordInteraction("drag_end");
    setBubbleText("放这儿也行。");
    playPetSound("drag_end");
    playAnimation("idle", 900);
```

In `probeDesktopIconInteraction()`, for the eye-care reminder:

```ts
      recordInteraction("eye_care_reminder");
      setBubbleText("看屏幕太久啦，陪小橘眺望一下窗外，放松一下眼睛吧~ 👀");
      playPetSound("care_reminder");
      playAnimation("idle", 8000);
```

In `probeDesktopIconInteraction()`, for the water reminder:

```ts
      recordInteraction("water_care_reminder");
      setBubbleText("（吸溜）主人，该喝杯水润润嗓子啦，不要一直盯着屏幕喵！🥛");
      playPetSound("care_reminder");
      playAnimation("fishChase", 8000);
```

In the idle quirk list, add a `sound` field to each entry:

```ts
          {
            text: "（砸嘴）……梦见超大金枪鱼了喵 🐟",
            animation: "fishEat" as AnimationName,
            sound: "fishEat" as PetSoundEvent,
            duration: 2500,
          },
          {
            text: "（幸福地翻个身）~ 换个姿势继续睡喵…… 🐾",
            animation: "tickle" as AnimationName,
            sound: "idle" as PetSoundEvent,
            duration: 2000,
          },
          {
            text: "（亲昵地蹭了蹭）……主人工作辛苦啦，小橘陪着你喵 💤",
            animation: "tickle" as AnimationName,
            sound: "idle" as PetSoundEvent,
            duration: 2000,
          },
          {
            text: "（趴下警觉喵喵叫）~ 好像有大鱼的气味？🐾",
            animation: "crouchAlert" as AnimationName,
            sound: "crouchAlert" as PetSoundEvent,
            duration: 2500,
          },
          {
            text: "（抱着小鱼撒娇）~ 嘿嘿，这只小鱼是橘橘的宝贝！🐟",
            animation: "hugFish" as AnimationName,
            sound: "hugFish" as PetSoundEvent,
            duration: 3000,
          },
          {
            text: "（美滋滋地坐着嚼鱼）~ 金枪鱼味儿的玩具鱼，真香！🐾",
            animation: "gnawFish" as AnimationName,
            sound: "gnawFish" as PetSoundEvent,
            duration: 2500,
          },
```

After `const chosen = quirks[Math.floor(Math.random() * quirks.length)];`, trigger the chosen sound:

```ts
        setBubbleText(chosen.text);
        playPetSound(chosen.sound);
        playAnimation(chosen.animation, chosen.duration);
```

In the desktop icon wrap success chain, before the icon hug animation:

```ts
            recordInteraction("desktop_icon_hug_pose");
            playPetSound("iconHug");
            if (playAnimation(getDesktopIconHugAnimationName())) {
```

- [ ] **Step 6: Typecheck and build**

Run:

```powershell
npm run build
```

Expected: PASS. If TypeScript complains that `activePetManifest` can be undefined, keep the optional chain exactly as `activePetManifest?.sounds`.

- [ ] **Step 7: Commit Task 3**

Run:

```powershell
git add -- src/App.tsx
git commit -m "feat: play xiaoju sounds from pet actions"
```

---

### Task 4: Add Xiaoju Sound Manifest Entries And Starter Assets

**Files:**
- Modify: `public/pets/xiaoju-cat/pet.json`
- Create: `public/pets/xiaoju-cat/sounds/*.wav`
- Modify: `src/pet-core/petAssets.test.ts`

- [ ] **Step 1: Generate deterministic starter WAV files**

Run this PowerShell command from the repo root. It creates short synthesized starter cues under the pet package. These are real audio files, not empty placeholders; later polished `.webm` or `.ogg` files can replace them by updating `pet.json`.

```powershell
@'
const fs = require("node:fs");
const path = require("node:path");

const outDir = path.join("public", "pets", "xiaoju-cat", "sounds");
fs.mkdirSync(outDir, { recursive: true });

const sampleRate = 44100;
let seed = 13640;

function random() {
  seed = (seed * 1664525 + 1013904223) >>> 0;
  return seed / 0x100000000;
}

function envelope(position) {
  const attack = Math.min(1, position / 0.12);
  const release = Math.min(1, (1 - position) / 0.2);
  return Math.max(0, Math.min(attack, release));
}

function renderCue({
  duration,
  startFreq,
  endFreq = startFreq,
  gain = 0.26,
  wobble = 0,
  noise = 0,
  chirps = 1,
}) {
  const sampleCount = Math.max(1, Math.round(duration * sampleRate));
  const samples = new Float32Array(sampleCount);
  let phase = 0;

  for (let index = 0; index < sampleCount; index += 1) {
    const t = index / sampleRate;
    const position = index / sampleCount;
    const chirpPosition = (position * chirps) % 1;
    const frequency =
      startFreq +
      (endFreq - startFreq) * chirpPosition +
      Math.sin(t * Math.PI * 2 * wobble) * wobble * 4;

    phase += (Math.PI * 2 * frequency) / sampleRate;
    const shaped = Math.sin(phase) * 0.82 + Math.sin(phase * 2.01) * 0.18;
    const noiseValue = (random() * 2 - 1) * noise;
    samples[index] = Math.max(
      -1,
      Math.min(1, (shaped + noiseValue) * gain * envelope(chirpPosition)),
    );
  }

  return samples;
}

function toWav(samples) {
  const buffer = Buffer.alloc(44 + samples.length * 2);
  buffer.write("RIFF", 0);
  buffer.writeUInt32LE(36 + samples.length * 2, 4);
  buffer.write("WAVE", 8);
  buffer.write("fmt ", 12);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate * 2, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write("data", 36);
  buffer.writeUInt32LE(samples.length * 2, 40);

  for (let index = 0; index < samples.length; index += 1) {
    buffer.writeInt16LE(Math.round(samples[index] * 32767), 44 + index * 2);
  }

  return buffer;
}

const cues = {
  "idle-purr-1.wav": { duration: 0.42, startFreq: 130, endFreq: 155, gain: 0.16, wobble: 7, noise: 0.04, chirps: 2 },
  "idle-breath-1.wav": { duration: 0.32, startFreq: 180, endFreq: 150, gain: 0.1, wobble: 3, noise: 0.08 },
  "idle-meow-soft-1.wav": { duration: 0.28, startFreq: 520, endFreq: 420, gain: 0.2, wobble: 5 },
  "tickle-hm-1.wav": { duration: 0.22, startFreq: 440, endFreq: 620, gain: 0.24, wobble: 4 },
  "tickle-hmph-1.wav": { duration: 0.2, startFreq: 360, endFreq: 310, gain: 0.22, wobble: 3, noise: 0.02 },
  "tickle-purr-1.wav": { duration: 0.3, startFreq: 150, endFreq: 190, gain: 0.18, wobble: 8, noise: 0.03, chirps: 2 },
  "drag-meow-1.wav": { duration: 0.35, startFreq: 620, endFreq: 430, gain: 0.28, wobble: 6 },
  "drag-question-1.wav": { duration: 0.26, startFreq: 470, endFreq: 720, gain: 0.25, wobble: 5 },
  "drag-protest-1.wav": { duration: 0.3, startFreq: 680, endFreq: 500, gain: 0.27, wobble: 7, noise: 0.01 },
  "drag-end-hmph-1.wav": { duration: 0.2, startFreq: 330, endFreq: 280, gain: 0.19, wobble: 3, noise: 0.02 },
  "drag-end-soft-drop-1.wav": { duration: 0.18, startFreq: 210, endFreq: 130, gain: 0.18, wobble: 2, noise: 0.06 },
  "fish-chase-mrrp-1.wav": { duration: 0.24, startFreq: 500, endFreq: 760, gain: 0.24, wobble: 8 },
  "fish-chase-steps-1.wav": { duration: 0.3, startFreq: 230, endFreq: 260, gain: 0.16, wobble: 16, noise: 0.09, chirps: 3 },
  "fish-chase-flutter-1.wav": { duration: 0.28, startFreq: 700, endFreq: 900, gain: 0.18, wobble: 18, noise: 0.05, chirps: 3 },
  "fish-eat-nom-1.wav": { duration: 0.24, startFreq: 260, endFreq: 210, gain: 0.18, wobble: 9, noise: 0.06, chirps: 2 },
  "fish-eat-lick-1.wav": { duration: 0.22, startFreq: 390, endFreq: 300, gain: 0.16, wobble: 5, noise: 0.08 },
  "fish-eat-purr-1.wav": { duration: 0.36, startFreq: 140, endFreq: 180, gain: 0.17, wobble: 8, noise: 0.03, chirps: 2 },
  "crouch-alert-eh-1.wav": { duration: 0.18, startFreq: 540, endFreq: 700, gain: 0.2, wobble: 5 },
  "crouch-alert-mrrp-1.wav": { duration: 0.24, startFreq: 430, endFreq: 640, gain: 0.22, wobble: 7 },
  "crouch-alert-bell-1.wav": { duration: 0.32, startFreq: 900, endFreq: 760, gain: 0.12, wobble: 2 },
  "hug-fish-purr-1.wav": { duration: 0.42, startFreq: 145, endFreq: 170, gain: 0.16, wobble: 8, noise: 0.03, chirps: 2 },
  "hug-fish-meow-1.wav": { duration: 0.3, startFreq: 520, endFreq: 450, gain: 0.2, wobble: 5 },
  "hug-fish-hum-1.wav": { duration: 0.32, startFreq: 260, endFreq: 240, gain: 0.15, wobble: 4 },
  "gnaw-fish-nibble-1.wav": { duration: 0.28, startFreq: 250, endFreq: 220, gain: 0.15, wobble: 12, noise: 0.08, chirps: 3 },
  "gnaw-fish-smack-1.wav": { duration: 0.2, startFreq: 300, endFreq: 250, gain: 0.15, wobble: 8, noise: 0.1, chirps: 2 },
  "gnaw-fish-hum-1.wav": { duration: 0.3, startFreq: 240, endFreq: 270, gain: 0.14, wobble: 4 },
  "icon-hug-poof-1.wav": { duration: 0.2, startFreq: 190, endFreq: 120, gain: 0.18, wobble: 2, noise: 0.08 },
  "icon-hug-purr-1.wav": { duration: 0.38, startFreq: 135, endFreq: 165, gain: 0.15, wobble: 7, noise: 0.03, chirps: 2 },
  "icon-hug-meow-1.wav": { duration: 0.26, startFreq: 510, endFreq: 450, gain: 0.18, wobble: 4 },
  "care-reminder-meow-1.wav": { duration: 0.28, startFreq: 560, endFreq: 470, gain: 0.2, wobble: 4 },
  "care-reminder-bell-1.wav": { duration: 0.32, startFreq: 880, endFreq: 720, gain: 0.12, wobble: 2 },
};

for (const [fileName, cue] of Object.entries(cues)) {
  fs.writeFileSync(path.join(outDir, fileName), toWav(renderCue(cue)));
}

console.log(`created ${Object.keys(cues).length} xiaoju sound files`);
'@ | node -
```

Expected: prints `created 31 xiaoju sound files`.

- [ ] **Step 2: Update `pet.json` with sound cue manifest**

Replace `public/pets/xiaoju-cat/pet.json` with:

```json
{
  "id": "xiaoju-cat",
  "displayName": "小橘",
  "description": "一只橘黄色毛绒小猫咪，会睡觉、抓鱼、吃鱼、跳来跳去，也会陪你等结果。",
  "spritesheetPath": "spritesheet-scruff.webp",
  "sounds": {
    "idle": [
      { "path": "sounds/idle-purr-1.wav", "volume": 0.28 },
      { "path": "sounds/idle-breath-1.wav", "volume": 0.22 },
      { "path": "sounds/idle-meow-soft-1.wav", "volume": 0.26 }
    ],
    "tickle": [
      { "path": "sounds/tickle-hm-1.wav", "volume": 0.38 },
      { "path": "sounds/tickle-hmph-1.wav", "volume": 0.34 },
      { "path": "sounds/tickle-purr-1.wav", "volume": 0.32 }
    ],
    "drag": [
      { "path": "sounds/drag-meow-1.wav", "volume": 0.42 },
      { "path": "sounds/drag-question-1.wav", "volume": 0.38 },
      { "path": "sounds/drag-protest-1.wav", "volume": 0.4 }
    ],
    "drag_end": [
      { "path": "sounds/drag-end-hmph-1.wav", "volume": 0.3 },
      { "path": "sounds/drag-end-soft-drop-1.wav", "volume": 0.28 }
    ],
    "fishChase": [
      { "path": "sounds/fish-chase-mrrp-1.wav", "volume": 0.36 },
      { "path": "sounds/fish-chase-steps-1.wav", "volume": 0.26 },
      { "path": "sounds/fish-chase-flutter-1.wav", "volume": 0.28 }
    ],
    "fishEat": [
      { "path": "sounds/fish-eat-nom-1.wav", "volume": 0.3 },
      { "path": "sounds/fish-eat-lick-1.wav", "volume": 0.28 },
      { "path": "sounds/fish-eat-purr-1.wav", "volume": 0.3 }
    ],
    "crouchAlert": [
      { "path": "sounds/crouch-alert-eh-1.wav", "volume": 0.3 },
      { "path": "sounds/crouch-alert-mrrp-1.wav", "volume": 0.32 },
      { "path": "sounds/crouch-alert-bell-1.wav", "volume": 0.22 }
    ],
    "hugFish": [
      { "path": "sounds/hug-fish-purr-1.wav", "volume": 0.28 },
      { "path": "sounds/hug-fish-meow-1.wav", "volume": 0.3 },
      { "path": "sounds/hug-fish-hum-1.wav", "volume": 0.24 }
    ],
    "gnawFish": [
      { "path": "sounds/gnaw-fish-nibble-1.wav", "volume": 0.24 },
      { "path": "sounds/gnaw-fish-smack-1.wav", "volume": 0.22 },
      { "path": "sounds/gnaw-fish-hum-1.wav", "volume": 0.24 }
    ],
    "iconHug": [
      { "path": "sounds/icon-hug-poof-1.wav", "volume": 0.26 },
      { "path": "sounds/icon-hug-purr-1.wav", "volume": 0.24 },
      { "path": "sounds/icon-hug-meow-1.wav", "volume": 0.24 }
    ],
    "care_reminder": [
      { "path": "sounds/care-reminder-meow-1.wav", "volume": 0.28 },
      { "path": "sounds/care-reminder-bell-1.wav", "volume": 0.2 }
    ]
  }
}
```

- [ ] **Step 3: Add a manifest test that verifies built-in cues are package-relative**

In `src/pet-core/petAssets.test.ts`, add this test inside the existing describe block.

```ts
  test("declares built-in xiaoju sound files with relative package paths", () => {
    const sounds = builtInPetManifest.sounds ?? {};

    expect(Object.keys(sounds).sort()).toEqual([
      "care_reminder",
      "crouchAlert",
      "drag",
      "drag_end",
      "fishChase",
      "fishEat",
      "gnawFish",
      "hugFish",
      "iconHug",
      "idle",
      "tickle",
    ]);

    for (const cues of Object.values(sounds)) {
      expect(cues.length).toBeGreaterThanOrEqual(2);
      for (const cue of cues) {
        expect(cue.path.startsWith("sounds/")).toBe(true);
        expect(cue.path.includes("\\")).toBe(false);
        expect(cue.path.includes(":")).toBe(false);
      }
    }
  });
```

- [ ] **Step 4: Run manifest tests**

Run:

```powershell
npm test -- src/pet-core/petAssets.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

Run:

```powershell
git add -- public/pets/xiaoju-cat/pet.json public/pets/xiaoju-cat/sounds src/pet-core/petAssets.test.ts
git commit -m "feat: add xiaoju sound cues"
```

---

### Task 5: Verify Build And Runtime Audio Behavior

**Files:**
- No planned source edits.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
npm test -- src/pet-core/petAssets.test.ts src/pet-core/sound.test.ts
```

Expected: PASS.

- [ ] **Step 2: Run the full test suite**

Run:

```powershell
npm test
```

Expected: PASS.

- [ ] **Step 3: Run production build**

Run:

```powershell
npm run build
```

Expected: PASS.

- [ ] **Step 4: Start the local Vite app for a browser smoke test**

Run:

```powershell
npm run dev
```

Expected: Vite starts on `http://localhost:1420` because `vite.config.ts` uses port `1420` with `strictPort: true`.

- [ ] **Step 5: Browser smoke test**

Open `http://localhost:1420`.

Verify:

- The app loads without a console error from `sound.ts`.
- `fetch("/pets/xiaoju-cat/sounds/tickle-hm-1.wav")` returns HTTP 200 in the browser console.
- Single click on the pet triggers the tickle animation and does not produce repeated overlapping sound when clicked rapidly.
- Double click triggers the fish chase/eat sequence.
- Opening the platform panel or checking updates does not trigger a sound.

- [ ] **Step 6: Stop the dev server**

Stop the `npm run dev` process with `Ctrl+C`.

- [ ] **Step 7: Commit verification-only follow-up only if a fix was needed**

If Task 5 required source changes, commit those changes with:

```powershell
git add -- src/App.tsx src/pet-core/sound.ts src/pet-core/sound.test.ts src/pet-core/petAssets.ts src/pet-core/petAssets.test.ts public/pets/xiaoju-cat/pet.json public/pets/xiaoju-cat/sounds
git commit -m "fix: stabilize xiaoju sound playback"
```

If no source changes were needed, do not create an empty commit.

---

## Self-Review Checklist

- Spec coverage:
  - Pet-owned assets: Task 4.
  - Manifest `sounds` field: Tasks 1 and 4.
  - Relative path resolution: Tasks 1 and 2.
  - Random variants: Task 2.
  - Cooldowns and no dense overlaps: Task 2.
  - App action triggers: Task 3.
  - System events remain silent: Task 3 and Task 5.
  - Missing/rejected audio does not break animation: Task 2.
  - Tests and build: Task 5.
- Placeholder scan:
  - No unresolved placeholder markers or unspecified test tasks.
- Type consistency:
  - `PetManifest.sounds` uses `PetManifestSounds`.
  - App trigger names match `PetSoundEvent`.
  - Manifest keys match the sound event strings used by `App.tsx`.
