from __future__ import annotations

import io
import json
import math
import statistics
import zipfile
from datetime import date
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps


HERE = Path(__file__).resolve()
XIAOXING_ROOT = HERE.parents[3]
ROOT = HERE.parents[1]
V4_ZIP_PATH = (
    XIAOXING_ROOT
    / "validation"
    / "arm-chain-screen-right-v4-wrist-motion"
    / "archive"
    / "stage-a-v4-approved-2026-07-24.zip"
)
COLOR_PATH = XIAOXING_ROOT / "source" / "masters" / "front-color-source-exact-after-reset.png"
VISIBLE_MASK_PATH = ROOT / "masks" / "visible-upper-arm-locked.png"
H_TEST_MASK_PATH = ROOT / "masks" / "hidden-upper-arm-sleeve-test-roi.png"
SLEEVE_MASK_PATH = ROOT / "masks" / "sleeve-hem-occluder-alpha-locked.png"
MIXED_BAND_PATH = ROOT / "masks" / "sleeve-hem-aa-mixed-band.png"
SEAM_RESPONSIBILITY_PATH = ROOT / "masks" / "sleeve-upper-arm-seam-responsibility.png"
VISIBLE_REFERENCE_PATH = ROOT / "qa" / "visible-upper-arm-source-pixels-reference.png"
OWNERSHIP_APPROVAL_PATH = ROOT / "audit" / "ownership-gate-user-approval-2026-07-25.json"
COVERAGE_AUDIT_PATH = ROOT / "audit" / "hidden-roi-and-coverage.json"

MATERIALS_DIR = ROOT / "materials" / "textured"
QA_DIR = ROOT / "qa"
AUDIT_DIR = ROOT / "audit"

MATERIAL_PATH = MATERIALS_DIR / "upper-arm-sleeve-hidden-test.png"
SAFE_SLEEVE_MASK_PATH = ROOT / "masks" / "sleeve-hem-qa-context-safe.png"
REJECTED_SLEEVE_PIXELS_PATH = (
    ROOT / "masks" / "sleeve-hem-qa-context-rejected-source-pixels.png"
)
CHECKER_PATH = QA_DIR / "upper-arm-sleeve-hidden-test-checkerboard.png"
SAFE_SLEEVE_CHECKER_PATH = QA_DIR / "sleeve-hem-qa-context-safe-checkerboard.png"
SAFE_SLEEVE_REVIEW_PATH = QA_DIR / "sleeve-hem-qa-context-purity-review.png"
DEFAULT_PATH = QA_DIR / "default-recomposition.png"
SLEEVE_AWAY_PATH = QA_DIR / "sleeve-moved-away.png"
MAX_100_PATH = QA_DIR / "maximum-exposure-100.png"
MAX_200_PATH = QA_DIR / "maximum-exposure-200.png"
SCAN_PATH = QA_DIR / "maximum-exposure-single-parameter-scan.gif"
FK_41_PATH = QA_DIR / "fk-41-textured-alpha-slow-preview.gif"
EXTREMES_PATH = QA_DIR / "six-combination-extremes.png"
EPSILON_PATH = QA_DIR / "critical-epsilon-no-exposure.gif"
GRAYSCALE_PATH = QA_DIR / "maximum-exposure-grayscale.png"
EDGE_PATH = QA_DIR / "maximum-exposure-edge-enhanced.png"
FLICKER_PATH = QA_DIR / "seam-flicker-edge-preview.gif"

PIXEL_AUDIT_PATH = AUDIT_DIR / "textured-pixel-identity-and-scope.json"
ALPHA_AUDIT_PATH = AUDIT_DIR / "textured-alpha-and-flicker.json"
TEXTURE_AUDIT_PATH = AUDIT_DIR / "hidden-texture-method.json"
SAFE_SLEEVE_AUDIT_PATH = AUDIT_DIR / "sleeve-hem-qa-context-purity.json"
STAGE_REPORT_PATH = AUDIT_DIR / "stage-b-report.zh-CN.md"
FINAL_VISUAL_REJECTION_PATH = (
    AUDIT_DIR / "REJECTED-STAGE-B-HIDDEN-TEXTURE-CANDIDATE-2026-07-25.md"
)

CANVAS = (512, 1086)
LOCAL_CROP = (305, 235, 420, 445)
MAX_CROP = (326, 355, 378, 423)
EPSILON_DEG = 0.05
TRANSPARENT_GAP_ALPHA_THRESHOLD = 16
STRONG_EXPOSURE_ALPHA_THRESHOLD = 128
SOFT_COVERAGE_ALPHA_THRESHOLD = 250
MAX_SOFT_RESPONSIBILITY_PIXELS = 1


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def alpha(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if image.size != CANVAS:
        raise RuntimeError(f"Unexpected canvas: {path.name} {image.size}")
    return image.getchannel("A")


def alpha_png(mask: Image.Image) -> Image.Image:
    image = Image.new("RGBA", CANVAS, (255, 255, 255, 0))
    image.putalpha(mask)
    return image


def points(mask: Image.Image) -> list[tuple[int, int]]:
    bbox = mask.getbbox()
    if bbox is None:
        return []
    return [
        (x, y)
        for y in range(bbox[1], bbox[3])
        for x in range(bbox[0], bbox[2])
        if mask.getpixel((x, y))
    ]


def solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for pivot in range(size):
        best = max(range(pivot, size), key=lambda row: abs(augmented[row][pivot]))
        augmented[pivot], augmented[best] = augmented[best], augmented[pivot]
        value = augmented[pivot][pivot]
        if abs(value) < 1e-9:
            raise RuntimeError("Texture gradient fit is singular.")
        augmented[pivot] = [item / value for item in augmented[pivot]]
        for row in range(size):
            if row == pivot:
                continue
            factor = augmented[row][pivot]
            augmented[row] = [
                item - factor * source
                for item, source in zip(augmented[row], augmented[pivot])
            ]
    return [augmented[row][-1] for row in range(size)]


def fit_channel(
    samples: list[tuple[list[float], tuple[int, int, int]]],
    channel: int,
) -> list[float]:
    feature_count = len(samples[0][0])
    matrix = [[0.0] * feature_count for _ in range(feature_count)]
    vector = [0.0] * feature_count
    for feature, rgb in samples:
        for row in range(feature_count):
            vector[row] += feature[row] * rgb[channel]
            for column in range(feature_count):
                matrix[row][column] += feature[row] * feature[column]
    for diagonal in range(feature_count):
        matrix[diagonal][diagonal] += 1e-6
    return solve_linear(matrix, vector)


def predict(coefficients: list[float], feature: list[float]) -> float:
    return sum(coefficient * value for coefficient, value in zip(coefficients, feature))


def clamp_channel(value: float) -> int:
    return max(0, min(255, int(round(value))))


def checkerboard(size: tuple[int, int], cell: int = 10) -> Image.Image:
    image = Image.new("RGB", size, (224, 224, 224))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle(
                    (x, y, min(x + cell - 1, size[0] - 1), min(y + cell - 1, size[1] - 1)),
                    fill=(248, 248, 248),
                )
    return image


def add_header(
    image: Image.Image,
    title: str,
    note: str = "",
    min_width: int = 720,
) -> Image.Image:
    width = max(min_width, image.width)
    header = 64 if note else 44
    canvas = Image.new("RGB", (width, image.height + header), (240, 240, 240))
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 4), title, font=font(22), fill=(20, 20, 20))
    if note:
        draw.text((10, 35), note, font=font(14), fill=(65, 65, 65))
    canvas.paste(image.convert("RGB"), ((width - image.width) // 2, header))
    return canvas


def checker_composite(
    layer: Image.Image,
    crop: tuple[int, int, int, int],
    scale: int,
) -> Image.Image:
    cropped = layer.crop(crop)
    size = (cropped.width * scale, cropped.height * scale)
    board = checkerboard(size, max(4, 8 * scale))
    scaled = cropped.resize(size, Image.Resampling.NEAREST)
    board.paste(scaled, (0, 0), scaled.getchannel("A"))
    return board


def inverse_affine(
    angle_deg: float,
    origin: tuple[float, float],
) -> tuple[float, float, float, float, float, float]:
    angle = math.radians(angle_deg)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    ox, oy = origin
    return (
        cosine,
        sine,
        ox - cosine * ox - sine * oy,
        -sine,
        cosine,
        oy + sine * ox - cosine * oy,
    )


def transform_rgba(
    image: Image.Image,
    angle_deg: float,
    origin: tuple[float, float],
) -> Image.Image:
    return image.transform(
        CANVAS,
        Image.Transform.AFFINE,
        inverse_affine(angle_deg, origin),
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )


def transform_mask(
    mask: Image.Image,
    angle_deg: float,
    origin: tuple[float, float],
) -> Image.Image:
    return mask.transform(
        CANVAS,
        Image.Transform.AFFINE,
        inverse_affine(angle_deg, origin),
        resample=Image.Resampling.BICUBIC,
        fillcolor=0,
    )


def translate_rgba(image: Image.Image, dx: int, dy: int) -> Image.Image:
    output = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    output.alpha_composite(image, (dx, dy))
    return output


def local_frame(
    shoulder: tuple[float, float],
    elbow: tuple[float, float],
):
    length = math.dist(shoulder, elbow)
    unit = (
        (elbow[0] - shoulder[0]) / length,
        (elbow[1] - shoulder[1]) / length,
    )
    normal = (-unit[1], unit[0])

    def convert(point: tuple[float, float]) -> tuple[float, float]:
        delta = (point[0] - shoulder[0], point[1] - shoulder[1])
        return (
            delta[0] * unit[0] + delta[1] * unit[1],
            delta[0] * normal[0] + delta[1] * normal[1],
        )

    return length, unit, normal, convert


def build_texture(
    color: Image.Image,
    visible: Image.Image,
    h_test: Image.Image,
    upper_material: Image.Image,
    shoulder: tuple[float, float],
    elbow: tuple[float, float],
    half_width: float,
) -> tuple[Image.Image, dict[str, object]]:
    _, _, _, local = local_frame(shoulder, elbow)
    visible_points = points(visible)
    h_points = points(h_test)
    visible_s_min = min(local(point)[0] for point in visible_points)
    s_center = visible_s_min + 13.0

    def feature(point: tuple[int, int], clamp_hidden: bool) -> list[float]:
        s, q = local(point)
        if clamp_hidden:
            s = max(s, visible_s_min + 7.0)
        s_norm = (s - s_center) / 14.0
        q_norm = q / half_width
        return [1.0, s_norm, q_norm, q_norm * q_norm]

    training: list[tuple[list[float], tuple[int, int, int]]] = []
    seam_core: list[tuple[tuple[int, int], tuple[int, int, int]]] = []
    for point in visible_points:
        rgb = color.getpixel(point)
        red, green, blue = rgb
        s, q = local(point)
        is_skin = red >= 205 and red - green >= 8 and green - blue >= 2
        if (
            is_skin
            and s >= visible_s_min + 7.0
            and abs(q) <= half_width * 0.72
        ):
            training.append((feature(point, False), rgb))
        if (
            is_skin
            and visible_s_min <= s <= visible_s_min + 6.0
            and abs(q) <= half_width * 0.65
        ):
            seam_core.append((point, rgb))
    if len(training) < 40 or len(seam_core) < 8:
        raise RuntimeError(
            f"Insufficient source skin evidence: training={len(training)}, seam={len(seam_core)}"
        )

    coefficients = [fit_channel(training, channel) for channel in range(3)]
    seam_residuals = [[], [], []]
    for point, rgb in seam_core:
        base_feature = feature(point, True)
        for channel in range(3):
            seam_residuals[channel].append(
                rgb[channel] - predict(coefficients[channel], base_feature)
            )
    shadow_delta = [
        max(-34.0, min(0.0, statistics.median(values)))
        for values in seam_residuals
    ]

    boundary = set()
    for point in h_points:
        x, y = point
        if any(
            not upper_material.getpixel((x + dx, y + dy))
            for dx, dy in (
                (-1, -1),
                (0, -1),
                (1, -1),
                (-1, 0),
                (1, 0),
                (-1, 1),
                (0, 1),
                (1, 1),
            )
            if 0 <= x + dx < CANVAS[0] and 0 <= y + dy < CANVAS[1]
        ):
            boundary.add(point)
    inner_boundary = {
        point
        for point in h_points
        if point not in boundary
        and any(
            (point[0] + dx, point[1] + dy) in boundary
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
        )
    }

    visible_edge_colors: dict[str, list[tuple[int, int, int]]] = {
        "negative": [],
        "positive": [],
    }
    for point in visible_points:
        x, y = point
        if not any(
            not upper_material.getpixel((x + dx, y + dy))
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
            if 0 <= x + dx < CANVAS[0] and 0 <= y + dy < CANVAS[1]
        ):
            continue
        _, q = local(point)
        visible_edge_colors["negative" if q < 0 else "positive"].append(
            color.getpixel(point)
        )

    fallback_line = (166, 132, 119)
    line_colors: dict[str, tuple[int, int, int]] = {}
    for side, values in visible_edge_colors.items():
        if values:
            line_colors[side] = tuple(
                int(round(statistics.median(color_value[channel] for color_value in values)))
                for channel in range(3)
            )
        else:
            line_colors[side] = fallback_line

    visible_reference = Image.open(VISIBLE_REFERENCE_PATH).convert("RGBA")
    material = visible_reference.copy()
    generated_colors: list[tuple[int, int, int]] = []
    for point in h_points:
        s, q = local(point)
        depth = max(0.0, visible_s_min - s)
        q_norm = q / half_width
        base_feature = feature(point, True)
        shadow_weight = math.exp(-depth / 7.5)
        tangent_variation = (
            0.9 * q_norm
            + 0.7 * (q_norm**3 - 0.3 * q_norm)
            + 0.45 * (depth / 24.0) * (1.0 - min(1.0, depth / 24.0))
        )
        rgb_values = []
        for channel in range(3):
            value = predict(coefficients[channel], base_feature)
            value += shadow_delta[channel] * shadow_weight
            value += (0.20 if channel == 0 else 0.15) * depth
            value += tangent_variation * (1.2 if channel == 0 else 0.8)
            rgb_values.append(clamp_channel(value))
        rgb = tuple(rgb_values)

        side = "negative" if q < 0 else "positive"
        if point in boundary:
            weight = 0.78
        elif point in inner_boundary:
            weight = 0.34
        else:
            weight = 0.0
        if weight:
            line = line_colors[side]
            rgb = tuple(
                clamp_channel((1.0 - weight) * value + weight * line[channel])
                for channel, value in enumerate(rgb)
            )
        material.putpixel(point, (*rgb, 255))
        generated_colors.append(rgb)

    metadata = {
        "method": (
            "local upper-arm coordinates; fitted longitudinal/transverse skin plane; "
            "sleeve-shadow residual decays shoulderward; source-derived side-line "
            "medians continue material boundary tangents"
        ),
        "trainingPixelCount": len(training),
        "seamShadowEvidencePixelCount": len(seam_core),
        "coefficientsRgb": coefficients,
        "shadowDeltaRgb": shadow_delta,
        "visibleMinimumLongitudinalCoordinatePx": visible_s_min,
        "lineColorsRgb": line_colors,
        "trueMaterialBoundaryPixelCount": len(boundary),
        "innerBoundaryPixelCount": len(inner_boundary),
        "generatedPixelCount": len(generated_colors),
        "uniqueGeneratedRgbCount": len(set(generated_colors)),
        "generatedRgbRange": {
            "minimum": [min(rgb[channel] for rgb in generated_colors) for channel in range(3)],
            "maximum": [max(rgb[channel] for rgb in generated_colors) for channel in range(3)],
        },
        "prohibitions": {
            "averageColorFill": False,
            "mirror": False,
            "radialFill": False,
            "repeatedClone": False,
            "externalGeneration": False,
            "sourceUpload": False,
        },
    }
    return material, metadata


def build_safe_sleeve_context(
    color: Image.Image,
    full_sleeve_mask: Image.Image,
    mixed_band: Image.Image,
    seam_responsibility: Image.Image,
    visible: Image.Image,
    shoulder: tuple[float, float],
    elbow: tuple[float, float],
    half_width: float,
) -> tuple[Image.Image, Image.Image, dict[str, object]]:
    _, _, _, local = local_frame(shoulder, elbow)
    visible_s_min = min(local(point)[0] for point in points(visible))
    s_min = visible_s_min - 34.0
    s_max = visible_s_min + 8.0
    q_limit = half_width + 1.5

    safe = Image.new("L", CANVAS, 0)
    rejected = Image.new("L", CANVAS, 0)
    local_geometry_count = 0
    mandatory_count = 0
    fabric_like_count = 0
    accepted_dark_nonmandatory = 0
    for point in points(full_sleeve_mask):
        s, q = local(point)
        if not (s_min <= s <= s_max and abs(q) <= q_limit):
            continue
        local_geometry_count += 1
        red, green, blue = color.getpixel(point)
        brightness = (red + green + blue) / 3.0
        spread = max(red, green, blue) - min(red, green, blue)
        fabric_like = (
            brightness >= 185.0
            and abs(red - green) <= 9
            and -2 <= green - blue <= 18
            and spread <= 28
        )
        mandatory = bool(
            mixed_band.getpixel(point)
            or seam_responsibility.getpixel(point)
        )
        if fabric_like or mandatory:
            safe.putpixel(point, 255)
            fabric_like_count += int(fabric_like)
            mandatory_count += int(mandatory)
            if brightness < 120.0 and not mandatory:
                accepted_dark_nonmandatory += 1
        else:
            rejected.putpixel(point, 255)

    remaining = set(points(safe))
    components: list[set[tuple[int, int]]] = []
    while remaining:
        seed = remaining.pop()
        component = {seed}
        stack = [seed]
        while stack:
            x, y = stack.pop()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(component)
    kept_component = max(
        components,
        key=lambda component: (
            sum(seam_responsibility.getpixel(point) > 0 for point in component),
            len(component),
        ),
    )
    discarded_component_pixels = 0
    for component in components:
        if component is kept_component:
            continue
        for point in component:
            safe.putpixel(point, 0)
            rejected.putpixel(point, 255)
            discarded_component_pixels += 1

    metadata = {
        "status": "engineering_candidate_pending_user_visual_approval",
        "purpose": "local sleeve-hem seam QA context only",
        "notACompleteSleeveMaterial": True,
        "localLongitudinalRangePx": [s_min, s_max],
        "localTransverseRangePx": [-q_limit, q_limit],
        "localGeometryPixelCount": local_geometry_count,
        "safePixelCount": len(points(safe)),
        "rejectedSourcePixelCount": len(points(rejected)),
        "fabricLikeAcceptedPixelCount": fabric_like_count,
        "approvedMixedOrResponsibilityPixelCount": mandatory_count,
        "acceptedDarkNonmandatoryPixelCount": accepted_dark_nonmandatory,
        "connectedComponentCountBeforeFiltering": len(components),
        "discardedDisconnectedPixelCount": discarded_component_pixels,
        "selection": {
            "minimumBrightness": 185.0,
            "maximumAbsRedMinusGreen": 9,
            "greenMinusBlueRange": [-2, 18],
            "maximumChannelSpread": 28,
            "mandatoryExceptions": [
                "approved sleeve-hem mixed band",
                "approved seam responsibility set",
            ],
        },
        "invalidatedPredecessor": (
            "audit/REJECTED-FULL-SLEEVE-SOURCE-CONTEXT-2026-07-25.md"
        ),
    }
    return safe, rejected, metadata


def union_alpha(first: Image.Image, second: Image.Image) -> Image.Image:
    result = Image.new("L", first.size, 0)
    first_pixels = first.load()
    second_pixels = second.load()
    output = result.load()
    for y in range(first.height):
        for x in range(first.width):
            a = first_pixels[x, y]
            b = second_pixels[x, y]
            output[x, y] = 255 - ((255 - a) * (255 - b) // 255)
    return result


def make_frame(
    arm: Image.Image,
    sleeve: Image.Image | None,
    angle: float,
    shoulder: tuple[float, float],
    crop: tuple[int, int, int, int],
    scale: int,
    title: str,
) -> Image.Image:
    arm_transformed = transform_rgba(arm, angle, shoulder)
    composite = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    composite.alpha_composite(arm_transformed)
    if sleeve is not None:
        composite.alpha_composite(transform_rgba(sleeve, angle, shoulder))
    panel = checker_composite(composite, crop, scale)
    header = 36
    frame = Image.new("RGB", (panel.width, panel.height + header), (240, 240, 240))
    ImageDraw.Draw(frame).text((7, 5), title, font=font(16), fill=(25, 25, 25))
    frame.paste(panel, (0, header))
    return frame


def save_gif(frames: list[Image.Image], path: Path, duration: int) -> None:
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )


def main() -> None:
    visual_rejected = FINAL_VISUAL_REJECTION_PATH.exists()
    approval = json.loads(OWNERSHIP_APPROVAL_PATH.read_text(encoding="utf-8"))
    coverage = json.loads(COVERAGE_AUDIT_PATH.read_text(encoding="utf-8"))
    if approval.get("status") != "approved":
        raise SystemExit("Ownership gate is not approved.")
    if coverage.get("status") != "pass":
        raise SystemExit("Hidden ROI or coverage proof has not passed.")

    MATERIALS_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    color = Image.open(COLOR_PATH).convert("RGB")
    visible = alpha(VISIBLE_MASK_PATH)
    h_test = alpha(H_TEST_MASK_PATH)
    sleeve_mask = alpha(SLEEVE_MASK_PATH)
    mixed_band = alpha(MIXED_BAND_PATH)
    seam_responsibility = alpha(SEAM_RESPONSIBILITY_PATH)
    visible_reference = Image.open(VISIBLE_REFERENCE_PATH).convert("RGBA")

    with zipfile.ZipFile(V4_ZIP_PATH) as archive:
        skeleton = json.loads(archive.read("skeleton.json"))
        samples = json.loads(archive.read("samples/fk-41-samples.json"))
        upper_material = Image.open(
            io.BytesIO(archive.read("materials/solid/upper_arm.png"))
        ).convert("RGBA").getchannel("A")

    shoulder = (
        float(skeleton["landmarks"]["shoulder"]["x"]),
        float(skeleton["landmarks"]["shoulder"]["y"]),
    )
    elbow = (
        float(skeleton["landmarks"]["elbow"]["x"]),
        float(skeleton["landmarks"]["elbow"]["y"]),
    )
    half_width = float(skeleton["localHalfWidthsPx"]["upper_arm"]["underSleeve"])
    material, texture_metadata = build_texture(
        color,
        visible,
        h_test,
        upper_material,
        shoulder,
        elbow,
        half_width,
    )
    material.save(MATERIAL_PATH)

    safe_sleeve_mask, rejected_sleeve_pixels, safe_sleeve_metadata = (
        build_safe_sleeve_context(
            color,
            sleeve_mask,
            mixed_band,
            seam_responsibility,
            visible,
            shoulder,
            elbow,
            half_width,
        )
    )
    alpha_png(safe_sleeve_mask).save(SAFE_SLEEVE_MASK_PATH)
    alpha_png(rejected_sleeve_pixels).save(REJECTED_SLEEVE_PIXELS_PATH)
    SAFE_SLEEVE_AUDIT_PATH.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "auditDate": date.today().isoformat(),
                **safe_sleeve_metadata,
                "checks": {
                    "safeContextIsSubsetOfApprovedOccluder": all(
                        sleeve_mask.getpixel(point)
                        for point in points(safe_sleeve_mask)
                    ),
                    "safeAndRejectedAreDisjoint": not any(
                        rejected_sleeve_pixels.getpixel(point)
                        for point in points(safe_sleeve_mask)
                    ),
                    "noDarkNonmandatoryPixelsAccepted": (
                        safe_sleeve_metadata["acceptedDarkNonmandatoryPixelCount"] == 0
                    ),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    sleeve_context = color.convert("RGBA")
    sleeve_context.putalpha(safe_sleeve_mask)

    add_header(
        checker_composite(sleeve_context, MAX_CROP, 6),
        "袖口接缝 QA 安全上下文",
        "只含局部袖口织物与已批准混合带；不是完整袖子材料",
    ).save(SAFE_SLEEVE_CHECKER_PATH)
    purity_crop = (320, 350, 382, 410)
    purity_base = color.crop(purity_crop).resize(
        (
            (purity_crop[2] - purity_crop[0]) * 6,
            (purity_crop[3] - purity_crop[1]) * 6,
        ),
        Image.Resampling.NEAREST,
    )
    safe_crop = safe_sleeve_mask.crop(purity_crop).resize(
        purity_base.size,
        Image.Resampling.NEAREST,
    )
    rejected_crop = rejected_sleeve_pixels.crop(purity_crop).resize(
        purity_base.size,
        Image.Resampling.NEAREST,
    )
    purity_overlay = purity_base.convert("RGBA")
    purity_overlay.alpha_composite(
        Image.composite(
            Image.new("RGBA", purity_base.size, (0, 210, 140, 150)),
            Image.new("RGBA", purity_base.size, (0, 0, 0, 0)),
            safe_crop,
        )
    )
    purity_overlay.alpha_composite(
        Image.composite(
            Image.new("RGBA", purity_base.size, (245, 45, 60, 190)),
            Image.new("RGBA", purity_base.size, (0, 0, 0, 0)),
            rejected_crop,
        )
    )
    add_header(
        purity_overlay,
        "袖口 QA 上下文语义纯度审查 600%",
        "绿=随袖口移动的安全像素，红=从移动上下文剔除的非织物源像素",
    ).save(SAFE_SLEEVE_REVIEW_PATH)

    union_mask = ImageChops.lighter(visible, h_test)
    union_bbox = union_mask.getbbox()
    if union_bbox is None:
        raise RuntimeError("Textured material is empty.")

    checker_crop = (
        max(0, union_bbox[0] - 12),
        max(0, union_bbox[1] - 12),
        min(CANVAS[0], union_bbox[2] + 12),
        min(CANVAS[1], union_bbox[3] + 12),
    )
    add_header(
        checker_composite(material, checker_crop, 8),
        "上臂袖下测试层棋盘格 800%",
        "仅 V_upper_arm + H_test；更深肩侧、肘部与前臂根部未制作",
    ).save(CHECKER_PATH)

    default_local = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    default_local.alpha_composite(material)
    default_local.alpha_composite(sleeve_context)
    default_eval_mask = ImageChops.lighter(safe_sleeve_mask, visible)
    default_full = color.convert("RGBA")
    default_full.paste(default_local, (0, 0), default_eval_mask)
    default_full.convert("RGB").save(DEFAULT_PATH)

    sleeve_away = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    sleeve_away.alpha_composite(material)
    sleeve_away.alpha_composite(translate_rgba(sleeve_context, 48, -16))
    add_header(
        checker_composite(sleeve_away, LOCAL_CROP, 3),
        "袖子移开诊断图",
        "袖子仅作 +48,-16 px 诊断位移；不是批准动作或 Cubism 参数",
    ).save(SLEEVE_AWAY_PATH)

    add_header(
        checker_composite(material, MAX_CROP, 1),
        "最大暴露 100%",
        "冻结参数无相对露出变化；此图隐藏袖子以审查完整 H_test",
        min_width=360,
    ).save(MAX_100_PATH)
    add_header(
        checker_composite(material, MAX_CROP, 2),
        "最大暴露 200%",
        "冻结参数无相对露出变化；此图隐藏袖子以审查完整 H_test",
        min_width=360,
    ).save(MAX_200_PATH)

    rest_theta = float(skeleton["restAnglesDeg"]["theta1"])
    fk_frames = []
    scan_frames = []
    edge_frames = []
    alpha_results = []
    default_render_0 = None
    default_render_40 = None
    for sample in samples["samples"]:
        delta = float(sample["theta1"]) - rest_theta
        label = f"样本 {sample['index']:02d}/40  θ1={sample['theta1']:.3f}°"
        fk_frames.append(
            make_frame(material, sleeve_context, delta, shoulder, LOCAL_CROP, 2, label)
        )
        scan_frames.append(
            make_frame(material, None, delta, shoulder, LOCAL_CROP, 2, label + "（袖子隐藏）")
        )

        arm_alpha = transform_mask(material.getchannel("A"), delta, shoulder)
        sleeve_alpha = transform_mask(sleeve_mask, delta, shoulder)
        responsibility_alpha = transform_mask(seam_responsibility, delta, shoulder)
        composite_alpha = union_alpha(arm_alpha, sleeve_alpha)
        responsibility_points = [
            point for point in points(responsibility_alpha)
            if responsibility_alpha.getpixel(point) >= 128
        ]
        missing = [
            point for point in responsibility_points
            if composite_alpha.getpixel(point) < TRANSPARENT_GAP_ALPHA_THRESHOLD
        ]
        soft_coverage = [
            point for point in responsibility_points
            if (
                TRANSPARENT_GAP_ALPHA_THRESHOLD
                <= composite_alpha.getpixel(point)
                < SOFT_COVERAGE_ALPHA_THRESHOLD
            )
        ]
        minimum_alpha = min(
            (composite_alpha.getpixel(point) for point in responsibility_points),
            default=255,
        )
        transformed_h_test = transform_mask(h_test, delta, shoulder)
        exposed_h_test_alpha = 0
        exposed_h_test_soft_pixels = 0
        exposed_h_test_strong_pixels = 0
        for point in points(transformed_h_test):
            value = transformed_h_test.getpixel(point) * (
                255 - sleeve_alpha.getpixel(point)
            ) // 255
            exposed_h_test_alpha = max(exposed_h_test_alpha, value)
            if value >= TRANSPARENT_GAP_ALPHA_THRESHOLD:
                exposed_h_test_soft_pixels += 1
            if value >= STRONG_EXPOSURE_ALPHA_THRESHOLD:
                exposed_h_test_strong_pixels += 1
        alpha_results.append(
            {
                "index": sample["index"],
                "theta1": sample["theta1"],
                "theta2": sample["theta2"],
                "phiWristLocal": sample["phiWristLocal"],
                "responsibilityPixelCount": len(responsibility_points),
                "missingCoveragePixelCount": len(missing),
                "softCoveragePixelCount": len(soft_coverage),
                "minimumCompositeAlpha": minimum_alpha,
                "exposedHTestSoftFringePixelCountAtAlpha16": exposed_h_test_soft_pixels,
                "exposedHTestStrongPixelCountAtAlpha128": exposed_h_test_strong_pixels,
                "maximumExposedHTestAlpha": exposed_h_test_alpha,
            }
        )

        composite = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        composite.alpha_composite(transform_rgba(material, delta, shoulder))
        composite.alpha_composite(transform_rgba(sleeve_context, delta, shoulder))
        if sample["index"] == 0:
            default_render_0 = composite.copy()
        if sample["index"] == 40:
            default_render_40 = composite.copy()
        edge_crop = composite.crop(LOCAL_CROP).convert("RGB").filter(ImageFilter.FIND_EDGES)
        edge_crop = edge_crop.resize(
            (edge_crop.width * 2, edge_crop.height * 2),
            Image.Resampling.NEAREST,
        )
        edge_frames.append(
            add_header(edge_crop, label, "边缘增强；观察袖口接缝爬动与闪烁")
        )

    save_gif(fk_frames, FK_41_PATH, 140)
    save_gif(scan_frames, SCAN_PATH, 140)
    save_gif(edge_frames, FLICKER_PATH, 140)

    extremes = (
        skeleton["requiredCombinationExtremes"]
        + skeleton["requiredWristExtremes"]
    )
    extreme_panels = []
    extreme_alpha = []
    for index, extreme in enumerate(extremes):
        theta1 = float(extreme["theta1"])
        delta = theta1 - rest_theta
        theta2 = float(extreme["theta2"])
        wrist = float(extreme.get("phiWristLocal", skeleton["restAnglesDeg"]["phiWristLocal"]))
        panel = make_frame(
            material,
            sleeve_context,
            delta,
            shoulder,
            LOCAL_CROP,
            2,
            f"极{index+1}  θ1/θ2/腕={theta1:.2f}/{theta2:.2f}/{wrist:.2f}",
        )
        extreme_panels.append(panel)
        arm_alpha = transform_mask(material.getchannel("A"), delta, shoulder)
        sleeve_alpha = transform_mask(sleeve_mask, delta, shoulder)
        responsibility_alpha = transform_mask(seam_responsibility, delta, shoulder)
        composite_alpha = union_alpha(arm_alpha, sleeve_alpha)
        critical = [
            point for point in points(responsibility_alpha)
            if responsibility_alpha.getpixel(point) >= 128
        ]
        extreme_alpha.append(
            {
                "index": index + 1,
                "theta1": theta1,
                "theta2": theta2,
                "phiWristLocal": wrist,
                "missingCoveragePixelCount": sum(
                    composite_alpha.getpixel(point) < TRANSPARENT_GAP_ALPHA_THRESHOLD
                    for point in critical
                ),
                "softCoveragePixelCount": sum(
                    (
                        TRANSPARENT_GAP_ALPHA_THRESHOLD
                        <= composite_alpha.getpixel(point)
                        < SOFT_COVERAGE_ALPHA_THRESHOLD
                    )
                    for point in critical
                ),
                "minimumCompositeAlpha": min(
                    (composite_alpha.getpixel(point) for point in critical),
                    default=255,
                ),
            }
        )
    gap = 18
    columns = 2
    rows = 3
    panel_w = max(panel.width for panel in extreme_panels)
    panel_h = max(panel.height for panel in extreme_panels)
    sheet = Image.new(
        "RGB",
        (columns * panel_w + (columns + 1) * gap, rows * panel_h + (rows + 1) * gap),
        (230, 230, 230),
    )
    for index, panel in enumerate(extreme_panels):
        x = gap + (index % columns) * (panel_w + gap)
        y = gap + (index // columns) * (panel_h + gap)
        sheet.paste(panel, (x, y))
    sheet.save(EXTREMES_PATH)

    epsilon_values = [
        rest_theta - EPSILON_DEG,
        rest_theta,
        rest_theta + EPSILON_DEG,
        rest_theta,
        rest_theta - EPSILON_DEG,
    ]
    epsilon_frames = [
        make_frame(
            material,
            sleeve_context,
            value - rest_theta,
            shoulder,
            MAX_CROP,
            6,
            f"θ1={value:.4f}°  ε={EPSILON_DEG:.2f}°；无相对露出临界点",
        )
        for value in epsilon_values
    ]
    save_gif(epsilon_frames, EPSILON_PATH, 420)

    raw_max_crop = material.crop(MAX_CROP)
    raw_max_scaled = raw_max_crop.resize(
        (raw_max_crop.width * 4, raw_max_crop.height * 4),
        Image.Resampling.NEAREST,
    )
    neutral_max = Image.new("RGB", raw_max_scaled.size, (235, 235, 235))
    neutral_max.paste(
        raw_max_scaled,
        (0, 0),
        raw_max_scaled.getchannel("A"),
    )
    grayscale = ImageOps.grayscale(neutral_max).convert("RGB")
    add_header(
        grayscale,
        "最大暴露灰度检查",
        "检查亮度渐变、袖口阴影衰减和硬色块",
    ).save(GRAYSCALE_PATH)
    edge = ImageOps.grayscale(neutral_max).filter(ImageFilter.FIND_EDGES)
    edge = ImageOps.autocontrast(edge).convert("RGB")
    add_header(
        edge,
        "最大暴露边缘增强检查",
        "检查断线、硬接缝、重复纹理和轮廓切线",
    ).save(EDGE_PATH)

    if default_render_0 is None or default_render_40 is None:
        raise RuntimeError("Missing deterministic return frames.")
    return_difference = ImageChops.difference(
        default_render_0,
        default_render_40,
    ).getbbox()

    material_pixels = material.load()
    color_pixels = color.load()
    visible_rgb_differences = 0
    visible_max_difference = 0
    for point in points(visible):
        material_rgb = material_pixels[point][:3]
        source_rgb = color_pixels[point]
        difference = max(
            abs(material_rgb[channel] - source_rgb[channel])
            for channel in range(3)
        )
        visible_max_difference = max(visible_max_difference, difference)
        if difference:
            visible_rgb_differences += 1

    scope_differences = 0
    scope_max_difference = 0
    reference_pixels = visible_reference.load()
    h_test_set = set(points(h_test))
    for y in range(CANVAS[1]):
        for x in range(CANVAS[0]):
            if (x, y) in h_test_set:
                continue
            current = material_pixels[x, y]
            reference = reference_pixels[x, y]
            difference = max(
                abs(current[channel] - reference[channel])
                for channel in range(4)
            )
            scope_max_difference = max(scope_max_difference, difference)
            if difference:
                scope_differences += 1

    output_alpha = material.getchannel("A")
    alpha_outside_union = sum(
        1
        for point in points(output_alpha)
        if not union_mask.getpixel(point)
    )
    h_test_not_opaque = sum(
        output_alpha.getpixel(point) != 255 for point in points(h_test)
    )

    default_composite_differences = 0
    for point in points(default_eval_mask):
        if default_local.getpixel(point)[:3] != color.getpixel(point):
            default_composite_differences += 1

    pixel_checks = {
        "visibleRgbPixelDifferenceCount": visible_rgb_differences,
        "visibleMaximumRgbChannelDifference": visible_max_difference,
        "visiblePixelExact": visible_rgb_differences == 0,
        "outsideHTestRgbaDifferenceCount": scope_differences,
        "outsideHTestMaximumChannelDifference": scope_max_difference,
        "outsideHTestZeroModification": scope_differences == 0,
        "alphaPixelsOutsideVisibleUnionHTest": alpha_outside_union,
        "hTestNonOpaquePixels": h_test_not_opaque,
        "defaultLocalCompositeDifferenceCount": default_composite_differences,
        "defaultRecompositionPreservesSource": default_composite_differences == 0,
    }
    PIXEL_AUDIT_PATH.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "auditDate": date.today().isoformat(),
                "status": "pass" if all(
                    (
                        pixel_checks["visiblePixelExact"],
                        pixel_checks["outsideHTestZeroModification"],
                        alpha_outside_union == 0,
                        h_test_not_opaque == 0,
                        pixel_checks["defaultRecompositionPreservesSource"],
                    )
                ) else "fail_stop",
                "checks": pixel_checks,
                "limitations": (
                    "Default recomposition uses authoritative RGB outside the local "
                    "evaluation mask and the semantic-purity-filtered sleeve-hem QA "
                    "strip inside it; complete sleeve separation is out of scope."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    max_missing = max(
        result["missingCoveragePixelCount"] for result in alpha_results
    )
    max_extreme_missing = max(
        result["missingCoveragePixelCount"] for result in extreme_alpha
    )
    minimum_alpha = min(
        result["minimumCompositeAlpha"] for result in alpha_results
    )
    max_soft_coverage = max(
        result["softCoveragePixelCount"] for result in alpha_results
    )
    max_extreme_soft_coverage = max(
        result["softCoveragePixelCount"] for result in extreme_alpha
    )
    max_exposed_h_test_soft = max(
        result["exposedHTestSoftFringePixelCountAtAlpha16"] for result in alpha_results
    )
    max_exposed_h_test_strong = max(
        result["exposedHTestStrongPixelCountAtAlpha128"] for result in alpha_results
    )
    alpha_checks = {
        "maximumMissingCoveragePixels41": max_missing,
        "maximumMissingCoveragePixelsSixExtremes": max_extreme_missing,
        "maximumSoftCoveragePixels41": max_soft_coverage,
        "maximumSoftCoveragePixelsSixExtremes": max_extreme_soft_coverage,
        "minimumCompositeAlphaOnResponsibilitySet": minimum_alpha,
        "maximumHTestSoftFringePixelsAtAlpha16": max_exposed_h_test_soft,
        "maximumUnexpectedHTestStrongExposurePixelsAtAlpha128": max_exposed_h_test_strong,
        "transparentGapAlphaThreshold": TRANSPARENT_GAP_ALPHA_THRESHOLD,
        "softCoverageAlphaThreshold": SOFT_COVERAGE_ALPHA_THRESHOLD,
        "strongExposureAlphaThreshold": STRONG_EXPOSURE_ALPHA_THRESHOLD,
        "predeclaredSoftResponsibilityPixelLimit": MAX_SOFT_RESPONSIBILITY_PIXELS,
        "deterministicReturnPixelExact": return_difference is None,
        "criticalExposureParameterExists": False,
        "epsilonDiagnosticDeg": EPSILON_DEG,
        "epsilonPurpose": (
            "No relative exposure onset exists under the frozen shared transform; "
            "the ±epsilon animation checks local raster stability around rest."
        ),
    }
    alpha_passed = (
        max_missing == 0
        and max_extreme_missing == 0
        and max_soft_coverage <= MAX_SOFT_RESPONSIBILITY_PIXELS
        and max_extreme_soft_coverage <= MAX_SOFT_RESPONSIBILITY_PIXELS
        and max_exposed_h_test_strong == 0
        and minimum_alpha >= STRONG_EXPOSURE_ALPHA_THRESHOLD
        and return_difference is None
    )
    ALPHA_AUDIT_PATH.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "auditDate": date.today().isoformat(),
                "status": (
                    "numeric_pass_visual_fail_stop"
                    if alpha_passed and visual_rejected
                    else ("pass" if alpha_passed else "fail_stop")
                ),
                "visualValidity": (
                    "invalidated_by_disconnected_cropped_material"
                    if visual_rejected
                    else "pending_user_chinese_review"
                ),
                "realTextureRgba": "materials/textured/upper-arm-sleeve-hidden-test.png",
                "geometricSleeveOccluderAlpha": (
                    "masks/sleeve-hem-occluder-alpha-locked.png"
                ),
                "visualSleeveContext": "masks/sleeve-hem-qa-context-safe.png",
                "visualSleeveContextBoundary": (
                    "Local seam QA strip only; not a complete sleeve material."
                ),
                "primarySamples": alpha_results,
                "combinationExtremes": extreme_alpha,
                "checks": alpha_checks,
                "continuousDomainBasis": (
                    "Sleeve and upper arm share the same frozen shoulder transform; "
                    "relative texture alpha is invariant between samples."
                ),
                "limitations": [
                    "Pillow bicubic raster QA is not Cubism.",
                    "Premultiplied-alpha, atlas, UV padding and mipmap checks remain future gates.",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    TEXTURE_AUDIT_PATH.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "auditDate": date.today().isoformat(),
                "status": (
                    "user_visual_rejected_fail_stop"
                    if visual_rejected
                    else "engineering_pass_pending_user_visual_approval"
                ),
                "scope": "sleeve-proximal hidden upper-arm texture method test only",
                "texture": texture_metadata,
                "pixelIdentityAudit": "audit/textured-pixel-identity-and-scope.json",
                "alphaAudit": "audit/textured-alpha-and-flicker.json",
                "sleeveQaContextAudit": "audit/sleeve-hem-qa-context-purity.json",
                "invalidatedVisualQa": [
                    "audit/REJECTED-FULL-SLEEVE-SOURCE-CONTEXT-2026-07-25.md",
                    (
                        "audit/"
                        "REJECTED-STAGE-B-HIDDEN-TEXTURE-CANDIDATE-2026-07-25.md"
                    ),
                ],
                "visualGate": (
                    "failed_user_chinese_review"
                    if visual_rejected
                    else "pending_user_chinese_review"
                ),
                "stopReason": (
                    "Upper-arm and sleeve QA materials are disconnected, cropped "
                    "fragments rather than complete independently moving materials."
                    if visual_rejected
                    else None
                ),
                "requiredSupport": (
                    [
                        "original layered complete sleeve art",
                        (
                            "or explicit authorization for a new Stage A revision "
                            "with controlled reconstruction of the complete sleeve "
                            "and full under-sleeve upper-arm material"
                        ),
                    ]
                    if visual_rejected
                    else []
                ),
                "doesNotClaim": [
                    "complete upper-arm material",
                    "elbow hidden texture",
                    "forearm-root texture",
                    "pose-dependent elbow folds",
                    "Cubism",
                    "PSD",
                    "Physics",
                    "Runtime",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    overall_engineering_pass = (
        json.loads(PIXEL_AUDIT_PATH.read_text(encoding="utf-8"))["status"] == "pass"
        and alpha_passed
    )
    STAGE_REPORT_PATH.write_text(
        f"""# 小星单臂：阶段 B 中文报告

## 结论

**{'用户视觉否决，阶段 B 失败并停止' if visual_rejected else ('工程检查通过，等待用户中文视觉批准' if overall_engineering_pass else '工程检查失败并停止')}。**

本轮产物只能称为“袖下近端上臂纹理方法验证”，不能称为完整上臂材料。

## 已完成范围

- 已批准 `V_upper_arm` 与袖口混合带所有权。
- `H_total` 与 `H_test` 已分离；本轮 `H_test` 为 `{len(points(h_test))}` 像素。
- `w_required=5 px`，`w_final=12 px`，冻结材料最小连续承载 `16.75 px`。
- 只在 `H_test` 内生成纹理；可见像素逐像素不变，`H_test` 外零改动。
- 纹理使用上臂局部坐标中的纵向/横向渐变、袖口阴影衰减和原稿侧边线色延续。
- 未使用平均色块、镜像、径向纹理、重复克隆、外部生成服务或素材上传。
- 用户指出旧运动预览把头发、衣身等非袖子源像素烘焙进袖子裁片；该视觉 QA 已正式作废。
- 新预览只使用语义纯度过滤后的局部袖口 QA 条带；它不是完整袖子材料。

## 工程结果

- 可见 RGB 差异像素：`{visible_rgb_differences}`
- `H_test` 外 RGBA 差异像素：`{scope_differences}`
- 默认局部回组差异像素：`{default_composite_differences}`
- 41 样本最大接缝缺失像素：`{max_missing}`
- 6 个组合极值最大接缝缺失像素：`{max_extreme_missing}`
- 41 样本责任集最大软边像素：`{max_soft_coverage}`（预先容差上限 `{MAX_SOFT_RESPONSIBILITY_PIXELS}`）
- 责任集最低合成 alpha：`{minimum_alpha}`（低于 `{TRANSPARENT_GAP_ALPHA_THRESHOLD}` 才计透明缺口）
- `H_test` 意外强露出像素（alpha≥{STRONG_EXPOSURE_ALPHA_THRESHOLD}）：`{max_exposed_h_test_strong}`
- 0→1→0 返回是否逐像素一致：`{'是' if return_difference is None else '否'}`

冻结参数中袖子和上臂相对变换恒定，因此不存在“新露出临界参数”。`±{EPSILON_DEG:.2f}°` 动画用于检查休止点附近的栅格稳定性，不代表新增动作参数。

## 视觉证据状态

用户已确认上臂候选断开、袖子上下文断开且呈裁剪状。以下文件仅保留为失败复盘证据，不得用于宣称视觉通过。

1. `qa/upper-arm-sleeve-hidden-test-checkerboard.png`
2. `qa/sleeve-moved-away.png`
3. `qa/maximum-exposure-100.png`
4. `qa/maximum-exposure-200.png`
5. `qa/maximum-exposure-single-parameter-scan.gif`
6. `qa/fk-41-textured-alpha-slow-preview.gif`
7. `qa/six-combination-extremes.png`
8. `qa/critical-epsilon-no-exposure.gif`
9. `qa/maximum-exposure-grayscale.png`
10. `qa/maximum-exposure-edge-enhanced.png`
11. `qa/seam-flicker-edge-preview.gif`
12. `qa/sleeve-hem-qa-context-safe-checkerboard.png`
13. `qa/sleeve-hem-qa-context-purity-review.png`

## 明确未完成

- 更深肩侧隐藏纹理；
- 肘部 joint disk、前臂根部和姿势相关肘褶；
- 正式 PSD；
- Cubism ArtMesh、Deformer、参数、Physics 或 Runtime；
- premultiplied alpha、atlas、UV padding 和 mipmap 验证。

## 当前门禁

{'视觉门禁失败并停止。继续需要原画提供完整独立袖子分层，或明确授权建立新的 Stage A 修订，对完整袖子隐藏区与完整袖下上臂材料进行本地受控补画并重新审批。' if visual_rejected else '需要用户用中文视觉确认：小暴露与最大暴露下的肤色、阴影衰减、轮廓线延续、无色块/硬接缝，以及慢速扫描中无不可接受脏边、爬动或闪烁。'}
""",
        encoding="utf-8",
    )
    if not overall_engineering_pass:
        raise SystemExit("Textured Stage B engineering QA failed.")
    print(
        (
            "STOP: numeric QA passed but user visual review rejected the "
            "disconnected/cropped material candidate"
        )
        if visual_rejected
        else (
            "PASS: textured H_test engineering QA; "
            "status=engineering_pass_pending_user_visual_approval"
        )
    )


if __name__ == "__main__":
    main()
