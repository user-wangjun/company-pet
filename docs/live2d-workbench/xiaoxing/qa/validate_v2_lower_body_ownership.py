from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "blueprints" / "v2-lower-body-ownership-contract.json"
SOURCE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
OUT = ROOT / "audit" / "v2-lower-body-ownership-validation.json"


def main():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = Image.open(SOURCE)
    errors = []
    if list(source.size) != data["canvas"]:
        errors.append("source canvas mismatch")
    seen = set()
    for group in data["groups"]:
        if group["id"] in seen:
            errors.append(f"duplicate id: {group['id']}")
        seen.add(group["id"])
        points = group["polygon"]
        if len(points) < 3:
            errors.append(f"polygon too short: {group['id']}")
        for x, y in points:
            if not (0 <= x < source.width and 0 <= y < source.height):
                errors.append(f"point outside canvas: {group['id']} ({x},{y})")
    result = {
        "status": "self_review_passed_coarse_candidate" if not errors else "failed",
        "groupCount": len(data["groups"]),
        "errors": errors,
        "rules": {
            "native_canvas": True,
            "review_only": True,
            "no_formal_rgba": True,
            "hidden_thigh_candidates_present": (ROOT / "blueprints" / "v2-hidden-thigh-contract.json").exists(),
            "hidden_thighs_not_final": True
        }
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
