from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_gate3_hand_partition import partition


ROOT = Path(__file__).resolve().parents[1]
MASTERS = ROOT / "source" / "masters"
QA = ROOT / "qa"
OUT = QA / "draft-hand-layers"
AUDIT = ROOT / "audit"


def font(size):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)
    except OSError:
        return ImageFont.load_default()


def checker(size, cell=16):
    image = Image.new("RGB", size, (245, 245, 245))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if ((x // cell) + (y // cell)) % 2 == 0:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(225, 225, 225))
    return image.convert("RGBA")


def main():
    color = Image.open(MASTERS / "gate3-color-target-v1.png").convert("RGB")
    specs = {"R": (65, 545, 140, 635), "L": (372, 545, 445, 635)}
    names = ("palm", "thumb", "index", "middle", "ring", "little")
    labels = {"palm": "掌心／腕根", "thumb": "拇指", "index": "食指", "middle": "中指", "ring": "无名指", "little": "小指"}
    OUT.mkdir(parents=True, exist_ok=True)
    contact = Image.new("RGB", (1500, 620), "white")
    draw = ImageDraw.Draw(contact)
    draw.text((24, 16), "小星手部草稿层（仅 QA，不是正式 Cubism 素材）", fill=(25, 25, 25), font=font(24))
    draw.text((24, 52), "每格都是 512×1086 全画布透明 PNG；合成时仍使用原彩色目标像素。", fill=(80, 80, 80), font=font(16))
    manifest = {"status": "qa_draft_only", "canvas": [512, 1086], "layers": []}
    for side_index, side in enumerate(("R", "L")):
        masks = partition(color, side, specs[side])
        side_name = "角色右手（画面左侧）" if side == "R" else "角色左手（画面右侧）"
        side_x = 24 + side_index * 740
        draw.text((side_x, 95), side_name, fill=(35, 85, 135), font=font(20))
        for index, name in enumerate(names):
            mask = masks[name]
            rgba = Image.new("RGBA", color.size, (0, 0, 0, 0))
            rgba.paste(color.convert("RGBA"), (0, 0), mask)
            path = OUT / f"{side}_{name}.png"
            rgba.save(path)
            manifest["layers"].append({"side": side, "name": name, "label": labels[name], "path": str(path.relative_to(ROOT)).replace("\\", "/"), "status": "draft"})
            x = side_x + (index % 3) * 245
            y = 125 + (index // 3) * 185
            panel = checker((220, 155))
            crop = rgba.crop(specs[side]).resize((220, 264))
            panel = checker((220, 264))
            panel.alpha_composite(crop)
            contact.paste(panel.convert("RGB"), (x, y))
            draw.rectangle((x, y, x + 220, y + 264), outline=(190, 195, 205), width=2)
            draw.text((x + 7, y + 7), labels[name], fill=(35, 35, 35), font=font(15), stroke_width=2, stroke_fill="white")
    draw.text((24, 592), "草稿层只验证：每根手指是否独立、透明范围是否正确、合成后是否仍与原图贴合。确认前不会导入 Cubism。", fill=(35, 85, 135), font=font(16))
    contact.save(QA / "gate3-hand-draft-layer-contact-sheet.png", quality=95)
    (QA / "draft-hand-layers.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Validate the files after writing them, rather than trusting the in-memory
    # masks. This catches wrong canvas sizes, accidental alpha overlap, missing
    # pixels, and color changes introduced during export.
    validation = {"status": "pass", "sides": {}}
    for side in ("R", "L"):
        files = [Image.open(OUT / f"{side}_{name}.png").convert("RGBA") for name in names]
        dimensions_ok = all(image.size == color.size for image in files)
        pixels = [image.load() for image in files]
        source_pixels = color.load()
        bbox = specs[side]
        union_pixels = overlap_pixels = rgb_mismatch_pixels = 0
        for y in range(bbox[1], bbox[3]):
            for x in range(bbox[0], bbox[2]):
                visible = [pixel[x, y] for pixel in pixels if pixel[x, y][3] > 0]
                if visible:
                    union_pixels += 1
                    if len(visible) > 1:
                        overlap_pixels += 1
                    if visible[-1][:3] != source_pixels[x, y]:
                        rgb_mismatch_pixels += 1
        skin_mask = partition(color, side, bbox)["skin"].convert("L")
        expected_skin = skin_mask.histogram()[255]
        side_pass = dimensions_ok and overlap_pixels == 0 and rgb_mismatch_pixels == 0 and union_pixels == expected_skin
        validation["sides"][side] = {
            "dimensionsOk": dimensions_ok,
            "layerCount": len(files),
            "unionPixels": union_pixels,
            "expectedPixels": expected_skin,
            "missingPixels": expected_skin - union_pixels,
            "overlapPixels": overlap_pixels,
            "rgbMismatchPixels": rgb_mismatch_pixels,
            "passed": side_pass,
        }
        if not side_pass:
            validation["status"] = "fail"
    (AUDIT / "gate3-hand-draft-validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    if validation["status"] != "pass":
        raise SystemExit("hand draft export validation failed")


if __name__ == "__main__":
    main()
