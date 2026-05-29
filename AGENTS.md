# Project Rules

## Desktop Pet Packages

This app is a desktop-pet platform, not a one-off pet app. Keep each pet as an isolated package.

- Put every pet package under `public/pets/<pet-id>/`.
- Do not put pet assets in the project root, `src/`, `src-tauri/`, `dist/`, `output/`, `prd_render/`, or `releases/`.
- Use lowercase stable ids with hyphens, for example `xiaoju-cat`, `black-cat`, or `sleepy-bunny`.
- The folder name and `pet.json` `id` must match.
- File paths inside `pet.json` must be relative to that pet package folder. Never use absolute Windows paths.

Minimum package shape:

```text
public/pets/index.json
public/pets/<pet-id>/
  pet.json
  spritesheet.webp
  preview.png          # optional, for future platform picker UI
  README.md            # optional notes for this pet
```

Minimum `pet.json` fields:

```json
{
  "id": "xiaoju-cat",
  "displayName": "小橘",
  "description": "一只橘黄色毛绒小猫咪。",
  "spritesheetPath": "spritesheet.webp"
}
```

## Asset Loading

- `public/pets/index.json` is the platform registry. Add every built-in pet id to its `pets` array.
- The built-in default pet id lives in `src/pet-core/petAssets.ts` as `DEFAULT_PET_ID`.
- Do not hardcode `/pets/<pet-id>` in components. Use `getPetManifestUrl()` and `resolvePetAssetUrl()`.
- When changing the default pet or adding pet asset path behavior, update `src/pet-core/petAssets.test.ts`.

## Adding A New Pet

When the user asks to create another desktop pet:

1. Create `public/pets/<pet-id>/`.
2. Add a `pet.json` whose `id` matches `<pet-id>`.
3. Add `<pet-id>` to `public/pets/index.json`.
4. Put all sprite, preview, prompt, and pet-specific files inside that folder.
5. Leave existing pet packages in place unless the user explicitly asks to remove one.
6. Run `npm test -- src/pet-core/petAssets.test.ts` and `npm run build` after path or manifest changes.

## Collaboration Notes

- Keep platform code separate from pet-specific content.
- Pet-specific naming, copy, sprites, and prompts belong in the pet package.
- Shared renderer, interaction, and loading logic belongs in `src/`.
- Antigravity project rules are mirrored in `.agents/rules/desktop-pet-pack.md`; keep that file aligned with these rules when changing package conventions.
