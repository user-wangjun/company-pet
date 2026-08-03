from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
VALIDATION = WORKBENCH / "validation"
V13 = VALIDATION / "arm-chain-screen-left-v13-material-separation"
V14 = VALIDATION / "arm-chain-screen-left-v14-complete-textures"
SOURCE = WORKBENCH / "source/masters/front-color-source-exact-after-reset.png"
V13_MANIFEST = V13 / "audit/v13-material-boundary-freeze-manifest-2026-07-27.json"
V14_MANIFEST = V14 / "audit/v14-complete-texture-freeze-manifest-2026-07-28.json"
MASKS = STAGE / "masks"
MATERIALS = STAGE / "materials"
QA = STAGE / "qa"
AUDIT = STAGE / "audit"
BOARD = QA / "V18-MATERIAL-BOUNDARY-USER-REVIEW.zh-CN.png"
REPORT = AUDIT / "v18-material-boundary-repair-report.json"

LAYERS = ("sleeve", "upper_arm", "forearm_bracelet", "whole_hand")
DRAW_ORDER = ("upper_arm", "whole_hand", "forearm_bracelet", "sleeve")
COLORS = {
    "sleeve": (69, 119, 188),
    "upper_arm": (235, 151, 54),
    "forearm_bracelet": (65, 166, 126),
    "whole_hand": (216, 79, 118),
}
W, H = 512, 1086


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_manifest(root: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mismatches = []
    for item in manifest["lockedArtifacts"]:
        path = root / item["path"]
        if (
            not path.exists()
            or path.stat().st_size != item["bytes"]
            or sha256(path) != item["sha256"]
        ):
            mismatches.append(item["path"])
    return {
        "matched": len(manifest["lockedArtifacts"]) - len(mismatches),
        "total": len(manifest["lockedArtifacts"]),
        "mismatches": mismatches,
        "pass": not mismatches,
    }


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    paths = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def alpha(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA").getchannel("A")


def save_alpha(path: Path, channel: Image.Image) -> None:
    image = Image.new("RGBA", channel.size, (255, 255, 255, 0))
    image.putalpha(channel)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def checker(size: tuple[int, int], cell: int = 12) -> Image.Image:
    image = Image.new("RGBA", size, (238, 238, 238, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(205, 205, 205, 255))
    return image


def crop_preview(image: Image.Image, box: tuple[int, int, int, int], size: tuple[int, int], nearest: bool = False) -> Image.Image:
    resampling = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
    return image.crop(box).resize(size, resampling)


def colored(mask: Image.Image, color: tuple[int, int, int], opacity: int = 255) -> Image.Image:
    out = Image.new("RGBA", mask.size, color + (0,))
    out.putalpha(mask.point(lambda value: round(value * opacity / 255)))
    return out


def compose(materials: dict[str, Image.Image], background: tuple[int, int, int, int] = (0, 0, 0, 0)) -> Image.Image:
    out = Image.new("RGBA", (W, H), background)
    for name in DRAW_ORDER:
        out.alpha_composite(materials[name])
    return out


def main() -> None:
    integrity = {
        "v13": verify_manifest(V13, V13_MANIFEST),
        "v14": verify_manifest(V14, V14_MANIFEST),
    }
    if not all(item["pass"] for item in integrity.values()):
        raise RuntimeError("Frozen upstream input verification failed.")

    source = Image.open(SOURCE).convert("RGB")
    v13_visible = {name: alpha(V13 / "masks/visible" / f"{name}.png") for name in LAYERS}
    v13_complete = {name: alpha(V13 / "masks/complete" / f"{name}.png") for name in LAYERS}
    v14_visible = {
        name: alpha(V14 / "corrected-masks/visible" / f"{name}.png") for name in LAYERS
    }
    old_materials = {
        name: Image.open(V14 / "materials" / f"{name}.png").convert("RGBA")
        for name in LAYERS
    }

    # V14 moved the entire 448 px source-registered cuff band from upper-arm
    # skin into the sleeve. The flat default composite hid the semantic error.
    # Restore the already frozen V13 ownership boundary. Preserve V14 texture
    # bytes everywhere else, and move the exact cuff pixels from the old sleeve
    # material into upper-arm ownership so the default composite stays exact.
    reassigned_band = ImageChops.subtract(v14_visible["sleeve"], v13_visible["sleeve"])
    reassigned_pixels = sum(value > 0 for value in reassigned_band.getdata())

    visible = v13_visible
    complete = v13_complete
    hidden = {
        name: ImageChops.subtract(complete[name], visible[name]) for name in LAYERS
    }
    materials: dict[str, Image.Image] = {}
    for name in LAYERS:
        material = old_materials[name].copy()
        if name == "upper_arm":
            material_px = material.load()
            old_sleeve_px = old_materials["sleeve"].load()
            band_px = reassigned_band.load()
            for y in range(H):
                for x in range(W):
                    if band_px[x, y] > 0:
                        material_px[x, y] = old_sleeve_px[x, y]
        material.putalpha(complete[name])
        materials[name] = material
        save_alpha(MASKS / "visible" / f"{name}.png", visible[name])
        save_alpha(MASKS / "complete" / f"{name}.png", complete[name])
        save_alpha(MASKS / "hidden" / f"{name}.png", hidden[name])
        MATERIALS.mkdir(parents=True, exist_ok=True)
        material.save(MATERIALS / f"{name}.png")

    candidate = compose(materials, (248, 248, 248, 255)).convert("RGB")
    visible_union = Image.new("L", (W, H), 0)
    for channel in visible.values():
        visible_union = ImageChops.lighter(visible_union, channel)
    default_difference = sum(
        candidate.getpixel((x, y)) != source.getpixel((x, y))
        for y in range(H)
        for x in range(W)
        if visible_union.getpixel((x, y)) > 0
    )

    current_ownership = checker((W, H))
    repaired_visible = checker((W, H))
    repaired_complete = checker((W, H))
    for name in DRAW_ORDER:
        current_ownership.alpha_composite(colored(v14_visible[name], COLORS[name]))
        repaired_visible.alpha_composite(colored(visible[name], COLORS[name]))
        repaired_complete.alpha_composite(colored(complete[name], COLORS[name], 92))
        repaired_complete.alpha_composite(colored(visible[name], COLORS[name], 255))

    board = Image.new("RGB", (1900, 1240), (239, 242, 247))
    draw = ImageDraw.Draw(board)
    draw.text((42, 25), "小星 V18｜袖口归属与上臂补全修正", font=font(40, True), fill=(24, 31, 43))
    draw.text(
        (45, 82),
        "已确认 V14 将整片袖口带错误归入袖子；本候选恢复皮肤 / 布料边界，并单独显示隐藏补全",
        font=font(22),
        fill=(71, 81, 97),
    )

    panels = [
        ("V14/V17 当前归属（问题）", current_ownership),
        ("修正后可见归属", repaired_visible),
        ("修正后完整结构\n实色=可见，淡色=隐藏", repaired_complete),
    ]
    for index, (label, image) in enumerate(panels):
        x = 45 + index * 410
        preview = image.resize((370, 785), Image.Resampling.NEAREST)
        board.paste(preview.convert("RGB"), (x, 145))
        draw.multiline_text((x, 948), label, font=font(23, True), fill=(42, 51, 65), spacing=5)

    right_x = 1290
    draw.rounded_rectangle((right_x, 135, 1860, 525), radius=22, fill=(255, 255, 255), outline=(195, 204, 218), width=2)
    draw.text((right_x + 28, 163), "袖口局部：原稿 / 修正版", font=font(28, True), fill=(31, 39, 52))
    cuff = (112, 360, 190, 430)
    source_rgba = source.convert("RGBA")
    source_crop = crop_preview(source_rgba, cuff, (235, 235))
    candidate_crop = crop_preview(candidate.convert("RGBA"), cuff, (235, 235))
    board.paste(source_crop.convert("RGB"), (right_x + 28, 220))
    board.paste(candidate_crop.convert("RGB"), (right_x + 300, 220))
    draw.text((right_x + 28, 466), "锁定原稿", font=font(19), fill=(68, 77, 92))
    draw.text((right_x + 300, 466), "候选默认合成", font=font(19), fill=(68, 77, 92))

    draw.rounded_rectangle((right_x, 555, 1860, 1025), radius=22, fill=(255, 255, 255), outline=(195, 204, 218), width=2)
    draw.text((right_x + 28, 580), "袖子与上臂独立纹理", font=font(28, True), fill=(31, 39, 52))
    isolate_box = (90, 210, 220, 440)
    sleeve_bg = checker((130, 230), 10)
    arm_bg = checker((130, 230), 10)
    sleeve_bg.alpha_composite(materials["sleeve"].crop(isolate_box))
    arm_bg.alpha_composite(materials["upper_arm"].crop(isolate_box))
    sleeve_preview = sleeve_bg.resize((235, 414), Image.Resampling.NEAREST)
    arm_preview = arm_bg.resize((235, 414), Image.Resampling.NEAREST)
    board.paste(sleeve_preview.convert("RGB"), (right_x + 28, 640))
    board.paste(arm_preview.convert("RGB"), (right_x + 300, 640))
    draw.text((right_x + 28, 1000), "袖子：仅布料", font=font(19), fill=(68, 77, 92))
    draw.text((right_x + 300, 1000), "上臂：皮肤延伸至肩下", font=font(19), fill=(68, 77, 92))

    draw.rounded_rectangle((45, 1085, 1860, 1198), radius=18, fill=(255, 241, 207))
    draw.text(
        (72, 1108),
        f"失败候选：移动 {reassigned_pixels}px 袖口归属后，默认合成对原稿出现 "
        f"{default_difference}px 差异；本候选不采用。",
        font=font(23, True),
        fill=(133, 82, 0),
    )
    draw.text(
        (72, 1155),
        "结论：不能直接把整片袖口阴影改归上臂；回到原稿一致的四层材料继续核对。",
        font=font(21),
        fill=(112, 72, 10),
    )
    QA.mkdir(parents=True, exist_ok=True)
    board.save(BOARD)

    report = {
        "schemaVersion": 1,
        "status": "engineering_fail_candidate_rejected",
        "scope": "screen-left sleeve/upper-arm semantic ownership and hidden completion repair",
        "upstreamIntegrity": integrity,
        "earliestDefect": {
            "stage": "V14 cuff ownership correction",
            "description": "the entire source-registered cuff band was assigned to sleeve, including exposed skin",
            "reassignedPixels": reassigned_pixels,
        },
        "repair": {
            "visibleOwnership": "restore frozen V13 sleeve/upper-arm boundary",
            "hiddenCompletion": "retain V14 hidden texture outside repaired boundary",
            "defaultSourceRgbDifferencePixels": default_difference,
            "pass": default_difference == 0,
        },
        "downstreamStatus": {
            "v15Mesh": "must be rebuilt after material approval; frozen V15 remains untouched",
            "v16Nodes": "rejected candidate; not reused",
            "physics": False,
            "runtime": False,
        },
        "reviewBoard": BOARD.relative_to(STAGE).as_posix(),
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "v13": f"{integrity['v13']['matched']}/{integrity['v13']['total']}",
                "v14": f"{integrity['v14']['matched']}/{integrity['v14']['total']}",
                "reassignedPixels": reassigned_pixels,
                "defaultSourceRgbDifferencePixels": default_difference,
                "reviewBoard": report["reviewBoard"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
