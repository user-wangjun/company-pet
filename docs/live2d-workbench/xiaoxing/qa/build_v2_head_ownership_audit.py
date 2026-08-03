from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
CONTRACT = ROOT / "blueprints" / "v2-head-ownership-contract.json"
OUT = ROOT / "qa" / "v2-head-ownership-audit.png"
CROP = (155, 18, 355, 350)
SCALE = 2


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def mapped(points, origin):
    return [((x - CROP[0]) * SCALE + origin[0], (y - CROP[1]) * SCALE + origin[1]) for x, y in points]


def panel(board, base, groups, origin, title, colors):
    x, y = origin
    board.paste(base, (x, y + 48))
    draw = ImageDraw.Draw(board)
    draw.rounded_rectangle((x - 8, y, x + 408, y + 730), radius=10, outline=(190, 195, 205), width=2)
    draw.text((x + 8, y + 10), title, fill=(30, 35, 45), font=font(20))
    for index, group in enumerate(groups):
        points = mapped(group["polygon"], (x, y + 48))
        draw.line(points + [points[0]], fill=colors[index], width=4, joint="curve")
    note_y = y + 675
    for index, group in enumerate(groups):
        draw.text((x + 8, note_y), f"{group['label']}：{group['status']}", fill=colors[index], font=font(13))
        note_y += 23


def main():
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    groups = {group["id"]: group for group in data["groups"]}
    line = Image.open(LINE).convert("RGB")
    base = line.crop(CROP).resize(((CROP[2] - CROP[0]) * SCALE, (CROP[3] - CROP[1]) * SCALE), Image.Resampling.NEAREST)
    board = Image.new("RGB", (1280, 840), "white")
    draw = ImageDraw.Draw(board)
    draw.text((25, 15), "小星 V2｜头部线稿分组复核（只描边，不导出素材）", fill=(25, 28, 35), font=font(27))
    draw.text((25, 55), "三个面板分别检查脸/耳、前发、后发；线条不代表已经确认的 alpha 边界。", fill=(165, 50, 45), font=font(16))
    panel(board, base, [groups["face_base"], groups["ear_screen_left"], groups["ear_screen_right"]], (20, 95), "1. 脸底与耳朵", [(20, 145, 185), (220, 130, 35), (220, 130, 35)])
    panel(board, base, [groups["front_hair_screen_left"], groups["front_hair_screen_right"]], (440, 95), "2. 左右前发", [(45, 145, 220), (55, 175, 115)])
    panel(board, base, [groups["back_hair"]], (860, 95), "3. 后发主体", [(165, 75, 185)])
    draw.text((25, 810), "当前结论：耳朵与头发隐藏区仍需侧/背视图补全；本图只用于发现越界，不生成 RGBA。", fill=(175, 55, 45), font=font(15))
    board.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
