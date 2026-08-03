from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
COLOR = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def line_overlay(color: Image.Image, line: Image.Image) -> Image.Image:
    out = color.convert("RGBA")
    rgb = line.convert("RGB")
    mask = Image.new("L", line.size, 0)
    mp, px = mask.load(), rgb.load()
    for y in range(line.height):
        for x in range(line.width):
            r, g, b = px[x, y]
            if (r + g + b) / 3 < 150:
                mp[x, y] = 185
    red = Image.new("RGBA", line.size, (235, 30, 30, 0))
    red.putalpha(mask)
    return Image.alpha_composite(out, red)


def main() -> None:
    color = Image.open(COLOR).convert("RGB")
    line = Image.open(LINE).convert("RGB")
    overlay = line_overlay(color, line).convert("RGB")
    board = Image.new("RGB", (1660, 1235), "white")
    d = ImageDraw.Draw(board)
    d.text((24, 18), "小星 V2 线稿优先基线（原始比例、无拉伸）", fill=(25, 25, 30), font=font(27))
    d.text((24, 56), "线稿决定分层边界；彩稿只负责身份、颜色和材质。红线叠加用于暴露两张图内部并非逐像素一致。", fill=(150, 50, 45), font=font(17))
    for x, image, label in ((24, color, "彩色参考（仅配色/身份）"), (574, line, "线稿生产基线（分层边界）"), (1124, overlay, "同坐标叠加（红=线稿）")):
        board.paste(image, (x, 110))
        d.rectangle((x, 110, x + 511, 1195), outline=(185, 190, 198), width=2)
        d.text((x + 10, 120), label, fill=(30, 55, 90), font=font(16), stroke_width=2, stroke_fill="white")
    out = ROOT / "qa" / "v2-lineart-baseline-audit.png"
    board.save(out, quality=95)
    status = {
        "currentAuthority": "v2-lineart-first",
        "sourceOfTruth": {"separationBoundaries": "source/masters/gate3-line-master-candidate-v1.png", "identityAndPalette": "source/masters/gate3-color-target-v1.png"},
        "invariants": ["512x1086 source coordinates", "no non-uniform resize", "no polygon draft promoted to production mask", "each exported layer traced from line art before texturing"],
        "rejectedExperiments": ["gate4-eye-*", "gate5-*", "gate6-*", "gate7-*", "gate8-*", "gate9-*", "gate10-*"],
        "reason": "眼睛与线稿未对齐；Gate 5 非等比拉伸；Gate 6 无法证明动作；Gate 7 起的素材继承错误边界并发生变形",
        "articlePrinciplesApplied": ["每个图层独立导出 PNG", "每层建立自己的三角网格", "图层按绘制顺序管理", "每层只有一个节点且节点至多一个父节点", "父节点变换传递给子节点", "弹性与追踪在正确分层和网格之后"],
    }
    (ROOT / "audit" / "authoritative-status-v2.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
