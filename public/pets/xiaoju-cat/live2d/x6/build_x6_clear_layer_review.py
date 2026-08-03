from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PET = ROOT.parent
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
CONTRACT = X6 / "x6-joint-safe-motion-bundle-contract-v4.json"
AUDIT = X6 / "x6-joint-safe-motion-bundle-audit-v4.json"
REST = QA / "x6-production-layer-stack-rest-v2.png"
CANVAS = (1774, 887)
VIEW_BOUNDS = {
    "front": (0, 0, 650, 887),
    "side": (650, 0, 1120, 887),
    "back": (1120, 0, 1774, 887),
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


def checker(size: tuple[int, int], block: int = 12) -> Image.Image:
    image = Image.new("RGBA", size, (249, 250, 251, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(229, 233, 236, 255))
    return image


def fit(image: Image.Image, size: tuple[int, int], padding: int = 14) -> Image.Image:
    background = checker(size)
    copy = image.copy()
    copy.thumbnail((size[0] - padding * 2, size[1] - padding * 2), Image.Resampling.LANCZOS)
    background.alpha_composite(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return background


def load_full(path: str | None, bounds: list[int] | None) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    if path and bounds:
        canvas.alpha_composite(Image.open(PET / path).convert("RGBA"), (bounds[0], bounds[1]))
    return canvas


def shifted(image: Image.Image, delta: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.alpha_composite(image, delta)
    return canvas


def crop_alpha(image: Image.Image, padding: int = 10) -> Image.Image:
    bounds = image.getchannel("A").getbbox()
    if not bounds:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    bounds = (
        max(0, bounds[0] - padding),
        max(0, bounds[1] - padding),
        min(CANVAS[0], bounds[2] + padding),
        min(CANVAS[1], bounds[3] + padding),
    )
    return image.crop(bounds)


def main() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    records = {(row["view"], row["bundle"]): row for row in contract["exports"]}
    visible = {
        key: load_full(record["visibleFile"], record["visibleBounds"])
        for key, record in records.items()
    }
    collars = {
        key: load_full(record["hiddenCollarFile"], record["hiddenCollarBounds"])
        for key, record in records.items()
    }

    output = Image.new("RGB", (1900, 1650), "#f5f7f9")
    draw = ImageDraw.Draw(output)
    draw.text((54, 28), "小橘 X6：分层到底是什么样", font=font(40, True), fill="#19324b")
    draw.text((56, 84), "这里不显示骨点、网格或彩色技术标记，只看实际毛发素材和移动结果。", font=font(21), fill="#5b6874")

    draw.text((54, 132), "1  静止时：仍然是完整的小橘", font=font(27, True), fill="#19324b")
    rest = Image.open(REST).convert("RGBA")
    for column, (view, label) in enumerate((("front", "正面"), ("side", "侧面"), ("back", "背面"))):
        x = 48 + column * 616
        draw.rounded_rectangle((x, 180, x + 580, 570), radius=8, fill="white", outline="#cbd5df", width=2)
        panel = rest.crop(VIEW_BOUNDS[view])
        output.paste(fit(panel, (552, 340)).convert("RGB"), (x + 14, 212))
        draw.text((x + 257, 188), label, font=font(19, True), fill="#3b4c5d")

    draw.text((54, 608), "2  真正导出的动作组", font=font(27, True), fill="#19324b")
    draw.text((338, 613), "切口藏在相邻层下面；单独拿出来看会有接入端，这是正常的。", font=font(18), fill="#6b7782")
    groups = (
        ("头部和五官", ("head", "mouth", "ear_L", "ear_R", "eye_L", "eye_R"), "内部保留眼、嘴、左右耳"),
        ("身体", ("body",), "完整躯干主体"),
        ("一条前肢", ("arm_R_upper", "arm_R_lower_paw"), "内部为上臂＋小臂/前爪"),
        ("一条后肢", ("leg_R_upper", "leg_R_lower_paw"), "内部为大腿＋小腿/后爪"),
        ("尾巴", ("tail",), "一个动作组"),
    )
    cell_width = 350
    for index, (label, bundle_ids, note) in enumerate(groups):
        x = 48 + index * 365
        y = 662
        draw.rounded_rectangle((x, y, x + cell_width, y + 280), radius=8, fill="white", outline="#cbd5df", width=2)
        piece = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        for bundle_id in bundle_ids:
            piece.alpha_composite(visible[("front", bundle_id)])
        output.paste(fit(crop_alpha(piece), (324, 210), 10).convert("RGB"), (x + 13, y + 36))
        draw.text((x + 14, y + 9), label, font=font(17, True), fill="#245b88")
        draw.text((x + 14, y + 250), note, font=font(14), fill="#74808a")

    draw.text((54, 985), "3  为什么移动时不会断开", font=font(27, True), fill="#19324b")
    draw.text((398, 990), "只演示一条前肢：身体不动，隐藏接入端跟着手臂移动。", font=font(18), fill="#6b7782")
    upper = visible[("front", "arm_R_upper")]
    lower = visible[("front", "arm_R_lower_paw")]
    upper_collar = collars[("front", "arm_R_upper")]
    lower_collar = collars[("front", "arm_R_lower_paw")]
    frames = (
        ("静止", (0, 0), (0, 0)),
        ("整条前肢抬起", (-12, -6), (-12, -6)),
        ("小臂继续展开", (-12, -6), (-20, 2)),
    )
    static_order = (
        "tail",
        "leg_L_upper", "leg_L_lower_paw", "leg_R_upper", "leg_R_lower_paw",
        "body", "head", "mouth", "ear_L", "ear_R", "eye_L", "eye_R",
        "arm_L_upper", "arm_L_lower_paw",
    )
    crop = VIEW_BOUNDS["front"]
    rendered_frames: list[Image.Image] = []
    for index, (label, upper_delta, lower_delta) in enumerate(frames):
        x = 48 + index * 616
        y = 1042
        draw.rounded_rectangle((x, y, x + 580, y + 420), radius=8, fill="white", outline="#cbd5df", width=2)
        frame = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        frame.alpha_composite(shifted(upper_collar, upper_delta))
        frame.alpha_composite(shifted(lower_collar, lower_delta))
        for bundle_id in static_order:
            image = visible.get(("front", bundle_id))
            if image:
                frame.alpha_composite(image)
        frame.alpha_composite(shifted(upper, upper_delta))
        frame.alpha_composite(shifted(lower, lower_delta))
        rendered_frames.append(frame)
        output.paste(fit(frame.crop(crop), (552, 350), 12).convert("RGB"), (x + 14, y + 42))
        draw.text((x + 18, y + 10), f"{index + 1}. {label}", font=font(19, True), fill="#245b88")
        draw.text((x + 18, y + 386), "接缝下方始终有真实毛发像素", font=font(15), fill="#3d806a")

    draw.rounded_rectangle((48, 1502, 1852, 1618), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((72, 1525), "你现在只需要判断两件事：", font=font(21, True), fill="#19324b")
    draw.text((360, 1527), "分组是否自然；手臂移动后视觉上是否仍连贯。", font=font(20), fill="#384958")
    draw.text((72, 1574), f"机器检查：10 px 拉开后 {audit['passCount']}/{audit['jointRecordCount']} 个关节保持连接。当前仍是 X6 候选。", font=font(18), fill="#28765f")
    output.save(QA / "x6-clear-layer-and-overlap-review-v5.png", optimize=True)

    shoulder = Image.new("RGB", (1600, 720), "#f5f7f9")
    shoulder_draw = ImageDraw.Draw(shoulder)
    shoulder_draw.text((46, 24), "前肢肩部重叠放大", font=font(36, True), fill="#19324b")
    shoulder_draw.text((48, 78), "上臂顶部的实心毛面压进身体和颈胸毛下面；三帧均显示最终实际像素，不叠技术色块。", font=font(19), fill="#5b6874")
    shoulder_crop = (130, 270, 330, 445)
    for index, ((label, _, _), frame) in enumerate(zip(frames, rendered_frames)):
        x = 46 + index * 520
        shoulder_draw.rounded_rectangle((x, 125, x + 480, 650), radius=8, fill="white", outline="#cbd5df", width=2)
        shoulder.paste(fit(frame.crop(shoulder_crop), (450, 455), 8).convert("RGB"), (x + 15, 165))
        shoulder_draw.text((x + 18, 137), f"{index + 1}. {label}", font=font(19, True), fill="#245b88")
        shoulder_draw.text((x + 18, 620), "上沿肩面连续；下方棋盘格是正常腋窝", font=font(15), fill="#28765f")
    shoulder.save(QA / "x6-shoulder-overlap-closeup-v6.png", optimize=True)

    result = {
        "schemaVersion": 1,
        "stage": "X6-clear-layer-review-candidate",
        "status": "candidate-for-user-visual-review",
        "sourceBundleContract": "live2d/x6/x6-joint-safe-motion-bundle-contract-v4.json",
        "sourcePullAudit": "live2d/x6/x6-joint-safe-motion-bundle-audit-v4.json",
        "review": "live2d/x6/qa/x6-clear-layer-and-overlap-review-v5.png",
        "shoulderCloseup": "live2d/x6/qa/x6-shoulder-overlap-closeup-v6.png",
        "displayRules": {
            "technicalOverlaysHidden": True,
            "actualFurPixelsOnly": True,
            "singleLimbExplanation": True,
            "userQuestions": ["分组是否自然", "手臂移动后视觉上是否仍连贯"],
        },
        "gateBoundary": {"gate6Approved": False, "x7Authorized": False},
    }
    (X6 / "x6-clear-layer-review-contract-v5.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "ok", "review": result["review"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
