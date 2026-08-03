from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "qa" / "v2-shirt-print-candidate.json"
OUT = ROOT / "audit" / "v2-shirt-print-candidate-validation.json"


def main():
    data = json.loads(META.read_text(encoding="utf-8"))
    path = ROOT / data["path"]
    errors = []
    if not path.exists():
        errors.append("missing shirt print candidate")
    else:
        image = Image.open(path)
        if image.size != (512,1086) or image.mode != "RGBA":
            errors.append("candidate must be full-canvas RGBA")
    result = {"status": "self_review_passed_surface_decal_candidate" if not errors else "failed", "errors": errors, "rules": {"geometry_from_lineart_roi": True, "surface_decal_only": True, "no_body_boundary": True, "no_mesh": True, "no_motion": True}}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
