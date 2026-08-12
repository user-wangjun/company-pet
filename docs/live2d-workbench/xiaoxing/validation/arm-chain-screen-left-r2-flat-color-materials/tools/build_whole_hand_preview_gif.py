from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageChops, ImageDraw, ImageFont


R2_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ROOT = R2_ROOT / "candidates" / "upper-arm-aa-anatomical-v8"
OUTPUT_ROOT = R2_ROOT / "previews" / "whole-hand-v8"
CANVAS = (512, 1086)

SHOULDER_PIVOT = (166.0, 270.0)
ELBOW_PIVOT = (149.0, 399.0)
WRIST_PIVOT = (110.0, 538.0)

# This is the existing R2 diagnostic pose arc plus a small independent wrist
# flex.  It is intentionally a preview-only motion blockout; it is not a
# Cubism/runtime motion contract.
POSES = (
    ("00-rest", 0.0, 0.0, 0.0),
    ("01-raise-1", -12.0, 30.0, -4.0),
    ("02-raise-2", -24.0, 65.0, -8.0),
    ("03-raise-3", -36.0, 100.0, -12.0),
    ("04-raise-4", -48.0, 135.0, -16.0),
    ("05-raise-peak", -52.0, 155.0, -20.0),
    ("06-lower-4", -48.0, 135.0, -16.0),
    ("07-lower-3", -36.0, 100.0, -12.0),
    ("08-lower-2", -24.0, 65.0, -8.0),
    ("09-lower-1", -12.0, 30.0, -4.0),
    ("10-return", 0.0, 0.0, 0.0),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def rotate_point(point: tuple[float, float], center: tuple[float, float], angle: float) -> tuple[float, float]:
    """Forward-map a point using Pillow's image-space rotation convention."""
    theta = math.radians(angle)
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    dx = point[0] - center[0]
    dy = point[1] - center[1]
    return (
        center[0] + cos_theta * dx + sin_theta * dy,
        center[1] - sin_theta * dx + cos_theta * dy,
    )


def transform_with_rotations(
    image: Image.Image,
    rotations: Iterable[tuple[tuple[float, float], float]],
) -> Image.Image:
    """Compose rigid rotations and resample once with bicubic coverage."""
    matrix = (1.0, 0.0, 0.0, 1.0)
    translation = (0.0, 0.0)
    for center, angle in rotations:
        theta = math.radians(angle)
        a = math.cos(theta)
        b = math.sin(theta)
        d = -math.sin(theta)
        e = math.cos(theta)
        cx, cy = center
        rotation_translation = (cx - a * cx - b * cy, cy - d * cx - e * cy)
        ma, mb, md, me = matrix
        tx, ty = translation
        matrix = (
            a * ma + b * md,
            a * mb + b * me,
            d * ma + e * md,
            d * mb + e * me,
        )
        translation = (
            a * tx + b * ty + rotation_translation[0],
            d * tx + e * ty + rotation_translation[1],
        )

    a, b, d, e = matrix
    tx, ty = translation
    inverse = (
        e,
        -b,
        -(e * tx - b * ty),
        -d,
        a,
        -(-d * tx + a * ty),
    )
    return image.transform(
        CANVAS,
        Image.Transform.AFFINE,
        inverse,
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    ).convert("RGBA")


def alpha_composite_layers(layers: Iterable[Image.Image]) -> Image.Image:
    result = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer in layers:
        result.alpha_composite(layer)
    return result


def load_layer(relative: str, candidate: bool = False) -> Image.Image:
    root = CANDIDATE_ROOT if candidate else R2_ROOT
    path = root / relative
    if not path.exists():
        raise FileNotFoundError(path)
    image = Image.open(path).convert("RGBA")
    if image.size != CANVAS:
        raise ValueError(f"unexpected canvas for {path}: {image.size}")
    return image


def load_alpha(relative: str) -> Image.Image:
    path = R2_ROOT / relative
    if not path.exists():
        raise FileNotFoundError(path)
    image = Image.open(path).convert("L")
    if image.size != CANVAS:
        raise ValueError(f"unexpected canvas for {path}: {image.size}")
    return image


def colored_alpha_layer(alpha: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    layer = Image.new("RGBA", CANVAS, (*color, 0))
    layer.putalpha(alpha)
    return layer


def build_frame(
    layers: dict[str, Image.Image],
    shoulder_angle: float,
    elbow_angle: float,
    wrist_angle: float,
) -> Image.Image:
    upper_arm = transform_with_rotations(layers["upper_arm"], [(SHOULDER_PIVOT, shoulder_angle)])
    sleeve = transform_with_rotations(layers["sleeve"], [(SHOULDER_PIVOT, shoulder_angle)])
    child_rotations = [(ELBOW_PIVOT, elbow_angle), (SHOULDER_PIVOT, shoulder_angle)]
    hand_rotations = [(WRIST_PIVOT, wrist_angle), *child_rotations]
    bracelet_back = transform_with_rotations(layers["bracelet-back"], child_rotations)
    forearm = transform_with_rotations(layers["forearm"], child_rotations)
    hand_hidden = transform_with_rotations(layers["hand-hidden"], hand_rotations)
    hand = transform_with_rotations(layers["hand"], hand_rotations)
    bracelet_front = transform_with_rotations(layers["bracelet-front"], child_rotations)

    # The protected hidden hand root is rendered behind forearm/bracelet. It
    # closes the moving wrist without painting over the visible bracelet.
    return alpha_composite_layers(
        [upper_arm, sleeve, hand_hidden, bracelet_back, forearm, hand, bracelet_front]
    )


def opaque_white(image: Image.Image) -> Image.Image:
    background = Image.new("RGBA", CANVAS, (255, 255, 255, 255))
    background.alpha_composite(image)
    return background.convert("RGB")


def count_components(alpha: Image.Image, threshold: int = 8) -> int:
    pixels = alpha.load()
    width, height = alpha.size
    visited = bytearray(width * height)
    components = 0
    bbox = alpha.getbbox()
    if bbox is None:
        return 0
    left, top, right, bottom = bbox
    for y in range(top, bottom):
        for x in range(left, right):
            index = y * width + x
            if visited[index] or pixels[x, y] <= threshold:
                continue
            components += 1
            visited[index] = 1
            queue = [index]
            while queue:
                current = queue.pop()
                cx = current % width
                cy = current // width
                for ny in range(max(top, cy - 1), min(bottom, cy + 2)):
                    for nx in range(max(left, cx - 1), min(right, cx + 2)):
                        neighbor = ny * width + nx
                        if visited[neighbor] or pixels[nx, ny] <= threshold:
                            continue
                        visited[neighbor] = 1
                        queue.append(neighbor)
    return components


def remove_tiny_alpha_islands(image: Image.Image, threshold: int = 8, minimum_size: int = 4) -> tuple[Image.Image, int]:
    """Remove isolated bicubic ringing while preserving the connected AA body."""
    alpha = image.getchannel("A")
    pixels = alpha.load()
    width, height = alpha.size
    visited = bytearray(width * height)
    removed = 0
    bbox = alpha.getbbox()
    if bbox is None:
        return image, removed
    left, top, right, bottom = bbox
    for y in range(top, bottom):
        for x in range(left, right):
            index = y * width + x
            if visited[index] or pixels[x, y] <= threshold:
                continue
            visited[index] = 1
            queue = [index]
            component: list[int] = []
            while queue:
                current = queue.pop()
                component.append(current)
                cx = current % width
                cy = current // width
                for ny in range(max(top, cy - 1), min(bottom, cy + 2)):
                    for nx in range(max(left, cx - 1), min(right, cx + 2)):
                        neighbor = ny * width + nx
                        if visited[neighbor] or pixels[nx, ny] <= threshold:
                            continue
                        visited[neighbor] = 1
                        queue.append(neighbor)
            if len(component) < minimum_size:
                for current in component:
                    pixels[current % width, current // width] = 0
                removed += len(component)
    cleaned = image.copy()
    cleaned.putalpha(alpha)
    return cleaned, removed


def overlap_pixels(first: Image.Image, second: Image.Image, threshold: int = 8) -> int:
    first_px = first.load()
    second_px = second.load()
    return sum(
        1
        for y in range(CANVAS[1])
        for x in range(CANVAS[0])
        if first_px[x, y] > threshold and second_px[x, y] > threshold
    )


def union_bbox(images: Iterable[Image.Image], margin: int = 18) -> tuple[int, int, int, int]:
    boxes = [image.getchannel("A").getbbox() for image in images]
    boxes = [box for box in boxes if box is not None]
    if not boxes:
        raise ValueError("all preview frames are empty")
    left = max(0, min(box[0] for box in boxes) - margin)
    top = max(0, min(box[1] for box in boxes) - margin)
    right = min(CANVAS[0], max(box[2] for box in boxes) + margin)
    bottom = min(CANVAS[1], max(box[3] for box in boxes) + margin)
    return (left, top, right, bottom)


def crop_preview(image: Image.Image, crop: tuple[int, int, int, int], scale: int = 2) -> Image.Image:
    cropped = image.crop(crop)
    return cropped.resize((cropped.width * scale, cropped.height * scale), Image.Resampling.BICUBIC)


def make_contact_sheet(
    frames: list[Image.Image],
    pose_meta: list[dict[str, float | str]],
    crop: tuple[int, int, int, int],
) -> Image.Image:
    scale = 1
    tile = crop_preview(frames[0], crop, scale)
    tile_w, tile_h = tile.size
    cols = 3
    rows = math.ceil(len(frames) / cols)
    margin = 18
    header_h = 82
    footer_h = 48
    board = Image.new(
        "RGB",
        (margin + cols * (tile_w + margin), header_h + margin + rows * (tile_h + footer_h + margin)),
        (238, 243, 247),
    )
    draw = ImageDraw.Draw(board)
    draw.rectangle((0, 0, board.width, header_h), fill=(28, 42, 58))
    draw.text((margin, 16), "小星 Left｜整只手抬臂预览｜含独立腕部小幅转动", fill=(255, 255, 255), font=font(22, True))
    draw.text((margin, 49), "v8 upper_arm + R2 forearm/bracelet/hand｜preview only｜不是 Runtime/Cubism 证据", fill=(209, 226, 238), font=font(14))
    for index, (frame, meta) in enumerate(zip(frames, pose_meta)):
        x = margin + (index % cols) * (tile_w + margin)
        y = header_h + margin + (index // cols) * (tile_h + footer_h + margin)
        draw.rounded_rectangle((x, y, x + tile_w, y + tile_h + footer_h), radius=8, fill=(255, 255, 255), outline=(178, 191, 204), width=2)
        board.paste(crop_preview(frame, crop, scale), (x, y))
        draw.text((x + 8, y + tile_h + 10), f"{meta['id']}  S={meta['shoulderAngle']:.0f}°  E={meta['elbowAngle']:.0f}°  W={meta['wristAngle']:.0f}°", fill=(28, 42, 58), font=font(14, True))
    return board


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    layers = {
        "upper_arm": load_layer("flat-layers/upper_arm.png", candidate=True),
        "sleeve": load_layer("flat-layers/sleeve.png"),
        "forearm": load_layer("flat-layers/forearm.png"),
        "bracelet-back": load_layer("flat-layers/bracelet-back.png"),
        "bracelet-front": load_layer("flat-layers/bracelet-front.png"),
        "hand": load_layer("flat-layers/hand.png"),
        "hand-hidden": colored_alpha_layer(load_alpha("display-alpha/hand-hidden.png"), (179, 91, 190)),
    }
    frames = []
    pose_meta = []
    diagnostics = []
    for frame_id, shoulder_angle, elbow_angle, wrist_angle in POSES:
        frame, removed_islands = remove_tiny_alpha_islands(build_frame(layers, shoulder_angle, elbow_angle, wrist_angle))
        frames.append(frame)
        pose_meta.append({"id": frame_id, "shoulderAngle": shoulder_angle, "elbowAngle": elbow_angle, "wristAngle": wrist_angle})
        alpha = frame.getchannel("A")
        upper = transform_with_rotations(layers["upper_arm"], [(SHOULDER_PIVOT, shoulder_angle)]).getchannel("A")
        child_rotations = [(ELBOW_PIVOT, elbow_angle), (SHOULDER_PIVOT, shoulder_angle)]
        forearm = transform_with_rotations(layers["forearm"], child_rotations).getchannel("A")
        hand_rotations = [(WRIST_PIVOT, wrist_angle), *child_rotations]
        hand_visible = transform_with_rotations(layers["hand"], hand_rotations).getchannel("A")
        hand_hidden = transform_with_rotations(layers["hand-hidden"], hand_rotations).getchannel("A")
        hand = ImageChops.lighter(hand_visible, hand_hidden)
        elbow_point = rotate_point(ELBOW_PIVOT, SHOULDER_PIVOT, shoulder_angle)
        wrist_after_elbow = rotate_point(WRIST_PIVOT, ELBOW_PIVOT, elbow_angle)
        wrist_point = rotate_point(wrist_after_elbow, SHOULDER_PIVOT, shoulder_angle)
        diagnostics.append(
            {
                "id": frame_id,
                "shoulderAngle": shoulder_angle,
                "elbowAngle": elbow_angle,
                "wristAngle": wrist_angle,
                "bbox": list(alpha.getbbox() or (0, 0, 0, 0)),
                "connectedComponentsAtAlphaGt8": count_components(alpha),
                "tinyAlphaIslandsRemoved": removed_islands,
                "elbowOverlapPixels": overlap_pixels(upper, forearm),
                "wristOverlapPixels": overlap_pixels(forearm, hand),
                "elbowPoint": [round(value, 3) for value in elbow_point],
                "wristPoint": [round(value, 3) for value in wrist_point],
            }
        )

    crop = union_bbox(frames)
    gif_frames = [crop_preview(opaque_white(frame), crop, scale=2).convert("P", palette=Image.Palette.ADAPTIVE, colors=256, dither=Image.Dither.NONE) for frame in frames]
    gif_path = OUTPUT_ROOT / "whole-hand-v8-preview.gif"
    gif_frames[0].save(
        gif_path,
        format="GIF",
        save_all=True,
        append_images=gif_frames[1:],
        duration=130,
        loop=0,
        optimize=False,
        disposal=2,
    )

    contact_path = OUTPUT_ROOT / "whole-hand-v8-contact-sheet.png"
    make_contact_sheet([opaque_white(frame) for frame in frames], pose_meta, crop).save(contact_path, format="PNG", optimize=False, compress_level=9)

    input_paths = {
        "candidateUpperArm": CANDIDATE_ROOT / "flat-layers/upper_arm.png",
        "r2Sleeve": R2_ROOT / "flat-layers/sleeve.png",
        "r2Forearm": R2_ROOT / "flat-layers/forearm.png",
        "r2BraceletBack": R2_ROOT / "flat-layers/bracelet-back.png",
        "r2BraceletFront": R2_ROOT / "flat-layers/bracelet-front.png",
        "r2Hand": R2_ROOT / "flat-layers/hand.png",
        "r2HandHidden": R2_ROOT / "display-alpha/hand-hidden.png",
    }
    report = {
        "schemaVersion": 1,
        "stage": "WHOLE_HAND_PREVIEW_GIF",
        "status": "PREVIEW_ONLY / FORMAL_LAYER_UNCHANGED",
        "sourceCanvas": list(CANVAS),
        "crop": list(crop),
        "scale": 2,
        "frameCount": len(frames),
        "durationMs": 130,
        "loop": True,
        "transformOrder": [
            "upper_arm and sleeve <- shoulder rotation",
            "forearm, bracelet-back, bracelet-front, hand <- elbow fold then shoulder rotation",
            "hand <- small local wrist rotation before inheriting elbow and shoulder transforms",
            "hand hidden wrist root <- same wrist rotation, behind forearm and bracelet",
            "bracelet depth order = back -> forearm skin -> hand -> front",
        ],
        "pivots": {
            "shoulder": list(SHOULDER_PIVOT),
            "elbow": list(ELBOW_PIVOT),
            "wrist": list(WRIST_PIVOT),
        },
        "inputs": {key: {"path": str(path.relative_to(R2_ROOT)).replace("\\", "/"), "sha256": sha256_file(path)} for key, path in input_paths.items()},
        "outputs": {
            "gif": {"path": str(gif_path.relative_to(R2_ROOT)).replace("\\", "/"), "sha256": sha256_file(gif_path)},
            "contactSheet": {"path": str(contact_path.relative_to(R2_ROOT)).replace("\\", "/"), "sha256": sha256_file(contact_path)},
        },
        "checks": {
            "allFramesHaveVisiblePixels": all(item["bbox"] != [0, 0, 0, 0] for item in diagnostics),
            "allFramesSingleConnectedArmChainAtAlphaGt8": all(item["connectedComponentsAtAlphaGt8"] == 1 for item in diagnostics),
            "allElbowOverlapsPositive": all(item["elbowOverlapPixels"] > 0 for item in diagnostics),
            "allWristOverlapsPositive": all(item["wristOverlapPixels"] > 0 for item in diagnostics),
            "bicubicRingingIslandsRemoved": sum(int(item["tinyAlphaIslandsRemoved"]) for item in diagnostics),
            "hiddenWristRootIncludedInPreview": True,
        },
        "formalGate": {
            "engineeringPass": None,
            "userVisualApproval": None,
            "overallGatePass": False,
            "formalR2Promotion": False,
            "reason": "GIF is a user-facing preview only; it does not replace direct visual approval of the latest bounded material or the formal R2 gate.",
        },
        "frames": diagnostics,
    }
    (OUTPUT_ROOT / "preview-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"gif": str(gif_path), "contactSheet": str(contact_path), "crop": crop, "checks": report["checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
