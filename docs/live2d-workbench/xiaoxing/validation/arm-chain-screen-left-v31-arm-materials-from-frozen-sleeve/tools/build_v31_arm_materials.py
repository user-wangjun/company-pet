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
V30 = (
    XIAOXING
    / "validation/arm-chain-screen-left-v30-right-structure-convergence"
)
V30_FREEZE = V30 / "audit/v30-sleeve-geometry-freeze-manifest-2026-07-28.json"
V30_SLEEVE_COMPLETE = V30 / "masks/sleeve-complete-fresh.png"
V30_SLEEVE_VISIBLE = V30 / "masks/sleeve-visible-owned.png"
V30_SLEEVE_MATERIAL = V30 / "materials/sleeve.png"
V30_SKELETON = V30 / "skeleton-lock.json"
RIGHT_V6 = (
    XIAOXING
    / "validation/arm-chain-screen-right-v6-complete-upper-arm-geometry"
)
RIGHT_V6_FREEZE = (
    RIGHT_V6
    / "audit/v6-complete-upper-arm-geometry-freeze-manifest-2026-07-25.json"
)
RIGHT_V6_CONTRACT = (
    RIGHT_V6 / "design/complete-upper-arm-geometry-contract.json"
)
RIGHT_V6_UPPER_MASK = RIGHT_V6 / "masks/upper-arm-complete-geometry.png"
UPPER_FREEZE = (
    ROOT / "audit/v31-upper-arm-geometry-freeze-manifest-2026-07-28.json"
)
FOREARM_FREEZE = (
    ROOT / "audit/v31-forearm-geometry-freeze-manifest-2026-07-29.json"
)
FOREARM_BEFORE = (
    ROOT / "masks/reference/forearm-before-proximal-fill.png"
)
FOREARM_FLAT_ROOT_BEFORE = (
    ROOT / "masks/reference/forearm-before-curved-hidden-root.png"
)
FOREARM_BEFORE_SMOOTH_CAPS = (
    ROOT / "masks/reference/forearm-before-smooth-endcaps.png"
)
FOREARM_BEFORE_REDLINE_CAPS = (
    ROOT / "masks/reference/forearm-before-user-redline-caps.png"
)
FOREARM_BEFORE_CONVEX_CAPS = (
    ROOT / "masks/reference/forearm-before-user-convex-caps.png"
)

W, H = 512, 1086
MOTION_W = 768
MOTION_OFFSET = np.array((160.0, 0.0))
S = np.array((170.0, 251.0))
E = np.array((147.0, 405.0))
WR = np.array((115.0, 529.0))
ORDER = ["upper_arm", "forearm", "hand", "sleeve"]
COLORS = {
    "upper_arm": (231, 82, 72, 255),
    "forearm": (242, 155, 43, 255),
    "hand": (31, 166, 119, 255),
    "sleeve": (40, 112, 194, 255),
}


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


def external_fill(seed: np.ndarray) -> tuple[np.ndarray, int]:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    closed = cv2.morphologyEx(seed, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours, _ = cv2.findContours(
        closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
    )
    retained = [c for c in contours if cv2.contourArea(c) >= 2.0]
    output = np.zeros_like(seed)
    cv2.drawContours(output, retained, -1, 255, cv2.FILLED)
    output = cv2.dilate(output, kernel, iterations=1)
    return output, sum(len(c) for c in retained)


def largest_component(mask: np.ndarray) -> np.ndarray:
    binary = (mask > 8).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )
    if count <= 2:
        return np.where(binary > 0, 255, 0).astype(np.uint8)
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return np.where(labels == largest, 255, 0).astype(np.uint8)


def source_skin_visible(source: Image.Image):
    rgb = np.asarray(source.convert("RGB"), dtype=np.int16)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    envelope = np.zeros((H, W), dtype=np.uint8)
    cv2.fillPoly(
        envelope,
        [
            np.array(
                [
                    (125, 378),
                    (189, 398),
                    (180, 454),
                    (160, 510),
                    (138, 554),
                    (136, 592),
                    (123, 630),
                    (91, 642),
                    (53, 638),
                    (52, 597),
                    (68, 566),
                    (90, 532),
                    (98, 490),
                    (107, 440),
                ],
                dtype=np.int32,
            )
        ],
        255,
    )
    seed = (
        (r - b > 12)
        & (r - g > 6)
        & (r > 165)
        & (g > 135)
        & (envelope > 0)
    )
    skin, contour_points = external_fill(seed.astype(np.uint8) * 255)
    skin = cv2.bitwise_and(skin, envelope)

    yy, xx = np.indices((H, W))
    u = (WR - E) / np.linalg.norm(WR - E)
    projection = (xx - E[0]) * u[0] + (yy - E[1]) * u[1]
    upper = np.where((skin > 0) & (projection <= -2.0), 255, 0).astype(
        np.uint8
    )
    forearm = np.where(
        (skin > 0) & (projection > -2.0) & (projection < 126.0),
        255,
        0,
    ).astype(np.uint8)
    hand = np.where((skin > 0) & (projection >= 126.0), 255, 0).astype(
        np.uint8
    )
    return {"upper_arm": upper, "forearm": forearm, "hand": hand}, {
        "skinContourPointCount": contour_points,
        "visibleUnionPixels": int(np.count_nonzero(skin)),
    }


def source_sleeve_visible(source: Image.Image):
    # Closed semantic outline traced from the Reset garment boundary. Color
    # thresholding is not used here because pale highlights and the adjacent
    # torso are too similar and would cut a false notch into the cuff.
    sleeve = np.zeros((H, W), dtype=np.uint8)
    boundary = np.array(
        [
            (168, 220),
            (155, 228),
            (143, 245),
            (130, 278),
            (115, 320),
            (100, 360),
            (96, 372),
            (103, 378),
            (122, 389),
            (146, 400),
            (184, 416),
            (184, 390),
            (183, 360),
            (180, 335),
            (176, 315),
            (171, 295),
            (167, 275),
            (164, 255),
            (165, 240),
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(sleeve, [boundary], 255, lineType=cv2.LINE_AA)
    return sleeve, len(boundary)


def source_bracelet_visible(source: Image.Image):
    # The bracelet is a forearm-owned accessory, but its mask must follow the
    # actual gray chain, knot, and dangling pixels. Filling its outer hull would
    # incorrectly claim the skin inside the loop.
    scale = 8
    canvas = np.zeros((H * scale, W * scale), dtype=np.uint8)
    paths = (
        ([(101, 513), (108, 515), (116, 518), (124, 521), (132, 523)], 1.7),
        ([(100, 517), (107, 519), (115, 522), (123, 525), (130, 527)], 1.6),
        ([(102, 513), (98, 512), (95, 516), (94, 521), (97, 526), (101, 526)], 1.8),
        ([(101, 525), (99, 531), (98, 538)], 1.35),
        ([(99, 526), (94, 531), (92, 534)], 1.25),
        ([(131, 522), (135, 523), (136, 527), (133, 531), (130, 531)], 1.75),
        ([(130, 529), (129, 535), (128, 538)], 1.3),
    )
    for points, width in paths:
        cv2.polylines(
            canvas,
            [np.asarray(points, dtype=np.int32) * scale],
            False,
            255,
            thickness=max(1, round(width * scale)),
            lineType=cv2.LINE_AA,
        )
    for x, y, radius in (
        (103, 514, 1.35),
        (108, 516, 1.25),
        (114, 518, 1.25),
        (120, 521, 1.25),
        (126, 523, 1.3),
        (131, 525, 1.35),
        (98, 523, 1.25),
        (98, 533, 1.1),
        (131, 530, 1.2),
    ):
        cv2.circle(
            canvas,
            (x * scale, y * scale),
            round(radius * scale),
            255,
            thickness=-1,
            lineType=cv2.LINE_AA,
        )
    bracelet = np.asarray(
        Image.fromarray(canvas).resize((W, H), Image.Resampling.LANCZOS)
    )
    return bracelet, sum(len(points) for points, _ in paths)


def correct_frozen_sleeve_cuff(
    source_sleeve: np.ndarray,
    frozen_visible: np.ndarray,
    frozen_complete: np.ndarray,
):
    # The V30 shoulder/body-side structure stays intact. At the cuff, Reset is
    # authoritative: no sleeve pixels may continue below its diagonal hem.
    corrected_visible = frozen_visible.copy()
    corrected_complete = frozen_complete.copy()
    corrected_complete[350:] = source_sleeve[350:]
    corrected_visible[350:] = source_sleeve[350:]
    cuff_rows = np.where(np.any(source_sleeve[350:] > 8, axis=1))[0] + 350
    first_row = int(cuff_rows.min())
    last_row = int(cuff_rows.max())
    for y in cuff_rows:
        xs = np.where(source_sleeve[y] > 8)[0]
        base_hidden_width = 18
        terminal_progress = max(
            0.0, (y - 388.0) / max(1.0, last_row - 388.0)
        )
        hidden_width = base_hidden_width + int(
            round(
                max(0, len(xs) - base_hidden_width)
                * terminal_progress**2
            )
        )
        corrected_visible[y, xs[-hidden_width:]] = 0
        remaining = np.where(corrected_visible[y] > 8)[0]
        if len(remaining) <= 4:
            corrected_visible[y] = 0
    corrected_hidden = cv2.subtract(corrected_complete, corrected_visible)
    removed_visible = (frozen_visible > 8) & (corrected_visible <= 8)
    removed_complete = (frozen_complete > 8) & (corrected_complete <= 8)
    return corrected_visible, corrected_complete, corrected_hidden, {
        "correctionStartRow": 350,
        "removedVisiblePixels": int(np.count_nonzero(removed_visible)),
        "removedCompletePixels": int(np.count_nonzero(removed_complete)),
        "correctedVisibleBeyondSourceCuffPixels": int(
            np.count_nonzero(
                (corrected_visible[350:] > 8)
                & (source_sleeve[350:] <= 8)
            )
        ),
        "correctedCompleteBeyondSourceCuffPixels": int(
            np.count_nonzero(
                (corrected_complete[350:] > 8)
                & (source_sleeve[350:] <= 8)
            )
        ),
        "terminalVisiblePixelsRows410Plus": int(
            np.count_nonzero(corrected_visible[410:] > 8)
        ),
    }


def ribbon(points, widths, samples=180):
    points = np.asarray(points, dtype=np.float64)
    widths = np.asarray(widths, dtype=np.float64)
    ts = np.linspace(0.0, 1.0, samples)
    curve = (
        ((1 - ts) ** 2)[:, None] * points[0]
        + (2 * (1 - ts) * ts)[:, None] * points[1]
        + (ts**2)[:, None] * points[2]
    )
    derivative = (
        (2 * (1 - ts))[:, None] * (points[1] - points[0])
        + (2 * ts)[:, None] * (points[2] - points[1])
    )
    tangent = derivative / np.linalg.norm(derivative, axis=1)[:, None]
    normal = np.column_stack((-tangent[:, 1], tangent[:, 0]))
    width = (
        ((1 - ts) ** 2) * widths[0]
        + 2 * (1 - ts) * ts * widths[1]
        + (ts**2) * widths[2]
    )
    polygon = np.vstack(
        (curve + normal * width[:, None], (curve - normal * width[:, None])[::-1])
    )
    canvas = np.zeros((H * 4, W * 4), dtype=np.uint8)
    cv2.fillPoly(
        canvas,
        [np.round(polygon * 4).astype(np.int32)],
        255,
        lineType=cv2.LINE_AA,
    )
    return np.asarray(
        Image.fromarray(canvas).resize((W, H), Image.Resampling.LANCZOS)
    )


def anatomical_upper_arm():
    # Register the exact user-approved screen-right V6 flat geometry into the
    # unchanged screen-left shoulder/elbow frame. The normal coordinate is
    # mirrored because these are opposite character arms. This keeps the
    # character-specific taper and asymmetric elbow end instead of inventing a
    # generic capsule from anatomy averages.
    right_s = np.array((332.0, 261.0))
    right_e = np.array((355.0, 415.0))
    right_u = (right_e - right_s) / np.linalg.norm(right_e - right_s)
    right_n = np.array((-right_u[1], right_u[0]))
    left_u = (E - S) / np.linalg.norm(E - S)
    left_n = np.array((-left_u[1], left_u[0]))
    source_basis = np.column_stack((right_u, right_n))
    target_basis = np.column_stack((left_u, -left_n))
    linear = target_basis @ source_basis.T
    translation = S - linear @ right_s
    matrix = np.column_stack((linear, translation)).astype(np.float64)
    source_mask = np.asarray(
        Image.open(RIGHT_V6_UPPER_MASK).convert("L"), dtype=np.uint8
    )
    registered = cv2.warpAffine(
        source_mask,
        matrix,
        (W, H),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return np.where(registered > 8, 255, 0).astype(np.uint8)


def anatomical_wrist_tongue():
    u2 = (WR - E) / np.linalg.norm(WR - E)
    n2 = np.array((-u2[1], u2[0]))
    # Match the actual hand-root skin corridor with a small safety inset. The
    # insert stays broad through the wrist instead of shrinking immediately
    # into a centered teardrop.
    outer = WR - u2 * 5.0 + n2 * 10.0
    inner = WR - u2 * 5.0 - n2 * 7.0
    outer_end = WR + u2 * 12.0 + n2 * 10.0
    inner_end = WR + u2 * 12.0 - n2 * 8.0
    ts = np.linspace(0.0, 1.0, 64)

    outer_curve = (
        ((1 - ts) ** 3)[:, None] * outer
        + (3 * (1 - ts) ** 2 * ts)[:, None]
        * (WR + n2 * 10.0)
        + (3 * (1 - ts) * ts**2)[:, None]
        * (WR + u2 * 7.0 + n2 * 10.0)
        + (ts**3)[:, None] * outer_end
    )
    rounded_cap = (
        ((1 - ts) ** 3)[:, None] * outer_end
        + (3 * (1 - ts) ** 2 * ts)[:, None]
        * (outer_end + u2 * 9.333)
        + (3 * (1 - ts) * ts**2)[:, None]
        * (inner_end + u2 * 9.333)
        + (ts**3)[:, None] * inner_end
    )
    inner_curve = (
        ((1 - ts) ** 3)[:, None] * inner_end
        + (3 * (1 - ts) ** 2 * ts)[:, None]
        * (WR + u2 * 7.0 - n2 * 8.0)
        + (3 * (1 - ts) * ts**2)[:, None]
        * (WR - n2 * 7.5)
        + (ts**3)[:, None] * inner
    )
    # This internal closure is only the semantic boundary of the wrist insert
    # used in the diagnostic. It sits inside the continuous forearm material.
    # A shallow cubic arc avoids introducing a false jagged/straight wrist edge
    # in the enlarged review.
    top_curve = (
        ((1 - ts) ** 3)[:, None] * inner
        + (3 * (1 - ts) ** 2 * ts)[:, None] * (inner - u2 * 1.0)
        + (3 * (1 - ts) * ts**2)[:, None] * (outer - u2 * 1.0)
        + (ts**3)[:, None] * outer
    )
    polygon = np.vstack((outer_curve, rounded_cap, inner_curve, top_curve))
    scale = 8
    canvas = np.zeros((H * scale, W * scale), dtype=np.uint8)
    cv2.fillPoly(
        canvas,
        [np.round(polygon * scale).astype(np.int32)],
        255,
        lineType=cv2.LINE_AA,
    )
    return np.asarray(
        Image.fromarray(canvas).resize((W, H), Image.Resampling.LANCZOS)
    )


def anatomical_forearm():
    # Preserve the approved forearm shaft and distal taper. Only the proximal
    # root is extended slightly toward the shirt side (negative normal) and
    # two pixels farther beneath the sleeve, then smoothly converges by the
    # early shaft. This is an asymmetric anatomical continuation, not a seam
    # patch.
    u2 = (WR - E) / np.linalg.norm(WR - E)
    p0 = E - u2 * 17.0
    p1 = np.array((135.0, 467.0))
    # At the wrist, stop the shaft almost on the locked wrist plane and let
    # the cap itself form the hidden rounded tongue inside the hand. Keeping a
    # long parallel-sided shaft beyond the wrist makes the overlap read like a
    # second forearm segment instead of the user's redlined convex insert.
    p2 = WR.copy()
    ts = np.linspace(0.0, 1.0, 220)
    curve = (
        ((1 - ts) ** 2)[:, None] * p0
        + (2 * (1 - ts) * ts)[:, None] * p1
        + (ts**2)[:, None] * p2
    )
    derivative = (
        (2 * (1 - ts))[:, None] * (p1 - p0)
        + (2 * ts)[:, None] * (p2 - p1)
    )
    tangent = derivative / np.linalg.norm(derivative, axis=1)[:, None]
    normal = np.column_stack((-tangent[:, 1], tangent[:, 0]))
    stations = np.array((0.0, 0.12, 0.45, 1.0))
    outer_width = np.interp(ts, stations, (18.0, 17.0, 14.0, 10.8))
    shirt_side_width = np.interp(
        ts, stations, (22.0, 18.0, 14.5, 10.8)
    )
    outer_side = curve + normal * outer_width[:, None]
    inner_side = (curve - normal * shirt_side_width[:, None])[::-1]
    inner_root = inner_side[-1]
    outer_root = outer_side[0]
    cap_c1 = inner_root - u2 * 24.0
    cap_c2 = outer_root - u2 * 24.0
    cap_ts = np.linspace(0.0, 1.0, 48)
    proximal_cap = (
        ((1 - cap_ts) ** 3)[:, None] * inner_root
        + (3 * (1 - cap_ts) ** 2 * cap_ts)[:, None] * cap_c1
        + (3 * (1 - cap_ts) * cap_ts**2)[:, None] * cap_c2
        + (cap_ts**3)[:, None] * outer_root
    )
    outer_distal = outer_side[-1]
    inner_distal = inner_side[0]
    wrist_bridge = (
        ((1 - cap_ts) ** 3)[:, None] * outer_distal
        + (3 * (1 - cap_ts) ** 2 * cap_ts)[:, None]
        * (outer_distal + u2 * 1.0)
        + (3 * (1 - cap_ts) * cap_ts**2)[:, None]
        * (inner_distal + u2 * 1.0)
        + (cap_ts**3)[:, None] * inner_distal
    )
    polygon = np.vstack(
        (outer_side, wrist_bridge, inner_side, proximal_cap)
    )
    scale = 8
    canvas = np.zeros((H * scale, W * scale), dtype=np.uint8)
    cv2.fillPoly(
        canvas,
        [np.round(polygon * scale).astype(np.int32)],
        255,
        lineType=cv2.LINE_AA,
    )
    forearm = np.asarray(
        Image.fromarray(canvas).resize((W, H), Image.Resampling.LANCZOS)
    )
    return np.maximum(forearm, anatomical_wrist_tongue())


def build_complete(visible, bracelet):
    u2 = (WR - E) / np.linalg.norm(WR - E)
    upper_body = anatomical_upper_arm()
    forearm_body = anatomical_forearm()
    hand_root = ribbon(
        [WR - u2 * 20, WR - u2 * 3, WR + u2 * 13],
        [9.8, 10.2, 9.0],
        90,
    )
    complete = {
        "upper_arm": np.maximum(visible["upper_arm"], upper_body),
        "forearm": np.maximum(visible["forearm"], forearm_body),
        "hand": np.maximum(visible["hand"], hand_root),
    }
    complete["hand"][bracelet > 8] = 0
    complete["hand"] = np.maximum(
        largest_component(complete["hand"]), visible["hand"]
    )
    hidden = {
        name: cv2.subtract(complete[name], visible[name])
        for name in ("upper_arm", "forearm", "hand")
    }
    return complete, hidden


def antialias(mask):
    return Image.fromarray(mask).filter(ImageFilter.GaussianBlur(0.42))


def solid(mask, color):
    image = Image.new("RGBA", (W, H), color)
    image.putalpha(antialias(mask))
    return image


def composite(layers, background=None):
    canvas = (
        background.convert("RGBA").copy()
        if background is not None
        else Image.new("RGBA", (W, H), (0, 0, 0, 0))
    )
    for name in ORDER:
        canvas.alpha_composite(layers[name])
    return canvas


def composite_motion(layers):
    canvas = Image.new("RGBA", (MOTION_W, H), (0, 0, 0, 0))
    for name in ORDER:
        canvas.alpha_composite(layers[name])
    return canvas


def rotate_translate(image, old_pivot, new_pivot, angle_deg):
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    ox, oy = old_pivot
    nx, ny = new_pivot
    return image.transform(
        (W, H),
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


def rotate_translate_padded(image, old_pivot, new_pivot, angle_deg):
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    ox, oy = old_pivot
    nx, ny = np.asarray(new_pivot) + MOTION_OFFSET
    return image.transform(
        (MOTION_W, H),
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


def point_at(origin, length, angle_deg):
    angle = math.radians(angle_deg)
    return np.array(
        (
            origin[0] + length * math.cos(angle),
            origin[1] + length * math.sin(angle),
        )
    )


def overlap(a, b):
    aa = np.asarray(a.getchannel("A")) > 8
    bb = np.asarray(b.getchannel("A")) > 8
    return int(np.count_nonzero(aa & bb))


def components(mask):
    return cv2.connectedComponents((mask > 8).astype(np.uint8))[0] - 1


def holes(mask):
    contours, hierarchy = cv2.findContours(
        (mask > 8).astype(np.uint8) * 255,
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if hierarchy is None:
        return 0
    return sum(1 for item in hierarchy[0] if item[3] >= 0)


def holes_with_min_area(mask, minimum_area):
    contours, hierarchy = cv2.findContours(
        (mask > 8).astype(np.uint8) * 255,
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if hierarchy is None:
        return 0
    return sum(
        1
        for contour, item in zip(contours, hierarchy[0])
        if item[3] >= 0 and cv2.contourArea(contour) >= minimum_area
    )


def checker(size, cell=16):
    image = Image.new("RGB", size, (239, 239, 239))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle(
                    (x, y, x + cell - 1, y + cell - 1),
                    fill=(207, 207, 207),
                )
    return image


def crop4(image, box):
    crop = image.crop(box)
    return crop.resize(
        (crop.width * 4, crop.height * 4), Image.Resampling.NEAREST
    )


def crop_smooth(image, box, scale=5):
    crop = image.crop(box)
    return crop.resize(
        (crop.width * scale, crop.height * scale),
        Image.Resampling.LANCZOS,
    )


def fit(board, image, box, label):
    x0, y0, x1, y1 = box
    area = Image.new("RGB", (x1 - x0, y1 - y0), "white")
    item = image.convert("RGBA")
    item.thumbnail((area.width, area.height - 48), Image.Resampling.LANCZOS)
    px = (area.width - item.width) // 2
    area.paste(item.convert("RGB"), (px, 0), item.getchannel("A"))
    ImageDraw.Draw(area).text(
        (8, area.height - 40),
        label,
        fill=(18, 28, 43),
        font=font(21, True),
    )
    board.paste(area, (x0, y0))


def moved_check(name, complete_layers, visible_layers):
    base = composite(visible_layers)
    base.putalpha(base.getchannel("A").point(lambda p: round(p * 0.22)))
    moved = complete_layers[name].transform(
        (W, H),
        Image.Transform.AFFINE,
        (1, 0, -150, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )
    canvas = checker((W, H)).convert("RGBA")
    canvas.alpha_composite(base)
    canvas.alpha_composite(moved)
    return canvas


def main():
    for folder in (
        "materials",
        "masks/visible",
        "masks/hidden",
        "masks/complete",
        "masks/reference",
        "qa",
        "samples",
        "audit",
    ):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)

    upper_freeze = json.loads(UPPER_FREEZE.read_text(encoding="utf-8"))
    assert upper_freeze["status"] == "frozen_engineering_and_user_visual_pass"
    assert sha256(ROOT / upper_freeze["userApproval"]["path"]) == (
        upper_freeze["userApproval"]["sha256"]
    )
    for item in upper_freeze["lockedGeometry"]:
        assert sha256(ROOT / item["path"]) == item["sha256"]

    forearm_freeze = None
    if FOREARM_FREEZE.exists():
        forearm_freeze = json.loads(
            FOREARM_FREEZE.read_text(encoding="utf-8")
        )
        assert (
            forearm_freeze["status"]
            == "frozen_engineering_and_user_visual_pass"
        )
        assert sha256(
            ROOT / forearm_freeze["userApproval"]["path"]
        ) == forearm_freeze["userApproval"]["sha256"]
        for item in forearm_freeze["lockedGeometry"]:
            assert sha256(ROOT / item["path"]) == item["sha256"]

    if not FOREARM_BEFORE.exists():
        Image.open(ROOT / "masks/complete/forearm.png").convert("L").save(
            FOREARM_BEFORE
        )
    if not FOREARM_FLAT_ROOT_BEFORE.exists():
        Image.open(ROOT / "masks/complete/forearm.png").convert("L").save(
            FOREARM_FLAT_ROOT_BEFORE
        )
    if not FOREARM_BEFORE_SMOOTH_CAPS.exists():
        Image.open(ROOT / "masks/complete/forearm.png").convert("L").save(
            FOREARM_BEFORE_SMOOTH_CAPS
        )
    if not FOREARM_BEFORE_REDLINE_CAPS.exists():
        Image.open(ROOT / "masks/complete/forearm.png").convert("L").save(
            FOREARM_BEFORE_REDLINE_CAPS
        )
    if not FOREARM_BEFORE_CONVEX_CAPS.exists():
        Image.open(ROOT / "masks/complete/forearm.png").convert("L").save(
            FOREARM_BEFORE_CONVEX_CAPS
        )

    freeze = json.loads(V30_FREEZE.read_text(encoding="utf-8"))
    assert freeze["status"] == "frozen_engineering_and_user_visual_pass"
    frozen_hashes = {x["path"]: x["sha256"] for x in freeze["artifacts"]}
    for relative, path in (
        ("masks/sleeve-complete-fresh.png", V30_SLEEVE_COMPLETE),
        ("masks/sleeve-visible-owned.png", V30_SLEEVE_VISIBLE),
        ("materials/sleeve.png", V30_SLEEVE_MATERIAL),
        ("skeleton-lock.json", V30_SKELETON),
    ):
        assert sha256(path) == frozen_hashes[relative]

    right_freeze = json.loads(RIGHT_V6_FREEZE.read_text(encoding="utf-8"))
    assert right_freeze["status"] == "frozen_engineering_and_user_visual_pass"
    right_mask_lock = next(
        item
        for item in right_freeze["lockedGeometry"]
        if item["path"] == "masks/upper-arm-complete-geometry.png"
    )
    assert sha256(RIGHT_V6_UPPER_MASK) == right_mask_lock["sha256"]
    right_contract = json.loads(RIGHT_V6_CONTRACT.read_text(encoding="utf-8"))
    assert right_contract["frozenSkeleton"]["L1"] == round(
        float(np.linalg.norm(E - S)), 6
    )

    source = Image.open(SOURCE).convert("RGBA")
    assert source.size == (W, H)
    skeleton = json.loads(V30_SKELETON.read_text(encoding="utf-8"))
    assert skeleton["landmarksPx"] == {
        "shoulder": [170.0, 251.0],
        "elbow": [147.0, 405.0],
        "wrist": [115.0, 529.0],
    }

    visible, trace_stats = source_skin_visible(source)
    upper_anatomy_envelope = anatomical_upper_arm()
    elbow_reassigned_bool = (
        (visible["upper_arm"] > 8)
        & (upper_anatomy_envelope <= 8)
    )
    elbow_reassigned = (
        elbow_reassigned_bool.astype(np.uint8) * 255
    )
    visible["upper_arm"][elbow_reassigned_bool] = 0
    visible["forearm"][elbow_reassigned_bool] = 255
    trace_stats["upperToForearmElbowReassignedPixels"] = int(
        np.count_nonzero(elbow_reassigned > 8)
    )
    skin_union_before_bracelet = np.maximum.reduce(list(visible.values()))
    forearm_skin_before_bracelet = visible["forearm"].copy()
    bracelet, bracelet_contour_points = source_bracelet_visible(source)
    bracelet_added = (bracelet > 8) & (visible["forearm"] <= 8)
    visible["forearm"] = np.maximum(visible["forearm"], bracelet)
    bracelet_removed_from_hand = (bracelet > 8) & (visible["hand"] > 8)
    visible["hand"][bracelet > 8] = 0
    trace_stats["skinVisibleUnionPixels"] = trace_stats["visibleUnionPixels"]
    trace_stats["braceletContourPointCount"] = bracelet_contour_points
    trace_stats["braceletVisiblePixelsOwnedByForearm"] = int(
        np.count_nonzero(bracelet > 8)
    )
    trace_stats["braceletPixelsAddedBeyondSkinExtraction"] = int(
        np.count_nonzero(bracelet_added)
    )
    trace_stats["braceletPixelsRemovedFromHandOwnership"] = int(
        np.count_nonzero(bracelet_removed_from_hand)
    )
    trace_stats["visibleUnionPixels"] = int(
        np.count_nonzero(
            np.maximum(skin_union_before_bracelet, bracelet)
        )
    )
    complete, hidden = build_complete(visible, bracelet)
    frozen_sleeve_visible = np.asarray(
        Image.open(V30_SLEEVE_VISIBLE).convert("L"), dtype=np.uint8
    )
    frozen_sleeve_complete = np.asarray(
        Image.open(V30_SLEEVE_COMPLETE).convert("L"), dtype=np.uint8
    )
    source_sleeve, sleeve_contour_points = source_sleeve_visible(source)
    (
        sleeve_visible,
        sleeve_complete,
        sleeve_hidden,
        cuff_correction,
    ) = correct_frozen_sleeve_cuff(
        source_sleeve,
        frozen_sleeve_visible,
        frozen_sleeve_complete,
    )

    visible_layers = {
        name: solid(visible[name], COLORS[name])
        for name in ("upper_arm", "forearm", "hand")
    }
    complete_layers = {
        name: solid(complete[name], COLORS[name])
        for name in ("upper_arm", "forearm", "hand")
    }
    visible_layers["sleeve"] = solid(sleeve_visible, COLORS["sleeve"])
    complete_layers["sleeve"] = solid(sleeve_complete, COLORS["sleeve"])

    for name in ("upper_arm", "forearm", "hand"):
        Image.fromarray(visible[name]).save(ROOT / f"masks/visible/{name}.png")
        Image.fromarray(hidden[name]).save(ROOT / f"masks/hidden/{name}.png")
        Image.fromarray(complete[name]).save(ROOT / f"masks/complete/{name}.png")
        complete_layers[name].save(ROOT / f"materials/{name}.png")
    Image.fromarray(sleeve_visible).save(ROOT / "masks/visible/sleeve.png")
    Image.fromarray(bracelet).save(
        ROOT / "masks/visible/bracelet-owned-by-forearm.png"
    )
    Image.fromarray(sleeve_hidden).save(ROOT / "masks/hidden/sleeve.png")
    Image.fromarray(sleeve_complete).save(ROOT / "masks/complete/sleeve.png")
    complete_layers["sleeve"].save(ROOT / "materials/sleeve.png")

    for item in upper_freeze["lockedGeometry"]:
        assert sha256(ROOT / item["path"]) == item["sha256"]

    rejected_upper = np.maximum(
        visible["upper_arm"],
        ribbon(
            [
                S - (E - S) / np.linalg.norm(E - S) * 5.0,
                np.array((159.0, 332.0)),
                E + (E - S) / np.linalg.norm(E - S) * 14.0,
            ],
            [12.5, 14.5, 18.0],
        ),
    )
    approved_right_mask = np.asarray(
        Image.open(RIGHT_V6_UPPER_MASK).convert("L"), dtype=np.uint8
    )
    upper_compare = Image.new("RGB", (1200, 650), (244, 247, 251))
    for col, (mask, label, label_color) in enumerate(
        (
            (
                rejected_upper,
                "① 修前：通用直条",
                (166, 42, 42),
            ),
            (
                approved_right_mask,
                "② 已批准 right 原型",
                (44, 92, 150),
            ),
            (
                complete["upper_arm"],
                "③ 修后：镜像注册到 left 骨架",
                (22, 112, 76),
            ),
        )
    ):
        isolated = checker((W, H)).convert("RGBA")
        isolated.alpha_composite(solid(mask, COLORS["upper_arm"]))
        bbox = Image.fromarray(mask).getbbox()
        crop = isolated.crop(
            (
                max(0, bbox[0] - 20),
                max(0, bbox[1] - 20),
                min(W, bbox[2] + 20),
                min(H, bbox[3] + 20),
            )
        )
        scale = min(330 / crop.width, 540 / crop.height)
        crop = crop.resize(
            (
                max(1, round(crop.width * scale)),
                max(1, round(crop.height * scale)),
            ),
            Image.Resampling.NEAREST,
        )
        x = col * 400 + (400 - crop.width) // 2
        upper_compare.paste(crop.convert("RGB"), (x, 70))
        ImageDraw.Draw(upper_compare).text(
            (col * 400 + 22, 20),
            label,
            fill=label_color,
            font=font(22, True),
        )
    upper_compare.save(ROOT / "qa/upper-arm-anatomy-before-after.png")

    forearm_before_mask = np.asarray(
        Image.open(FOREARM_BEFORE_CONVEX_CAPS).convert("L"), dtype=np.uint8
    )
    forearm_compare = Image.new("RGB", (1200, 650), (244, 247, 251))
    compare_draw = ImageDraw.Draw(forearm_compare)
    for col, (mask, label) in enumerate(
        (
            (forearm_before_mask, "① 修前：浅弧削角"),
            (complete["forearm"], "② 修后：肘帽＋腕端曲线榫头"),
        )
    ):
        isolated = checker((W, H)).convert("RGBA")
        isolated.alpha_composite(solid(mask, COLORS["forearm"]))
        bbox = Image.fromarray(mask).getbbox()
        crop = isolated.crop(
            (
                max(0, bbox[0] - 20),
                max(0, bbox[1] - 20),
                min(W, bbox[2] + 20),
                min(H, bbox[3] + 20),
            )
        )
        scale = min(330 / crop.width, 520 / crop.height)
        crop = crop.resize(
            (
                max(1, round(crop.width * scale)),
                max(1, round(crop.height * scale)),
            ),
            Image.Resampling.LANCZOS,
        )
        x = col * 400 + (400 - crop.width) // 2
        forearm_compare.paste(crop.convert("RGB"), (x, 70))
        compare_draw.text(
            (col * 400 + 22, 20),
            label,
            fill=(166, 42, 42) if col == 0 else (22, 112, 76),
            font=font(22, True),
        )

    added_forearm = np.where(
        (complete["forearm"] > 8) & (forearm_before_mask <= 8),
        255,
        0,
    ).astype(np.uint8)
    removed_forearm = np.where(
        (complete["forearm"] <= 8) & (forearm_before_mask > 8),
        255,
        0,
    ).astype(np.uint8)
    root_review = checker((W, H)).convert("RGBA")
    root_review.alpha_composite(solid(complete["forearm"], COLORS["forearm"]))
    root_review.alpha_composite(solid(added_forearm, (218, 45, 62, 255)))
    proximal_crop = root_review.crop((105, 370, 190, 455))
    proximal_crop = proximal_crop.resize(
        (510, 230), Image.Resampling.LANCZOS
    )
    distal_crop = root_review.crop((75, 500, 145, 570))
    distal_crop = distal_crop.resize(
        (510, 230), Image.Resampling.LANCZOS
    )
    forearm_compare.paste(proximal_crop.convert("RGB"), (845, 80))
    forearm_compare.paste(distal_crop.convert("RGB"), (845, 355))
    compare_draw.text(
        (855, 315),
        "肘端",
        fill=(58, 71, 91),
        font=font(18, True),
    )
    compare_draw.text(
        (855, 590),
        "腕端",
        fill=(58, 71, 91),
        font=font(18, True),
    )
    compare_draw.text(
        (822, 20),
        "③ 红色=新增的肘帽与腕端隐藏榫头",
        fill=(166, 42, 42),
        font=font(22, True),
    )
    forearm_compare.save(ROOT / "qa/forearm-root-before-after.png")

    skeleton_out = dict(skeleton)
    skeleton_out["status"] = "unchanged_from_user_approved_v25_for_v31"
    skeleton_out["geometryMutation"] = "none"
    skeleton_out["v30SleeveEvidence"] = {
        "manifest": "../arm-chain-screen-left-v30-right-structure-convergence/audit/v30-sleeve-geometry-freeze-manifest-2026-07-28.json",
        "sha256": sha256(V30_FREEZE),
        "status": "preserved_but_cuff_visual_regression_reported_by_user",
    }
    save_json(ROOT / "skeleton-lock.json", skeleton_out)

    contract = {
        "schemaVersion": 1,
        "status": "stage_a_geometry_candidate_pending_user_visual_approval",
        "scope": "screen-left cuff correction plus upper arm, forearm, and hand geometry",
        "authority": {
            "resetColorMasterSha256": sha256(SOURCE),
            "approvedSkeletonSha256": frozen_hashes["skeleton-lock.json"],
            "rejectedV30SleeveManifestSha256": sha256(V30_FREEZE),
            "approvedRightUpperArmV6ManifestSha256": sha256(RIGHT_V6_FREEZE),
            "approvedRightUpperArmMaskSha256": sha256(RIGHT_V6_UPPER_MASK),
        },
        "construction": {
            "visiblePixels": "fresh deterministic extraction from the Reset color master inside the screen-left arm semantic envelope",
            "oldMaterialUse": "none; V26 and V27 are failure comparison only",
            "jointMethod": "exact approved screen-right V6 upper-arm mask mirrored in bone-local coordinates onto the unchanged screen-left shoulder/elbow frame; smooth tapered axial continuation through elbow and wrist; no circular seam patches",
            "cuffCorrection": "V30 is preserved as rejected evidence; from row 350 downward, both visible and complete sleeve ownership are clamped to the closed Reset semantic cuff outline",
        },
        "layers": [
            {
                "id": "upper_arm",
                "visiblePixelOwnership": "source skin from frozen sleeve cuff to elbow split",
                "hiddenExtensionResponsibility": "character-specific continuous shoulder-to-elbow body inherited from the approved screen-right V6 bone-local silhouette, mirrored for the opposite arm and tapered into the elbow beneath the sleeve",
                "overlapResponsibility": [
                    "beneath frozen sleeve at cuff",
                    "beneath forearm across elbow corridor",
                ],
                "forbiddenIntrusion": ["hair", "shirt torso", "background"],
                "drawOrder": 10,
            },
            {
                "id": "forearm",
                "visiblePixelOwnership": "source skin from elbow split through wrist plus the complete visible bracelet silhouette; bracelet is a forearm-owned attached accessory in the four-layer Stage A contract",
                "hiddenExtensionResponsibility": "tapered elbow and wrist roots following the approved forearm axis",
                "overlapResponsibility": [
                    "over upper arm at elbow",
                    "beneath hand at wrist except the bracelet-owned corridor, which is excluded from hand ownership",
                ],
                "attachedAccessory": {
                    "id": "bracelet",
                    "parent": "forearm",
                    "movesWith": "forearm",
                    "visibleMask": "masks/visible/bracelet-owned-by-forearm.png",
                    "construction": "8x supersampled fine double-chain, bead, knot, and dangle silhouette traced from Reset; no filled outer hull",
                },
                "forbiddenIntrusion": ["shirt torso", "background", "palm"],
                "drawOrder": 20,
            },
            {
                "id": "hand",
                "visiblePixelOwnership": "source palm, thumb, and all finger silhouettes distal to the forearm-owned bracelet corridor, without polygon simplification",
                "hiddenExtensionResponsibility": "short tapered wrist root aligned to the forearm, with palm participating in wrist motion",
                "overlapResponsibility": ["over forearm at wrist"],
                "forbiddenIntrusion": [
                    "forearm shaft",
                    "shirt",
                    "skirt",
                    "background",
                    "bracelet",
                ],
                "drawOrder": 30,
            },
        ],
        "v30Sleeve": "preserved read-only as rejected evidence after the user identified the extra cuff block",
        "stop": "remain at Stage A until user approves the Chinese visual review board",
    }
    save_json(ROOT / "layering-contract.json", contract)

    default = composite(visible_layers)
    default.save(ROOT / "qa/default-recomposition.png")
    overlay = source.copy()
    tint = default.copy()
    tint.putalpha(tint.getchannel("A").point(lambda p: round(p * 0.62)))
    overlay.alpha_composite(tint)
    overlay.save(ROOT / "qa/default-overlay-original.png")

    before_layers = dict(visible_layers)
    before_layers["sleeve"] = solid(
        frozen_sleeve_visible, COLORS["sleeve"]
    )
    before_default = composite(before_layers)
    before_overlay = source.copy()
    before_tint = before_default.copy()
    before_tint.putalpha(
        before_tint.getchannel("A").point(lambda p: round(p * 0.62))
    )
    before_overlay.alpha_composite(before_tint)
    cuff_compare = Image.new("RGB", (1000, 470), (244, 247, 251))
    before_crop = crop4(before_overlay, (95, 345, 200, 435))
    after_crop = crop4(overlay, (95, 345, 200, 435))
    cuff_compare.paste(before_crop.convert("RGB"), (40, 50))
    cuff_compare.paste(after_crop.convert("RGB"), (540, 50))
    compare_draw = ImageDraw.Draw(cuff_compare)
    compare_draw.text(
        (40, 10),
        "修前：蓝色整块压住皮肤",
        fill=(166, 42, 42),
        font=font(25, True),
    )
    compare_draw.text(
        (540, 10),
        "修后：袖口回到原图斜线",
        fill=(22, 112, 76),
        font=font(25, True),
    )
    cuff_compare.save(ROOT / "qa/cuff-correction-before-after.png")

    for name in ("upper_arm", "forearm", "hand"):
        moved_check(name, complete_layers, visible_layers).save(
            ROOT / f"qa/displaced-{name}.png"
        )

    cuff = crop4(overlay, (105, 365, 195, 445))
    elbow = crop4(composite(complete_layers, source), (110, 380, 185, 445))
    wrist = crop4(composite(complete_layers, source), (80, 500, 140, 565))
    hand_zoom = crop4(overlay, (48, 520, 130, 630))
    source_bracelet_zoom = crop_smooth(source, (75, 490, 150, 565))
    cuff.save(ROOT / "qa/zoom-cuff-upper-arm.png")
    elbow.save(ROOT / "qa/zoom-elbow.png")
    wrist.save(ROOT / "qa/zoom-wrist.png")
    hand_zoom.save(ROOT / "qa/zoom-hand.png")
    source_bracelet_zoom.save(ROOT / "qa/source-bracelet-zoom.png")
    bracelet_flat_zoom = crop_smooth(default, (75, 490, 150, 565))
    bracelet_overlay_zoom = crop_smooth(overlay, (75, 490, 150, 565))
    bracelet_isolated = checker((W, H)).convert("RGBA")
    bracelet_isolated.alpha_composite(
        solid(bracelet, COLORS["forearm"])
    )
    bracelet_isolated_zoom = crop_smooth(
        bracelet_isolated, (75, 490, 150, 565)
    )
    bracelet_board = Image.new("RGB", (1600, 560), (241, 245, 250))
    fit(
        bracelet_board,
        source_bracelet_zoom,
        (20, 20, 390, 540),
        "① Reset 原图：手链轮廓权威",
    )
    fit(
        bracelet_board,
        bracelet_flat_zoom,
        (410, 20, 780, 540),
        "② 纯色回组：橙色归前臂",
    )
    fit(
        bracelet_board,
        bracelet_overlay_zoom,
        (800, 20, 1170, 540),
        "③ 叠原图：检查漏出/侵入",
    )
    fit(
        bracelet_board,
        bracelet_isolated_zoom,
        (1190, 20, 1580, 540),
        "④ 手链归属掩码：不属于手",
    )
    bracelet_board.save(ROOT / "qa/bracelet-forearm-ownership-review.png")

    u2 = (WR - E) / np.linalg.norm(WR - E)
    forearm_body_without_bracelet = np.maximum(
        forearm_skin_before_bracelet, anatomical_forearm()
    )
    body_y, body_x = np.where(forearm_body_without_bracelet > 8)
    body_projection = (
        (body_x - E[0]) * u2[0] + (body_y - E[1]) * u2[1]
    )
    wrist_projection = float(np.linalg.norm(WR - E))
    complete_max_projection = float(body_projection.max())
    extension_beyond_wrist = complete_max_projection - wrist_projection

    def wrist_marker(image):
        marked = image.copy().convert("RGBA")
        marker = ImageDraw.Draw(marked)
        normal = np.array((-u2[1], u2[0]))
        plane_a = WR - normal * 22
        plane_b = WR + normal * 22
        endpoint = WR + u2 * extension_beyond_wrist
        marker.line(
            [tuple(plane_a), tuple(plane_b)],
            fill=(225, 45, 62, 255),
            width=2,
        )
        marker.ellipse(
            (WR[0] - 3, WR[1] - 3, WR[0] + 3, WR[1] + 3),
            fill=(225, 45, 62, 255),
        )
        marker.line(
            [tuple(WR), tuple(endpoint)],
            fill=(0, 151, 190, 255),
            width=2,
        )
        marker.ellipse(
            (
                endpoint[0] - 2,
                endpoint[1] - 2,
                endpoint[0] + 2,
                endpoint[1] + 2,
            ),
            fill=(0, 151, 190, 255),
        )
        return marked

    forearm_only = checker((W, H)).convert("RGBA")
    forearm_only.alpha_composite(
        solid(forearm_body_without_bracelet, COLORS["forearm"])
    )
    forearm_only = wrist_marker(forearm_only)

    hidden_wrist_tongue = anatomical_wrist_tongue()
    ownership_diagnostic = checker((W, H)).convert("RGBA")
    diagnostic_hand = solid(complete["hand"], COLORS["hand"])
    diagnostic_hand.putalpha(
        diagnostic_hand.getchannel("A").point(
            lambda alpha: round(alpha * 0.32)
        )
    )
    ownership_diagnostic.alpha_composite(diagnostic_hand)
    ownership_diagnostic.alpha_composite(
        solid(hidden_wrist_tongue, (225, 45, 62, 230))
    )
    ownership_diagnostic.alpha_composite(
        solid(bracelet, (155, 73, 188, 255))
    )

    default_marked = wrist_marker(default)
    wrist_board = Image.new("RGB", (1600, 650), (241, 245, 250))
    fit(
        wrist_board,
        crop_smooth(source, (75, 485, 150, 575)),
        (20, 20, 390, 610),
        "① Reset：腕点、手链与手掌关系",
    )
    fit(
        wrist_board,
        crop_smooth(forearm_only, (75, 485, 150, 575)),
        (410, 20, 780, 610),
        f"② 移开手：前臂越过腕点 {extension_beyond_wrist:.1f}px",
    )
    fit(
        wrist_board,
        crop_smooth(ownership_diagnostic, (75, 485, 150, 575)),
        (800, 20, 1170, 610),
        "③ 上贴手链｜两侧贴边｜底部凸包",
    )
    fit(
        wrist_board,
        crop_smooth(default_marked, (75, 485, 150, 575)),
        (1190, 20, 1580, 610),
        "④ 默认回组：绿色手遮住隐藏延伸",
    )
    ImageDraw.Draw(wrist_board).text(
        (30, 615),
        "红线/红点=锁定腕点；红色块=按你标注伸入手掌的前臂隐藏榫头；紫色手链仍归前臂。腕点和 L2 未改。",
        fill=(58, 71, 91),
        font=font(20, True),
    )
    wrist_board.save(
        ROOT / "qa/forearm-wrist-length-and-bracelet-review.png"
    )

    yy, xx = np.indices((H, W))
    projection_from_wrist = (
        (xx - WR[0]) * u2[0] + (yy - WR[1]) * u2[1]
    )
    tongue_clearance_mask = np.where(
        projection_from_wrist >= -1.0,
        hidden_wrist_tongue,
        0,
    ).astype(np.uint8)
    tongue_clearance_layer = solid(
        tongue_clearance_mask, (225, 45, 62, 230)
    )

    def tongue_leak_pixels(tongue_pose, hand_pose):
        tongue_alpha = np.asarray(tongue_pose.getchannel("A")) > 32
        hand_alpha = np.asarray(hand_pose.getchannel("A")) > 8
        hand_with_raster_tolerance = cv2.dilate(
            hand_alpha.astype(np.uint8),
            np.ones((3, 3), dtype=np.uint8),
            iterations=1,
        ) > 0
        leak = tongue_alpha & ~hand_with_raster_tolerance
        return int(np.count_nonzero(leak)), leak

    wrist_stress_angles = (-12, -8, -4, 0, 4, 8, 12)
    wrist_stress_results = []
    wrist_stress_board = Image.new(
        "RGB", (2100, 560), (241, 245, 250)
    )
    for col, angle in enumerate(wrist_stress_angles):
        stress_hand = rotate_translate(
            complete_layers["hand"], WR, WR, angle
        )
        leak_count, leak_mask = tongue_leak_pixels(
            tongue_clearance_layer, stress_hand
        )
        wrist_stress_results.append(
            {"wristLocalDeg": angle, "leakPixels": leak_count}
        )
        diagnostic = checker((W, H)).convert("RGBA")
        translucent_hand = stress_hand.copy()
        translucent_hand.putalpha(
            translucent_hand.getchannel("A").point(
                lambda alpha: round(alpha * 0.32)
            )
        )
        diagnostic.alpha_composite(translucent_hand)
        diagnostic.alpha_composite(tongue_clearance_layer)
        if leak_count:
            diagnostic.alpha_composite(
                solid(leak_mask.astype(np.uint8) * 255, (255, 213, 46, 255))
            )
        fit(
            wrist_stress_board,
            crop_smooth(diagnostic, (75, 490, 150, 580)),
            (col * 300 + 10, 20, col * 300 + 290, 530),
            f"{angle:+d}°｜外露 {leak_count}px",
        )
    ImageDraw.Draw(wrist_stress_board).text(
        (25, 532),
        "红=前臂隐藏楔形；绿=手部；黄=超出手部覆盖范围。±12°仅为穿模压力检查，不是已批准动作范围。",
        fill=(58, 71, 91),
        font=font(19, True),
    )
    wrist_stress_board.save(
        ROOT / "qa/wrist-hidden-tongue-motion-clearance-review.png"
    )

    rest1 = skeleton["restAnglesDeg"]["theta1"]
    rest2 = skeleton["restAnglesDeg"]["theta2"]
    target = skeleton["stageAQaMotion"]["target"]
    l1 = skeleton["boneLengthsPx"]["L1ShoulderToElbow"]
    l2 = skeleton["boneLengthsPx"]["L2ElbowToWrist"]
    rest_global = math.degrees(math.atan2(WR[1] - E[1], WR[0] - E[0]))
    samples, frames, selected, joint_evidence = [], [], {}, {}
    first_hash = last_hash = None
    for index in range(41):
        k = index if index <= 20 else 40 - index
        progress = 0.5 * (1 - math.cos(math.pi * k / 20))
        theta1 = rest1 + (target["theta1"] - rest1) * progress
        theta2 = rest2 + (target["theta2"] - rest2) * progress
        d1 = theta1 - rest1
        new_e = point_at(S, l1, theta1)
        new_w = point_at(new_e, l2, theta1 + theta2)
        d2 = theta1 + theta2 - rest_global
        posed = {
            "upper_arm": rotate_translate_padded(
                complete_layers["upper_arm"], S, S, d1
            ),
            "forearm": rotate_translate_padded(
                complete_layers["forearm"], E, new_e, d2
            ),
            "hand": rotate_translate_padded(
                complete_layers["hand"],
                WR,
                new_w,
                d2 + target["wristLocal"] * progress,
            ),
            "sleeve": rotate_translate_padded(
                complete_layers["sleeve"], S, S, d1 * 0.82
            ),
        }
        posed_tongue = rotate_translate_padded(
            tongue_clearance_layer, E, new_e, d2
        )
        tongue_leak_count, _ = tongue_leak_pixels(
            posed_tongue, posed["hand"]
        )
        pose = composite_motion(posed)
        digest = hashlib.sha256(pose.tobytes()).hexdigest()
        first_hash = digest if index == 0 else first_hash
        last_hash = digest if index == 40 else last_hash
        seam_counts = {
            "sleeveUpper": overlap(posed["sleeve"], posed["upper_arm"]),
            "upperForearm": overlap(posed["upper_arm"], posed["forearm"]),
            "forearmHand": overlap(posed["forearm"], posed["hand"]),
        }
        pose_alpha = np.asarray(pose.getchannel("A"))
        connected = components(pose_alpha) == 1
        touches_canvas_edge = bool(
            np.any(pose_alpha[:3] > 8)
            or np.any(pose_alpha[-3:] > 8)
            or np.any(pose_alpha[:, :3] > 8)
            or np.any(pose_alpha[:, -3:] > 8)
        )
        passed = (
            seam_counts["sleeveUpper"] >= 1800
            and seam_counts["upperForearm"] >= 280
            and seam_counts["forearmHand"] >= 360
            and tongue_leak_count <= 2
            and connected
            and not touches_canvas_edge
        )
        samples.append(
            {
                "index": index,
                "progress": progress,
                "elbowPx": [float(x) for x in new_e],
                "wristPx": [float(x) for x in new_w],
                "L1Px": float(np.linalg.norm(new_e - S)),
                "L2Px": float(np.linalg.norm(new_w - new_e)),
                "overlapPixels": seam_counts,
                "wristTongueLeakPixels": tongue_leak_count,
                "connected": connected,
                "touchesMotionCanvasEdge": touches_canvas_edge,
                "pass": passed,
            }
        )
        frame = Image.new("RGB", (500, 960), "white")
        bbox = pose.getchannel("A").getbbox()
        crop = pose.crop(
            (
                max(0, bbox[0] - 18),
                max(0, bbox[1] - 18),
                min(MOTION_W, bbox[2] + 18),
                min(H, bbox[3] + 18),
            )
        )
        crop.thumbnail((470, 880), Image.Resampling.LANCZOS)
        frame.paste(
            crop.convert("RGB"),
            ((500 - crop.width) // 2, 48),
            crop.getchannel("A"),
        )
        ImageDraw.Draw(frame).text(
            (14, 8),
            f"样本 {index:02d}｜{progress:.2f}",
            fill=(18, 28, 43),
            font=font(20, True),
        )
        frame.save(ROOT / f"samples/fk-{index:03d}.png")
        thumb = frame.resize((250, 480), Image.Resampling.LANCZOS)
        frames.append(thumb)
        if index in (0, 10, 20, 30, 40):
            selected[index] = thumb
        if index in (0, 10, 20):
            overlap_debug = Image.new(
                "RGBA", (MOTION_W, H), (0, 0, 0, 0)
            )
            overlap_debug.alpha_composite(posed["upper_arm"])
            translucent_forearm = posed["forearm"].copy()
            translucent_forearm.putalpha(
                translucent_forearm.getchannel("A").point(
                    lambda p: round(p * 0.62)
                )
            )
            overlap_debug.alpha_composite(translucent_forearm)
            joint_evidence[index] = {
                "pose": pose.copy(),
                "overlapDebug": overlap_debug,
                "elbow": new_e + MOTION_OFFSET,
                "wrist": new_w + MOTION_OFFSET,
            }

    save_json(ROOT / "samples/fk-41-samples.json", samples)
    frames[0].save(
        ROOT / "qa/fk-41-slow-preview.gif",
        save_all=True,
        append_images=frames[1:],
        duration=190,
        loop=0,
        disposal=2,
    )
    contact = Image.new("RGB", (1250, 540), (244, 247, 251))
    for col, index in enumerate((0, 10, 20, 30, 40)):
        contact.paste(selected[index], (col * 250, 34))
        ImageDraw.Draw(contact).text(
            (col * 250 + 10, 5),
            f"{index:02d}",
            fill=(18, 28, 43),
            font=font(20, True),
        )
    contact.save(ROOT / "qa/fk-selected-contact-sheet.png")

    transition_board = Image.new("RGB", (2200, 2040), (241, 245, 250))
    transition_draw = ImageDraw.Draw(transition_board)
    transition_draw.text(
        (45, 25),
        "小星 V31｜衔接处大图审查：袖口/肘 与 腕/手",
        fill=(18, 28, 43),
        font=font(40, True),
    )
    transition_draw.text(
        (45, 82),
        "蓝=袖子，红=冻结大臂，橙=本次补全前臂，绿=手；逐格看是否开缝、突起、变细或像补丁。",
        fill=(58, 71, 91),
        font=font(24),
    )
    review_rows = (
        ("pose", "elbow", "默认：袖口—大臂—前臂"),
        (
            "overlapDebug",
            "elbow",
            "诊断：移除袖子，前臂半透明看肘部重叠",
        ),
        ("pose", "wrist", "默认：前臂—腕—手掌"),
    )
    for col, index in enumerate((0, 10, 20)):
        evidence = joint_evidence[index]
        for row, (image_key, joint_name, joint_label) in enumerate(
            review_rows
        ):
            center = evidence[joint_name]
            radius = 70 if joint_name == "elbow" else 58
            x0 = max(0, int(round(center[0])) - radius)
            y0 = max(0, int(round(center[1])) - radius)
            x1 = min(MOTION_W, int(round(center[0])) + radius)
            y1 = min(H, int(round(center[1])) + radius)
            crop = evidence[image_key].crop((x0, y0, x1, y1))
            backing = checker(crop.size).convert("RGBA")
            backing.alpha_composite(crop)
            backing = backing.resize((620, 520), Image.Resampling.LANCZOS)
            px = 45 + col * 710
            py = 150 + row * 590
            transition_board.paste(backing.convert("RGB"), (px, py))
            transition_draw.text(
                (px, py + 530),
                f"样本 {index:02d}｜{joint_label}",
                fill=(18, 28, 43),
                font=font(23, True),
            )
    transition_draw.rounded_rectangle(
        (45, 1935, 2155, 2010),
        14,
        fill="white",
        outline=(175, 186, 203),
        width=2,
    )
    transition_draw.text(
        (70, 1957),
        "需要你批准：上排是否接住袖口；中排红色大臂隐藏端与半透明橙色前臂是否自然重叠；下排腕与手掌是否连续。",
        fill=(139, 66, 30),
        font=font(23, True),
    )
    transition_board.save(ROOT / "qa/joint-transitions-review.png")

    visible_union = np.maximum.reduce(list(visible.values()))
    visible_overlaps = {
        "upperForearm": int(
            np.count_nonzero((visible["upper_arm"] > 8) & (visible["forearm"] > 8))
        ),
        "forearmHand": int(
            np.count_nonzero((visible["forearm"] > 8) & (visible["hand"] > 8))
        ),
    }
    default_overlap = {
        "sleeveUpper": overlap(
            complete_layers["sleeve"], complete_layers["upper_arm"]
        ),
        "upperForearm": overlap(
            complete_layers["upper_arm"], complete_layers["forearm"]
        ),
        "forearmHand": overlap(
            complete_layers["forearm"], complete_layers["hand"]
        ),
    }
    max_l1_error = max(abs(x["L1Px"] - l1) for x in samples)
    max_l2_error = max(abs(x["L2Px"] - l2) for x in samples)
    all_frames_pass = all(x["pass"] for x in samples)
    forearm_skin_complete = np.maximum(
        forearm_skin_before_bracelet, anatomical_forearm()
    )
    forearm_skin_holes = holes(forearm_skin_complete)
    bracelet_loop_holes = max(
        0, holes(complete["forearm"]) - forearm_skin_holes
    )
    bracelet_structural_loop_holes = max(
        0,
        holes_with_min_area(complete["forearm"], 8.0)
        - forearm_skin_holes,
    )
    base_geometry_pass = (
        components(complete["upper_arm"]) == 1
        and holes(complete["upper_arm"]) == 0
        and components(complete["forearm"]) == 1
        and forearm_skin_holes == 0
        and bracelet_structural_loop_holes <= 2
        and components(complete["hand"]) == 1
        and holes(complete["hand"]) == 0
    )
    source_trace_pass = (
        trace_stats["visibleUnionPixels"]
        == int(np.count_nonzero(visible_union))
        and max(visible_overlaps.values()) == 0
    )
    wrist_clearance_pass = (
        max(x["wristTongueLeakPixels"] for x in samples) <= 2
        and max(x["leakPixels"] for x in wrist_stress_results) <= 2
    )
    report = {
        "schemaVersion": 1,
        "status": (
            "engineering_pass_pending_user_visual_approval"
            if (
                all_frames_pass
                and base_geometry_pass
                and source_trace_pass
                and wrist_clearance_pass
            )
            else "engineering_fail_stop_stage_a"
        ),
        "scope": "screen-left cuff correction plus upper arm, forearm, and hand Stage A geometry",
        "authoritativeInputs": {
            "resetColorMasterSha256": sha256(SOURCE),
            "rejectedV30SleeveManifestSha256": sha256(V30_FREEZE),
            "approvedSkeletonSha256": frozen_hashes["skeleton-lock.json"],
            "approvedRightUpperArmV6ManifestSha256": sha256(RIGHT_V6_FREEZE),
            "approvedRightUpperArmMaskSha256": sha256(RIGHT_V6_UPPER_MASK),
            "pass": True,
        },
        "skeletonUnchanged": True,
        "upperArmFrozen": {
            "manifest": "audit/v31-upper-arm-geometry-freeze-manifest-2026-07-28.json",
            "status": upper_freeze["status"],
            "lockedArtifactCount": len(upper_freeze["lockedGeometry"]),
            "pass": all(
                sha256(ROOT / item["path"]) == item["sha256"]
                for item in upper_freeze["lockedGeometry"]
            ),
        },
        "forearmFrozen": (
            {
                "manifest": "audit/v31-forearm-geometry-freeze-manifest-2026-07-29.json",
                "status": forearm_freeze["status"],
                "lockedArtifactCount": len(
                    forearm_freeze["lockedGeometry"]
                ),
                "pass": all(
                    sha256(ROOT / item["path"]) == item["sha256"]
                    for item in forearm_freeze["lockedGeometry"]
                ),
            }
            if forearm_freeze is not None
            else {
                "status": "not_frozen",
                "pass": False,
            }
        ),
        "cuffCorrection": {
            **cuff_correction,
            "sourceSleeveContourPointCount": sleeve_contour_points,
            "sourceRule": "closed Reset semantic cuff outline is authoritative from row 350 downward",
            "pass": (
                cuff_correction["correctedVisibleBeyondSourceCuffPixels"] == 0
                and cuff_correction["correctedCompleteBeyondSourceCuffPixels"]
                == 0
                and cuff_correction["terminalVisiblePixelsRows410Plus"] == 0
            ),
        },
        "sourceTracing": {
            **trace_stats,
            "visibleUnionPixelsAfterSemanticSplit": int(
                np.count_nonzero(visible_union)
            ),
            "visibleLayerOverlapPixels": visible_overlaps,
            "pass": source_trace_pass,
        },
        "geometry": {
            name: {
                "components": components(complete[name]),
                "holes": holes(complete[name]),
                "visiblePixels": int(np.count_nonzero(visible[name] > 8)),
                "hiddenPixels": int(np.count_nonzero(hidden[name] > 8)),
            }
            for name in ("upper_arm", "forearm", "hand")
        },
        "upperArmAnatomy": {
            "profile": "exact approved screen-right V6 upper-arm geometry registered into the unchanged screen-left bone frame",
            "registration": "rigid bone-local transform with mirrored normal coordinate; identical L1",
            "rightReferenceL1Px": right_contract["frozenSkeleton"]["L1"],
            "leftTargetL1Px": round(float(np.linalg.norm(E - S)), 6),
            "sourceMaskSha256": sha256(RIGHT_V6_UPPER_MASK),
            "flatTrapezoidRejected": True,
            "genericRoundedCapsuleRejected": True,
        },
        "forearmProximalCorrection": {
            "reason": "user explicitly specifies outward convex round caps at both ends to support joint overlap",
            "method": "use an integrated outward cubic-bezier cap at the elbow and a wrist-plane-origin rounded hidden tongue that tapers directly into the hand; both are continuous parts of the forearm silhouette, not separate circular patches",
            "addedPixels": int(np.count_nonzero(added_forearm > 8)),
            "removedPixels": int(np.count_nonzero(removed_forearm > 8)),
            "circularPatchUsed": False,
            "straightCapRejected": True,
            "rootLongitudinalExtensionBeyondSideEndpointsPx": 18.0,
            "wristShaftEndpointBeyondLockedWristPx": 0.0,
            "wristRoundedTongueNominalExtensionBeyondLockedWristPx": 19.0,
            "wristRoundedTongueBezierSegments": 3,
            "wristBoundaryRule": "start 5 px above the locked wrist under the bracelet, keep both sides close to the wrist skin boundary, then close with a downward convex U-cap",
            "wristMaskSupersampling": "8x with LANCZOS downsample",
            "review": "qa/forearm-root-before-after.png",
        },
        "braceletOwnership": {
            "logicalOwner": "forearm",
            "movesWith": "forearm",
            "construction": "8x supersampled fine double-chain, bead, knot, and dangle silhouette traced from Reset; no filled outer hull",
            "mask": "masks/visible/bracelet-owned-by-forearm.png",
            "visiblePixels": int(np.count_nonzero(bracelet > 8)),
            "pixelsAddedBeyondSkinThreshold": int(
                np.count_nonzero(bracelet_added)
            ),
            "pixelsRemovedFromHandOwnership": int(
                np.count_nonzero(bracelet_removed_from_hand)
            ),
            "naturalTransparentLoopHoles": bracelet_loop_holes,
            "structuralTransparentLoopHolesArea8PxPlus": bracelet_structural_loop_holes,
            "forearmSkinBodyHoles": forearm_skin_holes,
            "maximumDeclaredAccessoryLoopHoles": 2,
            "accessoryLoopHolesAllowed": bracelet_structural_loop_holes <= 2,
            "review": "qa/bracelet-forearm-ownership-review.png",
            "status": "pending_user_visual_approval",
        },
        "forearmWristReach": {
            "lockedWristPointPx": [float(WR[0]), float(WR[1])],
            "wristProjectionFromElbowPx": round(wrist_projection, 6),
            "completeForearmMaxProjectionPx": round(
                complete_max_projection, 6
            ),
            "hiddenExtensionBeyondWristPx": round(
                extension_beyond_wrist, 6
            ),
            "handMovedAwayForReview": True,
            "review": "qa/forearm-wrist-length-and-bracelet-review.png",
            "pass": extension_beyond_wrist >= 10.0,
        },
        "wristTongueMotionClearance": {
            "method": "count U-cap pixels from 1 px above the locked wrist downward that fall outside the hand cover after a one-pixel raster tolerance; the proximal closure is under the bracelet",
            "all41ApprovedPullTestMaximumLeakPixels": max(
                x["wristTongueLeakPixels"] for x in samples
            ),
            "diagnosticWristLocalSweepDeg": list(wrist_stress_angles),
            "diagnosticSweepResults": wrist_stress_results,
            "diagnosticSweepMaximumLeakPixels": max(
                x["leakPixels"] for x in wrist_stress_results
            ),
            "diagnosticSweepIsNotApprovedMotionRange": True,
            "review": "qa/wrist-hidden-tongue-motion-clearance-review.png",
            "pass": wrist_clearance_pass,
        },
        "jointTransitionVisualEvidence": {
            "review": "qa/joint-transitions-review.png",
            "samples": [0, 10, 20],
            "status": "pending_user_visual_approval",
        },
        "seams": {
            "defaultCompleteOverlapPixels": default_overlap,
            "minimumAcross41Samples": {
                seam: min(
                    x["overlapPixels"][seam] for x in samples
                )
                for seam in ("sleeveUpper", "upperForearm", "forearmHand")
            },
            "all41SamplesPass": all_frames_pass,
        },
        "boneLengths": {
            "L1Px": l1,
            "L2Px": l2,
            "maxL1ErrorPx": max_l1_error,
            "maxL2ErrorPx": max_l2_error,
            "pass": max_l1_error <= 0.01 and max_l2_error <= 0.01,
        },
        "disconnects": {
            "count": sum(1 for x in samples if not x["connected"]),
            "pass": all(x["connected"] for x in samples),
        },
        "motionCanvas": {
            "width": MOTION_W,
            "height": H,
            "horizontalReviewPaddingPx": int(MOTION_OFFSET[0]),
            "edgeTouchSampleCount": sum(
                1 for x in samples if x["touchesMotionCanvasEdge"]
            ),
            "pass": all(
                not x["touchesMotionCanvasEdge"] for x in samples
            ),
        },
        "returnConsistency": {
            "firstPoseSha256": first_hash,
            "lastPoseSha256": last_hash,
            "pass": first_hash == last_hash,
        },
        "visualGate": {
            "status": "pending_user_visual_approval",
            "review": "qa/V31-阶段A-大臂前臂手-中文视觉审查板.png",
            "earliestFailurePoint": "short wrist wedge boundary and motion-clearance visuals pending user re-review",
        },
        "stop": "remain at Stage A",
    }
    save_json(ROOT / "audit/machine-report.json", report)

    board = Image.new("RGB", (2400, 2280), (244, 247, 251))
    draw = ImageDraw.Draw(board)
    draw.text(
        (45, 24),
        "小星 V31 修正｜left 袖口、大臂、前臂、手：阶段 A 几何审查",
        fill=(18, 28, 43),
        font=font(46, True),
    )
    draw.text(
        (45, 84),
        "蓝=按 Reset 收回袖口后的候选；红=大臂；橙=前臂；绿=手。V30 保留为失败证据。",
        fill=(58, 71, 91),
        font=font(24),
    )
    fit(board, crop4(source, (35, 190, 215, 650)), (35, 135, 465, 865), "① Reset 原图：轮廓权威")
    fit(board, crop4(default, (35, 190, 215, 650)), (485, 135, 915, 865), "② 修正回组：袖口不再多一块")
    fit(board, crop4(overlay, (35, 190, 215, 650)), (935, 135, 1365, 865), "③ 叠原图：检查侵入与偏离")
    complete_only = composite(complete_layers)
    fit(board, crop4(complete_only, (35, 190, 215, 650)), (1385, 135, 1815, 865), "④ 完整材料：检查粗细与连续")
    fit(board, cuff_compare, (1835, 135, 2365, 865), "⑤ 袖口修前/修后：多余蓝块必须消失")

    moved_upper = crop4(
        moved_check("upper_arm", complete_layers, visible_layers),
        (0, 190, 512, 650),
    )
    moved_fore = crop4(
        moved_check("forearm", complete_layers, visible_layers),
        (0, 300, 512, 650),
    )
    moved_hand = crop4(
        moved_check("hand", complete_layers, visible_layers),
        (0, 390, 512, 660),
    )
    fit(board, upper_compare, (35, 905, 755, 1565), "⑥ 大臂修前/修后：检查三角肌、中段 taper、肘端")
    fit(board, forearm_compare, (775, 905, 1495, 1565), "⑦ 前臂补前/补后：红色只应补在袖口衣身侧")
    fit(board, moved_hand, (1515, 905, 2235, 1565), "⑧ 移开手：腕根不是圆补丁，手掌整体参与")

    fit(board, contact, (35, 1605, 2365, 2045), "⑨ 41 帧 0→1→0 选帧：逐格看袖口、肘、腕是否开缝")
    draw.rounded_rectangle(
        (35, 2075, 2365, 2245),
        18,
        fill="white",
        outline=(175, 186, 203),
        width=2,
    )
    draw.text(
        (65, 2098),
        "需要你批准：②默认是否自然；⑤袖口/肘是否像真实手臂；⑦前臂 taper；⑧腕根与手掌；⑨运动中是否断裂。",
        fill=(118, 46, 22),
        font=font(24, True),
    )
    draw.text(
        (65, 2150),
        "最早失败点规则：从袖口开始，依次检查肘、腕、手轮廓；任一处失败即停在阶段 A。",
        fill=(52, 64, 82),
        font=font(23),
    )
    board.save(ROOT / "qa/V31-阶段A-大臂前臂手-中文视觉审查板.png")

    artifacts = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and path.name != "artifact-manifest.json":
            artifacts.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256(path),
                }
            )
    save_json(
        ROOT / "audit/artifact-manifest.json",
        {
            "schemaVersion": 1,
            "status": "candidate_not_frozen",
            "artifacts": artifacts,
        },
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
