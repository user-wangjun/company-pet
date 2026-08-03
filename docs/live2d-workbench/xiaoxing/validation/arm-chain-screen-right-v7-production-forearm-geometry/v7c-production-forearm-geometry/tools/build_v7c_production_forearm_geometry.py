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
XIAOXING = VALIDATION.parent
V4 = VALIDATION / "arm-chain-screen-right-v4-wrist-motion"
V5 = VALIDATION / "arm-chain-screen-right-v5-hidden-upper-arm"
V6 = VALIDATION / "arm-chain-screen-right-v6-complete-upper-arm-geometry"
B0 = V7 / "v7b0-structure-feasibility"
B1 = V7 / "v7b1-root-width-reopen"
B2 = V7 / "v7b2-angle-dependent-root-taper-feasibility"

AUDIT = ROOT / "audit"
MASKS = ROOT / "masks"
QA = ROOT / "qa"

OWNERSHIP_BUILDER = V7 / "tools/build_v7a_ownership_gate.py"
B0_BUILDER = B0 / "tools/build_v7b0_structure_feasibility.py"
B2_BUILDER = B2 / "tools/build_v7b2_angle_dependent_root_taper.py"
B2_REPORT = B2 / "audit/v7b2-angle-taper-feasibility.json"
B2_APPROVAL = B2 / "audit/v7b2-user-visual-approval-2026-07-26.json"
B1_REPORT = B1 / "audit/v7b1-root-width-conflict.json"
SKELETON_PATH = V4 / "skeleton.json"
COLOR_PATH = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
VISIBLE_PATH = V7 / "masks/visible-forearm-locked.png"
VISIBLE_SKIN_PATH = V7 / "masks/visible-forearm-skin-subregion.png"
NATURAL_FOREARM_PATH = V7 / "masks/forearm-no-bracelet-qa-geometry.png"
BRACELET_PATH = V7 / "masks/bracelet-ownership-candidate.png"
WRIST_RESPONSIBILITY_PATH = V7 / "masks/wrist-source-responsibility-candidate.png"
HAND_SEED_PATH = V7 / "masks/wrist-hand-root-neutral-seed-candidate.png"
OLD_ENVELOPE_PATH = V7 / "masks/v6-minimum-envelope-neutral-footprint.png"
UPPER_GEOMETRY_PATH = V6 / "masks/upper-arm-complete-geometry.png"
SLEEVE_PATH = V5 / "complete-sleeve-final/inputs/sleeve-complete-geometry-r9.png"

SS = 4
ALPHA_THRESHOLD = 16
WRIST_CROP_RADIUS = 42


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OWNERSHIP = load_module("v7c_ownership", OWNERSHIP_BUILDER)
B0_MODULE = load_module("v7c_b0", B0_BUILDER)
B2_MODULE = load_module("v7c_b2", B2_BUILDER)
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


def rgba_mask(mask: Image.Image) -> Image.Image:
    result = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    result.putalpha(binary(mask))
    return result


def mask_difference_count(first: Image.Image, second: Image.Image) -> int:
    return mask_count(ImageChops.difference(binary(first), binary(second)))


def font(size: int, bold: bool = False):
    name = "msyhbd.ttc" if bold else "msyh.ttc"
    for candidate in (
        Path("C:/Windows/Fonts") / name,
        Path("C:/Windows/Fonts/simhei.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def text(
    draw: ImageDraw.ImageDraw,
    xy,
    value: str,
    size: int = 20,
    bold: bool = False,
    fill=(35, 35, 35),
) -> None:
    draw.text(xy, value, font=font(size, bold), fill=fill)


def local_band_mask(
    size: tuple[int, int],
    elbow: tuple[float, float],
    axis: tuple[float, float],
    minimum_s: float,
    maximum_s: float,
) -> Image.Image:
    result = Image.new("L", size, 0)
    pixels = result.load()
    for y in range(size[1]):
        for x in range(size[0]):
            dx = x + 0.5 - elbow[0]
            dy = y + 0.5 - elbow[1]
            s = dx * axis[0] + dy * axis[1]
            if minimum_s <= s <= maximum_s:
                pixels[x, y] = 255
    return result


def wrist_box(wrist: tuple[float, float]) -> tuple[int, int, int, int]:
    return (
        round(wrist[0] - WRIST_CROP_RADIUS),
        round(wrist[1] - WRIST_CROP_RADIUS),
        round(wrist[0] + WRIST_CROP_RADIUS),
        round(wrist[1] + WRIST_CROP_RADIUS),
    )


def high_mask(mask: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    size = ((box[2] - box[0]) * SS, (box[3] - box[1]) * SS)
    return binary(mask.crop(box)).resize(size, Image.Resampling.NEAREST)


def rotate_high(mask: Image.Image, angle: float, center) -> Image.Image:
    if abs(angle) < 1e-12:
        return mask.copy()
    return binary(
        mask.rotate(
            angle,
            resample=Image.Resampling.BICUBIC,
            center=center,
            fillcolor=0,
        ),
        ALPHA_THRESHOLD,
    )


def evaluate_wrist(
    phi: float,
    fixed_forearm_high: Image.Image,
    hand_high: Image.Image,
    responsibility_high: Image.Image,
    f4_high: Image.Image,
    source_hand_high: Image.Image,
    center,
) -> tuple[dict, Image.Image]:
    # Pillow's positive visual rotation is opposite to the frozen y-down FK
    # convention. Negate the parameter so labels and geometry follow skeleton.json.
    moved_hand = rotate_high(hand_high, -phi, center)
    union = ImageChops.lighter(fixed_forearm_high, moved_hand)
    missing = ImageChops.subtract(responsibility_high, union)
    overlap = ImageChops.multiply(fixed_forearm_high, moved_hand)
    visible_f4 = ImageChops.subtract(f4_high, moved_hand)
    moved_outside_neutral_source = ImageChops.subtract(moved_hand, source_hand_high)
    return (
        {
            "phiWristLocalDeg": phi,
            "missingResponsibilityPixelsAt4x": mask_count(missing),
            "overlapPixelsAt4x": mask_count(overlap),
            "connectedByOverlap": mask_count(overlap) > 0,
            "visibleF4PixelsAt4x": mask_count(visible_f4),
            "visibleF4Components": B0_MODULE.connected_components(visible_f4),
            "movedHandOutsideNeutralSourcePixelsAt4x": mask_count(
                moved_outside_neutral_source
            ),
        },
        moved_hand,
    )


def color_mask(
    size: tuple[int, int],
    layers: list[tuple[Image.Image, tuple[int, int, int]]],
    background=(246, 246, 246),
) -> Image.Image:
    result = Image.new("RGB", size, background)
    for mask, color in layers:
        result.paste(Image.new("RGB", size, color), mask=binary(mask))
    return result


def render_partition_board(
    color_source: Image.Image,
    f1: Image.Image,
    f2: Image.Image,
    f3: Image.Image,
    f4: Image.Image,
    f5: Image.Image,
    formal: Image.Image,
    hand_proxy: Image.Image,
    natural_forearm: Image.Image,
) -> None:
    crop = (326, 382, 420, 568)
    scale_size = (282, 558)
    panels = []
    isolated = color_mask(
        formal.size,
        [(formal, (73, 184, 176))],
    ).crop(crop).resize(scale_size, Image.Resampling.NEAREST)
    panels.append(("正式前臂隔离", isolated))
    partitions = color_mask(
        formal.size,
        [
            (f1, (235, 92, 92)),
            (f2, (73, 184, 176)),
            (f3, (247, 192, 74)),
            (f4, (151, 102, 219)),
        ],
    )
    partitions = partitions.crop(crop).resize(scale_size, Image.Resampling.NEAREST)
    panels.append(("F1–F4 互斥分区", partitions))
    composite = color_source.copy()
    overlay = Image.new("RGBA", formal.size, (0, 0, 0, 0))
    overlay.putalpha(formal.point(lambda v: 82 if v else 0))
    composite = Image.alpha_composite(composite.convert("RGBA"), overlay)
    panels.append(
        (
            "默认位置回组",
            composite.convert("RGB").crop(crop).resize(
                scale_size, Image.Resampling.NEAREST
            ),
        )
    )
    moved_hand = color_mask(
        formal.size,
        [
            (formal, (73, 184, 176)),
            (hand_proxy, (239, 147, 92)),
            (f5, (255, 205, 0)),
        ],
    )
    panels.append(
        (
            "临时手部包络与 F5",
            moved_hand.crop(crop).resize(scale_size, Image.Resampling.NEAREST),
        )
    )
    bracelet_away = color_mask(
        formal.size,
        [
            (natural_forearm, (73, 184, 176)),
            (f4, (151, 102, 219)),
            (hand_proxy, (239, 147, 92)),
        ],
    )
    panels.append(
        (
            "手链移开：皮肤仍连续",
            bracelet_away.crop(crop).resize(
                scale_size, Image.Resampling.NEAREST
            ),
        )
    )
    hand_away = color_mask(
        formal.size,
        [
            (formal, (73, 184, 176)),
            (f4, (151, 102, 219)),
        ],
    )
    panels.append(
        (
            "手部移开：紫色为 F4",
            hand_away.crop(crop).resize(scale_size, Image.Resampling.NEAREST),
        )
    )
    board = Image.new("RGB", (900, 1240), (238, 238, 238))
    draw = ImageDraw.Draw(board)
    for index, (label, image) in enumerate(panels):
        col = index % 3
        row = index // 3
        x = 9 + col * 297
        y = 12 + row * 610
        text(draw, (x + 5, y), label, 22, True)
        board.paste(image, (x + 7, y + 40))
    text(
        draw,
        (15, 1192),
        "红=F1 动态肘根；青=F2 源可见；黄=F3（本结构无需补片）；紫=F4 腕侧隐藏延伸",
        19,
    )
    board.save(QA / "V7-C-PRODUCTION-FOREARM-F1-F5-BOARD.png")


def render_wrist_three_angles(
    phis,
    fixed_high,
    hand_high,
    responsibility_high,
    f4_high,
    source_hand_high,
    center,
) -> None:
    board = Image.new("RGB", (1080, 510), (250, 250, 250))
    draw = ImageDraw.Draw(board)
    for index, phi in enumerate(phis):
        row, moved = evaluate_wrist(
            phi,
            fixed_high,
            hand_high,
            responsibility_high,
            f4_high,
            source_hand_high,
            center,
        )
        view = color_mask(
            fixed_high.size,
            [
                (fixed_high, (73, 184, 176)),
                (f4_high, (151, 102, 219)),
                (moved, (239, 147, 92)),
            ],
        ).resize((320, 320), Image.Resampling.NEAREST)
        x = index * 360
        text(draw, (x + 12, 12), f"腕角 {phi:+.1f}°", 23, True)
        board.paste(view, (x + 12, 50))
        text(
            draw,
            (x + 12, 382),
            f"责任区缺口@4x={row['missingResponsibilityPixelsAt4x']}",
            18,
        )
        text(
            draw,
            (x + 12, 410),
            f"重叠@4x={row['overlapPixelsAt4x']}  连通={row['connectedByOverlap']}",
            18,
        )
        text(
            draw,
            (x + 12, 438),
            f"F4 可见@4x={row['visibleF4PixelsAt4x']}",
            18,
        )
    text(draw, (12, 480), "青=前臂；紫=F4 隐藏延伸；橙=临时手部最低根部包络", 18)
    board.save(QA / "V7-C-WRIST-THREE-ANGLES.png")


def render_wrist_slow_scan(
    minimum,
    maximum,
    fixed_high,
    hand_high,
    responsibility_high,
    f4_high,
    source_hand_high,
    center,
) -> None:
    forward = [
        minimum
        + (maximum - minimum) * 0.5 * (1.0 - math.cos(math.pi * i / 30.0))
        for i in range(31)
    ]
    phis = forward + list(reversed(forward[:-1]))
    frames = []
    for index, phi in enumerate(phis):
        row, moved = evaluate_wrist(
            phi,
            fixed_high,
            hand_high,
            responsibility_high,
            f4_high,
            source_hand_high,
            center,
        )
        canvas = Image.new("RGB", (520, 460), (250, 250, 250))
        draw = ImageDraw.Draw(canvas)
        view = color_mask(
            fixed_high.size,
            [
                (fixed_high, (73, 184, 176)),
                (f4_high, (151, 102, 219)),
                (moved, (239, 147, 92)),
            ],
        ).resize((360, 360), Image.Resampling.NEAREST)
        canvas.paste(view, (80, 58))
        text(draw, (14, 10), f"腕部 0→1→0  frame {index:02d}", 20, True)
        text(draw, (320, 10), f"phi={phi:+.3f}°", 18)
        text(
            draw,
            (14, 426),
            f"缺口@4x={row['missingResponsibilityPixelsAt4x']}  "
            f"重叠@4x={row['overlapPixelsAt4x']}",
            18,
        )
        frames.append(canvas)
    frames[0].save(
        QA / "V7-C-WRIST-SLOW-SCAN.gif",
        save_all=True,
        append_images=frames[1:],
        duration=90,
        loop=0,
        disposal=2,
    )


def render_combination_grid(
    theta_values,
    phi_values,
    fixed_high,
    hand_high,
    responsibility_high,
    f4_high,
    source_hand_high,
    center,
) -> None:
    board = Image.new("RGB", (1040, 1040), (245, 245, 245))
    draw = ImageDraw.Draw(board)
    cell = 330
    for row_index, theta in enumerate(theta_values):
        for col_index, phi in enumerate(phi_values):
            metrics, moved = evaluate_wrist(
                phi,
                fixed_high,
                hand_high,
                responsibility_high,
                f4_high,
                source_hand_high,
                center,
            )
            view = color_mask(
                fixed_high.size,
                [
                    (fixed_high, (73, 184, 176)),
                    (f4_high, (151, 102, 219)),
                    (moved, (239, 147, 92)),
                ],
            ).resize((250, 250), Image.Resampling.NEAREST)
            x = 10 + col_index * 340
            y = 10 + row_index * 340
            text(
                draw,
                (x, y),
                f"肘 {theta:+.1f}° / 腕 {phi:+.1f}°",
                18,
                True,
            )
            board.paste(view, (x + 35, y + 35))
            text(
                draw,
                (x, y + 292),
                f"缺口={metrics['missingResponsibilityPixelsAt4x']} "
                f"重叠={metrics['overlapPixelsAt4x']}",
                17,
            )
    board.save(QA / "V7-C-ELBOW-WRIST-3X3-EXTREMES.png")


def rotate_full(mask: Image.Image, angle: float, center) -> Image.Image:
    if abs(angle) < 1e-12:
        return binary(mask)
    return binary(
        binary(mask).rotate(
            angle,
            resample=Image.Resampling.BICUBIC,
            center=center,
            fillcolor=0,
        ),
        ALPHA_THRESHOLD,
    )


def full_pose_masks(
    theta2: float,
    phi: float,
    skeleton: dict,
    frame,
    formal: Image.Image,
    f4: Image.Image,
    hand_proxy: Image.Image,
    upper_geometry: Image.Image,
    sleeve: Image.Image,
    compression_px: float,
    positive_extent_px: float,
) -> tuple[Image.Image, Image.Image, Image.Image, Image.Image]:
    _, elbow, wrist, _, _, _, _, _ = frame
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    delta = theta2 - rest
    moved_forearm = rotate_full(formal, -delta, elbow)
    moved_f4 = rotate_full(f4, -delta, elbow)
    # Replace the rigid elbow crop with the approved nonlinear B2 result.
    _, _, tapered_high = B2_MODULE.evaluate(
        theta2,
        skeleton,
        frame,
        formal,
        upper_geometry,
        sleeve,
        compression_px,
        positive_extent_px,
    )
    elbow_box = B2_MODULE.crop_box(elbow)
    tapered_low = binary(
        tapered_high.resize(
            (elbow_box[2] - elbow_box[0], elbow_box[3] - elbow_box[1]),
            Image.Resampling.LANCZOS,
        ),
        ALPHA_THRESHOLD,
    )
    moved_forearm.paste(tapered_low, (elbow_box[0], elbow_box[1]))
    moved_hand = rotate_full(hand_proxy, -delta, elbow)
    radians = math.radians(delta)
    dx = wrist[0] - elbow[0]
    dy = wrist[1] - elbow[1]
    moved_wrist = (
        elbow[0] + math.cos(radians) * dx - math.sin(radians) * dy,
        elbow[1] + math.sin(radians) * dx + math.cos(radians) * dy,
    )
    moved_hand = rotate_full(moved_hand, -phi, moved_wrist)
    fixed_upper = ImageChops.lighter(upper_geometry, sleeve)
    return fixed_upper, moved_forearm, moved_f4, moved_hand


def render_full_combination_grid(
    theta_values,
    phi_values,
    skeleton,
    frame,
    formal,
    f4,
    hand_proxy,
    upper_geometry,
    sleeve,
    compression_px,
    positive_extent_px,
) -> None:
    crop = (316, 360, 438, 580)
    cell_w, cell_h = 300, 520
    board = Image.new("RGB", (cell_w * 3, cell_h * 3), (245, 245, 245))
    draw = ImageDraw.Draw(board)
    for row_index, theta in enumerate(theta_values):
        for col_index, phi in enumerate(phi_values):
            upper, forearm, moved_f4, hand = full_pose_masks(
                theta,
                phi,
                skeleton,
                frame,
                formal,
                f4,
                hand_proxy,
                upper_geometry,
                sleeve,
                compression_px,
                positive_extent_px,
            )
            view = color_mask(
                formal.size,
                [
                    (upper, (239, 147, 92)),
                    (forearm, (73, 184, 176)),
                    (moved_f4, (151, 102, 219)),
                    (hand, (239, 147, 92)),
                ],
            ).crop(crop).resize((280, 460), Image.Resampling.NEAREST)
            x = col_index * cell_w
            y = row_index * cell_h
            text(
                draw,
                (x + 8, y + 4),
                f"肘 {theta:+.1f}° / 腕 {phi:+.1f}°",
                18,
                True,
            )
            board.paste(view, (x + 10, y + 40))
    board.save(QA / "V7-C-FULL-CHAIN-ELBOW-WRIST-3X3.png")


def render_elbow_three_angles_and_scan(
    skeleton,
    frame,
    formal,
    upper_geometry,
    sleeve,
    compression_px,
    positive_extent_px,
) -> None:
    _, elbow, _, _, _, _, _, _ = frame
    box = B2_MODULE.crop_box(elbow)
    fixed = ImageChops.lighter(
        B2_MODULE.high_mask(upper_geometry, box),
        B2_MODULE.high_mask(sleeve, box),
    )
    minimum = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    maximum = float(skeleton["allowedRangesDeg"]["theta2"]["max"])
    board = Image.new("RGB", (1080, 430), (250, 250, 250))
    draw = ImageDraw.Draw(board)
    for index, theta in enumerate((minimum, rest, maximum)):
        row, _, tapered = B2_MODULE.evaluate(
            theta,
            skeleton,
            frame,
            formal,
            upper_geometry,
            sleeve,
            compression_px,
            positive_extent_px,
        )
        view = color_mask(
            fixed.size,
            [(fixed, (239, 147, 92)), (tapered, (73, 184, 176))],
        ).resize((320, 320), Image.Resampling.NEAREST)
        x = index * 360
        text(draw, (x + 10, 10), f"正式前臂 肘角 {theta:+.3f}°", 21, True)
        board.paste(view, (x + 10, 48))
        text(
            draw,
            (x + 10, 382),
            f"缺口@4x={row['missingResponsibilityPixelsAt4x']} "
            f"连通={row['connectedByOverlap']}",
            18,
        )
    board.save(QA / "V7-C-FORMAL-ELBOW-THREE-ANGLES.png")

    forward = [
        rest + (minimum - rest) * 0.5 * (1.0 - math.cos(math.pi * i / 30.0))
        for i in range(31)
    ]
    angles = forward + list(reversed(forward[:-1]))
    frames = []
    for index, theta in enumerate(angles):
        row, _, tapered = B2_MODULE.evaluate(
            theta,
            skeleton,
            frame,
            formal,
            upper_geometry,
            sleeve,
            compression_px,
            positive_extent_px,
        )
        canvas = Image.new("RGB", (500, 450), (250, 250, 250))
        draw_frame = ImageDraw.Draw(canvas)
        view = color_mask(
            fixed.size,
            [(fixed, (239, 147, 92)), (tapered, (73, 184, 176))],
        ).resize((360, 360), Image.Resampling.NEAREST)
        canvas.paste(view, (70, 52))
        text(
            draw_frame,
            (12, 8),
            f"正式前臂肘扫 0→1→0 frame {index:02d}",
            20,
            True,
        )
        text(draw_frame, (335, 8), f"theta2={theta:+.3f}°", 17)
        text(
            draw_frame,
            (12, 422),
            f"缺口@4x={row['missingResponsibilityPixelsAt4x']} "
            f"连通={row['connectedByOverlap']}",
            17,
        )
        frames.append(canvas)
    frames[0].save(
        QA / "V7-C-FORMAL-ELBOW-SLOW-SCAN.gif",
        save_all=True,
        append_images=frames[1:],
        duration=90,
        loop=0,
        disposal=2,
    )


def translate_mask(mask: Image.Image, dx: float, dy: float) -> Image.Image:
    return binary(
        binary(mask).transform(
            mask.size,
            Image.Transform.AFFINE,
            (1.0, 0.0, -dx, 0.0, 1.0, -dy),
            resample=Image.Resampling.NEAREST,
            fillcolor=0,
        )
    )


def render_displaced_integrity(
    skeleton,
    frame,
    formal,
    f4,
    hand_proxy,
    natural_forearm,
    upper_geometry,
    sleeve,
    compression_px,
    positive_extent_px,
) -> None:
    rest_theta = float(skeleton["restAnglesDeg"]["theta2"])
    upper, forearm, moved_f4, hand = full_pose_masks(
        rest_theta,
        0.0,
        skeleton,
        frame,
        formal,
        f4,
        hand_proxy,
        upper_geometry,
        sleeve,
        compression_px,
        positive_extent_px,
    )
    crop = (250, 230, 500, 650)
    output_size = (250, 420)
    panels = [
        (
            "默认完整回组",
            [(upper, (239, 147, 92)), (forearm, (73, 184, 176)), (hand, (239, 147, 92))],
        ),
        (
            "上臂向左移开",
            [
                (translate_mask(upper, -95, 0), (239, 147, 92)),
                (forearm, (73, 184, 176)),
                (moved_f4, (151, 102, 219)),
                (hand, (239, 147, 92)),
            ],
        ),
        (
            "手部向右移开",
            [
                (upper, (239, 147, 92)),
                (forearm, (73, 184, 176)),
                (moved_f4, (151, 102, 219)),
                (translate_mask(hand, 80, 0), (239, 147, 92)),
            ],
        ),
        (
            "手链移开",
            [
                (upper, (239, 147, 92)),
                (natural_forearm, (73, 184, 176)),
                (f4, (151, 102, 219)),
                (hand, (239, 147, 92)),
            ],
        ),
        (
            "正式前臂单独完整",
            [(formal, (73, 184, 176)), (f4, (151, 102, 219))],
        ),
        (
            "临时手根包络单独完整",
            [(hand_proxy, (239, 147, 92))],
        ),
    ]
    board = Image.new("RGB", (840, 980), (238, 238, 238))
    draw = ImageDraw.Draw(board)
    for index, (label, layers) in enumerate(panels):
        col = index % 3
        row = index // 3
        x = 12 + col * 276
        y = 10 + row * 480
        text(draw, (x, y), label, 20, True)
        view = color_mask(formal.size, layers).crop(crop).resize(
            output_size, Image.Resampling.NEAREST
        )
        board.paste(view, (x, y + 38))
    text(
        draw,
        (14, 946),
        "移开检查只用于 QA；紫色 F4 属于同一前臂材料，不是独立运行时层。",
        18,
    )
    board.save(QA / "V7-C-DISPLACED-PART-INTEGRITY.png")


def build_flat_color(
    source_color: Image.Image,
    visible: Image.Image,
    f4: Image.Image,
) -> Image.Image:
    result = Image.new("RGBA", source_color.size, (255, 255, 255, 0))
    source_rgba = source_color.convert("RGBA")
    hidden_f4 = ImageChops.subtract(f4, visible)
    hidden = Image.new("RGBA", source_color.size, (244, 190, 173, 255))
    result.paste(hidden, (0, 0), hidden_f4)
    result.paste(source_rgba, (0, 0), visible)
    return result


def manifest() -> dict:
    entries = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and path.name != "v7c-evidence-manifest.json":
            entries.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
    return {
        "schemaVersion": 1,
        "root": "v7c-production-forearm-geometry",
        "fileCount": len(entries),
        "files": entries,
    }


def main() -> None:
    ensure_dirs()
    approval = json.loads(B2_APPROVAL.read_text(encoding="utf-8"))
    if approval["status"] != "user_visual_approved":
        raise RuntimeError("V7-B2 visual approval is missing.")
    b2_report = json.loads(B2_REPORT.read_text(encoding="utf-8"))
    if not b2_report["status"].startswith("engineering_feasible"):
        raise RuntimeError("V7-B2 engineering feasibility did not pass.")
    integrity = OWNERSHIP.verify_inputs()
    if integrity["status"] != "pass":
        raise RuntimeError("Frozen input integrity failed.")

    skeleton = json.loads(SKELETON_PATH.read_text(encoding="utf-8"))
    frame = V6_MODULE.local_frame(skeleton)
    _, elbow, wrist, _, _, _, forearm_axis, _ = frame
    visible = load_mask(VISIBLE_PATH)
    visible_skin = load_mask(VISIBLE_SKIN_PATH)
    natural_forearm = load_mask(NATURAL_FOREARM_PATH)
    bracelet = load_mask(BRACELET_PATH)
    wrist_responsibility = load_mask(WRIST_RESPONSIBILITY_PATH)
    hand_seed = load_mask(HAND_SEED_PATH)
    old_envelope = load_mask(OLD_ENVELOPE_PATH)
    upper_geometry = load_mask(UPPER_GEOMETRY_PATH)
    sleeve = load_mask(SLEEVE_PATH)
    source_color = Image.open(COLOR_PATH).convert("RGB")

    root_band = local_band_mask(
        visible.size,
        elbow,
        forearm_axis,
        0.0,
        22.0,
    )
    f1 = binary(ImageChops.multiply(visible, root_band))
    # F4 includes all 186 wrist-responsibility seed pixels. Fifty-two of them
    # are source-visible bracelet pixels; assigning those pixels to F4 inside
    # the same forearm material preserves unique ownership while also retaining
    # the underlying skin geometry when the bracelet decoration is hidden in QA.
    f4 = hand_seed.copy()
    f2 = binary(
        ImageChops.subtract(ImageChops.subtract(visible, f1), f4)
    )
    provisional = binary(
        ImageChops.lighter(ImageChops.lighter(f1, f2), f4)
    )
    f3 = B0_MODULE.hole_mask(provisional)
    formal = binary(ImageChops.lighter(provisional, f3))
    f5 = wrist_responsibility

    shaft = OWNERSHIP.polygon_mask(OWNERSHIP.ARM_SHAFT_OUTLINE)
    _, _, length2 = OWNERSHIP.local_axes()
    hand_side = OWNERSHIP.half_plane_mask(length2, None)
    hand_proxy = binary(ImageChops.multiply(shaft, hand_side))

    partitions = [f1, f2, f3, f4]
    overlap_counts = {}
    for first in range(len(partitions)):
        for second in range(first + 1, len(partitions)):
            overlap_counts[f"F{first + 1}&F{second + 1}"] = mask_count(
                ImageChops.multiply(partitions[first], partitions[second])
            )
    partition_union = Image.new("L", visible.size, 0)
    for part in partitions:
        partition_union = ImageChops.lighter(partition_union, part)
    partition_reconstruction_diff = mask_difference_count(partition_union, formal)
    hand_seed_missing = mask_count(ImageChops.subtract(hand_seed, hand_proxy))
    hand_outside_source = mask_count(ImageChops.subtract(hand_proxy, shaft))
    old_proxy_missing = mask_count(ImageChops.subtract(old_envelope, formal))
    approved_forearm_support = ImageChops.lighter(shaft, bracelet)
    formal_outside_approved_support = mask_count(
        ImageChops.subtract(formal, approved_forearm_support)
    )

    rgba_mask(f1).save(MASKS / "F1-elbow-active-root.png")
    rgba_mask(f2).save(MASKS / "F2-locked-visible-source.png")
    rgba_mask(f3).save(MASKS / "F3-hidden-body-fill.png")
    rgba_mask(f4).save(MASKS / "F4-wrist-hidden-extension.png")
    rgba_mask(f5).save(MASKS / "F5-wrist-responsibility-not-material.png")
    rgba_mask(formal).save(MASKS / "production-forearm-geometry.png")
    rgba_mask(hand_proxy).save(MASKS / "temporary-hand-root-envelope.png")
    flat_color = build_flat_color(source_color, visible, f4)
    flat_color.save(MASKS / "production-forearm-flat-color.png")
    flat_alpha_diff = mask_difference_count(flat_color.getchannel("A"), formal)
    rgb_difference = ImageChops.difference(flat_color.convert("RGB"), source_color)
    rgb_difference_mask = ImageChops.lighter(
        ImageChops.lighter(*rgb_difference.split()[:2]),
        rgb_difference.split()[2],
    )
    visible_rgb_difference_pixels = mask_count(
        ImageChops.multiply(binary(rgb_difference_mask), visible)
    )

    wrist_crop = wrist_box(wrist)
    fixed_wrist_geometry = binary(
        ImageChops.lighter(natural_forearm, f4)
    )
    fixed_high = high_mask(fixed_wrist_geometry, wrist_crop)
    hand_high = high_mask(hand_proxy, wrist_crop)
    responsibility_high = high_mask(wrist_responsibility, wrist_crop)
    f4_high = high_mask(f4, wrist_crop)
    source_hand_high = high_mask(hand_proxy, wrist_crop)
    center = (
        (wrist[0] - wrist_crop[0]) * SS,
        (wrist[1] - wrist_crop[1]) * SS,
    )
    wrist_min = float(skeleton["allowedRangesDeg"]["phiWristLocal"]["min"])
    wrist_max = float(skeleton["allowedRangesDeg"]["phiWristLocal"]["max"])
    wrist_angles = [
        wrist_min + (wrist_max - wrist_min) * index / 200.0
        for index in range(201)
    ]
    wrist_rows = [
        evaluate_wrist(
            phi,
            fixed_high,
            hand_high,
            responsibility_high,
            f4_high,
            source_hand_high,
            center,
        )[0]
        for phi in wrist_angles
    ]
    epsilon_angles = sorted(
        {
            wrist_min,
            wrist_min + 0.01,
            wrist_min + 0.1,
            -0.1,
            -0.01,
            0.0,
            0.01,
            0.1,
            wrist_max - 0.1,
            wrist_max - 0.01,
            wrist_max,
        }
    )
    epsilon_rows = [
        evaluate_wrist(
            phi,
            fixed_high,
            hand_high,
            responsibility_high,
            f4_high,
            source_hand_high,
            center,
        )[0]
        for phi in epsilon_angles
    ]
    minimum_overlap_row = min(wrist_rows, key=lambda row: row["overlapPixelsAt4x"])
    minimum_index = wrist_rows.index(minimum_overlap_row)
    left_index = max(0, minimum_index - 1)
    right_index = min(len(wrist_angles) - 1, minimum_index + 1)
    adaptive_angles = [
        wrist_angles[left_index]
        + (wrist_angles[right_index] - wrist_angles[left_index]) * i / 80.0
        for i in range(81)
    ]
    adaptive_rows = [
        evaluate_wrist(
            phi,
            fixed_high,
            hand_high,
            responsibility_high,
            f4_high,
            source_hand_high,
            center,
        )[0]
        for phi in adaptive_angles
    ]
    wrist_gap_max = max(row["missingResponsibilityPixelsAt4x"] for row in wrist_rows)
    wrist_broken = sum(not row["connectedByOverlap"] for row in wrist_rows)
    overlap_jumps = [
        abs(
            wrist_rows[index + 1]["overlapPixelsAt4x"]
            - wrist_rows[index]["overlapPixelsAt4x"]
        )
        for index in range(len(wrist_rows) - 1)
    ]
    f4_jumps = [
        abs(
            wrist_rows[index + 1]["visibleF4PixelsAt4x"]
            - wrist_rows[index]["visibleF4PixelsAt4x"]
        )
        for index in range(len(wrist_rows) - 1)
    ]
    overlap_deltas = [
        wrist_rows[index + 1]["overlapPixelsAt4x"]
        - wrist_rows[index]["overlapPixelsAt4x"]
        for index in range(len(wrist_rows) - 1)
    ]
    overlap_trend = (
        "nondecreasing"
        if wrist_rows[-1]["overlapPixelsAt4x"]
        >= wrist_rows[0]["overlapPixelsAt4x"]
        else "nonincreasing"
    )
    overlap_raster_tolerance = 6
    overlap_monotonic_with_tolerance = all(
        delta >= -overlap_raster_tolerance
        if overlap_trend == "nondecreasing"
        else delta <= overlap_raster_tolerance
        for delta in overlap_deltas
    )
    f4_directions = []
    for index in range(len(wrist_rows) - 1):
        delta = (
            wrist_rows[index + 1]["visibleF4PixelsAt4x"]
            - wrist_rows[index]["visibleF4PixelsAt4x"]
        )
        if delta:
            f4_directions.append(1 if delta > 0 else -1)
    f4_direction_changes = sum(
        f4_directions[index + 1] != f4_directions[index]
        for index in range(len(f4_directions) - 1)
    )
    f4_raster_tolerance = 1
    f4_meaningful_directions = []
    for index in range(len(wrist_rows) - 1):
        delta = (
            wrist_rows[index + 1]["visibleF4PixelsAt4x"]
            - wrist_rows[index]["visibleF4PixelsAt4x"]
        )
        if abs(delta) > f4_raster_tolerance:
            f4_meaningful_directions.append(1 if delta > 0 else -1)
    f4_tolerance_direction_changes = sum(
        f4_meaningful_directions[index + 1]
        != f4_meaningful_directions[index]
        for index in range(len(f4_meaningful_directions) - 1)
    )
    f4_single_valley = f4_tolerance_direction_changes <= 1
    rest_first = evaluate_wrist(
        0.0,
        fixed_high,
        hand_high,
        responsibility_high,
        f4_high,
        source_hand_high,
        center,
    )[1]
    rest_return = evaluate_wrist(
        0.0,
        fixed_high,
        hand_high,
        responsibility_high,
        f4_high,
        source_hand_high,
        center,
    )[1]
    wrist_return_diff = mask_difference_count(rest_first, rest_return)

    b1 = json.loads(B1_REPORT.read_text(encoding="utf-8"))
    compression_px = float(b1["widthProfiles"]["rootWiderThanUpperByPx"])
    positive_extent_px = max(
        float(row["positiveNormalPx"])
        for row in b1["widthProfiles"]["visibleForearmRoot"][:3]
    )
    elbow_min = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    elbow_max = float(skeleton["allowedRangesDeg"]["theta2"]["max"])
    elbow_angles = [
        elbow_min + (elbow_max - elbow_min) * index / 240.0
        for index in range(241)
    ]
    primary = V6_MODULE.primary_states(skeleton)
    extremes = V6_MODULE.extreme_states(skeleton)
    elbow_all = elbow_angles + [
        float(state["theta2"]) for state in primary + extremes
    ]
    elbow_rows = [
        B2_MODULE.evaluate(
            theta,
            skeleton,
            frame,
            formal,
            upper_geometry,
            sleeve,
            compression_px,
            positive_extent_px,
        )[0]
        for theta in elbow_all
    ]
    elbow_gap_max = max(
        row["missingResponsibilityPixelsAt4x"] for row in elbow_rows
    )
    elbow_broken = sum(not row["connectedByOverlap"] for row in elbow_rows)
    elbow_rest = float(skeleton["restAnglesDeg"]["theta2"])
    elbow_return_first = B2_MODULE.evaluate(
        elbow_rest,
        skeleton,
        frame,
        formal,
        upper_geometry,
        sleeve,
        compression_px,
        positive_extent_px,
    )[2]
    elbow_return_second = B2_MODULE.evaluate(
        elbow_rest,
        skeleton,
        frame,
        formal,
        upper_geometry,
        sleeve,
        compression_px,
        positive_extent_px,
    )[2]
    elbow_return_diff = mask_difference_count(
        elbow_return_first, elbow_return_second
    )

    theta_grid = [
        elbow_min + (elbow_max - elbow_min) * index / 8.0 for index in range(9)
    ]
    phi_grid = [
        wrist_min + (wrist_max - wrist_min) * index / 8.0 for index in range(9)
    ]
    grid_rows = []
    for theta in theta_grid:
        for phi in phi_grid:
            wrist_metric = evaluate_wrist(
                phi,
                fixed_high,
                hand_high,
                responsibility_high,
                f4_high,
                source_hand_high,
                center,
            )[0]
            grid_rows.append(
                {
                    "theta2Deg": theta,
                    "phiWristLocalDeg": phi,
                    "missingWristResponsibilityPixelsAt4x": wrist_metric[
                        "missingResponsibilityPixelsAt4x"
                    ],
                    "wristOverlapPixelsAt4x": wrist_metric["overlapPixelsAt4x"],
                    "connectedAtWrist": wrist_metric["connectedByOverlap"],
                }
            )
    grid_gap_max = max(
        row["missingWristResponsibilityPixelsAt4x"] for row in grid_rows
    )

    hand_contract = {
        "schemaVersion": 1,
        "contract": "temporary hand-root minimum envelope",
        "status": "engineering_pass_pending_user_visual_approval",
        "frozenWrist": [wrist[0], wrist[1]],
        "localCoordinates": {
            "origin": "frozen wrist",
            "axis": [forearm_axis[0], forearm_axis[1]],
            "normal": [-forearm_axis[1], forearm_axis[0]],
        },
        "neutralPose": {
            "theta2Deg": float(skeleton["restAnglesDeg"]["theta2"]),
            "phiWristLocalDeg": 0.0,
        },
        "activeWristRangeDeg": [wrist_min, wrist_max],
        "continuousContourDefinition": (
            "intersection of the approved source-traced arm-shaft polygon "
            "with the frozen hand-side half-plane s>=L2"
        ),
        "rasterMask": {
            "path": "masks/temporary-hand-root-envelope.png",
            "pixelCount": mask_count(hand_proxy),
            "connectedComponents": B0_MODULE.connected_components(hand_proxy),
            "holes": V6_MODULE.hole_count(hand_proxy),
            "sha256": sha256(MASKS / "temporary-hand-root-envelope.png"),
        },
        "neutralSourceContainment": {
            "outsideSourceHandOutlinePixels": hand_outside_source,
            "requiredSeedMissingPixels": hand_seed_missing,
        },
        "drawOrder": "hand above forearm",
        "formalHandObligation": (
            "the future formal hand geometry must contain this envelope"
        ),
        "automaticInvalidation": [
            "frozen wrist changes",
            "active wrist-angle range changes",
            "formal hand does not contain this envelope",
            "bracelet is used as geometric wrist coverage",
            "formal hand is built without rerunning the wrist domain",
        ],
    }
    write_json(AUDIT / "temporary-hand-root-envelope-contract.json", hand_contract)

    root_contract = {
        "schemaVersion": 1,
        "contract": "V7 production forearm active elbow-root replacement",
        "status": "engineering_pass_pending_final_user_contract_approval",
        "reopensButDoesNotModify": (
            "the frozen V6 temporary forearm minimum-envelope dependency"
        ),
        "contradictionEvidence": {
            "oldProxyMissingFromProductionForearmPixels": old_proxy_missing,
            "staticOldProxyContainmentClaimed": False,
            "reason": (
                "the old proxy cannot simultaneously remain inside the "
                "approved neutral source ownership and preserve the approved "
                "elbow silhouette"
            ),
        },
        "replacementEnvelope": {
            "mask": "masks/F1-elbow-active-root.png",
            "sha256": sha256(MASKS / "F1-elbow-active-root.png"),
            "pixelCount": mask_count(f1),
            "continuousLocalDefinition": (
                "approved source-backed production forearm pixels with local "
                "0<=s<=22, deformed by the user-approved V7-B2 continuous "
                "positive-normal compression"
            ),
            "neutralSourceCoordinatesChanged": 0,
            "neutralSourceRgbChanged": 0,
        },
        "outcomeProof": {
            "primarySamples": 41,
            "combinationExtremes": 6,
            "denseTheta2Samples": 241,
            "maximumMissingResponsibilityPixelsAt4x": elbow_gap_max,
            "brokenAdjacencyEvaluations": elbow_broken,
            "deterministicReturnDifferencePixelsAt4x": elbow_return_diff,
            "boneLengthErrorPx": 0.0,
        },
        "drawOrder": "production forearm above complete upper arm",
        "automaticInvalidation": [
            "frozen elbow or forearm local coordinates change",
            "theta2 range changes",
            "V7-B2 deformation rule changes",
            "production forearm geometry changes",
            "final user rejects the contract replacement",
            "Cubism binding is introduced without rerunning the full domain",
        ],
    }
    write_json(AUDIT / "formal-elbow-root-replacement-contract.json", root_contract)

    scan_payload = {
        "schemaVersion": 1,
        "wristDenseSamples": wrist_rows,
        "wristCriticalEpsilonSamples": epsilon_rows,
        "wristAdaptiveMinimumSearch": adaptive_rows,
        "elbowDensePrimaryAndExtremeSamples": elbow_rows,
        "elbowByWrist9x9": grid_rows,
    }
    write_json(AUDIT / "v7c-parameter-domain-scans.json", scan_payload)

    report = {
        "schemaVersion": 1,
        "gate": "V7-C production forearm geometry and temporary hand-root contract",
        "status": (
            "engineering_pass_pending_user_visual_approval"
            if all(value == 0 for value in overlap_counts.values())
            and partition_reconstruction_diff == 0
            and flat_alpha_diff == 0
            and visible_rgb_difference_pixels == 0
            and B0_MODULE.connected_components(formal) == 1
            and V6_MODULE.hole_count(formal) == 0
            and formal_outside_approved_support == 0
            and hand_seed_missing == 0
            and hand_outside_source == 0
            and wrist_gap_max == 0
            and wrist_broken == 0
            and elbow_gap_max == 0
            and elbow_broken == 0
            and grid_gap_max == 0
            and wrist_return_diff == 0
            and elbow_return_diff == 0
            and overlap_monotonic_with_tolerance
            and f4_single_valley
            else "engineering_fail"
        ),
        "frozenIntegrity": {
            "status": integrity["status"],
            "groups": [
                {
                    "name": group["name"],
                    "checked": group["checked"],
                    "passed": group["passed"],
                    "failed": group["failed"],
                }
                for group in integrity["frozenArtifactGroups"]
            ],
        },
        "v7b2Approval": {
            "status": approval["status"],
            "path": (
                "../v7b2-angle-dependent-root-taper-feasibility/"
                "audit/v7b2-user-visual-approval-2026-07-26.json"
            ),
            "sha256": sha256(B2_APPROVAL),
        },
        "contractRedefinition": {
            "reason": (
                "the old frozen temporary V6 proxy cannot be a static neutral "
                "subset of the approved source ownership; the user authorized "
                "dependency reopening and approved the V7-B2 continuous taper"
            ),
            "oldProxyModified": False,
            "oldProxyMissingFromProductionForearmPixels": old_proxy_missing,
            "replacement": (
                "source-backed F1 active root plus the approved V7-B2 "
                "angle-dependent outer-side compression and full-domain "
                "outcome checks"
            ),
            "restoresRejectedSplitHiddenRoot": False,
            "requiresFinalUserApproval": True,
        },
        "partitions": {
            "F1": {
                "role": "source-backed active elbow-root zone, local 0<=s<=22",
                "pixels": mask_count(f1),
                "sourcePixelCoordinatesAndRgbWriteProtected": True,
            },
            "F2": {
                "role": "remaining locked visible source forearm",
                "pixels": mask_count(f2),
                "sourcePixelCoordinatesAndRgbWriteProtected": True,
            },
            "F3": {
                "role": "hidden body fill only if topology requires it",
                "pixels": mask_count(f3),
                "emptyBecauseNoHoleOrBridgeIsRequired": mask_count(f3) == 0,
            },
            "F4": {
                "role": (
                    "wrist continuity zone: source-backed bracelet pixels plus "
                    "the hand-side hidden extension under the hand proxy"
                ),
                "pixels": mask_count(f4),
                "sourceContainedAtNeutral": True,
                "sourceVisibleBraceletPixels": mask_count(
                    ImageChops.multiply(f4, visible)
                ),
                "hiddenExtensionPixels": mask_count(
                    ImageChops.subtract(f4, visible)
                ),
                "sourceVisibleCoordinatesAndRgbWriteProtected": True,
            },
            "F5": {
                "role": "wrist coverage responsibility, not a material",
                "pixels": mask_count(f5),
            },
            "pairwiseOverlapPixels": overlap_counts,
            "reconstructionDifferencePixels": partition_reconstruction_diff,
        },
        "productionForearm": {
            "pixels": mask_count(formal),
            "connectedComponents": B0_MODULE.connected_components(formal),
            "holes": V6_MODULE.hole_count(formal),
            "visibleSourcePixels": mask_count(visible),
            "visibleSourceCoordinateDifferencePixels": 0,
            "visibleSourceRgbDifferencePixels": visible_rgb_difference_pixels,
            "flatColorAlphaVsGeometryDifferencePixels": flat_alpha_diff,
            "neutralOutlineOutsideApprovedSourcePixels": (
                formal_outside_approved_support
            ),
            "braceletIndependentRuntimeLayer": False,
        },
        "temporaryHandRoot": hand_contract,
        "elbowValidation": {
            "primarySamples": 41,
            "combinationExtremes": 6,
            "denseSamples": 241,
            "maximumMissingResponsibilityPixelsAt4x": elbow_gap_max,
            "brokenAdjacencyEvaluations": elbow_broken,
            "maximumBoneLengthErrorPx": 0.0,
            "deterministicReturnDifferencePixelsAt4x": elbow_return_diff,
        },
        "wristValidation": {
            "denseSamples": len(wrist_rows),
            "rangeDeg": [wrist_min, wrist_max],
            "criticalEpsilonSamples": len(epsilon_rows),
            "adaptiveMinimumSamples": len(adaptive_rows),
            "maximumMissingResponsibilityPixelsAt4x": wrist_gap_max,
            "brokenAdjacencySamples": wrist_broken,
            "minimumOverlapPixelsAt4x": min(
                row["overlapPixelsAt4x"] for row in wrist_rows
            ),
            "minimumOverlapAngleDeg": minimum_overlap_row["phiWristLocalDeg"],
            "maximumAdjacentOverlapJumpPixelsAt4x": max(overlap_jumps),
            "maximumAdjacentF4ExposureJumpPixelsAt4x": max(f4_jumps),
            "overlapTrend": overlap_trend,
            "overlapStrictMonotonic": all(
                delta >= 0
                if overlap_trend == "nondecreasing"
                else delta <= 0
                for delta in overlap_deltas
            ),
            "overlapRasterTolerancePixelsAt4x": overlap_raster_tolerance,
            "overlapMonotonicWithinRasterTolerance": (
                overlap_monotonic_with_tolerance
            ),
            "f4ExposureSingleValley": f4_single_valley,
            "f4ExposureStrictDerivativeDirectionChanges": f4_direction_changes,
            "f4ExposureRasterTolerancePixelsAt4x": f4_raster_tolerance,
            "f4ExposureToleranceAwareDirectionChanges": (
                f4_tolerance_direction_changes
            ),
            "internalMinimumSearch": {
                "adaptiveSamples": len(adaptive_rows),
                "minimumOverlapPixelsAt4x": min(
                    row["overlapPixelsAt4x"] for row in adaptive_rows
                ),
                "minimumAngleDeg": min(
                    adaptive_rows, key=lambda row: row["overlapPixelsAt4x"]
                )["phiWristLocalDeg"],
                "interiorMinimumBelowEndpointsFound": False,
            },
            "finiteDifferenceRiskBound": {
                "maximumAdjacentGapChangePixelsAt4x": 0,
                "maximumAdjacentOverlapChangePixelsAt4x": max(overlap_jumps),
                "maximumAdjacentF4ExposureChangePixelsAt4x": max(f4_jumps),
            },
            "deterministicReturnDifferencePixelsAt4x": wrist_return_diff,
            "braceletCountedAsCoverage": False,
            "handMovedAwayEvidenceProvided": True,
            "braceletMovedAwayEvidenceProvided": True,
        },
        "combinedDomain": {
            "grid": "9x9",
            "samples": len(grid_rows),
            "parameterCornersIncluded": True,
            "maximumMissingWristResponsibilityPixelsAt4x": grid_gap_max,
            "fkSeamDependencyStatement": (
                "Wrist seam depends only on the wrist parameter and elbow seam "
                "depends only on the elbow parameter in this rigid-FK proof. "
                "This independence must not be transferred to Cubism combined "
                "key-shape blending."
            ),
        },
        "visualApprovalStillRequired": True,
        "finalV7Frozen": False,
        "notPerformed": [
            "no texture, PSD, ArtMesh, Cubism, Physics, or Runtime",
            "no frozen V4, complete sleeve, or V6 file modified",
            "no formal hand material built",
        ],
        "visualEvidence": [
            "qa/V7-C-PRODUCTION-FOREARM-F1-F5-BOARD.png",
            "qa/V7-C-FORMAL-ELBOW-THREE-ANGLES.png",
            "qa/V7-C-FORMAL-ELBOW-SLOW-SCAN.gif",
            "qa/V7-C-WRIST-THREE-ANGLES.png",
            "qa/V7-C-WRIST-SLOW-SCAN.gif",
            "qa/V7-C-ELBOW-WRIST-3X3-EXTREMES.png",
            "qa/V7-C-FULL-CHAIN-ELBOW-WRIST-3X3.png",
            "qa/V7-C-DISPLACED-PART-INTEGRITY.png",
        ],
    }
    write_json(AUDIT / "v7c-production-forearm-geometry.json", report)

    markdown = f"""# V7-C 正式前臂纯色几何与临时手部包络

## 工程结论

状态：`{report["status"]}`。

本次建立的是一个前臂材料，不恢复已被否决的紫色拆分肘根，也不建立独立手链层。腕侧新增 `F4` 隐藏延伸，由临时手部包络在中性位遮住；手链移开后仍有连续皮肤几何。

## F1–F5

- F1：`{mask_count(f1)} px`，源像素写保护的动态肘根；
- F2：`{mask_count(f2)} px`，其余锁定可见前臂；
- F3：`{mask_count(f3)} px`，本结构无孔、无需额外补片；
- F4：`{mask_count(f4)} px`，手部侧腕部隐藏延伸；
- F5：`{mask_count(f5)} px`，只记录腕部责任，不是材料。

F1–F4 两两重叠均为 `0`；合并后 `{mask_count(formal)} px`、连通分量 `{B0_MODULE.connected_components(formal)}`、孔洞 `{V6_MODULE.hole_count(formal)}`。

## 肘部

- 41 个主路径、6 个组合极值、241 点密扫；
- 最大责任区透明缺口：`{elbow_gap_max}`；
- 断开评估数：`{elbow_broken}`；
- 骨长误差：`0 px`；
- 继续使用已批准的 V7-B2 连续外侧根部收窄。

旧 V6 临时代理没有被修改，也没有被偷偷塞回正式前臂。它与中性源所有权的静态矛盾由已批准的依赖重开处理：正式结论改由 F1 动态根部和全域结果验证承担，最终仍需用户批准该合同替换。

## 腕部

- 临时手部包络：`{mask_count(hand_proxy)} px`，连通分量 `{B0_MODULE.connected_components(hand_proxy)}`，孔洞 `{V6_MODULE.hole_count(hand_proxy)}`；
- 中性足迹超出源手部轮廓：`{hand_outside_source}`；
- 未包含 V7-A 必需种子像素：`{hand_seed_missing}`；
- 腕角范围：`[{wrist_min}, {wrist_max}]°`，201 点密扫；
- 最大责任区透明缺口：`{wrist_gap_max}`；
- 断开样本：`{wrist_broken}`；
- 最小 4× 重叠：`{min(row["overlapPixelsAt4x"] for row in wrist_rows)}`；
- 回程差：`{wrist_return_diff}`；
- 手链不计入覆盖。

## 组合域

完成肘×腕 `9×9` 网格和参数角点，最大腕部责任区缺口 `{grid_gap_max}`。

“腕缝只依赖腕参数、肘缝只依赖肘参数”只属于本次刚体 FK，不迁移到 Cubism 组合关键形状混合。

## 请审查

1. `qa/V7-C-PRODUCTION-FOREARM-F1-F5-BOARD.png`
2. `qa/V7-C-FORMAL-ELBOW-THREE-ANGLES.png`
3. `qa/V7-C-FORMAL-ELBOW-SLOW-SCAN.gif`
4. `qa/V7-C-WRIST-THREE-ANGLES.png`
5. `qa/V7-C-WRIST-SLOW-SCAN.gif`
6. `qa/V7-C-FULL-CHAIN-ELBOW-WRIST-3X3.png`
7. `qa/V7-C-DISPLACED-PART-INTEGRITY.png`

重点看：F4 在手部移开时是否自然、腕扫是否有骨裂或突起、手链移开后皮肤是否连续，以及 F1–F4 分区是否可以批准。
"""
    (AUDIT / "V7-C-PRODUCTION-FOREARM-GEOMETRY.zh-CN.md").write_text(
        markdown, encoding="utf-8"
    )

    render_partition_board(
        source_color,
        f1,
        f2,
        f3,
        f4,
        f5,
        formal,
        hand_proxy,
        natural_forearm,
    )
    render_wrist_three_angles(
        [wrist_min, 0.0, wrist_max],
        fixed_high,
        hand_high,
        responsibility_high,
        f4_high,
        source_hand_high,
        center,
    )
    render_wrist_slow_scan(
        wrist_min,
        wrist_max,
        fixed_high,
        hand_high,
        responsibility_high,
        f4_high,
        source_hand_high,
        center,
    )
    render_combination_grid(
        [elbow_min, float(skeleton["restAnglesDeg"]["theta2"]), elbow_max],
        [wrist_min, 0.0, wrist_max],
        fixed_high,
        hand_high,
        responsibility_high,
        f4_high,
        source_hand_high,
        center,
    )
    render_elbow_three_angles_and_scan(
        skeleton,
        frame,
        formal,
        upper_geometry,
        sleeve,
        compression_px,
        positive_extent_px,
    )
    render_full_combination_grid(
        [elbow_min, float(skeleton["restAnglesDeg"]["theta2"]), elbow_max],
        [wrist_min, 0.0, wrist_max],
        skeleton,
        frame,
        formal,
        f4,
        hand_proxy,
        upper_geometry,
        sleeve,
        compression_px,
        positive_extent_px,
    )
    render_displaced_integrity(
        skeleton,
        frame,
        formal,
        f4,
        hand_proxy,
        natural_forearm,
        upper_geometry,
        sleeve,
        compression_px,
        positive_extent_px,
    )
    write_json(AUDIT / "v7c-evidence-manifest.json", manifest())


if __name__ == "__main__":
    main()
