from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
CONTRACT = ROOT / "blueprints" / "v2-lower-body-ownership-contract.json"
HIDDEN = ROOT / "blueprints" / "v2-hidden-thigh-contract.json"
OUT_DIR = ROOT / "qa" / "v2-lower-body-candidate-layers"
OUT_META = ROOT / "qa" / "v2-lower-body-candidate-layers.json"
OUT_SHEET = ROOT / "qa" / "v2-lower-body-candidate-contact-sheet.png"


PALETTE = {
    "skirt": (38, 37, 42, 255),
    "leg_screen_left": (246, 216, 210, 255),
    "leg_screen_right": (246, 216, 210, 255),
    "sock_screen_left": (239, 238, 235, 255),
    "sock_screen_right": (239, 238, 235, 255),
    "shoe_screen_left": (224, 224, 222, 255),
    "shoe_screen_right": (224, 224, 222, 255),
}


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def mask_layer(canvas, polygons, color):
    layer = Image.new("RGBA", canvas, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for polygon in polygons:
        draw.polygon([tuple(point) for point in polygon], fill=color)
    return layer


def main():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    hidden = json.loads(HIDDEN.read_text(encoding="utf-8"))
    canvas = tuple(contract["canvas"])
    group_map = {group["id"]: group for group in contract["groups"]}
    hidden_map = {item["id"]: item for item in hidden["frontHiddenCandidates"]}
    polygons = {}
    for leg_id in ("leg_screen_left", "leg_screen_right"):
        polygons[leg_id] = [group_map[leg_id]["polygon"]]
    polygons["leg_screen_left"].append(hidden_map["leg_screen_left_hidden_thigh"]["polygon"])
    polygons["leg_screen_right"].append(hidden_map["leg_screen_right_hidden_thigh"]["polygon"])
    for group_id in ("skirt", "sock_screen_left", "sock_screen_right", "shoe_screen_left", "shoe_screen_right"):
        polygons[group_id] = [group_map[group_id]["polygon"]]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    layers = []
    for layer_id, layer_polygons in polygons.items():
        layer = mask_layer(canvas, layer_polygons, PALETTE[layer_id])
        path = OUT_DIR / f"{layer_id}.png"
        layer.save(path)
        layers.append({
            "id": layer_id,
            "path": path.relative_to(ROOT).as_posix(),
            "sourceGeometry": "blueprints/v2-lower-body-ownership-contract.json plus v2-hidden-thigh-contract.json" if layer_id.startswith("leg_") else "blueprints/v2-lower-body-ownership-contract.json",
            "status": "candidate_only_no_texture_no_mesh",
            "rgba": True,
            "fullCanvas": True
        })

    line = Image.open(LINE).convert("RGB")
    reconstruction = Image.new("RGBA", canvas, (255, 255, 255, 0))
    # Back-to-front: legs, skirt, socks, shoes.
    for layer_id in ("leg_screen_left", "leg_screen_right", "skirt", "sock_screen_left", "sock_screen_right", "shoe_screen_left", "shoe_screen_right"):
        reconstruction.alpha_composite(Image.open(OUT_DIR / f"{layer_id}.png").convert("RGBA"))
    board = Image.new("RGB", (1200, 650), "white")
    board.paste(line.crop((110, 540, 400, 1065)).resize((360, 650), Image.Resampling.NEAREST), (25, 0))
    board.paste(reconstruction.crop((110, 540, 400, 1065)).resize((360, 650), Image.Resampling.NEAREST).convert("RGB"), (405, 0))
    d = ImageDraw.Draw(board)
    d.text((32, 16), "线稿参考", fill=(30, 35, 45), font=font(21))
    d.text((412, 16), "层-only 平色重建（候选）", fill=(30, 35, 45), font=font(21))
    d.text((800, 22), "候选层", fill=(30, 35, 45), font=font(21))
    y = 65
    for item in layers:
        d.text((800, y), f"• {item['id']}", fill=(70, 75, 85), font=font(16))
        y += 31
    d.text((800, 300), "检查重点", fill=(180, 55, 45), font=font(18))
    d.text((800, 335), "1. 裙摆下没有断腿", fill=(70, 75, 85), font=font(15))
    d.text((800, 365), "2. 袜口有少量重叠", fill=(70, 75, 85), font=font(15))
    d.text((800, 395), "3. 鞋层不带袜子", fill=(70, 75, 85), font=font(15))
    d.text((800, 450), "状态：候选层，未进网格/动作。", fill=(180, 55, 45), font=font(15))
    board.save(OUT_SHEET)
    OUT_META.write_text(json.dumps({
        "status": "candidate_only_no_texture_no_mesh",
        "canvas": list(canvas),
        "layers": layers,
        "drawOrder": ["leg_screen_left", "leg_screen_right", "skirt", "sock_screen_left", "sock_screen_right", "shoe_screen_left", "shoe_screen_right"],
        "paletteSource": "flat neutral colors sampled/approximated from gate3-color-target-v1; geometry remains line-art contracts",
        "missingByDesign": ["skirt_hidden_back_layer", "texture", "artmesh", "motion", "physics"]
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT_SHEET)


if __name__ == "__main__":
    main()
