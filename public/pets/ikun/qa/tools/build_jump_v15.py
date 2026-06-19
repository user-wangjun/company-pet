#!/usr/bin/env python3
"""Build the ikun v15 double-click jump row from the package-local reference."""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image


PET_DIR = Path(__file__).resolve().parents[2]
REFERENCE_PATH = PET_DIR / "references" / "jump-ref.png"
ATLAS_PATH = PET_DIR / "spritesheet.webp"
QA_DIR = PET_DIR / "qa"
OUTPUT_DIR = QA_DIR / "jump-v15"
PREVIEW_DIR = QA_DIR / "previews"
CELL_WIDTH = 192
CELL_HEIGHT = 208
COLUMNS = 8
ROWS = 9
JUMP_ROW = 8
SCALE = 0.53
SOURCE_FRAME_COUNT = 8
SOURCE_MASK_HEIGHT = 610
GROUND_FRAME_INDICES = [0, 1, 6, 7]
DEST_BASELINE_Y = 198


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def largest_component(mask: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    visited = np.zeros((height, width), dtype=bool)
    best_points: list[tuple[int, int]] = []

    for start_y, start_x in np.argwhere(mask):
        if visited[start_y, start_x]:
            continue

        points: list[tuple[int, int]] = []
        queue: deque[tuple[int, int]] = deque([(int(start_y), int(start_x))])
        visited[start_y, start_x] = True

        while queue:
            y, x = queue.popleft()
            points.append((y, x))
            for next_y, next_x in (
                (y - 1, x),
                (y + 1, x),
                (y, x - 1),
                (y, x + 1),
            ):
                if (
                    0 <= next_y < height
                    and 0 <= next_x < width
                    and mask[next_y, next_x]
                    and not visited[next_y, next_x]
                ):
                    visited[next_y, next_x] = True
                    queue.append((next_y, next_x))

        if len(points) > len(best_points):
            best_points = points

    component = np.zeros((height, width), dtype=bool)
    for y, x in best_points:
        component[y, x] = True
    return component


def fill_holes(mask: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    exterior = np.zeros((height, width), dtype=bool)
    queue: deque[tuple[int, int]] = deque()

    for x in range(width):
        for y in (0, height - 1):
            if not mask[y, x] and not exterior[y, x]:
                exterior[y, x] = True
                queue.append((y, x))
    for y in range(height):
        for x in (0, width - 1):
            if not mask[y, x] and not exterior[y, x]:
                exterior[y, x] = True
                queue.append((y, x))

    while queue:
        y, x = queue.popleft()
        for next_y, next_x in (
            (y - 1, x),
            (y + 1, x),
            (y, x - 1),
            (y, x + 1),
        ):
            if (
                0 <= next_y < height
                and 0 <= next_x < width
                and not mask[next_y, next_x]
                and not exterior[next_y, next_x]
            ):
                exterior[next_y, next_x] = True
                queue.append((next_y, next_x))

    return mask | (~mask & ~exterior)


def frame_mask(crop: Image.Image) -> np.ndarray:
    rgb = np.asarray(crop.convert("RGB"))
    non_background = (
        ((255 - rgb).max(axis=2) > 12)
        | ((rgb.max(axis=2) - rgb.min(axis=2)) > 20)
    ) & ~((rgb[:, :, 0] > 238) & (rgb[:, :, 1] > 238) & (rgb[:, :, 2] > 238))
    non_background[SOURCE_MASK_HEIGHT:, :] = False
    return fill_holes(largest_component(non_background))


def bbox_from_mask(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        raise RuntimeError("empty jump frame mask")
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def build_jump_frames() -> list[Image.Image]:
    source = Image.open(REFERENCE_PATH).convert("RGBA")
    slot_width = source.width / SOURCE_FRAME_COUNT
    prepared: list[tuple[Image.Image, np.ndarray, tuple[int, int, int, int]]] = []

    for index in range(SOURCE_FRAME_COUNT):
        left = round(index * slot_width)
        right = round((index + 1) * slot_width)
        crop = source.crop((left, 0, right, source.height))
        mask = frame_mask(crop)
        bbox = bbox_from_mask(mask)
        prepared.append((crop, mask, bbox))

    source_baseline = max(prepared[index][2][3] for index in GROUND_FRAME_INDICES)
    frames: list[Image.Image] = []

    for crop, mask, bbox in prepared:
        rgba = np.asarray(crop.convert("RGBA")).copy()
        rgba[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
        sprite = Image.fromarray(rgba).crop(bbox)
        width = max(1, round(sprite.width * SCALE))
        height = max(1, round(sprite.height * SCALE))
        sprite = sprite.resize((width, height), Image.Resampling.LANCZOS)
        resized = np.asarray(sprite).copy()
        connected_alpha = largest_component(resized[:, :, 3] > 0)
        resized[:, :, 3] = np.where(
            connected_alpha,
            resized[:, :, 3],
            0,
        ).astype(np.uint8)
        sprite = Image.fromarray(resized)

        bottom = DEST_BASELINE_Y - round((source_baseline - bbox[3]) * SCALE)
        x = round((CELL_WIDTH - width) / 2)
        y = bottom - height
        if x < 0 or y < 0 or x + width > CELL_WIDTH or y + height > CELL_HEIGHT:
            raise RuntimeError(
                f"jump frame out of cell bounds: bbox={bbox}, placed={(x, y, width, height)}"
            )

        frame = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
        frame.alpha_composite(sprite, (x, y))
        frames.append(frame)

    return frames


def save_gif(frames: list[Image.Image], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=[130, 120, 120, 140, 130, 130, 120, 160],
        loop=0,
        disposal=2,
        optimize=False,
    )


def frame_metrics(frame: Image.Image, index: int) -> dict[str, object]:
    alpha = frame.getchannel("A")
    bbox = alpha.getbbox() or (0, 0, 0, 0)
    used_pixels = sum(1 for value in alpha.getdata() if value > 8)
    return {
        "frame": index,
        "usedPixels": used_pixels,
        "bbox": list(bbox),
        "touchesEdge": (
            bbox[0] <= 0
            or bbox[1] <= 0
            or bbox[2] >= CELL_WIDTH
            or bbox[3] >= CELL_HEIGHT
        ),
        "padding": False,
    }


def update_actions() -> None:
    path = PET_DIR / "actions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = 15
    data["notes"] = [
        note
        for note in data.get("notes", [])
        if "练习收尾" not in note and "practice-finish" not in note
    ]
    note = "Route 1 v15 replaces row 8 with the user-provided 01-08 jump reference; this row is the ikun double-click action."
    if note not in data["notes"]:
        data["notes"].append(note)

    for series in data["series"]:
        if series["id"] == "gesture-no-ball":
            series["rows"] = [row for row in series["rows"] if row != JUMP_ROW]
            series["notes"] = "无球手势镜头；第 3 行参考 BV1A7rmBrEWX 的红围巾别感冒动作。"
    data["series"] = [series for series in data["series"] if series["id"] != "jump-no-ball"]
    data["series"].append(
        {
            "id": "jump-no-ball",
            "displayName": "跳跃",
            "sourceRange": None,
            "rows": [JUMP_ROW],
            "basketball": "none",
            "notes": "用户提供的 01-08 跳跃参考；下蹲、起跳、空中停顿、落地恢复，全程无篮球。",
            "reference": "references/jump-ref.png",
        }
    )

    for action in data["actions"]:
        if action["row"] == JUMP_ROW:
            action.clear()
            action.update(
                {
                    "id": "jump",
                    "displayName": "跳跃",
                    "seriesId": "jump-no-ball",
                    "sequenceIndex": 0,
                    "sequenceRole": "double-click-jump",
                    "row": JUMP_ROW,
                    "frames": 8,
                    "currentRuntimeAnimation": "fishEat",
                    "view": "front",
                    "basketball": {
                        "mode": "none",
                        "frames": [],
                        "sourceObservation": "用户提供的 01-08 跳跃图全程无篮球。",
                    },
                    "referenceMatch": "user-reference-jump-v15",
                    "motionStatus": "reference-standard-v15",
                    "cue": "按 references/jump-ref.png：站定、下蹲蓄力、双臂张开起跳、空中收手、落地缓冲、恢复站定。",
                    "prototypeFrames": list(range(8)),
                    "sourceImage": "references/jump-ref.png",
                }
            )

    revision = "Route 1 v15: row 8 replaces the old practice-finish double-click action with the user-provided 8-frame jump reference."
    data["revisionNotes"] = [
        note
        for note in data.get("revisionNotes", [])
        if "practice-finish double-click" not in note
    ]
    if revision not in data["revisionNotes"]:
        data["revisionNotes"].append(revision)

    write_json(path, data)


def update_action_board() -> None:
    path = PET_DIR / "action-board.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = 15
    data["status"] = "route1-v15-double-click-jump"
    note = "Route 1 v15 replaces row 8 with the user-provided 8-frame jump reference for ikun double-click."
    data["notes"] = [
        item
        for item in data.get("notes", [])
        if "row 8" not in item.lower() and "第 8 行" not in item
    ]
    data["notes"].append(note)

    for row in data["currentAtlasRows"]:
        if row["row"] == JUMP_ROW:
            row.update(
                {
                    "actionId": "jump",
                    "seriesId": "jump-no-ball",
                    "view": "front",
                    "basketball": "none",
                    "matchStatus": "reference-standard-v15",
                    "review": "User-provided 01-08 jump reference: crouch, lift-off, airborne hold, landing squash, recover.",
                    "reference": "references/jump-ref.png",
                }
            )

    for series in data["seriesPlayback"]:
        if series["seriesId"] == "gesture-no-ball":
            series["rows"] = [row for row in series["rows"] if row != JUMP_ROW]
            series["playbackRule"] = "第 3 行参考 references/bie-ganmao-ref.jpg 做红围巾别感冒动作，本轮不加气泡。"
    data["seriesPlayback"] = [
        series for series in data["seriesPlayback"] if series["seriesId"] != "jump-no-ball"
    ]
    data["seriesPlayback"].append(
        {
            "seriesId": "jump-no-ball",
            "rows": [JUMP_ROW],
            "basketball": "none",
            "playbackRule": "双击触发 01-08 跳跃：下蹲蓄力、起跳、空中停顿、落地恢复。",
        }
    )

    data["plannedSimpleActions"] = [
        action for action in data["plannedSimpleActions"] if action["id"] != "jump"
    ]
    data["plannedSimpleActions"].append(
        {
            "id": "jump",
            "displayName": "跳跃",
            "priority": 5,
            "status": "reference-standard-v15",
            "implementedRow": JUMP_ROW,
            "view": "front",
            "basketball": {
                "mode": "none",
                "frames": [],
                "sourceObservation": "用户提供的 01-08 跳跃参考全程无篮球。",
            },
            "keyframes": [
                "front stance",
                "crouch preparation",
                "arms open during lift-off",
                "airborne hold",
                "arms fold during descent",
                "landing crouch",
                "return to neutral stance",
            ],
            "rigRequirements": [
                "root",
                "spine",
                "left-shoulder",
                "right-shoulder",
                "left-hip",
                "right-hip",
                "left-knee",
                "right-knee",
            ],
            "referenceMatch": "user-reference-jump-v15",
            "sourceImage": "references/jump-ref.png",
        }
    )
    write_json(path, data)


def update_pose_map() -> None:
    path = PET_DIR / "pose-map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("actionReferences", {})["jump"] = "references/jump-ref.png"
    write_json(path, data)


def update_motion_review(frames: list[Image.Image]) -> None:
    path = QA_DIR / "motion-review.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["source"] = "route1-v15-double-click-jump"
    data["generatedAt"] = datetime.now(timezone.utc).isoformat()
    for row in data["rows"]:
        if row["row"] == JUMP_ROW:
            row["frames"] = [frame_metrics(frame, index) for index, frame in enumerate(frames)]

    reference_updates = [
        item for item in data.get("referenceUpdates", []) if item.get("row") != JUMP_ROW
    ]
    reference_updates.append(
        {
            "row": JUMP_ROW,
            "action": "jump",
            "reference": "references/jump-ref.png",
            "basketball": "none",
            "frameOrder": "01-08",
            "runtimeAnimation": "fishEat",
            "trigger": "double-click",
        }
    )
    data["referenceUpdates"] = sorted(reference_updates, key=lambda item: item["row"])

    data["notes"] = [
        note
        for note in data.get("notes", [])
        if "Row 8" not in note and "row 8" not in note and "第 8 行" not in note
    ]
    data["notes"].append(
        "Row 8 was replaced from the user-provided 01-08 jump reference and is the ikun double-click action."
    )
    write_json(path, data)


def update_readme() -> None:
    path = PET_DIR / "README.md"
    text = path.read_text(encoding="utf-8")
    old = "Rows 0 and 8 have fewer runtime frames than the 8-column atlas."
    if old in text:
        text = text.replace(
            old,
            "Row 0 has fewer runtime frames than the 8-column atlas.",
        )
    marker = "当前动作行处于不同精修阶段。"
    if marker in text and "第 8 行记录为用户提供的双击跳跃动作" not in text:
        text = text.replace(
            "第 7 行记录为正面后撤步修复。",
            "第 7 行记录为正面后撤步修复，第 8 行记录为用户提供的双击跳跃动作。",
        )
    if "| 跳跃 | 正面 | 无球 | 双击触发" not in text:
        text = text.replace(
            "| 后撤步 | 正面 | 全帧有球 | 正面后撤步原型，篮球保持跟手并整体旋转；暂不使用侧面带球素材。 |\n",
            "| 后撤步 | 正面 | 全帧有球 | 正面后撤步原型，篮球保持跟手并整体旋转；暂不使用侧面带球素材。 |\n"
            "| 跳跃 | 正面 | 无球 | 双击触发，按 `references/jump-ref.png` 的 01-08 顺序完成下蹲、起跳、空中停顿、落地恢复。 |\n",
        )
    path.write_text(text, encoding="utf-8")


def update_sources() -> None:
    path = PET_DIR / "SOURCES.md"
    text = path.read_text(encoding="utf-8")
    line = "- `references/jump-ref.png`: user-provided 8-frame jump board for row 8 `jump`, used by the `ikun` double-click action.\n"
    if line not in text:
        anchor = "- `references/under-leg-dribble-ref.png`: user-provided 8-frame action board for row 4 `under-leg-dribble`.\n"
        text = text.replace(anchor, anchor + line)
    path.write_text(text, encoding="utf-8")


def validate_jump_row(atlas: Image.Image) -> dict[str, object]:
    errors: list[str] = []
    pre_existing_warnings: list[str] = []
    if atlas.size != (CELL_WIDTH * COLUMNS, CELL_HEIGHT * ROWS):
        errors.append(f"atlas size is {atlas.size}, expected {(CELL_WIDTH * COLUMNS, CELL_HEIGHT * ROWS)}")

    jump_frames = []
    for frame_index in range(COLUMNS):
        cell = atlas.crop(
            (
                frame_index * CELL_WIDTH,
                JUMP_ROW * CELL_HEIGHT,
                (frame_index + 1) * CELL_WIDTH,
                (JUMP_ROW + 1) * CELL_HEIGHT,
            )
        )
        metrics = frame_metrics(cell, frame_index)
        if metrics["usedPixels"] == 0:
            errors.append(f"jump row frame {frame_index} is empty")
        if metrics["touchesEdge"]:
            errors.append(f"jump row frame {frame_index} touches edge")
        jump_frames.append(metrics)

    for row_index in range(ROWS):
        if row_index == JUMP_ROW:
            continue
        for frame_index in range(COLUMNS):
            cell = atlas.crop(
                (
                    frame_index * CELL_WIDTH,
                    row_index * CELL_HEIGHT,
                    (frame_index + 1) * CELL_WIDTH,
                    (row_index + 1) * CELL_HEIGHT,
                )
            )
            metrics = frame_metrics(cell, frame_index)
            if metrics["touchesEdge"]:
                pre_existing_warnings.append(f"row {row_index} frame {frame_index} touches edge")

    return {
        "ok": not errors,
        "file": str(ATLAS_PATH),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "scope": "row-8-jump-v15",
        "cell": {
            "width": CELL_WIDTH,
            "height": CELL_HEIGHT,
            "columns": COLUMNS,
            "rows": ROWS,
        },
        "errors": errors,
        "preExistingWarnings": pre_existing_warnings,
        "row": {"row": JUMP_ROW, "frames": jump_frames},
    }


def main() -> None:
    if not REFERENCE_PATH.is_file():
        raise FileNotFoundError(REFERENCE_PATH)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    frames = build_jump_frames()
    (OUTPUT_DIR / "frames").mkdir(parents=True, exist_ok=True)
    row_strip = Image.new("RGBA", (CELL_WIDTH * COLUMNS, CELL_HEIGHT), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        row_strip.alpha_composite(frame, (index * CELL_WIDTH, 0))
        frame.save(OUTPUT_DIR / "frames" / f"frame-{index:02d}.png")
    row_strip.save(OUTPUT_DIR / "row-8-jump-v15.png")

    with Image.open(ATLAS_PATH) as source:
        atlas = source.convert("RGBA")
    cleared_row = Image.new("RGBA", (CELL_WIDTH * COLUMNS, CELL_HEIGHT), (0, 0, 0, 0))
    atlas.paste(cleared_row, (0, JUMP_ROW * CELL_HEIGHT))
    atlas.alpha_composite(row_strip, (0, JUMP_ROW * CELL_HEIGHT))
    atlas.save(OUTPUT_DIR / "spritesheet-v15.png")
    atlas.save(ATLAS_PATH, lossless=True, quality=100, method=6)

    save_gif(frames, PREVIEW_DIR / "row-8.gif")
    save_gif(frames, OUTPUT_DIR / "row-8-jump-v15.gif")
    write_json(OUTPUT_DIR / "atlas-validation.json", validate_jump_row(atlas))

    update_actions()
    update_action_board()
    update_pose_map()
    update_motion_review(frames)
    update_readme()
    update_sources()
    print("ikun v15 double-click jump assets and metadata rebuilt")


if __name__ == "__main__":
    main()
