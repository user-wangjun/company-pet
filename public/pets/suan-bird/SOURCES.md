# Sources

- `reference.png`: user-provided “蒜鸟三视图” reference image.
- `action-reference.png`: user-provided “蒜鸟动作设定图” storyboard image.
- `flight-reference.png`: user-provided “飞行动作” storyboard image for drag/move.
- `source-front.png`: generated clean front-facing sprite grounded in `reference.png`.
- `source-side-left.png`: generated clean side-view sprite grounded in `reference.png`.
- `source-back.png`: generated clean back-view sprite grounded in `reference.png`.
- `action-sources/generated-row-*-magenta.png`: high-resolution action strips
  generated from the supplied character and action references on a removable
  magenta background.
- `action-sources/generated-row-*-alpha.png`: chroma-key-cleaned transparent
  versions of the generated strips.
- `action-sources/row-*.png`: normalized transparent action rows selected from
  the generated strips and fitted to 192x208 runtime cells.
- `spritesheet.webp`: package atlas assembled from the action row strips with
  transparent 192x208 runtime cells.
- `qa/build_atlas.py`: deterministic component extraction and atlas build script.
- `qa/validate_render_quality.py`: regression checks for atlas dimensions,
  transparency, WebP fidelity, and minimum facial-detail quality.
- `qa/contact-sheet.png`: visual QA sheet for all 9 runtime rows.
- `qa/previews/*.gif`: per-row motion previews.
- `qa/validation.json`: atlas geometry and transparency validation.

The generated clean sprites and rebuilt action frames preserve the garlic bulb
head, green neckerchief, garlic pendant, round cream bird body, orange beak and
feet, and soft mascot rendering from the supplied references.
