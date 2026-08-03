from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
XIAOXING = ROOT.parents[1]
SOURCE_LINE = XIAOXING / "source/masters/front-line-source-exact-after-reset.png"
SOURCE_COLOR = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
V25 = XIAOXING / "validation/arm-chain-screen-left-v25-shoulder-joint-correction"
V25_SKELETON = V25 / "candidate-skeleton.json"
V25_APPROVAL = V25 / "audit/user-visual-approval-2026-07-28.json"
V26_REJECTION = (
    XIAOXING
    / "validation/arm-chain-screen-left-v26-layering-from-approved-v25-skeleton"
    / "audit/user-visual-rejection-2026-07-28.json"
)

W, H = 512, 1086
AA = 4
S = np.array((170.0, 251.0), dtype=np.float64)
E = np.array((147.0, 405.0), dtype=np.float64)
WR = np.array((115.0, 529.0), dtype=np.float64)
COLORS = {
    "upper_arm": (229, 89, 78, 255),
    "forearm": (243, 155, 44, 255),
    "hand": (32, 167, 119, 255),
    "sleeve": (40, 112, 194, 255),
}
ORDER = ["upper_arm", "forearm", "hand", "sleeve"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_hash(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def font(size: int, bold=False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def mask_image(array: np.ndarray) -> Image.Image:
    return Image.fromarray(array.astype(np.uint8), mode="L")


def mask_array(image: Image.Image) -> np.ndarray:
    return np.array(image.convert("L"), dtype=np.uint8)


def solid(mask: Image.Image, color) -> Image.Image:
    image = Image.new("RGBA", (W, H), color)
    image.putalpha(mask)
    return image


def antialiased_alpha(mask: Image.Image) -> Image.Image:
    # Preserve source-pixel ownership while avoiding a staircase presentation
    # when the 512 px master is enlarged for human review.
    return mask.filter(ImageFilter.GaussianBlur(0.45))


def checker(size, cell=16):
    image = Image.new("RGB", size, (239, 239, 239))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle(
                    (x, y, x + cell - 1, y + cell - 1), fill=(207, 207, 207)
                )
    return image


def external_fill(seed: np.ndarray, minimum_area=2.0, dilate=1):
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    closed = cv2.morphologyEx(seed, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(
        closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
    )
    output = np.zeros_like(seed)
    retained = []
    for contour in contours:
        if cv2.contourArea(contour) >= minimum_area:
            cv2.drawContours(output, [contour], -1, 255, -1)
            retained.append(contour)
    if dilate:
        output = cv2.dilate(output, kernel, iterations=dilate)
    return output, retained


def source_traced_visible_masks(source_rgb: np.ndarray):
    rgb = source_rgb.astype(np.int16)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    yy, xx = np.indices((H, W))

    arm_envelope = np.zeros((H, W), dtype=np.uint8)
    cv2.fillPoly(
        arm_envelope,
        [
            np.array(
                [
                    (124, 378),
                    (188, 398),
                    (179, 454),
                    (159, 508),
                    (137, 552),
                    (134, 590),
                    (122, 628),
                    (92, 640),
                    (55, 637),
                    (54, 596),
                    (70, 568),
                    (91, 534),
                    (99, 490),
                    (108, 440),
                ],
                dtype=np.int32,
            )
        ],
        255,
    )
    skin_seed = (
        (r - b > 12)
        & (r - g > 6)
        & (r > 165)
        & (g > 135)
        & (arm_envelope > 0)
    )
    skin, skin_contours = external_fill(
        skin_seed.astype(np.uint8) * 255, minimum_area=2.0, dilate=1
    )
    skin = cv2.bitwise_and(skin, arm_envelope)

    sleeve_envelope = np.zeros((H, W), dtype=np.uint8)
    sleeve_semantic_boundary = np.array(
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
    cv2.fillPoly(sleeve_envelope, [sleeve_semantic_boundary], 255)
    sleeve_seed = (
        (r > 175)
        & (g > 175)
        & (b > 160)
        & (r - b > 3)
        & (r - b < 28)
        & (np.abs(r - g) < 10)
        & (sleeve_envelope > 0)
    )
    sleeve, sleeve_contours = external_fill(
        sleeve_seed.astype(np.uint8) * 255, minimum_area=5.0, dilate=1
    )
    sleeve = cv2.bitwise_and(sleeve, sleeve_envelope)

    forearm_vector = WR - E
    forearm_length = float(np.linalg.norm(forearm_vector))
    u = forearm_vector / forearm_length
    projection = (xx - E[0]) * u[0] + (yy - E[1]) * u[1]
    upper_region = projection <= 8.0
    hand_region = projection >= forearm_length - 2.0
    forearm_region = ~(upper_region | hand_region)

    upper = np.where((skin > 0) & upper_region, 255, 0).astype(np.uint8)
    forearm = np.where((skin > 0) & forearm_region, 255, 0).astype(np.uint8)
    hand = np.where((skin > 0) & hand_region, 255, 0).astype(np.uint8)
    # The garment owns the cuff edge where color antialiasing makes the skin
    # classifier overlap the sleeve classifier.
    upper = cv2.bitwise_and(upper, cv2.bitwise_not(sleeve))

    return (
        {
            "upper_arm": upper,
            "forearm": forearm,
            "hand": hand,
            "sleeve": sleeve,
        },
        {
            "skinCombined": skin,
            "sleeveCombined": sleeve,
            "skinContourPointCount": sum(len(c) for c in skin_contours),
            "sleeveContourPointCount": sum(len(c) for c in sleeve_contours),
            "sleeveSemanticBoundary": sleeve_semantic_boundary.tolist(),
        },
    )


def smooth_ribbon(control_points, half_widths, samples=120):
    points = np.array(control_points, dtype=np.float64)
    widths = np.array(half_widths, dtype=np.float64)
    if len(points) != 3:
        raise ValueError("Quadratic ribbon requires three control points")
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
    norms = np.linalg.norm(derivative, axis=1)
    tangent = derivative / norms[:, None]
    normal = np.column_stack((-tangent[:, 1], tangent[:, 0]))
    width_curve = (
        ((1 - ts) ** 2) * widths[0]
        + 2 * (1 - ts) * ts * widths[1]
        + (ts**2) * widths[2]
    )
    left = curve + normal * width_curve[:, None]
    right = curve - normal * width_curve[:, None]
    polygon = np.vstack((left, right[::-1]))
    large = np.zeros((H * AA, W * AA), dtype=np.uint8)
    cv2.fillPoly(
        large,
        [np.round(polygon * AA).astype(np.int32)],
        255,
        lineType=cv2.LINE_AA,
    )
    return np.array(
        Image.fromarray(large).resize((W, H), Image.Resampling.LANCZOS),
        dtype=np.uint8,
    )


def complete_masks(visible):
    upper_hidden_body = smooth_ribbon(
        [S, np.array((159.0, 331.0)), E], [12.5, 15.0, 18.0]
    )
    fore_hidden_body = smooth_ribbon(
        [E, np.array((135.0, 467.0)), WR], [18.0, 14.5, 10.5]
    )
    u = (WR - E) / np.linalg.norm(WR - E)
    hand_root_start = WR - u * 18.0
    hand_root_end = WR + u * 9.0
    hand_root_mid = (hand_root_start + hand_root_end) / 2
    hand_hidden_root = smooth_ribbon(
        [hand_root_start, hand_root_mid, hand_root_end], [9.5, 10.0, 9.0], 60
    )

    sleeve_hidden = np.zeros((H * AA, W * AA), dtype=np.uint8)
    sleeve_hidden_points = np.array(
        [
            (163, 221),
            (171, 218),
            (179, 225),
            (185, 244),
            (190, 272),
            (192, 307),
            (193, 345),
            (191, 382),
            (185, 414),
            (179, 389),
            (178, 352),
            (175, 318),
            (169, 286),
            (163, 255),
        ],
        dtype=np.float64,
    )
    cv2.fillPoly(
        sleeve_hidden,
        [np.round(sleeve_hidden_points * AA).astype(np.int32)],
        255,
        lineType=cv2.LINE_AA,
    )
    sleeve_hidden = np.array(
        Image.fromarray(sleeve_hidden).resize((W, H), Image.Resampling.LANCZOS),
        dtype=np.uint8,
    )

    complete = {
        "upper_arm": np.maximum(visible["upper_arm"], upper_hidden_body),
        "forearm": np.maximum(visible["forearm"], fore_hidden_body),
        "hand": np.maximum(visible["hand"], hand_hidden_root),
        "sleeve": np.maximum(visible["sleeve"], sleeve_hidden),
    }
    hidden = {
        name: cv2.subtract(complete[name], visible[name]) for name in ORDER
    }
    return complete, hidden


def composite(layers, background=None):
    canvas = (
        background.convert("RGBA").copy()
        if background is not None
        else Image.new("RGBA", (W, H), (0, 0, 0, 0))
    )
    for name in ORDER:
        canvas.alpha_composite(layers[name])
    return canvas


def boundary_overlay(source, masks):
    canvas = source.convert("RGBA").copy()
    for name in ORDER:
        array = mask_array(masks[name])
        edge = cv2.morphologyEx(
            array,
            cv2.MORPH_GRADIENT,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        )
        rgba = np.zeros((H, W, 4), dtype=np.uint8)
        rgba[:, :, :3] = COLORS[name][:3]
        rgba[:, :, 3] = edge
        canvas.alpha_composite(Image.fromarray(rgba, mode="RGBA"))
    return canvas


def crop_scale(image, box, factor=3, resample=Image.Resampling.LANCZOS):
    crop = image.crop(box)
    return crop.resize(
        (crop.width * factor, crop.height * factor), resample=resample
    )


def rotate_translate(image, old_pivot, new_pivot, angle_deg):
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
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


def point_at(origin, length, angle_deg):
    a = math.radians(angle_deg)
    return np.array(
        (origin[0] + length * math.cos(a), origin[1] + length * math.sin(a))
    )


def render_pose(complete_images, theta1, theta2, wrist_local):
    l1, l2 = float(np.linalg.norm(E - S)), float(np.linalg.norm(WR - E))
    rest1 = math.degrees(math.atan2(E[1] - S[1], E[0] - S[0]))
    rest_global = math.degrees(math.atan2(WR[1] - E[1], WR[0] - E[0]))
    new_e = point_at(S, l1, theta1)
    new_w = point_at(new_e, l2, theta1 + theta2)
    d1 = theta1 - rest1
    d2 = theta1 + theta2 - rest_global
    posed = {
        "upper_arm": rotate_translate(
            complete_images["upper_arm"], S, S, d1
        ),
        "forearm": rotate_translate(complete_images["forearm"], E, new_e, d2),
        "hand": rotate_translate(
            complete_images["hand"], WR, new_w, d2 + wrist_local
        ),
        "sleeve": rotate_translate(
            complete_images["sleeve"], S, S, d1 * 0.82
        ),
    }
    return posed, new_e, new_w


def overlap_count(a, b):
    return int(np.count_nonzero((mask_array(a) > 8) & (mask_array(b) > 8)))


def panel(board, image, box, label):
    x0, y0, x1, y1 = box
    area = Image.new("RGB", (x1 - x0, y1 - y0), "white")
    item = image.convert("RGBA")
    item.thumbnail((area.width, area.height), Image.Resampling.LANCZOS)
    x = (area.width - item.width) // 2
    y = (area.height - item.height) // 2
    area.paste(item.convert("RGB"), (x, y), item.getchannel("A"))
    board.paste(area, (x0, y0))
    draw = ImageDraw.Draw(board)
    draw.rectangle(box, outline=(166, 176, 190), width=2)
    draw.text((x0, y1 + 8), label, fill=(29, 39, 53), font=font(23, True))


def main():
    for directory in (
        "materials",
        "masks/visible",
        "masks/hidden",
        "masks/complete",
        "qa",
        "samples",
        "audit",
    ):
        (ROOT / directory).mkdir(parents=True, exist_ok=True)

    source_color = Image.open(SOURCE_COLOR).convert("RGBA")
    source_line = Image.open(SOURCE_LINE).convert("RGBA")
    expected = {
        SOURCE_LINE: "706aaf10652147cf76e233532b5459ce130921a96806f6970c91e1f3a427172f",
        SOURCE_COLOR: "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5",
    }
    for path, digest in expected.items():
        if sha256(path) != digest:
            raise RuntimeError(f"Authority mismatch: {path.name}")
    approval = json.loads(V25_APPROVAL.read_text(encoding="utf-8"))
    if approval["approvedLandmarksPx"] != {
        "shoulder": S.tolist(),
        "elbow": E.tolist(),
        "wrist": WR.tolist(),
    }:
        raise RuntimeError("V25 landmark approval mismatch")
    if json.loads(V26_REJECTION.read_text(encoding="utf-8"))["status"] != "user_visual_rejected":
        raise RuntimeError("Missing V26 visual rejection")

    source_rgb = np.array(source_color.convert("RGB"))
    visible, trace = source_traced_visible_masks(source_rgb)
    complete, hidden = complete_masks(visible)
    visible_images = {}
    complete_images = {}
    for name in ORDER:
        visible_mask = mask_image(visible[name])
        complete_mask = mask_image(complete[name])
        hidden_mask = mask_image(hidden[name])
        visible_mask.save(ROOT / f"masks/visible/{name}.png")
        complete_mask.save(ROOT / f"masks/complete/{name}.png")
        hidden_mask.save(ROOT / f"masks/hidden/{name}.png")
        visible_images[name] = solid(antialiased_alpha(visible_mask), COLORS[name])
        complete_images[name] = solid(antialiased_alpha(complete_mask), COLORS[name])
        complete_images[name].save(ROOT / f"materials/{name}.png")

    l1, l2 = float(np.linalg.norm(E - S)), float(np.linalg.norm(WR - E))
    rest1 = math.degrees(math.atan2(E[1] - S[1], E[0] - S[0]))
    fore_global = math.degrees(math.atan2(WR[1] - E[1], WR[0] - E[0]))
    rest2 = fore_global - rest1
    target1, target2 = rest1 + 6.0, rest2 + 7.0

    skeleton = {
        "schemaVersion": 1,
        "status": "locked_from_user_approved_v25_landmarks",
        "scope": "screen-left arm source-traced Stage A geometry only",
        "approvedEvidence": {
            "candidate": "../arm-chain-screen-left-v25-shoulder-joint-correction/candidate-skeleton.json",
            "approval": "../arm-chain-screen-left-v25-shoulder-joint-correction/audit/user-visual-approval-2026-07-28.json",
        },
        "landmarksPx": {
            "shoulder": S.tolist(),
            "elbow": E.tolist(),
            "wrist": WR.tolist(),
        },
        "boneLengthsPx": {
            "L1ShoulderToElbow": l1,
            "L2ElbowToWrist": l2,
            "tolerancePx": 0.01,
        },
        "restAnglesDeg": {
            "theta1": rest1,
            "theta2": rest2,
            "forearmGlobal": fore_global,
        },
        "stageAQaMotion": {
            "status": "geometry_pull_test_not_user_approved_motion",
            "sampleCount": 41,
            "path": "0_to_1_to_0",
            "target": {
                "theta1": target1,
                "theta2": target2,
                "wristLocal": 2.5,
            },
        },
        "parentChildRelations": [
            {"id": "sleeve", "parent": "shoulder_rotation"},
            {"id": "upper_arm", "parent": "shoulder_rotation"},
            {"id": "forearm", "parent": "elbow_rotation"},
            {"id": "hand", "parent": "wrist_rotation"},
        ],
        "drawOrderBackToFront": [
            {"id": name, "order": 10 * (index + 1)}
            for index, name in enumerate(ORDER)
        ],
    }
    save_json(ROOT / "skeleton-lock.json", skeleton)

    contract = {
        "schemaVersion": 1,
        "status": "source_traced_stage_a_candidate_pending_user_visual_approval",
        "scope": "screen-left sleeve, upper arm, forearm, and hand flat geometry",
        "constructionRule": {
            "visible": "deterministically extracted from Reset color pixels inside source-registered semantic envelopes",
            "hidden": "smooth tapered anatomical or garment continuation; never used to redefine visible source ownership",
            "rejectedEvidence": "V26 is comparison evidence only and is not read as geometry input",
        },
        "layers": [
            {
                "id": "sleeve",
                "visiblePixelOwnership": "source-traced sleeve pixels up to the cuff and hair/torso semantic boundary",
                "hiddenExtension": "garment-flow continuation beneath foreground hair",
                "overlap": "covers upper-arm root and cuff overlap",
                "forbidden": ["hair pixels", "skin below cuff", "background"],
            },
            {
                "id": "upper_arm",
                "visiblePixelOwnership": "source-traced skin between cuff and approved elbow split",
                "hiddenExtension": "smooth tapered shoulder-to-elbow body under sleeve",
                "overlap": "under sleeve at shoulder/cuff and under forearm at elbow",
                "forbidden": ["hair", "shirt torso", "background"],
            },
            {
                "id": "forearm",
                "visiblePixelOwnership": "source-traced skin between elbow and wrist",
                "hiddenExtension": "smooth tapered elbow-to-wrist body through bracelet corridor",
                "overlap": "over upper arm at elbow and under hand at wrist",
                "forbidden": ["shirt torso", "background", "palm"],
            },
            {
                "id": "hand",
                "visiblePixelOwnership": "source-traced palm, thumb, and finger silhouette without polygon simplification",
                "hiddenExtension": "short tapered wrist root beneath bracelet/forearm",
                "overlap": "over forearm at wrist",
                "forbidden": ["forearm shaft", "shirt", "skirt", "background"],
            },
        ],
        "stop": "no texture, PSD, Cubism, mesh, Physics, or Runtime before user visual approval",
    }
    save_json(ROOT / "layering-contract.json", contract)

    default = composite(visible_images)
    default.save(ROOT / "qa/default-recomposition.png")
    outline = boundary_overlay(source_color, {n: mask_image(visible[n]) for n in ORDER})
    outline.save(ROOT / "qa/default-boundary-overlay-original.png")

    displaced = {}
    for name in ORDER:
        ghost = composite(visible_images)
        ghost.putalpha(ghost.getchannel("A").point(lambda value: round(value * 0.18)))
        shifted = complete_images[name].transform(
            (W, H),
            Image.Transform.AFFINE,
            (1, 0, -155, 0, 1, 0),
            resample=Image.Resampling.BICUBIC,
        )
        canvas = checker((W, H)).convert("RGBA")
        canvas.alpha_composite(ghost)
        canvas.alpha_composite(shifted)
        displaced[name] = canvas
        canvas.save(ROOT / f"qa/displaced-{name}.png")

    zoom_boxes = {
        "shoulder-sleeve": (130, 210, 202, 330),
        "elbow": (118, 380, 187, 440),
        "wrist": (88, 500, 142, 553),
        "hand": (54, 532, 130, 628),
    }
    for name, box in zoom_boxes.items():
        crop_scale(outline, box, 7).save(ROOT / f"qa/zoom-{name}.png")

    samples = []
    frames = []
    chosen = {}
    first_hash = last_hash = None
    max_l1_error = max_l2_error = 0.0
    seams_pass = True
    for index in range(41):
        j = index if index <= 20 else 40 - index
        p = 0.5 * (1 - math.cos(math.pi * j / 20))
        theta1 = rest1 + (target1 - rest1) * p
        theta2 = rest2 + (target2 - rest2) * p
        wrist_local = 2.5 * p
        posed, new_e, new_w = render_pose(
            complete_images, theta1, theta2, wrist_local
        )
        pose = composite(posed)
        digest = image_hash(pose)
        if index == 0:
            first_hash = digest
        if index == 40:
            last_hash = digest
        l1_now = float(np.linalg.norm(new_e - S))
        l2_now = float(np.linalg.norm(new_w - new_e))
        max_l1_error = max(max_l1_error, abs(l1_now - l1))
        max_l2_error = max(max_l2_error, abs(l2_now - l2))
        overlaps = {
            "sleeveUpper": overlap_count(posed["sleeve"], posed["upper_arm"]),
            "upperForearm": overlap_count(posed["upper_arm"], posed["forearm"]),
            "forearmHand": overlap_count(posed["forearm"], posed["hand"]),
        }
        seam_ok = all(value > 10 for value in overlaps.values())
        seams_pass = seams_pass and seam_ok
        crop = crop_scale(pose, (0, 190, 220, 650), 2)
        frame = Image.new("RGB", (500, 960), "white")
        frame.paste(crop.convert("RGB"), (30, 28), crop.getchannel("A"))
        draw = ImageDraw.Draw(frame)
        draw.text(
            (15, 5),
            f"样本 {index:02d}｜{p:.2f}",
            fill=(24, 24, 24),
            font=font(20, True),
        )
        frame.save(ROOT / f"samples/fk-{index:03d}.png")
        frames.append(frame.resize((250, 480), Image.Resampling.LANCZOS))
        if index in (0, 10, 20, 30, 40):
            chosen[index] = frames[-1]
        samples.append(
            {
                "index": index,
                "progress": p,
                "theta1Deg": theta1,
                "theta2Deg": theta2,
                "wristLocalDeg": wrist_local,
                "L1ErrorPx": abs(l1_now - l1),
                "L2ErrorPx": abs(l2_now - l2),
                "overlapPixels": overlaps,
                "pass": seam_ok,
            }
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
    contact = Image.new("RGB", (1250, 520), (243, 245, 248))
    for column, index in enumerate((0, 10, 20, 30, 40)):
        contact.paste(chosen[index], (column * 250, 40))
        ImageDraw.Draw(contact).text(
            (column * 250 + 10, 8),
            f"{index:02d}",
            fill=(20, 20, 20),
            font=font(21, True),
        )
    contact.save(ROOT / "qa/fk-selected-contact-sheet.png")

    material_sheet = checker((680, 920), 18).convert("RGBA")
    for index, name in enumerate(ORDER):
        tile_x, tile_y = (index % 2) * 340, (index // 2) * 460
        item = crop_scale(complete_images[name], (45, 200, 215, 650), 2)
        item.thumbnail((290, 400), Image.Resampling.LANCZOS)
        material_sheet.alpha_composite(
            item,
            (
                tile_x + (340 - item.width) // 2,
                tile_y + 45 + (400 - item.height) // 2,
            ),
        )
        ImageDraw.Draw(material_sheet).text(
            (tile_x + 12, tile_y + 8),
            {"upper_arm": "上臂", "forearm": "前臂", "hand": "手", "sleeve": "袖子"}[name],
            fill=(25, 25, 25, 255),
            font=font(23, True),
        )

    displaced_sheet = Image.new("RGB", (2200, 640), (238, 241, 245))
    for index, name in enumerate(ORDER):
        item = displaced[name].crop((25, 190, 400, 660))
        item.thumbnail((500, 550), Image.Resampling.LANCZOS)
        x = index * 550 + (550 - item.width) // 2
        y = 65 + (550 - item.height) // 2
        displaced_sheet.paste(item.convert("RGB"), (x, y))
        ImageDraw.Draw(displaced_sheet).text(
            (index * 550 + 12, 12),
            {
                "upper_arm": "移开上臂：肩根 / 肘端",
                "forearm": "移开前臂：肘 / 腕",
                "hand": "移开手：腕根",
                "sleeve": "移开袖子：肩 / 袖口",
            }[name],
            fill=(28, 28, 28),
            font=font(22, True),
        )

    review = Image.new("RGB", (2400, 2520), (244, 247, 251))
    draw = ImageDraw.Draw(review)
    draw.text(
        (50, 30),
        "小星｜画面左侧手臂 V27 源像素精细分层审查",
        fill=(20, 30, 44),
        font=font(48, True),
    )
    draw.text(
        (50, 98),
        "可见边界逐像素取自 Reset 原稿；平滑曲线只补隐藏材料。请重点看轮廓，不要把纯色误当纹理。",
        fill=(65, 76, 93),
        font=font(27),
    )
    source_crop = crop_scale(source_color, (45, 200, 220, 650), 2)
    default_crop = crop_scale(default, (45, 200, 220, 650), 2)
    outline_crop = crop_scale(outline, (45, 200, 220, 650), 2)
    panel(review, source_crop, (40, 160, 480, 1080), "① 原稿：看袖口、手指和肢体曲线")
    panel(review, default_crop, (500, 160, 940, 1080), "② 纯色回组：轮廓应与原稿一致")
    panel(review, outline_crop, (960, 160, 1400, 1080), "③ 边界叠原稿：彩线不应越界")
    panel(review, material_sheet, (1420, 160, 2100, 1080), "④ 完整材料：看隐藏延伸是否自然")
    panel(review, displaced_sheet, (40, 1160, 2360, 1780), "⑤ 四层分别移开：看隐藏肩、肘、腕和袖口")

    zoom_row = Image.new("RGB", (1080, 390), (238, 241, 245))
    for index, name in enumerate(zoom_boxes):
        item = Image.open(ROOT / f"qa/zoom-{name}.png").convert("RGB")
        item.thumbnail((260, 330), Image.Resampling.LANCZOS)
        zoom_row.paste(item, (index * 270, 48))
        ImageDraw.Draw(zoom_row).text(
            (index * 270 + 8, 8),
            {"shoulder-sleeve": "肩袖", "elbow": "肘", "wrist": "腕", "hand": "手指"}[name],
            fill=(25, 25, 25),
            font=font(22, True),
        )
    panel(review, zoom_row, (40, 1850, 1140, 2260), "⑥ 局部：彩线应紧贴原稿，不能削平曲线")
    panel(review, contact, (1170, 1850, 2360, 2260), "⑦ 0→1→0：手腕与手掌应连续跟随")
    draw.rounded_rectangle(
        (40, 2330, 2360, 2485),
        radius=18,
        fill="white",
        outline=(184, 194, 208),
        width=2,
    )
    draw.text(
        (66, 2350),
        "请逐项批准：回组像原稿｜袖口自然｜肩不侵头发｜肘不僵硬｜腕掌联动｜手指不粗糙｜移开后隐藏材料可信",
        fill=(34, 44, 58),
        font=font(25, True),
    )
    draw.text(
        (66, 2405),
        "若仍失败，请指出最早失败格；本轮继续停在阶段 A，不进入纹理 / PSD / Cubism / Physics / Runtime。",
        fill=(139, 66, 27),
        font=font(24),
    )
    draw.text(
        (66, 2450),
        "本板需要用户肉眼批准；机器的像素、骨长、接缝和回程检查不能替代视觉结论。",
        fill=(76, 86, 101),
        font=font(22),
    )
    review.save(ROOT / "qa/V27-阶段A-中文用户视觉审查板.png")

    visible_union = np.zeros((H, W), dtype=np.uint8)
    for name in ORDER:
        visible_union = np.maximum(visible_union, visible[name])
    source_target = np.maximum(trace["skinCombined"], trace["sleeveCombined"])
    visible_union_difference = int(
        np.count_nonzero((visible_union > 0) != (source_target > 0))
    )
    visible_pair_overlaps = {}
    for i, a in enumerate(ORDER):
        for b in ORDER[i + 1 :]:
            visible_pair_overlaps[f"{a}:{b}"] = int(
                np.count_nonzero((visible[a] > 0) & (visible[b] > 0))
            )
    complete_overlaps = {
        "sleeveUpper": int(
            np.count_nonzero((complete["sleeve"] > 8) & (complete["upper_arm"] > 8))
        ),
        "upperForearm": int(
            np.count_nonzero((complete["upper_arm"] > 8) & (complete["forearm"] > 8))
        ),
        "forearmHand": int(
            np.count_nonzero((complete["forearm"] > 8) & (complete["hand"] > 8))
        ),
    }
    engineering_pass = (
        visible_union_difference == 0
        and all(value == 0 for value in visible_pair_overlaps.values())
        and all(value > 10 for value in complete_overlaps.values())
        and seams_pass
        and max_l1_error < 0.01
        and max_l2_error < 0.01
        and first_hash == last_hash
    )
    report = {
        "schemaVersion": 1,
        "status": (
            "engineering_pass_pending_user_visual_approval"
            if engineering_pass
            else "engineering_fail_stop_stage_a"
        ),
        "scope": "screen-left V27 source-traced Stage A geometry",
        "authority": {
            "lineMasterSha256": sha256(SOURCE_LINE),
            "colorMasterSha256": sha256(SOURCE_COLOR),
            "v25ApprovalSha256": sha256(V25_APPROVAL),
            "v26RejectionSha256": sha256(V26_REJECTION),
            "pass": True,
        },
        "sourceTracing": {
            "visibleUnionDifferencePixels": visible_union_difference,
            "visibleLayerOverlapPixels": visible_pair_overlaps,
            "skinContourPointCount": trace["skinContourPointCount"],
            "sleeveContourPointCount": trace["sleeveContourPointCount"],
            "pass": visible_union_difference == 0
            and all(value == 0 for value in visible_pair_overlaps.values()),
        },
        "boneLengths": {
            "L1Px": l1,
            "L2Px": l2,
            "maxL1ErrorPx": max_l1_error,
            "maxL2ErrorPx": max_l2_error,
            "pass": max_l1_error < 0.01 and max_l2_error < 0.01,
        },
        "seams": {
            "defaultCompleteOverlapPixels": complete_overlaps,
            "all41SamplesPass": seams_pass,
            "pass": seams_pass and all(value > 10 for value in complete_overlaps.values()),
        },
        "disconnects": {"count": 0 if seams_pass else 1, "pass": seams_pass},
        "returnConsistency": {
            "firstPoseSha256": first_hash,
            "lastPoseSha256": last_hash,
            "pass": first_hash == last_hash,
        },
        "visualGate": {
            "status": "pending_user_visual_approval",
            "review": "qa/V27-阶段A-中文用户视觉审查板.png",
            "earliestFailurePoint": None,
            "required": [
                "default resemblance",
                "natural cuff transition",
                "no shoulder/hair intrusion",
                "anatomical elbow",
                "wrist and palm follow forearm",
                "non-coarse hand contour",
                "credible displaced hidden material",
            ],
        },
        "stop": "remain at Stage A until user approval",
    }
    save_json(ROOT / "audit/machine-report.json", report)
    (ROOT / "audit/MACHINE-REPORT.zh-CN.md").write_text(
        "\n".join(
            [
                "# V27 阶段 A 机器报告",
                "",
                f"- 状态：`{report['status']}`",
                f"- 源轮廓回组差异：`{visible_union_difference}px`",
                f"- 手臂源轮廓点数：`{trace['skinContourPointCount']}`",
                f"- 袖子源轮廓点数：`{trace['sleeveContourPointCount']}`",
                f"- 骨长最大误差：L1 `{max_l1_error:.9f}px`；L2 `{max_l2_error:.9f}px`",
                f"- 41 样本接缝：`{'通过' if seams_pass else '失败'}`",
                f"- 回程一致：`{'通过' if first_hash == last_hash else '失败'}`",
                "",
                "机器结果不能替代用户对轮廓、人体结构和隐藏材料的肉眼批准。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {"schemaVersion": 1, "status": report["status"], "files": []}
    for path in sorted(ROOT.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path != ROOT / "audit/artifact-manifest.json"
        ):
            manifest["files"].append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    save_json(ROOT / "audit/artifact-manifest.json", manifest)
    print(
        json.dumps(
            {
                "status": report["status"],
                "files": len(manifest["files"]),
                "sourceDifferencePx": visible_union_difference,
                "skinContourPoints": trace["skinContourPointCount"],
                "sleeveContourPoints": trace["sleeveContourPointCount"],
                "seamsPass": seams_pass,
                "returnPass": first_hash == last_hash,
                "review": report["visualGate"]["review"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
