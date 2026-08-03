from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
QA_DIR = ROOT / "qa"
LAYER_DIR = ROOT / "actual-layer-candidates"
SRC = QA_DIR / "x5-actual-xiaoju-spread-pose-three-view.png"
ATLAS = QA_DIR / "x5-actual-xiaoju-transparent-layer-atlas.png"
BOUNDARY = QA_DIR / "x5-actual-xiaoju-layer-boundary-preview.png"
RECONSTRUCTION = QA_DIR / "x5-actual-xiaoju-layer-reconstruction-coverage.png"
CONTRACT = ROOT / "x5-actual-xiaoju-layer-split-contract.json"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


COLORS = [
    (220, 80, 62, 235),
    (40, 118, 220, 235),
    (30, 150, 102, 235),
    (222, 128, 28, 235),
    (136, 82, 196, 235),
    (18, 138, 160, 235),
    (194, 76, 132, 235),
]


@dataclass(frozen=True)
class Shape:
    kind: str
    args: tuple


@dataclass(frozen=True)
class LayerDef:
    view: str
    layer_id: str
    name: str
    parent: str
    draw_order: int
    pivot: str
    hidden_overlap: str
    mesh_zone: str
    elastic: str
    shapes: tuple[Shape, ...]


def S(kind: str, *args) -> Shape:
    return Shape(kind, args)


P = {
    "front": {
        "skull": (335, 205), "neck": (335, 312), "rib": (335, 398), "abd": (335, 515), "pelvis": (335, 610),
        "eye_L": (382, 177), "eye_R": (288, 177), "muzzle": (335, 250),
        "ear_L_base": (415, 104), "ear_L_tip": (455, 37), "ear_R_base": (255, 104), "ear_R_tip": (218, 37),
        "shoulder_L": (430, 330), "elbow_L": (485, 350), "wrist_L": (545, 377), "forepaw_L": (606, 400),
        "shoulder_R": (240, 330), "elbow_R": (185, 350), "wrist_R": (125, 377), "forepaw_R": (70, 400),
        "hip_L": (410, 600), "knee_L": (475, 675), "hock_L": (505, 735), "hindpaw_L": (545, 775),
        "hip_R": (260, 600), "knee_R": (195, 675), "hock_R": (165, 735), "hindpaw_R": (125, 775),
        "tail_root": (335, 638), "tail_mid": (338, 730), "tail_tip": (340, 825),
    },
    "side": {
        "skull": (805, 205), "neck": (832, 318), "rib": (890, 420), "abd": (925, 525), "pelvis": (965, 600),
        "eye_L": (760, 178), "eye_R": (768, 182), "muzzle": (745, 246),
        "ear_L_base": (840, 105), "ear_L_tip": (815, 42), "ear_R_base": (880, 110), "ear_R_tip": (888, 50),
        "shoulder_L": (850, 345), "elbow_L": (800, 382), "wrist_L": (755, 420), "forepaw_L": (720, 458),
        "shoulder_R": (875, 358), "elbow_R": (828, 396), "wrist_R": (785, 432), "forepaw_R": (750, 468),
        "hip_L": (900, 600), "knee_L": (845, 665), "hock_L": (790, 720), "hindpaw_L": (744, 744),
        "hip_R": (930, 610), "knee_R": (885, 680), "hock_R": (840, 738), "hindpaw_R": (805, 770),
        "tail_root": (980, 615), "tail_mid": (1010, 710), "tail_tip": (1006, 800),
    },
    "back": {
        "skull": (1440, 205), "neck": (1440, 318), "rib": (1440, 420), "abd": (1440, 530), "pelvis": (1440, 615),
        "ear_L_base": (1496, 136), "ear_L_tip": (1488, 90), "ear_R_base": (1384, 136), "ear_R_tip": (1392, 90),
        "shoulder_L": (1548, 365), "elbow_L": (1602, 410), "wrist_L": (1652, 445), "forepaw_L": (1628, 470),
        "shoulder_R": (1332, 365), "elbow_R": (1278, 410), "wrist_R": (1228, 445), "forepaw_R": (1195, 470),
        "hip_L": (1538, 616), "knee_L": (1588, 674), "hock_L": (1618, 702), "hindpaw_L": (1608, 716),
        "hip_R": (1342, 616), "knee_R": (1292, 674), "hock_R": (1248, 702), "hindpaw_R": (1218, 716),
        "tail_root": (1428, 638), "tail_mid": (1405, 724), "tail_tip": (1388, 802),
    },
}


def ellipse_shape(center: tuple[int, int], rx: int, ry: int) -> Shape:
    return S("ellipse", center, rx, ry)


def poly_shape(points: list[tuple[int, int]]) -> Shape:
    return S("poly", tuple(points))


def line_shape(points: list[tuple[int, int]], width: int) -> Shape:
    return S("line", tuple(points), width)


def build_layers_for_view(view: str) -> list[LayerDef]:
    p = P[view]
    back = view == "back"
    side = view == "side"
    layers: list[LayerDef] = []

    def add(layer_id: str, name: str, parent: str, draw: int, pivot: str, overlap: str, mesh: str, elastic: str, *shapes: Shape) -> None:
        layers.append(LayerDef(view, layer_id, name, parent, draw, pivot, overlap, mesh, elastic, shapes))

    add("tail_root_socket", "尾根隐藏插口毛皮", "Pelvis", 88, "tail_root", "under pelvis and tail_root, +18px safety", "tail-root high density", "socket soft", line_shape([p["tail_root"], p["tail_mid"]], 86))
    add("tail_base", "尾根段", "TailRoot", 90, "tail_root", "over tail_root_socket, under tail_mid", "bend fan", "root active", line_shape([p["tail_root"], p["tail_mid"]], 70))
    add("tail_mid", "尾中段", "TailMid", 95, "tail_mid", "over tail_base, under tail_tip", "two bend bands", "medium lag", line_shape([p["tail_root"], p["tail_mid"], p["tail_tip"]], 58))
    add("tail_tip", "尾尖段", "TailTip", 100, "tail_tip", "over tail_mid", "tip fan", "high lag", ellipse_shape(p["tail_tip"], 42, 45))

    for side_id in ("L", "R"):
        add(f"hind_thigh_{side_id}", f"{side_id} 大腿/髋包络", f"Hip_{side_id}", 145 if side_id == "L" else 155, f"hip_{side_id}", "under pelvis, +20px hip overlap", "hip/knee dense", "soft thigh", line_shape([p[f"hip_{side_id}"], p[f"knee_{side_id}"]], 96))
        add(f"hind_shin_{side_id}", f"{side_id} 小腿/跗", f"Knee_{side_id}", 146 if side_id == "L" else 156, f"knee_{side_id}", "under thigh and paw", "knee/hock dense", "low", line_shape([p[f"knee_{side_id}"], p[f"hock_{side_id}"]], 72))
        add(f"hind_paw_{side_id}", f"{side_id} 后爪", f"Hock_{side_id}", 147 if side_id == "L" else 157, f"hindpaw_{side_id}", "into shin +14px", "toe arcs", "toe soft", ellipse_shape(p[f"hindpaw_{side_id}"], 66, 43))

    add("pelvis", "骨盆/臀部", "BodyRoot", 210, "pelvis", "under abdomen, hips and tail", "medium oval", "stable mass", ellipse_shape(p["pelvis"], 146, 124))
    add("abdomen", "腹部软层", "BodyRoot", 220, "abd", "under ribcage and pelvis, +24px", "breath grid", "breath/settle", ellipse_shape(p["abd"], 148, 160))
    add("ribcage", "胸腔/躯干", "BodyRoot", 230, "rib", "under neck and forelimbs", "shoulder/contact dense", "small breath", ellipse_shape(p["rib"], 158, 166))
    add("neck_fill", "颈部隐藏补全", "Neck", 310, "neck", "under head and chest fur", "head-neck seam", "low stretch", ellipse_shape(p["neck"], 72, 76))
    add("chest_fur", "胸毛覆盖片", "Ribcage", 300, "neck", "over ribcage, under head/muzzle", "fur tips dense", "fur lag", poly_shape([(p["neck"][0]-70, p["neck"][1]-30), (p["neck"][0]+70, p["neck"][1]-30), (p["rib"][0]+90, p["rib"][1]+45), (p["rib"][0], p["rib"][1]+128), (p["rib"][0]-90, p["rib"][1]+45)]))

    for side_id in ("L", "R"):
        add(f"scapula_fur_{side_id}", f"{side_id} 肩胛遮挡毛", f"Scapula_{side_id}", 340 if side_id == "L" else 341, f"shoulder_{side_id}", "over ribcage and upper_arm", "armpit seam", "armpit shear", ellipse_shape(p[f"shoulder_{side_id}"], 58, 45))
        add(f"upper_arm_{side_id}", f"{side_id} 上臂", f"Shoulder_{side_id}", 350 if side_id == "L" else 351, f"shoulder_{side_id}", "under scapula, over forearm", "shoulder/elbow dense", "low", line_shape([p[f"shoulder_{side_id}"], p[f"elbow_{side_id}"]], 70))
        add(f"forearm_{side_id}", f"{side_id} 前臂", f"Elbow_{side_id}", 360 if side_id == "L" else 361, f"elbow_{side_id}", "under upper_arm and paw", "elbow/wrist dense", "sleeve soft", line_shape([p[f"elbow_{side_id}"], p[f"wrist_{side_id}"]], 62))
        add(f"wrist_fur_{side_id}", f"{side_id} 腕毛", f"Wrist_{side_id}", 370 if side_id == "L" else 371, f"wrist_{side_id}", "over wrist seam", "small fan", "soft", ellipse_shape(p[f"wrist_{side_id}"], 34, 26))
        add(f"fore_paw_{side_id}", f"{side_id} 前爪", f"Wrist_{side_id}", 380 if side_id == "L" else 381, f"forepaw_{side_id}", "into wrist +16px", "toe/contact arc", "toe soft", ellipse_shape(p[f"forepaw_{side_id}"], 72, 48))

    add("head_base", "头骨/脸底", "Neck", 500, "skull", "under ears, eyes and muzzle", "face oval medium", "stable mass", ellipse_shape(p["skull"], 168, 180))
    add("ear_root_L", "左耳根", "Head", 610, "ear_L_base", "under ear face/head fur", "root wedge", "root active", ellipse_shape(p["ear_L_base"], 42, 35))
    add("ear_face_L", "左耳面", "EarRoot_L", 620, "ear_L_base", "over root", "triangle surface", "low bend", poly_shape([(p["ear_L_base"][0]-38, p["ear_L_base"][1]+25), p["ear_L_tip"], (p["ear_L_base"][0]+48, p["ear_L_base"][1]+28)]))
    add("ear_tip_L", "左耳尖", "EarRoot_L", 630, "ear_L_tip", "into ear_face +12px", "tip dense", "tip high", ellipse_shape(p["ear_L_tip"], 35, 38))
    add("ear_root_R", "右耳根", "Head", 611, "ear_R_base", "under ear face/head fur", "root wedge", "root active", ellipse_shape(p["ear_R_base"], 42, 35))
    add("ear_face_R", "右耳面", "EarRoot_R", 621, "ear_R_base", "over root", "triangle surface", "low bend", poly_shape([(p["ear_R_base"][0]-48, p["ear_R_base"][1]+28), p["ear_R_tip"], (p["ear_R_base"][0]+38, p["ear_R_base"][1]+25)]))
    add("ear_tip_R", "右耳尖", "EarRoot_R", 631, "ear_R_tip", "into ear_face +12px", "tip dense", "tip high", ellipse_shape(p["ear_R_tip"], 35, 38))

    if not back:
        add("muzzle_base", "口鼻底", "Head", 530, "muzzle", "under whisker roots and jaw", "mouth curve dense", "low expression", ellipse_shape(p["muzzle"], 64, 46))
        add("jaw_line", "下颌/微笑线", "Muzzle", 540, "muzzle", "over muzzle", "curve points", "none", line_shape([(p["muzzle"][0]-38, p["muzzle"][1]+22), (p["muzzle"][0], p["muzzle"][1]+38), (p["muzzle"][0]+38, p["muzzle"][1]+22)], 10))
        add("cheek_fur_L", "左脸颊毛", "Head", 560, "skull", "over head/neck", "fur tips dense", "fur lag", ellipse_shape((p["skull"][0]+75, p["skull"][1]+48), 70, 65))
        add("cheek_fur_R", "右脸颊毛", "Head", 561, "skull", "over head/neck", "fur tips dense", "fur lag", ellipse_shape((p["skull"][0]-75, p["skull"][1]+48), 70, 65))
        visible_eye_sides = ("L",) if side else ("L", "R")
        for side_id in visible_eye_sides:
            eye = p[f"eye_{side_id}"]
            add(f"eye_socket_{side_id}", f"{side_id} 眼眶底/遮罩", "Head", 690 if side_id == "L" else 691, f"eye_{side_id}", "under iris and lids", "socket ellipse dense", "none", ellipse_shape(eye, 34, 42))
            add(f"iris_{side_id}", f"{side_id} 虹膜", f"EyeSocket_{side_id}", 700 if side_id == "L" else 701, f"eye_{side_id}", "clipped by socket", "radial", "gaze active", ellipse_shape(eye, 22, 28))
            add(f"pupil_{side_id}", f"{side_id} 瞳孔", f"Iris_{side_id}", 705 if side_id == "L" else 706, f"eye_{side_id}", "inside iris", "radial", "pupil scale", ellipse_shape(eye, 10, 18))
            add(f"highlight_{side_id}", f"{side_id} 高光", f"Iris_{side_id}", 710 if side_id == "L" else 711, f"eye_{side_id}", "inside iris", "small quad", "highlight parallax", ellipse_shape((eye[0]-8, eye[1]-13), 7, 7))
            add(f"upper_lid_{side_id}", f"{side_id} 上眼睑", f"EyeSocket_{side_id}", 720 if side_id == "L" else 722, f"eye_{side_id}", "over iris", "lid arc dense", "blink active", line_shape([(eye[0]-33, eye[1]-19), (eye[0], eye[1]-32), (eye[0]+33, eye[1]-19)], 12))
            add(f"lower_lid_{side_id}", f"{side_id} 下眼睑", f"EyeSocket_{side_id}", 721 if side_id == "L" else 723, f"eye_{side_id}", "over iris", "lid arc dense", "blink small", line_shape([(eye[0]-29, eye[1]+20), (eye[0], eye[1]+30), (eye[0]+29, eye[1]+20)], 8))
        add("whisker_L", "左胡须束", "Muzzle", 760, "muzzle", "root under muzzle", "spline endpoints", "tip high", line_shape([(p["muzzle"][0]+18, p["muzzle"][1]), (p["muzzle"][0]+95, p["muzzle"][1]-18), (p["muzzle"][0]+155, p["muzzle"][1]-4)], 5), line_shape([(p["muzzle"][0]+18, p["muzzle"][1]+10), (p["muzzle"][0]+100, p["muzzle"][1]+16), (p["muzzle"][0]+160, p["muzzle"][1]+38)], 5))
        add("whisker_R", "右胡须束", "Muzzle", 761, "muzzle", "root under muzzle", "spline endpoints", "tip high", line_shape([(p["muzzle"][0]-18, p["muzzle"][1]), (p["muzzle"][0]-95, p["muzzle"][1]-18), (p["muzzle"][0]-155, p["muzzle"][1]-4)], 5), line_shape([(p["muzzle"][0]-18, p["muzzle"][1]+10), (p["muzzle"][0]-100, p["muzzle"][1]+16), (p["muzzle"][0]-160, p["muzzle"][1]+38)], 5))

    return layers


def all_layers() -> list[LayerDef]:
    layers: list[LayerDef] = []
    for view in ("front", "side", "back"):
        layers.extend(build_layers_for_view(view))
    return layers


def draw_shape(draw: ImageDraw.ImageDraw, shape: Shape, fill: int, outline: tuple[int, int, int, int] | None = None, width: int = 2) -> None:
    if shape.kind == "ellipse":
        (cx, cy), rx, ry = shape.args
        box = [cx - rx, cy - ry, cx + rx, cy + ry]
        if outline:
            draw.ellipse(box, fill=fill, outline=outline, width=width)
        else:
            draw.ellipse(box, fill=fill)
    elif shape.kind == "poly":
        (points,) = shape.args
        if outline:
            draw.polygon(points, fill=fill, outline=outline)
            draw.line(list(points) + [points[0]], fill=outline, width=width)
        else:
            draw.polygon(points, fill=fill)
    elif shape.kind == "line":
        points, line_width = shape.args
        draw.line(points, fill=fill if outline is None else outline, width=line_width if outline is None else max(width, line_width), joint="curve")


def layer_mask(size: tuple[int, int], layer: LayerDef) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for shape in layer.shapes:
        draw_shape(draw, shape, 255)
    return mask


def remove_white_background(rgba: Image.Image, mask: Image.Image) -> Image.Image:
    out = rgba.copy()
    pix = out.load()
    mp = mask.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pix[x, y]
            if mp[x, y] == 0 or (r > 245 and g > 245 and b > 245):
                pix[x, y] = (r, g, b, 0)
            else:
                pix[x, y] = (r, g, b, min(a, mp[x, y]))
    return out


def save_layer_image(src: Image.Image, layer: LayerDef) -> dict[str, object]:
    mask = layer_mask(src.size, layer)
    mask_bbox = mask.getbbox()
    out_name = f"{layer.view}_{layer.layer_id}.png"
    out_path = LAYER_DIR / out_name
    bbox = None
    cropped = None
    if mask_bbox:
        masked = remove_white_background(src.crop(mask_bbox).convert("RGBA"), mask.crop(mask_bbox))
        local_bbox = masked.getbbox()
        if local_bbox:
            cropped = masked.crop(local_bbox)
            bbox = (
                mask_bbox[0] + local_bbox[0],
                mask_bbox[1] + local_bbox[1],
                mask_bbox[0] + local_bbox[2],
                mask_bbox[1] + local_bbox[3],
            )
    if bbox and cropped:
        cropped.save(out_path)
        bounds = [int(v) for v in bbox]
        size = [cropped.width, cropped.height]
        extraction = "source-mask"
        alpha_histogram = cropped.getchannel("A").histogram()
        alpha_pixel_count = cropped.width * cropped.height - alpha_histogram[0]
    else:
        placeholder = Image.new("RGBA", (120, 90), (0, 0, 0, 0))
        d = ImageDraw.Draw(placeholder, "RGBA")
        if "paw" in layer.layer_id:
            d.ellipse([20, 26, 100, 72], fill=(244, 205, 154, 235), outline=(168, 118, 70, 235), width=3)
            for tx in (42, 60, 78):
                d.ellipse([tx - 7, 34, tx + 7, 48], fill=(223, 136, 106, 230))
        elif "whisker" in layer.layer_id or "jaw_line" in layer.layer_id:
            d.line([(14, 46), (60, 35), (106, 43)], fill=(190, 126, 62, 235), width=4)
            d.line([(14, 56), (62, 58), (106, 66)], fill=(190, 126, 62, 225), width=4)
        else:
            d.ellipse([24, 18, 96, 72], fill=(226, 142, 42, 235), outline=(148, 82, 32, 235), width=3)
        placeholder.save(out_path)
        bounds = []
        size = [placeholder.width, placeholder.height]
        extraction = "hidden-fill-placeholder"
        alpha_pixel_count = 0
    return {
        "view": layer.view,
        "id": layer.layer_id,
        "name": layer.name,
        "file": f"live2d/x5/actual-layer-candidates/{out_name}",
        "bounds": bounds,
        "size": size,
        "parent": layer.parent,
        "drawOrder": layer.draw_order,
        "pivot": layer.pivot,
        "hiddenOverlap": layer.hidden_overlap,
        "meshDensityZone": layer.mesh_zone,
        "elastic": layer.elastic,
        "extraction": extraction,
        "alphaPixelCount": alpha_pixel_count,
        "qaFlag": "tiny-source-fragment" if extraction == "source-mask" and alpha_pixel_count < 100 else None,
        "candidateOnly": True,
    }


def checker(size: tuple[int, int], block: int = 10) -> Image.Image:
    img = Image.new("RGB", size, (245, 245, 245))
    draw = ImageDraw.Draw(img)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle([x, y, x + block - 1, y + block - 1], fill=(225, 225, 225))
    return img


def make_boundary_preview(src: Image.Image, layers: list[LayerDef]) -> None:
    img = src.convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    for i, layer in enumerate(layers):
        color = COLORS[i % len(COLORS)]
        for shape in layer.shapes:
            draw_shape(draw, shape, 0, color, 3)
        if i % 5 == 0:
            first = layer.shapes[0]
            if first.kind == "ellipse":
                (cx, cy), _, _ = first.args
            elif first.kind == "poly":
                pts = first.args[0]
                cx = sum(x for x, _ in pts) // len(pts)
                cy = sum(y for _, y in pts) // len(pts)
            else:
                pts = first.args[0]
                cx, cy = pts[0]
            draw.rounded_rectangle([cx + 5, cy - 18, cx + 122, cy + 6], radius=4, fill=(255, 255, 255, 220), outline=color, width=1)
            draw.text((cx + 10, cy - 17), f"{layer.view}:{layer.layer_id[:12]}", font=font(12), fill=color)
    header = Image.new("RGBA", (img.width, img.height + 86), (250, 250, 247, 255))
    header.alpha_composite(img, (0, 86))
    d = ImageDraw.Draw(header, "RGBA")
    d.rounded_rectangle([24, 14, img.width - 24, 70], radius=8, fill=(255, 252, 246, 246), outline=(120, 135, 120, 220), width=2)
    d.text((48, 26), "X5 实际小橘透明层候选：边界预览（按三视图分层）", font=font(28), fill=(34, 38, 44, 255))
    header.convert("RGB").save(BOUNDARY)


def fit_preview(path: Path, max_w: int, max_h: int) -> Image.Image:
    img = Image.open(path).convert("RGBA")
    bg = checker((max_w, max_h), 8).convert("RGBA")
    scale = min(max_w / img.width, max_h / img.height, 1.0)
    resized = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.Resampling.LANCZOS)
    bg.alpha_composite(resized, ((max_w - resized.width) // 2, (max_h - resized.height) // 2))
    return bg.convert("RGB")


def make_atlas(records: list[dict[str, object]]) -> None:
    cell_w, cell_h = 188, 154
    cols = 8
    rows = math.ceil(len(records) / cols)
    header = 112
    img = Image.new("RGB", (cols * cell_w + 40, rows * cell_h + header + 40), (250, 250, 247))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([20, 16, img.width - 20, 90], radius=8, fill=(255, 252, 246), outline=(120, 135, 120), width=2)
    draw.text((44, 28), f"X5 实际小橘透明 PNG 分层候选 Atlas ({len(records)} layers)", font=font(28), fill=(34, 38, 44))
    draw.text((44, 62), "每格是一个真实透明 PNG 候选层；用于审核边界/隐藏补全/后续三角剖分，不是 PSD 或 Cubism 输出。", font=font(16), fill=(112, 82, 54))
    for i, record in enumerate(records):
        col = i % cols
        row = i // cols
        x = 20 + col * cell_w
        y = header + row * cell_h
        draw.rounded_rectangle([x + 6, y + 4, x + cell_w - 6, y + cell_h - 8], radius=6, fill=(255, 255, 255), outline=(176, 176, 160), width=1)
        preview = fit_preview(ROOT.parent.parent / record["file"], cell_w - 24, 98)
        img.paste(preview, (x + 12, y + 10))
        label = f"{record['view']}:{record['id']}"
        draw.text((x + 12, y + 112), label[:24], font=font(12), fill=(38, 45, 52))
        draw.text((x + 12, y + 132), f"draw {record['drawOrder']} -> {record['parent']}"[:28], font=font(10), fill=(92, 88, 78))
    img.save(ATLAS)


VIEW_BOUNDS = {
    "front": (0, 0, 650, 887),
    "side": (650, 0, 1120, 887),
    "back": (1120, 0, 1774, 887),
}


def make_reconstruction_coverage(src: Image.Image, records: list[dict[str, object]]) -> dict[str, object]:
    union = Image.new("L", src.size, 0)
    for record in records:
        if record["extraction"] != "source-mask":
            continue
        x0, y0, x1, y1 = record["bounds"]
        layer_img = Image.open(ROOT.parent.parent / record["file"]).convert("RGBA")
        placed = Image.new("L", src.size, 0)
        placed.paste(layer_img.getchannel("A"), (x0, y0))
        union = ImageChops.lighter(union, placed)

    rgba = src.convert("RGBA")
    reconstruction = rgba.copy()
    reconstruction.putalpha(union)
    body_mask = Image.new("L", src.size, 0)
    body_pixels = body_mask.load()
    source_pixels = src.load()
    for y in range(src.height):
        for x in range(src.width):
            r, g, b = source_pixels[x, y]
            if r < 245 or g < 245 or b < 245:
                body_pixels[x, y] = 255
    missing = ImageChops.subtract(body_mask, union)

    metrics: dict[str, object] = {}
    for view, bounds in VIEW_BOUNDS.items():
        body_crop = body_mask.crop(bounds)
        union_crop = ImageChops.multiply(union.crop(bounds), body_crop)
        body_count = body_crop.width * body_crop.height - body_crop.histogram()[0]
        covered_count = union_crop.width * union_crop.height - union_crop.histogram()[0]
        metrics[view] = {
            "visibleSourcePixels": body_count,
            "coveredVisiblePixels": covered_count,
            "coverageRatio": round(covered_count / body_count, 4) if body_count else 0.0,
        }

    panel_w, panel_h = 560, 280
    sheet = Image.new("RGB", (panel_w * 3 + 80, panel_h * 3 + 170), (250, 250, 247))
    draw = ImageDraw.Draw(sheet)
    draw.rounded_rectangle([20, 16, sheet.width - 20, 96], radius=8, fill=(255, 252, 246), outline=(120, 135, 120), width=2)
    draw.text((44, 28), "X5 实际小橘分层重组覆盖核验", font=font(28), fill=(34, 38, 44))
    draw.text((44, 64), "原图 / 透明层覆盖重组 / 红色未覆盖区；只是 X5 QA，不是 PSD 或 Cubism。", font=font(16), fill=(112, 82, 54))
    titles = ("原图视图", "分层覆盖重组", "未覆盖可见像素")
    for col, title in enumerate(titles):
        draw.text((40 + col * panel_w, 116), title, font=font(18), fill=(45, 52, 58))
    for row, (view, bounds) in enumerate(VIEW_BOUNDS.items()):
        original_crop = src.crop(bounds).convert("RGBA")
        reconstruction_crop = reconstruction.crop(bounds)
        missing_crop = missing.crop(bounds)
        missing_overlay = original_crop.copy()
        red = Image.new("RGBA", original_crop.size, (225, 48, 48, 185))
        missing_overlay = Image.composite(red, missing_overlay, missing_crop)
        panels = (original_crop, reconstruction_crop, missing_overlay)
        for col, panel in enumerate(panels):
            bg = checker((panel_w - 20, panel_h - 20), 10).convert("RGBA")
            scale = min((panel_w - 28) / panel.width, (panel_h - 28) / panel.height)
            resized = panel.resize((max(1, int(panel.width * scale)), max(1, int(panel.height * scale))), Image.Resampling.LANCZOS)
            bg.alpha_composite(resized, ((bg.width - resized.width) // 2, (bg.height - resized.height) // 2))
            sheet.paste(bg.convert("RGB"), (40 + col * panel_w, 150 + row * panel_h))
        ratio = metrics[view]["coverageRatio"]
        draw.text((48, 154 + row * panel_h), f"{view}  coverage={ratio:.2%}", font=font(14), fill=(35, 80, 55))
    sheet.save(RECONSTRUCTION)
    return metrics


def write_contract(records: list[dict[str, object]], coverage: dict[str, object]) -> None:
    by_view = {view: len([r for r in records if r["view"] == view]) for view in ("front", "side", "back")}
    data = {
        "schemaVersion": 1,
        "stage": "X5-actual-xiaoju-transparent-layer-split-candidates",
        "status": "candidate-for-user-review",
        "revision": "layer-split-v2-reconstruction-coverage-qa",
        "sourceImage": "live2d/x5/qa/x5-actual-xiaoju-spread-pose-three-view.png",
        "articleProcessMapping": [
            "independent transparent PNG layer candidates",
            "one semantic visual unit per future ArtMesh",
            "layer boundary first, then triangulation/helper mesh points",
            "each layer owns one primary controller; helper points remain mesh vertices",
        ],
        "gateBoundary": {
            "currentGate": "x5-layer-mesh-node-torque",
            "candidateOnly": True,
            "x5MayPassOnlyWithUserApproval": True,
            "x6Authorized": False,
            "notProduced": ["PSD", "Cubism ArtMesh", "Deformer", "Action Tracer", "runtime replacement"],
        },
        "counts": {
            "totalLayerPngs": len(records),
            "byView": by_view,
        },
        "qa": {
            "transparentLayerAtlas": "live2d/x5/qa/x5-actual-xiaoju-transparent-layer-atlas.png",
            "boundaryPreview": "live2d/x5/qa/x5-actual-xiaoju-layer-boundary-preview.png",
            "reconstructionCoverage": "live2d/x5/qa/x5-actual-xiaoju-layer-reconstruction-coverage.png",
            "layerDirectory": "live2d/x5/actual-layer-candidates",
            "coverageByView": coverage,
            "hiddenFillPlaceholderCount": len([r for r in records if r["extraction"] == "hidden-fill-placeholder"]),
            "tinySourceFragmentCount": len([r for r in records if r["qaFlag"] == "tiny-source-fragment"]),
        },
        "layers": records,
        "knownRisks": [
            "Source is a generated spread-pose review image with a white background; alpha extraction is mask-based and must be repainted before final PSD.",
            "Hidden texture under occluded joints is declared and previewed, but this script cannot create final paint-quality fur reconstruction.",
            "Back-view face/eye layers are intentionally omitted because they are not visible in the back projection.",
            "This refines X4/X5 layer candidates only and does not authorize X6.",
        ],
    }
    CONTRACT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    LAYER_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    src = Image.open(SRC).convert("RGB")
    layers = all_layers()
    records = [save_layer_image(src, layer) for layer in layers]
    make_boundary_preview(src, layers)
    make_atlas(records)
    coverage = make_reconstruction_coverage(src, records)
    write_contract(records, coverage)
    for path in (ATLAS, BOUNDARY, RECONSTRUCTION, CONTRACT, LAYER_DIR):
        print(path.as_posix())
    print(f"layers={len(records)}")


if __name__ == "__main__":
    main()
