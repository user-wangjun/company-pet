from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean, pstdev

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
PET_ROOT = HERE.parents[1]
SOURCE = PET_ROOT / "three-view-preview.png"
QA_DIR = HERE / "qa"
CONTRACT_PATH = HERE / "x1-canonical-body-contract.json"
REPORT_PATH = HERE / "x1-canonical-body-report.md"
OVERLAY_PATH = QA_DIR / "x1-three-view-landmark-overlay.png"
SHEET_PATH = QA_DIR / "x1-three-view-review-sheet.png"
CANONICAL_PATH = QA_DIR / "x1-canonical-skeleton-projections.png"
SPREAD_AID_PATH = QA_DIR / "x1-spread-pose-review-aid.png"


VIEWS = {
    "front": {
        "label": "FRONT",
        "ground_y": 750,
        "body_top_y": 120,
        "center_x": 292,
        "bbox": [84, 120, 550, 770],
    },
    "side": {
        "label": "LEFT SIDE",
        "ground_y": 750,
        "body_top_y": 120,
        "center_x": 875,
        "bbox": [625, 120, 1165, 770],
    },
    "back": {
        "label": "BACK",
        "ground_y": 750,
        "body_top_y": 120,
        "center_x": 1452,
        "bbox": [1250, 120, 1665, 770],
    },
}


# Anatomical left/right always means the cat's own left/right.
LANDMARKS_2D = {
    "front": {
        "skull_center": ([292, 282], "visible"),
        "jaw_center": ([292, 392], "visible"),
        "neck_base": ([292, 443], "inferred"),
        "ribcage_center": ([292, 516], "inferred"),
        "abdomen_center": ([292, 626], "inferred"),
        "pelvis_center": ([292, 655], "occluded"),
        "scapula_L": ([370, 472], "inferred"),
        "shoulder_L": ([382, 492], "inferred"),
        "elbow_L": ([399, 586], "inferred"),
        "wrist_L": ([389, 682], "inferred"),
        "forepaw_L": ([380, 730], "visible"),
        "scapula_R": ([214, 472], "inferred"),
        "shoulder_R": ([202, 492], "inferred"),
        "elbow_R": ([185, 586], "inferred"),
        "wrist_R": ([195, 682], "inferred"),
        "forepaw_R": ([204, 730], "visible"),
        "hip_L": ([412, 586], "inferred"),
        "knee_L": ([432, 652], "inferred"),
        "hock_L": ([422, 704], "inferred"),
        "hindpaw_L": ([420, 730], "visible"),
        "hip_R": ([172, 586], "inferred"),
        "knee_R": ([152, 652], "inferred"),
        "hock_R": ([162, 704], "inferred"),
        "hindpaw_R": ([164, 730], "visible"),
        "tail_root": ([292, 642], "occluded"),
        "tail_mid_1": ([440, 650], "visible"),
        "tail_mid_2": ([475, 625], "visible"),
        "tail_tip": ([478, 590], "visible"),
    },
    "side": {
        "skull_center": ([780, 286], "visible"),
        "jaw_center": ([710, 392], "visible"),
        "neck_base": ([790, 444], "inferred"),
        "ribcage_center": ([864, 516], "inferred"),
        "abdomen_center": ([906, 619], "inferred"),
        "pelvis_center": ([958, 648], "inferred"),
        "scapula_L": ([818, 470], "inferred"),
        "shoulder_L": ([797, 496], "inferred"),
        "elbow_L": ([835, 588], "inferred"),
        "wrist_L": ([758, 681], "inferred"),
        "forepaw_L": ([730, 730], "visible"),
        "scapula_R": ([826, 476], "occluded"),
        "shoulder_R": ([805, 502], "occluded"),
        "elbow_R": ([843, 594], "occluded"),
        "wrist_R": ([766, 687], "occluded"),
        "forepaw_R": ([738, 734], "partly-visible"),
        "hip_L": ([963, 586], "inferred"),
        "knee_L": ([928, 650], "inferred"),
        "hock_L": ([892, 704], "inferred"),
        "hindpaw_L": ([868, 730], "visible"),
        "hip_R": ([972, 592], "occluded"),
        "knee_R": ([937, 656], "occluded"),
        "hock_R": ([901, 710], "occluded"),
        "hindpaw_R": ([877, 734], "partly-visible"),
        "tail_root": ([1000, 640], "inferred"),
        "tail_mid_1": ([1060, 670], "visible"),
        "tail_mid_2": ([1110, 704], "visible"),
        "tail_tip": ([1090, 730], "visible"),
    },
    "back": {
        "skull_center": ([1452, 282], "visible"),
        "jaw_center": ([1452, 392], "occluded"),
        "neck_base": ([1452, 440], "inferred"),
        "ribcage_center": ([1452, 518], "inferred"),
        "abdomen_center": ([1452, 620], "inferred"),
        "pelvis_center": ([1452, 648], "inferred"),
        "scapula_L": ([1374, 470], "inferred"),
        "shoulder_L": ([1362, 496], "occluded"),
        "elbow_L": ([1345, 588], "occluded"),
        "wrist_L": ([1354, 681], "occluded"),
        "forepaw_L": ([1362, 730], "occluded"),
        "scapula_R": ([1530, 470], "inferred"),
        "shoulder_R": ([1542, 496], "occluded"),
        "elbow_R": ([1559, 588], "occluded"),
        "wrist_R": ([1550, 681], "occluded"),
        "forepaw_R": ([1542, 730], "occluded"),
        "hip_L": ([1340, 586], "inferred"),
        "knee_L": ([1318, 650], "inferred"),
        "hock_L": ([1328, 704], "inferred"),
        "hindpaw_L": ([1340, 730], "visible"),
        "hip_R": ([1564, 586], "inferred"),
        "knee_R": ([1586, 650], "inferred"),
        "hock_R": ([1576, 704], "inferred"),
        "hindpaw_R": ([1564, 730], "visible"),
        "tail_root": ([1452, 640], "inferred"),
        "tail_mid_1": ([1410, 676], "visible"),
        "tail_mid_2": ([1355, 708], "visible"),
        "tail_tip": ([1304, 710], "visible"),
    },
}


CANONICAL_JOINTS = {
    "skull_center": [0.00, 0.74, 0.10],
    "jaw_center": [0.00, 0.63, 0.19],
    "neck_base": [0.00, 0.50, 0.03],
    "ribcage_center": [0.00, 0.37, 0.00],
    "abdomen_center": [0.00, 0.21, -0.01],
    "pelvis_center": [0.00, 0.16, -0.08],
    "scapula_L": [0.12, 0.45, -0.02],
    "shoulder_L": [0.18, 0.41, 0.04],
    "elbow_L": [0.18, 0.26, -0.04],
    "wrist_L": [0.16, 0.11, 0.10],
    "forepaw_L": [0.16, 0.03, 0.18],
    "scapula_R": [-0.12, 0.45, -0.02],
    "shoulder_R": [-0.18, 0.41, 0.04],
    "elbow_R": [-0.18, 0.26, -0.04],
    "wrist_R": [-0.16, 0.11, 0.10],
    "forepaw_R": [-0.16, 0.03, 0.18],
    "hip_L": [0.18, 0.25, -0.05],
    "knee_L": [0.23, 0.13, 0.03],
    "hock_L": [0.21, 0.06, -0.02],
    "hindpaw_L": [0.22, 0.03, 0.09],
    "hip_R": [-0.18, 0.25, -0.05],
    "knee_R": [-0.23, 0.13, 0.03],
    "hock_R": [-0.21, 0.06, -0.02],
    "hindpaw_R": [-0.22, 0.03, 0.09],
    "tail_root": [0.00, 0.18, -0.21],
    "tail_mid_1": [0.18, 0.13, -0.27],
    "tail_mid_2": [0.31, 0.06, -0.18],
    "tail_tip": [0.25, 0.03, 0.03],
}


SEGMENTS = [
    ("skull_center", "jaw_center", "head"),
    ("skull_center", "neck_base", "neck"),
    ("neck_base", "ribcage_center", "spine"),
    ("ribcage_center", "abdomen_center", "spine"),
    ("abdomen_center", "pelvis_center", "spine"),
    ("ribcage_center", "scapula_L", "left"),
    ("scapula_L", "shoulder_L", "left"),
    ("shoulder_L", "elbow_L", "left"),
    ("elbow_L", "wrist_L", "left"),
    ("wrist_L", "forepaw_L", "left"),
    ("ribcage_center", "scapula_R", "right"),
    ("scapula_R", "shoulder_R", "right"),
    ("shoulder_R", "elbow_R", "right"),
    ("elbow_R", "wrist_R", "right"),
    ("wrist_R", "forepaw_R", "right"),
    ("pelvis_center", "hip_L", "left"),
    ("hip_L", "knee_L", "left"),
    ("knee_L", "hock_L", "left"),
    ("hock_L", "hindpaw_L", "left"),
    ("pelvis_center", "hip_R", "right"),
    ("hip_R", "knee_R", "right"),
    ("knee_R", "hock_R", "right"),
    ("hock_R", "hindpaw_R", "right"),
    ("pelvis_center", "tail_root", "tail"),
    ("tail_root", "tail_mid_1", "tail"),
    ("tail_mid_1", "tail_mid_2", "tail"),
    ("tail_mid_2", "tail_tip", "tail"),
]


MASS_BLOCKS = {
    "skull": {
        "center": [0.00, 0.72, 0.10],
        "radii": [0.20, 0.16, 0.17],
        "mass_fraction": 0.18,
        "volume_drift_limit": 0.03,
    },
    "ribcage": {
        "center": [0.00, 0.38, 0.00],
        "radii": [0.23, 0.20, 0.20],
        "mass_fraction": 0.36,
        "volume_drift_limit": 0.03,
    },
    "abdomen": {
        "center": [0.00, 0.23, -0.01],
        "radii": [0.21, 0.14, 0.18],
        "mass_fraction": 0.21,
        "volume_drift_limit": 0.05,
    },
    "pelvis": {
        "center": [0.00, 0.16, -0.08],
        "radii": [0.22, 0.13, 0.16],
        "mass_fraction": 0.25,
        "volume_drift_limit": 0.03,
    },
}


MASS_ELLIPSES_2D = {
    "front": {
        "skull": [292, 290, 170, 160],
        "ribcage": [292, 505, 205, 190],
        "abdomen": [292, 620, 190, 135],
        "pelvis": [292, 650, 240, 120],
    },
    "side": {
        "skull": [780, 290, 170, 160],
        "ribcage": [865, 510, 220, 190],
        "abdomen": [905, 618, 230, 135],
        "pelvis": [958, 650, 230, 120],
    },
    "back": {
        "skull": [1452, 290, 170, 160],
        "ribcage": [1452, 508, 210, 190],
        "abdomen": [1452, 620, 200, 135],
        "pelvis": [1452, 650, 250, 120],
    },
}

HEAD_ANCHORS_2D = {
    "front": {
        "eye_socket_L": {"xy": [352, 315], "visibility": "visible"},
        "eye_center_L": {"xy": [352, 318], "visibility": "visible"},
        "eye_safe_ellipse_L": {"center": [352, 318], "radii": [34, 44], "visibility": "visible"},
        "eye_cover_zone_L": {"center": [352, 321], "radii": [43, 52], "visibility": "visible"},
        "eye_socket_R": {"xy": [232, 315], "visibility": "visible"},
        "eye_center_R": {"xy": [232, 318], "visibility": "visible"},
        "eye_safe_ellipse_R": {"center": [232, 318], "radii": [34, 44], "visibility": "visible"},
        "eye_cover_zone_R": {"center": [232, 321], "radii": [43, 52], "visibility": "visible"},
        "ear_base_L": {"xy": [405, 205], "visibility": "visible"},
        "ear_tip_L": {"xy": [460, 125], "visibility": "visible"},
        "ear_inner_L": {"xy": [406, 183], "visibility": "visible"},
        "ear_base_R": {"xy": [179, 205], "visibility": "visible"},
        "ear_tip_R": {"xy": [124, 125], "visibility": "visible"},
        "ear_inner_R": {"xy": [178, 183], "visibility": "visible"},
    },
    "side": {
        "eye_socket_L": {"xy": [690, 324], "visibility": "visible"},
        "eye_center_L": {"xy": [690, 326], "visibility": "visible"},
        "eye_safe_ellipse_L": {"center": [690, 326], "radii": [20, 34], "visibility": "visible"},
        "eye_cover_zone_L": {"center": [690, 328], "radii": [27, 42], "visibility": "visible"},
        "eye_socket_R": {"xy": [704, 326], "visibility": "occluded"},
        "eye_center_R": {"xy": [704, 328], "visibility": "occluded"},
        "eye_safe_ellipse_R": {"center": [704, 328], "radii": [18, 32], "visibility": "occluded"},
        "eye_cover_zone_R": {"center": [704, 330], "radii": [25, 40], "visibility": "occluded"},
        "ear_base_L": {"xy": [740, 210], "visibility": "visible"},
        "ear_tip_L": {"xy": [720, 122], "visibility": "visible"},
        "ear_inner_L": {"xy": [738, 183], "visibility": "visible"},
        "ear_base_R": {"xy": [760, 214], "visibility": "occluded"},
        "ear_tip_R": {"xy": [730, 128], "visibility": "occluded"},
        "ear_inner_R": {"xy": [756, 188], "visibility": "occluded"},
    },
    "back": {
        "eye_socket_L": {"xy": [1392, 318], "visibility": "occluded"},
        "eye_center_L": {"xy": [1392, 320], "visibility": "occluded"},
        "eye_safe_ellipse_L": {"center": [1392, 320], "radii": [31, 40], "visibility": "occluded"},
        "eye_cover_zone_L": {"center": [1392, 322], "radii": [40, 49], "visibility": "occluded"},
        "eye_socket_R": {"xy": [1512, 318], "visibility": "occluded"},
        "eye_center_R": {"xy": [1512, 320], "visibility": "occluded"},
        "eye_safe_ellipse_R": {"center": [1512, 320], "radii": [31, 40], "visibility": "occluded"},
        "eye_cover_zone_R": {"center": [1512, 322], "radii": [40, 49], "visibility": "occluded"},
        "ear_base_L": {"xy": [1348, 210], "visibility": "visible"},
        "ear_tip_L": {"xy": [1288, 126], "visibility": "visible"},
        "ear_inner_L": {"xy": [1350, 184], "visibility": "occluded"},
        "ear_base_R": {"xy": [1556, 210], "visibility": "visible"},
        "ear_tip_R": {"xy": [1616, 126], "visibility": "visible"},
        "ear_inner_R": {"xy": [1554, 184], "visibility": "occluded"},
    },
}

HEAD_REFERENCE_POINTS_3D = {
    "eye_socket_L": [0.105, 0.705, 0.215],
    "eye_center_L": [0.105, 0.700, 0.235],
    "eye_socket_R": [-0.105, 0.705, 0.215],
    "eye_center_R": [-0.105, 0.700, 0.235],
    "ear_base_L": [0.135, 0.825, 0.060],
    "ear_tip_L": [0.210, 0.965, 0.020],
    "ear_inner_L": [0.140, 0.870, 0.085],
    "ear_base_R": [-0.135, 0.825, 0.060],
    "ear_tip_R": [-0.210, 0.965, 0.020],
    "ear_inner_R": [-0.140, 0.870, 0.085],
}

HEAD_REFERENCE_SEGMENTS = [
    {
        "from": "skull_center",
        "to": "ear_base_L",
        "group": "ear",
        "use": "head-to-left-ear-root transform reference; not a solved ear deformer",
    },
    {
        "from": "ear_base_L",
        "to": "ear_tip_L",
        "group": "ear",
        "use": "left ear root-to-tip attention and secondary-motion reference",
    },
    {
        "from": "ear_base_L",
        "to": "ear_inner_L",
        "group": "ear",
        "use": "left inner-ear surface orientation reference",
    },
    {
        "from": "skull_center",
        "to": "ear_base_R",
        "group": "ear",
        "use": "head-to-right-ear-root transform reference; not a solved ear deformer",
    },
    {
        "from": "ear_base_R",
        "to": "ear_tip_R",
        "group": "ear",
        "use": "right ear root-to-tip attention and secondary-motion reference",
    },
    {
        "from": "ear_base_R",
        "to": "ear_inner_R",
        "group": "ear",
        "use": "right inner-ear surface orientation reference",
    },
]

HEAD_REFERENCE_VOLUMES = {
    "eye_safe_ellipse_L": {
        "center": [0.105, 0.700, 0.238],
        "radii": [0.040, 0.052, 0.018],
        "use": "future X6 gaze and clipping range reference; not a solved eye rig",
    },
    "eye_safe_ellipse_R": {
        "center": [-0.105, 0.700, 0.238],
        "radii": [0.040, 0.052, 0.018],
        "use": "future X6 gaze and clipping range reference; not a solved eye rig",
    },
    "eye_cover_zone_L": {
        "center": [0.105, 0.698, 0.252],
        "radii": [0.052, 0.064, 0.028],
        "use": "future X2 forepaw cover target reference; not a contact solve",
    },
    "eye_cover_zone_R": {
        "center": [-0.105, 0.698, 0.252],
        "radii": [0.052, 0.064, 0.028],
        "use": "future X2 forepaw cover target reference; not a contact solve",
    },
}

MOMENT_PREFLIGHT = {
    "status": "reference-only-not-solved-in-X1",
    "gateBoundary": "X1 may list future moment arms and pivots, but X2/X5/X6 must solve numeric ranges, contacts, support, and deformer pivots after user approval.",
    "futureMomentChains": [
        {
            "name": "password-cover-forelimb",
            "deferredTo": "X2",
            "chain": ["scapula", "shoulder", "elbow", "wrist", "forepaw", "eye_cover_zone"],
            "requiredChecksLater": [
                "forepaw contact timing",
                "lever-arm direction",
                "shoulder/elbow/wrist torque sign",
                "ribcage and pelvis volume preservation",
                "body support reaction while paw is released",
            ],
        },
        {
            "name": "gaze-and-eyelid",
            "deferredTo": "X5-X6",
            "chain": ["skull_center", "eye_socket", "eye_center", "upper_lid", "lower_lid"],
            "requiredChecksLater": [
                "eye rotation center",
                "eyelid hinge/deformer pivot",
                "safe ellipse clipping",
                "blink and gaze parameter coupling",
            ],
        },
    ],
    "forbiddenInX1": [
        "numeric torque values",
        "contact reaction forces",
        "center-of-mass support solve",
        "eye deformer pivots",
        "new spread-pose or master image generation",
    ],
}

SOFT_TISSUE_CONTROL_ZONES = {
    "status": "x1-review-reference-not-deformer-contract",
    "gateBoundary": "These zones name future skin/fur/muscle envelopes for X4/X5. X1 does not define ArtMesh topology, Rotation Deformers, Physics, or deformation weights.",
    "zones": [
        {
            "id": "neck-cheek-chest-fur",
            "displayName": "颈部/脸颊/胸毛软层",
            "drivenBy": ["skull_center", "jaw_center", "neck_base", "ribcage_center"],
            "purpose": "bridge head-to-chest motion and hide normal fur overlap without covering anatomical errors",
            "futureGate": "X4-X5",
        },
        {
            "id": "scapula-chest-sling-L",
            "displayName": "左肩胛-胸侧软组织",
            "drivenBy": ["ribcage_center", "scapula_L", "shoulder_L"],
            "purpose": "preserve armpit and shoulder-side volume when the left forelimb lifts",
            "futureGate": "X4-X5",
        },
        {
            "id": "scapula-chest-sling-R",
            "displayName": "右肩胛-胸侧软组织",
            "drivenBy": ["ribcage_center", "scapula_R", "shoulder_R"],
            "purpose": "preserve armpit and shoulder-side volume when the right forelimb lifts",
            "futureGate": "X4-X5",
        },
        {
            "id": "forelimb-envelope-L",
            "displayName": "左上臂/前臂包络",
            "drivenBy": ["shoulder_L", "elbow_L", "wrist_L", "forepaw_L"],
            "purpose": "keep limb thickness and fur sleeve continuity across shoulder, elbow, and wrist",
            "futureGate": "X4-X5",
        },
        {
            "id": "forelimb-envelope-R",
            "displayName": "右上臂/前臂包络",
            "drivenBy": ["shoulder_R", "elbow_R", "wrist_R", "forepaw_R"],
            "purpose": "keep limb thickness and fur sleeve continuity across shoulder, elbow, and wrist",
            "futureGate": "X4-X5",
        },
        {
            "id": "ribcage-abdomen-skin",
            "displayName": "胸腹表皮包络",
            "drivenBy": ["ribcage_center", "abdomen_center", "pelvis_center"],
            "purpose": "allow local breathing and paw-pull response without whole-body scaling or ribcage collapse",
            "futureGate": "X4-X7",
        },
        {
            "id": "hip-thigh-envelope-L",
            "displayName": "左髋/大腿/后腿包络",
            "drivenBy": ["pelvis_center", "hip_L", "knee_L", "hock_L", "hindpaw_L"],
            "purpose": "preserve kitten round thigh volume from sitting pose to later hidden-anatomy references",
            "futureGate": "X4-X5",
        },
        {
            "id": "hip-thigh-envelope-R",
            "displayName": "右髋/大腿/后腿包络",
            "drivenBy": ["pelvis_center", "hip_R", "knee_R", "hock_R", "hindpaw_R"],
            "purpose": "preserve kitten round thigh volume from sitting pose to later hidden-anatomy references",
            "futureGate": "X4-X5",
        },
        {
            "id": "tail-root-fur-socket",
            "displayName": "尾根毛发/皮肤插口",
            "drivenBy": ["pelvis_center", "tail_root", "tail_mid_1"],
            "purpose": "keep tail-root attachment continuous when the tail moves",
            "futureGate": "X4-X7",
        },
        {
            "id": "ear-soft-envelope-L",
            "displayName": "左耳根/耳面软组织",
            "drivenBy": ["skull_center", "ear_base_L", "ear_tip_L", "ear_inner_L"],
            "purpose": "preserve ear-root attachment, inner-ear surface, and ear-tip secondary motion reference",
            "futureGate": "X4-X7",
        },
        {
            "id": "ear-soft-envelope-R",
            "displayName": "右耳根/耳面软组织",
            "drivenBy": ["skull_center", "ear_base_R", "ear_tip_R", "ear_inner_R"],
            "purpose": "preserve ear-root attachment, inner-ear surface, and ear-tip secondary motion reference",
            "futureGate": "X4-X7",
        },
    ],
}

SOFT_TISSUE_ELLIPSES_2D = {
    "front": [
        ("neck-cheek-chest-fur", [292, 430, 180, 160]),
        ("scapula-chest-sling-L", [375, 520, 105, 155]),
        ("scapula-chest-sling-R", [209, 520, 105, 155]),
        ("forelimb-envelope-L", [388, 610, 70, 250]),
        ("forelimb-envelope-R", [196, 610, 70, 250]),
        ("ribcage-abdomen-skin", [292, 575, 260, 235]),
        ("hip-thigh-envelope-L", [402, 650, 120, 180]),
        ("hip-thigh-envelope-R", [182, 650, 120, 180]),
        ("tail-root-fur-socket", [420, 633, 120, 95]),
    ],
    "side": [
        ("neck-cheek-chest-fur", [780, 432, 170, 150]),
        ("scapula-chest-sling-L", [808, 526, 115, 160]),
        ("forelimb-envelope-L", [782, 615, 78, 245]),
        ("ribcage-abdomen-skin", [890, 575, 285, 235]),
        ("hip-thigh-envelope-L", [930, 648, 165, 190]),
        ("tail-root-fur-socket", [1035, 655, 160, 95]),
    ],
    "back": [
        ("neck-cheek-chest-fur", [1452, 430, 180, 150]),
        ("scapula-chest-sling-L", [1368, 525, 110, 160]),
        ("scapula-chest-sling-R", [1536, 525, 110, 160]),
        ("forelimb-envelope-L", [1352, 615, 72, 245]),
        ("forelimb-envelope-R", [1552, 615, 72, 245]),
        ("ribcage-abdomen-skin", [1452, 575, 260, 235]),
        ("hip-thigh-envelope-L", [1340, 650, 130, 180]),
        ("hip-thigh-envelope-R", [1564, 650, 130, 180]),
        ("tail-root-fur-socket", [1410, 655, 160, 95]),
    ],
}

SOFT_TISSUE_SPREAD_ELLIPSES = [
    ("neck-cheek-chest-fur", [0.00, 0.55, 0.22, 0.17]),
    ("scapula-chest-sling-L", [0.30, 0.34, 0.20, 0.11]),
    ("scapula-chest-sling-R", [-0.30, 0.34, 0.20, 0.11]),
    ("forelimb-envelope-L", [0.58, 0.18, 0.36, 0.08]),
    ("forelimb-envelope-R", [-0.58, 0.18, 0.36, 0.08]),
    ("ribcage-abdomen-skin", [0.00, 0.25, 0.30, 0.22]),
    ("hip-thigh-envelope-L", [0.44, -0.09, 0.34, 0.10]),
    ("hip-thigh-envelope-R", [-0.44, -0.09, 0.34, 0.10]),
    ("tail-root-fur-socket", [0.22, -0.16, 0.28, 0.08]),
]

SOFT_TISSUE_MOMENT_ANCHORS = {
    "status": "reference-only-not-solved-in-X1",
    "gateBoundary": "These anchors mark future soft-tissue pivot/pull directions. X1 does not solve torque magnitudes, deformation weights, ArtMesh topology, Physics, or contact reactions.",
    "anchors": [
        {
            "id": "neck-fur-pull",
            "zone": "neck-cheek-chest-fur",
            "pivot": "neck_base",
            "pullToward": "ribcage_center",
            "futureUse": "neck/chest fur compression and stretch around head follow",
        },
        {
            "id": "left-scapula-sling-pivot",
            "zone": "scapula-chest-sling-L",
            "pivot": "scapula_L",
            "pullToward": "shoulder_L",
            "futureUse": "left armpit and shoulder fur shear during forelimb lift",
        },
        {
            "id": "right-scapula-sling-pivot",
            "zone": "scapula-chest-sling-R",
            "pivot": "scapula_R",
            "pullToward": "shoulder_R",
            "futureUse": "right armpit and shoulder fur shear during forelimb lift",
        },
        {
            "id": "left-forelimb-elbow-sleeve",
            "zone": "forelimb-envelope-L",
            "pivot": "elbow_L",
            "pullToward": "wrist_L",
            "futureUse": "left forearm sleeve bend and volume preservation",
        },
        {
            "id": "right-forelimb-elbow-sleeve",
            "zone": "forelimb-envelope-R",
            "pivot": "elbow_R",
            "pullToward": "wrist_R",
            "futureUse": "right forearm sleeve bend and volume preservation",
        },
        {
            "id": "belly-skin-hinge",
            "zone": "ribcage-abdomen-skin",
            "pivot": "abdomen_center",
            "pullToward": "pelvis_center",
            "futureUse": "belly skin lag, breathing offset, and low-amplitude body compensation",
        },
        {
            "id": "left-thigh-soft-hinge",
            "zone": "hip-thigh-envelope-L",
            "pivot": "hip_L",
            "pullToward": "knee_L",
            "futureUse": "left thigh mass preservation and sitting-to-reference continuity",
        },
        {
            "id": "right-thigh-soft-hinge",
            "zone": "hip-thigh-envelope-R",
            "pivot": "hip_R",
            "pullToward": "knee_R",
            "futureUse": "right thigh mass preservation and sitting-to-reference continuity",
        },
        {
            "id": "tail-root-socket-pull",
            "zone": "tail-root-fur-socket",
            "pivot": "tail_root",
            "pullToward": "tail_mid_1",
            "futureUse": "tail root socket continuity under tail motion",
        },
        {
            "id": "left-ear-root-pivot",
            "zone": "ear-soft-envelope-L",
            "pivot": "ear_base_L",
            "pullToward": "ear_tip_L",
            "futureUse": "left ear attention tilt, root compression, and ear-tip secondary motion",
        },
        {
            "id": "right-ear-root-pivot",
            "zone": "ear-soft-envelope-R",
            "pivot": "ear_base_R",
            "pullToward": "ear_tip_R",
            "futureUse": "right ear attention tilt, root compression, and ear-tip secondary motion",
        },
    ],
}

SOFT_TISSUE_MOMENT_ANCHORS_2D = {
    "front": [
        ("neck-fur-pull", [292, 443], [292, 516]),
        ("left-scapula-sling-pivot", [370, 472], [382, 492]),
        ("right-scapula-sling-pivot", [214, 472], [202, 492]),
        ("left-forelimb-elbow-sleeve", [399, 586], [389, 682]),
        ("right-forelimb-elbow-sleeve", [185, 586], [195, 682]),
        ("belly-skin-hinge", [292, 626], [292, 655]),
        ("left-thigh-soft-hinge", [412, 586], [432, 652]),
        ("right-thigh-soft-hinge", [172, 586], [152, 652]),
        ("tail-root-socket-pull", [292, 642], [440, 650]),
        ("left-ear-root-pivot", [405, 205], [460, 125]),
        ("right-ear-root-pivot", [179, 205], [124, 125]),
    ],
    "side": [
        ("neck-fur-pull", [790, 444], [864, 516]),
        ("left-scapula-sling-pivot", [818, 470], [797, 496]),
        ("left-forelimb-elbow-sleeve", [835, 588], [758, 681]),
        ("belly-skin-hinge", [906, 619], [958, 648]),
        ("left-thigh-soft-hinge", [963, 586], [928, 650]),
        ("tail-root-socket-pull", [1000, 640], [1060, 670]),
        ("left-ear-root-pivot", [740, 210], [720, 122]),
        ("right-ear-root-pivot", [760, 214], [730, 128]),
    ],
    "back": [
        ("neck-fur-pull", [1452, 440], [1452, 518]),
        ("left-scapula-sling-pivot", [1374, 470], [1362, 496]),
        ("right-scapula-sling-pivot", [1530, 470], [1542, 496]),
        ("left-forelimb-elbow-sleeve", [1345, 588], [1354, 681]),
        ("right-forelimb-elbow-sleeve", [1559, 588], [1550, 681]),
        ("belly-skin-hinge", [1452, 620], [1452, 648]),
        ("left-thigh-soft-hinge", [1340, 586], [1318, 650]),
        ("right-thigh-soft-hinge", [1564, 586], [1586, 650]),
        ("tail-root-socket-pull", [1452, 640], [1410, 676]),
        ("left-ear-root-pivot", [1348, 210], [1288, 126]),
        ("right-ear-root-pivot", [1556, 210], [1616, 126]),
    ],
}

AUXILIARY_REFERENCE_JOINTS = {
    "status": "reference-only-not-solved-in-X1",
    "gateBoundary": "Auxiliary joints are future layer, node, and triangulation seed references only. X1 does not define ArtMesh topology, deformers, weights, or numerical motion ranges.",
    "triangulationReference": {
        "source": "user supplied Zhihu article p/383268858; direct page access returned 403 during implementation, so only the general triangle-mesh principle is adopted",
        "adoptedPrinciple": "future mesh control should keep semantic boundary points and interior hinge points explicit so that later ArtMesh triangles can preserve anatomy and soft-tissue envelopes",
        "forbiddenInX1": [
            "actual ArtMesh vertex list",
            "Delaunay or Cubism triangulation output",
            "deformation weights",
            "Rotation Deformer pivots",
            "Physics groups",
        ],
    },
    "joints": [
        {
            "id": "cheek_fur_L",
            "kind": "soft-boundary",
            "attachedTo": ["skull_center", "jaw_center", "neck_base"],
            "futureUse": "left cheek fur layer boundary and head-to-neck overlap control",
            "futureGate": "X4-X5",
        },
        {
            "id": "cheek_fur_R",
            "kind": "soft-boundary",
            "attachedTo": ["skull_center", "jaw_center", "neck_base"],
            "futureUse": "right cheek fur layer boundary and head-to-neck overlap control",
            "futureGate": "X4-X5",
        },
        {
            "id": "whisker_root_L",
            "kind": "appendage-root",
            "attachedTo": ["jaw_center", "cheek_fur_L"],
            "futureUse": "left whisker bundle root and cheek-follow reference",
            "futureGate": "X4-X7",
        },
        {
            "id": "whisker_root_R",
            "kind": "appendage-root",
            "attachedTo": ["jaw_center", "cheek_fur_R"],
            "futureUse": "right whisker bundle root and cheek-follow reference",
            "futureGate": "X4-X7",
        },
        {
            "id": "ear_mid_L",
            "kind": "secondary-hinge",
            "attachedTo": ["ear_base_L", "ear_tip_L", "ear_inner_L"],
            "futureUse": "left ear surface bend and tip-lag reference",
            "futureGate": "X5-X7",
        },
        {
            "id": "ear_mid_R",
            "kind": "secondary-hinge",
            "attachedTo": ["ear_base_R", "ear_tip_R", "ear_inner_R"],
            "futureUse": "right ear surface bend and tip-lag reference",
            "futureGate": "X5-X7",
        },
        {
            "id": "chest_fur_tip",
            "kind": "soft-boundary",
            "attachedTo": ["neck_base", "ribcage_center", "abdomen_center"],
            "futureUse": "front chest-fur hanging point and breathing overlap reference",
            "futureGate": "X4-X7",
        },
        {
            "id": "armpit_L",
            "kind": "fold-boundary",
            "attachedTo": ["ribcage_center", "scapula_L", "shoulder_L"],
            "futureUse": "left shoulder/chest hidden overlap and sleeve fold reference",
            "futureGate": "X4-X5",
        },
        {
            "id": "armpit_R",
            "kind": "fold-boundary",
            "attachedTo": ["ribcage_center", "scapula_R", "shoulder_R"],
            "futureUse": "right shoulder/chest hidden overlap and sleeve fold reference",
            "futureGate": "X4-X5",
        },
        {
            "id": "foretoe_L",
            "kind": "distal-boundary",
            "attachedTo": ["wrist_L", "forepaw_L"],
            "futureUse": "left forepaw toe/edge mesh seed for contact silhouettes",
            "futureGate": "X4-X5",
        },
        {
            "id": "foretoe_R",
            "kind": "distal-boundary",
            "attachedTo": ["wrist_R", "forepaw_R"],
            "futureUse": "right forepaw toe/edge mesh seed for contact silhouettes",
            "futureGate": "X4-X5",
        },
        {
            "id": "hindtoe_L",
            "kind": "distal-boundary",
            "attachedTo": ["hock_L", "hindpaw_L"],
            "futureUse": "left hindpaw toe/edge mesh seed for sitting silhouette",
            "futureGate": "X4-X5",
        },
        {
            "id": "hindtoe_R",
            "kind": "distal-boundary",
            "attachedTo": ["hock_R", "hindpaw_R"],
            "futureUse": "right hindpaw toe/edge mesh seed for sitting silhouette",
            "futureGate": "X4-X5",
        },
        {
            "id": "tail_base_socket_L",
            "kind": "socket-boundary",
            "attachedTo": ["pelvis_center", "tail_root"],
            "futureUse": "left tail-root fur socket boundary and hidden overlap seed",
            "futureGate": "X4-X7",
        },
        {
            "id": "tail_base_socket_R",
            "kind": "socket-boundary",
            "attachedTo": ["pelvis_center", "tail_root"],
            "futureUse": "right tail-root fur socket boundary and hidden overlap seed",
            "futureGate": "X4-X7",
        },
    ],
}

AUXILIARY_JOINTS_3D = {
    "cheek_fur_L": [0.145, 0.635, 0.185],
    "cheek_fur_R": [-0.145, 0.635, 0.185],
    "whisker_root_L": [0.125, 0.615, 0.235],
    "whisker_root_R": [-0.125, 0.615, 0.235],
    "ear_mid_L": [0.175, 0.895, 0.040],
    "ear_mid_R": [-0.175, 0.895, 0.040],
    "chest_fur_tip": [0.000, 0.335, 0.155],
    "armpit_L": [0.145, 0.365, 0.065],
    "armpit_R": [-0.145, 0.365, 0.065],
    "foretoe_L": [0.160, 0.010, 0.225],
    "foretoe_R": [-0.160, 0.010, 0.225],
    "hindtoe_L": [0.245, 0.010, 0.130],
    "hindtoe_R": [-0.245, 0.010, 0.130],
    "tail_base_socket_L": [0.080, 0.165, -0.185],
    "tail_base_socket_R": [-0.080, 0.165, -0.185],
}

AUXILIARY_JOINTS_2D = {
    "front": {
        "cheek_fur_L": {"xy": [390, 380], "visibility": "visible"},
        "cheek_fur_R": {"xy": [194, 380], "visibility": "visible"},
        "whisker_root_L": {"xy": [366, 398], "visibility": "visible"},
        "whisker_root_R": {"xy": [218, 398], "visibility": "visible"},
        "ear_mid_L": {"xy": [432, 164], "visibility": "visible"},
        "ear_mid_R": {"xy": [152, 164], "visibility": "visible"},
        "chest_fur_tip": {"xy": [292, 542], "visibility": "visible"},
        "armpit_L": {"xy": [350, 555], "visibility": "inferred"},
        "armpit_R": {"xy": [234, 555], "visibility": "inferred"},
        "foretoe_L": {"xy": [382, 744], "visibility": "visible"},
        "foretoe_R": {"xy": [202, 744], "visibility": "visible"},
        "hindtoe_L": {"xy": [430, 744], "visibility": "visible"},
        "hindtoe_R": {"xy": [154, 744], "visibility": "visible"},
        "tail_base_socket_L": {"xy": [330, 646], "visibility": "occluded"},
        "tail_base_socket_R": {"xy": [254, 646], "visibility": "occluded"},
    },
    "side": {
        "cheek_fur_L": {"xy": [704, 390], "visibility": "visible"},
        "cheek_fur_R": {"xy": [720, 394], "visibility": "occluded"},
        "whisker_root_L": {"xy": [675, 408], "visibility": "visible"},
        "whisker_root_R": {"xy": [690, 410], "visibility": "occluded"},
        "ear_mid_L": {"xy": [730, 165], "visibility": "visible"},
        "ear_mid_R": {"xy": [745, 170], "visibility": "occluded"},
        "chest_fur_tip": {"xy": [812, 542], "visibility": "visible"},
        "armpit_L": {"xy": [790, 552], "visibility": "inferred"},
        "armpit_R": {"xy": [798, 558], "visibility": "occluded"},
        "foretoe_L": {"xy": [714, 744], "visibility": "visible"},
        "foretoe_R": {"xy": [722, 746], "visibility": "partly-visible"},
        "hindtoe_L": {"xy": [852, 744], "visibility": "visible"},
        "hindtoe_R": {"xy": [861, 746], "visibility": "partly-visible"},
        "tail_base_socket_L": {"xy": [990, 652], "visibility": "inferred"},
        "tail_base_socket_R": {"xy": [1008, 654], "visibility": "occluded"},
    },
    "back": {
        "cheek_fur_L": {"xy": [1374, 382], "visibility": "visible"},
        "cheek_fur_R": {"xy": [1530, 382], "visibility": "visible"},
        "whisker_root_L": {"xy": [1390, 402], "visibility": "occluded"},
        "whisker_root_R": {"xy": [1514, 402], "visibility": "occluded"},
        "ear_mid_L": {"xy": [1318, 166], "visibility": "visible"},
        "ear_mid_R": {"xy": [1586, 166], "visibility": "visible"},
        "chest_fur_tip": {"xy": [1452, 540], "visibility": "occluded"},
        "armpit_L": {"xy": [1385, 555], "visibility": "occluded"},
        "armpit_R": {"xy": [1519, 555], "visibility": "occluded"},
        "foretoe_L": {"xy": [1360, 744], "visibility": "occluded"},
        "foretoe_R": {"xy": [1544, 744], "visibility": "occluded"},
        "hindtoe_L": {"xy": [1334, 744], "visibility": "visible"},
        "hindtoe_R": {"xy": [1570, 744], "visibility": "visible"},
        "tail_base_socket_L": {"xy": [1430, 650], "visibility": "inferred"},
        "tail_base_socket_R": {"xy": [1474, 650], "visibility": "inferred"},
    },
}

AUXILIARY_REFERENCE_SEGMENTS = [
    ("jaw_center", "cheek_fur_L", "auxiliary"),
    ("jaw_center", "cheek_fur_R", "auxiliary"),
    ("cheek_fur_L", "whisker_root_L", "auxiliary"),
    ("cheek_fur_R", "whisker_root_R", "auxiliary"),
    ("ear_base_L", "ear_mid_L", "auxiliary"),
    ("ear_mid_L", "ear_tip_L", "auxiliary"),
    ("ear_base_R", "ear_mid_R", "auxiliary"),
    ("ear_mid_R", "ear_tip_R", "auxiliary"),
    ("neck_base", "chest_fur_tip", "auxiliary"),
    ("chest_fur_tip", "ribcage_center", "auxiliary"),
    ("shoulder_L", "armpit_L", "auxiliary"),
    ("armpit_L", "ribcage_center", "auxiliary"),
    ("shoulder_R", "armpit_R", "auxiliary"),
    ("armpit_R", "ribcage_center", "auxiliary"),
    ("forepaw_L", "foretoe_L", "auxiliary"),
    ("forepaw_R", "foretoe_R", "auxiliary"),
    ("hindpaw_L", "hindtoe_L", "auxiliary"),
    ("hindpaw_R", "hindtoe_R", "auxiliary"),
    ("tail_root", "tail_base_socket_L", "auxiliary"),
    ("tail_root", "tail_base_socket_R", "auxiliary"),
]

FUTURE_ARTIFACT_REQUESTS = {
    "spreadPoseXiaojuPlate": {
        "requestedByUser": True,
        "reason": "A spread-pose / 大字型 anatomical plate would make hidden limb, torso, and eye-area drawing easier for later separation.",
        "gateDisposition": "realistic-master-deferred-until-after-X1-approval-and-X2-pose/support-solve",
        "x1ReviewAid": "live2d/x1/qa/x1-spread-pose-review-aid.png",
        "notGeneratedInX1": True,
        "constraintsWhenAuthorized": [
            "derive from approved X1 body and X2 support/action constraints",
            "must preserve Xiaoju identity, proportions, segment lengths, and mass volumes",
            "must not replace the authoritative three-view body or bypass hidden-anatomy validation",
        ],
    }
}


COLORS = {
    "head": (80, 230, 255, 230),
    "neck": (80, 230, 255, 230),
    "spine": (80, 230, 255, 230),
    "left": (255, 70, 210, 230),
    "right": (255, 210, 50, 230),
    "tail": (60, 235, 110, 230),
    "visible": (255, 255, 255, 245),
    "partly-visible": (210, 255, 255, 245),
    "inferred": (255, 145, 40, 245),
    "occluded": (255, 70, 70, 245),
    "eye": (50, 120, 255, 235),
    "eye-safe": (60, 170, 255, 120),
    "cover-zone": (255, 110, 40, 105),
    "soft-tissue": (120, 95, 255, 62),
    "soft-tissue-line": (95, 75, 220, 185),
    "muscle-anchor": (170, 45, 210, 230),
    "muscle-vector": (170, 45, 210, 165),
    "ear": (40, 190, 180, 235),
    "ear-vector": (40, 190, 180, 165),
    "ear-chain": (20, 160, 150, 210),
    "auxiliary": (20, 90, 220, 150),
    "auxiliary-joint": (20, 90, 220, 230),
}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    choices = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for path in choices:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def distance3(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def point3(name: str) -> list[float]:
    if name in CANONICAL_JOINTS:
        return CANONICAL_JOINTS[name]
    if name in HEAD_REFERENCE_POINTS_3D:
        return HEAD_REFERENCE_POINTS_3D[name]
    return AUXILIARY_JOINTS_3D[name]


def draw_anchor_vector(draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float], radius: int = 6) -> None:
    sx, sy = start
    ex, ey = end
    vx = ex - sx
    vy = ey - sy
    length = math.hypot(vx, vy)
    if length > 1e-6:
        ux = vx / length
        uy = vy / length
        line_end = (sx + ux * min(length, 34), sy + uy * min(length, 34))
        draw.line([start, line_end], fill=COLORS["muscle-vector"], width=3)
        ah = 7
        left = (line_end[0] - ux * ah - uy * ah * 0.55, line_end[1] - uy * ah + ux * ah * 0.55)
        right = (line_end[0] - ux * ah + uy * ah * 0.55, line_end[1] - uy * ah - ux * ah * 0.55)
        draw.polygon([line_end, left, right], fill=COLORS["muscle-vector"])
    draw.polygon([(sx, sy - radius), (sx + radius, sy), (sx, sy + radius), (sx - radius, sy)], fill=COLORS["muscle-anchor"], outline=(255, 255, 255, 230))


def build_contract() -> dict:
    segment_contract = []
    for a, b, group in SEGMENTS:
        segment_contract.append(
            {
                "from": a,
                "to": b,
                "group": group,
                "rest_length": round(distance3(CANONICAL_JOINTS[a], CANONICAL_JOINTS[b]), 5),
                "length_drift_limit": 0.02,
            }
        )

    auxiliary_segment_contract = []
    for a, b, group in AUXILIARY_REFERENCE_SEGMENTS:
        auxiliary_segment_contract.append(
            {
                "from": a,
                "to": b,
                "group": group,
                "rest_length": round(distance3(point3(a), point3(b)), 5),
                "use": "future layer boundary / triangulation seed reference only",
                "length_drift_limit": "deferred-to-X5",
            }
        )

    observations = {}
    for view_name, points in LANDMARKS_2D.items():
        observations[view_name] = {
            name: {"xy": xy, "visibility": visibility}
            for name, (xy, visibility) in points.items()
        }

    return {
        "schemaVersion": 1,
        "stage": "X1-canonical-body",
        "status": "candidate-for-user-review",
        "source": "three-view-preview.png",
        "sourceLimitations": [
            "single RGB composite rather than separate transparent orthographic plates",
            "views are visually aligned but not calibrated camera projections",
            "fur and seated pose occlude scapula, hip, and several limb joints",
            "tail curl differs in projected visibility and is provisional",
        ],
        "biomechanicsReferences": [
            {
                "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11737544/",
                "use": "forelimb topology: scapula, upper arm, forearm, carpals; shoulder, elbow, wrist",
            },
            {
                "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC2043500/",
                "use": "three-dimensional feline hindlimb topology and coupled hip, knee, ankle axes",
            },
            {
                "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3137431/",
                "use": "postural endpoint forces and small-angle balance behavior",
            },
        ],
        "coordinateSystem": {
            "units": "normalized kitten body height",
            "origin": "ground projection below pelvis center",
            "axes": {"x": "cat anatomical left", "y": "up", "z": "forward"},
            "anatomicalSideRule": "L/R always refers to the cat, never the viewer",
        },
        "views": VIEWS,
        "observedLandmarks2D": observations,
        "canonicalJoints3D": CANONICAL_JOINTS,
        "headReferenceAnchors2D": HEAD_ANCHORS_2D,
        "headReferencePoints3D": HEAD_REFERENCE_POINTS_3D,
        "headReferenceSegments": HEAD_REFERENCE_SEGMENTS,
        "headReferenceVolumes": HEAD_REFERENCE_VOLUMES,
        "auxiliaryReferenceJoints": AUXILIARY_REFERENCE_JOINTS,
        "auxiliaryJoints3D": AUXILIARY_JOINTS_3D,
        "auxiliaryJoints2D": AUXILIARY_JOINTS_2D,
        "auxiliaryReferenceSegments": auxiliary_segment_contract,
        "segments": segment_contract,
        "massBlocks": MASS_BLOCKS,
        "softTissueControlZones": SOFT_TISSUE_CONTROL_ZONES,
        "softTissueMomentAnchors": SOFT_TISSUE_MOMENT_ANCHORS,
        "momentPreflight": MOMENT_PREFLIGHT,
        "futureArtifactRequests": FUTURE_ARTIFACT_REQUESTS,
        "jointRangePolicy": {
            "status": "topology-only-in-X1",
            "note": "Numerical pose ranges are intentionally deferred to X2; X1 freezes joint identity, bend branch, and segment length only.",
            "preferredBendBranches": {
                "fore_elbow_L": "caudal-and-inward",
                "fore_elbow_R": "caudal-and-inward",
                "hind_knee_L": "cranial-with-folded-hock",
                "hind_knee_R": "cranial-with-folded-hock",
            },
        },
        "gatePolicy": {
            "x1MayPassOnlyWithUserApproval": True,
            "x2Authorized": False,
            "forbiddenBeforeX1Approval": [
                "support-pose-solve",
                "new-master-generation",
                "material-separation",
                "photoshop-import",
                "cubism-editing",
            ],
        },
    }


def vertical_consistency() -> dict:
    names = [
        "skull_center",
        "jaw_center",
        "neck_base",
        "ribcage_center",
        "abdomen_center",
        "pelvis_center",
        "shoulder_L",
        "elbow_L",
        "wrist_L",
        "forepaw_L",
        "hip_L",
        "knee_L",
        "hock_L",
        "hindpaw_L",
    ]
    rows = []
    for name in names:
        values = []
        for view_name, view in VIEWS.items():
            y = LANDMARKS_2D[view_name][name][0][1]
            height = view["ground_y"] - view["body_top_y"]
            values.append((view["ground_y"] - y) / height)
        rows.append(
            {
                "landmark": name,
                "normalizedHeights": {k: round(v, 4) for k, v in zip(VIEWS, values)},
                "mean": round(mean(values), 4),
                "stddev": round(pstdev(values), 4),
                "spread": round(max(values) - min(values), 4),
            }
        )
    return {
        "rows": rows,
        "maxSpread": max(row["spread"] for row in rows),
        "meanSpread": round(mean(row["spread"] for row in rows), 4),
        "reviewThreshold": 0.06,
    }


def draw_overlay(source: Image.Image) -> Image.Image:
    base = source.convert("RGBA")
    annotations = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(annotations, "RGBA")
    title_font = load_font(28, bold=True)
    label_font = load_font(16, bold=True)
    small_font = load_font(13)

    for view_name, view in VIEWS.items():
        x0, y0, x1, y1 = view["bbox"]
        draw.rounded_rectangle([x0, y0, x1, y1], radius=16, outline=(30, 140, 255, 150), width=3)
        draw.text((x0 + 8, 70), view["label"], font=title_font, fill=(10, 70, 130, 255))
        draw.line([(x0, view["ground_y"]), (x1, view["ground_y"])], fill=(20, 120, 255, 170), width=2)

        for block_name, (cx, cy, width, height) in MASS_ELLIPSES_2D[view_name].items():
            box = [cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2]
            color = {
                "skull": (50, 180, 255, 38),
                "ribcage": (40, 220, 170, 42),
                "abdomen": (255, 190, 40, 42),
                "pelvis": (180, 80, 255, 42),
            }[block_name]
            outline = color[:3] + (185,)
            draw.ellipse(box, fill=color, outline=outline, width=3)
            draw.text((cx - width / 2 + 5, cy - height / 2 + 4), block_name.upper(), font=small_font, fill=outline)

        for zone_id, (cx, cy, width, height) in SOFT_TISSUE_ELLIPSES_2D[view_name]:
            box = [cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2]
            draw.ellipse(box, fill=COLORS["soft-tissue"], outline=COLORS["soft-tissue-line"], width=2)
            if zone_id in {"neck-cheek-chest-fur", "ribcage-abdomen-skin", "tail-root-fur-socket"}:
                label = zone_id.replace("-fur", "").replace("-skin", "").replace("-socket", "").upper()
                draw.text((cx - width / 2 + 5, cy + height / 2 - 18), label, font=small_font, fill=COLORS["soft-tissue-line"])

        for _, start_xy, end_xy in SOFT_TISSUE_MOMENT_ANCHORS_2D[view_name]:
            draw_anchor_vector(draw, tuple(start_xy), tuple(end_xy), radius=5)

        for side in ("L", "R"):
            skull = tuple(LANDMARKS_2D[view_name]["skull_center"][0])
            ear_base = tuple(HEAD_ANCHORS_2D[view_name][f"ear_base_{side}"]["xy"])
            ear_tip = tuple(HEAD_ANCHORS_2D[view_name][f"ear_tip_{side}"]["xy"])
            ear_inner = tuple(HEAD_ANCHORS_2D[view_name][f"ear_inner_{side}"]["xy"])
            draw.line([skull, ear_base], fill=COLORS["ear-chain"], width=3)
            draw.line([ear_base, ear_tip], fill=COLORS["ear-chain"], width=4)
            draw.line([ear_base, ear_inner], fill=COLORS["ear-chain"], width=2)

        for a, b, _ in AUXILIARY_REFERENCE_SEGMENTS:
            def xy_for(name: str) -> tuple[int, int]:
                if name in LANDMARKS_2D[view_name]:
                    return tuple(LANDMARKS_2D[view_name][name][0])
                if name in HEAD_ANCHORS_2D[view_name]:
                    return tuple(HEAD_ANCHORS_2D[view_name][name]["xy"])
                return tuple(AUXILIARY_JOINTS_2D[view_name][name]["xy"])

            draw.line([xy_for(a), xy_for(b)], fill=COLORS["auxiliary"], width=2)

        points = LANDMARKS_2D[view_name]
        for a, b, group in SEGMENTS:
            pa = points[a][0]
            pb = points[b][0]
            draw.line([tuple(pa), tuple(pb)], fill=COLORS[group], width=5)

        for name, (xy, visibility) in points.items():
            x, y = xy
            radius = 6 if visibility in {"visible", "partly-visible"} else 5
            fill = COLORS[visibility]
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=fill, outline=(25, 25, 25, 240), width=2)
            if name in {
                "skull_center",
                "neck_base",
                "ribcage_center",
                "pelvis_center",
                "shoulder_L",
                "elbow_L",
                "wrist_L",
                "forepaw_L",
                "hip_L",
                "knee_L",
                "hock_L",
                "tail_root",
                "tail_tip",
            }:
                short = (
                    name.replace("_center", "")
                    .replace("shoulder", "SH")
                    .replace("elbow", "EL")
                    .replace("wrist", "WR")
                    .replace("forepaw", "FP")
                    .replace("hip", "HP")
                    .replace("knee", "KN")
                    .replace("hock", "HK")
                    .replace("tail_root", "TR")
                    .replace("tail_tip", "TT")
                    .upper()
                )
                draw.text((x + 8, y - 9), short, font=label_font, fill=(15, 15, 15, 235), stroke_width=2, stroke_fill=(255, 255, 255, 230))

        for anchor_name, anchor in HEAD_ANCHORS_2D[view_name].items():
            if anchor_name.startswith("eye_safe_ellipse"):
                cx, cy = anchor["center"]
                rx, ry = anchor["radii"]
                draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=COLORS["eye-safe"], width=3)
                continue
            if anchor_name.startswith("eye_cover_zone"):
                cx, cy = anchor["center"]
                rx, ry = anchor["radii"]
                draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=COLORS["cover-zone"], width=3)
                continue
            x, y = anchor["xy"]
            if anchor_name.startswith("ear"):
                fill = COLORS["ear"] if anchor["visibility"] == "visible" else COLORS["occluded"]
                draw.polygon([(x, y - 5), (x + 5, y), (x, y + 5), (x - 5, y)], fill=fill, outline=(255, 255, 255, 235))
            else:
                fill = COLORS["eye"] if anchor["visibility"] == "visible" else COLORS["occluded"]
                draw.rectangle([x - 4, y - 4, x + 4, y + 4], fill=fill, outline=(255, 255, 255, 235), width=1)
            if anchor_name.startswith("eye_center"):
                short = "EYE_" + anchor_name.rsplit("_", 1)[-1]
                draw.text((x + 7, y - 8), short, font=small_font, fill=(20, 50, 95, 255), stroke_width=2, stroke_fill=(255, 255, 255, 230))
            if anchor_name.startswith("ear_base") or anchor_name.startswith("ear_tip"):
                short = anchor_name.replace("ear_base", "EAR_B").replace("ear_tip", "EAR_T").upper()
                draw.text((x + 7, y - 8), short, font=small_font, fill=(10, 95, 90, 255), stroke_width=2, stroke_fill=(255, 255, 255, 230))

        for aux_name, aux in AUXILIARY_JOINTS_2D[view_name].items():
            x, y = aux["xy"]
            fill = COLORS["auxiliary-joint"] if aux["visibility"] != "occluded" else COLORS["occluded"]
            draw.rectangle([x - 5, y - 5, x + 5, y + 5], fill=fill, outline=(255, 255, 255, 235), width=1)
            if aux_name in {"cheek_fur_L", "cheek_fur_R", "ear_mid_L", "ear_mid_R", "chest_fur_tip", "armpit_L", "armpit_R", "foretoe_L", "foretoe_R", "hindtoe_L", "hindtoe_R"}:
                short = (
                    aux_name.replace("cheek_fur", "CHK")
                    .replace("whisker_root", "WH")
                    .replace("ear_mid", "EAR_M")
                    .replace("chest_fur_tip", "CHEST")
                    .replace("armpit", "ARM")
                    .replace("foretoe", "FTOE")
                    .replace("hindtoe", "HTOE")
                    .replace("tail_base_socket", "TS")
                    .upper()
                )
                draw.text((x + 7, y - 8), short, font=small_font, fill=(15, 60, 145, 255), stroke_width=2, stroke_fill=(255, 255, 255, 230))

    legend_y = 812
    draw.rounded_rectangle([65, 797, 1708, 867], radius=14, fill=(255, 255, 255, 225), outline=(40, 80, 120, 120), width=2)
    draw.text((80, legend_y), "L/R = cat anatomy", font=label_font, fill=(20, 20, 20, 255))
    items = [
        ("left chain", COLORS["left"]),
        ("right chain", COLORS["right"]),
        ("tail", COLORS["tail"]),
        ("eye anchor", COLORS["eye"]),
        ("ear anchor", COLORS["ear"]),
        ("ear chain", COLORS["ear-chain"]),
        ("cover zone", COLORS["cover-zone"]),
        ("soft tissue", COLORS["soft-tissue-line"]),
        ("muscle anchor", COLORS["muscle-anchor"]),
        ("aux joint", COLORS["auxiliary-joint"]),
        ("visible", COLORS["visible"]),
        ("inferred", COLORS["inferred"]),
        ("occluded", COLORS["occluded"]),
    ]
    x = 270
    for label, color in items:
        if x > 1570:
            x = 270
            legend_y += 28
        draw.ellipse([x, legend_y + 2, x + 14, legend_y + 16], fill=color, outline=(20, 20, 20, 230))
        draw.text((x + 20, legend_y), label, font=label_font, fill=(20, 20, 20, 255))
        x += 160
    draw.text((80, 850), "Mass ellipses are volume constraints, not cut lines. Auxiliary joints are future layer/triangulation seeds, not ArtMesh.", font=small_font, fill=(65, 65, 65, 255))
    return Image.alpha_composite(base, annotations)


def build_review_sheet(source: Image.Image, overlay: Image.Image) -> Image.Image:
    margin = 38
    gap = 54
    header = 72
    width = source.width + margin * 2
    height = header + source.height * 2 + gap + margin
    sheet = Image.new("RGB", (width, height), "#eef3f7")
    draw = ImageDraw.Draw(sheet)
    title = load_font(30, bold=True)
    subtitle = load_font(19)
    draw.text((margin, 18), "X1 CANONICAL BODY REVIEW — ORIGINAL / ANATOMICAL OVERLAY", font=title, fill=(20, 55, 85))
    draw.text((margin, header - 4), "Original three-view source", font=subtitle, fill=(40, 70, 95))
    sheet.paste(source.convert("RGB"), (margin, header + 22))
    second_y = header + 22 + source.height + gap
    draw.text((margin, second_y - 31), "X1 candidate overlay — inferred joints remain provisional", font=subtitle, fill=(40, 70, 95))
    sheet.paste(overlay.convert("RGB"), (margin, second_y))
    return sheet


def draw_canonical_projections() -> Image.Image:
    width, height = 1500, 850
    base = Image.new("RGBA", (width, height), (244, 248, 251, 255))
    annotations = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(annotations, "RGBA")
    title_font = load_font(30, bold=True)
    panel_font = load_font(24, bold=True)
    label_font = load_font(13, bold=True)
    note_font = load_font(16)
    scale = 560.0

    panels = {
        "front": {"origin": (250, 690), "label": "CANONICAL FRONT  (x / y)"},
        "side": {"origin": (750, 690), "label": "CANONICAL SIDE  (z / y)"},
        "top": {"origin": (1250, 430), "label": "CANONICAL TOP  (x / z)"},
    }

    draw.text((38, 22), "X1 — ONE CANONICAL 3D BODY, THREE ORTHOGRAPHIC PROJECTIONS", font=title_font, fill=(18, 58, 92, 255))

    def project(view_name: str, point: list[float]) -> tuple[float, float]:
        ox, oy = panels[view_name]["origin"]
        x, y, z = point
        if view_name == "front":
            return ox - x * scale, oy - y * scale
        if view_name == "side":
            return ox - z * scale, oy - y * scale
        return ox - x * scale, oy + z * scale

    for view_name, panel in panels.items():
        ox, oy = panel["origin"]
        draw.rounded_rectangle([ox - 220, 105, ox + 220, 748], radius=18, fill=(255, 255, 255, 235), outline=(30, 120, 200, 150), width=3)
        draw.text((ox - 205, 122), panel["label"], font=panel_font, fill=(20, 78, 125, 255))
        if view_name in {"front", "side"}:
            draw.line([(ox - 190, oy), (ox + 190, oy)], fill=(80, 100, 115, 120), width=2)
            draw.line([(ox, oy), (ox, 205)], fill=(80, 100, 115, 120), width=2)
        else:
            draw.line([(ox - 190, oy), (ox + 190, oy)], fill=(80, 100, 115, 120), width=2)
            draw.line([(ox, 230), (ox, 650)], fill=(80, 100, 115, 120), width=2)

        for block_name, block in MASS_BLOCKS.items():
            cx, cy = project(view_name, block["center"])
            rx, ry, rz = block["radii"]
            if view_name == "front":
                pw, ph = rx * scale, ry * scale
            elif view_name == "side":
                pw, ph = rz * scale, ry * scale
            else:
                pw, ph = rx * scale, rz * scale
            color = {
                "skull": (50, 180, 255, 40),
                "ribcage": (40, 220, 170, 44),
                "abdomen": (255, 190, 40, 44),
                "pelvis": (180, 80, 255, 44),
            }[block_name]
            draw.ellipse([cx - pw, cy - ph, cx + pw, cy + ph], fill=color, outline=color[:3] + (190,), width=3)

        for a, b, group in SEGMENTS:
            pa = project(view_name, CANONICAL_JOINTS[a])
            pb = project(view_name, CANONICAL_JOINTS[b])
            draw.line([pa, pb], fill=COLORS[group], width=5)

        for volume_name, volume in HEAD_REFERENCE_VOLUMES.items():
            cx, cy = project(view_name, volume["center"])
            rx, ry, rz = volume["radii"]
            if view_name == "front":
                pw, ph = rx * scale, ry * scale
            elif view_name == "side":
                pw, ph = rz * scale, ry * scale
            else:
                pw, ph = rx * scale, rz * scale
            color = COLORS["eye-safe"] if "safe" in volume_name else COLORS["cover-zone"]
            draw.ellipse([cx - pw, cy - ph, cx + pw, cy + ph], outline=color, width=3)

        for segment in HEAD_REFERENCE_SEGMENTS:
            pa = project(view_name, point3(segment["from"]))
            pb = project(view_name, point3(segment["to"]))
            draw.line([pa, pb], fill=COLORS["ear-chain"], width=3)

        for a, b, _ in AUXILIARY_REFERENCE_SEGMENTS:
            pa = project(view_name, point3(a))
            pb = project(view_name, point3(b))
            draw.line([pa, pb], fill=COLORS["auxiliary"], width=2)

        for name, point in CANONICAL_JOINTS.items():
            px, py = project(view_name, point)
            if name.endswith("_L"):
                fill = COLORS["left"]
            elif name.endswith("_R"):
                fill = COLORS["right"]
            elif name.startswith("tail"):
                fill = COLORS["tail"]
            else:
                fill = COLORS["head"]
            draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=fill, outline=(15, 25, 35, 235), width=2)
            if name in {"skull_center", "neck_base", "ribcage_center", "pelvis_center", "shoulder_L", "elbow_L", "wrist_L", "forepaw_L", "hip_L", "knee_L", "tail_root", "tail_tip"}:
                short = name.replace("_center", "").replace("shoulder", "SH").replace("elbow", "EL").replace("wrist", "WR").replace("forepaw", "FP").replace("hip", "HP").replace("knee", "KN").replace("tail_root", "TR").replace("tail_tip", "TT").upper()
                draw.text((px + 7, py - 8), short, font=label_font, fill=(20, 30, 40, 255), stroke_width=2, stroke_fill=(255, 255, 255, 235))

        for name, point in HEAD_REFERENCE_POINTS_3D.items():
            px, py = project(view_name, point)
            if name.startswith("ear"):
                draw.polygon([(px, py - 5), (px + 5, py), (px, py + 5), (px - 5, py)], fill=COLORS["ear"], outline=(255, 255, 255, 235))
            else:
                draw.rectangle([px - 4, py - 4, px + 4, py + 4], fill=COLORS["eye"], outline=(255, 255, 255, 235), width=1)
            if name.startswith("eye_center"):
                short = "EYE_" + name.rsplit("_", 1)[-1]
                draw.text((px + 7, py - 8), short, font=label_font, fill=(20, 50, 95, 255), stroke_width=2, stroke_fill=(255, 255, 255, 235))
            if name.startswith("ear_base") or name.startswith("ear_tip"):
                short = name.replace("ear_base", "EAR_B").replace("ear_tip", "EAR_T").upper()
                draw.text((px + 7, py - 8), short, font=label_font, fill=(10, 95, 90, 255), stroke_width=2, stroke_fill=(255, 255, 255, 235))

        for name, point in AUXILIARY_JOINTS_3D.items():
            px, py = project(view_name, point)
            draw.rectangle([px - 4, py - 4, px + 4, py + 4], fill=COLORS["auxiliary-joint"], outline=(255, 255, 255, 235), width=1)
            if name in {"cheek_fur_L", "cheek_fur_R", "ear_mid_L", "ear_mid_R", "chest_fur_tip", "armpit_L", "armpit_R", "foretoe_L", "foretoe_R", "hindtoe_L", "hindtoe_R"}:
                short = (
                    name.replace("cheek_fur", "CHK")
                    .replace("ear_mid", "EAR_M")
                    .replace("chest_fur_tip", "CHEST")
                    .replace("armpit", "ARM")
                    .replace("foretoe", "FTOE")
                    .replace("hindtoe", "HTOE")
                    .upper()
                )
                draw.text((px + 7, py - 8), short, font=label_font, fill=(15, 60, 145, 255), stroke_width=2, stroke_fill=(255, 255, 255, 235))

    draw.text((60, 785), "Magenta = cat left  |  Yellow = cat right  |  Green = tail  |  Blue = eye anchors  |  Dark blue squares/lines = auxiliary layer/triangulation seeds", font=note_font, fill=(35, 55, 70, 255))
    draw.text((60, 812), "This is a normalized topology/volume contract, not a calibrated 3D scan or ArtMesh. X2 contacts/torques and X6 eye rig remain unauthorized.", font=note_font, fill=(80, 80, 80, 255))
    return Image.alpha_composite(base, annotations).convert("RGB")


def draw_spread_pose_review_aid() -> Image.Image:
    width, height = 1500, 1000
    base = Image.new("RGBA", (width, height), (246, 249, 252, 255))
    annotations = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(annotations, "RGBA")
    title_font = load_font(30, bold=True)
    panel_font = load_font(20, bold=True)
    label_font = load_font(13, bold=True)
    note_font = load_font(16)

    draw.text((42, 28), "X1 REVIEW AID — SPREAD-POSE ANATOMY SKETCH (NOT A MASTER IMAGE)", font=title_font, fill=(18, 58, 92, 255))
    draw.text((42, 66), "Derived from the X1 topology for visual review only. It does not authorize X2, contact solve, or realistic spread-pose generation.", font=note_font, fill=(85, 85, 85, 255))

    ox, oy = 750, 645
    scale = 520

    def p(x: float, y: float) -> tuple[float, float]:
        return ox + x * scale, oy - y * scale

    spread = {
        "skull_center": [0.00, 0.74],
        "jaw_center": [0.00, 0.62],
        "neck_base": [0.00, 0.50],
        "ribcage_center": [0.00, 0.35],
        "abdomen_center": [0.00, 0.18],
        "pelvis_center": [0.00, 0.03],
        "scapula_L": [0.18, 0.42],
        "shoulder_L": [0.34, 0.38],
        "elbow_L": [0.55, 0.25],
        "wrist_L": [0.72, 0.08],
        "forepaw_L": [0.86, -0.04],
        "scapula_R": [-0.18, 0.42],
        "shoulder_R": [-0.34, 0.38],
        "elbow_R": [-0.55, 0.25],
        "wrist_R": [-0.72, 0.08],
        "forepaw_R": [-0.86, -0.04],
        "hip_L": [0.24, 0.05],
        "knee_L": [0.48, -0.04],
        "hock_L": [0.67, -0.17],
        "hindpaw_L": [0.82, -0.30],
        "hip_R": [-0.24, 0.05],
        "knee_R": [-0.48, -0.04],
        "hock_R": [-0.67, -0.17],
        "hindpaw_R": [-0.82, -0.30],
        "tail_root": [0.00, -0.05],
        "tail_mid_1": [0.18, -0.18],
        "tail_mid_2": [0.34, -0.27],
        "tail_tip": [0.50, -0.30],
        "eye_center_L": [0.10, 0.71],
        "eye_center_R": [-0.10, 0.71],
        "ear_base_L": [0.15, 0.84],
        "ear_tip_L": [0.24, 1.00],
        "ear_inner_L": [0.15, 0.90],
        "ear_base_R": [-0.15, 0.84],
        "ear_tip_R": [-0.24, 1.00],
        "ear_inner_R": [-0.15, 0.90],
        "cheek_fur_L": [0.18, 0.62],
        "cheek_fur_R": [-0.18, 0.62],
        "whisker_root_L": [0.20, 0.60],
        "whisker_root_R": [-0.20, 0.60],
        "ear_mid_L": [0.20, 0.92],
        "ear_mid_R": [-0.20, 0.92],
        "chest_fur_tip": [0.00, 0.30],
        "armpit_L": [0.24, 0.30],
        "armpit_R": [-0.24, 0.30],
        "foretoe_L": [0.92, -0.08],
        "foretoe_R": [-0.92, -0.08],
        "hindtoe_L": [0.88, -0.34],
        "hindtoe_R": [-0.88, -0.34],
        "tail_base_socket_L": [0.09, -0.08],
        "tail_base_socket_R": [-0.09, -0.08],
    }

    mass_shapes = {
        "skull": {"center": [0.00, 0.72], "radii": [0.22, 0.17], "color": (50, 180, 255, 42)},
        "ribcage": {"center": [0.00, 0.35], "radii": [0.25, 0.20], "color": (40, 220, 170, 46)},
        "abdomen": {"center": [0.00, 0.18], "radii": [0.23, 0.15], "color": (255, 190, 40, 46)},
        "pelvis": {"center": [0.00, 0.03], "radii": [0.24, 0.14], "color": (180, 80, 255, 46)},
    }

    draw.rounded_rectangle([45, 120, 1455, 895], radius=18, fill=(255, 255, 255, 235), outline=(30, 120, 200, 150), width=3)
    draw.line([p(-1.05, -0.34), p(1.05, -0.34)], fill=(80, 100, 115, 100), width=2)
    draw.line([p(0, -0.38), p(0, 0.93)], fill=(80, 100, 115, 90), width=2)

    for name, shape in mass_shapes.items():
        cx, cy = p(*shape["center"])
        rx, ry = shape["radii"]
        draw.ellipse([cx - rx * scale, cy - ry * scale, cx + rx * scale, cy + ry * scale], fill=shape["color"], outline=shape["color"][:3] + (190,), width=3)
        draw.text((cx - rx * scale + 8, cy - ry * scale + 8), name.upper(), font=label_font, fill=shape["color"][:3] + (230,))

    for side in ("L", "R"):
        eye = spread[f"eye_center_{side}"]
        ex, ey = p(*eye)
        draw.ellipse([ex - 30, ey - 38, ex + 30, ey + 38], outline=COLORS["eye-safe"], width=3)
        draw.ellipse([ex - 40, ey - 48, ex + 40, ey + 48], outline=COLORS["cover-zone"], width=3)
        ear_base = p(*spread[f"ear_base_{side}"])
        ear_tip = p(*spread[f"ear_tip_{side}"])
        ear_inner = p(*spread[f"ear_inner_{side}"])
        draw.line([p(*spread["skull_center"]), ear_base], fill=COLORS["ear-chain"], width=3)
        draw.line([ear_base, ear_tip], fill=COLORS["ear-vector"], width=5)
        draw.line([ear_base, ear_inner], fill=COLORS["ear-vector"], width=3)

    for zone_id, (cx, cy, rx, ry) in SOFT_TISSUE_SPREAD_ELLIPSES:
        x, y = p(cx, cy)
        draw.ellipse([x - rx * scale, y - ry * scale, x + rx * scale, y + ry * scale], fill=COLORS["soft-tissue"], outline=COLORS["soft-tissue-line"], width=3)
        if zone_id in {"neck-cheek-chest-fur", "ribcage-abdomen-skin", "tail-root-fur-socket"}:
            label = zone_id.replace("-fur", "").replace("-skin", "").replace("-socket", "").upper()
            draw.text((x - rx * scale + 8, y + ry * scale - 20), label, font=label_font, fill=COLORS["soft-tissue-line"], stroke_width=2, stroke_fill=(255, 255, 255, 210))

    spread_anchor_pairs = {
        "neck-fur-pull": ("neck_base", "ribcage_center"),
        "left-scapula-sling-pivot": ("scapula_L", "shoulder_L"),
        "right-scapula-sling-pivot": ("scapula_R", "shoulder_R"),
        "left-forelimb-elbow-sleeve": ("elbow_L", "wrist_L"),
        "right-forelimb-elbow-sleeve": ("elbow_R", "wrist_R"),
        "belly-skin-hinge": ("abdomen_center", "pelvis_center"),
        "left-thigh-soft-hinge": ("hip_L", "knee_L"),
        "right-thigh-soft-hinge": ("hip_R", "knee_R"),
        "tail-root-socket-pull": ("tail_root", "tail_mid_1"),
        "left-ear-root-pivot": ("ear_base_L", "ear_tip_L"),
        "right-ear-root-pivot": ("ear_base_R", "ear_tip_R"),
    }
    for _, (start_name, end_name) in spread_anchor_pairs.items():
        draw_anchor_vector(draw, p(*spread[start_name]), p(*spread[end_name]), radius=6)

    for a, b, group in SEGMENTS:
        if a not in spread or b not in spread:
            continue
        draw.line([p(*spread[a]), p(*spread[b])], fill=COLORS[group], width=6)

    for a, b, _ in AUXILIARY_REFERENCE_SEGMENTS:
        if a not in spread or b not in spread:
            continue
        draw.line([p(*spread[a]), p(*spread[b])], fill=COLORS["auxiliary"], width=3)

    for name, point in spread.items():
        x, y = p(*point)
        if name.endswith("_L"):
            fill = COLORS["left"]
        elif name.endswith("_R"):
            fill = COLORS["right"]
        elif name.startswith("tail"):
            fill = COLORS["tail"]
        elif name.startswith("eye"):
            fill = COLORS["eye"]
        elif name.startswith("ear"):
            fill = COLORS["ear"]
        elif name in AUXILIARY_JOINTS_3D:
            fill = COLORS["auxiliary-joint"]
        else:
            fill = COLORS["head"]
        if name.startswith("eye"):
            draw.rectangle([x - 5, y - 5, x + 5, y + 5], fill=fill, outline=(255, 255, 255, 235), width=1)
        elif name.startswith("ear"):
            draw.polygon([(x, y - 6), (x + 6, y), (x, y + 6), (x - 6, y)], fill=fill, outline=(255, 255, 255, 235))
        elif name in AUXILIARY_JOINTS_3D:
            draw.rectangle([x - 5, y - 5, x + 5, y + 5], fill=fill, outline=(255, 255, 255, 235), width=1)
        else:
            draw.ellipse([x - 6, y - 6, x + 6, y + 6], fill=fill, outline=(15, 25, 35, 235), width=2)
        if name in {
            "skull_center",
            "neck_base",
            "ribcage_center",
            "pelvis_center",
            "shoulder_L",
            "elbow_L",
            "wrist_L",
            "forepaw_L",
            "shoulder_R",
            "elbow_R",
            "wrist_R",
            "forepaw_R",
            "hip_L",
            "knee_L",
            "hock_L",
            "hindpaw_L",
            "hip_R",
            "knee_R",
            "hock_R",
            "hindpaw_R",
            "tail_root",
            "tail_tip",
            "eye_center_L",
            "eye_center_R",
            "ear_base_L",
            "ear_tip_L",
            "ear_base_R",
            "ear_tip_R",
            "cheek_fur_L",
            "cheek_fur_R",
            "ear_mid_L",
            "ear_mid_R",
            "chest_fur_tip",
            "armpit_L",
            "armpit_R",
            "foretoe_L",
            "foretoe_R",
            "hindtoe_L",
            "hindtoe_R",
        }:
            short = (
                name.replace("_center", "")
                .replace("cheek_fur", "CHK")
                .replace("ear_mid", "EAR_M")
                .replace("chest_fur_tip", "CHEST")
                .replace("armpit", "ARM")
                .replace("foretoe", "FTOE")
                .replace("hindtoe", "HTOE")
                .replace("shoulder", "SH")
                .replace("elbow", "EL")
                .replace("wrist", "WR")
                .replace("forepaw", "FP")
                .replace("hip", "HP")
                .replace("knee", "KN")
                .replace("hock", "HK")
                .replace("hindpaw", "HFP")
                .replace("tail_root", "TR")
                .replace("tail_tip", "TT")
                .upper()
            )
            draw.text((x + 8, y - 8), short, font=label_font, fill=(20, 30, 40, 255), stroke_width=2, stroke_fill=(255, 255, 255, 235))

    draw.text((70, 842), "Review purpose: exposes limb identity, segment continuity, mass volumes, soft-tissue envelopes, eye anchors, and cover zones.", font=note_font, fill=(45, 65, 85, 255))
    draw.text((70, 870), "Boundary: schematic spread sketch only; not a new identity source, not a realistic master, not X2 support/contact/moment evidence.", font=note_font, fill=(110, 70, 45, 255))
    draw.text((70, 912), "Magenta = cat left | Yellow = cat right | Green = tail | Purple = future soft-tissue controls | Blue squares = auxiliary layer/triangulation seeds", font=note_font, fill=(35, 55, 70, 255))

    return Image.alpha_composite(base, annotations).convert("RGB")


def write_report(contract: dict, consistency: dict) -> None:
    inferred_count = 0
    occluded_count = 0
    visible_count = 0
    for points in LANDMARKS_2D.values():
        for _, visibility in points.values():
            if visibility == "inferred":
                inferred_count += 1
            elif visibility == "occluded":
                occluded_count += 1
            else:
                visible_count += 1

    mass_sum = sum(block["mass_fraction"] for block in MASS_BLOCKS.values())
    symmetry_pairs = []
    for side_name in ["scapula", "shoulder", "elbow", "wrist", "forepaw", "hip", "knee", "hock", "hindpaw"]:
        left = CANONICAL_JOINTS[f"{side_name}_L"]
        right = CANONICAL_JOINTS[f"{side_name}_R"]
        symmetry_pairs.append(
            {
                "name": side_name,
                "x_error": abs(left[0] + right[0]),
                "yz_error": abs(left[1] - right[1]) + abs(left[2] - right[2]),
            }
        )
    max_symmetry_error = max(item["x_error"] + item["yz_error"] for item in symmetry_pairs)

    pass_checks = {
        "same landmark vocabulary in all three views": all(set(points) == set(CANONICAL_JOINTS) for points in LANDMARKS_2D.values()),
        "mass fractions sum to one": abs(mass_sum - 1.0) < 1e-9,
        "canonical paired joints are symmetric": max_symmetry_error < 1e-9,
        "vertical alignment spread below review threshold": consistency["maxSpread"] <= consistency["reviewThreshold"],
        "side forelimbs fold shoulder-to-caudal-elbow-to-cranial-wrist": all(LANDMARKS_2D["side"][f"shoulder_{side}"][0][0] < LANDMARKS_2D["side"][f"elbow_{side}"][0][0] and LANDMARKS_2D["side"][f"wrist_{side}"][0][0] < LANDMARKS_2D["side"][f"elbow_{side}"][0][0] for side in ("L", "R")),
        "canonical forelimbs preserve the caudal elbow branch": all(CANONICAL_JOINTS[f"elbow_{side}"][2] < CANONICAL_JOINTS[f"shoulder_{side}"][2] and CANONICAL_JOINTS[f"wrist_{side}"][2] > CANONICAL_JOINTS[f"elbow_{side}"][2] for side in ("L", "R")),
        "X2 remains unauthorized": contract["gatePolicy"]["x2Authorized"] is False,
    }

    rows = "\n".join(
        f"| `{row['landmark']}` | {row['normalizedHeights']['front']:.4f} | {row['normalizedHeights']['side']:.4f} | {row['normalizedHeights']['back']:.4f} | {row['spread']:.4f} |"
        for row in consistency["rows"]
    )
    checks = "\n".join(f"- [{'x' if ok else ' '}] {name}" for name, ok in pass_checks.items())

    report = f"""# 小橘 X1 统一身体报告

> 状态：候选，等待用户 X1 Gate 审核。本文不授权进入 X2、生成完整母版、拆层或 Cubism。

## 产物

- `x1-canonical-body-contract.json`：统一三维近似骨架、固定骨段、质量块、视图标注和 Gate 约束。
- `qa/x1-three-view-landmark-overlay.png`：三视图骨架、可见性与质量块叠加图。
- `qa/x1-three-view-review-sheet.png`：原图与标注图上下对照。
- `qa/x1-canonical-skeleton-projections.png`：同一套近似 3D 骨架与质量块的正、侧、顶投影。
- `qa/x1-spread-pose-review-aid.png`：大字型/展开姿势工程草图，只用于 X1 视觉审核辅助，不是写实母版。

## 解释边界

源图的三个视角在尺寸和地面基线上一致，但不是经过相机标定的严格正交工程图。毛发和坐姿遮住肩胛、髋、远侧肢体与部分尾根，因此本阶段只冻结：

1. 同名解剖点和左右身份；
2. 一套近似 3D 拓扑与骨段长度；
3. 头、肋笼、腹部和骨盆四个不可坍缩质量块；
4. 前肢、后肢和尾巴的连续父子链；
5. 推断点的风险等级。

X1 不声称已经得到精确猫科三维扫描，也不在此阶段确定遮眼动作的数值关节范围。动作范围、接触和力矩属于 X2。

## X1 修订：眼部参考锚点

本版根据用户审核意见补充头部局部参考锚点：`eye_socket_L/R`、`eye_center_L/R`、`eye_safe_ellipse_L/R`、`eye_cover_zone_L/R`，以及 `ear_base_L/R`、`ear_tip_L/R`、`ear_inner_L/R`。这些锚点只用于后续 X2 遮眼目标、X5 节点支点、X6 眼部参数和 X7 耳朵弹性控制的共同坐标依据。

这些锚点不是眼球转动解、眼睑 Deformer、耳朵 Deformer、耳尖 Physics、爪部接触、重心支撑或力矩求解。侧视右眼、背视双眼和部分耳内面仍按遮挡/推断风险处理。

## X1 修订：耳朵参考链

本版补充 `headReferenceSegments`，把耳朵锚点接回头骨：`skull_center -> ear_base_L/R -> ear_tip_L/R`，并从 `ear_base_L/R` 接到 `ear_inner_L/R`。这样后续 X5-X7 可以明确从头部运动传递到耳根，再由耳根带动耳尖和耳面。

这些线仍然只是头部局部拓扑和力矩传递参考，不是耳朵 Rotation Deformer、ArtMesh、Physics 或弹性数值。耳朵实际摆动、耳尖滞后、耳面压缩和注意力参数必须留到后续 Gate。

## X1 修订：力矩预检边界

本版在合同中加入 `momentPreflight`，只列出未来必须求解的力矩链：

- 遮眼前肢链：肩胛、肩、肘、腕、前爪到 `eye_cover_zone`；
- 眼部链：头骨、眼眶、眼球中心、上下眼睑。

X1 仍禁止数值力矩、接触反力、重心支撑、眼部 Deformer 支点和任何动作曲线。它们必须在 X2 或 X5-X6 获得用户 Gate 批准后再解。

## X1 修订：肌肉/软组织包络控制区

本版根据用户审核意见补充 `softTissueControlZones`，用于说明关键骨架周边的肌肉、皮肤和毛发包络以后应如何被控制。它们包括：

- 颈部、脸颊和胸毛软层；
- 左右耳根、耳面和耳尖软组织；
- 左右肩胛到胸侧的软组织吊带；
- 左右前肢上臂/前臂包络；
- 胸腹表皮包络；
- 左右髋、大腿和后腿包络；
- 尾根毛发/皮肤插口。

这些区域只是在 X1 阶段标出未来 X4/X5 拆层、ArtMesh 和 Deformer 的控制依据。它们不是正式网格、不是 Rotation Deformer、不是 Physics 分组，也不定义权重、曲线或变形极值。后续正式控制必须在 X4/X5 Gate 中逐层填写合同并用视觉证据验证。

## X1 修订：肌肉力矩参考锚点

本版在 `softTissueControlZones` 之外补充 `softTissueMomentAnchors`。这些锚点用紫色或青绿色菱形和短向量标在 QA 图中，只表示未来软组织控制的 pivot / pull 方向，例如肩胛胸侧吊带、前臂包络、腹部皮肤、髋腿包络、尾根插口和耳根到耳尖的注意力/弹性方向。

这些锚点不是数值力矩解，不包含扭矩大小、弹簧刚度、阻尼、权重、ArtMesh 拓扑或 Physics 设置。它们只保证后续 X4/X5 设计 Deformer 和网格时不会只看到骨架线，而能同时看到周边肌肉/毛皮应围绕哪些点被牵拉。

## X1 修订：辅助关节与三角剖分种子

本版根据用户审核意见补充 `auxiliaryReferenceJoints`、`auxiliaryJoints2D/3D` 和 `auxiliaryReferenceSegments`。新增点包括脸颊毛、胡须根、耳中点、胸毛尖、左右腋下、前后爪趾缘和尾根套口。这些点用于后续 X4/X5 拆层、节点树和 ArtMesh 设计时保留语义边界，也给未来三角剖分提供清楚的边界点和内部控制种子。

用户提供的知乎文章 `https://zhuanlan.zhihu.com/p/383268858` 被记录为参考来源；实现时页面直接抓取不稳定，因此本 X1 只采纳通用网格原则：未来网格需要明确顶点、边和三角面，关键解剖边界与局部支点应先作为语义点保留。X1 仍不生成 Delaunay/Cubism 三角剖分、不定义 ArtMesh 顶点表、不写权重、不设置 Deformer，也不进入 X2。

## 后续产物请求：大字型小橘参考图

用户提出需要一张大字型/展开姿势的小橘图，以便后续更清楚地绘制隐藏肢体、躯干和眼部相关部分。该需求已记录到合同的 `futureArtifactRequests.spreadPoseXiaojuPlate`。

本 X1 版本只生成 `qa/x1-spread-pose-review-aid.png` 作为工程草图：它展示统一骨架、体块、展开四肢、眼部锚点和遮眼目标区，帮助人工判断结构是否清楚。它不是写实完整图，不替代三视图权威输入，不授权 X2，也不作为后续拆层母版。

真正可用于绘制隐藏结构或拆层的写实大字型参考图仍属于后续 Gate。后续若授权，必须从已批准的 X1 身体和 X2 支撑/动作约束派生，不能替代三视图权威输入，也不能绕过隐藏结构验证。

## 生物学拓扑核验

- 前肢按猫科研究中的肩胛、上臂、前臂、腕段建模，并保留肩、肘、腕三个主要关节。侧视折叠链已修正为肩在前、肘向后、腕和爪再回到前方。
- 后肢保持髋、膝、跗/踝、爪的连续链；X1 只冻结拓扑，不把三维研究中的成人猫关节角直接套到小橘的幼猫比例上。
- 姿势研究用于确认关节力与末端支撑必须联合求解；这些力矩和接触数值仍严格留在 X2。
- 眼部锚点用于保留头部局部坐标和未来眼眶安全范围；眼球、眼睑和遮眼接触力矩尚未求解。

参考：

- [Role of forelimb morphology in muscle sensorimotor functions during locomotion in the cat](https://pmc.ncbi.nlm.nih.gov/articles/PMC11737544/)
- [A Three Dimensional Model of the Feline Hindlimb](https://pmc.ncbi.nlm.nih.gov/articles/PMC2043500/)
- [Biomechanical capabilities influence postural control strategies in the cat hindlimb](https://pmc.ncbi.nlm.nih.gov/articles/PMC3137431/)

## 标注统计

- 可见或部分可见观察：{visible_count}
- 推断观察：{inferred_count}
- 完全遮挡观察：{occluded_count}
- 质量比例合计：{mass_sum:.2f}
- 归一化垂直对齐最大 spread：{consistency['maxSpread']:.4f}
- 归一化垂直对齐平均 spread：{consistency['meanSpread']:.4f}
- X1 审核阈值：{consistency['reviewThreshold']:.4f}

## 三视图垂直一致性

归一化值以各视图地面到身体顶部的高度为 1。它用于发现视图比例漂移，不代表三维深度。

| Landmark | Front | Side | Back | Spread |
| --- | ---: | ---: | ---: | ---: |
{rows}

## 自动自检

{checks}

## 必须由用户视觉确认的点

- 肩胛和肩关节是否偏高或偏外；
- 侧视髋、膝、跗的折叠方向是否符合小橘体型；
- 背视前肢完全遮挡时的左右位置是否可接受；
- 尾根与尾巴三维走向是否应在后续目标姿势中重新定向；
- 四个质量块是否保留了小橘的幼猫头身比和圆润体积；
- 眼眶中心、眼球中心、安全椭圆和遮眼目标区是否符合小橘脸部比例；
- 肩胛胸侧、前肢、胸腹、髋腿、颈胸毛和尾根软组织包络是否覆盖了后续拆层/网格需要；
- 肌肉力矩参考锚点的 pivot / pull 方向是否足够表达后续软组织控制需求；
- 耳根、耳尖、耳内面锚点和耳根到耳尖的牵拉方向是否符合小橘耳朵比例；
- 耳朵参考链 `skull_center -> ear_base -> ear_tip / ear_inner` 是否足够表达头部带动耳朵的关系；
- 辅助关节节点是否覆盖脸颊毛、胡须根、耳中、胸毛、腋下、爪趾缘和尾根套口等后续拆层/三角剖分需要；
- 辅助参考线是否足够表达未来网格种子之间的语义连接，但又没有误导成正式 ArtMesh；
- 是否同意把大字型/展开姿势参考图作为 X1 通过后的后续 Gate 产物，而不是当前 X1 产物。

## Gate 结论

自动检查只证明合同内部一致，不等于 X1 通过。当前状态保持 `candidate-for-user-review`，X2 明确为未授权。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE).convert("RGB")
    if source.size != (1774, 887):
        raise SystemExit(f"Unexpected source size: {source.size}")

    contract = build_contract()
    consistency = vertical_consistency()
    contract["qa"] = {
        "verticalConsistency": consistency,
        "overlay": str(OVERLAY_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
        "reviewSheet": str(SHEET_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
        "canonicalProjections": str(CANONICAL_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
        "spreadPoseReviewAid": str(SPREAD_AID_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
        "report": str(REPORT_PATH.relative_to(PET_ROOT)).replace("\\", "/"),
    }
    CONTRACT_PATH.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    overlay = draw_overlay(source)
    overlay.save(OVERLAY_PATH)
    review_sheet = build_review_sheet(source, overlay)
    review_sheet.save(SHEET_PATH)
    canonical_sheet = draw_canonical_projections()
    canonical_sheet.save(CANONICAL_PATH)
    spread_aid = draw_spread_pose_review_aid()
    spread_aid.save(SPREAD_AID_PATH)
    write_report(contract, consistency)

    print(json.dumps({
        "contract": str(CONTRACT_PATH),
        "report": str(REPORT_PATH),
        "overlay": str(OVERLAY_PATH),
        "reviewSheet": str(SHEET_PATH),
        "canonicalProjections": str(CANONICAL_PATH),
        "spreadPoseReviewAid": str(SPREAD_AID_PATH),
        "maxVerticalSpread": consistency["maxSpread"],
        "status": contract["status"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
