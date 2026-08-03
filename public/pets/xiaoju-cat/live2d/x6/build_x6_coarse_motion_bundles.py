from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PET = ROOT.parent
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
OUT = X6 / "coarse-motion-bundles-v3"
VISIBLE_CONTRACT = X6 / "x6-layer-assembly-contract-v1.json"
STACK_CONTRACT = X6 / "x6-production-layer-stack-contract-v2.json"
CANVAS = (1774, 887)
VIEW_BOUNDS = {
    "front": (0, 0, 650, 887),
    "side": (650, 0, 1120, 887),
    "back": (1120, 0, 1774, 887),
}


BUNDLE_META = {
    "head": ("Body", "Head"),
    "mouth": ("Head", "Mouth"),
    "ear_L": ("Head", "EarRoot_L"),
    "ear_R": ("Head", "EarRoot_R"),
    "eye_L": ("Head", "EyeSocket_L"),
    "eye_R": ("Head", "EyeSocket_R"),
    "body": ("XiaojuRoot", "Body"),
    "arm_L_upper": ("Body", "Shoulder_L"),
    "arm_L_lower_paw": ("arm_L_upper", "Elbow_L"),
    "arm_R_upper": ("Body", "Shoulder_R"),
    "arm_R_lower_paw": ("arm_R_upper", "Elbow_R"),
    "leg_L_upper": ("Body", "Hip_L"),
    "leg_L_lower_paw": ("leg_L_upper", "Knee_L"),
    "leg_R_upper": ("Body", "Hip_R"),
    "leg_R_lower_paw": ("leg_R_upper", "Knee_R"),
    "tail": ("Body", "TailRoot"),
}


FAMILIES = {
    "HEAD / MOUTH / EARS / EYES": {"head", "mouth", "ear_L", "ear_R", "eye_L", "eye_R"},
    "BODY": {"body"},
    "ARMS: UPPER + LOWER/PAW": {"arm_L_upper", "arm_L_lower_paw", "arm_R_upper", "arm_R_lower_paw"},
    "LEGS: UPPER + LOWER/PAW": {"leg_L_upper", "leg_L_lower_paw", "leg_R_upper", "leg_R_lower_paw"},
    "TAIL": {"tail"},
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
    copy.thumbnail((size[0] - 12, size[1] - 12), Image.Resampling.LANCZOS)
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


def compose(records: list[dict]) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for record in sorted(records, key=lambda item: item["drawOrder"]):
        image = Image.open(PET / record["file"]).convert("RGBA")
        canvas.alpha_composite(image, (record["bounds"][0], record["bounds"][1]))
    return canvas


def build_review(records: list[dict], assignments: dict[tuple[str, str], str], bundles: list[dict]) -> None:
    canvas = Image.new("RGB", (1900, 1510), "#f5f7f9")
    draw = ImageDraw.Draw(canvas)
    draw.text((52, 30), "X6  Coarse Motion Bundles over Fine Internal Layers", font=font(39, True), fill="#17324d")
    draw.text((54, 82), "Visible action control is reduced to 16 anatomical bundles. Fine PNG and mesh layers remain internal children.", font=font(20), fill="#5f6e7b")
    draw.rounded_rectangle((48, 122, 1852, 220), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((72, 144), "Head | Mouth | Ear L/R | Eye L/R | Body | Upper arm L/R | Forearm+Paw L/R | Thigh L/R | Shin+Paw L/R | Tail", font=font(21, True), fill="#1769d2")
    draw.text((72, 184), "Shoulder, elbow, hip and knee remain pivots/deformers; they are not extra visible art pieces.", font=font(18), fill="#5f6e7b")

    view_records = {view: [record for record in records if record["view"] == view] for view in VIEW_BOUNDS}
    for column, view in enumerate(("front", "side", "back")):
        x = 250 + column * 550
        draw.text((x + 195, 245), view.upper(), font=font(25, True), fill="#17324d")
        for row, (family, bundle_ids) in enumerate(FAMILIES.items()):
            y = 285 + row * 220
            if column == 0:
                draw.text((28, y + 82), family, font=font(16, True), fill="#5f6e7b")
            draw.rounded_rectangle((x, y, x + 510, y + 190), radius=8, fill="white", outline="#cbd5df", width=2)
            subset = [
                record for record in view_records[view]
                if assignments[(record["view"], record["id"])] in bundle_ids
            ]
            image = compose(subset)
            alpha_bounds = image.getchannel("A").getbbox()
            image = image.crop(alpha_bounds)
            canvas.paste(fit(image, (484, 154)).convert("RGB"), (x + 13, y + 24))
            active = sorted({assignments[(record["view"], record["id"])] for record in subset})
            draw.text((x + 14, y + 4), f"{len(subset)} internal layers / {len(active)} bundles", font=font(14), fill="#5f6e7b")

    draw.rounded_rectangle((48, 1400, 1852, 1472), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((72, 1421), f"Audit: {len(records)}/{len(records)} visible layers uniquely assigned; {len(bundles)} view-bundle records; no X7 or Cubism output.", font=font(19, True), fill="#159570")
    canvas.save(QA / "x6-coarse-motion-bundle-review-v3.png", optimize=True)


def main() -> None:
    QA.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    visible_contract = json.loads(VISIBLE_CONTRACT.read_text(encoding="utf-8"))
    stack_contract = json.loads(STACK_CONTRACT.read_text(encoding="utf-8"))
    records = visible_contract["layers"]
    assignments: dict[tuple[str, str], str] = {}
    for record in records:
        key = (record["view"], record["id"])
        if key in assignments:
            raise ValueError(f"Duplicate visible-layer key: {key}")
        assignments[key] = classify(record["id"])

    placement_bundles: dict[str, set[str]] = {}
    for placement in stack_contract["placements"]:
        placement_key = placement["file"]
        target_bundles = {
            assignments[(placement["view"], target_id)]
            for target_id in placement["targetVisibleLayers"]
        }
        placement_bundles[placement_key] = target_bundles

    bundles = []
    for view in VIEW_BOUNDS:
        for bundle_id in BUNDLE_META:
            layers = [record for record in records if record["view"] == view and assignments[(view, record["id"])] == bundle_id]
            if not layers:
                continue
            composite = compose(layers)
            alpha_bounds = composite.getchannel("A").getbbox()
            filename = f"{view}_{bundle_id}.png"
            composite.crop(alpha_bounds).save(OUT / filename, optimize=True)
            fine_files = sorted(
                path for path, bundle_ids in placement_bundles.items()
                if bundle_id in bundle_ids and any(p["file"] == path and p["view"] == view for p in stack_contract["placements"])
            )
            parent, controller = BUNDLE_META[bundle_id]
            bundles.append(
                {
                    "view": view,
                    "id": bundle_id,
                    "parentBundle": parent,
                    "primaryController": controller,
                    "file": f"live2d/x6/coarse-motion-bundles-v3/{filename}",
                    "bounds": list(alpha_bounds),
                    "visibleLayerIds": [record["id"] for record in layers],
                    "visibleLayerCount": len(layers),
                    "fineUnderpaintFiles": fine_files,
                    "fineUnderpaintCount": len(fine_files),
                    "rule": "one coarse action subject; internal PNG/mesh layers keep their own masks and topology",
                }
            )

    assigned_visible = len(assignments)
    assigned_placements = sum(bool(bundle_ids) for bundle_ids in placement_bundles.values())
    result = {
        "schemaVersion": 1,
        "stage": "X6-coarse-motion-bundle-candidate",
        "status": "candidate-for-user-visual-review",
        "strategy": "coarse-action-bundles-over-fine-internal-layer-mesh-nodes",
        "bundleVocabulary": list(BUNDLE_META),
        "bundleCount": len(BUNDLE_META),
        "visibleLayerCount": len(records),
        "visibleLayersUniquelyAssigned": assigned_visible == len(records),
        "finePlacementCount": len(stack_contract["placements"]),
        "finePlacementsAssigned": assigned_placements,
        "allFinePlacementsAssigned": assigned_placements == len(stack_contract["placements"]),
        "bundles": bundles,
        "qa": {"review": "live2d/x6/qa/x6-coarse-motion-bundle-review-v3.png"},
        "gateBoundary": {
            "gate6Approved": False,
            "x7Authorized": False,
            "notPsd": True,
            "notCubism": True,
            "notPhysics": True,
        },
        "notes": [
            "Forearm and fore paw are one coarse action bundle per side.",
            "Hind shin and hind paw are one coarse action bundle per side.",
            "Eyes, lids and highlights remain fine internal layers under one Eye bundle per side.",
            "Tail remains one visible action bundle so later X7 elasticity can use internal TailRoot/TailMid/TailTip nodes without another art split.",
        ],
    }
    (X6 / "x6-coarse-motion-bundle-contract-v3.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    build_review(records, assignments, bundles)
    print(json.dumps({
        "status": "ok",
        "bundleVocabulary": len(BUNDLE_META),
        "viewBundleRecords": len(bundles),
        "visibleAssigned": assigned_visible,
        "fineAssigned": assigned_placements,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
