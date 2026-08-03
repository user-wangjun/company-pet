from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
CONTRACT = ROOT / "blueprints" / "v2-upper-body-ownership-contract.json"
OUT_DIR = ROOT / "qa" / "v2-upper-body-candidate-layers"
OUT_META = ROOT / "qa" / "v2-upper-body-candidate-layers.json"
OUT_SHEET = ROOT / "qa" / "v2-upper-body-candidate-contact-sheet.png"


PALETTE = {
    "neck": (246, 216, 210, 255),
    "torso_tshirt_core": (238, 238, 229, 255),
    "sleeve_screen_left": (238, 238, 229, 255),
    "sleeve_screen_right": (238, 238, 229, 255),
    "arm_screen_left_forearm": (246, 216, 210, 255),
    "arm_screen_right_forearm": (246, 216, 210, 255),
    "hand_screen_left": (246, 216, 210, 255),
    "hand_screen_right": (246, 216, 210, 255),
    "necklace": (180, 170, 135, 255),
}


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    canvas = tuple(data["canvas"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    layers = []
    for group in data["groups"]:
        layer_id = group["id"]
        image = Image.new("RGBA", canvas, (0, 0, 0, 0))
        ImageDraw.Draw(image).polygon([tuple(point) for point in group["polygon"]], fill=PALETTE[layer_id])
        path = OUT_DIR / f"{layer_id}.png"
        image.save(path)
        layers.append({"id": layer_id, "path": path.relative_to(ROOT).as_posix(), "status": "candidate_only_no_texture_no_mesh", "fullCanvas": True, "rgba": True})

    # Back-to-front reconstruction: neck, torso, sleeves, forearms, hands, necklace.
    order = ["neck", "torso_tshirt_core", "sleeve_screen_left", "sleeve_screen_right", "arm_screen_left_forearm", "arm_screen_right_forearm", "hand_screen_left", "hand_screen_right", "necklace"]
    reconstruction = Image.new("RGBA", canvas, (0, 0, 0, 0))
    for layer_id in order:
        reconstruction.alpha_composite(Image.open(OUT_DIR / f"{layer_id}.png").convert("RGBA"))

    line = Image.open(LINE).convert("RGB")
    board = Image.new("RGB", (1320, 760), "white")
    crop = (65, 170, 450, 680)
    line_crop = line.crop(crop).resize((420, 520), Image.Resampling.NEAREST)
    recon_crop_rgba = reconstruction.crop(crop).resize((420, 520), Image.Resampling.NEAREST)
    recon_background = Image.new("RGBA", recon_crop_rgba.size, (255, 255, 255, 255))
    recon_background.alpha_composite(recon_crop_rgba)
    recon_crop = recon_background.convert("RGB")
    board.paste(line_crop, (20, 80))
    board.paste(recon_crop, (460, 80))
    d = ImageDraw.Draw(board)
    d.text((26, 24), "线稿参考", fill=(30,35,45), font=font(23))
    d.text((466, 24), "层-only 平色重建（候选）", fill=(30,35,45), font=font(23))
    d.text((900, 24), "候选层", fill=(30,35,45), font=font(23))
    y = 78
    for item in layers:
        d.text((900, y), f"• {item['id']}", fill=(70,75,85), font=font(15))
        y += 31
    d.text((900, 410), "检查重点", fill=(180,55,45), font=font(18))
    for idx, label in enumerate(("袖子不带前臂", "手层不带袖子", "项链不并入衣身", "隐藏部分无断洞")):
        d.text((900, 445 + idx*30), f"{idx+1}. {label}", fill=(70,75,85), font=font(14))
    d.text((900, 610), "状态：候选层，未进网格/动作。", fill=(180,55,45), font=font(15))
    board.save(OUT_SHEET)
    OUT_META.write_text(json.dumps({"status": "candidate_only_no_texture_no_mesh", "canvas": list(canvas), "layers": layers, "drawOrder": order, "missingByDesign": ["shirt_print", "hair_occlusion_fill", "artmesh", "motion", "physics"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT_SHEET)


if __name__ == "__main__":
    main()
