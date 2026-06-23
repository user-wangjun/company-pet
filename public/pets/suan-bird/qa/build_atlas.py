from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PET_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = PET_DIR / "action-sources"
QA_DIR = PET_DIR / "qa"
PREVIEW_DIR = QA_DIR / "previews"

CELL_WIDTH = 192
CELL_HEIGHT = 208
COLUMNS = 8
ROWS = 9

ROW_NAMES = [
    "idle",
    "drag",
    "reserved-running-left",
    "tickle",
    "crouchAlert",
    "hugFish",
    "gnawFish",
    "fishChase",
    "fishEat",
]
USED_FRAMES = [6, 8, 8, 8, 8, 8, 8, 8, 6]

SOURCE_ROWS = {
    0: "generated-row-00-idle-alpha.png",
    1: "generated-row-01-drag-alpha.png",
    3: "generated-row-03-tickle-alpha.png",
    4: "generated-row-04-crouchAlert-alpha.png",
    5: "generated-row-05-hugFish-alpha.png",
    6: "generated-row-06-gnawFish-alpha.png",
    7: "generated-row-07-fishChase-alpha.png",
    8: "generated-row-08-fishEat-alpha.png",
}

FRAME_BOTTOMS = {
    0: [202, 202, 200, 198, 200, 202],
    1: [202, 184, 170, 168, 174, 170, 188, 202],
    3: [202, 202, 202, 182, 176, 186, 196, 202],
}


def alpha_components(image: Image.Image) -> list[dict[str, object]]:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    width, height = rgba.size
    data = alpha.tobytes()
    visited = bytearray(width * height)
    components: list[dict[str, object]] = []

    for start, alpha_value in enumerate(data):
        if alpha_value <= 12 or visited[start]:
            continue

        queue = deque([start])
        visited[start] = 1
        pixels: list[int] = []
        min_x = width
        min_y = height
        max_x = 0
        max_y = 0

        while queue:
            current = queue.popleft()
            pixels.append(current)
            x = current % width
            y = current // width
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

            for neighbor in (
                current - 1 if x > 0 else -1,
                current + 1 if x + 1 < width else -1,
                current - width if y > 0 else -1,
                current + width if y + 1 < height else -1,
            ):
                if neighbor >= 0 and data[neighbor] > 12 and not visited[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)

        components.append(
            {
                "area": len(pixels),
                "bbox": (min_x, min_y, max_x + 1, max_y + 1),
                "pixels": pixels,
            }
        )

    return sorted(components, key=lambda component: int(component["area"]), reverse=True)


def split_source_row(path: Path, frame_count: int) -> list[Image.Image]:
    with Image.open(path) as opened:
        strip = opened.convert("RGBA")

    components = alpha_components(strip)
    if len(components) < frame_count:
        raise RuntimeError(
            f"{path.name} has {len(components)} components; "
            f"expected at least {frame_count}"
        )

    seeds = sorted(
        components[:frame_count],
        key=lambda component: (
            component["bbox"][0] + component["bbox"][2]
        )
        / 2,
    )
    seed_ids = {id(seed) for seed in seeds}
    groups: list[list[dict[str, object]]] = [[seed] for seed in seeds]

    for component in components:
        if id(component) in seed_ids:
            continue
        area = int(component["area"])
        if area < 80:
            continue
        center_x = (component["bbox"][0] + component["bbox"][2]) / 2
        nearest_index = min(
            range(len(seeds)),
            key=lambda index: abs(
                (
                    seeds[index]["bbox"][0]
                    + seeds[index]["bbox"][2]
                )
                / 2
                - center_x
            ),
        )
        seed = seeds[nearest_index]
        if area < max(100, int(seed["area"]) * 0.015):
            continue
        groups[nearest_index].append(component)

    source_pixels = strip.load()
    frames: list[Image.Image] = []
    for group in groups:
        min_x = max(0, min(component["bbox"][0] for component in group) - 2)
        min_y = max(0, min(component["bbox"][1] for component in group) - 2)
        max_x = min(strip.width, max(component["bbox"][2] for component in group) + 2)
        max_y = min(strip.height, max(component["bbox"][3] for component in group) + 2)
        frame = Image.new("RGBA", (max_x - min_x, max_y - min_y), (0, 0, 0, 0))
        frame_pixels = frame.load()

        for component in group:
            for pixel_index in component["pixels"]:
                x = pixel_index % strip.width
                y = pixel_index // strip.width
                frame_pixels[x - min_x, y - min_y] = source_pixels[x, y]
        frames.append(frame)

    return frames


def fit_row(row: int, frames: list[Image.Image]) -> list[Image.Image]:
    max_source_width = max(frame.width for frame in frames)
    max_source_height = max(frame.height for frame in frames)
    scale = min(182 / max_source_width, 198 / max_source_height)
    bottoms = FRAME_BOTTOMS.get(row, [202] * len(frames))
    fitted: list[Image.Image] = []

    for index, frame in enumerate(frames):
        width = max(1, round(frame.width * scale))
        height = max(1, round(frame.height * scale))
        resized = frame.resize((width, height), Image.Resampling.LANCZOS)
        cell = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
        x = (CELL_WIDTH - width) // 2
        y = bottoms[index] - height
        cell.alpha_composite(resized, (x, y))
        fitted.append(cell)

    return fitted


def clear_transparent_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    data = bytearray(rgba.tobytes())
    for index in range(0, len(data), 4):
        if data[index + 3] == 0:
            data[index] = 0
            data[index + 1] = 0
            data[index + 2] = 0
    return Image.frombytes("RGBA", rgba.size, bytes(data))


def compose_rows() -> tuple[Image.Image, dict[int, list[Image.Image]], dict[str, object]]:
    fitted_rows: dict[int, list[Image.Image]] = {}
    source_quality: dict[str, object] = {}

    for row, source_name in SOURCE_ROWS.items():
        source_path = SOURCE_DIR / source_name
        with Image.open(source_path) as source:
            source_quality[source_name] = {
                "width": source.width,
                "height": source.height,
                "frameCount": USED_FRAMES[row],
                "minimumSlotWidth": source.width // USED_FRAMES[row],
            }
        fitted_rows[row] = fit_row(
            row, split_source_row(source_path, USED_FRAMES[row])
        )

    fitted_rows[2] = [
        frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        for frame in fitted_rows[1]
    ]

    atlas = Image.new(
        "RGBA",
        (CELL_WIDTH * COLUMNS, CELL_HEIGHT * ROWS),
        (0, 0, 0, 0),
    )
    for row in range(ROWS):
        strip = Image.new(
            "RGBA", (CELL_WIDTH * COLUMNS, CELL_HEIGHT), (0, 0, 0, 0)
        )
        for column, frame in enumerate(fitted_rows[row]):
            strip.alpha_composite(frame, (column * CELL_WIDTH, 0))
            atlas.alpha_composite(
                frame, (column * CELL_WIDTH, row * CELL_HEIGHT)
            )
        strip = clear_transparent_rgb(strip)
        strip.save(SOURCE_DIR / f"row-{row:02d}-{ROW_NAMES[row]}.png")

    return clear_transparent_rgb(atlas), fitted_rows, source_quality


def write_contact_sheet(atlas: Image.Image) -> None:
    label_width = 160
    contact = Image.new(
        "RGBA", (label_width + atlas.width, atlas.height), (248, 250, 245, 255)
    )
    draw = ImageDraw.Draw(contact)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
        small = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
        small = ImageFont.load_default()

    for row, name in enumerate(ROW_NAMES):
        y = row * CELL_HEIGHT
        draw.text((12, y + 16), f"{row}: {name}", fill=(50, 115, 38), font=font)
        draw.text(
            (12, y + 44),
            f"{USED_FRAMES[row]} frames",
            fill=(80, 110, 76),
            font=small,
        )
        for column in range(COLUMNS):
            x = label_width + column * CELL_WIDTH
            fill = (
                (255, 255, 255, 255)
                if (row + column) % 2 == 0
                else (239, 244, 234, 255)
            )
            draw.rectangle(
                (x, y, x + CELL_WIDTH - 1, y + CELL_HEIGHT - 1),
                fill=fill,
                outline=(202, 220, 190, 255),
            )

    contact.alpha_composite(atlas, (label_width, 0))
    contact.convert("RGB").save(QA_DIR / "contact-sheet.png")


def write_previews(fitted_rows: dict[int, list[Image.Image]]) -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    for old in PREVIEW_DIR.glob("*.gif"):
        old.unlink()

    for row, name in enumerate(ROW_NAMES):
        frames: list[Image.Image] = []
        for cell in fitted_rows[row]:
            background = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (250, 252, 247, 255))
            background.alpha_composite(cell)
            frames.append(background.convert("P", palette=Image.Palette.ADAPTIVE))

        duration = 90 if row in {1, 2} else 300 if row == 8 else 140
        frames[0].save(
            PREVIEW_DIR / f"row-{row:02d}-{name}.gif",
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=0,
            optimize=False,
            disposal=2,
        )


def write_validation(atlas: Image.Image, source_quality: dict[str, object]) -> None:
    pixels = atlas.load()
    transparent_rgb_ok = True
    for y in range(atlas.height):
        for x in range(atlas.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0 and (red or green or blue):
                transparent_rgb_ok = False
                break
        if not transparent_rgb_ok:
            break

    rows: list[dict[str, object]] = []
    for row, name in enumerate(ROW_NAMES):
        cells: list[dict[str, object]] = []
        for column in range(COLUMNS):
            cell = atlas.crop(
                (
                    column * CELL_WIDTH,
                    row * CELL_HEIGHT,
                    (column + 1) * CELL_WIDTH,
                    (row + 1) * CELL_HEIGHT,
                )
            )
            non_transparent = sum(
                1 for alpha in cell.getchannel("A").getdata() if alpha > 0
            )
            expected_used = column < USED_FRAMES[row]
            cells.append(
                {
                    "col": column,
                    "expectedUsed": expected_used,
                    "nonTransparentPixels": non_transparent,
                    "ok": (
                        non_transparent > 1200
                        if expected_used
                        else non_transparent == 0
                    ),
                }
            )
        rows.append(
            {
                "row": row,
                "name": name,
                "usedFrames": USED_FRAMES[row],
                "cells": cells,
            }
        )

    validation = {
        "ok": (
            atlas.size == (1536, 1872)
            and transparent_rgb_ok
            and all(cell["ok"] for row in rows for cell in row["cells"])
        ),
        "atlas": {
            "width": atlas.width,
            "height": atlas.height,
            "cellWidth": CELL_WIDTH,
            "cellHeight": CELL_HEIGHT,
            "columns": COLUMNS,
            "rows": ROWS,
        },
        "transparentRgbOk": transparent_rgb_ok,
        "source": "generated high-resolution row strips grounded in reference.png",
        "sourceQuality": source_quality,
        "rows": rows,
    }
    (QA_DIR / "validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    summary = {
        "ok": validation["ok"],
        "spritesheet": str(PET_DIR / "spritesheet.webp"),
        "contactSheet": str(QA_DIR / "contact-sheet.png"),
        "generatedRows": sorted(SOURCE_ROWS.values()),
        "mirroredRows": ["row-02-reserved-running-left"],
        "dragFramePlan": {
            "takeoffFrame": 0,
            "loopStartFrame": 1,
            "loopFrameCount": 6,
            "landingApproachFrame": 6,
            "landingFrame": 7,
            "landingTransitionSpeed": 0.25,
            "landingHoldMs": 350,
        },
        "previews": [
            str(path) for path in sorted(PREVIEW_DIR.glob("*.gif"))
        ],
    }
    (QA_DIR / "sprite-build-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    atlas, fitted_rows, source_quality = compose_rows()
    atlas.save(QA_DIR / "spritesheet.png")
    atlas.save(
        PET_DIR / "spritesheet.webp",
        format="WEBP",
        lossless=True,
        quality=100,
        method=6,
        exact=True,
    )
    fitted_rows[0][0].save(PET_DIR / "preview.png")
    write_contact_sheet(atlas)
    write_previews(fitted_rows)
    write_validation(atlas, source_quality)
    print(f"wrote {PET_DIR / 'spritesheet.webp'}")


if __name__ == "__main__":
    main()
