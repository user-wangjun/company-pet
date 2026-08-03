# X4 小橘语义分层视觉审核

> 状态：X4 分层候选已生成，等待用户视觉审核。  
> X4 只负责分层、隐藏补全、安全重叠和绘制顺序；不授权 X5 三角剖分、ArtMesh、Cubism 或运行时。

## 必看预览

- `qa/x4-layer-separation-overview.png`：分层总览、绘制顺序和审核重点。
- `qa/x4-expanded-hidden-fill-check.png`：把头、四肢、尾巴移开后的隐藏补全/安全重叠检查。
- `x4-layer-separation-contract.json`：机器可读分层合同。

## 图层候选

| ID | 内容 | 父区域 | 隐藏补全/重叠 | Draw |
| --- | --- | --- | --- | --- |
| `planet_back` | 星球后层 | `PlanetRoot` | behind Xiaoju and planet rim | 10 |
| `tail_base` | 尾根插口 | `Pelvis` | large overlap under pelvis and tail_mid | 90 |
| `tail_mid` | 尾中段 | `TailRoot` | under tail_base and tail_tip | 95 |
| `tail_tip` | 尾尖 | `TailMid` | overlap into tail_mid | 100 |
| `hind_leg_L` | 左后腿 | `Pelvis` | hip/thigh fill under pelvis | 150 |
| `hind_leg_R` | 右后腿 | `Pelvis` | hip/thigh fill under pelvis | 151 |
| `pelvis` | 骨盆/臀部 | `BodyRoot` | under abdomen, legs, tail root | 210 |
| `abdomen` | 腹部软层 | `BodyRoot` | under ribcage and pelvis | 220 |
| `ribcage` | 胸腔/躯干 | `BodyRoot` | under neck, forelimbs, chest fur | 230 |
| `neck_chest_fur` | 颈胸毛软层 | `Neck` | bridges head, neck, chest | 300 |
| `forelimb_L` | 左前肢整链 | `Scapula_L` | shoulder/elbow/wrist sleeve overlap | 360 |
| `forelimb_R` | 右前肢整链 | `Scapula_R` | shoulder/elbow/wrist sleeve overlap | 361 |
| `head_base` | 头骨/脸底 | `Neck` | complete underside under ears/muzzle/eyes | 500 |
| `muzzle_jaw` | 口鼻/下颌 | `Head` | under cheek fur and eye region | 540 |
| `cheek_fur_L` | 左脸颊毛 | `Head` | overlaps head edge and neck | 560 |
| `cheek_fur_R` | 右脸颊毛 | `Head` | overlaps head edge and neck | 561 |
| `ear_L` | 左耳根/耳面/耳尖 | `Head` | ear root wedge under head fur | 620 |
| `ear_R` | 右耳根/耳面/耳尖 | `Head` | ear root wedge under head fur | 621 |
| `eye_L_parts` | 左眼组 | `EyeSocket_L` | socket mask, lids, pupil, highlight separated in X5 | 700 |
| `eye_R_parts` | 右眼组 | `EyeSocket_R` | socket mask, lids, pupil, highlight separated in X5 | 701 |
| `whisker_L` | 左胡须束 | `Muzzle` | root tucked under muzzle | 760 |
| `whisker_R` | 右胡须束 | `Muzzle` | root tucked under muzzle | 761 |
| `planet_front` | 星球前景边缘/接触阴影 | `PlanetRoot` | front occluder only, not anatomy | 900 |

## 审核问题

1. 这些层是否足够支持之后的遮眼、目光、耳朵、尾巴和呼吸微动？
2. 头、前肢、后肢、尾巴移开后，绿色隐藏补全区是否足够，不会露洞？
3. 眼睛是否应该在 X4 就进一步拆成眼底/虹膜/瞳孔/高光/上下眼睑/眼眶遮罩，还是等 X5 合同里细化？
4. 星球前景遮挡与小橘身体是否分得够清楚？

## Gate 决策

- 说 `X4 通过`：授权进入 X5，在真实图层边界内做三角剖分、辅助点和 Layer-Mesh-Node 合同。
- 说 `X4 不通过` 或指出具体问题：继续只修 X4 分层，不进入 X5。
