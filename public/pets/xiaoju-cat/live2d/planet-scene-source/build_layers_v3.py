"""Build clean, full-canvas Live2D foreleg layers and QA composites.

The generated source sheet contains exactly two detached forelegs on alpha.
This script keeps the source untouched, separates each connected limb, places
both in the full 1370x1148 scene, and renders a cover-pose QA image.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parent
V2 = ROOT / "layers-v2"
V3 = ROOT / "layers-v3"
CANVAS_SIZE = (1370, 1148)


@dataclass(frozen=True)
class Placement:
    scale: float
    xy: tuple[int, int]


def alpha_bbox(image: Image.Image, half: str) -> tuple[int, int, int, int]:
    alpha = image.getchannel("A")
    width, height = image.size
    if half == "left":
        region = alpha.crop((0, 0, width // 2, height))
        bbox = region.getbbox()
        if bbox is None:
            raise RuntimeError("No foreground found in left half")
        return bbox

    region = alpha.crop((width // 2, 0, width, height))
    bbox = region.getbbox()
    if bbox is None:
        raise RuntimeError("No foreground found in right half")
    x0, y0, x1, y1 = bbox
    return x0 + width // 2, y0, x1 + width // 2, y1


def prepare_limb(source: Image.Image, bbox: tuple[int, int, int, int], scale: float) -> Image.Image:
    limb = source.crop(bbox)
    limb = limb.rotate(180, resample=Image.Resampling.BICUBIC, expand=True)
    size = (round(limb.width * scale), round(limb.height * scale))
    return limb.resize(size, Image.Resampling.LANCZOS)


def full_canvas_layer(limb: Image.Image, xy: tuple[int, int]) -> Image.Image:
    layer = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    layer.alpha_composite(limb, xy)
    return layer


def composite_scene(layers: list[Image.Image]) -> Image.Image:
    result = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    for layer in layers:
        result.alpha_composite(layer)
    return result


def body_occluder(
    body: Image.Image,
    box: tuple[int, int, int, int],
    blur: float = 10,
) -> Image.Image:
    """Copy a soft shoulder patch that hides a moving limb's root seam."""
    mask = Image.new("L", CANVAS_SIZE, 0)
    ImageDraw.Draw(mask).ellipse(box, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(blur))
    alpha = Image.new("L", CANVAS_SIZE, 0)
    body_alpha = body.getchannel("A")
    alpha.paste(Image.composite(body_alpha, alpha, mask))
    result = body.copy()
    result.putalpha(alpha)
    return result


def main() -> None:
    V3.mkdir(parents=True, exist_ok=True)
    source = Image.open(V3 / "forelegs-open-root-transparent.png").convert("RGBA")
    if source.size != CANVAS_SIZE:
        raise RuntimeError(f"Unexpected source size: {source.size}")

    # After the 180-degree turn, the source-right limb points up-right and is
    # used on the viewer's left. The source-left limb points up-left and is
    # used on the viewer's right.
    viewer_left = prepare_limb(source, alpha_bbox(source, "right"), scale=0.65)
    viewer_right = prepare_limb(source, alpha_bbox(source, "left"), scale=0.58)

    left_layer = full_canvas_layer(viewer_left, Placement(0.65, (430, 345)).xy)
    right_layer = full_canvas_layer(viewer_right, Placement(0.58, (835, 355)).xy)

    body = Image.open(V2 / "10_Cat_Body_Base.png").convert("RGBA")
    left_occluder = body_occluder(body, (390, 680, 650, 1040))
    right_occluder = body_occluder(body, (1010, 500, 1275, 760))

    left_layer.save(V3 / "60_Foreleg_L_Complete.png")
    right_layer.save(V3 / "61_Foreleg_R_Complete.png")
    left_occluder.save(V3 / "30_Shoulder_Occluder_L.png")
    right_occluder.save(V3 / "31_Shoulder_Occluder_R.png")

    # Cover-pose order: face below forelegs, planet above their shoulder roots.
    qa = composite_scene(
        [
            Image.open(V2 / "00_Stars_Background.png").convert("RGBA"),
            body,
            Image.open(V2 / "20_Eye_L_Whole.png").convert("RGBA"),
            Image.open(V2 / "21_Eye_R_Whole.png").convert("RGBA"),
            left_layer,
            right_layer,
            Image.open(V2 / "50_Planet_Foreground.png").convert("RGBA"),
            left_occluder,
            right_occluder,
        ]
    )
    qa.convert("RGB").save(V3 / "qa-cover-composite.jpg", quality=94)


if __name__ == "__main__":
    main()
