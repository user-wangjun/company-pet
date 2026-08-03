from __future__ import annotations

import hashlib
import json
from pathlib import Path


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
AUDIT = STAGE / "audit"
APPROVAL = AUDIT / "v13-user-visual-approval-material-boundaries-2026-07-27.json"
MANIFEST = AUDIT / "v13-material-boundary-freeze-manifest-2026-07-27.json"
V12_MANIFEST = (
    WORKBENCH
    / "validation/arm-chain-screen-left-v12-body-geometry/audit"
    / "v12-body-geometry-freeze-manifest-2026-07-27.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record(path: Path, role: str) -> dict:
    return {
        "role": role,
        "path": path.relative_to(STAGE).as_posix(),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def main() -> None:
    report_path = AUDIT / "v13-material-separation-engineering-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report["status"] != "user_visual_approved_ready_to_freeze":
        raise RuntimeError("V13 report is not approved and ready to freeze.")
    if not report["engineeringPass"]:
        raise RuntimeError("V13 engineering checks did not pass.")
    if report["inputIntegrity"]["v12Freeze"]["matchedArtifacts"] != 7:
        raise RuntimeError("V12 freeze no longer matches 7/7.")

    board = STAGE / "qa/V13-MATERIAL-BOUNDARY-USER-REVIEW.zh-CN.png"
    contract = STAGE / "contracts/v13-material-ownership-contract.json"
    approval = {
        "schemaVersion": 1,
        "checkpoint": "V13 screen-left arm material boundaries and hidden overlaps",
        "decisionDate": "2026-07-27",
        "decisionOwner": "user",
        "decision": "approved",
        "decisionText": "合适，请继续任务",
        "approvedScope": [
            "screen-left sleeve visible ownership and complete hidden shoulder cap",
            "upper-arm and forearm split at the approved elbow",
            "bracelet uniquely owned by forearm_bracelet",
            "whole-hand ownership including one source-registered enclosed finger gap",
            "hidden shoulder, elbow and wrist overlaps",
            "41 pull samples and 3 reviewed extrema",
        ],
        "approvedEvidence": {
            "reviewBoard": {
                "path": board.relative_to(STAGE).as_posix(),
                "sha256": sha256(board),
            },
            "contract": {
                "path": contract.relative_to(STAGE).as_posix(),
                "sha256": sha256(contract),
            },
        },
        "authorization": {
            "textureInsideApprovedMasks": True,
            "meshBeforeTextureVisualApproval": False,
            "physics": False,
            "runtime": False,
        },
    }
    write_json(APPROVAL, approval)

    paths: list[tuple[Path, str]] = [
        (APPROVAL, "user visual approval and texture authorization"),
        (report_path, "V13 material separation engineering report"),
        (AUDIT / "V13-MATERIAL-SEPARATION-REPORT.zh-CN.md", "Chinese V13 report"),
        (contract, "approved four-layer ownership contract"),
        (board, "approved material-boundary review board"),
        (STAGE / "tools/build_v13_material_separation.py", "deterministic V13 evidence builder"),
        (STAGE / "tools/freeze_v13_material_boundaries.py", "V13 freeze manifest builder"),
    ]
    for group in ("visible", "complete", "hidden"):
        for path in sorted((STAGE / "masks" / group).glob("*.png")):
            paths.append((path, f"{group} mask: {path.stem}"))
    paths.append(
        (
            STAGE / "masks/reference/source-registered-enclosed-finger-gap.png",
            "source-registered enclosed finger-gap responsibility",
        )
    )
    locked = [record(path, role) for path, role in paths]
    manifest = {
        "schemaVersion": 1,
        "checkpoint": "V13 screen-left arm material boundaries and hidden overlaps",
        "freezeDate": "2026-07-27",
        "decisionOwner": "user",
        "status": "frozen_v13_material_boundaries_user_approved",
        "scope": "four complete screen-left arm masks and semantic ownership; texture not yet approved",
        "upstreamFreeze": {
            "path": V12_MANIFEST.relative_to(WORKBENCH).as_posix(),
            "sha256": sha256(V12_MANIFEST),
            "matchedArtifacts": 7,
            "artifactCount": 7,
        },
        "lockedArtifacts": locked,
        "artifactCount": len(locked),
        "invalidationRules": [
            "Any byte change to a locked V13 artifact reopens material-boundary approval.",
            "Any alpha-boundary, ownership, hidden-overlap, draw-order, or finger-gap change reopens V13.",
            "Texture may fill only the frozen complete masks and must preserve visible source pixels 1:1.",
            "Mesh work requires separate visual approval of the completed textured materials.",
        ],
        "explicitlyNotApproved": [
            "completed textures",
            "PSD",
            "mesh",
            "nodes",
            "continuous parameter motion",
            "Physics",
            "Runtime",
        ],
        "nextGate": "complete texture fill and displaced-part visual review",
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
