from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
PET = ROOT.parent
X6 = Path(__file__).resolve().parent
CONTRACT = X6 / "x6-joint-safe-motion-bundle-contract-v4.json"
OUTPUT = X6 / "x6-joint-safe-motion-bundle-audit-v4.json"
CANVAS = (1774, 887)


def load_full(path: str, bounds: list[int]) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.alpha_composite(Image.open(PET / path).convert("RGBA"), (bounds[0], bounds[1]))
    return canvas


def offset_alpha(alpha: Image.Image, delta: tuple[int, int]) -> Image.Image:
    moved = Image.new("L", CANVAS, 0)
    moved.paste(alpha, delta)
    return moved


def pixels(alpha: Image.Image) -> int:
    return sum(value > 8 for value in alpha.tobytes())


def center(alpha: Image.Image) -> tuple[float, float]:
    bounds = alpha.getbbox()
    if not bounds:
        return 0.0, 0.0
    return (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2


def outward_delta(parent: Image.Image, child: Image.Image, distance: int = 10) -> tuple[int, int]:
    px, py = center(parent)
    cx, cy = center(child)
    dx, dy = cx - px, cy - py
    length = math.hypot(dx, dy) or 1.0
    return round(distance * dx / length), round(distance * dy / length)


def main() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    records = {(row["view"], row["bundle"]): row for row in contract["exports"]}
    rows = []
    for key, child_record in records.items():
        view, child_id = key
        parent_id = child_record["effectiveParentBundleInView"]
        if not parent_id:
            continue
        cover_ids = child_record.get("occlusionCoverBundles") or [parent_id]
        parent = Image.new("L", CANVAS, 0)
        for cover_id in cover_ids:
            parent_record = records[(view, cover_id)]
            cover = load_full(parent_record["visibleFile"], parent_record["visibleBounds"]).getchannel("A")
            parent = ImageChops.lighter(parent, cover)
        child = load_full(child_record["visibleFile"], child_record["visibleBounds"]).getchannel("A")
        collar = load_full(child_record["hiddenCollarFile"], child_record["hiddenCollarBounds"]).getchannel("A")
        delta = outward_delta(parent, child)
        moved_child = offset_alpha(child, delta)
        moved_collar = offset_alpha(collar, delta)
        parent_contact = pixels(ImageChops.multiply(parent, moved_collar))
        child_boundary = moved_child.filter(ImageFilter.MaxFilter(5))
        child_contact = pixels(ImageChops.multiply(child_boundary, moved_collar))
        passes = parent_contact >= 16 and child_contact >= 8
        rows.append(
            {
                "view": view,
                "childBundle": child_id,
                "declaredParentBundle": child_record["parentBundle"],
                "effectiveParentBundleInView": parent_id,
                "occlusionCoverBundles": cover_ids,
                "occludedParentFallback": child_record["occludedParentFallback"],
                "outwardShiftPixels": list(delta),
                "parentContactAfterShiftPixels": parent_contact,
                "childBoundaryContactAfterShiftPixels": child_contact,
                "passes": passes,
            }
        )
    result = {
        "schemaVersion": 1,
        "stage": "X6-joint-safe-motion-bundle-10px-pull-audit",
        "status": "pass-candidate" if all(row["passes"] for row in rows) else "fail-candidate",
        "stressDistancePixels": 10,
        "jointRecordCount": len(rows),
        "passCount": sum(row["passes"] for row in rows),
        "allJointsRemainConnected": all(row["passes"] for row in rows),
        "minimumParentContactAfterShiftPixels": min(row["parentContactAfterShiftPixels"] for row in rows),
        "minimumChildBoundaryContactAfterShiftPixels": min(row["childBoundaryContactAfterShiftPixels"] for row in rows),
        "records": rows,
        "gateBoundary": {"gate6Approved": False, "x7Authorized": False},
        "limit": "This tests layer overlap under a 10 px outward pull. It does not authorize or replace X7 elasticity, Cubism deformation, or rotation QA.",
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "joints": result["jointRecordCount"],
        "passes": result["passCount"],
        "minParentContact": result["minimumParentContactAfterShiftPixels"],
        "minChildContact": result["minimumChildBoundaryContactAfterShiftPixels"],
    }, ensure_ascii=False))
    if not result["allJointsRemainConnected"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
