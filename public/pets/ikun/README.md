# ikun

Desktop pet package created from the provided three-view reference image.

- `spritesheet.png` contains the source-image-rigged action set across the existing 192x208 cell grid.
- `actions.json` records the action series, row numbers, frame counts, basketball-prop timing, and current temporary runtime row mapping.
- `rig.json` records the movable body joints, basketball whole-prop rule, front/back view rule, and strap constraints.
- `action-board.json` separates current atlas rows from future precision redraws and marks the first simple actions now implemented in the atlas.
- `pose-map.json` records the Bilibili source URL, video-linked rows, and prototype frame semantics.
- `icon-hug.png` is a short warming/shiver placeholder sheet required by the current platform loader.
- `reference.png` keeps the original source image in the pet package for future animation work.
- `qa/contact-sheet.png` and `qa/previews/` are visual QA artifacts for reviewing the animations.

This revision uses the original user-provided model image as the visual source. The repaired action pass includes no-ball tie-shan-kao, no-ball back-view motion, under-leg dribble, short throw, and step-back. The basketball is drawn as a complete round prop, rotates as one object, and is removed from rows or frames that are marked no-ball. Row 1 tie-shan-kao is body-led and does not use a standalone shoulder blob.

Row 0 has fewer runtime frames than the 8-column atlas. Its unused cells are padded with settle/recover poses for visual QA only; `actions.json` still records the real runtime frame count. Row 2 was full-cell rebuilt as a no-ball back-view row so basketball removal no longer leaves missing body layers. Row 3 now uses the BV1A7rmBrEWX `别感冒` reference as an 8-frame red-scarf cold-reminder gesture; the lift frames remove the original down right arm before drawing the connected sleeve and hand-to-mouth pose.

### Route 1 v11 refinement

- Row 1 `tieshankao`: uses `references/tieshankao-ref.jpg`; no basketball; shoulder/back body hit with squat, load, impact, and recoil.
- Row 3 `bie-ganmao`: uses `references/bie-ganmao-ref.jpg`; no basketball; red-scarf hand-to-mouth cold reminder; no bubble in this pass.
- Row 7 `step-back`: uses `references/step-back-ref.jpg`; one complete basketball prop in every frame.
- Rows 1/3/7 should use `references/character-views-ref.png` as the primary identity/view lock.

### Route 1 v12 under-leg dribble standard

- Row 4 `under-leg-dribble` uses `references/under-leg-dribble-ref.png` as the authoritative 01-08 sequence.
- The same row is the `ikun`-specific idle animation through runtime animation `crouchAlert`.
- The loop standard is: image-left hold, lower, center entry, deepest under-leg crouch, emerge, low control, center return, image-right catch.
- Every frame contains exactly one complete basketball. Eyes, hands, leg spread, and crouch height follow the reference rather than the old nearly-standing prototype.

### 路线 1 v14 丢球动作标准

- 第 6 行图集使用 `references/throw-09-16-ref.png` 的 09-16 连续动作。
- 运行时在图集八帧后追加 `throw-finish.png`，形成 9 帧完整动作。
- 第 17 帧来自 `references/throw-finish-ref.png`，人物保持向右指向，篮球完全消失。
- 所有帧都清除灰色背景、编号、地面阴影、腿间白块和白色动效线。
- 原来的第 6 行丢球图片已全部移除，不与新动作混用。

## Action rows

| Row | Frames | Series | Action | Basketball |
| --- | ---: | --- | --- | --- |
| 0 | 6 | 开场无球站定 | 待机准备 | 无 |
| 1 | 8 | 无球铁山靠 | 铁山靠 | 无 |
| 2 | 8 | 背面无球动作 | 背面无球动作 | 无 |
| 3 | 8 | 无球手势收尾 | 别感冒 | 无 |
| 4 | 8 | 胯下运球 | 胯下运球 | 全帧有 |
| 5 | 8 | 副歌无球舞步 | 姬霓太美舞步 | 无 |
| 6 | 9 | 09-17 连续丢球 | 丢篮球 | 前 8 帧有，第 9 帧消失 |
| 7 | 8 | 后撤步 | 后撤步 | 全帧有 |
| 8 | 6 | 无球手势收尾 | 练习收尾 | 无 |

## Motion review

当前动作行处于不同精修阶段。`action-board.json` 将第 1 行记录为身体带动的铁山靠，第 2 行记录为重建的背面无球动作，第 3 行记录为 BV1A7rmBrEWX `别感冒` 参考动作，第 4 行记录为用户确认的 v12 待机胯下运球标准，第 6 行记录为 v14 九帧丢球标准，第 7 行记录为正面后撤步修复，第 8 行记录为用户提供的双击跳跃动作。

`qa/motion-review.json` tracks `paddingCells` for the copied visual-only cells and keeps `blankCells` empty.
It also records row 2 in `repairedRows` because that row was rebuilt to fix the missing back-body layer.

The implemented simple action pass is:

| Action | View | Basketball rule | Note |
| --- | --- | --- | --- |
| 铁山靠 | 正面/微侧 | 无球 | 下沉、侧向蓄力、身体带肩顶出、停顿、回弹。 |
| 别感冒 | 正面 | 无球 | 红围巾、缩肩；抬手帧先移除原本下垂的右手/袖口，再把袖子连到嘴边的黄手，轻咳/提醒后回收。 |
| 胯下运球 | 正面 | 全帧有球 | 严格按 `references/under-leg-dribble-ref.png` 的 01-08 顺序，宽站姿下蹲并从胯下穿球；这是 `ikun` 的待机动作标准。 |
| 后撤步 | 正面 | 全帧有球 | 重心后移，球跟手走并整体旋转。 |
| 丢篮球 | 正面 | 前 8 帧有球，第 9 帧无球 | 按 09-16 完成持球、旋球和出手，再播放 `throw-finish.png`，保持指向并让篮球完全消失。 |

Back-facing moves must be drawn from the back model in `reference.png`; do not rotate or mirror the front face for back actions. Overall straps follow the torso and shoulder joints, and back-view straps should use the back-derived crossed shape.
