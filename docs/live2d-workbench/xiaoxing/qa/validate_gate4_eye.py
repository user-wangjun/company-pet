from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MOTION = ROOT / "audit" / "gate4-eye-motion-validation.json"
LAYERS = ROOT / "qa" / "draft-eye-layers.json"
OUT = ROOT / "audit" / "gate4-eye-contract-validation.json"


def main() -> int:
    results: list[dict] = []
    motion = json.loads(MOTION.read_text(encoding="utf-8")) if MOTION.exists() else {}
    layers = json.loads(LAYERS.read_text(encoding="utf-8")) if LAYERS.exists() else {}

    results.append({"name": "motion_preflight_pass", "passed": motion.get("status") == "pass", "details": motion.get("status", "missing")})
    states = motion.get("states", {})
    monotonic = True
    for side in ("R", "L"):
        open_px = states.get(f"{side}_1", {}).get("openingMaskHistogramSum", -1)
        half_px = states.get(f"{side}_3", {}).get("openingMaskHistogramSum", -1)
        closed_px = states.get(f"{side}_4", {}).get("openingMaskHistogramSum", -1)
        monotonic = monotonic and open_px > half_px > closed_px == 0
    results.append({"name": "blink_open_half_closed", "passed": monotonic, "details": "open > half > closed(0) for both eyes"})

    required = ("eye_mask", "socket", "sclera", "iris", "pupil", "highlight", "upper_lid", "lower_lid")
    layer_errors: list[str] = []
    for side in ("R", "L"):
        eye = layers.get("eyes", {}).get(side, {})
        for name in required:
            rel = eye.get(name)
            if not rel:
                layer_errors.append(f"{side}/{name}: missing manifest path")
                continue
            path = ROOT / rel
            if not path.exists():
                layer_errors.append(f"{side}/{name}: missing file")
                continue
            image = Image.open(path)
            if image.size != (512, 1086) or image.mode != "RGBA":
                layer_errors.append(f"{side}/{name}: {image.size}/{image.mode}")
    results.append({"name": "material_layers_full_canvas_rgba", "passed": not layer_errors, "details": f"errors={layer_errors}"})

    passed = all(item["passed"] for item in results)
    report = {"status": "pass_pending_visual_gate" if passed else "fail", "checksPassed": sum(x["passed"] for x in results), "checksTotal": len(results), "results": results}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
