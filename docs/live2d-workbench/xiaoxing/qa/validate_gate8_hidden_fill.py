from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "qa" / "hidden-fill-candidates.json"
OUT = ROOT / "audit" / "gate8-hidden-fill-validation.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors: list[str] = []
    for entry in manifest.get("entries", []):
        if entry.get("status") != "candidate_only":
            errors.append(f"not candidate_only: {entry.get('id')}")
        path = ROOT / entry["path"]
        if not path.exists():
            errors.append(f"missing: {entry['path']}")
            continue
        im = Image.open(path)
        if im.size != (512, 1086) or im.mode != "RGBA":
            errors.append(f"{entry['id']}: {im.size}/{im.mode}")
        if not str(path).replace("\\", "/").startswith(str(ROOT / "qa").replace("\\", "/")):
            errors.append(f"outside qa: {entry['path']}")
    report = {"status": "self_review_passed_candidate_only" if not errors and manifest.get("rules", {}).get("notFormalExport") else "fail", "entryCount": len(manifest.get("entries", [])), "errors": errors, "rules": {"all_candidates_full_canvas_rgba": not errors, "candidate_only": manifest.get("rules", {}).get("candidateOnly") is True, "not_formal_export": manifest.get("rules", {}).get("notFormalExport") is True}}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"].startswith("self_review") else 1


if __name__ == "__main__":
    raise SystemExit(main())
