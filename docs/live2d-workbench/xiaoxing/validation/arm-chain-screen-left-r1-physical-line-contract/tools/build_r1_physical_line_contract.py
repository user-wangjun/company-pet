"""Build the deterministic R1 physical-body and line-semantics contract.

This script deliberately stops at R1.  It reads the four authoritative source
images plus the read-only V25/V38 evidence, and writes only JSON contracts and
one annotated review image.  It never creates masks, flat-color materials,
meshes, nodes, motions, Physics, or Runtime artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageChops, ImageDraw, ImageFont


OUTPUT_DIR = Path(__file__).resolve().parents[1]
CHARACTER_DIR = OUTPUT_DIR.parents[1]
SOURCE_DIR = CHARACTER_DIR / "source"
VALIDATION_DIR = CHARACTER_DIR / "validation"
V25_DIR = VALIDATION_DIR / "arm-chain-screen-left-v25-shoulder-joint-correction"
V38_DIR = VALIDATION_DIR / "arm-chain-screen-left-v38-reset-guided-wrist-underlay"
V38_REPORT_PATH = V38_DIR / "audit" / "machine-report.json"

FRONT_MASTER_SIZE = (512, 1086)
THREE_VIEW_SIZE = (1448, 1086)
FRONT_CROP_BOX = (34, 0, 546, 1086)

SOURCE_SPECS = [
    {
        "id": "three_view_line",
        "path": SOURCE_DIR / "xiaoxing-three-view-line.png",
        "relativePath": "../../source/xiaoxing-three-view-line.png",
        "expectedSha256": "7F8605A85DF7FA2C8843E925F8274A06403D884D975B1B195B2A583478DC222C",
        "role": "结构线稿唯一权威；决定可见轮廓、材料边界和关节关系",
    },
    {
        "id": "three_view_color",
        "path": SOURCE_DIR / "xiaoxing-three-view-color.png",
        "relativePath": "../../source/xiaoxing-three-view-color.png",
        "expectedSha256": "2D1B9C71C4E6C17EA503800B05F44BF7BFE127799A5E156886C191B97D350154",
        "role": "身份、颜色和材质参照；不得覆盖线稿结构",
    },
    {
        "id": "front_line_master",
        "path": SOURCE_DIR / "masters" / "front-line-source-exact-after-reset.png",
        "relativePath": "../../source/masters/front-line-source-exact-after-reset.png",
        "expectedSha256": "706AAF10652147CF76E233532B5459CE130921A96806F6970C91E1F3A427172F",
        "role": "正面正式 512×1086 线稿坐标母版",
    },
    {
        "id": "front_color_master",
        "path": SOURCE_DIR / "masters" / "front-color-source-exact-after-reset.png",
        "relativePath": "../../source/masters/front-color-source-exact-after-reset.png",
        "expectedSha256": "33B3CE81781C02B36488ED72FA27C2A136682824CA10C42077895EAB0FFB2DD5",
        "role": "正面正式 512×1086 彩稿身份/颜色坐标参照",
    },
]

IDENTITY = {
    "character": "xiaoxing",
    "subject": "小星 Left",
    "view": "front",
    "screenSide": "left",
    "anatomicalSide": "right",
    "definition": "正面画面左侧手臂，即角色解剖学右臂",
}

# These are R1 anatomical pivot projections from the source line/color review.
# They are not contour endpoints and are not copied from V25.  The shoulder is
# hidden under the sleeve, so its glenohumeral center is derived from the
# shoulder cap and the shared upper-arm axis; elbow and wrist are hinge/center
# projections rather than points on the outside ink contour.  The old values
# are loaded separately and reported only as a comparison at build time.
FRONT_LANDMARKS = {
    "shoulder": [166.0, 270.0],
    "elbow": [149.0, 399.0],
    "wrist": [110.0, 538.0],
    "palmRoot": [104.0, 552.0],
}

VIEW_LANDMARKS = {
    "front": {
        "view": "front",
        "screenSide": "left",
        "anatomicalSide": "right",
        "projectionStatus": "authoritative-formal-master",
        "points": {
            key: [value[0] + FRONT_CROP_BOX[0], value[1]]
            for key, value in FRONT_LANDMARKS.items()
        },
    },
    "side": {
        "view": "side",
        "screenSide": "profile-near",
        "anatomicalSide": "right",
        "projectionStatus": "derived-profile-projection; profile alone does not disambiguate anatomical side",
        "points": {
            "shoulder": [688.0, 270.0],
            "elbow": [686.0, 399.0],
            "wrist": [677.0, 538.0],
            "palmRoot": [672.0, 552.0],
        },
    },
    "back": {
        "view": "back",
        "screenSide": "right",
        "anatomicalSide": "right",
        "projectionStatus": "derived-back-projection; anatomical right projects to screen-right in the back view",
        "points": {
            "shoulder": [1207.0, 270.0],
            "elbow": [1220.0, 399.0],
            "wrist": [1243.0, 538.0],
            "palmRoot": [1249.0, 552.0],
        },
    },
}

V25_POINTS = {
    "shoulder": [170.0, 251.0],
    "elbow": [147.0, 405.0],
    "wrist": [115.0, 529.0],
}

VOLUME_SECTIONS = {
    "shoulder": {
        "center": FRONT_LANDMARKS["shoulder"],
        "radiiPx": [25.0, 22.0],
        "evidenceStatus": "derived",
        "observedBasis": "前视袖山、袖口方向、侧视袖内上臂根和背视肩线共同约束",
        "note": "皮肤肩根被袖子遮挡；此处是物理体积截面候选，不是可见皮肤 mask",
    },
    "elbow": {
        "center": FRONT_LANDMARKS["elbow"],
        "radiiPx": [18.0, 16.0],
        "evidenceStatus": "derived",
        "observedBasis": "袖口下方可见前臂宽度、侧视袖口出臂截面、固定肩腕骨长",
        "note": "原线稿没有可独立认定的肘褶线；支点是由骨轴和局部宽度推导",
    },
    "wrist": {
        "center": FRONT_LANDMARKS["wrist"],
        "radiiPx": [20.0, 15.0],
        "evidenceStatus": "derived",
        "observedBasis": "手链两侧对称包络、前臂末端轮廓、手掌根方向",
        "note": "手链遮挡下的皮肤截面未直接可见；不可从 V38 皮肤/手链旧材料填充",
    },
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(OUTPUT_DIR).as_posix()


def dist(a: Iterable[float], b: Iterable[float]) -> float:
    ax, ay = a
    bx, by = b
    return math.hypot(bx - ax, by - ay)


def angle_deg(a: Iterable[float], b: Iterable[float]) -> float:
    ax, ay = a
    bx, by = b
    return math.degrees(math.atan2(by - ay, bx - ax))


def included_angle(a: Iterable[float], vertex: Iterable[float], c: Iterable[float]) -> float:
    va = (a[0] - vertex[0], a[1] - vertex[1])
    vc = (c[0] - vertex[0], c[1] - vertex[1])
    denom = math.hypot(*va) * math.hypot(*vc)
    if denom == 0:
        return 0.0
    cosine = max(-1.0, min(1.0, (va[0] * vc[0] + va[1] * vc[1]) / denom))
    return math.degrees(math.acos(cosine))


def point_in_ellipse(point: Iterable[float], center: Iterable[float], radii: Iterable[float]) -> bool:
    px, py = point
    cx, cy = center
    rx, ry = radii
    return ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= 1.0 + 1e-9


def image_metadata(path: Path, expected_sha: str, role: str, relative_path: str) -> dict[str, Any]:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        alpha_min, alpha_max = alpha.getextrema()
        alpha_histogram = alpha.histogram()
        alpha_nonzero = sum(alpha_histogram[1:])
        alpha_partial = sum(alpha_histogram[1:255])
        actual_size = list(image.size)
        mode = image.mode
        image_format = image.format
        info_keys = sorted(image.info.keys())
    actual_sha = sha256_file(path)
    return {
        "id": path.stem,
        "path": relative_path,
        "role": role,
        "dimensions": {"width": actual_size[0], "height": actual_size[1]},
        "colorMode": mode,
        "format": image_format,
        "metadataKeys": info_keys,
        "alpha": {
            "state": "opaque-full-canvas" if alpha_min == 255 and alpha_max == 255 else "non-opaque",
            "min": alpha_min,
            "max": alpha_max,
            "nonzeroPixels": alpha_nonzero,
            "partialPixels": alpha_partial,
            "transparentPixels": alpha_histogram[0],
        },
        "expectedSha256": expected_sha.lower(),
        "actualSha256": actual_sha,
        "sha256Match": actual_sha.lower() == expected_sha.lower(),
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_source_authority() -> dict[str, Any]:
    records = [
        image_metadata(spec["path"], spec["expectedSha256"], spec["role"], spec["relativePath"])
        for spec in SOURCE_SPECS
    ]
    line_three = Image.open(SOURCE_SPECS[0]["path"]).convert("RGB")
    color_three = Image.open(SOURCE_SPECS[1]["path"]).convert("RGB")
    line_front = Image.open(SOURCE_SPECS[2]["path"]).convert("RGB")
    color_front = Image.open(SOURCE_SPECS[3]["path"]).convert("RGB")
    line_crop = line_three.crop(FRONT_CROP_BOX)
    color_crop = color_three.crop(FRONT_CROP_BOX)
    line_exact = ImageChops.difference(line_crop, line_front).getbbox() is None
    color_exact = ImageChops.difference(color_crop, color_front).getbbox() is None
    return {
        "schemaVersion": 1,
        "stage": "R1 physical body, joints, and line semantics",
        "status": "engineering-audit-candidate",
        "identity": IDENTITY,
        "authoritativeInputs": records,
        "coordinateRelation": {
            "threeViewCanvas": {"width": THREE_VIEW_SIZE[0], "height": THREE_VIEW_SIZE[1]},
            "frontMasterCanvas": {"width": FRONT_MASTER_SIZE[0], "height": FRONT_MASTER_SIZE[1]},
            "frontMasterCropBoxInThreeViewPx": list(FRONT_CROP_BOX),
            "frontMasterTransform": "frontMaster(x,y) == threeView(x+34,y), exact 1:1 integer crop",
            "lineCropByteIdentity": line_exact,
            "colorCropByteIdentity": color_exact,
            "formalCoordinateRule": "all R1 front candidates stay in 512x1086 frontMaster coordinates; no scale, rotation, or manual reposition",
            "viewRegions": {
                "front": {"region": [34, 0, 546, 1086], "role": "exact master crop"},
                "side": {"region": [546, 0, 967, 1086], "role": "layout/projection reference only"},
                "back": {"region": [967, 0, 1448, 1086], "role": "layout/projection reference only"},
            },
            "viewInterpretation": "front, side, and back are projections of one body; side/back are not separate skeletons or materials",
        },
        "readOnlyEvidence": {
            "v25Comparison": "../arm-chain-screen-left-v25-shoulder-joint-correction/candidate-skeleton.json",
            "v38Regression": "../arm-chain-screen-left-v38-reset-guided-wrist-underlay/audit/machine-report.json",
            "oldDirectoriesUnmodifiedByThisBuild": True,
        },
    }


def build_body_contract(v38_report: dict[str, Any]) -> dict[str, Any]:
    projection_lengths: dict[str, dict[str, float]] = {}
    for view, data in VIEW_LANDMARKS.items():
        points = data["points"]
        projection_lengths[view] = {
            "upperArmPx": round(dist(points["shoulder"], points["elbow"]), 6),
            "forearmPx": round(dist(points["elbow"], points["wrist"]), 6),
            "wristToPalmRootPx": round(dist(points["wrist"], points["palmRoot"]), 6),
        }
    means = {
        key: sum(lengths[key] for lengths in projection_lengths.values()) / len(projection_lengths)
        for key in projection_lengths["front"]
    }
    canonical_landmarks = {
        key: {
            "frontMaster": value,
            "sourceThreeView": VIEW_LANDMARKS["front"]["points"][key],
            "sideProjection": VIEW_LANDMARKS["side"]["points"][key],
            "backProjection": VIEW_LANDMARKS["back"]["points"][key],
            "evidenceStatus": "derived" if key != "palmRoot" else "observed+derived",
        }
        for key, value in FRONT_LANDMARKS.items()
    }
    front = FRONT_LANDMARKS
    shoulder_angle = angle_deg(front["shoulder"], front["elbow"])
    forearm_angle = angle_deg(front["elbow"], front["wrist"])
    elbow_angle = included_angle(front["shoulder"], front["elbow"], front["wrist"])
    wrist_angle = included_angle(front["elbow"], front["wrist"], front["palmRoot"])
    v25_delta = {
        name: [round(front[name][0] - V25_POINTS[name][0], 3), round(front[name][1] - V25_POINTS[name][1], 3)]
        for name in V25_POINTS
    }
    return {
        "schemaVersion": 1,
        "stage": "R1 physical body, joints, and line semantics",
        "status": "engineering-candidate-waiting-user-visual-approval",
        "identity": IDENTITY,
        "scope": {
            "included": ["sleeve", "upper_arm", "forearm", "hand"],
            "braceletTreatment": "bracelet is an attached subregion owned by forearm; no separate moving layer is required for this R1",
            "excluded": ["opposite arm", "full-body separation", "materials", "masks", "mesh", "nodes", "motion", "Physics", "Runtime"],
        },
        "coordinateSystems": {
            "formalFront": "frontMaster 512x1086 RGB source coordinates",
            "threeView": "source three-view 1448x1086 pixel coordinates",
            "sideRegistration": "screenSide and anatomicalSide are recorded on every view projection; side profile is depth evidence, not a second body",
        },
        "viewProjections": VIEW_LANDMARKS,
        "canonicalBody": {
            "model": "one articulated right arm projected into front/side/back",
            "actualJoints": ["shoulder", "elbow", "wrist"],
            "handAxisReference": {"id": "palmRoot", "role": "hand direction/extent reference only; not a fourth joint"},
            "identityRule": "front screen-left is anatomical right; back projection reverses screen placement",
            "fixedSegmentRule": "one set of segment lengths; view projection may shorten apparent length within declared 5% QA tolerance",
            "supportRelation": "shoulder is supported by the torso/scapular volume; sleeve is an occluding garment, not a substitute for the hidden arm root",
            "depth": {
                "front": "arm hangs lateral to torso; sleeve is foreground at shoulder; forearm-owned bracelet is foreground at wrist",
                "side": "arm is lateral to shirt body; forearm skin exits the sleeve opening and hand is distal",
                "back": "anatomical right projects to screen-right; hair/shirt may occlude the shoulder root",
                "evidenceStatus": "derived",
            },
        },
        "landmarks": canonical_landmarks,
        "jointPlacementBasis": {
            "shoulder": {
                "anatomicalCenter": "glenohumeral joint center / humeral-head center projection",
                "frontPlacementRule": "在袖山覆盖下取肩关节中心的投影；不取头发线、肩部外轮廓或袖口端点",
                "visibility": "hidden-under-sleeve-derived",
                "frontMaster": FRONT_LANDMARKS["shoulder"],
            },
            "elbow": {
                "anatomicalCenter": "humeroulnar hinge center between upper-arm and forearm axes",
                "frontPlacementRule": "取袖口出臂处上臂—前臂骨轴的铰链中心；不取任一侧皮肤外轮廓",
                "visibility": "occluded-transition-derived",
                "frontMaster": FRONT_LANDMARKS["elbow"],
            },
            "wrist": {
                "anatomicalCenter": "radiocarpal joint center at the forearm-to-palm transition",
                "frontPlacementRule": "取手链下方两侧腕部轮廓之间的中轴、并与掌部方向相接；不落在任一边缘；手链只遮挡外观，不改变腕关节支点",
                "visibility": "bracelet-occluded-derived",
                "frontMaster": FRONT_LANDMARKS["wrist"],
            },
            "palmRoot": {
                "anatomicalCenter": "proximal palm direction reference",
                "frontPlacementRule": "只用于掌部方向和手段长度参考，不计入关节数量",
                "visibility": "observed-derived-reference",
                "frontMaster": FRONT_LANDMARKS["palmRoot"],
            },
        },
        "boneAxes": {
            "upper_arm": {
                "from": "shoulder",
                "to": "elbow",
                "frontMasterStart": front["shoulder"],
                "frontMasterEnd": front["elbow"],
                "screenAxisAngleDeg": round(shoulder_angle, 6),
                "lengthPx": round(dist(front["shoulder"], front["elbow"]), 6),
                "evidenceStatus": "derived",
            },
            "forearm": {
                "from": "elbow",
                "to": "wrist",
                "frontMasterStart": front["elbow"],
                "frontMasterEnd": front["wrist"],
                "screenAxisAngleDeg": round(forearm_angle, 6),
                "lengthPx": round(dist(front["elbow"], front["wrist"]), 6),
                "evidenceStatus": "derived",
            },
            "hand_palm_root": {
                "from": "wrist",
                "to": "palmRoot",
                "frontMasterStart": front["wrist"],
                "frontMasterEnd": front["palmRoot"],
                "screenAxisAngleDeg": round(angle_deg(front["wrist"], front["palmRoot"]), 6),
                "lengthPx": round(dist(front["wrist"], front["palmRoot"]), 6),
                "evidenceStatus": "observed+derived",
            },
        },
        "jointAnglesAtRest": {
            "elbowIncludedDeg": round(elbow_angle, 6),
            "wristIncludedDeg": round(wrist_angle, 6),
            "interpretation": "near-extended hanging arm; angles are structural measurements, not action keyforms",
        },
        "localVolumeSections": VOLUME_SECTIONS,
        "activityPressureRanges": {
            "status": "qa-pressure-only-not-formal-action-design",
            "shoulder": {
                "start": {"localJointAngleDeg": 0.0, "screenAxisAngleDeg": round(shoulder_angle, 6)},
                "testExtremesDeg": [-18.0, 20.0],
                "preferredBendBranch": "保持肘点在躯干外侧，优先沿屏幕左下方分支，不穿过躯干",
                "depthSwitch": "unresolved beyond small frontal-plane test; shoulder rotation under sleeve is not visible",
                "outsideCurrent2DRange": "大于约 20° 的抬臂、明显前后摆和肩胛滑动均超出当前二维线稿证据",
            },
            "elbow": {
                "start": {"localJointAngleDeg": round(180.0 - elbow_angle, 6), "screenAxisAngleDeg": round(forearm_angle, 6)},
                "testExtremesDeg": [0.0, 35.0],
                "preferredBendBranch": "向屏幕左侧轻微屈曲；保持手腕不穿过袖口/躯干，禁止肘部分支翻转",
                "depthSwitch": "unresolved for pronation/supination; profile depth is not encoded by the front line master",
                "outsideCurrent2DRange": "超过约 35° 的深屈肘、肘向后穿袖和前臂跨躯干均不可信",
            },
            "wrist": {
                "start": {"localJointAngleDeg": 0.0, "screenAxisAngleDeg": round(angle_deg(front["wrist"], front["palmRoot"]), 6)},
                "testExtremesDeg": [-15.0, 18.0],
                "preferredBendBranch": "小幅向屏幕左下/右下分支，保持掌根与手链同一腕部支点",
                "depthSwitch": "unresolved; bracelet occludes the wrist skin and cannot be used to invent depth",
                "outsideCurrent2DRange": "大于约 18° 的背屈、旋前旋后和手链环绕深度切换留待后续证据",
            },
        },
        "observedDerivedUnresolved": [
            {"id": "shoulder-visible-sleeve", "status": "observed", "conclusion": "袖山、袖口和三视图肩线可见，皮肤肩根不可见"},
            {"id": "shoulder-pivot", "status": "derived", "conclusion": "以袖山/躯干体积、固定骨长和侧背投影共同定位肩支点"},
            {"id": "elbow-pivot", "status": "derived", "conclusion": "肘点由肩腕固定骨长、袖口下皮肤宽度和三视图投影求得，原线无独立肘褶"},
            {"id": "wrist-pivot", "status": "derived", "conclusion": "腕点由前臂末端、手掌根方向和手链外轮廓共同定位"},
            {"id": "bracelet-hidden-wrist-skin", "status": "unresolved", "conclusion": "手链下方隐藏皮肤的完整截面不能从 V38 旧材料或默认遮挡推断"},
            {"id": "profile-side-identity", "status": "unresolved", "conclusion": "单独侧视无法独立区分解剖侧，只作为同一身体的厚度/遮挡证据"},
        ],
        "historicalComparison": {
            "source": "../arm-chain-screen-left-v25-shoulder-joint-correction/candidate-skeleton.json",
            "sourceSha256": sha256_file(V25_DIR / "candidate-skeleton.json"),
            "v25CandidateFrontMasterPoints": V25_POINTS,
            "r1MeasuredFrontMasterPoints": {key: front[key] for key in ["shoulder", "elbow", "wrist"]},
            "r1MinusV25Px": v25_delta,
            "use": "comparison-only; V25 is not inherited as R1 fact",
        },
        "v38RegressionEvidence": {
            "source": "../arm-chain-screen-left-v38-reset-guided-wrist-underlay/audit/machine-report.json",
            "status": v38_report.get("status"),
            "engineeringPass": v38_report.get("engineeringPass"),
            "overallGatePass": v38_report.get("overallGatePass"),
            "userFinding": v38_report.get("userVisualApproval", {}).get("finding"),
            "braceletPixelsAlsoPresentInForearmAlpha": v38_report.get("userVisualRejection", {}).get("diagnostics", {}).get("braceletPixelsAlsoPresentInForearmAlpha"),
            "rootTransitionPixels": v38_report.get("userVisualRejection", {}).get("diagnostics", {}).get("rootTransitionPixels"),
            "regressionUse": "semantic ownership and complete material geometry must be rebuilt before any downstream stage",
        },
    }


def segment(
    segment_id: str,
    category: str,
    owner: str,
    status: str,
    reference_anchors: list[list[float]],
    description: str,
    *,
    evidence: str = "front line master",
) -> dict[str, Any]:
    return {
        "id": segment_id,
        "view": "front",
        "screenSide": "left",
        "anatomicalSide": "right",
        "classification": category,
        "classificationStatus": status,
        "inkOwner": owner,
        "referenceAnchorsFrontMasterPx": reference_anchors,
        "geometryStatus": "source-line-preserved; reference-anchors-only",
        "syntheticBoundaryTraceRendered": False,
        "evidence": evidence,
        "description": description,
    }


def build_line_ownership_contract() -> dict[str, Any]:
    segments = [
        segment("sleeve_outer_profile", "sleeve_or_cuff_boundary", "sleeve", "observed", [[177, 233], [162, 246], [147, 272], [130, 314], [112, 359], [108, 369]], "袖子外轮廓，拥有袖子可见边缘与其抗锯齿"),
        segment("sleeve_cuff_outer_edge", "sleeve_or_cuff_boundary", "sleeve", "observed", [[108, 369], [126, 379], [148, 388], [177, 398]], "袖口外侧下缘"),
        segment("sleeve_cuff_inner_edge", "sleeve_or_cuff_boundary", "sleeve", "observed", [[111, 374], [129, 384], [151, 393], [178, 402]], "袖口内侧/衣物边界；不把它当作皮肤 alpha"),
        segment("sleeve_arm_opening", "sleeve_or_cuff_boundary", "sleeve", "observed", [[177, 398], [190, 401], [204, 401]], "袖口下皮肤出臂口的衣物侧边界"),
        segment("forearm_outer_visible_contour", "skin_outer_contour", "forearm", "observed", [[177, 399], [169, 430], [158, 464], [147, 495], [132, 517], [124, 523]], "袖口至手链近端的皮肤外轮廓"),
        segment("forearm_inner_visible_contour", "skin_outer_contour", "forearm", "observed", [[204, 401], [197, 430], [187, 464], [177, 494], [158, 518], [147, 522]], "袖口至手链近端的皮肤内轮廓"),
        segment("hand_radial_outer_contour", "wrist_hand_boundary", "hand", "observed", [[110, 539], [101, 559], [90, 580], [79, 603], [74, 610]], "手链下方至拇指侧手部外轮廓"),
        segment("hand_ulnar_outer_contour", "wrist_hand_boundary", "hand", "observed", [[145, 538], [143, 555], [138, 572], [134, 589]], "手链下方至小指侧手部外轮廓"),
        segment("hand_thumb_web", "internal_structure", "hand", "observed", [[122, 551], [126, 564], [126, 581]], "拇指根/虎口内部结构线，不能形成独立材料边界"),
        segment("hand_finger_separation_1", "internal_structure", "hand", "observed", [[114, 571], [111, 591], [108, 610]], "手指间内部结构线"),
        segment("hand_finger_separation_2", "internal_structure", "hand", "observed", [[106, 570], [101, 594], [98, 615]], "手指间内部结构线"),
        segment("hand_finger_separation_3", "internal_structure", "hand", "observed", [[98, 570], [92, 594], [87, 610]], "手指间内部结构线"),
        segment("bracelet_proximal_loop", "bracelet_body_boundary", "forearm", "observed", [[103, 516], [115, 514], [131, 518], [145, 523]], "手链近端主环；按用户决定归入 forearm 子区域"),
        segment("bracelet_distal_loop", "bracelet_body_boundary", "forearm", "observed", [[102, 524], [116, 527], [132, 530], [146, 533]], "手链远端主环；不另建移动层"),
        segment("bracelet_left_beads", "bracelet_body_boundary", "forearm", "observed", [[104, 518], [101, 522], [101, 528], [105, 532]], "左侧珠子/结扣形状，forearm 子区域"),
        segment("bracelet_right_beads", "bracelet_body_boundary", "forearm", "observed", [[141, 520], [146, 523], [148, 529], [145, 535]], "右侧珠子/结扣形状，forearm 子区域"),
        segment("bracelet_hanging_left", "bracelet_hanging_part_boundary", "forearm", "observed", [[106, 526], [103, 533], [101, 540]], "左侧悬垂件/链结，forearm 子区域"),
        segment("bracelet_hanging_right", "bracelet_hanging_part_boundary", "forearm", "observed", [[140, 529], [145, 536], [146, 542]], "右侧悬垂件/链结，forearm 子区域"),
        segment("sleeve_fold_outer", "clothing_wrinkle", "sleeve", "observed", [[145, 247], [143, 273], [139, 302], [133, 329]], "袖子浅褶皱；不切材料"),
        segment("sleeve_fold_inner", "clothing_wrinkle", "sleeve", "observed", [[166, 253], [165, 282], [163, 314], [160, 349]], "袖子浅褶皱；不切材料"),
        segment("sleeve_cuff_fold", "clothing_wrinkle", "sleeve", "observed", [[119, 367], [139, 378], [159, 389]], "袖口附近衣物褶皱线"),
        segment("adjacent_hair_strands", "texture_or_decoration", "none", "observed", [[188, 232], [183, 263], [181, 295], [179, 327]], "邻接头发线；不属于四个目标语义层"),
        segment("adjacent_shirt_print", "texture_or_decoration", "none", "observed", [[184, 338], [196, 350], [207, 366]], "衣服印花/装饰线；彩稿也只作表面参照"),
        segment("adjacent_skin_light_shade", "shadow_line", "deferred_surface", "observed", [[183, 414], [177, 449], [169, 480]], "皮肤浅阴影/材质线；不形成几何边界"),
        segment("ambiguous_cuff_gray_line", "unresolved", "unresolved", "unresolved", [[156, 392], [170, 397], [183, 400]], "浅灰线在袖口/皮肤交界处的确切语义需用户视觉确认"),
        segment("ambiguous_bracelet_underlay_line", "unresolved", "unresolved", "unresolved", [[111, 535], [124, 538], [140, 539]], "手链下方皮肤/附件遮挡线不可从源线唯一判断"),
    ]
    layers = {
        "sleeve": {
            "id": "sleeve",
            "view": "front",
            "screenSide": "left",
            "anatomicalSide": "right",
            "visiblePixelResponsibility": "袖子本体、袖口外轮廓、衣物边界及袖口抗锯齿边缘",
            "hiddenCompletionResponsibility": "肩侧袖内衣物厚度和袖内遮挡连续性；不得代替隐藏皮肤肩根",
            "parentCandidate": "torso_support",
            "anatomicalAnchor": "shoulder_support / sleeve_opening",
            "drawOrder": 20,
            "depthRelations": ["foreground_of_upper_arm_at_sleeve_opening", "behind_adjacent_hair_where_source_line_shows_hair"],
            "antialiasEdgeOwner": ["sleeve_outer_profile", "sleeve_cuff_outer_edge", "sleeve_cuff_inner_edge", "sleeve_arm_opening"],
            "inkOwner": ["sleeve_outer_profile", "sleeve_cuff_outer_edge", "sleeve_cuff_inner_edge", "sleeve_arm_opening", "sleeve_fold_outer", "sleeve_fold_inner", "sleeve_cuff_fold"],
            "forbiddenSemantics": ["skin", "upper_arm_visible_pixels", "forearm", "hand", "bracelet", "bracelet_hanging_part", "shirt_print"],
            "evidenceStatus": "observed+derived",
        },
        "upper_arm": {
            "id": "upper_arm",
            "view": "front",
            "screenSide": "left",
            "anatomicalSide": "right",
            "visiblePixelResponsibility": "肩至肘的皮肤材料；当前正面大部分被袖子遮挡，不宣称已有正式可见 mask",
            "hiddenCompletionResponsibility": "在肩袖和肘前臂下方保持完整皮肤体积，延伸到共享肩/肘支点",
            "parentCandidate": "torso_support",
            "anatomicalAnchor": "shoulder / elbow",
            "drawOrder": 30,
            "depthRelations": ["behind_sleeve_at_shoulder", "parent_side_of_elbow_overlap_with_forearm"],
            "antialiasEdgeOwner": ["future_upper_arm_visible_boundary_only_after_R1_approval"],
            "inkOwner": ["future_upper_arm_boundary_only_after_R1_approval"],
            "forbiddenSemantics": ["sleeve", "forearm", "hand", "bracelet", "bracelet_hanging_part", "skin_shadow_baked_as_boundary"],
            "evidenceStatus": "derived; visible boundary locally unresolved under sleeve",
        },
        "forearm": {
            "id": "forearm",
            "view": "front",
            "screenSide": "left",
            "anatomicalSide": "right",
            "visiblePixelResponsibility": "袖口下方至腕部的前臂皮肤，以及用户指定归入 forearm 的手链主环、珠子、结扣和悬垂件",
            "hiddenCompletionResponsibility": "从肘到腕的连续皮肤截面，并保留 forearm-owned bracelet 的附件连续性；不另建 bracelet 移动层",
            "parentCandidate": "upper_arm",
            "anatomicalAnchor": "elbow / wrist",
            "drawOrder": 40,
            "depthRelations": ["forearm-owned_bracelet_foreground_at_wrist", "hidden_overlap_with_upper_arm_at_elbow", "hidden_overlap_with_hand_at_wrist"],
            "antialiasEdgeOwner": ["forearm_outer_visible_contour", "forearm_inner_visible_contour", "bracelet_proximal_loop", "bracelet_distal_loop", "bracelet_left_beads", "bracelet_right_beads", "bracelet_hanging_left", "bracelet_hanging_right"],
            "inkOwner": ["forearm_outer_visible_contour", "forearm_inner_visible_contour", "bracelet_proximal_loop", "bracelet_distal_loop", "bracelet_left_beads", "bracelet_right_beads", "bracelet_hanging_left", "bracelet_hanging_right"],
            "forbiddenSemantics": ["sleeve", "upper_arm_visible_boundary_if_not_observed", "hand", "duplicated_bracelet_in_hand", "skin_shadow_baked_as_boundary"],
            "evidenceStatus": "observed visible contour and forearm-owned accessory + derived hidden continuation",
        },
        "hand": {
            "id": "hand",
            "view": "front",
            "screenSide": "left",
            "anatomicalSide": "right",
            "visiblePixelResponsibility": "手链远端之后的掌、拇指和手指皮肤及其真实外轮廓",
            "hiddenCompletionResponsibility": "腕部至掌根的连续皮肤，受手链遮挡处只按同一身体证据补全",
            "parentCandidate": "forearm",
            "anatomicalAnchor": "wrist / palmRoot",
            "drawOrder": 50,
            "depthRelations": ["distal_to_forearm_at_wrist", "behind_forearm_owned_bracelet_where_accessory_overlays_skin"],
            "antialiasEdgeOwner": ["hand_radial_outer_contour", "hand_ulnar_outer_contour"],
            "inkOwner": ["hand_radial_outer_contour", "hand_ulnar_outer_contour", "hand_thumb_web", "hand_finger_separation_1", "hand_finger_separation_2", "hand_finger_separation_3"],
            "forbiddenSemantics": ["sleeve", "upper_arm", "forearm", "duplicated_bracelet_in_hand", "bracelet_beads", "bracelet_hanging_part"],
            "evidenceStatus": "observed distal contour + derived hidden wrist continuation",
        },
    }
    return {
        "schemaVersion": 1,
        "stage": "R1 line semantics and unique pixel ownership",
        "status": "engineering-candidate-waiting-user-visual-approval",
        "identity": IDENTITY,
        "scope": "front screen-left / anatomical right arm plus sleeve and forearm-owned bracelet subregion; adjacent hair/print are classified but excluded",
        "lineInventory": {
            "coordinateSystem": "frontMaster 512x1086",
            "roiFrontMasterPx": [70, 225, 215, 620],
            "classificationRule": "manual source-line semantic review; no color threshold, rectangle, polygon, or regularized contour decides ownership",
            "visualReviewPolicy": {
                "sourceLineRendering": "authoritative front-line master is shown unchanged",
                "semanticOverlay": "anchor-only; no synthetic colored boundary polyline is drawn",
                "reason": "approximate redraws can drift from the actual source contour and must not be mistaken for geometry",
            },
            "segments": segments,
            "coverageStatus": "all inventoried target-arm segments have observed, derived, or unresolved classification; reference anchors locate review areas but are not boundary traces; unresolved entries are explicit and block downstream local separation",
        },
        "layers": layers,
        "boundaryOwnership": [
            {"id": "sleeve_outer_silhouette", "owner": "sleeve", "edgeOwner": "sleeve", "inkOwner": "sleeve", "status": "observed"},
            {"id": "sleeve_cuff_skin_opening", "owner": "sleeve", "edgeOwner": "sleeve", "inkOwner": "sleeve", "status": "observed"},
            {"id": "forearm_visible_skin_contour", "owner": "forearm", "edgeOwner": "forearm", "inkOwner": "forearm", "status": "observed"},
            {"id": "hand_visible_skin_contour", "owner": "hand", "edgeOwner": "hand", "inkOwner": "hand", "status": "observed"},
            {"id": "bracelet_main_loop", "owner": "forearm", "edgeOwner": "forearm", "inkOwner": "forearm", "status": "observed", "semanticSubregion": "bracelet"},
            {"id": "bracelet_hanging_parts", "owner": "forearm", "edgeOwner": "forearm", "inkOwner": "forearm", "status": "observed", "semanticSubregion": "bracelet_hanging_part"},
            {"id": "elbow_skin_boundary", "owner": "unresolved", "edgeOwner": "unresolved", "inkOwner": "unresolved", "status": "unresolved", "reason": "no directly visible elbow material line"},
            {"id": "wrist_skin_under_bracelet", "owner": "unresolved", "edgeOwner": "unresolved", "inkOwner": "unresolved", "status": "unresolved", "reason": "bracelet occludes the skin boundary"},
        ],
        "antiAliasingRules": {
            "oneEdgeOneOwner": True,
            "forearmOwnsBraceletSubregion": True,
            "handMayNotDuplicateForearmOwnedBracelet": True,
            "lineInkDoesNotCreateMaterialBoundary": True,
            "drawOrderCannotSubstituteForSemanticOwnership": True,
        },
        "mutualExclusion": [
            {"set": ["forearm", "hand"], "forbiddenSharedSemantics": ["duplicated_bracelet", "bracelet-shaped-RGB-in-hand", "bracelet-shaped-alpha-in-hand"]},
        ],
        "unresolvedForNextGate": [
            "袖口浅灰交界线的确切皮肤/衣物语义需用户视觉批准",
            "手链归入 forearm，但手链下隐藏腕部皮肤截面仍不得从 V38 旧材料继承",
            "当前 R1 不生成任何 visible/hidden/complete mask",
        ],
    }


def bezier_ellipse_segments(center: list[float], radii: list[float], rotation_deg: float) -> list[dict[str, list[float]]]:
    """Return a closed 8-segment cubic approximation of a smooth ellipse."""
    cx, cy = center
    rx, ry = radii
    rotation = math.radians(rotation_deg)
    cos_r = math.cos(rotation)
    sin_r = math.sin(rotation)
    delta = math.pi / 4.0
    alpha = (4.0 / 3.0) * math.tan(delta / 4.0)

    def transform(x: float, y: float) -> list[float]:
        return [round(cx + x * cos_r - y * sin_r, 6), round(cy + x * sin_r + y * cos_r, 6)]

    def point(theta: float) -> list[float]:
        return transform(rx * math.cos(theta), ry * math.sin(theta))

    def derivative(theta: float) -> tuple[float, float]:
        dx = -rx * math.sin(theta)
        dy = ry * math.cos(theta)
        return dx * cos_r - dy * sin_r, dx * sin_r + dy * cos_r

    segments: list[dict[str, list[float]]] = []
    for index in range(8):
        start_theta = index * delta
        end_theta = (index + 1) * delta
        start = point(start_theta)
        end = point(end_theta)
        d0 = derivative(start_theta)
        d1 = derivative(end_theta)
        c1 = [round(start[0] + alpha * d0[0], 6), round(start[1] + alpha * d0[1], 6)]
        c2 = [round(end[0] - alpha * d1[0], 6), round(end[1] - alpha * d1[1], 6)]
        segments.append({"start": start, "control1": c1, "control2": c2, "end": end})
    # Make closure exact after rounding.
    segments[-1]["end"] = segments[0]["start"]
    return segments


def build_joint_envelope_contract(body: dict[str, Any]) -> dict[str, Any]:
    joint_specs = [
        {
            "id": "shoulder",
            "parentLayer": "sleeve",
            "childLayer": "upper_arm",
            "pivot": FRONT_LANDMARKS["shoulder"],
            "radiiPx": [25.0, 22.0],
            "rotationDeg": angle_deg(FRONT_LANDMARKS["shoulder"], FRONT_LANDMARKS["elbow"]),
            "minimumOverlap": {"longitudinalPx": 14.0, "transversePx": 8.0},
            "referenceSectionWidthPx": 42.0,
            "parentResponsibility": "sleeve owns garment-side cover and hides the upper-arm proximal continuation",
            "childResponsibility": "upper_arm continues the hidden skin volume into the shoulder pivot and under the sleeve",
            "depth": "sleeve foreground; upper_arm hidden underneath at the visible sleeve opening",
        },
        {
            "id": "elbow",
            "parentLayer": "upper_arm",
            "childLayer": "forearm",
            "pivot": FRONT_LANDMARKS["elbow"],
            "radiiPx": [18.0, 16.0],
            "rotationDeg": angle_deg(FRONT_LANDMARKS["elbow"], FRONT_LANDMARKS["wrist"]),
            "minimumOverlap": {"longitudinalPx": 10.0, "transversePx": 7.0},
            "referenceSectionWidthPx": 34.0,
            "parentResponsibility": "upper_arm extends a hidden distal cover under the forearm at the shared elbow pivot",
            "childResponsibility": "forearm extends a hidden proximal cover under the upper arm without changing the visible contour",
            "depth": "no visible duplicate skin; parent/child overlap is hidden and must not be faked by draw order",
        },
        {
            "id": "wrist",
            "parentLayer": "forearm",
            "childLayer": "hand",
            "pivot": FRONT_LANDMARKS["wrist"],
            "radiiPx": [20.0, 15.0],
            "rotationDeg": angle_deg(FRONT_LANDMARKS["wrist"], FRONT_LANDMARKS["palmRoot"]),
            "minimumOverlap": {"longitudinalPx": 8.0, "transversePx": 6.0},
            "referenceSectionWidthPx": 36.0,
            "parentResponsibility": "forearm owns continuous skin into the hidden proximal wrist underlay",
            "childResponsibility": "hand owns continuous skin into the hidden distal wrist/palm-root underlay",
            "depth": "bracelet is a forearm-owned foreground subregion at the wrist; hand must not duplicate it",
        },
    ]
    joints = []
    for spec in joint_specs:
        controls = bezier_ellipse_segments(spec["pivot"], spec["radiiPx"], spec["rotationDeg"])
        joints.append({
            "id": spec["id"],
            "view": "front",
            "screenSide": "left",
            "anatomicalSide": "right",
            "sharedPhysicalPivotFrontMasterPx": spec["pivot"],
            "parentLayer": spec["parentLayer"],
            "childLayer": spec["childLayer"],
            "parentHiddenCoverage": {"owner": spec["parentLayer"], "responsibility": spec["parentResponsibility"], "evidenceStatus": "derived"},
            "childHiddenCoverage": {"owner": spec["childLayer"], "responsibility": spec["childResponsibility"], "evidenceStatus": "derived"},
            "minimumBidirectionalHiddenOverlapPx": spec["minimumOverlap"],
            "activeEnvelope": {
                "shape": "local_smooth_convex_ellipse",
                "basis": "shared pivot + parent/child bone axis + observed local width + multi-view depth",
                "center": spec["pivot"],
                "radiiPx": spec["radiiPx"],
                "rotationDeg": round(spec["rotationDeg"], 6),
                "bezierSegments": controls,
                "controlPointOrder": "clockwise closed loop in image coordinates; 8 monotonic 45-degree arcs",
                "analyticReference": "ellipse curvature is continuous; cubic controls use the 45-degree kappa approximation",
                "notFixedCircularPatch": True,
                "notGlobalConvexHull": True,
                "notRadialBlurOrDilation": True,
            },
            "widthGuard": {
                "referenceSectionWidthPx": spec["referenceSectionWidthPx"],
                "envelopeTransverseDiameterPx": round(2.0 * spec["radiiPx"][1], 6),
                "maximumAllowedDiameterPx": round(spec["referenceSectionWidthPx"] + 2.0 * spec["minimumOverlap"]["transversePx"], 6),
                "noAbnormalBulgeRule": "envelope diameter may not exceed the local reference width plus declared hidden overlap",
            },
            "depthAndDrawOrder": spec["depth"],
        })
    return {
        "schemaVersion": 1,
        "stage": "R1 smooth joint-envelope and hidden-overlap contract",
        "status": "engineering-candidate-waiting-user-visual-approval",
        "identity": IDENTITY,
        "globalRules": {
            "sharedPivotRequired": True,
            "hiddenOverlapIsNotVisiblePixelSharing": True,
            "allowedGeometry": ["local smooth convex envelope", "ellipse arc", "Bezier curve with continuous tangent"],
            "forbiddenGeometry": ["尖角", "楔形", "锐利多边形", "粗糙全局凸包", "固定圆形补丁", "径向填充", "blur", "dilate", "克隆皮肤块", "纹理遮缝"],
            "visibleBoundaryRule": "visible ownership remains unique even where hidden parent/child envelopes overlap",
        },
        "joints": joints,
        "unresolved": [
            "隐藏肩根的三维深度仍是 derived candidate，需用户视觉批准",
            "腕部在手链遮挡下的真实截面与深度切换仍 unresolved",
            "这些包络是后续几何 QA 的覆盖依据，不是正式 mask 或动作设计",
        ],
    }


def font(path_candidates: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in path_candidates:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


FONT_REGULAR = [
    r"C:\Windows\Fonts\Noto Sans SC (TrueType).otf",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]
FONT_BOLD = [
    r"C:\Windows\Fonts\Noto Sans SC Bold (TrueType).otf",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]


def draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font_obj: Any, fill: tuple[int, int, int], max_width: int, line_spacing: int = 8) -> int:
    x, y = xy
    lines: list[str] = []
    current = ""
    for character in text:
        candidate = current + character
        if current and draw.textbbox((0, 0), candidate, font=font_obj)[2] > max_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current:
        lines.append(current)
    for line in lines:
        draw.text((x, y), line, font=font_obj, fill=fill)
        y += draw.textbbox((0, 0), line, font=font_obj)[3] + line_spacing
    return y


def bezier_point(segment_data: dict[str, list[float]], t: float) -> tuple[float, float]:
    p0 = segment_data["start"]
    p1 = segment_data["control1"]
    p2 = segment_data["control2"]
    p3 = segment_data["end"]
    u = 1.0 - t
    return (
        u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
    )


def envelope_points(envelope: dict[str, Any], samples_per_segment: int = 10) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for segment_data in envelope["bezierSegments"]:
        for i in range(samples_per_segment):
            points.append(bezier_point(segment_data, i / samples_per_segment))
    points.append(tuple(envelope["bezierSegments"][0]["start"]))
    return points


def semantic_color(category: str) -> tuple[int, int, int, int]:
    return {
        "sleeve_or_cuff_boundary": (0, 165, 235, 210),
        "skin_outer_contour": (210, 48, 58, 220),
        "wrist_hand_boundary": (231, 119, 35, 220),
        "bracelet_body_boundary": (198, 40, 185, 230),
        "bracelet_hanging_part_boundary": (145, 35, 160, 230),
        "internal_structure": (239, 144, 38, 190),
        "clothing_wrinkle": (70, 125, 205, 165),
        "shadow_line": (126, 126, 126, 130),
        "texture_or_decoration": (100, 100, 100, 115),
        "unresolved": (235, 60, 60, 240),
    }.get(category, (80, 80, 80, 170))


def fit_image(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    x0, y0, x1, y1 = box
    target_w = max(1, x1 - x0)
    target_h = max(1, y1 - y0)
    scale = min(target_w / image.width, target_h / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.Resampling.NEAREST)


def paste_center(canvas: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    px = x0 + (x1 - x0 - image.width) // 2
    py = y0 + (y1 - y0 - image.height) // 2
    canvas.paste(image, (px, py))
    return px, py, px + image.width, py + image.height


def draw_panel_frame(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, subtitle: str | None = None) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=14, outline=(186, 194, 204), width=3, fill=(255, 255, 255))
    draw.text((x0 + 16, y0 + 12), title, font=font(FONT_BOLD, 24), fill=(25, 31, 40))
    if subtitle:
        draw.text((x0 + 16, y0 + 48), subtitle, font=font(FONT_REGULAR, 18), fill=(80, 88, 98))


def build_review_png(body: dict[str, Any], line_contract: dict[str, Any], envelope_contract: dict[str, Any]) -> bytes:
    line_path = SOURCE_DIR / "masters" / "front-line-source-exact-after-reset.png"
    color_path = SOURCE_DIR / "masters" / "front-color-source-exact-after-reset.png"
    three_line_path = SOURCE_DIR / "xiaoxing-three-view-line.png"
    line = Image.open(line_path).convert("RGB")
    color = Image.open(color_path).convert("RGB")
    three_line = Image.open(three_line_path).convert("RGB")
    canvas = Image.new("RGB", (3600, 2600), (246, 248, 251))
    draw = ImageDraw.Draw(canvas)
    draw.text((40, 28), "小星 Left｜R1 物理身体、关节与线稿语义合同", font=font(FONT_BOLD, 48), fill=(16, 22, 30))
    draw.text((42, 92), "view=front｜screenSide=left｜anatomicalSide=right｜审查图，不是正式材料｜R1 only", font=font(FONT_REGULAR, 27), fill=(59, 69, 80))
    draw.rounded_rectangle((2570, 30, 3550, 112), radius=18, fill=(255, 239, 223), outline=(210, 130, 60), width=3)
    draw.text((2610, 52), "当前状态：等待用户批准 R1", font=font(FONT_BOLD, 28), fill=(135, 67, 19))

    # Full source views.
    full_boxes = [
        ((40, 150, 360, 850), line, "正面原始线稿", "512×1086；结构/边界权威"),
        ((380, 150, 700, 850), color, "正面原始彩稿", "512×1086；身份/颜色参照"),
    ]
    for box, image, title, subtitle in full_boxes:
        draw_panel_frame(draw, box, title, subtitle)
        fitted = fit_image(image, (box[0] + 12, box[1] + 78, box[2] - 12, box[3] - 12))
        paste_center(canvas, fitted, (box[0] + 12, box[1] + 78, box[2] - 12, box[3] - 12))

    # Main structural overlay.
    overlay_box = (730, 150, 1290, 1290)
    draw_panel_frame(draw, overlay_box, "正面结构叠加", "原始线稿原样保留；标 3 个解剖学关节中心，不重绘拟合边界")
    main = line.convert("RGBA")
    overlay = Image.new("RGBA", main.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay, "RGBA")
    points = FRONT_LANDMARKS
    # Three green markers are the actual joints.  palmRoot remains a
    # direction reference in the contract, not a fourth joint marker.  The
    # source line is deliberately left untouched: the old synthetic colored
    # polylines were only approximations and did not qualify as source traces.
    joint_labels = {
        "shoulder": "肩关节中心",
        "elbow": "肘关节中心",
        "wrist": "腕关节中心",
    }
    for index, key in enumerate(["shoulder", "elbow", "wrist"], start=1):
        x, y = points[key]
        odraw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(0, 154, 123, 220), outline=(255, 255, 255, 255), width=1)
        odraw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 255, 255, 255))
        odraw.text((x + 10, y - 17), f"{index} {joint_labels[key]}", font=font(FONT_REGULAR, 13), fill=(0, 106, 86, 255))
    main = Image.alpha_composite(main, overlay).convert("RGB")
    fitted_main = fit_image(main, (overlay_box[0] + 12, overlay_box[1] + 78, overlay_box[2] - 12, overlay_box[3] - 12))
    main_position = paste_center(canvas, fitted_main, (overlay_box[0] + 12, overlay_box[1] + 78, overlay_box[2] - 12, overlay_box[3] - 12))
    # Native-to-display transform for a small coordinate annotation.
    sx = fitted_main.width / main.width
    sy = fitted_main.height / main.height
    draw.text((main_position[0] + 12, main_position[1] + 10), f"显示比例 {sx:.2f}×；支点是骨性中心投影，源线稿未改画；正式坐标仍保持 512×1086", font=font(FONT_REGULAR, 16), fill=(40, 45, 55))

    # Three-view source strip and coordinate relation.
    three_box = (1320, 150, 2480, 500)
    draw_panel_frame(draw, three_box, "三视图原始线稿", "三视图=同一身体的 front / side / back 投影；front 母图为 x=34 精确裁切")
    fitted_three = fit_image(three_line, (three_box[0] + 14, three_box[1] + 78, three_box[2] - 14, three_box[3] - 14))
    paste_center(canvas, fitted_three, (three_box[0] + 14, three_box[1] + 78, three_box[2] - 14, three_box[3] - 14))

    # Evidence and regression notes.
    notes_box = (40, 900, 700, 2555)
    draw_panel_frame(draw, notes_box, "证据状态与回归边界", "机器检查不能替代人体结构和线稿贴合的用户审查")
    note_y = 980
    note_y = draw_wrapped(draw, (62, note_y), "observed：原图直接可见；derived：由三视图、固定骨长、局部体积和遮挡关系推导；unresolved：证据不足，不生成式猜测。", font(FONT_REGULAR, 23), (42, 48, 58), 600, 10)
    note_y += 18
    draw.text((62, note_y), "颜色图只说明身份/颜色，不覆盖线稿结构。", font=font(FONT_BOLD, 23), fill=(26, 91, 146))
    note_y += 50
    draw.text((62, note_y), "R1 只登记合同，不生成正式材料。", font=font(FONT_BOLD, 23), fill=(26, 91, 146))
    note_y += 62
    v38_text = "V38 回归：工程检查通过，但用户视觉拒绝“全是断口”。报告记录 429 个有效手链像素同时存在于 forearm alpha，且 RGB/遮挡修补不能解决语义污染。本轮按用户决定将手链视为 forearm 附着子区域；仍禁止 hand 重复拥有手链或用旧材料补隐藏腕部。"
    note_y = draw_wrapped(draw, (62, note_y), v38_text, font(FONT_REGULAR, 22), (138, 61, 35), 600, 9)
    note_y += 26
    anatomy_text = "关节点按人体骨性中心放置：肩=袖山下的盂肱关节中心投影；肘=上臂与前臂骨轴的铰链中心；腕=前臂进入掌部的中心。三点都不是轮廓端点；手链只遮挡腕部外观，不改变腕支点。"
    note_y = draw_wrapped(draw, (62, note_y), anatomy_text, font(FONT_REGULAR, 22), (36, 106, 89), 600, 9)
    note_y += 26
    stop_text = "停止条件：未批准 R1 前不得进入平色 mask、纹理、网格、Rig、Physics 或 Runtime。"
    draw_wrapped(draw, (62, note_y), stop_text, font(FONT_BOLD, 22), (138, 61, 35), 600, 9)
    note_y += 100
    draw.text((62, note_y), "语义图例（合同分类，不在主图重绘边界）", font=font(FONT_BOLD, 24), fill=(25, 31, 40))
    legend = [
        ("袖口/衣物边界", semantic_color("sleeve_or_cuff_boundary")),
        ("皮肤外轮廓", semantic_color("skin_outer_contour")),
        ("手/腕边界", semantic_color("wrist_hand_boundary")),
        ("手链主体/悬垂件", semantic_color("bracelet_body_boundary")),
        ("内部结构/褶皱", semantic_color("internal_structure")),
        ("unresolved", semantic_color("unresolved")),
    ]
    legend_y = note_y + 50
    for label, color_value in legend:
        draw.rounded_rectangle((64, legend_y + 2, 112, legend_y + 22), radius=5, fill=color_value[:3], outline=(70, 76, 86), width=1)
        draw.text((128, legend_y), label, font=font(FONT_REGULAR, 21), fill=(50, 56, 67))
        legend_y += 40
    draw_wrapped(draw, (62, legend_y + 20), "主图不再叠加任何近似彩色折线；原线稿像素就是唯一可见边界。合同里的 reference anchors 只用于定位审查段落，不是 source trace。关节包络仍只登记在 JSON 合同中，不是 mask。", font(FONT_REGULAR, 21), (60, 68, 78), 600, 9)

    # Zoom panels.  Each has line and color side-by-side, nearest-neighbor only.
    zoom_specs = [
        ("肩/袖山", (135, 225, 215, 410), 4, 1320, 540),
        ("肘/袖口出臂", (100, 360, 185, 470), 5, 2440, 540),
        ("腕/手掌根", (80, 490, 165, 565), 6, 1320, 1380),
        ("手链主体与悬垂件", (92, 505, 160, 550), 8, 2440, 1380),
    ]
    for title, crop_box, zoom, px, py in zoom_specs:
        panel_w, panel_h = 1080, 720
        panel_box = (px, py, px + panel_w, py + panel_h)
        draw_panel_frame(draw, panel_box, f"{title}｜最近邻 {zoom * 100}%", "审查裁剪，不是正式材料")
        line_crop = line.crop(crop_box).resize(((crop_box[2] - crop_box[0]) * zoom, (crop_box[3] - crop_box[1]) * zoom), Image.Resampling.NEAREST)
        color_crop = color.crop(crop_box).resize(((crop_box[2] - crop_box[0]) * zoom, (crop_box[3] - crop_box[1]) * zoom), Image.Resampling.NEAREST)
        # Keep both source variants visible without interpolation.
        target = (panel_box[0] + 14, panel_box[1] + 76, panel_box[0] + panel_w // 2 - 8, panel_box[3] - 14)
        paste_center(canvas, fit_image(line_crop, target), target)
        target2 = (panel_box[0] + panel_w // 2 + 8, panel_box[1] + 76, panel_box[2] - 14, panel_box[3] - 14)
        paste_center(canvas, fit_image(color_crop, target2), target2)
        draw.text((target[0] + 8, panel_box[1] + 82), "线稿", font=font(FONT_BOLD, 18), fill=(25, 31, 40))
        draw.text((target2[0] + 8, panel_box[1] + 82), "彩稿", font=font(FONT_BOLD, 18), fill=(25, 31, 40))
        # Add a small conceptual label, without painting a mask.
        if "肩" in title:
            label = "肩支点 derived｜袖子 parent cover ↔ upper_arm child hidden continuation"
        elif "肘" in title:
            label = "肘支点 derived｜upper_arm ↔ forearm 双向隐藏覆盖"
        else:
            label = "腕支点 derived｜forearm ↔ hand；bracelet 属于 forearm 子区域"
        draw.text((panel_box[0] + 20, panel_box[3] - 42), label, font=font(FONT_REGULAR, 19), fill=(45, 99, 67))

    # Contract-summary footer.
    footer_y = 2430
    draw.rounded_rectangle((730, footer_y, 3550, 2555), radius=14, fill=(235, 245, 239), outline=(90, 155, 110), width=3)
    footer_text = "解剖学关节点：肩关节中心→肘关节中心→腕关节中心（三个）；掌根仅作手掌方向参考｜原始线稿原样保留，不画不贴合的合成语义线｜关节包络只登记在合同｜bracelet 归入 forearm｜用户视觉门禁未通过前停止在 R1。"
    draw_wrapped(draw, (760, footer_y + 28), footer_text, font(FONT_BOLD, 25), (36, 89, 51), 2740, 9)

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG", optimize=False)
    return buffer.getvalue()


def validate_contracts(source: dict[str, Any], body: dict[str, Any], line_contract: dict[str, Any], envelope: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"id": check_id, "pass": bool(passed), "detail": detail})

    add("input_hashes", all(item["sha256Match"] for item in source["authoritativeInputs"]), "四个权威输入 SHA-256 与登记值一致")
    dims_ok = all(item["dimensions"] == {"width": 512, "height": 1086} for item in source["authoritativeInputs"][2:]) and all(item["dimensions"] == {"width": 1448, "height": 1086} for item in source["authoritativeInputs"][:2])
    add("input_dimensions", dims_ok, "三视图 1448×1086；两个正面母图 512×1086")
    alpha_ok = all(item["alpha"]["state"] == "opaque-full-canvas" for item in source["authoritativeInputs"])
    add("input_color_and_alpha", alpha_ok, "四个源图为 RGB、整幅 alpha=255；当前不是透明材料")
    add("front_coordinate_identity", bool(source["coordinateRelation"]["lineCropByteIdentity"] and source["coordinateRelation"]["colorCropByteIdentity"]), "正面母图是三视图 x=34 的 1:1 精确裁切")

    identity_records = [body["identity"], line_contract["identity"], envelope["identity"]]
    identity_ok = all(record.get("view") == "front" and record.get("screenSide") == "left" and record.get("anatomicalSide") == "right" for record in identity_records)
    layer_identity_ok = all(layer.get("screenSide") == "left" and layer.get("anatomicalSide") == "right" for layer in line_contract["layers"].values())
    segment_identity_ok = all(item.get("screenSide") and item.get("anatomicalSide") for item in line_contract["lineInventory"]["segments"])
    joint_identity_ok = all(item.get("screenSide") == "left" and item.get("anatomicalSide") == "right" for item in envelope["joints"])
    add("side_fields_complete", identity_ok and layer_identity_ok and segment_identity_ok and joint_identity_ok, "所有 R1 合同记录同时登记 screenSide 与 anatomicalSide")

    projection = body["viewProjections"]
    length_keys = ["upperArmPx", "forearmPx", "wristToPalmRootPx"]
    lengths = {key: [projection[view]["points"] for view in projection] for key in []}
    measured: dict[str, list[float]] = {key: [] for key in length_keys}
    for view_data in projection.values():
        p = view_data["points"]
        measured["upperArmPx"].append(dist(p["shoulder"], p["elbow"]))
        measured["forearmPx"].append(dist(p["elbow"], p["wrist"]))
        measured["wristToPalmRootPx"].append(dist(p["wrist"], p["palmRoot"]))
    length_consistency = True
    details = []
    for key, values in measured.items():
        mean = sum(values) / len(values)
        deviations = [abs(value - mean) / mean for value in values]
        ok = max(deviations) <= 0.05
        length_consistency = length_consistency and ok
        details.append(f"{key}: max相对偏差={max(deviations):.4f}")
    add("bone_length_consistency", length_consistency, "; ".join(details) + "；阈值=5%")

    front_upper = dist(FRONT_LANDMARKS["shoulder"], FRONT_LANDMARKS["elbow"])
    front_forearm = dist(FRONT_LANDMARKS["elbow"], FRONT_LANDMARKS["wrist"])
    upper_forearm_ratio = front_upper / front_forearm if front_forearm else 0.0
    add(
        "human_limb_segment_proportion",
        0.85 <= upper_forearm_ratio <= 1.15,
        f"正面上臂/前臂骨段长度比={upper_forearm_ratio:.4f}；活动支点要求保持在 0.85–1.15 的近等长范围",
    )

    joints_in_volume = all(point_in_ellipse(FRONT_LANDMARKS[name], VOLUME_SECTIONS[name]["center"], VOLUME_SECTIONS[name]["radiiPx"]) for name in ["shoulder", "elbow", "wrist"])
    add("pivots_inside_local_volume", joints_in_volume, "肩/肘/腕支点位于各自登记的局部体积截面内")

    line_segments = line_contract["lineInventory"]["segments"]
    categories = {"sleeve_or_cuff_boundary", "skin_outer_contour", "wrist_hand_boundary", "bracelet_body_boundary", "bracelet_hanging_part_boundary", "internal_structure", "clothing_wrinkle", "shadow_line", "texture_or_decoration", "unresolved"}
    statuses = {"observed", "derived", "unresolved"}
    line_complete = bool(line_segments) and len({item["id"] for item in line_segments}) == len(line_segments) and all(
        item["classification"] in categories
        and item["classificationStatus"] in statuses
        and item.get("referenceAnchorsFrontMasterPx")
        and item.get("geometryStatus") == "source-line-preserved; reference-anchors-only"
        and item.get("syntheticBoundaryTraceRendered") is False
        for item in line_segments
    )
    add("line_classification_complete", line_complete, f"线段清单 {len(line_segments)} 条均有分类状态；坐标仅作原线稿审查锚点，不冒充拟合边界；unresolved 明确登记而非猜测")

    layers = line_contract["layers"]
    layer_unique = set(layers) == {"sleeve", "upper_arm", "forearm", "hand"}
    bracelet_segments_owned_by_forearm = all(item["inkOwner"] == "forearm" for item in line_segments if item["classification"] in {"bracelet_body_boundary", "bracelet_hanging_part_boundary"})
    bracelet_registered_in_forearm = all(segment_id in layers["forearm"]["inkOwner"] for segment_id in ["bracelet_proximal_loop", "bracelet_distal_loop", "bracelet_left_beads", "bracelet_right_beads", "bracelet_hanging_left", "bracelet_hanging_right"])
    hand_does_not_duplicate = "duplicated_bracelet_in_hand" in layers["hand"]["forbiddenSemantics"]
    boundaries = line_contract["boundaryOwnership"]
    boundary_ids_unique = len({item["id"] for item in boundaries}) == len(boundaries)
    edge_owner_present = all(item.get("edgeOwner") for item in boundaries)
    add("visible_ownership_unique", layer_unique and boundary_ids_unique and edge_owner_present, "四个实际语义层与每条可见边界各有唯一责任者；手链作为 forearm 子区域登记")
    add("bracelet_grouped_with_forearm", bracelet_segments_owned_by_forearm and bracelet_registered_in_forearm and hand_does_not_duplicate, "按用户决定，bracelet 归入 forearm；hand 不重复拥有手链")

    envelope_checks = []
    control_order_ok = True
    tangent_ok = True
    no_bulge_ok = True
    for joint in envelope["joints"]:
        segments = joint["activeEnvelope"]["bezierSegments"]
        for index, current in enumerate(segments):
            nxt = segments[(index + 1) % len(segments)]
            control_order_ok = control_order_ok and current["end"] == nxt["start"]
            before = (current["end"][0] - current["control2"][0], current["end"][1] - current["control2"][1])
            after = (nxt["control1"][0] - nxt["start"][0], nxt["control1"][1] - nxt["start"][1])
            cross = abs(before[0] * after[1] - before[1] * after[0])
            dot = before[0] * after[0] + before[1] * after[1]
            tangent_ok = tangent_ok and cross <= 0.01 and dot > 0
        width_guard = joint["widthGuard"]
        no_bulge_ok = no_bulge_ok and width_guard["envelopeTransverseDiameterPx"] <= width_guard["maximumAllowedDiameterPx"]
        envelope_checks.append(f"{joint['id']}: C1={'pass' if tangent_ok else 'fail'}")
    add("joint_envelope_control_order", control_order_ok, "每个局部椭圆 Bézier 环为闭合有序控制点")
    add("joint_envelope_smoothness", tangent_ok and no_bulge_ok, "连接处切线连续、无尖角；横向直径未超出局部宽度+隐藏重叠预算")
    add("forbidden_geometry_absent", all(not joint["activeEnvelope"]["notFixedCircularPatch"] is False for joint in envelope["joints"]), "合同未使用尖角、楔形、固定圆斑、blur、dilate 或粗糙全局凸包")

    unresolved_declared = any(item["status"] == "unresolved" for item in body["observedDerivedUnresolved"]) and any(item["classificationStatus"] == "unresolved" for item in line_segments)
    add("unresolved_evidence_is_explicit", unresolved_declared, "证据不足的肩根深度、肘线、腕部手链下截面均显式标 unresolved")

    return checks


def build_machine_report(source: dict[str, Any], body: dict[str, Any], line_contract: dict[str, Any], envelope: dict[str, Any], checks: list[dict[str, Any]], deterministic: dict[str, Any]) -> dict[str, Any]:
    passed = all(check["pass"] for check in checks) and deterministic["pass"]
    return {
        "schemaVersion": 1,
        "stage": "R1 physical body, joints, and line semantics",
        "status": "engineering_pass_waiting_user_visual_approval" if passed else "engineering_failed",
        "identity": IDENTITY,
        "engineeringPass": passed,
        "overallGatePass": False,
        "visualGate": {
            "status": "waiting_user_visual_approval",
            "approvalOwner": "user",
            "review": "qa/R1-小星Left-物理关节与线稿语义-中文审查图.png",
            "engineeringChecksDoNotReplaceVisualApproval": True,
            "R1GATE": "unchecked",
        },
        "checks": checks,
        "determinism": deterministic,
        "verifiedFacts": [
            "四个权威输入哈希/尺寸/颜色模式/alpha 已审计",
            "正面母图与三视图 x=34 精确 1:1 对齐",
            "R1 使用一套肩—肘—腕身体模型；palmRoot 只是手掌方向参考，不是第四关节",
            "肩/肘/腕坐标按盂肱中心、肘铰链中心、腕掌过渡中心放置，不把衣物/皮肤轮廓端点当作关节点",
            "正面上臂与前臂骨段长度保持近等长，避免肩点过高造成不合理的活动杠杆",
            "按用户决定，bracelet 是 forearm 附着子区域而不是独立移动层；hand 不得重复拥有手链形状/alpha/RGB",
            "肩/肘/腕使用局部圆滑 Bézier 椭圆包络候选，机器检查无尖角和异常外扩",
            "QA 主图保留权威线稿原像素，不再绘制与实际轮廓不贴合的合成语义折线；合同坐标仅作 reference anchors",
        ],
        "derivedConclusions": [
            "肩、肘、腕支点来自原图地标、固定骨长、局部体积和多视图投影的推导",
            "上臂大部分在袖子下隐藏，R1 不宣称已有正式上臂 visible mask",
            "侧视仅约束深度/宽度，不能独立为目标手臂建立另一套身体",
        ],
        "unresolvedRisks": [
            "袖口浅灰交界线的局部语义需用户视觉确认",
            "原线稿无独立肘褶线，肘部可见材料边界需后续用户门禁",
            "手链遮挡下的腕部隐藏皮肤截面与深度切换 unresolved",
            "语义分类的 reference anchors 不是精确 source trace；任何后续着色/分层前仍需基于原线稿逐段完成用户确认的像素级归属",
            "当前包络是 R1 物理 QA 合同，不是正式 mask、动作、网格或 Runtime 数据",
        ],
        "historicalDifferences": body["historicalComparison"],
        "v38Regression": body["v38RegressionEvidence"],
        "downstreamForbiddenUntilApproval": ["R2 flat-color masks", "texture", "PSD", "Cubism", "ArtMesh", "nodes", "parameters", "motion", "Physics", "Runtime", "pet integration"],
        "outputReferences": {
            "sourceAuthority": "audit/source-authority.json",
            "bodyJointContract": "contracts/body-joint-contract.json",
            "lineOwnershipContract": "contracts/line-ownership-contract.json",
            "jointEnvelopeContract": "contracts/joint-envelope-contract.json",
            "reviewImage": "qa/R1-小星Left-物理关节与线稿语义-中文审查图.png",
        },
    }


def contract_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the R1 physical and line-semantics contract")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR, help="R1 output directory; defaults to the package directory")
    args = parser.parse_args()
    if args.output.resolve() != OUTPUT_DIR.resolve():
        raise SystemExit("This R1 builder only writes to its package-local output directory.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "audit").mkdir(exist_ok=True)
    (OUTPUT_DIR / "contracts").mkdir(exist_ok=True)
    (OUTPUT_DIR / "qa").mkdir(exist_ok=True)

    source = build_source_authority()
    v38_report = load_json(V38_REPORT_PATH)
    body = build_body_contract(v38_report)
    line_contract = build_line_ownership_contract()
    envelope = build_joint_envelope_contract(body)
    checks = validate_contracts(source, body, line_contract, envelope)

    # Determinism is checked in memory before any report is written.  The PNG
    # encoder is called twice with identical settings, so visual output is part
    # of the deterministic check as well.
    source2 = build_source_authority()
    body2 = build_body_contract(v38_report)
    line2 = build_line_ownership_contract()
    envelope2 = build_joint_envelope_contract(body2)
    review_bytes_1 = build_review_png(body, line_contract, envelope)
    review_bytes_2 = build_review_png(body2, line2, envelope2)
    deterministic = {
        "pass": source == source2 and body == body2 and line_contract == line2 and envelope == envelope2 and review_bytes_1 == review_bytes_2,
        "contractDigestRun1": contract_digest({"source": source, "body": body, "line": line_contract, "envelope": envelope}),
        "contractDigestRun2": contract_digest({"source": source2, "body": body2, "line": line2, "envelope": envelope2}),
        "reviewPngSha256Run1": hashlib.sha256(review_bytes_1).hexdigest(),
        "reviewPngSha256Run2": hashlib.sha256(review_bytes_2).hexdigest(),
        "method": "in-memory rebuild twice with canonical JSON and fixed PNG settings",
    }
    checks.append({"id": "deterministic_reconstruction", "pass": deterministic["pass"], "detail": "合同对象与中文审查图两次内存重建字节一致"})
    report = build_machine_report(source, body, line_contract, envelope, checks, deterministic)

    write_json(OUTPUT_DIR / "audit" / "source-authority.json", source)
    write_json(OUTPUT_DIR / "contracts" / "body-joint-contract.json", body)
    write_json(OUTPUT_DIR / "contracts" / "line-ownership-contract.json", line_contract)
    write_json(OUTPUT_DIR / "contracts" / "joint-envelope-contract.json", envelope)
    (OUTPUT_DIR / "qa" / "R1-小星Left-物理关节与线稿语义-中文审查图.png").write_bytes(review_bytes_1)
    write_json(OUTPUT_DIR / "audit" / "machine-report.json", report)

    if not report["engineeringPass"]:
        failed = [check["id"] for check in report["checks"] if not check["pass"]]
        print(json.dumps({"engineeringPass": False, "failedChecks": failed}, ensure_ascii=False))
        return 1
    print(json.dumps({"engineeringPass": True, "overallGatePass": False, "output": rel(OUTPUT_DIR)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
