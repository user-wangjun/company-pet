from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
OUT = ROOT / "audit" / "v2-eye-line-components.json"


def components(image: Image.Image, box: tuple[int, int, int, int]):
    gray = image.convert("L").crop(box)
    w, h = gray.size
    pix = gray.load()
    points = {(x, y) for y in range(h) for x in range(w) if pix[x, y] < 125}
    out = []
    while points:
        seed = points.pop()
        q = deque([seed])
        group = [seed]
        while q:
            x, y = q.popleft()
            for nx in range(x - 1, x + 2):
                for ny in range(y - 1, y + 2):
                    if (nx, ny) in points:
                        points.remove((nx, ny))
                        q.append((nx, ny))
                        group.append((nx, ny))
        if len(group) < 5:
            continue
        xs = [p[0] for p in group]
        ys = [p[1] for p in group]
        out.append({"pixels": len(group), "bbox": [box[0] + min(xs), box[1] + min(ys), box[0] + max(xs) + 1, box[1] + max(ys) + 1]})
    return sorted(out, key=lambda x: x["pixels"], reverse=True)


def main():
    image = Image.open(LINE)
    rois = {"R": [202, 124, 256, 164], "L": [263, 124, 316, 164]}
    report = {"source": "source/masters/gate3-line-master-candidate-v1.png", "threshold": 125, "rois": {side: {"box": box, "components": components(image, tuple(box))} for side, box in rois.items()}}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
