from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
XIAOXING = ROOT.parents[1]
V31 = (
    XIAOXING
    / "validation/arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve"
)
V34 = (
    XIAOXING
    / "validation/arm-chain-screen-left-v34-hand-root-from-frozen-ucap"
)
V34_TOOL = V34 / "tools/build_v34_hand_root.py"
SOURCE = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
BRACELET = V31 / "masks/visible/bracelet-owned-by-forearm.png"
USER_BLUE_ANNOTATION = ROOT / "references/user-blue-hidden-root-boundary.png"
SOURCE_TO_ANNOTATION = np.array(
    [
        [4.28191815, -0.00390210235, -191.418631],
        [0.00390210235, 4.28191815, -2025.97574],
    ],
    dtype=np.float32,
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_mask(path: Path, mask: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask.astype(np.uint8), "L").save(path)


def crop(image: Image.Image, box=(66, 475, 151, 655), scale=6) -> Image.Image:
    item = image.crop(box)
    return item.resize(
        (item.width * scale, item.height * scale),
        Image.Resampling.LANCZOS,
    )


def panel(
    board: Image.Image,
    image: Image.Image,
    box: tuple[int, int, int, int],
    label: str,
    v33,
) -> None:
    left, top, right, bottom = box
    draw = ImageDraw.Draw(board)
    draw.rounded_rectangle(
        box, radius=20, fill=(255, 255, 255), outline=(170, 183, 200), width=3
    )
    draw.text(
        (left + 20, top + 15),
        label,
        fill=(25, 38, 55),
        font=v33.font(25, True),
    )
    available = (right - left - 30, bottom - top - 82)
    scale = min(available[0] / image.width, available[1] / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    board.paste(
        resized,
        (
            left + (right - left - resized.width) // 2,
            top + 67 + (bottom - top - 67 - resized.height) // 2,
        ),
    )


def main() -> None:
    for folder in ("masks/reference", "masks/complete", "materials", "qa", "audit"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    for obsolete in (
        "masks/reference/skin-boundary-forearm-cap.png",
        "masks/complete/forearm-skin-boundary.png",
        "materials/forearm-skin-boundary.png",
    ):
        (ROOT / obsolete).unlink(missing_ok=True)

    v34 = load_module(V34_TOOL, "v34_hand_root")
    v33 = v34.load_v33()
    source = Image.open(SOURCE).convert("RGBA")
    annotation = Image.open(USER_BLUE_ANNOTATION).convert("RGBA")
    bracelet = np.asarray(Image.open(BRACELET).convert("L"), dtype=np.uint8)
    old_ucap = np.asarray(
        Image.open(V34 / "masks/reference/slim-blue-forearm-ucap.png").convert("L"),
        dtype=np.uint8,
    )
    old_forearm = np.asarray(
        Image.open(V34 / "masks/complete/forearm-slim.png").convert("L"),
        dtype=np.uint8,
    )
    old_hand_mask = np.asarray(
        Image.open(V34 / "masks/complete/hand.png").convert("L"), dtype=np.uint8
    )
    source_hand = np.asarray(
        Image.open(v34.VISIBLE_HAND).convert("L"), dtype=np.uint8
    )
    old_hand_layer = Image.open(V34 / "materials/hand.png").convert("RGBA")

    annotation_bgr = cv2.cvtColor(
        np.asarray(annotation.convert("RGB")), cv2.COLOR_RGB2BGR
    )
    blue_annotation = (
        (annotation_bgr[:, :, 0] > 150)
        & (annotation_bgr[:, :, 1] > 90)
        & (annotation_bgr[:, :, 2] < 110)
        & (
            annotation_bgr[:, :, 0].astype(np.int16)
            - annotation_bgr[:, :, 2].astype(np.int16)
            > 80
        )
    ).astype(np.uint8) * 255
    annotation_to_source = cv2.invertAffineTransform(SOURCE_TO_ANNOTATION)
    blue_boundary = cv2.warpAffine(
        blue_annotation,
        annotation_to_source,
        (v33.W, v33.H),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    blue_barrier = cv2.dilate(
        (blue_boundary > 8).astype(np.uint8),
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        iterations=1,
    )
    yy = np.indices(source_hand.shape)[0]
    traversable = (
        (source_hand > 8)
        & (blue_barrier == 0)
        & (yy >= 510)
        & (yy <= 610)
    ).astype(np.uint8)
    component_count, component_labels, component_stats, component_centroids = (
        cv2.connectedComponentsWithStats(traversable, 8)
    )
    hidden_candidates = []
    for component_id in range(1, component_count):
        x, y, width, height, area = component_stats[component_id]
        center_x, center_y = component_centroids[component_id]
        if (
            80 <= x <= 120
            and 520 <= y <= 555
            and 100 <= area <= 800
            and center_y < 550
        ):
            hidden_candidates.append((int(area), component_id))
    if not hidden_candidates:
        raise RuntimeError("User blue boundary did not isolate a hidden wrist region")
    _, hidden_component = max(hidden_candidates)
    area_above_blue = np.where(
        component_labels == hidden_component, 255, 0
    ).astype(np.uint8)
    # User correction: the blue line is the final upper boundary of the hand,
    # not the lower edge of an added hidden root. Everything above it is
    # excluded; the blue line and source skin below it define the whole hand.
    hand_mask = cv2.subtract(source_hand, area_above_blue)
    visible_hand = hand_mask.copy()
    hidden_hand = np.zeros_like(hand_mask)
    forearm_mask = old_forearm.copy()

    save_mask(ROOT / "masks/reference/user-blue-boundary-registered.png", blue_boundary)
    save_mask(ROOT / "masks/reference/user-blue-excluded-above-line.png", area_above_blue)
    save_mask(ROOT / "masks/visible/hand.png", visible_hand)
    save_mask(ROOT / "masks/hidden/hand.png", hidden_hand)
    save_mask(ROOT / "masks/complete/hand.png", hand_mask)

    bracelet_layer = v33.solid(bracelet, v33.PURPLE)
    old_forearm_layer = Image.open(V34 / "materials/forearm-slim.png").convert("RGBA")
    forearm_layer = old_forearm_layer
    visible_colors = np.asarray(old_hand_layer.convert("RGB"))[visible_hand > 8]
    skin_color = tuple(int(value) for value in np.median(visible_colors, axis=0))
    hand_layer = v33.solid(hand_mask, (*skin_color, 255))
    hand_layer.save(ROOT / "materials/hand-skin-boundary.png")
    textured_hand = source.copy()
    textured_hand.putalpha(Image.fromarray(hand_mask))
    textured_hand.save(ROOT / "materials/hand-textured-from-reset.png")
    new_default = v33.compose(
        [hand_layer, forearm_layer, bracelet_layer],
        background=v33.checker((v33.W, v33.H)),
    )

    flat_hand_review = v33.checker((v33.W, v33.H)).convert("RGBA")
    flat_hand_review.alpha_composite(hand_layer)
    textured_hand_review = v33.checker((v33.W, v33.H)).convert("RGBA")
    textured_hand_review.alpha_composite(textured_hand)
    textured_recomposition = source.copy()
    source_without_hand = source.copy()
    source_without_hand.putalpha(
        Image.fromarray(cv2.subtract(np.full_like(hand_mask, 255), hand_mask))
    )
    textured_recomposition = source_without_hand
    textured_recomposition.alpha_composite(textured_hand)
    textured_recomposition.save(
        ROOT / "qa/textured-hand-reset-recomposition.png"
    )
    texture_alpha_mismatch = int(
        np.count_nonzero(
            (np.asarray(textured_hand.getchannel("A")) > 8)
            != (hand_mask > 8)
        )
    )
    textured_recomposition_mismatch = int(
        np.count_nonzero(
            np.asarray(textured_recomposition.convert("RGBA"))
            != np.asarray(source.convert("RGBA"))
        )
    )

    full = v33.checker((v33.W, v33.H)).convert("RGBA")
    for layer in (
        Image.open(V31 / "materials/upper_arm.png").convert("RGBA"),
        hand_layer,
        forearm_layer,
        Image.open(V31 / "materials/sleeve.png").convert("RGBA"),
        bracelet_layer,
    ):
        full.alpha_composite(layer)
    full.save(ROOT / "qa/screen-left-full-arm-recomposition.png")

    overlap = int(np.count_nonzero((forearm_mask > 8) & (hand_mask > 8)))
    hand_above_blue_px = int(
        np.count_nonzero((hand_mask > 8) & (area_above_blue > 8))
    )
    forearm_skin = cv2.subtract(forearm_mask, bracelet)
    components, _ = cv2.connectedComponents(
        (forearm_skin > 8).astype(np.uint8)
    )

    stress_angles = (-12, -8, -4, 0, 4, 8, 12)
    stress_metrics = []
    stress_board = Image.new(
        "RGB", (len(stress_angles) * 360, 700), (237, 242, 248)
    )
    stress_draw = ImageDraw.Draw(stress_board)
    for index, angle in enumerate(stress_angles):
        transform = cv2.getRotationMatrix2D(
            (float(v33.WR[0]), float(v33.WR[1])), angle, 1.0
        )
        posed_hand_mask = cv2.warpAffine(
            hand_mask,
            transform,
            (v33.W, v33.H),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        posed_hand_mask = v33.largest_component(posed_hand_mask)
        posed_overlap = int(
            np.count_nonzero((forearm_mask > 8) & (posed_hand_mask > 8))
        )
        union = ((forearm_skin > 8) | (posed_hand_mask > 8)).astype(np.uint8)
        posed_components, _ = cv2.connectedComponents(union)
        disconnected = posed_components - 1 != 1
        stress_metrics.append(
            {
                "angleDeg": angle,
                "overlapPx": posed_overlap,
                "disconnected": disconnected,
            }
        )
        posed_hand_layer = v33.solid(posed_hand_mask, (*skin_color, 255))
        posed = v33.compose(
            [posed_hand_layer, forearm_layer, bracelet_layer],
            background=v33.checker((v33.W, v33.H)),
        )
        sample = crop(posed, scale=4).convert("RGB")
        sample.thumbnail((330, 600), Image.Resampling.NEAREST)
        x = index * 360 + (360 - sample.width) // 2
        stress_board.paste(sample, (x, 65))
        stress_draw.text(
            (index * 360 + 125, 18),
            f"{angle:+d}°",
            fill=(25, 38, 55),
            font=v33.font(24, True),
        )
    stress_board.save(ROOT / "qa/wrist-stress-samples.png")
    minimum_stress_overlap = min(item["overlapPx"] for item in stress_metrics)
    stress_disconnects = sum(item["disconnected"] for item in stress_metrics)

    board = Image.new("RGB", (2660, 1040), (237, 242, 248))
    draw = ImageDraw.Draw(board)
    draw.text(
        (55, 28),
        "小星 V36｜手部色块与实际纹理效果冻结审查",
        fill=(17, 28, 43),
        font=v33.font(42, True),
    )
    draw.text(
        (57, 88),
        "本板不显示任何辅助线｜色块与真实纹理使用同一手部遮罩｜纹理直接来自 Reset 原图",
        fill=(62, 75, 95),
        font=v33.font(25),
    )
    images = (
        (crop(source), "1. Reset 原图参照"),
        (crop(flat_hand_review), "2. 干净色块：无蓝线"),
        (crop(textured_hand_review), "3. 实际手部纹理：透明底"),
        (crop(textured_recomposition), "4. 实际纹理放回原位"),
    )
    for index, (image, label) in enumerate(images):
        panel(
            board,
            image.convert("RGB"),
            (35 + index * 655, 145, 655 + index * 655, 920),
            label,
            v33,
        )
    draw.text(
        (60, 960),
        (
            f"工程自检：上边界外残留手部 {hand_above_blue_px}px｜"
            f"纹理遮罩差异 {texture_alpha_mismatch}px｜"
            f"放回原位差异 {textured_recomposition_mismatch}px｜"
            f"手部重叠 {overlap}px｜"
            f"前臂皮肤连通主体 {components - 1} 个"
        ),
        fill=(24, 108, 81)
        if hand_above_blue_px == 0 and components == 2
        else (180, 48, 43),
        font=v33.font(24, True),
    )
    board_path = ROOT / "qa/V36-手部色块与实际纹理效果-冻结审查图.png"
    board.save(board_path)
    for obsolete in (
        "qa/V36-腕部贴合皮肤边界-中文审查图.png",
        "qa/V36-手部隐藏腕根贴合皮肤边界-正式审查图.png",
        "qa/V36-直接采用用户蓝线隐藏区域-正式审查图.png",
        "qa/V36-蓝线及下方为完整手部-正式审查图.png",
        "masks/reference/skin-boundary-hand-root.png",
        "masks/reference/user-blue-hidden-root.png",
    ):
        (ROOT / obsolete).unlink(missing_ok=True)

    report = {
        "status": "candidate_pending_user_visual_approval",
        "scope": "screen-left hand final upper boundary from user blue annotation",
        "authorization": "user explicitly allowed reopening V34 hand-root and forearm wrist-cap freeze",
        "unchangedFrozenAreas": [
            "sleeve",
            "upperArm",
            "bracelet",
            "visibleHandAndFiveFingerContour",
            "visibleForearmAboveBracelet",
            "skeletonAndPivots",
        ],
        "sourceHashes": {
            "userBlueAnnotation": sha256(USER_BLUE_ANNOTATION),
            "v34Hand": sha256(V34 / "materials/hand.png"),
            "v34SlimForearm": sha256(V34 / "materials/forearm-slim.png"),
            "v34SlimCap": sha256(
                V34 / "masks/reference/slim-blue-forearm-ucap.png"
            ),
            "v31Bracelet": sha256(BRACELET),
        },
        "geometry": {
            "handBoundaryMethod": "directly exclude the registered-blue-line upper component; blue line and source skin below define the complete hand",
            "sourceToAnnotationAffine": SOURCE_TO_ANNOTATION.tolist(),
            "registeredBlueBoundaryPx": int(
                np.count_nonzero(blue_boundary > 8)
            ),
            "excludedAboveBluePx": int(np.count_nonzero(area_above_blue > 8)),
            "handPixelsAboveBluePx": hand_above_blue_px,
            "slimForearmCapHandOverlapPx": overlap,
            "forearmSkinConnectedComponents": components - 1,
            "completeHandMatchesSourceHandPx": int(
                np.count_nonzero((hand_mask > 8) != (source_hand > 8))
            ),
            "textureAlphaMismatchPx": texture_alpha_mismatch,
            "texturedRecompositionChannelMismatchCount": (
                textured_recomposition_mismatch
            ),
            "oldHiddenHandPx": int(
                np.count_nonzero((old_hand_mask > 8) & (visible_hand <= 8))
            ),
            "newHiddenHandPx": 0,
            "wristStress": {
                "anglesDeg": list(stress_angles),
                "minimumOverlapPx": minimum_stress_overlap,
                "disconnectCount": stress_disconnects,
                "samples": stress_metrics,
            },
        },
        "outputs": {
            "review": "qa/V36-手部色块与实际纹理效果-冻结审查图.png",
            "fullArm": "qa/screen-left-full-arm-recomposition.png",
            "wristStress": "qa/wrist-stress-samples.png",
            "texturedHand": "materials/hand-textured-from-reset.png",
            "texturedResetRecomposition": "qa/textured-hand-reset-recomposition.png",
        },
    }
    (ROOT / "audit/machine-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(board_path)


if __name__ == "__main__":
    main()
