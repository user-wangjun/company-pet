from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import numpy as np


ROOT = Path(__file__).resolve().parent
MASTER = ROOT / "front-master.png"
LAYERS = ROOT / "layers"


def subject_alpha(rgb: np.ndarray) -> np.ndarray:
    """Recover the cat from the near-white generation background."""
    distance = 255 - rgb.min(axis=2)
    alpha = np.clip((distance.astype(np.float32) - 2.0) * 18.0, 0, 255)
    return Image.fromarray(alpha.astype(np.uint8), "L").filter(
        ImageFilter.GaussianBlur(0.55)
    )


def ellipse_mask(size: tuple[int, int], box: tuple[int, int, int, int], blur=1.2):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse(box, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(blur))


def polygon_mask(size: tuple[int, int], points: list[tuple[int, int]], blur=2.0):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(blur))


def isolated(image: Image.Image, mask: Image.Image) -> Image.Image:
    layer = image.copy()
    source_alpha = image.getchannel("A")
    combined = Image.fromarray(
        np.minimum(np.asarray(source_alpha), np.asarray(mask)).astype(np.uint8),
        "L",
    )
    layer.putalpha(combined)
    return layer


def iris_without_pupil(
    rgba: Image.Image,
    center: tuple[int, int],
    pupil_radius: tuple[int, int],
) -> Image.Image:
    """Extend surrounding iris pixels inward so the pupil can move independently."""
    data = np.asarray(rgba.convert("RGBA")).copy()
    cx, cy = center
    rx, ry = pupil_radius
    h, w = data.shape[:2]
    yy, xx = np.ogrid[:h, :w]
    normalized = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    ys, xs = np.where(normalized <= 1.0)
    for y, x in zip(ys, xs):
        dx = x - cx
        dy = y - cy
        length = max((dx * dx + dy * dy) ** 0.5, 0.001)
        sx = int(round(cx + dx / length * (rx + 3)))
        sy = int(round(cy + dy / length * (ry + 3)))
        sx = min(max(sx, 0), w - 1)
        sy = min(max(sy, 0), h - 1)
        data[y, x, :3] = data[sy, sx, :3]
    return Image.fromarray(data, "RGBA")


def patch_closed_eye_base(
    rgba: Image.Image,
    eye_box: tuple[int, int, int, int],
    source_offset_y: int = -60,
) -> None:
    """Replace the fixed eye on the body with nearby forehead fur."""
    x0, y0, x1, y1 = eye_box
    patch = rgba.crop((x0, y0 + source_offset_y, x1, y1 + source_offset_y))
    mask = ellipse_mask(rgba.size, eye_box, blur=4.0).crop(eye_box)
    rgba.paste(patch, (x0, y0), mask)


def make_eyelid(size: tuple[int, int], box: tuple[int, int, int, int]) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    inset = 7
    center_y = (y0 + y1) // 2
    draw.arc(
        (x0 + inset, center_y - 18, x1 - inset, center_y + 10),
        start=15,
        end=165,
        fill=(112, 55, 24, 220),
        width=4,
    )
    return layer.filter(ImageFilter.GaussianBlur(0.35))


def build_psd(layer_specs: dict[str, Image.Image]) -> None:
    """Write a Cubism-importable layered PSD using the local pytoshop tool."""
    try:
        from pytoshop import enums
        from pytoshop.user import nested_layers
    except ImportError:
        return

    psd_layers = []
    for filename in reversed(list(layer_specs)):
        rgba = np.asarray(Image.open(LAYERS / filename).convert("RGBA"))
        channels = {
            enums.ChannelId.red: rgba[:, :, 0],
            enums.ChannelId.green: rgba[:, :, 1],
            enums.ChannelId.blue: rgba[:, :, 2],
            enums.ChannelId.transparency: rgba[:, :, 3],
        }
        psd_layers.append(
            nested_layers.Image(
                name=filename.removesuffix(".png").split("_", 1)[1],
                channels=channels,
                color_mode=enums.ColorMode.rgb,
            )
        )

    psd = nested_layers.nested_layers_to_psd(
        psd_layers,
        enums.ColorMode.rgb,
        # pytoshop's public docs say (height, width), but 1.2.1 consumes
        # this tuple as (width, height).
        size=(555, 775),
        compression=enums.Compression.zip,
    )
    with (ROOT / "xiaoju-login-live2d-source.psd").open("wb") as output:
        psd.write(output)


def main() -> None:
    LAYERS.mkdir(parents=True, exist_ok=True)
    master = Image.open(MASTER).convert("RGB")
    rgba = master.convert("RGBA")
    rgba.putalpha(subject_alpha(np.asarray(master)))
    size = rgba.size

    left_eye = (172, 242, 234, 309)
    right_eye = (287, 242, 349, 309)
    left_pupil = (203, 274)
    right_pupil = (318, 274)

    body = rgba.copy()
    patch_closed_eye_base(body, left_eye)
    patch_closed_eye_base(body, right_eye)

    eye_source = iris_without_pupil(rgba, left_pupil, (13, 19))
    eye_source = iris_without_pupil(eye_source, right_pupil, (13, 19))

    layer_specs = {
        "00_Body_Base.png": body,
        "10_Eye_L_Base.png": isolated(eye_source, ellipse_mask(size, left_eye)),
        "11_Eye_R_Base.png": isolated(eye_source, ellipse_mask(size, right_eye)),
        "20_Pupil_L.png": isolated(rgba, ellipse_mask(size, (190, 254, 216, 295), 0.8)),
        "21_Pupil_R.png": isolated(rgba, ellipse_mask(size, (305, 254, 331, 295), 0.8)),
        "30_Eyelid_L.png": make_eyelid(size, left_eye),
        "31_Eyelid_R.png": make_eyelid(size, right_eye),
        "40_Arm_L_Cover.png": isolated(
            rgba,
            polygon_mask(size, [(92, 420), (155, 395), (227, 454), (239, 684), (176, 725), (105, 690)]),
        ),
        "41_Arm_R_Cover.png": isolated(
            rgba,
            polygon_mask(size, [(328, 454), (400, 395), (463, 420), (450, 690), (379, 725), (316, 684)]),
        ),
    }

    for filename, layer in layer_specs.items():
        layer.save(LAYERS / filename)

    build_psd(layer_specs)

    composite = Image.new("RGBA", size, (0, 0, 0, 0))
    for filename in layer_specs:
        if filename.startswith("3"):
            continue
        composite.alpha_composite(Image.open(LAYERS / filename).convert("RGBA"))
    composite.save(ROOT / "layered-preview-open.png")


if __name__ == "__main__":
    main()
