from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "qa" / "draft-material-layers.json"
CONTRACT = ROOT / "blueprints" / "gate3-production-blueprint-contract.json"
OUT = ROOT / "audit" / "gate7-material-draft-validation.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    ids = {layer["id"] for layer in contract["layers"]}
    errors: list[str] = []
    for entry in manifest.get("layers", []):
        if entry["id"] not in ids:
            errors.append(f"not in gate3 contract: {entry['id']}")
        path = ROOT / entry["path"]
        if not path.exists():
            errors.append(f"missing file: {entry['path']}")
            continue
        image = Image.open(path)
        if image.size != (512, 1086) or image.mode != "RGBA":
            errors.append(f"{entry['id']}: {image.size}/{image.mode}")
    hand_ok = contract["handSegmentation"].get("individualFingerMotion") is False and "hand_R" in ids and "hand_L" in ids
    report = {
        "status": "self_review_passed_visible_only" if not errors and hand_ok else "fail",
        "layerCount": len(manifest.get("layers", [])),
        "errors": errors,
        "rules": {"all_draft_layers_full_canvas_rgba": not errors, "hand_is_coarse": hand_ok, "hidden_fill_still_required": manifest.get("rules", {}).get("hiddenFillStillRequired") is True},
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"].startswith("self_review") else 1


if __name__ == "__main__":
    raise SystemExit(main())
