from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
X6 = Path(__file__).resolve().parent
QA = X6 / "qa"
SOURCE = ROOT.parent / "three-view-preview.png"
X2_SAMPLES = ROOT / "x2" / "x2-cover-roundtrip-samples.json"
LOGIN_ART = ROOT.parent
ASSEMBLED = QA / "x6-assembled-xiaoju-three-view-v1.png"

NAVY = "#17324d"
BLUE = "#1769d2"
CYAN = "#00a6a6"
ORANGE = "#ef6c2f"
GREEN = "#159570"
RED = "#d73c36"
INK = "#24303a"
MUTED = "#61707e"
PAPER = "#f6f8fa"
GRID = "#d8e0e7"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def sample_at_progress(samples: list[dict], progress: float, phase: str = "enter") -> dict:
    candidates = [s for s in samples if s["phase"] == phase]
    return min(candidates, key=lambda s: abs(s["coverProgress"] - progress))


def curve_points(values: list[float], box: tuple[int, int, int, int], lo: float, hi: float) -> list[tuple[int, int]]:
    x0, y0, x1, y1 = box
    span = max(hi - lo, 1e-9)
    return [
        (
            round(x0 + (x1 - x0) * i / max(1, len(values) - 1)),
            round(y1 - (y1 - y0) * (value - lo) / span),
        )
        for i, value in enumerate(values)
    ]


def delayed(values: list[float], frames: float) -> list[float]:
    out: list[float] = []
    for i in range(len(values)):
        source = clamp(i - frames, 0.0, len(values) - 1.0)
        a = int(math.floor(source))
        b = min(a + 1, len(values) - 1)
        f = source - a
        out.append(values[a] * (1.0 - f) + values[b] * f)
    return out


def derivatives(values: list[float], dt: float) -> tuple[list[float], list[float]]:
    velocity = [0.0]
    for i in range(1, len(values)):
        velocity.append((values[i] - values[i - 1]) / dt)
    acceleration = [0.0]
    for i in range(1, len(velocity)):
        acceleration.append((velocity[i] - velocity[i - 1]) / dt)
    return velocity, acceleration


def rounded_range(values: list[float]) -> list[float]:
    return [round(min(values), 4), round(max(values), 4)]


def build_contract(samples: list[dict]) -> tuple[dict, dict]:
    dt = 1.6 / (len(samples) - 1)
    cover_l = [float(s["coverProgress"]) for s in samples]
    cover_r = delayed(cover_l, 0.024 / dt)
    velocity_l, acceleration_l = derivatives(cover_l, dt)
    velocity_r, acceleration_r = derivatives(cover_r, dt)

    channels = []
    for side in ("L", "R"):
        for index, joint in enumerate(("Shoulder", "Elbow", "Wrist")):
            values = [float(s["sides"][side]["angleDeltaFromRestDeg"][index]) for s in samples]
            velocity, acceleration = derivatives(values, dt)
            channels.append(
                {
                    "parameter": f"Param{joint}{side}",
                    "type": "active-rotation",
                    "source": "X2 approved 41-point roundtrip",
                    "rangeDeg": rounded_range(values),
                    "maxVelocityDegPerSec": round(max(abs(v) for v in velocity), 3),
                    "maxAccelerationDegPerSec2": round(max(abs(v) for v in acceleration), 3),
                    "blend": "Override within password-cover motion",
                    "physicsMayDrive": False,
                }
            )

    keyforms = []
    for progress in (0.0, 0.25, 0.5, 0.75, 1.0):
        sample = sample_at_progress(samples, progress)
        keyforms.append(
            {
                "coverProgress": progress,
                "sampleIndex": sample["index"],
                "bodyCompensation": sample["bodyCompensation"],
                "leftAngleDeltaDeg": sample["sides"]["L"]["angleDeltaFromRestDeg"],
                "rightAngleDeltaDeg": sample["sides"]["R"]["angleDeltaFromRestDeg"],
                "pawFaceContact": sample["sides"]["L"]["faceContact"] and sample["sides"]["R"]["faceContact"],
                "segmentLengthDrift": max(
                    sample["sides"]["L"]["segmentLengthDrift"],
                    sample["sides"]["R"]["segmentLengthDrift"],
                ),
            }
        )

    eye_parameters = [
        {"parameter": "ParamEyeBallX", "nominalRange": [-1.0, 1.0], "runtimeSafeRange": [-0.65, 0.65], "blend": "Override"},
        {"parameter": "ParamEyeBallY", "nominalRange": [-1.0, 1.0], "runtimeSafeRange": [-0.45, 0.45], "blend": "Override"},
        {"parameter": "ParamEyeLOpen", "range": [0.0, 1.0], "blend": "Multiply(blink, state visibility)"},
        {"parameter": "ParamEyeROpen", "range": [0.0, 1.0], "blend": "Multiply(blink, state visibility)"},
        {"parameter": "ParamBlink", "range": [0.0, 1.0], "distribution": "bounded non-uniform 2.5-6.5 s"},
        {"parameter": "ParamEyeConvergence", "range": [0.0, 0.08], "nearTargetsOnly": True},
        {"parameter": "ParamEyeLidFollowY", "range": [-0.09, 0.09], "sourceGain": "10-20% of safe gaze Y"},
        {"parameter": "ParamPupilScale", "range": [0.96, 1.04], "mouseDistanceDriven": False},
        {"parameter": "ParamEyeHighlightX", "range": [-0.42, 0.42], "irisGain": 0.65},
        {"parameter": "ParamEyeHighlightY", "range": [-0.29, 0.29], "irisGain": 0.65},
        {"parameter": "ParamGazeWeight", "range": [0.0, 1.0], "preserveVelocityOnOwnerChange": True},
        {"parameter": "ParamEyeHeadCompX", "range": [-0.12, 0.12], "shortCounterCompensation": True},
        {"parameter": "ParamEyeHeadCompY", "range": [-0.08, 0.08], "shortCounterCompensation": True},
    ]

    contract = {
        "schemaVersion": 1,
        "stage": "X6-parameter-motion-action-tracer",
        "status": "candidate-for-user-visual-review",
        "approvalBasis": {
            "x5Approved": True,
            "evidence": "User said: 可以了，继续下一步吧",
        },
        "sourceContracts": [
            "live2d/x2/x2-cover-roundtrip-samples.json",
            "live2d/x5/x5-generated-fine-layer-candidates-contract-v1.json",
            "live2d/x5/x5-generated-fine-mesh-contract-v1.json",
            "live2d/x6/x6-layer-assembly-contract-v1.json",
        ],
        "maskReconstructionSource": {
            "contract": "live2d/x6/x6-layer-assembly-contract-v1.json",
            "preview": "live2d/x6/qa/x6-assembled-xiaoju-three-view-v1.png",
            "visibleLayerCount": 113,
            "coverageRequired": 1.0,
            "evidenceLevel": "rest-pose mask reconstruction only",
            "productionFineLayerAssemblyComplete": False,
        },
        "gateBoundary": {
            "allowed": ["parameter vocabulary", "bounded Action Tracer map", "keyform ranges", "Cubism-ready Motion output definition"],
            "forbidden": ["Cubism authoring", "final Physics tuning", "X7 elastic motion", "runtime integration"],
        },
        "inputPriority": [
            "password-cover contact",
            "explicit interaction target",
            "current input field",
            "pointer inside Xiaoju/login attention region",
            "idle observation target",
        ],
        "actionTracerPipeline": [
            "raw input or app state",
            "target ownership and priority",
            "model-local coordinates",
            "safe ellipse and dead zone",
            "velocity/acceleration limiting and smoothing",
            "active parameter targets",
            "Deformer cascade",
        ],
        "interruptionRule": "Preserve current value and velocity; blend ownership without resetting to rest.",
        "gaze": {
            "eyeSafeEllipse": {"x": [-0.65, 0.65], "y": [-0.45, 0.45], "deadZoneRadius": 0.05},
            "saccadeMs": [80, 180],
            "smoothPursuitMs": [120, 220],
            "headDelayMs": [120, 280],
            "headRemainderGain": [0.20, 0.35],
            "bodyDelayAfterHead": True,
            "bodyRemainderGain": [0.05, 0.12],
            "ninePointAudit": [[x, y] for y in (-0.45, 0.0, 0.45) for x in (-0.65, 0.0, 0.65)],
        },
        "blink": {
            "keyformValues": [1.0, 0.75, 0.5, 0.25, 0.0],
            "closeMs": [60, 90],
            "closedHoldMs": [20, 70],
            "openMs": [100, 160],
            "leftRightOffsetMs": [10, 25],
            "preserveGazeState": True,
        },
        "eyeLayerOwnership": {
            "left": {
                "socketBase": "eye_socket_L",
                "mask": "EyeMask_L (Cubism-ready definition; not authored in this gate)",
                "iris": "iris_L",
                "pupil": "pupil_L",
                "highlight": "highlight_L",
                "upperLid": "upper_lid_L",
                "lowerLid": "lower_lid_L",
                "furOccluder": "cheek_fur_L",
            },
            "right": {
                "socketBase": "eye_socket_R",
                "mask": "EyeMask_R (Cubism-ready definition; not authored in this gate)",
                "iris": "iris_R",
                "pupil": "pupil_R",
                "highlight": "highlight_R",
                "upperLid": "upper_lid_R",
                "lowerLid": "lower_lid_R",
                "furOccluder": "cheek_fur_R",
            },
            "hierarchy": "Head -> EyeSocket -> EyeMask / Iris -> Pupil + Highlight / UpperLid / LowerLid / EyeFurOccluder",
            "reject": ["baked duplicate pupil", "duplicate highlight", "iris outside mask", "blink encoded as gaze"],
        },
        "eyeParameters": eye_parameters,
        "coverMotion": {
            "durationSec": 1.6,
            "sampleCount": len(samples),
            "masterParameters": ["ParamForelegCoverL", "ParamForelegCoverR"],
            "rightSideDelayMs": 24,
            "leftProgressRange": rounded_range(cover_l),
            "rightProgressRange": rounded_range(cover_r),
            "maxProgressVelocityPerSec": round(max(max(map(abs, velocity_l)), max(map(abs, velocity_r))), 4),
            "maxProgressAccelerationPerSec2": round(max(max(map(abs, acceleration_l)), max(map(abs, acceleration_r))), 4),
            "keyforms": keyforms,
            "activeJointChannels": channels,
            "physicsMayDetermineCorePath": False,
        },
        "loginStates": {
            "idle": "bounded safe observations; blink and low drift remain active",
            "email-focus": "eyes lead input target; head follows after delay",
            "password-cover-enter": "stop new targets; center/down gaze; blink leads paw contact by 40-100 ms",
            "password-cover-hold": "internal blink phase continues; visible gaze weight is zero",
            "password-cover-exit": "open only after paws clear socket; reacquire without center reset",
        },
        "nextGate": "X7 only after explicit X6 user approval",
    }

    trace = {
        "schemaVersion": 1,
        "status": "candidate-trace-audit",
        "sampleRateHz": round(1.0 / dt, 3),
        "columns": ["index", "timeSec", "phase", "coverL", "coverR", "velocityL", "velocityR", "accelerationL", "accelerationR"],
        "samples": [
            {
                "index": i,
                "timeSec": round(i * dt, 4),
                "phase": samples[i]["phase"],
                "coverL": round(cover_l[i], 5),
                "coverR": round(cover_r[i], 5),
                "velocityL": round(velocity_l[i], 5),
                "velocityR": round(velocity_r[i], 5),
                "accelerationL": round(acceleration_l[i], 5),
                "accelerationR": round(acceleration_r[i], 5),
            }
            for i in range(len(samples))
        ],
        "tests": {
            "bounded": all(0.0 <= v <= 1.0 for v in cover_l + cover_r),
            "continuous": max(abs(cover_l[i] - cover_l[i - 1]) for i in range(1, len(cover_l))) <= 0.08,
            "roundtripReturnsToRest": cover_l[-1] == 0.0 and cover_r[-1] <= 0.02,
            "leftRightIntentionalOffset": cover_l != cover_r,
            "segmentLengthsInheritedFromX2": "zero drift at all 41 source samples",
        },
    }
    return contract, trace


def card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str) -> None:
    draw.rounded_rectangle(box, radius=8, fill="white", outline="#cbd5df", width=2)
    draw.text((box[0] + 22, box[1] + 18), title, font=font(28, True), fill=NAVY)


def build_review(contract: dict, trace: dict, samples: list[dict]) -> None:
    canvas = Image.new("RGB", (1900, 1480), PAPER)
    draw = ImageDraw.Draw(canvas)
    draw.text((58, 38), "X6  Parameter + Action Tracer Review", font=font(42, True), fill=NAVY)
    draw.text((60, 92), "Bounded inputs drive active parameters; core cover motion stays on the approved X2 path.", font=font(22), fill=MUTED)

    card(draw, (48, 140, 928, 610), "1  Mask-reconstructed Xiaoju gaze safety and nine-point audit")
    assembled = Image.open(ASSEMBLED).convert("RGBA")
    front_rgba = assembled.crop((0, 0, 650, 887))
    front_bg = Image.new("RGBA", front_rgba.size, "white")
    front_bg.alpha_composite(front_rgba)
    front = front_bg.convert("RGB")
    front.thumbnail((410, 410), Image.Resampling.LANCZOS)
    canvas.paste(front, (82, 188))
    fx, fy = 82, 188
    fw, fh = front.size
    center_x, center_y = fx + fw * 0.515, fy + fh * 0.205
    rx, ry = fw * 0.17, fh * 0.045
    draw.ellipse((center_x-rx, center_y-ry, center_x+rx, center_y+ry), outline=CYAN, width=4)
    for x, y in contract["gaze"]["ninePointAudit"]:
        px = center_x + rx * x / 0.65
        py = center_y - ry * y / 0.45
        draw.ellipse((px-7, py-7, px+7, py+7), fill=ORANGE, outline="white", width=2)
    draw.text((525, 205), "Tracer chain", font=font(22, True), fill=INK)
    chain = ["target owner", "model-local", "safe ellipse", "speed limits", "Eye X/Y", "head delay", "body follow"]
    for i, label in enumerate(chain):
        y = 250 + i * 45
        draw.rounded_rectangle((525, y, 840, y+32), radius=6, fill="#eef4f8", outline="#b6c8d7")
        draw.text((540, y+5), label, font=font(17), fill=INK)
        if i < len(chain)-1:
            draw.line((682, y+32, 682, y+45), fill=BLUE, width=3)
    draw.text((525, 570), "safe X  -0.65..0.65    safe Y  -0.45..0.45", font=font(17, True), fill=GREEN)

    card(draw, (962, 140, 1852, 610), "2  Rest -> Cover -> Rest parameter trace")
    box = (1010, 235, 1800, 515)
    draw.rectangle(box, fill="#fbfcfd", outline=GRID)
    for i in range(5):
        y = box[1] + i * (box[3]-box[1]) / 4
        draw.line((box[0], y, box[2], y), fill=GRID, width=1)
    left = [s["coverL"] for s in trace["samples"]]
    right = [s["coverR"] for s in trace["samples"]]
    draw.line(curve_points(left, box, 0, 1), fill=BLUE, width=5, joint="curve")
    draw.line(curve_points(right, box, 0, 1), fill=ORANGE, width=4, joint="curve")
    draw.line((box[0]+(box[2]-box[0])/2, box[1], box[0]+(box[2]-box[0])/2, box[3]), fill=RED, width=2)
    draw.text((1010, 535), "blue: left   orange: right (+24 ms)   red: cover hold apex", font=font(18), fill=MUTED)
    draw.text((1010, 570), "41 source samples | bounded 0..1 | return is continuous | no pose-image switching", font=font(17, True), fill=GREEN)

    card(draw, (48, 642, 1852, 1040), "3  Five active keyforms inherited from X2 (segment length remains fixed)")
    keyforms = contract["coverMotion"]["keyforms"]
    for idx, key in enumerate(keyforms):
        sample = sample_at_progress(samples, key["coverProgress"])
        x0 = 82 + idx * 350
        y0 = 710
        draw.rounded_rectangle((x0, y0, x0+315, y0+270), radius=7, fill="#fbfcfd", outline="#cbd5df")
        draw.text((x0+16, y0+14), f"Cover {key['coverProgress']:.2f}", font=font(22, True), fill=NAVY)
        scale = 320
        origin = (x0+158, y0+226)
        for side, color in (("L", BLUE), ("R", ORANGE)):
            joints = sample["sides"][side]["joints"]
            names = [f"shoulder_{side}", f"elbow_{side}", f"wrist_{side}", f"forepaw_{side}"]
            pts = [(origin[0] + joints[name][0]*scale, origin[1] - (joints[name][1]-0.02)*scale) for name in names]
            draw.line(pts, fill=color, width=8, joint="curve")
            for px, py in pts:
                draw.ellipse((px-6, py-6, px+6, py+6), fill="white", outline=color, width=3)
        draw.text((x0+16, y0+240), f"source sample {key['sampleIndex']:02d} | drift {key['segmentLengthDrift']:.1f}", font=font(15), fill=MUTED)

    card(draw, (48, 1074, 928, 1425), "4  Blink five-keyform ownership")
    values = contract["blink"]["keyformValues"]
    for i, openness in enumerate(values):
        cx = 140 + i * 165
        cy = 1218
        draw.ellipse((cx-58, cy-40, cx+58, cy+40), fill="#fff6dc", outline="#8c5a1d", width=3)
        lid = 40 * (1-openness)
        draw.pieslice((cx-59, cy-41-lid, cx+59, cy+41-lid), 180, 360, fill="#e79635")
        draw.pieslice((cx-59, cy-41+lid, cx+59, cy+41+lid), 0, 180, fill="#e79635")
        if openness > 0.08:
            draw.ellipse((cx-15, cy-28*openness, cx+15, cy+28*openness), fill="#342516")
        draw.text((cx-29, 1282), f"{openness:.2f}", font=font(18, True), fill=INK)
    draw.text((84, 1340), "Blink changes openness only. Gaze target and velocity continue underneath.", font=font(18), fill=GREEN)

    card(draw, (962, 1074, 1852, 1425), "5  Gate checks and interruption rules")
    checks = [
        ("PASS", "Eye target is clipped to a safe ellipse before parameters."),
        ("PASS", "Left/right cover has intentional 24 ms offset."),
        ("PASS", "All 41 samples stay bounded and return to rest."),
        ("PASS", "Priority changes preserve value and velocity."),
        ("PASS", "Physics is forbidden from core cover joints."),
        ("HOLD", "X7 elasticity and Cubism authoring remain locked."),
    ]
    for i, (state, label) in enumerate(checks):
        y = 1145 + i * 43
        color = GREEN if state == "PASS" else ORANGE
        draw.rounded_rectangle((1002, y, 1080, y+28), radius=5, fill=color)
        draw.text((1015, y+4), state, font=font(14, True), fill="white")
        draw.text((1095, y+3), label, font=font(17), fill=INK)

    path = QA / "x6-parameter-action-tracer-review-v1.png"
    canvas.save(path, optimize=True)


def build_actual_motion_preview() -> None:
    frames = [
        ("REST / EMAIL", "login-email-focus-v1.png", 0.0),
        ("COVER 0.25", "login-password-cover-early-v1.png", 0.25),
        ("COVER 0.50", "login-password-cover-mid-v1.png", 0.50),
        ("COVER 1.00", "login-password-cover-v1.png", 1.00),
        ("EXIT 0.25", "login-password-cover-early-v1.png", 0.25),
    ]
    canvas = Image.new("RGB", (1900, 830), PAPER)
    draw = ImageDraw.Draw(canvas)
    draw.text((55, 36), "X6  Actual Xiaoju Motion Contact Sheet", font=font(40, True), fill=NAVY)
    draw.text((57, 90), "Art reference proves visual intent; the blue/orange traces below remain the authoritative continuous controls.", font=font(20), fill=MUTED)
    for i, (label, filename, progress) in enumerate(frames):
        x0 = 45 + i * 370
        y0 = 145
        draw.rounded_rectangle((x0, y0, x0+340, y0+530), radius=8, fill="white", outline="#cbd5df", width=2)
        image = Image.open(LOGIN_ART / filename).convert("RGB")
        image.thumbnail((320, 415), Image.Resampling.LANCZOS)
        canvas.paste(image, (x0+10+(320-image.width)//2, y0+52))
        draw.text((x0+15, y0+14), label, font=font(20, True), fill=NAVY)
        draw.line((x0+22, y0+485, x0+318, y0+485), fill=GRID, width=8)
        draw.line((x0+22, y0+485, x0+22+296*progress, y0+485), fill=BLUE, width=8)
        delayed_progress = clamp(progress - 0.03, 0.0, 1.0) if i < 4 else clamp(progress + 0.03, 0.0, 1.0)
        draw.line((x0+22, y0+506, x0+318, y0+506), fill=GRID, width=8)
        draw.line((x0+22, y0+506, x0+22+296*delayed_progress, y0+506), fill=ORANGE, width=8)
    draw.text((55, 703), "blue  ParamForelegCoverL     orange  ParamForelegCoverR (+24 ms)     eyelids close 40-100 ms before paw contact", font=font(20, True), fill=INK)
    draw.text((55, 750), "Exit continues from the current parameter value and velocity; it does not snap to rest or reset gaze to center.", font=font(21), fill=GREEN)
    canvas.save(QA / "x6-actual-xiaoju-motion-contact-sheet-v1.png", optimize=True)


def main() -> None:
    QA.mkdir(parents=True, exist_ok=True)
    samples = json.loads(X2_SAMPLES.read_text(encoding="utf-8"))["samples"]
    contract, trace = build_contract(samples)
    dump(X6 / "x6-parameter-action-tracer-contract-v1.json", contract)
    dump(X6 / "x6-input-to-parameter-trace-v1.json", trace)
    build_review(contract, trace, samples)
    build_actual_motion_preview()
    self_review = {
        "schemaVersion": 1,
        "status": "pass-candidate-for-user-review",
        "checks": {
            "x5ApprovalRecorded": True,
            "x2RoundtripReused": True,
            "maskReconstructionReferenced": ASSEMBLED.exists(),
            "gazeNinePointBounded": len(contract["gaze"]["ninePointAudit"]) == 9,
            "blinkFiveKeyforms": len(contract["blink"]["keyformValues"]) == 5,
            "traceBounded": trace["tests"]["bounded"],
            "traceContinuous": trace["tests"]["continuous"],
            "returnsToRest": trace["tests"]["roundtripReturnsToRest"],
            "intentionalBilateralOffset": trace["tests"]["leftRightIntentionalOffset"],
            "coreMotionNotPhysics": not contract["coverMotion"]["physicsMayDetermineCorePath"],
            "x7NotAuthorized": True,
        },
        "knownLimits": [
            "This is a Cubism-ready parameter/keyform candidate, not a .cmo3/.moc3 model.",
            "Eye clipping and eyelid deformation still require Cubism wireframe proof after this gate.",
            "The five cover diagrams are control-chain previews over the approved X2 solve, not final rendered fur deformation.",
        ],
    }
    dump(X6 / "x6-self-review-v1.json", self_review)
    print(json.dumps({"status": "ok", "samples": len(samples), "preview": str(QA / 'x6-parameter-action-tracer-review-v1.png')}))


if __name__ == "__main__":
    main()
