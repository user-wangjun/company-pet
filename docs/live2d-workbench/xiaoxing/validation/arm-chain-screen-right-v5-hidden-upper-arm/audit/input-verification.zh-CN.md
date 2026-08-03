# 阶段 B 输入冻结复核

## 结论

**通过。**

- V4 冻结清单列出的产物均直接从冻结 ZIP 中读取并校验，没有解压或修改 V4 目录。
- 四张权威图像的 SHA-256 均与交接记录一致。
- 两张正面母图均为 `512×1086`。
- 两张正面母图均等于各自三视图从 `(x=34, y=0, width=512, height=1086)` 做出的整数裁切，逐像素一致，没有缩放。

本报告只证明输入身份和正面母图坐标锁定，不证明可见上臂像素所有权、袖口 alpha 边界、连续参数域覆盖或真实纹理质量。

## V4 冻结产物

| 产物 | SHA-256 |
| --- | --- |
| `skeleton.json` | 通过 |
| `materials/solid/sleeve.png` | 通过 |
| `materials/solid/upper_arm.png` | 通过 |
| `materials/solid/forearm.png` | 通过 |
| `materials/solid/hand.png` | 通过 |
| `samples/fk-41-samples.json` | 通过 |
| `audit/stage-a-geometry-report.json` | 通过 |
| `audit/stage-a-regression-wrist-motion.json` | 通过 |
| `qa/default-recomposition.png` | 通过 |
| `qa/displaced-parts-review.png` | 通过 |
| `qa/fk-41-contact-sheet.png` | 通过 |
| `qa/fk-41-slow-preview.gif` | 通过 |
| `qa/seam-stress-review.png` | 通过 |
| `qa/sleeve-boundary-review.png` | 通过 |
| `qa/wrist-motion-review.png` | 通过 |
| `qa/wrist-motion-slow-preview.gif` | 通过 |
| `tools/build_stage_a_geometry.py` | 通过 |

## 权威图像

| 图像 | 尺寸 | SHA-256 |
| --- | ---: | --- |
| `source/xiaoxing-three-view-line.png` | `1448×1086` | 通过 |
| `source/xiaoxing-three-view-color.png` | `1448×1086` | 通过 |
| `source/masters/front-line-source-exact-after-reset.png` | `512×1086` | 通过 |
| `source/masters/front-color-source-exact-after-reset.png` | `512×1086` | 通过 |

## 正面母图整数裁切

| 正面母图 | 尺寸 `512×1086` | 与三视图整数裁切逐像素一致 |
| --- | --- | --- |
| `source/masters/front-line-source-exact-after-reset.png` | 通过 | 通过 |
| `source/masters/front-color-source-exact-after-reset.png` | 通过 | 通过 |

## 下一门禁

在原始整数坐标中建立精确 `V_upper_arm`，并独立锁定袖口遮挡 alpha 边界及 1–3 px 混合带所有权。两项均需中文高倍率视觉审查和用户明确批准；批准前不得计算最终 `H_test` 或补画隐藏纹理。
