from __future__ import annotations

import json
import shutil
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps


PET = Path(__file__).resolve().parents[2]
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
V4 = X6 / "x6-joint-safe-motion-bundle-contract-v4.json"
V10 = X6 / "x6-front-complete-overlap-contract-v10.json"
V11 = X6 / "x6-head-hidden-texture-contract-v11.json"
GUIDE = X6 / "hidden-texture-guides-v11" / "head-base-texture-alpha.png"
REFERENCE = X6 / "front-user-segmentation-v8" / "front-reconstruction.png"
OUTPUT = X6 / "front-all-layers-v14"
CANVAS = (650, 887)

LABELS = {
    "tail": "尾巴",
    "leg_L_lower_paw": "左小腿＋后爪",
    "leg_R_lower_paw": "右小腿＋后爪",
    "leg_L_upper": "左大腿",
    "leg_R_upper": "右大腿",
    "arm_L_lower_paw": "左小臂＋前爪",
    "arm_R_lower_paw": "右小臂＋前爪",
    "arm_L_upper": "左上臂",
    "arm_R_upper": "右上臂",
    "body": "身体底",
    "ear_L": "左耳",
    "ear_R": "右耳",
    "head": "头底（眼周修正）",
    "eye_L": "左眼（仅眼球）",
    "eye_R": "右眼（仅眼球）",
    "mouth": "嘴部",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def checker(size: tuple[int, int], block: int = 16) -> Image.Image:
    image = Image.new("RGBA", size, (250, 251, 252, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(225, 231, 236, 255))
    return image


def place(path: str, bounds: list[int]) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.alpha_composite(Image.open(PET / path).convert("RGBA"), (bounds[0], bounds[1]))
    return canvas


def crop_alpha(image: Image.Image) -> Image.Image:
    bounds = image.getchannel("A").getbbox()
    return image.crop(bounds or (0, 0, image.width, image.height))


def fit(image: Image.Image, size: tuple[int, int], padding: int = 10) -> Image.Image:
    target = checker(size)
    source = image.copy()
    source.thumbnail((size[0] - 2 * padding, size[1] - 2 * padding), Image.Resampling.LANCZOS)
    target.alpha_composite(source, ((size[0] - source.width) // 2, (size[1] - source.height) // 2))
    return target


def compose(order: list[str], layers: dict[str, Image.Image], offsets: dict[str, tuple[int, int]] | None = None) -> Image.Image:
    result = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer_id in order:
        dx, dy = (offsets or {}).get(layer_id, (0, 0))
        result.alpha_composite(layers[layer_id], (dx, dy))
    return result


def mean_rgb_error(reference: Image.Image, output: Image.Image, mask: Image.Image | None = None) -> float:
    ref = reference.convert("RGBA")
    out = output.convert("RGBA")
    mask_bytes = (mask or ref.getchannel("A")).tobytes()
    ref_bytes = ref.tobytes()
    out_bytes = out.tobytes()
    error = 0
    samples = 0
    for index, weight in enumerate(mask_bytes):
        if weight <= 8:
            continue
        for channel in range(3):
            error += abs(ref_bytes[index * 4 + channel] - out_bytes[index * 4 + channel])
            samples += 1
    return round(error / max(samples, 1), 4)


def recover_rest_alpha(reference: Image.Image, layers: dict[str, Image.Image], order: list[str]) -> dict:
    reconstruction = compose(order, layers)
    missing = ImageChops.subtract(reference.getchannel("A"), reconstruction.getchannel("A"))
    missing_pixels = missing.load()
    reference_pixels = reference.load()
    assignments = {"ear_L": 0, "ear_R": 0, "head": 0}
    for y in range(CANVAS[1]):
        for x in range(CANVAS[0]):
            amount = missing_pixels[x, y]
            if amount <= 8:
                continue
            if y < 150:
                layer_id = "ear_L" if x > CANVAS[0] // 2 else "ear_R"
            else:
                layer_id = "head"
            layer_pixels = layers[layer_id].load()
            red, green, blue, _ = reference_pixels[x, y]
            layer_pixels[x, y] = (red, green, blue, amount)
            assignments[layer_id] += 1
    return {"recoveredPixels": sum(assignments.values()), "assignedLayers": assignments}


def largest_component_alpha(alpha: Image.Image) -> tuple[Image.Image, int]:
    width, height = alpha.size
    values = alpha.load()
    visited = bytearray(width * height)
    best: list[tuple[int, int]] = []
    removed_components = 0
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if visited[index] or values[x, y] == 0:
                continue
            queue = deque([(x, y)])
            visited[index] = 1
            component: list[tuple[int, int]] = []
            while queue:
                px, py = queue.popleft()
                component.append((px, py))
                for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                    if nx < 0 or nx >= width or ny < 0 or ny >= height:
                        continue
                    neighbor = ny * width + nx
                    if visited[neighbor] or values[nx, ny] == 0:
                        continue
                    visited[neighbor] = 1
                    queue.append((nx, ny))
            if len(component) > len(best):
                if best:
                    removed_components += 1
                best = component
            else:
                removed_components += 1
    keep = Image.new("L", alpha.size, 0)
    keep_pixels = keep.load()
    for x, y in best:
        keep_pixels[x, y] = values[x, y]
    return keep, removed_components


def build_tight_eye(row: dict) -> tuple[Image.Image, dict]:
    source = Image.open(PET / row["file"]).convert("RGBA")
    source_pixels = source.load()
    dark = Image.new("L", source.size, 0)
    dark_pixels = dark.load()
    for y in range(source.height):
        for x in range(source.width):
            red, green, blue, alpha = source_pixels[x, y]
            luminance = (red * 299 + green * 587 + blue * 114) // 1000
            if alpha > 32 and luminance < 80:
                dark_pixels[x, y] = 255
    dark_bounds = dark.getbbox()
    if dark_bounds is None:
        raise RuntimeError(f"cannot locate eye contour for {row['id']}")
    margin = 3
    bounds = (
        max(0, dark_bounds[0] - margin),
        max(0, dark_bounds[1] - margin),
        min(source.width, dark_bounds[2] + margin),
        min(source.height, dark_bounds[3] + margin),
    )
    scale = 4
    high = Image.new("L", (source.width * scale, source.height * scale), 0)
    draw = ImageDraw.Draw(high)
    draw.ellipse(tuple(value * scale for value in bounds), fill=255)
    contour = high.resize(source.size, Image.Resampling.LANCZOS)
    tight_alpha = ImageChops.multiply(source.getchannel("A"), contour)
    tight = source.copy()
    tight.putalpha(tight_alpha)
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.alpha_composite(tight, (row["canvasBounds"][0], row["canvasBounds"][1]))
    return canvas, {
        "sourceAlphaPixels": sum(value > 8 for value in source.getchannel("A").tobytes()),
        "eyeOnlyAlphaPixels": sum(value > 8 for value in tight_alpha.tobytes()),
        "darkContourBoundsInSource": list(dark_bounds),
        "eyeOnlyBoundsInSource": list(bounds),
        "method": "dark-eye-contour-bounds-plus-three-pixel-antialiased-ellipse-no-surrounding-face-patch",
    }


def build_head(v4: dict, v10: dict, eye_layers: dict[str, Image.Image]) -> tuple[Image.Image, dict]:
    v10_head = next(row for row in v10["layers"] if row["id"] == "head")
    rejected = place(v10_head["file"], v10_head["canvasBounds"])
    target_alpha, removed_components = largest_component_alpha(rejected.getchannel("A"))
    target_bounds = target_alpha.getbbox()
    if target_bounds is None:
        raise RuntimeError("head mask is empty")

    guide = Image.open(GUIDE).convert("RGBA")
    guide_bounds = guide.getchannel("A").getbbox()
    if guide_bounds is None:
        raise RuntimeError("head guide is empty")
    fitted = ImageOps.fit(
        guide.crop(guide_bounds),
        (target_bounds[2] - target_bounds[0], target_bounds[3] - target_bounds[1]),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.49),
    )
    texture = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    texture.alpha_composite(fitted, (target_bounds[0], target_bounds[1]))
    texture.putalpha(target_alpha)

    reference = Image.open(REFERENCE).convert("RGBA")
    top = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer_id in ("eye_L", "eye_R", "mouth"):
        if layer_id in eye_layers:
            top.alpha_composite(eye_layers[layer_id])
        else:
            row = next(item for item in v10["layers"] if item["id"] == layer_id)
            top.alpha_composite(place(row["file"], row["canvasBounds"]))

    corrected = texture.copy()
    corrected_pixels = corrected.load()
    reference_pixels = reference.load()
    top_pixels = top.load()
    guide_pixels = texture.load()
    alpha_pixels = target_alpha.load()
    hidden_pixels = 0
    solved_edge_pixels = 0
    visible_identity_pixels = 0
    for y in range(CANVAS[1]):
        for x in range(CANVAS[0]):
            head_alpha = alpha_pixels[x, y]
            if head_alpha == 0:
                corrected_pixels[x, y] = (0, 0, 0, 0)
                continue
            top_rgb = top_pixels[x, y][:3]
            top_alpha = top_pixels[x, y][3]
            if top_alpha <= 2:
                corrected_pixels[x, y] = (*reference_pixels[x, y][:3], head_alpha)
                visible_identity_pixels += 1
                continue
            hidden_pixels += 1
            if top_alpha >= 250:
                corrected_pixels[x, y] = (*guide_pixels[x, y][:3], head_alpha)
                continue
            amount = top_alpha / 255.0
            solved = []
            for channel in range(3):
                value = (reference_pixels[x, y][channel] - amount * top_rgb[channel]) / (1.0 - amount)
                solved.append(max(0, min(255, round(value))))
            corrected_pixels[x, y] = (*solved, head_alpha)
            solved_edge_pixels += 1
    corrected.putalpha(target_alpha)
    return corrected, {
        "canvasBounds": list(target_bounds),
        "hiddenTexturePixels": hidden_pixels,
        "visibleIdentityPixels": visible_identity_pixels,
        "inverseAlphaSolvedEdgePixels": solved_edge_pixels,
        "removedDisconnectedMaskComponents": removed_components,
        "visibleBlendOutsideOcclusionPixels": 0,
        "method": "largest-connected-head-mask-with-exact-visible-reference-natural-hidden-guide-and-inverse-alpha-edge-solve",
    }


def build_atlas(rows: list[dict], layers: dict[str, Image.Image], invalid_hidden: set[str]) -> Path:
    output = Image.new("RGB", (1800, 1580), "#f3f6f8")
    draw = ImageDraw.Draw(output)
    draw.text((48, 28), "小橘 X6：正面全部 16 个独立图层 v14", font=font(38, True), fill="#18344f")
    draw.text((50, 82), "透明 PNG 按实际绘制顺序列出；左右眼已改为仅眼球，橙色状态仍需继续修复隐藏毛流。", font=font(19), fill="#586a78")
    card_w, card_h = 420, 340
    for index, row in enumerate(rows):
        col, line = index % 4, index // 4
        x = 45 + col * 440
        y = 125 + line * 355
        layer_id = row["id"]
        status = "隐藏毛流待修" if layer_id in invalid_hidden else "当前可审"
        status_color = "#c7671e" if layer_id in invalid_hidden else "#26705b"
        draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=7, fill="white", outline="#c9d4df", width=2)
        draw.text((x + 15, y + 13), f"{index + 1:02d}  {LABELS[layer_id]}", font=font(18, True), fill="#203b55")
        draw.text((x + 15, y + 43), status, font=font(14, True), fill=status_color)
        preview = fit(crop_alpha(layers[layer_id]), (card_w - 30, card_h - 85), 9)
        output.paste(preview.convert("RGB"), (x + 15, y + 70))
        draw.text((x + 15, y + card_h - 23), layer_id, font=font(12), fill="#647584")
    path = QA / "x6-front-all-layer-atlas-v14.png"
    output.save(path, optimize=True)
    return path


def build_eye_review(reference: Image.Image, head: Image.Image, layers: dict[str, Image.Image], order: list[str]) -> Path:
    output = Image.new("RGB", (1700, 980), "#f3f6f8")
    draw = ImageDraw.Draw(output)
    draw.text((48, 26), "小橘 X6：眼周接缝修正 v14", font=font(38, True), fill="#18344f")
    draw.text((50, 80), "左右眼只保留眼球与黑色眼缘；周边脸毛归头底，隐藏毛流只留在眼球遮挡内部。", font=font(19), fill="#586a78")
    reconstruction = compose(order, layers)
    eye_moved = compose(order, layers, {"eye_R": (-72, 0), "eye_L": (72, 0)})
    panels = [
        ("原始身份参考", reference.crop((190, 55, 480, 300))),
        ("修正后静止装回", reconstruction.crop((190, 55, 480, 300))),
        ("双眼移开检查头底", eye_moved.crop((160, 45, 510, 320))),
        ("完整头底单层", crop_alpha(head)),
    ]
    for index, (label, image) in enumerate(panels):
        x = 45 + index * 415
        draw.rounded_rectangle((x, 125, x + 390, 820), radius=7, fill="white", outline="#c9d4df", width=2)
        draw.text((x + 18, 145), label, font=font(19, True), fill="#245b88")
        preview = fit(image, (354, 600), 12)
        output.paste(preview.convert("RGB"), (x + 18, 195))
    draw.rounded_rectangle((45, 850, 1655, 935), radius=7, fill="white", outline="#c9d4df", width=2)
    draw.text((70, 875), "审核重点：静止眼缘不应出现环形切口；眼睛移开后，下面应是连续毛流而不是眼睛残影。", font=font(20, True), fill="#2c5f52")
    path = QA / "x6-front-eye-seam-review-v14.png"
    output.save(path, optimize=True)
    return path


def main() -> None:
    v4 = json.loads(V4.read_text(encoding="utf-8"))
    v10 = json.loads(V10.read_text(encoding="utf-8"))
    v11 = json.loads(V11.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)

    eye_layers: dict[str, Image.Image] = {}
    eye_audits = {}
    for layer_id in ("eye_L", "eye_R"):
        row = next(item for item in v10["layers"] if item["id"] == layer_id)
        eye_layers[layer_id], eye_audits[layer_id] = build_tight_eye(row)
    head, head_audit = build_head(v4, v10, eye_layers)
    layers: dict[str, Image.Image] = {}
    exports = []
    for row in v10["layers"]:
        layer_id = row["id"]
        source_path = PET / row["file"]
        output_path = OUTPUT / source_path.name
        if layer_id == "head":
            crop = head.crop(tuple(row["canvasBounds"]))
            crop.save(output_path, optimize=True)
            layers[layer_id] = head
        elif layer_id in eye_layers:
            crop = eye_layers[layer_id].crop(tuple(row["canvasBounds"]))
            crop.save(output_path, optimize=True)
            layers[layer_id] = eye_layers[layer_id]
        else:
            shutil.copy2(source_path, output_path)
            layers[layer_id] = place(row["file"], row["canvasBounds"])
        exports.append({"id": layer_id, "file": f"live2d/x6/front-all-layers-v14/{output_path.name}", "canvasBounds": row["canvasBounds"]})

    reference = Image.open(REFERENCE).convert("RGBA")
    rest_alpha_recovery = recover_rest_alpha(reference, layers, v10["drawOrderBackToFront"])
    for row, export in zip(v10["layers"], exports):
        output_path = PET / export["file"]
        layers[row["id"]].crop(tuple(row["canvasBounds"])).save(output_path, optimize=True)
    reconstruction = compose(v10["drawOrderBackToFront"], layers)
    reconstruction.save(OUTPUT / "front-reconstruction.png", optimize=True)
    invalid_hidden = {
        row["id"]
        for row in v10["layers"]
        if row["completeStructuralLayer"] and row["id"] != "head"
    }
    atlas = build_atlas(v10["layers"], layers, invalid_hidden)
    eye_review = build_eye_review(reference, head, layers, v10["drawOrderBackToFront"])

    ref_alpha = reference.getchannel("A").tobytes()
    out_alpha = reconstruction.getchannel("A").tobytes()
    contract = {
        "schemaVersion": 1,
        "stage": "X6-front-all-layer-review",
        "status": "candidate-for-user-visual-review",
        "authorizationEvidence": "User requested all separated layers after identifying the visible eye-edge seam.",
        "scope": "front-sixteen-layers-only",
        "layerCount": len(exports),
        "drawOrderBackToFront": v10["drawOrderBackToFront"],
        "exports": exports,
        "headCorrection": head_audit,
        "eyeLayerCorrection": eye_audits,
        "restAlphaRecovery": rest_alpha_recovery,
        "restReconstructionAudit": {
            "extraAlphaPixels": sum(ref == 0 and out > 0 for ref, out in zip(ref_alpha, out_alpha)),
            "missingAlphaPixels": sum(ref > 0 and out == 0 for ref, out in zip(ref_alpha, out_alpha)),
            "visibleRgbMeanAbsoluteError": mean_rgb_error(reference, reconstruction),
        },
        "remainingInvalidHiddenTextures": sorted(invalid_hidden),
        "qa": {
            "allLayerAtlas": f"live2d/x6/qa/{atlas.name}",
            "eyeSeamReview": f"live2d/x6/qa/{eye_review.name}",
            "reconstruction": "live2d/x6/front-all-layers-v14/front-reconstruction.png",
        },
        "supersedesHeadReview": "live2d/x6/qa/x6-head-hidden-texture-review-v13.png",
        "gateBoundary": {
            "frontAllLayerReviewAuthorizedByUser": True,
            "headCorrectionApprovedByUser": False,
            "remainingStructuralHiddenTexturesApprovedByUser": False,
            "sideBackPropagationAuthorized": False,
            "gate6Approved": False,
            "x7Authorized": False,
        },
        "materialSource": v11["generatedTextureAlpha"],
    }
    (X6 / "x6-front-all-layer-contract-v14.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": contract["status"], "layerCount": contract["layerCount"], "rest": contract["restReconstructionAudit"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
