from __future__ import annotations

import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(__file__).resolve().parents[3]
SKELETON = json.loads((ROOT / "skeleton.json").read_text(encoding="utf-8"))
LINE_PATH = PACKAGE / "source/masters/front-line-source-exact-after-reset.png"
COLOR_PATH = PACKAGE / "source/masters/front-color-source-exact-after-reset.png"
OUTPUT_PATH = ROOT / "qa/skeleton-design-review.png"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_name = "msyhbd.ttc" if bold else "msyh.ttc"
    candidates = [
        Path(os.environ.get("WINDIR", "")) / "Fonts" / font_name,
        Path(font_name),
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_TITLE = font(30, True)
FONT_SECTION = font(22, True)
FONT_BODY = font(18)
FONT_SMALL = font(15)


def xy(name: str) -> tuple[float, float]:
    item = SKELETON["landmarks"][name]
    return float(item["x"]), float(item["y"])


PS = xy("shoulder")
PE = xy("elbow")
PW = xy("wrist")


def draw_skeleton(draw: ImageDraw.ImageDraw, transform, width: int = 6) -> None:
    ps = transform(PS)
    pe = transform(PE)
    pw = transform(PW)
    bone = (235, 63, 72, 255)
    joint = (0, 117, 190, 255)
    draw.line([ps, pe, pw], fill=bone, width=width, joint="curve")
    radii = {
        "肩": SKELETON["jointDisksPx"]["shoulderRadius"],
        "肘": SKELETON["jointDisksPx"]["elbowRadius"],
        "腕": SKELETON["jointDisksPx"]["wristRadius"],
    }
    for label, point in zip(("肩", "肘", "腕"), (ps, pe, pw)):
        scale_probe = transform((PS[0] + 1, PS[1]))[0] - transform(PS)[0]
        radius = max(7, radii[label] * scale_probe)
        draw.ellipse(
            [point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius],
            outline=joint,
            width=max(2, width // 2),
        )
        draw.ellipse(
            [point[0] - 5, point[1] - 5, point[0] + 5, point[1] + 5],
            fill=joint,
        )
        draw.text((point[0] + radius + 5, point[1] - 13), label, font=FONT_BODY, fill=joint)


def paste_panel(canvas, image, origin, title):
    x, y = origin
    canvas.paste(image, (x, y))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([x, y, x + image.width - 1, y + image.height - 1], outline=(180, 180, 180), width=2)
    draw.text((x, y - 34), title, font=FONT_SECTION, fill=(25, 25, 25))


def make_full_panel(line: Image.Image) -> Image.Image:
    scale = 0.72
    panel = line.convert("RGBA").resize(
        (round(line.width * scale), round(line.height * scale)),
        Image.Resampling.LANCZOS,
    )
    overlay = Image.new("RGBA", panel.size, (0, 0, 0, 0))
    draw_skeleton(ImageDraw.Draw(overlay), lambda p: (p[0] * scale, p[1] * scale), width=5)
    return Image.alpha_composite(panel, overlay).convert("RGB")


def make_crop_panel(source: Image.Image, skeleton: bool) -> Image.Image:
    crop_box = (280, 220, 472, 690)
    scale = 2
    crop = source.crop(crop_box).convert("RGBA").resize(
        ((crop_box[2] - crop_box[0]) * scale, (crop_box[3] - crop_box[1]) * scale),
        Image.Resampling.NEAREST,
    )
    if skeleton:
        overlay = Image.new("RGBA", crop.size, (0, 0, 0, 0))
        transform = lambda p: ((p[0] - crop_box[0]) * scale, (p[1] - crop_box[1]) * scale)
        draw_skeleton(ImageDraw.Draw(overlay), transform, width=7)
        crop = Image.alpha_composite(crop, overlay)
    return crop.convert("RGB")


def draw_text_block(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    rest = SKELETON["restAnglesDeg"]
    ranges = SKELETON["allowedRangesDeg"]
    lines = [
        ("设计状态", "待用户视觉确认"),
        ("验证侧", "画面右侧／角色左臂"),
        ("肩", f"({PS[0]:.0f}, {PS[1]:.0f})，袖内推断"),
        ("肘", f"({PE[0]:.0f}, {PE[1]:.0f})，轮廓估计"),
        ("腕", f"({PW[0]:.0f}, {PW[1]:.0f})，手链下估计"),
        ("L1", f"{SKELETON['boneLengthsPx']['L1ShoulderToElbow']:.3f} px，锁定"),
        ("L2", f"{SKELETON['boneLengthsPx']['L2ElbowToWrist']:.3f} px，锁定"),
        ("θ1 默认", f"{rest['theta1']:.3f}°"),
        ("θ1 范围", f"{ranges['theta1']['min']:.3f}° ～ {ranges['theta1']['max']:.3f}°"),
        ("θ2 默认", f"{rest['theta2']:.3f}°"),
        ("θ2 范围", f"{ranges['theta2']['min']:.3f}° ～ {ranges['theta2']['max']:.3f}°"),
        ("采样", "41 帧 0→1→0，无 Physics"),
    ]
    draw.text((x, y), "数值合同", font=FONT_SECTION, fill=(25, 25, 25))
    y += 40
    for label, value in lines:
        draw.text((x, y), label, font=FONT_SMALL, fill=(85, 85, 85))
        draw.text((x + 100, y), value, font=FONT_SMALL, fill=(20, 20, 20))
        y += 30
    y += 12
    draw.text((x, y), "本图只审骨架与范围", font=FONT_BODY, fill=(190, 45, 50))
    y += 32
    notices = [
        "• 蓝圈是覆盖搜索用关节盘，不是正式材料。",
        "• 手链不得用于遮住腕部失败。",
        "• 尚未生成纯色材料、纹理或 Cubism。",
        "• 近看图采用最近邻放大，属于审查裁剪。",
    ]
    for line in notices:
        draw.text((x, y), line, font=FONT_SMALL, fill=(45, 45, 45))
        y += 28


def main() -> None:
    line = Image.open(LINE_PATH).convert("RGB")
    color = Image.open(COLOR_PATH).convert("RGB")
    if line.size != (512, 1086) or color.size != (512, 1086):
        raise ValueError("authoritative front masters must remain 512x1086")

    canvas = Image.new("RGB", (1580, 1100), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((35, 20), "小星｜画面右侧手臂：阶段 A 骨架设计审查", font=FONT_TITLE, fill=(20, 20, 20))
    draw.text(
        (35, 62),
        "审查图，不是材料｜红线：固定骨段｜蓝圈：覆盖搜索关节盘",
        font=FONT_BODY,
        fill=(85, 85, 85),
    )

    full = make_full_panel(line)
    line_crop = make_crop_panel(line, skeleton=True)
    color_crop = make_crop_panel(color, skeleton=True)
    paste_panel(canvas, full, (35, 130), "正面线稿定位")
    paste_panel(canvas, line_crop, (430, 130), "线稿近看 200%（最近邻）")
    paste_panel(canvas, color_crop, (840, 130), "彩稿近看 200%（仅身份／材质参照）")
    draw_text_block(draw, 1245, 130)

    draw.text(
        (35, 1062),
        "待审：选侧、肩肘腕落点、固定骨长、动作范围、手链排除规则。",
        font=FONT_BODY,
        fill=(20, 20, 20),
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUTPUT_PATH)
    print(OUTPUT_PATH.relative_to(PACKAGE).as_posix())


if __name__ == "__main__":
    main()
