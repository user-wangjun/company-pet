from __future__ import annotations

import hashlib
import io
import json
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
LINE_PATH = XIAOXING_ROOT / "source" / "masters" / "front-line-source-exact-after-reset.png"
COLOR_PATH = XIAOXING_ROOT / "source" / "masters" / "front-color-source-exact-after-reset.png"

MASKS_DIR = ROOT / "masks"
QA_DIR = ROOT / "qa"
AUDIT_DIR = ROOT / "audit"

VISIBLE_MASK_PATH = MASKS_DIR / "visible-upper-arm-locked.png"
SLEEVE_OCCLUDER_PATH = MASKS_DIR / "sleeve-hem-occluder-alpha-locked.png"
SLEEVE_CORE_PATH = MASKS_DIR / "sleeve-hem-core-reference.png"
SKIN_CORE_PATH = MASKS_DIR / "upper-arm-skin-core-reference.png"
MIXED_BAND_PATH = MASKS_DIR / "sleeve-hem-aa-mixed-band.png"
VISIBLE_TEXTURE_REFERENCE_PATH = QA_DIR / "visible-upper-arm-source-pixels-reference.png"

OWNERSHIP_REVIEW_PATH = QA_DIR / "ownership-line-color-mask-800.png"
VISIBLE_CHECKER_PATH = QA_DIR / "visible-upper-arm-checkerboard.png"
HEM_NO_OVERLAY_PATH = QA_DIR / "sleeve-hem-no-overlay-800.png"
HEM_THIN_OVERLAY_PATH = QA_DIR / "sleeve-hem-thin-overlay-800.png"
HEM_OWNERSHIP_PATH = QA_DIR / "sleeve-hem-ownership-800.png"

PIXEL_AUDIT_PATH = AUDIT_DIR / "visible-upper-arm-pixel-copy.json"
OWNERSHIP_AUDIT_PATH = AUDIT_DIR / "ownership-gate.json"
OWNERSHIP_REPORT_PATH = AUDIT_DIR / "ownership-gate.zh-CN.md"
APPROVAL_PATH = AUDIT_DIR / "ownership-gate-user-approval-2026-07-25.json"

CANVAS = (512, 1086)
REVIEW_CROP = (328, 372, 380, 424)
SCALE = 8

# The authoritative line/color masters show this sleeve-hem centerline. Points are
# in the original integer coordinate system and intentionally retain asymmetry.
HEM_CENTERLINE = (
    (336, 398),
    (340, 397),
    (345, 397),
    (350, 395),
    (355, 394),
    (360, 392),
    (365, 391),
    (370, 389),
    (375, 387),
    (380, 384),
    (385, 381),
    (390, 378),
    (395, 374),
)

# This polygon follows the visible skin/outline envelope between the sleeve hem
# and the frozen V4 elbow split. It is intersected with the V4 upper-arm
# candidate, then clipped by the sleeve-owned mixed band.
VISIBLE_UPPER_ARM_ENVELOPE = (
    (336, 398),
    (340, 397),
    (345, 397),
    (350, 395),
    (355, 394),
    (360, 392),
    (363, 390),
    (364, 393),
    (365, 397),
    (366, 400),
    (367, 404),
    (368, 408),
    (370, 412),
    (371, 416),
    (371, 418),
    (340, 418),
    (339, 413),
    (338, 406),
)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_v4_alpha(archive: zipfile.ZipFile, path: str) -> Image.Image:
    return Image.open(io.BytesIO(archive.read(path))).convert("RGBA").getchannel("A")


def alpha_png(mask: Image.Image) -> Image.Image:
    result = Image.new("RGBA", CANVAS, (255, 255, 255, 0))
    result.putalpha(mask)
    return result


def pixel_count(mask: Image.Image) -> int:
    histogram = mask.histogram()
    return sum(histogram[1:])


def crop_scaled(image: Image.Image) -> Image.Image:
    width = (REVIEW_CROP[2] - REVIEW_CROP[0]) * SCALE
    height = (REVIEW_CROP[3] - REVIEW_CROP[1]) * SCALE
    return image.crop(REVIEW_CROP).resize((width, height), Image.Resampling.NEAREST)


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


def add_title(panel: Image.Image, title: str, note: str = "") -> Image.Image:
    header = 58 if note else 42
    canvas = Image.new("RGB", (panel.width, panel.height + header), (240, 240, 240))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 4), title, fill=(20, 20, 20), font=font(22))
    if note:
        draw.text((8, 32), note, fill=(70, 70, 70), font=font(14))
    canvas.paste(panel.convert("RGB"), (0, header))
    return canvas


def stack_panels(panels: list[Image.Image], columns: int) -> Image.Image:
    gap = 18
    rows = (len(panels) + columns - 1) // columns
    cell_w = max(panel.width for panel in panels)
    cell_h = max(panel.height for panel in panels)
    canvas = Image.new(
        "RGB",
        (columns * cell_w + (columns + 1) * gap, rows * cell_h + (rows + 1) * gap),
        (228, 228, 228),
    )
    for index, panel in enumerate(panels):
        x = gap + (index % columns) * (cell_w + gap)
        y = gap + (index // columns) * (cell_h + gap)
        canvas.paste(panel, (x, y))
    return canvas


def outline(mask: Image.Image) -> Image.Image:
    dilated = mask.filter(ImageFilter.MaxFilter(3))
    eroded = ImageChops.invert(
        ImageChops.invert(mask).filter(ImageFilter.MaxFilter(3))
    )
    return ImageChops.subtract(dilated, eroded)


# Imported late only to keep the image-operation list grouped above.
from PIL import ImageFilter  # noqa: E402


def tint_overlay(
    base: Image.Image,
    layers: list[tuple[Image.Image, tuple[int, int, int, int]]],
) -> Image.Image:
    result = base.convert("RGBA")
    for mask, rgba in layers:
        tint = Image.new("RGBA", result.size, rgba)
        transparent = Image.new("RGBA", result.size, (0, 0, 0, 0))
        result.alpha_composite(Image.composite(tint, transparent, mask))
    return result


def make_review_images(
    line: Image.Image,
    color: Image.Image,
    visible: Image.Image,
    sleeve_core: Image.Image,
    mixed_band: Image.Image,
) -> None:
    line_crop = crop_scaled(line)
    color_crop = crop_scaled(color)
    visible_crop = crop_scaled(visible)
    sleeve_core_crop = crop_scaled(sleeve_core)
    mixed_crop = crop_scaled(mixed_band)

    mask_rgb = Image.new("RGB", visible_crop.size, (255, 255, 255))
    mask_rgb.paste((0, 160, 220), mask=visible_crop)
    ownership = tint_overlay(
        color_crop,
        [
            (sleeve_core_crop, (45, 110, 255, 125)),
            (mixed_crop, (255, 205, 0, 190)),
            (visible_crop, (0, 210, 175, 125)),
        ],
    )
    panels = [
        add_title(line_crop, "权威线稿 800% 最近邻", "同坐标审查裁剪，不是材料"),
        add_title(color_crop, "权威彩稿 800% 最近邻", "同坐标审查裁剪，不是材料"),
        add_title(mask_rgb, "可见上臂候选遮罩", "青色为 V_upper_arm；待用户批准"),
        add_title(
            ownership,
            "所有权叠加",
            "蓝=袖子核心，黄=2 px 混合带归袖子，绿=上臂",
        ),
    ]
    stack_panels(panels, 2).save(OWNERSHIP_REVIEW_PATH)

    color_crop.save(HEM_NO_OVERLAY_PATH)
    hem_line = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(hem_line).line(HEM_CENTERLINE, fill=255, width=1, joint="curve")
    hem_outline = crop_scaled(hem_line)
    thin = tint_overlay(color_crop, [(hem_outline, (255, 0, 30, 215))])
    thin = add_title(
        thin,
        "袖口中心线细线叠加 800%",
        "红线 1 px；原稿整数坐标；不是正式材料",
    )
    thin.save(HEM_THIN_OVERLAY_PATH)
    add_title(
        ownership,
        "袖口所有权 800% 最近邻",
        "蓝=袖子核心，黄=抗锯齿混合带且归袖子，绿=上臂核心",
    ).save(HEM_OWNERSHIP_PATH)


def make_checker_review(color: Image.Image, visible: Image.Image) -> Image.Image:
    bbox = visible.getbbox()
    if bbox is None:
        raise RuntimeError("Visible upper-arm mask is empty.")
    pad = 12
    crop_box = (
        max(0, bbox[0] - pad),
        max(0, bbox[1] - pad),
        min(CANVAS[0], bbox[2] + pad),
        min(CANVAS[1], bbox[3] + pad),
    )
    source_layer = color.convert("RGBA")
    source_layer.putalpha(visible)
    cropped = source_layer.crop(crop_box)
    scaled_size = (cropped.width * SCALE, cropped.height * SCALE)
    board = checkerboard(scaled_size, cell=16)
    board.paste(
        cropped.resize(scaled_size, Image.Resampling.NEAREST),
        (0, 0),
        cropped.getchannel("A").resize(scaled_size, Image.Resampling.NEAREST),
    )
    return add_title(
        board,
        "可见上臂源像素棋盘格 800%",
        "RGB 逐像素复制自权威彩稿；透明区不属于上臂",
    )


def main() -> None:
    MASKS_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    line = Image.open(LINE_PATH).convert("RGB")
    color = Image.open(COLOR_PATH).convert("RGB")
    with zipfile.ZipFile(V4_ZIP_PATH) as archive:
        sleeve_bytes = archive.read("masks/visible/sleeve.png")
        upper_bytes = archive.read("masks/visible/upper_arm.png")
        sleeve_candidate = load_v4_alpha(archive, "masks/visible/sleeve.png")
        upper_candidate = load_v4_alpha(archive, "masks/visible/upper_arm.png")

    hem_center = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(hem_center).line(HEM_CENTERLINE, fill=255, width=1, joint="curve")
    # Width 5 means the center pixel plus two pixels on either side. This is the
    # predeclared 2 px mixed band in the flattened RGB source.
    hem_mixed = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(hem_mixed).line(HEM_CENTERLINE, fill=255, width=5, joint="curve")

    sleeve_core = ImageChops.subtract(sleeve_candidate, hem_mixed)
    sleeve_occluder = ImageChops.lighter(sleeve_candidate, hem_mixed)

    envelope = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(envelope).polygon(VISIBLE_UPPER_ARM_ENVELOPE, fill=255)
    visible_upper = ImageChops.multiply(upper_candidate, envelope)
    visible_upper = ImageChops.subtract(visible_upper, sleeve_occluder)

    # The reference "skin core" is identical to the proposed V_upper_arm at this
    # gate. The mixed band is excluded and belongs to the sleeve.
    skin_core = visible_upper.copy()

    alpha_png(visible_upper).save(VISIBLE_MASK_PATH)
    alpha_png(sleeve_occluder).save(SLEEVE_OCCLUDER_PATH)
    alpha_png(sleeve_core).save(SLEEVE_CORE_PATH)
    alpha_png(skin_core).save(SKIN_CORE_PATH)
    alpha_png(hem_mixed).save(MIXED_BAND_PATH)

    visible_texture = color.convert("RGBA")
    visible_texture.putalpha(visible_upper)
    visible_texture.save(VISIBLE_TEXTURE_REFERENCE_PATH)

    source_pixels = color.load()
    copied_pixels = visible_texture.load()
    max_rgb_difference = 0
    differing_pixels = 0
    for y in range(CANVAS[1]):
        for x in range(CANVAS[0]):
            if visible_upper.getpixel((x, y)) == 0:
                continue
            source_rgb = source_pixels[x, y]
            copied_rgb = copied_pixels[x, y][:3]
            difference = max(abs(a - b) for a, b in zip(source_rgb, copied_rgb))
            max_rgb_difference = max(max_rgb_difference, difference)
            if difference:
                differing_pixels += 1

    make_review_images(line, color, visible_upper, sleeve_core, hem_mixed)
    make_checker_review(color, visible_upper).save(VISIBLE_CHECKER_PATH)

    visible_bbox = list(visible_upper.getbbox() or ())
    approved = False
    if APPROVAL_PATH.exists():
        approval = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))
        approved = approval.get("status") == "approved" and all(
            approval.get("approvedItems", {}).get(item) is True
            for item in (
                "visibleUpperArmBoundary",
                "sleeveHemOccluderBoundary",
                "mixedBandOwnedBySleeve",
                "predeclaredMotionFringeTolerance",
            )
        )
    pixel_audit = {
        "schemaVersion": 1,
        "auditDate": date.today().isoformat(),
        "status": "pass_user_visual_approved" if approved else "pass_pending_user_visual_approval",
        "source": "source/masters/front-color-source-exact-after-reset.png",
        "visibleMask": (
            "validation/arm-chain-screen-right-v5-hidden-upper-arm/"
            "masks/visible-upper-arm-locked.png"
        ),
        "visiblePixelCount": pixel_count(visible_upper),
        "boundingBoxExclusive": visible_bbox,
        "differingRgbPixelCount": differing_pixels,
        "maximumRgbChannelDifference": max_rgb_difference,
        "pixelExactCopy": differing_pixels == 0,
        "visiblePixelsRescaled": False,
        "visiblePixelsRedrawn": False,
        "note": (
            "The visible-pixel copy is locked by explicit user approval."
            if approved
            else "The filename is the proposed lock target. It is not an approved "
            "lock until the user passes the Chinese visual gate."
        ),
    }
    PIXEL_AUDIT_PATH.write_text(
        json.dumps(pixel_audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    ownership_audit = {
        "schemaVersion": 1,
        "auditDate": date.today().isoformat(),
        "status": "engineering_pass_user_visual_approved" if approved else "awaiting_user_visual_approval",
        "scope": "exact visible upper arm and sleeve-hem occluder ownership",
        "coordinateSystem": {
            "canvas": [512, 1086],
            "origin": "top_left",
            "integerCoordinates": True,
            "reviewCropExclusive": list(REVIEW_CROP),
        },
        "authority": {
            "line": "source/masters/front-line-source-exact-after-reset.png",
            "color": "source/masters/front-color-source-exact-after-reset.png",
            "lineSha256": sha256_file(LINE_PATH),
            "colorSha256": sha256_file(COLOR_PATH),
        },
        "v4Candidates": {
            "sourceArchive": (
                "validation/arm-chain-screen-right-v4-wrist-motion/archive/"
                "stage-a-v4-approved-2026-07-24.zip"
            ),
            "visibleSleeveSha256": sha256_bytes(sleeve_bytes),
            "visibleUpperArmSha256": sha256_bytes(upper_bytes),
            "treatment": (
                "Reference candidates only. The V4 upper-arm start at y=383 was "
                "rejected because it enters the sleeve region."
            ),
        },
        "ownership": {
            "sleeveHemCenterline": [list(point) for point in HEM_CENTERLINE],
            "mixedBandWidthPx": 2,
            "mixedBandTotalStrokeWidthPx": 5,
            "mixedBandOwner": "sleeve",
            "visibleUpperArmEnvelope": [
                list(point) for point in VISIBLE_UPPER_ARM_ENVELOPE
            ],
            "visibleUpperArmPixelCount": pixel_count(visible_upper),
            "sleeveCorePixelCount": pixel_count(sleeve_core),
            "mixedBandPixelCount": pixel_count(hem_mixed),
            "visibleUpperArmBoundingBoxExclusive": visible_bbox,
            "excludedOwners": [
                "sleeve",
                "forearm",
                "bracelet",
                "shirt_body",
                "hair",
                "background",
            ],
        },
        "flatSourceLimitation": (
            "The authoritative masters are RGB, not layered RGBA. Fractional "
            "source alpha is not recoverable. The emitted sleeve alpha is a "
            "locked ownership alpha for the flattened composite, with the mixed "
            "band assigned to the sleeve; it is not claimed to be original layer alpha."
        ),
        "predeclaredMotionFringeTolerance": {
            "defaultAtOneToOne": "zero changed source pixels",
            "movingAtOneHundredPercent": (
                "at most one continuous source-pixel fringe; no detached dark halo, "
                "no crawling, and no intermittent gap"
            ),
            "movingAtTwoHundredPercent": (
                "at most two nearest-neighbor display pixels, corresponding to one "
                "source pixel"
            ),
            "failureAction": (
                "Stop and request original layered art or separate approval for "
                "controlled boundary reconstruction."
            ),
        },
        "pixelCopyAudit": pixel_audit,
        "userApproval": (
            "audit/ownership-gate-user-approval-2026-07-25.json"
            if approved
            else None
        ),
        "nextGate": (
            "Compute H_total, define H_test and prove the continuous-domain "
            "coverage lower bound."
            if approved
            else "Obtain explicit Chinese visual approval for both V_upper_arm "
            "and the sleeve-hem ownership before computing final H_test."
        ),
    }
    OWNERSHIP_AUDIT_PATH.write_text(
        json.dumps(ownership_audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    approval_summary = (
        "**工程检查通过，用户中文视觉门禁已批准。**"
        if approved
        else "**工程候选已生成，等待用户中文视觉批准。**"
    )
    approval_note = (
        "批准记录：`audit/ownership-gate-user-approval-2026-07-25.json`。"
        if approved
        else "文件名中的 `locked` 表示批准后将锁定的目标文件，不表示当前已经获得批准。"
    )
    next_step = (
        "当前可继续计算 `H_total`、划定 `H_test` 并证明连续参数域覆盖下界；"
        "该批准不覆盖隐藏纹理或后续 QA。"
        if approved
        else "批准前不计算最终 `H_test`，不补隐藏纹理。"
    )
    OWNERSHIP_REPORT_PATH.write_text(
        f"""# 阶段 B：可见上臂与袖口所有权门禁

## 当前决定

{approval_summary}

{approval_note} {next_step}

## 可见上臂 `V_upper_arm`

- 坐标母图：`source/masters/front-color-source-exact-after-reset.png`
- 线稿边界：`source/masters/front-line-source-exact-after-reset.png`
- 全画布候选：`masks/visible-upper-arm-locked.png`
- 源像素参考层：`qa/visible-upper-arm-source-pixels-reference.png`
- 可见像素数：`{pixel_count(visible_upper)}`
- 包围盒（右、下边界不含）：`{visible_bbox}`
- RGB 复制差异像素：`{differing_pixels}`
- 最大通道差异：`{max_rgb_difference}`

V4 可见上臂候选从固定 `y=383` 开始，进入了实际袖子区域，因此没有直接沿用。本候选使用原稿袖口折线、原稿手臂轮廓和冻结 V4 肘部分界的交集。袖子、前臂、手链、衣身、头发和背景均排除。

## 袖口遮挡 alpha 与混合带

- 遮挡 alpha 候选：`masks/sleeve-hem-occluder-alpha-locked.png`
- 袖子核心参考：`masks/sleeve-hem-core-reference.png`
- 抗锯齿混合带：`masks/sleeve-hem-aa-mixed-band.png`
- 上臂皮肤核心参考：`masks/upper-arm-skin-core-reference.png`

权威正面母图是 RGB 扁平图，无法恢复原始图层的分数 alpha。本轮锁定的是扁平画面的**像素所有权 alpha**：袖口中心线两侧共 5 px 描边，即中心像素加每侧 2 px，全部归袖子所有；不声称它是原始分层 alpha。

## 预先声明的运动脏边容差

- 默认 1:1 回组：允许改变的源像素数为 `0`。
- 100% 运动审查：最多允许连续 `1` 个源像素宽的边缘色带；不得出现独立暗边、透明缝、爬动或间歇闪烁。
- 200% 最近邻审查：最多允许 `2` 个显示像素，对应 `1` 个源像素。
- 超过以上任一标准即停止，必须请求原画分层，或另行批准受控边界重建；不得临时改写所有权。

## 请审查

1. `qa/ownership-line-color-mask-800.png`：线稿、彩稿、遮罩及所有权同坐标 800% 对照。
2. `qa/visible-upper-arm-checkerboard.png`：可见上臂源像素棋盘格。
3. `qa/sleeve-hem-no-overlay-800.png`：无叠加原稿。
4. `qa/sleeve-hem-thin-overlay-800.png`：1 px 袖口中心线叠加。
5. `qa/sleeve-hem-ownership-800.png`：袖子核心、混合带、皮肤核心所有权。

## 需要的批准

请分别确认：

1. `V_upper_arm` 的袖口、手臂两侧和肘部分界是否可以锁定；
2. 袖口混合带归袖子所有，以及上述运动脏边容差是否可以锁定。
""",
        encoding="utf-8",
    )
    print("Built ownership gate; status: awaiting_user_visual_approval")


if __name__ == "__main__":
    main()
