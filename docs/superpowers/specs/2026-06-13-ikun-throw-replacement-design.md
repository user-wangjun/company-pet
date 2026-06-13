# Ikun Throw Animation Replacement Design

## Goal

Replace every existing frame of the `ikun` single-click throw animation with
the eight poses numbered 09-16 in the user-provided reference image:

`D:\Users\Downloads\ChatGPT Image 2026年6月13日 16_07_11.png`

The new throw must begin smoothly after the current eight-frame under-leg
dribble idle animation and must ship in a rebuilt Windows executable.

## Scope

- Copy the new reference into `public/pets/ikun/references/`.
- Replace atlas row 6, which is exposed at runtime as `gnawFish`.
- Remove all old row-6 sprite pixels instead of mixing old and new frames.
- Keep the current row-4 idle changes and every other atlas row unchanged.
- Update `actions.json`, `action-board.json`, `pose-map.json`, package notes,
  QA images, and the row-6 animation preview.
- Rebuild the Tauri executable and NSIS installer.

## Frame Extraction

The reference is a two-by-four contact sheet containing the continuation
poses 09-16. Each source panel will be isolated in reading order. The gray
background, frame number, floor shadow, and detached white motion marks will
be removed. The pet and complete basketball remain opaque.

The extracted sprites will be normalized into eight transparent 192x208 cells.
Normalization uses the current idle frame 08 as the transition anchor:

- match the apparent character height,
- keep the foot baseline stable,
- keep the torso center close to the idle torso center,
- preserve safe padding without clipping the raised or thrown basketball.

The basketball is present in frames 09-14. Frames 15-16 show the released ball
moving away from the hand, including the complete ball while it remains inside
the cell. No pixels from the old throw row are retained.

## Runtime Mapping

The interaction mapping remains unchanged:

- one click on `ikun` plays runtime animation `gnawFish`,
- `gnawFish` reads atlas row 6,
- row 6 uses all eight frames for the complete 09-16 sequence.

Only pet-specific package assets and metadata change. Shared renderer and
interaction code are out of scope unless verification exposes a loader defect.

## Verification

- Compare idle frame 08 and throw frame 09 side by side and in animation.
- Confirm all eight row-6 cells are populated, transparent, and unclipped.
- Confirm row 6 contains no frame numbers, gray background, floor shadows,
  detached white motion lines, or pixels from the previous throw sequence.
- Confirm other atlas rows are byte-equivalent to the pre-edit atlas.
- Run the focused pet asset tests and the full frontend build.
- Build the Tauri Windows executable and NSIS installer.
- Copy the finished artifacts into `releases/` without deleting unrelated
  release files.

## Error Handling

If deterministic extraction cannot cleanly separate a panel from its
background, stop before replacing the atlas and repair that panel locally.
Do not substitute generated artwork or reuse an old throw frame.
