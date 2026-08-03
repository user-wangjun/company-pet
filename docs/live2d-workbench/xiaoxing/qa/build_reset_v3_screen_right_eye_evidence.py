from __future__ import annotations

from pathlib import Path
import json

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
LINE_PATH = ROOT / "source" / "masters" / "front-line-source-exact-after-reset.png"
COLOR_PATH = ROOT / "source" / "masters" / "front-color-source-exact-after-reset.png"
OUTPUT = ROOT / "qa" / "reset-v3-screen-right-eye-pixel-evidence.png"
AUDIT = ROOT / "audit" / "reset-v3-screen-right-eye-evidence.json"

# 画面右眼的局部审查范围。右、下边界不包含在裁切中。
CROP = (246, 110, 312, 155)
SCALE = 12


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = (
        ("msyhbd.ttc", "msyh.ttc")
        if bold
        else ("msyh.ttc", "msyhbd.ttc")
    )
    for name in names:
        path = Path(r"C:\Windows\Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def add_source_grid(
    image: Image.Image,
    *,
    source_origin: tuple[int, int],
    scale: int,
) -> Image.Image:
    result = image.convert("RGB")
    draw = ImageDraw.Draw(result)
    width, height = result.size
    origin_x, origin_y = source_origin

    for x in range(0, width + 1, scale):
        source_x = origin_x + x // scale
        color = (40, 130, 210) if source_x % 5 == 0 else (185, 215, 235)
        draw.line((x, 0, x, height), fill=color, width=1)
    for y in range(0, height + 1, scale):
        source_y = origin_y + y // scale
        color = (40, 130, 210) if source_y % 5 == 0 else (185, 215, 235)
        draw.line((0, y, width, y), fill=color, width=1)
    return result


def threshold_map(line_crop: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(line_crop)
    # 只做证据观察：越黑越接近线稿中心，绝不作为自动分层遮罩。
    mapped = Image.new("RGB", gray.size, (255, 255, 255))
    src = gray.load()
    dst = mapped.load()
    for y in range(gray.height):
        for x in range(gray.width):
            value = src[x, y]
            if value <= 80:
                dst[x, y] = (20, 20, 20)
            elif value <= 145:
                dst[x, y] = (215, 45, 55)
            elif value <= 205:
                dst[x, y] = (245, 155, 35)
            else:
                dst[x, y] = (255, 255, 255)
    return mapped


def main() -> None:
    line = Image.open(LINE_PATH).convert("RGB")
    color = Image.open(COLOR_PATH).convert("RGB")
    if line.size != (512, 1086) or color.size != (512, 1086):
        raise ValueError(f"正面母版尺寸异常：line={line.size}, color={color.size}")

    line_crop = line.crop(CROP)
    color_crop = color.crop(CROP)
    threshold_crop = threshold_map(line_crop)

    panels = []
    for label, crop, show_grid in (
        ("① 原始线稿（无叠加）", line_crop, False),
        ("② 原始彩稿（无叠加）", color_crop, False),
        ("③ 原始线稿坐标网格", line_crop, True),
        ("④ 线稿深浅证据（不可作遮罩）", threshold_crop, True),
    ):
        enlarged = crop.resize(
            (crop.width * SCALE, crop.height * SCALE),
            Image.Resampling.NEAREST,
        )
        if show_grid:
            enlarged = add_source_grid(
                enlarged,
                source_origin=(CROP[0], CROP[1]),
                scale=SCALE,
            )
        panels.append((label, enlarged))

    margin = 24
    gap = 22
    title_h = 142
    label_h = 58
    panel_w, panel_h = panels[0][1].size
    board_w = margin * 2 + panel_w * 4 + gap * 3
    board_h = title_h + panel_h + label_h + 100
    board = Image.new("RGB", (board_w, board_h), (248, 248, 248))
    draw = ImageDraw.Draw(board)
    draw.text(
        (margin, 16),
        "小星 Reset V3：画面右眼像素级证据板",
        font=font(38, bold=True),
        fill=(20, 20, 20),
    )
    draw.text(
        (margin, 64),
        "裁切范围 x=246…311，y=110…154；12×最近邻放大。第③④栏蓝色粗网格每 5 个原图像素。",
        font=font(22),
        fill=(45, 45, 45),
    )
    draw.text(
        (margin, 98),
        "本图仅用于定位，不是材料。第①栏保留无叠加原线，禁止从第④栏自动生成遮罩。",
        font=font(22),
        fill=(180, 35, 35),
    )

    for index, (label, panel) in enumerate(panels):
        x = margin + index * (panel_w + gap)
        y = title_h
        board.paste(panel, (x, y))
        draw.rectangle(
            (x, y, x + panel_w - 1, y + panel_h - 1),
            outline=(105, 105, 105),
            width=2,
        )
        draw.text(
            (x, y + panel_h + 12),
            label,
            font=font(21),
            fill=(20, 20, 20),
        )

    draw.text(
        (margin, board_h - 58),
        "人工追踪顺序：内眼角 → 上眼线峰值 → 外眼角 → 下眼线最低点 → 回到内眼角。",
        font=font(22),
        fill=(25, 85, 135),
    )
    board.save(OUTPUT)

    AUDIT.write_text(
        json.dumps(
            {
                "stage": "reset-v3-screen-right-eye-pixel-evidence",
                "status": "visual_review_required",
                "canvas": [512, 1086],
                "cropInclusive": {
                    "x": [CROP[0], CROP[2] - 1],
                    "y": [CROP[1], CROP[3] - 1],
                },
                "scale": SCALE,
                "resampling": "nearest",
                "lineSource": str(LINE_PATH.relative_to(ROOT)),
                "colorReference": str(COLOR_PATH.relative_to(ROOT)),
                "reviewOnly": True,
                "materialGenerated": False,
                "iterationNotes": [
                    "第一版 x=268…329 截掉眼睛内侧，工作自审未通过。",
                    "第二版扩大为 x=246…311，并同时保留无叠加线稿和坐标网格。",
                ],
                "prohibited": [
                    "从阈值图直接生成眼睛遮罩",
                    "把局部裁切作为材料",
                    "在人工边界通过前生成 PSD 或 Cubism",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
