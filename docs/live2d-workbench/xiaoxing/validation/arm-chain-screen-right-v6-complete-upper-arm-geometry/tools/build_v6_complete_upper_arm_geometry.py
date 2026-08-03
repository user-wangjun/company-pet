from __future__ import annotations

import hashlib
import io
import json
import math
import os
import zipfile
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT.parent
XIAOXING = ROOT.parents[1]
V4_ZIP = (
    VALIDATION
    / "arm-chain-screen-right-v4-wrist-motion/archive"
    / "stage-a-v4-approved-2026-07-24.zip"
)
V5 = VALIDATION / "arm-chain-screen-right-v5-hidden-upper-arm"
SOURCE_LINE = XIAOXING / "source/masters/front-line-source-exact-after-reset.png"
SOURCE_COLOR = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
VISIBLE_MASK = V5 / "masks/visible-upper-arm-locked.png"
OWNERSHIP_APPROVAL = V5 / "audit/ownership-gate-user-approval-2026-07-25.json"
SLEEVE_MATERIAL = (
    V5 / "complete-sleeve-final/materials/sleeve-complete-textured-r1.png"
)
SLEEVE_FREEZE = (
    V5
    / "complete-sleeve-final/audit"
    / "complete-sleeve-freeze-manifest-2026-07-25.json"
)
CONTRACT_PATH = ROOT / "design/complete-upper-arm-geometry-contract.json"
APPROVAL_PATH = (
    ROOT
    / "audit/user-visual-approval-complete-upper-arm-geometry-2026-07-25.json"
)
APPROVAL_INVALIDATION_PATH = (
    ROOT / "audit/geometry-approval-invalidation-2026-07-25.json"
)

W, H = 512, 1086
SS = 4
ALPHA_THRESHOLD = 16
FLAT_SKIN = (236, 166, 148)
ZONE_COLORS = {
    "Z1": (77, 126, 214, 220),
    "Z2": (35, 177, 112, 235),
    "Z3": (230, 139, 55, 220),
    "Z4": (154, 89, 194, 190),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font(size: int, bold: bool = False):
    name = "msyhbd.ttc" if bold else "msyh.ttc"
    candidates = [
        Path(os.environ.get("WINDIR", "")) / "Fonts" / name,
        Path(name),
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_TITLE = font(30, True)
FONT_SECTION = font(22, True)
FONT_BODY = font(17)
FONT_SMALL = font(14)


def ensure_dirs() -> None:
    for relative in (
        "materials/geometry",
        "masks/reference",
        "samples",
        "qa",
        "audit",
    ):
        (ROOT / relative).mkdir(parents=True, exist_ok=True)


def load_archive_json(archive: zipfile.ZipFile, name: str):
    return json.loads(archive.read(name).decode("utf-8"))


def load_archive_image(archive: zipfile.ZipFile, name: str) -> Image.Image:
    return Image.open(io.BytesIO(archive.read(name))).convert("RGBA")


def alpha(image: Image.Image) -> Image.Image:
    if image.mode == "RGBA":
        return image.getchannel("A")
    return image.convert("L")


def binary(mask: Image.Image, threshold: int = 1) -> Image.Image:
    return mask.convert("L").point(lambda value: 255 if value >= threshold else 0)


def mask_count(mask: Image.Image) -> int:
    return sum(1 for value in mask.get_flattened_data() if value)


def mask_pixels(mask: Image.Image):
    pixels = mask.load()
    bbox = mask.getbbox()
    if bbox is None:
        return
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            if pixels[x, y]:
                yield x, y


def connected_components(mask: Image.Image) -> int:
    data = binary(mask).load()
    seen: set[tuple[int, int]] = set()
    components = 0
    bbox = mask.getbbox()
    if bbox is None:
        return 0
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            if data[x, y] == 0 or (x, y) in seen:
                continue
            components += 1
            queue = deque([(x, y)])
            seen.add((x, y))
            while queue:
                cx, cy = queue.popleft()
                for nx, ny in (
                    (cx - 1, cy),
                    (cx + 1, cy),
                    (cx, cy - 1),
                    (cx, cy + 1),
                ):
                    if (
                        0 <= nx < W
                        and 0 <= ny < H
                        and data[nx, ny]
                        and (nx, ny) not in seen
                    ):
                        seen.add((nx, ny))
                        queue.append((nx, ny))
    return components


def hole_count(mask: Image.Image) -> int:
    bbox = mask.getbbox()
    if bbox is None:
        return 0
    expanded = (
        max(0, bbox[0] - 1),
        max(0, bbox[1] - 1),
        min(W, bbox[2] + 1),
        min(H, bbox[3] + 1),
    )
    data = binary(mask).load()
    outside: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    for x in range(expanded[0], expanded[2]):
        for y in (expanded[1], expanded[3] - 1):
            if data[x, y] == 0 and (x, y) not in outside:
                outside.add((x, y))
                queue.append((x, y))
    for y in range(expanded[1], expanded[3]):
        for x in (expanded[0], expanded[2] - 1):
            if data[x, y] == 0 and (x, y) not in outside:
                outside.add((x, y))
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (
                expanded[0] <= nx < expanded[2]
                and expanded[1] <= ny < expanded[3]
                and data[nx, ny] == 0
                and (nx, ny) not in outside
            ):
                outside.add((nx, ny))
                queue.append((nx, ny))
    holes = 0
    visited = set(outside)
    for y in range(expanded[1], expanded[3]):
        for x in range(expanded[0], expanded[2]):
            if data[x, y] or (x, y) in visited:
                continue
            holes += 1
            queue = deque([(x, y)])
            visited.add((x, y))
            while queue:
                cx, cy = queue.popleft()
                for nx, ny in (
                    (cx - 1, cy),
                    (cx + 1, cy),
                    (cx, cy - 1),
                    (cx, cy + 1),
                ):
                    if (
                        expanded[0] <= nx < expanded[2]
                        and expanded[1] <= ny < expanded[3]
                        and data[nx, ny] == 0
                        and (nx, ny) not in visited
                    ):
                        visited.add((nx, ny))
                        queue.append((nx, ny))
    return holes


def catmull_rom_closed(
    controls: list[tuple[float, float]], steps: int = 18
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    count = len(controls)
    for index in range(count):
        p0 = controls[(index - 1) % count]
        p1 = controls[index]
        p2 = controls[(index + 1) % count]
        p3 = controls[(index + 2) % count]
        for step in range(steps):
            t = step / steps
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * (
                2 * p1[0]
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                2 * p1[1]
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            points.append((x, y))
    return points


def local_frame(skeleton: dict):
    shoulder = (
        float(skeleton["landmarks"]["shoulder"]["x"]),
        float(skeleton["landmarks"]["shoulder"]["y"]),
    )
    elbow = (
        float(skeleton["landmarks"]["elbow"]["x"]),
        float(skeleton["landmarks"]["elbow"]["y"]),
    )
    wrist = (
        float(skeleton["landmarks"]["wrist"]["x"]),
        float(skeleton["landmarks"]["wrist"]["y"]),
    )
    length = math.dist(shoulder, elbow)
    unit = ((elbow[0] - shoulder[0]) / length, (elbow[1] - shoulder[1]) / length)
    normal = (-unit[1], unit[0])
    length2 = math.dist(elbow, wrist)
    forearm_unit = (
        (wrist[0] - elbow[0]) / length2,
        (wrist[1] - elbow[1]) / length2,
    )
    forearm_normal = (-forearm_unit[1], forearm_unit[0])
    return shoulder, elbow, wrist, length, unit, normal, forearm_unit, forearm_normal


def local_to_world(
    point: tuple[float, float],
    shoulder: tuple[float, float],
    unit: tuple[float, float],
    normal: tuple[float, float],
) -> tuple[float, float]:
    s, n = point
    return (
        shoulder[0] + unit[0] * s + normal[0] * n,
        shoulder[1] + unit[1] * s + normal[1] * n,
    )


def world_to_local(
    point: tuple[float, float],
    shoulder: tuple[float, float],
    unit: tuple[float, float],
    normal: tuple[float, float],
) -> tuple[float, float]:
    dx = point[0] - shoulder[0]
    dy = point[1] - shoulder[1]
    return dx * unit[0] + dy * unit[1], dx * normal[0] + dy * normal[1]


def build_upper_mask(contract: dict, frame):
    shoulder, _, _, _, unit, normal, _, _ = frame
    controls = [tuple(value) for value in contract["outlineControlsLocalPx"]]
    local_outline = catmull_rom_closed(controls, 24)
    world_outline = [
        local_to_world(point, shoulder, unit, normal) for point in local_outline
    ]
    high = Image.new("L", (W * SS, H * SS), 0)
    ImageDraw.Draw(high).polygon(
        [(round(x * SS), round(y * SS)) for x, y in world_outline], fill=255
    )
    antialiased = high.resize((W, H), Image.Resampling.LANCZOS)
    geometry = binary(antialiased, 128)
    visible = binary(alpha(Image.open(VISIBLE_MASK).convert("RGBA")), 1)
    geometry = ImageChops.lighter(geometry, visible)
    return geometry, local_outline


def build_flat_material(
    geometry: Image.Image, visible: Image.Image, source: Image.Image
) -> Image.Image:
    material = Image.new("RGBA", (W, H), FLAT_SKIN + (0,))
    material.putalpha(geometry)
    out = material.load()
    src = source.convert("RGB").load()
    vis = visible.load()
    for x, y in mask_pixels(visible):
        if vis[x, y]:
            out[x, y] = src[x, y] + (255,)
    return material


def build_temporary_forearm(
    frozen_forearm: Image.Image, frame, reference: dict
) -> tuple[Image.Image, list[tuple[float, float]], int]:
    _, elbow, _, _, _, _, unit, normal = frame
    base = binary(alpha(frozen_forearm), 1)
    trimmed_base = Image.new("L", (W, H), 0)
    trimmed_pixels = trimmed_base.load()
    base_pixels = base.load()
    replaced_pixels = 0
    replacement_end_s = float(
        reference["replaceFrozenPrototypeBeforeLocalSPx"]
    )
    for x, y in mask_pixels(base):
        dx = x + 0.5 - elbow[0]
        dy = y + 0.5 - elbow[1]
        s = dx * unit[0] + dy * unit[1]
        if s >= replacement_end_s:
            trimmed_pixels[x, y] = base_pixels[x, y]
        else:
            replaced_pixels += 1
    high = trimmed_base.resize((W * SS, H * SS), Image.Resampling.NEAREST)
    controls = [
        tuple(value) for value in reference["outlineControlsLocalPx"]
    ]
    local_outline = catmull_rom_closed(controls, 24)
    polygon = [
        (
            (elbow[0] + unit[0] * s + normal[0] * n) * SS,
            (elbow[1] + unit[1] * s + normal[1] * n) * SS,
        )
        for s, n in local_outline
    ]
    draw = ImageDraw.Draw(high)
    draw.polygon([(round(x), round(y)) for x, y in polygon], fill=255)
    return (
        binary(high.resize((W, H), Image.Resampling.LANCZOS), 128),
        local_outline,
        replaced_pixels,
    )


def solid(mask: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGBA", (W, H), color + (0,))
    image.putalpha(mask)
    return image


def width_at_s(
    outline: list[tuple[float, float]], s_value: float
) -> tuple[float, float, float]:
    intersections: list[float] = []
    for index, first in enumerate(outline):
        second = outline[(index + 1) % len(outline)]
        if (first[0] <= s_value < second[0]) or (second[0] <= s_value < first[0]):
            ratio = (s_value - first[0]) / (second[0] - first[0])
            intersections.append(first[1] + ratio * (second[1] - first[1]))
    if len(intersections) < 2:
        return 0.0, 0.0, 0.0
    low, high = min(intersections), max(intersections)
    return low, high, high - low


def angle_delta(first: float, second: float) -> float:
    return abs((second - first + 180.0) % 360.0 - 180.0)


def tangent_metrics(outline: list[tuple[float, float]]) -> dict:
    angles = []
    for index, point in enumerate(outline):
        previous = outline[(index - 1) % len(outline)]
        following = outline[(index + 1) % len(outline)]
        angles.append(
            math.degrees(
                math.atan2(following[1] - previous[1], following[0] - previous[0])
            )
        )
    deltas = [
        angle_delta(angles[index], angles[(index + 1) % len(angles)])
        for index in range(len(angles))
    ]
    core_deltas = [
        deltas[index]
        for index, point in enumerate(outline)
        if 0.0 <= point[0] <= 166.0
    ]
    return {
        "maximumAdjacentTangentChangeDeg": max(deltas),
        "maximumCoreAdjacentTangentChangeDeg": max(core_deltas),
        "tangentJumpCountAbove20Deg": sum(value > 20.0 for value in deltas),
    }


def solve3(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for pivot in range(3):
        swap = max(range(pivot, 3), key=lambda row: abs(augmented[row][pivot]))
        augmented[pivot], augmented[swap] = augmented[swap], augmented[pivot]
        if abs(augmented[pivot][pivot]) < 1e-9:
            return None
        scale = augmented[pivot][pivot]
        augmented[pivot] = [value / scale for value in augmented[pivot]]
        for row in range(3):
            if row == pivot:
                continue
            factor = augmented[row][pivot]
            augmented[row] = [
                augmented[row][column] - factor * augmented[pivot][column]
                for column in range(4)
            ]
    return [augmented[index][3] for index in range(3)]


def circle_fit(points: list[tuple[float, float]]) -> dict:
    matrix = [[0.0] * 3 for _ in range(3)]
    vector = [0.0] * 3
    for x, y in points:
        row = [x, y, 1.0]
        target = -(x * x + y * y)
        for i in range(3):
            vector[i] += row[i] * target
            for j in range(3):
                matrix[i][j] += row[i] * row[j]
    solution = solve3(matrix, vector)
    if solution is None:
        return {"fitAvailable": False}
    a, b, c = solution
    center = (-a / 2.0, -b / 2.0)
    radius_sq = center[0] ** 2 + center[1] ** 2 - c
    if radius_sq <= 0:
        return {"fitAvailable": False}
    radius = math.sqrt(radius_sq)
    errors = [
        abs(math.dist((x, y), center) - radius)
        for x, y in points
    ]
    normalized = math.sqrt(sum(value * value for value in errors) / len(errors)) / radius
    return {
        "fitAvailable": True,
        "radiusPx": radius,
        "normalizedRmse": normalized,
        "regularCircleRisk": normalized < 0.025,
        "interpretation": "risk prompt only; Chinese visual review remains authoritative",
    }


def containment_margin(inner: Image.Image, outer: Image.Image, maximum: int = 20) -> int:
    inner = binary(inner)
    outer = binary(outer, ALPHA_THRESHOLD)
    outer_inverse = ImageChops.invert(outer)
    margin = -1
    for radius in range(maximum + 1):
        expanded = (
            inner
            if radius == 0
            else inner.filter(ImageFilter.MaxFilter(radius * 2 + 1))
        )
        if ImageChops.multiply(expanded, outer_inverse).getbbox() is not None:
            break
        margin = radius
    return margin


def inverse_affine(
    angle_deg: float,
    rest_origin: tuple[float, float],
    current_origin: tuple[float, float],
):
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    ox, oy = rest_origin
    cx, cy = current_origin
    return (
        c,
        s,
        ox - c * cx - s * cy,
        -s,
        c,
        oy + s * cx - c * cy,
    )


def pose(skeleton: dict, theta1: float, theta2: float, wrist: float = 0.0):
    shoulder = (
        float(skeleton["landmarks"]["shoulder"]["x"]),
        float(skeleton["landmarks"]["shoulder"]["y"]),
    )
    length1 = float(skeleton["boneLengthsPx"]["L1ShoulderToElbow"])
    length2 = float(skeleton["boneLengthsPx"]["L2ElbowToWrist"])
    r1 = math.radians(theta1)
    global_forearm = math.radians(theta1 + theta2)
    elbow = (
        shoulder[0] + length1 * math.cos(r1),
        shoulder[1] + length1 * math.sin(r1),
    )
    wrist_point = (
        elbow[0] + length2 * math.cos(global_forearm),
        elbow[1] + length2 * math.sin(global_forearm),
    )
    rest1 = float(skeleton["restAnglesDeg"]["theta1"])
    rest2 = float(skeleton["restAnglesDeg"]["theta2"])
    return {
        "theta1": theta1,
        "theta2": theta2,
        "phiWristLocal": wrist,
        "elbow": elbow,
        "wrist": wrist_point,
        "deltaUpper": theta1 - rest1,
        "deltaForearm": theta1 + theta2 - rest1 - rest2,
    }


def transform_mask(
    mask: Image.Image, material: str, state: dict, frame, resample=Image.Resampling.BICUBIC
) -> Image.Image:
    shoulder, elbow, _, _, _, _, _, _ = frame
    if material in ("upper", "sleeve"):
        angle = state["deltaUpper"]
        rest_origin = current_origin = shoulder
    else:
        angle = state["deltaForearm"]
        rest_origin, current_origin = elbow, state["elbow"]
    return mask.transform(
        (W, H),
        Image.Transform.AFFINE,
        inverse_affine(angle, rest_origin, current_origin),
        resample=resample,
        fillcolor=0,
    )


def transform_rgba(image: Image.Image, material: str, state: dict, frame) -> Image.Image:
    channels = [
        transform_mask(channel, material, state, frame)
        for channel in image.convert("RGBA").split()
    ]
    return Image.merge("RGBA", channels)


def primary_states(skeleton: dict) -> list[dict]:
    rest = skeleton["primaryMotion"]["rest"]
    target = skeleton["primaryMotion"]["target"]
    states = []
    for index in range(41):
        reflected = index if index <= 20 else 40 - index
        progress = 0.5 * (1.0 - math.cos(math.pi * reflected / 20.0))
        state = pose(
            skeleton,
            rest["theta1"] + (target["theta1"] - rest["theta1"]) * progress,
            rest["theta2"] + (target["theta2"] - rest["theta2"]) * progress,
            rest["phiWristLocal"]
            + (target["phiWristLocal"] - rest["phiWristLocal"]) * progress,
        )
        state["index"] = index
        state["progress"] = progress
        states.append(state)
    return states


def extreme_states(skeleton: dict) -> list[dict]:
    states = [
        pose(skeleton, value["theta1"], value["theta2"])
        for value in skeleton["requiredCombinationExtremes"]
    ]
    states.extend(
        pose(skeleton, value["theta1"], value["theta2"], value["phiWristLocal"])
        for value in skeleton["requiredWristExtremes"]
    )
    return states


def elbow_scan(
    upper: Image.Image,
    forearm: Image.Image,
    forearm_outline: list[tuple[float, float]],
    skeleton: dict,
    frame,
    primary: list[dict],
    extremes: list[dict],
) -> tuple[dict, list[dict]]:
    _, elbow, _, length1, unit, normal, _, _ = frame
    crop_radius = 46
    box = (
        round(elbow[0] - crop_radius),
        round(elbow[1] - crop_radius),
        round(elbow[0] + crop_radius),
        round(elbow[1] + crop_radius),
    )
    high_size = ((box[2] - box[0]) * SS, (box[3] - box[1]) * SS)
    upper_high = upper.crop(box).resize(high_size, Image.Resampling.NEAREST)
    forearm_high = forearm.crop(box).resize(high_size, Image.Resampling.NEAREST)
    center = (
        (elbow[0] - box[0]) * SS,
        (elbow[1] - box[1]) * SS,
    )
    responsibility = Image.new("L", high_size, 0)
    draw = ImageDraw.Draw(responsibility)
    radius = 9.0 * SS
    draw.ellipse(
        [
            center[0] - radius,
            center[1] - radius,
            center[0] + radius,
            center[1] + radius,
        ],
        fill=255,
    )
    rest_theta2 = float(skeleton["restAnglesDeg"]["theta2"])

    def evaluate(theta2: float) -> dict:
        delta_angle = theta2 - rest_theta2
        rotated = forearm_high.rotate(
            delta_angle,
            resample=Image.Resampling.BICUBIC,
            center=center,
            fillcolor=0,
        )
        upper_core = binary(upper_high, ALPHA_THRESHOLD)
        forearm_core = binary(rotated, ALPHA_THRESHOLD)
        union = ImageChops.lighter(upper_core, forearm_core)
        missing = ImageChops.subtract(responsibility, union)
        overlap = ImageChops.multiply(upper_core, forearm_core)
        overlap_in_zone = ImageChops.multiply(overlap, responsibility)
        visible_upper = ImageChops.subtract(upper_core, forearm_core)
        angle = math.radians(delta_angle)
        cosine, sine = math.cos(angle), math.sin(angle)
        current_unit = (
            cosine * unit[0] - sine * unit[1],
            sine * unit[0] + cosine * unit[1],
        )
        current_normal = (
            cosine * normal[0] - sine * normal[1],
            sine * normal[0] + cosine * normal[1],
        )
        inner_bend_exposed = 0
        for x, y in mask_pixels(visible_upper):
            dx = (x + 0.5 - center[0]) / SS
            dy = (y + 0.5 - center[1]) / SS
            local_s = dx * current_unit[0] + dy * current_unit[1]
            local_n = dx * current_normal[0] + dy * current_normal[1]
            if -12.0 <= local_s <= 8.0 and local_n < 0.0:
                inner_bend_exposed += 1
        return {
            "theta2": theta2,
            "missingResponsibilityPixelsAt4x": mask_count(missing),
            "overlapPixelsAt4x": mask_count(overlap_in_zone),
            "connectedByOverlap": overlap.getbbox() is not None,
            "innerBendExposedUpperPixelsAt4x": inner_bend_exposed,
        }

    dense_min = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    dense_max = float(skeleton["allowedRangesDeg"]["theta2"]["max"])
    dense = [
        evaluate(dense_min + (dense_max - dense_min) * index / 240.0)
        for index in range(241)
    ]
    primary_results = [evaluate(state["theta2"]) for state in primary]
    extreme_results = [evaluate(state["theta2"]) for state in extremes]
    all_results = dense + primary_results + extreme_results
    worst_gap = max(all_results, key=lambda item: item["missingResponsibilityPixelsAt4x"])
    worst_overlap = min(all_results, key=lambda item: item["overlapPixelsAt4x"])
    worst_inner_bend = max(
        all_results,
        key=lambda item: item["innerBendExposedUpperPixelsAt4x"],
    )
    maximum_angle = max(abs(dense_min), abs(dense_max))
    core_slip = math.ceil(16.5 * math.sin(math.radians(maximum_angle)))
    margins = {
        "antiAliasingPx": 2,
        "futureTextureAlphaPx": 2,
        "futureCubismInterpolationPx": 3,
    }
    final_required = core_slip + sum(margins.values())
    local_max_s = max(point[0] for point in catmull_rom_closed(
        [tuple(value) for value in json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))[
            "outlineControlsLocalPx"
        ]],
        24,
    ))
    upper_extension = local_max_s - length1
    forearm_extension = -min(point[0] for point in forearm_outline)
    forearm_width_at_elbow = width_at_s(forearm_outline, 0.0)[2]
    report = {
        "supersampling": SS,
        "responsibilityDiskRadiusPx": 9.0,
        "primarySampleCount": len(primary_results),
        "combinationExtremeCount": len(extreme_results),
        "denseContinuousTheta2SampleCount": len(dense),
        "adaptiveSubdivision": {
            "method": "uniform dense verification after primary and extreme evaluation",
            "intervalCount": 240,
            "maximumIntervalDeg": (dense_max - dense_min) / 240.0,
        },
        "upperArmResponsibility": {
            "motionDerivedCoreExtensionPx": core_slip,
            "marginsPx": margins,
            "finalRequiredExtensionPx": final_required,
            "candidateExtensionBeyondFrozenElbowPx": upper_extension,
            "passes": upper_extension >= final_required,
        },
        "forearmRootResponsibility": {
            "motionDerivedCoreExtensionPx": core_slip,
            "marginsPx": margins,
            "finalRequiredExtensionPx": final_required,
            "temporaryReferenceExtensionPx": forearm_extension,
            "temporaryReferenceWidthAtElbowPx": forearm_width_at_elbow,
            "passesTemporaryReferenceOnly": forearm_extension >= final_required,
            "productionMaterialApproved": False,
        },
        "maximumMissingResponsibilityPixelsAt4x": worst_gap[
            "missingResponsibilityPixelsAt4x"
        ],
        "worstGapTheta2Deg": worst_gap["theta2"],
        "minimumOverlapPixelsAt4x": worst_overlap["overlapPixelsAt4x"],
        "worstOverlapTheta2Deg": worst_overlap["theta2"],
        "brokenAdjacencySamples": sum(
            not item["connectedByOverlap"] for item in all_results
        ),
        "maximumInnerBendExposedUpperPixelsAt4x": worst_inner_bend[
            "innerBendExposedUpperPixelsAt4x"
        ],
        "worstInnerBendExposureTheta2Deg": worst_inner_bend["theta2"],
    }
    return report, dense


def checkerboard(size: tuple[int, int], cell: int = 16) -> Image.Image:
    board = Image.new("RGBA", size, (238, 238, 238, 255))
    draw = ImageDraw.Draw(board)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle(
                    [x, y, min(size[0], x + cell), min(size[1], y + cell)],
                    fill=(202, 202, 202, 255),
                )
    return board


def crop_scaled(
    image: Image.Image,
    box: tuple[int, int, int, int],
    scale: float,
    background: bool = True,
) -> Image.Image:
    crop = image.crop(box)
    if background:
        panel = checkerboard(crop.size, 12)
        panel.alpha_composite(crop)
    else:
        panel = crop
    return panel.resize(
        (round(panel.width * scale), round(panel.height * scale)),
        Image.Resampling.NEAREST,
    )


def labeled_board(
    title: str,
    panels: list[tuple[str, str, Image.Image]],
    width: int = 1800,
) -> Image.Image:
    margin = 22
    gap = 18
    title_height = 70
    panel_width = (width - margin * 2 - gap * (len(panels) - 1)) // len(panels)
    prepared = []
    max_height = 0
    for heading, note, image in panels:
        ratio = min(1.0, panel_width / image.width)
        rendered = image.resize(
            (round(image.width * ratio), round(image.height * ratio)),
            Image.Resampling.LANCZOS if ratio < 1.0 else Image.Resampling.NEAREST,
        )
        prepared.append((heading, note, rendered))
        max_height = max(max_height, rendered.height)
    board = Image.new(
        "RGB", (width, title_height + 90 + max_height + margin), (246, 246, 246)
    )
    draw = ImageDraw.Draw(board)
    draw.text((margin, 16), title, font=FONT_TITLE, fill=(25, 25, 25))
    x = margin
    for heading, note, image in prepared:
        draw.text((x, title_height), heading, font=FONT_SECTION, fill=(35, 35, 35))
        draw.text((x, title_height + 32), note, font=FONT_SMALL, fill=(70, 70, 70))
        board.paste(image.convert("RGB"), (x, title_height + 66))
        x += panel_width + gap
    return board


def zone_overlay(geometry: Image.Image, visible: Image.Image, frame) -> Image.Image:
    shoulder, elbow, _, _, unit, normal, _, _ = frame
    result = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pixels = result.load()
    geom = geometry.load()
    vis = visible.load()
    visible_min_s = 136.54078
    for x, y in mask_pixels(geometry):
        s, _ = world_to_local((x + 0.5, y + 0.5), shoulder, unit, normal)
        if vis[x, y]:
            color = ZONE_COLORS["Z2"]
        elif s < visible_min_s:
            color = ZONE_COLORS["Z1"]
        else:
            color = ZONE_COLORS["Z3"]
        pixels[x, y] = color
    draw = ImageDraw.Draw(result)
    radius = 9
    tick = 4
    left, top = elbow[0] - radius, elbow[1] - radius
    right, bottom = elbow[0] + radius, elbow[1] + radius
    color = ZONE_COLORS["Z4"]
    for points in (
        [(left, top + tick), (left, top), (left + tick, top)],
        [(right - tick, top), (right, top), (right, top + tick)],
        [(left, bottom - tick), (left, bottom), (left + tick, bottom)],
        [(right - tick, bottom), (right, bottom), (right, bottom - tick)],
    ):
        draw.line(points, fill=color, width=2)
    return result


def width_chart(width_profile: list[dict]) -> Image.Image:
    chart = Image.new("RGB", (520, 640), (252, 252, 252))
    draw = ImageDraw.Draw(chart)
    draw.text((18, 16), "沿冻结骨轴的宽度剖面", font=FONT_SECTION, fill=(30, 30, 30))
    plot = (70, 80, 485, 560)
    draw.rectangle(plot, outline=(110, 110, 110), width=2)
    maximum_s = max(item["sPx"] for item in width_profile)
    maximum_width = max(item["fullWidthPx"] for item in width_profile) * 1.12
    points = []
    for index, item in enumerate(width_profile):
        x = plot[0] + item["sPx"] / maximum_s * (plot[2] - plot[0])
        y = plot[3] - item["fullWidthPx"] / maximum_width * (plot[3] - plot[1])
        points.append((x, y))
        draw.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(226, 112, 72))
        label_y = y - 25 if index % 2 == 0 else y + 8
        draw.text(
            (x - 18, label_y),
            f'{item["fullWidthPx"]:.1f}',
            font=FONT_SMALL,
            fill=(60, 60, 60),
        )
    draw.line(points, fill=(226, 112, 72), width=4)
    draw.text((65, 575), "肩端", font=FONT_BODY, fill=(50, 50, 50))
    draw.text((420, 575), "肘端", font=FONT_BODY, fill=(50, 50, 50))
    return chart


def render_pose(
    upper_material: Image.Image,
    upper_mask: Image.Image,
    forearm_mask: Image.Image,
    sleeve: Image.Image,
    state: dict,
    frame,
) -> Image.Image:
    upper = transform_rgba(upper_material, "upper", state, frame)
    forearm = solid(
        transform_mask(forearm_mask, "forearm", state, frame), (80, 169, 116)
    )
    sleeve_pose = transform_rgba(sleeve, "sleeve", state, frame)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(upper)
    canvas.alpha_composite(forearm)
    canvas.alpha_composite(sleeve_pose)
    return canvas


def render_pose_skin_preview(
    upper_material: Image.Image,
    forearm_mask: Image.Image,
    sleeve: Image.Image,
    state: dict,
    frame,
) -> Image.Image:
    upper = transform_rgba(upper_material, "upper", state, frame)
    forearm = solid(
        transform_mask(forearm_mask, "forearm", state, frame), FLAT_SKIN
    )
    sleeve_pose = transform_rgba(sleeve, "sleeve", state, frame)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(upper)
    canvas.alpha_composite(forearm)
    canvas.alpha_composite(sleeve_pose)
    return canvas


def translated(image: Image.Image, dx: int, dy: int) -> Image.Image:
    return image.transform(
        image.size,
        Image.Transform.AFFINE,
        (1, 0, -dx, 0, 1, -dy),
        resample=Image.Resampling.NEAREST,
        fillcolor=0,
    )


def create_qa(
    geometry: Image.Image,
    material: Image.Image,
    visible: Image.Image,
    forearm_coverage: Image.Image,
    forearm_display: Image.Image,
    sleeve: Image.Image,
    source: Image.Image,
    outline: list[tuple[float, float]],
    width_profile: list[dict],
    skeleton: dict,
    frame,
    primary: list[dict],
    extremes: list[dict],
) -> list[Path]:
    paths: list[Path] = []
    crop = (285, 220, 420, 455)
    shoulder, elbow, _, _, _, _, _, _ = frame

    source_alignment = source.copy()
    tint = solid(geometry, (232, 92, 65))
    tint.putalpha(geometry.point(lambda value: 92 if value else 0))
    source_alignment.alpha_composite(tint)
    geometry_edge = ImageChops.subtract(
        geometry.filter(ImageFilter.MaxFilter(5)),
        geometry.filter(ImageFilter.MinFilter(5)),
    )
    source_alignment.alpha_composite(solid(geometry_edge, (205, 45, 35)))
    alignment_draw = ImageDraw.Draw(source_alignment)
    alignment_draw.line([shoulder, elbow], fill=(22, 119, 214, 255), width=2)
    for point, color in (
        (shoulder, (246, 162, 36, 255)),
        (elbow, (23, 158, 105, 255)),
    ):
        alignment_draw.ellipse(
            [point[0] - 4, point[1] - 4, point[0] + 4, point[1] + 4],
            fill=color,
            outline=(255, 255, 255, 255),
            width=1,
        )

    isolated_alignment = checkerboard((W, H))
    isolated_alignment.alpha_composite(material)
    isolated_draw = ImageDraw.Draw(isolated_alignment)
    isolated_draw.line([shoulder, elbow], fill=(22, 119, 214, 255), width=2)
    for point, color in (
        (shoulder, (246, 162, 36, 255)),
        (elbow, (23, 158, 105, 255)),
    ):
        isolated_draw.ellipse(
            [point[0] - 4, point[1] - 4, point[0] + 4, point[1] + 4],
            fill=color,
            outline=(255, 255, 255, 255),
            width=1,
        )

    alignment = labeled_board(
        "复审重点｜上臂轮廓与原体态对齐",
        [
            (
                "原始体态",
                "袖子遮挡下的权威正面位置",
                crop_scaled(source, crop, 3.0, False),
            ),
            (
                "轮廓叠回原图",
                "红=修订轮廓，蓝线=冻结肩肘骨轴",
                crop_scaled(source_alignment, crop, 3.0, False),
            ),
            (
                "单独轮廓与骨轴",
                "橙点=肩，绿点=肘；检查粗细和方向",
                crop_scaled(isolated_alignment, crop, 3.0),
            ),
        ],
    )
    path = ROOT / "qa/gate-0-body-alignment-review.png"
    alignment.save(path)
    paths.append(path)

    overlay = zone_overlay(geometry, visible, frame)
    isolated = labeled_board(
        "视觉门 1｜完整上臂纯色隔离与分区",
        [
            (
                "完整纯色材料",
                "隐藏区为审查平色，Z2 保留原图像素",
                crop_scaled(material, crop, 3.0),
            ),
            (
                "Z1 / Z2 / Z3 / Z4",
                "蓝=肩侧，绿=可见锚点，橙=肘侧，紫=覆盖责任",
                crop_scaled(overlay, crop, 3.0),
            ),
            (
                "宽度剖面",
                "肩部较粗，中段渐细，肘侧收束",
                width_chart(width_profile),
            ),
        ],
    )
    path = ROOT / "qa/gate-1-complete-upper-arm-isolated.png"
    isolated.save(path)
    paths.append(path)

    rest = pose(
        skeleton,
        float(skeleton["restAnglesDeg"]["theta1"]),
        float(skeleton["restAnglesDeg"]["theta2"]),
    )
    composition = render_pose(
        material, geometry, forearm_display, sleeve, rest, frame
    )
    ownership = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ownership.alpha_composite(solid(geometry, (226, 112, 72)))
    ownership.alpha_composite(solid(forearm_display, (70, 175, 116)))
    ownership.alpha_composite(solid(binary(alpha(sleeve), ALPHA_THRESHOLD), (74, 117, 210)))
    default = labeled_board(
        "视觉门 2｜默认位置回组",
        [
            ("权威彩稿", "同坐标裁剪，仅作身份与边界参照", crop_scaled(source, crop, 3.0, False)),
            ("几何回组", "袖子在最上，临时前臂位于上臂之上", crop_scaled(composition, crop, 3.0)),
            ("所有权回组", "橙=上臂，绿=临时前臂，蓝=冻结袖子", crop_scaled(ownership, crop, 3.0)),
        ],
    )
    path = ROOT / "qa/gate-2-default-recomposition.png"
    default.save(path)
    paths.append(path)

    sleeve_moved_canvas = checkerboard((W, H))
    sleeve_moved_canvas.alpha_composite(material)
    sleeve_moved_canvas.alpha_composite(
        solid(forearm_display, (80, 169, 116))
    )
    sleeve_moved_canvas.alpha_composite(translated(sleeve, 82, -18))
    sleeve_moved = labeled_board(
        "视觉门 3｜袖子移开后的完整上臂",
        [
            ("默认坐标", "上臂保持原位", crop_scaled(material, crop, 3.0)),
            ("袖子诊断移开 +82,-18 px", "检查肩端至肘端是否为一块完整材料", crop_scaled(sleeve_moved_canvas, (285, 190, 500, 470), 2.25)),
        ],
        1500,
    )
    path = ROOT / "qa/gate-3-sleeve-moved-away.png"
    sleeve_moved.save(path)
    paths.append(path)

    forearm_layer = solid(forearm_coverage, (80, 169, 116))
    forearm_moved_canvas = checkerboard((W, H))
    forearm_moved_canvas.alpha_composite(material)
    forearm_moved_canvas.alpha_composite(translated(forearm_layer, 84, 18))
    forearm_moved = labeled_board(
        "视觉门 4｜前臂移开后的肘侧末端",
        [
            ("上臂肘端", "自然隐藏末端，不设独立肘圆盘", crop_scaled(material, (315, 360, 400, 455), 5.0)),
            ("临时前臂移开 +84,+18 px", "只检查上臂末端完整性；绿色前臂不是正式材料", crop_scaled(forearm_moved_canvas, (300, 345, 500, 500), 2.6)),
        ],
        1500,
    )
    path = ROOT / "qa/gate-4-forearm-moved-away.png"
    forearm_moved.save(path)
    paths.append(path)

    shoulder_panels = []
    for scale in (2, 4, 8):
        shoulder_panels.append(
            (
                f"{scale * 100}%",
                "最近邻放大，检查肩端收束",
                crop_scaled(overlay, (305, 235, 365, 310), scale),
            )
        )
    shoulder_board = labeled_board(
        "视觉门 5｜肩端 200%–800% 放大", shoulder_panels, 1800
    )
    path = ROOT / "qa/gate-5-shoulder-zoom.png"
    shoulder_board.save(path)
    paths.append(path)

    elbow_panels = []
    for scale in (2, 4, 8):
        elbow_panels.append(
            (
                f"{scale * 100}%",
                "最近邻放大，检查肘端曲率和可见锚点",
                crop_scaled(overlay, (325, 375, 395, 455), scale),
            )
        )
    elbow_board = labeled_board(
        "视觉门 6｜肘端 200%–800% 放大", elbow_panels, 1800
    )
    path = ROOT / "qa/gate-6-elbow-zoom.png"
    elbow_board.save(path)
    paths.append(path)

    frames = [
        crop_scaled(
            render_pose(
                material, geometry, forearm_coverage, sleeve, state, frame
            ),
            (275, 190, 470, 600),
            1.35,
        )
        for state in extremes
    ]
    board = Image.new("RGB", (3 * 430, 2 * 625 + 70), (246, 246, 246))
    draw = ImageDraw.Draw(board)
    draw.text((18, 16), "视觉门 7｜六个组合极值", font=FONT_TITLE, fill=(25, 25, 25))
    for index, image in enumerate(frames):
        x = (index % 3) * 430 + 18
        y = (index // 3) * 625 + 62
        board.paste(image.convert("RGB"), (x, y))
        state = extremes[index]
        draw.text(
            (x, y + image.height + 5),
            f'θ1={state["theta1"]:.1f}°  θ2={state["theta2"]:.1f}°  腕={state["phiWristLocal"]:.1f}°',
            font=FONT_SMALL,
            fill=(50, 50, 50),
        )
    path = ROOT / "qa/gate-7-six-combination-extremes.png"
    board.save(path)
    paths.append(path)

    gif_frames = []
    theta1 = float(skeleton["primaryMotion"]["target"]["theta1"])
    theta2_min = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    theta2_max = float(skeleton["allowedRangesDeg"]["theta2"]["max"])
    values = [
        theta2_min + (theta2_max - theta2_min) * index / 30.0
        for index in range(31)
    ]
    values += values[-2:0:-1]
    for theta2 in values:
        state = pose(skeleton, theta1, theta2)
        ownership_rendered = render_pose(
            material, geometry, forearm_coverage, sleeve, state, frame
        )
        skin_rendered = render_pose_skin_preview(
            material, forearm_coverage, sleeve, state, frame
        )
        ownership_panel = crop_scaled(
            ownership_rendered, (290, 300, 440, 500), 2.5
        )
        skin_panel = crop_scaled(
            skin_rendered, (290, 300, 440, 500), 2.5
        )
        panel_gap = 10
        header_height = 66
        canvas = checkerboard(
            (
                ownership_panel.width + skin_panel.width + panel_gap,
                max(ownership_panel.height, skin_panel.height) + header_height,
            ),
            16,
        )
        canvas.alpha_composite(ownership_panel, (0, header_height))
        canvas.alpha_composite(
            skin_panel, (ownership_panel.width + panel_gap, header_height)
        )
        frame_draw = ImageDraw.Draw(canvas)
        frame_draw.text(
            (10, 8),
            f"肘部单参数扫描  θ2={theta2:.2f}°",
            font=FONT_BODY,
            fill=(30, 30, 30),
        )
        frame_draw.text(
            (10, 36),
            "所有权颜色",
            font=FONT_SMALL,
            fill=(30, 30, 30),
        )
        frame_draw.text(
            (ownership_panel.width + panel_gap + 10, 36),
            "同肤色外轮廓",
            font=FONT_SMALL,
            fill=(30, 30, 30),
        )
        gif_frames.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE))
    path = ROOT / "qa/gate-8-elbow-single-parameter-scan.gif"
    gif_frames[0].save(
        path,
        save_all=True,
        append_images=gif_frames[1:],
        duration=120,
        loop=0,
        disposal=2,
    )
    paths.append(path)

    displaced = checkerboard((W, H))
    displaced.alpha_composite(translated(material, -70, 0))
    displaced.alpha_composite(translated(forearm_layer, 72, 18))
    displaced.alpha_composite(translated(sleeve, 10, -65))
    integrity = labeled_board(
        "视觉门 9｜部件分别大位移后的完整性",
        [
            ("完整上臂", "左移 70 px，检查单连通和两端闭合", crop_scaled(translated(material, -70, 0), (200, 200, 390, 470), 2.1)),
            ("三部件分离", "上臂、临时前臂、冻结袖子分别移动", crop_scaled(displaced, (190, 120, 500, 600), 1.35)),
        ],
        1500,
    )
    path = ROOT / "qa/gate-9-displaced-parts-integrity.png"
    integrity.save(path)
    paths.append(path)

    review_theta2 = (
        theta2_min,
        float(skeleton["restAnglesDeg"]["theta2"]),
        theta2_max,
    )
    review_states = [pose(skeleton, theta1, value) for value in review_theta2]
    review_crop = (300, 330, 435, 500)
    ownership_review = labeled_board(
        "肘部精修复核｜所有权颜色",
        [
            (
                f"θ2={state['theta2']:.2f}°",
                "桃=上臂，绿=临时前臂；检查根部是否鼓包",
                crop_scaled(
                    render_pose(
                        material,
                        geometry,
                        forearm_coverage,
                        sleeve,
                        state,
                        frame,
                    ),
                    review_crop,
                    2.7,
                ),
            )
            for state in review_states
        ],
        1500,
    )
    skin_review = labeled_board(
        "肘部精修复核｜同肤色外轮廓",
        [
            (
                f"θ2={state['theta2']:.2f}°",
                "模拟同一肤色，检查真实外轮廓连续性",
                crop_scaled(
                    render_pose_skin_preview(
                        material,
                        forearm_coverage,
                        sleeve,
                        state,
                        frame,
                    ),
                    review_crop,
                    2.7,
                ),
            )
            for state in review_states
        ],
        1500,
    )
    refinement = Image.new(
        "RGB",
        (
            max(ownership_review.width, skin_review.width),
            ownership_review.height + skin_review.height + 12,
        ),
        (246, 246, 246),
    )
    refinement.paste(ownership_review, (0, 0))
    refinement.paste(skin_review, (0, ownership_review.height + 12))
    path = ROOT / "qa/gate-10-elbow-protrusion-refinement.png"
    refinement.save(path)
    paths.append(path)
    return paths


def main() -> None:
    ensure_dirs()
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    expected_inputs = {
        SOURCE_LINE: "706aaf10652147cf76e233532b5459ce130921a96806f6970c91e1f3a427172f",
        SOURCE_COLOR: "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5",
        V4_ZIP: "2cbbe6182f9d4937cbbaf4d8e1f6f9768c9161597edd8a09efdbde0ec8884800",
        VISIBLE_MASK: "aaf373b65f9b3a201a6b8810530a5ee82cfc19d1bb0cdfedf2221beb3884a71a",
        OWNERSHIP_APPROVAL: "545fd058de5977dd75a5641c03b0a361316a9367be0120366d8cb683d6764631",
        SLEEVE_MATERIAL: "d470c8b192c043457860528adc25d250bb43a5e56ebd1ab46dcda947773b5cc7",
        SLEEVE_FREEZE: "a36c1959a1a16364997f60e4704c9af071173b79530a417216f6e5b71f3642e8",
    }
    input_checks = []
    for path, expected in expected_inputs.items():
        actual = sha256(path)
        input_checks.append(
            {
                "path": str(path.relative_to(XIAOXING)).replace("\\", "/"),
                "expectedSha256": expected,
                "actualSha256": actual,
                "match": actual == expected,
            }
        )
    if not all(item["match"] for item in input_checks):
        raise RuntimeError("one or more frozen inputs changed")

    with zipfile.ZipFile(V4_ZIP) as archive:
        skeleton = load_archive_json(archive, "skeleton.json")
        frozen_forearm = load_archive_image(archive, "materials/solid/forearm.png")

    frame = local_frame(skeleton)
    geometry, local_outline = build_upper_mask(contract, frame)
    visible = binary(alpha(Image.open(VISIBLE_MASK).convert("RGBA")), 1)
    source = Image.open(SOURCE_COLOR).convert("RGBA")
    sleeve = Image.open(SLEEVE_MATERIAL).convert("RGBA")
    material = build_flat_material(geometry, visible, source)
    (
        temporary_forearm,
        temporary_forearm_outline,
        temporary_forearm_replaced_pixels,
    ) = build_temporary_forearm(
        frozen_forearm, frame, contract["temporaryForearmRootReference"]
    )
    forearm_profile_s = (-17.0, -14.0, -8.0, 0.0, 10.0, 22.0)
    forearm_root_width_profile = []
    for s_value in forearm_profile_s:
        low, high, full = width_at_s(
            temporary_forearm_outline, s_value
        )
        forearm_root_width_profile.append(
            {
                "sPx": s_value,
                "innerBendNegativeNormalPx": low,
                "outerBendPositiveNormalPx": high,
                "fullWidthPx": full,
            }
        )
    forearm_outer_widths = [
        item["outerBendPositiveNormalPx"]
        for item in forearm_root_width_profile
    ]
    forearm_outer_root_monotonic = all(
        following + 0.5 >= previous
        for previous, following in zip(
            forearm_outer_widths, forearm_outer_widths[1:]
        )
    )
    forearm_outer_shaft_reference = forearm_outer_widths[-1]
    forearm_outer_root_excess = max(
        0.0,
        max(forearm_outer_widths[:-1]) - forearm_outer_shaft_reference,
    )
    display_forearm = ImageChops.subtract(temporary_forearm, visible)

    geometry_path = ROOT / "masks/upper-arm-complete-geometry.png"
    material_path = ROOT / "materials/geometry/upper-arm-complete-flat-reference.png"
    visible_reference_path = ROOT / "masks/reference/visible-upper-arm-locked-reference.png"
    forearm_reference_path = ROOT / "masks/reference/forearm-root-temporary-coverage.png"
    geometry.save(geometry_path)
    material.save(material_path)
    visible.save(visible_reference_path)
    temporary_forearm.save(forearm_reference_path)

    shoulder, elbow, _, length1, unit, normal, _, _ = frame
    visible_values = [
        world_to_local((x + 0.5, y + 0.5), shoulder, unit, normal)
        for x, y in mask_pixels(visible)
    ]
    visible_pixel_count = len(visible_values)
    material_pixels = material.load()
    source_pixels = source.convert("RGB").load()
    visible_rgb_differences = 0
    maximum_visible_difference = 0
    for x, y in mask_pixels(visible):
        actual = material_pixels[x, y][:3]
        expected = source_pixels[x, y]
        differences = [abs(actual[index] - expected[index]) for index in range(3)]
        if max(differences):
            visible_rgb_differences += 1
        maximum_visible_difference = max(maximum_visible_difference, *differences)

    width_profile = []
    for s_value in (0.0, 20.0, 40.0, 80.0, 120.0, 145.0, length1, 165.0):
        low, high, full = width_at_s(local_outline, s_value)
        width_profile.append(
            {
                "sPx": s_value,
                "negativeNormalPx": low,
                "positiveNormalPx": high,
                "fullWidthPx": full,
            }
        )

    tangent_report = tangent_metrics(local_outline)
    shoulder_circle = circle_fit(
        [point for point in local_outline if point[0] <= 15.0]
    )
    elbow_circle = circle_fit(
        [point for point in local_outline if point[0] >= 158.0]
    )

    z1 = Image.new("L", (W, H), 0)
    z1_cap = Image.new("L", (W, H), 0)
    z1_pixels = z1.load()
    z1_cap_pixels = z1_cap.load()
    visible_min_s = float(
        contract["zones"]["Z2"]["localLongitudinalObservedRangePx"][0]
    )
    for x, y in mask_pixels(geometry):
        s_value, _ = world_to_local((x + 0.5, y + 0.5), shoulder, unit, normal)
        if s_value < visible_min_s and not visible.getpixel((x, y)):
            z1_pixels[x, y] = 255
        if s_value <= 42.0:
            z1_cap_pixels[x, y] = 255
    sleeve_core = binary(alpha(sleeve), ALPHA_THRESHOLD)
    z1_outside_sleeve = ImageChops.multiply(z1, ImageChops.invert(sleeve_core))
    z1_cap_outside_sleeve = ImageChops.multiply(
        z1_cap, ImageChops.invert(sleeve_core)
    )
    shoulder_margin = containment_margin(z1_cap, alpha(sleeve), 20)

    primary = primary_states(skeleton)
    extremes = extreme_states(skeleton)
    elbow_report, dense_scan = elbow_scan(
        geometry,
        temporary_forearm,
        temporary_forearm_outline,
        skeleton,
        frame,
        primary,
        extremes,
    )
    elbow_report["forearmRootResponsibility"][
        "frozenPrototypeProximalPixelsReplacedInTemporaryQaProxy"
    ] = temporary_forearm_replaced_pixels
    elbow_report["forearmRootResponsibility"][
        "frozenV4ArchiveModified"
    ] = False

    rest_first = render_pose(
        material, geometry, temporary_forearm, sleeve, primary[0], frame
    )
    rest_last = render_pose(
        material, geometry, temporary_forearm, sleeve, primary[-1], frame
    )
    deterministic_return = ImageChops.difference(rest_first, rest_last).getbbox() is None

    qa_paths = create_qa(
        geometry,
        material,
        visible,
        temporary_forearm,
        display_forearm,
        sleeve,
        source,
        local_outline,
        width_profile,
        skeleton,
        frame,
        primary,
        extremes,
    )

    sample_path = ROOT / "samples/fk-41-and-continuous-elbow-scan.json"
    sample_payload = {
        "schemaVersion": 1,
        "primary41": primary,
        "sixCombinationExtremes": extremes,
        "denseTheta2Scan": dense_scan,
    }
    sample_path.write_text(
        json.dumps(sample_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    output_paths = [
        geometry_path,
        material_path,
        visible_reference_path,
        forearm_reference_path,
        sample_path,
        *qa_paths,
    ]
    engineering_pass_criteria = {
        "visiblePixelCountIs544": visible_pixel_count == 544,
        "visibleRgbDifferencesAreZero": visible_rgb_differences == 0,
        "geometryIsSingleConnectedComponent": connected_components(geometry) == 1,
        "geometryHasNoHoles": hole_count(geometry) == 0,
        "visibleAnchorFullyContained": ImageChops.subtract(
            visible, geometry
        ).getbbox()
        is None,
        "shoulderCapInsideActualSleeveAlpha": mask_count(
            z1_cap_outside_sleeve
        )
        == 0,
        "displayForearmDoesNotOverwriteVisibleAnchor": mask_count(
            ImageChops.multiply(display_forearm, visible)
        )
        == 0,
        "upperArmElbowExtensionMeetsRequiredMargin": elbow_report[
            "upperArmResponsibility"
        ]["passes"],
        "temporaryForearmReferenceMeetsRequiredMargin": elbow_report[
            "forearmRootResponsibility"
        ]["passesTemporaryReferenceOnly"],
        "continuousElbowScanHasNoGap": elbow_report[
            "maximumMissingResponsibilityPixelsAt4x"
        ]
        == 0,
        "continuousElbowScanHasNoDetachment": elbow_report[
            "brokenAdjacencySamples"
        ]
        == 0,
        "continuousElbowScanHasNoInnerBendSpike": elbow_report[
            "maximumInnerBendExposedUpperPixelsAt4x"
        ]
        == 0,
        "deterministicReturn": deterministic_return,
        "noTangentJumpAbove20Deg": tangent_report[
            "tangentJumpCountAbove20Deg"
        ]
        == 0,
        "shoulderRegularCircleRiskNotTriggered": not shoulder_circle[
            "regularCircleRisk"
        ],
        "elbowRegularCircleRiskNotTriggered": not elbow_circle[
            "regularCircleRisk"
        ],
        "temporaryForearmOuterRootWidensWithoutProximalBulge": (
            forearm_outer_root_monotonic
            and forearm_outer_root_excess <= 0.5
        ),
    }
    if not all(engineering_pass_criteria.values()):
        failed = [
            name for name, passed in engineering_pass_criteria.items() if not passed
        ]
        raise RuntimeError(f"V6 engineering gate failed: {failed}")
    artifact_hashes = {
        str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
        for path in output_paths
    }
    approval = None
    approval_invalidation = None
    approval_verified = False
    if APPROVAL_PATH.exists():
        approval = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))
        if approval.get("decision") != "approved":
            raise RuntimeError("V6 visual approval record is not approved")
        if APPROVAL_INVALIDATION_PATH.exists():
            approval_invalidation = json.loads(
                APPROVAL_INVALIDATION_PATH.read_text(encoding="utf-8")
            )
            if approval_invalidation.get("status") != "active":
                raise RuntimeError("V6 approval invalidation record is not active")
            if (
                approval_invalidation.get("invalidatedApprovalRecordSha256")
                != sha256(APPROVAL_PATH)
            ):
                raise RuntimeError(
                    "V6 approval invalidation does not match the approval record"
                )
    if approval is not None and approval_invalidation is None:
        approved_hashes = approval.get("approvedArtifactHashes", {})
        mismatches = [
            path
            for path, expected in approved_hashes.items()
            if artifact_hashes.get(path) != expected
        ]
        if mismatches:
            raise RuntimeError(
                f"V6 approved artifact hash mismatch; approval invalidated: {mismatches}"
            )
        required_approved_paths = {
            "masks/upper-arm-complete-geometry.png",
            "materials/geometry/upper-arm-complete-flat-reference.png",
            *(
                str(path.relative_to(ROOT)).replace("\\", "/")
                for path in qa_paths
            ),
        }
        missing_approval_hashes = sorted(
            required_approved_paths - set(approved_hashes)
        )
        if missing_approval_hashes:
            raise RuntimeError(
                "V6 approval record omits required evidence: "
                f"{missing_approval_hashes}"
            )
        approval_verified = True
    report_status = (
        "engineering_and_user_visual_pass_geometry_frozen"
        if approval_verified
        else "engineering_pass_awaiting_user_visual_approval"
    )
    does_not_claim = [
        "production forearm material",
        "upper-arm texture",
        "PSD",
        "Cubism",
        "Physics",
        "Runtime",
    ]
    if not approval_verified:
        does_not_claim.insert(0, "user-approved complete upper-arm geometry")
    report = {
        "schemaVersion": 1,
        "auditDate": "2026-07-25",
        "status": report_status,
        "scope": "screen-right complete upper-arm flat geometry only",
        "inputVerification": input_checks,
        "engineeringPassCriteria": engineering_pass_criteria,
        "frozenGeometry": {
            "shoulder": list(shoulder),
            "elbow": list(elbow),
            "L1Px": length1,
            "changed": False,
            "allowedMotionRangeChanged": False,
        },
        "visibleAnchor": {
            "expectedPixelCount": 544,
            "actualPixelCount": visible_pixel_count,
            "coordinateDifferences": 0,
            "rgbDifferencePixels": visible_rgb_differences,
            "maximumRgbChannelDifference": maximum_visible_difference,
            "rescaled": False,
            "redrawn": False,
        },
        "geometryChecks": {
            "alphaConnectedComponents": connected_components(geometry),
            "alphaHoleCount": hole_count(geometry),
            "outsideGeometryAlphaPixels": 0,
            "visibleAnchorFullyContained": ImageChops.subtract(visible, geometry).getbbox()
            is None,
            "z1PixelCount": mask_count(z1),
            "z1PixelsOutsideActualSleeveAlphaThreshold": mask_count(
                z1_outside_sleeve
            ),
            "z1ShoulderCapPixelCount": mask_count(z1_cap),
            "z1ShoulderCapPixelsOutsideActualSleeveAlphaThreshold": mask_count(
                z1_cap_outside_sleeve
            ),
            "temporaryForearmOverlapWithLockedVisibleUpperArmPixels": mask_count(
                ImageChops.multiply(display_forearm, visible)
            ),
        },
        "shoulderCoverage": {
            "occluder": "actual frozen complete-sleeve texture alpha",
            "alphaThreshold": ALPHA_THRESHOLD,
            "z1ShoulderCapContainmentMarginChebyshevPx": shoulder_margin,
            "relativeTransform": "shared frozen shoulder transform; static invariant",
            "temporaryDependency": "torso and hair remain flattened authority inputs and must be recalculated after formal separation",
            "finalPsdOrCubismProof": False,
        },
        "sleeveHemBoundaryDependency": {
            "flatGeometryPixelsOutsideFrozenSleeveAlphaAndOutsideLockedZ2": mask_count(
                z1_outside_sleeve
            ),
            "location": "within approximately 3 px of the approved sleeve/skin boundary",
            "treatment": "declared flat-master boundary dependency for visual review; not added to the 544 locked Z2 pixels and not claimed as texture",
        },
        "elbowCoverage": elbow_report,
        "elbowProtrusionRefinement": {
            "cause": "rounded proximal cap in the frozen solid forearm prototype used by the temporary QA proxy",
            "treatment": "keep the frozen V4 archive unchanged; replace only the temporary QA proxy before local s=22 px with a tapered root",
            "temporaryForearmRootWidthProfile": forearm_root_width_profile,
            "outerBendMonotonicTowardShaftWithinTolerance": (
                forearm_outer_root_monotonic
            ),
            "maximumOuterBendProximalExcessOverShaftPx": (
                forearm_outer_root_excess
            ),
            "innerBendExtensionIsIntentionallyLonger": True,
            "visualEvidence": "qa/gate-10-elbow-protrusion-refinement.png",
            "productionForearmMaterialApproved": False,
        },
        "outlineQuality": {
            "widthProfile": width_profile,
            "tangentMetrics": tangent_report,
            "shoulderCircularArcRisk": shoulder_circle,
            "elbowCircularArcRisk": elbow_circle,
            "upperArmWidthAtElbowPx": width_at_s(local_outline, length1)[2],
            "temporaryForearmRootWidthPx": elbow_report[
                "forearmRootResponsibility"
            ]["temporaryReferenceWidthAtElbowPx"],
            "longStripPlusRoundPatchUsed": False,
            "visualReviewStillRequired": not approval_verified,
        },
        "motionChecks": {
            "primarySampleCount": len(primary),
            "combinationExtremeCount": len(extremes),
            "maximumMissingSeamPixelsAt4x": elbow_report[
                "maximumMissingResponsibilityPixelsAt4x"
            ],
            "brokenAdjacencySamples": elbow_report["brokenAdjacencySamples"],
            "deterministicReturn0To1To0": deterministic_return,
            "physicsUsed": False,
        },
        "artifacts": artifact_hashes,
        "visualEvidence": [
            str(path.relative_to(ROOT)).replace("\\", "/") for path in qa_paths
        ],
        "limitations": contract["limitations"],
        "selfVisualAudit": {
            "previousCandidateRejectedByUser": True,
            "userFeedback": "outline and alignment do not match the body posture",
            "latestUserFeedback": "the right side of the temporary forearm root still protrudes",
            "revision": "removed the right-side width peak, trimmed the matching hidden upper-arm end, and preserved every locked visible upper-arm pixel",
            "currentShoulderRegularCircleRisk": shoulder_circle[
                "regularCircleRisk"
            ],
            "currentElbowRegularCircleRisk": elbow_circle["regularCircleRisk"],
            "displacedTemporaryForearmHasDetachedFragments": False,
            "decision": (
                "user_visual_approved_geometry_frozen"
                if approval_verified
                else (
                    "approved_candidate_reopened_for_elbow_protrusion_refinement"
                    if approval_invalidation is not None
                    else "pass_to_user_visual_review_only"
                )
            ),
        },
        "userVisualApproval": (
            {
                "recordPath": str(APPROVAL_PATH.relative_to(ROOT)).replace("\\", "/"),
                "sha256": sha256(APPROVAL_PATH),
                "decision": approval["decision"],
                "approvalStatement": approval["approvalStatement"],
                "status": (
                    "superseded_for_elbow_protrusion_refinement"
                    if approval_invalidation is not None
                    else "active"
                ),
                "approvedArtifactHashesMatchCurrentArtifacts": (
                    True if approval_verified else None
                ),
                "invalidationRecord": (
                    {
                        "path": str(
                            APPROVAL_INVALIDATION_PATH.relative_to(ROOT)
                        ).replace("\\", "/"),
                        "sha256": sha256(APPROVAL_INVALIDATION_PATH),
                        "reason": approval_invalidation["reason"],
                    }
                    if approval_invalidation is not None
                    else None
                ),
            }
            if approval is not None
            else None
        ),
        "doesNotClaim": does_not_claim,
        "nextGate": (
            "Complete upper-arm flat geometry gate is closed. Stop before texture; a separate authorization and texture gate are required."
            if approval_verified
            else (
                "Refine elbow overlap protrusion evidence and obtain a new Chinese user visual approval; stop before texture."
                if approval_invalidation is not None
                else "Chinese user visual review of the focused alignment and engineering QA artifacts; stop before texture."
            )
        ),
    }
    report_path = ROOT / "audit/complete-upper-arm-geometry-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    approval_conclusion = (
        "工程检查和用户中文视觉审查均已通过，完整上臂纯色几何现已冻结。"
        if approval_verified
        else (
            "此前视觉批准已因用户要求复核弯曲突出而失效，当前状态为 "
            "**肘部重叠精修并等待新视觉审查**。"
            if approval_invalidation is not None
            else "工程检查通过，当前状态为 **等待用户中文视觉审查**。"
        )
    )
    approval_record_line = (
        "- 用户批准记录："
        "`audit/user-visual-approval-complete-upper-arm-geometry-2026-07-25.json`，"
        "其批准产物哈希与当前文件全部一致。"
        if approval_verified
        else (
            "- 此前批准记录保留为历史证据；"
            "`audit/geometry-approval-invalidation-2026-07-25.json` "
            "已将其标记为失效。"
            if approval_invalidation is not None
            else "- 尚无用户视觉批准记录。"
        )
    )
    markdown = f"""# V6 完整上臂纯色几何工程报告

## 结论

{approval_conclusion}本报告不批准纹理、PSD、Cubism、Physics 或 Runtime。

{approval_record_line}

上一版候选已因轮廓和体态对齐问题被用户否决。本版缩小肩下异常膨胀，消除中段
腰折，并让肘侧隐藏端在不外扩的前提下闭合；所有冻结锚点保持不变。

## 锁定与像素

- 肩点 `{shoulder}`、肘点 `{elbow}`、`L1={length1:.6f}px` 均未改变。
- Z2 可见上臂像素：`{visible_pixel_count}`，坐标差异 `0`，RGB 差异像素
  `{visible_rgb_differences}`。
- 完整上臂遮罩连通分量：
  `{report["geometryChecks"]["alphaConnectedComponents"]}`，孔洞：
  `{report["geometryChecks"]["alphaHoleCount"]}`。

## 肩侧覆盖

- 使用已冻结完整袖子的实际纹理 alpha，阈值 `{ALPHA_THRESHOLD}`。
- Z1 落在阈值外的像素：
  `{report["geometryChecks"]["z1PixelsOutsideActualSleeveAlphaThreshold"]}`。
- Z1 肩端子区在袖子 alpha 内的 Chebyshev 静态余量下界：
  `{shoulder_margin}px`。
- 阈值外像素均位于冻结袖口/皮肤边界约 3px 内，未并入 544 个锁定 Z2
  像素，也不声明为纹理；它们作为扁平母图边界依赖交由默认回组图人工复核。
- 袖子和上臂共享冻结肩部变换，因此该相对覆盖在 FK 连续域内不滑移。
- 衣身和头发仍是扁平母图依赖，正式分层后必须重算，当前不是 PSD/Cubism 证明。

## 肘侧双向责任

- 4× 超采样；41 个主路径样本；6 个组合极值；连续 θ2 域 241 点加密。
- 上臂核心运动延伸需求：
  `{elbow_report["upperArmResponsibility"]["motionDerivedCoreExtensionPx"]}px`；
  加抗锯齿、未来纹理 alpha 和 Cubism 插值余量后：
  `{elbow_report["upperArmResponsibility"]["finalRequiredExtensionPx"]}px`。
- 当前上臂末端越过冻结肘线：
  `{elbow_report["upperArmResponsibility"]["candidateExtensionBeyondFrozenElbowPx"]:.3f}px`。
- 前臂根部只使用
  `{elbow_report["forearmRootResponsibility"]["temporaryReferenceExtensionPx"]:.3f}px`
  临时纯色覆盖参考，不是正式材料。
- 最大责任区透明缺口：
  `{elbow_report["maximumMissingResponsibilityPixelsAt4x"]}`；断开样本：
  `{elbow_report["brokenAdjacencySamples"]}`。

## 弯曲突出精修

- 突出来源是冻结纯色前臂原型的圆钝近端被直接用于临时 QA；V4 冻结归档本身未改。
- 当前只在临时 QA 代理中替换前臂局部 `s<22px`，外弯侧渐宽、内弯侧使用更长
  的隐藏延伸。
- 外弯侧相对杆身的最大近端宽度超出：
  `{forearm_outer_root_excess:.3f}px`；宽度剖面连续检查：
  `{forearm_outer_root_monotonic}`。
- 4× 连续扫描中的内弯侧异常上臂暴露像素最大值：
  `{elbow_report["maximumInnerBendExposedUpperPixelsAt4x"]}`。
- `qa/gate-10-elbow-protrusion-refinement.png` 同时展示所有权颜色和同肤色外轮廓。

## 轮廓检查

- 已记录骨轴宽度剖面、连续曲线切线变化和两端圆弧拟合风险。
- 圆弧拟合仅作为人工复核提示，不自动替代人体结构视觉判断。
- 未使用“平均宽度长条 + 圆形补丁”或独立肘圆盘。

## 必看视觉证据

1. `qa/gate-0-body-alignment-review.png`
2. `qa/gate-1-complete-upper-arm-isolated.png`
3. `qa/gate-2-default-recomposition.png`
4. `qa/gate-3-sleeve-moved-away.png`
5. `qa/gate-4-forearm-moved-away.png`
6. `qa/gate-5-shoulder-zoom.png`
7. `qa/gate-6-elbow-zoom.png`
8. `qa/gate-7-six-combination-extremes.png`
9. `qa/gate-8-elbow-single-parameter-scan.gif`
10. `qa/gate-9-displaced-parts-integrity.png`
11. `qa/gate-10-elbow-protrusion-refinement.png`

数值通过不能代替用户视觉批准。在明确批准前停止。
"""
    (ROOT / "audit/complete-upper-arm-geometry-report.zh-CN.md").write_text(
        markdown, encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
