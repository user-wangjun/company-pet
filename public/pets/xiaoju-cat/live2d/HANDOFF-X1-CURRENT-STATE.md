# 小橘 Live2D：当前状态与新对话交接

> 初始交接日期：2026-07-17  
> 状态同步日期：2026-07-19  
> 当前阶段：**X3 登录页实际可见目标彩图 v1 用户审核**；生产线稿/遮罩尚未授权。  
> 门禁状态：**X1、X2 保留有效；旧 X3-X6 的历史通过/授权因生产母版身份漂移与分层方法错误而被当前审计覆盖。X4-X7 均未授权。**

> **重要：本文件后续的大段 X3-X6 记录仅保留为失败过程与技术证据，不再代表当前生产状态。** 当前状态以 `XIAOJU-LIVE2D-IMPLEMENTATION-PRD-v2.2.md`、`PROCESS-AND-ARTIFACT-AUDIT-v1.md`、`blueprints/artifact-usability-audit-v1.json` 和 `blueprints/v2-artifact-disposition.json` 为准。

## 0. 2026-07-19 状态同步

当前权威门禁状态以 `live2d/blueprints/v2-artifact-disposition.json` 为准：

- `status`: `x3-login-target-color-master-v1-user-review`
- `currentGate`: `x3-target-color-and-line-mask-master`
- `x1ApprovedByUser`: `true`
- `x2Authorized`: `true`
- `x2ApprovedByUser`: `true`
- `x3Authorized`: `true`
- `gate3Approved`: `false`
- `x4Authorized`: `false`
- `gate4Approved`: `false`
- `x5Authorized`: `false`
- `gate5Approved`: `false`
- `x6Authorized`: `false`
- `gate6Approved`: `false`
- `x7Authorized`: `false`

当前 X3 采用成对目标图：`live2d/x3/qa/x3-login-target-color-master-v1.png` 是登录页最终可见 Rest 画面，`live2d/x3/qa/x3-login-full-body-master-v1.png` 是移除星球后的完整连续身体母版。前者锁定构图和可见效果，后者提供被星球遮挡的胸腹、骨盆、后腿及完整前肢链，二者必须共同通过身份、姿势与配准审核。用户尚未通过该图对，因此不得开始生产线稿、遮罩、分层或网格。

本文件最初记录的是 X1 候选状态。后续用户在同一任务中逐 Gate 授权到 X5，并以“可以了，继续下一步吧”明确通过整个 X5。用户随后指出 X6 参数前应先把分层拼成完整小橘，因此 X6 先用 113 个可见源图透明层按绘制顺序重建静止三视图，再把 63 个精细独立素材按三视图登记为 111 个隐藏补全放置。动作编排不直接操纵这些细层，而使用 16 个粗粒度动作组：头、嘴、左右耳、左右眼、身体、左右上臂、左右小臂连前爪、左右大腿、左右小腿连后爪、尾巴。肩肘髋膝仅作为内部转轴。Rest 可见身份继续来自坐标对齐的源图层；精细素材只位于对应关节/区域后方，不再强行替换整只猫的可见表面。该生产层栈仍是待用户审核候选；不得进入 Cubism、X7 Physics 或真实运行时。

用户进一步指出 v3 粗动作组切口不整洁且缺少遮挡/重叠区，移动后可能断骨。X6 v4 因而把每个动作组拆成“可见身份 PNG + 随子组移动但绘制在父层后方的隐藏套筒 PNG”，并对躯干孤立遮罩碎片做整组连续性清理。侧视中完全被躯干遮挡的远侧上臂/大腿不虚构可见层，而使用隐藏近端桥接接入身体。当前 39 个父子关节均有非零重叠，10 px 向外拉开审计 `39/39` 仍保持父子双端接触；这仍只是 X6 候选，不授权 X7 或 Cubism。

用户随后反馈 v4 技术图难懂且视觉不美。v5 不再把所有切线和青色套筒叠到猫身上，也不再单独放大楔形隐藏接入端；审核图改为“无标记完整三视图 -> 五类完整外形动作组 -> 一条前肢三帧移动”。这只修正用户审核表达，v4 分层和拉开审计仍是底层依据。

用户继续指出正面前肢顶部没有真正压入身体。复核确认旧肩套筒只有父层内部覆盖，曾先后出现 V 形窄带和过宽环状试验，均被否决。当前肩部改为局部实心椭圆肩帽，随上臂移动并同时压在 Body 与 Head/颈胸毛后方；正面右上臂抬起 `(-12,-6) px` 后仍有 `2835 px` 父遮挡接触和 `2754 px` 上臂近端接触。`qa/x6-shoulder-overlap-closeup-v6.png` 是当前肩部首要审核图。

用户随后手绘了更清晰的正面分层边界：头、连续身体为主层；耳、眼、中央嘴部、大腿和尾巴为独立细节/动作层；上臂压在身体下，小臂连前爪压在上臂下；小腿连后爪压在大腿下。X6 v7 将其整理为 10 个语义分组的干净正面边界候选；该边界现已获用户许可用于正面实际分层，但这项许可不自动扩展到侧面/背面或 X7。

用户以“可以，你试试分层先”通过 v7 正面边界并授权先制作正面实际分层。X6 v8 已导出 16 个可独立移动的透明 PNG；隐藏肩、肘、髋、膝、颈和尾根接入区并入对应子层，由父层按绘制顺序遮住。实际层静止重组 `extraAlphaPixels=0`、`missingAlphaPixels=15`、`changedRgbaPixels=34`；同一接入几何的正面 15 个关节在 10 px 拉开审计中 `15/15` 通过，最小父层接触 `351 px`、最小子层边界接触 `160 px`。当前只等待用户审核 v8 正面实际层；侧面、背面和 X7 仍未授权。

用户随后准确指出 v8 仍有“从整图裁剪后未补全”的问题。重新对照知乎文章的独立 PNG 图层、逐层网格与画家顺序原则，并按 `rig-live2d-pet/material-separation.md` 的完整底图要求执行大幅拉开审计后，确认静止重组指标不能证明隐藏结构完整：它只是被绘制顺序遮住了。v9 将 v8 降级为切片失败证据，列出 11 个必须回炉的结构层：头底、身体底、左右上下前肢、左右上下后肢和尾巴。局部肩帽/关节套筒不能替代完整颈肩、髋、关节内藏长度和连续毛流。任何新网格、侧背传播和 X7 都继续锁定。

用户进一步明确“不是切片，而是分成完整图层，有重叠区域”。X6 v10 因而不再复用 v8 合并套筒：从可见身份层重新建立 16 张独立 PNG，并为头底、身体底、四个前肢段、四个后肢段和尾巴共 11 个结构层补入真实隐藏像素。后到前绘制顺序改为“下段 -> 上段 -> 身体 -> 耳 -> 头 -> 眼/嘴”，使身体覆盖肢根、上段覆盖下段接入、头覆盖颈部。15 个父子关系全部具有真实像素重叠，最小重叠 `1200 px`；静止重组 `extraAlphaPixels=0`、`missingAlphaPixels=0`、可见 RGB 平均绝对误差 `1.1993`。v10 仍只是正面视觉候选，隐藏毛流质量和拉开外观必须由用户审核；侧面、背面、网格和 X7 未授权。

用户放大指出 v10 头底出现极其诡异的放射状/万花筒纹理。该失败来自最近像素/径向扩散，不是生物毛流；因此 v10 的完整形状和 15 个重叠掩码保留，但其隐藏纹理生成方式整体否决，不能传播到身体和四肢。v11 只校准头底：使用独立自然橘猫毛流纹理源替换眼、嘴和耳根遮挡下的 `22468` 个隐藏像素，并在眼窝边缘做 6 px 羽化；正常可见外轮廓和额纹保留。静止重组 `extraAlphaPixels=0`、`missingAlphaPixels=0`、可见 RGB 平均绝对误差 `1.6371`。v12 只把同一份 v11 材质重新排成放大复审图，增加眼、嘴、耳全部移开的检查，不修改纹理本体。用户随后指出仍看到放射状旧图，复核确认是 v10 与带反例对比的 v11 仍被错误登记为视觉候选；v13 将它们排除出当前审核入口，只展示同一份 v11 修正版。用户继续指出 v13 静止眼缘仍有明显分界，并要求查看所有分层；随后进一步质疑眼睛层为什么包含周边脸毛。复核确认两个原因：v11 的 6 px 羽化向外污染了可见脸毛，且早期左右眼层各自携带一个约 `71×85` 的圆形脸部切片。v14 将左右眼收紧为仅眼球和黑色眼缘，周边脸毛归还头底；头底只在眼球/嘴部真实遮挡内部使用自然毛流，并对半透明边缘反算底色。正面全部 16 张透明 PNG 同步导出并制成图集。静止重组 `extraAlphaPixels=0`、`missingAlphaPixels=0`、可见 RGB 平均绝对误差降为 `0.0021`。图集中 10 个仍沿用 v10 失败隐藏纹理的结构层明确标橙，不能视作通过；不得传播侧背或进入 X7。

用户随后明确纠正方法：“不是让你去切图片，而且按照大字型和三视图来用技能生成相关分层”，并要求移动关节必须保留重叠，避免断骨或局部凸块。v15 因而停止把 v14 可见像素裁层作为当前候选，改用 `rig-live2d-pet` 与内置 imagegen，以小橘坐姿三视图、大字型三视图和 X5 毛发材质为身份参考，分别生成正、侧、背三套完整独立材质。每视图 16 层，共 48 张透明 PNG；肩根、肘、髋根、膝和尾根采用圆钝隐藏延伸，目标父子重叠为关节长度的 `20%-30%`，眼层只包含眼球与眼缘。导出器只分离生成板上已经独立的透明主体，不从整猫切取解剖区域。该批次仍等待用户视觉审核，`gate6Approved=false`、`x7Authorized=false`。

用户随后说“可以，你先拼凑一下出个预览给我看看”，只授权在 X6 内用 v15 图层制作拼装预览。v16 直接读取 48 张透明 PNG，记录每层缩放、旋转、坐标与绘制顺序，并生成正、侧、背静止拼装及小幅关节拉开对照。首轮自审发现侧视头底自带一只耳、背视头底自带双耳，独立耳层装回后会重复；现已用 imagegen 重新生成无耳但隐藏颅骨完整的侧、背头底，并纳入 v15 确定性导出器。侧视远侧膝的零重叠也已校正。最终 30 个颈、肩、肘、髋、膝和尾根关系在静止与轻拉开状态均保持非零 alpha 重叠，最小值均为 `524 px`。该结果仍是 X6 视觉候选，不代表用户通过，也不授权 X7。

## 1. 新对话必须遵循的唯一依据

1. 通用工作流：`C:\Users\13640\.codex\skills\rig-live2d-pet\SKILL.md`
2. 小橘专用实施 PRD：`live2d/XIAOJU-LIVE2D-IMPLEMENTATION-PRD-v2.2.md`
3. 当前门禁状态：`live2d/blueprints/v2-artifact-disposition.json`
4. 资产审计：`live2d/PROCESS-AND-ARTIFACT-AUDIT-v1.md` 与 `live2d/blueprints/artifact-usability-audit-v1.json`
5. 本交接文档与 X1、X2 报告和合同。

用户已经明确要求：无论上下文如何压缩，在没有新的明确许可前，都必须继续按照上述 PRD 执行，不得越级或另起方案。

## 2. 当前已经完成的 X1 产物

- `live2d/x1/build_x1_canonical_body.py`：确定性生成脚本。
- `live2d/x1/x1-canonical-body-contract.json`：统一近似 3D 骨架、骨段长度、质量块、三视图观察点、可见性和门禁合同。
- `live2d/x1/x1-canonical-body-report.md`：解释边界、统计、自检和人工审核点。
- `live2d/x1/qa/x1-three-view-landmark-overlay.png`：三视图解剖点、链条与质量块叠加图。
- `live2d/x1/qa/x1-three-view-review-sheet.png`：原图与标注图对照。
- `live2d/x1/qa/x1-canonical-skeleton-projections.png`：同一套近似 3D 骨架的正、侧、顶投影。
- `live2d/x2/X2-USER-VISUAL-REVIEW.md`：当前 X2 用户视觉审核入口，集中列出必看预览、自动核验摘要、审核问题和 Gate 决策词。
- `live2d/x2/x2-user-review-manifest.json`：机器可读 X2 审核清单，列出当前必看证据和允许的用户 Gate 决策。
- `live2d/x2/qa/x2-length-triangle-diagnostic.png`：X2 骨段长度与局部三角约束诊断图，只用于判断块面动作是否靠骨段伸缩作弊。
- `live2d/x2/x2-length-triangle-diagnostic.json`：上述诊断图的机器可读摘要；其中骨段边应保持近零漂移，折叠三角斜边允许随关节运动变化。
- `live2d/x3/x3-spread-pose-master-contract.json`：X3 完整连续大字型/展开三视图母版合同，定义母版必须包含和禁止包含的内容。
- `live2d/x3/X3-USER-VISUAL-REVIEW.md`：X3 用户视觉审核入口，说明为什么当前仍不能直接分层，以及母版审核问题。
- `live2d/x3/qa/x3-spread-pose-master-blockout.png`：当前 X3 完整连续大字型/展开三视图母版结构候选图，等待用户视觉审核。
- `live2d/x3/qa/x3-user-review-composite.png`：X3 用户视觉审核总览图，把母版候选和 6 项审核标准放在一起。
- `live2d/x3/x3-spread-pose-master-blockout.json`：上述候选图的机器可读边界说明，明确它不是正式分层或 ArtMesh。
- `live2d/x3/x3-user-review-manifest.json`：机器可读 X3 审核清单，列出当前必看证据和允许的用户 Gate 决策。
- `live2d/x4/build_x4_layer_separation_preview.py`：确定性生成 X4 分层预览、隐藏补全检查、合同和审核说明。
- `live2d/x4/qa/x4-layer-separation-overview.png`：X4 语义分层总览与绘制顺序。
- `live2d/x4/qa/x4-expanded-hidden-fill-check.png`：X4 头、四肢、尾巴移开后的隐藏补全/安全重叠检查。
- `live2d/x4/x4-layer-separation-contract.json`：X4 分层合同，列出层、父区域、隐藏补全、绘制顺序和禁止项。
- `live2d/x4/X4-USER-VISUAL-REVIEW.md`：当前 X4 用户视觉审核入口。
- `live2d/x5/build_x5_mesh_node_torque_preview.py`：确定性生成 X5 详细分层、三角剖分/力矩、父子链接/弹性预览和合同。
- `live2d/x5/build_x5_actual_xiaoju_overlays.py`：把 X5 分层、三角剖分与力矩锚点直接叠到实际小橘权威三视图上，避免只看抽象占位猫。
- `live2d/x5/build_x5_spread_pose_moment_elastic_preview.py`：把骨段、主/次锚点、`r/F` 箭头、`tau` 弧线、父子链接和轻量 `k/c` 弹性关系叠到实际小橘大字型三视图候选上；已按用户反馈移除大面积肌肉色块，并修正为 clean-v12：后肢改为可见身体内短控制链，背/侧尾巴弹性链贴合实际尾巴方向，背视胡须锚点隐藏，耳朵只保留短弹性提示。
- `live2d/x5/build_x5_actual_layer_split_candidates.py`：按知乎文章/Skill 固化的“独立 PNG 图层 -> 图层边界 -> 三角剖分 -> 节点/弹性”顺序，从实际小橘大字型三视图候选生成 126 个透明 PNG 分层候选；其中 9 个不可见或白底区域明确标为隐藏补全占位，不冒充已绘制完成的真实像素层。
- `live2d/x5/actual-layer-candidates/`：实际小橘三视图透明 PNG 分层候选目录，命名格式为 `<view>_<layer-id>.png`。
- `live2d/x5/qa/x5-actual-xiaoju-transparent-layer-atlas.png`：126 个透明 PNG 分层候选总览。
- `live2d/x5/qa/x5-actual-xiaoju-layer-boundary-preview.png`：三视图分层边界预览。
- `live2d/x5/qa/x5-actual-xiaoju-layer-reconstruction-coverage.png`：把原图、透明层覆盖重组和红色未覆盖像素并列。当前覆盖率为正面 `92.80%`、侧面 `94.42%`、背面 `91.71%`，证明几何遮罩分层仍需要毛发边缘和关节隐藏补全精修，不得写成 X5 已通过。
- `live2d/x5/x5-actual-xiaoju-layer-split-contract.json`：实际小橘透明分层候选合同，记录每层父节点、绘制顺序、pivot、隐藏补全、网格密度区、弹性关系和是否为隐藏补全占位。
- `live2d/x5/generated-layer-materials/x5-xiaoju-fine-layer-source-atlas-alpha-v1.png`：使用内置 `imagegen` 严格参考现有小橘大字型三视图生成的精细分层素材母表，经本地色键去背景后保留 Alpha。
- `live2d/x5/generated-fine-layer-candidates-v1/`：从精细素材母表净化并拆出的 `63` 个透明语义分层 PNG；普通层只保留主连通部件，避免夹带邻层碎片。
- `live2d/x5/qa/x5-generated-fine-layer-candidates-atlas-v1.png`：本轮 `63` 个精细透明分层总览。
- `live2d/x5/x5-generated-fine-layer-candidates-contract-v1.json`：每层的视图用途、父节点、主控制器、pivot、隐藏重叠、网格密度和弹性用途合同。
- `live2d/x5/generated-fine-mesh-candidates-v1/`：依据每层动作主体和变形角色进行文章式粗网格；共 `1417` 个顶点、`1798` 个三角形。相对完整覆盖 v3 网格，顶点减少 `82.18%`、三角形减少 `86.43%`。截图中曾误判为耳朵的 `head_base_side` 现明确为 `Neck` 继承型刚性头壳，仅 `16` 顶点/`18` 三角形；真正耳面层绑定 `EarRoot_L/R`，使用 `10–11` 个顶点，耳尖层使用 `7` 个顶点。
- `live2d/x5/x5-generated-fine-mesh-contract-v1.json`：记录 `63` 层的唯一主控制节点、支点、顶点弹性权重和 `tau = k(target-angle) - c*angularVelocity` 关系；当前最小三角角度 `8.842°`，未检出低于 `5°` 的 sliver triangle。
- `live2d/x5/x5-mesh-alpha-coverage-audit-v1.json`：逐层栅格化三角形并与真实 Alpha 双向比较；动作主体驱动的粗网格下 `63/63` 层仍同时通过覆盖率与外溢精度 `95%` 门槛。1 像素边界容差下覆盖率最低 `96.34%`、平均 `98.89%`，Alpha 精度最低 `98.24%`、平均 `99.68%`。
- `live2d/x5/x5-mesh-deformation-smoothness-audit-v1.json` 与 `qa/x5-mesh-deformation-smoothness-preview-v1.png`：对降密网格施加 `±15°` 父节点旋转和逐顶点弹性滞后；`63/63` 层通过，翻面数为 `0`，面积比 `0.9678–1.0323`，边长比 `0.9683–1.0316`。这是 X5 拓扑应力测试，不是 X6 动作参数或 Action Tracer。
- `live2d/x5/qa/x5-generated-fine-layer-triangulation-atlas-v1.png`：精细分层的蓝色三角网格、红色唯一主支点和绿色高弹性顶点预览。
- `live2d/x5/qa/x5-triangulation-detail-head-v1.png`、`x5-triangulation-detail-torso-v1.png`、`x5-triangulation-detail-limbs-v1.png`、`x5-triangulation-detail-tail-v1.png`：将同一批 `63` 层三角网格按头部、躯干、四肢和尾巴分区放大，作为网格边界与密度的首要细节审核图。
- 当前锚点显示规则：每层仍严格只有一个红色主节点，但绿色弹性顶点在预览中每层最多显示 `3` 个代表点；其余弹性保留为连续权重，不冒充独立锚点。实际小橘叠图只用红色突出躯干、肩、髋主力矩锚点，肘腕膝踝降为小型蓝色关节节点。
- `live2d/x5/qa/x5-layer-anchor-only-atlas-v1.png` 与 `x5-layer-anchor-only-head-v1.png`：隐藏全部蓝色网格顶点和绿色弹性权重点，只显示每层唯一红色动作锚点，用于避免把三角网格交点误读为大量动作锚点。
- `live2d/x5/qa/x5-generated-fine-actual-xiaoju-mesh-node-torque-overlay-v1.png`：把骨段、局部三角带、主力矩支点、重力方向和耳尾弹性支点叠回实际小橘三视图。
- `live2d/x5/qa/x5-generated-fine-production-review-composite-v1.png`：当前 X5 精细分层 -> 三角剖分 -> 节点/力矩/弹性的首要用户视觉审核入口。
- `live2d/x5/build_x5_article_node_elastic_audit.py`：按知乎文章规则生成每层唯一节点、单父级联、根节点可达性、刚性长度与距离弹性/阻力衰减检查。
- `live2d/x5/x5-article-node-elastic-audit-v1.json`：`63` 层唯一 LayerNode 与文章规则对齐的机器审计；全部节点沿单父链回到 `BodyRoot`，静态层弹性全零，软层弹性随距离增加且阻力衰减随距离减弱。
- `live2d/x5/qa/x5-article-node-cascade-elastic-preview-v1.png`：当前分层获用户认可后的剩余 X5 首要审核入口，直接在实际小橘三视图上显示父变换传递和软组织弹性链。
- `live2d/x5/X5-GENERATED-FINE-LAYER-PROMPT-v1.md`：本轮内置 `imagegen` 的完整 Prompt 与输出边界。
- `live2d/x5/qa/x5-actual-xiaoju-spread-pose-three-view.png`：基于实际小橘权威三视图生成的大字型/摊开三视图候选，只供 X5 用户视觉审核和后续分层/剖分判断。
- `live2d/x5/qa/x5-actual-xiaoju-spread-pose-moment-elastic.png`：实际小橘大字型三视图上的 X5 力矩分布与弹性关系预览。
- `live2d/x5/qa/x5-actual-xiaoju-review-composite.png`：实际小橘源图上的 X5 分层、三角剖分、主/次力矩和弹性审核总览。
- `live2d/x5/qa/x5-detailed-layer-atlas.png`：X5 按三视图展开的 54 个详细语义层图集。
- `live2d/x5/qa/x5-triangulation-moment-preview.png`：X5 三角剖分密度、主要/次要力矩锚点和力方向预览。
- `live2d/x5/qa/x5-link-elastic-preview.png`：X5 父子节点级联与弹性链预览。
- `live2d/x5/x5-layer-mesh-node-torque-contract.json`：X5 Layer-Mesh-Node、力矩锚点、弹性关系机器合同。
- `live2d/x5/x5-actual-xiaoju-spread-pose-contract.json`：实际小橘大字型三视图候选边界合同。
- `live2d/x5/x5-actual-xiaoju-spread-pose-moment-elastic-contract.json`：实际小橘大字型力矩/弹性预览候选边界合同。
- `live2d/x5/x5-actual-xiaoju-overlay-contract.json`：实际小橘源图叠图候选边界合同。
- `live2d/x5/x5-self-review.json`：X5 自审结果。
- `live2d/x5/X5-USER-VISUAL-REVIEW.md`：当前 X5 用户视觉审核入口。
- `live2d/x6/build_x6_coarse_motion_bundles.py`：把 113 个可见层和 111 个精细补全放置归入 16 个粗粒度动作组；细层保留为组内材质/网格，不再各自作为动作主体。
- `live2d/x6/qa/x6-coarse-motion-bundle-review-v3.png`：当前 X6 粗粒度动作拆分首要预览。
- `live2d/x6/x6-coarse-motion-bundle-contract-v3.json`：粗动作组父子关系、主控制器、可见层唯一归属和精细补全归属合同。
- `live2d/x6/build_x6_joint_safe_motion_bundles.py`：生成 v4 整洁可见切片、独立隐藏关节套筒和拉开视觉检查。
- `live2d/x6/audit_x6_joint_safe_motion_bundles.py`：对全部父子关节执行 10 px 向外拉开后的双端接触审计。
- `live2d/x6/qa/x6-joint-safe-motion-bundle-review-v4.png`：当前 X6 动作组切口、隐藏覆盖和拉开检查首要预览；取代 v3 作为审核入口。
- `live2d/x6/x6-joint-safe-motion-bundle-contract-v4.json` 与 `x6-joint-safe-motion-bundle-audit-v4.json`：42 个视图动作组导出、39 个关节套筒及 39/39 拉开连续性结果。
- `live2d/x6/build_x6_clear_layer_review.py`：生成无技术覆盖的中文 X6 分层解释图。
- `live2d/x6/qa/x6-clear-layer-and-overlap-review-v5.png`：当前面向用户的首要审核入口；只展示完整小橘、自然动作组和单前肢移动结果。
- `live2d/x6/x6-clear-layer-review-contract-v5.json`：记录 v5 仅简化审核表达、不改变 v4 分层合同和门禁的边界。
- `live2d/x6/qa/x6-shoulder-overlap-closeup-v6.png`：前肢肩部静止、整肢抬起和小臂展开的无技术色块放大图；用于区分上沿肩面连接与下方正常腋窝轮廓。
- `live2d/x6/build_x6_user_defined_segmentation_preview.py`：把用户手绘边界整理为平滑的正面语义分层审核图，不生成侧面/背面正式切片。
- `live2d/x6/qa/x6-user-defined-segmentation-preview-v7.png`：当前正面首要审核图；显示头/身体主层、耳眼嘴、大腿、尾巴及上下肢段的边界和遮挡含义。
- `live2d/x6/x6-user-defined-segmentation-contract-v7.json`：10 个正面语义分组与父子遮挡顺序；明确正面未批准、侧背未授权、X7 未授权。
- `live2d/x6/build_x6_front_actual_segmentation.py`：依据已通过的 v7 正面边界，将可见表面与子层所属隐藏接入区合并为实际透明动作层并执行重组审计。
- `live2d/x6/front-user-segmentation-v8/`：16 个正面实际透明动作层及 `front-reconstruction.png`。
- `live2d/x6/x6-front-actual-segmentation-contract-v8.json`：实际层路径、画布坐标、父层、后到前绘制顺序、静止重组与正面关节拉开证据。
- `live2d/x6/qa/x6-front-actual-segmentation-review-v8.png`：已被 v9 否决的切片候选；仅保留为静止重组不足以证明隐藏完整性的反例。
- `live2d/x6/audit_x6_front_hidden_completion.py`：把头、四肢和尾巴大幅拉开，审计独立 PNG 是否拥有完整被遮挡结构。
- `live2d/x6/x6-front-hidden-completion-audit-v9.json`：记录 v8 隐藏区不合格、11 个必须回炉的结构层和严格 Gate 边界。
- `live2d/x6/qa/x6-front-hidden-completion-audit-v9.png`：v8 失败证据；直接对比静止遮挡与拉开后缺失，并规定 v10 的返工标准。
- `live2d/x6/build_x6_front_complete_layers.py`：从可见身份图重新构造完整正面层，为隐藏区生成连续纹理并验证真实父子像素重叠。
- `live2d/x6/front-complete-overlap-layers-v10/`：16 张正面完整独立 PNG 与静止重组图，不包含 v8 的浮动套筒层。
- `live2d/x6/x6-front-complete-overlap-contract-v10.json`：完整层坐标、绘制顺序、11 个结构层隐藏补全量、15 个重叠关系和静止重组审计。
- `live2d/x6/qa/x6-front-complete-overlap-review-v10.png`：已部分否决；仅保留完整形状与重叠关系证据，其中的自动扩散隐藏纹理不可再用。
- `live2d/x6/hidden-texture-guides-v11/head-base-texture-source.png` 与 `head-base-texture-alpha.png`：v11 头底自然毛流纹理源及去背景版本，只用于隐藏区。
- `live2d/x6/build_x6_head_hidden_texture_candidate.py`：保留头部完整掩码，用自然毛流源替换隐藏像素，并在真实可见毛发边缘做窄范围羽化。
- `live2d/x6/front-head-hidden-texture-v11/`：修正后的完整头底和装配重组图。
- `live2d/x6/x6-head-hidden-texture-contract-v11.json`：头底纹理来源、替换量、融合范围、静止重组审计与严格 Gate 状态。
- `live2d/x6/qa/x6-head-hidden-texture-review-v11.png`：历史对照图；保留 v10 放射纹反例与 v11 修正结果。
- `live2d/x6/build_x6_head_hidden_texture_review_v12.py`：只重排 v11 材质的放大复审图，不生成或修改任何新纹理；现已被 v13 审核入口取代。
- `live2d/x6/x6-head-hidden-texture-review-contract-v12.json`：记录 v12 只改审核表达且继承 v11 关闭 Gate 的合同；保留为历史版本。
- `live2d/x6/qa/x6-head-hidden-texture-review-v12.png`：已被 v13 取代的历史复审图。
- `live2d/x6/build_x6_head_hidden_texture_review_v13.py`：生成只含当前自然毛流修正版的审核图，明确排除 v10 放射状旧图和 v11 反例对照图。
- `live2d/x6/x6-head-hidden-texture-review-contract-v13.json`：记录 v13 审核入口、被排除的失败对照和继承自 v11 的关闭 Gate。
- `live2d/x6/qa/x6-head-hidden-texture-review-v13.png`：已被 v14 取代；其眼周可见毛发存在错误外羽化。
- `live2d/x6/build_x6_front_all_layers_v14.py`：修正眼周可见毛发被错误羽化的问题，导出正面全部 16 层、静止重组、眼周审核图和全层图集。
- `live2d/x6/front-all-layers-v14/`：正面 16 张独立透明 PNG 与静止重组；头底已更新，其他结构层是否可用以合同状态为准。
- `live2d/x6/x6-front-all-layer-contract-v14.json`：记录全层导出、眼周修正方法、静止重组审计、仍无效的隐藏纹理和关闭 Gate。
- `live2d/x6/qa/x6-front-eye-seam-review-v14.png` 与 `x6-front-all-layer-atlas-v14.png`：从整猫可见像素裁层的方法已被用户否决，只保留为历史失败证据。
- `live2d/x6/generated-complete-layer-materials-v15/`：由技能和 imagegen 根据小橘坐姿三视图、大字型三视图生成的正、侧、背完整材质板及透明版本。
- `live2d/x6/build_x6_generated_complete_layers_v15.py`：从生成板中按透明连通主体导出 48 个完整独立 PNG，不从整猫切取解剖区域。
- `live2d/x6/generated-complete-layer-candidates-v15/`：正、侧、背各 16 张透明独立材质，保留肩、肘、髋、膝和尾根隐藏延伸。
- `live2d/x6/x6-generated-complete-layer-contract-v15.json`：记录图层来源、48 层清单、重叠规则、拒绝条件和关闭 Gate。
- `live2d/x6/qa/x6-generated-complete-three-view-layer-review-v15.png`：当前三视图 48 层首要用户审核图。
- `live2d/x6/build_x6_generated_layer_assembly_v16.py`：只读取 48 张透明层进行三视图确定性拼装和小幅关节拉开，不使用整猫兜底。
- `live2d/x6/generated-layer-assembly-v16/`：正、侧、背静止拼装与关节轻拉开透明 PNG。
- `live2d/x6/x6-generated-layer-assembly-contract-v16.json`：记录摆放、绘制顺序、拉开偏移与 30 个父子重叠审计。
- `live2d/x6/qa/x6-generated-layer-assembly-review-v16.png`：当前首要拼装审核图。

权威源图仍为 `three-view-preview.png`。它是 1774×887 的 RGB 三视图合成图，视角比例和地面线基本一致，但不是相机标定后的严格正交工程图。毛发与坐姿遮挡肩胛、髋、远侧四肢及部分尾根，因此推断点必须继续保留风险标记。

## 3. 核验结果

X1 历史核验：

- X1 合同状态：`candidate-for-user-review`
- 三视图归一化垂直对齐最大 spread：`0.0111`
- 审核阈值：`0.0600`
- 质量比例合计：`1.00`
- 自动检查：7 项全部通过，包括同名点词汇一致、左右对称、质量守恒、侧视前肢折叠方向和统一骨架前肢分支。

X2 当前核验：

- X2 合同状态：`approved`
- 采样数量：`41`
- 最大骨段长度漂移：`0.00000000`
- 峰值控制力矩需求：`0.8698`
- 峰值物理力矩需求：`1.0000`
- COM 全采样位于支撑范围：`true`
- Cover 附近双爪接触眼部目标区：`true`

自动检查只证明合同内部一致，不能代替用户的视觉批准。

## 4. 已做的关键生物学修正

早期侧视前肢曾把肘放在肩的前方。现已按猫科前肢的连续链修正为：

`肩胛 -> 肩（较前） -> 肘（向后/尾侧） -> 腕与爪（再回到前方）`

统一 3D 骨架也采用同一弯曲分支，不再用不同视图各画一套骨架。X1 只冻结拓扑、左右身份、骨段长度和质量块；关节数值范围、接触、重心、支撑反力与力矩仍属于 X2，不能提前伪造。

研究依据：

- https://pmc.ncbi.nlm.nih.gov/articles/PMC11737544/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC2043500/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC3137431/

## 5. 新对话的固定启动顺序

1. 完整读取通用 `rig-live2d-pet` Skill，以及其中的 `gate-workflow.md` 和 `biomechanical-preflight.md`。
2. 完整读取小橘 PRD v2.1、本交接文档、X1 报告、X1 JSON 合同、X2 报告、X2 JSON 合同、`x2/X2-USER-VISUAL-REVIEW.md`、`x2/x2-user-review-manifest.json`、`x2/x2-length-triangle-diagnostic.json`、`x3/x3-spread-pose-master-contract.json`、`x3/X3-USER-VISUAL-REVIEW.md`、`x3/x3-user-review-manifest.json` 与门禁状态 JSON。
3. 按门禁 JSON 判断当前停点。若为 `x6-head-hidden-texture-review-candidate`，只能展示或修正 v11 头底隐藏毛流；用户确认该方法前不得批量处理其余结构层，更不得制作网格、映射侧面/背面或进入 X7。
4. 向用户展示并共同审核 `x6/X6-USER-VISUAL-REVIEW.md` 中的分层重组、九点目光、五阶段眨眼、41 点遮眼往返和实际登录动作接触表。
5. 若用户否决，只修改 X6 合同与预览，不进入 X7。
6. 只有用户明确说出“X6 通过”或同等明确批准后，才可更新门禁并进入 X7。

## 6. X6 批准前严格禁止

- PSD 导入或 Photoshop 操作；
- Cubism 建模、网格、Deformer、Physics 或运行时替换；
- X7 Physics、弹性链和微动作曲线定稿；
- 用整图切换、独立前肢 PNG、CSS/DOM 关节动画掩盖身体问题。

## 7. 可复现命令

在项目根目录执行：

```powershell
python public\pets\xiaoju-cat\live2d\x1\build_x1_canonical_body.py
python public\pets\xiaoju-cat\live2d\x2\build_x2_pose_solve.py
```

预期输出状态均为 `candidate-for-user-review`，并重新生成对应合同、报告及 QA 图。若新对话遇到只读沙箱，应使用用户已经授予的本任务完整文件权限，但仍不得扩大到 PRD 门禁之外的工作。

## 8. 当前结论

X1、X2 的解剖、运动学、接触与力矩证据继续有效。X3-X6 的历史产物只保留为结构参考、QA 方法或失败证据，不再构成生产 Gate 的通过依据。当前必须先在 X3 获得一份与 `three-view-preview.png` 身份、比例、毛色和三视一致性相符的大字型三视图目标彩图；目标图通过后，再在同一画布建立生产线稿、隐藏重叠和全画布遮罩，并以平涂层无误重组。两次审核都通过前，不得生成正式材质分层、三角网格、节点权重、参数、Physics、PSD/Cubism 或运行时产物。
