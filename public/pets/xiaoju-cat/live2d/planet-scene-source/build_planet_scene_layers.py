from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parent
LIVE2D_ROOT = ROOT.parent
LAYERS = ROOT / "layers"
BACKGROUND = LIVE2D_ROOT / "planet-background-v1.png"
CAT_WITH_PAWS = LIVE2D_ROOT / "planet-cat-cutout-v1.png"
CAT_BODY = LIVE2D_ROOT / "planet-cat-body-no-paws-v1.png"


def generated_cutout(path: Path) -> Image.Image:
    """Recover alpha from the neutral checkerboard baked into generated PNGs."""
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    mean = rgb.mean(axis=2)
    warmth = rgb[:, :, 0] - rgb[:, :, 2]
    alpha = np.maximum.reduce(
        [
            np.clip((chroma - 2) * 22, 0, 255),
            np.clip((warmth - 1) * 14, 0, 255),
            np.clip((232 - mean) * 9, 0, 255),
        ]
    ).astype(np.uint8)
    alpha = np.asarray(
        Image.fromarray(alpha, "L")
        .filter(ImageFilter.MedianFilter(3))
        .filter(ImageFilter.GaussianBlur(0.45))
    )
    rgba = np.dstack([rgb.astype(np.uint8), alpha])
    return Image.fromarray(rgba, "RGBA")


def ellipse_mask(size: tuple[int, int], box: tuple[int, int, int, int], blur=1.1) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse(box, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(blur))


def polygon_mask(size: tuple[int, int], points: list[tuple[int, int]], blur=1.1) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(blur))


def isolated(image: Image.Image, mask: Image.Image) -> Image.Image:
    layer = image.copy()
    alpha = np.minimum(np.asarray(image.getchannel("A")), np.asarray(mask)).astype(np.uint8)
    layer.putalpha(Image.fromarray(alpha, "L"))
    return layer


def remove_region(image: Image.Image, mask: Image.Image) -> Image.Image:
    layer = image.copy()
    alpha = np.asarray(layer.getchannel("A"), dtype=np.int16)
    alpha = alpha * (255 - np.asarray(mask, dtype=np.int16)) // 255
    layer.putalpha(Image.fromarray(alpha.astype(np.uint8), "L"))
    return layer


def iris_without_pupil(
    rgba: Image.Image,
    center: tuple[int, int],
    radius: tuple[int, int],
) -> Image.Image:
    data = np.asarray(rgba.convert("RGBA")).copy()
    cx, cy = center
    rx, ry = radius
    h, w = data.shape[:2]
    yy, xx = np.ogrid[:h, :w]
    inside = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.0
    ys, xs = np.where(inside)
    for y, x in zip(ys, xs):
        dx, dy = x - cx, y - cy
        length = max((dx * dx + dy * dy) ** 0.5, 0.001)
        sx = int(np.clip(round(cx + dx / length * (rx + 4)), 0, w - 1))
        sy = int(np.clip(round(cy + dy / length * (ry + 4)), 0, h - 1))
        data[y, x, :3] = data[sy, sx, :3]
    return Image.fromarray(data, "RGBA")


def patch_eye_base(rgba: Image.Image, box: tuple[int, int, int, int], offset_y: int) -> None:
    x0, y0, x1, y1 = box
    patch = rgba.crop((x0, y0 + offset_y, x1, y1 + offset_y))
    local_mask = ellipse_mask(rgba.size, box, blur=7).crop(box)
    rgba.paste(patch, (x0, y0), local_mask)


def make_eyelid(size: tuple[int, int], box: tuple[int, int, int, int]) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    cy = (y0 + y1) // 2
    draw.arc((x0 + 10, cy - 25, x1 - 10, cy + 15), 10, 170, fill=(108, 52, 22, 235), width=6)
    return layer.filter(ImageFilter.GaussianBlur(0.4))


def main() -> None:
    LAYERS.mkdir(parents=True, exist_ok=True)
    background = Image.open(BACKGROUND).convert("RGBA")
    cat = generated_cutout(CAT_WITH_PAWS)
    body_source = generated_cutout(CAT_BODY)
    size = background.size

    left_eye = (642, 490, 775, 610)
    right_eye = (870, 420, 990, 545)
    left_pupil = (708, 550)
    right_pupil = (930, 482)
    left_paw_mask = ellipse_mask(size, (565, 655, 790, 830), blur=3)
    right_paw_mask = ellipse_mask(size, (1040, 450, 1255, 645), blur=3)

    body = body_source.copy()
    patch_eye_base(body, left_eye, -110)
    patch_eye_base(body, right_eye, -105)

    eye_source = iris_without_pupil(body_source, left_pupil, (27, 38))
    eye_source = iris_without_pupil(eye_source, right_pupil, (27, 38))

    planet_mask = polygon_mask(
        size,
        [
            (300, 1148), (390, 1068), (500, 960), (600, 874), (700, 802),
            (800, 741), (900, 689), (1000, 643), (1100, 602), (1200, 564),
            (1300, 506), (1370, 480), (1370, 1148),
        ],
        blur=1.5,
    )
    planet = background.copy()
    planet.putalpha(planet_mask)

    transparent = Image.new("RGBA", size, (0, 0, 0, 0))
    layer_specs: list[tuple[str, Image.Image]] = [
        ("00_Stars_Background.png", background),
        ("10_Cat_Body_Base.png", body),
        ("20_Eye_L_Base.png", isolated(eye_source, ellipse_mask(size, left_eye))),
        ("21_Eye_R_Base.png", isolated(eye_source, ellipse_mask(size, right_eye))),
        ("30_Pupil_L.png", isolated(body_source, ellipse_mask(size, (676, 508, 740, 595), 0.8))),
        ("31_Pupil_R.png", isolated(body_source, ellipse_mask(size, (899, 438, 961, 530), 0.8))),
        ("40_Eyelid_L.png", make_eyelid(size, left_eye)),
        ("41_Eyelid_R.png", make_eyelid(size, right_eye)),
        ("50_Planet_Foreground.png", planet),
        ("60_Paw_L.png", isolated(cat, left_paw_mask)),
        ("61_Paw_R.png", isolated(cat, right_paw_mask)),
    ]

    for filename, layer in layer_specs:
        layer.save(LAYERS / filename)

    preview = transparent.copy()
    for filename, layer in layer_specs:
        if filename.startswith("4"):
            continue
        preview.alpha_composite(layer)
    preview.save(ROOT / "planet-scene-layered-preview.png")


if __name__ == "__main__":
    main()
