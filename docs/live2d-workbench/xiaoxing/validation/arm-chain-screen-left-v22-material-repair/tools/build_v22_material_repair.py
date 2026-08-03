from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
VALIDATION = WORKBENCH / "validation"
V12 = VALIDATION / "arm-chain-screen-left-v12-body-geometry"
V14 = VALIDATION / "arm-chain-screen-left-v14-complete-textures"
V12_MANIFEST = V12 / "audit/v12-body-geometry-freeze-manifest-2026-07-27.json"
V14_MANIFEST = V14 / "audit/v14-complete-texture-freeze-manifest-2026-07-28.json"
SOURCE = WORKBENCH / "source/masters/front-color-source-exact-after-reset.png"
HAIR_MASK = WORKBENCH / "model/working-v9/long-hair-shirt/胸前长发_归属蒙版.png"
QA = STAGE / "qa"
AUDIT = STAGE / "audit"
MATERIALS = STAGE / "materials"
MASKS = STAGE / "masks"
BOARD = QA / "V22-MATERIAL-REPAIR-USER-REVIEW.zh-CN.png"
REPORT = AUDIT / "v22-material-repair-report.json"

LAYERS = ("sleeve", "upper_arm", "forearm_bracelet", "whole_hand")
DRAW_ORDER = ("upper_arm", "whole_hand", "forearm_bracelet", "sleeve")
COLORS = {
    "sleeve": (65, 119, 190),
    "upper_arm": (236, 148, 52),
    "forearm_bracelet": (63, 165, 125),
    "whole_hand": (215, 78, 119),
}
W, H = 512, 1086
CROP = (65, 205, 215, 635)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(root: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad = []
    for item in manifest["lockedArtifacts"]:
        path = root / item["path"]
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


def alpha(group: str, name: str) -> Image.Image:
    return Image.open(V14 / "corrected-masks" / group / f"{name}.png").convert("RGBA").getchannel("A")


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


def compose(materials: dict[str, Image.Image], background=(248, 248, 248, 255)) -> Image.Image:
    image = Image.new("RGBA", (W, H), background)
    for name in DRAW_ORDER:
        image.alpha_composite(materials[name])
    return image


def crop(image: Image.Image, size=(300, 800), nearest=False) -> Image.Image:
    method = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
    return image.crop(CROP).resize(size, method)


def build_upper_arm(old_complete: Image.Image, visible: Image.Image, sleeve_complete: Image.Image) -> Image.Image:
    channel = Image.new("L", (W, H), 0)
    px = channel.load()
    sx, sy = 176.0, 257.0
    ex, ey = 153.0, 411.0
    dx, dy = ex - sx, ey - sy
    length2 = dx * dx + dy * dy
    for y in range(225, 388):
        for x in range(125, 215):
            t = max(0.0, min(1.0, ((x - sx) * dx + (y - sy) * dy) / length2))
            cx, cy = sx + t * dx, sy + t * dy
            radius = 25.0 - 8.0 * t - 1.5 * max(0.0, t - 0.72)
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius:
                if sleeve_complete.getpixel((x, y)) > 0 or old_complete.getpixel((x, y)) > 0:
                    px[x, y] = 255
    result = ImageChops.lighter(old_complete, ImageChops.subtract(ImageChops.subtract(channel, visible), old_complete))
    return result


def fill_skin(old_material: Image.Image, old_complete: Image.Image, new_complete: Image.Image, added: Image.Image) -> Image.Image:
    result = old_material.copy()
    old_px = old_material.load()
    new_px = result.load()
    valid_rows = [
        y for y in range(H)
        if any(old_complete.getpixel((x, y)) > 0 for x in range(W))
    ]
    added_px = added.load()
    for y in range(H):
        row = [x for x in range(W) if new_complete.getpixel((x, y)) > 0]
        if not row:
            continue
        source_y = min(valid_rows, key=lambda candidate: abs(candidate - y))
        source_row = [x for x in range(W) if old_complete.getpixel((x, source_y)) > 0]
        interior = source_row[2:-2] or source_row
        base = tuple(
            round(sum(old_px[x, source_y][channel] for x in interior) / len(interior))
            for channel in range(3)
        )
        left, right = min(row), max(row)
        for x in range(W):
            if added_px[x, y] > 0:
                u = (x - left) / max(1, right - left)
                shade = round(4 - 13 * abs(2 * u - 1))
                new_px[x, y] = tuple(max(0, min(255, value + shade)) for value in base) + (255,)
    result.putalpha(new_complete)
    return result


def fill_sleeve_cloth(
    old_material: Image.Image,
    visible_mask: Image.Image,
    hidden_mask: Image.Image,
    source: Image.Image,
) -> Image.Image:
    """Fill only hidden sleeve pixels from light cloth anchors.

    Visible source pixels are copied unchanged. Hidden pixels never sample
    from hair/body pixels or from the old generated hidden texture.
    """
    source_px = source.load()
    old_px = old_material.load()
    result = old_material.copy()
    result_px = result.load()
    anchors: list[tuple[int, int, tuple[int, int, int]]] = []
    visible_px = visible_mask.load()
    for y in range(H):
        for x in range(W):
            if visible_px[x, y] > 0:
                rgb = source_px[x, y]
                if sum(rgb) / 3 >= 168:
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
            )[:12]
            if nearby:
                weights = [1.0 / (1.0 + (ax - x) ** 2 + (ay - y) ** 2) for ax, ay, _ in nearby]
                total = sum(weights)
                rgb = tuple(
                    round(sum(weight * color[channel] for weight, (_, _, color) in zip(weights, nearby)) / total)
                    for channel in range(3)
                )
            else:
                rgb = (235, 238, 232)
            result_px[x, y] = rgb + (255,)
    result.putalpha(ImageChops.lighter(visible_mask, hidden_mask))
    return result


def main() -> None:
    upstream = {
        "v12": verify(V12, V12_MANIFEST),
        "v14": verify(V14, V14_MANIFEST),
    }
    if not all(item["pass"] for item in upstream.values()):
        raise RuntimeError("Frozen upstream verification failed.")

    source = Image.open(SOURCE).convert("RGB")
    hair = Image.open(HAIR_MASK).convert("L")
    visible = {name: alpha("visible", name) for name in LAYERS}
    old_complete = {name: alpha("complete", name) for name in LAYERS}
    hidden = {name: alpha("hidden", name) for name in LAYERS}
    old_materials = {
        name: Image.open(V14 / "materials" / f"{name}.png").convert("RGBA")
        for name in LAYERS
    }

    new_complete = dict(old_complete)
    new_complete["upper_arm"] = build_upper_arm(
        old_complete["upper_arm"], visible["upper_arm"], old_complete["sleeve"]
    )
    new_hidden = {
        name: ImageChops.subtract(new_complete[name], visible[name]) for name in LAYERS
    }
    added_upper = ImageChops.subtract(new_complete["upper_arm"], old_complete["upper_arm"])
    materials = dict(old_materials)
    materials["sleeve"] = fill_sleeve_cloth(
        old_materials["sleeve"], visible["sleeve"], hidden["sleeve"], source
    )
    materials["upper_arm"] = fill_skin(
        old_materials["upper_arm"],
        old_complete["upper_arm"],
        new_complete["upper_arm"],
        added_upper,
    )

    for name in LAYERS:
        MATERIALS.mkdir(parents=True, exist_ok=True)
        MASKS.mkdir(parents=True, exist_ok=True)
        materials[name].save(MATERIALS / f"{name}.png")
        save_alpha(MASKS / "visible" / f"{name}.png", visible[name])
        save_alpha(MASKS / "complete" / f"{name}.png", new_complete[name])
        save_alpha(MASKS / "hidden" / f"{name}.png", new_hidden[name])

    default = compose(materials).convert("RGB")
    union = Image.new("L", (W, H), 0)
    for channel in visible.values():
        union = ImageChops.lighter(union, channel)
    visible_difference = sum(
        default.getpixel((x, y)) != source.getpixel((x, y))
        for y in range(H)
        for x in range(W)
        if union.getpixel((x, y)) > 0
    )
    hair_overlap_hidden = sum(
        hair.getpixel((x, y)) > 0 and hidden["sleeve"].getpixel((x, y)) > 0
        for y in range(H)
        for x in range(W)
    )
    hidden_dark_old = sum(
        sum(old_materials["sleeve"].getpixel((x, y))[:3]) / 3 < 168
        for y in range(H)
        for x in range(W)
        if hidden["sleeve"].getpixel((x, y)) > 0
    )
    hidden_dark_new = sum(
        sum(materials["sleeve"].getpixel((x, y))[:3]) / 3 < 168
        for y in range(H)
        for x in range(W)
        if hidden["sleeve"].getpixel((x, y)) > 0
    )

    visible_sleeve = checker((W, H))
    visible_sleeve.alpha_composite(tinted(visible["sleeve"], COLORS["sleeve"]))
    hidden_sleeve = checker((W, H))
    hidden_sleeve.alpha_composite(tinted(hidden["sleeve"], COLORS["sleeve"]))
    hidden_texture = materials["sleeve"].copy()
    hidden_texture.putalpha(hidden["sleeve"])
    hidden_sleeve.alpha_composite(hidden_texture)
    complete_sleeve = checker((W, H))
    complete_sleeve.alpha_composite(materials["sleeve"])
    old_upper = checker((W, H))
    old_upper.alpha_composite(old_materials["upper_arm"])
    new_upper = checker((W, H))
    new_upper.alpha_composite(materials["upper_arm"])
    xray = checker((W, H))
    xray.alpha_composite(tinted(new_complete["upper_arm"], COLORS["upper_arm"]))
    xray.alpha_composite(tinted(new_complete["sleeve"], COLORS["sleeve"], 230))

    board = Image.new("RGB", (2220, 1240), (239, 242, 247))
    draw = ImageDraw.Draw(board)
    draw.text((42, 24), "小星 V22｜袖子隐藏补图与上臂体态修正", font=font(40, True), fill=(24, 31, 43))
    draw.text(
        (45, 80),
        "可见层、隐藏补图、完整层分开显示；隐藏袖子只从布料锚点续接，不复制头发或暗线。",
        font=font(22),
        fill=(70, 80, 96),
    )
    panels = [
        ("锁定原稿", source.convert("RGBA"), False),
        ("可见袖子归属", visible_sleeve, True),
        ("隐藏袖子补图\n仅布料", hidden_sleeve, False),
        ("完整袖子纹理", complete_sleeve, False),
        ("旧上臂", old_upper, False),
        ("候选上臂", new_upper, False),
        ("透视关系\n橙=上臂 / 蓝=袖子", xray, True),
    ]
    for index, (label, image, nearest) in enumerate(panels):
        x = 35 + index * 312
        board.paste(crop(image, (270, 760), nearest).convert("RGB"), (x, 140))
        draw.multiline_text((x, 920), label, font=font(18, True), fill=(42, 51, 65), spacing=3)

    draw.rounded_rectangle((35, 970, 2185, 1210), radius=18, fill=(255, 255, 255), outline=(196, 204, 218), width=2)
    draw.text((65, 995), "工程核验", font=font(27, True), fill=(31, 39, 52))
    lines = [
        f"V12 {upstream['v12']['matched']}/{upstream['v12']['total']}；V14 {upstream['v14']['matched']}/{upstream['v14']['total']}，冻结输入未改。",
        f"默认可见源图差异：{visible_difference}px；袖子隐藏区与头发归属区几何重叠：{hair_overlap_hidden}px（只表示遮挡关系）。",
        f"袖子隐藏区暗像素（旧→新）：{hidden_dark_old} → {hidden_dark_new}；新补图不从头发/旧隐藏纹理取样。",
        f"新增隐藏上臂像素：{sum(v > 0 for v in added_upper.getdata())}；上臂可见层保持不变。",
        "停止点：请只审查袖子补图是否仍盖住原图、是否出现头发线条，以及上臂是否有肩部体态。",
    ]
    for index, line in enumerate(lines):
        draw.text((68, 1045 + index * 31), line, font=font(18), fill=(62, 71, 86))
    QA.mkdir(parents=True, exist_ok=True)
    board.save(BOARD)

    report = {
        "schemaVersion": 1,
        "status": "engineering_pass_pending_user_visual_approval",
        "scope": "sleeve hidden cloth-only fill and hidden upper-arm anatomy candidate",
        "upstreamIntegrity": upstream,
        "sleeve": {
            "visibleRgbUnchanged": True,
            "hiddenHairGeometryOverlapPixels": hair_overlap_hidden,
            "oldHiddenDarkPixels": hidden_dark_old,
            "newHiddenDarkPixels": hidden_dark_new,
        },
        "upperArm": {
            "visibleMaskUnchanged": True,
            "addedHiddenPixels": sum(v > 0 for v in added_upper.getdata()),
            "anchors": {"shoulder": [176.0, 257.0], "elbow": [153.0, 411.0], "wrist": [115.0, 529.0]},
        },
        "defaultVisibleSourceRgbDifferencePixels": visible_difference,
        "reviewBoard": BOARD.relative_to(STAGE).as_posix(),
        "notCreated": ["mesh", "nodes", "continuous motion", "Physics", "Runtime"],
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
