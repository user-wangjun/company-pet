from __future__ import annotations

import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(__file__).resolve().parents[3]
SKELETON = json.loads((ROOT / "skeleton.json").read_text(encoding="utf-8"))
EVIDENCE = json.loads((ROOT / "audit/elbow-landmark-evidence.json").read_text(encoding="utf-8"))
LINE_PATH = PACKAGE / "source/masters/front-line-source-exact-after-reset.png"
COLOR_PATH = PACKAGE / "source/masters/front-color-source-exact-after-reset.png"
OUTPUT_PATH = ROOT / "qa/skeleton-design-review-v2.png"


def font(size: int, bold: bool = False):
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


def xy(name):
    item = SKELETON["landmarks"][name]
    return float(item["x"]), float(item["y"])


PS, PE, PW = xy("shoulder"), xy("elbow"), xy("wrist")


def dashed_line(draw, start, end, fill, width=3, dash=12, gap=8):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    cursor = 0.0
    while cursor < length:
        stop = min(cursor + dash, length)
        draw.line(
            [
                (start[0] + ux * cursor, start[1] + uy * cursor),
                (start[0] + ux * stop, start[1] + uy * stop),
            ],
            fill=fill,
            width=width,
        )
        cursor += dash + gap


def draw_skeleton(draw, transform, width=6, show_cross_section=True):
    ps, pe, pw = transform(PS), transform(PE), transform(PW)
    bone = (235, 63, 72, 255)
    joint = (0, 117, 190, 255)
    chord = (120, 120, 120, 230)
    cross = (0, 145, 90, 255)
    dashed_line(draw, ps, pw, chord, max(2, width // 2))
    draw.line([ps, pe, pw], fill=bone, width=width, joint="curve")

    scale = transform((PS[0] + 1, PS[1]))[0] - transform(PS)[0]
    radii = [
        SKELETON["jointDisksPx"]["shoulderRadius"],
        SKELETON["jointDisksPx"]["elbowRadius"],
        SKELETON["jointDisksPx"]["wristRadius"],
    ]
    for label, point, radius_raw in zip(("肩", "肘", "腕"), (ps, pe, pw), radii):
        radius = max(7, radius_raw * scale)
        draw.ellipse(
            [point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius],
            outline=joint,
            width=max(2, width // 2),
        )
        draw.ellipse([point[0] - 5, point[1] - 5, point[0] + 5, point[1] + 5], fill=joint)
        draw.text((point[0] + radius + 5, point[1] - 13), label, font=FONT_BODY, fill=joint)

    if show_cross_section:
        scan = next(row for row in EVIDENCE["scanlines"] if row["y"] == 425)
        left = transform((scan["dominantSkinSpanX"][0], 425))
        right = transform((scan["dominantSkinSpanX"][1], 425))
        draw.line([left, right], fill=cross, width=max(3, width // 2))
        draw.ellipse([left[0] - 4, left[1] - 4, left[0] + 4, left[1] + 4], fill=cross)
        draw.ellipse([right[0] - 4, right[1] - 4, right[0] + 4, right[1] + 4], fill=cross)


def paste_panel(canvas, image, origin, title):
    x, y = origin
    canvas.paste(image, (x, y))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([x, y, x + image.width - 1, y + image.height - 1], outline=(180, 180, 180), width=2)
    draw.text((x, y - 34), title, font=FONT_SECTION, fill=(25, 25, 25))


def make_full_panel(line):
    scale = 0.72
    panel = line.convert("RGBA").resize(
        (round(line.width * scale), round(line.height * scale)),
        Image.Resampling.LANCZOS,
    )
    overlay = Image.new("RGBA", panel.size, (0, 0, 0, 0))
    draw_skeleton(ImageDraw.Draw(overlay), lambda p: (p[0] * scale, p[1] * scale), width=5)
    return Image.alpha_composite(panel, overlay).convert("RGB")


def make_crop_panel(source):
    crop_box = (280, 220, 472, 690)
    scale = 2
    crop = source.crop(crop_box).convert("RGBA").resize(
        ((crop_box[2] - crop_box[0]) * scale, (crop_box[3] - crop_box[1]) * scale),
        Image.Resampling.NEAREST,
    )
    overlay = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    transform = lambda p: ((p[0] - crop_box[0]) * scale, (p[1] - crop_box[1]) * scale)
    draw_skeleton(ImageDraw.Draw(overlay), transform, width=7)
    return Image.alpha_composite(crop, overlay).convert("RGB")


def draw_text_block(draw, x, y):
    rest = SKELETON["restAnglesDeg"]
    ranges = SKELETON["allowedRangesDeg"]
    correction = SKELETON["elbowCorrectionFromV1"]
    lines = [
        ("状态", "V2，待用户视觉确认"),
        ("肩", f"({PS[0]:.0f}, {PS[1]:.0f})，袖内推断"),
        ("肘", f"({PE[0]:.0f}, {PE[1]:.0f})，向内修正 11 px"),
        ("腕", f"({PW[0]:.0f}, {PW[1]:.0f})，手链下估计"),
        ("皮肤横截面", "y=425，x=341～374"),
        ("直线对照", f"肘向内偏 {correction['newElbowInwardOffsetFromChordPx']:.2f} px"),
        ("轮廓中心拟合", f"RMS {EVIDENCE['correctedCenterlineFit']['rmsErrorPx']:.2f} px"),
        ("L1", f"{SKELETON['boneLengthsPx']['L1ShoulderToElbow']:.3f} px"),
        ("L2", f"{SKELETON['boneLengthsPx']['L2ElbowToWrist']:.3f} px"),
        ("默认提携角", f"{abs(rest['theta2']):.3f}°，前臂向外"),
        ("θ1 范围", f"{ranges['theta1']['min']:.3f}° ～ {ranges['theta1']['max']:.3f}°"),
        ("θ2 范围", f"{ranges['theta2']['min']:.3f}° ～ {ranges['theta2']['max']:.3f}°"),
        ("采样", "41 帧 0→1→0，无 Physics"),
    ]
    draw.text((x, y), "V2 数值合同", font=FONT_SECTION, fill=(25, 25, 25))
    y += 40
    for label, value in lines:
        draw.text((x, y), label, font=FONT_SMALL, fill=(85, 85, 85))
        draw.text((x + 112, y), value, font=FONT_SMALL, fill=(20, 20, 20))
        y += 30
    y += 12
    draw.text((x, y), "本次修正", font=FONT_BODY, fill=(190, 45, 50))
    y += 32
    notices = [
        "• 灰虚线：被否决的肩—腕直杆方向。",
        "• 绿色线：肘高可见皮肤横截面。",
        "• 红线：修正后的两段固定骨骼。",
        "• 蓝圈：覆盖搜索用关节盘，不是材料。",
        "• 尚未生成纯色材料、纹理或 Cubism。",
    ]
    for line in notices:
        draw.text((x, y), line, font=FONT_SMALL, fill=(45, 45, 45))
        y += 28


def main():
    line = Image.open(LINE_PATH).convert("RGB")
    color = Image.open(COLOR_PATH).convert("RGB")
    if line.size != (512, 1086) or color.size != (512, 1086):
        raise ValueError("authoritative front masters must remain 512x1086")

    canvas = Image.new("RGB", (1580, 1100), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((35, 20), "小星｜画面右侧手臂：阶段 A 骨架修正审查 V2", font=FONT_TITLE, fill=(20, 20, 20))
    draw.text(
        (35, 62),
        "审查图，不是材料｜灰虚线：肩腕直线｜绿线：肘部横截面｜红线：修正骨段",
        font=FONT_BODY,
        fill=(85, 85, 85),
    )

    paste_panel(canvas, make_full_panel(line), (35, 130), "正面线稿定位")
    paste_panel(canvas, make_crop_panel(line), (430, 130), "线稿近看 200%（最近邻）")
    paste_panel(canvas, make_crop_panel(color), (840, 130), "彩稿近看 200%（仅身份／材质参照）")
    draw_text_block(draw, 1245, 130)

    draw.text(
        (35, 1062),
        "待审：肘点是否位于体积中心、折角是否符合人体自然下垂、肩腕推断是否仍需调整。",
        font=FONT_BODY,
        fill=(20, 20, 20),
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUTPUT_PATH)
    print(OUTPUT_PATH.relative_to(PACKAGE).as_posix())


if __name__ == "__main__":
    main()
