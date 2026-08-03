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
UPPER_FREEZE = (
    V31 / "audit/v31-upper-arm-geometry-freeze-manifest-2026-07-28.json"
)
FOREARM_FREEZE = (
    V31 / "audit/v31-forearm-geometry-freeze-manifest-2026-07-29.json"
)
V31_SKELETON = V31 / "skeleton-lock.json"
FROZEN_FOREARM = V31 / "masks/complete/forearm.png"
FROZEN_FOREARM_VISIBLE = V31 / "masks/visible/forearm.png"
FROZEN_FOREARM_HIDDEN = V31 / "masks/hidden/forearm.png"
FROZEN_BRACELET = V31 / "masks/visible/bracelet-owned-by-forearm.png"
FAILED_V31_HAND = V31 / "masks/complete/hand.png"

W, H = 512, 1086
MOTION_W = 768
MOTION_OFFSET = np.array((160.0, 0.0))
S = np.array((170.0, 251.0))
E = np.array((147.0, 405.0))
WR = np.array((115.0, 529.0))
HAND_COLOR = (31, 166, 119, 255)
FOREARM_COLOR = (242, 155, 43, 255)
BRACELET_COLOR = (148, 74, 184, 255)


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


def verify_freeze_manifest(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = []
    for item in [*manifest["lockedGeometry"], manifest["userApproval"]]:
        target = V31 / item["path"]
        actual = sha256(target) if target.is_file() else None
        checks.append(
            {
                "path": item["path"],
                "expectedSha256": item["sha256"],
                "actualSha256": actual,
                "match": actual == item["sha256"],
            }
        )
    if not all(item["match"] for item in checks):
        raise RuntimeError("冻结上游材料哈希不一致")
    return {
        "manifest": manifest_path.relative_to(XIAOXING).as_posix(),
        "manifestSha256": sha256(manifest_path),
        "status": manifest["status"],
        "checks": checks,
        "pass": True,
    }


def checker(size: tuple[int, int], cell: int = 16) -> Image.Image:
    image = Image.new("RGB", size, (238, 241, 245))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle(
                    (x, y, min(size[0], x + cell), min(size[1], y + cell)),
                    fill=(210, 216, 224),
                )
    return image


def antialias(mask: np.ndarray) -> Image.Image:
    return Image.fromarray(mask).filter(ImageFilter.GaussianBlur(0.36))


def solid(mask: np.ndarray, color: tuple[int, int, int, int]) -> Image.Image:
    image = Image.new("RGBA", (W, H), color)
    image.putalpha(antialias(mask))
    return image


def solid_exact(
    mask: np.ndarray, color: tuple[int, int, int, int]
) -> Image.Image:
    image = Image.new("RGBA", (W, H), color)
    alpha_scale = color[3] / 255.0
    image.putalpha(
        Image.fromarray(
            np.where(
                mask > 8,
                round(255 * alpha_scale),
                0,
            ).astype(np.uint8)
        )
    )
    return image


def fit(
    board: Image.Image,
    image: Image.Image,
    box: tuple[int, int, int, int],
    label: str,
) -> None:
    x0, y0, x1, y1 = box
    available_w = x1 - x0
    available_h = y1 - y0 - 54
    copy = image.copy()
    copy.thumbnail((available_w, available_h), Image.Resampling.LANCZOS)
    px = x0 + (available_w - copy.width) // 2
    py = y0 + 48 + (available_h - copy.height) // 2
    board.paste(copy.convert("RGB"), (px, py))
    ImageDraw.Draw(board).text(
        (x0 + 12, y0 + 8),
        label,
        fill=(18, 28, 43),
        font=font(23, True),
    )


def crop_large(
    image: Image.Image,
    box: tuple[int, int, int, int] = (58, 500, 143, 630),
    scale: int = 6,
) -> Image.Image:
    crop = image.crop(box)
    return crop.resize(
        (crop.width * scale, crop.height * scale),
        Image.Resampling.NEAREST,
    )


def coordinate_grid(source: Image.Image) -> Image.Image:
    box = (58, 500, 143, 630)
    scale = 8
    crop = source.crop(box).resize(
        ((box[2] - box[0]) * scale, (box[3] - box[1]) * scale),
        Image.Resampling.NEAREST,
    )
    board = Image.new(
        "RGB", (crop.width + 140, crop.height + 120), (241, 245, 250)
    )
    board.paste(crop.convert("RGB"), (100, 70))
    draw = ImageDraw.Draw(board)
    for x in range(box[0], box[2] + 1, 5):
        px = 100 + (x - box[0]) * scale
        draw.line((px, 60, px, 70 + crop.height), fill=(40, 82, 125), width=1)
        draw.text((px - 12, 28), str(x), fill=(18, 28, 43), font=font(14))
    for y in range(box[1], box[3] + 1, 5):
        py = 70 + (y - box[1]) * scale
        draw.line((90, py, 100 + crop.width, py), fill=(40, 82, 125), width=1)
        draw.text((24, py - 8), str(y), fill=(18, 28, 43), font=font(14))
    return board


def foreground_hand_candidate(source: Image.Image) -> np.ndarray:
    rgb = np.asarray(source.convert("RGB"), dtype=np.int16)
    roi = rgb[500:630, 58:143]
    r, g, b = roi[:, :, 0], roi[:, :, 1], roi[:, :, 2]

    # Reset background is neutral and very bright. Skin, its anti-aliased
    # contour, and internal finger lines are warmer and/or darker. Keep the
    # background-connected negative spaces instead of filling an external hull.
    chroma = np.max(roi, axis=2) - np.min(roi, axis=2)
    darkness = 252 - np.mean(roi, axis=2)
    # Restrict to the authoritative hand corridor below the forearm-owned
    # bracelet. The polygon is only an exclusion envelope, not the hand shape.
    envelope = np.zeros(roi.shape[:2], dtype=np.uint8)
    cv2.fillPoly(
        envelope,
        [
            np.array(
                [
                    (45, 21),
                    (71, 29),
                    (75, 54),
                    (67, 82),
                    (58, 111),
                    (42, 125),
                    (12, 123),
                    (7, 98),
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
    # Interior palm seeds prevent GrabCut from fragmenting along the drawn
    # knuckle/finger lines. These seeds stay away from every real finger gap.
    grab[42:72, 34:59] = cv2.GC_FGD
    grab[53:80, 25:43] = cv2.GC_FGD
    neutral_background = (
        (np.mean(roi, axis=2) >= 247)
        & (chroma <= 5)
        & (envelope > 0)
    )
    grab[neutral_background] = cv2.GC_BGD
    background_model = np.zeros((1, 65), dtype=np.float64)
    foreground_model = np.zeros((1, 65), dtype=np.float64)
    cv2.grabCut(
        roi.astype(np.uint8),
        grab,
        None,
        background_model,
        foreground_model,
        7,
        cv2.GC_INIT_WITH_MASK,
    )
    keep = np.where(
        (grab == cv2.GC_FGD) | (grab == cv2.GC_PR_FGD), 1, 0
    ).astype(np.uint8)

    # Retain the wrist-connected body only. This removes the nearby skirt and
    # any isolated line noise while preserving background-connected finger gaps.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        keep, connectivity=8
    )
    wrist_labels = set(
        int(value)
        for value in np.unique(labels[24:48, 37:68])
        if value != 0
    )
    keep = np.where(np.isin(labels, list(wrist_labels)), 1, 0).astype(
        np.uint8
    )

    candidate = np.zeros((H, W), dtype=np.uint8)
    candidate[500:630, 58:143] = keep * 255
    candidate[np.asarray(Image.open(FROZEN_BRACELET).convert("L")) > 8] = 0
    return candidate


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


def fill_small_holes(mask: np.ndarray, maximum_area: float = 12.0) -> np.ndarray:
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


def largest_component(mask: np.ndarray) -> np.ndarray:
    binary = (mask > 8).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )
    if count <= 1:
        return np.zeros_like(mask)
    label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return np.where(labels == label, 255, 0).astype(np.uint8)


def supersampled_polygon(points: list[tuple[float, float]], scale: int = 8):
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


def refine_visible_hand(source: Image.Image) -> np.ndarray:
    visible = foreground_hand_candidate(source)
    bracelet = np.asarray(
        Image.open(FROZEN_BRACELET).convert("L"), dtype=np.uint8
    )

    # The top edge follows the Reset skin immediately below the forearm-owned
    # bracelet. It excludes the forearm and all dangling bracelet strokes.
    below_bracelet = supersampled_polygon(
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
    visible = cv2.bitwise_and(visible, below_bracelet)
    visible[cv2.dilate(bracelet, np.ones((3, 3), np.uint8)) > 8] = 0
    rgb = np.asarray(source.convert("RGB"), dtype=np.int16)
    chroma = np.max(rgb, axis=2) - np.min(rgb, axis=2)
    neutral_background = (np.mean(rgb, axis=2) >= 247) & (chroma <= 5)
    visible[neutral_background] = 0
    visible = fill_small_holes(visible)
    visible[neutral_background] = 0
    # The neutral pixels above lie on the Reset outer wrist edge. Connect them
    # to the surrounding background along that same edge instead of sealing
    # them as tiny transparent holes inside the complete material.
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

    # Reset contains an open thumb/index valley. GrabCut identifies the white
    # valley but can close its 1 px outlet, producing a prohibited hole. Open
    # the same valley along the observed Reset negative-space direction.
    negative_space = supersampled_polygon(
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
    visible[negative_space > 8] = 0
    visible = largest_component(visible)
    visible[bracelet > 8] = 0
    return visible


def continuous_hidden_wrist_root() -> np.ndarray:
    u = (WR - E) / np.linalg.norm(WR - E)
    n = np.array((-u[1], u[0]))
    stations = [
        (WR - u * 7.0, 14.0, 11.4),
        (WR + u * 2.0, 15.5, 12.5),
        (WR + u * 13.0, 15.8, 13.3),
        (WR + u * 24.0, 14.5, 12.6),
    ]
    outer = [center + n * left for center, left, _ in stations]
    inner = [center - n * right for center, _, right in stations]

    # Catmull-Rom sampling produces one continuous wrist/palm material with
    # skin-boundary-aligned sides and rounded transverse ends.
    def smooth_side(points: list[np.ndarray], samples_per_span: int = 32):
        padded = [points[0], *points, points[-1]]
        output = []
        for index in range(1, len(padded) - 2):
            p0, p1, p2, p3 = padded[index - 1 : index + 3]
            for t in np.linspace(0.0, 1.0, samples_per_span, endpoint=False):
                t2, t3 = t * t, t * t * t
                output.append(
                    0.5
                    * (
                        2 * p1
                        + (-p0 + p2) * t
                        + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                        + (-p0 + 3 * p1 - 3 * p2 + p3) * t3
                    )
                )
        output.append(points[-1])
        return output

    outer_curve = smooth_side(outer)
    inner_curve = smooth_side(inner)
    distal_center = stations[-1][0]
    distal_u = u
    distal_cap = []
    for angle in np.linspace(90, -90, 48):
        radians = math.radians(angle)
        distal_cap.append(
            distal_center
            + n * math.sin(radians) * 14.5
            + distal_u * math.cos(radians) * 3.0
        )
    proximal_center = stations[0][0]
    proximal_cap = []
    for angle in np.linspace(-90, 90, 40):
        radians = math.radians(angle)
        proximal_cap.append(
            proximal_center
            + n * math.sin(radians) * 14.0
            - u * math.cos(radians) * 2.0
        )
    polygon = [
        *outer_curve,
        *distal_cap,
        *reversed(inner_curve),
        *proximal_cap,
    ]
    return supersampled_polygon([(float(x), float(y)) for x, y in polygon])


def build_hand_masks(source: Image.Image):
    visible = refine_visible_hand(source)
    root = continuous_hidden_wrist_root()
    bracelet = np.asarray(
        Image.open(FROZEN_BRACELET).convert("L"), dtype=np.uint8
    )
    complete = np.maximum(visible, root)
    complete[bracelet > 8] = 0

    # Bracelet pixels cross the proximal edge, so they remain exterior
    # ownership, not enclosed holes. Remove any sub-pixel islands and retain
    # the single palm-connected body.
    complete = largest_component(complete)
    complete[bracelet > 8] = 0
    hidden = cv2.subtract(complete, visible)
    return visible, hidden, complete, root


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


def alpha_binary(image: Image.Image) -> np.ndarray:
    return np.asarray(image.getchannel("A")) > 8


def overlap_pixels(a: Image.Image, b: Image.Image) -> int:
    return int(np.count_nonzero(alpha_binary(a) & alpha_binary(b)))


def compose_layers(
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


def shifted(image: Image.Image, dx: int, dy: int = 0) -> Image.Image:
    return image.transform(
        image.size,
        Image.Transform.AFFINE,
        (1, 0, -dx, 0, 1, -dy),
        resample=Image.Resampling.BICUBIC,
    )


def outline(mask: np.ndarray, color: tuple[int, int, int, int], width=1):
    edge = cv2.morphologyEx(
        (mask > 8).astype(np.uint8) * 255,
        cv2.MORPH_GRADIENT,
        np.ones((3, 3), dtype=np.uint8),
    )
    if width > 1:
        edge = cv2.dilate(edge, np.ones((width, width), dtype=np.uint8))
    return solid(edge, color)


def hand_crop(image: Image.Image, scale: int = 5) -> Image.Image:
    return crop_large(image, (58, 500, 143, 630), scale)


def save_mask(path: Path, mask: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.where(mask > 8, 255, 0).astype(np.uint8)).save(path)


def build_motion_evidence(
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
    frames = []
    selected = {}
    samples = []
    first_hash = last_hash = None
    for index in range(41):
        mirrored_index = index if index <= 20 else 40 - index
        progress = 0.5 * (
            1 - math.cos(math.pi * mirrored_index / 20.0)
        )
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
        ucap_exposed = alpha_binary(posed_ucap) & ~alpha_binary(posed_hand)
        union = alpha_binary(posed_forearm) | alpha_binary(posed_hand)
        disconnected = (
            cv2.connectedComponents(union.astype(np.uint8), connectivity=8)[
                0
            ]
            - 1
            != 1
        )
        overlap = overlap_pixels(posed_forearm, posed_hand)
        pose = compose_layers(
            [posed_forearm, posed_hand, posed_bracelet],
            size=(MOTION_W, H),
        )
        digest = hashlib.sha256(pose.tobytes()).hexdigest()
        first_hash = digest if index == 0 else first_hash
        last_hash = digest if index == 40 else last_hash
        sample = {
            "index": index,
            "progress": progress,
            "elbowPx": [float(value) for value in new_elbow],
            "wristPx": [float(value) for value in new_wrist],
            "L1Px": float(np.linalg.norm(new_elbow - S)),
            "L2Px": float(np.linalg.norm(new_wrist - new_elbow)),
            "forearmHandCompleteOverlapPx": overlap,
            "forearmUCapExposedPx": int(np.count_nonzero(ucap_exposed)),
            "disconnected": bool(disconnected),
        }
        sample["pass"] = (
            overlap >= 510
            and sample["forearmUCapExposedPx"] == 0
            and not disconnected
        )
        samples.append(sample)

        bbox = pose.getchannel("A").getbbox()
        crop = pose.crop(
            (
                max(0, bbox[0] - 26),
                max(0, bbox[1] - 26),
                min(MOTION_W, bbox[2] + 26),
                min(H, bbox[3] + 26),
            )
        )
        backing = checker(crop.size).convert("RGBA")
        backing.alpha_composite(crop)
        backing.thumbnail((520, 760), Image.Resampling.LANCZOS)
        frame = Image.new("RGB", (560, 840), (241, 245, 250))
        frame.paste(
            backing.convert("RGB"),
            ((560 - backing.width) // 2, 54),
        )
        draw = ImageDraw.Draw(frame)
        draw.text(
            (18, 12),
            f"样本 {index:02d}｜进度 {progress:.3f}",
            fill=(18, 28, 43),
            font=font(21, True),
        )
        draw.text(
            (18, 806),
            f"重叠 {overlap}px｜凸包外露 {sample['forearmUCapExposedPx']}px",
            fill=(50, 68, 89),
            font=font(18),
        )
        frame.save(ROOT / f"samples/fk-{index:03d}.png")
        preview = frame.resize((280, 420), Image.Resampling.LANCZOS)
        frames.append(preview)
        if index in (0, 5, 10, 15, 20, 25, 30, 35, 40):
            center = new_wrist + MOTION_OFFSET
            detail_box = (
                max(0, int(round(center[0])) - 62),
                max(0, int(round(center[1])) - 42),
                min(MOTION_W, int(round(center[0])) + 62),
                min(H, int(round(center[1])) + 132),
            )
            detail = pose.crop(detail_box)
            detail_backing = checker(detail.size).convert("RGBA")
            detail_backing.alpha_composite(detail)
            detail_backing = detail_backing.resize(
                (268, 374), Image.Resampling.LANCZOS
            )
            selected_frame = Image.new("RGB", (280, 420), (241, 245, 250))
            selected_frame.paste(detail_backing.convert("RGB"), (6, 34))
            selected_draw = ImageDraw.Draw(selected_frame)
            selected_draw.text(
                (8, 6),
                f"{index:02d}｜重叠 {overlap}px｜外露 {sample['forearmUCapExposedPx']}px",
                fill=(18, 28, 43),
                font=font(14, True),
            )
            selected[index] = selected_frame

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
    sheet.save(ROOT / "qa/fk-key-samples.png")
    return samples, first_hash, last_hash


def build_stress_evidence(
    hand_layer: Image.Image,
    ucap_layer: Image.Image,
):
    angles = (-12, -8, -4, 0, 4, 8, 12)
    results = []
    board = Image.new("RGB", (2100, 640), (241, 245, 250))
    for column, angle in enumerate(angles):
        hand = rotate_translate(hand_layer, WR, WR, angle)
        leak = alpha_binary(ucap_layer) & ~alpha_binary(hand)
        leak_count = int(np.count_nonzero(leak))
        results.append(
            {"wristRelativeDeg": angle, "forearmUCapExposedPx": leak_count}
        )
        diagnostic = checker((W, H)).convert("RGBA")
        translucent = hand.copy()
        translucent.putalpha(
            translucent.getchannel("A").point(lambda value: value * 0.38)
        )
        diagnostic.alpha_composite(translucent)
        diagnostic.alpha_composite(ucap_layer)
        if leak_count:
            diagnostic.alpha_composite(
                solid(leak.astype(np.uint8) * 255, (255, 219, 45, 255))
            )
        fit(
            board,
            hand_crop(diagnostic, 4),
            (column * 300 + 8, 20, column * 300 + 292, 600),
            f"{angle:+d}°｜外露 {leak_count}px",
        )
    ImageDraw.Draw(board).text(
        (28, 604),
        "橙=冻结前臂 U 形凸包；半透明绿=完整手部；黄=外露。±12°仅用于穿模压力检查，不是批准动作范围。",
        fill=(74, 58, 40),
        font=font(20, True),
    )
    board.save(ROOT / "qa/wrist-relative-stress-review.png")
    return results


def build_exploration_board(
    source: Image.Image, candidate: np.ndarray
) -> Image.Image:
    source_zoom = crop_large(source)
    mask_rgba = checker((W, H)).convert("RGBA")
    mask_rgba.alpha_composite(solid(candidate, HAND_COLOR))
    overlay = source.convert("RGBA").copy()
    tint = solid(candidate, (31, 166, 119, 145))
    overlay.alpha_composite(tint)
    failed = np.asarray(
        Image.open(FAILED_V31_HAND).convert("L"), dtype=np.uint8
    )
    comparison = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    comparison.alpha_composite(solid(failed, (225, 65, 65, 125)))
    comparison.alpha_composite(solid(candidate, (31, 166, 119, 165)))

    board = Image.new("RGB", (2040, 920), (241, 245, 250))
    fit(board, source_zoom, (20, 20, 500, 880), "① Reset 权威手部")
    fit(
        board,
        crop_large(mask_rgba),
        (520, 20, 1000, 880),
        "② 保留指缝的直接候选",
    )
    fit(
        board,
        crop_large(overlay),
        (1020, 20, 1500, 880),
        "③ 候选叠 Reset",
    )
    fit(
        board,
        crop_large(comparison),
        (1520, 20, 2020, 880),
        "④ 失败 V31 红 / V32 绿",
    )
    return board


def main() -> None:
    for folder in (
        "materials",
        "masks/visible",
        "masks/hidden",
        "masks/complete",
        "qa",
        "samples",
        "audit",
    ):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)

    freeze_checks_before = {
        "upperArm": verify_freeze_manifest(UPPER_FREEZE),
        "forearm": verify_freeze_manifest(FOREARM_FREEZE),
    }
    source = Image.open(SOURCE).convert("RGBA")
    skeleton = json.loads(V31_SKELETON.read_text(encoding="utf-8"))
    visible, hidden, complete, root = build_hand_masks(source)
    bracelet = np.asarray(
        Image.open(FROZEN_BRACELET).convert("L"), dtype=np.uint8
    )
    forearm = np.asarray(
        Image.open(FROZEN_FOREARM).convert("L"), dtype=np.uint8
    )
    forearm_visible = np.asarray(
        Image.open(FROZEN_FOREARM_VISIBLE).convert("L"), dtype=np.uint8
    )
    forearm_hidden = np.asarray(
        Image.open(FROZEN_FOREARM_HIDDEN).convert("L"), dtype=np.uint8
    )
    forearm_skin = forearm.copy()
    forearm_skin[bracelet > 8] = 0
    forearm_visible_skin = forearm_visible.copy()
    forearm_visible_skin[bracelet > 8] = 0

    yy, xx = np.indices((H, W))
    u = (WR - E) / np.linalg.norm(WR - E)
    projection_from_wrist = (xx - WR[0]) * u[0] + (yy - WR[1]) * u[1]
    ucap = np.where(
        (forearm_hidden > 8)
        & (bracelet <= 8)
        & (projection_from_wrist >= -1.0),
        255,
        0,
    ).astype(np.uint8)

    save_mask(ROOT / "masks/visible/hand.png", visible)
    save_mask(ROOT / "masks/hidden/hand.png", hidden)
    save_mask(ROOT / "masks/complete/hand.png", complete)
    hand_layer = solid(complete, HAND_COLOR)
    hand_layer.save(ROOT / "materials/hand.png")

    skeleton_lock = {
        "schemaVersion": 1,
        "status": "referenced_frozen_skeleton_for_v32_hand_stage_a",
        "scope": "screen-left hand Stage A flat geometry only",
        "frozenSkeleton": {
            "path": (
                "../arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve/"
                "skeleton-lock.json"
            ),
            "sha256": sha256(V31_SKELETON),
        },
        "landmarksPx": {
            "shoulder": [170.0, 251.0],
            "elbow": [147.0, 405.0],
            "wrist": [115.0, 529.0],
        },
        "boneLengthsPx": {
            "L1ShoulderToElbow": 155.7080601638849,
            "L2ElbowToWrist": 128.06248474865697,
            "tolerancePx": 0.01,
        },
        "geometryMutation": "none",
        "parentChildRelations": [
            {"id": "forearm", "parent": "elbow_rotation"},
            {"id": "hand", "parent": "wrist_rotation"},
        ],
        "stageAQaMotion": {
            "sampleCount": 41,
            "path": "0_to_1_to_0",
            "wristStressDeg": [-12, -8, -4, 0, 4, 8, 12],
            "stressRangeApproval": "not_approved_motion_range",
        },
    }
    save_json(ROOT / "skeleton-lock.json", skeleton_lock)

    contract = {
        "schemaVersion": 1,
        "status": "stage_a_candidate_pending_user_visual_approval",
        "scope": "screen-left hand only",
        "directionConvention": "left means screen-left, consistent with V31",
        "authoritativeVisibleSource": {
            "path": "../../source/masters/front-color-source-exact-after-reset.png",
            "sha256": sha256(SOURCE),
        },
        "visiblePixelOwnership": [
            "wrist skin below the forearm-owned bracelet",
            "palm and hand back silhouette visible in Reset",
            "five-finger outer contour visible in Reset",
            "background-connected negative spaces between fingers visible in Reset",
        ],
        "hiddenRootResponsibility": (
            "one continuous skin material following both wrist boundaries from "
            "beneath the bracelet into the palm; no circle, rectangle, patch, "
            "flat average-color block, or detached insert"
        ),
        "forearmUCapCoverageResponsibility": {
            "frozenSource": (
                "../arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve/"
                "masks/complete/forearm.png"
            ),
            "rule": (
                "the complete hand covers the frozen distal U-shaped forearm "
                "cap at rest, in all 41 FK samples, and throughout the diagnostic "
                "-12 to +12 degree wrist-relative sweep"
            ),
            "minimumCompleteOverlapPx": 510,
        },
        "braceletExclusionResponsibility": {
            "owner": "forearm",
            "mask": (
                "../arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve/"
                "masks/visible/bracelet-owned-by-forearm.png"
            ),
            "handVisibleAndCompleteMustExclude": True,
        },
        "forbiddenIntrusionRegions": [
            "background outside the Reset hand contour and declared hidden wrist corridor",
            "shirt or sleeve",
            "skirt",
            "screen-right hand or any other body region",
        ],
        "drawOrderBackToFront": [
            {"id": "frozen_forearm_skin", "order": 20},
            {"id": "hand", "order": 30},
            {
                "id": "forearm_owned_bracelet",
                "order": 40,
                "note": "separate diagnostic draw item; ownership remains forearm",
            },
        ],
        "pivotAndHierarchy": {
            "pivot": "wrist",
            "wristPx": [115.0, 529.0],
            "parent": "forearm/elbow_rotation",
            "child": "hand/wrist_rotation",
            "motionRule": "wrist, palm, and all fingers move as one hand material",
            "scalingAllowedToHideSeams": False,
        },
        "geometryMutation": {
            "frozenSkeleton": "none",
            "frozenUpperArm": "none",
            "frozenForearm": "none",
            "frozenBracelet": "none",
            "frozenForearmUCap": "none",
        },
    }
    save_json(ROOT / "hand-layering-contract.json", contract)

    # Connectivity and overlap use the byte-frozen complete forearm, including
    # its forearm-owned bracelet pixels. The purple bracelet layer is drawn
    # last only to make that ownership visible in the diagnostic palette.
    forearm_layer = solid(forearm, FOREARM_COLOR)
    forearm_visible_layer = solid(forearm_visible, FOREARM_COLOR)
    bracelet_layer = solid(bracelet, BRACELET_COLOR)
    # Engineering coverage uses the exact frozen binary mask. Antialiasing is
    # presentation-only and must not expand the measured U-cap by a pixel.
    ucap_layer = solid_exact(ucap, (226, 68, 58, 255))

    default = compose_layers(
        [forearm_layer, hand_layer, bracelet_layer],
        background=checker((W, H)),
    )
    default.save(ROOT / "qa/default-solid-recomposition.png")

    overlay = source.copy()
    translucent_forearm = forearm_visible_layer.copy()
    translucent_forearm.putalpha(
        translucent_forearm.getchannel("A").point(lambda value: value * 0.42)
    )
    translucent_hand = solid(complete, (31, 166, 119, 112))
    translucent_bracelet = solid(bracelet, (148, 74, 184, 185))
    overlay.alpha_composite(translucent_forearm)
    overlay.alpha_composite(translucent_hand)
    overlay.alpha_composite(translucent_bracelet)
    overlay.save(ROOT / "qa/default-overlay-reset.png")

    displaced_hand = checker((W, H)).convert("RGBA")
    faded_default = compose_layers(
        [forearm_layer, hand_layer, bracelet_layer]
    )
    faded_default.putalpha(
        faded_default.getchannel("A").point(lambda value: value * 0.22)
    )
    displaced_hand.alpha_composite(faded_default)
    displaced_hand.alpha_composite(shifted(hand_layer, -145))
    displaced_hand.save(ROOT / "qa/hand-displaced-review.png")

    forearm_moved = checker((W, H)).convert("RGBA")
    forearm_moved.alpha_composite(hand_layer)
    forearm_moved.alpha_composite(shifted(forearm_layer, 145))
    forearm_moved.alpha_composite(shifted(bracelet_layer, 145))
    forearm_moved.save(ROOT / "qa/frozen-forearm-displaced-wrist-root.png")

    rejected = np.asarray(
        Image.open(FAILED_V31_HAND).convert("L"), dtype=np.uint8
    )
    contour_comparison = source.copy()
    contour_comparison.alpha_composite(
        outline(rejected, (226, 55, 55, 210), 2)
    )
    contour_comparison.alpha_composite(
        outline(visible, (20, 176, 112, 255), 2)
    )
    comparison_board = Image.new("RGB", (1600, 940), (241, 245, 250))
    fit(
        comparison_board,
        hand_crop(source, 6),
        (20, 20, 520, 900),
        "① Reset 手部轮廓",
    )
    fit(
        comparison_board,
        hand_crop(contour_comparison, 6),
        (540, 20, 1060, 900),
        "② 绿=V32 直接追踪 / 红=失败 V31",
    )
    isolated_visible = checker((W, H)).convert("RGBA")
    isolated_visible.alpha_composite(solid(visible, HAND_COLOR))
    fit(
        comparison_board,
        hand_crop(isolated_visible, 6),
        (1080, 20, 1580, 900),
        "③ V32 可见像素与开放指缝",
    )
    comparison_board.save(ROOT / "qa/reset-vs-candidate-hand-contour.png")

    zoom_board = Image.new("RGB", (2100, 900), (241, 245, 250))
    zoom_targets = [
        ((91, 518, 137, 566), "① 手腕：手链接口"),
        ((78, 545, 127, 595), "② 手掌：宽度与掌形"),
        ((60, 565, 104, 626), "③ 四指组：轮廓与指缝"),
        ((92, 565, 125, 612), "④ 拇指组：开放负空间"),
    ]
    for column, (box, label) in enumerate(zoom_targets):
        crop = source.crop(box).resize(
            ((box[2] - box[0]) * 9, (box[3] - box[1]) * 9),
            Image.Resampling.NEAREST,
        )
        crop_overlay = source.copy()
        crop_overlay.alpha_composite(outline(visible, (20, 176, 112, 255), 2))
        traced = crop_overlay.crop(box).resize(
            ((box[2] - box[0]) * 9, (box[3] - box[1]) * 9),
            Image.Resampling.NEAREST,
        )
        pair = Image.new(
            "RGB",
            (max(crop.width, traced.width), crop.height + traced.height + 10),
            "white",
        )
        pair.paste(crop.convert("RGB"), (0, 0))
        pair.paste(traced.convert("RGB"), (0, crop.height + 10))
        fit(
            zoom_board,
            pair,
            (column * 525 + 10, 20, column * 525 + 515, 870),
            label,
        )
    ImageDraw.Draw(zoom_board).text(
        (24, 868),
        "每格上半=Reset，下半=V32 绿色轮廓叠 Reset；重点看腕宽、掌宽、五指外轮廓和背景连通指缝。",
        fill=(58, 71, 91),
        font=font(19, True),
    )
    zoom_board.save(ROOT / "qa/hand-local-zooms.png")

    ownership = Image.new("RGB", (1750, 900), (241, 245, 250))
    ownership_reset = source.copy()
    ownership_reset.alpha_composite(
        solid(bracelet, (148, 74, 184, 170))
    )
    ownership_reset.alpha_composite(outline(visible, (20, 176, 112, 255), 2))
    ownership_masks = checker((W, H)).convert("RGBA")
    ownership_masks.alpha_composite(solid(visible, HAND_COLOR))
    ownership_masks.alpha_composite(bracelet_layer)
    collision = (complete > 8) & (bracelet > 8)
    collision_image = checker((W, H)).convert("RGBA")
    collision_image.alpha_composite(solid(complete, (31, 166, 119, 150)))
    collision_image.alpha_composite(bracelet_layer)
    if np.any(collision):
        collision_image.alpha_composite(
            solid(collision.astype(np.uint8) * 255, (255, 219, 45, 255))
        )
    for column, (image, label) in enumerate(
        [
            (ownership_reset, "① Reset：紫=冻结手链，绿线=手"),
            (ownership_masks, "② 可见归属：手链保持前景"),
            (
                collision_image,
                f"③ 完整掩码侵占手链 {np.count_nonzero(collision)}px",
            ),
        ]
    ):
        fit(
            ownership,
            hand_crop(image, 6),
            (column * 580 + 10, 20, column * 580 + 570, 870),
            label,
        )
    ownership.save(ROOT / "qa/bracelet-exclusion-ownership.png")

    ucap_review = Image.new("RGB", (1600, 920), (241, 245, 250))
    translucent_complete = solid(complete, (31, 166, 119, 105))
    ucap_diag = checker((W, H)).convert("RGBA")
    ucap_diag.alpha_composite(translucent_complete)
    ucap_diag.alpha_composite(ucap_layer)
    ucap_diag.alpha_composite(bracelet_layer)
    ucap_only = checker((W, H)).convert("RGBA")
    ucap_only.alpha_composite(ucap_layer)
    complete_only = checker((W, H)).convert("RGBA")
    complete_only.alpha_composite(hand_layer)
    for column, (image, label) in enumerate(
        [
            (ucap_only, "① 冻结前臂 U 形凸包"),
            (complete_only, "② 手部完整连续腕根"),
            (ucap_diag, "③ 半透明覆盖：橙不得外露"),
        ]
    ):
        fit(
            ucap_review,
            hand_crop(image, 6),
            (column * 530 + 10, 20, column * 530 + 520, 880),
            label,
        )
    ucap_review.save(ROOT / "qa/forearm-ucap-hand-coverage.png")

    samples, first_pose_hash, last_pose_hash = build_motion_evidence(
        skeleton,
        forearm_layer,
        bracelet_layer,
        hand_layer,
        ucap_layer,
    )
    stress_results = build_stress_evidence(hand_layer, ucap_layer)

    rgb = np.asarray(source.convert("RGB"), dtype=np.int16)
    chroma = np.max(rgb, axis=2) - np.min(rgb, axis=2)
    neutral_background = (np.mean(rgb, axis=2) >= 247) & (chroma <= 5)
    skirt = np.zeros((H, W), dtype=bool)
    skirt[555:640, 135:220] = True
    clothes = np.zeros((H, W), dtype=bool)
    clothes[200:555, 135:260] = True
    other_body = np.zeros((H, W), dtype=bool)
    other_body[:, 250:] = True
    forbidden_counts = {
        "background": int(
            np.count_nonzero((visible > 8) & neutral_background)
        ),
        "clothes": int(np.count_nonzero((complete > 8) & clothes)),
        "skirt": int(np.count_nonzero((complete > 8) & skirt)),
        "otherBodyOrOtherHand": int(
            np.count_nonzero((complete > 8) & other_body)
        ),
    }
    forbidden_total = sum(forbidden_counts.values())
    bracelet_visible_invasion = int(
        np.count_nonzero((visible > 8) & (bracelet > 8))
    )
    bracelet_complete_invasion = int(
        np.count_nonzero((complete > 8) & (bracelet > 8))
    )
    minimum_overlap = min(
        sample["forearmHandCompleteOverlapPx"] for sample in samples
    )
    disconnect_count = sum(sample["disconnected"] for sample in samples)
    max_fk_ucap_exposure = max(
        sample["forearmUCapExposedPx"] for sample in samples
    )
    max_stress_ucap_exposure = max(
        result["forearmUCapExposedPx"] for result in stress_results
    )
    max_l1_error = max(
        abs(
            sample["L1Px"]
            - skeleton["boneLengthsPx"]["L1ShoulderToElbow"]
        )
        for sample in samples
    )
    max_l2_error = max(
        abs(
            sample["L2Px"] - skeleton["boneLengthsPx"]["L2ElbowToWrist"]
        )
        for sample in samples
    )
    hand_components = components(complete)
    hand_holes = holes(complete)
    return_consistent = first_pose_hash == last_pose_hash

    freeze_checks_after = {
        "upperArm": verify_freeze_manifest(UPPER_FREEZE),
        "forearm": verify_freeze_manifest(FOREARM_FREEZE),
    }
    freeze_unchanged = all(
        before["manifestSha256"] == freeze_checks_after[name]["manifestSha256"]
        and all(item["match"] for item in freeze_checks_after[name]["checks"])
        for name, before in freeze_checks_before.items()
    )
    engineering_pass = (
        freeze_unchanged
        and max_l1_error <= 0.01
        and max_l2_error <= 0.01
        and minimum_overlap >= 510
        and disconnect_count == 0
        and return_consistent
        and hand_components == 1
        and hand_holes == 0
        and bracelet_visible_invasion == 0
        and bracelet_complete_invasion == 0
        and max_fk_ucap_exposure == 0
        and max_stress_ucap_exposure == 0
        and forbidden_total == 0
    )
    failed_checks = []
    check_map = {
        "frozen hashes unchanged": freeze_unchanged,
        "bone lengths": max_l1_error <= 0.01 and max_l2_error <= 0.01,
        "minimum forearm-hand overlap >= 510 px": minimum_overlap >= 510,
        "41-frame disconnect count = 0": disconnect_count == 0,
        "0-to-1-to-0 return consistency": return_consistent,
        "hand complete mask is one component": hand_components == 1,
        "hand complete mask has no closed holes": hand_holes == 0,
        "bracelet invasion = 0": (
            bracelet_visible_invasion == 0
            and bracelet_complete_invasion == 0
        ),
        "41-frame U-cap exposure = 0": max_fk_ucap_exposure == 0,
        "stress U-cap exposure = 0": max_stress_ucap_exposure == 0,
        "forbidden region intrusion = 0": forbidden_total == 0,
    }
    failed_checks.extend(name for name, passed in check_map.items() if not passed)
    earliest_failure = (
        failed_checks[0]
        if failed_checks
        else "none_in_machine_checks_pending_user_visual_review"
    )
    report = {
        "schemaVersion": 1,
        "status": (
            "engineering_pass_pending_user_visual_approval"
            if engineering_pass
            else "engineering_fail_stop_stage_a"
        ),
        "scope": "screen-left hand Stage A geometry only",
        "authoritativeInputs": {
            "resetColorMaster": {
                "path": "../../source/masters/front-color-source-exact-after-reset.png",
                "sha256": sha256(SOURCE),
            },
            "frozenSkeleton": {
                "path": (
                    "../arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve/"
                    "skeleton-lock.json"
                ),
                "sha256": sha256(V31_SKELETON),
            },
            "frozenUpperArmManifest": freeze_checks_before["upperArm"],
            "frozenForearmManifest": freeze_checks_before["forearm"],
            "rejectedV31HandUse": (
                "comparison only; never used to construct visible, hidden, or "
                "complete V32 hand geometry"
            ),
        },
        "frozenUpstreamHashCheck": {
            "before": freeze_checks_before,
            "after": freeze_checks_after,
            "unchanged": freeze_unchanged,
            "pass": freeze_unchanged,
        },
        "boneLengthError": {
            "maxL1ErrorPx": max_l1_error,
            "maxL2ErrorPx": max_l2_error,
            "tolerancePx": 0.01,
            "pass": max_l1_error <= 0.01 and max_l2_error <= 0.01,
        },
        "forearmHandMinimumCompleteOverlap": {
            "minimumAcross41SamplesPx": minimum_overlap,
            "frozenBaselinePx": 510,
            "pass": minimum_overlap >= 510,
        },
        "disconnectsAcross41Frames": {
            "count": disconnect_count,
            "pass": disconnect_count == 0,
        },
        "returnConsistency": {
            "firstPoseSha256": first_pose_hash,
            "lastPoseSha256": last_pose_hash,
            "pass": return_consistent,
        },
        "handCompleteGeometry": {
            "components": hand_components,
            "closedTransparentHoles": hand_holes,
            "visiblePixels": int(np.count_nonzero(visible > 8)),
            "hiddenPixels": int(np.count_nonzero(hidden > 8)),
            "completePixels": int(np.count_nonzero(complete > 8)),
            "pass": hand_components == 1 and hand_holes == 0,
        },
        "braceletIntrusion": {
            "visibleHandPixels": bracelet_visible_invasion,
            "completeHandPixels": bracelet_complete_invasion,
            "pass": (
                bracelet_visible_invasion == 0
                and bracelet_complete_invasion == 0
            ),
        },
        "forearmUCapExposureAcross41Frames": {
            "maximumPx": max_fk_ucap_exposure,
            "samples": [
                {
                    "index": sample["index"],
                    "exposedPx": sample["forearmUCapExposedPx"],
                }
                for sample in samples
            ],
            "pass": max_fk_ucap_exposure == 0,
        },
        "forearmUCapExposureWristStress": {
            "results": stress_results,
            "maximumPx": max_stress_ucap_exposure,
            "stressRangeIsApprovedMotionRange": False,
            "pass": max_stress_ucap_exposure == 0,
        },
        "forbiddenRegionIntrusion": {
            "pixels": forbidden_counts,
            "totalPixels": forbidden_total,
            "method": (
                "Reset-neutral background test plus explicit screen-left garment/"
                "skirt and opposite-body exclusion regions; hidden root is limited "
                "to the declared continuous wrist corridor"
            ),
            "pass": forbidden_total == 0,
        },
        "machineChecks": check_map,
        "earliestFailurePoint": earliest_failure,
        "visualGate": {
            "status": "pending_user_visual_approval",
            "review": "qa/V32-阶段A-screen-left手部-中文视觉审查板.png",
            "handFrozen": False,
        },
        "stop": (
            "Remain at Stage A. Do not freeze the hand or proceed to texture, "
            "PSD, Cubism, Physics, Runtime, the other arm, or the full body "
            "before explicit user approval of the Chinese visual review board."
        ),
    }
    save_json(ROOT / "audit/machine-report.json", report)

    review = Image.new("RGB", (3400, 5900), (238, 243, 249))
    draw = ImageDraw.Draw(review)
    draw.text(
        (70, 35),
        "小星 V32｜screen-left 手部阶段 A 中文视觉审查板",
        fill=(18, 28, 43),
        font=font(48, True),
    )
    draw.text(
        (70, 100),
        "只审手部：绿色=V32 手，橙色/红色=冻结前臂及 U 形凸包，紫色=仍归前臂的手链。手部尚未冻结。",
        fill=(58, 71, 91),
        font=font(27),
    )
    review_items = [
        (hand_crop(source, 7), "1. Reset 原图手部｜看原始腕宽、掌形和五指"),
        (
            hand_crop(
                compose_layers([hand_layer], background=checker((W, H))),
                7,
            ),
            "2. 手部纯色完整材料｜看连续腕根、单一主体和开放指缝",
        ),
        (hand_crop(default, 7), "3. 默认回组｜看是否像 Reset、手链是否可见"),
        (
            hand_crop(overlay, 7),
            "4. 回组叠 Reset｜看轮廓偏移、绿色上窜和腕宽",
        ),
        (
            hand_crop(forearm_moved, 7),
            "5. 前臂移开｜看手部隐藏腕根是否连续、是否像补丁",
        ),
        (
            ucap_review,
            "6. 前臂凸包半透明叠手｜橙色必须完全被绿覆盖",
        ),
        (
            ownership,
            "7. 手链像素排除｜紫色保持可见，侵占必须为 0px",
        ),
        (
            zoom_board,
            "8. 手指轮廓与指缝｜看五指、长度、粗细、粘连和手套感",
        ),
        (
            Image.open(ROOT / "qa/fk-key-samples.png").convert("RGB"),
            "9. 41 帧关键样本｜看橙漏、绿窜、透明缝和整体随动",
        ),
        (
            Image.open(ROOT / "qa/wrist-relative-stress-review.png").convert(
                "RGB"
            ),
            "10. ±12°穿模压力｜仅查 U 形凸包外露，不代表动作批准",
        ),
    ]
    for index, (image, label) in enumerate(review_items):
        row = index // 2
        column = index % 2
        fit(
            review,
            image,
            (
                50 + column * 1690,
                155 + row * 1040,
                1660 + column * 1690,
                1165 + row * 1040,
            ),
            label,
        )
    draw.rounded_rectangle(
        (70, 5410, 3330, 5840),
        radius=22,
        fill=(255, 255, 255),
        outline=(170, 183, 200),
        width=3,
    )
    questions = [
        "1 默认回组是否像原图？  2 手腕宽度是否自然？  3 手部上缘是否正确接住手链下方？",
        "4 冻结前臂凸包是否完整覆盖？  5 手链是否可见且无绿色侵占？  6 手掌和手指是否符合原图？",
        "7 指缝是否保留？  8 手指是否过粗、过短、粘连或像手套？",
        "9 运动中是否出现橙色漏出、绿色上窜或透明缝？  10 哪一处是最早失败点？",
    ]
    draw.text(
        (105, 5442),
        "请逐项审查：",
        fill=(132, 55, 28),
        font=font(28, True),
    )
    for row, question in enumerate(questions):
        draw.text(
            (105, 5495 + row * 74),
            question,
            fill=(35, 48, 64),
            font=font(24, row == 3),
        )
    draw.text(
        (105, 5790),
        (
            f"机器门禁：{'通过' if engineering_pass else '未通过'}｜"
            f"41 帧最小重叠 {minimum_overlap}px｜"
            f"41 帧/压力凸包最大外露 {max_fk_ucap_exposure}/"
            f"{max_stress_ucap_exposure}px｜手部尚未冻结"
        ),
        fill=(20, 102, 77) if engineering_pass else (178, 50, 43),
        font=font(24, True),
    )
    review.save(ROOT / "qa/V32-阶段A-screen-left手部-中文视觉审查板.png")

    artifact_paths = [
        "skeleton-lock.json",
        "hand-layering-contract.json",
        "masks/visible/hand.png",
        "masks/hidden/hand.png",
        "masks/complete/hand.png",
        "materials/hand.png",
        "qa/default-solid-recomposition.png",
        "qa/default-overlay-reset.png",
        "qa/hand-displaced-review.png",
        "qa/frozen-forearm-displaced-wrist-root.png",
        "qa/reset-vs-candidate-hand-contour.png",
        "qa/hand-local-zooms.png",
        "qa/bracelet-exclusion-ownership.png",
        "qa/forearm-ucap-hand-coverage.png",
        "qa/fk-41-slow-preview.gif",
        "qa/fk-key-samples.png",
        "qa/wrist-relative-stress-review.png",
        "qa/V32-阶段A-screen-left手部-中文视觉审查板.png",
        "samples/fk-41-samples.json",
        "audit/machine-report.json",
        "tools/build_v32_hand_stage_a.py",
    ]
    artifact_paths.extend(f"samples/fk-{index:03d}.png" for index in range(41))
    save_json(
        ROOT / "audit/artifact-manifest.json",
        {
            "schemaVersion": 1,
            "status": "stage_a_candidate_not_frozen",
            "artifacts": [
                {"path": path, "sha256": sha256(ROOT / path)}
                for path in artifact_paths
            ],
            "handFrozen": False,
            "visualApproval": "pending",
        },
    )

    # Remove files created only for the initial segmentation exploration.
    for relative in (
        "qa/hand-trace-exploration.png",
        "qa/hand-coordinate-grid.png",
        "audit/exploration.json",
    ):
        path = ROOT / relative
        if path.exists():
            path.unlink()


if __name__ == "__main__":
    main()
