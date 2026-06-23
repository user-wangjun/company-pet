# Suan Bird Smooth Landing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the abrupt static landing swap with a short current-flight to approach-flight to landing transition, followed by a 350ms landing hold.

**Architecture:** Extend the suan-bird drag frame plan with the approach frame and transition speed. Build the release texture sequence through a tested pure helper, then let Pixi play the three-frame non-looping transition before starting the landing hold timer.

**Tech Stack:** React, TypeScript, PixiJS, Vitest, Playwright CLI

---

### Task 1: Lock The Landing Sequence

**Files:**
- Modify: `src/pet-core/animationRows.test.ts`
- Modify: `src/pet-core/interaction.test.ts`

- [x] **Step 1: Expect the approach frame and transition speed**

Update the suan-bird drag frame plan assertion with:

```ts
landingApproachFrame: 6,
landingTransitionSpeed: 0.25,
```

- [x] **Step 2: Expect a three-frame landing sequence**

Add a test that builds:

```ts
["current-flight", "flight-7", "landing"]
```

from a current texture and the configured drag frames.

- [x] **Step 3: Expect a 350ms landing hold**

Change the suan-bird drag-end action assertion from `700` to `350`.

- [x] **Step 4: Run focused tests and verify RED**

Run:

```powershell
npm test -- src/pet-core/animationRows.test.ts src/pet-core/interaction.test.ts
```

Expected: failures for missing plan fields, missing sequence helper, and the old 700ms hold.

### Task 2: Implement The Transition

**Files:**
- Modify: `src/pet-core/animationRows.ts`
- Modify: `src/pet-core/interaction.ts`
- Modify: `src/App.tsx`
- Modify: `public/pets/suan-bird/README.md`

- [x] **Step 1: Extend the drag plan**

Set approach frame `6` and transition speed `0.25`.

- [x] **Step 2: Add the pure landing-sequence helper**

Return current frame, configured approach frame, and configured landing frame; return `null` when configured atlas frames are missing.

- [x] **Step 3: Play the transition before holding**

On release, assign the three textures, use the transition speed, play once, and start the 350ms idle-return timer inside `sprite.onComplete`.

- [x] **Step 4: Document the release behavior**

Describe the short flight-to-landing transition and 350ms landing hold.

- [x] **Step 5: Run focused tests and verify GREEN**

Run:

```powershell
npm test -- src/pet-core/animationRows.test.ts src/pet-core/interaction.test.ts
```

Expected: all focused tests pass.

### Task 3: Verify Runtime And Build

**Files:**
- Verify: `src/App.tsx`
- Verify: `public/pets/suan-bird/spritesheet.webp`

- [x] **Step 1: Browser timeline verification**

Capture release at 0ms, about 100ms, about 220ms, and after the 350ms hold. Verify the first samples change through the transition and idle returns after the hold.

- [x] **Step 2: Run complete verification**

Run:

```powershell
npm test
npm run build
```

Expected: all tests pass and Vite builds successfully.
