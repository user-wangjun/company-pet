from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "blueprints" / "gate3-production-blueprint-contract.json"
OUT = ROOT / "model" / "material-export-manifest.json"


def main():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    layers = sorted(contract["layers"], key=lambda item: item["drawOrder"])
    manifest = {
        "character": contract["character"],
        "stage": "gate3-material-export-plan",
        "status": "plan_only_pending_user_visual_gate",
        "sourceMaster": {
            "path": contract["masters"]["colorTarget"],
            "lineReference": contract["masters"]["lineMasterCandidate"],
            "canvas": [512, 1086],
            "exportScale": 2,
            "exportCanvas": [1024, 2172],
            "coordinateTransform": "source-master coordinates; no translation or crop during layer export",
        },
        "rules": {
            "format": "RGBA PNG",
            "oneFullCanvasFilePerLayer": True,
            "transparentUnusedPixels": True,
            "preserveSourceColors": True,
            "hiddenFillRequired": True,
            "doNotFlatten": True,
            "noFormalPetRegistration": True,
        },
        "layers": [
            {
                "order": index + 1,
                "id": layer["id"],
                "drawOrder": layer["drawOrder"],
                "parent": layer["parent"],
                "pivot": layer["pivot"],
                "source": layer["source"],
                "hiddenFill": layer["hiddenFill"],
                "visibleOwnership": layer["visibleOwnership"],
                "maskPath": f"model/materials/draft/{layer['id']}.png",
                "maskStatus": "not_exported_until_gate3_visual_approval",
            }
            for index, layer in enumerate(layers)
        ],
        "qaRequiredBeforeCubism": [
            "full-canvas dimensions and alpha check",
            "no uncovered visible boundary pixels",
            "no accidental neighboring-material pixels",
            "hidden-fill continuity under every occluder",
            "draw-order contact sheet",
            "head/eyes/hands visual inspection",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "layerCount": len(manifest["layers"]), "output": str(OUT)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
