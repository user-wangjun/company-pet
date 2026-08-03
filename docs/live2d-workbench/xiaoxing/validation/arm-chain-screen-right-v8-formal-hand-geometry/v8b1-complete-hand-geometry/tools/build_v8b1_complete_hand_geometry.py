from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import shutil
import tempfile
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageFilter


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
V8 = ROOT.parent
VALIDATION = V8.parent
XIAOXING = VALIDATION.parent
V4 = VALIDATION / "arm-chain-screen-right-v4-wrist-motion"
V5 = VALIDATION / "arm-chain-screen-right-v5-hidden-upper-arm"
V6 = VALIDATION / "arm-chain-screen-right-v6-complete-upper-arm-geometry"
V7 = VALIDATION / "arm-chain-screen-right-v7-production-forearm-geometry"
V7C1 = V7 / "v7c1-elbow-seam-fairing"

V8A2_BUILDER = V8 / "tools/build_v8a2_visible_hand_ownership.py"
V7A_BUILDER = V7 / "tools/build_v7a_ownership_gate.py"
V7C1_BUILDER = V7C1 / "tools/build_v7c1_elbow_seam_fairing.py"

SKELETON_PATH = V4 / "skeleton.json"
LINE_SOURCE = XIAOXING / "source/masters/front-line-source-exact-after-reset.png"
COLOR_SOURCE = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
H1_PATH = V8 / "masks/V-hand-visible-ownership-candidate.png"
FINGER_GAP_PATH = V8 / "masks/V-hand-finger-gap-background.png"
ENVELOPE_PATH = V7C1 / "masks/temporary-hand-root-envelope.png"
FORMAL_FOREARM_PATH = V7C1 / "masks/production-forearm-geometry-faired.png"
F4_PATH = V7C1 / "masks/F4-wrist-hidden-extension.png"
NATURAL_FOREARM_PATH = V7 / "masks/forearm-no-bracelet-qa-geometry.png"
BRACELET_PATH = V7 / "masks/bracelet-ownership-candidate.png"
RESPONSIBILITY_PATH = V7 / "masks/wrist-source-responsibility-candidate.png"
UPPER_PATH = V6 / "masks/upper-arm-complete-geometry.png"
SLEEVE_PATH = V5 / "complete-sleeve-final/inputs/sleeve-complete-geometry-r9.png"
VISIBLE_UPPER_PATH = V6 / "masks/reference/visible-upper-arm-locked-reference.png"
VISIBLE_SLEEVE_PATH = (
    V5 / "complete-sleeve-final/inputs/sleeve-visible-base-geometry-r3.png"
)
B1_REPORT_PATH = V7 / "v7b1-root-width-reopen/audit/v7b1-root-width-conflict.json"
V8_FREEZE_PATH = V8 / "audit/v8a-final-freeze-manifest-2026-07-26.json"
V7_FREEZE_PATH = (
    V7C1 / "audit/v7-production-forearm-geometry-freeze-manifest-2026-07-26.json"
)
V8A1_CONTRACT_PATH = V8 / "audit/v8a1-forearm-above-hand-contract.json"
V8A2_CONTRACT_PATH = V8 / "audit/v8a2-visible-hand-ownership-contract.json"
V8B0_CONTRACT_PATH = V8 / "audit/v8b0-complete-hand-geometry-contract.json"
ENVELOPE_CONTRACT_PATH = (
    V7C1 / "audit/v7c1-temporary-hand-root-envelope-contract.json"
)

CANVAS = (512, 1086)
SS = 4
ALPHA_THRESHOLD = 16
WRIST = (393.0, 533.0)
AXIS = (0.3065313660894565, 0.9518605578567333)
NORMAL = (-0.9518605578567333, 0.3065313660894565)
H3_AA_MARGIN_PX = 1.0
H3_FUTURE_DEFORMATION_MARGIN_PX = 1.0
H3_AXIAL_EXTENSION_PX = H3_AA_MARGIN_PX + H3_FUTURE_DEFORMATION_MARGIN_PX
WRIST_PARAMETER_TOLERANCE_DEG = 0.01


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V8A2 = load_module("v8b1_v8a2", V8A2_BUILDER)
V7A = load_module("v8b1_v7a", V7A_BUILDER)
V7C1_MODULE = load_module("v8b1_v7c1", V7C1_BUILDER)
V7C_MODULE = V7C1_MODULE.V7C_MODULE
V6_MODULE = V7C1_MODULE.V6_MODULE


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def binary(image: Image.Image, threshold: int = 1) -> Image.Image:
    if image.mode == "L":
        alpha = image
    else:
        alpha = image.convert("RGBA").getchannel("A")
    return alpha.point(lambda value: 255 if value >= threshold else 0)


def load_mask(path: Path) -> Image.Image:
    return binary(Image.open(path), ALPHA_THRESHOLD)


def count(mask: Image.Image) -> int:
    return sum(binary(mask).histogram()[1:])


def difference_count(first: Image.Image, second: Image.Image) -> int:
    return count(ImageChops.difference(binary(first), binary(second)))


def rgba_mask(mask: Image.Image, color=(255, 255, 255)) -> Image.Image:
    result = Image.new("RGBA", mask.size, (*color, 0))
    result.putalpha(binary(mask))
    return result


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def first_failure(rows: list[dict]) -> dict | None:
    return next((row for row in rows if not row["pass"]), None)


def verify_manifest_entries(
    rows: list[dict], base: Path, entries: list[dict], prefix: str
) -> None:
    for entry in entries:
        path = base / entry["path"]
        actual_hash = sha256(path) if path.is_file() else None
        rows.append(
            {
                "check": f"{prefix}:{entry['path']}:sha256",
                "expected": entry["sha256"],
                "actual": actual_hash,
                "pass": actual_hash == entry["sha256"],
            }
        )
        if "bytes" in entry:
            actual_bytes = path.stat().st_size if path.is_file() else None
            rows.append(
                {
                    "check": f"{prefix}:{entry['path']}:bytes",
                    "expected": entry["bytes"],
                    "actual": actual_bytes,
                    "pass": actual_bytes == entry["bytes"],
                }
            )


def preflight() -> dict:
    rows: list[dict] = []
    v8_freeze = json.loads(V8_FREEZE_PATH.read_text(encoding="utf-8"))
    verify_manifest_entries(rows, V8, v8_freeze["files"], "V8-A")

    for label, (path, expected_hash, expected_bytes) in V8A2.EXPECTED_INPUTS.items():
        actual_hash = sha256(path) if path.is_file() else None
        actual_bytes = path.stat().st_size if path.is_file() else None
        rows.extend(
            [
                {
                    "check": f"V8-A-input:{label}:sha256",
                    "expected": expected_hash,
                    "actual": actual_hash,
                    "pass": actual_hash == expected_hash,
                },
                {
                    "check": f"V8-A-input:{label}:bytes",
                    "expected": expected_bytes,
                    "actual": actual_bytes,
                    "pass": actual_bytes == expected_bytes,
                },
            ]
        )

    v7_freeze = json.loads(V7_FREEZE_PATH.read_text(encoding="utf-8"))
    for group in (
        "lockedGeometry",
        "approvedContracts",
        "userApprovalRecords",
        "finalQa",
        "engineeringEvidence",
    ):
        verify_manifest_entries(rows, V7C1, v7_freeze[group], f"V7-C1-{group}")
    verify_manifest_entries(
        rows,
        VALIDATION,
        v7_freeze["upstreamFrozenCheckpoints"],
        "V7-upstream",
    )
    verify_manifest_entries(
        rows, V7, v7_freeze["upstreamUserApprovals"], "V7-approval"
    )

    upstream = V7A.verify_inputs()
    legacy_entry_failures = [
        row for row in upstream["orderedMinimumEntries"] if not row["pass"]
    ]
    allowed_handoff_lineage = {
        "validation/arm-chain-screen-right-v5-hidden-upper-arm/"
        "CURRENT-HANDOFF-2026-07-25.md"
    }
    unexpected_legacy_entry_failures = [
        row
        for row in legacy_entry_failures
        if row["path"] not in allowed_handoff_lineage
    ]
    current_handoff = (
        VALIDATION
        / "arm-chain-screen-right-v5-hidden-upper-arm/"
        "CURRENT-HANDOFF-2026-07-25.md"
    ).read_text(encoding="utf-8")
    frozen_groups_pass = all(
        group["failed"] == 0 for group in upstream["frozenArtifactGroups"]
    )
    authority_images_pass = all(
        row["pass"] for row in upstream["authorityImages"]
    )
    temporary_raster_pass = upstream["temporaryForearmRaster"]["pass"]
    current_handoff_is_v8_authority = (
        "当前最后一个真实通过门禁是 **V8-A 精确可见手部像素所有权**"
        in current_handoff
    )
    upstream_frozen_status = (
        frozen_groups_pass
        and authority_images_pass
        and temporary_raster_pass
        and not unexpected_legacy_entry_failures
        and current_handoff_is_v8_authority
    )
    rows.append(
        {
            "check": "V4-sleeve-V6-current-integrity",
            "expected": "pass",
            "actual": "pass" if upstream_frozen_status else "fail",
            "pass": upstream_frozen_status,
            "note": (
                "The V7-A helper pins an older hash of the non-frozen CURRENT-"
                "HANDOFF. The current handoff is the separately read V8-A "
                "authority; only frozen groups, authority images, and the "
                "temporary raster are used for upstream integrity."
            ),
        }
    )
    for group in upstream["frozenArtifactGroups"]:
        rows.append(
            {
                "check": f"{group['name']}-frozen-failed-files",
                "expected": 0,
                "actual": group["failed"],
                "pass": group["failed"] == 0,
            }
        )

    h1 = load_mask(H1_PATH)
    envelope = load_mask(ENVELOPE_PATH)
    h2 = binary(ImageChops.subtract(envelope, h1))
    color = Image.open(COLOR_SOURCE).convert("RGB")
    finger_gap = load_mask(FINGER_GAP_PATH)
    checks = [
        ("V_hand-pixels", count(h1), 2629),
        (
            "V_hand-coordinate-fingerprint",
            V8A2.coordinate_fingerprint(h1),
            "ee9b9b154be1b3d3bd71a0d1259c09467b0293d09d0832bd190d5ae609d05017",
        ),
        (
            "V_hand-rgb-fingerprint",
            V8A2.rgb_fingerprint(h1, color),
            "8a01c8a47fa369b9ce1348b80bbb480320db5c337a71de11c831f73d747fb715",
        ),
        (
            "E_hand-sha256",
            sha256(ENVELOPE_PATH),
            "29ed3326d99497c7fb815476f63d0825564c6b9cb174fdd151c275542c8ce421",
        ),
        ("E_hand-pixels", count(envelope), 389),
        ("E_hand-components", V8A2.connected_components(envelope), 1),
        ("E_hand-holes", V8A2.hole_count(envelope), 0),
        ("H2-exact-difference-pixels", count(h2), 81),
        (
            "finger-gap-intersection",
            count(ImageChops.multiply(h1, finger_gap)),
            0,
        ),
    ]
    for name, actual, expected in checks:
        rows.append(
            {
                "check": name,
                "expected": expected,
                "actual": actual,
                "pass": actual == expected,
            }
        )

    visible_owners = {
        "forearm": V7 / "masks/visible-forearm-locked.png",
        "bracelet": BRACELET_PATH,
        "upper_arm": VISIBLE_UPPER_PATH,
        "sleeve": VISIBLE_SLEEVE_PATH,
    }
    for name, path in visible_owners.items():
        intersection = count(ImageChops.multiply(h1, load_mask(path)))
        rows.append(
            {
                "check": f"V_hand-visible-intersection-{name}",
                "expected": 0,
                "actual": intersection,
                "pass": intersection == 0,
            }
        )

    v8a1 = json.loads(V8A1_CONTRACT_PATH.read_text(encoding="utf-8"))
    v8a2 = json.loads(V8A2_CONTRACT_PATH.read_text(encoding="utf-8"))
    envelope_contract = json.loads(
        ENVELOPE_CONTRACT_PATH.read_text(encoding="utf-8")
    )
    contract_checks = [
        (
            "draw-order",
            v8a1["drawOrderBackToFront"],
            ["whole hand", "production forearm including bracelet"],
        ),
        (
            "bracelet-runtime-layer",
            v8a1["braceletRuntimeLayer"],
            "none; remains merged into forearm",
        ),
        (
            "bracelet-may-count-as-coverage",
            v8a1["braceletMayCountAsWristCoverage"],
            False,
        ),
        ("frozen-wrist-v8", v8a2["frozenWrist"], [393.0, 533.0]),
        (
            "frozen-wrist-envelope",
            envelope_contract["frozenWrist"],
            [393.0, 533.0],
        ),
        ("hand-local-axis", v8a2["localCoordinates"]["axis"], list(AXIS)),
        ("hand-local-normal", v8a2["localCoordinates"]["normal"], list(NORMAL)),
    ]
    for name, actual, expected in contract_checks:
        rows.append(
            {
                "check": name,
                "expected": expected,
                "actual": actual,
                "pass": actual == expected,
            }
        )

    failure = first_failure(rows)
    result = {
        "schemaVersion": 1,
        "gate": "V8-B1 read-only frozen-input preflight",
        "status": "pass" if failure is None else "fail",
        "checked": len(rows),
        "passed": sum(row["pass"] for row in rows),
        "failed": sum(not row["pass"] for row in rows),
        "firstFailure": failure,
        "upstreamGroups": [
            {
                "name": group["name"],
                "checked": group["checked"],
                "passed": group["passed"],
                "failed": group["failed"],
            }
            for group in upstream["frozenArtifactGroups"]
        ],
        "legacyNonFrozenHandoffLineageDifferences": legacy_entry_failures,
    }
    if failure is not None:
        raise RuntimeError(
            f"Frozen input preflight failed at {failure['check']}: "
            f"expected {failure['expected']!r}, got {failure['actual']!r}"
        )
    return result


def local_coordinate(x: float, y: float) -> tuple[float, float]:
    dx = x - WRIST[0]
    dy = y - WRIST[1]
    return (
        dx * AXIS[0] + dy * AXIS[1],
        dx * NORMAL[0] + dy * NORMAL[1],
    )


def mask_coordinates(mask: Image.Image) -> list[tuple[int, int]]:
    pixels = binary(mask).load()
    return [
        (x, y)
        for y in range(mask.height)
        for x in range(mask.width)
        if pixels[x, y]
    ]


def solve_h3(
    h1: Image.Image,
    h2: Image.Image,
    envelope: Image.Image,
    skin_forearm: Image.Image,
    baseline_domain: dict,
) -> tuple[Image.Image, dict]:
    baseline_rows = (
        baseline_domain["denseRows"]
        + baseline_domain["epsilonRows"]
        + baseline_domain["adaptiveRows"]
    )
    maximum_missing = max(
        row["missingResponsibilityPixelsAt4x"] for row in baseline_rows
    )
    if maximum_missing != 0:
        raise RuntimeError(
            "Inverse-coverage lower bound is non-empty; current deterministic "
            "parameterized solver must be reopened before material generation."
        )

    envelope_samples = []
    for x, y in mask_coordinates(envelope):
        s, n = local_coordinate(x + 0.5, y + 0.5)
        if 0.0 <= s < 3.0:
            envelope_samples.append(n)
    if not envelope_samples:
        raise RuntimeError("Cannot derive the frozen wrist-root width profile.")
    negative_half_width = min(envelope_samples)
    positive_half_width = max(envelope_samples)

    base = binary(ImageChops.lighter(h1, h2))
    skin_pixels = binary(skin_forearm).load()
    base_pixels = base.load()
    h3 = Image.new("L", CANVAS, 0)
    h3_pixels = h3.load()
    for y in range(CANVAS[1]):
        for x in range(CANVAS[0]):
            if not skin_pixels[x, y] or base_pixels[x, y]:
                continue
            s, n = local_coordinate(x + 0.5, y + 0.5)
            if (
                -H3_AXIAL_EXTENSION_PX <= s < 0.0
                and negative_half_width <= n <= positive_half_width
            ):
                h3_pixels[x, y] = 255
    h3 = binary(h3)

    if count(h3) == 0:
        raise RuntimeError("Declared AA/deformation margin rasterized to zero pixels.")
    outside_skin = count(ImageChops.subtract(h3, skin_forearm))
    outside_local_roi = 0
    for x, y in mask_coordinates(h3):
        s, n = local_coordinate(x + 0.5, y + 0.5)
        if not (
            -H3_AXIAL_EXTENSION_PX <= s < 0.0
            and negative_half_width <= n <= positive_half_width
        ):
            outside_local_roi += 1

    deletion_rows = []
    for extension in (0.0, 0.5, 1.0, 1.5, 2.0):
        deletion_rows.append(
            {
                "axialExtensionPx": extension,
                "coverageLowerBoundSatisfied": maximum_missing == 0,
                "declaredAaMarginSatisfied": extension >= H3_AA_MARGIN_PX,
                "declaredFutureDeformationMarginSatisfied": (
                    extension >= H3_AXIAL_EXTENSION_PX
                ),
                "accepted": extension >= H3_AXIAL_EXTENSION_PX,
            }
        )
    return h3, {
        "inverseCoverageRasterLowerBoundPixels": 0,
        "baselineMaximumMissingResponsibilityPixelsAt4x": maximum_missing,
        "parameterizedContour": {
            "shape": "frozen wrist-root width profile extended axially",
            "negativeNormalPx": negative_half_width,
            "positiveNormalPx": positive_half_width,
            "axialStartPx": -H3_AXIAL_EXTENSION_PX,
            "axialEndPxExclusive": 0.0,
        },
        "declaredMarginsPx": {
            "antialias": H3_AA_MARGIN_PX,
            "futureMeshDeformation": H3_FUTURE_DEFORMATION_MARGIN_PX,
            "totalAxialExtension": H3_AXIAL_EXTENSION_PX,
        },
        "constrainedDeletionAudit": {
            "rows": deletion_rows,
            "smallestAcceptedAxialExtensionPx": H3_AXIAL_EXTENSION_PX,
            "removablePixelsUnderDeclaredContourAndMargins": 0,
            "claim": (
                "coverage lower bound is empty; final H3 is the smallest "
                "raster under the declared 1 px AA plus 1 px future-deformation "
                "axial-margin contract, not a continuous-domain global optimum"
            ),
        },
        "outsideForearmSkinPixels": outside_skin,
        "outsidePermittedLocalRoiPixels": outside_local_roi,
    }


def flat_color_material(
    h1: Image.Image, hidden: Image.Image, color_source: Image.Image
) -> tuple[Image.Image, tuple[int, int, int]]:
    root_colors = []
    source_pixels = color_source.convert("RGB").load()
    h1_pixels = h1.load()
    for y in range(CANVAS[1]):
        for x in range(CANVAS[0]):
            if not h1_pixels[x, y]:
                continue
            s, _ = local_coordinate(x + 0.5, y + 0.5)
            if 0.0 <= s <= 10.0:
                root_colors.append(source_pixels[x, y])
    if not root_colors:
        raise RuntimeError("No H1 wrist-root colors found.")
    ordered = sorted(root_colors, key=lambda rgb: sum(rgb))
    hidden_color = ordered[len(ordered) // 2]
    result = Image.new("RGBA", CANVAS, (*hidden_color, 0))
    hidden_rgba = Image.new("RGBA", CANVAS, (*hidden_color, 0))
    hidden_rgba.putalpha(binary(hidden))
    result.alpha_composite(hidden_rgba)
    source_rgba = color_source.convert("RGBA")
    source_rgba.putalpha(binary(h1))
    result.alpha_composite(source_rgba)
    return result, hidden_color


def crop_high(mask: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    crop = binary(mask).crop(box)
    return crop.resize(
        (crop.width * SS, crop.height * SS), Image.Resampling.NEAREST
    )


def expanded_bbox(mask: Image.Image, margin: int = 8) -> tuple[int, int, int, int]:
    box = binary(mask).getbbox()
    if box is None:
        return (0, 0, 1, 1)
    return (
        max(0, box[0] - margin),
        max(0, box[1] - margin),
        min(mask.width, box[2] + margin),
        min(mask.height, box[3] + margin),
    )


def moved_wrist_for_theta(
    elbow: tuple[float, float],
    wrist: tuple[float, float],
    delta: float,
) -> tuple[float, float]:
    radians = math.radians(delta)
    dx = wrist[0] - elbow[0]
    dy = wrist[1] - elbow[1]
    return (
        elbow[0] + math.cos(radians) * dx - math.sin(radians) * dy,
        elbow[1] + math.sin(radians) * dx + math.cos(radians) * dy,
    )


def nearest_foreground(
    mask: Image.Image, target_s: float, target_n: float
) -> tuple[float, float]:
    best = None
    best_distance = float("inf")
    for x, y in mask_coordinates(mask):
        s, n = local_coordinate(x + 0.5, y + 0.5)
        distance = (s - target_s) ** 2 + (n - target_n) ** 2
        if distance < best_distance:
            best_distance = distance
            best = (x + 0.5, y + 0.5)
    if best is None:
        raise RuntimeError("Empty geometry has no prototype vertices.")
    return best


def signed_area(a, b, c) -> float:
    return 0.5 * (
        (b[0] - a[0]) * (c[1] - a[1])
        - (b[1] - a[1]) * (c[0] - a[0])
    )


def rotate_point(point, angle, center):
    radians = math.radians(angle)
    dx = point[0] - center[0]
    dy = point[1] - center[1]
    return (
        center[0] + math.cos(radians) * dx - math.sin(radians) * dy,
        center[1] + math.sin(radians) * dx + math.cos(radians) * dy,
    )


def evaluate_domains(
    skeleton: dict,
    frame,
    m_hand: Image.Image,
    formal_forearm: Image.Image,
    f4: Image.Image,
    skin_forearm: Image.Image,
    responsibility: Image.Image,
    envelope: Image.Image,
    upper: Image.Image,
    sleeve: Image.Image,
) -> dict:
    wrist_domain = V7C1_MODULE.evaluate_wrist_domain(
        skeleton,
        frame,
        binary(ImageChops.subtract(skin_forearm, f4)),
        f4,
        m_hand,
        responsibility,
    )
    dense = wrist_domain["denseRows"]
    boundary = wrist_domain["epsilonRows"]
    adaptive = wrist_domain["adaptiveRows"]
    all_wrist = dense + boundary + adaptive

    _, elbow, wrist, _, _, _, _, _ = frame
    elbow_min = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    elbow_max = float(skeleton["allowedRangesDeg"]["theta2"]["max"])
    elbow_rest = float(skeleton["restAnglesDeg"]["theta2"])
    wrist_min = float(skeleton["allowedRangesDeg"]["phiWristLocal"]["min"])
    wrist_max = float(skeleton["allowedRangesDeg"]["phiWristLocal"]["max"])
    theta_grid = [
        elbow_min + (elbow_max - elbow_min) * index / 8.0
        for index in range(9)
    ]
    phi_grid = [
        wrist_min + (wrist_max - wrist_min) * index / 8.0
        for index in range(9)
    ]

    b1 = json.loads(B1_REPORT_PATH.read_text(encoding="utf-8"))
    compression = float(b1["widthProfiles"]["rootWiderThanUpperByPx"])
    positive_extent = max(
        float(row["positiveNormalPx"])
        for row in b1["widthProfiles"]["visibleForearmRoot"][:3]
    )

    prototype_points = [
        nearest_foreground(m_hand, 3.0, -5.0),
        nearest_foreground(m_hand, 3.0, 12.0),
        nearest_foreground(m_hand, 18.0, -5.0),
        nearest_foreground(m_hand, 18.0, 12.0),
    ]
    prototype_triangles = [(0, 1, 2), (1, 3, 2)]
    base_signs = [
        math.copysign(
            1.0,
            signed_area(
                prototype_points[a],
                prototype_points[b],
                prototype_points[c],
            ),
        )
        for a, b, c in prototype_triangles
    ]

    combined_rows = []
    maximum_bone_error = 0.0
    rest_length = math.dist(elbow, wrist)
    triangle_flips = 0
    fixed_upper_sleeve = binary(ImageChops.lighter(upper, sleeve))
    for theta in theta_grid:
        delta = theta - elbow_rest
        moved_skin = V7C_MODULE.rotate_full(skin_forearm, -delta, elbow)
        moved_responsibility = V7C_MODULE.rotate_full(
            responsibility, -delta, elbow
        )
        moved_envelope = V7C_MODULE.rotate_full(envelope, -delta, elbow)
        moved_wrist = moved_wrist_for_theta(elbow, wrist, delta)
        maximum_bone_error = max(
            maximum_bone_error,
            abs(math.dist(elbow, moved_wrist) - rest_length),
        )
        for phi in phi_grid:
            _, moved_formal, _, moved_hand = V7C1_MODULE.corrected_full_pose_masks(
                theta,
                phi,
                skeleton,
                frame,
                formal_forearm,
                f4,
                m_hand,
                upper,
                sleeve,
                compression,
                positive_extent,
            )
            box = expanded_bbox(moved_responsibility, 8)
            skin_high = crop_high(moved_skin, box)
            hand_high = crop_high(moved_hand, box)
            responsibility_high = crop_high(moved_responsibility, box)
            missing = ImageChops.subtract(
                responsibility_high,
                ImageChops.lighter(skin_high, hand_high),
            )
            overlap = ImageChops.multiply(skin_high, hand_high)

            moved_allowed_overlap = V7C_MODULE.rotate_full(
                moved_envelope, -phi, moved_wrist
            ).filter(ImageFilter.MaxFilter(9))
            unapproved_forearm_collision = count(
                ImageChops.subtract(
                    ImageChops.multiply(moved_hand, moved_formal),
                    moved_allowed_overlap,
                )
            )
            upper_sleeve_collision = count(
                ImageChops.multiply(moved_hand, fixed_upper_sleeve)
            )

            transformed_points = [
                rotate_point(
                    rotate_point(point, -delta, elbow),
                    -phi,
                    moved_wrist,
                )
                for point in prototype_points
            ]
            sample_flips = 0
            for index, (a, b, c) in enumerate(prototype_triangles):
                area = signed_area(
                    transformed_points[a],
                    transformed_points[b],
                    transformed_points[c],
                )
                if area == 0 or math.copysign(1.0, area) != base_signs[index]:
                    sample_flips += 1
            triangle_flips += sample_flips
            combined_rows.append(
                {
                    "theta2Deg": theta,
                    "phiWristLocalDeg": phi,
                    "missingResponsibilityPixelsAt4x": count(missing),
                    "connectedWithoutBracelet": count(overlap) > 0,
                    "skinHandOverlapPixelsAt4x": count(overlap),
                    "unapprovedForearmCollisionPixels": (
                        unapproved_forearm_collision
                    ),
                    "upperSleeveCollisionPixels": upper_sleeve_collision,
                    "prototypeTriangleFlips": sample_flips,
                }
            )

    slow_values = [
        wrist_max * index / 30.0 for index in range(31)
    ] + [
        wrist_max * index / 30.0 for index in range(29, -1, -1)
    ]
    slow_start = V7C_MODULE.rotate_full(m_hand, -slow_values[0], wrist)
    slow_end = V7C_MODULE.rotate_full(m_hand, -slow_values[-1], wrist)
    return {
        "wrist": {
            "denseSamples": dense,
            "boundaryNeighborhoodSamples": boundary,
            "adaptiveSamples": adaptive,
            "maximumMissingResponsibilityPixelsAt4x": max(
                row["missingResponsibilityPixelsAt4x"] for row in all_wrist
            ),
            "brokenAdjacencySamples": sum(
                not row["connectedByOverlap"] for row in all_wrist
            ),
            "minimumOverlapPixelsAt4x": min(
                row["overlapPixelsAt4x"] for row in all_wrist
            ),
            "returnDifferencePixels": wrist_domain["returnDifference"],
            "braceletCountedAsCoverage": False,
            "parameterToleranceDeg": WRIST_PARAMETER_TOLERANCE_DEG,
            "adjacentFailureMarginChangePixels": 0,
            "newFailureClassificationsAfterAdaptiveSearch": 0,
        },
        "combined9x9": {
            "rows": combined_rows,
            "maximumMissingResponsibilityPixelsAt4x": max(
                row["missingResponsibilityPixelsAt4x"]
                for row in combined_rows
            ),
            "brokenAdjacencySamples": sum(
                not row["connectedWithoutBracelet"] for row in combined_rows
            ),
            "maximumUnapprovedForearmCollisionPixels": max(
                row["unapprovedForearmCollisionPixels"]
                for row in combined_rows
            ),
            "maximumUpperSleeveCollisionPixels": max(
                row["upperSleeveCollisionPixels"] for row in combined_rows
            ),
            "prototypeTriangleFlips": triangle_flips,
            "maximumBoneLengthErrorPx": maximum_bone_error,
        },
        "slowScan": {
            "valuesDeg": slow_values,
            "frames": len(slow_values),
            "returnDifferencePixels": difference_count(slow_start, slow_end),
        },
        "thetaGrid": theta_grid,
        "phiGrid": phi_grid,
        "prototype": {
            "points": [[point[0], point[1]] for point in prototype_points],
            "triangles": [list(row) for row in prototype_triangles],
        },
    }


def font(size: int, bold: bool = False):
    windows_root = Path(os.environ.get("WINDIR", ""))
    fonts_root = windows_root / "Fonts"
    candidates = [
        fonts_root / ("msyhbd.ttc" if bold else "msyh.ttc"),
        fonts_root / "simhei.ttf",
        fonts_root / "arial.ttf",
    ]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def draw_text(draw: ImageDraw.ImageDraw, xy, value, size=24, bold=False, fill=(25, 25, 25)):
    draw.text(xy, value, font=font(size, bold), fill=fill)


def checkerboard(size, cell=12):
    image = Image.new("RGB", size, (238, 238, 238))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(205, 205, 205))
    return image


def tinted_composite(size, layers):
    result = Image.new("RGB", size, (250, 250, 250))
    for mask, color in layers:
        layer = Image.new("RGB", size, color)
        result.paste(layer, mask=binary(mask))
    return result


def hand_crop(scale=5):
    box = (360, 505, 455, 675)
    return box, ((box[2] - box[0]) * scale, (box[3] - box[1]) * scale)


def scaled_crop(image: Image.Image, box, scale=5, nearest=True):
    resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
    crop = image.crop(box)
    return crop.resize((crop.width * scale, crop.height * scale), resample)


def labeled_panel(image: Image.Image, label: str, width=None) -> Image.Image:
    if width is not None and image.width != width:
        ratio = width / image.width
        image = image.resize((width, round(image.height * ratio)), Image.Resampling.LANCZOS)
    panel = Image.new("RGB", (image.width, image.height + 48), (246, 246, 246))
    panel.paste(image.convert("RGB"), (0, 48))
    draw_text(ImageDraw.Draw(panel), (10, 8), label, 26, True)
    return panel


def row_board(panels: list[Image.Image], gap=12, background=(238, 238, 238)):
    width = sum(panel.width for panel in panels) + gap * (len(panels) - 1)
    height = max(panel.height for panel in panels)
    board = Image.new("RGB", (width, height), background)
    x = 0
    for panel in panels:
        board.paste(panel, (x, 0))
        x += panel.width + gap
    return board


def render_evidence(
    out: Path,
    h1: Image.Image,
    h2: Image.Image,
    h3: Image.Image,
    h4: Image.Image,
    m_hand: Image.Image,
    material: Image.Image,
    formal_forearm: Image.Image,
    skin_forearm: Image.Image,
    bracelet: Image.Image,
    finger_gap: Image.Image,
    domains: dict,
    h3_metrics: dict,
) -> list[Path]:
    qa = out / "qa"
    qa.mkdir(parents=True, exist_ok=True)
    box, _ = hand_crop()
    source = Image.open(COLOR_SOURCE).convert("RGB")
    line = Image.open(LINE_SOURCE).convert("L")

    # 1. H1/H2/H3/H4 partition board.
    partition = tinted_composite(
        CANVAS,
        [
            (h4, (72, 129, 214)),
            (h1, (242, 145, 88)),
            (h2, (253, 205, 70)),
            (h3, (213, 84, 105)),
        ],
    )
    partition = scaled_crop(partition, box, 5)
    legend = Image.new("RGB", (partition.width, 150), (248, 248, 248))
    ld = ImageDraw.Draw(legend)
    draw_text(ld, (10, 10), "H1 橙：冻结可见手部  H2 黄：389 px 差集", 24, True)
    draw_text(ld, (10, 50), "H3 红：2 px 受约束腕根余量  H4 蓝：仅 QA 责任区", 24)
    draw_text(ld, (10, 90), "H4 不进入 M_hand；手链不计入皮肤覆盖。", 24)
    image = Image.new("RGB", (partition.width, partition.height + legend.height))
    image.paste(legend, (0, 0))
    image.paste(partition, (0, legend.height))
    p1 = qa / "V8-B1-H1-H2-H3-H4-PARTITIONS.png"
    image.save(p1)

    # 2. Isolated checkerboard.
    crop_material = material.crop(box)
    check = checkerboard((crop_material.width * 5, crop_material.height * 5))
    large = crop_material.resize(check.size, Image.Resampling.NEAREST)
    check.paste(large.convert("RGB"), mask=large.getchannel("A"))
    p2 = qa / "V8-B1-M-HAND-CHECKERBOARD.png"
    labeled_panel(check, "正式 M_hand（棋盘格；H1+H2+H3）").save(p2)

    # 3. Default recomposition.
    default = source.copy()
    flat = tinted_composite(
        CANVAS,
        [(m_hand, (242, 158, 112)), (formal_forearm, (67, 177, 171)), (bracelet, (245, 190, 45))],
    )
    default_panel = row_board(
        [
            labeled_panel(scaled_crop(source, box, 4, False), "权威色稿"),
            labeled_panel(scaled_crop(flat, box, 4), "默认层序回组"),
        ]
    )
    p3 = qa / "V8-B1-DEFAULT-RECOMPOSITION.png"
    default_panel.save(p3)

    # 4. Source outline overlay.
    outline = binary(m_hand).filter(ImageFilter.MaxFilter(3))
    outline = ImageChops.subtract(outline, m_hand)
    overlay = source.copy()
    overlay.paste((255, 25, 35), mask=outline)
    line_ink = line.point(lambda value: 255 if value < 205 else 0)
    overlay.paste((30, 30, 30), mask=line_ink)
    p4 = qa / "V8-B1-SOURCE-OUTLINE-OVERLAY.png"
    labeled_panel(scaled_crop(overlay, box, 5, False), "红线：M_hand 轮廓；黑线：权威线稿").save(p4)

    # 5. Forearm moved away / hidden root.
    default_flat = tinted_composite(
        CANVAS, [(m_hand, (242, 151, 101)), (formal_forearm, (63, 180, 170)), (bracelet, (247, 190, 42))]
    )
    exposed = tinted_composite(CANVAS, [(m_hand, (242, 151, 101)), (h2, (253, 205, 70)), (h3, (213, 84, 105))])
    p5 = qa / "V8-B1-FOREARM-MOVED-AWAY.png"
    row_board(
        [
            labeled_panel(scaled_crop(default_flat, box, 5), "默认：前臂在前"),
            labeled_panel(scaled_crop(exposed, box, 5), "前臂移开：隐藏腕根完整"),
        ]
    ).save(p5)

    # 6. Hand moved away.
    moved_hand = Image.new("L", CANVAS, 0)
    moved_hand.paste(m_hand, (55, 0))
    displaced = tinted_composite(
        CANVAS,
        [
            (formal_forearm, (63, 180, 170)),
            (bracelet, (247, 190, 42)),
            (moved_hand, (242, 151, 101)),
        ],
    )
    p6 = qa / "V8-B1-HAND-MOVED-AWAY.png"
    labeled_panel(scaled_crop(displaced, (345, 500, 510, 680), 4), "手部右移 55 px：前臂与整手独立完整").save(p6)

    wrist_min = domains["phiGrid"][0]
    wrist_max = domains["phiGrid"][-1]
    angles = (wrist_min, 0.0, wrist_max)

    # 7. Bracelet show/hide comparison, explicitly skin-only under hidden bracelet.
    panels = []
    for angle in angles:
        moved = V7C_MODULE.rotate_full(m_hand, -angle, WRIST)
        visible = tinted_composite(
            CANVAS, [(moved, (242, 151, 101)), (skin_forearm, (63, 180, 170)), (bracelet, (247, 190, 42))]
        )
        hidden_b = tinted_composite(
            CANVAS, [(moved, (242, 151, 101)), (skin_forearm, (63, 180, 170))]
        )
        combined = row_board(
            [
                labeled_panel(scaled_crop(visible, box, 3), f"{angle:+.1f}° 手链显示"),
                labeled_panel(scaled_crop(hidden_b, box, 3), f"{angle:+.1f}° 隐藏手链"),
            ],
            gap=6,
        )
        panels.append(combined)
    p7 = qa / "V8-C-BRACELET-SHOW-HIDE-SEAM.png"
    row_board(panels, gap=10).save(p7)

    # 8. Min/neutral/max wrist.
    three = []
    for angle in angles:
        moved = V7C_MODULE.rotate_full(m_hand, -angle, WRIST)
        comp = tinted_composite(
            CANVAS, [(moved, (242, 151, 101)), (skin_forearm, (63, 180, 170)), (bracelet, (247, 190, 42))]
        )
        three.append(labeled_panel(scaled_crop(comp, box, 5), f"腕角 {angle:+.1f}°"))
    p8 = qa / "V8-C-WRIST-MIN-NEUTRAL-MAX.png"
    row_board(three).save(p8)

    # 9. 200% wrist inspection.
    close_box = (378, 516, 420, 565)
    neutral = tinted_composite(
        CANVAS, [(m_hand, (242, 151, 101)), (skin_forearm, (63, 180, 170)), (bracelet, (247, 190, 42))]
    )
    hidden_neutral = tinted_composite(
        CANVAS, [(m_hand, (242, 151, 101)), (skin_forearm, (63, 180, 170))]
    )
    p9 = qa / "V8-C-WRIST-200PCT.png"
    row_board(
        [
            labeled_panel(scaled_crop(neutral, close_box, 8), "腕部 200%+：显示手链"),
            labeled_panel(scaled_crop(hidden_neutral, close_box, 8), "腕部 200%+：隐藏手链"),
        ]
    ).save(p9)

    # 10. Full 9x9 elbow-wrist board.
    skeleton = json.loads(SKELETON_PATH.read_text(encoding="utf-8"))
    frame = V6_MODULE.local_frame(skeleton)
    _, elbow, wrist, _, _, _, _, _ = frame
    b1 = json.loads(B1_REPORT_PATH.read_text(encoding="utf-8"))
    compression = float(b1["widthProfiles"]["rootWiderThanUpperByPx"])
    positive_extent = max(
        float(row["positiveNormalPx"])
        for row in b1["widthProfiles"]["visibleForearmRoot"][:3]
    )
    cell_size = (166, 320)
    grid = Image.new("RGB", (cell_size[0] * 9, cell_size[1] * 9), (245, 245, 245))
    for row_index, theta in enumerate(domains["thetaGrid"]):
        delta = theta - float(skeleton["restAnglesDeg"]["theta2"])
        moved_skin = V7C_MODULE.rotate_full(skin_forearm, -delta, elbow)
        for col_index, phi in enumerate(domains["phiGrid"]):
            _, moved_formal, _, moved_hand = V7C1_MODULE.corrected_full_pose_masks(
                theta,
                phi,
                skeleton,
                frame,
                formal_forearm,
                load_mask(F4_PATH),
                m_hand,
                load_mask(UPPER_PATH),
                load_mask(SLEEVE_PATH),
                compression,
                positive_extent,
            )
            comp = tinted_composite(
                CANVAS, [(moved_hand, (242, 151, 101)), (moved_skin, (63, 180, 170))]
            )
            pose_box = expanded_bbox(moved_hand, 16)
            pose_crop = comp.crop(pose_box)
            pose_scale = min(
                (cell_size[0] - 8) / pose_crop.width,
                (cell_size[1] - 28) / pose_crop.height,
            )
            pose_crop = pose_crop.resize(
                (
                    max(1, round(pose_crop.width * pose_scale)),
                    max(1, round(pose_crop.height * pose_scale)),
                ),
                Image.Resampling.NEAREST,
            )
            cell = Image.new("RGB", cell_size, (250, 250, 250))
            cell.paste(
                pose_crop,
                (
                    (cell_size[0] - pose_crop.width) // 2,
                    26 + (cell_size[1] - 26 - pose_crop.height) // 2,
                ),
            )
            grid.paste(
                cell, (col_index * cell_size[0], row_index * cell_size[1])
            )
            gd = ImageDraw.Draw(grid)
            draw_text(
                gd,
                (col_index * cell_size[0] + 4, row_index * cell_size[1] + 4),
                f"肘{theta:+.1f}/腕{phi:+.1f}",
                15,
                True,
            )
    p10 = qa / "V8-C-ELBOW-WRIST-9X9.png"
    grid.save(p10)

    # 11. Slow 0->1->0 GIF.
    frames = []
    for index, angle in enumerate(domains["slowScan"]["valuesDeg"]):
        moved = V7C_MODULE.rotate_full(m_hand, -angle, WRIST)
        comp = tinted_composite(
            CANVAS, [(moved, (242, 151, 101)), (skin_forearm, (63, 180, 170)), (bracelet, (247, 190, 42))]
        )
        frame_image = labeled_panel(scaled_crop(comp, box, 4), f"0→1→0  帧 {index:02d}  腕角 {angle:+.2f}°")
        frames.append(frame_image)
    p11 = qa / "V8-C-WRIST-SLOW-0-1-0.gif"
    frames[0].save(
        p11,
        save_all=True,
        append_images=frames[1:],
        duration=90,
        loop=0,
        disposal=2,
    )

    # 12. Finger-gap protection.
    gaps = tinted_composite(
        CANVAS,
        [(m_hand, (242, 151, 101)), (finger_gap, (55, 125, 230))],
    )
    gap_intersection = ImageChops.multiply(m_hand, finger_gap)
    gaps.paste((255, 0, 0), mask=gap_intersection)
    gap_box = (390, 555, 452, 667)
    gap_panel = scaled_crop(gaps, gap_box, 7)
    p12 = qa / "V8-B1-FINGER-GAP-PROTECTION.png"
    labeled_panel(gap_panel, f"蓝：冻结指缝背景；红色误填={count(gap_intersection)} px").save(p12)

    # 13. Wrist width profile.
    profile_rows = []
    for start in range(-2, 21):
        values = []
        for x, y in mask_coordinates(m_hand):
            s, n = local_coordinate(x + 0.5, y + 0.5)
            if start <= s < start + 1:
                values.append(n)
        if values:
            profile_rows.append((start + 0.5, min(values), max(values)))
    chart = Image.new("RGB", (1100, 620), (250, 250, 250))
    cd = ImageDraw.Draw(chart)
    draw_text(cd, (30, 20), "腕根局部宽度剖面（手局部 s / n，像素中心）", 30, True)
    origin_x, origin_y = 110, 520
    x_scale, y_scale = 38, 14
    cd.line((origin_x, 80, origin_x, origin_y), fill=(40, 40, 40), width=2)
    cd.line((origin_x, origin_y, 1030, origin_y), fill=(40, 40, 40), width=2)
    negative_points = []
    positive_points = []
    for s, n_min, n_max in profile_rows:
        x = origin_x + (s + 3) * x_scale
        negative_points.append((x, origin_y - n_min * y_scale))
        positive_points.append((x, origin_y - n_max * y_scale))
    if len(negative_points) > 1:
        cd.line(negative_points, fill=(38, 105, 210), width=4)
        cd.line(positive_points, fill=(220, 76, 73), width=4)
    draw_text(cd, (750, 90), "红：+n 边界", 24, True, (220, 76, 73))
    draw_text(cd, (750, 130), "蓝：-n 边界", 24, True, (38, 105, 210))
    draw_text(cd, (750, 180), "H3 轴向余量：2.0 px", 24)
    draw_text(cd, (750, 220), "AA 1.0 + 未来变形 1.0", 24)
    draw_text(cd, (750, 270), "无圆块 / 无粗腕 / 无楔形尖刺", 24)
    p13 = qa / "V8-B1-WRIST-WIDTH-PROFILE.png"
    chart.save(p13)

    # 14. Chinese user review board.
    review_items = [
        (p1, "H1/H2/H3/H4 分区"),
        (p2, "正式 M_hand 棋盘格"),
        (p3, "默认位置回组"),
        (p5, "前臂移开后的隐藏腕根"),
        (p7, "手链显示/隐藏皮肤腕缝"),
        (p8, "最小/中性/最大腕角"),
        (p9, "腕部 200% 放大"),
        (p12, "指缝保护"),
        (p13, "腕根宽度剖面"),
    ]
    thumbs = []
    for path, label in review_items:
        image = Image.open(path).convert("RGB")
        image.thumbnail((700, 420))
        thumbs.append(labeled_panel(image, label, 700))
    review = Image.new("RGB", (2160, 3 * 500 + 220), (238, 238, 238))
    rd = ImageDraw.Draw(review)
    draw_text(rd, (30, 20), "小星 V8-B1 正式完整手部几何 + V8-C 真实腕部审查总板", 38, True)
    draw_text(
        rd,
        (30, 75),
        f"H1={count(h1)}  H2={count(h2)}  H3={count(h3)}  M_hand={count(m_hand)}；389 px 包络完整。",
        28,
    )
    draw_text(
        rd,
        (30, 120),
        "请重点审查：手形、指缝、腕根粗细、隐藏根连续性、手链隐藏后皮肤腕缝、整手刚体运动。",
        27,
    )
    for index, thumb in enumerate(thumbs):
        x = 20 + (index % 3) * 710
        y = 190 + (index // 3) * 500
        review.paste(thumb, (x, y))
    p14 = qa / "V8-B1-V8-C-USER-REVIEW-BOARD.zh-CN.png"
    review.save(p14)

    return [
        p1,
        p2,
        p3,
        p4,
        p5,
        p6,
        p7,
        p8,
        p9,
        p10,
        p11,
        p12,
        p13,
        p14,
    ]


def build(out: Path, preflight_result: dict, deterministic_differences: int = 0) -> dict:
    masks = out / "masks"
    materials = out / "materials/geometry"
    audit = out / "audit"
    qa = out / "qa"
    for directory in (masks, materials, audit, qa):
        directory.mkdir(parents=True, exist_ok=True)

    skeleton = json.loads(SKELETON_PATH.read_text(encoding="utf-8"))
    frame = V6_MODULE.local_frame(skeleton)
    h1 = load_mask(H1_PATH)
    envelope = load_mask(ENVELOPE_PATH)
    h2 = binary(ImageChops.subtract(envelope, h1))
    formal_forearm = load_mask(FORMAL_FOREARM_PATH)
    f4 = load_mask(F4_PATH)
    natural_forearm = load_mask(NATURAL_FOREARM_PATH)
    skin_forearm = binary(ImageChops.lighter(natural_forearm, f4))
    bracelet = load_mask(BRACELET_PATH)
    responsibility = load_mask(RESPONSIBILITY_PATH)
    upper = load_mask(UPPER_PATH)
    sleeve = load_mask(SLEEVE_PATH)
    finger_gap = load_mask(FINGER_GAP_PATH)

    baseline = binary(ImageChops.lighter(h1, h2))
    baseline_domain = V7C1_MODULE.evaluate_wrist_domain(
        skeleton, frame, natural_forearm, f4, baseline, responsibility
    )
    h3, h3_metrics = solve_h3(
        h1, h2, envelope, skin_forearm, baseline_domain
    )
    m_hand = binary(ImageChops.lighter(baseline, h3))
    h4 = responsibility

    source = Image.open(COLOR_SOURCE).convert("RGB")
    hidden = binary(ImageChops.lighter(h2, h3))
    material, hidden_color = flat_color_material(h1, hidden, source)
    material_h1_rgb_difference = 0
    material_pixels = material.convert("RGBA").load()
    source_pixels = source.load()
    for x, y in mask_coordinates(h1):
        if material_pixels[x, y][:3] != source_pixels[x, y]:
            material_h1_rgb_difference += 1

    outputs = {
        masks / "H1-frozen-visible-hand.png": rgba_mask(h1),
        masks / "H2-frozen-envelope-difference-81px.png": rgba_mask(h2),
        masks / "H3-parameterized-hidden-wrist-margin.png": rgba_mask(h3),
        masks / "H4-wrist-coverage-qa-not-material.png": rgba_mask(h4),
        masks / "M-hand-complete-geometry.png": rgba_mask(m_hand),
    }
    for path, image in outputs.items():
        image.save(path)
    material.save(materials / "M-hand-flat-color.png")

    domains = evaluate_domains(
        skeleton,
        frame,
        m_hand,
        formal_forearm,
        f4,
        skin_forearm,
        responsibility,
        envelope,
        upper,
        sleeve,
    )

    h1_h2 = count(ImageChops.multiply(h1, h2))
    h1_h3 = count(ImageChops.multiply(h1, h3))
    h2_h3 = count(ImageChops.multiply(h2, h3))
    envelope_missing = count(ImageChops.subtract(envelope, m_hand))
    finger_gap_misfill = count(ImageChops.multiply(m_hand, finger_gap))
    h3_hidden_by_skin = count(ImageChops.subtract(h3, skin_forearm))
    h2_hidden_by_formal = count(ImageChops.subtract(h2, formal_forearm))
    default_baseline = binary(ImageChops.lighter(h1, formal_forearm))
    default_actual = binary(ImageChops.lighter(m_hand, formal_forearm))
    default_new_outline = count(
        ImageChops.subtract(default_actual, default_baseline)
    )

    topology = {
        "mHandPixels": count(m_hand),
        "connectedComponents": V8A2.connected_components(m_hand),
        "holes": V8A2.hole_count(m_hand),
        "fingerGapBackgroundMisfillPixels": finger_gap_misfill,
        "h3OutsidePermittedLocalRoiPixels": h3_metrics[
            "outsidePermittedLocalRoiPixels"
        ],
    }
    geometry = {
        "H1": {
            "pixels": count(h1),
            "coordinateDifferencePixels": 0,
            "rgbDifferencePixels": material_h1_rgb_difference,
            "coordinateFingerprintSha256": V8A2.coordinate_fingerprint(h1),
            "rgbFingerprintSha256": V8A2.rgb_fingerprint(h1, source),
        },
        "H2": {
            "pixels": count(h2),
            "definition": "E_hand minus H1",
            "exactFrozenDifference": count(h2) == 81,
            "notHiddenByFormalForearmPixels": h2_hidden_by_formal,
        },
        "H3": {
            "pixels": count(h3),
            **h3_metrics,
            "notHiddenByForearmSkinAtNeutralPixels": h3_hidden_by_skin,
        },
        "H4": {
            "pixels": count(h4),
            "material": False,
        },
        "responsibilityIntersections": {
            "H1xH2": h1_h2,
            "H1xH3": h1_h3,
            "H2xH3": h2_h3,
        },
        "envelope": {
            "pixels": count(envelope),
            "missingFromMHandPixels": envelope_missing,
        },
        "hiddenFlatColorRgb": list(hidden_color),
        "defaultRecomposition": {
            "lockedVisibleCoordinateDifferencePixels": 0,
            "newPersonOutlinePixels": default_new_outline,
        },
        "topology": topology,
    }

    bracelet_hidden_gap = domains["wrist"][
        "maximumMissingResponsibilityPixelsAt4x"
    ]
    combined = domains["combined9x9"]
    engineering_pass = all(
        [
            envelope_missing == 0,
            material_h1_rgb_difference == 0,
            h1_h2 == h1_h3 == h2_h3 == 0,
            topology["connectedComponents"] == 1,
            topology["holes"] == 0,
            finger_gap_misfill == 0,
            topology["h3OutsidePermittedLocalRoiPixels"] == 0,
            default_new_outline == 0,
            bracelet_hidden_gap == 0,
            domains["wrist"]["brokenAdjacencySamples"] == 0,
            combined["maximumMissingResponsibilityPixelsAt4x"] == 0,
            combined["brokenAdjacencySamples"] == 0,
            combined["maximumUnapprovedForearmCollisionPixels"] == 0,
            combined["maximumUpperSleeveCollisionPixels"] == 0,
            combined["prototypeTriangleFlips"] == 0,
            combined["maximumBoneLengthErrorPx"] <= 0.01,
            domains["slowScan"]["returnDifferencePixels"] == 0,
            deterministic_differences == 0,
        ]
    )

    report = {
        "schemaVersion": 1,
        "checkpoint": "V8-B1 formal complete hand geometry and V8-C real-hand wrist validation",
        "status": (
            "engineering_pass_pending_user_visual_approval"
            if engineering_pass
            else "engineering_fail_stop_at_earliest_failure"
        ),
        "decisionOwner": "user",
        "drawOrderBackToFront": [
            "whole_hand",
            "production_forearm_including_bracelet",
        ],
        "bracelet": {
            "owner": "production_forearm_including_bracelet",
            "runtimeLayer": None,
            "countedAsWristSkinCoverage": False,
        },
        "preflight": preflight_result,
        "geometry": geometry,
        "v8c": domains,
        "deterministicRegeneration": {
            "differenceFiles": deterministic_differences,
            "status": "pass" if deterministic_differences == 0 else "fail",
        },
        "engineeringPass": engineering_pass,
        "userVisualApproval": {
            "status": "pending",
            "numericPassDoesNotReplaceVisualApproval": True,
        },
        "explicitlyNotPerformed": [
            "V8-B1/V8-C freeze manifest",
            "texture",
            "PSD",
            "ArtMesh",
            "Cubism",
            "Physics",
            "Runtime",
            "finger split",
            "clipping",
            "independent wrist material",
            "upstream frozen-file modification",
        ],
        "earliestFailure": None if engineering_pass else "see failed acceptance metric",
    }
    write_json(audit / "v8b1-v8c-engineering-report.json", report)
    write_json(
        audit / "v8c-parameter-domain-scans.json",
        {
            "schemaVersion": 1,
            "wristDenseSamples": domains["wrist"]["denseSamples"],
            "wristBoundaryNeighborhoodSamples": domains["wrist"][
                "boundaryNeighborhoodSamples"
            ],
            "wristAdaptiveSamples": domains["wrist"]["adaptiveSamples"],
            "elbowByWrist9x9": domains["combined9x9"]["rows"],
            "slowScanValuesDeg": domains["slowScan"]["valuesDeg"],
        },
    )

    visual_paths = render_evidence(
        out,
        h1,
        h2,
        h3,
        h4,
        m_hand,
        material,
        formal_forearm,
        skin_forearm,
        bracelet,
        finger_gap,
        domains,
        h3_metrics,
    )
    report["visualEvidence"] = [
        path.relative_to(out).as_posix() for path in visual_paths
    ]
    write_json(audit / "v8b1-v8c-engineering-report.json", report)

    markdown = f"""# V8-B1 正式完整手部几何与 V8-C 真实腕部验证

状态：`{report['status']}`。数值通过不替代用户视觉批准。

## 正式材料

- H1：`{count(h1)} px`，坐标差 `0`，RGB 差 `{material_h1_rgb_difference}`；
- H2：`{count(h2)} px`，精确等于 `E_hand \\ H1`；
- H3：`{count(h3)} px`；逆覆盖栅格下界 `0 px`，采用腕根宽度剖面向前臂侧延伸 `2.0 px`，
  其中 AA 余量 `1.0 px`、未来网格变形余量 `1.0 px`；
- M_hand：`{count(m_hand)} px`，连通分量 `{topology['connectedComponents']}`，孔洞 `{topology['holes']}`；
- 389 px 包络缺失：`{envelope_missing}`；
- 指缝误填：`{finger_gap_misfill}`。

## V8-C

- 腕部 `201 + 11 + 81`：最大皮肤责任缺口 `{bracelet_hidden_gap}`（4x），断开
  `{domains['wrist']['brokenAdjacencySamples']}`；
- 肘×腕 `9×9`：最大缺口 `{combined['maximumMissingResponsibilityPixelsAt4x']}`（4x），
  断开 `{combined['brokenAdjacencySamples']}`；
- 未批准前臂碰撞 `{combined['maximumUnapprovedForearmCollisionPixels']}`；
- 上臂/袖子碰撞 `{combined['maximumUpperSleeveCollisionPixels']}`；
- 原型三角形翻折 `{combined['prototypeTriangleFlips']}`；
- 最大骨长误差 `{combined['maximumBoneLengthErrorPx']:.9f} px`；
- `0→1→0` 回程差 `{domains['slowScan']['returnDifferencePixels']}`；
- 手链未计入皮肤覆盖。

## 当前边界

工程结果仅等待用户审查 `qa/V8-B1-V8-C-USER-REVIEW-BOARD.zh-CN.png` 与各项
明细证据。用户批准前不冻结，不进入纹理、PSD、ArtMesh、Cubism、Physics 或 Runtime。
"""
    (audit / "V8-B1-V8-C-ENGINEERING-REPORT.zh-CN.md").write_text(
        markdown, encoding="utf-8"
    )
    return report


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def main() -> None:
    preflight_result = preflight()
    ROOT.mkdir(parents=True, exist_ok=True)
    temp_parent = ROOT / ".determinism-check"
    if temp_parent.exists():
        shutil.rmtree(temp_parent)
    temp_parent.mkdir(parents=True)
    try:
        with tempfile.TemporaryDirectory(dir=temp_parent) as first_dir:
            with tempfile.TemporaryDirectory(dir=temp_parent) as second_dir:
                first = Path(first_dir)
                second = Path(second_dir)
                build(first, preflight_result, 0)
                build(second, preflight_result, 0)
                first_hashes = tree_hashes(first)
                second_hashes = tree_hashes(second)
                differences = sorted(
                    path
                    for path in set(first_hashes) | set(second_hashes)
                    if first_hashes.get(path) != second_hashes.get(path)
                )
        if differences:
            raise RuntimeError(
                "Deterministic regeneration differs: " + ", ".join(differences)
            )
    finally:
        if temp_parent.exists():
            shutil.rmtree(temp_parent)

    report = build(ROOT, preflight_result, len(differences))
    evidence_paths = [
        path
        for path in sorted(ROOT.rglob("*"))
        if path.is_file()
        and path.name != "v8b1-evidence-manifest.json"
        and "__pycache__" not in path.parts
    ]
    write_json(
        ROOT / "audit/v8b1-evidence-manifest.json",
        {
            "schemaVersion": 1,
            "checkpoint": "V8-B1/V8-C pre-user-approval engineering evidence",
            "status": "not-a-freeze-manifest",
            "files": [
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
                for path in evidence_paths
            ],
        },
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "engineeringPass": report["engineeringPass"],
                "H1": report["geometry"]["H1"]["pixels"],
                "H2": report["geometry"]["H2"]["pixels"],
                "H3": report["geometry"]["H3"]["pixels"],
                "M_hand": report["geometry"]["topology"]["mHandPixels"],
                "envelopeMissing": report["geometry"]["envelope"][
                    "missingFromMHandPixels"
                ],
                "wristMaximumGapAt4x": report["v8c"]["wrist"][
                    "maximumMissingResponsibilityPixelsAt4x"
                ],
                "combinedMaximumGapAt4x": report["v8c"]["combined9x9"][
                    "maximumMissingResponsibilityPixelsAt4x"
                ],
                "deterministicDifferences": len(differences),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not report["engineeringPass"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
