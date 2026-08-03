from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
CONTRACT = ROOT / "blueprints" / "v2-upper-body-ownership-contract.json"
OUT = ROOT / "qa" / "v2-upper-body-ownership-audit.png"


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
    board = Image.new("RGBA", (1024, 1086), "white")
    board.alpha_composite(line, (0, 0))
    overlay = Image.new("RGBA", board.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    colors = [(235,145,45,75),(55,155,225,65),(55,185,135,65),(170,90,205,65),(235,90,120,65),(245,190,50,65),(80,125,225,65),(180,120,50,65),(100,180,180,65)]
    for index, group in enumerate(data["groups"]):
        pts = [tuple(point) for point in group["polygon"]]
        od.polygon(pts, fill=colors[index], outline=(130,45,55,220))
        cx = sum(point[0] for point in pts) // len(pts)
        cy = sum(point[1] for point in pts) // len(pts)
        od.ellipse((cx-11, cy-11, cx+11, cy+11), fill=(255,205,45,235), outline=(105,55,25,255), width=2)
        od.text((cx-5, cy-10), str(index+1), fill=(40,35,25,255), font=font(17))
    board.alpha_composite(overlay)
    out = board.convert("RGB")
    d = ImageDraw.Draw(out)
    d.rectangle((535,0,1024,1086), fill="white")
    d.text((560,28), "小星 V2｜上半身材料所有权候选", fill=(25,28,35), font=font(26))
    d.text((560,70), "左侧：原线稿 + 半透明候选范围；编号不是最终切图。", fill=(155,45,40), font=font(16))
    d.text((560,99), "手部按每侧一整层处理，不拆手指。", fill=(55,80,125), font=font(16))
    y = 155
    for index, group in enumerate(data["groups"]):
        d.text((560,y), f"{index+1}. {group['label']}", fill=(35,40,50), font=font(17))
        d.text((585,y+26), f"父节点：{group['parent']}｜交界：{group['seam']}", fill=(80,80,90), font=font(12))
        y += 70
    d.text((560,850), "检查重点", fill=(180,55,45), font=font(18))
    d.text((560,885), "• 袖子不带前臂", fill=(70,75,85), font=font(15))
    d.text((560,915), "• 手层不带袖子", fill=(70,75,85), font=font(15))
    d.text((560,945), "• 项链不并入衣身", fill=(70,75,85), font=font(15))
    d.text((560,1000), "状态：粗分层候选，未生成 RGBA。", fill=(180,55,45), font=font(15))
    out.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
