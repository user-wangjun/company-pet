from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
MASTERS = ROOT / "source" / "masters"
QA = ROOT / "qa"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def wrap(draw, text, xy, width, fill=(60, 60, 60), size=17, line_gap=6):
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = (current + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=font(size))[2] <= width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, fill=fill, font=font(size))
        y += size + line_gap
    return y


def main():
    color = Image.open(MASTERS / "gate3-color-target-v1.png").convert("RGB")
    line = Image.open(MASTERS / "gate3-line-master-candidate-v1.png").convert("RGB")
    sections = [
        ("01  face / eyes / hair roots", (145, 18, 370, 275), "Eye materials are explicit, but the face and ear areas behind the hair still require full hidden continuation."),
        ("02  shoulders / sleeves / arms", (60, 200, 450, 475), "The sleeve is a foreground garment. Shoulder root and upper arm must remain complete beneath the cuff."),
        ("03  shirt print / waist / skirt", (115, 255, 405, 680), "The butterfly print must remain a constrained sticker layer; torso, waist and pelvis stay in the hidden base."),
        ("04  hands / bracelets", (58, 500, 455, 650), "V1 hand split is palm + thumb + grouped finger fan. The source supports this grouping, not five independent finger materials."),
    ]
    row_heights = [600, 500, 830, 340]
    board = Image.new("RGB", (1600, sum(row_heights) + 80), "white")
    draw = ImageDraw.Draw(board)
    draw.text((24, 20), "小星 Gate 3 局部视觉 QA / semantic boundary review", fill=(30, 30, 30), font=font(24))
    y = 70
    for (title, box, note), row_height in zip(sections, row_heights):
        draw.rectangle((24, y, 1575, y + row_height - 12), fill=(248, 249, 251), outline=(210, 214, 220), width=2)
        draw.text((45, y + 18), title, fill=(25, 25, 25), font=font(20))
        crop_w = 540
        source_h = box[3] - box[1]
        source_w = box[2] - box[0]
        scale = crop_w / source_w
        crop_h = int(source_h * scale)
        color_crop = color.crop(box).resize((crop_w, crop_h))
        line_crop = line.crop(box).resize((crop_w, crop_h))
        img_y = y + 62
        board.paste(color_crop, (45, img_y))
        board.paste(line_crop, (625, img_y))
        draw.rectangle((45, img_y, 45 + crop_w, img_y + crop_h), outline=(190, 195, 200), width=2)
        draw.rectangle((625, img_y, 625 + crop_w, img_y + crop_h), outline=(190, 195, 200), width=2)
        draw.text((55, img_y + 8), "color target", fill=(40, 40, 40), font=font(15), stroke_width=2, stroke_fill="white")
        draw.text((635, img_y + 8), "line candidate", fill=(40, 40, 40), font=font(15), stroke_width=2, stroke_fill="white")
        wrap(draw, "审查结论： " + note, (1200, img_y + 16), 330, size=17)
        y += row_height
    board.save(QA / "gate3-detail-qa.png", quality=95)


if __name__ == "__main__":
    main()

