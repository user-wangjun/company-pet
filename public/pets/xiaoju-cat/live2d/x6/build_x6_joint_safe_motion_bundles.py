from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat


ROOT = Path(__file__).resolve().parents[1]
PET = ROOT.parent
X5 = ROOT / "x5"
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
OUT = X6 / "joint-safe-motion-bundles-v4"
VISIBLE_CONTRACT = X6 / "x6-layer-assembly-contract-v1.json"
X5_SPLIT_CONTRACT = X5 / "x5-actual-xiaoju-layer-split-contract.json"
STACK_CONTRACT = X6 / "x6-production-layer-stack-contract-v2.json"
CANVAS = (1774, 887)
VIEW_BOUNDS = {
    "front": (0, 0, 650, 887),
    "side": (650, 0, 1120, 887),
    "back": (1120, 0, 1774, 887),
}


BUNDLE_META = {
    "head": ("body", "Head"),
    "mouth": ("head", "Mouth"),
    "ear_L": ("head", "EarRoot_L"),
    "ear_R": ("head", "EarRoot_R"),
    "eye_L": ("head", "EyeSocket_L"),
    "eye_R": ("head", "EyeSocket_R"),
    "body": (None, "Body"),
    "arm_L_upper": ("body", "Shoulder_L"),
    "arm_L_lower_paw": ("arm_L_upper", "Elbow_L"),
    "arm_R_upper": ("body", "Shoulder_R"),
    "arm_R_lower_paw": ("arm_R_upper", "Elbow_R"),
    "leg_L_upper": ("body", "Hip_L"),
    "leg_L_lower_paw": ("leg_L_upper", "Knee_L"),
    "leg_R_upper": ("body", "Hip_R"),
    "leg_R_lower_paw": ("leg_R_upper", "Knee_R"),
    "tail": ("body", "TailRoot"),
}

COLLAR_WIDTH = {
    "head": 35,
    "mouth": 17,
    "ear_L": 21,
    "ear_R": 21,
    "eye_L": 11,
    "eye_R": 11,
    "arm_L_upper": 31,
    "arm_R_upper": 31,
    "arm_L_lower_paw": 27,
    "arm_R_lower_paw": 27,
    "leg_L_upper": 35,
    "leg_R_upper": 35,
    "leg_L_lower_paw": 29,
    "leg_R_lower_paw": 29,
    "tail": 31,
}

STRESS_PAIRS = (
    ("front", "body", "head", (0, -14), "neck"),
    ("front", "body", "arm_R_upper", (-14, -6), "shoulder"),
    ("front", "arm_R_upper", "arm_R_lower_paw", (-14, 8), "elbow"),
    ("front", "body", "leg_R_upper", (-12, 10), "hip"),
    ("front", "leg_R_upper", "leg_R_lower_paw", (-13, 8), "knee"),
    ("back", "body", "tail", (0, 16), "tail root"),
)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def checker(size: tuple[int, int], block: int = 12) -> Image.Image:
    image = Image.new("RGBA", size, (247, 248, 249, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(224, 229, 233, 255))
    return image


def fit(image: Image.Image, size: tuple[int, int], pad: int = 12) -> Image.Image:
    background = checker(size)
    copy = image.copy()
    copy.thumbnail((size[0] - pad * 2, size[1] - pad * 2), Image.Resampling.LANCZOS)
    background.alpha_composite(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return background


def side_of(layer_id: str) -> str:
    if layer_id.endswith("_L"):
        return "L"
    if layer_id.endswith("_R"):
        return "R"
    raise ValueError(f"Expected anatomical side suffix: {layer_id}")


def classify(layer_id: str) -> str:
    if layer_id.startswith("ear_"):
        return f"ear_{side_of(layer_id)}"
    if any(token in layer_id for token in ("eye_socket", "iris", "pupil", "highlight", "upper_lid", "lower_lid")):
        return f"eye_{side_of(layer_id)}"
    if any(token in layer_id for token in ("muzzle", "jaw", "whisker")):
        return "mouth"
    if layer_id == "head_base" or layer_id.startswith("cheek_fur"):
        return "head"
    if layer_id.startswith("scapula_fur") or layer_id.startswith("upper_arm"):
        return f"arm_{side_of(layer_id)}_upper"
    if any(layer_id.startswith(prefix) for prefix in ("forearm", "wrist_fur", "fore_paw")):
        return f"arm_{side_of(layer_id)}_lower_paw"
    if layer_id.startswith("hind_thigh"):
        return f"leg_{side_of(layer_id)}_upper"
    if any(layer_id.startswith(prefix) for prefix in ("hind_shin", "hind_paw")):
        return f"leg_{side_of(layer_id)}_lower_paw"
    if layer_id.startswith("tail_"):
        return "tail"
    if layer_id in {"neck_fill", "chest_fur", "ribcage", "abdomen", "pelvis"}:
        return "body"
    raise KeyError(f"Unclassified visible layer: {layer_id}")


def prune_tiny_components(image: Image.Image, largest_only: bool = False) -> tuple[Image.Image, int, int]:
    alpha = image.getchannel("A")
    width, height = alpha.size
    source = alpha.tobytes()
    visited = bytearray(width * height)
    components: list[list[int]] = []
    for index, value in enumerate(source):
        if value <= 8 or visited[index]:
            continue
        visited[index] = 1
        queue = deque([index])
        component: list[int] = []
        while queue:
            current = queue.popleft()
            component.append(current)
            x = current % width
            y = current // width
            for neighbor in (
                current - 1 if x else -1,
                current + 1 if x + 1 < width else -1,
                current - width if y else -1,
                current + width if y + 1 < height else -1,
            ):
                if neighbor >= 0 and not visited[neighbor] and source[neighbor] > 8:
                    visited[neighbor] = 1
                    queue.append(neighbor)
        components.append(component)
    if not components:
        return image, 0, 0
    largest = max(len(component) for component in components)
    minimum = max(18, round(largest * 0.012))
    kept = [max(components, key=len)] if largest_only else [component for component in components if len(component) >= minimum]
    keep_indices = {index for component in kept for index in component}
    cleaned_alpha = bytearray(source)
    removed_pixels = 0
    for index, value in enumerate(cleaned_alpha):
        if value and index not in keep_indices:
            cleaned_alpha[index] = 0
            removed_pixels += 1
    cleaned = image.copy()
    cleaned.putalpha(Image.frombytes("L", (width, height), bytes(cleaned_alpha)))
    return cleaned, len(components) - len(kept), removed_pixels


def place(canvas: Image.Image, image: Image.Image, bounds: list[int] | tuple[int, ...]) -> None:
    canvas.alpha_composite(image, (bounds[0], bounds[1]))


def compose_records(records: list[dict], clean: bool = False) -> tuple[Image.Image, int, int]:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    removed_components = 0
    removed_pixels = 0
    for record in sorted(records, key=lambda item: item["drawOrder"]):
        image = Image.open(PET / record["file"]).convert("RGBA")
        if clean and classify(record["id"]) in {"body", "arm_L_upper", "arm_R_upper", "arm_L_lower_paw", "arm_R_lower_paw", "leg_L_upper", "leg_R_upper", "leg_L_lower_paw", "leg_R_lower_paw", "tail"}:
            image, count, pixels = prune_tiny_components(image)
            removed_components += count
            removed_pixels += pixels
        place(canvas, image, record["bounds"])
    if clean and records:
        bundle_ids = {classify(record["id"]) for record in records}
        continuous_bundles = {"body"}
        if len(bundle_ids) == 1 and next(iter(bundle_ids)) in continuous_bundles:
            bounds = canvas.getchannel("A").getbbox()
            if bounds:
                crop, count, pixels = prune_tiny_components(canvas.crop(bounds), largest_only=True)
                canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
                canvas.alpha_composite(crop, (bounds[0], bounds[1]))
                removed_components += count
                removed_pixels += pixels
    return canvas, removed_components, removed_pixels


def compose_placements(placements: list[dict]) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for placement in placements:
        if placement["role"] == "hairline-reference-no-area-underpaint":
            continue
        place(canvas, Image.open(PET / placement["file"]).convert("RGBA"), placement["bounds"])
    return canvas


def alpha_pixels(alpha: Image.Image) -> int:
    return sum(value > 8 for value in alpha.tobytes())


def nearest_alpha_point(alpha: Image.Image, target: tuple[float, float]) -> tuple[int, int]:
    bounds = alpha.getbbox()
    if not bounds:
        return round(target[0]), round(target[1])
    pixels = alpha.load()
    best = (bounds[0], bounds[1])
    best_distance = float("inf")
    for y in range(bounds[1], bounds[3]):
        for x in range(bounds[0], bounds[2]):
            if pixels[x, y] <= 8:
                continue
            distance = (x - target[0]) ** 2 + (y - target[1]) ** 2
            if distance < best_distance:
                best = (x, y)
                best_distance = distance
    return best


def bridge_to_collar(child_alpha: Image.Image, collar: Image.Image, width: int = 19) -> Image.Image:
    collar_bounds = collar.getbbox()
    child_bounds = child_alpha.getbbox()
    if not collar_bounds or not child_bounds:
        return collar
    collar_center = ((collar_bounds[0] + collar_bounds[2]) / 2, (collar_bounds[1] + collar_bounds[3]) / 2)
    child_center = ((child_bounds[0] + child_bounds[2]) / 2, (child_bounds[1] + child_bounds[3]) / 2)
    child_point = nearest_alpha_point(child_alpha, collar_center)
    collar_point = nearest_alpha_point(collar, child_center)
    bridge = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(bridge).line((child_point, collar_point), fill=255, width=width)
    return ImageChops.subtract(ImageChops.lighter(collar, bridge), child_alpha)


def rounded_grow(alpha: Image.Image, radius: int, threshold: int = 4) -> Image.Image:
    blurred = alpha.filter(ImageFilter.GaussianBlur(radius))
    return blurred.point(lambda value: 255 if value >= threshold else 0)


def localized_shoulder_cap(child_alpha: Image.Image, parent_alpha: Image.Image, base_collar: Image.Image) -> Image.Image:
    collar_bounds = base_collar.getbbox()
    if not collar_bounds:
        return base_collar
    target = ((collar_bounds[0] + collar_bounds[2]) / 2, (collar_bounds[1] + collar_bounds[3]) / 2)
    proximal = nearest_alpha_point(child_alpha, target)
    ellipse = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(ellipse).ellipse(
        (proximal[0] - 44, proximal[1] - 34, proximal[0] + 44, proximal[1] + 34),
        fill=255,
    )
    localized_base = ImageChops.darker(base_collar, rounded_grow(ellipse, 6))
    return ImageChops.lighter(localized_base, ellipse)


def tint_alpha(alpha: Image.Image, color: tuple[int, int, int, int]) -> Image.Image:
    image = Image.new("RGBA", alpha.size, color)
    image.putalpha(ImageChops.multiply(alpha, Image.new("L", alpha.size, color[3])))
    return image


def offset(image: Image.Image, delta: tuple[int, int]) -> Image.Image:
    moved = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    moved.alpha_composite(image, delta)
    return moved


def crop_union(images: list[Image.Image], padding: int = 18) -> tuple[int, int, int, int]:
    alpha = Image.new("L", CANVAS, 0)
    for image in images:
        alpha = ImageChops.lighter(alpha, image.getchannel("A"))
    bounds = alpha.getbbox() or (0, 0, 1, 1)
    return (
        max(0, bounds[0] - padding),
        max(0, bounds[1] - padding),
        min(CANVAS[0], bounds[2] + padding),
        min(CANVAS[1], bounds[3] + padding),
    )


def outline(alpha: Image.Image, color: tuple[int, int, int, int]) -> Image.Image:
    outer = alpha.filter(ImageFilter.MaxFilter(5))
    inner = alpha.filter(ImageFilter.MinFilter(3))
    return tint_alpha(ImageChops.subtract(outer, inner), color)


def build_review(bundle_images: dict[tuple[str, str], Image.Image], overlaps: dict[tuple[str, str], Image.Image], audits: list[dict]) -> None:
    canvas = Image.new("RGB", (1900, 1580), "#f5f7f9")
    draw = ImageDraw.Draw(canvas)
    draw.text((52, 30), "X6  Joint-safe Motion Bundles", font=font(40, True), fill="#17324d")
    draw.text((54, 84), "Clean visible cuts and separate hidden collars. Collars move with the child bundle but render behind the parent.", font=font(20), fill="#5f6e7b")
    draw.rounded_rectangle((48, 120, 1852, 205), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((72, 141), "Visible PNG = identity surface   |   Hidden collar PNG = shoulder/elbow/hip/knee/neck/tail-root overlap reserve", font=font(20, True), fill="#1769d2")
    draw.text((72, 174), "No collar replaces visible rest pixels; cyan is QA-only visualization.", font=font(17), fill="#5f6e7b")

    for column, view in enumerate(("front", "side", "back")):
        x = 48 + column * 616
        draw.text((x + 245, 222), view.upper(), font=font(25, True), fill="#17324d")
        visible = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        collar_map = Image.new("L", CANVAS, 0)
        for bundle_id in BUNDLE_META:
            image = bundle_images.get((view, bundle_id))
            if image:
                visible.alpha_composite(image)
                visible.alpha_composite(outline(image.getchannel("A"), (20, 94, 190, 210)))
            overlap = overlaps.get((view, bundle_id))
            if overlap:
                collar_map = ImageChops.lighter(collar_map, overlap.getchannel("A"))
        visible.alpha_composite(tint_alpha(collar_map, (0, 190, 170, 175)))
        crop = visible.crop(VIEW_BOUNDS[view])
        draw.rounded_rectangle((x, 260, x + 580, 840), radius=8, fill="white", outline="#cbd5df", width=2)
        canvas.paste(fit(crop, (552, 526)).convert("RGB"), (x + 14, 285))
        count = sum(1 for row in audits if row["view"] == view)
        minimum = min((row["overlapPixels"] for row in audits if row["view"] == view), default=0)
        draw.text((x + 18, 810), f"joint collars: {count}; minimum overlap: {minimum}px", font=font(16, True), fill="#159570")

    draw.text((52, 875), "PULL TEST: child visible art + hidden collar shifted away from parent", font=font(24, True), fill="#17324d")
    for index, (view, parent_id, child_id, delta, label) in enumerate(STRESS_PAIRS):
        column = index % 3
        row = index // 3
        x = 48 + column * 616
        y = 920 + row * 285
        parent = bundle_images[(view, parent_id)]
        child = bundle_images[(view, child_id)]
        overlap = overlaps[(view, child_id)]
        moved_overlap = offset(overlap, delta)
        moved_child = offset(child, delta)
        proof = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        proof.alpha_composite(moved_overlap)
        proof.alpha_composite(parent)
        proof.alpha_composite(moved_child)
        proof.alpha_composite(tint_alpha(moved_overlap.getchannel("A"), (0, 190, 170, 115)))
        crop = crop_union([parent, moved_overlap, moved_child], 14)
        draw.rounded_rectangle((x, y, x + 580, y + 245), radius=8, fill="white", outline="#cbd5df", width=2)
        canvas.paste(fit(proof.crop(crop), (552, 190), 8).convert("RGB"), (x + 14, y + 34))
        audit = next(row for row in audits if row["view"] == view and row["bundle"] == child_id)
        draw.text((x + 16, y + 8), f"{view.upper()} {label}: {audit['overlapPixels']} px, shift {delta}", font=font(16, True), fill="#1769d2")

    removed_components = sum(row.get("removedComponents", 0) for row in audits)
    draw.rounded_rectangle((48, 1505, 1852, 1560), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((72, 1522), f"Audit: all parent-child joints have nonzero hidden overlap; isolated mask fragments removed: {removed_components}. X7 remains locked.", font=font(18, True), fill="#159570")
    canvas.save(QA / "x6-joint-safe-motion-bundle-review-v4.png", optimize=True)


def main() -> None:
    QA.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    visible = json.loads(VISIBLE_CONTRACT.read_text(encoding="utf-8"))["layers"]
    x5_layers = json.loads(X5_SPLIT_CONTRACT.read_text(encoding="utf-8"))["layers"]
    stack = json.loads(STACK_CONTRACT.read_text(encoding="utf-8"))
    x5_by_key = {(record["view"], record["id"]): record for record in x5_layers}
    visible_by_bundle: dict[tuple[str, str], list[dict]] = {}
    original_by_bundle: dict[tuple[str, str], list[dict]] = {}
    for record in visible:
        bundle_id = classify(record["id"])
        key = (record["view"], bundle_id)
        visible_by_bundle.setdefault(key, []).append(record)
        original_by_bundle.setdefault(key, []).append(x5_by_key[(record["view"], record["id"])])

    placement_by_bundle: dict[tuple[str, str], list[dict]] = {}
    for placement in stack["placements"]:
        bundle_ids = {classify(target) for target in placement["targetVisibleLayers"]}
        for bundle_id in bundle_ids:
            placement_by_bundle.setdefault((placement["view"], bundle_id), []).append(placement)

    bundle_images: dict[tuple[str, str], Image.Image] = {}
    source_reserves: dict[tuple[str, str], Image.Image] = {}
    cleanup: dict[tuple[str, str], tuple[int, int]] = {}
    for key, records in visible_by_bundle.items():
        image, removed_components, removed_pixels = compose_records(records, clean=True)
        bundle_images[key] = image
        cleanup[key] = (removed_components, removed_pixels)
        original, _, _ = compose_records(original_by_bundle[key], clean=False)
        source_reserves[key] = original

    overlaps: dict[tuple[str, str], Image.Image] = {}
    audits: list[dict] = []
    exports: list[dict] = []
    for key, visible_image in bundle_images.items():
        view, bundle_id = key
        parent_id, controller = BUNDLE_META[bundle_id]
        effective_parent_id = parent_id
        occluded_parent_fallback = False
        if parent_id and (view, parent_id) not in bundle_images and (view, "body") in bundle_images:
            effective_parent_id = "body"
            occluded_parent_fallback = True
        visible_alpha = visible_image.getchannel("A")
        overlap = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        overlap_pixels = 0
        cover_bundle_ids = [effective_parent_id] if effective_parent_id else []
        if bundle_id in {"arm_L_upper", "arm_R_upper"} and (view, "head") in bundle_images:
            cover_bundle_ids.append("head")
        if effective_parent_id and (view, effective_parent_id) in bundle_images:
            parent_alpha = Image.new("L", CANVAS, 0)
            for cover_bundle_id in cover_bundle_ids:
                parent_alpha = ImageChops.lighter(
                    parent_alpha,
                    bundle_images[(view, cover_bundle_id)].getchannel("A"),
                )
            requested_width = COLLAR_WIDTH[bundle_id]
            collar_width = requested_width
            collar = Image.new("L", CANVAS, 0)
            for candidate_width in sorted({requested_width, 51, 75, 101, 151}):
                if candidate_width < requested_width:
                    continue
                candidate_width += 1 - candidate_width % 2
                grown = visible_alpha.filter(ImageFilter.MaxFilter(candidate_width))
                candidate = ImageChops.darker(parent_alpha, ImageChops.subtract(grown, visible_alpha))
                collar = candidate
                collar_width = candidate_width
                if alpha_pixels(candidate) >= 64:
                    break
            if bundle_id in {"arm_L_upper", "arm_R_upper"}:
                collar = localized_shoulder_cap(visible_alpha, parent_alpha, collar)
            elif occluded_parent_fallback:
                collar = bridge_to_collar(visible_alpha, collar, 19)
            reserve = source_reserves[key].copy()
            underpaint = compose_placements(placement_by_bundle.get(key, []))
            reserve.alpha_composite(underpaint)
            blurred = visible_image.filter(ImageFilter.GaussianBlur(max(2, collar_width // 5)))
            mean = ImageStat.Stat(visible_image.convert("RGB"), mask=visible_alpha).mean
            fallback = Image.new("RGBA", CANVAS, tuple(round(value) for value in mean) + (255,))
            fallback.putalpha(collar)
            blurred.putalpha(ImageChops.darker(blurred.getchannel("A"), collar))
            fallback.alpha_composite(blurred)
            overlap.alpha_composite(fallback)
            reserve.putalpha(ImageChops.darker(reserve.getchannel("A"), collar))
            overlap.alpha_composite(reserve)
            overlap.putalpha(collar)
            overlap_pixels = alpha_pixels(collar)
        overlaps[key] = overlap

        visible_bounds = visible_alpha.getbbox()
        visible_name = f"{view}_{bundle_id}_visible.png"
        visible_image.crop(visible_bounds).save(OUT / visible_name, optimize=True)
        overlap_bounds = overlap.getchannel("A").getbbox()
        overlap_name = None
        if overlap_bounds:
            overlap_name = f"{view}_{bundle_id}_hidden-collar.png"
            overlap.crop(overlap_bounds).save(OUT / overlap_name, optimize=True)
        removed_components, removed_pixels = cleanup[key]
        record = {
            "view": view,
            "bundle": bundle_id,
            "parentBundle": parent_id,
            "effectiveParentBundleInView": effective_parent_id,
            "occlusionCoverBundles": cover_bundle_ids,
            "occludedParentFallback": occluded_parent_fallback,
            "primaryController": controller,
            "visibleFile": f"live2d/x6/joint-safe-motion-bundles-v4/{visible_name}",
            "visibleBounds": list(visible_bounds),
            "hiddenCollarFile": f"live2d/x6/joint-safe-motion-bundles-v4/{overlap_name}" if overlap_name else None,
            "hiddenCollarBounds": list(overlap_bounds) if overlap_bounds else None,
            "overlapPixels": overlap_pixels,
            "collarWidthPixels": COLLAR_WIDTH.get(bundle_id, 0),
            "shoulderCapMode": "rounded-broad-underlap" if bundle_id in {"arm_L_upper", "arm_R_upper"} else None,
            "removedComponents": removed_components,
            "removedPixels": removed_pixels,
            "drawRule": "hidden collar moves with child but renders behind parent; visible child renders above parent",
        }
        exports.append(record)
        if effective_parent_id:
            audits.append(record)

    missing_overlap = [f"{row['view']}:{row['bundle']}" for row in audits if row["overlapPixels"] == 0]
    if missing_overlap:
        raise ValueError(f"Missing joint overlap collars: {missing_overlap}")
    build_review(bundle_images, overlaps, audits)
    result = {
        "schemaVersion": 1,
        "stage": "X6-joint-safe-coarse-motion-bundle-candidate",
        "status": "candidate-for-user-visual-review",
        "strategy": "clean-visible-cuts-plus-separate-child-owned-hidden-joint-collars",
        "bundleVocabulary": list(BUNDLE_META),
        "bundleCount": len(BUNDLE_META),
        "viewBundleRecordCount": len(exports),
        "parentChildJointRecordCount": len(audits),
        "allParentChildJointsHaveOverlap": not missing_overlap,
        "minimumOverlapPixels": min(row["overlapPixels"] for row in audits),
        "isolatedComponentsRemoved": sum(row["removedComponents"] for row in exports),
        "isolatedPixelsRemoved": sum(row["removedPixels"] for row in exports),
        "exports": exports,
        "qa": {"review": "live2d/x6/qa/x6-joint-safe-motion-bundle-review-v4.png"},
        "gateBoundary": {
            "gate6Approved": False,
            "x7Authorized": False,
            "notPsd": True,
            "notCubism": True,
            "notPhysics": True,
        },
        "notes": [
            "Visible cuts and hidden overlap reserves are separate PNGs so rest-pose identity pixels are not replaced.",
            "The hidden collar follows the child bundle and is drawn behind its parent bundle.",
            "Small disconnected mask artifacts are removed only from body, limb and tail layer exports.",
            "This is X6 separation and overlap QA, not X7 elasticity or Cubism output.",
        ],
    }
    (X6 / "x6-joint-safe-motion-bundle-contract-v4.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": "ok",
        "viewBundleRecords": len(exports),
        "jointRecords": len(audits),
        "minimumOverlapPixels": result["minimumOverlapPixels"],
        "isolatedComponentsRemoved": result["isolatedComponentsRemoved"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
