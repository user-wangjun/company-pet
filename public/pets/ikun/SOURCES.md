# ikun action notes and sources

The `ikun` action rows are rough desk-pet interpretations of user-requested meme cues. They are not copied frames from source videos.

## Web references

- Bilibili video used as the posture reference for this revision:
  - https://www.bilibili.com/video/BV1ct4y1n7t9/
- Bilibili video used as the `别感冒` reference:
  - https://www.bilibili.com/video/BV1A7rmBrEWX/
- Sinomemes documents the basketball self-introduction meme and transcript containing "练习时长两年半" and "唱、跳、rap、篮球".
  - https://sinomemes.com/index.php/2021/05/09/you-play-basketball-like-cai-xukun/
- Wikipedia's `只因你太美` article describes the song and the "鸡你太美" homophone spread from the basketball-video context.
  - https://zh.wikipedia.org/wiki/%E5%8F%AA%E5%9B%A0%E4%BD%A0%E5%A4%AA%E7%BE%8E
- Wikipedia's `蔡徐坤篮球视频事件` article summarizes the 2019 basketball-video meme context and later secondary creations.
  - https://zh.wikipedia.org/wiki/%E8%94%A1%E5%BE%90%E5%9D%A4%E7%AF%AE%E7%90%83%E8%A7%86%E9%A2%91%E4%BA%8B%E4%BB%B6
- Sina/TMTPost describes "鸡你太美" as an empty-ear reinterpretation of `只因你太美` and mentions the basketball show and dance as the source material for parodies.
  - https://finance.sina.com.cn/roll/2019-04-05/doc-ihvhiqax0230702.shtml

## User-provided cues

- `铁山靠` is represented visually as a no-ball crouch, side pullback, shoulder-led body hit, impact hold, and recoil.
- `胯下运球` uses the user-provided `references/under-leg-dribble-ref.png` as the authoritative 01-08 idle-loop standard.
- `后撤步` and `丢篮球` are represented as first-pass simple basketball actions.
- `别感冒` is represented visually from BV1A7rmBrEWX as a red-scarf cold reminder: shrink shoulders, replace the original down-arm layer with a connected raised sleeve/hand to the mouth, cough/remind, recover.

## Retargeting notes

The final sprites do not copy pixels from source videos. The videos are used for pose timing only: body lean, crouch height, arm placement, leg spread, hand-to-mouth gestures, scarf emphasis, and basketball position are retargeted onto the `ikun` puppet. Some first-pass rows are user-requested prototype actions derived from the three-view model rather than direct video timestamps.

The visible pet artwork is source-image-rigged from the user-provided model image (`reference.png` / `static-frame.png`): hair, face, clothing texture, pendant, and shoes are cut from that image and animated as layered parts. This keeps the character identity aligned with the provided model instead of using a simplified redraw.

The basketball uses a complete round overlay prop matched to the source-image orange/line palette. The original orange-pixel cutout was too fragmented because the reference ball is partially covered by clothing and dark seam lines; the repaired prop prevents the ball from breaking apart during rotation and dribble poses.

This revision splits the action rows into prop-aware series:

- Row 1 is a no-ball tie-shan-kao prototype; the repaired row uses body motion only and avoids standalone shoulder blobs or basketball-like artifacts.
- Row 2 is a no-ball back-view prototype derived from the back model in `reference.png`; it was rebuilt from a clean gap-filled back base so the removed basketball does not leave missing body or arm layers.
- Row 3 is the BV1A7rmBrEWX `别感冒` reference pass: an 8-frame red-scarf, shrink-shoulders, hand-to-mouth cold-reminder gesture. In lift frames, the old down right arm/hand is removed before the raised sleeve is drawn so the pose is not an extra overlay.
- Row 4 is the v12 under-leg dribble standard with basketball visible in every frame. Its pose order, wide crouch, eye line, hand contact, and ball path follow `references/under-leg-dribble-ref.png` frames 01-08.
- Row 6 is a repaired throw prototype: frames 0-3 keep the basketball near the hand/release, while frames 4-7 hide it to avoid a stray floating ball.
- Row 7 is a front-only step-back prototype with one explicit basketball prop in every frame.
- Rows 0, 3, 5, and 8 are no-ball rows and the spritesheet removes the basketball from those rows.

Rows 0 and 8 have visual-only padding cells after their runtime frame counts. These copied settle/recover cells prevent blank atlas slots in QA previews and are not additional source-video motion claims.

## Route 1 action references, 2026-06-02

These user-provided local references were copied into this pet package so the action redraw is reproducible without reading files from the desktop at runtime.

- `references/bie-ganmao-ref.jpg`: row 3 `bie-ganmao`, red-scarf hand-to-mouth cold reminder, no bubble in this pass.
- `references/tieshankao-ref.jpg`: row 1 `tieshankao`, squat/load/side-body shoulder hit, no basketball.
- `references/step-back-ref.jpg`: row 7 `step-back`, dance-footwork step-back with one whole basketball prop.
- `references/character-views-ref.png`: primary character-view sheet for rows 1/3/7 identity and front, side, rear 3/4, back, and side view locking during Route 1 v11 row generation.

## Under-leg dribble reference, 2026-06-06

- `references/under-leg-dribble-ref.png`: user-provided 8-frame action board for row 4 `under-leg-dribble`.
- Frame order is 01 through 08. The package keeps this reference locally so later redraws use the same crouch depth, hand-to-ball contact, eye tracking, and image-left-to-image-right ball path.
- Row 4 is also the `ikun`-specific idle animation, selected by `getPetIdleAnimationName("ikun")`.
