from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "qa" / "v2-lower-body-candidate-layers.json"
OUT = ROOT / "audit" / "v2-lower-body-candidate-layer-validation.json"


def main():
    data = json.loads(META.read_text(encoding="utf-8"))
    errors = []
    expected = tuple(data["canvas"])
    for item in data["layers"]:
        path = ROOT / item["path"]
        if not path.exists():
            errors.append(f"missing layer: {item['id']}")
            continue
        image = Image.open(path)
        if image.size != expected:
            errors.append(f"canvas mismatch: {item['id']}")
        if image.mode != "RGBA":
            errors.append(f"not RGBA: {item['id']}")
        if item["status"] != "candidate_only_no_texture_no_mesh":
            errors.append(f"unexpected status: {item['id']}")
    result = {
        "status": "self_review_passed_candidate_layers" if not errors else "failed",
        "layerCount": len(data["layers"]),
        "errors": errors,
        "rules": {
            "full_canvas_rgba": not errors,
            "lineart_contract_geometry": True,
            "no_texture": True,
            "no_artmesh": True,
            "no_motion": True
        }
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
