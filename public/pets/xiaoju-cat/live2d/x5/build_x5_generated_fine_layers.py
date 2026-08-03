from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "generated-layer-materials" / "x5-xiaoju-fine-layer-source-atlas-alpha-v1.png"
OUT_DIR = ROOT / "generated-fine-layer-candidates-v1"
ATLAS = ROOT / "qa" / "x5-generated-fine-layer-candidates-atlas-v1.png"
CONTRACT = ROOT / "x5-generated-fine-layer-candidates-contract-v1.json"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


@dataclass(frozen=True)
class Spec:
    layer_id: str
    view: str
    bbox: tuple[int, int, int, int]
    parent: str
    pivot: str
    overlap: str
    mesh_zone: str
    elastic: str


def spec(layer_id: str, view: str, bbox: tuple[int, int, int, int], parent: str, pivot: str,
         overlap: str, mesh_zone: str, elastic: str = "none") -> Spec:
    return Spec(layer_id, view, bbox, parent, pivot, overlap, mesh_zone, elastic)


SPECS = [
    spec("head_base_front", "front", (20, 5, 290, 250), "Neck", "skull", "under eyes, muzzle and ears", "face oval medium"),
    spec("cheek_fur_L", "front", (286, 88, 382, 224), "Head", "jaw_L", "over head and neck", "fur edge dense", "fur lag"),
    spec("muzzle_base", "front", (378, 105, 512, 224), "Head", "muzzle", "over head base, under whiskers", "mouth curve dense"),
    spec("cheek_fur_R", "front", (510, 88, 618, 224), "Head", "jaw_R", "over head and neck", "fur edge dense", "fur lag"),
    spec("head_base_side", "side", (622, 5, 760, 238), "Neck", "skull", "under side eye, muzzle and ears", "face profile dense"),
    spec("ear_face_L", "front", (728, 18, 818, 148), "EarRoot_L", "ear_base_L", "over ear root", "triangle surface"),
    spec("ear_tip_L", "front", (818, 22, 906, 126), "EarRoot_L", "ear_tip_L", "into ear face +12px", "tip dense", "tip high"),
    spec("ear_face_R", "front", (900, 12, 1004, 166), "EarRoot_R", "ear_base_R", "over ear root", "triangle surface"),
    spec("head_ear_back", "back", (952, 5, 1102, 238), "Neck", "skull", "under back ear overlays", "back head medium"),
    spec("ear_tip_R", "front", (1088, 18, 1170, 128), "EarRoot_R", "ear_tip_R", "into ear face +12px", "tip dense", "tip high"),
    spec("eye_socket_L", "front", (1164, 30, 1248, 112), "Head", "eye_L", "under iris and lids", "socket ellipse dense"),
    spec("eye_socket_R", "front", (1254, 30, 1342, 112), "Head", "eye_R", "under iris and lids", "socket ellipse dense"),
    spec("iris_L", "front", (1168, 106, 1244, 177), "EyeSocket_L", "eye_L", "clipped by socket", "radial dense", "gaze active"),
    spec("iris_R", "front", (1260, 106, 1338, 177), "EyeSocket_R", "eye_R", "clipped by socket", "radial dense", "gaze active"),
    spec("pupil_L", "front", (1172, 168, 1238, 232), "Iris_L", "eye_L", "inside iris", "radial"),
    spec("pupil_R", "front", (1265, 168, 1334, 232), "Iris_R", "eye_R", "inside iris", "radial"),
    spec("highlight_L", "front", (1172, 224, 1238, 274), "Iris_L", "eye_L", "inside iris", "small quad", "highlight parallax"),
    spec("highlight_R", "front", (1262, 224, 1338, 274), "Iris_R", "eye_R", "inside iris", "small quad", "highlight parallax"),
    spec("upper_lid_L", "front", (1148, 266, 1252, 316), "EyeSocket_L", "eye_L", "over iris", "lid arc dense", "blink active"),
    spec("upper_lid_R", "front", (1254, 266, 1360, 316), "EyeSocket_R", "eye_R", "over iris", "lid arc dense", "blink active"),
    spec("lower_lid_L", "front", (1148, 306, 1252, 352), "EyeSocket_L", "eye_L", "over iris", "lid arc dense", "blink small"),
    spec("lower_lid_R", "front", (1254, 306, 1360, 352), "EyeSocket_R", "eye_R", "over iris", "lid arc dense", "blink small"),
    spec("whisker_L", "front", (1115, 340, 1255, 452), "Muzzle", "whisker_root_L", "root under muzzle", "spline endpoints", "tip high"),
    spec("whisker_R", "front", (1248, 340, 1395, 452), "Muzzle", "whisker_root_R", "root under muzzle", "spline endpoints", "tip high"),
    spec("neck_fill", "shared", (35, 246, 232, 430), "Neck", "neck", "under head and chest fur", "head-neck seam"),
    spec("chest_fur", "front", (260, 238, 466, 458), "Ribcage", "neck", "over ribcage, under muzzle", "fur tips dense", "fur lag"),
    spec("ribcage_front", "front", (475, 238, 655, 458), "BodyRoot", "rib", "under neck, abdomen and forelimbs", "shoulder dense"),
    spec("abdomen_front", "front", (660, 238, 830, 458), "BodyRoot", "abdomen", "under ribcage and pelvis", "breath grid", "breath settle"),
    spec("pelvis_front", "front", (830, 238, 990, 458), "BodyRoot", "pelvis", "under abdomen, hips and tail", "hip dense"),
    spec("torso_side", "side", (984, 238, 1120, 458), "BodyRoot", "rib", "under side neck, limbs and pelvis", "profile volume grid"),
    spec("upper_arm_L", "front", (20, 438, 155, 590), "Shoulder_L", "shoulder_L", "under scapula and forearm", "shoulder-elbow dense"),
    spec("fore_paw_L", "front", (20, 562, 110, 682), "Wrist_L", "forepaw_L", "into wrist +16px", "toe arc dense", "toe soft"),
    spec("forearm_L", "front", (125, 438, 308, 684), "Elbow_L", "elbow_L", "under upper arm and paw", "elbow-wrist dense", "sleeve soft"),
    spec("upper_arm_R", "front", (306, 438, 452, 684), "Shoulder_R", "shoulder_R", "under scapula and forearm", "shoulder-elbow dense"),
    spec("forearm_R", "front", (440, 438, 568, 594), "Elbow_R", "elbow_R", "under upper arm and paw", "elbow-wrist dense", "sleeve soft"),
    spec("fore_paw_R", "front", (480, 560, 576, 684), "Wrist_R", "forepaw_R", "into wrist +16px", "toe arc dense", "toe soft"),
    spec("paw_contact_alt", "side", (565, 438, 680, 684), "Wrist_L", "forepaw_L", "side contact alternative", "toe arc dense", "toe soft"),
    spec("hind_thigh_L", "front", (680, 438, 805, 686), "Hip_L", "hip_L", "under pelvis and shin", "hip-knee dense", "soft thigh"),
    spec("hind_shin_L", "front", (790, 438, 915, 686), "Knee_L", "knee_L", "under thigh and paw", "knee-hock dense"),
    spec("hind_thigh_R", "front", (912, 438, 1058, 686), "Hip_R", "hip_R", "under pelvis and shin", "hip-knee dense", "soft thigh"),
    spec("hind_shin_R", "front", (1045, 438, 1180, 686), "Knee_R", "knee_R", "under thigh and paw", "knee-hock dense"),
    spec("hind_leg_side_L", "side", (1170, 438, 1312, 686), "Hip_L", "hip_L", "under side pelvis", "hip-hock dense"),
    spec("hind_leg_side_R", "side", (1295, 438, 1465, 686), "Hip_R", "hip_R", "under side pelvis", "hip-hock dense"),
    spec("tail_root_socket", "shared", (20, 675, 112, 772), "Pelvis", "tail_root", "under pelvis and tail base", "root fan", "socket soft"),
    spec("tail_base", "shared", (95, 670, 230, 820), "TailRoot", "tail_root", "over socket, under mid", "bend fan", "root active"),
    spec("tail_mid_short", "shared", (220, 670, 355, 820), "TailMid", "tail_mid", "over base, under tip", "bend bands", "medium lag"),
    spec("tail_curve", "side", (340, 665, 500, 850), "TailMid", "tail_mid", "side continuation", "curve bands", "medium lag"),
    spec("tail_mid_long", "shared", (455, 660, 690, 820), "TailMid", "tail_mid", "over tail base", "two bend bands", "medium lag"),
    spec("tail_tip_long", "shared", (555, 660, 790, 805), "TailTip", "tail_tip", "over tail mid", "tip fan", "high lag"),
    spec("tail_tip", "shared", (770, 690, 930, 820), "TailTip", "tail_tip", "over tail mid", "tip fan", "high lag"),
    spec("head_back_base", "back", (925, 660, 1135, 845), "Neck", "skull", "under ears", "back face oval"),
    spec("head_profile_L", "side", (1110, 655, 1305, 850), "Neck", "skull", "side head profile", "profile dense"),
    spec("head_profile_R", "side", (1290, 655, 1495, 850), "Neck", "skull", "opposite profile reference", "profile dense"),
    spec("back_neck_L", "back", (15, 820, 165, 1018), "Neck", "neck", "under back head", "neck seam"),
    spec("back_ribcage_L", "back", (165, 815, 355, 1018), "BodyRoot", "rib", "under neck and abdomen", "back shoulder dense"),
    spec("back_pelvis_L", "back", (360, 815, 555, 1018), "BodyRoot", "pelvis", "under back abdomen and tail", "back hip dense"),
    spec("back_limb_fill_1", "back", (570, 815, 682, 1020), "Shoulder_L", "shoulder_L", "under back forelimb", "joint dense"),
    spec("back_limb_fill_2", "back", (670, 815, 782, 1020), "Shoulder_R", "shoulder_R", "under back forelimb", "joint dense"),
    spec("back_limb_fill_3", "back", (775, 815, 892, 1020), "Hip_L", "hip_L", "under back hindlimb", "joint dense"),
    spec("back_torso_1", "back", (885, 810, 1090, 1022), "BodyRoot", "rib", "back torso overlap", "volume grid"),
    spec("back_torso_2", "back", (1070, 810, 1240, 1022), "BodyRoot", "abdomen", "back abdomen overlap", "breath grid", "breath settle"),
    spec("back_torso_3", "back", (1220, 810, 1370, 1022), "BodyRoot", "pelvis", "back pelvis overlap", "hip dense"),
    spec("back_torso_4", "back", (1350, 810, 1536, 1022), "BodyRoot", "pelvis", "back far-side overlap", "hip dense"),
]


def checker(size: tuple[int, int], block: int = 10) -> Image.Image:
    image = Image.new("RGB", size, (245, 245, 245))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle([x, y, x + block - 1, y + block - 1], fill=(225, 225, 225))
    return image


def keep_connected_material(image: Image.Image, keep_bundle: bool = False) -> Image.Image:
    alpha = image.getchannel("A")
    width, height = alpha.size
    values = alpha.tobytes()
    visited = bytearray(width * height)
    components: list[list[int]] = []
    for start, value in enumerate(values):
        if value <= 8 or visited[start]:
            continue
        visited[start] = 1
        queue = deque([start])
        component: list[int] = []
        while queue:
            index = queue.popleft()
            component.append(index)
            x, y = index % width, index // width
            for ny in range(max(0, y - 1), min(height, y + 2)):
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    neighbor = ny * width + nx
                    if not visited[neighbor] and values[neighbor] > 8:
                        visited[neighbor] = 1
                        queue.append(neighbor)
        components.append(component)
    if not components:
        return image
    selected = components if keep_bundle else [max(components, key=len)]
    if keep_bundle:
        selected = [component for component in selected if len(component) >= 3]
    keep = bytearray(width * height)
    for component in selected:
        for index in component:
            keep[index] = values[index]
    cleaned = image.copy()
    cleaned.putalpha(Image.frombytes("L", (width, height), bytes(keep)))
    return cleaned


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ATLAS.parent.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE).convert("RGBA")
    records: list[dict[str, object]] = []
    for index, item in enumerate(SPECS):
        crop = source.crop(item.bbox)
        crop = keep_connected_material(crop, keep_bundle=item.layer_id.startswith("whisker_"))
        alpha_bbox = crop.getchannel("A").getbbox()
        if not alpha_bbox:
            continue
        crop = crop.crop(alpha_bbox)
        filename = f"{index + 1:02d}_{item.view}_{item.layer_id}.png"
        crop.save(OUT_DIR / filename)
        alpha_hist = crop.getchannel("A").histogram()
        alpha_pixels = crop.width * crop.height - alpha_hist[0]
        records.append({
            "index": index + 1,
            "id": item.layer_id,
            "view": item.view,
            "file": f"live2d/x5/generated-fine-layer-candidates-v1/{filename}",
            "sourceAtlasBounds": list(item.bbox),
            "size": [crop.width, crop.height],
            "alphaPixelCount": alpha_pixels,
            "parent": item.parent,
            "primaryController": item.parent,
            "pivot": item.pivot,
            "hiddenOverlap": item.overlap,
            "meshDensityZone": item.mesh_zone,
            "elastic": item.elastic,
            "candidateOnly": True,
        })

    cols, cell_w, cell_h = 6, 244, 188
    rows = math.ceil(len(records) / cols)
    sheet = Image.new("RGB", (cols * cell_w + 40, rows * cell_h + 126), (250, 250, 247))
    draw = ImageDraw.Draw(sheet)
    draw.rounded_rectangle([20, 16, sheet.width - 20, 96], radius=8, fill=(255, 252, 246), outline=(120, 135, 120), width=2)
    draw.text((44, 28), f"X5 小橘生成式精细分层素材 ({len(records)} layers)", font=font(28), fill=(34, 38, 44))
    draw.text((44, 64), "基于现有小橘大字型三视图；透明 PNG，包含关节隐藏毛流扩展；仅供 X5 审核。", font=font(16), fill=(112, 82, 54))
    for i, record in enumerate(records):
        col, row = i % cols, i // cols
        x, y = 20 + col * cell_w, 112 + row * cell_h
        draw.rounded_rectangle([x + 5, y + 4, x + cell_w - 6, y + cell_h - 8], radius=5, fill=(255, 255, 255), outline=(176, 176, 160))
        layer = Image.open(ROOT.parent.parent / record["file"]).convert("RGBA")
        bg = checker((cell_w - 24, 126), 8).convert("RGBA")
        scale = min((cell_w - 32) / layer.width, 118 / layer.height, 1.0)
        preview = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.Resampling.LANCZOS)
        bg.alpha_composite(preview, ((bg.width - preview.width) // 2, (bg.height - preview.height) // 2))
        sheet.paste(bg.convert("RGB"), (x + 12, y + 10))
        draw.text((x + 12, y + 140), f"{record['index']:02d} {record['view']}:{record['id']}"[:31], font=font(12), fill=(38, 45, 52))
        draw.text((x + 12, y + 160), f"-> {record['parent']} / {record['pivot']}"[:34], font=font(10), fill=(92, 88, 78))
    sheet.save(ATLAS)

    contract = {
        "schemaVersion": 1,
        "stage": "X5-generated-fine-layer-material-candidates",
        "status": "candidate-for-user-review",
        "revision": "generated-fine-layers-v1-imagegen-chroma-alpha",
        "sourceAuthority": "live2d/x5/qa/x5-actual-xiaoju-spread-pose-three-view.png",
        "generatedSourceAtlas": "live2d/x5/generated-layer-materials/x5-xiaoju-fine-layer-source-atlas-alpha-v1.png",
        "generationMethod": "built-in imagegen identity-preserving material atlas, then local chroma-key alpha removal and deterministic semantic crops",
        "counts": {"layers": len(records), "byView": {view: len([r for r in records if r["view"] == view]) for view in ("front", "side", "back", "shared")}},
        "gateBoundary": {"currentGate": "x5-layer-mesh-node-torque", "gate5Approved": False, "x6Authorized": False},
        "qa": {"atlas": "live2d/x5/qa/x5-generated-fine-layer-candidates-atlas-v1.png"},
        "layers": records,
        "knownRisks": [
            "Generated hidden fur is an identity-preserving X5 candidate and still requires user visual approval.",
            "Generated source pieces are not a PSD, Cubism ArtMesh, Deformer, parameter, or runtime output.",
            "Side/back-specific pieces are material references; final import placement must remain constrained by the approved canonical skeleton.",
        ],
    }
    CONTRACT.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    print(ATLAS.as_posix())
    print(CONTRACT.as_posix())
    print(f"layers={len(records)}")


if __name__ == "__main__":
    main()
