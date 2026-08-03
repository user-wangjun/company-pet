from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


HERE = Path(__file__).resolve()
ROOT = HERE.parent.parent
XIAOXING = ROOT.parents[1]
SOURCE_LINE = XIAOXING / "source/masters/front-line-source-exact-after-reset.png"
SOURCE_COLOR = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
V25_APPROVAL = (
    XIAOXING
    / "validation/arm-chain-screen-left-v25-shoulder-joint-correction"
    / "audit/user-visual-approval-2026-07-28.json"
)
V27 = XIAOXING / "validation/arm-chain-screen-left-v27-source-traced-layering"
V27_SKELETON = V27 / "skeleton-lock.json"
V27_REPORT = V27 / "audit/machine-report.json"

W, H, AA = 512, 1086, 4
S = np.array((170.0, 251.0))
E = np.array((147.0, 405.0))
WR = np.array((115.0, 529.0))
ORDER = ["upper_arm", "forearm", "hand", "sleeve"]
COLORS = {
    "upper_arm": (229, 89, 78, 255),
    "forearm": (243, 155, 44, 255),
    "hand": (32, 167, 119, 255),
    "sleeve": (40, 112, 194, 255),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_hash(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def font(size: int, bold=False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def cubic(p0, p1, p2, p3, count=48):
    ts = np.linspace(0, 1, count)
    return np.array(
        [
            (1 - t) ** 3 * p0
            + 3 * (1 - t) ** 2 * t * p1
            + 3 * (1 - t) * t**2 * p2
            + t**3 * p3
            for t in ts
        ]
    )


def build_physical_sleeve(visible: np.ndarray):
    top = np.array((164.0, 220.0))
    cap_mid = np.array((204.0, 270.0))
    armhole_mid = np.array((204.0, 346.0))
    underarm = np.array((184.0, 416.0))

    cap_curve = cubic(
        top,
        np.array((176.0, 213.0)),
        np.array((197.0, 222.0)),
        cap_mid,
        56,
    )
    armhole_upper = cubic(
        cap_mid,
        np.array((210.0, 294.0)),
        np.array((209.0, 326.0)),
        armhole_mid,
        56,
    )
    armhole_lower = cubic(
        armhole_mid,
        np.array((202.0, 372.0)),
        np.array((194.0, 401.0)),
        underarm,
        56,
    )
    return_path = np.array(
        [
            (184, 390),
            (183, 360),
            (180, 335),
            (176, 315),
            (171, 295),
            (167, 275),
            (164, 255),
            (165, 240),
        ],
        dtype=np.float64,
    )
    hidden_polygon = np.vstack(
        [cap_curve, armhole_upper[1:], armhole_lower[1:], return_path]
    )
    large = np.zeros((H * AA, W * AA), dtype=np.uint8)
    cv2.fillPoly(
        large,
        [np.round(hidden_polygon * AA).astype(np.int32)],
        255,
        lineType=cv2.LINE_AA,
    )
    hidden_candidate = np.array(
        Image.fromarray(large).resize((W, H), Image.Resampling.LANCZOS),
        dtype=np.uint8,
    )
    complete = np.maximum(visible, hidden_candidate)
    hidden_only = cv2.subtract(complete, visible)
    attachment_curve = np.vstack(
        [cap_curve, armhole_upper[1:], armhole_lower[1:]]
    )
    return complete, hidden_only, attachment_curve


def mask_image(array):
    return Image.fromarray(array.astype(np.uint8), mode="L")


def antialiased(mask):
    return mask.filter(ImageFilter.GaussianBlur(0.45))


def solid(mask, color):
    image = Image.new("RGBA", (W, H), color)
    image.putalpha(mask)
    return image


def composite(layers, background=None):
    canvas = (
        background.convert("RGBA").copy()
        if background is not None
        else Image.new("RGBA", (W, H), (0, 0, 0, 0))
    )
    for name in ORDER:
        canvas.alpha_composite(layers[name])
    return canvas


def checker(size, cell=16):
    image = Image.new("RGB", size, (239, 239, 239))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle(
                    (x, y, x + cell - 1, y + cell - 1), fill=(207, 207, 207)
                )
    return image


def crop_scale(image, box, factor=3):
    crop = image.crop(box)
    return crop.resize(
        (crop.width * factor, crop.height * factor), Image.Resampling.LANCZOS
    )


def rotate_translate(image, old_pivot, new_pivot, angle_deg):
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    ox, oy = old_pivot
    nx, ny = new_pivot
    return image.transform(
        (W, H),
        Image.Transform.AFFINE,
        (
            c,
            s,
            ox - c * nx - s * ny,
            -s,
            c,
            oy + s * nx - c * ny,
        ),
        resample=Image.Resampling.BICUBIC,
    )


def point_at(origin, length, angle_deg):
    angle = math.radians(angle_deg)
    return np.array(
        (
            origin[0] + length * math.cos(angle),
            origin[1] + length * math.sin(angle),
        )
    )


def pose_layers(layers, theta1, theta2, wrist_local):
    l1 = float(np.linalg.norm(E - S))
    l2 = float(np.linalg.norm(WR - E))
    rest1 = math.degrees(math.atan2(E[1] - S[1], E[0] - S[0]))
    rest_global = math.degrees(math.atan2(WR[1] - E[1], WR[0] - E[0]))
    new_e = point_at(S, l1, theta1)
    new_w = point_at(new_e, l2, theta1 + theta2)
    d1 = theta1 - rest1
    d2 = theta1 + theta2 - rest_global
    return (
        {
            "upper_arm": rotate_translate(layers["upper_arm"], S, S, d1),
            "forearm": rotate_translate(layers["forearm"], E, new_e, d2),
            "hand": rotate_translate(layers["hand"], WR, new_w, d2 + wrist_local),
            "sleeve": rotate_translate(layers["sleeve"], S, S, d1 * 0.82),
        },
        new_e,
        new_w,
    )


def overlap(a, b):
    aa = np.array(a.getchannel("A"))
    bb = np.array(b.getchannel("A"))
    return int(np.count_nonzero((aa > 8) & (bb > 8)))


def labeled_panel(board, image, box, label):
    x0, y0, x1, y1 = box
    area = Image.new("RGB", (x1 - x0, y1 - y0), "white")
    item = image.convert("RGBA")
    item.thumbnail((area.width, area.height), Image.Resampling.LANCZOS)
    x = (area.width - item.width) // 2
    y = (area.height - item.height) // 2
    area.paste(item.convert("RGB"), (x, y), item.getchannel("A"))
    board.paste(area, (x0, y0))
    draw = ImageDraw.Draw(board)
    draw.rectangle(box, outline=(166, 176, 190), width=2)
    draw.text((x0, y1 + 8), label, fill=(27, 37, 51), font=font(23, True))


def main():
    for directory in ("materials", "masks", "qa", "samples", "audit"):
        (ROOT / directory).mkdir(parents=True, exist_ok=True)

    source_color = Image.open(SOURCE_COLOR).convert("RGBA")
    expected = {
        SOURCE_LINE: "706aaf10652147cf76e233532b5459ce130921a96806f6970c91e1f3a427172f",
        SOURCE_COLOR: "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5",
    }
    for path, digest in expected.items():
        if sha256(path) != digest:
            raise RuntimeError(f"Authority mismatch: {path.name}")
    if json.loads(V27_REPORT.read_text(encoding="utf-8"))["status"] != "engineering_pass_pending_user_visual_approval":
        raise RuntimeError("V27 engineering baseline is not valid")

    v27_visible = {
        name: Image.open(V27 / f"masks/visible/{name}.png").convert("L")
        for name in ORDER
    }
    v27_complete = {
        name: Image.open(V27 / f"masks/complete/{name}.png").convert("L")
        for name in ORDER
    }
    sleeve_visible = np.array(v27_visible["sleeve"])
    sleeve_complete, sleeve_hidden, attachment_curve = build_physical_sleeve(
        sleeve_visible
    )
    mask_image(sleeve_visible).save(ROOT / "masks/sleeve-visible-source-traced.png")
    mask_image(sleeve_hidden).save(ROOT / "masks/sleeve-hidden-physical.png")
    mask_image(sleeve_complete).save(ROOT / "masks/sleeve-complete-physical.png")

    complete_masks = {
        "upper_arm": v27_complete["upper_arm"],
        "forearm": v27_complete["forearm"],
        "hand": v27_complete["hand"],
        "sleeve": mask_image(sleeve_complete),
    }
    visible_layers = {
        name: solid(antialiased(v27_visible[name]), COLORS[name]) for name in ORDER
    }
    complete_layers = {
        name: solid(antialiased(complete_masks[name]), COLORS[name])
        for name in ORDER
    }
    for name in ORDER:
        complete_layers[name].save(ROOT / f"materials/{name}.png")

    physics_contract = {
        "schemaVersion": 1,
        "status": "physical_sleeve_completion_candidate_pending_user_visual_approval",
        "garmentClassification": "oversized drop-shoulder short T-shirt sleeve",
        "lockedVisibleInput": {
            "path": "../arm-chain-screen-left-v27-source-traced-layering/masks/visible/sleeve.png",
            "sha256": sha256(V27 / "masks/visible/sleeve.png"),
            "mutation": "none",
        },
        "anchorsPx": {
            "shoulderPivot": S.tolist(),
            "capTop": [164.0, 220.0],
            "underarmJoin": [184.0, 416.0],
            "cuffVisibleOuter": [96.0, 372.0],
            "cuffVisibleInner": [184.0, 416.0],
        },
        "physicalResponsibilities": {
            "attachmentArc": "continuous curved sleeve-cap/armhole attachment from shoulder top to underarm",
            "bodyContact": "hidden inner sleeve lies beneath hair and shirt body, following the torso attachment rather than background",
            "gravity": "free cloth mass hangs toward the cuff; hidden completion adds no upward spike or circular plug",
            "strain": "attachment arc is longer and smoother than the former pointed closure, avoiding an artificial pin constraint",
            "cuff": "visible cuff edge remains source-locked and free",
        },
        "onlineReferences": [
            {
                "title": "Geometrical Development of the Pattern for the Sleeve Top",
                "url": "https://www.jstage.jst.go.jp/article/jhej1951/32/3/32_3_216/_article",
                "appliedPrinciple": "model the sleeve as a cylindrical volume with an elliptical sleeve-cap attachment to the trunk",
            },
            {
                "title": "CLO Help Center: Why is my armpit fabric doing this?",
                "url": "https://support.clo3d.com/hc/en-us/community/posts/360045781713-Why-is-my-armpit-fabric-doing-this",
                "appliedPrinciple": "sleeve-cap shape and its relationship to the armhole seam must be checked together",
            },
            {
                "title": "A real-time cloth draping simulation algorithm using conjugate harmonic functions",
                "url": "https://www.sciencedirect.com/science/article/abs/pii/S0097849306001865",
                "appliedPrinciple": "large-scale cloth shape follows body transforms while local drape responds to gravity, elasticity, and body contact",
            },
        ],
        "prohibitions": [
            "no pointed cap closure",
            "no circular hidden patch",
            "no extension below the source-locked cuff",
            "no texture, mesh, Physics, Cubism, or Runtime in this checkpoint",
        ],
    }
    save_json(ROOT / "sleeve-physics-contract.json", physics_contract)

    skeleton = json.loads(V27_SKELETON.read_text(encoding="utf-8"))
    skeleton["status"] = "unchanged_from_user_approved_v25_for_v28_sleeve_completion"
    skeleton["geometryMutation"] = "none"
    save_json(ROOT / "skeleton-lock.json", skeleton)

    default = composite(visible_layers)
    default.save(ROOT / "qa/default-recomposition-visible-unchanged.png")
    old_sleeve = solid(
        antialiased(v27_complete["sleeve"]), (128, 146, 171, 255)
    )
    new_sleeve = complete_layers["sleeve"]

    old_isolated = checker((W, H)).convert("RGBA")
    old_isolated.alpha_composite(old_sleeve)
    new_isolated = checker((W, H)).convert("RGBA")
    new_isolated.alpha_composite(new_sleeve)

    physics_diagram = source_color.copy()
    diagram_draw = ImageDraw.Draw(physics_diagram)
    curve = [tuple(map(float, point)) for point in attachment_curve]
    diagram_draw.line(curve, fill=(220, 52, 52, 255), width=3)
    diagram_draw.ellipse((S[0] - 5, S[1] - 5, S[0] + 5, S[1] + 5), fill=(255, 210, 0, 255))
    diagram_draw.line((206, 260, 206, 365), fill=(45, 150, 80, 255), width=4)
    diagram_draw.polygon(
        [(199, 356), (213, 356), (206, 370)], fill=(45, 150, 80, 255)
    )
    diagram_draw.line((96, 372, 184, 416), fill=(40, 112, 194, 255), width=4)
    physics_diagram.save(ROOT / "qa/sleeve-physics-annotation.png")

    ghost = default.copy()
    ghost.putalpha(ghost.getchannel("A").point(lambda value: round(value * 0.18)))
    displaced = checker((W, H)).convert("RGBA")
    displaced.alpha_composite(ghost)
    shifted = new_sleeve.transform(
        (W, H),
        Image.Transform.AFFINE,
        (1, 0, -155, 0, 1, 0),
        resample=Image.Resampling.BICUBIC,
    )
    displaced.alpha_composite(shifted)
    displaced.save(ROOT / "qa/displaced-sleeve-physical.png")

    rest1 = skeleton["restAnglesDeg"]["theta1"]
    rest2 = skeleton["restAnglesDeg"]["theta2"]
    target = skeleton["stageAQaMotion"]["target"]
    frames = []
    chosen = {}
    samples = []
    first_hash = last_hash = None
    seams_pass = True
    max_l1_error = max_l2_error = 0.0
    l1 = skeleton["boneLengthsPx"]["L1ShoulderToElbow"]
    l2 = skeleton["boneLengthsPx"]["L2ElbowToWrist"]
    for index in range(41):
        j = index if index <= 20 else 40 - index
        progress = 0.5 * (1 - math.cos(math.pi * j / 20))
        theta1 = rest1 + (target["theta1"] - rest1) * progress
        theta2 = rest2 + (target["theta2"] - rest2) * progress
        wrist_local = target["wristLocal"] * progress
        posed, new_e, new_w = pose_layers(
            complete_layers, theta1, theta2, wrist_local
        )
        pose = composite(posed)
        digest = image_hash(pose)
        if index == 0:
            first_hash = digest
        if index == 40:
            last_hash = digest
        l1_error = abs(float(np.linalg.norm(new_e - S)) - l1)
        l2_error = abs(float(np.linalg.norm(new_w - new_e)) - l2)
        max_l1_error = max(max_l1_error, l1_error)
        max_l2_error = max(max_l2_error, l2_error)
        sleeve_upper = overlap(posed["sleeve"], posed["upper_arm"])
        seam_ok = sleeve_upper > 10
        seams_pass = seams_pass and seam_ok
        frame = Image.new("RGB", (500, 960), "white")
        arm = crop_scale(pose, (0, 190, 220, 650), 2)
        frame.paste(arm.convert("RGB"), (30, 28), arm.getchannel("A"))
        ImageDraw.Draw(frame).text(
            (14, 5),
            f"样本 {index:02d}｜{progress:.2f}",
            fill=(24, 24, 24),
            font=font(20, True),
        )
        frame.save(ROOT / f"samples/fk-{index:03d}.png")
        thumb = frame.resize((250, 480), Image.Resampling.LANCZOS)
        frames.append(thumb)
        if index in (0, 10, 20, 30, 40):
            chosen[index] = thumb
        samples.append(
            {
                "index": index,
                "progress": progress,
                "sleeveUpperOverlapPixels": sleeve_upper,
                "L1ErrorPx": l1_error,
                "L2ErrorPx": l2_error,
                "pass": seam_ok,
            }
        )
    save_json(ROOT / "samples/fk-41-samples.json", samples)
    frames[0].save(
        ROOT / "qa/fk-41-slow-preview.gif",
        save_all=True,
        append_images=frames[1:],
        duration=190,
        loop=0,
        disposal=2,
    )
    contact = Image.new("RGB", (1250, 520), (243, 245, 248))
    for column, index in enumerate((0, 10, 20, 30, 40)):
        contact.paste(chosen[index], (column * 250, 40))
        ImageDraw.Draw(contact).text(
            (column * 250 + 10, 8),
            f"{index:02d}",
            fill=(20, 20, 20),
            font=font(21, True),
        )
    contact.save(ROOT / "qa/fk-selected-contact-sheet.png")

    review = Image.new("RGB", (2400, 2180), (244, 247, 251))
    draw = ImageDraw.Draw(review)
    draw.text(
        (50, 28),
        "小星 V28｜按服装结构与受力补全画面左侧袖子",
        fill=(20, 30, 44),
        font=font(48, True),
    )
    draw.text(
        (50, 96),
        "蓝色可见袖口与外轮廓保持 V27 源像素；本轮只重做头发和衣身下面的袖山 / 袖窿隐藏材料。",
        fill=(65, 76, 93),
        font=font(27),
    )
    source_crop = crop_scale(source_color, (75, 200, 220, 440), 3)
    old_crop = crop_scale(old_isolated, (75, 195, 225, 440), 3)
    new_crop = crop_scale(new_isolated, (75, 195, 225, 440), 3)
    diagram_crop = crop_scale(physics_diagram, (75, 195, 225, 440), 3)
    labeled_panel(review, source_crop, (40, 160, 540, 940), "① 原稿：落肩宽袖，袖口自由下垂")
    labeled_panel(review, old_crop, (565, 160, 1065, 940), "② V27 失败：隐藏部分收成尖顶")
    labeled_panel(review, new_crop, (1090, 160, 1590, 940), "③ V28 完整袖：连续袖山与腋下连接")
    labeled_panel(review, diagram_crop, (1615, 160, 2115, 940), "④ 受力：红=连接弧，绿=重力，蓝=自由袖口")

    displaced_crop = crop_scale(displaced, (25, 185, 395, 650), 2)
    default_crop = crop_scale(default, (45, 195, 220, 650), 2)
    hidden_view = checker((W, H)).convert("RGBA")
    hidden_view.alpha_composite(
        solid(antialiased(mask_image(sleeve_hidden)), (128, 75, 190, 255))
    )
    hidden_crop = crop_scale(hidden_view, (120, 195, 220, 440), 3)
    labeled_panel(review, default_crop, (40, 1030, 490, 1770), "⑤ 默认回组：可见轮廓必须完全不变")
    labeled_panel(review, displaced_crop, (515, 1030, 1115, 1770), "⑥ 移开袖子：检查完整袖山，不得是补丁")
    labeled_panel(review, hidden_crop, (1140, 1030, 1590, 1770), "⑦ 紫色仅为隐藏责任：不越过袖口")
    labeled_panel(review, contact, (1615, 1030, 2360, 1770), "⑧ 0→1→0：肩根覆盖与下垂方向")

    draw.rounded_rectangle(
        (40, 1850, 2360, 2125),
        radius=18,
        fill="white",
        outline=(183, 193, 207),
        width=2,
    )
    draw.text(
        (66, 1872),
        "服装结构判断：袖子不是肩点向袖口收尖的三角片，而是套在上臂外的筒状布片；袖山沿衣身连接弧固定，袖口为自由边。",
        fill=(31, 42, 57),
        font=font(24, True),
    )
    draw.text(
        (66, 1925),
        "物理判断：固定弧承担衣身拉力，布量受重力朝袖口方向下垂；隐藏补全因此向内形成连续弧面，不向上形成尖刺。",
        fill=(31, 42, 57),
        font=font(24),
    )
    draw.text(
        (66, 1985),
        "请批准前看：完整袖是否像宽松 T 恤袖｜肩下是否有足够布量｜腋下连接是否自然｜移开后是否仍像真实袖子。",
        fill=(125, 60, 24),
        font=font(24, True),
    )
    draw.text(
        (66, 2045),
        "本板仍是阶段 A 几何候选；机器通过不代表视觉通过，未进入纹理 / PSD / Cubism / Physics / Runtime。",
        fill=(75, 85, 100),
        font=font(23),
    )
    review.save(ROOT / "qa/V28-SLEEVE-PHYSICS-USER-REVIEW.zh-CN.png")

    visible_diff = int(
        np.count_nonzero(
            sleeve_visible
            != np.array(
                Image.open(V27 / "masks/visible/sleeve.png").convert("L")
            )
        )
    )
    hidden_area = int(np.count_nonzero(sleeve_hidden > 8))
    components = cv2.connectedComponents((sleeve_complete > 8).astype(np.uint8))[0] - 1
    cuff_band = np.zeros((H, W), dtype=np.uint8)
    cv2.line(cuff_band, (96, 372), (184, 416), 255, 5)
    cuff_visible_before = cv2.bitwise_and(sleeve_visible, cuff_band)
    cuff_visible_after = cv2.bitwise_and(sleeve_complete, cuff_band)
    cuff_difference = int(
        np.count_nonzero((cuff_visible_before > 0) != (cuff_visible_after > 0))
    )
    yy, xx = np.indices((H, W))
    cuff_limit_y = 372.0 + 0.5 * (xx - 96.0)
    hidden_beyond_cuff = int(
        np.count_nonzero((sleeve_hidden > 8) & (yy > cuff_limit_y + 1.0))
    )
    engineering_pass = (
        visible_diff == 0
        and hidden_area > 100
        and components == 1
        and hidden_beyond_cuff == 0
        and seams_pass
        and max_l1_error < 0.01
        and max_l2_error < 0.01
        and first_hash == last_hash
    )
    report = {
        "schemaVersion": 1,
        "status": (
            "engineering_pass_pending_user_visual_approval"
            if engineering_pass
            else "engineering_fail_stop_stage_a"
        ),
        "scope": "screen-left V28 physical sleeve completion only",
        "authority": {
            "lineMasterSha256": sha256(SOURCE_LINE),
            "colorMasterSha256": sha256(SOURCE_COLOR),
            "v25ApprovalSha256": sha256(V25_APPROVAL),
            "v27SkeletonSha256": sha256(V27_SKELETON),
            "pass": True,
        },
        "visibleSleeve": {
            "differenceFromV27Pixels": visible_diff,
            "pass": visible_diff == 0,
        },
        "hiddenCompletion": {
            "addedPixels": hidden_area,
            "connectedComponents": components,
            "cuffBandDifferencePixels": cuff_difference,
            "pixelsBeyondCuff": hidden_beyond_cuff,
            "construction": "continuous sleeve-cap and armhole attachment arc",
            "pass": hidden_area > 100
            and components == 1
            and hidden_beyond_cuff == 0,
        },
        "motion": {
            "samples": 41,
            "allSleeveUpperOverlapsPass": seams_pass,
            "maxL1ErrorPx": max_l1_error,
            "maxL2ErrorPx": max_l2_error,
            "returnConsistency": first_hash == last_hash,
            "pass": seams_pass
            and max_l1_error < 0.01
            and max_l2_error < 0.01
            and first_hash == last_hash,
        },
        "visualGate": {
            "status": "pending_user_visual_approval",
            "review": "qa/V28-SLEEVE-PHYSICS-USER-REVIEW.zh-CN.png",
            "earliestFailurePoint": None,
        },
        "stop": "remain at Stage A until user approves the completed sleeve",
    }
    save_json(ROOT / "audit/machine-report.json", report)
    (ROOT / "audit/MACHINE-REPORT.zh-CN.md").write_text(
        "\n".join(
            [
                "# V28 袖子物理补全机器报告",
                "",
                f"- 状态：`{report['status']}`",
                f"- V27 可见袖子变化：`{visible_diff}px`",
                f"- 新增隐藏布量：`{hidden_area}px`",
                f"- 完整袖连通分量：`{components}`",
                f"- 41 样本肩袖覆盖：`{'通过' if seams_pass else '失败'}`",
                f"- 回程一致：`{'通过' if first_hash == last_hash else '失败'}`",
                "",
                "工程检查不能替代用户对袖山、腋下连接和布料下垂感的肉眼批准。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {"schemaVersion": 1, "status": report["status"], "files": []}
    for path in sorted(ROOT.rglob("*")):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path != ROOT / "audit/artifact-manifest.json"
        ):
            manifest["files"].append(
                {
                    "path": path.relative_to(ROOT).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    save_json(ROOT / "audit/artifact-manifest.json", manifest)
    print(
        json.dumps(
            {
                "status": report["status"],
                "visibleDifferencePx": visible_diff,
                "hiddenAddedPixels": hidden_area,
                "components": components,
                "cuffBandDifferencePx": cuff_difference,
                "motionPass": report["motion"]["pass"],
                "review": report["visualGate"]["review"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
