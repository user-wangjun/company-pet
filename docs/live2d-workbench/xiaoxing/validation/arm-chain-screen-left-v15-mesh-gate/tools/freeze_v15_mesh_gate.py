from __future__ import annotations

import hashlib
import json
from pathlib import Path


STAGE = Path(__file__).resolve().parents[1]
WORKBENCH = STAGE.parents[1]
AUDIT = STAGE / "audit"
APPROVAL = AUDIT / "v15-user-visual-approval-artmesh-2026-07-28.json"
MANIFEST = AUDIT / "v15-artmesh-freeze-manifest-2026-07-28.json"
V14_MANIFEST = (
    WORKBENCH
    / "validation/arm-chain-screen-left-v14-complete-textures/audit"
    / "v14-complete-texture-freeze-manifest-2026-07-28.json"
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


def verify_manifest(manifest_path: Path, root: Path) -> tuple[int, int]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    locked = manifest["lockedArtifacts"]
    matched = sum(
        sha256(root / artifact["path"]) == artifact["sha256"]
        and (root / artifact["path"]).stat().st_size == artifact["bytes"]
        for artifact in locked
    )
    return matched, len(locked)


def main() -> None:
    report_path = AUDIT / "v15-mesh-engineering-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report["status"] != "engineering_pass_pending_user_visual_approval":
        raise RuntimeError("V15 engineering state is not ready for visual approval.")
    if not report["engineeringPass"]:
        raise RuntimeError("V15 engineering checks did not pass.")
    v14_matched, v14_count = verify_manifest(V14_MANIFEST, V14_MANIFEST.parents[1])
    if (v14_matched, v14_count) != (24, 24):
        raise RuntimeError(f"V14 freeze mismatch: {v14_matched}/{v14_count}.")

    board = STAGE / "qa/V15-MESH-USER-REVIEW.zh-CN.png"
    approval = {
        "schemaVersion": 1,
        "checkpoint": "V15 screen-left arm four-layer ArtMesh",
        "decisionDate": "2026-07-28",
        "decisionOwner": "user",
        "decision": "approved",
        "decisionText": "合适，请继续任务",
        "approvedScope": [
            "one ArtMesh per approved V14 material",
            "triangles constrained to each complete alpha boundary",
            "source-registered enclosed hand gap remains unbridged",
            "UV coordinates remain on the unchanged 512x1086 canvas",
            "sparse joint-local and long-span topology shown in the V15 review board",
        ],
        "approvedEvidence": {
            "reviewBoard": {
                "path": board.relative_to(STAGE).as_posix(),
                "sha256": sha256(board),
            }
        },
        "authorization": {
            "actualNodes": True,
            "activeMotionBeforeNodeApproval": False,
            "physics": False,
            "runtime": False,
        },
    }
    write_json(APPROVAL, approval)

    paths: list[tuple[Path, str]] = [
        (APPROVAL, "user visual approval and actual-node authorization"),
        (report_path, "V15 ArtMesh engineering report"),
        (AUDIT / "V15-MESH-REPORT.zh-CN.md", "Chinese V15 report"),
        (board, "approved ArtMesh review board"),
        (STAGE / "contracts/v15-layer-mesh-node-contract.json", "approved mesh and node-candidate contract"),
        (STAGE / "tools/build_v15_mesh_gate.py", "deterministic V15 mesh builder"),
        (STAGE / "tools/freeze_v15_mesh_gate.py", "V15 freeze manifest builder"),
    ]
    for path in sorted((STAGE / "meshes").glob("*.json")):
        paths.append((path, f"approved ArtMesh topology: {path.stem}"))
    for path in sorted((STAGE / "qa").glob("wireframe-*.png")):
        paths.append((path, f"approved ArtMesh wireframe: {path.stem}"))

    locked = [record(path, role) for path, role in paths]
    manifest = {
        "schemaVersion": 1,
        "checkpoint": "V15 screen-left arm four-layer ArtMesh",
        "freezeDate": "2026-07-28",
        "decisionOwner": "user",
        "status": "frozen_v15_artmesh_user_approved",
        "scope": "four approved ArtMesh topologies and their exact V14 material mapping",
        "upstreamFreeze": {
            "path": V14_MANIFEST.relative_to(WORKBENCH).as_posix(),
            "sha256": sha256(V14_MANIFEST),
            "matchedArtifacts": v14_matched,
            "artifactCount": v14_count,
        },
        "lockedArtifacts": locked,
        "artifactCount": len(locked),
        "invalidationRules": [
            "Any byte change to a locked V15 artifact reopens ArtMesh approval.",
            "Any vertex, triangle, UV, alpha-boundary mapping, or hand-gap change reopens V15.",
            "Downstream node work must copy or reference V15; it must not edit V15 in place.",
            "Active motion requires separate node approval before parameter authoring.",
        ],
        "explicitlyNotApproved": [
            "actual node hierarchy",
            "continuous parameter motion",
            "Physics",
            "Runtime",
        ],
        "nextGate": "actual node hierarchy, pivots, ownership, and parent-only cascade proof",
    }
    write_json(MANIFEST, manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "artifactCount": manifest["artifactCount"],
                "upstreamV14": f"{v14_matched}/{v14_count}",
                "manifestSha256": sha256(MANIFEST),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
