from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
V14 = WORKBENCH / "validation/arm-chain-screen-left-v14-complete-textures"
V14_MANIFEST = V14 / "audit/v14-complete-texture-freeze-manifest-2026-07-28.json"
MASK_ROOT = V14 / "corrected-masks"
MATERIAL_ROOT = V14 / "materials"
SOURCE_COLOR = WORKBENCH / "source/masters/front-color-source-exact-after-reset.png"
AUDIT = STAGE / "audit"
QA = STAGE / "qa"
BOARD = QA / "V17-MATERIAL-USER-REVIEW.zh-CN.png"
REPORT = AUDIT / "v17-material-recheck-report.json"
W, H = 512, 1086

LAYERS = ("sleeve", "upper_arm", "forearm_bracelet", "whole_hand")
LABELS = {
    "sleeve": "袖子",
    "upper_arm": "上臂",
    "forearm_bracelet": "前臂 + 手链",
    "whole_hand": "整手",
}
COLORS = {
    "sleeve": (79, 126, 189),
    "upper_arm": (235, 155, 60),
    "forearm_bracelet": (70, 164, 126),
    "whole_hand": (214, 92, 125),
}
JOINTS = {
    "肩—肘": (164, 330, 220, 450),
    "肘—腕": (105, 455, 175, 565),
    "手指空隙": (92, 510, 145, 570),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_freeze() -> dict:
    manifest = json.loads(V14_MANIFEST.read_text(encoding="utf-8"))
    mismatches = []
    for artifact in manifest["lockedArtifacts"]:
        path = V14 / artifact["path"]
        if (
            not path.exists()
            or path.stat().st_size != artifact["bytes"]
            or sha256(path) != artifact["sha256"]
        ):
            mismatches.append(artifact["path"])
    return {
        "status": manifest["status"],
        "matchedArtifacts": len(manifest["lockedArtifacts"]) - len(mismatches),
        "artifactCount": len(manifest["lockedArtifacts"]),
        "mismatches": mismatches,
        "pass": not mismatches,
    }


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def mask(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA").getchannel("A")


def colored_layer(alpha: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    solid = Image.new("RGBA", alpha.size, color + (0,))
    solid.putalpha(alpha)
    return solid


def checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    out = Image.new("RGB", size, (238, 238, 238))
    draw = ImageDraw.Draw(out)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if ((x // cell) + (y // cell)) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(208, 208, 208))
    return out.convert("RGBA")


def load_assets() -> tuple[dict[str, Image.Image], dict[str, Image.Image], dict[str, Image.Image]]:
    complete = {name: mask(MASK_ROOT / "complete" / f"{name}.png") for name in LAYERS}
    visible = {name: mask(MASK_ROOT / "visible" / f"{name}.png") for name in LAYERS}
    materials = {
        name: Image.open(MATERIAL_ROOT / f"{name}.png").convert("RGBA") for name in LAYERS
    }
    return complete, visible, materials


def composite(materials: dict[str, Image.Image]) -> Image.Image:
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for name in ("upper_arm", "whole_hand", "forearm_bracelet", "sleeve"):
        out.alpha_composite(materials[name])
    return out


def build_board(complete: dict, visible: dict, materials: dict) -> None:
    board = Image.new("RGB", (2200, 1420), (239, 242, 247))
    draw = ImageDraw.Draw(board)
    draw.text((42, 28), "小星 V17｜画面左侧手臂分层与缺失补全审查", font=font(42, True), fill=(24, 31, 43))
    draw.text(
        (45, 88),
        "本阶段只审查色块归属、隐藏补全和关节接缝；未进入网格、节点或运动",
        font=font(24),
        fill=(74, 83, 99),
    )

    composite_img = composite(materials)
    # Full-color default recomposition.
    full = checker((W, H))
    full.alpha_composite(composite_img)
    full_preview = full.resize((410, 869), Image.Resampling.LANCZOS)
    board.paste(full_preview.convert("RGB"), (55, 170))
    draw.text((55, 1055), "默认合成（完整纹理）", font=font(26, True), fill=(45, 54, 69))

    # Full color-block ownership view.
    ownership = checker((W, H))
    for name in ("upper_arm", "whole_hand", "forearm_bracelet", "sleeve"):
        ownership.alpha_composite(colored_layer(complete[name], COLORS[name]))
    own_preview = ownership.resize((410, 869), Image.Resampling.LANCZOS)
    board.paste(own_preview.convert("RGB"), (505, 170))
    draw.text((505, 1055), "色块归属（完整 alpha）", font=font(26, True), fill=(45, 54, 69))

    panel_x = 970
    draw.rounded_rectangle((panel_x, 155, 2150, 620), radius=26, fill=(255, 255, 255), outline=(196, 204, 218), width=2)
    draw.text((panel_x + 35, 185), "四层归属与补全", font=font(31, True), fill=(29, 36, 49))
    y = 250
    for name in LAYERS:
        complete_count = sum(1 for value in complete[name].getdata() if value > 0)
        visible_count = sum(1 for value in visible[name].getdata() if value > 0)
        hidden_count = complete_count - visible_count
        draw.rectangle((panel_x + 40, y + 5, panel_x + 70, y + 35), fill=COLORS[name])
        draw.text(
            (panel_x + 90, y),
            f"{LABELS[name]}：完整 {complete_count}px｜可见 {visible_count}px｜隐藏补全 {hidden_count}px",
            font=font(23),
            fill=(63, 72, 88),
        )
        y += 70

    # Joint crops with both ownership and texture.
    draw.rounded_rectangle((panel_x, 650, 2150, 1375), radius=26, fill=(255, 255, 255), outline=(196, 204, 218), width=2)
    draw.text((panel_x + 35, 680), "关节与空隙局部（色块 / 默认纹理）", font=font(31, True), fill=(29, 36, 49))
    crop_x = panel_x + 40
    crop_y = 745
    for index, (label, box) in enumerate(JOINTS.items()):
        left, top, right, bottom = box
        crop_size = (right - left, bottom - top)
        own_crop = checker(crop_size)
        tex_crop = checker(crop_size)
        for name in ("upper_arm", "whole_hand", "forearm_bracelet", "sleeve"):
            own_crop.alpha_composite(colored_layer(complete[name], COLORS[name]).crop(box))
            tex_crop.alpha_composite(materials[name].crop(box))
        own_crop = own_crop.resize((260, 230), Image.Resampling.NEAREST)
        tex_crop = tex_crop.resize((260, 230), Image.Resampling.NEAREST)
        x = crop_x + index * 370
        board.paste(own_crop.convert("RGB"), (x, crop_y))
        board.paste(tex_crop.convert("RGB"), (x, crop_y + 240))
        draw.text((x, crop_y - 36), label, font=font(22, True), fill=(57, 66, 82))
        draw.text((x, crop_y + 480), "色块", font=font(18), fill=(80, 89, 104))
        draw.text((x + 120, crop_y + 480), "纹理", font=font(18), fill=(80, 89, 104))

    # Overlap evidence.
    overlap_pairs = [
        ("sleeve", "upper_arm", "袖口"),
        ("upper_arm", "forearm_bracelet", "肘部"),
        ("forearm_bracelet", "whole_hand", "腕部"),
    ]
    overlap_text = []
    for a, b, label in overlap_pairs:
        overlap = sum(
            1
            for va, vb in zip(complete[a].getdata(), complete[b].getdata())
            if va > 0 and vb > 0
        )
        overlap_text.append(f"{label}相邻 alpha 重叠：{overlap}px")
    draw.text((panel_x + 40, 1275), "；".join(overlap_text), font=font(21), fill=(69, 78, 94))

    draw.rounded_rectangle((panel_x + 40, 1310, 2110, 1360), radius=12, fill=(255, 239, 199))
    draw.text(
        (panel_x + 60, 1323),
        "停止点：请审查四层色块和三个局部；批准前不生成网格或节点。",
        font=font(21, True),
        fill=(137, 84, 0),
    )
    QA.mkdir(parents=True, exist_ok=True)
    board.save(BOARD)


def main() -> None:
    freeze = verify_freeze()
    if not freeze["pass"] or freeze["matchedArtifacts"] != freeze["artifactCount"]:
        raise RuntimeError("V14 freeze verification failed.")
    complete, visible, materials = load_assets()
    build_board(complete, visible, materials)
    default = composite(materials)
    # Recomposition gate: the locked four-layer draw order must reproduce the
    # approved source on every visible-owned pixel, not merely render without
    # exceptions.
    source = Image.open(SOURCE_COLOR).convert("RGB")
    visible_union = Image.new("L", (W, H), 0)
    for layer_mask in visible.values():
        visible_union = ImageChops.lighter(visible_union, layer_mask)
    default_rgb = Image.new("RGBA", (W, H), (248, 248, 248, 255))
    default_rgb.alpha_composite(default)
    default_rgb = default_rgb.convert("RGB")
    source_rgb_difference = sum(
        default_rgb.getpixel((x, y)) != source.getpixel((x, y))
        for y in range(H)
        for x in range(W)
        if visible_union.getpixel((x, y)) > 0
    )
    ownership = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for name in ("upper_arm", "whole_hand", "forearm_bracelet", "sleeve"):
        ownership.alpha_composite(colored_layer(complete[name], COLORS[name]))
    adjacent = {}
    for a, b, label in (("sleeve", "upper_arm", "sleeveUpper"), ("upper_arm", "forearm_bracelet", "upperForearm"), ("forearm_bracelet", "whole_hand", "forearmHand")):
        adjacent[label] = sum(
            1 for va, vb in zip(complete[a].getdata(), complete[b].getdata()) if va > 0 and vb > 0
        )
    report = {
        "schemaVersion": 1,
        "status": "engineering_pass_pending_user_visual_approval",
        "engineeringPass": True,
        "inputIntegrity": {"v14Freeze": freeze},
        "scope": "four material layers, hidden-area completion, default recomposition, and joint visual review",
        "materials": {
            name: {
                "completePixels": sum(1 for value in complete[name].getdata() if value > 0),
                "visiblePixels": sum(1 for value in visible[name].getdata() if value > 0),
                "hiddenPixels": sum(
                    1 for vc, cc in zip(visible[name].getdata(), complete[name].getdata()) if cc > 0 and vc == 0
                ),
            }
            for name in LAYERS
        },
        "defaultRecomposition": {"canvas": [W, H], "alphaPixels": sum(1 for value in default.getchannel("A").getdata() if value > 0)},
        "spliceCheck": {
            "drawOrder": ["upper_arm", "whole_hand", "forearm_bracelet", "sleeve"],
            "visibleUnionPixels": sum(1 for value in visible_union.getdata() if value > 0),
            "sourceRgbDifferencePixels": source_rgb_difference,
            "pass": source_rgb_difference == 0,
        },
        "adjacentCompleteAlphaOverlapPixels": adjacent,
        "reviewBoard": BOARD.relative_to(STAGE).as_posix(),
        "notCreated": ["ArtMesh", "Deformer", "continuous parameter motion", "Physics", "Runtime"],
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (AUDIT / "V17-MATERIAL-REPORT.zh-CN.md").write_text(
        f"""# V17 材料分层与缺失补全审查

- 状态：工程检查通过，等待视觉批准；
- V14 冻结输入：{freeze['matchedArtifacts']}/{freeze['artifactCount']}；
- 范围：四层色块归属、隐藏补全、默认合成和袖口/肘部/腕部局部；
- 当前未创建 ArtMesh、Deformer、连续参数、Physics 或 Runtime；
- 审查图：`{BOARD.relative_to(STAGE).as_posix()}`。
""",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "v14Freeze": f"{freeze['matchedArtifacts']}/{freeze['artifactCount']}", "reviewBoard": report["reviewBoard"], "adjacent": adjacent}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
