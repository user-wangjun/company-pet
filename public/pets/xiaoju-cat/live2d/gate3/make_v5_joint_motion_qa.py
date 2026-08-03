import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
PARTS = ROOT / "parts-v5"
QA = ROOT / "qa"
CANVAS = (1370, 1148)


def load(name: str) -> Image.Image:
    return Image.open(PARTS / name).convert("RGBA")


def point_from(origin: tuple[float, float], length: float, angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    return origin[0] + math.cos(angle) * length, origin[1] + math.sin(angle) * length


def rigid_map(
    image: Image.Image,
    source_proximal: tuple[float, float],
    source_distal: tuple[float, float],
    target_proximal: tuple[float, float],
    target_distal: tuple[float, float],
) -> Image.Image:
    source_angle = math.atan2(source_distal[1] - source_proximal[1], source_distal[0] - source_proximal[0])
    target_angle = math.atan2(target_distal[1] - target_proximal[1], target_distal[0] - target_proximal[0])
    angle = target_angle - source_angle
    c, s = math.cos(angle), math.sin(angle)

    # PIL requests the inverse map from destination pixels back to source.
    a, b = c, s
    d, e = -s, c
    tx = source_proximal[0] - (c * target_proximal[0] + s * target_proximal[1])
    ty = source_proximal[1] - (-s * target_proximal[0] + c * target_proximal[1])
    return image.transform(CANVAS, Image.Transform.AFFINE, (a, b, tx, d, e, ty), Image.Resampling.BICUBIC)


def alpha_overlap(a: Image.Image, b: Image.Image) -> int:
    aa = a.getchannel("A")
    bb = b.getchannel("A")
    return sum(value > 0 for value in Image.composite(aa, Image.new("L", CANVAS), bb).get_flattened_data())


CHAINS = {
    "ViewL": {
        "source": [(650.0, 700.0), (760.0, 820.0), (875.0, 960.0), (950.0, 1010.0)],
        "files": [
            "62_ShoulderFill_ViewL_v5.png",
            "63_UpperArm_ViewL_v5.png",
            "64_Forearm_ViewL_v5.png",
            "65_Paw_ViewL_v5.png",
        ],
        "expandedAngles": [160.0, 215.0, 200.0],
        # Elbow stays outside the ribcage; the forearm folds back toward the
        # face and the paw hangs down over the orbit. This avoids the earlier
        # human-like straight overhead reach.
        "coverAngles": [170.0, -50.0, 75.0],
    },
    "ViewR": {
        "source": [(1000.0, 685.0), (1080.0, 790.0), (1135.0, 900.0), (1190.0, 925.0)],
        "files": [
            "66_ShoulderFill_ViewR_v5.png",
            "67_UpperArm_ViewR_v5.png",
            "68_Forearm_ViewR_v5.png",
            "69_Paw_ViewR_v5.png",
        ],
        "expandedAngles": [-20.0, -40.0, -25.0],
        "coverAngles": [10.0, -120.0, 105.0],
    },
}


def target_joints(source: list[tuple[float, float]], angles: list[float]) -> list[tuple[float, float]]:
    lengths = [math.dist(source[index], source[index + 1]) for index in range(3)]
    target = [source[0]]
    for length, angle in zip(lengths, angles):
        target.append(point_from(target[-1], length, angle))
    return target


def pose_layers(chain: dict, joints: list[tuple[float, float]]) -> list[Image.Image]:
    source = chain["source"]
    original = [load(name) for name in chain["files"]]
    # Shoulder fill is chest-owned and remains fixed; the three distal layers
    # receive exact rigid transforms, preserving every bone-segment length.
    return [
        original[0],
        rigid_map(original[1], source[0], source[1], joints[0], joints[1]),
        rigid_map(original[2], source[1], source[2], joints[1], joints[2]),
        rigid_map(original[3], source[2], source[3], joints[2], joints[3]),
    ]


def render_pose(
    name: str,
    joint_sets: dict[str, list[tuple[float, float]]],
    draw_joints: bool = True,
    cover_occlusion: bool | None = None,
    analyze: bool = True,
) -> tuple[Image.Image, dict]:
    background = Image.new("RGBA", CANVAS, (20, 22, 28, 255))
    transformed = {side: pose_layers(CHAINS[side], joint_sets[side]) for side in CHAINS}

    background.alpha_composite(load("30_Tail_Complete_v5.png"))
    if cover_occlusion is None:
        cover_occlusion = name == "cover"
    if cover_occlusion:
        # During face cover the upper arms pass behind the chest/head silhouette.
        # A draw-order keyform is required; otherwise a perfectly connected
        # elbow can appear as a floating orange capsule beside the body.
        for side in ("ViewL", "ViewR"):
            background.alpha_composite(transformed[side][1])

    for layer_name in ("10_Body_HiddenBase_v5.png", "40_HindLeg_Near_v5.png", "41_HindPaw_Near_v5.png"):
        background.alpha_composite(load(layer_name))

    for side in ("ViewL", "ViewR"):
        if cover_occlusion:
            background.alpha_composite(transformed[side][0])
            background.alpha_composite(transformed[side][2])
        else:
            for layer in transformed[side][:-1]:
                background.alpha_composite(layer)

    # Approved head remains above the arm bones, while paws contact the face in
    # front. This reproduces the intended occlusion logic for password cover.
    background.alpha_composite(load("15_NeckFill_Approved.png"))
    background.alpha_composite(load("20_Head_Approved.png"))
    for side in ("ViewL", "ViewR"):
        background.alpha_composite(transformed[side][-1])

    draw = ImageDraw.Draw(background)
    report = {"pose": name, "chains": {}}
    for side, joints in joint_sets.items():
        if draw_joints:
            for x, y in joints:
                draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(80, 220, 255, 255), outline=(255, 255, 255, 255), width=2)
        source = CHAINS[side]["source"]
        source_lengths = [math.dist(source[index], source[index + 1]) for index in range(3)]
        target_lengths = [math.dist(joints[index], joints[index + 1]) for index in range(3)]
        overlaps = [alpha_overlap(transformed[side][index], transformed[side][index + 1]) for index in range(3)] if analyze else []
        report["chains"][side] = {
            "sourceLengthsPx": [round(value, 3) for value in source_lengths],
            "targetLengthsPx": [round(value, 3) for value in target_lengths],
            "maxLengthDriftPx": round(max(abs(a - b) for a, b in zip(source_lengths, target_lengths)), 6),
            "adjacentAlphaOverlapPixels": overlaps,
            "hasDisconnectedJoint": any(value == 0 for value in overlaps) if analyze else None,
            "joints": [[round(x, 3), round(y, 3)] for x, y in joints],
        }
    return background, report


def main() -> None:
    rest = {side: CHAINS[side]["source"] for side in CHAINS}
    expanded = {side: target_joints(CHAINS[side]["source"], CHAINS[side]["expandedAngles"]) for side in CHAINS}
    cover = {side: target_joints(CHAINS[side]["source"], CHAINS[side]["coverAngles"]) for side in CHAINS}
    poses = []
    panels = []
    for name, joints in (("rest", rest), ("expanded", expanded), ("cover", cover)):
        panel, report = render_pose(name, joints)
        panels.append(panel)
        poses.append(report)

    sheet = Image.new("RGBA", (CANVAS[0] * 3, CANVAS[1] + 48), (20, 22, 28, 255))
    draw = ImageDraw.Draw(sheet)
    for index, (name, panel) in enumerate(zip(("REST", "EXPANDED", "COVER"), panels)):
        sheet.alpha_composite(panel, (index * CANVAS[0], 48))
        draw.text((index * CANVAS[0] + 18, 16), name, fill=(255, 255, 255, 255))
    image_path = QA / "gate3-v5-joint-motion-contact-sheet.png"
    sheet.save(image_path)

    all_chains = [chain for pose in poses for chain in pose["chains"].values()]
    technical_pass = all(chain["maxLengthDriftPx"] <= 0.001 and not chain["hasDisconnectedJoint"] for chain in all_chains)
    result = {
        "schemaVersion": 1,
        "method": "rigid forward-kinematics material stress test; not final Cubism deformation",
        "poses": poses,
        "maxBoneLengthDriftPx": max(chain["maxLengthDriftPx"] for chain in all_chains),
        "disconnectedJointCount": sum(chain["hasDisconnectedJoint"] for chain in all_chains),
        "technicalPass": technical_pass,
        "visualPass": False,
        "visualStatus": "requires_review_of_paw_orbit_contact_occlusion_and_fur_seams",
        "pass": False,
    }
    report_path = QA / "gate3-v5-joint-motion-report.json"
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(image_path)
    print(report_path)
    print(f"maxBoneLengthDriftPx={result['maxBoneLengthDriftPx']} disconnectedJointCount={result['disconnectedJointCount']} technicalPass={str(result['technicalPass']).lower()} visualPass=false")


if __name__ == "__main__":
    main()
