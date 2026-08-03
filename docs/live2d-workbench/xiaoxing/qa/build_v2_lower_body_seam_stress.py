from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
LAYERS = ROOT / "qa" / "v2-lower-body-candidate-layers"
OUT = ROOT / "qa" / "v2-lower-body-seam-stress.png"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def shifted(layer, dx=0, dy=0):
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(layer, (dx, dy))
    return out


def pose(skirt_dy=0, left_dx=0, right_dx=0):
    canvas = Image.new("RGBA", (512, 1086), (255, 105, 115, 255))
    order = [
        ("leg_screen_left", left_dx, 0),
        ("leg_screen_right", right_dx, 0),
        ("skirt", 0, skirt_dy),
        ("sock_screen_left", left_dx, 0),
        ("sock_screen_right", right_dx, 0),
        ("shoe_screen_left", left_dx, 0),
        ("shoe_screen_right", right_dx, 0),
    ]
    for name, dx, dy in order:
        canvas.alpha_composite(shifted(Image.open(LAYERS / f"{name}.png").convert("RGBA"), dx, dy))
    return canvas


def main():
    cases = [
        ("基准姿态", 0, 0, 0),
        ("裙子上移 8px", -8, 0, 0),
        ("裙子下移 8px", 8, 0, 0),
        ("双腿左右各移 3px", 0, -3, 3),
    ]
    board = Image.new("RGB", (1100, 820), "white")
    d = ImageDraw.Draw(board)
    d.text((24, 18), "小星 V2｜下半身接缝压力审查（候选层）", fill=(25, 28, 35), font=font(28))
    d.text((24, 57), "只模拟小幅位移，不代表最终参数；红底用于暴露透明露白或断层。", fill=(175, 55, 45), font=font(16))
    positions = [(25, 105), (285, 105), (545, 105), (805, 105)]
    crop = (110, 540, 400, 1065)
    for (label, skirt_dy, left_dx, right_dx), (x, y) in zip(cases, positions):
        image = pose(skirt_dy, left_dx, right_dx).crop(crop)
        shown = image.resize((230, 420), Image.Resampling.NEAREST)
        board.paste(shown.convert("RGB"), (x, y))
        d.text((x, y + 430), label, fill=(35, 40, 50), font=font(16))
        d.text((x, y + 457), "检查：裙下、袜口、鞋口", fill=(80, 80, 90), font=font(13))
    d.text((24, 775), "候选层规则：裙子在腿上方；袜子与鞋口少量重叠；整腿含裙内隐藏延伸。", fill=(55, 80, 125), font=font(15))
    board.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
