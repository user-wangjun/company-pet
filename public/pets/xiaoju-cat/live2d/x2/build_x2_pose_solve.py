from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
LIVE2D = HERE.parent
PET_ROOT = LIVE2D.parent
X1_CONTRACT = LIVE2D / "x1" / "x1-canonical-body-contract.json"
QA_DIR = HERE / "qa"
CONTRACT_PATH = HERE / "x2-pose-solve-contract.json"
SAMPLES_PATH = HERE / "x2-cover-roundtrip-samples.json"
REPORT_PATH = HERE / "x2-pose-solve-report.md"
SUPPORT_MAP_PATH = QA_DIR / "x2-contact-support-map.png"
BLOCKOUT_PATH = QA_DIR / "x2-cover-roundtrip-blockout-sheet.png"
TORQUE_PATH = QA_DIR / "x2-moment-demand-preflight.png"
PHYSICAL_TORQUE_PATH = QA_DIR / "x2-physical-moment-preflight.png"
FULL_MOMENT_PATH = QA_DIR / "x2-full-moment-review-sheet.png"
INTUITIVE_PREVIEW_PATH = QA_DIR / "x2-intuitive-moment-cover-preview.png"
INTUITIVE_GIF_PATH = QA_DIR / "x2-intuitive-moment-cover-preview.gif"


CANVAS = (1500, 980)
SCALE = 720.0
ORIGIN = (750.0, 850.0)

COLORS = {
    "bg": (246, 249, 252, 255),
    "panel": (255, 255, 255, 238),
    "line": (45, 72, 96, 210),
    "left": (255, 65, 205, 235),
    "right": (255, 205, 45, 235),
    "tail": (60, 235, 110, 230),
    "mass": (58, 178, 235, 42),
    "contact": (60, 210, 120, 100),
    "reaction": (40, 145, 80, 230),
    "com": (255, 65, 55, 245),
    "target": (255, 110, 40, 135),
    "torque": (100, 75, 230, 230),
    "warning": (210, 115, 35, 255),
}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    choices = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for path in choices:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp2(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t))


def p(point: tuple[float, float]) -> tuple[float, float]:
    return ORIGIN[0] + point[0] * SCALE, ORIGIN[1] - point[1] * SCALE


def fabrik(root: tuple[float, float], rest: list[tuple[float, float]], target: tuple[float, float], lengths: list[float]) -> list[tuple[float, float]]:
    total = sum(lengths)
    if dist(root, target) >= total:
        direction = ((target[0] - root[0]) / dist(root, target), (target[1] - root[1]) / dist(root, target))
        pts = [root]
        for length in lengths:
            pts.append((pts[-1][0] + direction[0] * length, pts[-1][1] + direction[1] * length))
        return pts

    pts = [root] + rest[1:]
    for _ in range(18):
        pts[-1] = target
        for i in range(len(pts) - 2, -1, -1):
            d = max(1e-8, dist(pts[i], pts[i + 1]))
            lam = lengths[i] / d
            pts[i] = (
                (1 - lam) * pts[i + 1][0] + lam * pts[i][0],
                (1 - lam) * pts[i + 1][1] + lam * pts[i][1],
            )
        pts[0] = root
        for i in range(len(pts) - 1):
            d = max(1e-8, dist(pts[i], pts[i + 1]))
            lam = lengths[i] / d
            pts[i + 1] = (
                (1 - lam) * pts[i][0] + lam * pts[i + 1][0],
                (1 - lam) * pts[i][1] + lam * pts[i + 1][1],
            )
    return pts


def norm(v: tuple[float, float]) -> tuple[float, float]:
    d = math.hypot(v[0], v[1])
    if d < 1e-8:
        return (0.0, 1.0)
    return (v[0] / d, v[1] / d)


def solve_two_link(
    root: tuple[float, float],
    target: tuple[float, float],
    l1: float,
    l2: float,
    preferred_elbow: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    dx, dy = target[0] - root[0], target[1] - root[1]
    d = math.hypot(dx, dy)
    max_reach = l1 + l2 - 1e-7
    min_reach = abs(l1 - l2) + 1e-7
    if d > max_reach:
        ux, uy = dx / d, dy / d
        target = (root[0] + ux * max_reach, root[1] + uy * max_reach)
        dx, dy = target[0] - root[0], target[1] - root[1]
        d = max_reach
    elif d < min_reach:
        ux, uy = norm((dx, dy))
        target = (root[0] + ux * min_reach, root[1] + uy * min_reach)
        dx, dy = target[0] - root[0], target[1] - root[1]
        d = min_reach

    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, l1 * l1 - a * a))
    ux, uy = dx / d, dy / d
    base = (root[0] + a * ux, root[1] + a * uy)
    perp = (-uy, ux)
    candidate_a = (base[0] + h * perp[0], base[1] + h * perp[1])
    candidate_b = (base[0] - h * perp[0], base[1] - h * perp[1])
    elbow = candidate_a if dist(candidate_a, preferred_elbow) <= dist(candidate_b, preferred_elbow) else candidate_b
    return root, elbow, target


def vec_angle(v: tuple[float, float]) -> float:
    return math.degrees(math.atan2(v[1], v[0]))


def short_delta(a: float, b: float) -> float:
    return (b - a + 180.0) % 360.0 - 180.0


def solve_cover_chain(
    rest: list[tuple[float, float]],
    eye_target: tuple[float, float],
    progress: float,
    lengths: list[float],
    previous: list[tuple[float, float]] | None,
) -> list[tuple[float, float]]:
    del eye_target, previous
    root = rest[0]
    rest_angles = [
        vec_angle((rest[i + 1][0] - rest[i][0], rest[i + 1][1] - rest[i][1]))
        for i in range(3)
    ]
    # Global segment angles chosen as a low-detail Motion curve target. They keep
    # the elbow on one fold branch and make the paw cover from the outer cheek
    # side toward the eye, instead of flipping outward from the nose bridge.
    if root[0] > 0:
        cover_angles = [125.0, 60.0, 160.0]
    else:
        cover_angles = [55.0, 120.0, 20.0]
    # Stagger distal joints slightly so the shoulder initiates the lift and the
    # wrist settles last. This mirrors the intended active Motion ownership.
    lags = [0.00, 0.08, 0.16]
    gains = []
    for lag in lags:
        local = max(0.0, min(1.0, (progress - lag) / (1.0 - lag)))
        gains.append(smoothstep(local))
    angles = [
        rest_angle + short_delta(rest_angle, cover_angle) * gain
        for rest_angle, cover_angle, gain in zip(rest_angles, cover_angles, gains)
    ]
    pts = [root]
    for angle_deg, length in zip(angles, lengths):
        pts.append(
            (
                pts[-1][0] + math.cos(math.radians(angle_deg)) * length,
                pts[-1][1] + math.sin(math.radians(angle_deg)) * length,
            )
        )
    return pts


def angle(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def angle_delta(a: float, b: float) -> float:
    d = (b - a + 180.0) % 360.0 - 180.0
    return d


def chain_angles(points: list[tuple[float, float]]) -> list[float]:
    return [angle(points[i], points[i + 1]) for i in range(len(points) - 1)]


def cross2(r: tuple[float, float], f: tuple[float, float]) -> float:
    return r[0] * f[1] - r[1] * f[0]


def force_add(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return (a[0] + b[0], a[1] + b[1])


def force_scale(v: tuple[float, float], scale: float) -> tuple[float, float]:
    return (v[0] * scale, v[1] * scale)


def physical_moment_demand(
    joint_point: tuple[float, float],
    paw: tuple[float, float],
    eye_target: tuple[float, float],
    progress: float,
    capacity: float,
) -> dict:
    contact_strength = smoothstep((progress - 0.84) / 0.16)
    distal_gravity = (0.0, -0.055)
    lift_inertia = (0.0, 0.035 * (1.0 - abs(progress - 0.5) * 2.0))
    face_normal = norm((paw[0] - eye_target[0], paw[1] - eye_target[1]))
    face_reaction = force_scale(face_normal, 0.115 * contact_strength)
    total_force = force_add(force_add(distal_gravity, lift_inertia), face_reaction)
    lever = (paw[0] - joint_point[0], paw[1] - joint_point[1])
    signed_tau = cross2(lever, total_force)
    component_torques = {
        "distalGravity": cross2(lever, distal_gravity),
        "liftInertia": cross2(lever, lift_inertia),
        "faceReaction": cross2(lever, face_reaction),
    }
    return {
        "signedTau": round(signed_tau, 5),
        "relativeDemand": round(min(1.0, abs(signed_tau) / capacity), 4),
        "leverArm": [round(lever[0], 5), round(lever[1], 5)],
        "force": [round(total_force[0], 5), round(total_force[1], 5)],
        "components": {
            "distalGravity": [round(distal_gravity[0], 5), round(distal_gravity[1], 5)],
            "liftInertia": [round(lift_inertia[0], 5), round(lift_inertia[1], 5)],
            "faceReaction": [round(face_reaction[0], 5), round(face_reaction[1], 5)],
            "faceContactStrength": round(contact_strength, 4),
        },
        "componentTorques": {k: round(v, 5) for k, v in component_torques.items()},
        "method": "tau = r x (distal gravity + lift inertia + face contact reaction)",
    }


def load_x1() -> dict:
    return json.loads(X1_CONTRACT.read_text(encoding="utf-8"))


def body_com(x1: dict, compensation: tuple[float, float]) -> tuple[float, float]:
    sx = sy = sm = 0.0
    for block in x1["massBlocks"].values():
        m = float(block["mass_fraction"])
        sx += block["center"][0] * m
        sy += block["center"][1] * m
        sm += m
    return (sx / sm + compensation[0], sy / sm + compensation[1])


def build_samples(x1: dict) -> tuple[list[dict], dict]:
    joints = x1["canonicalJoints3D"]
    eye_targets = {
        "L": tuple(x1["headReferenceVolumes"]["eye_cover_zone_L"]["center"][:2]),
        "R": tuple(x1["headReferenceVolumes"]["eye_cover_zone_R"]["center"][:2]),
    }
    rest = {}
    scapula = {}
    lengths = {}
    rest_angles = {}
    for side in ("L", "R"):
        scapula[side] = tuple(joints[f"scapula_{side}"][:2])
        chain_names = [f"shoulder_{side}", f"elbow_{side}", f"wrist_{side}", f"forepaw_{side}"]
        rest[side] = [(joints[name][0], joints[name][1]) for name in chain_names]
        lengths[side] = [dist(rest[side][i], rest[side][i + 1]) for i in range(3)]
        rest_angles[side] = chain_angles(rest[side])

    samples = []
    max_segment_drift = 0.0
    max_angle_step = 0.0
    peak_relative_demand = 0.0
    peak_physical_demand = 0.0
    previous_angles: dict[str, list[float]] | None = None
    previous_points: dict[str, list[tuple[float, float]]] = {}
    support_x = (-0.285, 0.285)
    stable_count = 0

    for index in range(41):
        trip = index / 40.0
        raw_progress = trip * 2.0 if trip <= 0.5 else (1.0 - trip) * 2.0
        progress = smoothstep(raw_progress)
        phase = "enter" if trip < 0.5 else "exit"
        if abs(progress - 1.0) < 1e-9:
            phase = "cover-hold-key"
        compensation = (0.0, -0.008 * progress)
        com = body_com(x1, compensation)
        support_ok = support_x[0] <= com[0] <= support_x[1]
        stable_count += int(support_ok)
        side_data = {}
        angle_step_frame = 0.0

        for side in ("L", "R"):
            start = rest[side]
            target = lerp2(start[-1], eye_targets[side], progress)
            solved = solve_cover_chain(start, eye_targets[side], progress, lengths[side], previous_points.get(side))
            seg_lengths = [dist(solved[i], solved[i + 1]) for i in range(3)]
            drifts = [abs(a - b) for a, b in zip(seg_lengths, lengths[side])]
            max_segment_drift = max(max_segment_drift, max(drifts))
            angles = chain_angles(solved)
            angle_steps = [0.0, 0.0, 0.0]
            if previous_angles is not None:
                angle_steps = [abs(angle_delta(a, b)) for a, b in zip(previous_angles[side], angles)]
                angle_step_frame = max(angle_step_frame, max(angle_steps))

            paw = solved[-1]
            distance_to_cover = dist(paw, eye_targets[side])
            joint_efforts = {}
            physical_efforts = {}
            scapula_step = 0.0 if previous_angles is None else max(angle_steps) * 0.45
            scapula_load = progress * 0.20
            scapula_sign = -1.0 if side == "L" else 1.0
            scapula_demand = min(1.0, scapula_load + scapula_step * 0.006)
            peak_relative_demand = max(peak_relative_demand, scapula_demand)
            joint_efforts["scapula"] = {
                "signedMoment": round(scapula_sign * scapula_demand, 5),
                "relativeDemand": round(scapula_demand, 4),
                "components": {
                    "activeAngleDemand": 0.0,
                    "distalLoad": round(scapula_load, 4),
                    "velocityLoad": round(scapula_step * 0.006, 4),
                },
                "expectedDrive": "stabilize-scapula-and-transfer-load-to-body",
            }
            for joint_index, (joint_name, angle_capacity, load_scale, velocity_scale) in enumerate(
                (
                    ("shoulder", 150.0, 0.24, 0.010),
                    ("elbow", 145.0, 0.18, 0.009),
                    ("wrist", 130.0, 0.10, 0.007),
                )
            ):
                signed_delta = angle_delta(rest_angles[side][joint_index], angles[joint_index])
                active_drive = abs(signed_delta) / angle_capacity
                distal_load = progress * load_scale
                velocity_load = angle_steps[joint_index] * velocity_scale
                demand = min(1.0, active_drive * 0.62 + distal_load + velocity_load)
                peak_relative_demand = max(peak_relative_demand, demand)
                joint_efforts[joint_name] = {
                    "signedMoment": round(signed_delta * (0.62 / angle_capacity) + distal_load, 5),
                    "relativeDemand": round(demand, 4),
                    "components": {
                        "activeAngleDemand": round(active_drive, 4),
                        "distalLoad": round(distal_load, 4),
                        "velocityLoad": round(velocity_load, 4),
                    },
                    "expectedDrive": "lift-and-fold-toward-eye",
                }
            for joint_name, joint_point, capacity in (
                ("scapula", scapula[side], 0.042),
                ("shoulder", solved[0], 0.034),
                ("elbow", solved[1], 0.026),
                ("wrist", solved[2], 0.018),
            ):
                physical = physical_moment_demand(joint_point, paw, eye_targets[side], progress, capacity)
                peak_physical_demand = max(peak_physical_demand, physical["relativeDemand"])
                physical_efforts[joint_name] = physical

            side_data[side] = {
                "joints": {
                    f"scapula_{side}": [round(v, 5) for v in scapula[side]],
                    f"shoulder_{side}": [round(v, 5) for v in solved[0]],
                    f"elbow_{side}": [round(v, 5) for v in solved[1]],
                    f"wrist_{side}": [round(v, 5) for v in solved[2]],
                    f"forepaw_{side}": [round(v, 5) for v in solved[3]],
                },
                "target": [round(v, 5) for v in target],
                "distanceToEyeCoverZone": round(distance_to_cover, 5),
                "segmentLengthDrift": round(max(drifts), 8),
                "anglesDeg": [round(a, 3) for a in angles],
                "angleDeltaFromRestDeg": [round(angle_delta(a, b), 3) for a, b in zip(rest_angles[side], angles)],
                "moments": joint_efforts,
                "controlMoments": joint_efforts,
                "physicalMoments": physical_efforts,
                "faceContact": progress >= 0.94 and distance_to_cover <= 0.035,
            }

        previous_points = {side: [tuple(v) for v in side_data[side]["joints"].values()] for side in ("L", "R")}
        previous_angles = {side: side_data[side]["anglesDeg"] for side in ("L", "R")}
        max_angle_step = max(max_angle_step, angle_step_frame)
        forepaw_contacts_released = progress >= 0.12

        samples.append(
            {
                "index": index,
                "roundtripT": round(trip, 4),
                "coverProgress": round(progress, 4),
                "phase": phase,
                "bodyCompensation": [round(v, 5) for v in compensation],
                "centerOfMass": [round(v, 5) for v in com],
                "supportHullX": [support_x[0], support_x[1]],
                "supportOk": support_ok,
                "contacts": {
                    "chestBellyPlanetBand": {
                        "active": True,
                        "normal": [0.0, 1.0],
                        "friction": "static-preferred; tiny tangential slide allowed below 0.015 body-height",
                    },
                    "hindPaws": {"active": True, "role": "secondary stabilizers"},
                    "forePawsOnPlanet": {"active": not forepaw_contacts_released, "releaseProgress": 0.12},
                    "forePawsOnFace": {
                        "active": side_data["L"]["faceContact"] and side_data["R"]["faceContact"],
                        "requiredOnlyNearCover": True,
                    },
                },
                "sides": side_data,
            }
        )

    all_face_contact = any(s["contacts"]["forePawsOnFace"]["active"] for s in samples)
    continuity = {
        "sampleCount": len(samples),
        "maxSegmentLengthDrift": round(max_segment_drift, 8),
        "maxSingleSampleAngleStepDeg": round(max_angle_step, 4),
        "supportOkSamples": stable_count,
        "supportOkAllSamples": stable_count == len(samples),
        "faceContactOccursAtCover": all_face_contact,
        "peakRelativeMomentDemand": round(peak_relative_demand, 4),
        "peakPhysicalMomentDemand": round(peak_physical_demand, 4),
        "volumePolicy": "skull/ribcage/abdomen/pelvis scale remains 1.0; contact compression is local soft tissue only",
        "futureMeshPolicy": "formal layer images, Delaunay triangulation, helper mesh points, and elastic coefficients are deferred until X3/X4 approval",
    }
    return samples, continuity


def make_contract(x1: dict, samples: list[dict], continuity: dict) -> dict:
    physical_summary = {}
    control_summary = {}
    for side in ("L", "R"):
        physical_summary[side] = {}
        control_summary[side] = {}
        for joint in ("scapula", "shoulder", "elbow", "wrist"):
            physical_values = [sample["sides"][side]["physicalMoments"][joint] for sample in samples]
            control_values = [sample["sides"][side]["controlMoments"][joint] for sample in samples]
            peak_physical = max(physical_values, key=lambda item: item["relativeDemand"])
            peak_control = max(control_values, key=lambda item: item["relativeDemand"])
            cover_physical = samples[20]["sides"][side]["physicalMoments"][joint]
            cover_control = samples[20]["sides"][side]["controlMoments"][joint]
            physical_summary[side][joint] = {
                "peakRelativeDemand": peak_physical["relativeDemand"],
                "peakSignedTau": peak_physical["signedTau"],
                "coverSignedTau": cover_physical["signedTau"],
                "coverSign": "positive" if cover_physical["signedTau"] > 0 else "negative" if cover_physical["signedTau"] < 0 else "zero",
                "signConvention": "positive is counter-clockwise in the X2 front-plane drawing",
            }
            control_summary[side][joint] = {
                "peakRelativeDemand": peak_control["relativeDemand"],
                "peakSignedMoment": peak_control["signedMoment"],
                "coverSignedMoment": cover_control["signedMoment"],
            }

    return {
        "schemaVersion": 1,
        "stage": "X2-pose-solve",
        "status": "candidate-for-user-review",
        "x1ApprovalBasis": "User said to continue X2 after reviewing X1; X1 artifacts are treated as the approved body source for this X2 candidate.",
        "sourceContracts": {
            "x1": "live2d/x1/x1-canonical-body-contract.json",
            "planetScene": "live2d/planet-scene-source/planet-scene-v2-layered-preview.png",
        },
        "gateBoundary": {
            "allowed": [
                "contact map",
                "center-of-mass and support report",
                "0-to-1-to-0 connected low-detail blockout",
                "qualitative moment direction and relative demand simulation",
            ],
            "forbidden": [
                "realistic master generation",
                "spread-pose Xiaoju art generation",
                "material separation",
                "Photoshop or PSD import",
                "Cubism ArtMesh, Deformer, Physics, or runtime edits",
            ],
        },
        "contactModel": {
            "primarySupport": {
                "id": "chest-belly-planet-band",
                "bodyDrivers": ["ribcage", "abdomen"],
                "normal": [0.0, 1.0],
                "supportHullX": [-0.285, 0.285],
                "frictionAssumption": "static preferred; tiny slide below 0.015 normalized body height is allowed during cover enter/exit",
                "mustNotCollapse": ["ribcage", "abdomen", "pelvis"],
            },
            "secondarySupport": [
                {"id": "hindpaw_L", "role": "stabilizer", "maySlide": False},
                {"id": "hindpaw_R", "role": "stabilizer", "maySlide": False},
            ],
            "releasedDuringCover": [
                {"id": "forepaw_L", "releaseProgress": 0.12, "target": "eye_cover_zone_L"},
                {"id": "forepaw_R", "releaseProgress": 0.12, "target": "eye_cover_zone_R"},
            ],
        },
        "momentSimulation": {
            "status": "split-physical-and-control-preflight",
            "physicalMomentPreflight": {
                "method": "2D front-plane qualitative tau = r x F using distal gravity, lift inertia, and face contact reaction",
                "chain": ["scapula", "shoulder", "elbow", "wrist", "forepaw", "eye_cover_zone"],
                "forceModel": {
                    "distalGravity": "downward force applied at forepaw",
                    "liftInertia": "upward transient force during lift",
                    "faceContactReaction": "normal reaction from eye-cover zone when progress approaches cover",
                },
                "signConvention": "positive tau is counter-clockwise in the X2 front-plane drawing; left/right signs are expected to mirror",
                "summary": physical_summary,
                "interpretation": "Checks whether external force direction and lever arms agree with the intended cover pose. This is not a calibrated animal dynamics solve.",
            },
            "controlMomentPreflight": {
                "method": "active joint curve with qualitative demand = active angle demand + distal load + velocity load",
                "chain": ["scapula", "shoulder", "elbow", "wrist", "forepaw", "eye_cover_zone"],
                "summary": control_summary,
                "interpretation": "Checks whether the Motion-like drive can remain smooth and avoid a single saturated joint.",
            },
        },
        "continuity": continuity,
        "samplePaths": {
            "roundtripSamples": str(SAMPLES_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
            "supportMap": str(SUPPORT_MAP_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
            "blockoutSheet": str(BLOCKOUT_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
            "controlMomentDemand": str(TORQUE_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
            "physicalMomentDemand": str(PHYSICAL_TORQUE_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
            "fullMomentReviewSheet": str(FULL_MOMENT_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
            "intuitiveMomentCoverPreview": str(INTUITIVE_PREVIEW_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
            "intuitiveMomentCoverPreviewGif": str(INTUITIVE_GIF_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
            "report": str(REPORT_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
        },
        "futureLayerAndMeshPolicy": {
            "sourceReference": "Zhihu article opened by user: Live2D动画引擎的图形学原理及实现",
            "sequence": [
                "X2 user approval for support and cover blockout",
                "X3 complete connected spread-pose/continuous master from approved body",
                "X3 user approval",
                "X4 detailed semantic layer images from the approved master",
                "Delaunay-style triangulation per actual layer boundary",
                "helper mesh nodes and elastic coefficients after layer boundaries exist"
            ],
            "rules": [
                "Do not use bone length changes to simulate swing or elasticity",
                "Every real layer will own a mesh and exactly one primary node in the later mesh-node contract",
                "Triangulation must happen on actual layer point sets and layer boundaries, not on the X2 blockout alone",
                "Elastic coefficients belong to mesh vertices after triangulation; farther soft vertices may have higher elasticity while anatomical pivots remain stable"
            ]
        },
        "gatePolicy": {
            "x2MayPassOnlyWithUserApproval": True,
            "x3Authorized": False,
            "forbiddenBeforeX2Approval": [
                "complete-master-generation",
                "realistic-spread-pose-three-view",
                "material-separation",
                "photoshop-import",
                "cubism-editing",
            ],
        },
    }


def draw_chain(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]], color: tuple[int, int, int, int], width: int = 5) -> None:
    projected = [p(pt) for pt in pts]
    draw.line(projected, fill=color, width=width)
    for x, y in projected:
        draw.ellipse([x - 7, y - 7, x + 7, y + 7], fill=color, outline=(30, 30, 30, 230), width=2)


def draw_support_map(x1: dict, samples: list[dict]) -> None:
    img = Image.new("RGBA", CANVAS, COLORS["bg"])
    draw = ImageDraw.Draw(img, "RGBA")
    title = load_font(30, True)
    label = load_font(16, True)
    small = load_font(13)
    draw.text((45, 28), "X2 CONTACT / COM / SUPPORT MAP", font=title, fill=(18, 58, 92, 255))
    draw.text((45, 66), "Low-detail solve only: support and moments before any master image, layers, ArtMesh, or Cubism.", font=small, fill=(85, 85, 85, 255))
    draw.rounded_rectangle([70, 110, 1430, 905], radius=18, fill=COLORS["panel"], outline=(30, 120, 200, 150), width=3)

    # Planet proxy and contact band.
    planet_box = [p((-0.58, 0.16))[0], p((0.0, 0.16))[1], p((0.58, -0.38))[0], p((0.0, -0.38))[1]]
    draw.ellipse(planet_box, fill=(90, 130, 225, 55), outline=(60, 95, 190, 180), width=4)
    band_y = 0.205
    draw.rounded_rectangle([p((-0.31, band_y + 0.02))[0], p((0, band_y + 0.02))[1], p((0.31, band_y - 0.035))[0], p((0, band_y - 0.035))[1]], radius=12, fill=COLORS["contact"], outline=COLORS["reaction"], width=3)
    draw.text((p((-0.31, band_y + 0.03))[0], p((0, band_y + 0.03))[1] - 22), "chest/belly contact band", font=label, fill=COLORS["reaction"])

    for name, block in x1["massBlocks"].items():
        cx, cy, _ = block["center"]
        rx, ry, _ = block["radii"]
        x, y = p((cx, cy))
        draw.ellipse([x - rx * SCALE, y - ry * SCALE, x + rx * SCALE, y + ry * SCALE], fill=COLORS["mass"], outline=(50, 150, 210, 165), width=3)
        draw.text((x - rx * SCALE + 6, y - ry * SCALE + 5), name.upper(), font=small, fill=(35, 95, 135, 230))

    support_x = samples[0]["supportHullX"]
    draw.line([p((support_x[0], -0.02)), p((support_x[0], 0.53))], fill=(40, 145, 80, 100), width=3)
    draw.line([p((support_x[1], -0.02)), p((support_x[1], 0.53))], fill=(40, 145, 80, 100), width=3)
    draw.text((p((support_x[0], 0.55))[0] - 14, p((support_x[0], 0.55))[1]), "support hull X", font=label, fill=(40, 145, 80, 230))

    for sample, name in [(samples[0], "REST"), (samples[10], "MID ENTER"), (samples[20], "COVER")]:
        com = tuple(sample["centerOfMass"])
        x, y = p(com)
        draw.ellipse([x - 9, y - 9, x + 9, y + 9], fill=COLORS["com"], outline=(255, 255, 255, 230), width=2)
        draw.line([x, y, x, p((com[0], -0.02))[1]], fill=(255, 65, 55, 125), width=2)
        draw.text((x + 12, y - 8), name, font=small, fill=COLORS["com"])

    # Key cover chains.
    for side, color in (("L", COLORS["left"]), ("R", COLORS["right"])):
        pts = [tuple(samples[20]["sides"][side]["joints"][f"{name}_{side}"]) for name in ("scapula", "shoulder", "elbow", "wrist", "forepaw")]
        draw_chain(draw, pts, color, 6)
        target = tuple(samples[20]["sides"][side]["target"])
        tx, ty = p(target)
        draw.ellipse([tx - 18, ty - 24, tx + 18, ty + 24], outline=COLORS["target"], width=3)
        draw.text((tx + 20, ty - 8), f"eye cover {side}", font=small, fill=(165, 70, 40, 255))

    draw.text((90, 875), "Result to review: COM stays inside support hull while forepaws release; ribcage/abdomen/pelvis volumes are not scaled.", font=small, fill=(60, 70, 80, 255))
    img.convert("RGB").save(SUPPORT_MAP_PATH)


def draw_blockout_sheet(samples: list[dict]) -> None:
    width, height = 1600, 1120
    img = Image.new("RGBA", (width, height), COLORS["bg"])
    draw = ImageDraw.Draw(img, "RGBA")
    title = load_font(29, True)
    label = load_font(13, True)
    draw.text((35, 24), "X2 0 -> 1 -> 0 COVER BLOCKOUT, 9 KEY FRAMES FROM 41 SAMPLES", font=title, fill=(18, 58, 92, 255))
    indices = [0, 5, 10, 15, 20, 25, 30, 35, 40]
    cell_w, cell_h = 500, 320
    start_x, start_y = 42, 84

    def local_project(pt: tuple[float, float], ox: float, oy: float) -> tuple[float, float]:
        return ox + pt[0] * 320, oy - pt[1] * 320

    for n, index in enumerate(indices):
        sample = samples[index]
        col = n % 3
        row = n // 3
        x0 = start_x + col * (cell_w + 18)
        y0 = start_y + row * (cell_h + 22)
        draw.rounded_rectangle([x0, y0, x0 + cell_w, y0 + cell_h], radius=14, fill=COLORS["panel"], outline=(30, 120, 200, 130), width=2)
        ox, oy = x0 + cell_w / 2, y0 + 280
        draw.ellipse([ox - 135, oy - 82, ox + 135, oy + 64], fill=(90, 130, 225, 45), outline=(60, 95, 190, 130), width=2)
        draw.rounded_rectangle([ox - 76, oy - 205, ox + 76, oy - 35], radius=60, fill=(50, 180, 255, 38), outline=(50, 150, 210, 135), width=2)
        draw.ellipse([ox - 118, oy - 150, ox + 118, oy + 10], fill=(40, 220, 170, 38), outline=(40, 165, 130, 135), width=2)
        draw.ellipse([ox - 108, oy - 70, ox + 108, oy + 55], fill=(255, 190, 40, 34), outline=(190, 140, 35, 125), width=2)
        for side, color in (("L", COLORS["left"]), ("R", COLORS["right"])):
            pts = [tuple(sample["sides"][side]["joints"][f"{name}_{side}"]) for name in ("scapula", "shoulder", "elbow", "wrist", "forepaw")]
            projected = [local_project(pt, ox, oy) for pt in pts]
            draw.line(projected, fill=color, width=5)
            for px, py in projected:
                draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=color, outline=(20, 20, 20, 220), width=1)
        com = local_project(tuple(sample["centerOfMass"]), ox, oy)
        draw.ellipse([com[0] - 6, com[1] - 6, com[0] + 6, com[1] + 6], fill=COLORS["com"], outline=(255, 255, 255, 230), width=1)
        draw.text((x0 + 14, y0 + 12), f"sample {index:02d}  p={sample['coverProgress']:.2f}", font=label, fill=(25, 55, 85, 255))
        draw.text((x0 + 14, y0 + 34), f"{sample['phase']}  support={sample['supportOk']}", font=label, fill=(60, 70, 80, 255))
    img.convert("RGB").save(BLOCKOUT_PATH)


def draw_torque_chart(samples: list[dict]) -> None:
    width, height = 1500, 850
    img = Image.new("RGBA", (width, height), COLORS["bg"])
    draw = ImageDraw.Draw(img, "RGBA")
    title = load_font(30, True)
    label = load_font(15, True)
    small = load_font(12)
    draw.text((45, 28), "X2 CONTROL MOMENT PREFLIGHT", font=title, fill=(18, 58, 92, 255))
    draw.text((45, 66), "Dimensionless demand from active angle, distal load, and velocity load; separate from physical tau = r x F.", font=small, fill=(85, 85, 85, 255))
    chart = [110, 130, 1400, 720]
    draw.rounded_rectangle(chart, radius=12, fill=COLORS["panel"], outline=(30, 120, 200, 130), width=2)
    x0, y0, x1, y1 = chart
    for k in range(6):
        y = y1 - (y1 - y0) * k / 5
        draw.line([x0 + 45, y, x1 - 30, y], fill=(80, 105, 125, 65), width=1)
        draw.text((x0 + 10, y - 8), f"{k/5:.1f}", font=small, fill=(60, 70, 80, 255))
    draw.text((x0 + 10, y0 + 12), "relative demand", font=small, fill=(60, 70, 80, 255))

    series = [
        ("L scapula", "L", "scapula", (255, 115, 220, 235)),
        ("L shoulder", "L", "shoulder", (255, 65, 205, 240)),
        ("L elbow", "L", "elbow", (190, 65, 235, 230)),
        ("L wrist", "L", "wrist", (130, 75, 245, 230)),
        ("R scapula", "R", "scapula", (255, 225, 95, 235)),
        ("R shoulder", "R", "shoulder", (255, 205, 45, 240)),
        ("R elbow", "R", "elbow", (255, 155, 45, 230)),
        ("R wrist", "R", "wrist", (235, 105, 35, 230)),
    ]
    plot_x0, plot_x1 = x0 + 55, x1 - 40
    plot_y0, plot_y1 = y0 + 35, y1 - 35
    for name, side, joint, color in series:
        pts = []
        for sample in samples:
            x = plot_x0 + (plot_x1 - plot_x0) * sample["index"] / 40
            demand = sample["sides"][side]["moments"][joint]["relativeDemand"]
            y = plot_y1 - (plot_y1 - plot_y0) * demand
            pts.append((x, y))
        draw.line(pts, fill=color, width=3)
    legend_x = 140
    for idx, (name, _, _, color) in enumerate(series):
        lx = legend_x + (idx % 3) * 245
        ly = 760 + (idx // 3) * 26
        draw.line([lx, ly + 8, lx + 34, ly + 8], fill=color, width=4)
        draw.text((lx + 42, ly), name, font=label, fill=(30, 45, 60, 255))
    draw.text((1010, 760), "Review focus: demand should rise smoothly, peak near cover, then return without jumps.", font=small, fill=(70, 70, 80, 255))
    img.convert("RGB").save(TORQUE_PATH)


def draw_physical_torque_chart(samples: list[dict]) -> None:
    width, height = 1500, 880
    img = Image.new("RGBA", (width, height), COLORS["bg"])
    draw = ImageDraw.Draw(img, "RGBA")
    title = load_font(30, True)
    label = load_font(15, True)
    small = load_font(12)
    draw.text((45, 28), "X2 PHYSICAL MOMENT PREFLIGHT  tau = r x F", font=title, fill=(18, 58, 92, 255))
    draw.text((45, 66), "External-force proxy: distal gravity + lift inertia + face contact reaction. It checks signs and lever arms, not calibrated cat dynamics.", font=small, fill=(85, 85, 85, 255))
    chart = [110, 130, 1400, 735]
    draw.rounded_rectangle(chart, radius=12, fill=COLORS["panel"], outline=(30, 120, 200, 130), width=2)
    x0, y0, x1, y1 = chart
    for k in range(6):
        y = y1 - (y1 - y0) * k / 5
        draw.line([x0 + 45, y, x1 - 30, y], fill=(80, 105, 125, 65), width=1)
        draw.text((x0 + 10, y - 8), f"{k/5:.1f}", font=small, fill=(60, 70, 80, 255))
    draw.text((x0 + 10, y0 + 12), "relative |tau|", font=small, fill=(60, 70, 80, 255))

    series = [
        ("L scapula", "L", "scapula", (255, 115, 220, 235)),
        ("L shoulder", "L", "shoulder", (255, 65, 205, 240)),
        ("L elbow", "L", "elbow", (190, 65, 235, 230)),
        ("L wrist", "L", "wrist", (130, 75, 245, 230)),
        ("R scapula", "R", "scapula", (255, 225, 95, 235)),
        ("R shoulder", "R", "shoulder", (255, 205, 45, 240)),
        ("R elbow", "R", "elbow", (255, 155, 45, 230)),
        ("R wrist", "R", "wrist", (235, 105, 35, 230)),
    ]
    plot_x0, plot_x1 = x0 + 55, x1 - 40
    plot_y0, plot_y1 = y0 + 35, y1 - 35
    for _, side, joint, color in series:
        pts = []
        for sample in samples:
            x = plot_x0 + (plot_x1 - plot_x0) * sample["index"] / 40
            demand = sample["sides"][side]["physicalMoments"][joint]["relativeDemand"]
            y = plot_y1 - (plot_y1 - plot_y0) * demand
            pts.append((x, y))
        draw.line(pts, fill=color, width=3)
    legend_x = 140
    for idx, (name, _, _, color) in enumerate(series):
        lx = legend_x + (idx % 3) * 245
        ly = 775 + (idx // 3) * 26
        draw.line([lx, ly + 8, lx + 34, ly + 8], fill=color, width=4)
        draw.text((lx + 42, ly), name, font=label, fill=(30, 45, 60, 255))
    draw.text((1010, 775), "Review focus: physical tau signs should agree with lift, contact, and support.", font=small, fill=(70, 70, 80, 255))
    img.convert("RGB").save(PHYSICAL_TORQUE_PATH)


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    color: tuple[int, int, int, int],
    width: int = 4,
) -> None:
    draw.line([start, end], fill=color, width=width)
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    head = [
        end,
        (end[0] - ux * 15 + px * 7, end[1] - uy * 15 + py * 7),
        (end[0] - ux * 15 - px * 7, end[1] - uy * 15 - py * 7),
    ]
    draw.polygon(head, fill=color)


def draw_full_moment_review_sheet(samples: list[dict]) -> None:
    width, height = 1800, 1040
    img = Image.new("RGBA", (width, height), COLORS["bg"])
    draw = ImageDraw.Draw(img, "RGBA")
    title = load_font(30, True)
    label = load_font(15, True)
    small = load_font(12)
    tiny = load_font(11)
    draw.text((45, 28), "X2 FULL MOMENT REVIEW: SCAPULA -> SHOULDER -> ELBOW -> WRIST -> PAW", font=title, fill=(18, 58, 92, 255))
    draw.text((45, 66), "Cover-frame force and lever-arm sketch. Blue is lift inertia, gray is gravity, orange is face contact reaction; bars show signed tau.", font=small, fill=(85, 85, 85, 255))

    sample = samples[20]
    panels = {"L": (55, 115, 820, 535), "R": (55, 555, 820, 975)}

    for side, (x0, y0, x1, y1) in panels.items():
        color = COLORS["left"] if side == "L" else COLORS["right"]
        draw.rounded_rectangle([x0, y0, x1, y1], radius=12, fill=COLORS["panel"], outline=(30, 120, 200, 130), width=2)
        draw.text((x0 + 18, y0 + 16), f"{side} forelimb cover-frame moment sketch", font=label, fill=(25, 55, 85, 255))
        pts = {
            name: tuple(sample["sides"][side]["joints"][f"{name}_{side}"])
            for name in ("scapula", "shoulder", "elbow", "wrist", "forepaw")
        }
        target = tuple(sample["sides"][side]["target"])
        fit_points = list(pts.values()) + [target]
        min_x = min(pt[0] for pt in fit_points)
        max_x = max(pt[0] for pt in fit_points)
        min_y = min(pt[1] for pt in fit_points)
        max_y = max(pt[1] for pt in fit_points)
        center_x = (min_x + max_x) * 0.5
        center_y = (min_y + max_y) * 0.5
        fit_scale = min(520.0 / max(0.001, max_x - min_x), 300.0 / max(0.001, max_y - min_y))
        panel_center = (x0 + 400, y0 + 235)

        def local_project(pt: tuple[float, float]) -> tuple[float, float]:
            return (
                panel_center[0] + (pt[0] - center_x) * fit_scale,
                panel_center[1] - (pt[1] - center_y) * fit_scale,
            )

        projected = [local_project(pts[name]) for name in ("scapula", "shoulder", "elbow", "wrist", "forepaw")]
        draw.line(projected, fill=color, width=6)
        for name, point in pts.items():
            px, py = local_project(point)
            radius = 8 if name != "forepaw" else 10
            draw.ellipse([px - radius, py - radius, px + radius, py + radius], fill=color, outline=(25, 25, 25, 230), width=2)
            draw.text((px + 10, py - 12), name, font=tiny, fill=(25, 35, 45, 255))

        tx, ty = local_project(target)
        draw.ellipse([tx - 22, ty - 28, tx + 22, ty + 28], outline=COLORS["target"], width=3)
        draw.text((tx + 24, ty - 10), "eye cover target", font=tiny, fill=(145, 65, 35, 255))

        paw_screen = local_project(pts["forepaw"])
        components = sample["sides"][side]["physicalMoments"]["wrist"]["components"]
        force_scale_px = 1050.0
        force_colors = {
            "distalGravity": (80, 85, 95, 220),
            "liftInertia": (40, 135, 220, 220),
            "faceReaction": (235, 115, 30, 230),
        }
        for component_name in ("distalGravity", "liftInertia", "faceReaction"):
            fx, fy = components[component_name]
            end = (paw_screen[0] + fx * force_scale_px, paw_screen[1] - fy * force_scale_px)
            draw_arrow(draw, paw_screen, end, force_colors[component_name], 4)
            draw.text((end[0] + 6, end[1] - 7), component_name, font=tiny, fill=force_colors[component_name])

        for joint in ("scapula", "shoulder", "elbow", "wrist"):
            start = local_project(pts[joint])
            draw.line([start, paw_screen], fill=(90, 95, 110, 80), width=2)
            tau = sample["sides"][side]["physicalMoments"][joint]["signedTau"]
            sign = "+" if tau > 0 else "-" if tau < 0 else "0"
            draw.text((start[0] - 36, start[1] + 12), f"tau {sign}", font=tiny, fill=(65, 55, 105, 245))

    chart = [900, 135, 1735, 925]
    draw.rounded_rectangle(chart, radius=12, fill=COLORS["panel"], outline=(30, 120, 200, 130), width=2)
    draw.text((chart[0] + 22, chart[1] + 18), "Cover-frame signed tau and component checks", font=label, fill=(25, 55, 85, 255))
    bar_x0 = chart[0] + 250
    zero_x = chart[0] + 505
    y = chart[1] + 70
    max_abs_tau = max(
        abs(sample["sides"][side]["physicalMoments"][joint]["signedTau"])
        for side in ("L", "R")
        for joint in ("scapula", "shoulder", "elbow", "wrist")
    )
    max_abs_tau = max(max_abs_tau, 1e-6)
    draw.line([zero_x, y - 22, zero_x, chart[3] - 105], fill=(50, 70, 90, 150), width=2)
    for side in ("L", "R"):
        for joint in ("scapula", "shoulder", "elbow", "wrist"):
            item = sample["sides"][side]["physicalMoments"][joint]
            tau = item["signedTau"]
            rel = item["relativeDemand"]
            width_px = tau / max_abs_tau * 245
            color = COLORS["left"] if side == "L" else COLORS["right"]
            draw.text((chart[0] + 26, y - 10), f"{side} {joint}", font=small, fill=(35, 45, 60, 255))
            x_end = zero_x + width_px
            draw.rounded_rectangle([min(zero_x, x_end), y - 10, max(zero_x, x_end), y + 10], radius=5, fill=color)
            draw.text((chart[0] + 610, y - 10), f"tau={tau:+.5f} d={rel:.3f}", font=small, fill=(45, 55, 70, 255))
            component_text = ", ".join(f"{k}:{v:+.4f}" for k, v in item["componentTorques"].items())
            draw.text((chart[0] + 26, y + 13), component_text, font=tiny, fill=(75, 80, 90, 255))
            y += 74

    draw.text((chart[0] + 22, chart[3] - 70), "Gate note: this is still X2 low-detail biomechanics evidence, not X3 master art or Cubism Physics.", font=small, fill=(70, 70, 80, 255))
    img.convert("RGB").save(FULL_MOMENT_PATH)


def draw_intuitive_cover_frame(
    sample: dict,
    size: tuple[int, int],
    title_text: str,
    note_text: str,
) -> Image.Image:
    width, height = size
    img = Image.new("RGBA", size, (246, 249, 252, 255))
    draw = ImageDraw.Draw(img, "RGBA")
    title = load_font(21, True)
    label = load_font(15, True)
    small = load_font(12)
    tiny = load_font(10)

    draw.rounded_rectangle([18, 18, width - 18, height - 18], radius=14, fill=(255, 255, 255, 245), outline=(30, 120, 200, 130), width=2)
    draw.text((34, 30), title_text, font=title, fill=(18, 58, 92, 255))
    draw.text((34, 62), note_text, font=small, fill=(76, 80, 86, 255))

    cx, ground = width * 0.52, height * 0.83
    scale = 440.0

    def lp(pt: tuple[float, float]) -> tuple[float, float]:
        return (cx + pt[0] * scale, ground - pt[1] * scale)

    progress = sample["coverProgress"]
    # Planet and non-deforming contact band.
    draw.ellipse([cx - 178, ground - 105, cx + 178, ground + 74], fill=(84, 128, 230, 62), outline=(58, 92, 180, 160), width=3)
    draw.rounded_rectangle([cx - 110, ground - 170, cx + 110, ground - 128], radius=16, fill=(60, 210, 120, 95), outline=(35, 145, 75, 200), width=2)
    draw.text((cx - 106, ground - 198), "胸腹接触带锁住支撑", font=small, fill=(35, 120, 70, 255))

    # Body masses: intentionally simple X2 blockout, not master art.
    body_y = ground - 170 - progress * 4
    head_y = body_y - 120
    draw.ellipse([cx - 92, body_y - 74, cx + 92, body_y + 42], fill=(246, 164, 54, 165), outline=(150, 92, 35, 210), width=3)
    draw.ellipse([cx - 78, head_y - 70, cx + 78, head_y + 60], fill=(246, 164, 54, 185), outline=(150, 92, 35, 220), width=3)
    draw.polygon([(cx - 58, head_y - 48), (cx - 30, head_y - 86), (cx - 14, head_y - 45)], fill=(246, 164, 54, 165), outline=(150, 92, 35, 210))
    draw.polygon([(cx + 58, head_y - 48), (cx + 30, head_y - 86), (cx + 14, head_y - 45)], fill=(246, 164, 54, 165), outline=(150, 92, 35, 210))
    eye_l = (cx - 28, head_y - 8)
    eye_r = (cx + 28, head_y - 8)
    for ex, ey in (eye_l, eye_r):
        draw.ellipse([ex - 10, ey - 8, ex + 10, ey + 8], fill=(28, 34, 42, 230))
    draw.arc([cx - 20, head_y + 14, cx + 20, head_y + 40], 15, 165, fill=(115, 70, 45, 220), width=2)

    # COM and support hint.
    com = tuple(sample["centerOfMass"])
    com_screen = lp(com)
    draw.ellipse([com_screen[0] - 7, com_screen[1] - 7, com_screen[0] + 7, com_screen[1] + 7], fill=(255, 64, 58, 245), outline=(255, 255, 255, 240), width=2)
    draw.line([com_screen[0], com_screen[1], com_screen[0], ground - 90], fill=(255, 64, 58, 130), width=2)
    draw.text((com_screen[0] + 10, com_screen[1] - 8), "重心仍在支撑里", font=tiny, fill=(190, 50, 45, 255))

    side_colors = {"L": COLORS["left"], "R": COLORS["right"]}
    joint_label_offsets = {
        "scapula": (-54, -6),
        "shoulder": (8, 8),
        "elbow": (8, -10),
        "wrist": (8, -14),
        "forepaw": (8, -18),
    }
    for side in ("L", "R"):
        joints = sample["sides"][side]["joints"]
        pts = [tuple(joints[f"{name}_{side}"]) for name in ("scapula", "shoulder", "elbow", "wrist", "forepaw")]
        screen_pts = [lp(pt) for pt in pts]
        draw.line(screen_pts, fill=side_colors[side], width=7)
        for name, (x, y) in zip(("scapula", "shoulder", "elbow", "wrist", "forepaw"), screen_pts):
            radius = 7 if name != "forepaw" else 10
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=side_colors[side], outline=(28, 28, 32, 230), width=2)
            if progress >= 0.18 or name in ("scapula", "shoulder"):
                dx, dy = joint_label_offsets[name]
                zh = {"scapula": "肩胛", "shoulder": "肩", "elbow": "肘", "wrist": "腕", "forepaw": "爪"}[name]
                draw.text((x + dx, y + dy), zh, font=tiny, fill=(35, 35, 50, 245))

        paw = screen_pts[-1]
        target = lp(tuple(sample["sides"][side]["target"]))
        draw.ellipse([target[0] - 24, target[1] - 30, target[0] + 24, target[1] + 30], outline=(255, 110, 35, 190), width=3)
        if progress > 0.05:
            draw_arrow(draw, screen_pts[1], screen_pts[2], (50, 105, 230, 210), 3)
            draw_arrow(draw, screen_pts[2], screen_pts[3], (50, 105, 230, 210), 3)
            draw_arrow(draw, screen_pts[3], paw, (50, 105, 230, 210), 3)
        if progress > 0.82:
            draw_arrow(draw, paw, target, (235, 115, 30, 220), 3)
            paw_fill = (255, 145, 215, 105) if side == "L" else (255, 215, 80, 105)
            draw.ellipse([target[0] - 30, target[1] - 24, target[0] + 30, target[1] + 24], fill=paw_fill, outline=side_colors[side], width=3)
            draw.text((target[0] - 22, target[1] + 25), "掌面盖眼", font=tiny, fill=(70, 45, 55, 245))

    stage_lines = [
        ("1 肩胛", "近端稳定，把力传回身体"),
        ("2 肩", "先抬起整条前肢"),
        ("3 肘", "向内折叠，缩短到眼前"),
        ("4 腕/爪", "最后贴近眼眶，不靠拉长骨段"),
    ]
    box_x, box_y = 34, height - 168
    for i, (head, body) in enumerate(stage_lines):
        y = box_y + i * 34
        active = progress >= i * 0.22
        fill = (255, 247, 224, 255) if active else (235, 239, 244, 255)
        outline = (225, 150, 50, 210) if active else (140, 150, 160, 120)
        draw.rounded_rectangle([box_x, y, box_x + 270, y + 25], radius=8, fill=fill, outline=outline, width=1)
        draw.text((box_x + 10, y + 4), head, font=small, fill=(75, 55, 35, 255))
        draw.text((box_x + 82, y + 5), body, font=tiny, fill=(70, 74, 82, 255))

    draw.text((width - 310, height - 52), "X2块面预览，不是X3母版/拆层", font=small, fill=(85, 86, 92, 255))
    return img.convert("RGB")


def draw_intuitive_moment_preview(samples: list[dict]) -> None:
    indices = [0, 6, 12, 20, 28, 34]
    titles = [
        "Rest：爪仍在低位",
        "释放：胸腹支撑",
        "抬起：肩先带",
        "Cover：掌面盖眼",
        "退出：沿链回落",
        "回稳：回支撑姿态",
    ]
    notes = [
        "力矩几乎不需要抬爪，只保持身体不塌。",
        "前爪离开星球，重心仍落在胸腹接触带内。",
        "肩胛不乱跑，肩部先把整条前肢抬起来。",
        "腕在外侧，掌面从外向内盖住眼睛。",
        "力矩方向反向释放，骨段长度仍锁住。",
        "爪回到低位，身体只做低幅补偿。",
    ]
    frame_w, frame_h = 640, 520
    sheet = Image.new("RGB", (frame_w * 3, frame_h * 2), (246, 249, 252))
    frames = []
    for n, index in enumerate(indices):
        frame = draw_intuitive_cover_frame(samples[index], (frame_w, frame_h), titles[n], notes[n])
        frames.append(frame)
        sheet.paste(frame, ((n % 3) * frame_w, (n // 3) * frame_h))
    sheet.save(INTUITIVE_PREVIEW_PATH)

    gif_frames = [
        draw_intuitive_cover_frame(samples[index], (frame_w, frame_h), titles[min(n, len(titles) - 1)], notes[min(n, len(notes) - 1)])
        for n, index in enumerate([0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40])
    ]
    gif_frames[0].save(
        INTUITIVE_GIF_PATH,
        save_all=True,
        append_images=gif_frames[1:],
        duration=260,
        loop=0,
    )


def write_report(contract: dict, samples: list[dict]) -> None:
    continuity = contract["continuity"]
    max_left_cover = min(s["sides"]["L"]["distanceToEyeCoverZone"] for s in samples)
    max_right_cover = min(s["sides"]["R"]["distanceToEyeCoverZone"] for s in samples)
    peak_demands = {}
    peak_physical_demands = {}
    physical_cover_signs = {}
    for side in ("L", "R"):
        peak_demands[side] = {}
        peak_physical_demands[side] = {}
        physical_cover_signs[side] = {}
        for joint in ("scapula", "shoulder", "elbow", "wrist"):
            peak_demands[side][joint] = max(s["sides"][side]["moments"][joint]["relativeDemand"] for s in samples)
            peak_physical_demands[side][joint] = max(s["sides"][side]["physicalMoments"][joint]["relativeDemand"] for s in samples)
            tau = samples[20]["sides"][side]["physicalMoments"][joint]["signedTau"]
            physical_cover_signs[side][joint] = "+" if tau > 0 else "-" if tau < 0 else "0"

    report = f"""# 小橘 X2 支撑与遮眼动作求解报告

> 状态：候选，等待用户 X2 Gate 审核。本文不授权生成完整母版、实际大字型三视图、拆层、PSD 或 Cubism。

## X2 边界

本阶段只验证从已批准的 X1 统一身体出发，遮眼链是否能在低细节块面中由肩、肘、腕和前爪连续带动，同时胸腹与星球接触是否能维持支撑。

禁止项保持不变：不生成写实小橘母版，不生成实际大字型三视图，不拆层，不建 ArtMesh/Deformer/Physics，不进入运行时。

## 产物

- `x2-pose-solve-contract.json`：接触、支撑、力矩和 Gate 合同。
- `x2-cover-roundtrip-samples.json`：41 个 `Rest -> Cover -> Rest` 采样点。
- `qa/x2-contact-support-map.png`：接触带、支撑范围和 COM 投影。
- `qa/x2-cover-roundtrip-blockout-sheet.png`：9 张关键帧块面图，来自 41 采样。
- `qa/x2-moment-demand-preflight.png`：控制力矩需求趋势。
- `qa/x2-physical-moment-preflight.png`：物理 `tau = r x F` 力矩趋势。
- `qa/x2-full-moment-review-sheet.png`：肩胛、肩、肘、腕的 cover 帧力臂、外力分量和 signed tau 审阅图。
- `qa/x2-intuitive-moment-cover-preview.png`：面向视觉审核的 6 格直观动作预览。
- `qa/x2-intuitive-moment-cover-preview.gif`：同一 X2 块面动作的慢速往返预览。

## 自动核验

- 采样数量：{continuity['sampleCount']}
- 最大骨段长度漂移：{continuity['maxSegmentLengthDrift']:.8f}
- 最大单采样角度步进：{continuity['maxSingleSampleAngleStepDeg']:.4f} deg
- 峰值控制力矩需求：{continuity['peakRelativeMomentDemand']:.4f}
- 峰值物理力矩需求：{continuity['peakPhysicalMomentDemand']:.4f}
- COM 全采样位于支撑范围：{continuity['supportOkAllSamples']}
- Cover 附近双爪接触眼部目标区：{continuity['faceContactOccursAtCover']}
- 左爪最小目标距离：{max_left_cover:.5f}
- 右爪最小目标距离：{max_right_cover:.5f}

## 物理力矩预检结论

物理层使用 `tau = r x F`，其中 `F` 由远端重力、抬升惯性和接触脸部后的反作用力组成。它检查外力方向、力臂和关节顺序是否符合最初讨论的力矩链。

| Side | Scapula | Shoulder | Elbow | Wrist |
| --- | ---: | ---: | ---: | ---: |
| L | {peak_physical_demands['L']['scapula']:.3f} | {peak_physical_demands['L']['shoulder']:.3f} | {peak_physical_demands['L']['elbow']:.3f} | {peak_physical_demands['L']['wrist']:.3f} |
| R | {peak_physical_demands['R']['scapula']:.3f} | {peak_physical_demands['R']['shoulder']:.3f} | {peak_physical_demands['R']['elbow']:.3f} | {peak_physical_demands['R']['wrist']:.3f} |

Cover 帧物理力矩符号：

| Side | Scapula | Shoulder | Elbow | Wrist |
| --- | :---: | :---: | :---: | :---: |
| L | {physical_cover_signs['L']['scapula']} | {physical_cover_signs['L']['shoulder']} | {physical_cover_signs['L']['elbow']} | {physical_cover_signs['L']['wrist']} |
| R | {physical_cover_signs['R']['scapula']} | {physical_cover_signs['R']['shoulder']} | {physical_cover_signs['R']['elbow']} | {physical_cover_signs['R']['wrist']} |

这层不替代真实动物动力学，也不写 Cubism 参数；它只回答“外力和接触反力沿这条链传回去时，肩胛、肩、肘、腕的符号和相对大小是否合理”。符号约定为 X2 正视图中逆时针为正，左右两侧预期镜像。

## 控制力矩预检结论

控制层使用主动角度需求、末端负载和速度负载，检查后续 Motion 曲线能不能平滑带动这条链，避免把所有负担压在一个关节上。

| Side | Scapula | Shoulder | Elbow | Wrist |
| --- | ---: | ---: | ---: | ---: |
| L | {peak_demands['L']['scapula']:.3f} | {peak_demands['L']['shoulder']:.3f} | {peak_demands['L']['elbow']:.3f} | {peak_demands['L']['wrist']:.3f} |
| R | {peak_demands['R']['scapula']:.3f} | {peak_demands['R']['shoulder']:.3f} | {peak_demands['R']['elbow']:.3f} | {peak_demands['R']['wrist']:.3f} |

本版把旧的“目标误差力”改为“主动角度需求 + 末端负载 + 速度负载”的力矩代理，避免 rest 状态误判为肩部满负载。现在肩胛承担近端稳定和负载传递，肩部主导抬升，肘部承担折叠，腕部只做低幅贴合；需求曲线随遮眼进度平滑升高并在返回段下降。该结论只是 X2 块面依据，不是 Cubism 参数、弹簧刚度或真实动物动力学数值。

## X2 修订：力矩优化

本轮按用户意见把 X2 力矩拆成双轨：`physicalMomentPreflight` 保留最初讨论的外力/力臂逻辑，`controlMomentPreflight` 只负责 Motion 曲线带动是否平滑。优化后峰值控制力矩需求为 {continuity['peakRelativeMomentDemand']:.4f}，峰值物理力矩需求为 {continuity['peakPhysicalMomentDemand']:.4f}，双爪到眼部目标区的最小距离为 L {max_left_cover:.5f} / R {max_right_cover:.5f}。

## 后续图层与三角剖分顺序

根据用户指定的知乎文章《Live2D动画引擎的图形学原理及实现》，后续实现应遵守这个顺序：先有实际图层边界，再为每个图层建立三角网格；图层由唯一节点控制，节点再组成父子骨骼；弹性系数属于网格顶点级的后续模拟，而不是让 X2 骨段变长。

因此当前 X2 不生成分层图片、不打正式三角剖分辅助点，也不分配弹性顶点。正确顺序应为：

1. X2 遮眼支撑块面通过；
2. X3 生成完整连续大字型/展开母版并审核；
3. X4 从批准母版细致拆出实际语义图层；
4. 在每个真实图层边界内按 Delaunay/三角图元原则建立网格；
5. 再给远离主节点的软组织顶点配置弹性系数和阻尼。

这也解释了为什么 X2 必须继续坚持 `maxSegmentLengthDrift = 0`：视觉上的摆动、回弹和形变应交给后续图层网格与弹性顶点，而不是修改生物骨段长度。

## 人工审核点

- 胸腹与星球接触带是否符合登录场景意图；
- 前爪释放星球后，COM 是否仍让身体看起来稳定；
- 肩、肘、腕折叠方向是否符合小橘圆身体和短前肢；
- 爪心到眼部遮挡区的路径是否自然，是否需要左右爪错时；
- 低幅身体补偿是否足够，是否有肋笼、腹部或骨盆被压扁的风险。
- 是否确认 X2 只作为动作/支撑门禁，不在本阶段提前生成正式分层图片。

## Gate 结论

自动检查只说明 X2 候选内部一致，不等于 X2 通过。当前状态保持 `candidate-for-user-review`，X3 明确未授权。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    x1 = load_x1()
    samples, continuity = build_samples(x1)
    contract = make_contract(x1, samples, continuity)
    CONTRACT_PATH.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SAMPLES_PATH.write_text(json.dumps({"schemaVersion": 1, "samples": samples}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    draw_support_map(x1, samples)
    draw_blockout_sheet(samples)
    draw_torque_chart(samples)
    draw_physical_torque_chart(samples)
    draw_full_moment_review_sheet(samples)
    draw_intuitive_moment_preview(samples)
    write_report(contract, samples)
    print(
        json.dumps(
            {
                "contract": str(CONTRACT_PATH),
                "samples": str(SAMPLES_PATH),
                "report": str(REPORT_PATH),
                "supportMap": str(SUPPORT_MAP_PATH),
                "blockoutSheet": str(BLOCKOUT_PATH),
                "momentDemand": str(TORQUE_PATH),
                "physicalMomentDemand": str(PHYSICAL_TORQUE_PATH),
                "fullMomentReviewSheet": str(FULL_MOMENT_PATH),
                "intuitiveMomentCoverPreview": str(INTUITIVE_PREVIEW_PATH),
                "intuitiveMomentCoverPreviewGif": str(INTUITIVE_GIF_PATH),
                "status": contract["status"],
                "sampleCount": continuity["sampleCount"],
                "supportOkAllSamples": continuity["supportOkAllSamples"],
                "maxSegmentLengthDrift": continuity["maxSegmentLengthDrift"],
                "x3Authorized": contract["gatePolicy"]["x3Authorized"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
