# 阶段 A 纯色几何报告

## 决定

**工程检查与中文视觉门禁均通过。**

纯色色块只证明几何，不是正式材料，也不证明 Cubism。
批准记录及对应产物摘要见 `audit/stage-a-user-approval-2026-07-24.json`。

## 工程结果

- 41 样本与 4 个组合极值均使用固定 `L1=155.708060px`、`L2=123.967738px`。
- 最大 L1 误差：`5.684e-14px`。
- 最大 L2 误差：`7.105e-14px`。
- 三处接缝最大缺失像素：`{'sleeve_to_upper_arm': 0, 'upper_arm_to_forearm': 0, 'forearm_to_hand': 0}`。
- 相邻材料最小重叠像素：`{'sleeve_to_upper_arm': 3228, 'upper_arm_to_forearm': 660, 'forearm_to_hand': 324}`。
- 发生断开的样本：`0`。
- 原型三角形翻折：`0`。
- 原型退化三角形：`0`。
- 样本 0 与 40 像素差异：`False`。

## 视觉门禁

请依次查看：

1. `qa/visible-ownership-review.png`
2. `qa/default-recomposition.png`
3. `qa/displaced-parts-review.png`
4. `qa/fk-41-contact-sheet.png`
5. `qa/fk-41-slow-preview.gif`
6. `qa/combined-extremes-review.png`
7. `qa/seam-stress-review.png`
8. `qa/revision-shoulder-hand-review.png`
9. `qa/sleeve-boundary-review.png`

当前允许进入阶段 B，但只补画袖子下面的一处上臂隐藏纹理。
