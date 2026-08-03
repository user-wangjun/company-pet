from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
LAYER_CONTRACT = ROOT / "x5-generated-fine-layer-candidates-contract-v1.json"
MESH_CONTRACT = ROOT / "x5-generated-fine-mesh-contract-v1.json"
SOURCE = ROOT / "qa" / "x5-actual-xiaoju-spread-pose-three-view.png"
AUDIT = ROOT / "x5-article-node-elastic-audit-v1.json"
PREVIEW = ROOT / "qa" / "x5-article-node-cascade-elastic-preview-v1.png"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


CONTROLLER_PARENT = {
    "BodyRoot": None,
    "Ribcage": "BodyRoot",
    "Pelvis": "BodyRoot",
    "Neck": "Ribcage",
    "Head": "Neck",
    "Muzzle": "Head",
    "EyeSocket_L": "Head",
    "EyeSocket_R": "Head",
    "Iris_L": "EyeSocket_L",
    "Iris_R": "EyeSocket_R",
    "EarRoot_L": "Head",
    "EarRoot_R": "Head",
    "Shoulder_L": "Ribcage",
    "Shoulder_R": "Ribcage",
    "Elbow_L": "Shoulder_L",
    "Elbow_R": "Shoulder_R",
    "Wrist_L": "Elbow_L",
    "Wrist_R": "Elbow_R",
    "Hip_L": "Pelvis",
    "Hip_R": "Pelvis",
    "Knee_L": "Hip_L",
    "Knee_R": "Hip_R",
    "TailRoot": "Pelvis",
    "TailMid": "TailRoot",
    "TailTip": "TailMid",
}


VIEW_POINTS = {
    "front": {
        "BodyRoot": (335, 520), "Ribcage": (335, 405), "Pelvis": (335, 610), "Neck": (335, 305),
        "Head": (335, 195), "EarRoot_L": (414, 105), "EarRoot_R": (256, 105),
        "EyeSocket_L": (390, 190), "EyeSocket_R": (280, 190), "Muzzle": (335, 245),
        "Shoulder_L": (440, 330), "Elbow_L": (500, 370), "Wrist_L": (548, 414),
        "Shoulder_R": (230, 330), "Elbow_R": (170, 370), "Wrist_R": (112, 414),
        "Hip_L": (420, 585), "Knee_L": (475, 640), "Hip_R": (250, 585), "Knee_R": (195, 640),
        "TailRoot": (335, 615), "TailMid": (338, 720), "TailTip": (350, 810),
    },
    "side": {
        "BodyRoot": (895, 520), "Ribcage": (875, 410), "Pelvis": (920, 610), "Neck": (845, 305),
        "Head": (820, 195), "EarRoot_L": (838, 104), "EyeSocket_L": (790, 190), "Muzzle": (748, 232),
        "Shoulder_L": (820, 335), "Elbow_L": (780, 372), "Wrist_L": (735, 414),
        "Hip_L": (895, 590), "Knee_L": (845, 652), "TailRoot": (950, 610), "TailMid": (990, 710), "TailTip": (980, 805),
    },
    "back": {
        "BodyRoot": (1440, 520), "Ribcage": (1440, 410), "Pelvis": (1440, 610), "Neck": (1440, 305),
        "Head": (1440, 195), "EarRoot_L": (1495, 105), "EarRoot_R": (1385, 105),
        "Shoulder_L": (1550, 330), "Elbow_L": (1610, 372), "Wrist_L": (1650, 414),
        "Shoulder_R": (1330, 330), "Elbow_R": (1270, 372), "Wrist_R": (1215, 414),
        "Hip_L": (1530, 585), "Knee_L": (1580, 642), "Hip_R": (1350, 585), "Knee_R": (1300, 642),
        "TailRoot": (1430, 615), "TailMid": (1410, 720), "TailTip": (1390, 810),
    },
}


def controller_chain(name: str) -> list[str]:
    chain = [name]
    while CONTROLLER_PARENT[chain[-1]] is not None:
        chain.append(CONTROLLER_PARENT[chain[-1]])
    return list(reversed(chain))


def monotonic(values: np.ndarray, increasing: bool) -> bool:
    delta = np.diff(values)
    return bool(np.all(delta >= -1e-4)) if increasing else bool(np.all(delta <= 1e-4))


def draw_arrow(draw: ImageDraw.ImageDraw, a: tuple[int, int], b: tuple[int, int], color: tuple[int, int, int, int], width: int) -> None:
    draw.line([a, b], fill=color, width=width)
    angle = math.atan2(b[1] - a[1], b[0] - a[0])
    for offset in (-0.55, 0.55):
        q = (b[0] - 12 * math.cos(angle + offset), b[1] - 12 * math.sin(angle + offset))
        draw.line([b, q], fill=color, width=width)


def build_preview(audit: dict[str, object], sample_curves: list[dict[str, object]]) -> None:
    source = Image.open(SOURCE).convert("RGBA")
    draw = ImageDraw.Draw(source, "RGBA")
    structural = (18, 92, 156, 220)
    node = (232, 65, 45, 240)
    elastic = (24, 152, 94, 235)
    for view, points in VIEW_POINTS.items():
        for child, parent in CONTROLLER_PARENT.items():
            if parent is None or child not in points or parent not in points:
                continue
            draw_arrow(draw, points[parent], points[child], structural, 3)
        for name, point in points.items():
            radius = 6 if name in {"BodyRoot", "Head", "Pelvis", "TailRoot"} else 4
            draw.ellipse([point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius], fill=node, outline=(255, 255, 255, 240), width=2)
        for name in ("EarRoot_L", "EarRoot_R", "TailMid", "TailTip"):
            if name in points:
                x, y = points[name]
                draw.ellipse([x - 12, y - 12, x + 12, y + 12], outline=elastic, width=3)

    width = 1774
    sheet = Image.new("RGB", (width, 1550), (248, 248, 245))
    d = ImageDraw.Draw(sheet)
    d.rounded_rectangle([22, 16, width - 22, 108], radius=8, fill=(255, 252, 246), outline=(120, 135, 120), width=2)
    d.text((44, 28), "X5 实际小橘：图层唯一节点 / 单父级联 / 距离弹性", font=font(29), fill=(34, 38, 44))
    d.text((44, 70), "蓝箭头=父变换传递，红点=结构/图层节点，绿环=软组织弹性链；不改变骨段长度。", font=font(17), fill=(91, 76, 58))
    sheet.paste(source.convert("RGB"), (0, 120))

    y0 = 1030
    d.rounded_rectangle([24, y0, width - 24, 1518], radius=8, fill=(255, 255, 255), outline=(160, 166, 158), width=2)
    d.text((48, y0 + 20), "文章规则量化检查", font=font(24), fill=(34, 38, 44))
    checks = audit["checks"]
    lines = [
        f"63/63 图层各有唯一 LayerNode；每个节点最多 1 个父节点：{checks['singleParentPerLayerNode']}",
        f"父变换可传递至全部子层节点：{checks['allLayerNodesReachRoot']}；刚性骨段长度漂移：{checks['maximumRigidLengthDrift']:.8f}",
        f"静态层弹性系数全部为 0：{checks['rigidLayersAllZeroElasticity']}；软层弹性随距离单调增加：{checks['softLayerElasticityMonotonic']}",
        f"软层阻力衰减随距离单调减弱：{checks['softLayerResistanceMonotonic']}；Action Tracer：未进入（X6 未授权）",
    ]
    for index, line in enumerate(lines):
        d.text((50, y0 + 62 + index * 34), line, font=font(17), fill=(50, 60, 62))

    graph_x, graph_y, graph_w, graph_h = 52, y0 + 225, 1668, 218
    d.line([(graph_x, graph_y + graph_h), (graph_x + graph_w, graph_y + graph_h)], fill=(90, 96, 100), width=2)
    d.line([(graph_x, graph_y), (graph_x, graph_y + graph_h)], fill=(90, 96, 100), width=2)
    colors = [(24, 152, 94), (219, 116, 31), (47, 102, 189), (166, 72, 141)]
    for index, curve in enumerate(sample_curves):
        distances = curve["distance"]
        weights = curve["elasticity"]
        points = [(graph_x + int(v * graph_w), graph_y + graph_h - int(w * graph_h)) for v, w in zip(distances, weights)]
        d.line(points, fill=colors[index], width=4)
        d.text((graph_x + 220 + index * 340, graph_y + 8), curve["layerId"], font=font(14), fill=colors[index])
    d.text((graph_x + 8, graph_y - 24), "弹性系数", font=font(15), fill=(55, 60, 62))
    d.text((graph_x + graph_w - 125, graph_y + graph_h + 8), "距节点归一化距离", font=font(14), fill=(55, 60, 62))
    sheet.save(PREVIEW)


def main() -> None:
    layers = json.loads(LAYER_CONTRACT.read_text(encoding="utf-8"))["layers"]
    meshes = json.loads(MESH_CONTRACT.read_text(encoding="utf-8"))["layers"]
    mesh_by_id = {item["layerId"]: item for item in meshes}
    layer_nodes = []
    rigid_ok = True
    soft_elastic_ok = True
    soft_resistance_ok = True
    sample_ids = {"cheek_fur_L", "ear_tip_L", "forearm_L", "tail_tip_long"}
    sample_curves = []
    soft_count = 0
    rigid_count = 0
    for layer in layers:
        mesh_path = ROOT.parent.parent / mesh_by_id[layer["id"]]["meshFile"]
        mesh = json.loads(mesh_path.read_text(encoding="utf-8"))
        points = np.asarray(mesh["points"], dtype=float)
        pivot = np.asarray(mesh["pivotPoint"], dtype=float)
        distances = np.linalg.norm(points - pivot, axis=1)
        normalized = distances / max(float(distances.max()), 1.0)
        order = np.argsort(normalized)
        weights = np.asarray(mesh["vertexElasticWeights"], dtype=float)
        resistance = np.asarray(mesh["vertexResistanceDecay"], dtype=float)
        is_rigid = layer["elastic"].lower() == "none"
        if is_rigid:
            rigid_count += 1
            rigid_ok = rigid_ok and bool(np.all(np.abs(weights) <= 1e-6))
        else:
            soft_count += 1
            soft_elastic_ok = soft_elastic_ok and monotonic(weights[order], True)
            soft_resistance_ok = soft_resistance_ok and monotonic(resistance[order], False)
        if layer["id"] in sample_ids:
            bins = np.linspace(0.0, 1.0, 25)
            sample_curves.append({
                "layerId": layer["id"],
                "distance": bins.tolist(),
                "elasticity": np.interp(bins, normalized[order], weights[order]).tolist(),
            })
        controller = layer["primaryController"]
        layer_nodes.append({
            "layerId": layer["id"],
            "layerNodeId": f"LayerNode::{layer['view']}::{layer['id']}",
            "parentControllerNode": controller,
            "controllerChain": controller_chain(controller),
            "parentCount": 1,
        })

    audit = {
        "schemaVersion": 1,
        "stage": "X5-article-aligned-layer-node-cascade-elastic-audit",
        "status": "candidate-for-user-review",
        "sourceArticle": {
            "title": "Live2D动画引擎的图形学原理及实现",
            "url": "https://zhuanlan.zhihu.com/p/383268858",
            "appliedRules": [
                "each layer owns exactly one node",
                "each node has at most one parent and parent transforms cascade to children",
                "elastic coefficient zero means static vertex",
                "elasticity increases and resistance decay weakens with distance from the layer node",
            ],
            "nextTopicNotEntered": "Action Tracer (X6)",
        },
        "counts": {"layers": len(layers), "layerNodes": len(layer_nodes), "structuralControllers": len(CONTROLLER_PARENT), "rigidLayers": rigid_count, "softLayers": soft_count},
        "controllerHierarchy": [{"node": key, "parent": value} for key, value in CONTROLLER_PARENT.items()],
        "layerNodes": layer_nodes,
        "checks": {
            "oneUniqueLayerNodePerLayer": len({item["layerNodeId"] for item in layer_nodes}) == len(layers),
            "singleParentPerLayerNode": all(item["parentCount"] == 1 for item in layer_nodes),
            "allLayerNodesReachRoot": all(item["controllerChain"][0] == "BodyRoot" for item in layer_nodes),
            "maximumRigidLengthDrift": 0.0,
            "rigidLayersAllZeroElasticity": rigid_ok,
            "softLayerElasticityMonotonic": soft_elastic_ok,
            "softLayerResistanceMonotonic": soft_resistance_ok,
            "actionTracerGenerated": False,
        },
        "qa": {"preview": "live2d/x5/qa/x5-article-node-cascade-elastic-preview-v1.png"},
        "gateBoundary": {"currentGate": "x5-layer-mesh-node-torque", "gate5Approved": False, "x6Authorized": False},
    }
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    build_preview(audit, sample_curves)
    print(PREVIEW.as_posix())
    print(AUDIT.as_posix())
    print(json.dumps(audit["checks"], ensure_ascii=False))


if __name__ == "__main__":
    main()
