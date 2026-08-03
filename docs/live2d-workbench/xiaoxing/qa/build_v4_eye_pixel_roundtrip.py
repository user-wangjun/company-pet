from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


ROOT = Path(__file__).resolve().parents[1]
COLOR_PATH = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
OUT_DIR = ROOT / "model" / "working-v4" / "eyes-roundtrip"
QA_PATH = ROOT / "qa" / "v4-eye-pixel-roundtrip-review.png"
CANVAS = (512, 1086)

EYES = {
    "screen_left": {
        "box": (196, 110, 248, 154),
        "aperture": [
            (204, 132), (208, 127), (214, 124), (222, 122), (231, 124),
            (238, 128), (242, 132), (238, 139), (230, 144), (220, 145),
            (211, 143), (206, 138),
        ],
        "iris": (210, 120, 232, 147),
    },
    "screen_right": {
        "box": (255, 110, 307, 154),
        "aperture": [
            (260, 132), (265, 127), (272, 124), (281, 122), (290, 124),
            (296, 128), (299, 132), (296, 138), (289, 143), (281, 145),
            (272, 143), (264, 138),
        ],
        "iris": (270, 120, 292, 147),
    },
}


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (Path(r"C:\Windows\Fonts\msyh.ttc"), Path(r"C:\Windows\Fonts\simhei.ttf")):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def polygon_mask(points: list[tuple[int, int]]) -> Image.Image:
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return mask


def ellipse_mask(box: tuple[int, int, int, int]) -> Image.Image:
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).ellipse(box, fill=255)
    return mask


def source_layer(source: Image.Image, mask: Image.Image) -> Image.Image:
    layer = source.convert("RGBA")
    layer.putalpha(mask)
    return layer


def crop8(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    return image.crop(box).convert("RGB").resize(
        ((box[2] - box[0]) * 8, (box[3] - box[1]) * 8), Image.Resampling.NEAREST
    )


def build() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUT_DIR.glob("*.png"):
        stale.unlink()

    source = Image.open(COLOR_PATH).convert("RGB")
    if source.size != CANVAS:
        raise ValueError(f"彩稿必须保持 {CANVAS} 原始坐标")

    review_rows = []
    for side, spec in EYES.items():
        aperture = polygon_mask(spec["aperture"])
        iris = ImageChops.multiply(ellipse_mask(spec["iris"]), aperture)
        surface = ImageChops.subtract(aperture, iris)

        whole_layer = source_layer(source, aperture)
        surface_layer = source_layer(source, surface)
        iris_layer = source_layer(source, iris)
        whole_layer.save(OUT_DIR / f"10_default_visible_eye_{side}.png")
        surface_layer.save(OUT_DIR / f"11_default_surface_{side}.png")
        iris_layer.save(OUT_DIR / f"12_default_iris_region_{side}.png")

        skin = Image.new("RGBA", CANVAS, (247, 224, 215, 255))
        isolated = Image.alpha_composite(skin, whole_layer)
        rebuilt = Image.alpha_composite(Image.alpha_composite(skin, surface_layer), iris_layer)

        # 分层重组与整眼提取使用同一批原像素，差异应严格为 0。
        diff = ImageChops.difference(isolated.convert("RGB"), rebuilt.convert("RGB"))
        stat = ImageStat.Stat(diff, aperture)
        mae = sum(stat.mean) / 3.0
        extrema = diff.getextrema()
        max_diff = max(channel[1] for channel in extrema)
        review_rows.append((side, spec["box"], isolated, rebuilt, diff, mae, max_diff))

    panel_w, panel_h = 416, 352
    gap, title_h, row_gap = 28, 94, 94
    sheet_w = gap + 4 * (panel_w + gap)
    sheet_h = title_h + 2 * (panel_h + row_gap + gap) + 72
    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((gap, 18), "小星双眼 V4：原彩稿像素回组（不重新设计眼型）", fill=(24, 24, 24), font=font(32))
    headers = ["① 原始彩稿", "② 原像素整眼提取", "③ 原像素拆层重组", "④ ②与③像素差异"]
    for column, header in enumerate(headers):
        draw.text((gap + column * (panel_w + gap), title_h), header, fill=(35, 35, 35), font=font(23))

    for row, (side, box, isolated, rebuilt, diff, mae, max_diff) in enumerate(review_rows):
        y = title_h + 50 + row * (panel_h + row_gap + gap)
        panels = [crop8(source, box), crop8(isolated, box), crop8(rebuilt, box), crop8(diff, box)]
        for column, panel in enumerate(panels):
            x = gap + column * (panel_w + gap)
            sheet.paste(panel, (x, y))
            draw.rectangle((x, y, x + panel_w - 1, y + panel_h - 1), outline=(166, 166, 166), width=2)
        label = "画面左眼" if side == "screen_left" else "画面右眼"
        draw.text(
            (gap, y + panel_h + 12),
            f"{label}：拆层回组 MAE={mae:.3f}，最大通道差={max_diff}；黑色差异图表示完全一致。",
            fill=(52, 52, 52),
            font=font(21),
        )

    draw.text(
        (gap, sheet.height - 48),
        "当前只验证‘不改长相’；虹膜、瞳孔、高光、眼线的进一步拆分必须继续保持默认回组一致。",
        fill=(112, 30, 30),
        font=font(22),
    )
    sheet.save(QA_PATH)


if __name__ == "__main__":
    build()
