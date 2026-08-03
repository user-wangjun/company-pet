from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
OUT_DIR = ROOT / "qa" / "draft-material-layers"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


# All points use the locked 512×1086 front-master coordinate system.
GROUPS = {
    "头发": {
        "back_hair_center": [(160, 120), (175, 52), (220, 20), (286, 20), (335, 55), (352, 145), (337, 315), (300, 360), (255, 305), (205, 360), (166, 320), (153, 190)],
        "bangs_center": [(195, 102), (215, 45), (257, 34), (300, 52), (314, 112), (280, 145), (248, 129), (215, 151)],
        "front_hair_side_R": [(164, 140), (204, 130), (201, 255), (192, 320), (170, 302)],
        "front_hair_side_L": [(302, 138), (340, 153), (337, 305), (318, 335), (300, 255)],
    },
    "袖臂手": {
        "sleeve_R": [(76, 285), (147, 220), (176, 350), (116, 390)],
        "sleeve_L": [(370, 285), (345, 265), (318, 350), (337, 390)],
        "arm_R_upper": [(118, 370), (154, 365), (140, 455), (105, 455)],
        "arm_R_forearm": [(105, 445), (141, 445), (120, 575), (94, 568)],
        "hand_R": [(91, 560), (123, 560), (133, 620), (91, 633), (75, 615)],
        "arm_L_upper": [(335, 370), (300, 365), (314, 455), (349, 455)],
        "arm_L_forearm": [(313, 445), (349, 445), (359, 568), (333, 575)],
        "hand_L": [(330, 560), (362, 560), (380, 615), (364, 633), (322, 620)],
    },
    "衣裙": {
        "torso_tshirt_core": [(146, 235), (366, 235), (392, 575), (121, 575)],
        "shirt_print": [(176, 302), (328, 302), (334, 535), (170, 535)],
        "skirt_back": [(121, 565), (392, 565), (379, 643), (134, 643)],
        "skirt_front_center": [(198, 572), (315, 572), (309, 640), (202, 640)],
        "skirt_pleats_R": [(126, 570), (215, 570), (203, 642), (134, 642)],
        "skirt_pleats_L": [(300, 570), (388, 570), (379, 642), (309, 642)],
    },
    "腿袜鞋": {
        "leg_R_thigh": [(176, 610), (242, 610), (235, 770), (181, 770)],
        "leg_R_lower": [(181, 760), (235, 760), (230, 870), (184, 870)],
        "sock_R": [(180, 850), (232, 850), (235, 950), (177, 950)],
        "shoe_R": [(168, 925), (239, 925), (246, 1048), (158, 1048)],
        "leg_L_thigh": [(270, 610), (334, 610), (330, 770), (275, 770)],
        "leg_L_lower": [(275, 760), (330, 760), (325, 870), (278, 870)],
        "sock_L": [(276, 850), (328, 850), (334, 950), (274, 950)],
        "shoe_L": [(270, 925), (340, 925), (351, 1048), (263, 1048)],
    },
}

HIDDEN_ZONES = {
    "头发": [(205, 55, 310, 190), (176, 285, 225, 375), (290, 285, 338, 375)],
    "袖臂手": [(112, 345, 158, 390), (298, 345, 344, 390)],
    "衣裙": [(145, 225, 365, 280), (124, 550, 390, 605)],
    "腿袜鞋": [(176, 590, 242, 650), (270, 590, 334, 650), (178, 845, 235, 885), (274, 845, 334, 885)],
}


def export_layer(source: Image.Image, layer_id: str, points, path: Path) -> Image.Image:
    mask = Image.new("L", source.size, 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    if "hair" in layer_id:
        # Hair is the only dark material in these coarse regions; reject shirt/skin pixels that the polygon may touch.
        rgb = source.convert("RGB")
        px = rgb.load()
        mp = mask.load()
        for yy in range(source.height):
            for xx in range(source.width):
                if mp[xx, yy] and sum(px[xx, yy]) / 3 > 145:
                    mp[xx, yy] = 0
    layer = source.copy()
    layer.putalpha(mask)
    layer.save(path)
    return layer


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = Image.open(MASTER).convert("RGBA")
    entries = []
    group_composites = {}
    for group, layers in GROUPS.items():
        composite = Image.new("RGBA", source.size, (0, 0, 0, 0))
        for layer_id, points in layers.items():
            path = OUT_DIR / f"{layer_id}.png"
            layer = export_layer(source, layer_id, points, path)
            composite = Image.alpha_composite(composite, layer)
            entries.append({"id": layer_id, "group": group, "path": f"qa/draft-material-layers/{path.name}", "status": "visible_only_draft", "hiddenFill": "required_before_cubism"})
        group_composites[group] = composite

    board = Image.new("RGB", (1600, 4 * 620 + 110), "white")
    d = ImageDraw.Draw(board)
    d.text((24, 20), "小星 Gate 7 粗分层 RGBA 素材草稿审查", fill=(25, 25, 30), font=font(27))
    d.text((24, 58), "红色框为正式绑定前必须补画的隐藏区域；当前草稿只验证可见边界，不冒充最终素材。", fill=(150, 50, 45), font=font(17))
    y = 100
    for group, composite in group_composites.items():
        d.text((24, y), group, fill=(25, 75, 135), font=font(22))
        src = source.resize((260, 552)).convert("RGB")
        comp = composite.resize((260, 552))
        checker = Image.new("RGB", (260, 552), (235, 235, 235))
        cd = ImageDraw.Draw(checker)
        for yy in range(0, 552, 20):
            for xx in range(0, 260, 20):
                if (xx // 20 + yy // 20) % 2:
                    cd.rectangle((xx, yy, xx + 19, yy + 19), fill=(250, 250, 250))
        checker.paste(comp.convert("RGB"), mask=comp.getchannel("A"))
        hidden = source.copy()
        hd = ImageDraw.Draw(hidden)
        for box in HIDDEN_ZONES[group]:
            hd.rectangle(box, outline=(220, 45, 45, 255), width=5)
            hd.line((box[0], box[1], box[2], box[3]), fill=(220, 45, 45, 220), width=3)
        hidden = hidden.resize((260, 552)).convert("RGB")
        board.paste(src, (24, y + 38))
        board.paste(checker, (320, y + 38))
        board.paste(hidden, (616, y + 38))
        d.text((34, y + 48), "母稿", fill=(30, 30, 30), font=font(15), stroke_width=2, stroke_fill="white")
        d.text((330, y + 48), "透明草稿合成", fill=(30, 30, 30), font=font(15), stroke_width=2, stroke_fill="white")
        d.text((626, y + 48), "隐藏补画缺口", fill=(150, 35, 35), font=font(15), stroke_width=2, stroke_fill="white")
        ids = list(GROUPS[group])
        d.text((920, y + 55), f"本组 {len(ids)} 层", fill=(35, 35, 35), font=font(18))
        ty = y + 95
        for layer_id in ids:
            d.text((920, ty), f"• {layer_id}", fill=(65, 65, 65), font=font(14))
            ty += 26
        y += 620

    qa_path = ROOT / "qa" / "gate7-material-draft-contact-sheet.png"
    board.save(qa_path, quality=95)
    manifest = {"stage": "gate7-visible-material-draft", "status": "self_review_pending_hidden_fill", "canvas": [512, 1086], "format": "RGBA PNG full canvas", "source": "source/masters/gate3-color-target-v1.png", "layers": entries, "rules": {"draftOnly": True, "preserveSourcePixels": True, "hiddenFillStillRequired": True, "noFormalPetRegistration": True}}
    (ROOT / "qa" / "draft-material-layers.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(qa_path)


if __name__ == "__main__":
    main()
