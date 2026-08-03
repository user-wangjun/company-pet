from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "blueprints" / "v2-body-seam-contract.json"
SOURCE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
OUT = ROOT / "audit" / "v2-body-seam-validation.json"


def main():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = Image.open(SOURCE)
    errors = []
    if list(source.size) != data.get("canvas"):
        errors.append("source canvas does not match contract")
    ids = set()
    for seam in data.get("seams", []):
        if seam["id"] in ids:
            errors.append(f"duplicate seam id: {seam['id']}")
        ids.add(seam["id"])
        x0, y0, x1, y1 = seam["crop"]
        if not (0 <= x0 < x1 <= source.width and 0 <= y0 < y1 <= source.height):
            errors.append(f"crop outside canvas: {seam['id']}")
        polylines = seam.get("polylines") or [seam.get("polyline", [])]
        for polyline in polylines:
            if len(polyline) < 2:
                errors.append(f"too few seam points: {seam['id']}")
            for x, y in polyline:
                if not (x0 <= x < x1 and y0 <= y < y1):
                    errors.append(f"point outside review crop: {seam['id']} ({x},{y})")
    result = {
        "status": "self_review_passed_landmarks_only" if not errors else "failed",
        "seamCount": len(data.get("seams", [])),
        "errors": errors,
        "rules": {
            "single_native_canvas": True,
            "review_landmarks_not_masks": True,
            "no_nonuniform_resize": True,
            "no_rgba_export": True,
            "hand_policy_coarse": True
        }
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
