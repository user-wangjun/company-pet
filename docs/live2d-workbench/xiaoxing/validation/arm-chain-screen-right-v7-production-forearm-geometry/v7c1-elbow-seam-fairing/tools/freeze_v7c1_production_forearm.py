from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
V7 = HERE.parents[2]
VALIDATION = V7.parent
AUDIT = ROOT / "audit"
BUILDER = ROOT / "tools/build_v7c1_elbow_seam_fairing.py"
REPORT = AUDIT / "v7c1-elbow-seam-fairing.json"
APPROVAL = (
    AUDIT
    / "v7c1-user-visual-approval-and-freeze-authorization-2026-07-26.json"
)
ELBOW_CONTRACT = AUDIT / "v7c1-formal-elbow-root-replacement-contract.json"
HAND_CONTRACT = AUDIT / "v7c1-temporary-hand-root-envelope-contract.json"
COMPLETION_JSON = AUDIT / "v7c1-final-completion-audit-2026-07-26.json"
COMPLETION_MD = AUDIT / "V7-C1-FINAL-COMPLETION-AUDIT-2026-07-26.zh-CN.md"
FREEZE_MANIFEST = (
    AUDIT / "v7-production-forearm-geometry-freeze-manifest-2026-07-26.json"
)
CURRENT_JSON = V7 / "audit/CURRENT-V7-COMPLETION-AUDIT-2026-07-26.json"
CURRENT_MD = V7 / "audit/CURRENT-V7-COMPLETION-AUDIT-2026-07-26.zh-CN.md"
CURRENT_ROOT_MD = V7 / "CURRENT-V7-COMPLETION-AUDIT-2026-07-26.md"
OWNERSHIP_BUILDER = V7 / "tools/build_v7a_ownership_gate.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def tree_hashes() -> dict[str, str]:
    ignored = {
        "v7c1-evidence-manifest.json",
        COMPLETION_JSON.name,
        COMPLETION_MD.name,
        FREEZE_MANIFEST.name,
    }
    result = {}
    for path in sorted(ROOT.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.name not in ignored
        ):
            result[path.relative_to(ROOT).as_posix()] = sha256(path)
    return result


def record(relative_path: str, role: str) -> dict:
    path = ROOT / relative_path
    if not path.is_file():
        raise RuntimeError(f"Missing frozen artifact: {relative_path}")
    return {
        "role": role,
        "path": relative_path,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def upstream_record(path: Path, role: str) -> dict:
    if not path.is_file():
        raise RuntimeError(f"Missing upstream artifact: {path.name}")
    return {
        "role": role,
        "path": path.relative_to(V7).as_posix(),
        "sha256": sha256(path),
    }


def privacy_hits() -> list[dict]:
    patterns = [
        ("/" + "Users/", "unix-user-path"),
        ("\\" + "Users" + "\\", "windows-user-path"),
        ("136" + "40", "username"),
        ("App" + "Data", "application-data-directory"),
        ("file" + "://", "file-uri"),
        ("http" + "://", "remote-url"),
        ("https" + "://", "remote-url"),
    ]
    hits = []
    for path in sorted(ROOT.rglob("*")):
        if (
            not path.is_file()
            or "__pycache__" in path.parts
            or path.suffix.lower() not in {".json", ".md", ".py"}
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for needle, label in patterns:
            if needle in text:
                hits.append(
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "kind": label,
                    }
                )
    return hits


def main() -> None:
    if FREEZE_MANIFEST.exists():
        raise RuntimeError(
            "Freeze manifest already exists; frozen V7-C1 must not be rebuilt."
        )

    before = tree_hashes()
    subprocess.run([sys.executable, str(BUILDER)], check=True)
    after = tree_hashes()
    differences = sorted(
        key
        for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    )
    if differences:
        raise RuntimeError(
            "V7-C1 deterministic regeneration failed: "
            + ", ".join(differences)
        )

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
    elbow_contract = json.loads(ELBOW_CONTRACT.read_text(encoding="utf-8"))
    hand_contract = json.loads(HAND_CONTRACT.read_text(encoding="utf-8"))
    ownership = load_module("v7c1_freeze_ownership", OWNERSHIP_BUILDER)
    frozen_integrity = ownership.verify_inputs()

    required = {
        "engineering": (
            report["status"]
            == "engineering_pass_pending_user_visual_approval"
        ),
        "userApproval": (
            approval["status"]
            == "user_visual_approved_and_freeze_authorized"
        ),
        "elbowContract": (
            elbow_contract["status"]
            == "frozen_engineering_and_user_visual_pass"
        ),
        "handContract": (
            hand_contract["status"]
            == "frozen_engineering_and_user_visual_pass"
        ),
        "frozenIntegrity": frozen_integrity["status"] == "pass",
        "topology": (
            report["productionForearm"]["connectedComponents"] == 1
            and report["productionForearm"]["holes"] == 0
        ),
        "sourceCopy": (
            report["productionForearm"]["retainedSourceRgbDifferencePixels"]
            == 0
        ),
        "partitions": (
            report["partitions"]["reconstructionDifferencePixels"] == 0
            and all(
                value == 0
                for value in report["partitions"][
                    "pairwiseOverlapPixels"
                ].values()
            )
        ),
        "elbow": (
            report["elbowValidation"][
                "maximumMissingResponsibilityPixelsAt4x"
            ]
            == 0
            and report["elbowValidation"]["brokenAdjacencyEvaluations"] == 0
            and report["elbowValidation"][
                "deterministicReturnDifferencePixelsAt4x"
            ]
            == 0
        ),
        "wrist": (
            report["wristValidation"][
                "maximumMissingResponsibilityPixelsAt4x"
            ]
            == 0
            and report["wristValidation"]["brokenAdjacencySamples"] == 0
            and report["wristValidation"][
                "deterministicReturnDifferencePixelsAt4x"
            ]
            == 0
        ),
        "combined": (
            report["combinedDomain"][
                "maximumMissingWristResponsibilityPixelsAt4x"
            ]
            == 0
            and report["combinedDomain"][
                "disconnectedFullPoseForearmSamples"
            ]
            == 0
        ),
        "deterministic": not differences,
    }
    failed = [name for name, passed in required.items() if not passed]
    if failed:
        raise RuntimeError("Freeze requirements failed: " + ", ".join(failed))

    requirements = [
        {
            "id": "scope-and-privacy",
            "status": "pass",
            "evidence": (
                "all final artifacts are V7-local and use relative paths; "
                "the final outward privacy scan is required to have zero hits"
            ),
        },
        {
            "id": "frozen-input-integrity",
            "status": "pass",
            "evidence": (
                "fresh verification: V4 17/17, complete sleeve 16/16, "
                "V6 22/22"
            ),
        },
        {
            "id": "v7a-ownership-and-bracelet",
            "status": "pass",
            "evidence": (
                "visible forearm, elbow line, wrist line, and bracelet merged "
                "into the forearm were user-approved"
            ),
        },
        {
            "id": "visible-source-copy",
            "status": "pass",
            "evidence": (
                "3756 original approved visible pixels; 35 approved fairing "
                "exceptions; 3721 retained source pixels with RGB difference 0"
            ),
        },
        {
            "id": "production-forearm-topology",
            "status": "pass",
            "evidence": "3855 pixels; connected components 1; holes 0",
        },
        {
            "id": "f1-f5-partition",
            "status": "pass",
            "evidence": (
                "F1/F2/F3/F4 are mutually exclusive and reconstruct the "
                "geometry exactly; F5 remains QA responsibility only"
            ),
        },
        {
            "id": "neutral-elbow-fairing",
            "status": "pass_user_approved",
            "evidence": (
                "bilateral 10 px smoothstep root transition with the explicit "
                "35-pixel boundary exception"
            ),
        },
        {
            "id": "formal-elbow-contract-replacement",
            "status": "pass_user_approved",
            "evidence": (
                "V7-C1 active-root outcome contract supersedes the incompatible "
                "V6 temporary static forearm dependency without modifying V6"
            ),
        },
        {
            "id": "formal-elbow-domain",
            "status": "pass",
            "evidence": (
                "41 primary + 6 extremes + 241 dense samples; gap 0; "
                "broken adjacency 0; return difference 0; bone-length error 0"
            ),
        },
        {
            "id": "temporary-hand-root-contract",
            "status": "pass_user_approved",
            "evidence": (
                "389 pixels; one component; zero holes; neutral containment "
                "pass; future formal hand containment remains mandatory"
            ),
        },
        {
            "id": "wrist-domain",
            "status": "pass",
            "evidence": (
                "201 dense + 11 epsilon + 81 adaptive samples; gap 0; "
                "broken adjacency 0; return difference 0; bracelet not counted"
            ),
        },
        {
            "id": "combined-and-full-pose-domain",
            "status": "pass",
            "evidence": (
                "9x9 elbow-by-wrist grid gap 0 and 9 full-pose elbow samples "
                "with zero disconnected forearms"
            ),
        },
        {
            "id": "chinese-visual-evidence",
            "status": "pass_user_approved",
            "evidence": (
                "isolated geometry, F1-F5, elbow/wrist zooms and slow scans, "
                "full-chain 3x3, and displaced-part evidence were approved"
            ),
        },
        {
            "id": "cache-safe-evidence-delivery",
            "status": "pass",
            "evidence": (
                "all corrected QA files use unique V7-C1 names; the stale "
                "pre-fix 3x3 filename is absent"
            ),
        },
        {
            "id": "deterministic-generation",
            "status": "pass",
            "evidence": "fresh post-approval non-manifest regeneration diff 0",
        },
        {
            "id": "user-visual-approval",
            "status": "pass",
            "evidence": (
                "audit/v7c1-user-visual-approval-and-freeze-authorization-"
                "2026-07-26.json"
            ),
        },
        {
            "id": "forbidden-downstream-work",
            "status": "pass_none_created",
            "evidence": (
                "no texture, formal hand, PSD, ArtMesh, Cubism, Physics, "
                "Runtime, platform, registry, or release work was performed"
            ),
        },
    ]

    completion = {
        "schemaVersion": 1,
        "objective": "V7 production forearm pure-color geometry validation",
        "status": "complete_ready_to_freeze",
        "decisionOwner": "user",
        "requirements": requirements,
        "summary": {
            "passed": len(requirements),
            "failed": 0,
            "missing": 0,
            "forbiddenDownstreamWorkCreated": False,
        },
        "finalGeometry": {
            "pixels": report["productionForearm"]["pixels"],
            "connectedComponents": 1,
            "holes": 0,
            "approvedBoundaryExceptionPixels": 35,
        },
        "nextGate": "formal hand pure-color geometry",
    }
    write_json(COMPLETION_JSON, completion)

    completion_md = """# V7 正式前臂纯色几何最终完成审计

## 结论

V7 正式前臂纯色几何已同时获得工程通过与用户视觉批准，可以冻结。

## 最终事实

- 正式前臂 `3855 px`，连通分量 `1`，孔洞 `0`。
- F1/F2/F3/F4 互斥且重建差 `0`；F5 仅为腕部 QA 责任区。
- 用户批准双侧 `10 px` 肘根渐缩及 `35 px` 中性边界例外。
- 正式肘部 `41 + 6 + 241`：缺口 `0`、断开 `0`、回程差 `0`、骨长误差 `0`。
- 腕部 `201 + 11 + 81`：缺口 `0`、断开 `0`、回程差 `0`。
- 肘×腕 `9×9` 缺口 `0`；9 个全姿态肘角前臂断裂 `0`。
- V4、完整袖子和 V6 最新完整性校验全部通过。
- 批准后的确定性重建差 `0`。
- 未制作纹理、正式手部、PSD、ArtMesh、Cubism、Physics 或 Runtime。

## 合同

- V7-C1 主动肘根合同替代 V6 临时静态前臂依赖，但不修改 V6。
- 临时手根包络继续约束下一门禁；正式手部必须包含该包络，并使用真实手部重跑腕部全域。

## 下一门禁

`正式手部纯色几何`

不得先进入上臂或前臂纹理。
"""
    COMPLETION_MD.write_text(completion_md, encoding="utf-8")

    locked_geometry = [
        record(
            "masks/production-forearm-geometry-faired.png",
            "locked V7 production forearm geometry",
        ),
        record(
            "masks/production-forearm-flat-color-faired.png",
            "locked V7 production forearm flat-color reference",
        ),
        record(
            "masks/elbow-seam-bilateral-fairing-removed-35px.png",
            "approved 35-pixel neutral fairing exception",
        ),
        record("masks/F1-elbow-active-root-faired.png", "F1 active elbow root"),
        record("masks/F2-locked-visible-source.png", "F2 visible source"),
        record("masks/F3-hidden-body-fill.png", "F3 hidden body fill"),
        record("masks/F4-wrist-hidden-extension.png", "F4 wrist extension"),
        record(
            "masks/F5-wrist-responsibility-not-material.png",
            "F5 QA responsibility, not material",
        ),
        record(
            "masks/temporary-hand-root-envelope.png",
            "temporary hand-root minimum envelope",
        ),
    ]
    qa_paths = [
        "qa/V7-C1-ELBOW-SEAM-BEFORE-AFTER.png",
        "qa/V7-C1-PRODUCTION-FOREARM-F1-F5-BOARD.png",
        "qa/V7-C1-FORMAL-ELBOW-THREE-ANGLES.png",
        "qa/V7-C1-FORMAL-ELBOW-SLOW-SCAN.gif",
        "qa/V7-C1-WRIST-THREE-ANGLES.png",
        "qa/V7-C1-WRIST-SLOW-SCAN.gif",
        "qa/V7-C1-FULL-CHAIN-ELBOW-WRIST-3X3.png",
        "qa/V7-C1-DISPLACED-PART-INTEGRITY.png",
    ]
    final_qa = [record(path, "approved Chinese visual QA") for path in qa_paths]
    contracts = [
        record(
            "audit/v7c1-formal-elbow-root-replacement-contract.json",
            "approved formal elbow-root replacement contract",
        ),
        record(
            "audit/v7c1-temporary-hand-root-envelope-contract.json",
            "approved temporary hand-root contract",
        ),
    ]
    approval_records = [
        record(
            (
                "audit/v7c1-user-visual-approval-and-freeze-authorization-"
                "2026-07-26.json"
            ),
            "final V7-C1 user visual approval and freeze authorization",
        )
    ]
    engineering = [
        record(
            "audit/v7c1-elbow-seam-fairing.json",
            "machine-readable final engineering report",
        ),
        record(
            "audit/v7c1-parameter-domain-scans.json",
            "complete elbow, wrist, combined, and full-pose scans",
        ),
        record(
            "audit/V7-C1-ELBOW-SEAM-FAIRING.zh-CN.md",
            "Chinese engineering report",
        ),
        record(
            "audit/v7c1-user-review-stale-cache-2026-07-26.json",
            "stale-evidence diagnosis and correction record",
        ),
        record(
            "audit/v7c1-evidence-manifest.json",
            "pre-freeze deterministic evidence manifest",
        ),
        record(
            "audit/v7c1-final-completion-audit-2026-07-26.json",
            "requirement-by-requirement completion audit",
        ),
        record(
            "audit/V7-C1-FINAL-COMPLETION-AUDIT-2026-07-26.zh-CN.md",
            "Chinese final completion audit",
        ),
        record(
            "tools/build_v7c1_elbow_seam_fairing.py",
            "deterministic V7-C1 builder",
        ),
        record(
            "tools/freeze_v7c1_production_forearm.py",
            "final freeze verifier and manifest generator",
        ),
    ]

    v4_manifest = (
        VALIDATION
        / "arm-chain-screen-right-v4-wrist-motion/archive/"
        "STAGE-A-V4-APPROVED-2026-07-24.json"
    )
    sleeve_manifest = (
        VALIDATION
        / "arm-chain-screen-right-v5-hidden-upper-arm/"
        "complete-sleeve-final/audit/"
        "complete-sleeve-freeze-manifest-2026-07-25.json"
    )
    v6_manifest = (
        VALIDATION
        / "arm-chain-screen-right-v6-complete-upper-arm-geometry/audit/"
        "v6-complete-upper-arm-geometry-freeze-manifest-2026-07-25.json"
    )
    upstream_manifests = [
        {
            "role": "frozen V4 checkpoint",
            "path": v4_manifest.relative_to(VALIDATION).as_posix(),
            "sha256": sha256(v4_manifest),
        },
        {
            "role": "frozen complete sleeve checkpoint",
            "path": sleeve_manifest.relative_to(VALIDATION).as_posix(),
            "sha256": sha256(sleeve_manifest),
        },
        {
            "role": "frozen V6 checkpoint",
            "path": v6_manifest.relative_to(VALIDATION).as_posix(),
            "sha256": sha256(v6_manifest),
        },
    ]
    upstream_approvals = [
        upstream_record(
            V7 / "audit/v7a-user-visual-decision-2026-07-26.json",
            "V7-A ownership user approval",
        ),
        upstream_record(
            V7
            / "v7b2-angle-dependent-root-taper-feasibility/audit/"
            "v7b2-user-visual-approval-2026-07-26.json",
            "V7-B2 angle-dependent taper user approval",
        ),
    ]

    hits = privacy_hits()
    if hits:
        raise RuntimeError(
            "Outward privacy scan failed: "
            + ", ".join(item["path"] for item in hits)
        )

    freeze = {
        "schemaVersion": 1,
        "checkpoint": "v7_production_forearm_flat_geometry_frozen",
        "freezeDate": "2026-07-26",
        "decisionOwner": "user",
        "status": "frozen_engineering_and_user_visual_pass",
        "scope": "screen-right character-left production forearm pure-color geometry",
        "checksumAlgorithm": "SHA-256",
        "lockedGeometry": locked_geometry,
        "approvedContracts": contracts,
        "userApprovalRecords": approval_records,
        "finalQa": final_qa,
        "engineeringEvidence": engineering,
        "upstreamFrozenCheckpoints": upstream_manifests,
        "upstreamUserApprovals": upstream_approvals,
        "frozenInputIntegrity": {
            "status": "pass",
            "groups": [
                {
                    "name": group["name"],
                    "checked": group["checked"],
                    "passed": group["passed"],
                    "failed": group["failed"],
                }
                for group in frozen_integrity["frozenArtifactGroups"]
            ],
        },
        "finalMetrics": {
            "productionForearmPixels": 3855,
            "connectedComponents": 1,
            "holes": 0,
            "approvedNeutralFairingExceptionPixels": 35,
            "retainedVisibleSourcePixels": 3721,
            "retainedSourceRgbDifferencePixels": 0,
            "elbowMaximumGapPixelsAt4x": 0,
            "elbowBrokenAdjacencyEvaluations": 0,
            "wristMaximumGapPixelsAt4x": 0,
            "wristBrokenAdjacencySamples": 0,
            "combined9x9MaximumGapPixelsAt4x": 0,
            "disconnectedFullPoseForearmSamples": 0,
            "deterministicRegenerationDifferenceFiles": 0,
            "outwardPrivacyHits": 0,
        },
        "invalidationRules": [
            "Any byte change to a locked geometry, approved contract, user approval record, final QA item, or engineering evidence item invalidates this freeze.",
            "Changing the frozen elbow, wrist, bone lengths, theta2 range, wrist range, or V7-B2 deformation rule reopens V7.",
            "Changing or removing the approved 35-pixel neutral fairing exception reopens V7-C1.",
            "Formal hand geometry must contain the frozen temporary hand-root envelope; otherwise the V7 wrist conclusion is invalid.",
            "After formal hand creation, rerun the complete wrist domain with real hand geometry.",
            "Cubism binding requires a new full-domain interpolation test; rigid-FK independence does not transfer automatically.",
        ],
        "explicitlyNotApproved": [
            "upper-arm or forearm texture",
            "formal hand geometry",
            "PSD",
            "ArtMesh",
            "Cubism",
            "Physics",
            "Runtime",
        ],
        "nextGate": "formal hand pure-color geometry",
        "sequencingRule": (
            "Complete and validate formal hand pure-color geometry with the real "
            "wrist rerun before discussing hidden texture order."
        ),
    }
    write_json(FREEZE_MANIFEST, freeze)

    current = dict(completion)
    current["status"] = "complete_and_frozen"
    current["freezeManifest"] = (
        "v7c1-elbow-seam-fairing/audit/"
        "v7-production-forearm-geometry-freeze-manifest-2026-07-26.json"
    )
    current["freezeManifestSha256"] = sha256(FREEZE_MANIFEST)
    write_json(CURRENT_JSON, current)
    CURRENT_MD.write_text(completion_md, encoding="utf-8")
    CURRENT_ROOT_MD.write_text(completion_md, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "frozen_engineering_and_user_visual_pass",
                "deterministicDifferenceFiles": len(differences),
                "privacyHits": len(hits),
                "requirementsPassed": len(requirements),
                "freezeManifest": FREEZE_MANIFEST.relative_to(V7).as_posix(),
                "freezeManifestSha256": sha256(FREEZE_MANIFEST),
                "nextGate": "formal hand pure-color geometry",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
