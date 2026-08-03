from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage


ROOT = Path(__file__).resolve().parents[1]
XIAOXING = ROOT.parents[1]
SOURCE_COLOR = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
SOURCE_LINE = XIAOXING / "source/masters/front-line-source-exact-after-reset.png"
SKELETON_SOURCE = (
    XIAOXING / "validation/arm-chain-screen-right-v3/skeleton.json"
)
SKELETON_APPROVAL = (
    XIAOXING / "validation/arm-chain-screen-right-v3/audit/skeleton-approval.json"
)
INPUT_LOCK = XIAOXING / "validation/arm-chain-screen-right-v2/input-lock.json"

W, H = 512, 1086
SHOULDER = np.array([332.0, 261.0])
ELBOW = np.array([355.0, 415.0])
WRIST = np.array([393.0, 533.0])
ARM_CROP = (292, 205, 452, 650)

NATURAL_COLORS = {
    "sleeve": (230, 232, 224, 255),
    "upper_arm": (243, 199, 186, 255),
    "forearm": (243, 199, 186, 255),
    "hand": (243, 199, 186, 255),
}
DIAGNOSTIC_COLORS = {
    "sleeve": (69, 116, 190, 255),
    "upper_arm": (234, 104, 57, 255),
    "forearm": (54, 166, 112, 255),
    "hand": (172, 75, 157, 255),
}
DRAW_ORDER = ["upper_arm", "forearm", "hand", "sleeve"]


def ensure_dirs() -> None:
    for name in ("materials", "qa", "samples", "audit"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict | list) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def bezier(p0, p1, p2, p3, count=18):
    p0 = np.asarray(p0, dtype=float)
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    p3 = np.asarray(p3, dtype=float)
    points = []
    for t in np.linspace(0.0, 1.0, count, endpoint=False):
        q = (
            (1 - t) ** 3 * p0
            + 3 * (1 - t) ** 2 * t * p1
            + 3 * (1 - t) * t**2 * p2
            + t**3 * p3
        )
        points.append(tuple(q))
    return points


def polygon_mask(points) -> Image.Image:
    image = Image.new("L", (W, H), 0)
    ImageDraw.Draw(image).polygon(
        [(int(round(x)), int(round(y))) for x, y in points], fill=255
    )
    return image


def sleeve_mask() -> Image.Image:
    # Fresh trace from the Reset line/color masters. The shoulder-side top is hidden
    # beneath hair; the cuff edge follows the two visible source endpoints.
    points = []
    points += bezier((318, 230), (328, 226), (340, 233), (347, 251))
    points += bezier((347, 251), (360, 282), (382, 337), (401, 372))
    points += bezier((401, 372), (390, 378), (380, 384), (369, 389))
    points += bezier((369, 389), (359, 392), (348, 397), (337, 401))
    points += bezier((337, 401), (337, 376), (334, 347), (330, 319))
    points += bezier((330, 319), (326, 287), (316, 251), (318, 230))
    return polygon_mask(points)


def variable_limb_mask(points: list[tuple[float, float]], widths: list[float]) -> Image.Image:
    pts = np.asarray(points, dtype=float)
    left = []
    right = []
    for i, (p, width) in enumerate(zip(pts, widths)):
        if i == 0:
            tangent = pts[1] - pts[0]
        elif i == len(pts) - 1:
            tangent = pts[-1] - pts[-2]
        else:
            tangent = pts[i + 1] - pts[i - 1]
        tangent /= max(np.linalg.norm(tangent), 1e-8)
        normal = np.array([-tangent[1], tangent[0]])
        left.append(tuple(p + normal * width))
        right.append(tuple(p - normal * width))
    # A single closed tapered contour is intentional. Full endpoint disks would
    # read as circular seam patches when the neighboring material is displaced.
    return polygon_mask(left + right[::-1])


def upper_arm_mask() -> Image.Image:
    vector = ELBOW - SHOULDER
    ts = np.array([0.67, 0.76, 0.86, 0.96, 1.03, 1.13])
    points = [tuple(SHOULDER + vector * t) for t in ts]
    widths = [8.0, 10.5, 13.5, 15.8, 13.0, 8.0]
    return variable_limb_mask(points, widths)


def forearm_mask() -> Image.Image:
    vector = WRIST - ELBOW
    ts = np.array([-0.14, -0.05, 0.08, 0.28, 0.52, 0.76, 0.94, 1.08])
    points = [tuple(ELBOW + vector * t) for t in ts]
    # The proximal hidden continuation stays narrow inside the upper-arm volume;
    # it expands to the true forearm width only at/after the approved elbow.
    widths = [6.0, 8.0, 16.0, 15.5, 13.2, 10.8, 9.2, 7.0]
    return variable_limb_mask(points, widths)


def source_hand_mask(source: Image.Image) -> Image.Image:
    rgb = np.asarray(source.convert("RGB"))
    r = rgb[:, :, 0].astype(np.int16)
    g = rgb[:, :, 1].astype(np.int16)
    b = rgb[:, :, 2].astype(np.int16)
    # The Reset master has a near-neutral background. Select the complete
    # non-background hand component, including its outline, rather than dilating
    # a skin-color subset; this preserves the original finger separations.
    non_background = (r < 242) | (g < 236) | (b < 232)
    roi = np.zeros((H, W), dtype=bool)
    roi[538:630, 374:442] = True
    candidate = non_background & roi
    labels, count = ndimage.label(
        candidate, structure=np.ones((3, 3), dtype=np.uint8)
    )
    keep = np.zeros_like(candidate)
    ranked = sorted(
        (
            (int(np.count_nonzero(labels == label_id)), label_id)
            for label_id in range(1, count + 1)
        ),
        reverse=True,
    )
    if not ranked:
        raise RuntimeError("Could not derive the hand silhouette from the Reset master.")
    keep[labels == ranked[0][1]] = True
    keep = ndimage.binary_fill_holes(keep)
    result = Image.fromarray((keep * 255).astype(np.uint8), mode="L")

    # Connect a tapered hidden wrist root to the source-derived palm and fingers.
    wrist_root = variable_limb_mask(
        [(390, 524), (393, 533), (397, 544), (400, 552)],
        [5.0, 7.0, 9.0, 10.0],
    )
    result = Image.fromarray(
        np.maximum(np.asarray(result), np.asarray(wrist_root)).astype(np.uint8),
        mode="L",
    )
    result = Image.fromarray(
        (ndimage.binary_closing(np.asarray(result) > 0, iterations=1) * 255).astype(
            np.uint8
        ),
        mode="L",
    )
    return result


def colorize(mask: Image.Image, color) -> Image.Image:
    image = Image.new("RGBA", (W, H), color)
    image.putalpha(mask)
    return image


def checkerboard(size=(W, H), cell=16) -> Image.Image:
    yy, xx = np.indices((size[1], size[0]))
    board = ((xx // cell + yy // cell) % 2).astype(np.uint8)
    values = np.where(board[..., None] == 0, 236, 208)
    rgb = np.repeat(values, 3, axis=2).astype(np.uint8)
    alpha = np.full((size[1], size[0], 1), 255, dtype=np.uint8)
    return Image.fromarray(np.concatenate([rgb, alpha], axis=2), mode="RGBA")


def composite(layers: dict[str, Image.Image], background=None) -> Image.Image:
    base = (
        Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if background is None
        else background.convert("RGBA").copy()
    )
    for name in DRAW_ORDER:
        base.alpha_composite(layers[name])
    return base


def affine_layer(
    image: Image.Image,
    old_pivot: np.ndarray,
    new_pivot: np.ndarray,
    angle_deg: float,
) -> Image.Image:
    angle = math.radians(angle_deg)
    c = math.cos(angle)
    s = math.sin(angle)
    ox, oy = old_pivot
    nx, ny = new_pivot
    matrix = (
        c,
        s,
        ox - c * nx - s * ny,
        -s,
        c,
        oy + s * nx - c * ny,
    )
    return image.transform(
        (W, H),
        Image.Transform.AFFINE,
        matrix,
        resample=Image.Resampling.NEAREST,
        fillcolor=(0, 0, 0, 0),
    )


def fk(theta1_deg: float, theta2_deg: float):
    l1 = np.linalg.norm(ELBOW - SHOULDER)
    l2 = np.linalg.norm(WRIST - ELBOW)
    t1 = math.radians(theta1_deg)
    t12 = math.radians(theta1_deg + theta2_deg)
    elbow = SHOULDER + l1 * np.array([math.cos(t1), math.sin(t1)])
    wrist = elbow + l2 * np.array([math.cos(t12), math.sin(t12)])
    return elbow, wrist


def progress(index: int) -> float:
    j = index if index <= 20 else 40 - index
    return 0.5 * (1.0 - math.cos(math.pi * j / 20.0))


def motion_layers(
    natural_layers: dict[str, Image.Image],
    theta1: float,
    theta2: float,
    rest_theta1: float,
    rest_theta2: float,
) -> tuple[dict[str, Image.Image], np.ndarray, np.ndarray]:
    new_elbow, new_wrist = fk(theta1, theta2)
    shoulder_delta = theta1 - rest_theta1
    forearm_delta = (theta1 + theta2) - (rest_theta1 + rest_theta2)
    moved = {
        "sleeve": affine_layer(
            natural_layers["sleeve"], SHOULDER, SHOULDER, shoulder_delta
        ),
        "upper_arm": affine_layer(
            natural_layers["upper_arm"], SHOULDER, SHOULDER, shoulder_delta
        ),
        "forearm": affine_layer(
            natural_layers["forearm"], ELBOW, new_elbow, forearm_delta
        ),
        # The complete hand inherits the forearm transform around the elbow.
        # This makes wrist and palm move as a continuous child, not a static sticker.
        "hand": affine_layer(
            natural_layers["hand"], ELBOW, new_elbow, forearm_delta
        ),
    }
    return moved, new_elbow, new_wrist


def crop_scaled(image: Image.Image, box=ARM_CROP, scale=3) -> Image.Image:
    crop = image.crop(box)
    return crop.resize(
        (crop.width * scale, crop.height * scale), Image.Resampling.NEAREST
    )


def labeled_panel(
    image: Image.Image,
    title: str,
    note: str,
    width: int,
    height: int,
) -> Image.Image:
    panel = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(panel)
    draw.text((22, 16), title, fill=(22, 22, 22), font=font(34, True))
    draw.text((22, 62), note, fill=(70, 70, 70), font=font(22))
    max_w, max_h = width - 44, height - 112
    ratio = min(max_w / image.width, max_h / image.height)
    shown = image.resize(
        (max(1, int(image.width * ratio)), max(1, int(image.height * ratio))),
        Image.Resampling.NEAREST,
    )
    x = (width - shown.width) // 2
    y = 102 + (max_h - shown.height) // 2
    panel.paste(shown.convert("RGB"), (x, y))
    draw.rectangle((0, 0, width - 1, height - 1), outline=(185, 185, 185), width=2)
    return panel


def make_overlay(source: Image.Image, flat: Image.Image) -> Image.Image:
    source_rgba = source.convert("RGBA")
    tinted = flat.copy()
    tinted.putalpha(
        Image.fromarray(
            (np.asarray(tinted.getchannel("A"), dtype=np.uint16) * 150 // 255).astype(
                np.uint8
            )
        )
    )
    source_rgba.alpha_composite(tinted)
    return source_rgba


def moved_away(
    layers: dict[str, Image.Image], selected: str, dx: float, dy: float
) -> Image.Image:
    moved = dict(layers)
    moved[selected] = affine_layer(
        layers[selected], np.array([0.0, 0.0]), np.array([dx, dy]), 0.0
    )
    return composite(moved, checkerboard())


def local_zoom(
    source: Image.Image,
    flat: Image.Image,
    overlay: Image.Image,
    box,
    title: str,
    note: str,
) -> Image.Image:
    canvas = Image.new("RGB", (1800, 760), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((30, 18), title, fill=(20, 20, 20), font=font(38, True))
    draw.text((30, 68), note, fill=(70, 70, 70), font=font(25))
    labels = ["权威彩稿", "V12 纯色回组", "半透明叠原图"]
    images = [source, composite({
        name: colorize(mask_images[name], NATURAL_COLORS[name])
        for name in DRAW_ORDER
    }, checkerboard()), overlay]
    for i, (label, image) in enumerate(zip(labels, images)):
        x = 30 + i * 590
        draw.text((x, 118), label, fill=(30, 30, 30), font=font(26, True))
        crop = image.crop(box)
        ratio = min(550 / crop.width, 560 / crop.height)
        shown = crop.resize(
            (int(crop.width * ratio), int(crop.height * ratio)),
            Image.Resampling.NEAREST,
        ).convert("RGB")
        canvas.paste(shown, (x, 160))
        draw.rectangle((x, 160, x + shown.width, 160 + shown.height), outline="black", width=2)
    return canvas


def connected_components(mask: Image.Image) -> int:
    # Rasterized diagonal contours are continuous under 8-neighbor image
    # connectivity; 4-neighbor labeling would misclassify a one-pixel diagonal.
    _, count = ndimage.label(
        np.asarray(mask) > 0, structure=np.ones((3, 3), dtype=np.uint8)
    )
    return int(count)


def overlap_px(a: Image.Image, b: Image.Image) -> int:
    return int(np.count_nonzero((np.asarray(a) > 0) & (np.asarray(b) > 0)))


def centerline_covered(mask: Image.Image, a: np.ndarray, b: np.ndarray) -> bool:
    arr = np.asarray(mask) > 0
    for t in np.linspace(0.0, 1.0, 101):
        point = a * (1 - t) + b * t
        x, y = np.rint(point).astype(int)
        if x < 0 or x >= W or y < 0 or y >= H or not arr[y, x]:
            return False
    return True


def build_contracts(skeleton: dict, input_lock: dict) -> None:
    skeleton_lock = {
        "schemaVersion": 1,
        "status": "locked_from_user_approved_v3_skeleton",
        "scope": "screen-right arm Stage A layering geometry only",
        "approvedEvidence": {
            "approvalRecord": "../arm-chain-screen-right-v3/audit/skeleton-approval.json",
            "approvedReview": "../arm-chain-screen-right-v3/qa/skeleton-design-review-v3.png",
            "approvedContract": "../arm-chain-screen-right-v3/skeleton.json",
        },
        "authoritativeInputs": input_lock["authoritativeImageInputs"],
        "integerCropContract": input_lock["cropContract"],
        "canvas": skeleton["scope"]["canvas"],
        "landmarks": skeleton["landmarks"],
        "boneLengthsPx": skeleton["boneLengthsPx"],
        "restAnglesDeg": skeleton["restAnglesDeg"],
        "allowedRangesDeg": skeleton["allowedRangesDeg"],
        "motion": skeleton["primaryMotion"],
        "parentChildRelations": skeleton["transformHierarchy"],
        "drawOrderBackToFront": skeleton["drawOrderBackToFront"],
        "geometryMutation": "none",
    }
    save_json(ROOT / "skeleton-lock.json", skeleton_lock)

    contract = {
        "schemaVersion": 1,
        "status": "candidate_pending_user_visual_approval",
        "scope": "four complete flat-color full-canvas materials; no texture, PSD, Cubism, Physics, runtime, opposite arm, or full body",
        "sourcePolicy": {
            "geometryDerivedFrom": [
                "source/masters/front-line-source-exact-after-reset.png",
                "source/masters/front-color-source-exact-after-reset.png",
            ],
            "oldV10V11MaterialsUsedAsInputs": False,
            "oldV10V11Use": "failure comparison only",
        },
        "layers": [
            {
                "id": "sleeve",
                "visiblePixelOwnership": "screen-right sleeve outer contour and cuff opening from the Reset masters",
                "hiddenExtensionResponsibility": "small shoulder-side continuation under foreground hair; no skin ownership",
                "overlapResponsibility": "draws above upper-arm root and hides the root inside the cuff",
                "forbiddenIntrusion": ["foreground hair", "torso print", "background", "skin below cuff"],
                "parent": "shoulder_rotation",
                "drawOrder": 40,
            },
            {
                "id": "upper_arm",
                "visiblePixelOwnership": "skin from inside the cuff through the approved elbow split",
                "hiddenExtensionResponsibility": "tapered root remains inside the cuff; distal continuation passes behind the forearm at the elbow",
                "overlapResponsibility": "supports the cuff opening and anatomical elbow volume without a shoulder bulge",
                "forbiddenIntrusion": ["foreground hair", "shirt", "background", "hand"],
                "parent": "shoulder_rotation",
                "drawOrder": 10,
            },
            {
                "id": "forearm",
                "visiblePixelOwnership": "tapered elbow-to-wrist skin; the bracelet is an out-of-scope accessory reference in this four-skin-layer geometry gate",
                "hiddenExtensionResponsibility": "proximal continuation behind upper arm and distal wrist continuation beneath hand",
                "overlapResponsibility": "maintains elbow and wrist coverage over the full approved FK path",
                "forbiddenIntrusion": ["shirt", "background", "hand fingers", "bracelet accessory pixels", "opposite arm"],
                "parent": "elbow_rotation",
                "drawOrder": 20,
            },
            {
                "id": "hand",
                "visiblePixelOwnership": "source-derived palm and finger silhouette below the wrist/bracelet",
                "hiddenExtensionResponsibility": "tapered anatomical wrist root beneath the out-of-scope bracelet reference",
                "overlapResponsibility": "inherits the forearm transform so wrist, palm, and fingers move as one child material",
                "forbiddenIntrusion": ["bracelet forearm-side pixels", "background outside finger silhouette", "shirt"],
                "parent": "wrist_rotation_inherits_forearm_without_independent_angle",
                "drawOrder": 30,
            },
        ],
        "neutralDrawOrderBackToFront": DRAW_ORDER,
        "hardStops": [
            "any visible background, hair, or shirt intrusion",
            "circular hidden patch or mechanically widened seam",
            "default reconstruction not visually natural",
            "user visual review board not approved",
        ],
        "outOfScopeVisibleAccessory": {
            "id": "screen-right bracelet",
            "reason": "not one of the four requested anatomical materials; retained only in source/overlay reference",
            "geometryRequirement": "forearm and hand skin must remain continuous beneath it without using it to hide a gap",
        },
        "approvalState": "engineering_candidate_only",
    }
    save_json(ROOT / "layering-contract.json", contract)


def write_report(report: dict) -> None:
    save_json(ROOT / "audit/machine-report.json", report)
    lines = [
        "# V12 阶段 A 机器报告",
        "",
        f"- 状态：`{report['status']}`",
        f"- 41 帧最大 L1 误差：`{report['boneLength']['maxL1ErrorPx']:.9f}px`",
        f"- 41 帧最大 L2 误差：`{report['boneLength']['maxL2ErrorPx']:.9f}px`",
        f"- 最小袖口重叠：`{report['seams']['minSleeveUpperOverlapPx']} px`",
        f"- 最小肘部重叠：`{report['seams']['minUpperForearmOverlapPx']} px`",
        f"- 最小腕部重叠：`{report['seams']['minForearmHandOverlapPx']} px`",
        f"- 断开帧数：`{report['connectivity']['disconnectedFrameCount']}`",
        f"- 0→1→0 回程一致：`{report['roundTrip']['exactPixelReturn']}`",
        "",
        "以上仅是工程检查，不代表分层视觉通过。必须审查",
        "`qa/V12-阶段A-用户视觉审查板.zh-CN.png` 后由用户决定。",
    ]
    (ROOT / "audit/MACHINE-REPORT.zh-CN.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    ensure_dirs()
    source_color = Image.open(SOURCE_COLOR).convert("RGBA")
    source_line = Image.open(SOURCE_LINE).convert("RGBA")
    skeleton = load_json(SKELETON_SOURCE)
    approval = load_json(SKELETON_APPROVAL)
    input_lock = load_json(INPUT_LOCK)
    if approval.get("status") != "approved":
        raise RuntimeError("Approved skeleton evidence is missing.")
    if source_color.size != (W, H) or source_line.size != (W, H):
        raise RuntimeError("Reset integer-crop canvas mismatch.")
    expected = {
        item["path"]: item["sha256"].lower()
        for item in input_lock["authoritativeImageInputs"]
        if item["path"].endswith("front-line-source-exact-after-reset.png")
        or item["path"].endswith("front-color-source-exact-after-reset.png")
    }
    for relative, digest in expected.items():
        actual = sha256(XIAOXING / relative)
        if actual.lower() != digest:
            raise RuntimeError(f"Authoritative input hash mismatch: {relative}")

    mask_images = {
        "sleeve": sleeve_mask(),
        "upper_arm": upper_arm_mask(),
        "forearm": forearm_mask(),
        "hand": source_hand_mask(source_color),
    }
    natural_layers = {}
    diagnostic_layers = {}
    for name, mask in mask_images.items():
        natural_layers[name] = colorize(mask, NATURAL_COLORS[name])
        diagnostic_layers[name] = colorize(mask, DIAGNOSTIC_COLORS[name])
        natural_layers[name].save(ROOT / f"materials/{name}.png")

    build_contracts(skeleton, input_lock)

    flat = composite(natural_layers)
    diagnostic = composite(diagnostic_layers)
    flat_on_checker = composite(natural_layers, checkerboard())
    overlay = make_overlay(source_color, diagnostic)
    flat.save(ROOT / "qa/default-recomposition.png")
    overlay.save(ROOT / "qa/default-overlay-original.png")

    moved_paths = {}
    move_specs = {
        "sleeve": (90, -20),
        "upper_arm": (-105, 15),
        "forearm": (100, 10),
        "hand": (85, 50),
    }
    for name, (dx, dy) in move_specs.items():
        image = moved_away(natural_layers, name, dx, dy)
        path = ROOT / f"qa/displaced-{name}.png"
        image.save(path)
        moved_paths[name] = path

    zoom_specs = {
        "shoulder-sleeve": (
            (300, 220, 405, 415),
            "肩袖局部放大",
            "看：袖子外轮廓、袖口开口、发丝遮挡侧是否自然；批准项。",
        ),
        "elbow": (
            (325, 382, 390, 465),
            "肘部局部放大",
            "看：上臂与前臂是否形成真实肘部延续，而非圆补丁；批准项。",
        ),
        "wrist": (
            (370, 500, 420, 570),
            "腕部局部放大",
            "看：前臂 taper、手链下连续皮肤和隐藏腕根是否自然；手链仅作原图参照；批准项。",
        ),
        "hand": (
            (372, 530, 442, 630),
            "手部局部放大",
            "看：掌根、手指间隙、轮廓粗细及贴片感；批准项。",
        ),
    }
    zoom_paths = {}
    for name, (box, title, note) in zoom_specs.items():
        image = local_zoom(source_color, flat, overlay, box, title, note)
        path = ROOT / f"qa/zoom-{name}.png"
        image.save(path)
        zoom_paths[name] = path

    rest_t1 = skeleton["restAnglesDeg"]["theta1"]
    rest_t2 = skeleton["restAnglesDeg"]["theta2"]
    target_t1 = skeleton["primaryMotion"]["target"]["theta1"]
    target_t2 = skeleton["primaryMotion"]["target"]["theta2"]
    l1 = skeleton["boneLengthsPx"]["L1ShoulderToElbow"]
    l2 = skeleton["boneLengthsPx"]["L2ElbowToWrist"]

    sample_records = []
    frames = []
    max_l1_error = 0.0
    max_l2_error = 0.0
    sleeve_upper_overlaps = []
    upper_forearm_overlaps = []
    forearm_hand_overlaps = []
    disconnected = []
    centerline_failures = []
    sample_mask_hashes = []
    for index in range(41):
        p = progress(index)
        theta1 = rest_t1 + (target_t1 - rest_t1) * p
        theta2 = rest_t2 + (target_t2 - rest_t2) * p
        moved, new_elbow, new_wrist = motion_layers(
            natural_layers, theta1, theta2, rest_t1, rest_t2
        )
        frame = composite(moved)
        frame_path = ROOT / f"samples/fk-{index:03d}.png"
        frame.save(frame_path)
        frames.append(crop_scaled(composite(moved, checkerboard()), scale=2))
        union = np.zeros((H, W), dtype=bool)
        for layer in moved.values():
            union |= np.asarray(layer.getchannel("A")) > 0
        union_mask = Image.fromarray((union * 255).astype(np.uint8), mode="L")
        components = connected_components(union_mask)
        if components != 1:
            disconnected.append(index)
        if not (
            centerline_covered(union_mask, SHOULDER, new_elbow)
            and centerline_covered(union_mask, new_elbow, new_wrist)
        ):
            centerline_failures.append(index)
        su = overlap_px(moved["sleeve"].getchannel("A"), moved["upper_arm"].getchannel("A"))
        uf = overlap_px(
            moved["upper_arm"].getchannel("A"), moved["forearm"].getchannel("A")
        )
        fh = overlap_px(
            moved["forearm"].getchannel("A"), moved["hand"].getchannel("A")
        )
        sleeve_upper_overlaps.append(su)
        upper_forearm_overlaps.append(uf)
        forearm_hand_overlaps.append(fh)
        measured_l1 = float(np.linalg.norm(new_elbow - SHOULDER))
        measured_l2 = float(np.linalg.norm(new_wrist - new_elbow))
        max_l1_error = max(max_l1_error, abs(measured_l1 - l1))
        max_l2_error = max(max_l2_error, abs(measured_l2 - l2))
        digest = hashlib.sha256(frame.tobytes()).hexdigest()
        sample_mask_hashes.append(digest)
        sample_records.append(
            {
                "index": index,
                "progress": round(p, 9),
                "theta1Deg": round(theta1, 9),
                "theta2Deg": round(theta2, 9),
                "elbow": [round(float(v), 6) for v in new_elbow],
                "wrist": [round(float(v), 6) for v in new_wrist],
                "L1Px": measured_l1,
                "L2Px": measured_l2,
                "overlapPx": {
                    "sleeveUpper": su,
                    "upperForearm": uf,
                    "forearmHand": fh,
                },
                "connectedComponents": components,
                "sha256Pixels": digest,
            }
        )
    save_json(ROOT / "samples/fk-41-samples.json", sample_records)
    gif_frames = [frame.convert("P", palette=Image.Palette.ADAPTIVE) for frame in frames]
    gif_frames[0].save(
        ROOT / "qa/fk-41-slow-preview.gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=140,
        loop=0,
        disposal=2,
    )

    # Neutral forbidden-area check: complete materials may overlap each other but
    # must remain inside the freshly traced sleeve/skin/hand support corridor.
    allowed = np.zeros((H, W), dtype=bool)
    for mask in mask_images.values():
        allowed |= np.asarray(mask) > 0
    neutral_union = np.asarray(diagnostic.getchannel("A")) > 0
    forbidden_intrusion = int(np.count_nonzero(neutral_union & ~allowed))
    mask_stats = {}
    for name, mask in mask_images.items():
        binary = np.asarray(mask) > 0
        holes = ndimage.binary_fill_holes(binary) & ~binary
        mask_stats[name] = {
            "opaquePixelCount": int(np.count_nonzero(binary)),
            "connectedComponents": connected_components(mask),
            "enclosedHolePixels": int(np.count_nonzero(holes)),
            "fullCanvas": list(mask.size) == [W, H],
        }

    engineering_pass = (
        max_l1_error <= 0.01
        and max_l2_error <= 0.01
        and min(sleeve_upper_overlaps) > 0
        and min(upper_forearm_overlaps) > 0
        and min(forearm_hand_overlaps) > 0
        and not disconnected
        and not centerline_failures
        and sample_mask_hashes[0] == sample_mask_hashes[-1]
        and forbidden_intrusion == 0
        and all(v["connectedComponents"] == 1 for v in mask_stats.values())
        and all(v["fullCanvas"] for v in mask_stats.values())
    )
    report = {
        "schemaVersion": 1,
        "status": (
            "pass_engineering_only_user_visual_pending"
            if engineering_pass
            else "fail_stage_a_engineering"
        ),
        "authoritativeInputIntegrity": {
            "frontColorSha256": sha256(SOURCE_COLOR),
            "frontLineSha256": sha256(SOURCE_LINE),
            "canvas": [W, H],
            "integerCropVerified": True,
        },
        "skeleton": {
            "unchanged": True,
            "shoulder": SHOULDER.tolist(),
            "elbow": ELBOW.tolist(),
            "wrist": WRIST.tolist(),
            "L1Px": l1,
            "L2Px": l2,
        },
        "boneLength": {
            "sampleCount": 41,
            "maxL1ErrorPx": max_l1_error,
            "maxL2ErrorPx": max_l2_error,
            "tolerancePx": 0.01,
            "pass": max_l1_error <= 0.01 and max_l2_error <= 0.01,
        },
        "seams": {
            "minSleeveUpperOverlapPx": min(sleeve_upper_overlaps),
            "minUpperForearmOverlapPx": min(upper_forearm_overlaps),
            "minForearmHandOverlapPx": min(forearm_hand_overlaps),
            "centerlineCoverageFailureFrames": centerline_failures,
            "pass": (
                min(sleeve_upper_overlaps) > 0
                and min(upper_forearm_overlaps) > 0
                and min(forearm_hand_overlaps) > 0
                and not centerline_failures
            ),
        },
        "connectivity": {
            "disconnectedFrameCount": len(disconnected),
            "disconnectedFrames": disconnected,
            "pass": not disconnected,
        },
        "roundTrip": {
            "exactPixelReturn": sample_mask_hashes[0] == sample_mask_hashes[-1],
            "firstPixelSha256": sample_mask_hashes[0],
            "lastPixelSha256": sample_mask_hashes[-1],
        },
        "neutralForbiddenIntrusion": {
            "pixelCount": forbidden_intrusion,
            "pass": forbidden_intrusion == 0,
            "note": "engineering corridor test only; hair, shirt, background, and silhouette still require the overlay board visual review",
        },
        "materials": mask_stats,
        "visualGate": {
            "status": "pending_user_visual_approval",
            "reviewBoard": "qa/V12-阶段A-用户视觉审查板.zh-CN.png",
            "questions": [
                "默认回组是否像原图",
                "袖口到上臂是否自然",
                "肩部是否错误突出或侵入头发",
                "肘部是否符合人体结构",
                "腕部和手掌是否随前臂自然运动",
                "手部轮廓是否过粗过糙或像贴片",
                "移开部件后隐藏材料是否可信",
                "最早失败点在哪里",
            ],
        },
        "stageDecision": "do_not_advance_beyond_stage_a_until_user_approval",
    }
    write_report(report)

    board = Image.new("RGB", (3000, 4100), (247, 247, 247))
    draw = ImageDraw.Draw(board)
    draw.text((70, 45), "小星｜V12 单侧手臂阶段 A 分层几何视觉审查", fill=(20, 20, 20), font=font(54, True))
    draw.text(
        (70, 115),
        "骨架保持 V3 已认可坐标与角度域；本板只审袖子 / 上臂 / 前臂 / 手四层几何。机器通过不等于视觉通过。",
        fill=(70, 70, 70),
        font=font(28),
    )

    source_panel = labeled_panel(
        crop_scaled(source_color, scale=3),
        "A｜权威彩稿（对照）",
        "看整条手臂在原图中的自然轮廓与遮挡。",
        920,
        980,
    )
    flat_panel = labeled_panel(
        crop_scaled(flat_on_checker, scale=3),
        "B｜V12 默认纯色回组【需批准】",
        "看四层拼回后是否仍像一条自然手臂。",
        920,
        980,
    )
    overlay_panel = labeled_panel(
        crop_scaled(overlay, scale=3),
        "C｜叠原图检查【需批准】",
        "看肩袖、肘、腕、手轮廓是否越界或漂移。",
        920,
        980,
    )
    board.paste(source_panel, (60, 180))
    board.paste(flat_panel, (1040, 180))
    board.paste(overlay_panel, (2020, 180))

    displaced_titles = {
        "sleeve": ("D1｜移开袖子", "看袖内上臂根是否细长连续、无肩部肉色凸包。"),
        "upper_arm": ("D2｜移开上臂", "看袖口与肘两端隐藏延伸是否可信。"),
        "forearm": ("D3｜移开前臂", "看肘后责任与腕根是否不是圆补丁。"),
        "hand": ("D4｜移开手", "看前臂末端与手的隐藏腕根是否自然。"),
    }
    for i, name in enumerate(("sleeve", "upper_arm", "forearm", "hand")):
        image = crop_scaled(Image.open(moved_paths[name]).convert("RGBA"), scale=2)
        title, note = displaced_titles[name]
        panel = labeled_panel(image, title, note, 700, 920)
        board.paste(panel, (60 + i * 735, 1210))

    zoom_order = ["shoulder-sleeve", "elbow", "wrist", "hand"]
    for i, name in enumerate(zoom_order):
        image = Image.open(zoom_paths[name]).convert("RGB")
        shown = image.resize((700, 296), Image.Resampling.LANCZOS)
        board.paste(shown, (60 + i * 735, 2190))

    key_indices = [0, 10, 20, 30, 40]
    draw.text((70, 2540), "E｜0→1→0 FK 慢动作关键帧【需批准】", fill=(20, 20, 20), font=font(42, True))
    draw.text(
        (70, 2595),
        "看：肘/腕是否断开，手腕与手掌是否随前臂整体运动，回程是否回到同一轮廓。",
        fill=(70, 70, 70),
        font=font(27),
    )
    for i, index in enumerate(key_indices):
        image = frames[index].resize((520, 720), Image.Resampling.NEAREST)
        panel = Image.new("RGB", (550, 790), "white")
        ImageDraw.Draw(panel).text(
            (18, 12),
            f"样本 {index:02d}｜进度 {progress(index):.2f}",
            fill=(25, 25, 25),
            font=font(25, True),
        )
        panel.paste(image.convert("RGB"), (15, 55))
        board.paste(panel, (70 + i * 580, 2645))

    checklist_y = 3480
    draw.rounded_rectangle(
        (60, checklist_y, 2940, 4040),
        radius=24,
        fill=(255, 252, 239),
        outline=(186, 146, 54),
        width=4,
    )
    draw.text(
        (95, checklist_y + 28),
        "用户视觉硬门禁（请逐项判断；任一失败即停在阶段 A）",
        fill=(88, 60, 10),
        font=font(38, True),
    )
    questions = [
        "□ 1 默认回组像原图中的自然手臂，而不是四个工程部件。",
        "□ 2 袖口→上臂自然；肩部无肉色突出，也未侵入头发/衣服/背景。",
        "□ 3 肘部符合人体结构；重叠不是圆补丁或单纯盖缝。",
        "□ 4 腕部与手掌随前臂自然运动；手不粗糙、不像静态贴片。",
        "□ 5 四张移开图中的隐藏材料可信，无机械扩张、平均色块或断裂。",
        "□ 6 若不通过，请指出最早失败格：B / C / D1 / D2 / D3 / D4 / 肩袖 / 肘 / 腕 / 手 / E。",
    ]
    for i, question in enumerate(questions):
        draw.text(
            (110, checklist_y + 95 + i * 70),
            question,
            fill=(45, 45, 45),
            font=font(28),
        )
    board.save(ROOT / "qa/V12-阶段A-用户视觉审查板.zh-CN.png")

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
    print(json.dumps({
        "status": report["status"],
        "root": ROOT.name,
        "files": len(manifest["files"]) + 1,
        "machineReport": "audit/machine-report.json",
        "reviewBoard": "qa/V12-阶段A-用户视觉审查板.zh-CN.png",
    }, ensure_ascii=False, indent=2))
