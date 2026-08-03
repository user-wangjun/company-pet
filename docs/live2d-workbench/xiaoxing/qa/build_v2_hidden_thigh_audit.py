from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
THREE = ROOT / "source" / "xiaoxing-three-view-line.png"
CONTRACT = ROOT / "blueprints" / "v2-hidden-thigh-contract.json"
OUT = ROOT / "qa" / "v2-hidden-thigh-lineart-audit.png"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def map_points(points, crop, origin, scale):
    return [((x - crop[0]) * scale + origin[0], (y - crop[1]) * scale + origin[1]) for x, y in points]


def dashed(draw, points, fill, width=4, dash=12):
    for a, b in zip(points, points[1:]):
        x0, y0 = a
        x1, y1 = b
        length = max(abs(x1-x0), abs(y1-y0))
        if length == 0:
            continue
        steps = max(1, int(length // dash))
        for i in range(0, steps, 2):
            t0 = i / steps
            t1 = min(1, (i + 1) / steps)
            draw.line((x0+(x1-x0)*t0, y0+(y1-y0)*t0, x0+(x1-x0)*t1, y0+(y1-y0)*t1), fill=fill, width=width)


def main():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    front = Image.open(FRONT).convert("RGB")
    three = Image.open(THREE).convert("RGB")
    board = Image.new("RGB", (1240, 930), "white")
    d = ImageDraw.Draw(board)
    d.text((28, 20), "小星 V2｜裙内隐藏大腿连续性审查（不导出素材）", fill=(25, 28, 35), font=font(28))
    d.text((28, 62), "青色虚线/色块：被裙子遮住、但腿层必须继续存在的部分。侧视图只用于证明体积，不复制像素。", fill=(45, 110, 150), font=font(16))

    front_crop = tuple(data["frontReviewCrop"])
    front_raw = front.crop(front_crop)
    front_scale = 2
    front_origin = (55, 125)
    board.paste(front_raw.resize((front_raw.width*front_scale, front_raw.height*front_scale), Image.Resampling.NEAREST), front_origin)
    overlay = Image.new("RGBA", board.size, (0,0,0,0))
    od = ImageDraw.Draw(overlay)
    for item in data["frontHiddenCandidates"]:
        pts = map_points(item["polygon"], front_crop, front_origin, front_scale)
        od.polygon(pts, fill=(30, 180, 210, 75), outline=(20, 135, 165, 230))
        dashed(od, pts + [pts[0]], (15, 120, 155, 255), width=4, dash=14)
    board.paste(overlay.convert("RGB"), (0,0), overlay)
    d = ImageDraw.Draw(board)
    d.text((55, 845), "正面：隐藏部分只在裙层下方延伸，并与可见腿连续重叠。", fill=(55, 70, 85), font=font(15))

    side_crop = tuple(data["sideReviewCrop"])
    side_raw = three.crop(side_crop)
    side_scale = 2
    side_origin = (700, 125)
    board.paste(side_raw.resize((side_raw.width*side_scale, side_raw.height*side_scale), Image.Resampling.NEAREST), side_origin)
    d = ImageDraw.Draw(board)
    ev = data["sideEvidence"]
    for name in ("frontContourCandidate", "backContourCandidate"):
        pts = map_points(ev[name], side_crop, side_origin, side_scale)
        dashed(d, pts, (20, 140, 175), width=5, dash=14)
        for x, y in pts:
            d.ellipse((x-6,y-6,x+6,y+6), fill=(255,190,50), outline=(100,55,25), width=2)
    d.text((700, 845), "侧面：裙内大腿向上连续；不从侧视图拷贝形状到正面。", fill=(55, 70, 85), font=font(15))
    d.text((28, 890), "通过条件：无断腿、无圆形补丁、隐藏区位于裙下、正面与侧面体积逻辑一致。", fill=(175, 55, 45), font=font(16))
    board.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
