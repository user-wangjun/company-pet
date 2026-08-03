from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
LAYERS = ROOT / "qa" / "v2-upper-body-candidate-layers"
OUT = ROOT / "qa" / "v2-upper-body-seam-stress.png"


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


def pose(forearm_left=0, forearm_right=0, hand_left=0, hand_right=0):
    canvas = Image.new("RGBA", (512, 1086), (255, 105, 115, 255))
    order = [
        ("neck", 0), ("torso_tshirt_core", 0),
        ("sleeve_screen_left", 0), ("sleeve_screen_right", 0),
        ("arm_screen_left_forearm", forearm_left), ("arm_screen_right_forearm", forearm_right),
        ("hand_screen_left", hand_left), ("hand_screen_right", hand_right),
        ("necklace", 0),
    ]
    for name, dx in order:
        canvas.alpha_composite(shifted(Image.open(LAYERS / f"{name}.png").convert("RGBA"), dx, 0))
    return canvas


def main():
    cases = [
        ("基准姿态", 0, 0, 0, 0),
        ("前臂向外各 3px", -3, 3, -3, 3),
        ("手层向外各 3px", 0, 0, -3, 3),
        ("同侧前臂与手层错开 3px", -3, 3, 0, 0),
    ]
    board = Image.new("RGB", (1100, 820), "white")
    d = ImageDraw.Draw(board)
    d.text((24, 18), "小星 V2｜上半身接缝压力审查（候选层）", fill=(25,28,35), font=font(28))
    d.text((24, 57), "红底用于暴露透明露白；只模拟小幅位移，不代表最终参数。", fill=(175,55,45), font=font(16))
    positions = [(25,105),(285,105),(545,105),(805,105)]
    crop = (55,170,455,660)
    for (label, fl, fr, hl, hr), (x,y) in zip(cases, positions):
        image = pose(fl, fr, hl, hr).crop(crop)
        board.paste(image.resize((230,420), Image.Resampling.NEAREST).convert("RGB"), (x,y))
        d.text((x,y+430), label, fill=(35,40,50), font=font(15))
        d.text((x,y+457), "检查：袖口、腕部、手链", fill=(80,80,90), font=font(13))
    d.text((24,775), "候选层规则：袖子覆盖前臂根部；前臂与完整手层在手链处保持少量重叠。", fill=(55,80,125), font=font(15))
    board.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
