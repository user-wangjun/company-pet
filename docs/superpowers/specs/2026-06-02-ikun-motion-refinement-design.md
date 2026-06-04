# ikun Motion Refinement Design

## Goal

Refine the existing `ikun` desktop-pet package using the approved route 1: match the character's three-view references to a simple joint rig, treat the basketball as a separate equipment layer, then redraw selected multi-frame actions from the rig and integrate the resulting pet back into the Yuxin desktop-pet platform.

This pass focuses on the user's newly confirmed action references:

- `D:/Users/Desktop/9997f7334b7e9e4acf436a73e3a84149.jpg` -> row 3 `bie-ganmao`.
- `D:/Users/Desktop/5a424dcef6de752289def3554032d2e7.jpg` -> row 1 `tieshankao`.
- `D:/Users/Desktop/13307dea98bb06e28b95f690ee47327e.jpg` -> row 7 `step-back`.

Additional user update on 2026-06-03:

- `public/pets/ikun/references/character-views-ref.png` -> primary character-view sheet for Route 1 v11 identity and front/side/back view locking, copied from the user-provided 2026-06-03 view reference.

## Current State

The package already exists at `public/pets/ikun/` and is registered in `public/pets/index.json`. Its `pet.json` points to `spritesheet.webp`, `preview.png`, `actions.json`, `rig.json`, and `action-board.json`, all relative to the pet package folder. The platform can load the package without a shared renderer change.

Current action metadata uses a 192 x 208 cell, 8 columns, and 9 rows. The key rows for this refinement are:

- Row 1 `tieshankao`: currently a first-pass no-ball shoulder/body hit.
- Row 3 `bie-ganmao`: currently a first-pass red-scarf hand-to-mouth reminder action.
- Row 7 `step-back`: currently a first-pass front step-back with basketball present in all frames.

## Scope

Change only pet-package content unless verification proves a platform bug:

- `public/pets/ikun/spritesheet.webp`
- `public/pets/ikun/preview.png`, if the preview needs to reflect the refined identity
- `public/pets/ikun/rig.json`
- `public/pets/ikun/actions.json`
- `public/pets/ikun/action-board.json`
- `public/pets/ikun/pose-map.json`
- `public/pets/ikun/README.md`
- `public/pets/ikun/SOURCES.md`
- `public/pets/ikun/qa/*`

Do not change `DEFAULT_PET_ID`, shared renderer behavior, platform routing, or global asset helpers for this refinement. Do not place pet-specific assets outside `public/pets/ikun/`.

## Rig And Equipment Model

Upgrade `rig.json` from a descriptive redraw note into the source of truth for motion retargeting:

- Keep front, back, left, and right view rules. Back-view actions must use back hair, crossed back straps, and back-body layers rather than a mirrored front face.
- Use the package-local `references/character-views-ref.png` as the primary identity/view lock for rows 1, 3, and 7 after copying the 2026-06-03 user-provided view sheet into the pet package.
- Keep simple joints for root, spine, neck, shoulders, elbows, wrists, hips, knees, and ankles.
- Add action-specific pose tracks for rows 1, 3, and 7. Each track records frame-level intent for root offset, spine lean, head angle, arm contact, leg stance, and prop visibility.
- Keep the basketball as one whole prop layer. The ball may move, rotate, scale slightly, attach to a hand, pass under a leg, leave the visible frame, or hide. It must never fragment or leave orange residue in no-ball rows.

## Action Designs

### Row 1: `tieshankao`

Reference image: `D:/Users/Desktop/5a424dcef6de752289def3554032d2e7.jpg`.

Use the second reference's back and side body language for the shoulder-hit loop. The row remains no-ball. The motion should read as squat, load, side turn, shoulder/upper-back drive, impact hold, and recoil. The frame sequence should use a three-quarter/back-lean silhouette where useful, but must preserve the pet's recognizable yellow face, gray hair, black shirt, and gray overalls when the face is visible.

Acceptance details:

- No basketball in any frame.
- No detached shoulder blob or separate impact effect.
- Body mass drives the action; the shoulder hit should not look like a plain static lean.
- Hair and straps follow the torso turn and remain attached.

### Row 3: `bie-ganmao`

Reference image: `D:/Users/Desktop/9997f7334b7e9e4acf436a73e3a84149.jpg`.

Use the first reference's front-facing red-scarf sequence. The row remains no-ball. The action should read as cold-weather reminder: front idle, hand lifts toward scarf/mouth, hand-to-mouth hold, small cough/reminder beat, recover.

Acceptance details:

- Red scarf is visible and consistent across the row.
- The raised arm replaces the down-arm layer in lift/hold frames.
- No basketball in any frame.

### Row 7: `step-back`

Reference image: `D:/Users/Desktop/13307dea98bb06e28b95f690ee47327e.jpg`.

Use the third reference's step-back and dance-footwork poses. This row keeps basketball present in all frames as a separate equipment layer. The action should read as gather, lean back, one-foot lift or slide, side/back weight shift, ball control, recover to ready.

Acceptance details:

- Exactly one complete basketball is visible in each frame.
- Ball follows the controlling hand and rotates as one whole prop.
- Footwork is visible without cropping feet or moving outside the frame.
- The character identity stays front/three-quarter rather than becoming an unrelated side-view figure.
- No leftover ball fragments, duplicate balls, or orange smears.

## Secondary Basketball QA

Rows 4 `under-leg-dribble` and 6 `throw-basketball` are not the main redraw targets for this user update, but route 1 requires checking them against the equipment-layer rules:

- Row 4: ball remains whole while passing under the leg.
- Row 6: ball is visible only in the planned release frames and hidden after release.
- No no-ball row shows basketball residue.

Only repair rows 4 or 6 if QA reveals a visible equipment-layer problem.

## Output Artifacts

The implementation should return multi-frame action images through the pet package and QA folder:

- Updated `spritesheet.webp`.
- Updated metadata files: `rig.json`, `actions.json`, `action-board.json`, and `pose-map.json`.
- Updated documentation: `README.md` and `SOURCES.md`.
- QA contact sheet showing all rows.
- Motion previews for the refined rows, especially rows 1, 3, and 7.

The final installed platform should be able to show `ikun` as a selectable pet package in the Yuxin desktop-pet executable.

## Verification

Run package and platform checks after implementation:

- Visual QA: inspect the final contact sheet and the row motion previews.
- Asset-path QA: confirm all `pet.json` paths are relative to `public/pets/ikun/`.
- `npm test -- src/pet-core/petAssets.test.ts`
- `npm run build`
- `npm run tauri build`
- Copy the rebuilt executable to the tested release/install path only after the build succeeds.
- Use Windows app automation to verify the Yuxin desktop-pet executable can see the `ikun` package.

## Non-Goals

- Do not replace the whole platform or build a one-off `ikun` app.
- Do not remove existing pet packages.
- Do not hardcode `/pets/ikun` inside shared components.
- Do not add platform-side action runtime branching unless the current package cannot be loaded or previewed without it.
- Do not use absolute Windows paths inside `pet.json` or runtime metadata consumed by the platform.
