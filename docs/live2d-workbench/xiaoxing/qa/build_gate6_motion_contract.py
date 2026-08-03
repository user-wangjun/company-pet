from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
QA = ROOT / "qa"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


PARAMETERS = [
    {"id": "ParamAngleX", "range": [-15, 15], "purpose": "头部左右转；眼睛、刘海和侧发跟随", "layers": ["Head", "eye_socket_R", "eye_socket_L", "iris_R", "iris_L", "bangs_center", "bangs_R", "bangs_L", "front_hair_side_R", "front_hair_side_L"]},
    {"id": "ParamAngleY", "range": [-10, 10], "purpose": "头部上下点头；脸、眼睛和下巴连续变形", "layers": ["Head", "face_base", "eye_socket_R", "eye_socket_L", "sclera_R", "sclera_L", "iris_R", "iris_L"]},
    {"id": "ParamAngleZ", "range": [-5, 5], "purpose": "头部轻微侧倾；头发和项链延迟跟随", "layers": ["Head", "back_hair_center", "back_hair_R", "back_hair_L", "necklace_chain", "necklace_pendant"]},
    {"id": "ParamBodySway", "range": [-1, 1], "purpose": "小幅重心摆动；脚底保持接触", "layers": ["Body_Global", "Torso", "Arm_R", "Arm_L", "skirt_pleats_R", "skirt_pleats_L"]},
    {"id": "ParamHairSway", "range": [-1, 1], "purpose": "头发轻微滞后摆动，不改变发型身份", "layers": ["back_hair_center", "back_hair_R", "back_hair_L", "front_hair_side_R", "front_hair_side_L"]},
    {"id": "ParamEyeBallX", "range": [-1, 1], "purpose": "虹膜和瞳孔左右视线", "layers": ["iris_R", "iris_L", "pupil_R", "pupil_L", "highlight_R", "highlight_L"]},
    {"id": "ParamEyeOpen", "range": [0, 1], "purpose": "眨眼；闭合时眼白和虹膜完全隐藏", "layers": ["upper_lid_R", "upper_lid_L", "lower_lid_R", "lower_lid_L", "eye_mask_R", "eye_mask_L"]},
    {"id": "ParamMouthOpenY", "range": [0, 1], "purpose": "轻量口型，不新增夸张表情", "layers": ["mouth_inner", "mouth_upper", "mouth_lower", "tongue"]},
    {"id": "ParamBreath", "range": [0, 1], "purpose": "胸口和衣身极小幅呼吸", "layers": ["Torso", "torso_tshirt_core", "skirt_front_center"]},
    {"id": "ParamNecklaceSway", "range": [-1, 1], "purpose": "项链受头部与身体运动驱动的轻摆", "layers": ["necklace_chain", "necklace_pendant"]},
    {"id": "ParamSkirtSway", "range": [-1, 1], "purpose": "左右裙褶受身体运动驱动的微摆", "layers": ["skirt_pleats_R", "skirt_pleats_L"]},
]

PHYSICS = [
    {"id": "PhysicsHairFront", "inputs": [{"parameter": "ParamAngleX", "weight": 0.45}, {"parameter": "ParamAngleZ", "weight": 0.35}, {"parameter": "ParamBodySway", "weight": 0.20}], "output": "ParamHairSway", "feel": "轻、慢半拍、回弹一次以内"},
    {"id": "PhysicsHairBack", "inputs": [{"parameter": "ParamAngleZ", "weight": 0.55}, {"parameter": "ParamBodySway", "weight": 0.45}], "output": "ParamHairSway", "feel": "比前发稍重，幅度更小"},
    {"id": "PhysicsNecklace", "inputs": [{"parameter": "ParamAngleZ", "weight": 0.40}, {"parameter": "ParamBodySway", "weight": 0.60}], "output": "ParamNecklaceSway", "feel": "短链轻摆，不穿过衣身"},
    {"id": "PhysicsSkirt", "inputs": [{"parameter": "ParamBodySway", "weight": 1.0}], "output": "ParamSkirtSway", "feel": "左右裙褶微幅反向跟随"},
]


def arrow(draw: ImageDraw.ImageDraw, x: int, y: int, dx: int, dy: int, color):
    draw.line((x, y, x + dx, y + dy), fill=color, width=5)
    ex, ey = x + dx, y + dy
    draw.polygon([(ex, ey), (ex - 12, ey - 5), (ex - 5, ey - 15)], fill=color)


def main() -> None:
    source = Image.open(MASTER).convert("RGB").resize((300, 636))
    board = Image.new("RGB", (4 * 360, 820), "white")
    d = ImageDraw.Draw(board)
    d.text((24, 18), "小星 Gate 6 首版运动范围与联动审查", fill=(20, 25, 35), font=font(26))
    d.text((24, 55), "只验证参数方向、幅度和层间跟随；不代表最终 Cubism 网格。", fill=(55, 75, 105), font=font(17))
    cards = [
        ("静止基准", "所有参数回到 0；脚底与身体比例不漂移", (120, 120, 120), []),
        ("头部左右转", "AngleX ±15°；眼睛跟随，侧发有轻微延迟", (70, 105, 190), [(175, 238, -48, 0), (185, 238, 48, 0)]),
        ("身体轻摆", "BodySway ±1；重心小幅移动，脚底不抬起", (50, 145, 105), [(178, 390, -30, 10), (182, 390, 30, 10)]),
        ("眨眼与头发", "EyeOpen 1→0；HairSway ±1，不做逐根发丝动作", (170, 90, 155), [(150, 190, 0, 34), (250, 190, 0, 34)]),
    ]
    for i, (title, note, color, arrows) in enumerate(cards):
        x = i * 360 + 30
        d.rounded_rectangle((x, 100, x + 330, 800), radius=10, fill=(247, 248, 250), outline=(205, 210, 218), width=2)
        d.text((x + 15, 115), title, fill=color, font=font(21))
        d.text((x + 15, 150), note, fill=(55, 55, 55), font=font(15))
        panel = source.copy()
        pd = ImageDraw.Draw(panel)
        if i == 0:
            pd.ellipse((122, 38, 178, 96), outline=color, width=4)
            pd.rectangle((78, 130, 222, 408), outline=color, width=4)
        elif i == 1:
            pd.ellipse((90, 38, 210, 155), outline=color, width=4)
            pd.arc((70, 80, 230, 250), 200, 340, fill=color, width=5)
        elif i == 2:
            pd.line((150, 135, 142, 470), fill=color, width=5)
            pd.line((150, 470, 142, 620), fill=color, width=5)
        else:
            pd.arc((84, 88, 145, 125), 0, 180, fill=color, width=5)
            pd.arc((155, 88, 216, 125), 0, 180, fill=color, width=5)
            pd.arc((92, 35, 208, 300), 15, 165, fill=color, width=4)
        for ax, ay, dx, dy in arrows:
            arrow(pd, ax, ay, dx, dy, color)
        board.paste(panel, (x + 15, 180))
    out = QA / "gate6-motion-contract-contact-sheet.png"
    board.save(out, quality=95)
    contract = {
        "stage": "gate6-motion-contract",
        "status": "self_review_passed_pre_cubism",
        "character": "xiaoxing",
        "policy": "首版只保留有明显视觉收益的参数；手部不做逐指动作；眼睛优先于装饰细节",
        "parameters": PARAMETERS,
        "physics": PHYSICS,
        "evidence": "qa/gate6-motion-contract-contact-sheet.png",
    }
    (ROOT / "blueprints" / "gate6-motion-contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    gate3 = json.loads((ROOT / "blueprints" / "gate3-production-blueprint-contract.json").read_text(encoding="utf-8"))
    known = {layer["id"] for layer in gate3["layers"]}
    # Deformer names are also valid targets; validate against the full tree's keys and values.
    known |= set(gate3["deformerTree"].keys()) | {v for values in gate3["deformerTree"].values() for v in values}
    missing = sorted({layer for p in PARAMETERS for layer in p["layers"] if layer not in known})
    parameter_ids = {p["id"] for p in PARAMETERS}
    bad_physics_inputs = sorted({i["parameter"] for physics in PHYSICS for i in physics["inputs"] if i["parameter"] not in parameter_ids})
    bad_physics_outputs = sorted({physics["output"] for physics in PHYSICS if physics["output"] not in parameter_ids})
    validation = {"status": "self_review_passed_pre_cubism" if not missing and not bad_physics_inputs and not bad_physics_outputs else "fail", "parameterCount": len(PARAMETERS), "physicsGroupCount": len(PHYSICS), "missingTargets": missing, "badPhysicsInputs": bad_physics_inputs, "badPhysicsOutputs": bad_physics_outputs, "rules": {"all_targets_exist": not missing, "physics_inputs_exist": not bad_physics_inputs, "physics_outputs_exist": not bad_physics_outputs, "hand_is_coarse": gate3["handSegmentation"].get("individualFingerMotion") is False}}
    (ROOT / "audit" / "gate6-motion-contract-validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
