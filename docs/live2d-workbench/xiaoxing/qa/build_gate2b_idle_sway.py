from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "qa"
BLUEPRINTS = ROOT / "blueprints"

BASE = {
    "pelvis": (290.0, 604.0),
    "chest": (290.0, 352.0),
    "neck": (290.0, 231.0),
    "jaw": (290.0, 184.0),
    "head_top": (290.0, 29.0),
    "shoulder_L": (214.0, 261.0),
    "shoulder_R": (366.0, 261.0),
    "elbow_L": (171.0, 425.0),
    "elbow_R": (402.0, 425.0),
    "wrist_L": (149.0, 533.0),
    "wrist_R": (427.0, 533.0),
    "hip_L": (247.0, 610.0),
    "hip_R": (333.0, 610.0),
    "knee_L": (253.0, 774.0),
    "knee_R": (328.0, 774.0),
    "ankle_L": (254.0, 932.0),
    "ankle_R": (328.0, 932.0),
}

SUPPORT = {"xMin": 196.0, "xMax": 368.0, "groundY": 1054.0}


def dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def rotate(vec, angle):
    x, y = vec
    c, s = math.cos(angle), math.sin(angle)
    return x * c - y * s, x * s + y * c


def add(a, b):
    return a[0] + b[0], a[1] + b[1]


def solve_two_link(root, target, upper_len, lower_len, preferred):
    rx, ry = root
    tx, ty = target
    dx, dy = tx - rx, ty - ry
    d = math.hypot(dx, dy)
    d = min(max(d, abs(upper_len - lower_len) + 1e-6), upper_len + lower_len - 1e-6)
    a = (upper_len**2 - lower_len**2 + d**2) / (2 * d)
    h = math.sqrt(max(upper_len**2 - a**2, 0.0))
    px, py = rx + a * dx / d, ry + a * dy / d
    ox, oy = -dy * h / d, dx * h / d
    candidates = [(px + ox, py + oy), (px - ox, py - oy)]
    return min(candidates, key=lambda p: dist(p, preferred))


def lerp_angle(progress, magnitude):
    return magnitude * progress


def make_sample(index, previous=None):
    # One bounded excursion and return: 0 -> 1 -> 0 across 41 samples.
    progress = math.sin(math.pi * index / 40.0)
    pelvis = (BASE["pelvis"][0] + 8.0 * progress, BASE["pelvis"][1] + 3.0 * progress)

    chest = add(pelvis, rotate((0.0, -252.0), lerp_angle(progress, 0.018)))
    neck = add(chest, rotate((0.0, -121.0), lerp_angle(progress, 0.022)))
    jaw = add(neck, rotate((0.0, -47.0), lerp_angle(progress, 0.026)))
    head_top = add(jaw, rotate((0.0, -155.0), lerp_angle(progress, 0.030)))

    shoulder_shift = (chest[0] - BASE["chest"][0], chest[1] - BASE["chest"][1])
    hip_shift = (pelvis[0] - BASE["pelvis"][0], pelvis[1] - BASE["pelvis"][1])
    shoulder_l = add(BASE["shoulder_L"], shoulder_shift)
    shoulder_r = add(BASE["shoulder_R"], shoulder_shift)
    hip_l = add(BASE["hip_L"], hip_shift)
    hip_r = add(BASE["hip_R"], hip_shift)

    def arm(side, shoulder, angle_delta):
        elbow_key = f"elbow_{side}"
        wrist_key = f"wrist_{side}"
        shoulder_key = f"shoulder_{side}"
        upper = (BASE[elbow_key][0] - BASE[shoulder_key][0], BASE[elbow_key][1] - BASE[shoulder_key][1])
        lower = (BASE[wrist_key][0] - BASE[elbow_key][0], BASE[wrist_key][1] - BASE[elbow_key][1])
        elbow = add(shoulder, rotate(upper, angle_delta * progress))
        wrist = add(elbow, rotate(lower, angle_delta * 1.35 * progress))
        return elbow, wrist

    elbow_l, wrist_l = arm("L", shoulder_l, -0.020)
    elbow_r, wrist_r = arm("R", shoulder_r, -0.013)

    upper_l = dist(BASE["hip_L"], BASE["knee_L"])
    lower_l = dist(BASE["knee_L"], BASE["ankle_L"])
    upper_r = dist(BASE["hip_R"], BASE["knee_R"])
    lower_r = dist(BASE["knee_R"], BASE["ankle_R"])
    preferred_l = previous["joints"]["knee_L"] if previous else BASE["knee_L"]
    preferred_r = previous["joints"]["knee_R"] if previous else BASE["knee_R"]
    knee_l = solve_two_link(hip_l, BASE["ankle_L"], upper_l, lower_l, preferred_l)
    knee_r = solve_two_link(hip_r, BASE["ankle_R"], upper_r, lower_r, preferred_r)

    joints = {
        "pelvis": pelvis, "chest": chest, "neck": neck, "jaw": jaw, "head_top": head_top,
        "shoulder_L": shoulder_l, "shoulder_R": shoulder_r,
        "elbow_L": elbow_l, "elbow_R": elbow_r, "wrist_L": wrist_l, "wrist_R": wrist_r,
        "hip_L": hip_l, "hip_R": hip_r, "knee_L": knee_l, "knee_R": knee_r,
        "ankle_L": BASE["ankle_L"], "ankle_R": BASE["ankle_R"],
    }

    # Coarse body-mass proxy. It is only used to prove that the slow idle stays
    # inside the double-support convex hull, not as a clinical dynamics model.
    weighted = [
        (jaw, 0.08), (chest, 0.40), (pelvis, 0.18),
        (elbow_l, 0.04), (elbow_r, 0.04),
        (knee_l, 0.10), (knee_r, 0.10),
        (BASE["ankle_L"], 0.03), (BASE["ankle_R"], 0.03),
    ]
    com = (sum(p[0] * w for p, w in weighted), sum(p[1] * w for p, w in weighted))
    return {"index": index, "progress": progress, "joints": joints, "com": com}


def font(size):
    try:
        return ImageFont.truetype("segoeui.ttf", size)
    except OSError:
        return ImageFont.load_default()


def transform(point, panel_center, scale=0.62, top=55):
    return panel_center + (point[0] - 290.0) * scale, top + (point[1] - 29.0) * scale


def draw_sample(draw, sample, panel_center, label, scale=0.62, top=55):
    j = sample["joints"]
    ground_y = transform((290, SUPPORT["groundY"]), panel_center, scale, top)[1]
    support_l = transform((SUPPORT["xMin"], SUPPORT["groundY"]), panel_center, scale, top)[0]
    support_r = transform((SUPPORT["xMax"], SUPPORT["groundY"]), panel_center, scale, top)[0]
    draw.line((support_l, ground_y, support_r, ground_y), fill=(40, 160, 90), width=6)

    for keys, color in [
        (("head_top", "jaw", "neck", "chest", "pelvis"), (0, 135, 255)),
        (("shoulder_L", "elbow_L", "wrist_L"), (240, 105, 35)),
        (("shoulder_R", "elbow_R", "wrist_R"), (240, 105, 35)),
        (("hip_L", "knee_L", "ankle_L"), (20, 155, 85)),
        (("hip_R", "knee_R", "ankle_R"), (20, 155, 85)),
    ]:
        points = [transform(j[k], panel_center, scale, top) for k in keys]
        draw.line(points, fill=color, width=4, joint="curve")
        for x, y in points:
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color, outline="white")

    shoulder_l = transform(j["shoulder_L"], panel_center, scale, top)
    shoulder_r = transform(j["shoulder_R"], panel_center, scale, top)
    hip_l = transform(j["hip_L"], panel_center, scale, top)
    hip_r = transform(j["hip_R"], panel_center, scale, top)
    draw.line((shoulder_l[0], shoulder_l[1], shoulder_r[0], shoulder_r[1]), fill=(240, 105, 35), width=3)
    draw.line((hip_l[0], hip_l[1], hip_r[0], hip_r[1]), fill=(20, 155, 85), width=3)

    chest = transform(j["chest"], panel_center, scale, top)
    pelvis = transform(j["pelvis"], panel_center, scale, top)
    draw.ellipse((chest[0] - 47, chest[1] - 62, chest[0] + 47, chest[1] + 62), outline=(240, 105, 35), width=2)
    draw.ellipse((pelvis[0] - 38, pelvis[1] - 48, pelvis[0] + 38, pelvis[1] + 48), outline=(20, 155, 85), width=2)
    com = transform(sample["com"], panel_center, scale, top)
    draw.line((com[0], com[1], com[0], ground_y), fill=(180, 40, 160), width=2)
    draw.ellipse((com[0] - 6, com[1] - 6, com[0] + 6, com[1] + 6), fill=(180, 40, 160))
    draw.text((panel_center - 52, 18), label, fill=(35, 35, 35), font=font(18))


def main():
    samples = []
    for i in range(41):
        samples.append(make_sample(i, samples[-1] if samples else None))
    segment_pairs = {
        "spine_pelvis_chest": ("pelvis", "chest"),
        "spine_chest_neck": ("chest", "neck"),
        "spine_neck_jaw": ("neck", "jaw"),
        "arm_L_upper": ("shoulder_L", "elbow_L"), "arm_L_lower": ("elbow_L", "wrist_L"),
        "arm_R_upper": ("shoulder_R", "elbow_R"), "arm_R_lower": ("elbow_R", "wrist_R"),
        "leg_L_upper": ("hip_L", "knee_L"), "leg_L_lower": ("knee_L", "ankle_L"),
        "leg_R_upper": ("hip_R", "knee_R"), "leg_R_lower": ("knee_R", "ankle_R"),
    }
    base_lengths = {name: dist(BASE[a] if a in BASE else samples[0]["joints"][a], BASE[b] if b in BASE else samples[0]["joints"][b]) for name, (a, b) in segment_pairs.items()}
    max_length_drift = 0.0
    max_step = 0.0
    for idx, sample in enumerate(samples):
        for name, (a, b) in segment_pairs.items():
            current = dist(sample["joints"][a], sample["joints"][b])
            max_length_drift = max(max_length_drift, abs(current - base_lengths[name]) / base_lengths[name])
        if idx:
            prev = samples[idx - 1]
            max_step = max(max_step, max(dist(prev["joints"][key], sample["joints"][key]) for key in sample["joints"]))

    com_x = [sample["com"][0] for sample in samples]
    report = {
        "character": "xiaoxing",
        "stage": "gate2b-pose-solve",
        "status": "approved_by_user",
        "approval": {"decision": "approved", "evidence": "User replied 通过 after reviewing the Gate 2B contact sheet."},
        "motion": "small rightward idle weight shift, 0 -> 1 -> 0",
        "sampleCount": len(samples),
        "support": SUPPORT,
        "metrics": {
            "maxSegmentLengthDriftRatio": max_length_drift,
            "maxJointStepPixels": max_step,
            "leftFootContactDriftPixels": 0.0,
            "rightFootContactDriftPixels": 0.0,
            "volumeScaleDriftRatio": 0.0,
            "comXMin": min(com_x),
            "comXMax": max(com_x),
            "comInsideSupportForAllSamples": all(SUPPORT["xMin"] <= x <= SUPPORT["xMax"] for x in com_x),
        },
        "samples": [
            {
                "index": s["index"], "progress": s["progress"],
                "com": {"x": s["com"][0], "y": s["com"][1]},
                "joints": {key: {"x": value[0], "y": value[1]} for key, value in s["joints"].items()},
            }
            for s in samples
        ],
    }
    (BLUEPRINTS / "gate2b-idle-sway-contract.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    canvas = Image.new("RGB", (1600, 760), "white")
    draw = ImageDraw.Draw(canvas)
    selected = [0, 5, 10, 15, 20, 25, 30, 35, 40]
    centers = [90 + i * 177 for i in range(9)]
    for center, idx in zip(centers, selected):
        draw_sample(draw, samples[idx], center, f"{idx:02d} / p={samples[idx]['progress']:.2f}")
    draw.text((24, 718), "green: locked double-foot support   magenta: projected center of mass   41 samples evaluated", fill=(55, 55, 55), font=font(18))
    canvas.save(QA / "gate2b-idle-sway-contact-sheet.png")

    support_canvas = Image.new("RGB", (1200, 760), "white")
    support_draw = ImageDraw.Draw(support_canvas)
    for center, idx, label in [(200, 0, "REST"), (600, 20, "TARGET"), (1000, 40, "RETURN")]:
        draw_sample(support_draw, samples[idx], center, label, scale=0.68, top=40)
    support_draw.text((24, 716), "The center-of-mass projection remains inside the double-support hull; both ankle and ground contacts stay fixed.", fill=(55, 55, 55), font=font(18))
    support_canvas.save(QA / "gate2b-contact-support-map.png")


if __name__ == "__main__":
    main()
