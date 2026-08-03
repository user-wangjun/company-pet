from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
XIAOXING = ROOT.parents[1]
V27 = XIAOXING / "validation/arm-chain-screen-left-v27-source-traced-layering"
V29 = XIAOXING / "validation/arm-chain-screen-left-v29-bilateral-dual-anchor-sleeve"
RIGHT = (
    XIAOXING
    / "validation/arm-chain-screen-right-v5-hidden-upper-arm"
    / "complete-sleeve-final"
)
SOURCE_COLOR = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
V25_APPROVAL = (
    XIAOXING
    / "validation/arm-chain-screen-left-v25-shoulder-joint-correction"
    / "audit/user-visual-approval-2026-07-28.json"
)
RIGHT_GEOMETRY = RIGHT / "inputs/sleeve-complete-geometry-r9.png"
RIGHT_TEXTURE = RIGHT / "materials/sleeve-complete-textured-r1.png"
RIGHT_APPROVAL = RIGHT / "audit/user-visual-approval-geometry-2026-07-25.json"

W, H = 512, 1086
S = np.array((170.0, 251.0))
E = np.array((147.0, 405.0))
WR = np.array((115.0, 529.0))
ORDER = ["upper_arm", "forearm", "hand", "sleeve"]
COLORS = {
    "upper_arm": (229, 89, 78, 255),
    "forearm": (243, 155, 44, 255),
    "hand": (32, 167, 119, 255),
    "sleeve": (40, 112, 194, 255),
}
RIGHT_REGISTER_SX = 1.12
RIGHT_REGISTER_TX = -31.0
RIGHT_REGISTER_SY = (416.0 - 220.0) / (398.0 - 221.0)
RIGHT_REGISTER_TY = 220.0 - RIGHT_REGISTER_SY * 221.0


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


v29 = load_module(
    V29 / "tools/build_v29_bilateral_dual_anchor.py", "v29_builder"
)


def save_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size, bold=False):
    for path in (
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def cubic(p0, p1, p2, p3, count=48):
    ts = np.linspace(0.0, 1.0, count)
    return np.array(
        [
            (1 - t) ** 3 * p0
            + 3 * (1 - t) ** 2 * t * p1
            + 3 * (1 - t) * t**2 * p2
            + t**3 * p3
            for t in ts
        ]
    )


def build_fresh_left_sleeve():
    # Kept only as historical evidence for the rejected first V30 candidate.
    # The corrected candidate below uses the approved right geometry itself as
    # the garment-shape authority; hand-drawn cubic approximation is forbidden.
    raise RuntimeError("rejected V30 cubic sleeve must not be reused")


def aligned_right_complete():
    alpha = np.array(
        Image.open(RIGHT_GEOMETRY).convert("RGBA").getchannel("A")
    )
    mirrored = np.ascontiguousarray(alpha[:, ::-1])
    return cv2.warpAffine(
        mirrored,
        np.float32(
            [
                [RIGHT_REGISTER_SX, 0, RIGHT_REGISTER_TX],
                [0, RIGHT_REGISTER_SY, RIGHT_REGISTER_TY],
            ]
        ),
        (W, H),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def hidden_from_registered_right(visible, registered_right):
    # The source-visible outer edge and cuff face the background and are final
    # silhouette boundaries. Hidden sleeve may only continue on the occluded
    # inner/right side, plus the shoulder cap above the first visible row.
    candidate = cv2.bitwise_and(
        registered_right, cv2.bitwise_not(visible)
    )
    hidden = np.zeros_like(candidate)
    visible_rows = np.where(np.any(visible > 8, axis=1))[0]
    first_visible = int(visible_rows.min())
    last_visible = int(visible_rows.max())
    hidden[:first_visible] = candidate[:first_visible]
    for y in range(first_visible, last_visible + 1):
        xs = np.where(visible[y] > 8)[0]
        if not len(xs):
            continue
        inner_edge = int(xs.max())
        hidden[y, inner_edge + 1 :] = candidate[y, inner_edge + 1 :]
    return hidden


def partition_complete_by_inner_occlusion(complete):
    # Only a narrow strip on the torso-facing/right edge is occluded at rest.
    # The strip tapers from the hair-covered shoulder toward the open cuff.
    hidden = np.zeros_like(complete)
    ys = np.where(np.any(complete > 8, axis=1))[0]
    top = int(ys.min())
    bottom = int(ys.max())
    shoulder_peak_y = min(270, bottom)
    for y in range(top, bottom + 1):
        xs = np.where(complete[y] > 8)[0]
        if not len(xs):
            continue
        if y <= shoulder_peak_y:
            progress = (y - top) / max(1, shoulder_peak_y - top)
            desired_width = int(round(4.0 + 14.0 * progress))
        elif y <= 290:
            progress = (y - shoulder_peak_y) / max(
                1, 290 - shoulder_peak_y
            )
            desired_width = int(round(18.0 + 4.0 * progress))
        else:
            progress = (y - 290) / max(1, bottom - 290)
            desired_width = int(round(22.0 - 6.0 * progress))
        strip_width = min(
            desired_width,
            max(3, len(xs) // 3),
            len(xs),
        )
        hidden[y, xs[-strip_width:]] = complete[y, xs[-strip_width:]]
    visible = cv2.bitwise_and(complete, cv2.bitwise_not(hidden))
    return visible, hidden


def constrain_shoulder_cap_to_source(complete, source_visible):
    # Do not let the mirrored template create a shoulder bump above or outside
    # the source garment. Follow the source shoulder rows, then blend back into
    # the registered template by y=270 while retaining inner-side underlap.
    constrained = complete.copy()
    source_rows = np.where(np.any(source_visible > 8, axis=1))[0]
    first_source = int(source_rows.min())
    blend_end = 270
    constrained[:first_source] = 0
    for y in range(first_source, blend_end + 1):
        source_xs = np.where(source_visible[y] > 8)[0]
        template_xs = np.where(complete[y] > 8)[0]
        if not len(source_xs) or not len(template_xs):
            continue
        progress = (y - first_source) / max(1, blend_end - first_source)
        left = int(
            round(
                source_xs.min()
                + (template_xs.min() - source_xs.min()) * progress
            )
        )
        right_extra = 6.0 + (
            template_xs.max() - source_xs.max() - 6.0
        ) * progress
        right = int(round(source_xs.max() + max(3.0, right_extra)))
        constrained[y] = 0
        constrained[y, left : right + 1] = 255
    return clean_source_visible(constrained), first_source


def source_registered_visible_ownership(raw):
    # The authoritative source shows a folded inner sleeve edge: it runs from
    # the shoulder toward the underarm, then diagonally down-right to the inner
    # cuff. The broad color classifier continued past that edge into the torso.
    envelope = np.zeros((H, W), dtype=np.uint8)
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
            (180, 405),
            (176, 390),
            (170, 375),
            (164, 360),
            (158, 345),
            (152, 330),
            (146, 315),
            (140, 300),
            (130, 289),
            (136, 273),
            (143, 258),
            (151, 244),
            (160, 232),
        ],
        dtype=np.int32,
    )
    cv2.fillPoly(envelope, [boundary], 255)
    return cv2.bitwise_and(raw, envelope), boundary


def clean_source_visible(raw):
    # Color tracing left small internal holes and cuff notches. They are not
    # garment openings, so keep the registered outer contour and fill its
    # interior into one closed visible material.
    binary = ((raw > 8).astype(np.uint8) * 255)
    binary = cv2.morphologyEx(
        binary,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        iterations=2,
    )
    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
    )
    filled = np.zeros_like(binary)
    cv2.drawContours(
        filled,
        [max(contours, key=cv2.contourArea)],
        -1,
        255,
        thickness=cv2.FILLED,
    )
    return filled


def checker_layer(mask, color):
    canvas = v29.v28.checker((W, H)).convert("RGBA")
    canvas.alpha_composite(
        v29.v28.solid(Image.fromarray(mask), color)
    )
    return canvas


def crop_large(image):
    return v29.v28.crop_scale(image, (70, 195, 215, 435), 4)


def labeled(board, image, box, label):
    x0, y0, x1, y1 = box
    area = Image.new("RGB", (x1 - x0, y1 - y0), "white")
    item = image.convert("RGBA")
    item.thumbnail((area.width, area.height - 48), Image.Resampling.LANCZOS)
    px = (area.width - item.width) // 2
    area.paste(item.convert("RGB"), (px, 0), item.getchannel("A"))
    ImageDraw.Draw(area).text(
        (8, area.height - 42),
        label,
        fill=(20, 28, 40),
        font=font(21, True),
    )
    board.paste(area, (x0, y0))


def main():
    for folder in ("materials", "masks", "samples", "qa", "audit"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)

    left_source_classifier = np.array(
        Image.open(V27 / "masks/visible/sleeve.png").convert("L")
    )
    right_aligned = aligned_right_complete()
    # The complete outline is one registered approved garment shape. Visible
    # and hidden ownership are an exact partition of that same mask; hidden is
    # restricted to a narrow torso-facing strip.
    complete, source_shoulder_top = constrain_shoulder_cap_to_source(
        clean_source_visible(right_aligned), left_source_classifier
    )
    visible_owned, hidden = partition_complete_by_inner_occlusion(complete)
    partition_union = np.maximum(visible_owned, hidden)
    partition_difference = int(
        np.count_nonzero((partition_union > 8) != (complete > 8))
    )

    complete_masks = {
        name: np.array(
            Image.open(V27 / f"masks/complete/{name}.png").convert("L")
        )
        for name in ORDER
    }
    complete_masks["sleeve"] = complete
    layers = {
        name: v29.v28.solid(
            v29.v28.antialiased(Image.fromarray(complete_masks[name])),
            COLORS[name],
        )
        for name in ORDER
    }
    for name, image in layers.items():
        image.save(ROOT / f"materials/{name}.png")
    for name, mask in {
        "sleeve-complete-fresh.png": complete,
        "sleeve-visible-owned.png": visible_owned,
        "sleeve-hidden-fresh.png": hidden,
        "visible-hidden-partition-union.png": partition_union,
        "right-complete-aligned-reference.png": right_aligned,
    }.items():
        Image.fromarray(mask).save(ROOT / f"masks/{name}")

    skeleton = json.loads(
        (V29 / "skeleton-lock.json").read_text(encoding="utf-8")
    )
    skeleton["status"] = "unchanged_from_user_approved_v25_for_v30"
    save_json(ROOT / "skeleton-lock.json", skeleton)

    overlap = int(
        np.count_nonzero((complete > 8) & (right_aligned > 8))
    )
    union = int(
        np.count_nonzero((complete > 8) | (right_aligned > 8))
    )
    iou = overlap / union
    contract = {
        "schemaVersion": 1,
        "status": "candidate_pending_user_visual_approval",
        "scope": "screen-left sleeve Stage A geometry only",
        "authority": {
            "v25ApprovedSkeletonSha256": sha256(V25_APPROVAL),
            "leftSourceVisibleSha256": sha256(
                V27 / "masks/visible/sleeve.png"
            ),
            "rightApprovedGeometrySha256": sha256(RIGHT_GEOMETRY),
            "rightApprovalSha256": sha256(RIGHT_APPROVAL),
        },
        "construction": {
            "method": (
                "register approved right sleeve alpha as the one complete mask, "
                "then partition a narrow torso-facing strip as hidden ownership"
            ),
            "rightRole": (
                "authoritative complete sleeve structure; texture is not copied"
            ),
            "rightMutation": "none",
            "leftShoulder": [170, 251],
            "rightRegistrationAffine": [
                [RIGHT_REGISTER_SX, 0.0, RIGHT_REGISTER_TX],
                [0.0, RIGHT_REGISTER_SY, RIGHT_REGISTER_TY],
            ],
            "ownershipCorrection": (
                "visible and hidden are an exact partition of the complete mask; "
                "hidden follows the user-marked garment edge: 4px at the cap, "
                "18px below the shoulder, 22px through the body-side turn, "
                "then 16px at the cuff"
            ),
            "shoulderConstraint": (
                "no complete-sleeve pixels above the first source-proven "
                "shoulder row; blend to registered right template by y=270"
            ),
        },
    }
    save_json(ROOT / "sleeve-geometry-contract.json", contract)

    right_outline = cv2.morphologyEx(
        (right_aligned > 8).astype(np.uint8) * 255,
        cv2.MORPH_GRADIENT,
        np.ones((3, 3), dtype=np.uint8),
    )
    current_outline = checker_layer(complete, COLORS["sleeve"])
    current_outline.alpha_composite(
        v29.v28.solid(Image.fromarray(right_outline), (235, 45, 45, 255))
    )
    ownership = v29.v28.checker((W, H)).convert("RGBA")
    ownership.alpha_composite(
        v29.v28.solid(Image.fromarray(visible_owned), (40, 112, 194, 255))
    )
    ownership.alpha_composite(
        v29.v28.solid(Image.fromarray(hidden), (211, 45, 135, 255))
    )

    rest1 = skeleton["restAnglesDeg"]["theta1"]
    rest2 = skeleton["restAnglesDeg"]["theta2"]
    target = skeleton["stageAQaMotion"]["target"]
    l1 = skeleton["boneLengthsPx"]["L1ShoulderToElbow"]
    l2 = skeleton["boneLengthsPx"]["L2ElbowToWrist"]
    torso_mask = np.zeros((H, W), dtype=np.uint8)
    cv2.fillPoly(
        torso_mask,
        [np.array([(166, 215), (346, 215), (362, 585), (137, 585)], dtype=np.int32)],
        255,
    )
    torso_context = Image.new("RGBA", (W, H), (238, 239, 235, 255))
    torso_context.putalpha(Image.fromarray(torso_mask))
    occluder = cv2.dilate(
        (hidden > 8).astype(np.uint8) * 255,
        np.ones((3, 3), dtype=np.uint8),
    )
    occluder[visible_owned > 8] = 0
    fixed_occluder = Image.new("RGBA", (W, H), (238, 239, 235, 255))
    fixed_occluder.putalpha(Image.fromarray(occluder))
    hidden_layer = v29.v28.solid(
        v29.v28.antialiased(Image.fromarray(hidden)), COLORS["sleeve"]
    )

    samples = []
    frames = []
    chosen = {}
    first_hash = None
    last_hash = None
    all_pass = True
    for index in range(41):
        j = index if index <= 20 else 40 - index
        progress = 0.5 * (1.0 - math.cos(math.pi * j / 20.0))
        theta1 = rest1 + (target["theta1"] - rest1) * progress
        theta2 = rest2 + (target["theta2"] - rest2) * progress
        d1 = theta1 - rest1
        new_e = v29.v28.point_at(S, l1, theta1)
        new_w = v29.v28.point_at(new_e, l2, theta1 + theta2)
        rest_global = math.degrees(
            math.atan2(WR[1] - E[1], WR[0] - E[0])
        )
        d2 = theta1 + theta2 - rest_global
        warped_sleeve, src_mesh, dst_mesh, weights = v29.warp_sleeve(
            layers["sleeve"], d1
        )
        warped_hidden, _, _, _ = v29.warp_sleeve(hidden_layer, d1)
        posed = {
            "upper_arm": v29.v28.rotate_translate(
                layers["upper_arm"], S, S, d1
            ),
            "forearm": v29.v28.rotate_translate(
                layers["forearm"], E, new_e, d2
            ),
            "hand": v29.v28.rotate_translate(
                layers["hand"],
                WR,
                new_w,
                d2 + target["wristLocal"] * progress,
            ),
            "sleeve": warped_sleeve,
        }
        pose = v29.composite(posed)
        digest = hashlib.sha256(pose.tobytes()).hexdigest()
        first_hash = digest if index == 0 else first_hash
        last_hash = digest if index == 40 else last_hash
        hidden_alpha = (
            hidden
            if abs(d1) < 1e-9
            else np.array(warped_hidden.getchannel("A"))
        )
        revealed = (hidden_alpha > 8) & (occluder <= 8)
        revealed_pixels = int(np.count_nonzero(revealed))
        context = torso_context.copy()
        context.alpha_composite(pose)
        context.alpha_composite(fixed_occluder)
        highlight = Image.new("RGBA", (W, H), (211, 45, 135, 0))
        highlight.putalpha(
            Image.fromarray(revealed.astype(np.uint8) * 210)
        )
        context.alpha_composite(highlight)
        alpha = np.array(warped_sleeve.getchannel("A"))
        components = (
            cv2.connectedComponents((alpha > 8).astype(np.uint8))[0] - 1
        )
        holes = v29.hole_count(alpha)
        overlap_px = v29.v28.overlap(
            warped_sleeve, posed["upper_arm"]
        )
        _, nx, ny = v29.mesh_points()
        min_strain, max_strain = v29.edge_strain(
            src_mesh, dst_mesh, nx, ny
        )
        fixed = weights <= 0.08
        anchor_drift = float(
            np.max(np.linalg.norm(dst_mesh[fixed] - src_mesh[fixed], axis=1))
        )
        passed = (
            components == 1
            and holes == 0
            and overlap_px >= 2000
            and min_strain >= 0.90
            and max_strain <= 1.12
            and anchor_drift <= 1.0
        )
        all_pass = all_pass and passed
        samples.append(
            {
                "index": index,
                "progress": progress,
                "revealedHiddenPixels": revealed_pixels,
                "sleeveUpperOverlapPixels": overlap_px,
                "components": components,
                "holes": holes,
                "minStrain": min_strain,
                "maxStrain": max_strain,
                "anchorDriftPx": anchor_drift,
                "pass": passed,
            }
        )
        frame = Image.new("RGB", (500, 960), "white")
        crop = v29.v28.crop_scale(context, (0, 190, 240, 650), 2)
        frame.paste(crop.convert("RGB"), (10, 32), crop.getchannel("A"))
        ImageDraw.Draw(frame).text(
            (14, 8),
            f"样本 {index:02d}｜{progress:.2f}",
            fill=(15, 22, 32),
            font=font(20, True),
        )
        frame.save(ROOT / f"samples/fk-{index:03d}.png")
        thumb = frame.resize((250, 480), Image.Resampling.LANCZOS)
        frames.append(thumb)
        if index in (0, 10, 20, 30, 40):
            chosen[index] = thumb

    exposures = [item["revealedHiddenPixels"] for item in samples]
    exposure_pass = (
        exposures[0] == 0
        and exposures[40] == 0
        and exposures[20] > 0
        and exposures == list(reversed(exposures))
    )
    base_components = (
        cv2.connectedComponents((complete > 8).astype(np.uint8))[0] - 1
    )
    base_holes = v29.hole_count(complete)
    hidden_ratio = (
        float(np.count_nonzero(hidden > 8))
        / float(np.count_nonzero(complete > 8))
    )
    shoulder_protrusion = int(
        np.count_nonzero(complete[:source_shoulder_top] > 8)
    )
    all_pass = (
        all_pass
        and exposure_pass
        and first_hash == last_hash
        and base_components == 1
        and base_holes == 0
        and partition_difference == 0
        and hidden_ratio <= 0.28
        and shoulder_protrusion == 0
    )
    save_json(ROOT / "samples/fk-41-samples.json", samples)
    frames[0].save(
        ROOT / "qa/fk-41-slow-preview.gif",
        save_all=True,
        append_images=frames[1:],
        duration=190,
        loop=0,
        disposal=2,
    )
    contact = Image.new("RGB", (1250, 570), (242, 245, 249))
    for col, index in enumerate((0, 10, 20, 30, 40)):
        contact.paste(chosen[index], (col * 250, 40))
        draw = ImageDraw.Draw(contact)
        draw.text(
            (col * 250 + 10, 8),
            f"{index:02d}",
            fill=(20, 25, 35),
            font=font(21, True),
        )
        draw.text(
            (col * 250 + 10, 528),
            f"隐藏露出 {exposures[index]} px",
            fill=(170, 35, 110),
            font=font(16, True),
        )
    contact.save(ROOT / "qa/fk-selected-contact-sheet.png")

    source = Image.open(SOURCE_COLOR).convert("RGBA")
    left_source_crop = crop_large(source)
    right_texture = np.array(Image.open(RIGHT_TEXTURE).convert("RGBA"))
    aligned_texture = Image.fromarray(
        cv2.warpAffine(
            np.ascontiguousarray(right_texture[:, ::-1, :]),
            np.float32(
                [
                    [RIGHT_REGISTER_SX, 0, RIGHT_REGISTER_TX],
                    [0, RIGHT_REGISTER_SY, RIGHT_REGISTER_TY],
                ]
            ),
            (W, H),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        ),
        "RGBA",
    )
    right_crop = crop_large(aligned_texture)
    complete_large = crop_large(checker_layer(complete, COLORS["sleeve"]))
    outline_large = crop_large(current_outline)
    ownership_on_source = source.copy()
    ownership_on_source.alpha_composite(
        v29.v28.solid(
            Image.fromarray(visible_owned), (40, 112, 194, 170)
        )
    )
    ownership_on_source.alpha_composite(
        v29.v28.solid(Image.fromarray(hidden), (211, 45, 135, 185))
    )
    complete_partition_outline = cv2.morphologyEx(
        (complete > 8).astype(np.uint8) * 255,
        cv2.MORPH_GRADIENT,
        np.ones((3, 3), dtype=np.uint8),
    )
    ownership_on_source.alpha_composite(
        v29.v28.solid(
            Image.fromarray(complete_partition_outline),
            (235, 45, 45, 255),
        )
    )
    ownership_large = crop_large(ownership_on_source)
    v29_large = crop_large(
        checker_layer(
            np.array(Image.open(V29 / "masks/sleeve-complete-dual-anchor.png")),
            (120, 145, 174, 255),
        )
    )

    board = Image.new("RGB", (2400, 1900), (244, 247, 251))
    draw = ImageDraw.Draw(board)
    draw.text(
        (50, 26),
        "小星 V30 修正｜left 完整袖型与窄幅隐藏归属",
        fill=(18, 28, 43),
        font=font(48, True),
    )
    draw.text(
        (50, 88),
        "④肩顶受 left 原图外轮廓约束；⑥直接叠原图，蓝+洋红=④，洋红仅为衣身侧窄条。",
        fill=(60, 72, 92),
        font=font(24),
    )
    labeled(board, left_source_crop, (40, 145, 480, 790), "① left 原图")
    labeled(board, right_crop, (500, 145, 940, 790), "② 已批准 right 镜像参照")
    labeled(board, v29_large, (960, 145, 1400, 790), "③ V29 失败袖型")
    labeled(board, complete_large, (1420, 145, 1860, 790), "④ V30 修正完整袖型")
    labeled(board, outline_large, (1880, 145, 2360, 790), "⑤ 修正袖型 + right 红轮廓")
    labeled(
        board,
        ownership_large,
        (40, 830, 600, 1510),
        "⑥ 与①同坐标：蓝+洋红=④，红线=④完整外轮廓",
    )
    labeled(board, contact, (620, 830, 2360, 1510), "⑦ 0→1→0：隐藏料仅抬臂时露出")
    draw.rounded_rectangle(
        (40, 1550, 2360, 1855),
        20,
        fill=(255, 255, 255),
        outline=(174, 186, 204),
        width=2,
    )
    draw.text(
        (70, 1585),
        "必须由你批准的变化：",
        fill=(125, 50, 20),
        font=font(28, True),
    )
    draw.text(
        (70, 1640),
        "1. 第④格是否保持左图真实袖长并接近第②格结构；2. 第⑥格隐藏洋红是否只是合理窄条；",
        fill=(35, 46, 62),
        font=font(25),
    )
    draw.text(
        (70, 1692),
        "3. 肩顶是否不再向背景突出；4. 袖口是否覆盖上臂，运动中是否无裂缝或突然露出大片隐藏料。",
        fill=(35, 46, 62),
        font=font(25),
    )
    draw.text(
        (70, 1760),
        "仍为阶段 A 几何候选；未进入纹理、PSD、Cubism、Physics 或 Runtime。",
        fill=(72, 85, 105),
        font=font(24),
    )
    board.save(ROOT / "qa/V30-RIGHT-STRUCTURE-CONVERGENCE-USER-REVIEW.zh-CN.png")

    report = {
        "schemaVersion": 1,
        "status": (
            "engineering_pass_pending_user_visual_approval"
            if all_pass
            else "engineering_fail_stop_stage_a"
        ),
        "scope": "screen-left sleeve right-structure convergence only",
        "skeletonUnchanged": True,
        "rightReference": {
            "approvedCompleteGeometryUsedAsRegisteredCompleteTemplate": True,
            "visibleHiddenDerivedFromOneCompleteMask": True,
            "alphaGeometryReused": True,
            "textureCopied": False,
            "rightModified": False,
        },
        "geometry": {
            "completeMaskIoUWithAlignedRight": iou,
            "visibleOwnedPixels": int(np.count_nonzero(visible_owned > 8)),
            "hiddenPixels": int(np.count_nonzero(hidden > 8)),
            "visibleHiddenPartitionDifferencePixels": partition_difference,
            "hiddenAreaRatio": hidden_ratio,
            "shoulderProtrusionPixelsAboveSource": shoulder_protrusion,
            "components": base_components,
            "holes": base_holes,
        },
        "motion": {
            "samples": 41,
            "allFramesPass": all_pass,
            "returnConsistency": first_hash == last_hash,
            "defaultHiddenExposurePixels": exposures[0],
            "peakHiddenExposurePixels": exposures[20],
            "returnHiddenExposurePixels": exposures[40],
            "minimumSleeveUpperOverlapPixels": min(
                item["sleeveUpperOverlapPixels"] for item in samples
            ),
        },
        "visualGate": {
            "status": "pending_user_visual_approval",
            "review": "qa/V30-RIGHT-STRUCTURE-CONVERGENCE-USER-REVIEW.zh-CN.png",
            "earliestFailurePoint": None,
        },
        "stop": "remain at Stage A",
    }
    save_json(ROOT / "audit/machine-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
