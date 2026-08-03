# Live2D Gate 1 input audit

- Root: `D:\CodeWorkspace\电脑桌宠\docs\live2d-workbench\xiaoxing`
- Automated status: **review_required**
- This report is evidence for review, not automatic gate approval.

## Summary

| Metric | Count/value |
| --- | ---: |
| `images` | 2 |
| `json_files` | 0 |
| `binary_models` | 0 |
| `other_files` | 0 |
| `exact_duplicate_groups` | 0 |
| `near_duplicate_pairs` | 1 |
| `opaque_images` | 2 |
| `full_canvas_alpha_images` | 0 |
| `missing_model_references` | 0 |
| `image_errors` | 0 |
| `json_errors` | 0 |
| `psd_layer_inventory_available` | False |

## Exact duplicate groups

None.

## Near duplicate candidates

- `source/xiaoxing-three-view-color.png` vs `source/xiaoxing-three-view-line.png` (dHash distance 2)

## Opaque images

- `source/xiaoxing-three-view-color.png`
- `source/xiaoxing-three-view-line.png`

## Full-canvas alpha images

None.

## Missing model references

None.

## Required human review

- [ ] Visually inspect every exact and near duplicate candidate.
- [ ] Confirm which opaque images are references versus invalid part layers.
- [ ] Open representative PSDs and verify real layer contents and unique names.
- [ ] Choose one identity reference and one default-composition reference.
- [ ] Do not pass Gate 1 until a human records the classifications.

Detailed per-file metadata is stored in the JSON report.
