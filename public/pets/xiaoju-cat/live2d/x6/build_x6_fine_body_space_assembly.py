from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
X5 = ROOT / "x5"
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
INSTANCES = X6 / "fine-body-space-instances-v1"
SOURCE_CONTRACT = X5 / "x5-generated-fine-layer-candidates-contract-v1.json"
CANVAS = (1800, 900)
VIEW_X = {"front": 0, "side": 600, "back": 1200}


@dataclass(frozen=True)
class Placement:
    index: int
    view: str
    center: tuple[int, int]
    width: int
    rotation: float = 0.0
    mirror: bool = False
    role: str = "visible-primary"


def p(index: int, view: str, x: int, y: int, width: int, rotation: float = 0.0, mirror: bool = False, role: str = "visible-primary") -> Placement:
    return Placement(index, view, (VIEW_X[view] + x, y), width, rotation, mirror, role)


PLACEMENTS = [
    # Front: tail and body back-to-front.
    p(44, "front", 300, 650, 86),
    p(45, "front", 300, 690, 112),
    p(48, "front", 300, 755, 150, 82),
    p(49, "front", 300, 815, 145, 86),
    p(50, "front", 300, 855, 82, 90),
    p(29, "front", 300, 612, 264),
    p(28, "front", 300, 505, 242),
    p(27, "front", 300, 402, 238),
    p(25, "front", 300, 292, 170),
    p(26, "front", 300, 350, 208),
    # L/R names are anatomical. In a front view Xiaoju's right side is viewer-left.
    p(40, "front", 225, 642, 108, 18),
    p(41, "front", 165, 710, 94, 62),
    p(38, "front", 375, 642, 108, -18),
    p(39, "front", 435, 710, 94, -62),
    p(34, "front", 210, 388, 90, -48),
    p(35, "front", 151, 443, 86, -45),
    p(36, "front", 98, 492, 72, 56),
    p(31, "front", 390, 388, 90, 48),
    p(33, "front", 449, 443, 86, 45),
    p(32, "front", 502, 492, 72, -56),
    p(1, "front", 300, 185, 270),
    p(4, "front", 225, 220, 126, -4),
    p(2, "front", 375, 220, 126, 4),
    p(8, "front", 220, 106, 84, -7),
    p(10, "front", 217, 72, 50, -6),
    p(6, "front", 380, 106, 84, 7),
    p(7, "front", 383, 72, 50, 6),
    p(3, "front", 300, 242, 122),
    p(12, "front", 252, 186, 58),
    p(11, "front", 348, 186, 58),
    p(14, "front", 252, 186, 37),
    p(13, "front", 348, 186, 37),
    p(16, "front", 252, 188, 15),
    p(15, "front", 348, 188, 15),
    p(18, "front", 245, 177, 9),
    p(17, "front", 341, 177, 9),
    p(20, "front", 252, 167, 56),
    p(19, "front", 348, 167, 56),
    p(22, "front", 252, 205, 54),
    p(21, "front", 348, 205, 54),
    p(23, "front", 210, 247, 150, 0, False, "registered-source-defect-hidden"),
    p(24, "front", 390, 247, 150, 0, False, "registered-source-defect-hidden"),

    # Side: profile faces left; long tail and far-side pieces remain behind the torso.
    p(49, "side", 500, 735, 210, -15),
    p(48, "side", 470, 690, 220, -25),
    p(47, "side", 420, 625, 176, -28),
    p(43, "side", 390, 675, 108, -16),
    p(42, "side", 315, 675, 108, 16),
    p(30, "side", 320, 462, 260),
    p(25, "side", 245, 292, 158),
    p(37, "side", 145, 490, 82, 36),
    p(33, "side", 180, 445, 80, 32),
    p(31, "side", 220, 395, 86, 28),
    p(5, "side", 215, 185, 210, 0, False, "registered-redundant-profile-hidden"),
    p(52, "side", 205, 185, 230),
    p(6, "side", 245, 82, 92, 4, False, "registered-duplicate-ear-hidden"),
    p(53, "side", 205, 185, 230, 0, False, "registered-opposite-profile-hidden"),

    # Back: use back-specific pieces; duplicated forms are overlapped as regional fills.
    p(45, "back", 300, 690, 112),
    p(46, "back", 300, 742, 104),
    p(48, "back", 300, 760, 152, 84),
    p(49, "back", 300, 825, 145, 86),
    # The same anatomical convention applies in the back contract.
    p(59, "back", 205, 700, 102, 58, True, "mirrored-instance"),
    p(59, "back", 395, 700, 102, -58),
    p(56, "back", 300, 605, 276),
    p(62, "back", 245, 565, 150, 3, False, "registered-redundant-torso-hidden"),
    p(63, "back", 355, 565, 150, -3, False, "registered-redundant-torso-hidden"),
    p(61, "back", 300, 492, 264),
    p(60, "back", 300, 392, 272),
    p(55, "back", 300, 310, 252),
    p(58, "back", 205, 420, 88, -52),
    p(57, "back", 395, 420, 88, 52),
    p(54, "back", 300, 252, 198),
    p(51, "back", 300, 172, 270),
    p(9, "back", 215, 82, 92, -6, False, "registered-duplicate-ear-hidden"),
    p(9, "back", 385, 82, 92, 6, True, "registered-duplicate-ear-hidden"),
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in (
        Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def checker(size: tuple[int, int], block: int = 12) -> Image.Image:
    image = Image.new("RGBA", size, (247, 248, 249, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(224, 229, 233, 255))
    return image


def transform(image: Image.Image, placement: Placement) -> Image.Image:
    source = remove_green_guide_fringe(image)
    source = ImageOps.mirror(source) if placement.mirror else source
    height = max(1, round(source.height * placement.width / source.width))
    resized = source.resize((placement.width, height), Image.Resampling.LANCZOS)
    return resized.rotate(placement.rotation, resample=Image.Resampling.BICUBIC, expand=True)


def remove_green_guide_fringe(image: Image.Image) -> Image.Image:
    out = image.copy().convert("RGBA")
    pixels = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = pixels[x, y]
            if a and g > r + 6 and b < 145:
                peak = max(r, g)
                pixels[x, y] = (min(255, peak + 12), round(peak * 0.66), round(peak * 0.32), a)
    return out


def build_instances(records: dict[int, dict]) -> list[dict]:
    INSTANCES.mkdir(parents=True, exist_ok=True)
    outputs = []
    occurrence: dict[tuple[str, int], int] = {}
    for z, placement in enumerate(PLACEMENTS):
        key = (placement.view, placement.index)
        occurrence[key] = occurrence.get(key, 0) + 1
        record = records[placement.index]
        source_path = ROOT.parent / record["file"]
        image = transform(Image.open(source_path).convert("RGBA"), placement)
        x = round(placement.center[0] - image.width / 2)
        y = round(placement.center[1] - image.height / 2)
        filename = f"{z+1:03d}_{placement.view}_{placement.index:02d}_{record['id']}_{occurrence[key]}.png"
        image.save(INSTANCES / filename, optimize=True)
        outputs.append(
            {
                "z": z,
                "sourceIndex": placement.index,
                "sourceId": record["id"],
                "sourceFile": record["file"],
                "view": placement.view,
                "role": placement.role,
                "instanceFile": f"live2d/x6/fine-body-space-instances-v1/{filename}",
                "position": [x, y],
                "center": list(placement.center),
                "width": placement.width,
                "rotationDeg": placement.rotation,
                "mirror": placement.mirror,
                "sha256": hashlib.sha256((INSTANCES / filename).read_bytes()).hexdigest(),
            }
        )
    return outputs


def compose(instances: list[dict], hidden: set[int] | None = None) -> Image.Image:
    hidden = hidden or set()
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    for instance in instances:
        if instance["z"] in hidden or instance["role"].endswith("hidden"):
            continue
        image = Image.open(ROOT.parent / instance["instanceFile"]).convert("RGBA")
        canvas.alpha_composite(image, tuple(instance["position"]))
    return canvas


def view_crop(image: Image.Image, view: str) -> Image.Image:
    x = VIEW_X[view]
    return image.crop((x, 0, x + 600, 900))


def group(instance: dict) -> str:
    layer = instance["sourceId"]
    if any(token in layer for token in ("eye", "iris", "pupil", "highlight", "lid", "muzzle", "cheek", "whisker")):
        return "face"
    if "ear" in layer or "tail" in layer:
        return "ears_tail"
    if any(token in layer for token in ("arm", "fore", "paw_contact")):
        return "forelimbs"
    if "hind" in layer or "limb_fill" in layer:
        return "hindlimbs"
    return "torso_head"


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    bg = checker(size)
    copy = image.copy()
    copy.thumbnail((size[0] - 20, size[1] - 20), Image.Resampling.LANCZOS)
    bg.alpha_composite(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return bg


def build_review(instances: list[dict], composite: Image.Image) -> None:
    canvas = Image.new("RGB", (1900, 1440), "#f5f7f9")
    draw = ImageDraw.Draw(canvas)
    draw.text((52, 34), "X6  Fine Independent Materials: Body-Space Assembly Candidate", font=font(39, True), fill="#17324d")
    draw.text((54, 88), "This composite reopens transformed instances derived from the 63 fine PNG materials. It does not use the full spread-pose source.", font=font(19), fill="#5f6e7b")
    for i, view in enumerate(("front", "side", "back")):
        x = 48 + i * 616
        draw.rounded_rectangle((x, 138, x + 580, 800), radius=8, fill="white", outline="#cbd5df", width=2)
        draw.text((x + 20, 158), view.upper(), font=font(24, True), fill="#17324d")
        canvas.paste(fit(view_crop(composite, view), (552, 580)).convert("RGB"), (x + 14, 205))

    groups = ("torso_head", "face", "forelimbs", "hindlimbs", "ears_tail")
    labels = ("torso + head", "face + eyes", "forelimbs", "hindlimbs", "ears + tail")
    for i, (group_id, label) in enumerate(zip(groups, labels)):
        subset = [item for item in instances if group(item) == group_id]
        image = compose(subset)
        x = 48 + i * 366
        draw.rounded_rectangle((x, 835, x + 338, 1305), radius=8, fill="white", outline="#cbd5df", width=2)
        draw.text((x + 16, 852), label, font=font(19, True), fill="#17324d")
        canvas.paste(fit(image, (310, 370)).convert("RGB"), (x + 14, 902))
        draw.text((x + 16, 1268), f"{len(subset)} transformed instances", font=font(15), fill="#5f6e7b")
    draw.text((55, 1350), "Candidate only: inspect anatomy, overlaps and identity before this can replace mask-derived reconstruction QA.", font=font(20, True), fill="#d26a2e")
    canvas.save(QA / "x6-fine-body-space-assembly-review-v1.png", optimize=True)


def build_knockout_proof(instances: list[dict], composite: Image.Image) -> dict:
    selected = []
    for view, source_index in (("front", 1), ("front", 33), ("front", 48), ("side", 30), ("back", 60)):
        match = next(item for item in instances if item["view"] == view and item["sourceIndex"] == source_index)
        selected.append(match)
    hidden = {item["z"] for item in selected}
    knockout = compose(instances, hidden=hidden)

    canvas = Image.new("RGB", (1900, 930), "#f5f7f9")
    draw = ImageDraw.Draw(canvas)
    draw.text((52, 34), "X6  Fine-PNG Composition and Knockout Proof", font=font(40, True), fill="#17324d")
    draw.text((54, 88), "Both panels reopen transformed PNG instances only. Five disabled instances expose real holes; no full-pose image fills them.", font=font(20), fill="#5f6e7b")
    for i, (title, image) in enumerate((("All active fine-material instances", composite), ("Five instances disabled", knockout))):
        x = 48 + i * 920
        draw.rounded_rectangle((x, 145, x + 875, 825), radius=8, fill="white", outline="#cbd5df", width=2)
        draw.text((x + 20, 165), title, font=font(25, True), fill="#17324d")
        canvas.paste(fit(image, (839, 575)).convert("RGB"), (x + 18, 220))
    names = ", ".join(f"{item['view']}:{item['sourceId']}" for item in selected)
    draw.text((980, 795), names, font=font(15, True), fill="#d26a2e")
    path = QA / "x6-fine-body-space-knockout-proof-v1.png"
    canvas.save(path, optimize=True)
    return {
        "proofImage": "live2d/x6/qa/x6-fine-body-space-knockout-proof-v1.png",
        "disabledInstanceZ": sorted(hidden),
        "disabledInstances": [f"{item['view']}:{item['sourceId']}" for item in selected],
        "compositionReadsInstancePngsOnly": True,
        "fullPoseSourceReadDuringComposition": False,
    }


def main() -> None:
    QA.mkdir(parents=True, exist_ok=True)
    contract = json.loads(SOURCE_CONTRACT.read_text(encoding="utf-8"))
    records = {int(record["index"]): record for record in contract["layers"]}
    assert set(records) == set(range(1, 64))
    used = {placement.index for placement in PLACEMENTS}
    assert used == set(range(1, 64)), sorted(set(range(1, 64)) - used)
    instances = build_instances(records)
    composite = compose(instances)
    composite.save(QA / "x6-fine-body-space-assembled-three-view-v1.png", optimize=True)
    for view in VIEW_X:
        view_crop(composite, view).save(QA / f"x6-fine-body-space-assembled-{view}-v1.png", optimize=True)
    build_review(instances, composite)
    knockout_proof = build_knockout_proof(instances, composite)

    source_hashes = {
        record["id"]: hashlib.sha256((ROOT.parent / record["file"]).read_bytes()).hexdigest()
        for record in contract["layers"]
    }

    data = {
        "schemaVersion": 1,
        "stage": "X6-fine-independent-material-body-space-assembly",
        "status": "rejected-visible-replacement-experiment",
        "evidenceClassification": "historical fine-material placement experiment; not the production rest stack",
        "supersededBy": "live2d/x6/x6-production-layer-stack-contract-v2.json",
        "sourceContract": "live2d/x5/x5-generated-fine-layer-candidates-contract-v1.json",
        "sourceMaterialCount": 63,
        "allSourceMaterialsRegistered": used == set(range(1, 64)),
        "compositionUsesFullSpreadPoseSource": False,
        "compositionReadsTransformedPngInstancesOnly": True,
        "sourceMaterialSha256": source_hashes,
        "canvas": list(CANVAS),
        "viewOrigins": VIEW_X,
        "instances": instances,
        "knockoutProof": knockout_proof,
        "qa": {
            "assembledThreeView": "live2d/x6/qa/x6-fine-body-space-assembled-three-view-v1.png",
            "review": "live2d/x6/qa/x6-fine-body-space-assembly-review-v1.png",
            "knockoutProof": "live2d/x6/qa/x6-fine-body-space-knockout-proof-v1.png",
        },
        "gateBoundary": {
            "currentGate": "x6-parameter-action-tracer",
            "candidateOnly": True,
            "gate6Approved": False,
            "x7Authorized": False,
        },
        "knownLimits": [
            "This experiment incorrectly forced hidden-fill materials to replace visible identity art and must not be used as the X6 rest candidate.",
            "The opposite side-profile material is registered but hidden in the primary left-facing side composite.",
            "No Cubism ArtMesh, Deformer, Physics or runtime output is produced.",
        ],
    }
    (X6 / "x6-fine-body-space-assembly-contract-v1.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "materials": len(used), "instances": len(instances)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
