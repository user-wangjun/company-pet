from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WORKBENCH = Path(__file__).resolve().parents[3]
STAGE = Path(__file__).resolve().parents[1]
V10 = WORKBENCH / "validation" / "arm-chain-screen-right-v10-minimal-cubism-rough-rig"
V11 = WORKBENCH / "validation" / "arm-chain-screen-right-v11-automation-prototype"

FRONT_COLOR = WORKBENCH / "source" / "masters" / "front-color-source-exact-after-reset.png"
FRONT_LINE = WORKBENCH / "source" / "masters" / "front-line-source-exact-after-reset.png"
THREE_VIEW_COLOR = WORKBENCH / "source" / "xiaoxing-three-view-color.png"
BODY_CONTRACT = WORKBENCH / "blueprints" / "gate2a-canonical-body-contract.json"
V10_CONTRACT = V10 / "contracts" / "v10-minimal-cubism-rig-contract.json"
V10_MANIFEST = V10 / "audit" / "v10-freeze-manifest-2026-07-27.json"
V11_MANIFEST = V11 / "audit" / "v11-freeze-manifest-2026-07-27.json"

CONTRACT_OUT = STAGE / "contracts" / "v12-screen-left-body-geometry-contract.json"
AUDIT_OUT = STAGE / "audit" / "v12-screen-left-material-inventory-and-geometry-audit.json"
REPORT_OUT = STAGE / "audit" / "V12-SCREEN-LEFT-BODY-GEOMETRY-REVIEW.zh-CN.md"
BOARD_OUT = STAGE / "qa" / "V12-SCREEN-LEFT-BODY-GEOMETRY-REVIEW.zh-CN.png"

CANVAS = (512, 1086)
FRONT_CROP_OFFSET_X = 34
CENTER_X = 256.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_manifest(manifest_path: Path, root: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = []
    for item in manifest["lockedArtifacts"]:
        artifact = (root / item["path"]).resolve()
        exists = artifact.is_file()
        actual_bytes = artifact.stat().st_size if exists else None
        actual_hash = sha256(artifact) if exists else None
        checks.append(
            {
                "path": item["path"],
                "exists": exists,
                "bytesMatch": actual_bytes == item["bytes"],
                "sha256Match": actual_hash == item["sha256"],
            }
        )
    return {
        "manifest": manifest_path.relative_to(WORKBENCH).as_posix(),
        "manifestSha256": sha256(manifest_path),
        "artifactCount": len(checks),
        "matchedArtifacts": sum(
            c["exists"] and c["bytesMatch"] and c["sha256Match"] for c in checks
        ),
        "pass": all(
            c["exists"] and c["bytesMatch"] and c["sha256Match"] for c in checks
        ),
        "checks": checks,
    }


def length(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def front_landmark(body: dict, key: str) -> tuple[float, float]:
    point = next(p for p in body["landmarks"][key] if p["view"] == "front")
    return (float(point["x"] - FRONT_CROP_OFFSET_X), float(point["y"]))


def locate_exact_front_crop() -> list[int]:
    three = Image.open(THREE_VIEW_COLOR).convert("RGB")
    front = Image.open(FRONT_COLOR).convert("RGB")
    matches = []
    for x in range(three.width - front.width + 1):
        if three.crop((x, 0, x + front.width, front.height)).tobytes() == front.tobytes():
            matches.append(x)
    return matches


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def draw_point(
    draw: ImageDraw.ImageDraw,
    point: tuple[float, float],
    crop: tuple[int, int, int, int],
    origin: tuple[int, int],
    scale: float,
    color: tuple[int, int, int],
    label: str,
) -> None:
    x = origin[0] + (point[0] - crop[0]) * scale
    y = origin[1] + (point[1] - crop[1]) * scale
    r = 8
    draw.ellipse((x - r, y - r, x + r, y + r), fill=color, outline="white", width=2)
    draw.text((x + 12, y - 18), label, font=font(22, True), fill=color)


def draw_chain(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    crop: tuple[int, int, int, int],
    origin: tuple[int, int],
    scale: float,
    color: tuple[int, int, int],
    labels: list[str],
    width: int = 6,
) -> None:
    mapped = [
        (origin[0] + (p[0] - crop[0]) * scale, origin[1] + (p[1] - crop[1]) * scale)
        for p in points
    ]
    draw.line(mapped, fill=color, width=width)
    for point, label in zip(points, labels):
        draw_point(draw, point, crop, origin, scale, color, label)


def make_board(
    revised_chain: list[tuple[float, float]],
    previous_chain: list[tuple[float, float]],
    v10_l1: float,
    v10_l2: float,
) -> None:
    board = Image.new("RGB", (1900, 1260), (245, 246, 248))
    draw = ImageDraw.Draw(board)
    draw.text((55, 35), "小星 V12｜画面左侧手臂：身体几何最小审查", font=font(42, True), fill=(25, 31, 42))
    draw.text(
        (57, 95),
        "只审肩—肘—腕与左右身份；不审材料、网格、节点、Physics 或 Runtime",
        font=font(24),
        fill=(75, 82, 94),
    )

    crop = (55, 210, 190, 650)
    scale = 2.25
    panel_y = 180
    color = Image.open(FRONT_COLOR).convert("RGB").crop(crop)
    line = Image.open(FRONT_LINE).convert("RGB").crop(crop)
    color = color.resize((round(color.width * scale), round(color.height * scale)), Image.Resampling.NEAREST)
    line = line.resize((round(line.width * scale), round(line.height * scale)), Image.Resampling.NEAREST)
    board.paste(color, (55, panel_y))
    board.paste(line, (425, panel_y))

    cyan = (0, 155, 210)
    gray = (132, 139, 151)
    previous_mapped = [
        (425 + (p[0] - crop[0]) * scale, panel_y + (p[1] - crop[1]) * scale)
        for p in previous_chain
    ]
    draw_chain(draw, revised_chain, crop, (55, panel_y), scale, cyan, ["肩 S", "肘 E", "腕 W"])
    draw.line(previous_mapped, fill=gray, width=4)
    draw_chain(draw, revised_chain, crop, (425, panel_y), scale, cyan, ["肩 S", "肘 E", "腕 W"])

    draw.text((55, 1190), "原彩稿 + 左上修正候选", font=font(24, True), fill=cyan)
    draw.text((425, 1190), "线稿：青=修正后；灰=上一版", font=font(24, True), fill=(55, 60, 68))

    x = 800
    draw.rounded_rectangle((x, 180, 1845, 690), radius=24, fill=(255, 255, 255), outline=(208, 213, 221), width=2)
    draw.text((x + 35, 215), "身份与现有素材", font=font(30, True), fill=(25, 31, 42))
    lines = [
        "• 画面左侧 = 角色自身右臂（正面视图）。",
        "• 独立袖型、手链、手掌与手指轮廓均在当前原稿中存在。",
        "• 肩根和上臂被袖子遮挡；腕根被手链遮挡。",
        "• 原图没有可见肘线，肘点只能由骨长与轮廓共同约束。",
        "• 历史 V5–V15 分层已否决，不作为第二臂生产材料。",
        "• 正式材料不得镜像第一臂；必须保留本侧独有像素与姿态。",
    ]
    for i, text in enumerate(lines):
        draw.text((x + 38, 275 + i * 58), text, font=font(23), fill=(48, 55, 66))

    draw.rounded_rectangle((x, 725, 1845, 1165), radius=24, fill=(255, 255, 255), outline=(208, 213, 221), width=2)
    draw.text((x + 35, 760), "候选 B：整体左上平移 4 px", font=font(30, True), fill=cyan)
    metrics = [
        f"S = ({revised_chain[0][0]:.0f}, {revised_chain[0][1]:.0f})",
        f"E = ({revised_chain[1][0]:.0f}, {revised_chain[1][1]:.0f})",
        f"W = ({revised_chain[2][0]:.0f}, {revised_chain[2][1]:.0f})",
        f"L1 = {length(revised_chain[0], revised_chain[1]):.6f} px（目标 {v10_l1:.6f}）",
        f"L2 = {length(revised_chain[1], revised_chain[2]):.6f} px（目标 {v10_l2:.6f}）",
        "修正方式：S、E、W 同时左移 4 px、上移 4 px；骨长不变。",
    ]
    for i, text in enumerate(metrics):
        draw.text((x + 40, 825 + i * 47), text, font=font(23), fill=(48, 55, 66))
    draw.rounded_rectangle((x + 35, 1100, 1810, 1140), radius=12, fill=(221, 243, 227))
    draw.text(
        (x + 55, 1105),
        "视觉结论：用户已确认候选 B 合适；允许进入第二臂材料分离。",
        font=font(22, True),
        fill=(44, 112, 67),
    )
    BOARD_OUT.parent.mkdir(parents=True, exist_ok=True)
    board.save(BOARD_OUT)


def main() -> None:
    body = json.loads(BODY_CONTRACT.read_text(encoding="utf-8"))
    v10 = json.loads(V10_CONTRACT.read_text(encoding="utf-8"))
    v10_chain = [
        tuple(v10["frozenSkeleton"]["shoulder"]),
        tuple(v10["frozenSkeleton"]["elbow"]),
        tuple(v10["frozenSkeleton"]["wrist"]),
    ]
    previous_chain = [(2 * CENTER_X - x, y) for x, y in v10_chain]
    revised_chain = [(x - 4.0, y - 4.0) for x, y in previous_chain]
    legacy_chain = [
        front_landmark(body, "shoulder_L"),
        front_landmark(body, "elbow_L"),
        front_landmark(body, "wrist_L"),
    ]
    v10_l1 = float(v10["frozenSkeleton"]["L1Px"])
    v10_l2 = float(v10["frozenSkeleton"]["L2Px"])

    v10_freeze = verify_manifest(V10_MANIFEST, V10)
    v11_freeze = verify_manifest(V11_MANIFEST, V11)
    crop_matches = locate_exact_front_crop()
    sources = []
    for path, role in [
        (THREE_VIEW_COLOR, "identity and three-view color source"),
        (FRONT_COLOR, "exact registered front color source"),
        (FRONT_LINE, "exact registered front line source"),
        (BODY_CONTRACT, "approved whole-body landmark contract"),
        (V10_CONTRACT, "frozen screen-right arm tolerance and bone-length reference"),
    ]:
        sources.append(
            {
                "role": role,
                "path": path.relative_to(WORKBENCH).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
        )

    contract = {
        "schemaVersion": 1,
        "checkpoint": "V12 screen-left arm body geometry only",
        "status": "engineering_candidate_pending_user_visual_approval",
        "scope": "screen-left arm, character anatomical right; shoulder-elbow-wrist geometry only",
        "canvas": {"width": 512, "height": 1086, "origin": "top_left"},
        "identity": {
            "screenSide": "left",
            "characterSide": "right",
            "namingRule": "screen side first; character anatomical side written explicitly",
            "legacyBodyContractCaution": "The legacy landmark keys place shoulder_L/elbow_L/wrist_L on screen-left despite its prose saying L/R is anatomical. Coordinates are retained only as a legacy candidate, not as side identity authority.",
        },
        "candidateA": {
            "status": "rejected_by_user_directional_feedback",
            "userFeedback": "整体偏向右下一点",
            "shoulderPx": previous_chain[0],
            "elbowPx": previous_chain[1],
            "wristPx": previous_chain[2],
        },
        "candidateB": {
            "status": "user_visual_approved",
            "derivation": "bilateral equal-length geometry reflected about registered front center x=256; no image material was mirrored",
            "revision": "translate the complete shoulder-elbow-wrist chain 4 px left and 4 px up in source-master coordinates",
            "shoulderPx": revised_chain[0],
            "elbowPx": revised_chain[1],
            "wristPx": revised_chain[2],
            "L1Px": length(revised_chain[0], revised_chain[1]),
            "L2Px": length(revised_chain[1], revised_chain[2]),
            "matchesFrozenV10BoneLengths": {
                "L1ErrorPx": abs(length(revised_chain[0], revised_chain[1]) - v10_l1),
                "L2ErrorPx": abs(length(revised_chain[1], revised_chain[2]) - v10_l2),
                "pass": abs(length(revised_chain[0], revised_chain[1]) - v10_l1) < 1e-6
                and abs(length(revised_chain[1], revised_chain[2]) - v10_l2) < 1e-6,
            },
        },
        "legacyGate2ACandidate": {
            "shoulderPx": legacy_chain[0],
            "elbowPx": legacy_chain[1],
            "wristPx": legacy_chain[2],
            "L1Px": length(legacy_chain[0], legacy_chain[1]),
            "L2Px": length(legacy_chain[1], legacy_chain[2]),
            "reasonNotSelected": "does not preserve the current frozen single-arm bone lengths and places the inferred elbow about 20 px farther outward",
        },
        "occlusionAndHiddenRegions": [
            "shoulder root and upper arm are hidden beneath the screen-left sleeve",
            "no visible elbow line exists in the source; the elbow is an internal articulated boundary",
            "wrist root is hidden beneath the screen-left bracelet",
            "the hand and finger silhouette is side-specific and must remain source-registered",
        ],
        "prohibitions": [
            "do not mirror screen-right arm pixels as formal material",
            "do not reuse rejected V5-V15 masks or material layers",
            "do not start material separation before user approval of this geometry",
            "do not create mesh, nodes, parameter motion, Physics, or Runtime at this checkpoint",
        ],
        "approvalRequired": "satisfied: user confirmed candidate B is suitable",
    }

    historical = [
        "model/working-v8/body-original-pixel/03_sleeve_screen_left.png",
        "model/working-v8/body-original-pixel/05_arm_screen_left_forearm.png",
        "model/working-v8/body-original-pixel/07_hand_screen_left.png",
        "model/working-v11/joint-overlaps/画面左袖子_原像素.png",
        "model/working-v11/joint-overlaps/画面左前臂手链整手_含袖内补全.png",
    ]
    audit = {
        "schemaVersion": 1,
        "status": "body_geometry_user_visual_approved_ready_to_freeze",
        "authoritativeInputs": sources,
        "registration": {
            "frontMasterExactCropOffsetsFound": crop_matches,
            "expectedUniqueOffsetX": FRONT_CROP_OFFSET_X,
            "pass": crop_matches == [FRONT_CROP_OFFSET_X],
        },
        "frozenBoundaryReadOnlyVerification": {
            "v10": {k: v for k, v in v10_freeze.items() if k != "checks"},
            "v11": {k: v for k, v in v11_freeze.items() if k != "checks"},
            "pass": v10_freeze["pass"] and v11_freeze["pass"],
        },
        "currentSecondArmMaterialInventory": {
            "approvedCompleteProductionMaterials": [],
            "sourceVisibleRegions": [
                "screen-left sleeve",
                "screen-left continuous visible arm skin",
                "screen-left bracelet",
                "screen-left whole hand and fingers",
            ],
            "historicalRejectedArtifactsPresentButProhibited": historical,
            "materialGap": "no currently approved complete independent screen-left sleeve, upper-arm, forearm, bracelet-ownership, or whole-hand material set with hidden continuations",
        },
        "geometry": contract,
        "nextGate": {
            "gate": "complete material separation",
            "reason": "body geometry candidate B is user-approved; no current complete production materials exist for the screen-left arm",
            "reviewArtifact": BOARD_OUT.relative_to(WORKBENCH).as_posix(),
            "bodyGeometryStopCleared": True,
        },
    }

    for path in (CONTRACT_OUT, AUDIT_OUT, REPORT_OUT):
        path.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_OUT.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    AUDIT_OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    make_board(revised_chain, previous_chain, v10_l1, v10_l2)

    report = f"""# V12 画面左侧手臂：身体几何审查

## 当前结论

已确认画面左侧为角色自身右臂。当前原稿中存在本侧独立袖型、连续手臂肤色、手链、
整手与手指轮廓；这些像素和姿态不能由已冻结第一臂镜像替代。

V10 冻结 38/38、V11 冻结 {v11_freeze['artifactCount']}/{v11_freeze['artifactCount']}
只读复核通过，未改写任何冻结工件。正面母稿仍是三视图彩稿从 x={FRONT_CROP_OFFSET_X}
开始的唯一 512×1086 整数裁切。

## 最早缺口

原稿没有可见肘线。旧 Gate 2A 的画面左侧肘点与保持 V10 双侧等骨长的候选相差约
20 px；旧候选会产生不同的上下臂长度。候选 A 又被用户指出整体偏向右下一点，
因此当前候选 B 将整条轴统一左移 4 px、上移 4 px：

- 肩：({revised_chain[0][0]:.0f}, {revised_chain[0][1]:.0f})
- 肘：({revised_chain[1][0]:.0f}, {revised_chain[1][1]:.0f})
- 腕：({revised_chain[2][0]:.0f}, {revised_chain[2][1]:.0f})
- 上臂：{length(revised_chain[0], revised_chain[1]):.6f} px
- 前臂：{length(revised_chain[1], revised_chain[2]):.6f} px

该候选只反射骨架坐标来满足双侧等骨长，没有镜像任何图像材料。袖、手链、手掌与
手指仍必须从画面左侧原稿独立构造。

## 批准与后续边界

用户已确认候选 B 合适，身体几何视觉门禁通过，允许进入材料分离。材料通过视觉审查
前仍不进行网格、节点、连续参数运动、Physics 或 Runtime。历史 V5–V15 分层只作失败
追溯，不作为生产输入。
"""
    REPORT_OUT.write_text(report, encoding="utf-8")
    print(json.dumps({
        "status": audit["status"],
        "v10Freeze": f"{v10_freeze['matchedArtifacts']}/{v10_freeze['artifactCount']}",
        "v11Freeze": f"{v11_freeze['matchedArtifacts']}/{v11_freeze['artifactCount']}",
        "frontCropOffsets": crop_matches,
        "board": BOARD_OUT.relative_to(WORKBENCH).as_posix(),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
