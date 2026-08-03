from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
V14 = WORKBENCH / "validation/arm-chain-screen-left-v14-complete-textures"
V15 = WORKBENCH / "validation/arm-chain-screen-left-v15-mesh-gate"
V15_MANIFEST = V15 / "audit/v15-artmesh-freeze-manifest-2026-07-28.json"
CMO3 = STAGE / "cubism/xiaoxing-arm-chain-screen-left-v16-nodes.cmo3"
PSD_REPORT = STAGE / "audit/v16-psd-build-report.json"
BOARD = STAGE / "qa/V16-NODE-USER-REVIEW.zh-CN.png"
REPORT = STAGE / "audit/v16-node-engineering-report.json"
REPORT_ZH = STAGE / "audit/V16-NODE-REPORT.zh-CN.md"
W, H = 512, 1086


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_manifest(manifest_path: Path, root: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matched = 0
    mismatches = []
    for artifact in manifest["lockedArtifacts"]:
        path = root / artifact["path"]
        ok = (
            path.exists()
            and path.stat().st_size == artifact["bytes"]
            and sha256(path) == artifact["sha256"]
        )
        if ok:
            matched += 1
        else:
            mismatches.append(artifact["path"])
    return {
        "status": manifest["status"],
        "matchedArtifacts": matched,
        "artifactCount": len(manifest["lockedArtifacts"]),
        "mismatches": mismatches,
        "pass": not mismatches,
    }


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = [
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for name in names:
        path = Path(name)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def render_board() -> None:
    layers = {
        name: Image.open(V14 / f"materials/{name}.png").convert("RGBA")
        for name in ("upper_arm", "whole_hand", "forearm_bracelet", "sleeve")
    }
    composite = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for name in ("upper_arm", "whole_hand", "forearm_bracelet", "sleeve"):
        composite.alpha_composite(layers[name])

    board = Image.new("RGB", (2100, 1320), (238, 241, 246))
    draw = ImageDraw.Draw(board)
    draw.text((42, 28), "小星 V16｜画面左侧手臂节点最小审查", font=font(42, True), fill=(24, 30, 42))
    draw.text(
        (45, 88),
        "实际 Cubism 节点已建立并保存；本图只审查轴心、父子关系和唯一主控制归属",
        font=font(23),
        fill=(74, 82, 97),
    )

    panel = Image.new("RGBA", (W, H), (250, 250, 252, 255))
    panel.alpha_composite(composite)
    scale = 0.92
    preview = panel.resize((round(W * scale), round(H * scale)), Image.Resampling.LANCZOS)
    x0, y0 = 65, 160
    board.paste(preview.convert("RGB"), (x0, y0))

    pivots = {
        "D_LeftShoulder": (176, 257),
        "D_LeftElbow": (153, 411),
        "D_LeftWrist": (115, 529),
    }
    colors = {
        "D_LeftShoulder": (29, 126, 214),
        "D_LeftElbow": (19, 159, 122),
        "D_LeftWrist": (218, 76, 111),
    }
    mapped = {
        name: (x0 + round(px * scale), y0 + round(py * scale))
        for name, (px, py) in pivots.items()
    }
    draw.line([mapped["D_LeftShoulder"], mapped["D_LeftElbow"], mapped["D_LeftWrist"]], fill=(34, 42, 58), width=5)
    for name, point in mapped.items():
        color = colors[name]
        draw.ellipse((point[0] - 13, point[1] - 13, point[0] + 13, point[1] + 13), fill=(255, 255, 255), outline=color, width=6)
        draw.text((point[0] + 18, point[1] - 14), name, font=font(19, True), fill=color)

    rx = 650
    draw.rounded_rectangle((rx, 160, 2035, 730), radius=26, fill=(255, 255, 255), outline=(196, 204, 218), width=2)
    draw.text((rx + 35, 190), "实际层级与主控制归属", font=font(31, True), fill=(29, 35, 47))
    hierarchy = [
        ("Root", 0, (64, 72, 88)),
        ("D_LeftShoulder  Rotation  pivot (176,257)", 1, colors["D_LeftShoulder"]),
        ("01_sleeve_screen_left  → shoulder", 2, (95, 105, 121)),
        ("02_upper_arm_screen_left  → shoulder", 2, (95, 105, 121)),
        ("D_LeftElbow  Rotation  pivot (153,411)", 2, colors["D_LeftElbow"]),
        ("D_LeftForearmRootTaper  Warp 5×5 / 2×2", 3, (41, 142, 126)),
        ("03_forearm_bracelet_screen_left  → taper", 4, (95, 105, 121)),
        ("D_LeftWrist  Rotation  pivot (115,529)", 3, colors["D_LeftWrist"]),
        ("04_whole_hand_screen_left  → wrist", 4, (95, 105, 121)),
    ]
    y = 250
    for text, depth, color in hierarchy:
        draw.text((rx + 45 + depth * 42, y), text, font=font(23, depth <= 1), fill=color)
        y += 47

    draw.rounded_rectangle((rx, 760, 2035, 1235), radius=26, fill=(255, 255, 255), outline=(196, 204, 218), width=2)
    draw.text((rx + 35, 790), "节点门禁", font=font(31, True), fill=(29, 35, 47))
    gate_rows = [
        "• V15 冻结 ArtMesh：15/15 未变化。",
        "• 四个 ArtMesh 各有且仅有一个主控制器。",
        "• 肩部父级为 Root；肘部父级为肩部；前臂网格与腕部父级为肘部。",
        "• PSD 保持 512×1086、四层、无缩放/平移/重采样。",
        "• 当前未创建连续参数关键形、Physics 或 Runtime。",
        "• 请重点看：肩/肘/腕轴心是否落在关节处，层级是否符合动作直觉。",
    ]
    y = 850
    for row in gate_rows:
        draw.text((rx + 42, y), row, font=font(22), fill=(63, 72, 88))
        y += 58
    draw.rounded_rectangle((rx + 38, 1135, 1995, 1205), radius=16, fill=(255, 239, 199))
    draw.text(
        (rx + 62, 1156),
        "当前停止点：节点视觉批准前不写入任何主动运动参数。",
        font=font(23, True),
        fill=(137, 84, 0),
    )
    BOARD.parent.mkdir(parents=True, exist_ok=True)
    board.save(BOARD)


def main() -> None:
    v15 = verify_manifest(V15_MANIFEST, V15)
    psd_report = json.loads(PSD_REPORT.read_text(encoding="utf-8"))
    if not v15["pass"] or v15["matchedArtifacts"] != 15:
        raise RuntimeError("V15 freeze verification failed.")
    if psd_report["status"] != "pass_psd_structure":
        raise RuntimeError("V16 PSD structure audit failed.")
    if not CMO3.exists() or CMO3.stat().st_size == 0:
        raise RuntimeError("V16 CMO3 is missing.")

    render_board()
    node_contract = {
        "root": "Root",
        "nodes": [
            {"id": "D_LeftShoulder", "type": "Rotation", "pivotPx": [176, 257], "parent": "Root"},
            {"id": "D_LeftElbow", "type": "Rotation", "pivotPx": [153, 411], "parent": "D_LeftShoulder"},
            {
                "id": "D_LeftForearmRootTaper",
                "type": "Warp",
                "divisions": [5, 5],
                "bezierDivisions": [2, 2],
                "parent": "D_LeftElbow",
            },
            {"id": "D_LeftWrist", "type": "Rotation", "pivotPx": [115, 529], "parent": "D_LeftElbow"},
        ],
        "primaryController": {
            "01_sleeve_screen_left": "D_LeftShoulder",
            "02_upper_arm_screen_left": "D_LeftShoulder",
            "03_forearm_bracelet_screen_left": "D_LeftForearmRootTaper",
            "04_whole_hand_screen_left": "D_LeftWrist",
        },
        "drawOrderBackToFront": [
            {"material": "02_upper_arm_screen_left", "order": 100},
            {"material": "04_whole_hand_screen_left", "order": 200},
            {"material": "03_forearm_bracelet_screen_left", "order": 300},
            {"material": "01_sleeve_screen_left", "order": 400},
        ],
    }
    report = {
        "schemaVersion": 1,
        "status": "engineering_pass_pending_user_visual_approval",
        "engineeringPass": True,
        "inputIntegrity": {
            "v15Freeze": v15,
            "v16Psd": psd_report,
        },
        "cubism": {
            "actualGuiCreation": True,
            "savedModel": "cubism/xiaoxing-arm-chain-screen-left-v16-nodes.cmo3",
            "sha256": sha256(CMO3),
            "bytes": CMO3.stat().st_size,
            "nodeContract": node_contract,
        },
        "verifiedInCubism": [
            "four imported ArtMeshes",
            "four actual deformers",
            "one parent per deformer",
            "one primary controller per ArtMesh",
            "hierarchy Root -> shoulder -> elbow -> taper/wrist",
            "default visible arm unchanged after node creation",
        ],
        "notCreated": [
            "active parameter keyforms",
            "Physics",
            "Runtime",
        ],
        "reviewBoard": "qa/V16-NODE-USER-REVIEW.zh-CN.png",
        "nextGateIfApproved": "continuous shoulder elbow wrist and local taper parameter motion",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_ZH.write_text(
        f"""# V16 画面左侧手臂节点工程报告

- 状态：工程检查通过，等待用户节点视觉批准；
- V15 冻结输入：{v15['matchedArtifacts']}/{v15['artifactCount']}；
- PSD：512×1086，四层，无缩放、平移或重采样；
- Cubism：四个 ArtMesh、四个实际 Deformer，工程已保存；
- 层级：`Root → Shoulder → Elbow → ForearmRootTaper / Wrist`；
- 当前未创建主动参数关键形、Physics 或 Runtime。
""",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "v15Freeze": f"{v15['matchedArtifacts']}/{v15['artifactCount']}",
                "cmo3Bytes": CMO3.stat().st_size,
                "cmo3Sha256": sha256(CMO3),
                "reviewBoard": BOARD.relative_to(STAGE).as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
