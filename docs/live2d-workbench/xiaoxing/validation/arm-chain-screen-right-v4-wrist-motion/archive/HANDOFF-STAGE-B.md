# 小星单臂验证：阶段 B 交接

## 已冻结结论

阶段 A V4 已通过工程检查和用户中文视觉审查。当前冻结范围仅为画面右侧的
`sleeve → upper_arm → forearm → hand`。

- 肩、肘、腕坐标以及 `L1/L2` 已锁定。
- 主路径为 41 个确定性 `0→1→0` 采样，另含 6 个组合极值。
- 三处接缝缺失像素均为 0，没有材料脱离、三角形翻折或退化。
- 手掌通过主动参数 `phiWristLocal` 绕固定腕点运动；不是逐帧图片，也不使用 Physics。
- 阶段 A 仍只证明纯色几何，不证明真实纹理、PSD、Cubism 或 Runtime。

## 阶段 B 唯一任务

在新的验证目录中，只补全“袖子下面的上臂隐藏纹理”。

权威输入：

1. `source/masters/front-color-source-exact-after-reset.png`
2. `source/masters/front-line-source-exact-after-reset.png`
3. 本归档的 `skeleton.json`
4. 本归档的 `materials/solid/upper_arm.png`
5. 本归档的 `masks/visible/upper_arm.png`
6. 本归档的 `samples/fk-41-samples.json`

执行边界：

- 原始可见上臂像素保持 1:1，不重绘、不缩放。
- 隐藏区由完整上臂范围减去可见上臂归属得到。
- 只允许在该隐藏区内进行本地受控图像编辑。
- 延续肤色、线宽、轮廓切线与光照，不得使用圆形色块、平均色、镜像或径向纹理。
- 不上传原图或工作区文件。

必须输出：

1. 上臂完整纹理层的棋盘格图。
2. 默认位置回组图。
3. 袖子移开后的隐藏材料图。
4. 41 样本慢速运动预览。
5. 灰度、边缘增强与接缝闪烁检查。

阶段 B 获得用户视觉批准之前，不制作正式 PSD，不进入 Cubism。
