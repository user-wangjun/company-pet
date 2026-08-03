from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
CONTRACT = ROOT / "blueprints" / "v2-lower-body-ownership-contract.json"
OUT = ROOT / "qa" / "v2-lower-body-ownership-audit.png"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def main():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    line = Image.open(LINE).convert("RGBA")
    board = Image.new("RGBA", (1024, 1320), "white")
    shown = line.resize((512, 1086), Image.Resampling.NEAREST)
    board.alpha_composite(shown, (0, 0))
    overlay = Image.new("RGBA", board.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    colors = [(235, 145, 45, 85), (55, 155, 225, 75), (55, 185, 135, 75), (170, 90, 205, 75), (235, 90, 120, 75), (245, 190, 50, 75), (80, 125, 225, 75)]
    for index, group in enumerate(data["groups"]):
        pts = [tuple(point) for point in group["polygon"]]
        color = colors[index % len(colors)]
        od.polygon(pts, fill=color, outline=(120, 45, 50, 220))
        cx = sum(p[0] for p in pts) // len(pts)
        cy = sum(p[1] for p in pts) // len(pts)
        od.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill=(255, 210, 55, 240), outline=(110, 55, 25, 255), width=2)
        ImageDraw.Draw(overlay).text((cx - 6, cy - 11), str(index + 1), fill=(40, 35, 25, 255), font=font(18))
    board.alpha_composite(overlay)
    out = board.convert("RGB")
    d = ImageDraw.Draw(out)
    d.rectangle((520, 0, 1024, 1320), fill="white")
    d.text((550, 30), "小星 V2｜下半身材料所有权候选", fill=(25, 28, 35), font=font(26))
    d.text((550, 72), "左侧：原线稿 + 半透明候选范围；编号不是最终切图。", fill=(155, 45, 40), font=font(16))
    d.text((550, 101), "需要检查：边界有没有越过线稿、相邻层是否留有合理重叠。", fill=(55, 80, 125), font=font(16))
    y = 155
    for index, group in enumerate(data["groups"]):
        d.text((550, y), f"{index + 1}. {group['label']}", fill=(35, 40, 50), font=font(18))
        d.text((575, y + 28), f"父节点：{group['parent']}｜交界：{group['seam']}", fill=(80, 80, 90), font=font(13))
        y += 68
    d.text((550, 1085), "状态：粗分层候选，未生成 RGBA。", fill=(180, 55, 45), font=font(16))
    d.text((550, 1120), "裙内隐藏大腿仍需结合侧视图补全。", fill=(80, 80, 90), font=font(15))
    d.text((550, 1170), "原则：线稿定边 → 独立层 → 网格 → 参数。", fill=(55, 80, 125), font=font(15))
    out.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
