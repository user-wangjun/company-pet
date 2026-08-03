from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
LAYERS = ROOT / "generated-complete-layer-candidates-v15"
ASSEMBLED = ROOT / "generated-layer-assembly-v16"
QA = ROOT / "qa"
CONTRACT = ROOT / "x6-generated-layer-assembly-contract-v16.json"
CANVAS = (620, 820)


def font(size: int):
    for path in (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/msyh.ttc")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def checker(size: tuple[int, int], step: int = 22) -> Image.Image:
    out = Image.new("RGBA", size, (246, 248, 250, 255))
    draw = ImageDraw.Draw(out)
    for y in range(0, size[1], step):
        for x in range(0, size[0], step):
            if (x // step + y // step) % 2:
                draw.rectangle((x, y, min(size[0], x + step), min(size[1], y + step)), fill=(224, 230, 235, 255))
    return out


def layer_path(view: str, semantic: str) -> Path:
    matches = list((LAYERS / view).glob(f"*_{view}_{semantic}.png"))
    if len(matches) != 1:
        raise ValueError(f"Expected one layer for {view}:{semantic}, found {matches}")
    return matches[0]


def placed_layer(view: str, semantic: str, placement: dict, offset: tuple[int, int] = (0, 0)) -> Image.Image:
    source = Image.open(layer_path(view, semantic)).convert("RGBA")
    target_h = placement["height"]
    target_w = max(1, round(source.width * target_h / source.height))
    source = source.resize((target_w, target_h), Image.Resampling.LANCZOS)
    if placement.get("mirror"):
        source = source.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if placement.get("angle", 0):
        source = source.rotate(placement["angle"], Image.Resampling.BICUBIC, expand=True)
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    cx = placement["center"][0] + offset[0]
    cy = placement["center"][1] + offset[1]
    x = round(cx - source.width / 2)
    y = round(cy - source.height / 2)
    canvas.alpha_composite(source, (x, y))
    return canvas


PLACEMENTS = {
    "front": {
        "tail": {"center": (310, 686), "height": 268, "angle": 0},
        "leg_L_lower_paw": {"center": (137, 674), "height": 184, "angle": -48},
        "leg_R_lower_paw": {"center": (483, 674), "height": 184, "angle": 48},
        "leg_L_upper": {"center": (219, 574), "height": 196, "angle": -30},
        "leg_R_upper": {"center": (401, 574), "height": 196, "angle": 30},
        "arm_L_lower_paw": {"center": (104, 408), "height": 178, "angle": -57},
        "arm_R_lower_paw": {"center": (516, 408), "height": 178, "angle": 57},
        "arm_L_upper": {"center": (193, 337), "height": 178, "angle": -48},
        "arm_R_upper": {"center": (427, 337), "height": 178, "angle": 48},
        "body_base": {"center": (310, 478), "height": 450, "angle": 0},
        "ear_L": {"center": (224, 104), "height": 152, "angle": -7},
        "ear_R": {"center": (396, 104), "height": 152, "angle": 7},
        "head_base": {"center": (310, 206), "height": 230, "angle": 0},
        "eye_L": {"center": (268, 203), "height": 59, "angle": 0},
        "eye_R": {"center": (352, 203), "height": 59, "angle": 0},
        "muzzle_mouth": {"center": (310, 258), "height": 72, "angle": 0},
    },
    "side": {
        "tail": {"center": (438, 660), "height": 278, "angle": 7},
        "leg_far_lower_paw": {"center": (193, 685), "height": 178, "angle": -55},
        "leg_far_upper": {"center": (283, 585), "height": 194, "angle": -31},
        "arm_far_lower_paw": {"center": (116, 437), "height": 166, "angle": -63},
        "arm_far_upper": {"center": (213, 363), "height": 170, "angle": -52},
        "leg_near_lower_paw": {"center": (143, 666), "height": 184, "angle": -58},
        "leg_near_upper": {"center": (270, 565), "height": 205, "angle": -33},
        "arm_near_lower_paw": {"center": (93, 411), "height": 176, "angle": -66},
        "arm_near_upper": {"center": (201, 337), "height": 182, "angle": -54},
        "body_base": {"center": (340, 476), "height": 500, "angle": 0},
        "ear_far": {"center": (290, 105), "height": 128, "angle": 2},
        "ear_near": {"center": (239, 102), "height": 154, "angle": -5},
        "head_base": {"center": (256, 205), "height": 235, "angle": 0},
        "eye_far": {"center": (257, 205), "height": 45, "angle": 0},
        "eye_near": {"center": (208, 204), "height": 56, "angle": 0},
        "muzzle_mouth": {"center": (169, 258), "height": 66, "angle": 0},
    },
    "back": {
        "tail": {"center": (310, 684), "height": 275, "angle": 0},
        "leg_L_lower_paw": {"center": (139, 674), "height": 184, "angle": -48},
        "leg_R_lower_paw": {"center": (481, 674), "height": 184, "angle": 48, "mirror": True},
        "leg_L_upper": {"center": (220, 574), "height": 196, "angle": -30},
        "leg_R_upper": {"center": (400, 574), "height": 196, "angle": 30},
        "arm_L_lower_paw": {"center": (105, 409), "height": 178, "angle": -57},
        "arm_R_lower_paw": {"center": (515, 409), "height": 178, "angle": 57},
        "arm_L_upper": {"center": (194, 338), "height": 178, "angle": -48},
        "arm_R_upper": {"center": (426, 338), "height": 178, "angle": 48},
        "pelvis_tailroot_fill": {"center": (310, 572), "height": 125, "angle": 0},
        "scapula_fill_L": {"center": (240, 350), "height": 118, "angle": -8},
        "scapula_fill_R": {"center": (380, 350), "height": 118, "angle": 8},
        "body_base": {"center": (310, 478), "height": 452, "angle": 0},
        "ear_L": {"center": (224, 102), "height": 150, "angle": -7},
        "ear_R": {"center": (396, 102), "height": 150, "angle": 7},
        "head_base": {"center": (310, 205), "height": 232, "angle": 0},
    },
}

DRAW_ORDER = {
    "front": [
        "tail", "leg_L_lower_paw", "leg_R_lower_paw", "leg_L_upper", "leg_R_upper",
        "arm_L_lower_paw", "arm_R_lower_paw", "arm_L_upper", "arm_R_upper",
        "ear_L", "ear_R", "head_base", "body_base", "eye_L", "eye_R", "muzzle_mouth",
    ],
    "side": [
        "tail", "leg_far_lower_paw", "leg_far_upper", "arm_far_lower_paw", "arm_far_upper",
        "leg_near_lower_paw", "leg_near_upper", "arm_near_lower_paw", "arm_near_upper",
        "ear_far", "ear_near", "eye_far", "head_base", "body_base", "eye_near", "muzzle_mouth",
    ],
    "back": [
        "tail", "leg_L_lower_paw", "leg_R_lower_paw", "leg_L_upper", "leg_R_upper",
        "arm_L_lower_paw", "arm_R_lower_paw", "arm_L_upper", "arm_R_upper",
        "pelvis_tailroot_fill", "scapula_fill_L", "scapula_fill_R",
        "ear_L", "ear_R", "head_base", "body_base",
    ],
}

PULL_OFFSETS = {
    "front": {
        "arm_L_upper": (-8, 4), "arm_L_lower_paw": (-15, 10),
        "leg_L_upper": (-6, 4), "leg_L_lower_paw": (-13, 9), "tail": (0, 9),
    },
    "side": {
        "arm_near_upper": (-8, 4), "arm_near_lower_paw": (-15, 9),
        "leg_near_upper": (-7, 4), "leg_near_lower_paw": (-14, 9), "tail": (5, 8),
    },
    "back": {
        "arm_R_upper": (8, 4), "arm_R_lower_paw": (15, 10),
        "leg_R_upper": (6, 4), "leg_R_lower_paw": (13, 9), "tail": (0, 9),
    },
}

JOINTS = {
    "front": [
        ("body_base", "head_base", "neck"), ("body_base", "arm_L_upper", "shoulder_L"),
        ("arm_L_upper", "arm_L_lower_paw", "elbow_L"), ("body_base", "arm_R_upper", "shoulder_R"),
        ("arm_R_upper", "arm_R_lower_paw", "elbow_R"), ("body_base", "leg_L_upper", "hip_L"),
        ("leg_L_upper", "leg_L_lower_paw", "knee_L"), ("body_base", "leg_R_upper", "hip_R"),
        ("leg_R_upper", "leg_R_lower_paw", "knee_R"), ("body_base", "tail", "tail_root"),
    ],
    "side": [
        ("body_base", "head_base", "neck"), ("body_base", "arm_near_upper", "shoulder_near"),
        ("arm_near_upper", "arm_near_lower_paw", "elbow_near"), ("body_base", "arm_far_upper", "shoulder_far"),
        ("arm_far_upper", "arm_far_lower_paw", "elbow_far"), ("body_base", "leg_near_upper", "hip_near"),
        ("leg_near_upper", "leg_near_lower_paw", "knee_near"), ("body_base", "leg_far_upper", "hip_far"),
        ("leg_far_upper", "leg_far_lower_paw", "knee_far"), ("body_base", "tail", "tail_root"),
    ],
    "back": [
        ("body_base", "head_base", "neck"), ("body_base", "arm_L_upper", "shoulder_L"),
        ("arm_L_upper", "arm_L_lower_paw", "elbow_L"), ("body_base", "arm_R_upper", "shoulder_R"),
        ("arm_R_upper", "arm_R_lower_paw", "elbow_R"), ("body_base", "leg_L_upper", "hip_L"),
        ("leg_L_upper", "leg_L_lower_paw", "knee_L"), ("body_base", "leg_R_upper", "hip_R"),
        ("leg_R_upper", "leg_R_lower_paw", "knee_R"), ("body_base", "tail", "tail_root"),
    ],
}


def render(view: str, pulled: bool = False) -> tuple[Image.Image, dict[str, Image.Image]]:
    composite = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    rendered: dict[str, Image.Image] = {}
    for semantic in DRAW_ORDER[view]:
        offset = PULL_OFFSETS.get(view, {}).get(semantic, (0, 0)) if pulled else (0, 0)
        layer = placed_layer(view, semantic, PLACEMENTS[view][semantic], offset)
        rendered[semantic] = layer
        composite.alpha_composite(layer)
    return composite, rendered


def overlap_pixels(a: Image.Image, b: Image.Image) -> int:
    aa = np.asarray(a.getchannel("A")) > 16
    bb = np.asarray(b.getchannel("A")) > 16
    return int((aa & bb).sum())


def make_review(rests: dict[str, Image.Image], pulls: dict[str, Image.Image]) -> Path:
    panel_w, panel_h = 430, 590
    header = 120
    canvas = Image.new("RGBA", (panel_w * 3, header + panel_h * 2 + 52), (244, 247, 249, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((28, 18), "Xiaoju X6 v16 - assembly from 48 generated transparent layers", fill=(25, 35, 42), font=font(30))
    draw.text((28, 58), "Top: rest assembly. Bottom: small joint pull check. No whole-cat image fallback.", fill=(63, 77, 87), font=font(18))
    draw.text((28, 87), "Body occludes rounded shoulder/hip/tail roots; upper segments occlude lower joint sleeves.", fill=(11, 115, 80), font=font(17))

    for col, view in enumerate(("front", "side", "back")):
        for row, source in enumerate((rests[view], pulls[view])):
            tile = checker((panel_w - 18, panel_h - 18))
            preview = source.copy()
            preview.thumbnail((tile.width - 16, tile.height - 16), Image.Resampling.LANCZOS)
            tile.alpha_composite(preview, ((tile.width - preview.width) // 2, (tile.height - preview.height) // 2))
            x = col * panel_w + 9
            y = header + row * panel_h + 9
            canvas.alpha_composite(tile, (x, y))
            draw.rectangle((x, y, x + tile.width, y + tile.height), outline=(163, 175, 184), width=2)
            label = f"{view.upper()} - {'REST' if row == 0 else 'JOINT PULL'}"
            draw.rounded_rectangle((x + 12, y + 12, x + 190, y + 43), radius=4, fill=(255, 255, 255, 230), outline=(150, 160, 168))
            draw.text((x + 20, y + 18), label, fill=(29, 40, 47), font=font(16))
    out = QA / "x6-generated-layer-assembly-review-v16.png"
    canvas.save(out)
    return out


def main() -> None:
    ASSEMBLED.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    rests: dict[str, Image.Image] = {}
    pulls: dict[str, Image.Image] = {}
    audits: list[dict] = []

    for view in ("front", "side", "back"):
        rest, rest_layers = render(view, pulled=False)
        pull, pull_layers = render(view, pulled=True)
        rests[view] = rest
        pulls[view] = pull
        rest.save(ASSEMBLED / f"{view}-rest.png")
        pull.save(ASSEMBLED / f"{view}-joint-pull.png")
        for parent, child, joint in JOINTS[view]:
            audits.append({
                "view": view,
                "joint": joint,
                "parent": parent,
                "child": child,
                "restOverlapPixels": overlap_pixels(rest_layers[parent], rest_layers[child]),
                "pullOverlapPixels": overlap_pixels(pull_layers[parent], pull_layers[child]),
            })

    review = make_review(rests, pulls)
    minimum_rest = min(item["restOverlapPixels"] for item in audits)
    minimum_pull = min(item["pullOverlapPixels"] for item in audits)
    contract = {
        "schemaVersion": 1,
        "version": "v16",
        "status": "generated-layer-assembly-review-candidate",
        "sourceLayerContract": "x6-generated-complete-layer-contract-v15.json",
        "usesIndependentGeneratedPngLayers": True,
        "usesWholeCatFallback": False,
        "views": {
            view: {
                "rest": f"generated-layer-assembly-v16/{view}-rest.png",
                "jointPull": f"generated-layer-assembly-v16/{view}-joint-pull.png",
                "drawOrder": DRAW_ORDER[view],
                "placements": PLACEMENTS[view],
                "pullOffsets": PULL_OFFSETS[view],
            }
            for view in ("front", "side", "back")
        },
        "overlapAudit": {
            "jointCount": len(audits),
            "minimumRestOverlapPixels": minimum_rest,
            "minimumPullOverlapPixels": minimum_pull,
            "allRestNonZero": minimum_rest > 0,
            "allPullNonZero": minimum_pull > 0,
            "joints": audits,
        },
        "primaryReview": review.relative_to(ROOT).as_posix(),
        "assemblyApprovedByUser": False,
        "gate6Approved": False,
        "x7Authorized": False,
    }
    CONTRACT.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"review": str(review), "minimumRest": minimum_rest, "minimumPull": minimum_pull}, ensure_ascii=False))


if __name__ == "__main__":
    main()
