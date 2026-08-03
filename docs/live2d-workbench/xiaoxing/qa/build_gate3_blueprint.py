from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
MASTERS = SOURCE / "masters"
QA = ROOT / "qa"
BLUEPRINTS = ROOT / "blueprints"
CROP = (34, 0, 546, 1086)

# Hand contours are kept as explicit candidate polygons in source-master pixel
# space. They are reviewed geometry, not production alpha masks yet.
HAND_POLYGONS_R = {
    "palm": [(103, 532), (118, 532), (122, 548), (118, 566), (109, 580), (98, 575), (96, 560)],
    "thumb": [(107, 569), (118, 565), (126, 575), (126, 591), (122, 604), (116, 611), (109, 606), (106, 594), (106, 582)],
    "little": [(65, 570), (76, 570), (80, 583), (76, 600), (69, 612), (63, 612), (62, 602)],
    "ring": [(74, 570), (86, 571), (90, 584), (87, 604), (82, 621), (76, 625), (72, 614), (74, 595)],
    "middle": [(84, 570), (97, 572), (101, 586), (99, 605), (96, 623), (90, 628), (85, 617), (86, 596)],
    "index": [(95, 570), (106, 574), (110, 586), (111, 600), (107, 614), (102, 617), (98, 607), (99, 590)],
}


HAND_POLYGONS_L = {
    "palm": [(394, 532), (409, 532), (416, 548), (416, 566), (407, 580), (396, 575), (390, 560)],
    "thumb": [(384, 570), (394, 566), (401, 575), (402, 587), (399, 600), (395, 610), (390, 605), (387, 590)],
    "index": [(394, 570), (405, 572), (410, 585), (411, 603), (408, 617), (403, 620), (398, 610), (397, 592)],
    "middle": [(403, 570), (414, 573), (419, 587), (420, 607), (417, 624), (412, 629), (407, 616), (407, 594)],
    "ring": [(412, 571), (424, 575), (430, 590), (433, 607), (430, 620), (424, 625), (418, 613), (416, 592)],
    "little": [(422, 573), (435, 578), (443, 592), (447, 606), (444, 614), (438, 614), (431, 604), (426, 590)],
}


HAND_POLYGONS = {"R": HAND_POLYGONS_R, "L": HAND_POLYGONS_L}

# Centerlines are used only to resolve ownership where neighboring finger
# candidate polygons overlap. Every final preview pixel is still clipped to the
# independently extracted hand-skin component and to the visible line geometry.
HAND_CENTERLINES = {
    "R": {
        "thumb": [(106, 574), (110, 587), (114, 600), (116, 607)],
        "index": [(99, 577), (101, 592), (103, 609)],
        "middle": [(90, 577), (93, 599), (94, 622)],
        "ring": [(81, 578), (82, 600), (79, 620)],
        "little": [(73, 578), (69, 595), (65, 609)],
    },
    "L": {
        "thumb": [(394, 574), (396, 589), (393, 605)],
        "index": [(402, 577), (405, 597), (404, 616)],
        "middle": [(409, 578), (412, 601), (412, 625)],
        "ring": [(415, 579), (418, 600), (420, 619)],
        "little": [(423, 579), (428, 596), (431, 613)],
    },
}


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def crop_master(path: Path, out: Path):
    image = Image.open(path).convert("RGB")
    image.crop(CROP).save(out, quality=95)


def label(draw, number, xy, color):
    x, y = xy
    draw.ellipse((x - 13, y - 13, x + 13, y + 13), fill=color, outline="white", width=2)
    draw.text((x - 6, y - 10), str(number), fill="white", font=font(15))


def main():
    MASTERS.mkdir(parents=True, exist_ok=True)
    crop_master(SOURCE / "xiaoxing-three-view-color.png", MASTERS / "gate3-color-target-v1.png")
    crop_master(SOURCE / "xiaoxing-three-view-line.png", MASTERS / "gate3-line-master-candidate-v1.png")

    line = Image.open(MASTERS / "gate3-line-master-candidate-v1.png").convert("RGBA")
    board = Image.new("RGB", (1430, 1130), "white")
    board.paste(line.convert("RGB"), (24, 24))
    draw = ImageDraw.Draw(board, "RGBA")
    draw.text((24, 3), "小星 Gate 3 生产蓝图－候选边界（不是最终蒙版）", fill=(35, 35, 35), font=font(20))

    # Local coordinates on the exact 512 x 1086 front master. These outlines are
    # semantic ownership guides; they deliberately do not pretend to be pixel masks.
    regions = [
        (1, "back_hair_center/R/L", (125, 30, 385, 390), (112, 76, 190, 210)),
        (2, "face_base", (187, 50, 322, 198), (35, 140, 215, 210)),
        (3, "bangs_center/R/L", (185, 35, 323, 145), (190, 70, 180, 210)),
        (4, "front_hair_side_R", (128, 95, 214, 410), (190, 70, 180, 210)),
        (5, "front_hair_side_L", (298, 95, 382, 410), (190, 70, 180, 210)),
        (6, "eye_R", (215, 112, 252, 150), (35, 140, 215, 210)),
        (7, "eye_L", (270, 112, 307, 150), (35, 140, 215, 210)),
        (8, "neck", (237, 180, 276, 244), (25, 155, 100, 210)),
        (9, "torso_tshirt_core", (132, 220, 380, 585), (240, 115, 35, 210)),
        (10, "shirt_print", (198, 275, 322, 505), (235, 75, 75, 210)),
        (11, "arm_R_upper", (90, 285, 151, 430), (240, 115, 35, 210)),
        (12, "arm_R_forearm", (86, 415, 139, 535), (240, 115, 35, 210)),
        (13, "hand_R", (62, 538, 136, 630), (240, 115, 35, 210)),
        (14, "arm_L_upper", (357, 285, 420, 430), (240, 115, 35, 210)),
        (15, "arm_L_forearm", (368, 415, 429, 535), (240, 115, 35, 210)),
        (16, "hand_L", (382, 538, 447, 630), (240, 115, 35, 210)),
        (17, "skirt_back/front/pleat groups", (135, 565, 378, 650), (25, 155, 100, 210)),
        (18, "leg_R_thigh", (198, 632, 258, 790), (25, 155, 100, 210)),
        (19, "leg_L_thigh", (282, 632, 342, 790), (25, 155, 100, 210)),
        (20, "leg_R_lower", (199, 770, 258, 933), (25, 155, 100, 210)),
        (21, "leg_L_lower", (282, 770, 342, 933), (25, 155, 100, 210)),
        (22, "sock_R", (198, 910, 259, 993), (25, 155, 100, 210)),
        (23, "sock_L", (282, 910, 343, 993), (25, 155, 100, 210)),
        (24, "shoe_R", (170, 978, 274, 1072), (70, 110, 165, 210)),
        (25, "shoe_L", (270, 978, 377, 1072), (70, 110, 165, 210)),
        (26, "bracelet_R", (86, 518, 141, 548), (205, 145, 35, 220)),
        (27, "bracelet_L", (366, 518, 432, 548), (205, 145, 35, 220)),
        (28, "necklace_chain + pendant", (237, 199, 276, 255), (205, 145, 35, 220)),
        (39, "sleeve_R", (90, 250, 160, 390), (60, 155, 210, 220)),
        (40, "sleeve_L", (350, 250, 425, 390), (60, 155, 210, 220)),
    ]
    hand_region_polygons = {
        "hand_R": [polygon for polygon in HAND_POLYGONS["R"].values()],
        "hand_L": [polygon for polygon in HAND_POLYGONS["L"].values()],
    }
    master_offset = (24, 24)
    for number, name, box, color in regions:
        if name in hand_region_polygons:
            for polygon in hand_region_polygons[name]:
                shifted = [(x + master_offset[0], y + master_offset[1]) for x, y in polygon]
                draw.polygon(shifted, fill=(color[0], color[1], color[2], 55), outline=color)
            first = hand_region_polygons[name][0][0]
            label(draw, number, (first[0] + master_offset[0], first[1] + master_offset[1]), color)
        else:
            shifted_box = (box[0] + master_offset[0], box[1] + master_offset[1], box[2] + master_offset[0], box[3] + master_offset[1])
            draw.rectangle(shifted_box, outline=color, width=2)
            label(draw, number, (shifted_box[0] + 14, shifted_box[1] + 14), color)

    # Review legend and non-negotiable hidden continuations.
    x0 = 575
    draw.rectangle((x0, 24, 1410, 1105), fill=(248, 249, 251, 255), outline=(210, 214, 220, 255), width=2)
    draw.text((x0 + 24, 48), "语义图层候选（ID 保留英文）", fill=(30, 30, 30), font=font(22))
    y = 90
    for number, name, _, color in regions:
        draw.ellipse((x0 + 24, y + 2, x0 + 42, y + 20), fill=color)
        draw.text((x0 + 50, y - 2), f"{number:02d}  {name}", fill=(55, 55, 55), font=font(15))
        y += 28
        if y > 860:
            break
    draw.text((x0 + 290, 90), "必须补画的隐藏区域", fill=(30, 30, 30), font=font(18))
    hidden = [
        "后发：补全后脑与头皮",
        "前发：补全耳后及刘海下方发根",
        "脸部：补全被头发遮住的脸颊与太阳穴",
        "颈部：补全脖子和肩根连接",
        "袖子：补全袖口下的上臂",
        "躯干：补全衣服下的胸腔、腰腹和骨盆",
        "裙子：补全腰带与大腿根遮挡",
        "四肢：关节两侧都保留连续材质",
        "眼睛：补全眼白、眼睑和眼窝",
        "印花：保持为受限的独立贴花层",
    ]
    y2 = 126
    for item in hidden:
        draw.text((x0 + 290, y2), "• " + item, fill=(75, 75, 75), font=font(14))
        y2 += 31
    draw.text((x0 + 24, 930), "R／L 按角色自身的左右方向命名。\n编号引导线只表示图层归属，不是最终透明蒙版。", fill=(75, 75, 75), font=font(15), spacing=7)
    board.save(QA / "gate3-production-blueprint-review.png", quality=95)

    # Hand close-up review: each visible digit is assigned independently.
    # Hidden roots remain reconstruction obligations for the production pass.
    color_master = Image.open(MASTERS / "gate3-color-target-v1.png").convert("RGB")
    hand_board = Image.new("RGB", (1400, 590), "white")
    hand_draw = ImageDraw.Draw(hand_board, "RGBA")
    hand_draw.text((24, 14), "小星手部分层局部审查－首版完整手层方案", fill=(35, 35, 35), font=font(22))
    hand_specs = [("角色右手／画面左侧", (65, 510, 155, 645), "R"), ("角色左手／画面右侧", (355, 510, 445, 645), "L")]
    hand_color = (55, 135, 190, 220)
    panels = []
    for title, crop_box, side in hand_specs:
        panels.extend([(title, crop_box, side, color_master, "color"), (title, crop_box, side, line, "line")])
    for col, (title, crop_box, side, source_image, label_text) in enumerate(panels):
            x0 = 25 + col * 340
            y0 = 62
            crop = source_image.crop(crop_box).resize((300, 450))
            hand_board.paste(crop.convert("RGB"), (x0, y0))
            hand_draw.rectangle((x0, y0, x0 + 300, y0 + 450), outline=(205, 210, 215), width=2)
            source_name = "彩色原图" if label_text == "color" else "线稿与分层"
            hand_draw.text((x0 + 8, y0 + 8), f"{title}－{source_name}", fill=(40, 40, 40), font=font(14), stroke_width=2, stroke_fill="white")
            scale = 300 / (crop_box[2] - crop_box[0])
            cx, cy = x0 - crop_box[0] * scale, y0 - crop_box[1] * scale
            for polygon in HAND_POLYGONS[side].values():
                shifted = [(cx + x * scale, cy + y * scale) for x, y in polygon]
                hand_draw.polygon(shifted, fill=(*hand_color[:3], 65), outline=hand_color, width=4)
    hand_draw.text((24, 530), "蓝色轮廓：完整手层（掌心、拇指和所有手指保持原图整体）", fill=(70, 70, 70), font=font(16))
    hand_draw.text((24, 558), "首版只做手腕轻微摆动，不制作握拳、张指或逐指动作；手链仍保持独立。", fill=(70, 70, 70), font=font(16))
    hand_board.save(QA / "gate3-hand-layer-review.png", quality=95)

    layers = [
        {"id": "back_hair_center", "drawOrder": 10, "parent": "Head", "pivot": "head_center", "source": "front+side+back", "hiddenFill": "complete back head and scalp", "visibleOwnership": "central rear hair mass"},
        {"id": "back_hair_R", "drawOrder": 11, "parent": "Head", "pivot": "hair_R_root", "source": "front+side+back", "hiddenFill": "root overlap beneath crown and character-right side hair", "visibleOwnership": "character-right rear hair tail"},
        {"id": "back_hair_L", "drawOrder": 12, "parent": "Head", "pivot": "hair_L_root", "source": "front+side+back", "hiddenFill": "root overlap beneath crown and character-left side hair", "visibleOwnership": "character-left rear hair tail"},
        {"id": "body_hidden_base", "drawOrder": 20, "parent": "Body_Global", "pivot": "pelvis", "source": "three-view inferred", "hiddenFill": "full neck, ribcage, abdomen, pelvis and limb roots", "visibleOwnership": "underpaint only, normally occluded"},
        {"id": "leg_R_thigh", "drawOrder": 30, "parent": "Leg_R", "pivot": "hip_R", "source": "front+side+back", "hiddenFill": "hip to knee continuation behind skirt", "visibleOwnership": "character-right thigh"},
        {"id": "leg_L_thigh", "drawOrder": 31, "parent": "Leg_L", "pivot": "hip_L", "source": "front+side+back", "hiddenFill": "hip to knee continuation behind skirt", "visibleOwnership": "character-left thigh"},
        {"id": "leg_R_lower", "drawOrder": 32, "parent": "Leg_R", "pivot": "knee_R", "source": "front+side+back", "hiddenFill": "knee continuation under sock", "visibleOwnership": "character-right lower leg"},
        {"id": "leg_L_lower", "drawOrder": 33, "parent": "Leg_L", "pivot": "knee_L", "source": "front+side+back", "hiddenFill": "knee continuation under sock", "visibleOwnership": "character-left lower leg"},
        {"id": "sock_R", "drawOrder": 40, "parent": "Leg_R", "pivot": "ankle_R", "source": "front+side+back", "hiddenFill": "sock volume behind shoe", "visibleOwnership": "character-right sock"},
        {"id": "sock_L", "drawOrder": 41, "parent": "Leg_L", "pivot": "ankle_L", "source": "front+side+back", "hiddenFill": "sock volume behind shoe", "visibleOwnership": "character-left sock"},
        {"id": "shoe_R", "drawOrder": 42, "parent": "Leg_R", "pivot": "ankle_R", "source": "front+side+back", "hiddenFill": "complete sole and heel", "visibleOwnership": "character-right shoe"},
        {"id": "shoe_L", "drawOrder": 43, "parent": "Leg_L", "pivot": "ankle_L", "source": "front+side+back", "hiddenFill": "complete sole and heel", "visibleOwnership": "character-left shoe"},
        {"id": "torso_tshirt_core", "drawOrder": 60, "parent": "Torso", "pivot": "chest", "source": "front+side+back color", "hiddenFill": "complete shoulder seams, underarms and hem behind sleeves/skirt", "visibleOwnership": "shirt torso shell excluding sleeves"},
        {"id": "shirt_print", "drawOrder": 61, "parent": "Torso", "pivot": "chest", "source": "front color", "hiddenFill": "none; constrained sticker layer", "visibleOwnership": "front butterfly and text print"},
        {"id": "necklace_chain", "drawOrder": 62, "parent": "Torso", "pivot": "neck_base", "source": "front color", "hiddenFill": "chain continuation beneath hair", "visibleOwnership": "necklace chain"},
        {"id": "necklace_pendant", "drawOrder": 63, "parent": "Torso", "pivot": "pendant", "source": "front color", "hiddenFill": "attachment beneath chain", "visibleOwnership": "butterfly pendant"},
        {"id": "skirt_back", "drawOrder": 25, "parent": "Torso", "pivot": "pelvis", "source": "front+side+back", "hiddenFill": "complete rear waistband and back pleats", "visibleOwnership": "rear skirt mass behind legs"},
        {"id": "skirt_front_center", "drawOrder": 70, "parent": "Torso", "pivot": "pelvis", "source": "front+side+back", "hiddenFill": "waist band and upper-leg overlap", "visibleOwnership": "central front pleats"},
        {"id": "skirt_pleats_R", "drawOrder": 71, "parent": "Torso", "pivot": "hip_R", "source": "front+side+back", "hiddenFill": "overlap beneath center and side seam", "visibleOwnership": "character-right front pleat group"},
        {"id": "skirt_pleats_L", "drawOrder": 72, "parent": "Torso", "pivot": "hip_L", "source": "front+side+back", "hiddenFill": "overlap beneath center and side seam", "visibleOwnership": "character-left front pleat group"},
        {"id": "arm_R_upper", "drawOrder": 80, "parent": "Arm_R", "pivot": "shoulder_R", "source": "front+side+back", "hiddenFill": "shoulder under sleeve", "visibleOwnership": "character-right upper arm"},
        {"id": "arm_R_forearm", "drawOrder": 81, "parent": "Arm_R", "pivot": "elbow_R", "source": "front+side+back", "hiddenFill": "elbow continuation", "visibleOwnership": "character-right forearm"},
        {"id": "hand_R", "drawOrder": 82, "parent": "Arm_R", "pivot": "wrist_R", "source": "front+side+back", "hiddenFill": "short wrist continuation beneath bracelet; fingers remain in source pose", "visibleOwnership": "complete character-right hand including all fingers"},
        {"id": "arm_L_upper", "drawOrder": 83, "parent": "Arm_L", "pivot": "shoulder_L", "source": "front+side+back", "hiddenFill": "shoulder under sleeve", "visibleOwnership": "character-left upper arm"},
        {"id": "arm_L_forearm", "drawOrder": 84, "parent": "Arm_L", "pivot": "elbow_L", "source": "front+side+back", "hiddenFill": "elbow continuation", "visibleOwnership": "character-left forearm"},
        {"id": "hand_L", "drawOrder": 85, "parent": "Arm_L", "pivot": "wrist_L", "source": "front+side+back", "hiddenFill": "short wrist continuation beneath bracelet; fingers remain in source pose", "visibleOwnership": "complete character-left hand including all fingers"},
        {"id": "bracelet_R", "drawOrder": 86, "parent": "Arm_R", "pivot": "wrist_R", "source": "front+side+back color", "hiddenFill": "none", "visibleOwnership": "character-right bracelet"},
        {"id": "bracelet_L", "drawOrder": 87, "parent": "Arm_L", "pivot": "wrist_L", "source": "front+side+back color", "hiddenFill": "none", "visibleOwnership": "character-left bracelet"},
        {"id": "sleeve_R", "drawOrder": 88, "parent": "Arm_R", "pivot": "shoulder_R", "source": "front+side+back color", "hiddenFill": "complete shoulder cap and cuff underside", "visibleOwnership": "character-right shirt sleeve"},
        {"id": "sleeve_L", "drawOrder": 89, "parent": "Arm_L", "pivot": "shoulder_L", "source": "front+side+back color", "hiddenFill": "complete shoulder cap and cuff underside", "visibleOwnership": "character-left shirt sleeve"},
        {"id": "neck", "drawOrder": 100, "parent": "Neck", "pivot": "neck_base", "source": "front+side+back inferred", "hiddenFill": "full neck and shoulder connection", "visibleOwnership": "visible neck and collar gap"},
        {"id": "face_base", "drawOrder": 110, "parent": "Head", "pivot": "head_center", "source": "front+side+back", "hiddenFill": "temple, cheek and jaw under hair", "visibleOwnership": "skin face base"},
        {"id": "ear_R", "drawOrder": 111, "parent": "Head", "pivot": "ear_R_root", "source": "front+side+back inferred", "hiddenFill": "complete ear behind hair", "visibleOwnership": "character-right ear"},
        {"id": "ear_L", "drawOrder": 112, "parent": "Head", "pivot": "ear_L_root", "source": "front+side+back inferred", "hiddenFill": "complete ear behind hair", "visibleOwnership": "character-left ear"},
        {"id": "brow_R", "drawOrder": 118, "parent": "Head", "pivot": "head_center", "source": "front line", "hiddenFill": "none", "visibleOwnership": "character-right brow"},
        {"id": "brow_L", "drawOrder": 119, "parent": "Head", "pivot": "head_center", "source": "front line", "hiddenFill": "none", "visibleOwnership": "character-left brow"},
        {"id": "eye_socket_R", "drawOrder": 120, "parent": "Head", "pivot": "eye_R_center", "source": "front+side inferred", "hiddenFill": "complete socket under lids and hair", "visibleOwnership": "character-right eye socket/base"},
        {"id": "eye_socket_L", "drawOrder": 121, "parent": "Head", "pivot": "eye_L_center", "source": "front+side inferred", "hiddenFill": "complete socket under lids and hair", "visibleOwnership": "character-left eye socket/base"},
        {"id": "sclera_R", "drawOrder": 122, "parent": "Head", "pivot": "eye_R_center", "source": "front line", "hiddenFill": "eye-white continuation beyond opening", "visibleOwnership": "character-right eye white"},
        {"id": "sclera_L", "drawOrder": 123, "parent": "Head", "pivot": "eye_L_center", "source": "front line", "hiddenFill": "eye-white continuation beyond opening", "visibleOwnership": "character-left eye white"},
        {"id": "iris_R", "drawOrder": 124, "parent": "Head", "pivot": "eye_R_center", "source": "front color inferred", "hiddenFill": "complete iris disk", "visibleOwnership": "character-right iris"},
        {"id": "iris_L", "drawOrder": 125, "parent": "Head", "pivot": "eye_L_center", "source": "front color inferred", "hiddenFill": "complete iris disk", "visibleOwnership": "character-left iris"},
        {"id": "pupil_R", "drawOrder": 126, "parent": "Head", "pivot": "eye_R_center", "source": "front color inferred", "hiddenFill": "complete pupil", "visibleOwnership": "character-right pupil"},
        {"id": "pupil_L", "drawOrder": 127, "parent": "Head", "pivot": "eye_L_center", "source": "front color inferred", "hiddenFill": "complete pupil", "visibleOwnership": "character-left pupil"},
        {"id": "highlight_R", "drawOrder": 128, "parent": "Head", "pivot": "eye_R_center", "source": "front color inferred", "hiddenFill": "none", "visibleOwnership": "character-right eye highlight"},
        {"id": "highlight_L", "drawOrder": 129, "parent": "Head", "pivot": "eye_L_center", "source": "front color inferred", "hiddenFill": "none", "visibleOwnership": "character-left eye highlight"},
        {"id": "upper_lid_R", "drawOrder": 130, "parent": "Head", "pivot": "eye_R_center", "source": "front line", "hiddenFill": "lid arc beyond visible opening", "visibleOwnership": "character-right upper lid/lash"},
        {"id": "upper_lid_L", "drawOrder": 131, "parent": "Head", "pivot": "eye_L_center", "source": "front line", "hiddenFill": "lid arc beyond visible opening", "visibleOwnership": "character-left upper lid/lash"},
        {"id": "lower_lid_R", "drawOrder": 132, "parent": "Head", "pivot": "eye_R_center", "source": "front line", "hiddenFill": "lower lid corners", "visibleOwnership": "character-right lower lid"},
        {"id": "lower_lid_L", "drawOrder": 133, "parent": "Head", "pivot": "eye_L_center", "source": "front line", "hiddenFill": "lower lid corners", "visibleOwnership": "character-left lower lid"},
        {"id": "eye_mask_R", "drawOrder": 134, "parent": "Head", "pivot": "eye_R_center", "source": "derived mask", "hiddenFill": "full closed socket mask", "visibleOwnership": "character-right clipping responsibility"},
        {"id": "eye_mask_L", "drawOrder": 135, "parent": "Head", "pivot": "eye_L_center", "source": "derived mask", "hiddenFill": "full closed socket mask", "visibleOwnership": "character-left clipping responsibility"},
        {"id": "nose", "drawOrder": 140, "parent": "Head", "pivot": "head_center", "source": "front+side line", "hiddenFill": "none", "visibleOwnership": "nose line and shadow"},
        {"id": "mouth_inner", "drawOrder": 141, "parent": "Head", "pivot": "mouth_center", "source": "front+side inferred", "hiddenFill": "complete closed mouth cavity", "visibleOwnership": "mouth interior revealed by opening"},
        {"id": "mouth_upper", "drawOrder": 142, "parent": "Head", "pivot": "mouth_center", "source": "front+side line", "hiddenFill": "upper lip continuation through corners", "visibleOwnership": "upper mouth line/lip"},
        {"id": "mouth_lower", "drawOrder": 143, "parent": "Head", "pivot": "mouth_center", "source": "front+side line", "hiddenFill": "lower lip continuation through corners", "visibleOwnership": "lower mouth line/lip"},
        {"id": "tongue", "drawOrder": 144, "parent": "Head", "pivot": "mouth_center", "source": "three-view inferred", "hiddenFill": "complete tongue patch inside cavity", "visibleOwnership": "tongue for open-mouth expressions"},
        {"id": "bangs_center", "drawOrder": 150, "parent": "Head", "pivot": "bang_center_root", "source": "front+side+back", "hiddenFill": "roots beneath crown and forehead overlap", "visibleOwnership": "central fringe group"},
        {"id": "bangs_R", "drawOrder": 151, "parent": "Head", "pivot": "bang_R_root", "source": "front+side+back", "hiddenFill": "root overlap beneath crown", "visibleOwnership": "character-right fringe group"},
        {"id": "bangs_L", "drawOrder": 152, "parent": "Head", "pivot": "bang_L_root", "source": "front+side+back", "hiddenFill": "root overlap beneath crown", "visibleOwnership": "character-left fringe group"},
        {"id": "front_hair_side_R", "drawOrder": 153, "parent": "Head", "pivot": "hair_R_root", "source": "front+side+back", "hiddenFill": "behind-ear and shoulder overlap", "visibleOwnership": "character-right front side hair"},
        {"id": "front_hair_side_L", "drawOrder": 154, "parent": "Head", "pivot": "hair_L_root", "source": "front+side+back", "hiddenFill": "behind-ear and shoulder overlap", "visibleOwnership": "character-left front side hair"},
    ]
    contract = {
        "character": "xiaoxing",
        "stage": "gate3-production-blueprint",
        "status": "blueprint_pending_user_visual_approval",
        "masters": {
            "colorTarget": "source/masters/gate3-color-target-v1.png",
            "lineMasterCandidate": "source/masters/gate3-line-master-candidate-v1.png",
            "sourceCrop": {"x": CROP[0], "y": CROP[1], "width": CROP[2] - CROP[0], "height": CROP[3] - CROP[1]},
            "transformBackToSource": {"translateX": CROP[0], "translateY": CROP[1], "scale": 1.0},
        },
        "layerCount": len(layers),
        "handSegmentation": {"v3Policy": "one complete hand layer per side + independent bracelet", "individualFingerMotion": False, "reason": "首版没有握拳、张指或手势动作；完整手层足以支持手腕轻微摆动，避免为不会使用的逐指运动增加隐藏补画和网格成本", "candidatePolygonsSourceMaster": HAND_POLYGONS, "candidateCenterlinesSourceMaster": HAND_CENTERLINES, "supersedes": "v2 individual-finger draft"},
        "layers": layers,
        "deformerTree": {
            "Xiaoxing_Root": ["Body_Global", "Head"],
            "Body_Global": ["body_hidden_base", "Torso", "Neck", "Arm_R", "Arm_L", "Leg_R", "Leg_L"],
            "Torso": ["torso_tshirt_core", "shirt_print", "necklace_chain", "necklace_pendant", "skirt_back", "skirt_front_center", "skirt_pleats_R", "skirt_pleats_L"],
            "Neck": ["neck"],
            "Arm_R": ["arm_R_upper", "arm_R_forearm", "hand_R", "bracelet_R", "sleeve_R"],
            "Arm_L": ["arm_L_upper", "arm_L_forearm", "hand_L", "bracelet_L", "sleeve_L"],
            "Leg_R": ["leg_R_thigh", "leg_R_lower", "sock_R", "shoe_R"],
            "Leg_L": ["leg_L_thigh", "leg_L_lower", "sock_L", "shoe_L"],
            "Head": ["back_hair_center", "back_hair_R", "back_hair_L", "face_base", "ear_R", "ear_L", "brow_R", "brow_L", "eye_socket_R", "eye_socket_L", "sclera_R", "sclera_L", "iris_R", "iris_L", "pupil_R", "pupil_L", "highlight_R", "highlight_L", "upper_lid_R", "upper_lid_L", "lower_lid_R", "lower_lid_L", "eye_mask_R", "eye_mask_L", "nose", "mouth_inner", "mouth_upper", "mouth_lower", "tongue", "bangs_center", "bangs_R", "bangs_L", "front_hair_side_R", "front_hair_side_L"],
        },
        "parameterDraft": [
            {"id": "ParamAngleX", "range": [-20, 20], "parts": ["Head", "eye_socket_R", "eye_socket_L", "sclera_R", "sclera_L", "iris_R", "iris_L", "pupil_R", "pupil_L", "bangs_center", "bangs_R", "bangs_L", "front_hair_side_R", "front_hair_side_L"]},
            {"id": "ParamAngleY", "range": [-12, 12], "parts": ["Head", "face_base", "eye_socket_R", "eye_socket_L", "sclera_R", "sclera_L", "iris_R", "iris_L"]},
            {"id": "ParamBodySway", "range": [-1, 1], "parts": ["Body_Global", "Torso", "Head"], "motionEvidence": "gate2b-idle-sway-contract.json"},
            {"id": "ParamEyeBallX", "range": [-1, 1], "parts": ["iris_R", "iris_L", "pupil_R", "pupil_L", "highlight_R", "highlight_L"]},
            {"id": "ParamEyeOpen", "range": [0, 1], "parts": ["upper_lid_R", "upper_lid_L", "lower_lid_R", "lower_lid_L", "eye_mask_R", "eye_mask_L"]},
            {"id": "ParamMouthOpenY", "range": [0, 1], "parts": ["mouth_inner", "mouth_upper", "mouth_lower", "tongue"]},
        ],
        "drawOrderBackToFront": [layer["id"] for layer in sorted(layers, key=lambda item: item["drawOrder"])],
        "qa": {"reviewBoard": "qa/gate3-production-blueprint-review.png", "noFormalPetRegistration": True},
    }
    (BLUEPRINTS / "gate3-production-blueprint-contract.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
