# 小星单臂：阶段 B 中文报告

## 结论

**用户视觉否决，阶段 B 失败并停止。**

本轮产物只能称为“袖下近端上臂纹理方法验证”，不能称为完整上臂材料。

## 已完成范围

- 已批准 `V_upper_arm` 与袖口混合带所有权。
- `H_total` 与 `H_test` 已分离；本轮 `H_test` 为 `709` 像素。
- `w_required=5 px`，`w_final=12 px`，冻结材料最小连续承载 `16.75 px`。
- 只在 `H_test` 内生成纹理；可见像素逐像素不变，`H_test` 外零改动。
- 纹理使用上臂局部坐标中的纵向/横向渐变、袖口阴影衰减和原稿侧边线色延续。
- 未使用平均色块、镜像、径向纹理、重复克隆、外部生成服务或素材上传。
- 用户指出旧运动预览把头发、衣身等非袖子源像素烘焙进袖子裁片；该视觉 QA 已正式作废。
- 新预览只使用语义纯度过滤后的局部袖口 QA 条带；它不是完整袖子材料。

## 工程结果

- 可见 RGB 差异像素：`0`
- `H_test` 外 RGBA 差异像素：`0`
- 默认局部回组差异像素：`0`
- 41 样本最大接缝缺失像素：`0`
- 6 个组合极值最大接缝缺失像素：`0`
- 41 样本责任集最大软边像素：`1`（预先容差上限 `1`）
- 责任集最低合成 alpha：`198`（低于 `16` 才计透明缺口）
- `H_test` 意外强露出像素（alpha≥128）：`0`
- 0→1→0 返回是否逐像素一致：`是`

冻结参数中袖子和上臂相对变换恒定，因此不存在“新露出临界参数”。`±0.05°` 动画用于检查休止点附近的栅格稳定性，不代表新增动作参数。

## 视觉证据状态

用户已确认上臂候选断开、袖子上下文断开且呈裁剪状。以下文件仅保留为失败复盘证据，不得用于宣称视觉通过。

1. `qa/upper-arm-sleeve-hidden-test-checkerboard.png`
2. `qa/sleeve-moved-away.png`
3. `qa/maximum-exposure-100.png`
4. `qa/maximum-exposure-200.png`
5. `qa/maximum-exposure-single-parameter-scan.gif`
6. `qa/fk-41-textured-alpha-slow-preview.gif`
7. `qa/six-combination-extremes.png`
8. `qa/critical-epsilon-no-exposure.gif`
9. `qa/maximum-exposure-grayscale.png`
10. `qa/maximum-exposure-edge-enhanced.png`
11. `qa/seam-flicker-edge-preview.gif`
12. `qa/sleeve-hem-qa-context-safe-checkerboard.png`
13. `qa/sleeve-hem-qa-context-purity-review.png`

## 明确未完成

- 更深肩侧隐藏纹理；
- 肘部 joint disk、前臂根部和姿势相关肘褶；
- 正式 PSD；
- Cubism ArtMesh、Deformer、参数、Physics 或 Runtime；
- premultiplied alpha、atlas、UV padding 和 mipmap 验证。

## 当前门禁

视觉门禁失败并停止。继续需要原画提供完整独立袖子分层，或明确授权建立新的 Stage A 修订，对完整袖子隐藏区与完整袖下上臂材料进行本地受控补画并重新审批。
