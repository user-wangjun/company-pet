# 阶段 B：可见上臂与袖口所有权门禁

## 当前决定

**工程检查通过，用户中文视觉门禁已批准。**

批准记录：`audit/ownership-gate-user-approval-2026-07-25.json`。 当前可继续计算 `H_total`、划定 `H_test` 并证明连续参数域覆盖下界；该批准不覆盖隐藏纹理或后续 QA。

## 可见上臂 `V_upper_arm`

- 坐标母图：`source/masters/front-color-source-exact-after-reset.png`
- 线稿边界：`source/masters/front-line-source-exact-after-reset.png`
- 全画布候选：`masks/visible-upper-arm-locked.png`
- 源像素参考层：`qa/visible-upper-arm-source-pixels-reference.png`
- 可见像素数：`544`
- 包围盒（右、下边界不含）：`[338, 394, 371, 417]`
- RGB 复制差异像素：`0`
- 最大通道差异：`0`

V4 可见上臂候选从固定 `y=383` 开始，进入了实际袖子区域，因此没有直接沿用。本候选使用原稿袖口折线、原稿手臂轮廓和冻结 V4 肘部分界的交集。袖子、前臂、手链、衣身、头发和背景均排除。

## 袖口遮挡 alpha 与混合带

- 遮挡 alpha 候选：`masks/sleeve-hem-occluder-alpha-locked.png`
- 袖子核心参考：`masks/sleeve-hem-core-reference.png`
- 抗锯齿混合带：`masks/sleeve-hem-aa-mixed-band.png`
- 上臂皮肤核心参考：`masks/upper-arm-skin-core-reference.png`

权威正面母图是 RGB 扁平图，无法恢复原始图层的分数 alpha。本轮锁定的是扁平画面的**像素所有权 alpha**：袖口中心线两侧共 5 px 描边，即中心像素加每侧 2 px，全部归袖子所有；不声称它是原始分层 alpha。

## 预先声明的运动脏边容差

- 默认 1:1 回组：允许改变的源像素数为 `0`。
- 100% 运动审查：最多允许连续 `1` 个源像素宽的边缘色带；不得出现独立暗边、透明缝、爬动或间歇闪烁。
- 200% 最近邻审查：最多允许 `2` 个显示像素，对应 `1` 个源像素。
- 超过以上任一标准即停止，必须请求原画分层，或另行批准受控边界重建；不得临时改写所有权。

## 请审查

1. `qa/ownership-line-color-mask-800.png`：线稿、彩稿、遮罩及所有权同坐标 800% 对照。
2. `qa/visible-upper-arm-checkerboard.png`：可见上臂源像素棋盘格。
3. `qa/sleeve-hem-no-overlay-800.png`：无叠加原稿。
4. `qa/sleeve-hem-thin-overlay-800.png`：1 px 袖口中心线叠加。
5. `qa/sleeve-hem-ownership-800.png`：袖子核心、混合带、皮肤核心所有权。

## 需要的批准

请分别确认：

1. `V_upper_arm` 的袖口、手臂两侧和肘部分界是否可以锁定；
2. 袖口混合带归袖子所有，以及上述运动脏边容差是否可以锁定。
