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
- When adding a new pet, create `public/pets/<pet-id>/`, add `pet.json`, update `public/pets/index.json`, and put all pet-specific assets in that folder.
- Keep this rule file aligned with `AGENTS.md`.
