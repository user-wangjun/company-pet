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
QA = STAGE / "qa"
AUDIT = STAGE / "audit"
MATERIALS = STAGE / "materials"
MASKS = STAGE / "masks"
BOARD = QA / "V20-ARMHOLE-ANATOMY-USER-REVIEW.zh-CN.png"
REPORT = AUDIT / "v20-armhole-anatomy-repair-report.json"

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


def alpha(root: Path, group: str, name: str) -> Image.Image:
    return Image.open(root / "corrected-masks" / group / f"{name}.png").convert("RGBA").getchannel("A")


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


def capsule_mask(shoulder=(176.0, 257.0), elbow=(153.0, 411.0)) -> Image.Image:
    channel = Image.new("L", (W, H), 0)
    pixels = channel.load()
    sx, sy = shoulder
    ex, ey = elbow
    dx, dy = ex - sx, ey - sy
    length2 = dx * dx + dy * dy
    for y in range(max(0, int(sy - 28)), min(H, int(ey + 28))):
        for x in range(max(0, int(sx - 32)), min(W, int(sx + 32))):
            t = ((x - sx) * dx + (y - sy) * dy) / length2
            t = max(0.0, min(1.0, t))
            cx, cy = sx + t * dx, sy + t * dy
            radius = 25.0 - 8.0 * t - 1.5 * max(0.0, t - 0.72)
            # Keep the repair behind the sleeve; the original visible skin
            # below the cuff remains byte-for-byte unchanged.
            if y <= 386 and (x - cx) ** 2 + (y - cy) ** 2 <= radius * radius:
                pixels[x, y] = 255
    return channel


def main() -> None:
    integrity = {
        "v12": verify(V12, V12_MANIFEST),
        "v14": verify(V14, V14_MANIFEST),
    }
    if not all(item["pass"] for item in integrity.values()):
        raise RuntimeError("Frozen upstream input verification failed.")

    source = Image.open(SOURCE).convert("RGB")
    old_complete = {name: alpha(V14, "complete", name) for name in LAYERS}
    visible = {name: alpha(V14, "visible", name) for name in LAYERS}
    old_materials = {
        name: Image.open(V14 / "materials" / f"{name}.png").convert("RGBA")
        for name in LAYERS
    }

    # The sleeve complete mask is already source-registered and has no missing
    # visible pixels. Keep it unchanged. Widen only the hidden shoulder cap and
    # taper the upper arm toward the approved elbow; never touch visible skin.
    capsule = capsule_mask()
    allowed_hidden = ImageChops.lighter(old_complete["sleeve"], old_complete["upper_arm"])
    repair = ImageChops.multiply(capsule, allowed_hidden)
    repair = ImageChops.subtract(repair, visible["upper_arm"])
    repair = ImageChops.subtract(repair, old_complete["upper_arm"])
    new_complete = dict(old_complete)
    new_complete["upper_arm"] = ImageChops.lighter(old_complete["upper_arm"], repair)
    hidden = {
        name: ImageChops.subtract(new_complete[name], visible[name]) for name in LAYERS
    }
    added_pixels = sum(value > 0 for value in repair.getdata())

    materials = {}
    for name in LAYERS:
        material = old_materials[name].copy()
        if name == "upper_arm":
            # Continue the existing skin gradient into only the newly added
            # hidden pixels. Sample the nearest valid old row, then add a soft
            # cylindrical edge falloff so the shoulder reads as volume rather
            # than a stretched rectangle.
            old_px = old_materials[name].load()
            new_px = material.load()
            repair_px = repair.load()
            valid_rows = [
                y
                for y in range(H)
                if any(old_complete[name].getpixel((x, y)) > 0 for x in range(W))
            ]
            for y in range(H):
                new_row = [x for x in range(W) if new_complete[name].getpixel((x, y)) > 0]
                if not new_row or not any(repair_px[x, y] > 0 for x in new_row):
                    continue
                source_y = min(valid_rows, key=lambda candidate: abs(candidate - y))
                source_row = [
                    x for x in range(W) if old_complete[name].getpixel((x, source_y)) > 0
                ]
                interior = source_row[2:-2] or source_row
                base = tuple(
                    round(sum(old_px[x, source_y][channel] for x in interior) / len(interior))
                    for channel in range(3)
                )
                left, right = min(new_row), max(new_row)
                for x in range(W):
                    if repair_px[x, y] > 0:
                        u = (x - left) / max(1, right - left)
                        shade = round(4 - 13 * abs(2 * u - 1))
                        new_px[x, y] = tuple(
                            max(0, min(255, value + shade)) for value in base
                        ) + (255,)
        material.putalpha(new_complete[name])
        materials[name] = material
        MATERIALS.mkdir(parents=True, exist_ok=True)
        material.save(MATERIALS / f"{name}.png")
        save_alpha(MASKS / "visible" / f"{name}.png", visible[name])
        save_alpha(MASKS / "complete" / f"{name}.png", new_complete[name])
        save_alpha(MASKS / "hidden" / f"{name}.png", hidden[name])

    default = compose(materials)
    union = Image.new("L", (W, H), 0)
    for channel in visible.values():
        union = ImageChops.lighter(union, channel)
    default_difference = sum(
        default.convert("RGB").getpixel((x, y)) != source.getpixel((x, y))
        for y in range(H)
        for x in range(W)
        if union.getpixel((x, y)) > 0
    )
    sleeve_visible_missing = sum(
        value > 0
        for value in ImageChops.subtract(visible["sleeve"], new_complete["sleeve"]).getdata()
    )

    # Review panels: solid complete sleeve, old vs repaired upper arm, and a
    # default composite that must retain the approved visible pixels.
    old_upper = checker((W, H))
    old_upper.alpha_composite(old_materials["upper_arm"])
    new_upper = checker((W, H))
    new_upper.alpha_composite(materials["upper_arm"])
    sleeve_solid = checker((W, H))
    sleeve_solid.alpha_composite(tinted(new_complete["sleeve"], COLORS["sleeve"]))
    xray = checker((W, H))
    xray.alpha_composite(tinted(new_complete["upper_arm"], COLORS["upper_arm"]))
    xray.alpha_composite(tinted(new_complete["sleeve"], COLORS["sleeve"], 230))

    board = Image.new("RGB", (1900, 1040), (239, 242, 247))
    draw = ImageDraw.Draw(board)
    draw.text((42, 24), "小星 V20｜袖子完整轮廓与上臂体态修正", font=font(38, True), fill=(24, 31, 43))
    draw.text(
        (45, 78),
        "袖子保持原稿注册形状；只扩充被袖子遮住的肩部上臂，并向肘部渐收，默认可见皮肤不改。",
        font=font(22),
        fill=(70, 80, 96),
    )
    panels = [
        ("锁定原稿", source.convert("RGBA"), False),
        ("V14 默认合成", compose(old_materials), False),
        ("袖子完整色块\n不再透视混色", sleeve_solid, True),
        ("上臂旧补全\n等宽直条", old_upper, False),
        ("上臂候选\n肩宽→肱部→肘收束", new_upper, False),
        ("候选透视\n橙=上臂，蓝=袖子", xray, True),
    ]
    for index, (label, image, nearest) in enumerate(panels):
        x = 40 + index * 305
        board.paste(crop(image, nearest=nearest).convert("RGB"), (x, 130))
        draw.multiline_text((x, 945), label, font=font(19, True), fill=(42, 51, 65), spacing=3)

    draw.rounded_rectangle((40, 980, 1860, 1028), radius=12, fill=(255, 241, 207))
    draw.text(
        (65, 992),
        f"工程核验：V12 {integrity['v12']['matched']}/{integrity['v12']['total']}；"
        f"V14 {integrity['v14']['matched']}/{integrity['v14']['total']}；"
        f"新增隐藏上臂 {added_pixels}px；默认可见差异 {default_difference}px。",
        font=font(19, True),
        fill=(132, 81, 0),
    )
    QA.mkdir(parents=True, exist_ok=True)
    board.save(BOARD)

    report = {
        "schemaVersion": 1,
        "status": "candidate_rejected_material_boundary_insufficient",
        "scope": "rejected sleeve/upper-arm repair candidate; source boundary insufficient",
        "upstreamIntegrity": integrity,
        "sleeve": {
            "sourceVisibleCoverageMissingPixels": sleeve_visible_missing,
            "completeMaskUnchanged": True,
            "hiddenPixels": sum(value > 0 for value in hidden["sleeve"].getdata()),
        },
        "upperArm": {
            "addedHiddenPixels": added_pixels,
            "visibleMaskUnchanged": True,
            "shoulderElbowWrist": [[176.0, 257.0], [153.0, 411.0], [115.0, 529.0]],
        },
        "defaultVisibleSourceRgbDifferencePixels": default_difference,
        "reviewBoard": BOARD.relative_to(STAGE).as_posix(),
        "notCreated": ["mesh", "nodes", "continuous motion", "Physics", "Runtime"],
        "rejection": {
            "reason": "sleeve layer includes unresolved cuff skin and torso-side hidden shirt area",
            "earliestMissingEvidence": "source-registered sleeve-to-torso armhole boundary under occlusion",
        },
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
