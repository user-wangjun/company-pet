from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_gate4_eye_preflight import EYES


ROOT = Path(__file__).resolve().parents[1]
MASTERS = ROOT / "source" / "masters"
QA = ROOT / "qa"
OUT = QA / "draft-eye-layers"
AUDIT = ROOT / "audit"


def font(size):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)
    except OSError:
        return ImageFont.load_default()


def quadratic(a, control, b, steps=16):
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * a[0] + 2 * (1 - t) * t * control[0] + t ** 2 * b[0]
        y = (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * control[1] + t ** 2 * b[1]
        points.append((round(x), round(y)))
    return points


def geometry(eye, openness=1.0):
    outer = tuple(eye["outerCorner"])
    inner = tuple(eye["innerCorner"])
    center_y = round((outer[1] + inner[1]) / 2)
    upper_mid = (eye["upperApex"][0], round(center_y + (eye["upperApex"][1] - center_y) * openness))
    lower_mid = (eye["lowerApex"][0], round(center_y + (eye["lowerApex"][1] - center_y) * openness))
    # Solve the quadratic control point so that t=0.5 passes through the
    # measured lid apex. Treating the apex itself as the control point makes
    # the eye opening only half as tall as the source.
    upper_control = (round(2 * upper_mid[0] - (outer[0] + inner[0]) / 2), round(2 * upper_mid[1] - (outer[1] + inner[1]) / 2))
    lower_control = (round(2 * lower_mid[0] - (outer[0] + inner[0]) / 2), round(2 * lower_mid[1] - (outer[1] + inner[1]) / 2))
    top = quadratic(outer, upper_control, inner)
    bottom = quadratic(inner, lower_control, outer)
    return top, bottom, top + bottom[1:]


def render_eye(eye, gaze=0.0, openness=1.0):
    canvas = Image.new("RGBA", (512, 1086), (0, 0, 0, 0))
    top, bottom, opening = geometry(eye, openness)
    opening_mask = Image.new("L", canvas.size, 0)
    if openness > 0.05:
        ImageDraw.Draw(opening_mask).polygon(opening, fill=255)
    sclera = Image.new("RGBA", canvas.size, (247, 229, 223, 255))
    canvas = Image.composite(sclera, canvas, opening_mask)

    iris_center = (round(eye["irisCenter"][0] + gaze * 3), eye["irisCenter"][1])
    radius = eye["irisRadius"]
    iris = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    idraw = ImageDraw.Draw(iris)
    idraw.ellipse((iris_center[0] - radius, iris_center[1] - radius, iris_center[0] + radius, iris_center[1] + radius), fill=(72, 55, 48, 255))
    idraw.ellipse((iris_center[0] - 4, iris_center[1] - 4, iris_center[0] + 4, iris_center[1] + 4), fill=(30, 26, 24, 255))
    idraw.ellipse((iris_center[0] - 4, iris_center[1] - 5, iris_center[0] - 1, iris_center[1] - 2), fill=(245, 241, 235, 245))
    iris.putalpha(Image.composite(iris.getchannel("A"), Image.new("L", canvas.size, 0), opening_mask))
    canvas = Image.alpha_composite(canvas, iris)

    draw = ImageDraw.Draw(canvas)
    if openness > 0.05:
        draw.line(top, fill=(45, 37, 35, 255), width=2, joint="curve")
        draw.line(bottom, fill=(110, 83, 78, 210), width=1, joint="curve")
    else:
        closed_control = ((eye["upperApex"][0] + eye["lowerApex"][0]) // 2, eye["outerCorner"][1] + 1)
        closed = quadratic(tuple(eye["outerCorner"]), closed_control, tuple(eye["innerCorner"]))
        draw.line(closed, fill=(45, 37, 35, 255), width=2, joint="curve")
    return canvas, opening_mask


def crop_preview(image, crop, scale=5):
    return image.crop(crop).resize(((crop[2] - crop[0]) * scale, (crop[3] - crop[1]) * scale), Image.Resampling.NEAREST)


def build_material_layers(eye):
    """Create full-canvas draft responsibilities; these are not final textures."""
    top, bottom, opening = geometry(eye, 1.0)
    mask = Image.new("L", (512, 1086), 0)
    ImageDraw.Draw(mask).polygon(opening, fill=255)
    layers = {}
    layers["eye_mask"] = Image.merge("RGBA", (mask, mask, mask, mask))

    def filled(name, color, alpha=255):
        image = Image.new("RGBA", (512, 1086), (0, 0, 0, 0))
        image_draw = ImageDraw.Draw(image)
        image_draw.polygon(opening, fill=(*color, alpha))
        layers[name] = image

    filled("socket", (224, 177, 169), 105)
    filled("sclera", (247, 229, 223), 255)
    center = eye["irisCenter"]
    radius = eye["irisRadius"]
    iris = Image.new("RGBA", (512, 1086), (0, 0, 0, 0))
    iris_draw = ImageDraw.Draw(iris)
    iris_draw.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), fill=(72, 55, 48, 255))
    layers["iris"] = iris
    pupil = Image.new("RGBA", (512, 1086), (0, 0, 0, 0))
    ImageDraw.Draw(pupil).ellipse((center[0] - 4, center[1] - 4, center[0] + 4, center[1] + 4), fill=(30, 26, 24, 255))
    layers["pupil"] = pupil
    highlight = Image.new("RGBA", (512, 1086), (0, 0, 0, 0))
    ImageDraw.Draw(highlight).ellipse((center[0] - 4, center[1] - 5, center[0] - 1, center[1] - 2), fill=(245, 241, 235, 245))
    layers["highlight"] = highlight
    upper = Image.new("RGBA", (512, 1086), (0, 0, 0, 0))
    ImageDraw.Draw(upper).line(top, fill=(45, 37, 35, 255), width=2, joint="curve")
    layers["upper_lid"] = upper
    lower = Image.new("RGBA", (512, 1086), (0, 0, 0, 0))
    ImageDraw.Draw(lower).line(bottom, fill=(110, 83, 78, 210), width=1, joint="curve")
    layers["lower_lid"] = lower
    return layers


def main():
    color = Image.open(MASTERS / "gate3-color-target-v1.png").convert("RGB")
    OUT.mkdir(parents=True, exist_ok=True)
    states = [
        ("向角色右侧看", -1.0, 1.0),
        ("正视", 0.0, 1.0),
        ("向角色左侧看", 1.0, 1.0),
        ("半眨眼", 0.0, 0.5),
        ("闭眼", 0.0, 0.0),
    ]
    board = Image.new("RGB", (1760, 920), "white")
    draw = ImageDraw.Draw(board)
    draw.text((24, 16), "小星 Gate 4 眼睛运动草稿（眨眼与视线）", fill=(25, 25, 25), font=font(25))
    draw.text((24, 52), "这是几何与遮罩验证，不替代最终纹理；虹膜始终裁切在眼裂内，闭眼时不得漏出眼白。", fill=(75, 75, 75), font=font(16))
    validation = {"status": "pass", "states": {}, "rules": {"gazeRangePixels": 3, "blinkOpenness": [1.0, 0.5, 0.0]}}
    material_manifest = {"status": "draft_only", "canvas": [512, 1086], "eyes": {}}
    for row, side in enumerate(("R", "L")):
        eye = EYES[side]
        y = 105 + row * 395
        draw.text((24, y - 28), eye["label"], fill=(35, 85, 135), font=font(19))
        original = color.crop(eye["crop"]).resize(((eye["crop"][2] - eye["crop"][0]) * 5, (eye["crop"][3] - eye["crop"][1]) * 5), Image.Resampling.NEAREST)
        board.paste(original, (24, y))
        draw.rectangle((24, y, 24 + original.width, y + original.height), outline=(190, 195, 205), width=2)
        draw.text((32, y + 8), "原图", fill=(35, 35, 35), font=font(14), stroke_width=2, stroke_fill="white")
        for index, (label, gaze, openness) in enumerate(states):
            rendered, mask = render_eye(eye, gaze, openness)
            preview = crop_preview(rendered, eye["crop"])
            x = 320 + index * 285
            checker = Image.new("RGB", preview.size, (240, 240, 240))
            cdraw = ImageDraw.Draw(checker)
            for cy in range(0, preview.height, 16):
                for cx in range(0, preview.width, 16):
                    if (cx // 16 + cy // 16) % 2 == 0:
                        cdraw.rectangle((cx, cy, cx + 15, cy + 15), fill=(220, 220, 220))
            checker = checker.convert("RGBA")
            checker.alpha_composite(preview)
            board.paste(checker.convert("RGB"), (x, y))
            draw.rectangle((x, y, x + preview.width, y + preview.height), outline=(190, 195, 205), width=2)
            draw.text((x + 7, y + 7), label, fill=(35, 35, 35), font=font(14), stroke_width=2, stroke_fill="white")
            key = f"{side}_{index}"
            visible_sclera = sum(mask.histogram()[1:])
            validation["states"][key] = {"label": label, "gaze": gaze, "openness": openness, "openingMaskHistogramSum": visible_sclera}
            if label == "正视":
                for material in ("composite", "mask"):
                    path = OUT / f"eye_{side}_{material}.png"
                    (rendered if material == "composite" else Image.merge("RGBA", (mask, mask, mask, mask))).save(path)
        draw.text((24, y + original.height + 14), "原图只用于身份参照；草稿验证眼裂、虹膜移动和眨眼遮罩，不改变脸部比例。", fill=(80, 80, 80), font=font(14))
        material_layers = build_material_layers(eye)
        material_manifest["eyes"][side] = {}
        for material, layer in material_layers.items():
            path = OUT / f"eye_{side}_{material}.png"
            layer.save(path)
            material_manifest["eyes"][side][material] = str(path.relative_to(ROOT)).replace("\\", "/")
    draw.text((24, 885), "自审重点：两眼运动方向一致；虹膜不穿出眼角；半眨眼仍保留瞳孔；闭眼不残留眼白。", fill=(35, 85, 135), font=font(16))
    board.save(QA / "gate4-eye-motion-contact-sheet.png", quality=95)
    material_board = Image.new("RGB", (1760, 720), "white")
    material_draw = ImageDraw.Draw(material_board)
    material_draw.text((24, 16), "小星 Gate 4 眼睛材料职责草稿（全画布透明层）", fill=(25, 25, 25), font=font(24))
    material_draw.text((24, 50), "每只眼睛八层：眼窝、眼白、虹膜、瞳孔、高光、上眼睑、下眼睑、裁切遮罩。", fill=(75, 75, 75), font=font(16))
    material_names = ["socket", "sclera", "iris", "pupil", "highlight", "upper_lid", "lower_lid", "eye_mask"]
    material_labels = {"socket": "眼窝底色", "sclera": "眼白", "iris": "虹膜", "pupil": "瞳孔", "highlight": "高光", "upper_lid": "上眼睑", "lower_lid": "下眼睑", "eye_mask": "眼裂遮罩"}
    for row, side in enumerate(("R", "L")):
        eye = EYES[side]
        y = 105 + row * 295
        material_draw.text((24, y - 27), eye["label"], fill=(35, 85, 135), font=font(18))
        for index, material in enumerate(material_names):
            path = OUT / f"eye_{side}_{material}.png"
            layer = Image.open(path).convert("RGBA")
            preview = crop_preview(layer, eye["crop"], scale=4)
            x = 24 + index * 215
            checker = Image.new("RGB", preview.size, (240, 240, 240))
            checker_draw = ImageDraw.Draw(checker)
            for cy in range(0, preview.height, 14):
                for cx in range(0, preview.width, 14):
                    if (cx // 14 + cy // 14) % 2 == 0:
                        checker_draw.rectangle((cx, cy, cx + 13, cy + 13), fill=(220, 220, 220))
            checker = checker.convert("RGBA")
            checker.alpha_composite(preview)
            material_board.paste(checker.convert("RGB"), (x, y))
            material_draw.rectangle((x, y, x + preview.width, y + preview.height), outline=(190, 195, 205), width=2)
            material_draw.text((x + 6, y + 6), material_labels[material], fill=(35, 35, 35), font=font(13), stroke_width=2, stroke_fill="white")
    material_draw.text((24, 680), "草稿只验证图层职责和遮罩关系；最终颜色、睫毛粗细与虹膜纹理仍以彩色三视图为准。", fill=(35, 85, 135), font=font(15))
    material_board.save(QA / "gate4-eye-material-contact-sheet.png", quality=95)
    (AUDIT / "gate4-eye-motion-validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    (QA / "draft-eye-layers.json").write_text(json.dumps(material_manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
