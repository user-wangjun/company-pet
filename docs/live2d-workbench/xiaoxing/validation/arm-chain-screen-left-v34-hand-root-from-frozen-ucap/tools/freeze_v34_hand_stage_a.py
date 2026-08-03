from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
BUILD_TOOL = ROOT / "tools/build_v34_hand_root.py"
APPROVAL = (
    ROOT / "audit/user-visual-approval-and-freeze-authorization-2026-07-29.json"
)
FREEZE_MANIFEST = (
    ROOT / "audit/v34-hand-stage-a-freeze-manifest-2026-07-29.json"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def verify_artifact_manifest() -> dict:
    manifest_path = ROOT / "audit/artifact-manifest.json"
    manifest = read_json(manifest_path)
    checks = []
    for item in manifest["artifacts"]:
        path = ROOT / item["path"]
        actual = sha256(path) if path.exists() else None
        checks.append(
            {
                "path": item["path"],
                "expectedSha256": item["sha256"],
                "actualSha256": actual,
                "match": actual == item["sha256"],
            }
        )
    return {
        "path": "audit/artifact-manifest.json",
        "sha256": sha256(manifest_path),
        "checks": checks,
        "pass": all(item["match"] for item in checks),
    }


def load_builder():
    spec = importlib.util.spec_from_file_location("v34_builder", BUILD_TOOL)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def artifact(path: str) -> dict:
    return {"path": path, "sha256": sha256(ROOT / path)}


def main() -> None:
    pre_report = read_json(ROOT / "audit/machine-report.json")
    pre_manifest = verify_artifact_manifest()
    assert pre_manifest["pass"]
    assert pre_report["status"] in {
        "engineering_pass_slim_ucap_pending_user_visual_approval",
        "frozen_engineering_and_user_visual_pass",
    }
    assert pre_report["earliestFailurePoint"] in {
        "none_in_machine_checks_pending_user_visual_review",
        "none",
    }
    assert pre_report["frozenUpstreamHashCheck"]["pass"] is True
    assert all(pre_report["machineChecks"].values())

    approved_artifacts = [
        "masks/visible/hand.png",
        "masks/hidden/hand.png",
        "masks/complete/hand.png",
        "materials/hand.png",
        "masks/reference/slim-blue-forearm-ucap.png",
        "masks/complete/forearm-slim.png",
        "materials/forearm-slim.png",
        "qa/V34-前臂凸包削瘦复核图.png",
        "qa/V34-阶段A-screen-left手部-最终中文视觉审查板.png",
    ]
    save_json(
        APPROVAL,
        {
            "schemaVersion": 1,
            "status": "user_visual_approved_and_freeze_authorized",
            "decisionOwner": "user",
            "decisionDate": "2026-07-29",
            "userDecision": "可以，暂时先冻结，就这样",
            "approvedScope": {
                "side": "screen-left",
                "stage": "hand Stage A flat geometry",
                "parts": [
                    "approved visible hand contour",
                    "continuous hidden hand wrist root",
                    "complete hand material",
                    "user-authorized slim hidden forearm U-cap candidate",
                ],
                "drawOrderBackToFront": [
                    "hand",
                    "slim forearm candidate",
                    "forearm-owned bracelet",
                ],
            },
            "approvedArtifacts": [
                artifact(path) for path in approved_artifacts
            ],
            "engineeringEvidenceAtApproval": {
                "minimumOverlapAcross41SamplesPx": (
                    pre_report["motion"]["minimumCompleteOverlapPx"]
                ),
                "requiredMinimumOverlapPx": 510,
                "disconnectCountAcross41Samples": (
                    pre_report["motion"]["disconnectCount"]
                ),
                "returnConsistency": (
                    pre_report["motion"]["returnConsistency"]
                ),
                "stressDisconnectCount": sum(
                    item["disconnected"]
                    for item in pre_report["wristStress"]["results"]
                ),
                "visibleBraceletPixelDuplicationPx": (
                    pre_report["geometry"][
                        "visibleBraceletPixelDuplicationPx"
                    ]
                ),
                "forbiddenRegionIntrusionPx": (
                    pre_report["forbiddenRegionIntrusion"]["totalPixels"]
                ),
            },
            "ownershipClarification": {
                "forearmUCapIsForeground": True,
                "foregroundOnlyPixelsAreNotTransparentGaps": True,
                "maximumForegroundOnlyPxAcross41Samples": (
                    pre_report["motion"][
                        "maximumFrozenUCapNotCoveredByHandPx"
                    ]
                ),
                "maximumForegroundOnlyPxAcrossStressSweep": (
                    pre_report["wristStress"][
                        "maximumFrozenUCapNotCoveredByHandPx"
                    ]
                ),
            },
            "temporaryMeaning": (
                "this is the current immutable checkpoint; a later change "
                "requires explicit user authorization to reopen the frozen scope"
            ),
            "doesNotAuthorize": [
                "texture or PSD work",
                "Cubism mesh, deformers, Physics, or runtime work",
                "screen-right changes",
                "whole-body advancement",
            ],
        },
    )

    builder = load_builder()
    builder.main()

    report = read_json(ROOT / "audit/machine-report.json")
    artifact_manifest = verify_artifact_manifest()
    assert report["status"] == "frozen_engineering_and_user_visual_pass"
    assert report["visualGate"]["handFrozen"] is True
    assert report["visualGate"]["slimForearmUCapFrozen"] is True
    assert report["frozenUpstreamHashCheck"]["pass"] is True
    assert all(report["machineChecks"].values())
    assert artifact_manifest["pass"]

    locked_geometry = [
        "skeleton-lock.json",
        "hand-layering-contract.json",
        "masks/visible/hand.png",
        "masks/hidden/hand.png",
        "masks/complete/hand.png",
        "materials/hand-visible-flat.png",
        "materials/hand-hidden-flat.png",
        "materials/hand.png",
        "masks/reference/slim-blue-forearm-ucap.png",
        "masks/complete/forearm-slim.png",
        "materials/forearm-slim.png",
    ]
    locked_evidence = [
        "qa/default-solid-recomposition.png",
        "qa/default-overlay-reset.png",
        "qa/forearm-displaced-hand-root.png",
        "qa/hand-local-zooms.png",
        "qa/bracelet-exclusion-ownership.png",
        "qa/forearm-ucap-hand-coverage.png",
        "qa/fk-41-slow-preview.gif",
        "qa/fk-key-wrist-samples.png",
        "qa/wrist-stress-review.png",
        "qa/V34-前臂凸包削瘦复核图.png",
        "qa/V34-阶段A-screen-left手部-最终中文视觉审查板.png",
        "samples/fk-41-samples.json",
        "audit/machine-report.json",
        "audit/self-visual-qa-slim-ucap-2026-07-29.json",
        "audit/artifact-manifest.json",
        "audit/user-visual-approval-and-freeze-authorization-2026-07-29.json",
        "tools/build_v34_hand_root.py",
        "tools/freeze_v34_hand_stage_a.py",
    ]
    save_json(
        FREEZE_MANIFEST,
        {
            "schemaVersion": 1,
            "checkpoint": "v34_screen_left_hand_stage_a_geometry_frozen",
            "freezeDate": "2026-07-29",
            "decisionOwner": "user",
            "status": "frozen_engineering_and_user_visual_pass",
            "scope": (
                "screen-left hand Stage A flat geometry and the approved "
                "slim hidden forearm U-cap checkpoint"
            ),
            "checksumAlgorithm": "SHA-256",
            "userApproval": artifact(
                "audit/user-visual-approval-and-freeze-authorization-2026-07-29.json"
            ),
            "frozenUpstreamHashCheck": report["frozenUpstreamHashCheck"],
            "engineeringSummary": {
                "maxL1ErrorPx": report["boneLengthError"]["maxL1ErrorPx"],
                "maxL2ErrorPx": report["boneLengthError"]["maxL2ErrorPx"],
                "minimumOverlapAcross41SamplesPx": (
                    report["motion"]["minimumCompleteOverlapPx"]
                ),
                "disconnectCountAcross41Samples": (
                    report["motion"]["disconnectCount"]
                ),
                "returnConsistency": report["motion"]["returnConsistency"],
                "handComponents": report["geometry"]["handComponents"],
                "handClosedHoles": report["geometry"]["handClosedHoles"],
                "visibleBraceletPixelDuplicationPx": (
                    report["geometry"]["visibleBraceletPixelDuplicationPx"]
                ),
                "forbiddenRegionIntrusionPx": (
                    report["forbiddenRegionIntrusion"]["totalPixels"]
                ),
            },
            "lockedGeometry": [
                artifact(path) for path in locked_geometry
            ],
            "lockedEvidence": [
                artifact(path) for path in locked_evidence
            ],
            "invalidationRule": (
                "any byte change to a locked artifact reopens the screen-left "
                "hand Stage A visual and engineering gate"
            ),
            "nextGate": (
                "none authorized; remain at the frozen Stage A checkpoint"
            ),
        },
    )

    final_manifest = read_json(FREEZE_MANIFEST)
    for item in [
        *final_manifest["lockedGeometry"],
        *final_manifest["lockedEvidence"],
        final_manifest["userApproval"],
    ]:
        assert sha256(ROOT / item["path"]) == item["sha256"]


if __name__ == "__main__":
    main()
