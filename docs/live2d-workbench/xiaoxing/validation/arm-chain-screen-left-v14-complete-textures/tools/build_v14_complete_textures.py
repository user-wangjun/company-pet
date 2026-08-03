from __future__ import annotations

import hashlib
import json
import math
import random
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
V13 = WORKBENCH / "validation/arm-chain-screen-left-v13-material-separation"
V13_FREEZE = V13 / "audit/v13-material-boundary-freeze-manifest-2026-07-27.json"
SOURCE_COLOR = WORKBENCH / "source/masters/front-color-source-exact-after-reset.png"

W, H = 512, 1086
LAYERS = ["sleeve", "upper_arm", "forearm_bracelet", "whole_hand"]
DRAW_ORDER = ["upper_arm", "whole_hand", "forearm_bracelet", "sleeve"]
SEEDS = {
    "sleeve": 1401,
    "upper_arm": 1402,
    "forearm_bracelet": 1403,
    "whole_hand": 1404,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def binary(mask: Image.Image, threshold: int = 1) -> Image.Image:
    return mask.convert("L").point(lambda value: 255 if value >= threshold else 0)


def load_mask(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    return binary(image.getchannel("A"))


def count(mask: Image.Image) -> int:
    return sum(1 for value in binary(mask).get_flattened_data() if value)


def points(mask: Image.Image) -> set[tuple[int, int]]:
    data = binary(mask).load()
    bbox = mask.getbbox()
    if bbox is None:
        return set()
    return {
        (x, y)
        for y in range(bbox[1], bbox[3])
        for x in range(bbox[0], bbox[2])
        if data[x, y]
    }


def verify_manifest(path: Path, root: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    matches = 0
    for item in manifest["lockedArtifacts"]:
        artifact = root / item["path"]
        if (
            artifact.is_file()
            and artifact.stat().st_size == item["bytes"]
            and sha256(artifact) == item["sha256"]
        ):
            matches += 1
    return {
        "path": path.relative_to(WORKBENCH).as_posix(),
        "sha256": sha256(path),
        "matchedArtifacts": matches,
        "artifactCount": manifest["artifactCount"],
        "pass": matches == manifest["artifactCount"],
    }


def solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]
    for column in range(n):
        pivot = max(range(column, n), key=lambda row: abs(augmented[row][column]))
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        if abs(divisor) < 1e-9:
            divisor = 1e-9
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(n):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                augmented[row][i] - factor * augmented[column][i]
                for i in range(n + 1)
            ]
    return [augmented[index][-1] for index in range(n)]


def edge_distance(region: set[tuple[int, int]]) -> dict[tuple[int, int], int]:
    distance: dict[tuple[int, int], int] = {}
    queue = deque()
    for x, y in region:
        if any((x + dx, y + dy) not in region for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            distance[(x, y)] = 1
            queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        value = distance[(x, y)] + 1
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            point = (x + dx, y + dy)
            if point in region and point not in distance:
                distance[point] = value
                queue.append(point)
    return distance


def distance_from_seed(
    geometry: set[tuple[int, int]],
    seed: set[tuple[int, int]],
) -> dict[tuple[int, int], int]:
    distance = {point: 0 for point in seed}
    queue = deque(seed)
    while queue:
        x, y = queue.popleft()
        value = distance[(x, y)] + 1
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            point = (x + dx, y + dy)
            if point in geometry and point not in distance:
                distance[point] = value
                queue.append(point)
    return distance


def frame(
    origin: tuple[float, float],
    end: tuple[float, float],
):
    dx, dy = end[0] - origin[0], end[1] - origin[1]
    length = math.hypot(dx, dy)
    unit = (dx / length, dy / length)
    normal = (-unit[1], unit[0])
    return origin, unit, normal, length


def local(
    point: tuple[float, float],
    coordinate_frame,
) -> tuple[float, float]:
    origin, unit, normal, _ = coordinate_frame
    dx, dy = point[0] - origin[0], point[1] - origin[1]
    return dx * unit[0] + dy * unit[1], dx * normal[0] + dy * normal[1]


def fit_color_field(
    source: Image.Image,
    visible: set[tuple[int, int]],
    coordinate_frame,
    layer: str,
) -> tuple[list[list[float]], dict, list[tuple[float, float, tuple[int, int, int]]]]:
    src = source.load()
    visible_edge = edge_distance(visible)
    local_rows = []
    for x, y in sorted(visible, key=lambda p: (p[1], p[0])):
        rgb = src[x, y]
        luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
        skin_like = rgb[0] - rgb[1] > 4 and rgb[0] - rgb[2] > 8
        if (
            visible_edge.get((x, y), 0) >= 2
            and luminance >= (145 if layer == "sleeve" else 105)
            and (layer == "sleeve" or skin_like)
        ):
            s, n = local((x + 0.5, y + 0.5), coordinate_frame)
            local_rows.append((s, n, rgb))
    if len(local_rows) < 30:
        raise RuntimeError(f"Insufficient visible samples for {layer}: {len(local_rows)}")
    s_values = [row[0] for row in local_rows]
    n_values = [row[1] for row in local_rows]
    s_center = sum(s_values) / len(s_values)
    n_center = sum(n_values) / len(n_values)
    s_scale = max(12.0, max(s_values) - min(s_values))
    n_scale = max(10.0, max(n_values) - min(n_values))
    samples = []
    for s, n, rgb in local_rows:
        sn = max(-1.0, min(1.0, (s - s_center) / s_scale))
        nn = max(-1.0, min(1.0, (n - n_center) / n_scale))
        features = [1.0, sn, nn, nn * nn, sn * nn]
        samples.append((features, rgb))
    coefficients = []
    for channel in range(3):
        size = 5
        ata = [[0.0] * size for _ in range(size)]
        aty = [0.0] * size
        for features, rgb in samples:
            for i in range(size):
                aty[i] += features[i] * rgb[channel]
                for j in range(size):
                    ata[i][j] += features[i] * features[j]
        for i in range(size):
            ata[i][i] += 0.8 if i else 0.02
        coefficients.append(solve_linear(ata, aty))
    errors = []
    for features, rgb in samples:
        predicted = [
            sum(coefficients[channel][i] * features[i] for i in range(5))
            for channel in range(3)
        ]
        errors.append(math.sqrt(sum((predicted[i] - rgb[i]) ** 2 for i in range(3))))
    anchors = local_rows[:: max(1, len(local_rows) // 260)]
    return coefficients, {
        "sampleCount": len(samples),
        "sCenter": s_center,
        "nCenter": n_center,
        "sScale": s_scale,
        "nScale": n_scale,
        "meanFitRgbError": sum(errors) / len(errors),
        "maximumFitRgbError": max(errors),
    }, anchors


def predict(
    coefficients: list[list[float]],
    fit: dict,
    s: float,
    n: float,
) -> list[float]:
    sn = max(-1.0, min(1.0, (s - fit["sCenter"]) / fit["sScale"]))
    nn = max(-1.0, min(1.0, (n - fit["nCenter"]) / fit["nScale"]))
    features = [1.0, sn, nn, nn * nn, sn * nn]
    return [
        sum(coefficients[channel][i] * features[i] for i in range(5))
        for channel in range(3)
    ]


def smooth_noise(seed: int) -> Image.Image:
    rng = random.Random(seed)
    small = Image.new("L", (64, 136), 128)
    data = small.load()
    for y in range(small.height):
        for x in range(small.width):
            data[x, y] = rng.randrange(74, 183)
    return small.resize((W, H), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(2.2))


def median(values: list[int], fallback: int) -> int:
    if not values:
        return fallback
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def estimate_line_color(
    source: Image.Image,
    visible: set[tuple[int, int]],
) -> tuple[int, int, int]:
    src = source.load()
    distance = edge_distance(visible)
    candidates = [
        src[x, y]
        for x, y in visible
        if distance.get((x, y), 99) <= 2 and sum(src[x, y]) / 3 < 205
    ]
    fallback = (164, 143, 137)
    return tuple(median([rgb[i] for rgb in candidates], fallback[i]) for i in range(3))


def nearest_anchor_rgb(
    s: float,
    n: float,
    anchors: list[tuple[float, float, tuple[int, int, int]]],
) -> tuple[float, float, float]:
    nearest = sorted(anchors, key=lambda row: (row[0] - s) ** 2 * 0.08 + (row[1] - n) ** 2)[:10]
    weighted = [0.0, 0.0, 0.0]
    total = 0.0
    for anchor_s, anchor_n, rgb in nearest:
        weight = 1.0 / (0.5 + (anchor_s - s) ** 2 * 0.08 + (anchor_n - n) ** 2)
        total += weight
        for channel in range(3):
            weighted[channel] += rgb[channel] * weight
    return tuple(value / total for value in weighted)


def build_material(
    layer: str,
    source: Image.Image,
    visible_mask: Image.Image,
    complete_mask: Image.Image,
    coordinate_frame,
    fit_visible_mask: Image.Image | None = None,
) -> tuple[Image.Image, dict]:
    geometry = points(complete_mask)
    visible = points(visible_mask)
    fit_visible = points(fit_visible_mask) if fit_visible_mask is not None else visible
    hidden = geometry - visible
    geometry_edge = edge_distance(geometry)
    seam_distance = distance_from_seed(geometry, visible)
    coefficients, fit, fit_anchors = fit_color_field(source, fit_visible, coordinate_frame, layer)
    _, _, seam_anchors = fit_color_field(source, visible, coordinate_frame, layer)
    line_color = estimate_line_color(source, fit_visible)
    noise = smooth_noise(SEEDS[layer]).load()
    src = source.load()
    result = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out = result.load()
    noise_strength = 2.3 if layer == "sleeve" else 1.6
    for x, y in hidden:
        s, n = local((x + 0.5, y + 0.5), coordinate_frame)
        rgb = predict(coefficients, fit, s, n)
        distance = seam_distance.get((x, y), 999)
        if distance <= 18:
            anchor = nearest_anchor_rgb(s, n, seam_anchors)
            blend = 0.82 * (1.0 - distance / 19.0) ** 2
            rgb = [
                rgb[channel] * (1.0 - blend) + anchor[channel] * blend
                for channel in range(3)
            ]
        noise_weight = min(1.0, distance / 9.0)
        texture = ((noise[x, y] - 128.0) / 34.0) * noise_strength * noise_weight
        rgb = [
            rgb[channel] + texture * factor
            for channel, factor in enumerate((1.0, 0.72, 0.48))
        ]
        edge = geometry_edge.get((x, y), 99)
        if edge == 1:
            mix = 0.42 if layer == "sleeve" else 0.34
            rgb = [
                line_color[channel] * mix + rgb[channel] * (1.0 - mix)
                for channel in range(3)
            ]
        elif edge == 2:
            rgb = [
                line_color[channel] * 0.12 + rgb[channel] * 0.88
                for channel in range(3)
            ]
        out[x, y] = tuple(max(0, min(255, round(value))) for value in rgb) + (255,)
    for x, y in visible:
        out[x, y] = src[x, y] + (255,)
    return result, {
        "geometryPixels": len(geometry),
        "visiblePixels": len(visible),
        "hiddenPixels": len(hidden),
        "lineRgb": line_color,
        "fit": fit,
    }


def patch_default_ownership(
    materials: dict[str, Image.Image],
    visible_masks: dict[str, Image.Image],
    source: Image.Image,
) -> int:
    source_pixels = source.load()
    changed = 0
    visible_union = Image.new("L", (W, H), 0)
    for mask in visible_masks.values():
        visible_union = ImageChops.lighter(visible_union, mask)
    union_points = points(visible_union)
    for x, y in union_points:
        top_layer = None
        for layer in DRAW_ORDER:
            if materials[layer].getpixel((x, y))[3]:
                top_layer = layer
        if top_layer is None:
            continue
        pixel = materials[top_layer].getpixel((x, y))
        target = source_pixels[x, y] + (255,)
        if pixel != target:
            materials[top_layer].putpixel((x, y), target)
            changed += 1
    return changed


def rgba_transform(
    image: Image.Image,
    angle_deg: float,
    rest_origin: tuple[float, float],
    current_origin: tuple[float, float],
) -> Image.Image:
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    ox, oy = rest_origin
    cx, cy = current_origin
    affine = (
        c,
        s,
        ox - c * cx - s * cy,
        -s,
        c,
        oy + s * cx - c * cy,
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


def rotate_vector(vector: tuple[float, float], angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    return (vector[0] * c - vector[1] * s, vector[0] * s + vector[1] * c)


def pose_materials(
    materials: dict[str, Image.Image],
    shoulder: tuple[float, float],
    elbow: tuple[float, float],
    wrist: tuple[float, float],
    shoulder_delta: float,
    elbow_delta: float,
    wrist_delta: float,
) -> dict[str, Image.Image]:
    upper_vector = (elbow[0] - shoulder[0], elbow[1] - shoulder[1])
    forearm_vector = (wrist[0] - elbow[0], wrist[1] - elbow[1])
    moved_upper = rotate_vector(upper_vector, shoulder_delta)
    moved_elbow = (shoulder[0] + moved_upper[0], shoulder[1] + moved_upper[1])
    moved_forearm = rotate_vector(forearm_vector, shoulder_delta + elbow_delta)
    moved_wrist = (moved_elbow[0] + moved_forearm[0], moved_elbow[1] + moved_forearm[1])
    return {
        "sleeve": rgba_transform(materials["sleeve"], shoulder_delta, shoulder, shoulder),
        "upper_arm": rgba_transform(materials["upper_arm"], shoulder_delta, shoulder, shoulder),
        "forearm_bracelet": rgba_transform(
            materials["forearm_bracelet"],
            shoulder_delta + elbow_delta,
            elbow,
            moved_elbow,
        ),
        "whole_hand": rgba_transform(
            materials["whole_hand"],
            shoulder_delta + elbow_delta + wrist_delta,
            wrist,
            moved_wrist,
        ),
    }


def composite(materials: dict[str, Image.Image], background=(248, 248, 248)) -> Image.Image:
    image = Image.new("RGBA", (W, H), background + (255,))
    for layer in DRAW_ORDER:
        image.alpha_composite(materials[layer])
    return image.convert("RGB")


def checker() -> Image.Image:
    image = Image.new("RGBA", (W, H), (238, 238, 238, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, H, 16):
        for x in range(0, W, 16):
            if (x // 16 + y // 16) % 2:
                draw.rectangle((x, y, x + 15, y + 15), fill=(202, 202, 202, 255))
    return image


def shifted(image: Image.Image, dx: int, dy: int) -> Image.Image:
    return image.transform(
        (W, H),
        Image.Transform.AFFINE,
        (1, 0, -dx, 0, 1, -dy),
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )


def scaled_crop(image: Image.Image, box: tuple[int, int, int, int], scale: int) -> Image.Image:
    crop = image.crop(box)
    return crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST)


def seam_metrics(
    material: Image.Image,
    visible_mask: Image.Image,
    complete_mask: Image.Image,
) -> dict:
    visible = points(visible_mask)
    hidden = points(complete_mask) - visible
    pixels_rgba = material.load()
    pairs = []
    for x, y in hidden:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (x + dx, y + dy)
            if neighbor in visible:
                a = pixels_rgba[x, y]
                b = pixels_rgba[neighbor[0], neighbor[1]]
                pairs.append(math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3))))
    hidden_luminance = [
        0.2126 * pixels_rgba[x, y][0]
        + 0.7152 * pixels_rgba[x, y][1]
        + 0.0722 * pixels_rgba[x, y][2]
        for x, y in hidden
    ]
    mean = sum(hidden_luminance) / max(1, len(hidden_luminance))
    stddev = math.sqrt(
        sum((value - mean) ** 2 for value in hidden_luminance)
        / max(1, len(hidden_luminance))
    )
    return {
        "adjacentPairCount": len(pairs),
        "meanRgbJump": sum(pairs) / max(1, len(pairs)),
        "maximumRgbJump": max(pairs) if pairs else 0.0,
        "hiddenLuminanceStdDev": stddev,
    }


def build_board(
    source: Image.Image,
    materials: dict[str, Image.Image],
    visible_masks: dict[str, Image.Image],
    hidden_masks: dict[str, Image.Image],
    metrics: dict,
    shoulder,
    elbow,
    wrist,
) -> None:
    board = Image.new("RGB", (2200, 1640), (239, 241, 245))
    draw = ImageDraw.Draw(board)
    draw.text((45, 28), "小星 V14｜袖口归属修正 + 完整纹理最小审查", font=font(40, True), fill=(25, 31, 42))
    draw.text(
        (47, 88),
        "袖口阴影带归还袖子；其余可见像素保持原稿 1:1，并补隐藏肩根、肘根与腕根",
        font=font(23),
        fill=(76, 84, 96),
    )
    crop = (50, 205, 205, 655)
    scale = 2
    source_crop = scaled_crop(source, crop, scale)
    board.paste(source_crop, (45, 155))

    reconstruction = composite(materials)
    board.paste(scaled_crop(reconstruction, crop, scale), (400, 155))

    displaced_canvas = checker()
    offsets = {
        "sleeve": (-38, -15),
        "upper_arm": (-12, 0),
        "forearm_bracelet": (22, 0),
        "whole_hand": (48, 15),
    }
    for layer in DRAW_ORDER:
        displaced_canvas.alpha_composite(shifted(materials[layer], *offsets[layer]))
    board.paste(
        scaled_crop(displaced_canvas.convert("RGB"), (10, 180, 265, 680), 2),
        (755, 155),
    )
    draw.text((45, 1080), "当前原稿", font=font(23, True), fill=(42, 49, 59))
    draw.text((400, 1080), "四臂层默认关系（未含躯干遮挡）", font=font(23, True), fill=(42, 49, 59))
    draw.text((755, 1080), "四层移开：检查隐藏纹理与轮廓", font=font(23, True), fill=(42, 49, 59))

    info_x = 1320
    draw.rounded_rectangle((info_x, 155, 2155, 810), radius=24, fill="white", outline=(204, 211, 220), width=2)
    draw.text((info_x + 30, 188), "请重点判断", font=font(30, True), fill=(25, 31, 42))
    questions = [
        "1. 袖内肩帽是否仍像同一件宽松 T 恤？",
        "2. 袖口阴影是否随袖子移开，裸露上臂不再残留白边？",
        "3. 隐藏上臂是否保持原稿肤色和细长比例？",
        "4. 肘根移开后是否无硬色块、圆补丁或断纹？",
        "5. 手链归属是否清楚，隐藏腕根是否自然？",
        "6. 整手移开后手指与唯一封闭负空间是否保持？",
        "7. 默认可见段与三处接缝是否保持身份且无露白？",
    ]
    for index, question in enumerate(questions):
        draw.text((info_x + 35, 255 + index * 67), question, font=font(22), fill=(48, 55, 66))
    draw.rounded_rectangle((info_x + 30, 720, 2120, 772), radius=13, fill=(221, 243, 227))
    draw.text(
        (info_x + 50, 730),
        "视觉结论：用户已确认当前纹理合适；允许进入 ArtMesh。",
        font=font(22, True),
        fill=(44, 112, 67),
    )

    draw.rounded_rectangle((45, 1140, 2155, 1590), radius=24, fill="white", outline=(204, 211, 220), width=2)
    draw.text((75, 1170), "接缝与隐藏区放大", font=font(28, True), fill=(25, 31, 42))
    seam_boxes = [
        ("肩 / 袖内", (130, 240, 190, 405)),
        ("肘", (125, 390, 175, 445)),
        ("腕 / 手链", (88, 505, 142, 555)),
    ]
    for index, (label, seam_box) in enumerate(seam_boxes):
        panel = scaled_crop(reconstruction, seam_box, 5)
        panel.thumbnail((560, 300))
        x = 75 + index * 680
        board.paste(panel, (x, 1230))
        draw.text((x, 1540), label, font=font(21, True), fill=(45, 52, 62))
    output = STAGE / "qa/V14-COMPLETE-TEXTURE-USER-REVIEW.zh-CN.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    board.save(output)


def main() -> None:
    freeze = verify_manifest(V13_FREEZE, V13)
    if not freeze["pass"]:
        raise RuntimeError("V13 freeze verification failed.")
    v13_manifest = json.loads(V13_FREEZE.read_text(encoding="utf-8"))
    v12_path = WORKBENCH / v13_manifest["upstreamFreeze"]["path"]
    v12_manifest = json.loads(v12_path.read_text(encoding="utf-8"))
    geometry = v12_manifest["frozenGeometry"]
    shoulder = tuple(float(value) for value in geometry["shoulder"])
    elbow = tuple(float(value) for value in geometry["elbow"])
    wrist = tuple(float(value) for value in geometry["wrist"])
    hand_end = (98.0, 585.0)
    frames = {
        "sleeve": frame(shoulder, (145.0, 382.0)),
        "upper_arm": frame(shoulder, elbow),
        "forearm_bracelet": frame(elbow, wrist),
        "whole_hand": frame(wrist, hand_end),
    }
    source = Image.open(SOURCE_COLOR).convert("RGB")
    visible_masks = {
        layer: load_mask(V13 / f"masks/visible/{layer}.png") for layer in LAYERS
    }
    complete_masks = {
        layer: load_mask(V13 / f"masks/complete/{layer}.png") for layer in LAYERS
    }
    # Downstream isolated-texture review exposed a semantic leak that the flat
    # V13 tint board did not: the sleeve-edge highlight/shadow band remained in
    # the upper-arm visible material. Preserve V13 byte-for-byte and supersede
    # only that ownership band here.
    cuff_band = binary(
        ImageChops.multiply(
            visible_masks["upper_arm"],
            visible_masks["sleeve"].filter(ImageFilter.MaxFilter(37)),
        )
    )
    cuff_band_pixels = count(cuff_band)
    visible_masks["upper_arm"] = binary(
        ImageChops.subtract(visible_masks["upper_arm"], cuff_band)
    )
    visible_masks["sleeve"] = binary(
        ImageChops.lighter(visible_masks["sleeve"], cuff_band)
    )
    complete_masks["sleeve"] = binary(
        ImageChops.lighter(complete_masks["sleeve"], cuff_band)
    )
    hidden_masks = {
        layer: binary(ImageChops.subtract(complete_masks[layer], visible_masks[layer]))
        for layer in LAYERS
    }
    corrected_mask_root = STAGE / "corrected-masks"
    for group, masks in (
        ("visible", visible_masks),
        ("complete", complete_masks),
        ("hidden", hidden_masks),
    ):
        directory = corrected_mask_root / group
        directory.mkdir(parents=True, exist_ok=True)
        for layer, mask in masks.items():
            image = Image.new("RGBA", (W, H), (255, 255, 255, 0))
            image.putalpha(mask)
            image.save(directory / f"{layer}.png")
    cuff_image = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    cuff_image.putalpha(cuff_band)
    cuff_image.save(corrected_mask_root / "cuff-shadow-band-reassigned-to-sleeve.png")
    materials = {}
    build_metrics = {}
    all_skin_visible = Image.new("L", (W, H), 0)
    for layer in ("upper_arm", "forearm_bracelet", "whole_hand"):
        all_skin_visible = ImageChops.lighter(all_skin_visible, visible_masks[layer])
    for layer in LAYERS:
        material, layer_metrics = build_material(
            layer,
            source,
            visible_masks[layer],
            complete_masks[layer],
            frames[layer],
            all_skin_visible if layer == "upper_arm" else None,
        )
        materials[layer] = material
        build_metrics[layer] = layer_metrics
    default_patch_pixels = patch_default_ownership(materials, visible_masks, source)

    material_dir = STAGE / "materials"
    material_dir.mkdir(parents=True, exist_ok=True)
    for layer, material in materials.items():
        material.save(material_dir / f"{layer}.png")

    source_pixels = source.load()
    material_metrics = {}
    all_pass = True
    for layer in LAYERS:
        visible = points(visible_masks[layer])
        complete = points(complete_masks[layer])
        alpha = points(materials[layer].getchannel("A"))
        visible_rgb_diff = sum(
            materials[layer].getpixel((x, y))[:3] != source_pixels[x, y]
            for x, y in visible
        )
        alpha_difference = len(alpha ^ complete)
        seams = seam_metrics(materials[layer], visible_masks[layer], complete_masks[layer])
        layer_pass = visible_rgb_diff == 0 and alpha_difference == 0
        all_pass = all_pass and layer_pass
        material_metrics[layer] = {
            **build_metrics[layer],
            **seams,
            "visibleRgbDifferencePixels": visible_rgb_diff,
            "alphaGeometryDifferencePixels": alpha_difference,
            "pass": layer_pass,
        }

    reconstruction = composite(materials)
    reconstruction_pixels = reconstruction.load()
    visible_union = Image.new("L", (W, H), 0)
    for mask in visible_masks.values():
        visible_union = ImageChops.lighter(visible_union, mask)
    default_rgb_difference = sum(
        reconstruction_pixels[x, y] != source_pixels[x, y]
        for x, y in points(visible_union)
    )

    frames_rgba = []
    minimum_alpha_overlaps = {
        "sleeveUpper": 10**9,
        "upperForearm": 10**9,
        "forearmHand": 10**9,
    }
    motion_failures = 0
    first_frame = None
    last_frame = None
    for index in range(41):
        reflected = index if index <= 20 else 40 - index
        progress = 0.5 * (1 - math.cos(math.pi * reflected / 20))
        posed = pose_materials(
            materials,
            shoulder,
            elbow,
            wrist,
            8.0 * progress,
            12.0 * progress,
            12.0 * progress,
        )
        masks = {layer: binary(posed[layer].getchannel("A"), 64) for layer in LAYERS}
        overlaps = {
            "sleeveUpper": count(ImageChops.multiply(masks["sleeve"], masks["upper_arm"])),
            "upperForearm": count(ImageChops.multiply(masks["upper_arm"], masks["forearm_bracelet"])),
            "forearmHand": count(ImageChops.multiply(masks["forearm_bracelet"], masks["whole_hand"])),
        }
        for key, value in overlaps.items():
            minimum_alpha_overlaps[key] = min(minimum_alpha_overlaps[key], value)
        if min(overlaps.values()) <= 0:
            motion_failures += 1
        rendered = composite(posed)
        crop = scaled_crop(rendered, (80, 225, 195, 640), 2)
        frames_rgba.append(crop)
        if index == 0:
            first_frame = rendered
        if index == 40:
            last_frame = rendered
    return_difference = sum(
        a != b
        for a, b in zip(
            first_frame.get_flattened_data(),
            last_frame.get_flattened_data(),
        )
    )
    gif_path = STAGE / "qa/V14-TEXTURE-SEAM-SLOW-SCAN.gif"
    gif_path.parent.mkdir(parents=True, exist_ok=True)
    frames_rgba[0].save(
        gif_path,
        save_all=True,
        append_images=frames_rgba[1:],
        duration=90,
        loop=0,
        disposal=2,
    )

    engineering_pass = (
        all_pass
        and default_rgb_difference == 0
        and min(minimum_alpha_overlaps.values()) > 0
        and motion_failures == 0
        and return_difference == 0
    )
    report = {
        "schemaVersion": 1,
        "checkpoint": "V14 complete textures for screen-left arm",
        "status": (
            "user_visual_approved_ready_to_freeze"
            if engineering_pass
            else "engineering_fail_stop_at_earliest_failure"
        ),
        "decisionOwner": "user",
        "scope": "four complete textured layers inside frozen V13 masks",
        "inputIntegrity": {
            "v13Freeze": freeze,
            "sourceColor": {
                "path": SOURCE_COLOR.relative_to(WORKBENCH).as_posix(),
                "sha256": sha256(SOURCE_COLOR),
            },
            "externalOrCloudGenerationUsed": False,
            "rejectedV5V15MasksUsed": False,
            "screenRightPixelsMirrored": False,
        },
        "v13BoundaryCorrection": {
            "reason": "isolated textured upper-arm review exposed sleeve-edge highlight/shadow pixels remaining on the arm when the sleeve moved away",
            "v13FrozenArtifactsModified": False,
            "supersededScope": "cuff-edge ownership only",
            "pixelsReassignedFromUpperArmToSleeve": cuff_band_pixels,
            "correctedMaskRoot": "corrected-masks",
            "requiresFreshUserVisualApproval": True,
        },
        "method": {
            "type": "deterministic local color-field continuation",
            "rules": [
                "copy every approved visible source pixel 1:1",
                "fit a bounded low-order field in each approved layer coordinate frame",
                "blend hidden seam pixels toward nearby visible anchors",
                "add only low-amplitude deterministic nonperiodic variation away from seams",
                "continue an estimated source outline color along hidden complete boundaries",
                "never write alpha outside frozen V13 complete masks",
            ],
            "defaultOwnershipPatchPixels": default_patch_pixels,
        },
        "materials": material_metrics,
        "defaultRecomposition": {
            "visibleUnionPixels": count(visible_union),
            "sourceRgbDifferencePixels": default_rgb_difference,
        },
        "motionStress": {
            "sampleCount": 41,
            "minimumAdjacentAlphaOverlapPixels": minimum_alpha_overlaps,
            "failureCount": motion_failures,
            "returnDifferencePixels": return_difference,
            "slowScan": "qa/V14-TEXTURE-SEAM-SLOW-SCAN.gif",
        },
        "engineeringPass": engineering_pass,
        "userVisualApproval": {
            "status": "approved",
            "decisionText": "合适，请继续任务",
            "reviewBoard": "qa/V14-COMPLETE-TEXTURE-USER-REVIEW.zh-CN.png",
            "engineeringChecksDoNotReplaceVisualApproval": True,
        },
        "explicitlyNotPerformed": [
            "PSD",
            "mesh",
            "nodes",
            "continuous parameter motion",
            "Physics",
            "Runtime",
            "upstream frozen-file modification",
        ],
        "nextGateIfApproved": "mesh construction for the four approved textured layers",
    }
    write_json(STAGE / "audit/v14-complete-texture-engineering-report.json", report)
    build_board(
        source,
        materials,
        visible_masks,
        hidden_masks,
        material_metrics,
        shoulder,
        elbow,
        wrist,
    )
    markdown = f"""# V14 画面左侧手臂完整纹理

状态：`{report['status']}`。用户已确认当前纹理与袖口归属修正版合适。

- V13 冻结输入：{freeze['matchedArtifacts']}/{freeze['artifactCount']}，原冻结工件未修改；
- 纹理移开审查发现并修正袖口归属：{cuff_band_pixels} px 从上臂归还袖子；
- 四层可见原稿 RGB 差：均为 0；
- 四层 alpha 与 V13 冻结完整遮罩差：均为 0；
- 默认可见区域重组 RGB 差：{default_rgb_difference}；
- 41 样本相邻最小 alpha 重叠：袖/上臂 {minimum_alpha_overlaps['sleeveUpper']}、
  上臂/前臂 {minimum_alpha_overlaps['upperForearm']}、前臂/手
  {minimum_alpha_overlaps['forearmHand']}；
- 运动失败：{motion_failures}；回程差：{return_difference}。

用户已批准 `qa/V14-COMPLETE-TEXTURE-USER-REVIEW.zh-CN.png` 和
`qa/V14-TEXTURE-SEAM-SLOW-SCAN.gif`，允许进入 ArtMesh。节点、主动参数运动、
Physics 与 Runtime 仍未授权提前进行。
"""
    (STAGE / "audit/V14-COMPLETE-TEXTURE-REPORT.zh-CN.md").write_text(markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "engineeringPass": engineering_pass,
                "defaultRgbDifferencePixels": default_rgb_difference,
                "minimumAdjacentAlphaOverlapPixels": minimum_alpha_overlaps,
                "motionFailureCount": motion_failures,
                "returnDifferencePixels": return_difference,
                "reviewBoard": "qa/V14-COMPLETE-TEXTURE-USER-REVIEW.zh-CN.png",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not engineering_pass:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
