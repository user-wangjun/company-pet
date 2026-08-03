from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
LAYER_CONTRACT = ROOT / "x5-generated-fine-layer-candidates-contract-v1.json"
MESH_CONTRACT = ROOT / "x5-generated-fine-mesh-contract-v1.json"
OUTPUT = ROOT / "x5-mesh-deformation-smoothness-audit-v1.json"
PREVIEW = ROOT / "qa" / "x5-mesh-deformation-smoothness-preview-v1.png"
ANGLES = (-15.0, -7.5, 7.5, 15.0)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf"), Path("C:/Windows/Fonts/arial.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def deform(points: np.ndarray, pivot: np.ndarray, weights: np.ndarray, resistance: np.ndarray, degrees: float) -> np.ndarray:
    relative = points - pivot
    base_angle = math.radians(degrees)
    # Soft vertices lag slightly behind the parent rotation. Resistance keeps
    # near-node vertices stable and lets distal material settle progressively.
    lag = 0.22 * weights * (1.0 - resistance)
    angles = base_angle * (1.0 - lag)
    cosines = np.cos(angles)
    sines = np.sin(angles)
    x = relative[:, 0] * cosines - relative[:, 1] * sines
    y = relative[:, 0] * sines + relative[:, 1] * cosines
    return np.column_stack((x, y)) + pivot


def signed_area(points: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    a = points[triangles[:, 0]]
    b = points[triangles[:, 1]]
    c = points[triangles[:, 2]]
    return 0.5 * ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]))


def edge_ratios(original: np.ndarray, changed: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    ratios = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        before = np.linalg.norm(original[triangles[:, a]] - original[triangles[:, b]], axis=1)
        after = np.linalg.norm(changed[triangles[:, a]] - changed[triangles[:, b]], axis=1)
        ratios.append(after / np.maximum(before, 1e-9))
    return np.concatenate(ratios)


def render_sample(layer: dict[str, object], mesh: dict[str, object], size: tuple[int, int]) -> Image.Image:
    points = np.asarray(mesh["points"], dtype=float)
    pivot = np.asarray(mesh["pivotPoint"], dtype=float)
    weights = np.asarray(mesh["vertexElasticWeights"], dtype=float)
    resistance = np.asarray(mesh["vertexResistanceDecay"], dtype=float)
    changed = deform(points, pivot, weights, resistance, 15.0)
    all_points = np.vstack((points, changed))
    minimum = all_points.min(axis=0)
    maximum = all_points.max(axis=0)
    span = np.maximum(maximum - minimum, 1.0)
    scale = min((size[0] - 48) / span[0], (size[1] - 58) / span[1])
    offset = np.asarray([(size[0] - span[0] * scale) / 2, (size[1] - span[1] * scale) / 2]) - minimum * scale
    original_screen = points * scale + offset
    changed_screen = changed * scale + offset
    pivot_screen = pivot * scale + offset
    image = Image.new("RGB", size, (250, 250, 247))
    draw = ImageDraw.Draw(image)
    triangles = mesh["triangles"]
    for triangle in triangles:
        draw.line([tuple(original_screen[index]) for index in (*triangle, triangle[0])], fill=(160, 165, 168), width=1)
    for triangle in triangles:
        draw.line([tuple(changed_screen[index]) for index in (*triangle, triangle[0])], fill=(20, 105, 215), width=2)
    x, y = pivot_screen
    draw.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(235, 67, 45), outline=(255, 255, 255), width=2)
    draw.text((10, size[1] - 26), f"{layer['id']}  灰=静止  蓝=+15°弹性滞后", font=font(13), fill=(45, 52, 57))
    return image


def main() -> None:
    layers = json.loads(LAYER_CONTRACT.read_text(encoding="utf-8"))["layers"]
    mesh_contract = json.loads(MESH_CONTRACT.read_text(encoding="utf-8"))["layers"]
    mesh_paths = {item["layerId"]: ROOT.parent.parent / item["meshFile"] for item in mesh_contract}
    layer_by_id = {item["id"]: item for item in layers}
    results = []
    meshes = {}
    for layer in layers:
        mesh = json.loads(mesh_paths[layer["id"]].read_text(encoding="utf-8"))
        meshes[layer["id"]] = mesh
        points = np.asarray(mesh["points"], dtype=float)
        triangles = np.asarray(mesh["triangles"], dtype=int)
        pivot = np.asarray(mesh["pivotPoint"], dtype=float)
        weights = np.asarray(mesh["vertexElasticWeights"], dtype=float)
        resistance = np.asarray(mesh["vertexResistanceDecay"], dtype=float)
        original_areas = signed_area(points, triangles)
        valid = np.abs(original_areas) > 1e-8
        layer_flips = 0
        minimum_area_ratio = 1.0
        maximum_area_ratio = 1.0
        minimum_edge_ratio = 1.0
        maximum_edge_ratio = 1.0
        for degrees in ANGLES:
            changed = deform(points, pivot, weights, resistance, degrees)
            changed_areas = signed_area(changed, triangles)
            layer_flips += int(np.sum(original_areas[valid] * changed_areas[valid] <= 0.0))
            area_ratios = np.abs(changed_areas[valid]) / np.maximum(np.abs(original_areas[valid]), 1e-9)
            ratios = edge_ratios(points, changed, triangles)
            minimum_area_ratio = min(minimum_area_ratio, float(area_ratios.min()))
            maximum_area_ratio = max(maximum_area_ratio, float(area_ratios.max()))
            minimum_edge_ratio = min(minimum_edge_ratio, float(ratios.min()))
            maximum_edge_ratio = max(maximum_edge_ratio, float(ratios.max()))
        passes = layer_flips == 0 and minimum_area_ratio >= 0.80 and maximum_area_ratio <= 1.20 and minimum_edge_ratio >= 0.90 and maximum_edge_ratio <= 1.10
        results.append({
            "layerId": layer["id"],
            "triangleFlips": layer_flips,
            "minimumAreaRatio": round(minimum_area_ratio, 6),
            "maximumAreaRatio": round(maximum_area_ratio, 6),
            "minimumEdgeLengthRatio": round(minimum_edge_ratio, 6),
            "maximumEdgeLengthRatio": round(maximum_edge_ratio, 6),
            "passes": passes,
        })
    audit = {
        "schemaVersion": 1,
        "stage": "X5-mesh-deformation-smoothness-audit",
        "status": "candidate-for-user-review",
        "test": {
            "parentRotationDegrees": list(ANGLES),
            "elasticLag": "22% of vertexElasticWeight multiplied by inverse resistance decay",
            "thresholds": {"triangleFlips": 0, "areaRatio": [0.80, 1.20], "edgeLengthRatio": [0.90, 1.10]},
            "boundary": "topology stress test only; no X6 parameters, keyforms, motion curves, or Action Tracer",
        },
        "counts": {"layers": len(results), "passing": sum(item["passes"] for item in results), "failing": sum(not item["passes"] for item in results)},
        "global": {
            "triangleFlips": sum(item["triangleFlips"] for item in results),
            "minimumAreaRatio": min(item["minimumAreaRatio"] for item in results),
            "maximumAreaRatio": max(item["maximumAreaRatio"] for item in results),
            "minimumEdgeLengthRatio": min(item["minimumEdgeLengthRatio"] for item in results),
            "maximumEdgeLengthRatio": max(item["maximumEdgeLengthRatio"] for item in results),
        },
        "layers": sorted(results, key=lambda item: (item["passes"], item["minimumAreaRatio"])),
        "qa": {"preview": "live2d/x5/qa/x5-mesh-deformation-smoothness-preview-v1.png"},
        "gateBoundary": {"currentGate": "x5-layer-mesh-node-torque", "gate5Approved": False, "x6Authorized": False},
    }
    OUTPUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    sample_ids = ["upper_lid_L", "ear_tip_L", "forearm_L", "tail_tip_long"]
    sheet = Image.new("RGB", (1440, 720), (249, 249, 246))
    draw = ImageDraw.Draw(sheet)
    draw.rounded_rectangle([20, 16, 1420, 104], radius=8, fill=(255, 252, 246), outline=(120, 135, 120), width=2)
    draw.text((42, 28), "X5 降密网格小角度变形流畅性应力测试", font=font(27), fill=(34, 38, 44))
    draw.text((42, 67), "灰=静止网格，蓝=父节点 +15° 与弹性滞后；检查翻面、面积突变和骨段式拉伸。", font=font(16), fill=(92, 76, 56))
    for index, layer_id in enumerate(sample_ids):
        card = render_sample(layer_by_id[layer_id], meshes[layer_id], (336, 500))
        sheet.paste(card, (24 + index * 354, 126))
    summary = audit["global"]
    draw.text((30, 650), f"63 层通过 {audit['counts']['passing']} / 翻面 {summary['triangleFlips']} / 面积比 {summary['minimumAreaRatio']:.4f}-{summary['maximumAreaRatio']:.4f} / 边长比 {summary['minimumEdgeLengthRatio']:.4f}-{summary['maximumEdgeLengthRatio']:.4f}", font=font(17), fill=(40, 64, 54))
    draw.text((30, 684), "门禁：仅 X5 拓扑应力测试；gate5Approved=false，x6Authorized=false。", font=font(14), fill=(156, 62, 47))
    sheet.save(PREVIEW)
    print(json.dumps({"counts": audit["counts"], "global": audit["global"]}, ensure_ascii=False, indent=2))
    print(PREVIEW.as_posix())


if __name__ == "__main__":
    main()
