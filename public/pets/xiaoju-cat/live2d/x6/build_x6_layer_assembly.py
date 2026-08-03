from __future__ import annotations

import json
import math
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont
from scipy import ndimage


ROOT = Path(__file__).resolve().parents[1]
X5 = ROOT / "x5"
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
OUT = X6 / "assembled-layer-candidates-v1"
SOURCE = X5 / "qa" / "x5-actual-xiaoju-spread-pose-three-view.png"
CONTRACT = X5 / "x5-actual-xiaoju-layer-split-contract.json"

VIEW_BOUNDS = {
    "front": (0, 0, 650, 887),
    "side": (650, 0, 1120, 887),
    "back": (1120, 0, 1774, 887),
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def checker(size: tuple[int, int], block: int = 12) -> Image.Image:
    image = Image.new("RGBA", size, (247, 248, 249, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle((x, y, x + block - 1, y + block - 1), fill=(225, 229, 233, 255))
    return image


def body_mask(source: Image.Image) -> np.ndarray:
    rgb = np.asarray(source.convert("RGB"))
    return np.any(rgb < 245, axis=2)


def load_layers(source: Image.Image, contract: dict) -> list[dict]:
    layers: list[dict] = []
    for record in contract["layers"]:
        if record["extraction"] != "source-mask" or not record["bounds"]:
            continue
        x0, y0, x1, y1 = record["bounds"]
        image = Image.open(ROOT.parent / record["file"]).convert("RGBA")
        mask = np.zeros((source.height, source.width), dtype=bool)
        alpha = np.asarray(image.getchannel("A")) > 0
        mask[y0:y1, x0:x1] = alpha
        layers.append({"record": record, "mask": mask})
    return layers


def assign_seam_pixels(source: Image.Image, layers: list[dict]) -> tuple[np.ndarray, np.ndarray, dict]:
    labels = np.zeros((source.height, source.width), dtype=np.int16)
    for label, layer in enumerate(sorted(layers, key=lambda item: item["record"]["drawOrder"]), start=1):
        layer["label"] = label
        labels[layer["mask"]] = label

    visible = body_mask(source)
    strict_union = labels > 0
    missing = visible & ~strict_union
    _, nearest = ndimage.distance_transform_edt(~strict_union, return_indices=True)
    nearest_labels = labels[nearest[0], nearest[1]]
    assigned = np.where(missing, nearest_labels, labels)

    metrics: dict[str, dict] = {}
    for view, (x0, y0, x1, y1) in VIEW_BOUNDS.items():
        body = visible[y0:y1, x0:x1]
        strict = strict_union[y0:y1, x0:x1] & body
        repaired = (assigned[y0:y1, x0:x1] > 0) & body
        total = int(body.sum())
        metrics[view] = {
            "visiblePixels": total,
            "strictCoveredPixels": int(strict.sum()),
            "strictCoverage": round(float(strict.sum() / total), 6),
            "seamPixelsAssigned": int((missing[y0:y1, x0:x1]).sum()),
            "assembledCoveredPixels": int(repaired.sum()),
            "assembledCoverage": round(float(repaired.sum() / total), 6),
        }
    return labels, assigned, metrics


def save_refined_layers(source: Image.Image, layers: list[dict], assigned: np.ndarray) -> list[dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    rgb = source.convert("RGBA")
    outputs: list[dict] = []
    for layer in layers:
        label = layer["label"]
        mask = assigned == label
        ys, xs = np.where(mask)
        if len(xs) == 0:
            continue
        bounds = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        alpha = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
        image = rgb.copy()
        image.putalpha(alpha)
        crop = image.crop(bounds)
        filename = f"{layer['record']['view']}_{layer['record']['id']}.png"
        crop.save(OUT / filename, optimize=True)
        outputs.append(
            {
                "view": layer["record"]["view"],
                "id": layer["record"]["id"],
                "file": f"live2d/x6/assembled-layer-candidates-v1/{filename}",
                "bounds": list(bounds),
                "drawOrder": layer["record"]["drawOrder"],
                "parent": layer["record"]["parent"],
                "pivot": layer["record"]["pivot"],
                "sourceAlphaPixels": int(layer["mask"].sum()),
                "assembledAlphaPixels": int(mask.sum()),
                "seamFillPixels": int((mask & ~layer["mask"]).sum()),
                "seamFillMethod": "nearest existing semantic layer within the same visible source body",
            }
        )
    return outputs


def compose(source_size: tuple[int, int], outputs: list[dict], hidden: set[str] | None = None) -> Image.Image:
    composite = Image.new("RGBA", source_size, (0, 0, 0, 0))
    hidden = hidden or set()
    for record in sorted(outputs, key=lambda item: item["drawOrder"]):
        if f"{record['view']}:{record['id']}" in hidden:
            continue
        image = Image.open(ROOT.parent / record["file"]).convert("RGBA")
        composite.alpha_composite(image, (record["bounds"][0], record["bounds"][1]))
    return composite


def strict_composite(source: Image.Image, layers: list[dict]) -> Image.Image:
    union = Image.new("L", source.size, 0)
    for layer in layers:
        union = ImageChops.lighter(union, Image.fromarray((layer["mask"] * 255).astype(np.uint8), mode="L"))
    result = source.convert("RGBA")
    result.putalpha(union)
    return result


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    background = checker(size)
    copy = image.copy()
    copy.thumbnail((size[0] - 20, size[1] - 20), Image.Resampling.LANCZOS)
    background.alpha_composite(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return background


def build_review(source: Image.Image, strict: Image.Image, assembled: Image.Image, outputs: list[dict], metrics: dict) -> None:
    width, height = 1900, 1410
    canvas = Image.new("RGB", (width, height), "#f5f7f9")
    draw = ImageDraw.Draw(canvas)
    draw.text((52, 34), "X6  Mask-Layer Reconstruction Before Parameter Tracing", font=font(40, True), fill="#17324d")
    draw.text((54, 88), "These PNGs were mask-cut from the full spread-pose source. This proves reconstruction only, not production separation.", font=font(20), fill="#5f6e7b")

    titles = ("Approved source pose", "Strict mask-layer reconstruction", "Seam-assigned reconstruction")
    panels = (source.convert("RGBA"), strict, assembled)
    panel_w, panel_h = 580, 600
    for i, (title, image) in enumerate(zip(titles, panels)):
        x = 48 + i * 616
        draw.rounded_rectangle((x, 138, x + panel_w, 790), radius=8, fill="white", outline="#cbd5df", width=2)
        draw.text((x + 20, 156), title, font=font(24, True), fill="#17324d")
        canvas.paste(fit(image, (panel_w - 28, panel_h - 54)).convert("RGB"), (x + 14, 205))
        if i == 1:
            draw.text((x + 20, 755), "Visible gaps remain measurable here.", font=font(17, True), fill="#d26a2e")
        if i == 2:
            draw.text((x + 20, 755), "All visible source pixels belong to a mask layer.", font=font(17, True), fill="#159570")

    draw.rounded_rectangle((48, 830, 1852, 1358), radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((72, 854), "Assembly audit", font=font(28, True), fill="#17324d")
    headers = ("VIEW", "STRICT COVERAGE", "SEAM PIXELS ASSIGNED", "ASSEMBLED COVERAGE")
    xs = (86, 400, 840, 1390)
    for x, label in zip(xs, headers):
        draw.text((x, 915), label, font=font(18, True), fill="#5f6e7b")
    for row, view in enumerate(("front", "side", "back")):
        y = 965 + row * 72
        data = metrics[view]
        draw.text((86, y), view.upper(), font=font(22, True), fill="#24303a")
        draw.text((400, y), f"{data['strictCoverage']:.2%}", font=font(22), fill="#d26a2e")
        draw.text((840, y), f"{data['seamPixelsAssigned']:,}", font=font(22), fill="#24303a")
        draw.text((1390, y), f"{data['assembledCoverage']:.2%}", font=font(22, True), fill="#159570")
        draw.line((72, y + 42, 1820, y + 42), fill="#e1e6eb", width=1)
    draw.text((72, 1208), f"Coordinate-aligned visible layers: {len(outputs)}", font=font(20, True), fill="#24303a")
    draw.text((72, 1252), "Hidden-fill placeholders remain separate and are not counted as visible source reconstruction.", font=font(18), fill="#5f6e7b")
    draw.text((72, 1294), "The 63 fine independent materials still need body-space placement before production assembly; X7 remains locked.", font=font(18, True), fill="#1769d2")
    canvas.save(QA / "x6-layer-assembly-review-v1.png", optimize=True)


def group_for(layer_id: str) -> str:
    if any(token in layer_id for token in ("eye", "iris", "pupil", "highlight", "lid", "muzzle", "jaw", "cheek", "whisker")):
        return "face"
    if "ear" in layer_id or "tail" in layer_id:
        return "ears_tail"
    if any(token in layer_id for token in ("scapula", "upper_arm", "forearm", "wrist", "fore_paw")):
        return "forelimbs"
    if "hind_" in layer_id:
        return "hindlimbs"
    return "torso_head"


def compose_subset(source_size: tuple[int, int], outputs: list[dict], group: str) -> Image.Image:
    subset = [record for record in outputs if group_for(record["id"]) == group]
    return compose(source_size, subset)


def build_origin_proof(source: Image.Image, outputs: list[dict], assembled: Image.Image) -> dict:
    groups = ("torso_head", "face", "forelimbs", "hindlimbs", "ears_tail")
    group_images = {group: compose_subset(source.size, outputs, group) for group in groups}
    hidden = {"front:head_base", "front:forearm_L", "front:tail_mid"}
    knockout = compose(source.size, outputs, hidden=hidden)

    canvas = Image.new("RGB", (1900, 1320), "#f5f7f9")
    draw = ImageDraw.Draw(canvas)
    draw.text((52, 34), "X6  What Was Actually Composited", font=font(40, True), fill="#17324d")
    draw.text((54, 88), "Every panel below is rebuilt by reopening transparent PNG files. The source image is used only for the final pixel audit.", font=font(20), fill="#5f6e7b")
    labels = {
        "torso_head": "Torso + head masks",
        "face": "Face / eye masks",
        "forelimbs": "Forelimb masks",
        "hindlimbs": "Hindlimb masks",
        "ears_tail": "Ear + tail masks",
    }
    for i, group in enumerate(groups):
        x = 45 + i * 370
        draw.rounded_rectangle((x, 140, x + 340, 650), radius=8, fill="white", outline="#cbd5df", width=2)
        draw.text((x + 16, 158), labels[group], font=font(20, True), fill="#17324d")
        canvas.paste(fit(group_images[group], (312, 420)).convert("RGB"), (x + 14, 205))
        count = sum(1 for record in outputs if group_for(record["id"]) == group)
        draw.text((x + 16, 618), f"{count} PNG files", font=font(17), fill="#5f6e7b")

    lower = (("All 113 mask layers", assembled), ("Three layers disabled", knockout))
    for i, (label, image) in enumerate(lower):
        x = 48 + i * 910
        draw.rounded_rectangle((x, 690, x + 860, 1258), radius=8, fill="white", outline="#cbd5df", width=2)
        draw.text((x + 20, 710), label, font=font(25, True), fill="#17324d")
        canvas.paste(fit(image, (824, 455)).convert("RGB"), (x + 18, 760))
    draw.text((982, 1218), "disabled: front head_base, forearm_L, tail_mid", font=font(17, True), fill="#d26a2e")
    canvas.save(QA / "x6-mask-layer-origin-and-knockout-proof-v1.png", optimize=True)

    source_rgba = source.convert("RGBA")
    source_pixels = np.asarray(source_rgba)
    assembled_pixels = np.asarray(assembled)
    visible = body_mask(source)
    rgb_equal = np.all(source_pixels[:, :, :3] == assembled_pixels[:, :, :3], axis=2)
    alpha_covered = assembled_pixels[:, :, 3] > 0
    file_hashes = {}
    for record in outputs:
        path = ROOT.parent / record["file"]
        file_hashes[f"{record['view']}:{record['id']}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "proofImage": "live2d/x6/qa/x6-mask-layer-origin-and-knockout-proof-v1.png",
        "compositionInputCount": len(outputs),
        "compositionReadsOnlyLayerPngs": True,
        "sourceImageUsedDuringComposition": False,
        "sourceImageUsedAfterCompositionForAudit": True,
        "visibleBodyRgbExactMatchRatio": round(float((rgb_equal & visible).sum() / visible.sum()), 8),
        "visibleBodyAlphaCoverageRatio": round(float((alpha_covered & visible).sum() / visible.sum()), 8),
        "knockoutLayers": sorted(hidden),
        "fileSha256": file_hashes,
    }


def main() -> None:
    QA.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE).convert("RGB")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    layers = load_layers(source, contract)
    _, assigned, metrics = assign_seam_pixels(source, layers)
    outputs = save_refined_layers(source, layers, assigned)
    assembled = compose(source.size, outputs)
    strict = strict_composite(source, layers)
    assembled.save(QA / "x6-assembled-xiaoju-three-view-v1.png", optimize=True)
    for view, bounds in VIEW_BOUNDS.items():
        assembled.crop(bounds).save(QA / f"x6-assembled-xiaoju-{view}-v1.png", optimize=True)
    build_review(source, strict, assembled, outputs, metrics)
    origin_proof = build_origin_proof(source, outputs, assembled)

    result = {
        "schemaVersion": 1,
        "stage": "X6-mask-layer-reconstruction-precondition",
        "status": "candidate-for-user-visual-review",
        "evidenceClassification": "mask-derived rest-pose reconstruction QA",
        "productionLayerAssemblyComplete": False,
        "fine63BodySpaceAssemblyComplete": False,
        "source": "live2d/x5/qa/x5-actual-xiaoju-spread-pose-three-view.png",
        "sourceLayerContract": "live2d/x5/x5-actual-xiaoju-layer-split-contract.json",
        "method": [
            "place every source-mask layer at its recorded X5 bounds",
            "measure visible source pixels not owned by any layer",
            "assign each seam pixel to the nearest existing semantic layer",
            "recompose strictly by drawOrder from transparent PNG layers",
        ],
        "counts": {
            "visibleCoordinateAlignedLayers": len(outputs),
            "hiddenFillPlaceholdersExcludedFromVisibleReconstruction": len([r for r in contract["layers"] if r["extraction"] != "source-mask"]),
        },
        "coverageByView": metrics,
        "originAndCompositionProof": origin_proof,
        "layers": outputs,
        "qa": {
            "assembledThreeView": "live2d/x6/qa/x6-assembled-xiaoju-three-view-v1.png",
            "front": "live2d/x6/qa/x6-assembled-xiaoju-front-v1.png",
            "side": "live2d/x6/qa/x6-assembled-xiaoju-side-v1.png",
            "back": "live2d/x6/qa/x6-assembled-xiaoju-back-v1.png",
            "review": "live2d/x6/qa/x6-layer-assembly-review-v1.png",
            "originAndKnockoutProof": "live2d/x6/qa/x6-mask-layer-origin-and-knockout-proof-v1.png",
        },
        "gateBoundary": {
            "currentGate": "x6-parameter-action-tracer",
            "notCubism": True,
            "notRuntime": True,
            "x7Authorized": False,
        },
        "knownLimits": [
            "Seam assignment repairs visible rest-pose ownership; it does not paint hidden anatomy behind moving joints.",
            "The 63 generated fine layers remain detail references because their atlas cells do not yet carry body-space placement coordinates.",
            "Final Cubism proof still requires ArtMesh/deformer screenshots after X6 approval.",
        ],
    }
    (X6 / "x6-layer-assembly-contract-v1.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "layers": len(outputs), "coverage": metrics}, ensure_ascii=False))


if __name__ == "__main__":
    main()
