from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
COLOR = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
OUT = ROOT / "qa" / "v2-shirt-print-candidate-contact-sheet.png"
OUT_LAYER = ROOT / "qa" / "v2-shirt-print-candidate-layer.png"
OUT_META = ROOT / "qa" / "v2-shirt-print-candidate.json"


ROI = (181, 292, 321, 552)


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def components(binary, w, h):
    seen = set()
    groups = []
    for y in range(h):
        for x in range(w):
            if not binary[y][x] or (x, y) in seen:
                continue
            q = deque([(x, y)])
            seen.add((x, y))
            group = []
            while q:
                px, py = q.popleft()
                group.append((px, py))
                for nx, ny in ((px+1,py),(px-1,py),(px,py+1),(px,py-1)):
                    if 0 <= nx < w and 0 <= ny < h and binary[ny][nx] and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        q.append((nx, ny))
            groups.append(group)
    return groups


def main():
    line = Image.open(LINE).convert("L")
    color = Image.open(COLOR).convert("RGB")
    x0, y0, x1, y1 = ROI
    crop = line.crop(ROI)
    w, h = crop.size
    px = crop.load()
    binary = [[px[x, y] < 150 and not (y < 100 and (x < 28 or x > 122)) for x in range(w)] for y in range(h)]
    keep = Image.new("L", (w, h), 0)
    keep_px = keep.load()
    groups = components(binary, w, h)
    kept_count = 0
    for group in groups:
        minx = min(p[0] for p in group)
        maxx = max(p[0] for p in group)
        miny = min(p[1] for p in group)
        maxy = max(p[1] for p in group)
        touches_frame = minx <= 1 or miny <= 1 or maxx >= w-2 or maxy >= h-2
        if touches_frame or len(group) < 3:
            continue
        kept_count += 1
        for gx, gy in group:
            keep_px[gx, gy] = 210

    layer = Image.new("RGBA", (512, 1086), (0, 0, 0, 0))
    layer.paste((40, 38, 42, 230), (x0, y0, x1, y1), keep)
    layer.save(OUT_LAYER)

    board = Image.new("RGB", (1080, 520), "white")
    line_crop = line.crop((165, 270, 335, 570)).convert("RGB").resize((300, 500), Image.Resampling.NEAREST)
    color_crop = color.crop((165, 270, 335, 570)).resize((300, 500), Image.Resampling.NEAREST)
    candidate_crop = layer.crop((165, 270, 335, 570))
    candidate_bg = Image.new("RGBA", candidate_crop.size, "white")
    candidate_bg.alpha_composite(candidate_crop)
    candidate_crop = candidate_bg.convert("RGB").resize((300, 500), Image.Resampling.NEAREST)
    board.paste(line_crop, (25, 0))
    board.paste(color_crop, (365, 0))
    board.paste(candidate_crop, (705, 0))
    d = ImageDraw.Draw(board)
    d.text((28, 18), "线稿印花来源", fill=(30,35,45), font=font(21))
    d.text((368, 18), "彩稿材质参考", fill=(30,35,45), font=font(21))
    d.text((708, 18), "印花候选层", fill=(30,35,45), font=font(21))
    d.text((708, 475), "状态：候选表面贴层；不参与身体变形。", fill=(175,55,45), font=font(14))
    board.save(OUT)
    OUT_META.write_text(json.dumps({"status": "candidate_only_surface_decal", "path": OUT_LAYER.relative_to(ROOT).as_posix(), "geometrySource": "line-art internal components within shirt ROI", "colorSource": "gate3-color-target-v1", "roi": list(ROI), "keptComponents": kept_count, "missingByDesign": ["texture refinement", "mesh", "motion"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
