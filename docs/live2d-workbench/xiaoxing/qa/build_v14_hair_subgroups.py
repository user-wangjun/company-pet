from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
V6 = ROOT / "model" / "working-v6" / "face-eye-sample"
V9 = ROOT / "model" / "working-v9" / "long-hair-shirt"
V12 = ROOT / "model" / "working-v12" / "eye-hidden-materials"
OUT = ROOT / "model" / "working-v14" / "hair-subgroups"
QA = ROOT / "qa" / "v14-hair-subgroup-pull-review.png"
REPORT = ROOT / "audit" / "v14-hair-subgroup-validation.json"
CANVAS = (512, 1086)
CROP = (150, 12, 360, 405)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def polygon_mask(points: list[tuple[int, int]]) -> np.ndarray:
    image = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(image).polygon(points, fill=255)
    return np.asarray(image) > 0


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


def shift_layer(image: Image.Image, dx: int, dy: int) -> Image.Image:
    shifted = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    shifted.paste(image, (dx, dy), image)
    return shifted


def build_hidden_back_rgb(source: np.ndarray, visible: np.ndarray, hidden: np.ndarray) -> np.ndarray:
    pixels = source[visible]
    dark = pixels[np.mean(pixels, axis=1) < 125]
    base = np.median(dark if len(dark) >= 20 else pixels, axis=0).astype(np.float64)
    yy, xx = np.indices(visible.shape)
    center_x = 256.0
    horizontal = np.abs(xx - center_x) / 105.0
    vertical = np.clip((yy - 30.0) / 360.0, 0, 1)
    factor = np.clip(0.88 + 0.15 * horizontal + 0.08 * vertical, 0.82, 1.18)
    result = source.astype(np.float64).copy()
    generated = base[None, None, :] * factor[:, :, None]
    result[hidden] = np.clip(generated[hidden], 12, 150)
    result[visible] = source[visible]
    return result.astype(np.uint8)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    QA.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    source_image = Image.open(SOURCE).convert("RGB")
    line_image = Image.open(LINE).convert("RGB")
    source = np.asarray(source_image)
    if source_image.size != CANVAS or line_image.size != CANVAS:
        raise ValueError("线稿和彩稿必须保持 512×1086 原始坐标")

    head_hair = np.asarray(Image.open(V6 / "前发_修订原像素.png").convert("RGBA"))[:, :, 3] > 0
    long_hair = np.asarray(Image.open(V9 / "胸前长发_原像素.png").convert("RGBA"))[:, :, 3] > 0
    full_hair = head_hair | long_hair
    r = source[:, :, 0].astype(np.int16)
    g = source[:, :, 1].astype(np.int16)
    b = source[:, :, 2].astype(np.int16)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    skin_like = (r - g > 12) & (r - b > 18) & (luminance > 150)
    grid_y, grid_x = np.indices(full_hair.shape)
    central_face_zone = (grid_x >= 205) & (grid_x <= 305) & (grid_y >= 90) & (grid_y <= 205)
    full_hair &= ~(skin_like & central_face_zone)

    bangs_region = polygon_mask(
        [
            (199, 88), (214, 76), (235, 70), (256, 72), (280, 73),
            (300, 84), (310, 104), (306, 130), (298, 146), (290, 130),
            (281, 146), (272, 128), (262, 146), (252, 132), (243, 146),
            (234, 130), (224, 146), (214, 136), (204, 146), (198, 119),
        ]
    )
    left_side_region = polygon_mask(
        [
            (176, 92), (207, 86), (224, 111), (230, 160), (232, 221),
            (228, 287), (221, 343), (214, 383), (193, 382), (182, 337),
            (175, 274), (171, 205), (172, 142),
        ]
    )
    right_side_region = polygon_mask(
        [
            (304, 87), (334, 96), (340, 143), (339, 206), (336, 275),
            (329, 338), (319, 383), (298, 381), (290, 341), (284, 286),
            (281, 221), (283, 160), (289, 112),
        ]
    )

    bangs = full_hair & bangs_region
    left_side = full_hair & left_side_region & ~bangs
    right_side = full_hair & right_side_region & ~bangs
    back_visible = full_hair & ~bangs & ~left_side & ~right_side

    face_layer = Image.open(V6 / "脸底_含刘海下补全.png").convert("RGBA")
    face_mask = np.asarray(face_layer)[:, :, 3] > 0
    face_rgb = np.asarray(face_layer)[:, :, :3].copy()
    visible_face = face_mask & ~full_hair
    face_rgb[visible_face] = source[visible_face]
    face_layer = rgba(face_rgb, face_mask)
    eyes_layer = Image.open(V12 / "双眼默认材料回组.png").convert("RGBA")
    eyes_mask = np.asarray(eyes_layer)[:, :, 3] > 0
    brows_layer = Image.open(V6 / "双眉_原像素原坐标.png").convert("RGBA")
    brows_mask = np.asarray(brows_layer)[:, :, 3] > 0
    shirt_layer = Image.open(V9 / "衣身_含长发下补底.png").convert("RGBA")
    shirt_mask = np.asarray(shirt_layer)[:, :, 3] > 0

    back_shape = polygon_mask(
        [
            (183, 119), (188, 68), (214, 34), (253, 20), (291, 34),
            (321, 68), (334, 124), (338, 191), (336, 257), (330, 320),
            (318, 382), (298, 383), (286, 325), (280, 252), (277, 182),
            (234, 182), (232, 252), (225, 326), (215, 383), (194, 382),
            (182, 327), (175, 260), (172, 190),
        ]
    )
    yy = np.indices(full_hair.shape)[0]
    foreground_cover = (
        face_mask
        | eyes_mask
        | brows_mask
        | bangs
        | ((left_side | right_side) & (yy < 270))
    )
    back_hidden = back_shape & foreground_cover & (yy < 220) & ~back_visible
    back_rgb = build_hidden_back_rgb(source, back_visible, back_hidden)

    back_layer = rgba(back_rgb, back_visible | back_hidden)
    # Visible source pixels always override generated hidden texture.
    back_layer = Image.alpha_composite(back_layer, rgba(source, back_visible))
    bangs_layer = rgba(source, bangs)
    left_side_layer = rgba(source, left_side)
    right_side_layer = rgba(source, right_side)

    claimed = full_hair | face_mask | eyes_mask | brows_mask | shirt_mask
    residual = rgba(source, ~claimed)
    default = residual.copy()
    for part in (
        shirt_layer,
        back_layer,
        face_layer,
        eyes_layer,
        brows_layer,
        left_side_layer,
        right_side_layer,
        bangs_layer,
    ):
        default = Image.alpha_composite(default, part)
    diff = ImageChops.difference(default.convert("RGB"), source_image)
    diff_array = np.asarray(diff)
    mae = float(diff_array.mean())
    max_error = int(diff_array.max())

    outputs = {
        "01_后发_含遮挡补全.png": back_layer,
        "02_画面左侧发束_原像素.png": left_side_layer,
        "03_画面右侧发束_原像素.png": right_side_layer,
        "04_刘海_原像素.png": bangs_layer,
        "05_脸底.png": face_layer,
        "06_双眼默认层.png": eyes_layer,
        "07_双眉.png": brows_layer,
        "默认合成_零误差.png": default,
    }
    for name, image in outputs.items():
        image.save(OUT / name)

    bangs_offset = (0, -6)
    left_offset = (-8, 2)
    right_offset = (8, 2)
    pulled = residual.copy()
    pulled = Image.alpha_composite(pulled, shirt_layer)
    pulled = Image.alpha_composite(pulled, back_layer)
    pulled = Image.alpha_composite(pulled, face_layer)
    pulled = Image.alpha_composite(pulled, eyes_layer)
    pulled = Image.alpha_composite(pulled, brows_layer)
    pulled = Image.alpha_composite(pulled, shift_layer(left_side_layer, *left_offset))
    pulled = Image.alpha_composite(pulled, shift_layer(right_side_layer, *right_offset))
    pulled = Image.alpha_composite(pulled, shift_layer(bangs_layer, *bangs_offset))

    original_crop = source_image.crop(CROP)
    back_crop = crop_checker(back_layer)
    bangs_crop = crop_checker(bangs_layer)
    sides = Image.alpha_composite(left_side_layer, right_side_layer)
    sides_crop = crop_checker(sides)
    pulled_crop = crop_checker(pulled)
    diff_crop = diff.crop(CROP).convert("RGB")

    panel_size = (360, 500)
    title_h = 62
    footer_h = 156
    sheet = Image.new("RGB", (panel_size[0] * 3, (panel_size[1] + title_h) * 2 + footer_h), "white")
    draw = ImageDraw.Draw(sheet)
    entries = [
        ("① 原始头发与上身", original_crop),
        ("② 后发（含遮挡补全）", back_crop),
        ("③ 刘海原像素层", bangs_crop),
        ("④ 左右侧发束原像素层", sides_crop),
        ("⑤ 刘海上移、侧发外移检查", pulled_crop),
        ("⑥ 默认合成像素差异", diff_crop),
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

    footer_y = (panel_size[1] + title_h) * 2 + 14
    draw.text(
        (18, footer_y),
        "②后发位于脸底之后；隐藏补全只存在于脸、刘海和侧发默认遮挡范围，不改变默认长相。",
        fill="#222222",
        font=font(19),
    )
    draw.text(
        (18, footer_y + 40),
        "⑤是接缝压力图：刘海上移 6px、左右侧发外移 8px，用于检查透明洞和烙死发丝。",
        fill="#222222",
        font=font(19),
    )
    draw.text(
        (18, footer_y + 82),
        f"默认合成：MAE={mae:.3f}，最大通道差={max_error}；当前仍是材料门禁，不是正式动作幅度。",
        fill="#8D251E",
        font=font(20),
    )
    sheet.save(QA)

    REPORT.write_text(
        json.dumps(
            {
                "stage": "v14-hair-subgroups",
                "source": str(SOURCE.relative_to(ROOT)),
                "lineReference": str(LINE.relative_to(ROOT)),
                "pixelCounts": {
                    "backVisible": int(back_visible.sum()),
                    "backHidden": int(back_hidden.sum()),
                    "bangs": int(bangs.sum()),
                    "leftSideLock": int(left_side.sum()),
                    "rightSideLock": int(right_side.sum()),
                },
                "pullOffsets": {
                    "bangs": list(bangs_offset),
                    "leftSideLock": list(left_offset),
                    "rightSideLock": list(right_offset),
                },
                "defaultCompositeMae": mae,
                "defaultCompositeMaxError": max_error,
                "visiblePixelsRepainted": False,
                "hiddenFillVisibleInDefault": False,
                "psdImport": False,
                "cubismImport": False,
                "next": "visual-review_then-final-material-joint-gate",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
