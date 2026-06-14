#!/usr/bin/env python3
"""重建 ikun v14 九帧丢球动作的 GIF、过渡图和运动检查数据。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw


PET_DIR = Path(__file__).resolve().parents[2]
ATLAS_PATH = PET_DIR / "spritesheet.webp"
FINISH_FRAME_PATH = PET_DIR / "throw-finish.png"
QA_DIR = PET_DIR / "qa"
OUTPUT_DIR = QA_DIR / "throw-v14"
CELL_WIDTH = 192
CELL_HEIGHT = 208
THROW_ROW = 6
IDLE_ROW = 4


def extract_cell(atlas: Image.Image, row: int, frame: int) -> Image.Image:
    left = frame * CELL_WIDTH
    top = row * CELL_HEIGHT
    return atlas.crop((left, top, left + CELL_WIDTH, top + CELL_HEIGHT)).convert("RGBA")


def save_gif(frames: list[Image.Image], durations: list[int], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
        optimize=False,
    )


def checkerboard(size: tuple[int, int], block: int = 12) -> Image.Image:
    background = Image.new("RGBA", size, (238, 238, 238, 255))
    draw = ImageDraw.Draw(background)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle(
                    (x, y, min(x + block - 1, size[0]), min(y + block - 1, size[1])),
                    fill=(210, 210, 210, 255),
                )
    return background


def frame_metrics(frame: Image.Image, index: int) -> dict[str, object]:
    alpha = frame.getchannel("A")
    bbox = alpha.getbbox()
    used_pixels = sum(1 for value in alpha.getdata() if value > 8)
    if bbox is None:
        bbox = (0, 0, 0, 0)
    touches_edge = (
        bbox[0] <= 0
        or bbox[1] <= 0
        or bbox[2] >= CELL_WIDTH
        or bbox[3] >= CELL_HEIGHT
    )
    return {
        "frame": index,
        "usedPixels": used_pixels,
        "bbox": list(bbox),
        "touchesEdge": touches_edge,
        "padding": False,
    }


def update_motion_review(throw_frames: list[Image.Image]) -> None:
    path = QA_DIR / "motion-review.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["source"] = "route1-v14-throw-finish"
    data["generatedAt"] = datetime.now(timezone.utc).isoformat()

    row = next(item for item in data["rows"] if item.get("row") == THROW_ROW)
    row["frames"] = [
        frame_metrics(frame, index)
        for index, frame in enumerate(throw_frames)
    ]

    reference_updates = [
        item for item in data.get("referenceUpdates", []) if item.get("row") != THROW_ROW
    ]
    reference_updates.append(
        {
            "row": THROW_ROW,
            "action": "throw-basketball",
            "reference": "references/throw-09-16-ref.png",
            "finishReference": "references/throw-finish-ref.png",
            "finishFramePath": "throw-finish.png",
            "basketball": "frames-09-16-ball-frame-17-none",
            "frameOrder": "09-17",
        }
    )
    data["referenceUpdates"] = sorted(reference_updates, key=lambda item: item["row"])
    data["notes"] = [
        note
        for note in data.get("notes", [])
        if "Row 6" not in note and "row 6" not in note
        and "第 6 行" not in note
    ]
    data["notes"].append(
        "第 6 行 09-16 帧已清理白色背景，运行时追加独立无球第 17 帧。"
    )
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    with Image.open(ATLAS_PATH) as source:
        atlas = source.convert("RGBA")

    throw_frames = [extract_cell(atlas, THROW_ROW, index) for index in range(8)]
    with Image.open(FINISH_FRAME_PATH) as source:
        finish_frame = source.convert("RGBA")
    runtime_throw_frames = [*throw_frames, finish_frame]
    idle_last = extract_cell(atlas, IDLE_ROW, 7)

    save_gif(
        runtime_throw_frames,
        [150, 150, 150, 180, 180, 150, 150, 220, 420],
        QA_DIR / "previews" / "row-6.gif",
    )
    save_gif(
        [idle_last, *runtime_throw_frames],
        [420, 150, 150, 150, 180, 180, 150, 150, 220, 520],
        OUTPUT_DIR / "transition-08-09.gif",
    )

    comparison = checkerboard((CELL_WIDTH * 3, CELL_HEIGHT + 24))
    comparison.alpha_composite(idle_last, (0, 24))
    comparison.alpha_composite(throw_frames[0], (CELL_WIDTH, 24))
    comparison.alpha_composite(finish_frame, (CELL_WIDTH * 2, 24))
    draw = ImageDraw.Draw(comparison)
    draw.rectangle((0, 0, comparison.width, 23), fill=(25, 25, 25, 255))
    draw.text((54, 5), "IDLE 08", fill=(255, 255, 255, 255))
    draw.text((CELL_WIDTH + 50, 5), "THROW 09", fill=(255, 255, 255, 255))
    draw.text((CELL_WIDTH * 2 + 48, 5), "FINISH 17", fill=(255, 255, 255, 255))
    comparison.save(OUTPUT_DIR / "transition-08-09.png")

    update_motion_review(runtime_throw_frames)
    print("ikun v14 九帧丢球动作 QA 产物已重建")


if __name__ == "__main__":
    main()
