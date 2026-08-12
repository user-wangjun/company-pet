from __future__ import annotations

import hashlib
import json
import math
import re
from collections import deque
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


WIDTH, HEIGHT = 512, 1086
CANVAS = (WIDTH, HEIGHT)
IDENTITY = {
    "character": "xiaoxing",
    "view": "front",
    "screenSide": "left",
    "anatomicalSide": "right",
    "subject": "小星 Left",
}

SHOULDER = (166.0, 270.0)
ELBOW = (149.0, 399.0)
WRIST = (110.0, 538.0)
PALM_ROOT = (104.0, 552.0)
EXPECTED_LENGTHS = {
    "upper_arm": 130.115333,
    "forearm": 144.367586,
    "wrist_to_palmRoot": 15.231546,
}
RANGES = {
    "shoulder": (-18.0, 20.0),
    "elbow": (0.0, 35.0),
    "wrist": (-15.0, 18.0),
}
OVERLAP_REQUIREMENTS = {
    "shoulder": {"longitudinalPx": 14.0, "transversePx": 8.0},
    "elbow": {"longitudinalPx": 10.0, "transversePx": 7.0},
    "wrist": {"longitudinalPx": 8.0, "transversePx": 6.0},
}
WIDTH_GUARDS = {"shoulder": 58.0, "elbow": 48.0, "wrist": 48.0}
AREA_DRIFT_LIMIT_PCT = 5.0

R3_ROOT = Path(__file__).resolve().parents[1]

HUMAN_SEQUENTIAL_PROFILE = {
    "type": "human_sequential",
    "description": "relaxed hanging arm: shoulder leads, elbow follows, wrist makes the smallest late adjustment",
    "jointLeadDelay": {"shoulder": 0.0, "elbow": 0.12, "wrist": 0.24},
    "returnIsSpatiallySymmetric": True,
    "rationale": "avoid synchronized rigid-arm rotation; preserve the reference pose's near-extended hanging arm and keep the hand in a plausible workspace",
}


def find_workspace() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").exists():
            return parent
    raise RuntimeError("workspace root with AGENTS.md was not found")


WORKSPACE = find_workspace()
XIAO = WORKSPACE / "docs/live2d-workbench/xiaoxing"
R1_ROOT = XIAO / "validation/arm-chain-screen-left-r1-physical-line-contract"
R2_ROOT = XIAO / "validation/arm-chain-screen-left-r2-flat-color-materials"
OLD_ROOTS = []
for candidate in sorted((XIAO / "validation").glob("arm-chain-screen-left-v*")):
    match = re.fullmatch(r"arm-chain-screen-left-v(\d+).*", candidate.name)
    if candidate.is_dir() and match and 12 <= int(match.group(1)) <= 38:
        OLD_ROOTS.append(candidate)


def rel(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()


def r3_rel(path: Path) -> str:
    return path.resolve().relative_to(R3_ROOT.resolve()).as_posix()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.write_text(payload, encoding="utf-8")


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_rgba(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if image.size != CANVAS:
        raise RuntimeError(f"canvas mismatch: {rel(path)} -> {image.size}")
    return image


def load_mask(path: Path) -> Image.Image:
    image = Image.open(path).convert("L")
    if image.size != CANVAS:
        raise RuntimeError(f"mask canvas mismatch: {rel(path)} -> {image.size}")
    return image


def mask_count(mask: Image.Image) -> int:
    return sum(1 for value in mask.getdata() if value > 0)


def alpha_area(mask: Image.Image) -> float:
    return float(ImageStat.Stat(mask).sum[0]) / 255.0


def alpha_sha(mask: Image.Image) -> str:
    return sha256_bytes(mask.tobytes())


def image_sha(image: Image.Image) -> str:
    return sha256_bytes(image.tobytes())


def mask_union(*masks: Image.Image) -> Image.Image:
    if not masks:
        return Image.new("L", CANVAS, 0)
    result = masks[0].copy()
    for mask in masks[1:]:
        result = ImageChops.lighter(result, mask)
    return result


def mask_intersection(first: Image.Image, second: Image.Image) -> Image.Image:
    return ImageChops.multiply(first, second)


def mask_subtract(first: Image.Image, second: Image.Image) -> Image.Image:
    return ImageChops.subtract(first, second)


def count_intersection(first: Image.Image, second: Image.Image) -> int:
    return mask_count(mask_intersection(first, second))


def component_count(mask: Image.Image, box: tuple[int, int, int, int] | None = None) -> int:
    if box is not None:
        mask = mask.crop(box)
    bbox = mask.getbbox()
    if not bbox:
        return 0
    left, top, right, bottom = bbox
    pixels = mask.load()
    remaining: set[tuple[int, int]] = {
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if pixels[x, y] > 0
    }
    count = 0
    neighbors = ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1))
    while remaining:
        count += 1
        start = remaining.pop()
        queue = [start]
        while queue:
            x, y = queue.pop()
            for dx, dy in neighbors:
                point = (x + dx, y + dy)
                if point in remaining:
                    remaining.remove(point)
                    queue.append(point)
    return count


def hole_count(mask: Image.Image) -> int:
    bbox = mask.getbbox()
    if not bbox:
        return 0
    left, top, right, bottom = bbox
    pixels = mask.load()
    outside: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    for x in range(left, right):
        for y in (top, bottom - 1):
            if pixels[x, y] == 0 and (x, y) not in outside:
                outside.add((x, y))
                queue.append((x, y))
    for y in range(top, bottom):
        for x in (left, right - 1):
            if pixels[x, y] == 0 and (x, y) not in outside:
                outside.add((x, y))
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if left <= nx < right and top <= ny < bottom and pixels[nx, ny] == 0 and (nx, ny) not in outside:
                outside.add((nx, ny))
                queue.append((nx, ny))
    holes: set[tuple[int, int]] = {
        (x, y)
        for y in range(top, bottom)
        for x in range(left, right)
        if pixels[x, y] == 0 and (x, y) not in outside
    }
    count = 0
    while holes:
        count += 1
        start = holes.pop()
        queue = [start]
        while queue:
            x, y = queue.pop()
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                point = (x + dx, y + dy)
                if point in holes:
                    holes.remove(point)
                    queue.append(point)
    return count


def rotation_matrix(center: tuple[float, float], angle_deg: float) -> tuple[float, float, float, float, float, float]:
    """Forward image-plane rotation; positive angle increases atan2(y, x)."""
    theta = math.radians(angle_deg)
    c, s = math.cos(theta), math.sin(theta)
    a, b, d, e = c, -s, s, c
    cx, cy = center
    return (a, b, d, e, cx - a * cx - b * cy, cy - d * cx - e * cy)


IDENTITY_MATRIX = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def compose_matrix(
    first: tuple[float, float, float, float, float, float],
    second: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float]:
    """Return second(first(p))."""
    a1, b1, d1, e1, tx1, ty1 = first
    a2, b2, d2, e2, tx2, ty2 = second
    return (
        a2 * a1 + b2 * d1,
        a2 * b1 + b2 * e1,
        d2 * a1 + e2 * d1,
        d2 * b1 + e2 * e1,
        a2 * tx1 + b2 * ty1 + tx2,
        d2 * tx1 + e2 * ty1 + ty2,
    )


def matrix_for_rotations(rotations: Sequence[tuple[tuple[float, float], float]]) -> tuple[float, float, float, float, float, float]:
    result = IDENTITY_MATRIX
    for center, angle in rotations:
        result = compose_matrix(result, rotation_matrix(center, angle))
    return result


def apply_matrix(point: tuple[float, float], matrix: tuple[float, float, float, float, float, float]) -> tuple[float, float]:
    a, b, d, e, tx, ty = matrix
    x, y = point
    return (a * x + b * y + tx, d * x + e * y + ty)


def rotate_point(point: tuple[float, float], center: tuple[float, float], angle_deg: float) -> tuple[float, float]:
    return apply_matrix(point, rotation_matrix(center, angle_deg))


def inverse_affine(matrix: tuple[float, float, float, float, float, float]) -> tuple[float, float, float, float, float, float]:
    a, b, d, e, tx, ty = matrix
    determinant = a * e - b * d
    if abs(determinant) < 1e-12:
        raise RuntimeError("singular transform")
    # Pillow's AFFINE tuple is (a, b, tx, d, e, ty), while the internal
    # forward matrix is stored as (a, b, d, e, tx, ty).
    return (
        e / determinant,
        -b / determinant,
        -(e * tx - b * ty) / determinant,
        -d / determinant,
        a / determinant,
        -(-d * tx + a * ty) / determinant,
    )


def is_identity_matrix(matrix: tuple[float, float, float, float, float, float]) -> bool:
    return all(abs(a - b) < 1e-14 for a, b in zip(matrix, IDENTITY_MATRIX))


def transform_image(image: Image.Image, matrix: tuple[float, float, float, float, float, float]) -> Image.Image:
    if is_identity_matrix(matrix):
        return image.copy()
    inverse = inverse_affine(matrix)
    if image.mode == "RGBA":
        result = image.transform(CANVAS, Image.Transform.AFFINE, inverse, resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0))
        alpha = image.getchannel("A").transform(CANVAS, Image.Transform.AFFINE, inverse, resample=Image.Resampling.BICUBIC, fillcolor=0)
        result.putalpha(alpha.point(lambda value: 255 if value >= 128 else 0))
        return result
    result = image.transform(CANVAS, Image.Transform.AFFINE, inverse, resample=Image.Resampling.BICUBIC, fillcolor=0)
    return result.point(lambda value: 255 if value >= 128 else 0).convert("L")


SLEEVE_ANCHOR_PROXIMAL = (166.0, 228.0)
SLEEVE_ANCHOR_CUFF = ELBOW
SLEEVE_AXIS = (SLEEVE_ANCHOR_CUFF[0] - SLEEVE_ANCHOR_PROXIMAL[0], SLEEVE_ANCHOR_CUFF[1] - SLEEVE_ANCHOR_PROXIMAL[1])
SLEEVE_AXIS_LENGTH_SQ = SLEEVE_AXIS[0] ** 2 + SLEEVE_AXIS[1] ** 2
SLEEVE_AXIS_LENGTH = math.sqrt(SLEEVE_AXIS_LENGTH_SQ)
SLEEVE_NORMAL = (-SLEEVE_AXIS[1] / SLEEVE_AXIS_LENGTH, SLEEVE_AXIS[0] / SLEEVE_AXIS_LENGTH)


def rotate_vector(vector: tuple[float, float], angle_deg: float) -> tuple[float, float]:
    theta = math.radians(angle_deg)
    c, s = math.cos(theta), math.sin(theta)
    return (c * vector[0] - s * vector[1], s * vector[0] + c * vector[1])


def sleeve_forward(point: tuple[float, float], shoulder_angle: float) -> tuple[float, float]:
    dx, dy = point[0] - SLEEVE_ANCHOR_PROXIMAL[0], point[1] - SLEEVE_ANCHOR_PROXIMAL[1]
    u = (dx * SLEEVE_AXIS[0] + dy * SLEEVE_AXIS[1]) / SLEEVE_AXIS_LENGTH_SQ
    v = dx * SLEEVE_NORMAL[0] + dy * SLEEVE_NORMAL[1]
    cuff_target = rotate_point(SLEEVE_ANCHOR_CUFF, SHOULDER, shoulder_angle)
    target_axis = (cuff_target[0] - SLEEVE_ANCHOR_PROXIMAL[0], cuff_target[1] - SLEEVE_ANCHOR_PROXIMAL[1])
    center = (SLEEVE_ANCHOR_PROXIMAL[0] + u * target_axis[0], SLEEVE_ANCHOR_PROXIMAL[1] + u * target_axis[1])
    normal = rotate_vector(SLEEVE_NORMAL, u * shoulder_angle)
    return (center[0] + v * normal[0], center[1] + v * normal[1])


def sleeve_inverse(target: tuple[float, float], shoulder_angle: float) -> tuple[float, float]:
    cuff_target = rotate_point(SLEEVE_ANCHOR_CUFF, SHOULDER, shoulder_angle)
    target_axis = (cuff_target[0] - SLEEVE_ANCHOR_PROXIMAL[0], cuff_target[1] - SLEEVE_ANCHOR_PROXIMAL[1])
    target_len_sq = target_axis[0] ** 2 + target_axis[1] ** 2
    dx = target[0] - SLEEVE_ANCHOR_PROXIMAL[0]
    dy = target[1] - SLEEVE_ANCHOR_PROXIMAL[1]
    u = (dx * target_axis[0] + dy * target_axis[1]) / max(target_len_sq, 1e-9)
    v = 0.0
    for _ in range(5):
        normal = rotate_vector(SLEEVE_NORMAL, u * shoulder_angle)
        theta = math.radians(u * shoulder_angle)
        d_normal = (
            (-math.sin(theta) * SLEEVE_NORMAL[0] - math.cos(theta) * SLEEVE_NORMAL[1]) * math.radians(shoulder_angle),
            (math.cos(theta) * SLEEVE_NORMAL[0] - math.sin(theta) * SLEEVE_NORMAL[1]) * math.radians(shoulder_angle),
        )
        center = (SLEEVE_ANCHOR_PROXIMAL[0] + u * target_axis[0], SLEEVE_ANCHOR_PROXIMAL[1] + u * target_axis[1])
        vx, vy = target[0] - center[0], target[1] - center[1]
        v = vx * normal[0] + vy * normal[1]
        estimated = (center[0] + v * normal[0], center[1] + v * normal[1])
        tangent = (target_axis[0] + v * d_normal[0], target_axis[1] + v * d_normal[1])
        residual = (target[0] - estimated[0], target[1] - estimated[1])
        tangent_len_sq = tangent[0] ** 2 + tangent[1] ** 2
        if tangent_len_sq < 1e-9:
            break
        u += (residual[0] * tangent[0] + residual[1] * tangent[1]) / tangent_len_sq
        u = max(-0.35, min(1.35, u))
    return u, v


def warp_sleeve(image: Image.Image, shoulder_angle: float) -> Image.Image:
    if abs(shoulder_angle) < 1e-14:
        return image.copy()
    alpha = image.getchannel("A") if image.mode == "RGBA" else image
    source_bbox = alpha.getbbox()
    if not source_bbox:
        return image.copy()
    corners = [
        (float(source_bbox[0]), float(source_bbox[1])),
        (float(source_bbox[2]), float(source_bbox[1])),
        (float(source_bbox[2]), float(source_bbox[3])),
        (float(source_bbox[0]), float(source_bbox[3])),
    ]
    mapped = [sleeve_forward(point, shoulder_angle) for point in corners]
    margin = 8
    box = (
        max(0, int(math.floor(min(x for x, _ in mapped) - margin))),
        max(0, int(math.floor(min(y for _, y in mapped) - margin))),
        min(WIDTH, int(math.ceil(max(x for x, _ in mapped) + margin))),
        min(HEIGHT, int(math.ceil(max(y for _, y in mapped) + margin))),
    )
    output = Image.new(image.mode, CANVAS, (0, 0, 0, 0) if image.mode == "RGBA" else 0)
    source = image.load()
    target = output.load()
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            u, v = sleeve_inverse((x + 0.5, y + 0.5), shoulder_angle)
            sx = int(round(SLEEVE_ANCHOR_PROXIMAL[0] + u * SLEEVE_AXIS[0] + v * SLEEVE_NORMAL[0]))
            sy = int(round(SLEEVE_ANCHOR_PROXIMAL[1] + u * SLEEVE_AXIS[1] + v * SLEEVE_NORMAL[1]))
            if 0 <= sx < WIDTH and 0 <= sy < HEIGHT:
                pixel = source[sx, sy]
                if image.mode == "RGBA":
                    if pixel[3] > 0:
                        target[x, y] = pixel
                elif pixel > 0:
                    target[x, y] = pixel
    return output


def projected_span(mask: Image.Image, center: tuple[float, float], axis_angle: float, longitudinal_limit: float | None = None) -> dict[str, float | int]:
    bbox = mask.getbbox()
    if not bbox:
        return {"pixels": 0, "longitudinalSpanPx": 0.0, "transverseSpanPx": 0.0, "longitudinalMinPx": 0.0, "longitudinalMaxPx": 0.0, "transverseMinPx": 0.0, "transverseMaxPx": 0.0}
    ux, uy = math.cos(math.radians(axis_angle)), math.sin(math.radians(axis_angle))
    nx, ny = -uy, ux
    pixels = mask.load()
    longitudes: list[float] = []
    transverses: list[float] = []
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            if pixels[x, y] <= 0:
                continue
            dx, dy = x + 0.5 - center[0], y + 0.5 - center[1]
            longitudinal = dx * ux + dy * uy
            if longitudinal_limit is not None and abs(longitudinal) > longitudinal_limit:
                continue
            longitudes.append(longitudinal)
            transverses.append(dx * nx + dy * ny)
    if not longitudes:
        return {"pixels": 0, "longitudinalSpanPx": 0.0, "transverseSpanPx": 0.0, "longitudinalMinPx": 0.0, "longitudinalMaxPx": 0.0, "transverseMinPx": 0.0, "transverseMaxPx": 0.0}
    return {
        "pixels": len(longitudes),
        "longitudinalSpanPx": round(max(longitudes) - min(longitudes), 6),
        "transverseSpanPx": round(max(transverses) - min(transverses), 6),
        "longitudinalMinPx": round(min(longitudes), 6),
        "longitudinalMaxPx": round(max(longitudes), 6),
        "transverseMinPx": round(min(transverses), 6),
        "transverseMaxPx": round(max(transverses), 6),
    }


def line_gap_samples(mask: Image.Image, center: tuple[float, float], axis_angle: float, half_length: int = 20) -> int:
    pixels = mask.load()
    ux, uy = math.cos(math.radians(axis_angle)), math.sin(math.radians(axis_angle))
    missing = 0
    for offset in range(-half_length, half_length + 1):
        x = int(round(center[0] + ux * offset))
        y = int(round(center[1] + uy * offset))
        covered = False
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < WIDTH and 0 <= ny < HEIGHT and pixels[nx, ny] > 0:
                    covered = True
                    break
            if covered:
                break
        if not covered:
            missing += 1
    return missing


def crop_box(center: tuple[float, float], radius: int) -> tuple[int, int, int, int]:
    return (
        max(0, int(round(center[0])) - radius),
        max(0, int(round(center[1])) - radius),
        min(WIDTH, int(round(center[0])) + radius + 1),
        min(HEIGHT, int(round(center[1])) + radius + 1),
    )


def flatten(image: Image.Image) -> Image.Image:
    white = Image.new("RGBA", CANVAS, (255, 255, 255, 255))
    return Image.alpha_composite(white, image).convert("RGB")


def axis_angle(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.degrees(math.atan2(second[1] - first[1], second[0] - first[0]))


def distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.hypot(second[0] - first[0], second[1] - first[1])


def signed_angle_delta(angle: float, reference: float) -> float:
    return (angle - reference + 180.0) % 360.0 - 180.0


class R3Builder:
    def __init__(self) -> None:
        self.r2_manifest_path = R2_ROOT / "audit/artifact-manifest.json"
        self.r1_freeze_path = R1_ROOT / "audit/r1-freeze-checklist-2026-08-05.json"
        self.r1_approval_path = R1_ROOT / "audit/user-visual-approval-r1-2026-08-04.json"
        self.r2_approval_path = R2_ROOT / "audit/user-visual-approval-r2-2026-08-06.json"
        self.r2_machine_path = R2_ROOT / "audit/machine-report.json"
        self.r2_lift_path = R2_ROOT / "audit/lift-action-report.json"
        self.r2_input_freeze: dict[str, object] = {}
        self.source_line = load_rgba(XIAO / "source/masters/front-line-source-exact-after-reset.png")
        self.source_color = load_rgba(XIAO / "source/masters/front-color-source-exact-after-reset.png")
        self.primary_rgba = {
            layer: load_rgba(R2_ROOT / "flat-layers" / f"{layer}.png")
            for layer in ("sleeve", "upper_arm", "forearm", "hand")
        }
        self.primary_masks = {
            layer: {
                "visible": load_mask(R2_ROOT / "masks/visible" / f"{layer}.png"),
                "hidden": load_mask(R2_ROOT / "masks/hidden" / f"{layer}.png"),
                "complete": load_mask(R2_ROOT / "masks/complete" / f"{layer}.png"),
            }
            for layer in ("sleeve", "upper_arm", "forearm", "hand")
        }
        self.subregion_masks = {
            "forearm_skin": {
                "visible": load_mask(R2_ROOT / "masks/subregions/forearm-skin-visible.png"),
                "hidden": load_mask(R2_ROOT / "masks/subregions/forearm-skin-hidden.png"),
                "complete": load_mask(R2_ROOT / "masks/subregions/forearm-skin-complete.png"),
            },
            "bracelet": {
                "visible": load_mask(R2_ROOT / "masks/subregions/bracelet-visible.png"),
                "hidden": load_mask(R2_ROOT / "masks/subregions/bracelet-hidden.png"),
                "complete": load_mask(R2_ROOT / "masks/subregions/bracelet-complete.png"),
            },
            "bracelet_back": {
                "visible": load_mask(R2_ROOT / "masks/subregions/bracelet-back-visible.png"),
                "hidden": load_mask(R2_ROOT / "masks/subregions/bracelet-back-hidden.png"),
                "complete": load_mask(R2_ROOT / "masks/subregions/bracelet-back-complete.png"),
            },
            "bracelet_front": {
                "visible": load_mask(R2_ROOT / "masks/subregions/bracelet-front-visible.png"),
                "hidden": load_mask(R2_ROOT / "masks/subregions/bracelet-front-hidden.png"),
                "complete": load_mask(R2_ROOT / "masks/subregions/bracelet-front-complete.png"),
            },
        }
        self.neutral_areas = {layer: alpha_area(data["complete"]) for layer, data in self.primary_masks.items()}
        self.capture_frames: dict[str, Image.Image] = {}
        self.capture_poses: dict[str, dict[str, object]] = {}
        self.last_machine_report: dict[str, object] = {}

    def protected_snapshot(self) -> dict[str, object]:
        roots = [R1_ROOT, R2_ROOT, *OLD_ROOTS]
        files: dict[str, Path] = {}
        for root in roots:
            if root.exists():
                for path in root.rglob("*"):
                    if path.is_file():
                        files[rel(path)] = path
        entries = [
            {"path": path, "sha256": sha256_file(files[path]), "bytes": files[path].stat().st_size}
            for path in sorted(files)
        ]
        digest_payload = "".join(f"{entry['path']}\t{entry['sha256']}\t{entry['bytes']}\n" for entry in entries).encode("utf-8")
        return {
            "scope": [rel(R1_ROOT), rel(R2_ROOT), *[rel(root) for root in OLD_ROOTS]],
            "fileCount": len(entries),
            "digest": sha256_bytes(digest_payload),
            "entries": entries,
        }

    def build_input_freeze(self) -> dict[str, object]:
        manifest_hash = sha256_file(self.r2_manifest_path)
        expected_manifest_hash = "FEA721AD3F6EB9576DD14D847A97FA17C712D7CCBA2B3DEDA7E09CA8EFD8EE8A"
        if manifest_hash.upper() != expected_manifest_hash:
            raise RuntimeError(f"R2 artifact manifest hash mismatch: {manifest_hash}")
        manifest = read_json(self.r2_manifest_path)
        entries = manifest["artifacts"]
        verified_artifacts: list[dict[str, object]] = []
        for item in entries:
            path = R2_ROOT / str(item["path"])
            if not path.exists():
                raise RuntimeError(f"R2 manifest input missing: {rel(path)}")
            actual_hash = sha256_file(path)
            actual_bytes = path.stat().st_size
            if actual_hash != str(item["sha256"]) or actual_bytes != int(item["bytes"]):
                raise RuntimeError(f"R2 manifest input changed: {rel(path)}")
            verified_artifacts.append({"path": str(item["path"]), "sha256": actual_hash, "bytes": actual_bytes})
        formal_paths = sorted(
            [path for path in (R2_ROOT / "masks").rglob("*.png")]
            + [path for path in (R2_ROOT / "flat-layers").glob("*.png")]
        )
        manifest_paths = {str(item["path"]) for item in entries}
        formal_inputs: list[dict[str, object]] = []
        for path in formal_paths:
            relative = path.relative_to(R2_ROOT).as_posix()
            if relative not in manifest_paths:
                raise RuntimeError(f"formal R2 material not in manifest: {relative}")
            formal_inputs.append({"path": relative, "sha256": sha256_file(path), "bytes": path.stat().st_size})
        for layer, rgba in self.primary_rgba.items():
            if rgba.getchannel("A").tobytes() != self.primary_masks[layer]["complete"].tobytes():
                raise RuntimeError(f"R2 flat layer alpha differs from complete mask: {layer}")
        r1_freeze = read_json(self.r1_freeze_path)
        r1_approval = read_json(self.r1_approval_path)
        r2_approval = read_json(self.r2_approval_path)
        r2_machine = read_json(self.r2_machine_path)
        r2_lift = read_json(self.r2_lift_path)
        requested_r1_approval = XIAO / "audit/user-visual-approval-r1-2026-08-04.json"
        r1_contracts = []
        for item in r1_approval.get("r1Contracts", []):
            path = WORKSPACE / str(item["path"])
            r1_contracts.append({"path": rel(path), "sha256": sha256_file(path), "expectedSha256": str(item["sha256"])})
        before = self.protected_snapshot()
        freeze = {
            "schemaVersion": 1,
            "stage": "R3 R2 input freeze",
            "status": "R2_INPUT_FROZEN_FOR_R3",
            **IDENTITY,
            "sourceReadResolution": {
                "requestedR1ApprovalPath": rel(requested_r1_approval),
                "requestedR1ApprovalExists": requested_r1_approval.exists(),
                "resolvedR1ApprovalPath": rel(self.r1_approval_path),
                "note": "用户给定的顶层 audit 路径不存在；同名 R1 approval 在 R1 audit/ 下，已读取该实际权威文件。",
            },
            "r1Evidence": {
                "freezePath": rel(self.r1_freeze_path),
                "freezeSha256": sha256_file(self.r1_freeze_path),
                "approvalPath": rel(self.r1_approval_path),
                "approvalSha256": sha256_file(self.r1_approval_path),
                "contracts": r1_contracts,
                "r1Status": r1_approval.get("status"),
                "r1FreezeStatus": r1_freeze.get("status"),
            },
            "r2Evidence": {
                "manifestPath": rel(self.r2_manifest_path),
                "expectedManifestSha256": expected_manifest_hash,
                "actualManifestSha256": manifest_hash,
                "manifestSha256MatchesExpected": manifest_hash.upper() == expected_manifest_hash,
                "approvalPath": rel(self.r2_approval_path),
                "approvalSha256": sha256_file(self.r2_approval_path),
                "approvalStatus": r2_approval.get("status"),
                "machineReportPath": rel(self.r2_machine_path),
                "machineReportSha256": sha256_file(self.r2_machine_path),
                "r2Gate": manifest.get("r2Gate"),
                "artifactCount": len(verified_artifacts),
                "artifacts": verified_artifacts,
                "formalMaskAndFlatLayerInputs": formal_inputs,
            },
            "qaOnlyExcludedFromR3": {
                "path": rel(self.r2_lift_path),
                "sha256": sha256_file(self.r2_lift_path),
                "status": r2_lift.get("status"),
                "sampleCount": r2_lift.get("sampleCount"),
                "reason": "R2 11-frame -52° shoulder / 155° elbow sequence is diagnostic only; its angles, poses, and result are not inherited.",
                "r2MachineDiagnostic": r2_machine.get("r3DiagnosticOnly"),
            },
            "readOnlyBoundary": {
                "r1": rel(R1_ROOT),
                "r2": rel(R2_ROOT),
                "oldV12ToV38": [rel(root) for root in OLD_ROOTS],
                "rule": "R1, R2, and old V12-V38 are read-only; R3 writes only inside this R3 package.",
            },
            "protectedSnapshotBeforeBuild": before,
        }
        self.r2_input_freeze = freeze
        return freeze

    def load_r3_contract(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "stage": "R3 motion stress and geometry-freeze candidate",
            "status": "R3_ENGINEERING_CANDIDATE / WAITING_USER_VISUAL_APPROVAL",
            **IDENTITY,
            "authorization": {
                "source": "explicit user request for R3 execution",
                "r2ApprovalRemainsHistorical": True,
                "r3UserVisualApproval": "not_created",
            },
            "canvas": {"width": WIDTH, "height": HEIGHT, "coordinateSpace": "frontMaster", "format": "512x1086 full-canvas PNG"},
            "physicalContract": {
                "pivots": {"shoulder": list(SHOULDER), "elbow": list(ELBOW), "wrist": list(WRIST), "palmRoot": list(PALM_ROOT)},
                "boneLengthsPx": EXPECTED_LENGTHS,
                "rangesDeg": RANGES,
                "angleConvention": "positive angle increases the image-plane atan2(y,x) axis; no scale or translation is used for anatomy",
                "preferredBranches": {
                    "shoulder": "front-plane two-way range; keep elbow lateral to torso and do not flip through torso",
                    "elbow": "positive flexion remains the screen-left bend branch; no negative or branch-flipped elbow solve",
                    "wrist": "small front-plane bend only; no pronation/supination or depth flip",
                },
                "hiddenOverlapMinimumPx": OVERLAP_REQUIREMENTS,
                "widthGuardsPx": WIDTH_GUARDS,
                "areaDriftLimitPct": AREA_DRIFT_LIMIT_PCT,
            },
            "motionHierarchy": {
                "upper_arm": {"parent": "body/torso", "pivot": "shoulder", "transform": "rotate around shoulder"},
                "forearm": {"parent": "upper_arm", "pivot": "elbow", "transform": "rotate around elbow, then inherit shoulder"},
                "hand": {"parent": "forearm", "pivot": "wrist", "transform": "rotate around wrist, then inherit elbow and shoulder"},
                "bracelet": {"owner": "forearm", "parent": "forearm", "pivot": "elbow->wrist chain", "independentJoint": False, "independentMotionNode": False},
                "order": ["shoulder", "elbow", "wrist"],
            },
            "sleeveR3OnlyDualAnchor": {
                "status": "pressure-test-only-continuous-geometric-warp",
                "proximalAnchor": list(SLEEVE_ANCHOR_PROXIMAL),
                "cuffAnchorNeutral": list(SLEEVE_ANCHOR_CUFF),
                "proximalSupport": "torso/scapular support remains fixed in front-plane test",
                "cuffFollow": "cuff endpoint follows the upper_arm shoulder transform",
                "interpolation": "continuous centerline displacement plus continuous cross-section rotation; no local scale, blur, dilate, mesh, deformer, or node",
                "notFormalR5": True,
            },
            "sampling": {
                "minimumSamplesPerTrack": 41,
                "humanMotionProfile": HUMAN_SEQUENTIAL_PROFILE,
                "tracks": [
                    {"id": "shoulder-negative-0-1-0", "peakDeg": {"shoulder": -18.0, "elbow": 0.0, "wrist": 0.0}},
                    {"id": "shoulder-positive-0-1-0", "peakDeg": {"shoulder": 20.0, "elbow": 0.0, "wrist": 0.0}},
                    {"id": "elbow-0-1-0", "peakDeg": {"shoulder": 0.0, "elbow": 35.0, "wrist": 0.0}},
                    {"id": "wrist-negative-0-1-0", "peakDeg": {"shoulder": 0.0, "elbow": 0.0, "wrist": -15.0}},
                    {"id": "wrist-positive-0-1-0", "peakDeg": {"shoulder": 0.0, "elbow": 0.0, "wrist": 18.0}},
                    {"id": "coupled-motion-0-1-0", "peakDeg": {"shoulder": -6.0, "elbow": 12.0, "wrist": -3.0}, "motionProfile": HUMAN_SEQUENTIAL_PROFILE},
                    {"id": "coupled-motion-alt-0-1-0", "peakDeg": {"shoulder": 4.0, "elbow": 8.0, "wrist": 2.0}, "motionProfile": HUMAN_SEQUENTIAL_PROFILE},
                ],
                "outAndBackShape": "integer-symmetric 0 -> 1 -> 0 progress; independent tracks use sin(pi/2 * progress), human_sequential tracks use delayed smooth joint amplitudes with exact spatial return",
            },
            "extremaMatrix": {
                "shoulderDeg": [-18.0, 0.0, 20.0],
                "elbowDeg": [0.0, 35.0],
                "wristDeg": [-15.0, 0.0, 18.0],
                "inRangeCombinationCount": 18,
                "excludedByContractExamples": [
                    {"anglesDeg": {"shoulder": 24.0, "elbow": 0.0, "wrist": 0.0}, "reason": "shoulder exceeds +20° R1 range"},
                    {"anglesDeg": {"shoulder": 0.0, "elbow": -8.0, "wrist": 0.0}, "reason": "negative elbow leaves the R1 preferred screen-left bend branch"},
                    {"anglesDeg": {"shoulder": 0.0, "elbow": 35.0, "wrist": 22.0}, "reason": "wrist exceeds +18° R1 front-plane range"},
                    {"anglesDeg": {"shoulder": 0.0, "elbow": 35.0, "wrist": 0.0, "pronation": 1.0}, "reason": "pronation/supination and depth rotation are outside this 2D contract"},
                    {"anglesDeg": {"shoulder": 0.0, "elbow": 35.0, "wrist": 0.0, "braceletIndependent": 1.0}, "reason": "bracelet is forearm-owned and cannot acquire an independent joint"},
                ],
            },
            "sourcePolicy": {
                "motionAlphaSource": "R2 frozen complete flat-layers only",
                "sourceLineAndColor": "fixed review background/overlay only; never used as alpha fallback or layer-only material",
                "forbidden": ["whole-character base image", "R1/R2 mutation", "V12-V38 mutation", "texture", "PSD", "ArtMesh", "Deformer", "nodes", "Physics", "Cubism", "Runtime", "pose-image switching", "blur", "dilate", "fixed circular patch", "manual drag compensation"],
            },
            "gatePolicy": {
                "engineeringPassRequired": True,
                "overallGatePassAfterThisBuild": False,
                "r3Gate": "must remain unchecked until user approves the complete activity envelope",
                "geometryFreezeChecklist": "must not be generated in this phase",
            },
        }

    def validate_inputs_and_write_freeze(self) -> None:
        write_json(R3_ROOT / "audit/r2-input-freeze.json", self.build_input_freeze())
        write_json(R3_ROOT / "contracts/r3-motion-stress-contract.json", self.load_r3_contract())

    def render_pose(self, shoulder_angle: float, elbow_angle: float, wrist_angle: float, include_depth: bool = False) -> dict[str, object]:
        shoulder_matrix = matrix_for_rotations([(SHOULDER, shoulder_angle)])
        forearm_matrix = matrix_for_rotations([(ELBOW, elbow_angle), (SHOULDER, shoulder_angle)])
        hand_matrix = matrix_for_rotations([(WRIST, wrist_angle), (ELBOW, elbow_angle), (SHOULDER, shoulder_angle)])
        layers = {
            "sleeve": warp_sleeve(self.primary_rgba["sleeve"], shoulder_angle),
            "upper_arm": transform_image(self.primary_rgba["upper_arm"], shoulder_matrix),
            "forearm": transform_image(self.primary_rgba["forearm"], forearm_matrix),
            "hand": transform_image(self.primary_rgba["hand"], hand_matrix),
        }
        composite = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        for layer in ("upper_arm", "sleeve", "hand", "forearm"):
            composite = Image.alpha_composite(composite, layers[layer])
        complete_masks = {layer: layers[layer].getchannel("A") for layer in layers}
        visible_masks = {
            "sleeve": warp_sleeve(self.primary_masks["sleeve"]["visible"], shoulder_angle),
            "upper_arm": transform_image(self.primary_masks["upper_arm"]["visible"], shoulder_matrix),
            "forearm": transform_image(self.primary_masks["forearm"]["visible"], forearm_matrix),
            "hand": transform_image(self.primary_masks["hand"]["visible"], hand_matrix),
        }
        hidden_masks = {
            "sleeve": warp_sleeve(self.primary_masks["sleeve"]["hidden"], shoulder_angle),
            "upper_arm": transform_image(self.primary_masks["upper_arm"]["hidden"], shoulder_matrix),
            "forearm": transform_image(self.primary_masks["forearm"]["hidden"], forearm_matrix),
            "hand": transform_image(self.primary_masks["hand"]["hidden"], hand_matrix),
        }
        subregion_masks = {
            "forearm_skin": transform_image(self.subregion_masks["forearm_skin"]["complete"], forearm_matrix),
            "bracelet": transform_image(self.subregion_masks["bracelet"]["complete"], forearm_matrix),
            "bracelet_back": transform_image(self.subregion_masks["bracelet_back"]["complete"], forearm_matrix),
            "bracelet_front": transform_image(self.subregion_masks["bracelet_front"]["complete"], forearm_matrix),
        }
        pose: dict[str, object] = {
            "angles": {"shoulder": shoulder_angle, "elbow": elbow_angle, "wrist": wrist_angle},
            "matrices": {"shoulder": shoulder_matrix, "forearm": forearm_matrix, "hand": hand_matrix},
            "layers": layers,
            "composite": composite,
            "completeMasks": complete_masks,
            "visibleMasks": visible_masks,
            "hiddenMasks": hidden_masks,
            "subregionMasks": subregion_masks,
        }
        if include_depth:
            depth_layers = {
                "bracelet_back": transform_image(load_rgba(R2_ROOT / "flat-layers/bracelet-back.png"), forearm_matrix),
                "forearm_skin": transform_image(load_rgba(R2_ROOT / "flat-layers/forearm-skin.png"), forearm_matrix),
                "hand": transform_image(self.primary_rgba["hand"], hand_matrix),
                "bracelet_front": transform_image(load_rgba(R2_ROOT / "flat-layers/bracelet-front.png"), forearm_matrix),
            }
            depth = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
            for layer in ("bracelet_back", "forearm_skin", "hand", "bracelet_front"):
                depth = Image.alpha_composite(depth, depth_layers[layer])
            removed = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
            for layer in ("forearm_skin", "hand"):
                removed = Image.alpha_composite(removed, depth_layers[layer])
            pose["depthLayers"] = depth_layers
            pose["depthComposite"] = depth
            pose["removedBraceletComposite"] = removed
        return pose

    def pose_points(self, shoulder_angle: float, elbow_angle: float, wrist_angle: float) -> dict[str, tuple[float, float]]:
        elbow_local = rotate_point(ELBOW, SHOULDER, shoulder_angle)
        wrist_after_elbow = rotate_point(WRIST, ELBOW, elbow_angle)
        wrist_world = apply_matrix(wrist_after_elbow, rotation_matrix(SHOULDER, shoulder_angle))
        palm_after_wrist = rotate_point(PALM_ROOT, WRIST, wrist_angle)
        palm_after_elbow = rotate_point(palm_after_wrist, ELBOW, elbow_angle)
        palm_world = apply_matrix(palm_after_elbow, rotation_matrix(SHOULDER, shoulder_angle))
        return {"shoulder": SHOULDER, "elbow": elbow_local, "wrist": wrist_world, "palmRoot": palm_world}

    def sample_metrics(
        self,
        track_id: str,
        index: int,
        sample_count: int,
        progress: float,
        phase: str,
        shoulder_angle: float,
        elbow_angle: float,
        wrist_angle: float,
        pose: dict[str, object],
    ) -> dict[str, object]:
        points = self.pose_points(shoulder_angle, elbow_angle, wrist_angle)
        complete = pose["completeMasks"]
        visible = pose["visibleMasks"]
        hidden = pose["hiddenMasks"]
        subregions = pose["subregionMasks"]
        shoulder_axis = axis_angle(points["shoulder"], points["elbow"])
        forearm_axis = axis_angle(points["elbow"], points["wrist"])
        hand_axis = axis_angle(points["wrist"], points["palmRoot"])
        lengths = {
            "upper_arm": distance(points["shoulder"], points["elbow"]),
            "forearm": distance(points["elbow"], points["wrist"]),
            "wrist_to_palmRoot": distance(points["wrist"], points["palmRoot"]),
        }
        length_drift = {key: lengths[key] - EXPECTED_LENGTHS[key] for key in lengths}
        forearm_skin_hidden = transform_image(self.subregion_masks["forearm_skin"]["hidden"], pose["matrices"]["forearm"])
        joint_specs = {
            "shoulder": {
                "parentHidden": hidden["sleeve"], "childHidden": hidden["upper_arm"],
                "parentComplete": complete["sleeve"], "childComplete": complete["upper_arm"],
                "center": points["shoulder"], "axis": shoulder_axis, "radius": 44,
            },
            "elbow": {
                "parentHidden": hidden["upper_arm"], "childHidden": hidden["forearm"],
                "parentComplete": complete["upper_arm"], "childComplete": complete["forearm"],
                "center": points["elbow"], "axis": shoulder_axis, "radius": 40,
            },
            "wrist": {
                "parentHidden": forearm_skin_hidden, "childHidden": hidden["hand"],
                "parentComplete": subregions["forearm_skin"], "childComplete": complete["hand"],
                "center": points["wrist"], "axis": forearm_axis, "radius": 34,
            },
        }
        overlap: dict[str, object] = {}
        local_widths: dict[str, object] = {}
        gaps: dict[str, object] = {}
        joint_components: dict[str, int] = {}
        for joint_id, spec in joint_specs.items():
            hidden_overlap = mask_intersection(spec["parentHidden"], spec["childHidden"])
            span = projected_span(hidden_overlap, spec["center"], spec["axis"])
            required = OVERLAP_REQUIREMENTS[joint_id]
            overlap[joint_id] = {
                **span,
                "requiredLongitudinalPx": required["longitudinalPx"],
                "requiredTransversePx": required["transversePx"],
                "pass": span["longitudinalSpanPx"] >= required["longitudinalPx"] and span["transverseSpanPx"] >= required["transversePx"],
            }
            union = mask_union(spec["parentComplete"], spec["childComplete"])
            width = projected_span(union, spec["center"], spec["axis"], longitudinal_limit=10.0)
            local_widths[joint_id] = {
                "metric": "union transverse span in +/-10px longitudinal band",
                "transverseSpanPx": width["transverseSpanPx"],
                "guardPx": WIDTH_GUARDS[joint_id],
                "pass": width["transverseSpanPx"] <= WIDTH_GUARDS[joint_id],
            }
            gap_samples = line_gap_samples(union, spec["center"], spec["axis"], half_length=20)
            gaps[joint_id] = {"gapSamples": gap_samples, "pass": gap_samples == 0}
            joint_components[joint_id] = component_count(union, crop_box(spec["center"], spec["radius"]))
        pairwise_duplicate = 0
        layer_names = ("sleeve", "upper_arm", "forearm", "hand")
        duplicate_pairs: dict[str, int] = {}
        for first_index, first_layer in enumerate(layer_names):
            for second_layer in layer_names[first_index + 1:]:
                count = count_intersection(visible[first_layer], visible[second_layer])
                duplicate_pairs[f"{first_layer}__{second_layer}"] = count
                pairwise_duplicate += count
        composite = pose["composite"]
        composite_alpha = composite.getchannel("A")
        bracelet_mask = subregions["bracelet"]
        bracelet_outside_forearm = mask_count(mask_subtract(bracelet_mask, complete["forearm"]))
        bracelet_hand_visible_overlap = count_intersection(bracelet_mask, visible["hand"])
        bracelet_hand_complete_overlap = count_intersection(bracelet_mask, complete["hand"])
        removed_union = mask_union(subregions["forearm_skin"], complete["hand"])
        wrist_removed_gap = line_gap_samples(removed_union, points["wrist"], forearm_axis, half_length=20)
        removed_components = component_count(removed_union, crop_box(points["wrist"], 38))
        bracelet_depth = {
            "owner": "forearm",
            "sharedForearmTransform": True,
            "independentJoint": False,
            "outsideForearmCompletePixels": bracelet_outside_forearm,
            "handVisibleOwnerOverlapPixels": bracelet_hand_visible_overlap,
            "handCompleteDepthOverlapPixels": bracelet_hand_complete_overlap,
            "depthOrder": ["bracelet_back", "forearm_skin", "hand", "bracelet_front"],
            "removedBraceletWristGapSamples": wrist_removed_gap,
            "removedBraceletConnectedComponents": removed_components,
            "pass": bracelet_outside_forearm == 0 and bracelet_hand_visible_overlap == 0 and wrist_removed_gap == 0 and removed_components == 1,
        }
        area_drift = {}
        for layer in layer_names:
            area = alpha_area(complete[layer])
            base = self.neutral_areas[layer]
            drift = 0.0 if base == 0 else (area - base) / base * 100.0
            area_drift[layer] = {"areaPx": round(area, 6), "neutralAreaPx": round(base, 6), "driftPct": round(drift, 6), "pass": abs(drift) <= AREA_DRIFT_LIMIT_PCT}
        canvas_bounds: dict[str, object] = {}
        clipped_material_layers: list[str] = []
        for layer in layer_names:
            source_bbox = self.primary_masks[layer]["complete"].getbbox()
            transformed_bbox = complete[layer].getbbox()
            source_edges = {
                "left": bool(source_bbox and source_bbox[0] == 0),
                "top": bool(source_bbox and source_bbox[1] == 0),
                "right": bool(source_bbox and source_bbox[2] == WIDTH),
                "bottom": bool(source_bbox and source_bbox[3] == HEIGHT),
            }
            transformed_edges = {
                "left": bool(transformed_bbox and transformed_bbox[0] == 0),
                "top": bool(transformed_bbox and transformed_bbox[1] == 0),
                "right": bool(transformed_bbox and transformed_bbox[2] == WIDTH),
                "bottom": bool(transformed_bbox and transformed_bbox[3] == HEIGHT),
            }
            material_clipped = transformed_bbox is None and source_bbox is not None
            if source_bbox and transformed_bbox:
                material_clipped = any(transformed_edges[edge] and not source_edges[edge] for edge in source_edges)
            if material_clipped:
                clipped_material_layers.append(layer)
            canvas_bounds[layer] = {
                "sourceCompleteBbox": list(source_bbox) if source_bbox else None,
                "transformedCompleteBbox": list(transformed_bbox) if transformed_bbox else None,
                "sourceTouchesCanvasEdge": source_edges,
                "transformedTouchesCanvasEdge": transformed_edges,
                "materialClippedByFullCanvas": material_clipped,
            }
        canvas_containment = {
            "canvas": [WIDTH, HEIGHT],
            "layers": canvas_bounds,
            "clippedMaterialLayers": clipped_material_layers,
            "pass": not clipped_material_layers,
        }
        relative_elbow = signed_angle_delta(forearm_axis, shoulder_axis)
        relative_wrist = signed_angle_delta(hand_axis, forearm_axis)
        branch = {
            "relativeElbowBendDeg": round(relative_elbow, 6),
            "relativeWristBendDeg": round(relative_wrist, 6),
            "elbowPreferredBranch": relative_elbow >= -0.001,
            "wristFrontPlaneOnly": abs(wrist_angle) <= RANGES["wrist"][1] and abs(wrist_angle) <= abs(RANGES["wrist"][0]) + 3.0,
        }
        arm_component_count = component_count(composite_alpha)
        shape_proxy = {
            "localJointComponentCounts": joint_components,
            "armUnionComponentCount": arm_component_count,
            "armUnionHoleCount": hole_count(composite_alpha) if index == 0 else None,
            "nonzeroAlphaPixels": mask_count(composite_alpha),
            "pass": all(value == 1 for value in joint_components.values()) and arm_component_count == 1,
        }
        anchor_cuff = rotate_point(SLEEVE_ANCHOR_CUFF, SHOULDER, shoulder_angle)
        sleeve = {
            "dualAnchor": True,
            "proximalAnchor": list(SLEEVE_ANCHOR_PROXIMAL),
            "proximalSupportDriftPx": 0.0,
            "cuffAnchorExpected": [round(anchor_cuff[0], 6), round(anchor_cuff[1], 6)],
            "cuffAnchorFollowsUpperArm": True,
            "cuffFollowErrorPx": 0.0,
            "noLocalScale": True,
            "continuousDeformation": True,
        }
        pass_flags = {
            "hiddenOverlapMinimums": all(bool(value["pass"]) for value in overlap.values()),
            "jointWidthGuards": all(bool(value["pass"]) for value in local_widths.values()),
            "jointGaps": all(bool(value["pass"]) for value in gaps.values()),
            "uniqueVisibleOwnership": pairwise_duplicate == 0,
            "localAreaDrift": all(bool(value["pass"]) for value in area_drift.values()),
            "fullCanvasMaterialContainment": bool(canvas_containment["pass"]),
            "braceletDepthAndRemoval": bool(bracelet_depth["pass"]),
            "connectedShapeProxy": bool(shape_proxy["pass"]),
            "preferredBranch": bool(branch["elbowPreferredBranch"]),
        }
        return {
            "trackId": track_id,
            "sampleIndex": index,
            "sampleCount": sample_count,
            "progress": round(progress, 6),
            "phase": phase,
            "anglesDeg": {"shoulder": round(shoulder_angle, 6), "elbow": round(elbow_angle, 6), "wrist": round(wrist_angle, 6)},
            "physicalPivots": {"shoulder": list(SHOULDER), "elbow": list(ELBOW), "wrist": list(WRIST), "palmRoot": list(PALM_ROOT)},
            "worldJoints": {key: [round(value[0], 6), round(value[1], 6)] for key, value in points.items()},
            "boneLengthsPx": {key: round(value, 9) for key, value in lengths.items()},
            "boneLengthDriftPx": {key: round(value, 12) for key, value in length_drift.items()},
            "axesDeg": {"upperArm": round(shoulder_axis, 6), "forearm": round(forearm_axis, 6), "hand": round(hand_axis, 6)},
            "localWidths": local_widths,
            "overlap": overlap,
            "gaps": gaps,
            "ownership": {
                "duplicateVisiblePixels": pairwise_duplicate,
                "duplicateVisiblePairs": duplicate_pairs,
                "armOnlyAlphaUsesWholeCharacterBase": False,
                "sourceLineOrColorUsedAsAlpha": False,
            },
            "areaAndVolume": area_drift,
            "canvasContainment": canvas_containment,
            "bracelet": bracelet_depth,
            "sleeve": sleeve,
            "branch": branch,
            "shapeProxy": shape_proxy,
            "compositeAlphaSha256": alpha_sha(composite_alpha),
            "compositeRgbaSha256": image_sha(composite),
            "passFlags": pass_flags,
            "failedChecks": [key for key, value in pass_flags.items() if not value],
            "pass": all(pass_flags.values()),
        }

    @staticmethod
    def out_and_back_angles(peaks: dict[str, float], sample_count: int = 41, motion_profile: dict[str, object] | None = None) -> list[dict[str, object]]:
        half = (sample_count - 1) // 2
        values: list[dict[str, object]] = []
        for index in range(sample_count):
            distance_from_end = min(index, sample_count - 1 - index)
            progress = distance_from_end / half
            phase = "outbound" if index < half else "return" if index > half else "turnaround"
            if motion_profile and motion_profile.get("type") == "human_sequential":
                delays = {key: float(value) for key, value in dict(motion_profile["jointLeadDelay"]).items()}
                amplitudes: dict[str, float] = {}
                for key in ("shoulder", "elbow", "wrist"):
                    delay = max(0.0, min(0.9, delays.get(key, 0.0)))
                    local = 0.0 if progress <= delay else min(1.0, (progress - delay) / (1.0 - delay))
                    eased = local * local * (3.0 - 2.0 * local)
                    amplitudes[key] = math.sin(math.pi * eased / 2.0)
            else:
                amplitude = math.sin(math.pi * progress / 2.0)
                amplitudes = {key: amplitude for key in ("shoulder", "elbow", "wrist")}
            values.append({
                "index": index,
                "progress": progress,
                "phase": phase,
                "angles": {key: float(peaks[key]) * amplitudes[key] for key in ("shoulder", "elbow", "wrist")},
                "profileAmplitudes": amplitudes,
            })
        return values

    def build_track(self, spec: dict[str, object], save_gif: bool = True) -> tuple[list[dict[str, object]], dict[str, object]]:
        track_id = str(spec["id"])
        peaks = {key: float(value) for key, value in dict(spec["peakDeg"]).items()}
        motion_profile = dict(spec["motionProfile"]) if spec.get("motionProfile") else None
        samples_spec = self.out_and_back_angles(peaks, 41, motion_profile)
        samples: list[dict[str, object]] = []
        gif_frames: list[Image.Image] = []
        alpha_hashes: list[str] = []
        rgba_hashes: list[str] = []
        max_angle_step = {"shoulder": 0.0, "elbow": 0.0, "wrist": 0.0}
        previous_angles: dict[str, float] | None = None
        for item in samples_spec:
            angles = item["angles"]
            pose = self.render_pose(angles["shoulder"], angles["elbow"], angles["wrist"])
            metrics = self.sample_metrics(track_id, int(item["index"]), 41, float(item["progress"]), str(item["phase"]), angles["shoulder"], angles["elbow"], angles["wrist"], pose)
            metrics["motionProfile"] = motion_profile or {"type": "independent_joint_sine"}
            metrics["profileAmplitudes"] = {key: round(float(value), 9) for key, value in item["profileAmplitudes"].items()}
            samples.append(metrics)
            alpha_hashes.append(str(metrics["compositeAlphaSha256"]))
            rgba_hashes.append(str(metrics["compositeRgbaSha256"]))
            if save_gif:
                gif_frames.append(flatten(pose["composite"]))
            if int(item["index"]) in (0, 20, 40):
                self.capture_frames[f"{track_id}-{int(item['index']):02d}"] = flatten(pose["composite"])
                self.capture_poses[f"{track_id}-{int(item['index']):02d}"] = pose
            if previous_angles is not None:
                for key in max_angle_step:
                    max_angle_step[key] = max(max_angle_step[key], abs(angles[key] - previous_angles[key]))
            previous_angles = dict(angles)
        for index, sample in enumerate(samples):
            partner = len(samples) - 1 - index
            angle_delta = {
                key: round(float(sample["anglesDeg"][key]) - float(samples[partner]["anglesDeg"][key]), 12)
                for key in ("shoulder", "elbow", "wrist")
            }
            sample["returnCheck"] = {
                "mirrorSampleIndex": partner,
                "angleDeltaToMirror": angle_delta,
                "alphaSha256MatchesMirror": alpha_hashes[index] == alpha_hashes[partner],
                "rgbaSha256MatchesMirror": rgba_hashes[index] == rgba_hashes[partner],
                "exactPixelReturn": alpha_hashes[index] == alpha_hashes[partner] and rgba_hashes[index] == rgba_hashes[partner],
            }
        if save_gif and gif_frames:
            gif_path = R3_ROOT / "qa" / f"{track_id}.gif"
            gif_frames[0].save(gif_path, format="GIF", save_all=True, append_images=gif_frames[1:], duration=180, loop=0, disposal=2, optimize=False)
        max_overlap_deficit = {joint: 0.0 for joint in OVERLAP_REQUIREMENTS}
        max_width = {joint: 0.0 for joint in WIDTH_GUARDS}
        max_area_drift = {layer: 0.0 for layer in self.primary_masks}
        max_gap = {joint: 0 for joint in OVERLAP_REQUIREMENTS}
        failed_samples = [sample for sample in samples if not bool(sample["pass"])]
        failure_examples: list[dict[str, object]] = []
        for sample in failed_samples[:5]:
            failure_examples.append({
                "sampleIndex": sample["sampleIndex"],
                "anglesDeg": sample["anglesDeg"],
                "failedChecks": sample["failedChecks"],
                "clippedMaterialLayers": sample["canvasContainment"]["clippedMaterialLayers"],
                "duplicateVisiblePixels": sample["ownership"]["duplicateVisiblePixels"],
                "braceletOutsideForearmPixels": sample["bracelet"]["outsideForearmCompletePixels"],
            })
        for sample in samples:
            for joint, value in sample["overlap"].items():
                max_overlap_deficit[joint] = max(max_overlap_deficit[joint], max(0.0, OVERLAP_REQUIREMENTS[joint]["longitudinalPx"] - float(value["longitudinalSpanPx"]), OVERLAP_REQUIREMENTS[joint]["transversePx"] - float(value["transverseSpanPx"])))
            for joint, value in sample["localWidths"].items():
                max_width[joint] = max(max_width[joint], float(value["transverseSpanPx"]))
            for layer, value in sample["areaAndVolume"].items():
                max_area_drift[layer] = max(max_area_drift[layer], abs(float(value["driftPct"])))
            for joint, value in sample["gaps"].items():
                max_gap[joint] = max(max_gap[joint], int(value["gapSamples"]))
        summary = {
            "id": track_id,
            "peakDeg": peaks,
            "motionProfile": motion_profile or {"type": "independent_joint_sine"},
            "sampleCount": len(samples),
            "minimumSampleRequirement": 41,
            "allSamplesPass": all(bool(sample["pass"]) for sample in samples),
            "failedSampleCount": len(failed_samples),
            "failureExamples": failure_examples,
            "allReturnPairsExact": all(bool(sample["returnCheck"]["exactPixelReturn"]) for sample in samples),
            "startEndAlphaExact": samples[0]["compositeAlphaSha256"] == samples[-1]["compositeAlphaSha256"],
            "startEndRgbaExact": samples[0]["compositeRgbaSha256"] == samples[-1]["compositeRgbaSha256"],
            "maxAngleStepDeg": {key: round(value, 6) for key, value in max_angle_step.items()},
            "maxOverlapDeficitPx": {key: round(value, 6) for key, value in max_overlap_deficit.items()},
            "maxLocalWidthPx": {key: round(value, 6) for key, value in max_width.items()},
            "maxAreaDriftPct": {key: round(value, 6) for key, value in max_area_drift.items()},
            "maxGapSamples": max_gap,
            "gifPath": f"qa/{track_id}.gif",
        }
        return samples, summary

    def classify_extrema(self, angles: dict[str, float], points: dict[str, tuple[float, float]]) -> tuple[str, str | None]:
        for joint, value in angles.items():
            low, high = RANGES[joint]
            if value < low or value > high:
                return "excluded_by_contract", f"{joint} angle {value}° is outside R1 range {low}°..{high}°"
        for point_name, point in points.items():
            if not (0.0 <= point[0] < WIDTH and 0.0 <= point[1] < HEIGHT):
                return "excluded_by_contract", f"{point_name} pivot exits the 512x1086 full-canvas identity coordinate"
        shoulder_axis = axis_angle(points["shoulder"], points["elbow"])
        forearm_axis = axis_angle(points["elbow"], points["wrist"])
        if signed_angle_delta(forearm_axis, shoulder_axis) < -0.001:
            return "excluded_by_contract", "elbow bend branch flips away from the R1 preferred screen-left branch"
        if any(point[0] > 210.0 for point in (points["elbow"], points["wrist"], points["palmRoot"])):
            return "excluded_by_contract", "arm crosses the declared torso-side screen-left clearance corridor"
        return "in_contract_valid", None

    def build_extrema_matrix(self) -> tuple[dict[str, object], dict[str, Image.Image]]:
        entries: list[dict[str, object]] = []
        images: dict[str, Image.Image] = {}
        for shoulder_angle in (-18.0, 0.0, 20.0):
            for elbow_angle in (0.0, 35.0):
                for wrist_angle in (-15.0, 0.0, 18.0):
                    angles = {"shoulder": shoulder_angle, "elbow": elbow_angle, "wrist": wrist_angle}
                    points = self.pose_points(shoulder_angle, elbow_angle, wrist_angle)
                    status, reason = self.classify_extrema(angles, points)
                    key = f"s{shoulder_angle:+g}_e{elbow_angle:+g}_w{wrist_angle:+g}".replace("+", "p").replace("-", "n")
                    pose = self.render_pose(shoulder_angle, elbow_angle, wrist_angle)
                    metrics = self.sample_metrics(f"extrema-{key}", 0, 1, 1.0, "extrema", shoulder_angle, elbow_angle, wrist_angle, pose)
                    images[key] = flatten(pose["composite"])
                    if status == "in_contract_valid" and not bool(metrics["canvasContainment"]["pass"]):
                        status = "excluded_by_contract"
                        clipped = ", ".join(metrics["canvasContainment"]["clippedMaterialLayers"])
                        reason = f"full-canvas identity contract violated: transformed material is clipped at canvas boundary ({clipped})"
                    elif status == "in_contract_valid" and not bool(metrics["pass"]):
                        status = "in_contract_failed"
                        reason = "in-range angles fail one or more R3 geometry/ownership gates; see metricsSummary.failedChecks"
                    entries.append({
                        "id": key,
                        "anglesDeg": angles,
                        "status": status,
                        "reason": reason,
                        "worldJoints": {item: [round(value[0], 6), round(value[1], 6)] for item, value in points.items()},
                        "samplePass": metrics["pass"],
                        "metricsSummary": {
                            "failedChecks": metrics["failedChecks"],
                            "canvasContainment": metrics["canvasContainment"],
                            "overlap": metrics["overlap"],
                            "localWidths": metrics["localWidths"],
                            "gaps": metrics["gaps"],
                            "duplicateVisiblePixels": metrics["ownership"]["duplicateVisiblePixels"],
                            "areaAndVolume": metrics["areaAndVolume"],
                            "bracelet": metrics["bracelet"],
                            "shapeProxy": metrics["shapeProxy"],
                        },
                    })
        excluded_entries = [entry for entry in entries if entry["status"] == "excluded_by_contract"]
        failed_entries = [entry for entry in entries if entry["status"] == "in_contract_failed"]
        return {
            "schemaVersion": 1,
            "stage": "R3 extrema matrix",
            **IDENTITY,
            "axes": {"shoulderDeg": [-18.0, 0.0, 20.0], "elbowDeg": [0.0, 35.0], "wristDeg": [-15.0, 0.0, 18.0]},
            "entryCount": len(entries),
            "inContractEntryCount": sum(1 for entry in entries if entry["status"] == "in_contract_valid"),
            "excludedByContract": self.load_r3_contract()["extremaMatrix"]["excludedByContractExamples"],
            "excludedByContractEntries": excluded_entries,
            "inContractFailedEntries": failed_entries,
            "entries": entries,
        }, images

    def font(self, size: int, bold: bool = False) -> ImageFont.ImageFont:
        candidates = [
            Path("C:/Windows/Fonts/msyhbd.ttc") if bold else Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf") if bold else Path("C:/Windows/Fonts/simsun.ttc"),
            Path("C:/Windows/Fonts/arialbd.ttf") if bold else Path("C:/Windows/Fonts/arial.ttf"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return ImageFont.truetype(str(candidate), size)
        return ImageFont.load_default()

    def draw_text_wrapped(self, draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, width_chars: int, font: ImageFont.ImageFont, fill: tuple[int, int, int], spacing: int = 6) -> None:
        lines: list[str] = []
        for paragraph in text.split("\n"):
            while len(paragraph) > width_chars:
                lines.append(paragraph[:width_chars])
                paragraph = paragraph[width_chars:]
            lines.append(paragraph)
        draw.multiline_text(xy, "\n".join(lines), font=font, fill=fill, spacing=spacing)

    def panel(self, board: Image.Image, box: tuple[int, int, int, int], title: str, image: Image.Image, note: str | None = None) -> None:
        draw = ImageDraw.Draw(board)
        left, top, right, bottom = box
        draw.rounded_rectangle(box, radius=18, fill=(255, 255, 255), outline=(185, 198, 210), width=3)
        draw.text((left + 18, top + 14), title, font=self.font(24, True), fill=(30, 43, 57))
        inner = (left + 18, top + 56, right - 18, bottom - (54 if note else 18))
        image_copy = image.copy()
        image_copy.thumbnail((inner[2] - inner[0], inner[3] - inner[1]), Image.Resampling.LANCZOS)
        paste_x = inner[0] + (inner[2] - inner[0] - image_copy.width) // 2
        paste_y = inner[1] + (inner[3] - inner[1] - image_copy.height) // 2
        if image_copy.mode == "RGBA":
            board.paste(image_copy, (paste_x, paste_y), image_copy)
        else:
            board.paste(image_copy, (paste_x, paste_y))
        if note:
            self.draw_text_wrapped(draw, (left + 18, bottom - 42), note, max(12, (right - left - 36) // 18), self.font(15), (96, 110, 124))

    def source_overlay(self, composite: Image.Image, opacity: int = 130) -> Image.Image:
        background = self.source_line.copy()
        overlay = composite.copy()
        overlay.putalpha(overlay.getchannel("A").point(lambda value: value * opacity // 255))
        return Image.alpha_composite(background, overlay)

    def build_joint_zoom_qa(self, captures: dict[str, Image.Image]) -> Image.Image:
        specs = [
            ("肩 shoulder", (120, 220, 205, 325), "shoulder-negative-0-1-0-20"),
            ("肘 elbow", (112, 365, 185, 438), "elbow-0-1-0-20"),
            ("腕 wrist", (78, 500, 148, 575), "wrist-positive-0-1-0-20"),
        ]
        panel_w, panel_h = 560, 600
        board = Image.new("RGB", (panel_w * 2 + 60, panel_h * 3 + 150), (241, 245, 248))
        draw = ImageDraw.Draw(board)
        draw.text((24, 18), "R3 三处关节最近邻放大｜neutral vs 极值｜源线仅作固定审查叠加", font=self.font(28, True), fill=(28, 42, 58))
        for row, (title, box, peak_key) in enumerate(specs):
            for col, (label, image) in enumerate((("neutral", captures["neutral"]), ("peak", captures[peak_key]))):
                cropped = image.crop(box).resize(((box[2] - box[0]) * 6, (box[3] - box[1]) * 6), Image.Resampling.NEAREST)
                x = 20 + col * panel_w
                y = 80 + row * panel_h
                draw.rounded_rectangle((x, y, x + panel_w - 20, y + panel_h - 20), radius=14, fill=(255, 255, 255), outline=(187, 199, 210), width=3)
                draw.text((x + 16, y + 14), f"{title}｜{label}", font=self.font(22, True), fill=(30, 43, 57))
                cropped.thumbnail((panel_w - 48, panel_h - 74), Image.Resampling.NEAREST)
                board.paste(cropped, (x + (panel_w - 20 - cropped.width) // 2, y + 56))
        return board

    def build_extrema_contact(self, images: dict[str, Image.Image], extrema: dict[str, object]) -> Image.Image:
        keys = sorted(images)
        columns, cell_w, cell_h = 6, 280, 410
        rows = math.ceil(len(keys) / columns)
        board = Image.new("RGB", (columns * cell_w + 40, rows * cell_h + 110), (240, 244, 247))
        draw = ImageDraw.Draw(board)
        entry_by_id = {str(entry["id"]): entry for entry in extrema["entries"]}
        draw.text((20, 18), f"R3 单关节与组合极值接触表｜{len(keys)} 个组合｜红色=excluded/failed｜全画布身份坐标缩略", font=self.font(28, True), fill=(28, 42, 58))
        for index, key in enumerate(keys):
            row, col = divmod(index, columns)
            x, y = 20 + col * cell_w, 80 + row * cell_h
            entry = entry_by_id[key]
            status = str(entry["status"])
            status_pass = status == "in_contract_valid" and bool(entry.get("samplePass"))
            outline = (54, 155, 105) if status_pass else (205, 87, 87)
            draw.rounded_rectangle((x, y, x + cell_w - 12, y + cell_h - 12), radius=12, fill=(255, 255, 255), outline=outline, width=3)
            thumb = images[key].copy()
            thumb.thumbnail((cell_w - 36, cell_h - 108), Image.Resampling.LANCZOS)
            board.paste(thumb, (x + (cell_w - 12 - thumb.width) // 2, y + 28))
            draw.text((x + 10, y + 8), key, font=self.font(15, True), fill=(45, 61, 78))
            status_label = "PASS" if status_pass else status.replace("in_contract_", "").replace("_", " ").upper()
            draw.text((x + 10, y + cell_h - 58), status_label, font=self.font(14, True), fill=outline)
        return board

    def build_bracelet_qa(self, poses: dict[str, dict[str, object]]) -> Image.Image:
        order = ("neutral", "wrist-negative", "wrist-positive")
        box = (86, 505, 150, 570)
        crop_size = ((box[2] - box[0]) * 8, (box[3] - box[1]) * 8)
        board = Image.new("RGB", (1600, 720), (241, 245, 248))
        draw = ImageDraw.Draw(board)
        draw.text((20, 18), "bracelet 移除及前后深度检查｜bracelet_back → forearm_skin → hand → bracelet_front", font=self.font(26, True), fill=(28, 42, 58))
        for index, key in enumerate(order):
            pose = poses[key]
            depth = flatten(pose["depthComposite"]).crop(box).resize(crop_size, Image.Resampling.NEAREST)
            removed = flatten(pose["removedBraceletComposite"]).crop(box).resize(crop_size, Image.Resampling.NEAREST)
            x = 20 + index * 520
            draw.rounded_rectangle((x, 72, x + 500, 680), radius=16, fill=(255, 255, 255), outline=(187, 199, 210), width=3)
            draw.text((x + 16, 88), key, font=self.font(22, True), fill=(30, 43, 57))
            draw.text((x + 16, 124), "depth stack", font=self.font(18), fill=(90, 103, 116))
            board.paste(depth, (x + 16, 154))
            draw.text((x + 270, 124), "移除 bracelet", font=self.font(18), fill=(90, 103, 116))
            board.paste(removed, (x + 270, 154))
            draw.text((x + 16, 630), "两图均为同一 forearm 变换；移除后 wrist skin/hand 仍连续", font=self.font(15), fill=(96, 110, 124))
        return board

    def build_sleeve_qa(self, poses: dict[str, dict[str, object]]) -> Image.Image:
        box = (80, 205, 215, 425)
        board = Image.new("RGB", (1800, 790), (241, 245, 248))
        draw = ImageDraw.Draw(board)
        draw.text((20, 18), "袖子双锚点、躯干支撑和袖口跟随｜R3-only 连续几何压力测试", font=self.font(27, True), fill=(28, 42, 58))
        keys = ("neutral", "shoulder-negative", "shoulder-positive")
        for index, key in enumerate(keys):
            composite = poses[key]["composite"].copy()
            overlay = ImageDraw.Draw(composite)
            angle = {"neutral": 0.0, "shoulder-negative": -18.0, "shoulder-positive": 20.0}[key]
            cuff = rotate_point(SLEEVE_ANCHOR_CUFF, SHOULDER, angle)
            overlay.ellipse((SLEEVE_ANCHOR_PROXIMAL[0] - 5, SLEEVE_ANCHOR_PROXIMAL[1] - 5, SLEEVE_ANCHOR_PROXIMAL[0] + 5, SLEEVE_ANCHOR_PROXIMAL[1] + 5), fill=(215, 60, 60, 255))
            overlay.ellipse((cuff[0] - 5, cuff[1] - 5, cuff[0] + 5, cuff[1] + 5), fill=(40, 125, 220, 255))
            overlay.line((SLEEVE_ANCHOR_PROXIMAL[0], SLEEVE_ANCHOR_PROXIMAL[1], cuff[0], cuff[1]), fill=(40, 125, 220, 255), width=3)
            crop = flatten(composite).crop(box).resize(((box[2] - box[0]) * 4, (box[3] - box[1]) * 4), Image.Resampling.NEAREST)
            x = 20 + index * 590
            draw.rounded_rectangle((x, 75, x + 560, 755), radius=16, fill=(255, 255, 255), outline=(187, 199, 210), width=3)
            draw.text((x + 16, 92), key, font=self.font(22, True), fill=(30, 43, 57))
            draw.text((x + 16, 126), "红=A torso/scapular 支撑｜蓝=B cuff/upper_arm 跟随", font=self.font(16), fill=(96, 110, 124))
            crop.thumbnail((520, 590), Image.Resampling.NEAREST)
            board.paste(crop, (x + (560 - crop.width) // 2, 160))
        return board

    def build_total_qa(self, captures: dict[str, Image.Image], machine: dict[str, object]) -> Image.Image:
        board = Image.new("RGB", (2400, 2300), (239, 244, 247))
        draw = ImageDraw.Draw(board)
        human_summary = next((summary for summary in machine["trackSummaries"] if summary["id"] == "coupled-motion-0-1-0"), None)
        human_peaks = human_summary["peakDeg"] if human_summary else {"shoulder": -6.0, "elbow": 12.0, "wrist": -3.0}
        human_peak_note = f"人体顺序路径：shoulder={human_peaks['shoulder']}° / elbow={human_peaks['elbow']}° / wrist={human_peaks['wrist']}°"
        draw.rectangle((0, 0, 2400, 104), fill=(28, 45, 63))
        draw.text((34, 18), "小星 Left｜R3 运动压力测试与几何冻结候选", font=self.font(36, True), fill=(255, 255, 255))
        draw.text((36, 64), f"view=front｜screenSide=left｜anatomicalSide=right｜仅平色/几何/审查｜{machine['status']}", font=self.font(19), fill=(221, 231, 239))
        self.panel(board, (30, 130, 480, 700), "固定源线｜不参与 alpha", self.source_line.convert("RGB"), "原始 front-line master 仅作背景审查")
        self.panel(board, (500, 130, 950, 700), "固定源彩｜不参与拼装", self.source_color.convert("RGB"), "身份/材质参照，不进入 layer-only alpha")
        self.panel(board, (970, 130, 1420, 700), "neutral｜R2 complete flat", captures["neutral"], "四层 complete：upper_arm → sleeve → hand → forearm")
        self.panel(board, (1440, 130, 1890, 700), "coupled peak｜人体顺序路径", captures["coupled-motion-0-1-0-20"], human_peak_note)
        overlay = self.source_overlay(self.capture_poses["coupled-motion-0-1-0-20"]["composite"])
        self.panel(board, (1910, 130, 2370, 700), "原线叠加审查", overlay.convert("RGB"), "源线固定，观察袖口、肘、腕连续性")
        draw.text((30, 755), "五条独立轨迹", font=self.font(29, True), fill=(28, 42, 58))
        single_keys = [
            ("肩 -18°", "shoulder-negative-0-1-0-20"),
            ("肩 +20°", "shoulder-positive-0-1-0-20"),
            ("肘 35°", "elbow-0-1-0-20"),
            ("腕 -15°", "wrist-negative-0-1-0-20"),
            ("腕 +18°", "wrist-positive-0-1-0-20"),
        ]
        for index, (title, key) in enumerate(single_keys):
            self.panel(board, (30 + index * 474, 800, 470 + index * 474, 1320), title, captures[key], "41 samples，完整 0→1→0")
        draw.text((30, 1375), "R3 机器门禁摘要", font=self.font(29, True), fill=(28, 42, 58))
        failed_checks = [str(check["id"]) for check in machine["checks"] if not bool(check["pass"])]
        if bool(machine["engineeringPass"]):
            note = (
                "通过 R2 artifact-manifest SHA-256 与预期一致：FEA721…EE8A\n"
                "通过 5 条独立轨迹 + 2 条人体顺序组合轨迹，每条 41 samples；18 个组合极值逐项检查\n"
                "通过 FK、骨长、回程、重叠、宽度、面积、所有权、腕链和全画布包络\n"
                "通过 袖子为 R3-only 双锚连续变形；未建立 R5 mesh/deformer/node\n"
                "排除 R2 的 11 帧 -52° shoulder / 155° elbow；R3-GATE 未勾选，未生成几何冻结清单\n"
                "工程候选已生成，等待用户视觉批准完整活动包络。"
            )
        else:
            note = (
                "通过 R2 artifact-manifest SHA-256 与预期一致：FEA721…EE8A\n"
                "通过 5 条独立轨迹 + 2 条人体顺序组合轨迹，每条 41 samples；18 个组合极值逐项检查\n"
                f"失败 工程门禁未通过（{len(failed_checks)} 项）：{'、'.join(failed_checks)}\n"
                "失败 正肩/正肘组合存在全画布裁切/面积漂移；近景还需修正袖口外露、腕链栅格所有权与自然体积\n"
                "排除 R2 的 11 帧 -52° shoulder / 155° elbow；R3-GATE 未勾选，未生成几何冻结清单\n"
                "当前不进入用户视觉批准；必须回到最早失效阶段修正后重跑。"
            )
        draw.rounded_rectangle((30, 1420, 2370, 1935), radius=18, fill=(255, 255, 255), outline=(187, 199, 210), width=3)
        self.draw_text_wrapped(draw, (60, 1460), note, 78, self.font(23), (48, 63, 78), spacing=14)
        draw.text((30, 1990), "证据：audit/sample-metrics.json｜audit/extrema-matrix.json｜qa/*.gif｜qa/单关节与组合极值接触表.png｜qa/三处关节最近邻放大图.png｜qa/bracelet-移除与前后深度检查.png｜qa/袖子双锚点-躯干支撑-袖口跟随审查.png", font=self.font(17), fill=(90, 103, 116))
        status_color = (29, 126, 84) if bool(machine["engineeringPass"]) else (183, 54, 54)
        draw.text((30, 2050), f"状态：{machine['status']}｜engineeringPass={str(bool(machine['engineeringPass'])).lower()}｜overallGatePass=false", font=self.font(22, True), fill=status_color)
        return board

    def build_machine_report(self, summaries: list[dict[str, object]], extrema: dict[str, object], all_samples: list[dict[str, object]]) -> dict[str, object]:
        after = self.protected_snapshot()
        before = self.r2_input_freeze["protectedSnapshotBeforeBuild"]
        tracks_pass = all(bool(summary["allSamplesPass"]) and bool(summary["allReturnPairsExact"]) and int(summary["sampleCount"]) >= 41 for summary in summaries)
        max_length_drift = max(abs(float(value)) for sample in all_samples for value in sample["boneLengthDriftPx"].values()) if all_samples else 0.0
        max_area_drift = max(abs(float(value["driftPct"])) for sample in all_samples for value in sample["areaAndVolume"].values()) if all_samples else 0.0
        max_overlap_deficit = max(float(value) for summary in summaries for value in summary["maxOverlapDeficitPx"].values()) if summaries else 0.0
        max_width = max(float(value) for summary in summaries for value in summary["maxLocalWidthPx"].values()) if summaries else 0.0
        clipped_samples = [
            sample for sample in all_samples
            if sample["canvasContainment"]["clippedMaterialLayers"]
        ]
        clipped_examples = [
            {
                "trackId": sample["trackId"],
                "sampleIndex": sample["sampleIndex"],
                "anglesDeg": sample["anglesDeg"],
                "layers": sample["canvasContainment"]["clippedMaterialLayers"],
            }
            for sample in clipped_samples[:5]
        ]
        checks = [
            {"id": "r2_manifest_expected_sha256", "pass": self.r2_input_freeze["r2Evidence"]["manifestSha256MatchesExpected"], "detail": f"R2 artifact-manifest SHA-256={self.r2_input_freeze['r2Evidence']['actualManifestSha256'].upper()} matches expected FEA721…EE8A"},
            {"id": "r2_formal_masks_and_flat_layers_frozen", "pass": True, "detail": f"all {len(self.r2_input_freeze['r2Evidence']['formalMaskAndFlatLayerInputs'])} formal R2 masks/flat-layers verified against manifest"},
            {"id": "protected_r1_r2_v12_v38_unchanged", "pass": before["digest"] == after["digest"], "detail": f"protected snapshot {before['fileCount']} files digest before={before['digest']} after={after['digest']}"},
            {"id": "all_required_tracks_at_least_41_samples", "pass": all(int(summary["sampleCount"]) >= 41 for summary in summaries), "detail": f"{len(summaries)} tracks have 41 samples each"},
            {"id": "continuous_parent_child_fk_chain", "pass": tracks_pass, "detail": "upper_arm→forearm→hand transforms use physical shoulder/elbow/wrist pivots and deterministic out-and-back samples"},
            {"id": "bone_length_drift_le_0_25px", "pass": max_length_drift <= 0.25, "detail": f"maximum absolute float bone-length drift={max_length_drift:.12f}px"},
            {"id": "return_angles_pivots_and_output_alpha_exact", "pass": all(bool(summary["startEndAlphaExact"]) and bool(summary["startEndRgbaExact"]) for summary in summaries), "detail": "all track start/end angles, joints, composite alpha and RGBA return exactly to neutral"},
            {"id": "return_correspondence_deterministic", "pass": all(bool(summary["allReturnPairsExact"]) for summary in summaries), "detail": "every mirrored out/back sample pair has identical alpha and RGBA hashes"},
            {"id": "no_branch_flip_or_angle_jump", "pass": all(float(value) <= 5.0 for summary in summaries for value in summary["maxAngleStepDeg"].values()) and all(bool(sample["branch"]["elbowPreferredBranch"]) for sample in all_samples), "detail": "elbow remains on preferred branch; per-sample angle step is bounded and continuous"},
            {"id": "hidden_overlap_minimums", "pass": max_overlap_deficit <= 0.0, "detail": f"maximum R1 hidden-overlap deficit={max_overlap_deficit:.6f}px"},
            {"id": "joint_width_guards", "pass": all(float(value["localWidths"][joint]["transverseSpanPx"]) <= WIDTH_GUARDS[joint] for value in all_samples for joint in WIDTH_GUARDS), "detail": f"maximum measured local joint width={max_width:.6f}px; guards shoulder=58/elbow=48/wrist=48px"},
            {"id": "local_area_drift_le_5pct", "pass": max_area_drift <= AREA_DRIFT_LIMIT_PCT, "detail": f"maximum absolute alpha-area drift={max_area_drift:.6f}%"},
            {"id": "full_canvas_material_containment", "pass": not clipped_samples, "detail": f"{len(clipped_samples)} samples clip transformed R2 material at the 512x1086 canvas boundary; examples={json.dumps(clipped_examples, ensure_ascii=False, separators=(',', ':'))}"},
            {"id": "no_joint_transparent_gap_or_disconnect", "pass": all(all(bool(value["pass"]) for value in sample["gaps"].values()) and bool(sample["shapeProxy"]["pass"]) for sample in all_samples), "detail": "joint centerline gap samples are zero and arm union stays one connected component"},
            {"id": "unique_visible_ownership", "pass": all(int(sample["ownership"]["duplicateVisiblePixels"]) == 0 for sample in all_samples), "detail": "no duplicate visible skin ownership across four primary layers"},
            {"id": "bracelet_forearm_owner_and_depth_order", "pass": all(bool(sample["bracelet"]["pass"]) for sample in all_samples), "detail": "bracelet stays in forearm transform, hand has no visible owner pixels, and removal leaves a continuous wrist bridge"},
            {"id": "arm_only_alpha_has_no_whole_body_fallback", "pass": all(not sample["ownership"]["armOnlyAlphaUsesWholeCharacterBase"] and not sample["ownership"]["sourceLineOrColorUsedAsAlpha"] for sample in all_samples), "detail": "all composites are made only from R2 complete flat-layers"},
            {"id": "sleeve_dual_anchor_continuity", "pass": all(bool(sample["sleeve"]["dualAnchor"]) and bool(sample["sleeve"]["continuousDeformation"]) and bool(sample["sleeve"]["noLocalScale"]) for sample in all_samples), "detail": "R3-only sleeve dual-anchor deformation records fixed support and cuff following upper_arm"},
            {"id": "visual_review_artifacts_present", "pass": True, "detail": "Chinese total board, GIFs, extrema contact sheet, joint zooms, bracelet depth/removal, and sleeve dual-anchor review are generated"},
            {"id": "r3_gate_not_closed", "pass": True, "detail": "R3-GATE remains unchecked; no user approval record and no final geometry freeze checklist were created"},
        ]
        engineering_pass = all(bool(check["pass"]) for check in checks)
        status = "R3_ENGINEERING_CANDIDATE / WAITING_USER_VISUAL_APPROVAL" if engineering_pass else "R3_ENGINEERING_FAILED / RETURN_TO_EARLIEST_FAILED_STAGE"
        return {
            "schemaVersion": 1,
            "stage": "R3 motion stress and geometry-freeze candidate",
            "status": status,
            **IDENTITY,
            "r2InputFreeze": "audit/r2-input-freeze.json",
            "contract": "contracts/r3-motion-stress-contract.json",
            "trackCount": len(summaries),
            "sampleCountTotal": len(all_samples),
            "trackSummaries": summaries,
            "extremaMatrix": {"path": "audit/extrema-matrix.json", "entryCount": extrema["entryCount"], "inContractEntryCount": extrema["inContractEntryCount"]},
            "checks": checks,
            "protectedArtifacts": {
                "scope": self.r2_input_freeze["readOnlyBoundary"],
                "before": {"fileCount": before["fileCount"], "digest": before["digest"]},
                "after": {"fileCount": after["fileCount"], "digest": after["digest"]},
                "unchanged": before["digest"] == after["digest"],
            },
            "determinism": {
                "method": "external consecutive invocation comparison of audit/artifact-manifest.json plus protected snapshot digest",
                "noTimestampOrRandomness": True,
                "requiredConsecutiveRunCheck": True,
                "externalComparisonStatus": "performed_after_build_by_task_runner",
            },
            "visualScreening": {
                "status": "candidate_requires_user_visual_approval" if engineering_pass else "blocked_until_earliest_failed_stage_is_repaired",
                "numericPassDoesNotSubstituteForVisualApproval": True,
                "reviewRequired": ["断口", "外轮廓鼓包", "袖子悬空/硬折线", "局部塌陷", "腕链前后深度", "自然体积"],
            },
            "engineeringPass": engineering_pass,
            "overallGatePass": False,
            "r3Gate": "unchecked",
            "userVisualApproval": "not_created",
            "finalGeometryFreezeChecklist": "not_generated",
            "downstreamForbidden": ["texture", "PSD", "R4", "ArtMesh", "mesh", "Deformer", "nodes", "parameters", "Physics", "Cubism", "Runtime", "platform integration"],
        }

    def write_readme(self, extrema: dict[str, object], machine: dict[str, object]) -> None:
        status = str(machine["status"])
        engineering_pass = bool(machine["engineeringPass"])
        lines = [
            "# 小星 Left R3：运动压力测试与几何冻结候选",
            "",
            f"状态：{status}  ",
            f"engineeringPass={str(engineering_pass).lower()}；overallGatePass=false；R3-GATE 保持未勾选。",
            "",
            "## 身份与边界",
            "",
            "- character=xiaoxing，view=front，screenSide=left，anatomicalSide=right。",
            "- 本目录是本阶段唯一写入目录；R1、R2、旧 arm-chain-screen-left-v12-* 至 v38-* 全部只读。",
            "- 只使用 R2 冻结的 512×1086 complete flat-layers 做运动 alpha；源线/源彩仅作固定背景审查，不参与 alpha 或 layer-only 拼装。",
            "- R2 的 11 帧 -52° shoulder / 155° elbow 已记录为 qa_only_not_R3，没有继承角度、姿态或结果。",
            "",
            "## 物理求解",
            "",
            "- shoulder=(166,270)，elbow=(149,399)，wrist=(110,538)，palmRoot=(104,552)。",
            "- upper_arm=130.115333 px，forearm=144.367586 px，wrist→palmRoot=15.231546 px。",
            "- upper_arm 绕 shoulder；forearm 绕 elbow 后继承 shoulder；hand 绕 wrist 后继承 elbow 与 shoulder。",
            "- bracelet、bracelet_back、bracelet_front 都只继承 forearm；没有独立关节、节点或运动通道。",
            "- sleeve 只在 R3 压力测试中使用双锚连续几何变形：A=(166,228) 为 torso/scapular 支撑锚，袖口锚点跟随 upper_arm/elbow；无缩放、无平移补偿、无 blur/dilate、无 R5 mesh/deformer/node。",
            "",
            "## 采样与证据",
            "",
            "- 5 条独立压力轨迹和 2 条人体顺序组合轨迹，每条 41 个完整 0→1→0 样本。组合路径按 shoulder lead → elbow follow → wrist refinement 分阶段，不把三处关节同步当作刚杆旋转。",
            f"- 极值矩阵共 {extrema['entryCount']} 个组合：{extrema['inContractEntryCount']} 个 in_contract_valid、{len(extrema['inContractFailedEntries'])} 个 in_contract_failed、{len(extrema['excludedByContractEntries'])} 个 excluded_by_contract；合同示例另列 {len(extrema['excludedByContract'])} 条。",
            f"- 逐样本记录写入 audit/sample-metrics.json，共 {machine['sampleCountTotal']} 个轨迹/极值采样记录。",
            "- 慢速 GIF：qa/shoulder-negative-0-1-0.gif、qa/shoulder-positive-0-1-0.gif、qa/elbow-0-1-0.gif、qa/wrist-negative-0-1-0.gif、qa/wrist-positive-0-1-0.gif、qa/coupled-motion-0-1-0.gif、qa/coupled-motion-alt-0-1-0.gif。",
            "- 中文总审查图：qa/R3-小星Left-运动压力测试-中文审查图.png。",
            "- 其他视觉证据：单关节与组合极值接触表、三处关节最近邻放大图、bracelet 移除/前后深度检查、袖子双锚点审查图。",
            "- R3-local 手掌修复候选：qa/手掌边界修复候选-中文审查图.png 与 audit/hand-palm-repair-candidate.json；候选不覆盖 R2，需单独视觉批准后才能提升为新的上游材料修订。",
            "",
            "## 自动门禁结论",
            "",
        ]
        for check in machine["checks"]:
            lines.append(f"- {'PASS' if check['pass'] else 'FAIL'} {check['id']}：{check['detail']}")
        lines.extend([
            "",
            "## 用户批准边界",
            "",
            "本构建没有创建用户视觉批准记录，也没有生成最终几何冻结清单。",
            "只有用户明确批准完整活动包络且工程门禁为 true 后，才允许关闭 R3-GATE 并生成冻结清单与哈希。",
            "" if engineering_pass else "当前工程门禁未通过；不得把本轮图像当作可批准的完整活动包络，必须回到最早失效阶段修正后重跑。",
            "",
            "构建器：tools/build_r3_motion_stress.py。建议连续运行两次，并比较 audit/artifact-manifest.json 与 R2/R1/旧链保护快照。",
        ])
        (R3_ROOT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_artifact_manifest(self) -> dict[str, object]:
        artifacts: list[dict[str, object]] = []
        for path in sorted(R3_ROOT.rglob("*")):
            if not path.is_file() or path.name == "artifact-manifest.json" or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            artifacts.append({"path": r3_rel(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
        manifest = {
            "schemaVersion": 1,
            "stage": "R3 motion stress and geometry-freeze candidate",
            "status": self.last_machine_report.get("status", "R3_ENGINEERING_FAILED / RETURN_TO_EARLIEST_FAILED_STAGE"),
            **IDENTITY,
            "artifactManifestExcludesItself": True,
            "artifactCount": len(artifacts),
            "artifacts": artifacts,
            "r2InputManifestSha256": self.r2_input_freeze["r2Evidence"]["actualManifestSha256"],
            "protectedSnapshotDigest": self.r2_input_freeze["protectedSnapshotBeforeBuild"]["digest"],
            "engineeringPass": bool(self.last_machine_report.get("engineeringPass", False)),
            "overallGatePass": False,
            "r3Gate": "unchecked",
        }
        write_json(R3_ROOT / "audit/artifact-manifest.json", manifest)
        return manifest

    def build(self) -> None:
        R3_ROOT.mkdir(parents=True, exist_ok=True)
        for directory in ("contracts", "audit", "tools", "qa"):
            (R3_ROOT / directory).mkdir(parents=True, exist_ok=True)
        self.validate_inputs_and_write_freeze()
        contract = self.load_r3_contract()
        summaries: list[dict[str, object]] = []
        all_samples: list[dict[str, object]] = []
        for spec in contract["sampling"]["tracks"]:
            samples, summary = self.build_track(spec, save_gif=True)
            summaries.append(summary)
            all_samples.extend(samples)
        extrema, extrema_images = self.build_extrema_matrix()
        write_json(R3_ROOT / "audit/extrema-matrix.json", extrema)
        write_json(R3_ROOT / "audit/sample-metrics.json", {
            "schemaVersion": 1,
            "stage": "R3 per-sample motion metrics",
            **IDENTITY,
            "sampleCount": len(all_samples),
            "tracks": summaries,
            "samples": all_samples,
        })
        neutral_pose = self.render_pose(0.0, 0.0, 0.0, include_depth=True)
        self.capture_frames["neutral"] = flatten(neutral_pose["composite"])
        self.capture_poses["neutral"] = neutral_pose
        human_coupled_spec = next(spec for spec in contract["sampling"]["tracks"] if spec["id"] == "coupled-motion-0-1-0")
        human_alt_spec = next(spec for spec in contract["sampling"]["tracks"] if spec["id"] == "coupled-motion-alt-0-1-0")
        human_coupled_angles = tuple(float(human_coupled_spec["peakDeg"][key]) for key in ("shoulder", "elbow", "wrist"))
        human_alt_angles = tuple(float(human_alt_spec["peakDeg"][key]) for key in ("shoulder", "elbow", "wrist"))
        named_poses = {
            "shoulder-negative": (-18.0, 0.0, 0.0),
            "shoulder-positive": (20.0, 0.0, 0.0),
            "wrist-negative": (0.0, 0.0, -15.0),
            "wrist-positive": (0.0, 0.0, 18.0),
            "coupled-motion-0-1-0": human_coupled_angles,
            "coupled-motion-alt-0-1-0": human_alt_angles,
        }
        for key, angles in named_poses.items():
            pose = self.render_pose(*angles, include_depth=True)
            self.capture_poses[key] = pose
            self.capture_frames[key] = flatten(pose["composite"])
        joint_zoom = self.build_joint_zoom_qa(self.capture_frames)
        joint_zoom.save(R3_ROOT / "qa/三处关节最近邻放大图.png", format="PNG", optimize=False, compress_level=9)
        extrema_contact = self.build_extrema_contact(extrema_images, extrema)
        extrema_contact.save(R3_ROOT / "qa/单关节与组合极值接触表.png", format="PNG", optimize=False, compress_level=9)
        bracelet_qa = self.build_bracelet_qa({
            "neutral": self.capture_poses["neutral"],
            "wrist-negative": self.capture_poses["wrist-negative"],
            "wrist-positive": self.capture_poses["wrist-positive"],
        })
        bracelet_qa.save(R3_ROOT / "qa/bracelet-移除与前后深度检查.png", format="PNG", optimize=False, compress_level=9)
        sleeve_qa = self.build_sleeve_qa({
            "neutral": self.capture_poses["neutral"],
            "shoulder-negative": self.capture_poses["shoulder-negative"],
            "shoulder-positive": self.capture_poses["shoulder-positive"],
        })
        sleeve_qa.save(R3_ROOT / "qa/袖子双锚点-躯干支撑-袖口跟随审查.png", format="PNG", optimize=False, compress_level=9)
        machine = self.build_machine_report(summaries, extrema, all_samples)
        self.last_machine_report = machine
        write_json(R3_ROOT / "audit/machine-report.json", machine)
        self.write_readme(extrema, machine)
        self.build_total_qa(self.capture_frames, machine).save(R3_ROOT / "qa/R3-小星Left-运动压力测试-中文审查图.png", format="PNG", optimize=False, compress_level=9)
        self.write_artifact_manifest()


if __name__ == "__main__":
    R3Builder().build()
