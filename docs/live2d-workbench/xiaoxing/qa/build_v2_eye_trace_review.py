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


def pts(points, box, scale, origin):
    return [((x - box[0]) * scale + origin[0], (y - box[1]) * scale + origin[1]) for x, y in points]


def main():
    box = (190, 115, 320, 160)
    scale = 8
    origin = (30, 105)
    image = Image.open(LINE).convert("RGB").crop(box).resize(((box[2] - box[0]) * scale, (box[3] - box[1]) * scale), Image.Resampling.NEAREST)
    board = Image.new("RGB", (1110, 540), "white")
    board.paste(image, origin)
    d = ImageDraw.Draw(board)
    d.text((24, 18), "V2 双眼线稿候选描边复核（不导出素材）", fill=(25, 25, 30), font=font(25))
    d.text((24, 55), "青线=沿线稿的候选曲线；圆点=候选地标。若线稿仍有歧义，保留待复核，不生成眼睛层。", fill=(150, 50, 45), font=font(16))
    traces = {
        "R": {
            "upper": [(205, 130), (210, 125), (218, 122), (228, 124), (236, 129), (240, 131)],
            "lower": [(205, 133), (214, 138), (223, 141), (233, 138), (240, 133)],
            "landmarks": {"外眼角": (205, 132), "内眼角": (240, 132), "上峰": (218, 122), "下峰": (223, 141), "虹膜候选中心": (222, 131)},
        },
        "L": {
            "upper": [(265, 132), (271, 126), (278, 122), (285, 124), (292, 129), (294, 132)],
            "lower": [(265, 134), (273, 140), (280, 142), (288, 139), (293, 135), (294, 132)],
            "landmarks": {"内眼角": (265, 133), "外眼角": (294, 133), "上峰": (278, 122), "下峰": (280, 142), "虹膜候选中心": (280, 130)},
        },
    }
    colors = {"R": (25, 160, 190), "L": (180, 75, 170)}
    for side, data in traces.items():
        col = colors[side]
        d.line(pts(data["upper"], box, scale, origin), fill=col, width=5, joint="curve")
        d.line(pts(data["lower"], box, scale, origin), fill=col, width=5, joint="curve")
        for label, point in data["landmarks"].items():
            x, y = pts([point], box, scale, origin)[0]
            d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(245, 170, 45), outline=(80, 50, 20), width=2)
            d.text((x + 8, y - 10), label, fill=(60, 50, 30), font=font(14), stroke_width=2, stroke_fill="white")
    d.text((35, 470), "画面左眼（角色自身右眼）", fill=colors["R"], font=font(16))
    d.text((540, 470), "画面右眼（角色自身左眼）", fill=colors["L"], font=font(16))
    out = ROOT / "qa" / "v2-eye-lineart-trace-review.png"
    board.save(out, quality=95)
    print(out)


if __name__ == "__main__":
    main()
