from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import triangle as triangle_lib
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import binary_erosion
from scipy.spatial import Delaunay
from skimage.measure import approximate_polygon, find_contours


ROOT = Path(__file__).resolve().parent
LAYER_CONTRACT = ROOT / "x5-generated-fine-layer-candidates-contract-v1.json"
MESH_DIR = ROOT / "generated-fine-mesh-candidates-v1"
MESH_CONTRACT = ROOT / "x5-generated-fine-mesh-contract-v1.json"
PREVIEW = ROOT / "qa" / "x5-generated-fine-layer-triangulation-atlas-v1.png"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def checker(size: tuple[int, int], block: int = 8) -> Image.Image:
    image = Image.new("RGB", size, (245, 245, 245))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle([x, y, x + block - 1, y + block - 1], fill=(226, 226, 226))
    return image


def pivot_guess(layer_id: str, mask: np.ndarray) -> tuple[float, float]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return 0.0, 0.0
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    if layer_id.startswith("ear_"):
        guess = ((x0 + x1) / 2, y1 - 2)
    elif layer_id.startswith("whisker_L"):
        guess = (x1 - 2, (y0 + y1) / 2)
    elif layer_id.startswith("whisker_R"):
        guess = (x0 + 2, (y0 + y1) / 2)
    elif any(token in layer_id for token in ("arm", "forearm", "paw", "thigh", "shin", "leg", "tail_")):
        guess = ((x0 + x1) / 2, y0 + 2)
    else:
        guess = ((x0 + x1) / 2, (y0 + y1) / 2)
    gx, gy = int(round(guess[0])), int(round(guess[1]))
    if 0 <= gy < mask.shape[0] and 0 <= gx < mask.shape[1] and mask[gy, gx]:
        return float(gx), float(gy)
    distances = (xs - gx) ** 2 + (ys - gy) ** 2
    nearest = int(np.argmin(distances))
    return float(xs[nearest]), float(ys[nearest])


def elastic_range(value: str) -> tuple[float, float]:
    lower = value.lower()
    if lower == "none":
        return 0.0, 0.0
    if any(token in lower for token in ("high", "tip", "fur lag", "sleeve", "soft thigh")):
        return 0.12, 0.78
    if any(token in lower for token in ("medium", "breath", "settle", "soft")):
        return 0.08, 0.52
    if any(token in lower for token in ("active", "gaze", "blink")):
        return 0.02, 0.18
    return 0.0, 0.12


def build_points(mask: np.ndarray, dense: bool, pivot: tuple[float, float]) -> np.ndarray:
    boundary = mask & ~binary_erosion(mask)
    by, bx = np.nonzero(boundary)
    spacing = 12 if dense else 19
    interior: list[tuple[int, int]] = []
    for y in range(spacing // 2, mask.shape[0], spacing):
        for x in range(spacing // 2, mask.shape[1], spacing):
            if mask[y, x]:
                interior.append((x, y))
    candidates = [(int(x), int(y)) for x, y in zip(bx, by)] + interior
    minimum_distance = 5.5 if dense else 8.0
    accepted: list[tuple[float, float]] = []
    min_distance_sq = minimum_distance * minimum_distance
    for point in candidates:
        if all((point[0] - other[0]) ** 2 + (point[1] - other[1]) ** 2 >= min_distance_sq for other in accepted):
            accepted.append((float(point[0]), float(point[1])))
    pivot_point = (float(pivot[0]), float(pivot[1]))
    accepted = [point for point in accepted if (point[0] - pivot_point[0]) ** 2 + (point[1] - pivot_point[1]) ** 2 >= (minimum_distance * 0.6) ** 2]
    accepted.append(pivot_point)
    return np.unique(np.asarray(accepted, dtype=np.float64), axis=0)


def triangle_inside(mask: np.ndarray, tri: np.ndarray) -> bool:
    # The constrained triangulator already clips triangle edges to the alpha
    # contour. Requiring edge midpoints to hit a discrete opaque pixel removes
    # valid boundary triangles on one-to-three-pixel eyelids and whiskers.
    x, y = tri.mean(axis=0)
    ix = min(mask.shape[1] - 1, max(0, int(round(x))))
    iy = min(mask.shape[0] - 1, max(0, int(round(y))))
    return bool(mask[iy, ix])


def action_deformation_profile(layer: dict[str, object], alpha_pixels: int) -> tuple[str, str]:
    layer_id = str(layer["id"])
    elastic = str(layer["elastic"]).lower()
    zone = str(layer["meshDensityZone"]).lower()
    if alpha_pixels < 1000:
        return "micro-feature-local", "micro-coarse"
    if layer_id.startswith("ear_face") or layer_id.startswith("ear_tip"):
        return "ear-hinge-local", "hinge-coarse"
    if "muzzle" in layer_id:
        return "face-feature-local", "feature-coarse"
    if elastic == "none" and alpha_pixels > 5000:
        return "parent-transform-rigid-surface", "inherited-rigid-sparse"
    if any(token in layer_id for token in ("eye_socket", "iris", "pupil", "lid")):
        return "face-feature-local", "feature-coarse"
    if elastic != "none" or "dense" in zone or "curve" in zone:
        return "secondary-soft-local", "soft-medium"
    return "local-surface", "regular-coarse"


def constrained_quality_mesh(mask: np.ndarray, density_profile: str, pivot: tuple[float, float]) -> tuple[np.ndarray, list[list[int]]]:
    # Padding closes components that touch a cropped layer edge. Without it,
    # find_contours returns open fragments and the resulting PSLG only meshes
    # thin interior islands instead of the complete opaque material region.
    padded_mask = np.pad(mask, 1, mode="constant", constant_values=False)
    contours = find_contours(padded_mask.astype(np.uint8), 0.5)
    all_points: list[list[float]] = []
    all_triangles: list[list[int]] = []
    # Keep deformation zones denser while allowing large rigid material areas
    # to use broader triangles. This reduces runtime work without flattening
    # eyelids, fur rims, joints, or tail curves.
    if density_profile == "micro-coarse":
        tolerance = 1.8
        max_area = 220.0
    elif density_profile == "inherited-rigid-sparse":
        tolerance = 7.5
        max_area = 1800.0
    elif density_profile == "hinge-coarse":
        tolerance = 4.75
        max_area = 900.0
    elif density_profile == "feature-coarse":
        tolerance = 3.5
        max_area = 620.0
    elif density_profile == "soft-medium":
        tolerance = 2.4
        max_area = 320.0
    else:
        tolerance = 4.25
        max_area = 760.0
    for contour in contours:
        simplified = approximate_polygon(contour, tolerance=tolerance)
        vertices = np.asarray([[float(point[1] - 1), float(point[0] - 1)] for point in simplified], dtype=np.float64)
        if len(vertices) > 1 and np.linalg.norm(vertices[0] - vertices[-1]) < 1e-6:
            vertices = vertices[:-1]
        if len(vertices) < 3:
            continue
        segments = np.asarray([[index, (index + 1) % len(vertices)] for index in range(len(vertices))], dtype=np.int32)
        result = triangle_lib.triangulate(
            {"vertices": vertices, "segments": segments},
            f"pq20a{max_area}Q",
        )
        if "triangles" not in result or "vertices" not in result:
            continue
        component_points = np.asarray(result["vertices"], dtype=np.float64)
        component_triangles = []
        for simplex in result["triangles"]:
            triangle_points = component_points[np.asarray(simplex)]
            if triangle_inside(mask, triangle_points):
                component_triangles.append([int(value) for value in simplex])
        if not component_triangles:
            continue
        offset = len(all_points)
        all_points.extend(component_points.tolist())
        all_triangles.extend([[a + offset, b + offset, c + offset] for a, b, c in component_triangles])
    if all_triangles:
        return np.asarray(all_points, dtype=np.float64), all_triangles
    points = build_points(mask, density_profile in ("soft-medium", "feature-coarse"), pivot)
    delaunay = Delaunay(points)
    triangles = [simplex.tolist() for simplex in delaunay.simplices if triangle_inside(mask, points[simplex])]
    return points, triangles


def min_angle_degrees(tri: np.ndarray) -> float:
    lengths = [np.linalg.norm(tri[(i + 1) % 3] - tri[(i + 2) % 3]) for i in range(3)]
    angles = []
    for i in range(3):
        a, b, c = lengths[i], lengths[(i + 1) % 3], lengths[(i + 2) % 3]
        denominator = max(1e-9, 2 * b * c)
        cosine = np.clip((b * b + c * c - a * a) / denominator, -1.0, 1.0)
        angles.append(math.degrees(math.acos(cosine)))
    return float(min(angles))


def render_card(image: Image.Image, mesh: dict[str, object], size: tuple[int, int]) -> Image.Image:
    bg = checker(size).convert("RGBA")
    scale = min((size[0] - 18) / image.width, (size[1] - 18) / image.height, 1.0)
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    ox, oy = (size[0] - resized.width) // 2, (size[1] - resized.height) // 2
    bg.alpha_composite(resized, (ox, oy))
    draw = ImageDraw.Draw(bg, "RGBA")
    points = [(ox + p[0] * scale, oy + p[1] * scale) for p in mesh["points"]]
    for a, b, c in mesh["triangles"]:
        draw.line([points[a], points[b], points[c], points[a]], fill=(22, 106, 220, 175), width=1)
    elastic_candidates = sorted(
        (index for index, weight in enumerate(mesh["vertexElasticWeights"]) if weight >= 0.45),
        key=lambda index: mesh["vertexElasticWeights"][index],
        reverse=True,
    )
    representative_elastic = set(elastic_candidates[:3])
    for index, point in enumerate(points):
        weight = mesh["vertexElasticWeights"][index]
        color = (24, 155, 94, 235) if index in representative_elastic else (22, 106, 220, 175)
        radius = 3 if index in representative_elastic else 1
        draw.ellipse([point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius], fill=color)
    pivot = mesh["pivotPoint"]
    px, py = ox + pivot[0] * scale, oy + pivot[1] * scale
    draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=(238, 70, 48, 245), outline=(255, 255, 255, 245), width=2)
    return bg.convert("RGB")


def main() -> None:
    MESH_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    layer_contract = json.loads(LAYER_CONTRACT.read_text(encoding="utf-8"))
    summaries: list[dict[str, object]] = []
    mesh_payloads: list[tuple[dict[str, object], Image.Image, dict[str, object]]] = []
    for layer in layer_contract["layers"]:
        path = ROOT.parent.parent / layer["file"]
        image = Image.open(path).convert("RGBA")
        alpha = np.asarray(image.getchannel("A"))
        mask = alpha > 24
        pivot = pivot_guess(layer["id"], mask)
        deformation_role, density_profile = action_deformation_profile(layer, int(mask.sum()))
        points, triangles = constrained_quality_mesh(mask, density_profile, pivot)
        if len(points) < 3:
            continue
        low, high = elastic_range(layer["elastic"])
        distances = np.linalg.norm(points - np.asarray(pivot), axis=1)
        max_distance = max(float(distances.max()), 1.0)
        weights = (low + (high - low) * (distances / max_distance)).clip(0.0, 1.0)
        pivot_index = int(np.argmin(distances))
        weights[pivot_index] = 0.0
        if high == 0.0:
            resistance_decay = np.ones_like(distances)
        else:
            normalized_distance = (distances / max_distance).clip(0.0, 1.0)
            resistance_decay = 1.0 - 0.65 * normalized_distance
            resistance_decay[pivot_index] = 1.0
        angles = [min_angle_degrees(points[np.asarray(tri)]) for tri in triangles]
        payload = {
            "schemaVersion": 1,
            "layerId": layer["id"],
            "sourceLayer": layer["file"],
            "primaryController": layer["primaryController"],
            "parent": layer["parent"],
            "actionSubject": layer["primaryController"],
            "deformationRole": deformation_role,
            "densityProfile": density_profile,
            "pivotName": layer["pivot"],
            "pivotPoint": [round(v, 3) for v in pivot],
            "points": [[round(float(x), 3), round(float(y), 3)] for x, y in points],
            "triangles": triangles,
            "vertexElasticWeights": [round(float(value), 4) for value in weights],
            "vertexResistanceDecay": [round(float(value), 4) for value in resistance_decay],
            "springRelation": {
                "model": "tau = k(targetAngle-angle) - c*angularVelocity",
                "stiffnessRange": [round(0.92 - high * 0.42, 3), round(0.92 - low * 0.42, 3)],
                "dampingRangeNearToFar": [0.72, round(0.72 - high * 0.28, 3)],
                "resistanceDecayNearToFar": [1.0, 1.0 if high == 0.0 else 0.35],
                "anatomicalPivotWeight": 0.0,
            },
            "quality": {
                "pointCount": len(points),
                "triangleCount": len(triangles),
                "minimumTriangleAngleDegrees": round(min(angles), 3) if angles else 0.0,
                "medianTriangleAngleDegrees": round(float(np.median(angles)), 3) if angles else 0.0,
            },
            "candidateOnly": True,
        }
        mesh_name = Path(layer["file"]).stem + ".mesh.json"
        (MESH_DIR / mesh_name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        summary = {
            "layerId": layer["id"],
            "view": layer["view"],
            "meshFile": f"live2d/x5/generated-fine-mesh-candidates-v1/{mesh_name}",
            "primaryController": layer["primaryController"],
            "actionSubject": layer["primaryController"],
            "deformationRole": deformation_role,
            "densityProfile": density_profile,
            "pivot": layer["pivot"],
            "pointCount": len(points),
            "triangleCount": len(triangles),
            "minimumTriangleAngleDegrees": payload["quality"]["minimumTriangleAngleDegrees"],
            "elasticRange": [round(low, 3), round(high, 3)],
        }
        summaries.append(summary)
        mesh_payloads.append((layer, image, payload))

    cols, cell_w, cell_h = 6, 244, 190
    rows = math.ceil(len(mesh_payloads) / cols)
    sheet = Image.new("RGB", (cols * cell_w + 40, rows * cell_h + 126), (250, 250, 247))
    draw = ImageDraw.Draw(sheet)
    draw.rounded_rectangle([20, 16, sheet.width - 20, 96], radius=8, fill=(255, 252, 246), outline=(120, 135, 120), width=2)
    draw.text((44, 28), f"X5 精细分层三角剖分 / 主节点 / 弹性顶点 ({len(mesh_payloads)} layers)", font=font(27), fill=(34, 38, 44))
    draw.text((44, 64), "蓝=三角网格，红=每层唯一主支点，绿=每层最多 3 个代表性高弹性顶点；骨性支点权重固定为 0。", font=font(16), fill=(112, 82, 54))
    for i, (layer, image, mesh) in enumerate(mesh_payloads):
        col, row = i % cols, i // cols
        x, y = 20 + col * cell_w, 112 + row * cell_h
        draw.rounded_rectangle([x + 5, y + 4, x + cell_w - 6, y + cell_h - 8], radius=5, fill=(255, 255, 255), outline=(176, 176, 160))
        card = render_card(image, mesh, (cell_w - 24, 128))
        sheet.paste(card, (x + 12, y + 10))
        draw.text((x + 12, y + 142), f"{layer['view']}:{layer['id']}"[:31], font=font(12), fill=(38, 45, 52))
        draw.text((x + 12, y + 161), f"V{len(mesh['points'])} / T{len(mesh['triangles'])} -> {layer['primaryController']}"[:34], font=font(10), fill=(92, 88, 78))
    sheet.save(PREVIEW)

    total_points = sum(item["pointCount"] for item in summaries)
    total_triangles = sum(item["triangleCount"] for item in summaries)
    contract = {
        "schemaVersion": 1,
        "stage": "X5-generated-fine-layer-triangulation-node-elastic",
        "status": "candidate-for-user-review",
        "revision": "generated-fine-mesh-v7-action-subject-driven",
        "sourceLayerContract": "live2d/x5/x5-generated-fine-layer-candidates-contract-v1.json",
        "method": "quality-constrained triangulation of padded closed alpha contours; triangle material membership is checked at the centroid so valid thin boundary triangles are retained",
        "counts": {"layers": len(summaries), "points": total_points, "triangles": total_triangles},
        "rules": [
            "one primary controller and one red anatomical/material pivot per semantic layer",
            "helper points remain mesh vertices and do not become extra bone segments",
            "triangle density is concentrated at deformation zones; broad rigid areas use fewer larger triangles for smoother runtime evaluation",
            "broad rigid layers use a separate sparse density budget because their actions are inherited from parent transforms instead of requiring dense local control",
            "small ears, eyelids, eyes, and rigid face pieces follow the article-style coarse contour-plus-center topology instead of photo-tracing every texture detail",
            "density is selected from each layer's action subject and deformation role, not from texture or silhouette complexity alone",
            "anatomical pivot elastic weight is zero",
            "elastic weights increase away from the pivot only for approved soft materials",
            "layers marked none keep every elastic coefficient at zero",
            "resistance decay weakens monotonically away from the layer node for approved soft materials",
            "active joint motion remains separate from secondary spring-damper response",
        ],
        "gateBoundary": {"currentGate": "x5-layer-mesh-node-torque", "gate5Approved": False, "x6Authorized": False},
        "qa": {
            "triangulationAtlas": "live2d/x5/qa/x5-generated-fine-layer-triangulation-atlas-v1.png",
            "alphaCoverageAudit": "live2d/x5/x5-mesh-alpha-coverage-audit-v1.json",
        },
        "layers": summaries,
    }
    MESH_CONTRACT.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    print(PREVIEW.as_posix())
    print(MESH_CONTRACT.as_posix())
    print(json.dumps(contract["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
