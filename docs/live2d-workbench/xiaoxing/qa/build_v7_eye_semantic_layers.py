from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
V6 = ROOT / "model" / "working-v6" / "face-eye-sample"
OUT = ROOT / "model" / "working-v7" / "eye-semantic"
QA = ROOT / "qa" / "v7-eye-semantic-original-pixel-review.png"
REPORT = ROOT / "audit" / "v7-eye-semantic-validation.json"
CANVAS = (512, 1086)

EYES = {
    "画面左眼": {
        "box": (196, 110, 248, 154),
        "aperture": [
            (204, 132), (208, 127), (214, 124), (222, 122), (231, 124),
            (238, 128), (242, 132), (238, 139), (230, 144), (220, 145),
            (211, 143), (206, 138),
        ],
        "iris": (213, 123, 234, 143),
        "pupil": (218, 126, 230, 141),
        "highlight": (221, 122, 228, 130),
        "upper_line_y": 129,
        "lower_line_y": 139,
    },
    "画面右眼": {
        "box": (255, 110, 307, 154),
        "aperture": [
            (260, 132), (265, 127), (272, 124), (281, 122), (290, 124),
            (296, 128), (299, 132), (296, 138), (289, 143), (281, 145),
            (272, 143), (264, 138),
        ],
        "iris": (269, 123, 290, 143),
        "pupil": (274, 126, 286, 141),
        "highlight": (277, 122, 284, 130),
        "upper_line_y": 129,
        "lower_line_y": 139,
    },
}


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def polygon_mask(points: list[tuple[int, int]]) -> np.ndarray:
    image = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(image).polygon(points, fill=255)
    return np.asarray(image) > 0


def ellipse_mask(box: tuple[int, int, int, int]) -> np.ndarray:
    image = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(image).ellipse(box, fill=255)
    return np.asarray(image) > 0


def layer(source: np.ndarray, mask: np.ndarray) -> Image.Image:
    rgba = np.zeros((CANVAS[1], CANVAS[0], 4), dtype=np.uint8)
    rgba[:, :, :3] = source
    rgba[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def checker(size: tuple[int, int], cell: int = 8) -> Image.Image:
    w, h = size
    yy, xx = np.indices((h, w))
    board = (xx // cell + yy // cell) % 2
    values = np.where(board[:, :, None] == 0, 239, 208).astype(np.uint8)
    return Image.fromarray(np.repeat(values, 3, axis=2), "RGB")


def crop_on_checker(image: Image.Image, box: tuple[int, int, int, int], scale: int = 7) -> Image.Image:
    crop = image.crop(box).convert("RGBA")
    background = checker(crop.size)
    background.paste(crop, (0, 0), crop)
    return background.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    QA.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    source_image = Image.open(SOURCE).convert("RGB")
    source = np.asarray(source_image)
    yy = np.indices((CANVAS[1], CANVAS[0]))[0]
    luminance = (
        0.2126 * source[:, :, 0]
        + 0.7152 * source[:, :, 1]
        + 0.0722 * source[:, :, 2]
    )

    semantic_by_eye: dict[str, dict[str, Image.Image]] = {}
    combined_semantic = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    pixel_counts: dict[str, dict[str, int]] = {}

    for eye_name, spec in EYES.items():
        aperture = polygon_mask(spec["aperture"])
        iris_geometry = ellipse_mask(spec["iris"]) & aperture
        pupil_geometry = ellipse_mask(spec["pupil"]) & iris_geometry
        highlight_geometry = ellipse_mask(spec["highlight"]) & iris_geometry

        highlight = highlight_geometry & (luminance > 150)
        upper_line = aperture & (yy <= spec["upper_line_y"]) & (luminance < 155) & ~highlight
        lower_line = aperture & (yy >= spec["lower_line_y"]) & (luminance < 170) & ~highlight
        pupil = pupil_geometry & (yy >= 128) & (luminance < 105) & ~highlight & ~upper_line & ~lower_line
        iris = iris_geometry & ~pupil & ~highlight & ~upper_line & ~lower_line
        sclera_surface = aperture & ~iris & ~pupil & ~highlight & ~upper_line & ~lower_line

        masks = {
            "眼白与眼睑表面": sclera_surface,
            "虹膜": iris,
            "瞳孔": pupil,
            "高光": highlight,
            "上眼线": upper_line,
            "下眼线": lower_line,
        }
        layers = {name: layer(source, mask) for name, mask in masks.items()}
        semantic_by_eye[eye_name] = layers
        pixel_counts[eye_name] = {name: int(mask.sum()) for name, mask in masks.items()}

        prefix = "left" if eye_name == "画面左眼" else "right"
        for order, (part_name, part_layer) in enumerate(layers.items(), start=1):
            part_layer.save(OUT / f"{prefix}_{order:02d}_{part_name}.png")
            combined_semantic = Image.alpha_composite(combined_semantic, part_layer)

    residual = Image.open(V6 / "头部其余层.png").convert("RGBA")
    face = Image.open(V6 / "脸底_含刘海下补全.png").convert("RGBA")
    brows = Image.open(V6 / "双眉_原像素原坐标.png").convert("RGBA")
    front_hair = Image.open(V6 / "前发_修订原像素.png").convert("RGBA")
    rebuilt = residual.copy()
    for part in (face, combined_semantic, brows, front_hair):
        rebuilt = Image.alpha_composite(rebuilt, part)
    rebuilt.save(OUT / "默认合成_语义眼层回组.png")

    diff = ImageChops.difference(rebuilt.convert("RGB"), source_image)
    diff_array = np.asarray(diff)
    mae = float(diff_array.mean())
    max_error = int(diff_array.max())

    headers = ["原眼", "眼白/眼睑", "虹膜", "瞳孔+高光", "上下眼线", "语义层回组"]
    panel_w, panel_h = 364, 308
    title_h, header_h, row_gap = 66, 54, 76
    sheet_w = panel_w * len(headers)
    sheet_h = title_h + header_h + (panel_h + row_gap) * 2 + 110
    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 16), "小星双眼：原彩稿像素语义拆层（不重新描边）", fill="#171717", font=font(27))
    for col, header in enumerate(headers):
        draw.text((col * panel_w + 14, title_h + 12), header, fill="#222222", font=font(21))

    for row, (eye_name, spec) in enumerate(EYES.items()):
        y = title_h + header_h + row * (panel_h + row_gap)
        whole_eye = layer(source, polygon_mask(spec["aperture"]))
        layers = semantic_by_eye[eye_name]
        pupil_highlight = Image.alpha_composite(layers["瞳孔"], layers["高光"])
        eye_lines = Image.alpha_composite(layers["上眼线"], layers["下眼线"])
        recombined = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        for part in layers.values():
            recombined = Image.alpha_composite(recombined, part)
        images = [
            whole_eye,
            layers["眼白与眼睑表面"],
            layers["虹膜"],
            pupil_highlight,
            eye_lines,
            recombined,
        ]
        for col, image in enumerate(images):
            crop = crop_on_checker(image, spec["box"])
            crop.thumbnail((panel_w - 18, panel_h - 18), Image.Resampling.NEAREST)
            px = col * panel_w + (panel_w - crop.width) // 2
            py = y + (panel_h - crop.height) // 2
            sheet.paste(crop, (px, py))
            draw.rectangle(
                (col * panel_w, y, (col + 1) * panel_w - 1, y + panel_h - 1),
                outline="#777777",
                width=2,
            )
        draw.text(
            (18, y + panel_h + 12),
            f"{eye_name}：所有可见像素只改变所属图层，不改变颜色或坐标。",
            fill="#303030",
            font=font(20),
        )

    footer_y = sheet_h - 90
    draw.text(
        (20, footer_y),
        f"整脸默认回组：MAE={mae:.3f}，最大通道差={max_error}；只有保持 0 才允许进入 PSD。",
        fill="#8D251E",
        font=font(22),
    )
    draw.text(
        (20, footer_y + 38),
        "当前仍是材料审查层；眨眼闭合补画、眼球移动边界与遮罩将在默认回组通过后单独处理。",
        fill="#333333",
        font=font(20),
    )
    sheet.save(QA)

    REPORT.write_text(
        json.dumps(
            {
                "stage": "v7-original-pixel-eye-semantic-separation",
                "defaultCompositeMae": mae,
                "defaultCompositeMaxError": max_error,
                "visiblePixelsRepainted": False,
                "coordinateTransformApplied": False,
                "parts": pixel_counts,
                "psdImport": False,
                "cubismImport": False,
                "next": "visual-review-then-closed-eye-hidden-material",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
