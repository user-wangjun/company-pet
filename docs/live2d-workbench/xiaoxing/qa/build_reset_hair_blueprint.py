from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
COLOR = ROOT / "source" / "masters" / "front-color-source-exact-after-reset.png"
LINE = ROOT / "source" / "masters" / "front-line-source-exact-after-reset.png"
OUT_DIR = ROOT / "model" / "reset-v2" / "hair-blueprint"
QA_IMAGE = ROOT / "qa" / "reset-v2-hair-closed-boundary-review.png"
QA_CLOSEUP = ROOT / "qa" / "reset-v2-hair-closeup-review.png"
AUDIT_JSON = ROOT / "audit" / "reset-v2-hair-blueprint.json"
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
    samples: int = 36,
) -> list[tuple[float, float]]:
    points = []
    for index in range(samples + 1):
        t = index / samples
        u = 1 - t
        points.append(
            (
                u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
            )
        )
    return points


def mask_from_points(points: list[tuple[float, float]]) -> Image.Image:
    image = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(image).polygon(points, fill=255)
    return image


def rgba_from_mask(mask: Image.Image, color: tuple[int, int, int, int]) -> Image.Image:
    image = Image.new("RGBA", CANVAS, color)
    image.putalpha(mask)
    return image


def checker() -> Image.Image:
    image = Image.new("RGB", CANVAS, (247, 247, 247))
    draw = ImageDraw.Draw(image)
    for y in range(0, CANVAS[1], 16):
        for x in range(0, CANVAS[0], 16):
            if (x // 16 + y // 16) % 2:
                draw.rectangle((x, y, x + 15, y + 15), fill=(230, 230, 230))
    return image


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUT_DIR.glob("*.png"):
        stale.unlink()

    # 后发是一块完整底材：外轮廓来自正面线稿，脸和前发将覆盖中央。
    back_outer_left = cubic((256, 31), (210, 20), (165, 55), (157, 150))
    back_lower_left = cubic((157, 150), (153, 240), (165, 290), (190, 325))
    back_bottom = [
        (190, 325), (200, 338), (210, 327), (220, 345), (232, 332),
        (244, 350), (256, 335), (268, 350), (280, 332), (292, 345),
        (302, 327), (312, 338), (322, 325),
    ]
    back_lower_right = cubic((322, 325), (347, 290), (359, 240), (355, 150))
    back_outer_right = cubic((355, 150), (347, 55), (302, 20), (256, 31))
    back_points = back_outer_left + back_lower_left[1:] + back_bottom[1:] + back_lower_right[1:] + back_outer_right[1:]

    # 中央刘海：上缘沿头顶，底缘按原稿前额发束的总体锯齿走势绘制。
    bangs_top_left = cubic((185, 118), (185, 70), (215, 38), (256, 30))
    bangs_top_right = cubic((256, 30), (297, 38), (327, 70), (327, 118))
    bangs_fringe = [
        (325, 112), (318, 123), (310, 112), (302, 128), (292, 115),
        (283, 130), (272, 117), (260, 132), (248, 116), (238, 130),
        (228, 114), (218, 126), (208, 112), (198, 122), (188, 110),
    ]
    bangs_points = bangs_top_left + bangs_top_right[1:] + bangs_fringe + [(171, 119)]

    # 画面左右侧发保持粗粒度整束，不拆成大量小发丝。
    left_outer = cubic((184, 85), (158, 120), (153, 220), (175, 315))
    left_tips = [(175, 315), (180, 340), (188, 326), (194, 345), (201, 328), (210, 318)]
    left_inner = cubic((210, 318), (208, 282), (215, 200), (215, 115))
    left_top = cubic((217, 114), (211, 92), (198, 82), (184, 82))
    left_points = left_outer + left_tips[1:] + left_inner[1:] + left_top[1:]

    right_outer = cubic((328, 85), (354, 120), (359, 220), (337, 315))
    right_tips = [(337, 315), (332, 340), (324, 326), (318, 345), (311, 328), (302, 318)]
    right_inner = cubic((302, 318), (304, 282), (297, 200), (297, 115))
    right_top = cubic((295, 114), (301, 92), (314, 82), (328, 82))
    right_points = right_outer + right_tips[1:] + right_inner[1:] + right_top[1:]

    shapes = {
        "01_后发完整遮罩": back_points,
        "02_中央刘海完整遮罩": bangs_points,
        "03_画面左侧发完整遮罩": left_points,
        "04_画面右侧发完整遮罩": right_points,
    }
    preview_colors = {
        "01_后发完整遮罩": (35, 42, 60, 235),
        "02_中央刘海完整遮罩": (105, 65, 135, 235),
        "03_画面左侧发完整遮罩": (45, 120, 155, 235),
        "04_画面右侧发完整遮罩": (45, 150, 105, 235),
    }

    masks: dict[str, Image.Image] = {}
    for name, points in shapes.items():
        mask = mask_from_points(points)
        masks[name] = mask
        rgba_from_mask(mask, (255, 255, 255, 255)).save(OUT_DIR / f"{name}.png")

    flat = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for name in ("01_后发完整遮罩", "03_画面左侧发完整遮罩", "04_画面右侧发完整遮罩", "02_中央刘海完整遮罩"):
        flat = Image.alpha_composite(flat, rgba_from_mask(masks[name], preview_colors[name]))
    flat.save(OUT_DIR / "头发平色回组.png")

    color = Image.open(COLOR).convert("RGB")
    line = Image.open(LINE).convert("RGB")
    overlay = color.convert("RGBA")
    overlay_draw = ImageDraw.Draw(overlay)
    outline_colors = {
        "01_后发完整遮罩": (255, 80, 80, 235),
        "02_中央刘海完整遮罩": (230, 60, 220, 235),
        "03_画面左侧发完整遮罩": (20, 160, 245, 235),
        "04_画面右侧发完整遮罩": (30, 205, 110, 235),
    }
    for name, points in shapes.items():
        if name == "01_后发完整遮罩":
            overlay_draw.line(back_outer_left + back_lower_left[1:], fill=outline_colors[name], width=2)
            overlay_draw.line(back_lower_right + back_outer_right[1:], fill=outline_colors[name], width=2)
        else:
            overlay_draw.line(points + [points[0]], fill=outline_colors[name], width=2)
    overlay.save(OUT_DIR / "头发曲线叠加审查_非材料.png")

    panels = [
        ("① 原始线稿（完整画布）", line),
        ("② 原始彩稿（完整画布）", color),
        ("③ 头发闭合平色材料（完整画布）", flat),
        ("④ 曲线叠加定位（仅审查）", overlay.convert("RGB")),
    ]
    board = Image.new("RGB", (2176, 1410), (248, 248, 248))
    draw = ImageDraw.Draw(board)
    draw.text((24, 18), "小星 Reset V2：头发闭合语义边界", font=font(40), fill=(20, 20, 20))
    draw.text(
        (24, 70),
        "仅保留后发、中央刘海、画面左右侧发四组；每组均实际绘制为完整 512×1086 闭合遮罩。",
        font=font(23),
        fill=(170, 35, 35),
    )
    draw.text(
        (24, 104),
        "红=后发，紫=刘海，蓝=画面左侧发，绿=画面右侧发；彩色线只用于定位检查。",
        font=font(21),
        fill=(55, 55, 55),
    )
    for index, (label, image) in enumerate(panels):
        x = 24 + index * 536
        y = 150
        if image.mode == "RGBA":
            background = checker()
            background.paste(image.convert("RGB"), (0, 0), image.getchannel("A"))
            board.paste(background, (x, y))
        else:
            board.paste(image, (x, y))
        draw.rectangle((x, y, x + 511, y + 1085), outline=(130, 130, 130), width=2)
        draw.text((x, 1248), label, font=font(23), fill=(20, 20, 20))
    draw.text(
        (24, 1350),
        "停止条件：任一发组越过原发束进入脸、衣服或印花，或隐藏补全出现硬直块，就不生成纹理 PSD。",
        font=font(23),
        fill=(170, 35, 35),
    )
    board.save(QA_IMAGE)

    crop_box = (110, 5, 402, 370)
    original_close = color.crop(crop_box).resize((876, 1095), Image.Resampling.NEAREST)
    overlay_close = overlay.convert("RGB").crop(crop_box).resize((876, 1095), Image.Resampling.NEAREST)
    close = Image.new("RGB", (1800, 1240), (248, 248, 248))
    close_draw = ImageDraw.Draw(close)
    close_draw.text((24, 16), "头发局部放大审查（仅预览，不是材料图层）", font=font(34), fill=(20, 20, 20))
    close_draw.text(
        (24, 62),
        "左：原始彩稿；右：闭合曲线叠加。真实遮罩仍为 512×1086 全画布 PNG。",
        font=font(23),
        fill=(170, 35, 35),
    )
    close.paste(original_close, (24, 120))
    close.paste(overlay_close, (900, 120))
    close_draw.rectangle((24, 120, 899, 1214), outline=(130, 130, 130), width=2)
    close_draw.rectangle((900, 120, 1775, 1214), outline=(130, 130, 130), width=2)
    close.save(QA_CLOSEUP)

    report = {
        "stage": "reset-v2-hair-closed-semantic-boundary",
        "status": "visual_review_required",
        "canvas": list(CANVAS),
        "lineSource": str(LINE.relative_to(ROOT)),
        "colorReference": str(COLOR.relative_to(ROOT)),
        "groups": [
            {
                "name": name,
                "mask": str((OUT_DIR / f"{name}.png").relative_to(ROOT)),
                "closedPointCount": len(points),
            }
            for name, points in shapes.items()
        ],
        "rules": {
            "fullCanvasLayers": True,
            "closedGeometry": True,
            "coarseFourGroupPolicy": True,
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
