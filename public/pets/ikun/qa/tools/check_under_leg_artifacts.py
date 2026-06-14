from argparse import ArgumentParser
from pathlib import Path

from PIL import Image, ImageChops


CELL_WIDTH = 192
CELL_HEIGHT = 208
FRAME_COUNT = 8
MAX_SEMITRANSPARENT_PIXELS = 600
MAX_LOW_ALPHA_PIXELS = 180
MIN_ORANGE_PIXELS = 1200


def parse_args():
    parser = ArgumentParser(
        description="Check the ikun under-leg row for translucent ghost outlines."
    )
    parser.add_argument(
        "row",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "under-leg-v12"
        / "row-4-under-leg-v12.png",
    )
    parser.add_argument(
        "--atlas",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "spritesheet.webp",
    )
    return parser.parse_args()


def is_orange(pixel):
    red, green, blue, alpha = pixel
    return (
        alpha > 0
        and red > 150
        and 45 < green < 180
        and blue < 80
        and red > green * 1.25
    )


args = parse_args()
with Image.open(args.row) as opened:
    row = opened.convert("RGBA")
with Image.open(args.atlas) as opened:
    atlas = opened.convert("RGBA")

assert row.size == (CELL_WIDTH * FRAME_COUNT, CELL_HEIGHT), row.size
assert atlas.size == (CELL_WIDTH * FRAME_COUNT, CELL_HEIGHT * 9), atlas.size

packaged_row = atlas.crop(
    (0, CELL_HEIGHT * 4, CELL_WIDTH * FRAME_COUNT, CELL_HEIGHT * 5)
)
assert ImageChops.difference(row, packaged_row).getbbox() is None, (
    "packaged atlas row 4 differs from the cleaned QA row; "
    "replace the complete atlas row instead of alpha-compositing over it"
)

violations = []
for frame in range(FRAME_COUNT):
    cell = row.crop(
        (frame * CELL_WIDTH, 0, (frame + 1) * CELL_WIDTH, CELL_HEIGHT)
    )
    pixels = list(cell.get_flattened_data())
    semitransparent = sum(0 < pixel[3] < 255 for pixel in pixels)
    low_alpha = sum(0 < pixel[3] <= 64 for pixel in pixels)
    orange = sum(is_orange(pixel) for pixel in pixels)
    hidden_rgb = sum(
        pixel[3] == 0 and any(channel != 0 for channel in pixel[:3])
        for pixel in pixels
    )

    if semitransparent > MAX_SEMITRANSPARENT_PIXELS:
        violations.append(
            f"frame {frame + 1}: {semitransparent} semitransparent pixels"
        )
    if low_alpha > MAX_LOW_ALPHA_PIXELS:
        violations.append(f"frame {frame + 1}: {low_alpha} low-alpha pixels")
    if orange < MIN_ORANGE_PIXELS:
        violations.append(f"frame {frame + 1}: basketball lost ({orange} orange pixels)")
    if hidden_rgb:
        violations.append(f"frame {frame + 1}: {hidden_rgb} hidden RGB pixels")

assert not violations, "under-leg artifact check failed:\n" + "\n".join(violations)
print("ikun under-leg artifact check passed")
