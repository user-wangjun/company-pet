#!/usr/bin/env python3
"""从参考图提取 ikun 丢球帧、清理地面阴影，并生成无球收尾帧。"""

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
OUTPUT_DIR = PET_DIR / "qa" / "throw-v14"
FRAME_DIR = OUTPUT_DIR / "frames"
CELL_WIDTH = 192
CELL_HEIGHT = 208
THROW_ROW = 6
SCALE = 0.48
BASELINE_Y = 190
BODY_CENTER_X = 96
FINISH_CROP = (350, 100, 1120, 980)

PANELS = [
    (0, 40, 362, 500),
    (362, 40, 724, 500),
    (724, 40, 1086, 500),
    (1086, 40, 1448, 500),
    (0, 550, 362, 970),
    (362, 550, 724, 970),
    (724, 550, 1086, 970),
    (1086, 550, 1448, 970),
]


def fill_holes(mask: np.ndarray) -> np.ndarray:
    flood = mask.copy()
    flood_fill = np.zeros((mask.shape[0] + 2, mask.shape[1] + 2), dtype=np.uint8)
    cv2.floodFill(flood, flood_fill, (0, 0), 255)
    holes = cv2.bitwise_not(flood)
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(holes, 8)
    ys, _xs = np.nonzero(mask)
    if len(ys) == 0:
        return mask

    subject_top = int(ys.min())
    subject_bottom = int(ys.max())
    upper_body_limit = round(
        subject_top + (subject_bottom - subject_top) * 0.64
    )
    filled = mask.copy()
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        component_bottom = int(
            stats[label, cv2.CC_STAT_TOP] + stats[label, cv2.CC_STAT_HEIGHT]
        )
        if component_bottom <= upper_body_limit or area <= 64:
            filled[labels == label] = 255
    return filled


def remove_thin_white_marks(mask: np.ndarray, hsv: np.ndarray) -> np.ndarray:
    near_white = (
        (hsv[:, :, 1] < 28)
        & (hsv[:, :, 2] > 218)
        & (mask > 0)
    ).astype(np.uint8)
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(near_white, 8)
    cleaned = mask.copy()
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        is_thin_line = (
            area < 300
            and width > 8
            and (height <= 4 or width >= height * 2.8)
        )
        if is_thin_line:
            cleaned[labels == label] = 0
    return cleaned


def remove_ground_shadow(mask: np.ndarray, hsv: np.ndarray) -> np.ndarray:
    """按鞋底基线移除浅灰地面阴影，同时保留深色鞋体。"""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return mask

    source_top = int(ys.min())
    source_bottom = int(ys.max())
    lower_start = round(source_top + (source_bottom - source_top) * 0.66)
    value = hsv[:, :, 2]
    saturation = hsv[:, :, 1]
    y_grid = np.indices(mask.shape)[0]
    shoe_dark = (
        (mask > 0)
        & (value < 120)
        & (y_grid >= lower_start)
    )
    shoe_ys, _shoe_xs = np.nonzero(shoe_dark)
    if len(shoe_ys) < 20:
        return mask

    shoe_bottom = int(round(float(np.percentile(shoe_ys, 99.6))))
    cleanup_band = max(16, round((source_bottom - source_top) * 0.045))
    floor_candidate = (
        (mask > 0)
        & (y_grid >= shoe_bottom - cleanup_band)
        & (saturation < 45)
        & (value > 92)
    )

    cleaned = mask.copy()
    cleaned[floor_candidate] = 0
    cleaned[y_grid > shoe_bottom + 1] = 0
    return cleaned


def remove_background_fringe(mask: np.ndarray, hsv: np.ndarray) -> np.ndarray:
    """移除贴在角色外轮廓上的浅色背景边，不处理主体内部的眼白等区域。"""
    distance = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    fringe = (
        (mask > 0)
        & (distance <= 8)
        & (hsv[:, :, 1] < 38)
        & (hsv[:, :, 2] > 202)
    )
    cleaned = mask.copy()
    cleaned[fringe] = 0
    return cleaned


def foreground_mask(panel_rgb: np.ndarray) -> np.ndarray:
    panel_bgr = cv2.cvtColor(panel_rgb, cv2.COLOR_RGB2BGR)
    height, width = panel_bgr.shape[:2]
    grab_mask = np.full((height, width), cv2.GC_PR_BGD, dtype=np.uint8)

    border = 8
    grab_mask[:border, :] = cv2.GC_BGD
    grab_mask[-border:, :] = cv2.GC_BGD
    grab_mask[:, :border] = cv2.GC_BGD
    grab_mask[:, -border:] = cv2.GC_BGD

    hsv = cv2.cvtColor(panel_bgr, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    strong_color = (saturation > 55) & (value > 35)
    dark_detail = value < 145
    grab_mask[strong_color | dark_detail] = cv2.GC_FGD

    background_model = np.zeros((1, 65), np.float64)
    foreground_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(
        panel_bgr,
        grab_mask,
        None,
        background_model,
        foreground_model,
        6,
        cv2.GC_INIT_WITH_MASK,
    )
    raw = np.where(
        (grab_mask == cv2.GC_FGD) | (grab_mask == cv2.GC_PR_FGD),
        255,
        0,
    ).astype(np.uint8)
    # 浅灰背带裤与背景接近，GrabCut 在部分姿势会挖掉裤腿。
    # 将明显偏暗或有颜色的像素并入候选前景，再通过组件规则去掉地面阴影。
    material_candidate = (saturation > 28) | (value < 210)
    raw[material_candidate] = 255

    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(raw, 8)
    if count <= 1:
        raise RuntimeError("未能从参考格子中提取前景")

    component_areas = stats[1:, cv2.CC_STAT_AREA]
    largest_label = int(np.argmax(component_areas)) + 1
    keep = labels == largest_label

    orange = (
        ((hsv[:, :, 0] <= 18) | (hsv[:, :, 0] >= 175))
        & (saturation >= 135)
        & (value >= 120)
    )
    for label in range(1, count):
        if label == largest_label:
            continue
        component = labels == label
        area = int(stats[label, cv2.CC_STAT_AREA])
        orange_pixels = int(np.count_nonzero(component & orange))
        if area >= 650 and orange_pixels >= 180:
            keep |= component

    cleaned = (keep.astype(np.uint8) * 255)
    cleaned = cv2.morphologyEx(
        cleaned,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    cleaned = remove_thin_white_marks(cleaned, hsv)
    cleaned = fill_holes(cleaned)
    cleaned = remove_ground_shadow(cleaned, hsv)
    cleaned = remove_background_fringe(cleaned, hsv)
    return cv2.erode(
        cleaned,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        iterations=2,
    )


def body_anchor(mask: np.ndarray) -> tuple[float, float]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        raise RuntimeError("前景遮罩为空")

    baseline = float(np.percentile(ys, 99.8))
    lower_cutoff = float(np.percentile(ys, 58))
    lower_xs = xs[ys >= lower_cutoff]
    center_x = float(np.median(lower_xs if len(lower_xs) else xs))
    return center_x, baseline


def resize_rgba_premultiplied(
    image: Image.Image,
    size: tuple[int, int],
) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
    alpha = rgba[:, :, 3:4] / 255.0
    premultiplied = rgba.copy()
    premultiplied[:, :, :3] *= alpha
    resized = np.asarray(
        Image.fromarray(np.uint8(np.clip(premultiplied, 0, 255))).resize(
            size,
            Image.Resampling.LANCZOS,
        ),
        dtype=np.float32,
    )
    resized_alpha = resized[:, :, 3:4]
    visible = resized_alpha[:, :, 0] > 0
    resized_rgb = np.zeros_like(resized[:, :, :3])
    resized_rgb[visible] = (
        resized[visible, :3] * 255.0 / resized_alpha[visible]
    )
    output = np.dstack([resized_rgb, resized_alpha])
    return Image.fromarray(np.uint8(np.clip(output, 0, 255)))


def remove_resized_fringe(image: Image.Image) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA")).copy()
    visible = (rgba[:, :, 3] > 8).astype(np.uint8) * 255
    distance = cv2.distanceTransform(visible, cv2.DIST_L2, 5)
    hsv = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2HSV)
    fringe = (
        (visible > 0)
        & (distance <= 2.4)
        & (hsv[:, :, 1] < 48)
        & (hsv[:, :, 2] > 185)
    )
    rgba[fringe] = 0
    return Image.fromarray(rgba)


def render_frame(
    panel: Image.Image,
    scale: float | None = None,
) -> tuple[Image.Image, dict[str, object]]:
    panel_rgb = np.asarray(panel.convert("RGB"))
    mask = foreground_mask(panel_rgb)
    anchor_x, baseline = body_anchor(mask)

    ys, xs = np.nonzero(mask)
    source_left = int(xs.min())
    source_top = int(ys.min())
    source_right = int(xs.max()) + 1
    source_bottom = int(ys.max()) + 1

    rgba = np.dstack([panel_rgb, mask]).astype(np.uint8)
    rgba[mask == 0, :3] = 0
    sprite = Image.fromarray(rgba).crop(
        (source_left, source_top, source_right, source_bottom)
    )

    applied_scale = scale
    if applied_scale is None:
        applied_scale = min(
            SCALE,
            184 / sprite.width,
            164 / sprite.height,
        )
    target_width = max(1, round(sprite.width * applied_scale))
    target_height = max(1, round(sprite.height * applied_scale))
    sprite = resize_rgba_premultiplied(sprite, (target_width, target_height))
    sprite = remove_resized_fringe(sprite)

    anchor_in_crop_x = (anchor_x - source_left) * applied_scale
    baseline_in_crop = (baseline - source_top) * applied_scale
    left = round(BODY_CENTER_X - anchor_in_crop_x)
    top = round(BASELINE_Y - baseline_in_crop)

    margin = 3
    if left < margin:
        left = margin
    if left + sprite.width > CELL_WIDTH - margin:
        left = CELL_WIDTH - margin - sprite.width
    if top < margin:
        top = margin
    if top + sprite.height > CELL_HEIGHT - margin:
        top = CELL_HEIGHT - margin - sprite.height

    frame = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
    frame.alpha_composite(sprite, (left, top))
    alpha = np.asarray(frame.getchannel("A"))
    used_y, used_x = np.nonzero(alpha > 8)
    bbox = [
        int(used_x.min()),
        int(used_y.min()),
        int(used_x.max()) + 1,
        int(used_y.max()) + 1,
    ]
    metadata = {
        "bbox": bbox,
        "usedPixels": int(np.count_nonzero(alpha > 8)),
        "sourceAnchor": [round(anchor_x, 2), round(baseline, 2)],
        "placement": [left, top],
        "scale": round(applied_scale, 6),
    }
    return frame, metadata


def build_frames() -> tuple[list[Image.Image], list[dict[str, object]]]:
    with Image.open(REFERENCE_PATH) as source:
        reference = source.convert("RGB")

    frames: list[Image.Image] = []
    metadata: list[dict[str, object]] = []
    FRAME_DIR.mkdir(parents=True, exist_ok=True)

    for index, panel_box in enumerate(PANELS):
        panel = reference.crop(panel_box)
        frame, frame_metadata = render_frame(panel, SCALE)
        frame_path = FRAME_DIR / f"frame-{index:02d}.png"
        frame.save(frame_path)
        frame_metadata.update(
            {
                "frame": index,
                "sourceFrame": f"{index + 9:02d}",
                "path": str(frame_path.relative_to(PET_DIR)).replace("\\", "/"),
            }
        )
        frames.append(frame)
        metadata.append(frame_metadata)

    strip = Image.new("RGBA", (CELL_WIDTH * 8, CELL_HEIGHT), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        strip.alpha_composite(frame, (index * CELL_WIDTH, 0))
    strip.save(OUTPUT_DIR / "row-6-throw-v14.png")
    (OUTPUT_DIR / "frame-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return frames, metadata


def build_finish_frame() -> dict[str, object]:
    with Image.open(FINISH_REFERENCE_PATH) as source:
        panel = source.convert("RGB").crop(FINISH_CROP)

    frame, metadata = render_frame(panel)
    frame.save(FINISH_FRAME_PATH)
    frame.save(OUTPUT_DIR / "frame-08-finish.png")
    metadata.update(
        {
            "frame": 8,
            "sourceFrame": "17",
            "path": FINISH_FRAME_PATH.name,
            "sourceImage": str(
                FINISH_REFERENCE_PATH.relative_to(PET_DIR)
            ).replace("\\", "/"),
            "basketball": "none",
        }
    )
    return metadata


def apply_to_atlas(frames: list[Image.Image]) -> None:
    with Image.open(ATLAS_PATH) as source:
        atlas = source.convert("RGBA")

    before = np.asarray(atlas).copy()
    top = THROW_ROW * CELL_HEIGHT
    atlas.paste((0, 0, 0, 0), (0, top, atlas.width, top + CELL_HEIGHT))
    for index, frame in enumerate(frames):
        atlas.alpha_composite(frame, (index * CELL_WIDTH, top))

    after = np.asarray(atlas)
    unchanged_rows = np.concatenate(
        [before[:top], before[top + CELL_HEIGHT :]],
        axis=0,
    )
    resulting_rows = np.concatenate(
        [after[:top], after[top + CELL_HEIGHT :]],
        axis=0,
    )
    if not np.array_equal(unchanged_rows, resulting_rows):
        raise RuntimeError("替换第 6 行时意外修改了其他图集行")

    normalized = np.asarray(atlas).copy()
    normalized[normalized[:, :, 3] == 0, :3] = 0
    atlas = Image.fromarray(normalized)
    atlas.save(OUTPUT_DIR / "spritesheet-v14.png")
    atlas.save(ATLAS_PATH, "WEBP", lossless=True, method=6, exact=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="将生成的八帧覆盖到正式 spritesheet.webp 第 6 行",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames, metadata = build_frames()
    finish_metadata = build_finish_frame()
    if args.apply:
        apply_to_atlas(frames)

    print(
        json.dumps(
            {
                "ok": True,
                "applied": args.apply,
                "outputDir": str(OUTPUT_DIR),
                "frames": [*metadata, finish_metadata],
                "finishFrame": str(FINISH_FRAME_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
