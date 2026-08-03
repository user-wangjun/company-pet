from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT.parent
XIAOXING = VALIDATION.parent

INPUTS = ROOT / "inputs"
PSD = ROOT / "psd"
CUBISM = ROOT / "cubism"
CONTRACTS = ROOT / "contracts"
AUDIT = ROOT / "audit"
QA = ROOT / "qa"

CANVAS = (512, 1086)
OLD_UPPER_QA_RGBA = (72, 116, 202, 255)
OLD_F4_ENGINEERING_RGBA = (244, 190, 173, 255)

V4 = VALIDATION / "arm-chain-screen-right-v4-wrist-motion"
SLEEVE = (
    VALIDATION
    / "arm-chain-screen-right-v5-hidden-upper-arm"
    / "complete-sleeve-final"
)
V6 = VALIDATION / "arm-chain-screen-right-v6-complete-upper-arm-geometry"
V7 = (
    VALIDATION
    / "arm-chain-screen-right-v7-production-forearm-geometry"
    / "v7c1-elbow-seam-fairing"
)
V8 = (
    VALIDATION
    / "arm-chain-screen-right-v8-formal-hand-geometry"
    / "v8b1-complete-hand-geometry"
)
V9 = VALIDATION / "arm-chain-screen-right-v9-upper-arm-hidden-texture-proof"

FREEZE_MANIFESTS = [
    (
        "V4",
        V4 / "archive/STAGE-A-V4-APPROVED-2026-07-24.json",
        "dd6a91b263a5e0e135931f4196176256000a4d7aff648f907428da52030711b1",
    ),
    (
        "complete_sleeve",
        SLEEVE / "audit/complete-sleeve-freeze-manifest-2026-07-25.json",
        "a36c1959a1a16364997f60e4704c9af071173b79530a417216f6e5b71f3642e8",
    ),
    (
        "V6",
        V6 / "audit/v6-complete-upper-arm-geometry-freeze-manifest-2026-07-25.json",
        "e23e54c89e9fd5615b4686915f2243f32e21542dd81fb126ac45606a610107ae",
    ),
    (
        "V7_C1",
        V7 / "audit/v7-production-forearm-geometry-freeze-manifest-2026-07-26.json",
        "65469d0eda4d5c27b79d3d23fbd92604a51ad82c5ca08ce6a875ab7d1bffea33",
    ),
    (
        "V8_B1_V8_C",
        V8 / "audit/v8b1-v8c-freeze-manifest-2026-07-26.json",
        "6c256bc1037ada098a1dd3daaa4a9bbe3fac807c532f9716cbf7b71eb0614e4c",
    ),
    (
        "V9",
        V9 / "audit/v9-upper-arm-hidden-texture-freeze-manifest-2026-07-26.json",
        "6c22bce8369b7314e85af8f2ddc41236fa6365efcb30da320beda15aeaba6f4c",
    ),
]

LAYERS = [
    {
        "id": "sleeve",
        "psdLayerName": "01_sleeve",
        "source": SLEEVE / "materials/sleeve-complete-textured-r1.png",
        "output": INPUTS / "01_sleeve.png",
        "geometry": SLEEVE / "inputs/sleeve-complete-geometry-r9.png",
        "drawOrder": 400,
    },
    {
        "id": "upper_arm",
        "psdLayerName": "02_upper_arm_engineering",
        "source": V9 / "materials/upper-arm-shoulder-hidden-candidate-b.png",
        "output": INPUTS / "02_upper_arm_engineering.png",
        "geometry": V6 / "masks/upper-arm-complete-geometry.png",
        "drawOrder": 100,
    },
    {
        "id": "production_forearm_including_bracelet",
        "psdLayerName": "03_forearm_including_bracelet",
        "source": V7 / "masks/production-forearm-flat-color-faired.png",
        "output": INPUTS / "03_forearm_including_bracelet.png",
        "geometry": V7 / "masks/production-forearm-geometry-faired.png",
        "drawOrder": 300,
    },
    {
        "id": "whole_hand",
        "psdLayerName": "04_whole_hand",
        "source": V8 / "materials/geometry/M-hand-flat-color.png",
        "output": INPUTS / "04_whole_hand.png",
        "geometry": V8 / "masks/M-hand-complete-geometry.png",
        "drawOrder": 200,
    },
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(XIAOXING.resolve()).as_posix()


def iter_path_hash_records(value: object):
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            yield value["path"], value["sha256"].lower()
        for child in value.values():
            yield from iter_path_hash_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_path_hash_records(child)


def resolve_locked_path(manifest: Path, raw_path: str, expected: str) -> Path | None:
    rel = Path(raw_path.replace("\\", "/"))
    base = manifest.parent
    candidates: list[Path] = []
    while True:
        candidates.append((base / rel).resolve())
        if base == XIAOXING or base.parent == base:
            break
        base = base.parent
    for candidate in candidates:
        if candidate.is_file() and sha256(candidate) == expected:
            return candidate
    return None


def coverage_channel(path: Path) -> Image.Image:
    image = Image.open(path)
    return image.getchannel("A") if "A" in image.getbands() else image.convert("L")


def alpha_difference(first: Path, second: Path) -> int:
    diff = ImageChops.difference(coverage_channel(first), coverage_channel(second))
    return sum(1 for value in diff.get_flattened_data() if value)


def alpha_metrics(path: Path) -> dict[str, object]:
    image = Image.open(path)
    alpha = coverage_channel(path)
    return {
        "mode": image.mode,
        "canvas": list(image.size),
        "alphaNonzeroPixels": sum(1 for value in alpha.get_flattened_data() if value),
        "alphaBoundingBox": list(alpha.getbbox()) if alpha.getbbox() else None,
        "sha256": sha256(path),
    }


def mask_points(path: Path) -> list[tuple[int, int]]:
    mask = coverage_channel(path)
    return [
        (x, y)
        for y in range(CANVAS[1])
        for x in range(CANVAS[0])
        if mask.getpixel((x, y)) > 0
    ]


def changed_rgba_points(first: Image.Image, second: Image.Image) -> list[tuple[int, int]]:
    return [
        (x, y)
        for y in range(CANVAS[1])
        for x in range(CANVAS[0])
        if first.getpixel((x, y)) != second.getpixel((x, y))
    ]


def adjacent_approved_mode(
    image: Image.Image,
    blocked_points: set[tuple[int, int]],
) -> tuple[tuple[int, int, int, int], list[tuple[int, int]]]:
    ring: set[tuple[int, int]] = set()
    for x, y in blocked_points:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                point = (x + dx, y + dy)
                if (
                    0 <= point[0] < CANVAS[0]
                    and 0 <= point[1] < CANVAS[1]
                    and point not in blocked_points
                    and image.getpixel(point)[3] == 255
                ):
                    ring.add(point)
    colors = Counter(image.getpixel(point) for point in ring)
    if not colors:
        raise SystemExit("No adjacent approved opaque upper-arm pixels were found.")
    selected = sorted(colors.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return selected, sorted(ring)


def save_color_correction_qa(
    upper_before: Image.Image,
    upper_after: Image.Image,
    forearm_before: Image.Image,
    forearm_after: Image.Image,
    upper_mask_path: Path,
    f4_mask_path: Path,
) -> None:
    crop = (326, 382, 420, 568)
    scale = 4
    panels = [
        ("upper before", upper_before),
        ("upper after", upper_after),
        ("forearm before", forearm_before),
        ("forearm after", forearm_after),
    ]
    board = Image.new("RGB", (376 * 2, 744 * 2 + 52), (35, 35, 39))
    draw = ImageDraw.Draw(board)
    for index, (label, image) in enumerate(panels):
        x = (index % 2) * 376
        y = (index // 2) * 744
        checker = Image.new("RGBA", CANVAS, (230, 230, 230, 255))
        cdraw = ImageDraw.Draw(checker)
        for py in range(0, CANVAS[1], 12):
            for px in range(0, CANVAS[0], 12):
                if (px // 12 + py // 12) % 2:
                    cdraw.rectangle((px, py, px + 11, py + 11), fill=(190, 190, 190, 255))
        checker.alpha_composite(image)
        panel = checker.crop(crop).resize((376, 744), Image.Resampling.NEAREST)
        board.paste(panel.convert("RGB"), (x, y))
        draw.text((x + 8, y + 8), label, fill=(20, 20, 20))

    upper_mask = coverage_channel(upper_mask_path)
    f4_mask = coverage_channel(f4_mask_path)
    draw.text(
        (8, 744 * 2 + 18),
        (
            f"H_upper QA identity: {sum(value > 0 for value in upper_mask.get_flattened_data())} px; "
            f"F4 ownership: {sum(value > 0 for value in f4_mask.get_flattened_data())} px"
        ),
        fill=(255, 255, 255),
    )
    board.save(QA / "03-material-color-correction-ownership-isolation.png")


def verify_freezes() -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    for name, manifest, expected_manifest_hash in FREEZE_MANIFESTS:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        records = list(dict.fromkeys(iter_path_hash_records(data)))
        if name == "V4":
            records.extend(
                (path, expected.lower())
                for path, expected in data.get("artifactSha256", {}).items()
            )
        records = list(dict.fromkeys(records))
        failures = []
        for raw_path, expected in records:
            resolved = resolve_locked_path(manifest, raw_path, expected)
            if resolved is None:
                failures.append({"path": raw_path, "expectedSha256": expected})
        groups.append(
            {
                "group": name,
                "manifest": relative(manifest),
                "manifestSha256": sha256(manifest),
                "expectedManifestSha256": expected_manifest_hash,
                "manifestHashPass": sha256(manifest) == expected_manifest_hash,
                "referencedRecords": len(records),
                "passedRecords": len(records) - len(failures),
                "failedRecords": len(failures),
                "firstFailure": failures[0] if failures else None,
            }
        )
    return groups


def save_qa(layers: list[dict[str, object]]) -> None:
    composite = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer in sorted(layers, key=lambda item: int(item["drawOrder"])):
        composite.alpha_composite(Image.open(Path(layer["output"])).convert("RGBA"))
    composite.save(QA / "01-default-frozen-draw-order-recomposition.png")

    thumb_size = (256, 543)
    board = Image.new("RGBA", (thumb_size[0] * 4, thumb_size[1] + 50), (32, 32, 36, 255))
    draw = ImageDraw.Draw(board)
    for index, layer in enumerate(layers):
        image = Image.open(Path(layer["output"])).convert("RGBA")
        checker = Image.new("RGBA", CANVAS, (225, 225, 225, 255))
        tile = 16
        cdraw = ImageDraw.Draw(checker)
        for y in range(0, CANVAS[1], tile):
            for x in range(0, CANVAS[0], tile):
                if (x // tile + y // tile) % 2:
                    cdraw.rectangle((x, y, x + tile - 1, y + tile - 1), fill=(190, 190, 190, 255))
        checker.alpha_composite(image)
        checker.thumbnail(thumb_size, Image.Resampling.NEAREST)
        x = index * thumb_size[0]
        board.alpha_composite(checker, (x, 0))
        draw.text((x + 8, thumb_size[1] + 14), str(layer["id"]), fill=(255, 255, 255, 255))
    board.convert("RGB").save(QA / "02-four-material-isolation-sheet.png")


def main() -> None:
    freeze_groups = verify_freezes()
    freeze_pass = all(
        group["manifestHashPass"] and group["failedRecords"] == 0
        for group in freeze_groups
    )
    if not freeze_pass:
        raise SystemExit("Frozen input integrity failed; no V10 inputs were generated.")

    for directory in (INPUTS, PSD, CUBISM, CONTRACTS, AUDIT, QA):
        directory.mkdir(parents=True, exist_ok=True)

    for layer in LAYERS:
        source = Path(layer["source"])
        output = Path(layer["output"])
        if Image.open(source).size != CANVAS:
            raise SystemExit(f"Canvas mismatch: {relative(source)}")
        if alpha_difference(source, Path(layer["geometry"])) != 0:
            raise SystemExit(f"Alpha mismatch: {relative(source)}")
        shutil.copy2(source, output)

    unapproved_mask = V9 / "masks/H_upper-not-in-scope.png"
    upper_path = INPUTS / "02_upper_arm_engineering.png"
    upper_before = Image.open(upper_path).convert("RGBA")
    upper_after = upper_before.copy()
    upper_points = set(mask_points(unapproved_mask))
    upper_before_colors = sorted({upper_before.getpixel(point) for point in upper_points})
    if len(upper_points) != 349 or upper_before_colors != [OLD_UPPER_QA_RGBA]:
        raise SystemExit("Upper-arm QA placeholder is not the frozen 349-pixel blue region.")
    upper_sample_rgba, upper_sample_ring = adjacent_approved_mode(
        upper_before,
        upper_points,
    )
    for point in upper_points:
        alpha = upper_before.getpixel(point)[3]
        upper_after.putpixel(point, (*upper_sample_rgba[:3], alpha))
    upper_after.save(upper_path)

    f4_mask_path = V7 / "masks/F4-wrist-hidden-extension.png"
    f5_mask_path = V7 / "masks/F5-wrist-responsibility-not-material.png"
    h3_mask_path = V8 / "masks/H3-parameterized-hidden-wrist-margin.png"
    bracelet_mask_path = V7.parent / "masks/bracelet-ownership-candidate.png"
    visible_forearm_path = V7.parent / "masks/visible-forearm-locked.png"
    forearm_path = INPUTS / "03_forearm_including_bracelet.png"
    hand_path = INPUTS / "04_whole_hand.png"
    forearm_before = Image.open(forearm_path).convert("RGBA")
    forearm_after = forearm_before.copy()
    hand = Image.open(hand_path).convert("RGBA")
    f4_points = set(mask_points(f4_mask_path))
    f5_points = set(mask_points(f5_mask_path))
    h3_points = set(mask_points(h3_mask_path))
    bracelet_points = set(mask_points(bracelet_mask_path))
    visible_forearm_points = set(mask_points(visible_forearm_path))
    h3_colors = sorted({hand.getpixel(point) for point in h3_points})
    if len(f4_points) != 186 or len(f5_points) != 348 or len(h3_points) != 42:
        raise SystemExit("Frozen F4, F5, or H3 ownership count changed.")
    if h3_colors != [(244, 222, 216, 255)]:
        raise SystemExit("Frozen H3 wrist-root color is no longer #F4DED8.")
    f4_allowed_points = {
        point
        for point in f4_points
        if forearm_before.getpixel(point) == OLD_F4_ENGINEERING_RGBA
    }
    if len(f4_allowed_points) != 134:
        raise SystemExit("F4 engineering-skin region is no longer the expected 134 pixels.")
    if f4_allowed_points & bracelet_points:
        raise SystemExit("F4 engineering-skin correction would modify bracelet ownership.")
    if f4_allowed_points & visible_forearm_points:
        raise SystemExit("F4 engineering-skin correction would modify frozen visible forearm.")
    for point in f4_allowed_points:
        alpha = forearm_before.getpixel(point)[3]
        forearm_after.putpixel(point, (*h3_colors[0][:3], alpha))
    forearm_after.save(forearm_path)

    upper_changed = set(changed_rgba_points(upper_before, upper_after))
    forearm_changed = set(changed_rgba_points(forearm_before, forearm_after))
    correction_pass = (
        upper_changed == upper_points
        and forearm_changed == f4_allowed_points
        and alpha_difference(Path(LAYERS[1]["source"]), upper_path) == 0
        and alpha_difference(Path(LAYERS[2]["source"]), forearm_path) == 0
        and not (forearm_changed & bracelet_points)
        and not (forearm_changed & visible_forearm_points)
    )
    if not correction_pass:
        raise SystemExit("V10 material color correction audit failed.")

    material_report = []
    for layer in LAYERS:
        source = Path(layer["source"])
        output = Path(layer["output"])
        material_report.append(
            {
                "id": layer["id"],
                "psdLayerName": layer["psdLayerName"],
                "source": relative(source),
                "v10Input": output.relative_to(ROOT).as_posix(),
                "geometry": relative(Path(layer["geometry"])),
                "drawOrder": layer["drawOrder"],
                "alphaDifferencePixels": alpha_difference(
                    output,
                    Path(layer["geometry"]),
                ),
                **alpha_metrics(output),
            }
        )

    correction_audit = {
        "schemaVersion": 1,
        "status": "pass_engineering_material_color_correction",
        "scope": "V10-derived material RGB only; frozen geometry and upstream files unchanged",
        "upperArm": {
            "material": "inputs/02_upper_arm_engineering.png",
            "authorityMask": relative(unapproved_mask),
            "qaIdentity": "H_upper-not-in-scope; engineering QA placeholder, not production texture",
            "maskPixels": len(upper_points),
            "changedPixels": len(upper_changed),
            "beforeRgba": list(OLD_UPPER_QA_RGBA),
            "afterRgba": list(upper_sample_rgba),
            "samplingRule": (
                "Mode RGBA of the 8-connected, opaque, approved V9 candidate-B "
                "pixels immediately outside H_upper; frequency descending then RGBA ascending"
            ),
            "samplingRingPixels": len(upper_sample_ring),
            "alphaDifferencePixels": alpha_difference(
                Path(LAYERS[1]["source"]),
                upper_path,
            ),
            "changedOutsideAuthorityMaskPixels": len(upper_changed - upper_points),
            "frozenCandidateBOutsideMaskDifferencePixels": len(
                upper_changed - upper_points
            ),
        },
        "forearmWrist": {
            "material": "inputs/03_forearm_including_bracelet.png",
            "authorityMask": relative(f4_mask_path),
            "f5QaResponsibilityMask": relative(f5_mask_path),
            "h3FrozenColorAuthorityMask": relative(h3_mask_path),
            "f4MaskPixels": len(f4_points),
            "f4EngineeringSkinPixels": len(f4_allowed_points),
            "f4FrozenVisiblePixelsRetained": len(f4_points - f4_allowed_points),
            "changedPixels": len(forearm_changed),
            "beforeRgba": list(OLD_F4_ENGINEERING_RGBA),
            "afterRgba": list(h3_colors[0]),
            "h3UniqueRgba": [list(color) for color in h3_colors],
            "changedOutsideAllowedF4SkinPixels": len(
                forearm_changed - f4_allowed_points
            ),
            "changedBraceletOwnershipPixels": len(forearm_changed & bracelet_points),
            "changedFrozenVisibleForearmPixels": len(
                forearm_changed & visible_forearm_points
            ),
            "alphaDifferencePixels": alpha_difference(
                Path(LAYERS[2]["source"]),
                forearm_path,
            ),
            "separateWristMaterialCreated": False,
        },
        "frozenGeometry": {
            "canvas": list(CANVAS),
            "integerRegistrationChanged": False,
            "resampled": False,
            "translated": False,
            "scaled": False,
        },
        "privacy": {
            "absolutePathsWritten": False,
            "sourceFilesUploaded": False,
            "cloudServicesUsed": False,
        },
    }
    (AUDIT / "v10-material-color-correction-audit.json").write_text(
        json.dumps(correction_audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    skeleton = json.loads((V4 / "skeleton.json").read_text(encoding="utf-8"))
    contract = {
        "schemaVersion": 1,
        "status": "authorized_minimal_cubism_rough_rig_contract",
        "scope": "single screen-right arm engineering rough rig only",
        "canvas": skeleton["scope"]["canvas"],
        "frozenSkeleton": {
            "shoulder": [332.0, 261.0],
            "elbow": [355.0, 415.0],
            "wrist": [393.0, 533.0],
            "L1Px": 155.70806,
            "L2Px": 123.967738,
        },
        "parameters": {
            "ParamArmShoulder": {
                "minimum": 73.505624,
                "default": 81.505624,
                "maximum": 89.505624,
                "unit": "degrees",
            },
            "ParamArmElbow": {
                "minimum": -27.355943,
                "default": -9.355943,
                "maximum": -3.355943,
                "unit": "degrees",
            },
            "ParamArmWrist": {
                "minimum": -8.0,
                "default": 0.0,
                "maximum": 12.0,
                "unit": "degrees",
            },
            "ParamV7ForearmRootTaper": {
                "minimum": 0.0,
                "default": 0.0,
                "maximum": 1.0,
                "derivedFrom": "ParamArmElbow on the bent branch",
                "maximumCompressionPx": 4.373770766592578,
                "falloffEndPx": 22.0,
                "positiveSideOnly": True,
            },
        },
        "drawOrderBackToFront": [
            {"id": "upper_arm", "order": 100},
            {"id": "whole_hand", "order": 200},
            {"id": "production_forearm_including_bracelet", "order": 300},
            {"id": "sleeve", "order": 400},
        ],
        "deformerHierarchy": [
            {"id": "D_Shoulder", "type": "Rotation", "pivotCanvasPx": [332, 261], "parent": None},
            {"id": "D_Elbow", "type": "Rotation", "pivotCanvasPx": [355, 415], "parent": "D_Shoulder"},
            {"id": "D_ForearmRootTaper", "type": "Warp", "parent": "D_Elbow"},
            {"id": "D_Wrist", "type": "Rotation", "pivotCanvasPx": [393, 533], "parent": "D_Elbow"},
        ],
        "artMeshPrimaryController": {
            "sleeve": "D_Shoulder",
            "upper_arm": "D_Shoulder",
            "production_forearm_including_bracelet": "D_ForearmRootTaper",
            "whole_hand": "D_Wrist",
        },
        "physics": False,
        "clipping": False,
        "runtimeExport": False,
        "upperArmEngineeringLimitation": {
            "approvedV9Candidate": "B",
            "unapprovedHiddenQaPlaceholderPixels": len(upper_points),
            "qaIdentity": "H_upper-not-in-scope",
            "sourceBlueQaRgba": list(OLD_UPPER_QA_RGBA),
            "cubismMaterialQaRgba": list(upper_sample_rgba),
            "cubismMaterialQaColorSource": "deterministic adjacent approved V9 candidate-B sample",
            "completeProductionTextureClaimed": False,
        },
        "forearmWristEngineeringCorrection": {
            "f4OwnershipPixels": len(f4_points),
            "correctedEngineeringSkinPixels": len(f4_allowed_points),
            "retainedFrozenVisiblePixels": len(f4_points - f4_allowed_points),
            "h3FrozenRgba": list(h3_colors[0]),
            "f5IsQaResponsibilityNotMaterial": True,
            "separateWristMaterial": False,
        },
    }
    (CONTRACTS / "v10-minimal-cubism-rig-contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report = {
        "schemaVersion": 1,
        "status": "pass_frozen_inputs_and_v10_color_correction",
        "canvas": list(CANVAS),
        "frozenInputIntegrity": freeze_groups,
        "materials": material_report,
        "upperArmQaIdentity": {
            "mask": relative(unapproved_mask),
            "pixels": len(upper_points),
            "sourceUniqueRgba": [list(color) for color in upper_before_colors],
            "v10CubismMaterialRgba": list(upper_sample_rgba),
            "identityPreservedInAuditRatherThanBlueMaterialPollution": True,
            "completeProductionTextureClaimed": False,
        },
        "materialColorCorrectionAudit": "audit/v10-material-color-correction-audit.json",
        "drawOrderBackToFront": [
            "upper_arm",
            "whole_hand",
            "production_forearm_including_bracelet",
            "sleeve",
        ],
        "privacy": {
            "absolutePathsWritten": False,
            "sourceFilesUploaded": False,
            "cloudServicesUsed": False,
        },
    }
    (AUDIT / "v10-input-integrity-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    save_qa(LAYERS)
    save_color_correction_qa(
        upper_before,
        upper_after,
        forearm_before,
        forearm_after,
        unapproved_mask,
        f4_mask_path,
    )


if __name__ == "__main__":
    main()
