from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
MASTERS = ROOT / "source" / "masters"
QA = ROOT / "qa"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


REGIONS = [
    ("头发：后发底层 / 前发束 / 刘海", (145, 20, 370, 360),
     [
         ([(160, 118), (175, 52), (220, 20), (286, 20), (335, 55), (352, 145), (337, 310), (305, 352), (270, 282), (238, 352), (175, 322), (153, 190)], (86, 61, 157, 105)),
         ([(180, 105), (207, 48), (252, 35), (305, 52), (329, 112), (301, 151), (258, 132), (216, 155)], (180, 88, 178, 100)),
         ([(164, 145), (205, 135), (220, 345), (181, 318)], (62, 124, 190, 100)),
         ([(302, 138), (342, 155), (328, 325), (293, 348)], (62, 124, 190, 100)),
     ], "后发先补全头部与颈后；前发束独立于脸和耳朵，摆动时不露白。"),
    ("袖子与手臂：衣物前景 / 手臂底层", (55, 205, 455, 610),
     [
         ([(76, 285), (147, 220), (176, 350), (116, 390)], (40, 126, 184, 105)),
         ([(369, 285), (305, 220), (278, 350), (337, 390)], (40, 126, 184, 105)),
         ([(118, 373), (154, 366), (120, 575), (94, 568)], (225, 128, 110, 105)),
         ([(335, 373), (300, 366), (333, 575), (359, 568)], (225, 128, 110, 105)),
     ], "袖口覆盖手臂根部；手臂在袖子下保持完整，手部只做腕部跟随。"),
    ("上衣与裙子：印花贴层 / 衣身 / 裙褶", (105, 260, 410, 660),
     [
         ([(154, 271), (255, 250), (351, 272), (392, 575), (121, 575)], (205, 128, 45, 78)),
         ([(176, 304), (320, 304), (334, 535), (170, 535)], (236, 184, 72, 72)),
         ([(121, 565), (392, 565), (379, 643), (134, 643)], (65, 66, 75, 125)),
     ], "印花只作为衣服表面贴层，不承担身体变形；裙褶留在衣身之后单独摆动。"),
    ("腿、袜子与鞋：连续支撑关系", (145, 595, 370, 1065),
     [
         ([(176, 610), (242, 610), (230, 870), (184, 870)], (229, 161, 135, 92)),
         ([(270, 610), (334, 610), (325, 870), (278, 870)], (229, 161, 135, 92)),
         ([(180, 850), (232, 850), (235, 950), (177, 950)], (184, 206, 219, 120)),
         ([(276, 850), (328, 850), (334, 950), (274, 950)], (184, 206, 219, 120)),
         ([(168, 925), (239, 925), (246, 1048), (158, 1048)], (65, 117, 93, 108)),
         ([(270, 925), (340, 925), (351, 1048), (263, 1048)], (65, 117, 93, 108)),
     ], "腿部是底层，袜口和鞋子覆盖接缝；不把鞋底或袜褶拆成无动作价值的小层。"),
]


def main() -> None:
    color = Image.open(MASTERS / "gate3-color-target-v1.png").convert("RGBA")
    line = Image.open(MASTERS / "gate3-line-master-candidate-v1.png").convert("RGBA")
    rows = []
    for title, box, shapes, note in REGIONS:
        c = color.crop(box).resize((560, 760))
        l = line.crop(box).resize((560, 760))
        overlay = Image.new("RGBA", c.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        sx, sy = 560 / (box[2] - box[0]), 760 / (box[3] - box[1])
        for points, rgba in shapes:
            local = [((x - box[0]) * sx, (y - box[1]) * sy) for x, y in points]
            od.polygon(local, fill=rgba, outline=(28, 88, 148, 220), width=4)
        rows.append((title, note, c, l, Image.alpha_composite(c, overlay)))

    board = Image.new("RGB", (1800, 4 * 850 + 100), "white")
    d = ImageDraw.Draw(board)
    d.text((32, 22), "小星 Gate 5 头发与身体粗分层预检（中文）", fill=(25, 25, 25), font=font(28))
    d.text((32, 60), "目标：先保证遮挡关系、隐藏补画和转动连续性；不为没有动作的细节增加层数。", fill=(55, 75, 105), font=font(18))
    y = 95
    for title, note, c, l, o in rows:
        d.text((32, y), title, fill=(25, 70, 130), font=font(22))
        d.text((620, y + 4), note, fill=(55, 55, 55), font=font(16))
        iy = y + 42
        board.paste(c.convert("RGB"), (32, iy))
        board.paste(l.convert("RGB"), (620, iy))
        board.paste(o.convert("RGB"), (1208, iy))
        for x, label in ((32, "彩色母稿"), (620, "线稿边界"), (1208, "粗分层覆盖")):
            d.text((x + 10, iy + 10), label, fill=(35, 35, 35), font=font(16), stroke_width=2, stroke_fill="white")
        y += 850
    out = QA / "gate5-hair-body-preflight.png"
    board.save(out, quality=95)
    groups = {
        "头发": ["back_hair_center", "back_hair_R", "back_hair_L", "bangs_center", "bangs_R", "bangs_L", "front_hair_side_R", "front_hair_side_L"],
        "袖子与手臂": ["sleeve_R", "sleeve_L", "arm_R_upper", "arm_R_forearm", "hand_R", "arm_L_upper", "arm_L_forearm", "hand_L"],
        "上衣与裙子": ["torso_tshirt_core", "shirt_print", "skirt_back", "skirt_front_center", "skirt_pleats_R", "skirt_pleats_L"],
        "腿袜鞋": ["leg_R_thigh", "leg_L_thigh", "leg_R_lower", "leg_L_lower", "sock_R", "sock_L", "shoe_R", "shoe_L"],
    }
    gate3 = json.loads((ROOT / "blueprints" / "gate3-production-blueprint-contract.json").read_text(encoding="utf-8"))
    layer_ids = {layer["id"] for layer in gate3["layers"]}
    missing = sorted({item for values in groups.values() for item in values} - layer_ids)
    bounds_errors = []
    for title, _box, shapes, _note in REGIONS:
        for points, _rgba in shapes:
            for x, y in points:
                if not (0 <= x < 512 and 0 <= y < 1086):
                    bounds_errors.append(f"{title}: ({x},{y})")
    contract = {
        "stage": "gate5-hair-body-coarse-preflight",
        "status": "pass_pending_visual_gate" if not missing and not bounds_errors else "fail",
        "policy": "只拆有动作价值的材料；手部保持完整手层；所有活动件在遮挡区预留隐藏补画",
        "groups": groups,
        "sourceMaster": "source/masters/gate3-color-target-v1.png",
        "qaImage": "qa/gate5-hair-body-preflight.png",
    }
    (ROOT / "blueprints" / "gate5-hair-body-contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    validation = {
        "status": contract["status"],
        "checks": {
            "all_group_layers_exist_in_gate3": not missing,
            "all_overlay_points_inside_master": not bounds_errors,
            "hand_policy_remains_complete_layer": gate3.get("handSegmentation", {}).get("individualFingerMotion") is False,
        },
        "missingLayers": missing,
        "boundsErrors": bounds_errors,
    }
    (ROOT / "audit" / "gate5-hair-body-validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "audit" / "gate5-hair-body-preflight.md").write_text(
        "# Gate 5 头发与身体粗分层预检\n\n"
        "本图只审查遮挡、接缝和运动价值，不代表最终导入 Cubism 的纹理。\n"
        "手部沿用完整手层方案；本阶段重点是后发/前发、袖子/手臂、衣身/裙褶、腿/袜/鞋的层间关系。\n",
        encoding="utf-8",
    )
    print(out)


if __name__ == "__main__":
    main()
