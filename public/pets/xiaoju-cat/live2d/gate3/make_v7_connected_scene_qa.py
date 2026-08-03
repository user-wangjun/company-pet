import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
CANDIDATES = ROOT / "candidates"
QA = ROOT / "qa"
SCENE = ROOT.parent / "planet-scene-source" / "layers-v2"
CANVAS = (1370, 1148)


def remove_green(source: Image.Image) -> Image.Image:
    source = source.convert("RGBA")
    result = Image.new("RGBA", source.size, (0, 0, 0, 0))
    src = source.load()
    dst = result.load()
    for y in range(source.height):
        for x in range(source.width):
            r, g, b, a = src[x, y]
            excess = g - max(r, b)
            if excess >= 72:
                continue
            if excess > 18:
                a = round(a * (72 - excess) / 54)
            if a <= 0:
                continue
            # Suppress the green fringe without changing opaque orange fur.
            if excess > 0:
                g = min(g, max(r, b) + 4)
            dst[x, y] = (r, g, b, a)
    return result


def fit_cat(cat: Image.Image, width: int, x: int, y: int) -> Image.Image:
    bbox = cat.getchannel("A").getbbox()
    crop = cat.crop(bbox)
    height = round(crop.height * width / crop.width)
    crop = crop.resize((width, height), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    layer.alpha_composite(crop, (x, y))
    return layer


def composite_scene(cat_layer: Image.Image) -> Image.Image:
    scene = Image.open(SCENE / "00_Stars_Background.png").convert("RGBA")
    scene.alpha_composite(cat_layer)
    scene.alpha_composite(Image.open(SCENE / "50_Planet_Foreground.png").convert("RGBA"))
    return scene


def main() -> None:
    chroma = Image.open(CANDIDATES / "xiaoju-connected-prone-v7-chromakey.png")
    alpha = remove_green(chroma)
    alpha_path = CANDIDATES / "xiaoju-connected-prone-v7-alpha.png"
    alpha.save(alpha_path)

    variants = [
        {"id": "A", "width": 1280, "x": 20, "y": 62},
        {"id": "B", "width": 1340, "x": -5, "y": 38},
        {"id": "C", "width": 1215, "x": 72, "y": 90},
    ]
    sheet = Image.new("RGBA", (685 * 3, 610), (20, 22, 28, 255))
    draw = ImageDraw.Draw(sheet)
    for index, variant in enumerate(variants):
        cat_layer = fit_cat(alpha, variant["width"], variant["x"], variant["y"])
        scene = composite_scene(cat_layer)
        scene_path = QA / f"gate3-v7-connected-scene-{variant['id']}.png"
        scene.save(scene_path)
        preview = scene.resize((685, 574), Image.Resampling.LANCZOS)
        sheet.alpha_composite(preview, (index * 685, 36))
        draw.text((index * 685 + 12, 10), f"{variant['id']} width={variant['width']} x={variant['x']} y={variant['y']}", fill=(255, 255, 255, 255))
    sheet_path = QA / "gate3-v7-connected-scene-alignment-sheet.png"
    sheet.save(sheet_path)

    alpha_bbox = alpha.getchannel("A").getbbox()
    report = {
        "schemaVersion": 1,
        "candidate": "xiaoju-connected-prone-v7",
        "sourceRole": "single coherent anatomy master before layer separation",
        "alphaBbox": list(alpha_bbox) if alpha_bbox else None,
        "transparentCorners": [alpha.getpixel(point)[3] for point in ((0, 0), (alpha.width - 1, 0), (0, alpha.height - 1), (alpha.width - 1, alpha.height - 1))],
        "variants": variants,
        "previousV5CompositeVerdict": "rejected_disconnected_anatomy_and_mixed_pose_sources",
        "gate3Pass": False,
        "nextGate": "human choose connected scene alignment before any v7 separation",
    }
    report_path = QA / "gate3-v7-connected-scene-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(alpha_path)
    print(sheet_path)
    print(report_path)


if __name__ == "__main__":
    main()
