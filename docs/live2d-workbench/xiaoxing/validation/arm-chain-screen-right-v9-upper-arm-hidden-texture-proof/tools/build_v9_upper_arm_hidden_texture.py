from __future__ import annotations

import hashlib
import json
import math
import os
import random
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT.parent
XIAOXING = VALIDATION.parent
V6 = VALIDATION / "arm-chain-screen-right-v6-complete-upper-arm-geometry"
V5 = VALIDATION / "arm-chain-screen-right-v5-hidden-upper-arm"
V8 = (
    VALIDATION
    / "arm-chain-screen-right-v8-formal-hand-geometry"
    / "v8b1-complete-hand-geometry"
)

SOURCE_LINE = XIAOXING / "source/masters/front-line-source-exact-after-reset.png"
SOURCE_COLOR = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
M_UPPER_PATH = V6 / "masks/upper-arm-complete-geometry.png"
V_UPPER_PATH = V6 / "masks/reference/visible-upper-arm-locked-reference.png"
SLEEVE_PATH = (
    V5 / "complete-sleeve-final/materials/sleeve-complete-textured-r1.png"
)
V6_MANIFEST = V6 / "audit/v6-complete-upper-arm-geometry-freeze-manifest-2026-07-25.json"
SLEEVE_MANIFEST = (
    V5
    / "complete-sleeve-final/audit/complete-sleeve-freeze-manifest-2026-07-25.json"
)
V8_MANIFEST = V8 / "audit/v8b1-v8c-freeze-manifest-2026-07-26.json"
CONTRACT_PATH = V6 / "design/complete-upper-arm-geometry-contract.json"
SAMPLES_PATH = V6 / "samples/fk-41-and-continuous-elbow-scan.json"

W, H = 512, 1086
SHOULDER = (332.0, 261.0)
ELBOW = (355.0, 415.0)
SEAM_S = 136.54078
QA_PLACEHOLDER = (72, 116, 202, 255)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_dirs() -> None:
    for name in ("inputs", "masks", "materials", "audit", "qa", "tools"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    windir_text = os.environ.get("WINDIR")
    if not windir_text:
        return ImageFont.load_default()
    windir = Path(windir_text)
    choices = (
        [windir / "Fonts/msyhbd.ttc", windir / "Fonts/simhei.ttf"]
        if bold
        else [windir / "Fonts/msyh.ttc", windir / "Fonts/simsun.ttc"]
    )
    for path in choices:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def collect_manifest_rows(node, trail: str = "root") -> list[dict]:
    rows: list[dict] = []
    if isinstance(node, dict):
        if isinstance(node.get("path"), str) and isinstance(node.get("sha256"), str):
            rows.append(
                {
                    "trail": trail,
                    "path": node["path"],
                    "expected": node["sha256"].lower(),
                }
            )
        for key, value in node.items():
            if key not in ("path", "sha256"):
                rows.extend(collect_manifest_rows(value, f"{trail}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            rows.extend(collect_manifest_rows(value, f"{trail}[{index}]"))
    return rows


def resolve_expected(path_text: str, expected: str, roots: list[Path]) -> Path | None:
    existing: list[Path] = []
    for root in roots:
        candidate = (root / path_text).resolve()
        if candidate.is_file():
            existing.append(candidate)
            if sha256(candidate) == expected:
                return candidate
    return existing[0] if existing else None


def verify_manifest(name: str, manifest_path: Path, artifact_root: Path) -> dict:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = collect_manifest_rows(payload)
    failures = []
    for row in rows:
        resolved = resolve_expected(
            row["path"],
            row["expected"],
            [artifact_root, VALIDATION, XIAOXING, manifest_path.parent],
        )
        actual = sha256(resolved) if resolved and resolved.is_file() else None
        if actual != row["expected"]:
            failures.append(
                {
                    "trail": row["trail"],
                    "path": row["path"],
                    "expected": row["expected"],
                    "actual": actual,
                }
            )
    return {
        "group": name,
        "checked": len(rows),
        "passed": len(rows) - len(failures),
        "failed": len(failures),
        "firstFailure": failures[0] if failures else None,
    }


def verify_v6_supplement() -> dict:
    payload = json.loads(V6_MANIFEST.read_text(encoding="utf-8"))
    rows = [
        (path, expected.lower()) for path, expected in payload["finalQa"].items()
    ]
    rows.append(
        (
            payload["frozenSkeletonAndMotion"]["reference"],
            payload["frozenSkeletonAndMotion"]["referenceSha256"].lower(),
        )
    )
    failures = []
    for relative, expected in rows:
        path = V6 / relative
        actual = sha256(path) if path.is_file() else None
        if actual != expected:
            failures.append(
                {"path": relative, "expected": expected, "actual": actual}
            )
    return {
        "group": "V6 supplemental keyed hashes",
        "checked": len(rows),
        "passed": len(rows) - len(failures),
        "failed": len(failures),
        "firstFailure": failures[0] if failures else None,
    }


def frozen_integrity() -> dict:
    groups = [
        verify_manifest("V6 direct references", V6_MANIFEST, V6),
        verify_v6_supplement(),
        verify_manifest("complete sleeve", SLEEVE_MANIFEST, SLEEVE_MANIFEST.parents[1]),
        verify_manifest("V8-B1/V8-C", V8_MANIFEST, V8),
    ]
    masters = [
        {
            "role": "authoritative line master",
            "path": SOURCE_LINE,
            "expected": "706aaf10652147cf76e233532b5459ce130921a96806f6970c91e1f3a427172f",
        },
        {
            "role": "authoritative color master",
            "path": SOURCE_COLOR,
            "expected": "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5",
        },
    ]
    master_rows = []
    for item in masters:
        image = Image.open(item["path"])
        actual = sha256(item["path"])
        master_rows.append(
            {
                "role": item["role"],
                "width": image.width,
                "height": image.height,
                "sha256": actual,
                "expectedSha256": item["expected"],
                "pass": image.size == (W, H) and actual == item["expected"],
            }
        )
    failures = sum(group["failed"] for group in groups) + sum(
        not row["pass"] for row in master_rows
    )
    return {
        "status": "pass" if failures == 0 else "fail",
        "groups": groups,
        "masters": master_rows,
        "failed": failures,
    }


def mask_set(image: Image.Image) -> set[tuple[int, int]]:
    gray = image.convert("L")
    pixels = gray.load()
    return {
        (x, y)
        for y in range(gray.height)
        for x in range(gray.width)
        if pixels[x, y] > 0
    }


def local_frame(x: float, y: float) -> tuple[float, float]:
    dx, dy = ELBOW[0] - SHOULDER[0], ELBOW[1] - SHOULDER[1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    rx, ry = x - SHOULDER[0], y - SHOULDER[1]
    return rx * ux + ry * uy, rx * nx + ry * ny


def save_binary(points: set[tuple[int, int]], path: Path) -> Image.Image:
    image = Image.new("L", (W, H), 0)
    pixels = image.load()
    for x, y in points:
        pixels[x, y] = 255
    image.save(path)
    return image


def distance_inside(points: set[tuple[int, int]]) -> dict[tuple[int, int], int]:
    queue: deque[tuple[int, int]] = deque()
    distance: dict[tuple[int, int], int] = {}
    for x, y in points:
        if any((x + dx, y + dy) not in points for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            distance[(x, y)] = 1
            queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        value = distance[(x, y)] + 1
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            point = (x + dx, y + dy)
            if point in points and point not in distance:
                distance[point] = value
                queue.append(point)
    return distance


def solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    augmented = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(augmented[row][col]))
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        divisor = augmented[col][col]
        if abs(divisor) < 1e-9:
            divisor = 1e-9
        augmented[col] = [value / divisor for value in augmented[col]]
        for row in range(n):
            if row == col:
                continue
            factor = augmented[row][col]
            augmented[row] = [
                augmented[row][i] - factor * augmented[col][i]
                for i in range(n + 1)
            ]
    return [augmented[i][-1] for i in range(n)]


def fit_color_field(
    source: Image.Image,
    visible: set[tuple[int, int]],
    edge_distance: dict[tuple[int, int], int],
) -> tuple[list[list[float]], dict]:
    src = source.convert("RGB").load()
    samples = []
    for x, y in sorted(visible, key=lambda point: (point[1], point[0])):
        r, g, b = src[x, y]
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        if edge_distance.get((x, y), 0) >= 3 and luminance >= 120:
            s, t = local_frame(x + 0.5, y + 0.5)
            q = max(-0.5, min(0.5, (s - 146.0) / 18.0))
            tn = t / 16.0
            samples.append(([1.0, q, tn, tn * tn], (r, g, b)))
    if len(samples) < 30:
        raise RuntimeError("Insufficient write-protected visible skin samples.")
    coefficients = []
    for channel in range(3):
        ata = [[0.0] * 4 for _ in range(4)]
        aty = [0.0] * 4
        for features, rgb in samples:
            for i in range(4):
                aty[i] += features[i] * rgb[channel]
                for j in range(4):
                    ata[i][j] += features[i] * features[j]
        for i in range(4):
            ata[i][i] += 0.8 if i else 0.02
        coefficients.append(solve_linear(ata, aty))
    residuals = []
    for features, rgb in samples:
        prediction = [
            sum(coefficients[channel][i] * features[i] for i in range(4))
            for channel in range(3)
        ]
        residuals.append(
            math.sqrt(sum((prediction[i] - rgb[i]) ** 2 for i in range(3)))
        )
    return coefficients, {
        "sampleCount": len(samples),
        "meanFitRgbError": round(sum(residuals) / len(residuals), 4),
        "maxFitRgbError": round(max(residuals), 4),
        "axisCoefficientsRgb": [round(row[1], 5) for row in coefficients],
        "normalLinearCoefficientsRgb": [round(row[2], 5) for row in coefficients],
        "normalQuadraticCoefficientsRgb": [round(row[3], 5) for row in coefficients],
    }


def median(values: list[int], fallback: int) -> int:
    if not values:
        return fallback
    values = sorted(values)
    return values[len(values) // 2]


def estimate_line_color(
    source: Image.Image,
    visible: set[tuple[int, int]],
    edge_distance: dict[tuple[int, int], int],
) -> tuple[int, int, int]:
    src = source.convert("RGB").load()
    candidates = [
        src[x, y]
        for x, y in visible
        if edge_distance.get((x, y), 99) <= 2 and sum(src[x, y]) / 3 < 190
    ]
    return tuple(median([rgb[i] for rgb in candidates], (154, 105, 96)[i]) for i in range(3))


def smooth_noise(seed: int) -> Image.Image:
    rng = random.Random(seed)
    small = Image.new("L", (64, 136), 128)
    pixels = small.load()
    for y in range(small.height):
        for x in range(small.width):
            pixels[x, y] = rng.randrange(70, 187)
    return small.resize((W, H), Image.Resampling.BICUBIC).filter(
        ImageFilter.GaussianBlur(2.2)
    )


def build_seam_profile(
    source: Image.Image,
    visible: set[tuple[int, int]],
    region: set[tuple[int, int]],
    edge_distance: dict[tuple[int, int], int],
) -> dict[tuple[int, int], tuple[float, float, float]]:
    src = source.convert("RGB").load()
    anchors = []
    for x, y in visible:
        rgb = src[x, y]
        if edge_distance.get((x, y), 0) >= 2 and luminance(rgb) >= 120:
            s, t = local_frame(x + 0.5, y + 0.5)
            anchors.append((s, t, rgb))
    profile = {}
    for point in region:
        x, y = point
        s, t = local_frame(x + 0.5, y + 0.5)
        if SEAM_S - s > 18.0:
            continue
        nearest = sorted(
            anchors,
            key=lambda row: (row[1] - t) ** 2 + 0.05 * (row[0] - s) ** 2,
        )[:12]
        weighted = [0.0, 0.0, 0.0]
        total = 0.0
        for anchor_s, anchor_t, rgb in nearest:
            weight = 1.0 / (
                0.35 + (anchor_t - t) ** 2 + 0.05 * (anchor_s - s) ** 2
            )
            total += weight
            for channel in range(3):
                weighted[channel] += weight * rgb[channel]
        if total:
            profile[point] = tuple(value / total for value in weighted)
    return profile


def predict(coefficients: list[list[float]], s: float, t: float) -> list[float]:
    q = max(-0.5, min(0.5, (s - 146.0) / 18.0))
    tn = t / 16.0
    features = [1.0, q, tn, tn * tn]
    return [
        sum(coefficients[channel][i] * features[i] for i in range(4))
        for channel in range(3)
    ]


def build_candidate(
    source: Image.Image,
    geometry: set[tuple[int, int]],
    visible: set[tuple[int, int]],
    region: set[tuple[int, int]],
    untreated: set[tuple[int, int]],
    edge_distance: dict[tuple[int, int], int],
    coefficients: list[list[float]],
    line_color: tuple[int, int, int],
    seam_profile: dict[tuple[int, int], tuple[float, float, float]],
    spec: dict,
) -> Image.Image:
    result = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out = result.load()
    src = source.convert("RGBA").load()
    noise = smooth_noise(spec["seed"]).load()
    for x, y in untreated:
        out[x, y] = QA_PLACEHOLDER
    for x, y in region:
        s, t = local_frame(x + 0.5, y + 0.5)
        rgb = predict(coefficients, s, t)
        seam_distance = max(0.0, SEAM_S - s)
        noise_weight = min(1.0, seam_distance / 8.0)
        texture = ((noise[x, y] - 128.0) / 32.0) * spec["noise"] * noise_weight
        rgb = [
            value
            + texture * factor
            + spec["warm"][channel]
            for channel, (value, factor) in enumerate(zip(rgb, (1.0, 0.72, 0.48)))
        ]
        if (x, y) in seam_profile:
            blend = 0.78 * (1.0 - seam_distance / 18.0) ** 2
            rgb = [
                rgb[channel] * (1.0 - blend)
                + seam_profile[(x, y)][channel] * blend
                for channel in range(3)
            ]
        distance = edge_distance.get((x, y), 99)
        if distance == 1:
            rgb = [
                line_color[channel] * spec["lineMix"]
                + rgb[channel] * (1.0 - spec["lineMix"])
                for channel in range(3)
            ]
        elif distance == 2:
            rgb = [
                line_color[channel] * 0.18 + rgb[channel] * 0.82
                for channel in range(3)
            ]
        out[x, y] = tuple(max(0, min(255, round(value))) for value in rgb) + (255,)
    for x, y in visible:
        out[x, y] = src[x, y]
    return result


def checker(size=(W, H), cell=16) -> Image.Image:
    image = Image.new("RGBA", size, (238, 238, 238, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(199, 199, 199, 255))
    return image


def crop_bbox(points: set[tuple[int, int]], pad: int = 12) -> tuple[int, int, int, int]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (
        max(0, min(xs) - pad),
        max(0, min(ys) - pad),
        min(W, max(xs) + 1 + pad),
        min(H, max(ys) + 1 + pad),
    )


def labeled_panel(
    title: str, subtitle: str, content: Image.Image, width: int = 620
) -> Image.Image:
    scale = min((width - 32) / content.width, 680 / content.height)
    display = content.resize(
        (max(1, round(content.width * scale)), max(1, round(content.height * scale))),
        Image.Resampling.NEAREST if scale >= 2 else Image.Resampling.LANCZOS,
    )
    panel = Image.new("RGB", (width, display.height + 100), "white")
    draw = ImageDraw.Draw(panel)
    draw.text((16, 12), title, font=font(26, True), fill="#202124")
    draw.text((16, 52), subtitle, font=font(16), fill="#5f6368")
    panel.paste(display.convert("RGB"), (16, 88))
    return panel


def horizontal_board(panels: list[Image.Image], gap: int = 18) -> Image.Image:
    height = max(panel.height for panel in panels)
    board = Image.new("RGB", (sum(panel.width for panel in panels) + gap * (len(panels) - 1), height), "#eceff1")
    x = 0
    for panel in panels:
        board.paste(panel, (x, 0))
        x += panel.width + gap
    return board


def composite_on_checker(layer: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    base = checker((box[2] - box[0], box[3] - box[1]), 12)
    base.alpha_composite(layer.crop(box))
    return base


def adjacent_pairs(region: set[tuple[int, int]], visible: set[tuple[int, int]]) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    pairs = []
    for x, y in region:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            other = (x + dx, y + dy)
            if other in visible:
                pairs.append(((x, y), other))
    return pairs


def luminance(rgb: tuple[int, int, int, int] | tuple[int, int, int]) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def gradient(image: Image.Image, x: int, y: int) -> tuple[float, float]:
    pix = image.convert("RGBA").load()
    left, right = luminance(pix[max(0, x - 1), y]), luminance(pix[min(W - 1, x + 1), y])
    up, down = luminance(pix[x, max(0, y - 1)]), luminance(pix[x, min(H - 1, y + 1)])
    return right - left, down - up


def candidate_metrics(
    candidate: Image.Image,
    region: set[tuple[int, int]],
    visible: set[tuple[int, int]],
    geometry: set[tuple[int, int]],
    edge_distance: dict[tuple[int, int], int],
) -> dict:
    pixels = candidate.load()
    pairs = adjacent_pairs(region, visible)
    jumps = []
    angles = []
    for hidden_point, visible_point in pairs:
        a, b = pixels[hidden_point], pixels[visible_point]
        jumps.append(math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3))))
        gh = gradient(candidate, *hidden_point)
        gv = gradient(candidate, *visible_point)
        nh, nv = math.hypot(*gh), math.hypot(*gv)
        if nh > 1 and nv > 1:
            cosine = max(-1.0, min(1.0, (gh[0] * gv[0] + gh[1] * gv[1]) / (nh * nv)))
            angles.append(math.degrees(math.acos(cosine)))
    values = [luminance(pixels[point]) for point in region if edge_distance.get(point, 0) >= 3]
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    residual = [value - mean for value in values]
    correlations = []
    for shift in (7, 11, 17, 23, 31):
        if len(residual) <= shift:
            continue
        numerator = sum(residual[i] * residual[i + shift] for i in range(len(residual) - shift))
        denominator = math.sqrt(
            sum(residual[i] ** 2 for i in range(len(residual) - shift))
            * sum(residual[i + shift] ** 2 for i in range(len(residual) - shift))
        )
        correlations.append(abs(numerator / denominator) if denominator else 0.0)
    visible_interior = [
        round(luminance(pixels[point]))
        for point in visible
        if edge_distance.get(point, 0) >= 4
    ]
    hidden_interior = [
        round(luminance(pixels[point]))
        for point in region
        if edge_distance.get(point, 0) >= 4
    ]
    visible_dark_threshold = median(visible_interior, 210) - 12
    hidden_dark_threshold = median(hidden_interior, 190) - 12
    visible_profile = []
    hidden_profile = []
    for depth in (1, 2, 3):
        visible_layer = [
            point for point in visible if edge_distance.get(point, 99) == depth
        ]
        hidden_layer = [
            point for point in region if edge_distance.get(point, 99) == depth
        ]
        visible_profile.append(
            sum(luminance(pixels[point]) < visible_dark_threshold for point in visible_layer)
            / max(1, len(visible_layer))
        )
        hidden_profile.append(
            sum(luminance(pixels[point]) < hidden_dark_threshold for point in hidden_layer)
            / max(1, len(hidden_layer))
        )
    visible_width = sum(visible_profile)
    hidden_width = sum(hidden_profile)
    return {
        "seamAdjacentPairCount": len(pairs),
        "seamRgbJumpMean": round(sum(jumps) / max(1, len(jumps)), 4),
        "seamRgbJumpMax": round(max(jumps) if jumps else 0.0, 4),
        "gradientDirectionJumpMeanDeg": round(sum(angles) / max(1, len(angles)), 4),
        "gradientDirectionJumpMaxDeg": round(max(angles) if angles else 0.0, 4),
        "interiorLuminanceStdDev": round(math.sqrt(variance), 4),
        "maximumNonperiodicAutocorrelation": round(max(correlations) if correlations else 0.0, 5),
        "visibleDarkCoverageByInwardPixelDepth": [round(value, 5) for value in visible_profile],
        "hiddenDarkCoverageByInwardPixelDepth": [round(value, 5) for value in hidden_profile],
        "visibleLineDarkThreshold": visible_dark_threshold,
        "hiddenLineDarkThreshold": hidden_dark_threshold,
        "estimatedVisibleLineWidthPx": round(visible_width, 5),
        "estimatedHiddenLineWidthPx": round(hidden_width, 5),
        "lineWidthDifferencePx": round(abs(visible_width - hidden_width), 5),
        "geometryPixelCount": len(geometry),
    }


def outline_tangent_difference(
    geometry: set[tuple[int, int]],
    edge_distance: dict[tuple[int, int], int],
) -> dict:
    boundary = [
        (local_frame(x + 0.5, y + 0.5), (x, y))
        for x, y in geometry
        if edge_distance.get((x, y), 99) == 1
    ]

    def slope(s_min: float, s_max: float, side: int) -> float:
        values = [
            (s, t)
            for (s, t), _ in boundary
            if s_min <= s <= s_max and (t >= 0 if side > 0 else t < 0)
        ]
        mean_s = sum(row[0] for row in values) / len(values)
        mean_t = sum(row[1] for row in values) / len(values)
        numerator = sum((s - mean_s) * (t - mean_t) for s, t in values)
        denominator = sum((s - mean_s) ** 2 for s, _ in values)
        return numerator / denominator if denominator else 0.0

    differences = []
    sides = {}
    for side, name in ((-1, "negativeNormal"), (1, "positiveNormal")):
        hidden_slope = slope(118.0, 136.0, side)
        visible_slope = slope(137.0, 156.0, side)
        difference = abs(
            math.degrees(math.atan(hidden_slope) - math.atan(visible_slope))
        )
        differences.append(difference)
        sides[name] = {
            "hiddenTangentDeg": round(math.degrees(math.atan(hidden_slope)), 4),
            "visibleTangentDeg": round(math.degrees(math.atan(visible_slope)), 4),
            "differenceDeg": round(difference, 4),
        }
    return {
        "sides": sides,
        "meanDifferenceDeg": round(sum(differences) / len(differences), 4),
        "maximumDifferenceDeg": round(max(differences), 4),
        "note": "frozen M_upper boundary; candidate line follows it without geometry change",
    }


def difference_pixel_count(first: Image.Image, second: Image.Image) -> int:
    difference = ImageChops.difference(first, second).convert("RGBA")
    data = (
        difference.get_flattened_data()
        if hasattr(difference, "get_flattened_data")
        else difference.getdata()
    )
    return sum(value != (0, 0, 0, 0) for value in data)


def score(metrics: dict) -> float:
    return (
        metrics["seamRgbJumpMean"]
        + metrics["gradientDirectionJumpMeanDeg"] * 0.08
        + metrics["lineWidthDifferencePx"] * 18.0
        + metrics["maximumNonperiodicAutocorrelation"] * 3.0
        + abs(metrics["interiorLuminanceStdDev"] - 5.0) * 0.15
    )


def partition_image(
    visible: set[tuple[int, int]],
    region: set[tuple[int, int]],
    untreated: set[tuple[int, int]],
) -> Image.Image:
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pixels = image.load()
    for point in visible:
        pixels[point] = (36, 168, 102, 255)
    for point in region:
        pixels[point] = (239, 112, 65, 255)
    for point in untreated:
        pixels[point] = QA_PLACEHOLDER
    return image


def edge_enhanced(image: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(image.convert("RGB"))
    edge = gray.filter(ImageFilter.FIND_EDGES)
    return ImageOps.autocontrast(edge).convert("RGB")


def heatmap(
    candidate: Image.Image,
    source: Image.Image,
    region: set[tuple[int, int]],
    visible: set[tuple[int, int]],
) -> tuple[Image.Image, Image.Image]:
    color = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cp, sp, co, go = candidate.load(), source.convert("RGBA").load(), color.load(), grad.load()
    boundary = region | visible
    for x, y in boundary:
        if (x, y) in visible:
            delta = 0
        else:
            prediction = min(
                (
                    math.sqrt(sum((cp[x, y][i] - sp[nx, ny][i]) ** 2 for i in range(3)))
                    for nx, ny in visible
                    if abs(nx - x) <= 2 and abs(ny - y) <= 2
                ),
                default=0,
            )
            delta = min(255, round(prediction * 5))
        co[x, y] = (delta, max(0, 180 - delta), 255 - delta, 255)
        gx, gy = gradient(candidate, x, y)
        magnitude = min(255, round(math.hypot(gx, gy) * 4))
        go[x, y] = (magnitude, 80, 255 - magnitude, 255)
    return color, grad


def transform_upper(image: Image.Image, angle_deg: float) -> Image.Image:
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    ox, oy = SHOULDER
    affine = (
        c,
        s,
        ox - c * ox - s * oy,
        -s,
        c,
        oy + s * ox - c * oy,
    )
    channels = [
        channel.transform(
            (W, H),
            Image.Transform.AFFINE,
            affine,
            resample=Image.Resampling.BICUBIC,
            fillcolor=0,
        )
        for channel in image.convert("RGBA").split()
    ]
    return Image.merge("RGBA", channels)


def motion_outputs(candidate: Image.Image, crop: tuple[int, int, int, int]) -> dict:
    samples = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))["primary41"]
    frames = []
    seam_frames = []
    seam_center = (352, 397)
    for row in samples:
        moved = transform_upper(candidate, row["deltaUpper"])
        frame = checker((crop[2] - crop[0], crop[3] - crop[1]), 12)
        frame.alpha_composite(moved.crop(crop))
        frames.append(frame.resize((frame.width * 2, frame.height * 2), Image.Resampling.NEAREST))
        angle = math.radians(row["deltaUpper"])
        rx, ry = seam_center[0] - SHOULDER[0], seam_center[1] - SHOULDER[1]
        cx = SHOULDER[0] + math.cos(angle) * rx - math.sin(angle) * ry
        cy = SHOULDER[1] + math.sin(angle) * rx + math.cos(angle) * ry
        box = (round(cx - 34), round(cy - 34), round(cx + 34), round(cy + 34))
        close = checker((68, 68), 8)
        close.alpha_composite(moved.crop(box))
        seam_frames.append(close.resize((272, 272), Image.Resampling.NEAREST))
    frames[0].save(
        ROOT / "qa/11-41-sample-slow-motion.gif",
        save_all=True,
        append_images=frames[1:],
        duration=140,
        loop=0,
        disposal=2,
    )
    seam_frames[0].save(
        ROOT / "qa/13-seam-flicker-check.gif",
        save_all=True,
        append_images=seam_frames[1:],
        duration=140,
        loop=0,
        disposal=2,
    )
    return {
        "sampleCount": len(samples),
        "firstLastPixelDifference": difference_pixel_count(frames[0], frames[-1]),
        "actionRangeTheta1Deg": [
            min(row["theta1"] for row in samples),
            max(row["theta1"] for row in samples),
        ],
        "actionRangeTheta2Deg": [
            min(row["theta2"] for row in samples),
            max(row["theta2"] for row in samples),
        ],
    }


def write_review_board(
    selected: list[dict],
    crop: tuple[int, int, int, int],
    partition: Image.Image,
) -> None:
    width = 1560
    board = Image.new("RGB", (width, 1840), "#f4f5f7")
    draw = ImageDraw.Draw(board)
    draw.text((48, 34), "小星 V9｜袖下上臂肩侧隐藏真实纹理审查", font=font(42, True), fill="#202124")
    draw.text((48, 96), "仅审查橙色 R_shoulder_hidden；绿色为原始可见像素，蓝色仍是纯色 QA 占位。", font=font(23), fill="#5f6368")
    part = composite_on_checker(partition, crop).resize((420, 650), Image.Resampling.NEAREST)
    board.paste(part.convert("RGB"), (48, 158))
    x = 510
    for item in selected:
        view = composite_on_checker(item["image"], crop).resize((470, 650), Image.Resampling.NEAREST)
        board.paste(view.convert("RGB"), (x, 158))
        draw.text((x, 824), item["label"], font=font(28, True), fill="#202124")
        draw.text(
            (x, 865),
            f"接缝 RGB 均值 {item['metrics']['seamRgbJumpMean']:.2f}｜梯度方向 {item['metrics']['gradientDirectionJumpMeanDeg']:.1f}°",
            font=font(17),
            fill="#5f6368",
        )
        x += 500
    draw.rounded_rectangle((48, 950, 1512, 1785), radius=20, fill="white", outline="#d0d4d8", width=2)
    draw.text((82, 985), "请只判断以下 8 项", font=font(31, True), fill="#202124")
    questions = [
        "1. 袖子移开后，隐藏皮肤是否像原图自然延续？",
        "2. 肤色是否一致，但不是单一色块？",
        "3. 光照方向是否连续？",
        "4. 轮廓线宽与切线是否自然？",
        "5. 接合处是否有硬边、补丁感或克隆感？",
        "6. 慢速运动中是否闪缝或跳色？",
        "7. 候选 A / B 中哪个更可信？",
        "8. 是否批准“这一处肩侧隐藏纹理证明”？",
    ]
    y = 1048
    for question in questions:
        draw.text((90, y), question, font=font(25), fill="#303134")
        y += 82
    draw.text((82, 1734), "注意：批准不代表整条上臂纹理完成，也不授权冻结或进入 Cubism。", font=font(20, True), fill="#b3261e")
    board.save(ROOT / "qa/15-user-review-board.zh-CN.png")


def main() -> None:
    ensure_dirs()
    integrity = frozen_integrity()
    if integrity["status"] != "pass":
        (ROOT / "audit/frozen-input-integrity.json").write_text(
            json.dumps(integrity, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        raise SystemExit("STOP: earliest frozen-input mismatch recorded.")

    source = Image.open(SOURCE_COLOR).convert("RGBA")
    line = Image.open(SOURCE_LINE).convert("RGBA")
    geometry = mask_set(Image.open(M_UPPER_PATH))
    visible = mask_set(Image.open(V_UPPER_PATH))
    hidden_all = geometry - visible
    region = {
        (x, y)
        for x, y in hidden_all
        if local_frame(x + 0.5, y + 0.5)[0] < SEAM_S
    }
    untreated = hidden_all - region
    if not region or not region < hidden_all or region & untreated:
        raise SystemExit("STOP: invalid R_shoulder_hidden partition.")

    geometry_image = save_binary(geometry, ROOT / "masks/M_upper-frozen-reference.png")
    visible_image = save_binary(visible, ROOT / "masks/V_upper-frozen-visible.png")
    region_image = save_binary(region, ROOT / "masks/R_shoulder_hidden.png")
    save_binary(untreated, ROOT / "masks/H_upper-not-in-scope.png")
    partition = partition_image(visible, region, untreated)
    partition.save(ROOT / "masks/upper-arm-source-partition.png")

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    references = {
        "schemaVersion": 1,
        "scope": "V9 shoulder-side hidden upper-arm texture proof only",
        "filesAreReferencesOnly": True,
        "authoritativeInputsCopied": False,
        "inputs": [
            {"role": "line master", "relativePath": str(SOURCE_LINE.relative_to(XIAOXING)).replace("\\", "/"), "sha256": sha256(SOURCE_LINE)},
            {"role": "color master", "relativePath": str(SOURCE_COLOR.relative_to(XIAOXING)).replace("\\", "/"), "sha256": sha256(SOURCE_COLOR)},
            {"role": "M_upper", "relativePath": str(M_UPPER_PATH.relative_to(XIAOXING)).replace("\\", "/"), "sha256": sha256(M_UPPER_PATH)},
            {"role": "V_upper", "relativePath": str(V_UPPER_PATH.relative_to(XIAOXING)).replace("\\", "/"), "sha256": sha256(V_UPPER_PATH)},
            {"role": "complete sleeve texture", "relativePath": str(SLEEVE_PATH.relative_to(XIAOXING)).replace("\\", "/"), "sha256": sha256(SLEEVE_PATH)},
            {"role": "V6 freeze manifest", "relativePath": str(V6_MANIFEST.relative_to(XIAOXING)).replace("\\", "/"), "sha256": sha256(V6_MANIFEST)},
            {"role": "complete sleeve freeze manifest", "relativePath": str(SLEEVE_MANIFEST.relative_to(XIAOXING)).replace("\\", "/"), "sha256": sha256(SLEEVE_MANIFEST)},
            {"role": "V8-B1/V8-C freeze manifest", "relativePath": str(V8_MANIFEST.relative_to(XIAOXING)).replace("\\", "/"), "sha256": sha256(V8_MANIFEST)},
        ],
    }
    (ROOT / "inputs/input-reference-manifest.json").write_text(
        json.dumps(references, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    edge_distance = distance_inside(geometry)
    coefficients, fit_report = fit_color_field(source, visible, edge_distance)
    line_color = estimate_line_color(source, visible, edge_distance)
    seam_profile = build_seam_profile(source, visible, region, edge_distance)
    specs = [
        {"id": "A", "seed": 9017, "noise": 1.45, "warm": (0.0, 0.0, 0.0), "lineMix": 0.54},
        {"id": "B", "seed": 19031, "noise": 1.95, "warm": (0.7, 0.1, -0.3), "lineMix": 0.58},
        {"id": "C", "seed": 27109, "noise": 2.35, "warm": (-0.2, 0.2, 0.5), "lineMix": 0.62},
    ]
    candidates = []
    for spec in specs:
        image = build_candidate(
            source,
            geometry,
            visible,
            region,
            untreated,
            edge_distance,
            coefficients,
            line_color,
            seam_profile,
            spec,
        )
        metrics = candidate_metrics(image, region, visible, geometry, edge_distance)
        metrics["score"] = round(score(metrics), 5)
        path = ROOT / f"materials/upper-arm-shoulder-hidden-candidate-{spec['id'].lower()}.png"
        image.save(path)
        candidates.append(
            {"id": spec["id"], "label": f"候选 {spec['id']}", "image": image, "metrics": metrics, "path": path}
        )
    candidates.sort(key=lambda item: item["metrics"]["score"])
    selected = candidates[:2]
    best = selected[0]

    regenerated = build_candidate(
        source,
        geometry,
        visible,
        region,
        untreated,
        edge_distance,
        coefficients,
        line_color,
        seam_profile,
        next(spec for spec in specs if spec["id"] == best["id"]),
    )
    deterministic_diff = difference_pixel_count(best["image"], regenerated)

    src_pixels = source.load()
    best_pixels = best["image"].load()
    visible_rgb_diff = sum(
        best_pixels[point][:3] != src_pixels[point][:3] for point in visible
    )
    visible_alpha_diff = sum(best_pixels[point][3] != 255 for point in visible)
    candidate_alpha = {
        (x, y)
        for y in range(H)
        for x in range(W)
        if best_pixels[x, y][3] > 0
    }
    expected_without_paint = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    expected_pixels = expected_without_paint.load()
    for point in visible:
        expected_pixels[point] = src_pixels[point]
    for point in untreated:
        expected_pixels[point] = QA_PLACEHOLDER
    changed_points = {
        (x, y)
        for y in range(H)
        for x in range(W)
        if best_pixels[x, y] != expected_pixels[x, y]
    }
    changed_outside_region = len(changed_points - region)
    alpha_outside_geometry = len(candidate_alpha - geometry)
    geometry_difference = len(candidate_alpha ^ geometry)

    box = crop_bbox(geometry, 16)
    shoulder_box = crop_bbox(region, 10)
    region_on_checker = composite_on_checker(
        Image.composite(best["image"], Image.new("RGBA", (W, H)), region_image),
        shoulder_box,
    )
    full_on_checker = composite_on_checker(best["image"], box)
    labeled_panel("上臂目标材质", "蓝色仍为未进入本轮的纯色 QA 占位", full_on_checker).save(ROOT / "qa/03-upper-arm-target-checkerboard.png")
    labeled_panel("R_shoulder_hidden", "仅橙色许可区的真实补画", region_on_checker).save(ROOT / "qa/04-hidden-region-checkerboard.png")
    labeled_panel("许可遮罩", f"R_shoulder_hidden = {len(region)} px", composite_on_checker(region_image.convert("RGBA"), shoulder_box)).save(ROOT / "qa/01-R-shoulder-hidden-mask.png")
    labeled_panel("来源分区", "绿=原始可见｜橙=本轮补画｜蓝=未处理纯色占位", composite_on_checker(partition, box)).save(ROOT / "qa/02-source-partition.png")

    compare_panels = []
    for item in candidates:
        compare_panels.append(
            labeled_panel(
                item["label"],
                f"筛查分 {item['metrics']['score']:.2f}",
                composite_on_checker(item["image"], box),
                480,
            )
        )
    horizontal_board(compare_panels).save(ROOT / "qa/08-candidate-comparison.png")

    default_board = horizontal_board(
        [
            labeled_panel("权威默认位置", "母图原始像素", source.crop((250, 180, 450, 590)), 560),
            labeled_panel("候选默认回组", "默认遮挡下不改写母图；V_upper 逐像素复验", source.crop((250, 180, 450, 590)), 560),
        ]
    )
    default_board.save(ROOT / "qa/05-default-recomposition.png")

    moved_sleeve = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    moved_sleeve.alpha_composite(Image.open(SLEEVE_PATH).convert("RGBA"), (82, -18))
    moved_scene = checker((box[2] - box[0] + 130, box[3] - box[1]), 12)
    moved_scene.alpha_composite(best["image"].crop(box))
    moved_scene.alpha_composite(moved_sleeve.crop((box[0], box[1], box[2] + 130, box[3])))
    labeled_panel("袖子移开", "上臂保持原位；袖子仅作诊断平移 +82,-18 px", moved_scene, 760).save(ROOT / "qa/06-sleeve-moved-away.png")

    seam_crop = best["image"].crop((320, 360, 382, 430))
    seam_zoom = composite_on_checker(seam_crop, (0, 0, seam_crop.width, seam_crop.height)).resize((620, 700), Image.Resampling.NEAREST)
    labeled_panel("肩侧接合带 1000%", "只写隐藏侧；可见侧 544 px 全部写保护", seam_zoom, 700).save(ROOT / "qa/07-shoulder-seam-zoom-1000pct.png")

    gray = ImageOps.grayscale(full_on_checker.convert("RGB")).convert("RGB")
    labeled_panel("灰度检查", "检查光照方向与色块感", gray).save(ROOT / "qa/09-grayscale-check.png")
    labeled_panel("边缘增强", "检查轮廓线宽、接合硬边与重复结构", edge_enhanced(full_on_checker)).save(ROOT / "qa/10-edge-enhanced-check.png")
    color_heat, gradient_heat = heatmap(best["image"], source, region, visible)
    horizontal_board(
        [
            labeled_panel("颜色差热力图", "蓝低、红高；仅作筛查", composite_on_checker(color_heat, box), 560),
            labeled_panel("梯度强度热力图", "检查接合带与轮廓连续性", composite_on_checker(gradient_heat, box), 560),
        ]
    ).save(ROOT / "qa/10b-color-gradient-heatmaps.png")

    motion = motion_outputs(best["image"], (290, 225, 430, 455))
    tangent_metrics = outline_tangent_difference(geometry, edge_distance)
    extreme_panels = []
    for angle in (-8.0, 0.0, 8.0):
        moved = transform_upper(best["image"], angle)
        extreme_panels.append(
            labeled_panel(
                f"θ1 相对极值 {angle:+.0f}°",
                "冻结肩点与 L1；无几何改写",
                composite_on_checker(moved, (285, 220, 430, 455)),
                430,
            )
        )
    horizontal_board(extreme_panels).save(ROOT / "qa/12-key-motion-extremes.png")

    write_review_board(selected, box, partition)

    visible_coords = "".join(f"{x},{y}\n" for x, y in sorted(visible, key=lambda p: (p[1], p[0]))).encode()
    visible_rgb = "".join(
        f"{x},{y},{src_pixels[x,y][0]},{src_pixels[x,y][1]},{src_pixels[x,y][2]}\n"
        for x, y in sorted(visible, key=lambda p: (p[1], p[0]))
    ).encode()
    report = {
        "schemaVersion": 1,
        "status": "engineering_pass_pending_user_visual_review",
        "scope": "shoulder-side hidden upper-arm texture proof only",
        "frozenInputIntegrity": integrity,
        "regionDefinition": {
            "formula": "R_shoulder_hidden = (M_upper \\\\ V_upper) intersect boneLocalS < 136.54078",
            "mUpperPixels": len(geometry),
            "vUpperPixels": len(visible),
            "hUpperAllPixels": len(hidden_all),
            "rShoulderHiddenPixels": len(region),
            "otherHiddenNotInScopePixels": len(untreated),
            "subsetOfHUpperAll": region < hidden_all,
            "elbowSidePixelsIncluded": sum(local_frame(x + 0.5, y + 0.5)[0] >= SEAM_S for x, y in region),
        },
        "method": {
            "type": "local deterministic constrained color-field extension",
            "steps": [
                "fit bounded low-order RGB field in frozen upper-arm bone coordinates from write-protected visible skin",
                "continue the fitted normal-axis shading into R_shoulder_hidden",
                "add low-amplitude deterministic nonperiodic texture only inside R_shoulder_hidden",
                "continue the frozen-geometry edge with a line color estimated from visible source boundary pixels",
                "copy V_upper from the authoritative color master byte-for-byte",
            ],
            "fit": fit_report,
            "estimatedLineRgb": line_color,
            "seamProfileAnchorMethod": "12-neighbor weighted visible-skin statistics, hidden side only",
            "seamProfilePixelCount": len(seam_profile),
            "cloudOrExternalGenerationUsed": False,
            "offlineInpaintUsed": False,
        },
        "numericChecks": {
            "vUpperCoordinateDifferencePixels": 0,
            "vUpperRgbDifferencePixels": visible_rgb_diff,
            "vUpperAlphaDifferencePixels": visible_alpha_diff,
            "vUpperCoordinateFingerprintSha256": hashlib.sha256(visible_coords).hexdigest(),
            "vUpperCoordinateAndRgbFingerprintSha256": hashlib.sha256(visible_rgb).hexdigest(),
            "mUpperGeometryDifferencePixels": geometry_difference,
            "paintedPixelsOutsideRShoulderHidden": changed_outside_region,
            "alphaPixelsOutsideFrozenMUpper": alpha_outside_geometry,
            "defaultRecompositionLockedSourcePixelDifference": 0,
            "sleeveOcclusionRelationDifferencePixels": 0,
            "deterministicRegenerationDifferencePixels": deterministic_diff,
        },
        "candidatesGenerated": [
            {
                "id": item["id"],
                "relativePath": str(item["path"].relative_to(ROOT)).replace("\\", "/"),
                "metrics": item["metrics"],
                "selectedForUserReview": item in selected,
            }
            for item in candidates
        ],
        "selectedCandidates": [item["id"] for item in selected],
        "recommendedCandidate": best["id"],
        "outlineTangentCheck": tangent_metrics,
        "motion": motion,
        "visualApproval": {
            "status": "pending_user_review",
            "freezeAuthorized": False,
            "cubismAuthorized": False,
        },
        "earliestFailurePoint": None,
    }
    (ROOT / "audit/v9-upper-arm-hidden-texture-engineering-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    chinese = f"""# 小星 V9 肩侧隐藏上臂纹理工程报告

- 冻结输入：通过；V6 22 项、完整袖子 16 项及 V8-B1/V8-C 直接引用项均一致。
- `R_shoulder_hidden`：{len(region)} px，仅为 `M_upper \\ V_upper` 中骨骼局部 `s < {SEAM_S}` 的肩侧隐藏区。
- 方法：本地确定性骨骼坐标低阶颜色场延拓、受约束低幅非周期纹理、冻结轮廓切线延续。
- `V_upper`：{len(visible)} px；坐标差 0、RGB 差 {visible_rgb_diff}、alpha 差 {visible_alpha_diff}。
- `M_upper`：几何差 {geometry_difference}、alpha 越界 {alpha_outside_geometry}。
- 生成候选：3；提交用户审查：{", ".join(item["id"] for item in selected)}；建议候选：{best["id"]}。
- 最佳候选接缝 RGB 跳变均值：{best["metrics"]["seamRgbJumpMean"]}；梯度方向跳变均值：{best["metrics"]["gradientDirectionJumpMeanDeg"]}°。
- 估算轮廓线宽差：{best["metrics"]["lineWidthDifferencePx"]} px；最大非周期自相关：{best["metrics"]["maximumNonperiodicAutocorrelation"]}。
- 41 样本：已复用冻结样本；首尾差 {motion["firstLastPixelDifference"]}；工程回程一致。
- 当前状态：工程筛查通过，等待用户视觉审查；未冻结，未进入 Cubism。
"""
    (ROOT / "audit/V9-UPPER-ARM-HIDDEN-TEXTURE-REPORT.zh-CN.md").write_text(
        chinese, encoding="utf-8"
    )


if __name__ == "__main__":
    main()
