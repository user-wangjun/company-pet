# 小橘 X1 统一身体报告

> 状态：候选，等待用户 X1 Gate 审核。本文不授权进入 X2、生成完整母版、拆层或 Cubism。

## 产物

- `x1-canonical-body-contract.json`：统一三维近似骨架、固定骨段、质量块、视图标注和 Gate 约束。
- `qa/x1-three-view-landmark-overlay.png`：三视图骨架、可见性与质量块叠加图。
- `qa/x1-three-view-review-sheet.png`：原图与标注图上下对照。
- `qa/x1-canonical-skeleton-projections.png`：同一套近似 3D 骨架与质量块的正、侧、顶投影。
- `qa/x1-spread-pose-review-aid.png`：大字型/展开姿势工程草图，只用于 X1 视觉审核辅助，不是写实母版。

## 解释边界

源图的三个视角在尺寸和地面基线上一致，但不是经过相机标定的严格正交工程图。毛发和坐姿遮住肩胛、髋、远侧肢体与部分尾根，因此本阶段只冻结：

1. 同名解剖点和左右身份；
2. 一套近似 3D 拓扑与骨段长度；
3. 头、肋笼、腹部和骨盆四个不可坍缩质量块；
4. 前肢、后肢和尾巴的连续父子链；
5. 推断点的风险等级。

X1 不声称已经得到精确猫科三维扫描，也不在此阶段确定遮眼动作的数值关节范围。动作范围、接触和力矩属于 X2。

## X1 修订：眼部参考锚点

本版根据用户审核意见补充头部局部参考锚点：`eye_socket_L/R`、`eye_center_L/R`、`eye_safe_ellipse_L/R`、`eye_cover_zone_L/R`，以及 `ear_base_L/R`、`ear_tip_L/R`、`ear_inner_L/R`。这些锚点只用于后续 X2 遮眼目标、X5 节点支点、X6 眼部参数和 X7 耳朵弹性控制的共同坐标依据。

这些锚点不是眼球转动解、眼睑 Deformer、耳朵 Deformer、耳尖 Physics、爪部接触、重心支撑或力矩求解。侧视右眼、背视双眼和部分耳内面仍按遮挡/推断风险处理。

## X1 修订：耳朵参考链

本版补充 `headReferenceSegments`，把耳朵锚点接回头骨：`skull_center -> ear_base_L/R -> ear_tip_L/R`，并从 `ear_base_L/R` 接到 `ear_inner_L/R`。这样后续 X5-X7 可以明确从头部运动传递到耳根，再由耳根带动耳尖和耳面。

这些线仍然只是头部局部拓扑和力矩传递参考，不是耳朵 Rotation Deformer、ArtMesh、Physics 或弹性数值。耳朵实际摆动、耳尖滞后、耳面压缩和注意力参数必须留到后续 Gate。

## X1 修订：力矩预检边界

本版在合同中加入 `momentPreflight`，只列出未来必须求解的力矩链：

- 遮眼前肢链：肩胛、肩、肘、腕、前爪到 `eye_cover_zone`；
- 眼部链：头骨、眼眶、眼球中心、上下眼睑。

X1 仍禁止数值力矩、接触反力、重心支撑、眼部 Deformer 支点和任何动作曲线。它们必须在 X2 或 X5-X6 获得用户 Gate 批准后再解。

## X1 修订：肌肉/软组织包络控制区

本版根据用户审核意见补充 `softTissueControlZones`，用于说明关键骨架周边的肌肉、皮肤和毛发包络以后应如何被控制。它们包括：

- 颈部、脸颊和胸毛软层；
- 左右耳根、耳面和耳尖软组织；
- 左右肩胛到胸侧的软组织吊带；
- 左右前肢上臂/前臂包络；
- 胸腹表皮包络；
- 左右髋、大腿和后腿包络；
- 尾根毛发/皮肤插口。

这些区域只是在 X1 阶段标出未来 X4/X5 拆层、ArtMesh 和 Deformer 的控制依据。它们不是正式网格、不是 Rotation Deformer、不是 Physics 分组，也不定义权重、曲线或变形极值。后续正式控制必须在 X4/X5 Gate 中逐层填写合同并用视觉证据验证。

## X1 修订：肌肉力矩参考锚点

本版在 `softTissueControlZones` 之外补充 `softTissueMomentAnchors`。这些锚点用紫色或青绿色菱形和短向量标在 QA 图中，只表示未来软组织控制的 pivot / pull 方向，例如肩胛胸侧吊带、前臂包络、腹部皮肤、髋腿包络、尾根插口和耳根到耳尖的注意力/弹性方向。

这些锚点不是数值力矩解，不包含扭矩大小、弹簧刚度、阻尼、权重、ArtMesh 拓扑或 Physics 设置。它们只保证后续 X4/X5 设计 Deformer 和网格时不会只看到骨架线，而能同时看到周边肌肉/毛皮应围绕哪些点被牵拉。

## X1 修订：辅助关节与三角剖分种子

本版根据用户审核意见补充 `auxiliaryReferenceJoints`、`auxiliaryJoints2D/3D` 和 `auxiliaryReferenceSegments`。新增点包括脸颊毛、胡须根、耳中点、胸毛尖、左右腋下、前后爪趾缘和尾根套口。这些点用于后续 X4/X5 拆层、节点树和 ArtMesh 设计时保留语义边界，也给未来三角剖分提供清楚的边界点和内部控制种子。

用户提供的知乎文章 `https://zhuanlan.zhihu.com/p/383268858` 被记录为参考来源；实现时页面直接抓取不稳定，因此本 X1 只采纳通用网格原则：未来网格需要明确顶点、边和三角面，关键解剖边界与局部支点应先作为语义点保留。X1 仍不生成 Delaunay/Cubism 三角剖分、不定义 ArtMesh 顶点表、不写权重、不设置 Deformer，也不进入 X2。

## 后续产物请求：大字型小橘参考图

用户提出需要一张大字型/展开姿势的小橘图，以便后续更清楚地绘制隐藏肢体、躯干和眼部相关部分。该需求已记录到合同的 `futureArtifactRequests.spreadPoseXiaojuPlate`。

本 X1 版本只生成 `qa/x1-spread-pose-review-aid.png` 作为工程草图：它展示统一骨架、体块、展开四肢、眼部锚点和遮眼目标区，帮助人工判断结构是否清楚。它不是写实完整图，不替代三视图权威输入，不授权 X2，也不作为后续拆层母版。

真正可用于绘制隐藏结构或拆层的写实大字型参考图仍属于后续 Gate。后续若授权，必须从已批准的 X1 身体和 X2 支撑/动作约束派生，不能替代三视图权威输入，也不能绕过隐藏结构验证。

## 生物学拓扑核验

- 前肢按猫科研究中的肩胛、上臂、前臂、腕段建模，并保留肩、肘、腕三个主要关节。侧视折叠链已修正为肩在前、肘向后、腕和爪再回到前方。
- 后肢保持髋、膝、跗/踝、爪的连续链；X1 只冻结拓扑，不把三维研究中的成人猫关节角直接套到小橘的幼猫比例上。
- 姿势研究用于确认关节力与末端支撑必须联合求解；这些力矩和接触数值仍严格留在 X2。
- 眼部锚点用于保留头部局部坐标和未来眼眶安全范围；眼球、眼睑和遮眼接触力矩尚未求解。

参考：

- [Role of forelimb morphology in muscle sensorimotor functions during locomotion in the cat](https://pmc.ncbi.nlm.nih.gov/articles/PMC11737544/)
- [A Three Dimensional Model of the Feline Hindlimb](https://pmc.ncbi.nlm.nih.gov/articles/PMC2043500/)
- [Biomechanical capabilities influence postural control strategies in the cat hindlimb](https://pmc.ncbi.nlm.nih.gov/articles/PMC3137431/)

## 标注统计

- 可见或部分可见观察：24
- 推断观察：42
- 完全遮挡观察：18
- 质量比例合计：1.00
- 归一化垂直对齐最大 spread：0.0111
- 归一化垂直对齐平均 spread：0.0037
- X1 审核阈值：0.0600

## 三视图垂直一致性

归一化值以各视图地面到身体顶部的高度为 1。它用于发现视图比例漂移，不代表三维深度。

| Landmark | Front | Side | Back | Spread |
| --- | ---: | ---: | ---: | ---: |
| `skull_center` | 0.7429 | 0.7365 | 0.7429 | 0.0063 |
| `jaw_center` | 0.5683 | 0.5683 | 0.5683 | 0.0000 |
| `neck_base` | 0.4873 | 0.4857 | 0.4921 | 0.0063 |
| `ribcage_center` | 0.3714 | 0.3714 | 0.3683 | 0.0032 |
| `abdomen_center` | 0.1968 | 0.2079 | 0.2063 | 0.0111 |
| `pelvis_center` | 0.1508 | 0.1619 | 0.1619 | 0.0111 |
| `shoulder_L` | 0.4095 | 0.4032 | 0.4032 | 0.0063 |
| `elbow_L` | 0.2603 | 0.2571 | 0.2571 | 0.0032 |
| `wrist_L` | 0.1079 | 0.1095 | 0.1095 | 0.0016 |
| `forepaw_L` | 0.0317 | 0.0317 | 0.0317 | 0.0000 |
| `hip_L` | 0.2603 | 0.2603 | 0.2603 | 0.0000 |
| `knee_L` | 0.1556 | 0.1587 | 0.1587 | 0.0032 |
| `hock_L` | 0.0730 | 0.0730 | 0.0730 | 0.0000 |
| `hindpaw_L` | 0.0317 | 0.0317 | 0.0317 | 0.0000 |

## 自动自检

- [x] same landmark vocabulary in all three views
- [x] mass fractions sum to one
- [x] canonical paired joints are symmetric
- [x] vertical alignment spread below review threshold
- [x] side forelimbs fold shoulder-to-caudal-elbow-to-cranial-wrist
- [x] canonical forelimbs preserve the caudal elbow branch
- [x] X2 remains unauthorized

## 必须由用户视觉确认的点

- 肩胛和肩关节是否偏高或偏外；
- 侧视髋、膝、跗的折叠方向是否符合小橘体型；
- 背视前肢完全遮挡时的左右位置是否可接受；
- 尾根与尾巴三维走向是否应在后续目标姿势中重新定向；
- 四个质量块是否保留了小橘的幼猫头身比和圆润体积；
- 眼眶中心、眼球中心、安全椭圆和遮眼目标区是否符合小橘脸部比例；
- 肩胛胸侧、前肢、胸腹、髋腿、颈胸毛和尾根软组织包络是否覆盖了后续拆层/网格需要；
- 肌肉力矩参考锚点的 pivot / pull 方向是否足够表达后续软组织控制需求；
- 耳根、耳尖、耳内面锚点和耳根到耳尖的牵拉方向是否符合小橘耳朵比例；
- 耳朵参考链 `skull_center -> ear_base -> ear_tip / ear_inner` 是否足够表达头部带动耳朵的关系；
- 辅助关节节点是否覆盖脸颊毛、胡须根、耳中、胸毛、腋下、爪趾缘和尾根套口等后续拆层/三角剖分需要；
- 辅助参考线是否足够表达未来网格种子之间的语义连接，但又没有误导成正式 ArtMesh；
- 是否同意把大字型/展开姿势参考图作为 X1 通过后的后续 Gate 产物，而不是当前 X1 产物。

## Gate 结论

自动检查只证明合同内部一致，不等于 X1 通过。当前状态保持 `candidate-for-user-review`，X2 明确为未授权。
