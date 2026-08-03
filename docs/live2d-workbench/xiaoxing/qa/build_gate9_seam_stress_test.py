from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "source" / "masters" / "gate3-color-target-v1.png"
HIDDEN = ROOT / "qa" / "hidden-fill-candidates.json"
DRAFT_DIR = ROOT / "qa" / "draft-material-layers"


def font(size: int):
    for path in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def shift(image: Image.Image, dx: int, dy: int = 0) -> Image.Image:
    out = Image.new("RGBA", image.size, (0, 0, 0, 0))
    out.alpha_composite(image, (dx, dy))
    return out


def checker(size):
    out = Image.new("RGBA", size, (235, 235, 235, 255))
    d = ImageDraw.Draw(out)
    for yy in range(0, size[1], 16):
        for xx in range(0, size[0], 16):
            if (xx // 16 + yy // 16) % 2:
                d.rectangle((xx, yy, xx + 15, yy + 15), fill=(250, 250, 250, 255))
    return out


def main() -> None:
    source = Image.open(MASTER).convert("RGBA")
    hidden = json.loads(HIDDEN.read_text(encoding="utf-8"))
    rows = []
    results = []
    for entry in hidden["entries"]:
        layer_id = entry["id"]
        draft_id = layer_id if (DRAFT_DIR / f"{layer_id}.png").exists() else ("torso_tshirt_core" if layer_id == "torso_tshirt_core_hem" else layer_id)
        draft_path = DRAFT_DIR / f"{draft_id}.png"
        if not draft_path.exists():
            results.append({"id": layer_id, "status": "missing_visible_draft"})
            continue
        candidate = Image.open(ROOT / entry["path"]).convert("RGBA")
        active = Image.open(draft_path).convert("RGBA")
        target = tuple(entry["target"])
        group = "头发" if "hair" in layer_id else "袖臂" if "sleeve" in layer_id else "衣身" if "torso" in layer_id else "裙子" if "skirt" in layer_id else "腿袜"
        dx = 8 if group == "头发" else 5 if group in ("衣身", "裙子") else 4
        panels = []
        coverage = []
        crop = (max(0, target[0] - 28), max(0, target[1] - 28), min(512, target[2] + 28), min(1086, target[3] + 28))
        for label, delta in (("左极限", -dx), ("原位", 0), ("右极限", dx)):
            scene = checker((512, 1086))
            scene.alpha_composite(candidate)
            scene.alpha_composite(shift(active, delta))
            coverage_alpha = ImageChops.lighter(candidate.getchannel("A"), shift(active, delta).getchannel("A"))
            alpha = coverage_alpha.crop(target)
            # Candidate fill is intentionally conservative; any transparent pixel in the target is a fail.
            hist = alpha.histogram()
            uncovered = sum(hist[:255])
            coverage.append({"label": label, "uncoveredPixels": uncovered, "targetPixels": (target[2] - target[0]) * (target[3] - target[1])})
            crop_img = scene.crop(crop).resize((340, 170))
            cd = ImageDraw.Draw(crop_img)
            cd.text((8, 8), label, fill=(35, 70, 135), font=font(15), stroke_width=2, stroke_fill="white")
            panels.append(crop_img.convert("RGB"))
        rows.append((layer_id, group, panels, coverage))
        results.append({"id": layer_id, "group": group, "shiftPixels": dx, "coverage": coverage, "status": "pass" if all(x["uncoveredPixels"] == 0 for x in coverage) else "fail"})

    board = Image.new("RGB", (1600, len(rows) * 220 + 100), "white")
    d = ImageDraw.Draw(board)
    d.text((24, 18), "小星 Gate 9 接缝移动压力测试", fill=(25, 25, 30), font=font(26))
    d.text((24, 55), "在首版幅度内移动活动层；棋盘格只用于暴露透明露白，不代表最终运行背景。", fill=(55, 75, 105), font=font(17))
    y = 95
    for layer_id, group, panels, _coverage in rows:
        d.text((24, y + 58), f"{layer_id}（{group}）", fill=(30, 75, 135), font=font(17))
        x = 320
        for panel in panels:
            board.paste(panel, (x, y))
            x += 360
        y += 220
    qa_path = ROOT / "qa" / "gate9-seam-stress-contact-sheet.png"
    board.save(qa_path, quality=95)
    report = {"status": "self_review_passed" if all(x.get("status") == "pass" for x in results) else "fail", "rows": results, "rules": {"candidateOnly": True, "testUses首版移动幅度": True}}
    (ROOT / "audit" / "gate9-seam-stress-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(qa_path)


if __name__ == "__main__":
    main()
