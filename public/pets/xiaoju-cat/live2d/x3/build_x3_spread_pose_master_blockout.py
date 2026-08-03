from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
LIVE2D = ROOT.parent
QA_DIR = ROOT / "qa"
OUT_PNG = QA_DIR / "x3-spread-pose-master-blockout.png"
OUT_JSON = ROOT / "x3-spread-pose-master-blockout.json"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def ellipse(draw: ImageDraw.ImageDraw, cx: int, cy: int, rx: int, ry: int, fill, outline, width: int = 3) -> None:
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill, outline=outline, width=width)


def line(draw: ImageDraw.ImageDraw, pts: list[tuple[int, int]], fill, width: int = 6) -> None:
    draw.line(pts, fill=fill, width=width, joint="curve")


def joint(draw: ImageDraw.ImageDraw, p: tuple[int, int], fill) -> None:
    draw.ellipse([p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5], fill=fill)


def paw(draw: ImageDraw.ImageDraw, p: tuple[int, int], side: str) -> None:
    fill = (255, 183, 93)
    outline = (136, 82, 28)
    ellipse(draw, p[0], p[1], 26, 18, fill, outline, 3)
    dx = -18 if side == "L" else 18
    for i in (-1, 0, 1):
        ellipse(draw, p[0] + i * 9, p[1] - 13, 5, 5, (255, 218, 151), outline, 1)
    draw.line([(p[0], p[1] - 3), (p[0] + dx // 3, p[1] + 9)], fill=outline, width=2)


def ear(draw: ImageDraw.ImageDraw, base: tuple[int, int], tip: tuple[int, int], inner: tuple[int, int], mirror: int) -> None:
    outer = [
        (base[0] - 30 * mirror, base[1] + 14),
        tip,
        (base[0] + 32 * mirror, base[1] + 18),
    ]
    draw.polygon(outer, fill=(246, 146, 38), outline=(128, 80, 35))
    draw.line([outer[0], tip, outer[2]], fill=(128, 80, 35), width=3)
    inner_poly = [
        (base[0] - 12 * mirror, base[1] + 4),
        inner,
        (base[0] + 12 * mirror, base[1] + 9),
    ]
    draw.polygon(inner_poly, fill=(255, 198, 126), outline=(164, 98, 62))


def draw_cat_front(draw: ImageDraw.ImageDraw, ox: int, oy: int, title: str) -> None:
    orange = (246, 151, 37)
    line_color = (121, 78, 32)
    soft = (255, 206, 122)
    blue = (24, 96, 200)
    mag = (210, 52, 168)

    draw.text((ox - 150, oy - 310), title, fill=(44, 40, 34), font=font(28))
    ellipse(draw, ox, oy - 90, 155, 190, orange, line_color, 5)
    ellipse(draw, ox, oy + 118, 138, 162, orange, line_color, 5)
    ellipse(draw, ox, oy + 30, 120, 160, (248, 164, 47), line_color, 3)
    ellipse(draw, ox, oy + 164, 110, 112, (246, 151, 37), line_color, 3)

    ear(draw, (ox - 88, oy - 255), (ox - 150, oy - 372), (ox - 113, oy - 300), -1)
    ear(draw, (ox + 88, oy - 255), (ox + 150, oy - 372), (ox + 113, oy - 300), 1)

    for sx, color in ((-1, blue), (1, mag)):
        eye = (ox + sx * 62, oy - 128)
        ellipse(draw, eye[0], eye[1], 34, 42, soft, line_color, 3)
        ellipse(draw, eye[0], eye[1], 15, 22, (36, 35, 32), None if False else line_color, 2)
        draw.arc([eye[0] - 46, eye[1] - 54, eye[0] + 46, eye[1] + 40], 205, 335, fill=(236, 96, 54), width=4)
        draw.arc([eye[0] - 52, eye[1] - 62, eye[0] + 52, eye[1] + 48], 200, 340, fill=color, width=3)

    draw.arc([ox - 46, oy - 96, ox + 46, oy - 22], 30, 150, fill=line_color, width=3)
    draw.arc([ox - 38, oy - 62, ox + 38, oy + 10], 25, 155, fill=line_color, width=3)

    # Spread forelimbs: shoulder -> elbow -> wrist -> paw.
    for sx, color in ((-1, blue), (1, mag)):
        shoulder = (ox + sx * 124, oy + 8)
        elbow = (ox + sx * 238, oy + 36)
        wrist = (ox + sx * 310, oy + 116)
        fpaw = (ox + sx * 354, oy + 184)
        line(draw, [shoulder, elbow, wrist, fpaw], color, 8)
        for p in (shoulder, elbow, wrist):
            joint(draw, p, color)
        paw(draw, fpaw, "L" if sx < 0 else "R")
        draw.line([shoulder, (ox + sx * 92, oy - 15)], fill=(255, 204, 134), width=18)

    for sx in (-1, 1):
        hip = (ox + sx * 92, oy + 178)
        knee = (ox + sx * 178, oy + 285)
        hock = (ox + sx * 136, oy + 406)
        hpaw = (ox + sx * 206, oy + 454)
        line(draw, [hip, knee, hock, hpaw], (108, 96, 78), 8)
        for p in (hip, knee, hock):
            joint(draw, p, (108, 96, 78))
        paw(draw, hpaw, "L" if sx < 0 else "R")

    # Tail root visible as future hidden-area reference.
    line(draw, [(ox + 36, oy + 236), (ox + 190, oy + 280), (ox + 282, oy + 212), (ox + 256, oy + 108)], orange, 24)
    draw.line([(ox + 36, oy + 236), (ox + 190, oy + 280), (ox + 282, oy + 212), (ox + 256, oy + 108)], fill=line_color, width=4)

    for p, label in [
        ((ox - 124, oy + 8), "shoulder"),
        ((ox - 238, oy + 36), "elbow"),
        ((ox - 310, oy + 116), "wrist"),
        ((ox + 36, oy + 236), "tail root"),
    ]:
        draw.text((p[0] + 8, p[1] - 24), label, fill=(70, 70, 64), font=font(13))


def draw_cat_side(draw: ImageDraw.ImageDraw, ox: int, oy: int, title: str) -> None:
    orange = (246, 151, 37)
    line_color = (121, 78, 32)
    draw.text((ox - 150, oy - 310), title, fill=(44, 40, 34), font=font(28))
    ellipse(draw, ox - 38, oy - 104, 146, 180, orange, line_color, 5)
    ellipse(draw, ox + 38, oy + 108, 178, 148, orange, line_color, 5)
    ear(draw, (ox - 88, oy - 258), (ox - 126, oy - 376), (ox - 105, oy - 302), -1)
    ear(draw, (ox + 8, oy - 258), (ox + 0, oy - 372), (ox - 1, oy - 300), 1)
    ellipse(draw, ox - 130, oy - 132, 28, 38, (255, 206, 122), line_color, 3)
    ellipse(draw, ox - 130, oy - 132, 12, 20, (36, 35, 32), line_color, 2)

    fore = [(ox - 18, oy + 10), (ox - 156, oy + 54), (ox - 228, oy + 146), (ox - 276, oy + 220)]
    line(draw, fore, (24, 96, 200), 8)
    for p in fore[:-1]:
        joint(draw, p, (24, 96, 200))
    paw(draw, fore[-1], "L")

    hind = [(ox + 86, oy + 166), (ox + 202, oy + 278), (ox + 152, oy + 402), (ox + 234, oy + 454)]
    line(draw, hind, (108, 96, 78), 8)
    for p in hind[:-1]:
        joint(draw, p, (108, 96, 78))
    paw(draw, hind[-1], "L")

    line(draw, [(ox + 172, oy + 132), (ox + 330, oy + 90), (ox + 374, oy - 48), (ox + 290, oy - 146)], orange, 24)
    draw.line([(ox + 172, oy + 132), (ox + 330, oy + 90), (ox + 374, oy - 48), (ox + 290, oy - 146)], fill=line_color, width=4)
    draw.text((ox + 162, oy + 150), "tail root visible", fill=(70, 70, 64), font=font(13))


def draw_cat_back(draw: ImageDraw.ImageDraw, ox: int, oy: int, title: str) -> None:
    orange = (246, 151, 37)
    line_color = (121, 78, 32)
    draw.text((ox - 150, oy - 310), title, fill=(44, 40, 34), font=font(28))
    ellipse(draw, ox, oy - 92, 152, 184, orange, line_color, 5)
    ellipse(draw, ox, oy + 128, 148, 164, orange, line_color, 5)
    ear(draw, (ox - 92, oy - 258), (ox - 156, oy - 374), (ox - 116, oy - 304), -1)
    ear(draw, (ox + 92, oy - 258), (ox + 156, oy - 374), (ox + 116, oy - 304), 1)
    draw.arc([ox - 86, oy - 130, ox + 86, oy - 40], 35, 145, fill=(200, 112, 42), width=4)

    for sx, color in ((-1, (24, 96, 200)), (1, (210, 52, 168))):
        shoulder = (ox + sx * 120, oy + 6)
        elbow = (ox + sx * 238, oy + 38)
        wrist = (ox + sx * 310, oy + 124)
        fpaw = (ox + sx * 350, oy + 196)
        line(draw, [shoulder, elbow, wrist, fpaw], color, 8)
        for p in (shoulder, elbow, wrist):
            joint(draw, p, color)
        paw(draw, fpaw, "L" if sx < 0 else "R")

    for sx in (-1, 1):
        hip = (ox + sx * 94, oy + 176)
        knee = (ox + sx * 180, oy + 288)
        hock = (ox + sx * 138, oy + 410)
        hpaw = (ox + sx * 210, oy + 456)
        line(draw, [hip, knee, hock, hpaw], (108, 96, 78), 8)
        for p in (hip, knee, hock):
            joint(draw, p, (108, 96, 78))
        paw(draw, hpaw, "L" if sx < 0 else "R")

    line(draw, [(ox, oy + 224), (ox - 126, oy + 312), (ox - 250, oy + 280), (ox - 302, oy + 174)], orange, 24)
    draw.line([(ox, oy + 224), (ox - 126, oy + 312), (ox - 250, oy + 280), (ox - 302, oy + 174)], fill=line_color, width=4)
    draw.text((ox - 64, oy + 236), "tail root", fill=(70, 70, 64), font=font(13))


def main() -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    W, H = 2200, 1320
    img = Image.new("RGB", (W, H), (250, 250, 246))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 150], fill=(255, 245, 226))
    draw.text((42, 28), "X3 Spread-Pose / Large-Character Three-View Master Blockout", fill=(42, 36, 28), font=font(34))
    draw.text((42, 82), "Candidate construction plate only: complete body continuity before X4 layers. Not layer separation, not ArtMesh.", fill=(120, 72, 26), font=font(22))
    draw.text((42, 116), "Derived from approved X1 body topology + X2 support/cover gate. User must approve X3 before formal layer images.", fill=(70, 70, 64), font=font(17))

    draw_cat_front(draw, 370, 650, "FRONT spread")
    draw_cat_side(draw, 1100, 650, "SIDE spread")
    draw_cat_back(draw, 1830, 650, "BACK spread")

    draw.rounded_rectangle([42, 1170, W - 42, H - 38], radius=8, fill=(238, 246, 247), outline=(190, 214, 218), width=2)
    notes = [
        "X3 review focus: same Xiaoju identity, same segment lengths, complete hidden anatomy, safe overlaps for future layers.",
        "Still forbidden: final layer images, formal Delaunay/ArtMesh, PSD, Cubism, runtime.",
        "If this master passes, X4 may generate detailed semantic layers from this approved master only.",
    ]
    for i, note in enumerate(notes):
        draw.text((70, 1192 + i * 32), note, fill=(42, 68, 72), font=font(18))

    img.save(OUT_PNG)
    meta = {
        "schemaVersion": 1,
        "stage": "X3-spread-pose-master",
        "status": "candidate-for-user-review",
        "artifact": "live2d/x3/qa/x3-spread-pose-master-blockout.png",
        "type": "construction-blockout-not-final-layer-art",
        "sourceAuthority": [
            "three-view-preview.png",
            "live2d/x1/x1-canonical-body-contract.json",
            "live2d/x2/x2-pose-solve-contract.json",
            "live2d/x3/x3-spread-pose-master-contract.json"
        ],
        "gateBoundary": {
            "x3ApprovedByUser": False,
            "x4Authorized": False,
            "forbidden": [
                "formal layer images",
                "formal triangulation",
                "ArtMesh",
                "PSD",
                "Cubism"
            ]
        }
    }
    OUT_JSON.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT_PNG.as_posix())
    print(OUT_JSON.as_posix())


if __name__ == "__main__":
    main()
