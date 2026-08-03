# 阶段 B：隐藏 ROI 与连续域覆盖下界

## 结论

**通过。**

- `H_total = M_upper_arm - V_upper_arm`：`3689` 像素。
- 本轮 `R_sleeve_proximal` 取可见上臂起点向肩侧 `24 px`，并向肘侧仅延伸 `3 px` 承接袖口混合带；同时要求位于已批准袖口遮挡 alpha 下方。
- `H_test`：`709` 像素，包围盒 `[336, 370, 367, 400]`。
- 更深肩侧隐藏纹理、肘部 joint disk、前臂根侧和姿势相关肘褶均明确排除，不能用本轮结果冒充完成。

## 覆盖下界

本轮把 `depth` 定义为：袖子—上臂接缝责任集的像素中心，到已批准 `V_upper_arm` 的最近欧氏距离；取其中最大值。

- `w_required = 5.000 px`
- `m_AA = 2 px`
- `m_texture_alpha = 2 px`
- `m_planned_mesh = 3 px`
- `w_final = ceil(w_required) + margins = 12.000 px`
- 冻结 `M_upper_arm` 最小连续承载深度：`16.750 px`
- 冻结承载余量：`4.750 px`
- `H_test` 责任深度：`24 px`

因此 `w_final` 可以由冻结几何承载，不需要修改肩点、骨长、动作范围或 V4 边界。

## 连续参数域证明

冻结 V4 中，`sleeve` 与 `upper_arm` 同属 `shoulder_rotation`，实现中都使用相同 `deltaUpper` 和相同肩点。故：

`T_upper_arm(t)^-1 T_sleeve(t) = I`

对所有允许的 `theta1`、`theta2` 和 `phiWristLocal` 恒成立。接缝责任集在上臂局部坐标中不随参数变化，覆盖指标在整个连续域恒定，导数为 `0`。41 个主路径样本和 6 个极值均得到相同的 `w_required`；各样本区间单调，内部上界变化 `0 px < 0.01 px`，因此无需自适应细分。

## 边界

该证明只属于冻结 V4 自建刚体 FK。它不证明 Cubism 关键形插值、预乘 alpha、atlas、UV padding 或 mipmap。

## 下一步

只允许在 `masks/hidden-upper-arm-sleeve-test-roi.png` 内进行本地受控纹理补全；`V_upper_arm` 写保护，`H_test` 外必须零改动。
