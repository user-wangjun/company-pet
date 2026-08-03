from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "qa"
AUDIT = ROOT / "audit"

FRAME_NAMES = [
    "cubism-36-taper-0-clean.png",
    "cubism-35-taper-25-clean.png",
    "cubism-34-taper-50-clean.png",
    "cubism-33-taper-75-clean.png",
    "cubism-32-taper-100-clean.png",
    "cubism-38-taper-reset-clean.png",
]

# The final evidence was captured at 400% editor zoom. This rectangle contains
# the complete arm canvas and excludes the parameter panel.
CANVAS_CROP = (1160, 280, 1390, 760)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def make_board(
    output_name: str,
    title: str,
    subtitle: str,
    items: list[tuple[str, str]],
) -> None:
    cell_w, cell_h = 520, 410
    margin, header_h = 28, 116
    cols = 3
    rows = (len(items) + cols - 1) // cols
    board = Image.new(
        "RGB",
        (margin * 2 + cols * cell_w, header_h + margin + rows * cell_h),
        "#f4f6f8",
    )
    draw = ImageDraw.Draw(board)
    draw.text((margin, 20), title, fill="#17212b", font=font(30))
    draw.text((margin, 65), subtitle, fill="#b42318", font=font(18))
    for index, (label, filename) in enumerate(items):
        row, col = divmod(index, cols)
        x = margin + col * cell_w
        y = header_h + row * cell_h
        image = Image.open(QA / filename).convert("RGB")
        crop = image.crop((650, 140, 1536, 880))
        crop.thumbnail((cell_w - 24, cell_h - 58))
        panel = Image.new("RGB", (cell_w - 12, cell_h - 12), "white")
        panel.paste(crop, ((panel.width - crop.width) // 2, 42))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.text((12, 8), label, fill="#17212b", font=font(18))
        draw.rounded_rectangle(
            (x, y, x + panel.width, y + panel.height),
            radius=10,
            fill="white",
            outline="#cbd5df",
            width=2,
        )
        board.paste(panel, (x, y))
    board.save(QA / output_name)


def main() -> None:
    frames = [Image.open(QA / name).convert("RGBA") for name in FRAME_NAMES]
    frame_size = frames[0].size
    if any(frame.size != frame_size for frame in frames):
        raise SystemExit("Cubism GUI evidence screenshots have inconsistent sizes.")

    default_crop = frames[0].crop(CANVAS_CROP)
    return_crop = frames[-1].crop(CANVAS_CROP)
    difference = ImageChops.difference(default_crop, return_crop)
    stats = ImageStat.Stat(difference)
    changed_pixels = sum(
        1
        for pixel in difference.get_flattened_data()
        if pixel[0] or pixel[1] or pixel[2] or pixel[3]
    )
    report = {
        "schemaVersion": 1,
        "status": "pass" if changed_pixels == 0 else "review",
        "evidenceSource": "real Cubism Editor GUI screenshots",
        "physicsEnabled": False,
        "sequence": ["0", "0.25", "0.5", "0.75", "1", "0"],
        "screenshots": [
            {"path": f"qa/{name}", "sha256": sha256(QA / name)}
            for name in FRAME_NAMES
        ],
        "canvasCropScreenshotPx": list(CANVAS_CROP),
        "defaultReturnPixelComparison": {
            "changedPixels": changed_pixels,
            "maximumChannelDifference": max(channel[1] for channel in difference.getextrema()),
            "meanChannelDifference": stats.mean,
            "exactMatch": changed_pixels == 0,
        },
        "continuousRecording": {
            "path": "qa/V10-FINAL-CONTINUOUS-MOTION.mp4",
            "sha256": sha256(QA / "V10-FINAL-CONTINUOUS-MOTION.mp4"),
            "genuineContinuousCapture": True,
            "covers": [
                "ParamArmShoulder 0->1->0",
                "ParamArmElbow 0->1->0",
                "ParamArmWrist 0->1->0",
                "ParamV7ForearmRootTaper 0->1->0",
                "combined extrema and deterministic return",
            ],
        },
        "historicalStaticGif": {
            "path": "qa/cubism-v10-0-1-0.gif",
            "currentEvidence": False,
            "reason": "assembled still frames; retained only as historical evidence",
        },
        "fiveStateEvidence": [
            {
                "parameter": "ParamV7ForearmRootTaper",
                "value": 0.0,
                "path": "qa/cubism-36-taper-0-clean.png",
            },
            {
                "parameter": "ParamV7ForearmRootTaper",
                "value": 0.25,
                "path": "qa/cubism-35-taper-25-clean.png",
            },
            {
                "parameter": "ParamV7ForearmRootTaper",
                "value": 0.5,
                "path": "qa/cubism-34-taper-50-clean.png",
            },
            {
                "parameter": "ParamV7ForearmRootTaper",
                "value": 0.75,
                "path": "qa/cubism-33-taper-75-clean.png",
            },
            {
                "parameter": "ParamV7ForearmRootTaper",
                "value": 1.0,
                "path": "qa/cubism-32-taper-100-clean.png",
            },
        ],
        "keyformDecision": {
            "edited": True,
            "reason": (
                "The existing D_ForearmRootTaper was refined from a 2x2 to a "
                "2x6 Bezier grid and its maximum keyform now moves only the "
                "outer top control within the approved local band."
            ),
        },
    }
    (AUDIT / "v10-cubism-return-determinism.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    make_board(
        "V10-FINAL-USER-REVIEW.zh-CN.png",
        "小星单侧手臂 V10 中文视觉审查",
        "仅验证工程粗绑；不代表正式纹理、正式 PSD、完整 Cubism、Physics 或 Runtime。",
        [
            ("默认姿势", "cubism-39-final-default-clean.png"),
            ("肩部中间值", "cubism-40-shoulder-mid.png"),
            ("肩部最大值", "cubism-41-shoulder-max.png"),
            ("肘部中间值", "cubism-42-elbow-mid.png"),
            ("肘部最大值", "cubism-43-elbow-max.png"),
            ("腕部中间值", "cubism-44-wrist-mid.png"),
            ("腕部最大值", "cubism-45-wrist-max.png"),
            ("肘根 taper 50%", "cubism-34-taper-50-clean.png"),
            ("肘根 taper 100%", "cubism-32-taper-100-clean.png"),
        ],
    )
    make_board(
        "V10-FINAL-ENGINEERING-QA.zh-CN.png",
        "V10 工程结构与隔离检查",
        "网格、Deformer、参数、Draw Order 与隐藏覆盖证据；最终冻结仍等待用户批准。",
        [
            ("前臂 ArtMesh：10 顶点 / 10 三角形", "cubism-31-final-forearm-artmesh-wireframe.png"),
            ("taper 最大关键形与 2x6 网格", "cubism-37-taper-100-grid.png"),
            ("层级、参数、Draw Order", "cubism-49-final-hierarchy-parameters-draw-order.png"),
            ("袖子移开（可见性隔离）", "cubism-46-sleeve-moved-away-isolation.png"),
            ("前臂移开（可见性隔离）", "cubism-47-forearm-moved-away-isolation.png"),
            ("手部移开（可见性隔离）", "cubism-48-hand-moved-away-isolation.png"),
        ],
    )


if __name__ == "__main__":
    main()
