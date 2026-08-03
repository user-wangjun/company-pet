from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


PET = Path(__file__).resolve().parents[2]
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
SOURCE_CONTRACT = X6 / "x6-joint-safe-motion-bundle-contract-v4.json"
SOURCE_AUDIT = X6 / "x6-joint-safe-motion-bundle-audit-v4.json"
REST = QA / "x6-production-layer-stack-rest-v2.png"
OUTPUT = X6 / "front-user-segmentation-v8"
CANVAS = (650, 887)

DRAW_ORDER = [
    "tail",
    "leg_L_lower_paw",
    "leg_R_lower_paw",
    "leg_L_upper",
    "leg_R_upper",
    "arm_L_lower_paw",
    "arm_R_lower_paw",
    "arm_L_upper",
    "arm_R_upper",
    "ear_L",
    "ear_R",
    "eye_L",
    "eye_R",
    "mouth",
    "head",
    "body",
]

PARENTS = {
    "tail": "body",
    "leg_L_lower_paw": "leg_L_upper",
    "leg_R_lower_paw": "leg_R_upper",
    "leg_L_upper": "body",
    "leg_R_upper": "body",
    "arm_L_lower_paw": "arm_L_upper",
    "arm_R_lower_paw": "arm_R_upper",
    "arm_L_upper": "body+head",
    "arm_R_upper": "body+head",
    "ear_L": "head",
    "ear_R": "head",
    "eye_L": "head",
    "eye_R": "head",
    "mouth": "head",
    "head": "body",
    "body": None,
}

DISPLAY = {
    "head": "头部主体",
    "mouth": "嘴部（含内部口鼻子层）",
    "ear_L": "左耳",
    "ear_R": "右耳",
    "eye_L": "左眼",
    "eye_R": "右眼",
    "body": "连续身体",
    "arm_L_upper": "左上臂／肩袖",
    "arm_L_lower_paw": "左小臂＋前爪",
    "arm_R_upper": "右上臂／肩袖",
    "arm_R_lower_paw": "右小臂＋前爪",
    "leg_L_upper": "左大腿",
    "leg_L_lower_paw": "左小腿＋后爪",
    "leg_R_upper": "右大腿",
    "leg_R_lower_paw": "右小腿＋后爪",
    "tail": "尾巴",
}

SEMANTIC_CARDS = [
    ("头部主体", ["head"]),
    ("耳朵", ["ear_L", "ear_R"]),
    ("眼睛", ["eye_L", "eye_R"]),
    ("嘴部", ["mouth"]),
    ("连续身体", ["body"]),
    ("左右上臂／肩袖", ["arm_L_upper", "arm_R_upper"]),
    ("左右小臂＋前爪", ["arm_L_lower_paw", "arm_R_lower_paw"]),
    ("左右大腿", ["leg_L_upper", "leg_R_upper"]),
    ("左右小腿＋后爪", ["leg_L_lower_paw", "leg_R_lower_paw"]),
    ("尾巴", ["tail"]),
]


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


def place(path: str, bounds: list[int]) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    image = Image.open(PET / path).convert("RGBA")
    canvas.alpha_composite(image, (bounds[0], bounds[1]))
    return canvas


def merge_layer(record: dict) -> Image.Image:
    layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    if record.get("hiddenCollarFile"):
        layer.alpha_composite(place(record["hiddenCollarFile"], record["hiddenCollarBounds"]))
    layer.alpha_composite(place(record["visibleFile"], record["visibleBounds"]))
    return layer


def tight_export(layer: Image.Image, path: Path) -> list[int]:
    box = layer.getchannel("A").getbbox()
    if box is None:
        raise RuntimeError(f"empty layer: {path.name}")
    layer.crop(box).save(path, optimize=True)
    return list(box)


def compose(layers: dict[str, Image.Image], offsets: dict[str, tuple[int, int]] | None = None) -> Image.Image:
    offsets = offsets or {}
    result = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for bundle_id in DRAW_ORDER:
        dx, dy = offsets.get(bundle_id, (0, 0))
        result.alpha_composite(layers[bundle_id], (dx, dy))
    return result


def fit(image: Image.Image, size: tuple[int, int], padding: int = 12) -> Image.Image:
    target = checker(size)
    source = image.copy()
    source.thumbnail((size[0] - padding * 2, size[1] - padding * 2), Image.Resampling.LANCZOS)
    target.alpha_composite(source, ((size[0] - source.width) // 2, (size[1] - source.height) // 2))
    return target


def card_image(layers: dict[str, Image.Image], bundle_ids: list[str]) -> Image.Image:
    result = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for bundle_id in DRAW_ORDER:
        if bundle_id in bundle_ids:
            result.alpha_composite(layers[bundle_id])
    box = result.getchannel("A").getbbox()
    return result.crop(box) if box else result


def render_preview(layers: dict[str, Image.Image], rest: Image.Image) -> None:
    output = Image.new("RGB", (1800, 1520), "#f4f6f8")
    draw = ImageDraw.Draw(output)
    draw.text((48, 25), "小橘 X6：正面实际分层 v8", font=font(38, True), fill="#19324b")
    draw.text((50, 79), "使用真实透明 PNG 重组；关节隐藏接入区已并入子层，父层在静止姿势中将其遮住。", font=font(20), fill="#586774")

    draw.rounded_rectangle((42, 120, 585, 1010), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((64, 140), "实际图层重组", font=font(24, True), fill="#245b88")
    output.paste(fit(rest, (500, 810), 16).convert("RGB"), (64, 185))

    draw.rounded_rectangle((610, 120, 1758, 1010), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((632, 140), "10 类动作主体（内部共 16 个可独立层）", font=font(24, True), fill="#245b88")
    card_w, card_h = 215, 360
    start_x, start_y = 632, 190
    for index, (label, bundle_ids) in enumerate(SEMANTIC_CARDS):
        col, row = index % 5, index // 5
        x = start_x + col * 222
        y = start_y + row * 392
        draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=6, fill="#fbfcfd", outline="#d4dce3", width=2)
        preview = fit(card_image(layers, bundle_ids), (195, 292), 10)
        output.paste(preview.convert("RGB"), (x + 10, y + 10))
        draw.text((x + 10, y + 312), label, font=font(15, True), fill="#34495a")

    draw.rounded_rectangle((42, 1035, 1758, 1478), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((64, 1055), "前肢重叠试移：检查肩与肘移动后是否断开", font=font(24, True), fill="#245b88")
    frames = [
        ("静止重组", {}),
        ("整条右前肢抬起", {"arm_R_upper": (-8, -5), "arm_R_lower_paw": (-8, -5)}),
        ("右小臂继续展开", {"arm_R_upper": (-8, -5), "arm_R_lower_paw": (-16, 3)}),
    ]
    for index, (label, offsets) in enumerate(frames):
        x = 105 + index * 555
        frame = compose(layers, offsets)
        output.paste(fit(frame, (480, 330), 8).convert("RGB"), (x, 1105))
        draw.text((x + 150, 1438), label, font=font(18, True), fill="#34495a")
    output.save(QA / "x6-front-actual-segmentation-review-v8.png", optimize=True)


def main() -> None:
    source = json.loads(SOURCE_CONTRACT.read_text(encoding="utf-8"))
    records = {row["bundle"]: row for row in source["exports"] if row["view"] == "front"}
    if set(records) != set(DRAW_ORDER):
        raise RuntimeError("front bundle vocabulary differs from approved v7 grouping")

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    layers = {bundle_id: merge_layer(records[bundle_id]) for bundle_id in DRAW_ORDER}
    exports = []
    for index, bundle_id in enumerate(DRAW_ORDER, 1):
        filename = f"{index:02d}_{bundle_id}.png"
        bounds = tight_export(layers[bundle_id], OUTPUT / filename)
        record = records[bundle_id]
        exports.append(
            {
                "id": bundle_id,
                "displayName": DISPLAY[bundle_id],
                "file": f"live2d/x6/front-user-segmentation-v8/{filename}",
                "canvasBounds": bounds,
                "parent": PARENTS[bundle_id],
                "containsVisibleSurface": True,
                "containsHiddenJointOverlap": bool(record.get("hiddenCollarFile")),
                "sourceVisibleFile": record["visibleFile"],
                "sourceHiddenOverlapFile": record.get("hiddenCollarFile"),
            }
        )

    reference = Image.open(REST).convert("RGBA").crop((0, 0, *CANVAS))
    reconstruction = compose(layers)
    difference = ImageChops.difference(reference, reconstruction)
    ref_alpha = reference.getchannel("A").tobytes()
    out_alpha = reconstruction.getchannel("A").tobytes()
    extra_pixels = sum(out > 0 and ref == 0 for out, ref in zip(out_alpha, ref_alpha))
    missing_pixels = sum(out == 0 and ref > 0 for out, ref in zip(out_alpha, ref_alpha))
    changed_pixels = sum(any(pixel) for pixel in difference.get_flattened_data())
    if extra_pixels != 0 or changed_pixels > 50:
        raise RuntimeError(f"rest reconstruction drift: extra={extra_pixels}, changed={changed_pixels}")
    reconstruction.save(OUTPUT / "front-reconstruction.png", optimize=True)
    render_preview(layers, reconstruction)

    source_audit = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    front_joint_records = [row for row in source_audit["records"] if row["view"] == "front"]
    result = {
        "schemaVersion": 1,
        "stage": "X6-front-actual-segmentation-candidate",
        "status": "candidate-for-user-visual-review",
        "basis": "user-approved-v7-front-boundary-and-occlusion-order",
        "scope": "front-view-actual-transparent-png-separation-only",
        "canvas": {"width": CANVAS[0], "height": CANVAS[1]},
        "semanticGroupCount": len(SEMANTIC_CARDS),
        "movableLayerCount": len(exports),
        "drawOrderBackToFront": DRAW_ORDER,
        "layers": exports,
        "restReconstructionAudit": {
            "extraAlphaPixels": extra_pixels,
            "missingAlphaPixels": missing_pixels,
            "changedRgbaPixels": changed_pixels,
            "status": "pass" if extra_pixels == 0 and changed_pixels <= 50 else "fail",
        },
        "inheritedFrontJointPullAudit": {
            "source": "live2d/x6/x6-joint-safe-motion-bundle-audit-v4.json",
            "stressDistancePixels": source_audit["stressDistancePixels"],
            "jointCount": len(front_joint_records),
            "passCount": sum(row["passes"] for row in front_joint_records),
            "minimumParentContactAfterShiftPixels": min(row["parentContactAfterShiftPixels"] for row in front_joint_records),
            "minimumChildBoundaryContactAfterShiftPixels": min(row["childBoundaryContactAfterShiftPixels"] for row in front_joint_records),
        },
        "qa": {
            "reconstruction": "live2d/x6/front-user-segmentation-v8/front-reconstruction.png",
            "review": "live2d/x6/qa/x6-front-actual-segmentation-review-v8.png",
        },
        "gateBoundary": {
            "frontBoundaryApprovedByUser": True,
            "frontActualLayersApprovedByUser": False,
            "sideBackPropagationAuthorized": False,
            "gate6Approved": False,
            "x7Authorized": False,
        },
    }
    (X6 / "x6-front-actual-segmentation-contract-v8.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "ok", "layers": len(exports), **result["restReconstructionAudit"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
