from __future__ import annotations

import hashlib
import json
from pathlib import Path


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
AUDIT = STAGE / "audit"
APPROVAL = AUDIT / "v14-user-visual-approval-complete-textures-2026-07-28.json"
MANIFEST = AUDIT / "v14-complete-texture-freeze-manifest-2026-07-28.json"
V13_MANIFEST = (
    WORKBENCH
    / "validation/arm-chain-screen-left-v13-material-separation/audit"
    / "v13-material-boundary-freeze-manifest-2026-07-27.json"
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
    report_path = AUDIT / "v14-complete-texture-engineering-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report["status"] != "user_visual_approved_ready_to_freeze":
        raise RuntimeError("V14 is not approved and ready to freeze.")
    if not report["engineeringPass"]:
        raise RuntimeError("V14 engineering checks did not pass.")
    if report["inputIntegrity"]["v13Freeze"]["matchedArtifacts"] != 20:
        raise RuntimeError("V13 freeze no longer matches 20/20.")

    board = STAGE / "qa/V14-COMPLETE-TEXTURE-USER-REVIEW.zh-CN.png"
    slow = STAGE / "qa/V14-TEXTURE-SEAM-SLOW-SCAN.gif"
    approval = {
        "schemaVersion": 1,
        "checkpoint": "V14 screen-left arm corrected ownership and complete textures",
        "decisionDate": "2026-07-28",
        "decisionOwner": "user",
        "decision": "approved",
        "decisionText": "合适，请继续任务",
        "approvedScope": [
            "448 cuff-edge pixels reassigned from upper arm to sleeve without modifying frozen V13",
            "complete sleeve texture",
            "complete upper-arm texture",
            "complete forearm texture including bracelet ownership",
            "complete whole-hand texture including the source-registered enclosed finger gap",
            "41-sample seam scan and deterministic return",
        ],
        "approvedEvidence": {
            "reviewBoard": {
                "path": board.relative_to(STAGE).as_posix(),
                "sha256": sha256(board),
            },
            "slowScan": {
                "path": slow.relative_to(STAGE).as_posix(),
                "sha256": sha256(slow),
            },
        },
        "authorization": {
            "artMesh": True,
            "nodesBeforeMeshVisualApproval": False,
            "activeMotionBeforeNodeApproval": False,
            "physics": False,
            "runtime": False,
        },
    }
    write_json(APPROVAL, approval)

    paths: list[tuple[Path, str]] = [
        (APPROVAL, "user visual approval and ArtMesh authorization"),
        (report_path, "V14 complete texture engineering report"),
        (AUDIT / "V14-COMPLETE-TEXTURE-REPORT.zh-CN.md", "Chinese V14 report"),
        (board, "approved complete texture review board"),
        (slow, "approved 41-sample texture seam slow scan"),
        (STAGE / "tools/build_v14_complete_textures.py", "deterministic V14 builder"),
        (STAGE / "tools/freeze_v14_complete_textures.py", "V14 freeze manifest builder"),
    ]
    for path in sorted((STAGE / "materials").glob("*.png")):
        paths.append((path, f"approved complete material: {path.stem}"))
    for group in ("visible", "complete", "hidden"):
        for path in sorted((STAGE / "corrected-masks" / group).glob("*.png")):
            paths.append((path, f"corrected {group} mask: {path.stem}"))
    paths.append(
        (
            STAGE / "corrected-masks/cuff-shadow-band-reassigned-to-sleeve.png",
            "approved cuff-shadow ownership correction",
        )
    )
    locked = [record(path, role) for path, role in paths]
    manifest = {
        "schemaVersion": 1,
        "checkpoint": "V14 screen-left arm corrected ownership and complete textures",
        "freezeDate": "2026-07-28",
        "decisionOwner": "user",
        "status": "frozen_v14_complete_textures_user_approved",
        "scope": "four complete textured screen-left arm layers and corrected cuff ownership",
        "upstreamFreeze": {
            "path": V13_MANIFEST.relative_to(WORKBENCH).as_posix(),
            "sha256": sha256(V13_MANIFEST),
            "matchedArtifacts": 20,
            "artifactCount": 20,
        },
        "lockedArtifacts": locked,
        "artifactCount": len(locked),
        "invalidationRules": [
            "Any byte change to a locked V14 artifact reopens texture approval.",
            "Any alpha, visible RGB, hidden texture, cuff ownership, bracelet ownership, or finger-gap change reopens V14.",
            "Every ArtMesh must use exactly one approved V14 material and stay inside its frozen complete alpha boundary.",
            "Nodes and active motion require their own downstream evidence and user visual approval.",
        ],
        "explicitlyNotApproved": [
            "completed ArtMesh",
            "nodes",
            "continuous parameter motion",
            "Physics",
            "Runtime",
        ],
        "nextGate": "four-layer ArtMesh topology and wireframe visual review",
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
