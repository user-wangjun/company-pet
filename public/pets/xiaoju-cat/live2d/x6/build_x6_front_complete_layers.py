from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from scipy.ndimage import distance_transform_edt


PET = Path(__file__).resolve().parents[2]
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
SOURCE = X6 / "x6-joint-safe-motion-bundle-contract-v4.json"
REFERENCE = X6 / "front-user-segmentation-v8" / "front-reconstruction.png"
OUTPUT = X6 / "front-complete-overlap-layers-v10"
CANVAS = (650, 887)

# Complete child layers are painted first. Their roots are hidden by the complete
# parent layer, not by a separate floating patch.
DRAW_ORDER = [
    "tail",
    "leg_L_lower_paw",
    "leg_R_lower_paw",
    "leg_L_upper",
    "leg_R_upper",
    "arm_L_lower_paw",
    "arm_R_lower_paw",
    "arm_L_upper",
    "arm_R_upper",
    "body",
    "ear_L",
    "ear_R",
    "head",
    "eye_L",
    "eye_R",
    "mouth",
]

PARENT_COVERS = {
    "tail": ["body"],
    "leg_L_lower_paw": ["leg_L_upper"],
    "leg_R_lower_paw": ["leg_R_upper"],
    "leg_L_upper": ["body"],
    "leg_R_upper": ["body"],
    "arm_L_lower_paw": ["arm_L_upper"],
    "arm_R_lower_paw": ["arm_R_upper"],
    "arm_L_upper": ["body"],
    "arm_R_upper": ["body"],
    "body": [],
    "ear_L": ["head"],
    "ear_R": ["head"],
    "head": ["body"],
    "eye_L": ["head"],
    "eye_R": ["head"],
    "mouth": ["head"],
}

STRUCTURAL = [
    "head",
    "body",
    "arm_L_upper",
    "arm_R_upper",
    "arm_L_lower_paw",
    "arm_R_lower_paw",
    "leg_L_upper",
    "leg_R_upper",
    "leg_L_lower_paw",
    "leg_R_lower_paw",
    "tail",
]


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


def load_layers(contract: dict) -> dict[str, Image.Image]:
    result = {}
    for row in contract["exports"]:
        if row["view"] != "front":
            continue
        canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        image = Image.open(PET / row["visibleFile"]).convert("RGBA")
        bounds = row["visibleBounds"]
        canvas.alpha_composite(image, (bounds[0], bounds[1]))
        result[row["bundle"]] = canvas
    return result


def capsule(points: list[tuple[int, int]], width: int) -> Image.Image:
    mask = Image.new("L", CANVAS, 0)
    draw = ImageDraw.Draw(mask)
    draw.line(points, fill=255, width=width, joint="curve")
    radius = width // 2
    for x, y in (points[0], points[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    return mask


def polygon(points: list[tuple[int, int]]) -> Image.Image:
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return mask


def desired_masks(layers: dict[str, Image.Image], reference_alpha: Image.Image) -> dict[str, Image.Image]:
    masks = {layer_id: image.getchannel("A").point(lambda value: 255 if value > 8 else 0) for layer_id, image in layers.items()}

    shapes = {
        "head": polygon([(240, 92), (285, 66), (386, 66), (438, 104), (476, 206), (462, 315), (420, 389), (250, 389), (207, 315), (195, 206)]),
        "body": polygon([(258, 326), (412, 326), (442, 410), (228, 410)]),
        "arm_R_upper": capsule([(253, 338), (188, 376)], 78),
        "arm_L_upper": capsule([(417, 338), (482, 376)], 78),
        "arm_R_lower_paw": capsule([(190, 375), (117, 425)], 58),
        "arm_L_lower_paw": capsule([(480, 375), (553, 425)], 58),
        "leg_R_upper": capsule([(213, 620), (178, 680)], 96),
        "leg_L_upper": capsule([(457, 620), (492, 680)], 96),
        "leg_R_lower_paw": capsule([(180, 675), (128, 700)], 66),
        "leg_L_lower_paw": capsule([(490, 675), (542, 700)], 66),
        "tail": capsule([(335, 704), (337, 824)], 74),
    }

    # All inferred content remains inside the approved full-body silhouette.
    for layer_id, shape in shapes.items():
        shape = ImageChops.multiply(shape, reference_alpha)
        masks[layer_id] = ImageChops.lighter(masks[layer_id], shape)

    # Structural child extensions must live inside the complete parent overlap.
    for child, parents in PARENT_COVERS.items():
        if child not in STRUCTURAL or not parents or child == "head":
            continue
        parent_union = Image.new("L", CANVAS, 0)
        for parent in parents:
            parent_union = ImageChops.lighter(parent_union, masks[parent])
        original = layers[child].getchannel("A").point(lambda value: 255 if value > 8 else 0)
        inferred = ImageChops.subtract(masks[child], original)
        inferred = ImageChops.multiply(inferred, parent_union)
        masks[child] = ImageChops.lighter(original, inferred)
    return masks


def nearest_texture_fill(source: Image.Image, target_mask: Image.Image, layer_id: str) -> Image.Image:
    rgba = np.asarray(source, dtype=np.uint8)
    target = np.asarray(target_mask, dtype=np.uint8)
    known = rgba[:, :, 3] > 8
    if not np.any(known):
        raise RuntimeError(f"layer has no source texture: {layer_id}")

    # Seed the whole canvas from the nearest real source pixel so OpenCV never
    # pulls transparent black into the reconstructed fur edge.
    _, nearest_indices = distance_transform_edt(~known, return_indices=True)
    seeded = rgba[:, :, :3][nearest_indices[0], nearest_indices[1]].copy()
    missing = ((target > 8) & ~known).astype(np.uint8) * 255
    repaired = cv2.inpaint(seeded, missing, 4.0, cv2.INPAINT_TELEA)
    # Return local fur-frequency detail after the low-frequency color field is
    # repaired. This avoids both flat airbrushed fills and hard clone bands.
    low_frequency = cv2.GaussianBlur(seeded, (0, 0), 2.2)
    detail = seeded.astype(np.int16) - low_frequency.astype(np.int16)
    textured = np.clip(repaired.astype(np.int16) + (detail * 0.72), 0, 255).astype(np.uint8)
    repaired[missing > 0] = textured[missing > 0]
    repaired[known] = rgba[:, :, :3][known]

    result = np.dstack((repaired, target))
    return Image.fromarray(result.astype(np.uint8), "RGBA")


def compose(layers: dict[str, Image.Image], offsets: dict[str, tuple[int, int]] | None = None) -> Image.Image:
    offsets = offsets or {}
    result = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer_id in DRAW_ORDER:
        dx, dy = offsets.get(layer_id, (0, 0))
        result.alpha_composite(layers[layer_id], (dx, dy))
    return result


def tight_export(image: Image.Image, path: Path) -> list[int]:
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        raise RuntimeError(f"empty layer: {path.name}")
    image.crop(bounds).save(path, optimize=True)
    return list(bounds)


def fit(image: Image.Image, size: tuple[int, int], padding: int = 10) -> Image.Image:
    target = checker(size)
    source = image.copy()
    source.thumbnail((size[0] - padding * 2, size[1] - padding * 2), Image.Resampling.LANCZOS)
    target.alpha_composite(source, ((size[0] - source.width) // 2, (size[1] - source.height) // 2))
    return target


def render_review(layers: dict[str, Image.Image], reconstruction: Image.Image) -> None:
    output = Image.new("RGB", (1800, 1540), "#f4f6f8")
    draw = ImageDraw.Draw(output)
    draw.text((48, 25), "小橘 X6：完整图层＋真实重叠 v10", font=font(38, True), fill="#19324b")
    draw.text((50, 79), "每个结构层自身包含被遮住的形体；静止时由父层覆盖，拉开后不再依赖短套筒补缝。", font=font(20), fill="#586774")

    draw.rounded_rectangle((42, 120, 560, 950), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((62, 140), "完整图层静止重组", font=font(23, True), fill="#245b88")
    output.paste(fit(reconstruction, (478, 750), 12).convert("RGB"), (62, 185))

    offsets = {
        "head": (0, -55), "ear_L": (0, -55), "ear_R": (0, -55), "eye_L": (0, -55), "eye_R": (0, -55), "mouth": (0, -55),
        "arm_R_upper": (-28, -8), "arm_R_lower_paw": (-52, 4), "arm_L_upper": (28, -8), "arm_L_lower_paw": (52, 4),
        "leg_R_upper": (-20, 18), "leg_R_lower_paw": (-38, 32), "leg_L_upper": (20, 18), "leg_L_lower_paw": (38, 32),
        "tail": (0, 42),
    }
    draw.rounded_rectangle((585, 120, 1103, 950), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((605, 140), "整体拉开：显示重叠长度", font=font(23, True), fill="#245b88")
    output.paste(fit(compose(layers, offsets), (478, 750), 12).convert("RGB"), (605, 185))

    draw.rounded_rectangle((1128, 120, 1758, 950), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((1148, 140), "关键完整底层（非可见切片）", font=font(23, True), fill="#245b88")
    cards = ["head", "body", "arm_R_upper", "arm_R_lower_paw", "leg_R_upper", "leg_R_lower_paw", "tail"]
    labels = ["头底", "身体底", "右上臂", "右小臂＋爪", "右大腿", "右小腿＋爪", "尾巴"]
    for index, (layer_id, label) in enumerate(zip(cards, labels)):
        col, row = index % 2, index // 2
        x = 1150 + col * 290
        y = 190 + row * 178
        draw.rounded_rectangle((x, y, x + 270, y + 160), radius=6, fill="#fbfcfd", outline="#d4dce3", width=2)
        box = layers[layer_id].getchannel("A").getbbox()
        crop = layers[layer_id].crop(box) if box else layers[layer_id]
        output.paste(fit(crop, (250, 118), 7).convert("RGB"), (x + 10, y + 8))
        draw.text((x + 10, y + 130), label, font=font(16, True), fill="#34495a")

    draw.rounded_rectangle((42, 980, 1758, 1495), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((64, 1000), "关节分级拉动：完整层仍保持重叠", font=font(24, True), fill="#245b88")
    frames = [
        ("静止", {}),
        ("右上臂连小臂外移", {"arm_R_upper": (-14, -6), "arm_R_lower_paw": (-14, -6)}),
        ("右小臂再外移", {"arm_R_upper": (-14, -6), "arm_R_lower_paw": (-27, 5)}),
        ("右后腿分级外移", {"leg_R_upper": (-12, 8), "leg_R_lower_paw": (-25, 18)}),
    ]
    for index, (label, frame_offsets) in enumerate(frames):
        x = 76 + index * 425
        output.paste(fit(compose(layers, frame_offsets), (390, 380), 8).convert("RGB"), (x, 1050))
        draw.text((x + 85, 1440), label, font=font(17, True), fill="#34495a")
    output.save(QA / "x6-front-complete-overlap-review-v10.png", optimize=True)


def main() -> None:
    source_contract = json.loads(SOURCE.read_text(encoding="utf-8"))
    source_layers = load_layers(source_contract)
    reference = Image.open(REFERENCE).convert("RGBA")
    masks = desired_masks(source_layers, reference.getchannel("A"))
    complete_layers = {
        layer_id: nearest_texture_fill(image, masks[layer_id], layer_id) if layer_id in STRUCTURAL else image
        for layer_id, image in source_layers.items()
    }

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    exports = []
    for index, layer_id in enumerate(DRAW_ORDER, 1):
        filename = f"{index:02d}_{layer_id}.png"
        bounds = tight_export(complete_layers[layer_id], OUTPUT / filename)
        original_alpha = source_layers[layer_id].getchannel("A")
        complete_alpha = complete_layers[layer_id].getchannel("A")
        added = ImageChops.subtract(complete_alpha, original_alpha)
        exports.append(
            {
                "id": layer_id,
                "file": f"live2d/x6/front-complete-overlap-layers-v10/{filename}",
                "canvasBounds": bounds,
                "parentCoverLayers": PARENT_COVERS[layer_id],
                "sourceVisiblePixels": sum(value > 8 for value in original_alpha.tobytes()),
                "hiddenCompletionPixels": sum(value > 8 for value in added.tobytes()),
                "completeStructuralLayer": layer_id in STRUCTURAL,
            }
        )

    overlap_records = []
    for child, parents in PARENT_COVERS.items():
        for parent in parents:
            overlap = ImageChops.multiply(complete_layers[child].getchannel("A"), complete_layers[parent].getchannel("A"))
            pixels = sum(value > 8 for value in overlap.tobytes())
            overlap_records.append({"child": child, "parent": parent, "overlapPixels": pixels, "passes": pixels >= 100})

    reconstruction = compose(complete_layers)
    reconstruction.save(OUTPUT / "front-complete-reconstruction.png", optimize=True)
    render_review(complete_layers, reconstruction)
    reference_array = np.asarray(reference, dtype=np.int16)
    reconstruction_array = np.asarray(reconstruction, dtype=np.int16)
    visible = reference_array[:, :, 3] > 8
    visible_rgb_mae = float(np.abs(reference_array[:, :, :3] - reconstruction_array[:, :, :3])[visible].mean())
    reference_alpha = reference_array[:, :, 3]
    reconstruction_alpha = reconstruction_array[:, :, 3]
    result = {
        "schemaVersion": 1,
        "stage": "X6-front-complete-overlap-layer-candidate",
        "status": "candidate-for-user-visual-review",
        "strategy": "complete-independent-semantic-layers-with-real-parent-child-overlap",
        "sourceRejectedCandidate": "live2d/x6/x6-front-actual-segmentation-contract-v8.json",
        "canvas": {"width": CANVAS[0], "height": CANVAS[1]},
        "layerCount": len(exports),
        "structuralCompleteLayerCount": len(STRUCTURAL),
        "drawOrderBackToFront": DRAW_ORDER,
        "layers": exports,
        "overlapAudit": {
            "jointCount": len(overlap_records),
            "passCount": sum(row["passes"] for row in overlap_records),
            "minimumOverlapPixels": min(row["overlapPixels"] for row in overlap_records),
            "records": overlap_records,
        },
        "restReconstructionAudit": {
            "extraAlphaPixels": int(np.count_nonzero((reference_alpha == 0) & (reconstruction_alpha > 0))),
            "missingAlphaPixels": int(np.count_nonzero((reference_alpha > 0) & (reconstruction_alpha == 0))),
            "visibleRgbMeanAbsoluteError": round(visible_rgb_mae, 4),
            "status": "pass-candidate" if visible_rgb_mae < 2.0 else "fail",
        },
        "qa": {
            "review": "live2d/x6/qa/x6-front-complete-overlap-review-v10.png",
            "reconstruction": "live2d/x6/front-complete-overlap-layers-v10/front-complete-reconstruction.png",
        },
        "gateBoundary": {
            "frontCompleteLayersApprovedByUser": False,
            "sideBackPropagationAuthorized": False,
            "gate6Approved": False,
            "x7Authorized": False,
        },
        "knownLimit": "Hidden texture is reconstructed only inside approved overlap masks and remains a visual-review candidate; it is not mesh, Cubism, or X7 output.",
    }
    (X6 / "x6-front-complete-overlap-contract-v10.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": result["status"], "layers": len(exports), "overlap": result["overlapAudit"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
