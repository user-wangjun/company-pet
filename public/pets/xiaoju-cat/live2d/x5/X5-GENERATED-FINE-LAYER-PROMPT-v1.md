# X5 生成式精细分层素材 Prompt v1

> 模式：内置 `imagegen` 编辑/参考图生成。  
> 身份与姿态参考：`live2d/x5/qa/x5-actual-xiaoju-spread-pose-three-view.png`。  
> 输出边界：只用于 X5 精细分层、隐藏毛流补全和三角剖分候选，不是 PSD/Cubism/X6 输出。

```text
Use case: precise-object-edit / production character material separation sheet.
Asset type: Xiaoju Live2D X5 fine layer-source atlas, based strictly on Image 1.
Image 1 role: identity, fur pattern, color, proportions, anatomy, and spread-pose reference. Preserve the same orange-and-white kitten Xiaoju: round kitten head, large amber eyes, pink nose, white muzzle/chest/belly/paws, orange tabby stripes, short rounded limbs, fluffy tail. Do not redesign the cat.
Primary request: create a clean high-resolution exploded material separation sheet containing isolated, non-overlapping source pieces for this exact Xiaoju. Arrange the pieces in orderly rows with generous gaps. Include: head base without eyes; muzzle and jaw; left/right cheek fur; left/right ear root, ear face and ear tip; left/right eye socket base without baked pupil/highlight; separate left/right iris, pupil, highlight, upper lid and lower lid; neck fill; chest fur; ribcage; abdomen; pelvis; left/right scapula fur, upper forelimb, forearm, wrist fur and forepaw; left/right hind thigh, shin/hock and hind paw; tail root socket, tail base, tail mid and tail tip; left/right whisker bundles. Every joint piece must extend beneath its neighbour with natural hidden orange/white fur and consistent fur direction.
View handling: prioritize front-view source pieces, and include side/back-specific torso, limb, head-back, ear-back and tail texture pieces in separate rows. Maintain the exact same body segment lengths and fur identity across views.
Scene/backdrop: perfectly flat solid #00ff00 chroma-key background, one uniform color, no shadows, gradients, texture, floor plane, reflections or lighting variation.
Composition: all pieces fully visible, isolated, uncropped, no overlap, ample padding; atlas layout only.
Style/medium: highly detailed realistic soft kitten fur matching Image 1, clean production cutout edges.
Constraints: no text, no labels, no arrows, no bones, no meshes, no colored control blocks, no extra cat, no duplicated whole body, no props, no watermark. Do not change identity or pose proportions. Do not use #00ff00 anywhere in the cat pieces.
```
