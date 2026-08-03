from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
XIAOXING = ROOT.parents[1]
VALIDATION = XIAOXING / "validation"

V14 = VALIDATION / "arm-chain-screen-left-v14-complete-textures"
V30 = VALIDATION / "arm-chain-screen-left-v30-right-structure-convergence"
V31 = VALIDATION / "arm-chain-screen-left-v31-arm-materials-from-frozen-sleeve"
V34 = VALIDATION / "arm-chain-screen-left-v34-hand-root-from-frozen-ucap"
V35 = VALIDATION / "arm-chain-screen-left-v35-frozen-arm-recomposition-review"
V36 = VALIDATION / "arm-chain-screen-left-v36-skin-boundary-wrist-cap"

SOURCE = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
SOURCE_EXPECTED_SHA256 = (
    "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5"
)

SLEEVE_COMPLETE = V31 / "masks/complete/sleeve.png"
SLEEVE_VISIBLE = V31 / "masks/visible/sleeve.png"
UPPER_COMPLETE = V31 / "masks/complete/upper_arm.png"
UPPER_VISIBLE = V31 / "masks/visible/upper_arm.png"
FOREARM_COMPLETE = V34 / "masks/complete/forearm-slim.png"
FOREARM_VISIBLE_WITH_BRACELET = V31 / "masks/visible/forearm.png"
BRACELET_MASK = V31 / "masks/visible/bracelet-owned-by-forearm.png"
HAND_COMPLETE = V36 / "masks/complete/hand.png"
HAND_TEXTURE = V36 / "materials/hand-textured-from-reset.png"

V14_REFERENCES = {
    "sleeve": V14 / "materials/sleeve.png",
    "upper_arm": V14 / "materials/upper_arm.png",
    "forearm": V14 / "materials/forearm_bracelet.png",
}

MATERIAL_OUTPUTS = {
    "sleeve": ROOT / "materials/sleeve-textured.png",
    "upper_arm": ROOT / "materials/upper-arm-textured.png",
    "forearm": ROOT / "materials/forearm-textured.png",
    "bracelet": ROOT / "materials/bracelet-owned-by-forearm-textured.png",
}

W, H = 512, 1086
SHOULDER = (170.0, 251.0)
ELBOW = (147.0, 405.0)
WRIST = (115.0, 529.0)
DRAW_ORDER = ("upper_arm", "hand", "forearm", "sleeve", "bracelet")
LIGHT_BG = (246, 248, 251, 255)
CARD_BG = (255, 255, 255)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-self-visual-qa",
        action="store_true",
        help="Record the operator's completed visual review after inspecting generated boards.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(XIAOXING).as_posix()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def load_mask(path: Path) -> np.ndarray:
    image = Image.open(path).convert("L")
    array = np.asarray(image, dtype=np.uint8)
    if array.shape != (H, W):
        raise RuntimeError(f"Unexpected mask size for {path}: {array.shape}")
    return array


def rgba_array(image_or_path: Image.Image | Path) -> np.ndarray:
    image = (
        image_or_path
        if isinstance(image_or_path, Image.Image)
        else Image.open(image_or_path)
    )
    return np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()


def rgba_image(array: np.ndarray) -> Image.Image:
    return Image.fromarray(array.astype(np.uint8), "RGBA")


def exact_alpha_image(rgb: np.ndarray, alpha: np.ndarray) -> Image.Image:
    result = np.zeros((H, W, 4), dtype=np.uint8)
    result[:, :, :3] = rgb
    result[:, :, 3] = alpha
    result[alpha == 0, :3] = 0
    return rgba_image(result)


def verify_entries(
    *,
    manifest_name: str,
    base: Path,
    entries: Iterable[dict],
    expected_key: str = "sha256",
) -> list[dict]:
    results: list[dict] = []
    for entry in entries:
        path = base / entry["path"]
        expected = entry[expected_key].lower()
        actual = sha256(path) if path.is_file() else None
        results.append(
            {
                "manifest": manifest_name,
                "path": rel(path),
                "expectedSha256": expected,
                "actualSha256": actual,
                "match": actual == expected,
            }
        )
    return results


def verify_frozen_inputs() -> dict:
    checks: list[dict] = []
    statuses: list[dict] = []

    v14_manifest_path = V14 / "audit/v14-complete-texture-freeze-manifest-2026-07-28.json"
    v14_manifest = json.loads(v14_manifest_path.read_text(encoding="utf-8"))
    statuses.append(
        {
            "id": "v14-texture-reference-only",
            "path": rel(v14_manifest_path),
            "sha256": sha256(v14_manifest_path),
            "status": v14_manifest["status"],
        }
    )
    checks.extend(
        verify_entries(
            manifest_name="v14-texture-reference-only",
            base=V14,
            entries=v14_manifest["lockedArtifacts"],
        )
    )

    v30_manifest_path = V30 / "audit/v30-sleeve-geometry-freeze-manifest-2026-07-28.json"
    v30_manifest = json.loads(v30_manifest_path.read_text(encoding="utf-8"))
    statuses.append(
        {
            "id": "v30-sleeve-upstream",
            "path": rel(v30_manifest_path),
            "sha256": sha256(v30_manifest_path),
            "status": v30_manifest["status"],
        }
    )
    checks.extend(
        verify_entries(
            manifest_name="v30-sleeve-upstream",
            base=V30,
            entries=v30_manifest["artifacts"],
        )
    )

    v31_specs = (
        (
            "v31-upper-arm",
            V31 / "audit/v31-upper-arm-geometry-freeze-manifest-2026-07-28.json",
        ),
        (
            "v31-forearm",
            V31 / "audit/v31-forearm-geometry-freeze-manifest-2026-07-29.json",
        ),
    )
    v31_manifests: dict[str, dict] = {}
    for name, path in v31_specs:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        v31_manifests[name] = manifest
        statuses.append(
            {
                "id": name,
                "path": rel(path),
                "sha256": sha256(path),
                "status": manifest["status"],
            }
        )
        checks.extend(
            verify_entries(
                manifest_name=name,
                base=V31,
                entries=manifest["lockedGeometry"],
            )
        )
        checks.extend(
            verify_entries(
                manifest_name=f"{name}:user-approval",
                base=V31,
                entries=[manifest["userApproval"]],
            )
        )

    v31_artifact_path = V31 / "audit/artifact-manifest.json"
    v31_artifact = json.loads(v31_artifact_path.read_text(encoding="utf-8"))
    checks.extend(
        verify_entries(
            manifest_name="v31-artifact-record",
            base=V31,
            entries=v31_artifact["artifacts"],
        )
    )

    v34_manifest_path = V34 / "audit/v34-hand-stage-a-freeze-manifest-2026-07-29.json"
    v34_manifest = json.loads(v34_manifest_path.read_text(encoding="utf-8"))
    statuses.append(
        {
            "id": "v34-hand-and-slim-forearm",
            "path": rel(v34_manifest_path),
            "sha256": sha256(v34_manifest_path),
            "status": v34_manifest["status"],
        }
    )
    for key in ("lockedGeometry", "lockedEvidence"):
        checks.extend(
            verify_entries(
                manifest_name=f"v34:{key}",
                base=V34,
                entries=v34_manifest[key],
            )
        )
    checks.extend(
        verify_entries(
            manifest_name="v34:user-approval",
            base=V34,
            entries=[v34_manifest["userApproval"]],
        )
    )
    for phase in ("before", "after"):
        for section in ("upperArm", "forearm"):
            node = v34_manifest["frozenUpstreamHashCheck"][phase][section]
            manifest_path = XIAOXING / node["manifest"]
            actual = sha256(manifest_path) if manifest_path.is_file() else None
            checks.append(
                {
                    "manifest": f"v34:upstream:{phase}:{section}:manifest",
                    "path": rel(manifest_path),
                    "expectedSha256": node["manifestSha256"],
                    "actualSha256": actual,
                    "match": actual == node["manifestSha256"],
                }
            )
            upstream_base = manifest_path.parent.parent
            checks.extend(
                verify_entries(
                    manifest_name=f"v34:upstream:{phase}:{section}",
                    base=upstream_base,
                    entries=[
                        {
                            "path": item["path"],
                            "expectedSha256": item["expectedSha256"],
                        }
                        for item in node["checks"]
                    ],
                    expected_key="expectedSha256",
                )
            )

    v34_artifact_path = V34 / "audit/artifact-manifest.json"
    v34_artifact = json.loads(v34_artifact_path.read_text(encoding="utf-8"))
    checks.extend(
        verify_entries(
            manifest_name="v34-artifact-record",
            base=V34,
            entries=v34_artifact["artifacts"],
        )
    )

    v35_report_path = V35 / "audit/v35-frozen-arm-recomposition-report.json"
    v35_report = json.loads(v35_report_path.read_text(encoding="utf-8"))
    for name, node in v35_report["sources"].items():
        path = XIAOXING / node["path"]
        actual = sha256(path) if path.is_file() else None
        checks.append(
            {
                "manifest": f"v35-recomposition:{name}",
                "path": rel(path),
                "expectedSha256": node["sha256"],
                "actualSha256": actual,
                "match": actual == node["sha256"],
            }
        )

    v36_manifest_path = (
        V36 / "audit/v36-hand-geometry-and-texture-freeze-manifest-2026-07-30.json"
    )
    v36_manifest = json.loads(v36_manifest_path.read_text(encoding="utf-8"))
    statuses.append(
        {
            "id": "v36-final-hand",
            "path": rel(v36_manifest_path),
            "sha256": sha256(v36_manifest_path),
            "status": v36_manifest["status"],
        }
    )
    for key in ("lockedGeometry", "lockedEvidence"):
        checks.extend(
            verify_entries(
                manifest_name=f"v36:{key}",
                base=V36,
                entries=v36_manifest[key],
            )
        )
    checks.extend(
        verify_entries(
            manifest_name="v36:user-approval",
            base=V36,
            entries=[v36_manifest["userApproval"]],
        )
    )
    upstream = v36_manifest["upstreamV34Integrity"]
    upstream_manifest_path = XIAOXING / upstream["manifest"]
    actual_upstream_manifest = sha256(upstream_manifest_path)
    checks.append(
        {
            "manifest": "v36:upstream-v34:manifest",
            "path": rel(upstream_manifest_path),
            "expectedSha256": upstream["manifestSha256"],
            "actualSha256": actual_upstream_manifest,
            "match": actual_upstream_manifest == upstream["manifestSha256"],
        }
    )
    checks.extend(
        verify_entries(
            manifest_name="v36:upstream-v34",
            base=V34,
            entries=[
                {
                    "path": item["path"],
                    "expectedSha256": item["expectedSha256"],
                }
                for item in upstream["checks"]
            ],
            expected_key="expectedSha256",
        )
    )

    v31_skeleton = json.loads((V31 / "skeleton-lock.json").read_text(encoding="utf-8"))
    v30_anchor_expected = v31_skeleton["v30SleeveEvidence"]["sha256"]
    v30_anchor_actual = sha256(v30_manifest_path)
    checks.append(
        {
            "manifest": "v31-skeleton:v30-sleeve-manifest-anchor",
            "path": rel(v30_manifest_path),
            "expectedSha256": v30_anchor_expected,
            "actualSha256": v30_anchor_actual,
            "match": v30_anchor_actual == v30_anchor_expected,
        }
    )

    source_actual = sha256(SOURCE)
    checks.append(
        {
            "manifest": "registered-reset-source",
            "path": rel(SOURCE),
            "expectedSha256": SOURCE_EXPECTED_SHA256,
            "actualSha256": source_actual,
            "match": source_actual == SOURCE_EXPECTED_SHA256,
        }
    )

    mismatches = [item for item in checks if not item["match"]]
    status_failures = [
        item
        for item in statuses
        if item["status"]
        not in {
            "frozen_v14_complete_textures_user_approved",
            "frozen_engineering_and_user_visual_pass",
        }
    ]
    return {
        "statuses": statuses,
        "checkCount": len(checks),
        "mismatchCount": len(mismatches),
        "mismatches": mismatches,
        "statusFailureCount": len(status_failures),
        "statusFailures": status_failures,
        "pass": not mismatches and not status_failures,
    }


def directory_snapshot(path: Path) -> dict:
    entries = []
    for item in sorted(path.rglob("*"), key=lambda candidate: candidate.as_posix()):
        if item.is_file():
            entries.append(
                {
                    "path": item.relative_to(path).as_posix(),
                    "sha256": sha256(item),
                }
            )
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry["sha256"].encode("ascii"))
        digest.update(b"\n")
    return {
        "root": rel(path),
        "fileCount": len(entries),
        "treeSha256": digest.hexdigest(),
        "entries": entries,
    }


def compare_snapshots(before: dict, after: dict) -> list[dict]:
    old = {item["path"]: item["sha256"] for item in before["entries"]}
    new = {item["path"]: item["sha256"] for item in after["entries"]}
    changes = []
    for path in sorted(set(old) | set(new)):
        if old.get(path) != new.get(path):
            changes.append(
                {
                    "path": path,
                    "beforeSha256": old.get(path),
                    "afterSha256": new.get(path),
                }
            )
    return changes


def nearest_seed_fill(rgb: np.ndarray, known: np.ndarray) -> np.ndarray:
    if not np.any(known):
        raise RuntimeError("Texture continuation has no registered source pixels")
    distance_input = np.where(known, 0, 1).astype(np.uint8)
    _, labels = cv2.distanceTransformWithLabels(
        distance_input,
        cv2.DIST_L2,
        5,
        labelType=cv2.DIST_LABEL_PIXEL,
    )
    maximum_label = int(labels.max())
    lookup = np.zeros((maximum_label + 1, 3), dtype=np.uint8)
    ys, xs = np.nonzero(known)
    lookup[labels[ys, xs]] = rgb[ys, xs]
    filled = lookup[labels]
    filled[known] = rgb[known]
    return filled


def build_material(
    *,
    name: str,
    complete: np.ndarray,
    visible: np.ndarray,
    source_rgb: np.ndarray,
    reference_path: Path,
    reference_exclusion: np.ndarray | None = None,
) -> tuple[Image.Image, dict]:
    complete_region = complete > 0
    visible_region = (visible > 0) & complete_region
    reference = rgba_array(reference_path)
    reference_region = (reference[:, :, 3] > 0) & complete_region
    if reference_exclusion is not None:
        reference_region &= reference_exclusion == 0
    reference_only = reference_region & ~visible_region

    rgb = np.zeros((H, W, 3), dtype=np.uint8)
    rgb[reference_region] = reference[:, :, :3][reference_region]
    rgb[visible_region] = source_rgb[visible_region]
    known = reference_region | visible_region
    continuation_region = complete_region & ~known

    nearest = nearest_seed_fill(rgb, known)
    rgb[continuation_region] = nearest[continuation_region]
    if np.any(continuation_region):
        inpaint_mask = np.where(continuation_region, 255, 0).astype(np.uint8)
        reconstructed = cv2.inpaint(
            nearest,
            inpaint_mask,
            3.0,
            cv2.INPAINT_NS,
        )
        rgb[continuation_region] = reconstructed[continuation_region]

    material = exact_alpha_image(rgb, complete)
    hidden_region = complete_region & ~visible_region
    hidden_rgb = rgb[hidden_region].astype(np.float32)
    hidden_luma = (
        hidden_rgb[:, 0] * 0.2126
        + hidden_rgb[:, 1] * 0.7152
        + hidden_rgb[:, 2] * 0.0722
    )
    unique_hidden = (
        len(np.unique(hidden_rgb.astype(np.uint8), axis=0))
        if hidden_rgb.size
        else 0
    )
    return material, {
        "name": name,
        "method": (
            "Reset visible RGB 1:1; registered V14 RGB reference only where "
            "available; remaining locked-mask interior reconstructed by "
            "deterministic nearest-source initialization plus Navier-Stokes "
            "RGB inpainting. Alpha is copied byte-for-byte from the current "
            "complete mask."
        ),
        "geometryPixels": int(np.count_nonzero(complete_region)),
        "visibleResetPixels": int(np.count_nonzero(visible_region)),
        "registeredV14ReferenceOnlyPixels": int(np.count_nonzero(reference_only)),
        "continuedInteriorPixels": int(np.count_nonzero(continuation_region)),
        "hiddenPixels": int(np.count_nonzero(hidden_region)),
        "hiddenUniqueRgbCount": unique_hidden,
        "hiddenLuminanceStdDev": (
            float(np.std(hidden_luma)) if hidden_luma.size else 0.0
        ),
        "referencePath": rel(reference_path),
        "referenceSha256": sha256(reference_path),
        "alphaBlurFeatherOrDilationUsed": False,
        "geometryMutation": "none",
    }


def build_bracelet(
    source_rgb: np.ndarray,
    bracelet: np.ndarray,
) -> tuple[Image.Image, dict]:
    region = bracelet > 0
    rgb = np.zeros((H, W, 3), dtype=np.uint8)
    rgb[region] = source_rgb[region]
    image = exact_alpha_image(rgb, bracelet)
    pixels = rgb[region].astype(np.float32)
    luma = pixels[:, 0] * 0.2126 + pixels[:, 1] * 0.7152 + pixels[:, 2] * 0.0722
    return image, {
        "name": "bracelet",
        "method": "Reset source RGB copied 1:1 under the frozen forearm-owned bracelet mask.",
        "geometryPixels": int(np.count_nonzero(region)),
        "visibleResetPixels": int(np.count_nonzero(region)),
        "registeredV14ReferenceOnlyPixels": 0,
        "continuedInteriorPixels": 0,
        "hiddenPixels": 0,
        "hiddenUniqueRgbCount": 0,
        "hiddenLuminanceStdDev": 0.0,
        "referencePath": rel(SOURCE),
        "referenceSha256": sha256(SOURCE),
        "alphaBlurFeatherOrDilationUsed": False,
        "geometryMutation": "none",
        "owner": "forearm",
        "movesWith": "forearm",
        "independentRigLayer": False,
    }


def alpha_mismatch(material: Image.Image, mask: np.ndarray) -> int:
    alpha = np.asarray(material.convert("RGBA").getchannel("A"), dtype=np.uint8)
    return int(np.count_nonzero(alpha != mask))


def visible_rgb_mismatch(
    material: Image.Image,
    source_rgb: np.ndarray,
    visible: np.ndarray,
) -> int:
    rgba = rgba_array(material)
    region = visible > 0
    return int(np.count_nonzero(np.any(rgba[:, :, :3][region] != source_rgb[region], axis=1)))


def connected_components(mask: np.ndarray) -> int:
    count, _ = cv2.connectedComponents((mask > 8).astype(np.uint8), 8)
    return int(count - 1)


def closed_holes(mask: np.ndarray) -> int:
    contours, hierarchy = cv2.findContours(
        (mask > 8).astype(np.uint8),
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if hierarchy is None:
        return 0
    return int(sum(1 for item in hierarchy[0] if item[3] >= 0))


def seam_metrics(
    material: Image.Image,
    complete: np.ndarray,
    visible: np.ndarray,
) -> dict:
    rgba = rgba_array(material)
    complete_region = complete > 0
    visible_region = (visible > 0) & complete_region
    hidden_region = complete_region & ~visible_region
    differences = []
    for dy, dx in ((0, 1), (1, 0)):
        first_visible = visible_region[: H - dy or None, : W - dx or None]
        first_hidden = hidden_region[: H - dy or None, : W - dx or None]
        second_visible = visible_region[dy:, dx:]
        second_hidden = hidden_region[dy:, dx:]
        adjacency = (first_visible & second_hidden) | (first_hidden & second_visible)
        first_rgb = rgba[: H - dy or None, : W - dx or None, :3].astype(np.float32)
        second_rgb = rgba[dy:, dx:, :3].astype(np.float32)
        delta = np.sqrt(np.sum((first_rgb - second_rgb) ** 2, axis=2))
        differences.extend(delta[adjacency].tolist())
    return {
        "visibleHiddenAdjacentPairCount": len(differences),
        "visibleHiddenMeanRgbJump": (
            float(np.mean(differences)) if differences else 0.0
        ),
        "visibleHiddenMaximumRgbJump": (
            float(np.max(differences)) if differences else 0.0
        ),
    }


def clipped_layer(image: Image.Image, alpha: np.ndarray) -> Image.Image:
    array = rgba_array(image)
    array[:, :, 3] = alpha
    array[alpha == 0, :3] = 0
    return rgba_image(array)


def compose(layers: Iterable[Image.Image]) -> Image.Image:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for layer in layers:
        canvas.alpha_composite(layer.convert("RGBA"))
    return canvas


def flatten(image: Image.Image, background=LIGHT_BG) -> Image.Image:
    canvas = Image.new("RGBA", image.size, background)
    canvas.alpha_composite(image.convert("RGBA"))
    return canvas.convert("RGB")


def crop_smooth(
    image: Image.Image,
    box: tuple[int, int, int, int],
    size: tuple[int, int],
) -> Image.Image:
    crop = image.crop(box)
    scale = min(size[0] / crop.width, size[1] / crop.height)
    crop = crop.resize(
        (
            max(1, round(crop.width * scale)),
            max(1, round(crop.height * scale)),
        ),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGB", size, CARD_BG)
    flattened = flatten(crop, CARD_BG) if crop.mode == "RGBA" else crop.convert("RGB")
    x = (size[0] - flattened.width) // 2
    y = (size[1] - flattened.height) // 2
    canvas.paste(flattened, (x, y))
    return canvas


def translate_rgba(image: Image.Image, dx: float, dy: float) -> Image.Image:
    return image.transform(
        (W, H),
        Image.Transform.AFFINE,
        (1, 0, -dx, 0, 1, -dy),
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )


def rotation_matrix(center: tuple[float, float], angle: float) -> np.ndarray:
    return cv2.getRotationMatrix2D(center, angle, 1.0)


def warp_mask(mask: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    return cv2.warpAffine(
        mask,
        matrix,
        (W, H),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def warp_rgba(
    image: Image.Image,
    matrix: np.ndarray,
    exact_mask: np.ndarray,
) -> Image.Image:
    source = rgba_array(image)
    rgb = cv2.warpAffine(
        source[:, :, :3],
        matrix,
        (W, H),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )
    return exact_alpha_image(rgb, exact_mask)


def wrist_band_width(mask: np.ndarray, angle_deg: float) -> float:
    forearm_vector = np.array(
        [WRIST[0] - ELBOW[0], WRIST[1] - ELBOW[1]],
        dtype=np.float64,
    )
    forearm_unit = forearm_vector / np.linalg.norm(forearm_vector)
    radians = math.radians(-angle_deg)
    rotation = np.array(
        [
            [math.cos(radians), -math.sin(radians)],
            [math.sin(radians), math.cos(radians)],
        ]
    )
    hand_axis = rotation @ forearm_unit
    normal = np.array([-hand_axis[1], hand_axis[0]])
    ys, xs = np.nonzero(mask > 8)
    points = np.column_stack((xs - WRIST[0], ys - WRIST[1]))
    longitudinal = points @ hand_axis
    transverse = points @ normal
    band = transverse[(longitudinal >= 8.0) & (longitudinal <= 20.0)]
    if band.size == 0:
        return 0.0
    return float(band.max() - band.min())


def make_wrist_stress(
    materials: dict[str, Image.Image],
    masks: dict[str, np.ndarray],
) -> tuple[list[dict], Image.Image]:
    angles = (-12, 0, 12)
    forearm_skin_for_components = cv2.subtract(
        masks["forearm"],
        masks["bracelet"],
    )
    board = Image.new("RGB", (1800, 760), (239, 243, 248))
    draw = ImageDraw.Draw(board)
    draw.text((40, 24), "腕部真实纹理压力检查｜冻结 V36 手部刚性旋转", font=font(34, True), fill=(24, 37, 53))
    draw.text(
        (42, 76),
        "±12°仅作穿模压力检查，不代表批准动作范围；前臂与手部 alpha 均未重画。",
        font=font(22),
        fill=(69, 83, 101),
    )
    metrics = []
    for index, angle in enumerate(angles):
        matrix = rotation_matrix(WRIST, angle)
        posed_hand_mask = warp_mask(masks["hand"], matrix)
        posed_hand = warp_rgba(materials["hand"], matrix, posed_hand_mask)
        overlap = int(
            np.count_nonzero(
                (masks["forearm"] > 8) & (posed_hand_mask > 8)
            )
        )
        bracelet_overlap = int(
            np.count_nonzero(
                (masks["bracelet"] > 8) & (posed_hand_mask > 8)
            )
        )
        union = (
            (forearm_skin_for_components > 8) | (posed_hand_mask > 8)
        ).astype(np.uint8)
        components = connected_components(union * 255)
        width = wrist_band_width(posed_hand_mask, angle)
        reference_width = wrist_band_width(
            warp_mask(masks["hand"], rotation_matrix(WRIST, angle)),
            angle,
        )
        metrics.append(
            {
                "angleDeg": angle,
                "forearmHandOverlapPx": overlap,
                "connectedComponents": components,
                "braceletHandOverlapPx": bracelet_overlap,
                "wristBandWidthPx": width,
                "frozenReferenceSamePoseWidthPx": reference_width,
                "wristWidthDeltaVsFrozenSamePosePx": width - reference_width,
                "disconnect": components != 1,
            }
        )
        posed = compose(
            [
                posed_hand,
                materials["forearm"],
                materials["bracelet"],
            ]
        )
        sample = crop_smooth(posed, (74, 480, 151, 650), (500, 560))
        x = 45 + index * 585
        board.paste(sample, (x, 142))
        draw.rounded_rectangle(
            (x, 142, x + 500, 702),
            radius=18,
            outline=(176, 189, 205),
            width=3,
        )
        draw.text(
            (x + 175, 106),
            f"{angle:+d}°",
            font=font(28, True),
            fill=(23, 41, 62),
        )
        draw.text(
            (x + 24, 710),
            f"重叠 {overlap}px｜组件 {components}｜手链接触 {bracelet_overlap}px",
            font=font(18, True),
            fill=(30, 104, 72),
        )
    return metrics, board


def make_bracelet_follow(
    materials: dict[str, Image.Image],
    masks: dict[str, np.ndarray],
) -> tuple[list[dict], Image.Image]:
    angles = (-8, 0, 8)
    board = Image.new("RGB", (1260, 650), (239, 243, 248))
    draw = ImageDraw.Draw(board)
    draw.text((32, 20), "手链随前臂检查｜同一刚性变换", font=font(29, True), fill=(24, 37, 53))
    metrics = []
    for index, angle in enumerate(angles):
        matrix = rotation_matrix(ELBOW, angle)
        posed_masks = {
            "forearm": warp_mask(masks["forearm"], matrix),
            "bracelet": warp_mask(masks["bracelet"], matrix),
            "hand": warp_mask(masks["hand"], matrix),
        }
        posed_forearm = warp_rgba(
            materials["forearm"],
            matrix,
            posed_masks["forearm"],
        )
        posed_bracelet = warp_rgba(
            materials["bracelet"],
            matrix,
            posed_masks["bracelet"],
        )
        posed_hand = warp_rgba(materials["hand"], matrix, posed_masks["hand"])
        bracelet_hand = int(
            np.count_nonzero(
                (posed_masks["bracelet"] > 8) & (posed_masks["hand"] > 8)
            )
        )
        bracelet_sleeve = int(
            np.count_nonzero(
                (posed_masks["bracelet"] > 8) & (masks["sleeve"] > 8)
            )
        )
        forearm_hand = int(
            np.count_nonzero(
                (posed_masks["forearm"] > 8) & (posed_masks["hand"] > 8)
            )
        )
        metrics.append(
            {
                "forearmRotationDeg": angle,
                "braceletUsesExactForearmTransform": True,
                "braceletHandOverlapPx": bracelet_hand,
                "braceletSleeveOverlapPx": bracelet_sleeve,
                "forearmHandOverlapPx": forearm_hand,
            }
        )
        posed = compose(
            [
                materials["upper_arm"],
                posed_hand,
                posed_forearm,
                materials["sleeve"],
                posed_bracelet,
            ]
        )
        sample = crop_smooth(posed, (48, 205, 215, 650), (365, 480))
        x = 35 + index * 405
        board.paste(sample, (x, 100))
        draw.rounded_rectangle(
            (x, 100, x + 365, 580),
            radius=16,
            outline=(176, 189, 205),
            width=3,
        )
        draw.text(
            (x + 130, 60),
            f"{angle:+d}°",
            font=font(23, True),
            fill=(23, 41, 62),
        )
        draw.text(
            (x + 30, 594),
            f"手链/手 {bracelet_hand}px｜手链/袖 {bracelet_sleeve}px",
            font=font(16, True),
            fill=(30, 104, 72),
        )
    return metrics, board


def make_displaced_check(materials: dict[str, Image.Image]) -> Image.Image:
    cases = (
        ("移开袖子｜看隐藏上臂与袖内", "sleeve", (-92, -15)),
        ("移开上臂｜看袖内与肘端", "upper_arm", (92, -4)),
        ("移开前臂+手链｜看肘端与手根", "forearm", (94, 4)),
        ("移开手部｜看冻结前臂腕帽", "hand", (92, 18)),
    )
    board = Image.new("RGB", (2200, 760), (239, 243, 248))
    draw = ImageDraw.Draw(board)
    draw.text((36, 24), "主要部件移开后的隐藏纹理检查", font=font(33, True), fill=(24, 37, 53))
    for index, (label, target, offset) in enumerate(cases):
        posed = dict(materials)
        if target == "forearm":
            posed["forearm"] = translate_rgba(materials["forearm"], *offset)
            posed["bracelet"] = translate_rgba(materials["bracelet"], *offset)
        else:
            posed[target] = translate_rgba(materials[target], *offset)
        composite = compose(posed[name] for name in DRAW_ORDER)
        sample = crop_smooth(composite, (36, 185, 235, 675), (500, 590))
        x = 35 + index * 540
        board.paste(sample, (x, 112))
        draw.rounded_rectangle(
            (x, 112, x + 500, 702),
            radius=18,
            outline=(176, 189, 205),
            width=3,
        )
        draw.text(
            (x + 10, 710),
            label,
            font=font(18, True),
            fill=(45, 57, 72),
        )
    return board


def make_boundary_closeups(
    source: Image.Image,
    complete_composite: Image.Image,
) -> Image.Image:
    boxes = (
        ("袖口 / 上臂", (100, 335, 190, 445)),
        ("肘部", (108, 372, 184, 465)),
        ("腕部 / 手链", (78, 493, 151, 585)),
    )
    board = Image.new("RGB", (1760, 740), (239, 243, 248))
    draw = ImageDraw.Draw(board)
    draw.text((34, 22), "冻结边界局部放大｜左=Reset，右=本次真实纹理", font=font(31, True), fill=(24, 37, 53))
    for index, (label, box) in enumerate(boxes):
        x = 35 + index * 570
        reset_panel = crop_smooth(source, box, (250, 540))
        texture_panel = crop_smooth(complete_composite, box, (250, 540))
        board.paste(reset_panel, (x, 106))
        board.paste(texture_panel, (x + 270, 106))
        draw.rounded_rectangle(
            (x, 106, x + 250, 646),
            radius=14,
            outline=(176, 189, 205),
            width=3,
        )
        draw.rounded_rectangle(
            (x + 270, 106, x + 520, 646),
            radius=14,
            outline=(176, 189, 205),
            width=3,
        )
        draw.text((x + 150, 662), label, font=font(18, True), fill=(45, 57, 72))
    return board


def panel(
    board: Image.Image,
    box: tuple[int, int, int, int],
    title: str,
    image: Image.Image,
    *,
    title_size: int = 22,
) -> None:
    draw = ImageDraw.Draw(board)
    left, top, right, bottom = box
    draw.rounded_rectangle(
        box,
        radius=22,
        fill=CARD_BG,
        outline=(180, 193, 210),
        width=3,
    )
    draw.text(
        (left + 20, top + 16),
        title,
        font=font(title_size, True),
        fill=(24, 37, 53),
    )
    available = (right - left - 28, bottom - top - 78)
    view = image.convert("RGB")
    view.thumbnail(available, Image.Resampling.LANCZOS)
    x = left + (right - left - view.width) // 2
    y = top + 62 + (bottom - top - 62 - view.height) // 2
    board.paste(view, (x, y))


def component_montage(materials: dict[str, Image.Image]) -> Image.Image:
    items = (
        ("袖子", materials["sleeve"]),
        ("上臂", materials["upper_arm"]),
        ("前臂", materials["forearm"]),
        ("手链（随前臂）", materials["bracelet"]),
        ("V36 冻结手部", materials["hand"]),
    )
    canvas = Image.new("RGB", (1250, 700), (248, 250, 252))
    draw = ImageDraw.Draw(canvas)
    for index, (label, image) in enumerate(items):
        x = 15 + index * 247
        draw.rounded_rectangle(
            (x, 10, x + 225, 675),
            radius=14,
            fill=(255, 255, 255),
            outline=(204, 213, 224),
            width=2,
        )
        bbox = image.getbbox()
        if bbox is None:
            continue
        item = image.crop(bbox)
        scale = min(195 / item.width, 570 / item.height)
        item = item.resize(
            (
                max(1, round(item.width * scale)),
                max(1, round(item.height * scale)),
            ),
            Image.Resampling.LANCZOS,
        )
        display = flatten(item, (246, 248, 251, 255))
        canvas.paste(display, (x + (225 - display.width) // 2, 58))
        draw.text(
            (x + 14, 20),
            label,
            font=font(17, True),
            fill=(43, 56, 73),
        )
    return canvas


def make_neutral_comparison(
    source: Image.Image,
    visible_composite: Image.Image,
) -> Image.Image:
    board = Image.new("RGB", (1450, 760), (239, 243, 248))
    draw = ImageDraw.Draw(board)
    draw.text((34, 22), "中立姿势回组与 Reset 比较", font=font(31, True), fill=(24, 37, 53))
    reset_crop = crop_smooth(source, (40, 185, 225, 665), (430, 620))
    arm_crop = crop_smooth(visible_composite, (40, 185, 225, 665), (430, 620))
    source_rgba = source.convert("RGBA")
    replaced = source_rgba.copy()
    replaced.alpha_composite(visible_composite)
    replaced_crop = crop_smooth(replaced, (40, 185, 225, 665), (430, 620))
    for index, (label, image) in enumerate(
        (
            ("Reset 局部", reset_crop),
            ("冻结可见区真实纹理", arm_crop),
            ("放回 Reset 原位", replaced_crop),
        )
    ):
        x = 30 + index * 470
        board.paste(image, (x, 94))
        draw.rounded_rectangle(
            (x, 94, x + 430, 714),
            radius=16,
            outline=(176, 189, 205),
            width=3,
        )
        draw.text((x + 105, 722), label, font=font(18, True), fill=(43, 56, 73))
    return board


def make_review_board(
    *,
    source: Image.Image,
    materials: dict[str, Image.Image],
    complete_composite: Image.Image,
    visible_composite: Image.Image,
    wrist_board: Image.Image,
    displaced_board: Image.Image,
    boundary_board: Image.Image,
    bracelet_board: Image.Image,
    engineering_pass: bool,
    alpha_mismatches: dict[str, int],
    wrist_metrics: list[dict],
) -> Image.Image:
    board = Image.new("RGB", (3800, 3000), (236, 241, 247))
    draw = ImageDraw.Draw(board)
    draw.text(
        (55, 35),
        "小星 V37｜screen-left 整臂正式纹理候选审查",
        font=font(48, True),
        fill=(20, 34, 51),
    )
    draw.text(
        (58, 104),
        "冻结内容：V31 袖子/上臂、V34 削瘦前臂、V31 前臂手链、V36 手部边界与手部纹理",
        font=font(23),
        fill=(63, 80, 101),
    )
    draw.text(
        (58, 140),
        "本次新增：仅冻结 alpha 内的袖子、上臂、前臂与手链 RGB；未画任何边界线，未进入网格/节点/参数。",
        font=font(23),
        fill=(63, 80, 101),
    )

    reset_view = crop_smooth(source, (40, 185, 225, 665), (560, 720))
    panel(board, (45, 205, 650, 1015), "1. Reset 原图局部", reset_view)
    panel(
        board,
        (680, 205, 2020, 1015),
        "2. 各部件最终真实纹理｜透明底展示，无辅助线",
        component_montage(materials),
    )
    complete_view = crop_smooth(
        complete_composite,
        (35, 185, 235, 675),
        (600, 720),
    )
    panel(
        board,
        (2050, 205, 2700, 1015),
        "3. 完整材质默认叠放",
        complete_view,
    )
    neutral = make_neutral_comparison(source, visible_composite)
    panel(
        board,
        (2730, 205, 3755, 1015),
        "4. 中立回组｜Reset / 冻结可见区 / 放回原位",
        neutral,
        title_size=20,
    )

    panel(
        board,
        (45, 1045, 1965, 1825),
        "5. 腕部中立、向内约 12°、向外约 12°",
        wrist_board,
    )
    panel(
        board,
        (1995, 1045, 3755, 1825),
        "6. 冻结边界放大｜仅并列，不在纹理上描线",
        boundary_board,
    )
    panel(
        board,
        (45, 1855, 2290, 2635),
        "7. 移开袖子 / 上臂 / 前臂+手链 / 手部后的隐藏区",
        displaced_board,
    )
    panel(
        board,
        (2320, 1855, 3755, 2635),
        "8. 手链随前臂｜同变换，不归手部",
        bracelet_board,
    )

    draw.rounded_rectangle(
        (45, 2665, 3755, 2950),
        radius=24,
        fill=(255, 255, 255),
        outline=(172, 188, 207),
        width=3,
    )
    min_overlap = min(item["forearmHandOverlapPx"] for item in wrist_metrics)
    disconnects = sum(item["disconnect"] for item in wrist_metrics)
    alpha_text = " / ".join(
        f"{name} {value}px" for name, value in alpha_mismatches.items()
    )
    result_color = (27, 113, 75) if engineering_pass else (175, 55, 48)
    draw.text(
        (78, 2698),
        (
            f"机器门禁：{'通过' if engineering_pass else '失败'}｜alpha mismatch：{alpha_text}｜"
            f"腕部最小重叠 {min_overlap}px｜断开 {disconnects}"
        ),
        font=font(24, True),
        fill=result_color,
    )
    draw.text(
        (78, 2750),
        "请重点看：隐藏上臂是否仍像同一条手臂；腕部 -12° 是否有可见手链/手部轻触；袖内纹理是否自然。",
        font=font(22, True),
        fill=(112, 61, 30),
    )
    draw.text(
        (78, 2798),
        "所有冻结边界保持不变；本板只是候选审查，未经你的视觉确认不会冻结 V37。",
        font=font(22, True),
        fill=(46, 62, 82),
    )
    draw.text(
        (78, 2850),
        "最终纹理文件没有蓝线、红线、辅助描边或棋盘背景；浅灰底仅用于本审查板展示透明素材。",
        font=font(20),
        fill=(73, 88, 106),
    )
    return board


def main() -> None:
    args = parse_args()
    integrity = verify_frozen_inputs()
    if not integrity["pass"]:
        print("冻结上游材料哈希不一致")
        print(json.dumps(integrity, ensure_ascii=False, indent=2))
        raise SystemExit(3)

    frozen_roots = {
        "v31": V31,
        "v34": V34,
        "v35": V35,
        "v36": V36,
    }
    snapshots_before = {
        name: directory_snapshot(path) for name, path in frozen_roots.items()
    }

    for folder in ("materials", "qa", "audit"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)

    source = Image.open(SOURCE).convert("RGB")
    source_rgb = np.asarray(source, dtype=np.uint8)
    masks = {
        "sleeve": load_mask(SLEEVE_COMPLETE),
        "sleeve_visible": load_mask(SLEEVE_VISIBLE),
        "upper_arm": load_mask(UPPER_COMPLETE),
        "upper_visible": load_mask(UPPER_VISIBLE),
        "forearm": load_mask(FOREARM_COMPLETE),
        "forearm_visible_with_bracelet": load_mask(
            FOREARM_VISIBLE_WITH_BRACELET
        ),
        "bracelet": load_mask(BRACELET_MASK),
        "hand": load_mask(HAND_COMPLETE),
    }
    masks["forearm_visible"] = np.minimum(
        cv2.subtract(
            masks["forearm_visible_with_bracelet"],
            masks["bracelet"],
        ),
        masks["forearm"],
    )

    sleeve, sleeve_info = build_material(
        name="sleeve",
        complete=masks["sleeve"],
        visible=masks["sleeve_visible"],
        source_rgb=source_rgb,
        reference_path=V14_REFERENCES["sleeve"],
    )
    upper, upper_info = build_material(
        name="upper_arm",
        complete=masks["upper_arm"],
        visible=masks["upper_visible"],
        source_rgb=source_rgb,
        reference_path=V14_REFERENCES["upper_arm"],
    )
    forearm, forearm_info = build_material(
        name="forearm",
        complete=masks["forearm"],
        visible=masks["forearm_visible"],
        source_rgb=source_rgb,
        reference_path=V14_REFERENCES["forearm"],
        reference_exclusion=masks["bracelet"],
    )
    bracelet, bracelet_info = build_bracelet(source_rgb, masks["bracelet"])
    # The frozen V34 forearm complete mask intentionally includes the bracelet
    # corridor and its natural loop holes. Keep the underlying skin continuation
    # for overlap support, then restore the real Reset bracelet RGB wherever the
    # bracelet-owned mask intersects that complete forearm material. The 137
    # bracelet pixels outside the complete forearm remain in the forearm-owned
    # bracelet submaterial below.
    forearm_array = rgba_array(forearm)
    bracelet_in_forearm = (
        (masks["bracelet"] > 0) & (masks["forearm"] > 0)
    )
    forearm_array[:, :, :3][bracelet_in_forearm] = source_rgb[
        bracelet_in_forearm
    ]
    forearm = rgba_image(forearm_array)
    forearm_info["braceletResetRgbPixelsInsideComplete"] = int(
        np.count_nonzero(bracelet_in_forearm)
    )
    forearm_info["braceletOutsideCompleteHandledBySubmaterialPx"] = int(
        np.count_nonzero(
            (masks["bracelet"] > 0) & (masks["forearm"] == 0)
        )
    )
    forearm_info["frozenAccessoryLoopHolesRetained"] = True
    hand = Image.open(HAND_TEXTURE).convert("RGBA")
    materials = {
        "sleeve": sleeve,
        "upper_arm": upper,
        "forearm": forearm,
        "bracelet": bracelet,
        "hand": hand,
    }
    material_info = {
        "sleeve": sleeve_info,
        "upper_arm": upper_info,
        "forearm": forearm_info,
        "bracelet": bracelet_info,
    }

    for name, path in MATERIAL_OUTPUTS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        materials[name].save(path)

    visible_layers = {
        "sleeve": clipped_layer(materials["sleeve"], masks["sleeve_visible"]),
        "upper_arm": clipped_layer(materials["upper_arm"], masks["upper_visible"]),
        "forearm": clipped_layer(materials["forearm"], masks["forearm_visible"]),
        "bracelet": clipped_layer(materials["bracelet"], masks["bracelet"]),
        "hand": clipped_layer(materials["hand"], masks["hand"]),
    }
    complete_composite = compose(materials[name] for name in DRAW_ORDER)
    visible_composite = compose(visible_layers[name] for name in DRAW_ORDER)

    complete_path = ROOT / "qa/full-arm-complete-material-composite.png"
    visible_path = ROOT / "qa/neutral-visible-recomposition.png"
    complete_composite.save(complete_path)
    visible_composite.save(visible_path)

    neutral_board = make_neutral_comparison(source, visible_composite)
    neutral_path = ROOT / "qa/neutral-reset-comparison.png"
    neutral_board.save(neutral_path)

    wrist_metrics, wrist_board = make_wrist_stress(materials, masks)
    wrist_path = ROOT / "qa/wrist-three-pose-texture-check.png"
    wrist_board.save(wrist_path)

    bracelet_metrics, bracelet_board = make_bracelet_follow(materials, masks)
    bracelet_path = ROOT / "qa/bracelet-follows-forearm-check.png"
    bracelet_board.save(bracelet_path)

    displaced_board = make_displaced_check(materials)
    displaced_path = ROOT / "qa/displaced-hidden-material-check.png"
    displaced_board.save(displaced_path)

    boundary_board = make_boundary_closeups(source, complete_composite)
    boundary_path = ROOT / "qa/frozen-boundary-closeups.png"
    boundary_board.save(boundary_path)

    alpha_masks = {
        "sleeve": masks["sleeve"],
        "upper_arm": masks["upper_arm"],
        "forearm": masks["forearm"],
        "bracelet": masks["bracelet"],
        "hand": masks["hand"],
    }
    alpha_mismatches = {
        name: alpha_mismatch(materials[name], alpha_masks[name])
        for name in alpha_masks
    }
    visible_masks = {
        "sleeve": masks["sleeve_visible"],
        "upper_arm": masks["upper_visible"],
        "forearm": masks["forearm_visible"],
        "bracelet": masks["bracelet"],
        "hand": masks["hand"],
    }
    rgb_mismatches = {
        name: visible_rgb_mismatch(
            materials[name],
            source_rgb,
            visible_masks[name],
        )
        for name in visible_masks
    }

    visible_rgba = rgba_array(visible_composite)
    target_visible_region = np.zeros((H, W), dtype=bool)
    for mask in visible_masks.values():
        target_visible_region |= mask > 8
    output_visible_region = visible_rgba[:, :, 3] > 8
    neutral_rgb_mismatch = int(
        np.count_nonzero(
            np.any(
                visible_rgba[:, :, :3][target_visible_region]
                != source_rgb[target_visible_region],
                axis=1,
            )
        )
    )
    missing_visible = int(
        np.count_nonzero(target_visible_region & ~output_visible_region)
    )
    extra_visible = int(
        np.count_nonzero(output_visible_region & ~target_visible_region)
    )
    complete_hidden_expansion = int(
        np.count_nonzero(
            (np.asarray(complete_composite.getchannel("A")) > 8)
            & ~target_visible_region
        )
    )

    topology = {
        name: {
            "connectedComponents": connected_components(mask),
            "closedHoles": closed_holes(mask),
        }
        for name, mask in alpha_masks.items()
    }
    frozen_topology_expectations = {
        "sleeve": {"connectedComponents": 1, "closedHoles": 0},
        "upper_arm": {"connectedComponents": 1, "closedHoles": 0},
        # These three holes are the frozen natural bracelet-loop openings
        # already present in masks/complete/forearm-slim.png.
        "forearm": {"connectedComponents": 1, "closedHoles": 3},
        "hand": {"connectedComponents": 1, "closedHoles": 0},
    }
    topology_main_pass = all(
        topology[name] == expected
        for name, expected in frozen_topology_expectations.items()
    )
    for name in ("sleeve", "upper_arm", "forearm"):
        material_info[name].update(
            seam_metrics(
                materials[name],
                alpha_masks[name],
                visible_masks[name],
            )
        )

    v36_report = json.loads(
        (V36 / "audit/machine-report.json").read_text(encoding="utf-8")
    )
    frozen_minimum_overlap = int(
        v36_report["geometry"]["wristStress"]["minimumOverlapPx"]
    )
    minimum_wrist_overlap = min(
        item["forearmHandOverlapPx"] for item in wrist_metrics
    )
    wrist_disconnects = sum(item["disconnect"] for item in wrist_metrics)
    wrist_width_delta = max(
        abs(item["wristWidthDeltaVsFrozenSamePosePx"])
        for item in wrist_metrics
    )
    bracelet_follow_pass = all(
        item["braceletUsesExactForearmTransform"]
        and item["braceletSleeveOverlapPx"] == 0
        for item in bracelet_metrics
    )
    hidden_texture_pass = all(
        material_info[name]["hiddenUniqueRgbCount"] >= 24
        and material_info[name]["hiddenLuminanceStdDev"] > 1.0
        for name in ("sleeve", "upper_arm", "forearm")
    )
    engineering_pass = (
        all(value == 0 for value in alpha_mismatches.values())
        and all(value == 0 for value in rgb_mismatches.values())
        and neutral_rgb_mismatch == 0
        and missing_visible == 0
        and extra_visible == 0
        and topology_main_pass
        and minimum_wrist_overlap >= frozen_minimum_overlap
        and wrist_disconnects == 0
        and wrist_width_delta == 0
        and bracelet_follow_pass
        and hidden_texture_pass
        and sha256(HAND_TEXTURE)
        == "82cc61096df0d8f9ff4db6afa800baafd5d1afa63ab3b119dc85bce371298876"
    )

    review_board = make_review_board(
        source=source,
        materials=materials,
        complete_composite=complete_composite,
        visible_composite=visible_composite,
        wrist_board=wrist_board,
        displaced_board=displaced_board,
        boundary_board=boundary_board,
        bracelet_board=bracelet_board,
        engineering_pass=engineering_pass,
        alpha_mismatches=alpha_mismatches,
        wrist_metrics=wrist_metrics,
    )
    review_path = ROOT / "qa/V37-screen-left整臂正式纹理-中文审查图.png"
    review_board.save(review_path)

    snapshots_after = {
        name: directory_snapshot(path) for name, path in frozen_roots.items()
    }
    frozen_changes = []
    snapshot_summary = {}
    for name in frozen_roots:
        changes = compare_snapshots(snapshots_before[name], snapshots_after[name])
        frozen_changes.extend(
            {"root": snapshots_before[name]["root"], **change}
            for change in changes
        )
        snapshot_summary[name] = {
            "root": snapshots_before[name]["root"],
            "fileCountBefore": snapshots_before[name]["fileCount"],
            "fileCountAfter": snapshots_after[name]["fileCount"],
            "treeSha256Before": snapshots_before[name]["treeSha256"],
            "treeSha256After": snapshots_after[name]["treeSha256"],
            "unchanged": not changes,
        }
    if frozen_changes:
        raise RuntimeError("Frozen directory changed during V37 generation")

    logical_outputs = [
        *MATERIAL_OUTPUTS.values(),
        complete_path,
        visible_path,
        neutral_path,
        wrist_path,
        bracelet_path,
        displaced_path,
        boundary_path,
        review_path,
        HERE,
    ]
    output_records = [
        {
            "path": rel(path),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in logical_outputs
    ]

    frozen_inputs = [
        ("resetColorMaster", SOURCE),
        ("sleeveCompleteMask", SLEEVE_COMPLETE),
        ("sleeveVisibleMask", SLEEVE_VISIBLE),
        ("upperArmCompleteMask", UPPER_COMPLETE),
        ("upperArmVisibleMask", UPPER_VISIBLE),
        ("forearmSlimCompleteMask", FOREARM_COMPLETE),
        ("forearmVisibleWithBracelet", FOREARM_VISIBLE_WITH_BRACELET),
        ("braceletOwnedByForearmMask", BRACELET_MASK),
        ("handCompleteMask", HAND_COMPLETE),
        ("handFrozenTexture", HAND_TEXTURE),
        (
            "v31UpperFreezeManifest",
            V31 / "audit/v31-upper-arm-geometry-freeze-manifest-2026-07-28.json",
        ),
        (
            "v31ForearmFreezeManifest",
            V31 / "audit/v31-forearm-geometry-freeze-manifest-2026-07-29.json",
        ),
        (
            "v34HandFreezeManifest",
            V34 / "audit/v34-hand-stage-a-freeze-manifest-2026-07-29.json",
        ),
        (
            "v35RecompositionReport",
            V35 / "audit/v35-frozen-arm-recomposition-report.json",
        ),
        (
            "v36HandFreezeManifest",
            V36 / "audit/v36-hand-geometry-and-texture-freeze-manifest-2026-07-30.json",
        ),
        (
            "v14TextureReferenceManifest",
            V14 / "audit/v14-complete-texture-freeze-manifest-2026-07-28.json",
        ),
    ]
    frozen_input_records = {
        name: {
            "path": rel(path),
            "sha256": sha256(path),
        }
        for name, path in frozen_inputs
    }

    report = {
        "schemaVersion": 1,
        "checkpoint": "V37 screen-left full-arm textures inside frozen geometry",
        "status": (
            "engineering_pass_pending_user_visual_approval"
            if engineering_pass
            else "engineering_fail_stop_at_earliest_failure"
        ),
        "decisionOwner": "user",
        "scope": (
            "screen-left sleeve, upper arm, slim forearm skin, forearm-owned "
            "bracelet, and byte-preserved V36 hand texture only"
        ),
        "sourcePathDiscovery": {
            "rule": "Use the registered Reset path from existing reports/scripts; do not guess.",
            "evidence": [
                rel(V35 / "tools/build_v35_frozen_arm_review.py"),
                rel(V36 / "tools/build_v36_user_blue_hand_boundary.py"),
                rel(V31 / "layering-contract.json"),
            ],
            "source": {
                "path": rel(SOURCE),
                "sha256": sha256(SOURCE),
            },
        },
        "frozenIntegrity": {
            "preflight": integrity,
            "directorySnapshots": snapshot_summary,
            "changedFrozenFiles": frozen_changes,
            "modifiedAnyFrozenFile": bool(frozen_changes),
            "pass": integrity["pass"] and not frozen_changes,
        },
        "frozenInputs": frozen_input_records,
        "textureMethod": {
            "visiblePixels": "Reset RGB copied 1:1 inside current visible ownership.",
            "hiddenPixels": (
                "Registered V14 RGB is used only as same-canvas texture/color "
                "reference. Remaining pixels are continued inside the current "
                "complete alpha by deterministic RGB-only inpainting."
            ),
            "oldAlphaUsed": False,
            "alphaSource": "current V31/V34/V36 complete masks only",
            "alphaBlurFeatherOrDilationUsed": False,
            "diagnosticLinesDrawnOnFinalTextures": False,
            "checkerboardUsedAsTextureInput": False,
        },
        "materials": {},
        "neutralRecomposition": {
            "approvedVisibleOwnershipPixels": int(
                np.count_nonzero(target_visible_region)
            ),
            "missingVisibleTexturePx": missing_visible,
            "extraOutsideFrozenVisibleOwnershipPx": extra_visible,
            "sourceRgbMismatchPx": neutral_rgb_mismatch,
            "completeMaterialHiddenExpansionPx": complete_hidden_expansion,
            "note": (
                "Hidden expansion is intentionally excluded from the neutral "
                "visible silhouette comparison and is reviewed separately in "
                "the displaced-part board."
            ),
            "visibleRecomposition": rel(visible_path),
            "resetComparison": rel(neutral_path),
        },
        "topologyAndHiddenMaterial": {
            "mainParts": topology,
            "frozenTopologyExpectations": frozen_topology_expectations,
            "forearmHoleClassification": (
                "three frozen natural bracelet-loop openings; no new hole was "
                "introduced by texture work"
            ),
            "mainPartsPass": topology_main_pass,
            "displacedReview": rel(displaced_path),
            "hiddenTextureNotFlatPass": hidden_texture_pass,
        },
        "wristStress": {
            "anglesDeg": [-12, 0, 12],
            "frozenMinimumOverlapBaselinePx": frozen_minimum_overlap,
            "minimumOverlapPx": minimum_wrist_overlap,
            "disconnectCount": wrist_disconnects,
            "maximumWristWidthDeltaVsFrozenSamePosePx": wrist_width_delta,
            "samples": wrist_metrics,
            "pass": (
                minimum_wrist_overlap >= frozen_minimum_overlap
                and wrist_disconnects == 0
                and wrist_width_delta == 0
            ),
            "review": rel(wrist_path),
            "diagnosticOnlyNotApprovedMotionRange": True,
        },
        "braceletFollow": {
            "owner": "forearm",
            "movesWith": "forearm",
            "samples": bracelet_metrics,
            "pass": bracelet_follow_pass,
            "review": rel(bracelet_path),
        },
        "outputFiles": output_records,
        "engineeringPass": engineering_pass,
        "selfVisualQa": {
            "status": (
                "completed"
                if args.confirm_self_visual_qa
                else "pending_operator_review"
            ),
            "reviewedArtifacts": (
                [
                    rel(review_path),
                    rel(displaced_path),
                    rel(wrist_path),
                    rel(boundary_path),
                ]
                if args.confirm_self_visual_qa
                else []
            ),
            "notes": (
                [
                    "No blue/red guide or checker pattern appears in final texture files.",
                    "Neutral visible reconstruction retains the Reset texture and silhouette.",
                    "Hidden roots are textured and remain inside the frozen masks.",
                    "The -12 degree sample has a 3 px bracelet/hand raster contact inherited from frozen geometry; no visible gross penetration was accepted by automation.",
                ]
                if args.confirm_self_visual_qa
                else ["Run visual inspection before using --confirm-self-visual-qa."]
            ),
        },
        "visualRisksPendingUserApproval": [
            (
                "The complete upper arm has only 310 directly visible Reset "
                "pixels; most hidden texture is registered V14/Reset-derived "
                "continuation and needs human review when displaced."
            ),
            (
                "At -12 degrees the frozen hand and forearm-owned bracelet have "
                "a 3 px raster contact; inspect the wrist panel for visible "
                "penetration. The geometry was not changed."
            ),
            (
                "The sleeve shoulder interior is normally occluded by body/hair; "
                "judge its material flow in the displaced-part panel."
            ),
        ],
        "userVisualApproval": {
            "status": "pending",
            "reviewBoard": rel(review_path),
            "engineeringChecksDoNotReplaceVisualApproval": True,
            "freezeAuthorized": False,
        },
        "explicitlyNotPerformed": [
            "right arm",
            "body",
            "ArtMesh",
            "mesh",
            "nodes",
            "parameters",
            "animation",
            "Physics",
            "runtime integration",
            "desktop-pet window behavior",
            "modification of V31/V34/V35/V36",
            "freezing V37",
        ],
    }
    for name in ("sleeve", "upper_arm", "forearm", "bracelet"):
        report["materials"][name] = {
            **material_info[name],
            "output": rel(MATERIAL_OUTPUTS[name]),
            "sha256": sha256(MATERIAL_OUTPUTS[name]),
            "alphaMask": rel(alpha_masks_path(name)),
            "alphaMaskSha256": sha256(alpha_masks_path(name)),
            "alphaMismatchPx": alpha_mismatches[name],
            "visibleResetRgbMismatchPx": rgb_mismatches[name],
            "topology": topology[name],
        }
    report["materials"]["hand"] = {
        "output": rel(HAND_TEXTURE),
        "sha256": sha256(HAND_TEXTURE),
        "reusedFrozenFileByReference": True,
        "copiedOrModified": False,
        "alphaMask": rel(HAND_COMPLETE),
        "alphaMaskSha256": sha256(HAND_COMPLETE),
        "alphaMismatchPx": alpha_mismatches["hand"],
        "visibleResetRgbMismatchPx": rgb_mismatches["hand"],
        "topology": topology["hand"],
    }

    report_path = ROOT / "audit/machine-report.json"
    write_json(report_path, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "engineeringPass": engineering_pass,
                "frozenInputMismatchCount": integrity["mismatchCount"],
                "frozenFilesModified": bool(frozen_changes),
                "alphaMismatchPx": alpha_mismatches,
                "neutralSourceRgbMismatchPx": neutral_rgb_mismatch,
                "minimumWristOverlapPx": minimum_wrist_overlap,
                "wristDisconnectCount": wrist_disconnects,
                "reviewBoard": rel(review_path),
                "machineReport": rel(report_path),
                "machineReportSha256": sha256(report_path),
                "selfVisualQa": report["selfVisualQa"]["status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not engineering_pass:
        raise SystemExit(2)


def alpha_masks_path(name: str) -> Path:
    return {
        "sleeve": SLEEVE_COMPLETE,
        "upper_arm": UPPER_COMPLETE,
        "forearm": FOREARM_COMPLETE,
        "bracelet": BRACELET_MASK,
        "hand": HAND_COMPLETE,
    }[name]


if __name__ == "__main__":
    main()
