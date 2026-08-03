from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PET = Path(__file__).resolve().parents[2]
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
CONTRACT = X6 / "x6-front-actual-segmentation-contract-v8.json"
CANVAS = (650, 887)

CRITICAL = {
    "head": "缺完整脸底、眼窝/口鼻后方与连续颈根",
    "body": "缺头、肩、髋和尾根移开后应出现的连续躯干表面",
    "arm_L_upper": "目前只有可见切片与局部肩帽，不是完整上臂",
    "arm_R_upper": "目前只有可见切片与局部肩帽，不是完整上臂",
    "arm_L_lower_paw": "肘后方只有短接入带，缺完整关节内藏长度",
    "arm_R_lower_paw": "肘后方只有短接入带，缺完整关节内藏长度",
    "leg_L_upper": "髋部主体仍由身体可见像素代替，独立大腿不完整",
    "leg_R_upper": "髋部主体仍由身体可见像素代替，独立大腿不完整",
    "leg_L_lower_paw": "膝后方只有短接入带，缺完整关节内藏长度",
    "leg_R_lower_paw": "膝后方只有短接入带，缺完整关节内藏长度",
    "tail": "只有局部尾根接入带，未证明尾巴移开后的完整根部",
}

DISPLAY = {
    "head": "头底",
    "body": "身体底",
    "arm_L_upper": "左上臂",
    "arm_R_upper": "右上臂",
    "arm_L_lower_paw": "左小臂＋爪",
    "arm_R_lower_paw": "右小臂＋爪",
    "leg_L_upper": "左大腿",
    "leg_R_upper": "右大腿",
    "leg_L_lower_paw": "左小腿＋爪",
    "leg_R_lower_paw": "右小腿＋爪",
    "tail": "尾巴",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def checker(size: tuple[int, int], block: int = 14) -> Image.Image:
    image = Image.new("RGBA", size, (249, 250, 251, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(226, 232, 236, 255))
    return image


def load_layer(row: dict) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    image = Image.open(PET / row["file"]).convert("RGBA")
    bounds = row["canvasBounds"]
    canvas.alpha_composite(image, (bounds[0], bounds[1]))
    return canvas


def compose(order: list[str], layers: dict[str, Image.Image], offsets: dict[str, tuple[int, int]] | None = None) -> Image.Image:
    offsets = offsets or {}
    result = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer_id in order:
        dx, dy = offsets.get(layer_id, (0, 0))
        result.alpha_composite(layers[layer_id], (dx, dy))
    return result


def fit(image: Image.Image, size: tuple[int, int], padding: int = 10) -> Image.Image:
    target = checker(size)
    source = image.copy()
    source.thumbnail((size[0] - padding * 2, size[1] - padding * 2), Image.Resampling.LANCZOS)
    target.alpha_composite(source, ((size[0] - source.width) // 2, (size[1] - source.height) // 2))
    return target


def render(contract: dict, layers: dict[str, Image.Image]) -> None:
    order = contract["drawOrderBackToFront"]
    head_group = {"head", "ear_L", "ear_R", "eye_L", "eye_R", "mouth"}
    expanded_offsets = {layer_id: (0, -72) for layer_id in head_group}
    expanded_offsets.update(
        {
            "arm_R_upper": (-42, -12),
            "arm_R_lower_paw": (-72, -2),
            "arm_L_upper": (42, -12),
            "arm_L_lower_paw": (72, -2),
            "leg_R_upper": (-30, 26),
            "leg_R_lower_paw": (-55, 44),
            "leg_L_upper": (30, 26),
            "leg_L_lower_paw": (55, 44),
            "tail": (0, 58),
        }
    )

    output = Image.new("RGB", (1800, 1530), "#f4f6f8")
    draw = ImageDraw.Draw(output)
    draw.text((48, 25), "小橘 X6：v8 隐藏补全审计", font=font(38, True), fill="#19324b")
    draw.text((50, 79), "结论：静止拼合看不出问题，但拉开后暴露出切片式分层；局部关节套筒不能代替完整底图。", font=font(20), fill="#8a2f33")

    panels = [
        ("静止时：遮挡掩盖缺失", compose(order, layers)),
        ("拉开后：父层与根部不完整", compose(order, layers, expanded_offsets)),
    ]
    for index, (label, image) in enumerate(panels):
        x = 45 + index * 555
        draw.rounded_rectangle((x, 120, x + 520, 920), radius=8, fill="white", outline="#cbd5df", width=2)
        draw.text((x + 20, 140), label, font=font(21, True), fill="#8a2f33" if index else "#245b88")
        output.paste(fit(image, (480, 720), 12).convert("RGB"), (x + 20, 185))

    draw.rounded_rectangle((1155, 120, 1755, 920), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((1178, 140), "必须回炉的 11 个结构层", font=font(23, True), fill="#8a2f33")
    y = 195
    for index, layer_id in enumerate(CRITICAL, 1):
        draw.ellipse((1180, y + 4, 1198, y + 22), fill="#d64545")
        draw.text((1212, y), f"{index}. {DISPLAY[layer_id]}", font=font(17, True), fill="#334657")
        draw.text((1212, y + 27), CRITICAL[layer_id], font=font(13), fill="#65727d")
        y += 63

    draw.rounded_rectangle((45, 950, 1755, 1485), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((68, 970), "正确的返工标准", font=font(24, True), fill="#245b88")
    rules = [
        "1. 每个语义层导出独立 PNG；但 PNG 内必须包含该层被遮住的完整形体和纹理。",
        "2. 头移开后，身体仍有完整颈肩；眼和嘴移开后，头底仍是连续毛发，而不是透明洞。",
        "3. 四肢分开后，上臂/大腿拥有完整根部，小臂/小腿拥有足够关节内藏长度；不使用圆形补丁冒充肌肉。",
        "4. 尾巴移开后，身体尾根完整；尾层自身也有连续根部，毛流方向跨越遮挡区。",
        "5. 返工后必须同时提交静止重组、各层单独图、头/四肢/尾巴大幅移开图，再谈网格和节点。",
    ]
    y = 1025
    for rule in rules:
        draw.text((75, y), rule, font=font(18), fill="#3f5262")
        y += 58
    draw.rounded_rectangle((70, 1335, 1730, 1450), radius=7, fill="#fff7f7", outline="#e5b3b3", width=2)
    draw.text((92, 1355), "v8 处置：", font=font(20, True), fill="#8a2f33")
    draw.text((210, 1357), "降级为“切片失败证据”，不再作为实际分层候选，也不据此进入网格、侧背传播或 X7。", font=font(19), fill="#334657")
    draw.text((92, 1402), "下一候选必须先补全隐藏结构，再由你进行新的正面视觉审核。", font=font(18), fill="#65727d")
    output.save(QA / "x6-front-hidden-completion-audit-v9.png", optimize=True)


def main() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    layers = {row["id"]: load_layer(row) for row in contract["layers"]}
    render(contract, layers)
    result = {
        "schemaVersion": 1,
        "stage": "X6-front-hidden-completion-correction",
        "status": "failed-hidden-area-completeness",
        "sourceCandidate": "live2d/x6/x6-front-actual-segmentation-contract-v8.json",
        "articleReference": {
            "url": "https://zhuanlan.zhihu.com/p/383268858",
            "observedPrinciples": [
                "each semantic layer is exported as an independent PNG",
                "each actual layer binds its own mesh",
                "painter draw order manages occlusion but does not synthesize missing texture",
            ],
        },
        "criticalIncompleteLayerCount": len(CRITICAL),
        "criticalIncompleteLayers": [
            {"id": layer_id, "displayName": DISPLAY[layer_id], "failure": failure}
            for layer_id, failure in CRITICAL.items()
        ],
        "decision": "reject-v8-as-complete-layer-set-and-return-to-front-hidden-area-reconstruction",
        "qa": {"review": "live2d/x6/qa/x6-front-hidden-completion-audit-v9.png"},
        "gateBoundary": {
            "frontBoundaryApprovedByUser": True,
            "frontActualLayersApprovedByUser": False,
            "sideBackPropagationAuthorized": False,
            "gate6Approved": False,
            "x7Authorized": False,
        },
    }
    (X6 / "x6-front-hidden-completion-audit-v9.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": result["status"], "criticalIncompleteLayers": len(CRITICAL)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
