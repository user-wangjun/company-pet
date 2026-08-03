from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageChops


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
COLOR = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
CONTRACT = ROOT / "blueprints" / "v2-eye-lineart-boundary-contract.json"
OUT_DIR = ROOT / "qa" / "v2-eye-color-candidates"


PALETTE = {
    "sclera": [247, 231, 224, 255],
    "iris": [94, 72, 68, 255],
    "pupil": [28, 24, 23, 255],
    "highlight": [252, 246, 242, 255],
    "upper_lid": [48, 38, 36, 255],
    "lower_lid": [151, 116, 108, 230]
}


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def checker(size):
    out = Image.new("RGB", size, (235, 235, 235))
    d = ImageDraw.Draw(out)
    for yy in range(0, size[1], 18):
        for xx in range(0, size[0], 18):
            if (xx // 18 + yy // 18) % 2:
                d.rectangle((xx, yy, xx + 17, yy + 17), fill=(250, 250, 250))
    return out


def main():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    line = Image.open(LINE).convert("RGB")
    color = Image.open(COLOR).convert("RGB")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    composites = {}
    for side in ("R", "L"):
        z = contract["zones"][side]
        upper = [tuple(x) for x in z["upperTraceCandidate"]]
        lower = [tuple(x) for x in z["lowerTraceCandidate"]]
        opening = upper + list(reversed(lower))
        center = tuple(z["irisCenterCandidate"])
        radius = z["irisRadiusCandidate"]
        opening_mask = Image.new("L", line.size, 0)
        ImageDraw.Draw(opening_mask).polygon(opening, fill=255)

        def solid(color_value, mask):
            layer = Image.new("RGBA", line.size, tuple(color_value))
            layer.putalpha(mask)
            return layer

        sclera = solid(PALETTE["sclera"], opening_mask)
        iris_mask = Image.new("L", line.size, 0)
        ImageDraw.Draw(iris_mask).ellipse((center[0]-radius, center[1]-radius, center[0]+radius, center[1]+radius), fill=255)
        iris_mask = ImageChops.multiply(iris_mask, opening_mask)
        iris = solid(PALETTE["iris"], iris_mask)
        pupil_radius = 4
        pupil_mask = Image.new("L", line.size, 0)
        ImageDraw.Draw(pupil_mask).ellipse((center[0]-pupil_radius, center[1]-pupil_radius, center[0]+pupil_radius, center[1]+pupil_radius), fill=255)
        pupil_mask = ImageChops.multiply(pupil_mask, opening_mask)
        pupil = solid(PALETTE["pupil"], pupil_mask)
        highlight_mask = Image.new("L", line.size, 0)
        ImageDraw.Draw(highlight_mask).ellipse((center[0]-3, center[1]-5, center[0], center[1]-2), fill=255)
        highlight_mask = ImageChops.multiply(highlight_mask, opening_mask)
        highlight = solid(PALETTE["highlight"], highlight_mask)
        upper_lid = Image.new("RGBA", line.size, (0,0,0,0)); ImageDraw.Draw(upper_lid).line(upper, fill=tuple(PALETTE["upper_lid"]), width=2, joint="curve")
        lower_lid = Image.new("RGBA", line.size, (0,0,0,0)); ImageDraw.Draw(lower_lid).line(lower, fill=tuple(PALETTE["lower_lid"]), width=2, joint="curve")
        layers = {"sclera": sclera, "iris": iris, "pupil": pupil, "highlight": highlight, "upper_lid": upper_lid, "lower_lid": lower_lid}
        comp = Image.new("RGBA", line.size, (0,0,0,0))
        for role, image in layers.items():
            path = OUT_DIR / f"eye_{side}_{role}.png"
            image.save(path)
            comp = Image.alpha_composite(comp, image)
            entries.append({"id": f"eye_{side}_{role}", "side": side, "role": role, "path": f"qa/v2-eye-color-candidates/{path.name}", "status": "color_candidate_only"})
        composites[side] = comp

    box = (190, 115, 320, 160)
    scale = 4
    size = ((box[2]-box[0])*scale, (box[3]-box[1])*scale)
    board = Image.new("RGB", (1700, 650), "white")
    d = ImageDraw.Draw(board)
    d.text((24,18), "V2 双眼颜色候选（线稿定形，彩稿仅取色）", fill=(25,25,30), font=font(25))
    d.text((24,55), "候选颜色来自彩稿眼部色调；几何仍完全取自 V2 线稿合同，不复用彩稿像素坐标。", fill=(150,50,45), font=font(16))
    line_crop = line.crop(box).resize(size, Image.Resampling.NEAREST)
    color_crop = color.crop(box).resize(size, Image.Resampling.NEAREST)
    board.paste(line_crop, (24,100)); board.paste(color_crop, (574,100))
    d.text((34,110), "线稿边界", fill=(25,55,95), font=font(16), stroke_width=2, stroke_fill="white")
    d.text((584,110), "彩稿取色参考", fill=(25,55,95), font=font(16), stroke_width=2, stroke_fill="white")
    combined = Image.new("RGBA", line.size, (0,0,0,0))
    for side in ("R","L"):
        combined = Image.alpha_composite(combined, composites[side])
    cc = combined.crop(box).resize(size, Image.Resampling.NEAREST)
    panel = checker(size); panel.paste(cc.convert("RGB"), mask=cc.getchannel("A"))
    board.paste(panel, (1124,100))
    d.text((1134,110), "线稿形状上的颜色候选", fill=(25,55,95), font=font(16), stroke_width=2, stroke_fill="white")
    d.text((24,520), "当前未加入：睫毛精修、虹膜纹理渐变、闭眼形、视线参数。", fill=(150,50,45), font=font(16))
    qa = ROOT / "qa" / "v2-eye-color-candidate-contact-sheet.png"
    board.save(qa, quality=95)
    manifest = {"status":"color_candidate_only_no_motion", "canvas":[512,1086], "palette":PALETTE, "paletteSource":"source/masters/gate3-color-target-v1.png (color sampling only)", "geometrySource":"blueprints/v2-eye-lineart-boundary-contract.json", "entries":entries, "missingByDesign":["eyelash_refinement","iris_gradient","closed_eye_keyform","gaze_parameter"]}
    (ROOT / "qa" / "v2-eye-color-candidates.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(qa)


if __name__ == "__main__":
    main()
