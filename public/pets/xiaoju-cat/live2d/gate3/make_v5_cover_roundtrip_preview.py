import json
import math
from pathlib import Path

from PIL import Image

from make_v5_joint_motion_qa import CHAINS, QA, render_pose, target_joints


FPS = 60
COVER_SECONDS = 1.70
HOLD_SECONDS = 0.30
RETURN_SECONDS = 1.70
DELAYS_SECONDS = [0.00, 0.07, 0.13]


def angle_of(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def smootherstep(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * value * value * (value * (value * 6 - 15) + 10)


def interpolate_angles(side: str, elapsed: float, reverse: bool = False) -> list[float]:
    source = CHAINS[side]["source"]
    rest = [angle_of(source[index], source[index + 1]) for index in range(3)]
    cover = CHAINS[side]["coverAngles"]
    duration = RETURN_SECONDS if reverse else COVER_SECONDS
    result = []
    for index, (start, end) in enumerate(zip(rest, cover)):
        # The reverse release starts distally: paw, then forearm, then upper arm.
        delay = DELAYS_SECONDS[2 - index] if reverse else DELAYS_SECONDS[index]
        phase = smootherstep((elapsed - delay) / duration)
        if reverse:
            result.append(end + (start - end) * phase)
        else:
            result.append(start + (end - start) * phase)
    return result


def build_samples() -> list[dict]:
    cover_frames = round((COVER_SECONDS + max(DELAYS_SECONDS)) * FPS)
    hold_frames = round(HOLD_SECONDS * FPS)
    return_frames = round((RETURN_SECONDS + max(DELAYS_SECONDS)) * FPS)
    samples = []
    for frame in range(cover_frames):
        elapsed = frame / FPS
        samples.append({"phase": "cover", "elapsed": elapsed, "angles": {side: interpolate_angles(side, elapsed) for side in CHAINS}})
    for frame in range(hold_frames):
        samples.append({"phase": "hold", "elapsed": frame / FPS, "angles": {side: CHAINS[side]["coverAngles"] for side in CHAINS}})
    for frame in range(return_frames):
        elapsed = frame / FPS
        samples.append({"phase": "return", "elapsed": elapsed, "angles": {side: interpolate_angles(side, elapsed, reverse=True) for side in CHAINS}})
    return samples


def main() -> None:
    samples = build_samples()
    previews = []
    for index, sample in enumerate(samples):
        joints = {side: target_joints(CHAINS[side]["source"], sample["angles"][side]) for side in CHAINS}
        cover_progress = index / max(1, round((COVER_SECONDS + max(DELAYS_SECONDS)) * FPS) - 1)
        if sample["phase"] == "hold":
            occlusion = True
        elif sample["phase"] == "return":
            return_progress = sample["elapsed"] / (RETURN_SECONDS + max(DELAYS_SECONDS))
            occlusion = return_progress < 0.45
        else:
            occlusion = cover_progress > 0.55
        if index % 3 == 0:
            frame, _ = render_pose("roundtrip", joints, draw_joints=False, cover_occlusion=occlusion, analyze=False)
            previews.append(frame.resize((685, 574), Image.Resampling.LANCZOS).convert("P", palette=Image.Palette.ADAPTIVE, colors=192))

    gif_path = QA / "gate3-v5-cover-roundtrip-20fps-preview.gif"
    previews[0].save(gif_path, save_all=True, append_images=previews[1:], duration=50, loop=0, disposal=2, optimize=False)

    max_steps = {}
    for side in CHAINS:
        per_joint = []
        for joint_index in range(3):
            values = [sample["angles"][side][joint_index] for sample in samples]
            per_joint.append(max(abs(values[index] - values[index - 1]) for index in range(1, len(values))))
        max_steps[side] = [round(value, 4) for value in per_joint]
    report = {
        "schemaVersion": 1,
        "sampleRateHz": FPS,
        "previewRateHz": 20,
        "sampleCount": len(samples),
        "durationSeconds": round(len(samples) / FPS, 3),
        "trajectory": "quintic smootherstep with proximal-to-distal lift and distal-to-proximal release delays",
        "maxJointStepDegPerFrameAt60Hz": max_steps,
        "maxObservedStepDeg": max(value for side in max_steps.values() for value in side),
        "jointStepLimitDeg": 3.5,
        "technicalPass": max(value for side in max_steps.values() for value in side) <= 3.5,
        "visualPass": False,
        "visualStatus": "preview_generated_requires_human_review_and_final_live2d_deformer_validation",
    }
    report_path = QA / "gate3-v5-cover-roundtrip-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(gif_path)
    print(report_path)
    print(f"durationSeconds={report['durationSeconds']} maxObservedStepDeg={report['maxObservedStepDeg']} technicalPass={str(report['technicalPass']).lower()} visualPass=false")


if __name__ == "__main__":
    main()
