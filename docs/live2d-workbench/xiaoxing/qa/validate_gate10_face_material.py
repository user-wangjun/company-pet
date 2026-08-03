from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "qa" / "draft-face-layers.json"
CONTRACT = ROOT / "blueprints" / "gate3-production-blueprint-contract.json"
OUT = ROOT / "audit" / "gate10-face-material-validation.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    ids = {x["id"] for x in contract["layers"]}
    errors: list[str] = []
    for entry in manifest.get("layers", []):
        if entry["id"] not in ids:
            errors.append(f"not in contract: {entry['id']}")
        path = ROOT / entry["path"]
        if not path.exists():
            errors.append(f"missing: {entry['path']}")
            continue
        image = Image.open(path)
        if image.size != (512, 1086) or image.mode != "RGBA":
            errors.append(f"{entry['id']}: {image.size}/{image.mode}")
    reused_ok = all((ROOT / path).exists() for path in manifest.get("reused", []))
    mouth_declared = set(manifest.get("missingByDesign", [])) == {"mouth_inner", "tongue"}
    report = {"status": "self_review_passed_face_draft" if not errors and reused_ok and mouth_declared else "fail", "draftLayerCount": len(manifest.get("layers", [])), "errors": errors, "rules": {"all_face_drafts_full_canvas_rgba": not errors, "eye_composites_reused": reused_ok, "closed_mouth_not_faked": mouth_declared}}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"].startswith("self_review") else 1


if __name__ == "__main__":
    raise SystemExit(main())
