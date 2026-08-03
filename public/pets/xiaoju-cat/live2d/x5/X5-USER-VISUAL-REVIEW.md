# X5 三角剖分、力矩锚点与弹性关系视觉审核

> **历史方法与失败证据，不是当前审核入口。** 网格审计、单父节点级联和数据合同可复用；126 个切片、63 个生成细层及其网格不得作为生产素材。当前有效门禁已回退到 X3，详见 `../PROCESS-AND-ARTIFACT-AUDIT-v1.md`。

> 状态：X5 候选已生成，等待用户视觉审核。  
> X5 只定义图层边界、ArtMesh 点密度、主控制节点、父子链接、力矩/弹性关系；还不进入 PSD、Cubism 或运行时。
> 分层子项：用户已于 2026-07-18 明确表示“分层可以了”；剩余审核集中在节点级联、三角网格、力矩与弹性关系。

## 必看预览

- `qa/x5-article-node-cascade-elastic-preview-v1.png`：当前剩余 X5 审核首要入口。蓝色箭头直接叠在实际小橘三视图上表示父变换传递；下方量化图证明静态层弹性为 0，软层弹性随距节点距离增加、阻力衰减随距离减弱。
- `x5-article-node-elastic-audit-v1.json`：按知乎文章规则建立的 `63` 个唯一 LayerNode、单父级联、根节点可达性、刚性骨段长度与逐顶点弹性/阻力自动检查。

- `qa/x5-generated-fine-production-review-composite-v1.png`：本轮实际小橘“精细分层 -> 三角剖分 -> 节点/力矩/弹性”总预览，是当前首要审核入口。
- `qa/x5-generated-fine-actual-xiaoju-mesh-node-torque-overlay-v1.png`：把骨段、局部三角带、主力矩支点、重力方向与耳尾弹性支点直接叠回现有小橘大字型三视图。
- `qa/x5-generated-fine-layer-candidates-atlas-v1.png`：基于现有小橘参考图生成并净化后的 `63` 个透明 PNG 精细分层候选。
- `qa/x5-generated-fine-layer-triangulation-atlas-v1.png`：按每层真实 Alpha 边界进行质量约束三角剖分；蓝色为网格，红色为每层唯一主支点，绿色为高弹性顶点。
- `qa/x5-triangulation-detail-head-v1.png`：头部、眼睛、耳朵和胡须分层网格放大审核图。
- `qa/x5-triangulation-detail-torso-v1.png`：颈部、胸腹、骨盆和背部分层网格放大审核图。
- `qa/x5-triangulation-detail-limbs-v1.png`：前肢、后肢和足部分层网格放大审核图。
- `qa/x5-triangulation-detail-tail-v1.png`：尾根、尾中和尾尖分层网格放大审核图。
- `x5-generated-fine-layer-candidates-contract-v1.json`：精细分层、父节点、pivot、隐藏重叠、网格密度区和弹性用途合同。
- `x5-generated-fine-mesh-contract-v1.json`：`63` 层的三角网格、主节点、顶点弹性权重和弹簧-阻尼关系合同。
- `x5-mesh-alpha-coverage-audit-v1.json`：三角形对每层真实 Alpha 的覆盖率与外溢精度双向硬检查；动画导向降密后仍为 `63/63` 层通过，1 像素边界容差最低覆盖 `95.10%`、最低 Alpha 精度 `99.00%`。
- `qa/x5-mesh-deformation-smoothness-preview-v1.png`：代表性眼睑、耳尖、前臂和尾尖在父节点 `+15°` 与弹性滞后下的静止/变形网格叠图。
- `x5-mesh-deformation-smoothness-audit-v1.json`：对全部 `63` 层进行 `±15°` 小角度拓扑应力测试；当前无三角翻面，面积比为 `0.9678–1.0323`，边长比为 `0.9683–1.0316`。

当前网格密度策略：先判断动作主体与变形角色，再决定密度，不再按纹理或轮廓复杂度铺点。父节点继承型头壳、躯干和骨段使用极粗网格；耳朵、眼睛和眼睑使用少量轮廓点加中心/内部点；只有毛发轮廓、关节和尾部曲线保留中等密度。当前共 `1417` 个顶点、`1798` 个三角形；相对完整覆盖 v3 网格，顶点减少 `82.18%`，三角形减少 `86.43%`。

动作主体示例：`head_base_side` 的动作主体是 `Neck`，角色为父节点继承型刚性表面，仅 `16` 顶点/`18` 三角形；`ear_face_L/R` 的动作主体是 `EarRoot_L/R`，使用 `10–11` 个顶点；`ear_tip_L/R` 使用 `7` 个顶点。

当前锚点显示策略：红色只表示每层唯一主节点或实际小橘叠图中的躯干/肩/髋主力矩锚点；肘腕膝踝显示为小型蓝色关节。绿色不是额外锚点，而是连续弹性权重的代表性顶点，每层最多显示 `3` 个。

- `qa/x5-layer-anchor-only-atlas-v1.png`：全部 `63` 层的纯锚点总览，隐藏网格和弹性点。
- `qa/x5-layer-anchor-only-head-v1.png`：头部分层纯锚点放大图，每层只显示一个红点。

- `qa/x5-actual-xiaoju-spread-pose-three-view.png`：基于实际小橘权威三视图生成的大字型/摊开三视图候选，用来判断后续分层、关节露出、骨段伸缩风险和三角剖分边界。
- `qa/x5-actual-xiaoju-spread-pose-moment-elastic.png`：直接叠在大字型小橘三视图上的力矩分布、父子锚点、肌肉包络、支撑反力与 `k/c` 弹性关系。
- `qa/x5-actual-xiaoju-review-composite.png`：直接叠在实际小橘三视图上的 X5 分层、三角剖分、主/次力矩和弹性审核总览。
- `qa/x5-actual-xiaoju-layer-overlay.png`：实际小橘三视图上的语义分层和隐藏补全区域叠图。
- `qa/x5-actual-xiaoju-triangulation-moment-overlay.png`：实际小橘三视图上的三角密度、主/次力矩锚点、外力/接触/重力方向叠图。
- `qa/x5-detailed-layer-atlas.png`：按小橘三视图展开的详细分层图集，当前共有 `54` 个语义层。
- `qa/x5-triangulation-moment-preview.png`：三角剖分密度、主要/次要力矩锚点、外力/接触/重力方向。
- `qa/x5-link-elastic-preview.png`：父子节点级联和弹性链。
- `x5-layer-mesh-node-torque-contract.json`：机器可读 Layer-Mesh-Node/力矩/弹性合同。
- `x5-actual-xiaoju-spread-pose-contract.json`：大字型实际小橘三视图的候选边界说明。
- `x5-actual-xiaoju-spread-pose-moment-elastic-contract.json`：大字型实际小橘三视图上的力矩/弹性可视化候选边界说明。
- `x5-actual-xiaoju-overlay-contract.json`：实际小橘叠图候选边界说明。
- `x5-self-review.json`：自动自审结果。

## 审核问题

1. 三角高密区是否放在眼睑、眼眶、肘腕、尾根、接触阴影等真正会弯/压/遮挡的位置？
2. 主力矩锚点是否只控制核心动作，次级锚点是否只控制软组织和回弹？
3. 父子链接是否合理：局部层不能反向拖动身体，星球不能改变小橘骨段。
4. 弹性关系是否足够但不过度，不会把小橘做成整身软塌？

## Gate 决策

- 说 `X5 通过`：授权进入 X6 参数、Action Tracer 和 Cubism-ready keyform 范围。
- 指出具体问题：继续只修 X5 合同和预览，不进入 X6。
