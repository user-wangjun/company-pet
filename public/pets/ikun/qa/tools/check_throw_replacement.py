#!/usr/bin/env python3
"""检查 ikun 的 09-17 丢球动作、透明背景和无球收尾是否完整。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


PET_DIR = Path(__file__).resolve().parents[2]
REFERENCE_PATH = PET_DIR / "references" / "throw-09-16-ref.png"
FINISH_REFERENCE_PATH = PET_DIR / "references" / "throw-finish-ref.png"
FINISH_FRAME_PATH = PET_DIR / "throw-finish.png"
ATLAS_PATH = PET_DIR / "spritesheet.webp"
CELL_WIDTH = 192
CELL_HEIGHT = 208
THROW_ROW = 6
EXPECTED_SOURCE_FRAMES = [f"{index:02d}" for index in range(9, 17)]
EXPECTED_RUNTIME_FRAMES = [*EXPECTED_SOURCE_FRAMES, "17"]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_reference(errors: list[str]) -> None:
    require(REFERENCE_PATH.is_file(), "缺少包内参考图 references/throw-09-16-ref.png", errors)
    require(
        FINISH_REFERENCE_PATH.is_file(),
        "缺少包内参考图 references/throw-finish-ref.png",
        errors,
    )


def count_pale_floor_pixels(frame: Image.Image) -> int:
    rgba = np.asarray(frame.convert("RGBA"))
    hsv = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2HSV)
    alpha = rgba[:, :, 3] > 8
    ys, _xs = np.nonzero(alpha)
    if len(ys) == 0:
        return 0
    bottom = int(ys.max())
    y_grid = np.indices(alpha.shape)[0]
    pale_floor = (
        alpha
        & (y_grid >= bottom - 12)
        & (hsv[:, :, 1] < 45)
        & (hsv[:, :, 2] > 120)
    )
    return int(np.count_nonzero(pale_floor))


def check_manifest(errors: list[str]) -> None:
    manifest = load_json(PET_DIR / "pet.json")
    require(
        manifest.get("throwFinishPath") == "throw-finish.png",
        "pet.json 未声明 throw-finish.png 收尾帧",
        errors,
    )


def check_actions(errors: list[str]) -> None:
    actions = load_json(PET_DIR / "actions.json")
    require(actions.get("version", 0) >= 14, "actions.json 版本尚未更新到 v14", errors)

    throw_action = next(
        (item for item in actions.get("actions", []) if item.get("id") == "throw-basketball"),
        None,
    )
    require(throw_action is not None, "actions.json 缺少 throw-basketball 动作", errors)
    if throw_action is None:
        return

    require(
        throw_action.get("sourceImage") == "references/throw-09-16-ref.png",
        "throw-basketball 未引用 09-16 包内参考图",
        errors,
    )
    require(
        throw_action.get("sourceFrames") == EXPECTED_RUNTIME_FRAMES,
        "throw-basketball 的源帧顺序不是 09-17",
        errors,
    )

    basketball = throw_action.get("basketball", {})
    require(
        basketball.get("frames") == list(range(8)),
        "09-16 帧应记录完整篮球位置",
        errors,
    )
    require(
        basketball.get("absentFrames") == [8],
        "第 17 帧应记录篮球消失",
        errors,
    )
    require(
        throw_action.get("finishFramePath") == "throw-finish.png",
        "throw-basketball 未声明独立无球收尾帧",
        errors,
    )
    require(
        throw_action.get("runtimeFrames") == 9,
        "throw-basketball 运行时帧数应为 9",
        errors,
    )


def check_pose_map(errors: list[str]) -> None:
    pose_map = load_json(PET_DIR / "pose-map.json")
    require(
        pose_map.get("revision") == "route1-v14-throw-finish",
        "pose-map.json 修订号尚未更新为 route1-v14-throw-finish",
        errors,
    )
    row = pose_map.get("rows", {}).get(str(THROW_ROW), [])
    require(len(row) == 9, "pose-map.json 丢球动作不是九帧", errors)
    if len(row) != 9:
        return

    require(
        [item.get("sourceFrame") for item in row] == EXPECTED_RUNTIME_FRAMES,
        "pose-map.json 丢球动作源帧顺序不是 09-17",
        errors,
    )
    require(
        all(
            item.get("sourceImage") == "references/throw-09-16-ref.png"
            for item in row[:8]
        ),
        "pose-map.json 09-16 帧存在错误参考图",
        errors,
    )
    require(
        row[8].get("sourceImage") == "references/throw-finish-ref.png"
        and row[8].get("storage") == "throw-finish.png"
        and row[8].get("basketball") == "absent",
        "pose-map.json 第 17 帧未正确声明无球独立收尾",
        errors,
    )


def check_atlas(errors: list[str]) -> dict[str, object]:
    with Image.open(ATLAS_PATH) as source:
        atlas = source.convert("RGBA")

    require(atlas.size == (CELL_WIDTH * 8, CELL_HEIGHT * 9), "spritesheet.webp 尺寸错误", errors)
    atlas_data = list(atlas.getdata())
    transparent_rgb_residue = sum(
        1 for red, green, blue, alpha in atlas_data if alpha == 0 and (red or green or blue)
    )
    require(
        transparent_rgb_residue == 0,
        f"图集存在 {transparent_rgb_residue} 个带隐藏 RGB 的全透明像素",
        errors,
    )
    frame_results: list[dict[str, object]] = []
    for frame_index in range(8):
        left = frame_index * CELL_WIDTH
        top = THROW_ROW * CELL_HEIGHT
        cell = atlas.crop((left, top, left + CELL_WIDTH, top + CELL_HEIGHT))
        alpha = cell.getchannel("A")
        used_pixels = sum(1 for value in alpha.getdata() if value > 8)
        require(
            used_pixels >= 6000,
            f"第 6 行第 {frame_index} 帧有效像素过少：{used_pixels}",
            errors,
        )
        transparent_corners = all(
            value <= 8
            for value in (
                alpha.getpixel((0, 0)),
                alpha.getpixel((CELL_WIDTH - 1, 0)),
                alpha.getpixel((0, CELL_HEIGHT - 1)),
                alpha.getpixel((CELL_WIDTH - 1, CELL_HEIGHT - 1)),
            )
        )
        require(
            transparent_corners,
            f"第 6 行第 {frame_index} 帧角落不透明，可能残留背景",
            errors,
        )
        pale_floor_pixels = count_pale_floor_pixels(cell)
        require(
            pale_floor_pixels <= 220,
            f"第 6 行第 {frame_index} 帧脚边浅色背景残留过多：{pale_floor_pixels}",
            errors,
        )
        frame_results.append(
            {
                "frame": frame_index,
                "usedPixels": used_pixels,
                "transparentCorners": transparent_corners,
                "paleFloorPixels": pale_floor_pixels,
            }
        )
    return {
        "width": atlas.width,
        "height": atlas.height,
        "transparentRgbResiduePixels": transparent_rgb_residue,
        "throwRow": frame_results,
    }


def check_finish_frame(errors: list[str]) -> dict[str, object]:
    require(FINISH_FRAME_PATH.is_file(), "缺少独立收尾帧 throw-finish.png", errors)
    if not FINISH_FRAME_PATH.is_file():
        return {}

    with Image.open(FINISH_FRAME_PATH) as source:
        frame = source.convert("RGBA")

    require(frame.size == (CELL_WIDTH, CELL_HEIGHT), "throw-finish.png 尺寸错误", errors)
    rgba = np.asarray(frame)
    alpha = rgba[:, :, 3]
    used_pixels = int(np.count_nonzero(alpha > 8))
    require(used_pixels >= 5000, f"收尾帧有效像素过少：{used_pixels}", errors)
    transparent_corners = all(
        alpha[y, x] <= 8
        for x, y in (
            (0, 0),
            (CELL_WIDTH - 1, 0),
            (0, CELL_HEIGHT - 1),
            (CELL_WIDTH - 1, CELL_HEIGHT - 1),
        )
    )
    require(transparent_corners, "收尾帧角落不透明，可能残留背景", errors)
    pale_floor_pixels = count_pale_floor_pixels(frame)
    require(
        pale_floor_pixels <= 220,
        f"收尾帧脚边浅色背景残留过多：{pale_floor_pixels}",
        errors,
    )

    hsv = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2HSV)
    orange = (
        (alpha > 8)
        & (hsv[:, :, 0] >= 3)
        & (hsv[:, :, 0] <= 18)
        & (hsv[:, :, 1] >= 150)
        & (hsv[:, :, 2] >= 130)
    ).astype(np.uint8)
    count, _labels, stats, _centroids = cv2.connectedComponentsWithStats(orange, 8)
    largest_orange_component = (
        int(stats[1:, cv2.CC_STAT_AREA].max()) if count > 1 else 0
    )
    require(
        largest_orange_component <= 850,
        f"收尾帧疑似仍有篮球，最大橙色连通区域：{largest_orange_component}",
        errors,
    )
    return {
        "usedPixels": used_pixels,
        "transparentCorners": transparent_corners,
        "paleFloorPixels": pale_floor_pixels,
        "largestOrangeComponent": largest_orange_component,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out")
    args = parser.parse_args()

    errors: list[str] = []
    check_reference(errors)
    check_manifest(errors)
    check_actions(errors)
    check_pose_map(errors)
    atlas_result = check_atlas(errors)
    finish_result = check_finish_frame(errors)

    result = {
        "ok": not errors,
        "file": str(ATLAS_PATH),
        "reference": str(REFERENCE_PATH.relative_to(PET_DIR)).replace("\\", "/"),
        "sourceFrames": EXPECTED_RUNTIME_FRAMES,
        "atlas": atlas_result,
        "finishFrame": finish_result,
        "errors": errors,
    }
    if args.json_out:
        output = Path(args.json_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if errors:
        print("ikun 丢球动作替换检查失败：")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("ikun 09-17 丢球动作、透明背景和无球收尾检查通过")


if __name__ == "__main__":
    main()
