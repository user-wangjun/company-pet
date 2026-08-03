from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "masters" / "front-line-source-exact-after-reset.png"
COLOR = ROOT / "source" / "masters" / "front-color-source-exact-after-reset.png"
OUT_DIR = ROOT / "model" / "reset-v1" / "head-line-ownership"
QA_IMAGE = ROOT / "qa" / "reset-v1-head-line-ownership-review.png"
AUDIT_JSON = ROOT / "audit" / "reset-v1-head-line-ownership.json"

CANVAS = (512, 1086)


def font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def polygon_mask(points: list[tuple[int, int]]) -> np.ndarray:
    image = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(image).polygon(points, fill=255)
    return np.asarray(image) > 0


def box_mask(box: tuple[int, int, int, int]) -> np.ndarray:
    image = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(image).rectangle(box, fill=255)
    return np.asarray(image) > 0


def make_layer(source: np.ndarray, owned: np.ndarray) -> Image.Image:
    rgba = np.zeros((CANVAS[1], CANVAS[0], 4), dtype=np.uint8)
    rgba[owned, :3] = source[owned, :3]
    rgba[owned, 3] = 255
    return Image.fromarray(rgba, "RGBA")


def checker(size: tuple[int, int], cell: int = 16) -> Image.Image:
    result = Image.new("RGB", size, (247, 247, 247))
    draw = ImageDraw.Draw(result)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(229, 229, 229))
    return result


def panel_from_full_canvas(layer: Image.Image) -> Image.Image:
    # 审查单元始终接收完整 512×1086 图层，不做局部裁切。
    background = checker(CANVAS)
    background.paste(layer.convert("RGB"), (0, 0), layer.getchannel("A"))
    return background


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale_png in OUT_DIR.glob("*.png"):
        stale_png.unlink()
    source_image = Image.open(SOURCE).convert("RGB")
    color_image = Image.open(COLOR).convert("RGB")
    if source_image.size != CANVAS or color_image.size != CANVAS:
        raise ValueError("source canvas must be 512x1086")

    source = np.asarray(source_image)
    gray = np.asarray(source_image.convert("L"))
    # 原线稿背景含大量 253–254 的浅灰压缩/渐变像素；它们不是可见线条。
    # 240 以下保留主体线条及抗锯齿边缘，并避免把背景噪点输出成材料。
    ink = gray < 240

    color_gray = color_image.convert("L")
    # 用局部平均亮度识别“黑色发块”，避免把白色衣服上的黑色印花误当成头发。
    # 单个印花笔画周围仍是亮色，密集头发周围则保持低亮度。
    hair_local_mean = color_gray.filter(ImageFilter.BoxBlur(6))
    dark_hair_seed = hair_local_mean.point(lambda value: 255 if value < 155 else 0)
    dark_hair_seed = dark_hair_seed.filter(ImageFilter.MaxFilter(9))
    dark_hair = np.asarray(dark_hair_seed) > 0

    # 只允许头发候选存在于实际头发轮廓内；该轮廓不直接成为材料，
    # 只用于把原线稿像素分配到语义层。
    hair_envelope = polygon_mask(
        [
            (137, 20), (256, 4), (375, 22), (401, 140), (391, 295),
            (372, 475), (322, 510), (286, 405), (256, 365),
            (226, 405), (190, 510), (140, 475), (121, 295), (111, 140),
        ]
    )
    upper_hair = polygon_mask(
        [(122, 15), (390, 15), (405, 285), (330, 330), (256, 275), (182, 330), (107, 285)]
    )
    lower_hair_screen_left = polygon_mask(
        [(120, 150), (222, 135), (224, 230), (212, 280), (203, 330), (198, 415), (188, 505), (145, 485), (125, 350)]
    )
    lower_hair_screen_right = polygon_mask(
        [(392, 150), (290, 135), (288, 230), (300, 280), (309, 330), (314, 415), (324, 505), (367, 485), (387, 350)]
    )
    hair_visibility_shape = upper_hair | lower_hair_screen_left | lower_hair_screen_right
    hair_geometry = dark_hair & hair_envelope & hair_visibility_shape

    masks: list[tuple[str, np.ndarray]] = []

    # 双眼范围按原线稿眼裂逐侧包围；这里只提取原线稿像素，不重描眼形。
    eye_screen_left = polygon_mask(
        [(204, 120), (214, 112), (242, 112), (256, 120), (256, 139), (244, 148), (215, 148), (204, 138)]
    )
    eye_screen_right = polygon_mask(
        [(262, 120), (278, 112), (303, 112), (316, 120), (316, 138), (304, 148), (276, 148), (262, 139)]
    )
    face_features = (
        polygon_mask([(240, 142), (273, 142), (280, 199), (257, 215), (233, 198)])
        | box_mask((248, 204, 266, 218))
    )

    # 前发只负责原图中实际位于脸前的发丝。侧发采用左右独立层；
    # 后发接收头发轮廓中剩余的原线稿像素。
    front_center = polygon_mask(
        [
            (195, 40), (256, 25), (317, 40), (330, 85), (320, 140),
            (290, 156), (256, 142), (220, 156), (190, 140), (182, 85),
        ]
    )
    front_screen_left = polygon_mask(
        [
            (124, 75), (188, 55), (219, 105), (220, 175), (210, 250),
            (205, 405), (188, 505), (148, 480), (128, 350), (116, 180),
        ]
    )
    front_screen_right = polygon_mask(
        [
            (388, 75), (324, 55), (293, 105), (292, 175), (302, 250),
            (307, 405), (324, 505), (364, 480), (384, 350), (396, 180),
        ]
    )
    face_contour = polygon_mask(
        [(194, 112), (218, 84), (294, 84), (318, 112), (321, 180), (300, 234), (256, 260), (212, 234), (191, 180)]
    )

    candidates = [
        ("01_画面左眼_原线稿像素", eye_screen_left),
        ("02_画面右眼_原线稿像素", eye_screen_right),
        ("03_鼻口_原线稿像素", face_features),
        ("04_中央刘海_原线稿像素", front_center & hair_geometry),
        ("05_画面左侧发_原线稿像素", front_screen_left & hair_geometry),
        ("06_画面右侧发_原线稿像素", front_screen_right & hair_geometry),
        ("07_脸轮廓与耳_原线稿像素", face_contour),
        ("08_后发_原线稿像素", hair_geometry),
    ]

    remaining = ink.copy()
    for name, candidate in candidates:
        owned = candidate & remaining & ink
        masks.append((name, owned))
        remaining &= ~owned

    # 头部范围内仍未归属的线稿像素单独暴露，不能藏进默认遮挡。
    head_review_area = (
        hair_visibility_shape
        | face_contour
        | eye_screen_left
        | eye_screen_right
        | face_features
    )
    unresolved = remaining & head_review_area
    remaining &= ~unresolved
    masks.append(("09_头部待判定像素_必须清零", unresolved))
    masks.append(("10_身体锁定参考_非本轮材料", remaining))

    layers: dict[str, Image.Image] = {}
    for name, owned in masks:
        layer = make_layer(source, owned)
        layer.save(OUT_DIR / f"{name}.png")
        layers[name] = layer

    # 使用全部导出层重新合成，验证没有通过背景图偷补。
    normalized_reference_array = np.full_like(source, 255)
    normalized_reference_array[ink] = source[ink]
    normalized_reference = Image.fromarray(normalized_reference_array, "RGB")
    composite = Image.new("RGBA", CANVAS, (255, 255, 255, 255))
    for name, _ in reversed(masks):
        composite = Image.alpha_composite(composite, layers[name])
    composite_rgb = composite.convert("RGB")
    diff = ImageChops.difference(normalized_reference, composite_rgb)

    layer_names = [name for name, _ in masks[:9]]
    panel_w, panel_h = 512, 1086
    columns = 4
    rows = 3
    margin_x, margin_y = 24, 130
    gap_x, gap_y = 26, 92
    board_w = margin_x * 2 + columns * panel_w + (columns - 1) * gap_x
    board_h = margin_y + rows * panel_h + (rows - 1) * gap_y + 160
    board = Image.new("RGB", (board_w, board_h), (248, 248, 248))
    draw = ImageDraw.Draw(board)
    title_font = font(40)
    label_font = font(25)
    note_font = font(22)
    draw.text((24, 20), "小星 Reset V1：头部原线稿像素所有权（全画布图层）", font=title_font, fill=(20, 20, 20))
    draw.text(
        (24, 72),
        "每格均为完整 512×1086 透明图层的 1:1 预览；没有局部裁切、缩放贴回、补色或重描。",
        font=note_font,
        fill=(170, 35, 35),
    )

    for index, name in enumerate(layer_names):
        row, col = divmod(index, columns)
        x = margin_x + col * (panel_w + gap_x)
        y = margin_y + row * (panel_h + gap_y)
        panel = panel_from_full_canvas(layers[name])
        board.paste(panel, (x, y))
        draw.rectangle((x, y, x + panel_w - 1, y + panel_h - 1), outline=(135, 135, 135), width=2)
        draw.text((x, y + panel_h + 10), name, font=label_font, fill=(25, 25, 25))

    unresolved_count = int(unresolved.sum())
    diff_bbox = diff.getbbox()
    summary_y = board_h - 125
    draw.text(
        (24, summary_y),
        f"头部待判定线稿像素：{unresolved_count}；全部图层回组差异范围：{diff_bbox}。",
        font=note_font,
        fill=(20, 125, 65) if diff_bbox is None else (180, 35, 35),
    )
    draw.text(
        (24, summary_y + 42),
        "本轮只做可见线稿归属；隐藏脸底、完整后发、眼白与虹膜尚未绘制，不能导入 PSD/Cubism。",
        font=note_font,
        fill=(170, 35, 35),
    )
    board.save(QA_IMAGE)

    report = {
        "stage": "reset-v1-head-visible-line-ownership",
        "status": "visual_review_required",
        "canvas": list(CANVAS),
        "source": str(SOURCE.relative_to(ROOT)),
        "colorGeometryReference": str(COLOR.relative_to(ROOT)),
        "layerCount": len(masks),
        "allLayersFullCanvas": all(image.size == CANVAS for image in layers.values()),
        "headUnresolvedInkPixels": unresolved_count,
        "roundtripDifferenceBox": diff_bbox,
        "rules": {
            "sourcePixelsOnly": True,
            "noCropAsLayer": True,
            "noResize": True,
            "noRedraw": True,
            "noHiddenFillYet": True,
            "notPsdOrCubismReady": True,
        },
        "layers": [
            {
                "name": name,
                "path": str((OUT_DIR / f"{name}.png").relative_to(ROOT)),
                "ownedInkPixels": int(mask.sum()),
            }
            for name, mask in masks
        ],
    }
    AUDIT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
