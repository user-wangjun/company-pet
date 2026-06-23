from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


PET_DIR = Path(__file__).resolve().parents[1]
PNG_ATLAS = PET_DIR / "qa" / "spritesheet.png"
WEBP_ATLAS = PET_DIR / "spritesheet.webp"

CELL_WIDTH = 192
CELL_HEIGHT = 208
USED_FRAMES = [6, 8, 8, 8, 8, 8, 8, 8, 6]


def composite_on(image: Image.Image, color: tuple[int, int, int, int]) -> Image.Image:
    background = Image.new("RGBA", image.size, color)
    background.alpha_composite(image)
    return background.convert("RGB")


def component_bounds(mask: list[bool], width: int, height: int) -> list[tuple[int, int, int, int, int]]:
    visited = bytearray(width * height)
    components: list[tuple[int, int, int, int, int]] = []

    for start, enabled in enumerate(mask):
        if not enabled or visited[start]:
            continue

        queue = deque([start])
        visited[start] = 1
        min_x = width
        min_y = height
        max_x = 0
        max_y = 0
        area = 0

        while queue:
            current = queue.popleft()
            x = current % width
            y = current // width
            area += 1
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

            for neighbor in (
                current - 1 if x > 0 else -1,
                current + 1 if x + 1 < width else -1,
                current - width if y > 0 else -1,
                current + width if y + 1 < height else -1,
            ):
                if neighbor >= 0 and mask[neighbor] and not visited[neighbor]:
                    visited[neighbor] = 1
                    queue.append(neighbor)

        components.append((min_x, min_y, max_x + 1, max_y + 1, area))

    return components


def assert_no_elongated_black_artifacts(atlas: Image.Image) -> None:
    for row, frame_count in enumerate(USED_FRAMES):
        for column in range(frame_count):
            cell = atlas.crop(
                (
                    column * CELL_WIDTH,
                    row * CELL_HEIGHT,
                    (column + 1) * CELL_WIDTH,
                    (row + 1) * CELL_HEIGHT,
                )
            ).convert("RGBA")
            mask = [
                alpha >= 240 and red < 25 and green < 25 and blue < 25
                for red, green, blue, alpha in cell.getdata()
            ]
            for x0, y0, x1, y1, area in component_bounds(
                mask, CELL_WIDTH, CELL_HEIGHT
            ):
                width = x1 - x0
                height = y1 - y0
                if area >= 120 and width >= height * 2.8:
                    raise AssertionError(
                        f"row {row} frame {column} has an elongated black "
                        f"component: bbox={(x0, y0, x1, y1)} area={area}"
                    )


def assert_default_frame_has_clean_face(atlas: Image.Image) -> None:
    default_frame = atlas.crop((0, 0, CELL_WIDTH, CELL_HEIGHT)).convert("RGBA")
    dark_mask = [
        alpha >= 200 and red < 40 and green < 40 and blue < 40
        for red, green, blue, alpha in default_frame.getdata()
    ]
    dark_components = sorted(
        component_bounds(dark_mask, CELL_WIDTH, CELL_HEIGHT),
        key=lambda component: component[4],
        reverse=True,
    )
    eye_components = dark_components[:2]

    if len(eye_components) != 2 or any(
        area < 120 or (x1 - x0) < 15 or (y1 - y0) < 15
        for x0, y0, x1, y1, area in eye_components
    ):
        raise AssertionError(
            "default idle frame has low-resolution or fragmented eye detail: "
            f"{eye_components}"
        )


def assert_webp_matches_png(png_atlas: Image.Image, webp_atlas: Image.Image) -> None:
    for name, color in (
        ("white", (255, 255, 255, 255)),
        ("black", (0, 0, 0, 255)),
    ):
        expected = composite_on(png_atlas, color)
        actual = composite_on(webp_atlas, color)
        difference = ImageChops.difference(expected, actual)
        mean_error = sum(ImageStat.Stat(difference).mean) / 3
        if mean_error > 0.5:
            raise AssertionError(
                f"WebP differs from the PNG atlas on {name}: "
                f"mean RGB error={mean_error:.3f}"
            )


def main() -> None:
    png_atlas = Image.open(PNG_ATLAS).convert("RGBA")
    webp_atlas = Image.open(WEBP_ATLAS).convert("RGBA")

    expected_size = (CELL_WIDTH * 8, CELL_HEIGHT * 9)
    assert png_atlas.size == expected_size
    assert webp_atlas.size == expected_size
    assert_default_frame_has_clean_face(png_atlas)
    assert_no_elongated_black_artifacts(png_atlas)
    assert_webp_matches_png(png_atlas, webp_atlas)
    print("suan-bird render quality: PASS")


if __name__ == "__main__":
    main()
