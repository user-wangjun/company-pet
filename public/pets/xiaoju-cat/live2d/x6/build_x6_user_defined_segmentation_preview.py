from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PET = ROOT.parent
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
CONTRACT = X6 / "x6-joint-safe-motion-bundle-contract-v4.json"
REST = QA / "x6-production-layer-stack-rest-v2.png"
CANVAS = (1774, 887)
FRONT_BOUNDS = (0, 0, 650, 887)

COLORS = {
    "head_body": (255, 184, 0, 255),
    "detail": (68, 72, 78, 255),
    "upper_arm": (108, 188, 0, 255),
    "lower_arm": (25, 158, 232, 255),
    "lower_leg": (244, 75, 94, 255),
}

GROUPS = {
    "head": ("head",),
    "ears": ("ear_L", "ear_R"),
    "eyes": ("eye_L", "eye_R"),
    "mouth": ("mouth",),
    "body": ("body",),
    "upper_arms": ("arm_L_upper", "arm_R_upper"),
    "lower_arms": ("arm_L_lower_paw", "arm_R_lower_paw"),
    "upper_legs": ("leg_L_upper", "leg_R_upper"),
    "lower_legs": ("leg_L_lower_paw", "leg_R_lower_paw"),
    "tail": ("tail",),
}

GROUP_COLORS = {
    "head": "head_body",
    "ears": "detail",
    "eyes": "detail",
    "mouth": "detail",
    "body": "head_body",
    "upper_arms": "upper_arm",
    "lower_arms": "lower_arm",
    "upper_legs": "detail",
    "lower_legs": "lower_leg",
    "tail": "detail",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def checker(size: tuple[int, int], block: int = 14) -> Image.Image:
    image = Image.new("RGBA", size, (249, 250, 251, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(227, 232, 235, 255))
    return image


def load_full(path: str, bounds: list[int]) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.alpha_composite(Image.open(PET / path).convert("RGBA"), (bounds[0], bounds[1]))
    return canvas


def smooth_outline(alpha: Image.Image, color: tuple[int, int, int, int], width: int = 7) -> Image.Image:
    softened = alpha.filter(ImageFilter.GaussianBlur(1.7))
    outer = softened.filter(ImageFilter.MaxFilter(width))
    inner = softened.filter(ImageFilter.MinFilter(width))
    edge = ImageChops.subtract(outer, inner)
    edge = edge.point(lambda value: min(255, value * 2))
    overlay = Image.new("RGBA", alpha.size, color)
    overlay.putalpha(ImageChops.multiply(edge, Image.new("L", alpha.size, color[3])))
    return overlay


def compose_group(records: dict[tuple[str, str], dict], bundle_ids: tuple[str, ...]) -> Image.Image:
    image = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for bundle_id in bundle_ids:
        record = records[("front", bundle_id)]
        image.alpha_composite(load_full(record["visibleFile"], record["visibleBounds"]))
    return image


def fit(image: Image.Image, size: tuple[int, int], padding: int = 14) -> Image.Image:
    background = checker(size)
    copy = image.copy()
    copy.thumbnail((size[0] - padding * 2, size[1] - padding * 2), Image.Resampling.LANCZOS)
    background.alpha_composite(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return background


def main() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    records = {(row["view"], row["bundle"]): row for row in contract["exports"]}
    rest = Image.open(REST).convert("RGBA").crop(FRONT_BOUNDS)
    overlay = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    group_stats = []
    for group_id, bundle_ids in GROUPS.items():
        group = compose_group(records, bundle_ids)
        alpha = group.getchannel("A")
        if group_id == "mouth":
            alpha = Image.new("L", CANVAS, 0)
            ImageDraw.Draw(alpha).polygon(
                ((315, 248), (333, 238), (354, 248), (344, 263), (324, 263)),
                fill=255,
            )
        overlay.alpha_composite(smooth_outline(alpha, COLORS[GROUP_COLORS[group_id]]))
        group_stats.append(
            {
                "id": group_id,
                "bundles": list(bundle_ids),
                "alphaPixels": sum(value > 8 for value in alpha.crop(FRONT_BOUNDS).tobytes()),
                "colorRole": GROUP_COLORS[group_id],
                "displayMaskRule": "central-mouth-control-only; whiskers remain internal children" if group_id == "mouth" else "bundle-alpha-boundary",
            }
        )
    marked = Image.open(REST).convert("RGBA")
    marked.alpha_composite(overlay)
    marked = marked.crop(FRONT_BOUNDS)

    output = Image.new("RGB", (1700, 1120), "#f5f7f9")
    draw = ImageDraw.Draw(output)
    draw.text((50, 28), "小橘 X6：按你的草图整理的分层方案", font=font(38, True), fill="#19324b")
    draw.text((52, 82), "当前只确认正面边界；线条已平滑化，尚未扩展到侧面、背面或进入 X7。", font=font(20), fill="#5b6874")
    draw.rounded_rectangle((46, 125, 810, 1030), radius=8, fill="white", outline="#cbd5df", width=2)
    output.paste(fit(marked, (724, 830), 16).convert("RGB"), (66, 168))
    draw.text((68, 138), "正面边界候选", font=font(22, True), fill="#245b88")

    draw.rounded_rectangle((840, 125, 1652, 1030), radius=8, fill="white", outline="#cbd5df", width=2)
    x = 878
    y = 158
    rows = (
        ("黄色", "头部主体、连续身体", COLORS["head_body"]),
        ("深灰", "耳朵、眼睛、嘴、大腿、尾巴", COLORS["detail"]),
        ("绿色", "上臂／肩袖：压在身体下面", COLORS["upper_arm"]),
        ("蓝色", "小臂＋前爪：压在上臂下面", COLORS["lower_arm"]),
        ("红色", "小腿＋后爪：压在大腿下面", COLORS["lower_leg"]),
    )
    draw.text((x, y), "图层含义", font=font(27, True), fill="#19324b")
    y += 58
    for color_name, label, color in rows:
        draw.rounded_rectangle((x, y, x + 42, y + 42), radius=6, fill=color[:3])
        draw.text((x + 60, y + 4), f"{color_name}：{label}", font=font(19), fill="#334657")
        y += 65

    draw.line((x, y + 6, 1608, y + 6), fill="#d9e0e6", width=2)
    y += 36
    draw.text((x, y), "遮挡顺序", font=font(25, True), fill="#19324b")
    y += 54
    rules = (
        "1. 身体盖住肩袖内侧，肩部不会断开",
        "2. 上臂盖住小臂接入端，肘部可弯曲",
        "3. 身体盖住大腿髋端，保留髋部体积",
        "4. 大腿盖住小腿接入端，膝部可弯曲",
        "5. 身体盖住尾根，尾巴作为独立动作组",
    )
    for rule in rules:
        draw.text((x, y), rule, font=font(18), fill="#4a5966")
        y += 48

    draw.rounded_rectangle((870, 865, 1622, 986), radius=8, fill="#f7faf8", outline="#b9d5c8", width=2)
    draw.text((894, 884), "这一步只确认：", font=font(20, True), fill="#246951")
    draw.text((1090, 886), "边界位置和父子遮挡是否符合你的草图。", font=font(19), fill="#334657")
    draw.text((894, 934), "确认后才把同一规则映射到侧面和背面。", font=font(18), fill="#5b6874")
    output.save(QA / "x6-user-defined-segmentation-preview-v7.png", optimize=True)

    result = {
        "schemaVersion": 1,
        "stage": "X6-user-defined-front-segmentation-candidate",
        "status": "candidate-for-user-visual-review",
        "userReference": "codex-clipboard-4d07c4c4-7799-42b7-a595-9a866e8a78e1.png",
        "scope": "front-view-boundary-and-occlusion-order-only",
        "groupCount": len(GROUPS),
        "groups": group_stats,
        "occlusionRules": [
            {"child": "upper_arms", "under": ["body", "head"]},
            {"child": "lower_arms", "under": ["upper_arms"]},
            {"child": "upper_legs", "under": ["body"]},
            {"child": "lower_legs", "under": ["upper_legs"]},
            {"child": "tail", "under": ["body"]},
        ],
        "qa": {"preview": "live2d/x6/qa/x6-user-defined-segmentation-preview-v7.png"},
        "gateBoundary": {
            "frontApprovedByUser": False,
            "sideBackPropagationAuthorized": False,
            "gate6Approved": False,
            "x7Authorized": False,
        },
    }
    (X6 / "x6-user-defined-segmentation-contract-v7.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "ok", "groups": len(GROUPS), "preview": result["qa"]["preview"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
