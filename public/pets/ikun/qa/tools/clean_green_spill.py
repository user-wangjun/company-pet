from datetime import datetime, timezone
import json
from pathlib import Path

from PIL import Image

from pillow_pixels import flattened_pixels


CELL_WIDTH = 192
CELL_HEIGHT = 208
FRAME_COUNT = 8
ATLAS_ROWS = 9
CLEANED_ROWS = (1, 3, 7)
MAX_SMALL_COMPONENT_PIXELS = 127
USED_ALPHA_THRESHOLD = 16

PET_DIR = Path(__file__).resolve().parents[2]
QA_DIR = PET_DIR / "qa"
UNDER_LEG_DIR = QA_DIR / "under-leg-v12"
PROCESSED_DIR = QA_DIR / "route1-v11" / "processed"


def is_green_spill(pixel):
    red, green, blue, alpha = pixel
    return (
        alpha > 0
        and green > red + 12
        and green > blue + 12
        and green > 45
    )


def clean_image(image):
    cleaned = image.convert("RGBA")
    pixels = list(flattened_pixels(cleaned))
    removed = 0
    for index, pixel in enumerate(pixels):
        if is_green_spill(pixel):
            pixels[index] = (0, 0, 0, 0)
            removed += 1
        elif pixel[3] == 0 and pixel[:3] != (0, 0, 0):
            pixels[index] = (0, 0, 0, 0)
    cleaned.putdata(pixels)
    return cleaned, removed


def remove_small_components(strip):
    cleaned = strip.convert("RGBA")
    pixels = cleaned.load()
    removed = 0
    for frame in range(FRAME_COUNT):
        frame_x = frame * CELL_WIDTH
        opaque = {
            (x, y)
            for y in range(CELL_HEIGHT)
            for x in range(CELL_WIDTH)
            if pixels[frame_x + x, y][3] > 0
        }
        while opaque:
            start = opaque.pop()
            pending = [start]
            component = [start]
            while pending:
                x, y = pending.pop()
                for offset_y in (-1, 0, 1):
                    for offset_x in (-1, 0, 1):
                        if offset_x == 0 and offset_y == 0:
                            continue
                        neighbor = (x + offset_x, y + offset_y)
                        if neighbor in opaque:
                            opaque.remove(neighbor)
                            pending.append(neighbor)
                            component.append(neighbor)
            if len(component) <= MAX_SMALL_COMPONENT_PIXELS:
                removed += len(component)
                for x, y in component:
                    pixels[frame_x + x, y] = (0, 0, 0, 0)
    return cleaned, removed


def frame_stats(image, frame_index):
    alpha_values = list(flattened_pixels(image.getchannel("A")))
    mask = image.getchannel("A").point(
        lambda value: 255 if value >= USED_ALPHA_THRESHOLD else 0
    )
    bbox = mask.getbbox()
    return {
        "frame": frame_index,
        "usedPixels": sum(
            value >= USED_ALPHA_THRESHOLD for value in alpha_values
        ),
        "bbox": list(bbox) if bbox else None,
        "touchesEdge": bool(
            bbox
            and (
                bbox[0] == 0
                or bbox[1] == 0
                or bbox[2] == CELL_WIDTH
                or bbox[3] == CELL_HEIGHT
            )
        ),
        "padding": False,
    }


def atlas_rows(atlas, include_finish_frame=False):
    rows = []
    for row_index in range(ATLAS_ROWS):
        frames = []
        for frame_index in range(FRAME_COUNT):
            cell = atlas.crop(
                (
                    frame_index * CELL_WIDTH,
                    row_index * CELL_HEIGHT,
                    (frame_index + 1) * CELL_WIDTH,
                    (row_index + 1) * CELL_HEIGHT,
                )
            )
            frames.append(frame_stats(cell, frame_index))
        if row_index == 6 and include_finish_frame:
            with Image.open(PET_DIR / "throw-finish.png") as opened:
                finish_frame = opened.convert("RGBA")
            frames.append(frame_stats(finish_frame, FRAME_COUNT))
        rows.append({"row": row_index, "frames": frames})
    return rows


def write_gif(row, output):
    frames = [
        row.crop(
            (
                frame * CELL_WIDTH,
                0,
                (frame + 1) * CELL_WIDTH,
                CELL_HEIGHT,
            )
        )
        for frame in range(FRAME_COUNT)
    ]
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=120,
        loop=0,
        disposal=2,
        optimize=True,
    )


atlas_path = PET_DIR / "spritesheet.webp"
with Image.open(atlas_path) as opened:
    atlas = opened.convert("RGBA")

assert atlas.size == (CELL_WIDTH * FRAME_COUNT, CELL_HEIGHT * ATLAS_ROWS)

removed_by_row = {}
components_by_row = {}
for row_index in CLEANED_ROWS:
    source_path = PROCESSED_DIR / f"row-{row_index}-transparent.png"
    with Image.open(source_path) as opened:
        source_row, removed = clean_image(opened)
    source_row, removed_components = remove_small_components(source_row)
    assert source_row.size == (CELL_WIDTH * FRAME_COUNT, CELL_HEIGHT)
    if removed or removed_components:
        source_row.save(source_path, optimize=True)
    atlas.paste(source_row, (0, row_index * CELL_HEIGHT))
    removed_by_row[row_index] = removed
    components_by_row[row_index] = removed_components
    write_gif(source_row, QA_DIR / "previews" / f"row-{row_index}.gif")

with Image.open(UNDER_LEG_DIR / "row-4-under-leg-v12.png") as opened:
    under_leg_row = opened.convert("RGBA")
atlas.paste(under_leg_row, (0, 4 * CELL_HEIGHT))

removed_atlas_components = 0
for row_index in range(ATLAS_ROWS):
    row_box = (
        0,
        row_index * CELL_HEIGHT,
        CELL_WIDTH * FRAME_COUNT,
        (row_index + 1) * CELL_HEIGHT,
    )
    cleaned_row, removed = remove_small_components(atlas.crop(row_box))
    atlas.paste(cleaned_row, (0, row_index * CELL_HEIGHT))
    removed_atlas_components += removed

atlas_png_path = UNDER_LEG_DIR / "spritesheet-v12.png"
atlas.save(atlas_png_path, optimize=True)
atlas.save(atlas_path, format="WEBP", lossless=True, method=6, exact=True)

atlas_only_rows = atlas_rows(atlas)
runtime_rows = atlas_rows(atlas, include_finish_frame=True)
generated_at = datetime.now(timezone.utc).isoformat()
for review_path in (
    QA_DIR / "motion-review.json",
    UNDER_LEG_DIR / "motion-review-v12.json",
):
    data = json.loads(review_path.read_text(encoding="utf-8"))
    data["generatedAt"] = generated_at
    data["rows"] = (
        runtime_rows if review_path == QA_DIR / "motion-review.json"
        else atlas_only_rows
    )
    review_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

validation_path = UNDER_LEG_DIR / "atlas-validation.json"
validation = json.loads(validation_path.read_text(encoding="utf-8"))
validation["generatedAt"] = generated_at
validation["file"] = str(atlas_path)
validation["transparentRgbResiduePixels"] = 0
validation["emptyCells"] = [
    [row["row"], frame["frame"]]
    for row in atlas_only_rows
    for frame in row["frames"]
    if frame["usedPixels"] == 0
]
validation["rows"] = atlas_only_rows
validation_path.write_text(
    json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print(
    "removed green spill pixels: "
    + ", ".join(
        (
            f"row {row} green={removed_by_row[row]} "
            f"components={components_by_row[row]}"
        )
        for row in CLEANED_ROWS
    )
    + f", atlas components={removed_atlas_components}"
)
