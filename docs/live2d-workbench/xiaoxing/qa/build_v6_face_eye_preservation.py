from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
V5 = ROOT / "model" / "working-v5" / "head-sample"
OUT = ROOT / "model" / "working-v6" / "face-eye-sample"
QA = ROOT / "qa" / "v6-face-eye-preservation-review.png"
REPORT = ROOT / "audit" / "v6-face-eye-preservation.json"

CANVAS = (512, 1086)
HEAD_BOX = (158, 12, 350, 372)
FACE = [
    (213, 96), (228, 82), (240, 76), (257, 73), (278, 79), (295, 95),
    (302, 118), (304, 146), (299, 169), (288, 188), (273, 200),
    (257, 205), (241, 201), (227, 193), (216, 179), (210, 161), (207, 138),
]
EYES = {
    "画面左眼": [
        (204, 132), (208, 127), (214, 124), (222, 122), (231, 124),
        (238, 128), (242, 132), (238, 139), (230, 144), (220, 145),
        (211, 143), (206, 138),
    ],
    "画面右眼": [
        (260, 132), (265, 127), (272, 124), (281, 122), (290, 124),
        (296, 128), (299, 132), (296, 138), (289, 143), (281, 145),
        (272, 143), (264, 138),
    ],
}
BROWS = {
    "画面左眉": [
        (209, 121), (217, 118), (228, 118), (238, 121),
        (237, 124), (228, 121), (217, 121), (211, 125),
    ],
    "画面右眉": [
        (266, 121), (275, 118), (287, 118), (297, 121),
        (296, 124), (287, 121), (276, 121), (269, 125),
    ],
}


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def mask_from_polygon(points: list[tuple[int, int]]) -> np.ndarray:
    image = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(image).polygon(points, fill=255)
    return np.asarray(image) > 0


def rgba_layer(rgb: np.ndarray, mask: np.ndarray) -> Image.Image:
    rgba = np.zeros((CANVAS[1], CANVAS[0], 4), dtype=np.uint8)
    rgba[:, :, :3] = rgb
    rgba[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    w, h = size
    yy, xx = np.indices((h, w))
    pattern = (xx // cell + yy // cell) % 2
    colors = np.where(pattern[:, :, None] == 0, 238, 207).astype(np.uint8)
    return Image.fromarray(np.repeat(colors, 3, axis=2), "RGB")


def on_checker(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    crop = image.crop(box).convert("RGBA")
    background = checker(crop.size)
    background.paste(crop, (0, 0), crop)
    return background


def panel(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    output = Image.new("RGB", size, "white")
    copy = image.copy()
    copy.thumbnail((size[0] - 18, size[1] - 18), Image.Resampling.NEAREST)
    output.paste(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return output


def fit_skin_model(source: np.ndarray, face: np.ndarray, excluded: np.ndarray) -> np.ndarray:
    yy, xx = np.indices(face.shape)
    r = source[:, :, 0].astype(np.int16)
    g = source[:, :, 1].astype(np.int16)
    b = source[:, :, 2].astype(np.int16)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    skin = (
        face
        & ~excluded
        & (yy >= 135)
        & (yy <= 199)
        & (r - g > 8)
        & (r - b > 12)
        & (luminance > 155)
    )
    sx = (xx[skin] - 255.0) / 60.0
    sy = (yy[skin] - 160.0) / 60.0
    design = np.stack([np.ones_like(sx), sx, sy], axis=1)
    full_x = (xx - 255.0) / 60.0
    full_y = (yy - 160.0) / 60.0
    full_design = np.stack([np.ones_like(full_x), full_x, full_y], axis=2)
    result = source.astype(np.float64).copy()
    for channel in range(3):
        coeff, *_ = np.linalg.lstsq(design, source[:, :, channel][skin], rcond=None)
        predicted = np.sum(full_design * coeff[None, None, :], axis=2)
        low, high = np.percentile(source[:, :, channel][skin], [8, 92])
        result[:, :, channel] = np.clip(predicted, low, high)
    return np.clip(result, 0, 255).astype(np.uint8)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    QA.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    source_image = Image.open(SOURCE).convert("RGB")
    line_image = Image.open(LINE).convert("RGB")
    if source_image.size != CANVAS or line_image.size != CANVAS:
        raise ValueError("线稿和彩稿必须保持 512×1086 的锁定母版坐标")
    source = np.asarray(source_image)

    front_hair_alpha = np.asarray(Image.open(V5 / "前发_原像素.png").convert("RGBA"))[:, :, 3] > 0
    face = mask_from_polygon(FACE)
    eye_masks = {name: mask_from_polygon(points) for name, points in EYES.items()}
    both_eyes = np.logical_or.reduce(list(eye_masks.values()))
    brow_regions = np.logical_or.reduce([mask_from_polygon(points) for points in BROWS.values()])

    # Only hidden face pixels receive a reconstruction. All pixels visible in the
    # default pose remain unchanged source pixels.
    yy = np.indices(face.shape)[0]
    rgb_max = np.max(source, axis=2)
    rgb_min = np.min(source, axis=2)
    luminance = (
        0.2126 * source[:, :, 0]
        + 0.7152 * source[:, :, 1]
        + 0.0722 * source[:, :, 2]
    )
    remaining_bang_pixels = (
        face
        & (yy < 151)
        & (luminance < 178)
        & ((rgb_max.astype(np.int16) - rgb_min.astype(np.int16)) < 75)
    )
    brow_pixels = brow_regions & (luminance < 150) & ~front_hair_alpha
    expanded_upper_bangs = np.asarray(
        Image.fromarray((remaining_bang_pixels * 255).astype(np.uint8), "L").filter(
            ImageFilter.MaxFilter(5)
        )
    ) > 0
    expanded_upper_bangs &= face & (yy < 119)
    refined_front_hair = (
        front_hair_alpha
        | ((remaining_bang_pixels | expanded_upper_bangs) & ~brow_pixels & ~both_eyes)
    )
    hidden_face = face & refined_front_hair
    feature_exclusion = both_eyes.copy()
    feature_exclusion[158:184, 232:281] = True  # nose and mouth region
    fitted_skin = fit_skin_model(source, face, feature_exclusion | front_hair_alpha)
    face_rgb = source.copy()
    face_rgb[hidden_face] = fitted_skin[hidden_face]

    face_base_mask = face & ~both_eyes & ~brow_pixels
    face_layer = rgba_layer(face_rgb, face_base_mask)
    left_eye_layer = rgba_layer(source, eye_masks["画面左眼"])
    right_eye_layer = rgba_layer(source, eye_masks["画面右眼"])
    eyes_layer = Image.alpha_composite(left_eye_layer, right_eye_layer)
    brows_layer = rgba_layer(source, brow_pixels)
    front_hair_layer = rgba_layer(source, refined_front_hair)

    claimed = face | refined_front_hair
    residual_layer = rgba_layer(source, ~claimed)

    default_composite = residual_layer.copy()
    default_composite = Image.alpha_composite(default_composite, face_layer)
    default_composite = Image.alpha_composite(default_composite, eyes_layer)
    default_composite = Image.alpha_composite(default_composite, brows_layer)
    default_composite = Image.alpha_composite(default_composite, front_hair_layer)

    source_rgba = source_image.convert("RGBA")
    diff = ImageChops.difference(default_composite.convert("RGB"), source_image)
    diff_array = np.asarray(diff)
    mae = float(diff_array.mean())
    max_error = int(diff_array.max())

    face_with_eyes = Image.alpha_composite(Image.alpha_composite(face_layer, eyes_layer), brows_layer)

    face_layer.save(OUT / "脸底_含刘海下补全.png")
    left_eye_layer.save(OUT / "左眼_原像素原坐标.png")
    right_eye_layer.save(OUT / "右眼_原像素原坐标.png")
    brows_layer.save(OUT / "双眉_原像素原坐标.png")
    front_hair_layer.save(OUT / "前发_修订原像素.png")
    residual_layer.save(OUT / "头部其余层.png")
    default_composite.save(OUT / "默认合成_零误差.png")
    Image.fromarray((hidden_face * 255).astype(np.uint8), "L").save(OUT / "脸底_隐藏补全范围.png")

    original_crop = source_image.crop(HEAD_BOX)
    face_crop = on_checker(face_with_eyes, HEAD_BOX)
    base_crop = on_checker(face_layer, HEAD_BOX)
    eyes_crop = on_checker(eyes_layer, HEAD_BOX)
    default_crop = default_composite.crop(HEAD_BOX).convert("RGB")
    diff_crop = diff.crop(HEAD_BOX).convert("RGB")

    panel_size = (360, 450)
    title_h = 64
    note_h = 146
    sheet = Image.new("RGB", (panel_size[0] * 3, (panel_size[1] + title_h) * 2 + note_h), "white")
    draw = ImageDraw.Draw(sheet)
    entries = [
        ("① 原始彩稿头部", original_crop),
        ("② 去掉前发后的完整脸与原眼", face_crop),
        ("③ 脸底（眼睛留空）", base_crop),
        ("④ 双眼原像素、原坐标", eyes_crop),
        ("⑤ 默认顺序重新合成", default_crop),
        ("⑥ 与原稿的像素差异", diff_crop),
    ]
    for index, (title, image) in enumerate(entries):
        row, column = divmod(index, 3)
        x = column * panel_size[0]
        y = row * (panel_size[1] + title_h)
        draw.text((x + 16, y + 17), title, fill="#171717", font=font(22))
        fitted = panel(image, panel_size)
        sheet.paste(fitted, (x, y + title_h))
        draw.rectangle(
            (x, y + title_h, x + panel_size[0] - 1, y + title_h + panel_size[1] - 1),
            outline="#777777",
            width=2,
        )

    note_y = (panel_size[1] + title_h) * 2 + 18
    draw.text(
        (20, note_y),
        "本轮没有描新眼型：④中的两只眼睛直接复制原彩稿对应像素，并保持原始坐标。",
        fill="#202020",
        font=font(21),
    )
    draw.text(
        (20, note_y + 40),
        "②额头只补刘海默认遮住的区域；这些补画像素在⑤中完全被前发覆盖，不改变默认长相。",
        fill="#202020",
        font=font(21),
    )
    draw.text(
        (20, note_y + 82),
        f"默认合成验证：MAE={mae:.3f}，最大通道差={max_error}。⑥为黑色时表示逐像素一致。",
        fill="#8D251E",
        font=font(21),
    )
    sheet.save(QA)

    REPORT.write_text(
        json.dumps(
            {
                "stage": "v6-face-base-and-original-eye-preservation",
                "source": str(SOURCE.relative_to(ROOT)),
                "lineGeometryReference": str(LINE.relative_to(ROOT)),
                "frontHairEvidence": "model/working-v5/head-sample/前发_原像素.png",
                "defaultCompositeMae": mae,
                "defaultCompositeMaxError": max_error,
                "visibleEyePixelsRepainted": False,
                "hiddenFaceFillOnlyUnderFrontHair": True,
                "psdImport": False,
                "cubismImport": False,
                "next": "semantic-eye-parts-with-default-composite-preserved",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
