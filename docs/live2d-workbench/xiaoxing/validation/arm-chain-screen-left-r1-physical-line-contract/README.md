# 小星 Left R1：物理身体、关节与线稿语义合同

本目录只对应：`view=front`、`screenSide=left`、`anatomicalSide=right`。它是已批准并冻结的
R1 物理身体、关节与线稿语义合同，不是 R2 正式材料包。R1 的用户批准记录位于
`audit/user-visual-approval-r1-2026-08-04.json`；当前总阶段状态以
`../../LEFT-REBUILD-WORKPLAN.md` 为准。

## 权威输入

所有源图路径均相对于本目录：

- `../../source/xiaoxing-three-view-line.png`：结构线稿。
- `../../source/xiaoxing-three-view-color.png`：身份、颜色和材质参照。
- `../../source/masters/front-line-source-exact-after-reset.png`：512×1086 正面线稿母图。
- `../../source/masters/front-color-source-exact-after-reset.png`：512×1086 正面彩稿参照。

正面母图已由脚本验证为三视图 `(x=34,y=0,width=512,height=1086)` 的 1:1 精确裁切。线稿决定结构；彩稿不能覆盖线稿结构。

## 运行

在本目录执行：

```powershell
python tools/build_r1_physical_line_contract.py
```

脚本会确定性生成并审计：

- `audit/source-authority.json`
- `audit/machine-report.json`
- `contracts/body-joint-contract.json`
- `contracts/line-ownership-contract.json`
- `contracts/joint-envelope-contract.json`
- `qa/R1-小星Left-物理关节与线稿语义-中文审查图.png`

不要手工修改脚本生成的 JSON 或审查图；应修改脚本后重新运行。

## R1 边界

本阶段只登记同一身体的肩—肘—腕关系、局部体积、活动范围建议、线稿分类、四层唯一所有权和圆滑关节包络。当前按用户决定，将 `bracelet` 作为 `forearm` 的附着子区域处理，不另建移动层；`hand` 不得重复包含手链专属形状、珠子、链条、绳结、悬垂件或其 RGB/alpha。

审查图中的三个绿色编号点是实际关节：肩、肘、腕。`palmRoot` 只作为掌部方向参考，不是第四个关节，也不参与关节数量统计。

这三个点按解剖学中心放置，而不是按线稿端点放置：肩点是袖山覆盖下的盂肱关节中心投影，肘点是上臂—前臂骨轴的铰链中心，腕点是前臂进入掌部的中心。手链只遮挡腕部外观，归入 `forearm`，不改变腕关节支点。

当前正面母图坐标为：肩 `[166,270]`、肘 `[149,399]`、腕 `[110,538]`；肩点向身体内侧收，腕点位于手链下方两侧腕部轮廓的中轴，而不是右侧内轮廓或手链带面。

审查图的正面结构区现在保留权威线稿原像素，不再叠加近似彩色折线。合同中的 `referenceAnchorsFrontMasterPx` 只是定位需要复核的源线段；它们不是拟合轮廓，也不能直接拿去生成 mask。这样不会把与实际线稿不贴合的重绘线误当成边界。

`observed`、`derived`、`unresolved` 均在合同中显式登记。`unresolved` 不允许用旧材料、对侧镜像或生成式猜测填充，并会阻止下游局部分层。

V38 只作为回归证据：其工程检查通过但用户视觉审查为“全是断口”。本轮不再把手链拆成独立移动语义层，但仍不继承 V38 的污染 alpha/RGB。旧 V25、V30–V38 目录均为只读历史证据，本目录不修改它们。

## 门禁

机器检查通过不等于视觉批准。R1 已于 2026-08-04 获得用户批准并关闭 `R1-GATE`，批准范围
仅允许进入 R2 平色几何与审查，不自动批准任何下游阶段。R2 后续状态及当前停止边界以
`../../LEFT-REBUILD-WORKPLAN.md` 和 R2 正式提升报告为准。
