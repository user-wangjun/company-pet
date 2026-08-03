from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
CONTRACT = ROOT / "blueprints" / "v2-body-seam-contract.json"
OUT = ROOT / "qa" / "v2-body-lineart-seam-audit.png"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw_panel(board, source, seam, x, y, width=560, height=310):
    draw = ImageDraw.Draw(board)
    crop = tuple(seam["crop"])
    raw = source.crop(crop)
    usable_w, usable_h = width - 28, height - 88
    scale = max(1, min(usable_w // raw.width, usable_h // raw.height))
    shown = raw.resize((raw.width * scale, raw.height * scale), Image.Resampling.NEAREST)
    ox = x + (width - shown.width) // 2
    oy = y + 55
    board.paste(shown, (ox, oy))
    draw.rounded_rectangle((x, y, x + width, y + height), radius=12, outline=(190, 195, 205), width=2)
    draw.text((x + 14, y + 10), seam["label"], fill=(30, 35, 45), font=font(20))
    draw.text((x + 14, y + 36), "红线：线稿中的图层交界候选", fill=(180, 55, 45), font=font(14))

    polylines = seam.get("polylines") or [seam["polyline"]]
    for polyline in polylines:
        points = [((px - crop[0]) * scale + ox, (py - crop[1]) * scale + oy) for px, py in polyline]
        draw.line(points, fill=(220, 45, 45), width=max(3, scale // 2), joint="curve")
        for px, py in points:
            r = max(3, scale // 2)
            draw.ellipse((px-r, py-r, px+r, py+r), fill=(255, 190, 50), outline=(120, 55, 25), width=1)

    note = seam["hiddenWork"]
    draw.text((x + 14, y + height - 31), f"后续：{note}", fill=(75, 75, 85), font=font(13))


def main():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = Image.open(LINE).convert("RGB")
    board = Image.new("RGB", (1200, 1440), "white")
    draw = ImageDraw.Draw(board)
    draw.text((28, 20), "小星 V2｜全身线稿接缝审查（不生成遮罩）", fill=(25, 28, 35), font=font(28))
    draw.text((28, 62), "用途：确认相邻图层在哪里交界。红线不是切图范围；每张近景保持原线稿比例，只做整数放大。", fill=(155, 45, 40), font=font(16))
    draw.text((28, 90), "左右一律按画面方向命名；手部每侧保持一整层，不拆手指。", fill=(55, 80, 125), font=font(16))

    positions = [(25, 125), (615, 125), (25, 455), (615, 455), (25, 785), (615, 785), (25, 1115), (615, 1115)]
    for seam, (x, y) in zip(contract["seams"], positions):
        draw_panel(board, source, seam, x, y)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    board.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
