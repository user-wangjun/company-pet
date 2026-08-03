from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "blueprints" / "v2-head-ownership-contract.json"
SOURCE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
OUT = ROOT / "audit" / "v2-head-ownership-validation.json"


def main():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = Image.open(SOURCE)
    errors=[]; ids=set()
    if list(source.size) != data["canvas"]: errors.append("source canvas mismatch")
    for group in data["groups"]:
        if group["id"] in ids: errors.append(f"duplicate id: {group['id']}")
        ids.add(group["id"])
        if len(group["polygon"]) < 3: errors.append(f"polygon too short: {group['id']}")
        for x,y in group["polygon"]:
            if not (0 <= x < source.width and 0 <= y < source.height): errors.append(f"point outside canvas: {group['id']}")
    result={"status":"visual_review_pending_not_promoted" if not errors else "failed","groupCount":len(data["groups"]),"errors":errors,"rules":{"native_canvas":True,"review_only":True,"eyes_independent":True,"ears_pending":True,"no_formal_rgba":True,"head_visual_gate_required":True}}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
