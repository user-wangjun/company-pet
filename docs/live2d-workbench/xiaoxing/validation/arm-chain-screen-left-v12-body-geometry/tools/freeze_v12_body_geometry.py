from __future__ import annotations

import hashlib
import json
from pathlib import Path


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
AUDIT = STAGE / "audit"
APPROVAL = AUDIT / "v12-user-visual-approval-body-geometry-2026-07-27.json"
MANIFEST = AUDIT / "v12-body-geometry-freeze-manifest-2026-07-27.json"
V10_MANIFEST = (
    WORKBENCH
    / "validation/arm-chain-screen-right-v10-minimal-cubism-rough-rig/audit"
    / "v10-freeze-manifest-2026-07-27.json"
)
V11_MANIFEST = (
    WORKBENCH
    / "validation/arm-chain-screen-right-v11-automation-prototype/audit"
    / "v11-freeze-manifest-2026-07-27.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record(path: Path, role: str) -> dict:
    return {
        "role": role,
        "path": path.relative_to(STAGE).as_posix(),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    contract_path = STAGE / "contracts/v12-screen-left-body-geometry-contract.json"
    audit_path = STAGE / "audit/v12-screen-left-material-inventory-and-geometry-audit.json"
    report_path = STAGE / "audit/V12-SCREEN-LEFT-BODY-GEOMETRY-REVIEW.zh-CN.md"
    board_path = STAGE / "qa/V12-SCREEN-LEFT-BODY-GEOMETRY-REVIEW.zh-CN.png"
    builder_path = STAGE / "tools/build_v12_screen_left_body_geometry.py"
    freeze_tool_path = STAGE / "tools/freeze_v12_body_geometry.py"

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if contract["candidateB"]["status"] != "user_visual_approved":
        raise RuntimeError("Candidate B is not recorded as user visually approved.")
    if audit["status"] != "body_geometry_user_visual_approved_ready_to_freeze":
        raise RuntimeError("V12 audit is not ready to freeze.")
    if not audit["frozenBoundaryReadOnlyVerification"]["pass"]:
        raise RuntimeError("V10/V11 read-only freeze verification did not pass.")

    approval = {
        "schemaVersion": 1,
        "checkpoint": "V12 screen-left arm body geometry candidate B",
        "decisionDate": "2026-07-27",
        "decisionOwner": "user",
        "decision": "approved",
        "decisionText": "合适，请继续任务",
        "revisionFeedback": "整体偏向了右下一点",
        "approvedRevision": "candidate B translates the complete shoulder-elbow-wrist axis 4 px left and 4 px up while preserving both frozen bone lengths",
        "approvedCoordinatesPx": {
            "shoulder": contract["candidateB"]["shoulderPx"],
            "elbow": contract["candidateB"]["elbowPx"],
            "wrist": contract["candidateB"]["wristPx"],
            "L1": contract["candidateB"]["L1Px"],
            "L2": contract["candidateB"]["L2Px"],
        },
        "approvedEvidence": {
            "reviewBoard": {
                "path": board_path.relative_to(STAGE).as_posix(),
                "sha256": sha256(board_path),
            },
            "contract": {
                "path": contract_path.relative_to(STAGE).as_posix(),
                "sha256": sha256(contract_path),
            },
        },
        "authorization": {
            "completeMaterialSeparation": True,
            "meshBeforeMaterialVisualApproval": False,
            "physics": False,
            "runtime": False,
        },
    }
    write_json(APPROVAL, approval)

    locked = [
        record(APPROVAL, "user visual approval and authorization for material separation"),
        record(contract_path, "approved screen-left arm body geometry contract"),
        record(audit_path, "material inventory and geometry audit"),
        record(report_path, "Chinese body geometry review report"),
        record(board_path, "approved minimal body geometry review board"),
        record(builder_path, "deterministic body geometry evidence builder"),
        record(freeze_tool_path, "V12 freeze manifest builder"),
    ]
    manifest = {
        "schemaVersion": 1,
        "checkpoint": "V12 screen-left arm body geometry",
        "freezeDate": "2026-07-27",
        "decisionOwner": "user",
        "status": "frozen_v12_screen_left_body_geometry_user_approved",
        "scope": "screen-left arm, character anatomical right; shoulder-elbow-wrist body geometry only",
        "approvedCandidate": "B",
        "frozenGeometry": approval["approvedCoordinatesPx"],
        "upstreamReadOnlyReferences": [
            {
                "path": V10_MANIFEST.relative_to(WORKBENCH).as_posix(),
                "sha256": sha256(V10_MANIFEST),
                "matchedArtifacts": 38,
                "artifactCount": 38,
            },
            {
                "path": V11_MANIFEST.relative_to(WORKBENCH).as_posix(),
                "sha256": sha256(V11_MANIFEST),
                "matchedArtifacts": 13,
                "artifactCount": 13,
            },
        ],
        "lockedArtifacts": locked,
        "artifactCount": len(locked),
        "invalidationRules": [
            "Any byte change to a locked V12 artifact reopens the body geometry gate.",
            "Any change to shoulder, elbow, wrist, L1, L2, screen-side identity, or the registered source canvas reopens V12.",
            "Any mismatch in the referenced V10 or V11 freeze invalidates downstream comparisons.",
            "Material separation must preserve this geometry and requires a separate user visual gate before mesh work.",
        ],
        "explicitlyNotApproved": [
            "mesh",
            "nodes",
            "continuous parameter motion",
            "Physics",
            "Runtime",
            "platform integration",
        ],
        "nextGate": "complete screen-left arm material separation and visual review",
    }
    write_json(MANIFEST, manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "artifactCount": manifest["artifactCount"],
                "manifestSha256": sha256(MANIFEST),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
