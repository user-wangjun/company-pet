from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
OUT_DIR = ROOT / "qa" / "hidden-fill-candidates"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


# (layer, target box, donor box, note); target is deliberately conservative and hidden-only.
CANDIDATES = [
    ("back_hair_center", (205, 55, 310, 125), (215, 45, 300, 105), "头顶发根与刘海下方"),
    ("front_hair_side_R", (176, 285, 210, 345), (175, 220, 205, 280), "角色右侧发束根部"),
    ("front_hair_side_L", (300, 285, 338, 345), (305, 220, 338, 280), "角色左侧发束根部"),
    ("sleeve_R", (120, 345, 150, 372), (115, 290, 148, 330), "角色右袖口内侧"),
    ("sleeve_L", (300, 345, 335, 372), (350, 290, 385, 330), "角色左袖口内侧"),
    ("torso_tshirt_core", (170, 225, 342, 260), None, "肩线与领口后方衣身（使用衣身平均色，避免带入头发/印花）"),
    ("torso_tshirt_core_hem", (145, 550, 390, 580), (150, 515, 365, 550), "裙腰上方衣身下摆"),
    ("leg_R_thigh", (176, 590, 242, 650), (183, 650, 232, 710), "角色右裙下大腿"),
    ("leg_L_thigh", (270, 590, 334, 650), (278, 650, 327, 710), "角色左裙下大腿"),
    ("sock_R", (178, 845, 235, 885), (180, 885, 232, 930), "角色右袜口内侧"),
    ("sock_L", (274, 845, 334, 885), (278, 885, 330, 930), "角色左袜口内侧"),
    ("skirt_back", (130, 580, 380, 610), (140, 590, 375, 640), "裙腰与后裙褶连续区"),
]


def make_candidate(source: Image.Image, target, donor) -> Image.Image:
    if donor is None:
        # A flat, conservative shirt-tone fill is safer than copying hair or print into a hidden seam.
        patch = Image.new("RGBA", (target[2] - target[0], target[3] - target[1]), (233, 233, 226, 255))
    else:
        patch = source.crop(donor).resize((target[2] - target[0], target[3] - target[1]))
    out = Image.new("RGBA", source.size, (0, 0, 0, 0))
    out.paste(patch, (target[0], target[1]))
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = Image.open(MASTER).convert("RGBA")
    board = Image.new("RGB", (1500, len(CANDIDATES) * 250 + 100), "white")
    d = ImageDraw.Draw(board)
    d.text((24, 18), "小星 Gate 8 隐藏补画候选审查", fill=(25, 25, 30), font=font(26))
    d.text((24, 55), "候选只覆盖活动层背后的隐藏区域；颜色来自同一母稿邻近纹理，正式前仍需人工精修。", fill=(150, 50, 45), font=font(17))
    entries = []
    y = 95
    for index, (layer_id, target, donor, note) in enumerate(CANDIDATES, 1):
        candidate = make_candidate(source, target, donor)
        path = OUT_DIR / f"{index:02d}_{layer_id}.png"
        candidate.save(path)
        entries.append({"id": layer_id, "target": list(target), "donor": list(donor) if donor else "flat shirt average", "note": note, "path": f"qa/hidden-fill-candidates/{path.name}", "status": "candidate_only"})
        crop_box = (max(0, target[0] - 35), max(0, target[1] - 35), min(512, target[2] + 35), min(1086, target[3] + 35))
        src_crop = source.crop(crop_box).resize((330, 170)).convert("RGB")
        checker = Image.new("RGB", src_crop.size, (236, 236, 236))
        cdraw = ImageDraw.Draw(checker)
        for yy in range(0, 170, 20):
            for xx in range(0, 330, 20):
                if (xx // 20 + yy // 20) % 2:
                    cdraw.rectangle((xx, yy, xx + 19, yy + 19), fill=(249, 249, 249))
        candidate_crop = candidate.crop(crop_box).resize((330, 170))
        checker.paste(candidate_crop.convert("RGB"), mask=candidate_crop.getchannel("A"))
        original = source.crop(crop_box).resize((330, 170)).convert("RGB")
        od = ImageDraw.Draw(original)
        scale_x, scale_y = 330 / (crop_box[2] - crop_box[0]), 170 / (crop_box[3] - crop_box[1])
        od.rectangle(((target[0] - crop_box[0]) * scale_x, (target[1] - crop_box[1]) * scale_y, (target[2] - crop_box[0]) * scale_x, (target[3] - crop_box[1]) * scale_y), outline=(220, 45, 45), width=4)
        board.paste(original, (24, y))
        board.paste(checker, (380, y))
        d.text((34, y + 8), "母稿+缺口", fill=(150, 35, 35), font=font(14), stroke_width=2, stroke_fill="white")
        d.text((390, y + 8), "补画候选", fill=(35, 80, 135), font=font(14), stroke_width=2, stroke_fill="white")
        d.text((740, y + 18), f"{layer_id}", fill=(30, 70, 130), font=font(18))
        d.text((740, y + 58), note, fill=(55, 55, 55), font=font(16))
        d.text((740, y + 98), f"目标 {target} ← 参考 {donor or '衣身平均色'}", fill=(90, 90, 90), font=font(14))
        y += 250
    qa_path = ROOT / "qa" / "gate8-hidden-fill-contact-sheet.png"
    board.save(qa_path, quality=95)
    manifest = {"stage": "gate8-hidden-fill-candidates", "status": "candidate_only_pending_visual_review", "canvas": [512, 1086], "source": "source/masters/gate3-color-target-v1.png", "entries": entries, "rules": {"candidateOnly": True, "notFormalExport": True, "noImageGenUsed": True}}
    (ROOT / "qa" / "hidden-fill-candidates.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(qa_path)


if __name__ == "__main__":
    main()
