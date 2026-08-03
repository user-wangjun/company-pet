from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
COLOR = ROOT / "source" / "masters" / "gate3-color-target-v1.png"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main() -> None:
    line = Image.open(LINE).convert("RGB")
    color = Image.open(COLOR).convert("RGB")
    # One common source box, preserved exactly; nearest-neighbor is used only for inspection.
    box = (180, 95, 340, 190)
    scale = 4
    line_crop = line.crop(box).resize(((box[2] - box[0]) * scale, (box[3] - box[1]) * scale), Image.Resampling.NEAREST)
    color_crop = color.crop(box).resize(((box[2] - box[0]) * scale, (box[3] - box[1]) * scale), Image.Resampling.NEAREST)
    board = Image.new("RGB", (1320, 620), "white")
    d = ImageDraw.Draw(board)
    d.text((24, 18), "小星 V2 双眼线稿边界审查（无拉伸）", fill=(25, 25, 30), font=font(26))
    d.text((24, 56), "黑色区域是唯一的分层边界依据；彩稿只放在右侧做身份对照，不参与坐标决定。", fill=(150, 50, 45), font=font(17))
    board.paste(line_crop, (24, 110))
    board.paste(color_crop, (24 + line_crop.width + 30, 110))
    d.text((34, 120), "线稿（生产依据）", fill=(25, 55, 95), font=font(17), stroke_width=2, stroke_fill="white")
    d.text((24 + line_crop.width + 40, 120), "彩稿（仅身份参考）", fill=(25, 55, 95), font=font(17), stroke_width=2, stroke_fill="white")
    # Candidate ROIs are intentionally broad and marked as review zones, not production masks.
    rois = {
        "角色右眼（画面左）": (205, 128, 252, 160),
        "角色左眼（画面右）": (266, 128, 313, 160),
    }
    for label, roi in rois.items():
        x0, y0 = (roi[0] - box[0]) * scale + 24, (roi[1] - box[1]) * scale + 110
        x1, y1 = (roi[2] - box[0]) * scale + 24, (roi[3] - box[1]) * scale + 110
        d.rectangle((x0, y0, x1, y1), outline=(30, 120, 210), width=4)
        d.text((x0 + 6, y0 + 6), label, fill=(30, 95, 170), font=font(15), stroke_width=2, stroke_fill="white")
    d.text((24, 570), "本图只锁定审查范围；在人工确认眼角、眼裂和虹膜边界之前，不导出眼睛 PNG、不做眨眼参数。", fill=(150, 55, 45), font=font(17))
    out = ROOT / "qa" / "v2-eye-lineart-boundary-audit.png"
    board.save(out, quality=95)
    print(out)


if __name__ == "__main__":
    main()
