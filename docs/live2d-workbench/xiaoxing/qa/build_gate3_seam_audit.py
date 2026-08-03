from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
MASTERS = ROOT / "source" / "masters"
QA = ROOT / "qa"
AUDIT = ROOT / "audit"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


PANELS = [
    ("头部／发根／眼睛", (110, 20, 405, 245), "检查：头发分组、完整脸底和眼睛材料层"),
    ("肩部／袖子／上臂", (75, 205, 440, 445), "检查：衣身在袖缝处结束，袖子与上臂独立"),
    ("衣服印花／腰部／裙子", (110, 390, 405, 700), "检查：印花独立；裙子分前后层和褶皱组"),
    ("双手／手链", (50, 500, 462, 660), "检查：手部分层贴合原图，手链独立"),
    ("膝盖／袜口", (175, 700, 350, 1005), "检查：腿部在袜口下保持连续，不出现断层"),
    ("鞋子／鞋底", (145, 940, 390, 1085), "检查：鞋面、鞋底和鞋跟的遮挡连续性"),
]


def main():
    color = Image.open(MASTERS / "gate3-color-target-v1.png").convert("RGB")
    line = Image.open(MASTERS / "gate3-line-master-candidate-v1.png").convert("RGB")
    board = Image.new("RGB", (1500, 1250), "white")
    draw = ImageDraw.Draw(board)
    draw.text((28, 16), "小星 Gate 3 接缝审查（统一母稿坐标）", fill=(25, 25, 25), font=font(26))
    draw.text((28, 54), "左：彩色目标　｜　右：线稿候选　｜　所有裁剪均为 512×1086 母稿坐标，未缩放、未平移", fill=(80, 80, 80), font=font(16))

    panel_w, panel_h = 680, 340
    for index, (title, box, conclusion) in enumerate(PANELS):
        row, col = divmod(index, 2)
        x, y = 28 + col * 735, 88 + row * 385
        crop_color = color.crop(box)
        crop_line = line.crop(box)
        scale = min(((panel_w - 40) / 2) / crop_color.width, (panel_h - 85) / crop_color.height)
        size = (round(crop_color.width * scale), round(crop_color.height * scale))
        crop_color = crop_color.resize(size, Image.Resampling.LANCZOS)
        crop_line = crop_line.resize(size, Image.Resampling.LANCZOS)
        draw.rectangle((x, y, x + panel_w, y + panel_h), fill=(248, 249, 251), outline=(205, 210, 218), width=2)
        draw.text((x + 10, y + 8), f"{index + 1:02d}  {title}", fill=(35, 35, 35), font=font(17))
        draw.text((x + panel_w - 150, y + 10), f"母稿区域 {box[2]-box[0]}×{box[3]-box[1]}", fill=(95, 95, 95), font=font(12))
        left_x, top = x + 10, y + 38
        right_x = x + 350
        draw.bitmap((left_x, top), ImageOps.grayscale(crop_color), fill=None)
        board.paste(crop_color, (left_x, top))
        board.paste(crop_line, (right_x, top))
        draw.rectangle((left_x, top, left_x + size[0], top + size[1]), outline=(180, 185, 192), width=1)
        draw.rectangle((right_x, top, right_x + size[0], top + size[1]), outline=(180, 185, 192), width=1)
        draw.text((left_x + 6, top + 5), "彩色原图", fill=(35, 35, 35), font=font(12), stroke_width=2, stroke_fill="white")
        draw.text((right_x + 6, top + 5), "线稿", fill=(35, 35, 35), font=font(12), stroke_width=2, stroke_fill="white")
        draw.text((x + 10, y + panel_h - 29), conclusion, fill=(75, 75, 75), font=font(14))

    board.save(QA / "gate3-seam-audit.png", quality=95)
    report = {
        "coordinateSystem": "512x1086 source master",
        "transform": {"scale": 1.0, "translation": [0, 0]},
        "panels": [{"title": title, "box": list(box), "check": conclusion} for title, box, conclusion in PANELS],
        "status": "visual_review_required",
        "note": "This is a registered seam audit, not a production alpha-mask export.",
    }
    (AUDIT / "gate3-seam-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
