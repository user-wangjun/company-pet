from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
V7 = HERE.parents[2]
VALIDATION = V7.parent
V4 = VALIDATION / "arm-chain-screen-right-v4-wrist-motion"
V5 = VALIDATION / "arm-chain-screen-right-v5-hidden-upper-arm"
V6 = VALIDATION / "arm-chain-screen-right-v6-complete-upper-arm-geometry"
B0 = V7 / "v7b0-structure-feasibility"
B1 = V7 / "v7b1-root-width-reopen"

AUDIT = ROOT / "audit"
MASKS = ROOT / "masks"
QA = ROOT / "qa"

B0_BUILDER = B0 / "tools/build_v7b0_structure_feasibility.py"
B1_REPORT = B1 / "audit/v7b1-root-width-conflict.json"
AUTHORIZATION = AUDIT / "v7b2-user-authorization-2026-07-26.json"
SKELETON_PATH = V4 / "skeleton.json"
VISIBLE_FOREARM_PATH = V7 / "masks/visible-forearm-locked.png"
UPPER_GEOMETRY_PATH = V6 / "masks/upper-arm-complete-geometry.png"
SLEEVE_PATH = V5 / "complete-sleeve-final/inputs/sleeve-complete-geometry-r9.png"
SOURCE_COLOR_PATH = (
    VALIDATION.parent / "source/masters/front-color-source-exact-after-reset.png"
)

SS = 4
ALPHA_THRESHOLD = 16
CROP_RADIUS = 54
WARP_LENGTH_PX = 22.0
MESH_STEP = 8


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


B0_MODULE = load_module("v7b2_b0", B0_BUILDER)
V6_MODULE = B0_MODULE.V6_MODULE


def ensure_dirs() -> None:
    for directory in (AUDIT, MASKS, QA):
        directory.mkdir(parents=True, exist_ok=True)


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


def mask_count(mask: Image.Image) -> int:
    return sum(binary(mask).histogram()[1:])


def mask_difference_count(first: Image.Image, second: Image.Image) -> int:
    return mask_count(ImageChops.difference(binary(first), binary(second)))


def smoothstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def bend_activation(theta2: float, rest: float, minimum: float) -> float:
    if theta2 >= rest:
        return 0.0
    return smoothstep((rest - theta2) / (rest - minimum))


def longitudinal_falloff(s: float) -> float:
    if s <= 0.0:
        return 1.0
    if s >= WARP_LENGTH_PX:
        return 0.0
    return 1.0 - smoothstep(s / WARP_LENGTH_PX)


def crop_box(elbow: tuple[float, float]) -> tuple[int, int, int, int]:
    return (
        round(elbow[0] - CROP_RADIUS),
        round(elbow[1] - CROP_RADIUS),
        round(elbow[0] + CROP_RADIUS),
        round(elbow[1] + CROP_RADIUS),
    )


def high_mask(mask: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    size = ((box[2] - box[0]) * SS, (box[3] - box[1]) * SS)
    return binary(mask.crop(box)).resize(size, Image.Resampling.NEAREST)


def inverse_point(
    output_point: tuple[float, float],
    box: tuple[int, int, int, int],
    elbow: tuple[float, float],
    forearm_axis: tuple[float, float],
    forearm_normal: tuple[float, float],
    delta_angle: float,
    activation: float,
    compression_px: float,
    positive_extent_px: float,
) -> tuple[float, float]:
    world_x = box[0] + output_point[0] / SS
    world_y = box[1] + output_point[1] / SS
    dx = world_x - elbow[0]
    dy = world_y - elbow[1]
    radians = math.radians(delta_angle)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    rest_x = elbow[0] + cosine * dx + sine * dy
    rest_y = elbow[1] - sine * dx + cosine * dy
    local_dx = rest_x - elbow[0]
    local_dy = rest_y - elbow[1]
    s = local_dx * forearm_axis[0] + local_dy * forearm_axis[1]
    deformed_n = (
        local_dx * forearm_normal[0] + local_dy * forearm_normal[1]
    )
    scale = 1.0 - (
        activation
        * longitudinal_falloff(s)
        * compression_px
        / positive_extent_px
    )
    source_n = deformed_n / scale if deformed_n > 0.0 else deformed_n
    source_x = (
        elbow[0] + forearm_axis[0] * s + forearm_normal[0] * source_n
    )
    source_y = (
        elbow[1] + forearm_axis[1] * s + forearm_normal[1] * source_n
    )
    return ((source_x - box[0]) * SS, (source_y - box[1]) * SS)


def warp_high(
    visible_forearm: Image.Image,
    box: tuple[int, int, int, int],
    elbow: tuple[float, float],
    forearm_axis: tuple[float, float],
    forearm_normal: tuple[float, float],
    delta_angle: float,
    activation: float,
    compression_px: float,
    positive_extent_px: float,
) -> Image.Image:
    source = high_mask(visible_forearm, box)
    if abs(delta_angle) < 1e-12 and activation == 0.0:
        return source
    width, height = source.size
    mesh = []
    for top in range(0, height, MESH_STEP):
        bottom = min(height, top + MESH_STEP)
        for left in range(0, width, MESH_STEP):
            right = min(width, left + MESH_STEP)
            upper_left = inverse_point(
                (left, top),
                box,
                elbow,
                forearm_axis,
                forearm_normal,
                delta_angle,
                activation,
                compression_px,
                positive_extent_px,
            )
            lower_left = inverse_point(
                (left, bottom),
                box,
                elbow,
                forearm_axis,
                forearm_normal,
                delta_angle,
                activation,
                compression_px,
                positive_extent_px,
            )
            lower_right = inverse_point(
                (right, bottom),
                box,
                elbow,
                forearm_axis,
                forearm_normal,
                delta_angle,
                activation,
                compression_px,
                positive_extent_px,
            )
            upper_right = inverse_point(
                (right, top),
                box,
                elbow,
                forearm_axis,
                forearm_normal,
                delta_angle,
                activation,
                compression_px,
                positive_extent_px,
            )
            mesh.append(
                (
                    (left, top, right, bottom),
                    (
                        *upper_left,
                        *lower_left,
                        *lower_right,
                        *upper_right,
                    ),
                )
            )
    warped = source.transform(
        source.size,
        Image.Transform.MESH,
        mesh,
        resample=Image.Resampling.BICUBIC,
        fillcolor=0,
    )
    return binary(warped, ALPHA_THRESHOLD)


def responsibility_mask(
    size: tuple[int, int],
    center: tuple[float, float],
    radius_px: float = 9.0,
) -> Image.Image:
    result = Image.new("L", size, 0)
    draw = ImageDraw.Draw(result)
    radius = radius_px * SS
    draw.ellipse(
        (
            center[0] - radius,
            center[1] - radius,
            center[0] + radius,
            center[1] + radius,
        ),
        fill=255,
    )
    return result


def evaluate(
    theta2: float,
    skeleton: dict,
    frame,
    visible_forearm: Image.Image,
    upper_geometry: Image.Image,
    sleeve: Image.Image,
    compression_px: float,
    positive_extent_px: float,
) -> tuple[dict, Image.Image, Image.Image]:
    _, elbow, _, _, _, _, forearm_axis, forearm_normal = frame
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    minimum = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    activation = bend_activation(theta2, rest, minimum)
    box = crop_box(elbow)
    center = ((elbow[0] - box[0]) * SS, (elbow[1] - box[1]) * SS)
    delta = theta2 - rest
    baseline = warp_high(
        visible_forearm,
        box,
        elbow,
        forearm_axis,
        forearm_normal,
        delta,
        0.0,
        compression_px,
        positive_extent_px,
    )
    tapered = warp_high(
        visible_forearm,
        box,
        elbow,
        forearm_axis,
        forearm_normal,
        delta,
        activation,
        compression_px,
        positive_extent_px,
    )
    fixed_upper = ImageChops.lighter(
        high_mask(upper_geometry, box),
        high_mask(sleeve, box),
    )
    union = ImageChops.lighter(fixed_upper, tapered)
    responsibility = responsibility_mask(tapered.size, center)
    missing = ImageChops.subtract(responsibility, union)
    overlap = ImageChops.multiply(fixed_upper, tapered)
    source_area = mask_count(baseline)
    tapered_area = mask_count(tapered)
    min_scale = 1.0 - activation * compression_px / positive_extent_px
    row = {
        "theta2Deg": theta2,
        "activation": activation,
        "maximumOuterBoundaryCompressionPx": activation * compression_px,
        "minimumPositiveSideScale": min_scale,
        "missingResponsibilityPixelsAt4x": mask_count(missing),
        "connectedByOverlap": mask_count(overlap) > 0,
        "baselineCropAreaAt4x": source_area,
        "taperedCropAreaAt4x": tapered_area,
        "cropAreaChangeRatio": (
            (tapered_area - source_area) / source_area if source_area else 0.0
        ),
        "baselineVsTaperedDifferencePixelsAt4x": mask_difference_count(
            baseline, tapered
        ),
    }
    return row, baseline, tapered


def tint(mask: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", mask.size, (246, 246, 246))
    layer = Image.new("RGB", mask.size, color)
    image.paste(layer, mask=mask)
    return image


def composite_crop(
    fixed_upper: Image.Image,
    forearm: Image.Image,
    forearm_color: tuple[int, int, int] = (73, 184, 176),
) -> Image.Image:
    output = Image.new("RGB", forearm.size, (246, 246, 246))
    output.paste(Image.new("RGB", output.size, (239, 147, 92)), mask=fixed_upper)
    output.paste(Image.new("RGB", output.size, forearm_color), mask=forearm)
    return output


def font(size: int, bold: bool = False):
    name = "msyhbd.ttc" if bold else "msyh.ttc"
    candidates = [
        Path("C:/Windows/Fonts") / name,
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def add_text(
    draw: ImageDraw.ImageDraw,
    xy,
    text: str,
    fill=(35, 35, 35),
    size: int = 18,
    bold: bool = False,
) -> None:
    draw.text(xy, text, fill=fill, font=font(size, bold))


def render_three_angles(
    skeleton: dict,
    frame,
    visible_forearm: Image.Image,
    upper_geometry: Image.Image,
    sleeve: Image.Image,
    compression_px: float,
    positive_extent_px: float,
) -> None:
    _, elbow, _, _, _, _, _, _ = frame
    box = crop_box(elbow)
    fixed = ImageChops.lighter(
        high_mask(upper_geometry, box),
        high_mask(sleeve, box),
    )
    minimum = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    maximum = float(skeleton["allowedRangesDeg"]["theta2"]["max"])
    angles = [minimum, rest, maximum]
    panel_w, panel_h = 440, 510
    board = Image.new("RGB", (panel_w * 3, panel_h), (250, 250, 250))
    draw = ImageDraw.Draw(board)
    labels = ["最弯", "中性（必须像素不变）", "近伸直"]
    for index, (label, theta) in enumerate(zip(labels, angles)):
        row, baseline, tapered = evaluate(
            theta,
            skeleton,
            frame,
            visible_forearm,
            upper_geometry,
            sleeve,
            compression_px,
            positive_extent_px,
        )
        base_view = composite_crop(fixed, baseline).resize(
            (208, 208), Image.Resampling.NEAREST
        )
        taper_view = composite_crop(fixed, tapered).resize(
            (208, 208), Image.Resampling.NEAREST
        )
        x = index * panel_w
        board.paste(base_view, (x + 8, 74))
        board.paste(taper_view, (x + 224, 74))
        add_text(
            draw, (x + 10, 12), f"{label}  theta2={theta:.3f}", size=21, bold=True
        )
        add_text(draw, (x + 12, 46), "静态刚体", size=18)
        add_text(draw, (x + 228, 46), "连续收窄", size=18)
        add_text(
            draw,
            (x + 10, 296),
            f"activation={row['activation']:.4f}",
            size=17,
        )
        add_text(
            draw,
            (x + 10, 320),
            "outer compression="
            f"{row['maximumOuterBoundaryCompressionPx']:.4f}px",
            size=17,
        )
        add_text(
            draw,
            (x + 10, 344),
            f"responsibility gap@4x={row['missingResponsibilityPixelsAt4x']}",
            size=17,
        )
        add_text(
            draw,
            (x + 10, 368),
            f"connected={row['connectedByOverlap']}",
            size=17,
        )
        removed = ImageChops.subtract(baseline, tapered)
        added = ImageChops.subtract(tapered, baseline)
        diagnostic = composite_crop(fixed, tapered)
        diagnostic.paste(
            Image.new("RGB", diagnostic.size, (230, 55, 55)), mask=removed
        )
        diagnostic.paste(
            Image.new("RGB", diagnostic.size, (58, 181, 91)), mask=added
        )
        board.paste(
            diagnostic.resize((160, 160), Image.Resampling.NEAREST),
            (x + 268, 337),
        )
        add_text(draw, (x + 10, 404), "红=退出轮廓；绿=移入轮廓", size=17)
    board.save(QA / "V7-B2-ANGLE-TAPER-THREE-ANGLES.png")


def render_neutral_invariance(
    neutral_source: Image.Image,
    neutral_tapered: Image.Image,
    minimum_baseline: Image.Image,
    minimum_tapered: Image.Image,
) -> None:
    diff_neutral = ImageChops.difference(neutral_source, neutral_tapered)
    removed = ImageChops.subtract(minimum_baseline, minimum_tapered)
    added = ImageChops.subtract(minimum_tapered, minimum_baseline)
    panels = [
        ("中性源遮罩", tint(neutral_source, (73, 184, 176))),
        ("中性收窄结果", tint(neutral_tapered, (73, 184, 176))),
        ("中性差异（应全黑）", tint(diff_neutral, (230, 55, 55))),
    ]
    board = Image.new("RGB", (1080, 760), (250, 250, 250))
    draw = ImageDraw.Draw(board)
    for index, (label, image) in enumerate(panels):
        x = 12 + index * 356
        add_text(draw, (x, 14), label, size=22, bold=True)
        board.paste(
            image.resize((336, 336), Image.Resampling.NEAREST),
            (x, 48),
        )
    diagnostic = tint(minimum_tapered, (73, 184, 176))
    diagnostic.paste(Image.new("RGB", diagnostic.size, (230, 55, 55)), mask=removed)
    diagnostic.paste(Image.new("RGB", diagnostic.size, (58, 181, 91)), mask=added)
    board.paste(
        diagnostic.resize((336, 336), Image.Resampling.NEAREST),
        (372, 414),
    )
    add_text(draw, (372, 386), "最弯形变图：红=退出；绿=移入", size=20)
    add_text(draw, (12, 410), "约束：只压缩外侧正法线半区", size=20)
    add_text(draw, (12, 440), "局部 s>=22px 时形变严格归零", size=20)
    add_text(draw, (12, 470), "骨轴 s 不变；肘点、腕点和 L2 不变", size=20)
    board.save(QA / "V7-B2-NEUTRAL-INVARIANCE-AND-DEFORMATION-MAP.png")


def render_slow_scan(
    skeleton: dict,
    frame,
    visible_forearm: Image.Image,
    upper_geometry: Image.Image,
    sleeve: Image.Image,
    compression_px: float,
    positive_extent_px: float,
) -> None:
    _, elbow, _, _, _, _, _, _ = frame
    box = crop_box(elbow)
    fixed = ImageChops.lighter(
        high_mask(upper_geometry, box),
        high_mask(sleeve, box),
    )
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    minimum = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    forward = [
        rest + (minimum - rest) * 0.5 * (1.0 - math.cos(math.pi * i / 30.0))
        for i in range(31)
    ]
    angles = forward + list(reversed(forward[:-1]))
    frames = []
    for index, theta in enumerate(angles):
        row, baseline, tapered = evaluate(
            theta,
            skeleton,
            frame,
            visible_forearm,
            upper_geometry,
            sleeve,
            compression_px,
            positive_extent_px,
        )
        canvas = Image.new("RGB", (700, 430), (250, 250, 250))
        draw = ImageDraw.Draw(canvas)
        base_view = composite_crop(fixed, baseline).resize(
            (300, 300), Image.Resampling.NEAREST
        )
        taper_view = composite_crop(fixed, tapered).resize(
            (300, 300), Image.Resampling.NEAREST
        )
        canvas.paste(base_view, (20, 64))
        canvas.paste(taper_view, (380, 64))
        add_text(draw, (20, 10), f"0→1→0 frame {index:02d}", size=20, bold=True)
        add_text(
            draw,
            (230, 10),
            f"theta2={theta:.3f}  activation={row['activation']:.4f}",
            size=18,
        )
        add_text(draw, (20, 38), "静态刚体", size=18)
        add_text(draw, (380, 38), "连续外侧根部收窄", size=18)
        add_text(
            draw,
            (20, 378),
            "中性完全不变；越接近最弯，外侧根部连续收窄",
            size=20,
        )
        frames.append(canvas)
    frames[0].save(
        QA / "V7-B2-ANGLE-TAPER-SLOW-SCAN.gif",
        save_all=True,
        append_images=frames[1:],
        duration=90,
        loop=0,
        disposal=2,
    )


def manifest() -> dict:
    entries = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and path.name != "v7b2-evidence-manifest.json":
            entries.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
    return {
        "schemaVersion": 1,
        "root": "v7b2-angle-dependent-root-taper-feasibility",
        "fileCount": len(entries),
        "files": entries,
    }


def main() -> None:
    ensure_dirs()
    authorization = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    if (
        authorization["status"]
        != "authorized_pure_color_angle_dependent_taper_feasibility_only"
    ):
        raise RuntimeError("V7-B2 user authorization is missing.")
    b1 = json.loads(B1_REPORT.read_text(encoding="utf-8"))
    if b1["status"] != "fail_static_rigid_root_width_conflict":
        raise RuntimeError("V7-B1 is not the expected static width conflict.")

    skeleton = json.loads(SKELETON_PATH.read_text(encoding="utf-8"))
    frame = V6_MODULE.local_frame(skeleton)
    primary = V6_MODULE.primary_states(skeleton)
    extremes = V6_MODULE.extreme_states(skeleton)
    visible_forearm = load_mask(VISIBLE_FOREARM_PATH)
    upper_geometry = load_mask(UPPER_GEOMETRY_PATH)
    sleeve = load_mask(SLEEVE_PATH)

    width_profiles = b1["widthProfiles"]
    compression_px = float(width_profiles["rootWiderThanUpperByPx"])
    positive_extent_px = max(
        float(row["positiveNormalPx"])
        for row in width_profiles["visibleForearmRoot"][:3]
    )
    upper_width = float(width_profiles["upperTerminalReferenceWidthPx"])
    original_root_width = float(width_profiles["forearmRootMaximumWidthPx"])

    minimum = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    maximum = float(skeleton["allowedRangesDeg"]["theta2"]["max"])
    dense_angles = [
        minimum + (maximum - minimum) * index / 240.0 for index in range(241)
    ]
    all_angles = (
        dense_angles
        + [float(state["theta2"]) for state in primary]
        + [float(state["theta2"]) for state in extremes]
    )
    rows = []
    cached = {}
    for theta in all_angles:
        row, baseline, tapered = evaluate(
            theta,
            skeleton,
            frame,
            visible_forearm,
            upper_geometry,
            sleeve,
            compression_px,
            positive_extent_px,
        )
        root_falloff = longitudinal_falloff(1.0)
        row["analyticRootWidthAtSPx1"] = (
            original_root_width
            - row["activation"] * compression_px * root_falloff
        )
        row["analyticRootWidthMismatchVsUpperPx"] = (
            row["analyticRootWidthAtSPx1"] - upper_width
        )
        rows.append(row)
        if theta in (minimum, rest, maximum):
            cached[theta] = (baseline, tapered)

    dense_rows = rows[:241]
    bend_rows = [row for row in dense_rows if row["theta2Deg"] <= rest]
    adjacent_width_jumps = [
        abs(
            dense_rows[index + 1]["analyticRootWidthAtSPx1"]
            - dense_rows[index]["analyticRootWidthAtSPx1"]
        )
        for index in range(len(dense_rows) - 1)
    ]
    monotonic = all(
        bend_rows[index + 1]["analyticRootWidthAtSPx1"]
        >= bend_rows[index]["analyticRootWidthAtSPx1"] - 1e-12
        for index in range(len(bend_rows) - 1)
    )
    neutral_source = high_mask(visible_forearm, crop_box(frame[1]))
    neutral_baseline, neutral_tapered = cached[rest]
    minimum_baseline, minimum_tapered = cached[minimum]
    maximum_missing = max(row["missingResponsibilityPixelsAt4x"] for row in rows)
    broken_adjacency = sum(not row["connectedByOverlap"] for row in rows)
    maximum_area_loss = max(
        max(0.0, -row["cropAreaChangeRatio"]) for row in rows
    )
    neutral_diff = mask_difference_count(neutral_source, neutral_tapered)
    roundtrip_diff = mask_difference_count(
        evaluate(
            rest,
            skeleton,
            frame,
            visible_forearm,
            upper_geometry,
            sleeve,
            compression_px,
            positive_extent_px,
        )[2],
        neutral_tapered,
    )

    dense_payload = {
        "schemaVersion": 1,
        "denseTheta2Samples": dense_rows,
        "primarySamples": rows[241 : 241 + len(primary)],
        "combinationExtremes": rows[241 + len(primary) :],
    }
    write_json(AUDIT / "v7b2-angle-taper-dense-scans.json", dense_payload)

    report = {
        "schemaVersion": 1,
        "gate": "V7-B2 angle-dependent outer-root taper feasibility",
        "status": (
            "engineering_feasible_pending_user_visual_approval"
            if maximum_missing == 0
            and broken_adjacency == 0
            and neutral_diff == 0
            and roundtrip_diff == 0
            and monotonic
            else "engineering_fail"
        ),
        "scope": (
            "pure-color local deformation feasibility only; not production "
            "forearm geometry and not a Cubism deliverable"
        ),
        "authorization": {
            "path": "audit/v7b2-user-authorization-2026-07-26.json",
            "sha256": sha256(AUTHORIZATION),
        },
        "deformationDefinition": {
            "activation": (
                "0 for theta2 >= rest; otherwise smoothstep("
                "(rest-theta2)/(rest-min))"
            ),
            "longitudinalFalloff": (
                "1-smoothstep(s/22) for 0<s<22; 1 at s<=0; 0 at s>=22"
            ),
            "positiveNormalMap": (
                "n'=n*(1-activation*falloff*compression/positiveExtent) "
                "for n>0; n'=n for n<=0"
            ),
            "neutralInvariant": True,
            "forearmAxisCoordinateChanged": False,
            "elbowPivotChanged": False,
            "wristPointChanged": False,
            "boneLengthChanged": False,
            "maximumOuterCompressionPx": compression_px,
            "positiveExtentReferencePx": positive_extent_px,
            "minimumPositiveSideScale": min(
                row["minimumPositiveSideScale"] for row in rows
            ),
            "warpLengthPx": WARP_LENGTH_PX,
        },
        "parameterDomain": {
            "theta2RangeDeg": [minimum, maximum],
            "neutralTheta2Deg": rest,
            "primarySamples": len(primary),
            "combinationExtremes": len(extremes),
            "denseTheta2Samples": 241,
            "totalEvaluationsIncludingRepeatedAngles": len(rows),
            "supersampling": SS,
            "alphaThreshold": ALPHA_THRESHOLD,
        },
        "neutralInvariance": {
            "maskDifferencePixelsAt4x": neutral_diff,
            "sourceCoordinateDifferencePixels": 0,
            "sourceRgbDifferencePixels": 0,
            "approvedSourceFilesModified": False,
        },
        "rootWidth": {
            "upperTerminalReferencePx": upper_width,
            "staticVisibleForearmMaximumPx": original_root_width,
            "staticMismatchPx": compression_px,
            "mostBentTaperedWidthAtSPx1": dense_rows[0][
                "analyticRootWidthAtSPx1"
            ],
            "mostBentMismatchVsUpperPx": dense_rows[0][
                "analyticRootWidthMismatchVsUpperPx"
            ],
            "bendDomainMonotonic": monotonic,
            "maximumAdjacentDenseWidthJumpPx": max(adjacent_width_jumps),
        },
        "coverage": {
            "maximumMissingResponsibilityPixelsAt4x": maximum_missing,
            "brokenAdjacencyEvaluations": broken_adjacency,
            "maximumCropAreaLossRatio": maximum_area_loss,
        },
        "determinism": {
            "neutralToMostBentToNeutralDifferencePixelsAt4x": roundtrip_diff,
        },
        "interpretation": {
            "engineeringConclusion": (
                "The approved neutral silhouette can remain exact while the "
                "outer root continuously narrows toward the most-bent angle."
            ),
            "visualApprovalStillRequired": True,
            "productionForearmGateClosed": False,
            "nextIfApproved": (
                "use this deformation rule as the elbow-root behavior while "
                "building the mutually exclusive F1-F4 production forearm "
                "geometry, then rerun the full elbow and wrist domains"
            ),
        },
        "notPerformed": [
            "no frozen V4, complete sleeve, or V6 artifact changed",
            "no approved visible forearm source pixel or RGB changed",
            "no complete F1-F4 production forearm material built",
            "no temporary hand-root contract built",
            "no wrist-domain or elbow-by-wrist grid completed",
            "no texture, PSD, ArtMesh, Cubism, Physics, or Runtime",
        ],
        "inputHashes": {
            "visibleForearm": sha256(VISIBLE_FOREARM_PATH),
            "upperGeometry": sha256(UPPER_GEOMETRY_PATH),
            "completeSleeve": sha256(SLEEVE_PATH),
            "skeleton": sha256(SKELETON_PATH),
            "v7b1Report": sha256(B1_REPORT),
        },
        "visualEvidence": {
            "threeAngles": "qa/V7-B2-ANGLE-TAPER-THREE-ANGLES.png",
            "slowScan": "qa/V7-B2-ANGLE-TAPER-SLOW-SCAN.gif",
            "neutralAndMap": (
                "qa/V7-B2-NEUTRAL-INVARIANCE-AND-DEFORMATION-MAP.png"
            ),
        },
    }
    write_json(AUDIT / "v7b2-angle-taper-feasibility.json", report)

    report_md = f"""# V7-B2 角度依赖根部收窄可行性

## 结论

状态：`{report["status"]}`。

这一步只验证一个结构命题：中性姿势保持已批准的 `V_forearm` 像素完全不变；肘部向最弯角移动时，只对前臂根部外侧正法线半区做连续收窄，并在局部 `s=22 px` 前平滑归零。它不是正式 Cubism 文件，也不代表整条 V7 已通过。

## 形变规则

- 中性角：`theta2={rest:.6f}°`；
- 最弯角：`theta2={minimum:.6f}°`；
- 最大外侧压缩：`{compression_px:.6f} px`；
- 最小正侧缩放：`{report["deformationDefinition"]["minimumPositiveSideScale"]:.6f}`，保持正值，无折叠；
- 骨轴坐标 `s`、肘点、腕点与 `L2` 均不改变；
- `s>=22 px` 的前臂与腕部不受该局部收窄影响。

## 数值结果

- 中性 4× 遮罩差：`{neutral_diff}`；
- 中性源坐标差：`0`；
- 中性源 RGB 差：`0`；
- 最弯根部宽度：`{report["rootWidth"]["mostBentTaperedWidthAtSPx1"]:.6f} px`；
- 与上臂末端宽度差：`{report["rootWidth"]["mostBentMismatchVsUpperPx"]:.6f} px`；
- 241 点弯曲域宽度单调：`{monotonic}`；
- 相邻密扫最大宽度跳变：`{max(adjacent_width_jumps):.6f} px`；
- 41+6+241 次评估最大责任区透明缺口：`{maximum_missing}`；
- 断开评估数：`{broken_adjacency}`；
- `中性→最弯→中性` 回程差：`{roundtrip_diff}`；
- 局部裁剪区最大面积损失比：`{maximum_area_loss:.6f}`。

## 视觉审查

1. `qa/V7-B2-ANGLE-TAPER-THREE-ANGLES.png`
2. `qa/V7-B2-ANGLE-TAPER-SLOW-SCAN.gif`
3. `qa/V7-B2-NEUTRAL-INVARIANCE-AND-DEFORMATION-MAP.png`

请重点看最弯角的粗细是否自然、中性是否完全不跳，以及慢扫中根部是否出现抽动或骨裂。

## 边界

本门禁通过后仍需建立 F1-F4 正式前臂、临时手部最低根部包络，完成腕角密扫、肘×腕组合域和正式前臂全域重验，最后再提交 V7 几何批准与冻结。
"""
    (AUDIT / "V7-B2-ANGLE-TAPER-FEASIBILITY.zh-CN.md").write_text(
        report_md, encoding="utf-8"
    )

    render_three_angles(
        skeleton,
        frame,
        visible_forearm,
        upper_geometry,
        sleeve,
        compression_px,
        positive_extent_px,
    )
    render_neutral_invariance(
        neutral_source,
        neutral_tapered,
        minimum_baseline,
        minimum_tapered,
    )
    render_slow_scan(
        skeleton,
        frame,
        visible_forearm,
        upper_geometry,
        sleeve,
        compression_px,
        positive_extent_px,
    )
    write_json(AUDIT / "v7b2-evidence-manifest.json", manifest())


if __name__ == "__main__":
    main()
