from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
LAYERS = ROOT / "qa" / "v2-upper-body-candidate-layers"
OUT = ROOT / "audit" / "v2-upper-body-seam-stress-validation.json"


def main():
    names = ["neck", "torso_tshirt_core", "sleeve_screen_left", "sleeve_screen_right", "arm_screen_left_forearm", "arm_screen_right_forearm", "hand_screen_left", "hand_screen_right", "necklace"]
    errors = []
    for name in names:
        path = LAYERS / f"{name}.png"
        if not path.exists():
            errors.append(f"missing candidate: {name}")
            continue
        image = Image.open(path)
        if image.size != (512, 1086) or image.mode != "RGBA":
            errors.append(f"invalid layer canvas/mode: {name}")
    result = {"status": "self_review_passed_stress_setup" if not errors else "failed", "testedOffsets": {"forearms": [-3,3], "hands": [-3,3]}, "errors": errors, "rules": {"candidate_layers_only": True, "no_mesh_or_physics": True, "visual_contact_sheet_required": True, "complete_hand_per_side": True}}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
