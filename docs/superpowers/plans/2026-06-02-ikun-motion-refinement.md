# Ikun Motion Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the existing `ikun` pet package so rows 1, 3, and 7 match the approved reference images, keep basketball as a whole equipment layer, rebuild QA media, and verify the Yuxin desktop-pet executable can see `ikun`.

**Architecture:** Keep all pet-specific art, references, metadata, and QA files inside `public/pets/ikun/`. Generate only the three target action rows, replace those rows in the existing 9-row atlas, then run package, build, and Windows executable verification. Platform code changes are out of scope unless the package cannot load.

**Tech Stack:** Vite/React, Tauri, `public/pets` package manifests, Python/Pillow image processing, hatch-pet QA scripts, imagegen, PowerShell, npm, Cargo, Windows Computer Use.

---

## File Map

- Read: `docs/superpowers/specs/2026-06-02-ikun-motion-refinement-design.md` for the approved design.
- Create: `public/pets/ikun/references/bie-ganmao-ref.jpg` from `D:/Users/Desktop/9997f7334b7e9e4acf436a73e3a84149.jpg`.
- Create: `public/pets/ikun/references/tieshankao-ref.jpg` from `D:/Users/Desktop/5a424dcef6de752289def3554032d2e7.jpg`.
- Create: `public/pets/ikun/references/step-back-ref.jpg` from `D:/Users/Desktop/13307dea98bb06e28b95f690ee47327e.jpg`.
- Create: `public/pets/ikun/references/character-views-ref.png` from the user-provided 2026-06-03 view reference; use it as the primary identity/view lock for rows 1, 3, and 7.
- Modify: `public/pets/ikun/rig.json` to add route-one row pose tracks.
- Modify: `public/pets/ikun/actions.json` to move to revision 11 and bind the new references.
- Modify: `public/pets/ikun/action-board.json` to describe the refined row plan.
- Modify: `public/pets/ikun/pose-map.json` to record per-frame row phases for rows 1, 3, and 7.
- Modify: `public/pets/ikun/spritesheet.webp` to replace rows 1, 3, and 7.
- Modify: `public/pets/ikun/preview.png` only if the generated atlas changes the visible identity.
- Modify: `public/pets/ikun/README.md` and `public/pets/ikun/SOURCES.md` to document the no-bubble refinement and copied local references.
- Create/modify: `public/pets/ikun/qa/route1-v11/*`, `public/pets/ikun/qa/contact-sheet-v11.png`, and `public/pets/ikun/qa/previews/row-1.gif`, `row-3.gif`, `row-7.gif`.
- Modify: `public/pets/index.json` only if `ikun` is missing from the registry.
- Modify after successful build: `releases/愈心桌宠.exe` and `releases/愈心桌宠_0.1.0_x64-setup.exe`.

## Task 1: Copy References Into The Pet Package

**Files:**
- Create: `public/pets/ikun/references/bie-ganmao-ref.jpg`
- Create: `public/pets/ikun/references/tieshankao-ref.jpg`
- Create: `public/pets/ikun/references/step-back-ref.jpg`
- Modify: `public/pets/ikun/SOURCES.md`

- [ ] **Step 1: Confirm the three desktop reference files exist**

Run:

```powershell
@(
  'D:\Users\Desktop\9997f7334b7e9e4acf436a73e3a84149.jpg',
  'D:\Users\Desktop\5a424dcef6de752289def3554032d2e7.jpg',
  'D:\Users\Desktop\13307dea98bb06e28b95f690ee47327e.jpg'
) | ForEach-Object {
  if (-not (Test-Path -LiteralPath $_)) { throw "Missing reference: $_" }
  Get-Item -LiteralPath $_ | Select-Object FullName,Length,LastWriteTime
}
```

Expected: all three files are listed with non-zero `Length`.

- [ ] **Step 2: Copy references into `public/pets/ikun/references/`**

Run:

```powershell
New-Item -ItemType Directory -Force -LiteralPath 'public\pets\ikun\references' | Out-Null
Copy-Item -LiteralPath 'D:\Users\Desktop\9997f7334b7e9e4acf436a73e3a84149.jpg' -Destination 'public\pets\ikun\references\bie-ganmao-ref.jpg' -Force
Copy-Item -LiteralPath 'D:\Users\Desktop\5a424dcef6de752289def3554032d2e7.jpg' -Destination 'public\pets\ikun\references\tieshankao-ref.jpg' -Force
Copy-Item -LiteralPath 'D:\Users\Desktop\13307dea98bb06e28b95f690ee47327e.jpg' -Destination 'public\pets\ikun\references\step-back-ref.jpg' -Force
Get-ChildItem -LiteralPath 'public\pets\ikun\references' | Select-Object Name,Length
```

Expected: the three copied reference files are present under the pet package.

- [ ] **Step 3: Document the local references in `SOURCES.md`**

Append this section to `public/pets/ikun/SOURCES.md` using `apply_patch`:

```markdown
## Route 1 action references, 2026-06-02

These user-provided local references were copied into this pet package so the action redraw is reproducible without reading files from the desktop at runtime.

- `references/bie-ganmao-ref.jpg`: row 3 `bie-ganmao`, red-scarf hand-to-mouth cold reminder, no bubble in this pass.
- `references/tieshankao-ref.jpg`: row 1 `tieshankao`, squat/load/side-body shoulder hit, no basketball.
- `references/step-back-ref.jpg`: row 7 `step-back`, dance-footwork step-back with one whole basketball prop.
```

Expected: `SOURCES.md` records references relative to `public/pets/ikun/`, not absolute Windows paths.

## Task 2: Update Rig And Action Metadata

**Files:**
- Modify: `public/pets/ikun/rig.json`
- Modify: `public/pets/ikun/actions.json`
- Modify: `public/pets/ikun/action-board.json`
- Modify: `public/pets/ikun/pose-map.json`
- Modify: `public/pets/ikun/README.md`

- [ ] **Step 1: Update `rig.json` route-one source metadata**

Use `apply_patch` to set these values in `public/pets/ikun/rig.json`:

```json
{
  "version": 2,
  "status": "route1-v11-no-bubble",
  "route1References": {
    "tieshankao": "references/tieshankao-ref.jpg",
    "bieGanmao": "references/bie-ganmao-ref.jpg",
    "stepBack": "references/step-back-ref.jpg"
  }
}
```

Also add this top-level `actionPoseTracks` object:

```json
{
  "tieshankao": [
    {"frame": 0, "view": "front-three-quarter", "root": {"x": 0, "y": 0, "r": 0}, "spine": {"r": 0}, "phase": "neutral", "basketball": "none"},
    {"frame": 1, "view": "front-three-quarter", "root": {"x": -2, "y": 8, "r": -4}, "spine": {"r": -6}, "phase": "crouch", "basketball": "none"},
    {"frame": 2, "view": "front-three-quarter", "root": {"x": -5, "y": 10, "r": -10}, "spine": {"r": -12}, "phase": "load-left", "basketball": "none"},
    {"frame": 3, "view": "back-three-quarter", "root": {"x": 6, "y": 9, "r": 13}, "spine": {"r": 16}, "phase": "shoulder-drive", "basketball": "none"},
    {"frame": 4, "view": "back-three-quarter", "root": {"x": 12, "y": 8, "r": 18}, "spine": {"r": 20}, "phase": "impact-hold", "basketball": "none"},
    {"frame": 5, "view": "front-three-quarter", "root": {"x": 6, "y": 7, "r": 8}, "spine": {"r": 10}, "phase": "recoil", "basketball": "none"},
    {"frame": 6, "view": "front-three-quarter", "root": {"x": 2, "y": 3, "r": 3}, "spine": {"r": 4}, "phase": "recover", "basketball": "none"},
    {"frame": 7, "view": "front-three-quarter", "root": {"x": 0, "y": 0, "r": 0}, "spine": {"r": 0}, "phase": "neutral", "basketball": "none"}
  ],
  "bieGanmao": [
    {"frame": 0, "view": "front", "root": {"x": 0, "y": 0, "r": 0}, "rightArm": "down", "phase": "front-idle", "basketball": "none"},
    {"frame": 1, "view": "front", "root": {"x": 0, "y": 2, "r": -1}, "rightArm": "lift-to-scarf", "phase": "raise-hand", "basketball": "none"},
    {"frame": 2, "view": "front", "root": {"x": 0, "y": 4, "r": -2}, "rightArm": "hand-near-mouth", "phase": "hand-to-mouth", "basketball": "none"},
    {"frame": 3, "view": "front", "root": {"x": -1, "y": 5, "r": -3}, "rightArm": "hand-near-mouth", "phase": "cough-reminder", "basketball": "none"},
    {"frame": 4, "view": "front", "root": {"x": 1, "y": 4, "r": 2}, "rightArm": "hand-near-mouth", "phase": "hold-reminder", "basketball": "none"},
    {"frame": 5, "view": "front", "root": {"x": 1, "y": 2, "r": 1}, "rightArm": "lower-from-mouth", "phase": "lower-hand", "basketball": "none"},
    {"frame": 6, "view": "front", "root": {"x": 0, "y": 1, "r": 0}, "rightArm": "down", "phase": "recover", "basketball": "none"},
    {"frame": 7, "view": "front", "root": {"x": 0, "y": 0, "r": 0}, "rightArm": "down", "phase": "front-idle", "basketball": "none"}
  ],
  "stepBack": [
    {"frame": 0, "view": "front", "root": {"x": 0, "y": 0, "r": 0}, "rightFoot": "plant", "basketball": {"state": "held-right", "rotationDegrees": 0}},
    {"frame": 1, "view": "front", "root": {"x": -2, "y": 2, "r": -3}, "rightFoot": "gather", "basketball": {"state": "dribble-low", "rotationDegrees": 45}},
    {"frame": 2, "view": "front-three-quarter", "root": {"x": -6, "y": 4, "r": -8}, "rightFoot": "lift", "basketball": {"state": "controlled-high", "rotationDegrees": 90}},
    {"frame": 3, "view": "front-three-quarter", "root": {"x": -12, "y": 5, "r": -12}, "rightFoot": "step-back", "basketball": {"state": "held-right-side", "rotationDegrees": 135}},
    {"frame": 4, "view": "front-three-quarter", "root": {"x": -16, "y": 4, "r": -10}, "rightFoot": "back-plant", "basketball": {"state": "held-right-side", "rotationDegrees": 180}},
    {"frame": 5, "view": "front-three-quarter", "root": {"x": -10, "y": 3, "r": -6}, "rightFoot": "slide-recover", "basketball": {"state": "held-right", "rotationDegrees": 225}},
    {"frame": 6, "view": "front", "root": {"x": -3, "y": 1, "r": -2}, "rightFoot": "recover", "basketball": {"state": "recover", "rotationDegrees": 270}},
    {"frame": 7, "view": "front", "root": {"x": 0, "y": 0, "r": 0}, "rightFoot": "plant", "basketball": {"state": "held-right", "rotationDegrees": 315}}
  ]
}
```

Expected: `rig.json` has no absolute reference paths and still states that basketball fragmentation is forbidden.

- [ ] **Step 2: Update `actions.json`**

Use `apply_patch` to make these exact metadata changes:

```json
{
  "version": 11,
  "revisionNotes": [
    "Route 1 v11: row 1 tieshankao uses references/tieshankao-ref.jpg, row 3 bie-ganmao uses references/bie-ganmao-ref.jpg with no bubble, and row 7 step-back uses references/step-back-ref.jpg.",
    "Basketball remains a whole equipment prop; rows 1 and 3 are no-ball rows, and row 7 contains exactly one complete basketball per frame."
  ]
}
```

For action `tieshankao`, set:

```json
{
  "referenceMatch": "route1-reference-tieshankao-ref",
  "motionStatus": "planned-route1-v11",
  "cue": "参考 references/tieshankao-ref.jpg：下沉、侧身蓄力、肩背顶出、停顿、回弹；全程无篮球。"
}
```

For action `bie-ganmao`, set:

```json
{
  "referenceMatch": "route1-reference-bie-ganmao-ref-no-bubble",
  "motionStatus": "planned-route1-v11",
  "cue": "参考 references/bie-ganmao-ref.jpg：红围巾、抬手到嘴边、轻咳/提醒、放下恢复；本轮不加气泡。"
}
```

For action `step-back`, set:

```json
{
  "referenceMatch": "route1-reference-step-back-ref",
  "motionStatus": "planned-route1-v11",
  "cue": "参考 references/step-back-ref.jpg：后撤步脚步和身体后仰，篮球作为一个完整道具跟手旋转。"
}
```

Expected: row 1 and row 3 `basketball.mode` remain `none`; row 7 `basketball.mode` remains `all`.

- [ ] **Step 3: Update `action-board.json` and `pose-map.json`**

Use `apply_patch` to set the revision string in both files to:

```json
"route1-v11-no-bubble"
```

In `pose-map.json`, set row 1, row 3, and row 7 phases to the phase names from `rig.json`:

```json
{
  "row1Phases": ["neutral", "crouch", "load-left", "shoulder-drive", "impact-hold", "recoil", "recover", "neutral"],
  "row3Phases": ["front-idle", "raise-hand", "hand-to-mouth", "cough-reminder", "hold-reminder", "lower-hand", "recover", "front-idle"],
  "row7Phases": ["held-right", "dribble-low", "controlled-high", "held-right-side", "held-right-side", "held-right", "recover", "held-right"]
}
```

Expected: the action board and pose map describe no bubble for row 3 and whole-ball behavior for row 7.

- [ ] **Step 4: Update `README.md`**

Add this row summary to `public/pets/ikun/README.md`:

```markdown
### Route 1 v11 refinement

- Row 1 `tieshankao`: uses `references/tieshankao-ref.jpg`; no basketball; shoulder/back body hit with squat, load, impact, and recoil.
- Row 3 `bie-ganmao`: uses `references/bie-ganmao-ref.jpg`; no basketball; red-scarf hand-to-mouth cold reminder; no bubble in this pass.
- Row 7 `step-back`: uses `references/step-back-ref.jpg`; one complete basketball prop in every frame.
```

Expected: README documents the user-facing result without absolute desktop paths.

## Task 3: Generate The Three Refined Row Strips

**Files:**
- Create: `public/pets/ikun/qa/route1-v11/decoded/row-1.png`
- Create: `public/pets/ikun/qa/route1-v11/decoded/row-3.png`
- Create: `public/pets/ikun/qa/route1-v11/decoded/row-7.png`

- [ ] **Step 1: Load the image generation workflow**

Before using the image generation tool, read and follow:

```powershell
Get-Content -LiteralPath 'C:\Users\13640\.codex\skills\.system\imagegen\SKILL.md' -Raw
```

Expected: the worker follows the installed imagegen path and does not call another image-generation mechanism.

- [ ] **Step 2: Generate row 1 `tieshankao`**

Inputs:

```text
public/pets/ikun/reference.png
public/pets/ikun/static-frame.png
public/pets/ikun/references/tieshankao-ref.jpg
public/pets/ikun/references/character-views-ref.png
```

Prompt:

```text
Create one horizontal 8-frame sprite strip for the existing ikun desktop pet, 1536x208 total, eight 192x208 cells, clean #00FF00 chroma-key background. Preserve the same compact 3D toy/plush look, yellow face, gray bowl hair, black shirt, gray overalls, red cheek circles, small orange beak mouth, and readable whole-body silhouette from the supplied ikun reference. Action row: tieshankao shoulder/body hit based on tieshankao-ref.jpg. Frames: neutral, squat, side load, shoulder/back drive, impact hold, recoil, recover, neutral. No basketball, no bubble, no text, no motion lines, no detached effects, no shadows, no cropped feet. Keep all pixels for each frame inside its cell.
```

Save the selected generated strip to:

```text
public/pets/ikun/qa/route1-v11/decoded/row-1.png
```

Expected: row 1 strip shows eight readable no-ball frames on green background.

- [ ] **Step 3: Generate row 3 `bie-ganmao`**

Inputs:

```text
public/pets/ikun/reference.png
public/pets/ikun/static-frame.png
public/pets/ikun/references/bie-ganmao-ref.jpg
public/pets/ikun/references/character-views-ref.png
```

Prompt:

```text
Create one horizontal 8-frame sprite strip for the existing ikun desktop pet, 1536x208 total, eight 192x208 cells, clean #00FF00 chroma-key background. Preserve the same compact 3D toy/plush look, yellow face, gray bowl hair, black shirt, gray overalls, red cheek circles, small orange beak mouth, and readable whole-body silhouette from the supplied ikun reference. Action row: bie-ganmao cold reminder based on bie-ganmao-ref.jpg. Add a red scarf consistent across the row. Frames: front idle, hand starts lifting toward scarf, hand near mouth, small cough/reminder beat, hand-to-mouth hold, hand lowers, recover, front idle. No basketball, no bubble, no text, no punctuation, no floating icons, no shadows, no cropped feet. Replace the down-arm pose with a connected raised sleeve and visible yellow hand in the lift and hold frames.
```

Save the selected generated strip to:

```text
public/pets/ikun/qa/route1-v11/decoded/row-3.png
```

Expected: row 3 strip shows red scarf and hand-to-mouth gesture with no bubble.

- [ ] **Step 4: Generate row 7 `step-back`**

Inputs:

```text
public/pets/ikun/reference.png
public/pets/ikun/static-frame.png
public/pets/ikun/references/step-back-ref.jpg
public/pets/ikun/references/character-views-ref.png
```

Prompt:

```text
Create one horizontal 8-frame sprite strip for the existing ikun desktop pet, 1536x208 total, eight 192x208 cells, clean #00FF00 chroma-key background. Preserve the same compact 3D toy/plush look, yellow face, gray bowl hair, black shirt, gray overalls, red cheek circles, small orange beak mouth, and readable whole-body silhouette from the supplied ikun reference. Action row: step-back dance-footwork with basketball based on step-back-ref.jpg. Frames: ready with ball, gather dribble, lean back with foot lift, step back, back-foot plant with side lean, slide recover, recover dribble, ready. Exactly one complete orange basketball in every frame, attached to or clearly controlled by the hand, rotating as one whole prop. No duplicate balls, no ball fragments, no text, no bubble, no motion lines, no detached effects, no shadows, no cropped feet.
```

Save the selected generated strip to:

```text
public/pets/ikun/qa/route1-v11/decoded/row-7.png
```

Expected: row 7 strip shows eight frames with exactly one whole basketball in each frame.

## Task 4: Replace Rows In The Existing Atlas And Render QA

**Files:**
- Modify: `public/pets/ikun/spritesheet.webp`
- Create: `public/pets/ikun/qa/route1-v11/spritesheet-v11.png`
- Create: `public/pets/ikun/qa/contact-sheet-v11.png`
- Modify: `public/pets/ikun/qa/previews/row-1.gif`
- Modify: `public/pets/ikun/qa/previews/row-3.gif`
- Modify: `public/pets/ikun/qa/previews/row-7.gif`
- Modify: `public/pets/ikun/qa/motion-review.json`

- [ ] **Step 1: Run the row replacement script**

Run this exact script from the repo root:

```powershell
@'
from pathlib import Path
import json
import math
from PIL import Image

ROOT = Path(r"D:\CodeWorkspace\电脑桌宠")
PET = ROOT / "public" / "pets" / "ikun"
CELL_W = 192
CELL_H = 208
COLUMNS = 8
ROWS = 9
CHROMA = (0, 255, 0)
THRESHOLD = 96.0

source_atlas = PET / "spritesheet.webp"
qa_dir = PET / "qa" / "route1-v11"
decoded = qa_dir / "decoded"
png_out = qa_dir / "spritesheet-v11.png"
webp_out = PET / "spritesheet.webp"
row_sources = {
    1: decoded / "row-1.png",
    3: decoded / "row-3.png",
    7: decoded / "row-7.png",
}

def color_distance(pixel):
    r, g, b, _a = pixel
    return math.sqrt((r - CHROMA[0]) ** 2 + (g - CHROMA[1]) ** 2 + (b - CHROMA[2]) ** 2)

def normalize_transparency(image):
    image = image.convert("RGBA")
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                pixels[x, y] = (0, 0, 0, 0)
            elif color_distance((r, g, b, a)) <= THRESHOLD:
                pixels[x, y] = (0, 0, 0, 0)
    return image

def load_strip(path):
    if not path.is_file():
        raise SystemExit(f"missing row strip: {path}")
    with Image.open(path) as opened:
        strip = opened.convert("RGBA")
    target_size = (CELL_W * COLUMNS, CELL_H)
    if strip.size != target_size:
        strip = strip.resize(target_size, Image.Resampling.LANCZOS)
    return normalize_transparency(strip)

with Image.open(source_atlas) as opened:
    atlas = opened.convert("RGBA")

expected_size = (CELL_W * COLUMNS, CELL_H * ROWS)
if atlas.size != expected_size:
    raise SystemExit(f"unexpected atlas size {atlas.size}, expected {expected_size}")

for row, strip_path in row_sources.items():
    strip = load_strip(strip_path)
    for frame in range(COLUMNS):
        cell = strip.crop((frame * CELL_W, 0, (frame + 1) * CELL_W, CELL_H))
        atlas.paste(Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0)), (frame * CELL_W, row * CELL_H))
        atlas.alpha_composite(cell, (frame * CELL_W, row * CELL_H))

for y in range(atlas.height):
    for x in range(atlas.width):
        r, g, b, a = atlas.getpixel((x, y))
        if a == 0:
            atlas.putpixel((x, y), (0, 0, 0, 0))

qa_dir.mkdir(parents=True, exist_ok=True)
atlas.save(png_out)
atlas.save(webp_out, "WEBP", lossless=False, quality=95, method=6)

result = {
    "ok": True,
    "sourceAtlas": str(source_atlas),
    "pngOut": str(png_out),
    "webpOut": str(webp_out),
    "replacedRows": sorted(row_sources),
}
print(json.dumps(result, ensure_ascii=False, indent=2))
'@ | python -
```

Expected: script prints `"ok": true` and `replacedRows` `[1, 3, 7]`.

- [ ] **Step 2: Render contact sheet**

Run:

```powershell
python 'C:\Users\13640\.codex\skills\hatch-pet\scripts\make_contact_sheet.py' 'public\pets\ikun\spritesheet.webp' --output 'public\pets\ikun\qa\contact-sheet-v11.png' --scale 2
```

Expected: `public/pets/ikun/qa/contact-sheet-v11.png` exists and shows all 9 rows.

- [ ] **Step 3: Render row GIF previews**

Run:

```powershell
@'
from pathlib import Path
from PIL import Image

ROOT = Path(r"D:\CodeWorkspace\电脑桌宠")
PET = ROOT / "public" / "pets" / "ikun"
ATLAS = PET / "spritesheet.webp"
OUT = PET / "qa" / "previews"
CELL_W = 192
CELL_H = 208
COLUMNS = 8
DURATIONS = [120, 120, 120, 120, 160, 120, 120, 220]

OUT.mkdir(parents=True, exist_ok=True)
with Image.open(ATLAS) as opened:
    atlas = opened.convert("RGBA")

for row in (1, 3, 7):
    frames = [
        atlas.crop((frame * CELL_W, row * CELL_H, (frame + 1) * CELL_W, (row + 1) * CELL_H))
        for frame in range(COLUMNS)
    ]
    frames[0].save(
        OUT / f"row-{row}.gif",
        save_all=True,
        append_images=frames[1:],
        duration=DURATIONS,
        loop=0,
        disposal=2,
        optimize=False,
    )
print("rendered row-1.gif row-3.gif row-7.gif")
'@ | python -
```

Expected: the three GIF files are updated.

- [ ] **Step 4: Update `motion-review.json`**

Use `apply_patch` to set:

```json
{
  "source": "route1-v11-no-bubble",
  "referenceUpdates": [
    {
      "row": 1,
      "actionId": "tieshankao",
      "source": "references/tieshankao-ref.jpg",
      "notes": "No-ball body-led shoulder hit: squat, side load, shoulder/back drive, impact hold, recoil."
    },
    {
      "row": 3,
      "actionId": "bie-ganmao",
      "source": "references/bie-ganmao-ref.jpg",
      "notes": "No-ball red-scarf hand-to-mouth cold reminder. No bubble in this pass."
    },
    {
      "row": 7,
      "actionId": "step-back",
      "source": "references/step-back-ref.jpg",
      "notes": "Step-back footwork with exactly one whole basketball prop in each frame."
    }
  ]
}
```

Expected: QA JSON records the same no-bubble decision as the spec.

## Task 5: Package QA And Frontend Build Verification

**Files:**
- Read: `public/pets/ikun/pet.json`
- Read: `public/pets/index.json`
- Read: `public/pets/ikun/qa/contact-sheet-v11.png`
- Read: `public/pets/ikun/qa/previews/row-1.gif`
- Read: `public/pets/ikun/qa/previews/row-3.gif`
- Read: `public/pets/ikun/qa/previews/row-7.gif`

- [ ] **Step 1: Validate atlas geometry**

Run:

```powershell
python 'C:\Users\13640\.codex\skills\hatch-pet\scripts\validate_atlas.py' 'public\pets\ikun\spritesheet.webp' --json-out 'public\pets\ikun\qa\route1-v11\atlas-validation.json' --allow-near-opaque-used-cells
```

Expected: JSON output includes `"ok": true` and no blank used cells.

- [ ] **Step 2: Inspect final contact sheet visually**

Open `D:\CodeWorkspace\电脑桌宠\public\pets\ikun\qa\contact-sheet-v11.png` with the local image viewer.

Expected visual checks:

- Row 1 has no basketball and reads as squat/load/shoulder hit/recoil.
- Row 3 has no basketball, no bubble, visible red scarf, and connected raised hand-to-mouth frames.
- Row 7 has one complete basketball in every frame.
- No frame is blank, cropped, or visually outside its 192 x 208 cell.

- [ ] **Step 3: Inspect the three GIF previews**

Open:

```text
D:\CodeWorkspace\电脑桌宠\public\pets\ikun\qa\previews\row-1.gif
D:\CodeWorkspace\电脑桌宠\public\pets\ikun\qa\previews\row-3.gif
D:\CodeWorkspace\电脑桌宠\public\pets\ikun\qa\previews\row-7.gif
```

Expected: each GIF loops smoothly and row 3 has no bubble.

- [ ] **Step 4: Confirm manifest paths**

Run:

```powershell
node -e "const fs=require('fs'); const pet=JSON.parse(fs.readFileSync('public/pets/ikun/pet.json','utf8')); for (const [k,v] of Object.entries(pet)) if (k.endsWith('Path') && /^[A-Za-z]:/.test(v)) throw new Error(k+' is absolute'); const idx=JSON.parse(fs.readFileSync('public/pets/index.json','utf8')); if (!idx.pets.includes('ikun')) throw new Error('ikun missing from registry'); console.log('manifest paths ok')"
```

Expected: prints `manifest paths ok`.

- [ ] **Step 5: Run pet asset tests**

Run:

```powershell
npm test -- src/pet-core/petAssets.test.ts
```

Expected: test command exits 0.

- [ ] **Step 6: Run frontend build**

Run:

```powershell
npm run build
```

Expected: build command exits 0 and writes `dist/`.

## Task 6: Tauri Build And Windows Exe Verification

**Files:**
- Modify: `releases/愈心桌宠.exe`
- Modify: `releases/愈心桌宠_0.1.0_x64-setup.exe`
- Modify outside git repo for manual test install: `D:\Users\Desktop\测试用\愈心桌宠\yuxin-desktop-pet.exe`

- [ ] **Step 1: Run Tauri build**

Run:

```powershell
npm run tauri build
```

Expected: command exits 0 and produces:

```text
src-tauri\target\release\yuxin-desktop-pet.exe
src-tauri\target\release\bundle\nsis\愈心桌宠_0.1.0_x64-setup.exe
```

- [ ] **Step 2: Copy release artifacts**

Run:

```powershell
Copy-Item -LiteralPath 'src-tauri\target\release\yuxin-desktop-pet.exe' -Destination 'releases\愈心桌宠.exe' -Force
Copy-Item -LiteralPath 'src-tauri\target\release\bundle\nsis\愈心桌宠_0.1.0_x64-setup.exe' -Destination 'releases\愈心桌宠_0.1.0_x64-setup.exe' -Force
Copy-Item -LiteralPath 'src-tauri\target\release\yuxin-desktop-pet.exe' -Destination 'D:\Users\Desktop\测试用\愈心桌宠\yuxin-desktop-pet.exe' -Force
```

Expected: all three destination files have a current `LastWriteTime`.

- [ ] **Step 3: Verify the executable can see `ikun`**

Use Computer Use to launch:

```text
D:\Users\Desktop\测试用\愈心桌宠\yuxin-desktop-pet.exe
```

Then inspect accessibility text or screenshot for:

```text
2 个桌宠包
ikun
启用
```

Expected: the app lists `ikun` as an available pet package. If direct click activation fails on the transparent window, record that as a Windows automation limitation and keep the accessibility evidence.

## Task 7: Commit Functional Package And Release Artifacts Separately

**Files:**
- Stage functional package: `public/pets/index.json`, `public/pets/ikun/`
- Stage plan/spec docs only if modified during execution: `docs/superpowers/specs/2026-06-02-ikun-motion-refinement-design.md`, `docs/superpowers/plans/2026-06-02-ikun-motion-refinement.md`
- Stage release artifacts separately: `releases/愈心桌宠.exe`, `releases/愈心桌宠_0.1.0_x64-setup.exe`

- [ ] **Step 1: Inspect changed files before staging**

Run:

```powershell
git status --short --branch
git diff --name-status
```

Expected: functional pet-package files and release artifacts can be separated. Do not stage unrelated existing changes in `src/`, marketing files, or `.gitignore` unless they are proven necessary for this task.

- [ ] **Step 2: Stage and commit functional pet package**

Run:

```powershell
git add -- public/pets/index.json public/pets/ikun
git diff --cached --name-status
git commit -m "feat: refine ikun motion package"
```

Expected: commit includes the `ikun` package, registry entry, updated metadata, updated spritesheet, references, and QA media. It does not include `releases/`.

- [ ] **Step 3: Stage and commit release artifacts**

Run:

```powershell
git add -- 'releases/愈心桌宠.exe' 'releases/愈心桌宠_0.1.0_x64-setup.exe'
git diff --cached --name-status
git commit -m "chore: update yuxin release artifact for ikun"
```

Expected: release commit includes only the two files under `releases/`.

- [ ] **Step 4: Final working-tree report**

Run:

```powershell
git status --short --branch
```

Expected: report remaining unrelated local changes separately. Do not claim the tree is clean if unrelated files remain modified.

## Self-Review

- Spec coverage: rows 1, 3, and 7 are mapped to the three user reference images; row 3 explicitly has no bubble; route-one basketball equipment checks are included; platform exe verification is included.
- Scope: implementation stays inside `public/pets/ikun/` plus registry and release artifacts. Shared platform code is excluded unless verification proves a loader bug.
- Git grouping: functional pet package and release binaries are split into separate commits.
- Verification: visual QA, atlas validation, manifest path checks, pet asset tests, frontend build, Tauri build, and Windows executable visibility checks are all included.
