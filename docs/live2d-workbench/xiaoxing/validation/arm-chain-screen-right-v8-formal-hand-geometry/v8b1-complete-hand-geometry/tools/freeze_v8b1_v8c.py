from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
V8 = ROOT.parent
VALIDATION = V8.parent
V4 = VALIDATION / "arm-chain-screen-right-v4-wrist-motion"
V5 = VALIDATION / "arm-chain-screen-right-v5-hidden-upper-arm"
V6 = VALIDATION / "arm-chain-screen-right-v6-complete-upper-arm-geometry"
V7 = VALIDATION / "arm-chain-screen-right-v7-production-forearm-geometry"
V7C1 = V7 / "v7c1-elbow-seam-fairing"

BUILDER = ROOT / "tools/build_v8b1_complete_hand_geometry.py"
REPORT = ROOT / "audit/v8b1-v8c-engineering-report.json"
SCANS = ROOT / "audit/v8c-parameter-domain-scans.json"
EVIDENCE_MANIFEST = ROOT / "audit/v8b1-evidence-manifest.json"
APPROVAL = (
    ROOT
    / "audit/v8b1-v8c-user-visual-approval-and-freeze-authorization-"
    "2026-07-26.json"
)
COMPLETION_JSON = (
    ROOT / "audit/v8b1-v8c-final-completion-audit-2026-07-26.json"
)
COMPLETION_MD = (
    ROOT / "audit/V8-B1-V8-C-FINAL-COMPLETION-AUDIT-2026-07-26.zh-CN.md"
)
FREEZE_MANIFEST = (
    ROOT / "audit/v8b1-v8c-freeze-manifest-2026-07-26.json"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path.name}")
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
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def record(relative_path: str, role: str) -> dict:
    path = ROOT / relative_path
    if not path.is_file():
        raise RuntimeError(f"Missing freeze artifact: {relative_path}")
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
        "path": path.relative_to(VALIDATION).as_posix(),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def verify_evidence_manifest() -> list[dict]:
    manifest = json.loads(EVIDENCE_MANIFEST.read_text(encoding="utf-8"))
    rows = []
    for item in manifest["files"]:
        path = ROOT / item["path"]
        actual_hash = sha256(path) if path.is_file() else None
        actual_bytes = path.stat().st_size if path.is_file() else None
        rows.append(
            {
                "path": item["path"],
                "expectedSha256": item["sha256"],
                "actualSha256": actual_hash,
                "expectedBytes": item["bytes"],
                "actualBytes": actual_bytes,
                "pass": (
                    actual_hash == item["sha256"]
                    and actual_bytes == item["bytes"]
                ),
            }
        )
    return rows


def privacy_hits() -> list[dict]:
    patterns = [
        ("/" + "Users/", "user-path"),
        ("\\" + "Users" + "\\", "user-path"),
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
        content = path.read_text(encoding="utf-8", errors="replace")
        for needle, label in patterns:
            if needle in content:
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
            "Freeze manifest already exists; frozen V8-B1/V8-C must not be rebuilt."
        )

    builder = load_module("v8b1_freeze_builder", BUILDER)
    fresh_preflight = builder.preflight()
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
    evidence_rows = verify_evidence_manifest()

    geometry = report["geometry"]
    wrist = report["v8c"]["wrist"]
    combined = report["v8c"]["combined9x9"]
    slow = report["v8c"]["slowScan"]
    required = {
        "freshPreflight": (
            fresh_preflight["status"] == "pass"
            and fresh_preflight["failed"] == 0
        ),
        "evidenceManifest": all(row["pass"] for row in evidence_rows),
        "engineeringPass": report["engineeringPass"] is True,
        "qualifiedUserApproval": (
            approval["status"]
            == "user_visual_approved_with_reservation_and_freeze_authorized"
        ),
        "h1": (
            geometry["H1"]["pixels"] == 2629
            and geometry["H1"]["coordinateDifferencePixels"] == 0
            and geometry["H1"]["rgbDifferencePixels"] == 0
        ),
        "h2": (
            geometry["H2"]["pixels"] == 81
            and geometry["H2"]["exactFrozenDifference"] is True
        ),
        "h3": (
            geometry["H3"]["pixels"] == 42
            and geometry["H3"]["outsidePermittedLocalRoiPixels"] == 0
            and geometry["H3"]["notHiddenByForearmSkinAtNeutralPixels"] == 0
        ),
        "partition": all(
            value == 0
            for value in geometry["responsibilityIntersections"].values()
        ),
        "envelope": geometry["envelope"]["missingFromMHandPixels"] == 0,
        "topology": (
            geometry["topology"]["mHandPixels"] == 2752
            and geometry["topology"]["connectedComponents"] == 1
            and geometry["topology"]["holes"] == 0
            and geometry["topology"]["fingerGapBackgroundMisfillPixels"] == 0
        ),
        "neutral": (
            geometry["defaultRecomposition"][
                "lockedVisibleCoordinateDifferencePixels"
            ]
            == 0
            and geometry["defaultRecomposition"]["newPersonOutlinePixels"] == 0
        ),
        "wrist": (
            wrist["maximumMissingResponsibilityPixelsAt4x"] == 0
            and wrist["brokenAdjacencySamples"] == 0
            and wrist["returnDifferencePixels"] == 0
            and wrist["braceletCountedAsCoverage"] is False
        ),
        "combined": (
            combined["maximumMissingResponsibilityPixelsAt4x"] == 0
            and combined["brokenAdjacencySamples"] == 0
            and combined["maximumUnapprovedForearmCollisionPixels"] == 0
            and combined["maximumUpperSleeveCollisionPixels"] == 0
            and combined["prototypeTriangleFlips"] == 0
            and combined["maximumBoneLengthErrorPx"] <= 0.01
        ),
        "slowReturn": slow["returnDifferencePixels"] == 0,
        "deterministic": (
            report["deterministicRegeneration"]["differenceFiles"] == 0
        ),
    }
    failed = [name for name, passed in required.items() if not passed]
    if failed:
        raise RuntimeError("Freeze requirements failed: " + ", ".join(failed))

    hits = privacy_hits()
    if hits:
        raise RuntimeError(
            "Outward privacy scan failed: "
            + ", ".join(item["path"] for item in hits)
        )

    forbidden_directories = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_dir()
        and path.name.lower()
        in {
            "texture",
            "textures",
            "psd",
            "artmesh",
            "cubism",
            "physics",
            "runtime",
            "clipping",
        }
    ]
    if forbidden_directories:
        raise RuntimeError(
            "Forbidden downstream directories exist: "
            + ", ".join(forbidden_directories)
        )

    requirements = [
        {
            "id": "scope-and-privacy",
            "status": "pass",
            "evidence": "all new artifacts are V8-B1-local, use relative paths, and outward privacy hits are 0",
        },
        {
            "id": "frozen-input-integrity",
            "status": "pass",
            "evidence": "fresh preflight 145/145; V4, sleeve, V6, V7-C1, and V8-A frozen evidence remains intact",
        },
        {
            "id": "formal-m-hand",
            "status": "pass",
            "evidence": "M_hand 2752 px; H1 2629, H2 81, H3 42; H1/H2/H3 intersections 0",
        },
        {
            "id": "v-hand-lock",
            "status": "pass",
            "evidence": "H1 coordinate difference 0 and RGB difference 0",
        },
        {
            "id": "envelope-containment",
            "status": "pass",
            "evidence": "all 389 frozen E_hand pixels are contained; missing 0",
        },
        {
            "id": "topology-and-finger-gaps",
            "status": "pass",
            "evidence": "one connected component, zero holes, finger-gap misfill 0",
        },
        {
            "id": "h3-locality-and-minimization",
            "status": "pass",
            "evidence": "H3 is 42 px, outside permitted wrist ROI 0; minimum under declared 1 px AA plus 1 px future-deformation margin",
        },
        {
            "id": "neutral-recomposition",
            "status": "pass",
            "evidence": "locked visible coordinate difference 0 and new person-outline pixels 0",
        },
        {
            "id": "real-hand-wrist-domain",
            "status": "pass",
            "evidence": "201 dense + 11 boundary + 81 adaptive samples; gap 0, broken adjacency 0, return difference 0",
        },
        {
            "id": "bracelet-hidden-skin-coverage",
            "status": "pass",
            "evidence": "maximum skin responsibility gap 0 with bracelet excluded from coverage",
        },
        {
            "id": "combined-domain",
            "status": "pass",
            "evidence": "elbow-by-wrist 9x9: gap 0, detachment 0, unapproved collisions 0, triangle flips 0",
        },
        {
            "id": "bone-and-return",
            "status": "pass",
            "evidence": "maximum bone error within 0.01 px and slow 0-to-1-to-0 return difference 0",
        },
        {
            "id": "deterministic-generation",
            "status": "pass",
            "evidence": "fresh pre-approval and post-approval regeneration difference files 0",
        },
        {
            "id": "chinese-visual-evidence",
            "status": "pass_user_approved_with_reservation",
            "evidence": "14 Chinese review artifacts were accepted as sufficient for this gate",
        },
        {
            "id": "user-freeze-authorization",
            "status": "pass",
            "evidence": "audit/v8b1-v8c-user-visual-approval-and-freeze-authorization-2026-07-26.json",
        },
        {
            "id": "forbidden-downstream-work",
            "status": "pass_none_created",
            "evidence": "no texture, PSD, ArtMesh, Cubism, Physics, Runtime, finger split, clipping, or independent wrist layer was created",
        },
    ]

    completion = {
        "schemaVersion": 1,
        "objective": "V8-B1 formal complete hand flat-color geometry and V8-C real-hand wrist validation",
        "status": "complete_ready_to_freeze",
        "decisionOwner": "user",
        "visualApprovalCharacterization": approval["approvalCharacterization"],
        "requirements": requirements,
        "summary": {
            "passed": len(requirements),
            "failed": 0,
            "missing": 0,
            "forbiddenDownstreamWorkCreated": False,
        },
        "finalGeometry": {
            "h1Pixels": 2629,
            "h2Pixels": 81,
            "h3Pixels": 42,
            "mHandPixels": 2752,
            "connectedComponents": 1,
            "holes": 0,
            "fingerGapMisfillPixels": 0,
        },
        "stageAArmMaterialGeometryChain": "complete",
        "nextGate": "separately authorized texture planning; no texture work is authorized by this freeze",
    }
    write_json(COMPLETION_JSON, completion)

    completion_md = """# V8-B1 / V8-C 最终完成审计

## 结论

V8-B1 正式完整手部纯色几何与 V8-C 真实手部腕部验证已获得工程通过，以及
用户带保留意见的视觉批准和明确冻结授权，可以冻结。

“带保留意见”表示当前结果足以通过本门禁，但不应被解释为无保留的高级视觉
品质认可，也不授权未来擅自加粗、改形或重做已经冻结的腕部和手部几何。

## 最终事实

- H1 `2629 px`、H2 `81 px`、H3 `42 px`，责任交集均为 `0`；
- M_hand `2752 px`，单连通，孔洞 `0`；
- 389 px 包络缺失 `0`；
- V_hand 坐标差 `0`、RGB 差 `0`；
- 指缝误填 `0`，默认位置人物轮廓外新增像素 `0`；
- 腕部 `201 + 11 + 81`：最大缺口 `0`、断开 `0`、回程差 `0`；
- 肘×腕 `9×9`：最大缺口 `0`、断开 `0`、未批准碰撞 `0`；
- 手链隐藏后皮肤覆盖缺口 `0`，手链未计入皮肤覆盖；
- 原型三角形翻折 `0`，骨长误差在 `0.01 px` 内；
- 确定性重新生成差异 `0`，隐私命中 `0`；
- 未制作纹理、PSD、ArtMesh、Cubism、Physics 或 Runtime。

## 阶段结论

单臂阶段 A 的 `sleeve → upper_arm → production_forearm → whole_hand`
四材料几何链完成并冻结。

下一步只能在另行授权后讨论纹理规划；本冻结不授权直接制作纹理。
"""
    COMPLETION_MD.write_text(completion_md, encoding="utf-8")

    locked_geometry = [
        record("masks/H1-frozen-visible-hand.png", "H1 frozen visible hand"),
        record(
            "masks/H2-frozen-envelope-difference-81px.png",
            "H2 exact frozen envelope difference",
        ),
        record(
            "masks/H3-parameterized-hidden-wrist-margin.png",
            "H3 constrained hidden wrist margin",
        ),
        record(
            "masks/H4-wrist-coverage-qa-not-material.png",
            "H4 QA responsibility, not material",
        ),
        record(
            "masks/M-hand-complete-geometry.png",
            "locked formal complete whole-hand geometry",
        ),
        record(
            "materials/geometry/M-hand-flat-color.png",
            "locked formal whole-hand flat-color reference",
        ),
    ]
    qa_paths = [
        "qa/V8-B1-H1-H2-H3-H4-PARTITIONS.png",
        "qa/V8-B1-M-HAND-CHECKERBOARD.png",
        "qa/V8-B1-DEFAULT-RECOMPOSITION.png",
        "qa/V8-B1-SOURCE-OUTLINE-OVERLAY.png",
        "qa/V8-B1-FOREARM-MOVED-AWAY.png",
        "qa/V8-B1-HAND-MOVED-AWAY.png",
        "qa/V8-C-BRACELET-SHOW-HIDE-SEAM.png",
        "qa/V8-C-WRIST-MIN-NEUTRAL-MAX.png",
        "qa/V8-C-WRIST-200PCT.png",
        "qa/V8-C-ELBOW-WRIST-9X9.png",
        "qa/V8-C-WRIST-SLOW-0-1-0.gif",
        "qa/V8-B1-FINGER-GAP-PROTECTION.png",
        "qa/V8-B1-WRIST-WIDTH-PROFILE.png",
        "qa/V8-B1-V8-C-USER-REVIEW-BOARD.zh-CN.png",
    ]
    final_qa = [record(path, "approved Chinese visual QA") for path in qa_paths]
    engineering = [
        record(
            "audit/v8b1-v8c-engineering-report.json",
            "machine-readable engineering report",
        ),
        record(
            "audit/v8c-parameter-domain-scans.json",
            "complete wrist and combined-domain scans",
        ),
        record(
            "audit/V8-B1-V8-C-ENGINEERING-REPORT.zh-CN.md",
            "Chinese engineering report",
        ),
        record(
            "audit/v8b1-evidence-manifest.json",
            "pre-freeze deterministic evidence manifest",
        ),
        record(
            "audit/v8b1-v8c-final-completion-audit-2026-07-26.json",
            "requirement-by-requirement completion audit",
        ),
        record(
            "audit/V8-B1-V8-C-FINAL-COMPLETION-AUDIT-2026-07-26.zh-CN.md",
            "Chinese final completion audit",
        ),
        record(
            "tools/build_v8b1_complete_hand_geometry.py",
            "deterministic V8-B1/V8-C builder",
        ),
        record(
            "tools/freeze_v8b1_v8c.py",
            "final freeze verifier and manifest generator",
        ),
    ]
    approvals = [
        record(
            "audit/v8b1-v8c-user-visual-approval-and-freeze-authorization-2026-07-26.json",
            "qualified user visual approval and explicit freeze authorization",
        )
    ]
    contracts = [
        upstream_record(
            V8 / "audit/v8a1-forearm-above-hand-contract.json",
            "approved forearm-above-hand draw-order contract",
        ),
        upstream_record(
            V8 / "audit/v8a2-visible-hand-ownership-contract.json",
            "frozen exact visible-hand ownership contract",
        ),
        upstream_record(
            V8 / "audit/v8b0-complete-hand-geometry-contract.json",
            "approved complete-hand geometry contract",
        ),
        upstream_record(
            V7C1 / "audit/v7c1-temporary-hand-root-envelope-contract.json",
            "frozen 389 px hand-root envelope contract",
        ),
    ]
    upstream = [
        upstream_record(
            V4 / "archive/STAGE-A-V4-APPROVED-2026-07-24.json",
            "frozen V4 checkpoint",
        ),
        upstream_record(
            V5
            / "complete-sleeve-final/audit/"
            "complete-sleeve-freeze-manifest-2026-07-25.json",
            "frozen complete-sleeve checkpoint",
        ),
        upstream_record(
            V6
            / "audit/v6-complete-upper-arm-geometry-freeze-manifest-"
            "2026-07-25.json",
            "frozen V6 checkpoint",
        ),
        upstream_record(
            V7C1
            / "audit/v7-production-forearm-geometry-freeze-manifest-"
            "2026-07-26.json",
            "frozen V7-C1 checkpoint",
        ),
        upstream_record(
            V8 / "audit/v8a-final-freeze-manifest-2026-07-26.json",
            "frozen V8-A checkpoint",
        ),
    ]

    freeze = {
        "schemaVersion": 1,
        "checkpoint": "V8-B1 formal complete hand geometry and V8-C real-hand wrist validation",
        "freezeDate": "2026-07-26",
        "decisionOwner": "user",
        "status": "frozen_engineering_and_qualified_user_visual_pass",
        "visualApprovalCharacterization": approval["approvalCharacterization"],
        "scope": "screen-right character-left formal whole-hand flat-color geometry and real-hand wrist domain",
        "checksumAlgorithm": "SHA-256",
        "lockedGeometry": locked_geometry,
        "approvedContracts": contracts,
        "userApprovalRecords": approvals,
        "finalQa": final_qa,
        "engineeringEvidence": engineering,
        "upstreamFrozenCheckpoints": upstream,
        "frozenInputIntegrity": {
            "status": "pass",
            "checked": fresh_preflight["checked"],
            "passed": fresh_preflight["passed"],
            "failed": fresh_preflight["failed"],
            "groups": fresh_preflight["upstreamGroups"],
        },
        "finalMetrics": {
            "h1Pixels": 2629,
            "h2Pixels": 81,
            "h3Pixels": 42,
            "mHandPixels": 2752,
            "envelopeMissingPixels": 0,
            "h1CoordinateDifferencePixels": 0,
            "h1RgbDifferencePixels": 0,
            "connectedComponents": 1,
            "holes": 0,
            "fingerGapMisfillPixels": 0,
            "defaultNewPersonOutlinePixels": 0,
            "wristMaximumGapPixelsAt4x": 0,
            "wristBrokenAdjacencySamples": 0,
            "combined9x9MaximumGapPixelsAt4x": 0,
            "combinedBrokenAdjacencySamples": 0,
            "unapprovedCollisionPixels": 0,
            "prototypeTriangleFlips": 0,
            "slowReturnDifferencePixels": 0,
            "deterministicRegenerationDifferenceFiles": 0,
            "outwardPrivacyHits": 0,
        },
        "stageAArmMaterialGeometryChain": "complete_and_frozen",
        "invalidationRules": [
            "Any byte change to locked geometry, the approval record, final QA, engineering evidence, or this gate's contracts invalidates this freeze.",
            "Changing V_hand ownership, the 389 px envelope, wrist point, local coordinates, draw order, bracelet ownership, or wrist range reopens V8.",
            "Changing H3 axial margin or wrist-root width profile reopens V8-B1/V8-C.",
            "Finger-relative motion requires reopening material granularity before finger splitting.",
            "Texture must remain inside the frozen geometry and cannot redesign alpha boundaries.",
            "Cubism binding requires a new full-domain interpolation test; rigid-FK proof does not transfer automatically.",
        ],
        "explicitlyNotApproved": approval["explicitlyNotApproved"],
        "nextGate": "separately authorized texture planning",
        "sequencingRule": "Do not create texture, PSD, ArtMesh, Cubism, Physics, or Runtime without a separate authorization.",
    }
    write_json(FREEZE_MANIFEST, freeze)

    print(
        json.dumps(
            {
                "status": freeze["status"],
                "requirementsPassed": len(requirements),
                "evidenceFilesVerified": len(evidence_rows),
                "freshPreflight": (
                    f"{fresh_preflight['passed']}/{fresh_preflight['checked']}"
                ),
                "privacyHits": len(hits),
                "freezeManifest": FREEZE_MANIFEST.relative_to(ROOT).as_posix(),
                "freezeManifestSha256": sha256(FREEZE_MANIFEST),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
