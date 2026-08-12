"""Build an R3-local hand/palm repair candidate without mutating frozen R2.

The candidate is deliberately separate from the official R3 motion build. It
uses the frozen R2 forearm, bracelet, and hand hidden root, then replaces only
the hand visible contour with a dense, source-measured inner-edge trace and a
local ownership guard. It is evidence for a possible upstream material
revision, not an R2 replacement or a texture/mesh artifact.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


R3_ROOT = Path(__file__).resolve().parents[1]
R3_BUILDER_PATH = R3_ROOT / "tools" / "build_r3_motion_stress.py"
CANDIDATE_ROOT = R3_ROOT / "repair-candidate" / "hand-palm"
MASK_ROOT = CANDIDATE_ROOT / "masks"
QA_PATH = R3_ROOT / "qa" / "手掌边界修复候选-中文审查图.png"
REPORT_PATH = R3_ROOT / "audit" / "hand-palm-repair-candidate.json"

spec = importlib.util.spec_from_file_location("r3_motion_stress", R3_BUILDER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load R3 builder: {R3_BUILDER_PATH}")
r3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r3)


HAND_SOURCE_TRACE_POINTS: list[tuple[float, float]] = [
    # Strict manual inner-edge trace of the supplied line art.  The trace is
    # clockwise from the thumb-side wrist handoff and explicitly rounds each
    # fingertip and open web turn.  It is geometry authored from the review
    # line, never source pixels used as alpha; the closing point is implicit.
    (121, 535), (119, 545), (118, 555), (115, 565), (110, 575),
    (108, 583), (106, 592), (103, 599), (100, 604), (98, 606),
    (96, 603), (97, 597), (98, 589), (99, 581), (100, 576),
    (97, 578), (94, 583), (92, 590), (90, 598), (88, 607),
    (87, 615), (86, 618), (84, 620), (82, 621), (80, 620),
    (79, 617), (79, 614), (81, 606), (83, 598), (85, 590),
    (87, 583), (89, 578), (86, 580), (83, 587), (80, 595),
    (78, 604), (77, 612), (76, 616), (74, 619), (72, 620),
    (70, 618), (70, 615), (70, 613), (72, 606), (75, 598),
    (78, 590), (81, 582), (79, 578), (76, 586), (73, 595),
    (70, 603), (67, 609), (65, 611), (64, 613), (64, 614),
    (66, 614), (68, 612), (69, 608), (70, 603), (72, 596),
    (73, 590), (78, 580), (81, 570), (86, 560), (91, 550),
    (95, 542), (98, 538), (100, 535), (107, 535), (115, 535),
]

# The source line is a thick review stroke. The candidate follows its inner
# edge by a declared sub-pixel amount so the flat color does not protrude
# outside the black contour at 800%/nearest-neighbour review. The smaller
# inset preserves the authored finger widths instead of turning them into
# narrow spikes.
HAND_TRACE_INSET_PX = 0.2
HAND_CURVE_SAMPLES_PER_SEGMENT = 8
HAND_MASK_SUPERSAMPLE = 8
HAND_VISIBLE_OWNERSHIP_GUARD_PX = 7.7

HAND_HIDDEN_ROOT_SEGMENTS: list[tuple[tuple[float, float], ...]] = [
    ((94, 538), (90, 535), (91, 529), (101, 523)),
    ((101, 523), (107, 519), (116, 517), (122, 521)),
    ((122, 521), (128, 524), (131, 529), (130, 535)),
    ((130, 535), (130, 541), (126, 547), (121, 551)),
    ((121, 551), (115, 554), (108, 553), (102, 548)),
    ((102, 548), (95, 548), (90, 545), (94, 538)),
]


def offset_closed_trace(points: list[tuple[float, float]], inset_px: float) -> list[tuple[float, float]]:
    """Offset the authored closed trace toward its interior.

    This is an explicit geometric contour operation, not a raster erosion,
    blur, dilate, or texture-derived alpha fallback.
    """

    if len(points) < 3 or inset_px == 0:
        return list(points)
    signed_area = sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )
    counter_clockwise = signed_area > 0

    def offset_line(
        first: tuple[float, float],
        second: tuple[float, float],
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        dx = second[0] - first[0]
        dy = second[1] - first[1]
        length = math.hypot(dx, dy)
        if length == 0:
            return first, second
        normal = (-dy / length, dx / length) if counter_clockwise else (dy / length, -dx / length)
        return (
            (first[0] + normal[0] * inset_px, first[1] + normal[1] * inset_px),
            (second[0] + normal[0] * inset_px, second[1] + normal[1] * inset_px),
        )

    def line_intersection(
        first: tuple[tuple[float, float], tuple[float, float]],
        second: tuple[tuple[float, float], tuple[float, float]],
    ) -> tuple[float, float]:
        (x1, y1), (x2, y2) = first
        (x3, y3), (x4, y4) = second
        denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denominator) < 1e-7:
            return ((x1 + x2) / 2, (y1 + y2) / 2)
        factor = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denominator
        return (x1 + factor * (x2 - x1), y1 + factor * (y2 - y1))

    return [
        line_intersection(
            offset_line(points[index - 1], points[index]),
            offset_line(points[index], points[(index + 1) % len(points)]),
        )
        for index in range(len(points))
    ]


def cubic_bezier(
    start: tuple[float, float],
    control1: tuple[float, float],
    control2: tuple[float, float],
    end: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    inverse = 1.0 - t
    return (
        inverse**3 * start[0]
        + 3 * inverse**2 * t * control1[0]
        + 3 * inverse * t**2 * control2[0]
        + t**3 * end[0],
        inverse**3 * start[1]
        + 3 * inverse**2 * t * control1[1]
        + 3 * inverse * t**2 * control2[1]
        + t**3 * end[1],
    )


def closed_catmull_rom(
    points: list[tuple[float, float]],
    samples_per_segment: int,
) -> list[tuple[float, float]]:
    """Create a closed C1 curve through the strict line-art anchors."""

    if len(points) < 3:
        return list(points)
    result: list[tuple[float, float]] = []
    point_count = len(points)
    for index in range(point_count):
        previous = points[(index - 1) % point_count]
        current = points[index]
        following = points[(index + 1) % point_count]
        next_following = points[(index + 2) % point_count]
        control1 = (
            current[0] + (following[0] - previous[0]) / 6.0,
            current[1] + (following[1] - previous[1]) / 6.0,
        )
        control2 = (
            following[0] - (next_following[0] - current[0]) / 6.0,
            following[1] - (next_following[1] - current[1]) / 6.0,
        )
        for sample in range(samples_per_segment):
            result.append(
                cubic_bezier(
                    current,
                    control1,
                    control2,
                    following,
                    sample / samples_per_segment,
                )
            )
    return result


def build_source_trace_mask() -> Image.Image:
    points = closed_catmull_rom(
        offset_closed_trace(HAND_SOURCE_TRACE_POINTS, HAND_TRACE_INSET_PX),
        HAND_CURVE_SAMPLES_PER_SEGMENT,
    )
    scale = HAND_MASK_SUPERSAMPLE
    high_res = Image.new("L", (r3.CANVAS[0] * scale, r3.CANVAS[1] * scale), 0)
    ImageDraw.Draw(high_res).polygon(
        [(round(x * scale), round(y * scale)) for x, y in points],
        fill=255,
    )
    # Deterministic vector coverage at the final pixel boundary. This is
    # raster antialiasing, not blur/dilate or a texture-derived alpha.
    return high_res.resize(r3.CANVAS, Image.Resampling.BOX)


def apply_ownership_guard(mask: Image.Image, bracelet: Image.Image, guard_px: float) -> Image.Image:
    """Keep visible palm pixels distal to the wrist handoff, then remove bracelet pixels."""

    guarded = Image.new("L", r3.CANVAS, 0)
    source = mask.load()
    target = guarded.load()
    wrist_x, wrist_y = r3.WRIST
    axis_x = r3.PALM_ROOT[0] - wrist_x
    axis_y = r3.PALM_ROOT[1] - wrist_y
    axis_length = math.hypot(axis_x, axis_y)
    bbox = mask.getbbox()
    if bbox:
        left, top, right, bottom = bbox
        for y in range(top, bottom):
            for x in range(left, right):
                if not source[x, y]:
                    continue
                projection = ((x - wrist_x) * axis_x + (y - wrist_y) * axis_y) / axis_length
                if projection >= guard_px:
                    target[x, y] = source[x, y]
    return r3.mask_subtract(guarded, bracelet)


def candidate_masks(builder: object) -> dict[str, Image.Image]:
    raw = build_source_trace_mask()
    bracelet = builder.subregion_masks["bracelet"]["complete"]
    visible = apply_ownership_guard(raw, bracelet, guard_px=HAND_VISIBLE_OWNERSHIP_GUARD_PX)
    hidden = builder.primary_masks["hand"]["hidden"].copy()
    complete = r3.mask_union(visible, hidden)
    return {"raw": raw, "visible": visible, "hidden": hidden, "complete": complete}


def save_mask(mask: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mask.save(path, format="PNG", optimize=False, compress_level=9)


def crop_preview(
    image: Image.Image,
    box: tuple[int, int, int, int],
    scale: int = 6,
    resampling: Image.Resampling = Image.Resampling.LANCZOS,
) -> Image.Image:
    if image.mode == "RGBA":
        image = r3.flatten(image)
    else:
        image = image.convert("RGB")
    crop = image.crop(box)
    return crop.resize((crop.width * scale, crop.height * scale), resampling)


def place_panel(
    board: Image.Image,
    box: tuple[int, int, int, int],
    title: str,
    image: Image.Image,
    note: str,
    builder: object,
) -> None:
    draw = ImageDraw.Draw(board)
    left, top, right, bottom = box
    draw.rounded_rectangle((left, top, right, bottom), radius=14, fill=(255, 255, 255), outline=(188, 202, 214), width=3)
    draw.text((left + 18, top + 14), title, font=builder.font(24, True), fill=(28, 42, 58))
    image_left = left + (right - left - image.width) // 2
    image_top = top + 62
    board.paste(image, (image_left, image_top))
    draw.text((left + 18, bottom - 44), note, font=builder.font(16), fill=(84, 99, 113))


def build_review_board(
    builder: object,
    original_neutral: dict[str, object],
    original_wrist_positive: dict[str, object],
    candidate_neutral: dict[str, object],
    candidate_wrist_positive: dict[str, object],
) -> Image.Image:
    crop_box = (54, 505, 144, 640)
    scale = 6
    source = crop_preview(builder.source_line, crop_box, scale)
    old_neutral = crop_preview(original_neutral["composite"], crop_box, scale)
    old_positive = crop_preview(original_wrist_positive["composite"], crop_box, scale)
    new_neutral = crop_preview(candidate_neutral["composite"], crop_box, scale)
    new_positive = crop_preview(candidate_wrist_positive["composite"], crop_box, scale)
    old_blend_neutral = Image.blend(source, old_neutral, 0.48)
    old_blend_positive = Image.blend(source, old_positive, 0.48)
    source_blend_neutral = Image.blend(source, new_neutral, 0.48)
    source_blend_positive = Image.blend(source, new_positive, 0.48)

    panel_width = 590
    panel_height = 900
    gap = 18
    board = Image.new("RGB", (panel_width * 4 + gap * 5, panel_height * 2 + 180), (239, 244, 247))
    draw = ImageDraw.Draw(board)
    draw.rectangle((0, 0, board.width, 112), fill=(28, 45, 63))
    draw.text((30, 20), "小星 Left｜手掌边界修复候选", font=builder.font(36, True), fill=(255, 255, 255))
    draw.text(
        (32, 70),
        "R3-local candidate｜R2 冻结不变｜严格线稿内缘 v2｜7.7 px 所有权保护｜8x 几何覆盖｜无 blur/dilate",
        font=builder.font(19),
        fill=(221, 231, 239),
    )
    titles = ["原线稿参考", "冻结 R2 + 原线稿", "R3 候选 + 原线稿", "R3 平色候选"]
    rows = [
        (source, old_blend_neutral, new_neutral, source_blend_neutral, "neutral"),
        (source, old_blend_positive, new_positive, source_blend_positive, "wrist +18°"),
    ]
    for row, (source_image, old_blend, new, blend, row_note) in enumerate(rows):
        top = 130 + row * (panel_height + 28)
        images = [source_image, old_blend, blend, new]
        notes = ["固定源线，不参与 alpha", "R2 frozen overlay", row_note + " overlay", "candidate visible + frozen hidden"]
        for column, (title, image, note) in enumerate(zip(titles, images, notes)):
            left = gap + column * (panel_width + gap)
            place_panel(board, (left, top, left + panel_width, top + panel_height), title, image, note, builder)
    return board


def main() -> None:
    builder = r3.R3Builder()
    freeze_path = R3_ROOT / "audit" / "r2-input-freeze.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    expected_manifest = "FEA721AD3F6EB9576DD14D847A97FA17C712D7CCBA2B3DEDA7E09CA8EFD8EE8A"
    actual_manifest = r3.sha256_file(builder.r2_manifest_path).upper()
    if actual_manifest != expected_manifest:
        raise RuntimeError(f"R2 manifest changed before candidate build: {actual_manifest}")

    original_neutral = builder.render_pose(0.0, 0.0, 0.0, include_depth=True)
    original_wrist_positive = builder.render_pose(0.0, 0.0, 18.0, include_depth=True)
    original_hand_rgba = builder.primary_rgba["hand"].copy()
    r2_hand_visible_area = r3.mask_count(builder.primary_masks["hand"]["visible"])
    r2_hand_complete_area = r3.mask_count(builder.primary_masks["hand"]["complete"])
    masks = candidate_masks(builder)
    candidate_hand_rgba = original_hand_rgba.copy()
    candidate_hand_rgba.putalpha(masks["complete"])
    builder.primary_masks["hand"] = {
        "visible": masks["visible"],
        "hidden": masks["hidden"],
        "complete": masks["complete"],
    }
    builder.primary_rgba["hand"] = candidate_hand_rgba
    builder.neutral_areas["hand"] = r3.alpha_area(masks["complete"])

    candidate_neutral = builder.render_pose(0.0, 0.0, 0.0, include_depth=True)
    candidate_wrist_positive = builder.render_pose(0.0, 0.0, 18.0, include_depth=True)
    board = build_review_board(builder, original_neutral, original_wrist_positive, candidate_neutral, candidate_wrist_positive)
    QA_PATH.parent.mkdir(parents=True, exist_ok=True)
    board.save(QA_PATH, format="PNG", optimize=False, compress_level=9)

    save_mask(masks["visible"], MASK_ROOT / "hand-visible.png")
    save_mask(masks["hidden"], MASK_ROOT / "hand-hidden.png")
    save_mask(masks["complete"], MASK_ROOT / "hand-complete.png")
    CANDIDATE_ROOT.mkdir(parents=True, exist_ok=True)
    candidate_hand_rgba.save(CANDIDATE_ROOT / "hand-flat-layer.png", format="PNG", optimize=False, compress_level=9)

    contract = builder.load_r3_contract()
    selected_ids = {
        "wrist-negative-0-1-0",
        "wrist-positive-0-1-0",
        "coupled-motion-0-1-0",
        "coupled-motion-alt-0-1-0",
    }
    track_reports: list[dict[str, object]] = []
    relevant_samples: list[dict[str, object]] = []
    for track_spec in contract["sampling"]["tracks"]:
        if str(track_spec["id"]) not in selected_ids:
            continue
        samples, summary = builder.build_track(track_spec, save_gif=False)
        relevant_samples.extend(samples)
        track_reports.append(
            {
                "id": summary["id"],
                "sampleCount": summary["sampleCount"],
                "peakDeg": summary["peakDeg"],
                "motionProfile": summary["motionProfile"],
                "candidateScopePass": all(
                    sample["ownership"]["duplicateVisiblePairs"]["forearm__hand"] == 0
                    and sample["bracelet"]["handVisibleOwnerOverlapPixels"] == 0
                    and sample["gaps"]["wrist"]["gapSamples"] == 0
                    for sample in samples
                ),
                "maxDuplicateVisiblePixelsAcrossAllLayers": max(sample["ownership"]["duplicateVisiblePixels"] for sample in samples),
                "maxHandForearmDuplicateVisiblePixels": max(sample["ownership"]["duplicateVisiblePairs"]["forearm__hand"] for sample in samples),
                "maxBraceletHandVisibleOverlapPixels": max(sample["bracelet"]["handVisibleOwnerOverlapPixels"] for sample in samples),
                "maxWristGapSamples": max(sample["gaps"]["wrist"]["gapSamples"] for sample in samples),
                "maxWristWidthPx": max(sample["localWidths"]["wrist"]["transverseSpanPx"] for sample in samples),
            }
        )

    report = {
        "schemaVersion": 1,
        "stage": "R3-local hand/palm repair candidate",
        "status": "HAND_PALM_REPAIR_CANDIDATE / NOT_PROMOTED_TO_R2",
        "subject": "小星 Left",
        "character": "xiaoxing",
        "view": "front",
        "screenSide": "left",
        "anatomicalSide": "right",
        "readOnlyBoundary": {
            "r1R2AndOldV12V38Unchanged": True,
            "r2Mutation": False,
            "candidateLivesInsideR3": True,
            "protectedSnapshotDigest": freeze["protectedSnapshotBeforeBuild"]["digest"],
        },
        "inputFreeze": {
            "r2ManifestExpectedSha256": expected_manifest,
            "r2ManifestActualSha256": actual_manifest,
            "protectedSnapshotDigest": freeze["protectedSnapshotBeforeBuild"]["digest"],
        },
        "geometry": {
            "wristPivot": list(r3.WRIST),
            "palmRoot": list(r3.PALM_ROOT),
            "visibleOwnershipGuardProjectionPx": HAND_VISIBLE_OWNERSHIP_GUARD_PX,
            "sourceTrace": "strict manual inner-edge trace of the supplied hand line art through a closed Catmull-Rom/Bézier curve; every fingertip and open web turn is explicit",
            "traceRevision": "hand-line-inner-edge-v2",
            "outlinePoints": [list(point) for point in HAND_SOURCE_TRACE_POINTS],
            "innerEdgeInsetPx": HAND_TRACE_INSET_PX,
            "curveSamplesPerSegment": HAND_CURVE_SAMPLES_PER_SEGMENT,
            "maskSupersample": HAND_MASK_SUPERSAMPLE,
            "maskDownsample": "BOX coverage; deterministic raster antialiasing only",
            "hiddenRoot": "frozen R2 hidden root copied unchanged; no enlarged underlay",
            "hiddenRootSegments": [[list(point) for point in segment] for segment in HAND_HIDDEN_ROOT_SEGMENTS],
            "forbiddenOperationsNotUsed": ["blur", "dilate", "fixed circular patch", "manual drag compensation", "texture", "mesh", "deformer", "runtime"],
        },
        "candidateMaterial": {
            "r2FrozenVisibleAreaPx": r2_hand_visible_area,
            "r2FrozenCompleteAreaPx": r2_hand_complete_area,
            "visibleAreaPx": r3.mask_count(masks["visible"]),
            "hiddenAreaPx": r3.mask_count(masks["hidden"]),
            "completeAreaPx": r3.mask_count(masks["complete"]),
            "visibleAreaDeltaPxFromR2": r3.mask_count(masks["visible"]) - r2_hand_visible_area,
            "completeAreaDeltaPxFromR2": r3.mask_count(masks["complete"]) - r2_hand_complete_area,
            "visibleMaskSha256": r3.alpha_sha(masks["visible"]),
            "hiddenMaskSha256": r3.alpha_sha(masks["hidden"]),
            "completeMaskSha256": r3.alpha_sha(masks["complete"]),
            "flatLayerSha256": r3.image_sha(candidate_hand_rgba),
        },
        "candidateScopeChecks": {
            "selectedTrackCount": len(track_reports),
            "selectedSampleCount": len(relevant_samples),
            "wristAndBraceletOwnershipPass": all(bool(item["candidateScopePass"]) for item in track_reports),
            "noR2OrProtectedMutation": True,
            "notAnOverallR3Pass": True,
        },
        "trackReports": track_reports,
        "outputs": {
            "reviewBoard": "qa/手掌边界修复候选-中文审查图.png",
            "candidateRoot": "repair-candidate/hand-palm/",
            "visibleMask": "repair-candidate/hand-palm/masks/hand-visible.png",
            "hiddenMask": "repair-candidate/hand-palm/masks/hand-hidden.png",
            "completeMask": "repair-candidate/hand-palm/masks/hand-complete.png",
            "flatLayer": "repair-candidate/hand-palm/hand-flat-layer.png",
        },
        "promotionPolicy": "候选需用户视觉批准后，才可在新的上游材料修订阶段取代 R2；本文件不关闭 R3-GATE，也不授权 R4 纹理。",
    }
    r3.write_json(REPORT_PATH, report)
    print(json.dumps({
        "status": report["status"],
        "r2ManifestSha256": actual_manifest,
        "protectedSnapshotDigest": report["inputFreeze"]["protectedSnapshotDigest"],
        "candidateScopePass": report["candidateScopeChecks"]["wristAndBraceletOwnershipPass"],
        "selectedSampleCount": report["candidateScopeChecks"]["selectedSampleCount"],
        "reviewBoard": report["outputs"]["reviewBoard"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
