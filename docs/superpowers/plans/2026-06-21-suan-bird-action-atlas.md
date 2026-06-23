# Suan Bird Action Atlas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the provisional Suan Bird atlas with the approved multi-frame actions and connect its four reminder animations without changing other pets.

**Architecture:** Keep the existing 8x9 runtime atlas contract and map the new Suan Bird poses onto existing animation names. Extend the pet-specific interaction mapping with a reminder kind, then add a small pure helper for meal/sleep reminder deduplication so `App.tsx` only schedules and plays returned actions.

**Tech Stack:** React 19, TypeScript, PixiJS, Vitest, Pillow-based deterministic sprite processing, WebP/PNG/GIF QA assets.

---

### Task 1: Lock the reminder behavior with tests

**Files:**
- Modify: `src/pet-core/interaction.test.ts`
- Modify: `src/pet-core/interaction.ts`

- [ ] **Step 1: Write failing tests for Suan Bird reminder mapping**

Add assertions that `water`, `eyeCare`, `meal`, and `sleep` map respectively to `crouchAlert`, `hugFish`, `gnawFish`, and `fishEat`, while existing `ikun` and `ds` reminder mappings remain unchanged.

- [ ] **Step 2: Run the focused test and verify the signature/mapping failure**

Run: `npm test -- src/pet-core/interaction.test.ts`

Expected: FAIL because `getPetCareReminderAction` does not accept or distinguish reminder kinds.

- [ ] **Step 3: Implement the minimal typed reminder mapping**

Add `PetCareReminderKind`, identify `suan-bird`, and return only the requested pet-specific action. Preserve current actions for other pets.

- [ ] **Step 4: Run the focused test**

Run: `npm test -- src/pet-core/interaction.test.ts`

Expected: PASS.

### Task 2: Add meal and sleep reminder deduplication

**Files:**
- Modify: `src/pet-core/interaction.test.ts`
- Modify: `src/pet-core/interaction.ts`
- Modify: `src/App.tsx`

- [ ] **Step 1: Write failing pure-helper tests**

Define test cases for no timed reminder outside configured hours, meal reminders during meal windows, sleep reminders overnight, and suppression when the same date/event key was already played.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `npm test -- src/pet-core/interaction.test.ts`

Expected: FAIL because the timed reminder helper is missing.

- [ ] **Step 3: Implement the pure helper**

Return `{ kind, key }` where `key` combines local date and event window, for example `meal-breakfast` or the overnight sleep window, or `null` when there is no reminder or it has already played.

- [ ] **Step 4: Wire the helper into `probeDesktopIconInteraction`**

Track the last timed reminder key in a ref. Play the pet-specific action and dialogue once per date/event window before idle quirks and icon probing.

- [ ] **Step 5: Run the focused tests**

Run: `npm test -- src/pet-core/interaction.test.ts`

Expected: PASS.

### Task 3: Produce the approved Suan Bird atlas

**Files:**
- Add: `public/pets/suan-bird/action-reference.png`
- Add: `public/pets/suan-bird/action-sources/*.png`
- Replace: `public/pets/suan-bird/spritesheet.webp`
- Replace: `public/pets/suan-bird/preview.png`
- Replace: `public/pets/suan-bird/qa/contact-sheet.png`
- Replace: `public/pets/suan-bird/qa/previews/*.gif`
- Replace: `public/pets/suan-bird/qa/validation.json`

- [ ] **Step 1: Preserve the user reference inside the pet package**

Copy the supplied action board to `action-reference.png`.

- [ ] **Step 2: Generate clean action sources**

Use the three-view reference and action board as identity and pose references. Generate sprite-ready poses on flat `#ff00ff` chroma backgrounds without text, numbers, shadows, or detached effects.

- [ ] **Step 3: Remove chroma and normalize frames**

Convert sources to RGBA, fit each pose within `192x208`, align the foot baseline, and normalize fully transparent RGB values.

- [ ] **Step 4: Compose the 8x9 atlas**

Write rows using the design mapping. Keep row 0 and row 8 at six used frames and all other rows at eight used frames.

- [ ] **Step 5: Generate QA outputs**

Create the contact sheet, per-row GIF previews, build summary, and validation JSON.

- [ ] **Step 6: Inspect the contact sheet and previews**

Reject identity drift, clipping, white backgrounds, detached effects, baseline jumps, or direction errors.

### Task 4: Update package notes and verify

**Files:**
- Modify: `public/pets/suan-bird/README.md`
- Modify: `public/pets/suan-bird/SOURCES.md`
- Verify: `public/pets/suan-bird/pet.json`

- [ ] **Step 1: Document final row semantics and source provenance**

Record the user action board, generated sources, runtime mapping, and QA outputs.

- [ ] **Step 2: Run required package tests**

Run: `npm test -- src/pet-core/petAssets.test.ts`

Expected: PASS.

- [ ] **Step 3: Run focused interaction tests**

Run: `npm test -- src/pet-core/interaction.test.ts`

Expected: PASS.

- [ ] **Step 4: Run the full suite and build**

Run: `npm test`

Expected: PASS.

Run: `npm run build`

Expected: PASS.

- [ ] **Step 5: Review the final diff**

Confirm all pet-specific imagery remains under `public/pets/suan-bird/`, existing pet packages are untouched by this task, and no generated build output is added.
