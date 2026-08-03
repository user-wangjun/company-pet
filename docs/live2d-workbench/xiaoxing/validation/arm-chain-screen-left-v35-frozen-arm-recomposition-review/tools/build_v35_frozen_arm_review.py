from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
XIAOXING = ROOT.parents[1]
V31 = (
    XIAOXING
    / "validation/arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve"
)
V34 = (
    XIAOXING
    / "validation/arm-chain-screen-left-v34-hand-root-from-frozen-ucap"
)
SOURCE = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"

SOURCES = {
    "sleeve": V31 / "materials/sleeve.png",
    "upperArm": V31 / "materials/upper_arm.png",
    "forearm": V34 / "materials/forearm-slim.png",
    "hand": V34 / "materials/hand.png",
    "braceletMask": V31 / "masks/visible/bracelet-owned-by-forearm.png",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for name in (
        "msyhbd.ttc" if bold else "msyh.ttc",
        "simhei.ttf",
        "arial.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def checker(size: tuple[int, int], cell: int = 22) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, (240, 244, 249))
    draw = ImageDraw.Draw(image)
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle(
                    (x, y, x + cell - 1, y + cell - 1),
                    fill=(210, 218, 228),
                )
    return image


def solid(mask_path: Path, color: tuple[int, int, int, int]) -> Image.Image:
    mask = Image.open(mask_path).convert("L")
    image = Image.new("RGBA", mask.size, color)
    image.putalpha(mask)
    return image


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    alpha = np.asarray(image.getchannel("A"))
    ys, xs = np.where(alpha > 8)
    return int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)


def crop_with_margin(
    image: Image.Image, bbox: tuple[int, int, int, int], margin: int
) -> Image.Image:
    left, top, right, bottom = bbox
    return image.crop(
        (
            max(0, left - margin),
            max(0, top - margin),
            min(image.width, right + margin),
            min(image.height, bottom + margin),
        )
    )


def fit(
    board: Image.Image,
    image: Image.Image,
    box: tuple[int, int, int, int],
    label: str,
) -> None:
    left, top, right, bottom = box
    label_height = 58
    target_width = right - left
    target_height = bottom - top - label_height
    scale = min(target_width / image.width, target_height / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.NEAREST,
    )
    x = left + (target_width - resized.width) // 2
    y = top + label_height + (target_height - resized.height) // 2
    board.paste(resized, (x, y))
    ImageDraw.Draw(board).text(
        (left + 18, top + 12), label, fill=(26, 38, 54), font=font(26, True)
    )


def main() -> None:
    for path in [SOURCE, *SOURCES.values()]:
        if not path.is_file():
            raise FileNotFoundError(path)

    layers = {name: Image.open(path).convert("RGBA") for name, path in SOURCES.items() if name != "braceletMask"}
    size = layers["hand"].size
    if any(layer.size != size for layer in layers.values()):
        raise ValueError("Frozen layers do not share one canvas")

    bracelet = solid(SOURCES["braceletMask"], (177, 63, 178, 255))
    transparent = Image.new("RGBA", size, (0, 0, 0, 0))
    # Frozen ownership order: upper arm behind the distal chain; hand behind
    # the forearm U-cap; sleeve and forearm-owned bracelet are foreground.
    for layer in (
        layers["upperArm"],
        layers["hand"],
        layers["forearm"],
        layers["sleeve"],
        bracelet,
    ):
        transparent.alpha_composite(layer)

    body_bbox = alpha_bbox(transparent)
    full_crop = crop_with_margin(transparent, body_bbox, 18)
    full_view = checker(full_crop.size).convert("RGBA")
    full_view.alpha_composite(full_crop)

    source = Image.open(SOURCE).convert("RGBA")
    source_crop = crop_with_margin(source, body_bbox, 18)
    source_view = checker(source_crop.size).convert("RGBA")
    source_view.alpha_composite(source_crop)

    wrist_bbox = (72, 458, 158, 650)
    wrist_crop = transparent.crop(wrist_bbox)
    wrist_view = checker(wrist_crop.size, 12).convert("RGBA")
    wrist_view.alpha_composite(wrist_crop)

    qa = ROOT / "qa"
    audit = ROOT / "audit"
    qa.mkdir(parents=True, exist_ok=True)
    audit.mkdir(parents=True, exist_ok=True)
    transparent.save(qa / "screen-left-frozen-arm-recomposition.png")

    board = Image.new("RGB", (2100, 1180), (235, 241, 247))
    draw = ImageDraw.Draw(board)
    draw.text(
        (55, 30),
        "小星 screen-left 手臂｜冻结材料完整拼合预览",
        fill=(17, 29, 44),
        font=font(42, True),
    )
    draw.text(
        (57, 88),
        "蓝=袖子｜红=上臂（默认姿态被袖子遮住）｜橙=瘦化前臂｜肤色=手｜紫=前臂所属手链",
        fill=(62, 76, 96),
        font=font(25),
    )
    panels = (
        (source_view.convert("RGB"), (45, 145, 690, 1070), "1. Reset 原图参照"),
        (full_view.convert("RGB"), (720, 145, 1365, 1070), "2. 冻结材料完整回组"),
        (wrist_view.convert("RGB"), (1395, 145, 2055, 1070), "3. 腕手衔接放大"),
    )
    for image, box, label in panels:
        draw.rounded_rectangle(box, 22, fill=(255, 255, 255), outline=(172, 184, 200), width=3)
        fit(board, image, (box[0] + 12, box[1] + 8, box[2] - 12, box[3] - 12), label)
    draw.text(
        (55, 1110),
        "本图仅做回组审查：没有改动 V31/V34 的袖子、上臂、前臂、手或手链几何。",
        fill=(41, 91, 78),
        font=font(24, True),
    )
    board_path = qa / "V35-screen-left冻结手臂完整拼合审查图.png"
    board.save(board_path)

    report = {
        "scope": "screen-left frozen full arm recomposition review",
        "mutatesFrozenGeometry": False,
        "drawOrderBackToFront": [
            "upperArm",
            "hand",
            "forearm",
            "sleeve",
            "bracelet",
        ],
        "sources": {
            name: {
                "path": path.relative_to(XIAOXING).as_posix(),
                "sha256": sha256(path),
            }
            for name, path in SOURCES.items()
        },
        "outputs": {
            "transparentRecomposition": "qa/screen-left-frozen-arm-recomposition.png",
            "reviewBoard": "qa/V35-screen-left冻结手臂完整拼合审查图.png",
        },
    }
    (audit / "v35-frozen-arm-recomposition-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(board_path)


if __name__ == "__main__":
    main()
