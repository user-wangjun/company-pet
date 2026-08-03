from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
MASTERS = ROOT / "source" / "masters"
QA = ROOT / "qa"
BLUEPRINTS = ROOT / "blueprints"


def font(size):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)
    except OSError:
        return ImageFont.load_default()


EYES = {
    "R": {
        "label": "角色右眼（画面左侧）",
        "crop": (205, 100, 260, 158),
        "outerCorner": (216, 130),
        "innerCorner": (243, 130),
        "upperApex": (233, 124),
        "lowerApex": (233, 139),
        "irisCenter": (234, 132),
        "irisRadius": 9,
    },
    "L": {
        "label": "角色左眼（画面右侧）",
        "crop": (263, 100, 318, 158),
        "innerCorner": (266, 130),
        "outerCorner": (296, 130),
        "upperApex": (280, 124),
        "lowerApex": (280, 139),
        "irisCenter": (278, 132),
        "irisRadius": 9,
    },
}


def draw_eye_panel(board, source, eye, x0, y0, scale=8):
    crop_box = eye["crop"]
    crop = source.crop(crop_box).resize(((crop_box[2] - crop_box[0]) * scale, (crop_box[3] - crop_box[1]) * scale), Image.Resampling.NEAREST)
    board.paste(crop, (x0, y0))
    draw = ImageDraw.Draw(board, "RGBA")
    draw.rectangle((x0, y0, x0 + crop.width, y0 + crop.height), outline=(175, 180, 190, 255), width=2)
    for gx in range(crop_box[0], crop_box[2] + 1, 5):
        px = x0 + (gx - crop_box[0]) * scale
        draw.line((px, y0, px, y0 + crop.height), fill=(55, 135, 215, 80), width=1)
        draw.text((px + 2, y0 + 2), str(gx), fill=(35, 95, 165, 190), font=font(10))
    for gy in range(crop_box[1], crop_box[3] + 1, 5):
        py = y0 + (gy - crop_box[1]) * scale
        draw.line((x0, py, x0 + crop.width, py), fill=(55, 135, 215, 80), width=1)
        draw.text((x0 + 2, py + 1), str(gy), fill=(35, 95, 165, 190), font=font(10))
    colors = {
        "outerCorner": (230, 70, 60, 230),
        "innerCorner": (230, 70, 60, 230),
        "upperApex": (45, 150, 90, 230),
        "lowerApex": (45, 150, 90, 230),
        "irisCenter": (155, 70, 185, 230),
    }
    for name, color in colors.items():
        sx, sy = eye[name]
        px = x0 + (sx - crop_box[0]) * scale
        py = y0 + (sy - crop_box[1]) * scale
        draw.ellipse((px - 7, py - 7, px + 7, py + 7), fill=color, outline=(255, 255, 255, 240), width=2)


def main():
    color = Image.open(MASTERS / "gate3-color-target-v1.png").convert("RGB")
    line = Image.open(MASTERS / "gate3-line-master-candidate-v1.png").convert("RGB")
    board = Image.new("RGB", (1840, 1080), "white")
    draw = ImageDraw.Draw(board)
    draw.text((24, 16), "小星 Gate 4 双眼坐标预检（原图像素 ×8）", fill=(25, 25, 25), font=font(26))
    draw.text((24, 54), "红：内外眼角　绿：上下眼睑最高／最低点　紫：虹膜中心。网格数字为 512×1086 母稿坐标。", fill=(75, 75, 75), font=font(16))
    for row, side in enumerate(("R", "L")):
        eye = EYES[side]
        y = 105 + row * 485
        draw.text((24, y - 30), eye["label"], fill=(35, 85, 135), font=font(20))
        draw.text((24, y), "彩色原图", fill=(45, 45, 45), font=font(15))
        draw_eye_panel(board, color, eye, 24, y + 25)
        draw.text((950, y), "线稿与坐标点", fill=(45, 45, 45), font=font(15))
        draw_eye_panel(board, line, eye, 950, y + 25)
    draw.text((24, 1040), "本图只锁定眼睛材料坐标，不改变原画；正式眨眼将由上下眼睑和眼白遮罩共同完成。", fill=(35, 85, 135), font=font(16))
    board.save(QA / "gate4-eye-landmark-preflight.png", quality=95)
    contract = {
        "stage": "gate4-eye-preflight",
        "status": "landmarks_pending_visual_qc",
        "coordinateSystem": "512x1086 source master",
        "eyes": EYES,
        "requiredMaterialsPerEye": ["socket", "sclera", "iris", "pupil", "highlight", "upper_lid", "lower_lid", "mask"],
        "rules": [
            "iris and pupil move together inside the eye-opening mask",
            "highlight follows the iris with reduced translation",
            "blink is lid deformation, not opacity-only hiding",
            "closed eye must preserve a clean lash line and no visible sclera leak",
        ],
    }
    (BLUEPRINTS / "gate4-eye-preflight-contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
