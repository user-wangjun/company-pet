# V6 完整上臂纯色几何工程报告

## 结论

此前视觉批准已因用户要求复核弯曲突出而失效，当前状态为 **肘部重叠精修并等待新视觉审查**。本报告不批准纹理、PSD、Cubism、Physics 或 Runtime。

- 此前批准记录保留为历史证据；`audit/geometry-approval-invalidation-2026-07-25.json` 已将其标记为失效。

上一版候选已因轮廓和体态对齐问题被用户否决。本版缩小肩下异常膨胀，消除中段
腰折，并让肘侧隐藏端在不外扩的前提下闭合；所有冻结锚点保持不变。

## 锁定与像素

- 肩点 `(332.0, 261.0)`、肘点 `(355.0, 415.0)`、`L1=155.708060px` 均未改变。
- Z2 可见上臂像素：`544`，坐标差异 `0`，RGB 差异像素
  `0`。
- 完整上臂遮罩连通分量：
  `1`，孔洞：
  `0`。

## 肩侧覆盖

- 使用已冻结完整袖子的实际纹理 alpha，阈值 `16`。
- Z1 落在阈值外的像素：
  `18`。
- Z1 肩端子区在袖子 alpha 内的 Chebyshev 静态余量下界：
  `8px`。
- 阈值外像素均位于冻结袖口/皮肤边界约 3px 内，未并入 544 个锁定 Z2
  像素，也不声明为纹理；它们作为扁平母图边界依赖交由默认回组图人工复核。
- 袖子和上臂共享冻结肩部变换，因此该相对覆盖在 FK 连续域内不滑移。
- 衣身和头发仍是扁平母图依赖，正式分层后必须重算，当前不是 PSD/Cubism 证明。

## 肘侧双向责任

- 4× 超采样；41 个主路径样本；6 个组合极值；连续 θ2 域 241 点加密。
- 上臂核心运动延伸需求：
  `8px`；
  加抗锯齿、未来纹理 alpha 和 Cubism 插值余量后：
  `15px`。
- 当前上臂末端越过冻结肘线：
  `17.302px`。
- 前臂根部只使用
  `23.537px`
  临时纯色覆盖参考，不是正式材料。
- 最大责任区透明缺口：
  `0`；断开样本：
  `0`。

## 弯曲突出精修

- 突出来源是冻结纯色前臂原型的圆钝近端被直接用于临时 QA；V4 冻结归档本身未改。
- 当前只在临时 QA 代理中替换前臂局部 `s<22px`，外弯侧渐宽、内弯侧使用更长
  的隐藏延伸。
- 外弯侧相对杆身的最大近端宽度超出：
  `0.000px`；宽度剖面连续检查：
  `True`。
- 4× 连续扫描中的内弯侧异常上臂暴露像素最大值：
  `0`。
- `qa/gate-10-elbow-protrusion-refinement.png` 同时展示所有权颜色和同肤色外轮廓。

## 轮廓检查

- 已记录骨轴宽度剖面、连续曲线切线变化和两端圆弧拟合风险。
- 圆弧拟合仅作为人工复核提示，不自动替代人体结构视觉判断。
- 未使用“平均宽度长条 + 圆形补丁”或独立肘圆盘。

## 必看视觉证据

1. `qa/gate-0-body-alignment-review.png`
2. `qa/gate-1-complete-upper-arm-isolated.png`
3. `qa/gate-2-default-recomposition.png`
4. `qa/gate-3-sleeve-moved-away.png`
5. `qa/gate-4-forearm-moved-away.png`
6. `qa/gate-5-shoulder-zoom.png`
7. `qa/gate-6-elbow-zoom.png`
8. `qa/gate-7-six-combination-extremes.png`
9. `qa/gate-8-elbow-single-parameter-scan.gif`
10. `qa/gate-9-displaced-parts-integrity.png`
11. `qa/gate-10-elbow-protrusion-refinement.png`

数值通过不能代替用户视觉批准。在明确批准前停止。
