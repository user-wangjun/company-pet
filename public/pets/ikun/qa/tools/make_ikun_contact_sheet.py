#!/usr/bin/env python3
"""按 ikun actions.json 的真实行映射生成联系表。"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PET_DIR = Path(__file__).resolve().parents[2]
ATLAS_PATH = PET_DIR / "spritesheet.webp"
FINISH_FRAME_PATH = PET_DIR / "throw-finish.png"
OUTPUT_PATH = PET_DIR / "qa" / "contact-sheet-v15.png"
CELL_WIDTH = 192
CELL_HEIGHT = 208
SCALE = 0.5
LABEL_HEIGHT = 22


def checkerboard(width: int, height: int, block: int = 8) -> Image.Image:
    image = Image.new("RGB", (width, height), "#eeeeee")
    draw = ImageDraw.Draw(image)
    for y in range(0, height, block):
        for x in range(0, width, block):
            if (x // block + y // block) % 2:
                draw.rectangle(
                    (x, y, min(x + block - 1, width), min(y + block - 1, height)),
                    fill="#d2d2d2",
                )
    return image


def load_font() -> ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), 12)
    return ImageFont.load_default()


def row_specs() -> dict[int, dict[str, object]]:
    data = json.loads((PET_DIR / "actions.json").read_text(encoding="utf-8"))
    return {
        int(action["row"]): {
            "id": action["id"],
            "displayName": action["displayName"],
            "frames": int(action["frames"]),
            "atlasFrames": int(action.get("atlasFrames", action["frames"])),
        }
        for action in data["actions"]
    }


def display_column_count(spec: dict[str, object]) -> int:
    return max(int(spec["frames"]), int(spec["atlasFrames"]))


def frame_label(column: int, *, independent_finish: bool = False) -> str:
    label = str(column + 1)
    if independent_finish:
        return f"{label} 独立收尾"
    return label


def main() -> None:
    specs = row_specs()
    columns = max(display_column_count(spec) for spec in specs.values())
    scaled_width = round(CELL_WIDTH * SCALE)
    scaled_height = round(CELL_HEIGHT * SCALE)
    sheet = Image.new(
        "RGB",
        (scaled_width * columns, (scaled_height + LABEL_HEIGHT) * 9),
        "#111111",
    )
    draw = ImageDraw.Draw(sheet)
    font = load_font()

    with Image.open(ATLAS_PATH) as source:
        atlas = source.convert("RGBA")
    with Image.open(FINISH_FRAME_PATH) as source:
        finish_frame = source.convert("RGBA")

    for row in range(9):
        spec = specs[row]
        row_top = row * (scaled_height + LABEL_HEIGHT)
        label = f"第 {row} 行  {spec['displayName']} / {spec['id']}"
        draw.text((5, row_top + 3), label, fill="#ffffff", font=font)
        frame_text = f"{spec['frames']} 帧"
        draw.text(
            (sheet.width - 48, row_top + 3),
            frame_text,
            fill="#ffffff",
            font=font,
        )

        for column in range(display_column_count(spec)):
            if row == 6 and column == 8:
                cell = finish_frame.copy()
            else:
                left = column * CELL_WIDTH
                top = row * CELL_HEIGHT
                cell = atlas.crop((left, top, left + CELL_WIDTH, top + CELL_HEIGHT))
            cell = cell.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)
            background = checkerboard(scaled_width, scaled_height).convert("RGBA")
            background.alpha_composite(cell)
            target_y = row_top + LABEL_HEIGHT
            sheet.paste(background.convert("RGB"), (column * scaled_width, target_y))
            outline = "#18a058" if column < spec["frames"] else "#cc3344"
            draw.rectangle(
                (
                    column * scaled_width,
                    target_y,
                    (column + 1) * scaled_width - 1,
                    target_y + scaled_height - 1,
                ),
                outline=outline,
                width=1,
            )
            draw.text(
                (column * scaled_width + 3, target_y + 2),
                frame_label(column, independent_finish=row == 6 and column == 8),
                fill="#111111",
                font=font,
            )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUTPUT_PATH)
    sheet.save(PET_DIR / "qa" / "contact-sheet.png")
    print(f"已生成 {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
