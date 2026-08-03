from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
XIAOXING = ROOT.parents[1]
V34 = (
    XIAOXING
    / "validation/arm-chain-screen-left-v34-hand-root-from-frozen-ucap"
)
V34_FREEZE = V34 / "audit/v34-hand-stage-a-freeze-manifest-2026-07-29.json"
APPROVAL = (
    ROOT
    / "audit/user-visual-approval-and-freeze-authorization-2026-07-30.json"
)
FREEZE = ROOT / "audit/v36-hand-geometry-and-texture-freeze-manifest-2026-07-30.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def verify_v34_geometry() -> dict:
    manifest = json.loads(V34_FREEZE.read_text(encoding="utf-8"))
    checks = []
    for item in manifest["lockedGeometry"]:
        path = V34 / item["path"]
        actual = sha256(path)
        checks.append(
            {
                "path": item["path"],
                "expectedSha256": item["sha256"],
                "actualSha256": actual,
                "match": actual == item["sha256"],
            }
        )
    return {
        "manifest": V34_FREEZE.relative_to(XIAOXING).as_posix(),
        "manifestSha256": sha256(V34_FREEZE),
        "status": manifest["status"],
        "checks": checks,
        "mismatchCount": sum(not item["match"] for item in checks),
        "pass": all(item["match"] for item in checks),
    }


def hash_items(paths: list[str]) -> list[dict]:
    return [{"path": path, "sha256": sha256(ROOT / path)} for path in paths]


def verify_items(items: list[dict]) -> dict:
    checks = []
    for item in items:
        actual = sha256(ROOT / item["path"])
        checks.append(
            {
                "path": item["path"],
                "expectedSha256": item["sha256"],
                "actualSha256": actual,
                "match": actual == item["sha256"],
            }
        )
    return {
        "checks": checks,
        "mismatchCount": sum(not item["match"] for item in checks),
        "pass": all(item["match"] for item in checks),
    }


def main() -> None:
    report_path = ROOT / "audit/machine-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    geometry = report["geometry"]
    stress = geometry["wristStress"]

    assert report["status"] == "candidate_pending_user_visual_approval"
    assert geometry["handPixelsAboveBluePx"] == 0
    assert geometry["textureAlphaMismatchPx"] == 0
    assert geometry["texturedRecompositionChannelMismatchCount"] == 0
    assert geometry["forearmSkinConnectedComponents"] == 1
    assert stress["minimumOverlapPx"] > 0
    assert stress["disconnectCount"] == 0

    upstream = verify_v34_geometry()
    assert upstream["pass"]

    approval = {
        "schemaVersion": 1,
        "decisionDate": "2026-07-30",
        "decisionOwner": "user",
        "status": "user_visual_approved_and_freeze_authorized",
        "userDecision": "可以，冻结吧",
        "approvedScope": {
            "character": "xiaoxing",
            "side": "screen-left",
            "part": "hand",
            "definition": (
                "the registered user blue line is the final upper boundary; "
                "the blue line and source skin below it are the complete hand; "
                "there is no hidden hand fill above the line"
            ),
            "textureSource": "Reset source pixels under the locked hand mask",
        },
        "approvedReview": {
            "path": "qa/V36-手部色块与实际纹理效果-冻结审查图.png",
            "sha256": sha256(
                ROOT / "qa/V36-手部色块与实际纹理效果-冻结审查图.png"
            ),
        },
        "approvedEngineeringEvidence": {
            "handPixelsAboveBoundaryPx": geometry["handPixelsAboveBluePx"],
            "textureAlphaMismatchPx": geometry["textureAlphaMismatchPx"],
            "texturedRecompositionChannelMismatchCount": geometry[
                "texturedRecompositionChannelMismatchCount"
            ],
            "neutralForearmHandOverlapPx": geometry[
                "slimForearmCapHandOverlapPx"
            ],
            "minimumOverlapAcrossStressPx": stress["minimumOverlapPx"],
            "stressDisconnectCount": stress["disconnectCount"],
        },
        "unchangedUpstream": {
            "v34LockedGeometryMismatchCount": upstream["mismatchCount"],
            "pass": upstream["pass"],
        },
    }
    save_json(APPROVAL, approval)

    locked_geometry_paths = [
        "references/user-blue-hidden-root-boundary.png",
        "masks/reference/user-blue-boundary-registered.png",
        "masks/reference/user-blue-excluded-above-line.png",
        "masks/visible/hand.png",
        "masks/hidden/hand.png",
        "masks/complete/hand.png",
        "materials/hand-skin-boundary.png",
        "materials/hand-textured-from-reset.png",
    ]
    locked_evidence_paths = [
        "qa/V36-手部色块与实际纹理效果-冻结审查图.png",
        "qa/textured-hand-reset-recomposition.png",
        "qa/screen-left-full-arm-recomposition.png",
        "qa/wrist-stress-samples.png",
        "audit/machine-report.json",
        "audit/user-visual-approval-and-freeze-authorization-2026-07-30.json",
        "tools/build_v36_user_blue_hand_boundary.py",
        "tools/freeze_v36_user_blue_hand.py",
    ]
    locked_geometry = hash_items(locked_geometry_paths)
    locked_evidence = hash_items(locked_evidence_paths)
    freeze = {
        "schemaVersion": 1,
        "checkpoint": "v36_screen_left_hand_user_blue_boundary_frozen",
        "freezeDate": "2026-07-30",
        "decisionOwner": "user",
        "status": "frozen_engineering_and_user_visual_pass",
        "scope": (
            "screen-left hand geometry and Reset-derived texture; user blue "
            "line is the final upper boundary and no hand pixels exist above it"
        ),
        "checksumAlgorithm": "SHA-256",
        "userApproval": {
            "path": APPROVAL.relative_to(ROOT).as_posix(),
            "sha256": sha256(APPROVAL),
        },
        "upstreamV34Integrity": upstream,
        "engineeringSummary": {
            "handPixelsAboveBoundaryPx": geometry["handPixelsAboveBluePx"],
            "textureAlphaMismatchPx": geometry["textureAlphaMismatchPx"],
            "texturedRecompositionChannelMismatchCount": geometry[
                "texturedRecompositionChannelMismatchCount"
            ],
            "neutralForearmHandOverlapPx": geometry[
                "slimForearmCapHandOverlapPx"
            ],
            "minimumOverlapAcrossStressPx": stress["minimumOverlapPx"],
            "stressDisconnectCount": stress["disconnectCount"],
            "forearmSkinConnectedComponents": geometry[
                "forearmSkinConnectedComponents"
            ],
        },
        "lockedGeometry": locked_geometry,
        "lockedEvidence": locked_evidence,
        "invalidationRule": (
            "any byte change to a locked artifact reopens the screen-left "
            "hand geometry, texture, engineering, and visual gates"
        ),
        "nextGate": "none authorized; remain at the frozen V36 checkpoint",
    }
    save_json(FREEZE, freeze)

    geometry_check = verify_items(locked_geometry)
    evidence_check = verify_items(locked_evidence)
    upstream_after = verify_v34_geometry()
    assert geometry_check["pass"]
    assert evidence_check["pass"]
    assert upstream_after["pass"]
    print(
        json.dumps(
            {
                "status": freeze["status"],
                "lockedGeometryCount": len(locked_geometry),
                "lockedEvidenceCount": len(locked_evidence),
                "geometryMismatchCount": geometry_check["mismatchCount"],
                "evidenceMismatchCount": evidence_check["mismatchCount"],
                "upstreamV34MismatchCount": upstream_after["mismatchCount"],
                "minimumOverlapAcrossStressPx": stress["minimumOverlapPx"],
                "stressDisconnectCount": stress["disconnectCount"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
