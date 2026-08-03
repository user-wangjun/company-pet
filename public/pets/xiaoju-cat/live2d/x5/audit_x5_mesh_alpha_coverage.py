from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parent
LAYER_CONTRACT = ROOT / "x5-generated-fine-layer-candidates-contract-v1.json"
MESH_CONTRACT = ROOT / "x5-generated-fine-mesh-contract-v1.json"
OUTPUT = ROOT / "x5-mesh-alpha-coverage-audit-v1.json"


def main() -> None:
    layers = json.loads(LAYER_CONTRACT.read_text(encoding="utf-8"))["layers"]
    mesh_summaries = json.loads(MESH_CONTRACT.read_text(encoding="utf-8"))["layers"]
    mesh_path_by_id = {item["layerId"]: ROOT.parent.parent / item["meshFile"] for item in mesh_summaries}
    results = []
    for layer in layers:
        image = Image.open(ROOT.parent.parent / layer["file"]).convert("RGBA")
        alpha = np.asarray(image.getchannel("A")) > 24
        mesh = json.loads(mesh_path_by_id[layer["id"]].read_text(encoding="utf-8"))
        coverage_image = Image.new("1", image.size, 0)
        draw = ImageDraw.Draw(coverage_image)
        points = mesh["points"]
        for triangle in mesh["triangles"]:
            draw.polygon([tuple(points[index]) for index in triangle], fill=1)
        strict_mesh_mask = np.asarray(coverage_image, dtype=bool)
        tolerant_mesh_mask = np.asarray(coverage_image.filter(ImageFilter.MaxFilter(3)), dtype=bool)
        tolerant_alpha = np.asarray(Image.fromarray((alpha.astype(np.uint8) * 255)).filter(ImageFilter.MaxFilter(3)), dtype=np.uint8) > 0
        covered = strict_mesh_mask & alpha
        tolerant_covered = tolerant_mesh_mask & alpha
        alpha_count = int(alpha.sum())
        mesh_count = int(strict_mesh_mask.sum())
        strict_coverage = float(covered.sum() / alpha_count) if alpha_count else 1.0
        tolerant_coverage = float(tolerant_covered.sum() / alpha_count) if alpha_count else 1.0
        strict_precision = float(covered.sum() / mesh_count) if mesh_count else 1.0
        tolerant_precision = float((strict_mesh_mask & tolerant_alpha).sum() / mesh_count) if mesh_count else 1.0
        results.append({
            "layerId": layer["id"],
            "view": layer["view"],
            "alphaPixelCount": alpha_count,
            "coveredAlphaPixelCount": int(covered.sum()),
            "strictCoverage": round(strict_coverage, 6),
            "onePixelBoundaryTolerantCoveredAlphaPixelCount": int(tolerant_covered.sum()),
            "onePixelBoundaryTolerantCoverage": round(tolerant_coverage, 6),
            "meshPixelCount": mesh_count,
            "outsideStrictAlphaPixelCount": int((strict_mesh_mask & ~alpha).sum()),
            "strictAlphaPrecision": round(strict_precision, 6),
            "outsideOnePixelAlphaTolerancePixelCount": int((strict_mesh_mask & ~tolerant_alpha).sum()),
            "onePixelBoundaryTolerantAlphaPrecision": round(tolerant_precision, 6),
            "passesNinetyFivePercentCoverage": tolerant_coverage >= 0.95,
            "passesNinetyFivePercentPrecision": tolerant_precision >= 0.95,
            "passesNinetyFivePercent": tolerant_coverage >= 0.95 and tolerant_precision >= 0.95,
        })
    audit = {
        "schemaVersion": 1,
        "stage": "X5-mesh-alpha-coverage-audit",
        "status": "candidate-for-user-review",
        "threshold": 0.95,
        "boundaryTolerancePixels": 1,
        "counts": {
            "layers": len(results),
            "passing": sum(item["passesNinetyFivePercent"] for item in results),
            "failing": sum(not item["passesNinetyFivePercent"] for item in results),
        },
        "minimumStrictCoverage": min(item["strictCoverage"] for item in results),
        "meanStrictCoverage": round(sum(item["strictCoverage"] for item in results) / len(results), 6),
        "minimumOnePixelBoundaryTolerantCoverage": min(item["onePixelBoundaryTolerantCoverage"] for item in results),
        "meanOnePixelBoundaryTolerantCoverage": round(sum(item["onePixelBoundaryTolerantCoverage"] for item in results) / len(results), 6),
        "minimumOnePixelBoundaryTolerantAlphaPrecision": min(item["onePixelBoundaryTolerantAlphaPrecision"] for item in results),
        "meanOnePixelBoundaryTolerantAlphaPrecision": round(sum(item["onePixelBoundaryTolerantAlphaPrecision"] for item in results) / len(results), 6),
        "layers": sorted(results, key=lambda item: min(item["onePixelBoundaryTolerantCoverage"], item["onePixelBoundaryTolerantAlphaPrecision"])),
        "gateBoundary": {"currentGate": "x5-layer-mesh-node-torque", "gate5Approved": False, "x6Authorized": False},
    }
    OUTPUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"counts": audit["counts"], "minimumStrictCoverage": audit["minimumStrictCoverage"], "meanStrictCoverage": audit["meanStrictCoverage"], "minimumOnePixelBoundaryTolerantCoverage": audit["minimumOnePixelBoundaryTolerantCoverage"], "meanOnePixelBoundaryTolerantCoverage": audit["meanOnePixelBoundaryTolerantCoverage"], "minimumOnePixelBoundaryTolerantAlphaPrecision": audit["minimumOnePixelBoundaryTolerantAlphaPrecision"], "meanOnePixelBoundaryTolerantAlphaPrecision": audit["meanOnePixelBoundaryTolerantAlphaPrecision"], "worst": audit["layers"][:10]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
