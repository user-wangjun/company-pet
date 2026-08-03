from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
LINE = ROOT / "source" / "masters" / "gate3-line-master-candidate-v1.png"
V8 = ROOT / "model" / "working-v8" / "body-original-pixel"
V9 = ROOT / "model" / "working-v9" / "long-hair-shirt"
V10 = ROOT / "model" / "working-v10" / "hidden-thigh"
V11 = ROOT / "model" / "working-v11" / "joint-overlaps"
V12 = ROOT / "model" / "working-v12" / "eye-hidden-materials"
V14 = ROOT / "model" / "working-v14" / "hair-subgroups"
OUT = ROOT / "model" / "working-v15" / "joint-material-gate"
QA = ROOT / "qa" / "v15-joint-material-gate-review.png"
REPORT = ROOT / "audit" / "v15-joint-material-gate-validation.json"
MANIFEST = OUT / "material-manifest.json"
CANVAS = (512, 1086)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def rgba(rgb: np.ndarray, mask: np.ndarray) -> Image.Image:
    result = np.zeros((CANVAS[1], CANVAS[0], 4), dtype=np.uint8)
    result[:, :, :3] = rgb
    result[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
    return Image.fromarray(result, "RGBA")


def border_connected(candidate: np.ndarray) -> np.ndarray:
    h, w = candidate.shape
    seen = np.zeros_like(candidate, dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for x in range(w):
        for y in (0, h - 1):
            if candidate[y, x] and not seen[y, x]:
                seen[y, x] = True
                queue.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if candidate[y, x] and not seen[y, x]:
                seen[y, x] = True
                queue.append((y, x))
    while queue:
        y, x = queue.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and candidate[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                queue.append((ny, nx))
    return seen


def load(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if image.size != CANVAS:
        raise ValueError(f"{path} 不是 512×1086 全画布材料")
    return image


def add_original_chest_hair(
    layers: dict[str, Image.Image], paths: dict[str, Path]
) -> None:
    """把 V9 已审定的胸前长发原像素并回左右侧发，避免衣身补底露出。"""
    chest_hair = load(V9 / "胸前长发_原像素.png")
    chest = np.asarray(chest_hair)
    yy, xx = np.indices((CANVAS[1], CANVAS[0]))
    chest_alpha = chest[:, :, 3] > 0
    splits = {
        "画面左侧发": chest_alpha & (xx < CANVAS[0] // 2),
        "画面右侧发": chest_alpha & (xx >= CANVAS[0] // 2),
    }
    for name, mask in splits.items():
        addition = rgba(chest[:, :, :3], mask)
        merged = Image.alpha_composite(layers[name], addition)
        path = OUT / f"{name}_含胸前长发原像素.png"
        merged.save(path)
        layers[name] = merged
        paths[name] = path


def split_default_eyes(
    layers: dict[str, Image.Image], paths: dict[str, Path]
) -> None:
    """默认预览按左右眼拆开；完整眼白/虹膜/瞳孔继续作为隐藏建模材料保留。"""
    both = np.asarray(layers.pop("双眼默认材料"))
    paths.pop("双眼默认材料")
    yy, xx = np.indices((CANVAS[1], CANVAS[0]))
    alpha = both[:, :, 3] > 0
    for name, mask in (
        ("画面左眼默认", alpha & (xx < CANVAS[0] // 2)),
        ("画面右眼默认", alpha & (xx >= CANVAS[0] // 2)),
    ):
        image = rgba(both[:, :, :3], mask)
        path = OUT / f"{name}.png"
        image.save(path)
        layers[name] = image
        paths[name] = path


def audited_reference_mask() -> np.ndarray:
    """由已审定的原像素材料建立主体基准，不把白底阴影误判成人物缺口。"""
    mask = np.zeros((CANVAS[1], CANVAS[0]), dtype=bool)
    excluded = {"默认全图回贴.png", "身体候选层回组.png"}
    for path in V8.glob("*.png"):
        if path.name not in excluded:
            mask |= np.asarray(load(path))[:, :, 3] > 0
    for name in (
        "01_后发_含遮挡补全.png",
        "02_画面左侧发束_原像素.png",
        "03_画面右侧发束_原像素.png",
        "04_刘海_原像素.png",
        "05_脸底.png",
        "06_双眼默认层.png",
        "07_双眉.png",
    ):
        mask |= np.asarray(load(V14 / name))[:, :, 3] > 0
    mask |= np.asarray(load(V9 / "胸前长发_原像素.png"))[:, :, 3] > 0
    return mask


def complete_neck(source: np.ndarray, occluder: np.ndarray) -> Image.Image:
    raw = load(V8 / "01_neck.png")
    neck_mask = np.asarray(raw)[:, :, 3] > 0
    r = source[:, :, 0].astype(np.int16)
    g = source[:, :, 1].astype(np.int16)
    b = source[:, :, 2].astype(np.int16)
    visible_skin = neck_mask & ~occluder & (r - g > 8) & (r - b > 12) & (r > 170)
    hidden = neck_mask & occluder
    pixels = source[visible_skin]
    base = np.median(pixels, axis=0).astype(np.uint8)
    rgb = source.copy()
    rgb[hidden] = base
    layer = rgba(rgb, neck_mask)
    return Image.alpha_composite(layer, rgba(source, neck_mask & ~hidden))


def checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    w, h = size
    yy, xx = np.indices((h, w))
    board = (xx // cell + yy // cell) % 2
    values = np.where(board[:, :, None] == 0, 239, 207).astype(np.uint8)
    return Image.fromarray(np.repeat(values, 3, axis=2), "RGB")


def on_checker(image: Image.Image) -> Image.Image:
    bg = checker(image.size)
    bg.paste(image, (0, 0), image)
    return bg


def fit_panel(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    panel = Image.new("RGB", size, "white")
    copy = image.copy()
    copy.thumbnail((size[0] - 16, size[1] - 16), Image.Resampling.NEAREST)
    panel.paste(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return panel


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    QA.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)

    source_image = Image.open(SOURCE).convert("RGB")
    line_image = Image.open(LINE).convert("RGB")
    source = np.asarray(source_image)
    if source_image.size != CANVAS or line_image.size != CANVAS:
        raise ValueError("线稿和彩稿必须保持 512×1086 原始坐标")

    paths = {
        "后发": V14 / "01_后发_含遮挡补全.png",
        "画面左腿": V10 / "画面左腿_含裙内补全.png",
        "画面右腿": V10 / "画面右腿_含裙内补全.png",
        "画面左袜": V11 / "画面左袜_含鞋内补全.png",
        "画面右袜": V11 / "画面右袜_含鞋内补全.png",
        "画面左鞋": V11 / "画面左鞋_原像素.png",
        "画面右鞋": V11 / "画面右鞋_原像素.png",
        "裙子": V10 / "裙子_原像素.png",
        "衣身": V9 / "衣身_含长发下补底.png",
        "画面左前臂与整手": V11 / "画面左前臂手链整手_含袖内补全.png",
        "画面右前臂与整手": V11 / "画面右前臂手链整手_含袖内补全.png",
        "画面左袖": V11 / "画面左袖子_原像素.png",
        "画面右袖": V11 / "画面右袖子_原像素.png",
        "脸底": V14 / "05_脸底.png",
        "双眼默认材料": V12 / "双眼默认材料回组.png",
        "双眉": V14 / "07_双眉.png",
        "画面左侧发": V14 / "02_画面左侧发束_原像素.png",
        "画面右侧发": V14 / "03_画面右侧发束_原像素.png",
        "刘海": V14 / "04_刘海_原像素.png",
    }
    layers = {name: load(path) for name, path in paths.items()}
    add_original_chest_hair(layers, paths)
    split_default_eyes(layers, paths)
    hair_mask = np.logical_or.reduce(
        [np.asarray(layers[name])[:, :, 3] > 0 for name in ("后发", "画面左侧发", "画面右侧发", "刘海")]
    )
    shirt_mask = np.asarray(layers["衣身"])[:, :, 3] > 0
    neck_layer = complete_neck(source, hair_mask | shirt_mask)
    neck_path = OUT / "颈部_含遮挡补全.png"
    neck_layer.save(neck_path)
    layers["颈部"] = neck_layer
    paths["颈部"] = neck_path

    draw_order = [
        "后发",
        "画面左腿", "画面右腿",
        "画面左袜", "画面右袜",
        "画面左鞋", "画面右鞋",
        "裙子",
        "颈部",
        "衣身",
        "画面左前臂与整手", "画面右前臂与整手",
        "画面左袖", "画面右袖",
        "脸底",
        "画面左眼默认", "画面右眼默认",
        "双眉",
        "画面左侧发", "画面右侧发",
        "刘海",
    ]
    composite = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for name in draw_order:
        composite = Image.alpha_composite(composite, layers[name])
    composite.save(OUT / "联合透明角色.png")

    alpha = np.asarray(composite)[:, :, 3] > 0
    reference_subject = audited_reference_mask()

    missing = reference_subject & ~alpha
    extra = alpha & ~reference_subject
    overlap = reference_subject & alpha

    white = Image.new("RGB", CANVAS, "white")
    white.paste(composite, (0, 0), composite)
    reference_white = Image.new("RGB", CANVAS, "white")
    reference_layer = rgba(source, reference_subject)
    reference_white.paste(reference_layer, (0, 0), reference_layer)
    diff = ImageChops.difference(white, reference_white)
    diff_array = np.asarray(diff)
    overlap_mae = float(diff_array[overlap].mean()) if overlap.any() else 0.0
    overlap_max = int(diff_array[overlap].max()) if overlap.any() else 0

    coverage = source_image.convert("RGBA")
    coverage_pixels = np.zeros((CANVAS[1], CANVAS[0], 4), dtype=np.uint8)
    coverage_pixels[:, :, :3] = (230, 35, 45)
    coverage_pixels[:, :, 3] = np.where(missing, 180, 0).astype(np.uint8)
    coverage = Image.alpha_composite(coverage, Image.fromarray(coverage_pixels, "RGBA"))

    amplified = np.clip(diff_array.astype(np.int16) * 5, 0, 255).astype(np.uint8)
    amplified_image = Image.fromarray(amplified, "RGB")

    panel_size = (360, 620)
    title_h = 62
    footer_h = 190
    sheet = Image.new("RGB", (panel_size[0] * 3, (panel_size[1] + title_h) * 2 + footer_h), "white")
    draw = ImageDraw.Draw(sheet)
    entries = [
        ("① 原始彩稿正面", source_image),
        ("② 联合透明角色", on_checker(composite)),
        ("③ 联合角色白底预览", white),
        ("④ 红色=审定材料未覆盖像素", coverage.convert("RGB")),
        ("⑤ 颜色差异放大 5 倍", amplified_image),
        ("⑥ 线稿结构参考", line_image),
    ]
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
        f"材料层数：{len(draw_order)}；参考主体像素={int(reference_subject.sum())}，联合覆盖={int(alpha.sum())}。",
        fill="#222222",
        font=font(19),
    )
    draw.text(
        (18, footer_y + 39),
        f"未覆盖像素={int(missing.sum())}，额外覆盖像素={int(extra.sum())}；重叠区域颜色 MAE={overlap_mae:.3f}，最大通道差={overlap_max}。",
        fill="#222222",
        font=font(19),
    )
    draw.text(
        (18, footer_y + 80),
        "基准来自已审定原像素材料，不再把白底投影误判为人物；红色缺口归零后才允许导入 PSD。",
        fill="#8D251E",
        font=font(20),
    )
    draw.text(
        (18, footer_y + 124),
        "闭眼线、完整眼白/虹膜为替换或隐藏材料，不参与此处默认透明角色的 20 层计数。",
        fill="#333333",
        font=font(18),
    )
    sheet.save(QA)

    manifest = {
        "stage": "v15-joint-material-gate",
        "canvas": list(CANVAS),
        "drawOrder": [
            {
                "index": index,
                "name": name,
                "path": str(paths[name].relative_to(ROOT)).replace("\\", "/"),
            }
            for index, name in enumerate(draw_order, start=1)
        ],
        "alternateHiddenMaterials": [
            f"model/working-v12/eye-hidden-materials/{side}_{index:02d}_{suffix}.png"
            for side in ("left", "right")
            for index, suffix in (
                (1, "完整眼白"),
                (2, "完整虹膜"),
                (3, "完整瞳孔"),
                (4, "原高光"),
                (5, "眼睑表面原像素"),
                (6, "上眼线原像素"),
                (7, "下眼线原像素"),
                (8, "闭眼线候选"),
            )
        ],
        "psdImport": False,
        "cubismImport": False,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    REPORT.write_text(
        json.dumps(
            {
                "stage": "v15-joint-material-gate",
                "layerCount": len(draw_order),
                "referenceSubjectPixels": int(reference_subject.sum()),
                "compositeAlphaPixels": int(alpha.sum()),
                "missingPixels": int(missing.sum()),
                "extraPixels": int(extra.sum()),
                "extraPixelsMeaning": "细分层新增的同色边缘或遮挡补全；默认合成仍须与彩稿零色差",
                "overlapColorMae": overlap_mae,
                "overlapColorMaxError": overlap_max,
                "status": "pass" if missing.sum() == 0 and overlap_max == 0 else "needs-coverage-review",
                "psdImport": False,
                "cubismImport": False,
                "next": (
                    "import-layered-psd"
                    if missing.sum() == 0 and overlap_max == 0
                    else "resolve-missing-coverage-before-psd-import"
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
