from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
QA_DIR = ROOT / "qa"
SRC = QA_DIR / "x5-actual-xiaoju-spread-pose-three-view.png"
OUT = QA_DIR / "x5-actual-xiaoju-spread-pose-moment-elastic.png"
CONTRACT = ROOT / "x5-actual-xiaoju-spread-pose-moment-elastic-contract.json"


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
    "bone": (30, 45, 65, 235),
    "primary": (18, 88, 230, 245),
    "secondary": (224, 108, 24, 245),
    "force": (216, 62, 48, 235),
    "elastic": (20, 145, 92, 230),
    "mesh": (55, 92, 120, 92),
    "soft": (20, 145, 92, 70),
    "white": (255, 255, 255, 238),
    "ink": (34, 38, 44, 255),
    "panel": (252, 250, 246, 246),
}


VIEWS = {
    "front": {
        "label": "FRONT",
        "p": {
            "skull": (335, 205), "neck": (335, 312), "rib": (335, 398), "abd": (335, 515), "pelvis": (335, 610),
            "eye_L": (382, 177), "eye_R": (288, 177),
            "ear_L_base": (415, 104), "ear_L_tip": (455, 37), "ear_R_base": (255, 104), "ear_R_tip": (218, 37),
            "shoulder_L": (430, 330), "elbow_L": (485, 350), "wrist_L": (545, 377), "forepaw_L": (606, 400),
            "shoulder_R": (240, 330), "elbow_R": (185, 350), "wrist_R": (125, 377), "forepaw_R": (70, 400),
            "hip_L": (410, 600), "knee_L": (475, 675), "hock_L": (505, 735), "hindpaw_L": (545, 775),
            "hip_R": (260, 600), "knee_R": (195, 675), "hock_R": (165, 735), "hindpaw_R": (125, 775),
            "tail_root": (335, 638), "tail_mid": (338, 730), "tail_tip": (340, 825),
            "whisker_L": (442, 225), "whisker_R": (228, 225), "chest_fur": (335, 350),
        },
    },
    "side": {
        "label": "SIDE",
        "p": {
            "skull": (805, 205), "neck": (832, 318), "rib": (890, 420), "abd": (925, 525), "pelvis": (965, 600),
            "eye_L": (760, 178), "eye_R": (768, 182),
            "ear_L_base": (840, 105), "ear_L_tip": (815, 42), "ear_R_base": (880, 110), "ear_R_tip": (888, 50),
            "shoulder_L": (850, 345), "elbow_L": (800, 382), "wrist_L": (755, 420), "forepaw_L": (720, 458),
            "shoulder_R": (875, 358), "elbow_R": (828, 396), "wrist_R": (785, 432), "forepaw_R": (750, 468),
            "hip_L": (975, 600), "knee_L": (936, 668), "hock_L": (900, 735), "hindpaw_L": (858, 792),
            "hip_R": (1000, 610), "knee_R": (963, 682), "hock_R": (932, 748), "hindpaw_R": (898, 800),
            "tail_root": (980, 615), "tail_mid": (1010, 710), "tail_tip": (1006, 800),
            "whisker_L": (735, 230), "whisker_R": (748, 242), "chest_fur": (855, 365),
        },
    },
    "back": {
        "label": "BACK",
        "p": {
            "skull": (1480, 205), "neck": (1480, 318), "rib": (1480, 420), "abd": (1480, 530), "pelvis": (1480, 615),
            "eye_L": (1520, 178), "eye_R": (1440, 178),
            "ear_L_base": (1536, 136), "ear_L_tip": (1528, 90), "ear_R_base": (1424, 136), "ear_R_tip": (1432, 90),
            "shoulder_L": (1588, 365), "elbow_L": (1642, 410), "wrist_L": (1692, 462), "forepaw_L": (1732, 510),
            "shoulder_R": (1372, 365), "elbow_R": (1318, 410), "wrist_R": (1268, 462), "forepaw_R": (1228, 510),
            "hip_L": (1578, 616), "knee_L": (1632, 674), "hock_L": (1678, 718), "hindpaw_L": (1712, 744),
            "hip_R": (1382, 616), "knee_R": (1328, 674), "hock_R": (1282, 718), "hindpaw_R": (1248, 744),
            "tail_root": (1468, 638), "tail_mid": (1435, 724), "tail_tip": (1398, 802),
            "whisker_L": (1580, 225), "whisker_R": (1380, 225), "chest_fur": (1480, 360),
        },
    },
}


PRIMARY_ANCHORS = [
    ("M0", "rib"),
    ("M1", "shoulder_L"), ("M2", "elbow_L"), ("M3", "wrist_L"),
    ("M1", "shoulder_R"), ("M2", "elbow_R"), ("M3", "wrist_R"),
]

SECONDARY_ANCHORS = [
    ("S1", "chest_fur", "fur k=.58 c=.82"),
    ("S2", "ear_L_tip", "ear k=.72 c=.78"),
    ("S2", "ear_R_tip", "ear k=.72 c=.78"),
    ("S3", "tail_mid", "tail k=.48 c=.68"),
    ("S4", "whisker_L", "whisker k=.42 c=.74"),
    ("S4", "whisker_R", "whisker k=.42 c=.74"),
    ("S5", "abd", "belly k=.64 c=.86"),
]


def txt(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int, fill=COL["ink"]) -> None:
    draw.text(xy, text, font=font(size), fill=fill)


def line(draw: ImageDraw.ImageDraw, pts: list[tuple[int, int]], fill, width: int = 3) -> None:
    draw.line(pts, fill=fill, width=width, joint="curve")


def dot(draw: ImageDraw.ImageDraw, p: tuple[int, int], fill, r: int = 7, outline=(255, 255, 255, 245)) -> None:
    x, y = p
    draw.ellipse([x - r, y - r, x + r, y + r], fill=fill, outline=outline, width=2)


def label(draw: ImageDraw.ImageDraw, p: tuple[int, int], text: str, color, dx: int = 8, dy: int = -26) -> None:
    f = font(15)
    x, y = p[0] + dx, p[1] + dy
    w = int(draw.textlength(text, font=f)) + 12
    draw.rounded_rectangle([x, y, x + w, y + 24], radius=4, fill=COL["white"], outline=color, width=1)
    draw.text((x + 6, y + 3), text, font=f, fill=color)


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], fill, width: int = 3) -> None:
    line(draw, [start, end], fill, width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    for da in (2.55, -2.55):
        p = (int(end[0] + math.cos(angle + da) * 11), int(end[1] + math.sin(angle + da) * 11))
        line(draw, [end, p], fill, width)


def arc(draw: ImageDraw.ImageDraw, center: tuple[int, int], radius: int, start: int, end: int, fill, width: int = 3) -> None:
    x, y = center
    draw.arc([x - radius, y - radius, x + radius, y + radius], start, end, fill=fill, width=width)
    a = math.radians(end)
    tip = (int(x + math.cos(a) * radius), int(y + math.sin(a) * radius))
    tangent = a + math.pi / 2
    for da in (2.55, -2.55):
        p = (int(tip[0] + math.cos(tangent + da) * 10), int(tip[1] + math.sin(tangent + da) * 10))
        line(draw, [tip, p], fill, width)


def soft_ellipse(draw: ImageDraw.ImageDraw, p: tuple[int, int], rx: int, ry: int, color) -> None:
    x, y = p
    draw.ellipse([x - rx, y - ry, x + rx, y + ry], outline=color, width=2)


def draw_local_mesh(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]]) -> None:
    for a, b in zip(points, points[1:]):
        line(draw, [a, b], COL["mesh"], 1)
    for i in range(len(points) - 2):
        line(draw, [points[i], points[i + 2]], COL["mesh"], 1)


def draw_view(draw: ImageDraw.ImageDraw, view: dict) -> None:
    p = view["p"]
    txt(draw, (p["skull"][0] - 75, 122), view["label"], 20)
    side_view = view["label"] == "SIDE"
    back_view = view["label"] == "BACK"
    active_sides = ("L",) if side_view else ("L", "R")

    # Bone segments and parent cascade. White under-stroke keeps lines readable without opaque blocks.
    chains = [
        ["skull", "neck", "rib", "abd", "pelvis"],
        ["pelvis", "tail_root", "tail_mid", "tail_tip"],
        ["shoulder_L", "elbow_L", "wrist_L", "forepaw_L"],
        ["ear_R_base", "ear_R_tip"],
    ]
    if not back_view:
        chains.append(["ear_L_base", "ear_L_tip"])
    chains.extend([
        ["hip_L", "knee_L"],
        ["hip_R", "knee_R"],
    ])
    if not side_view:
        chains.insert(4, ["shoulder_R", "elbow_R", "wrist_R", "forepaw_R"])
    for chain in chains:
        pts = [p[name] for name in chain]
        line(draw, pts, (255, 255, 255, 210), 7)
        line(draw, pts, COL["bone"], 3)

    # Sparse triangle hints only around deformation zones; no large filled patches.
    for group in (
        ["shoulder_L", "elbow_L", "wrist_L", "forepaw_L"],
        ["rib", "abd", "pelvis"],
        ["tail_root", "tail_mid", "tail_tip"],
    ):
        draw_local_mesh(draw, [p[name] for name in group])
    for group in (
        ["hip_L", "knee_L"],
        ["hip_R", "knee_R"],
    ):
        draw_local_mesh(draw, [p[name] for name in group])

    # Primary anchors and r/F/tau visual model.
    primary = [("M0", "rib")]
    for active_side in active_sides:
        primary.extend([(label_id, f"{joint}_{active_side}") for label_id, joint in (("M1", "shoulder"), ("M2", "elbow"), ("M3", "wrist"))])
    for anchor, name in primary:
        dot(draw, p[name], COL["primary"], 7)
        label(draw, p[name], anchor, COL["primary"])

    for side in active_sides:
        eye = p[f"eye_{side}"]
        paw = p[f"forepaw_{side}"]
        wrist = p[f"wrist_{side}"]
        elbow = p[f"elbow_{side}"]
        shoulder = p[f"shoulder_{side}"]
        arrow(draw, wrist, paw, COL["primary"], 2)
        arrow(draw, paw, (int((paw[0] + eye[0]) / 2), int((paw[1] + eye[1]) / 2)), COL["force"], 3)
        arc(draw, shoulder, 26, 210 if side == "L" else -30, 285 if side == "L" else 45, COL["primary"], 3)
        arc(draw, elbow, 24, 218 if side == "L" else -38, 292 if side == "L" else 36, COL["primary"], 3)
        arc(draw, wrist, 20, 225 if side == "L" else -45, 298 if side == "L" else 28, COL["primary"], 3)

    # Gravity and support are force arrows, not big blocks.
    arrow(draw, (p["rib"][0], p["rib"][1] - 58), (p["rib"][0], p["rib"][1] - 15), COL["force"], 3)
    label(draw, (p["rib"][0], p["rib"][1] - 55), "F_g", COL["force"], dx=10, dy=-8)
    arrow(draw, (p["abd"][0], p["abd"][1] + 56), (p["abd"][0], p["abd"][1] + 15), COL["elastic"], 3)
    label(draw, (p["abd"][0], p["abd"][1] + 48), "N", COL["elastic"], dx=10, dy=-8)

    # Secondary anchors and elastic links: small dots plus thin outlines.
    for anchor, name, desc in SECONDARY_ANCHORS:
        if back_view and name.startswith("whisker_"):
            continue
        dot(draw, p[name], COL["secondary"], 5)
        if anchor in ("S2", "S3", "S5"):
            label(draw, p[name], anchor, COL["secondary"], dx=7, dy=8)
    elastic_links = [("ear_R_base", "ear_R_tip"), ("tail_root", "tail_mid"), ("tail_mid", "tail_tip"), ("neck", "chest_fur"), ("abd", "pelvis")]
    elastic_links.insert(0, ("ear_L_base", "ear_L_tip"))
    for a, b in elastic_links:
        line(draw, [p[a], p[b]], COL["elastic"], 2)
    soft_zones = (
        (("ear_L_tip", 13, 18), ("ear_R_tip", 13, 18), ("tail_mid", 18, 52), ("tail_tip", 16, 24), ("abd", 44, 38), ("chest_fur", 45, 35))
        if back_view
        else (("ear_L_tip", 18, 26), ("ear_R_tip", 18, 26), ("tail_mid", 26, 70), ("tail_tip", 22, 34), ("abd", 44, 38), ("chest_fur", 45, 35))
    )
    for name, rx, ry in soft_zones:
        soft_ellipse(draw, p[name], rx, ry, COL["soft"])


def write_contract() -> None:
    data = {
        "schemaVersion": 1,
        "stage": "X5-actual-xiaoju-spread-pose-moment-elastic-preview",
        "status": "candidate-for-user-review",
        "revision": "clean-v12-visible-body-short-guides",
        "sourceImage": "live2d/x5/qa/x5-actual-xiaoju-spread-pose-three-view.png",
        "outputImage": "live2d/x5/qa/x5-actual-xiaoju-spread-pose-moment-elastic.png",
        "userCorrectionApplied": [
            "Removed large opaque color blocks.",
            "Torque is shown primarily through bone segments, key/secondary anchors, r/F arrows, and tau arcs.",
            "Elasticity is shown with small secondary anchors, thin spring links, and pale outline envelopes only.",
            "Anchor coordinates were realigned to the actual spread-pose Xiaoju preview.",
            "Clean-v3 moves torque bone segments closer to the visible limbs and removes face-crossing ear bones.",
            "Clean-v4 shows only the near-side primary forelimb torque chain in side view and moves back-view ear anchors inside the visible ears.",
            "Clean-v5 recalibrates back-view ear, forelimb, hindlimb, pelvis, and tail anchors against the cropped actual Xiaoju back silhouette.",
            "Clean-v6 moves back-view hindlimb bones from outer contour toward visible limb centerlines and pulls the right ear elastic anchor back inside the ear surface.",
            "Clean-v7 shortens back-view hindlimb and tail bones so they remain inside the visible fur silhouette and reduces ear/tail elastic overreach.",
            "Clean-v8 moves back-view hindlimb chains onto the visible splayed leg centers and pulls both ear-tip anchors further inside the ear surfaces.",
            "Clean-v9 shortens back-view hindlimb drawing to internal visible-leg guide segments instead of full external fold lines.",
            "Clean-v10 removes back-view lower hindlimb guide segments that still fell into blank space; distal hind paw subdivision is deferred to real transparent leg layers.",
            "Clean-v11 hides the back-view far-side ear elastic hint when it cannot be placed fully inside the visible ear surface.",
            "Clean-v12 replaces long hindlimb guide chains in all views with short visible-body support guides, restores both back-view ear elastic hints inside the ear surfaces, aligns the back/side tail elastic chain to the visible tail direction, and hides back-view whisker anchors that have no visible surface."
        ],
        "momentModel": {
            "primaryAnchors": ["M0_body_support", "M1_shoulder_L/R", "M2_elbow_L/R", "M3_wrist_L/R"],
            "secondaryAnchors": ["S1_chest_fur", "S2_ear_tip_L/R", "S3_tail_follow", "S4_whisker_tip", "S5_belly_soft"],
            "visualRule": "r and F arrows plus tau arcs show sign/direction; relative size is shown by anchor class and line weight, not by filled blobs."
        },
        "elasticModel": {
            "rule": "Bone-segment lengths remain stable; soft response lives in mesh vertices around secondary anchors.",
            "coefficients": {
                "ear_tip": {"k": 0.72, "c": 0.78},
                "tail": {"k": 0.48, "c": 0.68},
                "fur": {"k": 0.58, "c": 0.82},
                "whisker": {"k": 0.42, "c": 0.74},
                "belly": {"k": 0.64, "c": 0.86}
            }
        },
        "gateBoundary": {
            "currentGate": "x5-layer-mesh-node-torque",
            "candidateOnly": True,
            "x5MayPassOnlyWithUserApproval": True,
            "x6Authorized": False,
            "forbidden": ["PSD import", "Cubism editing", "X6 parameter/keyform finalization", "runtime replacement"]
        }
    }
    CONTRACT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    src = Image.open(SRC).convert("RGBA")
    header = 96
    footer = 152
    img = Image.new("RGBA", (src.width, src.height + header + footer), (250, 250, 247, 255))
    img.paste(src, (0, header))
    draw = ImageDraw.Draw(img, "RGBA")

    draw.rounded_rectangle([22, 14, src.width - 22, 78], radius=8, fill=COL["panel"], outline=(120, 135, 120, 220), width=2)
    txt(draw, (46, 30), "X5 实际小橘大字型：骨段/锚点力矩模拟 + 轻量弹性关系", 30)
    txt(draw, (920, 40), "蓝=M 主锚点  橙=S 次锚点  红=F  绿=弹性链接", 18, (80, 75, 62, 255))

    shifted_views = {}
    for key, view in VIEWS.items():
        shifted = {"label": view["label"], "p": {name: (xy[0], xy[1] + header) for name, xy in view["p"].items()}}
        shifted_views[key] = shifted
        draw_view(draw, shifted)

    y = src.height + header + 14
    draw.rounded_rectangle([22, y, src.width - 22, y + footer - 28], radius=8, fill=COL["panel"], outline=(120, 135, 120, 220), width=2)
    txt(draw, (48, y + 18), "读图方式：骨段线保持长度稳定；蓝色 M0/M1/M2/M3 是主要力矩锚点；红色 F 是外力/接触/重力方向；蓝色弧线是 tau 的符号方向。", 19)
    txt(draw, (48, y + 54), "橙色 S1-S5 是次级弹性锚点，绿色细线/淡轮廓只表示 k/c 弹性响应区，不再用大色块代表肌肉。", 19)
    txt(draw, (48, y + 90), "这仍是 X5 候选预览，只用于你审核力矩、父子链接和弹性关系；未进入 X6、PSD、Cubism 或运行时。", 19, (126, 54, 42, 255))

    img.convert("RGB").save(OUT)
    write_contract()
    print(OUT.as_posix())
    print(CONTRACT.as_posix())


if __name__ == "__main__":
    main()
