# Suan Bird Double-Click Hold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Change the suan-bird double-click bubble and hold the wrapped final frame longer before returning to idle.

**Architecture:** Keep the existing non-looping row 7 animation. Extend its interaction timeout to 2000ms so Pixi finishes the eight frames and remains on the final frame, while pet-owned copy stays in `public/pets/suan-bird/dialogues.json`.

**Tech Stack:** React, TypeScript, PixiJS, Vitest, Vite

---

### Task 1: Lock The Approved Double-Click Behavior

**Files:**
- Modify: `src/pet-core/interaction.test.ts`
- Modify: `src/pet-core/dialogue.test.ts`

- [x] **Step 1: Update the failing interaction assertion**

Expect the suan-bird double-click action to use:

```ts
{
  animation: "fishChase",
  sound: "fishChase",
  bubbleText: "蒜鸟蒜鸟，都不yong易；",
  durationMs: 2000,
}
```

- [x] **Step 2: Add a pet-package dialogue assertion**

Import `public/pets/suan-bird/dialogues.json` and assert:

```ts
expect(suanBirdDialogues.doubleClick).toBe("蒜鸟蒜鸟，都不yong易；");
```

- [x] **Step 3: Run focused tests and verify RED**

Run:

```powershell
npm test -- src/pet-core/interaction.test.ts src/pet-core/dialogue.test.ts
```

Expected: failures show the old bubble and `1200` duration.

### Task 2: Implement The Copy And Final-Frame Hold

**Files:**
- Modify: `src/pet-core/interaction.ts`
- Modify: `public/pets/suan-bird/dialogues.json`
- Modify: `public/pets/suan-bird/README.md`

- [x] **Step 1: Update the interaction fallback and timeout**

Set the double-click fallback text to `蒜鸟蒜鸟，都不yong易；` and `durationMs` to `2000`.

- [x] **Step 2: Update pet-owned dialogue**

Set `doubleClick` in `dialogues.json` to the same exact text.

- [x] **Step 3: Document the hold**

State that row 7 plays once and remains on its wrapped final frame until the 2000ms interaction timeout returns it to idle.

- [x] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
npm test -- src/pet-core/interaction.test.ts src/pet-core/dialogue.test.ts
```

Expected: all focused tests pass.

### Task 3: Verify Runtime And Build

**Files:**
- Verify: `src/App.tsx`
- Verify: `public/pets/suan-bird/spritesheet.webp`

- [x] **Step 1: Browser verification**

Double-click suan-bird and verify the exact bubble appears, the animation reaches row 7 frame 8, remains wrapped, and returns to idle at about 2000ms.

- [x] **Step 2: Run complete verification**

Run:

```powershell
npm test
npm run build
```

Expected: all tests pass and Vite builds successfully.
