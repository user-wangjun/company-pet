from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SAMPLES_PATH = ROOT / "x2-cover-roundtrip-samples.json"
QA_DIR = ROOT / "qa"
OUT_PNG = QA_DIR / "x2-length-triangle-diagnostic.png"
OUT_JSON = ROOT / "x2-length-triangle-diagnostic.json"

SIDES = ("L", "R")
JOINT_ORDER = {
    "L": ["scapula_L", "shoulder_L", "elbow_L", "wrist_L", "forepaw_L"],
    "R": ["scapula_R", "shoulder_R", "elbow_R", "wrist_R", "forepaw_R"],
}
TRIANGLES = {
    "L": [
        ("scapula_L", "shoulder_L", "elbow_L"),
        ("shoulder_L", "elbow_L", "wrist_L"),
        ("elbow_L", "wrist_L", "forepaw_L"),
    ],
    "R": [
        ("scapula_R", "shoulder_R", "elbow_R"),
        ("shoulder_R", "elbow_R", "wrist_R"),
        ("elbow_R", "wrist_R", "forepaw_R"),
    ],
}


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def dist(a: list[float], b: list[float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def point_xy(p: list[float], box: tuple[int, int, int, int]) -> tuple[int, int]:
    x0, y0, w, h = box
    x = x0 + int((p[0] + 0.34) / 0.68 * w)
    y = y0 + int((0.74 - p[1]) / 0.76 * h)
    return x, y


def draw_arrow(draw: ImageDraw.ImageDraw, a: tuple[int, int], b: tuple[int, int], color: tuple[int, int, int], width: int = 3) -> None:
    draw.line([a, b], fill=color, width=width)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for delta in (2.55, -2.55):
        q = (int(b[0] + math.cos(ang + delta) * 10), int(b[1] + math.sin(ang + delta) * 10))
        draw.line([b, q], fill=color, width=width)


def main() -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    samples = data["samples"]
    rest = samples[0]
    frame_indices = [0, 8, 16, 20, 24, 32, 40]

    rest_lengths: dict[str, dict[str, float]] = {}
    triangle_edge_drift: dict[str, dict[str, float]] = {}
    max_segment_drift = 0.0
    for side in SIDES:
        rest_lengths[side] = {}
        triangle_edge_drift[side] = {}
        rest_joints = rest["sides"][side]["joints"]
        order = JOINT_ORDER[side]
        for a, b in zip(order, order[1:]):
            rest_lengths[side][f"{a}->{b}"] = dist(rest_joints[a], rest_joints[b])
        for tri in TRIANGLES[side]:
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                key = f"{a}->{b}"
                base = dist(rest_joints[a], rest_joints[b])
                mx = 0.0
                for sample in samples:
                    joints = sample["sides"][side]["joints"]
                    mx = max(mx, abs(dist(joints[a], joints[b]) - base))
                triangle_edge_drift[side][key] = round(mx, 8)
        for sample in samples:
            max_segment_drift = max(max_segment_drift, abs(float(sample["sides"][side]["segmentLengthDrift"])))

    W, H = 1780, 1260
    img = Image.new("RGB", (W, H), (250, 250, 246))
    draw = ImageDraw.Draw(img)
    title_font = load_font(34)
    head_font = load_font(22)
    font = load_font(17)
    small = load_font(14)

    draw.rectangle([0, 0, W, 138], fill=(255, 245, 226))
    draw.text((34, 24), "X2 Length + Triangle Constraint Diagnostic", fill=(42, 36, 28), font=title_font)
    draw.text(
        (34, 76),
        "Diagnostic only: not layer separation, not formal Delaunay/ArtMesh, not X3 authorization.",
        fill=(120, 72, 26),
        font=head_font,
    )
    draw.text(
        (34, 108),
        "Purpose: show whether X2 cover motion preserves bone lengths and local triangle proportions in the low-detail blockout.",
        fill=(70, 70, 64),
        font=font,
    )

    left = 34
    top = 164
    panel_w = 240
    panel_h = 360
    gap = 14
    chain_color = {"L": (30, 102, 210), "R": (213, 54, 173)}
    tri_fill = {"L": (168, 203, 255), "R": (255, 178, 226)}

    for n, idx in enumerate(frame_indices):
        sample = samples[idx]
        x = left + n * (panel_w + gap)
        y = top
        box = (x + 22, y + 52, panel_w - 44, panel_h - 92)
        draw.rounded_rectangle([x, y, x + panel_w, y + panel_h], radius=8, fill=(255, 255, 255), outline=(218, 211, 199), width=2)
        draw.text((x + 14, y + 12), f"sample {idx}  p={sample['coverProgress']:.2f}", fill=(38, 38, 36), font=font)
        draw.rectangle([box[0], box[1], box[0] + box[2], box[1] + box[3]], outline=(235, 230, 220), width=1)

        support = sample["supportHullX"]
        sx0 = point_xy([support[0], 0.0], box)[0]
        sx1 = point_xy([support[1], 0.0], box)[0]
        sy = point_xy([0.0, 0.03], box)[1]
        draw.line([(sx0, sy), (sx1, sy)], fill=(94, 166, 118), width=4)
        com = point_xy(sample["centerOfMass"], box)
        draw.ellipse([com[0] - 5, com[1] - 5, com[0] + 5, com[1] + 5], fill=(25, 25, 25))
        draw.text((com[0] + 8, com[1] - 8), "COM", fill=(25, 25, 25), font=small)

        for side in SIDES:
            joints = sample["sides"][side]["joints"]
            for tri in TRIANGLES[side]:
                pts = [point_xy(joints[j], box) for j in tri]
                draw.polygon(pts, fill=tri_fill[side], outline=(180, 180, 180))
            pts = [point_xy(joints[j], box) for j in JOINT_ORDER[side]]
            draw.line(pts, fill=chain_color[side], width=4)
            for j, p in zip(JOINT_ORDER[side], pts):
                draw.ellipse([p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4], fill=chain_color[side])

        drift = max(abs(float(sample["sides"]["L"]["segmentLengthDrift"])), abs(float(sample["sides"]["R"]["segmentLengthDrift"])))
        draw.text((x + 14, y + panel_h - 28), f"segment drift: {drift:.8f}", fill=(32, 102, 60), font=small)

    # Lower audit table.
    table_y = top + panel_h + 34
    draw.rounded_rectangle([34, table_y, W - 34, H - 44], radius=8, fill=(255, 255, 255), outline=(218, 211, 199), width=2)
    draw.text((58, table_y + 22), "Audit summary", fill=(38, 38, 36), font=head_font)
    lines = [
        f"Max declared anatomical bone-segment drift across 41 samples: {max_segment_drift:.8f}",
        "Local triangles shown above are X2 diagnostic constraints only; they are not layer boundaries and not formal triangulation.",
        "Bone edges should stay fixed; triangle diagonals may change normally as shoulder, elbow, and wrist fold.",
        "Formal layer images must still wait for X3 spread-pose master approval; formal Delaunay/ArtMesh must wait for X4 layer boundaries.",
    ]
    for i, line in enumerate(lines):
        draw.text((58, table_y + 62 + i * 30), line, fill=(64, 64, 58), font=font)

    col_x = [58, 470, 890, 1280]
    row_y = table_y + 208
    draw.text((col_x[0], row_y), "Triangle edge", fill=(38, 38, 36), font=font)
    draw.text((col_x[1], row_y), "L max edge drift", fill=(38, 38, 36), font=font)
    draw.text((col_x[2], row_y), "R max edge drift", fill=(38, 38, 36), font=font)
    draw.text((col_x[3], row_y), "Meaning", fill=(38, 38, 36), font=font)
    draw.line([(58, row_y + 28), (W - 58, row_y + 28)], fill=(210, 210, 202), width=2)

    edge_labels = [
        ("scapula->shoulder", "proximal shoulder link"),
        ("shoulder->elbow", "upper forelimb bone"),
        ("elbow->wrist", "forearm bone"),
        ("wrist->forepaw", "paw contact link"),
        ("shoulder->wrist", "folding triangle diagonal"),
        ("elbow->forepaw", "distal triangle diagonal"),
    ]
    y = row_y + 46
    for label, meaning in edge_labels:
        def side_value(side: str) -> float:
            candidates = [v for k, v in triangle_edge_drift[side].items() if label.replace("->", f"_{side}->") in k]
            if not candidates:
                a, b = label.split("->")
                ka, kb = f"{a}_{side}", f"{b}_{side}"
                candidates = [v for k, v in triangle_edge_drift[side].items() if k == f"{ka}->{kb}" or k == f"{kb}->{ka}"]
            return max(candidates) if candidates else 0.0

        lv = side_value("L")
        rv = side_value("R")
        draw.text((col_x[0], y), label, fill=(54, 54, 50), font=small)
        draw.text((col_x[1], y), f"{lv:.8f}", fill=(32, 102, 60), font=small)
        draw.text((col_x[2], y), f"{rv:.8f}", fill=(32, 102, 60), font=small)
        draw.text((col_x[3], y), meaning, fill=(82, 82, 76), font=small)
        y += 28

    img.save(OUT_PNG)

    diagnostic = {
        "schemaVersion": 1,
        "stage": "X2-pose-solve",
        "status": "diagnostic-only-not-layer-separation",
        "gateBoundary": {
            "allowedUse": "Visualize X2 bone-length preservation and local triangle constraints in the existing low-detail blockout.",
            "notAllowedUse": [
                "formal material separation",
                "formal Delaunay triangulation",
                "ArtMesh topology",
                "X3/X4 authorization",
            ],
        },
        "sampleCount": len(samples),
        "reviewFrames": frame_indices,
        "maxSegmentLengthDrift": round(max_segment_drift, 8),
        "maxTriangleEdgeDrift": triangle_edge_drift,
        "interpretation": {
            "boneEdges": "Anatomical bone segment rows should remain near zero; these are the no-stretch evidence.",
            "foldingDiagonals": "Diagonal rows such as shoulder->wrist and elbow->forepaw are expected to change as the limb folds; they are visual triangle constraints, not fixed bones.",
            "formalTriangulation": "These diagnostic triangles are not layer boundaries, not Delaunay output, and not ArtMesh topology.",
        },
        "outputs": {
            "visualDiagnostic": "live2d/x2/qa/x2-length-triangle-diagnostic.png",
        },
    }
    OUT_JSON.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT_PNG.as_posix())
    print(OUT_JSON.as_posix())


if __name__ == "__main__":
    main()
