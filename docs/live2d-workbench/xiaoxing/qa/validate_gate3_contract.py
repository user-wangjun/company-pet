from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
CONTRACT_PATH = ROOT / "blueprints" / "gate3-production-blueprint-contract.json"
ALIGNMENT_PATH = ROOT / "audit" / "gate3-hand-pixel-alignment.json"
HAND_DRAFT_PATH = ROOT / "audit" / "gate3-hand-draft-validation.json"
HAND_SIMPLE_PATH = ROOT / "audit" / "gate3-hand-simple-validation.json"
OUT = ROOT / "audit" / "gate3-contract-validation.json"


def check(condition: bool, name: str, details: str, results: list[dict]):
    results.append({"name": name, "passed": bool(condition), "details": details})


def main():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    alignment = json.loads(ALIGNMENT_PATH.read_text(encoding="utf-8"))
    hand_draft = json.loads(HAND_DRAFT_PATH.read_text(encoding="utf-8")) if HAND_DRAFT_PATH.exists() else {"status": "missing"}
    hand_simple = json.loads(HAND_SIMPLE_PATH.read_text(encoding="utf-8")) if HAND_SIMPLE_PATH.exists() else {"status": "missing"}
    layers = contract["layers"]
    ids = [layer["id"] for layer in layers]
    orders = [layer["drawOrder"] for layer in layers]
    results: list[dict] = []

    check(contract["layerCount"] == len(layers), "layer_count", f"declared={contract['layerCount']} actual={len(layers)}", results)
    check(len(ids) == len(set(ids)), "unique_layer_ids", f"unique={len(set(ids))}", results)
    check(len(orders) == len(set(orders)), "unique_draw_orders", f"unique={len(set(orders))}", results)
    expected_order = [layer["id"] for layer in sorted(layers, key=lambda item: item["drawOrder"])]
    check(contract["drawOrderBackToFront"] == expected_order, "draw_order_projection", "list matches sorted layer drawOrder", results)

    layer_parent_from_tree: dict[str, str] = {}
    for parent, children in contract["deformerTree"].items():
        for child in children:
            if child in ids:
                layer_parent_from_tree[child] = parent
    missing = sorted(set(ids) - set(layer_parent_from_tree))
    mismatched = sorted(
        layer["id"] for layer in layers
        if layer_parent_from_tree.get(layer["id"]) != layer["parent"]
    )
    check(not missing, "all_layers_in_tree", f"missing={missing}", results)
    check(not mismatched, "single_parent_consistency", f"mismatched={mismatched}", results)

    polygon_errors = []
    for side, parts in contract["handSegmentation"]["candidatePolygonsSourceMaster"].items():
        for part, points in parts.items():
            if len(points) < 3:
                polygon_errors.append(f"{side}/{part}: fewer than 3 points")
            for x, y in points:
                if not (0 <= x < 512 and 0 <= y < 1086):
                    polygon_errors.append(f"{side}/{part}: ({x},{y}) out of bounds")
    check(not polygon_errors, "hand_polygons_in_bounds", f"errors={polygon_errors}", results)

    centerline_errors = []
    for side, parts in contract["handSegmentation"].get("candidateCenterlinesSourceMaster", {}).items():
        for part, points in parts.items():
            if len(points) < 2:
                centerline_errors.append(f"{side}/{part}: fewer than 2 points")
            for x, y in points:
                if not (0 <= x < 512 and 0 <= y < 1086):
                    centerline_errors.append(f"{side}/{part}: ({x},{y}) out of bounds")
    check(not centerline_errors, "hand_centerlines_in_bounds", f"errors={centerline_errors}", results)

    if "v3Policy" in contract["handSegmentation"]:
        simple_metrics_ok = hand_simple.get("policy") == "complete hand per side"
        for side in ("R", "L"):
            metrics = hand_simple.get("metrics", {}).get(side, {})
            simple_metrics_ok = simple_metrics_ok and metrics.get("coverageRatio") == 1.0 and metrics.get("uncoveredPixels") == 0 and metrics.get("overlapPixels") == 0
        check(simple_metrics_ok, "complete_hand_layer_coverage", f"status={hand_simple.get('status')}", results)
        check("hand_R" in ids and "hand_L" in ids and not any("finger" in layer_id or any(token in layer_id for token in ("thumb", "index", "middle", "ring", "little")) for layer_id in ids), "no_individual_finger_production_layers", "complete-hand v3 policy is authoritative", results)
    else:
        bad_hand_metrics = []
        for side in ("R", "L"):
            metrics = alignment["metrics"][side]
            if metrics["coverageRatio"] != 1.0 or metrics["uncoveredPixels"] != 0 or metrics["overlapPixels"] != 0:
                bad_hand_metrics.append({side: metrics})
        check(not bad_hand_metrics, "hand_partition_exact_coverage", f"failures={bad_hand_metrics}", results)
        tiny_digits = []
        for side in ("R", "L"):
            for digit in ("thumb", "index", "middle", "ring", "little"):
                pixels = alignment["metrics"][side]["partPixels"][digit]
                if pixels < 30:
                    tiny_digits.append(f"{side}/{digit}={pixels}px")
        check(not tiny_digits, "hand_digit_nontrivial_area", f"tiny={tiny_digits}", results)
        draft_ok = hand_draft.get("status") == "pass" and all(side.get("passed") for side in hand_draft.get("sides", {}).values())
        check(draft_ok, "hand_draft_export_roundtrip", f"status={hand_draft.get('status')}", results)

    color_master = Image.open(ROOT / "source" / "masters" / "gate3-color-target-v1.png").convert("RGB")
    line_master = Image.open(ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png").convert("RGB")
    check(color_master.size == (512, 1086) and line_master.size == (512, 1086), "master_dimensions", f"color={color_master.size} line={line_master.size}", results)
    source_color = Image.open(ROOT / "source" / "xiaoxing-three-view-color.png").convert("RGB").crop((34, 0, 546, 1086))
    source_line = Image.open(ROOT / "source" / "xiaoxing-three-view-line.png").convert("RGB").crop((34, 0, 546, 1086))
    exact_crops = ImageChops.difference(color_master, source_color).getbbox() is None and ImageChops.difference(line_master, source_line).getbbox() is None
    check(exact_crops, "masters_are_exact_source_crops", "both masters equal their declared source crop", results)

    registry_path = WORKSPACE / "public" / "pets" / "index.json"
    registry_text = registry_path.read_text(encoding="utf-8") if registry_path.exists() else ""
    check("xiaoxing" not in registry_text, "not_registered_as_formal_pet", "xiaoxing absent from public/pets/index.json", results)

    passed = all(item["passed"] for item in results)
    report = {
        "status": "pass_pending_user_visual_gate" if passed else "fail",
        "checksPassed": sum(item["passed"] for item in results),
        "checksTotal": len(results),
        "results": results,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
