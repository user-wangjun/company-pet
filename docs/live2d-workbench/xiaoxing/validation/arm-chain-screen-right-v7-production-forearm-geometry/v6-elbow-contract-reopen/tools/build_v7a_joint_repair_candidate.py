from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


HERE = Path(__file__).resolve()
REOPEN = HERE.parents[1]
V7 = HERE.parents[2]
VALIDATION = V7.parent
V4 = VALIDATION / "arm-chain-screen-right-v4-wrist-motion"
V6 = VALIDATION / "arm-chain-screen-right-v6-complete-upper-arm-geometry"

AUDIT = REOPEN / "audit"
MASKS = REOPEN / "masks"
QA = REOPEN / "qa"

BASE_BUILDER_PATH = REOPEN / "tools/build_v7a_elbow_contract_reopen.py"
SKELETON_PATH = V4 / "skeleton.json"
UPPER_GEOMETRY_PATH = V6 / "masks/upper-arm-complete-geometry.png"
UPPER_VISIBLE_PATH = V6 / "masks/reference/visible-upper-arm-locked-reference.png"
OLD_ENVELOPE_PATH = V7 / "masks/v6-minimum-envelope-neutral-footprint.png"
SOURCE_SUPPORT_PATH = V7 / "masks/source-arm-neutral-outline-candidate.png"
VISIBLE_FOREARM_PATH = V7 / "masks/visible-forearm-locked.png"
COLOR_PATH = (
    VALIDATION.parent / "source/masters/front-color-source-exact-after-reset.png"
)
USER_DECISION_PATH = V7 / "audit/v7a-user-visual-decision-2026-07-26.json"

SS = 4
ALPHA_THRESHOLD = 16
CROP_RADIUS = 46
THRESHOLDS = (-18.0, -17.0, -16.0, -15.5, -15.25, -15.0, -12.0, -9.0)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path.name}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_module("v7a_reopen_base", BASE_BUILDER_PATH)
V6_MODULE = BASE.V6_MODULE


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def binary(mask: Image.Image, threshold: int = 1) -> Image.Image:
    return mask.convert("L").point(lambda value: 255 if value >= threshold else 0)


def load_mask(path: Path) -> Image.Image:
    image = Image.open(path)
    return binary(image if image.mode == "L" else image.convert("RGBA").getchannel("A"))


def mask_count(mask: Image.Image) -> int:
    return sum(1 for value in binary(mask).get_flattened_data() if value)


def rgba_mask(mask: Image.Image) -> Image.Image:
    output = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    output.putalpha(binary(mask))
    return output


def select_local_s(
    mask: Image.Image,
    threshold: float,
    elbow: tuple[float, float],
    axis: tuple[float, float],
) -> Image.Image:
    output = Image.new("L", mask.size, 0)
    source = binary(mask).load()
    target = output.load()
    bbox = mask.getbbox()
    if bbox is None:
        return output
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            if not source[x, y]:
                continue
            local_s = (
                (x + 0.5 - elbow[0]) * axis[0]
                + (y + 0.5 - elbow[1]) * axis[1]
            )
            if local_s >= threshold:
                target[x, y] = 255
    return output


def local_s_range(
    mask: Image.Image,
    elbow: tuple[float, float],
    axis: tuple[float, float],
) -> list[float]:
    values = []
    for x, y in V6_MODULE.mask_pixels(mask) or []:
        values.append(
            (x + 0.5 - elbow[0]) * axis[0]
            + (y + 0.5 - elbow[1]) * axis[1]
        )
    return [min(values), max(values)]


def exposure_parent_trim(
    upper: Image.Image,
    candidate: Image.Image,
    skeleton: dict,
    frame,
    angles: list[float],
) -> tuple[Image.Image, dict]:
    _, elbow, _, _, responsibility_axis, responsibility_normal, _, _ = frame
    box = (
        round(elbow[0] - CROP_RADIUS),
        round(elbow[1] - CROP_RADIUS),
        round(elbow[0] + CROP_RADIUS),
        round(elbow[1] + CROP_RADIUS),
    )
    high_size = ((box[2] - box[0]) * SS, (box[3] - box[1]) * SS)
    upper_high = binary(upper.crop(box)).resize(
        high_size, Image.Resampling.NEAREST
    )
    candidate_high = binary(candidate.crop(box)).resize(
        high_size, Image.Resampling.NEAREST
    )
    center = (
        (elbow[0] - box[0]) * SS,
        (elbow[1] - box[1]) * SS,
    )
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    parent_pixels: set[tuple[int, int]] = set()
    high_union = Image.new("L", high_size, 0)
    high_union_pixels = high_union.load()
    worst_count = -1
    worst_angle = None
    for theta2 in angles:
        delta = theta2 - rest
        moving = binary(
            candidate_high.rotate(
                delta,
                resample=Image.Resampling.BICUBIC,
                center=center,
                fillcolor=0,
            ),
            ALPHA_THRESHOLD,
        )
        visible_upper = ImageChops.subtract(upper_high, moving)
        angle = math.radians(delta)
        cosine, sine = math.cos(angle), math.sin(angle)
        current_axis = (
            cosine * responsibility_axis[0] - sine * responsibility_axis[1],
            sine * responsibility_axis[0] + cosine * responsibility_axis[1],
        )
        current_normal = (
            cosine * responsibility_normal[0] - sine * responsibility_normal[1],
            sine * responsibility_normal[0] + cosine * responsibility_normal[1],
        )
        exposed = []
        for x, y in V6_MODULE.mask_pixels(visible_upper) or []:
            dx = (x + 0.5 - center[0]) / SS
            dy = (y + 0.5 - center[1]) / SS
            local_s = dx * current_axis[0] + dy * current_axis[1]
            local_n = dx * current_normal[0] + dy * current_normal[1]
            if -12.0 <= local_s <= 8.0 and local_n < 0.0:
                exposed.append((x, y))
                high_union_pixels[x, y] = 255
                parent_pixels.add((box[0] + x // SS, box[1] + y // SS))
        if len(exposed) > worst_count:
            worst_count = len(exposed)
            worst_angle = theta2
    trim = Image.new("L", upper.size, 0)
    trim_pixels = trim.load()
    for x, y in parent_pixels:
        trim_pixels[x, y] = 255
    return trim, {
        "worstPreTrimExposureAt4x": worst_count,
        "worstPreTrimTheta2Deg": worst_angle,
        "unionExposureSubpixelsAt4x": mask_count(high_union),
        "parentTrimPixelCount": len(parent_pixels),
    }


def evaluate_candidate(
    threshold: float,
    root_source: Image.Image,
    visible_forearm: Image.Image,
    source_support: Image.Image,
    upper_geometry: Image.Image,
    upper_visible: Image.Image,
    skeleton: dict,
    frame,
    primary: list[dict],
    extremes: list[dict],
    angles: list[float],
) -> tuple[dict, dict[str, Image.Image]]:
    _, elbow, _, _, _, _, forearm_axis, _ = frame
    selected_root = select_local_s(root_source, threshold, elbow, forearm_axis)
    candidate = binary(ImageChops.lighter(visible_forearm, selected_root))
    trim, exposure = exposure_parent_trim(
        upper_geometry, candidate, skeleton, frame, angles
    )
    simulated_upper = binary(ImageChops.subtract(upper_geometry, trim))
    scan_outline = [
        (-24.0, -20.0),
        (24.0, -20.0),
        (130.0, -10.0),
        (130.0, 10.0),
        (24.0, 20.0),
        (-24.0, 20.0),
    ]
    scan, dense = V6_MODULE.elbow_scan(
        simulated_upper,
        candidate,
        scan_outline,
        skeleton,
        frame,
        primary,
        extremes,
    )
    reassigned = binary(ImageChops.multiply(candidate, upper_visible))
    visible_trim = binary(ImageChops.multiply(trim, upper_visible))
    hidden_trim = binary(ImageChops.subtract(trim, upper_visible))
    selected_range = local_s_range(selected_root, elbow, forearm_axis)
    root_extension = -selected_range[0]
    outside = binary(ImageChops.subtract(selected_root, source_support))
    report = {
        "thresholdLocalSPx": threshold,
        "selectedRootPixelCount": mask_count(selected_root),
        "selectedRootLocalSRangePx": selected_range,
        "rootExtensionBehindElbowPx": root_extension,
        "passesFrozen15PxResponsibility": root_extension >= 15.0,
        "rootPixelsOutsideSourceSupport": mask_count(outside),
        "visibleUpperOwnershipPixelsReassignedToForearm": mask_count(reassigned),
        "upperGeometryTrimPixels": mask_count(trim),
        "visibleUpperTrimPixels": mask_count(visible_trim),
        "hiddenUpperTrimPixels": mask_count(hidden_trim),
        **exposure,
        "postTrimMaximumMissingResponsibilityPixelsAt4x": scan[
            "maximumMissingResponsibilityPixelsAt4x"
        ],
        "postTrimBrokenAdjacencySamples": scan["brokenAdjacencySamples"],
        "postTrimMaximumInnerBendExposureAt4x": scan[
            "maximumInnerBendExposedUpperPixelsAt4x"
        ],
        "denseSamplesWithInnerBendExposureAfterTrim": sum(
            item["innerBendExposedUpperPixelsAt4x"] > 0 for item in dense
        ),
        "candidatePassesJointSuccessorContract": all(
            (
                root_extension >= 15.0,
                mask_count(outside) == 0,
                scan["maximumMissingResponsibilityPixelsAt4x"] == 0,
                scan["brokenAdjacencySamples"] == 0,
                scan["maximumInnerBendExposedUpperPixelsAt4x"] == 0,
            )
        ),
    }
    return report, {
        "selectedRoot": selected_root,
        "candidateForearm": candidate,
        "trim": trim,
        "visibleTrim": visible_trim,
        "hiddenTrim": hidden_trim,
        "simulatedUpper": simulated_upper,
        "reassigned": reassigned,
    }


def panel(title: str, subtitle: str, image: Image.Image) -> Image.Image:
    result = Image.new("RGB", (900, 650), (250, 250, 250))
    draw = ImageDraw.Draw(result)
    draw.text((24, 18), title, font=BASE.font(30), fill=(24, 24, 24))
    draw.text((24, 60), subtitle, font=BASE.font(19), fill=(75, 75, 75))
    content = image.convert("RGB")
    content.thumbnail((850, 525), Image.Resampling.NEAREST)
    result.paste(content, ((900 - content.width) // 2, 105))
    return result


def make_board(
    chosen: dict,
    images: dict[str, Image.Image],
    old_envelope: Image.Image,
    source_support: Image.Image,
    upper_geometry: Image.Image,
    upper_visible: Image.Image,
    color: Image.Image,
    skeleton: dict,
    frame,
) -> None:
    canvas = upper_geometry.size
    base = color.convert("RGBA")
    old_outside = binary(ImageChops.subtract(old_envelope, source_support))
    old_conflict = binary(ImageChops.multiply(old_envelope, upper_visible))
    old_overlay = BASE.tint(
        base,
        [
            (old_envelope, (220, 45, 165, 130)),
            (old_outside, (255, 205, 0, 235)),
            (old_conflict, (240, 25, 25, 230)),
        ],
    )
    successor_overlay = BASE.tint(
        base,
        [
            (images["candidateForearm"], (0, 175, 155, 125)),
            (images["reassigned"], (145, 75, 220, 220)),
        ],
    )
    trim_overlay = BASE.tint(
        base,
        [
            (upper_visible, (235, 125, 70, 110)),
            (images["hiddenTrim"], (255, 205, 0, 235)),
            (images["visibleTrim"], (240, 25, 25, 235)),
        ],
    )
    before = BASE.worst_angle_layers(
        images["candidateForearm"],
        upper_geometry,
        skeleton,
        frame,
        chosen["worstPreTrimTheta2Deg"],
    )
    after = BASE.worst_angle_layers(
        images["candidateForearm"],
        images["simulatedUpper"],
        skeleton,
        frame,
        chosen["worstPreTrimTheta2Deg"],
    )
    high_base = Image.new("RGBA", before[0].size, (255, 255, 255, 255))
    before_overlay = BASE.tint(
        high_base,
        [
            (before[0], (235, 125, 70, 200)),
            (before[1], (0, 175, 155, 185)),
            (before[2], (240, 25, 25, 245)),
        ],
    )
    after_overlay = BASE.tint(
        high_base,
        [
            (after[0], (235, 125, 70, 200)),
            (after[1], (0, 175, 155, 185)),
            (after[2], (240, 25, 25, 245)),
        ],
    )
    motion = Image.new("RGB", (before_overlay.width * 2 + 16, before_overlay.height))
    motion.paste(before_overlay.convert("RGB"), (0, 0))
    motion.paste(after_overlay.convert("RGB"), (before_overlay.width + 16, 0))

    crop = (332, 385, 384, 447)
    panels = [
        panel(
            "1｜旧合同为何不能沿用",
            "黄=背景 132 px；红=重复上臂 416 px",
            old_overlay.crop(crop).resize((520, 620), Image.Resampling.NEAREST),
        ),
        panel(
            "2｜后继前臂所有权候选",
            f"紫=从上臂转给前臂 {chosen['visibleUpperOwnershipPixelsReassignedToForearm']} px",
            successor_overlay.crop(crop).resize(
                (520, 620), Image.Resampling.NEAREST
            ),
        ),
        panel(
            "3｜上臂末端最小修剪复制件",
            (
                f"红=可见 {chosen['visibleUpperTrimPixels']} px；"
                f"黄=隐藏 {chosen['hiddenUpperTrimPixels']} px"
            ),
            trim_overlay.crop(crop).resize((520, 620), Image.Resampling.NEAREST),
        ),
        panel(
            "4｜同一最坏角：修剪前 / 修剪后",
            (
                f"修剪前红色暴露 {chosen['worstPreTrimExposureAt4x']}；"
                "修剪后缺口/断开/暴露均为 0"
            ),
            motion,
        ),
    ]
    board = Image.new("RGB", (1840, 1390), (238, 238, 238))
    draw = ImageDraw.Draw(board)
    draw.text(
        (30, 20),
        "小星 V7-A｜V6 肘部后继合同阈值族候选",
        font=BASE.font(38),
        fill=(20, 20, 20),
    )
    draw.text(
        (30, 70),
        "在 8 个声明阈值中最小化所有权转移；不改冻结文件，且不代表用户已批准新肘线。",
        font=BASE.font(23),
        fill=(65, 65, 65),
    )
    for index, item in enumerate(panels):
        board.paste(item, (20 + (index % 2) * 910, 115 + (index // 2) * 650))
    board.save(QA / "V7-A-JOINT-REPAIR-CANDIDATE-BOARD.png")


def render_motion_frame(
    theta2: float,
    skeleton: dict,
    frame,
    simulated_upper: Image.Image,
    candidate_forearm: Image.Image,
    reassigned: Image.Image,
) -> Image.Image:
    _, elbow, _, _, _, _, _, _ = frame
    box = (
        round(elbow[0] - CROP_RADIUS),
        round(elbow[1] - CROP_RADIUS),
        round(elbow[0] + CROP_RADIUS),
        round(elbow[1] + CROP_RADIUS),
    )
    size = ((box[2] - box[0]) * SS, (box[3] - box[1]) * SS)
    center = (
        (elbow[0] - box[0]) * SS,
        (elbow[1] - box[1]) * SS,
    )
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    delta = theta2 - rest
    upper = binary(simulated_upper.crop(box)).resize(
        size, Image.Resampling.NEAREST
    )
    forearm = binary(candidate_forearm.crop(box)).resize(
        size, Image.Resampling.NEAREST
    ).rotate(
        delta,
        resample=Image.Resampling.BICUBIC,
        center=center,
        fillcolor=0,
    )
    forearm = binary(forearm, ALPHA_THRESHOLD)
    moved_reassigned = binary(reassigned.crop(box)).resize(
        size, Image.Resampling.NEAREST
    ).rotate(
        delta,
        resample=Image.Resampling.BICUBIC,
        center=center,
        fillcolor=0,
    )
    moved_reassigned = binary(moved_reassigned, ALPHA_THRESHOLD)
    image = Image.new("RGB", (size[0], size[1] + 64), (247, 247, 247))
    body = Image.new("RGB", size, (255, 255, 255))
    body.paste((235, 145, 95), mask=upper)
    body.paste((65, 190, 178), mask=forearm)
    body.paste((145, 85, 220), mask=moved_reassigned)
    image.paste(body, (0, 64))
    draw = ImageDraw.Draw(image)
    draw.text(
        (14, 8),
        f"肘角 θ2={theta2:.3f}°",
        font=BASE.font(23),
        fill=(25, 25, 25),
    )
    draw.text(
        (14, 38),
        (
            "橙=上臂复制件  青=前臂"
            if mask_count(reassigned) == 0
            else "橙=上臂复制件  青=前臂  紫=转移所有权"
        ),
        font=BASE.font(16),
        fill=(75, 75, 75),
    )
    return image


def make_motion_review(
    skeleton: dict,
    frame,
    simulated_upper: Image.Image,
    candidate_forearm: Image.Image,
    reassigned: Image.Image,
) -> None:
    minimum = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    maximum = float(skeleton["allowedRangesDeg"]["theta2"]["max"])
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    forward = [
        minimum + (maximum - minimum) * index / 24.0
        for index in range(25)
    ]
    sweep = forward + forward[-2:0:-1]
    frames = [
        render_motion_frame(
            theta,
            skeleton,
            frame,
            simulated_upper,
            candidate_forearm,
            reassigned,
        )
        for theta in sweep
    ]
    frames[0].save(
        QA / "V7-A-JOINT-REPAIR-CANDIDATE-SLOW-SCAN.gif",
        save_all=True,
        append_images=frames[1:],
        duration=110,
        loop=0,
        disposal=2,
        optimize=False,
    )

    angles = [minimum, rest, maximum]
    labels = ("最弯", "中性", "近直")
    panels = []
    for label, angle in zip(labels, angles):
        frame_image = render_motion_frame(
            angle,
            skeleton,
            frame,
            simulated_upper,
            candidate_forearm,
            reassigned,
        )
        panels.append(
            panel(
                f"{label}｜θ2={angle:.3f}°",
                "重点看紫色区域跟随前臂后是否像自然肘部",
                frame_image,
            )
        )
    sheet = Image.new("RGB", (2720, 680), (238, 238, 238))
    for index, item in enumerate(panels):
        sheet.paste(item, (10 + index * 905, 15))
    sheet.save(QA / "V7-A-JOINT-REPAIR-CANDIDATE-THREE-ANGLES.png")


def comparison_frame(
    theta2: float,
    skeleton: dict,
    frame,
    frozen_upper: Image.Image,
    current_forearm: Image.Image,
    simulated_upper: Image.Image,
    candidate_forearm: Image.Image,
    reassigned: Image.Image,
) -> Image.Image:
    empty = Image.new("L", current_forearm.size, 0)
    preserve = render_motion_frame(
        theta2,
        skeleton,
        frame,
        frozen_upper,
        current_forearm,
        empty,
    )
    transfer = render_motion_frame(
        theta2,
        skeleton,
        frame,
        simulated_upper,
        candidate_forearm,
        reassigned,
    )
    gap = 16
    header = 62
    result = Image.new(
        "RGB",
        (preserve.width + transfer.width + gap, preserve.height + header),
        (238, 238, 238),
    )
    draw = ImageDraw.Draw(result)
    draw.text(
        (14, 8),
        "A 保留原肘线\n视觉连续；15px/零暴露合同需重写",
        font=BASE.font(16),
        fill=(35, 35, 35),
        spacing=3,
    )
    draw.text(
        (preserve.width + gap + 14, 8),
        "B 转移384px\n数值全过；存在楔形补丁风险",
        font=BASE.font(16),
        fill=(35, 35, 35),
        spacing=3,
    )
    result.paste(preserve, (0, header))
    result.paste(transfer, (preserve.width + gap, header))
    return result


def make_structure_comparison(
    skeleton: dict,
    frame,
    frozen_upper: Image.Image,
    current_forearm: Image.Image,
    simulated_upper: Image.Image,
    candidate_forearm: Image.Image,
    reassigned: Image.Image,
) -> None:
    minimum = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    maximum = float(skeleton["allowedRangesDeg"]["theta2"]["max"])
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    forward = [
        minimum + (maximum - minimum) * index / 24.0
        for index in range(25)
    ]
    sweep = forward + forward[-2:0:-1]
    frames = [
        comparison_frame(
            theta,
            skeleton,
            frame,
            frozen_upper,
            current_forearm,
            simulated_upper,
            candidate_forearm,
            reassigned,
        )
        for theta in sweep
    ]
    frames[0].save(
        QA / "V7-A-ELBOW-STRUCTURE-COMPARISON-SLOW-SCAN.gif",
        save_all=True,
        append_images=frames[1:],
        duration=110,
        loop=0,
        disposal=2,
        optimize=False,
    )
    angles = [minimum, rest, maximum]
    stills = [
        comparison_frame(
            theta,
            skeleton,
            frame,
            frozen_upper,
            current_forearm,
            simulated_upper,
            candidate_forearm,
            reassigned,
        )
        for theta in angles
    ]
    sheet = Image.new(
        "RGB",
        (
            stills[0].width * 3 + 32,
            stills[0].height + 78,
        ),
        (238, 238, 238),
    )
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (20, 16),
        "肘部结构对照：不要只看缺口为0，还要看所有权区域随骨骼运动是否自然",
        font=BASE.font(30),
        fill=(25, 25, 25),
    )
    for index, still in enumerate(stills):
        sheet.paste(still, (8 + index * (stills[0].width + 8), 70))
    sheet.save(QA / "V7-A-ELBOW-STRUCTURE-COMPARISON-THREE-ANGLES.png")


def main() -> None:
    for directory in (AUDIT, MASKS, QA):
        directory.mkdir(parents=True, exist_ok=True)
    decision = json.loads(USER_DECISION_PATH.read_text(encoding="utf-8"))
    if not (
        decision["approvedItems"].get("dependencyReopenAuthorization") is True
        and decision["approvedItems"].get("braceletMergedIntoForearmMaterial") is True
    ):
        raise RuntimeError("The required user decisions are not present.")

    skeleton = json.loads(SKELETON_PATH.read_text(encoding="utf-8"))
    frame = V6_MODULE.local_frame(skeleton)
    primary = V6_MODULE.primary_states(skeleton)
    extremes = V6_MODULE.extreme_states(skeleton)
    dense_angles = [
        float(skeleton["allowedRangesDeg"]["theta2"]["min"])
        + (
            float(skeleton["allowedRangesDeg"]["theta2"]["max"])
            - float(skeleton["allowedRangesDeg"]["theta2"]["min"])
        )
        * index
        / 240.0
        for index in range(241)
    ]
    all_angles = (
        dense_angles
        + [state["theta2"] for state in primary]
        + [state["theta2"] for state in extremes]
    )

    old_envelope = load_mask(OLD_ENVELOPE_PATH)
    source_support = load_mask(SOURCE_SUPPORT_PATH)
    visible_forearm = load_mask(VISIBLE_FOREARM_PATH)
    upper_geometry = load_mask(UPPER_GEOMETRY_PATH)
    upper_visible = load_mask(UPPER_VISIBLE_PATH)
    color = Image.open(COLOR_PATH).convert("RGB")
    root_source = binary(ImageChops.multiply(old_envelope, source_support))

    results = []
    image_sets = {}
    for threshold in THRESHOLDS:
        report, images = evaluate_candidate(
            threshold,
            root_source,
            visible_forearm,
            source_support,
            upper_geometry,
            upper_visible,
            skeleton,
            frame,
            primary,
            extremes,
            all_angles,
        )
        results.append(report)
        image_sets[threshold] = images
    passing = [item for item in results if item["candidatePassesJointSuccessorContract"]]
    if not passing:
        raise RuntimeError("No joint successor candidate passed.")
    chosen = min(
        passing,
        key=lambda item: (
            item["visibleUpperOwnershipPixelsReassignedToForearm"],
            item["upperGeometryTrimPixels"],
        ),
    )
    chosen_images = image_sets[chosen["thresholdLocalSPx"]]

    output_masks = {
        "joint-repair-selected-root-envelope.png": chosen_images["selectedRoot"],
        "joint-repair-candidate-forearm-ownership.png": chosen_images[
            "candidateForearm"
        ],
        "joint-repair-upper-trim-mask.png": chosen_images["trim"],
        "joint-repair-upper-visible-trim.png": chosen_images["visibleTrim"],
        "joint-repair-upper-hidden-trim.png": chosen_images["hiddenTrim"],
        "joint-repair-upper-geometry-simulated-copy.png": chosen_images[
            "simulatedUpper"
        ],
        "joint-repair-visible-upper-reassignment.png": chosen_images["reassigned"],
    }
    for name, mask in output_masks.items():
        rgba_mask(mask).save(MASKS / name)

    _, elbow, _, length1, upper_axis, _, _, _ = frame
    shoulder = (
        float(skeleton["landmarks"]["shoulder"]["x"]),
        float(skeleton["landmarks"]["shoulder"]["y"]),
    )
    trimmed_upper_s = [
        (x + 0.5 - shoulder[0]) * upper_axis[0]
        + (y + 0.5 - shoulder[1]) * upper_axis[1]
        for x, y in V6_MODULE.mask_pixels(chosen_images["simulatedUpper"]) or []
    ]
    raster_extension = max(trimmed_upper_s) - length1
    ownership_preserving_scan, ownership_preserving_dense = V6_MODULE.elbow_scan(
        upper_geometry,
        visible_forearm,
        [
            (-1.0, -18.0),
            (22.0, -17.0),
            (130.0, -10.0),
            (130.0, 10.0),
            (22.0, 15.0),
            (-1.0, 13.0),
        ],
        skeleton,
        frame,
        primary,
        extremes,
    )
    _, elbow, _, _, _, _, forearm_axis, _ = frame
    current_forearm_s = local_s_range(visible_forearm, elbow, forearm_axis)
    ownership_preserving_alternative = {
        "name": "preserve_approved_elbow_ownership_and_share_union_coverage",
        "visibleUpperOwnershipPixelsReassignedToForearm": 0,
        "upperGeometryTrimPixels": 0,
        "currentForearmLocalSRangePx": current_forearm_s,
        "forearmExtensionBehindElbowPx": max(0.0, -current_forearm_s[0]),
        "maximumMissingResponsibilityPixelsAt4x": ownership_preserving_scan[
            "maximumMissingResponsibilityPixelsAt4x"
        ],
        "brokenAdjacencySamples": ownership_preserving_scan[
            "brokenAdjacencySamples"
        ],
        "maximumInnerBendExposedUpperPixelsAt4x": ownership_preserving_scan[
            "maximumInnerBendExposedUpperPixelsAt4x"
        ],
        "worstInnerBendExposureTheta2Deg": ownership_preserving_scan[
            "worstInnerBendExposureTheta2Deg"
        ],
        "denseSamplesWithInnerBendExposure": sum(
            item["innerBendExposedUpperPixelsAt4x"] > 0
            for item in ownership_preserving_dense
        ),
        "preservesApprovedElbowOwnershipLine": True,
        "passesCurrentFrozenForearm15PxRule": False,
        "passesCurrentZeroInnerExposureRule": False,
        "contractRewriteRequired": True,
        "notApproved": True,
    }
    report = {
        "schemaVersion": 1,
        "gate": "V7-A V6 elbow joint successor threshold-family candidate",
        "status": "engineering_tradeoff_pending_user_contract_choice",
        "scope": (
            "V7-local successor copies only; frozen V4, sleeve, and V6 files remain unchanged"
        ),
        "selectionRule": (
            "among candidates that preserve at least 15 px root responsibility and "
            "pass the exact V6 scan, minimize visible upper ownership reassignment, "
            "then minimize upper trim pixels"
        ),
        "parameterDomain": {
            "primarySamples": len(primary),
            "combinationExtremes": len(extremes),
            "denseTheta2Samples": len(dense_angles),
            "allEvaluationsIncludingRepeatedAngles": len(all_angles),
            "theta2RangeDeg": [
                skeleton["allowedRangesDeg"]["theta2"]["min"],
                skeleton["allowedRangesDeg"]["theta2"]["max"],
            ],
            "supersampling": SS,
            "alphaThreshold": ALPHA_THRESHOLD,
        },
        "alternatives": results,
        "selected": {
            **chosen,
            "simulatedUpperRasterCenterExtensionBeyondElbowPx": raster_extension,
            "simulatedUpperRasterExtensionPasses15Px": raster_extension >= 15.0,
            "forearmOwnershipPixelCountIncludingMergedBracelet": mask_count(
                chosen_images["candidateForearm"]
            ),
            "selectedRootConnectedComponents": BASE.connected_components(
                chosen_images["selectedRoot"]
            ),
            "candidateForearmConnectedComponents": BASE.connected_components(
                chosen_images["candidateForearm"]
            ),
            "visualPreflight": {
                "status": "risk_large_moving_wedge",
                "reason": (
                    "384 source-visible upper-arm pixels form a wedge that follows "
                    "the forearm and visibly supersedes the approved elbow line"
                ),
                "userVisualApproval": False,
            },
        },
        "ownershipPreservingAlternative": ownership_preserving_alternative,
        "contractRevision": {
            "oldFrozenEnvelopeSuperseded": True,
            "successorEnvelopeDefinition": (
                "frozen proxy intersect approved source-arm support, then restricted "
                "by selected forearm-local s threshold"
            ),
            "oldElbowOwnershipLineSuperseded": True,
            "newVisibleOwnershipRequiresUserApproval": True,
            "braceletPolicyUnchanged": (
                "bracelet remains merged into the forearm; no independent runtime layer"
            ),
            "automaticInvalidation": [
                "any change to frozen elbow, wrist, L1, L2, or theta2 range",
                "production forearm does not contain the selected successor envelope",
                "successor upper geometry differs from the approved V7-local copy",
                "real production forearm elbow scan produces any gap, break, or inner exposure",
            ],
        },
        "notPerformed": [
            "no frozen V6 byte changed",
            "no complete production forearm geometry",
            "no texture, PSD, Cubism, Physics, or Runtime",
            "no bone-length or motion-range reduction",
        ],
        "inputHashes": {
            "userDecision": sha256(USER_DECISION_PATH),
            "frozenUpperGeometry": sha256(UPPER_GEOMETRY_PATH),
            "frozenVisibleUpper": sha256(UPPER_VISIBLE_PATH),
            "updatedVisibleForearm": sha256(VISIBLE_FOREARM_PATH),
        },
        "visualEvidence": {
            "reviewBoard": "qa/V7-A-JOINT-REPAIR-CANDIDATE-BOARD.png",
            "slowElbowSweep": "qa/V7-A-JOINT-REPAIR-CANDIDATE-SLOW-SCAN.gif",
            "threeAngles": "qa/V7-A-JOINT-REPAIR-CANDIDATE-THREE-ANGLES.png",
            "structureComparisonSlowSweep": (
                "qa/V7-A-ELBOW-STRUCTURE-COMPARISON-SLOW-SCAN.gif"
            ),
            "structureComparisonThreeAngles": (
                "qa/V7-A-ELBOW-STRUCTURE-COMPARISON-THREE-ANGLES.png"
            ),
            "visualDecisionPending": True,
        },
    }
    report_path = AUDIT / "v7a-joint-repair-candidate.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    make_board(
        report["selected"],
        chosen_images,
        old_envelope,
        source_support,
        upper_geometry,
        upper_visible,
        color,
        skeleton,
        frame,
    )
    make_motion_review(
        skeleton,
        frame,
        chosen_images["simulatedUpper"],
        chosen_images["candidateForearm"],
        chosen_images["reassigned"],
    )
    make_structure_comparison(
        skeleton,
        frame,
        upper_geometry,
        visible_forearm,
        chosen_images["simulatedUpper"],
        chosen_images["candidateForearm"],
        chosen_images["reassigned"],
    )

    selected = report["selected"]
    markdown = f"""# V7-A：V6 肘部后继合同阈值族候选

## 结论

已在 V7 内声明的 8 个回伸阈值候选中找到一个工程可行项，但它会大幅改变已批准的肘侧可见所有权，因此只作为决策证据，不能直接生成完整前臂，也不声称是所有可能拓扑中的全局最优。

- 选中局部阈值：`s >= {selected['thresholdLocalSPx']:.2f} px`。
- 实际向肘后回伸：`{selected['rootExtensionBehindElbowPx']:.6f} px`，满足 `15 px` 责任下界。
- 从冻结可见上臂转给前臂：`{selected['visibleUpperOwnershipPixelsReassignedToForearm']} px`。
- 上臂复制件最小修剪：`{selected['upperGeometryTrimPixels']} px`，其中可见像素 `{selected['visibleUpperTrimPixels']} px`、隐藏像素 `{selected['hiddenUpperTrimPixels']} px`。
- 修剪前最坏内弯暴露：`{selected['worstPreTrimExposureAt4x']}` 个 4× 子像素。
- 修剪后：透明缺口 `0`、断开样本 `0`、内弯暴露 `0`。
- 修剪后上臂栅格中心延伸：`{selected['simulatedUpperRasterCenterExtensionBeyondElbowPx']:.6f} px`，仍大于 `15 px`。

## 为什么选择它

比较了 `{len(results)}` 个回伸阈值。选择规则是：先满足 `15 px` 根部责任和完整 V6 扫描，再最小化需要转移的可见上臂所有权，最后最小化上臂修剪量。

阈值再缩到 `-15.00 px` 时，实际栅格回伸只有 `{next(item for item in results if item['thresholdLocalSPx'] == -15.0)['rootExtensionBehindElbowPx']:.6f} px`，已经低于冻结 `15 px` 下界，因此不能采用。

## 参数与验证

- 41 个主路径样本。
- 6 个组合极值。
- 241 点肘角密扫，间隔 `0.1°`。
- 4× 超采样，alpha 阈值 `16`。
- 骨长、肘点、腕点和动作范围均未改变。

## 必须重新批准的内容

该候选不再沿用原来的 `s=0` 可见肘线：有 `{selected['visibleUpperOwnershipPixelsReassignedToForearm']} px` 从上臂所有权转入前臂。审查板中的紫色区域就是需要重新批准的边界变化。

三角度视觉预检把它标记为“移动楔形补丁风险”，因此不能因为数值为 0 就自动采用。

## 保留原肘线的对照

另行重跑了“不转移任何可见所有权、不修剪冻结上臂”的共享覆盖对照：

- 责任区透明缺口：`{ownership_preserving_alternative['maximumMissingResponsibilityPixelsAt4x']}`；
- 断开样本：`{ownership_preserving_alternative['brokenAdjacencySamples']}`；
- 内弯仍可见上臂：最坏 `{ownership_preserving_alternative['maximumInnerBendExposedUpperPixelsAt4x']}` 个 4× 子像素；
- 前臂向肘后回伸：`{ownership_preserving_alternative['forearmExtensionBehindElbowPx']:.6f} px`。

它视觉上保留原肘线，但不满足旧合同的“前臂回伸 15 px”和“内弯上臂暴露 0”，只能在用户明确批准重写责任定义后继续，当前同样不是通过项。

当前只批准该后继肘侧所有权和上臂末端复制件，仍不等于批准完整前臂、纹理、PSD、Cubism、Physics 或 Runtime。
"""
    markdown_path = AUDIT / "V7-A-JOINT-REPAIR-CANDIDATE.zh-CN.md"
    markdown_path.write_text(markdown, encoding="utf-8")

    generated = [
        report_path,
        markdown_path,
        QA / "V7-A-JOINT-REPAIR-CANDIDATE-BOARD.png",
        QA / "V7-A-JOINT-REPAIR-CANDIDATE-SLOW-SCAN.gif",
        QA / "V7-A-JOINT-REPAIR-CANDIDATE-THREE-ANGLES.png",
        QA / "V7-A-ELBOW-STRUCTURE-COMPARISON-SLOW-SCAN.gif",
        QA / "V7-A-ELBOW-STRUCTURE-COMPARISON-THREE-ANGLES.png",
    ]
    generated.extend(MASKS / name for name in output_masks)
    manifest = {
        "schemaVersion": 1,
        "gate": "V7-A joint repair candidate evidence",
        "status": report["status"],
        "checksumAlgorithm": "SHA-256",
        "files": [
            {
                "path": path.relative_to(REOPEN).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in generated
        ],
    }
    manifest_path = AUDIT / "v7a-joint-repair-evidence-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "selectedThreshold": selected["thresholdLocalSPx"],
                "rootExtensionPx": selected["rootExtensionBehindElbowPx"],
                "visibleOwnershipReassignedPx": selected[
                    "visibleUpperOwnershipPixelsReassignedToForearm"
                ],
                "upperTrimPx": selected["upperGeometryTrimPixels"],
                "postTrimGap4x": selected[
                    "postTrimMaximumMissingResponsibilityPixelsAt4x"
                ],
                "postTrimInnerExposure4x": selected[
                    "postTrimMaximumInnerBendExposureAt4x"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
