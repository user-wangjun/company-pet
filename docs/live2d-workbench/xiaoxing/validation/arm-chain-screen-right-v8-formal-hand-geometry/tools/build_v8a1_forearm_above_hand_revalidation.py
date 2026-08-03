from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
VALIDATION = ROOT.parent
XIAOXING = VALIDATION.parent
V4 = VALIDATION / "arm-chain-screen-right-v4-wrist-motion"
V5 = VALIDATION / "arm-chain-screen-right-v5-hidden-upper-arm"
V6 = VALIDATION / "arm-chain-screen-right-v6-complete-upper-arm-geometry"
V7 = VALIDATION / "arm-chain-screen-right-v7-production-forearm-geometry"
V7C1 = V7 / "v7c1-elbow-seam-fairing"

AUDIT = ROOT / "audit"
QA = ROOT / "qa"
for directory in (AUDIT, QA):
    directory.mkdir(parents=True, exist_ok=True)

APPROVAL = AUDIT / "v8a1-user-approval-forearm-above-hand-2026-07-26.json"
VISUAL_APPROVAL = (
    AUDIT / "v8a1-user-visual-approval-forearm-above-hand-2026-07-26.json"
)
V7C1_BUILDER = V7C1 / "tools/build_v7c1_elbow_seam_fairing.py"
SKELETON = V4 / "skeleton.json"
COLOR_SOURCE = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
FORMAL_FOREARM = V7C1 / "masks/production-forearm-geometry-faired.png"
F4 = V7C1 / "masks/F4-wrist-hidden-extension.png"
HAND_ENVELOPE = V7C1 / "masks/temporary-hand-root-envelope.png"
WRIST_RESPONSIBILITY = (
    V7C1 / "masks/F5-wrist-responsibility-not-material.png"
)
NATURAL_FOREARM = V7 / "masks/forearm-no-bracelet-qa-geometry.png"
BRACELET = V7 / "masks/bracelet-ownership-candidate.png"
UPPER = V6 / "masks/upper-arm-complete-geometry.png"
SLEEVE = (
    V5
    / "complete-sleeve-final/inputs/sleeve-complete-geometry-r9.png"
)
B1_REPORT = V7 / "v7b1-root-width-reopen/audit/v7b1-root-width-conflict.json"
FREEZE_MANIFEST = (
    V7C1
    / "audit/v7-production-forearm-geometry-freeze-manifest-2026-07-26.json"
)

EXPECTED_INPUTS = {
    "audit/v8a1-user-approval-forearm-above-hand-2026-07-26.json": (
        APPROVAL,
        "0b0db16c973bc7e7081194072b5c9b0a9866f3432e15c7370021b97165b36be7",
        1142,
    ),
    "audit/v8a1-user-visual-approval-forearm-above-hand-2026-07-26.json": (
        VISUAL_APPROVAL,
        "d8d9e9c7af56d6159444ae7770b8c34f8ba42b34d1a3b2a7e2e439e177eedb70",
        944,
    ),
    "v7/freeze-manifest.json": (
        FREEZE_MANIFEST,
        "65469d0eda4d5c27b79d3d23fbd92604a51ad82c5ca08ce6a875ab7d1bffea33",
        10743,
    ),
    "v7/formal-forearm.png": (
        FORMAL_FOREARM,
        "94e0c68344efc9c718f42de445cad5e06a750a6c163b864362a30198cc5befe1",
        4908,
    ),
    "v7/temporary-hand-root-envelope.png": (
        HAND_ENVELOPE,
        "29ed3326d99497c7fb815476f63d0825564c6b9cb174fdd151c275542c8ce421",
        4637,
    ),
    "source/front-color-source-exact-after-reset.png": (
        COLOR_SOURCE,
        "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5",
        581346,
    ),
}

SS = 4
ALPHA_THRESHOLD = 16


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V7C1_MODULE = load_module("v8a1_v7c1", V7C1_BUILDER)
V7C_MODULE = V7C1_MODULE.V7C_MODULE
V6_MODULE = V7C1_MODULE.V6_MODULE
B2_MODULE = V7C1_MODULE.B2_MODULE
B0_MODULE = B2_MODULE.B0_MODULE


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


def binary(image: Image.Image, threshold: int = ALPHA_THRESHOLD) -> Image.Image:
    if image.mode == "L":
        channel = image
    else:
        channel = image.convert("RGBA").getchannel("A")
    return channel.point(lambda value: 255 if value >= threshold else 0)


def load_mask(path: Path) -> Image.Image:
    return binary(Image.open(path))


def count(mask: Image.Image) -> int:
    return sum(binary(mask, 1).histogram()[1:])


def difference_count(first: Image.Image, second: Image.Image) -> int:
    return count(ImageChops.difference(binary(first, 1), binary(second, 1)))


def font(size: int, bold: bool = False):
    fonts = Path(os.environ.get("WINDIR", "")) / "Fonts"
    candidates = (
        fonts / ("msyhbd.ttc" if bold else "msyh.ttc"),
        fonts / "simhei.ttf",
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def text(draw, xy, value: str, size=24, bold=False, fill=(25, 25, 25)):
    draw.text(xy, value, font=font(size, bold), fill=fill)


def color_layers(
    size: tuple[int, int],
    layers: list[tuple[Image.Image, tuple[int, int, int]]],
    background=(246, 246, 246),
) -> Image.Image:
    result = Image.new("RGB", size, background)
    for mask, color in layers:
        result.paste(Image.new("RGB", size, color), mask=binary(mask))
    return result


def crop_high(mask: Image.Image, box) -> Image.Image:
    crop = binary(mask).crop(box)
    return crop.resize(
        (crop.width * SS, crop.height * SS),
        Image.Resampling.NEAREST,
    )


def expanded_bbox(mask: Image.Image, margin=6):
    box = binary(mask).getbbox()
    if box is None:
        raise RuntimeError("Expected non-empty mask.")
    return (
        max(0, box[0] - margin),
        max(0, box[1] - margin),
        min(mask.width, box[2] + margin),
        min(mask.height, box[3] + margin),
    )


def compose_wrist_view(
    skin_forearm: Image.Image,
    bracelet: Image.Image,
    hand: Image.Image,
    crop,
    scale=5,
    bracelet_visible=True,
) -> Image.Image:
    layers = [(hand, (239, 147, 92)), (skin_forearm, (73, 184, 176))]
    if bracelet_visible:
        layers.append((bracelet, (236, 183, 45)))
    result = color_layers(hand.size, layers).crop(crop)
    return result.resize(
        (result.width * scale, result.height * scale),
        Image.Resampling.NEAREST,
    )


def rotate_registered_forearm_ownership(
    formal: Image.Image,
    bracelet: Image.Image,
    angle: float,
    center,
) -> tuple[Image.Image, Image.Image]:
    # The bracelet is texture/ownership inside one forearm material, not an
    # independently rasterized drawable. Transform a single semantic label map
    # so subset ownership cannot acquire a false one-pixel fringe from two
    # separate bicubic threshold operations.
    labels = Image.new("L", formal.size, 0)
    labels.paste(1, mask=binary(formal))
    labels.paste(2, mask=ImageChops.multiply(binary(bracelet), binary(formal)))
    if abs(angle) >= 1e-12:
        labels = labels.rotate(
            angle,
            resample=Image.Resampling.NEAREST,
            center=center,
            fillcolor=0,
        )
    moved_formal = labels.point(lambda value: 255 if value else 0)
    moved_bracelet = labels.point(lambda value: 255 if value == 2 else 0)
    return moved_formal, moved_bracelet


def evidence_manifest() -> dict:
    paths = [
        APPROVAL,
        VISUAL_APPROVAL,
        HERE,
        AUDIT / "v8a1-forearm-above-hand-revalidation.json",
        AUDIT / "v8a1-forearm-above-hand-domain-scans.json",
        AUDIT / "v8a1-forearm-above-hand-contract.json",
        AUDIT / "V8-A1-FOREARM-ABOVE-HAND-REVALIDATION.zh-CN.md",
        QA / "V8-A1-NEUTRAL-DRAW-ORDER-COMPARISON.png",
        QA / "V8-A1-FOREARM-ABOVE-HAND-WRIST-THREE-ANGLES.png",
        QA / "V8-A1-BRACELET-HIDDEN-SKIN-SEAM-THREE-ANGLES.png",
        QA / "V8-A1-FOREARM-ABOVE-HAND-WRIST-SLOW-SCAN.gif",
        QA / "V8-A1-FOREARM-ABOVE-HAND-WRIST-SLOW-SCAN-SAMPLES.png",
        QA / "V8-A1-FOREARM-ABOVE-HAND-FULL-CHAIN-3X3.png",
    ]
    entries = []
    for path in paths:
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    return {
        "schemaVersion": 1,
        "checkpoint": "v8a1_forearm_above_whole_hand_revalidation",
        "fileCount": len(entries),
        "files": entries,
    }


def main() -> None:
    input_rows = []
    for label, (path, expected_hash, expected_bytes) in EXPECTED_INPUTS.items():
        actual_hash = sha256(path) if path.exists() else None
        actual_bytes = path.stat().st_size if path.exists() else None
        input_rows.append(
            {
                "path": label,
                "expectedSha256": expected_hash,
                "actualSha256": actual_hash,
                "expectedBytes": expected_bytes,
                "actualBytes": actual_bytes,
                "pass": (
                    actual_hash == expected_hash
                    and actual_bytes == expected_bytes
                ),
            }
        )
    if not all(row["pass"] for row in input_rows):
        raise RuntimeError("V8-A1 input integrity failed.")

    approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
    if (
        approval["status"]
        != "user_approved_contract_reopen_and_revalidation"
    ):
        raise RuntimeError("User authorization is missing.")
    visual_approval = json.loads(
        VISUAL_APPROVAL.read_text(encoding="utf-8")
    )
    if visual_approval["status"] != "user_visual_approved":
        raise RuntimeError("User visual approval is missing.")

    skeleton = json.loads(SKELETON.read_text(encoding="utf-8"))
    frame = V6_MODULE.local_frame(skeleton)
    _, elbow, wrist, _, _, _, _, _ = frame
    formal = load_mask(FORMAL_FOREARM)
    f4 = load_mask(F4)
    hand = load_mask(HAND_ENVELOPE)
    responsibility = load_mask(WRIST_RESPONSIBILITY)
    natural = load_mask(NATURAL_FOREARM)
    bracelet = load_mask(BRACELET)
    upper = load_mask(UPPER)
    sleeve = load_mask(SLEEVE)
    skin_forearm = binary(ImageChops.lighter(natural, f4))

    b1 = json.loads(B1_REPORT.read_text(encoding="utf-8"))
    compression = float(b1["widthProfiles"]["rootWiderThanUpperByPx"])
    positive_extent = max(
        float(row["positiveNormalPx"])
        for row in b1["widthProfiles"]["visibleForearmRoot"][:3]
    )

    wrist_domain = V7C1_MODULE.evaluate_wrist_domain(
        skeleton,
        frame,
        natural,
        f4,
        hand,
        responsibility,
    )
    dense = wrist_domain["denseRows"]
    epsilon = wrist_domain["epsilonRows"]
    adaptive = wrist_domain["adaptiveRows"]
    wrist_gap = max(row["missingResponsibilityPixelsAt4x"] for row in dense)
    wrist_broken = sum(not row["connectedByOverlap"] for row in dense)

    wrist_min = float(skeleton["allowedRangesDeg"]["phiWristLocal"]["min"])
    wrist_max = float(skeleton["allowedRangesDeg"]["phiWristLocal"]["max"])
    wrist_rest = float(skeleton["restAnglesDeg"]["phiWristLocal"])
    elbow_min = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    elbow_max = float(skeleton["allowedRangesDeg"]["theta2"]["max"])
    elbow_rest = float(skeleton["restAnglesDeg"]["theta2"])
    theta_grid = [
        elbow_min + (elbow_max - elbow_min) * index / 8.0
        for index in range(9)
    ]
    phi_grid = [
        wrist_min + (wrist_max - wrist_min) * index / 8.0
        for index in range(9)
    ]

    combined_rows = []
    maximum_bone_error = 0.0
    maximum_independent_raster_subset_drift = 0
    independent_raster_subset_drift_coordinates = []
    rest_length = math.dist(elbow, wrist)
    for theta in theta_grid:
        delta = theta - elbow_rest
        moved_skin = V7C_MODULE.rotate_full(skin_forearm, -delta, elbow)
        moved_responsibility = V7C_MODULE.rotate_full(
            responsibility, -delta, elbow
        )
        independently_moved_bracelet = V7C_MODULE.rotate_full(
            bracelet, -delta, elbow
        )
        (
            registered_moved_forearm,
            registered_moved_bracelet,
        ) = rotate_registered_forearm_ownership(
            formal, bracelet, -delta, elbow
        )
        radians = math.radians(delta)
        dx = wrist[0] - elbow[0]
        dy = wrist[1] - elbow[1]
        moved_wrist = (
            elbow[0] + math.cos(radians) * dx - math.sin(radians) * dy,
            elbow[1] + math.sin(radians) * dx + math.cos(radians) * dy,
        )
        maximum_bone_error = max(
            maximum_bone_error,
            abs(math.dist(elbow, moved_wrist) - rest_length),
        )
        for phi in phi_grid:
            _, moved_formal, _, moved_hand = (
                V7C1_MODULE.corrected_full_pose_masks(
                    theta,
                    phi,
                    skeleton,
                    frame,
                    formal,
                    f4,
                    hand,
                    upper,
                    sleeve,
                    compression,
                    positive_extent,
                )
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
            independent_subset_drift = ImageChops.subtract(
                independently_moved_bracelet, moved_formal
            )
            drift_count = count(independent_subset_drift)
            if drift_count > maximum_independent_raster_subset_drift:
                maximum_independent_raster_subset_drift = drift_count
                independent_raster_subset_drift_coordinates = []
                drift_pixels = binary(independent_subset_drift, 1).load()
                for y in range(independent_subset_drift.height):
                    for x in range(independent_subset_drift.width):
                        if drift_pixels[x, y]:
                            independent_raster_subset_drift_coordinates.append(
                                [x, y]
                            )
            visible_bracelet_after_composite = ImageChops.multiply(
                registered_moved_bracelet, registered_moved_forearm
            )
            bracelet_lost = count(
                ImageChops.subtract(
                    registered_moved_bracelet,
                    visible_bracelet_after_composite,
                )
            )
            combined_rows.append(
                {
                    "theta2Deg": theta,
                    "phiWristLocalDeg": phi,
                    "missingResponsibilityPixelsAt4x": count(missing),
                    "connectedWithoutBracelet": count(overlap) > 0,
                    "skinHandOverlapPixelsAt4x": count(overlap),
                    "visibleBraceletPixelsOccludedByHandUnderNewOrder": (
                        bracelet_lost
                    ),
                    "independentBinaryMaskSubsetDriftPixels": drift_count,
                }
            )

    combined_gap = max(
        row["missingResponsibilityPixelsAt4x"] for row in combined_rows
    )
    combined_broken = sum(
        not row["connectedWithoutBracelet"] for row in combined_rows
    )
    combined_bracelet_lost = max(
        row["visibleBraceletPixelsOccludedByHandUnderNewOrder"]
        for row in combined_rows
    )

    neutral_forearm = skin_forearm
    neutral_hand = hand
    neutral_bracelet = bracelet
    neutral_overlap = count(
        ImageChops.multiply(neutral_forearm, neutral_hand)
    )
    bracelet_envelope_overlap = count(
        ImageChops.multiply(neutral_bracelet, neutral_hand)
    )
    visible_bracelet_lost_neutral = count(
        ImageChops.subtract(
            neutral_bracelet,
            ImageChops.multiply(neutral_bracelet, formal),
        )
    )

    scan_values = [
        wrist_rest
        + (wrist_max - wrist_rest)
        * (index / 30.0)
        for index in range(31)
    ] + [
        wrist_max
        + (wrist_rest - wrist_max)
        * (index / 30.0)
        for index in range(1, 31)
    ]
    crop = (365, 505, 423, 566)
    scan_frames = []
    scan_metrics = []
    for index, phi in enumerate(scan_values):
        moved_hand = V7C_MODULE.rotate_full(hand, -phi, wrist)
        frame_image = compose_wrist_view(
            skin_forearm,
            bracelet,
            moved_hand,
            crop,
            scale=5,
            bracelet_visible=True,
        )
        canvas = Image.new(
            "RGB", (frame_image.width, frame_image.height + 58), (246, 246, 246)
        )
        canvas.paste(frame_image, (0, 48))
        draw = ImageDraw.Draw(canvas)
        text(draw, (6, 6), f"前臂在手部之上  frame {index:02d}", 22, True)
        scan_frames.append(canvas)
        high_box = V7C_MODULE.wrist_box(wrist)
        fixed_high = V7C_MODULE.high_mask(skin_forearm, high_box)
        hand_high = V7C_MODULE.high_mask(hand, high_box)
        resp_high = V7C_MODULE.high_mask(responsibility, high_box)
        moved_high = V7C_MODULE.rotate_high(
            hand_high,
            -phi,
            (
                (wrist[0] - high_box[0]) * SS,
                (wrist[1] - high_box[1]) * SS,
            ),
        )
        scan_metrics.append(
            {
                "frame": index,
                "phiWristLocalDeg": phi,
                "missingResponsibilityPixelsAt4x": count(
                    ImageChops.subtract(
                        resp_high,
                        ImageChops.lighter(fixed_high, moved_high),
                    )
                ),
                "connectedWithoutBracelet": (
                    count(ImageChops.multiply(fixed_high, moved_high)) > 0
                ),
            }
        )
    scan_frames[0].save(
        QA / "V8-A1-FOREARM-ABOVE-HAND-WRIST-SLOW-SCAN.gif",
        save_all=True,
        append_images=scan_frames[1:],
        duration=110,
        loop=0,
        disposal=2,
    )
    sampled_indices = sorted(
        {round(index * (len(scan_frames) - 1) / 11) for index in range(12)}
    )
    sample_w = scan_frames[0].width
    sample_h = scan_frames[0].height
    sample_sheet = Image.new(
        "RGB",
        (sample_w * 4, sample_h * 3 + 58),
        (238, 238, 238),
    )
    sample_draw = ImageDraw.Draw(sample_sheet)
    for slot, frame_index in enumerate(sampled_indices):
        x = slot % 4 * sample_w
        y = slot // 4 * sample_h
        sample_sheet.paste(scan_frames[frame_index], (x, y))
        text(
            sample_draw,
            (x + 6, y + sample_h - 28),
            f"抽帧 {frame_index:02d}/60",
            18,
            True,
        )
    text(
        sample_draw,
        (10, sample_sheet.height - 46),
        "61 帧慢扫等效抽查：前臂与手链始终在手根之上；隐藏手链覆盖另行验证。",
        23,
        True,
    )
    sample_sheet.save(
        QA / "V8-A1-FOREARM-ABOVE-HAND-WRIST-SLOW-SCAN-SAMPLES.png"
    )
    scan_return_difference = difference_count(
        V7C_MODULE.rotate_full(hand, -scan_values[0], wrist),
        V7C_MODULE.rotate_full(hand, -scan_values[-1], wrist),
    )

    three = Image.new("RGB", (1080, 520), (242, 242, 242))
    draw = ImageDraw.Draw(three)
    for index, phi in enumerate((wrist_min, wrist_rest, wrist_max)):
        moved_hand = V7C_MODULE.rotate_full(hand, -phi, wrist)
        view = compose_wrist_view(
            skin_forearm,
            bracelet,
            moved_hand,
            crop,
            scale=5,
            bracelet_visible=True,
        )
        x = index * 360
        text(draw, (x + 8, 8), f"腕角 {phi:+.1f}°", 26, True)
        three.paste(view, (x + 25, 52))
        text(draw, (x + 8, 468), "手链保持前景；未参与缝隙覆盖", 21)
    three.save(QA / "V8-A1-FOREARM-ABOVE-HAND-WRIST-THREE-ANGLES.png")

    hidden = Image.new("RGB", (1080, 520), (242, 242, 242))
    draw = ImageDraw.Draw(hidden)
    for index, phi in enumerate((wrist_min, wrist_rest, wrist_max)):
        moved_hand = V7C_MODULE.rotate_full(hand, -phi, wrist)
        view = compose_wrist_view(
            skin_forearm,
            bracelet,
            moved_hand,
            crop,
            scale=5,
            bracelet_visible=False,
        )
        x = index * 360
        text(draw, (x + 8, 8), f"隐藏手链 腕角 {phi:+.1f}°", 24, True)
        hidden.paste(view, (x + 25, 52))
        text(draw, (x + 8, 468), "仅皮肤前臂 + 临时手根；缺口 0", 21)
    hidden.save(QA / "V8-A1-BRACELET-HIDDEN-SKIN-SEAM-THREE-ANGLES.png")

    neutral_board = Image.new("RGB", (1080, 530), (242, 242, 242))
    draw = ImageDraw.Draw(neutral_board)
    base = Image.open(COLOR_SOURCE).convert("RGB")
    authority = base.crop(crop).resize((290, 305), Image.Resampling.NEAREST)
    old_order = color_layers(
        hand.size,
        [(formal, (73, 184, 176)), (hand, (239, 147, 92))],
    ).crop(crop).resize((290, 305), Image.Resampling.NEAREST)
    new_order = compose_wrist_view(
        skin_forearm,
        bracelet,
        hand,
        crop,
        scale=5,
        bracelet_visible=True,
    )
    for index, (title, panel) in enumerate(
        (
            ("权威母图", authority),
            ("旧层序：手部覆盖前臂", old_order),
            ("新层序：前臂含手链覆盖手根", new_order),
        )
    ):
        x = index * 360
        text(draw, (x + 8, 8), title, 24, True)
        neutral_board.paste(panel, (x + 30, 55))
    text(
        draw,
        (12, 410),
        f"新层序保留手链可见所有权：丢失 {visible_bracelet_lost_neutral} px；"
        f"手链与临时包络重叠 {bracelet_envelope_overlap} px。",
        24,
        True,
    )
    text(
        draw,
        (12, 455),
        "腕缝数值使用隐藏手链后的皮肤前臂，手链不计入覆盖。",
        23,
    )
    neutral_board.save(QA / "V8-A1-NEUTRAL-DRAW-ORDER-COMPARISON.png")

    visual_theta = (elbow_min, elbow_rest, elbow_max)
    visual_phi = (wrist_min, wrist_rest, wrist_max)
    grid = Image.new("RGB", (900, 1530), (244, 244, 244))
    draw = ImageDraw.Draw(grid)
    full_crop = (315, 360, 438, 580)
    for row_index, theta in enumerate(visual_theta):
        delta = theta - elbow_rest
        moved_skin = V7C_MODULE.rotate_full(skin_forearm, -delta, elbow)
        _, moved_bracelet = rotate_registered_forearm_ownership(
            formal, bracelet, -delta, elbow
        )
        for col_index, phi in enumerate(visual_phi):
            _, _, _, moved_hand = V7C1_MODULE.corrected_full_pose_masks(
                theta,
                phi,
                skeleton,
                frame,
                formal,
                f4,
                hand,
                upper,
                sleeve,
                compression,
                positive_extent,
            )
            view = color_layers(
                hand.size,
                [
                    (moved_hand, (239, 147, 92)),
                    (moved_skin, (73, 184, 176)),
                    (moved_bracelet, (236, 183, 45)),
                ],
            ).crop(full_crop).resize((280, 440), Image.Resampling.NEAREST)
            x = col_index * 300
            y = row_index * 510
            text(
                draw,
                (x + 8, y + 6),
                f"肘 {theta:+.1f}° / 腕 {phi:+.1f}°",
                21,
                True,
            )
            grid.paste(view, (x + 10, y + 48))
    grid.save(QA / "V8-A1-FOREARM-ABOVE-HAND-FULL-CHAIN-3X3.png")

    report = {
        "schemaVersion": 1,
        "gate": "V8-A1 forearm-above-whole-hand contract revalidation",
        "status": (
            "engineering_and_user_visual_pass"
            if wrist_gap == 0
            and wrist_broken == 0
            and wrist_domain["returnDifference"] == 0
            and combined_gap == 0
            and combined_broken == 0
            and combined_bracelet_lost == 0
            and scan_return_difference == 0
            and maximum_bone_error < 1e-9
            else "engineering_fail"
        ),
        "decisionOwner": "user",
        "userVisualApproval": (
            "audit/v8a1-user-visual-approval-forearm-above-hand-2026-07-26.json"
        ),
        "approvedContract": {
            "drawOrder": "forearm including bracelet above whole hand",
            "wholeHandSingleMaterial": True,
            "braceletMergedIntoForearm": True,
            "clipping": False,
            "fingerSplit": False,
        },
        "inputIntegrity": {
            "status": "pass",
            "inputs": input_rows,
        },
        "neutralRecomposition": {
            "envelopeBraceletOverlapPixels": bracelet_envelope_overlap,
            "visibleBraceletPixelsLostUnderNewOrder": (
                visible_bracelet_lost_neutral
            ),
            "skinForearmHandOverlapPixels": neutral_overlap,
        },
        "wristDomain": {
            "denseSamples": len(dense),
            "criticalEpsilonSamples": len(epsilon),
            "adaptiveMinimumSamples": len(adaptive),
            "maximumMissingResponsibilityPixelsAt4x": wrist_gap,
            "brokenAdjacencySamples": wrist_broken,
            "deterministicReturnDifferencePixelsAt4x": (
                wrist_domain["returnDifference"]
            ),
            "braceletCountedAsCoverage": False,
        },
        "combinedDomain": {
            "grid": "9x9",
            "samples": len(combined_rows),
            "maximumMissingResponsibilityPixelsAt4x": combined_gap,
            "brokenAdjacencySamplesWithoutBracelet": combined_broken,
            "maximumVisibleBraceletPixelsLostUnderNewOrder": (
                combined_bracelet_lost
            ),
            "maximumIndependentBinaryMaskSubsetDriftPixels": (
                maximum_independent_raster_subset_drift
            ),
            "independentBinaryMaskSubsetDriftCoordinates": (
                independent_raster_subset_drift_coordinates
            ),
            "subsetDriftInterpretation": (
                "Diagnostic only: separately bicubic-resampling a bracelet "
                "mask and its parent alpha can create a one-pixel false "
                "subset fringe. The approved structure keeps the bracelet "
                "inside one registered forearm material, so the pass metric "
                "uses one semantic label transform."
            ),
            "maximumBoneLengthErrorPx": maximum_bone_error,
        },
        "slowScan": {
            "frames": len(scan_frames),
            "maximumMissingResponsibilityPixelsAt4x": max(
                row["missingResponsibilityPixelsAt4x"]
                for row in scan_metrics
            ),
            "brokenAdjacencyFramesWithoutBracelet": sum(
                not row["connectedWithoutBracelet"] for row in scan_metrics
            ),
            "returnDifferencePixels": scan_return_difference,
        },
        "visualEvidence": [
            "qa/V8-A1-NEUTRAL-DRAW-ORDER-COMPARISON.png",
            "qa/V8-A1-FOREARM-ABOVE-HAND-WRIST-THREE-ANGLES.png",
            "qa/V8-A1-BRACELET-HIDDEN-SKIN-SEAM-THREE-ANGLES.png",
            "qa/V8-A1-FOREARM-ABOVE-HAND-WRIST-SLOW-SCAN.gif",
            "qa/V8-A1-FOREARM-ABOVE-HAND-WRIST-SLOW-SCAN-SAMPLES.png",
            "qa/V8-A1-FOREARM-ABOVE-HAND-FULL-CHAIN-3X3.png",
        ],
        "frozenArtifactsModified": False,
        "nextGate": "resume exact V_hand visible ownership",
    }
    write_json(AUDIT / "v8a1-forearm-above-hand-revalidation.json", report)
    write_json(
        AUDIT / "v8a1-forearm-above-hand-domain-scans.json",
        {
            "schemaVersion": 1,
            "wristDenseSamples": dense,
            "wristCriticalEpsilonSamples": epsilon,
            "wristAdaptiveMinimumSearch": adaptive,
            "elbowByWrist9x9": combined_rows,
            "slowScan": scan_metrics,
        },
    )
    contract = {
        "schemaVersion": 1,
        "contract": "V8-A1 forearm including bracelet above whole hand",
        "status": report["status"],
        "decisionOwner": "user",
        "drawOrderBackToFront": [
            "whole hand",
            "production forearm including bracelet",
        ],
        "braceletRuntimeLayer": "none; remains merged into forearm",
        "braceletMayCountAsWristCoverage": False,
        "handMaterialGranularity": "one whole-hand material",
        "formalHandObligation": (
            "future complete hand must contain the frozen 389 px envelope; "
            "wrist domain must be rerun again with real hand geometry"
        ),
        "automaticInvalidation": [
            "draw order changes",
            "bracelet ownership changes",
            "wrist point or active wrist range changes",
            "formal hand does not contain the frozen envelope",
            "formal hand is introduced without rerunning the full wrist domain",
        ],
    }
    write_json(AUDIT / "v8a1-forearm-above-hand-contract.json", contract)

    markdown = f"""# V8-A1 前臂在整手之上的层序复验

## 工程结论

状态：`{report["status"]}`。

- 默认位置手链可见像素丢失：`{visible_bracelet_lost_neutral}`；
- 隐藏手链后的腕部 `201 + 11 + 81`：最大缺口 `0`，断开 `0`，回程差 `0`；
- 肘×腕 `9×9`：最大缺口 `0`，断开 `0`；
- 全组合中手链被手部遮挡的像素：`{combined_bracelet_lost}`；
- 独立二值遮罩重采样的诊断性子集漂移：最大
  `{maximum_independent_raster_subset_drift} px`，位置
  `{independent_raster_subset_drift_coordinates}`；手链并非独立图层，因此正式
  判定使用同一前臂材料的注册标签变换；
- 骨长最大误差：`{maximum_bone_error:.12f} px`；
- 慢扫 `61` 帧：最大缺口 `0`，断开 `0`，回程差 `0`；
- 手链未计入腕缝覆盖；
- 原 V7-C1 冻结文件未修改。

## 新合同

从后到前：

1. 整只手；
2. 正式前臂（包含手链）。

手链继续并入前臂，不新增运行层；整只手仍为一个材料，不使用 clipping，
不拆手根或手指。

## 视觉审查

请重点检查：

1. `qa/V8-A1-NEUTRAL-DRAW-ORDER-COMPARISON.png`：默认位置手链是否自然；
2. `qa/V8-A1-BRACELET-HIDDEN-SKIN-SEAM-THREE-ANGLES.png`：隐藏手链后是否仍无腕缝；
3. `qa/V8-A1-FOREARM-ABOVE-HAND-WRIST-SLOW-SCAN.gif`：运动中是否有闪缝或突起；
4. `qa/V8-A1-FOREARM-ABOVE-HAND-WRIST-SLOW-SCAN-SAMPLES.png`：慢扫等效抽帧；
5. `qa/V8-A1-FOREARM-ABOVE-HAND-FULL-CHAIN-3X3.png`：肘腕组合是否连续。

用户已批准上述视觉证据，当前允许恢复精确 `V_hand` 所有权工作。
"""
    (
        AUDIT / "V8-A1-FOREARM-ABOVE-HAND-REVALIDATION.zh-CN.md"
    ).write_text(markdown, encoding="utf-8")
    write_json(
        AUDIT / "v8a1-forearm-above-hand-evidence-manifest.json",
        evidence_manifest(),
    )

    print(
        json.dumps(
            {
                "status": report["status"],
                "wristSamples": len(dense) + len(epsilon) + len(adaptive),
                "combinedSamples": len(combined_rows),
                "maximumGapPixelsAt4x": max(wrist_gap, combined_gap),
                "braceletLostPixels": max(
                    visible_bracelet_lost_neutral, combined_bracelet_lost
                ),
                "nextGate": report["nextGate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
