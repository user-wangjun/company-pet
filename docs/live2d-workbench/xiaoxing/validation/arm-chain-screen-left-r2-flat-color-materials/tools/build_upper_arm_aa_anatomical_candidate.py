"""Build a review-only antialiased upper-arm geometry candidate.

The current R2 upper-arm files remain protected inputs.  This candidate uses a
new explicit cubic path, derived from the R1 shoulder/elbow pivots and the
front master, then rasterizes that path on a 32x canvas and downsamples once
with BOX coverage.  It does not change the skeleton, visible ownership,
forearm, bracelet, or hand artifacts.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw


R2_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = R2_ROOT.parents[4]
XIAOXING_ROOT = R2_ROOT.parents[1]
SOURCE_ROOT = XIAOXING_ROOT / "source"
R1_ROOT = XIAOXING_ROOT / "validation" / "arm-chain-screen-left-r1-physical-line-contract"
OUT_ROOT = R2_ROOT / "candidates" / "upper-arm-aa-anatomical-v8"
CANVAS = (512, 1086)
WIDTH, HEIGHT = CANVAS
SUPERSAMPLE = 32


def load_r2_builder() -> Any:
    builder_path = R2_ROOT / "tools" / "build_r2_flat_color_materials.py"
    spec = importlib.util.spec_from_file_location("xiaoxing_r2_builder", builder_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import the existing R2 helpers: {builder_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r2 = load_r2_builder()


IDENTITY = {
    "character": "xiaoxing",
    "view": "front",
    "screenSide": "left",
    "anatomicalSide": "right",
    "subject": "小星 Left",
}

SOURCE_LINE = SOURCE_ROOT / "masters" / "front-line-source-exact-after-reset.png"
SOURCE_COLOR = SOURCE_ROOT / "masters" / "front-color-source-exact-after-reset.png"
OLD_MASK = R2_ROOT / "masks" / "complete" / "upper_arm.png"
SLEEVE_HIDDEN = R2_ROOT / "masks" / "hidden" / "sleeve.png"
FOREARM_HIDDEN = R2_ROOT / "masks" / "hidden" / "forearm.png"
BODY_CONTRACT = R1_ROOT / "contracts" / "body-joint-contract.json"
ENVELOPE_CONTRACT = R1_ROOT / "contracts" / "joint-envelope-contract.json"

# Explicit front-master cubic spans.  This is deliberately not a periodic
# B-spline: the previous periodic loop regularized both ends into a capsule.
# The new path has three authored anatomical regions:
#   shoulder root: short, slightly flattened under-sleeve entry;
#   brachium: asymmetric lateral sweep with a restrained torso-side contour;
#   elbow transition: oblique, short distal closure into the shared pivot.
# It remains hidden/complete geometry only; no visible upper-arm ownership is
# inferred from this path.
UPPER_ARM_BEZIER_SEGMENTS = (
    ((153.0, 248.0), (157.0, 245.0), (164.0, 245.0), (169.0, 248.0)),
    ((169.0, 248.0), (174.0, 251.0), (177.0, 258.0), (177.0, 268.0)),
    ((177.0, 268.0), (177.0, 287.0), (173.0, 312.0), (171.0, 335.0)),
    ((171.0, 335.0), (169.0, 352.0), (167.0, 370.0), (166.0, 385.0)),
    ((166.0, 385.0), (166.0, 393.0), (165.0, 401.0), (163.0, 407.0)),
    ((163.0, 407.0), (157.0, 412.0), (147.0, 414.0), (140.0, 410.0)),
    ((140.0, 410.0), (137.0, 405.0), (137.0, 398.0), (138.0, 390.0)),
    ((138.0, 390.0), (139.0, 370.0), (142.0, 348.0), (145.0, 327.0)),
    ((145.0, 327.0), (147.0, 318.0), (148.0, 312.0), (148.0, 307.0)),
    ((148.0, 307.0), (147.0, 286.0), (148.0, 267.0), (149.0, 258.0)),
    ((149.0, 258.0), (150.0, 252.0), (151.0, 249.0), (153.0, 248.0)),
)

UPPER_ARM_ANATOMICAL_ANCHORS = {
    "shoulderRoot": [153.0, 248.0],
    "shoulderPivot": [166.0, 270.0],
    "elbowPivot": [149.0, 399.0],
    "distalClosure": [140.0, 410.0],
}


def sha256_file(path: Path) -> str:
    return r2.sha256_file(path)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_png(path: Path, image: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=False, compress_level=9)


def alpha_composite_on_white(image: Image.Image) -> Image.Image:
    base = Image.new("RGBA", image.size, (255, 255, 255, 255))
    return Image.alpha_composite(base, image.convert("RGBA")).convert("RGB")


def alpha_preview(alpha: Image.Image, color: tuple[int, int, int], background: tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    alpha = alpha.convert("L")
    base = Image.new("RGB", alpha.size, background)
    foreground = Image.new("RGB", alpha.size, color)
    return Image.composite(foreground, base, alpha)


def crop_scaled(image: Image.Image, box: tuple[int, int, int, int], scale: int, resample: Image.Resampling) -> Image.Image:
    crop = image.crop(box)
    return crop.resize((crop.width * scale, crop.height * scale), resample)


def row_widths(mask: Image.Image, rows: tuple[int, ...]) -> dict[str, int | None]:
    pixels = mask.convert("L").load()
    result: dict[str, int | None] = {}
    for y in rows:
        xs = [x for x in range(WIDTH) if pixels[x, y] > 0]
        result[str(y)] = max(xs) - min(xs) + 1 if xs else None
    return result


def path_overlay(source: Image.Image, alpha: Image.Image, color: tuple[int, int, int], guide: list[tuple[float, float]]) -> Image.Image:
    overlay = r2.blend_overlay(source.convert("RGB"), r2.rgba_layer(alpha, color))
    draw = ImageDraw.Draw(overlay)
    draw.line([(round(x), round(y)) for x, y in guide], fill=(22, 119, 206), width=1, joint="curve")
    draw.line([(round(x), round(y)) for x, y in guide] + [(round(guide[0][0]), round(guide[0][1]))], fill=(22, 119, 206), width=1, joint="curve")
    return overlay


def anatomy_checks(logical: Image.Image, display: Image.Image) -> tuple[list[dict[str, object]], dict[str, object]]:
    components = r2.component_stats(logical)
    holes = r2.hole_count(logical)
    widths = row_widths(logical, (248, 260, 280, 300, 320, 340, 360, 380, 395, 405))
    required_widths = [widths[str(y)] for y in (260, 300, 340, 380, 395)]
    available_widths = [int(value) for value in required_widths if value is not None]
    proximal = [int(widths[str(y)]) for y in (260, 280) if widths[str(y)] is not None]
    mid = [int(widths[str(y)]) for y in (300, 320, 340, 360) if widths[str(y)] is not None]
    distal = [int(widths[str(y)]) for y in (380, 395, 405) if widths[str(y)] is not None]
    display_values = display.get_flattened_data() if hasattr(display, "get_flattened_data") else display.getdata()
    fractional = sum(1 for value in display_values if 0 < value < 255)
    old_mask = Image.open(OLD_MASK).convert("L")
    sleeve_hidden = Image.open(SLEEVE_HIDDEN).convert("L")
    forearm_hidden = Image.open(FOREARM_HIDDEN).convert("L")
    shoulder_overlap = r2.mask_count(r2.mask_intersection(logical, sleeve_hidden))
    elbow_roi = r2.roi_mask((128, 378, 174, 425))
    elbow_overlap = r2.mask_count(r2.mask_intersection(r2.mask_intersection(logical, forearm_hidden), elbow_roi))
    old_new = r2.mask_diff_stats(old_mask, logical)
    checks = [
        {
            "id": "upper_arm_candidate_single_component_no_holes",
            "pass": len(components) == 1 and holes == 0,
            "detail": f"大臂候选单连通且无孔洞：组件={len(components)}，孔洞={holes}",
            "componentCount": len(components),
            "holeCount": holes,
        },
        {
            "id": "upper_arm_visible_ownership_remains_empty",
            "pass": True,
            "detail": "候选只重建 hidden/complete；upper_arm visible ownership 仍为 0 px",
            "visiblePixelCount": 0,
        },
        {
            "id": "upper_arm_formal_alpha_has_fractional_coverage",
            "pass": fractional > 0,
            "detail": f"32×浮点曲线经一次 BOX 后保留 fractional Alpha：{fractional} px",
            "fractionalAlphaPixels": fractional,
            "supersample": SUPERSAMPLE,
            "downsample": "BOX exactly once",
        },
        {
            "id": "upper_arm_shoulder_hidden_overlap",
            "pass": shoulder_overlap > 0,
            "detail": "候选肩根与受保护 sleeve hidden 有局部重叠",
            "overlapPixels": shoulder_overlap,
        },
        {
            "id": "upper_arm_elbow_hidden_overlap",
            "pass": elbow_overlap > 0,
            "detail": "候选远端与受保护 forearm hidden 在肘部局部重叠",
            "overlapPixels": elbow_overlap,
            "roi": [128, 378, 174, 425],
        },
        {
            "id": "upper_arm_anatomical_taper",
            "pass": bool(proximal and mid and distal and max(proximal) >= max(mid) and max(distal) <= max(mid) + 2),
            "detail": "肩根有体积，中段收窄，肘部允许在 forearm hidden 重叠内保留不超过 2 px 的连续过渡",
            "sectionWidthsPx": widths,
        },
        {
            "id": "upper_arm_width_guard",
            "pass": bool(available_widths) and max(available_widths) <= 32 and min(available_widths) >= 18,
            "detail": "局部横截面保持在较窄的人体上臂候选宽度范围内，避免肩根与中段过粗",
            "minWidthPx": min(available_widths) if available_widths else None,
            "maxWidthPx": max(available_widths) if available_widths else None,
            "guardPx": [18, 32],
        },
        {
            "id": "upper_arm_candidate_diff_isolated",
            "pass": True,
            "detail": "新旧差异只用于审查，不覆盖受保护 R2 大臂正式文件",
            "oldToCandidate": old_new,
        },
    ]
    metrics = {
        "componentCount": len(components),
        "holeCount": holes,
        "sectionWidthsPx": widths,
        "fractionalAlphaPixels": fractional,
        "shoulderOverlapPixels": shoulder_overlap,
        "elbowOverlapPixels": elbow_overlap,
        "oldToCandidate": old_new,
    }
    return checks, metrics


def build_review_board(
    source_line: Image.Image,
    source_color: Image.Image,
    old_mask: Image.Image,
    logical: Image.Image,
    display: Image.Image,
    guide: list[tuple[float, float]],
    checks: list[dict[str, object]],
    metrics: dict[str, object],
) -> Path:
    qa_path = OUT_ROOT / "qa" / "upper-arm-aa-anatomical-review.png"
    box = (124, 232, 188, 424)
    scale = 5
    old_overlay = path_overlay(source_line, old_mask, (238, 142, 56), guide)
    candidate_overlay = path_overlay(source_line, logical, (239, 126, 48), guide)
    formal_overlay = path_overlay(source_line, display, (239, 126, 48), guide)
    formal_overlay_clean = r2.blend_overlay(source_line.convert("RGB"), r2.rgba_layer(display, (239, 126, 48)))
    diff = r2.repair_diff_overlay(old_mask, logical)
    diff_view = r2.blend_overlay_weighted(source_line.convert("RGB"), diff, 0.8)
    alpha_view = alpha_preview(display, (239, 126, 48), (255, 255, 255))
    line_crop = crop_scaled(source_line, box, scale, Image.Resampling.NEAREST)
    color_crop = crop_scaled(source_color, box, scale, Image.Resampling.NEAREST)
    old_crop = crop_scaled(old_overlay, box, scale, Image.Resampling.NEAREST)
    candidate_crop = crop_scaled(candidate_overlay, box, scale, Image.Resampling.NEAREST)
    formal_crop = crop_scaled(formal_overlay_clean, box, scale, Image.Resampling.BICUBIC)
    alpha_crop = crop_scaled(alpha_view, box, scale, Image.Resampling.BICUBIC)
    diff_crop = crop_scaled(diff_view, box, scale, Image.Resampling.NEAREST)

    width = 2240
    panel_w = 530
    panel_h = 560
    gap = 24
    margin = 28
    header = 126
    rows = 3
    board = Image.new("RGB", (width, header + margin + rows * panel_h + (rows - 1) * gap + margin), (239, 244, 248))
    draw = ImageDraw.Draw(board)
    draw.rectangle((0, 0, width, header), fill=(28, 48, 68))
    draw.text((margin, 18), "小星 Left｜大臂抗锯齿 + 右侧肘部衔接修复 v8", fill=(255, 255, 255), font=r2.font(32, True))
    draw.text((margin, 68), "front｜screen-left = anatomical-right｜512×1086 identity｜explicit cubic spans → 32× → BOX｜候选不覆盖现有 R2", fill=(211, 226, 237), font=r2.font(17))

    def panel(index: int, title: str, subtitle: str, image: Image.Image) -> None:
        row, col = divmod(index, 4)
        x = margin + col * (panel_w + gap)
        y = header + margin + row * (panel_h + gap)
        draw.rounded_rectangle((x, y, x + panel_w, y + panel_h), radius=14, fill=(255, 255, 255), outline=(173, 188, 201), width=2)
        draw.text((x + 16, y + 14), title, fill=(28, 42, 58), font=r2.font(21, True))
        draw.text((x + 16, y + 49), subtitle, fill=(91, 104, 117), font=r2.font(14))
        display_image = image.convert("RGB")
        display_image.thumbnail((panel_w - 34, panel_h - 96), Image.Resampling.LANCZOS)
        draw.rectangle((x + 16, y + 82, x + panel_w - 16, y + panel_h - 18), outline=(222, 229, 235), width=1)
        board.paste(display_image, (x + (panel_w - display_image.width) // 2, y + 88))

    panel(0, "1｜权威 front line", "原线稿｜仅作对照，不作为新色块", line_crop)
    panel(1, "2｜原彩身份参考", "原彩｜观察上臂体积与肩肘关系", color_crop)
    panel(2, "3｜旧 complete", "受保护旧二值候选｜阶梯边缘", old_crop)
    panel(3, "4｜新 complete logical", "新人体曲线｜二值逻辑 mask", candidate_crop)
    panel(4, "5｜新 formal display Alpha v8", "右侧线稿续接 + 肘部 hidden overlap → 32× → BOX", alpha_crop)
    panel(5, "6｜formal Alpha 源线叠加", "橙=新候选｜无额外描边，边缘为真实 coverage", formal_crop)
    panel(6, "7｜旧/新差异", "红=旧有而新无｜绿=新补入", diff_crop)

    anatomy = Image.new("RGB", (panel_w - 34, panel_h - 96), (252, 253, 254))
    anatomy_draw = ImageDraw.Draw(anatomy)
    anatomy_draw.text((16, 14), "人体轮廓横截面宽度（px）", fill=(28, 42, 58), font=r2.font(18, True))
    rows_data = metrics["sectionWidthsPx"]
    assert isinstance(rows_data, dict)
    values = [(int(y), int(value)) for y, value in rows_data.items() if value is not None]
    if values:
        chart_left, chart_top, chart_w, chart_h = 28, 72, 420, 290
        max_value = max(value for _, value in values) + 6
        anatomy_draw.line((chart_left, chart_top, chart_left, chart_top + chart_h), fill=(100, 115, 127), width=2)
        anatomy_draw.line((chart_left, chart_top + chart_h, chart_left + chart_w, chart_top + chart_h), fill=(100, 115, 127), width=2)
        points = []
        for index, (y_value, width_value) in enumerate(values):
            px = chart_left + round(index * chart_w / max(1, len(values) - 1))
            py = chart_top + chart_h - round(width_value / max_value * chart_h)
            points.append((px, py))
            anatomy_draw.ellipse((px - 5, py - 5, px + 5, py + 5), fill=(239, 126, 48))
            anatomy_draw.text((px - 12, chart_top + chart_h + 10), str(y_value), fill=(91, 104, 117), font=r2.font(12))
            anatomy_draw.text((px - 8, py - 28), str(width_value), fill=(28, 42, 58), font=r2.font(12, True))
        anatomy_draw.line(points, fill=(239, 126, 48), width=3)
        anatomy_draw.text((28, 400), "肩部较宽 → 中段收窄 → 肘部不鼓包", fill=(45, 130, 91), font=r2.font(15, True))
    panel(8, "8｜人体横截面检查", "肩根体积、非对称中段、肘部斜向收束", anatomy)

    status = Image.new("RGB", (panel_w - 34, panel_h - 96), (252, 253, 254))
    status_draw = ImageDraw.Draw(status)
    status_draw.text((16, 14), "工程检查与状态", fill=(28, 42, 58), font=r2.font(18, True))
    status_lines = [
        "engineeringPass（本候选）= " + str(all(bool(item["pass"]) for item in checks)),
        "userVisualApproval = None",
        "overallGatePass = False",
        f"fractional Alpha = {metrics['fractionalAlphaPixels']} px",
        f"shoulder overlap = {metrics['shoulderOverlapPixels']} px",
        f"elbow overlap = {metrics['elbowOverlapPixels']} px",
        "旧 R2 upper_arm 文件 = 保持不变",
        "前臂 / 手链 / hand = 保持不变",
        "下一步：审查 v8 后再决定是否提升正式层",
    ]
    y = 60
    for line in status_lines:
        color = (166, 63, 63) if ("False" in line or "None" in line or "下一步" in line) else (44, 130, 91)
        status_draw.text((16, y), line, fill=color, font=r2.font(15))
        y += 34
    panel(9, "9｜候选门禁", "工程结果与用户视觉批准分开", status)

    board_path = qa_path
    board_path.parent.mkdir(parents=True, exist_ok=True)
    board.save(board_path, format="PNG", optimize=False, compress_level=9)
    save_png(
        OUT_ROOT / "qa" / "upper-arm-formal-display-alpha-500pct-nearest.png",
        crop_scaled(alpha_view, box, 5, Image.Resampling.NEAREST),
    )
    save_png(
        OUT_ROOT / "qa" / "upper-arm-formal-display-alpha-500pct-presentation.png",
        crop_scaled(alpha_view, box, 5, Image.Resampling.BICUBIC),
    )
    save_png(
        OUT_ROOT / "qa" / "upper-arm-source-line-fit-500pct.png",
        crop_scaled(formal_overlay_clean, box, 5, Image.Resampling.BICUBIC),
    )
    sleeve_hidden = Image.open(SLEEVE_HIDDEN).convert("L")
    forearm_hidden = Image.open(FOREARM_HIDDEN).convert("L")
    transition_overlay = r2.blend_overlay(source_line.convert("RGB"), r2.rgba_layer(display, (239, 126, 48)))
    transition_overlay = r2.blend_overlay(transition_overlay, r2.rgba_layer(forearm_hidden, (42, 169, 132)))
    transition_overlay = r2.blend_overlay(transition_overlay, r2.rgba_layer(sleeve_hidden, (54, 139, 204)))
    save_png(
        OUT_ROOT / "qa" / "upper-arm-occlusion-transition-500pct.png",
        crop_scaled(transition_overlay, box, 5, Image.Resampling.NEAREST),
    )
    return board_path


def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    source_line = Image.open(SOURCE_LINE).convert("RGB")
    source_color = Image.open(SOURCE_COLOR).convert("RGB")
    if source_line.size != CANVAS or source_color.size != CANVAS:
        raise AssertionError("upper-arm candidate requires the 512x1086 front master")

    segments = UPPER_ARM_BEZIER_SEGMENTS
    guide = r2.bezier_chain(segments, samples_per_segment=128)
    high = r2.render_bezier_loop_highres(segments, SUPERSAMPLE, samples_per_segment=128)
    display = r2.downsample_coverage(high, SUPERSAMPLE)
    logical = r2.binary_from_coverage(display, threshold=128)
    visible = Image.new("L", CANVAS, 0)
    complete = logical.copy()

    checks, metrics = anatomy_checks(logical, display)
    failed = [item["id"] for item in checks if not bool(item["pass"])]
    if failed:
        raise AssertionError(f"upper-arm anatomical candidate failed closed checks: {failed}")

    color = (239, 126, 48)
    flat = r2.rgba_layer(display, color)
    old_mask = Image.open(OLD_MASK).convert("L")
    review_path = build_review_board(source_line, source_color, old_mask, logical, display, guide, checks, metrics)

    write_json(OUT_ROOT / "audit" / "user-authorized-reopen-upper-arm-aa-anatomy-2026-08-12.json", {
        "schemaVersion": 1,
        "stage": "UPPER_ARM_AA_ANATOMICAL_CANDIDATE",
        **IDENTITY,
        "decision": "authorized_by_latest_user_request",
        "userText": "先进行抗锯齿化的处理吧，而且根据人体来优化一下",
        "scope": [
            "upper_arm hidden/complete geometry candidate",
            "upper_arm formal display Alpha candidate",
            "upper_arm flat-color review artifact",
        ],
        "protected": [
            "upper_arm visible ownership",
            "sleeve",
            "forearm",
            "bracelet",
            "hand",
            "skeleton/pivots/body transform",
        ],
        "userVisualApproval": None,
        "overallGatePass": False,
    })

    contract = {
        "schemaVersion": 1,
        "stage": "UPPER_ARM_AA_ANATOMICAL_CANDIDATE",
        **IDENTITY,
        "source": {
            "line": {"path": str(SOURCE_LINE.relative_to(REPO_ROOT)).replace("\\", "/"), "sha256": sha256_file(SOURCE_LINE)},
            "color": {"path": str(SOURCE_COLOR.relative_to(REPO_ROOT)).replace("\\", "/"), "sha256": sha256_file(SOURCE_COLOR)},
            "canvas": list(CANVAS),
            "coordinateTransform": "identity; all points are front-master pixels",
        },
        "anatomyBasis": {
            "shoulderPivot": list(r2.SHOULDER_PIVOT),
            "elbowPivot": list(r2.ELBOW_PIVOT),
            "principle": "deltoid root fuller at shoulder, brachium tapers through the mid-arm, distal contour narrows into the elbow without a circular elbow bulb",
            "referenceContracts": [
                str(BODY_CONTRACT.relative_to(REPO_ROOT)).replace("\\", "/"),
                str(ENVELOPE_CONTRACT.relative_to(REPO_ROOT)).replace("\\", "/"),
            ],
        },
        "boundary": {
            "classification": "hidden anatomical material; no visible upper_arm ownership is authorized",
            "allowedSide": "inside the registered upper-arm cubic loop and beneath the sleeve/hair occlusion envelope",
            "anatomicalAnchors": UPPER_ARM_ANATOMICAL_ANCHORS,
            "bezierSegments": [[list(point) for point in segment] for segment in segments],
            "closed": True,
            "continuityTarget": "explicit connected cubic chain; no periodic end regularization",
            "outsideAlphaRule": "formal display Alpha is generated only from the high-resolution loop; no alpha may exist outside the loop",
        },
        "antialiasing": {
            "supersample": SUPERSAMPLE,
            "logic": "32x high-resolution fill -> one BOX coverage downsample -> threshold 128",
            "formalDisplayAlpha": "32x high-resolution fill -> one BOX coverage downsample; fractional edge coverage retained",
            "forbiddenOperations": ["low-resolution NEAREST geometry", "LANCZOS ringing", "blur", "dilate", "erode", "stroke expansion", "rectangle", "fixed circle", "global convex hull"],
        },
        "status": "UPPER_ARM_AA_ANATOMICAL_CANDIDATE / WAITING_USER_VISUAL_APPROVAL",
        "reviewImage": str(review_path.relative_to(REPO_ROOT)).replace("\\", "/"),
    }
    write_json(OUT_ROOT / "audit" / "upper-arm-aa-anatomical-contract.json", contract)

    save_png(OUT_ROOT / "masks" / "visible-upper_arm.png", visible)
    save_png(OUT_ROOT / "masks" / "hidden-upper_arm.png", logical)
    save_png(OUT_ROOT / "masks" / "complete-upper_arm.png", complete)
    save_png(OUT_ROOT / "display-alpha" / "upper_arm.png", display)
    save_png(OUT_ROOT / "flat-layers" / "upper_arm.png", flat)

    machine_report = {
        "schemaVersion": 1,
        "stage": "UPPER_ARM_AA_ANATOMICAL_CANDIDATE",
        **IDENTITY,
        "status": "UPPER_ARM_AA_ANATOMICAL_CANDIDATE / WAITING_USER_VISUAL_APPROVAL",
        "checks": checks,
        "metrics": metrics,
        "engineeringPass": all(bool(item["pass"]) for item in checks),
        "userVisualApproval": None,
        "overallGatePass": False,
        "protectedArtifacts": {
            "oldUpperArmMaskSha256": sha256_file(OLD_MASK),
            "oldUpperArmFlatLayerSha256": sha256_file(R2_ROOT / "flat-layers" / "upper_arm.png"),
            "forearmNotWritten": True,
            "handNotWritten": True,
        },
        "outputs": {
            "visible": "masks/visible-upper_arm.png",
            "hidden": "masks/hidden-upper_arm.png",
            "complete": "masks/complete-upper_arm.png",
            "displayAlpha": "display-alpha/upper_arm.png",
            "flatLayer": "flat-layers/upper_arm.png",
            "review": str(review_path.relative_to(OUT_ROOT)).replace("\\", "/"),
        },
        "downstreamForbidden": ["texture", "PSD", "Cubism", "Mesh", "Physics", "Runtime", "R3", "R4"],
    }
    write_json(OUT_ROOT / "audit" / "upper-arm-aa-machine-report.json", machine_report)

    readme = (
        "# 小星 Left｜大臂 AA + 右侧肘部衔接修复 v8\n\n"
        "当前状态：`UPPER_ARM_AA_ANATOMICAL_CANDIDATE / WAITING_USER_VISUAL_APPROVAL`。\n\n"
        "本候选只重建大臂的 hidden/complete 几何和正式 display Alpha：肩根短而有体积，中段保留不对称软组织轮廓，肘部以斜向短收束连接共享支点，不使用周期 B-spline 胶囊端或圆形补丁。路径在 32×高分辨率画布直接栅格化，逻辑 mask 与 formal display Alpha 均只做一次 BOX coverage downsample。\n\n"
        "当前 R2 的 upper_arm、sleeve、forearm、bracelet、hand 和骨架文件没有被覆盖。请先审查 `qa/upper-arm-aa-anatomical-review.png`，视觉批准后再决定是否提升正式层。\n"
    )
    (OUT_ROOT / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps({
        "engineeringPass": machine_report["engineeringPass"],
        "userVisualApproval": None,
        "overallGatePass": False,
        "review": str(review_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "candidateRoot": str(OUT_ROOT.relative_to(REPO_ROOT)).replace("\\", "/"),
        "fractionalAlphaPixels": metrics["fractionalAlphaPixels"],
        "sectionWidthsPx": metrics["sectionWidthsPx"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
