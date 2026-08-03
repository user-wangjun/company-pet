from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
OUT = ROOT / "qa" / "gate3-hand-coordinate-grid.png"


def font(size):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", size)
    except OSError:
        return ImageFont.load_default()


def draw_panel(canvas, image, box, left, top, title):
    scale = 5
    x1, y1, x2, y2 = box
    crop = image.crop(box).resize(((x2 - x1) * scale, (y2 - y1) * scale))
    canvas.paste(crop, (left, top))
    d = ImageDraw.Draw(canvas, "RGBA")
    d.rectangle((left, top, left + crop.width, top + crop.height), outline=(25, 25, 25, 230), width=2)
    d.text((left + 8, top + 8), title, fill=(25, 25, 25), font=font(17), stroke_width=2, stroke_fill="white")
    for gx in range(x1, x2 + 1, 10):
        px = left + (gx - x1) * scale
        d.line((px, top, px, top + crop.height), fill=(20, 120, 230, 90), width=1)
        d.text((px + 2, top + crop.height - 21), str(gx), fill=(20, 90, 175), font=font(12), stroke_width=1, stroke_fill="white")
    for gy in range(y1, y2 + 1, 10):
        py = top + (gy - y1) * scale
        d.line((left, py, left + crop.width, py), fill=(20, 120, 230, 90), width=1)
        d.text((left + 2, py + 1), str(gy), fill=(20, 90, 175), font=font(12), stroke_width=1, stroke_fill="white")


def main():
    image = Image.open(SOURCE).convert("RGB")
    canvas = Image.new("RGB", (1100, 820), "white")
    d = ImageDraw.Draw(canvas)
    d.text((20, 16), "小星手部轮廓坐标审阅（来源：line master）", fill=(25, 25, 25), font=font(22))
    draw_panel(canvas, image, (55, 500, 155, 650), 35, 60, "character R / viewer left")
    draw_panel(canvas, image, (355, 500, 455, 650), 565, 60, "character L / viewer right")
    d.text((20, 790), "Use source-master coordinates when describing missed or over-covered pixels.", fill=(70, 70, 70), font=font(15))
    canvas.save(OUT, quality=95)


if __name__ == "__main__":
    main()

