from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps


PET = Path(__file__).resolve().parents[2]
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
V4 = X6 / "x6-joint-safe-motion-bundle-contract-v4.json"
V10 = X6 / "x6-front-complete-overlap-contract-v10.json"
GUIDE = X6 / "hidden-texture-guides-v11" / "head-base-texture-alpha.png"
REFERENCE = X6 / "front-user-segmentation-v8" / "front-reconstruction.png"
OUTPUT = X6 / "front-head-hidden-texture-v11"
CANVAS = (650, 887)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def checker(size: tuple[int, int], block: int = 14) -> Image.Image:
    image = Image.new("RGBA", size, (249, 250, 251, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(226, 232, 236, 255))
    return image


def place(path: str, bounds: list[int]) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.alpha_composite(Image.open(PET / path).convert("RGBA"), (bounds[0], bounds[1]))
    return canvas


def fit(image: Image.Image, size: tuple[int, int], padding: int = 10) -> Image.Image:
    target = checker(size)
    source = image.copy()
    source.thumbnail((size[0] - padding * 2, size[1] - padding * 2), Image.Resampling.LANCZOS)
    target.alpha_composite(source, ((size[0] - source.width) // 2, (size[1] - source.height) // 2))
    return target


def load_v10_layers(contract: dict) -> dict[str, Image.Image]:
    return {row["id"]: place(row["file"], row["canvasBounds"]) for row in contract["layers"]}


def compose(order: list[str], layers: dict[str, Image.Image], offsets: dict[str, tuple[int, int]] | None = None) -> Image.Image:
    offsets = offsets or {}
    result = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer_id in order:
        dx, dy = offsets.get(layer_id, (0, 0))
        result.alpha_composite(layers[layer_id], (dx, dy))
    return result


def main() -> None:
    v4 = json.loads(V4.read_text(encoding="utf-8"))
    v10 = json.loads(V10.read_text(encoding="utf-8"))
    v4_head = next(row for row in v4["exports"] if row["view"] == "front" and row["bundle"] == "head")
    v10_head = next(row for row in v10["layers"] if row["id"] == "head")

    original_visible = place(v4_head["visibleFile"], v4_head["visibleBounds"])
    rejected_head = place(v10_head["file"], v10_head["canvasBounds"])
    target_alpha = rejected_head.getchannel("A")
    target_bounds = target_alpha.getbbox()
    if target_bounds is None:
        raise RuntimeError("v10 head mask is empty")

    guide = Image.open(GUIDE).convert("RGBA")
    guide_bounds = guide.getchannel("A").getbbox()
    if guide_bounds is None:
        raise RuntimeError("head texture guide is empty")
    guide = guide.crop(guide_bounds)
    fitted = ImageOps.fit(
        guide,
        (target_bounds[2] - target_bounds[0], target_bounds[3] - target_bounds[1]),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.49),
    )
    texture = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    texture.alpha_composite(fitted, (target_bounds[0], target_bounds[1]))
    texture.putalpha(target_alpha)

    hidden_mask = ImageChops.subtract(target_alpha, original_visible.getchannel("A"))
    # Feather the hidden texture a few pixels into the real fur. A hard knockout
    # boundary would preserve pixels but leave a visible eye-socket ring.
    guide_weight = hidden_mask.filter(ImageFilter.GaussianBlur(6.0))
    visible_feather = ImageChops.multiply(original_visible.getchannel("A"), ImageOps.invert(guide_weight))
    visible_overlay = original_visible.copy()
    visible_overlay.putalpha(visible_feather)
    corrected_head = texture.copy()
    corrected_head.alpha_composite(visible_overlay)
    corrected_head.putalpha(target_alpha)
    blend_zone = ImageChops.subtract(original_visible.getchannel("A"), visible_feather)
    preserved_visible = ImageChops.subtract(original_visible.getchannel("A"), blend_zone)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    corrected_crop = corrected_head.crop(target_bounds)
    corrected_crop.save(OUTPUT / "13_head-complete-natural-fur.png", optimize=True)

    layers = load_v10_layers(v10)
    layers["head"] = corrected_head
    reconstruction = compose(v10["drawOrderBackToFront"], layers)
    reconstruction.save(OUTPUT / "front-head-corrected-reconstruction.png", optimize=True)
    reference = Image.open(REFERENCE).convert("RGBA")
    reference_bytes = reference.tobytes()
    reconstruction_bytes = reconstruction.tobytes()
    color_error = 0
    color_samples = 0
    for index in range(reference.width * reference.height):
        if reference_bytes[index * 4 + 3] <= 8:
            continue
        for channel in range(3):
            color_error += abs(reference_bytes[index * 4 + channel] - reconstruction_bytes[index * 4 + channel])
            color_samples += 1
    reference_alpha = reference.getchannel("A").tobytes()
    reconstruction_alpha = reconstruction.getchannel("A").tobytes()

    output = Image.new("RGB", (1800, 1180), "#f4f6f8")
    draw = ImageDraw.Draw(output)
    draw.text((48, 25), "小橘 X6：头底隐藏毛流修正 v11", font=font(38, True), fill="#19324b")
    draw.text((50, 79), "只替换被眼睛、嘴部和耳根遮住的隐藏纹理；原有可见小橘像素与头部完整掩码保持不变。", font=font(20), fill="#586774")

    panels = [
        ("v10 已否决：放射纹", rejected_head, "#a33a3a"),
        ("v11 完整头底：自然毛流", corrected_head, "#246951"),
        ("装回耳、眼、嘴后的静止效果", reconstruction, "#245b88"),
    ]
    for index, (label, image, color) in enumerate(panels):
        x = 42 + index * 575
        draw.rounded_rectangle((x, 125, x + 540, 805), radius=8, fill="white", outline="#cbd5df", width=2)
        draw.text((x + 20, 145), label, font=font(21, True), fill=color)
        crop = image.crop(image.getchannel("A").getbbox())
        output.paste(fit(crop, (500, 590), 12).convert("RGB"), (x + 20, 195))

    draw.rounded_rectangle((42, 835, 1758, 1138), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((64, 855), "隐藏区检查：把眼睛和嘴移开，确认下面是连续毛发而不是几何填充", font=font(23, True), fill="#245b88")
    frames = [
        ("正常覆盖", {}),
        ("双眼向外移开", {"eye_R": (-58, 0), "eye_L": (58, 0)}),
        ("嘴部向下移开", {"mouth": (0, 58)}),
    ]
    for index, (label, offsets) in enumerate(frames):
        x = 100 + index * 550
        face = compose(v10["drawOrderBackToFront"], layers, offsets)
        crop = face.crop((175, 35, 495, 420))
        output.paste(fit(crop, (460, 210), 8).convert("RGB"), (x, 905))
        draw.text((x + 135, 1110), label, font=font(17, True), fill="#34495a")
    output.save(QA / "x6-head-hidden-texture-review-v11.png", optimize=True)

    result = {
        "schemaVersion": 1,
        "stage": "X6-front-head-hidden-texture-candidate",
        "status": "candidate-for-user-visual-review",
        "rejectedSource": "live2d/x6/front-complete-overlap-layers-v10/13_head.png",
        "generatedTextureSource": "live2d/x6/hidden-texture-guides-v11/head-base-texture-source.png",
        "generatedTextureAlpha": "live2d/x6/hidden-texture-guides-v11/head-base-texture-alpha.png",
        "outputLayer": "live2d/x6/front-head-hidden-texture-v11/13_head-complete-natural-fur.png",
        "canvasBounds": list(target_bounds),
        "visiblePixelsPreservedOutsideBlendZone": sum(value > 8 for value in preserved_visible.tobytes()),
        "blendZonePixels": sum(value > 8 for value in blend_zone.tobytes()),
        "hiddenTexturePixelsReplaced": sum(value > 8 for value in hidden_mask.tobytes()),
        "method": "generated-hidden-fur-texture-guide-with-six-pixel-boundary-feather-and-preserved-outer-identity",
        "qa": {
            "review": "live2d/x6/qa/x6-head-hidden-texture-review-v11.png",
            "reconstruction": "live2d/x6/front-head-hidden-texture-v11/front-head-corrected-reconstruction.png",
        },
        "restReconstructionAudit": {
            "extraAlphaPixels": sum(ref == 0 and out > 0 for ref, out in zip(reference_alpha, reconstruction_alpha)),
            "missingAlphaPixels": sum(ref > 0 and out == 0 for ref, out in zip(reference_alpha, reconstruction_alpha)),
            "visibleRgbMeanAbsoluteError": round(color_error / color_samples, 4),
            "status": "pass-candidate" if color_error / color_samples < 2.0 else "fail",
        },
        "gateBoundary": {
            "headHiddenTextureApprovedByUser": False,
            "remainingStructuralLayersAuthorizedForSameMethod": False,
            "sideBackPropagationAuthorized": False,
            "gate6Approved": False,
            "x7Authorized": False,
        },
    }
    (X6 / "x6-head-hidden-texture-contract-v11.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": result["status"], "hiddenTexturePixelsReplaced": result["hiddenTexturePixelsReplaced"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
