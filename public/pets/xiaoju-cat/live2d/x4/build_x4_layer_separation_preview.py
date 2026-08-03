from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
LIVE2D = ROOT.parent
QA_DIR = ROOT / "qa"
OVERVIEW = QA_DIR / "x4-layer-separation-overview.png"
EXPLODED = QA_DIR / "x4-expanded-hidden-fill-check.png"
CONTRACT = ROOT / "x4-layer-separation-contract.json"
REVIEW = ROOT / "X4-USER-VISUAL-REVIEW.md"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


FILL = {
    "fur": (246, 151, 37, 230),
    "fur2": (255, 181, 66, 230),
    "inner": (255, 210, 143, 235),
    "line": (118, 78, 35, 255),
    "eye": (255, 226, 160, 255),
    "black": (38, 36, 32, 255),
    "blue": (36, 105, 219, 240),
    "magenta": (215, 64, 179, 240),
    "soft": (124, 194, 183, 165),
    "hidden": (96, 185, 139, 135),
    "planet": (135, 195, 225, 220),
}


LAYERS = [
    {
        "id": "planet_back",
        "name": "星球后层",
        "parent": "PlanetRoot",
        "draw": 10,
        "hidden": "behind Xiaoju and planet rim",
        "source": "planet-scene-source",
    },
    {
        "id": "tail_base",
        "name": "尾根插口",
        "parent": "Pelvis",
        "draw": 90,
        "hidden": "large overlap under pelvis and tail_mid",
        "source": "X3 pelvis/tail continuity",
    },
    {
        "id": "tail_mid",
        "name": "尾中段",
        "parent": "TailRoot",
        "draw": 95,
        "hidden": "under tail_base and tail_tip",
        "source": "X3 tail",
    },
    {
        "id": "tail_tip",
        "name": "尾尖",
        "parent": "TailMid",
        "draw": 100,
        "hidden": "overlap into tail_mid",
        "source": "X3 tail",
    },
    {
        "id": "hind_leg_L",
        "name": "左后腿",
        "parent": "Pelvis",
        "draw": 150,
        "hidden": "hip/thigh fill under pelvis",
        "source": "X1/X3 hind chain",
    },
    {
        "id": "hind_leg_R",
        "name": "右后腿",
        "parent": "Pelvis",
        "draw": 151,
        "hidden": "hip/thigh fill under pelvis",
        "source": "X1/X3 hind chain",
    },
    {
        "id": "pelvis",
        "name": "骨盆/臀部",
        "parent": "BodyRoot",
        "draw": 210,
        "hidden": "under abdomen, legs, tail root",
        "source": "X3 body mass",
    },
    {
        "id": "abdomen",
        "name": "腹部软层",
        "parent": "BodyRoot",
        "draw": 220,
        "hidden": "under ribcage and pelvis",
        "source": "X3 body mass",
    },
    {
        "id": "ribcage",
        "name": "胸腔/躯干",
        "parent": "BodyRoot",
        "draw": 230,
        "hidden": "under neck, forelimbs, chest fur",
        "source": "X3 body mass",
    },
    {
        "id": "neck_chest_fur",
        "name": "颈胸毛软层",
        "parent": "Neck",
        "draw": 300,
        "hidden": "bridges head, neck, chest",
        "source": "X1 soft-tissue zone",
    },
    {
        "id": "forelimb_L",
        "name": "左前肢整链",
        "parent": "Scapula_L",
        "draw": 360,
        "hidden": "shoulder/elbow/wrist sleeve overlap",
        "source": "X2 cover chain",
    },
    {
        "id": "forelimb_R",
        "name": "右前肢整链",
        "parent": "Scapula_R",
        "draw": 361,
        "hidden": "shoulder/elbow/wrist sleeve overlap",
        "source": "X2 cover chain",
    },
    {
        "id": "head_base",
        "name": "头骨/脸底",
        "parent": "Neck",
        "draw": 500,
        "hidden": "complete underside under ears/muzzle/eyes",
        "source": "three-view-preview + X3 head",
    },
    {
        "id": "muzzle_jaw",
        "name": "口鼻/下颌",
        "parent": "Head",
        "draw": 540,
        "hidden": "under cheek fur and eye region",
        "source": "three-view-preview",
    },
    {
        "id": "cheek_fur_L",
        "name": "左脸颊毛",
        "parent": "Head",
        "draw": 560,
        "hidden": "overlaps head edge and neck",
        "source": "X1 soft zone",
    },
    {
        "id": "cheek_fur_R",
        "name": "右脸颊毛",
        "parent": "Head",
        "draw": 561,
        "hidden": "overlaps head edge and neck",
        "source": "X1 soft zone",
    },
    {
        "id": "ear_L",
        "name": "左耳根/耳面/耳尖",
        "parent": "Head",
        "draw": 620,
        "hidden": "ear root wedge under head fur",
        "source": "X1 ear anchors",
    },
    {
        "id": "ear_R",
        "name": "右耳根/耳面/耳尖",
        "parent": "Head",
        "draw": 621,
        "hidden": "ear root wedge under head fur",
        "source": "X1 ear anchors",
    },
    {
        "id": "eye_L_parts",
        "name": "左眼组",
        "parent": "EyeSocket_L",
        "draw": 700,
        "hidden": "socket mask, lids, pupil, highlight separated in X5",
        "source": "PRD X6.1",
    },
    {
        "id": "eye_R_parts",
        "name": "右眼组",
        "parent": "EyeSocket_R",
        "draw": 701,
        "hidden": "socket mask, lids, pupil, highlight separated in X5",
        "source": "PRD X6.1",
    },
    {
        "id": "whisker_L",
        "name": "左胡须束",
        "parent": "Muzzle",
        "draw": 760,
        "hidden": "root tucked under muzzle",
        "source": "three-view-preview",
    },
    {
        "id": "whisker_R",
        "name": "右胡须束",
        "parent": "Muzzle",
        "draw": 761,
        "hidden": "root tucked under muzzle",
        "source": "three-view-preview",
    },
    {
        "id": "planet_front",
        "name": "星球前景边缘/接触阴影",
        "parent": "PlanetRoot",
        "draw": 900,
        "hidden": "front occluder only, not anatomy",
        "source": "planet-scene-source",
    },
]


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], s: str, size: int, fill=(44, 40, 34, 255)) -> None:
    draw.text(xy, s, fill=fill, font=font(size))


def ellipse(draw: ImageDraw.ImageDraw, cx: int, cy: int, rx: int, ry: int, fill, outline=FILL["line"], width=3) -> None:
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill, outline=outline, width=width)


def poly(draw: ImageDraw.ImageDraw, pts: list[tuple[int, int]], fill, outline=FILL["line"], width=3) -> None:
    draw.polygon(pts, fill=fill, outline=outline)
    draw.line(pts + [pts[0]], fill=outline, width=width)


def line(draw: ImageDraw.ImageDraw, pts: list[tuple[int, int]], fill=FILL["line"], width=5) -> None:
    draw.line(pts, fill=fill, width=width, joint="curve")


def draw_layered_cat(draw: ImageDraw.ImageDraw, ox: int, oy: int, scale: float = 1.0, labels: bool = True) -> None:
    def p(x: float, y: float) -> tuple[int, int]:
        return (int(ox + x * scale), int(oy + y * scale))

    # Back and hidden-fill guides.
    ellipse(draw, *p(0, 88), int(168 * scale), int(112 * scale), FILL["hidden"], (64, 150, 112, 255), 2)
    ellipse(draw, *p(0, -38), int(138 * scale), int(166 * scale), FILL["hidden"], (64, 150, 112, 255), 2)

    # Tail.
    line(draw, [p(58, 160), p(206, 224), p(338, 172), p(296, 42)], FILL["fur"], int(28 * scale))
    line(draw, [p(58, 160), p(206, 224), p(338, 172), p(296, 42)], FILL["line"], int(4 * scale))
    for pt in (p(58, 160), p(206, 224), p(338, 172), p(296, 42)):
        ellipse(draw, pt[0], pt[1], int(10 * scale), int(10 * scale), FILL["soft"], (48, 126, 118, 255), 2)

    # Hind legs.
    for sx in (-1, 1):
        leg = [p(sx * 90, 124), p(sx * 188, 250), p(sx * 142, 388), p(sx * 222, 442)]
        line(draw, leg, FILL["fur2"], int(20 * scale))
        line(draw, leg, FILL["line"], int(3 * scale))
        ellipse(draw, leg[-1][0], leg[-1][1], int(42 * scale), int(22 * scale), FILL["inner"], FILL["line"], 2)

    # Body masses.
    ellipse(draw, *p(0, 104), int(136 * scale), int(150 * scale), FILL["fur"], FILL["line"], 4)
    ellipse(draw, *p(0, 28), int(118 * scale), int(148 * scale), FILL["fur2"], FILL["line"], 3)
    ellipse(draw, *p(0, -150), int(156 * scale), int(178 * scale), FILL["fur"], FILL["line"], 4)

    # Neck/chest soft layer.
    poly(draw, [p(-96, -18), p(-52, -84), p(0, -116), p(54, -84), p(98, -18), p(58, 44), p(0, 62), p(-58, 44)], FILL["soft"], (48, 126, 118, 255), 2)

    # Forelimbs.
    for sx, c in ((-1, FILL["blue"]), (1, FILL["magenta"])):
        chain = [p(sx * 118, -18), p(sx * 238, 20), p(sx * 314, 112), p(sx * 364, 186)]
        line(draw, chain, c, int(18 * scale))
        line(draw, chain, FILL["line"], int(3 * scale))
        for q in chain[:-1]:
            ellipse(draw, q[0], q[1], int(8 * scale), int(8 * scale), (255, 255, 255, 230), c, 2)
        ellipse(draw, chain[-1][0], chain[-1][1], int(34 * scale), int(24 * scale), FILL["inner"], FILL["line"], 2)

    # Ears.
    poly(draw, [p(-95, -300), p(-168, -430), p(-32, -282)], FILL["fur"], FILL["line"], 3)
    poly(draw, [p(-105, -314), p(-132, -376), p(-70, -300)], FILL["inner"], (164, 98, 62, 255), 2)
    poly(draw, [p(95, -300), p(168, -430), p(32, -282)], FILL["fur"], FILL["line"], 3)
    poly(draw, [p(105, -314), p(132, -376), p(70, -300)], FILL["inner"], (164, 98, 62, 255), 2)

    # Face details.
    ellipse(draw, *p(-62, -184), int(38 * scale), int(44 * scale), FILL["eye"], FILL["line"], 3)
    ellipse(draw, *p(62, -184), int(38 * scale), int(44 * scale), FILL["eye"], FILL["line"], 3)
    ellipse(draw, *p(-62, -184), int(15 * scale), int(23 * scale), FILL["black"], FILL["line"], 1)
    ellipse(draw, *p(62, -184), int(15 * scale), int(23 * scale), FILL["black"], FILL["line"], 1)
    draw.arc([p(-50, -148), p(50, -78)], 25, 155, fill=FILL["line"], width=max(2, int(3 * scale)))
    for sx in (-1, 1):
        for k in (-1, 0, 1):
            line(draw, [p(sx * 28, -112 + k * 10), p(sx * 128, -128 + k * 22)], FILL["line"], max(1, int(2 * scale)))

    if labels:
        labels_data = [
            ("ear_L/R", p(-206, -470)),
            ("head_base", p(-196, -240)),
            ("eye groups", p(90, -210)),
            ("neck_chest_fur", p(-140, -18)),
            ("ribcage/abdomen/pelvis", p(-140, 78)),
            ("forelimb_L/R", p(-410, 118)),
            ("hind_leg_L/R", p(-276, 360)),
            ("tail_base/mid/tip", p(170, 252)),
        ]
        for label, pos in labels_data:
            text(draw, pos, label, 18, (42, 70, 74, 255))


def draw_overview() -> None:
    img = Image.new("RGBA", (2400, 1600), (250, 250, 246, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 2400, 150], fill=(255, 244, 224, 255))
    text(draw, (42, 24), "X4 小橘语义分层预览", 40)
    text(draw, (42, 78), "从 X3 工程母版进入分层：显示真实层、隐藏补全、安全重叠和后续三角剖分边界预留。", 24, (105, 72, 36, 255))
    text(draw, (42, 112), "仍未进入 X5：本图不放正式 Delaunay、ArtMesh 或 Cubism 节点。", 20, (128, 50, 42, 255))

    draw_layered_cat(draw, 550, 805, 0.82, True)

    # Draw-order stack.
    x0, y0 = 1190, 210
    text(draw, (x0, y0 - 58), "绘制顺序 / Draw Order", 30)
    stack = sorted(LAYERS, key=lambda item: item["draw"])
    for i, layer in enumerate(stack):
        y = y0 + i * 48
        color = (246, 151, 37, 230)
        if "planet" in layer["id"]:
            color = FILL["planet"]
        elif "eye" in layer["id"]:
            color = FILL["eye"]
        elif "forelimb" in layer["id"]:
            color = FILL["blue"] if layer["id"].endswith("_L") else FILL["magenta"]
        elif "tail" in layer["id"]:
            color = (255, 181, 66, 230)
        elif "fur" in layer["id"]:
            color = FILL["soft"]
        draw.rounded_rectangle([x0, y, x0 + 860, y + 36], radius=7, fill=color, outline=(98, 88, 72, 255), width=1)
        text(draw, (x0 + 12, y + 5), f"{layer['draw']:03d}  {layer['id']}  {layer['name']}", 17, (35, 35, 32, 255))

    # Acceptance checklist.
    box = [42, 1378, 2358, 1548]
    draw.rounded_rectangle(box, radius=8, fill=(235, 247, 242, 255), outline=(106, 170, 145, 255), width=2)
    notes = [
        "X4 审核看点：每个活动区域都有独立层，关节附近有隐藏补全，前景遮挡与身体层分离。",
        "眼睛会在 X5/X6 拆成眼底、虹膜、瞳孔、高光、上下眼睑、眼眶遮罩；此处先作为眼组层边界。",
        "耳朵、脸颊毛、胸腹软层、尾根插口都已独立，以便后续设置主节点、顶点弹性和阻尼。",
        "如果 X4 通过，下一步才按真实层边界做三角剖分和 Layer-Mesh-Node 合同。",
    ]
    for i, note in enumerate(notes):
        text(draw, (70, 1404 + i * 34), note, 21, (36, 82, 68, 255))

    img.convert("RGB").save(OVERVIEW)


def draw_expanded() -> None:
    img = Image.new("RGBA", (2400, 1450), (250, 250, 246, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 2400, 140], fill=(255, 244, 224, 255))
    text(draw, (42, 24), "X4 展开检查：隐藏补全与安全重叠", 40)
    text(draw, (42, 82), "把头、前肢、后肢、尾巴和星球前景移开后，绿色区域表示必须补全的底层皮毛/肌肉包络。", 23, (105, 72, 36, 255))

    # Base ghost.
    draw_layered_cat(draw, 1200, 730, 0.62, False)
    text(draw, (1030, 170), "Rest recomposition ghost", 24, (70, 70, 64, 255))

    # Moved parts.
    panels = [
        ("Head moved", 260, 450),
        ("Forelimbs moved", 560, 980),
        ("Hind legs moved", 1340, 1040),
        ("Tail moved", 1820, 470),
    ]
    for label, x, y in panels:
        draw.rounded_rectangle([x - 180, y - 140, x + 180, y + 140], radius=8, fill=(255, 255, 255, 230), outline=(186, 178, 154, 255), width=2)
        if label != "Head moved":
            text(draw, (x - 150, y - 124), label, 22, (44, 40, 34, 255))

    # Head panel.
    ellipse(draw, 260, 450, 98, 110, FILL["fur"], FILL["line"], 4)
    poly(draw, [(205, 345), (170, 255), (255, 335)], FILL["fur"], FILL["line"], 2)
    poly(draw, [(315, 345), (350, 255), (265, 335)], FILL["fur"], FILL["line"], 2)
    ellipse(draw, 224, 430, 24, 32, FILL["eye"], FILL["line"], 2)
    ellipse(draw, 296, 430, 24, 32, FILL["eye"], FILL["line"], 2)
    draw.rounded_rectangle([88, 294, 224, 326], radius=5, fill=(255, 255, 255, 235), outline=(210, 202, 178, 255), width=1)
    text(draw, (96, 299), "Head moved", 22, (44, 40, 34, 255))
    text(draw, (105, 572), "neck/chest fill visible", 18, (38, 119, 86, 255))

    # Forelimb panel.
    for sx, c in ((-1, FILL["blue"]), (1, FILL["magenta"])):
        pts = [(560 + sx * 24, 930), (560 + sx * 96, 970), (560 + sx * 142, 1040), (560 + sx * 174, 1098)]
        line(draw, pts, c, 16)
        ellipse(draw, pts[-1][0], pts[-1][1], 28, 18, FILL["inner"], FILL["line"], 2)
    text(draw, (410, 1105), "shoulder/elbow/wrist sleeves", 18, (38, 119, 86, 255))

    # Hind leg panel.
    for sx in (-1, 1):
        pts = [(1340 + sx * 28, 990), (1340 + sx * 92, 1052), (1340 + sx * 70, 1128), (1340 + sx * 126, 1168)]
        line(draw, pts, FILL["fur2"], 18)
        ellipse(draw, pts[-1][0], pts[-1][1], 32, 18, FILL["inner"], FILL["line"], 2)
    text(draw, (1190, 1175), "hip/thigh fill under pelvis", 18, (38, 119, 86, 255))

    # Tail panel.
    line(draw, [(1780, 520), (1880, 566), (1992, 520), (1958, 416)], FILL["fur2"], 28)
    line(draw, [(1780, 520), (1880, 566), (1992, 520), (1958, 416)], FILL["line"], 4)
    text(draw, (1680, 610), "tail root socket overlap", 18, (38, 119, 86, 255))

    # Green hidden-fill arrows.
    arrow_color = (42, 142, 96, 255)
    for start, end in [
        ((360, 510), (1010, 515)),
        ((720, 1020), (1048, 748)),
        ((1460, 1040), (1265, 866)),
        ((1770, 520), (1318, 865)),
    ]:
        line(draw, [start, end], arrow_color, 4)
        draw.polygon([(end[0], end[1]), (end[0] - 18, end[1] - 4), (end[0] - 5, end[1] - 18)], fill=arrow_color)

    draw.rounded_rectangle([42, 1262, 2358, 1402], radius=8, fill=(238, 246, 247, 255), outline=(180, 210, 212, 255), width=2)
    notes = [
        "本图用于判断拆层是否会露洞：移开部件后，底层绿色区域必须存在连续皮毛，而不是靠默认遮挡糊过去。",
        "X4 通过后，X5 才会在每个真实图层边界内放辅助点并做三角剖分；当前只预留边界，不定网格。",
    ]
    for i, note in enumerate(notes):
        text(draw, (70, 1292 + i * 40), note, 22, (42, 68, 72, 255))

    img.convert("RGB").save(EXPLODED)


def write_contract() -> None:
    data = {
        "schemaVersion": 1,
        "stage": "X4-layer-separation",
        "status": "candidate-for-user-review",
        "x3ApprovalBasis": "User said the X3 likeness is not important now and explicitly requested entering layer separation: \"肯定是不像xiaoju的，但是我们应该进入分层了，不要管这个了\".",
        "sourceAuthority": [
            "three-view-preview.png",
            "live2d/x1/x1-canonical-body-contract.json",
            "live2d/x2/x2-pose-solve-contract.json",
            "live2d/x3/qa/x3-spread-pose-master-blockout.png",
        ],
        "gateBoundary": {
            "x4MayPassOnlyWithUserApproval": True,
            "x5Authorized": False,
            "allowed": [
                "semantic visual layer preview",
                "hidden-fill and overlap review",
                "draw-order proposal",
                "future mesh boundary readiness notes",
            ],
            "forbidden": [
                "formal Delaunay triangulation",
                "ArtMesh point placement",
                "Cubism Deformer editing",
                "runtime replacement",
            ],
        },
        "layers": LAYERS,
        "qa": {
            "overview": "live2d/x4/qa/x4-layer-separation-overview.png",
            "expandedHiddenFillCheck": "live2d/x4/qa/x4-expanded-hidden-fill-check.png",
            "review": "live2d/x4/X4-USER-VISUAL-REVIEW.md",
        },
        "nextGateIfApproved": "X5 layer-boundary triangulation and Layer-Mesh-Node contract",
    }
    CONTRACT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_review() -> None:
    layer_rows = "\n".join(
        f"| `{item['id']}` | {item['name']} | `{item['parent']}` | {item['hidden']} | {item['draw']} |"
        for item in sorted(LAYERS, key=lambda layer: layer["draw"])
    )
    REVIEW.write_text(
        f"""# X4 小橘语义分层视觉审核

> 状态：X4 分层候选已生成，等待用户视觉审核。  
> X4 只负责分层、隐藏补全、安全重叠和绘制顺序；不授权 X5 三角剖分、ArtMesh、Cubism 或运行时。

## 必看预览

- `qa/x4-layer-separation-overview.png`：分层总览、绘制顺序和审核重点。
- `qa/x4-expanded-hidden-fill-check.png`：把头、四肢、尾巴移开后的隐藏补全/安全重叠检查。
- `x4-layer-separation-contract.json`：机器可读分层合同。

## 图层候选

| ID | 内容 | 父区域 | 隐藏补全/重叠 | Draw |
| --- | --- | --- | --- | --- |
{layer_rows}

## 审核问题

1. 这些层是否足够支持之后的遮眼、目光、耳朵、尾巴和呼吸微动？
2. 头、前肢、后肢、尾巴移开后，绿色隐藏补全区是否足够，不会露洞？
3. 眼睛是否应该在 X4 就进一步拆成眼底/虹膜/瞳孔/高光/上下眼睑/眼眶遮罩，还是等 X5 合同里细化？
4. 星球前景遮挡与小橘身体是否分得够清楚？

## Gate 决策

- 说 `X4 通过`：授权进入 X5，在真实图层边界内做三角剖分、辅助点和 Layer-Mesh-Node 合同。
- 说 `X4 不通过` 或指出具体问题：继续只修 X4 分层，不进入 X5。
""",
        encoding="utf-8",
    )


def main() -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    draw_overview()
    draw_expanded()
    write_contract()
    write_review()
    print(OVERVIEW.as_posix())
    print(EXPLODED.as_posix())
    print(CONTRACT.as_posix())
    print(REVIEW.as_posix())


if __name__ == "__main__":
    main()
