# 阶段 B 隐藏纹理候选：用户视觉否决

## 结论

本候选已于 2026-07-25 被用户视觉否决，阶段 B 在此停止。

`materials/textured/upper-arm-sleeve-hidden-test.png` 以及基于它生成的运动预览不得再作为“完整、连续、可独立运动的上臂/袖子材料”通过证据，只保留为失败证据。

## 用户指出的问题

- `qa/upper-arm-sleeve-hidden-test-checkerboard.png` 中，上臂材料是断开的局部裁片。
- `qa/sleeve-moved-away.png` 中，上臂与袖子均呈分离状态；袖子上下文明显是被裁剪的小块。

## 根因

1. `H_test` 是袖口近端的局部验证区域，不是从肩部到下游有效边界的完整连续上臂材料。把它单独移动或最大暴露时，人工截断边界必然可见。
2. `masks/sleeve-hem-qa-context-safe.png` 只是从扁平源图中筛出的局部袖口 QA 条带，不是完整袖子材料。
3. 扁平源图中的袖子被头发和衣身遮挡。排除这些非袖子像素后，只能得到残缺袖片；保留它们则会把不属于袖子的内容一起运动。
4. 默认姿态遮挡、alpha 连续和像素零改动等数值结果，不能证明移动材料在视觉上完整。

## 失效的视觉通过证据

以下文件可用于复盘失败，但不得用于宣称本阶段视觉通过：

- `qa/upper-arm-sleeve-hidden-test-checkerboard.png`
- `qa/sleeve-moved-away.png`
- `qa/maximum-exposure-100.png`
- `qa/maximum-exposure-200.png`
- `qa/maximum-exposure-single-parameter-scan.gif`
- `qa/fk-41-textured-alpha-slow-preview.gif`
- `qa/six-combination-extremes.png`
- `qa/critical-epsilon-no-exposure.gif`
- `qa/maximum-exposure-grayscale.png`
- `qa/maximum-exposure-edge-enhanced.png`
- `qa/seam-flicker-edge-preview.gif`
- `qa/sleeve-hem-qa-context-safe-checkerboard.png`
- `qa/sleeve-hem-qa-context-purity-review.png`

## 仍然有效但范围受限的证据

- 输入哈希和 512×1086 精确裁切验证；
- 用户批准的 `V_upper_arm` 与袖口 alpha/混合所有权；
- `H_total`、`H_test` 的定义；
- 覆盖宽度下界与局部像素身份检查。

这些工程证据不抵消本次视觉失败。

## 继续所需支持

继续修复至少需要以下一种新的输入或授权：

1. 原画提供完整、独立的袖子分层（推荐）；或
2. 明确授权建立新的 Stage A 修订，对完整袖子隐藏区和完整袖下上臂材料进行本地受控补画，并重新走材料边界视觉门禁。

在获得上述支持前，不继续用更小的裁片、局部遮挡或有利姿态掩盖问题，也不进入 PSD、Cubism、Physics 或 Runtime。
