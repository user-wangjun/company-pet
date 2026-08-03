from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PET = Path(__file__).resolve().parents[2]
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
V10 = X6 / "x6-front-complete-overlap-contract-v10.json"
V11 = X6 / "x6-head-hidden-texture-contract-v11.json"
CANVAS = (650, 887)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def checker(size: tuple[int, int], block: int = 16) -> Image.Image:
    image = Image.new("RGBA", size, (250, 251, 252, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(226, 232, 237, 255))
    return image


def place(path: str, bounds: list[int]) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    canvas.alpha_composite(Image.open(PET / path).convert("RGBA"), (bounds[0], bounds[1]))
    return canvas


def fit(image: Image.Image, size: tuple[int, int], padding: int = 12) -> Image.Image:
    target = checker(size)
    source = image.copy()
    source.thumbnail((size[0] - padding * 2, size[1] - padding * 2), Image.Resampling.LANCZOS)
    target.alpha_composite(source, ((size[0] - source.width) // 2, (size[1] - source.height) // 2))
    return target


def compose(
    order: list[str],
    layers: dict[str, Image.Image],
    offsets: dict[str, tuple[int, int]] | None = None,
) -> Image.Image:
    result = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for layer_id in order:
        dx, dy = (offsets or {}).get(layer_id, (0, 0))
        result.alpha_composite(layers[layer_id], (dx, dy))
    return result


def crop_alpha(image: Image.Image, fallback: tuple[int, int, int, int] = (0, 0, 650, 887)) -> Image.Image:
    bounds = image.getchannel("A").getbbox()
    return image.crop(bounds or fallback)


def panel(
    output: Image.Image,
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    image: Image.Image,
    color: str,
    crop: tuple[int, int, int, int] | None = None,
) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=8, fill="white", outline="#c9d4df", width=2)
    draw.text((x1 + 22, y1 + 18), label, font=font(23, True), fill=color)
    source = image.crop(crop) if crop else crop_alpha(image)
    fitted = fit(source, (x2 - x1 - 40, y2 - y1 - 76), 12)
    output.paste(fitted.convert("RGB"), (x1 + 20, y1 + 60))


def main() -> None:
    v10 = json.loads(V10.read_text(encoding="utf-8"))
    v11 = json.loads(V11.read_text(encoding="utf-8"))
    layers = {row["id"]: place(row["file"], row["canvasBounds"]) for row in v10["layers"]}
    layers["head"] = place(v11["outputLayer"], v11["canvasBounds"])
    reconstruction = compose(v10["drawOrderBackToFront"], layers)

    output = Image.new("RGB", (1800, 1260), "#f3f6f8")
    draw = ImageDraw.Draw(output)
    draw.text((48, 25), "小橘 X6：当前头底修正版 v13", font=font(39, True), fill="#18344f")
    draw.text(
        (50, 80),
        "仅显示当前自然毛流修正版；已否决的放射状旧图不再混入审核入口。",
        font=font(20),
        fill="#586a78",
    )

    panel(output, draw, (42, 125, 722, 800), "完整头底（眼、嘴、耳已移开）", layers["head"], "#20634e")
    panel(output, draw, (752, 125, 1218, 800), "装回后的完整小橘", reconstruction, "#245b88")
    panel(
        output,
        draw,
        (1248, 125, 1758, 800),
        "脸部正常覆盖近看",
        reconstruction,
        "#245b88",
        crop=(185, 35, 485, 395),
    )

    draw.rounded_rectangle((42, 830, 1758, 1215), radius=8, fill="white", outline="#c9d4df", width=2)
    draw.text((64, 850), "遮挡层移开检查", font=font(25, True), fill="#245b88")
    draw.text(
        (64, 890),
        "从左到右只移动遮挡层，头底保持原位；重点看眼窝、鼻口与耳根下面是否连续。",
        font=font(18),
        fill="#60717f",
    )

    frames = [
        ("正常", {}),
        ("眼睛外移", {"eye_R": (-72, 0), "eye_L": (72, 0)}),
        ("嘴部下移", {"mouth": (0, 76)}),
        ("眼、嘴、耳全部移开", {"eye_R": (-72, 0), "eye_L": (72, 0), "mouth": (0, 76), "ear_R": (-42, -54), "ear_L": (42, -54)}),
    ]
    for index, (label, offsets) in enumerate(frames):
        frame = compose(v10["drawOrderBackToFront"], layers, offsets)
        crop = frame.crop((175, 20, 495, 430))
        x = 80 + index * 420
        fitted = fit(crop, (380, 245), 8)
        output.paste(fitted.convert("RGB"), (x, 935))
        label_box = draw.textbbox((0, 0), label, font=font(17, True))
        label_width = label_box[2] - label_box[0]
        draw.text((x + (380 - label_width) // 2, 1182), label, font=font(17, True), fill="#344a5b")

    QA.mkdir(parents=True, exist_ok=True)
    preview_path = QA / "x6-head-hidden-texture-review-v13.png"
    output.save(preview_path, optimize=True)

    contract = {
        "schemaVersion": 1,
        "stage": "X6-front-head-hidden-texture-review",
        "status": "candidate-for-user-visual-review",
        "materialSourceContract": "live2d/x6/x6-head-hidden-texture-contract-v11.json",
        "materialUnchangedFromV11": True,
        "preview": "live2d/x6/qa/x6-head-hidden-texture-review-v13.png",
        "supersedesReview": "live2d/x6/qa/x6-head-hidden-texture-review-v12.png",
        "rejectedComparisonsExcluded": [
            "live2d/x6/qa/x6-head-hidden-texture-review-v11.png",
            "live2d/x6/qa/x6-front-complete-overlap-review-v10.png",
        ],
        "reviewFocus": ["eye-socket-hidden-fur", "mouth-hidden-fur", "ear-root-hidden-fur", "rest-reconstruction"],
        "gateBoundary": v11["gateBoundary"],
    }
    (X6 / "x6-head-hidden-texture-review-contract-v13.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": contract["status"], "preview": contract["preview"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
