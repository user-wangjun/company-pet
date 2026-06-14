#!/usr/bin/env python3
"""将 ikun v14 丢球动作元数据更新为 09-17 无球收尾标准。"""

from __future__ import annotations

import json
from pathlib import Path


PET_DIR = Path(__file__).resolve().parents[2]
SOURCE_IMAGE = "references/throw-09-16-ref.png"
FINISH_SOURCE_IMAGE = "references/throw-finish-ref.png"
FINISH_FRAME_PATH = "throw-finish.png"
ATLAS_SOURCE_FRAMES = [f"{index:02d}" for index in range(9, 17)]
SOURCE_FRAMES = [*ATLAS_SOURCE_FRAMES, "17"]
BALL_STATES = [
    {"frame": 0, "state": "low-image-left-hold"},
    {"frame": 1, "state": "chest-level-image-left-hold"},
    {"frame": 2, "state": "finger-spin-lift"},
    {"frame": 3, "state": "finger-spin-high-hold"},
    {"frame": 4, "state": "finger-spin-continuation"},
    {"frame": 5, "state": "return-to-hand-hold"},
    {"frame": 6, "state": "released-image-right"},
    {"frame": 7, "state": "released-far-image-right"},
    {"frame": 8, "state": "absent"},
]
MOTION_PHASES = [
    "低位左侧持球",
    "托球到胸前",
    "抬指起旋",
    "高位旋球保持",
    "旋球延续",
    "回到手中持球",
    "向右出手",
    "篮球继续飞离",
    "篮球消失，保持指向",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def find_by_id(items: list[dict], item_id: str) -> dict:
    return next(item for item in items if item.get("id") == item_id)


def update_actions() -> None:
    path = PET_DIR / "actions.json"
    data = load_json(path)
    data["version"] = 14
    data["notes"] = [
        note
        for note in data.get("notes", [])
        if "throw row hides the ball" not in note
        and "throw row" not in note.lower()
        and "Route 1 v13 replaces row 6" not in note
        and "路线 1 v13" not in note
        and "路线 1 v14" not in note
    ]
    data["notes"].append(
        "路线 1 v14 清理第 6 行脚边白色背景，并追加独立无球收尾帧 throw-finish.png；运行时共 9 帧。"
    )

    series = find_by_id(data["series"], "basketball-throw")
    series.update(
        {
            "displayName": "09-17 连续丢球",
            "basketball": "throw-then-disappear",
            "notes": "09-16 使用图集连续丢球，第 17 帧使用 throw-finish.png 保持指向且篮球完全消失。",
            "reference": SOURCE_IMAGE,
            "finishReference": FINISH_SOURCE_IMAGE,
        }
    )

    action = find_by_id(data["actions"], "throw-basketball")
    action.update(
        {
            "sequenceRole": "throw-reference-09-17-finish",
            "frames": 9,
            "atlasFrames": 8,
            "runtimeFrames": 9,
            "basketball": {
                "mode": "throw-then-disappear",
                "frames": list(range(8)),
                "absentFrames": [8],
                "statesByFrame": BALL_STATES,
                "sourceObservation": "09-16 帧保留完整篮球并向右飞离；第 17 帧保持指向姿势，篮球完全消失。",
            },
            "referenceMatch": "route1-reference-throw-09-17-finish",
            "motionStatus": "reference-standard-v14",
            "cue": "按 09-16 完成持球、旋球和出手，再播放独立第 17 帧，篮球消失并保持向右指向。",
            "sourceImage": SOURCE_IMAGE,
            "finishSourceImage": FINISH_SOURCE_IMAGE,
            "finishFramePath": FINISH_FRAME_PATH,
            "sourceFrames": SOURCE_FRAMES,
            "prototypeFrames": list(range(9)),
        }
    )

    data["revisionNotes"] = [
        note
        for note in data.get("revisionNotes", [])
        if "row 6" not in note.lower()
        and "第 6 行" not in note
    ]
    data["revisionNotes"].append(
        "路线 1 v14：第 6 行 09-16 帧清除脚边白色背景，运行时追加 throw-finish.png 作为无球第 17 帧。"
    )
    save_json(path, data)


def update_action_board() -> None:
    path = PET_DIR / "action-board.json"
    data = load_json(path)
    data["version"] = 14
    data["status"] = "route1-v14-throw-finish"
    data["notes"] = [
        note
        for note in data.get("notes", [])
        if "Throw row hides" not in note
        and "throw row" not in note.lower()
        and "Route 1 v13 replaces row 6" not in note
        and "路线 1 v13" not in note
        and "路线 1 v14" not in note
    ]
    data["notes"].append(
        "路线 1 v14 清理 09-16 帧透明背景，并在运行时追加独立无球收尾帧 throw-finish.png。"
    )

    row = next(item for item in data["currentAtlasRows"] if item.get("row") == 6)
    row.clear()
    row.update(
        {
            "row": 6,
            "actionId": "throw-basketball",
            "seriesId": "basketball-throw",
            "view": "front",
            "basketball": "all-in-atlas-final-none",
            "matchStatus": "reference-standard-v14",
            "review": "图集 09-16 帧完成丢球，独立第 17 帧保持指向且篮球消失；脚边白色背景已清理。",
            "reference": SOURCE_IMAGE,
            "sourceFrames": ATLAS_SOURCE_FRAMES,
            "runtimeFrames": 9,
            "finishFramePath": FINISH_FRAME_PATH,
            "finishReference": FINISH_SOURCE_IMAGE,
        }
    )

    playback = next(
        item
        for item in data["seriesPlayback"]
        if item.get("seriesId") == "basketball-throw"
    )
    playback.update(
        {
            "basketball": "throw-then-disappear",
            "playbackRule": "先播放图集 09-16 八帧，再追加 throw-finish.png；最后一帧篮球完全消失。",
        }
    )

    planned = find_by_id(data["plannedSimpleActions"], "throw-basketball")
    planned.update(
        {
            "status": "reference-standard-v14",
            "basketball": {
                "mode": "throw-then-disappear",
                "frames": list(range(8)),
                "absentFrames": [8],
                "statesByFrame": BALL_STATES,
                "sourceObservation": "09-16 图集帧含球，第 17 帧无球并保持指向。",
            },
            "keyframes": MOTION_PHASES,
            "referenceMatch": "route1-reference-throw-09-17-finish",
            "sourceImage": SOURCE_IMAGE,
            "finishSourceImage": FINISH_SOURCE_IMAGE,
            "finishFramePath": FINISH_FRAME_PATH,
            "sourceFrames": SOURCE_FRAMES,
        }
    )
    save_json(path, data)


def update_pose_map() -> None:
    path = PET_DIR / "pose-map.json"
    data = load_json(path)
    data["revision"] = "route1-v14-throw-finish"
    data["rows"]["6"] = [
        {
            "frame": index,
            "prototypeAction": "throw-basketball",
            "sourceImage": (
                SOURCE_IMAGE if index < 8 else FINISH_SOURCE_IMAGE
            ),
            "sourceFrame": source_frame,
            "view": "front",
            "basketball": BALL_STATES[index]["state"],
            "motionPhase": MOTION_PHASES[index],
            **(
                {"storage": FINISH_FRAME_PATH}
                if index == 8
                else {"storage": "spritesheet.webp row 6"}
            ),
        }
        for index, source_frame in enumerate(SOURCE_FRAMES)
    ]
    data.setdefault("actionReferences", {})["throwBasketball"] = SOURCE_IMAGE
    data["actionReferences"]["throwBasketballFinish"] = FINISH_SOURCE_IMAGE
    save_json(path, data)


def main() -> None:
    update_actions()
    update_action_board()
    update_pose_map()
    print("ikun v14 丢球动作元数据已更新")


if __name__ == "__main__":
    main()
