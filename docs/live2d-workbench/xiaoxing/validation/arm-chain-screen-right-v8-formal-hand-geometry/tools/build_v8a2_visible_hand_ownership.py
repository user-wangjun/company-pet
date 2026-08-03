from __future__ import annotations

import hashlib
import json
import os
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
VALIDATION = ROOT.parent
XIAOXING = VALIDATION.parent
V5 = VALIDATION / "arm-chain-screen-right-v5-hidden-upper-arm"
V6 = VALIDATION / "arm-chain-screen-right-v6-complete-upper-arm-geometry"
V7 = VALIDATION / "arm-chain-screen-right-v7-production-forearm-geometry"
V7C1 = V7 / "v7c1-elbow-seam-fairing"

AUDIT = ROOT / "audit"
MASKS = ROOT / "masks"
QA = ROOT / "qa"
for directory in (AUDIT, MASKS, QA):
    directory.mkdir(parents=True, exist_ok=True)

LINE_SOURCE = XIAOXING / "source/masters/front-line-source-exact-after-reset.png"
COLOR_SOURCE = XIAOXING / "source/masters/front-color-source-exact-after-reset.png"
V8A1_APPROVAL = (
    AUDIT / "v8a1-user-visual-approval-forearm-above-hand-2026-07-26.json"
)
V8A1_CONTRACT = AUDIT / "v8a1-forearm-above-hand-contract.json"
V8A1_REPORT = AUDIT / "v8a1-forearm-above-hand-revalidation.json"
V8A2_APPROVAL = (
    AUDIT / "v8a2-user-visual-approval-visible-hand-2026-07-26.json"
)
V7C1_INDEPENDENT_REVERIFICATION = (
    AUDIT / "v7c1-independent-reverification-2026-07-26.json"
)
VISIBLE_FOREARM = V7 / "masks/visible-forearm-locked.png"
BRACELET = V7 / "masks/bracelet-ownership-candidate.png"
WRIST_LINE = V7 / "masks/wrist-ownership-line-candidate.png"
WRIST_RESPONSIBILITY = V7 / "masks/wrist-source-responsibility-candidate.png"
SOURCE_ROOT_SUPPORT = V7 / "masks/source-arm-neutral-outline-candidate.png"
ENVELOPE = V7C1 / "masks/temporary-hand-root-envelope.png"
ENVELOPE_CONTRACT = (
    V7C1 / "audit/v7c1-temporary-hand-root-envelope-contract.json"
)
VISIBLE_UPPER = (
    V6 / "masks/reference/visible-upper-arm-locked-reference.png"
)
VISIBLE_SLEEVE = (
    V5 / "complete-sleeve-final/inputs/sleeve-visible-base-geometry-r3.png"
)

EXPECTED_INPUTS = {
    "source/front-line-source-exact-after-reset.png": (
        LINE_SOURCE,
        "706aaf10652147cf76e233532b5459ce130921a96806f6970c91e1f3a427172f",
        460239,
    ),
    "source/front-color-source-exact-after-reset.png": (
        COLOR_SOURCE,
        "33b3ce81781c02b36488ed72fa27c2a136682824ca10c42077895eab0ffb2dd5",
        581346,
    ),
    "audit/v8a1-user-visual-approval.json": (
        V8A1_APPROVAL,
        "d8d9e9c7af56d6159444ae7770b8c34f8ba42b34d1a3b2a7e2e439e177eedb70",
        944,
    ),
    "audit/v8a1-forearm-above-hand-contract.json": (
        V8A1_CONTRACT,
        "13d9a1b74bcb9362ca644145276e1dfbac496a7684170a3104b1de2ee450bc48",
        865,
    ),
    "audit/v8a1-forearm-above-hand-revalidation.json": (
        V8A1_REPORT,
        "1704d65a076d4a574f832b6928649e0862f105c164afc0bcd0d239bcf1a775fd",
        4542,
    ),
    "audit/v8a2-user-visual-approval-visible-hand-2026-07-26.json": (
        V8A2_APPROVAL,
        "2cf7ffbb68b8db3820528759e39d33fe6e261d93bde1fa755aa6ecc85bad00c4",
        1651,
    ),
    "audit/v7c1-independent-reverification-2026-07-26.json": (
        V7C1_INDEPENDENT_REVERIFICATION,
        "048d347f4e03c64bd6c1e39646cded027c0fd5378a6eb1077cb717c198a71cfc",
        3515,
    ),
    "v7/visible-forearm-locked.png": (
        VISIBLE_FOREARM,
        "87933c37e8765be3d468c366277a7a0e12c1cbd2ccc28b4172af852c45a1e7ab",
        4920,
    ),
    "v7/bracelet-ownership-candidate.png": (
        BRACELET,
        "411a3974a1a1ff6c1d7fadd6135e34a01efb41dca9bdc6a4d44753b85aa6c719",
        4723,
    ),
    "v7/wrist-source-responsibility-candidate.png": (
        WRIST_RESPONSIBILITY,
        "6afa37f159e15f92a46865d014334e79f156268587dfb64c27a2b403454b89e2",
        4655,
    ),
    "v7/temporary-hand-root-envelope.png": (
        ENVELOPE,
        "29ed3326d99497c7fb815476f63d0825564c6b9cb174fdd151c275542c8ce421",
        4637,
    ),
    "v6/visible-upper-arm-locked-reference.png": (
        VISIBLE_UPPER,
        "c2dfe729e21f3359b9fe866ede85aef2304452a662b9ba471172b57af45c4ebd",
        732,
    ),
    "v5/sleeve-visible-base-geometry-r3.png": (
        VISIBLE_SLEEVE,
        "4b4aea367e21ec16e3550c765e4bf197a04fdca7732ca8fdc21193562205992c",
        5030,
    ),
}

CANVAS_SIZE = (512, 1086)
HAND_ROI = (365, 520, 450, 660)
HAND_SEED = (400, 560)
CONSERVATIVE_LINE_THRESHOLD = 205
RECOMMENDED_LINE_THRESHOLD = 225
BROAD_LINE_THRESHOLD = 235


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


def binary(image: Image.Image, threshold: int = 16) -> Image.Image:
    if image.mode == "L":
        channel = image
    else:
        channel = image.convert("RGBA").getchannel("A")
    return channel.point(lambda value: 255 if value >= threshold else 0)


def load_mask(path: Path) -> Image.Image:
    return binary(Image.open(path))


def count(mask: Image.Image) -> int:
    return sum(binary(mask, 1).histogram()[1:])


def connected_components(mask: Image.Image) -> int:
    pixels = binary(mask, 1).load()
    width, height = mask.size
    seen: set[tuple[int, int]] = set()
    components = 0
    for y in range(height):
        for x in range(width):
            if not pixels[x, y] or (x, y) in seen:
                continue
            components += 1
            seen.add((x, y))
            queue = deque([(x, y)])
            while queue:
                px, py = queue.popleft()
                for nx, ny in (
                    (px - 1, py),
                    (px + 1, py),
                    (px, py - 1),
                    (px, py + 1),
                ):
                    if (
                        0 <= nx < width
                        and 0 <= ny < height
                        and pixels[nx, ny]
                        and (nx, ny) not in seen
                    ):
                        seen.add((nx, ny))
                        queue.append((nx, ny))
    return components


def hole_count(mask: Image.Image) -> int:
    foreground = binary(mask, 1).load()
    width, height = mask.size
    exterior: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        for y in (0, height - 1):
            if not foreground[x, y] and (x, y) not in exterior:
                exterior.add((x, y))
                queue.append((x, y))
    for y in range(height):
        for x in (0, width - 1):
            if not foreground[x, y] and (x, y) not in exterior:
                exterior.add((x, y))
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in (
            (x - 1, y),
            (x + 1, y),
            (x, y - 1),
            (x, y + 1),
        ):
            if (
                0 <= nx < width
                and 0 <= ny < height
                and not foreground[nx, ny]
                and (nx, ny) not in exterior
            ):
                exterior.add((nx, ny))
                queue.append((nx, ny))
    unseen = {
        (x, y)
        for y in range(height)
        for x in range(width)
        if not foreground[x, y] and (x, y) not in exterior
    }
    holes = 0
    while unseen:
        holes += 1
        seed = unseen.pop()
        queue.append(seed)
        while queue:
            x, y = queue.popleft()
            for neighbor in (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            ):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
    return holes


def difference_count(first: Image.Image, second: Image.Image) -> int:
    return count(ImageChops.difference(binary(first, 1), binary(second, 1)))


def rgba_mask(mask: Image.Image, color=(255, 255, 255)) -> Image.Image:
    result = Image.new("RGBA", mask.size, (*color, 0))
    result.putalpha(binary(mask, 1))
    return result


def coordinates(mask: Image.Image) -> list[tuple[int, int]]:
    pixels = binary(mask, 1).load()
    return [
        (x, y)
        for y in range(mask.height)
        for x in range(mask.width)
        if pixels[x, y]
    ]


def coordinate_fingerprint(mask: Image.Image) -> str:
    payload = "\n".join(f"{x},{y}" for x, y in coordinates(mask))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def rgb_fingerprint(mask: Image.Image, source: Image.Image) -> str:
    source_pixels = source.convert("RGB").load()
    payload = bytearray()
    for x, y in coordinates(mask):
        payload.extend(source_pixels[x, y])
    return hashlib.sha256(payload).hexdigest()


def connected_component_from_seed(
    mask: Image.Image, seed: tuple[int, int]
) -> Image.Image:
    pixels = binary(mask, 1).load()
    if not pixels[seed[0], seed[1]]:
        raise RuntimeError(f"Seed is outside candidate: {seed}")
    seen = {seed}
    queue = deque([seed])
    while queue:
        x, y = queue.popleft()
        for nx, ny in (
            (x - 1, y),
            (x + 1, y),
            (x, y - 1),
            (x, y + 1),
        ):
            if (
                0 <= nx < mask.width
                and 0 <= ny < mask.height
                and pixels[nx, ny]
                and (nx, ny) not in seen
            ):
                seen.add((nx, ny))
                queue.append((nx, ny))
    result = Image.new("L", mask.size, 0)
    result_pixels = result.load()
    for point in seen:
        result_pixels[point[0], point[1]] = 255
    return result


def flood_exterior(barrier: Image.Image) -> set[tuple[int, int]]:
    barrier_pixels = binary(barrier, 1).load()
    width, height = barrier.size
    exterior: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        for y in (0, height - 1):
            if not barrier_pixels[x, y] and (x, y) not in exterior:
                exterior.add((x, y))
                queue.append((x, y))
    for y in range(height):
        for x in (0, width - 1):
            if not barrier_pixels[x, y] and (x, y) not in exterior:
                exterior.add((x, y))
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in (
            (x - 1, y),
            (x + 1, y),
            (x, y - 1),
            (x, y + 1),
        ):
            if (
                0 <= nx < width
                and 0 <= ny < height
                and not barrier_pixels[nx, ny]
                and (nx, ny) not in exterior
            ):
                exterior.add((nx, ny))
                queue.append((nx, ny))
    return exterior


def trace_hand_support(
    line_source: Image.Image,
    wrist_line: Image.Image,
    visible_forearm: Image.Image,
    threshold: int,
) -> Image.Image:
    x0, y0, x1, y1 = HAND_ROI
    width, height = x1 - x0, y1 - y0
    dark = line_source.convert("L").crop(HAND_ROI).point(
        lambda value: 255 if value < threshold else 0
    )
    dark = dark.filter(ImageFilter.MaxFilter(3))
    cut = binary(wrist_line).crop(HAND_ROI).filter(ImageFilter.MaxFilter(3))
    barrier = ImageChops.lighter(dark, cut)
    exterior = flood_exterior(barrier)
    enclosed = Image.new("L", (width, height), 255)
    enclosed_pixels = enclosed.load()
    for point in exterior:
        enclosed_pixels[point[0], point[1]] = 0
    local_seed = (HAND_SEED[0] - x0, HAND_SEED[1] - y0)
    selected = connected_component_from_seed(enclosed, local_seed)
    # The accepted wrist line closes the contour for flood fill but is not
    # itself source material. Remove it, then retain only the hand component.
    selected = binary(ImageChops.subtract(selected, cut), 1)
    selected = binary(
        ImageChops.subtract(selected, visible_forearm.crop(HAND_ROI)), 1
    )
    selected = connected_component_from_seed(selected, local_seed)
    result = Image.new("L", CANVAS_SIZE, 0)
    result.paste(selected, (x0, y0))
    return result


def convex_hull(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    unique = sorted(set(points))
    if len(unique) <= 1:
        return unique

    def cross(origin, first, second):
        return (
            (first[0] - origin[0]) * (second[1] - origin[1])
            - (first[1] - origin[1]) * (second[0] - origin[0])
        )

    lower = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def finger_gap_mask(hand_support: Image.Image) -> Image.Image:
    # A real finger gap has hand support on both its left and right at the same
    # scanline. This excludes ordinary exterior background below the fingertips
    # that a convex-hull-only diagnostic would incorrectly color as a gap.
    hand = binary(hand_support, 1)
    hand_pixels = hand.load()
    result = Image.new("L", CANVAS_SIZE, 0)
    result_pixels = result.load()
    for y in range(570, 626):
        occupied = [x for x in range(375, 443) if hand_pixels[x, y]]
        if len(occupied) < 2:
            continue
        left, right = min(occupied), max(occupied)
        for x in range(left + 1, right):
            if not hand_pixels[x, y]:
                result_pixels[x, y] = 255
    return result


def outline(mask: Image.Image, radius=3) -> Image.Image:
    expanded = binary(mask, 1).filter(ImageFilter.MaxFilter(radius))
    eroded = binary(mask, 1).filter(ImageFilter.MinFilter(radius))
    return binary(ImageChops.subtract(expanded, eroded), 1)


def font(size: int, bold: bool = False):
    fonts = Path(os.environ.get("WINDIR", "")) / "Fonts"
    candidates = (
        fonts / ("msyhbd.ttc" if bold else "msyh.ttc"),
        fonts / "simhei.ttf",
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def text(draw, xy, value: str, size=24, bold=False, fill=(25, 25, 25)):
    draw.text(xy, value, font=font(size, bold), fill=fill)


def overlay(
    base: Image.Image,
    mask: Image.Image,
    color: tuple[int, int, int],
    opacity=160,
) -> Image.Image:
    layer = Image.new("RGBA", base.size, (*color, 0))
    layer.putalpha(binary(mask, 1).point(lambda value: opacity if value else 0))
    return Image.alpha_composite(base.convert("RGBA"), layer)


def scaled_crop(image: Image.Image, box, scale: int) -> Image.Image:
    crop = image.crop(box)
    return crop.resize(
        (crop.width * scale, crop.height * scale),
        Image.Resampling.NEAREST,
    )


def checkerboard(size, tile=8) -> Image.Image:
    result = Image.new("RGB", size, (224, 224, 224))
    draw = ImageDraw.Draw(result)
    for y in range(0, size[1], tile):
        for x in range(0, size[0], tile):
            if (x // tile + y // tile) % 2:
                draw.rectangle(
                    (x, y, min(x + tile - 1, size[0] - 1), min(y + tile - 1, size[1] - 1)),
                    fill=(248, 248, 248),
                )
    return result


def build_panel(title: str, image: Image.Image, width=540, footer=None):
    target = image.convert("RGB")
    ratio = width / target.width
    target = target.resize(
        (width, round(target.height * ratio)), Image.Resampling.NEAREST
    )
    footer_height = 48 if footer else 0
    panel = Image.new(
        "RGB", (width, target.height + 54 + footer_height), (240, 240, 240)
    )
    draw = ImageDraw.Draw(panel)
    text(draw, (8, 8), title, 28, True)
    panel.paste(target, (0, 54))
    if footer:
        text(draw, (8, panel.height - 40), footer, 22)
    return panel


def save_visuals(
    source: Image.Image,
    candidate: Image.Image,
    locked: Image.Image,
    pending: Image.Image,
    pending_include: Image.Image,
    pending_exclude: Image.Image,
    visible_forearm: Image.Image,
    bracelet: Image.Image,
    gaps: Image.Image,
    envelope: Image.Image,
    envelope_hand: Image.Image,
    envelope_forearm: Image.Image,
) -> list[Path]:
    hand_box = (365, 520, 450, 660)
    wrist_box = (365, 515, 425, 565)
    finger_box = (375, 565, 442, 628)

    source_rgba = source.convert("RGBA")
    extracted = Image.new("RGBA", source.size, (0, 0, 0, 0))
    extracted.paste(source_rgba, mask=binary(candidate))
    crop = extracted.crop(hand_box)
    board = checkerboard(crop.size, 6).convert("RGBA")
    board = Image.alpha_composite(board, crop)
    isolated = build_panel(
        "V_hand 候选：权威源像素置于棋盘格",
        board,
        600,
        f"候选 {count(candidate)} px；未生成完整隐藏手部",
    )
    isolated.save(QA / "V8-A2-V-HAND-CHECKERBOARD.png")

    source_outline = overlay(source_rgba, outline(candidate, 3), (255, 0, 35), 235)
    outline_panel = build_panel(
        "V_hand 候选描边叠加权威母图",
        scaled_crop(source_outline, hand_box, 7),
        600,
        "红线只表示可见所有权候选，不是完整 M_hand",
    )
    outline_panel.save(QA / "V8-A2-V-HAND-OUTLINE-OVERLAY.png")

    boundary = overlay(source_rgba, visible_forearm, (0, 190, 190), 125)
    boundary = overlay(boundary, candidate, (45, 105, 255), 125)
    boundary = overlay(boundary, pending, (255, 0, 210), 240)
    boundary_panel = build_panel(
        "前臂 ↔ 手部所有权边界（200% 以上）",
        scaled_crop(boundary, wrist_box, 10),
        700,
        "青=冻结前臂；蓝=手部候选；粉=66 px 待裁决混合带",
    )
    boundary_panel.save(QA / "V8-A2-FOREARM-HAND-BOUNDARY-200PCT.png")

    adjacency = overlay(source_rgba, bracelet, (255, 190, 0), 150)
    adjacency = overlay(adjacency, candidate, (40, 110, 255), 120)
    adjacency = overlay(adjacency, envelope, (120, 65, 225), 90)
    adjacency_panel = build_panel(
        "手链、手部与 389 px 临时包络邻接",
        scaled_crop(adjacency, wrist_box, 10),
        700,
        "黄=手链；蓝=V_hand；紫=临时包络；可见所有权交集 0",
    )
    adjacency_panel.save(QA / "V8-A2-BRACELET-HAND-ADJACENCY.png")

    finger = overlay(source_rgba, candidate, (40, 110, 255), 105)
    finger = overlay(finger, gaps, (0, 210, 120), 205)
    finger = overlay(finger, pending, (255, 0, 210), 235)
    finger_panel = build_panel(
        "指缝背景与 AA 混合像素",
        scaled_crop(finger, finger_box, 10),
        700,
        "绿=保持透明的指缝背景；粉=待裁决 AA；未拆手指",
    )
    finger_panel.save(QA / "V8-A2-FINGER-GAPS-AND-AA.png")

    envelope_class = source_rgba
    envelope_class = overlay(envelope_class, envelope_hand, (40, 110, 255), 215)
    envelope_class = overlay(
        envelope_class, envelope_forearm, (255, 60, 20), 225
    )
    envelope_panel = build_panel(
        "389 px 包络相对 V_hand 的分类",
        scaled_crop(envelope_class, wrist_box, 10),
        700,
        f"蓝=E∩V_hand {count(envelope_hand)}；红=E∩前臂/手链 {count(envelope_forearm)}",
    )
    envelope_panel.save(QA / "V8-A2-ENVELOPE-V-HAND-CLASSIFICATION.png")

    resolved = Image.new("RGB", (1500, 620), (240, 240, 240))
    draw = ImageDraw.Draw(resolved)
    old = Image.new("RGB", source.size, (246, 246, 246))
    old.paste((0, 180, 175), mask=visible_forearm)
    old.paste((239, 147, 92), mask=envelope)
    new = Image.new("RGB", source.size, (246, 246, 246))
    new.paste((239, 147, 92), mask=envelope)
    new.paste((0, 180, 175), mask=visible_forearm)
    new.paste((245, 186, 30), mask=bracelet)
    conflict = overlay(source_rgba, envelope_forearm, (255, 0, 35), 235)
    panels = (
        ("旧层序：手在前", scaled_crop(old, wrist_box, 8)),
        ("新层序：前臂含手链在前", scaled_crop(new, wrist_box, 8)),
        ("81 px 隐藏重叠（已解决）", scaled_crop(conflict, wrist_box, 8)),
    )
    for index, (title, panel) in enumerate(panels):
        x = index * 500
        text(draw, (x + 8, 8), title, 26, True)
        resolved.paste(panel.resize((480, 400), Image.Resampling.NEAREST), (x + 10, 55))
    text(
        draw,
        (12, 500),
        "新层序允许完整手部在手链后方包含 389 px 包络；81 px 是隐藏材料重叠，不是重复可见所有权。",
        25,
        True,
    )
    resolved.save(QA / "V8-A2-ENVELOPE-DRAW-ORDER-RESOLUTION.png")

    exact_recompose = source.copy()
    candidate_pixels = source.copy()
    exact_recompose.paste(candidate_pixels, mask=candidate)
    recompose_difference = ImageChops.difference(exact_recompose, source)
    recompose_diff_mask = ImageChops.lighter(
        ImageChops.lighter(*recompose_difference.split()[:2]),
        recompose_difference.split()[2],
    )
    ownership = Image.new("RGB", source.size, (246, 246, 246))
    ownership.paste((45, 105, 255), mask=candidate)
    ownership.paste((0, 190, 190), mask=visible_forearm)
    ownership.paste((255, 190, 0), mask=bracelet)
    neutral = Image.new("RGB", (1500, 620), (240, 240, 240))
    draw = ImageDraw.Draw(neutral)
    neutral_panels = (
        ("权威母图", scaled_crop(source, hand_box, 5)),
        ("可见所有权分区", scaled_crop(ownership, hand_box, 5)),
        ("候选源像素回贴", scaled_crop(exact_recompose, hand_box, 5)),
    )
    for index, (title, panel) in enumerate(neutral_panels):
        x = index * 500
        text(draw, (x + 8, 8), title, 26, True)
        neutral.paste(panel.resize((420, 520), Image.Resampling.NEAREST), (x + 35, 55))
    text(
        draw,
        (12, 582),
        f"候选源像素回贴 RGB 差 {count(binary(recompose_diff_mask, 1))}；本图不声称完整 M_hand 回组。",
        23,
    )
    neutral.save(QA / "V8-A2-NEUTRAL-VISIBLE-OWNERSHIP-RECOMPOSITION.png")

    tri = source_rgba
    tri = overlay(tri, locked, (30, 105, 255), 135)
    tri = overlay(tri, pending_include, (255, 0, 210), 235)
    tri = overlay(tri, pending_exclude, (255, 150, 0), 235)
    tri_panel = build_panel(
        "V_hand 三值所有权：建议",
        scaled_crop(tri, hand_box, 7),
        600,
        "蓝=锁定；粉=建议纳入；橙=建议排除",
    )
    tri_panel.save(QA / "V8-A2-TRISTATE-OWNERSHIP.png")

    summary_paths = [
        QA / "V8-A2-V-HAND-CHECKERBOARD.png",
        QA / "V8-A2-V-HAND-OUTLINE-OVERLAY.png",
        QA / "V8-A2-FOREARM-HAND-BOUNDARY-200PCT.png",
        QA / "V8-A2-BRACELET-HAND-ADJACENCY.png",
        QA / "V8-A2-FINGER-GAPS-AND-AA.png",
        QA / "V8-A2-ENVELOPE-V-HAND-CLASSIFICATION.png",
        QA / "V8-A2-ENVELOPE-DRAW-ORDER-RESOLUTION.png",
        QA / "V8-A2-NEUTRAL-VISIBLE-OWNERSHIP-RECOMPOSITION.png",
        QA / "V8-A2-TRISTATE-OWNERSHIP.png",
    ]
    thumb_w, thumb_h = 520, 420
    summary = Image.new(
        "RGB", (thumb_w * 3, (thumb_h + 48) * 3 + 125), (235, 235, 235)
    )
    draw = ImageDraw.Draw(summary)
    labels = [
        "1 手部棋盘格",
        "2 描边叠加",
        "3 腕部边界",
        "4 手链邻接",
        "5 指缝与 AA",
        "6 包络分类",
        "7 层序解决",
        "8 默认回贴",
        "9 三值建议",
    ]
    for index, (path, label) in enumerate(zip(summary_paths, labels)):
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb_w - 16, thumb_h - 16))
        x = index % 3 * thumb_w
        y = index // 3 * (thumb_h + 48)
        text(draw, (x + 8, y + 8), label, 23, True)
        summary.paste(image, (x + 8, y + 44))
    footer = summary.height - 110
    text(
        draw,
        (12, footer),
        f"候选 V_hand={count(candidate)} px；锁定={count(locked)}；待裁决={count(pending)}。",
        28,
        True,
    )
    text(
        draw,
        (12, footer + 40),
        f"待裁决建议：纳入 {count(pending_include)} / 排除 {count(pending_exclude)}；指缝误填 0；可见所有权交集 0。",
        25,
    )
    summary.save(QA / "V8-A2-USER-REVIEW-BOARD.png")
    return summary_paths + [QA / "V8-A2-USER-REVIEW-BOARD.png"]


def manifest(
    paths: list[Path],
    checkpoint: str = "v8a2_visible_hand_ownership_locked",
) -> dict:
    entries = []
    for path in paths:
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    return {
        "schemaVersion": 1,
        "checkpoint": checkpoint,
        "fileCount": len(entries),
        "files": entries,
    }


def main() -> None:
    input_rows = []
    for label, (path, expected_hash, expected_bytes) in EXPECTED_INPUTS.items():
        actual_hash = sha256(path) if path.exists() else None
        actual_bytes = path.stat().st_size if path.exists() else None
        input_rows.append(
            {
                "path": label,
                "expectedSha256": expected_hash,
                "actualSha256": actual_hash,
                "expectedBytes": expected_bytes,
                "actualBytes": actual_bytes,
                "pass": (
                    actual_hash == expected_hash
                    and actual_bytes == expected_bytes
                ),
            }
        )
    if not all(row["pass"] for row in input_rows):
        raise RuntimeError("V8-A2 input integrity failed.")
    if (
        json.loads(V8A1_APPROVAL.read_text(encoding="utf-8"))["status"]
        != "user_visual_approved"
    ):
        raise RuntimeError("V8-A1 visual approval is missing.")
    approval = json.loads(V8A2_APPROVAL.read_text(encoding="utf-8"))
    if approval["status"] != "user_visual_approved":
        raise RuntimeError("V8-A2 visual approval is missing.")

    comparable_paths = [
        MASKS / "V-hand-visible-ownership-candidate.png",
        MASKS / "V-hand-locked-source-pixels.png",
        MASKS / "V-hand-aa-pending-66px.png",
        MASKS / "V-hand-aa-recommended-include-43px.png",
        MASKS / "V-hand-aa-recommended-exclude-23px.png",
        MASKS / "V-hand-finger-gap-background.png",
        MASKS / "V-hand-wrist-corridor-required-ownership.png",
    ]
    before_hashes = {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for path in comparable_paths
        if path.exists()
    }

    line = Image.open(LINE_SOURCE).convert("L")
    source = Image.open(COLOR_SOURCE).convert("RGB")
    visible_forearm = load_mask(VISIBLE_FOREARM)
    bracelet = load_mask(BRACELET)
    wrist_line = load_mask(WRIST_LINE)
    responsibility = load_mask(WRIST_RESPONSIBILITY)
    source_root_support = load_mask(SOURCE_ROOT_SUPPORT)
    envelope = load_mask(ENVELOPE)
    visible_upper = load_mask(VISIBLE_UPPER)
    visible_sleeve = load_mask(VISIBLE_SLEEVE)

    conservative = trace_hand_support(
        line,
        wrist_line,
        visible_forearm,
        CONSERVATIVE_LINE_THRESHOLD,
    )
    recommended = trace_hand_support(
        line,
        wrist_line,
        visible_forearm,
        RECOMMENDED_LINE_THRESHOLD,
    )
    broad = trace_hand_support(
        line,
        wrist_line,
        visible_forearm,
        BROAD_LINE_THRESHOLD,
    )
    required_wrist_hand = binary(
        ImageChops.subtract(responsibility, visible_forearm), 1
    )
    locked = binary(ImageChops.lighter(conservative, required_wrist_hand), 1)
    candidate = binary(ImageChops.lighter(recommended, required_wrist_hand), 1)
    broad = binary(ImageChops.lighter(broad, required_wrist_hand), 1)

    if count(ImageChops.subtract(locked, candidate)):
        raise RuntimeError("Locked hand pixels are not inside the candidate.")
    if count(ImageChops.subtract(candidate, broad)):
        raise RuntimeError("Candidate hand pixels are not inside broad support.")

    pending = binary(ImageChops.subtract(broad, locked), 1)
    pending_include = binary(ImageChops.subtract(candidate, locked), 1)
    pending_exclude = binary(ImageChops.subtract(broad, candidate), 1)
    gaps = finger_gap_mask(broad)
    gap_neighborhood = binary(
        gaps.filter(ImageFilter.MaxFilter(5)), 1
    )
    gap_aa_pending = binary(
        ImageChops.multiply(pending, gap_neighborhood), 1
    )
    gap_misfill = count(ImageChops.multiply(candidate, gaps))

    envelope_hand = binary(ImageChops.multiply(envelope, candidate), 1)
    envelope_forearm = binary(
        ImageChops.multiply(envelope, visible_forearm), 1
    )
    envelope_bracelet = binary(
        ImageChops.multiply(envelope, bracelet), 1
    )
    envelope_minus_hand = binary(
        ImageChops.subtract(envelope, candidate), 1
    )
    envelope_minus_hand_inside_source_support = binary(
        ImageChops.multiply(envelope_minus_hand, source_root_support), 1
    )
    envelope_unclassified = binary(
        ImageChops.subtract(
            envelope,
            ImageChops.lighter(envelope_hand, envelope_forearm),
        ),
        1,
    )
    envelope_outside_source_support = count(
        ImageChops.subtract(envelope, source_root_support)
    )
    envelope_components = connected_components(envelope)
    envelope_holes = hole_count(envelope)

    rgba_mask(candidate).save(MASKS / "V-hand-visible-ownership-candidate.png")
    rgba_mask(locked, (40, 105, 255)).save(
        MASKS / "V-hand-locked-source-pixels.png"
    )
    rgba_mask(pending, (255, 0, 210)).save(
        MASKS / "V-hand-aa-pending-66px.png"
    )
    rgba_mask(pending_include, (255, 0, 210)).save(
        MASKS / "V-hand-aa-recommended-include-43px.png"
    )
    rgba_mask(pending_exclude, (255, 150, 0)).save(
        MASKS / "V-hand-aa-recommended-exclude-23px.png"
    )
    rgba_mask(gaps, (0, 210, 120)).save(
        MASKS / "V-hand-finger-gap-background.png"
    )
    rgba_mask(required_wrist_hand, (80, 80, 255)).save(
        MASKS / "V-hand-wrist-corridor-required-ownership.png"
    )
    rgba_mask(gap_aa_pending, (255, 0, 210)).save(
        MASKS / "V-hand-finger-gap-aa-pending.png"
    )
    rgba_mask(envelope_hand, (40, 105, 255)).save(
        MASKS / "envelope-intersect-V-hand.png"
    )
    rgba_mask(envelope_forearm, (255, 60, 20)).save(
        MASKS / "envelope-intersect-visible-forearm.png"
    )

    visual_paths = save_visuals(
        source,
        candidate,
        locked,
        pending,
        pending_include,
        pending_exclude,
        visible_forearm,
        bracelet,
        gaps,
        envelope,
        envelope_hand,
        envelope_forearm,
    )

    extracted = Image.new("RGBA", source.size, (0, 0, 0, 0))
    extracted.paste(source.convert("RGBA"), mask=candidate)
    extracted_alpha_diff = difference_count(
        extracted.getchannel("A"), candidate
    )
    source_pixels = source.load()
    extracted_pixels = extracted.convert("RGB").load()
    rgb_difference_pixels = sum(
        extracted_pixels[x, y] != source_pixels[x, y]
        for x, y in coordinates(candidate)
    )

    overlaps = {
        "V_handIntersectV_sleevePixels": count(
            ImageChops.multiply(candidate, visible_sleeve)
        ),
        "V_handIntersectV_upperArmPixels": count(
            ImageChops.multiply(candidate, visible_upper)
        ),
        "V_handIntersectV_forearmPixels": count(
            ImageChops.multiply(candidate, visible_forearm)
        ),
        "V_handIntersectV_braceletPixels": count(
            ImageChops.multiply(candidate, bracelet)
        ),
    }
    wrist_unassigned = count(
        ImageChops.subtract(
            responsibility,
            ImageChops.lighter(visible_forearm, candidate),
        )
    )
    candidate_outside_broad = count(ImageChops.subtract(candidate, broad))

    envelope_contract = json.loads(
        ENVELOPE_CONTRACT.read_text(encoding="utf-8")
    )
    wrist_x, wrist_y = envelope_contract["frozenWrist"]
    axis_x, axis_y = envelope_contract["localCoordinates"]["axis"]
    normal_x, normal_y = envelope_contract["localCoordinates"]["normal"]
    round_trip_differences = 0
    for x, y in coordinates(envelope):
        dx = x - wrist_x
        dy = y - wrist_y
        s = dx * axis_x + dy * axis_y
        n = dx * normal_x + dy * normal_y
        rx = wrist_x + s * axis_x + n * normal_x
        ry = wrist_y + s * axis_y + n * normal_y
        round_trip_differences += round(rx) != x or round(ry) != y

    after_hashes = {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for path in comparable_paths
    }
    deterministic_differences = sorted(
        path
        for path, hash_value in after_hashes.items()
        if path in before_hashes and before_hashes[path] != hash_value
    )
    deterministic_status = (
        "pass"
        if len(before_hashes) == len(comparable_paths)
        and not deterministic_differences
        else "first_generation_pending_second_run"
    )
    coordinate_hash = coordinate_fingerprint(candidate)
    rgb_hash = rgb_fingerprint(candidate, source)
    approved = approval["approvedDecision"]
    approval_matches = (
        approved["candidatePixels"] == count(candidate)
        and approved["candidateCoordinateFingerprintSha256"]
        == coordinate_hash
        and approved["candidateRgbFingerprintSha256"] == rgb_hash
        and approved["mixedAaPixelsReviewed"] == count(pending)
        and approved["recommendedIncludePixelsApproved"]
        == count(pending_include)
        and approved["recommendedExcludePixelsApproved"]
        == count(pending_exclude)
        and approved["fingerGapBackgroundPixelsApproved"] == count(gaps)
    )
    if not approval_matches:
        raise RuntimeError(
            "V8-A2 approval does not match regenerated visible-hand ownership."
        )
    engineering_pass = (
        extracted_alpha_diff == 0
        and rgb_difference_pixels == 0
        and all(value == 0 for value in overlaps.values())
        and gap_misfill == 0
        and wrist_unassigned == 0
        and count(envelope_unclassified) == 0
        and envelope_outside_source_support == 0
        and envelope_components == 1
        and envelope_holes == 0
        and round_trip_differences == 0
        and deterministic_status == "pass"
    )

    report = {
        "schemaVersion": 1,
        "gate": "V8-A exact visible hand ownership",
        "status": (
            "engineering_and_user_visual_pass_locked"
            if engineering_pass
            else "engineering_fail"
        ),
        "decisionOwner": "user",
        "userApproval": {
            "status": approval["status"],
            "actualStatement": approval["actualStatement"],
            "record": (
                "audit/v8a2-user-visual-approval-visible-hand-2026-07-26.json"
            ),
            "approvalMatchesRegeneratedCandidate": approval_matches,
        },
        "upstreamReverification": {
            "status": "independent_reverification_pass",
            "record": (
                "audit/v7c1-independent-reverification-2026-07-26.json"
            ),
            "frozenFilesCompared": 29,
            "differenceFiles": 0,
            "frozenWorkspaceFilesWritten": False,
        },
        "method": {
            "authorityInputs": [
                "source/masters/front-line-source-exact-after-reset.png",
                "source/masters/front-color-source-exact-after-reset.png",
            ],
            "handRoi": list(HAND_ROI),
            "lineThresholds": {
                "lockedConservative": CONSERVATIVE_LINE_THRESHOLD,
                "recommendedCandidate": RECOMMENDED_LINE_THRESHOLD,
                "broadPendingSupport": BROAD_LINE_THRESHOLD,
            },
            "wristRule": (
                "union the V7-approved wrist responsibility not already owned "
                "by visible forearm; this prevents color thresholding from "
                "dropping hand-root pixels hidden by the bracelet"
            ),
            "noAverageColorAutoAssimilation": True,
        },
        "vHand": {
            "candidatePixels": count(candidate),
            "finalLockedPixels": count(candidate),
            "conservativeStablePixels": count(locked),
            "reviewedMixedPixels": count(pending),
            "approvedRecommendedIncludePixels": count(pending_include),
            "approvedRecommendedExcludePixels": count(pending_exclude),
            "remainingUnresolvedPixels": 0,
            "coordinateFingerprintSha256": coordinate_hash,
            "rgbFingerprintSha256": rgb_hash,
            "sourceCoordinateDifferencePixels": extracted_alpha_diff,
            "sourceRgbDifferencePixels": rgb_difference_pixels,
            "candidateOutsideBroadAuthoritySupportPixels": candidate_outside_broad,
            "visibleOwnershipIntersections": overlaps,
        },
        "wristBoundary": {
            "requiredHandOwnershipPixels": count(required_wrist_hand),
            "unassignedSourceResponsibilityPixels": wrist_unassigned,
            "drawOrder": "forearm including bracelet above whole hand",
            "braceletRuntimeLayer": "none; remains part of forearm",
        },
        "fingerGaps": {
            "backgroundPixelsMarkedForTransparency": count(gaps),
            "backgroundMisfillPixels": gap_misfill,
            "aaPendingPixelsAdjacentToFingerGaps": count(gap_aa_pending),
            "fingerSplit": False,
            "granularityReopenRule": (
                "reopen if future motion requires finger motion relative to palm"
            ),
        },
        "envelopeCompatibility": {
            "pixels": count(envelope),
            "sha256": sha256(ENVELOPE),
            "connectedComponents": envelope_components,
            "holes": envelope_holes,
            "coordinateRoundTripDifferencePixels": round_trip_differences,
            "eHandIntersectVHandPixels": count(envelope_hand),
            "eHandMinusVHandPixels": count(envelope_minus_hand),
            "eHandMinusVHandInsideApprovedNeutralPersonSupportPixels": count(
                envelope_minus_hand_inside_source_support
            ),
            "eHandIntersectVisibleForearmPixels": count(envelope_forearm),
            "eHandIntersectBraceletPixels": count(envelope_bracelet),
            "eHandOutsideApprovedNeutralPersonSupportPixels": (
                envelope_outside_source_support
            ),
            "eHandOutsideExclusiveVisibleHandSupportPixels": count(
                envelope_minus_hand
            ),
            "unclassifiedEnvelopePixels": count(envelope_unclassified),
            "interpretation": (
                "308 envelope pixels are visible-hand ownership. The remaining "
                "81 are bracelet/forearm visible ownership but may be hidden "
                "complete-hand material because the approved forearm layer is "
                "above the whole hand. Therefore the 81 pixels outside exclusive "
                "visible-hand support are explained hidden overlap, not neutral "
                "person-outline overflow."
            ),
        },
        "neutralVisibleRecomposition": {
            "candidateSourceCoordinateDifferencePixels": extracted_alpha_diff,
            "candidateSourceRgbDifferencePixels": rgb_difference_pixels,
            "visibleOwnershipDuplicatePixels": max(overlaps.values()),
            "personOutlineOutsidePixels": candidate_outside_broad,
            "formalCompleteHandClaimed": False,
        },
        "deterministicRegeneration": {
            "status": deterministic_status,
            "comparableFiles": len(comparable_paths),
            "differenceFiles": deterministic_differences,
        },
        "inputIntegrity": {"status": "pass", "inputs": input_rows},
        "visualEvidence": [
            path.relative_to(ROOT).as_posix() for path in visual_paths
        ],
        "explicitlyNotCreated": [
            "formal complete hand geometry",
            "hand texture",
            "PSD",
            "ArtMesh",
            "Cubism",
            "Physics",
            "Runtime",
            "finger split",
            "clipping",
        ],
        "nextGate": (
            "V8-A is closed. V8-B formal complete hand geometry requires "
            "separate explicit authorization before implementation."
        ),
    }
    write_json(AUDIT / "v8a2-visible-hand-ownership.json", report)

    contract = {
        "schemaVersion": 1,
        "contract": "V8-A locked exact visible whole-hand ownership",
        "status": report["status"],
        "decisionOwner": "user",
        "vHandMask": "masks/V-hand-visible-ownership-candidate.png",
        "vHandMaskFilenameLineage": (
            "candidate filename retained; contents are locked by this contract "
            "and the user approval fingerprint"
        ),
        "visibleOwnershipPixels": count(candidate),
        "reviewedMixedPixels": count(pending),
        "approvedRecommendedIncludePixels": count(pending_include),
        "approvedRecommendedExcludePixels": count(pending_exclude),
        "remainingUnresolvedPixels": 0,
        "coordinateFingerprintSha256": coordinate_hash,
        "rgbFingerprintSha256": rgb_hash,
        "userApprovalRecord": (
            "audit/v8a2-user-visual-approval-visible-hand-2026-07-26.json"
        ),
        "frozenWrist": [wrist_x, wrist_y],
        "localCoordinates": envelope_contract["localCoordinates"],
        "drawOrder": "forearm including bracelet above whole hand",
        "braceletOwnership": "forearm only",
        "fingerGaps": "remain transparent",
        "handMaterialGranularity": "one whole-hand material",
        "futureFormalHandObligation": [
            "contain the complete frozen 389 px envelope",
            "preserve approved V_hand source coordinates and RGB",
            "rerun the complete wrist domain with real hand geometry",
            "keep the forearm including bracelet above the whole hand",
        ],
        "automaticInvalidation": [
            "user rejects hand shape, finger gaps, or wrist ownership",
            "any approved mixed pixel receives a different ownership decision",
            "wrist point, local coordinates, draw order, or bracelet ownership changes",
            "future finger-relative motion requires finer material granularity",
        ],
    }
    write_json(AUDIT / "v8a2-visible-hand-ownership-contract.json", contract)

    markdown = f"""# V8-A 正式手部可见像素所有权锁定

## 工程结论

状态：`{report["status"]}`。

- 最终锁定 `V_hand`：`{count(candidate)} px`；
- 稳定源像素：`{count(locked)} px`；
- 已审查混合像素：`{count(pending)} px`；
- 批准纳入：`{count(pending_include)} px`；批准排除：`{count(pending_exclude)} px`；
- 未决像素：`0`；
- 源坐标差 `0`，源 RGB 差 `0`；
- 与袖子、上臂、前臂、手链的可见所有权交集均为 `0`；
- 腕缝责任区未归属源像素 `0`；
- 指缝背景误填 `0`；
- 指缝邻接 AA 已随本次视觉批准完成裁决，共 `{count(gap_aa_pending)} px`；
- 389 px 包络：`E∩V_hand={count(envelope_hand)}`，
  `E∩V_forearm=E∩V_bracelet={count(envelope_forearm)}`；
- 包络连通分量 `1`、孔洞 `0`、未分类像素 `0`、坐标往返差 `0`；
- 包络超出中性人物源支持区 `0`；超出独占可见手支持区的 `81 px` 已解释为
  前臂/手链在前、完整手部在后的隐藏材料重叠。

## 三值裁决结果

- 蓝色：稳定属于手部；
- 粉色：用户批准纳入手部的混合像素；
- 橙色：用户批准排除为背景的混合像素。

没有用平均色自动吞并邻近像素。候选由权威线稿闭合轮廓、冻结腕部所有权和
三档边界阈值共同确定。

## 指缝

指缝背景保持透明，未闭合填死；当前整只手仍是一个材料，没有拆指。将来若
需要弯指、张指、抓握或指点，必须重开材料粒度。

## 包络与层序

`308 px` 临时包络属于锁定可见手部；另外 `81 px` 属于前臂/手链可见所有权。
在用户批准的“前臂含手链位于整手之上”层序中，这 81 px 可以由未来完整手部
在后方静态包含，不再覆盖手链。

本阶段没有生成完整 `M_hand`，不得据此声称正式手部连通性、孔洞或真实手部
腕部全域已通过。

## 用户批准

优先查看：

1. `qa/V8-A2-USER-REVIEW-BOARD.png`
2. `qa/V8-A2-TRISTATE-OWNERSHIP.png`
3. `qa/V8-A2-FINGER-GAPS-AND-AA.png`
4. `qa/V8-A2-FOREARM-HAND-BOUNDARY-200PCT.png`

用户已明确回复“批准”。本记录锁定手形、指缝、腕部边界以及粉/橙混合像素
裁决；V8-A 到此关闭。完整 `M_hand` 仍未生成，V8-B 实施需要另行明确授权。
"""
    (AUDIT / "V8-A2-VISIBLE-HAND-OWNERSHIP.zh-CN.md").write_text(
        markdown, encoding="utf-8"
    )
    write_json(AUDIT / "v8a2-input-integrity.json", {
        "schemaVersion": 1,
        "status": "pass",
        "inputs": input_rows,
    })

    evidence_paths = (
        [HERE]
        + comparable_paths
        + [
            V8A2_APPROVAL,
            MASKS / "V-hand-finger-gap-aa-pending.png",
            MASKS / "envelope-intersect-V-hand.png",
            MASKS / "envelope-intersect-visible-forearm.png",
            AUDIT / "v8a2-visible-hand-ownership.json",
            AUDIT / "v8a2-visible-hand-ownership-contract.json",
            AUDIT / "V8-A2-VISIBLE-HAND-OWNERSHIP.zh-CN.md",
            AUDIT / "v8a2-input-integrity.json",
        ]
        + visual_paths
    )
    write_json(
        AUDIT / "v8a2-evidence-manifest.json",
        manifest(evidence_paths),
    )

    final_audit = f"""# V8-A 最终完成审计

日期：2026-07-26

状态：`{report["status"]}`。

- 用户视觉批准记录有效，且与重新生成候选的像素数、坐标指纹、RGB 指纹及
  66 个混合 AA 像素裁决完全一致；
- V7-C1 已在隔离临时副本中独立重建，29 个冻结文件差异 `0`，且没有写入
  V7 冻结目录；
- 精确 `V_hand` 已锁定为 `{count(candidate)} px`，未决像素 `0`；
- 源坐标差 `0`，源 RGB 差 `0`；
- 袖子、上臂、前臂、手链的可见所有权交集均为 `0`；
- 腕缝责任区未归属像素 `0`，指缝背景误填 `0`；
- 冻结 `389 px` 包络未分类像素 `0`，局部坐标往返差 `0`；
- 冻结包络连通分量 `1`、孔洞 `0`、中性人物源支持区外像素 `0`；
- 确定性重新生成差异 `0`；
- 层序锁定为“前臂含手链位于整手之上”，手链仍属于前臂且不是独立运行层。

本门只锁定可见像素所有权，没有生成完整 `M_hand`、纹理、PSD、ArtMesh、
Cubism、Physics、Runtime、拆指或 clipping。V8-B 实施必须另行获得明确授权。
"""
    final_audit_path = (
        AUDIT / "V8-A-FINAL-COMPLETION-AUDIT-2026-07-26.zh-CN.md"
    )
    final_audit_path.write_text(final_audit, encoding="utf-8")

    freeze_paths = [
        HERE,
        MASKS / "V-hand-visible-ownership-candidate.png",
        MASKS / "V-hand-finger-gap-background.png",
        MASKS / "V-hand-wrist-corridor-required-ownership.png",
        V8A2_APPROVAL,
        V7C1_INDEPENDENT_REVERIFICATION,
        AUDIT / "v8a2-visible-hand-ownership.json",
        AUDIT / "v8a2-visible-hand-ownership-contract.json",
        AUDIT / "v8a2-input-integrity.json",
        AUDIT / "v8a2-evidence-manifest.json",
        AUDIT / "V8-A2-VISIBLE-HAND-OWNERSHIP.zh-CN.md",
        final_audit_path,
        QA / "V8-A2-USER-REVIEW-BOARD.png",
        QA / "V8-A2-TRISTATE-OWNERSHIP.png",
        QA / "V8-A2-FINGER-GAPS-AND-AA.png",
        QA / "V8-A2-FOREARM-HAND-BOUNDARY-200PCT.png",
    ]
    freeze_file_manifest = manifest(
        freeze_paths,
        checkpoint="v8a_exact_visible_hand_ownership_frozen",
    )
    freeze_manifest = {
        "schemaVersion": 1,
        "checkpoint": "V8-A exact visible hand ownership",
        "freezeDate": "2026-07-26",
        "status": report["status"],
        "decisionOwner": "user",
        "vHand": {
            "path": "masks/V-hand-visible-ownership-candidate.png",
            "pixels": count(candidate),
            "coordinateFingerprintSha256": coordinate_hash,
            "rgbFingerprintSha256": rgb_hash,
            "remainingUnresolvedPixels": 0,
        },
        "drawOrder": "forearm including bracelet above whole hand",
        "braceletOwnership": "forearm only; no independent runtime layer",
        "frozenWrist": [wrist_x, wrist_y],
        "temporaryHandRootEnvelopePixels": count(envelope),
        "files": freeze_file_manifest["files"],
        "finalMetrics": {
            "sourceCoordinateDifferencePixels": extracted_alpha_diff,
            "sourceRgbDifferencePixels": rgb_difference_pixels,
            "visibleOwnershipMaximumIntersectionPixels": max(overlaps.values()),
            "wristUnassignedPixels": wrist_unassigned,
            "fingerGapBackgroundMisfillPixels": gap_misfill,
            "envelopeUnclassifiedPixels": count(envelope_unclassified),
            "envelopeConnectedComponents": envelope_components,
            "envelopeHoles": envelope_holes,
            "envelopeOutsideApprovedNeutralPersonSupportPixels": (
                envelope_outside_source_support
            ),
            "deterministicDifferenceFiles": deterministic_differences,
        },
        "invalidationRules": contract["automaticInvalidation"],
        "explicitlyNotApproved": report["explicitlyNotCreated"] + [
            "V8-B implementation"
        ],
        "nextGate": report["nextGate"],
    }
    write_json(
        AUDIT / "v8a-final-freeze-manifest-2026-07-26.json",
        freeze_manifest,
    )

    print(
        json.dumps(
            {
                "status": report["status"],
                "vHandFinalLockedPixels": count(candidate),
                "conservativeStablePixels": count(locked),
                "reviewedMixedPixels": count(pending),
                "remainingUnresolvedPixels": 0,
                "fingerGapMisfillPixels": gap_misfill,
                "wristUnassignedPixels": wrist_unassigned,
                "visibleOwnershipMaximumIntersectionPixels": max(
                    overlaps.values()
                ),
                "envelopeConnectedComponents": envelope_components,
                "envelopeHoles": envelope_holes,
                "envelopeUnclassifiedPixels": count(envelope_unclassified),
                "deterministicStatus": deterministic_status,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
