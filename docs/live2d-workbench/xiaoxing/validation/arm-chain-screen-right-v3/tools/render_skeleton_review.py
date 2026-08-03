from __future__ import annotations

import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(__file__).resolve().parents[3]
SKELETON = json.loads((ROOT / "skeleton.json").read_text(encoding="utf-8"))
EVIDENCE = json.loads((ROOT / "audit/elbow-height-evidence.json").read_text(encoding="utf-8"))
LINE_PATH = PACKAGE / "source/masters/front-line-source-exact-after-reset.png"
COLOR_PATH = PACKAGE / "source/masters/front-color-source-exact-after-reset.png"
OUTPUT_PATH = ROOT / "qa/skeleton-design-review-v3.png"


def font(size, bold=False):
    name = "msyhbd.ttc" if bold else "msyh.ttc"
    for candidate in (Path(os.environ.get("WINDIR", "")) / "Fonts" / name, Path(name)):
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            pass
    return ImageFont.load_default()


FONT_TITLE = font(30, True)
FONT_SECTION = font(22, True)
FONT_BODY = font(18)
FONT_SMALL = font(15)


def xy(name):
    p = SKELETON["landmarks"][name]
    return float(p["x"]), float(p["y"])


PS, PE, PW = xy("shoulder"), xy("elbow"), xy("wrist")
OLD_ELBOW = (357.0, 425.0)


def dashed_line(draw, start, end, fill, width=3, dash=12, gap=8):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    cursor = 0.0
    while cursor < length:
        stop = min(cursor + dash, length)
        draw.line(
            [(start[0] + ux * cursor, start[1] + uy * cursor),
             (start[0] + ux * stop, start[1] + uy * stop)],
            fill=fill,
            width=width,
        )
        cursor += dash + gap


def draw_skeleton(draw, transform, width=6):
    ps, pe, pw = transform(PS), transform(PE), transform(PW)
    old = transform(OLD_ELBOW)
    scale = transform((PS[0] + 1, PS[1]))[0] - transform(PS)[0]

    dashed_line(draw, ps, pw, (125, 125, 125, 220), max(2, width // 2))
    draw.line([ps, pe, pw], fill=(235, 63, 72, 255), width=width, joint="curve")

    scan = EVIDENCE["selectedScanline"]
    left = transform((scan["dominantSkinSpanX"][0], scan["y"]))
    right = transform((scan["dominantSkinSpanX"][1], scan["y"]))
    draw.line([left, right], fill=(0, 145, 90, 255), width=max(3, width // 2))
    for point in (left, right):
        draw.ellipse([point[0]-4, point[1]-4, point[0]+4, point[1]+4], fill=(0, 145, 90, 255))

    old_radius = 8 * scale
    draw.ellipse(
        [old[0]-old_radius, old[1]-old_radius, old[0]+old_radius, old[1]+old_radius],
        outline=(230, 126, 34, 255),
        width=max(2, width // 2),
    )
    draw.line([old, pe], fill=(230, 126, 34, 255), width=max(2, width // 2))

    radii = [
        SKELETON["jointDisksPx"]["shoulderRadius"],
        SKELETON["jointDisksPx"]["elbowRadius"],
        SKELETON["jointDisksPx"]["wristRadius"],
    ]
    for label, point, raw_radius in zip(("肩", "肘", "腕"), (ps, pe, pw), radii):
        radius = max(7, raw_radius * scale)
        draw.ellipse(
            [point[0]-radius, point[1]-radius, point[0]+radius, point[1]+radius],
            outline=(0, 117, 190, 255),
            width=max(2, width // 2),
        )
        draw.ellipse([point[0]-5, point[1]-5, point[0]+5, point[1]+5], fill=(0, 117, 190, 255))
        draw.text((point[0]+radius+5, point[1]-13), label, font=FONT_BODY, fill=(0, 117, 190, 255))


def make_full(source):
    scale = 0.72
    panel = source.convert("RGBA").resize(
        (round(source.width * scale), round(source.height * scale)),
        Image.Resampling.LANCZOS,
    )
    overlay = Image.new("RGBA", panel.size, (0, 0, 0, 0))
    draw_skeleton(ImageDraw.Draw(overlay), lambda p: (p[0]*scale, p[1]*scale), 5)
    return Image.alpha_composite(panel, overlay).convert("RGB")


def make_crop(source):
    box, scale = (280, 220, 472, 690), 2
    panel = source.crop(box).convert("RGBA").resize(
        ((box[2]-box[0])*scale, (box[3]-box[1])*scale),
        Image.Resampling.NEAREST,
    )
    overlay = Image.new("RGBA", panel.size, (0, 0, 0, 0))
    draw_skeleton(
        ImageDraw.Draw(overlay),
        lambda p: ((p[0]-box[0])*scale, (p[1]-box[1])*scale),
        7,
    )
    return Image.alpha_composite(panel, overlay).convert("RGB")


def paste_panel(canvas, image, origin, title):
    x, y = origin
    canvas.paste(image, (x, y))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([x, y, x+image.width-1, y+image.height-1], outline=(180, 180, 180), width=2)
    draw.text((x, y-34), title, font=FONT_SECTION, fill=(25, 25, 25))


def draw_text(draw, x, y):
    rest = SKELETON["restAnglesDeg"]
    ranges = SKELETON["allowedRangesDeg"]
    bones = SKELETON["boneLengthsPx"]
    lines = [
        ("状态", "V3，待用户视觉确认"),
        ("肩", "(332, 261)，袖内推断"),
        ("V3 肘", "(355, 415)"),
        ("V2 肘", "(357, 425)，已否决"),
        ("腕", "(393, 533)，手链下估计"),
        ("肘部横截面", "y=415，x=339～371"),
        ("L1", f"{bones['L1ShoulderToElbow']:.3f} px"),
        ("L2", f"{bones['L2ElbowToWrist']:.3f} px"),
        ("L1/L2", f"{bones['ratioL1ToL2']:.3f}（V2 为 1.457）"),
        ("默认折角", f"{abs(rest['theta2']):.3f}°，前臂向外"),
        ("θ1 范围", f"{ranges['theta1']['min']:.3f}° ～ {ranges['theta1']['max']:.3f}°"),
        ("θ2 范围", f"{ranges['theta2']['min']:.3f}° ～ {ranges['theta2']['max']:.3f}°"),
    ]
    draw.text((x, y), "V3 数值合同", font=FONT_SECTION, fill=(25, 25, 25))
    y += 40
    for label, value in lines:
        draw.text((x, y), label, font=FONT_SMALL, fill=(85, 85, 85))
        draw.text((x+112, y), value, font=FONT_SMALL, fill=(20, 20, 20))
        y += 30
    y += 12
    draw.text((x, y), "图例", font=FONT_BODY, fill=(190, 45, 50))
    y += 32
    for item in [
        "• 橙圈：V2 偏低肘点；箭头指向 V3。",
        "• 绿线：V3 肘高的可见皮肤横截面。",
        "• 红线：V3 两段固定骨骼。",
        "• 灰虚线：肩—腕直线对照。",
        "• 蓝圈：覆盖搜索范围，不是材料。",
    ]:
        draw.text((x, y), item, font=FONT_SMALL, fill=(45, 45, 45))
        y += 28


def main():
    line = Image.open(LINE_PATH).convert("RGB")
    color = Image.open(COLOR_PATH).convert("RGB")
    if line.size != (512, 1086) or color.size != (512, 1086):
        raise ValueError("authoritative front masters must remain 512x1086")

    canvas = Image.new("RGB", (1580, 1100), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((35, 20), "小星｜画面右侧手臂：阶段 A 肘高修正审查 V3", font=FONT_TITLE, fill=(20, 20, 20))
    draw.text(
        (35, 62),
        "审查图，不是材料｜橙圈：V2 旧肘点｜绿线：V3 肘高横截面｜红线：V3 骨段",
        font=FONT_BODY,
        fill=(85, 85, 85),
    )
    paste_panel(canvas, make_full(line), (35, 130), "正面线稿定位")
    paste_panel(canvas, make_crop(line), (430, 130), "线稿近看 200%（最近邻）")
    paste_panel(canvas, make_crop(color), (840, 130), "彩稿近看 200%（仅身份／材质参照）")
    draw_text(draw, 1245, 130)
    draw.text(
        (35, 1062),
        "待审：V3 肘高是否符合人体比例，肘折角是否自然，肩腕遮挡推断是否仍需调整。",
        font=FONT_BODY,
        fill=(20, 20, 20),
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUTPUT_PATH)
    print(OUTPUT_PATH.relative_to(PACKAGE).as_posix())


if __name__ == "__main__":
    main()
