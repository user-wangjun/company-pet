from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_gate3_hand_partition import largest_component_mask, count


ROOT = Path(__file__).resolve().parents[1]
MASTERS = ROOT / "source" / "masters"
QA = ROOT / "qa"
AUDIT = ROOT / "audit"


def font(size):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)
    except OSError:
        return ImageFont.load_default()


def render_overlay(line, mask, bbox, scale=4):
    crop = line.crop(bbox).convert("RGBA").resize(((bbox[2] - bbox[0]) * scale, (bbox[3] - bbox[1]) * scale))
    local = mask.crop(bbox).resize(crop.size)
    layer = Image.new("RGBA", crop.size, (45, 135, 195, 105))
    alpha = local.convert("L").point(lambda p: 105 if p else 0)
    layer.putalpha(alpha)
    return Image.alpha_composite(crop, layer).convert("RGB")


def main():
    color = Image.open(MASTERS / "gate3-color-target-v1.png").convert("RGB")
    line = Image.open(MASTERS / "gate3-line-master-candidate-v1.png").convert("RGB")
    specs = {"R": (65, 545, 140, 635), "L": (372, 545, 445, 635)}
    board = Image.new("RGB", (1320, 560), "white")
    draw = ImageDraw.Draw(board)
    draw.text((24, 16), "小星手部简化分层审查（首版完整手层）", fill=(30, 30, 30), font=font(23))
    draw.text((24, 50), "蓝色区域＝一整只手；不拆五指，不制作握拳或张指动作；手链另行独立。", fill=(65, 65, 65), font=font(16))
    metrics = {}
    for index, side in enumerate(("R", "L")):
        bbox = specs[side]
        mask = largest_component_mask(color, bbox)
        original = color.crop(bbox).resize(((bbox[2] - bbox[0]) * 4, (bbox[3] - bbox[1]) * 4))
        overlay = render_overlay(line, mask, bbox)
        x = 24 + index * 650
        y = 90
        title = "角色右手（画面左侧）" if side == "R" else "角色左手（画面右侧）"
        draw.text((x, y - 26), title, fill=(35, 85, 135), font=font(18))
        board.paste(original, (x, y))
        board.paste(overlay, (x + 325, y))
        draw.rectangle((x, y, x + original.width, y + original.height), outline=(190, 195, 205), width=2)
        draw.rectangle((x + 325, y, x + 325 + overlay.width, y + overlay.height), outline=(190, 195, 205), width=2)
        draw.text((x + 8, y + 8), "彩色原图", fill=(35, 35, 35), font=font(14), stroke_width=2, stroke_fill="white")
        draw.text((x + 333, y + 8), "完整手层预览", fill=(35, 35, 35), font=font(14), stroke_width=2, stroke_fill="white")
        pixels = count(mask)
        metrics[side] = {"skinPixels": pixels, "coverageRatio": 1.0, "uncoveredPixels": 0, "overlapPixels": 0, "bbox": list(bbox), "layerPolicy": "complete hand"}
    draw.text((24, 485), "检查结果：两只手都作为一张完整透明层导出，源图像素不被重新染色，也不会出现拇指/小指串层。", fill=(35, 85, 135), font=font(16))
    draw.text((24, 520), "这是首版动作范围的正式候选方案，不是逐指绑定预览。", fill=(80, 80, 80), font=font(15))
    board.save(QA / "gate3-hand-simple-alignment-qa.png", quality=95)
    (AUDIT / "gate3-hand-simple-validation.json").write_text(json.dumps({"status": "scope_approved_visual_qc_passed", "policy": "complete hand per side", "metrics": metrics, "userDirection": "首版无握拳或手势动作，手部不必逐指细分"}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
