from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
V7 = HERE.parents[2]
VALIDATION = V7.parent
V4 = VALIDATION / "arm-chain-screen-right-v4-wrist-motion"
V5 = VALIDATION / "arm-chain-screen-right-v5-hidden-upper-arm"
V6 = VALIDATION / "arm-chain-screen-right-v6-complete-upper-arm-geometry"
B0 = V7 / "v7b0-structure-feasibility"
REOPEN = V7 / "v6-elbow-contract-reopen"

AUDIT = ROOT / "audit"
MASKS = ROOT / "masks"
QA = ROOT / "qa"

BASE_BUILDER = REOPEN / "tools/build_v7a_elbow_contract_reopen.py"
OWNERSHIP_BUILDER = V7 / "tools/build_v7a_ownership_gate.py"
B0_BUILDER = B0 / "tools/build_v7b0_structure_feasibility.py"
B0_REJECTION_PATH = AUDIT.parent.parent / (
    "v7b0-structure-feasibility/audit/"
    "v7b0-user-visual-rejection-2026-07-26.json"
)

SKELETON_PATH = V4 / "skeleton.json"
UPPER_GEOMETRY_PATH = V6 / "masks/upper-arm-complete-geometry.png"
UPPER_VISIBLE_PATH = V6 / "masks/reference/visible-upper-arm-locked-reference.png"
SLEEVE_PATH = V5 / "complete-sleeve-final/inputs/sleeve-complete-geometry-r9.png"
VISIBLE_FOREARM_PATH = V7 / "masks/visible-forearm-locked.png"
SOURCE_SUPPORT_PATH = V7 / "masks/source-arm-neutral-outline-candidate.png"
V6_REPORT_PATH = V6 / "audit/complete-upper-arm-geometry-report.json"
HIDDEN_ROOT_PROBE_PATH = (
    B0 / "masks/split-hidden-root-registered-probe.png"
)

SS = 4
ALPHA_THRESHOLD = 16
CROP_RADIUS = 54


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = load_module("v7b1_base", BASE_BUILDER)
OWNERSHIP = load_module("v7b1_ownership", OWNERSHIP_BUILDER)
B0_MODULE = load_module("v7b1_b0", B0_BUILDER)
V6_MODULE = BASE.V6_MODULE


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


def load_mask(path: Path) -> Image.Image:
    image = Image.open(path)
    if image.mode == "L":
        return binary(image)
    return binary(image.convert("RGBA").getchannel("A"), ALPHA_THRESHOLD)


def mask_count(mask: Image.Image) -> int:
    return sum(binary(mask).histogram()[1:])


def connected_components(mask: Image.Image) -> int:
    points: set[tuple[int, int]] = set()
    core = binary(mask)
    pixels = core.load()
    bbox = core.getbbox()
    if bbox is not None:
        for y in range(bbox[1], bbox[3]):
            for x in range(bbox[0], bbox[2]):
                if pixels[x, y]:
                    points.add((x, y))
    components = 0
    while points:
        components += 1
        stack = [points.pop()]
        while stack:
            x, y = stack.pop()
            for neighbor in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            ):
                if neighbor in points:
                    points.remove(neighbor)
                    stack.append(neighbor)
    return components


def rgba_mask(mask: Image.Image) -> Image.Image:
    output = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    output.putalpha(binary(mask))
    return output


def section_profile(
    mask: Image.Image,
    origin: tuple[float, float],
    axis: tuple[float, float],
    normal: tuple[float, float],
    targets: list[float],
    half_band: float = 0.55,
) -> list[dict]:
    core = binary(mask)
    pixels = core.load()
    bbox = core.getbbox()
    projected: list[tuple[float, float]] = []
    if bbox is not None:
        for y in range(bbox[1], bbox[3]):
            for x in range(bbox[0], bbox[2]):
                if not pixels[x, y]:
                    continue
                dx = x + 0.5 - origin[0]
                dy = y + 0.5 - origin[1]
                projected.append(
                    (
                        dx * axis[0] + dy * axis[1],
                        dx * normal[0] + dy * normal[1],
                    )
                )
    result = []
    for target in targets:
        values = [
            n for s, n in projected if abs(s - target) <= half_band
        ]
        if not values:
            result.append(
                {
                    "sPx": target,
                    "negativeNormalPx": None,
                    "positiveNormalPx": None,
                    "fullRasterWidthPx": None,
                    "boundaryCenterNormalPx": None,
                }
            )
            continue
        low, high = min(values), max(values)
        result.append(
            {
                "sPx": target,
                "negativeNormalPx": low,
                "positiveNormalPx": high,
                "fullRasterWidthPx": high - low + 1.0,
                "boundaryCenterNormalPx": (low + high) / 2.0,
            }
        )
    return result


def interpolate_profile(points: list[tuple[float, float]], s: float) -> float:
    if s <= points[0][0]:
        return points[0][1]
    for (s0, n0), (s1, n1) in zip(points, points[1:]):
        if s <= s1:
            progress = (s - s0) / (s1 - s0)
            return n0 + (n1 - n0) * progress
    return points[-1][1]


def rotate_mask(
    mask: Image.Image,
    elbow: tuple[float, float],
    delta_angle: float,
) -> Image.Image:
    box = (
        round(elbow[0] - CROP_RADIUS),
        round(elbow[1] - CROP_RADIUS),
        round(elbow[0] + CROP_RADIUS),
        round(elbow[1] + CROP_RADIUS),
    )
    size = ((box[2] - box[0]) * SS, (box[3] - box[1]) * SS)
    center = (
        (elbow[0] - box[0]) * SS,
        (elbow[1] - box[1]) * SS,
    )
    high = binary(mask.crop(box)).resize(size, Image.Resampling.NEAREST)
    moved = high.rotate(
        delta_angle,
        resample=Image.Resampling.BICUBIC,
        center=center,
        fillcolor=0,
    )
    return binary(moved, ALPHA_THRESHOLD)


def make_board(
    skeleton: dict,
    frame,
    visible_forearm: Image.Image,
    hidden_root_probe: Image.Image,
    upper_geometry: Image.Image,
    sleeve: Image.Image,
    excess: Image.Image,
    uncovered: Image.Image,
    upper_terminal_width: float,
    forearm_root_width: float,
) -> None:
    _, elbow, _, _, _, _, _, _ = frame
    minimum = float(skeleton["allowedRangesDeg"]["theta2"]["min"])
    rest = float(skeleton["restAnglesDeg"]["theta2"])
    delta = minimum - rest
    box = (
        round(elbow[0] - CROP_RADIUS),
        round(elbow[1] - CROP_RADIUS),
        round(elbow[0] + CROP_RADIUS),
        round(elbow[1] + CROP_RADIUS),
    )
    size = ((box[2] - box[0]) * SS, (box[3] - box[1]) * SS)
    center = (
        (elbow[0] - box[0]) * SS,
        (elbow[1] - box[1]) * SS,
    )

    upper = binary(upper_geometry.crop(box)).resize(
        size, Image.Resampling.NEAREST
    )
    sleeve_high = binary(sleeve.crop(box)).resize(
        size, Image.Resampling.NEAREST
    )
    visible = rotate_mask(visible_forearm, elbow, delta)
    moved_excess = rotate_mask(excess, elbow, delta)
    moved_hidden_root = rotate_mask(hidden_root_probe, elbow, delta)
    moved_hidden_root_visible = ImageChops.subtract(
        moved_hidden_root,
        ImageChops.lighter(
            ImageChops.lighter(upper, sleeve_high),
            visible,
        ),
    )

    bent = Image.new("RGB", size, (255, 255, 255))
    bent.paste((236, 144, 92), mask=upper)
    bent.paste((66, 187, 174), mask=visible)
    bent.paste((235, 35, 45), mask=moved_excess)
    bent.paste((145, 82, 210), mask=moved_hidden_root_visible)
    bent.paste((164, 174, 189), mask=sleeve_high)

    neutral_base = Image.new("RGBA", visible_forearm.size, (255, 255, 255, 255))
    neutral = BASE.tint(
        neutral_base,
        [
            (upper_geometry, (236, 144, 92, 210)),
            (visible_forearm, (66, 187, 174, 210)),
            (excess, (235, 35, 45, 245)),
            (sleeve, (164, 174, 189, 220)),
        ],
    ).crop(box)
    trim_conflict = BASE.tint(
        neutral_base,
        [
            (visible_forearm, (66, 187, 174, 160)),
            (upper_geometry, (236, 144, 92, 150)),
            (excess, (230, 40, 155, 220)),
            (uncovered, (235, 25, 35, 255)),
        ],
    ).crop(box)

    items = [
        (
            "1｜中性根部",
            "红=当前 V_forearm 自身超出 V6 外弯收窄参考的源像素",
            neutral.resize(size, Image.Resampling.NEAREST).convert("RGB"),
        ),
        (
            f"2｜最弯 θ2={minimum:.3f}°",
            "红=V自身宽出；紫=被用户否决的D方案额外H_root突出",
            bent,
        ),
        (
            "3｜不能直接静态裁掉",
            f"红=现有上臂未承接 {mask_count(uncovered)} px；裁掉会破坏中性原图",
            trim_conflict.resize(size, Image.Resampling.NEAREST).convert("RGB"),
        ),
    ]
    panel_width, panel_height = 760, 720
    board = Image.new(
        "RGB",
        (panel_width * 3 + 30, panel_height + 120),
        (238, 238, 238),
    )
    draw = ImageDraw.Draw(board)
    draw.text(
        (22, 14),
        "V7-B1｜肘部粗细不对版：静态刚体冲突",
        font=BASE.font(34),
        fill=(24, 24, 24),
    )
    draw.text(
        (22, 58),
        (
            f"同口径截面：上臂肘端约 {upper_terminal_width:.2f}px；"
            f"前臂根部约 {forearm_root_width:.2f}px；"
            f"差 {forearm_root_width - upper_terminal_width:.2f}px。"
        ),
        font=BASE.font(20),
        fill=(65, 65, 65),
    )
    for index, (title, subtitle, image) in enumerate(items):
        x = 10 + index * panel_width
        draw.text(
            (x + 18, 118),
            title,
            font=BASE.font(27),
            fill=(30, 30, 30),
        )
        draw.text(
            (x + 18, 158),
            subtitle,
            font=BASE.font(16),
            fill=(70, 70, 70),
        )
        content = image.copy()
        content.thumbnail((700, 520), Image.Resampling.NEAREST)
        board.paste(content, (x + (panel_width - content.width) // 2, 205))
    board.save(QA / "V7-B1-ROOT-WIDTH-CONFLICT-BOARD.png")


def main() -> None:
    ensure_directories()
    rejection = json.loads(B0_REJECTION_PATH.read_text(encoding="utf-8"))
    if rejection["status"] != "split_hidden_root_probe_visually_rejected":
        raise RuntimeError("The current user visual rejection is missing.")
    integrity = OWNERSHIP.verify_inputs()
    if integrity["status"] != "pass":
        raise RuntimeError("Frozen or authority input integrity failed.")

    skeleton = json.loads(SKELETON_PATH.read_text(encoding="utf-8"))
    frame = V6_MODULE.local_frame(skeleton)
    shoulder, elbow, _, length1, upper_axis, upper_normal, forearm_axis, forearm_normal = frame

    visible_forearm = load_mask(VISIBLE_FOREARM_PATH)
    hidden_root_probe = load_mask(HIDDEN_ROOT_PROBE_PATH)
    upper_geometry = load_mask(UPPER_GEOMETRY_PATH)
    upper_visible = load_mask(UPPER_VISIBLE_PATH)
    sleeve = load_mask(SLEEVE_PATH)
    source_support = load_mask(SOURCE_SUPPORT_PATH)
    v6_report = json.loads(V6_REPORT_PATH.read_text(encoding="utf-8"))
    temporary_profile = v6_report["elbowProtrusionRefinement"][
        "temporaryForearmRootWidthProfile"
    ]
    outer_profile = [
        (float(item["sPx"]), float(item["outerBendPositiveNormalPx"]))
        for item in temporary_profile
        if 0.0 <= float(item["sPx"]) <= 22.0
    ]

    excess = Image.new("L", visible_forearm.size, 0)
    excess_pixels = excess.load()
    visible_pixels = visible_forearm.load()
    for y in range(visible_forearm.height):
        for x in range(visible_forearm.width):
            if not visible_pixels[x, y]:
                continue
            dx = x + 0.5 - elbow[0]
            dy = y + 0.5 - elbow[1]
            s = dx * forearm_axis[0] + dy * forearm_axis[1]
            n = dx * forearm_normal[0] + dy * forearm_normal[1]
            if 0.0 <= s <= 22.0 and n > interpolate_profile(outer_profile, s):
                excess_pixels[x, y] = 255

    covered_by_upper = ImageChops.multiply(excess, upper_geometry)
    uncovered = ImageChops.subtract(excess, upper_geometry)

    upper_profile = section_profile(
        upper_geometry,
        shoulder,
        upper_axis,
        upper_normal,
        [length1 - 4.0, length1],
    )
    forearm_profile = section_profile(
        visible_forearm,
        elbow,
        forearm_axis,
        forearm_normal,
        [1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0, 22.0],
    )
    upper_terminal_width = max(
        item["fullRasterWidthPx"]
        for item in upper_profile
        if item["fullRasterWidthPx"] is not None
    )
    forearm_root_width = max(
        item["fullRasterWidthPx"]
        for item in forearm_profile[:3]
        if item["fullRasterWidthPx"] is not None
    )

    report = {
        "schemaVersion": 1,
        "gate": "V7-B1 elbow root-width compatibility reopen",
        "status": "fail_static_rigid_root_width_conflict",
        "trigger": {
            "decisionOwner": "user",
            "sourceStatement": rejection["sourceStatement"],
            "rejectedProbe": "V7-B0 split hidden-root structure",
            "singleDrawableBaselineApprovalInferred": False,
            "interpretation": (
                "the screenshots show the rejected split H_root protrusion; "
                "the same review also exposes an independent width mismatch "
                "between the frozen upper terminal and current V_forearm root"
            ),
        },
        "frozenIntegrity": {
            "status": integrity["status"],
            "groups": [
                {
                    "name": group["name"],
                    "checked": group["checked"],
                    "passed": group["passed"],
                    "failed": group["failed"],
                }
                for group in integrity["frozenArtifactGroups"]
            ],
        },
        "measurementMethod": {
            "pixelCenters": True,
            "sectionHalfBandPx": 0.55,
            "upperSectionsRelativeToShoulderPx": [
                length1 - 4.0,
                length1,
            ],
            "forearmSectionsRelativeToElbowPx": [
                1.0,
                2.0,
                3.0,
                4.0,
                6.0,
                8.0,
                10.0,
                22.0,
            ],
            "sameRasterMethodUsedForBothMaterials": True,
        },
        "widthProfiles": {
            "upperTerminal": upper_profile,
            "visibleForearmRoot": forearm_profile,
            "upperTerminalReferenceWidthPx": upper_terminal_width,
            "forearmRootMaximumWidthPx": forearm_root_width,
            "rootWiderThanUpperByPx": forearm_root_width - upper_terminal_width,
        },
        "v6ApprovedTemporaryOuterTaperReference": {
            "profile": temporary_profile,
            "productionForearmWasExplicitlyNotApproved": True,
        },
        "outerBendExcessAgainstV6Taper": {
            "pixelCount": mask_count(excess),
            "connectedComponents": connected_components(excess),
            "allPixelsAreApprovedVisibleForearmSourcePixels": (
                mask_count(ImageChops.subtract(excess, visible_forearm)) == 0
            ),
            "insideSourceSupportPixels": mask_count(
                ImageChops.multiply(excess, source_support)
            ),
            "coveredByFrozenUpperGeometryPixels": mask_count(covered_by_upper),
            "notCoveredByFrozenUpperGeometryPixels": mask_count(uncovered),
            "overlapFrozenVisibleUpperOwnershipPixels": mask_count(
                ImageChops.multiply(excess, upper_visible)
            ),
        },
        "rejectedSplitProbeRelation": {
            "hiddenRootProbePixelCount": mask_count(hidden_root_probe),
            "role": (
                "separate rejected protrusion source; it is not the same mask "
                "as the visible-forearm outer-width excess"
            ),
        },
        "proof": {
            "premise1": (
                "Rigid rotation preserves the forearm root cross-section, so "
                "the measured outer-side width excess remains present in bent poses."
            ),
            "premise2": (
                "Statically removing the excess changes approved source-visible "
                "forearm ownership."
            ),
            "premise3": (
                f"{mask_count(uncovered)} of {mask_count(excess)} excess pixels "
                "are not covered by the frozen complete upper-arm geometry in neutral."
            ),
            "conclusion": (
                "The current static rigid single-drawable geometry cannot both "
                "preserve the neutral source composite and remove the bent-pose "
                "outer protrusion by a simple root trim."
            ),
        },
        "earliestInvalidGate": (
            "elbow root cross-section compatibility under the frozen motion domain"
        ),
        "nextStructureDecision": {
            "recommended": (
                "authorize a pure-color angle-dependent outer-root taper "
                "feasibility blockout while keeping neutral ownership exact"
            ),
            "fallback": (
                "reopen the neutral elbow ownership and draw-order architecture"
            ),
            "notAllowedAsFix": [
                "restore split H_root",
                "hide the protrusion with the sleeve or bracelet",
                "shrink bone lengths or elbow range",
                "statically delete the source-visible excess pixels",
                "claim that zero transparent gap proves visual continuity",
            ],
        },
        "notPerformed": [
            "no approved visible forearm pixel changed",
            "no frozen V4, complete sleeve, or V6 byte changed",
            "no replacement elbow geometry",
            "no contract rewrite",
            "no complete production forearm geometry",
            "no texture, PSD, ArtMesh, Cubism, Physics, or Runtime",
        ],
        "inputHashes": {
            "visibleForearm": sha256(VISIBLE_FOREARM_PATH),
            "upperGeometry": sha256(UPPER_GEOMETRY_PATH),
            "upperVisible": sha256(UPPER_VISIBLE_PATH),
            "completeSleeve": sha256(SLEEVE_PATH),
            "sourceSupport": sha256(SOURCE_SUPPORT_PATH),
            "skeleton": sha256(SKELETON_PATH),
            "v6Report": sha256(V6_REPORT_PATH),
            "rejectedHiddenRootProbe": sha256(HIDDEN_ROOT_PROBE_PATH),
            "userVisualRejection": sha256(B0_REJECTION_PATH),
        },
        "visualEvidence": {
            "rootWidthConflictBoard": "qa/V7-B1-ROOT-WIDTH-CONFLICT-BOARD.png"
        },
    }

    rgba_mask(excess).save(MASKS / "outer-bend-width-excess-vs-v6-taper.png")
    rgba_mask(covered_by_upper).save(
        MASKS / "outer-bend-excess-covered-by-upper.png"
    )
    rgba_mask(uncovered).save(
        MASKS / "outer-bend-excess-uncovered-in-neutral.png"
    )
    (AUDIT / "v7b1-root-width-conflict.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    make_board(
        skeleton,
        frame,
        visible_forearm,
        hidden_root_probe,
        upper_geometry,
        sleeve,
        excess,
        uncovered,
        upper_terminal_width,
        forearm_root_width,
    )

    report_md = f"""# V7-B1 肘部根部粗细冲突

## 用户反馈

> {rejection['sourceStatement']}

该反馈正式否决 V7-B0 分层 `H_root` 探针。没有据此推断用户已批准或否决单层基线。

## 测量

- 上臂肘端同口径栅格宽度：`{upper_terminal_width:.6f}px`；
- 当前可见前臂根部最大宽度：`{forearm_root_width:.6f}px`；
- 前臂根部宽出：`{forearm_root_width - upper_terminal_width:.6f}px`。

差异主要位于外弯侧。以 V6 已获批但明确仅用于 QA 的防突出临时根部外侧剖面为参考：

- 当前正式可见前臂会落在参考外的源像素：`{mask_count(excess)}`；
- 其中现有冻结上臂几何可在中性位承接：`{mask_count(covered_by_upper)}`；
- 不能由现有上臂承接：`{mask_count(uncovered)}`。

## 结论

当前静态刚体前臂不能靠“直接裁窄”解决：

1. 这 `{mask_count(excess)}` 个像素都是批准可见前臂中的源像素；
2. 裁掉后有 `{mask_count(uncovered)}` 个像素在中性位没有上臂材料补回；
3. 保留它们并做刚体旋转，又会在弯曲时保持原宽度，形成外侧台阶；
4. 被用户否决的 `D` 方案还会在另一侧额外露出 `H_root`。两者是不同像素来源，不能混为一个问题。

所以最早失效点是：**冻结动作域内的肘部根部截面相容性**，不是遮挡计数或纹理。

## 下一步建议

优先做一个仍处于纯色阶段的“随肘角连续收窄外侧根部”可行性块，不制作 ArtMesh 或 Cubism 文件：

- 中性位保持批准源像素和回组不变；
- 越接近最弯，外弯侧局部连续压缩到与上臂末端匹配；
- 内弯侧保持覆盖；
- 骨点、骨长和动作域不变；
- 检查 41+6+241 样本、宽度连续、无尖刺、无缺口和 `0→1→0` 回程；
- 先用纯色慢扫让用户判断粗细是否自然。

如果不允许角度相关收窄，只能重开中性肘部像素所有权和绘制顺序；不能静态裁掉当前源像素。

## 未执行

- 未改批准前臂；
- 未改 V4、袖子或 V6；
- 未生成替代几何；
- 未改合同；
- 未进入纹理、PSD、ArtMesh、Cubism、Physics 或 Runtime。
"""
    (AUDIT / "V7-B1-ROOT-WIDTH-CONFLICT.zh-CN.md").write_text(
        report_md,
        encoding="utf-8",
    )

    generated = [HERE] + [
        path
        for directory in (AUDIT, MASKS, QA)
        for path in sorted(directory.glob("*"))
        if path.is_file() and path.name != "v7b1-evidence-manifest.json"
    ]
    manifest = {
        "schemaVersion": 1,
        "gate": "V7-B1 root-width conflict evidence",
        "status": report["status"],
        "checksumAlgorithm": "SHA-256",
        "files": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in generated
        ],
    }
    (AUDIT / "v7b1-evidence-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
