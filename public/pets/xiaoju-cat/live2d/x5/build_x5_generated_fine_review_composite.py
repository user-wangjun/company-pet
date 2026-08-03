from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "qa" / "x5-actual-xiaoju-spread-pose-three-view.png"
LAYER_ATLAS = ROOT / "qa" / "x5-generated-fine-layer-candidates-atlas-v1.png"
MESH_ATLAS = ROOT / "qa" / "x5-generated-fine-layer-triangulation-atlas-v1.png"
MESH_CONTRACT = ROOT / "x5-generated-fine-mesh-contract-v1.json"
OVERLAY = ROOT / "qa" / "x5-generated-fine-actual-xiaoju-mesh-node-torque-overlay-v1.png"
COMPOSITE = ROOT / "qa" / "x5-generated-fine-production-review-composite-v1.png"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


P = {
    "front": {
        "ear_L": (414, 105), "ear_L_tip": (452, 40), "ear_R": (256, 105), "ear_R_tip": (220, 40),
        "head": (335, 195), "neck": (335, 305), "rib": (335, 405), "abd": (335, 520), "pelvis": (335, 610),
        "shoulder_L": (440, 330), "elbow_L": (500, 370), "wrist_L": (548, 414), "forepaw_L": (570, 435),
        "shoulder_R": (230, 330), "elbow_R": (170, 370), "wrist_R": (112, 414), "forepaw_R": (88, 435),
        "hip_L": (420, 585), "knee_L": (475, 640), "hock_L": (515, 692), "hindpaw_L": (535, 710),
        "hip_R": (250, 585), "knee_R": (195, 640), "hock_R": (150, 692), "hindpaw_R": (130, 710),
        "tail_root": (335, 615), "tail_mid": (338, 720), "tail_tip": (350, 810),
    },
    "side": {
        "ear_L": (838, 104), "ear_L_tip": (814, 45), "ear_R": (875, 108), "ear_R_tip": (882, 52),
        "head": (820, 195), "neck": (845, 305), "rib": (875, 410), "abd": (895, 520), "pelvis": (920, 610),
        "shoulder_L": (820, 335), "elbow_L": (780, 372), "wrist_L": (735, 414), "forepaw_L": (700, 438),
        "shoulder_R": (845, 350), "elbow_R": (805, 390), "wrist_R": (765, 430), "forepaw_R": (730, 454),
        "hip_L": (895, 590), "knee_L": (845, 652), "hock_L": (790, 705), "hindpaw_L": (745, 730),
        "hip_R": (930, 605), "knee_R": (885, 670), "hock_R": (840, 725), "hindpaw_R": (805, 754),
        "tail_root": (950, 610), "tail_mid": (990, 710), "tail_tip": (980, 805),
    },
    "back": {
        "ear_L": (1495, 105), "ear_L_tip": (1515, 42), "ear_R": (1385, 105), "ear_R_tip": (1365, 42),
        "head": (1440, 195), "neck": (1440, 305), "rib": (1440, 410), "abd": (1440, 520), "pelvis": (1440, 610),
        "shoulder_L": (1550, 330), "elbow_L": (1610, 372), "wrist_L": (1650, 414), "forepaw_L": (1630, 440),
        "shoulder_R": (1330, 330), "elbow_R": (1270, 372), "wrist_R": (1215, 414), "forepaw_R": (1188, 440),
        "hip_L": (1530, 585), "knee_L": (1580, 642), "hock_L": (1610, 690), "hindpaw_L": (1605, 710),
        "hip_R": (1350, 585), "knee_R": (1300, 642), "hock_R": (1245, 690), "hindpaw_R": (1215, 710),
        "tail_root": (1430, 615), "tail_mid": (1410, 720), "tail_tip": (1390, 810),
    },
}


def arrow(draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float], color: tuple[int, int, int, int], width: int = 4) -> None:
    draw.line([start, end], fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    for delta in (-0.55, 0.55):
        tip = (end[0] - 14 * math.cos(angle + delta), end[1] - 14 * math.sin(angle + delta))
        draw.line([end, tip], fill=color, width=width)


def segment_mesh(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], half_widths: list[float]) -> None:
    left: list[tuple[float, float]] = []
    right: list[tuple[float, float]] = []
    for index, point in enumerate(points):
        if index == 0:
            dx, dy = points[1][0] - point[0], points[1][1] - point[1]
        elif index == len(points) - 1:
            dx, dy = point[0] - points[index - 1][0], point[1] - points[index - 1][1]
        else:
            dx, dy = points[index + 1][0] - points[index - 1][0], points[index + 1][1] - points[index - 1][1]
        length = max(1.0, math.hypot(dx, dy))
        nx, ny = -dy / length, dx / length
        width = half_widths[index]
        left.append((point[0] + nx * width, point[1] + ny * width))
        right.append((point[0] - nx * width, point[1] - ny * width))
    mesh_color = (20, 105, 215, 135)
    for index in range(len(points) - 1):
        draw.line([left[index], left[index + 1], right[index + 1], right[index], left[index]], fill=mesh_color, width=2)
        draw.line([left[index], right[index + 1]], fill=mesh_color, width=2)
        draw.line([right[index], left[index + 1]], fill=mesh_color, width=1)


def draw_overlay() -> None:
    image = Image.open(SOURCE).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    primary = (232, 65, 45, 240)
    secondary = (24, 152, 94, 235)
    bone = (20, 76, 128, 235)
    helper = (26, 110, 220, 220)
    for view, p in P.items():
        spine = [p["head"], p["neck"], p["rib"], p["abd"], p["pelvis"]]
        segment_mesh(draw, spine, [52, 50, 82, 92, 82])
        for side in ("L", "R"):
            fore = [p[f"shoulder_{side}"], p[f"elbow_{side}"], p[f"wrist_{side}"], p[f"forepaw_{side}"]]
            hind = [p[f"hip_{side}"], p[f"knee_{side}"], p[f"hock_{side}"], p[f"hindpaw_{side}"]]
            segment_mesh(draw, fore, [28, 24, 20, 24])
            segment_mesh(draw, hind, [38, 32, 24, 28])
            draw.line(fore, fill=bone, width=5)
            draw.line(hind, fill=bone, width=5)
            for name in (f"shoulder_{side}",):
                x, y = p[name]
                draw.ellipse([x - 7, y - 7, x + 7, y + 7], fill=primary, outline=(255, 255, 255, 245), width=2)
            for name in (f"hip_{side}",):
                x, y = p[name]
                draw.ellipse([x - 7, y - 7, x + 7, y + 7], fill=primary, outline=(255, 255, 255, 245), width=2)
            for name in (f"elbow_{side}", f"wrist_{side}", f"knee_{side}", f"hock_{side}", f"hindpaw_{side}"):
                x, y = p[name]
                draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=helper, outline=(255, 255, 255, 220), width=1)
            paw = p[f"forepaw_{side}"]
            arrow(draw, (paw[0], paw[1] - 6), (paw[0], paw[1] + 42), primary, 4)
        draw.line([p["tail_root"], p["tail_mid"], p["tail_tip"]], fill=secondary, width=5)
        draw.line([p["ear_L"], p["ear_L_tip"]], fill=secondary, width=4)
        draw.line([p["ear_R"], p["ear_R_tip"]], fill=secondary, width=4)
        for name in ("rib", "tail_root", "tail_mid", "tail_tip", "ear_L", "ear_R"):
            x, y = p[name]
            draw.ellipse([x - 6, y - 6, x + 6, y + 6], fill=secondary, outline=(255, 255, 255, 240), width=2)
        gravity_start = (p["rib"][0], p["rib"][1] - 28)
        gravity_end = (p["rib"][0], p["rib"][1] + 45)
        x, y = p["rib"]
        draw.ellipse([x - 8, y - 8, x + 8, y + 8], fill=primary, outline=(255, 255, 255, 245), width=2)
        arrow(draw, gravity_start, gravity_end, primary, 5)
        draw.text((gravity_end[0] + 8, gravity_end[1] - 22), "F_g", font=font(16), fill=primary)
    header = Image.new("RGBA", (image.width, image.height + 94), (250, 250, 247, 255))
    header.alpha_composite(image, (0, 94))
    d = ImageDraw.Draw(header, "RGBA")
    d.rounded_rectangle([22, 14, header.width - 22, 78], radius=8, fill=(255, 252, 246, 248), outline=(120, 135, 120, 225), width=2)
    d.text((44, 24), "X5 实际小橘：分层网格支点 / 骨段 / 力矩与耳尾弹性", font=font(27), fill=(34, 38, 44, 255))
    d.text((44, 56), "蓝=骨段/小型关节，红=躯干/肩/髋主力矩支点与 F，绿=耳尾次级弹性支点。", font=font(15), fill=(104, 77, 52, 255))
    header.convert("RGB").save(OVERLAY)


def fit_panel(path: Path, width: int, height: int) -> Image.Image:
    image = Image.open(path).convert("RGB")
    scale = min(width / image.width, height / image.height)
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    panel = Image.new("RGB", (width, height), (250, 250, 247))
    panel.paste(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
    return panel


def build_composite() -> None:
    mesh = json.loads(MESH_CONTRACT.read_text(encoding="utf-8"))
    width = 1800
    top_h, atlas_h, mesh_h = 990, 1120, 1160
    sheet = Image.new("RGB", (width, 150 + top_h + atlas_h + mesh_h + 150), (250, 250, 247))
    draw = ImageDraw.Draw(sheet)
    draw.rounded_rectangle([24, 18, width - 24, 112], radius=8, fill=(255, 252, 246), outline=(120, 135, 120), width=2)
    draw.text((50, 32), "X5 小橘精细分层 -> 三角剖分 -> 节点/力矩/弹性 总预览", font=font(31), fill=(34, 38, 44))
    draw.text((50, 76), f"63 层 / {mesh['counts']['points']} 顶点 / {mesh['counts']['triangles']} 三角形；基于现有小橘三视图，仅供 X5 视觉审核。", font=font(18), fill=(104, 77, 52))
    y = 140
    sheet.paste(fit_panel(OVERLAY, width - 60, top_h), (30, y))
    y += top_h + 32
    draw.text((42, y - 4), "A. 生成式精细透明分层素材", font=font(24), fill=(34, 38, 44))
    y += 34
    sheet.paste(fit_panel(LAYER_ATLAS, width - 60, atlas_h), (30, y))
    y += atlas_h + 32
    draw.text((42, y - 4), "B. 每层真实 Alpha 边界的质量约束三角剖分", font=font(24), fill=(34, 38, 44))
    y += 34
    sheet.paste(fit_panel(MESH_ATLAS, width - 60, mesh_h), (30, y))
    y += mesh_h + 18
    draw.text((42, y), "门禁：gate5Approved=false，x6Authorized=false。本图不是 PSD/Cubism 或运行时输出。", font=font(17), fill=(158, 62, 47))
    sheet.save(COMPOSITE)


def main() -> None:
    draw_overlay()
    build_composite()
    print(OVERLAY.as_posix())
    print(COMPOSITE.as_posix())


if __name__ == "__main__":
    main()
