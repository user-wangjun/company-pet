from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
LAYER_CONTRACT = ROOT / "x5-generated-fine-layer-candidates-contract-v1.json"
MESH_CONTRACT = ROOT / "x5-generated-fine-mesh-contract-v1.json"
QA = ROOT / "qa"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def checker(size: tuple[int, int], block: int = 10) -> Image.Image:
    image = Image.new("RGB", size, (245, 245, 245))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle([x, y, x + block - 1, y + block - 1], fill=(226, 226, 226))
    return image


def render_layer(layer: dict[str, object], mesh: dict[str, object], size: tuple[int, int]) -> Image.Image:
    image = Image.open(ROOT.parent.parent / layer["file"]).convert("RGBA")
    panel = checker(size).convert("RGBA")
    scale = min((size[0] - 28) / image.width, (size[1] - 28) / image.height, 2.8)
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    ox = (size[0] - resized.width) // 2
    oy = (size[1] - resized.height) // 2
    panel.alpha_composite(resized, (ox, oy))
    draw = ImageDraw.Draw(panel, "RGBA")
    points = [(ox + point[0] * scale, oy + point[1] * scale) for point in mesh["points"]]
    for a, b, c in mesh["triangles"]:
        draw.line([points[a], points[b], points[c], points[a]], fill=(18, 101, 220, 220), width=2)
    elastic_candidates = sorted(
        (index for index, weight in enumerate(mesh["vertexElasticWeights"]) if weight >= 0.45),
        key=lambda index: mesh["vertexElasticWeights"][index],
        reverse=True,
    )
    for index in elastic_candidates[:3]:
        point = points[index]
        if mesh["vertexElasticWeights"][index] >= 0.45:
            draw.ellipse([point[0] - 3, point[1] - 3, point[0] + 3, point[1] + 3], fill=(22, 154, 91, 245))
    px = ox + mesh["pivotPoint"][0] * scale
    py = oy + mesh["pivotPoint"][1] * scale
    draw.ellipse([px - 7, py - 7, px + 7, py + 7], fill=(235, 67, 45, 255), outline=(255, 255, 255, 255), width=3)
    return panel.convert("RGB")


def render_anchor_only(layer: dict[str, object], mesh: dict[str, object], size: tuple[int, int]) -> Image.Image:
    image = Image.open(ROOT.parent.parent / layer["file"]).convert("RGBA")
    panel = checker(size).convert("RGBA")
    scale = min((size[0] - 28) / image.width, (size[1] - 28) / image.height, 2.8)
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    ox = (size[0] - resized.width) // 2
    oy = (size[1] - resized.height) // 2
    panel.alpha_composite(resized, (ox, oy))
    draw = ImageDraw.Draw(panel, "RGBA")
    px = ox + mesh["pivotPoint"][0] * scale
    py = oy + mesh["pivotPoint"][1] * scale
    draw.ellipse([px - 8, py - 8, px + 8, py + 8], fill=(235, 67, 45, 255), outline=(255, 255, 255, 255), width=3)
    return panel.convert("RGB")


def group_for(layer_id: str, index: int) -> str:
    if index <= 24 or index in (51, 52, 53):
        return "head"
    if 44 <= index <= 50:
        return "tail"
    if 31 <= index <= 43 or 57 <= index <= 59:
        return "limbs"
    return "torso"


def build_sheet(name: str, title: str, items: list[tuple[dict[str, object], dict[str, object]]], cols: int) -> Path:
    cell_w, cell_h = 344, 292
    rows = math.ceil(len(items) / cols)
    width = cols * cell_w + 48
    height = 126 + rows * cell_h + 38
    sheet = Image.new("RGB", (width, height), (249, 249, 246))
    draw = ImageDraw.Draw(sheet)
    draw.rounded_rectangle([18, 14, width - 18, 98], radius=8, fill=(255, 252, 246), outline=(120, 135, 120), width=2)
    draw.text((38, 25), title, font=font(27), fill=(34, 38, 44))
    draw.text((38, 64), "蓝=三角网格，红=该层唯一节点，绿=最多 3 个代表性高弹性顶点；其余弹性保留在权重合同中。", font=font(15), fill=(92, 76, 56))
    for index, (layer, mesh) in enumerate(items):
        col, row = index % cols, index // cols
        x, y = 24 + col * cell_w, 112 + row * cell_h
        draw.rounded_rectangle([x, y, x + cell_w - 12, y + cell_h - 12], radius=5, fill=(255, 255, 255), outline=(169, 171, 163), width=1)
        card = render_layer(layer, mesh, (cell_w - 32, 224))
        sheet.paste(card, (x + 10, y + 10))
        draw.text((x + 12, y + 239), f"{layer['index']:02d} {layer['view']}:{layer['id']}", font=font(14), fill=(38, 45, 52))
        draw.text((x + 12, y + 262), f"V{len(mesh['points'])} / T{len(mesh['triangles'])} -> {layer['primaryController']}", font=font(12), fill=(92, 82, 70))
    output = QA / f"x5-triangulation-detail-{name}-v1.png"
    sheet.save(output)
    return output


def build_anchor_sheet(name: str, title: str, items: list[tuple[dict[str, object], dict[str, object]]], cols: int, large: bool) -> Path:
    cell_w, cell_h = (344, 292) if large else (244, 194)
    image_h = 224 if large else 132
    rows = math.ceil(len(items) / cols)
    width = cols * cell_w + 48
    height = 126 + rows * cell_h + 38
    sheet = Image.new("RGB", (width, height), (249, 249, 246))
    draw = ImageDraw.Draw(sheet)
    draw.rounded_rectangle([18, 14, width - 18, 98], radius=8, fill=(255, 252, 246), outline=(120, 135, 120), width=2)
    draw.text((38, 25), title, font=font(27), fill=(34, 38, 44))
    draw.text((38, 64), "每个分层只有 1 个红色动作锚点；本图隐藏全部三角网格顶点和弹性权重点。", font=font(15), fill=(92, 76, 56))
    for index, (layer, mesh) in enumerate(items):
        col, row = index % cols, index // cols
        x, y = 24 + col * cell_w, 112 + row * cell_h
        draw.rounded_rectangle([x, y, x + cell_w - 12, y + cell_h - 12], radius=5, fill=(255, 255, 255), outline=(169, 171, 163), width=1)
        card = render_anchor_only(layer, mesh, (cell_w - 32, image_h))
        sheet.paste(card, (x + 10, y + 10))
        text_y = y + image_h + 18
        draw.text((x + 12, text_y), f"{layer['index']:02d} {layer['view']}:{layer['id']}", font=font(13 if large else 10), fill=(38, 45, 52))
        draw.text((x + 12, text_y + (22 if large else 16)), f"锚点 1 -> {layer['primaryController']}", font=font(12 if large else 10), fill=(132, 63, 48))
    output = QA / f"x5-layer-anchor-only-{name}-v1.png"
    sheet.save(output)
    return output


def main() -> None:
    QA.mkdir(parents=True, exist_ok=True)
    layers = json.loads(LAYER_CONTRACT.read_text(encoding="utf-8"))["layers"]
    mesh_contract = json.loads(MESH_CONTRACT.read_text(encoding="utf-8"))["layers"]
    mesh_paths = {item["layerId"]: ROOT.parent.parent / item["meshFile"] for item in mesh_contract}
    groups: dict[str, list[tuple[dict[str, object], dict[str, object]]]] = {key: [] for key in ("head", "torso", "limbs", "tail")}
    for layer in layers:
        mesh = json.loads(mesh_paths[layer["id"]].read_text(encoding="utf-8"))
        groups[group_for(layer["id"], layer["index"])].append((layer, mesh))
    outputs = [
        build_sheet("head", "X5 分层三角网格放大审核：头部 / 眼睛 / 耳朵 / 胡须", groups["head"], 4),
        build_sheet("torso", "X5 分层三角网格放大审核：颈部 / 胸腹 / 骨盆 / 背部", groups["torso"], 4),
        build_sheet("limbs", "X5 分层三角网格放大审核：前肢 / 后肢 / 足部", groups["limbs"], 4),
        build_sheet("tail", "X5 分层三角网格放大审核：尾根 / 尾中 / 尾尖", groups["tail"], 4),
        build_anchor_sheet("atlas", "X5 63 个分层的真实动作锚点总览", [(layer, json.loads(mesh_paths[layer["id"]].read_text(encoding="utf-8"))) for layer in layers], 6, False),
        build_anchor_sheet("head", "X5 头部分层动作锚点放大审核（无网格点）", groups["head"], 4, True),
    ]
    print("\n".join(path.as_posix() for path in outputs))


if __name__ == "__main__":
    main()
