---
description: Keep desktop pet packages isolated under public/pets and avoid hardcoded pet paths.
alwaysApply: true
---

# Desktop Pet Package Rules

This repository is a desktop-pet platform. Keep pet content isolated from platform code.

- Every pet package belongs in `public/pets/<pet-id>/`.
- Every built-in pet id must also be listed in `public/pets/index.json`.
- Do not place pet assets in the project root or in `src/`, `src-tauri/`, `dist/`, `output/`, `prd_render/`, or `releases/`.
- Use lowercase stable ids with hyphens.
- The package folder name and `pet.json` `id` must match.
- `pet.json` asset paths must be relative to the package folder.
- The default built-in pet id is `DEFAULT_PET_ID` in `src/pet-core/petAssets.ts`.
- Do not hardcode `/pets/<pet-id>` in UI code; use `getPetManifestUrl()` and `resolvePetAssetUrl()`.
- When adding a new pet, use the v1 pet creation workflow:
  - Inventory source art first. The user will usually provide character three-view art and multi-frame action art before personality is finalized.
  - Review the visuals and action feel with the user, then define the pet brief: name, personality, companionship style, dialogue voice, sound direction, and explicit no-go items.
  - Map actions to the platform baseline: `idle`, `singleClick`, `doubleClick`, `drag`, `eyeCare`, `water`, `meal`, and `sleep`.
  - Treat action input as 8-frame strips by default, but declare the true runtime frame count in `pet.json`; do not force short actions to 8 frames.
  - Create `public/pets/<pet-id>/`, add `pet.json`, update `public/pets/index.json`, and put all sprite, preview, prompt, reference, generation, QA, and pet-specific files in that folder.
  - Run `npm test -- src/pet-core/petAssets.test.ts` and `npm run build` after path or manifest changes.
- Use a shippable baseline checklist for new pets:
  - Stable lowercase package id and matching `pet.json` `id`.
  - Package-local identity references when available.
  - Runtime spritesheet with declared `idle`, `singleClick`, `doubleClick`, and `drag` animations.
  - Four care reminder mappings: `eyeCare`, `water`, `meal`, and `sleep`.
  - Package-local `pet.json` paths only.
  - `dialogues.json` when pet-specific reminder or interaction text is needed.
  - `preview.png` or a documented preview asset when the platform picker needs one.
  - Basic package-local QA artifacts such as contact sheets, row previews, validation JSON, or README notes.
- Treat idle quirks, desktop icon interaction, hover behavior, pet-specific sounds, fuller `README.md`/`SOURCES.md`, and deeper visual QA as premium enhancements unless the user explicitly makes them part of the pet's required scope.
- When improving an existing pet, update only that pet package for pet-specific assets, copy, prompts, QA, and notes; update shared `src/` code only for platform behavior that benefits more than one pet.
- Keep this rule file aligned with `AGENTS.md`.
