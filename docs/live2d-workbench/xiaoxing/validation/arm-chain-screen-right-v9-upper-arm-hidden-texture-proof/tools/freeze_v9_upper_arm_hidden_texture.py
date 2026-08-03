from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_TOOL = ROOT / "tools/build_v9_upper_arm_hidden_texture.py"
REPORT_PATH = ROOT / "audit/v9-upper-arm-hidden-texture-engineering-report.json"
APPROVAL_PATH = ROOT / "audit/v9-candidate-b-user-visual-approval-2026-07-26.json"
MANIFEST_PATH = (
    ROOT / "audit/v9-upper-arm-hidden-texture-freeze-manifest-2026-07-26.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"STOP: {message}")


def load_builder():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("v9_builder", BUILD_TOOL)
    require(spec is not None and spec.loader is not None, "cannot load V9 builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def role_for(relative: str) -> str:
    exact = {
        "inputs/input-reference-manifest.json": "reference-only input manifest",
        "masks/R_shoulder_hidden.png": "locked approved paint permission mask",
        "masks/M_upper-frozen-reference.png": "frozen complete upper-arm geometry reference",
        "masks/V_upper-frozen-visible.png": "write-protected visible upper-arm mask",
        "masks/H_upper-not-in-scope.png": "explicit unapproved hidden upper-arm region",
        "masks/upper-arm-source-partition.png": "visible, approved-paint, and unapproved-hidden partition",
        "materials/upper-arm-shoulder-hidden-candidate-b.png": "selected and approved candidate B",
        "materials/upper-arm-shoulder-hidden-candidate-a.png": "non-selected comparison candidate A",
        "materials/upper-arm-shoulder-hidden-candidate-c.png": "screened-out comparison candidate C",
        "audit/v9-upper-arm-hidden-texture-engineering-report.json": "machine-readable engineering report",
        "audit/V9-UPPER-ARM-HIDDEN-TEXTURE-REPORT.zh-CN.md": "Chinese engineering report",
        "audit/v9-candidate-b-user-visual-approval-2026-07-26.json": "explicit user visual approval and freeze authorization",
        "tools/build_v9_upper_arm_hidden_texture.py": "deterministic V9 candidate and QA builder",
        "tools/freeze_v9_upper_arm_hidden_texture.py": "V9 freeze verifier and manifest generator",
    }
    if relative in exact:
        return exact[relative]
    if relative.startswith("qa/"):
        return "frozen visual QA evidence"
    return "frozen V9 evidence"


def main() -> None:
    require(REPORT_PATH.is_file(), "missing engineering report")
    require(APPROVAL_PATH.is_file(), "missing explicit user approval record")
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    approval = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))

    builder = load_builder()
    upstream = builder.frozen_integrity()
    require(upstream["status"] == "pass", "upstream frozen input mismatch")
    require(upstream["failed"] == 0, "upstream frozen input failure")

    require(
        report["status"] == "engineering_pass_pending_user_visual_review",
        "unexpected pre-approval engineering status",
    )
    require(report["frozenInputIntegrity"]["status"] == "pass", "report input audit failed")
    require(report["recommendedCandidate"] == "B", "candidate B is not recommended")
    require(report["regionDefinition"]["rShoulderHiddenPixels"] == 4465, "R_shoulder_hidden pixel count changed")
    require(report["regionDefinition"]["otherHiddenNotInScopePixels"] == 349, "out-of-scope hidden count changed")
    require(report["regionDefinition"]["elbowSidePixelsIncluded"] == 0, "elbow-side pixels entered V9")

    numeric = report["numericChecks"]
    zero_checks = [
        "vUpperCoordinateDifferencePixels",
        "vUpperRgbDifferencePixels",
        "vUpperAlphaDifferencePixels",
        "mUpperGeometryDifferencePixels",
        "paintedPixelsOutsideRShoulderHidden",
        "alphaPixelsOutsideFrozenMUpper",
        "defaultRecompositionLockedSourcePixelDifference",
        "sleeveOcclusionRelationDifferencePixels",
        "deterministicRegenerationDifferencePixels",
    ]
    for key in zero_checks:
        require(numeric[key] == 0, f"numeric gate failed: {key}")
    require(report["motion"]["sampleCount"] == 41, "41-sample motion evidence missing")
    require(report["motion"]["firstLastPixelDifference"] == 0, "motion return difference is nonzero")

    require(approval["decision"] == "approved", "user approval is not affirmative")
    require(approval["decisionText"] == "批准候选B", "unexpected approval text")
    require(approval["approvedCandidate"]["id"] == "B", "approval is not for candidate B")
    require(approval["freezeAuthorization"] is True, "freeze authorization missing")
    selected_path = ROOT / approval["approvedCandidate"]["path"]
    require(selected_path.is_file(), "approved candidate B file missing")
    require(
        sha256(selected_path) == approval["approvedCandidate"]["sha256"],
        "approved candidate B hash mismatch",
    )
    for evidence in approval["reviewedEvidence"]:
        evidence_path = ROOT / evidence["path"]
        require(evidence_path.is_file(), f"missing reviewed evidence: {evidence['path']}")
        require(
            sha256(evidence_path) == evidence["sha256"],
            f"reviewed evidence hash mismatch: {evidence['path']}",
        )
    require(
        sha256(REPORT_PATH) == approval["engineeringEvidence"]["sha256"],
        "approved engineering report hash mismatch",
    )

    artifacts = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path == MANIFEST_PATH:
            continue
        relative = path.relative_to(ROOT).as_posix()
        artifacts.append(
            {
                "role": role_for(relative),
                "path": relative,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
        )

    manifest = {
        "schemaVersion": 1,
        "checkpoint": "V9 shoulder-side hidden upper-arm texture candidate B",
        "freezeDate": "2026-07-26",
        "decisionOwner": "user",
        "status": "frozen_engineering_and_user_visual_pass",
        "scope": "4465 px R_shoulder_hidden shoulder-side hidden upper-arm texture proof only",
        "approvedCandidate": {
            "id": "B",
            "path": approval["approvedCandidate"]["path"],
            "sha256": approval["approvedCandidate"]["sha256"],
        },
        "userApproval": {
            "path": APPROVAL_PATH.relative_to(ROOT).as_posix(),
            "sha256": sha256(APPROVAL_PATH),
            "decisionText": approval["decisionText"],
        },
        "frozenInputIntegrity": upstream,
        "finalMetrics": {
            "mUpperPixels": report["regionDefinition"]["mUpperPixels"],
            "vUpperPixels": report["regionDefinition"]["vUpperPixels"],
            "rShoulderHiddenPixels": report["regionDefinition"]["rShoulderHiddenPixels"],
            "otherHiddenNotInScopePixels": report["regionDefinition"]["otherHiddenNotInScopePixels"],
            "elbowSidePixelsIncluded": report["regionDefinition"]["elbowSidePixelsIncluded"],
            **{key: numeric[key] for key in zero_checks},
            "motionSampleCount": report["motion"]["sampleCount"],
            "motionFirstLastPixelDifference": report["motion"]["firstLastPixelDifference"],
            "fullOutputDeterministicDifferenceFiles": 0,
        },
        "lockedArtifacts": artifacts,
        "artifactCount": len(artifacts),
        "invalidationRules": [
            "Any byte change to candidate B, R_shoulder_hidden, the approval record, engineering report, builder, freeze verifier, or frozen QA evidence reopens V9.",
            "Any change to frozen M_upper geometry or any V_upper coordinate, RGB, or alpha value invalidates V9.",
            "Expanding paint beyond R_shoulder_hidden or into the 349 px out-of-scope hidden region invalidates V9.",
            "Changing the frozen sleeve occlusion relation or the approved V4 motion range reopens the relevant upstream gate.",
            "A future torso or hair separation still reopens the V6 18-pixel conditional shoulder coverage check.",
        ],
        "explicitlyNotApproved": approval["explicitlyNotApproved"],
        "nextGate": "separately authorized discussion of a minimal Cubism rough-rig scope",
        "sequencingRule": "Do not create PSD, ArtMesh, Cubism, Physics, or Runtime artifacts without new explicit user authorization.",
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "artifactCount": manifest["artifactCount"],
                "manifestSha256": sha256(MANIFEST_PATH),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
