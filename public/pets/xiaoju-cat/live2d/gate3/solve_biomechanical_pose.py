from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "qa" / "gate3-composite.png"
OUT_PNG = ROOT / "qa" / "gate3-biomechanical-pose-blockout.png"
OUT_JSON = ROOT / "qa" / "gate3-biomechanical-pose-report.json"

G = 9.81


@dataclass(frozen=True)
class Vec:
    x: float
    y: float

    def __add__(self, other: "Vec") -> "Vec":
        return Vec(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec") -> "Vec":
        return Vec(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vec":
        return Vec(self.x * scalar, self.y * scalar)

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def tuple(self) -> tuple[int, int]:
        return round(self.x), round(self.y)


def mix(a: Vec, b: Vec, t: float) -> Vec:
    return a * (1 - t) + b * t


def smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)


def cubic(a: Vec, b: Vec, c: Vec, d: Vec, t: float) -> Vec:
    u = 1 - t
    return a * (u**3) + b * (3 * u * u * t) + c * (3 * u * t * t) + d * (t**3)


def cross(a: Vec, b: Vec) -> float:
    return a.x * b.y - a.y * b.x


def solve_elbow(shoulder: Vec, wrist: Vec, upper: float, fore: float, bend_sign: int) -> Vec:
    delta = wrist - shoulder
    distance = delta.length()
    if distance > upper + fore or distance < abs(upper - fore):
        raise ValueError(f"unreachable wrist distance {distance:.2f}")
    along = (upper * upper - fore * fore + distance * distance) / (2 * distance)
    height = math.sqrt(max(0.0, upper * upper - along * along))
    unit = Vec(delta.x / distance, delta.y / distance)
    base = shoulder + unit * along
    normal = Vec(-unit.y, unit.x)
    candidates = (base + normal * height, base - normal * height)
    # A feline elbow cannot teleport through the limb axis. Keep the same
    # flexion side for the whole gesture; changing side is only legal by
    # passing continuously through full extension, which this motion does not.
    signed = [(cross(delta, point - shoulder), point) for point in candidates]
    valid = [point for value, point in signed if value * bend_sign >= 0]
    if not valid:
        raise ValueError("no elbow solution on requested bend side")
    return valid[0]


def vec_from_angle(length: float, degrees: float) -> Vec:
    radians = math.radians(degrees)
    return Vec(math.cos(radians) * length, math.sin(radians) * length)


def joint_angle(a: Vec, pivot: Vec, b: Vec) -> float:
    first = a - pivot
    second = b - pivot
    cosine = (first.x * second.x + first.y * second.y) / (first.length() * second.length())
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def gravity_torques(shoulder: Vec, elbow: Vec, wrist: Vec, paw: Vec, masses: tuple[float, float, float]) -> dict[str, float]:
    m_upper, m_fore, m_paw = masses
    upper_com = mix(shoulder, elbow, 0.5)
    fore_com = mix(elbow, wrist, 0.5)
    paw_com = mix(wrist, paw, 0.5)
    # In the screen plane, gravity is +Y; the moment arm is horizontal distance.
    shoulder_tau = G * (
        m_upper * (upper_com.x - shoulder.x)
        + m_fore * (fore_com.x - shoulder.x)
        + m_paw * (paw_com.x - shoulder.x)
    )
    elbow_tau = G * (
        m_fore * (fore_com.x - elbow.x)
        + m_paw * (paw_com.x - elbow.x)
    )
    wrist_tau = G * m_paw * (paw_com.x - wrist.x)
    return {"shoulder": shoulder_tau, "elbow": elbow_tau, "wrist": wrist_tau}


def frame_pose(progress: float) -> dict:
    eased = smoothstep(progress)
    left_eased = smoothstep(min(1.0, progress / 0.92))
    right_eased = smoothstep(max(0.0, (progress - 0.07) / 0.93))

    # Shoulder joints sit on the upper-lateral ribcage, not at the belly/planet
    # contact line. Keeping them high prevents the forelimbs from having to
    # over-extend just to reach the face.
    left_shoulder = mix(Vec(560, 720), Vec(555, 705), left_eased)
    right_shoulder = mix(Vec(900, 690), Vec(905, 680), right_eased)

    left_wrist = mix(Vec(670, 820), Vec(630, 490), left_eased) + Vec(25 * math.sin(math.pi * left_eased), 0)
    right_wrist = mix(Vec(1070, 710), Vec(930, 485), right_eased) + Vec(20 * math.sin(math.pi * right_eased), 0)

    left_elbow = solve_elbow(left_shoulder, left_wrist, 150, 150, bend_sign=1)
    right_elbow = solve_elbow(right_shoulder, right_wrist, 145, 145, bend_sign=1)

    left_paw_angle = -38 - 18 * left_eased
    right_paw_angle = -42 - 22 * right_eased
    left_paw = left_wrist + vec_from_angle(70, left_paw_angle)
    right_paw = right_wrist + vec_from_angle(68, right_paw_angle)

    head_counter_angle = -2.4 * left_eased + 1.8 * right_eased
    chest_center = Vec(705, 790)
    pelvis_center = Vec(500, 980)
    body_com = Vec(640 - 8 * eased, 815 + 4 * eased)
    contacts = [Vec(520, 860), Vec(920, 735), Vec(470, 1010)]
    support_min_x = min(point.x for point in contacts)
    support_max_x = max(point.x for point in contacts)

    result = {
        "progress": progress,
        "head_counter_angle_deg": head_counter_angle,
        "volumes": {
            "head": {"center": [775, 390], "size": [720, 650], "scale": [1.0, 1.0]},
            "ribcage": {"center": [chest_center.x, chest_center.y], "size": [500, 430], "scale": [1.0, 1.0]},
            "pelvis": {"center": [pelvis_center.x, pelvis_center.y], "size": [410, 260], "scale": [1.0, 1.0]},
        },
        "body_com": [body_com.x, body_com.y],
        "contacts": [[p.x, p.y] for p in contacts],
        "com_inside_support_x": support_min_x <= body_com.x <= support_max_x,
        "arms": {},
    }

    for key, shoulder, elbow, wrist, paw, lengths in (
        ("view_l", left_shoulder, left_elbow, left_wrist, left_paw, (150, 150, 70)),
        ("view_r", right_shoulder, right_elbow, right_wrist, right_paw, (145, 145, 68)),
    ):
        measured = ((elbow - shoulder).length(), (wrist - elbow).length(), (paw - wrist).length())
        elbow_angle = joint_angle(shoulder, elbow, wrist)
        result["arms"][key] = {
            "shoulder": [shoulder.x, shoulder.y],
            "elbow": [elbow.x, elbow.y],
            "wrist": [wrist.x, wrist.y],
            "paw": [paw.x, paw.y],
            "target_lengths": list(lengths),
            "measured_lengths": list(measured),
            "max_length_error_pct": max(abs(a - b) / b * 100 for a, b in zip(measured, lengths)),
            "elbow_flexion_angle_deg": elbow_angle,
            "elbow_bend_cross": cross(wrist - shoulder, elbow - shoulder),
            "gravity_torque_relative": gravity_torques(shoulder, elbow, wrist, paw, (0.32, 0.22, 0.15)),
        }
    return result


def ellipse(draw: ImageDraw.ImageDraw, center: Vec, size: tuple[int, int], color: tuple[int, int, int, int], label: str) -> None:
    width, height = size
    box = (center.x - width / 2, center.y - height / 2, center.x + width / 2, center.y + height / 2)
    draw.ellipse(box, fill=color, outline=(255, 255, 255, 220), width=3)
    font = ImageFont.load_default(size=20)
    draw.text((center.x - 45, center.y - 10), label, font=font, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 220))


def draw_chain(draw: ImageDraw.ImageDraw, points: list[Vec], color: tuple[int, int, int, int]) -> None:
    draw.line([point.tuple() for point in points], fill=color, width=14, joint="curve")
    for point in points:
        x, y = point.tuple()
        draw.ellipse((x - 11, y - 11, x + 11, y + 11), fill=color, outline=(255, 255, 255, 255), width=3)


base = Image.open(SOURCE).convert("RGBA")
frames = []
reports = []
for progress in (0.0, 0.25, 0.5, 0.75, 1.0):
    report = frame_pose(progress)
    reports.append(report)
    frame = base.copy()
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, 0, frame.width, frame.height), fill=(2, 5, 18, 105))

    ellipse(draw, Vec(775, 390), (720, 650), (255, 70, 90, 55), "HEAD")
    ellipse(draw, Vec(705, 790), (500, 430), (70, 150, 255, 65), "RIBCAGE")
    ellipse(draw, Vec(500, 980), (410, 260), (255, 190, 60, 70), "PELVIS")

    for contact in report["contacts"]:
        x, y = round(contact[0]), round(contact[1])
        draw.rectangle((x - 14, y - 14, x + 14, y + 14), fill=(80, 255, 110, 240), outline=(255, 255, 255, 255), width=3)

    for key, color in (("view_l", (255, 80, 190, 245)), ("view_r", (160, 90, 255, 245))):
        arm = report["arms"][key]
        points = [Vec(*arm[name]) for name in ("shoulder", "elbow", "wrist", "paw")]
        draw_chain(draw, points, color)

    com_x, com_y = report["body_com"]
    draw.ellipse((com_x - 15, com_y - 15, com_x + 15, com_y + 15), fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=3)
    draw.line((com_x, com_y, com_x, com_y + 95), fill=(255, 255, 255, 230), width=5)
    draw.polygon(((com_x, com_y + 110), (com_x - 12, com_y + 88), (com_x + 12, com_y + 88)), fill=(255, 255, 255, 230))

    font = ImageFont.load_default(size=24)
    draw.rounded_rectangle((18, 18, 250, 58), 8, fill=(0, 0, 0, 190))
    draw.text((30, 28), f"cover={progress:.2f}", font=font, fill=(255, 255, 255, 255))

    frame = Image.alpha_composite(frame, overlay)
    frame.thumbnail((420, 352), Image.Resampling.LANCZOS)
    frames.append(frame)

sheet = Image.new("RGBA", (sum(frame.width for frame in frames), max(frame.height for frame in frames)), (24, 24, 28, 255))
x = 0
for frame in frames:
    sheet.alpha_composite(frame, (x, 0))
    x += frame.width
sheet.save(OUT_PNG)

summary = {
    "source": str(SOURCE),
    "invariants": {
        "body_volume_scales": "all 1.0; contact compression is local only",
        "segment_length_error_limit_pct": 3.0,
        "elbow_flexion_range_deg": [35.0, 140.0],
        "scapula_slide_limit_px": 30.0,
        "com_must_remain_inside_contact_x_hull": True,
    },
    "frames": reports,
    "pass": all(
        frame["com_inside_support_x"]
        and all(
            arm["max_length_error_pct"] <= 3.0
            and 35.0 <= arm["elbow_flexion_angle_deg"] <= 140.0
            and arm["elbow_bend_cross"] > 0
            for arm in frame["arms"].values()
        )
        for frame in reports
    ),
}

# A five-key contact sheet can miss an IK branch flip. Audit a dense sequence
# and fail if any elbow/wrist/paw jumps farther than 35 px per 0.025 progress.
dense = [frame_pose(i / 40) for i in range(41)]
max_step = 0.0
max_elbow_angle_step = 0.0
for previous, current in zip(dense, dense[1:]):
    for side in ("view_l", "view_r"):
        for joint in ("elbow", "wrist", "paw"):
            a = Vec(*previous["arms"][side][joint])
            b = Vec(*current["arms"][side][joint])
            max_step = max(max_step, (b - a).length())
        max_elbow_angle_step = max(
            max_elbow_angle_step,
            abs(
                current["arms"][side]["elbow_flexion_angle_deg"]
                - previous["arms"][side]["elbow_flexion_angle_deg"]
            ),
        )
left_shoulder_slide = (Vec(*dense[-1]["arms"]["view_l"]["shoulder"]) - Vec(*dense[0]["arms"]["view_l"]["shoulder"])).length()
right_shoulder_slide = (Vec(*dense[-1]["arms"]["view_r"]["shoulder"]) - Vec(*dense[0]["arms"]["view_r"]["shoulder"])).length()
final_left_paw = Vec(*dense[-1]["arms"]["view_l"]["paw"])
final_right_paw = Vec(*dense[-1]["arms"]["view_r"]["paw"])
face_contact_ok = (
    620 <= final_left_paw.x <= 740
    and 390 <= final_left_paw.y <= 600
    and 890 <= final_right_paw.x <= 1040
    and 380 <= final_right_paw.y <= 590
)
summary["invariants"]["dense_max_joint_step_px"] = max_step
summary["invariants"]["dense_max_joint_step_limit_px"] = 35.0
summary["invariants"]["dense_max_elbow_angle_step_deg"] = max_elbow_angle_step
summary["invariants"]["dense_max_elbow_angle_step_limit_deg"] = 8.0
summary["invariants"]["scapula_slide_px"] = {
    "view_l": left_shoulder_slide,
    "view_r": right_shoulder_slide,
}
summary["invariants"]["final_paw_face_contact_windows_ok"] = face_contact_ok
summary["pass"] = (
    summary["pass"]
    and max_step <= 35.0
    and max_elbow_angle_step <= 8.0
    and max(left_shoulder_slide, right_shoulder_slide) <= 30.0
    and face_contact_ok
)
OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(OUT_PNG)
print(OUT_JSON)
print(f"pass={summary['pass']}")
