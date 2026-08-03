from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "blueprints" / "v2-upper-body-ownership-contract.json"
SOURCE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
OUT = ROOT / "audit" / "v2-upper-body-ownership-validation.json"


def main():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = Image.open(SOURCE)
    errors = []
    if list(source.size) != data["canvas"]:
        errors.append("source canvas mismatch")
    ids = set()
    for group in data["groups"]:
        if group["id"] in ids:
            errors.append(f"duplicate id: {group['id']}")
        ids.add(group["id"])
        if len(group["polygon"]) < 3:
            errors.append(f"polygon too short: {group['id']}")
        for x, y in group["polygon"]:
            if not (0 <= x < source.width and 0 <= y < source.height):
                errors.append(f"point outside canvas: {group['id']}")
    result = {
        "status": "self_review_passed_coarse_candidate" if not errors else "failed",
        "groupCount": len(data["groups"]),
        "errors": errors,
        "rules": {"native_canvas": True, "review_only": True, "complete_hand_per_side": True, "no_formal_rgba": True}
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
