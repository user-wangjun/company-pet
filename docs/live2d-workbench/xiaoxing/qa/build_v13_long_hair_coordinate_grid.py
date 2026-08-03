from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
HAIR = ROOT / "model" / "working-v9" / "long-hair-shirt" / "胸前长发_原像素.png"
OUT = ROOT / "qa" / "v13-long-hair-coordinate-grid.png"
CROP = (175, 245, 335, 350)
SCALE = 6


def font(size: int):
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def main() -> None:
    source = Image.open(SOURCE).convert("RGB")
    hair_alpha = np.asarray(Image.open(HAIR).convert("RGBA"))[:, :, 3]
    x0, y0, x1, y1 = CROP
    crop = source.crop(CROP).resize(((x1 - x0) * SCALE, (y1 - y0) * SCALE), Image.Resampling.NEAREST)

    alpha_crop = hair_alpha[y0:y1, x0:x1]
    overlay = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
    overlay[:, :, :3] = (220, 30, 170)
    overlay[:, :, 3] = np.where(alpha_crop > 0, 88, 0).astype(np.uint8)
    overlay_image = Image.fromarray(overlay, "RGBA").resize(crop.size, Image.Resampling.NEAREST)
    canvas = Image.alpha_composite(crop.convert("RGBA"), overlay_image).convert("RGB")

    draw = ImageDraw.Draw(canvas)
    for x in range(x0, x1 + 1, 5):
        px = (x - x0) * SCALE
        draw.line((px, 0, px, canvas.height), fill=(0, 120, 220), width=1)
        draw.text((px + 2, 2), str(x), fill=(0, 70, 150), font=font(12))
    for y in range(y0, y1 + 1, 5):
        py = (y - y0) * SCALE
        draw.line((0, py, canvas.width, py), fill=(0, 120, 220), width=1)
        draw.text((2, py + 1), str(y), fill=(0, 70, 150), font=font(12))

    board = Image.new("RGB", (canvas.width, canvas.height + 66), "white")
    board.paste(canvas, (0, 66))
    d = ImageDraw.Draw(board)
    d.text((12, 8), "小星胸前发尾坐标网格：粉色=V9 当前头发归属；蓝线每 5px", fill="#171717", font=font(22))
    d.text((12, 38), "用途：人工排除 Savoir/蝴蝶印花误收，并保留真正连续发束。", fill="#8D251E", font=font(18))
    board.save(OUT)


if __name__ == "__main__":
    main()
