from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parents[1]
PARTS = ROOT / "parts-v5"
QA = ROOT / "qa"
CANVAS = (1370, 1148)

FULL = ROOT / "candidates" / "xiaoju-fullbody-volume-v5-alpha.png"
BODY = ROOT / "candidates" / "xiaoju-body-no-forelegs-v5-alpha.png"
INPAINT = ROOT / "candidates" / "xiaoju-limbless-inpaint-v6-rejected-whole-alpha.png"
EXACT = PACKAGE / "live2d" / "planet-scene-source" / "layers-v2" / "10_Cat_Body_Base.png"


def normalized(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if image.size != CANVAS:
        image = image.resize(CANVAS, Image.Resampling.LANCZOS)
    red, green, blue, alpha = image.split()
    dominant_other = ImageChops.lighter(red, blue)
    green_excess = ImageChops.subtract(green, dominant_other)
    residue = green_excess.point(lambda value: 255 if value > 18 else 0)
    alpha = ImageChops.subtract(alpha, residue)
    image.putalpha(alpha)
    return image


def masked(source: Image.Image, points: list[tuple[int, int]], blur: float = 4) -> Image.Image:
    mask = Image.new("L", CANVAS, 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon(points, fill=255)
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    alpha = source.getchannel("A")
    source = source.copy()
    source.putalpha(Image.composite(alpha, Image.new("L", CANVAS, 0), mask))
    return source


def strip_green_residue(source: Image.Image) -> Image.Image:
    """Remove chroma pixels reintroduced by blurred RGBA mask compositing."""
    red, green, blue, alpha = source.split()
    dominant_other = ImageChops.lighter(red, blue)
    green_excess = ImageChops.subtract(green, dominant_other)
    residue = green_excess.point(lambda value: 255 if value > 18 else 0)
    cleaned = source.copy()
    cleaned.putalpha(ImageChops.subtract(alpha, residue))
    return cleaned


def capsule_masked(
    source: Image.Image,
    proximal: tuple[int, int],
    distal: tuple[int, int],
    radius: int,
    blur: float = 5,
) -> Image.Image:
    """Keep a fur-covered rounded bone segment without rectangular cut ends."""
    mask = Image.new("L", CANVAS, 0)
    draw = ImageDraw.Draw(mask)
    draw.line((proximal, distal), fill=255, width=radius * 2)
    for x, y in (proximal, distal):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
    if blur:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    alpha = source.getchannel("A")
    result = source.copy()
    result.putalpha(Image.composite(alpha, Image.new("L", CANVAS, 0), mask))
    return result


PARTS.mkdir(parents=True, exist_ok=True)
full = normalized(FULL)
body_source = normalized(BODY)
inpaint_source = normalized(INPAINT)
exact_source = normalized(EXACT)

# The v6 whole silhouette is rejected, but the pixels under the near hind leg
# and tail root are useful as local inpaint. Restrict it to those occluded
# zones so it cannot replace the approved v5 ribcage/pelvis volume.
inpaint_mask = Image.new("L", CANVAS, 0)
inpaint_draw = ImageDraw.Draw(inpaint_mask)
inpaint_draw.polygon(((70, 520), (450, 520), (500, 960), (360, 1080), (70, 1020)), fill=255)
inpaint_draw.polygon(((270, 625), (735, 610), (785, 1065), (300, 1110)), fill=255)
inpaint_mask = inpaint_mask.filter(ImageFilter.GaussianBlur(24))
body_core_source = Image.composite(inpaint_source, body_source, inpaint_mask)

# Body layer excludes the generated face and the tail. It retains chest,
# abdomen, pelvis and folded hind limbs as a continuous hidden base.
body = masked(
    body_core_source,
    [(300, 660), (620, 625), (1020, 640), (1160, 760), (1160, 1000), (1010, 1085), (330, 1090), (270, 880)],
    blur=14,
)

# Independent overlapping volume zones. They retain a hidden base underneath
# for safety, but Cubism deformation will bind ribcage, belly contact, and
# pelvis separately so contact compression cannot pancake the whole torso.
ribcage = masked(
    body,
    [(470, 610), (930, 600), (1135, 705), (1120, 925), (945, 1045), (600, 1015), (445, 805)],
    blur=18,
)
belly = masked(
    body,
    [(430, 790), (760, 735), (1060, 825), (1050, 1085), (455, 1095), (335, 965)],
    blur=18,
)
pelvis = masked(
    body,
    [(285, 625), (650, 610), (780, 790), (720, 1088), (315, 1095), (260, 865)],
    blur=18,
)

neck_fill = masked(
    exact_source,
    [(385, 485), (720, 520), (790, 690), (725, 825), (425, 840), (390, 700)],
    blur=10,
)

# Tail stays a unique visual source. v5 provides a complete root overlap;
# the approved visible tail can remain above it until final retouch.
tail = masked(
    body_source,
    [(75, 545), (355, 540), (445, 720), (430, 985), (250, 1050), (75, 920)],
    blur=6,
)

hindleg_near = masked(
    body_source,
    [(330, 620), (560, 610), (725, 790), (710, 975), (475, 1010), (325, 920)],
    blur=6,
)
hindpaw_near = masked(
    body_source,
    [(405, 925), (675, 910), (730, 1085), (390, 1125), (365, 1010)],
    blur=5,
)


def inferred_far_part(source: Image.Image, target_x: int, target_y: int, scale: float, rotation_deg: float) -> Image.Image:
    bbox = source.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("cannot mirror empty hind-limb source")
    crop = source.crop(bbox).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.LANCZOS)
    crop = crop.rotate(rotation_deg, resample=Image.Resampling.BICUBIC, expand=True)
    result = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    result.alpha_composite(crop, (target_x, target_y))
    return result


# The far hind limb is normally fully occluded. Infer its bilateral anatomy from
# the near limb, then apply perspective foreshortening and a small plane-angle
# rotation. It remains explicitly labelled INFERRED and sits behind the body.
hindleg_far = inferred_far_part(hindleg_near, 720, 665, 0.82, -4.0)
hindpaw_far = inferred_far_part(hindpaw_near, 820, 915, 0.82, -3.0)

hind_segments = {
    "44_Hip_Near_v5.png": masked(hindleg_near, [(290, 580), (585, 575), (660, 780), (555, 905), (300, 855)], blur=8),
    "45_Thigh_Near_v5.png": masked(hindleg_near, [(315, 675), (645, 640), (750, 890), (650, 1035), (350, 1015)], blur=8),
    "46_Hock_Near_v5.png": masked(hindleg_near, [(455, 825), (735, 805), (760, 1035), (480, 1060)], blur=7),
    "47_Hip_Far_v5_INFERRED.png": masked(hindleg_far, [(715, 650), (960, 650), (1090, 805), (1010, 915), (745, 875)], blur=8),
    "48_Thigh_Far_v5_INFERRED.png": masked(hindleg_far, [(735, 735), (1060, 700), (1100, 930), (1010, 1045), (760, 1015)], blur=8),
    "49_Hock_Far_v5_INFERRED.png": masked(hindleg_far, [(850, 835), (1090, 820), (1115, 1040), (860, 1060)], blur=7),
}

# Each forelimb includes a deliberately broad shoulder-root overlap, but not a
# second paw or the opposite limb. These are still complete-limb trial layers;
# Gate 3 will split shoulder/upper arm/forearm/wrist/paw after this QA passes.
foreleg_view_l = masked(
    full,
    [(555, 650), (740, 620), (815, 710), (925, 845), (1060, 970), (1045, 1090), (815, 1110), (700, 965), (580, 830)],
    blur=4,
)
foreleg_view_r = masked(
    full,
    [(900, 640), (1050, 610), (1120, 700), (1280, 845), (1285, 1015), (1090, 1035), (1010, 890), (915, 760)],
    blur=4,
)

segment_specs = {
    "62_ShoulderFill_ViewL_v5.png": [(535, 625), (760, 615), (825, 720), (770, 845), (600, 835), (535, 735)],
    "63_UpperArm_ViewL_v5.png": [(550, 645), (740, 615), (830, 740), (805, 865), (650, 890), (575, 820)],
    "64_Forearm_ViewL_v5.png": [(645, 775), (820, 715), (935, 850), (970, 970), (820, 1010), (695, 930)],
    "65_Paw_ViewL_v5.png": [(785, 945), (970, 915), (1070, 970), (1055, 1125), (805, 1125), (765, 1035)],
    "66_ShoulderFill_ViewR_v5.png": [(890, 625), (1050, 605), (1135, 720), (1085, 830), (940, 805), (895, 720)],
    "67_UpperArm_ViewR_v5.png": [(895, 635), (1050, 605), (1135, 745), (1105, 855), (975, 875), (915, 760)],
    "68_Forearm_ViewR_v5.png": [(985, 745), (1130, 695), (1200, 820), (1180, 930), (1070, 940), (1035, 880)],
    "69_Paw_ViewR_v5.png": [(1075, 895), (1275, 855), (1305, 1020), (1085, 1045), (1045, 980)],
}
segments = {}
for name, points in segment_specs.items():
    # Intersect every joint segment with its already isolated complete limb.
    # This prevents broad overlap polygons from carrying unrelated chest/face
    # pixels that only become visible when the arm rotates away from rest.
    limb_source = foreleg_view_l if "ViewL" in name else foreleg_view_r
    segments[name] = masked(limb_source, points, blur=5)

# Replace the two rotating bone spans with rounded capsule masks. Polygonal
# shoulder overlaps stay chest-owned; paw masks keep their real fur silhouette.
# This specifically removes the square texture plates exposed at large angles.
segments["63_UpperArm_ViewL_v5.png"] = capsule_masked(foreleg_view_l, (650, 700), (760, 820), 92)
segments["64_Forearm_ViewL_v5.png"] = capsule_masked(foreleg_view_l, (760, 820), (875, 960), 82)
segments["67_UpperArm_ViewR_v5.png"] = capsule_masked(foreleg_view_r, (1000, 685), (1080, 790), 84)
segments["68_Forearm_ViewR_v5.png"] = capsule_masked(foreleg_view_r, (1080, 790), (1135, 900), 72)

# Approved head only: remove the old long neck/body cutout and tail so the QA
# cannot accidentally hide missing body anatomy.
head = masked(
    exact_source,
    [(350, 0), (1175, 0), (1190, 650), (1040, 775), (650, 805), (410, 690), (350, 500)],
    blur=10,
)

outputs = {
    "10_Body_HiddenBase_v5.png": body,
    "11_Ribcage_Hidden_v5.png": ribcage,
    "12_Belly_Hidden_v5.png": belly,
    "13_Pelvis_Hidden_v5.png": pelvis,
    "15_NeckFill_Approved.png": neck_fill,
    "20_Head_Approved.png": head,
    "30_Tail_Complete_v5.png": tail,
    "40_HindLeg_Near_v5.png": hindleg_near,
    "41_HindPaw_Near_v5.png": hindpaw_near,
    "42_HindLeg_Far_v5_INFERRED.png": hindleg_far,
    "43_HindPaw_Far_v5_INFERRED.png": hindpaw_far,
    **hind_segments,
    "60_Foreleg_ViewL_Complete_v5.png": foreleg_view_l,
    "61_Foreleg_ViewR_Complete_v5.png": foreleg_view_r,
    **segments,
}
for name, image in outputs.items():
    image = strip_green_residue(image)
    outputs[name] = image
    image.save(PARTS / name)

# Continue QA from the exact cleaned layers written to disk, so a clean audit
# cannot disagree with the contact sheets because of stale in-memory pixels.
body = outputs["10_Body_HiddenBase_v5.png"]
ribcage = outputs["11_Ribcage_Hidden_v5.png"]
belly = outputs["12_Belly_Hidden_v5.png"]
pelvis = outputs["13_Pelvis_Hidden_v5.png"]
neck_fill = outputs["15_NeckFill_Approved.png"]
head = outputs["20_Head_Approved.png"]
tail = outputs["30_Tail_Complete_v5.png"]
hindleg_near = outputs["40_HindLeg_Near_v5.png"]
hindpaw_near = outputs["41_HindPaw_Near_v5.png"]
hindleg_far = outputs["42_HindLeg_Far_v5_INFERRED.png"]
hindpaw_far = outputs["43_HindPaw_Far_v5_INFERRED.png"]
foreleg_view_l = outputs["60_Foreleg_ViewL_Complete_v5.png"]
foreleg_view_r = outputs["61_Foreleg_ViewR_Complete_v5.png"]
segments = {name: outputs[name] for name in segment_specs}
hind_segments = {name: outputs[name] for name in hind_segments}

expanded = Image.new("RGBA", CANVAS, (20, 22, 28, 255))
for layer in (tail, hindleg_far, hindpaw_far, body, hindleg_near, hindpaw_near, foreleg_view_l, foreleg_view_r, neck_fill, head):
    expanded.alpha_composite(layer)
expanded.save(QA / "gate3-v5-parts-expanded.png")

segmented = Image.new("RGBA", CANVAS, (20, 22, 28, 255))
for layer in (tail, body, hindleg_near, hindpaw_near, *segments.values(), neck_fill, head):
    segmented.alpha_composite(layer)
segmented.save(QA / "gate3-v5-segmented-expanded.png")

full_anatomy = Image.new("RGBA", CANVAS, (20, 22, 28, 255))
for layer in (tail, hindleg_far, hindpaw_far, body, hindleg_near, hindpaw_near, *segments.values(), neck_fill, head):
    full_anatomy.alpha_composite(layer)
full_anatomy.save(QA / "gate3-v5-inferred-full-anatomy.png")

volume_zones = Image.new("RGBA", (450 * 3, 520), (20, 22, 28, 255))
volume_draw = ImageDraw.Draw(volume_zones)
for index, (label, layer) in enumerate((("Pelvis", pelvis), ("Ribcage", ribcage), ("Belly / contact band", belly))):
    bbox = layer.getchannel("A").getbbox()
    crop = layer.crop(bbox)
    crop.thumbnail((420, 430), Image.Resampling.LANCZOS)
    x = index * 450 + (450 - crop.width) // 2
    y = 62 + (430 - crop.height) // 2
    volume_zones.alpha_composite(crop, (x, y))
    volume_draw.text((index * 450 + 14, 18), label, fill=(255, 255, 255, 255))
volume_zones.save(QA / "gate3-v5-body-volume-zones.png")

isolated = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
isolated.alpha_composite(foreleg_view_l)
isolated.alpha_composite(foreleg_view_r)
isolated.save(QA / "gate3-v5-forelegs-only.png")

# Inspect every segment away from the body. This catches a layer that still
# contains a second paw, face pixels, or an excessive torso patch before PSD
# import. Crops retain transparent padding and are scaled uniformly per cell.
font = None
cell_w, cell_h = 340, 330
sheet = Image.new("RGBA", (cell_w * 4, cell_h * 2), (20, 22, 28, 255))
sheet_draw = ImageDraw.Draw(sheet)
for index, (name, segment) in enumerate(segments.items()):
    bbox = segment.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"empty segment: {name}")
    crop = segment.crop(bbox)
    crop.thumbnail((cell_w - 30, cell_h - 55), Image.Resampling.LANCZOS)
    x = (index % 4) * cell_w + (cell_w - crop.width) // 2
    y = (index // 4) * cell_h + 32 + (cell_h - 55 - crop.height) // 2
    sheet.alpha_composite(crop, (x, y))
    sheet_draw.text(((index % 4) * cell_w + 10, (index // 4) * cell_h + 8), name[3:-4], fill=(255, 255, 255, 255), font=font)
sheet.save(QA / "gate3-v5-foreleg-segments-contact-sheet.png")

hind_cell_w, hind_cell_h = 330, 300
hind_sheet = Image.new("RGBA", (hind_cell_w * 3, hind_cell_h * 2), (20, 22, 28, 255))
hind_draw = ImageDraw.Draw(hind_sheet)
for index, (name, segment) in enumerate(hind_segments.items()):
    bbox = segment.getchannel("A").getbbox()
    crop = segment.crop(bbox)
    crop.thumbnail((hind_cell_w - 28, hind_cell_h - 56), Image.Resampling.LANCZOS)
    x = (index % 3) * hind_cell_w + (hind_cell_w - crop.width) // 2
    y = (index // 3) * hind_cell_h + 38 + (hind_cell_h - 56 - crop.height) // 2
    hind_sheet.alpha_composite(crop, (x, y))
    hind_draw.text(((index % 3) * hind_cell_w + 10, (index // 3) * hind_cell_h + 10), name[3:-4], fill=(255, 255, 255, 255))
hind_sheet.save(QA / "gate3-v5-hindleg-segments-contact-sheet.png")

print(PARTS)
print(QA / "gate3-v5-parts-expanded.png")
print(QA / "gate3-v5-segmented-expanded.png")
print(QA / "gate3-v5-forelegs-only.png")
print(QA / "gate3-v5-foreleg-segments-contact-sheet.png")
print(QA / "gate3-v5-inferred-full-anatomy.png")
print(QA / "gate3-v5-body-volume-zones.png")
print(QA / "gate3-v5-hindleg-segments-contact-sheet.png")
