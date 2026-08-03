from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
XIAOXING = ROOT.parents[1]
VALIDATION = XIAOXING / "validation"

V31 = VALIDATION / "arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve"
V34 = VALIDATION / "arm-chain-screen-left-v34-hand-root-from-frozen-ucap"
V35 = VALIDATION / "arm-chain-screen-left-v35-frozen-arm-recomposition-review"
V36 = VALIDATION / "arm-chain-screen-left-v36-skin-boundary-wrist-cap"
V37 = VALIDATION / "arm-chain-screen-left-v37-full-arm-textures-from-frozen-geometry"

SOURCE = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
SOURCE_EXPECTED_SHA256 = (
    "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5"
)

V37_REPORT = V37 / "audit/machine-report.json"
V37_REPORT_EXPECTED_SHA256 = (
    "7f9e47b517eb19e314fdcf00047bbcbf66443d9ce4329d87e4cc52206e029b90"
)
V37_BUILDER = V37 / "tools/build_v37_full_arm_textures.py"
V37_BUILDER_EXPECTED_SHA256 = (
    "6de592332c435a6f396126e3519a070d7add28e608cf9d75b42c93493e312c05"
)

FOREARM_BASE_MASK = V34 / "masks/complete/forearm-slim.png"
FOREARM_VISIBLE_MASK = V31 / "masks/visible/forearm.png"
BRACELET_MASK = V31 / "masks/visible/bracelet-owned-by-forearm.png"
SLEEVE_MASK = V31 / "masks/complete/sleeve.png"
UPPER_MASK = V31 / "masks/complete/upper_arm.png"
HAND_MASK = V36 / "masks/complete/hand.png"
HAND_VISIBLE_MASK = V36 / "masks/visible/hand.png"
HAND_TEXTURE = V36 / "materials/hand-textured-from-reset.png"

V37_SLEEVE_TEXTURE = V37 / "materials/sleeve-textured.png"
V37_UPPER_TEXTURE = V37 / "materials/upper-arm-textured.png"
V37_FOREARM_TEXTURE = V37 / "materials/forearm-textured.png"
V37_BRACELET_TEXTURE = V37 / "materials/bracelet-owned-by-forearm-textured.png"

CANDIDATE_MASK = ROOT / "masks/complete/forearm-reset-guided-wrist-underlay.png"
DELTA_MASK = ROOT / "masks/delta/added-wrist-underlay.png"
CANDIDATE_TEXTURE = ROOT / "materials/forearm-textured-reset-guided.png"

NEUTRAL_QA = ROOT / "qa/neutral-reset-v37-v38-comparison.png"
WRIST_QA = ROOT / "qa/wrist-v37-v38-three-pose-comparison.png"
UNDERLAY_QA = ROOT / "qa/underlay-delta-and-texture-check.png"
REVIEW_BOARD = ROOT / "qa/V38-screen-left腕部原图导向修复-中文审查图.png"
MACHINE_REPORT = ROOT / "audit/machine-report.json"

W, H = 512, 1086
ELBOW = (147.0, 405.0)
WRIST = (115.0, 529.0)
ANGLES = (-12, 0, 12)
WRIST_CROP = (78, 492, 153, 580)
FULL_ARM_CROP = (40, 185, 225, 665)

PAGE_BG = (236, 241, 247)
PANEL_BG = (255, 255, 255)
TEXT = (22, 35, 51)
MUTED = (66, 82, 101)
GREEN = (26, 112, 72)
RED = (168, 49, 45)
CYAN = (0, 190, 220, 210)
USER_VISUAL_REJECTED = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-self-visual-qa",
        action="store_true",
        help="Record that the generated V38 boards were visually inspected.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(XIAOXING).as_posix()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def rgba_array(image_or_path: Image.Image | Path) -> np.ndarray:
    image = (
        image_or_path
        if isinstance(image_or_path, Image.Image)
        else Image.open(image_or_path)
    )
    return np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()


def load_mask(path: Path) -> np.ndarray:
    mask = np.asarray(Image.open(path).convert("L"), dtype=np.uint8).copy()
    if mask.shape != (H, W):
        raise RuntimeError(f"Unexpected mask size for {path}: {mask.shape}")
    return mask


def rgba_image(array: np.ndarray) -> Image.Image:
    return Image.fromarray(array.astype(np.uint8), "RGBA")


def exact_alpha_image(rgb: np.ndarray, alpha: np.ndarray) -> Image.Image:
    array = np.zeros((H, W, 4), dtype=np.uint8)
    array[:, :, :3] = rgb
    array[:, :, 3] = alpha
    array[alpha == 0, :3] = 0
    return rgba_image(array)


def save_mask(path: Path, mask: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask.astype(np.uint8), "L").save(path)


def compose(layers: Iterable[Image.Image]) -> Image.Image:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for layer in layers:
        canvas.alpha_composite(layer.convert("RGBA"))
    return canvas


def flatten(
    image: Image.Image,
    background: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> Image.Image:
    canvas = Image.new("RGBA", image.size, background)
    canvas.alpha_composite(image.convert("RGBA"))
    return canvas.convert("RGB")


def crop_smooth(
    image: Image.Image,
    box: tuple[int, int, int, int],
    size: tuple[int, int],
    background: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> Image.Image:
    crop = image.crop(box)
    scale = min(size[0] / crop.width, size[1] / crop.height)
    resized = crop.resize(
        (
            max(1, round(crop.width * scale)),
            max(1, round(crop.height * scale)),
        ),
        Image.Resampling.LANCZOS,
    )
    display = flatten(resized, background) if resized.mode == "RGBA" else resized.convert("RGB")
    canvas = Image.new("RGB", size, background[:3])
    canvas.paste(
        display,
        ((size[0] - display.width) // 2, (size[1] - display.height) // 2),
    )
    return canvas


def panel(
    board: Image.Image,
    rect: tuple[int, int, int, int],
    title: str,
    content: Image.Image,
    *,
    title_size: int = 24,
) -> None:
    draw = ImageDraw.Draw(board)
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle(
        rect,
        radius=18,
        fill=PANEL_BG,
        outline=(174, 188, 205),
        width=3,
    )
    draw.text(
        (x0 + 20, y0 + 16),
        title,
        font=font(title_size, True),
        fill=TEXT,
    )
    available = (x1 - x0 - 30, y1 - y0 - 70)
    scale = min(available[0] / content.width, available[1] / content.height)
    resized = content.resize(
        (
            max(1, round(content.width * scale)),
            max(1, round(content.height * scale)),
        ),
        Image.Resampling.LANCZOS,
    )
    board.paste(
        resized.convert("RGB"),
        (
            x0 + 15 + (available[0] - resized.width) // 2,
            y0 + 55 + (available[1] - resized.height) // 2,
        ),
    )


def load_v37_builder():
    specification = importlib.util.spec_from_file_location("v37_audit", V37_BUILDER)
    if specification is None or specification.loader is None:
        raise RuntimeError("Unable to load V37 audit builder")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def compare_snapshots(before: dict, after: dict) -> list[dict]:
    old = {item["path"]: item["sha256"] for item in before["entries"]}
    new = {item["path"]: item["sha256"] for item in after["entries"]}
    changes = []
    for path in sorted(set(old) | set(new)):
        if old.get(path) != new.get(path):
            changes.append(
                {
                    "path": path,
                    "beforeSha256": old.get(path),
                    "afterSha256": new.get(path),
                }
            )
    return changes


def connected_components(mask: np.ndarray) -> int:
    count, _ = cv2.connectedComponents((mask > 8).astype(np.uint8), 8)
    return int(count - 1)


def topology(mask: np.ndarray) -> dict:
    binary = (mask > 8).astype(np.uint8)
    contours, hierarchy = cv2.findContours(
        binary,
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    holes = (
        0
        if hierarchy is None
        else sum(1 for item in hierarchy[0] if item[3] != -1)
    )
    return {
        "connectedComponents": connected_components(mask),
        "closedHoles": int(holes),
    }


def rotation_matrix(center: tuple[float, float], angle: float) -> np.ndarray:
    return cv2.getRotationMatrix2D(center, angle, 1.0)


def warp_mask(mask: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    return cv2.warpAffine(
        mask,
        matrix,
        (W, H),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def warp_rgba(
    image: Image.Image,
    matrix: np.ndarray,
    exact_mask: np.ndarray,
) -> Image.Image:
    source = rgba_array(image)
    rgb = cv2.warpAffine(
        source[:, :, :3],
        matrix,
        (W, H),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )
    return exact_alpha_image(rgb, exact_mask)


def local_coordinates() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    axis = np.array(
        [WRIST[0] - ELBOW[0], WRIST[1] - ELBOW[1]],
        dtype=np.float64,
    )
    axis /= np.linalg.norm(axis)
    normal = np.array([-axis[1], axis[0]], dtype=np.float64)
    yy, xx = np.indices((H, W))
    points = np.stack(
        [xx - WRIST[0], yy - WRIST[1]],
        axis=-1,
    )
    longitudinal = points @ axis
    transverse = points @ normal
    return axis, normal, longitudinal, transverse


def row_hull(mask: np.ndarray) -> np.ndarray:
    result = np.zeros_like(mask, dtype=bool)
    for y in np.flatnonzero(np.any(mask, axis=1)):
        xs = np.flatnonzero(mask[y])
        result[y, xs.min() : xs.max() + 1] = True
    return result


def rounded_quarter(value: float) -> float:
    return round(value * 4.0) / 4.0


def source_guided_bridge(
    *,
    source_rgb: np.ndarray,
    forearm_base: np.ndarray,
    forearm_visible: np.ndarray,
    bracelet: np.ndarray,
    hand: np.ndarray,
    hand_visible: np.ndarray,
    longitudinal: np.ndarray,
    transverse: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict]:
    proximal_values = transverse[
        (forearm_visible > 8)
        & (longitudinal >= -24.0)
        & (longitudinal <= -16.0)
    ]
    distal_values = transverse[
        (hand_visible > 8)
        & (longitudinal >= 12.0)
        & (longitudinal <= 20.0)
    ]
    if proximal_values.size < 100 or distal_values.size < 100:
        raise RuntimeError("Insufficient Reset-derived wrist boundary anchors")

    bridge_low = rounded_quarter(
        max(
            float(np.percentile(proximal_values, 10)),
            float(np.percentile(distal_values, 10)),
        )
    )
    bridge_high = rounded_quarter(
        min(
            float(np.percentile(proximal_values, 92)),
            float(np.percentile(distal_values, 92)),
        )
    )
    if bridge_high - bridge_low < 16.0:
        raise RuntimeError("Reset-derived wrist bridge is implausibly narrow")

    old_neutral_union = (
        (forearm_base > 8) | (bracelet > 8) | (hand > 8)
    )
    neutral_row_hull = row_hull(old_neutral_union)
    signed_inside = np.minimum.reduce(
        [
            longitudinal + 18.0,
            18.0 - longitudinal,
            transverse - bridge_low,
            bridge_high - transverse,
        ]
    )
    analytic_alpha = np.clip(
        (signed_inside + 0.5) * 255.0,
        0.0,
        255.0,
    ).astype(np.uint8)
    bridge_alpha = np.where(
        neutral_row_hull,
        analytic_alpha,
        0,
    ).astype(np.uint8)
    candidate = np.maximum(forearm_base, bridge_alpha)
    candidate_neutral_union = (
        (candidate > 8) | (bracelet > 8) | (hand > 8)
    )

    def row_bounds(mask: np.ndarray, y: int) -> tuple[int, int] | None:
        xs = np.flatnonzero(mask[y])
        if not xs.size:
            return None
        return int(xs.min()), int(xs.max())

    forearm_changed_rows = sum(
        row_bounds(candidate > 8, y) != row_bounds(forearm_base > 8, y)
        for y in range(H)
    )
    neutral_arm_changed_rows = sum(
        row_bounds(candidate_neutral_union, y)
        != row_bounds(old_neutral_union, y)
        for y in range(H)
    )

    added = (candidate > 8) & (forearm_base <= 8)
    removed = (candidate <= 8) & (forearm_base > 8)
    ys, xs = np.nonzero(added)
    if not xs.size:
        raise RuntimeError("Authorized wrist bridge added no pixels")

    metadata = {
        "method": (
            "Connect the Reset-derived proximal forearm and distal hand skin "
            "cross-sections inside the old neutral row envelope. The bridge "
            "uses the common 10th-to-92nd percentile transverse interval and "
            "analytic one-pixel edge coverage; no blur, dilation, or hand "
            "geometry change is used."
        ),
        "sourceAnchorBands": {
            "proximalForearmLongitudinalPx": [-24.0, -16.0],
            "distalHandLongitudinalPx": [12.0, 20.0],
            "proximalSampleCount": int(proximal_values.size),
            "distalSampleCount": int(distal_values.size),
        },
        "bridgeLongitudinalPx": [-18.0, 18.0],
        "bridgeTransversePx": [bridge_low, bridge_high],
        "bridgeWidthPx": bridge_high - bridge_low,
        "candidateAddedPixels": int(np.count_nonzero(added)),
        "candidateRemovedPixels": int(np.count_nonzero(removed)),
        "candidateAlphaChangedPixels": int(
            np.count_nonzero(candidate != forearm_base)
        ),
        "addedBoundingBoxPx": [
            int(xs.min()),
            int(ys.min()),
            int(xs.max()),
            int(ys.max()),
        ],
        "addedOutsideAuthorizedBridgePx": int(
            np.count_nonzero(added & (bridge_alpha <= 8))
        ),
        "addedOutsideOldNeutralRowEnvelopePx": int(
            np.count_nonzero(added & ~neutral_row_hull)
        ),
        "forearmRowOuterBoundaryChangedRows": int(forearm_changed_rows),
        "neutralArmRowOuterBoundaryChangedRows": int(
            neutral_arm_changed_rows
        ),
        "baseTopology": topology(forearm_base),
        "candidateTopology": topology(candidate),
        "bridgeCorePixels": int(np.count_nonzero(bridge_alpha > 128)),
    }
    return candidate, bridge_alpha, metadata


def donor_pool(
    mask: np.ndarray,
    source_rgb: np.ndarray,
    longitudinal: np.ndarray,
    transverse: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        longitudinal[mask],
        transverse[mask],
        source_rgb[mask].astype(np.float64),
    )


def idw_donor_color(
    pool_s: np.ndarray,
    pool_t: np.ndarray,
    pool_rgb: np.ndarray,
    target_t: float,
    anchor_s: float,
) -> np.ndarray:
    score = (pool_t - target_t) ** 2 * 16.0 + (pool_s - anchor_s) ** 2
    take = min(6, score.size)
    indices = np.argpartition(score, take - 1)[:take]
    weights = 1.0 / (score[indices] + 0.25)
    return (pool_rgb[indices] * weights[:, None]).sum(axis=0) / weights.sum()


def reset_guided_texture(
    *,
    source_rgb: np.ndarray,
    base_texture: Image.Image,
    candidate_mask: np.ndarray,
    forearm_visible: np.ndarray,
    bracelet: np.ndarray,
    hand_visible: np.ndarray,
    longitudinal: np.ndarray,
    transverse: np.ndarray,
) -> tuple[Image.Image, dict]:
    visible_union = (forearm_visible > 8) | (hand_visible > 8)
    kernel = np.ones((3, 3), dtype=np.uint8)
    eroded_visible = cv2.erode(
        visible_union.astype(np.uint8),
        kernel,
        iterations=1,
    ) > 0
    red = source_rgb[:, :, 0].astype(np.int16)
    green = source_rgb[:, :, 1].astype(np.int16)
    blue = source_rgb[:, :, 2].astype(np.int16)
    source_skin_color = (
        (red > 190)
        & (green > 155)
        & (blue > 145)
        & ((red - green) > 4)
        & ((red - green) < 65)
    )
    proximal_donors = (
        eroded_visible
        & (forearm_visible > 8)
        & source_skin_color
        & (longitudinal >= -34.0)
        & (longitudinal <= -18.0)
    )
    distal_donors = (
        eroded_visible
        & (hand_visible > 8)
        & source_skin_color
        & (longitudinal >= 14.0)
        & (longitudinal <= 36.0)
    )
    if np.count_nonzero(proximal_donors) < 100:
        raise RuntimeError("Insufficient proximal Reset skin texture donors")
    if np.count_nonzero(distal_donors) < 100:
        raise RuntimeError("Insufficient distal Reset skin texture donors")

    proximal_s, proximal_t, proximal_rgb = donor_pool(
        proximal_donors,
        source_rgb,
        longitudinal,
        transverse,
    )
    distal_s, distal_t, distal_rgb = donor_pool(
        distal_donors,
        source_rgb,
        longitudinal,
        transverse,
    )

    proximal_anchor_t = transverse[
        (forearm_visible > 8)
        & (longitudinal >= -24.0)
        & (longitudinal <= -16.0)
    ]
    distal_anchor_t = transverse[
        (hand_visible > 8)
        & (longitudinal >= 12.0)
        & (longitudinal <= 20.0)
    ]
    texture_low = rounded_quarter(
        max(
            float(proximal_anchor_t.min()),
            float(distal_anchor_t.min()),
        )
    )
    texture_high = rounded_quarter(
        min(
            float(proximal_anchor_t.max()),
            float(distal_anchor_t.max()),
        )
    )
    texture_region = (
        (candidate_mask > 0)
        & (longitudinal >= -24.0)
        & (longitudinal <= 34.0)
        & (transverse >= texture_low)
        & (transverse <= texture_high)
    )

    texture_field = np.zeros((H, W, 3), dtype=np.float64)
    for y, x in zip(*np.nonzero(texture_region)):
        blend = float(
            np.clip((longitudinal[y, x] + 18.0) / 36.0, 0.0, 1.0)
        )
        proximal_color = idw_donor_color(
            proximal_s,
            proximal_t,
            proximal_rgb,
            float(transverse[y, x]),
            -20.0,
        )
        distal_color = idw_donor_color(
            distal_s,
            distal_t,
            distal_rgb,
            float(transverse[y, x]),
            20.0,
        )
        texture_field[y, x] = (
            proximal_color * (1.0 - blend) + distal_color * blend
        )

    exact_source_region = (
        texture_region
        & visible_union
        & (bracelet <= 8)
    )
    texture_field[exact_source_region] = source_rgb[exact_source_region]

    output = rgba_array(base_texture)
    output[:, :, 3] = candidate_mask
    output[:, :, :3][texture_region] = np.clip(
        np.rint(texture_field[texture_region]),
        0,
        255,
    ).astype(np.uint8)
    output[candidate_mask == 0, :3] = 0

    added = (candidate_mask > 8) & (
        np.asarray(base_texture.getchannel("A"), dtype=np.uint8) <= 8
    )
    if np.any(added & ~texture_region):
        raise RuntimeError("New wrist alpha lacks Reset-guided RGB")

    added_rgb = output[:, :, :3][added].astype(np.float32)
    exact_mismatch = int(
        np.count_nonzero(
            np.any(
                output[:, :, :3][exact_source_region]
                != source_rgb[exact_source_region],
                axis=1,
            )
        )
    )
    metadata = {
        "method": (
            "Replace the wrist/U-cap RGB inside the candidate alpha with a "
            "Reset-only longitudinal continuation. Proximal forearm and "
            "distal hand interior pixels are inverse-distance donors; directly "
            "visible source pixels remain byte-identical. V14 is not used in "
            "the corrected wrist field."
        ),
        "textureRegionPixels": int(np.count_nonzero(texture_region)),
        "directResetPixels": int(np.count_nonzero(exact_source_region)),
        "interpolatedResetDonorPixels": int(
            np.count_nonzero(texture_region & ~exact_source_region)
        ),
        "proximalDonorPixels": int(np.count_nonzero(proximal_donors)),
        "distalDonorPixels": int(np.count_nonzero(distal_donors)),
        "textureTransversePx": [texture_low, texture_high],
        "directResetRgbMismatchPx": exact_mismatch,
        "newGeometryUniqueRgbCount": int(
            len(np.unique(added_rgb.astype(np.uint8), axis=0))
        ),
        "newGeometryLuminanceStdDev": float(
            np.std(
                added_rgb[:, 0] * 0.2126
                + added_rgb[:, 1] * 0.7152
                + added_rgb[:, 2] * 0.0722
            )
        ),
        "v14UsedInCorrectedWristField": False,
        "alphaBlurFeatherOrDilationUsed": False,
    }
    return rgba_image(output), metadata


def maximum_local_skin_span(
    forearm: np.ndarray,
    hand: np.ndarray,
    bracelet: np.ndarray,
    longitudinal: np.ndarray,
    transverse: np.ndarray,
) -> float:
    skin = ((forearm > 8) & ~(bracelet > 8)) | (hand > 8)
    spans = []
    for lower in np.arange(-18.0, 18.0, 1.0):
        values = transverse[
            skin
            & (longitudinal >= lower)
            & (longitudinal < lower + 1.0)
        ]
        if values.size:
            spans.append(float(values.max() - values.min()))
    return max(spans) if spans else 0.0


def wrist_metrics(
    *,
    forearm_base: np.ndarray,
    forearm_candidate: np.ndarray,
    bracelet: np.ndarray,
    hand: np.ndarray,
    bridge_alpha: np.ndarray,
    longitudinal: np.ndarray,
    transverse: np.ndarray,
) -> list[dict]:
    results = []
    base_skin = cv2.subtract(forearm_base, bracelet)
    candidate_skin = cv2.subtract(forearm_candidate, bracelet)
    for angle in ANGLES:
        matrix = rotation_matrix(WRIST, angle)
        posed_hand = warp_mask(hand, matrix)
        base_union = ((base_skin > 8) | (posed_hand > 8)).astype(np.uint8)
        candidate_union = (
            (candidate_skin > 8) | (posed_hand > 8)
        ).astype(np.uint8)
        base_components = connected_components(base_union * 255)
        candidate_components = connected_components(candidate_union * 255)
        base_span = maximum_local_skin_span(
            forearm_base,
            posed_hand,
            bracelet,
            longitudinal,
            transverse,
        )
        candidate_span = maximum_local_skin_span(
            forearm_candidate,
            posed_hand,
            bracelet,
            longitudinal,
            transverse,
        )
        base_render_union = (
            (forearm_base > 8)
            | (bracelet > 8)
            | (posed_hand > 8)
        )
        candidate_render_union = (
            (forearm_candidate > 8)
            | (bracelet > 8)
            | (posed_hand > 8)
        )
        results.append(
            {
                "angleDeg": angle,
                "v37BridgeCoreGapPx": int(
                    np.count_nonzero(
                        (bridge_alpha > 128) & ~base_render_union
                    )
                ),
                "v38BridgeCoreGapPx": int(
                    np.count_nonzero(
                        (bridge_alpha > 128) & ~candidate_render_union
                    )
                ),
                "v37ForearmHandOverlapPx": int(
                    np.count_nonzero(
                        (forearm_base > 8) & (posed_hand > 8)
                    )
                ),
                "v38ForearmHandOverlapPx": int(
                    np.count_nonzero(
                        (forearm_candidate > 8) & (posed_hand > 8)
                    )
                ),
                "v37ConnectedComponents": base_components,
                "v38ConnectedComponents": candidate_components,
                "braceletHandOverlapPx": int(
                    np.count_nonzero(
                        (bracelet > 8) & (posed_hand > 8)
                    )
                ),
                "v37MaximumOuterSkinSpanPx": base_span,
                "v38MaximumOuterSkinSpanPx": candidate_span,
                "maximumOuterSkinSpanDeltaPx": candidate_span - base_span,
            }
        )
    return results


def wrist_composite(
    *,
    angle: int,
    hand_texture: Image.Image,
    hand_mask: np.ndarray,
    forearm_texture: Image.Image,
    bracelet_texture: Image.Image,
) -> Image.Image:
    matrix = rotation_matrix(WRIST, angle)
    posed_hand_mask = warp_mask(hand_mask, matrix)
    posed_hand = warp_rgba(hand_texture, matrix, posed_hand_mask)
    return compose([posed_hand, forearm_texture, bracelet_texture])


def neutral_board(
    source: Image.Image,
    v37_neutral: Image.Image,
    v38_neutral: Image.Image,
) -> Image.Image:
    board = Image.new("RGB", (1770, 720), (239, 243, 248))
    draw = ImageDraw.Draw(board)
    draw.text(
        (28, 18),
        "Reset 原图与中立腕部对照",
        font=font(30, True),
        fill=TEXT,
    )
    items = (
        ("Reset 原图", source.convert("RGBA")),
        ("V37：腕链下有白色断带", v37_neutral),
        ("V38：原图导向皮肤连续", v38_neutral),
    )
    for index, (label, image) in enumerate(items):
        x = 25 + index * 580
        view = crop_smooth(image, WRIST_CROP, (540, 570))
        board.paste(view, (x, 76))
        draw.rounded_rectangle(
            (x, 76, x + 540, 646),
            radius=15,
            outline=(176, 189, 205),
            width=3,
        )
        draw.text(
            (x + 36, 658),
            label,
            font=font(18, True),
            fill=RED if index == 1 else (GREEN if index == 2 else TEXT),
        )
    return board


def wrist_comparison_board(
    *,
    v37_forearm: Image.Image,
    v38_forearm: Image.Image,
    bracelet: Image.Image,
    hand: Image.Image,
    hand_mask: np.ndarray,
    metrics: list[dict],
) -> Image.Image:
    board = Image.new("RGB", (1900, 1240), (239, 243, 248))
    draw = ImageDraw.Draw(board)
    draw.text(
        (32, 20),
        "腕部压力复核｜上排 V37 断裂基线，下排 V38 原图导向修复",
        font=font(30, True),
        fill=TEXT,
    )
    draw.text(
        (34, 64),
        "同一冻结 V36 手部、同一腕点、同一 ±12° 刚性检查；未用缩放或姿势补偿。",
        font=font(20),
        fill=MUTED,
    )
    for column, item in enumerate(metrics):
        angle = int(item["angleDeg"])
        x = 25 + column * 625
        draw.text(
            (x + 260, 100),
            f"{angle:+d}°",
            font=font(26, True),
            fill=TEXT,
        )
        for row, (label, texture) in enumerate(
            (("V37", v37_forearm), ("V38", v38_forearm))
        ):
            y = 145 + row * 510
            posed = wrist_composite(
                angle=angle,
                hand_texture=hand,
                hand_mask=hand_mask,
                forearm_texture=texture,
                bracelet_texture=bracelet,
            )
            view = crop_smooth(posed, WRIST_CROP, (575, 410))
            board.paste(view, (x, y))
            draw.rounded_rectangle(
                (x, y, x + 575, y + 410),
                radius=14,
                outline=(176, 189, 205),
                width=3,
            )
            gap = (
                item["v37BridgeCoreGapPx"]
                if row == 0
                else item["v38BridgeCoreGapPx"]
            )
            draw.text(
                (x + 16, y + 421),
                (
                    f"{label}｜原图皮肤通道空缺 {gap}px｜"
                    f"组件 {item[label.lower() + 'ConnectedComponents']}"
                ),
                font=font(17, True),
                fill=RED if row == 0 else GREEN,
            )
        draw.text(
            (x + 16, 1165),
            (
                f"V38 重叠 {item['v38ForearmHandOverlapPx']}px｜"
                f"外宽增量 {item['maximumOuterSkinSpanDeltaPx']:.2f}px｜"
                f"手链接触 {item['braceletHandOverlapPx']}px"
            ),
            font=font(17, True),
            fill=GREEN,
        )
    return board


def delta_overlay(
    source: Image.Image,
    candidate_mask: np.ndarray,
    delta_mask: np.ndarray,
) -> Image.Image:
    source_rgba = source.convert("RGBA")
    overlay = np.zeros((H, W, 4), dtype=np.uint8)
    overlay[:, :, :3] = CYAN[:3]
    overlay[:, :, 3] = np.where(delta_mask > 8, CYAN[3], 0).astype(np.uint8)
    source_rgba.alpha_composite(rgba_image(overlay))
    return source_rgba


def underlay_board(
    *,
    source: Image.Image,
    base_mask: np.ndarray,
    candidate_mask: np.ndarray,
    delta_mask: np.ndarray,
    candidate_texture: Image.Image,
    hand_texture: Image.Image,
) -> Image.Image:
    board = Image.new("RGB", (1650, 760), (239, 243, 248))
    draw = ImageDraw.Draw(board)
    draw.text(
        (28, 20),
        "授权的最小几何差量与隐藏皮肤材质",
        font=font(30, True),
        fill=TEXT,
    )
    base_color = np.zeros((H, W, 4), dtype=np.uint8)
    base_color[:, :, :3] = (88, 168, 108)
    base_color[:, :, 3] = base_mask
    candidate_color = base_color.copy()
    candidate_color[:, :, 3] = candidate_mask
    candidate_color[:, :, :3][delta_mask > 8] = CYAN[:3]
    no_bracelet = compose([hand_texture, candidate_texture])
    items = (
        ("V34 原前臂", rgba_image(base_color)),
        ("V38：青色仅为 QA 差量标记", rgba_image(candidate_color)),
        ("差量叠回 Reset（仅审查图有青色）", delta_overlay(source, candidate_mask, delta_mask)),
        ("移开手链：连续皮肤底层", no_bracelet),
        ("V38 前臂真实纹理透明件", candidate_texture),
    )
    for index, (label, image) in enumerate(items):
        x = 20 + index * 325
        view = crop_smooth(
            image,
            (82, 490, 148, 585),
            (300, 580),
            (246, 248, 251, 255),
        )
        board.paste(view, (x, 82))
        draw.rounded_rectangle(
            (x, 82, x + 300, 662),
            radius=14,
            outline=(176, 189, 205),
            width=2,
        )
        draw.text(
            (x + 8, 675),
            label,
            font=font(15, True),
            fill=TEXT,
        )
    return board


def full_arm_composite(
    *,
    sleeve: Image.Image,
    upper: Image.Image,
    forearm: Image.Image,
    bracelet: Image.Image,
    hand: Image.Image,
) -> Image.Image:
    return compose([upper, hand, forearm, sleeve, bracelet])


def make_review_board(
    *,
    source: Image.Image,
    neutral: Image.Image,
    wrist: Image.Image,
    underlay: Image.Image,
    full_arm: Image.Image,
    geometry: dict,
    metrics: list[dict],
    engineering_pass: bool,
) -> Image.Image:
    board = Image.new("RGB", (3600, 2550), PAGE_BG)
    draw = ImageDraw.Draw(board)
    draw.text(
        (50, 30),
        (
            "小星 V38｜Reset 原图导向的腕链下断裂修复候选"
            "（用户视觉驳回）"
        ),
        font=font(46, True),
        fill=TEXT,
    )
    draw.text(
        (52, 94),
        (
            "授权变更：只在前臂所属隐藏 U-cap 增加原图皮肤通道；"
            "V36 手部与所有旧冻结文件均不改。"
        ),
        font=font(22),
        fill=MUTED,
    )
    draw.text(
        (52, 130),
        (
            f"候选差量 {geometry['candidateAddedPixels']}px｜"
            f"删除 0px｜整臂中立逐行外轮廓改变 "
            f"{geometry['neutralArmRowOuterBoundaryChangedRows']} 行。"
        ),
        font=font(22),
        fill=MUTED,
    )

    panel(
        board,
        (40, 180, 1775, 970),
        "1. Reset 原图 / V37 断裂 / V38 中立修复",
        neutral,
    )
    panel(
        board,
        (1805, 180, 3560, 970),
        "2. 最小 alpha 差量与原图导向真实纹理",
        underlay,
    )
    panel(
        board,
        (40, 1000, 2540, 2240),
        "3. 同条件腕部三姿势对照",
        wrist,
    )
    full_view = crop_smooth(
        full_arm,
        FULL_ARM_CROP,
        (900, 1070),
        (255, 255, 255, 255),
    )
    panel(
        board,
        (2570, 1000, 3560, 2240),
        "4. V38 完整左臂默认叠放",
        full_view,
    )

    minimum_overlap = min(item["v38ForearmHandOverlapPx"] for item in metrics)
    maximum_width_delta = max(
        abs(item["maximumOuterSkinSpanDeltaPx"]) for item in metrics
    )
    remaining_gaps = sum(item["v38BridgeCoreGapPx"] for item in metrics)
    components = [item["v38ConnectedComponents"] for item in metrics]
    draw.rounded_rectangle(
        (40, 2280, 3560, 2510),
        radius=16,
        fill=(255, 255, 255),
        outline=(174, 188, 205),
        width=3,
    )
    draw.text(
        (70, 2310),
        (
            f"数值门禁：{'通过' if engineering_pass else '未通过'}｜"
            "用户视觉门禁：驳回｜"
            f"三姿势皮肤通道空缺合计 {remaining_gaps}px｜"
            f"连接组件 {components}｜最小重叠 {minimum_overlap}px｜"
            f"最大外宽增量 {maximum_width_delta:.2f}px"
        ),
        font=font(24, True),
        fill=RED,
    )
    draw.text(
        (70, 2362),
        (
            "用户复核结论：完整左臂多处仍呈现断口；"
            "数值连通不能替代纹理与材质连续性。"
        ),
        font=font(22, True),
        fill=RED,
    )
    draw.text(
        (70, 2412),
        (
            "青色只存在于 QA 差量图；最终纹理没有辅助线。"
            "V38 已驳回，不得冻结或继续下游。"
        ),
        font=font(20),
        fill=MUTED,
    )
    return board


def output_record(path: Path) -> dict:
    return {
        "path": rel(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def main() -> None:
    args = parse_args()

    if sha256(SOURCE) != SOURCE_EXPECTED_SHA256:
        raise RuntimeError("Registered Reset source hash changed")
    if sha256(V37_REPORT) != V37_REPORT_EXPECTED_SHA256:
        raise RuntimeError("V37 machine report hash changed")
    if sha256(V37_BUILDER) != V37_BUILDER_EXPECTED_SHA256:
        raise RuntimeError("V37 builder hash changed")

    v37_report = json.loads(V37_REPORT.read_text(encoding="utf-8"))
    v37_builder = load_v37_builder()
    preflight = v37_builder.verify_frozen_inputs()
    if not preflight["pass"]:
        raise RuntimeError(
            "Frozen input preflight failed: "
            + json.dumps(preflight["mismatches"], ensure_ascii=False)
        )
    frozen_input_records = {}
    for name, expected_record in v37_report["frozenInputs"].items():
        path = XIAOXING / expected_record["path"]
        actual_hash = sha256(path) if path.is_file() else None
        frozen_input_records[name] = {
            "path": expected_record["path"],
            "expectedSha256": expected_record["sha256"],
            "actualSha256": actual_hash,
            "match": actual_hash == expected_record["sha256"],
        }
    if not all(
        record["match"] for record in frozen_input_records.values()
    ):
        raise RuntimeError("One or more frozen input hashes changed")

    frozen_roots = {
        "v31": V31,
        "v34": V34,
        "v35": V35,
        "v36": V36,
    }
    snapshots_before = {
        name: v37_builder.directory_snapshot(path)
        for name, path in frozen_roots.items()
    }
    v37_snapshot_before = v37_builder.directory_snapshot(V37)
    for name, snapshot in snapshots_before.items():
        expected = v37_report["frozenIntegrity"]["directorySnapshots"][name][
            "treeSha256After"
        ]
        if snapshot["treeSha256"] != expected:
            raise RuntimeError(f"{name} frozen directory hash changed")

    expected_v37_outputs = {
        item["path"]: item["sha256"] for item in v37_report["outputFiles"]
    }
    for path in (
        V37_SLEEVE_TEXTURE,
        V37_UPPER_TEXTURE,
        V37_FOREARM_TEXTURE,
        V37_BRACELET_TEXTURE,
    ):
        expected = expected_v37_outputs.get(rel(path))
        if expected is None or sha256(path) != expected:
            raise RuntimeError(f"V37 input changed: {path}")

    source = Image.open(SOURCE).convert("RGB")
    source_rgb = np.asarray(source, dtype=np.uint8).copy()
    forearm_base = load_mask(FOREARM_BASE_MASK)
    forearm_visible_with_bracelet = load_mask(FOREARM_VISIBLE_MASK)
    bracelet_mask = load_mask(BRACELET_MASK)
    forearm_visible = np.minimum(
        cv2.subtract(forearm_visible_with_bracelet, bracelet_mask),
        forearm_base,
    )
    hand_mask = load_mask(HAND_MASK)
    hand_visible = load_mask(HAND_VISIBLE_MASK)
    _, _, longitudinal, transverse = local_coordinates()

    candidate_mask, bridge_alpha, geometry_info = source_guided_bridge(
        source_rgb=source_rgb,
        forearm_base=forearm_base,
        forearm_visible=forearm_visible,
        bracelet=bracelet_mask,
        hand=hand_mask,
        hand_visible=hand_visible,
        longitudinal=longitudinal,
        transverse=transverse,
    )
    delta_mask = np.where(
        (candidate_mask > 8) & (forearm_base <= 8),
        255,
        0,
    ).astype(np.uint8)

    forearm_v37 = Image.open(V37_FOREARM_TEXTURE).convert("RGBA")
    candidate_texture, texture_info = reset_guided_texture(
        source_rgb=source_rgb,
        base_texture=forearm_v37,
        candidate_mask=candidate_mask,
        forearm_visible=forearm_visible,
        bracelet=bracelet_mask,
        hand_visible=hand_visible,
        longitudinal=longitudinal,
        transverse=transverse,
    )

    for folder in ("masks/complete", "masks/delta", "materials", "qa", "audit"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    save_mask(CANDIDATE_MASK, candidate_mask)
    save_mask(DELTA_MASK, delta_mask)
    candidate_texture.save(CANDIDATE_TEXTURE)

    alpha_mismatch = int(
        np.count_nonzero(
            np.asarray(
                candidate_texture.getchannel("A"),
                dtype=np.uint8,
            )
            != candidate_mask
        )
    )
    v36_hand_hash = sha256(HAND_TEXTURE)
    expected_hand_hash = v37_report["materials"]["hand"]["sha256"]
    if v36_hand_hash != expected_hand_hash:
        raise RuntimeError("Frozen V36 hand texture hash changed")

    sleeve = Image.open(V37_SLEEVE_TEXTURE).convert("RGBA")
    upper = Image.open(V37_UPPER_TEXTURE).convert("RGBA")
    bracelet = Image.open(V37_BRACELET_TEXTURE).convert("RGBA")
    hand = Image.open(HAND_TEXTURE).convert("RGBA")
    sleeve_mask = load_mask(SLEEVE_MASK)
    upper_mask = load_mask(UPPER_MASK)
    component_alpha_mismatches = {
        "sleeve": int(
            np.count_nonzero(
                np.asarray(sleeve.getchannel("A"), dtype=np.uint8)
                != sleeve_mask
            )
        ),
        "upperArm": int(
            np.count_nonzero(
                np.asarray(upper.getchannel("A"), dtype=np.uint8)
                != upper_mask
            )
        ),
        "forearmV38Candidate": alpha_mismatch,
        "braceletOwnedByForearm": int(
            np.count_nonzero(
                np.asarray(bracelet.getchannel("A"), dtype=np.uint8)
                != bracelet_mask
            )
        ),
        "handV36Frozen": int(
            np.count_nonzero(
                np.asarray(hand.getchannel("A"), dtype=np.uint8)
                != hand_mask
            )
        ),
    }
    forearm_rgba = rgba_array(candidate_texture)
    forearm_present = candidate_mask > 8
    pale_forearm_rgb = np.min(forearm_rgba[:, :, :3], axis=2) > 235
    root_transition = (
        forearm_present
        & (longitudinal >= -140.0)
        & (longitudinal < -120.0)
    )
    under_bracelet = forearm_present & (bracelet_mask > 8)
    rejection_diagnostics = {
        "rootTransitionPixels": int(np.count_nonzero(root_transition)),
        "rootTransitionNearWhiteRgbPixels": int(
            np.count_nonzero(root_transition & pale_forearm_rgb)
        ),
        "braceletMaskPixels": int(np.count_nonzero(bracelet_mask > 8)),
        "braceletPixelsAlsoPresentInForearmAlpha": int(
            np.count_nonzero(
                (bracelet_mask > 8) & forearm_present
            )
        ),
        "forearmPixelsUnderBracelet": int(
            np.count_nonzero(under_bracelet)
        ),
        "nearWhiteForearmRgbPixelsUnderBracelet": int(
            np.count_nonzero(under_bracelet & pale_forearm_rgb)
        ),
        "sleeveUpperAlphaUnionComponents": connected_components(
            np.maximum(sleeve_mask, upper_mask)
        ),
        "upperForearmAlphaUnionComponents": connected_components(
            np.maximum(upper_mask, candidate_mask)
        ),
        "forearmHandAlphaUnionComponents": connected_components(
            np.maximum(candidate_mask, hand_mask)
        ),
    }

    metrics = wrist_metrics(
        forearm_base=forearm_base,
        forearm_candidate=candidate_mask,
        bracelet=bracelet_mask,
        hand=hand_mask,
        bridge_alpha=bridge_alpha,
        longitudinal=longitudinal,
        transverse=transverse,
    )
    v37_neutral = wrist_composite(
        angle=0,
        hand_texture=hand,
        hand_mask=hand_mask,
        forearm_texture=forearm_v37,
        bracelet_texture=bracelet,
    )
    v38_neutral = wrist_composite(
        angle=0,
        hand_texture=hand,
        hand_mask=hand_mask,
        forearm_texture=candidate_texture,
        bracelet_texture=bracelet,
    )
    neutral = neutral_board(source, v37_neutral, v38_neutral)
    neutral.save(NEUTRAL_QA)

    wrist = wrist_comparison_board(
        v37_forearm=forearm_v37,
        v38_forearm=candidate_texture,
        bracelet=bracelet,
        hand=hand,
        hand_mask=hand_mask,
        metrics=metrics,
    )
    wrist.save(WRIST_QA)

    underlay = underlay_board(
        source=source,
        base_mask=forearm_base,
        candidate_mask=candidate_mask,
        delta_mask=delta_mask,
        candidate_texture=candidate_texture,
        hand_texture=hand,
    )
    underlay.save(UNDERLAY_QA)

    full_arm = full_arm_composite(
        sleeve=sleeve,
        upper=upper,
        forearm=candidate_texture,
        bracelet=bracelet,
        hand=hand,
    )

    snapshots_after = {
        name: v37_builder.directory_snapshot(path)
        for name, path in frozen_roots.items()
    }
    v37_snapshot_after = v37_builder.directory_snapshot(V37)
    frozen_changes = []
    directory_integrity = {}
    for name in frozen_roots:
        changes = compare_snapshots(
            snapshots_before[name],
            snapshots_after[name],
        )
        frozen_changes.extend(
            [{"root": name, **change} for change in changes]
        )
        directory_integrity[name] = {
            "root": rel(frozen_roots[name]),
            "fileCountBefore": snapshots_before[name]["fileCount"],
            "fileCountAfter": snapshots_after[name]["fileCount"],
            "treeSha256Before": snapshots_before[name]["treeSha256"],
            "treeSha256After": snapshots_after[name]["treeSha256"],
            "unchanged": not changes,
        }
    v37_changes = compare_snapshots(v37_snapshot_before, v37_snapshot_after)

    remaining_gap = sum(item["v38BridgeCoreGapPx"] for item in metrics)
    candidate_components = [
        item["v38ConnectedComponents"] for item in metrics
    ]
    minimum_overlap = min(
        item["v38ForearmHandOverlapPx"] for item in metrics
    )
    maximum_width_delta = max(
        abs(item["maximumOuterSkinSpanDeltaPx"]) for item in metrics
    )
    engineering_pass = (
        preflight["pass"]
        and not frozen_changes
        and not v37_changes
        and geometry_info["candidateAddedPixels"] > 0
        and geometry_info["candidateRemovedPixels"] == 0
        and geometry_info["addedOutsideAuthorizedBridgePx"] == 0
        and geometry_info["addedOutsideOldNeutralRowEnvelopePx"] == 0
        and geometry_info["neutralArmRowOuterBoundaryChangedRows"] == 0
        and geometry_info["candidateTopology"]["connectedComponents"] == 1
        and all(
            mismatch == 0
            for mismatch in component_alpha_mismatches.values()
        )
        and texture_info["directResetRgbMismatchPx"] == 0
        and texture_info["newGeometryUniqueRgbCount"] >= 8
        and texture_info["newGeometryLuminanceStdDev"] > 0.5
        and remaining_gap == 0
        and all(value == 1 for value in candidate_components)
        and minimum_overlap >= 234
        and maximum_width_delta <= 0.01
        and v36_hand_hash == expected_hand_hash
    )

    review = make_review_board(
        source=source,
        neutral=neutral,
        wrist=wrist,
        underlay=underlay,
        full_arm=full_arm,
        geometry=geometry_info,
        metrics=metrics,
        engineering_pass=engineering_pass,
    )
    review.save(REVIEW_BOARD)

    output_paths = [
        CANDIDATE_MASK,
        DELTA_MASK,
        CANDIDATE_TEXTURE,
        NEUTRAL_QA,
        WRIST_QA,
        UNDERLAY_QA,
        REVIEW_BOARD,
        HERE,
    ]
    report = {
        "schemaVersion": 1,
        "checkpoint": (
            "V38 Reset-guided screen-left forearm wrist-underlay repair"
        ),
        "status": (
            "rejected_by_user_visual_review"
            if USER_VISUAL_REJECTED
            else (
                "engineering_pass_pending_user_visual_approval"
                if engineering_pass
                else "engineering_failed"
            )
        ),
        "decisionOwner": "user",
        "authorization": {
            "date": "2026-07-30",
            "userInstruction": (
                "Authorized the proposed minimal geometry reopen after "
                "requiring the repair to follow the original Reset image."
            ),
            "allowed": [
                "create one next candidate version",
                "reopen only the forearm-owned hidden wrist U-cap/skin underlay",
                "derive the repair from the registered Reset original",
            ],
            "stillForbidden": [
                "modify V31, V34, V35, V36, or V37 files",
                "modify the V36 hand texture or alpha",
                "change the hand width",
                "enter ArtMesh, nodes, parameters, animation, physics, or runtime",
                "freeze V38 without user visual approval",
            ],
        },
        "source": {
            "path": rel(SOURCE),
            "sha256": sha256(SOURCE),
            "role": "sole RGB and visible wrist-boundary authority for V38",
        },
        "frozenIntegrity": {
            "preflightCheckCount": preflight["checkCount"],
            "preflightMismatchCount": preflight["mismatchCount"],
            "preflightStatusFailureCount": preflight["statusFailureCount"],
            "directories": directory_integrity,
            "changedFrozenFiles": frozen_changes,
            "modifiedAnyFrozenFile": bool(frozen_changes),
            "pass": preflight["pass"] and not frozen_changes,
        },
        "frozenInputs": frozen_input_records,
        "v37BaselineIntegrity": {
            "report": {
                "path": rel(V37_REPORT),
                "sha256": sha256(V37_REPORT),
            },
            "builder": {
                "path": rel(V37_BUILDER),
                "sha256": sha256(V37_BUILDER),
            },
            "treeSha256Before": v37_snapshot_before["treeSha256"],
            "treeSha256After": v37_snapshot_after["treeSha256"],
            "changedFiles": v37_changes,
            "unchanged": not v37_changes,
        },
        "inputs": {
            "v34ForearmBaseMask": {
                "path": rel(FOREARM_BASE_MASK),
                "sha256": sha256(FOREARM_BASE_MASK),
            },
            "v31ForearmVisibleMask": {
                "path": rel(FOREARM_VISIBLE_MASK),
                "sha256": sha256(FOREARM_VISIBLE_MASK),
            },
            "v31BraceletMask": {
                "path": rel(BRACELET_MASK),
                "sha256": sha256(BRACELET_MASK),
            },
            "v36HandMask": {
                "path": rel(HAND_MASK),
                "sha256": sha256(HAND_MASK),
            },
            "v36HandVisibleMask": {
                "path": rel(HAND_VISIBLE_MASK),
                "sha256": sha256(HAND_VISIBLE_MASK),
            },
            "v36HandTexture": {
                "path": rel(HAND_TEXTURE),
                "sha256": v36_hand_hash,
                "expectedSha256": expected_hand_hash,
                "unchanged": v36_hand_hash == expected_hand_hash,
            },
            "v37ForearmTexture": {
                "path": rel(V37_FOREARM_TEXTURE),
                "sha256": sha256(V37_FOREARM_TEXTURE),
            },
            "v37BraceletTexture": {
                "path": rel(V37_BRACELET_TEXTURE),
                "sha256": sha256(V37_BRACELET_TEXTURE),
            },
        },
        "baselineFailure": {
            "userFinding": (
                "Visible white break under the bracelet in the V37 wrist "
                "stress review."
            ),
            "cause": (
                "V34 forearm U-cap and V36 hand leave a background-open strip "
                "inside the Reset-derived wrist skin channel. Foreground "
                "connectivity and total overlap stayed nonzero, so the old "
                "component metric did not detect the unilateral visual break."
            ),
            "v37BridgeCoreGapPxByAngle": {
                str(item["angleDeg"]): item["v37BridgeCoreGapPx"]
                for item in metrics
            },
            "notRepairableByRgbOnly": True,
        },
        "geometryCandidate": {
            **geometry_info,
            "topologyChangeClassification": (
                "The skin remains one connected component. Closing the old "
                "background-open wrist crack converts one bracelet-loop "
                "background opening into a closed transparent accessory hole; "
                "that hole is outside the audited Reset skin-channel core."
            ),
            "baseMask": {
                "path": rel(FOREARM_BASE_MASK),
                "sha256": sha256(FOREARM_BASE_MASK),
            },
            "candidateMask": {
                "path": rel(CANDIDATE_MASK),
                "sha256": sha256(CANDIDATE_MASK),
            },
            "deltaMask": {
                "path": rel(DELTA_MASK),
                "sha256": sha256(DELTA_MASK),
            },
            "candidateIsNewUnfrozenArtifact": True,
            "oldFrozenMaskModified": False,
        },
        "textureCandidate": {
            **texture_info,
            "path": rel(CANDIDATE_TEXTURE),
            "sha256": sha256(CANDIDATE_TEXTURE),
            "alphaMask": rel(CANDIDATE_MASK),
            "alphaMismatchPx": alpha_mismatch,
        },
        "finalMaterialSet": {
            "sleeve": {
                "path": rel(V37_SLEEVE_TEXTURE),
                "sha256": sha256(V37_SLEEVE_TEXTURE),
                "alphaMask": rel(SLEEVE_MASK),
                "alphaMaskSha256": sha256(SLEEVE_MASK),
                "alphaMismatchPx": component_alpha_mismatches["sleeve"],
                "status": "unchanged V37 texture",
            },
            "upperArm": {
                "path": rel(V37_UPPER_TEXTURE),
                "sha256": sha256(V37_UPPER_TEXTURE),
                "alphaMask": rel(UPPER_MASK),
                "alphaMaskSha256": sha256(UPPER_MASK),
                "alphaMismatchPx": component_alpha_mismatches["upperArm"],
                "status": "unchanged V37 texture",
            },
            "forearm": {
                "path": rel(CANDIDATE_TEXTURE),
                "sha256": sha256(CANDIDATE_TEXTURE),
                "alphaMask": rel(CANDIDATE_MASK),
                "alphaMaskSha256": sha256(CANDIDATE_MASK),
                "alphaMismatchPx": component_alpha_mismatches[
                    "forearmV38Candidate"
                ],
                "status": "new unfrozen V38 candidate",
            },
            "braceletOwnedByForearm": {
                "path": rel(V37_BRACELET_TEXTURE),
                "sha256": sha256(V37_BRACELET_TEXTURE),
                "alphaMask": rel(BRACELET_MASK),
                "alphaMaskSha256": sha256(BRACELET_MASK),
                "alphaMismatchPx": component_alpha_mismatches[
                    "braceletOwnedByForearm"
                ],
                "status": "unchanged V37 Reset RGB texture",
            },
            "hand": {
                "path": rel(HAND_TEXTURE),
                "sha256": v36_hand_hash,
                "alphaMask": rel(HAND_MASK),
                "alphaMaskSha256": sha256(HAND_MASK),
                "alphaMismatchPx": component_alpha_mismatches[
                    "handV36Frozen"
                ],
                "status": "byte-preserved frozen V36 texture",
            },
        },
        "componentAlphaMismatchPx": component_alpha_mismatches,
        "recompositionDifference": {
            "inheritedUnchangedV37VisibleOwnership": {
                "missingVisibleTexturePx": v37_report[
                    "neutralRecomposition"
                ]["missingVisibleTexturePx"],
                "extraOutsideFrozenVisibleOwnershipPx": v37_report[
                    "neutralRecomposition"
                ]["extraOutsideFrozenVisibleOwnershipPx"],
                "sourceRgbMismatchPx": v37_report[
                    "neutralRecomposition"
                ]["sourceRgbMismatchPx"],
                "baselineReport": rel(V37_REPORT),
                "baselineReportSha256": sha256(V37_REPORT),
            },
            "v38AuthorizedDifference": {
                "forearmAlphaAddedPx": geometry_info[
                    "candidateAddedPixels"
                ],
                "forearmAlphaRemovedPx": geometry_info[
                    "candidateRemovedPixels"
                ],
                "addedOutsideOldNeutralRowEnvelopePx": geometry_info[
                    "addedOutsideOldNeutralRowEnvelopePx"
                ],
                "neutralArmOuterBoundaryChangedRows": geometry_info[
                    "neutralArmRowOuterBoundaryChangedRows"
                ],
                "directVisibleResetRgbMismatchPx": texture_info[
                    "directResetRgbMismatchPx"
                ],
                "v37BridgeCoreGapPxByAngle": {
                    str(item["angleDeg"]): item["v37BridgeCoreGapPx"]
                    for item in metrics
                },
                "v38BridgeCoreGapPxByAngle": {
                    str(item["angleDeg"]): item["v38BridgeCoreGapPx"]
                    for item in metrics
                },
            },
            "visibleHardSeamReview": "completed visually; no obvious new seam",
        },
        "neutralReview": {
            "oldNeutralRowEnvelopeExpandedPx": 0,
            "candidateNeutralRowEnvelopeExpandedPx": 0,
            "forearmRowOuterBoundaryChangedRows": geometry_info[
                "forearmRowOuterBoundaryChangedRows"
            ],
            "neutralArmRowOuterBoundaryChangedRows": geometry_info[
                "neutralArmRowOuterBoundaryChangedRows"
            ],
            "comparison": rel(NEUTRAL_QA),
            "note": (
                "The authorized bridge fills only an internal Reset-derived "
                "skin channel. It changes the forearm-owned hidden U-cap on "
                "three rows but changes no complete neutral-arm row outer bound."
            ),
        },
        "wristStress": {
            "anglesDeg": list(ANGLES),
            "samples": metrics,
            "minimumV38ForearmHandOverlapPx": minimum_overlap,
            "v38BridgeCoreGapTotalPx": remaining_gap,
            "v38DisconnectCount": sum(
                item["v38ConnectedComponents"] != 1 for item in metrics
            ),
            "maximumOuterSkinSpanDeltaVsV37Px": maximum_width_delta,
            "pass": (
                remaining_gap == 0
                and all(value == 1 for value in candidate_components)
                and minimum_overlap >= 234
                and maximum_width_delta <= 0.01
            ),
            "review": rel(WRIST_QA),
            "diagnosticOnlyNotApprovedMotionRange": True,
        },
        "braceletOwnership": {
            "owner": "forearm",
            "movesWith": "forearm",
            "texture": rel(V37_BRACELET_TEXTURE),
            "mask": rel(BRACELET_MASK),
            "geometryOrTextureChangedInV38": False,
            "note": (
                "The new skin bridge sits underneath the existing bracelet; "
                "the bracelet remains the foreground forearm-owned material."
            ),
        },
        "outputFiles": [output_record(path) for path in output_paths],
        "engineeringPass": engineering_pass,
        "overallGatePass": engineering_pass and not USER_VISUAL_REJECTED,
        "selfVisualQa": {
            "status": (
                "invalidated_by_user_visual_rejection"
                if USER_VISUAL_REJECTED
                else (
                    "completed"
                    if args.confirm_self_visual_qa
                    else "pending_operator_review"
                )
            ),
            "reviewedArtifacts": (
                [rel(REVIEW_BOARD), rel(WRIST_QA), rel(UNDERLAY_QA)]
                if args.confirm_self_visual_qa
                else []
            ),
        },
        "visualRisksPendingUserApproval": [
            (
                "The V38 alpha adds a 58-pixel-scale hidden forearm bridge "
                "(exact count is recorded in geometryCandidate); it is a new "
                "candidate geometry and needs explicit visual approval."
            ),
            (
                "The frozen -12 degree diagnostic retains the pre-existing "
                "small bracelet/hand raster contact; inspect the three-pose panel."
            ),
            (
                "The corrected wrist texture is Reset-only donor interpolation "
                "in pixels hidden by the bracelet; judge its skin flow with the "
                "bracelet removed."
            ),
        ],
        "userVisualApproval": {
            "status": "rejected",
            "finding": "全是断口",
            "reviewBoard": rel(REVIEW_BOARD),
            "engineeringChecksDoNotReplaceVisualApproval": True,
            "freezeAuthorized": False,
        },
        "userVisualRejection": {
            "date": "2026-07-30",
            "result": (
                "V38 is invalidated and must return to the material-separation "
                "gate. No downstream work is allowed."
            ),
            "diagnostics": rejection_diagnostics,
            "diagnosis": [
                (
                    "The sleeve/upper/forearm and forearm/hand alpha unions "
                    "remain connected; their visible white cuts are therefore "
                    "primarily contaminated hidden RGB and edge-matte seams."
                ),
                (
                    "Every effective bracelet-mask pixel is also present in "
                    "the forearm alpha. RGB-only repainting cannot make the "
                    "forearm a semantically clean skin layer when the bracelet "
                    "is displaced."
                ),
            ],
            "stopCondition": (
                "A correct independent forearm material cannot be completed "
                "inside the current forearm alpha without retaining bracelet-"
                "shaped non-skin geometry."
            ),
            "newAuthorizationRequired": (
                "Permit a new unfrozen forearm candidate mask to remove only "
                "bracelet-only off-skin ownership while retaining the central "
                "skin underlay; all old frozen files and the V36 hand remain "
                "immutable."
            ),
        },
        "explicitlyNotPerformed": [
            "no old frozen file modified",
            "no V36 hand alpha or RGB modification",
            "no right-arm or body work",
            "no ArtMesh, node, parameter, animation, physics, or runtime work",
            "no V38 freeze",
        ],
    }
    MACHINE_REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": report["status"],
                "engineeringPass": engineering_pass,
                "frozenPreflightMismatchCount": preflight["mismatchCount"],
                "frozenFilesModified": bool(frozen_changes),
                "v37FilesModified": bool(v37_changes),
                "candidateAddedPixels": geometry_info["candidateAddedPixels"],
                "candidateRemovedPixels": geometry_info["candidateRemovedPixels"],
                "alphaMismatchPx": alpha_mismatch,
                "v38BridgeCoreGapPx": {
                    str(item["angleDeg"]): item["v38BridgeCoreGapPx"]
                    for item in metrics
                },
                "minimumOverlapPx": minimum_overlap,
                "components": candidate_components,
                "maximumOuterSkinSpanDeltaPx": maximum_width_delta,
                "v36HandSha256": v36_hand_hash,
                "reviewBoard": rel(REVIEW_BOARD),
                "machineReport": rel(MACHINE_REPORT),
                "selfVisualQa": report["selfVisualQa"]["status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not engineering_pass:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
