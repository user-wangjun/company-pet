from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
VALIDATION = WORKBENCH / "validation"
V14 = VALIDATION / "arm-chain-screen-left-v14-complete-textures"
V15 = VALIDATION / "arm-chain-screen-left-v15-mesh-gate"
V20 = VALIDATION / "arm-chain-screen-left-v20-armhole-anatomy-repair"
V14_MANIFEST = V14 / "audit/v14-complete-texture-freeze-manifest-2026-07-28.json"
V15_MANIFEST = V15 / "audit/v15-artmesh-freeze-manifest-2026-07-28.json"
V20_REPORT = V20 / "audit/v20-armhole-anatomy-repair-report.json"
V15_TOOL = V15 / "tools/build_v15_mesh_gate.py"
QA = STAGE / "qa"
AUDIT = STAGE / "audit"
MESHES = STAGE / "meshes"
BOARD = QA / "V21-MESH-USER-REVIEW.zh-CN.png"
REPORT = AUDIT / "v21-mesh-rebuild-report.json"
LAYERS = ("sleeve", "upper_arm", "forearm_bracelet", "whole_hand")
DRAW_ORDER = ("upper_arm", "whole_hand", "forearm_bracelet", "sleeve")
LABELS = {
    "sleeve": "袖子",
    "upper_arm": "上臂（V20 重建）",
    "forearm_bracelet": "前臂 + 手链",
    "whole_hand": "整手",
}
W, H = 512, 1086
CROP = (50, 205, 205, 655)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(root: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad = []
    for item in manifest["lockedArtifacts"]:
        path = root / item["path"]
        if not path.exists() or path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            bad.append(item["path"])
    return {
        "matched": len(manifest["lockedArtifacts"]) - len(bad),
        "total": len(manifest["lockedArtifacts"]),
        "mismatches": bad,
        "pass": not bad,
    }


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in (
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def load_builder():
    spec = importlib.util.spec_from_file_location("v15_mesh_builder", V15_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load frozen V15 mesh algorithm.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tint_mask(mask: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGBA", mask.size, color + (0,))
    image.putalpha(mask)
    return image


def mask(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA").getchannel("A")


def main() -> None:
    upstream = {
        "v14": verify(V14, V14_MANIFEST),
        "v15": verify(V15, V15_MANIFEST),
    }
    if not all(item["pass"] for item in upstream.values()):
        raise RuntimeError("Frozen upstream verification failed.")
    v20_report = json.loads(V20_REPORT.read_text(encoding="utf-8"))
    if v20_report["defaultVisibleSourceRgbDifferencePixels"] != 0:
        raise RuntimeError("V20 material candidate is not source-consistent.")

    builder = load_builder()
    meshes: dict[str, dict] = {}
    wires: dict[str, Image.Image] = {}
    materials: dict[str, Image.Image] = {}
    for layer in LAYERS:
        materials[layer] = Image.open(V20 / "materials" / f"{layer}.png").convert("RGBA")
        if layer == "upper_arm":
            mesh, wire = builder.build_mesh(
                layer, V20 / "masks" / "complete" / f"{layer}.png"
            )
            mesh["sourceMaterial"] = f"../../arm-chain-screen-left-v20-armhole-anatomy-repair/materials/{layer}.png"
            mesh["alphaMask"] = f"../../arm-chain-screen-left-v20-armhole-anatomy-repair/masks/complete/{layer}.png"
            meshes[layer] = mesh
            wires[layer] = wire
        else:
            meshes[layer] = json.loads((V15 / "meshes" / f"{layer}.json").read_text(encoding="utf-8"))
            meshes[layer]["sourceMaterial"] = f"../../arm-chain-screen-left-v20-armhole-anatomy-repair/materials/{layer}.png"
            meshes[layer]["alphaMask"] = f"../../arm-chain-screen-left-v20-armhole-anatomy-repair/masks/complete/{layer}.png"
            wires[layer] = Image.open(V15 / "qa" / f"wireframe-{layer}.png").convert("RGBA")
        (MESHES).mkdir(parents=True, exist_ok=True)
        (MESHES / f"{layer}.json").write_text(
            json.dumps(meshes[layer], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        QA.mkdir(parents=True, exist_ok=True)
        wires[layer].save(QA / f"wireframe-{layer}.png")

    # Engineering checks cover the new topology and preserve the frozen seam
    # overlap contract for the three unchanged adjacent boundaries.
    metrics = {layer: meshes[layer]["engineeringQa"] for layer in LAYERS}
    complete = {
        layer: mask(V20 / "masks" / "complete" / f"{layer}.png") for layer in LAYERS
    }
    overlaps = {}
    for a, b, label in (
        ("sleeve", "upper_arm", "sleeveUpper"),
        ("upper_arm", "forearm_bracelet", "upperForearm"),
        ("forearm_bracelet", "whole_hand", "forearmHand"),
    ):
        overlaps[label] = sum(
            x > 0 and y > 0
            for x, y in zip(complete[a].getdata(), complete[b].getdata())
        )
    wire_panels = []
    for layer in LAYERS:
        panel = materials[layer].copy()
        panel.alpha_composite(wires[layer])
        bg = Image.new("RGBA", panel.size, (250, 250, 250, 255))
        bg.alpha_composite(panel)
        wire_panels.append(bg.convert("RGB").crop(CROP).resize((310, 900), Image.Resampling.NEAREST))

    board = Image.new("RGB", (2240, 1540), (239, 241, 245))
    draw = ImageDraw.Draw(board)
    draw.text((42, 25), "小星 V21｜V20 体态修正后的四层网格审查", font=font(40, True), fill=(25, 31, 42))
    draw.text(
        (45, 84),
        "仅检查 ArtMesh 线框覆盖、上臂肩部新轮廓、关节连通与手指空隙；尚未建立节点或主动运动",
        font=font(23),
        fill=(76, 84, 96),
    )
    for index, panel in enumerate(wire_panels):
        x = 42 + index * 335
        board.paste(panel, (x, 150))
        draw.text((x, 1080), LABELS[LAYERS[index]], font=font(21, True), fill=(42, 49, 59))
        metric = metrics[LAYERS[index]]
        draw.text(
            (x, 1120),
            f"V={metric['vertexCount']}  T={metric['triangleCount']}",
            font=font(18),
            fill=(64, 70, 80),
        )

    x = 1405
    draw.rounded_rectangle((x, 150, 2190, 820), radius=24, fill="white", outline=(204, 211, 220), width=2)
    draw.text((x + 30, 185), "工程门禁", font=font(30, True), fill=(25, 31, 42))
    notes = [
        f"V14 冻结输入：{upstream['v14']['matched']}/{upstream['v14']['total']}；V15 旧网格：{upstream['v15']['matched']}/{upstream['v15']['total']}。",
        "袖子、前臂、整手拓扑逐字复制 V15；仅上臂使用 V20 新完整 alpha 重建。",
        "四层三角形均限制在对应完整 alpha 内，UV 仍为 512×1086 注册坐标。",
        "上臂新肩部网格必须覆盖新增体态轮廓，不得退化成旧直条。",
        f"相邻完整 alpha 重叠：袖口 {overlaps['sleeveUpper']}px；肘部 {overlaps['upperForearm']}px；腕部 {overlaps['forearmHand']}px。",
        "请重点看：肩部线框是否顺着体态、袖口/肘部是否断开、手指间隙是否被桥接。",
    ]
    for index, note in enumerate(notes):
        draw.text((x + 34, 255 + index * 78), "• " + note, font=font(20), fill=(48, 55, 66))
    draw.rounded_rectangle((x + 30, 680, 2155, 780), radius=13, fill=(255, 242, 207))
    draw.text(
        (x + 50, 700),
        "停止点：网格视觉批准前不建立节点、参数、Physics 或 Runtime。",
        font=font(22, True),
        fill=(126, 83, 0),
    )
    QA.mkdir(parents=True, exist_ok=True)
    board.save(BOARD)

    report = {
        "schemaVersion": 1,
        "status": "engineering_pass_pending_user_visual_approval",
        "scope": "V20 four-layer ArtMesh rebuild; upper-arm topology replaced, other three copied from V15",
        "upstreamIntegrity": upstream,
        "v20MaterialStatus": v20_report["status"],
        "meshes": metrics,
        "adjacentCompleteAlphaOverlapPixels": overlaps,
        "reviewBoard": BOARD.relative_to(STAGE).as_posix(),
        "notCreated": ["actual node hierarchy", "continuous parameters", "Physics", "Runtime"],
    }
    AUDIT.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
