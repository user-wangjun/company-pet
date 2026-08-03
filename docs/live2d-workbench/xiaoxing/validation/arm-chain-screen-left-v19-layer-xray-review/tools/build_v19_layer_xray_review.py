from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
V14 = WORKBENCH / "validation/arm-chain-screen-left-v14-complete-textures"
MANIFEST = V14 / "audit/v14-complete-texture-freeze-manifest-2026-07-28.json"
SOURCE = WORKBENCH / "source/masters/front-color-source-exact-after-reset.png"
QA = STAGE / "qa"
AUDIT = STAGE / "audit"
BOARD = QA / "V19-SLEEVE-UPPER-ARM-XRAY-USER-REVIEW.zh-CN.png"
REPORT = AUDIT / "v19-layer-xray-review-report.json"
LAYERS = ("upper_arm", "whole_hand", "forearm_bracelet", "sleeve")
COLORS = {
    "sleeve": (69, 119, 188),
    "upper_arm": (235, 151, 54),
    "forearm_bracelet": (65, 166, 126),
    "whole_hand": (216, 79, 118),
}
W, H = 512, 1086
CROP = (62, 190, 225, 650)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
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


def alpha(group: str, name: str) -> Image.Image:
    return Image.open(V14 / "corrected-masks" / group / f"{name}.png").convert("RGBA").getchannel("A")


def checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    image = Image.new("RGBA", size, (238, 238, 238, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(205, 205, 205, 255))
    return image


def tint(channel: Image.Image, color: tuple[int, int, int], opacity: int = 255) -> Image.Image:
    image = Image.new("RGBA", channel.size, color + (0,))
    image.putalpha(channel.point(lambda value: round(value * opacity / 255)))
    return image


def crop_scaled(image: Image.Image, size: tuple[int, int] = (300, 846), nearest: bool = False) -> Image.Image:
    method = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
    return image.crop(CROP).resize(size, method)


def main() -> None:
    integrity = verify()
    if not integrity["pass"]:
        raise RuntimeError("V14 freeze verification failed.")

    source = Image.open(SOURCE).convert("RGB")
    materials = {
        name: Image.open(V14 / "materials" / f"{name}.png").convert("RGBA")
        for name in LAYERS
    }
    visible = {name: alpha("visible", name) for name in LAYERS}
    complete = {name: alpha("complete", name) for name in LAYERS}

    default = Image.new("RGBA", (W, H), (248, 248, 248, 255))
    for name in LAYERS:
        default.alpha_composite(materials[name])
    default_rgb = default.convert("RGB")
    union = Image.new("L", (W, H), 0)
    for channel in visible.values():
        union = ImageChops.lighter(union, channel)
    difference = sum(
        default_rgb.getpixel((x, y)) != source.getpixel((x, y))
        for y in range(H)
        for x in range(W)
        if union.getpixel((x, y)) > 0
    )

    visible_blocks = checker((W, H))
    for name in LAYERS:
        visible_blocks.alpha_composite(tint(visible[name], COLORS[name]))

    xray = checker((W, H))
    xray.alpha_composite(tint(complete["upper_arm"], COLORS["upper_arm"], 255))
    xray.alpha_composite(tint(complete["sleeve"], COLORS["sleeve"], 92))
    xray.alpha_composite(tint(visible["sleeve"], COLORS["sleeve"], 155))
    xray.alpha_composite(tint(complete["forearm_bracelet"], COLORS["forearm_bracelet"], 200))
    xray.alpha_composite(tint(complete["whole_hand"], COLORS["whole_hand"], 200))

    isolated_sleeve = checker((W, H))
    isolated_sleeve.alpha_composite(materials["sleeve"])
    isolated_arm = checker((W, H))
    isolated_arm.alpha_composite(materials["upper_arm"])

    board = Image.new("RGB", (1960, 1120), (239, 242, 247))
    draw = ImageDraw.Draw(board)
    draw.text((42, 24), "小星｜袖子与上臂分层透视复核", font=font(40, True), fill=(24, 31, 43))
    draw.text(
        (45, 80),
        "色块只表示归属；完整层按绘制顺序会互相遮挡。这里把隐藏上臂单独透视出来。",
        font=font(23),
        fill=(70, 80, 96),
    )

    panels = [
        ("锁定原稿", source.convert("RGBA"), False),
        ("默认合成", default, False),
        ("仅可见色块", visible_blocks, True),
        ("隐藏透视\n橙=完整上臂，蓝=袖子", xray, True),
        ("袖子独立纹理", isolated_sleeve, False),
        ("上臂独立纹理", isolated_arm, False),
    ]
    for index, (label, image, nearest) in enumerate(panels):
        x = 45 + index * 315
        preview = crop_scaled(image, nearest=nearest)
        board.paste(preview.convert("RGB"), (x, 140))
        draw.multiline_text((x, 1000), label, font=font(21, True), fill=(42, 51, 65), spacing=4)

    draw.rounded_rectangle((45, 1050, 1910, 1100), radius=13, fill=(255, 241, 207))
    draw.text(
        (70, 1062),
        f"工程事实：V14 冻结 {integrity['matched']}/{integrity['total']}；默认合成对原稿差异 {difference}px。"
        " 请判断隐藏上臂轮廓、袖子独立轮廓和袖口衔接。",
        font=font(20, True),
        fill=(132, 81, 0),
    )
    QA.mkdir(parents=True, exist_ok=True)
    board.save(BOARD)

    report = {
        "schemaVersion": 1,
        "status": "engineering_pass_pending_user_visual_approval",
        "scope": "diagnostic x-ray review only; no frozen artifact changed",
        "v14Integrity": integrity,
        "defaultSourceRgbDifferencePixels": difference,
        "reviewBoard": BOARD.relative_to(STAGE).as_posix(),
        "notCreated": ["mesh rebuild", "nodes", "motion", "Physics", "Runtime"],
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
