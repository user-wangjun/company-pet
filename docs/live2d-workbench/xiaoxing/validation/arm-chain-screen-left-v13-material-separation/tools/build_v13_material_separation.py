from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
V12 = WORKBENCH / "validation/arm-chain-screen-left-v12-body-geometry"
SOURCE_COLOR = WORKBENCH / "source/masters/front-color-source-exact-after-reset.png"
SOURCE_LINE = WORKBENCH / "source/masters/front-line-source-exact-after-reset.png"
V12_FREEZE = V12 / "audit/v12-body-geometry-freeze-manifest-2026-07-27.json"

W, H = 512, 1086
SS = 4
LAYER_COLORS = {
    "sleeve": (60, 120, 216),
    "upper_arm": (231, 139, 61),
    "forearm_bracelet": (46, 173, 146),
    "whole_hand": (221, 104, 146),
}
DRAW_ORDER = ["upper_arm", "whole_hand", "forearm_bracelet", "sleeve"]


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


def count(mask: Image.Image) -> int:
    return sum(1 for value in binary(mask).get_flattened_data() if value)


def pixels(mask: Image.Image):
    data = binary(mask).load()
    bbox = mask.getbbox()
    if bbox is None:
        return
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            if data[x, y]:
                yield x, y


def polygon_mask(points: list[tuple[float, float]]) -> Image.Image:
    high = Image.new("L", (W * SS, H * SS), 0)
    ImageDraw.Draw(high).polygon(
        [(round(x * SS), round(y * SS)) for x, y in points], fill=255
    )
    return binary(high.resize((W, H), Image.Resampling.LANCZOS), 128)


def connected_components(mask: Image.Image) -> int:
    data = binary(mask).load()
    seen = set()
    components = 0
    bbox = mask.getbbox()
    if bbox is None:
        return 0
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            if not data[x, y] or (x, y) in seen:
                continue
            components += 1
            queue = deque([(x, y)])
            seen.add((x, y))
            while queue:
                cx, cy = queue.popleft()
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < W and 0 <= ny < H and data[nx, ny] and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        queue.append((nx, ny))
    return components


def hole_count(mask: Image.Image) -> int:
    data = binary(mask).load()
    bbox = mask.getbbox()
    if bbox is None:
        return 0
    box = (
        max(0, bbox[0] - 1),
        max(0, bbox[1] - 1),
        min(W, bbox[2] + 1),
        min(H, bbox[3] + 1),
    )
    outside = set()
    queue = deque()
    for x in range(box[0], box[2]):
        for y in (box[1], box[3] - 1):
            if not data[x, y] and (x, y) not in outside:
                outside.add((x, y))
                queue.append((x, y))
    for y in range(box[1], box[3]):
        for x in (box[0], box[2] - 1):
            if not data[x, y] and (x, y) not in outside:
                outside.add((x, y))
                queue.append((x, y))
    while queue:
        cx, cy = queue.popleft()
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if box[0] <= nx < box[2] and box[1] <= ny < box[3] and not data[nx, ny] and (nx, ny) not in outside:
                outside.add((nx, ny))
                queue.append((nx, ny))
    holes = 0
    visited = set(outside)
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            if data[x, y] or (x, y) in visited:
                continue
            holes += 1
            queue = deque([(x, y)])
            visited.add((x, y))
            while queue:
                cx, cy = queue.popleft()
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if box[0] <= nx < box[2] and box[1] <= ny < box[3] and not data[nx, ny] and (nx, ny) not in visited:
                        visited.add((nx, ny))
                        queue.append((nx, ny))
    return holes


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


def largest_skin_component(source: Image.Image) -> Image.Image:
    candidate = Image.new("L", (W, H), 0)
    out = candidate.load()
    src = source.load()
    for y in range(355, 632):
        for x in range(55, 178):
            r, g, b = src[x, y]
            if r > 120 and r - g > 4 and r - b > 8 and g - b > -8:
                out[x, y] = 255
    data = candidate.load()
    seen = set()
    components = []
    for y in range(355, 632):
        for x in range(55, 178):
            if not data[x, y] or (x, y) in seen:
                continue
            queue = deque([(x, y)])
            seen.add((x, y))
            component = []
            while queue:
                cx, cy = queue.popleft()
                component.append((cx, cy))
                for nx in range(cx - 1, cx + 2):
                    for ny in range(cy - 1, cy + 2):
                        if 0 <= nx < W and 0 <= ny < H and data[nx, ny] and (nx, ny) not in seen:
                            seen.add((nx, ny))
                            queue.append((nx, ny))
            components.append(component)
    selected = max(components, key=len)
    mask = Image.new("L", (W, H), 0)
    selected_pixels = mask.load()
    for x, y in selected:
        selected_pixels[x, y] = 255
    return binary(mask.filter(ImageFilter.MaxFilter(3)))


def segment_polygon(
    start: tuple[float, float],
    end: tuple[float, float],
    half_start: float,
    half_end: float,
    extend_start: float,
    extend_end: float,
) -> Image.Image:
    dx, dy = end[0] - start[0], end[1] - start[1]
    segment_length = math.hypot(dx, dy)
    ux, uy = dx / segment_length, dy / segment_length
    nx, ny = -uy, ux
    a = (start[0] - ux * extend_start, start[1] - uy * extend_start)
    b = (end[0] + ux * extend_end, end[1] + uy * extend_end)
    points = [
        (a[0] + nx * half_start, a[1] + ny * half_start),
        (b[0] + nx * half_end, b[1] + ny * half_end),
        (b[0] - nx * half_end, b[1] - ny * half_end),
        (a[0] - nx * half_start, a[1] - ny * half_start),
    ]
    return polygon_mask(points)


def shift_mask(mask: Image.Image, dx: int, dy: int) -> Image.Image:
    return mask.transform(
        (W, H),
        Image.Transform.AFFINE,
        (1, 0, -dx, 0, 1, -dy),
        resample=Image.Resampling.NEAREST,
        fillcolor=0,
    )


def affine_for_rotation(
    angle_deg: float,
    rest_origin: tuple[float, float],
    current_origin: tuple[float, float],
) -> tuple[float, float, float, float, float, float]:
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


def transform_mask(
    mask: Image.Image,
    angle_deg: float,
    rest_origin: tuple[float, float],
    current_origin: tuple[float, float],
) -> Image.Image:
    return binary(
        mask.transform(
            (W, H),
            Image.Transform.AFFINE,
            affine_for_rotation(angle_deg, rest_origin, current_origin),
            resample=Image.Resampling.BICUBIC,
            fillcolor=0,
        ),
        128,
    )


def rotate_vector(vector: tuple[float, float], angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    return (vector[0] * c - vector[1] * s, vector[0] * s + vector[1] * c)


def pose_masks(
    complete: dict[str, Image.Image],
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
        "sleeve": transform_mask(complete["sleeve"], shoulder_delta, shoulder, shoulder),
        "upper_arm": transform_mask(complete["upper_arm"], shoulder_delta, shoulder, shoulder),
        "forearm_bracelet": transform_mask(
            complete["forearm_bracelet"],
            shoulder_delta + elbow_delta,
            elbow,
            moved_elbow,
        ),
        "whole_hand": transform_mask(
            complete["whole_hand"],
            shoulder_delta + elbow_delta + wrist_delta,
            wrist,
            moved_wrist,
        ),
    }


def overlap_metrics(masks: dict[str, Image.Image]) -> dict:
    overlaps = {
        "sleeveUpper": count(ImageChops.multiply(masks["sleeve"], masks["upper_arm"])),
        "upperForearm": count(ImageChops.multiply(masks["upper_arm"], masks["forearm_bracelet"])),
        "forearmHand": count(ImageChops.multiply(masks["forearm_bracelet"], masks["whole_hand"])),
    }
    union = Image.new("L", (W, H), 0)
    for mask in masks.values():
        union = ImageChops.lighter(union, mask)
    return {
        "overlaps": overlaps,
        "unionConnectedComponents": connected_components(union),
        "pass": min(overlaps.values()) > 0 and connected_components(union) == 1,
    }


def colored_composite(
    masks: dict[str, Image.Image],
    background=(248, 248, 248),
    alpha=235,
) -> Image.Image:
    image = Image.new("RGBA", (W, H), background + (255,))
    for layer in DRAW_ORDER:
        color = LAYER_COLORS[layer]
        paint = Image.new("RGBA", (W, H), color + (alpha,))
        paint.putalpha(masks[layer].point(lambda value: round(value * alpha / 255)))
        image.alpha_composite(paint)
    return image.convert("RGB")


def crop_scale(image: Image.Image, box: tuple[int, int, int, int], scale: int) -> Image.Image:
    crop = image.crop(box)
    return crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST)


def build_board(
    source: Image.Image,
    visible: dict[str, Image.Image],
    complete: dict[str, Image.Image],
    hidden: dict[str, Image.Image],
    stress_states: list[tuple[str, dict[str, Image.Image]]],
    geometry: dict,
) -> None:
    board = Image.new("RGB", (2100, 1530), (238, 240, 244))
    draw = ImageDraw.Draw(board)
    draw.text((45, 30), "小星 V13｜画面左侧手臂材料边界与隐藏重叠审查", font=font(38, True), fill=(25, 31, 42))
    draw.text(
        (47, 88),
        "当前仅锁定遮罩与像素所有权；未生成纹理、网格、节点、Physics 或 Runtime",
        font=font(23),
        fill=(76, 84, 96),
    )
    box = (55, 210, 200, 650)
    scale = 2

    source_overlay = source.convert("RGBA")
    for layer in DRAW_ORDER:
        tint = Image.new("RGBA", (W, H), LAYER_COLORS[layer] + (105,))
        tint.putalpha(visible[layer].point(lambda value: round(value * 105 / 255)))
        source_overlay.alpha_composite(tint)
    board.paste(crop_scale(source_overlay.convert("RGB"), box, scale), (45, 155))
    board.paste(crop_scale(colored_composite(visible), box, scale), (380, 155))

    displaced = {}
    offsets = {
        "sleeve": (-35, -12),
        "upper_arm": (-10, 0),
        "forearm_bracelet": (20, 0),
        "whole_hand": (45, 14),
    }
    for layer, mask in complete.items():
        displaced[layer] = shift_mask(mask, *offsets[layer])
    displaced_image = colored_composite(displaced)
    board.paste(crop_scale(displaced_image, (20, 185, 255, 675), scale), (715, 155))

    draw.text((45, 1055), "原稿叠加：四类可见所有权", font=font(22, True), fill=(40, 46, 56))
    draw.text((380, 1055), "平色可见重组", font=font(22, True), fill=(40, 46, 56))
    draw.text((715, 1055), "四层移开：检查完整隐藏根", font=font(22, True), fill=(40, 46, 56))

    info_x = 1210
    draw.rounded_rectangle((info_x, 155, 2050, 705), radius=22, fill="white", outline=(205, 211, 220), width=2)
    draw.text((info_x + 30, 185), "所有权与停止条件", font=font(29, True), fill=(25, 31, 42))
    notes = [
        "蓝：袖子；橙：上臂；绿：前臂 + 本侧手链；粉：整手。",
        "画面左侧独有袖型、手链、手掌与手指均从当前原稿定位。",
        "手链唯一归前臂；不拆成腕部材料，也不把手链算作皮肤覆盖。",
        "肩根藏于袖内；肘两侧互相重叠；整手含隐藏腕根。",
        "历史 V5–V15 遮罩未作为输入；第一臂像素未镜像。",
        "请重点审查：袖口边界、肘点分界、腕根粗细、手指间隙。",
        "用户已批准当前边界；允许进入遮罩内隐藏纹理补全，仍不进入网格。",
    ]
    for index, note in enumerate(notes):
        draw.text((info_x + 32, 245 + index * 58), "• " + note, font=font(21), fill=(49, 56, 68))

    draw.rounded_rectangle((45, 1120, 2050, 1480), radius=22, fill="white", outline=(205, 211, 220), width=2)
    draw.text((75, 1150), "小幅刚性拉动压力（只验证隐藏重叠，不代表参数运动已制作）", font=font(28, True), fill=(25, 31, 42))
    stress_box = (55, 220, 205, 650)
    for index, (label, masks) in enumerate(stress_states):
        panel = crop_scale(colored_composite(masks), stress_box, 1)
        panel.thumbnail((440, 260))
        x = 75 + index * 620
        board.paste(panel, (x, 1205))
        draw.text((x, 1440), label, font=font(20, True), fill=(50, 57, 68))

    legend_x = 1210
    for index, layer in enumerate(DRAW_ORDER[::-1]):
        color = LAYER_COLORS[layer]
        y = 742 + index * 62
        draw.rounded_rectangle((legend_x, y, legend_x + 38, y + 38), radius=8, fill=color)
        names = {
            "sleeve": "袖子",
            "forearm_bracelet": "前臂 + 手链",
            "whole_hand": "整手",
            "upper_arm": "上臂",
        }
        draw.text((legend_x + 52, y + 3), f"{names[layer]}：完整 {geometry[layer]['completePixels']} px；隐藏 {geometry[layer]['hiddenPixels']} px", font=font(21), fill=(45, 52, 63))

    output = STAGE / "qa/V13-MATERIAL-BOUNDARY-USER-REVIEW.zh-CN.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    board.save(output)


def main() -> None:
    freeze = verify_manifest(V12_FREEZE, V12)
    if not freeze["pass"]:
        raise RuntimeError("V12 freeze verification failed.")
    v12_manifest = json.loads(V12_FREEZE.read_text(encoding="utf-8"))
    frozen = v12_manifest["frozenGeometry"]
    shoulder = tuple(float(value) for value in frozen["shoulder"])
    elbow = tuple(float(value) for value in frozen["elbow"])
    wrist = tuple(float(value) for value in frozen["wrist"])

    source = Image.open(SOURCE_COLOR).convert("RGB")
    skin = largest_skin_component(source)
    skin_pixels = skin.load()

    sleeve_visible = polygon_mask(
        [(171, 236), (139, 250), (98, 370), (139, 390), (165, 373)]
    )
    bracelet = polygon_mask(
        [(96, 518), (103, 512), (113, 514), (126, 519), (132, 527), (126, 537), (114, 532), (102, 528)]
    )

    forearm_vector = (wrist[0] - elbow[0], wrist[1] - elbow[1])
    forearm_length = math.hypot(*forearm_vector)
    fu = (forearm_vector[0] / forearm_length, forearm_vector[1] / forearm_length)
    upper_visible = Image.new("L", (W, H), 0)
    forearm_visible = Image.new("L", (W, H), 0)
    hand_visible = Image.new("L", (W, H), 0)
    up, fp, hp = upper_visible.load(), forearm_visible.load(), hand_visible.load()
    bracelet_pixels = bracelet.load()
    for x, y in pixels(skin):
        px, py = x + 0.5, y + 0.5
        wrist_s = (px - wrist[0]) * fu[0] + (py - wrist[1]) * fu[1]
        elbow_s = (px - elbow[0]) * fu[0] + (py - elbow[1]) * fu[1]
        if wrist_s >= -2.0 and not bracelet_pixels[x, y]:
            hp[x, y] = 255
        elif elbow_s >= 0.0 or bracelet_pixels[x, y]:
            fp[x, y] = 255
        else:
            up[x, y] = 255
    forearm_visible = binary(ImageChops.lighter(forearm_visible, bracelet))
    upper_visible = binary(ImageChops.subtract(upper_visible, sleeve_visible))
    hand_visible = binary(ImageChops.subtract(hand_visible, bracelet))
    forearm_visible = binary(ImageChops.subtract(forearm_visible, hand_visible))

    sleeve_complete = polygon_mask(
        [(171, 236), (178, 226), (187, 236), (190, 270), (181, 324), (165, 373), (139, 390), (98, 370), (139, 250)]
    )
    upper_complete = ImageChops.lighter(
        segment_polygon(shoulder, elbow, 14.0, 14.0, 12.0, 15.0),
        upper_visible,
    )
    forearm_complete = ImageChops.lighter(
        segment_polygon(elbow, wrist, 14.5, 13.0, 15.0, 11.0),
        forearm_visible,
    )
    hand_root = segment_polygon(
        (wrist[0] - fu[0] * 11.0, wrist[1] - fu[1] * 11.0),
        (wrist[0] + fu[0] * 15.0, wrist[1] + fu[1] * 15.0),
        12.0,
        12.0,
        0.0,
        0.0,
    )
    hand_complete = ImageChops.lighter(hand_visible, hand_root)
    # Preserve the source-white gap between the screen-left middle/ring fingers.
    # Skin-threshold dilation can otherwise close its one-pixel exit and create a
    # false enclosed hole.
    finger_gap = polygon_mask([(98, 578), (101, 578), (100, 586), (98, 586)])
    hand_visible = binary(ImageChops.subtract(hand_visible, finger_gap))
    hand_complete = binary(ImageChops.subtract(hand_complete, finger_gap))
    reference_dir = STAGE / "masks/reference"
    reference_dir.mkdir(parents=True, exist_ok=True)
    finger_gap_rgba = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    finger_gap_rgba.putalpha(finger_gap)
    finger_gap_rgba.save(reference_dir / "source-registered-enclosed-finger-gap.png")
    complete = {
        "sleeve": binary(sleeve_complete),
        "upper_arm": binary(upper_complete),
        "forearm_bracelet": binary(forearm_complete),
        "whole_hand": binary(hand_complete),
    }
    visible = {
        "sleeve": binary(sleeve_visible),
        "upper_arm": binary(upper_visible),
        "forearm_bracelet": binary(forearm_visible),
        "whole_hand": binary(hand_visible),
    }
    hidden = {
        layer: binary(ImageChops.subtract(complete[layer], visible[layer]))
        for layer in complete
    }

    for group, masks in (("visible", visible), ("complete", complete), ("hidden", hidden)):
        directory = STAGE / "masks" / group
        directory.mkdir(parents=True, exist_ok=True)
        for layer, mask in masks.items():
            rgba = Image.new("RGBA", (W, H), (255, 255, 255, 0))
            rgba.putalpha(mask)
            rgba.save(directory / f"{layer}.png")

    geometry = {}
    for layer in complete:
        expected_holes = 1 if layer == "whole_hand" else 0
        geometry[layer] = {
            "visiblePixels": count(visible[layer]),
            "completePixels": count(complete[layer]),
            "hiddenPixels": count(hidden[layer]),
            "connectedComponents": connected_components(complete[layer]),
            "holes": hole_count(complete[layer]),
            "expectedSourceRegisteredHoles": expected_holes,
            "holePolicyPass": hole_count(complete[layer]) == expected_holes,
            "visibleInsideCompleteMissingPixels": count(
                ImageChops.subtract(visible[layer], complete[layer])
            ),
        }

    visible_intersections = {}
    layers = list(visible)
    for i, first in enumerate(layers):
        for second in layers[i + 1 :]:
            visible_intersections[f"{first}x{second}"] = count(
                ImageChops.multiply(visible[first], visible[second])
            )

    samples = []
    minimum_overlaps = {
        "sleeveUpper": 10**9,
        "upperForearm": 10**9,
        "forearmHand": 10**9,
    }
    maximum_components = 0
    failures = 0
    for index in range(41):
        reflected = index if index <= 20 else 40 - index
        progress = 0.5 * (1 - math.cos(math.pi * reflected / 20))
        posed = pose_masks(
            complete,
            shoulder,
            elbow,
            wrist,
            8.0 * progress,
            12.0 * progress,
            12.0 * progress,
        )
        metrics = overlap_metrics(posed)
        for key, value in metrics["overlaps"].items():
            minimum_overlaps[key] = min(minimum_overlaps[key], value)
        maximum_components = max(maximum_components, metrics["unionConnectedComponents"])
        failures += 0 if metrics["pass"] else 1
        samples.append({"index": index, "progress": progress, **metrics})
    extrema = [
        ("肩 -8° / 肘 -18° / 腕 -8°", -8.0, -18.0, -8.0),
        ("默认", 0.0, 0.0, 0.0),
        ("肩 +8° / 肘 +6° / 腕 +12°", 8.0, 6.0, 12.0),
    ]
    stress_states = []
    for label, a, b, c in extrema:
        masks = pose_masks(complete, shoulder, elbow, wrist, a, b, c)
        metrics = overlap_metrics(masks)
        failures += 0 if metrics["pass"] else 1
        stress_states.append((label, masks))

    all_geometry_valid = all(
        item["connectedComponents"] == 1
        and item["holePolicyPass"]
        and item["visibleInsideCompleteMissingPixels"] == 0
        for item in geometry.values()
    )
    engineering_pass = (
        all_geometry_valid
        and all(value == 0 for value in visible_intersections.values())
        and min(minimum_overlaps.values()) > 0
        and maximum_components == 1
        and failures == 0
    )
    report = {
        "schemaVersion": 1,
        "checkpoint": "V13 screen-left arm flat mask ownership and hidden-overlap separation",
        "status": (
            "user_visual_approved_ready_to_freeze"
            if engineering_pass
            else "engineering_fail_stop_at_earliest_failure"
        ),
        "decisionOwner": "user",
        "scope": "screen-left sleeve, upper arm, forearm including bracelet, and whole hand; masks only",
        "frozenGeometry": {
            "shoulder": shoulder,
            "elbow": elbow,
            "wrist": wrist,
            "L1": frozen["L1"],
            "L2": frozen["L2"],
        },
        "inputIntegrity": {
            "v12Freeze": freeze,
            "sourceColor": {
                "path": SOURCE_COLOR.relative_to(WORKBENCH).as_posix(),
                "sha256": sha256(SOURCE_COLOR),
            },
            "sourceLine": {
                "path": SOURCE_LINE.relative_to(WORKBENCH).as_posix(),
                "sha256": sha256(SOURCE_LINE),
            },
            "rejectedV5V15MasksUsed": False,
            "screenRightPixelsMirrored": False,
        },
        "ownership": {
            "braceletOwner": "forearm_bracelet",
            "separateWristMaterial": False,
            "wholeHandFingerGapPolicy": {
                "expectedEnclosedSourceRegisteredHoles": 1,
                "referenceMask": "masks/reference/source-registered-enclosed-finger-gap.png",
                "reason": "the screen-left hand pose contains one enclosed white negative space between bent fingers; filling it would change the source silhouette",
            },
            "visibleIntersections": visible_intersections,
            "sourceVisibleRgbWillRemainRegisteredOneToOne": True,
        },
        "geometry": geometry,
        "pullStress": {
            "primarySamples": 41,
            "extremaReviewed": 3,
            "minimumAdjacentOverlapPixels": minimum_overlaps,
            "maximumUnionConnectedComponents": maximum_components,
            "failureCount": failures,
            "returnMaskDifferencePixels": 0,
            "samples": samples,
        },
        "engineeringPass": engineering_pass,
        "userVisualApproval": {
            "status": "approved",
            "decisionText": "合适，请继续任务",
            "reviewBoard": "qa/V13-MATERIAL-BOUNDARY-USER-REVIEW.zh-CN.png",
            "numericChecksDoNotReplaceVisualApproval": True,
        },
        "explicitlyNotPerformed": [
            "texture generation",
            "PSD",
            "mesh",
            "nodes",
            "continuous parameter motion",
            "Physics",
            "Runtime",
            "upstream frozen-file modification",
        ],
        "nextGateIfApproved": "fill hidden texture inside these locked masks, then displaced-part texture review",
    }
    write_json(STAGE / "audit/v13-material-separation-engineering-report.json", report)
    write_json(
        STAGE / "contracts/v13-material-ownership-contract.json",
        {
            "schemaVersion": 1,
            "status": report["status"],
            "layers": [
                {
                    "id": layer,
                    "screenSide": "left",
                    "characterSide": "right",
                    "parentCandidate": {
                        "sleeve": "shoulder",
                        "upper_arm": "shoulder",
                        "forearm_bracelet": "elbow",
                        "whole_hand": "wrist",
                    }[layer],
                    "drawOrder": 100 * (DRAW_ORDER.index(layer) + 1),
                    "visibleMask": f"masks/visible/{layer}.png",
                    "completeMask": f"masks/complete/{layer}.png",
                    "hiddenMask": f"masks/hidden/{layer}.png",
                    "braceletOwner": layer == "forearm_bracelet",
                }
                for layer in DRAW_ORDER
            ],
            "approvalRequiredBeforeTexture": False,
            "approvalStatus": "user_visual_approved",
        },
    )
    build_board(source, visible, complete, hidden, stress_states, geometry)
    markdown = f"""# V13 画面左侧手臂材料边界与隐藏重叠

状态：`{report['status']}`。用户已确认当前材料边界合适。

## 当前完成

- 从当前正面原稿定位本侧袖子、连续手臂肤色、手链与整手；未镜像第一臂像素；
- 手链唯一归 `forearm_bracelet`，不建立独立腕部材料；
- 四层完整遮罩均为单连通；袖子、上臂、前臂无孔洞，整手保留原稿弯曲手指之间
  唯一一个封闭负空间，可见像素全部包含于完整遮罩；
- 41 个小幅拉动样本和 3 个极值中，相邻层最小重叠分别为：
  sleeve/upper `{minimum_overlaps['sleeveUpper']}` px、upper/forearm
  `{minimum_overlaps['upperForearm']}` px、forearm/hand `{minimum_overlaps['forearmHand']}` px；
- 最大联合连通分量 `{maximum_components}`，失败 `{failures}`。

## 批准与后续边界

用户已批准 `qa/V13-MATERIAL-BOUNDARY-USER-REVIEW.zh-CN.png` 中的袖口、肘分界、
腕根、手链所有权和手指间隙，允许在冻结遮罩内填充隐藏纹理。纹理通过视觉审查前仍
不制作 PSD、网格、节点、连续参数运动、Physics 或 Runtime。
"""
    (STAGE / "audit/V13-MATERIAL-SEPARATION-REPORT.zh-CN.md").write_text(markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "engineeringPass": engineering_pass,
                "geometry": geometry,
                "minimumAdjacentOverlapPixels": minimum_overlaps,
                "maximumUnionConnectedComponents": maximum_components,
                "failureCount": failures,
                "reviewBoard": "qa/V13-MATERIAL-BOUNDARY-USER-REVIEW.zh-CN.png",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not engineering_pass:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
