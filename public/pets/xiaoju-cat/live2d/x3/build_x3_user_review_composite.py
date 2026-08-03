from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
QA_DIR = ROOT / "qa"
SOURCE = QA_DIR / "x3-spread-pose-master-blockout.png"
OUT = QA_DIR / "x3-user-review-composite.png"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def main() -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    src = Image.open(SOURCE).convert("RGB")
    W, H = 2200, 1620
    canvas = Image.new("RGB", (W, H), (250, 250, 246))
    draw = ImageDraw.Draw(canvas)

    title = font(34)
    head = font(23)
    body = font(18)
    small = font(15)

    draw.rectangle([0, 0, W, 150], fill=(255, 245, 226))
    draw.text((42, 28), "小橘 X3 母版用户视觉审核总览", fill=(42, 36, 28), font=title)
    draw.text((42, 82), "当前 Gate: x3-candidate-for-user-review | X3 未通过 | X4 分层未授权", fill=(120, 72, 26), font=head)
    draw.text((42, 116), "只审核完整连续大字型/展开三视图母版；不授权正式分层、正式三角剖分、PSD 或 Cubism。", fill=(70, 70, 64), font=body)

    max_w, max_h = W - 84, 1040
    scale = min(max_w / src.width, max_h / src.height)
    resized = src.resize((int(src.width * scale), int(src.height * scale)), Image.Resampling.LANCZOS)
    x = (W - resized.width) // 2
    y = 178
    canvas.paste(resized, (x, y))
    draw.rectangle([x, y, x + resized.width, y + resized.height], outline=(190, 180, 165), width=2)

    panel_y = y + resized.height + 28
    draw.rounded_rectangle([42, panel_y, W - 42, H - 44], radius=8, fill=(238, 246, 247), outline=(190, 214, 218), width=2)
    draw.text((72, panel_y + 24), "X3 通过前要看的 6 件事", fill=(36, 60, 64), font=head)
    checks = [
        "1. 是否仍然像 three-view-preview.png 里的小橘，而不是另一只猫。",
        "2. 正、侧、背是否能看成同一套身体和同一组骨段长度。",
        "3. 隐藏前肢、肩胸连接、尾根、耳根、腹部和后肢是否连续。",
        "4. 幼猫圆润体积是否保留，肋笼、腹部、骨盆和头部没有塌陷。",
        "5. 未来拆层处是否有足够安全重叠，不会一切开就露洞。",
        "6. 是否没有提前画正式图层边界、正式三角剖分或 ArtMesh 顶点。",
    ]
    for i, text in enumerate(checks):
        draw.text((72, panel_y + 72 + i * 34), text, fill=(46, 66, 70), font=body)

    draw.text((72, H - 86), "Gate 决策: 只有明确 “X3 通过” 才能进入 X4 分层；否则继续修 X3 母版。", fill=(122, 54, 34), font=body)
    draw.text((W - 470, H - 28), "Generated from existing X3 candidate only", fill=(120, 120, 112), font=small)
    canvas.save(OUT)
    print(OUT.as_posix())
    print(canvas.size)


if __name__ == "__main__":
    main()
