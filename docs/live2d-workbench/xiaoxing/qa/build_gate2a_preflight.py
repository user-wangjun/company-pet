from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "xiaoxing-three-view-line.png"
QA = ROOT / "qa"
BLUEPRINTS = ROOT / "blueprints"

# Coordinates are deliberately recorded in image space so every later layer can
# be registered back to the same 1448 x 1086 reference canvas.
PANELS = {
    "front": {"center": 290, "x_min": 92, "x_max": 468},
    "side": {"center": 710, "x_min": 586, "x_max": 820},
    "back": {"center": 1130, "x_min": 968, "x_max": 1296},
}

LANDMARKS = {
    "skull_top": [(290, 29), (710, 28), (1130, 29)],
    "jaw": [(290, 184), (697, 179), (1130, 184)],
    "neck_base": [(290, 231), (700, 231), (1130, 231)],
    "shoulder_L": [(214, 261), (680, 261), (1053, 261)],
    "shoulder_R": [(366, 261), (736, 261), (1207, 261)],
    "elbow_L": [(171, 425), (674, 425), (1037, 425)],
    "elbow_R": [(402, 425), (748, 425), (1220, 425)],
    "wrist_L": [(149, 533), (670, 531), (1018, 533)],
    "wrist_R": [(427, 533), (753, 531), (1240, 533)],
    "chest_center": [(290, 352), (705, 352), (1130, 352)],
    "pelvis_center": [(290, 604), (706, 604), (1130, 604)],
    "hip_L": [(247, 610), (687, 610), (1087, 610)],
    "hip_R": [(333, 610), (724, 610), (1173, 610)],
    "knee_L": [(253, 774), (688, 774), (1087, 774)],
    "knee_R": [(328, 774), (724, 774), (1170, 774)],
    "ankle_L": [(254, 932), (684, 932), (1087, 932)],
    "ankle_R": [(328, 932), (727, 932), (1170, 932)],
    "sole_y": [(290, 1054), (710, 1054), (1130, 1054)],
}


def font(size: int):
    try:
        return ImageFont.truetype("segoeui.ttf", size)
    except OSError:
        return ImageFont.load_default()


def draw_joint(draw: ImageDraw.ImageDraw, xy, fill):
    x, y = xy
    draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=fill, outline="white", width=1)


def main():
    image = Image.open(SOURCE).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    cyan = (0, 150, 255, 230)
    orange = (245, 116, 34, 230)
    green = (25, 154, 88, 230)
    white = (255, 255, 255, 230)

    for name, panel in PANELS.items():
        draw.rectangle((panel["x_min"], 12, panel["x_max"], 1068), outline=(255, 255, 255, 150), width=2)
        draw.rectangle((panel["x_min"] + 6, 12, panel["x_min"] + 84, 39), fill=(0, 0, 0, 150))
        draw.text((panel["x_min"] + 12, 15), name.upper(), fill=white, font=font(18))

    # Corresponding horizontal body stations make scale drift visible.
    stations = [
        (29, "TOP"), (184, "JAW"), (231, "NECK"), (261, "SHOULDER"),
        (425, "ELBOW"), (533, "WRIST"), (604, "HIP"), (774, "KNEE"),
        (932, "ANKLE"), (1054, "GROUND"),
    ]
    for y, label in stations:
        draw.line((80, y, 1310, y), fill=(255, 210, 0, 85), width=1)
        draw.rectangle((80, y - 10, 148, y + 9), fill=(255, 255, 255, 210))
        draw.text((84, y - 9), label, fill=(130, 92, 0, 230), font=font(12))

    # Central articulated blockout and the three primary volume primitives.
    volume_bounds = {
        "front": {"head": (226, 44, 354, 190), "rib": (215, 270, 365, 470), "pelvis": (228, 515, 352, 674)},
        "side": {"head": (642, 44, 754, 190), "rib": (657, 270, 753, 470), "pelvis": (664, 515, 748, 674)},
        "back": {"head": (1066, 44, 1194, 190), "rib": (1055, 270, 1205, 470), "pelvis": (1068, 515, 1192, 674)},
    }
    for i, view in enumerate(("front", "side", "back")):
        lm = {key: value[i] for key, value in LANDMARKS.items() if key != "sole_y"}
        draw.ellipse(volume_bounds[view]["head"], outline=cyan, width=3)
        draw.ellipse(volume_bounds[view]["rib"], outline=orange, width=3)
        draw.ellipse(volume_bounds[view]["pelvis"], outline=green, width=3)

        chains = [
            ("spine", [lm["jaw"], lm["neck_base"], lm["chest_center"], lm["pelvis_center"]], cyan),
            ("arm_l", [lm["shoulder_L"], lm["elbow_L"], lm["wrist_L"]], orange),
            ("arm_r", [lm["shoulder_R"], lm["elbow_R"], lm["wrist_R"]], orange),
            ("leg_l", [lm["hip_L"], lm["knee_L"], lm["ankle_L"]], green),
            ("leg_r", [lm["hip_R"], lm["knee_R"], lm["ankle_R"]], green),
        ]
        for _, points, fill in chains:
            draw.line(points, fill=fill, width=4, joint="curve")
        for key, point in lm.items():
            fill = cyan if key in {"jaw", "neck_base", "chest_center", "pelvis_center"} else (green if key.startswith(("hip", "knee", "ankle")) else orange)
            draw_joint(draw, point, fill)

    draw.rectangle((1040, 1018, 1308, 1050), fill=(255, 255, 255, 225))
    draw.line((1050, 1034, 1080, 1034), fill=cyan, width=4)
    draw.text((1088, 1025), "head/spine", fill=(0, 90, 170), font=font(13))
    draw.line((1175, 1034, 1205, 1034), fill=orange, width=4)
    draw.text((1213, 1025), "upper body", fill=(160, 65, 0), font=font(13))

    output = QA / "gate2a-landmark-overlay.png"
    image.convert("RGB").save(output, quality=95)

    contract = {
        "character": "xiaoxing",
        "stage": "gate2a-body-model-preflight",
        "status": "approved_by_user",
        "approval": {"decision": "approved", "evidence": "User replied 是的 after reviewing the Gate 2A overlay."},
        "canvas": {"width": 1448, "height": 1086, "coordinateSystem": "source/xiaoxing-three-view-line.png pixel space"},
        "views": PANELS,
        "landmarks": {key: [{"view": view, "x": point[0], "y": point[1]} for view, point in zip(("front", "side", "back"), points)] for key, points in LANDMARKS.items()},
        "volumePrimitives": {
            "skull": {"type": "ellipse", "boundsByView": {"front": [226, 44, 354, 190], "side": [646, 44, 774, 190], "back": [1066, 44, 1194, 190]}},
            "ribcage": {"type": "ellipse", "centerY": 352, "halfWidthByView": {"front": 75, "side": 48, "back": 75}, "top": 270, "bottom": 470},
            "pelvis": {"type": "ellipse", "centerY": 604, "halfWidthByView": {"front": 62, "side": 42, "back": 62}, "top": 515, "bottom": 674},
        },
        "segmentContracts": {
            "upperArm": "shoulder-to-elbow; preserve per-view length within 5% after projection",
            "forearm": "elbow-to-wrist; preserve per-view length within 5% after projection",
            "thigh": "hip-to-knee; preserve per-view length within 5% after projection",
            "lowerLeg": "knee-to-ankle; preserve per-view length within 5% after projection",
            "foot": "ankle-to-sole contact; contact height locked in rest pose",
        },
        "jointRangesDraft": {
            "headAngleX": [-20, 20],
            "headAngleY": [-12, 12],
            "headAngleZ": [-8, 8],
            "bodyAngleX": [-6, 6],
            "bodyAngleZ": [-4, 4],
            "armMotion": "small companion motion only; no large pose change in Gate 2A",
        },
        "risks": ["illustrated views are not strict orthographic projections", "long hair occludes neck and shoulders", "oversized shirt hides torso volume", "front print needs constrained deformation"],
        "evidence": {"overlay": "qa/gate2a-landmark-overlay.png", "source": "source/xiaoxing-three-view-line.png"},
    }
    (BLUEPRINTS / "gate2a-canonical-body-contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
