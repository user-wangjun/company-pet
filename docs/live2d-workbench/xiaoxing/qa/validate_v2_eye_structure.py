from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "qa" / "v2-eye-structure-drafts.json"
CONTRACT = ROOT / "blueprints" / "v2-eye-lineart-boundary-contract.json"
OUT = ROOT / "audit" / "v2-eye-structure-validation.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    errors: list[str] = []
    for entry in manifest["entries"]:
        path = ROOT / entry["path"]
        if not path.exists():
            errors.append(f"missing: {entry['path']}")
            continue
        image = Image.open(path)
        if image.size != (512, 1086) or image.mode != "RGBA":
            errors.append(f"{entry['id']}: {image.size}/{image.mode}")
    for side, zone in contract["zones"].items():
        x0, y0, x1, y1 = zone["reviewBox"]
        for point_name in ("outerCorner", "innerCorner", "upperApex", "lowerApex", "irisCenterCandidate"):
            x, y = zone[point_name]
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                errors.append(f"{side}/{point_name} outside reviewBox")
    report = {"status": "self_review_passed_structure_only" if not errors else "fail", "layerCount": len(manifest["entries"]), "errors": errors, "rules": {"full_canvas_rgba": not errors, "lineart_only": manifest["status"] == "lineart_structure_draft_only", "no_final_texture": bool(manifest["missingByDesign"]), "no_motion_keys": "blink_keyforms" in manifest["missingByDesign"]}}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"].startswith("self_review") else 1


if __name__ == "__main__":
    raise SystemExit(main())
