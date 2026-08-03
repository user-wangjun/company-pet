import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
PARTS = ROOT / "parts-v5"
QA = ROOT / "qa"
CANVAS = (1370, 1148)

REQUIRED = [
    "10_Body_HiddenBase_v5.png",
    "11_Ribcage_Hidden_v5.png",
    "12_Belly_Hidden_v5.png",
    "13_Pelvis_Hidden_v5.png",
    "15_NeckFill_Approved.png",
    "20_Head_Approved.png",
    "30_Tail_Complete_v5.png",
    "40_HindLeg_Near_v5.png",
    "41_HindPaw_Near_v5.png",
    "42_HindLeg_Far_v5_INFERRED.png",
    "43_HindPaw_Far_v5_INFERRED.png",
    "44_Hip_Near_v5.png",
    "45_Thigh_Near_v5.png",
    "46_Hock_Near_v5.png",
    "47_Hip_Far_v5_INFERRED.png",
    "48_Thigh_Far_v5_INFERRED.png",
    "49_Hock_Far_v5_INFERRED.png",
    "60_Foreleg_ViewL_Complete_v5.png",
    "61_Foreleg_ViewR_Complete_v5.png",
    "62_ShoulderFill_ViewL_v5.png",
    "63_UpperArm_ViewL_v5.png",
    "64_Forearm_ViewL_v5.png",
    "65_Paw_ViewL_v5.png",
    "66_ShoulderFill_ViewR_v5.png",
    "67_UpperArm_ViewR_v5.png",
    "68_Forearm_ViewR_v5.png",
    "69_Paw_ViewR_v5.png",
]


def inspect(path: Path) -> dict:
    image = Image.open(path).convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    pixels = list(image.get_flattened_data())
    visible = sum(a > 0 for _, _, _, a in pixels)
    green_residue = sum(a > 16 and g > max(r, b) + 18 for r, g, b, a in pixels)
    corners = [image.getpixel(point)[3] for point in ((0, 0), (image.width - 1, 0), (0, image.height - 1), (image.width - 1, image.height - 1))]
    return {
        "file": path.name,
        "size": list(image.size),
        "alphaBbox": list(bbox) if bbox else None,
        "visiblePixelCount": visible,
        "visibleCoverage": round(visible / (image.width * image.height), 6),
        "cornerAlpha": corners,
        "greenResiduePixels": green_residue,
        "provisional": "PROVISIONAL" in path.name,
        "inferred": "INFERRED" in path.name,
        "valid": image.size == CANVAS and bbox is not None and corners == [0, 0, 0, 0] and green_residue == 0,
    }


def make_hindlimb_sheet(items: dict[str, Image.Image]) -> None:
    sheet = Image.new("RGBA", (1000, 620), (20, 22, 28, 255))
    draw = ImageDraw.Draw(sheet)
    names = [
        "40_HindLeg_Near_v5.png",
        "41_HindPaw_Near_v5.png",
        "42_HindLeg_Far_v5_INFERRED.png",
        "43_HindPaw_Far_v5_INFERRED.png",
    ]
    for index, name in enumerate(names):
        image = items[name]
        bbox = image.getchannel("A").getbbox()
        crop = image.crop(bbox)
        crop.thumbnail((450, 230), Image.Resampling.LANCZOS)
        cell_x = (index % 2) * 500
        cell_y = (index // 2) * 310
        x = cell_x + (500 - crop.width) // 2
        y = cell_y + 45 + (235 - crop.height) // 2
        sheet.alpha_composite(crop, (x, y))
        draw.text((cell_x + 12, cell_y + 12), name[:-4], fill=(255, 255, 255, 255))
    sheet.save(QA / "gate3-v5-hindlimbs-contact-sheet.png")


def main() -> None:
    missing = [name for name in REQUIRED if not (PARTS / name).is_file()]
    parts = {name: Image.open(PARTS / name).convert("RGBA") for name in REQUIRED if (PARTS / name).is_file()}
    reports = [inspect(PARTS / name) for name in REQUIRED if (PARTS / name).is_file()]
    invalid = [item["file"] for item in reports if not item["valid"]]
    provisional = [item["file"] for item in reports if item["provisional"]]
    inferred = [item["file"] for item in reports if item["inferred"]]
    if not missing:
        make_hindlimb_sheet(parts)

    blockers = []
    if missing:
        blockers.append("required_parts_missing")
    if invalid:
        blockers.append("invalid_alpha_canvas_or_chroma")
    if provisional:
        blockers.append("provisional_material_present")
    if inferred:
        blockers.append("far_hindlimb_bilateral_inference_requires_expanded_pose_acceptance")
    blockers.extend(
        [
            "ribcage_belly_pelvis_overlap_needs_final_expanded_pose_review",
            "rounded_forelimb_masks_need_final_fur_matte_and_draw_order_review",
            "v5_parts_not_yet_imported_into_editable_psd",
            "expanded_pose_and_roundtrip_motion_not_yet_approved",
        ]
    )

    report = {
        "schemaVersion": 1,
        "candidate": "v5_hidden_anatomy_material_trial",
        "canvas": list(CANVAS),
        "requiredPartCount": len(REQUIRED),
        "foundPartCount": len(reports),
        "missing": missing,
        "invalid": invalid,
        "provisional": provisional,
        "inferred": inferred,
        "parts": reports,
        "sourceVerdicts": {
            "v5Fullbody": "accept_as_hidden_anatomy_and_texture_source_only_not_as_final_login_pose",
            "v5NoForelegs": "accept_as_hidden_body_reconstruction_source",
            "v6Limbless": "reject_whole_silhouette_use_only_local_occluded_inpaint_pixels",
        },
        "gate3Pass": False,
        "blockers": blockers,
    }
    output = QA / "gate3-v5-parts-audit.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    print(QA / "gate3-v5-hindlimbs-contact-sheet.png")
    print(f"found={len(reports)} invalid={len(invalid)} provisional={len(provisional)} gate3Pass=false")


if __name__ == "__main__":
    main()
