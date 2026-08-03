# 小星 Live2D 独立工作包

这是“小星”的独立 Live2D 前期工作包。目前不属于正式桌宠包，不会注册到
`public/pets/index.json`，也不会改变平台默认桌宠。

当前完整交接与真实门禁状态见 `HANDOFF-2026-07-23.md`。该文档明确区分可用源
素材、已否决历史产物和 Reset V2 尚未通过的眼睛/头发候选；后续继续工作时应先
阅读交接文档，不得直接沿用旧 PSD 或 Cubism 工程。

如需把任务交给另一位执行者，可直接使用 `HANDOFF-PROMPT.md`。其中包含可复制
的完整交接提示词、当前 Reset V3 右眼证据板状态和接手后的第一步。

## 重要：V15 材料链已被用户否决并再次重置

2026-07-23 用户确认 `model/xiaoxing-material-master-v15.psd` 本身已有缺失，
头发和眼睛分层粗糙，后续派生结果无效。因此 V5–V15 和
`model/xiaoxing-rig-v1.cmo3` 全部降级为历史失败证据，不再修补或继续使用。

当前唯一权威输入重新收紧为两张原始三视图：

- `source/xiaoxing-three-view-line.png`
- `source/xiaoxing-three-view-color.png`

退回决定见 `audit/REJECTED-V5-V15-MATERIAL-CHAIN.md`，当前机器可读状态见
`audit/authoritative-status-reset-after-v15-rejection.json`。在新的线稿母版
得到用户明确通过以前，禁止生成材料 PSD、Cubism 网格、参数和物理。

## 历史：此前的第一次重置

经重新对照知乎文章和原始素材，Gate 4–10 的图像草稿全部降级为历史实验，不能作为分层、眼睛坐标、补画或网格依据。它们存在眼睛未对齐、非等比拉伸和可见层串材质等问题。

总标记见 `audit/REJECTED-GATE4-10.md`。

当前唯一有效基线是：`qa/v2-lineart-baseline-audit.png` 与 `audit/authoritative-status-v2.json`。

已重新逐段核对用户指定的知乎文章，并把可执行约束固化到
`ARTICLE_EXECUTION_CONTRACT.md`。文章中的关键流程是“独立图层 → 同尺寸透明 PNG → 每层网格 → 单父节点层级 → 柔性材料物理 → 视线/动作追踪”，后续不再用全身色块或非等比形变代替真实拆层。

已建立实际 Photoshop 工作母版：
`model/xiaoxing-line-separation-working-v1.psd`。当前包含锁定线稿参考层与头部、眼睛、上身、下身、中文审查分组；它是后续唯一可提升的分层母版，当前尚未把旧 V2 候选提升为正式材料。

V3 曾尝试把双眼重画成规则材料，但自审和用户复核均确认它改变了眼裂、眼白及虹膜比例；该版本从未导入 PSD，已整体移入 `audit/rejected-v3-eye-reconstruction/`，结论见 `audit/REJECTED-V3-EYE-RECONSTRUCTION.md`。

当前 V4 改为原彩稿像素回组，见 `qa/v4-eye-pixel-roundtrip-review.png`。现阶段只证明原像素拆开再合成时不改变长相；候选仍含刘海遮挡像素，因此明确标记为 `in_progress_not_promoted_to_psd`。下一步必须先完成前发所有权，再拆虹膜、瞳孔、高光和眼线。

- 线稿决定每个图层的边界和拆分。
- 彩色图只用于身份、颜色和材质参考。
- 所有图层必须保持 512×1086 原始坐标，不做非等比拉伸。
- 先逐层导出独立 PNG，再建立每层网格和父子节点；最后才做物理和追踪。

V2 双眼目前只完成线稿候选描边审查，还没有导出眼睛纹理：见
`qa/v2-eye-lineart-trace-review.png`、
`qa/v2-eye-lineart-boundary-audit.png` 与
`blueprints/v2-eye-lineart-boundary-contract.json`。

眼睛审查图现在统一使用“画面左眼／画面右眼”命名，避免与角色自身左右混淆；画面右眼的候选边界已按原始线稿重新收窄。

根据最新视觉复核，双眼候选已从“线稿中心线”改为覆盖完整黑色眼裂的边界范围；画面左、右眼均重新扩大并重新生成结构/颜色候选。

已生成 10 个仅用于结构检查的全画布 RGBA 草稿层（左右眼各 5 层）：
`qa/v2-eye-structure-contact-sheet.png`。这些层不含彩色纹理、睫毛细节或眨眼关键形。

已生成 12 个 V2 颜色候选层（左右眼各 6 层）：
`qa/v2-eye-color-candidate-contact-sheet.png`。其形状只来自线稿合同，彩稿只提供色值；仍没有眨眼或视线参数。

全身接缝目前只完成“交界候选地标”审查，没有生成遮罩：
`qa/v2-body-lineart-seam-audit.png` 与
`blueprints/v2-body-seam-contract.json`。
红线只表示相邻层的线稿交界位置，不是切图范围；手部仍按每侧一整层处理。

领口接缝已修正为衣领的浅弧线，不再误用项链 V 形；裙内隐藏大腿候选也已扩大到与可见腿完整衔接，避免出现缩小色块。

下半身已增加一张粗分层所有权审查图：
`qa/v2-lower-body-ownership-audit.png` 与
`blueprints/v2-lower-body-ownership-contract.json`。
半透明色块只用于检查裙子、左右腿、袜子和鞋的材料归属，尚未成为正式 alpha mask；裙内隐藏大腿仍需结合侧视图补全。

根据当前没有走路/抬腿动作的范围，分层清单已简化为：整条裙子一层、左右整腿各一层、左右袜子和鞋各一层；不再把大腿/小腿或裙褶拆成无动作价值的独立层。

在此基础上已生成 7 个全画布 RGBA 平色候选层，并做层-only 重建：
`qa/v2-lower-body-candidate-contact-sheet.png`。
这些文件仍标记为 `candidate_only_no_texture_no_mesh`；它们用于证明绘制顺序、隐藏腿连续和袜鞋纯度，不是最终纹理或 Cubism 导入件。

候选层已完成一次红底接缝压力审查：模拟裙子上下 8px、双腿左右 3px 的小幅位移，检查裙下、袜口和鞋口是否露出透明断层，见 `qa/v2-lower-body-seam-stress.png`。

上半身已完成 9 个全画布 RGBA 平色候选层的层-only 重建：
`qa/v2-upper-body-candidate-contact-sheet.png`。
其中衣身、左右袖子、左右前臂、左右完整手层、脖子和项链按粗粒度处理；手部没有拆指。审查底图已改为白底合成，避免把透明区域误读成黑色材质。

上半身候选层随后通过红底接缝压力审查：前臂和手层分别向左右小幅偏移 3px，袖口与腕部没有出现可见透明断层，见 `qa/v2-upper-body-seam-stress.png`。

衣服印花已单独建立表面贴层候选：`qa/v2-shirt-print-candidate-contact-sheet.png`。首次自审发现两侧头发线条混入，已收窄印花上部 ROI 并重新生成；当前只保留衣身内部的文字和蝴蝶笔画，不承担身体边界或变形。

头部材料目前只做了所有权候选图 `qa/v2-head-ownership-audit.png`；自审认为脸底与后发的重叠表达仍不够清楚，已停在视觉待复核状态，不生成头发或脸部 RGBA。

## 当前边界

- 角色名：小星
- 工作 id：`xiaoxing`
- 当前阶段：退回原始三视图，重新建立无缩放、无缺失的正面线稿母版
- 已授权：在视觉门禁通过后继续正式拆件、隐藏材质、Cubism 绑定和独立运行验证
- 当前暂停项：所有材料拆分、PSD、Cubism 工程与独立运行验证
- 范围外：运行时接入和正式桌宠注册

## 目录

```text
source/       原始参考图，不在这里覆盖修改
audit/        自动审计和人工审图结论
blueprints/   身体、拆件、层级和参数蓝图
qa/           后续视觉验证证据
model/        后续 Cubism 源文件与导出模型
```

## 当前素材

- `source/xiaoxing-three-view-color.png`：彩色三视图，当前身份与配色参考
- `source/xiaoxing-three-view-line.png`：线稿三视图，当前结构与边界参考

两个文件均为完整画板、无透明通道的单张 PNG，不是可直接绑定的分层素材。

## 工作规则

1. 所有小星专属素材和证据保留在本工作包内。
2. 先通过三视图确认同一个身体的比例与结构，再确定正面生产母稿。
3. 拆件必须从同一坐标锁定母稿派生；不拼接不同姿势或不同身份的局部。
4. 每个活动部件需要补全被遮挡区域，不能靠默认遮挡掩盖空洞。
5. 用户通过当前视觉门禁之前，不进入下一阶段。
6. 面向用户的审查图、颜色说明、通过条件和异常提示统一使用中文；文件名和 Cubism 参数 id 可保留英文。

## 当前 QA 入口

- `audit/REJECTED-V5-V15-MATERIAL-CHAIN.md`：当前有效的退回结论
- `audit/authoritative-status-reset-after-v15-rejection.json`：当前权威状态
- `source/xiaoxing-three-view-line.png`：唯一线稿来源
- `source/xiaoxing-three-view-color.png`：唯一身份与颜色来源
- `audit/REJECTED-RESET-V1-AUTO-OWNERSHIP.md`：自动阈值/区域切分再次被工作自审否决，未提升为材料
- `qa/reset-v2-eye-closed-boundary-review.png`：双眼完整闭合曲线与全画布平色材料审查
- `qa/reset-v2-eye-closeup-review.png`：双眼曲线的中文局部放大定位，仅用于预览
- `qa/reset-v2-hair-closed-boundary-review.png`：后发、刘海、左右侧发四组全画布闭合材料审查
- `qa/reset-v2-hair-closeup-review.png`：头发闭合曲线的中文局部放大定位，仅用于预览
- `audit/reset-v2-eye-blueprint.json`、`audit/reset-v2-hair-blueprint.json`：当前 V2 曲线坐标、图层路径和停止条件；仍待视觉门禁，尚未生成纹理 PSD

以下 V5–V15 项目均为已否决历史记录，不可作为继续生产的依据：

- `qa/v15-joint-material-gate-review.png`：21 个默认材料层的联合审查；未覆盖像素为 0，默认可见颜色误差为 0
- `audit/v15-psd-import-validation.json`：Photoshop 分层 PSD 验证；21 个默认层、16 个隐藏眼材质层，无多余空白层，导出预览与门禁合成完全一致
- `audit/authoritative-status-v15.json`：当前权威状态；正式分层 PSD 已通过，Cubism 绑定与运行时仍待完成
- `qa/v14-hair-subgroup-pull-review.png`：后发、刘海和画面左右侧发束的分组拉开审查；默认合成误差为 0
- `qa/v13-long-hair-coordinate-grid.png`：胸前发尾与 `Savoir` 印花的 5px 人工归属网格
- `audit/v13-long-hair-manual-boundary.json`：人工边界结论；首字母笔画留在衣身，未采用会切断发束的矩形排除方案
- `audit/authoritative-status-v13.json`：当前权威状态；现有材料子门禁已通过，剩余头发子分组和联合材料门禁
- `qa/v12-eye-hidden-materials-review.png`：完整眼白、虹膜、瞳孔、3px 视线压力测试与闭眼线候选；默认原眼回组误差为 0
- `audit/authoritative-status-v12.json`：当前权威状态；眼睛隐藏材料通过工作自审，PSD 导入前仅剩长发/印花边界和联合视觉门禁
- `qa/v11-sleeve-hand-sock-overlap-review.png`：袖内手臂、整手策略和鞋内袜子隐藏重叠；左右补全对称，默认回组误差为 0
- `audit/authoritative-status-v11.json`：当前权威状态；手腕不再制造独立接缝，长发/印花与眼睛隐藏材料仍待完成
- `qa/v10-hidden-thigh-continuity-review.png`：当前有效的裙内大腿连续补全；肤色取自同腿可见上段，裙子上移 26px 不再出现缩小色块
- `qa/v9-long-hair-shirt-separation-review.png`：胸前长发与衣身补底候选；默认合成误差为 0，但发尾与 `Savoir` 文字重叠处仍待归属精修
- `audit/authoritative-status-v10.json`：当前权威状态；大腿隐藏补全通过工作自审，其余视觉门禁仍未完成
- `qa/v8-body-original-pixel-ownership-review.png`：当前全身原彩稿像素粗分层；不再使用平色色块，双手保持整层，裙内大腿尚未伪造补画
- `qa/v7-eye-semantic-original-pixel-review.png`：双眼可见像素语义候选拆层；默认整脸回组误差为 0，隐藏眼材质仍待补齐
- `qa/v6-face-eye-preservation-review.png`：刘海下脸底补全与双眼原像素、原坐标保留审查
- `audit/authoritative-status-v8.json`：当前权威状态；所有 V5–V8 材料仍未导入 PSD/Cubism
- `qa/v5-front-hair-ownership-review.png`：当前有效的前发原像素归属与拉开审查；默认回贴误差为 0，尚未导入 PSD
- `audit/authoritative-status-v5.json`：当前权威状态；等待前发归属视觉门禁确认后才补脸底与双眼
- `qa/v2-eye-lineart-trace-review.png`：双眼线稿候选描边复核，统一按画面左右命名
- `qa/v2-body-lineart-seam-audit.png`：领口、袖口、手链、衣摆、裙腿、袜鞋的中文近景接缝候选审查
- `blueprints/v2-body-seam-contract.json`：全身接缝候选坐标与隐藏补全要求
- `audit/v2-body-seam-validation.json`：接缝候选坐标、原生画布和无拉伸规则验证
- `qa/v2-lower-body-ownership-audit.png`：下半身粗分层所有权审查
- `audit/v2-lower-body-ownership-validation.json`：下半身候选多边形与画布验证
- `qa/v2-layer-trace-checklist.png`：更新后的粗分层清单与父节点顺序
- `qa/v2-lower-body-candidate-contact-sheet.png`：7 个下半身候选层的层-only 平色重建
- `audit/v2-lower-body-candidate-layer-validation.json`：全画布 RGBA、候选状态和无网格/无动作验证
- `qa/v2-lower-body-seam-stress.png`：候选层小幅位移的红底接缝压力审查
- `audit/v2-lower-body-seam-stress-validation.json`：压力测试范围与候选层完整性验证
- `qa/v2-upper-body-candidate-contact-sheet.png`：上半身 9 个候选层的层-only 平色重建
- `audit/v2-upper-body-candidate-layer-validation.json`：上半身候选层完整性验证
- `qa/v2-upper-body-seam-stress.png`：上半身袖口/腕部/手链接缝压力审查
- `audit/v2-upper-body-seam-stress-validation.json`：上半身压力测试范围与候选层完整性验证
- `qa/v2-shirt-print-candidate-contact-sheet.png`：线稿印花、彩稿参考与印花候选层对照
- `qa/v2-shirt-print-candidate-layer.png`：全画布 RGBA 印花候选层
- `audit/v2-shirt-print-candidate-validation.json`：印花表面贴层候选验证

以下 Gate 3–10 条目仅保留为历史记录，其中 Gate 4–10 已明确废弃，不可继续派生：

- `qa/gate3-hand-pixel-alignment-qa.png`：左右手像素裁切分区
- `qa/gate3-hand-simple-alignment-qa.png`：当前有效的左右完整手层审查图
- `qa/gate3-hand-draft-layer-contact-sheet.png`：已废弃的逐指实验记录（不进入模型）
- `qa/gate4-eye-landmark-preflight.png`：双眼坐标、眼角与开合边界定位
- `qa/gate4-eye-motion-contact-sheet.png`：中文眨眼与视线运动草稿审查
- `qa/gate4-eye-material-contact-sheet.png`：眼窝、眼白、虹膜、瞳孔、高光、眼睑、眼裂遮罩分层审查
- `qa/draft-eye-layers.json`：眼睛八类全画布 RGBA 草稿清单（仅 QA，不是正式 Cubism 导入）
- `audit/gate4-eye-contract-validation.json`：眼睛运动与素材完整性验证
- `qa/gate5-hair-body-preflight.png`：头发、袖臂、衣裙、腿袜鞋的中文粗分层覆盖审查
- `blueprints/gate5-hair-body-contract.json`：只拆有动作价值材料的 Gate 5 分组合同
- `audit/gate5-hair-body-validation.json`：分组层存在性、坐标范围与完整手层政策验证
- `qa/gate6-motion-contract-contact-sheet.png`：头转、身体轻摆、眨眼与头发跟随的中文运动审查
- `blueprints/gate6-motion-contract.json`：9 个首版参数与 4 组保守物理联动
- `audit/gate6-motion-contract-validation.json`：参数目标、物理输入与完整手层政策验证
- `qa/gate7-material-draft-contact-sheet.png`：26 个可回收全画布 RGBA 可见层草稿的中文审查
- `qa/draft-material-layers.json`：可见层草稿清单；所有层仍标记为 `visible_only_draft`
- `audit/gate7-material-draft-validation.json`：尺寸、透明度、合同归属和隐藏补画政策验证
- `qa/gate8-hidden-fill-contact-sheet.png`：12 个隐藏补画候选的中文接缝审查
- `qa/hidden-fill-candidates.json`：隐藏补画候选清单，全部标记为 `candidate_only`
- `audit/gate8-hidden-fill-validation.json`：候选尺寸、透明度和非正式导出边界验证
- `qa/gate9-seam-stress-contact-sheet.png`：三档移动幅度的中文接缝压力图
- `audit/gate9-seam-stress-validation.json`：12 个候选、三档位置的透明露白验证
- `audit/gate9-seam-stress-review.md`：结构通过但边缘精修仍未完成的自审结论
- `audit/gate3-hand-draft-validation.json`：已废弃逐指方案的历史验证记录
- `qa/gate3-seam-audit.png`：头发、袖口、裙腰、手、袜口与鞋的同坐标接缝复核
- `blueprints/gate3-production-blueprint-contract.json`：62 层、绘制顺序、单父节点层级和参数草案
- `model/material-export-manifest.json`：门禁通过后逐层导出的全画布 RGBA PNG 清单；当前仅为计划，未生成正式 mask
