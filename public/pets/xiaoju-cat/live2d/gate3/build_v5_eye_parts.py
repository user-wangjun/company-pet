import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parents[1]
SOURCE = PACKAGE / "live2d" / "planet-scene-source" / "layers-v2"
PARTS = ROOT / "parts-v5" / "micro"
QA = ROOT / "qa"
CANVAS = (1370, 1148)

EYES = {
    "L": {"file": "20_Eye_L_Whole.png", "lid": "40_Eyelid_L.png", "center": (708, 549), "radius": (34, 40)},
    "R": {"file": "21_Eye_R_Whole.png", "lid": "41_Eyelid_R.png", "center": (929, 484), "radius": (33, 39)},
}


def ellipse_mask(center: tuple[int, int], radius: tuple[int, int], feather: float = 0) -> Image.Image:
    cx, cy = center
    rx, ry = radius
    mask = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(mask).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    return mask.filter(ImageFilter.GaussianBlur(feather)) if feather else mask


def clean_iris(whole: Image.Image, center: tuple[int, int], radius: tuple[int, int]) -> Image.Image:
    result = whole.copy()
    cx, cy = center
    rx, ry = radius
    mask = ellipse_mask(center, radius, feather=5)
    fill = Image.new("RGBA", CANVAS, (202, 128, 24, 255))

    # Preserve a cat-eye amber gradient while removing every fixed black pupil
    # and specular highlight from the gaze underpaint.
    pixels = fill.load()
    for y in range(cy - ry - 8, cy + ry + 9):
        for x in range(cx - rx - 8, cx + rx + 9):
            if 0 <= x < CANVAS[0] and 0 <= y < CANVAS[1]:
                vertical = (y - cy) / max(1, ry)
                shade = -42 if vertical < -0.1 else 24 if vertical > 0.25 else 0
                pixels[x, y] = (max(0, 202 + shade), max(0, 128 + shade // 2), max(0, 24 + shade // 5), 255)
    result = Image.composite(fill, result, mask)
    result.putalpha(whole.getchannel("A"))
    return result


def split_pupil_highlight(whole: Image.Image, center: tuple[int, int], radius: tuple[int, int]) -> tuple[Image.Image, Image.Image]:
    pupil_mask = ellipse_mask(center, radius)
    pupil = whole.copy()
    pupil.putalpha(ImageChops.multiply(whole.getchannel("A"), pupil_mask))

    cx, cy = center
    region = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(region).ellipse((cx - 22, cy - 36, cx + 12, cy + 2), fill=255)
    highlight_mask = Image.new("L", CANVAS, 0)
    source_pixels = whole.load()
    target_pixels = highlight_mask.load()
    region_pixels = region.load()
    for y in range(cy - 38, cy + 4):
        for x in range(cx - 24, cx + 14):
            r, g, b, a = source_pixels[x, y]
            if region_pixels[x, y] and a > 20 and min(r, g, b) > 190:
                target_pixels[x, y] = a
    highlight_mask = highlight_mask.filter(ImageFilter.GaussianBlur(0.7))
    highlight = whole.copy()
    highlight.putalpha(highlight_mask)

    # The pupil layer must not retain its original white glint; the glint moves
    # as a separate child of the same eyeball deformer.
    dark = Image.new("RGBA", CANVAS, (30, 20, 8, 255))
    pupil = Image.composite(dark, pupil, highlight_mask)
    pupil.putalpha(ImageChops.multiply(pupil.getchannel("A"), pupil_mask))
    return pupil, highlight


def translated(image: Image.Image, dx: int, dy: int) -> Image.Image:
    result = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    result.alpha_composite(image, (dx, dy))
    return result


def alpha_outside(moving: Image.Image, aperture: Image.Image) -> int:
    outside = ImageChops.subtract(moving.getchannel("A"), aperture.getchannel("A"))
    return sum(value > 0 for value in outside.get_flattened_data())


def clipped(image: Image.Image, aperture: Image.Image) -> Image.Image:
    result = image.copy()
    result.putalpha(ImageChops.multiply(image.getchannel("A"), aperture.getchannel("A")))
    return result


def vertical_eye_scale(image: Image.Image, center_y: int, openness: float) -> Image.Image:
    if openness <= 0.02:
        return Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    # Inverse affine map around the anatomical lid axis.
    return image.transform(
        CANVAS,
        Image.Transform.AFFINE,
        (1, 0, 0, 0, 1 / openness, center_y - center_y / openness),
        Image.Resampling.BICUBIC,
    )


def main() -> None:
    PARTS.mkdir(parents=True, exist_ok=True)
    built = {}
    report = {"schemaVersion": 1, "gazeRangePx": {"x": [-12, 12], "y": [-8, 8]}, "eyes": {}}
    for side, spec in EYES.items():
        whole = Image.open(SOURCE / spec["file"]).convert("RGBA")
        lid = Image.open(SOURCE / spec["lid"]).convert("RGBA")
        iris = clean_iris(whole, spec["center"], spec["radius"])
        pupil, highlight = split_pupil_highlight(whole, spec["center"], spec["radius"])
        clip_mask = Image.new("RGBA", CANVAS, (255, 255, 255, 0))
        clip_mask.putalpha(whole.getchannel("A"))
        outputs = {
            f"70_Iris_{side}_Clean_v5.png": iris,
            f"71_Pupil_{side}_v5.png": pupil,
            f"72_Highlight_{side}_v5.png": highlight,
            f"73_ClosedLidLine_{side}_v5.png": lid,
            f"74_EyeWhole_{side}_Safety_HIDDEN.png": whole,
            f"75_EyeClipMask_{side}_v5.png": clip_mask,
        }
        for name, image in outputs.items():
            image.save(PARTS / name)
            built[name] = image

        cx, cy = spec["center"]
        rx, ry = spec["radius"]
        iris_pixels = iris.load()
        dark_inside = 0
        for y in range(cy - ry + 5, cy + ry - 4):
            for x in range(cx - rx + 5, cx + rx - 4):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 0.72 ** 2:
                    r, g, b, a = iris_pixels[x, y]
                    dark_inside += a > 20 and max(r, g, b) < 55

        extremes = {}
        clipped_extremes = {}
        for label, (dx, dy) in {"left": (-12, 0), "right": (12, 0), "up": (0, -8), "down": (0, 8)}.items():
            moving = translated(pupil, dx, dy)
            extremes[label] = alpha_outside(moving, whole)
            clipped_extremes[label] = alpha_outside(clipped(moving, whole), whole)
        report["eyes"][side] = {
            "cleanIrisDarkResidualPixels": dark_inside,
            "rawPupilOutsideAperturePixels": extremes,
            "clippedPupilOutsideAperturePixels": clipped_extremes,
            "requiresClippingMask": True,
            "pass": dark_inside == 0 and max(clipped_extremes.values()) == 0,
        }

    # Eye-only contact sheet at center and four gaze extremes. The checker
    # background makes residual pupil ghosts and alpha spill immediately visible.
    cell_w, cell_h = 260, 190
    positions = [("LEFT", -12, 0), ("CENTER", 0, 0), ("RIGHT", 12, 0), ("UP", 0, -8), ("DOWN", 0, 8)]
    sheet = Image.new("RGBA", (cell_w * len(positions), cell_h * 2), (20, 22, 28, 255))
    draw = ImageDraw.Draw(sheet)
    for column, (label, dx, dy) in enumerate(positions):
        draw.text((column * cell_w + 10, 8), label, fill=(255, 255, 255, 255))
        for row, side in enumerate(("L", "R")):
            iris = built[f"70_Iris_{side}_Clean_v5.png"]
            aperture = built[f"74_EyeWhole_{side}_Safety_HIDDEN.png"]
            pupil = clipped(translated(built[f"71_Pupil_{side}_v5.png"], dx, dy), aperture)
            highlight = clipped(translated(built[f"72_Highlight_{side}_v5.png"], dx, dy), aperture)
            composite = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
            composite.alpha_composite(iris)
            composite.alpha_composite(pupil)
            composite.alpha_composite(highlight)
            bbox = iris.getchannel("A").getbbox()
            crop = composite.crop((bbox[0] - 12, bbox[1] - 12, bbox[2] + 12, bbox[3] + 12))
            crop.thumbnail((230, 130), Image.Resampling.LANCZOS)
            x = column * cell_w + (cell_w - crop.width) // 2
            y = row * cell_h + 42 + (135 - crop.height) // 2
            sheet.alpha_composite(crop, (x, y))
    sheet_path = QA / "gate3-v5-gaze-extremes-contact-sheet.png"
    sheet.save(sheet_path)

    # Blink proof uses the approved closed-eye head underpaint. Open eye meshes
    # collapse vertically into the lid axis; the closed line appears only near
    # zero, avoiding a frame-switched eye image.
    head = Image.open(SOURCE / "10_Cat_Body_Base.png").convert("RGBA")
    blink_sheet = Image.new("RGBA", (450 * 5, 430), (20, 22, 28, 255))
    blink_draw = ImageDraw.Draw(blink_sheet)
    for index, openness in enumerate((1.0, 0.72, 0.42, 0.16, 0.0)):
        frame = head.copy()
        for side, spec in EYES.items():
            eye = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
            eye.alpha_composite(built[f"70_Iris_{side}_Clean_v5.png"])
            eye.alpha_composite(built[f"71_Pupil_{side}_v5.png"])
            eye.alpha_composite(built[f"72_Highlight_{side}_v5.png"])
            frame.alpha_composite(vertical_eye_scale(eye, spec["center"][1], openness))
            if openness <= 0.18:
                lid = built[f"73_ClosedLidLine_{side}_v5.png"].copy()
                lid.putalpha(lid.getchannel("A").point(lambda value: round(value * (1 - openness / 0.18))))
                frame.alpha_composite(lid)
        crop = frame.crop((500, 300, 1100, 760))
        crop.thumbnail((430, 360), Image.Resampling.LANCZOS)
        x = index * 450 + (450 - crop.width) // 2
        y = 52 + (360 - crop.height) // 2
        blink_sheet.alpha_composite(crop, (x, y))
        blink_draw.text((index * 450 + 12, 16), f"ParamEyeOpen={openness:.2f}", fill=(255, 255, 255, 255))
    blink_path = QA / "gate3-v5-blink-contact-sheet.png"
    blink_sheet.save(blink_path)

    report["pass"] = all(item["pass"] for item in report["eyes"].values())
    report["gate3Pass"] = False
    report["gate3Blocker"] = "blink fur deformation and PSD/Cubism import are not yet visually validated"
    report_path = QA / "gate3-v5-eye-parts-audit.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(PARTS)
    print(sheet_path)
    print(blink_path)
    print(report_path)
    print(f"eyeParts={len(built)} technicalPass={str(report['pass']).lower()} gate3Pass=false")


if __name__ == "__main__":
    main()
