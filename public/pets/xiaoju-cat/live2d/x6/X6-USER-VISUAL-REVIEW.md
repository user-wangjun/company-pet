# 小橘 X6 用户视觉审核

> **历史失败证据，不是当前审核入口。** v15/v16 的生成分层与拼装因小橘身份、比例、部件语义和组装一致性不合格，已被 `../PROCESS-AND-ARTIFACT-AUDIT-v1.md` 降级。当前有效门禁已回退到 X3；不得由本文件继续 X6 或授权 X7。

> 当前 X6 已形成基于小橘三视图与大字型三视图生成的 48 个完整独立材质候选，但尚未获得用户通过。这里没有进入 PSD、Cubism、Physics、X7 弹性或运行时。

## 当前首要审核：48 层真实拼装与关节轻拉开 v16

1. `qa/x6-generated-layer-assembly-review-v16.png`
   - 上排是正、侧、背静止拼装；下排只对一侧前肢、后肢和尾巴做小幅拉开，用于暴露断骨、透明缺口和局部凸块。
   - 六张预览都直接读取 `generated-complete-layer-candidates-v15/` 的 48 张透明 PNG，并按合同坐标、缩放、旋转和画家顺序合成；没有整猫图片兜底，也没有重新调用 imagegen 生成整猫。
   - 首轮拼装暴露侧视头底带耳、背视头底带双耳；已重新生成无耳完整头底，独立耳层现在只出现一次。侧视远侧膝的零重叠也已修正。
2. `x6-generated-layer-assembly-contract-v16.json`
   - 登记三个视图的全部摆放、绘制顺序、轻拉开偏移和 30 个父子关节的 alpha 重叠审计。
   - 静止与轻拉开最小重叠均为 `524 px`，`allRestNonZero=true`、`allPullNonZero=true`。
   - 当前仍需用户判断整体小橘身份、颈肩毛流交界和四肢比例；`assemblyApprovedByUser=false`、`gate6Approved=false`、`x7Authorized=false`。

## 当前首要审核：技能生成的三视图完整分层 v15

1. `qa/x6-generated-complete-three-view-layer-review-v15.png`
   - 正、侧、背各 `16` 个完整独立材质，共 `48` 层；它们由内置 imagegen 依据小橘坐姿三视图、大字型三视图和 X5 毛发材质生成，不是从整猫可见像素裁切。
   - 眼层只包含眼球与眼缘；眼睑和眼周脸毛属于完整头底。嘴鼻层、耳、尾巴及四肢均为独立完整材质。
   - 肩根、肘、髋根、膝和尾根保留圆钝隐藏延伸，目标父子重叠为关节长度的 `20%-30%`，避免平切、断骨和局部圆形凸块。
2. `qa/x6-generated-complete-front-layer-atlas-v15.png`、`qa/x6-generated-complete-side-layer-atlas-v15.png`、`qa/x6-generated-complete-back-layer-atlas-v15.png`
   - 分别放大检查每个透明层的完整外形、毛流和隐藏端。
   - 生成板的透明格子只用于导出已经独立的材质主体，不用于从整猫裁解剖区域。
3. `x6-generated-complete-layer-contract-v15.json`
   - 登记 48 个透明 PNG、像素尺寸、非透明像素数、隐藏重叠职责与拒绝条件。
   - `generatedLayerMaterialsApprovedByUser=false`、`gate6Approved=false`、`x7Authorized=false`。

## 用户已否决的方法：正面可见像素裁层 v14

1. `qa/x6-front-eye-seam-review-v14.png`
   - 早期左右眼层各自携带一个约 `71×85` 的圆形脸部切片；v14 已改为仅保留眼球与黑色眼缘，周边脸毛全部归还头底。
   - v11 的 6 px 羽化曾把生成毛流混到可见眼周；v14 改为只在眼球遮挡内部使用生成毛流，并对半透明眼缘反算底色。
   - 并列展示原始身份参考、静止装回、双眼移开和完整头底，直接检查静止眼缘与移开后的隐藏毛流。
2. `qa/x6-front-all-layer-atlas-v14.png`
   - 按后到前绘制顺序列出用户要求的正面全部 `16` 张透明 PNG。
   - 绿色为当前可审；橙色明确表示该结构层仍沿用已否决的 v10 隐藏纹理，仅供完整分层盘点，不得误写为通过。
3. `x6-front-all-layer-contract-v14.json`
   - 静止重组 `extraAlphaPixels=0`、`missingAlphaPixels=0`、可见 RGB 平均绝对误差 `0.0021`。
   - `frontAllLayerReviewAuthorizedByUser=true`，但 `headCorrectionApprovedByUser=false`、`remainingStructuralHiddenTexturesApprovedByUser=false`、`sideBackPropagationAuthorized=false`、`gate6Approved=false`、`x7Authorized=false`。

## 历史失败证据：完整形状与真实重叠 v10

1. `qa/x6-front-complete-overlap-review-v10.png`
   - 左侧由 16 张完整独立 PNG 静止重组；中间把头、上下肢和尾巴整体拉开，直接显示隐藏形体；右侧展示关键完整底层。
   - 下方按父子级分步移动，不使用 v8 的短套筒或浮动圆补片。
   - 完整形状和重叠掩码仅作几何参考；自动扩散产生的放射状隐藏毛流已被用户否决，不再属于当前视觉候选。
2. `x6-front-complete-overlap-contract-v10.json`
   - 11 个结构层均增加真实隐藏像素；15 个父子关系 `15/15` 有实际重叠，最小 `1200 px`。
   - 静止重组没有新增或缺失透明轮廓像素，可见 RGB 平均绝对误差为 `1.1993`。
   - `frontCompleteLayersApprovedByUser=false`、`sideBackPropagationAuthorized=false`、`gate6Approved=false`、`x7Authorized=false`。

## 当前首要证据：v8 隐藏补全失败

1. `qa/x6-front-hidden-completion-audit-v9.png`
   - 用户指出 v8 像从整图裁切，缺少裁切后的隐藏补全。大幅移开头、四肢和尾巴后，该问题得到确认。
   - v8 静止重组看似正确，是因为父子绘制顺序遮住缺失；它不能证明每层具有完整形体。
   - 头底、身体底、左右上下前肢、左右上下后肢和尾巴共 11 个结构层必须回炉。
2. `x6-front-hidden-completion-audit-v9.json`
   - v8 的处置是 `reject-v8-as-complete-layer-set-and-return-to-front-hidden-area-reconstruction`。
   - 新候选必须同时通过静止重组、各层单独图，以及头/四肢/尾巴大幅移开图。
   - 在此之前不得制作新网格、传播侧面/背面或进入 X7。

## 已被 v9 否决：正面切片 v8

1. `qa/x6-front-actual-segmentation-review-v8.png`
   - 左侧虽是 16 个透明 PNG 重组且没有完整源图兜底，但这项证明不足：遮挡隐藏了缺失结构。
   - 右侧按用户草图归纳为 10 类动作主体；耳、眼与四肢左右侧仍分别保留，因此实际为 16 个可移动层。
   - 下方小幅平移范围太小，未暴露不完整底图；现已被 v9 的大幅拉开审计取代。
2. `x6-front-actual-segmentation-contract-v8.json`
   - 静止重组无新增透明边界外像素；与基准仅 34 个 RGBA 像素不同。
   - 正面 15 个父子接入点沿用已审计几何，10 px 拉开 `15/15` 保持父子双端接触。
   - `frontActualLayersApprovedByUser=false`、`sideBackPropagationAuthorized=false`、`gate6Approved=false`、`x7Authorized=false`。

## 先确认用户手绘的正面分层边界

1. `qa/x6-user-defined-segmentation-preview-v7.png`
   - 当前首要审核图，只确认正面边界和父子遮挡顺序。
   - 黄色是头部与连续身体主层；深灰是耳、眼、中央嘴部、大腿与尾巴；绿色上臂压在身体下；蓝色小臂连前爪压在上臂下；红色小腿连后爪压在大腿下。
   - 用户已用“可以，你试试分层先”确认这套正面边界；该批准只授权生成上面的 v8 正面实际层，不批准 v8 成品，也不授权侧面、背面或 X7。
2. `x6-user-defined-segmentation-contract-v7.json`
   - 登记 10 个语义分组和 5 条遮挡规则；`frontApprovedByUser=true`，其余侧背传播与后续 Gate 仍为 `false`。

## 再看此前的动作主体与肩部证据

1. `qa/x6-clear-layer-and-overlap-review-v5.png`
   - 当前面向用户的首要审核图：不显示骨点、网格、蓝线或青色技术覆盖，只展示完整小橘、五类自然动作组和一条前肢的三帧移动。
   - 前肢以完整外形展示，内部仍是“上臂 + 小臂/前爪”；后肢同理，避免把正常的隐藏楔形接入端单独放大成最终外观。
   - 用户只需判断分组是否自然、抬手后视觉是否连贯。
2. `qa/x6-shoulder-overlap-closeup-v6.png`
   - 针对用户指出的前肢肩部断口，放大静止、整肢抬起和小臂展开三帧；检查的是上沿肩面是否连续，下方棋盘格是正常腋窝外轮廓。
   - 左右上臂的隐藏层已从线状/V 形套筒改为局部实心椭圆肩帽，同时压入 Body 与 Head/颈胸毛遮挡层。
   - 正面右上臂在整肢抬起 `(-12,-6) px` 后仍有 `2835 px` 肩帽压在 Body＋Head 下方，并有 `2754 px` 与上臂近端接触。
3. `x6-clear-layer-review-contract-v5.json`
   - 只改变审核表达，不改变 v4 的实际分层、隐藏套筒或 39/39 拉开审计结论。
4. `qa/x6-joint-safe-motion-bundle-review-v4.png`（技术细节附图）
   - 蓝线是清理后的可见切口；青色只用于显示随子动作组移动、但绘制在父层后方的隐藏套筒/重叠区。
   - 下半部把颈、肩、肘、髋、膝和尾根的子层拉开，直接检查移动后是否露出透明断口。
   - 侧视躯干等动作组按连续主体清理孤立遮罩碎片；侧视被身体完全遮住的远侧上臂/大腿使用隐藏近端桥接层，不伪造额外可见肢段。
5. `x6-joint-safe-motion-bundle-contract-v4.json` 与 `x6-joint-safe-motion-bundle-audit-v4.json`
   - 可见身份切片和隐藏关节套筒分别导出，静止时套筒不替换可见身份像素。
   - 39 个现存父子关节全部有非零重叠；向外拉开 `10 px` 后 `39/39` 仍同时接触父层与子层。
6. `qa/x6-coarse-motion-bundle-review-v3.png`（已被 v4/v5 取代）
   - 用户可操作的动作主体缩减为 16 组：头、嘴、左右耳、左右眼、身体、左右上臂、左右小臂连前爪、左右大腿、左右小腿连后爪、尾巴。
   - 肩、肘、髋、膝只作为不可见 pivot/deformer；63 个精细素材与各层网格继续作为组内子层，不再各自冒充动作主体。
   - 尾巴保留为一个独立动作组；尾根、尾中、尾尖只预留为内部节点，当前不进入 X7 弹性。
7. `x6-coarse-motion-bundle-contract-v3.json`
   - `113/113` 个可见层唯一归属，`111/111` 个身体空间精细补全放置全部归组，没有重复或漏挂。
   - 小臂与前爪同组，小腿与后爪同组，符合本轮用户确认的粗粒度拆法。

## 先看生产层栈候选

1. `qa/x6-production-layer-stack-review-v2.png`
   - 左：从 113 个坐标对齐透明 PNG 重组的实际小橘 Rest，不使用完整源图兜底。
   - 中：63 个精细素材按三视图复用为 111 个身体空间隐藏补全放置；它们不是替换小橘身份的第二层皮肤。
   - 右：关闭若干可见关节/躯干层后的补全暴露检查，默认 Rest 轮廓外已裁切。
2. `x6-production-layer-stack-contract-v2.json`
   - 每个精细实例都有视图、目标可见层、像素边界、父节点和 pivot。
   - `63/63` 精细素材已登记为 `111` 个视图放置，未映射数量为 `0`；用户通过前仍标为候选。
3. 旧的 `x6-fine-body-space-assembly-review-v1.png` 已降级为“错误的可见替换实验”：它把隐藏补全素材强行拼成整只猫，因此出现左右误置、色块接缝和身份偏差，不再作为 X6 主审核入口。

## 先看遮罩裁层是否真的重建源图

1. `qa/x6-layer-assembly-review-v1.png`
   - 左：X5 获批的大字型三视图源姿势。
   - 中：严格按原透明层坐标和绘制顺序重组，可直接看到未归属接缝。
   - 右：把接缝像素分配回最近语义层后的遮罩重建结果。
2. `qa/x6-assembled-xiaoju-three-view-v1.png`
   - 这是按 `drawOrder` 从 113 个源图遮罩裁层重新读取并拼出的透明三视图，不是运行时整图切换。
   - 正、侧、背三个视图的可见源像素覆盖率均为 `100%`。
3. `qa/x6-mask-layer-origin-and-knockout-proof-v1.png`
   - 上排按躯干头部、脸眼、前肢、后肢、耳尾分组，全部从透明 PNG 文件重新读取。
   - 下排关闭 `front:head_base`、`front:forearm_L`、`front:tail_mid` 后会出现真实缺口，证明合成程序没有用完整底图兜底。

这组证据只能证明“遮罩裁层可以重建静止源图”。它不能证明 63 个精细独立素材已经完成身体空间定位和生产级装配。

## 再看 X6 参数与 Action Tracer

1. `qa/x6-parameter-action-tracer-review-v1.png`
   - 九点目光范围画在重组后的小橘正面层级上。
   - `Rest -> Cover -> Rest` 使用 X2 获批的 41 点固定骨段解算。
   - 左右前肢使用 24 ms 小幅错时，Physics 不负责核心遮眼轨迹。
   - 眨眼只改变眼睑开合，不清零目光目标或速度。
2. `qa/x6-actual-xiaoju-motion-contact-sheet-v1.png`
   - 登录画面只证明视觉意图；下方蓝/橙参数条才是连续控制定义。

## 自动检查摘要

- 113 个带身体坐标的源图遮罩透明层参与重建。
- 113 个可见层全部且仅归属一个粗粒度动作组；63 个精细素材形成的 111 个三视图隐藏补全放置也全部归组。
- 39 个父子关节拥有独立隐藏套筒；10 px 向外拉开审计为 `39/39` 通过，父层接触最少 `56 px`、子层边界接触最少 `19 px`。
- 严格层覆盖率：正面 `92.80%`、侧面 `94.42%`、背面 `91.71%`。
- 接缝归属修复后：正、侧、背均为 `100%`。
- 41 个遮眼往返样本全部保持 `0..1` 参数范围并连续回到 Rest。
- 五个主动遮眼关键形继承 X2 解算，骨段长度漂移为 `0`。
- 眼部有九点安全范围和五阶段眨眼定义。
- 状态抢占保留当前参数值与速度，不先跳回中心或 Rest。

## 已知边界

- 接缝归属只修复静止姿势中的可见像素所有权，不能代替关节移开后的隐藏毛发绘制。
- 63 个精细独立素材已完成候选级身体空间登记，并置于 16 个动作组内部，但隐藏补全质量和关节打开效果仍需用户视觉批准。
- 当前产物是 Cubism-ready 合同与视觉候选，不是 `.cmo3/.moc3`。
- X7 耳尖、尾巴、胡须、胸腹与身体回稳 Physics 仍未授权。

## Gate 决策

- 说 `X6 通过`：授权进入 X7 弹性与微动作。
- 指出具体问题：继续只修 X6 分层重组、参数或 Action Tracer，不进入 X7。
