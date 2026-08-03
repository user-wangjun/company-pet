from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
UPPER = ROOT / "blueprints" / "v2-upper-body-ownership-contract.json"
LOWER = ROOT / "blueprints" / "v2-lower-body-ownership-contract.json"
HIDDEN = ROOT / "blueprints" / "v2-hidden-thigh-contract.json"
OUT = ROOT / "model" / "working-v8" / "body-original-pixel"
QA = ROOT / "qa" / "v8-body-original-pixel-ownership-review.png"
REPORT = ROOT / "audit" / "v8-body-original-pixel-ownership.json"
CANVAS = (512, 1086)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def polygon_mask(polygons: list[list[list[int]]]) -> np.ndarray:
    image = Image.new("L", CANVAS, 0)
    draw = ImageDraw.Draw(image)
    for polygon in polygons:
        draw.polygon([tuple(point) for point in polygon], fill=255)
    return np.asarray(image) > 0


def border_connected(candidate: np.ndarray) -> np.ndarray:
    h, w = candidate.shape
    seen = np.zeros_like(candidate, dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if candidate[y, x] and not seen[y, x]:
                seen[y, x] = True
                queue.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if candidate[y, x] and not seen[y, x]:
                seen[y, x] = True
                queue.append((y, x))
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and candidate[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                queue.append((ny, nx))
    return seen


def rgba(source: np.ndarray, mask: np.ndarray) -> Image.Image:
    result = np.zeros((CANVAS[1], CANVAS[0], 4), dtype=np.uint8)
    result[:, :, :3] = source
    result[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
    return Image.fromarray(result, "RGBA")


def checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    w, h = size
    yy, xx = np.indices((h, w))
    pattern = (xx // cell + yy // cell) % 2
    values = np.where(pattern[:, :, None] == 0, 239, 207).astype(np.uint8)
    return Image.fromarray(np.repeat(values, 3, axis=2), "RGB")


def crop_checker(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    crop = image.crop(box).convert("RGBA")
    bg = checker(crop.size)
    bg.paste(crop, (0, 0), crop)
    return bg


def fit_panel(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    panel = Image.new("RGB", size, "white")
    copy = image.copy()
    copy.thumbnail((size[0] - 16, size[1] - 16), Image.Resampling.NEAREST)
    panel.paste(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return panel


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    QA.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    source_image = Image.open(SOURCE).convert("RGB")
    line_image = Image.open(LINE).convert("RGB")
    source = np.asarray(source_image)
    if source_image.size != CANVAS or line_image.size != CANVAS:
        raise ValueError("线稿和彩稿必须保持锁定的 512×1086 坐标")

    upper = json.loads(UPPER.read_text(encoding="utf-8"))
    lower = json.loads(LOWER.read_text(encoding="utf-8"))
    hidden = json.loads(HIDDEN.read_text(encoding="utf-8"))
    groups = upper["groups"] + lower["groups"]
    polygon_by_id = {group["id"]: [group["polygon"]] for group in groups}
    hidden_by_id = {item["id"]: item["polygon"] for item in hidden["frontHiddenCandidates"]}

    rgb_max = np.max(source, axis=2).astype(np.int16)
    rgb_min = np.min(source, axis=2).astype(np.int16)
    luminance = (
        0.2126 * source[:, :, 0]
        + 0.7152 * source[:, :, 1]
        + 0.0722 * source[:, :, 2]
    )
    background_candidate = (luminance > 236) & ((rgb_max - rgb_min) < 11)
    subject = ~border_connected(background_candidate)

    masks: dict[str, np.ndarray] = {}
    for layer_id, polygons in polygon_by_id.items():
        masks[layer_id] = polygon_mask(polygons) & subject

    # Keep each visible source pixel in its original coordinates. Hidden thigh
    # rectangles are recorded separately and are not textured in this ownership
    # pass, preventing the old “small coloured block” failure.
    hidden_masks = {
        "leg_screen_left": polygon_mask([hidden_by_id["leg_screen_left_hidden_thigh"]]) & masks["skirt"],
        "leg_screen_right": polygon_mask([hidden_by_id["leg_screen_right_hidden_thigh"]]) & masks["skirt"],
    }

    draw_order = [
        "neck",
        "torso_tshirt_core",
        "sleeve_screen_left",
        "sleeve_screen_right",
        "arm_screen_left_forearm",
        "arm_screen_right_forearm",
        "hand_screen_left",
        "hand_screen_right",
        "necklace",
        "leg_screen_left",
        "leg_screen_right",
        "skirt",
        "sock_screen_left",
        "sock_screen_right",
        "shoe_screen_left",
        "shoe_screen_right",
    ]
    layers: dict[str, Image.Image] = {}
    union = np.zeros((CANVAS[1], CANVAS[0]), dtype=bool)
    for index, layer_id in enumerate(draw_order, start=1):
        image = rgba(source, masks[layer_id])
        image.save(OUT / f"{index:02d}_{layer_id}.png")
        layers[layer_id] = image
        union |= masks[layer_id]

    body_rebuild = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer_id in draw_order:
        body_rebuild = Image.alpha_composite(body_rebuild, layers[layer_id])
    body_rebuild.save(OUT / "身体候选层回组.png")

    residual = rgba(source, ~union)
    default = residual.copy()
    for layer_id in draw_order:
        default = Image.alpha_composite(default, layers[layer_id])
    default.save(OUT / "默认全图回贴.png")
    diff = ImageChops.difference(default.convert("RGB"), source_image)
    diff_array = np.asarray(diff)
    mae = float(diff_array.mean())
    max_error = int(diff_array.max())

    upper_ids = draw_order[:9]
    lower_ids = draw_order[9:]
    upper_rebuild = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    lower_rebuild = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer_id in upper_ids:
        upper_rebuild = Image.alpha_composite(upper_rebuild, layers[layer_id])
    for layer_id in lower_ids:
        lower_rebuild = Image.alpha_composite(lower_rebuild, layers[layer_id])

    full_crop = (55, 185, 455, 1065)
    upper_crop = (55, 185, 455, 650)
    lower_crop = (115, 550, 390, 1065)
    original = source_image.crop(full_crop)
    body = crop_checker(body_rebuild, full_crop)
    upper_view = crop_checker(upper_rebuild, upper_crop)
    lower_view = crop_checker(lower_rebuild, lower_crop)
    line_view = line_image.crop(full_crop)
    diff_view = diff.crop(full_crop)

    panel_size = (380, 620)
    title_h = 64
    footer_h = 156
    sheet = Image.new("RGB", (panel_size[0] * 3, (panel_size[1] + title_h) * 2 + footer_h), "white")
    draw = ImageDraw.Draw(sheet)
    entries = [
        ("① 原彩稿身体", original),
        ("② 线稿边界参考", line_view),
        ("③ 原像素身体候选层回组", body),
        ("④ 上身候选层", upper_view),
        ("⑤ 下身候选层", lower_view),
        ("⑥ 默认回贴差异", diff_view),
    ]
    for index, (title, image) in enumerate(entries):
        row, col = divmod(index, 3)
        x = col * panel_size[0]
        y = row * (panel_size[1] + title_h)
        draw.text((x + 14, y + 17), title, fill="#171717", font=font(21))
        fitted = fit_panel(image, panel_size)
        sheet.paste(fitted, (x, y + title_h))
        draw.rectangle(
            (x, y + title_h, x + panel_size[0] - 1, y + title_h + panel_size[1] - 1),
            outline="#777777",
            width=2,
        )

    footer_y = (panel_size[1] + title_h) * 2 + 16
    draw.text(
        (20, footer_y),
        "本轮改为复制原彩稿像素，不再使用平色色块；双手仍按每侧一整层，不拆手指。",
        fill="#222222",
        font=font(21),
    )
    draw.text(
        (20, footer_y + 40),
        "裙内大腿只记录隐藏范围，尚未补画，因此不会再出现缩小的腿部色块。",
        fill="#222222",
        font=font(21),
    )
    draw.text(
        (20, footer_y + 82),
        f"默认回贴：MAE={mae:.3f}，最大通道差={max_error}；候选边界仍需逐项接缝审查后才能进 PSD。",
        fill="#8D251E",
        font=font(21),
    )
    sheet.save(QA)

    REPORT.write_text(
        json.dumps(
            {
                "stage": "v8-body-original-pixel-ownership",
                "source": str(SOURCE.relative_to(ROOT)),
                "lineReference": str(LINE.relative_to(ROOT)),
                "drawOrder": draw_order,
                "defaultCompositeMae": mae,
                "defaultCompositeMaxError": max_error,
                "visiblePixelsRepainted": False,
                "hiddenThighStatus": {
                    layer_id: {
                        "pixelCount": int(mask.sum()),
                        "status": "range_only_not_textured",
                    }
                    for layer_id, mask in hidden_masks.items()
                },
                "hands": "one_complete_layer_per_side_no_finger_rig",
                "psdImport": False,
                "cubismImport": False,
                "next": "line-edge-seam-review-and-hidden-fill",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
