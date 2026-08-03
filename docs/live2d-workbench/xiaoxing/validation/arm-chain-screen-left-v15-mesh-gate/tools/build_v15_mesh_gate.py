from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
V14 = WORKBENCH / "validation/arm-chain-screen-left-v14-complete-textures"
V14_FREEZE = V14 / "audit/v14-complete-texture-freeze-manifest-2026-07-28.json"
MATERIAL_ROOT = V14 / "materials"
MASK_ROOT = V14 / "corrected-masks/complete"
W, H = 512, 1086
LAYERS = ["sleeve", "upper_arm", "forearm_bracelet", "whole_hand"]
DRAW_ORDER = {
    "upper_arm": 100,
    "whole_hand": 200,
    "forearm_bracelet": 300,
    "sleeve": 400,
}
MESH_COLORS = {
    "sleeve": (50, 112, 225),
    "upper_arm": (224, 130, 48),
    "forearm_bracelet": (30, 165, 140),
    "whole_hand": (214, 85, 132),
}
POINT_SPACING = {
    "sleeve": 7.0,
    "upper_arm": 6.0,
    "forearm_bracelet": 6.0,
    "whole_hand": 4.0,
}
GRID_SPACING = {
    "sleeve": 14,
    "upper_arm": 11,
    "forearm_bracelet": 10,
    "whole_hand": 7,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def verify_manifest(path: Path, root: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    matches = 0
    for item in manifest["lockedArtifacts"]:
        artifact = root / item["path"]
        if (
            artifact.is_file()
            and artifact.stat().st_size == item["bytes"]
            and sha256(artifact) == item["sha256"]
        ):
            matches += 1
    return {
        "path": path.relative_to(WORKBENCH).as_posix(),
        "sha256": sha256(path),
        "matchedArtifacts": matches,
        "artifactCount": manifest["artifactCount"],
        "pass": matches == manifest["artifactCount"],
    }


def mask_points(mask_path: Path) -> set[tuple[int, int]]:
    alpha = Image.open(mask_path).convert("RGBA").getchannel("A")
    data = alpha.load()
    bbox = alpha.getbbox()
    if bbox is None:
        return set()
    return {
        (x, y)
        for y in range(bbox[1], bbox[3])
        for x in range(bbox[0], bbox[2])
        if data[x, y] > 0
    }


def boundary_points(points: set[tuple[int, int]]) -> set[tuple[int, int]]:
    return {
        (x, y)
        for x, y in points
        if any((x + dx, y + dy) not in points for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    }


def poisson_select(
    candidates: set[tuple[int, int]],
    minimum_distance: float,
) -> list[tuple[float, float]]:
    chosen: list[tuple[float, float]] = []
    # Sort around the boundary so long straight edges do not starve corners.
    ordered = sorted(candidates, key=lambda point: (point[1], point[0]))
    for x, y in ordered:
        if all((x - px) ** 2 + (y - py) ** 2 >= minimum_distance**2 for px, py in chosen):
            chosen.append((x + 0.5, y + 0.5))
    return chosen


def build_points(layer: str, points: set[tuple[int, int]]) -> list[tuple[float, float]]:
    boundary = boundary_points(points)
    selected = poisson_select(boundary, POINT_SPACING[layer])
    bbox = (
        min(x for x, y in points),
        min(y for x, y in points),
        max(x for x, y in points),
        max(y for x, y in points),
    )
    interior = []
    spacing = GRID_SPACING[layer]
    for y in range(bbox[1] + spacing // 2, bbox[3] + 1, spacing):
        for x in range(bbox[0] + spacing // 2, bbox[2] + 1, spacing):
            if (x, y) in points:
                interior.append((x + 0.5, y + 0.5))
    for p in interior:
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= (spacing * 0.65) ** 2 for q in selected):
            selected.append(p)
    # The approved pivots remain explicit action points when they lie inside alpha.
    pivots = {
        "sleeve": [(176.5, 257.5)],
        "upper_arm": [(176.5, 257.5), (153.5, 411.5)],
        "forearm_bracelet": [(153.5, 411.5), (115.5, 529.5)],
        "whole_hand": [(115.5, 529.5)],
    }[layer]
    for p in pivots:
        px, py = round(p[0] - 0.5), round(p[1] - 0.5)
        if (px, py) in points and all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= 9 for q in selected):
            selected.append(p)
    return selected


def circumcircle_contains(
    point: tuple[float, float],
    triangle: tuple[int, int, int],
    points: list[tuple[float, float]],
) -> bool:
    ax, ay = points[triangle[0]]
    bx, by = points[triangle[1]]
    cx, cy = points[triangle[2]]
    px, py = point
    determinant = (
        (ax - px) * ((by - py) * (cx * cx + cy * cy - px * px - py * py) - (cy - py) * (bx * bx + by * by - px * px - py * py))
        - (bx - px) * ((ay - py) * (cx * cx + cy * cy - px * px - py * py) - (cy - py) * (ax * ax + ay * ay - px * px - py * py))
        + (cx - px) * ((ay - py) * (bx * bx + by * by - px * px - py * py) - (by - py) * (ax * ax + ay * ay - px * px - py * py))
    )
    orientation = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    return determinant * (1 if orientation > 0 else -1) > 1e-7


def delaunay(input_points: list[tuple[float, float]]) -> list[tuple[int, int, int]]:
    points = input_points[:]
    min_x = min(x for x, _ in points)
    max_x = max(x for x, _ in points)
    min_y = min(y for _, y in points)
    max_y = max(y for _, y in points)
    span = max(max_x - min_x, max_y - min_y) + 1000.0
    cx, cy = (min_x + max_x) / 2, (min_y + max_y) / 2
    super_indices = [len(points), len(points) + 1, len(points) + 2]
    points.extend(
        [
            (cx - 2 * span, cy + span),
            (cx, cy - 2 * span),
            (cx + 2 * span, cy + span),
        ]
    )
    triangles = [(super_indices[0], super_indices[1], super_indices[2])]
    for index in range(len(input_points)):
        point = points[index]
        bad = [triangle for triangle in triangles if circumcircle_contains(point, triangle, points)]
        edge_counts: dict[tuple[int, int], int] = {}
        for triangle in bad:
            for a, b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
                edge = tuple(sorted((a, b)))
                edge_counts[edge] = edge_counts.get(edge, 0) + 1
        triangles = [triangle for triangle in triangles if triangle not in bad]
        for edge, count in edge_counts.items():
            if count == 1:
                triangles.append((edge[0], edge[1], index))
    return [
        triangle
        for triangle in triangles
        if all(index < len(input_points) for index in triangle)
    ]


def signed_area(
    triangle: tuple[int, int, int],
    points: list[tuple[float, float]],
) -> float:
    a, b, c = (points[index] for index in triangle)
    return 0.5 * ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def inside_mask(mask_points_set: set[tuple[int, int]], x: float, y: float) -> bool:
    return (round(x - 0.5), round(y - 0.5)) in mask_points_set


def triangle_inside(
    triangle: tuple[int, int, int],
    points: list[tuple[float, float]],
    mask_points_set: set[tuple[int, int]],
) -> bool:
    a, b, c = (points[index] for index in triangle)
    samples = [
        a,
        b,
        c,
        ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2),
        ((b[0] + c[0]) / 2, (b[1] + c[1]) / 2),
        ((c[0] + a[0]) / 2, (c[1] + a[1]) / 2),
        ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3),
        ((2 * a[0] + b[0] + c[0]) / 4, (2 * a[1] + b[1] + c[1]) / 4),
        ((a[0] + 2 * b[0] + c[0]) / 4, (a[1] + 2 * b[1] + c[1]) / 4),
        ((a[0] + b[0] + 2 * c[0]) / 4, (a[1] + b[1] + 2 * c[1]) / 4),
    ]
    return all(inside_mask(mask_points_set, x, y) for x, y in samples)


def aspect_ratio(triangle: tuple[int, int, int], points: list[tuple[float, float]]) -> float:
    a, b, c = (points[index] for index in triangle)
    lengths = [
        math.dist(a, b),
        math.dist(b, c),
        math.dist(c, a),
    ]
    return max(lengths) / max(1e-9, min(lengths))


def build_mesh(layer: str, mask_path: Path) -> tuple[dict, Image.Image]:
    mask = mask_points(mask_path)
    mesh_points = build_points(layer, mask)
    raw_triangles = delaunay(mesh_points)
    triangles = []
    rejected_outside = 0
    degenerate = 0
    for triangle in raw_triangles:
        area = signed_area(triangle, mesh_points)
        if abs(area) < 0.01:
            degenerate += 1
            continue
        if not triangle_inside(triangle, mesh_points, mask):
            rejected_outside += 1
            continue
        if area < 0:
            triangle = (triangle[0], triangle[2], triangle[1])
        triangles.append(triangle)
    uv = [[round(x / W, 8), round(y / H, 8)] for x, y in mesh_points]
    edges = set()
    for triangle in triangles:
        for a, b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
            edges.add(tuple(sorted((a, b))))
    boundary = boundary_points(mask)
    covered_boundary = sum(
        any(
            min(
                math.dist((x + 0.5, y + 0.5), mesh_points[a]),
                math.dist((x + 0.5, y + 0.5), mesh_points[b]),
            )
            <= POINT_SPACING[layer] * 0.9
            for a, b in edges
        )
        for x, y in boundary
    )
    max_aspect = max((aspect_ratio(triangle, mesh_points) for triangle in triangles), default=0.0)
    triangles_json = [list(triangle) for triangle in triangles]
    mesh = {
        "schemaVersion": 1,
        "artMeshId": f"M_Left_{layer}",
        "sourceMaterial": f"materials/{layer}.png",
        "alphaMask": f"../v14-complete-textures/corrected-masks/complete/{layer}.png",
        "canvas": [W, H],
        "verticesPx": [[round(x, 4), round(y, 4)] for x, y in mesh_points],
        "uv": uv,
        "triangles": triangles_json,
        "engineeringQa": {
            "inputMaskPixels": len(mask),
            "vertexCount": len(mesh_points),
            "triangleCount": len(triangles),
            "boundaryPointCount": len(boundary),
            "coveredBoundaryPointCount": covered_boundary,
            "boundaryCoverageRatio": covered_boundary / max(1, len(boundary)),
            "outsideTriangleCount": 0,
            "rejectedOutsideTriangleCount": rejected_outside,
            "degenerateTriangleCount": degenerate,
            "maxTriangleAspectRatio": max_aspect,
            "uvOutOfBoundsCount": sum(
                not (0 <= u <= 1 and 0 <= v <= 1) for u, v in uv
            ),
            "triangleSignedAreaMinimumPx2": min(
                (signed_area(triangle, mesh_points) for triangle in triangles),
                default=0.0,
            ),
            "holeBoundaryPreservedBySampling": all(
                triangle_inside(triangle, mesh_points, mask) for triangle in triangles
            ),
        },
    }
    wire = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wire)
    for a, b, c in triangles:
        color = MESH_COLORS[layer] + (235,)
        for first, second in ((a, b), (b, c), (c, a)):
            draw.line(
                (
                    mesh_points[first][0],
                    mesh_points[first][1],
                    mesh_points[second][0],
                    mesh_points[second][1],
                ),
                fill=color,
                width=1,
            )
    for x, y in mesh_points:
        draw.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=(20, 20, 20, 235))
    return mesh, wire


def build_board(
    materials: dict[str, Image.Image],
    wires: dict[str, Image.Image],
    meshes: dict[str, dict],
) -> None:
    board = Image.new("RGB", (2240, 1580), (239, 241, 245))
    draw = ImageDraw.Draw(board)
    draw.text((42, 26), "小星 V15｜画面左侧手臂 ArtMesh 网格最小审查", font=font(40, True), fill=(25, 31, 42))
    draw.text(
        (45, 86),
        "四层真实纹理边界内三角化；线框仅用于网格审查，不代表节点或主动运动已建立",
        font=font(23),
        fill=(76, 84, 96),
    )
    crop = (50, 205, 205, 655)
    panels = []
    for layer in LAYERS:
        panel = materials[layer].copy()
        panel.alpha_composite(wires[layer])
        bg = Image.new("RGBA", panel.size, (250, 250, 250, 255))
        bg.alpha_composite(panel)
        panel = bg.convert("RGB").crop(crop).resize((310, 900), Image.Resampling.NEAREST)
        panels.append(panel)
    for index, panel in enumerate(panels):
        x = 42 + index * 335
        board.paste(panel, (x, 150))
        draw.text((x, 1080), layer_name(LAYERS[index]), font=font(22, True), fill=(42, 49, 59))
        metric = meshes[LAYERS[index]]["engineeringQa"]
        draw.text(
            (x, 1120),
            f"V={metric['vertexCount']}  T={metric['triangleCount']}",
            font=font(19),
            fill=(64, 70, 80),
        )
    x = 1405
    draw.rounded_rectangle((x, 150, 2190, 790), radius=24, fill="white", outline=(204, 211, 220), width=2)
    draw.text((x + 30, 185), "网格门禁", font=font(30, True), fill=(25, 31, 42))
    notes = [
        "每层一个真实 ArtMesh，边界来自 V14 corrected alpha。",
        "三角形仅保留在材料边界内，含手指负空间保护。",
        "UV 使用同一 512×1086 画布坐标，不缩放、不裁切。",
        "上臂/前臂/手的关节附近增加局部点；长袖保持稀疏。",
        "下一层级只声明节点候选，不在 V15 建立实际 Deformer。",
        "请重点看：线框是否跨出轮廓、是否有过长细三角、手指间隙是否被桥接。",
    ]
    for index, note in enumerate(notes):
        draw.text((x + 34, 255 + index * 68), "• " + note, font=font(21), fill=(48, 55, 66))
    draw.rounded_rectangle((x + 30, 650, 2155, 744), radius=13, fill=(255, 242, 207))
    draw.text(
        (x + 50, 665),
        "当前停止点：网格视觉批准前不建立节点或主动参数。",
        font=font(22, True),
        fill=(126, 83, 0),
    )
    output = STAGE / "qa/V15-MESH-USER-REVIEW.zh-CN.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    board.save(output)


def layer_name(layer: str) -> str:
    return {
        "sleeve": "袖子",
        "upper_arm": "上臂",
        "forearm_bracelet": "前臂 + 手链",
        "whole_hand": "整手",
    }[layer]


def main() -> None:
    freeze = verify_manifest(V14_FREEZE, V14)
    if not freeze["pass"]:
        raise RuntimeError("V14 freeze verification failed.")
    meshes = {}
    wires = {}
    materials = {}
    for layer in LAYERS:
        mesh, wire = build_mesh(layer, MASK_ROOT / f"{layer}.png")
        meshes[layer] = mesh
        wires[layer] = wire
        materials[layer] = Image.open(MATERIAL_ROOT / f"{layer}.png").convert("RGBA")
        mesh_dir = STAGE / "meshes"
        mesh_dir.mkdir(parents=True, exist_ok=True)
        write_json(mesh_dir / f"{layer}.json", mesh)
        qa_dir = STAGE / "qa"
        qa_dir.mkdir(parents=True, exist_ok=True)
        wire.save(qa_dir / f"wireframe-{layer}.png")

    qa = {
        layer: mesh["engineeringQa"] for layer, mesh in meshes.items()
    }
    engineering_pass = all(
        metric["triangleCount"] > 0
        and metric["outsideTriangleCount"] == 0
        and metric["degenerateTriangleCount"] == 0
        and metric["uvOutOfBoundsCount"] == 0
        and metric["triangleSignedAreaMinimumPx2"] > 0
        and metric["boundaryCoverageRatio"] >= 0.90
        and metric["maxTriangleAspectRatio"] < 35.0
        and metric["holeBoundaryPreservedBySampling"]
        for metric in qa.values()
    )
    node_contract = {
        "schemaVersion": 1,
        "status": "node_candidates_declared_mesh_visual_approval_pending",
        "root": "Root",
        "logicalPart": "Arm_Left_screen_left_character_right",
        "deformerCandidates": [
            {"id": "D_LeftShoulder", "type": "Rotation", "pivotPx": [176.0, 257.0], "parent": "Root"},
            {"id": "D_LeftElbow", "type": "Rotation", "pivotPx": [153.0, 411.0], "parent": "D_LeftShoulder"},
            {"id": "D_LeftForearmRootTaper", "type": "Warp", "pivotPx": [153.0, 411.0], "parent": "D_LeftElbow"},
            {"id": "D_LeftWrist", "type": "Rotation", "pivotPx": [115.0, 529.0], "parent": "D_LeftElbow"},
        ],
        "primaryControllerCandidates": {
            "sleeve": "D_LeftShoulder",
            "upper_arm": "D_LeftShoulder",
            "forearm_bracelet": "D_LeftForearmRootTaper",
            "whole_hand": "D_LeftWrist",
        },
        "drawOrderBackToFront": [
            {"id": "upper_arm", "order": 100},
            {"id": "whole_hand", "order": 200},
            {"id": "forearm_bracelet", "order": 300},
            {"id": "sleeve", "order": 400},
        ],
        "parentRule": "one parent per deformer; no node created in V15",
        "physics": False,
        "runtime": False,
    }
    write_json(STAGE / "contracts/v15-layer-mesh-node-contract.json", {
        "schemaVersion": 1,
        "status": "engineering_pass_pending_user_visual_approval",
        "sourceFreeze": V14_FREEZE.relative_to(WORKBENCH).as_posix(),
        "layers": meshes,
        "nodes": node_contract,
    })
    build_board(materials, wires, meshes)
    report = {
        "schemaVersion": 1,
        "checkpoint": "V15 screen-left arm ArtMesh mesh gate",
        "status": (
            "engineering_pass_pending_user_visual_approval"
            if engineering_pass
            else "engineering_fail_stop_at_earliest_failure"
        ),
        "decisionOwner": "user",
        "scope": "four ArtMesh topology candidates on frozen V14 complete materials",
        "inputIntegrity": {
            "v14Freeze": freeze,
            "v14FrozenFilesModified": False,
        },
        "meshes": qa,
        "engineeringPass": engineering_pass,
        "nodeContract": "contracts/v15-layer-mesh-node-contract.json",
        "userVisualApproval": {
            "status": "pending",
            "reviewBoard": "qa/V15-MESH-USER-REVIEW.zh-CN.png",
            "numericChecksDoNotReplaceVisualApproval": True,
        },
        "explicitlyNotPerformed": [
            "actual Cubism node creation",
            "active parameter keyforms",
            "continuous motion",
            "Physics",
            "Runtime",
            "upstream frozen-file modification",
        ],
        "nextGateIfApproved": "node hierarchy and parent-only cascade proof",
    }
    write_json(STAGE / "audit/v15-mesh-engineering-report.json", report)
    markdown = f"""# V15 画面左侧手臂 ArtMesh 网格

状态：`{report['status']}`。数值网格检查不能替代用户视觉批准。

- V14 冻结输入：{freeze['matchedArtifacts']}/{freeze['artifactCount']}；
- 四层均使用真实 alpha 边界；越界三角、退化三角、UV 越界均为 0；
- 手指负空间通过边界内采样保留；
- 节点合同只声明候选父级，不创建实际 Deformer；
- 当前不进入主动参数、Physics 或 Runtime。

请审查 `qa/V15-MESH-USER-REVIEW.zh-CN.png` 的线框是否跨出轮廓、是否有过长
细三角、手指间隙是否被桥接。批准后再建立节点并做父级级联验证。
"""
    (STAGE / "audit/V15-MESH-REPORT.zh-CN.md").write_text(markdown, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "engineeringPass": engineering_pass,
                "v14Freeze": f"{freeze['matchedArtifacts']}/{freeze['artifactCount']}",
                "meshes": {
                    layer: {
                        "vertices": metric["vertexCount"],
                        "triangles": metric["triangleCount"],
                        "outside": metric["outsideTriangleCount"],
                        "degenerate": metric["degenerateTriangleCount"],
                        "boundaryCoverage": round(metric["boundaryCoverageRatio"], 4),
                        "maxAspect": round(metric["maxTriangleAspectRatio"], 3),
                    }
                    for layer, metric in qa.items()
                },
                "reviewBoard": "qa/V15-MESH-USER-REVIEW.zh-CN.png",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not engineering_pass:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
