"""Record the user-approved whole-hand flat-color visual freeze.

This marker deliberately does not promote or overwrite formal R2 PNGs.  It
captures the exact candidate/formal inputs and keeps the visual-freeze
decision separate from the still-open R2 engineering gate.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any


TOOL_PATH = Path(__file__).resolve()
R2_ROOT = TOOL_PATH.parents[1]
REPO_ROOT = TOOL_PATH.parents[6]
TODAY = date(2026, 8, 12).isoformat()
DATE_TAG = TODAY


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def file_record(relative_path: str, *, role: str) -> dict[str, Any]:
    path = REPO_ROOT / relative_path
    if not path.exists():
        raise FileNotFoundError(path)
    return {
        "path": relative_path,
        "role": role,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def load_json(relative_path: str) -> dict[str, Any]:
    path = REPO_ROOT / relative_path
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def failed_checks(report: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    checks = report.get("checks", {})
    items = checks.items() if isinstance(checks, dict) else enumerate(checks)
    for key, value in items:
        if isinstance(value, dict) and value.get("pass") is False:
            result.append(
                {
                    "id": str(key),
                    "detail": value.get("detail"),
                    "reason": value.get("reason"),
                }
            )
    return result


def main() -> None:
    candidate_root = R2_ROOT / "candidates" / "upper-arm-aa-anatomical-v8"
    candidate_report_path = repo_rel(candidate_root / "audit" / "upper-arm-aa-machine-report.json")
    candidate_contract_path = repo_rel(candidate_root / "audit" / "upper-arm-aa-anatomical-contract.json")
    preview_report_path = repo_rel(R2_ROOT / "previews" / "whole-hand-v8" / "preview-report.json")
    r2_report_path = repo_rel(R2_ROOT / "audit" / "machine-report.json")

    candidate_report = load_json(candidate_report_path)
    candidate_contract = load_json(candidate_contract_path)
    preview_report = load_json(preview_report_path)
    r2_report = load_json(r2_report_path)

    if candidate_report.get("engineeringPass") is not True:
        raise RuntimeError("upper-arm v8 candidate is not engineering-green")

    required_preview_checks = [
        "allFramesHaveVisiblePixels",
        "allFramesSingleConnectedArmChainAtAlphaGt8",
        "allElbowOverlapsPositive",
        "allWristOverlapsPositive",
        "hiddenWristRootIncludedInPreview",
    ]
    preview_checks = preview_report.get("checks", {})
    if not all(preview_checks.get(key) is True for key in required_preview_checks):
        raise RuntimeError("whole-hand preview checks are not all green")

    source_files = [
        file_record(
            "docs/live2d-workbench/xiaoxing/source/masters/front-line-source-exact-after-reset.png",
            role="authoritative semantic line source",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/source/masters/front-color-source-exact-after-reset.png",
            role="identity/color reference only",
        ),
    ]
    latest_markup_files = [
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/audit/user-markup-forearm-elbow-source-reference-2026-08-12.png",
            role="latest elbow/upper-arm boundary reference",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/audit/user-markup-forearm-hidden-connection-blue-2026-08-11.png",
            role="latest hidden wrist connection boundary reference",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/audit/user-markup-hand-redline-2026-08-09.png",
            role="hand red-line boundary reference",
        ),
    ]
    frozen_inputs = [
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/candidates/upper-arm-aa-anatomical-v8/flat-layers/upper_arm.png",
            role="frozen visual source: upper-arm flat color",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/candidates/upper-arm-aa-anatomical-v8/display-alpha/upper_arm.png",
            role="frozen visual source: upper-arm fractional display alpha",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/candidates/upper-arm-aa-anatomical-v8/masks/hidden-upper_arm.png",
            role="frozen visual source: upper-arm hidden logical mask",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/candidates/upper-arm-aa-anatomical-v8/masks/complete-upper_arm.png",
            role="frozen visual source: upper-arm complete logical mask",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/flat-layers/sleeve.png",
            role="protected formal R2 input: sleeve",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/flat-layers/forearm.png",
            role="protected formal R2 input: forearm",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/flat-layers/bracelet-back.png",
            role="protected formal R2 input: bracelet back",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/flat-layers/bracelet-front.png",
            role="protected formal R2 input: bracelet front",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/flat-layers/hand.png",
            role="protected formal R2 input: hand flat color",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/display-alpha/hand-hidden.png",
            role="protected formal R2 input: hidden wrist-root continuation",
        ),
    ]
    formal_upper_arm_inputs = [
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/flat-layers/upper_arm.png",
            role="current formal R2 upper-arm flat layer; unchanged",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/masks/hidden/upper_arm.png",
            role="current formal R2 upper-arm hidden mask; unchanged",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/masks/complete/upper_arm.png",
            role="current formal R2 upper-arm complete mask; unchanged",
        ),
    ]
    review_artifacts = [
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/candidates/upper-arm-aa-anatomical-v8/qa/upper-arm-aa-anatomical-review.png",
            role="source line, old/new geometry, formal alpha and gate board",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/candidates/upper-arm-aa-anatomical-v8/qa/upper-arm-source-line-fit-500pct.png",
            role="latest source-line fit review",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/candidates/upper-arm-aa-anatomical-v8/qa/upper-arm-occlusion-transition-500pct.png",
            role="elbow occlusion transition review",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/qa/手臂色块-实际线稿拟合-全臂-400pct.png",
            role="whole-arm line-fit review",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/previews/whole-hand-v8/whole-hand-v8-preview.gif",
            role="user-facing whole-hand preview",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/previews/whole-hand-v8/whole-hand-v8-contact-sheet.png",
            role="whole-hand preview contact sheet",
        ),
        file_record(
            "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/previews/whole-hand-v8/wrist-connection-contact-v2.png",
            role="wrist hidden-connection review",
        ),
    ]

    contract_path = REPO_ROOT / candidate_contract_path
    contract_sha = sha256(contract_path)
    boundary = candidate_contract.get("boundary")
    if not isinstance(boundary, dict):
        raise RuntimeError("candidate boundary contract is missing")

    r2_failures = r2_report.get("engineeringFailures", [])
    r2_diagnostics = r2_report.get("diagnosticOnlyFailures", [])
    approval = {
        "schemaVersion": 1,
        "recordType": "user_visual_approval",
        "approvalKind": "visual_freeze",
        "approvalDate": TODAY,
        "stage": "WHOLE_HAND_FLAT_COLOR_VISUAL_FREEZE",
        "character": "xiaoxing",
        "view": "front",
        "screenSide": "left",
        "anatomicalSide": "right",
        "decision": "approved",
        "status": "WHOLE_HAND_FLAT_COLOR_VISUAL_FREEZE / FORMAL_R2_PROMOTION_PENDING_ENGINEERING_REVALIDATION",
        "userVisualApproval": True,
        "userQuote": "行，那我们的色块就已经是ok了的吧，可以冻结了，然后标记一下吧",
        "approvalBasis": {
            "scope": "whole hand color blocks: upper-arm v8 + protected R2 sleeve/forearm/bracelet/hand inputs",
            "reviewArtifacts": [item["path"] for item in review_artifacts],
            "latestBoundaryEvidencePresent": True,
            "previewChecksPassed": True,
            "fingerGaps": "preserved as intentional negative space; no finger-gap fill authorized",
            "wristRoot": "hidden continuation is retained as the protected hand-hidden input and shown in the preview",
        },
        "authorizedScope": [
            "freeze the current whole-hand flat-color visual input by hash",
            "use upper-arm-aa-anatomical-v8 as the accepted upper-arm visual source",
            "retain current formal R2 sleeve/forearm/bracelet/hand inputs unchanged",
            "retain the latest boundary and anti-aliasing evidence as the review record",
        ],
        "notAuthorized": [
            "do not overwrite formal R2 PNGs in this marker step",
            "do not mark the reopened forearm engineering gate as passed",
            "no texture, PSD, mesh, ArtMesh, Deformer, node, parameter, action, Physics, Cubism, Runtime or R3/R4 work",
        ],
        "engineeringPassByScope": {
            "upperArmV8Candidate": candidate_report.get("engineeringPass"),
            "wholeHandPreview": True,
            "currentR2FormalScope": False,
            "overallGatePass": False,
        },
        "formalR2Promotion": False,
        "sourceAuthority": {
            "files": source_files,
            "coordinateTransform": "identity; all boundary points are front-master pixels",
            "canvas": [512, 1086],
            "candidateBoundaryContract": {
                "path": candidate_contract_path,
                "sha256": contract_sha,
                "classification": boundary.get("classification"),
                "allowedSide": boundary.get("allowedSide"),
                "bezierSegments": boundary.get("bezierSegments"),
                "outsideAlphaRule": boundary.get("outsideAlphaRule"),
            },
            "latestMarkupFiles": latest_markup_files,
        },
        "frozenInputs": frozen_inputs,
        "currentFormalUpperArmProtectedInputs": formal_upper_arm_inputs,
        "engineeringRevalidation": {
            "r2MachineReport": r2_report_path,
            "r2EngineeringPass": r2_report.get("engineeringPass"),
            "r2EngineeringFailures": r2_failures,
            "r2DiagnosticOnlyFailures": r2_diagnostics,
            "reasonFormalPromotionRemainsPending": "current formal R2 report still has forearm semantic holes and lift-frame connectivity diagnostics",
        },
    }

    manifest = {
        "schemaVersion": 1,
        "recordType": "frozen_visual_input_manifest",
        "manifestDate": TODAY,
        "freezeId": f"xiaoxing-front-screen-left-whole-hand-flat-color-{DATE_TAG}",
        "status": "FROZEN_VISUAL_INPUT / FORMAL_R2_PROMOTION_PENDING_ENGINEERING_REVALIDATION",
        "scope": {
            "character": "xiaoxing",
            "view": "front",
            "screenSide": "left",
            "anatomicalSide": "right",
            "material": "whole hand flat-color blocks",
            "assembly": "upper-arm v8 + sleeve + forearm + bracelet back/front + hand",
        },
        "userApprovalRecord": "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/audit/user-visual-approval-whole-hand-flat-color-freeze-2026-08-12.json",
        "candidateSource": {
            "path": "docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r2-flat-color-materials/candidates/upper-arm-aa-anatomical-v8",
            "engineeringPass": candidate_report.get("engineeringPass"),
            "machineReport": candidate_report_path,
            "contract": candidate_contract_path,
        },
        "frozenFiles": frozen_inputs,
        "reviewFiles": review_artifacts,
        "sourceAuthority": source_files,
        "latestMarkupFiles": latest_markup_files,
        "protectedFormalFilesUnchanged": formal_upper_arm_inputs,
        "previewReport": {
            "path": preview_report_path,
            "sha256": sha256(REPO_ROOT / preview_report_path),
            "checks": preview_checks,
            "formalPromotion": preview_report.get("formalGate", {}).get("formalR2Promotion"),
        },
        "gateSeparation": {
            "visualFreeze": True,
            "userVisualApproval": True,
            "upperArmCandidateEngineeringPass": True,
            "currentR2EngineeringPass": r2_report.get("engineeringPass"),
            "overallGatePass": False,
            "formalR2Promotion": False,
            "explanation": "visual approval freezes the reviewed color-block input; it does not erase existing formal R2 engineering failures",
        },
        "acceptedVisualDecisions": [
            "upper-arm v8 anatomical contour and anti-aliased display alpha are the frozen visual source",
            "bracelet/forearm/hand color blocks are the current protected R2 inputs",
            "wrist-root hidden continuation is included in the reviewed preview",
            "finger gaps remain intentional transparent negative spaces",
            "no extra boundary expansion or white-gap fill is part of this freeze",
        ],
        "knownLimitations": [
            "bracelet rear-half depth remains unresolved from the single front line drawing",
            "formal R2 promotion still requires engineering revalidation of forearm holes and lift-frame connectivity",
            "this freeze covers flat-color geometry/input only; it is not a Cubism/runtime/action freeze",
        ],
    }

    output_dir = R2_ROOT / "audit"
    approval_path = output_dir / f"user-visual-approval-whole-hand-flat-color-freeze-{DATE_TAG}.json"
    manifest_path = output_dir / f"whole-hand-flat-color-freeze-manifest-{DATE_TAG}.json"
    approval_path.write_text(json.dumps(approval, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"approval": repo_rel(approval_path), "manifest": repo_rel(manifest_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
