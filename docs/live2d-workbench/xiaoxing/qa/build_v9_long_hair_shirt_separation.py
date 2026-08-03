from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
UPPER = ROOT / "blueprints" / "v2-upper-body-ownership-contract.json"
V6_HAIR = ROOT / "model" / "working-v6" / "face-eye-sample" / "前发_修订原像素.png"
OUT = ROOT / "model" / "working-v9" / "long-hair-shirt"
QA = ROOT / "qa" / "v9-long-hair-shirt-separation-review.png"
REPORT = ROOT / "audit" / "v9-long-hair-shirt-separation.json"
CANVAS = (512, 1086)
CROP = (145, 165, 370, 410)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def polygon_mask(polygons: list[list[tuple[int, int]]]) -> np.ndarray:
    image = Image.new("L", CANVAS, 0)
    draw = ImageDraw.Draw(image)
    for points in polygons:
        draw.polygon(points, fill=255)
    return np.asarray(image) > 0


def connected_from_seed(candidate: np.ndarray, seed: np.ndarray) -> np.ndarray:
    h, w = candidate.shape
    seen = np.zeros_like(candidate, dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    ys, xs = np.nonzero(candidate & seed)
    for y, x in zip(ys.tolist(), xs.tolist()):
        if not seen[y, x]:
            seen[y, x] = True
            queue.append((y, x))
    while queue:
        y, x = queue.popleft()
        for ny in range(max(0, y - 1), min(h, y + 2)):
            for nx in range(max(0, x - 1), min(w, x + 2)):
                if candidate[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
    return seen


def rgba(rgb: np.ndarray, mask: np.ndarray) -> Image.Image:
    result = np.zeros((CANVAS[1], CANVAS[0], 4), dtype=np.uint8)
    result[:, :, :3] = rgb
    result[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
    return Image.fromarray(result, "RGBA")


def checker(size: tuple[int, int], cell: int = 10) -> Image.Image:
    w, h = size
    yy, xx = np.indices((h, w))
    board = (xx // cell + yy // cell) % 2
    values = np.where(board[:, :, None] == 0, 239, 207).astype(np.uint8)
    return Image.fromarray(np.repeat(values, 3, axis=2), "RGB")


def crop_checker(image: Image.Image) -> Image.Image:
    crop = image.crop(CROP).convert("RGBA")
    bg = checker(crop.size)
    bg.paste(crop, (0, 0), crop)
    return bg


def fit_panel(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    panel = Image.new("RGB", size, "white")
    copy = image.copy()
    copy.thumbnail((size[0] - 16, size[1] - 16), Image.Resampling.NEAREST)
    panel.paste(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return panel


def row_shirt_fill(source: np.ndarray, shirt: np.ndarray, hair: np.ndarray) -> np.ndarray:
    result = source.copy()
    r = source[:, :, 0].astype(np.int16)
    g = source[:, :, 1].astype(np.int16)
    b = source[:, :, 2].astype(np.int16)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    neutral_light = shirt & ~hair & (luminance > 184) & ((np.maximum.reduce([r, g, b]) - np.minimum.reduce([r, g, b])) < 34)

    row_colors: dict[int, np.ndarray] = {}
    for y in range(218, 585):
        pixels = source[y][neutral_light[y]]
        if len(pixels) >= 8:
            row_colors[y] = np.median(pixels, axis=0)
    known_rows = np.array(sorted(row_colors), dtype=np.int32)
    if len(known_rows) == 0:
        raise ValueError("无法从衣身可见区域估计隐藏补底颜色")

    hidden = shirt & hair
    for y in np.nonzero(hidden.any(axis=1))[0]:
        nearest = int(known_rows[np.argmin(np.abs(known_rows - y))])
        base = row_colors[nearest]
        xs = np.nonzero(hidden[y])[0]
        # Keep a tiny horizontal value variation so the revealed area does not
        # become a visibly flat rectangular patch.
        shade = ((xs - 255.0) / 110.0)[:, None] * np.array([2.0, 2.0, 1.0])[None, :]
        result[y, xs] = np.clip(base[None, :] + shade, 0, 255).astype(np.uint8)
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    QA.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    source_image = Image.open(SOURCE).convert("RGB")
    line_image = Image.open(LINE).convert("RGB")
    source = np.asarray(source_image)
    if source_image.size != CANVAS or line_image.size != CANVAS:
        raise ValueError("线稿和彩稿必须保持 512×1086 原始坐标")

    upper = json.loads(UPPER.read_text(encoding="utf-8"))
    torso_polygon = next(group["polygon"] for group in upper["groups"] if group["id"] == "torso_tshirt_core")
    shirt_mask = polygon_mask([[tuple(point) for point in torso_polygon]])

    extension_corridor = polygon_mask(
        [
            [(190, 314), (221, 314), (220, 351), (216, 379), (196, 382), (188, 352)],
            [(293, 314), (323, 314), (326, 352), (318, 382), (299, 378), (294, 350)],
        ]
    )
    full_corridor = polygon_mask(
        [
            [(176, 164), (219, 157), (233, 185), (234, 244), (228, 304),
             (220, 373), (196, 375), (186, 333), (178, 270), (173, 212)],
            [(279, 177), (294, 157), (331, 168), (338, 219), (334, 279),
             (326, 337), (315, 378), (293, 372), (286, 310), (280, 246)],
        ]
    )
    yy, xx = np.indices((CANVAS[1], CANVAS[0]))
    rgb_max = np.max(source, axis=2).astype(np.int16)
    rgb_min = np.min(source, axis=2).astype(np.int16)
    luminance = (
        0.2126 * source[:, :, 0]
        + 0.7152 * source[:, :, 1]
        + 0.0722 * source[:, :, 2]
    )
    base_hair = np.asarray(Image.open(V6_HAIR).convert("RGBA"))[:, :, 3] > 0
    base_long_hair = base_hair & (yy >= 165)
    base_seed = base_long_hair & (yy <= 225)
    base_long_hair = connected_from_seed(base_long_hair, base_seed)
    full_dark = full_corridor & (luminance < 188) & ((rgb_max - rgb_min) < 72)
    full_expanded = Image.fromarray((full_dark * 255).astype(np.uint8), "L").filter(
        ImageFilter.MaxFilter(3)
    )
    full_candidate = (np.asarray(full_expanded) > 0) & full_corridor
    full_connected = connected_from_seed(full_candidate, base_seed)
    dark_hair_candidate = extension_corridor & (luminance < 188) & ((rgb_max - rgb_min) < 72)
    expanded = Image.fromarray((dark_hair_candidate * 255).astype(np.uint8), "L")
    expanded = expanded.filter(ImageFilter.MaxFilter(3))
    extension_candidate = (np.asarray(expanded) > 0) & extension_corridor
    candidate = base_long_hair | extension_candidate
    seed = base_long_hair & (yy >= 300)
    long_hair = base_long_hair | full_connected | connected_from_seed(candidate, seed)
    # Manual boundary from the 5 px coordinate grid: below y=285 the printed
    # word occupies the central chest. The left inner hair edge ends at x=221
    # and the right inner edge begins at x=291. This narrow ownership correction
    # removes recognizable lettering without cutting rectangular holes through
    # either real side lock.
    central_print_gap = (yy >= 285) & (yy <= 330) & (xx >= 222) & (xx <= 290)
    long_hair &= ~central_print_gap
    printed_s_left_edge = polygon_mask(
        [[
            (221, 293), (231, 294), (231, 300), (222, 302),
            (216, 306), (224, 310), (235, 310), (235, 316),
            (224, 316), (217, 320), (229, 324), (229, 329),
            (217, 328), (211, 321), (212, 314), (218, 310),
            (212, 305), (214, 298),
        ]]
    )
    long_hair &= ~(printed_s_left_edge & (luminance < 185))
    # Mask dilation can capture a few bright shirt pixels between thin tips.
    # Hair highlights in this source remain darker than this threshold.
    long_hair &= ~((yy >= 280) & (luminance > 178))

    shirt_rgb = row_shirt_fill(source, shirt_mask, long_hair)
    shirt_layer = rgba(shirt_rgb, shirt_mask)
    hair_layer = rgba(source, long_hair)
    residual = rgba(source, ~(shirt_mask | long_hair))

    default = residual.copy()
    default = Image.alpha_composite(default, shirt_layer)
    default = Image.alpha_composite(default, hair_layer)
    diff = ImageChops.difference(default.convert("RGB"), source_image)
    diff_array = np.asarray(diff)
    mae = float(diff_array.mean())
    max_error = int(diff_array.max())

    shirt_layer.save(OUT / "衣身_含长发下补底.png")
    hair_layer.save(OUT / "胸前长发_原像素.png")
    residual.save(OUT / "其余原像素.png")
    default.save(OUT / "默认合成_零误差.png")
    Image.fromarray((long_hair * 255).astype(np.uint8), "L").save(OUT / "胸前长发_归属蒙版.png")
    Image.fromarray(((shirt_mask & long_hair) * 255).astype(np.uint8), "L").save(OUT / "衣身_隐藏补底范围.png")

    moved = residual.copy()
    moved = Image.alpha_composite(moved, shirt_layer)
    shifted_hair = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    shifted_hair.paste(hair_layer, (18, -2), hair_layer)
    moved = Image.alpha_composite(moved, shifted_hair)

    original_crop = source_image.crop(CROP)
    hair_crop = crop_checker(hair_layer)
    shirt_crop = crop_checker(shirt_layer)
    moved_crop = crop_checker(moved)
    default_crop = default.crop(CROP).convert("RGB")
    diff_crop = diff.crop(CROP).convert("RGB")

    panel_size = (350, 410)
    title_h = 62
    footer_h = 144
    sheet = Image.new("RGB", (panel_size[0] * 3, (panel_size[1] + title_h) * 2 + footer_h), "white")
    draw = ImageDraw.Draw(sheet)
    entries = [
        ("① 原始胸前区域", original_crop),
        ("② 胸前长发（原像素）", hair_crop),
        ("③ 衣身与长发下补底", shirt_crop),
        ("④ 长发右移 18px 检查", moved_crop),
        ("⑤ 默认顺序重新合成", default_crop),
        ("⑥ 与原稿像素差异", diff_crop),
    ]
    for index, (title, image) in enumerate(entries):
        row, col = divmod(index, 3)
        x = col * panel_size[0]
        y = row * (panel_size[1] + title_h)
        draw.text((x + 14, y + 16), title, fill="#171717", font=font(20))
        fitted = fit_panel(image, panel_size)
        sheet.paste(fitted, (x, y + title_h))
        draw.rectangle(
            (x, y + title_h, x + panel_size[0] - 1, y + title_h + panel_size[1] - 1),
            outline="#777777",
            width=2,
        )

    footer_y = (panel_size[1] + title_h) * 2 + 15
    draw.text(
        (18, footer_y),
        "②只接受从头发上端连续下来的暗色发束，避免把胸前蝴蝶印花和文字误收为头发。",
        fill="#222222",
        font=font(19),
    )
    draw.text(
        (18, footer_y + 39),
        "③只补长发默认遮住的衣身；④用于检查衣服上是否仍残留烙死的发丝。",
        fill="#222222",
        font=font(19),
    )
    draw.text(
        (18, footer_y + 79),
        f"默认合成：MAE={mae:.3f}，最大通道差={max_error}；本轮仍未导入 PSD。",
        fill="#8D251E",
        font=font(20),
    )
    sheet.save(QA)

    REPORT.write_text(
        json.dumps(
            {
                "stage": "v9-long-hair-shirt-separation",
                "source": str(SOURCE.relative_to(ROOT)),
                "lineReference": str(LINE.relative_to(ROOT)),
                "longHairPixelCount": int(long_hair.sum()),
                "shirtHiddenFillPixelCount": int((shirt_mask & long_hair).sum()),
                "defaultCompositeMae": mae,
                "defaultCompositeMaxError": max_error,
                "visiblePixelsRepainted": False,
                "hiddenFillVisibleInDefault": False,
                "psdImport": False,
                "cubismImport": False,
                "next": "visual-review_then_neck_sleeve_wrist_hidden-fill",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
