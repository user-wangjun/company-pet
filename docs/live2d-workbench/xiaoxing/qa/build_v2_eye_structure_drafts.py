from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
OUT_DIR = ROOT / "qa" / "v2-eye-structure-drafts"
CONTRACT = ROOT / "blueprints" / "v2-eye-lineart-boundary-contract.json"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def full_layer(size, draw_fn):
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(out))
    return out


def main():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    line = Image.open(LINE).convert("RGB")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    composites = {}
    for side in ("R", "L"):
        z = contract["zones"][side]
        upper = [tuple(p) for p in z["upperTraceCandidate"]]
        lower = [tuple(p) for p in z["lowerTraceCandidate"]]
        center = tuple(z["irisCenterCandidate"])
        radius = z["irisRadiusCandidate"]
        x0, y0, x1, y1 = z["reviewBox"]
        # Eye opening/mask: only the candidate polygon between the traced upper and lower curves.
        opening_polygon = upper + list(reversed(lower))
        mask = full_layer(line.size, lambda d: d.polygon(opening_polygon, fill=(255, 255, 255, 180)))
        # Structure lines remain neutral dark gray; these are not final colored eyelash textures.
        upper_layer = full_layer(line.size, lambda d: d.line(upper, fill=(55, 55, 55, 255), width=2, joint="curve"))
        lower_layer = full_layer(line.size, lambda d: d.line(lower, fill=(95, 95, 95, 230), width=2, joint="curve"))
        iris_layer = full_layer(line.size, lambda d: d.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), outline=(80, 80, 80, 230), width=2))
        pupil_radius = max(3, radius // 2)
        pupil_layer = full_layer(line.size, lambda d: d.ellipse((center[0] - pupil_radius, center[1] - pupil_radius, center[0] + pupil_radius, center[1] + pupil_radius), outline=(40, 40, 40, 240), width=2))
        layers = {"eye_mask": mask, "upper_lid": upper_layer, "lower_lid": lower_layer, "iris_boundary": iris_layer, "pupil_boundary": pupil_layer}
        comp = Image.new("RGBA", line.size, (0, 0, 0, 0))
        for name, image in layers.items():
            path = OUT_DIR / f"eye_{side}_{name}.png"
            image.save(path)
            comp = Image.alpha_composite(comp, image)
            entries.append({"id": f"eye_{side}_{name}", "side": side, "role": name, "path": f"qa/v2-eye-structure-drafts/{path.name}", "status": "lineart_structure_draft_only", "source": "v2-eye-lineart-boundary-contract.json"})
        composites[side] = comp

    # A compact 1:6 review board; all panels use the same crop and aspect ratio.
    box = (190, 115, 320, 160)
    scale = 4
    board = Image.new("RGB", (1700, 700), "white")
    d = ImageDraw.Draw(board)
    d.text((24, 18), "V2 双眼线稿结构层草稿（仅结构，不是最终纹理）", fill=(25, 25, 30), font=font(25))
    d.text((24, 55), "每个小图都来自同一线稿坐标；彩色、睫毛细节和眨眼参数尚未加入。", fill=(150, 50, 45), font=font(16))
    line_crop = line.crop(box).resize(((box[2] - box[0]) * scale, (box[3] - box[1]) * scale), Image.Resampling.NEAREST)
    board.paste(line_crop, (24, 100))
    d.text((34, 110), "线稿原图", fill=(25, 55, 95), font=font(16), stroke_width=2, stroke_fill="white")
    for idx, (side, comp) in enumerate(composites.items()):
        crop = comp.crop(box).resize(((box[2] - box[0]) * scale, (box[3] - box[1]) * scale), Image.Resampling.NEAREST)
        checker = Image.new("RGB", crop.size, (235, 235, 235))
        cd = ImageDraw.Draw(checker)
        for yy in range(0, crop.height, 18):
            for xx in range(0, crop.width, 18):
                if (xx // 18 + yy // 18) % 2:
                    cd.rectangle((xx, yy, xx + 17, yy + 17), fill=(250, 250, 250))
        checker.paste(crop.convert("RGB"), mask=crop.getchannel("A"))
        board.paste(checker, (24 + (idx + 1) * 550, 100))
        d.text((34 + (idx + 1) * 550, 110), f"角色{'右' if side == 'R' else '左'}眼结构层", fill=(25, 55, 95), font=font(16), stroke_width=2, stroke_fill="white")
    y = 580
    for name in ("eye_mask", "upper_lid", "lower_lid", "iris_boundary", "pupil_boundary"):
        d.text((24 + (list(("eye_mask", "upper_lid", "lower_lid", "iris_boundary", "pupil_boundary")).index(name)) * 250, y), name, fill=(55, 75, 105), font=font(15))
    d.text((24, 625), "通过条件：结构层必须贴合线稿，且不得越出 reviewBox；仍需人工检查后才可进入彩色纹理阶段。", fill=(150, 50, 45), font=font(16))
    qa = ROOT / "qa" / "v2-eye-structure-contact-sheet.png"
    board.save(qa, quality=95)
    (ROOT / "qa" / "v2-eye-structure-drafts.json").write_text(json.dumps({"status": "lineart_structure_draft_only", "canvas": [512, 1086], "entries": entries, "missingByDesign": ["colored_sclera", "iris_texture", "pupil_texture", "highlight", "eyelash_texture", "blink_keyforms"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(qa)


if __name__ == "__main__":
    main()
