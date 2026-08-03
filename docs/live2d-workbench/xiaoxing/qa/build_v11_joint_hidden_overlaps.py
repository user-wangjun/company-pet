from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
V8 = ROOT / "model" / "working-v8" / "body-original-pixel"
OUT = ROOT / "model" / "working-v11" / "joint-overlaps"
QA = ROOT / "qa" / "v11-sleeve-hand-sock-overlap-review.png"
REPORT = ROOT / "audit" / "v11-joint-overlap-validation.json"
CANVAS = (512, 1086)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def polygon_mask(points: list[tuple[int, int]]) -> np.ndarray:
    image = Image.new("L", CANVAS, 0)
    ImageDraw.Draw(image).polygon(points, fill=255)
    return np.asarray(image) > 0


def load_layer(name: str) -> tuple[Image.Image, np.ndarray]:
    image = Image.open(V8 / name).convert("RGBA")
    return image, np.asarray(image)[:, :, 3] > 0


def rgba(rgb: np.ndarray, mask: np.ndarray) -> Image.Image:
    result = np.zeros((CANVAS[1], CANVAS[0], 4), dtype=np.uint8)
    result[:, :, :3] = rgb
    result[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
    return Image.fromarray(result, "RGBA")


def median_fill(
    source: np.ndarray,
    sample_mask: np.ndarray,
    hidden_mask: np.ndarray,
    max_variation: float = 2.0,
) -> np.ndarray:
    result = source.copy()
    yy, xx = np.indices(sample_mask.shape)
    pixels = source[sample_mask]
    if len(pixels) < 10:
        raise ValueError("隐藏补全的同材质样本不足")
    base = np.median(pixels, axis=0)
    center_x = float(np.mean(xx[sample_mask]))
    xs = xx[hidden_mask]
    variation = ((xs - center_x) / 55.0)[:, None] * np.array(
        [max_variation, max_variation, max_variation * 0.7]
    )[None, :]
    result[hidden_mask] = np.clip(base[None, :] + variation, base - 3, base + 3).astype(np.uint8)
    return result


def checker(size: tuple[int, int], cell: int = 10) -> Image.Image:
    w, h = size
    yy, xx = np.indices((h, w))
    board = (xx // cell + yy // cell) % 2
    values = np.where(board[:, :, None] == 0, 239, 207).astype(np.uint8)
    return Image.fromarray(np.repeat(values, 3, axis=2), "RGB")


def crop_checker(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    crop = image.crop(box).convert("RGBA")
    bg = checker(crop.size)
    bg.paste(crop, (0, 0), crop)
    return bg


def fit_panel(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    panel = Image.new("RGB", size, "white")
    copy = image.copy()
    copy.thumbnail((size[0] - 16, size[1] - 16), Image.Resampling.NEAREST)
    panel.paste(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return panel


def shift_layer(image: Image.Image, dx: int, dy: int) -> Image.Image:
    shifted = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    shifted.paste(image, (dx, dy), image)
    return shifted


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    QA.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    source_image = Image.open(SOURCE).convert("RGB")
    line_image = Image.open(LINE).convert("RGB")
    source = np.asarray(source_image)
    if source_image.size != CANVAS or line_image.size != CANVAS:
        raise ValueError("线稿和彩稿必须保持 512×1086 原始坐标")

    sleeve_left_raw, sleeve_left_mask = load_layer("03_sleeve_screen_left.png")
    sleeve_right_raw, sleeve_right_mask = load_layer("04_sleeve_screen_right.png")
    _, arm_left_mask = load_layer("05_arm_screen_left_forearm.png")
    _, arm_right_mask = load_layer("06_arm_screen_right_forearm.png")
    _, hand_left_mask = load_layer("07_hand_screen_left.png")
    _, hand_right_mask = load_layer("08_hand_screen_right.png")
    _, sock_left_mask = load_layer("13_sock_screen_left.png")
    _, sock_right_mask = load_layer("14_sock_screen_right.png")
    shoe_left_raw, shoe_left_mask = load_layer("15_shoe_screen_left.png")
    shoe_right_raw, shoe_right_mask = load_layer("16_shoe_screen_right.png")

    yy = np.indices((CANVAS[1], CANVAS[0]))[0]
    r = source[:, :, 0].astype(np.int16)
    g = source[:, :, 1].astype(np.int16)
    b = source[:, :, 2].astype(np.int16)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b

    # Forearm + bracelet + whole hand stay together. This removes an unnecessary
    # wrist seam because the requested motion set has no fist or finger action.
    limb_left_visible = (arm_left_mask | hand_left_mask) & ~sleeve_left_mask
    limb_right_visible = (arm_right_mask | hand_right_mask) & ~sleeve_right_mask

    sleeve_left_shadow = arm_left_mask & (yy >= 370) & (yy <= 398) & (luminance < 175)
    sleeve_right_shadow = arm_right_mask & (yy >= 370) & (yy <= 398) & (luminance < 175)
    sleeve_left_effective = sleeve_left_mask | sleeve_left_shadow
    sleeve_right_effective = sleeve_right_mask | sleeve_right_shadow
    limb_left_visible &= ~sleeve_left_shadow
    limb_right_visible &= ~sleeve_right_shadow

    hidden_arm_left = polygon_mask(
        [(128, 357), (153, 365), (166, 375), (160, 405), (132, 406), (123, 385)]
    ) & sleeve_left_effective
    hidden_arm_right = polygon_mask(
        [(346, 375), (359, 365), (384, 357), (389, 385), (382, 406), (354, 405)]
    ) & sleeve_right_effective

    skin_sample_left = limb_left_visible & (yy >= 398) & (yy <= 485) & (r - g > 8) & (r - b > 12)
    skin_sample_right = limb_right_visible & (yy >= 398) & (yy <= 485) & (r - g > 8) & (r - b > 12)
    limb_left_rgb = median_fill(source, skin_sample_left, hidden_arm_left)
    limb_right_rgb = median_fill(source, skin_sample_right, hidden_arm_right)
    limb_left_layer = rgba(limb_left_rgb, limb_left_visible | hidden_arm_left)
    limb_right_layer = rgba(limb_right_rgb, limb_right_visible | hidden_arm_right)
    limb_left_layer = Image.alpha_composite(limb_left_layer, rgba(source, limb_left_visible))
    limb_right_layer = Image.alpha_composite(limb_right_layer, rgba(source, limb_right_visible))
    sleeve_left_layer = rgba(source, sleeve_left_effective)
    sleeve_right_layer = rgba(source, sleeve_right_effective)

    # Socks extend into the rigid shoes. Shoe-edge pixels move with the shoe so
    # they cannot remain as a dark horizontal scar on the sock.
    shoe_left_shadow = sock_left_mask & (yy >= 936) & (yy <= 956) & (luminance < 190)
    shoe_right_shadow = sock_right_mask & (yy >= 936) & (yy <= 956) & (luminance < 190)
    shoe_left_effective = shoe_left_mask | shoe_left_shadow
    shoe_right_effective = shoe_right_mask | shoe_right_shadow
    sock_left_visible = sock_left_mask & ~shoe_left_effective
    sock_right_visible = sock_right_mask & ~shoe_right_effective
    hidden_sock_left = polygon_mask(
        [(169, 925), (219, 925), (221, 950), (213, 958), (178, 958), (167, 951)]
    ) & shoe_left_effective
    hidden_sock_right = polygon_mask(
        [(274, 925), (326, 925), (331, 951), (322, 958), (287, 958), (272, 951)]
    ) & shoe_right_effective

    sock_sample_left = sock_left_visible & (yy >= 885) & (yy <= 932) & (luminance > 185)
    sock_sample_right = sock_right_visible & (yy >= 885) & (yy <= 932) & (luminance > 185)
    sock_left_rgb = median_fill(source, sock_sample_left, hidden_sock_left, max_variation=1.0)
    sock_right_rgb = median_fill(source, sock_sample_right, hidden_sock_right, max_variation=1.0)
    sock_left_layer = rgba(sock_left_rgb, sock_left_visible | hidden_sock_left)
    sock_right_layer = rgba(sock_right_rgb, sock_right_visible | hidden_sock_right)
    sock_left_layer = Image.alpha_composite(sock_left_layer, rgba(source, sock_left_visible))
    sock_right_layer = Image.alpha_composite(sock_right_layer, rgba(source, sock_right_visible))
    shoe_left_layer = rgba(source, shoe_left_effective)
    shoe_right_layer = rgba(source, shoe_right_effective)

    all_visible_union = (
        limb_left_visible
        | limb_right_visible
        | sleeve_left_effective
        | sleeve_right_effective
        | sock_left_visible
        | sock_right_visible
        | shoe_left_effective
        | shoe_right_effective
    )
    residual = rgba(source, ~all_visible_union)
    default = residual.copy()
    for part in (
        limb_left_layer,
        limb_right_layer,
        sleeve_left_layer,
        sleeve_right_layer,
        sock_left_layer,
        sock_right_layer,
        shoe_left_layer,
        shoe_right_layer,
    ):
        default = Image.alpha_composite(default, part)
    diff = ImageChops.difference(default.convert("RGB"), source_image)
    diff_array = np.asarray(diff)
    mae = float(diff_array.mean())
    max_error = int(diff_array.max())

    outputs = {
        "画面左前臂手链整手_含袖内补全.png": limb_left_layer,
        "画面右前臂手链整手_含袖内补全.png": limb_right_layer,
        "画面左袖子_原像素.png": sleeve_left_layer,
        "画面右袖子_原像素.png": sleeve_right_layer,
        "画面左袜_含鞋内补全.png": sock_left_layer,
        "画面右袜_含鞋内补全.png": sock_right_layer,
        "画面左鞋_原像素.png": shoe_left_layer,
        "画面右鞋_原像素.png": shoe_right_layer,
        "默认合成_零误差.png": default,
    }
    for name, image in outputs.items():
        image.save(OUT / name)

    limbs_only = Image.alpha_composite(limb_left_layer, limb_right_layer)
    sleeve_stress = residual.copy()
    sleeve_stress = Image.alpha_composite(sleeve_stress, limb_left_layer)
    sleeve_stress = Image.alpha_composite(sleeve_stress, limb_right_layer)
    sleeve_stress = Image.alpha_composite(sleeve_stress, shift_layer(sleeve_left_layer, -8, -14))
    sleeve_stress = Image.alpha_composite(sleeve_stress, shift_layer(sleeve_right_layer, 8, -14))

    socks_only = Image.alpha_composite(sock_left_layer, sock_right_layer)
    shoe_stress = residual.copy()
    shoe_stress = Image.alpha_composite(shoe_stress, sock_left_layer)
    shoe_stress = Image.alpha_composite(shoe_stress, sock_right_layer)
    shoe_stress = Image.alpha_composite(shoe_stress, shift_layer(shoe_left_layer, -3, 16))
    shoe_stress = Image.alpha_composite(shoe_stress, shift_layer(shoe_right_layer, 3, 16))

    arm_box = (55, 330, 460, 635)
    foot_box = (145, 845, 365, 1065)
    entries = [
        ("① 原始袖口与双臂", source_image.crop(arm_box)),
        ("② 前臂+手链+整手完整层", crop_checker(limbs_only, arm_box)),
        ("③ 袖子外移/上移压力检查", crop_checker(sleeve_stress, arm_box)),
        ("④ 原始袜口与鞋", source_image.crop(foot_box)),
        ("⑤ 双袜完整层（含鞋内）", crop_checker(socks_only, foot_box)),
        ("⑥ 鞋下移 16px 压力检查", crop_checker(shoe_stress, foot_box)),
    ]
    panel_size = (360, 390)
    title_h = 62
    footer_h = 158
    sheet = Image.new("RGB", (panel_size[0] * 3, (panel_size[1] + title_h) * 2 + footer_h), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (title, image) in enumerate(entries):
        row, col = divmod(index, 3)
        x = col * panel_size[0]
        y = row * (panel_size[1] + title_h)
        draw.text((x + 14, y + 16), title, fill="#171717", font=font(20))
        fitted = fit_panel(image, panel_size)
        sheet.paste(fitted, (x, y + title_h))
        draw.rectangle(
            (x, y + title_h, x + panel_size[0] - 1, y + title_h + panel_size[1] - 1),
            outline="#777777",
            width=2,
        )

    footer_y = (panel_size[1] + title_h) * 2 + 14
    draw.text(
        (18, footer_y),
        "手腕策略：每侧前臂、手链和整只手合并为一个活动层；不拆手指，也不制造无动作价值的腕部接缝。",
        fill="#222222",
        font=font(19),
    )
    draw.text(
        (18, footer_y + 41),
        "袖内手臂和鞋内袜子使用各自可见材质补全；边缘阴影归入上方遮挡层，移动后不留下黑线。",
        fill="#222222",
        font=font(19),
    )
    draw.text(
        (18, footer_y + 84),
        f"默认合成：MAE={mae:.3f}，最大通道差={max_error}；压力图仅用于暴露接缝，不代表正式动作幅度。",
        fill="#8D251E",
        font=font(20),
    )
    sheet.save(QA)

    REPORT.write_text(
        json.dumps(
            {
                "stage": "v11-sleeve-hand-sock-hidden-overlaps",
                "source": str(SOURCE.relative_to(ROOT)),
                "lineReference": str(LINE.relative_to(ROOT)),
                "handPolicy": "forearm_bracelet_whole_hand_one_layer_per_side",
                "fingerLayers": False,
                "wristJoint": False,
                "leftHiddenArmPixels": int(hidden_arm_left.sum()),
                "rightHiddenArmPixels": int(hidden_arm_right.sum()),
                "leftHiddenSockPixels": int(hidden_sock_left.sum()),
                "rightHiddenSockPixels": int(hidden_sock_right.sum()),
                "sleeveStressOffset": {"left": [-8, -14], "right": [8, -14]},
                "shoeStressOffset": {"left": [-3, 16], "right": [3, 16]},
                "defaultCompositeMae": mae,
                "defaultCompositeMaxError": max_error,
                "visiblePixelsRepainted": False,
                "hiddenFillVisibleInDefault": False,
                "psdImport": False,
                "cubismImport": False,
                "next": "visual-review_then_long-hair-print-refinement",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
