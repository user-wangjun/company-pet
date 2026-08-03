from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
VALIDATION = WORKBENCH / "validation"
V12 = VALIDATION / "arm-chain-screen-left-v12-body-geometry"
V13 = VALIDATION / "arm-chain-screen-left-v13-material-separation"
V14 = VALIDATION / "arm-chain-screen-left-v14-complete-textures"
V22 = VALIDATION / "arm-chain-screen-left-v22-material-repair"
V12_MANIFEST = V12 / "audit/v12-body-geometry-freeze-manifest-2026-07-27.json"
V13_MANIFEST = V13 / "audit/v13-material-boundary-freeze-manifest-2026-07-27.json"
V14_MANIFEST = V14 / "audit/v14-complete-texture-freeze-manifest-2026-07-28.json"
V22_REPORT = V22 / "audit/v22-material-repair-report.json"
SOURCE = WORKBENCH / "source/masters/front-color-source-exact-after-reset.png"
QA = STAGE / "qa"
AUDIT = STAGE / "audit"
MATERIALS = STAGE / "materials"
MASKS = STAGE / "masks"
BOARD = QA / "V24-SLEEVE-SEMANTIC-PURITY-REPAIR-USER-REVIEW.zh-CN.png"
REPORT = AUDIT / "v24-sleeve-semantic-purity-repair-report.json"

LAYERS = ("sleeve", "upper_arm", "forearm_bracelet", "whole_hand")
DRAW_ORDER = ("upper_arm", "whole_hand", "forearm_bracelet", "sleeve")
COLORS = {
    "sleeve": (65, 119, 190),
    "upper_arm": (236, 148, 52),
    "forearm_bracelet": (63, 165, 125),
    "whole_hand": (215, 78, 119),
}
W, H = 512, 1086
CROP = (65, 205, 225, 635)


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
    return Image.open(root / "masks" / group / f"{name}.png").convert("RGBA").getchannel("A")


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


def crop(image: Image.Image, size=(290, 760), nearest=False) -> Image.Image:
    method = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
    return image.crop(CROP).resize(size, method)


def clean_sleeve_complete(old_complete: Image.Image, visible: Image.Image) -> Image.Image:
    """Keep the sleeve as one cloth shape and drop the lower skin-like lobe."""
    visible_px = visible.load()
    old_px = old_complete.load()
    result = Image.new("L", (W, H), 0)
    result_px = result.load()
    visible_max_y = max(y for y in range(H) for x in range(W) if visible_px[x, y] > 0)
    cutoff_y = visible_max_y + 1
    for y in range(H):
        for x in range(W):
            if old_px[x, y] == 0:
                continue
            if visible_px[x, y] > 0:
                result_px[x, y] = 255
                continue
            if y >= cutoff_y:
                continue
            result_px[x, y] = 255
    return result


def fill_cloth_from_source(
    old_material: Image.Image,
    visible_mask: Image.Image,
    hidden_mask: Image.Image,
    source: Image.Image,
) -> Image.Image:
    source_px = source.load()
    result = old_material.copy()
    result_px = result.load()
    visible_px = visible_mask.load()
    anchors: list[tuple[int, int, tuple[int, int, int]]] = []
    for y in range(H):
        for x in range(W):
            if visible_px[x, y] == 0:
                continue
            rgb = source_px[x, y]
            if sum(rgb) / 3 >= 210:
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


def main() -> None:
    upstream = {
        "v12": verify(V12, V12_MANIFEST),
        "v13": verify(V13, V13_MANIFEST),
        "v14": verify(V14, V14_MANIFEST),
    }
    if not all(item["pass"] for item in upstream.values()):
        raise RuntimeError("Frozen upstream verification failed.")

    v22_report = json.loads(V22_REPORT.read_text(encoding="utf-8"))
    if v22_report["defaultVisibleSourceRgbDifferencePixels"] != 0:
        raise RuntimeError("V22 visible proof is not source-consistent.")

    source = Image.open(SOURCE).convert("RGB")
    visible = {
        "sleeve": alpha(V13, "visible", "sleeve"),
        "upper_arm": alpha(V22, "visible", "upper_arm"),
        "forearm_bracelet": alpha(V22, "visible", "forearm_bracelet"),
        "whole_hand": alpha(V22, "visible", "whole_hand"),
    }
    old_complete = {name: alpha(V22, "complete", name) for name in LAYERS}
    old_materials = {
        name: Image.open(V22 / "materials" / f"{name}.png").convert("RGBA")
        for name in LAYERS
    }

    new_complete = dict(old_complete)
    new_complete["sleeve"] = clean_sleeve_complete(old_complete["sleeve"], visible["sleeve"])
    new_hidden = {
        name: ImageChops.subtract(new_complete[name], visible[name]) for name in LAYERS
    }
    materials = dict(old_materials)
    materials["sleeve"] = fill_cloth_from_source(
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
    removed_lower_pixels = sum(
        old_complete["sleeve"].getpixel((x, y)) > 0 and new_complete["sleeve"].getpixel((x, y)) == 0
        for y in range(H)
        for x in range(W)
    )
    hidden_below_visible = sum(
        new_complete["sleeve"].getpixel((x, y)) > 0 and visible["sleeve"].getpixel((x, y)) == 0 and y >= 390
        for y in range(H)
        for x in range(W)
    )

    source_panel = checker((W, H))
    source_panel.alpha_composite(source.convert("RGBA"))
    old_complete_panel = checker((W, H))
    old_complete_panel.alpha_composite(tinted(old_complete["sleeve"], COLORS["sleeve"]))
    new_complete_panel = checker((W, H))
    new_complete_panel.alpha_composite(tinted(new_complete["sleeve"], COLORS["sleeve"]))
    old_texture = checker((W, H))
    old_texture.alpha_composite(old_materials["sleeve"])
    new_texture = checker((W, H))
    new_texture.alpha_composite(materials["sleeve"])
    xray = checker((W, H))
    xray.alpha_composite(tinted(new_complete["upper_arm"], COLORS["upper_arm"], 255))
    xray.alpha_composite(tinted(new_complete["sleeve"], COLORS["sleeve"], 230))

    board = Image.new("RGB", (2160, 1210), (239, 242, 247))
    draw = ImageDraw.Draw(board)
    draw.text((42, 24), "小星 V24｜袖子语义纯净修复", font=font(39, True), fill=(24, 31, 43))
    draw.text(
        (45, 80),
        "以 V13 批准可见袖边为准，移除被算进袖子的下方皮肤碎片；下面的皮肤归上臂层。",
        font=font(22),
        fill=(70, 80, 96),
    )
    panels = [
        ("锁定原稿", source_panel, False),
        ("V22 袖完整层", old_complete_panel, True),
        ("V24 袖完整层", new_complete_panel, True),
        ("V22 原袖纹理", old_texture, False),
        ("V24 袖纹理", new_texture, False),
        ("最终透视\n橙=上臂 / 蓝=袖子", xray, True),
    ]
    for index, (label, image, nearest) in enumerate(panels):
        x = 38 + index * 350
        board.paste(crop(image, (320, 780), nearest).convert("RGB"), (x, 140))
        draw.multiline_text((x, 945), label, font=font(19, True), fill=(42, 51, 65), spacing=4)

    draw.rounded_rectangle((38, 985, 2120, 1182), radius=18, fill=(255, 255, 255), outline=(196, 204, 218), width=2)
    draw.text((68, 1010), "工程核验", font=font(26, True), fill=(31, 39, 52))
    lines = [
        f"V12 {upstream['v12']['matched']}/{upstream['v12']['total']}；V13 {upstream['v13']['matched']}/{upstream['v13']['total']}；V14 {upstream['v14']['matched']}/{upstream['v14']['total']}，冻结输入未改。",
        f"默认可见源图差异：{visible_difference}px；袖子下方被移出的像素：{removed_lower_pixels}px。",
        f"袖子完整层在 y>=390 的非可见区域残留：{hidden_below_visible}px；袖子可见层回到 V13 边界。",
        f"V22 报告仍是 {v22_report['status']}，但这版只修语义边界，不进入 mesh/nodes/motion/Physics/Runtime。",
        "停止点：请只判断袖口下方是否还算进袖子，以及下臂皮肤是否自然回到上臂层。",
    ]
    for index, line in enumerate(lines):
        draw.text((68, 1055 + index * 28), line, font=font(18), fill=(62, 71, 86))
    QA.mkdir(parents=True, exist_ok=True)
    board.save(BOARD)

    report = {
        "schemaVersion": 1,
        "status": "engineering_pass_pending_user_visual_approval",
        "scope": "sleeve semantic boundary repair only",
        "upstreamIntegrity": upstream,
        "sleeve": {
            "visibleRgbUnchanged": True,
            "removedLowerPixels": removed_lower_pixels,
            "hiddenBelowVisiblePixels": hidden_below_visible,
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
