from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "source" / "masters" / "front-line-source-exact-after-reset.png"
COLOR = ROOT / "source" / "masters" / "front-color-source-exact-after-reset.png"
OUT_DIR = ROOT / "model" / "reset-v2" / "eye-blueprint"
QA_IMAGE = ROOT / "qa" / "reset-v2-eye-closed-boundary-review.png"
QA_CLOSEUP = ROOT / "qa" / "reset-v2-eye-closeup-review.png"
AUDIT_JSON = ROOT / "audit" / "reset-v2-eye-blueprint.json"
CANVAS = (512, 1086)


def font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def cubic(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    samples: int = 40,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index in range(samples + 1):
        t = index / samples
        u = 1.0 - t
        x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


def ellipse_points(center: tuple[float, float], radius: tuple[float, float], samples: int = 96) -> list[tuple[float, float]]:
    return [
        (
            center[0] + math.cos(index * math.tau / samples) * radius[0],
            center[1] + math.sin(index * math.tau / samples) * radius[1],
        )
        for index in range(samples)
    ]


EYES = {
    "画面左眼": {
        "upper": ((188, 132), (194, 124), (219, 123), (231, 132)),
        "lower": ((231, 132), (226, 141), (195, 145), (188, 132)),
        "irisCenter": (210.5, 133.5),
        "irisRadius": (12.5, 14.0),
        "pupilCenter": (210.5, 132.5),
        "pupilRadius": (6.2, 9.2),
        "highlightCenter": (207.0, 127.5),
        "highlightRadius": (3.2, 3.2),
    },
    "画面右眼": {
        "upper": ((276, 132), (284, 123), (310, 123), (322, 132)),
        "lower": ((322, 132), (318, 142), (288, 145), (276, 132)),
        "irisCenter": (299.5, 133.5),
        "irisRadius": (12.5, 14.0),
        "pupilCenter": (299.5, 132.5),
        "pupilRadius": (6.2, 9.2),
        "highlightCenter": (296.0, 127.5),
        "highlightRadius": (3.2, 3.2),
    },
}


def full_canvas_rgba() -> Image.Image:
    return Image.new("RGBA", CANVAS, (0, 0, 0, 0))


def draw_shape(points: list[tuple[float, float]], fill: tuple[int, int, int, int]) -> Image.Image:
    image = full_canvas_rgba()
    ImageDraw.Draw(image).polygon(points, fill=fill)
    return image


def draw_curve(points: list[tuple[float, float]], fill: tuple[int, int, int, int], width: int) -> Image.Image:
    image = full_canvas_rgba()
    ImageDraw.Draw(image).line(points, fill=fill, width=width, joint="curve")
    return image


def checker() -> Image.Image:
    image = Image.new("RGB", CANVAS, (247, 247, 247))
    draw = ImageDraw.Draw(image)
    cell = 16
    for y in range(0, CANVAS[1], cell):
        for x in range(0, CANVAS[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(230, 230, 230))
    return image


def show_on_checker(image: Image.Image) -> Image.Image:
    background = checker()
    background.paste(image.convert("RGB"), (0, 0), image.getchannel("A"))
    return background


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUT_DIR.glob("*.png"):
        stale.unlink()

    layers: dict[str, Image.Image] = {}
    contracts: dict[str, object] = {}
    for side, spec in EYES.items():
        upper = cubic(*spec["upper"])
        lower = cubic(*spec["lower"])
        eye_closed_shape = upper + lower[1:]
        iris_shape = ellipse_points(spec["irisCenter"], spec["irisRadius"])
        pupil_shape = ellipse_points(spec["pupilCenter"], spec["pupilRadius"])
        highlight_shape = ellipse_points(spec["highlightCenter"], spec["highlightRadius"])

        prefix = "screen_left" if side == "画面左眼" else "screen_right"
        layers[f"{prefix}_01_完整眼白遮罩"] = draw_shape(eye_closed_shape, (255, 255, 255, 255))
        layers[f"{prefix}_02_完整虹膜遮罩"] = draw_shape(iris_shape, (105, 88, 84, 255))
        layers[f"{prefix}_03_完整瞳孔遮罩"] = draw_shape(pupil_shape, (24, 18, 20, 255))
        layers[f"{prefix}_04_高光遮罩"] = draw_shape(highlight_shape, (255, 255, 255, 255))
        layers[f"{prefix}_05_上眼线曲线"] = draw_curve(upper, (35, 24, 26, 255), 3)
        layers[f"{prefix}_06_下眼线曲线"] = draw_curve(lower, (120, 95, 96, 255), 2)

        contracts[side] = {
            "upperCubic": [list(point) for point in spec["upper"]],
            "lowerCubic": [list(point) for point in spec["lower"]],
            "outerOrInnerEndpoints": [list(upper[0]), list(upper[-1])],
            "irisCenter": list(spec["irisCenter"]),
            "irisRadius": list(spec["irisRadius"]),
            "pupilCenter": list(spec["pupilCenter"]),
            "pupilRadius": list(spec["pupilRadius"]),
        }

    for name, image in layers.items():
        image.save(OUT_DIR / f"{name}.png")

    # 平色回组用于检查闭合几何；不是最终纹理。
    flat = full_canvas_rgba()
    for side in ("screen_left", "screen_right"):
        for suffix in (
            "01_完整眼白遮罩",
            "02_完整虹膜遮罩",
            "03_完整瞳孔遮罩",
            "04_高光遮罩",
            "06_下眼线曲线",
            "05_上眼线曲线",
        ):
            flat = Image.alpha_composite(flat, layers[f"{side}_{suffix}"])
    flat.save(OUT_DIR / "双眼平色回组.png")

    line = Image.open(LINE).convert("RGB")
    color = Image.open(COLOR).convert("RGB")
    overlay = color.convert("RGBA")
    outline = full_canvas_rgba()
    outline_draw = ImageDraw.Draw(outline)
    for spec in EYES.values():
        upper = cubic(*spec["upper"])
        lower = cubic(*spec["lower"])
        outline_draw.line(upper, fill=(220, 35, 80, 230), width=2)
        outline_draw.line(lower, fill=(20, 130, 220, 230), width=2)
        outline_draw.line(ellipse_points(spec["irisCenter"], spec["irisRadius"]) + [ellipse_points(spec["irisCenter"], spec["irisRadius"])[0]], fill=(245, 145, 20, 210), width=1)
    overlay = Image.alpha_composite(overlay, outline)
    overlay.save(OUT_DIR / "双眼曲线叠加审查_非材料.png")

    # 仅为人工看清像素位置的审查图；所有真正材料仍保持完整画布。
    closeup_box = (165, 98, 345, 160)
    closeup_source = color.crop(closeup_box).resize((1080, 372), Image.Resampling.NEAREST)
    closeup_overlay = overlay.convert("RGB").crop(closeup_box).resize((1080, 372), Image.Resampling.NEAREST)
    closeup = Image.new("RGB", (2220, 520), (248, 248, 248))
    closeup_draw = ImageDraw.Draw(closeup)
    closeup_draw.text((24, 14), "双眼局部放大审查（仅预览，不是材料图层）", font=font(34), fill=(20, 20, 20))
    closeup_draw.text((24, 62), "左：原始彩稿；右：曲线叠加。真实材料仍为 512×1086 全画布 PNG。", font=font(23), fill=(170, 35, 35))
    closeup.paste(closeup_source, (24, 120))
    closeup.paste(closeup_overlay, (1116, 120))
    closeup_draw.rectangle((24, 120, 1103, 491), outline=(130, 130, 130), width=2)
    closeup_draw.rectangle((1116, 120, 2195, 491), outline=(130, 130, 130), width=2)
    closeup.save(QA_CLOSEUP)

    panels = [
        ("① 原始线稿（完整画布）", line),
        ("② 原始彩稿（完整画布）", color),
        ("③ 闭合眼部平色材料（完整画布）", show_on_checker(flat)),
        ("④ 曲线叠加定位（仅审查，不是材料）", overlay.convert("RGB")),
    ]
    panel_w, panel_h = CANVAS
    margin, gap, label_h = 24, 24, 72
    board_w = margin * 2 + panel_w * 4 + gap * 3
    board_h = 150 + panel_h + label_h + 120
    board = Image.new("RGB", (board_w, board_h), (248, 248, 248))
    draw = ImageDraw.Draw(board)
    draw.text((24, 20), "小星 Reset V2：双眼闭合语义边界", font=font(40), fill=(20, 20, 20))
    draw.text(
        (24, 72),
        "材料均为完整 512×1086 同坐标图层；眼裂由贝塞尔曲线实际绘制，彩稿只用于身份对照。",
        font=font(23),
        fill=(170, 35, 35),
    )
    draw.text(
        (24, 106),
        "红=上眼线，蓝=下眼线，橙=完整虹膜范围；叠加线只用于检查位置，不导入模型。",
        font=font(21),
        fill=(55, 55, 55),
    )

    for index, (label, image) in enumerate(panels):
        x = margin + index * (panel_w + gap)
        y = 150
        board.paste(image.convert("RGB"), (x, y))
        draw.rectangle((x, y, x + panel_w - 1, y + panel_h - 1), outline=(130, 130, 130), width=2)
        draw.text((x, y + panel_h + 12), label, font=font(23), fill=(20, 20, 20))

    draw.text(
        (24, board_h - 75),
        "停止条件：双眼任一眼角、上峰、下峰或虹膜中心不贴合原稿，就不生成纹理 PSD。",
        font=font(23),
        fill=(170, 35, 35),
    )
    board.save(QA_IMAGE)

    report = {
        "stage": "reset-v2-eye-closed-semantic-boundary",
        "status": "visual_review_required",
        "canvas": list(CANVAS),
        "lineSource": str(LINE.relative_to(ROOT)),
        "colorReference": str(COLOR.relative_to(ROOT)),
        "contracts": contracts,
        "layers": [
            {
                "name": name,
                "path": str((OUT_DIR / f"{name}.png").relative_to(ROOT)),
                "size": list(image.size),
            }
            for name, image in layers.items()
        ],
        "rules": {
            "fullCanvasLayers": True,
            "closedGeometry": True,
            "curvesActuallyDrawn": True,
            "noCropAsMaterial": True,
            "flatMasksOnly": True,
            "noTexturePsdYet": True,
            "noCubism": True,
        },
        "closeupReviewOnly": str(QA_CLOSEUP.relative_to(ROOT)),
    }
    AUDIT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
