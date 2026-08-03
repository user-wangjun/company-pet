from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
V6 = ROOT / "model" / "working-v6" / "face-eye-sample"
OUT = ROOT / "model" / "working-v12" / "eye-hidden-materials"
QA = ROOT / "qa" / "v12-eye-hidden-materials-review.png"
REPORT = ROOT / "audit" / "v12-eye-hidden-materials-validation.json"
CANVAS = (512, 1086)

EYES = {
    "画面左眼": {
        "prefix": "left",
        "box": (196, 110, 248, 154),
        "aperture": [
            (204, 132), (208, 127), (214, 124), (222, 122), (231, 124),
            (238, 128), (242, 132), (238, 139), (230, 144), (220, 145),
            (211, 143), (206, 138),
        ],
        "iris": (213, 123, 234, 144),
        "pupil": (218, 126, 230, 142),
        "highlight": (221, 122, 228, 130),
        "center": (223.5, 133.5),
        "closed": [(205, 135), (212, 137), (221, 138), (231, 137), (241, 134)],
    },
    "画面右眼": {
        "prefix": "right",
        "box": (255, 110, 307, 154),
        "aperture": [
            (260, 132), (265, 127), (272, 124), (281, 122), (290, 124),
            (296, 128), (299, 132), (296, 138), (289, 143), (281, 145),
            (272, 143), (264, 138),
        ],
        "iris": (269, 123, 290, 144),
        "pupil": (274, 126, 286, 142),
        "highlight": (277, 122, 284, 130),
        "center": (279.5, 133.5),
        "closed": [(260, 134), (269, 137), (279, 138), (289, 137), (299, 135)],
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


def rgba(rgb: np.ndarray, mask: np.ndarray) -> Image.Image:
    result = np.zeros((CANVAS[1], CANVAS[0], 4), dtype=np.uint8)
    result[:, :, :3] = rgb
    result[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
    return Image.fromarray(result, "RGBA")


def checker(size: tuple[int, int], cell: int = 8) -> Image.Image:
    w, h = size
    yy, xx = np.indices((h, w))
    board = (xx // cell + yy // cell) % 2
    values = np.where(board[:, :, None] == 0, 239, 207).astype(np.uint8)
    return Image.fromarray(np.repeat(values, 3, axis=2), "RGB")


def crop_checker(image: Image.Image, box: tuple[int, int, int, int], scale: int = 7) -> Image.Image:
    crop = image.crop(box).convert("RGBA")
    bg = checker(crop.size)
    bg.paste(crop, (0, 0), crop)
    return bg.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST)


def clip_shift(image: Image.Image, dx: int, dy: int, clip: np.ndarray) -> Image.Image:
    shifted = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    shifted.paste(image, (dx, dy), image)
    alpha = np.asarray(shifted)[:, :, 3] > 0
    shifted.putalpha(Image.fromarray(((alpha & clip) * 255).astype(np.uint8), "L"))
    return shifted


def build_radial_iris(
    source: np.ndarray,
    iris_mask: np.ndarray,
    visible_iris: np.ndarray,
    center: tuple[float, float],
) -> np.ndarray:
    yy, xx = np.indices(iris_mask.shape)
    pixels = source[visible_iris]
    if len(pixels) < 15:
        raise ValueError("可见虹膜样本不足")
    base = np.median(pixels, axis=0).astype(np.float64)
    cx, cy = center
    radius = np.sqrt(((xx - cx) / 11.0) ** 2 + ((yy - cy) / 11.0) ** 2)
    lower_light = np.clip((yy - cy) / 12.0, -0.2, 0.8)
    factor = np.clip(0.82 + 0.34 * radius + 0.42 * lower_light, 0.68, 1.72)
    result = source.copy().astype(np.float64)
    generated = base[None, None, :] * factor[:, :, None]
    result[iris_mask] = np.clip(generated[iris_mask], 20, 230)
    return result.astype(np.uint8)


def closed_line_layer(
    points: list[tuple[int, int]],
    source: np.ndarray,
    upper_line: np.ndarray,
) -> Image.Image:
    colors = source[upper_line]
    color = tuple(np.median(colors, axis=0).astype(np.uint8).tolist()) if len(colors) else (45, 35, 34)
    image = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.line(points, fill=(*color, 255), width=2, joint="curve")
    # Preserve a slightly heavier outer corner, matching the open-eye source.
    draw.ellipse((points[0][0] - 1, points[0][1] - 1, points[0][0] + 2, points[0][1] + 2), fill=(*color, 255))
    draw.ellipse((points[-1][0] - 1, points[-1][1] - 1, points[-1][0] + 2, points[-1][1] + 2), fill=(*color, 255))
    return image


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    QA.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    source_image = Image.open(SOURCE).convert("RGB")
    line_image = Image.open(LINE).convert("RGB")
    source = np.asarray(source_image)
    if source_image.size != CANVAS or line_image.size != CANVAS:
        raise ValueError("线稿和彩稿必须保持 512×1086 原始坐标")

    yy = np.indices((CANVAS[1], CANVAS[0]))[0]
    luminance = (
        0.2126 * source[:, :, 0]
        + 0.7152 * source[:, :, 1]
        + 0.0722 * source[:, :, 2]
    )

    default_eyes = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    gaze_left_all = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    gaze_right_all = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    closed_all = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    review_rows: list[dict[str, object]] = []
    stats: dict[str, dict[str, int]] = {}

    for eye_name, spec in EYES.items():
        aperture = polygon_mask(spec["aperture"])
        iris_full_mask = ellipse_mask(spec["iris"])
        pupil_full_mask = ellipse_mask(spec["pupil"])
        highlight_geometry = ellipse_mask(spec["highlight"])

        highlight_visible = highlight_geometry & aperture & (luminance > 150)
        upper_line = aperture & (yy <= 129) & (luminance < 155) & ~highlight_visible
        lower_line = aperture & (yy >= 139) & (luminance < 175) & ~highlight_visible
        pupil_visible = (
            pupil_full_mask
            & aperture
            & (yy >= 128)
            & (luminance < 105)
            & ~upper_line
            & ~lower_line
            & ~highlight_visible
        )
        iris_visible = (
            iris_full_mask
            & aperture
            & (yy >= 127)
            & (luminance < 190)
            & ~pupil_visible
            & ~highlight_visible
            & ~upper_line
            & ~lower_line
        )
        surface_exact = aperture & ~iris_visible & ~pupil_visible & ~highlight_visible & ~upper_line & ~lower_line

        channel_spread = np.max(source, axis=2).astype(np.int16) - np.min(source, axis=2).astype(np.int16)
        sclera_samples = source[aperture & (luminance > 225) & (channel_spread < 28)]
        if len(sclera_samples) < 8:
            sclera_color = np.array([249, 243, 240], dtype=np.uint8)
        else:
            measured = np.median(sclera_samples, axis=0)
            # The flat source contains eyelid blush inside the coarse aperture.
            # Keep that warm source hue, but lift it toward the brightest source
            # pixels so the hidden eyeball does not become a skin-coloured patch.
            sclera_color = np.clip(measured * 0.35 + np.array([252, 248, 246]) * 0.65, 0, 255).astype(np.uint8)
        sclera_rgb = source.copy()
        sclera_rgb[aperture] = sclera_color
        sclera_layer = rgba(sclera_rgb, aperture)

        iris_rgb = build_radial_iris(source, iris_full_mask, iris_visible, spec["center"])
        iris_complete = rgba(iris_rgb, iris_full_mask)

        pupil_pixels = source[pupil_visible]
        pupil_color = np.median(pupil_pixels, axis=0).astype(np.uint8)
        pupil_rgb = source.copy()
        pupil_rgb[pupil_full_mask] = pupil_color
        pupil_rgb[pupil_visible] = source[pupil_visible]
        pupil_complete = rgba(pupil_rgb, pupil_full_mask)

        surface_layer = rgba(source, surface_exact)
        iris_visible_layer = rgba(source, iris_visible)
        pupil_visible_layer = rgba(source, pupil_visible)
        highlight_layer = rgba(source, highlight_visible)
        upper_line_layer = rgba(source, upper_line)
        lower_line_layer = rgba(source, lower_line)
        closed_line = closed_line_layer(spec["closed"], source, upper_line)

        eye_default = sclera_layer.copy()
        for part in (
            iris_complete,
            pupil_complete,
            surface_layer,
            iris_visible_layer,
            pupil_visible_layer,
            highlight_layer,
            upper_line_layer,
            lower_line_layer,
        ):
            eye_default = Image.alpha_composite(eye_default, part)
        # Clip the material stack to the original eye opening in the default pose.
        eye_default.putalpha(Image.fromarray((aperture * 255).astype(np.uint8), "L"))
        default_eyes = Image.alpha_composite(default_eyes, eye_default)

        gaze_surface_mask = surface_exact & (luminance > 180)
        gaze_surface_layer = rgba(source, gaze_surface_mask)
        eye_base = Image.alpha_composite(sclera_layer, gaze_surface_layer)
        eye_base = Image.alpha_composite(eye_base, upper_line_layer)
        eye_base = Image.alpha_composite(eye_base, lower_line_layer)
        moving_group = Image.alpha_composite(iris_complete, pupil_complete)
        moving_group = Image.alpha_composite(moving_group, highlight_layer)

        gaze_left = Image.alpha_composite(eye_base, clip_shift(moving_group, -3, 0, aperture))
        gaze_right = Image.alpha_composite(eye_base, clip_shift(moving_group, 3, 0, aperture))
        gaze_left.putalpha(Image.fromarray((aperture * 255).astype(np.uint8), "L"))
        gaze_right.putalpha(Image.fromarray((aperture * 255).astype(np.uint8), "L"))
        gaze_left_all = Image.alpha_composite(gaze_left_all, gaze_left)
        gaze_right_all = Image.alpha_composite(gaze_right_all, gaze_right)
        closed_all = Image.alpha_composite(closed_all, closed_line)

        prefix = spec["prefix"]
        layers = {
            "01_完整眼白": sclera_layer,
            "02_完整虹膜": iris_complete,
            "03_完整瞳孔": pupil_complete,
            "04_原高光": highlight_layer,
            "05_眼睑表面原像素": surface_layer,
            "06_上眼线原像素": upper_line_layer,
            "07_下眼线原像素": lower_line_layer,
            "08_闭眼线候选": closed_line,
        }
        for suffix, image in layers.items():
            image.save(OUT / f"{prefix}_{suffix}.png")

        iris_pupil = Image.alpha_composite(iris_complete, pupil_complete)
        iris_pupil = Image.alpha_composite(iris_pupil, highlight_layer)
        review_rows.append(
            {
                "name": eye_name,
                "box": spec["box"],
                "original": rgba(source, aperture),
                "sclera": sclera_layer,
                "iris": iris_pupil,
                "default": eye_default,
                "gaze": gaze_right if eye_name == "画面左眼" else gaze_left,
                "closed": closed_line,
            }
        )
        stats[eye_name] = {
            "aperturePixels": int(aperture.sum()),
            "visibleIrisPixels": int(iris_visible.sum()),
            "visiblePupilPixels": int(pupil_visible.sum()),
            "highlightPixels": int(highlight_visible.sum()),
            "upperLinePixels": int(upper_line.sum()),
            "lowerLinePixels": int(lower_line.sum()),
        }

    residual = Image.open(V6 / "头部其余层.png").convert("RGBA")
    face = Image.open(V6 / "脸底_含刘海下补全.png").convert("RGBA")
    brows = Image.open(V6 / "双眉_原像素原坐标.png").convert("RGBA")
    hair = Image.open(V6 / "前发_修订原像素.png").convert("RGBA")
    full_default = residual.copy()
    for part in (face, default_eyes, brows, hair):
        full_default = Image.alpha_composite(full_default, part)
    diff = ImageChops.difference(full_default.convert("RGB"), source_image)
    diff_array = np.asarray(diff)
    mae = float(diff_array.mean())
    max_error = int(diff_array.max())

    default_eyes.save(OUT / "双眼默认材料回组.png")
    gaze_left_all.save(OUT / "双眼视线左移3px检查.png")
    gaze_right_all.save(OUT / "双眼视线右移3px检查.png")
    closed_all.save(OUT / "双眼闭眼线候选.png")
    full_default.save(OUT / "整脸默认合成_零误差.png")

    headers = ["原眼", "完整眼白", "完整虹膜/瞳孔", "默认材料回组", "视线移动 3px", "闭眼线候选"]
    panel_w, panel_h = 360, 308
    title_h, header_h, row_gap = 66, 52, 74
    sheet_w = panel_w * 6
    sheet_h = title_h + header_h + (panel_h + row_gap) * 2 + 116
    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((18, 16), "小星双眼：隐藏眼白、完整虹膜与闭眼线审查", fill="#171717", font=font(27))
    for col, header in enumerate(headers):
        draw.text((col * panel_w + 14, title_h + 10), header, fill="#222222", font=font(20))

    for row, item in enumerate(review_rows):
        y = title_h + header_h + row * (panel_h + row_gap)
        images = [item["original"], item["sclera"], item["iris"], item["default"], item["gaze"], item["closed"]]
        for col, image in enumerate(images):
            crop = crop_checker(image, item["box"])
            crop.thumbnail((panel_w - 16, panel_h - 16), Image.Resampling.NEAREST)
            x = col * panel_w + (panel_w - crop.width) // 2
            py = y + (panel_h - crop.height) // 2
            sheet.paste(crop, (x, py))
            draw.rectangle(
                (col * panel_w, y, (col + 1) * panel_w - 1, y + panel_h - 1),
                outline="#777777",
                width=2,
            )
        draw.text(
            (18, y + panel_h + 11),
            f"{item['name']}：默认像素保持原位；完整材料只在眼球移动或闭眼时使用。",
            fill="#303030",
            font=font(19),
        )

    footer_y = sheet_h - 93
    draw.text(
        (18, footer_y),
        f"整脸默认回组：MAE={mae:.3f}，最大通道差={max_error}；完整虹膜的补画部分在默认睁眼中不可见。",
        fill="#8D251E",
        font=font(21),
    )
    draw.text(
        (18, footer_y + 40),
        "闭眼线为单独候选层，不参与默认合成；视线测试只移动 3px，避免低分辨率原稿被过度拉扯。",
        fill="#333333",
        font=font(19),
    )
    sheet.save(QA)

    REPORT.write_text(
        json.dumps(
            {
                "stage": "v12-eye-hidden-materials",
                "source": str(SOURCE.relative_to(ROOT)),
                "lineReference": str(LINE.relative_to(ROOT)),
                "parts": stats,
                "gazeStressPixels": 3,
                "defaultCompositeMae": mae,
                "defaultCompositeMaxError": max_error,
                "visiblePixelsRepainted": False,
                "hiddenIrisFillVisibleInDefault": False,
                "closedEyeUsedInDefault": False,
                "psdImport": False,
                "cubismImport": False,
                "next": "visual-review_then-psd-import-if-approved",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
