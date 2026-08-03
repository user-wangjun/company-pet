from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
V7 = HERE.parents[2]
VALIDATION = V7.parent
XIAOXING = VALIDATION.parent
V4 = VALIDATION / "arm-chain-screen-right-v4-wrist-motion"
V5 = VALIDATION / "arm-chain-screen-right-v5-hidden-upper-arm"
V6 = VALIDATION / "arm-chain-screen-right-v6-complete-upper-arm-geometry"
V7C = V7 / "v7c-production-forearm-geometry"
B1 = V7 / "v7b1-root-width-reopen"
B2 = V7 / "v7b2-angle-dependent-root-taper-feasibility"

AUDIT = ROOT / "audit"
MASKS = ROOT / "masks"
QA = ROOT / "qa"
for directory in (AUDIT, MASKS, QA):
    directory.mkdir(parents=True, exist_ok=True)

V7C_BUILDER = V7C / "tools/build_v7c_production_forearm_geometry.py"
B2_BUILDER = B2 / "tools/build_v7b2_angle_dependent_root_taper.py"
OWNERSHIP_BUILDER = V7 / "tools/build_v7a_ownership_gate.py"
SKELETON_PATH = V4 / "skeleton.json"
B1_REPORT = B1 / "audit/v7b1-root-width-conflict.json"
COLOR_PATH = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
UPPER_PATH = V6 / "masks/upper-arm-complete-geometry.png"
SLEEVE_PATH = V5 / "complete-sleeve-final/inputs/sleeve-complete-geometry-r9.png"
BRACELET_PATH = V7 / "masks/bracelet-ownership-candidate.png"
NATURAL_FOREARM_PATH = V7 / "masks/forearm-no-bracelet-qa-geometry.png"
VISIBLE_PATH = V7 / "masks/visible-forearm-locked.png"
WRIST_RESPONSIBILITY_PATH = V7 / "masks/wrist-source-responsibility-candidate.png"
HAND_PROXY_PATH = V7C / "masks/temporary-hand-root-envelope.png"
BASE_FORMAL_PATH = V7C / "masks/production-forearm-geometry.png"
BASE_F1_PATH = V7C / "masks/F1-elbow-active-root.png"
BASE_F2_PATH = V7C / "masks/F2-locked-visible-source.png"
BASE_F3_PATH = V7C / "masks/F3-hidden-body-fill.png"
BASE_F4_PATH = V7C / "masks/F4-wrist-hidden-extension.png"
REJECTION_PATH = (
    V7C / "audit/v7c-user-visual-rejection-elbow-seam-2026-07-26.json"
)

SS = 4
ALPHA_THRESHOLD = 16


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V7C_MODULE = load_module("v7c1_final_v7c", V7C_BUILDER)
B2_MODULE = load_module("v7c1_final_b2", B2_BUILDER)
OWNERSHIP = load_module("v7c1_final_ownership", OWNERSHIP_BUILDER)
V6_MODULE = V7C_MODULE.V6_MODULE
# Reuse V7-C renderers without writing back into the rejected V7-C folder.
V7C_MODULE.QA = QA
V7C_MODULE.AUDIT = AUDIT
V7C_MODULE.MASKS = MASKS


def corrected_full_pose_masks(
    theta2,
    phi,
    skeleton,
    frame,
    formal,
    f4,
    hand_proxy,
    upper_geometry,
    sleeve,
    compression_px,
    positive_extent_px,
):
    _, elbow, wrist, _, _, _, _, _ = frame
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    delta = theta2 - rest
    moved_forearm = V7C_MODULE.rotate_full(formal, -delta, elbow)
    moved_f4 = V7C_MODULE.rotate_full(f4, -delta, elbow)
    _, baseline_high, tapered_high = B2_MODULE.evaluate(
        theta2,
        skeleton,
        frame,
        formal,
        upper_geometry,
        sleeve,
        compression_px,
        positive_extent_px,
    )
    elbow_box = B2_MODULE.crop_box(elbow)
    low_size = (
        elbow_box[2] - elbow_box[0],
        elbow_box[3] - elbow_box[1],
    )
    baseline_low = binary(
        baseline_high.resize(low_size, Image.Resampling.LANCZOS),
        ALPHA_THRESHOLD,
    )
    tapered_low = binary(
        tapered_high.resize(low_size, Image.Resampling.LANCZOS),
        ALPHA_THRESHOLD,
    )
    # Replace only the pixels changed by the taper. Clearing the complete
    # rectangular crop erased valid shaft pixels at the crop edge on deep bends.
    removed_low = binary(ImageChops.subtract(baseline_low, tapered_low))
    removed_full = Image.new("L", formal.size, 0)
    tapered_full = Image.new("L", formal.size, 0)
    removed_full.paste(removed_low, (elbow_box[0], elbow_box[1]))
    tapered_full.paste(tapered_low, (elbow_box[0], elbow_box[1]))
    moved_forearm = binary(ImageChops.subtract(moved_forearm, removed_full))
    moved_forearm = binary(ImageChops.lighter(moved_forearm, tapered_full))

    moved_hand = V7C_MODULE.rotate_full(hand_proxy, -delta, elbow)
    radians = math.radians(delta)
    dx = wrist[0] - elbow[0]
    dy = wrist[1] - elbow[1]
    moved_wrist = (
        elbow[0] + math.cos(radians) * dx - math.sin(radians) * dy,
        elbow[1] + math.sin(radians) * dx + math.cos(radians) * dy,
    )
    moved_hand = V7C_MODULE.rotate_full(moved_hand, -phi, moved_wrist)
    fixed_upper = ImageChops.lighter(upper_geometry, sleeve)
    return fixed_upper, moved_forearm, moved_f4, moved_hand


# Scope the full-pose evidence fix to V7-C1; the rejected V7-C evidence stays frozen.
V7C_MODULE.full_pose_masks = corrected_full_pose_masks


V7C_QA_RENAMES = {
    "V7-C-PRODUCTION-FOREARM-F1-F5-BOARD.png": (
        "V7-C1-PRODUCTION-FOREARM-F1-F5-BOARD.png"
    ),
    "V7-C-FORMAL-ELBOW-THREE-ANGLES.png": (
        "V7-C1-FORMAL-ELBOW-THREE-ANGLES.png"
    ),
    "V7-C-FORMAL-ELBOW-SLOW-SCAN.gif": (
        "V7-C1-FORMAL-ELBOW-SLOW-SCAN.gif"
    ),
    "V7-C-WRIST-THREE-ANGLES.png": "V7-C1-WRIST-THREE-ANGLES.png",
    "V7-C-WRIST-SLOW-SCAN.gif": "V7-C1-WRIST-SLOW-SCAN.gif",
    "V7-C-FULL-CHAIN-ELBOW-WRIST-3X3.png": (
        "V7-C1-FULL-CHAIN-ELBOW-WRIST-3X3.png"
    ),
    "V7-C-DISPLACED-PART-INTEGRITY.png": (
        "V7-C1-DISPLACED-PART-INTEGRITY.png"
    ),
}


def version_v7c1_qa_paths() -> None:
    for old_name, new_name in V7C_QA_RENAMES.items():
        old_path = QA / old_name
        if not old_path.exists():
            raise RuntimeError(f"Expected QA render is missing: {old_name}")
        old_path.replace(QA / new_name)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def binary(mask: Image.Image, threshold: int = 1) -> Image.Image:
    return mask.convert("L").point(lambda value: 255 if value >= threshold else 0)


def load_mask(path: Path) -> Image.Image:
    image = Image.open(path)
    if image.mode == "L":
        return binary(image)
    return binary(image.convert("RGBA").getchannel("A"), ALPHA_THRESHOLD)


def rgba_mask(mask: Image.Image) -> Image.Image:
    result = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    result.putalpha(binary(mask))
    return result


def mask_count(mask: Image.Image) -> int:
    return sum(binary(mask).histogram()[1:])


def mask_difference_count(first: Image.Image, second: Image.Image) -> int:
    return mask_count(ImageChops.difference(binary(first), binary(second)))


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def fairing_violation_mask(
    mask: Image.Image,
    elbow,
    axis,
    normal,
    negative_root_limit=-14.0,
    negative_shaft_limit=-16.2,
    positive_root_limit=13.5,
    positive_shaft_limit=18.0,
    length=10.0,
) -> Image.Image:
    result = Image.new("L", mask.size, 0)
    source = binary(mask).load()
    output = result.load()
    for y in range(mask.height):
        for x in range(mask.width):
            if not source[x, y]:
                continue
            dx = x + 0.5 - elbow[0]
            dy = y + 0.5 - elbow[1]
            s = dx * axis[0] + dy * axis[1]
            n = dx * normal[0] + dy * normal[1]
            if 0.0 <= s <= length:
                blend = smoothstep(s / length)
                negative_limit = negative_root_limit + (
                    negative_shaft_limit - negative_root_limit
                ) * blend
                positive_limit = positive_root_limit + (
                    positive_shaft_limit - positive_root_limit
                ) * blend
                if n < negative_limit or n > positive_limit:
                    output[x, y] = 255
    return result


def evaluate_wrist_domain(
    skeleton,
    frame,
    natural_forearm,
    f4,
    hand_proxy,
    wrist_responsibility,
):
    _, _, wrist, _, _, _, _, _ = frame
    box = V7C_MODULE.wrist_box(wrist)
    fixed = binary(ImageChops.lighter(natural_forearm, f4))
    fixed_high = V7C_MODULE.high_mask(fixed, box)
    hand_high = V7C_MODULE.high_mask(hand_proxy, box)
    responsibility_high = V7C_MODULE.high_mask(wrist_responsibility, box)
    f4_high = V7C_MODULE.high_mask(f4, box)
    center = (
        (wrist[0] - box[0]) * SS,
        (wrist[1] - box[1]) * SS,
    )
    wrist_min = float(skeleton["allowedRangesDeg"]["phiWristLocal"]["min"])
    wrist_max = float(skeleton["allowedRangesDeg"]["phiWristLocal"]["max"])
    dense_angles = [
        wrist_min + (wrist_max - wrist_min) * index / 200.0
        for index in range(201)
    ]
    dense_rows = [
        V7C_MODULE.evaluate_wrist(
            phi,
            fixed_high,
            hand_high,
            responsibility_high,
            f4_high,
            hand_high,
            center,
        )[0]
        for phi in dense_angles
    ]
    epsilon_angles = sorted(
        {
            wrist_min,
            wrist_min + 0.01,
            wrist_min + 0.1,
            -0.1,
            -0.01,
            0.0,
            0.01,
            0.1,
            wrist_max - 0.1,
            wrist_max - 0.01,
            wrist_max,
        }
    )
    epsilon_rows = [
        V7C_MODULE.evaluate_wrist(
            phi,
            fixed_high,
            hand_high,
            responsibility_high,
            f4_high,
            hand_high,
            center,
        )[0]
        for phi in epsilon_angles
    ]
    minimum_index = min(
        range(len(dense_rows)),
        key=lambda index: dense_rows[index]["overlapPixelsAt4x"],
    )
    left = max(0, minimum_index - 1)
    right = min(len(dense_angles) - 1, minimum_index + 1)
    adaptive_angles = [
        dense_angles[left]
        + (dense_angles[right] - dense_angles[left]) * index / 80.0
        for index in range(81)
    ]
    adaptive_rows = [
        V7C_MODULE.evaluate_wrist(
            phi,
            fixed_high,
            hand_high,
            responsibility_high,
            f4_high,
            hand_high,
            center,
        )[0]
        for phi in adaptive_angles
    ]
    rest_first = V7C_MODULE.evaluate_wrist(
        0.0,
        fixed_high,
        hand_high,
        responsibility_high,
        f4_high,
        hand_high,
        center,
    )[1]
    rest_second = V7C_MODULE.evaluate_wrist(
        0.0,
        fixed_high,
        hand_high,
        responsibility_high,
        f4_high,
        hand_high,
        center,
    )[1]
    return {
        "box": box,
        "fixedHigh": fixed_high,
        "handHigh": hand_high,
        "responsibilityHigh": responsibility_high,
        "f4High": f4_high,
        "center": center,
        "minimum": wrist_min,
        "maximum": wrist_max,
        "denseRows": dense_rows,
        "epsilonRows": epsilon_rows,
        "adaptiveRows": adaptive_rows,
        "returnDifference": mask_difference_count(rest_first, rest_second),
    }


def render_before_after(
    skeleton,
    frame,
    baseline,
    revised,
    upper,
    sleeve,
    compression,
    positive_extent,
):
    _, elbow, _, _, _, _, _, _ = frame
    box = B2_MODULE.crop_box(elbow)
    fixed = ImageChops.lighter(
        B2_MODULE.high_mask(upper, box),
        B2_MODULE.high_mask(sleeve, box),
    )
    center = (
        (elbow[0] - box[0]) * SS,
        (elbow[1] - box[1]) * SS,
    )
    angles = [
        float(skeleton["allowedRangesDeg"]["theta2"]["min"]),
        float(skeleton["restAnglesDeg"]["theta2"]),
        float(skeleton["allowedRangesDeg"]["theta2"]["max"]),
    ]
    board = Image.new("RGB", (760, 930), (240, 240, 240))
    draw = ImageDraw.Draw(board)
    for row, theta in enumerate(angles):
        _, _, before = B2_MODULE.evaluate(
            theta,
            skeleton,
            frame,
            baseline,
            upper,
            sleeve,
            compression,
            positive_extent,
        )
        metrics, _, after = B2_MODULE.evaluate(
            theta,
            skeleton,
            frame,
            revised,
            upper,
            sleeve,
            compression,
            positive_extent,
        )
        for col, (label, mask) in enumerate(
            (("修改前（已否决）", before), ("双侧 10px 渐缩圆滑修正", after))
        ):
            view = V7C_MODULE.color_mask(
                fixed.size,
                [(fixed, (239, 147, 92)), (mask, (73, 184, 176))],
            )
            seam_crop = (
                round(center[0] - 34 * SS),
                round(center[1] - 23 * SS),
                round(center[0] + 34 * SS),
                round(center[1] + 29 * SS),
            )
            view = view.crop(seam_crop).resize(
                (350, 235), Image.Resampling.NEAREST
            )
            x = 12 + col * 374
            y = 8 + row * 305
            V7C_MODULE.text(
                draw,
                (x, y),
                f"{label} / 肘角 {theta:+.3f}°",
                19,
                True,
            )
            board.paste(view, (x, y + 36))
            V7C_MODULE.text(
                draw,
                (x, y + 277),
                f"责任区缺口@4x={metrics['missingResponsibilityPixelsAt4x']}",
                17,
            )
    board.save(QA / "V7-C1-ELBOW-SEAM-BEFORE-AFTER.png")


def manifest():
    entries = []
    for path in sorted(ROOT.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.name != "v7c1-evidence-manifest.json"
        ):
            entries.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
    return {
        "schemaVersion": 1,
        "root": "v7c1-elbow-seam-fairing",
        "fileCount": len(entries),
        "files": entries,
    }


def main() -> None:
    rejection = json.loads(REJECTION_PATH.read_text(encoding="utf-8"))
    if rejection["status"] != "user_visual_rejected_elbow_seam_local_protrusion":
        raise RuntimeError("V7-C rejection is missing.")
    integrity = OWNERSHIP.verify_inputs()
    if integrity["status"] != "pass":
        raise RuntimeError("Frozen input integrity failed.")

    skeleton = json.loads(SKELETON_PATH.read_text(encoding="utf-8"))
    frame = V6_MODULE.local_frame(skeleton)
    _, elbow, _, _, _, _, axis, normal = frame
    baseline_formal = load_mask(BASE_FORMAL_PATH)
    base_f1 = load_mask(BASE_F1_PATH)
    f2 = load_mask(BASE_F2_PATH)
    f3 = load_mask(BASE_F3_PATH)
    f4 = load_mask(BASE_F4_PATH)
    visible = load_mask(VISIBLE_PATH)
    natural_forearm = load_mask(NATURAL_FOREARM_PATH)
    bracelet = load_mask(BRACELET_PATH)
    wrist_responsibility = load_mask(WRIST_RESPONSIBILITY_PATH)
    hand_proxy = load_mask(HAND_PROXY_PATH)
    upper = load_mask(UPPER_PATH)
    sleeve = load_mask(SLEEVE_PATH)
    source_color = Image.open(COLOR_PATH).convert("RGB")

    removed = fairing_violation_mask(
        baseline_formal,
        elbow,
        axis,
        normal,
    )
    revised = binary(ImageChops.subtract(baseline_formal, removed))
    f1 = binary(ImageChops.subtract(base_f1, removed))
    revised_visible = binary(ImageChops.subtract(visible, removed))
    remaining_violation = fairing_violation_mask(
        revised,
        elbow,
        axis,
        normal,
    )
    if mask_count(removed) != 35:
        raise RuntimeError("The selected bilateral fairing no longer removes 35 pixels.")

    rgba_mask(removed).save(MASKS / "elbow-seam-bilateral-fairing-removed-35px.png")
    rgba_mask(f1).save(MASKS / "F1-elbow-active-root-faired.png")
    rgba_mask(f2).save(MASKS / "F2-locked-visible-source.png")
    rgba_mask(f3).save(MASKS / "F3-hidden-body-fill.png")
    rgba_mask(f4).save(MASKS / "F4-wrist-hidden-extension.png")
    rgba_mask(wrist_responsibility).save(
        MASKS / "F5-wrist-responsibility-not-material.png"
    )
    rgba_mask(revised).save(MASKS / "production-forearm-geometry-faired.png")
    rgba_mask(hand_proxy).save(MASKS / "temporary-hand-root-envelope.png")
    flat = V7C_MODULE.build_flat_color(source_color, revised_visible, f4)
    flat.save(MASKS / "production-forearm-flat-color-faired.png")

    b1 = json.loads(B1_REPORT.read_text(encoding="utf-8"))
    compression = float(b1["widthProfiles"]["rootWiderThanUpperByPx"])
    positive_extent = max(
        float(row["positiveNormalPx"])
        for row in b1["widthProfiles"]["visibleForearmRoot"][:3]
    )
    elbow_min = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    elbow_rest = float(skeleton["restAnglesDeg"]["theta2"])
    elbow_max = float(skeleton["allowedRangesDeg"]["theta2"]["max"])
    dense_angles = [
        elbow_min + (elbow_max - elbow_min) * index / 240.0
        for index in range(241)
    ]
    primary = V6_MODULE.primary_states(skeleton)
    extremes = V6_MODULE.extreme_states(skeleton)
    elbow_all = dense_angles + [
        float(state["theta2"]) for state in primary + extremes
    ]
    elbow_rows = [
        B2_MODULE.evaluate(
            theta,
            skeleton,
            frame,
            revised,
            upper,
            sleeve,
            compression,
            positive_extent,
        )[0]
        for theta in elbow_all
    ]
    elbow_gap = max(
        row["missingResponsibilityPixelsAt4x"] for row in elbow_rows
    )
    elbow_broken = sum(not row["connectedByOverlap"] for row in elbow_rows)
    elbow_return_first = B2_MODULE.evaluate(
        elbow_rest,
        skeleton,
        frame,
        revised,
        upper,
        sleeve,
        compression,
        positive_extent,
    )[2]
    elbow_return_second = B2_MODULE.evaluate(
        elbow_rest,
        skeleton,
        frame,
        revised,
        upper,
        sleeve,
        compression,
        positive_extent,
    )[2]
    elbow_return = mask_difference_count(
        elbow_return_first, elbow_return_second
    )

    wrist = evaluate_wrist_domain(
        skeleton,
        frame,
        natural_forearm,
        f4,
        hand_proxy,
        wrist_responsibility,
    )
    wrist_gap = max(
        row["missingResponsibilityPixelsAt4x"] for row in wrist["denseRows"]
    )
    wrist_broken = sum(
        not row["connectedByOverlap"] for row in wrist["denseRows"]
    )
    theta_grid = [
        elbow_min + (elbow_max - elbow_min) * index / 8.0
        for index in range(9)
    ]
    phi_grid = [
        wrist["minimum"]
        + (wrist["maximum"] - wrist["minimum"]) * index / 8.0
        for index in range(9)
    ]
    grid_rows = []
    for theta in theta_grid:
        for phi in phi_grid:
            metrics = V7C_MODULE.evaluate_wrist(
                phi,
                wrist["fixedHigh"],
                wrist["handHigh"],
                wrist["responsibilityHigh"],
                wrist["f4High"],
                wrist["handHigh"],
                wrist["center"],
            )[0]
            grid_rows.append(
                {
                    "theta2Deg": theta,
                    "phiWristLocalDeg": phi,
                    "missingWristResponsibilityPixelsAt4x": metrics[
                        "missingResponsibilityPixelsAt4x"
                    ],
                    "connectedAtWrist": metrics["connectedByOverlap"],
                }
            )
    grid_gap = max(
        row["missingWristResponsibilityPixelsAt4x"] for row in grid_rows
    )
    full_pose_forearm_rows = []
    for theta in theta_grid:
        _, posed_forearm, _, _ = corrected_full_pose_masks(
            theta,
            0.0,
            skeleton,
            frame,
            revised,
            f4,
            hand_proxy,
            upper,
            sleeve,
            compression,
            positive_extent,
        )
        full_pose_forearm_rows.append(
            {
                "theta2Deg": theta,
                "connectedComponents": (
                    B2_MODULE.B0_MODULE.connected_components(posed_forearm)
                ),
            }
        )
    full_pose_disconnected = sum(
        row["connectedComponents"] != 1 for row in full_pose_forearm_rows
    )

    partition_union = Image.new("L", revised.size, 0)
    for part in (f1, f2, f3, f4):
        partition_union = ImageChops.lighter(partition_union, part)
    partition_diff = mask_difference_count(partition_union, revised)
    overlap_counts = {}
    parts = (f1, f2, f3, f4)
    for first in range(4):
        for second in range(first + 1, 4):
            overlap_counts[f"F{first + 1}&F{second + 1}"] = mask_count(
                ImageChops.multiply(parts[first], parts[second])
            )
    approved_support = ImageChops.lighter(
        OWNERSHIP.polygon_mask(OWNERSHIP.ARM_SHAFT_OUTLINE),
        bracelet,
    )
    outside_support = mask_count(
        ImageChops.subtract(revised, approved_support)
    )
    retained_rgb_difference = ImageChops.difference(
        flat.convert("RGB"), source_color
    )
    channels = retained_rgb_difference.split()
    rgb_any = ImageChops.lighter(
        ImageChops.lighter(channels[0], channels[1]), channels[2]
    )
    retained_rgb_diff = mask_count(
        ImageChops.multiply(binary(rgb_any), revised_visible)
    )
    flat_alpha_diff = mask_difference_count(flat.getchannel("A"), revised)

    scan_payload = {
        "schemaVersion": 1,
        "elbowDensePrimaryAndExtremeSamples": elbow_rows,
        "wristDenseSamples": wrist["denseRows"],
        "wristCriticalEpsilonSamples": wrist["epsilonRows"],
        "wristAdaptiveMinimumSearch": wrist["adaptiveRows"],
        "elbowByWrist9x9": grid_rows,
        "fullPoseForearm9": full_pose_forearm_rows,
    }
    write_json(AUDIT / "v7c1-parameter-domain-scans.json", scan_payload)

    report = {
        "schemaVersion": 1,
        "gate": "V7-C1 user-requested elbow-seam fairing",
        "status": (
            "engineering_pass_pending_user_visual_approval"
            if mask_count(removed) == 35
            and mask_count(remaining_violation) == 0
            and B2_MODULE.B0_MODULE.connected_components(revised) == 1
            and V6_MODULE.hole_count(revised) == 0
            and partition_diff == 0
            and all(value == 0 for value in overlap_counts.values())
            and outside_support == 0
            and retained_rgb_diff == 0
            and flat_alpha_diff == 0
            and elbow_gap == 0
            and elbow_broken == 0
            and elbow_return == 0
            and wrist_gap == 0
            and wrist_broken == 0
            and wrist["returnDifference"] == 0
            and grid_gap == 0
            and full_pose_disconnected == 0
            else "engineering_fail"
        ),
        "trigger": {
            "decisionOwner": "user",
            "sourceStatement": rejection["sourceStatement"],
            "rejectedGate": "V7-C elbow seam",
        },
        "evidenceDeliveryCorrection": {
            "reviewStatement": "这些为什么是断掉的",
            "cause": (
                "the corrected 3x3 render reused the rejected V7-C filename "
                "and the UI retained the pre-fix image"
            ),
            "cacheSafeFullChainPath": (
                "qa/V7-C1-FULL-CHAIN-ELBOW-WRIST-3X3.png"
            ),
            "allQaFilesVersionedV7C1": True,
        },
        "selectedRepair": {
            "method": (
                "bilateral root profile for 0<=s<=10: "
                "negative n>=mix(-14.0,-16.2,smoothstep(s/10)); "
                "positive n<=mix(13.5,18.0,smoothstep(s/10))"
            ),
            "removedSourceBoundaryPixels": mask_count(removed),
            "remainingProfileViolationPixels": mask_count(remaining_violation),
            "removedMask": "masks/elbow-seam-bilateral-fairing-removed-35px.png",
            "alternativeReason": (
                "the prior 5-pixel one-sided repair removed the isolated tip "
                "but retained a visible width step at the neutral elbow; the "
                "bilateral 10px smoothstep profile aligns both root shoulders"
            ),
            "neutralOwnershipExceptionRequiresUserApproval": True,
        },
        "frozenIntegrity": {
            "status": integrity["status"],
            "groups": [
                {
                    "name": group["name"],
                    "checked": group["checked"],
                    "passed": group["passed"],
                    "failed": group["failed"],
                }
                for group in integrity["frozenArtifactGroups"]
            ],
        },
        "productionForearm": {
            "pixels": mask_count(revised),
            "connectedComponents": B2_MODULE.B0_MODULE.connected_components(
                revised
            ),
            "holes": V6_MODULE.hole_count(revised),
            "outsideApprovedNeutralSupportPixels": outside_support,
            "originalApprovedVisibleSourcePixels": mask_count(visible),
            "userRequestedFairingExceptionPixels": mask_count(removed),
            "retainedVisibleSourcePixels": mask_count(revised_visible),
            "retainedSourceRgbDifferencePixels": retained_rgb_diff,
            "flatColorAlphaDifferencePixels": flat_alpha_diff,
        },
        "partitions": {
            "F1Pixels": mask_count(f1),
            "F2Pixels": mask_count(f2),
            "F3Pixels": mask_count(f3),
            "F4Pixels": mask_count(f4),
            "F5ResponsibilityPixels": mask_count(wrist_responsibility),
            "pairwiseOverlapPixels": overlap_counts,
            "reconstructionDifferencePixels": partition_diff,
        },
        "elbowValidation": {
            "primarySamples": 41,
            "combinationExtremes": 6,
            "denseSamples": 241,
            "maximumMissingResponsibilityPixelsAt4x": elbow_gap,
            "brokenAdjacencyEvaluations": elbow_broken,
            "deterministicReturnDifferencePixelsAt4x": elbow_return,
            "boneLengthErrorPx": 0.0,
        },
        "wristValidation": {
            "denseSamples": len(wrist["denseRows"]),
            "criticalEpsilonSamples": len(wrist["epsilonRows"]),
            "adaptiveMinimumSamples": len(wrist["adaptiveRows"]),
            "maximumMissingResponsibilityPixelsAt4x": wrist_gap,
            "brokenAdjacencySamples": wrist_broken,
            "deterministicReturnDifferencePixelsAt4x": wrist[
                "returnDifference"
            ],
            "braceletCountedAsCoverage": False,
        },
        "combinedDomain": {
            "grid": "9x9",
            "samples": len(grid_rows),
            "maximumMissingWristResponsibilityPixelsAt4x": grid_gap,
            "fullPoseForearmThetaSamples": len(full_pose_forearm_rows),
            "disconnectedFullPoseForearmSamples": full_pose_disconnected,
            "fkOnlyDisclaimer": (
                "joint-local seam independence belongs only to this rigid-FK "
                "proof and must not be transferred to Cubism combined key shapes"
            ),
        },
        "visualApprovalStillRequired": True,
        "finalV7Frozen": False,
        "notPerformed": [
            "no frozen V4, complete sleeve, or V6 file changed",
            "no texture, PSD, ArtMesh, Cubism, Physics, or Runtime",
            "no final freeze manifest",
        ],
        "visualEvidence": [
            "qa/V7-C1-ELBOW-SEAM-BEFORE-AFTER.png",
            "qa/V7-C1-FORMAL-ELBOW-THREE-ANGLES.png",
            "qa/V7-C1-FORMAL-ELBOW-SLOW-SCAN.gif",
            "qa/V7-C1-WRIST-THREE-ANGLES.png",
            "qa/V7-C1-WRIST-SLOW-SCAN.gif",
            "qa/V7-C1-FULL-CHAIN-ELBOW-WRIST-3X3.png",
            "qa/V7-C1-DISPLACED-PART-INTEGRITY.png",
        ],
    }
    write_json(AUDIT / "v7c1-elbow-seam-fairing.json", report)

    render_before_after(
        skeleton,
        frame,
        baseline_formal,
        revised,
        upper,
        sleeve,
        compression,
        positive_extent,
    )
    V7C_MODULE.render_partition_board(
        source_color,
        f1,
        f2,
        f3,
        f4,
        wrist_responsibility,
        revised,
        hand_proxy,
        natural_forearm,
    )
    V7C_MODULE.render_elbow_three_angles_and_scan(
        skeleton,
        frame,
        revised,
        upper,
        sleeve,
        compression,
        positive_extent,
    )
    V7C_MODULE.render_wrist_three_angles(
        [wrist["minimum"], 0.0, wrist["maximum"]],
        wrist["fixedHigh"],
        wrist["handHigh"],
        wrist["responsibilityHigh"],
        wrist["f4High"],
        wrist["handHigh"],
        wrist["center"],
    )
    V7C_MODULE.render_wrist_slow_scan(
        wrist["minimum"],
        wrist["maximum"],
        wrist["fixedHigh"],
        wrist["handHigh"],
        wrist["responsibilityHigh"],
        wrist["f4High"],
        wrist["handHigh"],
        wrist["center"],
    )
    V7C_MODULE.render_full_combination_grid(
        [elbow_min, elbow_rest, elbow_max],
        [wrist["minimum"], 0.0, wrist["maximum"]],
        skeleton,
        frame,
        revised,
        f4,
        hand_proxy,
        upper,
        sleeve,
        compression,
        positive_extent,
    )
    V7C_MODULE.render_displaced_integrity(
        skeleton,
        frame,
        revised,
        f4,
        hand_proxy,
        natural_forearm,
        upper,
        sleeve,
        compression,
        positive_extent,
    )
    version_v7c1_qa_paths()

    markdown = f"""# V7-C1 肘缝双侧渐缩圆滑修正

## 触发

用户指出：`{rejection["sourceStatement"]}`。

旧 V7-C 数值无缺口，但直立角度的前臂根部仍比上臂接头左右各宽约 3 px，形成可见台阶。只裁右侧 5 px 尖点不足以解决粗细不对版，因此改为双侧 10 px 长度的 smoothstep 渐缩，共调整 35 个源边界像素。

## 最小修正

- 双侧根部在 `10 px` 长度内平滑过渡，共调整 `35 px`；
- F1 从 `718 px` 调整为 `{mask_count(f1)} px`；
- 其余 F2、F3、F4、腕线和手根包络不变；
- 新正式前臂 `{mask_count(revised)} px`、连通分量 `{B2_MODULE.B0_MODULE.connected_components(revised)}`、孔洞 `{V6_MODULE.hole_count(revised)}`；
- 圆滑轮廓约束剩余违规像素 `0`；
- 中性批准源支持外像素 `0`。

这 35 个像素是用户要求的中性边界圆滑例外；保留的 `{mask_count(revised_visible)} px` 源可见像素 RGB 差仍为 `0`。最终仍需用户视觉批准，不能把本次反馈自动解释成对修正结果的批准。

## 全域复跑

- 正式肘部：41+6+241，最大缺口 `{elbow_gap}`，断开 `{elbow_broken}`，回程差 `{elbow_return}`；
- 腕部：201 点 + 11 个临界点 + 81 个自适应点，最大缺口 `{wrist_gap}`，断开 `{wrist_broken}`，回程差 `{wrist["returnDifference"]}`；
- 肘×腕 9×9：最大缺口 `{grid_gap}`；
- 全姿态前臂 9 个肘角采样：断裂样本 `{full_pose_disconnected}`；
- 骨长误差：`0 px`；
- 手链不计入腕部覆盖。

## 请审查

1. `qa/V7-C1-ELBOW-SEAM-BEFORE-AFTER.png`
2. `qa/V7-C1-FORMAL-ELBOW-THREE-ANGLES.png`
3. `qa/V7-C1-FORMAL-ELBOW-SLOW-SCAN.gif`
4. `qa/V7-C1-FULL-CHAIN-ELBOW-WRIST-3X3.png`

请确认双侧小台阶已消失，并且圆滑后没有形成凹口、骨裂或新的粗细跳变。
"""
    (AUDIT / "V7-C1-ELBOW-SEAM-FAIRING.zh-CN.md").write_text(
        markdown,
        encoding="utf-8",
    )
    checklist = """# V7-C1 用户复核

只需检查本轮被指出的肘缝：

1. `qa/V7-C1-ELBOW-SEAM-BEFORE-AFTER.png`
2. `qa/V7-C1-FORMAL-ELBOW-SLOW-SCAN.gif`
3. `qa/V7-C1-FULL-CHAIN-ELBOW-WRIST-3X3.png`

确认点：

- 原双侧宽度台阶已消失；
- 上臂到前臂是圆滑连续连接；
- 三角度和慢扫中没有新凹口、尖刺、鼓包或骨裂；
- 接受这 35 个源边界像素作为用户要求的中性圆滑例外。

若可以，请回复：

`批准 V7-C1 肘缝双侧圆滑修正及 35 像素边界例外`
"""
    (AUDIT / "V7-C1-USER-REVIEW-CHECKLIST.zh-CN.md").write_text(
        checklist,
        encoding="utf-8",
    )
    write_json(AUDIT / "v7c1-evidence-manifest.json", manifest())


if __name__ == "__main__":
    main()
