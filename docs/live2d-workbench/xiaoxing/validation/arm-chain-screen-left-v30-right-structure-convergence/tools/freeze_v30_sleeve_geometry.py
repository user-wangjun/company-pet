from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
APPROVAL = ROOT / "audit/user-visual-approval-sleeve-2026-07-28.json"
REPORT = ROOT / "audit/machine-report.json"
MANIFEST = ROOT / "audit/v30-sleeve-geometry-freeze-manifest-2026-07-28.json"

ARTIFACTS = [
    "skeleton-lock.json",
    "sleeve-geometry-contract.json",
    "masks/sleeve-complete-fresh.png",
    "masks/sleeve-visible-owned.png",
    "masks/sleeve-hidden-fresh.png",
    "masks/visible-hidden-partition-union.png",
    "masks/right-complete-aligned-reference.png",
    "materials/sleeve.png",
    "samples/fk-41-samples.json",
    "qa/V30-RIGHT-STRUCTURE-CONVERGENCE-USER-REVIEW.zh-CN.png",
    "qa/fk-selected-contact-sheet.png",
    "qa/fk-41-slow-preview.gif",
    "audit/machine-report.json",
    "audit/user-visual-approval-sleeve-2026-07-28.json",
    "tools/build_v30_right_structure_convergence.py",
    "tools/freeze_v30_sleeve_geometry.py",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def binary_mask(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("L")) > 0


def main() -> None:
    approval = load_json(APPROVAL)
    report = load_json(REPORT)
    contract = load_json(ROOT / "sleeve-geometry-contract.json")

    assert approval["status"] == "user_visual_approved"
    assert approval["approvalEvidence"]["userStatement"] == "可以冻结袖子了"
    assert contract["status"] == "frozen_user_visual_approved"
    assert report["status"] == "engineering_pass_pending_user_visual_approval"
    assert report["skeletonUnchanged"] is True
    assert report["geometry"]["visibleHiddenPartitionDifferencePixels"] == 0
    assert report["geometry"]["shoulderProtrusionPixelsAboveSource"] == 0
    assert report["geometry"]["components"] == 1
    assert report["geometry"]["holes"] == 0
    assert report["motion"]["samples"] == 41
    assert report["motion"]["allFramesPass"] is True
    assert report["motion"]["returnConsistency"] is True

    complete = binary_mask(ROOT / "masks/sleeve-complete-fresh.png")
    visible = binary_mask(ROOT / "masks/sleeve-visible-owned.png")
    hidden = binary_mask(ROOT / "masks/sleeve-hidden-fresh.png")
    partition_union = binary_mask(
        ROOT / "masks/visible-hidden-partition-union.png"
    )
    assert not np.any(visible & hidden)
    assert np.array_equal(complete, visible | hidden)
    assert np.array_equal(complete, partition_union)

    missing = [path for path in ARTIFACTS if not (ROOT / path).is_file()]
    assert not missing, f"missing freeze artifacts: {missing}"

    manifest = {
        "schemaVersion": 1,
        "status": "frozen_engineering_and_user_visual_pass",
        "freezeDate": "2026-07-28",
        "decisionOwner": "user",
        "scope": "screen-left sleeve Stage A complete geometry and visible/hidden ownership only",
        "approval": "audit/user-visual-approval-sleeve-2026-07-28.json",
        "skeletonUnchanged": True,
        "engineeringChecks": {
            "visibleHiddenExactPartition": True,
            "shoulderProtrusionPixelsAboveSource": 0,
            "connectedComponents": 1,
            "holes": 0,
            "fkSamples": 41,
            "allFramesPass": True,
            "returnConsistency": True,
        },
        "artifacts": [
            {"path": path, "sha256": sha256(ROOT / path)}
            for path in ARTIFACTS
        ],
        "invalidationRules": [
            "any hash mismatch invalidates this sleeve freeze",
            "changing the complete sleeve mask requires new user visual approval",
            "changing visible or hidden ownership requires new user visual approval",
            "changing the approved shoulder, elbow, or wrist skeleton invalidates this freeze"
        ],
        "explicitlyNotApproved": approval["explicitlyNotApproved"],
        "nextGate": "remain at Stage A; review upper arm, forearm, hand, and whole-arm default regroup separately"
    }
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": manifest["status"],
        "artifactCount": len(manifest["artifacts"]),
        "manifest": MANIFEST.relative_to(ROOT).as_posix(),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
