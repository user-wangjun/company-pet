# 蒜鸟

`suan-bird` is a garlic-bird desktop pet built from the user-provided
three-view reference image and action storyboard.

The runtime atlas uses 192x208 cells arranged as 8 columns by 9 rows. The rows
follow the platform animation mapping with `suan-bird`-specific poses:

- row 0: idle / breathing, blink, and wing sway, 6 frames
- row 1: drag / takeoff, six-frame flight loop, and landing, 8 frames
- row 2: reserved left-facing movement / mirrored flight movement, 8 frames
- row 3: tickle / single-click happy crouch and pop, 8 frames
- row 4: crouch alert / water reminder with bottle, 8 frames
- row 5: hug / eye-care reminder with green glasses, 8 frames
- row 6: gnaw / meal reminder with bowl and snack, 8 frames
- row 7: chase / double-click crawl into green blanket, 8 frames
- row 8: eat / sleep reminder with cap and blanket, 6 frames

Runtime interaction mapping:

- drag: takeoff once, loop frames 2-7 while moving, then play current flight pose -> frame 7 -> frame 8 over about 200ms and hold landing for 350ms
- single click: happy wiggle
- double click: play the blanket-crawl row once, hold the wrapped final frame until the 2000ms interaction timeout, then return to idle
- desktop icon interaction: cheerful wing hug
- water reminder: bottle animation
- eye-care reminder: green glasses animation
- meal reminder: bowl and snack animation
- hover: no automatic action; click actions stay distinct
- sleep reminder: sleepy cap-and-blanket animation from row 8
- idle quirks: quiet bob, alert turn, wing hug, chirp yawn, happy wiggle

Pet-specific references, high-resolution generated action strips, transparent
intermediates, and QA notes are kept inside this package. The final atlas is
rebuilt deterministically with `qa/build_atlas.py` and checked with
`qa/validate_render_quality.py`. `qa/contact-sheet.png`,
`qa/previews/*.gif`, and `qa/validation.json` were regenerated with the final
action atlas.
