# 小星 Left 重制工作计划

更新时间：2026-08-12
计划状态：`R2_FORMAL_PROMOTED / R3_READY_NOT_STARTED`
当前门禁：`R2-GATE=passed｜engineeringPass=true｜userVisualApproval=true｜formalR2Promotion=true`

本文件是小星正面画面左侧手臂新分支的 TODO 登记表和执行入口。它只覆盖
`screenSide=left / anatomicalSide=right`。当本文件与旧 Left 试验说明冲突时，本文件
控制新分支；旧冻结与拒绝记录仍原样保留。

## 一、重制结论

本次不再沿 V31–V38 的腕部局部补丁继续修。V38 虽然机器检查通过，但用户视觉结论为
“全是断口”，后续诊断又证明旧前臂 alpha 同时包含手链专属形状与被污染的隐藏 RGB。
因此最早失效点是“语义所有权与完整材料几何”，不是纹理，也不是 Rig。

新分支从原始三视图重新建立一套左侧单臂事实链：

```text
原始三视图与同坐标正面母图
  → 统一身体体积与物理关节
  → 线稿语义边界和唯一像素所有权
  → 局部圆滑凸包式关节包络与隐藏补全
  → 全画布平色 mask 拼装
  → 多姿态压力测试和用户几何冻结
  → 仅在冻结 mask 内生成纹理
  → 网格、单父节点、主动动作
  → 二次 Physics
  → 自定义 Runtime；Cubism 仅作可选适配器
```

## 二、不可变规则

1. **侧别唯一**：用户所称“小星 Left”固定指正面画面左侧、角色解剖学右臂。所有合同
   同时登记 `screenSide` 和 `anatomicalSide`。
2. **坐标唯一**：正式候选均为 `512×1086` 全画布，保持与 Reset 正面母图 1:1 坐标；
   禁止生成后手工缩放、旋转或拖拽到相似位置。
3. **可见边界锁线**：皮肤外轮廓、袖口、皮肤与手链的材料边界必须逐段贴合原线稿。
   阴影、皱褶、肌理、装饰内线先分类，不得自动当作切层边界。
4. **隐藏补全有物理依据**：隐藏肩、肘、腕只允许由同一三视图身体、固定骨长、局部体积
   截面、关节活动范围与遮挡深度推导；证据不足就登记不确定性并停止，不可凭生成结果猜。
5. **关节是支点加隐藏重叠**：父子层共享同一物理解剖支点，但可见像素仍只有一个所有者。
   肩、肘、腕的覆盖区采用局部圆滑凸包/胶囊式包络，以圆弧或 Bézier 控制并保持连续曲率；
   禁止尖角、楔形、多边形补丁、固定圆斑、模糊、膨胀或对整组点直接求粗糙凸包。
6. **手链归入前臂**：`bracelet` 是 `forearm` 的附着子区域，不作为独立移动/语义层；`forearm`
   负责手链专属像素，`hand` 不得重复包含手链形状、alpha 或 RGB。绘制顺序不能替代正确分层。
7. **先平色后纹理**：先用二值/抗锯齿 mask 与调试色证明完整拼装、所有权和运动覆盖。
   平色门禁未通过，禁止生成纹理。纹理阶段不得改变任何 alpha、边界、位置或关节包络。
8. **结构服饰提前、表面服饰延后**：袖子、袖口、手链的几何与归属在平色阶段确定；印花、
   阴影和材质细节只在几何冻结后进入纹理阶段。
9. **机器与视觉双门禁**：哈希、连通、孔洞、像素所有权、骨长、覆盖和回程可以自动检查；
   身份、解剖自然度、线稿贴合、隐藏体积和材质连续性必须由中文视觉审查并由用户批准。
10. **后端解耦**：权威源数据是 JSON + PNG。PS 只可作为可选绘图适配器；Cubism 只可作为
    可选模型后端，不能反向决定源几何。

## 三、权威证据与继承策略

### 新分支的权威输入

| 角色 | 路径 | 已知 SHA-256；R1 必须实测复核 |
| --- | --- | --- |
| 完整线稿三视图 | `source/xiaoxing-three-view-line.png` | `7F8605A85DF7FA2C8843E925F8274A06403D884D975B1B195B2A583478DC222C` |
| 完整彩稿三视图 | `source/xiaoxing-three-view-color.png` | `2D1B9C71C4E6C17EA503800B05F44BF7BFE127799A5E156886C191B97D350154` |
| 正面线稿整数裁切 | `source/masters/front-line-source-exact-after-reset.png` | `706AAF10652147CF76E233532B5459CE130921A96806F6970C91E1F3A427172F` |
| 正面彩稿整数裁切 | `source/masters/front-color-source-exact-after-reset.png` | `33B3CE81781C02B36488ED72FA27C2A136682824CA10C42077895EAB0FFB2DD5` |

### 只读历史证据

- `arm-chain-screen-left-v25-shoulder-joint-correction`：旧骨架候选及当时批准；只能用于对照。
- `arm-chain-screen-left-v30-*` 至 `v36-*`：旧冻结几何、手部与批准；不得就地修改，也不得
  自动提升为 R1 权威源。
- `arm-chain-screen-left-v37-*`：旧正式纹理候选，作为断口回归样本。
- `arm-chain-screen-left-v38-reset-guided-wrist-underlay/audit/machine-report.json`：最新视觉拒绝和
  “手链形状污染前臂皮肤层”的硬回归证据。

旧批准仍只约束其旧工件；R1 必须重新取得独立的结构、平色几何和纹理批准。

## 四、阶段与门禁

| 阶段 | 目标 | 必须产物 | 通过条件 |
| --- | --- | --- | --- |
| R0 范围冻结 | 锁定侧别、目标、非目标和旧链边界 | 本文件、`SCOPE.md` | 已完成 |
| R1 物理与线稿合同 | 证明同一身体、支点、语义边界和圆滑包络 | JSON 合同、确定性审计、中文审查图 | 机器通过 + 用户视觉批准 |
| R2 平色完整材料 | 生成四个独立完整材料 mask 并重组；手链作为 forearm 子区域 | `sleeve/upper_arm/forearm/hand` 全画布 mask | 中性拼装与唯一所有权通过 |
| R3 运动压力与几何冻结 | 验证完整活动包络而非单一默认姿态 | 至少 41 点往返轨迹、组合极值、慢速预览 | 无断口、鼓包、缩骨、穿帮 + 用户批准 |
| R4 锁定纹理 | 在冻结 mask 内恢复可见纹理和物理连续的隐藏纹理 | 四个同坐标透明纹理层、移开审查 | alpha 不变、材质连续 + 用户批准 |
| R5 网格与主动动作 | 建稀疏边界驱动网格、单父树和主动动作 | mesh/node/motion 合同与运行证据 | 中间态和 `0→1→0` 回程通过 |
| R6 二次物理与 Runtime | 增加次级柔性并在目标 WebView 执行 | Physics 或自定义弹性、Runtime 对照 | 主动姿态不被物理改写，实际应用通过 |

任何阶段失败，都回到最早失效的上游阶段；禁止靠遮挡、纹理、网格密度或 Physics 掩盖。

## 五、TODO 登记表

状态规则：只有文件存在、自动检查实际通过且需要的视觉批准已取得，才可勾选。生成了候选
不等于完成。

### R0：范围冻结

- [x] `R0-01` 固定 Left 的屏幕侧与解剖侧映射。
- [x] `R0-02` 记录旧 V12–V38 只读边界，禁止改写冻结工件。
- [x] `R0-03` 选定 JSON + PNG 为权威格式，PS/Cubism 降为可选适配器。
- [x] `R0-04` 记录旧链最早失效点为语义所有权/完整材料几何。

### R1：物理身体、关节与线稿语义合同（当前阶段）

- [x] `R1-01` 实测四个权威输入的尺寸、色彩模式、alpha 状态与 SHA-256。
- [x] `R1-02` 登记三视图到同一身体坐标的视图关系，不把不同视图当作三套身体。
- [x] `R1-03` 在三视图标注肩、肘、腕、掌根及局部体积截面；明确左右和前后深度。
- [x] `R1-04` 从原图重新求身体轴、骨长与关节候选；V25 数值只作误差对照。
- [x] `R1-05` 提出用于几何压力测试的肩/肘/腕活动范围与弯曲分支；此范围不是正式动作。
- [x] `R1-06` 逐段分类可见线：皮肤轮廓、衣物边界、手链边界、内部结构线、阴影/纹理线。
- [x] `R1-07` 建立 `sleeve`、`upper_arm`、`forearm`、`hand` 的唯一可见所有权表；按用户决定将 `bracelet` 登记为 `forearm` 附着子区域。
- [x] `R1-08` 为肩、肘、腕登记父子层、共享支点、前后关系和双向隐藏补全责任。
- [x] `R1-09` 用圆弧/Bézier 控制点定义局部圆滑凸包式包络，并验证无尖角、无异常鼓包。
- [x] `R1-10` 明确抗锯齿边缘、线稿墨线、阴影和手链悬垂件的唯一所有者。
- [x] `R1-11` 生成中文审查图：原线/原彩、三处实际支点、体积近景和回归说明；原线稿原样保留，语义合同只用 reference anchors，不绘制不贴合的合成边界线。
- [x] `R1-12` 生成机器报告，区分已验证事实、推断、未决风险和禁止下游项。
- [x] `R1-GATE` 用户已批准 R1 中文审查图并授权进入 R2；批准登记与冻结清单见 R1 `audit/`。

### R2：全画布平色完整材料

2026-08-07/08-09 的手部拒绝、旧批准和 reopen 记录继续作为只读历史证据。2026-08-12 的整只手平色视觉批准记录与冻结 manifest 是当前视觉输入门禁：`audit/user-visual-approval-whole-hand-flat-color-freeze-2026-08-12.json`、`audit/whole-hand-flat-color-freeze-manifest-2026-08-12.json`。

本次恢复在原批准视觉输入上完成正式工程复核：builder 逐项复核冻结输入、latest markups、source authority、SHA-256、尺寸和 identity transform，并将 `candidates/upper-arm-aa-anatomical-v8/` 逐字节提升为唯一正式 R2 upper-arm 来源。hand 的 visible/hidden/complete、formal display Alpha、flat layer 和红线证据保持保护；`contracts/hand-line-trace-contract.json` 仍是 hand AA 规则权威。

`forearm_skin` 现在按 anatomical core 单一组件/0 孔洞检查；`forearm` primary 只允许 6 个逐坐标登记、均在 wrist ROI、并与 bracelet legal negative spaces 完全对应的 accessory openings。旧 `forearm_semantic_topology` 与 `forearm_complete_single_component_no_holes` 明确标记为 `superseded_by_semantic_core_and_registered_accessory_topology`，不伪造为通过。抬手断裂仍是 R2 diagnostic-only：静态 complete mask 单组件，03/04/06/07 的 64/71 px 小岛定位到 hand 的 `BICUBIC + Alpha>=128` 变换阈值；不进入 R3。

- [x] `R2-01` 为四个语义层分别输出 visible、hidden、complete 全画布 mask；手链归入 forearm 子区域。证据：R2 `masks/` 与 `audit/machine-report.json`。
- [x] `R2-02` 证明 `forearm_skin` anatomical core 单组件/0 孔洞，并证明 `forearm` 的 6 个 primary accessory openings 逐坐标登记且无额外孔洞。证据：R2 拓扑合同与机器报告。
- [x] `R2-03` 最新整只手视觉批准与 hand redline hash 已复核，正式 hand 输入保持保护，线外 alpha 门禁通过。证据：`audit/user-visual-approval-whole-hand-flat-color-freeze-2026-08-12.json`、`audit/whole-hand-flat-color-freeze-manifest-2026-08-12.json`。
- [x] `R2-04` 证明手链 alpha/RGB 不存在于前臂或手的皮肤材料中。证据：`masks/subregions/` 语义互斥检查与移开手链审查。
- [x] `R2-05` 按最终绘制顺序完成平色 layer-only 重组，不使用整人底图兜底；upper-arm v8 已逐字节提升为正式 R2 来源。证据：`audit/r2-formal-promotion-report.json`、R2 `flat-layers/` 与 draw-order 合同。
- [x] `R2-06` 自动检查像素漏领、重复可见所有权、越界、连通、孔洞、输入哈希、根部连续性、bracelet 前后关系、逐段原线拟合与受保护文件快照。证据：R2 `audit/machine-report.json`、`audit/segmented-boundary-report.json`。
- [x] `R2-07` 生成并更新正式中文 R2 审查图，包含中性位、单层移开、关节放大、bracelet 深度、源线拟合和当前停止边界。证据：`qa/R2-小星Left-全画布平色材料-中文审查图.png`。
- [x] `R2-08` 完成 hand hidden wrist-root AA 的工程复核与视觉冻结引用：浮点 Bézier/C2 连接、hidden envelope、逻辑 mask 与正式 display Alpha 分离、可见 hand 零变化、红线 hash/越界和确定性证据均已登记。证据：hand AA 合同、display Alpha、`audit/r2-repair-pixel-diff.json` 与最新视觉 freeze manifest。
- [x] `R2-GATE` `engineeringPass=true`、`userVisualApproval=true`、`formalR2Promotion=true`、`overallGatePass=true`，`R2-GATE=passed`；`R3=READY_NOT_STARTED`，只允许下一阶段另行授权，不在本次启动。

### R3：运动压力测试与几何冻结

当前状态：`READY_NOT_STARTED`。R3 历史候选和失败报告只读保留；本次只完成 R2 正式收口，不运行 R3。未来 R3 仍需至少 41 个高分辨率 floating-boundary coverage 点和独立用户批准。

- [ ] `R3-01` 对肩、肘、腕执行至少 41 点的连续 `0→1→0` 轨迹。
- [ ] `R3-02` 检查单关节极值、组合极值和往返回零，不只检查默认姿态。
- [ ] `R3-03` 自动检查骨长漂移、关节脱离、透明缝、重复皮肤、外轮廓鼓包和回程差异。
- [ ] `R3-04` 生成慢速预览、关键帧接触表和手链移开检查。
- [ ] `R3-GATE` 用户批准完整活动包络后，生成几何冻结清单与哈希。

### R4：锁定 mask 内纹理

- [ ] `R4-01` 可见像素从 Reset 彩稿同坐标提取，逐像素核对源 RGB。
- [ ] `R4-02` 隐藏皮肤纹理按三视图体积、邻接肤色与材质流连续补全，并标记推断区。
- [ ] `R4-03` 在袖子与 forearm 子区域内分别补全自身材质，不向皮肤层烘焙手链或阴影轮廓。
- [ ] `R4-04` 逐层核对纹理 alpha 与 R3 冻结 mask 完全一致。
- [ ] `R4-05` 完成纹理 layer-only 重组、移开层、三姿态与接缝近景审查。
- [ ] `R4-GATE` 用户批准纹理后冻结；未批准不得建网格。

### R5：网格、节点与主动动作

- [ ] `R5-01` 每个真实层建立一个边界驱动、无越界三角形的稀疏网格。
- [ ] `R5-02` 每层只有一个主要控制节点；父子树符合身体层级，绘制顺序不冒充父级。
- [ ] `R5-03` 支点放在 R1 批准的解剖关节；保持刚性骨长与隐藏覆盖。
- [ ] `R5-04` 用主动参数/动作曲线实现目标运动与 `0→1→0` 回程。
- [ ] `R5-05` 验证中间态无翻面、UV 破坏、断口、缩骨和手链漂移。
- [ ] `R5-GATE` 用户批准主动动作；未批准不得添加 Physics。

### R6：二次物理与 Runtime

- [ ] `R6-01` 只给袖口/手链悬垂等软性区域添加低幅二次响应，固定解剖支点。
- [ ] `R6-02` 验证冲量后收敛，无持续振荡，Physics 不决定核心手臂姿态。
- [ ] `R6-03` 先实现/验证自定义 Runtime 的层级、网格、绘制顺序、参数混合与弹性。
- [ ] `R6-04` 如确有生态需要，再制作 PSD/Cubism 适配器并做同序列对照。
- [ ] `R6-05` 在目标 WebView 进行慢速动作、60 秒稳定性和返回中性位验证。
- [ ] `R6-GATE` 用户批准独立运行结果；之后才能讨论全身或正式 pet 接入。

## 六、阶段一停止条件

出现任一项即停止 R1，不得用推测继续：

- 三视图需要不同骨长或不同身体体积才能解释同一只手臂。
- 无法从线稿判断某条线属于皮肤边界、手链边界还是内部纹理。
- 隐藏肩、肘、腕的截面与正面可见宽度或侧视体积冲突。
- 关节包络只能通过尖角、粗糙凸包、固定圆斑或异常外扩才能覆盖目标范围。
- 手链与皮肤无法建立互斥的语义所有权。
- R1 审查图无法让用户直接比较原线、原彩和候选结构。

## 七、第一阶段执行提示词

以下提示词只授权 R1，不授权平色 mask、纹理或 Rig：

```text
请使用 rig-live2d-pet skill，在 D:\CodeWorkspace\电脑桌宠 中执行“小星 Left 重制”的
第一阶段 R1：物理身体、关节与线稿语义合同。请自行完成全部工作，不调用外部模型或代理。

先完整阅读并遵守：
1. AGENTS.md
2. docs/live2d-workbench/xiaoxing/SCOPE.md
3. docs/live2d-workbench/xiaoxing/LEFT-REBUILD-WORKPLAN.md
4. docs/live2d-workbench/xiaoxing/HANDOFF-PROMPT.md
5. docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-v38-reset-guided-wrist-underlay/audit/machine-report.json

侧别定义必须固定为：
- view=front
- screenSide=left
- anatomicalSide=right
- 用户称呼“小星 Left”指上述同一只手臂。

本阶段唯一权威图像输入是：
- docs/live2d-workbench/xiaoxing/source/xiaoxing-three-view-line.png
- docs/live2d-workbench/xiaoxing/source/xiaoxing-three-view-color.png
- docs/live2d-workbench/xiaoxing/source/masters/front-line-source-exact-after-reset.png
- docs/live2d-workbench/xiaoxing/source/masters/front-color-source-exact-after-reset.png

旧 screen-left V12–V38 文件全部只读，不得改写、删除或覆盖。V25 骨架和 V30–V36
冻结数据只能作为误差对照，不能直接继承为 R1 结论；V37/V38 是断口与语义污染回归证据。
禁止从 screen-right 镜像几何作为新 Left 的物理事实。

只在以下新目录内写阶段一产物：
docs/live2d-workbench/xiaoxing/validation/arm-chain-screen-left-r1-physical-line-contract/

阶段一必须完成：
1. 实测四个权威输入的路径、尺寸、色彩模式、alpha 和 SHA-256，登记坐标关系；禁止缩放。
2. 用线稿三视图和彩稿三视图建立同一个身体的局部肩—肘—腕—掌根模型，记录左右、深度、
   骨长、局部体积截面、关节弯曲分支以及用于几何 QA 的活动范围建议。
3. 重新测量正面肩、肘、腕候选，不盲从旧坐标；把与 V25 的差异单独报告。
4. 逐段分类原线稿：皮肤可见轮廓、衣物/袖口边界、手链边界、内部结构线、阴影/纹理线。
   可见色块边界必须跟随真正的皮肤或服饰语义线，不能由颜色阈值或规则多边形替代；审查图保留原线稿，不用近似重绘线冒充 source trace。
5. 为 sleeve、upper_arm、forearm、hand 建立唯一可见像素所有权和绘制顺序；bracelet 作为 forearm
   附着子区域，hand 禁止包含手链专属 alpha 或 RGB。
6. 为肩、肘、腕定义“共享物理解剖支点 + 父子隐藏重叠”。覆盖区必须是局部圆滑凸包/
   胶囊式包络，用圆弧或 Bézier 控制点表达并保持连续曲率；禁止尖角、楔形、粗糙全局凸包、
   固定圆形补丁、blur、dilate 或依靠纹理遮缝。
7. 隐藏补全只能来自同一三视图身体、骨长、体积截面、活动范围和遮挡深度。每项结论标为
   observed、derived 或 unresolved；unresolved 不能被生成式猜测替代。
8. 生成确定性的中文审查图，至少包含：正面原线/原彩同坐标图；肩、肘、腕、袖口、手链的
   400%–800% 近景；三处实际支点；体积/包络合同说明；与 V38 断口的回归说明。原线稿必须
   原样可见；语义分类通过合同中的 source reference anchors 审查，不用不贴合的合成边界线。
9. 编写可重复运行的构建/审计脚本，并生成机器报告。不要手工修改脚本生成的报告。
10. 只在所有机器检查真实通过且用户批准登记存在后，更新 LEFT-REBUILD-WORKPLAN.md 中对应的 R1 checkbox；
    R1-GATE 已由用户批准关闭；R2 旧批准仅覆盖当时的平色几何与 layer-only 拼装范围，已被 2026-08-07 手部视觉拒绝重新打开，不自动授权下游制作。

建议的最小产物：
- README.md
- tools/build_r1_physical_line_contract.py
- audit/source-authority.json
- audit/machine-report.json
- contracts/body-joint-contract.json
- contracts/line-ownership-contract.json
- contracts/joint-envelope-contract.json
- qa/R1-小星Left-物理关节与线稿语义-中文审查图.png

自动检查至少覆盖：输入哈希与尺寸、坐标恒等、侧别字段完整、骨长一致性、支点位于合理体积、
线段分类无遗漏、可见所有权唯一、手链与皮肤语义互斥、包络控制点连续且无尖角、输出确定性。
人体自然度、隐藏体积是否可信、线稿贴合和圆滑包络是否自然必须保留为用户视觉门禁。

本阶段明确禁止：正式 visible/hidden/complete mask、平色拼装、纹理生成或补绘、PSD、Cubism、
ArtMesh、节点、参数、动作、Physics、Runtime、平台接入，以及对任何旧冻结目录的修改。

最终只汇报：实际创建文件、机器检查结果、与旧证据的差异、仍未解决的物理/语义问题、中文
审查图路径，以及“等待用户批准 R1”这一停止状态。不得声称进入 R2 或整个 Left 已完成。
```
