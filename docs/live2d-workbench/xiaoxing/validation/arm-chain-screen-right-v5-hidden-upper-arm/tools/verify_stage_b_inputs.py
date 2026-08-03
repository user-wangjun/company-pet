from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import date
from pathlib import Path

from PIL import Image, ImageChops


HERE = Path(__file__).resolve()
XIAOXING_ROOT = HERE.parents[3]
VALIDATION_ROOT = HERE.parents[1]
V4_ARCHIVE_ROOT = (
    XIAOXING_ROOT
    / "validation"
    / "arm-chain-screen-right-v4-wrist-motion"
    / "archive"
)
V4_MANIFEST_PATH = V4_ARCHIVE_ROOT / "STAGE-A-V4-APPROVED-2026-07-24.json"
V4_ZIP_PATH = V4_ARCHIVE_ROOT / "stage-a-v4-approved-2026-07-24.zip"
AUDIT_JSON_PATH = VALIDATION_ROOT / "audit" / "input-verification.json"
AUDIT_MD_PATH = VALIDATION_ROOT / "audit" / "input-verification.zh-CN.md"

SOURCE_EXPECTATIONS = {
    "source/xiaoxing-three-view-line.png": (
        "7f8605a85df7fa2c8843e925f8274a06403d884d975b1b195b2a583478dc222c"
    ),
    "source/xiaoxing-three-view-color.png": (
        "2d1b9c71c4e6c17ea503800b05f44bf7bfe127799a5e156886c191b97d350154"
    ),
    "source/masters/front-line-source-exact-after-reset.png": (
        "706aaf10652147cf76e233532b5459ce130921a96806f6970c91e1f3a427172f"
    ),
    "source/masters/front-color-source-exact-after-reset.png": (
        "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5"
    ),
}

FRONT_CROP_PAIRS = (
    (
        "source/xiaoxing-three-view-line.png",
        "source/masters/front-line-source-exact-after-reset.png",
    ),
    (
        "source/xiaoxing-three-view-color.png",
        "source/masters/front-color-source-exact-after-reset.png",
    ),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_to_xiaoxing(path: Path) -> str:
    return path.relative_to(XIAOXING_ROOT).as_posix()


def verify_v4_archive() -> list[dict[str, object]]:
    manifest = json.loads(V4_MANIFEST_PATH.read_text(encoding="utf-8"))
    results: list[dict[str, object]] = []
    with zipfile.ZipFile(V4_ZIP_PATH) as archive:
        names = set(archive.namelist())
        for artifact, expected in manifest["artifactSha256"].items():
            present = artifact in names
            actual = sha256_bytes(archive.read(artifact)) if present else None
            results.append(
                {
                    "path": artifact,
                    "expectedSha256": expected.lower(),
                    "actualSha256": actual,
                    "present": present,
                    "matches": present and actual == expected.lower(),
                }
            )
    return results


def verify_sources() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for relative_path, expected in SOURCE_EXPECTATIONS.items():
        path = XIAOXING_ROOT / relative_path
        actual = sha256_file(path)
        with Image.open(path) as image:
            size = list(image.size)
            mode = image.mode
        results.append(
            {
                "path": relative_path,
                "expectedSha256": expected,
                "actualSha256": actual,
                "matches": actual == expected,
                "size": size,
                "mode": mode,
            }
        )
    return results


def verify_front_crops() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    crop_box = (34, 0, 34 + 512, 1086)
    for three_view_relative, front_relative in FRONT_CROP_PAIRS:
        three_view_path = XIAOXING_ROOT / three_view_relative
        front_path = XIAOXING_ROOT / front_relative
        with Image.open(three_view_path) as three_view, Image.open(front_path) as front:
            crop = three_view.crop(crop_box).convert("RGBA")
            front_rgba = front.convert("RGBA")
            exact = ImageChops.difference(crop, front_rgba).getbbox() is None
            results.append(
                {
                    "threeViewPath": three_view_relative,
                    "frontMasterPath": front_relative,
                    "cropBox": [34, 0, 512, 1086],
                    "frontSize": list(front.size),
                    "frontIs512x1086": front.size == (512, 1086),
                    "pixelExactIntegerCrop": exact,
                    "scaled": not exact,
                }
            )
    return results


def build_markdown(report: dict[str, object]) -> str:
    v4_rows = "\n".join(
        f"| `{item['path']}` | {'通过' if item['matches'] else '失败'} |"
        for item in report["v4FrozenArtifacts"]
    )
    source_rows = "\n".join(
        f"| `{item['path']}` | `{item['size'][0]}×{item['size'][1]}` | "
        f"{'通过' if item['matches'] else '失败'} |"
        for item in report["authoritativeImages"]
    )
    crop_rows = "\n".join(
        f"| `{item['frontMasterPath']}` | "
        f"{'通过' if item['frontIs512x1086'] else '失败'} | "
        f"{'通过' if item['pixelExactIntegerCrop'] else '失败'} |"
        for item in report["frontMasterCropVerification"]
    )
    status_cn = "通过" if report["status"] == "pass" else "失败"
    return f"""# 阶段 B 输入冻结复核

## 结论

**{status_cn}。**

- V4 冻结清单列出的产物均直接从冻结 ZIP 中读取并校验，没有解压或修改 V4 目录。
- 四张权威图像的 SHA-256 均与交接记录一致。
- 两张正面母图均为 `512×1086`。
- 两张正面母图均等于各自三视图从 `(x=34, y=0, width=512, height=1086)` 做出的整数裁切，逐像素一致，没有缩放。

本报告只证明输入身份和正面母图坐标锁定，不证明可见上臂像素所有权、袖口 alpha 边界、连续参数域覆盖或真实纹理质量。

## V4 冻结产物

| 产物 | SHA-256 |
| --- | --- |
{v4_rows}

## 权威图像

| 图像 | 尺寸 | SHA-256 |
| --- | ---: | --- |
{source_rows}

## 正面母图整数裁切

| 正面母图 | 尺寸 `512×1086` | 与三视图整数裁切逐像素一致 |
| --- | --- | --- |
{crop_rows}

## 下一门禁

在原始整数坐标中建立精确 `V_upper_arm`，并独立锁定袖口遮挡 alpha 边界及 1–3 px 混合带所有权。两项均需中文高倍率视觉审查和用户明确批准；批准前不得计算最终 `H_test` 或补画隐藏纹理。
"""


def main() -> None:
    v4_results = verify_v4_archive()
    source_results = verify_sources()
    crop_results = verify_front_crops()
    passed = (
        all(item["matches"] for item in v4_results)
        and all(item["matches"] for item in source_results)
        and all(
            item["frontIs512x1086"] and item["pixelExactIntegerCrop"]
            for item in crop_results
        )
    )
    report: dict[str, object] = {
        "schemaVersion": 1,
        "auditDate": date.today().isoformat(),
        "scope": "stage_b_input_freeze_verification",
        "status": "pass" if passed else "fail_stop",
        "privacy": {
            "pathsAreRelative": True,
            "originalAssetsUploaded": False,
            "externalImageServicesUsed": False,
        },
        "v4Manifest": relative_to_xiaoxing(V4_MANIFEST_PATH),
        "v4Archive": relative_to_xiaoxing(V4_ZIP_PATH),
        "v4FrozenArtifacts": v4_results,
        "authoritativeImages": source_results,
        "frontMasterCropVerification": crop_results,
        "limitations": [
            "Does not prove exact visible upper-arm ownership.",
            "Does not prove the sleeve-hem occluder alpha boundary.",
            "Does not prove continuous-parameter coverage.",
            "Does not prove textured-alpha seam quality.",
        ],
        "nextGate": (
            "Lock exact V_upper_arm and the sleeve-hem occluder alpha boundary, "
            "then obtain explicit Chinese visual approval."
        ),
    }
    AUDIT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_JSON_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    AUDIT_MD_PATH.write_text(build_markdown(report), encoding="utf-8")
    if not passed:
        raise SystemExit("Input verification failed; Stage B must stop.")
    print("PASS: Stage B authoritative inputs and frozen V4 artifacts match.")


if __name__ == "__main__":
    main()
