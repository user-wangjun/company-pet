from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
XIAOXING = ROOT.parents[1]
SOURCE = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
V31 = (
    XIAOXING
    / "validation/arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve"
)
V32 = (
    XIAOXING
    / "validation/arm-chain-screen-left-v32-hand-from-frozen-forearm"
)
SKELETON = V31 / "skeleton-lock.json"
FOREARM_COMPLETE_OLD = V31 / "masks/complete/forearm.png"
FOREARM_VISIBLE = V31 / "masks/visible/forearm.png"
FOREARM_HIDDEN_OLD = V31 / "masks/hidden/forearm.png"
BRACELET = V31 / "masks/visible/bracelet-owned-by-forearm.png"
REOPEN = (
    V31
    / "audit/user-authorized-reopen-forearm-wrist-ucap-2026-07-29.json"
)
V32_INVALIDATION = (
    V32 / "audit/v32-invalidated-by-forearm-reopen-2026-07-29.json"
)

W, H = 512, 1086
MOTION_W = 768
MOTION_OFFSET = np.array((160.0, 0.0))
S = np.array((170.0, 251.0))
E = np.array((147.0, 405.0))
WR = np.array((115.0, 529.0))
BLUE = (24, 151, 219, 255)
YELLOW = (198, 214, 0, 255)
ORANGE = (242, 155, 43, 255)
GREEN = (31, 166, 119, 255)
PURPLE = (148, 74, 184, 255)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def font(size: int, bold: bool = False):
    for name in (
        "msyhbd.ttc" if bold else "msyh.ttc",
        "simhei.ttf",
        "arial.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def checker(size: tuple[int, int], cell: int = 16) -> Image.Image:
    image = Image.new("RGB", size, (238, 241, 245))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle(
                    (x, y, min(size[0], x + cell), min(size[1], y + cell)),
                    fill=(208, 215, 224),
                )
    return image


def antialias(mask: np.ndarray) -> Image.Image:
    return Image.fromarray(mask).filter(ImageFilter.GaussianBlur(0.35))


def solid(mask: np.ndarray, color: tuple[int, int, int, int]) -> Image.Image:
    image = Image.new("RGBA", (W, H), color)
    image.putalpha(antialias(mask))
    return image


def solid_exact(
    mask: np.ndarray, color: tuple[int, int, int, int]
) -> Image.Image:
    image = Image.new("RGBA", (W, H), color)
    image.putalpha(
        Image.fromarray(
            np.where(mask > 8, color[3], 0).astype(np.uint8)
        )
    )
    return image


def save_mask(path: Path, mask: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.where(mask > 8, 255, 0).astype(np.uint8)).save(path)


def supersampled_polygon(
    points: list[tuple[float, float]], scale: int = 8
) -> np.ndarray:
    canvas = np.zeros((H * scale, W * scale), dtype=np.uint8)
    cv2.fillPoly(
        canvas,
        [np.round(np.asarray(points) * scale).astype(np.int32)],
        255,
        lineType=cv2.LINE_AA,
    )
    return np.asarray(
        Image.fromarray(canvas).resize((W, H), Image.Resampling.LANCZOS)
    )


def cubic(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    count: int = 48,
) -> list[tuple[float, float]]:
    points = []
    a, b, c, d = [np.asarray(point, dtype=np.float64) for point in (p0, p1, p2, p3)]
    for t in np.linspace(0.0, 1.0, count, endpoint=False):
        point = (
            (1 - t) ** 3 * a
            + 3 * (1 - t) ** 2 * t * b
            + 3 * (1 - t) * t**2 * c
            + t**3 * d
        )
        points.append((float(point[0]), float(point[1])))
    points.append(p3)
    return points


def largest_component(mask: np.ndarray) -> np.ndarray:
    binary = (mask > 8).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )
    if count <= 1:
        return np.zeros_like(mask)
    label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return np.where(labels == label, 255, 0).astype(np.uint8)


def components(mask: np.ndarray) -> int:
    return (
        cv2.connectedComponents((mask > 8).astype(np.uint8), connectivity=8)[
            0
        ]
        - 1
    )


def holes(mask: np.ndarray) -> int:
    contours, hierarchy = cv2.findContours(
        (mask > 8).astype(np.uint8) * 255,
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if hierarchy is None:
        return 0
    return sum(1 for item in hierarchy[0] if item[3] >= 0)


def fill_small_holes(
    mask: np.ndarray, maximum_area: float = 12.0
) -> np.ndarray:
    result = mask.copy()
    contours, hierarchy = cv2.findContours(
        (mask > 8).astype(np.uint8) * 255,
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if hierarchy is None:
        return result
    for contour, item in zip(contours, hierarchy[0]):
        if item[3] >= 0 and cv2.contourArea(contour) <= maximum_area:
            cv2.drawContours(result, [contour], -1, 255, cv2.FILLED)
    return result


def trace_visible_hand(source: Image.Image, bracelet: np.ndarray) -> np.ndarray:
    rgb = np.asarray(source.convert("RGB"), dtype=np.int16)
    roi = rgb[500:630, 58:143]
    r, g, b = roi[:, :, 0], roi[:, :, 1], roi[:, :, 2]
    chroma = np.max(roi, axis=2) - np.min(roi, axis=2)
    darkness = 252 - np.mean(roi, axis=2)

    envelope = np.zeros(roi.shape[:2], dtype=np.uint8)
    cv2.fillPoly(
        envelope,
        [
            np.array(
                [
                    (43, 24),
                    (72, 31),
                    (75, 56),
                    (68, 82),
                    (59, 112),
                    (43, 126),
                    (12, 124),
                    (6, 99),
                    (20, 70),
                    (31, 43),
                ],
                dtype=np.int32,
            )
        ],
        1,
    )
    grab = np.full(roi.shape[:2], cv2.GC_BGD, dtype=np.uint8)
    grab[envelope > 0] = cv2.GC_PR_BGD
    warm = (
        (r - b >= 7)
        & (r - g >= 2)
        & (r >= 145)
        & (darkness >= 5)
    )
    strong_skin = (
        (r - b >= 16)
        & (r - g >= 7)
        & (r >= 178)
        & (g >= 135)
    )
    contour = (darkness >= 38) & (chroma >= 5)
    grab[(warm | contour) & (envelope > 0)] = cv2.GC_PR_FGD
    grab[strong_skin & (envelope > 0)] = cv2.GC_FGD
    grab[42:72, 34:59] = cv2.GC_FGD
    grab[53:80, 25:43] = cv2.GC_FGD
    neutral = (
        (np.mean(roi, axis=2) >= 247)
        & (chroma <= 5)
        & (envelope > 0)
    )
    grab[neutral] = cv2.GC_BGD
    bg_model = np.zeros((1, 65), dtype=np.float64)
    fg_model = np.zeros((1, 65), dtype=np.float64)
    cv2.grabCut(
        roi.astype(np.uint8),
        grab,
        None,
        bg_model,
        fg_model,
        7,
        cv2.GC_INIT_WITH_MASK,
    )
    keep = np.where(
        (grab == cv2.GC_FGD) | (grab == cv2.GC_PR_FGD), 1, 0
    ).astype(np.uint8)
    count, labels, _, _ = cv2.connectedComponentsWithStats(
        keep, connectivity=8
    )
    wrist_labels = {
        int(value)
        for value in np.unique(labels[24:48, 37:68])
        if value != 0
    }
    keep = np.where(np.isin(labels, list(wrist_labels)), 1, 0).astype(
        np.uint8
    )
    visible = np.zeros((H, W), dtype=np.uint8)
    visible[500:630, 58:143] = keep * 255

    # The top and both sides are clipped only by the Reset-derived hand
    # corridor. This is not a replacement silhouette; it excludes bracelet and
    # neighboring background classifications.
    skin_corridor = supersampled_polygon(
        [
            (99, 527),
            (106, 530),
            (116, 532),
            (127, 535),
            (132, 541),
            (132, 558),
            (126, 576),
            (116, 603),
            (108, 616),
            (96, 622),
            (77, 623),
            (63, 616),
            (61, 604),
            (67, 590),
            (78, 576),
            (88, 558),
        ]
    )
    visible = cv2.bitwise_and(visible, skin_corridor)
    visible[cv2.dilate(bracelet, np.ones((3, 3), np.uint8)) > 8] = 0
    full_rgb = np.asarray(source.convert("RGB"), dtype=np.int16)
    full_chroma = np.max(full_rgb, axis=2) - np.min(full_rgb, axis=2)
    neutral_background = (
        (np.mean(full_rgb, axis=2) >= 247) & (full_chroma <= 5)
    )
    visible[neutral_background] = 0
    visible = fill_small_holes(visible)
    visible[neutral_background] = 0

    # Preserve the Reset outer wrist edge as open background. This prevents
    # neutral boundary pixels from becoming artificial closed holes.
    outer_wrist_background = supersampled_polygon(
        [
            (0, 500),
            (101, 500),
            (101, 533),
            (98, 538),
            (96, 543),
            (94, 548),
            (90, 555),
            (0, 555),
        ]
    )
    visible[outer_wrist_background > 8] = 0

    # Keep the Reset thumb/index gap open to the background.
    thumb_gap = supersampled_polygon(
        [
            (96.2, 574.0),
            (100.0, 573.5),
            (101.5, 584.0),
            (101.0, 591.0),
            (105.0, 599.5),
            (110.5, 602.0),
            (108.5, 605.0),
            (103.5, 602.5),
            (98.0, 594.0),
            (95.2, 583.0),
        ]
    )
    visible[thumb_gap > 8] = 0
    return largest_component(visible)


def blue_forearm_ucap() -> tuple[
    np.ndarray,
    list[tuple[float, float]],
    list[tuple[float, float]],
]:
    # Blue line: both sides sample the Reset wrist skin boundary, and the
    # distal closure follows the palm-facing U drawn by the user.
    boundary = [
        (105, 529),
        (103, 536),
        (101, 543),
        (99, 549),
        (100, 556),
        (107, 561),
        (114, 558),
        (117, 554),
        (120, 548),
        (122, 540),
        (124, 532),
    ]
    # This small proximal underlap joins the U-cap to the existing forearm
    # beneath the bracelet. Its outer edge uses the same Reset wrist span; it
    # is not a free-floating mechanical bridge.
    attachment = [
        (99, 528),
        (105, 528),
        (107, 531),
        (104, 533),
        (99, 531),
    ]
    mask = np.maximum(
        supersampled_polygon(boundary),
        supersampled_polygon(attachment),
    )
    return mask, boundary, attachment


def yellow_hand_root() -> tuple[np.ndarray, list[tuple[float, float]]]:
    # Yellow line: a larger complete hand root following the Reset hand/palm
    # skin boundary. It covers the blue U-cap without leaving the skin envelope.
    boundary = [
        (94, 523),
        (133, 530),
        (131, 545),
        (127, 557),
        (122, 570),
        (115, 580),
        (105, 584),
        (94, 580),
        (86, 563),
        (90, 549),
        (94, 537),
    ]
    return supersampled_polygon(boundary), boundary


def compose(
    layers: list[Image.Image],
    size: tuple[int, int] = (W, H),
    background: Image.Image | None = None,
) -> Image.Image:
    canvas = (
        background.convert("RGBA").copy()
        if background is not None
        else Image.new("RGBA", size, (0, 0, 0, 0))
    )
    for layer in layers:
        canvas.alpha_composite(layer)
    return canvas


def crop_hand(image: Image.Image, scale: int = 6) -> Image.Image:
    crop = image.crop((70, 505, 138, 585))
    return crop.resize(
        (crop.width * scale, crop.height * scale),
        Image.Resampling.NEAREST,
    )


def fit(
    board: Image.Image,
    image: Image.Image,
    box: tuple[int, int, int, int],
    label: str,
) -> None:
    x0, y0, x1, y1 = box
    available_w = x1 - x0
    available_h = y1 - y0 - 52
    copy = image.copy()
    copy.thumbnail((available_w, available_h), Image.Resampling.LANCZOS)
    px = x0 + (available_w - copy.width) // 2
    py = y0 + 46 + (available_h - copy.height) // 2
    board.paste(copy.convert("RGB"), (px, py))
    ImageDraw.Draw(board).text(
        (x0 + 10, y0 + 7),
        label,
        fill=(18, 28, 43),
        font=font(22, True),
    )


def draw_boundary(
    image: Image.Image,
    points: list[tuple[float, float]],
    color: tuple[int, int, int, int],
    width: int = 3,
) -> None:
    draw = ImageDraw.Draw(image)
    draw.line([*points, points[0]], fill=color, width=width, joint="curve")


def rotate_translate(
    image: Image.Image,
    old_pivot: np.ndarray,
    new_pivot: np.ndarray,
    angle_deg: float,
    size: tuple[int, int] = (W, H),
    offset: np.ndarray | None = None,
) -> Image.Image:
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    ox, oy = old_pivot
    target = np.asarray(new_pivot, dtype=np.float64)
    if offset is not None:
        target = target + offset
    nx, ny = target
    return image.transform(
        size,
        Image.Transform.AFFINE,
        (
            c,
            s,
            ox - c * nx - s * ny,
            -s,
            c,
            oy + s * nx - c * ny,
        ),
        resample=Image.Resampling.BICUBIC,
    )


def point_at(origin: np.ndarray, length: float, angle_deg: float) -> np.ndarray:
    angle = math.radians(angle_deg)
    return np.array(
        (
            origin[0] + length * math.cos(angle),
            origin[1] + length * math.sin(angle),
        )
    )


def alpha(image: Image.Image) -> np.ndarray:
    return np.asarray(image.getchannel("A")) > 8


def build_motion(
    skeleton: dict,
    forearm_layer: Image.Image,
    bracelet_layer: Image.Image,
    hand_layer: Image.Image,
    ucap_layer: Image.Image,
):
    rest1 = skeleton["restAnglesDeg"]["theta1"]
    rest2 = skeleton["restAnglesDeg"]["theta2"]
    target = skeleton["stageAQaMotion"]["target"]
    l1 = skeleton["boneLengthsPx"]["L1ShoulderToElbow"]
    l2 = skeleton["boneLengthsPx"]["L2ElbowToWrist"]
    rest_global = math.degrees(math.atan2(WR[1] - E[1], WR[0] - E[0]))
    samples = []
    frames = []
    selected = {}
    first_hash = last_hash = None
    for index in range(41):
        k = index if index <= 20 else 40 - index
        progress = 0.5 * (1 - math.cos(math.pi * k / 20.0))
        theta1 = rest1 + (target["theta1"] - rest1) * progress
        theta2 = rest2 + (target["theta2"] - rest2) * progress
        new_elbow = point_at(S, l1, theta1)
        new_wrist = point_at(new_elbow, l2, theta1 + theta2)
        forearm_delta = theta1 + theta2 - rest_global
        wrist_delta = forearm_delta + target["wristLocal"] * progress
        posed_forearm = rotate_translate(
            forearm_layer,
            E,
            new_elbow,
            forearm_delta,
            (MOTION_W, H),
            MOTION_OFFSET,
        )
        posed_bracelet = rotate_translate(
            bracelet_layer,
            E,
            new_elbow,
            forearm_delta,
            (MOTION_W, H),
            MOTION_OFFSET,
        )
        posed_hand = rotate_translate(
            hand_layer,
            WR,
            new_wrist,
            wrist_delta,
            (MOTION_W, H),
            MOTION_OFFSET,
        )
        posed_ucap = rotate_translate(
            ucap_layer,
            E,
            new_elbow,
            forearm_delta,
            (MOTION_W, H),
            MOTION_OFFSET,
        )
        leak = alpha(posed_ucap) & ~alpha(posed_hand)
        overlap = int(np.count_nonzero(alpha(posed_forearm) & alpha(posed_hand)))
        union = alpha(posed_forearm) | alpha(posed_hand)
        disconnected = (
            cv2.connectedComponents(union.astype(np.uint8), connectivity=8)[
                0
            ]
            - 1
            != 1
        )
        pose = compose(
            [posed_forearm, posed_hand, posed_bracelet],
            (MOTION_W, H),
        )
        digest = hashlib.sha256(pose.tobytes()).hexdigest()
        first_hash = digest if index == 0 else first_hash
        last_hash = digest if index == 40 else last_hash
        sample = {
            "index": index,
            "progress": progress,
            "L1Px": float(np.linalg.norm(new_elbow - S)),
            "L2Px": float(np.linalg.norm(new_wrist - new_elbow)),
            "completeOverlapPx": overlap,
            "ucapExposedPx": int(np.count_nonzero(leak)),
            "disconnected": bool(disconnected),
        }
        samples.append(sample)

        center = new_wrist + MOTION_OFFSET
        box = (
            max(0, int(center[0]) - 62),
            max(0, int(center[1]) - 42),
            min(MOTION_W, int(center[0]) + 62),
            min(H, int(center[1]) + 132),
        )
        detail = pose.crop(box)
        backing = checker(detail.size).convert("RGBA")
        backing.alpha_composite(detail)
        backing = backing.resize((268, 374), Image.Resampling.LANCZOS)
        frame = Image.new("RGB", (280, 420), (241, 245, 250))
        frame.paste(backing.convert("RGB"), (6, 34))
        ImageDraw.Draw(frame).text(
            (8, 6),
            f"{index:02d}｜重叠 {overlap}px｜外露 {sample['ucapExposedPx']}px",
            fill=(18, 28, 43),
            font=font(14, True),
        )
        frames.append(frame)
        if index in (0, 5, 10, 15, 20, 25, 30, 35, 40):
            selected[index] = frame

    save_json(ROOT / "samples/fk-41-samples.json", samples)
    frames[0].save(
        ROOT / "qa/fk-41-slow-preview.gif",
        save_all=True,
        append_images=frames[1:],
        duration=210,
        loop=0,
        disposal=2,
    )
    sheet = Image.new("RGB", (840, 1260), (241, 245, 250))
    for position, index in enumerate(
        (0, 5, 10, 15, 20, 25, 30, 35, 40)
    ):
        row, column = divmod(position, 3)
        sheet.paste(selected[index], (column * 280, row * 420))
    sheet.save(ROOT / "qa/fk-key-wrist-samples.png")
    return samples, first_hash, last_hash


def build_stress(
    hand_layer: Image.Image,
    ucap_layer: Image.Image,
) -> list[dict]:
    angles = (-12, -8, -4, 0, 4, 8, 12)
    results = []
    board = Image.new("RGB", (2100, 650), (241, 245, 250))
    for column, angle in enumerate(angles):
        hand = rotate_translate(hand_layer, WR, WR, angle)
        leak = alpha(ucap_layer) & ~alpha(hand)
        count = int(np.count_nonzero(leak))
        results.append({"wristRelativeDeg": angle, "ucapExposedPx": count})
        diagnostic = checker((W, H)).convert("RGBA")
        translucent = hand.copy()
        translucent.putalpha(
            translucent.getchannel("A").point(lambda value: value * 0.34)
        )
        diagnostic.alpha_composite(translucent)
        diagnostic.alpha_composite(ucap_layer)
        if count:
            diagnostic.alpha_composite(
                solid(leak.astype(np.uint8) * 255, (255, 222, 45, 255))
            )
        fit(
            board,
            crop_hand(diagnostic, 5),
            (column * 300 + 8, 15, column * 300 + 292, 610),
            f"{angle:+d}°｜外露 {count}px",
        )
    ImageDraw.Draw(board).text(
        (25, 615),
        "蓝/红=重开的前臂 U 形凸包；半透明绿=沿皮肤边界的手部覆盖。±12°仅为压力检查。",
        fill=(58, 71, 91),
        font=font(19, True),
    )
    board.save(ROOT / "qa/wrist-stress-review.png")
    return results


def main() -> None:
    for folder in (
        "masks/visible",
        "masks/hidden",
        "masks/complete",
        "materials",
        "qa",
        "samples",
        "audit",
    ):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)

    reopen = json.loads(REOPEN.read_text(encoding="utf-8"))
    invalidation = json.loads(V32_INVALIDATION.read_text(encoding="utf-8"))
    assert reopen["status"] == "user_authorized_scope_limited_reopen"
    assert (
        invalidation["status"]
        == "invalidated_by_user_authorized_upstream_reopen"
    )

    source = Image.open(SOURCE).convert("RGBA")
    skeleton = json.loads(SKELETON.read_text(encoding="utf-8"))
    old_forearm = np.asarray(
        Image.open(FOREARM_COMPLETE_OLD).convert("L"), dtype=np.uint8
    )
    visible_forearm = np.asarray(
        Image.open(FOREARM_VISIBLE).convert("L"), dtype=np.uint8
    )
    old_hidden = np.asarray(
        Image.open(FOREARM_HIDDEN_OLD).convert("L"), dtype=np.uint8
    )
    bracelet = np.asarray(
        Image.open(BRACELET).convert("L"), dtype=np.uint8
    )

    blue_ucap, blue_boundary, blue_attachment = blue_forearm_ucap()
    yellow_root, yellow_boundary = yellow_hand_root()
    visible_hand = trace_visible_hand(source, bracelet)

    yy, xx = np.indices((H, W))
    u = (WR - E) / np.linalg.norm(WR - E)
    projection = (xx - WR[0]) * u[0] + (yy - WR[1]) * u[1]
    revised_forearm = old_forearm.copy()
    reopened_region = projection >= -4.0
    revised_forearm[reopened_region] = visible_forearm[reopened_region]
    revised_forearm = np.maximum(revised_forearm, blue_ucap)
    revised_forearm = np.maximum(revised_forearm, bracelet)
    revised_hidden = cv2.subtract(revised_forearm, visible_forearm)

    # The visible hand never owns bracelet pixels. The complete hand root may
    # pass behind the forearm-owned bracelet so independent wrist rotation does
    # not turn the bracelet cutout into a seam.
    complete_hand = np.maximum(visible_hand, yellow_root)
    complete_hand = largest_component(complete_hand)
    hidden_hand = cv2.subtract(complete_hand, visible_hand)

    save_mask(ROOT / "masks/visible/forearm.png", visible_forearm)
    save_mask(ROOT / "masks/hidden/forearm.png", revised_hidden)
    save_mask(ROOT / "masks/complete/forearm.png", revised_forearm)
    save_mask(ROOT / "masks/reference/blue-forearm-ucap.png", blue_ucap)
    save_mask(ROOT / "masks/visible/hand.png", visible_hand)
    save_mask(ROOT / "masks/hidden/hand.png", hidden_hand)
    save_mask(ROOT / "masks/complete/hand.png", complete_hand)
    save_mask(ROOT / "masks/reference/yellow-hand-root.png", yellow_root)

    forearm_layer = solid(revised_forearm, ORANGE)
    bracelet_layer = solid(bracelet, PURPLE)
    hand_layer = solid(complete_hand, GREEN)
    ucap_layer = solid_exact(blue_ucap, (230, 64, 55, 255))
    forearm_layer.save(ROOT / "materials/forearm.png")
    hand_layer.save(ROOT / "materials/hand.png")

    default = compose(
        [forearm_layer, hand_layer, bracelet_layer],
        background=checker((W, H)),
    )
    default.save(ROOT / "qa/default-solid-recomposition.png")

    boundary_overlay = source.copy()
    draw_boundary(boundary_overlay, blue_boundary, BLUE, 3)
    draw_boundary(boundary_overlay, blue_attachment, BLUE, 3)
    draw_boundary(boundary_overlay, yellow_boundary, YELLOW, 3)
    boundary_overlay.save(ROOT / "qa/reset-blue-yellow-boundaries.png")

    diagnostic = checker((W, H)).convert("RGBA")
    translucent_hand = hand_layer.copy()
    translucent_hand.putalpha(
        translucent_hand.getchannel("A").point(lambda value: value * 0.34)
    )
    diagnostic.alpha_composite(translucent_hand)
    diagnostic.alpha_composite(ucap_layer)
    diagnostic.alpha_composite(bracelet_layer)
    draw_boundary(diagnostic, blue_boundary, BLUE, 3)
    draw_boundary(diagnostic, blue_attachment, BLUE, 3)
    draw_boundary(diagnostic, yellow_boundary, YELLOW, 3)
    diagnostic.save(ROOT / "qa/blue-yellow-coverage-diagnostic.png")

    displaced = checker((W, H)).convert("RGBA")
    displaced.alpha_composite(hand_layer)
    moved_forearm = forearm_layer.transform(
        (W, H),
        Image.Transform.AFFINE,
        (1, 0, -145, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )
    moved_bracelet = bracelet_layer.transform(
        (W, H),
        Image.Transform.AFFINE,
        (1, 0, -145, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )
    displaced.alpha_composite(moved_forearm)
    displaced.alpha_composite(moved_bracelet)
    displaced.save(ROOT / "qa/forearm-displaced-hand-root.png")

    samples, first_hash, last_hash = build_motion(
        skeleton,
        forearm_layer,
        bracelet_layer,
        hand_layer,
        ucap_layer,
    )
    stress = build_stress(hand_layer, ucap_layer)

    minimum_overlap = min(item["completeOverlapPx"] for item in samples)
    max_fk_leak = max(item["ucapExposedPx"] for item in samples)
    max_stress_leak = max(item["ucapExposedPx"] for item in stress)
    disconnects = sum(item["disconnected"] for item in samples)
    bracelet_visible_duplication = int(
        np.count_nonzero((visible_hand > 8) & (bracelet > 8))
    )
    bracelet_hidden_underlap = int(
        np.count_nonzero((hidden_hand > 8) & (bracelet > 8))
    )
    max_l1_error = max(
        abs(
            item["L1Px"]
            - skeleton["boneLengthsPx"]["L1ShoulderToElbow"]
        )
        for item in samples
    )
    max_l2_error = max(
        abs(
            item["L2Px"] - skeleton["boneLengthsPx"]["L2ElbowToWrist"]
        )
        for item in samples
    )
    engineering_pass = (
        components(revised_forearm) == 1
        and components(complete_hand) == 1
        and holes(complete_hand) == 0
        and disconnects == 0
        and first_hash == last_hash
        and bracelet_visible_duplication == 0
        and max_fk_leak == 0
        and max_stress_leak == 0
        and max_l1_error <= 0.01
        and max_l2_error <= 0.01
    )
    report = {
        "schemaVersion": 1,
        "status": (
            "engineering_pass_pending_user_visual_approval"
            if engineering_pass
            else "engineering_fail_stop_stage_a"
        ),
        "scope": "screen-left forearm U-cap and dependent hand hidden root Stage A",
        "authoritativeInputs": {
            "reset": {
                "path": "../../source/masters/front-color-source-exact-after-reset.png",
                "sha256": sha256(SOURCE),
            },
            "skeleton": {
                "path": (
                    "../arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve/"
                    "skeleton-lock.json"
                ),
                "sha256": sha256(SKELETON),
            },
            "reopenAuthorization": {
                "path": (
                    "../arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve/"
                    "audit/user-authorized-reopen-forearm-wrist-ucap-2026-07-29.json"
                ),
                "sha256": sha256(REOPEN),
            },
        },
        "boundaryConstruction": {
            "rule": "every blue and yellow control point follows the corresponding Reset skin boundary",
            "blueForearmUCapPoints": blue_boundary,
            "blueForearmProximalUnderlapPoints": blue_attachment,
            "yellowHandRootPoints": yellow_boundary,
            "circlePatchUsed": False,
            "straightMechanicalExpansionUsed": False,
            "scaleUsedToHideSeam": False,
        },
        "geometry": {
            "forearmComponents": components(revised_forearm),
            "handComponents": components(complete_hand),
            "handClosedHoles": holes(complete_hand),
            "braceletVisiblePixelDuplicationPx": (
                bracelet_visible_duplication
            ),
            "braceletHiddenUnderlapPx": bracelet_hidden_underlap,
            "braceletHiddenUnderlapExpected": True,
        },
        "motion": {
            "sampleCount": 41,
            "minimumCompleteOverlapPx": minimum_overlap,
            "disconnectCount": disconnects,
            "maximumUCapExposurePx": max_fk_leak,
            "returnConsistency": first_hash == last_hash,
            "maxL1ErrorPx": max_l1_error,
            "maxL2ErrorPx": max_l2_error,
        },
        "wristStress": {
            "results": stress,
            "maximumUCapExposurePx": max_stress_leak,
            "rangeIsApprovedMotion": False,
        },
        "visualGate": {
            "status": "pending_user_visual_approval",
            "review": "qa/V33-蓝黄边界-中文视觉审查板.png",
            "forearmUCapFrozen": False,
            "handFrozen": False,
        },
        "earliestFailurePoint": (
            "none_in_machine_checks_pending_user_visual_review"
            if engineering_pass
            else "one or more Stage A geometry or motion checks failed"
        ),
        "stop": "remain at Stage A pending user visual approval",
    }
    save_json(ROOT / "audit/machine-report.json", report)

    board = Image.new("RGB", (3200, 4200), (238, 243, 249))
    draw = ImageDraw.Draw(board)
    draw.text(
        (60, 28),
        "小星 V33｜蓝色前臂凸包＋黄色手部覆盖边界",
        fill=(18, 28, 43),
        font=font(46, True),
    )
    draw.text(
        (60, 92),
        "两条线均沿 Reset 皮肤边界；紫=冻结手链，橙=前臂，绿=手。当前仅供视觉审查，尚未冻结。",
        fill=(58, 71, 91),
        font=font(26),
    )
    items = [
        (crop_hand(source, 8), "1. Reset 腕部原图｜只认真实皮肤边界"),
        (
            crop_hand(boundary_overlay, 8),
            "2. 蓝线=前臂 U 凸包｜黄线=手部覆盖边界",
        ),
        (
            crop_hand(
                compose(
                    [solid(blue_ucap, BLUE)],
                    background=checker((W, H)),
                ),
                8,
            ),
            "3. 修改后的蓝色前臂凸包｜两侧贴腕、底部自然 U 形",
        ),
        (
            crop_hand(
                compose(
                    [solid(yellow_root, YELLOW)],
                    background=checker((W, H)),
                ),
                8,
            ),
            "4. 修改后的黄色手部隐藏根｜沿手腕进入手掌",
        ),
        (crop_hand(default, 8), "5. 默认纯色回组｜看腕宽、手链与接缝"),
        (
            crop_hand(diagnostic, 8),
            "6. 半透明覆盖｜蓝色凸包必须完全处于黄色边界内",
        ),
        (
            Image.open(ROOT / "qa/fk-key-wrist-samples.png").convert("RGB"),
            "7. 41 帧关键腕部样本｜查橙漏、绿窜和透明缝",
        ),
        (
            Image.open(ROOT / "qa/wrist-stress-review.png").convert("RGB"),
            "8. ±12°压力检查｜仅查覆盖，不代表动作批准",
        ),
    ]
    for index, (image, label) in enumerate(items):
        row, column = divmod(index, 2)
        fit(
            board,
            image,
            (
                45 + column * 1580,
                140 + row * 925,
                1555 + column * 1580,
                1035 + row * 925,
            ),
            label,
        )
    draw.rounded_rectangle(
        (65, 3830, 3135, 4140),
        radius=22,
        fill="white",
        outline=(170, 183, 200),
        width=3,
    )
    draw.text(
        (95, 3860),
        "请审查：①蓝线两侧是否沿前臂腕部皮肤？ ②蓝线底部是否为自然 U 形？",
        fill=(35, 48, 64),
        font=font(24, True),
    )
    draw.text(
        (95, 3915),
        "③黄线是否沿手腕进入手掌的皮肤边界？ ④黄色覆盖是否完整包住蓝线？",
        fill=(35, 48, 64),
        font=font(24, True),
    )
    draw.text(
        (95, 3970),
        "⑤默认腕宽是否像 Reset？ ⑥有没有圆片、硬扩、橙漏、绿窜或透明缝？",
        fill=(35, 48, 64),
        font=font(24, True),
    )
    draw.text(
        (95, 4045),
        (
            f"机器：最小重叠 {minimum_overlap}px｜41 帧最大外露 {max_fk_leak}px｜"
            f"压力最大外露 {max_stress_leak}px｜前臂凸包和手部均未冻结"
        ),
        fill=(20, 102, 77)
        if report["status"]
        == "engineering_pass_pending_user_visual_approval"
        else (178, 50, 43),
        font=font(23, True),
    )
    board.save(ROOT / "qa/V33-蓝黄边界-中文视觉审查板.png")

    paths = [
        "masks/visible/forearm.png",
        "masks/hidden/forearm.png",
        "masks/complete/forearm.png",
        "masks/reference/blue-forearm-ucap.png",
        "masks/visible/hand.png",
        "masks/hidden/hand.png",
        "masks/complete/hand.png",
        "masks/reference/yellow-hand-root.png",
        "materials/forearm.png",
        "materials/hand.png",
        "qa/default-solid-recomposition.png",
        "qa/reset-blue-yellow-boundaries.png",
        "qa/blue-yellow-coverage-diagnostic.png",
        "qa/forearm-displaced-hand-root.png",
        "qa/fk-41-slow-preview.gif",
        "qa/fk-key-wrist-samples.png",
        "qa/wrist-stress-review.png",
        "qa/V33-蓝黄边界-中文视觉审查板.png",
        "samples/fk-41-samples.json",
        "audit/machine-report.json",
        "tools/build_v33_skin_boundary_wrist.py",
    ]
    save_json(
        ROOT / "audit/artifact-manifest.json",
        {
            "schemaVersion": 1,
            "status": "stage_a_candidate_pending_user_visual_approval",
            "artifacts": [
                {"path": path, "sha256": sha256(ROOT / path)}
                for path in paths
            ],
            "forearmUCapFrozen": False,
            "handFrozen": False,
        },
    )


if __name__ == "__main__":
    main()
