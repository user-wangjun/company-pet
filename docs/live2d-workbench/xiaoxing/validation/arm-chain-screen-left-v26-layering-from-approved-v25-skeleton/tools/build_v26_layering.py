from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
XIAOXING = ROOT.parents[1]
SOURCE_LINE = XIAOXING / "source/masters/front-line-source-exact-after-reset.png"
SOURCE_COLOR = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
V25 = XIAOXING / "validation/arm-chain-screen-left-v25-shoulder-joint-correction"
V25_SKELETON = V25 / "candidate-skeleton.json"
V25_APPROVAL = V25 / "audit/user-visual-approval-2026-07-28.json"

W, H = 512, 1086
SCALE = 4
SHOULDER = (170.0, 251.0)
ELBOW = (147.0, 405.0)
WRIST = (115.0, 529.0)

COLORS = {
    "upper_arm": (239, 126, 105, 255),
    "forearm": (245, 174, 66, 255),
    "hand": (65, 181, 139, 255),
    "sleeve": (66, 132, 207, 255),
}
DRAW_ORDER = ["upper_arm", "forearm", "hand", "sleeve"]


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


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def scale_points(points):
    return [(round(x * SCALE), round(y * SCALE)) for x, y in points]


def polygon_mask(points) -> Image.Image:
    large = Image.new("L", (W * SCALE, H * SCALE), 0)
    ImageDraw.Draw(large).polygon(scale_points(points), fill=255)
    return large.resize((W, H), Image.Resampling.LANCZOS)


def subtract(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.subtract(a, b)


def intersection(a: Image.Image, b: Image.Image) -> Image.Image:
    return ImageChops.multiply(a, b)


def solid(mask: Image.Image, color) -> Image.Image:
    image = Image.new("RGBA", (W, H), color)
    image.putalpha(mask)
    return image


def composite_layers(layers: dict[str, Image.Image], background=None) -> Image.Image:
    canvas = (
        background.convert("RGBA").copy()
        if background is not None
        else Image.new("RGBA", (W, H), (0, 0, 0, 0))
    )
    for name in DRAW_ORDER:
        canvas.alpha_composite(layers[name])
    return canvas


def crop_scale(image: Image.Image, box, factor=3, resample=Image.Resampling.NEAREST):
    crop = image.crop(box)
    return crop.resize((crop.width * factor, crop.height * factor), resample)


def checker(size, cell=16):
    image = Image.new("RGB", size, (238, 238, 238))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(207, 207, 207))
    return image


def paste_fit(board, image, box, background=(248, 248, 248)):
    x0, y0, x1, y1 = box
    area = Image.new("RGB", (x1 - x0, y1 - y0), background)
    source = image.convert("RGBA")
    source.thumbnail((area.width, area.height), Image.Resampling.LANCZOS)
    ox = (area.width - source.width) // 2
    oy = (area.height - source.height) // 2
    area.paste(source.convert("RGB"), (ox, oy), source.getchannel("A"))
    board.paste(area, (x0, y0))
    ImageDraw.Draw(board).rectangle(box, outline=(170, 177, 188), width=2)


def rotate_translate(image, old_pivot, new_pivot, angle_deg):
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    ox, oy = old_pivot
    nx, ny = new_pivot
    # Forward: q = R * (p-old) + new. Pillow needs the inverse.
    a, b = c, s
    d, e = -s, c
    c0 = ox - c * nx - s * ny
    f0 = oy + s * nx - c * ny
    return image.transform(
        (W, H),
        Image.Transform.AFFINE,
        (a, b, c0, d, e, f0),
        resample=Image.Resampling.BICUBIC,
    )


def point_at(origin, length, angle_deg):
    angle = math.radians(angle_deg)
    return (
        origin[0] + length * math.cos(angle),
        origin[1] + length * math.sin(angle),
    )


def disk_mask(center, radius):
    mask = Image.new("L", (W, H), 0)
    x, y = center
    ImageDraw.Draw(mask).ellipse(
        (x - radius, y - radius, x + radius, y + radius), fill=255
    )
    return mask


def nonzero(mask):
    return sum(1 for value in mask.getdata() if value > 8)


def make_masks():
    # All boundaries are newly traced against the Reset masters. Old V13-V24
    # masks are deliberately not read.
    sleeve_visible = polygon_mask(
        [
            (164, 225),
            (155, 231),
            (147, 242),
            (138, 260),
            (128, 286),
            (117, 314),
            (107, 342),
            (98, 370),
            (103, 375),
            (119, 384),
            (138, 394),
            (158, 403),
            (181, 413),
            (184, 402),
            (184, 374),
            (182, 348),
            (178, 325),
            (172, 302),
            (165, 279),
            (160, 255),
        ]
    )
    hair_occlusion = polygon_mask(
        [
            (174, 215),
            (210, 215),
            (210, 382),
            (184, 382),
            (184, 351),
            (181, 335),
            (177, 319),
            (172, 301),
            (167, 280),
            (164, 258),
            (165, 242),
            (169, 228),
        ]
    )
    sleeve_visible = subtract(sleeve_visible, hair_occlusion)
    sleeve_complete = polygon_mask(
        [
            (164, 225),
            (155, 231),
            (147, 242),
            (138, 260),
            (128, 286),
            (117, 314),
            (107, 342),
            (98, 370),
            (103, 375),
            (119, 384),
            (138, 394),
            (158, 403),
            (181, 413),
            (188, 405),
            (190, 376),
            (191, 342),
            (190, 305),
            (187, 274),
            (181, 248),
            (174, 231),
        ]
    )

    upper_visible = polygon_mask(
        [
            (137, 390),
            (148, 395),
            (162, 401),
            (181, 411),
            (178, 421),
            (172, 427),
            (159, 424),
            (146, 418),
            (138, 412),
        ]
    )
    upper_complete = polygon_mask(
        [
            (157, 247),
            (153, 274),
            (151, 306),
            (148, 339),
            (144, 372),
            (137, 397),
            (138, 413),
            (147, 421),
            (159, 425),
            (170, 409),
            (175, 381),
            (178, 345),
            (181, 309),
            (183, 276),
            (180, 251),
            (171, 245),
        ]
    )

    forearm_visible = polygon_mask(
        [
            (136, 399),
            (133, 417),
            (129, 440),
            (124, 463),
            (119, 485),
            (112, 508),
            (104, 527),
            (106, 537),
            (116, 542),
            (126, 538),
            (134, 526),
            (143, 509),
            (152, 489),
            (161, 466),
            (168, 444),
            (174, 422),
            (171, 409),
            (158, 402),
            (146, 399),
        ]
    )
    forearm_complete = polygon_mask(
        [
            (135, 397),
            (132, 416),
            (128, 439),
            (123, 462),
            (118, 485),
            (111, 507),
            (103, 526),
            (103, 540),
            (112, 548),
            (123, 546),
            (133, 532),
            (143, 511),
            (153, 490),
            (162, 467),
            (169, 444),
            (175, 421),
            (171, 407),
            (158, 399),
            (146, 396),
        ]
    )

    hand_visible = polygon_mask(
        [
            (101, 529),
            (98, 542),
            (93, 556),
            (85, 570),
            (76, 582),
            (68, 592),
            (61, 605),
            (60, 612),
            (63, 615),
            (68, 613),
            (74, 606),
            (81, 595),
            (86, 587),
            (82, 598),
            (75, 611),
            (70, 618),
            (71, 622),
            (75, 622),
            (80, 616),
            (85, 604),
            (88, 597),
            (85, 608),
            (80, 617),
            (81, 621),
            (85, 621),
            (90, 614),
            (94, 603),
            (96, 595),
            (94, 606),
            (91, 614),
            (93, 617),
            (97, 616),
            (101, 608),
            (104, 599),
            (105, 590),
            (106, 581),
            (109, 574),
            (114, 567),
            (116, 554),
            (116, 538),
            (112, 530),
        ]
    )
    hand_complete = polygon_mask(
        [
            (103, 516),
            (99, 537),
            (93, 556),
            (85, 570),
            (76, 582),
            (68, 592),
            (61, 605),
            (60, 612),
            (63, 615),
            (68, 613),
            (74, 606),
            (81, 595),
            (86, 587),
            (82, 598),
            (75, 611),
            (70, 618),
            (71, 622),
            (75, 622),
            (80, 616),
            (85, 604),
            (88, 597),
            (85, 608),
            (80, 617),
            (81, 621),
            (85, 621),
            (90, 614),
            (94, 603),
            (96, 595),
            (94, 606),
            (91, 614),
            (93, 617),
            (97, 616),
            (101, 608),
            (104, 599),
            (105, 590),
            (106, 581),
            (109, 574),
            (114, 567),
            (118, 551),
            (119, 532),
            (116, 519),
            (110, 515),
        ]
    )

    visible = {
        "sleeve": sleeve_visible,
        "upper_arm": upper_visible,
        "forearm": forearm_visible,
        "hand": hand_visible,
    }
    complete = {
        "sleeve": sleeve_complete,
        "upper_arm": upper_complete,
        "forearm": forearm_complete,
        "hand": hand_complete,
    }
    hidden = {name: subtract(complete[name], visible[name]) for name in visible}
    return visible, complete, hidden


def render_displaced(name, complete_layers, visible_layers):
    base = composite_layers(visible_layers)
    ghost = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ghost.alpha_composite(base)
    ghost.putalpha(ghost.getchannel("A").point(lambda p: round(p * 0.22)))
    shifted = complete_layers[name].transform(
        (W, H),
        Image.Transform.AFFINE,
        (1, 0, -150, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )
    canvas = checker((W, H)).convert("RGBA")
    canvas.alpha_composite(ghost)
    canvas.alpha_composite(shifted)
    return canvas


def sample_pose(complete_layers, theta1, theta2, wrist_local):
    l1 = math.dist(SHOULDER, ELBOW)
    l2 = math.dist(ELBOW, WRIST)
    rest1 = math.degrees(
        math.atan2(ELBOW[1] - SHOULDER[1], ELBOW[0] - SHOULDER[0])
    )
    rest_global2 = math.degrees(
        math.atan2(WRIST[1] - ELBOW[1], WRIST[0] - ELBOW[0])
    )
    new_elbow = point_at(SHOULDER, l1, theta1)
    new_wrist = point_at(new_elbow, l2, theta1 + theta2)
    shoulder_delta = theta1 - rest1
    forearm_delta = (theta1 + theta2) - rest_global2
    transformed = {
        "sleeve": rotate_translate(
            complete_layers["sleeve"], SHOULDER, SHOULDER, shoulder_delta * 0.82
        ),
        "upper_arm": rotate_translate(
            complete_layers["upper_arm"], SHOULDER, SHOULDER, shoulder_delta
        ),
        "forearm": rotate_translate(
            complete_layers["forearm"], ELBOW, new_elbow, forearm_delta
        ),
        "hand": rotate_translate(
            complete_layers["hand"],
            WRIST,
            new_wrist,
            forearm_delta + wrist_local,
        ),
    }
    return transformed, new_elbow, new_wrist


def main():
    for directory in [
        "materials",
        "masks/visible",
        "masks/hidden",
        "masks/complete",
        "qa",
        "samples",
        "audit",
    ]:
        (ROOT / directory).mkdir(parents=True, exist_ok=True)

    source_line = Image.open(SOURCE_LINE).convert("RGBA")
    source_color = Image.open(SOURCE_COLOR).convert("RGBA")
    if source_line.size != (W, H) or source_color.size != (W, H):
        raise RuntimeError("Reset master canvas mismatch")
    expected_hashes = {
        SOURCE_LINE: "706aaf10652147cf76e233532b5459ce130921a96806f6970c91e1f3a427172f",
        SOURCE_COLOR: "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5",
    }
    for path, expected in expected_hashes.items():
        if sha256(path) != expected:
            raise RuntimeError(f"Authority hash mismatch: {path.name}")

    approved = json.loads(V25_APPROVAL.read_text(encoding="utf-8"))
    candidate = json.loads(V25_SKELETON.read_text(encoding="utf-8"))
    joints = approved["approvedLandmarksPx"]
    if tuple(joints["shoulder"]) != SHOULDER:
        raise RuntimeError("Approved shoulder mismatch")
    if tuple(joints["elbow"]) != ELBOW or tuple(joints["wrist"]) != WRIST:
        raise RuntimeError("Approved elbow/wrist mismatch")
    if candidate["candidateV25"]["shoulder"] != list(SHOULDER):
        raise RuntimeError("Candidate and approval disagree")

    l1 = math.dist(SHOULDER, ELBOW)
    l2 = math.dist(ELBOW, WRIST)
    rest1 = math.degrees(
        math.atan2(ELBOW[1] - SHOULDER[1], ELBOW[0] - SHOULDER[0])
    )
    forearm_global = math.degrees(
        math.atan2(WRIST[1] - ELBOW[1], WRIST[0] - ELBOW[0])
    )
    rest2 = forearm_global - rest1
    target1 = rest1 + 8.0
    target2 = rest2 + 10.0

    skeleton_lock = {
        "schemaVersion": 1,
        "status": "landmarks_user_approved_stage_a_locked",
        "scope": "screen-left arm Stage A flat geometry only",
        "approvedEvidence": {
            "candidate": "../arm-chain-screen-left-v25-shoulder-joint-correction/candidate-skeleton.json",
            "approval": "../arm-chain-screen-left-v25-shoulder-joint-correction/audit/user-visual-approval-2026-07-28.json",
            "review": "../arm-chain-screen-left-v25-shoulder-joint-correction/qa/V25-SCREEN-LEFT-SHOULDER-CORRECTION-REVIEW.zh-CN.png",
        },
        "authoritativeInputs": [
            {
                "path": "source/masters/front-line-source-exact-after-reset.png",
                "sha256": sha256(SOURCE_LINE),
            },
            {
                "path": "source/masters/front-color-source-exact-after-reset.png",
                "sha256": sha256(SOURCE_COLOR),
            },
        ],
        "landmarksPx": {
            "shoulder": list(SHOULDER),
            "elbow": list(ELBOW),
            "wrist": list(WRIST),
        },
        "boneLengthsPx": {
            "L1ShoulderToElbow": l1,
            "L2ElbowToWrist": l2,
            "analyticTolerancePx": 0.01,
        },
        "restAnglesDeg": {
            "theta1": rest1,
            "theta2": rest2,
            "forearmGlobal": forearm_global,
        },
        "stageAQaAngleEnvelopeDeg": {
            "provenance": "bilateral relative offsets from the approved screen-right skeleton; used only as a flat-geometry pull test, not as motion approval",
            "theta1": {"min": rest1 - 8.0, "max": rest1 + 8.0},
            "theta2": {"min": max(0.0, rest2 - 6.0), "max": rest2 + 18.0},
            "wristLocal": {"min": -4.0, "max": 4.0},
        },
        "primaryQaMotion": {
            "path": "0_to_1_to_0",
            "sampleCount": 41,
            "rest": {"theta1": rest1, "theta2": rest2, "wristLocal": 0.0},
            "target": {
                "theta1": target1,
                "theta2": target2,
                "wristLocal": 3.0,
            },
        },
        "parentChildRelations": [
            {"id": "shoulder_rotation", "parent": "torso_out_of_scope"},
            {"id": "sleeve", "parent": "shoulder_rotation"},
            {"id": "upper_arm", "parent": "shoulder_rotation"},
            {"id": "elbow_rotation", "parent": "shoulder_rotation"},
            {"id": "forearm", "parent": "elbow_rotation"},
            {"id": "wrist_rotation", "parent": "elbow_rotation"},
            {"id": "hand", "parent": "wrist_rotation"},
        ],
        "drawOrderBackToFront": [
            {"id": name, "order": (index + 1) * 10}
            for index, name in enumerate(DRAW_ORDER)
        ],
        "limits": [
            "the QA angle envelope is not a user-approved motion range",
            "no texture, mesh, Cubism, Physics, or Runtime is authorized",
        ],
    }
    save_json(ROOT / "skeleton-lock.json", skeleton_lock)

    visible_masks, complete_masks, hidden_masks = make_masks()
    visible_layers = {}
    complete_layers = {}
    for name in DRAW_ORDER:
        visible_masks[name].save(ROOT / f"masks/visible/{name}.png")
        complete_masks[name].save(ROOT / f"masks/complete/{name}.png")
        hidden_masks[name].save(ROOT / f"masks/hidden/{name}.png")
        visible_layers[name] = solid(visible_masks[name], COLORS[name])
        complete_layers[name] = solid(complete_masks[name], COLORS[name])
        complete_layers[name].save(ROOT / f"materials/{name}.png")

    layering_contract = {
        "schemaVersion": 1,
        "status": "stage_a_geometry_candidate_pending_user_visual_approval",
        "scope": "screen-left sleeve, upper arm, forearm, and hand flat geometry only",
        "sourceRule": "all boundaries newly traced from Reset masters; V13-V24 materials are failure comparison only and were not read by the builder",
        "layers": [
            {
                "id": "upper_arm",
                "visiblePixelOwnership": "skin between the sleeve opening and the internal elbow split",
                "hiddenExtensionResponsibility": "continuous tapered upper-arm skin from the approved shoulder beneath the sleeve",
                "overlapResponsibility": ["under sleeve at cuff", "under forearm at elbow"],
                "forbiddenIntrusion": ["hair", "shirt torso", "background"],
                "parent": "shoulder_rotation",
                "drawOrder": 10,
            },
            {
                "id": "forearm",
                "visiblePixelOwnership": "tapered skin from elbow through the bracelet/wrist region",
                "hiddenExtensionResponsibility": "continuous elbow and wrist roots; bracelet interruption may not create an anatomical hole",
                "overlapResponsibility": ["over upper arm at elbow", "under hand at wrist"],
                "forbiddenIntrusion": ["shirt torso", "background", "hand palm"],
                "parent": "elbow_rotation",
                "drawOrder": 20,
            },
            {
                "id": "hand",
                "visiblePixelOwnership": "palm, thumb, and all visible finger silhouettes from the Reset master",
                "hiddenExtensionResponsibility": "narrow wrist root beneath the bracelet/forearm overlap",
                "overlapResponsibility": ["over forearm at wrist"],
                "forbiddenIntrusion": ["forearm shaft", "shirt", "skirt", "background"],
                "parent": "wrist_rotation",
                "drawOrder": 30,
            },
            {
                "id": "sleeve",
                "visiblePixelOwnership": "the original screen-left garment sleeve silhouette and cuff opening",
                "hiddenExtensionResponsibility": "garment continuation beneath the hair and torso-side occlusion without a shoulder bulge",
                "overlapResponsibility": ["over upper arm at cuff", "beneath foreground hair"],
                "forbiddenIntrusion": ["skin below cuff", "hair pixels", "background outside garment silhouette"],
                "parent": "shoulder_rotation",
                "drawOrder": 40,
            },
        ],
        "defaultCompositeRule": "visible masks are used for source-registered rest review; complete materials are used for displaced and FK overlap review",
        "braceletStageAResponsibility": "the bracelet occlusion corridor belongs to the forearm geometry in this four-layer-only checkpoint; texture/accessory separation is out of scope",
        "stopConditions": [
            "default visible composite does not read as the source arm",
            "shoulder or sleeve intrudes into hair/background",
            "hidden geometry looks like a circular patch or mechanical plug",
            "elbow or wrist overlap is not anatomically continuous",
            "hand reads as a static attached sticker",
        ],
    }
    save_json(ROOT / "layering-contract.json", layering_contract)

    default = composite_layers(visible_layers)
    default.save(ROOT / "qa/default-recomposition.png")
    overlay = source_color.copy()
    tinted = default.copy()
    tinted.putalpha(tinted.getchannel("A").point(lambda p: round(p * 0.56)))
    overlay.alpha_composite(tinted)
    overlay.save(ROOT / "qa/default-overlay-original.png")

    for name in DRAW_ORDER:
        render_displaced(name, complete_layers, visible_layers).save(
            ROOT / f"qa/displaced-{name}.png"
        )

    zoom_specs = {
        "shoulder-sleeve": (130, 215, 205, 325),
        "elbow": (115, 370, 190, 455),
        "wrist": (85, 495, 145, 555),
        "hand": (55, 525, 145, 655),
    }
    overlay_lines = source_color.copy()
    overlay_lines.alpha_composite(tinted)
    for name, box in zoom_specs.items():
        crop_scale(overlay_lines, box, 5).save(ROOT / f"qa/zoom-{name}.png")

    samples = []
    first_pose_hash = None
    last_pose_hash = None
    all_seams_pass = True
    max_l1_error = 0.0
    max_l2_error = 0.0
    preview_frames = []
    selected = {}
    for index in range(41):
        j = index if index <= 20 else 40 - index
        p = 0.5 * (1.0 - math.cos(math.pi * j / 20.0))
        theta1 = rest1 + (target1 - rest1) * p
        theta2 = rest2 + (target2 - rest2) * p
        wrist_local = 3.0 * p
        posed_masks, new_elbow, new_wrist = sample_pose(
            complete_masks, theta1, theta2, wrist_local
        )
        posed_layers = {
            name: solid(posed_masks[name], COLORS[name]) for name in DRAW_ORDER
        }
        pose = composite_layers(posed_layers)
        pose_hash = image_hash(pose)
        if index == 0:
            first_pose_hash = pose_hash
        if index == 40:
            last_pose_hash = pose_hash

        l1_now = math.dist(SHOULDER, new_elbow)
        l2_now = math.dist(new_elbow, new_wrist)
        max_l1_error = max(max_l1_error, abs(l1_now - l1))
        max_l2_error = max(max_l2_error, abs(l2_now - l2))
        seam_counts = {
            "shoulderSleeve": nonzero(
                intersection(
                    intersection(posed_masks["sleeve"], posed_masks["upper_arm"]),
                    disk_mask(SHOULDER, 28),
                )
            ),
            "elbow": nonzero(
                intersection(
                    intersection(posed_masks["upper_arm"], posed_masks["forearm"]),
                    disk_mask(new_elbow, 24),
                )
            ),
            "wrist": nonzero(
                intersection(
                    intersection(posed_masks["forearm"], posed_masks["hand"]),
                    disk_mask(new_wrist, 22),
                )
            ),
        }
        seam_pass = all(value > 10 for value in seam_counts.values())
        all_seams_pass = all_seams_pass and seam_pass

        frame = Image.new("RGB", (560, 1000), "white")
        crop = crop_scale(pose, (0, 190, 220, 665), 2)
        frame.paste(crop.convert("RGB"), (60, 35), crop.getchannel("A"))
        draw = ImageDraw.Draw(frame)
        draw.text(
            (20, 10),
            f"样本 {index:02d}｜进度 {p:.2f}",
            fill=(25, 25, 25),
            font=font(24, True),
        )
        draw.text(
            (18, 952),
            f"肩 {theta1:.2f}°  肘 {theta2:.2f}°  腕 +{wrist_local:.2f}°",
            fill=(45, 45, 45),
            font=font(18),
        )
        frame.save(ROOT / f"samples/fk-{index:03d}.png")
        preview_frames.append(frame.resize((280, 500), Image.Resampling.LANCZOS))
        if index in (0, 10, 20, 30, 40):
            selected[index] = frame
        samples.append(
            {
                "index": index,
                "progress": p,
                "theta1Deg": theta1,
                "theta2Deg": theta2,
                "wristLocalDeg": wrist_local,
                "elbowPx": list(new_elbow),
                "wristPx": list(new_wrist),
                "L1ErrorPx": abs(l1_now - l1),
                "L2ErrorPx": abs(l2_now - l2),
                "seamOverlapPixels": seam_counts,
                "seamPass": seam_pass,
            }
        )
    save_json(ROOT / "samples/fk-41-samples.json", samples)
    preview_frames[0].save(
        ROOT / "qa/fk-41-slow-preview.gif",
        save_all=True,
        append_images=preview_frames[1:],
        duration=180,
        loop=0,
        disposal=2,
    )

    contact = Image.new("RGB", (280 * 5, 540), (242, 244, 247))
    for col, index in enumerate((0, 10, 20, 30, 40)):
        panel = selected[index].resize((280, 500), Image.Resampling.LANCZOS)
        contact.paste(panel, (col * 280, 40))
        ImageDraw.Draw(contact).text(
            (col * 280 + 12, 8),
            f"{index:02d}",
            fill=(20, 20, 20),
            font=font(22, True),
        )
    contact.save(ROOT / "qa/fk-selected-contact-sheet.png")

    source_crop = crop_scale(source_color, (55, 200, 220, 665), 2)
    default_crop = crop_scale(default, (55, 200, 220, 665), 2)
    overlay_crop = crop_scale(overlay, (55, 200, 220, 665), 2)
    material_sheet = checker((660, 930), 18).convert("RGBA")
    for idx, name in enumerate(DRAW_ORDER):
        isolated = crop_scale(complete_layers[name], (55, 200, 220, 665), 2)
        x = (idx % 2) * 330
        y = (idx // 2) * 465
        isolated.thumbnail((280, 405), Image.Resampling.LANCZOS)
        tile_x = x + (330 - isolated.width) // 2
        tile_y = y + 40 + (405 - isolated.height) // 2
        material_sheet.alpha_composite(isolated, (tile_x, tile_y))
        ImageDraw.Draw(material_sheet).text(
            (x + 12, y + 8),
            {
                "upper_arm": "上臂",
                "forearm": "前臂",
                "hand": "手",
                "sleeve": "袖子",
            }[name],
            fill=(30, 30, 30, 255),
            font=font(23, True),
        )

    displaced_sheet = Image.new("RGB", (2200, 650), (238, 241, 245))
    displaced_draw = ImageDraw.Draw(displaced_sheet)
    for idx, name in enumerate(DRAW_ORDER):
        displaced = Image.open(ROOT / f"qa/displaced-{name}.png").convert("RGB")
        displaced = displaced.crop((35, 190, 390, 675))
        displaced.thumbnail((500, 565), Image.Resampling.LANCZOS)
        x = idx * 550 + (550 - displaced.width) // 2
        y = 55 + (565 - displaced.height) // 2
        displaced_sheet.paste(displaced, (x, y))
        displaced_draw.text(
            (idx * 550 + 14, 12),
            {
                "upper_arm": "移开上臂：看肩根与肘端",
                "forearm": "移开前臂：看肘与腕",
                "hand": "移开手：看腕根",
                "sleeve": "移开袖子：看袖口与肩",
            }[name],
            fill=(30, 30, 30),
            font=font(22, True),
        )

    review = Image.new("RGB", (2400, 2510), (244, 247, 251))
    draw = ImageDraw.Draw(review)
    draw.text(
        (55, 35),
        "小星｜画面左侧手臂 V26 阶段 A 分层几何审查",
        fill=(22, 31, 45),
        font=font(48, True),
    )
    draw.text(
        (55, 102),
        "只审袖子 / 上臂 / 前臂 / 手的几何与遮挡；纯色不是纹理。机器通过不等于视觉通过。",
        fill=(64, 75, 92),
        font=font(27),
    )
    boxes = [
        ((45, 165, 485, 1095), source_crop, "① 原稿：看自然轮廓与袖口"),
        ((505, 165, 945, 1095), default_crop, "② 默认回组：看是否像一条手臂"),
        ((965, 165, 1405, 1095), overlay_crop, "③ 叠原稿：看侵入与偏粗"),
        ((1425, 165, 2085, 1095), material_sheet, "④ 四层完整材料：看隐藏延伸"),
    ]
    for box, image, label in boxes:
        paste_fit(review, image, box)
        draw.text((box[0], box[3] + 10), label, fill=(35, 45, 58), font=font(23, True))

    paste_fit(review, displaced_sheet, (45, 1180, 2355, 1815))
    draw.text(
        (45, 1825),
        "⑤ 四层分别移开：必须能看到可信的隐藏延伸，不能是圆补丁或机械插头",
        fill=(35, 45, 58),
        font=font(23, True),
    )

    zoom_row = Image.new("RGB", (1080, 390), (238, 241, 245))
    for idx, name in enumerate(zoom_specs):
        image = Image.open(ROOT / f"qa/zoom-{name}.png").convert("RGB")
        image.thumbnail((260, 330), Image.Resampling.LANCZOS)
        zoom_row.paste(image, (idx * 270, 45))
        ImageDraw.Draw(zoom_row).text(
            (idx * 270 + 8, 8),
            {"shoulder-sleeve": "肩袖", "elbow": "肘", "wrist": "腕", "hand": "手"}[name],
            fill=(25, 25, 25),
            font=font(22, True),
        )
    paste_fit(review, zoom_row, (45, 1890, 1145, 2300))
    draw.text((45, 2310), "⑥ 局部：逐格看肩袖、肘、腕、手轮廓", fill=(35, 45, 58), font=font(23, True))

    paste_fit(review, contact, (1175, 1890, 2355, 2300))
    draw.text((1175, 2310), "⑦ 0→1→0：腕与手掌必须随前臂自然带动", fill=(35, 45, 58), font=font(23, True))

    draw.rounded_rectangle(
        (45, 2370, 2355, 2475), radius=18, fill=(255, 255, 255), outline=(188, 196, 208), width=2
    )
    draw.text(
        (70, 2385),
        "请批准前逐项确认：默认回组像原稿｜袖口自然｜肩不突入头发｜肘符合人体｜腕与手掌联动｜手不过粗｜移开后隐藏材料可信",
        fill=(38, 47, 61),
        font=font(25, True),
    )
    draw.text(
        (70, 2430),
        "若任一项失败，请指出最早失败处；本轮将停在阶段 A，不进入纹理 / PSD / Cubism / Physics / Runtime。",
        fill=(139, 68, 28),
        font=font(24),
    )
    review.save(ROOT / "qa/V26-阶段A-中文用户视觉审查板.png")

    overlap_default = {
        "sleeveUpperArm": nonzero(
            intersection(complete_masks["sleeve"], complete_masks["upper_arm"])
        ),
        "upperArmForearm": nonzero(
            intersection(complete_masks["upper_arm"], complete_masks["forearm"])
        ),
        "forearmHand": nonzero(
            intersection(complete_masks["forearm"], complete_masks["hand"])
        ),
    }
    engineering_pass = (
        max_l1_error < 0.01
        and max_l2_error < 0.01
        and all_seams_pass
        and first_pose_hash == last_pose_hash
        and all(value > 10 for value in overlap_default.values())
    )
    report = {
        "schemaVersion": 1,
        "status": (
            "engineering_pass_pending_user_visual_approval"
            if engineering_pass
            else "engineering_fail_stop_stage_a"
        ),
        "scope": "screen-left arm Stage A flat layering geometry",
        "authorityIntegrity": {
            "lineMasterSha256": sha256(SOURCE_LINE),
            "colorMasterSha256": sha256(SOURCE_COLOR),
            "v25ApprovalSha256": sha256(V25_APPROVAL),
            "pass": True,
        },
        "skeleton": {
            "shoulder": list(SHOULDER),
            "elbow": list(ELBOW),
            "wrist": list(WRIST),
            "L1Px": l1,
            "L2Px": l2,
            "maxL1ErrorPx": max_l1_error,
            "maxL2ErrorPx": max_l2_error,
            "pass": max_l1_error < 0.01 and max_l2_error < 0.01,
        },
        "seams": {
            "defaultOverlapPixels": overlap_default,
            "all41SamplesPass": all_seams_pass,
            "pass": all_seams_pass and all(value > 10 for value in overlap_default.values()),
        },
        "disconnects": {
            "analyticCriterion": "each parent-child material pair has positive overlap at every sampled joint",
            "count": 0 if all_seams_pass else 1,
            "pass": all_seams_pass,
        },
        "returnConsistency": {
            "firstPoseRgbaSha256": first_pose_hash,
            "lastPoseRgbaSha256": last_pose_hash,
            "pass": first_pose_hash == last_pose_hash,
        },
        "visualGate": {
            "status": "pending_user_visual_approval",
            "review": "qa/V26-阶段A-中文用户视觉审查板.png",
            "internalPreflight": {
                "defaultCompositeReadsAsOneArm": "candidate_yes_user_confirmation_required",
                "sleeveToUpperArm": "candidate_natural_user_confirmation_required",
                "shoulderHairIntrusion": "no_visible_intrusion_detected_after_hair_occlusion_subtraction",
                "elbowContinuity": "candidate_continuous_user_confirmation_required",
                "wristAndPalmFollowForearm": "present_in_41_sample_QA_motion",
                "handContour": "retraced_against_Reset_line_master_after_initial_coarse_candidate",
                "displacedHiddenMaterials": "all_four_shown_on_main_review_board",
                "earliestFailurePoint": None,
            },
            "requiredQuestions": [
                "默认回组是否像原图",
                "袖口到上臂是否自然",
                "肩部是否错误突出或侵入头发",
                "肘部是否符合人体结构",
                "腕部和手掌是否随前臂自然运动",
                "手部轮廓是否过粗、过糙或像贴片",
                "移开部件后隐藏材料是否可信",
                "最早失败点在哪里",
            ],
        },
        "stop": "do not continue beyond Stage A before user visual approval",
    }
    save_json(ROOT / "audit/machine-report.json", report)
    (ROOT / "audit/MACHINE-REPORT.zh-CN.md").write_text(
        "\n".join(
            [
                "# V26 阶段 A 机器报告",
                "",
                f"- 状态：`{report['status']}`",
                f"- 骨长最大误差：L1 `{max_l1_error:.9f}px`；L2 `{max_l2_error:.9f}px`",
                f"- 41 样本接缝：`{'通过' if all_seams_pass else '失败'}`",
                f"- 断开：`{report['disconnects']['count']}`",
                f"- 0→1→0 回程一致：`{'通过' if first_pose_hash == last_pose_hash else '失败'}`",
                "",
                "这些结果只证明工程可复现，不能证明分层视觉正确。视觉仍待用户检查中文审查板。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schemaVersion": 1,
        "status": report["status"],
        "files": [],
    }
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
                "review": report["visualGate"]["review"],
                "L1": l1,
                "L2": l2,
                "seamsPass": all_seams_pass,
                "returnPass": first_pose_hash == last_pose_hash,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
