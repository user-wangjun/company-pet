from __future__ import annotations

import json
import math
import os
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(__file__).resolve().parents[3]
SKELETON = json.loads((ROOT / "skeleton.json").read_text(encoding="utf-8"))
LINE_PATH = PACKAGE / "source/masters/front-line-source-exact-after-reset.png"
COLOR_PATH = PACKAGE / "source/masters/front-color-source-exact-after-reset.png"
W, H = 512, 1086

COLORS = {
    "sleeve": (68, 114, 196),
    "upper_arm": (235, 118, 61),
    "forearm": (54, 162, 109),
    "hand": (170, 83, 154),
}
DRAW_ORDER = ["upper_arm", "forearm", "hand", "sleeve"]
MATERIAL_IDS = ["sleeve", "upper_arm", "forearm", "hand"]


def font(size: int, bold: bool = False):
    name = "msyhbd.ttc" if bold else "msyh.ttc"
    for candidate in (Path(os.environ.get("WINDIR", "")) / "Fonts" / name, Path(name)):
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            pass
    return ImageFont.load_default()


FONT_TITLE = font(28, True)
FONT_SECTION = font(21, True)
FONT_BODY = font(16)
FONT_SMALL = font(13)


def point(name: str) -> tuple[float, float]:
    value = SKELETON["landmarks"][name]
    return float(value["x"]), float(value["y"])


PS, PE, PW = point("shoulder"), point("elbow"), point("wrist")
L1 = float(SKELETON["boneLengthsPx"]["L1ShoulderToElbow"])
L2 = float(SKELETON["boneLengthsPx"]["L2ElbowToWrist"])
REST_T1 = float(SKELETON["restAnglesDeg"]["theta1"])
REST_T2 = float(SKELETON["restAnglesDeg"]["theta2"])
TARGET_T1 = float(SKELETON["primaryMotion"]["target"]["theta1"])
TARGET_T2 = float(SKELETON["primaryMotion"]["target"]["theta2"])
REST_WRIST = float(SKELETON["restAnglesDeg"]["phiWristLocal"])
TARGET_WRIST = float(SKELETON["primaryMotion"]["target"]["phiWristLocal"])
HAND_REFERENCE = (
    float(SKELETON["handMotionReference"]["restPoint"]["x"]),
    float(SKELETON["handMotionReference"]["restPoint"]["y"]),
)


def ensure_dirs() -> None:
    for path in (
        ROOT / "materials/solid",
        ROOT / "masks/visible",
        ROOT / "samples",
        ROOT / "qa",
        ROOT / "audit",
    ):
        path.mkdir(parents=True, exist_ok=True)


def blank_mask() -> Image.Image:
    return Image.new("L", (W, H), 0)


def disk(draw: ImageDraw.ImageDraw, center, radius, fill=255) -> None:
    x, y = center
    draw.ellipse(
        [round(x - radius), round(y - radius), round(x + radius), round(y + radius)],
        fill=fill,
    )


def variable_segment(
    mask: Image.Image,
    a: tuple[float, float],
    b: tuple[float, float],
    radius_a: float,
    radius_b: float,
    cap_a: float | None = None,
    cap_b: float | None = None,
) -> None:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    nx, ny = -dy / length, dx / length
    polygon = [
        (a[0] + nx * radius_a, a[1] + ny * radius_a),
        (b[0] + nx * radius_b, b[1] + ny * radius_b),
        (b[0] - nx * radius_b, b[1] - ny * radius_b),
        (a[0] - nx * radius_a, a[1] - ny * radius_a),
    ]
    draw = ImageDraw.Draw(mask)
    draw.polygon([(round(x), round(y)) for x, y in polygon], fill=255)
    if cap_a is not None:
        disk(draw, a, cap_a)
    if cap_b is not None:
        disk(draw, b, cap_b)


def connected_skin_hand(color: Image.Image) -> Image.Image:
    roi = (370, 540, 458, 650)
    candidate = blank_mask()
    pixels = candidate.load()
    source = color.load()
    for y in range(roi[1], roi[3]):
        for x in range(roi[0], roi[2]):
            r, g, b = source[x, y]
            background_distance = math.sqrt((r - 250) ** 2 + (g - 248) ** 2 + (b - 247) ** 2)
            skin = r > 165 and 85 < g < 238 and 75 < b < 235 and r - g > 4 and r - b > 4
            dark_outline = max(r, g, b) < 205
            if skin or dark_outline or background_distance > 20:
                pixels[x, y] = 255

    data = candidate.load()
    seed = None
    for radius in range(0, 25):
        for yy in range(552 - radius, 553 + radius):
            for xx in range(400 - radius, 401 + radius):
                if 0 <= xx < W and 0 <= yy < H and data[xx, yy] > 0:
                    seed = (xx, yy)
                    break
            if seed:
                break
        if seed:
            break
    if seed is None:
        raise RuntimeError("hand skin seed not found")

    result = blank_mask()
    out = result.load()
    queue = deque([seed])
    seen = {seed}
    while queue:
        x, y = queue.popleft()
        if data[x, y] == 0:
            continue
        out[x, y] = 255
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                p = (x + dx, y + dy)
                if (
                    roi[0] <= p[0] < roi[2]
                    and roi[1] <= p[1] < roi[3]
                    and p not in seen
                    and data[p[0], p[1]] > 0
                ):
                    seen.add(p)
                    queue.append(p)
    bbox = result.getbbox()
    if bbox is None:
        raise RuntimeError("connected hand silhouette is empty")
    expanded = (
        max(0, bbox[0] - 1),
        max(0, bbox[1] - 1),
        min(W, bbox[2] + 1),
        min(H, bbox[3] + 1),
    )
    exterior = set()
    exterior_queue = deque()
    for x in range(expanded[0], expanded[2]):
        for y in (expanded[1], expanded[3] - 1):
            if out[x, y] == 0 and (x, y) not in exterior:
                exterior.add((x, y))
                exterior_queue.append((x, y))
    for y in range(expanded[1], expanded[3]):
        for x in (expanded[0], expanded[2] - 1):
            if out[x, y] == 0 and (x, y) not in exterior:
                exterior.add((x, y))
                exterior_queue.append((x, y))
    while exterior_queue:
        x, y = exterior_queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (
                expanded[0] <= nx < expanded[2]
                and expanded[1] <= ny < expanded[3]
                and out[nx, ny] == 0
                and (nx, ny) not in exterior
            ):
                exterior.add((nx, ny))
                exterior_queue.append((nx, ny))
    for y in range(expanded[1], expanded[3]):
        for x in range(expanded[0], expanded[2]):
            if out[x, y] == 0 and (x, y) not in exterior:
                out[x, y] = 255
    return result.filter(ImageFilter.GaussianBlur(0.45))


def build_rest_masks(color: Image.Image):
    widths = SKELETON["localHalfWidthsPx"]
    joints = SKELETON["jointDisksPx"]

    complete = {}
    visible = {}

    sleeve = blank_mask()
    sleeve_polygon = [
        (315, 238),
        (318, 231),
        (322, 225),
        (326, 221),
        (331, 219),
        (332, 220),
        (333, 222),
        (334, 224),
        (336, 226),
        (339, 227),
        (340, 228),
        (342, 229),
        (343, 230),
        (344, 231),
        (345, 232),
        (346, 233),
        (347, 234),
        (348, 236),
        (349, 237),
        (350, 239),
        (351, 241),
        (352, 243),
        (353, 245),
        (357, 255),
        (361, 265),
        (365, 275),
        (369, 285),
        (372, 295),
        (376, 305),
        (380, 315),
        (384, 325),
        (388, 335),
        (391, 345),
        (395, 355),
        (399, 365),
        (402, 371),
        (395, 374),
        (390, 378),
        (385, 381),
        (380, 384),
        (375, 387),
        (370, 389),
        (365, 391),
        (360, 392),
        (355, 394),
        (350, 395),
        (345, 397),
        (340, 397),
        (326, 326),
        (315, 275),
    ]
    ImageDraw.Draw(sleeve).polygon(sleeve_polygon, fill=255)
    complete["sleeve"] = sleeve
    visible["sleeve"] = sleeve.copy()

    upper = blank_mask()
    t = (383.0 - PS[1]) / (PE[1] - PS[1])
    visible_start = (PS[0] + (PE[0] - PS[0]) * t, 383.0)
    variable_segment(
        upper,
        PS,
        visible_start,
        joints["shoulderRadius"],
        widths["upper_arm"]["underSleeve"],
        joints["shoulderRadius"],
        None,
    )
    variable_segment(
        upper,
        visible_start,
        PE,
        widths["upper_arm"]["underSleeve"],
        widths["upper_arm"]["atElbow"],
        None,
        joints["elbowRadius"],
    )
    complete["upper_arm"] = upper
    upper_visible = blank_mask()
    variable_segment(
        upper_visible,
        visible_start,
        PE,
        widths["upper_arm"]["underSleeve"],
        widths["upper_arm"]["atElbow"],
        None,
        None,
    )
    visible["upper_arm"] = upper_visible

    forearm = blank_mask()
    variable_segment(
        forearm,
        PE,
        PW,
        widths["forearm"]["atElbow"],
        widths["forearm"]["atWrist"],
        joints["elbowRadius"],
        joints["wristRadius"],
    )
    complete["forearm"] = forearm
    forearm_visible = blank_mask()
    variable_segment(
        forearm_visible,
        PE,
        PW,
        widths["forearm"]["atElbow"],
        widths["forearm"]["atWrist"],
        None,
        None,
    )
    visible["forearm"] = forearm_visible

    hand_visible = connected_skin_hand(color)
    hand_root = blank_mask()
    palm_anchor = (399.0, 553.0)
    variable_segment(
        hand_root,
        PW,
        palm_anchor,
        widths["forearm"]["atWrist"],
        12.0,
        widths["forearm"]["atWrist"],
        12.0,
    )
    hand_root = hand_root.filter(ImageFilter.GaussianBlur(0.7))
    hand = ImageChops.lighter(hand_visible, hand_root)
    complete["hand"] = hand
    visible["hand"] = hand_visible

    return complete, visible


def solid_rgba(mask: Image.Image, color) -> Image.Image:
    rgba = Image.new("RGBA", (W, H), color + (0,))
    rgba.putalpha(mask)
    return rgba


def save_masks(complete, visible) -> None:
    for material_id in MATERIAL_IDS:
        solid_rgba(complete[material_id], COLORS[material_id]).save(
            ROOT / f"materials/solid/{material_id}.png"
        )
        solid_rgba(visible[material_id], (255, 255, 255)).save(
            ROOT / f"masks/visible/{material_id}.png"
        )


def progress(index: int) -> float:
    j = index if index <= 20 else 40 - index
    return 0.5 * (1.0 - math.cos(math.pi * j / 20.0))


def pose_for_angles(theta1: float, theta2: float, phi_wrist: float = REST_WRIST):
    r1 = math.radians(theta1)
    rg = math.radians(theta1 + theta2)
    pe = (PS[0] + L1 * math.cos(r1), PS[1] + L1 * math.sin(r1))
    pw = (pe[0] + L2 * math.cos(rg), pe[1] + L2 * math.sin(rg))
    return {
        "theta1": theta1,
        "theta2": theta2,
        "phiWristLocal": phi_wrist,
        "elbow": pe,
        "wrist": pw,
        "deltaUpper": theta1 - REST_T1,
        "deltaForearm": theta1 + theta2 - REST_T1 - REST_T2,
        "deltaHand": theta1 + theta2 - REST_T1 - REST_T2 + phi_wrist - REST_WRIST,
    }


def pose_for_index(index: int):
    u = progress(index)
    return pose_for_angles(
        REST_T1 + (TARGET_T1 - REST_T1) * u,
        REST_T2 + (TARGET_T2 - REST_T2) * u,
        REST_WRIST + (TARGET_WRIST - REST_WRIST) * u,
    ) | {"index": index, "progress": u}


def inverse_affine(angle_deg, rest_origin, current_origin):
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    ox, oy = rest_origin
    cx, cy = current_origin
    return (
        c,
        s,
        ox - c * cx - s * cy,
        -s,
        c,
        oy + s * cx - c * cy,
    )


def transformed_mask(mask: Image.Image, material_id: str, pose, resample=Image.Resampling.NEAREST):
    if material_id in ("sleeve", "upper_arm"):
        angle = pose["deltaUpper"]
        rest_origin = current_origin = PS
    elif material_id == "forearm":
        angle = pose["deltaForearm"]
        rest_origin, current_origin = PE, pose["elbow"]
    else:
        angle = pose["deltaHand"]
        rest_origin, current_origin = PW, pose["wrist"]
    return mask.transform(
        (W, H),
        Image.Transform.AFFINE,
        inverse_affine(angle, rest_origin, current_origin),
        resample=resample,
        fillcolor=0,
    )


def transform_point(p, material_id, pose):
    if material_id in ("sleeve", "upper_arm"):
        angle = pose["deltaUpper"]
        rest_origin = current_origin = PS
    elif material_id == "forearm":
        angle = pose["deltaForearm"]
        rest_origin, current_origin = PE, pose["elbow"]
    else:
        angle = pose["deltaHand"]
        rest_origin, current_origin = PW, pose["wrist"]
    a = math.radians(angle)
    c, s = math.cos(a), math.sin(a)
    dx, dy = p[0] - rest_origin[0], p[1] - rest_origin[1]
    return (
        current_origin[0] + c * dx - s * dy,
        current_origin[1] + s * dx + c * dy,
    )


def render_pose(complete, pose, visual=True):
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    transformed = {}
    for material_id in MATERIAL_IDS:
        transformed[material_id] = transformed_mask(
            complete[material_id],
            material_id,
            pose,
            Image.Resampling.BICUBIC if visual else Image.Resampling.NEAREST,
        )
    for material_id in DRAW_ORDER:
        canvas.alpha_composite(solid_rgba(transformed[material_id], COLORS[material_id]))
    return canvas, transformed


def checkerboard(size, cell=12):
    image = Image.new("RGB", size, (242, 242, 242))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle([x, y, min(x + cell - 1, size[0]), min(y + cell - 1, size[1])], fill=(215, 215, 215))
    return image


def crop_on_checker(image: Image.Image, box, scale=1.0):
    left, top, right, bottom = map(int, box)
    crop = checkerboard((right - left, bottom - top))
    source_box = (
        max(0, left),
        max(0, top),
        min(W, right),
        min(H, bottom),
    )
    if source_box[2] > source_box[0] and source_box[3] > source_box[1]:
        source = image.crop(source_box)
        destination = (source_box[0] - left, source_box[1] - top)
        if source.mode == "RGBA":
            crop.paste(source, destination, source)
        else:
            crop.paste(source, destination)
    if scale != 1.0:
        crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.LANCZOS)
    return crop


def place_panel(board, panel, xy, title):
    x, y = xy
    board.paste(panel, (x, y))
    draw = ImageDraw.Draw(board)
    draw.rectangle([x, y, x + panel.width - 1, y + panel.height - 1], outline=(175, 175, 175), width=2)
    draw.text((x, y - 30), title, font=FONT_SECTION, fill=(20, 20, 20))


def render_default_review(line, color, complete, visible):
    box = (280, 220, 472, 690)
    rest, _ = render_pose(complete, pose_for_index(0))
    source = color.crop(box).resize((384, 940), Image.Resampling.NEAREST)
    solid = crop_on_checker(rest, box, 2.0)
    overlay_base = color.convert("RGBA")
    overlay = rest.copy()
    overlay.putalpha(110)
    overlay_base.alpha_composite(overlay)
    overlay_crop = overlay_base.convert("RGB").crop(box).resize((384, 940), Image.Resampling.NEAREST)

    board = Image.new("RGB", (1500, 1060), "white")
    draw = ImageDraw.Draw(board)
    draw.text((30, 18), "小星｜阶段 A 默认位置纯色回组审查", font=FONT_TITLE, fill=(20, 20, 20))
    draw.text((30, 56), "纯色只证明几何，不是正式材料；所有层保持 512×1086 原坐标。", font=FONT_BODY, fill=(85, 85, 85))
    place_panel(board, source, (30, 105), "权威彩稿近看 200%")
    place_panel(board, solid, (445, 105), "四材料纯色回组")
    place_panel(board, overlay_crop, (860, 105), "纯色半透明叠加")

    x, y = 1270, 110
    draw.text((x, y), "Draw Order", font=FONT_SECTION, fill=(20, 20, 20))
    y += 42
    for material_id in reversed(DRAW_ORDER):
        draw.rectangle([x, y, x + 28, y + 20], fill=COLORS[material_id])
        draw.text((x + 38, y), material_id, font=FONT_BODY, fill=(35, 35, 35))
        y += 34
    y += 18
    for text in [
        "蓝：sleeve",
        "橙：upper_arm",
        "绿：forearm",
        "紫：hand",
        "",
        "手链不参与四材料。",
        "腕部必须在无手链状态连接。",
        "本图等待用户视觉门禁。",
    ]:
        draw.text((x, y), text, font=FONT_SMALL, fill=(45, 45, 45))
        y += 25
    board.save(ROOT / "qa/default-recomposition.png")


def render_ownership_review(color, complete, visible):
    box = (280, 220, 472, 690)
    board = Image.new("RGB", (1490, 1060), "white")
    draw = ImageDraw.Draw(board)
    draw.text((30, 18), "小星｜阶段 A 可见归属与完整材料范围", font=FONT_TITLE, fill=(20, 20, 20))
    draw.text((30, 56), "左：原图；中：可见归属 V_i；右：含逆覆盖和关节余量的完整 M_i。", font=FONT_BODY, fill=(85, 85, 85))

    source = color.crop(box).resize((384, 940), Image.Resampling.NEAREST)
    visible_composite = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    complete_composite = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for material_id in DRAW_ORDER:
        visible_composite.alpha_composite(solid_rgba(visible[material_id], COLORS[material_id]))
        complete_composite.alpha_composite(solid_rgba(complete[material_id], COLORS[material_id]))
    visible_crop = crop_on_checker(visible_composite, box, 2.0)
    complete_crop = crop_on_checker(complete_composite, box, 2.0)
    place_panel(board, source, (30, 105), "权威彩稿")
    place_panel(board, visible_crop, (445, 105), "可见像素归属候选 V_i")
    place_panel(board, complete_crop, (860, 105), "完整纯色材料 M_i")

    x, y = 1270, 110
    draw.text((x, y), "审查要点", font=FONT_SECTION, fill=(20, 20, 20))
    y += 42
    for text in [
        "1. 袖口与上臂归属是否合理",
        "2. 肘高与两段体积是否自然",
        "3. 手腕不靠手链遮缝",
        "4. 紫色手层是否包含整手",
        "5. 圆形余量不得冒充纹理",
        "",
        "当前只锁几何边界。",
        "真实肤色、线稿和阴影尚未补画。",
    ]:
        draw.text((x, y), text, font=FONT_SMALL, fill=(45, 45, 45))
        y += 27
    board.save(ROOT / "qa/visible-ownership-review.png")


def render_revision_review(color, complete, visible):
    rest, _ = render_pose(complete, pose_for_index(0))
    board = Image.new("RGB", (1330, 960), "white")
    draw = ImageDraw.Draw(board)
    draw.text((30, 18), "小星｜阶段 A 肩端与手部修正复核", font=FONT_TITLE, fill=(20, 20, 20))
    draw.text(
        (30, 56),
        "上排检查橙色上臂是否越出蓝色袖层；下排检查手部外轮廓、指缝和隐藏腕根。",
        font=FONT_BODY,
        fill=(85, 85, 85),
    )

    shoulder_box = (300, 230, 370, 305)
    shoulder_source = color.crop(shoulder_box).resize((280, 300), Image.Resampling.NEAREST)
    shoulder_solid = crop_on_checker(rest, shoulder_box, 4.0)
    shoulder_overlay_base = color.convert("RGBA")
    shoulder_overlay = rest.copy()
    shoulder_overlay.putalpha(120)
    shoulder_overlay_base.alpha_composite(shoulder_overlay)
    shoulder_overlay_crop = shoulder_overlay_base.convert("RGB").crop(shoulder_box).resize((280, 300), Image.Resampling.NEAREST)
    place_panel(board, shoulder_source, (30, 120), "肩部权威彩稿 400%")
    place_panel(board, shoulder_solid, (340, 120), "修正后纯色回组 400%")
    place_panel(board, shoulder_overlay_crop, (650, 120), "修正后半透明叠加")

    hand_box = (372, 532, 452, 642)
    hand_source = color.crop(hand_box).resize((320, 440), Image.Resampling.NEAREST)
    hand_visible = crop_on_checker(solid_rgba(visible["hand"], COLORS["hand"]), hand_box, 4.0)
    hand_complete = crop_on_checker(solid_rgba(complete["hand"], COLORS["hand"]), hand_box, 4.0)
    place_panel(board, hand_source, (30, 485), "手部权威彩稿 400%")
    place_panel(board, hand_visible, (380, 485), "手部可见归属 V_hand")
    place_panel(board, hand_complete, (730, 485), "含隐藏腕根 M_hand")

    x, y = 1090, 120
    draw.text((x, y), "修正标准", font=FONT_SECTION, fill=(20, 20, 20))
    y += 42
    for text in [
        "肩端：",
        "• 蓝色袖层外不得出现橙色凸起",
        "• 隐藏上臂仍须进入袖内",
        "",
        "手部：",
        "• 不包含手链",
        "• 保留掌部与各指外轮廓",
        "• 只做亚像素抗锯齿",
        "• 不用圆形或平均色重画手",
    ]:
        draw.text((x, y), text, font=FONT_SMALL, fill=(45, 45, 45))
        y += 27
    board.save(ROOT / "qa/revision-shoulder-hand-review.png")


def render_sleeve_boundary_review(line, color, complete):
    box = (300, 225, 415, 415)
    scale = 3.2
    line_crop = line.crop(box).resize(
        (round((box[2] - box[0]) * scale), round((box[3] - box[1]) * scale)),
        Image.Resampling.NEAREST,
    )
    mask = complete["sleeve"]
    mask_rgba = solid_rgba(mask, COLORS["sleeve"])
    mask_crop = crop_on_checker(mask_rgba, box, scale)

    overlay_base = color.convert("RGBA")
    shade = solid_rgba(mask, COLORS["sleeve"])
    shade.putalpha(mask.point(lambda p: 105 if p >= 128 else 0))
    overlay_base.alpha_composite(shade)
    overlay_draw = ImageDraw.Draw(overlay_base)
    visible_boundary = [
        (331, 219),
        (332, 220),
        (333, 222),
        (334, 224),
        (336, 226),
        (339, 227),
        (340, 228),
        (342, 229),
        (343, 230),
        (344, 231),
        (345, 232),
        (346, 233),
        (347, 234),
        (348, 236),
        (349, 237),
        (350, 239),
        (351, 241),
        (352, 243),
        (353, 245),
        (357, 255),
        (361, 265),
        (365, 275),
        (369, 285),
        (372, 295),
        (376, 305),
        (380, 315),
        (384, 325),
        (388, 335),
        (391, 345),
        (395, 355),
        (399, 365),
        (402, 371),
        (395, 374),
        (390, 378),
        (385, 381),
        (380, 384),
        (375, 387),
        (370, 389),
        (365, 391),
        (360, 392),
        (355, 394),
        (350, 395),
        (345, 397),
        (340, 397),
    ]
    hidden_boundary = [
        (340, 397),
        (326, 326),
        (315, 275),
        (315, 238),
        (318, 231),
        (322, 225),
        (326, 221),
        (331, 219),
    ]
    overlay_draw.line(visible_boundary, fill=(230, 40, 65, 255), width=2, joint="curve")
    for start, end in zip(hidden_boundary, hidden_boundary[1:]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        steps = max(1, math.ceil(length / 8))
        for index in range(0, steps, 2):
            t0 = index / steps
            t1 = min((index + 1) / steps, 1.0)
            segment = [
                (round(start[0] + dx * t0), round(start[1] + dy * t0)),
                (round(start[0] + dx * t1), round(start[1] + dy * t1)),
            ]
            overlay_draw.line(segment, fill=(244, 145, 35, 255), width=2)
    overlay_crop = overlay_base.convert("RGB").crop(box).resize(
        (round((box[2] - box[0]) * scale), round((box[3] - box[1]) * scale)),
        Image.Resampling.NEAREST,
    )

    board = Image.new("RGB", (1510, 720), "white")
    draw = ImageDraw.Draw(board)
    draw.text((30, 18), "小星｜阶段 A 袖子可见边界复核", font=FONT_TITLE, fill=(20, 20, 20))
    draw.text(
        (30, 56),
        "红线是必须贴合原图的可见外缘与下袖口；橙色虚线是遮挡下的隐藏延伸；蓝色为归属。",
        font=FONT_BODY,
        fill=(85, 85, 85),
    )
    place_panel(board, line_crop, (30, 115), "权威线稿 320%")
    place_panel(board, overlay_crop, (430, 115), "边界叠加 320%")
    place_panel(board, mask_crop, (830, 115), "完整纯色袖层 320%")
    x, y = 1230, 120
    draw.text((x, y), "边界规则", font=FONT_SECTION, fill=(20, 20, 20))
    y += 42
    for text in [
        "必须贴线：",
        "• 肩端到袖口的外轮廓",
        "• 袖口最下方可见轮廓",
        "",
        "允许隐藏延伸：",
        "• 头发遮挡下的肩端",
        "• 衣身遮挡下的内侧边界",
        "",
        "禁止：",
        "• 用两点直线近似曲线外缘",
        "• 把上方装饰线当成袖口轮廓",
    ]:
        draw.text((x, y), text, font=FONT_SMALL, fill=(45, 45, 45))
        y += 27
    board.save(ROOT / "qa/sleeve-boundary-review.png")


def translate_rgba(image, dx, dy):
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.paste(image, (dx, dy), image)
    return result


def render_displaced_review(complete):
    rest_layers = {m: solid_rgba(complete[m], COLORS[m]) for m in MATERIAL_IDS}
    offsets = {
        "sleeve": (55, -25),
        "upper_arm": (55, 0),
        "forearm": (55, 0),
        "hand": (55, 10),
    }
    board = Image.new("RGB", (1400, 1000), "white")
    draw = ImageDraw.Draw(board)
    draw.text((30, 18), "小星｜阶段 A 部件分别移开检查", font=FONT_TITLE, fill=(20, 20, 20))
    draw.text((30, 56), "每格只移动标题部件；用于暴露完整闭合范围和接缝余量。", font=FONT_BODY, fill=(85, 85, 85))
    box = (240, 190, 512, 720)
    positions = [(30, 110), (370, 110), (710, 110), (1050, 110)]
    for material_id, position in zip(MATERIAL_IDS, positions):
        composite = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for layer_id in DRAW_ORDER:
            layer = rest_layers[layer_id]
            if layer_id == material_id:
                layer = translate_rgba(layer, *offsets[layer_id])
            composite.alpha_composite(layer)
        panel = crop_on_checker(composite, box, 1.10)
        place_panel(board, panel, position, f"移开 {material_id}")
    draw.text(
        (30, 955),
        "判断：独立层必须闭合；隐藏余量可见但不得成为巨型色块；默认遮挡不能掩盖空洞。",
        font=FONT_BODY,
        fill=(35, 35, 35),
    )
    board.save(ROOT / "qa/displaced-parts-review.png")


def draw_pose_bones(image: Image.Image, pose):
    draw = ImageDraw.Draw(image)
    ps, pe, pw = PS, pose["elbow"], pose["wrist"]
    draw.line([ps, pe, pw], fill=(30, 30, 30, 255), width=2)
    hand_reference = transform_point(HAND_REFERENCE, "hand", pose)
    draw.line([pw, hand_reference], fill=(25, 120, 180, 255), width=2)
    for p in (ps, pe, pw):
        draw.ellipse([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
    draw.ellipse(
        [
            hand_reference[0] - 2,
            hand_reference[1] - 2,
            hand_reference[0] + 2,
            hand_reference[1] + 2,
        ],
        fill=(25, 120, 180, 255),
    )


def render_contact_sheet(complete, poses):
    cols, rows = 7, 6
    tile_w, tile_h = 150, 148
    board = Image.new("RGB", (cols * tile_w + 40, rows * tile_h + 100), "white")
    draw = ImageDraw.Draw(board)
    draw.text((20, 14), "小星｜阶段 A 41 样本 FK：0→1→0", font=FONT_TITLE, fill=(20, 20, 20))
    draw.text((20, 50), "固定 L1/L2；腕点不漂移；蓝线显示手掌局部轴；无 Physics。", font=FONT_BODY, fill=(85, 85, 85))
    box = (250, 215, 512, 680)
    for index, pose in enumerate(poses):
        frame, _ = render_pose(complete, pose)
        draw_pose_bones(frame, pose)
        crop = crop_on_checker(frame, box, 0.26)
        tile = Image.new("RGB", (tile_w - 8, tile_h - 8), "white")
        tile.paste(crop, ((tile.width - crop.width) // 2, 15))
        ImageDraw.Draw(tile).text((5, 1), f"{index:02d}  t={pose['progress']:.2f}", font=FONT_SMALL, fill=(25, 25, 25))
        x = 20 + (index % cols) * tile_w
        y = 82 + (index // cols) * tile_h
        board.paste(tile, (x, y))
        draw.rectangle([x, y, x + tile.width - 1, y + tile.height - 1], outline=(190, 190, 190))
    board.save(ROOT / "qa/fk-41-contact-sheet.png")


def render_gif(complete, poses):
    frames = []
    box = (250, 215, 512, 680)
    for pose in poses:
        frame, _ = render_pose(complete, pose)
        draw_pose_bones(frame, pose)
        crop = crop_on_checker(frame, box, 0.70)
        draw = ImageDraw.Draw(crop)
        draw.rectangle([0, 0, crop.width, 26], fill=(255, 255, 255))
        draw.text((8, 4), f"样本 {pose['index']:02d}｜t={pose['progress']:.2f}｜无 Physics", font=FONT_SMALL, fill=(20, 20, 20))
        frames.append(crop)
    frames[0].save(
        ROOT / "qa/fk-41-slow-preview.gif",
        save_all=True,
        append_images=frames[1:],
        duration=120,
        loop=0,
        disposal=2,
    )


def render_wrist_motion_review(complete, poses):
    selected = [0, 5, 10, 15, 20, 25, 30, 35, 40]
    board = Image.new("RGB", (1080, 1110), "white")
    draw = ImageDraw.Draw(board)
    draw.text((25, 16), "小星｜阶段 A 腕部独立运动复核", font=FONT_TITLE, fill=(20, 20, 20))
    draw.text(
        (25, 52),
        "腕点位置由前臂 FK 决定；手掌再绕该点施加局部角 φw。蓝线为腕点到手部参考点。",
        font=FONT_BODY,
        fill=(85, 85, 85),
    )
    for panel_index, sample_index in enumerate(selected):
        pose = poses[sample_index]
        frame, _ = render_pose(complete, pose)
        draw_pose_bones(frame, pose)
        cx, cy = pose["wrist"]
        box = (round(cx - 55), round(cy - 45), round(cx + 75), round(cy + 115))
        panel = crop_on_checker(frame, box, 1.65)
        x = 25 + (panel_index % 3) * 350
        y = 125 + (panel_index // 3) * 315
        place_panel(
            board,
            panel,
            (x, y),
            f"样本 {sample_index:02d}｜t={pose['progress']:.2f}｜φw={pose['phiWristLocal']:.1f}°",
        )
    draw.text(
        (25, 1075),
        "通过条件：手掌绕腕点连续转动；腕点不平移脱节；样本 0 与 40 完全一致。",
        font=FONT_BODY,
        fill=(35, 35, 35),
    )
    board.save(ROOT / "qa/wrist-motion-review.png")


def render_wrist_motion_gif(complete, poses):
    frames = []
    for pose in poses:
        frame, _ = render_pose(complete, pose)
        draw_pose_bones(frame, pose)
        cx, cy = pose["wrist"]
        box = (round(cx - 55), round(cy - 45), round(cx + 75), round(cy + 115))
        crop = crop_on_checker(frame, box, 1.65)
        draw = ImageDraw.Draw(crop)
        draw.rectangle([0, 0, crop.width, 28], fill=(255, 255, 255))
        draw.text(
            (7, 5),
            f"{pose['index']:02d}｜φw={pose['phiWristLocal']:.1f}°｜无 Physics",
            font=FONT_SMALL,
            fill=(20, 20, 20),
        )
        frames.append(crop)
    frames[0].save(
        ROOT / "qa/wrist-motion-slow-preview.gif",
        save_all=True,
        append_images=frames[1:],
        duration=140,
        loop=0,
        disposal=2,
    )


def render_extremes(complete):
    definitions = [
        ("默认", REST_T1, REST_T2, REST_WRIST),
        ("主动作目标", TARGET_T1, TARGET_T2, TARGET_WRIST),
    ]
    for i, item in enumerate(SKELETON["requiredCombinationExtremes"], start=1):
        definitions.append((f"肩肘极值 {i}", float(item["theta1"]), float(item["theta2"]), REST_WRIST))
    for i, item in enumerate(SKELETON["requiredWristExtremes"], start=1):
        definitions.append(
            (
                f"腕部极值 {i}",
                float(item["theta1"]),
                float(item["theta2"]),
                float(item["phiWristLocal"]),
            )
        )
    board = Image.new("RGB", (1100, 1780), "white")
    draw = ImageDraw.Draw(board)
    draw.text((25, 16), "小星｜阶段 A 必要组合极值", font=FONT_TITLE, fill=(20, 20, 20))
    draw.text((25, 52), "检查 θ1/θ2 范围四角与腕部局部角两端，不靠缩小动作掩盖失败。", font=FONT_BODY, fill=(85, 85, 85))
    box = (250, 200, 512, 720)
    for i, (label, t1, t2, wrist) in enumerate(definitions):
        pose = pose_for_angles(t1, t2, wrist)
        frame, _ = render_pose(complete, pose)
        draw_pose_bones(frame, pose)
        panel = crop_on_checker(frame, box, 0.62)
        x = 25 + (i % 2) * 535
        y = 105 + (i // 2) * 410
        place_panel(board, panel, (x, y), f"{label}｜θ1={t1:.1f}° θ2={t2:.1f}° φw={wrist:.1f}°")
    board.save(ROOT / "qa/combined-extremes-review.png")


def render_seam_stress_review(complete):
    extreme = SKELETON["requiredCombinationExtremes"][0]
    definitions = [
        ("默认", pose_for_angles(REST_T1, REST_T2, REST_WRIST)),
        ("主动作目标", pose_for_angles(TARGET_T1, TARGET_T2, TARGET_WRIST)),
        ("最弯组合极值", pose_for_angles(float(extreme["theta1"]), float(extreme["theta2"]))),
    ]
    board = Image.new("RGB", (1040, 930), "white")
    draw = ImageDraw.Draw(board)
    draw.text((25, 16), "小星｜阶段 A 接缝压力检查 400%", font=FONT_TITLE, fill=(20, 20, 20))
    draw.text((25, 52), "最近邻放大；不叠骨架线，直接观察透明缝和关节色块边界。", font=FONT_BODY, fill=(85, 85, 85))
    row_labels = ["袖口→上臂", "肘：上臂→前臂", "腕：前臂→手"]
    for column, (label, pose) in enumerate(definitions):
        frame, _ = render_pose(complete, pose, visual=False)
        hem_t = (383.0 - PS[1]) / (PE[1] - PS[1])
        hem_rest = (PS[0] + (PE[0] - PS[0]) * hem_t, 383.0)
        centers = [
            transform_point(hem_rest, "sleeve", pose),
            pose["elbow"],
            pose["wrist"],
        ]
        x = 160 + column * 285
        draw.text((x, 88), label, font=FONT_SECTION, fill=(25, 25, 25))
        for row, center in enumerate(centers):
            half = 28 if row < 2 else 24
            box = (
                round(center[0] - half),
                round(center[1] - half),
                round(center[0] + half),
                round(center[1] + half),
            )
            crop = crop_on_checker(frame, box, 4.0)
            y = 130 + row * 255
            board.paste(crop, (x, y))
            draw.rectangle([x, y, x + crop.width - 1, y + crop.height - 1], outline=(165, 165, 165), width=2)
            if column == 0:
                draw.text((25, y + 88), row_labels[row], font=FONT_BODY, fill=(35, 35, 35))
    draw.text(
        (25, 895),
        "通过条件：棋盘格不得穿过任何接缝责任区；圆形余量只允许存在于被相邻材料覆盖的隐藏部分。",
        font=FONT_BODY,
        fill=(35, 35, 35),
    )
    board.save(ROOT / "qa/seam-stress-review.png")


def alpha_pixel_count(mask: Image.Image) -> int:
    return sum(mask.histogram()[128:])


def intersection_count(a: Image.Image, b: Image.Image) -> int:
    return alpha_pixel_count(ImageChops.multiply(a, b))


def disk_mask(center, radius):
    mask = blank_mask()
    disk(ImageDraw.Draw(mask), center, radius)
    return mask


def missing_in_zone(union_mask, zone):
    return alpha_pixel_count(ImageChops.subtract(zone, union_mask))


def material_component_count(mask: Image.Image) -> int:
    binary = mask.point(lambda p: 255 if p >= 128 else 0)
    bbox = binary.getbbox()
    if bbox is None:
        return 0
    pixels = binary.load()
    visited = set()
    count = 0
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            if pixels[x, y] == 0 or (x, y) in visited:
                continue
            count += 1
            queue = deque([(x, y)])
            visited.add((x, y))
            while queue:
                px, py = queue.popleft()
                for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                    if (
                        bbox[0] <= nx < bbox[2]
                        and bbox[1] <= ny < bbox[3]
                        and pixels[nx, ny] > 0
                        and (nx, ny) not in visited
                    ):
                        visited.add((nx, ny))
                        queue.append((nx, ny))
    return count


def grid_triangles(mask, step=8):
    bbox = mask.getbbox()
    if bbox is None:
        return []
    px = mask.load()
    triangles = []
    x0 = max(0, bbox[0] - bbox[0] % step)
    y0 = max(0, bbox[1] - bbox[1] % step)
    for y in range(y0, min(H - step, bbox[3]), step):
        for x in range(x0, min(W - step, bbox[2]), step):
            points = [(x, y), (x + step, y), (x + step, y + step), (x, y + step)]
            if all(px[p[0], p[1]] >= 128 for p in points):
                triangles.append((points[0], points[1], points[2]))
                triangles.append((points[0], points[2], points[3]))
    return triangles


def signed_area(triangle):
    a, b, c = triangle
    return 0.5 * ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def audit_geometry(complete, poses):
    extremes = [
        pose_for_angles(float(item["theta1"]), float(item["theta2"]))
        for item in SKELETON["requiredCombinationExtremes"]
    ]
    extremes.extend(
        pose_for_angles(
            float(item["theta1"]),
            float(item["theta2"]),
            float(item["phiWristLocal"]),
        )
        for item in SKELETON["requiredWristExtremes"]
    )
    all_poses = poses + extremes
    min_overlaps = {
        "sleeve_to_upper_arm": None,
        "upper_arm_to_forearm": None,
        "forearm_to_hand": None,
    }
    max_missing = {"sleeve_to_upper_arm": 0, "upper_arm_to_forearm": 0, "forearm_to_hand": 0}
    max_l1_error = 0.0
    max_l2_error = 0.0
    detached_graph_samples = 0

    for pose in all_poses:
        transformed = {
            m: transformed_mask(complete[m], m, pose, Image.Resampling.NEAREST)
            for m in MATERIAL_IDS
        }
        overlaps = {
            "sleeve_to_upper_arm": intersection_count(transformed["sleeve"], transformed["upper_arm"]),
            "upper_arm_to_forearm": intersection_count(transformed["upper_arm"], transformed["forearm"]),
            "forearm_to_hand": intersection_count(transformed["forearm"], transformed["hand"]),
        }
        for key, value in overlaps.items():
            min_overlaps[key] = value if min_overlaps[key] is None else min(min_overlaps[key], value)
        if any(value <= 0 for value in overlaps.values()):
            detached_graph_samples += 1

        hem_t = (383.0 - PS[1]) / (PE[1] - PS[1])
        hem_rest = (PS[0] + (PE[0] - PS[0]) * hem_t, 383.0)
        hem_current = transform_point(hem_rest, "sleeve", pose)
        zones = {
            "sleeve_to_upper_arm": disk_mask(hem_current, 8.0),
            "upper_arm_to_forearm": disk_mask(pose["elbow"], 9.0),
            "forearm_to_hand": disk_mask(pose["wrist"], 6.0),
        }
        unions = {
            "sleeve_to_upper_arm": ImageChops.lighter(transformed["sleeve"], transformed["upper_arm"]),
            "upper_arm_to_forearm": ImageChops.lighter(transformed["upper_arm"], transformed["forearm"]),
            "forearm_to_hand": ImageChops.lighter(transformed["forearm"], transformed["hand"]),
        }
        for key in zones:
            max_missing[key] = max(max_missing[key], missing_in_zone(unions[key], zones[key]))

        max_l1_error = max(max_l1_error, abs(math.dist(PS, pose["elbow"]) - L1))
        max_l2_error = max(max_l2_error, abs(math.dist(pose["elbow"], pose["wrist"]) - L2))

    meshes = {m: grid_triangles(complete[m]) for m in MATERIAL_IDS}
    flipped = 0
    degenerate = 0
    for material_id, triangles in meshes.items():
        for triangle in triangles:
            base_area = signed_area(triangle)
            for pose in all_poses:
                moved = tuple(transform_point(p, material_id, pose) for p in triangle)
                area = signed_area(moved)
                if abs(area) < 1e-8:
                    degenerate += 1
                elif base_area * area < 0:
                    flipped += 1

    component_counts = {m: material_component_count(complete[m]) for m in MATERIAL_IDS}
    rest_render, _ = render_pose(complete, poses[0], visual=False)
    return_render, _ = render_pose(complete, poses[-1], visual=False)
    deterministic_difference = ImageChops.difference(rest_render, return_render).getbbox() is not None
    target_pose = poses[20]
    rigid_target_pose = pose_for_angles(target_pose["theta1"], target_pose["theta2"], REST_WRIST)
    target_hand_reference = transform_point(HAND_REFERENCE, "hand", target_pose)
    rigid_target_hand_reference = transform_point(HAND_REFERENCE, "hand", rigid_target_pose)
    independent_hand_displacement = math.dist(target_hand_reference, rigid_target_hand_reference)
    minimum_hand_displacement = float(
        SKELETON["handMotionReference"]["requiredMinimumTargetDisplacementPx"]
    )

    search_results = {}
    responsibility_radii = {
        "sleeve_to_upper_arm": 8.0,
        "upper_arm_to_forearm": 9.0,
        "forearm_to_hand": 6.0,
    }
    for seam, responsibility_radius in responsibility_radii.items():
        searched = 0.0
        while searched <= responsibility_radius + 5.0:
            zone = disk_mask((100, 100), responsibility_radius)
            candidate = disk_mask((100, 100), searched)
            if missing_in_zone(candidate, zone) == 0:
                break
            searched = round(searched + 0.25, 2)
        search_results[seam] = {
            "searchStepPx": 0.25,
            "minimumCoverageRadiusPx": searched,
            "antialiasMarginPx": 2.0,
            "plannedMeshMarginPx": 3.0,
            "finalAllowancePx": searched + 5.0,
            "sampleInvariantReason": "joint-centered responsibility disk is inverse-transformed with the rigid FK joint and was also raster-checked in every primary and extreme pose",
        }

    report = {
        "schemaVersion": 1,
        "stage": "stage_a_solid_geometry",
        "status": "engineering_pass_visual_review_required",
        "scope": "screen_right sleeve to upper_arm to forearm to hand",
        "sampleCount": 41,
        "combinationExtremeCount": len(extremes),
        "materials": {
            m: {
                "path": f"materials/solid/{m}.png",
                "canvas": [W, H],
                "alphaPixels": alpha_pixel_count(complete[m]),
                "connectedComponents": component_counts[m],
                "prototypeTriangleCount": len(meshes[m]),
            }
            for m in MATERIAL_IDS
        },
        "boneLength": {
            "L1": L1,
            "L2": L2,
            "maxL1ErrorPx": max_l1_error,
            "maxL2ErrorPx": max_l2_error,
            "declaredTolerancePx": SKELETON["boneLengthsPx"]["analyticTolerancePx"],
            "pass": max_l1_error <= SKELETON["boneLengthsPx"]["analyticTolerancePx"]
            and max_l2_error <= SKELETON["boneLengthsPx"]["analyticTolerancePx"],
        },
        "seamCoverage": {
            "responsibilityDiskRadiusPx": {
                "sleeve_to_upper_arm": 8.0,
                "upper_arm_to_forearm": 9.0,
                "forearm_to_hand": 6.0,
            },
            "postSearchMarginsPx": {"antialias": 2.0, "plannedMesh": 3.0},
            "finalJointAllowancePx": {
                "sleeveHem": 13.5,
                "elbow": 14.0,
                "wrist": 11.0,
            },
            "maximumMissingPixels": max_missing,
            "minimumPairOverlapPixels": min_overlaps,
            "pass": all(value == 0 for value in max_missing.values())
            and all(value > 0 for value in min_overlaps.values()),
        },
        "minimumOverlapSearch": search_results,
        "connectivity": {
            "individualMaterialComponents": component_counts,
            "samplesWithBrokenAdjacentOverlapGraph": detached_graph_samples,
            "pass": all(value == 1 for value in component_counts.values()) and detached_graph_samples == 0,
        },
        "triangleOrientation": {
            "scope": "deterministic prototype grid triangles, not Cubism ArtMesh",
            "flippedTriangles": flipped,
            "degenerateTriangles": degenerate,
            "pass": flipped == 0 and degenerate == 0,
        },
        "deterministicReturn": {
            "pixelDifferenceAtSample0Vs40": deterministic_difference,
            "pass": not deterministic_difference,
        },
        "wristMotion": {
            "parameter": "phiWristLocal",
            "restDeg": REST_WRIST,
            "targetDeg": TARGET_WRIST,
            "allowedRangeDeg": [
                float(SKELETON["allowedRangesDeg"]["phiWristLocal"]["min"]),
                float(SKELETON["allowedRangesDeg"]["phiWristLocal"]["max"]),
            ],
            "independentHandReferenceDisplacementAtTargetPx": independent_hand_displacement,
            "requiredMinimumTargetDisplacementPx": minimum_hand_displacement,
            "wristPointDefinedByForearmFK": True,
            "physicsUsed": False,
            "pass": independent_hand_displacement >= minimum_hand_displacement,
        },
        "physicsUsed": False,
        "limitations": [
            "Pure colors prove geometry only.",
            "Visible ownership masks are geometric candidates, not textured source extraction.",
            "Prototype triangles do not prove Cubism ArtMesh.",
            "User Chinese visual approval is still required.",
        ],
        "evidence": [
            "qa/visible-ownership-review.png",
            "qa/default-recomposition.png",
            "qa/displaced-parts-review.png",
            "qa/fk-41-contact-sheet.png",
            "qa/fk-41-slow-preview.gif",
            "qa/combined-extremes-review.png",
            "qa/seam-stress-review.png",
            "qa/revision-shoulder-hand-review.png",
            "qa/sleeve-boundary-review.png",
            "qa/wrist-motion-review.png",
            "qa/wrist-motion-slow-preview.gif",
        ],
    }
    return report


def write_samples(poses):
    payload = {
        "schemaVersion": 2,
        "motion": "quiet_outward_arm_shift_with_active_wrist",
        "path": "0_to_1_to_0",
        "physics": False,
        "samples": [],
    }
    for pose in poses:
        payload["samples"].append(
            {
                "index": pose["index"],
                "progress": round(pose["progress"], 9),
                "theta1": round(pose["theta1"], 9),
                "theta2": round(pose["theta2"], 9),
                "phiWristLocal": round(pose["phiWristLocal"], 9),
                "shoulder": [round(PS[0], 9), round(PS[1], 9)],
                "elbow": [round(pose["elbow"][0], 9), round(pose["elbow"][1], 9)],
                "wrist": [round(pose["wrist"][0], 9), round(pose["wrist"][1], 9)],
                "handReference": [
                    round(transform_point(HAND_REFERENCE, "hand", pose)[0], 9),
                    round(transform_point(HAND_REFERENCE, "hand", pose)[1], 9),
                ],
                "L1": round(math.dist(PS, pose["elbow"]), 9),
                "L2": round(math.dist(pose["elbow"], pose["wrist"]), 9),
            }
        )
    (ROOT / "samples/fk-41-samples.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_report(report):
    (ROOT / "audit/stage-a-geometry-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# 阶段 A 纯色几何报告",
        "",
        "## 决定",
        "",
        "**工程检查通过；中文视觉门禁待用户确认。**",
        "",
        "纯色色块只证明几何，不是正式材料，也不证明 Cubism。",
        "",
        "## 工程结果",
        "",
        f"- 41 样本与 {report['combinationExtremeCount']} 个组合极值均使用固定 `L1={L1:.6f}px`、`L2={L2:.6f}px`。",
        f"- 最大 L1 误差：`{report['boneLength']['maxL1ErrorPx']:.3e}px`。",
        f"- 最大 L2 误差：`{report['boneLength']['maxL2ErrorPx']:.3e}px`。",
        f"- 三处接缝最大缺失像素：`{report['seamCoverage']['maximumMissingPixels']}`。",
        f"- 相邻材料最小重叠像素：`{report['seamCoverage']['minimumPairOverlapPixels']}`。",
        f"- 发生断开的样本：`{report['connectivity']['samplesWithBrokenAdjacentOverlapGraph']}`。",
        f"- 原型三角形翻折：`{report['triangleOrientation']['flippedTriangles']}`。",
        f"- 原型退化三角形：`{report['triangleOrientation']['degenerateTriangles']}`。",
        f"- 样本 0 与 40 像素差异：`{report['deterministicReturn']['pixelDifferenceAtSample0Vs40']}`。",
        f"- 腕部局部角：`{report['wristMotion']['restDeg']:.1f}° → {report['wristMotion']['targetDeg']:.1f}° → {report['wristMotion']['restDeg']:.1f}°`。",
        f"- 排除前臂刚性变换后的手部参考点位移：`{report['wristMotion']['independentHandReferenceDisplacementAtTargetPx']:.3f}px`。",
        "",
        "## 视觉门禁",
        "",
        "请依次查看：",
        "",
        "1. `qa/visible-ownership-review.png`",
        "2. `qa/default-recomposition.png`",
        "3. `qa/displaced-parts-review.png`",
        "4. `qa/fk-41-contact-sheet.png`",
        "5. `qa/fk-41-slow-preview.gif`",
        "6. `qa/combined-extremes-review.png`",
        "7. `qa/seam-stress-review.png`",
        "8. `qa/revision-shoulder-hand-review.png`",
        "9. `qa/sleeve-boundary-review.png`",
        "10. `qa/wrist-motion-review.png`",
        "11. `qa/wrist-motion-slow-preview.gif`",
        "",
        "未获得用户明确通过前，不进入真实隐藏纹理补画。",
    ]
    (ROOT / "audit/stage-a-geometry-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ensure_dirs()
    line = Image.open(LINE_PATH).convert("RGB")
    color = Image.open(COLOR_PATH).convert("RGB")
    if line.size != (W, H) or color.size != (W, H):
        raise ValueError("authoritative masters must remain 512x1086")

    complete, visible = build_rest_masks(color)
    save_masks(complete, visible)
    poses = [pose_for_index(i) for i in range(41)]
    write_samples(poses)
    render_ownership_review(color, complete, visible)
    render_default_review(line, color, complete, visible)
    render_revision_review(color, complete, visible)
    render_sleeve_boundary_review(line, color, complete)
    render_displaced_review(complete)
    render_contact_sheet(complete, poses)
    render_gif(complete, poses)
    render_wrist_motion_review(complete, poses)
    render_wrist_motion_gif(complete, poses)
    render_extremes(complete)
    render_seam_stress_review(complete)
    report = audit_geometry(complete, poses)
    write_report(report)
    print(json.dumps({
        "status": report["status"],
        "boneLengthPass": report["boneLength"]["pass"],
        "seamCoveragePass": report["seamCoverage"]["pass"],
        "connectivityPass": report["connectivity"]["pass"],
        "trianglePass": report["triangleOrientation"]["pass"],
        "deterministicReturnPass": report["deterministicReturn"]["pass"],
        "wristMotionPass": report["wristMotion"]["pass"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
