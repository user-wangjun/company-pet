from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
THREE_VIEW = ROOT / "source" / "xiaoxing-three-view-line.png"
V8 = ROOT / "model" / "working-v8" / "body-original-pixel"
OUT = ROOT / "model" / "working-v10" / "hidden-thigh"
QA = ROOT / "qa" / "v10-hidden-thigh-continuity-review.png"
REPORT = ROOT / "audit" / "v10-hidden-thigh-continuity.json"
CANVAS = (512, 1086)
CROP = (125, 550, 385, 900)


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


def skin_fill(source: np.ndarray, visible: np.ndarray, hidden: np.ndarray) -> np.ndarray:
    yy, xx = np.indices(visible.shape)
    r = source[:, :, 0].astype(np.int16)
    g = source[:, :, 1].astype(np.int16)
    b = source[:, :, 2].astype(np.int16)
    sample = (
        visible
        & (yy >= 642)
        & (yy <= 725)
        & (r - g > 8)
        & (r - b > 12)
        & (r > 170)
    )
    result = source.copy()
    center_x = float(np.mean(xx[sample]))
    for channel in range(3):
        values = source[:, :, channel][sample]
        base = float(np.median(values))
        # Hidden thigh uses the same upper-leg skin median. Only a very small
        # horizontal variation is retained; extrapolating a polynomial upward
        # previously produced a visibly brown rectangular patch.
        variation = ((xx - center_x) / 55.0) * (1.5 if channel < 2 else 1.0)
        predicted = base + variation
        result[:, :, channel][hidden] = np.clip(predicted[hidden], base - 3, base + 3).astype(np.uint8)
    return result


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


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    QA.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    source_image = Image.open(SOURCE).convert("RGB")
    source = np.asarray(source_image)
    if source_image.size != CANVAS:
        raise ValueError("彩稿必须保持 512×1086 原始坐标")

    left_visible = np.asarray(Image.open(V8 / "10_leg_screen_left.png").convert("RGBA"))[:, :, 3] > 0
    right_visible = np.asarray(Image.open(V8 / "11_leg_screen_right.png").convert("RGBA"))[:, :, 3] > 0
    raw_skirt_layer = Image.open(V8 / "12_skirt.png").convert("RGBA")
    skirt_mask = np.asarray(raw_skirt_layer)[:, :, 3] > 0
    yy = np.indices(left_visible.shape)[0]
    luminance = (
        0.2126 * source[:, :, 0]
        + 0.7152 * source[:, :, 1]
        + 0.0722 * source[:, :, 2]
    )
    skirt_shadow = (
        (left_visible | right_visible)
        & (yy >= 635)
        & (yy <= 655)
        & (luminance < 170)
    )
    skirt_effective_mask = skirt_mask | skirt_shadow
    skirt_layer = rgba(source, skirt_effective_mask)
    left_visible &= ~skirt_mask
    right_visible &= ~skirt_mask
    left_visible &= ~skirt_shadow
    right_visible &= ~skirt_shadow

    left_hidden = polygon_mask(
        [(174, 579), (188, 573), (203, 574), (214, 581), (218, 595),
         (218, 646), (215, 656), (166, 656), (163, 646), (164, 595)]
    ) & skirt_effective_mask
    right_hidden = polygon_mask(
        [(282, 581), (294, 574), (309, 573), (322, 579), (327, 595),
         (328, 646), (325, 656), (276, 656), (273, 646), (274, 595)]
    ) & skirt_effective_mask

    left_rgb = skin_fill(source, left_visible, left_hidden)
    right_rgb = skin_fill(source, right_visible, right_hidden)
    left_complete_mask = left_visible | left_hidden
    right_complete_mask = right_visible | right_hidden
    left_layer = rgba(left_rgb, left_complete_mask)
    right_layer = rgba(right_rgb, right_complete_mask)
    # Exact visible source pixels always take priority over the hidden fill.
    left_visible_layer = rgba(source, left_visible)
    right_visible_layer = rgba(source, right_visible)
    left_layer = Image.alpha_composite(left_layer, left_visible_layer)
    right_layer = Image.alpha_composite(right_layer, right_visible_layer)

    union_visible = left_visible | right_visible | skirt_effective_mask
    residual = rgba(source, ~union_visible)
    default = residual.copy()
    default = Image.alpha_composite(default, left_layer)
    default = Image.alpha_composite(default, right_layer)
    default = Image.alpha_composite(default, skirt_layer)

    diff = ImageChops.difference(default.convert("RGB"), source_image)
    diff_array = np.asarray(diff)
    mae = float(diff_array.mean())
    max_error = int(diff_array.max())

    left_layer.save(OUT / "画面左腿_含裙内补全.png")
    right_layer.save(OUT / "画面右腿_含裙内补全.png")
    skirt_layer.save(OUT / "裙子_原像素.png")
    residual.save(OUT / "其余原像素.png")
    default.save(OUT / "默认合成_零误差.png")
    Image.fromarray(((left_hidden | right_hidden) * 255).astype(np.uint8), "L").save(
        OUT / "裙内大腿_隐藏补全范围.png"
    )

    legs_only = Image.alpha_composite(left_layer, right_layer)
    lifted_skirt = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    lifted_skirt.paste(skirt_layer, (0, -26), skirt_layer)
    stress = residual.copy()
    stress = Image.alpha_composite(stress, left_layer)
    stress = Image.alpha_composite(stress, right_layer)
    stress = Image.alpha_composite(stress, lifted_skirt)

    # A translucent cyan overlay is used only in this one panel to make the
    # hidden range readable; it is not a material texture.
    hidden_overlay = source_image.convert("RGBA")
    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    overlay_pixels = np.zeros((CANVAS[1], CANVAS[0], 4), dtype=np.uint8)
    overlay_pixels[:, :, :3] = (30, 190, 210)
    overlay_pixels[:, :, 3] = np.where(left_hidden | right_hidden, 105, 0).astype(np.uint8)
    overlay = Image.fromarray(overlay_pixels, "RGBA")
    hidden_overlay = Image.alpha_composite(hidden_overlay, overlay)

    original_crop = source_image.crop(CROP)
    legs_crop = crop_checker(legs_only)
    overlay_crop = hidden_overlay.crop(CROP).convert("RGB")
    stress_crop = crop_checker(stress)
    default_crop = default.crop(CROP).convert("RGB")
    diff_crop = diff.crop(CROP).convert("RGB")

    panel_size = (350, 470)
    title_h = 62
    footer_h = 150
    sheet = Image.new("RGB", (panel_size[0] * 3, (panel_size[1] + title_h) * 2 + footer_h), "white")
    draw = ImageDraw.Draw(sheet)
    entries = [
        ("① 原始裙腿区域", original_crop),
        ("② 双腿完整层（含裙内）", legs_crop),
        ("③ 青色仅标示隐藏范围", overlay_crop),
        ("④ 裙子上移 26px 压力检查", stress_crop),
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

    footer_y = (panel_size[1] + title_h) * 2 + 14
    draw.text(
        (18, footer_y),
        "隐藏大腿沿可见腿宽度连续向上，颜色由同一条腿的可见上段拟合；没有圆形补丁或缩小色块。",
        fill="#222222",
        font=font(19),
    )
    draw.text(
        (18, footer_y + 40),
        "④故意把裙子上移 26px；若补全正确，露出的腿应保持连续，不出现白缝或骤然变窄。",
        fill="#222222",
        font=font(19),
    )
    draw.text(
        (18, footer_y + 82),
        f"默认合成：MAE={mae:.3f}，最大通道差={max_error}；隐藏补全在默认姿势完全不可见。",
        fill="#8D251E",
        font=font(20),
    )
    sheet.save(QA)

    REPORT.write_text(
        json.dumps(
            {
                "stage": "v10-hidden-thigh-continuity",
                "frontSource": str(SOURCE.relative_to(ROOT)),
                "sideVolumeEvidence": str(THREE_VIEW.relative_to(ROOT)),
                "leftHiddenPixelCount": int(left_hidden.sum()),
                "rightHiddenPixelCount": int(right_hidden.sum()),
                "stressSkirtOffsetY": -26,
                "defaultCompositeMae": mae,
                "defaultCompositeMaxError": max_error,
                "visiblePixelsRepainted": False,
                "hiddenFillVisibleInDefault": False,
                "psdImport": False,
                "cubismImport": False,
                "next": "visual-review_then_sleeve_wrist_sock_hidden-overlaps",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
