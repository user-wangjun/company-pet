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

Use the v1 pet creation workflow:

1. Inventory the source art first. The user will usually provide character three-view art and multi-frame action art before personality is finalized.
2. Review the visuals and action feel with the user, then define the pet brief: name, personality, companionship style, dialogue voice, sound direction, and explicit no-go items.
3. Map the provided actions to the platform baseline: `idle`, `singleClick`, `doubleClick`, `drag`, `eyeCare`, `water`, `meal`, and `sleep`.
4. Treat action input as 8-frame strips by default, but declare the true runtime frame count in `pet.json`. Do not force idle, finish, or short actions to 8 frames if only 4 or 6 frames are valid.
5. Create `public/pets/<pet-id>/`.
6. Add a `pet.json` whose `id` matches `<pet-id>`.
7. Add `<pet-id>` to `public/pets/index.json`.
8. Put all sprite, preview, prompt, reference, generation, QA, and pet-specific files inside that folder.
9. Leave existing pet packages in place unless the user explicitly asks to remove one.
10. Run `npm test -- src/pet-core/petAssets.test.ts` and `npm run build` after path or manifest changes.

### Pet Creation Standards

Use two checklists so a new pet can ship at a clear baseline and improve later.

Shippable baseline:

- Stable lowercase package id and matching `pet.json` `id`.
- Character three-view or equivalent identity reference kept inside the pet package when available.
- Runtime spritesheet with declared animations for `idle`, `singleClick`, `doubleClick`, and `drag`.
- Four care reminder mappings: `eyeCare`, `water`, `meal`, and `sleep`.
- Package-local `pet.json` paths only; no absolute Windows paths and no hardcoded `/pets/<pet-id>` in platform code.
- `dialogues.json` when pet-specific reminder or interaction text is needed.
- `preview.png` or a documented preview asset when the platform picker needs one.
- Basic QA artifacts, such as a contact sheet, row preview, validation JSON, or README notes, stored inside the pet package.
- Focused pet asset tests plus `npm run build` after manifest or loading changes.

Premium enhancements:

- Idle quirks with 2-3 role-appropriate variants.
- Desktop icon interaction, hover behavior, or other optional interactions when the character has suitable art.
- Pet-specific sounds that match the character and stay interaction-driven rather than noisy or looping.
- More complete `README.md` and `SOURCES.md` covering references, licenses, generation prompts, QA decisions, and known limitations.
- Extra visual QA such as per-row GIF previews, transparent-frame checks, body-scale checks, and motion review notes.

When improving an existing pet, keep the same package boundary: update only that pet package for pet-specific assets, copy, prompts, QA, and notes; update shared `src/` code only for platform behavior that benefits more than one pet.

## Collaboration Notes

- Keep platform code separate from pet-specific content.
- Pet-specific naming, copy, sprites, and prompts belong in the pet package.
- Shared renderer, interaction, and loading logic belongs in `src/`.
- Antigravity project rules are mirrored in `.agents/rules/desktop-pet-pack.md`; keep that file aligned with these rules when changing package conventions.
