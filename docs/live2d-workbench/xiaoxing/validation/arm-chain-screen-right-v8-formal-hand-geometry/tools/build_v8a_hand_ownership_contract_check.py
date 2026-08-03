from __future__ import annotations

import hashlib
import json
import math
import os
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
VALIDATION = ROOT.parent
XIAOXING = VALIDATION.parent
V7 = VALIDATION / "arm-chain-screen-right-v7-production-forearm-geometry"
V7C1 = V7 / "v7c1-elbow-seam-fairing"

AUDIT = ROOT / "audit"
MASKS = ROOT / "masks"
QA = ROOT / "qa"
for directory in (AUDIT, MASKS, QA):
    directory.mkdir(parents=True, exist_ok=True)

LINE_SOURCE = XIAOXING / "source/masters/front-line-source-exact-after-reset.png"
COLOR_SOURCE = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
FREEZE_MANIFEST = (
    V7C1
    / "audit/v7-production-forearm-geometry-freeze-manifest-2026-07-26.json"
)
ENVELOPE_CONTRACT = (
    V7C1 / "audit/v7c1-temporary-hand-root-envelope-contract.json"
)
ENVELOPE = V7C1 / "masks/temporary-hand-root-envelope.png"
FORMAL_FOREARM = V7C1 / "masks/production-forearm-geometry-faired.png"
VISIBLE_FOREARM = V7 / "masks/visible-forearm-locked.png"
BRACELET = V7 / "masks/bracelet-ownership-candidate.png"
SOURCE_ROOT_SUPPORT = V7 / "masks/source-arm-neutral-outline-candidate.png"
V7A_APPROVAL = V7 / "audit/v7a-user-visual-decision-2026-07-26.json"

EXPECTED_INPUTS = {
    "source/masters/front-line-source-exact-after-reset.png": (
        LINE_SOURCE,
        "706aaf10652147cf76e233532b5459ce130921a96806f6970c91e1f3a427172f",
        460239,
    ),
    "source/masters/front-color-source-exact-after-reset.png": (
        COLOR_SOURCE,
        "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5",
        581346,
    ),
    "validation/v7/freeze-manifest.json": (
        FREEZE_MANIFEST,
        "65469d0eda4d5c27b79d3d23fbd92604a51ad82c5ca08ce6a875ab7d1bffea33",
        10743,
    ),
    "validation/v7/temporary-hand-root-envelope-contract.json": (
        ENVELOPE_CONTRACT,
        "da4f277a510de5e6ca1a2a7ba9f75645a8963b6e8d371ea4f61e75fd38e67028",
        1359,
    ),
    "validation/v7/temporary-hand-root-envelope.png": (
        ENVELOPE,
        "29ed3326d99497c7fb815476f63d0825564c6b9cb174fdd151c275542c8ce421",
        4637,
    ),
    "validation/v7/production-forearm-geometry-faired.png": (
        FORMAL_FOREARM,
        "94e0c68344efc9c718f42de445cad5e06a750a6c163b864362a30198cc5befe1",
        4908,
    ),
    "validation/v7/visible-forearm-locked.png": (
        VISIBLE_FOREARM,
        "87933c37e8765be3d468c366277a7a0e12c1cbd2ccc28b4172af852c45a1e7ab",
        4920,
    ),
    "validation/v7/bracelet-ownership-candidate.png": (
        BRACELET,
        "411a3974a1a1ff6c1d7fadd6135e34a01efb41dca9bdc6a4d44753b85aa6c719",
        4723,
    ),
    "validation/v7/source-arm-neutral-outline-candidate.png": (
        SOURCE_ROOT_SUPPORT,
        "6d8eced8522cbb6e78dc69739db9e1110ee6ec6c24e89df6b5e779185d2ee838",
        4920,
    ),
    "validation/v7/v7a-user-visual-decision-2026-07-26.json": (
        V7A_APPROVAL,
        "c383ed2cfbe352f61c78014784ed411cf7a20c338612e111a000f76450662ac4",
        2559,
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def binary(image: Image.Image, threshold: int = 16) -> Image.Image:
    if image.mode == "L":
        channel = image
    else:
        channel = image.convert("RGBA").getchannel("A")
    return channel.point(lambda value: 255 if value >= threshold else 0)


def load_mask(path: Path) -> Image.Image:
    return binary(Image.open(path))


def count(mask: Image.Image) -> int:
    return sum(binary(mask, 1).histogram()[1:])


def intersection(*masks: Image.Image) -> Image.Image:
    result = binary(masks[0], 1)
    for mask in masks[1:]:
        result = ImageChops.multiply(result, binary(mask, 1))
    return binary(result, 1)


def subtract(first: Image.Image, second: Image.Image) -> Image.Image:
    return binary(ImageChops.subtract(binary(first, 1), binary(second, 1)), 1)


def rgba_mask(mask: Image.Image, rgb=(255, 255, 255)) -> Image.Image:
    result = Image.new("RGBA", mask.size, (*rgb, 0))
    result.putalpha(binary(mask, 1))
    return result


def connected_components(mask: Image.Image) -> int:
    pixels = binary(mask, 1).load()
    width, height = mask.size
    seen: set[tuple[int, int]] = set()
    components = 0
    for y in range(height):
        for x in range(width):
            if not pixels[x, y] or (x, y) in seen:
                continue
            components += 1
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
                        0 <= nx < width
                        and 0 <= ny < height
                        and pixels[nx, ny]
                        and (nx, ny) not in seen
                    ):
                        seen.add((nx, ny))
                        queue.append((nx, ny))
    return components


def hole_count(mask: Image.Image) -> int:
    foreground = binary(mask, 1)
    background = ImageChops.invert(foreground)
    pixels = background.load()
    width, height = background.size
    seen: set[tuple[int, int]] = set()
    holes = 0
    for y in range(height):
        for x in range(width):
            if not pixels[x, y] or (x, y) in seen:
                continue
            queue = deque([(x, y)])
            seen.add((x, y))
            touches_edge = False
            while queue:
                px, py = queue.popleft()
                touches_edge |= px in (0, width - 1) or py in (0, height - 1)
                for nx, ny in (
                    (px - 1, py),
                    (px + 1, py),
                    (px, py - 1),
                    (px, py + 1),
                ):
                    if (
                        0 <= nx < width
                        and 0 <= ny < height
                        and pixels[nx, ny]
                        and (nx, ny) not in seen
                    ):
                        seen.add((nx, ny))
                        queue.append((nx, ny))
            if not touches_edge:
                holes += 1
    return holes


def mask_coordinates(mask: Image.Image) -> list[tuple[int, int]]:
    pixels = binary(mask, 1).load()
    width, height = mask.size
    return [
        (x, y)
        for y in range(height)
        for x in range(width)
        if pixels[x, y]
    ]


def coordinate_fingerprint(mask: Image.Image) -> str:
    payload = "\n".join(f"{x},{y}" for x, y in mask_coordinates(mask))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def rgb_fingerprint(mask: Image.Image, source: Image.Image) -> str:
    pixels = source.convert("RGB").load()
    payload = bytearray()
    for x, y in mask_coordinates(mask):
        payload.extend(pixels[x, y])
    return hashlib.sha256(payload).hexdigest()


def font(size: int, bold: bool = False):
    fonts = Path(os.environ.get("WINDIR", "")) / "Fonts"
    candidates = (
        fonts / ("msyhbd.ttc" if bold else "msyh.ttc"),
        fonts / "simhei.ttf",
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def overlay(
    base: Image.Image,
    mask: Image.Image,
    color: tuple[int, int, int],
    opacity: int,
) -> Image.Image:
    layer = Image.new("RGBA", base.size, (*color, 0))
    alpha = binary(mask, 1).point(lambda value: opacity if value else 0)
    layer.putalpha(alpha)
    return Image.alpha_composite(base.convert("RGBA"), layer)


def crop_scaled(image: Image.Image, box, scale: int = 8) -> Image.Image:
    crop = image.crop(box)
    return crop.resize(
        (crop.width * scale, crop.height * scale),
        Image.Resampling.NEAREST,
    )


def draw_label(draw: ImageDraw.ImageDraw, xy, text: str, size=28, bold=False):
    draw.text(xy, text, fill=(25, 25, 25), font=font(size, bold))


def build_visuals(
    source: Image.Image,
    envelope: Image.Image,
    visible: Image.Image,
    bracelet: Image.Image,
    formal: Image.Image,
    conflict: Image.Image,
    material_only: Image.Image,
    outside_material: Image.Image,
    first_pixel: tuple[int, int],
) -> None:
    box = (362, 505, 422, 565)
    scale = 8
    panel_size = ((box[2] - box[0]) * scale, (box[3] - box[1]) * scale)
    panels = []
    base = source.convert("RGBA")
    panels.append(("权威母图", crop_scaled(base, box, scale)))
    panels.append(
        (
            "蓝：389 px 临时包络",
            crop_scaled(overlay(base, envelope, (35, 90, 255), 175), box, scale),
        )
    )
    bracelet_panel = overlay(base, bracelet, (255, 190, 0), 150)
    bracelet_panel = overlay(bracelet_panel, conflict, (255, 0, 40), 235)
    panels.append(
        (
            "黄：手链所有权；红：冲突 81 px",
            crop_scaled(bracelet_panel, box, scale),
        )
    )
    formal_panel = overlay(base, formal, (0, 185, 175), 100)
    formal_panel = overlay(formal_panel, conflict, (255, 0, 40), 235)
    panels.append(
        (
            "青：正式前臂材料；红：可见冲突",
            crop_scaled(formal_panel, box, scale),
        )
    )
    classification = base
    classification = overlay(classification, outside_material, (50, 105, 255), 220)
    classification = overlay(classification, material_only, (255, 135, 0), 220)
    classification = overlay(classification, conflict, (255, 0, 40), 245)
    panels.append(
        (
            "包络分类：蓝 174 / 橙 134 / 红 81",
            crop_scaled(classification, box, scale),
        )
    )
    visible_panel = overlay(base, visible, (0, 190, 190), 115)
    visible_panel = overlay(visible_panel, envelope, (35, 90, 255), 115)
    visible_panel = overlay(visible_panel, conflict, (255, 0, 40), 245)
    panels.append(
        (
            "红区同时属于包络与冻结可见前臂",
            crop_scaled(visible_panel, box, scale),
        )
    )

    board = Image.new(
        "RGB",
        (panel_size[0] * 3, (panel_size[1] + 54) * 2 + 150),
        (238, 238, 238),
    )
    draw = ImageDraw.Draw(board)
    for index, (title, panel) in enumerate(panels):
        x = index % 3 * panel_size[0]
        y = index // 3 * (panel_size[1] + 54) + 42
        board.paste(panel.convert("RGB"), (x, y))
        draw_label(draw, (x + 8, y - 36), title, 25, True)
    footer_y = board.height - 135
    draw_label(
        draw,
        (12, footer_y),
        "结论：当前“整手在前臂之上”会让正式手部覆盖 81 个已冻结手链可见像素。",
        30,
        True,
    )
    draw_label(
        draw,
        (12, footer_y + 44),
        "这 81 px 不能复制给手部，也不能由手链承担腕缝；V_hand 因此尚未锁定。",
        27,
    )
    draw_label(
        draw,
        (12, footer_y + 82),
        f"最小反例：像素 ({first_pixel[0]}, {first_pixel[1]}) 同时属于 E_hand 与 V_bracelet。",
        27,
    )
    board.save(QA / "V8-A-STOP-REVIEW-BOARD.png")

    conflict_board = Image.new(
        "RGB",
        (panel_size[0] * 2, panel_size[1] + 112),
        (240, 240, 240),
    )
    conflict_board.paste(panels[2][1].convert("RGB"), (0, 48))
    conflict_board.paste(panels[5][1].convert("RGB"), (panel_size[0], 48))
    draw = ImageDraw.Draw(conflict_board)
    draw_label(draw, (8, 8), "V8-A 200% 以上腕根所有权冲突复核", 30, True)
    draw_label(
        draw,
        (8, conflict_board.height - 48),
        "左：手链与包络；右：可见前臂、包络与 81 px 红色交集。",
        26,
    )
    conflict_board.save(QA / "V8-A-ENVELOPE-BRACELET-CONFLICT-200PCT.png")

    px, py = first_pixel
    pixel_box = (px - 4, py - 4, px + 5, py + 5)
    pixel_source = crop_scaled(source.convert("RGBA"), pixel_box, 32)
    pixel_mask = crop_scaled(conflict.convert("RGBA"), pixel_box, 32)
    pixel_overlay = overlay(
        source.convert("RGBA"), conflict, (255, 0, 40), 235
    )
    pixel_overlay = crop_scaled(pixel_overlay, pixel_box, 32)
    mini = Image.new(
        "RGB",
        (1200, pixel_source.height + 110),
        (240, 240, 240),
    )
    mini.paste(pixel_source.convert("RGB"), (0, 48))
    mini.paste(pixel_overlay.convert("RGB"), (pixel_source.width, 48))
    draw = ImageDraw.Draw(mini)
    draw_label(draw, (8, 8), "最小反例：一个冻结手链像素被强制纳入手部最低包络", 28, True)
    draw_label(
        draw,
        (8, mini.height - 48),
        f"坐标 ({px}, {py})；左为母图，右侧红色为 E_hand ∩ V_bracelet。",
        25,
    )
    mini.save(QA / "V8-A-MINIMAL-COUNTEREXAMPLE.png")


def evidence_manifest() -> dict:
    entries = []
    for path in sorted(ROOT.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.name != "v8a-evidence-manifest.json"
        ):
            entries.append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
    return {
        "schemaVersion": 1,
        "root": "arm-chain-screen-right-v8-formal-hand-geometry",
        "fileCount": len(entries),
        "files": entries,
    }


def main() -> None:
    input_rows = []
    for label, (path, expected_hash, expected_bytes) in EXPECTED_INPUTS.items():
        actual_hash = sha256(path) if path.exists() else None
        actual_bytes = path.stat().st_size if path.exists() else None
        input_rows.append(
            {
                "path": label,
                "expectedSha256": expected_hash,
                "actualSha256": actual_hash,
                "expectedBytes": expected_bytes,
                "actualBytes": actual_bytes,
                "pass": (
                    actual_hash == expected_hash
                    and actual_bytes == expected_bytes
                ),
            }
        )
    if not all(row["pass"] for row in input_rows):
        raise RuntimeError("V8-A input integrity failed.")

    contract = json.loads(ENVELOPE_CONTRACT.read_text(encoding="utf-8"))
    source = Image.open(COLOR_SOURCE).convert("RGB")
    envelope = load_mask(ENVELOPE)
    formal = load_mask(FORMAL_FOREARM)
    visible = load_mask(VISIBLE_FOREARM)
    bracelet = load_mask(BRACELET)
    source_support = load_mask(SOURCE_ROOT_SUPPORT)

    conflict_visible = intersection(envelope, visible)
    conflict_bracelet = intersection(envelope, bracelet)
    conflict_formal = intersection(envelope, formal)
    formal_only = subtract(conflict_formal, conflict_visible)
    outside_formal = subtract(envelope, formal)
    without_visible = subtract(envelope, visible)
    outside_source_support = subtract(envelope, source_support)
    exclusive_hand_root_support = subtract(source_support, visible)
    outside_exclusive_hand_support = subtract(
        envelope, exclusive_hand_root_support
    )

    if count(conflict_visible) != count(conflict_bracelet):
        raise RuntimeError("The earliest conflict is no longer bracelet-only.")
    if count(ImageChops.difference(conflict_visible, conflict_bracelet)) != 0:
        raise RuntimeError("Visible-forearm and bracelet conflict sets diverged.")

    rgba_mask(conflict_visible, (255, 0, 40)).save(
        MASKS / "envelope-visible-forearm-conflict-81px.png"
    )
    rgba_mask(conflict_bracelet, (255, 0, 40)).save(
        MASKS / "envelope-bracelet-conflict-81px.png"
    )
    rgba_mask(conflict_formal, (255, 135, 0)).save(
        MASKS / "envelope-formal-forearm-material-overlap-215px.png"
    )
    rgba_mask(formal_only, (255, 135, 0)).save(
        MASKS / "envelope-hidden-forearm-material-only-overlap-134px.png"
    )
    rgba_mask(outside_formal, (50, 105, 255)).save(
        MASKS / "envelope-outside-formal-forearm-material-174px.png"
    )
    rgba_mask(without_visible, (50, 105, 255)).save(
        MASKS / "envelope-without-visible-forearm-308px.png"
    )

    wrist_x, wrist_y = contract["frozenWrist"]
    axis_x, axis_y = contract["localCoordinates"]["axis"]
    normal_x, normal_y = contract["localCoordinates"]["normal"]
    round_trip_differences = 0
    maximum_float_error = 0.0
    for x, y in mask_coordinates(envelope):
        dx = x - wrist_x
        dy = y - wrist_y
        s = dx * axis_x + dy * axis_y
        n = dx * normal_x + dy * normal_y
        rx = wrist_x + s * axis_x + n * normal_x
        ry = wrist_y + s * axis_y + n * normal_y
        maximum_float_error = max(
            maximum_float_error, abs(rx - x), abs(ry - y)
        )
        if round(rx) != x or round(ry) != y:
            round_trip_differences += 1

    coordinates = mask_coordinates(conflict_bracelet)
    first_pixel = coordinates[0]
    source_pixels = source.load()
    samples = [
        {"coordinate": [x, y], "sourceRgb": list(source_pixels[x, y])}
        for x, y in coordinates[:12]
    ]

    build_visuals(
        source,
        envelope,
        visible,
        bracelet,
        formal,
        conflict_bracelet,
        formal_only,
        outside_formal,
        first_pixel,
    )

    integrity = {
        "schemaVersion": 1,
        "status": "pass",
        "inputs": input_rows,
    }
    write_json(AUDIT / "v8a-input-integrity.json", integrity)

    report = {
        "schemaVersion": 1,
        "gate": "V8-A formal hand visible ownership and envelope compatibility",
        "status": "stopped_at_earliest_contract_conflict",
        "decisionOwner": "user",
        "lastValidUpstreamGate": "V7-C1 independently reverified",
        "scope": {
            "formalCompleteHandGenerated": False,
            "handTextureGenerated": False,
            "psdGenerated": False,
            "artMeshOrCubismWork": False,
            "fingerSplit": False,
            "drawOrderOrClippingChangeImplemented": False,
        },
        "vHand": {
            "status": "not_locked_due_to_earliest_envelope_draw_order_conflict",
            "pixelCount": None,
            "coordinateFingerprint": None,
            "rgbFingerprint": None,
            "sourceCoordinateDifferencePixels": None,
            "sourceRgbDifferencePixels": None,
            "reason": (
                "The frozen minimum envelope already conflicts with frozen "
                "bracelet ownership under the current whole-hand-above-forearm "
                "draw order, before full-hand boundary classification begins."
            ),
        },
        "frozenEnvelope": {
            "sha256": sha256(ENVELOPE),
            "pixels": count(envelope),
            "connectedComponents": connected_components(envelope),
            "holes": hole_count(envelope),
            "coordinateFingerprint": coordinate_fingerprint(envelope),
            "rgbFingerprintOnAuthorityColorSource": rgb_fingerprint(
                envelope, source
            ),
            "localCoordinateRasterRoundTripDifferencePixels": (
                round_trip_differences
            ),
            "maximumFloatRoundTripErrorPx": maximum_float_error,
        },
        "envelopeClassification": {
            "eHandIntersectVHandPixels": None,
            "eHandMinusVHandInsideOriginalHandSourceSupportPixels": None,
            "notEvaluatedReason": (
                "Exact V_hand is intentionally not claimed after the earlier "
                "frozen bracelet conflict."
            ),
            "eHandIntersectVisibleForearmPixels": count(conflict_visible),
            "eHandIntersectBraceletPixels": count(conflict_bracelet),
            "eHandIntersectFormalForearmMaterialPixels": count(conflict_formal),
            "eHandIntersectHiddenForearmMaterialOnlyPixels": count(formal_only),
            "eHandOutsideFormalForearmMaterialPixels": count(outside_formal),
            "eHandMinusVisibleForearmPixels": count(without_visible),
            "eHandOutsideApprovedNeutralPersonSupportPixels": count(
                outside_source_support
            ),
            "eHandOutsideExclusiveVisibleHandRootSupportPixels": count(
                outside_exclusive_hand_support
            ),
            "interpretation": (
                "The old zero-outside-source-hand result used a source arm/root "
                "support polygon that includes bracelet-owned pixels. Once "
                "unique visible ownership is applied, 81 envelope pixels lie "
                "outside exclusive hand-root support."
            ),
        },
        "earliestFailure": {
            "id": "frozen-envelope-intersects-frozen-bracelet-ownership",
            "pixels": count(conflict_bracelet),
            "minimalCounterexample": {
                "coordinate": list(first_pixel),
                "sourceRgb": list(source_pixels[first_pixel[0], first_pixel[1]]),
                "membership": [
                    "temporary_hand_envelope",
                    "visible_forearm",
                    "bracelet",
                ],
            },
            "samplePixels": samples,
            "setIdentity": (
                "E_hand ∩ V_forearm = E_hand ∩ V_bracelet = 81 px"
            ),
            "drawOrderConsequence": (
                "A semantically pure skin hand material that contains E_hand "
                "and is drawn above the forearm must cover these 81 visible "
                "bracelet pixels at neutral pose. Copying bracelet pixels into "
                "the hand would duplicate ownership and contaminate the hand."
            ),
        },
        "drawOrderCompatibility": {
            "currentContract": "whole hand above forearm",
            "status": "fail",
            "braceletMayCoverWristSeam": False,
            "singleWholeHandLayerFeasibleUnderCurrentOrder": False,
        },
        "structuralOptions": [
            {
                "id": "reverse-whole-part-order",
                "summary": (
                    "Place the forearm, including the bracelet, above the whole "
                    "hand and rerun neutral plus the complete wrist domain."
                ),
                "reopens": [
                    "V7-C1 temporary hand-root draw-order contract",
                    "V7 wrist 201+11+81 proof",
                    "V7 elbow-by-wrist 9x9 proof",
                    "neutral default recomposition review",
                ],
            },
            {
                "id": "separate-bracelet-foreground-occluder",
                "summary": (
                    "Reopen the bracelet as a foreground occluder instead of a "
                    "single merged forearm runtime material."
                ),
                "reopens": [
                    "V7-A bracelet ownership and no-runtime-layer decision",
                    "V7-C1 forearm material contract",
                    "V7 wrist and combined-domain proof",
                ],
            },
            {
                "id": "split-hand-root-depth",
                "summary": (
                    "Split hand-root depth from the rest of the hand so only "
                    "the root passes behind the bracelet/forearm."
                ),
                "reopens": [
                    "current whole-hand material granularity",
                    "current single hand draw-order contract",
                    "V7 wrist and combined-domain proof",
                ],
            },
        ],
        "nextGate": {
            "v8BAllowed": False,
            "requiredUserDecision": (
                "Choose a structure to reopen; no formal complete hand may be "
                "generated under the current contract."
            ),
        },
    }
    write_json(
        AUDIT / "v8a-hand-ownership-envelope-compatibility.json", report
    )

    markdown = f"""# V8-A 正式手部所有权与 389 px 包络相容性

## 结论

V8-A 在最早合同冲突处停止，当前不允许进入 V8-B。

冻结临时手根包络仍为 `389 px`、单连通、孔洞 `0`，哈希一致，手局部坐标
往返栅格差 `0`。但是本地集合复算得到：

- `E_hand ∩ V_forearm = 81 px`；
- `E_hand ∩ V_bracelet = 81 px`；
- 两个交集逐像素完全相同；
- `E_hand ∩ M_forearm = 215 px`，其中除可见手链外还有 `134 px` 隐藏前臂材料重叠；
- `E_hand \\ M_forearm = 174 px`；
- `E_hand` 位于批准的中性人物支持区外 `0 px`；
- 应用唯一可见所有权后，`E_hand` 位于专属手根支持区外 `81 px`。

旧合同中的“原始手部轮廓外 `0`”实际使用了包含手链所有权的手臂/手根支持
多边形，不能证明包络全部属于正式手部。

## 最早失败点

最小反例是坐标 `({first_pixel[0]}, {first_pixel[1]})`：它同时属于冻结
`E_hand`、冻结可见前臂和手链所有权。

在“整手绘制于前臂之上”的当前合同下，任何静态包含 `E_hand` 的纯皮肤手部
都会在默认位置覆盖 `81 px` 可见手链。把手链像素复制进手部会造成源像素
重复所有权和材料污染；让手链承担腕缝覆盖也被合同禁止。

因此：

- 当前单一整手材料与当前 Draw Order 不相容；
- `V_hand` 尚未锁定，不能给出伪造的像素数或指纹；
- 未生成完整 `M_hand`、纹理、PSD、ArtMesh、Cubism 或拆指结果；
- 不允许进入 V8-B。

## 中文视觉证据

1. `qa/V8-A-STOP-REVIEW-BOARD.png`
2. `qa/V8-A-ENVELOPE-BRACELET-CONFLICT-200PCT.png`
3. `qa/V8-A-MINIMAL-COUNTEREXAMPLE.png`

## 可选结构

1. 整体反转层序：前臂（含手链）在整手之上；重开 V7 手根层序、腕部全域、
   `9×9` 组合域和默认回组。
2. 把手链重开为前景遮挡层；重开 V7-A 手链归属、前臂材料合同及腕部全域。
3. 拆分手根深度；重开整手单材料粒度、单一手部层序及腕部全域。

本轮未实现上述任一结构，等待用户裁决。
"""
    (AUDIT / "V8-A-HAND-OWNERSHIP-ENVELOPE-COMPATIBILITY.zh-CN.md").write_text(
        markdown, encoding="utf-8"
    )
    write_json(AUDIT / "v8a-evidence-manifest.json", evidence_manifest())

    print(
        json.dumps(
            {
                "status": report["status"],
                "envelopePixels": count(envelope),
                "braceletConflictPixels": count(conflict_bracelet),
                "formalForearmOverlapPixels": count(conflict_formal),
                "coordinateRoundTripDifferencePixels": (
                    round_trip_differences
                ),
                "vHandLocked": False,
                "v8BAllowed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
