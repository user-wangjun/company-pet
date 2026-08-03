from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve()
XIAOXING_ROOT = HERE.parents[3]
VALIDATION_ROOT = HERE.parents[1]
V4_ZIP_PATH = (
    XIAOXING_ROOT
    / "validation"
    / "arm-chain-screen-right-v4-wrist-motion"
    / "archive"
    / "stage-a-v4-approved-2026-07-24.zip"
)
LINE_PATH = XIAOXING_ROOT / "source" / "masters" / "front-line-source-exact-after-reset.png"
COLOR_PATH = XIAOXING_ROOT / "source" / "masters" / "front-color-source-exact-after-reset.png"
OUTPUT_PATH = VALIDATION_ROOT / "qa" / "working" / "ownership-diagnostic.png"
COLOR_CROP_PATH = VALIDATION_ROOT / "qa" / "working" / "source-color-800-nogrid.png"
LINE_CROP_PATH = VALIDATION_ROOT / "qa" / "working" / "source-line-800-nogrid.png"

CROP = (320, 365, 390, 435)
SCALE = 8
PANEL_SIZE = ((CROP[2] - CROP[0]) * SCALE, (CROP[3] - CROP[1]) * SCALE)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def nearest_crop(image: Image.Image) -> Image.Image:
    return image.crop(CROP).resize(PANEL_SIZE, Image.Resampling.NEAREST)


def overlay_mask(base: Image.Image, mask: Image.Image, color: tuple[int, int, int, int]) -> Image.Image:
    result = nearest_crop(base).convert("RGBA")
    local_mask = nearest_crop(mask.convert("L"))
    tint = Image.new("RGBA", result.size, color)
    result.alpha_composite(Image.composite(tint, Image.new("RGBA", result.size), local_mask))
    return result


def add_grid(image: Image.Image) -> None:
    draw = ImageDraw.Draw(image)
    for x in range(0, image.width + 1, SCALE):
        draw.line((x, 0, x, image.height), fill=(0, 0, 0, 42), width=1)
    for y in range(0, image.height + 1, SCALE):
        draw.line((0, y, image.width, y), fill=(0, 0, 0, 42), width=1)


def load_v4_mask(archive: zipfile.ZipFile, path: str) -> Image.Image:
    return Image.open(io.BytesIO(archive.read(path))).convert("RGBA").getchannel("A")


def main() -> None:
    line = Image.open(LINE_PATH).convert("RGB")
    color = Image.open(COLOR_PATH).convert("RGB")
    with zipfile.ZipFile(V4_ZIP_PATH) as archive:
        upper_arm = load_v4_mask(archive, "masks/visible/upper_arm.png")
        sleeve = load_v4_mask(archive, "masks/visible/sleeve.png")

    panels = [
        ("权威线稿 800% 最近邻", nearest_crop(line)),
        ("权威彩稿 800% 最近邻", nearest_crop(color)),
        (
            "V4 上臂候选（青色，仅作参考）",
            overlay_mask(color, upper_arm, (0, 210, 255, 145)),
        ),
        (
            "V4 袖子候选（洋红，仅作参考）",
            overlay_mask(color, sleeve, (255, 0, 170, 145)),
        ),
    ]
    title_height = 52
    margin = 24
    canvas = Image.new(
        "RGB",
        (
            margin * 3 + PANEL_SIZE[0] * 2,
            margin * 3 + (PANEL_SIZE[1] + title_height) * 2,
        ),
        (238, 238, 238),
    )
    draw = ImageDraw.Draw(canvas)
    title_font = font(24)
    note_font = font(18)
    for index, (title, panel) in enumerate(panels):
        add_grid(panel)
        column = index % 2
        row = index // 2
        x = margin + column * (PANEL_SIZE[0] + margin)
        y = margin + row * (PANEL_SIZE[1] + title_height + margin)
        draw.text((x, y), title, fill=(20, 20, 20), font=title_font)
        canvas.paste(panel.convert("RGB"), (x, y + title_height))
    draw.text(
        (margin, canvas.height - 25),
        f"审查裁剪：原图坐标 x={CROP[0]}..{CROP[2]-1}, y={CROP[1]}..{CROP[3]-1}；不是正式材料。",
        fill=(55, 55, 55),
        font=note_font,
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUTPUT_PATH)
    nearest_crop(color).save(COLOR_CROP_PATH)
    nearest_crop(line).save(LINE_CROP_PATH)
    print(OUTPUT_PATH.relative_to(XIAOXING_ROOT).as_posix())


if __name__ == "__main__":
    main()
