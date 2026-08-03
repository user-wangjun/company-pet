from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
VALIDATION = WORKBENCH / "validation"
V14 = VALIDATION / "arm-chain-screen-left-v14-complete-textures"
V22 = VALIDATION / "arm-chain-screen-left-v22-material-repair"
V14_MANIFEST = V14 / "audit/v14-complete-texture-freeze-manifest-2026-07-28.json"
V22_REPORT = V22 / "audit/v22-material-repair-report.json"
REFERENCE = WORKBENCH / "model/working-v8/body-original-pixel/04_sleeve_screen_right.png"
SOURCE = WORKBENCH / "source/masters/front-color-source-exact-after-reset.png"
QA = STAGE / "qa"
AUDIT = STAGE / "audit"
MATERIALS = STAGE / "materials"
MASKS = STAGE / "masks"
BOARD = QA / "V23-SLEEVE-REFERENCE-REPAIR-USER-REVIEW.zh-CN.png"
REPORT = AUDIT / "v23-sleeve-reference-repair-report.json"

LAYERS = ("sleeve", "upper_arm", "forearm_bracelet", "whole_hand")
W, H = 512, 1086
CROP = (65, 205, 225, 635)
COLORS = {"sleeve": (65, 119, 190), "upper_arm": (236, 148, 52)}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_v14() -> dict:
    manifest = json.loads(V14_MANIFEST.read_text(encoding="utf-8"))
    bad = []
    for item in manifest["lockedArtifacts"]:
        path = V14 / item["path"]
        if not path.exists() or path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            bad.append(item["path"])
    return {
        "matched": len(manifest["lockedArtifacts"]) - len(bad),
        "total": len(manifest["lockedArtifacts"]),
        "mismatches": bad,
        "pass": not bad,
    }


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in (
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def alpha(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA").getchannel("A")


def save_alpha(path: Path, channel: Image.Image) -> None:
    image = Image.new("RGBA", channel.size, (255, 255, 255, 0))
    image.putalpha(channel)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    image = Image.new("RGBA", size, (238, 238, 238, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(205, 205, 205, 255))
    return image


def tinted(mask: Image.Image, color: tuple[int, int, int], opacity: int = 255) -> Image.Image:
    image = Image.new("RGBA", mask.size, color + (0,))
    image.putalpha(mask.point(lambda value: round(value * opacity / 255)))
    return image


def crop(image: Image.Image, size=(330, 820), nearest=False) -> Image.Image:
    method = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
    return image.crop(CROP).resize(size, method)


def fill_clean_sleeve(
    old_material: Image.Image,
    visible_mask: Image.Image,
    hidden_mask: Image.Image,
    source: Image.Image,
) -> Image.Image:
    source_px = source.load()
    result = old_material.copy()
    result_px = result.load()
    visible_px = visible_mask.load()
    # Only bright, low-chroma cloth anchors are eligible. This explicitly
    # rejects sleeve seam ink and any dark neighboring hair strands.
    anchors: list[tuple[int, int, tuple[int, int, int]]] = []
    for y in range(H):
        for x in range(W):
            if visible_px[x, y] == 0:
                continue
            rgb = source_px[x, y]
            if sum(rgb) / 3 >= 215 and max(rgb) - min(rgb) <= 42:
                anchors.append((x, y, rgb))
            result_px[x, y] = rgb + (255,)
    hidden_px = hidden_mask.load()
    for y in range(H):
        for x in range(W):
            if hidden_px[x, y] == 0:
                continue
            nearby = sorted(
                anchors,
                key=lambda item: (item[0] - x) ** 2 + (item[1] - y) ** 2,
            )[:16]
            if nearby:
                weights = [1.0 / (1.0 + (ax - x) ** 2 + (ay - y) ** 2) for ax, ay, _ in nearby]
                total = sum(weights)
                rgb = tuple(
                    round(sum(weight * color[channel] for weight, (_, _, color) in zip(weights, nearby)) / total)
                    for channel in range(3)
                )
            else:
                rgb = (239, 240, 233)
            result_px[x, y] = rgb + (255,)
    result.putalpha(ImageChops.lighter(visible_mask, hidden_mask))
    return result


def build_expanded_sleeve(old_complete: Image.Image, visible: Image.Image, reference: Image.Image) -> Image.Image:
    """Use the other sleeve only as a row-width/arc reference, never as pixels."""
    reflected = ImageOps.mirror(reference)
    out = old_complete.copy()
    ref_px = reflected.load()
    old_px = old_complete.load()
    visible_px = visible.load()
    for y in range(228, 399):
        ref_xs = [x for x in range(W) if ref_px[x, y] > 0]
        old_xs = [x for x in range(W) if old_px[x, y] > 0]
        if not ref_xs or not old_xs:
            continue
        # Scale the reference width into a conservative hidden inner-panel
        # extension. The target's original outer edge and visible pixels stay
        # fixed; only the torso-side hidden edge grows.
        extra = max(4, round(len(ref_xs) * 0.42))
        right = min(W - 1, max(old_xs) + extra)
        left = max(old_xs)
        for x in range(left, right + 1):
            if visible_px[x, y] == 0:
                out.putpixel((x, y), 255)
    return out


def main() -> None:
    v14 = verify_v14()
    if not v14["pass"]:
        raise RuntimeError("V14 freeze verification failed.")
    v22_report = json.loads(V22_REPORT.read_text(encoding="utf-8"))
    if v22_report["defaultVisibleSourceRgbDifferencePixels"] != 0:
        raise RuntimeError("V22 is not source-consistent.")
    source = Image.open(SOURCE).convert("RGB")
    reference = Image.open(REFERENCE).convert("RGBA").getchannel("A")
    reflected = ImageOps.mirror(reference)
    visible = {name: alpha(V22 / "masks/visible" / f"{name}.png") for name in LAYERS}
    old_complete = {name: alpha(V22 / "masks/complete" / f"{name}.png") for name in LAYERS}
    old_materials = {
        name: Image.open(V22 / "materials" / f"{name}.png").convert("RGBA")
        for name in LAYERS
    }
    new_complete = dict(old_complete)
    new_complete["sleeve"] = build_expanded_sleeve(
        old_complete["sleeve"], visible["sleeve"], reference
    )
    new_hidden = {
        name: ImageChops.subtract(new_complete[name], visible[name]) for name in LAYERS
    }
    added = ImageChops.subtract(new_complete["sleeve"], old_complete["sleeve"])
    materials = dict(old_materials)
    materials["sleeve"] = fill_clean_sleeve(
        old_materials["sleeve"],
        visible["sleeve"],
        new_hidden["sleeve"],
        source,
    )
    for name in LAYERS:
        MATERIALS.mkdir(parents=True, exist_ok=True)
        MASKS.mkdir(parents=True, exist_ok=True)
        materials[name].save(MATERIALS / f"{name}.png")
        save_alpha(MASKS / "visible" / f"{name}.png", visible[name])
        save_alpha(MASKS / "complete" / f"{name}.png", new_complete[name])
        save_alpha(MASKS / "hidden" / f"{name}.png", new_hidden[name])

    # Default visible proof: the added panel is hidden-only, so the source
    # visible union remains identical.
    union = Image.new("L", (W, H), 0)
    for channel in visible.values():
        union = ImageChops.lighter(union, channel)
    default = Image.new("RGBA", (W, H), (248, 248, 248, 255))
    for name in ("upper_arm", "whole_hand", "forearm_bracelet", "sleeve"):
        default.alpha_composite(materials[name])
    default = default.convert("RGB")
    visible_difference = sum(
        default.getpixel((x, y)) != source.getpixel((x, y))
        for y in range(H)
        for x in range(W)
        if union.getpixel((x, y)) > 0
    )
    added_pixels = sum(value > 0 for value in added.getdata())

    old_sleeve = checker((W, H))
    old_sleeve.alpha_composite(tinted(old_complete["sleeve"], COLORS["sleeve"]))
    new_sleeve = checker((W, H))
    new_sleeve.alpha_composite(tinted(new_complete["sleeve"], COLORS["sleeve"]))
    reference_panel = checker((W, H))
    reference_panel.alpha_composite(tinted(reflected, (68, 184, 190), 220))
    reference_panel.alpha_composite(tinted(new_complete["sleeve"], COLORS["sleeve"], 80))
    old_texture = checker((W, H))
    old_texture.alpha_composite(old_materials["sleeve"])
    new_texture = checker((W, H))
    new_texture.alpha_composite(materials["sleeve"])
    xray = checker((W, H))
    xray.alpha_composite(tinted(new_complete["sleeve"], COLORS["sleeve"], 220))
    xray.alpha_composite(tinted(new_complete["upper_arm"], COLORS["upper_arm"], 255))

    board = Image.new("RGB", (2160, 1160), (239, 242, 247))
    draw = ImageDraw.Draw(board)
    draw.text((42, 24), "小星 V23｜参考另一侧袖窿结构的补全候选", font=font(39, True), fill=(24, 31, 43))
    draw.text(
        (45, 80),
        "参照只用于宽度剖面与袖窿弧线；纹理仍来自当前袖子原稿，不镜像另一侧像素。",
        font=font(22),
        fill=(70, 80, 96),
    )
    panels = [
        ("V22 当前完整色块", old_sleeve, True),
        ("结构参照叠加\n青=另一侧宽度剖面", reference_panel, True),
        ("V23 扩展后完整色块", new_sleeve, True),
        ("V22 原袖纹理", old_texture, False),
        ("V23 补全袖纹理", new_texture, False),
        ("最终透视\n蓝=袖子 / 橙=上臂", xray, True),
    ]
    for index, (label, image, nearest) in enumerate(panels):
        x = 40 + index * 350
        board.paste(crop(image, (310, 780), nearest).convert("RGB"), (x, 140))
        draw.multiline_text((x, 940), label, font=font(19, True), fill=(42, 51, 65), spacing=4)

    draw.rounded_rectangle((40, 980, 2115, 1130), radius=18, fill=(255, 255, 255), outline=(196, 204, 218), width=2)
    draw.text((68, 1005), "工程核验", font=font(26, True), fill=(31, 39, 52))
    draw.text(
        (70, 1050),
        f"V14 冻结 {v14['matched']}/{v14['total']}；新增隐藏袖子 {added_pixels}px；"
        f"默认可见源图差异 {visible_difference}px；可见袖子像素未改。",
        font=font(18),
        fill=(62, 71, 86),
    )
    draw.text(
        (70, 1082),
        "停止点：请只判断袖子内侧衣片是否补足、袖窿弧线是否自然、是否再次覆盖原图或带入头发。",
        font=font(18),
        fill=(62, 71, 86),
    )
    QA.mkdir(parents=True, exist_ok=True)
    board.save(BOARD)

    report = {
        "schemaVersion": 1,
        "status": "engineering_pass_pending_user_visual_approval",
        "scope": "reference-guided sleeve inner-panel completion only",
        "v14Integrity": v14,
        "reference": {
            "path": "model/working-v8/body-original-pixel/04_sleeve_screen_right.png",
            "use": "row-width and armhole-arc reference only; no mirrored texture pixels",
        },
        "repair": {
            "addedHiddenSleevePixels": added_pixels,
            "visibleSleeveUnchanged": True,
            "defaultVisibleSourceRgbDifferencePixels": visible_difference,
        },
        "reviewBoard": BOARD.relative_to(STAGE).as_posix(),
        "notCreated": ["mesh", "nodes", "continuous motion", "Physics", "Runtime"],
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
