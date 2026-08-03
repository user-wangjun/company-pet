from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
MATERIALS = ROOT / "generated-complete-layer-materials-v15"
OUTPUT = ROOT / "generated-complete-layer-candidates-v15"
QA = ROOT / "qa"
CONTRACT = ROOT / "x6-generated-complete-layer-contract-v15.json"

VIEW_LAYERS = {
    "front": [
        "body_base", "head_base", "muzzle_mouth", "tail",
        "ear_L", "ear_R", "eye_L", "eye_R",
        "arm_L_upper", "arm_L_lower_paw", "arm_R_upper", "arm_R_lower_paw",
        "leg_L_upper", "leg_L_lower_paw", "leg_R_upper", "leg_R_lower_paw",
    ],
    "side": [
        "body_base", "head_base", "muzzle_mouth", "tail",
        "ear_near", "ear_far", "eye_near", "eye_far",
        "arm_near_upper", "arm_near_lower_paw", "arm_far_upper", "arm_far_lower_paw",
        "leg_near_upper", "leg_near_lower_paw", "leg_far_upper", "leg_far_lower_paw",
    ],
    "back": [
        "body_base", "head_base", "ear_L", "ear_R",
        "tail", "arm_L_upper", "arm_L_lower_paw", "arm_R_upper",
        "arm_R_lower_paw", "leg_L_upper", "leg_L_lower_paw", "leg_R_upper",
        "leg_R_lower_paw", "scapula_fill_L", "scapula_fill_R", "pelvis_tailroot_fill",
    ],
}

OVERLAP_RULES = {
    "head_base": "neck root extends under body by 20-30%",
    "ear": "ear root extends under head by 20-25%",
    "arm": "shoulder root and elbow sleeve each retain 20-30% hidden overlap",
    "leg": "hip root and knee sleeve each retain 20-30% hidden overlap",
    "tail": "tail root extends under pelvis by 20-30%",
    "muzzle": "muzzle perimeter extends under head fur by 12-18%",
    "eye": "eye-only layer; eyelid and surrounding fur remain on head material",
    "fill": "hidden bridge material is fully occluded at rest",
    "body": "continuous torso parent material with neck, shoulder, hip, and tail-root receiving zones",
}

GENERATED_OVERRIDES = {
    ("side", "head_base"): MATERIALS / "side-head-base-earless-alpha.png",
    ("back", "head_base"): MATERIALS / "back-head-base-earless-alpha.png",
}


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def checker(size: tuple[int, int], step: int = 18) -> Image.Image:
    w, h = size
    canvas = Image.new("RGBA", size, (245, 247, 249, 255))
    draw = ImageDraw.Draw(canvas)
    for y in range(0, h, step):
        for x in range(0, w, step):
            if (x // step + y // step) % 2:
                draw.rectangle((x, y, min(x + step, w), min(y + step, h)), fill=(222, 228, 233, 255))
    return canvas


def semantic_rule(name: str) -> str:
    for token in ("eye", "muzzle", "ear", "arm", "leg", "tail", "fill", "head_base", "body"):
        if token in name:
            return OVERLAP_RULES[token]
    return "complete generated material"


def connected_components(board: Image.Image, expected_count: int) -> list[dict]:
    alpha = np.asarray(board.getchannel("A"))
    work = Image.fromarray(np.where(alpha > 32, 255, 0).astype(np.uint8), mode="L").copy()
    components: list[dict] = []

    for index in range(expected_count):
        row, col = divmod(index, 4)
        active = np.asarray(work)
        x0, x1 = round(col * board.width / 4), round((col + 1) * board.width / 4)
        y0, y1 = round(row * board.height / 4), round((row + 1) * board.height / 4)
        ys, xs = np.where(active[y0:y1, x0:x1] == 255)
        if not len(xs):
            raise ValueError(f"missing generated material at grid row {row + 1}, column {col + 1}")
        xs = xs + x0
        ys = ys + y0
        center_x = (x0 + x1) / 2
        center_y = (y0 + y1) / 2
        nearest = np.argmin((xs - center_x) ** 2 + (ys - center_y) ** 2)
        seed = (int(xs[nearest]), int(ys[nearest]))
        ImageDraw.floodfill(work, seed, 128, thresh=0)
        filled = np.asarray(work)
        cy, cx = np.where(filled == 128)
        pixel_count = len(cx)
        if pixel_count < 500:
            raise ValueError(f"generated material at row {row + 1}, column {col + 1} is too small: {pixel_count}")
        components.append({
            "bbox": (int(cx.min()), int(cy.min()), int(cx.max()) + 1, int(cy.max()) + 1),
            "centroid": (float(cx.mean()), float(cy.mean())),
            "pixelCount": pixel_count,
        })
        mutable = np.array(work, copy=True)
        mutable[mutable == 128] = 0
        work = Image.fromarray(mutable, mode="L").copy()

    return components


def export_view(view: str, names: list[str]) -> tuple[list[dict], Path]:
    source = MATERIALS / f"{view}-layer-board-alpha.png"
    board = Image.open(source).convert("RGBA")
    width, height = board.size
    if width != height:
        raise ValueError(f"{source} must be square, got {board.size}")

    components = connected_components(board, len(names))
    if len(components) != len(names):
        raise ValueError(f"{view} expected {len(names)} connected materials, found {len(components)}")

    view_dir = OUTPUT / view
    view_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    layers: list[Image.Image] = []

    for index, (name, component) in enumerate(zip(names, components)):
        row, col = divmod(index, 4)
        x0, y0, x1, y1 = component["bbox"]
        margin = 8
        left = max(0, x0 - margin)
        top = max(0, y0 - margin)
        right = min(board.width, x1 + margin)
        bottom = min(board.height, y1 + margin)
        layer = board.crop((left, top, right, bottom))

        # Preserve only this generated material if soft antialiasing from another
        # nearby cell enters the padded crop.
        local_alpha = np.asarray(layer.getchannel("A"))
        yy, xx = np.ogrid[top:bottom, left:right]
        component_box = (xx >= x0 - 3) & (xx < x1 + 3) & (yy >= y0 - 3) & (yy < y1 + 3)
        isolated_alpha = np.where(component_box, local_alpha, 0).astype(np.uint8)
        layer.putalpha(Image.fromarray(isolated_alpha, mode="L"))

        source_method = "imagegen-complete-independent-material"
        override = GENERATED_OVERRIDES.get((view, name))
        if override is not None:
            corrected = Image.open(override).convert("RGBA")
            corrected_box = corrected.getchannel("A").getbbox()
            if corrected_box is None:
                raise ValueError(f"generated override is blank: {override}")
            margin = 10
            corrected_box = (
                max(0, corrected_box[0] - margin),
                max(0, corrected_box[1] - margin),
                min(corrected.width, corrected_box[2] + margin),
                min(corrected.height, corrected_box[3] + margin),
            )
            layer = corrected.crop(corrected_box)
            source_method = "imagegen-complete-earless-head-correction"
        out_name = f"{index + 1:02d}_{view}_{name}.png"
        out_path = view_dir / out_name
        layer.save(out_path)
        layers.append(layer)

        layer_alpha = np.asarray(layer.getchannel("A"))
        records.append({
            "id": f"{view}:{name}",
            "view": view,
            "gridCell": {"row": row + 1, "column": col + 1},
            "file": out_path.relative_to(ROOT).as_posix(),
            "pixelSize": [layer.width, layer.height],
            "nonTransparentPixels": int((layer_alpha > 6).sum()),
            "hiddenOverlapRole": semantic_rule(name),
            "sourceMethod": source_method,
        })

    atlas = build_atlas(view, names, layers)
    atlas_path = QA / f"x6-generated-complete-{view}-layer-atlas-v15.png"
    atlas.save(atlas_path)
    return records, atlas_path


def build_atlas(view: str, names: list[str], layers: list[Image.Image]) -> Image.Image:
    tile_w, tile_h = 300, 300
    header = 80
    canvas = Image.new("RGBA", (tile_w * 4, header + tile_h * 4), (250, 251, 252, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 16), f"Xiaoju X6 v15 - {view.upper()} - 16 generated complete layers", fill=(28, 37, 44), font=font(28))
    draw.text((24, 50), "Independent materials with hidden joint roots; not visible-pixel cutouts", fill=(68, 83, 92), font=font(16))

    for index, (name, layer) in enumerate(zip(names, layers)):
        row, col = divmod(index, 4)
        x, y = col * tile_w, header + row * tile_h
        tile = checker((tile_w - 12, tile_h - 44))
        preview = layer.copy()
        preview.thumbnail((tile.width - 30, tile.height - 30), Image.Resampling.LANCZOS)
        px = (tile.width - preview.width) // 2
        py = (tile.height - preview.height) // 2
        tile.alpha_composite(preview, (px, py))
        canvas.alpha_composite(tile, (x + 6, y + 4))
        draw.rectangle((x + 6, y + 4, x + tile_w - 6, y + tile_h - 40), outline=(184, 193, 199), width=1)
        draw.text((x + 10, y + tile_h - 32), f"{index + 1:02d} {name}", fill=(27, 40, 48), font=font(15))
    return canvas


def build_review(atlas_paths: dict[str, Path]) -> Path:
    panel_w, panel_h = 560, 650
    canvas = Image.new("RGBA", (panel_w * 3, panel_h + 150), (245, 247, 249, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((30, 18), "Xiaoju X6 v15 - generated complete three-view layer review", fill=(24, 34, 41), font=font(32))
    draw.text((30, 60), "48 independent transparent materials generated from the approved Xiaoju three-view and spread-pose references", fill=(63, 77, 87), font=font(18))
    draw.text((30, 92), "Joint rule: rounded hidden roots and 20-30% parent/child overlap; eye layers contain eyes only", fill=(14, 116, 82), font=font(18))

    for column, view in enumerate(("front", "side", "back")):
        atlas = Image.open(atlas_paths[view]).convert("RGBA")
        atlas.thumbnail((panel_w - 24, panel_h - 30), Image.Resampling.LANCZOS)
        x = column * panel_w + (panel_w - atlas.width) // 2
        y = 130 + (panel_h - atlas.height) // 2
        canvas.alpha_composite(atlas, (x, y))
        draw.rectangle((column * panel_w + 8, 122, (column + 1) * panel_w - 8, panel_h + 118), outline=(164, 175, 183), width=2)

    out = QA / "x6-generated-complete-three-view-layer-review-v15.png"
    canvas.save(out)
    return out


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    atlases: dict[str, Path] = {}
    for view, names in VIEW_LAYERS.items():
        view_records, atlas_path = export_view(view, names)
        records.extend(view_records)
        atlases[view] = atlas_path

    review = build_review(atlases)
    contract = {
        "schemaVersion": 1,
        "version": "v15",
        "status": "generated-complete-three-view-layer-review-candidate",
        "generationMethod": "built-in-imagegen-from-xiaoju-three-view-and-spread-pose-references",
        "notVisiblePixelCutouts": True,
        "sourceReferences": [
            "../../three-view-preview.png",
            "../x5/qa/x5-actual-xiaoju-spread-pose-three-view.png",
            "../x5/generated-layer-materials/x5-xiaoju-fine-layer-source-atlas-alpha-v1.png",
        ],
        "sourceBoards": {view: f"generated-complete-layer-materials-v15/{view}-layer-board-alpha.png" for view in VIEW_LAYERS},
        "generatedCorrections": {
            "side:head_base": "generated-complete-layer-materials-v15/side-head-base-earless-alpha.png",
            "back:head_base": "generated-complete-layer-materials-v15/back-head-base-earless-alpha.png",
        },
        "layerCounts": {"front": 16, "side": 16, "back": 16, "total": 48},
        "overlapPolicy": {
            "targetJointOverlapRatio": [0.20, 0.30],
            "rules": OVERLAP_RULES,
            "rejectionConditions": [
                "flat visible cut at a moving joint",
                "detached bone segment during pull test",
                "hard circular patch or local bulge",
                "radial or cloned hidden texture",
                "identity drift from Xiaoju references",
            ],
        },
        "qa": {
            "frontAtlas": atlases["front"].relative_to(ROOT).as_posix(),
            "sideAtlas": atlases["side"].relative_to(ROOT).as_posix(),
            "backAtlas": atlases["back"].relative_to(ROOT).as_posix(),
            "primaryReview": review.relative_to(ROOT).as_posix(),
        },
        "layers": records,
        "frontAllGeneratedLayersAuthorizedByUser": True,
        "sideBackGeneratedLayersAuthorizedByUser": True,
        "generatedLayerMaterialsApprovedByUser": False,
        "gate6Approved": False,
        "x7Authorized": False,
    }
    CONTRACT.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"exported {len(records)} generated complete layers")
    print(review)


if __name__ == "__main__":
    main()
