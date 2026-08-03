from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
VALIDATION = WORKBENCH / "validation"
V12 = VALIDATION / "arm-chain-screen-left-v12-body-geometry"
V13 = VALIDATION / "arm-chain-screen-left-v13-material-separation"
V14 = VALIDATION / "arm-chain-screen-left-v14-complete-textures"
SOURCE = WORKBENCH / "source/masters/front-color-source-exact-after-reset.png"
V12_MANIFEST = V12 / "audit/v12-body-geometry-freeze-manifest-2026-07-27.json"
V13_MANIFEST = V13 / "audit/v13-material-boundary-freeze-manifest-2026-07-27.json"
MATERIALS = STAGE / "materials"
MASKS = STAGE / "masks"
QA = STAGE / "qa"
AUDIT = STAGE / "audit"
BOARD = QA / "V21-AUTOMATED-MATERIAL-USER-REVIEW.zh-CN.png"
REPORT = AUDIT / "v21-automated-material-rebuild-report.json"

LAYERS = ("sleeve", "upper_arm", "forearm_bracelet", "whole_hand")
DRAW_ORDER = ("upper_arm", "whole_hand", "forearm_bracelet", "sleeve")
COLORS = {
    "sleeve": (67, 119, 190),
    "upper_arm": (236, 148, 51),
    "forearm_bracelet": (62, 165, 124),
    "whole_hand": (215, 78, 118),
}
W, H = 512, 1086
CROP = (62, 205, 215, 635)


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


def crop(image: Image.Image, size=(300, 805), nearest=False) -> Image.Image:
    method = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
    return image.crop(CROP).resize(size, method)


def fitted_sleeve_complete(visible: Image.Image) -> Image.Image:
    """Add only a narrow inferred sleeve-under-torso wedge.

    The inner boundary is fitted from the visible right edge, shoulder pivot,
    and inner cuff. It deliberately stops before the torso-side shirt region.
    """
    complete = visible.copy()
    pixels = complete.load()
    for y in range(228, 391):
        xs = [x for x in range(W) if visible.getpixel((x, y)) > 0]
        if xs:
            visible_right = max(xs)
        else:
            # Small shoulder cap before the first source-visible row.
            visible_right = round(169 + (y - 228) * 0.08)
        if y <= 257:
            hidden_right = round(176 + 5 * (y - 228) / 29)
        else:
            u = (y - 257) / (390 - 257)
            # Cubic ease from shoulder to the source-visible inner cuff.
            eased = u * u * (3 - 2 * u)
            hidden_right = round(181 * (1 - eased) + 150 * eased)
        for x in range(visible_right + 1, max(visible_right + 1, hidden_right + 1)):
            pixels[x, y] = 255
    return complete


def anatomical_upper_complete(visible: Image.Image) -> Image.Image:
    shoulder = (176.0, 257.0)
    elbow = (153.0, 411.0)
    sx, sy = shoulder
    ex, ey = elbow
    dx, dy = ex - sx, ey - sy
    length2 = dx * dx + dy * dy
    complete = visible.copy()
    pixels = complete.load()
    for y in range(232, 431):
        for x in range(125, 205):
            t = ((x - sx) * dx + (y - sy) * dy) / length2
            t = max(0.0, min(1.0, t))
            cx, cy = sx + t * dx, sy + t * dy
            # Rounded shoulder cap, natural biceps fullness, elbow taper.
            radius = 22.5 - 7.5 * t + 2.0 * math.sin(math.pi * t)
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius:
                pixels[x, y] = 255
    return complete


def source_visible_material(source: Image.Image, visible: Image.Image) -> Image.Image:
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    src = source.load()
    out = image.load()
    mask = visible.load()
    for y in range(H):
        for x in range(W):
            if mask[x, y] > 0:
                out[x, y] = src[x, y] + (255,)
    return image


def extend_sleeve_texture(
    source: Image.Image, visible: Image.Image, complete: Image.Image
) -> Image.Image:
    image = source_visible_material(source, visible)
    out = image.load()
    src = source.load()
    visible_rows: dict[int, int] = {}
    for y in range(H):
        xs = [x for x in range(W) if visible.getpixel((x, y)) > 0]
        if xs:
            visible_rows[y] = max(xs)
    available_rows = sorted(visible_rows)
    for y in range(H):
        for x in range(W):
            if complete.getpixel((x, y)) == 0 or visible.getpixel((x, y)) > 0:
                continue
            nearest_y = min(available_rows, key=lambda row: abs(row - y))
            sample_x = visible_rows[nearest_y]
            r, g, b = src[sample_x, nearest_y]
            distance = max(0, x - sample_x)
            fade = min(8, round(distance * 0.45))
            out[x, y] = (min(255, r + fade), min(255, g + fade), min(255, b + fade), 255)
    image.putalpha(complete)
    return image


def extend_upper_texture(
    source: Image.Image, visible: Image.Image, complete: Image.Image
) -> Image.Image:
    image = source_visible_material(source, visible)
    source_values = [
        source.getpixel((x, y))
        for y in range(H)
        for x in range(W)
        if visible.getpixel((x, y)) > 0
        and sum(source.getpixel((x, y))) > 520
    ]
    base = tuple(round(statistics.median(value[i] for value in source_values)) for i in range(3))
    shoulder = (176.0, 257.0)
    elbow = (153.0, 411.0)
    sx, sy = shoulder
    ex, ey = elbow
    dx, dy = ex - sx, ey - sy
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    out = image.load()
    for y in range(H):
        for x in range(W):
            if complete.getpixel((x, y)) == 0 or visible.getpixel((x, y)) > 0:
                continue
            lateral = (x - sx) * px + (y - sy) * py
            shade = -round(0.10 * abs(lateral)) + (2 if lateral > 0 else -2)
            out[x, y] = tuple(max(0, min(255, channel + shade)) for channel in base) + (255,)
    # Continue a restrained skin outline around the newly completed anatomy.
    eroded = complete.filter(ImageFilter.MinFilter(3))
    boundary = ImageChops.subtract(complete, eroded)
    for y in range(H):
        for x in range(W):
            if boundary.getpixel((x, y)) > 0 and visible.getpixel((x, y)) == 0:
                r, g, b, _ = out[x, y]
                out[x, y] = (max(0, r - 38), max(0, g - 45), max(0, b - 44), 255)
    image.putalpha(complete)
    return image


def main() -> None:
    integrity = {
        "v12": verify(V12, V12_MANIFEST),
        "v13": verify(V13, V13_MANIFEST),
    }
    if not all(item["pass"] for item in integrity.values()):
        raise RuntimeError("Frozen upstream input verification failed.")

    source = Image.open(SOURCE).convert("RGB")
    visible = {
        name: alpha(V13 / "masks/visible" / f"{name}.png") for name in LAYERS
    }
    complete = {
        "sleeve": fitted_sleeve_complete(visible["sleeve"]),
        "upper_arm": anatomical_upper_complete(visible["upper_arm"]),
        "forearm_bracelet": alpha(V14 / "corrected-masks/complete/forearm_bracelet.png"),
        "whole_hand": alpha(V14 / "corrected-masks/complete/whole_hand.png"),
    }
    hidden = {
        name: ImageChops.subtract(complete[name], visible[name]) for name in LAYERS
    }

    materials = {
        "sleeve": extend_sleeve_texture(source, visible["sleeve"], complete["sleeve"]),
        "upper_arm": extend_upper_texture(source, visible["upper_arm"], complete["upper_arm"]),
        "forearm_bracelet": Image.open(V14 / "materials/forearm_bracelet.png").convert("RGBA"),
        "whole_hand": Image.open(V14 / "materials/whole_hand.png").convert("RGBA"),
    }
    for name in LAYERS:
        if name in ("forearm_bracelet", "whole_hand"):
            materials[name].putalpha(complete[name])
        MATERIALS.mkdir(parents=True, exist_ok=True)
        materials[name].save(MATERIALS / f"{name}.png")
        save_alpha(MASKS / "visible" / f"{name}.png", visible[name])
        save_alpha(MASKS / "complete" / f"{name}.png", complete[name])
        save_alpha(MASKS / "hidden" / f"{name}.png", hidden[name])

    # Visible-only recomposition is the correct material gate: torso occlusion
    # is external and must never be smuggled into the sleeve layer.
    visible_composite = Image.new("RGBA", (W, H), (248, 248, 248, 255))
    for name in DRAW_ORDER:
        part = materials[name].copy()
        part.putalpha(visible[name])
        visible_composite.alpha_composite(part)
    union = Image.new("L", (W, H), 0)
    for channel in visible.values():
        union = ImageChops.lighter(union, channel)
    source_difference = sum(
        visible_composite.convert("RGB").getpixel((x, y)) != source.getpixel((x, y))
        for y in range(H)
        for x in range(W)
        if union.getpixel((x, y)) > 0
    )

    blocks = checker((W, H))
    for name in DRAW_ORDER:
        blocks.alpha_composite(tinted(visible[name], COLORS[name]))
    sleeve_isolated = checker((W, H))
    sleeve_isolated.alpha_composite(materials["sleeve"])
    upper_isolated = checker((W, H))
    upper_isolated.alpha_composite(materials["upper_arm"])
    structure = checker((W, H))
    structure.alpha_composite(tinted(complete["upper_arm"], COLORS["upper_arm"]))
    # Show sleeve as outline-like translucent cloth without hiding anatomy.
    structure.alpha_composite(tinted(complete["sleeve"], COLORS["sleeve"], 95))
    structure.alpha_composite(tinted(visible["sleeve"], COLORS["sleeve"], 210))

    board = Image.new("RGB", (1900, 1060), (239, 242, 247))
    draw = ImageDraw.Draw(board)
    draw.text((42, 24), "小星 V21｜自动重建袖子与上臂材料", font=font(38, True), fill=(24, 31, 43))
    draw.text(
        (45, 79),
        "衣身不再并入袖子；皮肤不再并入袖口。隐藏袖窿由肩点、可见内缘和袖口自动拟合。",
        font=font(22),
        fill=(70, 80, 96),
    )
    panels = [
        ("锁定原稿", source.convert("RGBA"), False),
        ("可见层拼接", visible_composite, False),
        ("可见归属色块", blocks, True),
        ("袖子独立纹理\n仅袖子，不含衣身/皮肤", sleeve_isolated, False),
        ("上臂独立纹理\n肩宽、肱部、肘收束", upper_isolated, False),
        ("完整结构透视\n橙=上臂，蓝=袖子", structure, True),
    ]
    for index, (label, image, nearest) in enumerate(panels):
        x = 40 + index * 305
        board.paste(crop(image, nearest=nearest).convert("RGB"), (x, 130))
        draw.multiline_text((x, 945), label, font=font(18, True), fill=(42, 51, 65), spacing=3)

    sleeve_hidden_pixels = sum(value > 0 for value in hidden["sleeve"].getdata())
    upper_hidden_pixels = sum(value > 0 for value in hidden["upper_arm"].getdata())
    draw.rounded_rectangle((40, 995, 1860, 1045), radius=12, fill=(255, 241, 207))
    draw.text(
        (65, 1007),
        f"工程核验：V12 {integrity['v12']['matched']}/{integrity['v12']['total']}；"
        f"V13 {integrity['v13']['matched']}/{integrity['v13']['total']}；"
        f"袖子隐藏 {sleeve_hidden_pixels}px；上臂隐藏 {upper_hidden_pixels}px；"
        f"可见拼接差异 {source_difference}px。",
        font=font(18, True),
        fill=(132, 81, 0),
    )
    QA.mkdir(parents=True, exist_ok=True)
    board.save(BOARD)

    report = {
        "schemaVersion": 1,
        "status": "engineering_pass_pending_user_visual_approval",
        "scope": "automatic sleeve-only armhole fit and anatomical upper-arm material rebuild",
        "upstreamIntegrity": integrity,
        "automation": {
            "sleeveBoundaryInputs": [
                "source-visible sleeve right edge",
                "approved shoulder pivot",
                "source-visible inner cuff",
            ],
            "torsoPixelsIncludedInSleeve": False,
            "skinCuffBandIncludedInSleeve": False,
            "directMirrorUsed": False,
        },
        "sleeve": {
            "visiblePixels": sum(value > 0 for value in visible["sleeve"].getdata()),
            "hiddenPixels": sleeve_hidden_pixels,
        },
        "upperArm": {
            "visiblePixels": sum(value > 0 for value in visible["upper_arm"].getdata()),
            "hiddenPixels": upper_hidden_pixels,
            "geometry": "rounded shoulder cap, biceps fullness, elbow taper",
        },
        "visibleSourceRgbDifferencePixels": source_difference,
        "reviewBoard": BOARD.relative_to(STAGE).as_posix(),
        "notCreated": ["mesh", "nodes", "continuous motion", "Physics", "Runtime"],
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
