from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "qa" / "v2-eye-color-candidates.json"
CONTRACT = ROOT / "blueprints" / "v2-eye-lineart-boundary-contract.json"
OUT = ROOT / "audit" / "v2-eye-color-candidate-validation.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    errors: list[str] = []
    for entry in manifest["entries"]:
        path = ROOT / entry["path"]
        if not path.exists():
            errors.append(f"missing: {entry['path']}")
            continue
        im = Image.open(path)
        if im.size != (512,1086) or im.mode != "RGBA":
            errors.append(f"{entry['id']}: {im.size}/{im.mode}")
        bbox = im.getchannel("A").getbbox()
        if bbox:
            z = contract["zones"][entry["side"]]["reviewBox"]
            if bbox[0] < z[0] or bbox[1] < z[1] or bbox[2] > z[2] + 1 or bbox[3] > z[3] + 1:
                errors.append(f"{entry['id']}: alpha bbox {bbox} outside reviewBox {z}")
    report = {"status":"self_review_passed_color_candidate_only" if not errors else "fail", "layerCount":len(manifest["entries"]), "errors":errors, "rules":{"full_canvas_rgba":not errors, "geometry_from_lineart_contract":manifest["geometrySource"].endswith("v2-eye-lineart-boundary-contract.json"), "color_only_from_color_master":"color sampling only" in manifest["paletteSource"], "no_motion":manifest["status"].endswith("no_motion")}}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"].startswith("self_review") else 1


if __name__ == "__main__":
    raise SystemExit(main())
