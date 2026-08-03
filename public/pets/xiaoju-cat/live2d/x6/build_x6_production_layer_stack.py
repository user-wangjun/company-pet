from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat


ROOT = Path(__file__).resolve().parents[1]
PET = ROOT.parent
X5 = ROOT / "x5"
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
OUT = X6 / "fine-body-space-underpaint-v2"
VISIBLE_CONTRACT = X6 / "x6-layer-assembly-contract-v1.json"
FINE_CONTRACT = X5 / "x5-generated-fine-layer-candidates-contract-v1.json"
CANVAS = (1774, 887)


ALIASES = {
    1: [("front", ("head_base",))],
    5: [("side", ("head_base",))],
    9: [("back", ("ear_face_L",)), ("back", ("ear_face_R",))],
    25: [("front", ("neck_fill",)), ("side", ("chest_fur",)), ("back", ("neck_fill",))],
    27: [("front", ("ribcage",))],
    28: [("front", ("abdomen",))],
    29: [("front", ("pelvis",))],
    30: [("side", ("ribcage",)), ("side", ("abdomen",)), ("side", ("pelvis",))],
    31: [("front", ("upper_arm_L",)), ("back", ("upper_arm_L",))],
    32: [(view, ("fore_paw_L",)) for view in ("front", "side", "back")],
    33: [(view, ("forearm_L",)) for view in ("front", "side", "back")],
    34: [(view, ("upper_arm_R",)) for view in ("front", "side", "back")],
    35: [(view, ("forearm_R",)) for view in ("front", "side", "back")],
    36: [(view, ("fore_paw_R",)) for view in ("front", "side", "back")],
    37: [("side", ("fore_paw_L",))],
    38: [(view, ("hind_thigh_L",)) for view in ("front", "side", "back")],
    39: [(view, ("hind_shin_L",)) for view in ("front", "side", "back")],
    40: [("front", ("hind_thigh_R",)), ("back", ("hind_thigh_R",))],
    41: [(view, ("hind_shin_R",)) for view in ("front", "side", "back")],
    42: [("side", ("hind_thigh_L",)), ("side", ("hind_shin_L",)), ("side", ("hind_paw_L",))],
    43: [("side", ("hind_shin_R",)), ("side", ("hind_paw_R",))],
    44: [("front", ("tail_root_socket",)), ("side", ("tail_mid",)), ("back", ("tail_mid",))],
    45: [(view, ("tail_mid",)) for view in ("front", "side", "back")],
    46: [(view, ("tail_mid",)) for view in ("front", "side", "back")],
    47: [("side", ("tail_mid", "tail_tip"))],
    48: [(view, ("tail_mid",)) for view in ("front", "side", "back")],
    49: [(view, ("tail_tip",)) for view in ("front", "side", "back")],
    50: [(view, ("tail_tip",)) for view in ("front", "side", "back")],
    51: [("back", ("head_base",))],
    52: [("side", ("head_base",))],
    53: [("side", ("head_base",))],
    54: [("back", ("neck_fill",))],
    55: [("back", ("ribcage",))],
    56: [("back", ("pelvis",))],
    57: [("back", ("upper_arm_L",)), ("back", ("forearm_L",)), ("back", ("fore_paw_L",))],
    58: [("back", ("upper_arm_R",)), ("back", ("forearm_R",)), ("back", ("fore_paw_R",))],
    59: [
        ("back", ("hind_thigh_L",)), ("back", ("hind_shin_L",)), ("back", ("hind_paw_L",)),
        ("back", ("hind_thigh_R",)), ("back", ("hind_shin_R",)), ("back", ("hind_paw_R",)),
    ],
    60: [("back", ("ribcage",))],
    61: [("back", ("abdomen",))],
    62: [("back", ("pelvis",))],
    63: [("back", ("pelvis",)), ("back", ("abdomen",))],
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    paths = (
        Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    )
    for path in paths:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def checker(size: tuple[int, int], block: int = 12) -> Image.Image:
    image = Image.new("RGBA", size, (247, 248, 249, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(224, 229, 233, 255))
    return image


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    background = checker(size)
    copy = image.copy()
    copy.thumbnail((size[0] - 20, size[1] - 20), Image.Resampling.LANCZOS)
    background.alpha_composite(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return background


def union_bounds(records: list[dict]) -> tuple[int, int, int, int]:
    return (
        min(record["bounds"][0] for record in records),
        min(record["bounds"][1] for record in records),
        max(record["bounds"][2] for record in records),
        max(record["bounds"][3] for record in records),
    )


def remove_guide_fringe(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if a and g > r * 1.16 and g > b * 1.12:
                pixels[x, y] = (r, min(g, max(r, b) + 12), b, max(0, a - 110))
    return rgba


def expansion_for(target_ids: tuple[str, ...]) -> tuple[int, int]:
    joined = " ".join(target_ids)
    if any(token in joined for token in ("arm", "forearm", "paw", "thigh", "shin", "wrist", "scapula")):
        return 34, 51
    if any(token in joined for token in ("ribcage", "abdomen", "pelvis", "neck", "chest", "head_base")):
        return 10, 11
    if any(token in joined for token in ("ear", "tail", "cheek", "muzzle")):
        return 6, 7
    return 3, 3


def expand_bounds(bounds: tuple[int, int, int, int], padding: int) -> tuple[int, int, int, int]:
    return (
        max(0, bounds[0] - padding),
        max(0, bounds[1] - padding),
        min(CANVAS[0], bounds[2] + padding),
        min(CANVAS[1], bounds[3] + padding),
    )


def target_mask(
    records: list[dict],
    bounds: tuple[int, int, int, int],
    dilation: int,
    rest_alpha: Image.Image,
) -> Image.Image:
    mask = Image.new("L", (bounds[2] - bounds[0], bounds[3] - bounds[1]), 0)
    for record in records:
        alpha = Image.open(PET / record["file"]).convert("RGBA").getchannel("A")
        layer = Image.new("L", mask.size, 0)
        layer.paste(alpha, (record["bounds"][0] - bounds[0], record["bounds"][1] - bounds[1]))
        mask = ImageChops.lighter(mask, layer)
    if dilation > 1:
        mask = mask.filter(ImageFilter.MaxFilter(dilation))
    if dilation >= 51:
        bridge = rest_alpha.crop(bounds)
        mask = ImageChops.lighter(mask, bridge)
    return mask


def transform_underpaint(source: Image.Image, bounds: tuple[int, int, int, int], mask: Image.Image) -> Image.Image:
    width = max(1, bounds[2] - bounds[0])
    height = max(1, bounds[3] - bounds[1])
    clean = remove_guide_fringe(source)
    alpha = clean.getchannel("A")
    means = ImageStat.Stat(clean.convert("RGB"), mask=alpha).mean
    base_color = tuple(max(0, min(255, round(value))) for value in means)
    material = Image.new("RGBA", clean.size, (*base_color, 255))
    material.alpha_composite(clean)
    material = ImageOps.fit(material, (width, height), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    material.putalpha(mask)
    return material


def compose_visible(layers: list[dict], hidden: set[str] | None = None) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    hidden = hidden or set()
    for record in sorted(layers, key=lambda item: item["drawOrder"]):
        key = f"{record['view']}:{record['id']}"
        if key in hidden:
            continue
        image = Image.open(PET / record["file"]).convert("RGBA")
        canvas.alpha_composite(image, (record["bounds"][0], record["bounds"][1]))
    return canvas


def compose_underpaint(placements: list[dict]) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for record in placements:
        if record["role"] == "hairline-reference-no-area-underpaint":
            continue
        image = Image.open(PET / record["file"]).convert("RGBA")
        canvas.alpha_composite(image, (record["bounds"][0], record["bounds"][1]))
    return canvas


def clip_to_rest_body(image: Image.Image, rest: Image.Image) -> Image.Image:
    clipped = image.copy()
    clipped.putalpha(ImageChops.darker(clipped.getchannel("A"), rest.getchannel("A")))
    return clipped


def targets_for(fine: dict, visible_by_key: dict[tuple[str, str], dict]) -> list[tuple[str, tuple[str, ...]]]:
    if fine["index"] in ALIASES:
        return ALIASES[fine["index"]]
    key = (fine["view"], fine["id"])
    if key in visible_by_key:
        return [(fine["view"], (fine["id"],))]
    raise KeyError(f"No body-space target for fine layer {fine['index']}:{fine['id']}")


def build_coverage_audit(placements: list[dict], visible_layers: list[dict]) -> dict:
    threshold = 0.55
    exempt = {
        "front:whisker_L": "hairline layer; no area underpaint required",
        "front:whisker_R": "hairline layer; no area underpaint required",
    }
    by_target: dict[tuple[str, str], list[dict]] = {}
    for placement in placements:
        for target_id in placement["targetVisibleLayers"]:
            by_target.setdefault((placement["view"], target_id), []).append(placement)

    rows = []
    for visible in visible_layers:
        key = (visible["view"], visible["id"])
        if key not in by_target:
            continue
        target = Image.open(PET / visible["file"]).convert("RGBA").getchannel("A")
        x0, y0, x1, y1 = visible["bounds"]
        merged = Image.new("L", target.size, 0)
        for placement in by_target[key]:
            alpha = Image.open(PET / placement["file"]).convert("RGBA").getchannel("A")
            px0, py0, _, _ = placement["bounds"]
            local = Image.new("L", target.size, 0)
            local.paste(alpha, (px0 - x0, py0 - y0))
            merged = ImageChops.lighter(merged, local)
        target_bytes = target.tobytes()
        merged_bytes = merged.tobytes()
        target_pixels = sum(value > 8 for value in target_bytes)
        covered_pixels = sum(a > 8 and b > 8 for a, b in zip(target_bytes, merged_bytes))
        coverage = covered_pixels / target_pixels if target_pixels else 1.0
        target_key = f"{key[0]}:{key[1]}"
        reason = exempt.get(target_key)
        rows.append(
            {
                "target": target_key,
                "targetAlphaPixels": target_pixels,
                "coveredAlphaPixels": covered_pixels,
                "coverage": round(coverage, 6),
                "instanceCount": len(by_target[key]),
                "exempt": reason is not None,
                "exemptionReason": reason,
                "passes": reason is not None or coverage >= threshold,
            }
        )
    required = [row for row in rows if not row["exempt"]]
    moving_tokens = ("upper_arm", "forearm", "fore_paw", "hind_thigh", "hind_shin", "hind_paw")
    mapped_keys = {
        (placement["view"], target_id)
        for placement in placements
        for target_id in placement["targetVisibleLayers"]
    }
    required_moving = [
        f"{visible['view']}:{visible['id']}"
        for visible in visible_layers
        if any(token in visible["id"] for token in moving_tokens)
    ]
    missing_moving = [
        key for key in required_moving if tuple(key.split(":", 1)) not in mapped_keys
    ]
    result = {
        "schemaVersion": 1,
        "stage": "X6-production-layer-stack-alpha-coverage-audit",
        "status": "pass-candidate",
        "threshold": threshold,
        "targetCount": len(rows),
        "requiredTargetCount": len(required),
        "exemptTargetCount": len(rows) - len(required),
        "requiredPassCount": sum(row["passes"] for row in required),
        "minimumRequiredCoverage": round(min(row["coverage"] for row in required), 6),
        "averageRequiredCoverage": round(sum(row["coverage"] for row in required) / len(required), 6),
        "allRequiredTargetsPass": all(row["passes"] for row in required),
        "requiredMovingLayerCount": len(required_moving),
        "mappedMovingLayerCount": len(required_moving) - len(missing_moving),
        "missingMovingLayers": missing_moving,
        "allRequiredMovingLayersMapped": not missing_moving,
        "targets": sorted(rows, key=lambda row: row["coverage"]),
        "gateBoundary": {"gate6Approved": False, "x7Authorized": False},
    }
    (X6 / "x6-production-layer-stack-coverage-audit-v2.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def build_review(rest: Image.Image, underpaint: Image.Image, reveal: Image.Image, counts: dict) -> None:
    canvas = Image.new("RGB", (1900, 1350), "#f5f7f9")
    draw = ImageDraw.Draw(canvas)
    draw.text((52, 34), "X6  Production Layer Stack: Visible Art + Hidden Underpaint", font=font(39, True), fill="#17324d")
    draw.text((54, 88), "The rest pose keeps Xiaoju's approved source pixels. The 63 fine materials sit behind their semantic joints and regions.", font=font(20), fill="#5f6e7b")
    panels = (
        ("Rest composite from visible PNG layers", rest),
        ("Body-space map of fine underpaint", underpaint),
        ("Selected visible layers disabled", reveal),
    )
    for i, (title, image) in enumerate(panels):
        x = 48 + i * 616
        draw.rounded_rectangle((x, 138, x + 580, 795), radius=8, fill="white", outline="#cbd5df", width=2)
        draw.text((x + 20, 158), title, font=font(23, True), fill="#17324d")
        canvas.paste(fit(image, (552, 550)).convert("RGB"), (x + 14, 205))
    draw.text((68, 755), "Identity-safe visible stack", font=font(18, True), fill="#159570")
    draw.text((684, 755), "Underpaint is not a replacement skin", font=font(18, True), fill="#1769d2")
    draw.text((1300, 755), "Open joints reveal registered fill", font=font(18, True), fill="#d26a2e")

    draw.rounded_rectangle((48, 835, 1852, 1280), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((74, 862), "Layer-stack audit", font=font(28, True), fill="#17324d")
    rows = (
        ("Visible coordinate-aligned PNG layers", str(counts["visibleLayers"]), "rest-pose identity and draw order"),
        ("Fine independent PNG materials", str(counts["fineMaterials"]), "hidden fill, overlap and deformation reserve"),
        ("Fine body-space instances", str(counts["finePlacements"]), "all instances have explicit view and pixel bounds"),
        ("Unmapped fine materials", str(counts["unmapped"]), "must remain zero"),
        ("Current gate", "X6 candidate", "X7 remains locked until explicit user approval"),
    )
    for row, (label, value, note) in enumerate(rows):
        y = 930 + row * 62
        draw.text((88, y), label, font=font(20, True), fill="#24303a")
        draw.text((715, y), value, font=font(20, True), fill="#1769d2" if row < 4 else "#d26a2e")
        if label == "Unmapped fine materials":
            note = (
                f"{note}; area {counts['coveragePassed']}/{counts['coverageRequired']}, "
                f"moving layers {counts['movingLayersMapped']}/{counts['movingLayersRequired']}"
            )
        draw.text((970, y), note, font=font(18), fill="#5f6e7b")
        draw.line((78, y + 38, 1818, y + 38), fill="#e1e6eb", width=1)
    draw.text((54, 1310), "Candidate only: no PSD, Cubism, Physics, runtime replacement or X7 work was performed.", font=font(18, True), fill="#d26a2e")
    canvas.save(QA / "x6-production-layer-stack-review-v2.png", optimize=True)


def build_joint_detail(rest: Image.Image, underpaint: Image.Image, visible_layers: list[dict]) -> None:
    specs = {
        "FRONT": {
            "crop": (30, 250, 640, 760),
            "hidden": {
                f"front:{name}" for name in (
                    "upper_arm_L", "forearm_L", "upper_arm_R", "forearm_R",
                    "hind_thigh_L", "hind_shin_L", "hind_thigh_R", "hind_shin_R",
                )
            },
        },
        "SIDE": {
            "crop": (650, 250, 1110, 790),
            "hidden": {
                f"side:{name}" for name in (
                    "forearm_L", "upper_arm_R", "forearm_R", "hind_thigh_L", "hind_shin_L",
                    "hind_shin_R",
                )
            },
        },
        "BACK": {
            "crop": (1130, 250, 1690, 790),
            "hidden": {
                f"back:{name}" for name in (
                    "upper_arm_L", "forearm_L", "upper_arm_R", "forearm_R",
                    "hind_thigh_L", "hind_shin_L", "hind_thigh_R", "hind_shin_R",
                )
            },
        },
    }
    canvas = Image.new("RGB", (1900, 1510), "#f5f7f9")
    draw = ImageDraw.Draw(canvas)
    draw.text((52, 34), "X6  Joint-Opened Hidden-Fill Detail", font=font(40, True), fill="#17324d")
    draw.text((54, 88), "Each column uses the same view crop. Middle row disables the visible limb layers; bottom row shows only registered fine underpaint.", font=font(20), fill="#5f6e7b")
    row_labels = ("REST", "VISIBLE LIMBS OFF", "UNDERPAINT ONLY")
    for column, (view, spec) in enumerate(specs.items()):
        x = 170 + column * 570
        draw.text((x + 190, 142), view, font=font(26, True), fill="#17324d")
        knockout = underpaint.copy()
        knockout.alpha_composite(compose_visible(visible_layers, hidden=spec["hidden"]))
        images = (rest, knockout, underpaint)
        for row, (label, image) in enumerate(zip(row_labels, images)):
            y = 190 + row * 405
            if column == 0:
                draw.text((28, y + 135), label, font=font(18, True), fill="#5f6e7b")
            draw.rounded_rectangle((x, y, x + 520, y + 360), radius=8, fill="white", outline="#cbd5df", width=2)
            crop = image.crop(spec["crop"])
            canvas.paste(fit(crop, (494, 324)).convert("RGB"), (x + 13, y + 18))
        draw.text((x, 1420), f"disabled visible limb layers: {len(spec['hidden'])}", font=font(17), fill="#5f6e7b")
    draw.text((54, 1470), "Review target: no reversed chain, exterior leak, empty shoulder/hip socket, or disconnected paw reserve.", font=font(19, True), fill="#d26a2e")
    canvas.save(QA / "x6-production-layer-stack-joint-detail-v2.png", optimize=True)


def main() -> None:
    QA.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    visible_contract = json.loads(VISIBLE_CONTRACT.read_text(encoding="utf-8"))
    fine_contract = json.loads(FINE_CONTRACT.read_text(encoding="utf-8"))
    visible_layers = visible_contract["layers"]
    visible_by_key = {(record["view"], record["id"]): record for record in visible_layers}
    rest = compose_visible(visible_layers)
    rest_alpha = rest.getchannel("A")

    placements = []
    material_hashes = {}
    for fine in fine_contract["layers"]:
        source_path = PET / fine["file"]
        source = Image.open(source_path).convert("RGBA")
        material_hashes[str(fine["index"])] = hashlib.sha256(source_path.read_bytes()).hexdigest()
        for instance, (view, target_ids) in enumerate(targets_for(fine, visible_by_key), start=1):
            targets = [visible_by_key[(view, target_id)] for target_id in target_ids]
            target_bounds = union_bounds(targets)
            padding, dilation = expansion_for(target_ids)
            bounds = expand_bounds(target_bounds, padding)
            mask = target_mask(targets, bounds, dilation, rest_alpha)
            transformed = transform_underpaint(source, bounds, mask)
            filename = f"{fine['index']:02d}_{view}_{fine['id']}_{instance}.png"
            transformed.save(OUT / filename, optimize=True)
            placements.append(
                {
                    "fineIndex": fine["index"],
                    "fineId": fine["id"],
                    "view": view,
                    "targetVisibleLayers": list(target_ids),
                    "targetBounds": list(target_bounds),
                    "bounds": list(bounds),
                    "paddingPixels": padding,
                    "maskDilationPixels": dilation,
                    "file": f"live2d/x6/fine-body-space-underpaint-v2/{filename}",
                    "defaultVisibility": "reference-only" if fine["index"] in (23, 24) else "behind-visible-source-layer",
                    "role": "hairline-reference-no-area-underpaint" if fine["index"] in (23, 24) else "hidden-underpaint-and-safe-overlap",
                    "parent": fine["parent"],
                    "pivot": fine["pivot"],
                }
            )

    raw_underpaint = compose_underpaint(placements)
    underpaint = clip_to_rest_body(raw_underpaint, rest)
    disabled = {
        "front:upper_arm_L",
        "front:forearm_L",
        "front:hind_thigh_R",
        "side:ribcage",
        "back:upper_arm_R",
        "back:pelvis",
    }
    reveal = underpaint.copy()
    reveal.alpha_composite(compose_visible(visible_layers, hidden=disabled))
    rest.save(QA / "x6-production-layer-stack-rest-v2.png", optimize=True)
    underpaint.save(QA / "x6-production-layer-stack-underpaint-map-v2.png", optimize=True)
    raw_underpaint.save(QA / "x6-production-layer-stack-underpaint-unclipped-audit-v2.png", optimize=True)
    reveal.save(QA / "x6-production-layer-stack-knockout-v2.png", optimize=True)

    coverage_audit = build_coverage_audit(placements, visible_layers)
    counts = {
        "visibleLayers": len(visible_layers),
        "fineMaterials": len(fine_contract["layers"]),
        "finePlacements": len(placements),
        "unmapped": 0,
        "coverageRequired": coverage_audit["requiredTargetCount"],
        "coveragePassed": coverage_audit["requiredPassCount"],
        "coverageExempt": coverage_audit["exemptTargetCount"],
        "minimumRequiredCoverage": coverage_audit["minimumRequiredCoverage"],
        "averageRequiredCoverage": coverage_audit["averageRequiredCoverage"],
        "movingLayersRequired": coverage_audit["requiredMovingLayerCount"],
        "movingLayersMapped": coverage_audit["mappedMovingLayerCount"],
    }
    build_review(rest, underpaint, reveal, counts)
    build_joint_detail(rest, underpaint, visible_layers)
    result = {
        "schemaVersion": 1,
        "stage": "X6-production-layer-stack-candidate",
        "status": "candidate-for-user-visual-review",
        "strategy": "coordinate-aligned-visible-source-layers-plus-body-space-fine-underpaint",
        "productionLayerAssemblyComplete": False,
        "fine63BodySpacePlacementComplete": True,
        "fine63PlacementApprovedByUser": False,
        "visibleRestPoseUsesWholeSourceImage": False,
        "visibleRestPoseUsesCoordinateAlignedLayerPngs": True,
        "fineMaterialsReplaceVisibleIdentityPixels": False,
        "counts": counts,
        "disabledForKnockoutProof": sorted(disabled),
        "materialSha256": material_hashes,
        "placements": placements,
        "qa": {
            "rest": "live2d/x6/qa/x6-production-layer-stack-rest-v2.png",
            "underpaintMap": "live2d/x6/qa/x6-production-layer-stack-underpaint-map-v2.png",
            "underpaintUnclippedAudit": "live2d/x6/qa/x6-production-layer-stack-underpaint-unclipped-audit-v2.png",
            "knockout": "live2d/x6/qa/x6-production-layer-stack-knockout-v2.png",
            "review": "live2d/x6/qa/x6-production-layer-stack-review-v2.png",
            "jointDetail": "live2d/x6/qa/x6-production-layer-stack-joint-detail-v2.png",
            "coverageAudit": "live2d/x6/x6-production-layer-stack-coverage-audit-v2.json",
        },
        "gateBoundary": {
            "currentGate": "x6-parameter-action-tracer",
            "gate6Approved": False,
            "x7Authorized": False,
            "notPsd": True,
            "notCubism": True,
            "notPhysics": True,
            "notRuntime": True,
        },
        "knownLimits": [
            "Fine materials are registered as hidden underpaint and overlap reserves; they do not replace approved visible source pixels at rest.",
            "Body-space placement is a candidate until the user reviews the rest, underpaint map and knockout proof.",
            "Actual hidden-area painting quality can only be accepted after joint-separated visual review at this gate.",
        ],
    }
    (X6 / "x6-production-layer-stack-contract-v2.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "ok", **counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
