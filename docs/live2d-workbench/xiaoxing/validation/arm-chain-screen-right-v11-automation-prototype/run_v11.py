from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from collections import deque
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageChops, ImageDraw


SCRIPT_VERSION = 2
ROOT = Path(__file__).resolve().parent
XIAOXING = ROOT.parents[1]
DEFAULT_CONFIG = ROOT / "config.json"
OUTPUT = ROOT / "output"
RUN_A = ROOT / ".v11-run-a"
RUN_B = ROOT / ".v11-run-b"
OUTPUT_BACKUP = ROOT / ".v11-output-backup"


class PipelineFailure(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PipelineFailure(f"无法读取 JSON：{display(path)}：{exc}") from exc
    if not isinstance(value, dict):
        raise PipelineFailure(f"JSON 根节点不是对象：{display(path)}")
    return value


def display(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(XIAOXING.resolve()).as_posix()
    except ValueError:
        return resolved.relative_to(ROOT.resolve()).as_posix()


def source_path(raw: str) -> Path:
    candidate = (XIAOXING / raw).resolve()
    try:
        candidate.relative_to(XIAOXING.resolve())
    except ValueError as exc:
        raise PipelineFailure(f"配置路径越界：{raw}") from exc
    return candidate


def ensure_owned_output(path: Path) -> None:
    if path.resolve().parent != ROOT.resolve():
        raise PipelineFailure("拒绝清理 V11 目录以外的路径")
    if path.name not in {
        "output",
        ".v11-run-a",
        ".v11-run-b",
        ".v11-output-backup",
    }:
        raise PipelineFailure("拒绝清理非 V11 生成目录")


def reset_directory(path: Path) -> None:
    ensure_owned_output(path)
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def transactional_publish(
    source: Path,
    validate_published: Callable[[Path], None],
) -> dict[str, Any]:
    ensure_owned_output(source)
    ensure_owned_output(OUTPUT)
    ensure_owned_output(OUTPUT_BACKUP)
    if OUTPUT_BACKUP.exists():
        if OUTPUT.exists():
            raise PipelineFailure(
                "检测到 output 与发布备份同时存在；拒绝删除可恢复旧输出"
            )
        OUTPUT_BACKUP.replace(OUTPUT)

    previous_output_moved = False
    candidate_installed = False
    try:
        if OUTPUT.exists():
            OUTPUT.replace(OUTPUT_BACKUP)
            previous_output_moved = True
        source.replace(OUTPUT)
        candidate_installed = True
        validate_published(OUTPUT)
    except Exception as publish_error:
        rollback_errors = []
        if candidate_installed and OUTPUT.exists():
            try:
                shutil.rmtree(OUTPUT)
            except OSError as exc:
                rollback_errors.append(f"无法移除失败的新输出：{exc}")
        if previous_output_moved and OUTPUT_BACKUP.exists():
            try:
                if OUTPUT.exists():
                    raise OSError("新输出仍占用 output 路径")
                OUTPUT_BACKUP.replace(OUTPUT)
            except OSError as exc:
                rollback_errors.append(f"无法恢复旧输出：{exc}")
        if rollback_errors:
            raise PipelineFailure(
                f"发布失败且回滚不完整：{'; '.join(rollback_errors)}"
            ) from publish_error
        raise

    cleanup_warning = None
    if OUTPUT_BACKUP.exists():
        try:
            shutil.rmtree(OUTPUT_BACKUP)
        except OSError as exc:
            cleanup_warning = (
                "新输出已验证并提交，但旧输出备份清理失败；"
                f"保留备份以供恢复：{exc}"
            )
    return {
        "status": "pass",
        "method": "transactional_directory_swap_with_rollback",
        "candidateValidatedAfterSwap": True,
        "publishedOutputModifiedAfterSwap": False,
        "backupCleanupWarning": cleanup_warning,
    }


def freeze_snapshot(config: dict[str, Any]) -> dict[str, Any]:
    freeze = config["freeze"]
    manifest_path = source_path(freeze["manifest"])
    if not manifest_path.is_file():
        raise PipelineFailure("V10 冻结清单不存在")
    actual_manifest_hash = sha256(manifest_path)
    if actual_manifest_hash != freeze["manifestSha256"]:
        raise PipelineFailure("V10 冻结清单哈希不一致")

    manifest = read_json(manifest_path)
    records = manifest.get("lockedArtifacts")
    expected_count = int(freeze["artifactCount"])
    if not isinstance(records, list) or len(records) != expected_count:
        raise PipelineFailure(
            f"V10 冻结项目数不是 {expected_count}："
            f"{len(records) if isinstance(records, list) else 'invalid'}"
        )

    v10_root = manifest_path.parents[1]
    artifacts: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    for record in records:
        raw = record.get("path")
        expected_hash = str(record.get("sha256", "")).lower()
        expected_bytes = int(record.get("bytes", -1))
        if not isinstance(raw, str):
            failures.append({"path": "<invalid>", "reason": "path"})
            continue
        path = (v10_root / raw).resolve()
        try:
            path.relative_to(v10_root.resolve())
        except ValueError:
            failures.append({"path": raw, "reason": "path_escape"})
            continue
        if not path.is_file():
            failures.append({"path": raw, "reason": "missing"})
            continue
        actual_hash = sha256(path)
        actual_bytes = path.stat().st_size
        artifacts[raw] = {"sha256": actual_hash, "bytes": actual_bytes}
        if actual_hash != expected_hash or actual_bytes != expected_bytes:
            failures.append(
                {
                    "path": raw,
                    "reason": "content_mismatch",
                    "expectedSha256": expected_hash,
                    "actualSha256": actual_hash,
                    "expectedBytes": expected_bytes,
                    "actualBytes": actual_bytes,
                }
            )

    upstream = []
    for record in manifest.get("frozenUpstreamAuthority", []):
        path = source_path(record["manifest"])
        actual_hash = sha256(path) if path.is_file() else None
        passed = actual_hash == record["sha256"]
        upstream.append(
            {
                "group": record["group"],
                "path": record["manifest"],
                "expectedSha256": record["sha256"],
                "actualSha256": actual_hash,
                "pass": passed,
            }
        )
        if not passed:
            failures.append(
                {"path": record["manifest"], "reason": "upstream_manifest_mismatch"}
            )

    if failures:
        first = failures[0]
        raise PipelineFailure(
            f"冻结输入校验失败（{len(failures)} 项），首项：{first['path']}"
        )
    return {
        "manifestPath": freeze["manifest"],
        "manifestSha256": actual_manifest_hash,
        "artifactCount": expected_count,
        "matchedArtifacts": len(artifacts),
        "artifacts": artifacts,
        "upstreamManifests": upstream,
    }


def compare_snapshots(before: dict[str, Any], after: dict[str, Any]) -> None:
    if before != after:
        raise PipelineFailure("V10 冻结文件在运行期间发生变化")


def prepare_inputs(config: dict[str, Any], work: Path) -> dict[str, Any]:
    canvas = tuple(config["canvas"])
    material_dir = work / "materials"
    psd_dir = work / "psd"
    material_dir.mkdir(parents=True)
    psd_dir.mkdir(parents=True)
    prepared = []

    for index, record in enumerate(config["materials"], start=1):
        source = source_path(record["path"])
        if not source.is_file() or sha256(source) != record["sha256"]:
            raise PipelineFailure(f"材料哈希不一致：{record['id']}")
        with Image.open(source) as image:
            if image.size != canvas:
                raise PipelineFailure(f"材料不是全画布：{record['id']}")
            if "A" not in image.getbands():
                raise PipelineFailure(f"材料缺少 alpha：{record['id']}")
            alpha = image.getchannel("A")
            bbox = alpha.getbbox()
            if bbox is None:
                raise PipelineFailure(f"材料 alpha 为空：{record['id']}")
            output_name = f"{index:02d}_{record['id']}.png"
            output = material_dir / output_name
            shutil.copyfile(source, output)
            prepared.append(
                {
                    "id": record["id"],
                    "source": record["path"],
                    "output": f"materials/{output_name}",
                    "sha256": sha256(output),
                    "canvas": list(image.size),
                    "alphaBoundingBox": list(bbox),
                    "alphaNonzeroPixels": sum(
                        value > 0 for value in alpha.get_flattened_data()
                    ),
                    "drawOrder": record["drawOrder"],
                }
            )

    psd_record = config["sources"]["psd"]
    psd_source = source_path(psd_record["path"])
    if not psd_source.is_file() or sha256(psd_source) != psd_record["sha256"]:
        raise PipelineFailure("Cubism 导入 PSD 哈希不一致")
    psd_output = psd_dir / psd_record["outputName"]
    shutil.copyfile(psd_source, psd_output)
    if sha256(psd_output) != psd_record["sha256"]:
        raise PipelineFailure("Cubism 导入 PSD 确定性复制失败")

    return {
        "materials": prepared,
        "psd": {
            "source": psd_record["path"],
            "output": f"psd/{psd_output.name}",
            "sha256": sha256(psd_output),
            "bytes": psd_output.stat().st_size,
            "method": "byte_exact_copy_of_hash_locked_v10_import_psd",
            "transformed": False,
        },
    }


def point(record: dict[str, Any]) -> tuple[float, float]:
    return float(record["x"]), float(record["y"])


def fk(
    shoulder: tuple[float, float],
    l1: float,
    l2: float,
    theta1: float,
    theta2: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    first = math.radians(theta1)
    second = math.radians(theta1 + theta2)
    elbow = (
        shoulder[0] + l1 * math.cos(first),
        shoulder[1] + l1 * math.sin(first),
    )
    wrist = (
        elbow[0] + l2 * math.cos(second),
        elbow[1] + l2 * math.sin(second),
    )
    return elbow, wrist


def rotate_point(
    origin: tuple[float, float],
    value: tuple[float, float],
    angle_deg: float,
) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    cosine, sine = math.cos(angle), math.sin(angle)
    dx, dy = value[0] - origin[0], value[1] - origin[1]
    return (
        origin[0] + cosine * dx - sine * dy,
        origin[1] + sine * dx + cosine * dy,
    )


def make_sample(
    index: int | str,
    progress: float | None,
    theta1: float,
    theta2: float,
    phi: float,
    shoulder: tuple[float, float],
    l1: float,
    l2: float,
    hand_rest: tuple[float, float],
    rest_wrist: tuple[float, float],
) -> dict[str, Any]:
    elbow, wrist = fk(shoulder, l1, l2, theta1, theta2)
    hand_local = (
        hand_rest[0] - rest_wrist[0],
        hand_rest[1] - rest_wrist[1],
    )
    hand_reference = rotate_point(
        wrist,
        (wrist[0] + hand_local[0], wrist[1] + hand_local[1]),
        theta1 + theta2 + phi
        - (REST["theta1"] + REST["theta2"] + REST["phi"]),
    )
    return {
        "index": index,
        "progress": None if progress is None else round(progress, 9),
        "theta1": round(theta1, 9),
        "theta2": round(theta2, 9),
        "phiWristLocal": round(phi, 9),
        "shoulder": [round(v, 9) for v in shoulder],
        "elbow": [round(v, 9) for v in elbow],
        "wrist": [round(v, 9) for v in wrist],
        "handReference": [round(v, 9) for v in hand_reference],
        "L1": l1,
        "L2": l2,
    }


REST: dict[str, float] = {}


def build_samples(
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    skeleton = read_json(source_path(config["sources"]["skeleton"]))
    contract = read_json(source_path(config["sources"]["rigContract"]))
    landmarks = skeleton["landmarks"]
    shoulder = point(landmarks["shoulder"])
    rest_elbow = point(landmarks["elbow"])
    rest_wrist = point(landmarks["wrist"])
    lengths = skeleton["boneLengthsPx"]
    l1 = float(lengths["L1ShoulderToElbow"])
    l2 = float(lengths["L2ElbowToWrist"])
    motion = skeleton["primaryMotion"]
    rest = motion["rest"]
    target = motion["target"]
    REST.update(
        theta1=float(rest["theta1"]),
        theta2=float(rest["theta2"]),
        phi=float(rest["phiWristLocal"]),
    )
    hand_rest = point(skeleton["handMotionReference"]["restPoint"])

    samples = []
    for index in range(41):
        phase_index = index if index <= 20 else 40 - index
        progress = 0.5 * (1.0 - math.cos(math.pi * phase_index / 20.0))
        theta1 = REST["theta1"] + progress * (float(target["theta1"]) - REST["theta1"])
        theta2 = REST["theta2"] + progress * (float(target["theta2"]) - REST["theta2"])
        phi = REST["phi"] + progress * (float(target["phiWristLocal"]) - REST["phi"])
        samples.append(
            make_sample(
                index,
                progress,
                theta1,
                theta2,
                phi,
                shoulder,
                l1,
                l2,
                hand_rest,
                rest_wrist,
            )
        )

    extremes = []
    combinations = [
        (
            value["theta1"],
            value["theta2"],
            REST["phi"],
            f"joint-{index + 1}",
        )
        for index, value in enumerate(skeleton["requiredCombinationExtremes"])
    ]
    combinations.extend(
        (
            value["theta1"],
            value["theta2"],
            value["phiWristLocal"],
            f"wrist-{index + 1}",
        )
        for index, value in enumerate(skeleton["requiredWristExtremes"])
    )
    for theta1, theta2, phi, name in combinations:
        extremes.append(
            make_sample(
                name,
                None,
                float(theta1),
                float(theta2),
                float(phi),
                shoulder,
                l1,
                l2,
                hand_rest,
                rest_wrist,
            )
        )

    frozen = contract["frozenSkeleton"]
    for key, actual in (
        ("shoulder", list(shoulder)),
        ("elbow", list(rest_elbow)),
        ("wrist", list(rest_wrist)),
    ):
        if any(abs(a - b) > 1e-9 for a, b in zip(actual, frozen[key])):
            raise PipelineFailure(f"V4/V10 骨架坐标不一致：{key}")
    if abs(l1 - frozen["L1Px"]) > 1e-9 or abs(l2 - frozen["L2Px"]) > 1e-9:
        raise PipelineFailure("V4/V10 骨长不一致")

    return (
        {
            "schemaVersion": 1,
            "motion": motion["name"],
            "path": motion["path"],
            "physics": False,
            "primary41": samples,
            "combinationExtremes": extremes,
        },
        skeleton,
        contract,
    )


def distance(a: list[float], b: list[float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def validate_fk(
    config: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    tolerance = float(config["checks"]["boneLengthTolerancePx"])
    reference_tolerance = float(config["checks"]["sampleReferenceTolerancePx"])
    samples = payload["primary41"]
    extremes = payload["combinationExtremes"]
    if len(samples) != 41:
        raise PipelineFailure("FK 主路径不是 41 样本")
    if len(extremes) != config["checks"]["expectedCombinationExtremeCount"]:
        raise PipelineFailure("组合极值数量不正确")

    max_l1_error = 0.0
    max_l2_error = 0.0
    for sample in [*samples, *extremes]:
        l1_error = abs(distance(sample["shoulder"], sample["elbow"]) - sample["L1"])
        l2_error = abs(distance(sample["elbow"], sample["wrist"]) - sample["L2"])
        max_l1_error = max(max_l1_error, l1_error)
        max_l2_error = max(max_l2_error, l2_error)
    if max_l1_error > tolerance or max_l2_error > tolerance:
        raise PipelineFailure("FK 骨长误差超限")

    reference = read_json(source_path(config["sources"]["sampleReference"]))
    reference_samples = reference.get("samples", [])
    if len(reference_samples) != 41:
        raise PipelineFailure("V4 参考样本不是 41 项")
    max_reference_error = 0.0
    for generated, expected in zip(samples, reference_samples):
        for field in ("elbow", "wrist", "handReference"):
            max_reference_error = max(
                max_reference_error,
                *(abs(a - b) for a, b in zip(generated[field], expected[field])),
            )
    if max_reference_error > reference_tolerance:
        raise PipelineFailure("重算 FK 与冻结 V4 样本不一致")

    return_error = max(
        abs(a - b)
        for field in ("elbow", "wrist", "handReference")
        for a, b in zip(samples[0][field], samples[-1][field])
    )
    if return_error > 1e-9:
        raise PipelineFailure("FK 0→1→0 回程不确定")
    return {
        "primarySampleCount": len(samples),
        "combinationExtremeCount": len(extremes),
        "maximumL1ErrorPx": round(max_l1_error, 12),
        "maximumL2ErrorPx": round(max_l2_error, 12),
        "maximumReferenceCoordinateErrorPx": round(max_reference_error, 12),
        "returnCoordinateErrorPx": round(return_error, 12),
        "pass": True,
    }


def affine_layer(
    image: Image.Image,
    rest_pivot: tuple[float, float],
    target_pivot: tuple[float, float],
    angle_deg: float,
) -> Image.Image:
    angle = math.radians(angle_deg)
    cosine, sine = math.cos(angle), math.sin(angle)
    a, b = cosine, sine
    d, e = -sine, cosine
    c = rest_pivot[0] - cosine * target_pivot[0] - sine * target_pivot[1]
    f = rest_pivot[1] + sine * target_pivot[0] - cosine * target_pivot[1]
    return image.transform(
        image.size,
        Image.Transform.AFFINE,
        (a, b, c, d, e, f),
        resample=Image.Resampling.BICUBIC,
    )


def transformed_layers(
    images: dict[str, Image.Image],
    sample: dict[str, Any],
    skeleton: dict[str, Any],
) -> dict[str, Image.Image]:
    shoulder = point(skeleton["landmarks"]["shoulder"])
    elbow = point(skeleton["landmarks"]["elbow"])
    wrist = point(skeleton["landmarks"]["wrist"])
    target_elbow = tuple(sample["elbow"])
    target_wrist = tuple(sample["wrist"])
    shoulder_delta = sample["theta1"] - REST["theta1"]
    forearm_delta = (
        sample["theta1"] + sample["theta2"] - REST["theta1"] - REST["theta2"]
    )
    hand_delta = forearm_delta + sample["phiWristLocal"] - REST["phi"]
    return {
        "sleeve": affine_layer(images["sleeve"], shoulder, shoulder, shoulder_delta),
        "upper_arm": affine_layer(
            images["upper_arm"], shoulder, shoulder, shoulder_delta
        ),
        "forearm": affine_layer(
            images["forearm"], elbow, target_elbow, forearm_delta
        ),
        "hand": affine_layer(images["hand"], wrist, target_wrist, hand_delta),
    }


def binary_alpha(image: Image.Image, threshold: int) -> Image.Image:
    return image.getchannel("A").point(
        lambda value: 255 if value >= threshold else 0,
        mode="1",
    )


def mask_count(mask: Image.Image) -> int:
    return sum(bool(value) for value in mask.get_flattened_data())


def component_count(mask: Image.Image) -> int:
    width, height = mask.size
    pixels = mask.load()
    visited = bytearray(width * height)
    components = 0
    for y in range(height):
        for x in range(width):
            offset = y * width + x
            if not pixels[x, y] or visited[offset]:
                continue
            components += 1
            queue = deque([(x, y)])
            visited[offset] = 1
            while queue:
                px, py = queue.popleft()
                for nx, ny in (
                    (px - 1, py),
                    (px + 1, py),
                    (px, py - 1),
                    (px, py + 1),
                    (px - 1, py - 1),
                    (px + 1, py - 1),
                    (px - 1, py + 1),
                    (px + 1, py + 1),
                ):
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    next_offset = ny * width + nx
                    if pixels[nx, ny] and not visited[next_offset]:
                        visited[next_offset] = 1
                        queue.append((nx, ny))
    return components


def composite(
    layers: dict[str, Image.Image],
    draw_orders: dict[str, int],
) -> Image.Image:
    result = Image.new("RGBA", next(iter(layers.values())).size, (0, 0, 0, 0))
    for layer_id in sorted(layers, key=lambda value: draw_orders[value]):
        result.alpha_composite(layers[layer_id])
    return result


def validate_material_motion(
    config: dict[str, Any],
    payload: dict[str, Any],
    skeleton: dict[str, Any],
    work: Path,
) -> tuple[dict[str, Any], dict[str, Image.Image]]:
    threshold = int(config["checks"]["alphaThreshold"])
    minimum_overlap = int(config["checks"]["minimumAdjacentOverlapPixels"])
    images = {}
    draw_orders = {}
    for index, record in enumerate(config["materials"], start=1):
        path = work / "materials" / f"{index:02d}_{record['id']}.png"
        images[record["id"]] = Image.open(path).convert("RGBA")
        draw_orders[record["id"]] = int(record["drawOrder"])

    rows = []
    selected: dict[str, Image.Image] = {}
    all_samples = [
        *payload["primary41"],
        *payload["combinationExtremes"],
    ]
    for position, sample in enumerate(all_samples):
        layers = transformed_layers(images, sample, skeleton)
        masks = {key: binary_alpha(value, threshold) for key, value in layers.items()}
        overlaps = {
            "sleeveUpper": mask_count(
                ImageChops.logical_and(masks["sleeve"], masks["upper_arm"])
            ),
            "upperForearm": mask_count(
                ImageChops.logical_and(masks["upper_arm"], masks["forearm"])
            ),
            "forearmHand": mask_count(
                ImageChops.logical_and(masks["forearm"], masks["hand"])
            ),
        }
        union = masks["sleeve"]
        for layer_id in ("upper_arm", "forearm", "hand"):
            union = ImageChops.logical_or(union, masks[layer_id])
        components = component_count(union)
        passed = components == 1 and all(
            value >= minimum_overlap for value in overlaps.values()
        )
        rows.append(
            {
                "sample": sample["index"],
                "adjacentOverlapPixels": overlaps,
                "unionConnectedComponents": components,
                "seamGapDetected": any(
                    value < minimum_overlap for value in overlaps.values()
                ),
                "detachmentDetected": components != 1,
                "pass": passed,
            }
        )
        if not passed:
            raise PipelineFailure(f"材料运动接缝或断开检查失败：{sample['index']}")
        if position in (0, 10, 20, 30, 40):
            selected[f"primary-{sample['index']}"] = composite(layers, draw_orders)
        if isinstance(sample["index"], str) and sample["index"] in {
            "joint-1",
            "joint-4",
            "wrist-2",
        }:
            selected[str(sample["index"])] = composite(layers, draw_orders)

    first = composite(
        transformed_layers(images, payload["primary41"][0], skeleton),
        draw_orders,
    )
    returned = composite(
        transformed_layers(images, payload["primary41"][-1], skeleton),
        draw_orders,
    )
    return_changed = sum(
        any(channel != 0 for channel in pixel)
        for pixel in ImageChops.difference(first, returned).get_flattened_data()
    )
    if return_changed != config["checks"]["expectedReturnChangedPixels"]:
        raise PipelineFailure("材料渲染 0→1→0 回程像素不一致")

    return (
        {
            "evaluatedPoseCount": len(rows),
            "primarySampleCount": 41,
            "combinationExtremeCount": len(payload["combinationExtremes"]),
            "minimumOverlapPixels": {
                key: min(row["adjacentOverlapPixels"][key] for row in rows)
                for key in ("sleeveUpper", "upperForearm", "forearmHand")
            },
            "maximumUnionConnectedComponents": max(
                row["unionConnectedComponents"] for row in rows
            ),
            "seamFailureCount": sum(row["seamGapDetected"] for row in rows),
            "detachmentFailureCount": sum(
                row["detachmentDetected"] for row in rows
            ),
            "returnChangedPixels": return_changed,
            "samples": rows,
            "pass": True,
        },
        selected,
    )


def validate_mesh(config: dict[str, Any]) -> dict[str, Any]:
    audit = read_json(source_path(config["sources"]["meshAudit"]))
    meshes = audit.get("artMeshQa", {}).get("meshes", [])
    if len(meshes) != config["checks"]["expectedMeshCount"]:
        raise PipelineFailure("冻结 ArtMesh 数量不正确")
    checked = []
    for mesh in meshes:
        expected_triangles = 2 * mesh["vertices"] - 2 - mesh["boundaryVertices"]
        passed = (
            mesh["triangles"] == expected_triangles
            and mesh["degenerateTriangles"] == 0
            and mesh["foldovers"] == 0
            and mesh["outOfBoundsVertices"] == 0
        )
        checked.append(
            {
                "id": mesh["id"],
                "vertices": mesh["vertices"],
                "boundaryVertices": mesh["boundaryVertices"],
                "triangles": mesh["triangles"],
                "expectedTriangles": expected_triangles,
                "degenerateTriangles": mesh["degenerateTriangles"],
                "foldovers": mesh["foldovers"],
                "outOfBoundsVertices": mesh["outOfBoundsVertices"],
                "pass": passed,
            }
        )
        if not passed:
            raise PipelineFailure(f"冻结网格检查失败：{mesh['id']}")
    return {
        "method": "revalidate_hash_locked_v10_numeric_mesh_records",
        "freshCmo3VertexExtraction": False,
        "meshes": checked,
        "pass": True,
    }


def build_review_board(
    images: dict[str, Image.Image],
    work: Path,
) -> str:
    qa = work / "qa"
    qa.mkdir()
    names = [
        "primary-0",
        "primary-10",
        "primary-20",
        "joint-1",
        "joint-4",
        "wrist-2",
    ]
    panel_size = (256, 543)
    board = Image.new("RGB", (panel_size[0] * 3, panel_size[1] * 2), (44, 44, 48))
    for index, name in enumerate(names):
        image = images[name]
        checker = Image.new("RGBA", image.size, (226, 226, 226, 255))
        draw = ImageDraw.Draw(checker)
        tile = 16
        for y in range(0, image.height, tile):
            for x in range(0, image.width, tile):
                if (x // tile + y // tile) % 2:
                    draw.rectangle(
                        (x, y, x + tile - 1, y + tile - 1),
                        fill=(192, 192, 192, 255),
                    )
        checker.alpha_composite(image)
        panel = checker.resize(panel_size, Image.Resampling.LANCZOS).convert("RGB")
        board.paste(panel, ((index % 3) * panel_size[0], (index // 3) * panel_size[1]))
    output = qa / "v11-minimal-review-board.png"
    board.save(output, optimize=False)
    return "qa/v11-minimal-review-board.png"


def file_manifest(work: Path, paths: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "path": raw,
            "sha256": sha256(work / raw),
            "bytes": (work / raw).stat().st_size,
        }
        for raw in sorted(paths)
    ]


def deterministic_paths(result: dict[str, Any]) -> list[str]:
    return sorted(record["path"] for record in result["artifacts"])


def compare_runs(
    first: Path,
    second: Path,
    paths: list[str],
) -> dict[str, Any]:
    comparisons = []
    for raw in paths:
        first_path = first / raw
        second_path = second / raw
        first_exists = first_path.is_file()
        second_exists = second_path.is_file()
        first_bytes = first_path.stat().st_size if first_exists else None
        second_bytes = second_path.stat().st_size if second_exists else None
        first_hash = sha256(first_path) if first_exists else None
        second_hash = sha256(second_path) if second_exists else None
        passed = (
            first_exists
            and second_exists
            and first_bytes == second_bytes
            and first_hash == second_hash
        )
        record = {
            "path": raw,
            "firstBytes": first_bytes,
            "secondBytes": second_bytes,
            "firstSha256": first_hash,
            "secondSha256": second_hash,
            "pass": passed,
        }
        comparisons.append(record)
        if not passed:
            raise PipelineFailure(
                "双运行确定性复现失败，首个差异："
                f"{raw}；bytes={first_bytes}/{second_bytes}；"
                f"sha256={first_hash}/{second_hash}"
            )
    return {
        "runCount": 2,
        "independentCleanDirectories": True,
        "comparedFileCount": len(comparisons),
        "matchedFileCount": len(comparisons),
        "comparisonFields": ["bytes", "sha256"],
        "reportVolatileFields": [],
        "temporaryPathsRecorded": False,
        "excludedFinalAggregateFiles": [
            "audit/V11-AUTOMATION-REPORT.zh-CN.md",
            "audit/v11-result.json",
        ],
        "exclusionReason": (
            "final aggregate reports are written after the comparison and contain "
            "no time or temporary-path fields"
        ),
        "firstDifference": None,
        "files": comparisons,
        "pass": True,
    }


def write_outputs(
    config: dict[str, Any],
    work: Path,
    freeze_before: dict[str, Any],
    prepared: dict[str, Any],
    samples: dict[str, Any],
    fk_report: dict[str, Any],
    motion_report: dict[str, Any],
    mesh_report: dict[str, Any],
    board_path: str,
) -> dict[str, Any]:
    sample_dir = work / "samples"
    audit_dir = work / "audit"
    sample_dir.mkdir()
    audit_dir.mkdir()
    sample_path = sample_dir / "fk-41-and-combination-extremes.json"
    sample_path.write_text(
        json.dumps(samples, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    freeze_after = freeze_snapshot(config)
    compare_snapshots(freeze_before, freeze_after)

    artifact_paths = [
        *(record["output"] for record in prepared["materials"]),
        prepared["psd"]["output"],
        "samples/fk-41-and-combination-extremes.json",
        board_path,
    ]
    artifacts = file_manifest(work, artifact_paths)
    result = {
        "schemaVersion": 1,
        "pipelineId": config["pipelineId"],
        "scriptVersion": SCRIPT_VERSION,
        "status": "pass",
        "scope": "single screen-right arm V11 automation prototype",
        "stages": {
            "frozenInputVerificationBefore": {
                "artifactCount": freeze_before["artifactCount"],
                "matchedArtifacts": freeze_before["matchedArtifacts"],
                "upstreamManifestCount": len(freeze_before["upstreamManifests"]),
                "pass": True,
            },
            "configuration": {"schemaVersion": config["schemaVersion"], "pass": True},
            "materialsAndPsd": {**prepared, "pass": True},
            "fkAndBoneLengths": fk_report,
            "seamsDetachmentAndReturn": motion_report,
            "mesh": mesh_report,
            "review": {"board": board_path, "pass": True},
            "frozenInputVerificationAfter": {
                "artifactCount": freeze_after["artifactCount"],
                "matchedArtifacts": freeze_after["matchedArtifacts"],
                "unchangedDuringRun": True,
                "pass": True,
            },
        },
        "artifacts": artifacts,
        "claims": {
            "automationReviewTool": True,
            "completeAssetGenerator": False,
            "engineeringAutomationPrototype": True,
            "v10FrozenFilesModified": False,
            "formalTexture": False,
            "fullCharacter": False,
            "physics": False,
            "runtime": False,
            "platformCodeChanged": False,
            "freshCubismGuiExecution": False,
            "freshCmo3MeshExtraction": False,
        },
    }
    result_path = audit_dir / "v11-result.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    mins = motion_report["minimumOverlapPixels"]
    report = f"""# 小星单臂 V11 自动化审查报告

## 结论

统一入口已按依赖顺序完成，机器结果为 `pass`。V10 冻结清单在运行前后均为
`{freeze_before["matchedArtifacts"]}/{freeze_before["artifactCount"]}` 一致，运行期间未变化。

## 本次实际执行

- 读取一份统一配置，确定性准备 4 个 `{config["canvas"][0]}×{config["canvas"][1]}` 全画布材料。
- 按哈希锁定的 V10 Cubism 导入 PSD 做字节级确定性复制，没有缩放、平移或重采样。
- 独立重算 41 个 `0→1→0` FK 样本与 6 个组合极值；最大骨长误差为
  `{max(fk_report["maximumL1ErrorPx"], fk_report["maximumL2ErrorPx"]):.12f}px`。
- 对 47 个姿态的实际材料 alpha 变换做检查。袖口—上臂、上臂—前臂、前臂—手的
  最小重叠像素分别为 `{mins["sleeveUpper"]}`、`{mins["upperForearm"]}`、
  `{mins["forearmHand"]}`；接缝失败 `0`，断开失败 `0`。
- 回程渲染差异像素为 `{motion_report["returnChangedPixels"]}`。
- 复核 4 个哈希锁定的 V10 数值网格记录：三角形计数关系成立，退化、翻折和越界均为 `0`。

## 最少审查入口

- `qa/v11-minimal-review-board.png`
- `audit/v11-result.json`

## 边界

本结果证明自动化原型可重复执行，不重新声明正式纹理、完整角色、Physics、Runtime
或平台接入。网格阶段复核的是冻结且哈希受保护的 V10 数值记录，不宣称本轮重新解析
了专有 CMO3 顶点，也不宣称本轮重新操作了 Cubism GUI。
"""
    (audit_dir / "V11-AUTOMATION-REPORT.zh-CN.md").write_text(
        report,
        encoding="utf-8",
    )
    return result


def run_once(
    config: dict[str, Any],
    work: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    reset_directory(work)
    before = freeze_snapshot(config)
    prepared = prepare_inputs(config, work)
    samples, skeleton, _contract = build_samples(config)
    fk_report = validate_fk(config, samples)
    motion_report, review_images = validate_material_motion(
        config, samples, skeleton, work
    )
    mesh_report = validate_mesh(config)
    board_path = build_review_board(review_images, work)
    result = write_outputs(
        config,
        work,
        before,
        prepared,
        samples,
        fk_report,
        motion_report,
        mesh_report,
        board_path,
    )
    return result, before


def atomic_write_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def finalize_candidate_results(
    work: Path,
    comparison: dict[str, Any],
    frozen_before_publish: dict[str, Any],
) -> dict[str, Any]:
    result_path = work / "audit/v11-result.json"
    report_path = work / "audit/V11-AUTOMATION-REPORT.zh-CN.md"
    result = read_json(result_path)
    result["stages"]["dualRunDeterminism"] = comparison
    result["stages"]["publication"] = {
        "afterDualRunPass": True,
        "method": "transactional_directory_swap_with_rollback",
        "candidateFinalizedBeforePublish": True,
        "candidateValidatedBeforeAndAfterSwap": True,
        "publishedOutputModifiedAfterSwap": False,
        "outcomeReportedByProcessExitCode": True,
    }
    result["stages"]["frozenInputVerificationBeforePublish"] = {
        "artifactCount": frozen_before_publish["artifactCount"],
        "matchedArtifacts": frozen_before_publish["matchedArtifacts"],
        "unchangedBeforeTransactionalPublish": True,
        "pass": True,
    }
    result["claims"]["automationReviewTool"] = True
    result["claims"]["completeAssetGenerator"] = False
    atomic_write_text(
        result_path,
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
    )

    report = report_path.read_text(encoding="utf-8")
    report += f"""

## 双运行确定性复现

- 同一流程在两个互相独立、运行前均清空的临时目录中完整执行。
- 直接比较 `{comparison["comparedFileCount"]}` 个确定性文件的字节数和 SHA-256；
  一致 `{comparison["matchedFileCount"]}/{comparison["comparedFileCount"]}`，首个差异：无。
- 比较范围包括 4 个材料、Cubism 导入 PSD、FK 样本和审查图。
- 最终机器结果和中文报告在比较通过后汇总生成，不参与自引用比较；其中不写入时间
  或临时路径字段。
- 候选结果和报告先在临时目录中完整写入并校验，随后才发布 `output/`。
- 发布采用带旧输出回滚保护的事务式目录切换；成功切换后不再写入 `output/`。
- 发布前 V10 冻结工件再次核对为
  `{frozen_before_publish["matchedArtifacts"]}/{frozen_before_publish["artifactCount"]}`；
  目录切换事务内还会再次核对，发布成功以进程退出码 `0` 为准。

本工具是冻结输入上的自动复核与确定性复现工具，不是完整素材生成器。它不会重新
绘制纹理、生成另一侧手臂、创建 Physics、执行 Runtime 或修改平台。
"""
    atomic_write_text(report_path, report)
    return result


def verify_candidate_output(
    work: Path,
    comparison: dict[str, Any],
) -> None:
    result_path = work / "audit/v11-result.json"
    report_path = work / "audit/V11-AUTOMATION-REPORT.zh-CN.md"
    result = read_json(result_path)
    if result.get("status") != "pass":
        raise PipelineFailure("候选机器结果不是 pass")
    if result.get("stages", {}).get("dualRunDeterminism") != comparison:
        raise PipelineFailure("候选机器结果中的双运行比较记录不一致")
    publication = result.get("stages", {}).get("publication", {})
    if (
        publication.get("candidateFinalizedBeforePublish") is not True
        or publication.get("publishedOutputModifiedAfterSwap") is not False
    ):
        raise PipelineFailure("候选机器结果缺少发布事务边界声明")
    artifacts = result.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 7:
        raise PipelineFailure("候选确定性工件数不是 7")
    for record in artifacts:
        raw = record.get("path")
        if not isinstance(raw, str):
            raise PipelineFailure("候选工件路径无效")
        path = work / raw
        if (
            not path.is_file()
            or path.stat().st_size != int(record.get("bytes", -1))
            or sha256(path) != record.get("sha256")
        ):
            raise PipelineFailure(f"候选工件校验失败：{raw}")
    if not report_path.is_file() or not report_path.read_text(
        encoding="utf-8"
    ).strip():
        raise PipelineFailure("候选中文报告缺失或为空")


def run(config_path: Path, verify_only: bool) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("schemaVersion") != 1:
        raise PipelineFailure("不支持的配置版本")
    if verify_only:
        before = freeze_snapshot(config)
        after = freeze_snapshot(config)
        compare_snapshots(before, after)
        return {
            "schemaVersion": 1,
            "pipelineId": config["pipelineId"],
            "status": "pass",
            "mode": "verify-only",
            "matchedArtifacts": before["matchedArtifacts"],
            "artifactCount": before["artifactCount"],
            "unchangedDuringRun": True,
        }

    try:
        first_result, first_freeze = run_once(config, RUN_A)
        second_result, second_freeze = run_once(config, RUN_B)
        compare_snapshots(first_freeze, second_freeze)
        comparison = compare_runs(
            RUN_A,
            RUN_B,
            deterministic_paths(first_result),
        )
        frozen_before_publish = freeze_snapshot(config)
        compare_snapshots(first_freeze, frozen_before_publish)
        finalize_candidate_results(RUN_A, comparison, frozen_before_publish)
        verify_candidate_output(RUN_A, comparison)

        def validate_published(work: Path) -> None:
            verify_candidate_output(work, comparison)
            frozen_during_publish = freeze_snapshot(config)
            compare_snapshots(first_freeze, frozen_during_publish)

        publication = transactional_publish(RUN_A, validate_published)
        result = read_json(OUTPUT / "audit/v11-result.json")
        result["publicationOutcome"] = publication
        if RUN_B.exists():
            shutil.rmtree(RUN_B)
        return result
    except Exception:
        for work in (RUN_A, RUN_B):
            if work.exists():
                shutil.rmtree(work)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="小星 Live2D 单臂 V11 自动化原型"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="统一配置文件；默认使用 V11 目录内 config.json",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="仅验证 V10 冻结输入，不生成 V11 输出",
    )
    arguments = parser.parse_args()
    try:
        result = run(arguments.config.resolve(), arguments.verify_only)
    except (PipelineFailure, KeyError, TypeError, ValueError, OSError) as exc:
        print(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "status": "fail",
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
