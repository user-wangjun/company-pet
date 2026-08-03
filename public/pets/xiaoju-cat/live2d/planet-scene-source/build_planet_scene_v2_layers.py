from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from build_planet_scene_layers import (
    BACKGROUND,
    CAT_BODY,
    generated_cutout,
    ellipse_mask,
    isolated,
    make_eyelid,
    patch_eye_base,
    polygon_mask,
)


ROOT = Path(__file__).resolve().parent
LAYERS = ROOT / "layers-v2"
FORELEGS = ROOT / "forelegs-v2-transparent.png"
V1_LAYERS = ROOT / "layers"


def place_foreleg(
    sheet: Image.Image,
    source_box: tuple[int, int, int, int],
    canvas_size: tuple[int, int],
    scale: float,
    rotation: float,
    position: tuple[int, int],
) -> Image.Image:
    limb = sheet.crop(source_box)
    # Fade only the hidden shoulder seam so the limb can tuck beneath the
    # torso without looking like a rounded sticker pasted on top of the cat.
    alpha = limb.getchannel("A")
    shoulder_fade = Image.new("L", limb.size, 255)
    fade_height = max(1, round(limb.height * 0.10))
    fade_draw = ImageDraw.Draw(shoulder_fade)
    for y in range(fade_height):
        fade_draw.line((0, y, limb.width, y), fill=round(255 * y / fade_height))
    alpha = Image.composite(alpha, Image.new("L", limb.size, 0), shoulder_fade)
    limb.putalpha(alpha)
    limb = limb.resize(
        (max(1, round(limb.width * scale)), max(1, round(limb.height * scale))),
        Image.Resampling.LANCZOS,
    )
    if rotation:
        limb = limb.rotate(rotation, Image.Resampling.BICUBIC, expand=True)
    layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    layer.alpha_composite(limb, position)
    return layer


def main() -> None:
    LAYERS.mkdir(parents=True, exist_ok=True)
    background = Image.open(BACKGROUND).convert("RGBA")
    body_source = generated_cutout(CAT_BODY)
    foreleg_sheet = Image.open(FORELEGS).convert("RGBA")
    size = background.size

    left_eye = (642, 490, 775, 610)
    right_eye = (870, 420, 990, 545)

    # Fill the sockets with adjacent facial fur, then overlay the original,
    # intact eyes as moving art meshes. This avoids the radial iris artifacts
    # produced by the v1 pupil-hole reconstruction.
    body = body_source.copy()
    patch_eye_base(body, left_eye, -110)
    patch_eye_base(body, right_eye, -105)

    left_foreleg = place_foreleg(
        foreleg_sheet,
        (205, 104, 549, 1024),
        size,
        scale=0.18,
        rotation=12,
        position=(585, 650),
    )
    right_foreleg = place_foreleg(
        foreleg_sheet,
        (841, 107, 1171, 1036),
        size,
        scale=0.16,
        rotation=74,
        position=(985, 540),
    )

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
    rest_paw_left = Image.open(V1_LAYERS / "60_Paw_L.png").convert("RGBA")
    rest_paw_right = Image.open(V1_LAYERS / "61_Paw_R.png").convert("RGBA")

    layer_specs = [
        ("00_Stars_Background.png", background),
        ("10_Cat_Body_Base.png", body),
        ("20_Eye_L_Whole.png", isolated(body_source, ellipse_mask(size, left_eye, 1.2))),
        ("21_Eye_R_Whole.png", isolated(body_source, ellipse_mask(size, right_eye, 1.2))),
        ("40_Eyelid_L.png", make_eyelid(size, left_eye)),
        ("41_Eyelid_R.png", make_eyelid(size, right_eye)),
        ("50_Planet_Foreground.png", planet),
        ("60_Rest_Paw_L.png", rest_paw_left),
        ("61_Rest_Paw_R.png", rest_paw_right),
        ("70_Cover_Foreleg_L.png", left_foreleg),
        ("71_Cover_Foreleg_R.png", right_foreleg),
    ]

    for filename, layer in layer_specs:
        layer.save(LAYERS / filename)

    preview = Image.new("RGBA", size, (0, 0, 0, 0))
    for filename, layer in layer_specs:
        if filename.startswith("4") or filename.startswith("7"):
            continue
        preview.alpha_composite(layer)
    preview.save(ROOT / "planet-scene-v2-layered-preview.png")


if __name__ == "__main__":
    main()
