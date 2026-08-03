# Live2D Gate 1 input audit

- Root: `D:\CodeWorkspace\电脑桌宠\public\pets\xiaoju-cat`
- Automated status: **review_required**
- This report is evidence for review, not automatic gate approval.

## Summary

| Metric | Count/value |
| --- | ---: |
| `images` | 73 |
| `json_files` | 8 |
| `binary_models` | 5 |
| `other_files` | 17 |
| `exact_duplicate_groups` | 7 |
| `near_duplicate_pairs` | 18 |
| `opaque_images` | 24 |
| `full_canvas_alpha_images` | 5 |
| `missing_model_references` | 0 |
| `image_errors` | 0 |
| `json_errors` | 0 |
| `psd_layer_inventory_available` | True |

## Exact duplicate groups

- `live2d/model/xiaoju-planet-login.2048/texture_00.png` ; `live2d/runtime/xiaoju-planet-login/xiaoju-planet-login.2048/texture_00.png`
- `live2d/planet-scene-source/planet-scene-v2-layered-preview.png` ; `live2d/planet-scene-source/pose-keys-v3/00-rest.png`
- `live2d/planet-scene-source/layers/00_Stars_Background.png` ; `live2d/planet-scene-source/layers-v2/00_Stars_Background.png`
- `live2d/planet-scene-source/layers/10_Cat_Body_Base.png` ; `live2d/planet-scene-source/layers-v2/10_Cat_Body_Base.png`
- `live2d/planet-scene-source/layers/50_Planet_Foreground.png` ; `live2d/planet-scene-source/layers-v2/50_Planet_Foreground.png`
- `live2d/planet-scene-source/layers-v2/60_Foreleg_L_Complete.png` ; `live2d/planet-scene-source/layers-v2/70_Cover_Foreleg_L.png`
- `live2d/planet-scene-source/layers-v2/61_Foreleg_R_Complete.png` ; `live2d/planet-scene-source/layers-v2/71_Cover_Foreleg_R.png`

## Near duplicate candidates

- `login-password-cover-early-v1.png` vs `login-password-cover-mid-v1.png` (dHash distance 2)
- `login-password-cover-early-v1.png` vs `login-password-cover-v1.png` (dHash distance 3)
- `login-password-cover-mid-v1.png` vs `login-password-cover-v1.png` (dHash distance 1)
- `live2d/planet-cat-body-no-paws-v1.png` vs `live2d/planet-cat-cutout-grid.png` (dHash distance 3)
- `live2d/planet-cat-body-no-paws-v1.png` vs `live2d/planet-cat-cutout-v1.png` (dHash distance 3)
- `live2d/planet-cat-cutout-grid.png` vs `live2d/planet-cat-cutout-v1.png` (dHash distance 0)
- `live2d/planet-scene-source/planet-scene-layered-preview.png` vs `live2d/planet-scene-source/planet-scene-v2-layered-preview.png` (dHash distance 0)
- `live2d/planet-scene-source/planet-scene-layered-preview.png` vs `live2d/planet-scene-source/pose-keys-v3/00-rest.png` (dHash distance 0)
- `live2d/planet-scene-source/xiaoju-planet-login-live2d-source.psd` vs `live2d/planet-scene-source/xiaoju-planet-login-live2d-v2-source.psd` (dHash distance 0)
- `live2d/planet-scene-source/xiaoju-planet-login-live2d-v3-source.psd` vs `live2d/planet-scene-source/layers-v3/qa-cover-composite.jpg` (dHash distance 1)
- `live2d/planet-scene-source/xiaoju-planet-login-live2d-v3-source.psd` vs `live2d/planet-scene-source/pose-keys-v3/02-halfway.png` (dHash distance 3)
- `live2d/planet-scene-source/layers/40_Eyelid_L.png` vs `live2d/planet-scene-source/layers-v2/40_Eyelid_L.png` (dHash distance 0)
- `live2d/planet-scene-source/layers/41_Eyelid_R.png` vs `live2d/planet-scene-source/layers-v2/41_Eyelid_R.png` (dHash distance 0)
- `live2d/planet-scene-source/layers/60_Paw_L.png` vs `live2d/planet-scene-source/layers-v2/60_Rest_Paw_L.png` (dHash distance 0)
- `live2d/planet-scene-source/layers/61_Paw_R.png` vs `live2d/planet-scene-source/layers-v2/61_Rest_Paw_R.png` (dHash distance 0)
- `live2d/planet-scene-source/pose-keys-v3/03-three-quarter.png` vs `live2d/planet-scene-source/pose-keys-v3/04-cover.png` (dHash distance 3)
- `live2d/source/layered-preview-open.png` vs `live2d/source/xiaoju-login-live2d-source.psd` (dHash distance 0)
- `live2d/source/layers/30_Eyelid_L.png` vs `live2d/source/layers/31_Eyelid_R.png` (dHash distance 0)

## Opaque images

- `login-email-focus-mid-v1.png`
- `login-email-focus-v1.png`
- `login-password-cover-early-v1.png`
- `login-password-cover-mid-v1.png`
- `login-password-cover-v1.png`
- `preview-earth-xiaoju-no-sprout.png`
- `preview-earth-xiaoju.png`
- `three-view-preview.png`
- `live2d/planet-background-v1.png`
- `live2d/planet-cat-body-no-paws-v1.png`
- `live2d/planet-cat-cutout-grid.png`
- `live2d/planet-cat-cutout-v1.png`
- `live2d/planet-scene-source/forelegs-v2-chroma.png`
- `live2d/planet-scene-source/xiaoju-planet-login-live2d-source.psd`
- `live2d/planet-scene-source/xiaoju-planet-login-live2d-v2-source.psd`
- `live2d/planet-scene-source/xiaoju-planet-login-live2d-v3-source.psd`
- `live2d/planet-scene-source/layers-v3/forelegs-chroma.png`
- `live2d/planet-scene-source/layers-v3/forelegs-open-root-chroma.png`
- `live2d/planet-scene-source/layers-v3/qa-cover-composite.jpg`
- `live2d/planet-scene-source/pose-keys-v3/01-quarter.png`
- `live2d/planet-scene-source/pose-keys-v3/02-halfway.png`
- `live2d/planet-scene-source/pose-keys-v3/03-three-quarter.png`
- `live2d/planet-scene-source/pose-keys-v3/04-cover.png`
- `live2d/source/front-master.png`

## Full-canvas alpha images

- `live2d/planet-scene-source/planet-scene-layered-preview.png`
- `live2d/planet-scene-source/planet-scene-v2-layered-preview.png`
- `live2d/planet-scene-source/layers/00_Stars_Background.png`
- `live2d/planet-scene-source/layers-v2/00_Stars_Background.png`
- `live2d/planet-scene-source/pose-keys-v3/00-rest.png`

## Missing model references

None.

## Required human review

- [ ] Visually inspect every exact and near duplicate candidate.
- [ ] Confirm which opaque images are references versus invalid part layers.
- [ ] Open representative PSDs and verify real layer contents and unique names.
- [ ] Choose one identity reference and one default-composition reference.
- [ ] Do not pass Gate 1 until a human records the classifications.

Detailed per-file metadata is stored in the JSON report.
