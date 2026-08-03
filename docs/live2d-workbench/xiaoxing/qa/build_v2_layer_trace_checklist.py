from __future__ import annotations

import json
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


GROUPS = [
    ("01", "后发", ["back_hair_center", "back_hair_R", "back_hair_L"], "Head", "线稿外轮廓；侧/背视图只用于隐藏补画"),
    ("02", "脸底与耳朵", ["face_base", "ear_R", "ear_L"], "Head", "线稿脸部轮廓；耳朵被头发遮挡处暂不伪造"),
    ("03", "眼睛结构", ["eye_socket_R", "eye_socket_L", "sclera_R", "sclera_L", "iris_R", "iris_L", "pupil_R", "pupil_L", "highlight_R", "highlight_L", "upper_lid_R", "upper_lid_L", "lower_lid_R", "lower_lid_L", "eye_mask_R", "eye_mask_L"], "Head", "已完成 V2 线稿候选；正式纹理待确认"),
    ("04", "眉鼻嘴", ["brow_R", "brow_L", "nose", "mouth_upper", "mouth_lower", "mouth_inner", "tongue"], "Head", "闭口母稿不凭空生成 mouth_inner/tongue"),
    ("05", "脖子与项链", ["neck", "necklace_chain", "necklace_pendant"], "Neck/Torso", "线稿边界；项链独立于衣身"),
    ("06", "上衣衣身与印花", ["torso_tshirt_core", "shirt_print"], "Torso", "印花是表面贴层，不承担身体变形"),
    ("07", "袖子与前臂", ["sleeve_R", "sleeve_L", "arm_R_upper", "arm_R_forearm", "arm_L_upper", "arm_L_forearm"], "Arm_R/Arm_L", "袖子覆盖手臂根部；边界按线稿描"),
    ("08", "手部与手链", ["hand_R", "hand_L", "bracelet_R", "bracelet_L"], "Arm_R/Arm_L", "每侧完整手层；不做逐指动作"),
    ("09", "裙子", ["skirt_base"], "Torso", "整条裙子作为一个材料层；褶线留在同一层，不拆无动作细节"),
    ("10", "腿部", ["leg_screen_left", "leg_screen_right"], "Leg_screen_left/Leg_screen_right", "左右整条腿各一层；裙内隐藏段需补画后再导出"),
    ("11", "袜子与鞋", ["sock_screen_left", "sock_screen_right", "shoe_screen_left", "shoe_screen_right"], "Leg_screen_left/Leg_screen_right", "袜口是接缝；鞋为完整刚性层，不拆鞋面细节"),
]


def main():
    line = Image.open(LINE).convert("RGB")
    board = Image.new("RGB", (1350, 1260), "white")
    d = ImageDraw.Draw(board)
    d.text((24, 18), "小星 V2 线稿优先分层清单（不拉伸、不导出遮罩）", fill=(25, 25, 30), font=font(25))
    d.text((24, 55), "左侧保持 512×1086 原始线稿；右侧只记录分组责任和顺序，不代表已经描边完成。", fill=(150, 50, 45), font=font(16))
    board.paste(line, (24, 100))
    d.rectangle((24, 100, 535, 1185), outline=(185, 190, 198), width=2)
    d.text((34, 110), "线稿生产基线", fill=(25, 55, 95), font=font(16), stroke_width=2, stroke_fill="white")
    x, y = 585, 105
    for num, name, ids, parent, note in GROUPS:
        d.text((x, y), f"{num}  {name}", fill=(25, 75, 135), font=font(18))
        d.text((x + 250, y), f"父节点：{parent}", fill=(80, 80, 80), font=font(14))
        y += 28
        d.text((x + 18, y), "层：" + ", ".join(ids), fill=(65, 65, 65), font=font(12))
        y += 24
        d.text((x + 18, y), "规则：" + note, fill=(110, 60, 50), font=font(13))
        y += 44
    d.text((585, 1205), "当前状态：仅为线稿分组清单；未通过单层视觉门禁前，不生成全身 RGBA。", fill=(150, 50, 45), font=font(16))
    out = ROOT / "qa" / "v2-layer-trace-checklist.png"
    board.save(out, quality=95)
    contract = {"stage":"v2-lineart-layer-trace-checklist", "status":"checklist_only_no_masks", "source":"source/masters/gate3-line-master-candidate-v1.png", "canvas":[512,1086], "groups":[{"order":int(num),"name":name,"layers":ids,"parent":parent,"note":note,"traceStatus":"not_traced"} for num,name,ids,parent,note in GROUPS], "handPolicy":"complete hand per side plus independent bracelet; no individual finger motion"}
    (ROOT / "blueprints" / "v2-lineart-layer-trace-checklist.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
