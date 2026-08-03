from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
LIVE2D = ROOT.parent
PET = LIVE2D.parent
QA_DIR = ROOT / "qa"
SRC = PET / "three-view-preview.png"
LAYER_OUT = QA_DIR / "x5-actual-xiaoju-layer-overlay.png"
MOMENT_OUT = QA_DIR / "x5-actual-xiaoju-triangulation-moment-overlay.png"
REVIEW_OUT = QA_DIR / "x5-actual-xiaoju-review-composite.png"
META_OUT = ROOT / "x5-actual-xiaoju-overlay-contract.json"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


COL = {
    "blue": (31, 105, 220, 230),
    "magenta": (218, 58, 174, 230),
    "orange": (246, 138, 32, 230),
    "green": (36, 150, 96, 220),
    "cyan": (32, 158, 176, 220),
    "yellow": (246, 190, 40, 220),
    "white": (255, 255, 255, 235),
    "ink": (42, 38, 32, 255),
    "mesh": (38, 82, 120, 160),
    "primary": (20, 92, 214, 245),
    "secondary": (230, 112, 28, 245),
    "elastic": (26, 148, 95, 245),
}


VIEWS = {
    "front": {
        "label": "FRONT",
        "bbox": (78, 115, 565, 788),
        "points": {
            "skull": (310, 300), "jaw": (310, 420), "neck": (310, 460),
            "ribcage": (310, 555), "abdomen": (310, 655), "pelvis": (310, 705),
            "ear_L_base": (405, 210), "ear_L_tip": (455, 120), "ear_R_base": (210, 210), "ear_R_tip": (150, 120),
            "eye_L": (374, 330), "eye_R": (246, 330),
            "shoulder_L": (400, 535), "elbow_L": (423, 630), "wrist_L": (410, 710), "forepaw_L": (410, 765),
            "shoulder_R": (220, 535), "elbow_R": (198, 630), "wrist_R": (205, 710), "forepaw_R": (205, 765),
            "hip_L": (455, 630), "knee_L": (500, 700), "hock_L": (480, 755), "hindpaw_L": (470, 780),
            "hip_R": (165, 630), "knee_R": (125, 700), "hock_R": (150, 755), "hindpaw_R": (155, 780),
            "tail_root": (500, 620), "tail_mid": (555, 665), "tail_tip": (520, 735),
        },
    },
    "side": {
        "label": "SIDE",
        "bbox": (625, 115, 1165, 790),
        "points": {
            "skull": (790, 310), "jaw": (700, 405), "neck": (800, 455),
            "ribcage": (890, 555), "abdomen": (935, 655), "pelvis": (980, 700),
            "ear_L_base": (780, 210), "ear_L_tip": (745, 115), "ear_R_base": (825, 215), "ear_R_tip": (820, 135),
            "eye_L": (700, 325), "eye_R": (720, 330),
            "shoulder_L": (800, 535), "elbow_L": (820, 635), "wrist_L": (780, 715), "forepaw_L": (750, 765),
            "shoulder_R": (825, 545), "elbow_R": (850, 640), "wrist_R": (815, 718), "forepaw_R": (785, 768),
            "hip_L": (1010, 610), "knee_L": (960, 690), "hock_L": (930, 745), "hindpaw_L": (900, 770),
            "hip_R": (1030, 625), "knee_R": (982, 700), "hock_R": (950, 750), "hindpaw_R": (930, 775),
            "tail_root": (1035, 690), "tail_mid": (1105, 720), "tail_tip": (1135, 690),
        },
    },
    "back": {
        "label": "BACK",
        "bbox": (1245, 115, 1670, 790),
        "points": {
            "skull": (1465, 300), "jaw": (1465, 420), "neck": (1465, 460),
            "ribcage": (1465, 555), "abdomen": (1465, 655), "pelvis": (1465, 705),
            "ear_L_base": (1375, 210), "ear_L_tip": (1320, 130), "ear_R_base": (1555, 210), "ear_R_tip": (1615, 130),
            "eye_L": (1405, 330), "eye_R": (1525, 330),
            "shoulder_L": (1370, 535), "elbow_L": (1345, 630), "wrist_L": (1355, 710), "forepaw_L": (1360, 765),
            "shoulder_R": (1560, 535), "elbow_R": (1585, 630), "wrist_R": (1575, 710), "forepaw_R": (1570, 765),
            "hip_L": (1340, 635), "knee_L": (1315, 705), "hock_L": (1328, 755), "hindpaw_L": (1340, 780),
            "hip_R": (1590, 635), "knee_R": (1615, 705), "hock_R": (1600, 755), "hindpaw_R": (1590, 780),
            "tail_root": (1460, 710), "tail_mid": (1390, 748), "tail_tip": (1320, 740),
        },
    },
}


def txt(draw: ImageDraw.ImageDraw, xy: tuple[int, int], s: str, size: int, fill=COL["ink"]) -> None:
    draw.text(xy, s, font=font(size), fill=fill)


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], s: str, fill=COL["white"]) -> None:
    w = int(font(16).getlength(s)) + 18
    x, y = xy
    draw.rounded_rectangle([x, y, x + w, y + 26], radius=5, fill=fill, outline=(60, 60, 60, 180), width=1)
    txt(draw, (x + 8, y + 4), s, 16)


def ellipse(draw: ImageDraw.ImageDraw, cx: int, cy: int, rx: int, ry: int, fill, outline, width: int = 3) -> None:
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill, outline=outline, width=width)


def poly(draw: ImageDraw.ImageDraw, pts: list[tuple[int, int]], fill, outline, width: int = 3) -> None:
    draw.polygon(pts, fill=fill, outline=outline)
    draw.line(pts + [pts[0]], fill=outline, width=width)


def line(draw: ImageDraw.ImageDraw, pts: list[tuple[int, int]], fill, width: int = 4) -> None:
    draw.line(pts, fill=fill, width=width, joint="curve")


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], fill, width: int = 4) -> None:
    line(draw, [start, end], fill, width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    for da in (2.55, -2.55):
        p = (int(end[0] + math.cos(angle + da) * 14), int(end[1] + math.sin(angle + da) * 14))
        line(draw, [end, p], fill, width)


def base_canvas() -> Image.Image:
    src = Image.open(SRC).convert("RGB")
    W, H = 2200, 1320
    img = Image.new("RGB", (W, H), (250, 250, 247))
    scale = min((W - 100) / src.width, 760 / src.height)
    resized = src.resize((int(src.width * scale), int(src.height * scale)), Image.LANCZOS)
    img.paste(resized, (50, 160))
    return img


def scale_point(p: tuple[int, int]) -> tuple[int, int]:
    # Matches base_canvas placement.
    scale = min((2200 - 100) / 1774, 760 / 887)
    return int(50 + p[0] * scale), int(160 + p[1] * scale)


def draw_layer_overlay() -> None:
    img = base_canvas().convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle([0, 0, 2200, 130], fill=(255, 246, 231, 255))
    txt(draw, (36, 24), "X5 actual Xiaoju layer overlay", 36)
    txt(draw, (36, 76), "直接基于 public/pets/xiaoju-cat/three-view-preview.png 叠加分层、隐藏补全和后续网格高密区。", 22, (116, 74, 36, 255))

    for view in VIEWS.values():
        p = {k: scale_point(v) for k, v in view["points"].items()}
        x0, y0, x1, y1 = [scale_point((view["bbox"][0], view["bbox"][1]))[0], scale_point((view["bbox"][0], view["bbox"][1]))[1], scale_point((view["bbox"][2], view["bbox"][3]))[0], scale_point((view["bbox"][2], view["bbox"][3]))[1]]
        draw.rounded_rectangle([x0, y0, x1, y1], radius=12, outline=(40, 150, 110, 220), width=3)
        txt(draw, (x0, y0 - 34), view["label"], 24, (42, 80, 72, 255))
        # Semantic layer envelopes.
        ellipse(draw, *p["skull"], 95, 120, (246, 138, 32, 42), COL["orange"], 3)
        ellipse(draw, *p["ribcage"], 92, 115, (36, 150, 96, 38), COL["green"], 3)
        ellipse(draw, *p["abdomen"], 82, 92, (36, 150, 96, 34), COL["green"], 2)
        ellipse(draw, *p["pelvis"], 85, 68, (246, 190, 40, 38), COL["yellow"], 2)
        poly(draw, [p["ear_L_base"], p["ear_L_tip"], (p["ear_L_base"][0] - 40, p["ear_L_base"][1] + 18)], (246, 138, 32, 45), COL["orange"], 3)
        poly(draw, [p["ear_R_base"], p["ear_R_tip"], (p["ear_R_base"][0] + 40, p["ear_R_base"][1] + 18)], (246, 138, 32, 45), COL["orange"], 3)
        for side, color in (("L", COL["blue"]), ("R", COL["magenta"])):
            line(draw, [p[f"shoulder_{side}"], p[f"elbow_{side}"], p[f"wrist_{side}"], p[f"forepaw_{side}"]], color, 7)
            line(draw, [p[f"hip_{side}"], p[f"knee_{side}"], p[f"hock_{side}"], p[f"hindpaw_{side}"]], (246, 190, 40, 210), 6)
        line(draw, [p["tail_root"], p["tail_mid"], p["tail_tip"]], (246, 138, 32, 230), 8)
        # Eye detail boundaries.
        for eye in ("eye_L", "eye_R"):
            ellipse(draw, *p[eye], 25, 30, (255, 230, 120, 60), (90, 70, 20, 230), 2)
        label(draw, (x0 + 8, y1 + 8), "Layer groups: head/eyes/ears/body/limbs/tail")
    draw.rounded_rectangle([36, 1128, 2164, 1268], radius=8, fill=(238, 248, 244, 255), outline=(90, 165, 130, 255), width=2)
    notes = [
        "这张图不再用抽象猫轮廓，而是把 X5 分层区直接叠到实际小橘三视图上。",
        "绿色/橙色半透明区域表示未来独立图层和隐藏补全边界；蓝/粉前肢是遮眼主动链；黄色后肢是支撑稳定链。",
        "当前仍是 X5 候选预览，不进入 X6 参数、PSD 或 Cubism。"
    ]
    for i, note in enumerate(notes):
        txt(draw, (64, 1154 + i * 34), note, 20, (36, 80, 66, 255))
    img.convert("RGB").save(LAYER_OUT)


def draw_mesh_moment_overlay() -> None:
    img = base_canvas().convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle([0, 0, 2200, 130], fill=(255, 246, 231, 255))
    txt(draw, (36, 24), "X5 actual Xiaoju triangulation + torque anchors", 34)
    txt(draw, (36, 76), "三角剖分密度、主/次力矩锚点直接叠在实际小橘三视图上；只作为 X5 审核证据。", 22, (116, 74, 36, 255))

    for view in VIEWS.values():
        p = {k: scale_point(v) for k, v in view["points"].items()}
        # Body fan triangles.
        for c_name, rx, ry, n in (("skull", 85, 105, 10), ("ribcage", 86, 104, 10), ("abdomen", 76, 84, 8), ("pelvis", 76, 58, 8)):
            c = p[c_name]
            ring = [(int(c[0] + math.cos(i / n * math.tau) * rx), int(c[1] + math.sin(i / n * math.tau) * ry)) for i in range(n)]
            for i in range(n):
                line(draw, [c, ring[i]], COL["mesh"], 1)
                line(draw, [ring[i], ring[(i + 1) % n]], COL["mesh"], 1)
        # Limb quad triangles.
        for side in ("L", "R"):
            for a, b in ((f"shoulder_{side}", f"elbow_{side}"), (f"elbow_{side}", f"wrist_{side}"), (f"wrist_{side}", f"forepaw_{side}"), (f"hip_{side}", f"knee_{side}"), (f"knee_{side}", f"hock_{side}"), (f"hock_{side}", f"hindpaw_{side}")):
                pa, pb = p[a], p[b]
                dx, dy = pb[0] - pa[0], pb[1] - pa[1]
                ln = max(1.0, math.hypot(dx, dy))
                nx, ny = -dy / ln * 18, dx / ln * 18
                q = [(int(pa[0] + nx), int(pa[1] + ny)), (int(pa[0] - nx), int(pa[1] - ny)), (int(pb[0] - nx), int(pb[1] - ny)), (int(pb[0] + nx), int(pb[1] + ny))]
                line(draw, q + [q[0]], COL["mesh"], 1)
                line(draw, [q[0], q[2]], COL["mesh"], 1)
        # Anchors.
        primary = ["ribcage", "shoulder_L", "elbow_L", "wrist_L", "shoulder_R", "elbow_R", "wrist_R"]
        secondary = ["neck", "ear_L_base", "ear_R_base", "tail_root", "abdomen"]
        for name in primary:
            ellipse(draw, *p[name], 9, 9, COL["primary"], (255, 255, 255, 240), 2)
        for name in secondary:
            ellipse(draw, *p[name], 8, 8, COL["secondary"], (255, 255, 255, 240), 2)
        # Force directions on front/side/back alike.
        for side, sx in (("L", -1), ("R", 1)):
            for name in (f"shoulder_{side}", f"elbow_{side}", f"wrist_{side}"):
                start = p[name]
                arrow(draw, start, (start[0] + sx * 48, start[1] - 28), COL["primary"], 3)
        arrow(draw, p["ribcage"], (p["ribcage"][0], p["ribcage"][1] + 54), COL["primary"], 3)
        arrow(draw, p["tail_root"], (p["tail_root"][0] + 52, p["tail_root"][1] + 10), COL["secondary"], 3)

    legend_x, legend_y = 1410, 955
    draw.rounded_rectangle([legend_x, legend_y, 2164, 1268], radius=8, fill=(255, 255, 255, 235), outline=(150, 150, 130, 255), width=2)
    txt(draw, (legend_x + 20, legend_y + 18), "Actual-image X5 legend", 24)
    txt(draw, (legend_x + 20, legend_y + 58), "Blue dots/arrows: primary active/torque anchors", 18, COL["primary"])
    txt(draw, (legend_x + 20, legend_y + 90), "Orange dots/arrows: secondary elastic anchors", 18, COL["secondary"])
    txt(draw, (legend_x + 20, legend_y + 122), "Thin slate lines: future triangle density on real layer boundaries", 18, (60, 80, 100, 255))
    txt(draw, (legend_x + 20, legend_y + 164), "Front paws: password-cover active chain", 18, COL["primary"])
    txt(draw, (legend_x + 20, legend_y + 196), "Hind paws: support/stabilize, not cover chain", 18, COL["green"])
    txt(draw, (legend_x + 20, legend_y + 238), "No PSD/Cubism/X6 generated here.", 18, (128, 56, 44, 255))
    img.convert("RGB").save(MOMENT_OUT)


def draw_review_composite() -> None:
    layer = Image.open(LAYER_OUT).resize((1100, 660), Image.LANCZOS)
    moment = Image.open(MOMENT_OUT).resize((1100, 660), Image.LANCZOS)
    img = Image.new("RGB", (2200, 1460), (250, 250, 247))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 2200, 120], fill=(255, 246, 231))
    txt(draw, (36, 22), "X5 actual Xiaoju review composite", 36)
    txt(draw, (36, 72), "基于实际小橘三视图生成的 X5 分层、三角剖分、力矩和弹性审核入口。", 22, (116, 74, 36))
    img.paste(layer, (0, 130))
    img.paste(moment, (1100, 130))
    draw.rounded_rectangle([36, 830, 2164, 1404], radius=8, fill=(238, 248, 244), outline=(90, 165, 130), width=2)
    checks = [
        "1. 分层现在必须看实际小橘，而不是抽象猫：头、眼、耳、胸腹、四肢、尾巴边界都直接叠到源图。",
        "2. 三角高密区应沿真实轮廓/高曲率/遮挡处布置：眼眶、眼睑、耳根、肩肘腕、髋膝跗、尾根。",
        "3. 主力矩锚点只用于核心动作和支撑：胸腹支撑、肩、肘、腕、前爪接触。",
        "4. 次级锚点只用于弹性：耳尖、尾巴、胡须、脸颊/胸毛、腹部呼吸与回稳。",
        "5. 后爪只保留支撑/稳定参数，不再误挂遮眼前肢链。",
        "6. 仍是 X5 候选：如果通过，下一步才进入 X6 参数和 Action Tracer。"
    ]
    for i, check in enumerate(checks):
        txt(draw, (70, 866 + i * 48), check, 22, (36, 78, 66))
    img.save(REVIEW_OUT)


def write_meta() -> None:
    data = {
        "schemaVersion": 1,
        "stage": "X5-actual-xiaoju-overlays",
        "status": "candidate-for-user-review",
        "sourceImage": "three-view-preview.png",
        "sourcePath": "public/pets/xiaoju-cat/three-view-preview.png",
        "userCorrection": "Preview must be generated on the actual Xiaoju three-view image, not an abstract placeholder cat.",
        "artifacts": {
            "layerOverlay": "live2d/x5/qa/x5-actual-xiaoju-layer-overlay.png",
            "triangulationMomentOverlay": "live2d/x5/qa/x5-actual-xiaoju-triangulation-moment-overlay.png",
            "reviewComposite": "live2d/x5/qa/x5-actual-xiaoju-review-composite.png",
        },
        "gateBoundary": {
            "currentGate": "x5-layer-mesh-node-torque",
            "x5MayPassOnlyWithUserApproval": True,
            "x6Authorized": False,
            "forbidden": ["PSD import", "Cubism editing", "X6 parameter/keyform finalization", "runtime replacement"],
        },
    }
    META_OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    draw_layer_overlay()
    draw_mesh_moment_overlay()
    draw_review_composite()
    write_meta()
    for p in (LAYER_OUT, MOMENT_OUT, REVIEW_OUT, META_OUT):
        print(p.as_posix())


if __name__ == "__main__":
    main()
