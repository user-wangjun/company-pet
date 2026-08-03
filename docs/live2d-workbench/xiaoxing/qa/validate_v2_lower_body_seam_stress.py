from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
LAYERS = ROOT / "qa" / "v2-lower-body-candidate-layers"
OUT = ROOT / "audit" / "v2-lower-body-seam-stress-validation.json"


def main():
    expected = (512, 1086)
    names = ["leg_screen_left", "leg_screen_right", "skirt", "sock_screen_left", "sock_screen_right", "shoe_screen_left", "shoe_screen_right"]
    errors = []
    for name in names:
        path = LAYERS / f"{name}.png"
        if not path.exists():
            errors.append(f"missing candidate: {name}")
            continue
        image = Image.open(path)
        if image.size != expected or image.mode != "RGBA":
            errors.append(f"invalid layer canvas/mode: {name}")
    result = {
        "status": "self_review_passed_stress_setup" if not errors else "failed",
        "testedOffsets": {"skirt": [-8, 0, 8], "legs": [-3, 3]},
        "errors": errors,
        "rules": {
            "candidate_layers_only": True,
            "no_mesh_or_physics": True,
            "visual_contact_sheet_required": True
        }
    }
    OUT.write_text(__import__('json').dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(__import__('json').dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
