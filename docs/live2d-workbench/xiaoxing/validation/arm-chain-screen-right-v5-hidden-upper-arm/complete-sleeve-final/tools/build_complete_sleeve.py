from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import date
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


HERE = Path(__file__).resolve()
REVISION = HERE.parents[1]
XIAOXING_ROOT = HERE.parents[4]

CANVAS = (512, 1086)
INPUTS = REVISION / "inputs"
MATERIALS = REVISION / "materials"
MASKS = REVISION / "masks"
QA = REVISION / "qa"
AUDIT = REVISION / "audit"

COLOR_PATH = (
    XIAOXING_ROOT / "source" / "masters" / "front-color-source-exact-after-reset.png"
)
R3_MATERIAL_PATH = INPUTS / "sleeve-visible-base-r3.png"
R3_GEOMETRY_PATH = INPUTS / "sleeve-visible-base-geometry-r3.png"
TRUSTED_PATH = INPUTS / "sleeve-source-trusted-r3.png"
R9_GEOMETRY_PATH = INPUTS / "sleeve-complete-geometry-r9.png"
R9_APPROVAL_PATH = AUDIT / "user-visual-approval-geometry-2026-07-25.json"

MATERIAL_PATH = MATERIALS / "sleeve-complete-textured-r1.png"
HIDDEN_MASK_PATH = MASKS / "sleeve-new-hidden-texture-region-r1.png"
SEAM_BAND_PATH = MASKS / "sleeve-internal-seam-repair-band-r1.png"
PROVENANCE_PATH = MASKS / "sleeve-texture-provenance-r1.png"
ISOLATED_GATE_PATH = QA / "gate-1-complete-textured-sleeve-isolated.png"
SEAM_GATE_PATH = QA / "gate-2-hidden-texture-seam-closeup.png"
DISPLACED_GATE_PATH = QA / "gate-3-complete-textured-sleeve-displaced.png"
AUDIT_PATH = AUDIT / "complete-sleeve-texture-r1.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for pivot in range(size):
        best = max(range(pivot, size), key=lambda row: abs(augmented[row][pivot]))
        augmented[pivot], augmented[best] = augmented[best], augmented[pivot]
        value = augmented[pivot][pivot]
        if abs(value) < 1e-9:
            raise RuntimeError("Sleeve texture fit is singular.")
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
    return solve_linear(matrix, vector)


def predict(coefficients: list[float], feature: list[float]) -> float:
    return sum(value * item for value, item in zip(coefficients, feature))


def component_count(mask: Image.Image) -> int:
    remaining = set(points(binary(mask)))
    components = 0
    while remaining:
        components += 1
        stack = [remaining.pop()]
        while stack:
            x, y = stack.pop()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
    return components


def alpha(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if image.size != CANVAS:
        raise RuntimeError(f"Unexpected canvas size for {path.name}: {image.size}")
    return image.getchannel("A")


def binary(mask: Image.Image, threshold: int = 8) -> Image.Image:
    return mask.point(lambda value: 255 if value > threshold else 0)


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


def clamp_channel(value: float) -> int:
    return max(0, min(255, round(value)))


def checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    image = Image.new("RGB", size, (238, 238, 238))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if ((x // cell) + (y // cell)) % 2:
                draw.rectangle(
                    (
                        x,
                        y,
                        min(x + cell - 1, size[0] - 1),
                        min(y + cell - 1, size[1] - 1),
                    ),
                    fill=(205, 205, 205),
                )
    return image


def panel(
    image: Image.Image,
    title: str,
    note: str,
    crop: tuple[int, int, int, int],
    scale: int,
    *,
    checker_background: bool = False,
    nearest: bool = False,
) -> Image.Image:
    resampling = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
    cropped = image.crop(crop).resize(
        ((crop[2] - crop[0]) * scale, (crop[3] - crop[1]) * scale),
        resampling,
    )
    if checker_background:
        content = checker(cropped.size, max(8, 10 * scale))
        content.paste(cropped, (0, 0), cropped.getchannel("A"))
    else:
        content = cropped.convert("RGB")
    result = Image.new("RGB", (content.width + 28, content.height + 86), "white")
    draw = ImageDraw.Draw(result)
    draw.text((14, 8), title, font=font(23), fill=(20, 20, 20))
    draw.text((14, 43), note, font=font(14), fill=(70, 70, 70))
    result.paste(content, (14, 78))
    return result


def row(title: str, panels: list[Image.Image]) -> Image.Image:
    gap = 20
    header = 64
    width = sum(item.width for item in panels) + gap * (len(panels) + 1)
    height = max(item.height for item in panels) + header + gap
    result = Image.new("RGB", (width, height), (240, 240, 240))
    ImageDraw.Draw(result).text(
        (gap, 13),
        title,
        font=font(30),
        fill=(20, 20, 20),
    )
    x = gap
    for item in panels:
        result.paste(item, (x, header))
        x += item.width + gap
    return result


def save_alpha(mask: Image.Image, path: Path) -> None:
    output = Image.new("RGBA", CANVAS, (255, 255, 255, 0))
    output.putalpha(mask)
    output.save(path)


def fit_cloth_plane(
    source: Image.Image,
    trusted: Image.Image,
    bbox: tuple[int, int, int, int],
) -> tuple[list[list[float]], list[tuple[int, int, int]]]:
    x0, y0, x1, y1 = bbox
    width = max(1, x1 - x0 - 1)
    height = max(1, y1 - y0 - 1)
    samples: list[tuple[list[float], tuple[int, int, int]]] = []
    colors: list[tuple[int, int, int]] = []
    for x, y in points(binary(trusted, 127)):
        red, green, blue, _ = source.getpixel((x, y))
        luminance = (red + green + blue) / 3
        chroma = max(red, green, blue) - min(red, green, blue)
        if luminance < 184 or luminance > 252 or chroma > 40:
            continue
        nx = (x - x0) / width
        ny = (y - y0) / height
        feature = [1.0, nx, ny, nx * ny, nx * nx, ny * ny]
        rgb = (red, green, blue)
        samples.append((feature, rgb))
        colors.append(rgb)
    if len(samples) < 300:
        raise RuntimeError(f"Insufficient trusted sleeve samples: {len(samples)}")
    return [fit_channel(samples, channel) for channel in range(3)], colors


def seam_discontinuity(
    material: Image.Image,
    target: Image.Image,
    stable: Image.Image,
) -> dict[str, float | int]:
    target_set = set(points(target))
    stable_set = set(points(stable))
    differences: list[int] = []
    for x, y in target_set:
        neighbors = [
            (x + dx, y + dy)
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
            if (x + dx, y + dy) in stable_set
        ]
        if not neighbors:
            continue
        rgb = material.getpixel((x, y))[:3]
        differences.append(
            min(
                max(
                    abs(rgb[channel] - material.getpixel(neighbor)[channel])
                    for channel in range(3)
                )
                for neighbor in neighbors
            )
        )
    return {
        "boundaryPairCount": len(differences),
        "maximumNearestRgbChannelDifference": max(differences, default=0),
        "meanNearestRgbChannelDifference": (
            sum(differences) / len(differences) if differences else 0.0
        ),
        "medianNearestRgbChannelDifference": (
            float(statistics.median(differences)) if differences else 0.0
        ),
    }


def main() -> None:
    for directory in (MATERIALS, MASKS, QA, AUDIT):
        directory.mkdir(parents=True, exist_ok=True)
    for path in (
        COLOR_PATH,
        R3_MATERIAL_PATH,
        R3_GEOMETRY_PATH,
        TRUSTED_PATH,
        R9_GEOMETRY_PATH,
        R9_APPROVAL_PATH,
    ):
        if not path.exists():
            raise RuntimeError(f"Missing required input: {path.name}")

    approval = json.loads(R9_APPROVAL_PATH.read_text(encoding="utf-8"))
    if approval.get("status") != "approved":
        raise SystemExit("R9 geometry is not user-approved.")
    if approval["candidate"]["geometrySha256"] != sha256(R9_GEOMETRY_PATH):
        raise SystemExit("Approved R9 geometry hash changed.")

    source = Image.open(COLOR_PATH).convert("RGBA")
    r3_material = Image.open(R3_MATERIAL_PATH).convert("RGBA")
    r3_alpha = alpha(R3_GEOMETRY_PATH)
    trusted = alpha(TRUSTED_PATH)
    r9_alpha = alpha(R9_GEOMETRY_PATH)
    if any(image.size != CANVAS for image in (source, r3_material)):
        raise RuntimeError("Material inputs must remain on the exact 512x1086 canvas.")

    r3_binary = binary(r3_alpha)
    r9_binary = binary(r9_alpha)
    trusted_binary = binary(trusted, 127)
    hidden = binary(ImageChops.subtract(r9_alpha, r3_alpha))

    # The old R3 outer edge becomes an internal join in R9. Rebuild only its
    # untrusted 8 px neighborhood so the former antialiased outline and its
    # pale halo cannot remain as a dotted dark
    # vertical seam. Exact trusted source pixels remain immutable.
    hidden_near = hidden.filter(ImageFilter.MaxFilter(17))
    untrusted = ImageChops.invert(trusted_binary)
    seam_band = ImageChops.multiply(
        ImageChops.multiply(r3_binary, hidden_near),
        untrusted,
    )
    target = ImageChops.lighter(hidden, seam_band)
    stable = ImageChops.subtract(r9_binary, target)
    target_points = points(target)
    target_set = set(target_points)
    stable_set = set(points(stable))
    hidden_set = set(points(hidden))

    bbox = r9_binary.getbbox()
    if bbox is None:
        raise RuntimeError("R9 geometry is empty.")
    coefficients, training_colors = fit_cloth_plane(source, trusted, bbox)
    channel_medians = [
        statistics.median(rgb[channel] for rgb in training_colors)
        for channel in range(3)
    ]
    channel_lowers = [value - 24 for value in channel_medians]
    channel_uppers = [value + 18 for value in channel_medians]

    x0, y0, x1, y1 = bbox
    width = max(1, x1 - x0 - 1)
    height = max(1, y1 - y0 - 1)
    row_extents: dict[int, tuple[int, int]] = {}
    for y in range(y0, y1):
        xs = [x for x in range(x0, x1) if r9_binary.getpixel((x, y))]
        if xs:
            row_extents[y] = (min(xs), max(xs))

    predicted: dict[tuple[int, int], tuple[float, float, float]] = {}
    for x, y in target_points:
        nx = (x - x0) / width
        ny = (y - y0) / height
        row_min, row_max = row_extents[y]
        row_width = max(1, row_max - row_min)
        u = (x - row_min) / row_width
        feature = [1.0, nx, ny, nx * ny, nx * nx, ny * ny]
        inner_shadow = -8.0 * max(0.0, 1.0 - u) * (0.40 + 0.60 * ny)
        shoulder_shadow = -4.0 * max(0.0, 1.0 - ny / 0.35)
        fold = 1.25 * math.sin(0.105 * x + 0.041 * y)
        micro = 0.55 * math.sin(0.73 * x + 0.39 * y)
        predicted[(x, y)] = tuple(
            max(
                channel_lowers[channel],
                min(
                    channel_uppers[channel],
                    predict(coefficients[channel], feature)
                    + inner_shadow
                    + shoulder_shadow
                    + fold
                    + micro,
                ),
            )
            for channel in range(3)
        )

    anchors: dict[tuple[int, int], tuple[float, float, float]] = {}
    for x, y in target_points:
        adjacent_stable = [
            (x + dx, y + dy)
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
            if (x + dx, y + dy) in stable_set
        ]
        if adjacent_stable:
            anchors[(x, y)] = tuple(
                sum(
                    r3_material.getpixel(neighbor)[channel]
                    for neighbor in adjacent_stable
                )
                / len(adjacent_stable)
                for channel in range(3)
            )

    values = dict(predicted)
    values.update(anchors)
    iterations = 0
    maximum_change = 0.0
    for iteration in range(650):
        next_values = dict(values)
        maximum_change = 0.0
        for point in target_points:
            if point in anchors:
                continue
            x, y = point
            neighbors: list[tuple[float, float, float]] = []
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in target_set:
                    neighbors.append(values[neighbor])
                elif neighbor in stable_set:
                    neighbors.append(
                        tuple(
                            float(r3_material.getpixel(neighbor)[channel])
                            for channel in range(3)
                        )
                    )
            if not neighbors:
                continue
            attraction = 0.045
            smoothed = tuple(
                (
                    sum(rgb[channel] for rgb in neighbors)
                    + attraction * predicted[point][channel]
                )
                / (len(neighbors) + attraction)
                for channel in range(3)
            )
            maximum_change = max(
                maximum_change,
                max(
                    abs(smoothed[channel] - values[point][channel])
                    for channel in range(3)
                ),
            )
            next_values[point] = smoothed
        values = next_values
        iterations = iteration + 1
        if maximum_change < 0.002:
            break

    material = r3_material.copy()
    for point in target_points:
        rgb = tuple(clamp_channel(value) for value in values[point])
        material.putpixel(point, (*rgb, 255))

    # Continue the two faint hem construction lines only inside the newly
    # reconstructed hidden sleeve. They are derived from the approved lower
    # boundary rather than cloned from the visible sleeve.
    bottom_by_x: dict[int, int] = {}
    for x in range(x0, x1):
        ys = [y for y in range(y0, y1) if hidden.getpixel((x, y))]
        if ys:
            bottom_by_x[x] = max(ys)
    hem_xs = [x for x in sorted(bottom_by_x) if x <= 344]
    hem_overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    hem_draw = ImageDraw.Draw(hem_overlay)
    if hem_xs:
        lower_line = [(x, bottom_by_x[x] - 5) for x in hem_xs]
        upper_line = [(x, bottom_by_x[x] - 8) for x in hem_xs]
        hem_draw.line(lower_line, fill=(150, 151, 147, 62), width=1)
        hem_draw.line(upper_line, fill=(165, 166, 162, 38), width=1)
    hem_overlay.putalpha(
        ImageChops.multiply(hem_overlay.getchannel("A"), hidden)
    )
    material.alpha_composite(hem_overlay)

    # Add the semantic outline only on the newly exposed outer boundary. The
    # former R3 boundary was deliberately removed inside seam_band.
    boundary = ImageChops.subtract(
        r9_alpha,
        r9_alpha.filter(ImageFilter.MinFilter(3)),
    )
    new_outer_boundary = ImageChops.multiply(boundary, hidden)
    boundary_rgba = Image.new("RGBA", CANVAS, (150, 151, 148, 0))
    boundary_rgba.putalpha(
        new_outer_boundary.point(lambda value: min(175, value))
    )
    material.alpha_composite(boundary_rgba)
    material.putalpha(r9_alpha)
    material.save(MATERIAL_PATH)

    save_alpha(hidden, HIDDEN_MASK_PATH)
    save_alpha(seam_band, SEAM_BAND_PATH)
    provenance = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    provenance.paste((34, 177, 96, 225), (0, 0, *CANVAS), r3_binary)
    provenance.paste((242, 142, 43, 235), (0, 0, *CANVAS), hidden)
    provenance.paste((122, 82, 196, 235), (0, 0, *CANVAS), seam_band)
    provenance.putalpha(r9_alpha)
    provenance.save(PROVENANCE_PATH)

    crop = (285, 205, 420, 420)
    isolated_gate = row(
        "纹理视觉门 1｜R9 锁定轮廓内的完整袖筒材料",
        [
            panel(
                r3_material,
                "原 R3 可见袖面",
                "仅作纹理基准；几何不完整",
                crop,
                4,
                checker_background=True,
            ),
            panel(
                material,
                "完整纹理袖筒",
                "新增内侧已补布料明暗、轮廓和袖口线",
                crop,
                4,
                checker_background=True,
            ),
            panel(
                provenance,
                "纹理来源",
                "绿=R3；橙=新增隐藏；紫=旧内边界融合带",
                crop,
                4,
                checker_background=True,
                nearest=True,
            ),
        ],
    )
    isolated_gate.save(ISOLATED_GATE_PATH)

    seam_crop = (300, 220, 365, 405)
    geometry_overlay = material.copy()
    blue = Image.new("RGBA", CANVAS, (45, 110, 235, 0))
    blue.putalpha(hidden.point(lambda value: min(155, value)))
    geometry_overlay.alpha_composite(blue)
    seam_gate = row(
        "纹理视觉门 2｜隐藏内袖与原袖面衔接",
        [
            panel(
                geometry_overlay,
                "新增区域定位",
                "蓝色仅标新增隐藏袖筒，不是成品颜色",
                seam_crop,
                5,
                checker_background=True,
                nearest=True,
            ),
            panel(
                material,
                "实际纹理衔接",
                "检查是否仍有竖向暗缝、灰块或重复克隆",
                seam_crop,
                5,
                checker_background=True,
            ),
        ],
    )
    seam_gate.save(SEAM_GATE_PATH)

    moved = ImageChops.offset(material, 48, -16)
    ImageDraw.Draw(moved).rectangle(
        (0, 0, 47, CANVAS[1] - 1),
        fill=(0, 0, 0, 0),
    )
    ImageDraw.Draw(moved).rectangle(
        (0, CANVAS[1] - 16, CANVAS[0] - 1, CANVAS[1] - 1),
        fill=(0, 0, 0, 0),
    )
    displaced_gate = row(
        "纹理视觉门 3｜完整袖筒大位移检查",
        [
            panel(
                material,
                "默认坐标孤立层",
                "检查完整材质、袖口线和隐藏内侧",
                crop,
                4,
                checker_background=True,
            ),
            panel(
                moved,
                "整体移开 +48,-16 px",
                "检查无洞、无裁断、无旧边界暗缝",
                crop,
                4,
                checker_background=True,
            ),
        ],
    )
    displaced_gate.save(DISPLACED_GATE_PATH)

    trusted_differences = 0
    outside_alpha = 0
    final_alpha = material.getchannel("A")
    for y in range(CANVAS[1]):
        for x in range(CANVAS[0]):
            if trusted_binary.getpixel((x, y)):
                if material.getpixel((x, y))[:3] != r3_material.getpixel((x, y))[:3]:
                    trusted_differences += 1
            if not r9_alpha.getpixel((x, y)) and final_alpha.getpixel((x, y)):
                outside_alpha += 1

    hidden_colors = [
        material.getpixel(point)[:3]
        for point in hidden_set
        if r9_alpha.getpixel(point) > 127
    ]
    seam_metrics = seam_discontinuity(material, target, stable)
    audit = {
        "schemaVersion": 1,
        "auditDate": date.today().isoformat(),
        "status": "user_visual_approved_complete_sleeve_texture",
        "scope": "complete screen-right sleeve texture inside user-approved R9 geometry",
        "geometryLock": {
            "approval": str(R9_APPROVAL_PATH.relative_to(REVISION)).replace("\\", "/"),
            "geometrySha256": sha256(R9_GEOMETRY_PATH),
            "alphaChanged": ImageChops.difference(final_alpha, r9_alpha).getbbox()
            is not None,
        },
        "textureMethod": {
            "description": (
                "trusted local cloth polynomial fit, exact stable-boundary anchors, "
                "constrained harmonic continuation, low-amplitude nonrepeating texture, "
                "derived hidden hem lines, and local removal of the obsolete R3 outer edge"
            ),
            "trainingPixelCount": len(training_colors),
            "anchorPixelCount": len(anchors),
            "harmonicIterations": iterations,
            "finalMaximumIterationChange": maximum_change,
            "channelMedianRgb": channel_medians,
            "planeCoefficientsRgb": coefficients,
            "prohibitions": {
                "uniformAverageFill": False,
                "radialFill": False,
                "mirroredClone": False,
                "repeatedClone": False,
                "externalGeneration": False,
                "sourceUpload": False,
            },
        },
        "counts": {
            "newHiddenMaskPixels": len(hidden_set),
            "internalSeamRepairPixels": len(points(seam_band)),
            "targetTexturePixels": len(target_points),
            "uniqueHiddenRgbCount": len(set(hidden_colors)),
            "trustedSourceRgbDifferences": trusted_differences,
            "outsideGeometryAlphaPixels": outside_alpha,
        },
        "checks": {
            "alphaMatchesLockedR9Exactly": ImageChops.difference(
                final_alpha,
                r9_alpha,
            ).getbbox()
            is None,
            "alphaConnectedComponents": component_count(final_alpha),
            "trustedSourceRgbPreserved": trusted_differences == 0,
            "newHiddenRegionFullyTextured": all(
                final_alpha.getpixel(point) > 0 for point in hidden_set
            ),
            "outsideGeometryTransparent": outside_alpha == 0,
            "hiddenTextureHasVariation": len(set(hidden_colors)) >= 100,
            "seamDiscontinuity": seam_metrics,
        },
        "artifacts": {
            "material": str(MATERIAL_PATH.relative_to(REVISION)).replace("\\", "/"),
            "hiddenMask": str(HIDDEN_MASK_PATH.relative_to(REVISION)).replace("\\", "/"),
            "seamRepairBand": str(SEAM_BAND_PATH.relative_to(REVISION)).replace(
                "\\", "/"
            ),
            "provenance": str(PROVENANCE_PATH.relative_to(REVISION)).replace("\\", "/"),
            "isolatedGate": str(ISOLATED_GATE_PATH.relative_to(REVISION)).replace(
                "\\", "/"
            ),
            "seamGate": str(SEAM_GATE_PATH.relative_to(REVISION)).replace("\\", "/"),
            "displacedGate": str(DISPLACED_GATE_PATH.relative_to(REVISION)).replace(
                "\\", "/"
            ),
        },
        "hashes": {
            "materialSha256": sha256(MATERIAL_PATH),
            "hiddenMaskSha256": sha256(HIDDEN_MASK_PATH),
            "seamRepairBandSha256": sha256(SEAM_BAND_PATH),
            "provenanceSha256": sha256(PROVENANCE_PATH),
            "isolatedGateSha256": sha256(ISOLATED_GATE_PATH),
            "seamGateSha256": sha256(SEAM_GATE_PATH),
            "displacedGateSha256": sha256(DISPLACED_GATE_PATH),
        },
        "visualGate": "approved_by_user_2026-07-25",
        "doesNotClaim": [
            "complete upper arm",
            "PSD",
            "Cubism",
            "Physics",
            "Runtime",
        ],
    }
    AUDIT_PATH.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if (
        not audit["checks"]["alphaMatchesLockedR9Exactly"]
        or audit["checks"]["alphaConnectedComponents"] != 1
        or not audit["checks"]["trustedSourceRgbPreserved"]
        or not audit["checks"]["newHiddenRegionFullyTextured"]
        or not audit["checks"]["outsideGeometryTransparent"]
        or not audit["checks"]["hiddenTextureHasVariation"]
        or seam_metrics["meanNearestRgbChannelDifference"] > 18
    ):
        raise SystemExit("Complete sleeve texture audit failed.")
    print(
        "PASS: complete R9 sleeve texture; "
        f"hidden={len(hidden_set)}, seam-band={len(points(seam_band))}, "
        f"unique-hidden-rgb={len(set(hidden_colors))}, "
        f"seam-mean={seam_metrics['meanNearestRgbChannelDifference']:.2f}; "
        "texture locked by user approval"
    )


if __name__ == "__main__":
    main()
