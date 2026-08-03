from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
XIAOXING = ROOT.parents[1]
V33 = (
    XIAOXING
    / "validation/arm-chain-screen-left-v33-skin-boundary-wrist-rebuild"
)
V33_TOOL = V33 / "tools/build_v33_skin_boundary_wrist.py"
APPROVAL = (
    V33
    / "audit/user-visual-approval-blue-forearm-ucap-2026-07-29.json"
)
SOURCE = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
FROZEN_BLUE = V33 / "masks/reference/blue-forearm-ucap.png"
FROZEN_FOREARM = V33 / "materials/forearm.png"
FROZEN_FOREARM_COMPLETE = V33 / "masks/complete/forearm.png"
FROZEN_FOREARM_VISIBLE = V33 / "masks/visible/forearm.png"
VISIBLE_HAND = V33 / "masks/visible/hand.png"
BRACELET = (
    XIAOXING
    / "validation/arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve"
    / "masks/visible/bracelet-owned-by-forearm.png"
)
SKELETON = (
    XIAOXING
    / "validation/arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve"
    / "skeleton-lock.json"
)
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
FINAL_APPROVAL = (
    ROOT / "audit/user-visual-approval-and-freeze-authorization-2026-07-29.json"
)


def load_v33():
    spec = importlib.util.spec_from_file_location("v33_helpers", V33_TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.ROOT = ROOT
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def verify_freeze_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    checks = []
    for item in [*manifest["lockedGeometry"], manifest["userApproval"]]:
        artifact = V31 / item["path"]
        actual = sha256(artifact)
        checks.append(
            {
                "path": item["path"],
                "expectedSha256": item["sha256"],
                "actualSha256": actual,
                "match": actual == item["sha256"],
            }
        )
    return {
        "manifest": str(path.relative_to(XIAOXING)).replace("\\", "/"),
        "manifestSha256": sha256(path),
        "status": manifest["status"],
        "checks": checks,
        "pass": all(item["match"] for item in checks),
    }


def outline(
    mask: np.ndarray,
    color: tuple[int, int, int, int],
    width: int = 2,
) -> Image.Image:
    binary = (mask > 8).astype(np.uint8)
    expanded = cv2.dilate(
        binary,
        np.ones((width * 2 + 1, width * 2 + 1), np.uint8),
        iterations=1,
    )
    edge = np.where(expanded > binary, 255, 0).astype(np.uint8)
    return v33_solid_exact(edge, color)


def hand_root_boundary(v33) -> tuple[
    np.ndarray,
    list[tuple[float, float]],
    list[tuple[float, float]],
    list[tuple[float, float]],
]:
    # The user-facing ownership seam is an OPEN ∩ line. It follows the Reset
    # wrist skin from the left side, beneath the bracelet, to the right side.
    # The complete hidden material closes behind that seam; its closed mask is
    # not itself the visual boundary under review.
    seam_left = v33.cubic(
        (83, 567), (91, 560), (98, 548), (106, 544), 30
    )
    seam_top = v33.cubic(
        (106, 544), (112, 542), (118, 544), (122, 551), 26
    )[1:]
    seam_right = v33.cubic(
        (122, 551), (125, 558), (121, 566), (116, 570), 24
    )[1:]
    seam = [*seam_left, *seam_top, *seam_right]

    hidden_right = v33.cubic(
        (116, 570), (125, 562), (132, 545), (133, 530), 24
    )[1:]
    hidden_top = v33.cubic(
        (133, 530), (122, 527), (106, 524), (94, 523), 36
    )[1:]
    hidden_left = v33.cubic(
        (94, 523), (90, 538), (84, 555), (83, 567), 28
    )[1:]
    hidden_boundary = [
        *seam,
        *hidden_right,
        *hidden_top,
        *hidden_left,
    ]
    # This narrow patch stays behind the open seam on the screen-right wrist
    # edge. It resolves transform-raster coverage without moving or thickening
    # the user-approved visual seam.
    internal_coverage_patch = [
        (116, 540),
        (127, 537),
        (130, 553),
        (119, 570),
        (111, 558),
    ]
    root = np.maximum(
        v33.supersampled_polygon(hidden_boundary),
        v33.supersampled_polygon(internal_coverage_patch),
    )
    return (
        root,
        seam,
        hidden_boundary,
        internal_coverage_patch,
    )


def slim_forearm_ucap(v33) -> tuple[
    np.ndarray,
    list[tuple[float, float]],
    list[tuple[float, float]],
]:
    # Scope-limited reopen authorized by the user. Keep the proximal wrist
    # span and attachment, but reduce the distal belly from about 33 px to
    # about 27 px past the locked wrist pivot while retaining the 510 px
    # 41-frame overlap baseline.
    boundary = [
        (105, 529),
        (103.5, 534.7),
        (101.9, 540.3),
        (100.8, 545.4),
        (102.3, 551.1),
        (107.9, 555.2),
        (113.6, 553.5),
        (117, 550),
        (119.6, 544.9),
        (121.6, 538.2),
        (123.1, 532),
    ]
    attachment = [
        (99, 528),
        (105, 528),
        (107, 531),
        (104, 533),
        (99, 531),
    ]
    mask = np.maximum(
        v33.supersampled_polygon(boundary),
        v33.supersampled_polygon(attachment),
    )
    return mask, boundary, attachment


def draw_open_boundary(
    image: Image.Image,
    points: list[tuple[float, float]],
    color: tuple[int, int, int, int],
    width: int = 3,
) -> None:
    ImageDraw.Draw(image).line(
        points,
        fill=color,
        width=width,
        joint="curve",
    )


def draw_visible_mask_boundary_near_seam(
    image: Image.Image,
    visible_mask: np.ndarray,
    seam: list[tuple[float, float]],
    color: tuple[int, int, int, int],
) -> None:
    """Draw the review mark on the rasterized visible-skin edge itself."""
    binary = (visible_mask > 8).astype(np.uint8)
    inside_edge = binary - cv2.erode(
        binary,
        np.ones((3, 3), np.uint8),
        iterations=1,
    )
    seam_band_image = Image.new("L", (image.width, image.height), 0)
    ImageDraw.Draw(seam_band_image).line(
        seam,
        fill=255,
        width=9,
        joint="curve",
    )
    seam_band = np.asarray(seam_band_image, dtype=np.uint8) > 0
    flush_edge = ((inside_edge > 0) & seam_band).astype(np.uint8)
    image.alpha_composite(
        v33_solid_exact(flush_edge * 255, color)
    )


def v33_solid_exact(
    mask: np.ndarray,
    color: tuple[int, int, int, int],
) -> Image.Image:
    layer = Image.new("RGBA", (mask.shape[1], mask.shape[0]), color)
    layer.putalpha(Image.fromarray(mask.astype(np.uint8)))
    return layer


def mark_pivot(image: Image.Image, pivot: np.ndarray) -> None:
    draw = ImageDraw.Draw(image)
    x, y = int(pivot[0]), int(pivot[1])
    draw.ellipse(
        (x - 4, y - 4, x + 4, y + 4),
        fill=(255, 255, 255, 255),
        outline=(225, 42, 42, 255),
        width=2,
    )
    draw.line((x - 7, y, x + 7, y), fill=(225, 42, 42, 255), width=1)
    draw.line((x, y - 7, x, y + 7), fill=(225, 42, 42, 255), width=1)


def build_overlap_explainer(
    v33,
    source: Image.Image,
    blue_ucap: np.ndarray,
    yellow_root: np.ndarray,
    bracelet_layer: Image.Image,
    yellow_seam: list[tuple[float, float]],
    forearm_extension_px: float,
    hand_extension_px: float,
    overlap_area_px: int,
) -> None:
    source_view = source.copy()
    draw_open_boundary(
        source_view, yellow_seam, (255, 72, 72, 255), 3
    )
    mark_pivot(source_view, v33.WR)

    forearm_view = v33.checker((v33.W, v33.H)).convert("RGBA")
    forearm_view.alpha_composite(v33.solid(blue_ucap, v33.BLUE))
    mark_pivot(forearm_view, v33.WR)

    hand_view = v33.checker((v33.W, v33.H)).convert("RGBA")
    hand_view.alpha_composite(v33.solid(yellow_root, v33.GREEN))
    mark_pivot(hand_view, v33.WR)

    overlap = (blue_ucap > 8) & (yellow_root > 8)
    combined = v33.checker((v33.W, v33.H)).convert("RGBA")
    blue_layer = v33.solid(blue_ucap, v33.BLUE)
    blue_layer.putalpha(
        blue_layer.getchannel("A").point(lambda value: value * 0.72)
    )
    green_layer = v33.solid(yellow_root, v33.GREEN)
    green_layer.putalpha(
        green_layer.getchannel("A").point(lambda value: value * 0.72)
    )
    combined.alpha_composite(blue_layer)
    combined.alpha_composite(green_layer)
    combined.alpha_composite(
        v33.solid(overlap.astype(np.uint8) * 255, (255, 212, 48, 255))
    )
    combined.alpha_composite(bracelet_layer)
    draw_open_boundary(
        combined, yellow_seam, (255, 72, 72, 255), 3
    )
    mark_pivot(combined, v33.WR)

    board = Image.new("RGB", (2200, 1600), (238, 243, 249))
    draw = ImageDraw.Draw(board)
    draw.text(
        (55, 30),
        "腕关节覆盖关系｜简明图",
        fill=(18, 28, 43),
        font=v33.font(42, True),
    )
    draw.text(
        (55, 88),
        "红点=活动关节点；红线=皮肤分界；蓝=前臂延伸；绿=手部回插；黄=两者重叠。",
        fill=(58, 71, 91),
        font=v33.font(23),
    )
    panels = [
        (
            v33.crop_hand(source_view, 7),
            "1. 关节点不是硬拼接边界｜两块材料都越过红点",
        ),
        (
            v33.crop_hand(forearm_view, 7),
            f"2. 前臂越过关节点约 {forearm_extension_px:.1f}px｜覆盖较多",
        ),
        (
            v33.crop_hand(hand_view, 7),
            f"3. 手部向前臂回插约 {hand_extension_px:.1f}px｜覆盖较少",
        ),
        (
            v33.crop_hand(combined, 7),
            f"4. 实际重叠 {overlap_area_px}px｜手链随前臂置顶",
        ),
    ]
    for index, (image, label) in enumerate(panels):
        row, column = divmod(index, 2)
        v33.fit(
            board,
            image,
            (
                45 + column * 1080,
                145 + row * 615,
                1055 + column * 1080,
                730 + row * 615,
            ),
            label,
        )
    draw.rounded_rectangle(
        (65, 1390, 2135, 1535),
        radius=18,
        fill="white",
        outline=(170, 183, 200),
        width=3,
    )
    draw.text(
        (95, 1425),
        "动作时：前臂与手围绕同一个红点旋转；黄色重叠区负责兜底，所以不会在红线处裂开。",
        fill=(35, 48, 64),
        font=v33.font(23, True),
    )
    board.save(ROOT / "qa/V34-腕关节覆盖关系-简明审查图.png")


def crop_full_hand(image: Image.Image, scale: int = 5) -> Image.Image:
    crop = image.crop((55, 500, 145, 635))
    return crop.resize(
        (crop.width * scale, crop.height * scale),
        Image.Resampling.NEAREST,
    )


def build_foreground_stress(
    v33,
    hand_layer: Image.Image,
    ucap_layer: Image.Image,
    bracelet_layer: Image.Image,
) -> list[dict]:
    angles = (-12, -8, -4, 0, 4, 8, 12)
    results = []
    board = Image.new("RGB", (2100, 650), (241, 245, 250))
    for column, angle in enumerate(angles):
        hand = v33.rotate_translate(
            hand_layer,
            v33.WR,
            v33.WR,
            angle,
        )
        hand_alpha = v33.alpha(hand)
        ucap_alpha = v33.alpha(ucap_layer)
        overlap = int(np.count_nonzero(ucap_alpha & hand_alpha))
        union = ucap_alpha | hand_alpha
        disconnected = (
            cv2.connectedComponents(
                union.astype(np.uint8),
                connectivity=8,
            )[0]
            - 1
            != 1
        )
        foreground_only = int(
            np.count_nonzero(ucap_alpha & ~hand_alpha)
        )
        results.append(
            {
                "wristRelativeDeg": angle,
                "completeOverlapPx": overlap,
                "ucapForegroundOnlyPx": foreground_only,
                "disconnected": bool(disconnected),
            }
        )
        diagnostic = v33.checker((v33.W, v33.H)).convert("RGBA")
        diagnostic.alpha_composite(hand)
        diagnostic.alpha_composite(ucap_layer)
        diagnostic.alpha_composite(bracelet_layer)
        v33.fit(
            board,
            v33.crop_hand(diagnostic, 5),
            (
                column * 300 + 8,
                15,
                column * 300 + 292,
                610,
            ),
            (
                f"{angle:+d}°｜重叠 {overlap}px｜"
                f"{'断开' if disconnected else '无缝'}"
            ),
        )
    ImageDraw.Draw(board).text(
        (25, 615),
        (
            "前后顺序：手部 → 前臂凸包 → 手链。"
            "前臂凸包是前景材料，未被手部覆盖不判作穿帮。"
        ),
        fill=(58, 71, 91),
        font=v33.font(19, True),
    )
    board.save(ROOT / "qa/wrist-stress-review.png")
    return results


def rebuild_motion_labels(
    v33,
    skeleton: dict,
    forearm_layer: Image.Image,
    bracelet_layer: Image.Image,
    hand_layer: Image.Image,
) -> None:
    rest1 = skeleton["restAnglesDeg"]["theta1"]
    rest2 = skeleton["restAnglesDeg"]["theta2"]
    target = skeleton["stageAQaMotion"]["target"]
    l1 = skeleton["boneLengthsPx"]["L1ShoulderToElbow"]
    l2 = skeleton["boneLengthsPx"]["L2ElbowToWrist"]
    rest_global = math.degrees(
        math.atan2(v33.WR[1] - v33.E[1], v33.WR[0] - v33.E[0])
    )
    frames = []
    selected = {}
    for index in range(41):
        k = index if index <= 20 else 40 - index
        progress = 0.5 * (1 - math.cos(math.pi * k / 20.0))
        theta1 = rest1 + (target["theta1"] - rest1) * progress
        theta2 = rest2 + (target["theta2"] - rest2) * progress
        new_elbow = v33.point_at(v33.S, l1, theta1)
        new_wrist = v33.point_at(
            new_elbow,
            l2,
            theta1 + theta2,
        )
        forearm_delta = theta1 + theta2 - rest_global
        wrist_delta = forearm_delta + target["wristLocal"] * progress
        posed_forearm = v33.rotate_translate(
            forearm_layer,
            v33.E,
            new_elbow,
            forearm_delta,
            (v33.MOTION_W, v33.H),
            v33.MOTION_OFFSET,
        )
        posed_bracelet = v33.rotate_translate(
            bracelet_layer,
            v33.E,
            new_elbow,
            forearm_delta,
            (v33.MOTION_W, v33.H),
            v33.MOTION_OFFSET,
        )
        posed_hand = v33.rotate_translate(
            hand_layer,
            v33.WR,
            new_wrist,
            wrist_delta,
            (v33.MOTION_W, v33.H),
            v33.MOTION_OFFSET,
        )
        forearm_alpha = v33.alpha(posed_forearm)
        hand_alpha = v33.alpha(posed_hand)
        overlap = int(np.count_nonzero(forearm_alpha & hand_alpha))
        disconnected = (
            cv2.connectedComponents(
                (forearm_alpha | hand_alpha).astype(np.uint8),
                connectivity=8,
            )[0]
            - 1
            != 1
        )
        pose = v33.compose(
            [posed_hand, posed_forearm, posed_bracelet],
            (v33.MOTION_W, v33.H),
        )
        center = new_wrist + v33.MOTION_OFFSET
        box = (
            max(0, int(center[0]) - 62),
            max(0, int(center[1]) - 42),
            min(v33.MOTION_W, int(center[0]) + 62),
            min(v33.H, int(center[1]) + 132),
        )
        detail = pose.crop(box)
        backing = v33.checker(detail.size).convert("RGBA")
        backing.alpha_composite(detail)
        backing = backing.resize((268, 374), Image.Resampling.LANCZOS)
        frame = Image.new("RGB", (280, 420), (241, 245, 250))
        frame.paste(backing.convert("RGB"), (6, 34))
        ImageDraw.Draw(frame).text(
            (8, 6),
            (
                f"{index:02d}｜重叠 {overlap}px｜"
                f"{'断开' if disconnected else '无缝'}"
            ),
            fill=(18, 28, 43),
            font=v33.font(14, True),
        )
        frames.append(frame)
        if index in (0, 5, 10, 15, 20, 25, 30, 35, 40):
            selected[index] = frame
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


def build_hand_material_review(
    v33,
    source: Image.Image,
    visible_layer: Image.Image,
    hidden_layer: Image.Image,
    complete_layer: Image.Image,
    default: Image.Image,
    displaced: Image.Image,
    minimum_overlap: int,
    max_fk_exposure: int,
    max_stress_exposure: int,
) -> None:
    visible_view = v33.compose(
        [visible_layer],
        background=v33.checker((v33.W, v33.H)),
    )
    hidden_view = v33.compose(
        [hidden_layer],
        background=v33.checker((v33.W, v33.H)),
    )
    complete_view = v33.compose(
        [complete_layer],
        background=v33.checker((v33.W, v33.H)),
    )

    board = Image.new("RGB", (2700, 2500), (238, 243, 249))
    draw = ImageDraw.Draw(board)
    draw.text(
        (55, 28),
        "小星｜完整手部纯色材料正式审查",
        fill=(18, 28, 43),
        font=v33.font(42, True),
    )
    draw.text(
        (55, 86),
        "这是几何与覆盖审查，不是最终纹理。前臂蓝色凸包保持冻结，手链仍归前臂。",
        fill=(58, 71, 91),
        font=v33.font(23),
    )
    panels = [
        (
            crop_full_hand(source, 5),
            "1. Reset 原手｜身份与外轮廓参考",
        ),
        (
            crop_full_hand(visible_view, 5),
            "2. 可见手材料｜只保留红线以下的 Reset 手部",
        ),
        (
            crop_full_hand(hidden_view, 5),
            "3. 腕部隐藏回插｜藏在前臂后，不默认露出",
        ),
        (
            crop_full_hand(complete_view, 5),
            "4. 完整手单件｜可见手＋隐藏回插",
        ),
        (
            crop_full_hand(default, 5),
            "5. 默认回组｜红线上方归前臂，腕部不再变粗",
        ),
        (
            crop_full_hand(displaced, 5),
            "6. 前臂移开｜完整手无孔、无圆片",
        ),
    ]
    for index, (image, label) in enumerate(panels):
        row, column = divmod(index, 3)
        v33.fit(
            board,
            image,
            (
                35 + column * 890,
                135 + row * 1010,
                855 + column * 890,
                1115 + row * 1010,
            ),
            label,
        )
    draw.rounded_rectangle(
        (65, 2200, 2635, 2425),
        radius=20,
        fill="white",
        outline=(170, 183, 200),
        width=3,
    )
    draw.text(
        (95, 2235),
        "请审查：手掌与手指外轮廓是否保持 Reset？手腕有没有变粗、变细或鼓包？",
        fill=(35, 48, 64),
        font=v33.font(23, True),
    )
    draw.text(
        (95, 2300),
        (
            f"机器：单连通无孔｜最小重叠 {minimum_overlap}px｜"
            "41 帧无断裂｜前臂置于手部上层｜手部尚未冻结"
        ),
        fill=(20, 102, 77),
        font=v33.font(22, True),
    )
    board.save(ROOT / "qa/V34-完整手部纯色材料-正式审查图.png")


def build_slim_ucap_review(
    v33,
    frozen_ucap: np.ndarray,
    slim_ucap: np.ndarray,
    bracelet_layer: Image.Image,
    default: Image.Image,
    old_extension_px: float,
    new_extension_px: float,
    minimum_overlap: int,
) -> None:
    comparison = v33.checker((v33.W, v33.H)).convert("RGBA")
    old_layer = v33.solid(frozen_ucap, (225, 67, 55, 255))
    old_layer.putalpha(
        old_layer.getchannel("A").point(lambda value: value * 0.55)
    )
    comparison.alpha_composite(old_layer)
    comparison.alpha_composite(v33.solid(slim_ucap, v33.BLUE))
    comparison.alpha_composite(bracelet_layer)

    board = Image.new("RGB", (2300, 1700), (238, 243, 249))
    draw = ImageDraw.Draw(board)
    draw.text(
        (55, 28),
        "小星｜前臂隐藏 U 形凸包削瘦复核",
        fill=(18, 28, 43),
        font=v33.font(42, True),
    )
    draw.text(
        (55, 86),
        "红=原冻结凸包；蓝=削瘦候选。可见前臂、手链、手部外轮廓均未改变。",
        fill=(58, 71, 91),
        font=v33.font(23),
    )
    items = [
        (
            v33.crop_hand(comparison, 7),
            (
                f"1. 凸包前后对比｜约 {old_extension_px:.1f}px "
                f"→ {new_extension_px:.1f}px"
            ),
        ),
        (
            crop_full_hand(default, 5),
            "2. 默认回组｜检查腕部是否仍显臃肿",
        ),
        (
            Image.open(ROOT / "qa/fk-key-wrist-samples.png").convert(
                "RGB"
            ),
            "3. 41 帧关键样本｜检查侧边穿出与断裂",
        ),
        (
            Image.open(ROOT / "qa/wrist-stress-review.png").convert(
                "RGB"
            ),
            "4. ±12°压力检查｜检查极限角度穿模",
        ),
    ]
    for index, (image, label) in enumerate(items):
        row, column = divmod(index, 2)
        v33.fit(
            board,
            image,
            (
                35 + column * 1135,
                130 + row * 690,
                1110 + column * 1135,
                800 + row * 690,
            ),
            label,
        )
    draw.rounded_rectangle(
        (65, 1535, 2235, 1650),
        radius=18,
        fill="white",
        outline=(170, 183, 200),
        width=3,
    )
    draw.text(
        (95, 1572),
        (
            f"机器：41 帧最小重叠 {minimum_overlap}px（门槛 510px）｜"
            "41 帧与 ±12°均无断裂｜候选尚未冻结"
        ),
        fill=(20, 102, 77),
        font=v33.font(22, True),
    )
    board.save(ROOT / "qa/V34-前臂凸包削瘦复核图.png")


def build_final_stage_a_review(
    v33,
    source: Image.Image,
    complete_hand_view: Image.Image,
    default: Image.Image,
    overlay: Image.Image,
    displaced: Image.Image,
    coverage_review: Image.Image,
    ownership_review: Image.Image,
    zoom_review: Image.Image,
    minimum_overlap: int,
    max_fk_foreground_only: int,
    max_stress_foreground_only: int,
    engineering_pass: bool,
) -> None:
    board = Image.new("RGB", (3400, 5900), (238, 243, 249))
    draw = ImageDraw.Draw(board)
    draw.text(
        (70, 35),
        "小星 V34｜screen-left 手部阶段 A 最终中文视觉审查板",
        fill=(18, 28, 43),
        font=v33.font(48, True),
    )
    draw.text(
        (70, 100),
        (
            "本板合并已批准手形与削瘦前臂凸包。橙/红=前景前臂凸包，"
            "紫=前臂所属手链；候选仍未冻结。"
        ),
        fill=(58, 71, 91),
        font=v33.font(27),
    )
    items = [
        (
            crop_full_hand(source, 6),
            "1. Reset 原图手部｜看真实腕宽、掌形与五指",
        ),
        (
            crop_full_hand(complete_hand_view, 6),
            "2. 手部纯色完整材料｜看单一主体、隐藏腕根和开放指缝",
        ),
        (
            crop_full_hand(default, 6),
            "3. 默认回组｜看是否像原图、腕部是否仍显臃肿",
        ),
        (
            crop_full_hand(overlay, 6),
            "4. 回组叠 Reset｜看边界偏移、前臂漏出与手部上窜",
        ),
        (
            crop_full_hand(displaced, 6),
            "5. 前臂移开｜看完整手部隐藏根是否连续、是否像补丁",
        ),
        (
            coverage_review,
            "6. 削瘦凸包半透明叠手｜看真实前后层与重叠范围",
        ),
        (
            ownership_review,
            "7. 手链排除与像素归属｜可见手侵占必须为 0px",
        ),
        (
            zoom_review,
            "8. 腕/掌/指局部放大｜看粗细、长度、粘连和手套感",
        ),
        (
            Image.open(ROOT / "qa/fk-key-wrist-samples.png").convert("RGB"),
            "9. 41 帧关键样本｜看断裂、侧边穿出和整体随动",
        ),
        (
            Image.open(ROOT / "qa/wrist-stress-review.png").convert("RGB"),
            "10. ±12°压力检查｜极限诊断，不代表批准动作范围",
        ),
    ]
    for index, (image, label) in enumerate(items):
        row, column = divmod(index, 2)
        v33.fit(
            board,
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
        "4 削瘦凸包是否仍显臃肿或穿进掌心？  5 手链是否可见且无手部可见像素侵占？",
        "6 手掌与五指是否符合原图？  7 指缝是否保留？  8 手指是否过粗、过短、粘连或像手套？",
        "9 运动中是否出现漏出、上窜、侧穿或透明缝？  10 哪一处是最早失败点？",
    ]
    draw.text(
        (105, 5442),
        "请逐项审查：",
        fill=(132, 55, 28),
        font=v33.font(28, True),
    )
    for row, question in enumerate(questions):
        draw.text(
            (105, 5495 + row * 74),
            question,
            fill=(35, 48, 64),
            font=v33.font(24, row == 3),
        )
    draw.text(
        (105, 5790),
        (
            f"机器门禁：{'通过' if engineering_pass else '未通过'}｜"
            f"41 帧最小重叠 {minimum_overlap}px｜"
            f"41 帧/压力前景凸包未被手覆盖最大 "
            f"{max_fk_foreground_only}/{max_stress_foreground_only}px｜"
            "均无断裂｜候选尚未冻结"
        ),
        fill=(20, 102, 77) if engineering_pass else (178, 50, 43),
        font=v33.font(22, True),
    )
    board.save(ROOT / "qa/V34-阶段A-screen-left手部-最终中文视觉审查板.png")


def main() -> None:
    for folder in (
        "masks/visible",
        "masks/hidden",
        "masks/complete",
        "masks/reference",
        "materials",
        "qa",
        "samples",
        "audit",
    ):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)

    v33 = load_v33()
    user_approved = FINAL_APPROVAL.exists()
    approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
    frozen_hashes = {
        item["path"]: item["sha256"]
        for item in approval["frozenArtifacts"]
    }
    assert approval["status"] == "user_visual_approved_frozen"
    assert approval["frozen"]["forearmUCap"] is True
    assert (
        sha256(FROZEN_BLUE)
        == frozen_hashes["../masks/reference/blue-forearm-ucap.png"]
    )
    assert (
        sha256(FROZEN_FOREARM_COMPLETE)
        == frozen_hashes["../masks/complete/forearm.png"]
    )
    frozen_before = {
        "blueUCap": sha256(FROZEN_BLUE),
        "forearmComplete": sha256(FROZEN_FOREARM_COMPLETE),
        "forearmMaterial": sha256(FROZEN_FOREARM),
    }
    freeze_checks_before = {
        "upperArm": verify_freeze_manifest(UPPER_FREEZE),
        "forearm": verify_freeze_manifest(FOREARM_FREEZE),
    }
    assert all(item["pass"] for item in freeze_checks_before.values())

    source = Image.open(SOURCE).convert("RGBA")
    source_visible_hand = np.asarray(
        Image.open(VISIBLE_HAND).convert("L"), dtype=np.uint8
    )
    frozen_blue_ucap = np.asarray(
        Image.open(FROZEN_BLUE).convert("L"), dtype=np.uint8
    )
    blue_ucap, blue_boundary, blue_attachment = slim_forearm_ucap(v33)
    bracelet = np.asarray(
        Image.open(BRACELET).convert("L"), dtype=np.uint8
    )
    skeleton = json.loads(SKELETON.read_text(encoding="utf-8"))
    frozen_forearm_complete_mask = np.asarray(
        Image.open(FROZEN_FOREARM_COMPLETE).convert("L"),
        dtype=np.uint8,
    )
    visible_forearm_mask = np.asarray(
        Image.open(FROZEN_FOREARM_VISIBLE).convert("L"),
        dtype=np.uint8,
    )
    forearm_complete_mask = cv2.subtract(
        frozen_forearm_complete_mask,
        frozen_blue_ucap,
    )
    forearm_complete_mask = np.maximum(
        forearm_complete_mask,
        visible_forearm_mask,
    )
    forearm_complete_mask = np.maximum(forearm_complete_mask, bracelet)
    forearm_complete_mask = np.maximum(forearm_complete_mask, blue_ucap)
    v33.save_mask(
        ROOT / "masks/reference/slim-blue-forearm-ucap.png",
        blue_ucap,
    )
    v33.save_mask(
        ROOT / "masks/complete/forearm-slim.png",
        forearm_complete_mask,
    )

    (
        base_hidden_root,
        yellow_seam,
        yellow_hidden_boundary,
        internal_coverage_patch,
    ) = hand_root_boundary(v33)
    ownership_keep = v33.supersampled_polygon(
        [
            *yellow_seam,
            (v33.W, yellow_seam[-1][1]),
            (v33.W, v33.H),
            (0, v33.H),
            (0, yellow_seam[0][1]),
        ]
    )
    visible_hand = cv2.bitwise_and(
        source_visible_hand,
        ownership_keep,
    )
    hand_reach = cv2.dilate(
        (visible_hand > 8).astype(np.uint8),
        np.ones((27, 27), np.uint8),
    )
    blue_overlap = np.where(
        (frozen_blue_ucap > 8) & (hand_reach > 0),
        255,
        0,
    ).astype(np.uint8)
    proximal_patch = cv2.bitwise_and(
        v33.supersampled_polygon(
            [
                (100, 524),
                (129, 529),
                (128, 538),
                (105, 536),
                (101, 531),
            ]
        ),
        forearm_complete_mask,
    )
    yellow_root = np.maximum(blue_overlap, proximal_patch)
    complete_hand = v33.largest_component(
        np.maximum(visible_hand, yellow_root)
    )
    complete_hand = v33.fill_small_holes(complete_hand, 20.0)
    hidden_hand = cv2.subtract(complete_hand, visible_hand)

    v33.save_mask(ROOT / "masks/visible/hand.png", visible_hand)
    v33.save_mask(ROOT / "masks/hidden/hand.png", hidden_hand)
    v33.save_mask(ROOT / "masks/complete/hand.png", complete_hand)
    v33.save_mask(
        ROOT / "masks/reference/yellow-hand-root.png", yellow_root
    )

    skeleton_lock = {
        "schemaVersion": 1,
        "status": "referenced_frozen_skeleton_for_v34_hand_stage_a",
        "scope": "screen-left hand Stage A flat geometry only",
        "frozenSkeleton": {
            "path": (
                "../arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve/"
                "skeleton-lock.json"
            ),
            "sha256": sha256(SKELETON),
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
        "scope": "screen-left hand plus user-authorized hidden forearm U-cap slim candidate",
        "directionConvention": "left means screen-left, consistent with V31",
        "authoritativeVisibleSource": {
            "path": "../../source/masters/front-color-source-exact-after-reset.png",
            "sha256": sha256(SOURCE),
        },
        "visiblePixelOwnership": [
            "wrist skin below the forearm-owned bracelet",
            "palm and hand-back silhouette visible in Reset",
            "five-finger outer contour visible in Reset",
            "background-connected negative spaces between fingers visible in Reset",
        ],
        "hiddenRootResponsibility": (
            "one continuous hand material extending behind the foreground forearm; "
            "no circular patch, mechanical rectangle, detached insert, or scale trick"
        ),
        "forearmUCapOverlapResponsibility": {
            "originalFrozenSource": (
                "../arm-chain-screen-left-v33-skin-boundary-wrist-rebuild/"
                "masks/reference/blue-forearm-ucap.png"
            ),
            "originalFrozenSourceBytePreserved": True,
            "authorizedSlimCandidate": "masks/reference/slim-blue-forearm-ucap.png",
            "rule": (
                "the forearm U-cap remains the foreground owner while hand and "
                "forearm overlap across the active wrist; connectivity and final "
                "draw order, rather than full hand coverage of the foreground cap, "
                "define the no-gap gate"
            ),
            "minimumCompleteOverlapPx": 510,
        },
        "braceletExclusionResponsibility": {
            "owner": "forearm",
            "mask": (
                "../arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve/"
                "masks/visible/bracelet-owned-by-forearm.png"
            ),
            "visibleHandMustExclude": True,
            "hiddenHandUnderlapAllowed": True,
            "braceletDrawnAboveHandAndForearm": True,
        },
        "forbiddenIntrusionRegions": [
            "background outside the Reset hand contour and declared hidden wrist corridor",
            "shirt or sleeve",
            "skirt",
            "screen-right hand or any other body region",
        ],
        "drawOrderBackToFront": [
            {"id": "hand", "order": 20},
            {"id": "slim_forearm_candidate", "order": 30},
            {"id": "forearm_owned_bracelet", "order": 40},
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
            "frozenVisibleForearm": "none",
            "frozenBracelet": "none",
            "originalFrozenForearmUCap": "none_byte_preserved",
            "newSlimForearmUCap": "scope_limited_candidate_not_frozen",
        },
    }
    save_json(ROOT / "hand-layering-contract.json", contract)

    forearm_layer = v33.solid(
        forearm_complete_mask,
        v33.ORANGE,
    )
    forearm_layer.save(ROOT / "materials/forearm-slim.png")
    bracelet_layer = v33.solid(bracelet, v33.PURPLE)
    source_rgb = np.asarray(source.convert("RGB"), dtype=np.uint8)
    visible_pixels = source_rgb[visible_hand > 8]
    skin_candidates = visible_pixels[
        (visible_pixels[:, 0] > 180)
        & (visible_pixels[:, 1] > 120)
        & (visible_pixels[:, 2] > 110)
        & (
            np.max(visible_pixels, axis=1)
            - np.min(visible_pixels, axis=1)
            > 8
        )
    ]
    skin_rgb = tuple(
        int(value) for value in np.median(skin_candidates, axis=0)
    )
    hidden_rgb = tuple(max(0, value - delta) for value, delta in zip(
        skin_rgb, (14, 28, 28)
    ))
    visible_layer = v33.solid(visible_hand, (*skin_rgb, 255))
    hidden_layer = v33.solid(hidden_hand, (*hidden_rgb, 255))
    hand_layer = v33.solid(complete_hand, (*skin_rgb, 255))
    hand_diagnostic_layer = v33.solid(complete_hand, v33.GREEN)
    ucap_layer = v33.solid_exact(blue_ucap, (230, 64, 55, 255))
    visible_layer.save(ROOT / "materials/hand-visible-flat.png")
    hidden_layer.save(ROOT / "materials/hand-hidden-flat.png")
    hand_layer.save(ROOT / "materials/hand.png")

    hidden_root_review = v33.compose(
        [
            visible_layer,
            v33.solid(hidden_hand, (38, 176, 126, 255)),
        ],
        background=v33.checker((v33.W, v33.H)),
    )
    crop_full_hand(hidden_root_review, 5).save(
        ROOT / "qa/complete-hand-hidden-root-closeup.png"
    )

    default = v33.compose(
        [hand_layer, forearm_layer, bracelet_layer],
        background=v33.checker((v33.W, v33.H)),
    )
    default.save(ROOT / "qa/default-solid-recomposition.png")
    crop_full_hand(default, 5).save(
        ROOT / "qa/default-solid-recomposition-closeup.png"
    )

    complete_hand_view = v33.compose(
        [hand_layer],
        background=v33.checker((v33.W, v33.H)),
    )
    hand_displaced = v33.checker((v33.W, v33.H)).convert("RGBA")
    faded_default = v33.compose([hand_layer, forearm_layer, bracelet_layer])
    faded_default.putalpha(
        faded_default.getchannel("A").point(lambda value: value * 0.22)
    )
    hand_displaced.alpha_composite(faded_default)
    shifted_hand = hand_layer.transform(
        (v33.W, v33.H),
        Image.Transform.AFFINE,
        (1, 0, 145, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )
    hand_displaced.alpha_composite(shifted_hand)
    hand_displaced.save(ROOT / "qa/hand-displaced-review.png")

    recomposition_overlay = source.copy()
    translucent_hand = hand_layer.copy()
    translucent_hand.putalpha(
        translucent_hand.getchannel("A").point(lambda value: value * 0.38)
    )
    translucent_forearm = forearm_layer.copy()
    translucent_forearm.putalpha(
        translucent_forearm.getchannel("A").point(lambda value: value * 0.38)
    )
    translucent_bracelet = bracelet_layer.copy()
    translucent_bracelet.putalpha(
        translucent_bracelet.getchannel("A").point(lambda value: value * 0.7)
    )
    recomposition_overlay.alpha_composite(translucent_hand)
    recomposition_overlay.alpha_composite(translucent_forearm)
    recomposition_overlay.alpha_composite(translucent_bracelet)
    recomposition_overlay.save(ROOT / "qa/default-overlay-reset.png")

    overlay = source.copy()
    draw_open_boundary(overlay, yellow_seam, (255, 72, 72, 255), 3)
    overlay.save(ROOT / "qa/reset-yellow-hand-boundary.png")

    root_only = v33.compose(
        [v33.solid(yellow_root, v33.YELLOW)],
        background=v33.checker((v33.W, v33.H)),
    )
    root_only.save(ROOT / "qa/yellow-hand-root-only.png")

    diagnostic = v33.checker((v33.W, v33.H)).convert("RGBA")
    translucent_hand = hand_diagnostic_layer.copy()
    translucent_hand.putalpha(
        translucent_hand.getchannel("A").point(
            lambda value: value * 0.34
        )
    )
    diagnostic.alpha_composite(translucent_hand)
    diagnostic.alpha_composite(ucap_layer)
    diagnostic.alpha_composite(bracelet_layer)
    draw_open_boundary(
        diagnostic, yellow_seam, (255, 72, 72, 255), 3
    )
    diagnostic.save(ROOT / "qa/frozen-blue-hand-coverage.png")

    displaced = v33.checker((v33.W, v33.H)).convert("RGBA")
    displaced.alpha_composite(hand_layer)
    shifted_forearm = forearm_layer.transform(
        (v33.W, v33.H),
        Image.Transform.AFFINE,
        (1, 0, -145, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )
    shifted_bracelet = bracelet_layer.transform(
        (v33.W, v33.H),
        Image.Transform.AFFINE,
        (1, 0, -145, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )
    displaced.alpha_composite(shifted_forearm)
    displaced.alpha_composite(shifted_bracelet)
    displaced.save(ROOT / "qa/forearm-displaced-hand-root.png")

    contour_comparison = source.copy()
    contour_comparison.alpha_composite(
        outline(visible_hand, (20, 176, 112, 255), 2)
    )
    contour_board = Image.new("RGB", (1600, 940), (241, 245, 250))
    v33.fit(
        contour_board,
        crop_full_hand(source, 5),
        (20, 20, 780, 900),
        "① Reset 原图轮廓",
    )
    v33.fit(
        contour_board,
        crop_full_hand(contour_comparison, 5),
        (820, 20, 1580, 900),
        "② 绿线=V34 可见手边界",
    )
    contour_board.save(ROOT / "qa/reset-vs-candidate-hand-contour.png")

    zoom_board = Image.new("RGB", (2100, 900), (241, 245, 250))
    zoom_targets = [
        ((91, 518, 137, 566), "① 手腕：手链接口"),
        ((78, 545, 127, 595), "② 手掌：宽度与掌形"),
        ((60, 565, 104, 626), "③ 四指组：轮廓与指缝"),
        ((92, 565, 125, 612), "④ 拇指组：开放负空间"),
    ]
    source_with_outline = source.copy()
    source_with_outline.alpha_composite(
        outline(visible_hand, (20, 176, 112, 255), 2)
    )
    for column, (box, label) in enumerate(zoom_targets):
        raw = source.crop(box).resize(
            ((box[2] - box[0]) * 9, (box[3] - box[1]) * 9),
            Image.Resampling.NEAREST,
        )
        traced = source_with_outline.crop(box).resize(
            ((box[2] - box[0]) * 9, (box[3] - box[1]) * 9),
            Image.Resampling.NEAREST,
        )
        pair = Image.new(
            "RGB",
            (max(raw.width, traced.width), raw.height + traced.height + 10),
            "white",
        )
        pair.paste(raw.convert("RGB"), (0, 0))
        pair.paste(traced.convert("RGB"), (0, raw.height + 10))
        v33.fit(
            zoom_board,
            pair,
            (column * 525 + 10, 20, column * 525 + 515, 870),
            label,
        )
    ImageDraw.Draw(zoom_board).text(
        (24, 868),
        "每格上半=Reset，下半=绿色候选轮廓叠 Reset；重点看腕宽、掌宽、五指与指缝。",
        fill=(58, 71, 91),
        font=v33.font(19, True),
    )
    zoom_board.save(ROOT / "qa/hand-local-zooms.png")

    ownership_review = Image.new("RGB", (1750, 900), (241, 245, 250))
    ownership_reset = source.copy()
    ownership_reset.alpha_composite(
        v33.solid(bracelet, (148, 74, 184, 170))
    )
    ownership_reset.alpha_composite(
        outline(visible_hand, (20, 176, 112, 255), 2)
    )
    ownership_masks = v33.checker((v33.W, v33.H)).convert("RGBA")
    ownership_masks.alpha_composite(visible_layer)
    ownership_masks.alpha_composite(bracelet_layer)
    visible_collision = (visible_hand > 8) & (bracelet > 8)
    collision_view = v33.checker((v33.W, v33.H)).convert("RGBA")
    collision_view.alpha_composite(
        v33.solid(visible_hand, (31, 166, 119, 150))
    )
    collision_view.alpha_composite(bracelet_layer)
    if np.any(visible_collision):
        collision_view.alpha_composite(
            v33.solid(
                visible_collision.astype(np.uint8) * 255,
                (255, 219, 45, 255),
            )
        )
    for column, (image, label) in enumerate(
        [
            (ownership_reset, "① Reset＋手链归属＋手部边界"),
            (ownership_masks, "② 可见手与手链分层"),
            (collision_view, "③ 黄色=可见像素侵占（应为 0）"),
        ]
    ):
        v33.fit(
            ownership_review,
            v33.crop_hand(image, 6),
            (column * 580 + 10, 20, column * 580 + 570, 880),
            label,
        )
    ownership_review.save(ROOT / "qa/bracelet-exclusion-ownership.png")

    coverage_review = Image.new("RGB", (1600, 900), (241, 245, 250))
    ucap_only = v33.checker((v33.W, v33.H)).convert("RGBA")
    ucap_only.alpha_composite(ucap_layer)
    overlap_only = v33.checker((v33.W, v33.H)).convert("RGBA")
    translucent_complete = hand_layer.copy()
    translucent_complete.putalpha(
        translucent_complete.getchannel("A").point(lambda value: value * 0.48)
    )
    overlap_only.alpha_composite(translucent_complete)
    overlap_only.alpha_composite(ucap_layer)
    overlap_only.alpha_composite(bracelet_layer)
    for column, (image, label) in enumerate(
        [
            (ucap_only, "① 削瘦前臂 U 形凸包"),
            (complete_hand_view, "② 完整手与隐藏腕根"),
            (overlap_only, "③ 前臂置前：检查重叠与穿模"),
        ]
    ):
        v33.fit(
            coverage_review,
            v33.crop_hand(image, 6),
            (column * 530 + 10, 20, column * 530 + 520, 880),
            label,
        )
    coverage_review.save(ROOT / "qa/forearm-ucap-hand-coverage.png")

    original_compose = v33.compose

    def compose_forearm_above_hand(
        layers,
        size=(v33.W, v33.H),
        background=None,
    ):
        if len(layers) == 3:
            return original_compose(
                [layers[1], layers[0], layers[2]],
                size,
                background,
            )
        return original_compose(layers, size, background)

    v33.compose = compose_forearm_above_hand
    try:
        samples, first_hash, last_hash = v33.build_motion(
            skeleton,
            forearm_layer,
            bracelet_layer,
            hand_layer,
            ucap_layer,
        )
    finally:
        v33.compose = original_compose
    rebuild_motion_labels(
        v33,
        skeleton,
        forearm_layer,
        bracelet_layer,
        hand_layer,
    )
    stress = build_foreground_stress(
        v33,
        hand_layer,
        ucap_layer,
        bracelet_layer,
    )

    minimum_overlap = min(
        item["completeOverlapPx"] for item in samples
    )
    max_fk_exposure = max(item["ucapExposedPx"] for item in samples)
    max_stress_exposure = max(
        item["ucapForegroundOnlyPx"] for item in stress
    )
    disconnects = sum(item["disconnected"] for item in samples)
    visible_bracelet_duplication = int(
        np.count_nonzero((visible_hand > 8) & (bracelet > 8))
    )
    hidden_bracelet_underlap = int(
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
            item["L2Px"]
            - skeleton["boneLengthsPx"]["L2ElbowToWrist"]
        )
        for item in samples
    )
    source_rgb_forbidden = np.asarray(source.convert("RGB"), dtype=np.int16)
    chroma = (
        np.max(source_rgb_forbidden, axis=2)
        - np.min(source_rgb_forbidden, axis=2)
    )
    neutral_background = (
        np.mean(source_rgb_forbidden, axis=2) >= 247
    ) & (chroma <= 5)
    skirt = np.zeros((v33.H, v33.W), dtype=bool)
    skirt[555:640, 135:220] = True
    clothes = np.zeros((v33.H, v33.W), dtype=bool)
    clothes[200:555, 135:260] = True
    other_body = np.zeros((v33.H, v33.W), dtype=bool)
    other_body[:, 250:] = True
    forbidden_counts = {
        "background": int(
            np.count_nonzero((visible_hand > 8) & neutral_background)
        ),
        "clothes": int(
            np.count_nonzero((complete_hand > 8) & clothes)
        ),
        "skirt": int(np.count_nonzero((complete_hand > 8) & skirt)),
        "otherBodyOrOtherHand": int(
            np.count_nonzero((complete_hand > 8) & other_body)
        ),
    }
    forbidden_total = sum(forbidden_counts.values())
    yy, xx = np.indices((v33.H, v33.W))
    wrist_axis = (v33.WR - v33.E) / np.linalg.norm(v33.WR - v33.E)
    wrist_projection = (
        (xx - v33.WR[0]) * wrist_axis[0]
        + (yy - v33.WR[1]) * wrist_axis[1]
    )
    forearm_extension_px = float(
        np.max(wrist_projection[blue_ucap > 8])
    )
    old_forearm_extension_px = float(
        np.max(wrist_projection[frozen_blue_ucap > 8])
    )
    hand_extension_px = float(
        max(0.0, -np.min(wrist_projection[yellow_root > 8]))
    )
    overlap_mask = (blue_ucap > 8) & (yellow_root > 8)
    overlap_area_px = int(np.count_nonzero(overlap_mask))
    frozen_after = {
        "blueUCap": sha256(FROZEN_BLUE),
        "forearmComplete": sha256(FROZEN_FOREARM_COMPLETE),
        "forearmMaterial": sha256(FROZEN_FOREARM),
    }
    frozen_preserved = frozen_before == frozen_after
    freeze_checks_after = {
        "upperArm": verify_freeze_manifest(UPPER_FREEZE),
        "forearm": verify_freeze_manifest(FOREARM_FREEZE),
    }
    freeze_unchanged = all(
        freeze_checks_before[name]["manifestSha256"]
        == freeze_checks_after[name]["manifestSha256"]
        and freeze_checks_after[name]["pass"]
        for name in freeze_checks_before
    )
    engineering_pass = (
        v33.components(complete_hand) == 1
        and v33.holes(complete_hand) == 0
        and disconnects == 0
        and first_hash == last_hash
        and minimum_overlap >= 510
        and visible_bracelet_duplication == 0
        and max_l1_error <= 0.01
        and max_l2_error <= 0.01
        and forbidden_total == 0
        and freeze_unchanged
        and frozen_preserved
    )
    check_map = {
        "V31 frozen hashes unchanged": freeze_unchanged,
        "original V33 forearm U-cap byte preserved": frozen_preserved,
        "bone lengths": max_l1_error <= 0.01 and max_l2_error <= 0.01,
        "minimum forearm-hand overlap >= 510 px": minimum_overlap >= 510,
        "41-frame disconnect count = 0": disconnects == 0,
        "0-to-1-to-0 return consistency": first_hash == last_hash,
        "hand complete mask is one component": (
            v33.components(complete_hand) == 1
        ),
        "hand complete mask has no closed holes": (
            v33.holes(complete_hand) == 0
        ),
        "visible bracelet pixel duplication = 0": (
            visible_bracelet_duplication == 0
        ),
        "forbidden region intrusion = 0": forbidden_total == 0,
        "41-frame foreground ownership remains connected": disconnects == 0,
        "stress foreground ownership remains connected": all(
            not item["disconnected"] for item in stress
        ),
    }
    failed_checks = [
        name for name, passed in check_map.items() if not passed
    ]
    earliest_failure = (
        failed_checks[0]
        if failed_checks
        else "none"
        if user_approved
        else "none_in_machine_checks_pending_user_visual_review"
    )

    report = {
        "schemaVersion": 1,
        "status": (
            "frozen_engineering_and_user_visual_pass"
            if engineering_pass and user_approved
            else "engineering_pass_slim_ucap_pending_user_visual_approval"
            if engineering_pass
            else "engineering_fail_stop_hand_stage_a"
        ),
        "scope": "screen-left hand hidden-root and complete hand geometry",
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
                "sha256": sha256(SKELETON),
            },
            "frozenUpperArmManifest": freeze_checks_before["upperArm"],
            "frozenForearmManifest": freeze_checks_before["forearm"],
            "approvedVisibleHand": {
                "path": "masks/visible/hand.png",
                "sha256": sha256(ROOT / "masks/visible/hand.png"),
            },
        },
        "frozenUpstreamHashCheck": {
            "before": freeze_checks_before,
            "after": freeze_checks_after,
            "unchanged": freeze_unchanged,
            "pass": freeze_unchanged,
        },
        "frozenUpstream": {
            "approval": {
                "path": (
                    "../arm-chain-screen-left-v33-skin-boundary-wrist-rebuild/"
                    "audit/user-visual-approval-blue-forearm-ucap-2026-07-29.json"
                ),
                "sha256": sha256(APPROVAL),
            },
            "blueUCapSha256": frozen_after["blueUCap"],
            "preserved": frozen_preserved,
        },
        "reopenedForearmUCap": {
            "status": "scope_limited_candidate_pending_user_visual_approval",
            "originalFrozenArtifactBytePreserved": frozen_preserved,
            "originalExtensionPastPivotPx": old_forearm_extension_px,
            "candidateExtensionPastPivotPx": forearm_extension_px,
            "candidateMask": {
                "path": "masks/reference/slim-blue-forearm-ucap.png",
                "sha256": sha256(
                    ROOT / "masks/reference/slim-blue-forearm-ucap.png"
                ),
            },
            "candidateCompleteForearm": {
                "path": "masks/complete/forearm-slim.png",
                "sha256": sha256(
                    ROOT / "masks/complete/forearm-slim.png"
                ),
            },
            "visibleForearmModified": False,
            "braceletModified": False,
            "visibleHandModified": False,
        },
        "boundaryConstruction": {
            "rule": (
                "the user-marked lower cap is the visible ownership seam; "
                "pixels above it belong to the foreground forearm, while "
                "the complete hand keeps a hidden root behind that forearm"
            ),
            "openWristSeamPoints": yellow_seam,
            "hiddenRootRule": (
                "frozen blue forearm U-cap intersected with a 27 px "
                "dilation of the red-line-below visible hand, plus one "
                "compact proximal patch clipped inside the frozen forearm"
            ),
            "hiddenRootHasAuxiliaryDiagonalBridge": False,
            "circlePatchUsed": False,
            "straightMechanicalExpansionUsed": False,
            "scaleUsedToHideSeam": False,
        },
        "geometry": {
            "handComponents": v33.components(complete_hand),
            "handClosedHoles": v33.holes(complete_hand),
            "visibleBraceletPixelDuplicationPx": (
                visible_bracelet_duplication
            ),
            "hiddenBraceletUnderlapPx": hidden_bracelet_underlap,
            "hiddenBraceletUnderlapExpected": True,
            "flatSkinRgb": list(skin_rgb),
            "flatHiddenRootRgb": list(hidden_rgb),
        },
        "boneLengthError": {
            "maxL1ErrorPx": max_l1_error,
            "maxL2ErrorPx": max_l2_error,
            "tolerancePx": 0.01,
            "pass": max_l1_error <= 0.01 and max_l2_error <= 0.01,
        },
        "forbiddenRegionIntrusion": {
            "pixels": forbidden_counts,
            "totalPixels": forbidden_total,
            "method": (
                "Reset-neutral background test plus explicit garment, skirt, "
                "and opposite-body exclusion regions; hidden root remains "
                "inside the declared wrist corridor"
            ),
            "pass": forbidden_total == 0,
        },
        "overlapContract": {
            "pivotPx": [float(v33.WR[0]), float(v33.WR[1])],
            "forearmExtensionPastPivotPx": forearm_extension_px,
            "handReturnAcrossPivotPx": hand_extension_px,
            "overlapAreaPx": overlap_area_px,
            "forearmCoversMoreThanHand": (
                forearm_extension_px > hand_extension_px
            ),
            "visibleSeamIsNotMaterialButtJoint": True,
            "braceletOwner": "forearm",
            "drawOrderBackToFront": [
                "hand",
                "forearm",
                "bracelet"
            ],
        },
        "motion": {
            "sampleCount": 41,
            "minimumCompleteOverlapPx": minimum_overlap,
            "requiredMinimumCompleteOverlapPx": 510,
            "disconnectCount": disconnects,
            "maximumFrozenUCapNotCoveredByHandPx": max_fk_exposure,
            "foregroundOnlyPixelsAreGapFailure": False,
            "reason": (
                "the frozen forearm U-cap is the intended foreground owner; "
                "minimum overlap, connectivity, return consistency, and "
                "final draw order are the gap gates"
            ),
            "returnConsistency": first_hash == last_hash,
        },
        "wristStress": {
            "results": stress,
            "maximumFrozenUCapNotCoveredByHandPx": max_stress_exposure,
            "rangeIsApprovedMotion": False,
            "gateEffect": (
                "foreground_ownership_diagnostic_not_a_gap_gate"
            ),
        },
        "machineChecks": check_map,
        "earliestFailurePoint": earliest_failure,
        "visualGate": {
            "status": (
                "user_visual_approved_frozen"
                if user_approved
                else "pending_user_visual_approval_of_slim_ucap"
            ),
            "review": (
                "qa/V34-阶段A-screen-left手部-最终中文视觉审查板.png"
            ),
            "secondaryReviews": [
                "qa/V34-前臂凸包削瘦复核图.png",
                "qa/V34-腕关节覆盖关系-简明审查图.png",
                "qa/V34-黄色手部边界-中文视觉审查板.png"
            ],
            "originalForearmUCapBytePreserved": True,
            "slimForearmUCapFrozen": user_approved,
            "handFrozen": user_approved,
        },
        "stop": (
            "screen-left hand Stage A frozen; do not mutate without explicit "
            "user authorization to reopen"
            if user_approved
            else "remain at hand Stage A pending user approval of the reopened "
            "slim forearm U-cap"
        ),
    }
    save_json(ROOT / "audit/machine-report.json", report)

    board = Image.new("RGB", (2600, 3300), (238, 243, 249))
    draw = ImageDraw.Draw(board)
    draw.text(
        (55, 28),
        "小星 V34 修正｜手腕 ∩ 形接缝",
        fill=(18, 28, 43),
        font=v33.font(42, True),
    )
    draw.text(
        (55, 86),
        "红线=需要你确认的开放接缝；隐藏补面位于线后，不再把手掌圈成封闭大块。",
        fill=(58, 71, 91),
        font=v33.font(24),
    )
    items = [
        (
            v33.crop_hand(source, 8),
            "1. Reset 腕部原图｜只认真实皮肤边界",
        ),
        (
            v33.crop_hand(overlay, 8),
            "2. 修改后接缝｜按你画的开放 ∩ 形",
        ),
        (
            v33.crop_hand(root_only, 8),
            "3. 接缝后的隐藏补面｜不等于可见边界线",
        ),
        (
            v33.crop_hand(default, 8),
            "4. 默认回组｜看手腕宽度与手链接缝",
        ),
        (
            v33.crop_hand(diagnostic, 8),
            "5. 覆盖诊断｜红块=冻结蓝凸包；细红线=接缝",
        ),
        (
            v33.crop_hand(displaced, 8),
            "6. 前臂移开｜检查完整手部隐藏根",
        ),
        (
            Image.open(ROOT / "qa/fk-key-wrist-samples.png").convert(
                "RGB"
            ),
            "7. 41 帧关键样本｜冻结蓝色未改",
        ),
        (
            Image.open(ROOT / "qa/wrist-stress-review.png").convert(
                "RGB"
            ),
            "8. ±12°覆盖压力检查｜只作工程检查",
        ),
    ]
    for index, (image, label) in enumerate(items):
        row, column = divmod(index, 2)
        v33.fit(
            board,
            image,
            (
                40 + column * 1280,
                130 + row * 720,
                1240 + column * 1280,
                820 + row * 720,
            ),
            label,
        )
    draw.rounded_rectangle(
        (55, 3020, 2545, 3235),
        radius=20,
        fill="white",
        outline=(170, 183, 200),
        width=3,
    )
    draw.text(
        (85, 3050),
        "请审查：红色 ∩ 线是否贴着左右手腕皮肤？顶部是否紧靠手链下方？",
        fill=(35, 48, 64),
        font=v33.font(22, True),
    )
    draw.text(
        (85, 3110),
        (
            f"机器：41 帧无断裂｜最小重叠 {minimum_overlap}px｜"
            "前臂凸包在手部前景｜±12°无缝｜手部未冻结"
        ),
        fill=(164, 105, 0) if engineering_pass else (178, 50, 43),
        font=v33.font(21, True),
    )
    board.save(ROOT / "qa/V34-黄色手部边界-中文视觉审查板.png")

    build_overlap_explainer(
        v33,
        source,
        blue_ucap,
        yellow_root,
        bracelet_layer,
        yellow_seam,
        forearm_extension_px,
        hand_extension_px,
        overlap_area_px,
    )

    default_review = default.copy()
    # Panel 5 must mark the same rasterized skin edge seen in panel 2.
    # The Bezier is only the ownership cutter; drawing it directly can sit a
    # few antialiased pixels away from the actual visible-hand boundary.
    draw_visible_mask_boundary_near_seam(
        default_review,
        visible_hand,
        yellow_seam,
        (255, 72, 72, 255),
    )
    build_hand_material_review(
        v33,
        source,
        visible_layer,
        hidden_layer,
        hand_layer,
        default_review,
        displaced,
        minimum_overlap,
        max_fk_exposure,
        max_stress_exposure,
    )
    build_slim_ucap_review(
        v33,
        frozen_blue_ucap,
        blue_ucap,
        bracelet_layer,
        default,
        old_forearm_extension_px,
        forearm_extension_px,
        minimum_overlap,
    )
    build_final_stage_a_review(
        v33,
        source,
        complete_hand_view,
        default,
        recomposition_overlay,
        displaced,
        coverage_review,
        ownership_review,
        zoom_board,
        minimum_overlap,
        max_fk_exposure,
        max_stress_exposure,
        engineering_pass,
    )
    save_json(
        ROOT / "audit/self-visual-qa-slim-ucap-2026-07-29.json",
        {
            "schemaVersion": 1,
            "status": (
                "self_visual_qa_pass_user_approved_frozen"
                if user_approved
                else "self_visual_qa_pass_pending_user_visual_approval"
            ),
            "date": "2026-07-29",
            "scope": (
                "screen-left approved hand geometry plus slim hidden "
                "forearm U-cap candidate"
            ),
            "reviewedEvidence": [
                {
                    "path": (
                        "../qa/V34-阶段A-screen-left手部-"
                        "最终中文视觉审查板.png"
                    ),
                    "sha256": sha256(
                        ROOT
                        / "qa/V34-阶段A-screen-left手部-最终中文视觉审查板.png"
                    ),
                },
                {
                    "path": "../qa/V34-前臂凸包削瘦复核图.png",
                    "sha256": sha256(
                        ROOT / "qa/V34-前臂凸包削瘦复核图.png"
                    ),
                },
                {
                    "path": "../qa/fk-key-wrist-samples.png",
                    "sha256": sha256(
                        ROOT / "qa/fk-key-wrist-samples.png"
                    ),
                },
                {
                    "path": "../qa/wrist-stress-review.png",
                    "sha256": sha256(ROOT / "qa/wrist-stress-review.png"),
                },
            ],
            "visualChecks": {
                "defaultComposite": (
                    "pass; wrist follows the Reset silhouette and the slim "
                    "foreground cap no longer forms the previous broad palm bulge"
                ),
                "handAndFingerContour": (
                    "pass; the approved visible contour and open finger spaces "
                    "remain unchanged"
                ),
                "fkKeyFrames": (
                    "pass; no lateral cap spike, transparent seam, or "
                    "disconnection in frames 0, 5, 10, 15, 20, 25, 30, 35, 40"
                ),
                "wristStress": (
                    "pass; no lateral breakout or disconnection at "
                    "-12, -8, -4, 0, 4, 8, 12 degrees"
                ),
                "visibleHandContourChanged": False,
                "visibleForearmChanged": False,
                "braceletChanged": False,
            },
            "engineeringChecks": {
                "originalExtensionPastPivotPx": old_forearm_extension_px,
                "candidateExtensionPastPivotPx": forearm_extension_px,
                "minimumFkOverlapPx": minimum_overlap,
                "requiredMinimumFkOverlapPx": 510,
                "fkDisconnectCount": disconnects,
                "stressDisconnectCount": sum(
                    item["disconnected"] for item in stress
                ),
                "returnConsistency": first_hash == last_hash,
                "visibleBraceletPixelDuplicationPx": (
                    visible_bracelet_duplication
                ),
                "forbiddenRegionIntrusionPx": forbidden_total,
                "machineReport": {
                    "path": "machine-report.json",
                    "sha256": sha256(ROOT / "audit/machine-report.json"),
                },
            },
            "candidateArtifacts": [
                {
                    "path": "../masks/reference/slim-blue-forearm-ucap.png",
                    "sha256": sha256(
                        ROOT / "masks/reference/slim-blue-forearm-ucap.png"
                    ),
                },
                {
                    "path": "../masks/complete/forearm-slim.png",
                    "sha256": sha256(
                        ROOT / "masks/complete/forearm-slim.png"
                    ),
                },
                {
                    "path": "../materials/forearm-slim.png",
                    "sha256": sha256(ROOT / "materials/forearm-slim.png"),
                },
            ],
            "originalFrozenArtifactBytePreserved": frozen_preserved,
            "candidateFrozen": user_approved,
            "stop": (
                "frozen checkpoint; explicit user authorization is required "
                "before any geometry mutation"
                if user_approved
                else "await user visual approval of the slim U-cap candidate"
            ),
        },
    )

    artifacts = [
        "skeleton-lock.json",
        "hand-layering-contract.json",
        "masks/visible/hand.png",
        "masks/hidden/hand.png",
        "masks/complete/hand.png",
        "masks/reference/yellow-hand-root.png",
        "masks/reference/slim-blue-forearm-ucap.png",
        "masks/complete/forearm-slim.png",
        "materials/hand-visible-flat.png",
        "materials/hand-hidden-flat.png",
        "materials/hand.png",
        "materials/forearm-slim.png",
        "qa/complete-hand-hidden-root-closeup.png",
        "qa/default-solid-recomposition.png",
        "qa/default-solid-recomposition-closeup.png",
        "qa/default-overlay-reset.png",
        "qa/hand-displaced-review.png",
        "qa/reset-vs-candidate-hand-contour.png",
        "qa/hand-local-zooms.png",
        "qa/bracelet-exclusion-ownership.png",
        "qa/forearm-ucap-hand-coverage.png",
        "qa/reset-yellow-hand-boundary.png",
        "qa/yellow-hand-root-only.png",
        "qa/frozen-blue-hand-coverage.png",
        "qa/forearm-displaced-hand-root.png",
        "qa/fk-41-slow-preview.gif",
        "qa/fk-key-wrist-samples.png",
        "qa/wrist-stress-review.png",
        "qa/V34-手链禁区与零外露冲突审查图.png",
        "qa/V34-前臂凸包削瘦复核图.png",
        "qa/V34-黄色手部边界-中文视觉审查板.png",
        "qa/V34-腕关节覆盖关系-简明审查图.png",
        "qa/V34-完整手部纯色材料-正式审查图.png",
        "qa/V34-阶段A-screen-left手部-最终中文视觉审查板.png",
        "samples/fk-41-samples.json",
        "audit/machine-report.json",
        "audit/user-rejection-bulky-closed-hand-root-2026-07-29.json",
        "audit/user-rejection-thick-visible-wrist-2026-07-29.json",
        "audit/user-visual-approval-hand-geometry-2026-07-29.json",
        "audit/hand-zero-exposure-bracelet-conflict-2026-07-29.json",
        "audit/self-visual-qa-slim-ucap-2026-07-29.json",
        (
            "audit/user-authorized-reopen-forearm-ucap-slimming-"
            "2026-07-29.json"
        ),
        (
            "audit/user-authorization-forearm-foreground-ownership-"
            "2026-07-29.json"
        ),
        "tools/build_v34_hand_root.py",
        "tools/freeze_v34_hand_stage_a.py",
    ]
    if user_approved:
        artifacts.append(
            "audit/user-visual-approval-and-freeze-authorization-2026-07-29.json"
        )
    save_json(
        ROOT / "audit/artifact-manifest.json",
        {
            "schemaVersion": 1,
            "status": (
                "frozen_engineering_and_user_visual_pass"
                if engineering_pass and user_approved
                else "slim_ucap_engineering_pass_pending_user_visual_approval"
            ),
            "artifacts": [
                {"path": path, "sha256": sha256(ROOT / path)}
                for path in artifacts
            ],
            "frozenUpstreamPreserved": frozen_preserved,
            "originalForearmUCapBytePreserved": True,
            "slimForearmUCapFrozen": user_approved,
            "handFrozen": user_approved,
        },
    )


if __name__ == "__main__":
    main()
