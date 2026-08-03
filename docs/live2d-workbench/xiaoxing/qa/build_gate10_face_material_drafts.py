from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
OUT_DIR = ROOT / "qa" / "draft-face-layers"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


REGIONS = {
    "face_base": ([(185, 95), (316, 95), (329, 165), (310, 225), (272, 252), (232, 252), (195, 225), (174, 165)], "skin"),
    "ear_R": ([(174, 145), (193, 140), (196, 205), (177, 208)], "skin"),
    "ear_L": ([(313, 140), (335, 145), (333, 208), (311, 205)], "skin"),
    "brow_R": ([(207, 121), (242, 121), (242, 137), (207, 137)], "vector_brow"),
    "brow_L": ([(267, 121), (302, 121), (302, 137), (267, 137)], "vector_brow"),
    "nose": ([(242, 162), (265, 162), (265, 191), (242, 191)], "nose"),
    "mouth_upper": ([(229, 196), (276, 196), (276, 211), (229, 211)], "dark"),
    "mouth_lower": ([(229, 205), (276, 205), (276, 220), (229, 220)], "lip"),
    "necklace_chain": ([(226, 238), (286, 238), (278, 282), (234, 282)], "vector_chain"),
    "necklace_pendant": ([(246, 276), (266, 276), (266, 302), (246, 302)], "vector_pendant"),
}


def masked_layer(source: Image.Image, points, kind: str) -> Image.Image:
    if kind.startswith("vector_"):
        out = Image.new("RGBA", source.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(out)
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        if kind == "vector_brow":
            d.arc((x0, y0, x1, y1 + 8), 205, 335, fill=(69, 55, 50, 230), width=2)
        elif kind == "vector_chain":
            mid = (x0 + x1) // 2
            d.line((x0, y0, mid, y1, x1, y0), fill=(132, 128, 124, 220), width=1)
        else:
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            d.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), outline=(128, 124, 120, 230), width=2)
            d.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=(156, 151, 146, 230))
        return out
    mask = Image.new("L", source.size, 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    rgb = source.convert("RGB")
    px, mp = rgb.load(), mask.load()
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    for y in range(max(0, min(ys)), min(source.height, max(ys) + 1)):
        for x in range(max(0, min(xs)), min(source.width, max(xs) + 1)):
            if not mp[x, y]:
                continue
            r, g, b = px[x, y]
            lum = (r + g + b) / 3
            keep = True
            if kind == "skin":
                keep = r > 175 and g > 135 and b > 120 and r - g > 7 and g - b > 2 and r < 252 and b < 245
            elif kind == "dark":
                keep = lum < 155
            elif kind == "nose":
                keep = lum < 232 and r >= b
            elif kind == "lip":
                keep = r > g and r > b and lum < 235
            if not keep:
                mp[x, y] = 0
    layer = source.copy()
    layer.putalpha(mask)
    return layer


def checker(size):
    out = Image.new("RGB", size, (235, 235, 235))
    d = ImageDraw.Draw(out)
    for yy in range(0, size[1], 18):
        for xx in range(0, size[0], 18):
            if (xx // 18 + yy // 18) % 2:
                d.rectangle((xx, yy, xx + 17, yy + 17), fill=(250, 250, 250))
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = Image.open(MASTER).convert("RGBA")
    layers = {}
    entries = []
    for layer_id, (points, kind) in REGIONS.items():
        layer = masked_layer(source, points, kind)
        path = OUT_DIR / f"{layer_id}.png"
        layer.save(path)
        layers[layer_id] = layer
        entries.append({"id": layer_id, "path": f"qa/draft-face-layers/{path.name}", "status": "visible_only_draft", "kind": kind})

    composite = Image.new("RGBA", source.size, (0, 0, 0, 0))
    for layer_id in ("ear_R", "ear_L", "face_base"):
        composite = Image.alpha_composite(composite, layers[layer_id])
    for side in ("R", "L"):
        eye_path = ROOT / "qa" / "draft-eye-layers" / f"eye_{side}_composite.png"
        if eye_path.exists():
            composite = Image.alpha_composite(composite, Image.open(eye_path).convert("RGBA"))
    for layer_id in ("brow_R", "brow_L", "nose", "mouth_upper", "mouth_lower", "necklace_chain", "necklace_pendant"):
        composite = Image.alpha_composite(composite, layers[layer_id])

    board = Image.new("RGB", (1600, 980), "white")
    d = ImageDraw.Draw(board)
    d.text((24, 18), "小星 Gate 10 脸部与口型素材草稿审查", fill=(25, 25, 30), font=font(26))
    d.text((24, 55), "眼睛沿用 Gate 4；本轮补齐脸底、耳朵、眉鼻嘴和项链的可见层。", fill=(55, 75, 105), font=font(17))
    face_crop = (155, 70, 350, 320)
    source_crop = source.crop(face_crop).resize((430, 550)).convert("RGB")
    comp_crop = composite.crop(face_crop).resize((430, 550))
    check = checker((430, 550))
    check.paste(comp_crop.convert("RGB"), mask=comp_crop.getchannel("A"))
    board.paste(source_crop, (24, 100))
    board.paste(check, (480, 100))
    d.text((34, 110), "彩色母稿", fill=(35, 35, 35), font=font(15), stroke_width=2, stroke_fill="white")
    d.text((490, 110), "脸部草稿合成", fill=(35, 75, 135), font=font(15), stroke_width=2, stroke_fill="white")
    x0, y0 = 940, 105
    for i, layer_id in enumerate(REGIONS):
        thumb = layers[layer_id].crop(face_crop).resize((190, 250))
        cell = checker((190, 250))
        cell.paste(thumb.convert("RGB"), mask=thumb.getchannel("A"))
        x = x0 + (i % 3) * 210
        y = y0 + (i // 3) * 210
        board.paste(cell.resize((180, 190)), (x, y))
        d.text((x, y + 192), layer_id, fill=(50, 70, 100), font=font(13))
    d.text((24, 700), "尚未生成：mouth_inner、tongue。正面母稿为闭口状态，这两层必须在正式口型设计时单独补画，不能从闭口像素伪造。", fill=(150, 55, 45), font=font(17))
    qa_path = ROOT / "qa" / "gate10-face-material-contact-sheet.png"
    board.save(qa_path, quality=95)
    manifest = {"stage": "gate10-face-material-draft", "status": "self_review_pending_hidden_mouth", "canvas": [512, 1086], "layers": entries, "reused": ["qa/draft-eye-layers/eye_R_composite.png", "qa/draft-eye-layers/eye_L_composite.png"], "missingByDesign": ["mouth_inner", "tongue"], "rules": {"draftOnly": True, "preserveSourceIdentity": True, "doNotFakeClosedMouthInteriors": True}}
    (ROOT / "qa" / "draft-face-layers.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(qa_path)


if __name__ == "__main__":
    main()
