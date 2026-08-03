from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main():
    box = (190, 112, 325, 170)
    scale = 6
    crop = Image.open(LINE).convert("RGB").crop(box).resize(((box[2] - box[0]) * scale, (box[3] - box[1]) * scale), Image.Resampling.NEAREST)
    d = ImageDraw.Draw(crop)
    for x in range(box[0], box[2] + 1, 5):
        xx = (x - box[0]) * scale
        d.line((xx, 0, xx, crop.height), fill=(65, 130, 220), width=1)
        d.text((xx + 2, 4), str(x), fill=(25, 75, 145), font=font(13), stroke_width=1, stroke_fill="white")
    for y in range(box[1], box[3] + 1, 5):
        yy = (y - box[1]) * scale
        d.line((0, yy, crop.width, yy), fill=(65, 130, 220), width=1)
        d.text((3, yy + 2), str(y), fill=(25, 75, 145), font=font(13), stroke_width=1, stroke_fill="white")
    board = Image.new("RGB", (crop.width + 48, crop.height + 100), "white")
    bd = ImageDraw.Draw(board)
    bd.text((18, 14), "V2 线稿双眼原始坐标网格（每小格 5px，整数放大 6 倍）", fill=(25, 25, 30), font=font(22))
    board.paste(crop, (24, 65))
    bd.text((24, board.height - 28), "只用于人工读坐标；不等于已批准的眼睛遮罩。", fill=(150, 50, 45), font=font(16))
    out = ROOT / "qa" / "v2-eye-coordinate-grid.png"
    board.save(out, quality=95)
    print(out)


if __name__ == "__main__":
    main()
