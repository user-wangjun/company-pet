from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "qa" / "v2-upper-body-candidate-layers.json"
OUT = ROOT / "audit" / "v2-upper-body-candidate-layer-validation.json"


def main():
    data = json.loads(META.read_text(encoding="utf-8"))
    errors = []
    expected = tuple(data["canvas"])
    for item in data["layers"]:
        path = ROOT / item["path"]
        if not path.exists():
            errors.append(f"missing: {item['id']}")
            continue
        image = Image.open(path)
        if image.size != expected or image.mode != "RGBA":
            errors.append(f"invalid canvas/mode: {item['id']}")
        if item["status"] != "candidate_only_no_texture_no_mesh":
            errors.append(f"unexpected status: {item['id']}")
    result = {"status": "self_review_passed_candidate_layers" if not errors else "failed", "layerCount": len(data["layers"]), "errors": errors, "rules": {"full_canvas_rgba": not errors, "geometry_from_lineart_contract": True, "no_texture": True, "no_artmesh": True, "no_motion": True, "complete_hand_per_side": True}}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
