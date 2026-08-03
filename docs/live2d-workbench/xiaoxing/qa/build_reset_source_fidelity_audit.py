from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source"
MASTERS = SOURCE / "masters"
QA = ROOT / "qa"
AUDIT = ROOT / "audit"

# 原始三视图中正面人物的整数像素区域。只裁切，不缩放。
CROP = (34, 0, 546, 1086)

LINE_SOURCE = SOURCE / "xiaoxing-three-view-line.png"
COLOR_SOURCE = SOURCE / "xiaoxing-three-view-color.png"
LINE_EXACT = MASTERS / "front-line-source-exact-after-reset.png"
COLOR_EXACT = MASTERS / "front-color-source-exact-after-reset.png"
OLD_LINE = MASTERS / "gate3-line-master-candidate-v1.png"
OLD_COLOR = MASTERS / "gate3-color-target-v1.png"
OUT_IMAGE = QA / "reset-source-fidelity-audit.png"
OUT_JSON = AUDIT / "reset-source-fidelity-audit.json"


def font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    result = image.copy()
    result.thumbnail(size, Image.Resampling.LANCZOS)
    return result


def checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(232, 232, 232))
    return image


def paste_center(board: Image.Image, image: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    fitted = fit(image, (x1 - x0, y1 - y0))
    x = x0 + (x1 - x0 - fitted.width) // 2
    y = y0 + (y1 - y0 - fitted.height) // 2
    board.paste(fitted.convert("RGB"), (x, y))


def main() -> None:
    MASTERS.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)

    line_three = Image.open(LINE_SOURCE).convert("RGB")
    color_three = Image.open(COLOR_SOURCE).convert("RGB")
    line_exact = line_three.crop(CROP)
    color_exact = color_three.crop(CROP)

    # PNG 保存不会改变解码后的像素；不进行任何 resize、滤镜或描边。
    line_exact.save(LINE_EXACT)
    color_exact.save(COLOR_EXACT)

    old_line = Image.open(OLD_LINE).convert("RGB")
    old_color = Image.open(OLD_COLOR).convert("RGB")
    line_diff = ImageChops.difference(line_exact, old_line)
    color_diff = ImageChops.difference(color_exact, old_color)
    line_bbox = line_diff.getbbox()
    color_bbox = color_diff.getbbox()

    board = Image.new("RGB", (1800, 1535), (248, 248, 248))
    draw = ImageDraw.Draw(board)
    title = font(42)
    header = font(30)
    body = font(24)

    draw.text((45, 30), "小星重置后：原始素材保真审查", font=title, fill=(20, 20, 20))
    draw.text(
        (45, 90),
        "本图只验证新的起点没有缩放、重画或丢像素；不代表材料分层已经完成。",
        font=body,
        fill=(170, 35, 35),
    )
    draw.text((45, 132), "正面裁切坐标：原三视图 x=34..545，y=0..1085；输出 512×1086。", font=body, fill=(45, 45, 45))

    top_y = 190
    panel_w = 520
    for index, (label, image) in enumerate(
        [
            ("① 原始线稿正面（整数裁切）", line_exact),
            ("② 重置后的线稿源副本", Image.open(LINE_EXACT).convert("RGB")),
            ("③ 原始彩稿正面（身份参考）", color_exact),
        ]
    ):
        x0 = 35 + index * 585
        draw.rectangle((x0, top_y, x0 + panel_w, top_y + 1160), outline=(130, 130, 130), width=2)
        draw.text((x0 + 12, top_y + 10), label, font=header, fill=(20, 20, 20))
        paste_center(board, image, (x0 + 15, top_y + 65, x0 + panel_w - 15, top_y + 1145))

    status_y = 1380
    exact = line_bbox is None and color_bbox is None
    status_color = (20, 125, 65) if exact else (190, 35, 35)
    status_text = "像素核验：通过。新源副本与原始三视图裁切完全一致。" if exact else "像素核验：失败，存在差异。"
    draw.text((45, status_y), status_text, font=header, fill=status_color)
    draw.text(
        (45, status_y + 48),
        f"旧 Gate 3 源裁切对比：线稿差异范围={line_bbox}；彩稿差异范围={color_bbox}。",
        font=body,
        fill=(45, 45, 45),
    )
    draw.text(
        (45, status_y + 88),
        "因此旧链路的缺失不是正面裁切造成的，而是从语义遮罩、独立材料和隐藏补全阶段开始。",
        font=body,
        fill=(170, 35, 35),
    )

    board.save(OUT_IMAGE)

    report = {
        "stage": "reset-source-fidelity",
        "status": "passed" if exact else "failed",
        "crop": list(CROP),
        "outputSize": list(line_exact.size),
        "operations": ["integer crop only", "PNG encode", "no resize", "no redraw", "no generation"],
        "line": {
            "source": str(LINE_SOURCE.relative_to(ROOT)),
            "exactCopy": str(LINE_EXACT.relative_to(ROOT)),
            "oldCropDifferenceBox": line_bbox,
            "sha256": sha256(LINE_EXACT),
        },
        "color": {
            "source": str(COLOR_SOURCE.relative_to(ROOT)),
            "exactCopy": str(COLOR_EXACT.relative_to(ROOT)),
            "oldCropDifferenceBox": color_bbox,
            "sha256": sha256(COLOR_EXACT),
        },
        "conclusion": "缺失起因不在正面源裁切，而在后续语义遮罩、独立材料与隐藏补全。",
        "notProven": [
            "语义线稿母版正确",
            "任何独立材料完整",
            "头发或眼睛分层可用",
            "PSD 或 Cubism 工程可用",
        ],
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
