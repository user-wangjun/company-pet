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
V28 = XIAOXING / "validation/arm-chain-screen-left-v28-physical-sleeve-completion"
SOURCE_LINE = XIAOXING / "source/masters/front-line-source-exact-after-reset.png"
SOURCE_COLOR = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
V25_APPROVAL = (
    XIAOXING
    / "validation/arm-chain-screen-left-v25-shoulder-joint-correction"
    / "audit/user-visual-approval-2026-07-28.json"
)
RIGHT_COMPLETE = (
    XIAOXING
    / "validation/arm-chain-screen-right-v5-hidden-upper-arm"
    / "complete-sleeve-final"
)
RIGHT_COMPLETE_TEXTURE = (
    RIGHT_COMPLETE / "materials/sleeve-complete-textured-r1.png"
)
RIGHT_COMPLETE_GEOMETRY = (
    RIGHT_COMPLETE / "inputs/sleeve-complete-geometry-r9.png"
)
RIGHT_COMPLETE_MANIFEST = (
    RIGHT_COMPLETE
    / "audit/complete-sleeve-freeze-manifest-2026-07-25.json"
)

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


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


v27 = load_module(
    V27 / "tools/build_v27_source_traced_layering.py", "v27_builder"
)
v28 = load_module(
    V28 / "tools/build_v28_physical_sleeve.py", "v28_builder"
)


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font(size: int, bold=False):
    for path in (
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def smoothstep(value):
    value = np.clip(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def rotate_point(point, pivot, angle_deg):
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    delta = np.asarray(point, dtype=np.float64) - pivot
    return pivot + np.array((c * delta[0] - s * delta[1], s * delta[0] + c * delta[1]))


def bilateral_reference(source_rgb):
    mirrored_source = np.ascontiguousarray(source_rgb[:, ::-1, :])
    mirrored_visible, _ = v27.source_traced_visible_masks(mirrored_source)
    return mirrored_visible["sleeve"]


def aligned_right_complete_reference():
    right_alpha = np.array(
        Image.open(RIGHT_COMPLETE_GEOMETRY).convert("RGBA").getchannel("A")
    )
    mirrored = np.ascontiguousarray(right_alpha[:, ::-1])
    # Frozen right shoulder (332, 261) mirrors to (179, 261); align to
    # the approved current-side shoulder (170, 251) without scaling.
    return cv2.warpAffine(
        mirrored,
        np.float32([[1, 0, -9], [0, 1, -10]]),
        (W, H),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def build_bilateral_sleeve(left_visible, mirrored_right):
    # Only the source-occluded inner side may use the opposite sleeve as a guide.
    guide_region = np.zeros((H, W), dtype=np.uint8)
    guide_polygon = np.array(
        [(157, 212), (193, 214), (193, 420), (178, 421), (158, 300)],
        dtype=np.int32,
    )
    cv2.fillPoly(guide_region, [guide_polygon], 255)
    bilateral_hidden = cv2.bitwise_and(mirrored_right, guide_region)

    # Continuous, narrow attachment fill. It does not redefine the outer edge or cuff.
    attachment = np.zeros((H * 4, W * 4), dtype=np.uint8)
    points = np.array(
        [
            (164, 220),
            (176, 218),
            (185, 236),
            (188, 275),
            (189, 325),
            (188, 370),
            (184, 416),
            (181, 388),
            (180, 350),
            (176, 310),
            (169, 268),
            (164, 242),
        ],
        dtype=np.float64,
    )
    cv2.fillPoly(
        attachment,
        [np.round(points * 4).astype(np.int32)],
        255,
        lineType=cv2.LINE_AA,
    )
    attachment = np.array(
        Image.fromarray(attachment).resize((W, H), Image.Resampling.LANCZOS)
    )
    complete = np.maximum(left_visible, np.maximum(bilateral_hidden, attachment))
    contours, _ = cv2.findContours(
        (complete > 8).astype(np.uint8) * 255,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_NONE,
    )
    closed = np.zeros((H, W), dtype=np.uint8)
    cv2.drawContours(closed, contours, -1, 255, thickness=cv2.FILLED)
    complete = np.maximum(complete, closed)
    hidden = cv2.subtract(complete, left_visible)
    return complete, hidden


def mesh_points():
    xs = np.array((78.0, 104.0, 130.0, 154.0, 176.0, 196.0))
    ys = np.array((205.0, 240.0, 280.0, 325.0, 370.0, 420.0, 440.0))
    return np.array([(x, y) for y in ys for x in xs]), len(xs), len(ys)


def deform_mesh(angle_deg):
    src, nx, ny = mesh_points()
    dst = []
    weights = []
    for x, y in src:
        vertical = smoothstep((y - 220.0) / 196.0)
        # The shoulder/torso attachment stays nearly fixed; the free cuff follows the arm.
        inner_lock = 1.0
        if x >= 168.0 and y <= 325.0:
            inner_lock = 0.18 + 0.82 * smoothstep((y - 220.0) / 105.0)
        weight = float(vertical * inner_lock)
        dst.append(rotate_point((x, y), S, angle_deg * weight))
        weights.append(weight)
    return src, np.array(dst), np.array(weights), nx, ny


def triangles(nx, ny):
    result = []
    for row in range(ny - 1):
        for col in range(nx - 1):
            a = row * nx + col
            b = a + 1
            c = a + nx
            d = c + 1
            result.extend(((a, b, d), (a, d, c)))
    return result


def warp_triangle_alpha(source, output, src_tri, dst_tri):
    src_rect = cv2.boundingRect(np.float32(src_tri))
    dst_rect = cv2.boundingRect(np.float32(dst_tri))
    sx, sy, sw, sh = src_rect
    dx, dy, dw, dh = dst_rect
    if sw <= 0 or sh <= 0 or dw <= 0 or dh <= 0:
        return
    src_local = np.float32([(x - sx, y - sy) for x, y in src_tri])
    dst_local = np.float32([(x - dx, y - dy) for x, y in dst_tri])
    patch = source[sy : sy + sh, sx : sx + sw]
    matrix = cv2.getAffineTransform(src_local, dst_local)
    warped = cv2.warpAffine(
        patch,
        matrix,
        (dw, dh),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    mask = np.zeros((dh, dw), dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.int32(np.round(dst_local)), 255, lineType=cv2.LINE_AA)
    target = output[dy : dy + dh, dx : dx + dw]
    contribution = np.uint8(
        warped.astype(np.float32) * (mask.astype(np.float32) / 255.0)
    )
    target[:] = np.maximum(target, contribution)


def warp_sleeve(image, angle_deg):
    if abs(angle_deg) < 1e-9:
        src, _, weights, nx, ny = deform_mesh(0.0)
        return image.copy(), src, src.copy(), weights
    source = np.array(image.getchannel("A"))
    output = np.zeros_like(source)
    src, dst, weights, nx, ny = deform_mesh(angle_deg)
    for tri in triangles(nx, ny):
        warp_triangle_alpha(source, output, src[list(tri)], dst[list(tri)])
    warped = Image.new("RGBA", (W, H), COLORS["sleeve"])
    warped.putalpha(Image.fromarray(output))
    return warped, src, dst, weights


def edge_strain(src, dst, nx, ny):
    ratios = []
    edges = set()
    for tri in triangles(nx, ny):
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edges.add(tuple(sorted((a, b))))
    for a, b in edges:
        old = np.linalg.norm(src[a] - src[b])
        new = np.linalg.norm(dst[a] - dst[b])
        if old > 0:
            ratios.append(float(new / old))
    return min(ratios), max(ratios)


def hole_count(alpha):
    _, hierarchy = cv2.findContours(
        (alpha > 8).astype(np.uint8) * 255,
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if hierarchy is None:
        return 0
    return int(sum(1 for item in hierarchy[0] if item[3] >= 0))


def composite(layers):
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for name in ORDER:
        canvas.alpha_composite(layers[name])
    return canvas


def labeled(board, image, box, text_value):
    x0, y0, x1, y1 = box
    area = Image.new("RGB", (x1 - x0, y1 - y0), "white")
    item = image.convert("RGBA")
    item.thumbnail((area.width, area.height - 48), Image.Resampling.LANCZOS)
    px = (area.width - item.width) // 2
    area.paste(item.convert("RGB"), (px, 0), item.getchannel("A"))
    ImageDraw.Draw(area).text((8, area.height - 42), text_value, fill=(20, 28, 40), font=font(22, True))
    board.paste(area, (x0, y0))


def main():
    for folder in ("materials", "masks", "samples", "qa", "audit"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)

    source_color = Image.open(SOURCE_COLOR).convert("RGBA")
    source_rgb = np.array(source_color.convert("RGB"))
    left_visible = np.array(
        Image.open(V27 / "masks/visible/sleeve.png").convert("L")
    )
    right_mirrored = bilateral_reference(source_rgb)
    right_complete_aligned = aligned_right_complete_reference()
    right_texture = np.array(Image.open(RIGHT_COMPLETE_TEXTURE).convert("RGBA"))
    right_texture_aligned = Image.fromarray(
        cv2.warpAffine(
            np.ascontiguousarray(right_texture[:, ::-1, :]),
            np.float32([[1, 0, -9], [0, 1, -10]]),
            (W, H),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        ),
        "RGBA",
    )
    sleeve_complete, sleeve_hidden = build_bilateral_sleeve(
        left_visible, right_mirrored
    )

    complete_masks = {
        name: np.array(
            Image.open(V27 / f"masks/complete/{name}.png").convert("L")
        )
        for name in ORDER
    }
    complete_masks["sleeve"] = sleeve_complete
    layers = {
        name: v28.solid(
            v28.antialiased(v28.mask_image(complete_masks[name])), COLORS[name]
        )
        for name in ORDER
    }
    for name, image in layers.items():
        image.save(ROOT / f"materials/{name}.png")
    Image.fromarray(left_visible).save(ROOT / "masks/sleeve-visible-left.png")
    Image.fromarray(right_mirrored).save(ROOT / "masks/sleeve-reference-right-mirrored.png")
    Image.fromarray(sleeve_hidden).save(ROOT / "masks/sleeve-hidden-bilateral.png")
    Image.fromarray(sleeve_complete).save(ROOT / "masks/sleeve-complete-dual-anchor.png")

    skeleton = json.loads(
        (V28 / "skeleton-lock.json").read_text(encoding="utf-8")
    )
    skeleton["status"] = "unchanged_from_user_approved_v25_for_v29"
    skeleton["parentChildRelations"][0] = {
        "id": "sleeve",
        "parent": "torso",
        "secondaryDriver": "upper_arm",
        "deformation": "dual-anchor graded warp",
    }
    save_json(ROOT / "skeleton-lock.json", skeleton)

    contract = {
        "schemaVersion": 1,
        "status": "invalidated_wrong_right_reference_stop_stage_a",
        "scope": "screen-left sleeve only; screen-right is read-only visual reference",
        "replacesAsFailedEvidence": "../arm-chain-screen-left-v28-physical-sleeve-completion",
        "authority": {
            "lineMasterSha256": sha256(SOURCE_LINE),
            "colorMasterSha256": sha256(SOURCE_COLOR),
            "v25ApprovalSha256": sha256(V25_APPROVAL),
            "leftVisibleSleeveSha256": sha256(V27 / "masks/visible/sleeve.png"),
            "rightCompleteComparisonGeometrySha256": sha256(
                RIGHT_COMPLETE_GEOMETRY
            ),
            "rightCompleteComparisonManifestSha256": sha256(
                RIGHT_COMPLETE_MANIFEST
            ),
        },
        "bilateralRule": {
            "rightSleeveUse": "INVALIDATED: source-extracted visible silhouette was used instead of the frozen complete right sleeve",
            "rightSleeveMutation": "none",
            "frozenCompleteRightUse": "comparison only; never copied into current material",
            "allowedDifference": "source perspective, pose, and hair occlusion",
            "forbiddenDifference": "different garment type, cap volume, or cuff construction",
        },
        "motionRule": {
            "shoulderAttachment": "near-fixed to torso",
            "middleCloth": "graded warp preserving area and continuity",
            "cuffAndUnderarm": "follow upper arm",
            "hiddenExposure": "zero in default pose; revealed only while the arm lifts away from the fixed torso occluder",
            "physics": "none; this is deterministic geometry preflight only",
        },
    }
    save_json(ROOT / "dual-anchor-sleeve-contract.json", contract)

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
    seam_band = np.zeros((H, W), dtype=np.uint8)
    cv2.line(
        seam_band,
        (164, 220),
        (184, 320),
        255,
        8,
        lineType=cv2.LINE_AA,
    )
    seam_band_pixels = int(np.count_nonzero(seam_band > 8))
    occluder_mask = cv2.dilate(
        (sleeve_hidden > 8).astype(np.uint8) * 255,
        np.ones((3, 3), dtype=np.uint8),
        iterations=1,
    )
    occluder_mask[left_visible > 8] = 0
    fixed_hidden_occluder = Image.new("RGBA", (W, H), (238, 239, 235, 255))
    fixed_hidden_occluder.putalpha(Image.fromarray(occluder_mask))
    hidden_layer = v28.solid(
        v28.antialiased(Image.fromarray(sleeve_hidden)), COLORS["sleeve"]
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
        new_e = v28.point_at(S, l1, theta1)
        new_w = v28.point_at(new_e, l2, theta1 + theta2)
        rest_global = math.degrees(math.atan2(WR[1] - E[1], WR[0] - E[0]))
        d2 = theta1 + theta2 - rest_global
        warped_sleeve, src_mesh, dst_mesh, weights = warp_sleeve(
            layers["sleeve"], d1
        )
        warped_hidden, _, _, _ = warp_sleeve(hidden_layer, d1)
        posed = {
            "upper_arm": v28.rotate_translate(layers["upper_arm"], S, S, d1),
            "forearm": v28.rotate_translate(layers["forearm"], E, new_e, d2),
            "hand": v28.rotate_translate(
                layers["hand"], WR, new_w, d2 + target["wristLocal"] * progress
            ),
            "sleeve": warped_sleeve,
        }
        pose = composite(posed)
        context_pose = torso_context.copy()
        context_pose.alpha_composite(pose)
        context_pose.alpha_composite(fixed_hidden_occluder)
        digest = hashlib.sha256(pose.tobytes()).hexdigest()
        first_hash = digest if index == 0 else first_hash
        last_hash = digest if index == 40 else last_hash
        overlap_px = v28.overlap(posed["sleeve"], posed["upper_arm"])
        sleeve_components = (
            cv2.connectedComponents(
                (np.array(warped_sleeve.getchannel("A")) > 8).astype(np.uint8)
            )[0]
            - 1
        )
        sleeve_holes = hole_count(np.array(warped_sleeve.getchannel("A")))
        sleeve_alpha = np.array(warped_sleeve.getchannel("A"))
        warped_hidden_alpha = (
            sleeve_hidden
            if abs(d1) < 1e-9
            else np.array(warped_hidden.getchannel("A"))
        )
        revealed_hidden = (warped_hidden_alpha > 8) & (occluder_mask <= 8)
        revealed_hidden_pixels = int(np.count_nonzero(revealed_hidden))
        revealed_overlay = Image.new("RGBA", (W, H), (211, 45, 135, 0))
        revealed_overlay.putalpha(
            Image.fromarray(revealed_hidden.astype(np.uint8) * 210)
        )
        context_pose.alpha_composite(revealed_overlay)
        torso_attachment_coverage = float(
            np.count_nonzero((sleeve_alpha > 8) & (seam_band > 8))
            / seam_band_pixels
        )
        fixed = weights <= 0.08
        anchor_drift = float(
            np.max(np.linalg.norm(dst_mesh[fixed] - src_mesh[fixed], axis=1))
        )
        _, nx, ny = mesh_points()
        min_strain, max_strain = edge_strain(src_mesh, dst_mesh, nx, ny)
        seam_pass = (
            overlap_px >= 3500
            and sleeve_components == 1
            and sleeve_holes == 0
            and torso_attachment_coverage >= 0.90
            and anchor_drift <= 1.0
            and min_strain >= 0.90
            and max_strain <= 1.12
        )
        all_pass = all_pass and seam_pass
        samples.append(
            {
                "index": index,
                "progress": progress,
                "sleeveUpperOverlapPixels": overlap_px,
                "sleeveComponents": sleeve_components,
                "sleeveHoles": sleeve_holes,
                "torsoAttachmentCoverageRatio": torso_attachment_coverage,
                "revealedHiddenPixels": revealed_hidden_pixels,
                "torsoAnchorMaxDriftPx": anchor_drift,
                "minMeshEdgeStrainRatio": min_strain,
                "maxMeshEdgeStrainRatio": max_strain,
                "pass": seam_pass,
            }
        )
        frame = Image.new("RGB", (500, 960), "white")
        crop = v28.crop_scale(context_pose, (0, 190, 240, 650), 2)
        frame.paste(crop.convert("RGB"), (10, 32), crop.getchannel("A"))
        draw = ImageDraw.Draw(frame)
        draw.text((14, 8), f"样本 {index:02d}｜{progress:.2f}", fill=(15, 22, 32), font=font(20, True))
        frame.save(ROOT / f"samples/fk-{index:03d}.png")
        thumb = frame.resize((250, 480), Image.Resampling.LANCZOS)
        frames.append(thumb)
        if index in (0, 10, 20, 30, 40):
            chosen[index] = thumb

    save_json(ROOT / "samples/fk-41-samples.json", samples)
    hidden_exposure = [item["revealedHiddenPixels"] for item in samples]
    exposure_pass = (
        hidden_exposure[0] == 0
        and hidden_exposure[40] == 0
        and hidden_exposure[20] > 0
        and hidden_exposure == list(reversed(hidden_exposure))
    )
    all_pass = all_pass and exposure_pass
    frames[0].save(
        ROOT / "qa/fk-41-dual-anchor-slow-preview.gif",
        save_all=True,
        append_images=frames[1:],
        duration=190,
        loop=0,
        disposal=2,
    )
    contact = Image.new("RGB", (1250, 570), (242, 245, 249))
    for col, index in enumerate((0, 10, 20, 30, 40)):
        contact.paste(chosen[index], (col * 250, 40))
        contact_draw = ImageDraw.Draw(contact)
        contact_draw.text((col * 250 + 10, 8), f"{index:02d}", fill=(20, 25, 35), font=font(21, True))
        contact_draw.text(
            (col * 250 + 10, 528),
            f"隐藏露出 {hidden_exposure[index]} px",
            fill=(170, 35, 110),
            font=font(16, True),
        )
    contact.save(ROOT / "qa/fk-selected-contact-sheet.png")

    bilateral = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    left_rgba = v28.solid(Image.fromarray(left_visible), (40, 112, 194, 170))
    right_rgba = v28.solid(Image.fromarray(right_mirrored), (224, 70, 70, 130))
    bilateral.alpha_composite(left_rgba)
    bilateral.alpha_composite(right_rgba)
    bilateral.save(ROOT / "qa/left-vs-mirrored-right-overlay.png")

    new_iso = v28.checker((W, H)).convert("RGBA")
    new_iso.alpha_composite(layers["sleeve"])
    old_iso = v28.checker((W, H)).convert("RGBA")
    old_iso.alpha_composite(Image.open(V28 / "materials/sleeve.png").convert("RGBA"))

    diagram = new_iso.copy()
    draw = ImageDraw.Draw(diagram)
    draw.line([(164, 220), (170, 251), (178, 320)], fill=(230, 45, 45, 255), width=4)
    draw.line([(96, 372), (184, 416)], fill=(30, 170, 90, 255), width=4)
    draw.text((196, 230), "固定带", fill=(230, 45, 45, 255), font=font(18, True))
    draw.text((195, 390), "随臂带", fill=(30, 150, 80, 255), font=font(18, True))
    diagram.save(ROOT / "qa/dual-anchor-annotation.png")

    visible_canvas = v28.checker((W, H)).convert("RGBA")
    visible_canvas.alpha_composite(
        v28.solid(Image.fromarray(left_visible), (40, 112, 194, 255))
    )
    hidden_canvas = v28.checker((W, H)).convert("RGBA")
    hidden_canvas.alpha_composite(
        v28.solid(Image.fromarray(sleeve_hidden), (211, 45, 135, 255))
    )
    split_canvas = v28.checker((W, H)).convert("RGBA")
    split_canvas.alpha_composite(
        v28.solid(Image.fromarray(left_visible), (40, 112, 194, 255))
    )
    split_canvas.alpha_composite(
        v28.solid(Image.fromarray(sleeve_hidden), (211, 45, 135, 255))
    )
    solid_canvas = v28.checker((W, H)).convert("RGBA")
    solid_canvas.alpha_composite(layers["sleeve"])
    sleeve_box = (70, 195, 215, 435)
    visible_large = v28.crop_scale(visible_canvas, sleeve_box, 4)
    hidden_large = v28.crop_scale(hidden_canvas, sleeve_box, 4)
    split_large = v28.crop_scale(split_canvas, sleeve_box, 4)
    solid_large = v28.crop_scale(solid_canvas, sleeve_box, 4)
    solid_large.save(ROOT / "qa/complete-sleeve-solid-large.png")
    split_large.save(ROOT / "qa/complete-sleeve-visible-hidden-large.png")

    material_board = Image.new("RGB", (2400, 1650), (244, 247, 251))
    material_draw = ImageDraw.Draw(material_board)
    material_draw.text(
        (50, 28),
        "小星 V29｜补全袖子完整材料大图",
        fill=(18, 28, 43),
        font=font(50, True),
    )
    material_draw.text(
        (50, 92),
        "蓝色=原图当前侧可见袖子；洋红=参考另一侧推断的隐藏袖料；最右为实际导出的完整闭合材料。",
        fill=(60, 72, 92),
        font=font(25),
    )
    labeled(material_board, visible_large, (40, 155, 600, 1335), "① 原图可见袖子（未补全）")
    labeled(material_board, hidden_large, (620, 155, 1180, 1335), "② 新补的隐藏袖料")
    labeled(material_board, split_large, (1200, 155, 1760, 1335), "③ 合并归属：蓝可见 / 洋红隐藏")
    labeled(material_board, solid_large, (1780, 155, 2340, 1335), "④ 实际完整袖子材料")
    material_draw.rounded_rectangle(
        (40, 1380, 2360, 1600),
        20,
        fill=(255, 255, 255),
        outline=(174, 186, 204),
        width=2,
    )
    material_draw.text(
        (70, 1415),
        "请直接审查第④格：完整轮廓是否仍像同一件落肩 T 恤袖子；内缘是否过直、过尖、过宽或像补丁。",
        fill=(120, 50, 20),
        font=font(27, True),
    )
    material_draw.text(
        (70, 1470),
        "第②格在默认姿态完全被衣身遮住，只在抬臂过程中逐渐露出；本板不代表视觉已通过。",
        fill=(60, 72, 92),
        font=font(25),
    )
    material_board.save(ROOT / "qa/V29-COMPLETE-SLEEVE-MATERIAL-REVIEW.zh-CN.png")

    right_outline = cv2.morphologyEx(
        (right_complete_aligned > 8).astype(np.uint8) * 255,
        cv2.MORPH_GRADIENT,
        np.ones((3, 3), dtype=np.uint8),
    )
    visible_overlay = v28.checker((W, H)).convert("RGBA")
    visible_overlay.alpha_composite(
        v28.solid(Image.fromarray(sleeve_complete), (40, 112, 194, 190))
    )
    visible_overlay.alpha_composite(
        v28.solid(Image.fromarray(right_complete_aligned), (224, 55, 55, 140))
    )
    complete_with_right_outline = v28.checker((W, H)).convert("RGBA")
    complete_with_right_outline.alpha_composite(layers["sleeve"])
    complete_with_right_outline.alpha_composite(
        v28.solid(Image.fromarray(right_outline), (235, 45, 45, 255))
    )
    common = (sleeve_complete > 8) & (right_complete_aligned > 8)
    left_only = (sleeve_complete > 8) & ~common
    right_only = (right_complete_aligned > 8) & ~common
    difference_canvas = v28.checker((W, H)).convert("RGBA")
    difference_canvas.alpha_composite(
        v28.solid(Image.fromarray(common.astype(np.uint8) * 255), (72, 176, 105, 255))
    )
    difference_canvas.alpha_composite(
        v28.solid(Image.fromarray(left_only.astype(np.uint8) * 255), (40, 112, 194, 255))
    )
    difference_canvas.alpha_composite(
        v28.solid(Image.fromarray(right_only.astype(np.uint8) * 255), (224, 55, 55, 255))
    )
    visible_overlay_large = v28.crop_scale(visible_overlay, sleeve_box, 4)
    complete_outline_large = v28.crop_scale(
        complete_with_right_outline, sleeve_box, 4
    )
    difference_large = v28.crop_scale(difference_canvas, sleeve_box, 4)
    left_crop = v28.crop_scale(source_color, (65, 195, 220, 455), 2)
    right_crop = v28.crop_scale(right_texture_aligned, sleeve_box, 4)
    bilateral_board = Image.new("RGB", (2400, 1650), (244, 247, 251))
    bilateral_draw = ImageDraw.Draw(bilateral_board)
    bilateral_draw.text(
        (50, 28),
        "小星 V29｜left 与 right 袖子直接镜像对比",
        fill=(18, 28, 43),
        font=font(50, True),
    )
    bilateral_draw.text(
        (50, 92),
        "冻结的完整 right 袖子已镜像并按肩点整数配准；红线用于检查当前完整 left 的袖山、筒身与袖口是否一致。",
        fill=(60, 72, 92),
        font=font(24),
    )
    labeled(bilateral_board, solid_large, (40, 155, 500, 1280), "① 当前完整 left 袖子")
    labeled(bilateral_board, right_crop, (520, 155, 980, 1280), "② 冻结完整 right 镜像")
    labeled(bilateral_board, visible_overlay_large, (1000, 155, 1460, 1280), "③ 蓝=left完整，红=right完整")
    labeled(bilateral_board, difference_large, (1480, 155, 1940, 1280), "④ 绿重合 / 蓝left独有 / 红right独有")
    labeled(bilateral_board, complete_outline_large, (1960, 155, 2380, 1280), "⑤ 当前完整袖子 + right 红轮廓")
    bilateral_draw.rounded_rectangle(
        (40, 1325, 2360, 1600),
        20,
        fill=(255, 255, 255),
        outline=(174, 186, 204),
        width=2,
    )
    bilateral_draw.text(
        (70, 1365),
        "对比结论不能只看面积：第⑤格要重点看红轮廓与蓝色完整袖子的肩顶、袖口斜率和内缘体量。",
        fill=(120, 50, 20),
        font=font(26, True),
    )
    bilateral_draw.text(
        (70, 1420),
        "right 完整袖材只作结构对照；根据当前任务边界，不得直接复制、缩放或修补进 left 材料。",
        fill=(60, 72, 92),
        font=font(24),
    )
    bilateral_draw.text(
        (70, 1475),
        "请确认第⑤格是否仍像同一件落肩 T 恤的两只完整袖子；机器面积指标不能代替轮廓判断。",
        fill=(60, 72, 92),
        font=font(24),
    )
    bilateral_board.save(ROOT / "qa/V29-LEFT-RIGHT-SLEEVE-DIRECT-COMPARISON.zh-CN.png")

    review = Image.new("RGB", (2400, 1900), (244, 247, 251))
    draw = ImageDraw.Draw(review)
    draw.text((50, 25), "小星 V29｜左右袖型校准 + 双端约束运动预检", fill=(18, 28, 43), font=font(48, True))
    draw.text((50, 88), "另一侧仅作隐藏袖型模板；默认不露隐藏料，抬臂时洋红区域才逐渐露出。", fill=(60, 72, 92), font=font(25))
    left_crop = v28.crop_scale(source_color, (65, 195, 220, 455), 2)
    right_crop = source_color.crop((292, 195, 447, 455)).transpose(Image.Transpose.FLIP_LEFT_RIGHT).resize((310, 520), Image.Resampling.LANCZOS)
    labeled(review, left_crop, (40, 145, 520, 760), "① 原图当前侧袖子")
    labeled(review, right_crop, (550, 145, 1030, 760), "② 原图另一侧镜像参照")
    labeled(review, bilateral, (1060, 145, 1540, 760), "③ 蓝=当前侧，红=另一侧隐藏模板")
    labeled(review, old_iso, (1570, 145, 2030, 760), "④ V28：内缘体量过大")
    labeled(review, new_iso, (40, 800, 520, 1450), "⑤ V29：按双侧尺度收回")
    labeled(review, diagram, (550, 800, 1030, 1450), "⑥ 红固定、绿随臂、中部渐变")
    labeled(review, contact, (1060, 800, 2360, 1450), "⑦ 洋红=运动中实际露出的隐藏袖料")
    draw.rounded_rectangle((40, 1490, 2360, 1850), 22, fill=(255, 255, 255), outline=(174, 186, 204), width=2)
    draw.text((70, 1530), "请重点批准：", fill=(130, 55, 20), font=font(28, True))
    draw.text((70, 1580), "1. 两侧是否仍像同一件落肩 T 恤；2. 当前侧完整袖子是否不再异常鼓起；", fill=(35, 46, 62), font=font(26))
    draw.text((70, 1630), "3. 默认姿态是否完全不露隐藏料；4. 抬臂时是否只在衣身让开的区域自然露出。", fill=(35, 46, 62), font=font(26))
    draw.text((70, 1700), "本板仍为阶段 A 几何候选。机器通过不代表视觉通过；未进入纹理 / PSD / Cubism / Physics / Runtime。", fill=(72, 85, 105), font=font(24))
    review.save(ROOT / "qa/V29-LEFT-RIGHT-DUAL-ANCHOR-USER-REVIEW.zh-CN.png")

    hidden_pixels = int(np.count_nonzero(sleeve_hidden > 8))
    right_left_overlap = int(
        np.count_nonzero((left_visible > 8) & (right_mirrored > 8))
    )
    left_union = int(np.count_nonzero((left_visible > 8) | (right_mirrored > 8)))
    bilateral_iou = right_left_overlap / left_union if left_union else 0.0
    complete_overlap = int(
        np.count_nonzero(
            (sleeve_complete > 8) & (right_complete_aligned > 8)
        )
    )
    complete_union = int(
        np.count_nonzero(
            (sleeve_complete > 8) | (right_complete_aligned > 8)
        )
    )
    complete_iou = complete_overlap / complete_union if complete_union else 0.0
    default_displayed = (sleeve_complete > 8) & (occluder_mask <= 8)
    default_visible_difference = int(
        np.count_nonzero(default_displayed != (left_visible > 8))
    )
    report = {
        "schemaVersion": 1,
        "status": "engineering_fail_stop_stage_a",
        "scope": "screen-left sleeve bilateral calibration and dual-anchor motion preflight",
        "skeleton": {"unchanged": True},
        "bilateral": {
            "mirroredRightUsedAsReferenceOnly": True,
            "rightMaterialModified": False,
            "visibleMaskIoU": bilateral_iou,
            "alignedFrozenCompleteRightUsedForComparisonOnly": True,
            "completeMaskIoU": complete_iou,
            "referenceAuthorityPass": False,
            "failure": "V29 geometry was calibrated from a source-extracted visible right silhouette, not the frozen approved complete right sleeve",
        },
        "geometry": {
            "hiddenAddedPixels": hidden_pixels,
            "defaultVisibleDifferencePixels": default_visible_difference,
            "v28HiddenPixels": int(
                np.count_nonzero(
                    np.array(Image.open(V28 / "masks/sleeve-hidden-physical.png")) > 8
                )
            ),
        },
        "motion": {
            "samples": 41,
            "allFramesPass": all_pass,
            "returnConsistency": first_hash == last_hash,
            "minimumOverlapPixels": min(x["sleeveUpperOverlapPixels"] for x in samples),
            "maximumSleeveHoles": max(x["sleeveHoles"] for x in samples),
            "minimumTorsoAttachmentCoverageRatio": min(
                x["torsoAttachmentCoverageRatio"] for x in samples
            ),
            "maximumTorsoAnchorDriftPx": max(x["torsoAnchorMaxDriftPx"] for x in samples),
            "minimumMeshEdgeStrainRatio": min(x["minMeshEdgeStrainRatio"] for x in samples),
            "maximumMeshEdgeStrainRatio": max(x["maxMeshEdgeStrainRatio"] for x in samples),
            "hiddenExposure": {
                "defaultPixels": hidden_exposure[0],
                "peakPixels": hidden_exposure[20],
                "returnPixels": hidden_exposure[40],
                "symmetricReturn": hidden_exposure == list(reversed(hidden_exposure)),
                "pass": exposure_pass,
            },
        },
        "visualGate": {
            "status": "failed_wrong_reference",
            "review": "qa/V29-LEFT-RIGHT-DUAL-ANCHOR-USER-REVIEW.zh-CN.png",
            "completeSleeveReview": "qa/V29-COMPLETE-SLEEVE-MATERIAL-REVIEW.zh-CN.png",
            "bilateralComparisonReview": "qa/V29-LEFT-RIGHT-SLEEVE-DIRECT-COMPARISON.zh-CN.png",
            "earliestFailurePoint": "right sleeve reference selection before hidden geometry construction",
        },
        "stop": "remain at Stage A",
    }
    save_json(ROOT / "audit/machine-report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
