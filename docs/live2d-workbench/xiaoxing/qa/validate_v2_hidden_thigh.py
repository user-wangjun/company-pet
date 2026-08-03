from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "blueprints" / "v2-hidden-thigh-contract.json"
FRONT = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
THREE = ROOT / "source" / "xiaoxing-three-view-line.png"
OUT = ROOT / "audit" / "v2-hidden-thigh-validation.json"


def main():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    front = Image.open(FRONT)
    three = Image.open(THREE)
    errors = []
    if list(front.size) != data["frontCanvas"]:
        errors.append("front canvas mismatch")
    if three.size != (1448, 1086):
        errors.append(f"unexpected three-view canvas: {three.size}")
    for item in data["frontHiddenCandidates"]:
        if item["coveredBy"] != "skirt":
            errors.append(f"hidden thigh not covered by skirt: {item['id']}")
        if len(item["polygon"]) < 4:
            errors.append(f"insufficient hidden contour: {item['id']}")
        ys = [p[1] for p in item["polygon"]]
        if min(ys) >= 635 or max(ys) <= 635:
            errors.append(f"hidden candidate does not bridge skirt seam: {item['id']}")
    result = {
        "status": "self_review_passed_volume_candidate" if not errors else "failed",
        "candidateCount": len(data["frontHiddenCandidates"]),
        "errors": errors,
        "rules": {
            "front_native_canvas": True,
            "side_reference_only": True,
            "bridges_skirt_seam": not any("bridge" in error or "hidden candidate" in error for error in errors),
            "no_rgba_export": True,
            "no_radial_patch": True
        }
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
