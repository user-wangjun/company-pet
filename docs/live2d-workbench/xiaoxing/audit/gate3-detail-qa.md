# Gate 3 局部视觉 QA

审查板：[gate3-detail-qa.png](../qa/gate3-detail-qa.png)

## 逐区结论

| 区域 | 视觉结论 | 当前动作 |
| --- | --- | --- |
| 脸、眼睛、发根 | 眼睛必须按 socket/sclera/iris/pupil/highlight/上下眼睑/遮罩拆分；耳后和发下脸侧不能留空 | 已在 62 层合同中显式列出 |
| 肩、袖、上臂 | 袖子是衣服前景，不得把袖口当成上臂终点；肩根需在衣服下完整延伸 | 保留 torso hidden base 与左右 upper-arm 隐藏补画 |
| 胸前印花、腰、裙 | 印花的直线和蝴蝶形状不应被躯干大网格拉扯；T 恤和裙腰遮住的躯干/骨盆仍需独立底层 | shirt_print 作为受限贴花，body_hidden_base 负责连续体积 |
| 手、腕饰 | 首版没有握拳、张指或手势动作；逐指拆分不会产生可见收益 | 左右完整手各一层，手链独立；只做手腕轻微跟随 |

## 手部精细度边界

历史上曾尝试手指扇与逐指拆分，用于确认用户指出的串色问题。随后用户明确首版没有握拳、张指或
其他手势，不应在手指上继续消耗资源。当前有效方案因此收敛为左右完整手各一层：保留原图全部手指
像素，只在腕部设置轴心并做轻微跟随；手链继续独立。逐指草稿仅保留为历史排错证据，不进入导出清单、
ArtMesh 或 Cubism 参数。

## 用户反馈后的修正

用户指出初版手部框选存在漏覆盖和过覆盖，并进一步指出修正版仍像是没有对齐。复查确认有三个原因：

1. 初版使用粗矩形表达手掌、拇指和手指扇，矩形本身无法贴合张开的手指轮廓。
2. 总蓝图把母稿粘贴到 `(24, 24)` 后，标注没有同步加上该偏移，导致所有框在审阅板上相对原图偏移 24 px。
3. 左手不应由右手轮廓镜像得到；两侧手势、指缝和拇指张角并不对称。

现已完成：

- 全局标注统一使用母稿偏移 `(24, 24)`，消除审阅板坐标错位。
- 手部不再使用矩形，改为源母稿坐标中的闭合候选多边形。
- 左右手分别作为完整连续材质导出，不再对手指重新着色或分配身份。
- 左右手分别从各自原图重新取样，不再镜像复用候选轮廓。
- 候选多边形只负责决定语义归属；实际预览颜色会裁切到从每只彩色手独立提取的真实皮肤像素连通域，
  因而不会越出手部外轮廓。
- 每只手只属于一个手部材质层；腕饰仍为独立前景层。
- 轮廓坐标写入 `gate3-production-blueprint-contract.json`，后续可以复现和继续微调。

像素检查结果：

| 手 | 皮肤像素 | 未覆盖 | 重叠 | 覆盖率 |
| --- | ---: | ---: | ---: | ---: |
| 角色右手 | 2068 | 0 px | 0 px | 1.000 |
| 角色左手 | 2094 | 0 px | 0 px | 1.000 |

修正版证据：

- [gate3-hand-coordinate-grid.png](../qa/gate3-hand-coordinate-grid.png)
- [gate3-hand-layer-review.png](../qa/gate3-hand-layer-review.png)
- [gate3-hand-pixel-alignment-qa.png](../qa/gate3-hand-pixel-alignment-qa.png)
- [gate3-hand-simple-alignment-qa.png](../qa/gate3-hand-simple-alignment-qa.png)（当前有效）
- [gate3-hand-draft-layer-contact-sheet.png](../qa/gate3-hand-draft-layer-contact-sheet.png)
- [gate3-hand-pixel-alignment.json](gate3-hand-pixel-alignment.json)
- [gate3-production-blueprint-review.png](../qa/gate3-production-blueprint-review.png)

## 自审规则

- 所有框选只表示语义 ownership，不直接当作 alpha mask。
- mask 阶段必须沿真实线稿边界描边，不能使用矩形框生成部件。
- 每个活动层必须包含被邻层遮挡的连续材质；透明洞不能由默认 draw order 掩盖。
- 任何生成式补画只允许填充已锁定区域，不得改变边界、比例或身份。

## 当前结果

**局部视觉 QA：已完成像素裁切版修正，等待用户视觉确认；生产 mask 尚未开始。**
