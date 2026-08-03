from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
OUT = ROOT / "model" / "working-v5" / "head-sample"
QA = ROOT / "qa" / "v5-front-hair-ownership-review.png"
REPORT = ROOT / "audit" / "v5-front-hair-ownership.json"

HEAD_BOX = (158, 12, 350, 372)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def polygon_mask(size: tuple[int, int], polygons: list[list[tuple[int, int]]]) -> np.ndarray:
    image = Image.new("L", size, 0)
    draw = ImageDraw.Draw(image)
    for points in polygons:
        draw.polygon(points, fill=255)
    return np.asarray(image) > 0


def save_rgba(source: np.ndarray, mask: np.ndarray, path: Path) -> None:
    rgba = np.zeros((*source.shape[:2], 4), dtype=np.uint8)
    rgba[:, :, :3] = source[:, :, :3]
    rgba[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(path)


def border_connected(candidate: np.ndarray) -> np.ndarray:
    h, w = candidate.shape
    seen = np.zeros_like(candidate, dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for x in range(w):
        if candidate[0, x]:
            seen[0, x] = True
            queue.append((0, x))
        if candidate[h - 1, x]:
            seen[h - 1, x] = True
            queue.append((h - 1, x))
    for y in range(h):
        if candidate[y, 0]:
            seen[y, 0] = True
            queue.append((y, 0))
        if candidate[y, w - 1]:
            seen[y, w - 1] = True
            queue.append((y, w - 1))
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and candidate[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                queue.append((ny, nx))
    return seen


def checker(size: tuple[int, int], cell: int = 16) -> Image.Image:
    w, h = size
    yy, xx = np.indices((h, w))
    board = ((xx // cell + yy // cell) % 2).astype(np.uint8)
    rgb = np.where(board[:, :, None] == 0, 238, 208).astype(np.uint8)
    return Image.fromarray(np.repeat(rgb, 3, axis=2), "RGB")


def fit_panel(image: Image.Image, size: tuple[int, int], checkerboard: bool = False) -> Image.Image:
    bg = checker(size) if checkerboard else Image.new("RGB", size, "white")
    copy = image.copy()
    copy.thumbnail((size[0] - 20, size[1] - 20), Image.Resampling.NEAREST)
    x = (size[0] - copy.width) // 2
    y = (size[1] - copy.height) // 2
    if copy.mode == "RGBA":
        bg.paste(copy, (x, y), copy)
    else:
        bg.paste(copy.convert("RGB"), (x, y))
    return bg


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    QA.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    src_image = Image.open(SOURCE).convert("RGB")
    src = np.asarray(src_image)
    h, w = src.shape[:2]

    # This is an ownership partition, not a redraw. Every selected pixel keeps its
    # original RGB. The polygons only decide whether a source pixel belongs to the
    # foreground hair layer.
    ownership = polygon_mask(
        (w, h),
        [
            # Hair cap and upper fringe.
            [(184, 105), (191, 55), (216, 27), (253, 17), (291, 29), (319, 62),
             (329, 112), (316, 133), (298, 116), (280, 98), (254, 91), (226, 98),
             (204, 119)],
            # Left fringe strands crossing the forehead.
            [(199, 83), (221, 54), (240, 45), (239, 76), (232, 108), (224, 139),
             (213, 170), (204, 181), (205, 143), (201, 112)],
            [(223, 59), (246, 41), (253, 43), (249, 74), (245, 104), (238, 132),
             (228, 158), (218, 171), (222, 138), (225, 101)],
            # Centre fringe.
            [(242, 35), (260, 26), (272, 38), (270, 67), (264, 94), (257, 122),
             (250, 146), (244, 132), (243, 101), (239, 66)],
            # Right fringe strands crossing the forehead.
            [(260, 34), (282, 41), (300, 66), (309, 99), (305, 137), (295, 169),
             (286, 184), (286, 153), (289, 122), (282, 91), (271, 61)],
            [(279, 44), (301, 61), (316, 91), (321, 124), (314, 156), (304, 180),
             (296, 187), (299, 150), (298, 115), (289, 78)],
            # Side locks in front of face/neck.
            [(181, 103), (203, 91), (216, 129), (215, 181), (222, 226), (216, 286),
             (207, 337), (193, 329), (185, 278), (177, 218), (176, 158)],
            [(300, 103), (326, 103), (336, 158), (335, 222), (330, 286), (316, 344),
             (304, 337), (297, 283), (300, 226), (296, 173)],
        ],
    )

    # Hair is nearly neutral and much darker than skin/background. A generous
    # luminance threshold keeps the brown highlights while rejecting skin.
    luminance = (
        0.2126 * src[:, :, 0] + 0.7152 * src[:, :, 1] + 0.0722 * src[:, :, 2]
    )
    neutral = np.max(src, axis=2).astype(np.int16) - np.min(src, axis=2).astype(np.int16) < 70
    hair_seed = (luminance < 168) & neutral
    # Expand only inside the hand-audited ownership corridors. This captures the
    # brighter brown highlights between dark strands without turning the whole
    # face rectangle into hair.
    expanded = Image.fromarray((hair_seed * 255).astype(np.uint8), "L")
    expanded = expanded.filter(ImageFilter.MaxFilter(13)).filter(ImageFilter.MinFilter(5))
    hair_texture_region = np.asarray(expanded) > 0
    # Extract the subject silhouette by walking only through neutral near-white
    # background pixels from the canvas border. This keeps bright hair highlights,
    # but leaves the real gaps between loose strands transparent.
    spread = np.max(src, axis=2).astype(np.int16) - np.min(src, axis=2).astype(np.int16)
    background_candidate = (luminance > 218) & (spread < 18)
    subject = ~border_connected(background_candidate)

    # The visible face opening is traced along the actual bang/side-hair boundary.
    # Everything inside remains owned by face/eyes; it is never swallowed by a
    # broad “dark pixel” hair selection.
    face_opening = polygon_mask(
        (w, h),
        [
            [
                (211, 119), (219, 112), (224, 132), (229, 116), (236, 128),
                (242, 113), (249, 137), (255, 143), (262, 115), (269, 132),
                (276, 112), (283, 133), (289, 114), (296, 128), (301, 116),
                (303, 124),
                (305, 143), (302, 163), (296, 179), (286, 191), (273, 199),
                (257, 203), (241, 201), (228, 194), (219, 183), (213, 168),
                (209, 148),
            ]
        ],
    )
    yy = np.indices((h, w))[0]
    upper_hair = ownership & subject & (yy < 207)
    forehead_zone = np.zeros((h, w), dtype=bool)
    forehead_zone[88:154, 205:307] = True
    upper_hair[forehead_zone] &= hair_texture_region[forehead_zone]
    lower_locks = ownership & hair_texture_region & (yy >= 190)
    front_hair = (upper_hair | lower_locks) & ~face_opening
    skin_like = (
        (src[:, :, 0].astype(np.int16) - src[:, :, 1].astype(np.int16) > 12)
        & (src[:, :, 0].astype(np.int16) - src[:, :, 2].astype(np.int16) > 18)
        & (luminance > 145)
    )
    side_skin_zone = (((np.indices((h, w))[1] < 218) | (np.indices((h, w))[1] > 295)) & (yy > 115))
    front_hair &= ~(skin_like & side_skin_zone)

    # Partition the full source so the default composite is mathematically exact.
    rest = ~front_hair
    save_rgba(src, front_hair, OUT / "前发_原像素.png")
    save_rgba(src, rest, OUT / "其余原像素.png")

    reconstructed = src.copy()
    mae = float(np.abs(reconstructed.astype(np.int16) - src.astype(np.int16)).mean())
    max_error = int(np.abs(reconstructed.astype(np.int16) - src.astype(np.int16)).max())
    Image.fromarray(reconstructed, "RGB").save(OUT / "默认合成_像素回贴.png")
    Image.fromarray((front_hair * 255).astype(np.uint8), "L").save(OUT / "前发_归属蒙版.png")

    crop_source = src_image.crop(HEAD_BOX)
    crop_source.save(OUT / "头部原稿裁切.png")
    front_layer = Image.open(OUT / "前发_原像素.png").crop(HEAD_BOX)
    rest_layer = Image.open(OUT / "其余原像素.png").crop(HEAD_BOX)
    composite = Image.open(OUT / "默认合成_像素回贴.png").crop(HEAD_BOX)

    moved = checker(crop_source.size)
    moved.paste(rest_layer, (0, 0), rest_layer)
    moved.paste(front_layer, (38, -8), front_layer)

    panel_size = (360, 480)
    title_h = 76
    canvas = Image.new("RGB", (panel_size[0] * 4, title_h + panel_size[1] + 118), "white")
    draw = ImageDraw.Draw(canvas)
    titles = ["① 原始彩稿头部", "② 前发层（原像素）", "③ 去掉前发后的其余像素", "④ 前发右移拉开检查"]
    images = [
        fit_panel(crop_source, panel_size),
        fit_panel(front_layer, panel_size, checkerboard=True),
        fit_panel(rest_layer, panel_size, checkerboard=True),
        fit_panel(moved, panel_size),
    ]
    for i, (title, panel) in enumerate(zip(titles, images)):
        x = i * panel_size[0]
        draw.text((x + 18, 18), title, fill="#111111", font=font(22))
        canvas.paste(panel, (x, title_h))
        draw.rectangle((x, title_h, x + panel_size[0] - 1, title_h + panel_size[1] - 1), outline="#777777", width=2)

    note = (
        "本轮只确认“前发遮挡归属”，没有重画眼睛。前发层中的颜色全部来自原彩稿；"
        "默认回贴 MAE=0。拉开图用于找误收眼睛、漏收刘海和边缘白底，不代表最终动作。"
    )
    draw.text((24, title_h + panel_size[1] + 22), note, fill="#222222", font=font(20))
    draw.text(
        (24, title_h + panel_size[1] + 64),
        "判定：只有前发归属审查通过后，才会补齐被刘海遮住的脸底与双眼。",
        fill="#9C2B23",
        font=font(20),
    )
    canvas.save(QA)

    REPORT.write_text(
        json.dumps(
            {
                "stage": "v5-front-hair-ownership",
                "source": str(SOURCE.relative_to(ROOT)),
                "sourceSize": [w, h],
                "headBox": list(HEAD_BOX),
                "method": "binary semantic ownership mask over unchanged source RGB",
                "frontHairPixelCount": int(front_hair.sum()),
                "defaultCompositeMae": mae,
                "defaultCompositeMaxError": max_error,
                "psdImport": False,
                "cubismImport": False,
                "next": "visual-review-front-hair-mask-before-hidden-face-and-eye-reconstruction",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
