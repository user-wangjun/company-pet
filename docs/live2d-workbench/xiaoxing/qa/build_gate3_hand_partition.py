from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_gate3_blueprint import HAND_CENTERLINES


ROOT = Path(__file__).resolve().parents[1]
MASTERS = ROOT / "source" / "masters"
QA = ROOT / "qa"
AUDIT = ROOT / "audit"


def font(size):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)
    except OSError:
        return ImageFont.load_default()


def skin_candidate(rgb):
    r, g, b = rgb
    return r > 150 and g > 120 and b > 105 and 5 < (r - g) < 75 and 0 <= (g - b) < 50 and (r - b) > 10


def largest_component_mask(image, bbox):
    x1, y1, x2, y2 = bbox
    candidates = set()
    for y in range(y1, y2):
        for x in range(x1, x2):
            if skin_candidate(image.getpixel((x, y))):
                candidates.add((x, y))
    components = []
    while candidates:
        start = next(iter(candidates))
        candidates.remove(start)
        queue = deque([start])
        component = {start}
        while queue:
            x, y = queue.popleft()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in candidates:
                    candidates.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        components.append(component)
    largest = max(components, key=len)
    mask = Image.new("1", image.size, 0)
    pix = mask.load()
    for x, y in largest:
        pix[x, y] = 1
    return mask


def count(mask):
    return mask.convert("L").histogram()[255]


def point_segment_distance_sq(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return (px - ax) ** 2 + (py - ay) ** 2
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    qx, qy = ax + t * dx, ay + t * dy
    return (px - qx) ** 2 + (py - qy) ** 2


def polyline_distance_sq(px, py, points):
    return min(point_segment_distance_sq(px, py, a, b) for a, b in zip(points, points[1:]))


def partition(color, side, bbox):
    skin = largest_component_mask(color, bbox)
    names = ("thumb", "index", "middle", "ring", "little")
    parts = {name: Image.new("1", color.size, 0) for name in ("palm", *names)}
    skin_pixels = skin.load()
    part_pixels = {name: mask.load() for name, mask in parts.items()}
    x1, y1, x2, y2 = bbox
    root_y = 573
    for y in range(y1, y2):
        for x in range(x1, x2):
            if not skin_pixels[x, y]:
                continue
            if y < root_y:
                owner = "palm"
            else:
                owner = min(names, key=lambda name: polyline_distance_sq(x, y, HAND_CENTERLINES[side][name]))
            part_pixels[owner][x, y] = 1
    return {"skin": skin, **parts}


def render_overlay(base, masks, bbox, scale=4):
    crop = base.crop(bbox).convert("RGBA").resize(((bbox[2] - bbox[0]) * scale, (bbox[3] - bbox[1]) * scale))
    colors = {
        "palm": (245, 130, 35, 110),
        "thumb": (225, 65, 45, 150),
        "index": (45, 120, 220, 145),
        "middle": (45, 160, 90, 145),
        "ring": (175, 65, 185, 145),
        "little": (235, 185, 35, 155),
    }
    for name in ("palm", "thumb", "index", "middle", "ring", "little"):
        local = masks[name].crop(bbox).resize(crop.size)
        layer = Image.new("RGBA", crop.size, colors[name])
        alpha = local.convert("L").point(lambda p: colors[name][3] if p else 0)
        layer.putalpha(alpha)
        crop = Image.alpha_composite(crop, layer)
    return crop.convert("RGB")


def main():
    color = Image.open(MASTERS / "gate3-color-target-v1.png").convert("RGB")
    line = Image.open(MASTERS / "gate3-line-master-candidate-v1.png").convert("RGB")
    specs = {"R": (65, 545, 140, 635), "L": (372, 545, 445, 635)}
    results = {side: partition(color, side, bbox) for side, bbox in specs.items()}
    metrics = {}
    for side, masks in results.items():
        skin = count(masks["skin"])
        parts = {name: count(masks[name]) for name in ("palm", "thumb", "index", "middle", "ring", "little")}
        metrics[side] = {
            "skinPixels": skin,
            "partPixels": parts,
            "partitionPixels": sum(parts.values()),
            "uncoveredPixels": skin - sum(parts.values()),
            "overlapPixels": 0,
            "coverageRatio": sum(parts.values()) / skin,
            "bbox": specs[side],
            "coordinateSystem": "512x1086 source master",
        }

    board = Image.new("RGB", (1320, 620), "white")
    draw = ImageDraw.Draw(board)
    draw.text((24, 16), "小星手部分层审查（像素对齐版）", fill=(30, 30, 30), font=font(24))
    panels = []
    for side in ("R", "L"):
        bbox = specs[side]
        side_name = "角色右手（画面左侧）" if side == "R" else "角色左手（画面右侧）"
        panels.append((f"{side_name}－彩色原图", color.crop(bbox).resize(((bbox[2] - bbox[0]) * 4, (bbox[3] - bbox[1]) * 4))))
        panels.append((f"{side_name}－线稿与分层", render_overlay(line, results[side], bbox)))
    for i, (title, panel) in enumerate(panels):
        x = 20 + i * 325
        y = 65
        board.paste(panel, (x, y))
        draw.rectangle((x, y, x + panel.width, y + panel.height), outline=(185, 190, 198), width=2)
        draw.text((x + 8, y + 8), title, fill=(35, 35, 35), font=font(15), stroke_width=2, stroke_fill="white")
    draw.text((24, 445), "颜色说明：橙＝掌心和腕根　红＝拇指　蓝＝食指　绿＝中指　紫＝无名指　黄＝小指", fill=(65, 65, 65), font=font(17))
    draw.text((24, 478), f"像素检查：右手覆盖 {metrics['R']['coverageRatio']:.0%}、漏盖 {metrics['R']['uncoveredPixels']}、重叠 {metrics['R']['overlapPixels']}　｜　左手覆盖 {metrics['L']['coverageRatio']:.0%}、漏盖 {metrics['L']['uncoveredPixels']}、重叠 {metrics['L']['overlapPixels']}", fill=(65, 65, 65), font=font(16))
    draw.text((24, 511), "所有颜色都被裁切在各自手部的真实皮肤轮廓内，不再使用矩形框。", fill=(65, 65, 65), font=font(16))
    draw.text((24, 548), "你需要判断：六种颜色是否各自落在正确部位；特别检查拇指和小指是否被其他颜色侵入。", fill=(35, 85, 135), font=font(17))
    draw.text((24, 582), "说明：这张图检查的是分层归属，不代表手已经绑定或开始运动。", fill=(90, 90, 90), font=font(15))
    board.save(QA / "gate3-hand-pixel-alignment-qa.png", quality=95)
    (AUDIT / "gate3-hand-pixel-alignment.json").write_text(json.dumps({"status": "visual_review_required", "metrics": metrics}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
