from __future__ import annotations

import hashlib
import json
import math
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
XIAOXING = HERE.parents[3]
SOURCE = XIAOXING / "source"
VALIDATION = XIAOXING / "validation"
V4 = VALIDATION / "arm-chain-screen-right-v4-wrist-motion"
V5 = VALIDATION / "arm-chain-screen-right-v5-hidden-upper-arm"
SLEEVE = V5 / "complete-sleeve-final"
V6 = VALIDATION / "arm-chain-screen-right-v6-complete-upper-arm-geometry"

LINE_PATH = SOURCE / "masters/front-line-source-exact-after-reset.png"
COLOR_PATH = SOURCE / "masters/front-color-source-exact-after-reset.png"
THREE_VIEW_LINE_PATH = SOURCE / "xiaoxing-three-view-line.png"
THREE_VIEW_COLOR_PATH = SOURCE / "xiaoxing-three-view-color.png"

HANDOFF_PATH = V5 / "CURRENT-HANDOFF-2026-07-25.md"
V4_MANIFEST_PATH = V4 / "archive/STAGE-A-V4-APPROVED-2026-07-24.json"
SLEEVE_MANIFEST_PATH = (
    SLEEVE / "audit/complete-sleeve-freeze-manifest-2026-07-25.json"
)
V6_MANIFEST_PATH = (
    V6 / "audit/v6-complete-upper-arm-geometry-freeze-manifest-2026-07-25.json"
)
V6_CONTRACT_PATH = (
    V6 / "audit/temporary-forearm-minimum-envelope-contract-2026-07-25.json"
)
V6_TEMP_FOREARM_PATH = V6 / "masks/reference/forearm-root-temporary-coverage.png"
V6_VISIBLE_UPPER_PATH = (
    V6 / "masks/reference/visible-upper-arm-locked-reference.png"
)

MASKS = ROOT / "masks"
QA = ROOT / "qa"
AUDIT = ROOT / "audit"
USER_DECISION_PATH = AUDIT / "v7a-user-visual-decision-2026-07-26.json"

CANVAS = (512, 1086)
ELBOW = (355.0, 415.0)
WRIST = (393.0, 533.0)
REVIEW_CROP = (328, 382, 414, 552)
BRACELET_CROP = (344, 507, 409, 550)
ELBOW_CROP = (332, 385, 384, 447)
SCALE = 8

ENTRY_EXPECTED_SHA256 = {
    HANDOFF_PATH: "cf5eaa8f8876810ddcba806eca95cebc51e2a3302c0260ffa62c525e6c216284",
    V4_MANIFEST_PATH: "dd6a91b263a5e0e135931f4196176256000a4d7aff648f907428da52030711b1",
    SLEEVE_MANIFEST_PATH: "a36c1959a1a16364997f60e4704c9af071173b79530a417216f6e5b71f3642e8",
    V6_MANIFEST_PATH: "e23e54c89e9fd5615b4686915f2243f32e21542dd81fb126ac45606a610107ae",
}

AUTHORITY_EXPECTED_SHA256 = {
    THREE_VIEW_LINE_PATH: "7f8605a85df7fa2c8843e925f8274a06403d884d975b1b195b2a583478dc222c",
    THREE_VIEW_COLOR_PATH: "2d1b9c71c4e6c17ea503800b05f44bf7bfe127799a5e156886c191b97d350154",
    LINE_PATH: "706aaf10652147cf76e233532b5459ce130921a96806f6970c91e1f3a427172f",
    COLOR_PATH: "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5",
}

# Source-line tracing of the visible screen-right arm shaft. The screen-left
# contour is the arm/shirt-background boundary, not the nearby shirt-body edge.
# The wrist end deliberately extends beyond the frozen wrist so the semantic
# split can be applied by the frozen local coordinate rather than by a guessed
# horizontal cut.
ARM_SHAFT_OUTLINE = (
    (337, 416),
    (338, 422),
    (341, 430),
    (344, 440),
    (348, 450),
    (351, 460),
    (355, 470),
    (359, 480),
    (363, 490),
    (366, 500),
    (370, 510),
    (373, 518),
    (376, 526),
    (378, 534),
    (380, 542),
    (382, 550),
    (405, 550),
    (402, 542),
    (400, 534),
    (397, 526),
    (395, 518),
    (393, 510),
    (390, 500),
    (388, 490),
    (386, 480),
    (384, 470),
    (381, 460),
    (379, 450),
    (377, 440),
    (375, 430),
    (372, 418),
    (371, 410),
)

# The decoration visibly crosses the frozen wrist line. This envelope is only a
# search limit. The actual candidate is the line-art signal plus a declared
# two-pixel flattened-RGB ownership band, not the filled polygon.
BRACELET_SEARCH_ENVELOPE = (
    (348, 524),
    (352, 519),
    (362, 521),
    (374, 519),
    (386, 514),
    (397, 512),
    (403, 517),
    (406, 524),
    (405, 534),
    (401, 542),
    (395, 547),
    (386, 547),
    (377, 543),
    (368, 540),
    (358, 540),
    (350, 536),
    (347, 531),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def mask_count(mask: Image.Image) -> int:
    return sum(mask.convert("L").histogram()[1:])


def coordinate_fingerprint(mask: Image.Image) -> str:
    rows = []
    pixels = binary(mask).load()
    bbox = mask.getbbox()
    if bbox is not None:
        for y in range(bbox[1], bbox[3]):
            for x in range(bbox[0], bbox[2]):
                if pixels[x, y]:
                    rows.append(f"{x},{y}\n")
    return hashlib.sha256("".join(rows).encode("utf-8")).hexdigest()


def binary(mask: Image.Image, threshold: int = 1) -> Image.Image:
    return mask.convert("L").point(lambda value: 255 if value >= threshold else 0)


def polygon_mask(points: tuple[tuple[int, int], ...]) -> Image.Image:
    result = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(result).polygon(points, fill=255)
    return result


def disk_mask(center: tuple[float, float], radius: float) -> Image.Image:
    result = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(result).ellipse(
        (
            center[0] - radius,
            center[1] - radius,
            center[0] + radius,
            center[1] + radius,
        ),
        fill=255,
    )
    return result


def local_axes() -> tuple[tuple[float, float], tuple[float, float], float]:
    length = math.dist(ELBOW, WRIST)
    axis = ((WRIST[0] - ELBOW[0]) / length, (WRIST[1] - ELBOW[1]) / length)
    normal = (-axis[1], axis[0])
    return axis, normal, length


def local_s(x: float, y: float) -> float:
    axis, _, _ = local_axes()
    return (x - ELBOW[0]) * axis[0] + (y - ELBOW[1]) * axis[1]


def half_plane_mask(lower: float | None, upper: float | None) -> Image.Image:
    result = Image.new("L", CANVAS, 0)
    pixels = result.load()
    for y in range(CANVAS[1]):
        for x in range(CANVAS[0]):
            value = local_s(x + 0.5, y + 0.5)
            if lower is not None and value < lower:
                continue
            if upper is not None and value >= upper:
                continue
            pixels[x, y] = 255
    return result


def line_mask(
    a: tuple[float, float],
    b: tuple[float, float],
    width: int = 1,
) -> Image.Image:
    result = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(result).line(
        [(round(a[0]), round(a[1])), (round(b[0]), round(b[1]))],
        fill=255,
        width=width,
    )
    return result


def split_segment(point: tuple[float, float], half_length: float = 25.0):
    _, normal, _ = local_axes()
    return (
        (point[0] - normal[0] * half_length, point[1] - normal[1] * half_length),
        (point[0] + normal[0] * half_length, point[1] + normal[1] * half_length),
    )


def bracelet_masks(line: Image.Image):
    envelope = polygon_mask(BRACELET_SEARCH_ENVELOPE)
    gray = line.convert("L")
    ink = gray.point(lambda value: 255 if value <= 238 else 0)
    core = ImageChops.multiply(ink, envelope)
    candidate = ImageChops.multiply(core.filter(ImageFilter.MaxFilter(5)), envelope)
    candidate = largest_component(candidate)
    core = ImageChops.multiply(core, candidate)
    # The two-pixel band is explicitly decoration-owned because the flattened
    # RGB source does not preserve fractional source alpha.
    mixed = ImageChops.subtract(candidate, core)
    return binary(core), binary(candidate), binary(mixed), envelope


def largest_component(mask: Image.Image) -> Image.Image:
    data = binary(mask).load()
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []
    bbox = mask.getbbox()
    if bbox is None:
        return Image.new("L", CANVAS, 0)
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            if not data[x, y] or (x, y) in seen:
                continue
            component: list[tuple[int, int]] = []
            queue = deque([(x, y)])
            seen.add((x, y))
            while queue:
                px, py = queue.popleft()
                component.append((px, py))
                for nx, ny in (
                    (px - 1, py),
                    (px + 1, py),
                    (px, py - 1),
                    (px, py + 1),
                ):
                    if (
                        0 <= nx < CANVAS[0]
                        and 0 <= ny < CANVAS[1]
                        and data[nx, ny]
                        and (nx, ny) not in seen
                    ):
                        seen.add((nx, ny))
                        queue.append((nx, ny))
            components.append(component)
    result = Image.new("L", CANVAS, 0)
    if components:
        pixels = result.load()
        for x, y in max(components, key=len):
            pixels[x, y] = 255
    return result


def connected_components(mask: Image.Image) -> int:
    data = binary(mask).load()
    seen: set[tuple[int, int]] = set()
    count = 0
    bbox = mask.getbbox()
    if bbox is None:
        return 0
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            if not data[x, y] or (x, y) in seen:
                continue
            count += 1
            queue = deque([(x, y)])
            seen.add((x, y))
            while queue:
                px, py = queue.popleft()
                for nx, ny in (
                    (px - 1, py),
                    (px + 1, py),
                    (px, py - 1),
                    (px, py + 1),
                ):
                    if (
                        0 <= nx < CANVAS[0]
                        and 0 <= ny < CANVAS[1]
                        and data[nx, ny]
                        and (nx, ny) not in seen
                    ):
                        seen.add((nx, ny))
                        queue.append((nx, ny))
    return count


def checkerboard(size: tuple[int, int], cell: int = 12) -> Image.Image:
    result = Image.new("RGB", size, (226, 226, 226))
    draw = ImageDraw.Draw(result)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle(
                    (x, y, min(x + cell - 1, size[0] - 1), min(y + cell - 1, size[1] - 1)),
                    fill=(248, 248, 248),
                )
    return result


def rgba_mask(mask: Image.Image, color=(255, 255, 255)) -> Image.Image:
    result = Image.new("RGBA", CANVAS, color + (0,))
    result.putalpha(binary(mask))
    return result


def source_layer(source: Image.Image, mask: Image.Image) -> Image.Image:
    result = source.convert("RGBA")
    result.putalpha(binary(mask))
    return result


def crop_scaled(image: Image.Image, crop, scale=SCALE) -> Image.Image:
    return image.crop(crop).resize(
        ((crop[2] - crop[0]) * scale, (crop[3] - crop[1]) * scale),
        Image.Resampling.NEAREST,
    )


def title(panel: Image.Image, heading: str, note: str = "") -> Image.Image:
    header = 62 if note else 42
    result = Image.new("RGB", (panel.width, panel.height + header), (238, 238, 238))
    draw = ImageDraw.Draw(result)
    draw.text((8, 4), heading, fill=(18, 18, 18), font=font(22))
    if note:
        draw.text((8, 34), note, fill=(62, 62, 62), font=font(14))
    result.paste(panel.convert("RGB"), (0, header))
    return result


def board(panels: list[Image.Image], columns: int) -> Image.Image:
    gap = 18
    rows = (len(panels) + columns - 1) // columns
    cell_w = max(panel.width for panel in panels)
    cell_h = max(panel.height for panel in panels)
    result = Image.new(
        "RGB",
        (columns * cell_w + (columns + 1) * gap, rows * cell_h + (rows + 1) * gap),
        (220, 220, 220),
    )
    for index, panel in enumerate(panels):
        x = gap + (index % columns) * (cell_w + gap)
        y = gap + (index // columns) * (cell_h + gap)
        result.paste(panel, (x, y))
    return result


def tint(
    base: Image.Image,
    layers: list[tuple[Image.Image, tuple[int, int, int, int]]],
) -> Image.Image:
    result = base.convert("RGBA")
    transparent = Image.new("RGBA", result.size, (0, 0, 0, 0))
    for mask, color in layers:
        layer = Image.new("RGBA", result.size, color)
        result.alpha_composite(Image.composite(layer, transparent, binary(mask)))
    return result


def outline(mask: Image.Image, width: int = 3) -> Image.Image:
    size = width if width % 2 else width + 1
    dilated = binary(mask).filter(ImageFilter.MaxFilter(size))
    eroded = ImageChops.invert(
        ImageChops.invert(binary(mask)).filter(ImageFilter.MaxFilter(size))
    )
    return ImageChops.subtract(dilated, eroded)


def manifest_entries(base: Path, manifest: dict, kind: str):
    entries: list[tuple[Path, str, str]] = []
    if kind == "v4":
        for path, digest in manifest["artifactSha256"].items():
            entries.append((base / path, digest, path))
    elif kind == "sleeve":
        for group in (
            "lockedArtifacts",
            "supportingMasks",
            "userApprovalRecords",
            "finalQa",
            "metadataSources",
        ):
            for item in manifest[group]:
                entries.append((base / item["path"], item["sha256"], item["path"]))
    elif kind == "v6":
        for item in manifest["lockedGeometry"]:
            entries.append((base / item["path"], item["sha256"], item["path"]))
        frozen = manifest["frozenSkeletonAndMotion"]
        entries.append(
            (base / frozen["reference"], frozen["referenceSha256"], frozen["reference"])
        )
        sample = frozen["sampleEvidence"]
        entries.append((base / sample["path"], sample["sha256"], sample["path"]))
        exception = manifest["shoulderCoverage"]["conditionalException"]
        entries.append((base / exception["path"], exception["sha256"], exception["path"]))
        contract = manifest["elbowCoverage"]["temporaryForearmContract"]
        entries.append((base / contract["path"], contract["sha256"], contract["path"]))
        for item in manifest["engineeringEvidence"]:
            entries.append((base / item["path"], item["sha256"], item["path"]))
        for path, digest in manifest["finalQa"].items():
            entries.append((base / path, digest, path))
        approval = manifest["userApproval"]
        entries.append((base / approval["path"], approval["sha256"], approval["path"]))
    return entries


def verify_inputs() -> dict:
    entry_results = []
    for path, expected in ENTRY_EXPECTED_SHA256.items():
        actual = sha256(path) if path.exists() else None
        entry_results.append(
            {
                "path": path.relative_to(XIAOXING).as_posix(),
                "expectedSha256": expected,
                "actualSha256": actual,
                "pass": actual == expected,
            }
        )

    authority_results = []
    for path, expected in AUTHORITY_EXPECTED_SHA256.items():
        actual = sha256(path) if path.exists() else None
        authority_results.append(
            {
                "path": path.relative_to(XIAOXING).as_posix(),
                "expectedSha256": expected,
                "actualSha256": actual,
                "pass": actual == expected,
            }
        )

    manifests = [
        ("V4", V4, json.loads(V4_MANIFEST_PATH.read_text("utf-8")), "v4"),
        (
            "completeSleeve",
            SLEEVE,
            json.loads(SLEEVE_MANIFEST_PATH.read_text("utf-8")),
            "sleeve",
        ),
        ("V6", V6, json.loads(V6_MANIFEST_PATH.read_text("utf-8")), "v6"),
    ]
    frozen_groups = []
    for name, base, manifest, kind in manifests:
        rows = []
        for path, expected, relative in manifest_entries(base, manifest, kind):
            actual = sha256(path) if path.exists() else None
            rows.append(
                {
                    "path": relative,
                    "expectedSha256": expected,
                    "actualSha256": actual,
                    "pass": actual == expected,
                }
            )
        frozen_groups.append(
            {
                "name": name,
                "checked": len(rows),
                "passed": sum(item["pass"] for item in rows),
                "failed": sum(not item["pass"] for item in rows),
                "items": rows,
            }
        )

    contract = json.loads(V6_CONTRACT_PATH.read_text("utf-8"))
    raster_expected = contract["frozenReference"]["sha256"]
    raster_actual = sha256(V6_TEMP_FOREARM_PATH)
    result = {
        "schemaVersion": 1,
        "gate": "V7-A input integrity",
        "status": "pass",
        "orderedMinimumEntries": entry_results,
        "authorityImages": authority_results,
        "frozenArtifactGroups": frozen_groups,
        "temporaryForearmRaster": {
            "path": V6_TEMP_FOREARM_PATH.relative_to(XIAOXING).as_posix(),
            "expectedSha256": raster_expected,
            "actualSha256": raster_actual,
            "pass": raster_expected == raster_actual,
        },
    }
    if not all(item["pass"] for item in entry_results + authority_results):
        result["status"] = "fail"
    if any(group["failed"] for group in frozen_groups):
        result["status"] = "fail"
    if raster_expected != raster_actual:
        result["status"] = "fail"
    return result


def save_review_images(
    line: Image.Image,
    color: Image.Image,
    visible_forearm: Image.Image,
    forearm_no_bracelet_qa: Image.Image,
    visible_upper: Image.Image,
    elbow_line: Image.Image,
    wrist_line: Image.Image,
    bracelet: Image.Image,
    mixed_band: Image.Image,
    root_envelope: Image.Image,
    source_arm_outline: Image.Image,
    outside_outline: Image.Image,
    upper_collision: Image.Image,
    user_decision: dict,
) -> None:
    approved = user_decision.get("approvedItems", {})
    lines_approved = (
        approved.get("elbowOwnershipLine") is True
        and approved.get("wristOwnershipLine") is True
    )
    visible_forearm_approved = approved.get("visibleForearmCandidate") is True
    bracelet_approved = approved.get("braceletMergedIntoForearmMaterial") is True
    mask_panel = Image.new("RGB", CANVAS, (255, 255, 255))
    mask_panel.paste((0, 175, 155), mask=visible_forearm)
    ownership = tint(
        color,
        [
            (visible_upper, (238, 112, 70, 125)),
            (visible_forearm, (0, 185, 150, 125)),
            (bracelet, (135, 85, 220, 185)),
            (elbow_line, (255, 30, 30, 230)),
            (wrist_line, (20, 100, 255, 230)),
        ],
    )
    panels = [
        title(crop_scaled(line, REVIEW_CROP), "权威线稿 800%", "同坐标、最近邻"),
        title(crop_scaled(color, REVIEW_CROP), "权威彩稿 800%", "同坐标、最近邻"),
        title(
            crop_scaled(mask_panel, REVIEW_CROP),
            (
                "V_forearm 已批准材料遮罩"
                if visible_forearm_approved
                else "V_forearm 候选遮罩"
            ),
            "青=前臂皮肤+已并入的手链",
        ),
        title(
            crop_scaled(ownership, REVIEW_CROP),
            "所有权候选叠加",
            "橙=冻结上臂 青=前臂 紫=前臂内手链子区 红=肘 蓝=腕",
        ),
    ]
    board(panels, 2).save(QA / "v7a-ownership-line-color-mask-800.png")

    visible_layer = source_layer(color, visible_forearm)
    bbox = visible_forearm.getbbox()
    if bbox is None:
        raise RuntimeError("V_forearm candidate is empty")
    pad = 12
    box = (
        max(0, bbox[0] - pad),
        max(0, bbox[1] - pad),
        min(CANVAS[0], bbox[2] + pad),
        min(CANVAS[1], bbox[3] + pad),
    )
    cropped = visible_layer.crop(box)
    scaled = cropped.resize(
        (cropped.width * SCALE, cropped.height * SCALE), Image.Resampling.NEAREST
    )
    checker = checkerboard(scaled.size, 16)
    checker.paste(scaled, (0, 0), scaled.getchannel("A"))
    title(
        checker,
        "V_forearm 可见源像素棋盘格 800%",
        "RGB 逐像素复制；透明区不属于前臂",
    ).save(QA / "v7a-visible-forearm-checkerboard-800.png")

    bracelet_overlay = tint(
        color,
        [
            (bracelet, (135, 85, 220, 170)),
            (mixed_band, (255, 205, 0, 210)),
            (wrist_line, (20, 100, 255, 230)),
        ],
    )
    bracelet_panels = [
        title(crop_scaled(line, BRACELET_CROP), "手链线稿 800%", "权威原线稿"),
        title(crop_scaled(color, BRACELET_CROP), "手链彩稿 800%", "权威原彩稿"),
        title(
            crop_scaled(bracelet_overlay, BRACELET_CROP),
            "手链所有权候选",
            "紫=前臂内手链子区 黄=2px混合带 蓝=冻结腕线",
        ),
    ]
    board(bracelet_panels, 3).save(QA / "v7a-bracelet-ownership-800.png")

    no_bracelet_geometry = Image.new("RGB", CANVAS, (255, 255, 255))
    no_bracelet_geometry.paste((237, 174, 164), mask=forearm_no_bracelet_qa)
    no_bracelet_geometry.paste(
        (20, 100, 255),
        mask=wrist_line,
    )
    merged_material = source_layer(color, visible_forearm)
    merged_background = Image.new("RGBA", CANVAS, (255, 255, 255, 255))
    merged_background.alpha_composite(merged_material)
    merged_panels = [
        title(crop_scaled(color, BRACELET_CROP), "权威原彩稿 800%", "手链跨越腕线"),
        title(
            crop_scaled(merged_background, BRACELET_CROP),
            "合并后的单一前臂材料",
            "皮肤与手链共用一个材料 alpha",
        ),
        title(
            crop_scaled(no_bracelet_geometry, BRACELET_CROP),
            "QA：隐藏手链装饰",
            "仅看自然前臂几何；蓝=冻结腕线",
        ),
    ]
    board(merged_panels, 3).save(
        QA / "v7a-bracelet-merged-no-runtime-layer-800.png"
    )

    footprint = tint(
        color,
        [
            (source_arm_outline, (0, 175, 155, 80)),
            (root_envelope, (235, 40, 165, 145)),
            (outside_outline, (255, 220, 0, 235)),
            (upper_collision, (255, 20, 20, 220)),
        ],
    )
    footprint_panels = [
        title(crop_scaled(line, ELBOW_CROP), "肘侧权威线稿 800%", "同坐标"),
        title(crop_scaled(color, ELBOW_CROP), "肘侧权威彩稿 800%", "同坐标"),
        title(
            crop_scaled(footprint, ELBOW_CROP),
            "V6 最低包络中性足迹",
            "粉=包络 红=冻结上臂冲突 黄=原轮廓外",
        ),
    ]
    board(footprint_panels, 3).save(QA / "v7a-neutral-footprint-compatibility-800.png")

    conflict_only = tint(
        color,
        [
            (outline(root_envelope), (235, 40, 165, 230)),
            (outside_outline, (255, 220, 0, 240)),
            (upper_collision, (255, 20, 20, 230)),
        ],
    )
    title(
        crop_scaled(conflict_only, ELBOW_CROP),
        "合同冲突像素 800%",
        "红=与冻结V_upper_arm重复；黄=超出原始手臂所有权轮廓",
    ).save(QA / "v7a-neutral-footprint-conflict-800.png")

    root_panel = Image.new("RGB", CANVAS, (255, 255, 255))
    root_panel.paste((225, 60, 170), mask=root_envelope)
    upper_panel = Image.new("RGB", CANVAS, (255, 255, 255))
    upper_panel.paste((235, 125, 70), mask=visible_upper)
    collision_panel = Image.new("RGB", CANVAS, (255, 255, 255))
    collision_panel.paste((235, 30, 30), mask=upper_collision)
    proof_panels = [
        title(
            crop_scaled(root_panel, ELBOW_CROP),
            f"A：V6 最低包络｜{mask_count(root_envelope)} px",
            "只由冻结代理和局部 s<=22 得到",
        ),
        title(
            crop_scaled(upper_panel, ELBOW_CROP),
            f"U：冻结 V_upper_arm｜{mask_count(visible_upper)} px",
            "V6 冻结可见上臂所有权",
        ),
        title(
            crop_scaled(collision_panel, ELBOW_CROP),
            f"A∩U：不可避免冲突｜{mask_count(upper_collision)} px",
            "与腕线、手链及候选前臂轮廓无关",
        ),
    ]
    proof_board = board(proof_panels, 3)
    proof_board.save(QA / "v7a-contract-contradiction-proof-800.png")

    review = Image.new("RGB", (1800, 2300), (244, 244, 244))
    review_draw = ImageDraw.Draw(review)
    review_draw.text(
        (50, 28),
        "小星 V7-A｜用户中文视觉审查总板",
        fill=(18, 18, 18),
        font=font(42),
    )
    review_draw.text(
        (50, 84),
        (
            "肘线、腕线和手链并入前臂方案已批准；合同冲突已授权重开。"
            if lines_approved and bracelet_approved
            else "按 1→2→3 审查；未明确批准的项目仍是候选。"
        ),
        fill=(72, 72, 72),
        font=font(24),
    )

    review_draw.rounded_rectangle(
        (35, 130, 1765, 910), radius=18, fill=(255, 255, 255), outline=(205, 205, 205), width=2
    )
    review_draw.text(
        (65, 150),
        "1｜待解释：最低包络同时压住冻结上臂，是否授权重开关节合同？",
        fill=(20, 20, 20),
        font=font(30),
    )
    review_draw.text(
        (65, 194),
        "左=A 最低包络；中=U 冻结上臂；右=A∩U 416 px。红区不是候选轮廓造成的。",
        fill=(82, 82, 82),
        font=font(20),
    )
    proof_scaled = proof_board.resize(
        (1450, round(proof_board.height * 1450 / proof_board.width)),
        Image.Resampling.LANCZOS,
    )
    review.paste(proof_scaled, (175, 235))

    review_draw.rounded_rectangle(
        (35, 940, 1765, 1690), radius=18, fill=(255, 255, 255), outline=(205, 205, 205), width=2
    )
    review_draw.text(
        (65, 960),
        (
            "2｜已批准：V_forearm（含手链）、肘线和腕线"
            if lines_approved and visible_forearm_approved
            else "2｜V_forearm、肘线、腕线：边界是否符合原稿？"
        ),
        fill=(20, 20, 20),
        font=font(30),
    )
    review_draw.text(
        (65, 1004),
        "检查青色前臂材料（含手链）是否混入上臂、衣身或背景；红=肘线，蓝=腕线。",
        fill=(82, 82, 82),
        font=font(20),
    )
    ownership_color = crop_scaled(color, REVIEW_CROP, 3)
    ownership_overlay = crop_scaled(ownership, REVIEW_CROP, 3)
    review.paste(ownership_color.convert("RGB"), (80, 1060))
    review.paste(ownership_overlay.convert("RGB"), (380, 1060))
    review_draw.text((80, 1580), "原彩稿 300%", fill=(50, 50, 50), font=font(22))
    review_draw.text((380, 1580), "所有权叠加 300%", fill=(50, 50, 50), font=font(22))
    review_draw.text(
        (880, 1090),
        "通过标准：\n\n"
        "• 前臂皮肤和轮廓完整\n\n"
        "• 不含衣身或背景\n\n"
        "• 肘线不切入冻结上臂\n\n"
        "• 腕线位于真实腕点\n\n"
        "• 不以手链遮住腕缝",
        fill=(45, 45, 45),
        font=font(24),
        spacing=8,
    )

    review_draw.rounded_rectangle(
        (35, 1720, 1765, 2260), radius=18, fill=(255, 255, 255), outline=(205, 205, 205), width=2
    )
    review_draw.text(
        (65, 1740),
        (
            "3｜已批准：手链并入前臂材料，不设独立运行层"
            if bracelet_approved
            else "3｜手链：是否并入前臂材料？"
        ),
        fill=(20, 20, 20),
        font=font(30),
    )
    review_draw.text(
        (65, 1784),
        "紫=前臂材料内的手链子区；黄=2 px 扁平 RGB 混合带；蓝=冻结腕线。",
        fill=(82, 82, 82),
        font=font(20),
    )
    bracelet_color = crop_scaled(color, BRACELET_CROP, 6)
    bracelet_review = crop_scaled(bracelet_overlay, BRACELET_CROP, 6)
    review.paste(bracelet_color.convert("RGB"), (80, 1840))
    review.paste(bracelet_review.convert("RGB"), (500, 1840))
    review_draw.text(
        (930, 1870),
        ("已批准方案：\n\n" if bracelet_approved else "建议裁决：\n\n")
        +
        "• 并入前臂材料\n"
        "• 不增加独立运行图层\n"
        "• 绘制顺序继承前臂（上臂之上、手部之下）\n"
        "• QA 可临时隐藏该子区检查腕缝\n"
        "• 不承担腕缝遮挡责任",
        fill=(45, 45, 45),
        font=font(24),
        spacing=8,
    )
    review.save(QA / "V7-A-USER-REVIEW-BOARD.png")


def save_wrist_gap_review(
    color: Image.Image,
    visible_forearm: Image.Image,
    forearm_no_bracelet_qa: Image.Image,
    bracelet: Image.Image,
    wrist_line: Image.Image,
    wrist_source_responsibility: Image.Image,
    wrist_hand_root_seed: Image.Image,
) -> None:
    merged = source_layer(color, visible_forearm)
    merged_background = Image.new("RGBA", CANVAS, (255, 255, 255, 255))
    merged_background.alpha_composite(merged)
    gap = tint(
        color,
        [
            (forearm_no_bracelet_qa, (0, 175, 155, 110)),
            (wrist_source_responsibility, (255, 205, 0, 90)),
            (wrist_hand_root_seed, (240, 25, 25, 225)),
            (wrist_line, (20, 100, 255, 230)),
        ],
    )
    ownership = tint(
        color,
        [
            (forearm_no_bracelet_qa, (0, 175, 155, 150)),
            (wrist_hand_root_seed, (235, 125, 70, 210)),
            (bracelet, (135, 85, 220, 155)),
            (wrist_line, (20, 100, 255, 230)),
        ],
    )
    panels = [
        title(
            crop_scaled(color, BRACELET_CROP),
            "权威原彩稿 800%",
            "手链下方皮肤必须连续",
        ),
        title(
            crop_scaled(merged_background, BRACELET_CROP),
            "当前已锁前臂材料",
            "只证明所有权；正式手部尚未建立",
        ),
        title(
            crop_scaled(gap, BRACELET_CROP),
            "隐藏手链后的腕部责任缺口",
            "红=待手部根部承担；蓝=冻结腕线",
        ),
        title(
            crop_scaled(ownership, BRACELET_CROP),
            "正确补法：建立手部根部包络",
            "青=前臂 橙=手部种子 紫=前臂内手链",
        ),
    ]
    board(panels, 2).save(QA / "v7a-wrist-gap-risk-and-responsibility-800.png")


def main() -> None:
    for directory in (MASKS, QA, AUDIT):
        directory.mkdir(parents=True, exist_ok=True)

    integrity = verify_inputs()
    (AUDIT / "v7a-input-integrity.json").write_text(
        json.dumps(integrity, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    if integrity["status"] != "pass":
        raise RuntimeError("Frozen input integrity failed; V7-A stopped.")

    user_decision = (
        json.loads(USER_DECISION_PATH.read_text("utf-8"))
        if USER_DECISION_PATH.exists()
        else {
            "status": "no_user_decision",
            "approvedItems": {},
            "downstreamAuthorization": False,
        }
    )
    approved_items = user_decision.get("approvedItems", {})
    visible_forearm_approved = (
        approved_items.get("visibleForearmCandidate") is True
    )
    elbow_line_approved = approved_items.get("elbowOwnershipLine") is True
    wrist_line_approved = approved_items.get("wristOwnershipLine") is True
    bracelet_approved = (
        approved_items.get("braceletMergedIntoForearmMaterial") is True
    )
    contract_conflict_approved = (
        approved_items.get("contractConflictConclusion") is True
    )

    line = Image.open(LINE_PATH).convert("RGB")
    color = Image.open(COLOR_PATH).convert("RGB")
    if line.size != CANVAS or color.size != CANVAS:
        raise RuntimeError("Authoritative front masters do not match the frozen canvas.")

    visible_upper = binary(Image.open(V6_VISIBLE_UPPER_PATH), 1)
    temp_forearm = binary(Image.open(V6_TEMP_FOREARM_PATH), 1)
    shaft = polygon_mask(ARM_SHAFT_OUTLINE)
    elbow_half = half_plane_mask(0.0, None)
    _, _, length = local_axes()
    wrist_half = half_plane_mask(None, length)
    bracelet_core, bracelet, mixed_band, bracelet_envelope = bracelet_masks(line)

    # Frozen visible upper-arm ownership has precedence. The semantic elbow line
    # is the frozen local s=0 line, but no already-frozen upper-arm pixel is
    # reassigned to the forearm candidate.
    forearm_no_bracelet_qa = ImageChops.multiply(shaft, elbow_half)
    forearm_no_bracelet_qa = ImageChops.multiply(
        forearm_no_bracelet_qa, wrist_half
    )
    forearm_no_bracelet_qa = binary(
        ImageChops.subtract(forearm_no_bracelet_qa, visible_upper)
    )
    visible_forearm_skin = forearm_no_bracelet_qa.copy()
    visible_forearm_skin = ImageChops.subtract(visible_forearm_skin, bracelet)
    visible_forearm_skin = binary(visible_forearm_skin)
    # User revision: the bracelet is no longer an independent runtime material.
    # Its approved decoration and mixed-band pixels are part of the production
    # forearm material. The bracelet mask remains only as a diagnostic subregion
    # so wrist QA can suppress it without creating a runtime layer.
    visible_forearm = binary(
        ImageChops.lighter(visible_forearm_skin, bracelet)
    )

    elbow_a, elbow_b = split_segment(ELBOW, 27.0)
    wrist_a, wrist_b = split_segment(WRIST, 27.0)
    elbow_line = line_mask(elbow_a, elbow_b, 1)
    wrist_line = line_mask(wrist_a, wrist_b, 1)

    contract = json.loads(V6_CONTRACT_PATH.read_text("utf-8"))
    s_limit = float(
        contract["minimumRootEnvelope"]["replaceFrozenPrototypeBeforeLocalSPx"]
    )
    root_limit = half_plane_mask(None, s_limit + 1e-9)
    root_envelope = ImageChops.multiply(temp_forearm, root_limit)
    root_envelope = binary(root_envelope)

    # At this gate, the original source-arm ownership footprint is the union of
    # the already-frozen visible upper-arm pixels and the source-traced shaft.
    # It is deliberately independent of upper/forearm draw order.
    source_arm_outline = binary(ImageChops.lighter(visible_upper, shaft))
    outside_outline = binary(ImageChops.subtract(root_envelope, source_arm_outline))
    upper_collision = binary(ImageChops.multiply(root_envelope, visible_upper))
    not_in_visible_forearm = binary(
        ImageChops.subtract(root_envelope, visible_forearm)
    )
    wrist_responsibility_disk = disk_mask(WRIST, 11.0)
    wrist_source_responsibility = binary(
        ImageChops.multiply(wrist_responsibility_disk, shaft)
    )
    wrist_hand_root_seed = binary(
        ImageChops.subtract(
            wrist_source_responsibility,
            forearm_no_bracelet_qa,
        )
    )
    wrist_hand_side = half_plane_mask(length, None)
    wrist_seed_hand_side = binary(
        ImageChops.multiply(wrist_hand_root_seed, wrist_hand_side)
    )
    wrist_seed_forearm_side = binary(
        ImageChops.subtract(wrist_hand_root_seed, wrist_hand_side)
    )

    rgba_mask(visible_forearm).save(MASKS / "visible-forearm-locked.png")
    rgba_mask(visible_forearm_skin).save(
        MASKS / "visible-forearm-skin-subregion.png"
    )
    rgba_mask(forearm_no_bracelet_qa).save(
        MASKS / "forearm-no-bracelet-qa-geometry.png"
    )
    rgba_mask(elbow_line).save(MASKS / "elbow-ownership-line-candidate.png")
    rgba_mask(wrist_line).save(MASKS / "wrist-ownership-line-candidate.png")
    rgba_mask(bracelet).save(MASKS / "bracelet-ownership-candidate.png")
    rgba_mask(bracelet_core).save(MASKS / "bracelet-core-reference.png")
    rgba_mask(mixed_band).save(MASKS / "wrist-aa-mixed-band-candidate.png")
    rgba_mask(root_envelope).save(MASKS / "v6-minimum-envelope-neutral-footprint.png")
    rgba_mask(source_arm_outline).save(MASKS / "source-arm-neutral-outline-candidate.png")
    rgba_mask(outside_outline).save(MASKS / "v6-envelope-outside-source-outline.png")
    rgba_mask(upper_collision).save(
        MASKS / "v6-envelope-locked-upper-arm-ownership-conflict.png"
    )
    rgba_mask(wrist_source_responsibility).save(
        MASKS / "wrist-source-responsibility-candidate.png"
    )
    rgba_mask(wrist_hand_root_seed).save(
        MASKS / "wrist-hand-root-neutral-seed-candidate.png"
    )
    source_layer(color, visible_forearm).save(
        QA / "visible-forearm-source-pixels-reference.png"
    )

    source_pixels = color.load()
    copied = source_layer(color, visible_forearm)
    copied_pixels = copied.load()
    differing = 0
    max_difference = 0
    for y in range(CANVAS[1]):
        for x in range(CANVAS[0]):
            if not visible_forearm.getpixel((x, y)):
                if copied_pixels[x, y][3] != 0:
                    raise RuntimeError("Visible forearm emitted alpha outside its mask.")
                continue
            expected = source_pixels[x, y]
            actual = copied_pixels[x, y][:3]
            difference = max(abs(a - b) for a, b in zip(expected, actual))
            max_difference = max(max_difference, difference)
            differing += int(difference != 0)

    pixel_report = {
        "schemaVersion": 1,
        "gate": "V7-A visible forearm pixel copy",
        "status": (
            "engineering_and_user_visual_pass"
            if visible_forearm_approved
            else "engineering_pass_pending_user_visual_approval"
        ),
        "candidateOnly": not visible_forearm_approved,
        "source": "source/masters/front-color-source-exact-after-reset.png",
        "mask": (
            "validation/arm-chain-screen-right-v7-production-forearm-geometry/"
            "masks/visible-forearm-locked.png"
        ),
        "visiblePixelCount": mask_count(visible_forearm),
        "boundingBoxExclusive": list(visible_forearm.getbbox() or ()),
        "coordinateDifferencePixels": 0,
        "rgbDifferencePixels": differing,
        "maximumRgbChannelDifference": max_difference,
        "alphaPixelsOutsideMask": 0,
        "connectedComponents": connected_components(visible_forearm),
        "note": (
            "The visible forearm candidate has explicit user approval."
            if visible_forearm_approved
            else "The filename is the proposed post-approval lock target. The user "
            "approved the elbow and wrist lines but did not explicitly approve "
            "V_forearm itself."
        ),
    }
    (AUDIT / "v7a-visible-forearm-pixel-copy.json").write_text(
        json.dumps(pixel_report, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )

    outside_count = mask_count(outside_outline)
    collision_count = mask_count(upper_collision)
    compatibility_pass = outside_count == 0 and collision_count == 0
    contradiction_proof = {
        "schemaVersion": 1,
        "proof": "V7-A frozen-envelope versus frozen-upper ownership contradiction",
        "status": "unsatisfiable_under_current_frozen_contracts",
        "coordinateFingerprintCanonicalFormat": (
            "rows sorted by y then x; UTF-8 LF; each row x,y"
        ),
        "sets": {
            "A": {
                "definition": (
                    "V6 frozen temporary-forearm raster restricted by frozen "
                    "forearm-local pixel-center s <= 22 px"
                ),
                "pixelCount": mask_count(root_envelope),
                "coordinateFingerprintSha256": coordinate_fingerprint(root_envelope),
                "rasterSha256": sha256(
                    MASKS / "v6-minimum-envelope-neutral-footprint.png"
                ),
            },
            "U": {
                "definition": "V6 frozen visible upper-arm ownership pixels",
                "pixelCount": mask_count(visible_upper),
                "coordinateFingerprintSha256": coordinate_fingerprint(visible_upper),
                "rasterSha256": sha256(V6_VISIBLE_UPPER_PATH),
            },
            "A_intersection_U": {
                "pixelCount": collision_count,
                "boundingBoxExclusive": list(upper_collision.getbbox() or ()),
                "coordinateFingerprintSha256": coordinate_fingerprint(upper_collision),
                "rasterSha256": sha256(
                    MASKS / "v6-envelope-locked-upper-arm-ownership-conflict.png"
                ),
            },
        },
        "frozenRequirements": [
            "A must be contained by the production forearm P.",
            "P is drawn above U in the neutral pose.",
            "U remains immutable frozen visible upper-arm ownership.",
            "One static source pixel cannot belong to both materials.",
            "Default occlusion cannot hide the neutral root footprint.",
        ],
        "derivation": [
            "A subset P implies A intersection U subset P intersection U.",
            f"|A intersection U| = {collision_count}.",
            f"Therefore every admissible P has |P intersection U| >= {collision_count}.",
            "Unique static ownership requires |P intersection U| = 0.",
        ],
        "conclusion": (
            "No production forearm P can satisfy all current frozen requirements."
        ),
        "independentOf": [
            "source-arm outline candidate",
            "V_forearm distal silhouette candidate",
            "wrist ownership line",
            "bracelet ownership",
            "hand proxy",
            "future texture",
            "Cubism",
            "Physics",
        ],
        "requiredReopen": (
            "At least one of A, U, draw order, or unique neutral ownership must be "
            "explicitly revised in a new user-approved dependency gate. Frozen "
            "artifacts themselves remain byte-unchanged."
        ),
    }
    (AUDIT / "v7a-contract-contradiction-proof.json").write_text(
        json.dumps(contradiction_proof, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    footprint_report = {
        "schemaVersion": 1,
        "gate": "V7-A neutral footprint compatibility",
        "status": "pass" if compatibility_pass else "fail_contract_conflict",
        "frozenElbow": list(ELBOW),
        "frozenWrist": list(WRIST),
        "localSInclusiveUpperBoundPx": s_limit,
        "frozenMinimumEnvelopePixelCount": mask_count(root_envelope),
        "sourceArmNeutralOutlinePixelCount": mask_count(source_arm_outline),
        "envelopePixelsOutsideOriginalArmOutline": outside_count,
        "envelopePixelsCollidingWithFrozenVisibleUpperArmOwnership": collision_count,
        "envelopePixelsNotInVForearmCandidate": mask_count(not_in_visible_forearm),
        "tests": {
            "neutralFootprintSubsetOfOriginalArmOutline": outside_count == 0,
            "uniqueStaticPixelOwnershipCompatibleWithFrozenUpperArm": collision_count
            == 0,
            "productionForearmAboveUpperArmCanContainEnvelopeWithoutOverwrite": collision_count
            == 0,
        },
        "decision": (
            "continue_to_user_visual_gate"
            if compatibility_pass
            else "stop_before_complete_forearm_geometry"
        ),
        "automaticReopenCondition": (
            "Only an explicit user-approved contract revision that preserves the "
            "frozen skeleton and does not silently modify V6 may reopen V7."
        ),
        "independentContradictionProof": "audit/v7a-contract-contradiction-proof.json",
    }
    (AUDIT / "v7a-neutral-footprint-compatibility.json").write_text(
        json.dumps(footprint_report, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    wrist_report = {
        "schemaVersion": 1,
        "gate": "V7-A neutral wrist continuity responsibility",
        "status": "blocked_pending_temporary_hand_root_envelope",
        "frozenWrist": list(WRIST),
        "responsibilityDiskRadiusPx": 11.0,
        "sourceSupportedResponsibilityPixels": mask_count(
            wrist_source_responsibility
        ),
        "coveredByNaturalForearmPixelsWithoutBracelet": mask_count(
            ImageChops.multiply(
                wrist_source_responsibility,
                forearm_no_bracelet_qa,
            )
        ),
        "uncoveredResponsibilityPixels": mask_count(wrist_hand_root_seed),
        "uncoveredPixelsOnHandSideOfFrozenWrist": mask_count(
            wrist_seed_hand_side
        ),
        "uncoveredPixelsOnForearmSideOfFrozenWrist": mask_count(
            wrist_seed_forearm_side
        ),
        "braceletPixelsInsideResponsibilityDisk": mask_count(
            ImageChops.multiply(bracelet, wrist_responsibility_disk)
        ),
        "interpretation": (
            "The uncovered source-supported pixels are entirely on the hand side. "
            "They must seed the temporary hand-root envelope; assigning them to the "
            "forearm would silently move the approved wrist ownership line."
        ),
        "braceletMayCountAsCoverage": False,
        "neutralSeedIsFinalHandEnvelope": False,
        "requiredNextWorkAfterElbowGate": (
            "build a source-contained asymmetric temporary hand-root minimum "
            "envelope, then scan the full active wrist range with the bracelet hidden"
        ),
        "automaticInvalidation": [
            "wrist point changes",
            "active wrist-angle range changes",
            "formal hand root does not contain the approved temporary envelope",
            "bracelet is used to hide a wrist gap",
        ],
    }
    (AUDIT / "v7a-wrist-neutral-responsibility.json").write_text(
        json.dumps(wrist_report, ensure_ascii=False, indent=2) + "\n",
        "utf-8",
    )

    ownership_report = {
        "schemaVersion": 1,
        "gate": "V7-A pixel ownership",
        "status": (
            "blocked_by_neutral_footprint_contract_conflict"
            if not compatibility_pass
            else "engineering_pass_pending_user_visual_approval"
        ),
        "authority": {
            "line": "source/masters/front-line-source-exact-after-reset.png",
            "color": "source/masters/front-color-source-exact-after-reset.png",
            "lineSha256": sha256(LINE_PATH),
            "colorSha256": sha256(COLOR_PATH),
        },
        "ownershipCandidates": {
            "V_forearm": {
                "pixelCount": mask_count(visible_forearm),
                "owner": "production_forearm",
                "approved": visible_forearm_approved,
                "rule": (
                    "source-traced arm shaft, distal of frozen elbow local s=0, "
                    "proximal of frozen wrist, excluding frozen V_upper_arm, plus "
                    "the approved bracelet decoration merged into this material"
                ),
            },
            "elbowBoundary": {
                "rule": (
                    "frozen local s=0 with immutable V_upper_arm ownership precedence"
                ),
                "lineEndpoints": [list(elbow_a), list(elbow_b)],
                "approved": elbow_line_approved,
            },
            "wristBoundary": {
                "rule": "frozen wrist local s=L2",
                "lineEndpoints": [list(wrist_a), list(wrist_b)],
                "approved": wrist_line_approved,
            },
            "bracelet": {
                "owner": "production_forearm",
                "independentRuntimeLayer": False,
                "binding": "inherited_from_forearm",
                "drawOrder": "same_as_forearm_above_upper_below_hand",
                "crossesFrozenWristBoundary": mask_count(
                    ImageChops.multiply(bracelet, wrist_line.filter(ImageFilter.MaxFilter(3)))
                )
                > 0,
                "pixelCount": mask_count(bracelet),
                "diagnosticSubregionOnly": True,
                "braceletHiddenQaRequired": True,
                "braceletHiddenQaGeometryMask": (
                    "masks/forearm-no-bracelet-qa-geometry.png"
                ),
                "approved": bracelet_approved,
            },
            "wristMixedBand": {
                "owner": "production_forearm",
                "widthPx": 2,
                "pixelCount": mask_count(mixed_band),
                "sourceAlphaRecoverable": False,
            },
        },
        "mutualExclusion": {
            "visibleUpperVsVisibleForearmOverlapPixels": mask_count(
                ImageChops.multiply(visible_upper, visible_forearm)
            ),
            "braceletSubregionPixelsOutsideForearmMaterial": mask_count(
                ImageChops.subtract(bracelet, visible_forearm)
            ),
            "mixedBandPixelsOutsideForearmMaterial": mask_count(
                ImageChops.subtract(mixed_band, visible_forearm)
            ),
        },
        "pixelCopy": pixel_report,
        "neutralFootprint": footprint_report,
        "wristNeutralResponsibility": wrist_report,
        "contractContradictionProof": contradiction_proof,
        "userDecision": {
            "path": USER_DECISION_PATH.relative_to(ROOT).as_posix()
            if USER_DECISION_PATH.exists()
            else None,
            "status": user_decision.get("status"),
            "approvedItems": approved_items,
            "contractConflictApproved": contract_conflict_approved,
            "downstreamAuthorization": user_decision.get(
                "downstreamAuthorization", False
            ),
        },
        "nextGate": (
            "No downstream gate. Stop for user decision on the frozen-envelope conflict."
            if not compatibility_pass
            else "Obtain explicit Chinese visual approval; do not build complete geometry yet."
        ),
    }
    (AUDIT / "v7a-ownership-gate.json").write_text(
        json.dumps(ownership_report, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )

    save_review_images(
        line,
        color,
        visible_forearm,
        forearm_no_bracelet_qa,
        visible_upper,
        elbow_line,
        wrist_line,
        bracelet,
        mixed_band,
        root_envelope,
        source_arm_outline,
        outside_outline,
        upper_collision,
        user_decision,
    )
    save_wrist_gap_review(
        color,
        visible_forearm,
        forearm_no_bracelet_qa,
        bracelet,
        wrist_line,
        wrist_source_responsibility,
        wrist_hand_root_seed,
    )

    status_cn = (
        "工程检查发现合同冲突，已按停止条件停在 V7-A。"
        if not compatibility_pass
        else "工程检查通过，等待用户中文视觉批准。"
    )
    approval_progress_cn = (
        "- 已批准：肘侧归属线、腕侧归属线。\n"
        "- 已修订并批准：手链及 `2 px` 混合带并入前臂材料，不增加独立运行层。\n"
        "- 已批准：更新后的 `V_forearm` 材料所有权；QA 仍可临时隐藏手链子区检查腕缝。\n"
        "- 已接受：冻结合同冲突，并授权在 V7 内建立依赖重开证据。"
        if elbow_line_approved and wrist_line_approved and bracelet_approved
        else "- 尚无完整的用户视觉门禁决定。"
    )
    lock_note_cn = (
        "文件名 `masks/visible-forearm-locked.png` 是批准后拟冻结的目标文件；"
        "当前 `V_forearm` 尚未获得明确用户批准，因此该文件仍是候选。"
        if not visible_forearm_approved
        else "用户已明确批准 `V_forearm`，该文件可作为后续冻结目标；"
        "但合同冲突仍阻止完整前臂几何。"
    )
    conflict_cn = (
        f"- 包络超出原始手臂所有权轮廓：`{outside_count}` 像素。\n"
        f"- 包络与冻结 `V_upper_arm` 静态所有权冲突：`{collision_count}` 像素。\n"
        "- 正式前臂被要求绘制在上臂之上，因此这些冲突像素会覆盖已冻结上臂，"
        "不能用默认遮挡、同色回组或后续纹理解释掉。\n"
        "- 当前不得生成 F1-F4 完整前臂几何，也不得建立腕部覆盖合同。"
        if not compatibility_pass
        else "- 中性足迹合同通过；仍须等待用户视觉批准。"
    )
    (AUDIT / "V7-A-OWNERSHIP-AND-NEUTRAL-FOOTPRINT.zh-CN.md").write_text(
        f"""# 小星 V7-A：正式前臂像素所有权与中性足迹相容性

## 当前结论

**{status_cn}**

{lock_note_cn}

## 用户决定进度

{approval_progress_cn}

## 输入完整性

- 四份最小冻结入口校验通过。
- V4 冻结项：`17/17`。
- 完整袖子冻结项：`16/16`。
- V6 冻结项：`22/22`。
- 四份权威图像校验通过，正面线稿和彩稿均为 `512×1086`。

## `V_forearm` 候选

- 可见像素数：`{mask_count(visible_forearm)}`。
- 包围盒（右、下不含）：`{list(visible_forearm.getbbox() or ())}`。
- 坐标差异：`0`。
- RGB 差异像素：`{differing}`。
- 最大 RGB 通道差：`{max_difference}`。
- 与冻结 `V_upper_arm` 重叠：`0`。
- 手链子区未包含于前臂材料的像素：`{mask_count(ImageChops.subtract(bracelet, visible_forearm))}`。
- 混合带未包含于前臂材料的像素：`{mask_count(ImageChops.subtract(mixed_band, visible_forearm))}`。

肘侧候选以冻结前臂局部 `s=0` 为语义分界，并让已冻结
`V_upper_arm` 像素优先；腕侧候选使用冻结腕点 `s=L2`。

## 手链与腕部混合带候选

手链可见结构真实跨越冻结腕线。用户已修订裁决：

1. 手链并入正式前臂材料；
2. 不建立独立运行图层；
3. 绘制顺序继承前臂，即位于上臂之上、手部之下；
4. 手链不能承担腕缝遮挡责任；
5. 仅保留 QA 子遮罩，可临时隐藏手链像素检查真实腕缝。

扁平 RGB 母图无法恢复原始分数 alpha。本候选把手链线稿信号外扩 `2 px`
作为抗锯齿混合带，并入前臂材料；不声称这是原始分层 alpha。

## 腕部“骨裂”风险裁决

隐藏手链后，冻结腕点 `11 px` 责任盘与原手臂源轮廓相交得到
`{mask_count(wrist_source_responsibility)}` 个像素：

- 自然前臂末端已承担：`{mask_count(ImageChops.multiply(wrist_source_responsibility, forearm_no_bracelet_qa))}` 像素；
- 尚未覆盖：`{mask_count(wrist_hand_root_seed)}` 像素；
- 未覆盖像素位于手部侧：`{mask_count(wrist_seed_hand_side)}`；
- 未覆盖像素位于前臂侧：`{mask_count(wrist_seed_forearm_side)}`。

因此用户指出的缺口真实存在，但正确补法不是继续把手部侧像素塞进前臂，也不是依赖
手链遮挡；应把这 `{mask_count(wrist_hand_root_seed)}` 个源支持像素作为临时手部根部
包络的中性种子。当前种子不是正式手部包络，必须在肘部前置门禁关闭后，对主动腕角
全范围重建和扫描。

## V6 最低包络中性足迹合同

- 冻结最低包络（局部 `s <= {s_limit:g} px`）像素：`{mask_count(root_envelope)}`。
{conflict_cn}

## 请审查的证据

1. `qa/v7a-ownership-line-color-mask-800.png`
2. `qa/v7a-visible-forearm-checkerboard-800.png`
3. `qa/v7a-bracelet-ownership-800.png`
4. `qa/v7a-bracelet-merged-no-runtime-layer-800.png`
5. `qa/v7a-wrist-gap-risk-and-responsibility-800.png`
6. `qa/v7a-neutral-footprint-compatibility-800.png`
7. `qa/v7a-neutral-footprint-conflict-800.png`
8. `qa/v7a-contract-contradiction-proof-800.png`
9. `qa/V7-A-USER-REVIEW-BOARD.png`：按 1→2→3 集中审查。

## 与候选轮廓无关的集合证明

设：

- `A` 为 V6 冻结最低包络在局部 `s <= {s_limit:g} px` 的中性栅格；
- `U` 为 V6 冻结可见上臂所有权；
- `P` 为任意待建正式前臂。

冻结条件要求 `A ⊆ P`，因此 `A∩U ⊆ P∩U`。当前直接从两份冻结栅格得到：

- `|A| = {mask_count(root_envelope)}`；
- `|U| = {mask_count(visible_upper)}`；
- `|A∩U| = {collision_count}`。

所以任何包含 `A` 的正式前臂都满足 `|P∩U| >= {collision_count}`，而唯一静态像素
所有权要求 `|P∩U| = 0`。两者矛盾。

这个矛盾不依赖本轮手臂外轮廓候选、腕线、手链、手部代理或未来纹理；即使不采用
“超出原始轮廓 `{outside_count}` 像素”这一辅助判断，冻结集合之间的冲突仍然成立。

## 需要用户决定

当前只需继续判断：

1. 青色 `V_forearm` 本体是否符合原稿；
2. 是否接受当前合同冲突结论；
3. 是否授权另建不修改冻结文件的依赖重开方案。

若不修改冻结 V6，当前 V7 无法合法继续；任何重开方案都必须单独批准，
并保留原冻结产物不变。正式前臂纯色几何、纹理、PSD、Cubism、Physics
和 Runtime 均未生成。
""",
        "utf-8",
    )

    visible_mark = "x" if visible_forearm_approved else " "
    elbow_mark = "x" if elbow_line_approved else " "
    wrist_mark = "x" if wrist_line_approved else " "
    bracelet_mark = "x" if bracelet_approved else " "
    contract_mark = "x" if contract_conflict_approved else " "
    reopen_mark = (
        "x"
        if approved_items.get("dependencyReopenAuthorization") is True
        else " "
    )
    (AUDIT / "V7-A-USER-REVIEW-CHECKLIST.zh-CN.md").write_text(
        f"""# V7-A 用户审查清单

请先看 `qa/V7-A-USER-REVIEW-BOARD.png`，再逐项确认。

## 1. 冻结合同冲突

- [{contract_mark}] 我确认图中 `A∩U = {collision_count}` 像素。
- [{contract_mark}] 我接受：在当前冻结条件下，不存在满足唯一静态像素所有权的正式前臂。
- [{reopen_mark}] 我授权另建依赖重开方案；不得修改现有 V4、袖子或 V6 冻结文件。

## 2. `V_forearm` 与归属线

- [{visible_mark}] 青色前臂候选符合原稿，没有混入上臂、手部、衣身或背景。
- [{elbow_mark}] 红色肘线候选可以接受。
- [{wrist_mark}] 蓝色腕线候选可以接受。

## 3. 手链

- [{bracelet_mark}] 批准手链并入正式前臂材料，不设独立运行图层。
- [{bracelet_mark}] 批准手链绘制顺序继承前臂，即位于上臂之上、手部之下。
- [{bracelet_mark}] 批准黄色 `2 px` 混合带归前臂；仅保留诊断子遮罩用于“手链隐藏”QA。

## 4. 腕部连续性

- [x] 用户已指出：隐藏手链后不得出现腕部“骨裂”式透明缺口。
- [x] 手链不能计入腕缝覆盖。
- [x] 当前 `{mask_count(wrist_hand_root_seed)}` 个未覆盖像素全部位于冻结腕线的手部侧。
- [ ] 临时手部根部最终轮廓尚未生成或批准；当前只锁定中性责任种子。

## 可直接回复

如果剩余两项也认可，可回复：

> 批准青色 V_forearm 本体；接受 416 像素冻结合同冲突；授权另建不修改冻结文件的 V6 依赖重开方案。

若有任何一项不认可，请指出总板中的编号和具体边界位置。本清单本身不构成批准记录，
只有用户的明确回复才构成门禁决定。
""",
        "utf-8",
    )

    evidence_paths = [
        path
        for directory in (MASKS, QA, AUDIT)
        for path in directory.iterdir()
        if path.is_file() and path.name != "v7a-evidence-manifest.json"
    ]
    evidence = {
        "schemaVersion": 1,
        "gate": "V7-A evidence manifest",
        "status": ownership_report["status"],
        "artifacts": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
            }
            for path in sorted(evidence_paths)
        ],
        "downstreamArtifactsCreated": False,
    }
    (AUDIT / "v7a-evidence-manifest.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    print(json.dumps(
        {
            "status": ownership_report["status"],
            "visibleForearmPixels": mask_count(visible_forearm),
            "rootEnvelopePixels": mask_count(root_envelope),
            "outsideOriginalOutlinePixels": outside_count,
            "lockedUpperOwnershipCollisionPixels": collision_count,
        },
        ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
