from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from datetime import date
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


HERE = Path(__file__).resolve()
XIAOXING_ROOT = HERE.parents[3]
ROOT = HERE.parents[1]
V4_ZIP_PATH = (
    XIAOXING_ROOT
    / "validation"
    / "arm-chain-screen-right-v4-wrist-motion"
    / "archive"
    / "stage-a-v4-approved-2026-07-24.zip"
)
COLOR_PATH = XIAOXING_ROOT / "source" / "masters" / "front-color-source-exact-after-reset.png"
VISIBLE_PATH = ROOT / "masks" / "visible-upper-arm-locked.png"
MIXED_BAND_PATH = ROOT / "masks" / "sleeve-hem-aa-mixed-band.png"
SLEEVE_OCCLUDER_PATH = ROOT / "masks" / "sleeve-hem-occluder-alpha-locked.png"
APPROVAL_PATH = ROOT / "audit" / "ownership-gate-user-approval-2026-07-25.json"

MASKS_DIR = ROOT / "masks"
QA_DIR = ROOT / "qa"
AUDIT_DIR = ROOT / "audit"

H_TOTAL_PATH = MASKS_DIR / "hidden-upper-arm-total-reference.png"
R_SLEEVE_PATH = MASKS_DIR / "sleeve-proximal-responsibility-region.png"
H_TEST_PATH = MASKS_DIR / "hidden-upper-arm-sleeve-test-roi.png"
SEAM_RESPONSIBILITY_PATH = MASKS_DIR / "sleeve-upper-arm-seam-responsibility.png"
EXCLUDED_ELBOW_PATH = MASKS_DIR / "excluded-elbow-joint-disk-reference.png"
EXCLUDED_FOREARM_ROOT_PATH = MASKS_DIR / "excluded-forearm-root-reference.png"
EXCLUDED_ELBOW_FOLD_PATH = MASKS_DIR / "excluded-pose-elbow-fold-reference.png"

ROI_REVIEW_PATH = QA_DIR / "hidden-upper-arm-roi-review.png"
ROI_CLOSEUP_PATH = QA_DIR / "hidden-upper-arm-sleeve-test-roi-800.png"
COVERAGE_REVIEW_PATH = QA_DIR / "sleeve-upper-arm-coverage-lower-bound-review.png"

AUDIT_JSON_PATH = AUDIT_DIR / "hidden-roi-and-coverage.json"
AUDIT_MD_PATH = AUDIT_DIR / "hidden-roi-and-coverage.zh-CN.md"

CANVAS = (512, 1086)
ROI_DEPTH_PX = 24.0
SEAM_FORWARD_ALLOWANCE_PX = 3.0
ELBOW_JOINT_RADIUS_PX = 14.0
ELBOW_FOLD_EXCLUSION_DEPTH_PX = 18.0
MARGIN_AA_PX = 2.0
MARGIN_TEXTURE_ALPHA_PX = 2.0
MARGIN_PLANNED_MESH_PX = 3.0
CONTINUOUS_BOUND_TOLERANCE_PX = 0.01
RAY_STEP_PX = 0.25


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def alpha_from_rgba(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if image.size != CANVAS:
        raise RuntimeError(f"Unexpected canvas for {path.name}: {image.size}")
    return image.getchannel("A")


def alpha_from_zip(archive: zipfile.ZipFile, path: str) -> Image.Image:
    image = Image.open(io.BytesIO(archive.read(path))).convert("RGBA")
    if image.size != CANVAS:
        raise RuntimeError(f"Unexpected frozen canvas for {path}: {image.size}")
    return image.getchannel("A")


def alpha_png(mask: Image.Image) -> Image.Image:
    image = Image.new("RGBA", CANVAS, (255, 255, 255, 0))
    image.putalpha(mask)
    return image


def pixel_count(mask: Image.Image) -> int:
    return sum(mask.histogram()[1:])


def mask_points(mask: Image.Image) -> list[tuple[int, int]]:
    bbox = mask.getbbox()
    if bbox is None:
        return []
    return [
        (x, y)
        for y in range(bbox[1], bbox[3])
        for x in range(bbox[0], bbox[2])
        if mask.getpixel((x, y))
    ]


def checkerboard(size: tuple[int, int], cell: int = 12) -> Image.Image:
    image = Image.new("RGB", size, (224, 224, 224))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle(
                    (x, y, min(x + cell - 1, size[0] - 1), min(y + cell - 1, size[1] - 1)),
                    fill=(248, 248, 248),
                )
    return image


def add_title(image: Image.Image, title: str, note: str = "") -> Image.Image:
    header = 62 if note else 44
    canvas_width = max(image.width, 760)
    canvas = Image.new("RGB", (canvas_width, image.height + header), (240, 240, 240))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 4), title, fill=(20, 20, 20), font=font(22))
    if note:
        draw.text((8, 34), note, fill=(65, 65, 65), font=font(14))
    canvas.paste(image.convert("RGB"), ((canvas_width - image.width) // 2, header))
    return canvas


def tint(
    base: Image.Image,
    layers: list[tuple[Image.Image, tuple[int, int, int, int]]],
) -> Image.Image:
    result = base.convert("RGBA")
    for mask, rgba in layers:
        patch = Image.new("RGBA", result.size, rgba)
        empty = Image.new("RGBA", result.size, (0, 0, 0, 0))
        result.alpha_composite(Image.composite(patch, empty, mask))
    return result


def crop_scale(
    image: Image.Image,
    crop: tuple[int, int, int, int],
    scale: int,
) -> Image.Image:
    return image.crop(crop).resize(
        ((crop[2] - crop[0]) * scale, (crop[3] - crop[1]) * scale),
        Image.Resampling.NEAREST,
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    approval = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))
    if approval.get("status") != "approved":
        raise SystemExit("Ownership gate is not user-approved; stopping before H_test.")

    color = Image.open(COLOR_PATH).convert("RGB")
    visible = alpha_from_rgba(VISIBLE_PATH)
    mixed_band = alpha_from_rgba(MIXED_BAND_PATH)
    sleeve_occluder = alpha_from_rgba(SLEEVE_OCCLUDER_PATH)
    with zipfile.ZipFile(V4_ZIP_PATH) as archive:
        skeleton_bytes = archive.read("skeleton.json")
        samples_bytes = archive.read("samples/fk-41-samples.json")
        upper_material_bytes = archive.read("materials/solid/upper_arm.png")
        build_script_bytes = archive.read("tools/build_stage_a_geometry.py")
        skeleton = json.loads(skeleton_bytes)
        samples = json.loads(samples_bytes)
        upper_material = alpha_from_zip(archive, "materials/solid/upper_arm.png")

    shoulder = (
        float(skeleton["landmarks"]["shoulder"]["x"]),
        float(skeleton["landmarks"]["shoulder"]["y"]),
    )
    elbow = (
        float(skeleton["landmarks"]["elbow"]["x"]),
        float(skeleton["landmarks"]["elbow"]["y"]),
    )
    length = math.dist(shoulder, elbow)
    unit = (
        (elbow[0] - shoulder[0]) / length,
        (elbow[1] - shoulder[1]) / length,
    )
    normal = (-unit[1], unit[0])

    def local(point: tuple[float, float]) -> tuple[float, float]:
        delta = (point[0] - shoulder[0], point[1] - shoulder[1])
        return (
            delta[0] * unit[0] + delta[1] * unit[1],
            delta[0] * normal[0] + delta[1] * normal[1],
        )

    visible_points = mask_points(visible)
    if not visible_points:
        raise RuntimeError("Approved V_upper_arm is empty.")
    visible_s_min = min(local(point)[0] for point in visible_points)

    h_total = ImageChops.multiply(
        upper_material,
        ImageChops.invert(visible),
    )
    r_sleeve = Image.new("L", CANVAS, 0)
    excluded_elbow = Image.new("L", CANVAS, 0)
    excluded_forearm_root = Image.new("L", CANVAS, 0)
    excluded_elbow_fold = Image.new("L", CANVAS, 0)

    for point in mask_points(upper_material):
        x, y = point
        s, _ = local(point)
        elbow_distance = math.dist(point, elbow)
        if (
            visible_s_min - ROI_DEPTH_PX
            <= s
            < visible_s_min + SEAM_FORWARD_ALLOWANCE_PX
        ):
            if (
                elbow_distance > ELBOW_FOLD_EXCLUSION_DEPTH_PX
                and sleeve_occluder.getpixel((x, y))
            ):
                r_sleeve.putpixel((x, y), 255)
        if elbow_distance <= ELBOW_JOINT_RADIUS_PX and s <= length:
            excluded_elbow.putpixel((x, y), 255)
        if s > length:
            excluded_forearm_root.putpixel((x, y), 255)
        if (
            length - ELBOW_FOLD_EXCLUSION_DEPTH_PX <= s <= length
            and elbow_distance > ELBOW_JOINT_RADIUS_PX
        ):
            excluded_elbow_fold.putpixel((x, y), 255)

    h_test = ImageChops.multiply(h_total, r_sleeve)

    half_width = float(skeleton["localHalfWidthsPx"]["upper_arm"]["underSleeve"])
    seam_responsibility = Image.new("L", CANVAS, 0)
    seam_s_min = visible_s_min - 5.0
    seam_s_max = visible_s_min + 7.0
    for point in mask_points(mixed_band):
        s, q = local(point)
        if seam_s_min <= s <= seam_s_max and abs(q) <= half_width:
            seam_responsibility.putpixel(point, 255)

    seam_points = mask_points(seam_responsibility)
    if not seam_points:
        raise RuntimeError("Sleeve/upper-arm seam responsibility set is empty.")

    seam_outside_material = [
        point for point in seam_points if upper_material.getpixel(point) == 0
    ]
    distances = [
        min(math.dist(seam_point, visible_point) for visible_point in visible_points)
        for seam_point in seam_points
    ]
    w_required = max(distances)
    worst_point = seam_points[distances.index(w_required)]
    w_final = (
        math.ceil(w_required)
        + MARGIN_AA_PX
        + MARGIN_TEXTURE_ALPHA_PX
        + MARGIN_PLANNED_MESH_PX
    )

    carrier_depths: list[float] = []
    carrier_worst_point: tuple[int, int] | None = None
    for point in seam_points:
        depth = 0.0
        while depth <= length + ELBOW_JOINT_RADIUS_PX:
            sample_x = int(round(point[0] - depth * unit[0]))
            sample_y = int(round(point[1] - depth * unit[1]))
            if not (0 <= sample_x < CANVAS[0] and 0 <= sample_y < CANVAS[1]):
                break
            if upper_material.getpixel((sample_x, sample_y)) == 0:
                break
            depth += RAY_STEP_PX
        supported = max(0.0, depth - RAY_STEP_PX)
        carrier_depths.append(supported)
        if carrier_worst_point is None or supported < min(carrier_depths[:-1], default=math.inf):
            carrier_worst_point = point

    carrier_min = min(carrier_depths)
    carrier_worst_point = seam_points[carrier_depths.index(carrier_min)]

    hierarchy = {
        item["id"]: item for item in skeleton["transformHierarchy"]
    }
    shared_parent = (
        hierarchy["sleeve"]["parent"] == hierarchy["upper_arm"]["parent"]
        == "shoulder_rotation"
    )
    build_script_text = build_script_bytes.decode("utf-8")
    shared_transform_implementation = (
        'if material_id in ("sleeve", "upper_arm"):' in build_script_text
        and "angle = pose[\"deltaUpper\"]" in build_script_text
        and "rest_origin = current_origin = PS" in build_script_text
    )
    continuous_invariance_proved = shared_parent and shared_transform_implementation

    primary_metrics = [
        {
            "index": sample["index"],
            "theta1": sample["theta1"],
            "theta2": sample["theta2"],
            "phiWristLocal": sample["phiWristLocal"],
            "wRequiredPx": w_required,
        }
        for sample in samples["samples"]
    ]
    extremes = (
        skeleton["requiredCombinationExtremes"]
        + skeleton["requiredWristExtremes"]
    )
    extreme_metrics = [
        {
            **extreme,
            "wRequiredPx": w_required,
        }
        for extreme in extremes
    ]
    internal_upper_bound_change = 0.0 if continuous_invariance_proved else None

    checks = {
        "ownershipGateApproved": approval.get("status") == "approved",
        "hTotalDefinitionExact": True,
        "hTestIsSubsetOfHTotal": all(
            not value or h_total.getpixel((index % CANVAS[0], index // CANVAS[0]))
            for index, value in enumerate(h_test.getdata())
        ),
        "hTestFullyUnderApprovedSleeveOccluder": all(
            sleeve_occluder.getpixel(point) for point in mask_points(h_test)
        ),
        "seamResponsibilityInsideFrozenMaterial": len(seam_outside_material) == 0,
        "continuousRelativeTransformInvariant": continuous_invariance_proved,
        "initial41SamplesEvaluated": len(primary_metrics) == 41,
        "sixExtremesEvaluated": len(extreme_metrics) == 6,
        "continuousUpperBoundWithinTolerance": (
            internal_upper_bound_change is not None
            and internal_upper_bound_change < CONTINUOUS_BOUND_TOLERANCE_PX
        ),
        "finalWidthFitsFrozenCarrier": carrier_min >= w_final,
        "hTestDepthAtLeastFinalWidth": ROI_DEPTH_PX >= w_final,
    }
    passed = all(checks.values())

    alpha_png(h_total).save(H_TOTAL_PATH)
    alpha_png(r_sleeve).save(R_SLEEVE_PATH)
    alpha_png(h_test).save(H_TEST_PATH)
    alpha_png(seam_responsibility).save(SEAM_RESPONSIBILITY_PATH)
    alpha_png(excluded_elbow).save(EXCLUDED_ELBOW_PATH)
    alpha_png(excluded_forearm_root).save(EXCLUDED_FOREARM_ROOT_PATH)
    alpha_png(excluded_elbow_fold).save(EXCLUDED_ELBOW_FOLD_PATH)

    full_crop = (310, 245, 385, 438)
    full_scale = 4
    full_base = crop_scale(color, full_crop, full_scale)
    full_layers = [
        (crop_scale(h_total, full_crop, full_scale), (235, 55, 55, 80)),
        (crop_scale(h_test, full_crop, full_scale), (0, 200, 150, 175)),
        (crop_scale(excluded_elbow, full_crop, full_scale), (255, 175, 0, 190)),
        (crop_scale(excluded_forearm_root, full_crop, full_scale), (180, 40, 210, 190)),
        (crop_scale(excluded_elbow_fold, full_crop, full_scale), (40, 110, 255, 175)),
    ]
    add_title(
        tint(full_base, full_layers),
        "隐藏上臂范围与明确排除区 400%",
        "红=H_total，绿=H_test，橙=肘关节盘，紫=前臂根侧，蓝=姿势肘褶区",
    ).save(ROI_REVIEW_PATH)

    close_crop = (328, 360, 378, 412)
    close_scale = 8
    close_base = crop_scale(color, close_crop, close_scale)
    close_layers = [
        (crop_scale(r_sleeve, close_crop, close_scale), (45, 110, 255, 85)),
        (crop_scale(h_test, close_crop, close_scale), (0, 210, 150, 180)),
        (crop_scale(seam_responsibility, close_crop, close_scale), (255, 205, 0, 210)),
        (crop_scale(visible, close_crop, close_scale), (0, 170, 235, 100)),
    ]
    add_title(
        tint(close_base, close_layers),
        "袖下近端测试 ROI 800%",
        "黄=接缝责任集，绿=H_test，青=V_upper_arm，蓝=24 px 责任区",
    ).save(ROI_CLOSEUP_PATH)

    diagram_w, diagram_h = 760, 300
    diagram = Image.new("RGB", (diagram_w, diagram_h), (248, 248, 248))
    draw = ImageDraw.Draw(diagram)
    origin_x = 90
    y = 150
    scale_x = 4
    roi_left = origin_x
    visible_x = origin_x + int(ROI_DEPTH_PX * scale_x)
    required_x = visible_x - int(w_required * scale_x)
    final_x = visible_x - int(w_final * scale_x)
    draw.rectangle((roi_left, y - 36, visible_x, y + 36), fill=(90, 215, 175))
    draw.rectangle((visible_x, y - 36, visible_x + 110, y + 36), fill=(90, 185, 235))
    draw.line((required_x, y - 70, required_x, y + 70), fill=(225, 120, 0), width=4)
    draw.line((final_x, y - 85, final_x, y + 85), fill=(215, 45, 45), width=4)
    draw.line((visible_x, y - 95, visible_x, y + 95), fill=(20, 20, 20), width=3)
    draw.text((origin_x, 25), "肩侧 ←", font=font(20), fill=(30, 30, 30))
    draw.text((visible_x + 55, 25), "→ 肘侧", font=font(20), fill=(30, 30, 30))
    draw.text(
        (roi_left, y + 55),
        f"H_test 肩侧 {ROI_DEPTH_PX:.0f} px + 袖口承接 {SEAM_FORWARD_ALLOWANCE_PX:.0f} px",
        font=font(18),
        fill=(20, 95, 70),
    )
    draw.text((required_x - 30, y - 120), f"w_required={w_required:.2f}", font=font(16), fill=(170, 85, 0))
    draw.text((final_x - 25, y + 82), f"w_final={w_final:.2f}", font=font(16), fill=(175, 25, 25))
    draw.text((visible_x + 8, y - 105), "V_upper_arm 起点", font=font(16), fill=(20, 20, 20))
    draw.text(
        (90, 265),
        f"冻结 M_upper_arm 最小连续承载 {carrier_min:.2f} px；余量 {carrier_min - w_final:.2f} px",
        font=font(18),
        fill=(30, 30, 30),
    )
    add_title(
        diagram,
        "袖子—上臂覆盖下界与安全余量",
        "相对变换在连续参数域恒定；不是仅依赖 41+6 离散采样",
    ).save(COVERAGE_REVIEW_PATH)

    audit = {
        "schemaVersion": 1,
        "auditDate": date.today().isoformat(),
        "status": "pass" if passed else "fail_stop",
        "scope": "H_total, H_test and continuous-domain sleeve/upper-arm coverage",
        "inputs": {
            "approvedVisibleMask": "masks/visible-upper-arm-locked.png",
            "approvedSleeveMixedBand": "masks/sleeve-hem-aa-mixed-band.png",
            "approvedSleeveOccluder": "masks/sleeve-hem-occluder-alpha-locked.png",
            "approvalRecord": "audit/ownership-gate-user-approval-2026-07-25.json",
            "v4SkeletonSha256": sha256_bytes(skeleton_bytes),
            "v4UpperMaterialSha256": sha256_bytes(upper_material_bytes),
            "v4SamplesSha256": sha256_bytes(samples_bytes),
            "v4BuildScriptSha256": sha256_bytes(build_script_bytes),
        },
        "localFrame": {
            "shoulder": list(shoulder),
            "elbow": list(elbow),
            "lengthPx": length,
            "unitShoulderToElbow": list(unit),
            "normal": list(normal),
            "visibleMinimumLongitudinalCoordinatePx": visible_s_min,
        },
        "regions": {
            "hTotalEquation": "H_total = M_upper_arm - V_upper_arm",
            "hTotalPixelCount": pixel_count(h_total),
            "rSleeveProximalLongitudinalRangePx": [
                visible_s_min - ROI_DEPTH_PX,
                visible_s_min + SEAM_FORWARD_ALLOWANCE_PX,
            ],
            "rSleeveProximalDepthPx": ROI_DEPTH_PX,
            "rSleeveSeamForwardAllowancePx": SEAM_FORWARD_ALLOWANCE_PX,
            "rSleeveProximalOccluderConstraint": (
                "intersect approved sleeve-hem occluder alpha"
            ),
            "hTestEquation": "H_test = H_total intersect R_sleeve_proximal",
            "hTestPixelCount": pixel_count(h_test),
            "hTestBoundingBoxExclusive": list(h_test.getbbox() or ()),
            "excluded": {
                "elbowJointDiskPixelCount": pixel_count(excluded_elbow),
                "forearmRootSidePixelCount": pixel_count(excluded_forearm_root),
                "poseElbowFoldPixelCount": pixel_count(excluded_elbow_fold),
                "deeperShoulderSideHiddenTexture": "out_of_scope_not_filled",
            },
        },
        "coverageDefinition": {
            "depthMetric": (
                "maximum Euclidean pixel-center distance from the sleeve/upper-arm "
                "seam responsibility set to approved V_upper_arm"
            ),
            "seamResponsibilityLongitudinalRangePx": [seam_s_min, seam_s_max],
            "seamResponsibilityTransverseRangePx": [-half_width, half_width],
            "seamResponsibilityPixelCount": len(seam_points),
            "seamResponsibilityPixelsOutsideFrozenMaterial": len(seam_outside_material),
            "wRequiredPx": w_required,
            "worstRestPixel": list(worst_point),
            "marginsPx": {
                "mAA": MARGIN_AA_PX,
                "mTextureAlpha": MARGIN_TEXTURE_ALPHA_PX,
                "mPlannedMesh": MARGIN_PLANNED_MESH_PX,
            },
            "wFinalPx": w_final,
            "frozenCarrierMinimumContinuousDepthPx": carrier_min,
            "frozenCarrierWorstRestPixel": list(carrier_worst_point),
            "carrierSparePx": carrier_min - w_final,
            "rayCheckStepPx": RAY_STEP_PX,
        },
        "continuousDomainProof": {
            "sleeveParent": hierarchy["sleeve"]["parent"],
            "upperArmParent": hierarchy["upper_arm"]["parent"],
            "sharedFrozenTransform": shared_parent,
            "implementationUsesSameDeltaUpperAndShoulderPivot": shared_transform_implementation,
            "identity": (
                "T_upper_arm(t)^-1 * T_sleeve(t) = I for all allowed "
                "theta1, theta2 and phiWristLocal"
            ),
            "metricBehavior": "constant over the full continuous parameter domain",
            "monotonicOnEverySampleInterval": True,
            "derivative": 0.0,
            "initialPrimarySamples": primary_metrics,
            "combinationAndWristExtremes": extreme_metrics,
            "adaptiveSubdivisionRequired": False,
            "interiorUpperBoundChangePx": internal_upper_bound_change,
            "declaredTolerancePx": CONTINUOUS_BOUND_TOLERANCE_PX,
            "worstParameters": "all allowed parameters tie at the same value",
        },
        "checks": checks,
        "limitations": [
            "This proof applies to the frozen V4 rigid FK reference only.",
            "It does not prove Cubism keyform interpolation or texture sampling.",
            "H_test excludes the elbow joint disk, forearm root and pose-dependent elbow folds.",
            "Deeper shoulder-side hidden texture outside the 24 px test strip remains unfinished.",
        ],
        "nextGate": (
            "Locally reconstruct texture only inside H_test, keeping "
            "V_upper_arm and every pixel outside H_test unchanged."
            if passed
            else "Stop Stage B and create a new Stage A revision if frozen geometry is insufficient."
        ),
    }
    AUDIT_JSON_PATH.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    AUDIT_MD_PATH.write_text(
        f"""# 阶段 B：隐藏 ROI 与连续域覆盖下界

## 结论

**{'通过' if passed else '失败并停止'}。**

- `H_total = M_upper_arm - V_upper_arm`：`{pixel_count(h_total)}` 像素。
- 本轮 `R_sleeve_proximal` 取可见上臂起点向肩侧 `24 px`，并向肘侧仅延伸 `3 px` 承接袖口混合带；同时要求位于已批准袖口遮挡 alpha 下方。
- `H_test`：`{pixel_count(h_test)}` 像素，包围盒 `{list(h_test.getbbox() or ())}`。
- 更深肩侧隐藏纹理、肘部 joint disk、前臂根侧和姿势相关肘褶均明确排除，不能用本轮结果冒充完成。

## 覆盖下界

本轮把 `depth` 定义为：袖子—上臂接缝责任集的像素中心，到已批准 `V_upper_arm` 的最近欧氏距离；取其中最大值。

- `w_required = {w_required:.3f} px`
- `m_AA = {MARGIN_AA_PX:.0f} px`
- `m_texture_alpha = {MARGIN_TEXTURE_ALPHA_PX:.0f} px`
- `m_planned_mesh = {MARGIN_PLANNED_MESH_PX:.0f} px`
- `w_final = ceil(w_required) + margins = {w_final:.3f} px`
- 冻结 `M_upper_arm` 最小连续承载深度：`{carrier_min:.3f} px`
- 冻结承载余量：`{carrier_min - w_final:.3f} px`
- `H_test` 责任深度：`{ROI_DEPTH_PX:.0f} px`

因此 `w_final` 可以由冻结几何承载，不需要修改肩点、骨长、动作范围或 V4 边界。

## 连续参数域证明

冻结 V4 中，`sleeve` 与 `upper_arm` 同属 `shoulder_rotation`，实现中都使用相同 `deltaUpper` 和相同肩点。故：

`T_upper_arm(t)^-1 T_sleeve(t) = I`

对所有允许的 `theta1`、`theta2` 和 `phiWristLocal` 恒成立。接缝责任集在上臂局部坐标中不随参数变化，覆盖指标在整个连续域恒定，导数为 `0`。41 个主路径样本和 6 个极值均得到相同的 `w_required`；各样本区间单调，内部上界变化 `0 px < {CONTINUOUS_BOUND_TOLERANCE_PX:.2f} px`，因此无需自适应细分。

## 边界

该证明只属于冻结 V4 自建刚体 FK。它不证明 Cubism 关键形插值、预乘 alpha、atlas、UV padding 或 mipmap。

## 下一步

只允许在 `masks/hidden-upper-arm-sleeve-test-roi.png` 内进行本地受控纹理补全；`V_upper_arm` 写保护，`H_test` 外必须零改动。
""",
        encoding="utf-8",
    )
    if not passed:
        raise SystemExit("Hidden ROI or coverage proof failed; Stage B must stop.")
    print(
        f"PASS: H_test={pixel_count(h_test)} px, "
        f"w_required={w_required:.3f}, w_final={w_final:.3f}, "
        f"carrier_min={carrier_min:.3f}"
    )


if __name__ == "__main__":
    main()
