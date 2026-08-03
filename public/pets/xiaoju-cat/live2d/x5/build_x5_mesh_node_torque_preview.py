from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
LIVE2D = ROOT.parent
QA_DIR = ROOT / "qa"
ATLAS = QA_DIR / "x5-detailed-layer-atlas.png"
MESH = QA_DIR / "x5-triangulation-moment-preview.png"
ELASTIC = QA_DIR / "x5-link-elastic-preview.png"
CONTRACT = ROOT / "x5-layer-mesh-node-torque-contract.json"
REVIEW = ROOT / "X5-USER-VISUAL-REVIEW.md"
QA_JSON = ROOT / "x5-self-review.json"


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
    "bg": (250, 250, 246),
    "paper": (255, 248, 235),
    "ink": (44, 40, 34),
    "muted": (86, 82, 74),
    "line": (112, 76, 34),
    "fur": (248, 153, 35),
    "fur2": (255, 184, 70),
    "soft": (113, 190, 178),
    "hidden": (74, 178, 122),
    "blue": (34, 105, 220),
    "magenta": (214, 58, 178),
    "eye": (255, 226, 158),
    "planet": (132, 194, 225),
    "mesh": (74, 99, 124),
    "primary": (20, 92, 214),
    "secondary": (232, 118, 32),
    "elastic": (34, 150, 106),
}


DETAILED_LAYERS: list[dict[str, object]] = [
    # Planet and contact.
    {"id": "planet_back", "name": "星球后层", "parent": "PlanetRoot", "pivot": "planet_center", "draw": 10, "density": "low, rim points", "overlap": "behind Xiaoju", "elastic": "none"},
    {"id": "planet_surface", "name": "星球主体表面", "parent": "PlanetBody", "pivot": "planet_center", "draw": 20, "density": "medium at contact band", "overlap": "under contact shadow", "elastic": "low float"},
    {"id": "contact_shadow", "name": "胸腹接触阴影", "parent": "PlanetBody", "pivot": "contact_band", "draw": 840, "density": "soft contact strip", "overlap": "clips planet surface", "elastic": "contact squash only"},
    {"id": "planet_front", "name": "星球前景边缘", "parent": "PlanetRoot", "pivot": "planet_center", "draw": 900, "density": "rim/control corners", "overlap": "occludes paws/body only", "elastic": "low float"},
    # Body masses.
    {"id": "tail_root_socket", "name": "尾根插口毛皮", "parent": "Pelvis", "pivot": "tail_root", "draw": 88, "density": "dense at socket", "overlap": "under tail_base", "elastic": "soft socket"},
    {"id": "tail_base", "name": "尾根段", "parent": "TailRoot", "pivot": "tail_root", "draw": 90, "density": "bend fan", "overlap": "into pelvis and tail_mid", "elastic": "root active"},
    {"id": "tail_mid", "name": "尾中段", "parent": "TailMid", "pivot": "tail_mid_1", "draw": 95, "density": "two bend bands", "overlap": "into tail_base/tip", "elastic": "medium lag"},
    {"id": "tail_tip", "name": "尾尖段", "parent": "TailTip", "pivot": "tail_mid_2", "draw": 100, "density": "tip fan", "overlap": "into tail_mid", "elastic": "high lag"},
    {"id": "hind_thigh_L", "name": "左大腿/髋包络", "parent": "Hip_L", "pivot": "hip_L", "draw": 145, "density": "hip and knee bands", "overlap": "under pelvis", "elastic": "soft thigh"},
    {"id": "hind_shin_L", "name": "左小腿/跗", "parent": "Knee_L", "pivot": "knee_L", "draw": 146, "density": "knee/hock dense", "overlap": "under thigh/paw", "elastic": "low"},
    {"id": "hind_paw_L", "name": "左后爪", "parent": "Hock_L", "pivot": "hindpaw_L", "draw": 147, "density": "toe arcs", "overlap": "into shin", "elastic": "toe soft"},
    {"id": "hind_thigh_R", "name": "右大腿/髋包络", "parent": "Hip_R", "pivot": "hip_R", "draw": 155, "density": "hip and knee bands", "overlap": "under pelvis", "elastic": "soft thigh"},
    {"id": "hind_shin_R", "name": "右小腿/跗", "parent": "Knee_R", "pivot": "knee_R", "draw": 156, "density": "knee/hock dense", "overlap": "under thigh/paw", "elastic": "low"},
    {"id": "hind_paw_R", "name": "右后爪", "parent": "Hock_R", "pivot": "hindpaw_R", "draw": 157, "density": "toe arcs", "overlap": "into shin", "elastic": "toe soft"},
    {"id": "pelvis", "name": "骨盆/臀部", "parent": "BodyRoot", "pivot": "pelvis_center", "draw": 210, "density": "medium oval", "overlap": "under abdomen/hips/tail", "elastic": "stable mass"},
    {"id": "abdomen", "name": "腹部软层", "parent": "BodyRoot", "pivot": "abdomen_center", "draw": 220, "density": "breath grid", "overlap": "under ribcage/pelvis", "elastic": "breath/settle"},
    {"id": "ribcage", "name": "胸腔/躯干", "parent": "BodyRoot", "pivot": "ribcage_center", "draw": 230, "density": "shoulder/contact dense", "overlap": "under neck/forelimbs", "elastic": "breath small"},
    {"id": "chest_fur", "name": "胸毛覆盖片", "parent": "Ribcage", "pivot": "neck_base", "draw": 300, "density": "fur tips dense", "overlap": "over chest/neck", "elastic": "fur lag"},
    {"id": "neck_fill", "name": "颈部隐藏补全", "parent": "Neck", "pivot": "neck_base", "draw": 310, "density": "head-neck seam", "overlap": "under head", "elastic": "low stretch"},
    # Forelimbs.
    {"id": "scapula_fur_L", "name": "左肩胛遮挡毛", "parent": "Scapula_L", "pivot": "scapula_L", "draw": 340, "density": "armpit seam", "overlap": "over ribcage/upper arm", "elastic": "armpit shear"},
    {"id": "upper_arm_L", "name": "左上臂", "parent": "Shoulder_L", "pivot": "shoulder_L", "draw": 350, "density": "shoulder/elbow dense", "overlap": "under scapula/forearm", "elastic": "low"},
    {"id": "forearm_L", "name": "左前臂", "parent": "Elbow_L", "pivot": "elbow_L", "draw": 360, "density": "elbow/wrist dense", "overlap": "under upper_arm/paw", "elastic": "sleeve soft"},
    {"id": "wrist_fur_L", "name": "左腕毛", "parent": "Wrist_L", "pivot": "wrist_L", "draw": 370, "density": "small fan", "overlap": "over wrist seam", "elastic": "soft"},
    {"id": "fore_paw_L", "name": "左前爪", "parent": "Wrist_L", "pivot": "forepaw_L", "draw": 380, "density": "toe/contact arc", "overlap": "into wrist", "elastic": "toe soft"},
    {"id": "scapula_fur_R", "name": "右肩胛遮挡毛", "parent": "Scapula_R", "pivot": "scapula_R", "draw": 341, "density": "armpit seam", "overlap": "over ribcage/upper arm", "elastic": "armpit shear"},
    {"id": "upper_arm_R", "name": "右上臂", "parent": "Shoulder_R", "pivot": "shoulder_R", "draw": 351, "density": "shoulder/elbow dense", "overlap": "under scapula/forearm", "elastic": "low"},
    {"id": "forearm_R", "name": "右前臂", "parent": "Elbow_R", "pivot": "elbow_R", "draw": 361, "density": "elbow/wrist dense", "overlap": "under upper_arm/paw", "elastic": "sleeve soft"},
    {"id": "wrist_fur_R", "name": "右腕毛", "parent": "Wrist_R", "pivot": "wrist_R", "draw": 371, "density": "small fan", "overlap": "over wrist seam", "elastic": "soft"},
    {"id": "fore_paw_R", "name": "右前爪", "parent": "Wrist_R", "pivot": "forepaw_R", "draw": 381, "density": "toe/contact arc", "overlap": "into wrist", "elastic": "toe soft"},
    # Head, ears, face.
    {"id": "head_base", "name": "头骨/脸底", "parent": "Neck", "pivot": "skull_center", "draw": 500, "density": "face oval medium", "overlap": "under ears/eyes/muzzle", "elastic": "stable mass"},
    {"id": "muzzle_base", "name": "口鼻底", "parent": "Head", "pivot": "jaw_center", "draw": 530, "density": "mouth curve dense", "overlap": "under whisker roots", "elastic": "low expression"},
    {"id": "jaw_line", "name": "下颌/微笑线", "parent": "Muzzle", "pivot": "jaw_center", "draw": 540, "density": "curve points", "overlap": "over muzzle", "elastic": "none"},
    {"id": "cheek_fur_L", "name": "左脸颊毛", "parent": "Head", "pivot": "jaw_center", "draw": 560, "density": "fur tips dense", "overlap": "over head/neck", "elastic": "fur lag"},
    {"id": "cheek_fur_R", "name": "右脸颊毛", "parent": "Head", "pivot": "jaw_center", "draw": 561, "density": "fur tips dense", "overlap": "over head/neck", "elastic": "fur lag"},
    {"id": "ear_root_L", "name": "左耳根", "parent": "Head", "pivot": "ear_base_L", "draw": 610, "density": "root wedge", "overlap": "under ear face/head fur", "elastic": "root active"},
    {"id": "ear_face_L", "name": "左耳面", "parent": "EarRoot_L", "pivot": "ear_base_L", "draw": 620, "density": "triangle surface", "overlap": "over root", "elastic": "low bend"},
    {"id": "ear_tip_L", "name": "左耳尖", "parent": "EarRoot_L", "pivot": "ear_tip_L", "draw": 630, "density": "tip dense", "overlap": "into ear face", "elastic": "tip high"},
    {"id": "ear_root_R", "name": "右耳根", "parent": "Head", "pivot": "ear_base_R", "draw": 611, "density": "root wedge", "overlap": "under ear face/head fur", "elastic": "root active"},
    {"id": "ear_face_R", "name": "右耳面", "parent": "EarRoot_R", "pivot": "ear_base_R", "draw": 621, "density": "triangle surface", "overlap": "over root", "elastic": "low bend"},
    {"id": "ear_tip_R", "name": "右耳尖", "parent": "EarRoot_R", "pivot": "ear_tip_R", "draw": 631, "density": "tip dense", "overlap": "into ear face", "elastic": "tip high"},
    # Eyes split.
    {"id": "eye_socket_L", "name": "左眼眶底/遮罩", "parent": "Head", "pivot": "eye_socket_L", "draw": 690, "density": "socket ellipse dense", "overlap": "under iris/lids", "elastic": "none"},
    {"id": "iris_L", "name": "左虹膜", "parent": "EyeSocket_L", "pivot": "eye_center_L", "draw": 700, "density": "round radial", "overlap": "clipped by socket", "elastic": "gaze active"},
    {"id": "pupil_L", "name": "左瞳孔", "parent": "Iris_L", "pivot": "eye_center_L", "draw": 705, "density": "round radial", "overlap": "inside iris", "elastic": "pupil scale"},
    {"id": "highlight_L", "name": "左高光", "parent": "Iris_L", "pivot": "eye_center_L", "draw": 710, "density": "small quad", "overlap": "inside iris", "elastic": "highlight parallax"},
    {"id": "upper_lid_L", "name": "左上眼睑", "parent": "EyeSocket_L", "pivot": "eye_socket_L", "draw": 720, "density": "lid arc dense", "overlap": "over iris", "elastic": "blink active"},
    {"id": "lower_lid_L", "name": "左下眼睑", "parent": "EyeSocket_L", "pivot": "eye_socket_L", "draw": 721, "density": "lid arc dense", "overlap": "over iris", "elastic": "blink small"},
    {"id": "eye_socket_R", "name": "右眼眶底/遮罩", "parent": "Head", "pivot": "eye_socket_R", "draw": 691, "density": "socket ellipse dense", "overlap": "under iris/lids", "elastic": "none"},
    {"id": "iris_R", "name": "右虹膜", "parent": "EyeSocket_R", "pivot": "eye_center_R", "draw": 701, "density": "round radial", "overlap": "clipped by socket", "elastic": "gaze active"},
    {"id": "pupil_R", "name": "右瞳孔", "parent": "Iris_R", "pivot": "eye_center_R", "draw": 706, "density": "round radial", "overlap": "inside iris", "elastic": "pupil scale"},
    {"id": "highlight_R", "name": "右高光", "parent": "Iris_R", "pivot": "eye_center_R", "draw": 711, "density": "small quad", "overlap": "inside iris", "elastic": "highlight parallax"},
    {"id": "upper_lid_R", "name": "右上眼睑", "parent": "EyeSocket_R", "pivot": "eye_socket_R", "draw": 722, "density": "lid arc dense", "overlap": "over iris", "elastic": "blink active"},
    {"id": "lower_lid_R", "name": "右下眼睑", "parent": "EyeSocket_R", "pivot": "eye_socket_R", "draw": 723, "density": "lid arc dense", "overlap": "over iris", "elastic": "blink small"},
    {"id": "whisker_L", "name": "左胡须束", "parent": "Muzzle", "pivot": "whisker_root_L", "draw": 760, "density": "spline endpoints", "overlap": "root under muzzle", "elastic": "tip high"},
    {"id": "whisker_R", "name": "右胡须束", "parent": "Muzzle", "pivot": "whisker_root_R", "draw": 761, "density": "spline endpoints", "overlap": "root under muzzle", "elastic": "tip high"},
]


MOMENT_ANCHORS = [
    {"id": "M0_body_support", "kind": "primary", "pivot": "ribcage_center", "force": "planet normal + gravity", "drives": ["ribcage", "abdomen", "contact_shadow"], "note": "support reaction; keeps COM inside planet support"},
    {"id": "M1_shoulder_L", "kind": "primary", "pivot": "shoulder_L", "force": "forepaw lift/contact", "drives": ["upper_arm_L", "forearm_L", "fore_paw_L"], "note": "tau = r x F / J^T F sign mirrors right"},
    {"id": "M1_shoulder_R", "kind": "primary", "pivot": "shoulder_R", "force": "forepaw lift/contact", "drives": ["upper_arm_R", "forearm_R", "fore_paw_R"], "note": "mirror of left shoulder"},
    {"id": "M2_elbow_L", "kind": "primary", "pivot": "elbow_L", "force": "distal forearm/paw load", "drives": ["forearm_L", "wrist_fur_L"], "note": "large active cover bend"},
    {"id": "M2_elbow_R", "kind": "primary", "pivot": "elbow_R", "force": "distal forearm/paw load", "drives": ["forearm_R", "wrist_fur_R"], "note": "large active cover bend"},
    {"id": "M3_wrist_L", "kind": "primary", "pivot": "wrist_L", "force": "paw face contact", "drives": ["fore_paw_L"], "note": "face contact clamp and paw orientation"},
    {"id": "M3_wrist_R", "kind": "primary", "pivot": "wrist_R", "force": "paw face contact", "drives": ["fore_paw_R"], "note": "face contact clamp and paw orientation"},
    {"id": "S1_neck_fur", "kind": "secondary", "pivot": "neck_base", "force": "head velocity", "drives": ["neck_fill", "chest_fur", "cheek_fur_L", "cheek_fur_R"], "note": "spring-damper fur bridge"},
    {"id": "S2_ear_L", "kind": "secondary", "pivot": "ear_base_L", "force": "head angular velocity + attention", "drives": ["ear_face_L", "ear_tip_L"], "note": "ear tip higher elasticity"},
    {"id": "S2_ear_R", "kind": "secondary", "pivot": "ear_base_R", "force": "head angular velocity + attention", "drives": ["ear_face_R", "ear_tip_R"], "note": "ear tip higher elasticity"},
    {"id": "S3_tail", "kind": "secondary", "pivot": "tail_root", "force": "tail-root active target", "drives": ["tail_mid", "tail_tip"], "note": "root active, continuation elastic"},
    {"id": "S4_whiskers", "kind": "secondary", "pivot": "whisker_root", "force": "head/muzzle velocity", "drives": ["whisker_L", "whisker_R"], "note": "stable roots, light tips"},
    {"id": "S5_belly", "kind": "secondary", "pivot": "abdomen_center", "force": "breath + body settle", "drives": ["abdomen", "chest_fur"], "note": "no whole-body scale"},
]


ELASTIC_CHAINS = [
    {"chain": "EarTip_L/R", "input": "ParamHeadAngle + ParamEarAttention", "output": "ParamEarTipLagL/R", "stiffness": 0.72, "damping": 0.78, "clamp": "±7 deg", "settle": "180-260 ms"},
    {"chain": "TailMid/Tip", "input": "ParamTailRoot", "output": "ParamTailFollow1/2", "stiffness": 0.48, "damping": 0.68, "clamp": "±14 deg", "settle": "360-520 ms"},
    {"chain": "Cheek/ChestFur", "input": "Head/Body velocity", "output": "ParamFurLag", "stiffness": 0.58, "damping": 0.82, "clamp": "±5 px", "settle": "140-220 ms"},
    {"chain": "WhiskerTips", "input": "Muzzle velocity", "output": "ParamWhiskerLag", "stiffness": 0.42, "damping": 0.74, "clamp": "±9 px", "settle": "220-340 ms"},
    {"chain": "BellyBreath", "input": "ParamBreath + settle", "output": "ParamBellySoft", "stiffness": 0.64, "damping": 0.86, "clamp": "±4 px", "settle": "continuous"},
    {"chain": "ForelimbSleeves", "input": "ParamCover + joint velocity", "output": "ParamSleeveShearL/R", "stiffness": 0.78, "damping": 0.9, "clamp": "±6 px", "settle": "120-180 ms"},
]


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], s: str, size: int, fill=COL["ink"]) -> None:
    draw.text(xy, s, font=font(size), fill=fill)


def ellipse(draw: ImageDraw.ImageDraw, cx: int, cy: int, rx: int, ry: int, fill, outline=COL["line"], width: int = 3) -> None:
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill, outline=outline, width=width)


def line(draw: ImageDraw.ImageDraw, pts: list[tuple[int, int]], fill=COL["line"], width: int = 4) -> None:
    draw.line(pts, fill=fill, width=width, joint="curve")


def poly(draw: ImageDraw.ImageDraw, pts: list[tuple[int, int]], fill, outline=COL["line"], width: int = 2) -> None:
    draw.polygon(pts, fill=fill, outline=outline)
    draw.line(pts + [pts[0]], fill=outline, width=width)


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], fill, width: int = 4) -> None:
    line(draw, [start, end], fill, width)
    ang = math.atan2(end[1] - start[1], end[0] - start[0])
    for da in (2.55, -2.55):
        p = (int(end[0] + math.cos(ang + da) * 16), int(end[1] + math.sin(ang + da) * 16))
        line(draw, [end, p], fill, width)


def cat_points(ox: int, oy: int, s: float = 1.0) -> dict[str, tuple[int, int]]:
    def p(x: float, y: float) -> tuple[int, int]:
        return int(ox + x * s), int(oy + y * s)
    return {
        "skull_center": p(0, -180), "jaw_center": p(0, -94), "neck_base": p(0, -22),
        "ribcage_center": p(0, 54), "abdomen_center": p(0, 150), "pelvis_center": p(0, 220),
        "shoulder_L": p(-116, -10), "elbow_L": p(-220, 38), "wrist_L": p(-302, 122), "forepaw_L": p(-366, 190),
        "shoulder_R": p(116, -10), "elbow_R": p(220, 38), "wrist_R": p(302, 122), "forepaw_R": p(366, 190),
        "hip_L": p(-96, 214), "knee_L": p(-178, 318), "hock_L": p(-136, 430), "hindpaw_L": p(-214, 472),
        "hip_R": p(96, 214), "knee_R": p(178, 318), "hock_R": p(136, 430), "hindpaw_R": p(214, 472),
        "tail_root": p(46, 238), "tail_mid_1": p(184, 286), "tail_mid_2": p(298, 230), "tail_tip": p(268, 112),
        "ear_base_L": p(-88, -318), "ear_tip_L": p(-166, -448), "ear_base_R": p(88, -318), "ear_tip_R": p(166, -448),
        "eye_socket_L": p(-58, -206), "eye_center_L": p(-58, -206), "eye_socket_R": p(58, -206), "eye_center_R": p(58, -206),
        "whisker_root_L": p(-28, -130), "whisker_root_R": p(28, -130), "planet_center": p(0, 320), "contact_band": p(0, 250),
    }


def draw_cat_base(draw: ImageDraw.ImageDraw, ox: int, oy: int, s: float = 1.0, mesh: bool = False) -> dict[str, tuple[int, int]]:
    pts = cat_points(ox, oy, s)
    # Hidden fills behind visible anatomy.
    ellipse(draw, *pts["ribcage_center"], int(138 * s), int(150 * s), (74, 178, 122, 75), (64, 146, 110), 2)
    ellipse(draw, *pts["abdomen_center"], int(128 * s), int(132 * s), (74, 178, 122, 70), (64, 146, 110), 2)
    # Tail and limbs.
    line(draw, [pts["tail_root"], pts["tail_mid_1"], pts["tail_mid_2"], pts["tail_tip"]], COL["fur2"], int(24 * s))
    line(draw, [pts["tail_root"], pts["tail_mid_1"], pts["tail_mid_2"], pts["tail_tip"]], COL["line"], max(2, int(3 * s)))
    for side, color in (("L", COL["blue"]), ("R", COL["magenta"])):
        line(draw, [pts[f"shoulder_{side}"], pts[f"elbow_{side}"], pts[f"wrist_{side}"], pts[f"forepaw_{side}"]], color, int(15 * s))
        ellipse(draw, *pts[f"forepaw_{side}"], int(30 * s), int(20 * s), (255, 213, 151), COL["line"], 2)
        line(draw, [pts[f"hip_{side}"], pts[f"knee_{side}"], pts[f"hock_{side}"], pts[f"hindpaw_{side}"]], COL["fur2"], int(15 * s))
        ellipse(draw, *pts[f"hindpaw_{side}"], int(34 * s), int(18 * s), (255, 213, 151), COL["line"], 2)
    # Body.
    ellipse(draw, *pts["pelvis_center"], int(120 * s), int(116 * s), COL["fur"], COL["line"], 3)
    ellipse(draw, *pts["abdomen_center"], int(122 * s), int(144 * s), COL["fur2"], COL["line"], 3)
    ellipse(draw, *pts["ribcage_center"], int(136 * s), int(152 * s), COL["fur"], COL["line"], 3)
    poly(draw, [(pts["neck_base"][0] - int(92*s), pts["neck_base"][1] + int(8*s)), (pts["neck_base"][0], pts["neck_base"][1] - int(74*s)), (pts["neck_base"][0] + int(92*s), pts["neck_base"][1] + int(8*s)), (pts["neck_base"][0] + int(42*s), pts["neck_base"][1] + int(88*s)), (pts["neck_base"][0] - int(42*s), pts["neck_base"][1] + int(88*s))], (113, 190, 178, 190), (64, 146, 136), 2)
    ellipse(draw, *pts["skull_center"], int(146 * s), int(170 * s), COL["fur"], COL["line"], 3)
    poly(draw, [(pts["ear_base_L"][0]-int(20*s), pts["ear_base_L"][1]+int(10*s)), pts["ear_tip_L"], (pts["ear_base_L"][0]+int(54*s), pts["ear_base_L"][1]+int(28*s))], COL["fur"], COL["line"], 2)
    poly(draw, [(pts["ear_base_R"][0]+int(20*s), pts["ear_base_R"][1]+int(10*s)), pts["ear_tip_R"], (pts["ear_base_R"][0]-int(54*s), pts["ear_base_R"][1]+int(28*s))], COL["fur"], COL["line"], 2)
    for side in ("L", "R"):
        ellipse(draw, *pts[f"eye_socket_{side}"], int(34*s), int(42*s), COL["eye"], COL["line"], 2)
        ellipse(draw, *pts[f"eye_center_{side}"], int(12*s), int(22*s), (32, 30, 28), COL["line"], 1)
    for side, mul in (("L", -1), ("R", 1)):
        for k in (-1, 0, 1):
            line(draw, [pts[f"whisker_root_{side}"], (pts[f"whisker_root_{side}"][0] + int(mul*(106+10*k)*s), pts[f"whisker_root_{side}"][1] + int((k*16-4)*s))], COL["line"], max(1, int(2*s)))
    if mesh:
        draw_mesh_overlay(draw, pts)
    return pts


def triangulate_fan(center: tuple[int, int], ring: list[tuple[int, int]]) -> list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]]:
    return [(center, ring[i], ring[(i + 1) % len(ring)]) for i in range(len(ring))]


def draw_mesh_overlay(draw: ImageDraw.ImageDraw, pts: dict[str, tuple[int, int]]) -> None:
    mesh_lines = []
    for center_name, rx, ry, count in [
        ("skull_center", 120, 142, 12), ("ribcage_center", 116, 126, 10),
        ("abdomen_center", 104, 112, 10), ("pelvis_center", 96, 86, 8),
    ]:
        c = pts[center_name]
        ring = [(int(c[0] + math.cos(i / count * math.tau) * rx), int(c[1] + math.sin(i / count * math.tau) * ry)) for i in range(count)]
        for tri in triangulate_fan(c, ring):
            mesh_lines += [(tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])]
    for side in ("L", "R"):
        for a, b in [(f"shoulder_{side}", f"elbow_{side}"), (f"elbow_{side}", f"wrist_{side}"), (f"wrist_{side}", f"forepaw_{side}"), (f"hip_{side}", f"knee_{side}"), (f"knee_{side}", f"hock_{side}"), (f"hock_{side}", f"hindpaw_{side}")]:
            pa, pb = pts[a], pts[b]
            dx, dy = pb[0]-pa[0], pb[1]-pa[1]
            ln = max(1, math.hypot(dx, dy))
            nx, ny = -dy/ln*18, dx/ln*18
            q1, q2, q3, q4 = (int(pa[0]+nx), int(pa[1]+ny)), (int(pa[0]-nx), int(pa[1]-ny)), (int(pb[0]-nx), int(pb[1]-ny)), (int(pb[0]+nx), int(pb[1]+ny))
            mesh_lines += [(q1, q2), (q2, q3), (q3, q4), (q4, q1), (q1, q3), (q2, q4)]
    for side in ("L", "R"):
        c = pts[f"eye_socket_{side}"]
        ring = [(int(c[0] + math.cos(i / 8 * math.tau) * 34), int(c[1] + math.sin(i / 8 * math.tau) * 42)) for i in range(8)]
        for tri in triangulate_fan(c, ring):
            mesh_lines += [(tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])]
    for a, b in mesh_lines:
        line(draw, [a, b], COL["mesh"], 1)


def draw_atlas_view_cat(draw: ImageDraw.ImageDraw, ox: int, oy: int, s: float, view: str) -> None:
    def p(x: float, y: float) -> tuple[int, int]:
        return int(ox + x * s), int(oy + y * s)
    if view == "side":
        ellipse(draw, *p(-40, -180), int(126*s), int(164*s), COL["fur"], COL["line"], 3)
        ellipse(draw, *p(34, 48), int(150*s), int(132*s), COL["fur"], COL["line"], 3)
        ellipse(draw, *p(58, 178), int(124*s), int(86*s), COL["fur2"], COL["line"], 3)
        poly(draw, [p(-118, -312), p(-144, -438), p(-48, -306)], COL["fur"], COL["line"], 2)
        poly(draw, [p(-24, -310), p(-30, -430), p(38, -300)], COL["fur"], COL["line"], 2)
        ellipse(draw, *p(-135, -205), int(26*s), int(38*s), COL["eye"], COL["line"], 2)
        ellipse(draw, *p(-135, -205), int(9*s), int(20*s), (32, 30, 28), COL["line"], 1)
        poly(draw, [p(-52, -20), p(-18, -76), p(52, -18), p(30, 70), p(-24, 64)], (113, 190, 178), (64, 146, 136), 2)
        line(draw, [p(-4, -8), p(-130, 42), p(-218, 124), p(-286, 190)], COL["blue"], int(14*s))
        ellipse(draw, *p(-286, 190), int(28*s), int(18*s), (255, 213, 151), COL["line"], 2)
        line(draw, [p(110, 164), p(210, 280), p(154, 420), p(236, 468)], COL["fur2"], int(14*s))
        ellipse(draw, *p(236, 468), int(32*s), int(18*s), (255, 213, 151), COL["line"], 2)
        line(draw, [p(160, 122), p(310, 82), p(366, -52), p(280, -142)], COL["fur2"], int(22*s))
        line(draw, [p(160, 122), p(310, 82), p(366, -52), p(280, -142)], COL["line"], max(2, int(3*s)))
        return
    if view == "back":
        ellipse(draw, *p(0, -180), int(140*s), int(166*s), COL["fur"], COL["line"], 3)
        ellipse(draw, *p(0, 48), int(142*s), int(146*s), COL["fur"], COL["line"], 3)
        ellipse(draw, *p(0, 178), int(126*s), int(92*s), COL["fur2"], COL["line"], 3)
        poly(draw, [p(-88, -314), p(-166, -444), p(-32, -300)], COL["fur"], COL["line"], 2)
        poly(draw, [p(88, -314), p(166, -444), p(32, -300)], COL["fur"], COL["line"], 2)
        draw.arc([p(-82, -218), p(82, -138)], 28, 152, fill=(190, 104, 38), width=max(2, int(4*s)))
        poly(draw, [p(-90, -18), p(0, -80), p(90, -18), p(46, 70), p(-46, 70)], (113, 190, 178), (64, 146, 136), 2)
        for side, color, sx in (("L", COL["blue"], -1), ("R", COL["magenta"], 1)):
            line(draw, [p(sx*112, -8), p(sx*214, 38), p(sx*292, 126), p(sx*356, 196)], color, int(14*s))
            ellipse(draw, *p(sx*356, 196), int(28*s), int(18*s), (255, 213, 151), COL["line"], 2)
            line(draw, [p(sx*88, 194), p(sx*172, 310), p(sx*132, 428), p(sx*206, 472)], COL["fur2"], int(14*s))
            ellipse(draw, *p(sx*206, 472), int(32*s), int(18*s), (255, 213, 151), COL["line"], 2)
        line(draw, [p(0, 226), p(-130, 310), p(-250, 278), p(-306, 176)], COL["fur2"], int(22*s))
        line(draw, [p(0, 226), p(-130, 310), p(-250, 278), p(-306, 176)], COL["line"], max(2, int(3*s)))
        return
    draw_cat_base(draw, ox, oy, s, mesh=False)


def draw_atlas() -> None:
    img = Image.new("RGB", (2600, 1700), COL["bg"])
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 2600, 132], fill=COL["paper"])
    text(draw, (36, 24), "X5 详细分层图集：按小橘三视图拆层", 38)
    text(draw, (36, 78), "左侧是三视图工程层级预览，右侧是全部语义层。眼睛、耳朵、四肢、尾巴和星球已细拆。", 22, (116, 76, 38))
    for i, title in enumerate(["FRONT", "SIDE", "BACK"]):
        x = 320 + i * 500
        text(draw, (x - 80, 164), title, 28)
        draw_atlas_view_cat(draw, x, 760, 0.52, title.lower())
        # View-specific callouts.
        text(draw, (x - 160, 1240), "隐藏补全: 颈/肩/髋/尾根", 18, (42, 118, 88))
        if title == "SIDE":
            text(draw, (x - 170, 1280), "侧视保留近/远侧肢体身份", 18, COL["muted"])
        if title == "BACK":
            text(draw, (x - 165, 1280), "背视保留尾根和耳根连接", 18, COL["muted"])
    # Layer table.
    x0, y0 = 1660, 160
    text(draw, (x0, y0), f"详细图层清单 ({len(DETAILED_LAYERS)} layers)", 28)
    y = y0 + 46
    for idx, item in enumerate(sorted(DETAILED_LAYERS, key=lambda x: int(x["draw"]))):
        row_y = y + idx * 25
        fill = (255, 255, 255) if idx % 2 == 0 else (242, 247, 246)
        draw.rectangle([x0, row_y, 2540, row_y + 22], fill=fill)
        color = COL["ink"]
        if "eye" in str(item["id"]) or "iris" in str(item["id"]) or "lid" in str(item["id"]):
            color = (84, 68, 24)
        elif "tail" in str(item["id"]):
            color = (116, 70, 16)
        elif "planet" in str(item["id"]) or "contact" in str(item["id"]):
            color = (20, 92, 122)
        text(draw, (x0 + 8, row_y + 2), f"{item['draw']:>03}  {item['id']}  {item['name']}  -> {item['parent']}", 14, color)
    img.save(ATLAS)


def draw_mesh_moment_preview() -> None:
    img = Image.new("RGB", (2500, 1650), COL["bg"])
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 2500, 132], fill=COL["paper"])
    text(draw, (36, 24), "X5 三角剖分 + 力矩锚点预览", 38)
    text(draw, (36, 78), "三角线表示未来 ArtMesh 点集密度；蓝色为主要主动/力矩锚点，橙色为次级软组织/弹性锚点。", 22, (116, 76, 38))
    pts = draw_cat_base(draw, 760, 820, 0.88, mesh=True)
    # Primary and secondary anchors.
    for anchor in MOMENT_ANCHORS:
        pivot = str(anchor["pivot"])
        if pivot == "whisker_root":
            p = ((pts["whisker_root_L"][0] + pts["whisker_root_R"][0]) // 2, pts["whisker_root_L"][1])
        else:
            p = pts.get(pivot, pts["ribcage_center"])
        color = COL["primary"] if anchor["kind"] == "primary" else COL["secondary"]
        ellipse(draw, p[0], p[1], 11, 11, color, (255, 255, 255), 2)
        # Small force/torque direction arrows.
        if "shoulder_L" in pivot or "elbow_L" in pivot or "wrist_L" in pivot:
            arrow(draw, p, (p[0] - 54, p[1] - 34), color, 3)
        elif "shoulder_R" in pivot or "elbow_R" in pivot or "wrist_R" in pivot:
            arrow(draw, p, (p[0] + 54, p[1] - 34), color, 3)
        elif "ear" in pivot:
            arrow(draw, p, (p[0], p[1] - 58), color, 3)
        elif "tail" in pivot:
            arrow(draw, p, (p[0] + 58, p[1] + 18), color, 3)
        else:
            arrow(draw, p, (p[0], p[1] + 58), color, 3)
    # Legend and anchor table.
    x0, y0 = 1440, 170
    text(draw, (x0, y0), "主/次力矩与连接锚点", 30)
    y = y0 + 52
    for i, anchor in enumerate(MOMENT_ANCHORS):
        yy = y + i * 58
        color = COL["primary"] if anchor["kind"] == "primary" else COL["secondary"]
        draw.rounded_rectangle([x0, yy, 2428, yy + 44], radius=7, fill=(255, 255, 255), outline=color, width=2)
        text(draw, (x0 + 14, yy + 5), f"{anchor['id']} [{anchor['kind']}] pivot={anchor['pivot']} force={anchor['force']}", 16, color)
        text(draw, (x0 + 14, yy + 24), str(anchor["note"]), 13, COL["muted"])
    draw.rounded_rectangle([36, 1470, 2464, 1606], radius=8, fill=(236, 248, 244), outline=(116, 178, 148), width=2)
    notes = [
        "主要锚点控制姿势和遮眼：肩、肘、腕、支撑接触。这里延续 X2 的 r x F / J^T F 符号和相对大小，不靠骨段伸缩。",
        "次级锚点只做软组织、耳尖、尾尖、胡须、胸腹回弹：使用 torque = k(target-angle) - c*angularVelocity 的弹性近似。",
        "三角剖分先按真实层边界和高曲率区域加密；眼睑、眼眶、肘腕、尾根、接触阴影是高密区。",
    ]
    for i, note in enumerate(notes):
        text(draw, (64, 1494 + i * 34), note, 20, (36, 86, 68))
    img.save(MESH)


def draw_elastic_preview() -> None:
    img = Image.new("RGB", (2500, 1500), COL["bg"])
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 2500, 132], fill=COL["paper"])
    text(draw, (36, 24), "X5 父子链接 + 弹性关系预览", 38)
    text(draw, (36, 78), "每个真实层只有一个主控制节点；辅助顶点/弹性顶点属于网格，不反向拖动父节点。", 22, (116, 76, 38))
    # Tree with explicit edges so the cascade reads clearly.
    nodes = {
        "xroot": ("XiaojuRoot", 80, 176, 500),
        "body": ("BodyRoot", 240, 270, 500),
        "mass": ("Ribcage / Abdomen / Pelvis", 470, 360, 520),
        "head": ("Neck -> Head", 470, 470, 520),
        "eyes": ("Eyes / Lids / Muzzle / Whiskers", 760, 560, 520),
        "ears": ("Ears L/R", 760, 650, 520),
        "fore": ("Scapula -> Shoulder -> Elbow -> Wrist -> ForePaw L/R", 470, 790, 580),
        "hind": ("Hip -> Knee -> Hock -> HindPaw L/R", 470, 910, 520),
        "tail": ("TailRoot -> TailMid -> TailTip", 470, 1030, 520),
        "proot": ("PlanetRoot", 80, 1210, 500),
        "planet": ("PlanetBack / Surface / ContactShadow / PlanetFront", 320, 1300, 560),
    }
    edges = [
        ("xroot", "body"),
        ("body", "mass"),
        ("body", "head"),
        ("head", "eyes"),
        ("head", "ears"),
        ("body", "fore"),
        ("body", "hind"),
        ("body", "tail"),
        ("proot", "planet"),
    ]
    for a, b in edges:
        _, ax, ay, aw = nodes[a]
        _, bx, by, _ = nodes[b]
        start = (ax + aw, ay + 24)
        end = (bx, by + 24)
        if b in {"fore", "hind", "tail"}:
            start = (ax + aw // 2, ay + 48)
            end = (bx + 16, by + 24)
        arrow(draw, start, end, COL["mesh"], 2)
    for label, x, y, w in nodes.values():
        draw.rounded_rectangle([x, y, x + w, y + 48], radius=8, fill=(255, 255, 255), outline=(150, 150, 130), width=2)
        text(draw, (x + 14, y + 12), label, 18, COL["ink"])
    # Elastic chains table.
    x0, y0 = 1200, 190
    text(draw, (x0, y0), "弹性链 / Spring-Damper", 30)
    y = y0 + 56
    for i, chain in enumerate(ELASTIC_CHAINS):
        yy = y + i * 118
        draw.rounded_rectangle([x0, yy, 2405, yy + 92], radius=8, fill=(242, 250, 247), outline=COL["elastic"], width=2)
        text(draw, (x0 + 16, yy + 9), f"{chain['chain']}  input={chain['input']}  output={chain['output']}", 17, COL["elastic"])
        text(draw, (x0 + 16, yy + 36), f"stiffness={chain['stiffness']} damping={chain['damping']} clamp={chain['clamp']} settle={chain['settle']}", 16, COL["muted"])
        text(draw, (x0 + 16, yy + 60), "关系：父节点主动位移/角速度 -> Physics 输出低幅参数 -> Warp/ArtMesh 顶点变形", 15, COL["muted"])
    img.save(ELASTIC)


def contract_layer_rows() -> list[dict[str, object]]:
    rows = []
    for layer in DETAILED_LAYERS:
        lid = str(layer["id"])
        ctrl = str(layer["parent"])
        if lid.startswith("iris") or lid.startswith("pupil") or lid.startswith("highlight"):
            active = ["ParamEyeBallX", "ParamEyeBallY"]
        elif "lid" in lid:
            active = ["ParamBlink", "ParamEyeLOpen/ROpen", "ParamEyeLidFollowY"]
        elif lid.startswith("fore_") or "upper_arm" in lid or "forearm" in lid or "wrist_fur" in lid or "scapula_fur" in lid:
            active = ["ParamPasswordCover", "ParamForelimbL/R"]
        elif lid.startswith("hind_"):
            active = ["ParamBodySettle", "ParamHindStabilize"]
        elif "ear" in lid:
            active = ["ParamEarAttentionL/R", "ParamHeadAngle"]
        elif "tail" in lid:
            active = ["ParamTailRoot", "ParamTailFollow"]
        elif "abdomen" in lid or "ribcage" in lid or "chest" in lid:
            active = ["ParamBreath", "ParamBodySettle"]
        else:
            active = []
        rows.append({
            "sourceLayer": lid,
            "artMeshId": f"ArtMesh_{lid}",
            "primaryController": ctrl,
            "parent": layer["parent"],
            "pivot": layer["pivot"],
            "meshDensityZones": layer["density"],
            "hiddenOverlap": layer["overlap"],
            "clipDrawOrder": layer["draw"],
            "activeParameters": active,
            "elasticOutputs": layer["elastic"],
            "evidence": "live2d/x5/qa/x5-detailed-layer-atlas.png",
        })
    return rows


def write_contract() -> None:
    data = {
        "schemaVersion": 1,
        "stage": "X5-layer-mesh-node-torque",
        "status": "candidate-for-user-review",
        "authorizationBasis": "User requested detailed layers plus triangulation, torque anchors, link anchors, and elasticity relationships after X4 preview.",
        "sourceAuthority": [
            "three-view-preview.png",
            "live2d/x1/x1-canonical-body-contract.json",
            "live2d/x2/x2-pose-solve-contract.json",
            "live2d/x4/x4-layer-separation-contract.json",
        ],
        "gateBoundary": {
            "x5MayPassOnlyWithUserApproval": True,
            "cubismEditingAuthorized": False,
            "allowed": ["Layer-Mesh-Node contract", "triangulation preview", "moment/link/elastic preview"],
            "forbidden": ["PSD import", "Cubism file editing", "runtime replacement"],
        },
        "modelBoundary": [
            {"logicalModel": "Xiaoju", "independentRoot": "XiaojuRoot", "exportCandidate": "same package or separate model TBD in X8", "requiredRenderPass": "between planet_back and planet_front", "sharedContacts": ["contact_shadow", "planet_front"]},
            {"logicalModel": "Planet", "independentRoot": "PlanetRoot", "exportCandidate": "same package or separate model TBD in X8", "requiredRenderPass": "back/surface before Xiaoju, front after Xiaoju", "sharedContacts": ["chest-belly-planet-band"]},
        ],
        "layerContract": contract_layer_rows(),
        "momentAnchors": MOMENT_ANCHORS,
        "elasticChains": ELASTIC_CHAINS,
        "actionTracerNotes": [
            {"input": "password focus/cover", "priority": 100, "target": ["ParamPasswordCover", "forelimb joint parameters"], "rule": "active motion owns paw trajectory; Physics secondary only"},
            {"input": "gaze target", "priority": 60, "target": ["ParamEyeBallX/Y", "ParamEyeHeadCompX/Y"], "rule": "eyes lead head; no reset on blink"},
            {"input": "idle", "priority": 10, "target": ["ParamBreath", "ParamTailRoot", "ParamEarAttention"], "rule": "preserve velocities across state changes"},
        ],
        "qa": {
            "detailedLayerAtlas": "live2d/x5/qa/x5-detailed-layer-atlas.png",
            "triangulationMomentPreview": "live2d/x5/qa/x5-triangulation-moment-preview.png",
            "linkElasticPreview": "live2d/x5/qa/x5-link-elastic-preview.png",
            "selfReview": "live2d/x5/x5-self-review.json",
        },
        "nextGateIfApproved": "X6 parameters, Action Tracer keyforms, and Cubism-ready motion ranges",
    }
    CONTRACT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_review() -> None:
    REVIEW.write_text(
        f"""# X5 三角剖分、力矩锚点与弹性关系视觉审核

> 状态：X5 候选已生成，等待用户视觉审核。  
> X5 只定义图层边界、ArtMesh 点密度、主控制节点、父子链接、力矩/弹性关系；还不进入 PSD、Cubism 或运行时。

## 必看预览

- `qa/x5-detailed-layer-atlas.png`：按小橘三视图展开的详细分层图集，当前共有 `{len(DETAILED_LAYERS)}` 个语义层。
- `qa/x5-triangulation-moment-preview.png`：三角剖分密度、主要/次要力矩锚点、外力/接触/重力方向。
- `qa/x5-link-elastic-preview.png`：父子节点级联和弹性链。
- `x5-layer-mesh-node-torque-contract.json`：机器可读 Layer-Mesh-Node/力矩/弹性合同。
- `x5-self-review.json`：自动自审结果。

## 审核问题

1. 眼睛、耳朵、四肢、尾巴、胸腹、胡须和星球层是否拆得够细？
2. 三角高密区是否放在眼睑、眼眶、肘腕、尾根、接触阴影等真正会弯/压/遮挡的位置？
3. 主力矩锚点是否只控制核心动作，次级锚点是否只控制软组织和回弹？
4. 父子链接是否合理：局部层不能反向拖动身体，星球不能改变小橘骨段。
5. 弹性关系是否足够但不过度，不会把小橘做成整身软塌？

## Gate 决策

- 说 `X5 通过`：授权进入 X6 参数、Action Tracer 和 Cubism-ready keyform 范围。
- 指出具体问题：继续只修 X5 合同和预览，不进入 X6。
""",
        encoding="utf-8",
    )


def write_self_review() -> None:
    layer_rows = contract_layer_rows()
    missing_controller = [row["sourceLayer"] for row in layer_rows if not row["primaryController"]]
    missing_overlap = [row["sourceLayer"] for row in layer_rows if not row["hiddenOverlap"]]
    eye_layers = [row["sourceLayer"] for row in layer_rows if "eye" in row["sourceLayer"] or "iris" in row["sourceLayer"] or "lid" in row["sourceLayer"] or "pupil" in row["sourceLayer"]]
    qa = {
        "schemaVersion": 1,
        "status": "pass-with-known-art-likeness-risk",
        "checks": {
            "layerCount": len(layer_rows),
            "allLayersHavePrimaryController": not missing_controller,
            "missingController": missing_controller,
            "allLayersHaveHiddenOverlap": not missing_overlap,
            "missingOverlap": missing_overlap,
            "eyeLayerCount": len(eye_layers),
            "momentAnchorCount": len(MOMENT_ANCHORS),
            "primaryMomentAnchorCount": len([a for a in MOMENT_ANCHORS if a["kind"] == "primary"]),
            "secondaryMomentAnchorCount": len([a for a in MOMENT_ANCHORS if a["kind"] == "secondary"]),
            "elasticChainCount": len(ELASTIC_CHAINS),
            "triangulationPreviewOnly": True,
            "cubismEditing": False,
            "hindPawsAvoidForelimbCoverParams": all(
                "ParamPasswordCover" not in row["activeParameters"]
                for row in layer_rows
                if str(row["sourceLayer"]).startswith("hind_")
            ),
        },
        "knownRisks": [
            "X3 likeness was explicitly waived by user; engineering topology proceeds despite Xiaoju-likeness risk.",
            "This is a production contract and preview, not real PSD/Cubism ArtMesh output.",
            "Final mesh points must be reprojected onto actual painted transparent layer boundaries after art exists.",
        ],
        "reviewImages": [ATLAS.as_posix(), MESH.as_posix(), ELASTIC.as_posix()],
    }
    QA_JSON.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    draw_atlas()
    draw_mesh_moment_preview()
    draw_elastic_preview()
    write_contract()
    write_review()
    write_self_review()
    for path in (ATLAS, MESH, ELASTIC, CONTRACT, REVIEW, QA_JSON):
        print(path.as_posix())


if __name__ == "__main__":
    main()
