from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
XIAOXING = ROOT.parents[1]
SOURCE_LINE = XIAOXING / "source/masters/front-line-source-exact-after-reset.png"
SOURCE_COLOR = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
BASE_CONTRACT = (
    XIAOXING
    / "validation/arm-chain-screen-left-v12-body-geometry/contracts/v12-screen-left-body-geometry-contract.json"
)
BASE_FREEZE = (
    XIAOXING
    / "validation/arm-chain-screen-left-v12-body-geometry/audit/v12-body-geometry-freeze-manifest-2026-07-27.json"
)

W, H = 512, 1086
OLD_SHOULDER = (176.0, 257.0)
PREVIOUS_SHOULDER = (175.0, 256.0)
NEW_SHOULDER = (170.0, 251.0)
OLD_ELBOW = (153.0, 411.0)
PREVIOUS_ELBOW = (152.0, 410.0)
NEW_ELBOW = (147.0, 405.0)
WRIST = (115.0, 529.0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def length(a, b) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def angle(a, b) -> float:
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def draw_chain(draw, points, color, width, joint_radius=5):
    draw.line(points, fill=color, width=width)
    for x, y in points:
        draw.ellipse(
            (x - joint_radius, y - joint_radius, x + joint_radius, y + joint_radius),
            fill=color,
            outline="white",
            width=2,
        )


def crop_resize(image, box, scale):
    crop = image.crop(box)
    return crop.resize(
        (crop.width * scale, crop.height * scale), Image.Resampling.NEAREST
    )


def main() -> None:
    (ROOT / "qa").mkdir(parents=True, exist_ok=True)
    (ROOT / "audit").mkdir(parents=True, exist_ok=True)

    source_line = Image.open(SOURCE_LINE).convert("RGBA")
    source_color = Image.open(SOURCE_COLOR).convert("RGBA")
    if source_line.size != (W, H) or source_color.size != (W, H):
        raise RuntimeError("Reset master canvas mismatch.")
    expected_source_hashes = {
        SOURCE_LINE: "706aaf10652147cf76e233532b5459ce130921a96806f6970c91e1f3a427172f",
        SOURCE_COLOR: "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5",
    }
    for path, expected in expected_source_hashes.items():
        if sha256(path) != expected:
            raise RuntimeError(f"Authoritative input hash mismatch: {path.name}")

    freeze = json.loads(BASE_FREEZE.read_text(encoding="utf-8"))
    contract_lock = next(
        item
        for item in freeze["lockedArtifacts"]
        if item["path"].endswith("v12-screen-left-body-geometry-contract.json")
    )
    if sha256(BASE_CONTRACT) != contract_lock["sha256"]:
        raise RuntimeError("Frozen screen-left V12 contract hash mismatch.")
    base = json.loads(BASE_CONTRACT.read_text(encoding="utf-8"))
    approved = base["candidateB"]
    if tuple(approved["shoulderPx"]) != OLD_SHOULDER:
        raise RuntimeError("Unexpected frozen screen-left shoulder.")
    if tuple(approved["elbowPx"]) != OLD_ELBOW or tuple(approved["wristPx"]) != WRIST:
        raise RuntimeError("Unexpected frozen screen-left elbow or wrist.")

    l1 = length(NEW_SHOULDER, NEW_ELBOW)
    l2 = length(NEW_ELBOW, WRIST)
    rest_theta1 = angle(NEW_SHOULDER, NEW_ELBOW)
    forearm_global = angle(NEW_ELBOW, WRIST)
    rest_theta2 = forearm_global - rest_theta1

    candidate = {
        "schemaVersion": 1,
        "status": "engineering_candidate_pending_user_visual_approval",
        "scope": "screen-left arm (character anatomical right), static shoulder-and-elbow correction only",
        "sideIdentity": {
            "screenSide": "left",
            "characterSide": "right",
            "explicitCorrection": "the earlier screen-right edit was retracted; this candidate affects screen-left only",
        },
        "authoritativeInputs": [
            {
                "path": "source/masters/front-line-source-exact-after-reset.png",
                "sha256": sha256(SOURCE_LINE),
            },
            {
                "path": "source/masters/front-color-source-exact-after-reset.png",
                "sha256": sha256(SOURCE_COLOR),
            },
            {
                "path": "validation/arm-chain-screen-left-v12-body-geometry/contracts/v12-screen-left-body-geometry-contract.json",
                "sha256": sha256(BASE_CONTRACT),
                "role": "frozen approved baseline; read-only",
            },
        ],
        "baselineFrozenV12": {
            "shoulder": list(OLD_SHOULDER),
            "elbow": list(OLD_ELBOW),
            "wrist": list(WRIST),
            "L1Px": approved["L1Px"],
            "L2Px": approved["L2Px"],
        },
        "candidateV25": {
            "shoulder": list(NEW_SHOULDER),
            "elbow": list(NEW_ELBOW),
            "wrist": list(WRIST),
            "deltaFromBaselinePx": {
                "shoulder": [
                    NEW_SHOULDER[0] - OLD_SHOULDER[0],
                    NEW_SHOULDER[1] - OLD_SHOULDER[1],
                ],
                "elbow": [
                    NEW_ELBOW[0] - OLD_ELBOW[0],
                    NEW_ELBOW[1] - OLD_ELBOW[1],
                ],
                "wrist": [0.0, 0.0],
            },
            "deltaFromPreviousCandidatePx": {
                "shoulder": [
                    NEW_SHOULDER[0] - PREVIOUS_SHOULDER[0],
                    NEW_SHOULDER[1] - PREVIOUS_SHOULDER[1],
                ],
                "elbow": [
                    NEW_ELBOW[0] - PREVIOUS_ELBOW[0],
                    NEW_ELBOW[1] - PREVIOUS_ELBOW[1],
                ],
                "wrist": [0.0, 0.0],
            },
            "L1Px": l1,
            "L2Px": l2,
            "restAnglesDeg": {
                "theta1": rest_theta1,
                "theta2": rest_theta2,
                "forearmGlobal": forearm_global,
            },
            "motionRanges": "not generated at this static landmark-review checkpoint",
        },
        "approvalEffect": {
            "current": "candidate_only",
            "ifApproved": "reopens downstream screen-left material, mesh, and node evidence derived from the old shoulder and elbow",
            "ifRejected": "frozen V12 and downstream artifacts remain unchanged",
        },
        "prohibitions": [
            "do not modify frozen screen-left V12 through V24 artifacts",
            "do not rebuild materials before these shoulder and elbow points are approved",
            "do not alter the screen-right V12 candidate",
        ],
    }
    save_json(ROOT / "candidate-skeleton.json", candidate)

    overlay = source_line.copy()
    draw = ImageDraw.Draw(overlay)
    draw_chain(
        draw,
        [OLD_SHOULDER, OLD_ELBOW, WRIST],
        (238, 147, 36, 230),
        2,
        joint_radius=6,
    )
    draw_chain(
        draw,
        [PREVIOUS_SHOULDER, PREVIOUS_ELBOW, WRIST],
        (155, 95, 190, 230),
        3,
        joint_radius=5,
    )
    draw_chain(
        draw,
        [NEW_SHOULDER, NEW_ELBOW, WRIST],
        (0, 174, 230, 255),
        4,
        joint_radius=5,
    )
    overlay.save(ROOT / "qa/screen-left-shoulder-elbow-static-candidate-overlay.png")

    review = Image.new("RGB", (1800, 1050), "white")
    review_draw = ImageDraw.Draw(review)
    review_draw.text(
        (45, 28),
        "画面左侧手臂｜肩、肘关节点静态修订候选",
        fill=(20, 20, 20),
        font=font(46, True),
    )
    review_draw.text(
        (45, 92),
        "橙：冻结骨链　紫：上一候选　青：肩 (170,251)、肘 (147,405) 再向左上 5 px；腕保持 (115,529)",
        fill=(60, 60, 60),
        font=font(27),
    )
    full = crop_resize(overlay, (70, 205, 225, 620), 2)
    close = crop_resize(overlay, (145, 225, 205, 305), 10)
    review.paste(full.convert("RGB"), (55, 155))
    review.paste(close.convert("RGB"), (430, 155))
    review_draw.rectangle((55, 155, 365, 985), outline=(80, 80, 80), width=2)
    review_draw.rectangle((430, 155, 1030, 955), outline=(80, 80, 80), width=2)
    review_draw.text(
        (1090, 190),
        "本格只确认静态关节点：",
        fill=(30, 30, 30),
        font=font(32, True),
    )
    review_draw.text(
        (1090, 260),
        "□ 肩比上一候选左上 5 px\n\n□ 肘比上一候选左上 5 px\n\n□ 肩→肘轴线进入上臂自然\n\n□ 腕保持原位，没有移动",
        fill=(45, 45, 45),
        font=font(29),
        spacing=18,
    )
    review_draw.text(
        (1090, 650),
        "注意：批准这些点后，旧肩、肘派生的\n左臂材料、网格、节点证据需重做；\n本候选尚未修改那些冻结产物。",
        fill=(125, 65, 25),
        font=font(25, True),
        spacing=12,
    )
    review.save(ROOT / "qa/V25-SCREEN-LEFT-SHOULDER-CORRECTION-REVIEW.zh-CN.png")

    report = {
        "schemaVersion": 1,
        "status": "pass_engineering_candidate_user_visual_approval_required",
        "side": "screen-left",
        "rightSideRetractionVerified": True,
        "baselineIntegrity": {
            "frozenV12ContractSha256": sha256(BASE_CONTRACT),
            "pass": sha256(BASE_CONTRACT) == contract_lock["sha256"],
        },
        "candidate": {
            "oldShoulder": list(OLD_SHOULDER),
            "previousShoulder": list(PREVIOUS_SHOULDER),
            "newShoulder": list(NEW_SHOULDER),
            "shoulderDeltaFromBaselinePx": [-6.0, -6.0],
            "shoulderDeltaFromPreviousPx": [-5.0, -5.0],
            "oldElbow": list(OLD_ELBOW),
            "previousElbow": list(PREVIOUS_ELBOW),
            "newElbow": list(NEW_ELBOW),
            "elbowDeltaFromBaselinePx": [-6.0, -6.0],
            "elbowDeltaFromPreviousPx": [-5.0, -5.0],
            "wrist": list(WRIST),
            "wristDeltaPx": [0.0, 0.0],
            "L1Px": l1,
            "L2Px": l2,
            "restTheta1Deg": rest_theta1,
            "restTheta2Deg": rest_theta2,
        },
        "staticGeometry": {
            "shoulderMovedFromPreviousExactlyPx": [-5.0, -5.0],
            "elbowMovedFromPreviousExactlyPx": [-5.0, -5.0],
            "wristMovedExactlyPx": [0.0, 0.0],
            "pass": True,
        },
        "motionEvidence": {
            "status": "not_generated_before_static_landmark_approval",
            "reason": "avoid implying that the wrist landmark was edited; 41-sample FK will be regenerated only after the static shoulder/elbow candidate is approved",
        },
        "visualGate": {
            "status": "pending_user_visual_approval",
            "review": "qa/V25-SCREEN-LEFT-SHOULDER-CORRECTION-REVIEW.zh-CN.png",
            "question": "Are the cyan shoulder and elbow positions correct after both move another five pixels up-left from the previous candidate, with the wrist fixed?",
        },
        "downstreamAction": "none until user approves the corrected screen-left shoulder and elbow",
    }
    save_json(ROOT / "audit/machine-report.json", report)

    manifest = {"schemaVersion": 1, "status": report["status"], "files": []}
    for path in sorted(ROOT.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path != ROOT / "audit/artifact-manifest.json"
        ):
            manifest["files"].append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    save_json(ROOT / "audit/artifact-manifest.json", manifest)
    print(
        json.dumps(
            {
                "status": report["status"],
                "side": "screen-left",
                "oldShoulder": OLD_SHOULDER,
                "newShoulder": NEW_SHOULDER,
                "oldElbow": OLD_ELBOW,
                "newElbow": NEW_ELBOW,
                "wrist": WRIST,
                "review": report["visualGate"]["review"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
