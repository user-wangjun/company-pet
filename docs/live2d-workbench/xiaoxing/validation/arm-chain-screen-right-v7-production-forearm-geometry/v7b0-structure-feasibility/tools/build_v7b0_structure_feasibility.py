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
REOPEN = V7 / "v6-elbow-contract-reopen"

AUDIT = ROOT / "audit"
MASKS = ROOT / "masks"
QA = ROOT / "qa"

BASE_BUILDER = REOPEN / "tools/build_v7a_elbow_contract_reopen.py"
OWNERSHIP_BUILDER = V7 / "tools/build_v7a_ownership_gate.py"
AUTHORIZATION_PATH = AUDIT / "v7b0-user-authorization-2026-07-26.json"
REJECTION_PATH = AUDIT / "v7b0-user-visual-rejection-2026-07-26.json"

SKELETON_PATH = V4 / "skeleton.json"
UPPER_GEOMETRY_PATH = V6 / "masks/upper-arm-complete-geometry.png"
UPPER_VISIBLE_PATH = V6 / "masks/reference/visible-upper-arm-locked-reference.png"
SLEEVE_PATH = V5 / "complete-sleeve-final/inputs/sleeve-complete-geometry-r9.png"
OLD_ENVELOPE_PATH = V7 / "masks/v6-minimum-envelope-neutral-footprint.png"
VISIBLE_FOREARM_PATH = V7 / "masks/visible-forearm-locked.png"
SOURCE_SUPPORT_PATH = V7 / "masks/source-arm-neutral-outline-candidate.png"
USER_DECISION_PATH = V7 / "audit/v7a-user-visual-decision-2026-07-26.json"

SS = 4
ALPHA_THRESHOLD = 16
CROP_RADIUS = 54


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_module("v7b0_base", BASE_BUILDER)
OWNERSHIP = load_module("v7b0_ownership", OWNERSHIP_BUILDER)
V6_MODULE = BASE.V6_MODULE


def ensure_directories() -> None:
    for directory in (AUDIT, MASKS, QA):
        directory.mkdir(parents=True, exist_ok=True)


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
    if image.mode == "L":
        return binary(image)
    return binary(image.convert("RGBA").getchannel("A"), ALPHA_THRESHOLD)


def mask_count(mask: Image.Image) -> int:
    return sum(binary(mask).histogram()[1:])


def mask_pixels(mask: Image.Image):
    core = binary(mask)
    pixels = core.load()
    bbox = core.getbbox()
    if bbox is None:
        return
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            if pixels[x, y]:
                yield x, y


def connected_components(mask: Image.Image) -> int:
    points = set(mask_pixels(mask) or [])
    components = 0
    while points:
        components += 1
        stack = [points.pop()]
        while stack:
            x, y = stack.pop()
            for neighbor in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            ):
                if neighbor in points:
                    points.remove(neighbor)
                    stack.append(neighbor)
    return components


def hole_mask(mask: Image.Image) -> Image.Image:
    core = binary(mask)
    result = Image.new("L", core.size, 0)
    bbox = core.getbbox()
    if bbox is None:
        return result
    box = (
        max(0, bbox[0] - 1),
        max(0, bbox[1] - 1),
        min(core.width, bbox[2] + 1),
        min(core.height, bbox[3] + 1),
    )
    inverse = ImageChops.invert(core.crop(box))
    pixels = inverse.load()
    outside: set[tuple[int, int]] = set()
    stack: list[tuple[int, int]] = []
    for x in range(inverse.width):
        for y in (0, inverse.height - 1):
            if pixels[x, y] and (x, y) not in outside:
                outside.add((x, y))
                stack.append((x, y))
    for y in range(inverse.height):
        for x in (0, inverse.width - 1):
            if pixels[x, y] and (x, y) not in outside:
                outside.add((x, y))
                stack.append((x, y))
    while stack:
        x, y = stack.pop()
        for neighbor in (
            (x - 1, y),
            (x + 1, y),
            (x, y - 1),
            (x, y + 1),
        ):
            nx, ny = neighbor
            if (
                0 <= nx < inverse.width
                and 0 <= ny < inverse.height
                and pixels[nx, ny]
                and neighbor not in outside
            ):
                outside.add(neighbor)
                stack.append(neighbor)
    holes = Image.new("L", inverse.size, 0)
    holes_pixels = holes.load()
    for y in range(inverse.height):
        for x in range(inverse.width):
            if pixels[x, y] and (x, y) not in outside:
                holes_pixels[x, y] = 255
    result.paste(holes, (box[0], box[1]))
    return result


def rgba_mask(mask: Image.Image) -> Image.Image:
    output = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    output.putalpha(binary(mask))
    return output


def crop_box(elbow: tuple[float, float]) -> tuple[int, int, int, int]:
    return (
        round(elbow[0] - CROP_RADIUS),
        round(elbow[1] - CROP_RADIUS),
        round(elbow[0] + CROP_RADIUS),
        round(elbow[1] + CROP_RADIUS),
    )


def high_mask(mask: Image.Image, box) -> Image.Image:
    size = ((box[2] - box[0]) * SS, (box[3] - box[1]) * SS)
    return binary(mask.crop(box)).resize(size, Image.Resampling.NEAREST)


def rotate_high(
    mask: Image.Image,
    box,
    center: tuple[float, float],
    delta_angle: float,
) -> Image.Image:
    rotated = high_mask(mask, box).rotate(
        delta_angle,
        resample=Image.Resampling.BICUBIC,
        center=center,
        fillcolor=0,
    )
    return binary(rotated, ALPHA_THRESHOLD)


def inner_exposure_count(
    visible_upper: Image.Image,
    center: tuple[float, float],
    responsibility_axis: tuple[float, float],
    responsibility_normal: tuple[float, float],
    delta_angle: float,
) -> int:
    angle = math.radians(delta_angle)
    cosine, sine = math.cos(angle), math.sin(angle)
    current_axis = (
        cosine * responsibility_axis[0] - sine * responsibility_axis[1],
        sine * responsibility_axis[0] + cosine * responsibility_axis[1],
    )
    current_normal = (
        cosine * responsibility_normal[0] - sine * responsibility_normal[1],
        sine * responsibility_normal[0] + cosine * responsibility_normal[1],
    )
    count = 0
    for x, y in mask_pixels(visible_upper) or []:
        dx = (x + 0.5 - center[0]) / SS
        dy = (y + 0.5 - center[1]) / SS
        local_s = dx * current_axis[0] + dy * current_axis[1]
        local_n = dx * current_normal[0] + dy * current_normal[1]
        if -12.0 <= local_s <= 8.0 and local_n < 0.0:
            count += 1
    return count


def evaluate_angle(
    theta2: float,
    skeleton: dict,
    frame,
    upper_geometry: Image.Image,
    sleeve: Image.Image,
    visible_forearm: Image.Image,
    hidden_root: Image.Image,
) -> dict:
    _, elbow, _, _, responsibility_axis, responsibility_normal, _, _ = frame
    box = crop_box(elbow)
    size = ((box[2] - box[0]) * SS, (box[3] - box[1]) * SS)
    center = (
        (elbow[0] - box[0]) * SS,
        (elbow[1] - box[1]) * SS,
    )
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    delta = theta2 - rest

    upper = binary(high_mask(upper_geometry, box), ALPHA_THRESHOLD)
    sleeve_high = binary(high_mask(sleeve, box), ALPHA_THRESHOLD)
    visible = rotate_high(visible_forearm, box, center, delta)
    hidden = rotate_high(hidden_root, box, center, delta)

    responsibility = Image.new("L", size, 0)
    draw = ImageDraw.Draw(responsibility)
    radius = 9.0 * SS
    draw.ellipse(
        (
            center[0] - radius,
            center[1] - radius,
            center[0] + radius,
            center[1] + radius,
        ),
        fill=255,
    )

    single_union = ImageChops.lighter(upper, visible)
    split_moving = ImageChops.lighter(visible, hidden)
    split_union = ImageChops.lighter(upper, split_moving)
    single_missing = ImageChops.subtract(responsibility, single_union)
    split_missing = ImageChops.subtract(responsibility, split_union)
    single_overlap = ImageChops.multiply(upper, visible)
    split_overlap = ImageChops.multiply(upper, split_moving)

    # H_root is below the upper arm and sleeve, while V_forearm remains above.
    # Therefore H_root cannot occlude upper-arm pixels. Only the part outside
    # upper/sleeve and not covered by V_forearm is visible in the split probe.
    hidden_occluders = ImageChops.lighter(
        ImageChops.lighter(upper, sleeve_high),
        visible,
    )
    visible_hidden_root = ImageChops.subtract(hidden, hidden_occluders)

    # Composition-aware upper visibility is identical for the two probes:
    # only V_forearm is above U; H_root is explicitly below U.
    visible_upper = ImageChops.subtract(upper, visible)
    composition_aware_inner_exposure = inner_exposure_count(
        visible_upper,
        center,
        responsibility_axis,
        responsibility_normal,
        delta,
    )

    # This legacy counter shows what would happen only if H_root were drawn
    # above U. It is diagnostic and cannot be used to pass the split probe.
    legacy_front_order_visible_upper = ImageChops.subtract(upper, split_moving)
    legacy_front_order_inner_exposure = inner_exposure_count(
        legacy_front_order_visible_upper,
        center,
        responsibility_axis,
        responsibility_normal,
        delta,
    )

    return {
        "theta2": theta2,
        "single": {
            "missingResponsibilityPixelsAt4x": mask_count(single_missing),
            "connectedByOverlap": single_overlap.getbbox() is not None,
            "compositionAwareInnerUpperExposureAt4x": (
                composition_aware_inner_exposure
            ),
        },
        "split": {
            "missingResponsibilityPixelsAt4x": mask_count(split_missing),
            "connectedByOverlap": split_overlap.getbbox() is not None,
            "compositionAwareInnerUpperExposureAt4x": (
                composition_aware_inner_exposure
            ),
            "legacyIfHiddenRootWereAboveInnerExposureAt4x": (
                legacy_front_order_inner_exposure
            ),
            "visibleHiddenRootPixelsAt4x": mask_count(visible_hidden_root),
            "visibleHiddenRootComponents": connected_components(
                visible_hidden_root
            ),
        },
    }


def summarize_scan(rows: list[dict], key: str) -> dict:
    candidate = [row[key] | {"theta2": row["theta2"]} for row in rows]
    worst_gap = max(candidate, key=lambda item: item["missingResponsibilityPixelsAt4x"])
    worst_inner = max(
        candidate,
        key=lambda item: item["compositionAwareInnerUpperExposureAt4x"],
    )
    result = {
        "maximumMissingResponsibilityPixelsAt4x": worst_gap[
            "missingResponsibilityPixelsAt4x"
        ],
        "worstGapTheta2Deg": worst_gap["theta2"],
        "brokenAdjacencySamples": sum(
            not item["connectedByOverlap"] for item in candidate
        ),
        "maximumCompositionAwareInnerUpperExposureAt4x": worst_inner[
            "compositionAwareInnerUpperExposureAt4x"
        ],
        "worstCompositionAwareInnerExposureTheta2Deg": worst_inner["theta2"],
    }
    if key == "split":
        worst_visible = max(
            candidate,
            key=lambda item: item["visibleHiddenRootPixelsAt4x"],
        )
        worst_legacy = max(
            candidate,
            key=lambda item: item[
                "legacyIfHiddenRootWereAboveInnerExposureAt4x"
            ],
        )
        result |= {
            "maximumVisibleHiddenRootPixelsAt4x": worst_visible[
                "visibleHiddenRootPixelsAt4x"
            ],
            "worstVisibleHiddenRootTheta2Deg": worst_visible["theta2"],
            "maximumVisibleHiddenRootComponents": max(
                item["visibleHiddenRootComponents"] for item in candidate
            ),
            "maximumLegacyIfHiddenRootWereAboveInnerExposureAt4x": worst_legacy[
                "legacyIfHiddenRootWereAboveInnerExposureAt4x"
            ],
            "worstLegacyIfHiddenRootWereAboveTheta2Deg": worst_legacy["theta2"],
        }
    return result


def render_body(
    theta2: float,
    skeleton: dict,
    frame,
    upper_geometry: Image.Image,
    sleeve: Image.Image,
    visible_forearm: Image.Image,
    hidden_root: Image.Image,
    split: bool,
    diagnostic: bool,
) -> Image.Image:
    _, elbow, _, _, _, _, _, _ = frame
    box = crop_box(elbow)
    size = ((box[2] - box[0]) * SS, (box[3] - box[1]) * SS)
    center = (
        (elbow[0] - box[0]) * SS,
        (elbow[1] - box[1]) * SS,
    )
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    delta = theta2 - rest
    upper = binary(high_mask(upper_geometry, box), ALPHA_THRESHOLD)
    sleeve_high = binary(high_mask(sleeve, box), ALPHA_THRESHOLD)
    visible = rotate_high(visible_forearm, box, center, delta)
    hidden = rotate_high(hidden_root, box, center, delta)

    body = Image.new("RGB", size, (255, 255, 255))
    if split:
        body.paste(
            (145, 82, 210) if diagnostic else (66, 187, 174),
            mask=hidden,
        )
    body.paste((236, 144, 92), mask=upper)
    body.paste((66, 187, 174), mask=visible)
    body.paste((164, 174, 189), mask=sleeve_high)
    return body


def labeled_frame(
    theta2: float,
    skeleton: dict,
    frame,
    upper_geometry: Image.Image,
    sleeve: Image.Image,
    visible_forearm: Image.Image,
    hidden_root: Image.Image,
    diagnostic: bool,
) -> Image.Image:
    single = render_body(
        theta2,
        skeleton,
        frame,
        upper_geometry,
        sleeve,
        visible_forearm,
        hidden_root,
        split=False,
        diagnostic=diagnostic,
    )
    split = render_body(
        theta2,
        skeleton,
        frame,
        upper_geometry,
        sleeve,
        visible_forearm,
        hidden_root,
        split=True,
        diagnostic=diagnostic,
    )
    gap = 14
    header = 86
    result = Image.new(
        "RGB",
        (single.width + split.width + gap, single.height + header),
        (240, 240, 240),
    )
    draw = ImageDraw.Draw(result)
    draw.text(
        (12, 8),
        f"θ2={theta2:.3f}°",
        font=BASE.font(22),
        fill=(25, 25, 25),
    )
    draw.text(
        (12, 38),
        "S｜单一前臂\n批准肘线不变",
        font=BASE.font(15),
        fill=(55, 55, 55),
        spacing=2,
    )
    draw.text(
        (single.width + gap + 12, 38),
        (
            "D｜分层隐藏根部\n紫=实际可见H_root"
            if diagnostic
            else "D｜分层隐藏根部\nH_root使用同色"
        ),
        font=BASE.font(15),
        fill=(55, 55, 55),
        spacing=2,
    )
    result.paste(single, (0, header))
    result.paste(split, (single.width + gap, header))
    return result


def make_three_angle_board(
    skeleton: dict,
    frame,
    upper_geometry: Image.Image,
    sleeve: Image.Image,
    visible_forearm: Image.Image,
    hidden_root: Image.Image,
    diagnostic: bool,
) -> None:
    angles = [
        float(skeleton["allowedRangesDeg"]["theta2"]["min"]),
        float(skeleton["restAnglesDeg"]["theta2"]),
        float(skeleton["allowedRangesDeg"]["theta2"]["max"]),
    ]
    labels = ("最弯", "中性", "近直")
    frames = [
        labeled_frame(
            angle,
            skeleton,
            frame,
            upper_geometry,
            sleeve,
            visible_forearm,
            hidden_root,
            diagnostic,
        )
        for angle in angles
    ]
    header = 72
    gap = 10
    width = sum(item.width for item in frames) + gap * (len(frames) + 1)
    height = max(item.height for item in frames) + header + 10
    board = Image.new("RGB", (width, height), (236, 236, 236))
    draw = ImageDraw.Draw(board)
    draw.text(
        (18, 12),
        (
            "V7-B0｜分层隐藏根部暴露诊断（紫色仅用于识别）"
            if diagnostic
            else "V7-B0｜两种肘部结构实际同色对照"
        ),
        font=BASE.font(30),
        fill=(24, 24, 24),
    )
    x = gap
    for label, item in zip(labels, frames):
        draw.text(
            (x + 8, 48),
            label,
            font=BASE.font(17),
            fill=(70, 70, 70),
        )
        board.paste(item, (x, header))
        x += item.width + gap
    name = (
        "V7-B0-SPLIT-HIDDEN-ROOT-DIAGNOSTIC-THREE-ANGLES.png"
        if diagnostic
        else "V7-B0-STRUCTURE-COMPARISON-THREE-ANGLES.png"
    )
    board.save(QA / name)


def make_slow_sweep(
    skeleton: dict,
    frame,
    upper_geometry: Image.Image,
    sleeve: Image.Image,
    visible_forearm: Image.Image,
    hidden_root: Image.Image,
) -> None:
    minimum = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    maximum = float(skeleton["allowedRangesDeg"]["theta2"]["max"])
    forward = [
        minimum + (maximum - minimum) * index / 30.0
        for index in range(31)
    ]
    sweep = forward + forward[-2:0:-1]
    frames = [
        labeled_frame(
            theta,
            skeleton,
            frame,
            upper_geometry,
            sleeve,
            visible_forearm,
            hidden_root,
            diagnostic=True,
        )
        for theta in sweep
    ]
    frames[0].save(
        QA / "V7-B0-STRUCTURE-COMPARISON-SLOW-SCAN.gif",
        save_all=True,
        append_images=frames[1:],
        duration=105,
        loop=0,
        disposal=2,
        optimize=False,
    )


def make_partition_board(
    old_envelope: Image.Image,
    visible_forearm: Image.Image,
    upper_visible: Image.Image,
    sleeve: Image.Image,
    hidden_root: Image.Image,
    residual: Image.Image,
    source_support: Image.Image,
) -> None:
    crop = (326, 379, 390, 448)
    outside = ImageChops.subtract(old_envelope, source_support)
    base = Image.new("RGBA", old_envelope.size, (255, 255, 255, 255))
    classified = BASE.tint(
        base,
        [
            (old_envelope, (210, 210, 210, 170)),
            (ImageChops.multiply(old_envelope, visible_forearm), (50, 185, 170, 235)),
            (ImageChops.multiply(old_envelope, upper_visible), (236, 120, 70, 235)),
            (ImageChops.multiply(hidden_root, sleeve), (120, 135, 160, 245)),
            (residual, (235, 35, 45, 245)),
        ],
    ).crop(crop)
    outside_review = BASE.tint(
        base,
        [
            (old_envelope, (220, 45, 165, 125)),
            (outside, (255, 195, 0, 235)),
            (ImageChops.multiply(outside, sleeve), (70, 110, 220, 245)),
            (ImageChops.multiply(outside, residual), (235, 35, 45, 245)),
        ],
    ).crop(crop)
    hidden_review = BASE.tint(
        base,
        [
            (visible_forearm, (50, 185, 170, 150)),
            (hidden_root, (145, 82, 210, 235)),
            (residual, (235, 35, 45, 245)),
        ],
    ).crop(crop)

    items = [
        (
            "A 的互斥分区",
            "青=V 622；橙=U 416；灰蓝=袖下39；红=无登记遮挡100",
            classified,
        ),
        (
            "轮廓外 132 px",
            "蓝=袖子可遮39；红=仍在背景侧93",
            outside_review,
        ),
        (
            "可登记 H_root",
            "紫=455 px；红=不能并入中性隐藏根部的100 px",
            hidden_review,
        ),
    ]
    panel_width, panel_height = 700, 680
    board = Image.new(
        "RGB",
        (panel_width * 3 + 40, panel_height + 105),
        (238, 238, 238),
    )
    draw = ImageDraw.Draw(board)
    draw.text(
        (24, 16),
        "V7-B0｜旧代理 1177 px 的真实分区",
        font=BASE.font(34),
        fill=(24, 24, 24),
    )
    draw.text(
        (24, 60),
        "只有被上臂或袖子中性遮挡的 455 px 能进入分层 H_root 探针；100 px 必须排除。",
        font=BASE.font(20),
        fill=(65, 65, 65),
    )
    for index, (title, subtitle, image) in enumerate(items):
        x = 10 + index * panel_width
        draw.text(
            (x + 16, 112),
            title,
            font=BASE.font(26),
            fill=(30, 30, 30),
        )
        draw.text(
            (x + 16, 150),
            subtitle,
            font=BASE.font(16),
            fill=(70, 70, 70),
        )
        content = image.resize((512, 552), Image.Resampling.NEAREST).convert("RGB")
        board.paste(content, (x + 90, 192))
    board.save(QA / "V7-B0-OLD-PROXY-PARTITION-BOARD.png")


def make_hole_diagnostic(
    visible_forearm: Image.Image,
    hidden_root: Image.Image,
    split_probe: Image.Image,
) -> None:
    holes = hole_mask(split_probe)
    crop = (326, 379, 406, 472)
    base = Image.new("RGBA", split_probe.size, (255, 255, 255, 255))
    combined = BASE.tint(
        base,
        [
            (visible_forearm, (50, 185, 170, 210)),
            (hidden_root, (145, 82, 210, 220)),
            (holes, (235, 35, 45, 255)),
        ],
    ).crop(crop)
    displaced = BASE.tint(
        base,
        [
            (hidden_root, (145, 82, 210, 235)),
            (holes, (235, 35, 45, 255)),
        ],
    ).crop(crop)
    board = Image.new("RGB", (1420, 780), (238, 238, 238))
    draw = ImageDraw.Draw(board)
    draw.text(
        (24, 16),
        "V7-B0｜分层前臂语义并集存在 2 个孔",
        font=BASE.font(34),
        fill=(24, 24, 24),
    )
    draw.text(
        (24, 60),
        "红=孔洞；青=批准 V_forearm；紫=登记 H_root。孔洞不因中性遮挡而变成合法材料。",
        font=BASE.font(20),
        fill=(65, 65, 65),
    )
    draw.text(
        (90, 112),
        "语义并集",
        font=BASE.font(26),
        fill=(35, 35, 35),
    )
    draw.text(
        (800, 112),
        "H_root 单独移开",
        font=BASE.font(26),
        fill=(35, 35, 35),
    )
    board.paste(
        combined.resize((600, 600), Image.Resampling.NEAREST).convert("RGB"),
        (40, 155),
    )
    board.paste(
        displaced.resize((600, 600), Image.Resampling.NEAREST).convert("RGB"),
        (750, 155),
    )
    board.save(QA / "V7-B0-SPLIT-PROBE-HOLE-DIAGNOSTIC.png")


def main() -> None:
    ensure_directories()

    authorization = json.loads(AUTHORIZATION_PATH.read_text(encoding="utf-8"))
    if authorization["status"] != "authorized_structure_feasibility_comparison_only":
        raise RuntimeError("V7-B0 user authorization is missing.")
    rejection = (
        json.loads(REJECTION_PATH.read_text(encoding="utf-8"))
        if REJECTION_PATH.exists()
        else None
    )
    decision = json.loads(USER_DECISION_PATH.read_text(encoding="utf-8"))
    if not (
        decision["approvedItems"].get("visibleForearmCandidate") is True
        and decision["approvedItems"].get("elbowOwnershipLine") is True
        and decision["approvedItems"].get("wristOwnershipLine") is True
        and decision["approvedItems"].get("braceletMergedIntoForearmMaterial")
        is True
        and decision["approvedItems"].get("dependencyReopenAuthorization") is True
    ):
        raise RuntimeError("Required V7-A decisions are not present.")

    fresh_integrity = OWNERSHIP.verify_inputs()
    if fresh_integrity["status"] != "pass":
        raise RuntimeError("Frozen or authority input integrity failed.")

    skeleton = json.loads(SKELETON_PATH.read_text(encoding="utf-8"))
    frame = V6_MODULE.local_frame(skeleton)
    primary = V6_MODULE.primary_states(skeleton)
    extremes = V6_MODULE.extreme_states(skeleton)

    old_envelope = load_mask(OLD_ENVELOPE_PATH)
    visible_forearm = load_mask(VISIBLE_FOREARM_PATH)
    source_support = load_mask(SOURCE_SUPPORT_PATH)
    upper_visible = load_mask(UPPER_VISIBLE_PATH)
    upper_geometry = load_mask(UPPER_GEOMETRY_PATH)
    sleeve = load_mask(SLEEVE_PATH)

    old_without_visible = ImageChops.subtract(old_envelope, visible_forearm)
    registered_occluders = ImageChops.lighter(upper_visible, sleeve)
    hidden_root = ImageChops.multiply(old_without_visible, registered_occluders)
    residual = ImageChops.subtract(old_without_visible, registered_occluders)
    single_probe = visible_forearm.copy()
    split_probe = ImageChops.lighter(visible_forearm, hidden_root)

    partitions = {
        "frozenEnvelope": mask_count(old_envelope),
        "alreadyVisibleForearm": mask_count(
            ImageChops.multiply(old_envelope, visible_forearm)
        ),
        "frozenVisibleUpper": mask_count(
            ImageChops.multiply(old_envelope, upper_visible)
        ),
        "registeredSleeveOnly": mask_count(
            ImageChops.multiply(
                old_envelope,
                ImageChops.multiply(
                    sleeve,
                    ImageChops.invert(
                        ImageChops.lighter(visible_forearm, upper_visible)
                    ),
                ),
            )
        ),
        "unregisteredResidual": mask_count(residual),
        "residualOutsideSourceSupport": mask_count(
            ImageChops.multiply(residual, ImageChops.invert(source_support))
        ),
        "residualInsideSourceSupport": mask_count(
            ImageChops.multiply(residual, source_support)
        ),
    }
    if sum(
        partitions[key]
        for key in (
            "alreadyVisibleForearm",
            "frozenVisibleUpper",
            "registeredSleeveOnly",
            "unregisteredResidual",
        )
    ) != partitions["frozenEnvelope"]:
        raise RuntimeError("The V7-B0 partition is not exhaustive and exclusive.")

    neutral_hidden_visible = ImageChops.subtract(
        hidden_root,
        ImageChops.lighter(
            ImageChops.lighter(upper_geometry, sleeve),
            visible_forearm,
        ),
    )

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
    dense_rows = [
        evaluate_angle(
            theta,
            skeleton,
            frame,
            upper_geometry,
            sleeve,
            visible_forearm,
            hidden_root,
        )
        for theta in dense_angles
    ]
    repeated_rows = [
        evaluate_angle(
            float(state["theta2"]),
            skeleton,
            frame,
            upper_geometry,
            sleeve,
            visible_forearm,
            hidden_root,
        )
        for state in primary + extremes
    ]
    all_rows = dense_rows + repeated_rows

    single_summary = summarize_scan(all_rows, "single")
    split_summary = summarize_scan(all_rows, "split")
    rest_theta = float(skeleton["restAnglesDeg"]["theta2"])
    neutral_row = evaluate_angle(
        rest_theta,
        skeleton,
        frame,
        upper_geometry,
        sleeve,
        visible_forearm,
        hidden_root,
    )

    report = {
        "schemaVersion": 1,
        "gate": "V7-B0 elbow structure feasibility comparison",
        "status": (
            "split_probe_engineering_and_user_visual_fail_"
            "single_baseline_unresolved"
            if rejection is not None
            else (
                "split_probe_engineering_fail_"
                "single_baseline_pending_user_visual_review"
            )
        ),
        "scope": (
            "V7-local structure probes only; no production forearm geometry "
            "and no contract rewrite"
        ),
        "frozenIntegrity": {
            "status": fresh_integrity["status"],
            "groups": [
                {
                    "name": group["name"],
                    "checked": group["checked"],
                    "passed": group["passed"],
                    "failed": group["failed"],
                }
                for group in fresh_integrity["frozenArtifactGroups"]
            ],
        },
        "authorization": {
            "path": "audit/v7b0-user-authorization-2026-07-26.json",
            "sha256": sha256(AUTHORIZATION_PATH),
        },
        "parameterDomain": {
            "primarySamples": len(primary),
            "combinationExtremes": len(extremes),
            "denseTheta2Samples": len(dense_angles),
            "allEvaluationsIncludingRepeatedAngles": len(all_rows),
            "theta2RangeDeg": [
                dense_angles[0],
                dense_angles[-1],
            ],
            "supersampling": SS,
            "alphaThreshold": ALPHA_THRESHOLD,
        },
        "oldProxyPartition": partitions,
        "singleDrawableProbe": {
            "definition": "approved V_forearm only, drawn above the frozen upper arm",
            "pixelCount": mask_count(single_probe),
            "connectedComponents": connected_components(single_probe),
            "holes": V6_MODULE.hole_count(single_probe),
            "approvedVisibleOwnershipChangedPixels": 0,
            "neutralElbowLineChangedPixels": 0,
            **single_summary,
        },
        "splitHiddenRootProbe": {
            "definition": (
                "approved V_forearm above upper plus H_root below frozen upper "
                "and complete sleeve"
            ),
            "visibleForearmPixelCount": mask_count(visible_forearm),
            "hiddenRootPixelCount": mask_count(hidden_root),
            "hiddenRootConnectedComponents": connected_components(hidden_root),
            "hiddenRootHoles": V6_MODULE.hole_count(hidden_root),
            "combinedForearmPixelCount": mask_count(split_probe),
            "combinedForearmConnectedComponents": connected_components(split_probe),
            "combinedForearmHoles": V6_MODULE.hole_count(split_probe),
            "hiddenRootOverlapsVisibleForearmPixels": mask_count(
                ImageChops.multiply(hidden_root, visible_forearm)
            ),
            "neutralVisibleHiddenRootPixels": mask_count(neutral_hidden_visible),
            "neutralCompositeDifferenceVsSinglePixels": neutral_row["split"][
                "visibleHiddenRootPixelsAt4x"
            ],
            "requiresSeparateDrawableOrMask": True,
            "approvedVisibleOwnershipChangedPixels": 0,
            "neutralElbowLineChangedPixels": 0,
            **split_summary,
            "engineeringPass": False,
            "engineeringFailures": [
                "semantic union has 2 holes",
                "adds no improvement to the already-zero responsibility gap",
                "adds no improvement to the already-zero broken adjacency count",
                "cannot change composition-aware upper visibility while below U",
                "exposes up to 8 disconnected visible H_root fragments",
                "requires a separate drawable or clipping obligation",
            ],
        },
        "comparison": {
            "splitImprovesMaximumMissingResponsibility": (
                split_summary["maximumMissingResponsibilityPixelsAt4x"]
                < single_summary["maximumMissingResponsibilityPixelsAt4x"]
            ),
            "splitImprovesBrokenAdjacency": (
                split_summary["brokenAdjacencySamples"]
                < single_summary["brokenAdjacencySamples"]
            ),
            "splitCanChangeCompositionAwareUpperExposure": False,
            "reason": (
                "H_root is below U, so it cannot occlude U. The split probe "
                "adds a second drawable/mask obligation without improving the "
                "already-zero responsibility gap or adjacency counters."
            ),
            "engineeringRecommendation": (
                "reject the split hidden-root probe; retain the approved "
                "single-drawable structure as the next contract-redefinition "
                "baseline, subject to user visual approval of this gate"
            ),
            "userVisualApproval": False,
            "userVisualDecision": (
                {
                    "status": rejection["status"],
                    "sourceStatement": rejection["sourceStatement"],
                    "singleDrawableBaselineApprovalInferred": False,
                    "path": "audit/v7b0-user-visual-rejection-2026-07-26.json",
                    "sha256": sha256(REJECTION_PATH),
                }
                if rejection is not None
                else None
            ),
        },
        "metricInterpretation": {
            "compositionAwareInnerUpperExposure": (
                "counts U remaining visible when only V_forearm is above U; "
                "H_root below U cannot reduce this value"
            ),
            "legacyIfHiddenRootWereAbove": (
                "diagnostic counter only; using it to pass would silently "
                "reverse the declared split draw order"
            ),
            "notAProductionPass": (
                "zero gap and adjacency are necessary engineering evidence, "
                "not user approval and not complete forearm geometry"
            ),
        },
        "notPerformed": [
            "no approved V_forearm pixel changed",
            "no approved elbow or wrist line changed",
            "no V4, complete sleeve, or V6 byte changed",
            "no contract rewrite",
            "no complete production forearm geometry",
            "no texture, PSD, ArtMesh, Cubism, Physics, or Runtime",
        ],
        "inputHashes": {
            "oldEnvelope": sha256(OLD_ENVELOPE_PATH),
            "visibleForearm": sha256(VISIBLE_FOREARM_PATH),
            "sourceSupport": sha256(SOURCE_SUPPORT_PATH),
            "upperVisible": sha256(UPPER_VISIBLE_PATH),
            "upperGeometry": sha256(UPPER_GEOMETRY_PATH),
            "completeSleeve": sha256(SLEEVE_PATH),
            "skeleton": sha256(SKELETON_PATH),
            "v7aUserDecision": sha256(USER_DECISION_PATH),
        },
        "visualEvidence": {
            "oldProxyPartition": "qa/V7-B0-OLD-PROXY-PARTITION-BOARD.png",
            "actualColorThreeAngles": (
                "qa/V7-B0-STRUCTURE-COMPARISON-THREE-ANGLES.png"
            ),
            "hiddenRootDiagnosticThreeAngles": (
                "qa/V7-B0-SPLIT-HIDDEN-ROOT-DIAGNOSTIC-THREE-ANGLES.png"
            ),
            "splitProbeHoleDiagnostic": (
                "qa/V7-B0-SPLIT-PROBE-HOLE-DIAGNOSTIC.png"
            ),
            "slowSweep": "qa/V7-B0-STRUCTURE-COMPARISON-SLOW-SCAN.gif",
        },
    }

    masks = {
        "single-drawable-forearm-probe.png": single_probe,
        "split-hidden-root-registered-probe.png": hidden_root,
        "split-forearm-combined-probe.png": split_probe,
        "old-envelope-unregistered-residual.png": residual,
    }
    for name, mask in masks.items():
        rgba_mask(mask).save(MASKS / name)

    (AUDIT / "v7b0-structure-feasibility.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (AUDIT / "v7b0-dense-elbow-scan.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "denseTheta2Samples": dense_rows,
                "note": (
                    "241 unique dense samples. Primary and combination "
                    "extremes are summarized in the feasibility report."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    make_partition_board(
        old_envelope,
        visible_forearm,
        upper_visible,
        sleeve,
        hidden_root,
        residual,
        source_support,
    )
    make_hole_diagnostic(
        visible_forearm,
        hidden_root,
        split_probe,
    )
    make_three_angle_board(
        skeleton,
        frame,
        upper_geometry,
        sleeve,
        visible_forearm,
        hidden_root,
        diagnostic=False,
    )
    make_three_angle_board(
        skeleton,
        frame,
        upper_geometry,
        sleeve,
        visible_forearm,
        hidden_root,
        diagnostic=True,
    )
    make_slow_sweep(
        skeleton,
        frame,
        upper_geometry,
        sleeve,
        visible_forearm,
        hidden_root,
    )

    report_md = f"""# V7-B0 肘部结构可行性复核

## 结论

本关没有批准或生成正式前臂。它只比较：

1. `S`：保持已批准肘线的单一前臂 Drawable；
2. `D`：可见前臂在上、隐藏根部在冻结上臂与袖子下方的分层结构。

当前工程证据判定 `D` 不通过：

- `S` 的责任区最大透明缺口为 `{single_summary['maximumMissingResponsibilityPixelsAt4x']}`，断开样本为 `{single_summary['brokenAdjacencySamples']}`；
- `D` 的责任区最大透明缺口为 `{split_summary['maximumMissingResponsibilityPixelsAt4x']}`，断开样本为 `{split_summary['brokenAdjacencySamples']}`；
- `S` 已经达到缺口 0、断开 0，`D` 没有改善这两项；
- `V_forearm ∪ H_root` 虽为单连通，但存在 `{V6_MODULE.hole_count(split_probe)}` 个孔，不满足完整前臂材料要求；
- `H_root` 位于上臂下方，因此不能遮住上臂。两种结构的合成语义“内弯上臂可见”最坏值相同，都是 `{single_summary['maximumCompositionAwareInnerUpperExposureAt4x']}` 个 4× 子像素；
- 动作中可见 `H_root` 最多碎成 `{split_summary['maximumVisibleHiddenRootComponents']}` 个分量，视觉上形成游动尖边；
- `D` 额外要求一个不同绘制顺序的 Drawable 或剪裁义务，不能被描述成无成本的同一普通材料。

这说明旧“内弯上臂暴露必须为 0”不能通过把 `H_root` 放到上臂后方解决。若它真正想检查的是背景裂缝，应在后继合同中改成对透明缺口、断开、鼓包、尖刺和批准肘线漂移的直接检查。

## 1177 px 旧代理的互斥分区

- 已由批准 `V_forearm` 承担：`{partitions['alreadyVisibleForearm']}` px；
- 与冻结可见上臂重叠：`{partitions['frozenVisibleUpper']}` px；
- 仅可登记在冻结袖子下方：`{partitions['registeredSleeveOnly']}` px；
- 没有上臂或袖子中性遮挡者：`{partitions['unregisteredResidual']}` px；
  - 位于源手臂轮廓外：`{partitions['residualOutsideSourceSupport']}` px；
  - 位于源手臂轮廓内但不属于当前上臂/前臂：`{partitions['residualInsideSourceSupport']}` px。

因此不能把完整旧代理直接改名为隐藏根部。当前分层探针只使用有登记中性遮挡者的 `{mask_count(hidden_root)}` px，并明确排除剩余 `{mask_count(residual)}` px。

## 分层探针自身

- `H_root`：`{mask_count(hidden_root)}` px，连通分量 `{connected_components(hidden_root)}`；
- `V_forearm ∪ H_root`：`{mask_count(split_probe)}` px，连通分量 `{connected_components(split_probe)}`，孔洞 `{V6_MODULE.hole_count(split_probe)}`；
- 与批准可见前臂重叠：`{mask_count(ImageChops.multiply(hidden_root, visible_forearm))}` px；
- 中性可见隐藏根部：`{mask_count(neutral_hidden_visible)}` px；
- 完整扫描中最大可见隐藏根部：`{split_summary['maximumVisibleHiddenRootPixelsAt4x']}` 个 4× 子像素，角度 `{split_summary['worstVisibleHiddenRootTheta2Deg']:.6f}°`。

最后一项必须由用户看慢扫判断是否像自然肘部；数值不能替代视觉批准。

## 当前建议

保留已批准的单一前臂结构作为下一步合同重定义的基线。不要从本关证据采用分层 `H_root`。下一步若用户批准此结论，应先精确定义真正的视觉失败指标，再进入正式 F1–F5 几何；不能继续沿用旧代理的字面包含和“看到任意上臂即失败”。

## 未执行

- 未改已批准前臂、肘线、腕线或手链决定；
- 未改 V4、完整袖子或 V6；
- 未改生产合同；
- 未生成完整正式前臂；
- 未进入纹理、PSD、ArtMesh、Cubism、Physics 或 Runtime。
"""
    (AUDIT / "V7-B0-STRUCTURE-FEASIBILITY.zh-CN.md").write_text(
        report_md,
        encoding="utf-8",
    )

    review_md = (
        f"""# V7-B0 用户视觉结论

用户已否决分层 `H_root`：

> {rejection['sourceStatement']}

该否决不自动批准或否决单一前臂基线。粗细不匹配已经转入 `V7-B1` 根部截面相容性重开，不再在本关继续选择。
"""
        if rejection is not None
        else """# V7-B0 用户视觉审查清单

本次不让用户选择工程实现细节，只确认结构方向。

## 请看

1. `qa/V7-B0-STRUCTURE-COMPARISON-THREE-ANGLES.png`
   - 左侧 `S` 是已批准肘线的单一前臂；
   - 右侧 `D` 是同色的分层隐藏根部；
   - 重点看最弯处右侧是否出现额外尖边。
2. `qa/V7-B0-SPLIT-HIDDEN-ROOT-DIAGNOSTIC-THREE-ANGLES.png`
   - 紫色只用于标出动作中真正露出的 `H_root`；
   - 中性不露出不代表动作中自然。
3. `qa/V7-B0-STRUCTURE-COMPARISON-SLOW-SCAN.gif`
   - 重点看紫色区域是否形成游动补片或碎边。
4. `qa/V7-B0-SPLIT-PROBE-HOLE-DIAGNOSTIC.png`
   - 红色是分层前臂语义并集中的孔洞；
   - 该项已使 `D` 工程不通过。

## 只需确认

是否同意：

- 否决分层 `H_root` 探针；
- 保留现有单一前臂和已批准肘线作为下一步合同重定义基线；
- 下一步重定义真正的肘部失败指标，再制作正式 F1–F5 几何。

这不等于批准完整正式前臂。
"""
    )
    (AUDIT / "V7-B0-USER-REVIEW-CHECKLIST.zh-CN.md").write_text(
        review_md,
        encoding="utf-8",
    )

    generated = [HERE] + [
        path
        for directory in (AUDIT, MASKS, QA)
        for path in sorted(directory.glob("*"))
        if path.is_file()
        and path.name != "v7b0-evidence-manifest.json"
    ]
    manifest = {
        "schemaVersion": 1,
        "gate": "V7-B0 structure feasibility evidence",
        "status": report["status"],
        "checksumAlgorithm": "SHA-256",
        "files": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in generated
        ],
    }
    (AUDIT / "v7b0-evidence-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
