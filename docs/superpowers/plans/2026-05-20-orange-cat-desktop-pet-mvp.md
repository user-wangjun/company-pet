# Orange Cat Desktop Pet MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first visible MVP: a formal Tauri-shaped React/PixiJS desktop pet app that can preview the existing xiaoju pet asset, parse pet manifests, animate state rows, drag the pet, show proud-cat bubbles, and simulate passive anti-mistouch behavior in browser preview.

**Architecture:** Keep core behavior in TypeScript modules (`pet-assets`, `pet-core`) and rendering in `pet-renderer`. Tauri files are scaffolded for the future Windows shell, while the first runnable effect uses Vite because Rust/Cargo is not currently installed on the machine.

**Tech Stack:** React, TypeScript, Vite, Vitest, PixiJS, Tauri v2 config skeleton.

---

### Task 1: Project Foundation

**Files:**
- Create: `package.json`
- Create: `index.html`
- Create: `tsconfig.json`
- Create: `vite.config.ts`
- Create: `.gitignore`
- Create: `src/main.tsx`
- Create: `src/vite-env.d.ts`

- [ ] **Step 1: Create package and Vite configuration**

Add React/Vite/Pixi/Vitest scripts and TypeScript config.

- [ ] **Step 2: Install dependencies**

Run: `npm install`

Expected: dependency install succeeds and creates `package-lock.json`.

### Task 2: Pet Manifest TDD

**Files:**
- Create: `src/pet-assets/types.ts`
- Create: `src/pet-assets/normalizePetManifest.test.ts`
- Create: `src/pet-assets/normalizePetManifest.ts`

- [ ] **Step 1: Write failing manifest normalization tests**

Tests must cover Codex-minimal `spritesheetPath` manifests and extended per-state manifests.

- [ ] **Step 2: Run red test**

Run: `npm test -- src/pet-assets/normalizePetManifest.test.ts --run`

Expected: fails because `normalizePetManifest.ts` does not exist yet.

- [ ] **Step 3: Implement manifest normalization**

Implement per-state `row / frames / fps / loop`, Codex fallback rows, and desktop-state aliases.

- [ ] **Step 4: Run green test**

Run: `npm test -- src/pet-assets/normalizePetManifest.test.ts --run`

Expected: all manifest tests pass.

### Task 3: Presence And Perch TDD

**Files:**
- Create: `src/pet-core/presence.test.ts`
- Create: `src/pet-core/presence.ts`
- Create: `src/pet-core/perchPlanner.test.ts`
- Create: `src/pet-core/perchPlanner.ts`

- [ ] **Step 1: Write failing presence tests**

Tests must prove default `solid`, dense-area `passive`, hover `materializing`, and drag `dragging`.

- [ ] **Step 2: Run red presence test**

Run: `npm test -- src/pet-core/presence.test.ts --run`

Expected: fails because `presence.ts` does not exist yet.

- [ ] **Step 3: Implement presence logic**

Implement pure TypeScript decision logic.

- [ ] **Step 4: Run green presence test**

Run: `npm test -- src/pet-core/presence.test.ts --run`

Expected: all presence tests pass.

- [ ] **Step 5: Write failing perch planner tests**

Tests must prove icon-edge candidates are preferred and taskbar-overlap candidates are rejected.

- [ ] **Step 6: Run red perch test**

Run: `npm test -- src/pet-core/perchPlanner.test.ts --run`

Expected: fails because `perchPlanner.ts` does not exist yet.

- [ ] **Step 7: Implement perch planner**

Implement pure candidate scoring and best-perch selection.

- [ ] **Step 8: Run green perch test**

Run: `npm test -- src/pet-core/perchPlanner.test.ts --run`

Expected: all perch planner tests pass.

### Task 4: PixiJS Preview Experience

**Files:**
- Create: `src/app/App.tsx`
- Create: `src/app/App.css`
- Create: `src/pet-renderer/PixiPetStage.tsx`
- Copy: `public/pets/xiaoju/spritesheet.webp`
- Copy: `public/pets/xiaoju/codex-pet.json`

- [ ] **Step 1: Copy xiaoju assets**

Copy existing Codex pet assets into `public/pets/xiaoju/`.

- [ ] **Step 2: Implement PixiJS pet stage**

Render the active manifest state using row/frame/fps/loop.

- [ ] **Step 3: Implement preview app**

Show a simulated Windows desktop with icon clusters, draggable xiaoju, proud bubbles, hover materialization, and passive anti-mistouch state.

- [ ] **Step 4: Build check**

Run: `npm run build`

Expected: TypeScript and Vite build pass.

### Task 5: Tauri Skeleton

**Files:**
- Create: `src-tauri/tauri.conf.json`
- Create: `src-tauri/Cargo.toml`
- Create: `src-tauri/src/main.rs`

- [ ] **Step 1: Add Tauri config skeleton**

Add transparent, undecorated, always-on-top window config pointing at Vite output.

- [ ] **Step 2: Document Rust blocker in source comments**

Keep comments short and explicit: local machine needs Rust/Cargo before `npm run tauri dev`.

### Task 6: Verification And Preview

**Files:**
- Modify as needed: implementation files from prior tasks.

- [ ] **Step 1: Run full tests**

Run: `npm test -- --run`

Expected: all tests pass.

- [ ] **Step 2: Run production build**

Run: `npm run build`

Expected: build succeeds.

- [ ] **Step 3: Start preview server**

Run: `npm run dev -- --host 127.0.0.1`

Expected: Vite serves the preview URL.

- [ ] **Step 4: Browser verify**

Open the local URL and verify the pet sprite animates, can be dragged, switches states, and shows passive/materializing labels.
