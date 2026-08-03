from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


HERE = Path(__file__).resolve()
REOPEN = HERE.parents[1]
V7 = HERE.parents[2]
VALIDATION = V7.parent
XIAOXING = VALIDATION.parent
V4 = VALIDATION / "arm-chain-screen-right-v4-wrist-motion"
V6 = VALIDATION / "arm-chain-screen-right-v6-complete-upper-arm-geometry"

AUDIT = REOPEN / "audit"
MASKS = REOPEN / "masks"
QA = REOPEN / "qa"

V6_BUILDER = V6 / "tools/build_v6_complete_upper_arm_geometry.py"
SKELETON_PATH = V4 / "skeleton.json"
UPPER_GEOMETRY_PATH = V6 / "masks/upper-arm-complete-geometry.png"
UPPER_VISIBLE_PATH = V6 / "masks/reference/visible-upper-arm-locked-reference.png"
V6_SCAN_PATH = V6 / "samples/fk-41-and-continuous-elbow-scan.json"
V7_INPUT_INTEGRITY_PATH = V7 / "audit/v7a-input-integrity.json"
USER_DECISION_PATH = V7 / "audit/v7a-user-visual-decision-2026-07-26.json"

OLD_ENVELOPE_PATH = V7 / "masks/v6-minimum-envelope-neutral-footprint.png"
SOURCE_SUPPORT_PATH = V7 / "masks/source-arm-neutral-outline-candidate.png"
VISIBLE_FOREARM_PATH = V7 / "masks/visible-forearm-locked.png"

CANVAS = (512, 1086)
SS = 4
ALPHA_THRESHOLD = 16
CROP_RADIUS = 46
ELBOW_CROP = (309, 369, 401, 461)


def load_v6_module():
    spec = importlib.util.spec_from_file_location("v6_frozen_builder", V6_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the frozen V6 builder.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V6_MODULE = load_v6_module()


def ensure_directories() -> None:
    for directory in (AUDIT, MASKS, QA):
        directory.mkdir(parents=True, exist_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def binary(mask: Image.Image, threshold: int = 1) -> Image.Image:
    return mask.convert("L").point(lambda value: 255 if value >= threshold else 0)


def load_alpha(path: Path) -> Image.Image:
    image = Image.open(path)
    if image.mode == "L":
        return binary(image)
    return binary(image.convert("RGBA").getchannel("A"))


def rgba_mask(mask: Image.Image) -> Image.Image:
    output = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    output.putalpha(binary(mask))
    return output


def mask_count(mask: Image.Image) -> int:
    return sum(binary(mask).histogram()[1:])


def mask_pixels(mask: Image.Image):
    core = binary(mask)
    pixels = core.load()
    bbox = core.getbbox()
    if bbox is None:
        return
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            if pixels[x, y]:
                yield x, y


def connected_components(mask: Image.Image) -> int:
    points = set(mask_pixels(mask) or [])
    components = 0
    while points:
        components += 1
        stack = [points.pop()]
        while stack:
            x, y = stack.pop()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in points:
                    points.remove(neighbor)
                    stack.append(neighbor)
    return components


def font(size: int):
    for path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def tint(base: Image.Image, layers: list[tuple[Image.Image, tuple[int, int, int, int]]]):
    output = base.convert("RGBA")
    for mask, color in layers:
        layer = Image.new("RGBA", base.size, color)
        layer.putalpha(ImageChops.multiply(binary(mask), Image.new("L", base.size, color[3])))
        output = Image.alpha_composite(output, layer)
    return output


def local_s_range(mask: Image.Image, elbow: tuple[float, float], axis):
    values = [
        (x + 0.5 - elbow[0]) * axis[0] + (y + 0.5 - elbow[1]) * axis[1]
        for x, y in mask_pixels(mask) or []
    ]
    if not values:
        return None
    return [min(values), max(values)]


def integrity_gate() -> dict:
    report = json.loads(V7_INPUT_INTEGRITY_PATH.read_text(encoding="utf-8"))
    failed_groups = {
        group["name"]: group["failed"] for group in report["frozenArtifactGroups"]
    }
    entries_pass = all(item["pass"] for item in report["orderedMinimumEntries"])
    authority_pass = all(item["pass"] for item in report["authorityImages"])
    groups_pass = all(value == 0 for value in failed_groups.values())
    temporary_pass = report["temporaryForearmRaster"]["pass"]
    decision = json.loads(USER_DECISION_PATH.read_text(encoding="utf-8"))
    decision_pass = (
        decision["approvedItems"].get("contractConflictConclusion") is True
        and decision["approvedItems"].get("dependencyReopenAuthorization") is True
    )
    result = {
        "schemaVersion": 1,
        "gate": "V7-A elbow dependency-reopen input integrity",
        "status": (
            "pass"
            if entries_pass
            and authority_pass
            and groups_pass
            and temporary_pass
            and decision_pass
            else "fail"
        ),
        "minimumEntriesPass": entries_pass,
        "authorityImagesPass": authority_pass,
        "frozenArtifactFailures": failed_groups,
        "temporaryForearmRasterPass": temporary_pass,
        "userAuthorizedDependencyReopen": decision_pass,
        "inputs": [
            {
                "role": "V7-A input integrity",
                "path": "../audit/v7a-input-integrity.json",
                "sha256": sha256(V7_INPUT_INTEGRITY_PATH),
            },
            {
                "role": "user decision",
                "path": "../audit/v7a-user-visual-decision-2026-07-26.json",
                "sha256": sha256(USER_DECISION_PATH),
            },
            {
                "role": "frozen V6 scan",
                "path": "../../arm-chain-screen-right-v6-complete-upper-arm-geometry/"
                "samples/fk-41-and-continuous-elbow-scan.json",
                "sha256": sha256(V6_SCAN_PATH),
            },
        ],
    }
    if result["status"] != "pass":
        raise RuntimeError("Dependency-reopen input integrity failed.")
    return result


def scan_candidate(
    name: str,
    candidate: Image.Image,
    upper_geometry: Image.Image,
    upper_visible: Image.Image,
    source_support: Image.Image,
    skeleton: dict,
    frame,
    primary: list[dict],
    extremes: list[dict],
) -> tuple[dict, list[dict]]:
    _, elbow, _, _, _, _, forearm_axis, _ = frame
    # Delegate the motion-domain calculation to the frozen V6 implementation
    # itself. The outline argument only feeds descriptive width/extension
    # fields, which are deliberately not reused below; all pass/fail values
    # come from the exact V6 4x scan implementation.
    scan_outline = [
        (-24.0, -20.0),
        (24.0, -20.0),
        (130.0, -10.0),
        (130.0, 10.0),
        (24.0, 20.0),
        (-24.0, 20.0),
    ]
    frozen_scan, dense = V6_MODULE.elbow_scan(
        upper_geometry,
        candidate,
        scan_outline,
        skeleton,
        frame,
        primary,
        extremes,
    )
    outside = ImageChops.subtract(binary(candidate), binary(source_support))
    ownership_overlap = ImageChops.multiply(binary(candidate), binary(upper_visible))
    report = {
        "name": name,
        "neutralPixelCount": mask_count(candidate),
        "neutralConnectedComponents": connected_components(candidate),
        "neutralPixelsOutsideSourceSupport": mask_count(outside),
        "neutralPixelsOverlappingFrozenVisibleUpperOwnership": mask_count(
            ownership_overlap
        ),
        "forearmLocalSRangePx": local_s_range(candidate, elbow, forearm_axis),
        "samples": {
            "primary41": frozen_scan["primarySampleCount"],
            "combinationExtremes": frozen_scan["combinationExtremeCount"],
            "denseTheta2": len(dense),
            "denseIntervalDeg": frozen_scan["adaptiveSubdivision"][
                "maximumIntervalDeg"
            ],
            "allEvaluationsIncludingRepeatedAngles": (
                frozen_scan["primarySampleCount"]
                + frozen_scan["combinationExtremeCount"]
                + len(dense)
            ),
        },
        "maximumMissingResponsibilityPixelsAt4x": frozen_scan[
            "maximumMissingResponsibilityPixelsAt4x"
        ],
        "worstGapTheta2Deg": frozen_scan["worstGapTheta2Deg"],
        "brokenAdjacencySamples": frozen_scan["brokenAdjacencySamples"],
        "maximumInnerBendExposedUpperPixelsAt4x": frozen_scan[
            "maximumInnerBendExposedUpperPixelsAt4x"
        ],
        "worstInnerBendExposureTheta2Deg": frozen_scan[
            "worstInnerBendExposureTheta2Deg"
        ],
        "denseSamplesWithInnerBendExposure": sum(
            item["innerBendExposedUpperPixelsAt4x"] > 0 for item in dense
        ),
    }
    report["passesCurrentReopenedContract"] = all(
        (
            report["neutralPixelsOutsideSourceSupport"] == 0,
            report["neutralPixelsOverlappingFrozenVisibleUpperOwnership"] == 0,
            report["maximumMissingResponsibilityPixelsAt4x"] == 0,
            report["brokenAdjacencySamples"] == 0,
            report["maximumInnerBendExposedUpperPixelsAt4x"] == 0,
        )
    )
    return report, dense


def worst_angle_layers(
    candidate: Image.Image,
    upper_geometry: Image.Image,
    skeleton: dict,
    frame,
    theta2: float,
):
    _, elbow, _, _, responsibility_axis, responsibility_normal, _, _ = frame
    box = (
        round(elbow[0] - CROP_RADIUS),
        round(elbow[1] - CROP_RADIUS),
        round(elbow[0] + CROP_RADIUS),
        round(elbow[1] + CROP_RADIUS),
    )
    high_size = ((box[2] - box[0]) * SS, (box[3] - box[1]) * SS)
    center = ((elbow[0] - box[0]) * SS, (elbow[1] - box[1]) * SS)
    upper = binary(upper_geometry.crop(box)).resize(
        high_size, Image.Resampling.NEAREST
    )
    moving = binary(candidate.crop(box)).resize(
        high_size, Image.Resampling.NEAREST
    )
    rest_theta2 = float(skeleton["restAnglesDeg"]["theta2"])
    delta = theta2 - rest_theta2
    rotated = moving.rotate(
        delta, resample=Image.Resampling.BICUBIC, center=center, fillcolor=0
    )
    rotated = binary(rotated, ALPHA_THRESHOLD)
    visible_upper = ImageChops.subtract(upper, rotated)
    angle = math.radians(delta)
    cosine, sine = math.cos(angle), math.sin(angle)
    current_axis = (
        cosine * responsibility_axis[0] - sine * responsibility_axis[1],
        sine * responsibility_axis[0] + cosine * responsibility_axis[1],
    )
    current_normal = (
        cosine * responsibility_normal[0] - sine * responsibility_normal[1],
        sine * responsibility_normal[0] + cosine * responsibility_normal[1],
    )
    exposure = Image.new("L", high_size, 0)
    out = exposure.load()
    for x, y in mask_pixels(visible_upper) or []:
        dx = (x + 0.5 - center[0]) / SS
        dy = (y + 0.5 - center[1]) / SS
        local_s = dx * current_axis[0] + dy * current_axis[1]
        local_n = dx * current_normal[0] + dy * current_normal[1]
        if -12.0 <= local_s <= 8.0 and local_n < 0.0:
            out[x, y] = 255
    return upper, rotated, exposure


def panel(title_text: str, subtitle: str, image: Image.Image) -> Image.Image:
    width, height = 900, 650
    result = Image.new("RGB", (width, height), (250, 250, 250))
    draw = ImageDraw.Draw(result)
    draw.text((24, 18), title_text, font=font(30), fill=(25, 25, 25))
    draw.text((24, 58), subtitle, font=font(19), fill=(80, 80, 80))
    content = image.convert("RGB")
    content.thumbnail((850, 530), Image.Resampling.NEAREST)
    result.paste(content, ((width - content.width) // 2, 100))
    return result


def make_qa(
    old_envelope: Image.Image,
    source_support: Image.Image,
    upper_visible: Image.Image,
    strict_max: Image.Image,
    source_max: Image.Image,
    strict_report: dict,
    source_report: dict,
    upper_geometry: Image.Image,
    skeleton: dict,
    frame,
) -> None:
    crop = ELBOW_CROP
    neutral_base = Image.new("RGBA", CANVAS, (255, 255, 255, 255))
    conflict = ImageChops.multiply(old_envelope, upper_visible)
    outside = ImageChops.subtract(old_envelope, source_support)
    old_review = tint(
        neutral_base,
        [
            (old_envelope, (215, 40, 165, 180)),
            (conflict, (240, 25, 25, 235)),
            (outside, (255, 200, 0, 240)),
        ],
    ).crop(crop)
    strict_review = tint(
        neutral_base,
        [
            (upper_visible, (235, 125, 70, 175)),
            (strict_max, (0, 175, 155, 190)),
        ],
    ).crop(crop)

    strict_layers = worst_angle_layers(
        strict_max,
        upper_geometry,
        skeleton,
        frame,
        strict_report["worstInnerBendExposureTheta2Deg"],
    )
    source_layers = worst_angle_layers(
        source_max,
        upper_geometry,
        skeleton,
        frame,
        source_report["worstInnerBendExposureTheta2Deg"],
    )
    high_base = Image.new("RGBA", strict_layers[0].size, (255, 255, 255, 255))
    strict_worst = tint(
        high_base,
        [
            (strict_layers[0], (235, 125, 70, 200)),
            (strict_layers[1], (0, 175, 155, 190)),
            (strict_layers[2], (240, 25, 25, 245)),
        ],
    )
    source_worst = tint(
        high_base,
        [
            (source_layers[0], (235, 125, 70, 200)),
            (source_layers[1], (0, 175, 155, 190)),
            (source_layers[2], (240, 25, 25, 245)),
        ],
    )

    panels = [
        panel(
            "1｜旧冻结代理：合同冲突",
            "红=与冻结可见上臂重复 416 px；黄=进入背景 132 px",
            old_review.resize((460, 540), Image.Resampling.NEAREST),
        ),
        panel(
            "2｜严格最大候选：中性位合法",
            "青=原轮廓内且不重复上臂的最大集合；橙=冻结可见上臂",
            strict_review.resize((460, 540), Image.Resampling.NEAREST),
        ),
        panel(
            "3｜严格最大候选：完整肘角失败",
            f"红=内弯异常暴露；最坏 {strict_report['maximumInnerBendExposedUpperPixelsAt4x']} 个 4× 子像素",
            strict_worst,
        ),
        panel(
            "4｜反证上界：连整条原手臂轮廓也失败",
            f"已允许重占上臂仍剩 {source_report['maximumInnerBendExposedUpperPixelsAt4x']} 个 4× 子像素",
            source_worst,
        ),
    ]
    board = Image.new("RGB", (1840, 1390), (238, 238, 238))
    draw = ImageDraw.Draw(board)
    draw.text(
        (30, 20),
        "小星 V7-A｜肘部依赖合同重开：最大集合反证",
        font=font(38),
        fill=(20, 20, 20),
    )
    draw.text(
        (30, 70),
        "结论：在冻结骨架、冻结上臂、原轮廓中性足迹和静态刚体前臂同时保持时，不存在通过候选。",
        font=font(23),
        fill=(65, 65, 65),
    )
    for index, item in enumerate(panels):
        x = 20 + (index % 2) * 910
        y = 115 + (index // 2) * 650
        board.paste(item, (x, y))
    board.save(QA / "V7-A-ELBOW-CONTRACT-REOPEN-BOARD.png")

    rgba_mask(strict_layers[2]).save(
        MASKS / "strict-max-worst-angle-inner-bend-exposure-4x.png"
    )
    rgba_mask(source_layers[2]).save(
        MASKS / "source-max-worst-angle-inner-bend-exposure-4x.png"
    )


def main() -> None:
    ensure_directories()
    integrity = integrity_gate()
    (AUDIT / "v7a-elbow-contract-reopen-input-integrity.json").write_text(
        json.dumps(integrity, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    skeleton = json.loads(SKELETON_PATH.read_text(encoding="utf-8"))
    frame = V6_MODULE.local_frame(skeleton)
    primary = V6_MODULE.primary_states(skeleton)
    extremes = V6_MODULE.extreme_states(skeleton)

    old_envelope = load_alpha(OLD_ENVELOPE_PATH)
    source_support = load_alpha(SOURCE_SUPPORT_PATH)
    upper_visible = load_alpha(UPPER_VISIBLE_PATH)
    upper_geometry = load_alpha(UPPER_GEOMETRY_PATH)
    visible_forearm = load_alpha(VISIBLE_FOREARM_PATH)

    source_clipped = ImageChops.multiply(old_envelope, source_support)
    strict_max = ImageChops.subtract(source_support, upper_visible)
    source_max = source_support.copy()
    strict_visible_root = ImageChops.lighter(
        visible_forearm,
        ImageChops.subtract(source_clipped, upper_visible),
    )

    masks = {
        "frozen-envelope-source-clipped.png": source_clipped,
        "strict-source-and-unique-maximum.png": strict_max,
        "source-compatible-maximum-with-reassignment.png": source_max,
        "approved-visible-plus-strict-root.png": strict_visible_root,
    }
    for name, mask in masks.items():
        rgba_mask(mask).save(MASKS / name)

    candidates = {
        "frozen_proxy": old_envelope,
        "source_clipped_frozen_proxy": source_clipped,
        "strict_source_and_unique_maximum": strict_max,
        "source_compatible_maximum_with_ownership_reassignment": source_max,
    }
    reports = {}
    scans = {}
    for name, candidate in candidates.items():
        report, dense = scan_candidate(
            name,
            candidate,
            upper_geometry,
            upper_visible,
            source_support,
            skeleton,
            frame,
            primary,
            extremes,
        )
        reports[name] = report
        scans[name] = dense

    old_scan = json.loads(V6_SCAN_PATH.read_text(encoding="utf-8"))
    strict_report = reports["strict_source_and_unique_maximum"]
    source_report = reports[
        "source_compatible_maximum_with_ownership_reassignment"
    ]
    proof = {
        "schemaVersion": 1,
        "gate": "V7-A elbow dependency contract reopen",
        "status": "fail_no_static_source_compatible_candidate",
        "scope": "contract proof only; no production forearm geometry generated",
        "frozenDomain": {
            "elbow": [
                skeleton["landmarks"]["elbow"]["x"],
                skeleton["landmarks"]["elbow"]["y"],
            ],
            "wrist": [
                skeleton["landmarks"]["wrist"]["x"],
                skeleton["landmarks"]["wrist"]["y"],
            ],
            "L1Px": skeleton["boneLengthsPx"]["L1ShoulderToElbow"],
            "L2Px": skeleton["boneLengthsPx"]["L2ElbowToWrist"],
            "theta2RangeDeg": [
                skeleton["allowedRangesDeg"]["theta2"]["min"],
                skeleton["allowedRangesDeg"]["theta2"]["max"],
            ],
            "primarySampleCount": len(primary),
            "combinationExtremeCount": len(extremes),
            "denseTheta2SampleCount": 241,
            "supersampling": SS,
        },
        "sets": {
            "A_frozen_proxy": {
                "pixelCount": mask_count(old_envelope),
                "outsideSourceSupportPixels": mask_count(
                    ImageChops.subtract(old_envelope, source_support)
                ),
                "overlapFrozenVisibleUpperPixels": mask_count(
                    ImageChops.multiply(old_envelope, upper_visible)
                ),
            },
            "S_source_support": {
                "pixelCount": mask_count(source_support),
                "meaning": "maximum neutral footprint allowed by the approved source-arm outline",
            },
            "M_strict_maximum": {
                "definition": "S minus frozen visible upper-arm ownership",
                "pixelCount": mask_count(strict_max),
                "meaning": "set-theoretic maximum under both source containment and unique ownership",
            },
        },
        "candidateResults": reports,
        "upperBoundProof": {
            "premise1": "Every neutral source-compatible static forearm candidate P is a subset of S.",
            "premise2": "For a fixed elbow rotation, rotating a subset preserves subset inclusion: R(P) is a subset of R(S).",
            "premise3": (
                "At the worst frozen theta2, even R(S), the largest admissible "
                "occluder, leaves frozen upper-arm pixels exposed in the V6 inner-bend responsibility zone."
            ),
            "sourceMaximumWorstTheta2Deg": source_report[
                "worstInnerBendExposureTheta2Deg"
            ],
            "sourceMaximumInnerBendExposedUpperPixelsAt4x": source_report[
                "maximumInnerBendExposedUpperPixelsAt4x"
            ],
            "conclusion": (
                "No static production forearm whose neutral footprint remains "
                "inside the approved source-arm outline can satisfy the frozen "
                "V6 zero-inner-bend-exposure condition over the full frozen theta2 domain."
            ),
        },
        "earliestInvalidGate": "neutral footprint versus full-domain elbow coverage contract",
        "requiredScopeChangeBeforeAnyFurtherGeometry": [
            "revise frozen V6 elbow/upper-arm geometry or ownership",
            "revise the zero-inner-bend-exposure responsibility definition",
            "allow an angle-dependent non-rigid elbow solution in a later Cubism gate",
            "or change another currently frozen constraint such as draw order or motion range",
        ],
        "notAuthorizedAndNotPerformed": [
            "no V4, sleeve, or V6 byte changed",
            "no complete production forearm geometry",
            "no texture, PSD, Cubism, Physics, or Runtime",
            "no motion-range or bone-length reduction",
        ],
        "frozenV6ReportedMaximumInnerBendExposureAt4x": reports[
            "frozen_proxy"
        ]["maximumInnerBendExposedUpperPixelsAt4x"],
    }
    (AUDIT / "v7a-elbow-contract-reopen-proof.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (AUDIT / "v7a-elbow-contract-reopen-dense-scans.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "theta2Scan": scans,
                "note": "241 dense samples per candidate; primary and extreme summaries are in the proof report.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    make_qa(
        old_envelope,
        source_support,
        upper_visible,
        strict_max,
        source_max,
        strict_report,
        source_report,
        upper_geometry,
        skeleton,
        frame,
    )

    report_md = f"""# V7-A 肘部依赖合同重开结论

## 结论

当前门禁不通过。失败点不是某一条候选轮廓画得不够好，而是冻结条件之间没有静态刚体解。

- 旧 V6 临时根部代理：{mask_count(old_envelope)} px。
- 旧代理进入原手臂轮廓外：{proof['sets']['A_frozen_proxy']['outsideSourceSupportPixels']} px。
- 旧代理与冻结可见上臂重复所有权：{proof['sets']['A_frozen_proxy']['overlapFrozenVisibleUpperPixels']} px。
- 严格最大候选在中性位同时满足“原轮廓内”和“不重复上臂”，但完整肘角扫描最坏仍暴露 {strict_report['maximumInnerBendExposedUpperPixelsAt4x']} 个 4× 子像素。
- 即使把整份原手臂轮廓都假设为前臂可用足迹，并允许重占上臂像素，最坏仍暴露 {source_report['maximumInnerBendExposedUpperPixelsAt4x']} 个 4× 子像素。

因此，任何更小的原轮廓内静态前臂候选都不可能把这个暴露数降到 0。

## 为什么这是上界反证

设 `S` 为原手臂轮廓允许的最大中性足迹，任意合规静态前臂 `P` 都满足 `P ⊆ S`。绕同一冻结肘点旋转后仍有 `R(P) ⊆ R(S)`。在冻结最坏肘角 {source_report['worstInnerBendExposureTheta2Deg']:.6f}°，最大集合 `R(S)` 仍不能覆盖 V6 内弯责任区，所以任何 `R(P)` 也不能。

## 扫描域

- 主路径：41 个样本。
- 组合极值：6 个。
- 肘角密扫：241 点，间隔 0.1°。
- 4× 超采样，责任区和内弯检查沿用 V6 定义。
- 未缩短骨长，未缩小动作范围。

## 当前停止点

最早无效门禁为：**中性足迹相容性与完整肘角覆盖合同同时成立**。

继续前必须明确改变至少一项当前冻结前提：V6 肘侧几何/所有权、内弯零暴露责任定义、绘制顺序、动作范围，或改为后续按角度变形的非刚体方案。当前授权只允许重开检查，不允许替你选择并修改这些冻结前提。

## 未执行

- 未生成完整正式前臂几何。
- 未改 V4、完整袖子或 V6 文件。
- 未制作纹理、PSD、Cubism、Physics 或 Runtime。
"""
    (AUDIT / "V7-A-ELBOW-CONTRACT-REOPEN.zh-CN.md").write_text(
        report_md, encoding="utf-8"
    )

    generated = [
        path
        for directory in (AUDIT, MASKS, QA)
        for path in sorted(directory.glob("*"))
        if path.is_file() and path.name != "v7a-elbow-contract-reopen-evidence-manifest.json"
    ]
    manifest = {
        "schemaVersion": 1,
        "gate": "V7-A elbow dependency contract reopen evidence",
        "status": proof["status"],
        "checksumAlgorithm": "SHA-256",
        "files": [
            {
                "path": path.relative_to(REOPEN).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in generated
        ],
    }
    (AUDIT / "v7a-elbow-contract-reopen-evidence-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(
        {
            "status": proof["status"],
            "strictMaxWorstInnerExposure4x": strict_report[
                "maximumInnerBendExposedUpperPixelsAt4x"
            ],
            "sourceMaxWorstInnerExposure4x": source_report[
                "maximumInnerBendExposedUpperPixelsAt4x"
            ],
            "board": "qa/V7-A-ELBOW-CONTRACT-REOPEN-BOARD.png",
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
