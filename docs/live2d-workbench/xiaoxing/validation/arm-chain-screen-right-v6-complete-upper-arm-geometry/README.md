# V6 完整上臂纯色几何门禁

## 当前状态

本目录只验证画面右侧、角色左侧的完整上臂纯色几何。完整袖子保持外部冻结引用，
不在本目录复制或修改。旧 V5 局部 `H_test` 纹理、`12/16.75 px` 覆盖数字及其运动
预览均不作为本门禁输入。

**当前 V6 门禁已关闭并冻结。** 用户已重新批准肘部重叠精修后的当前候选；此前
失效的批准记录继续保留为历史证据，不覆盖、不删除。当前批准和冻结入口为：

- `audit/user-visual-approval-complete-upper-arm-geometry-v2-2026-07-25.json`；
- `audit/v6-complete-upper-arm-geometry-freeze-manifest-2026-07-25.json`；
- `audit/temporary-forearm-minimum-envelope-contract-2026-07-25.json`；
- `audit/shoulder-18-pixel-conditional-exception-2026-07-25.json`。

当前结构合同为：

- 上臂包含自然的肩侧闭合端和肘侧隐藏末端；
- 前臂根部使用明确标记的临时纯色覆盖参考；
- 前臂绘制在上臂之上；
- 不建立独立肘关节材料，不使用 Glue；
- 任何纹理、PSD、Cubism、Physics 和 Runtime 工作均未授权。

上一版候选已因“轮廓有偏差、不符合体态”被用户否决。本版已回到同一几何门禁，
将肩下最大宽度从约 `47 px` 收回到约 `34 px`，沿冻结肩肘骨轴连续收束至原图
可见肘前约 `30 px`；锁定可见像素、骨点、骨长和动作范围均未改动。

本次肘部精修进一步确认，弯曲时的局部鼓包来自冻结纯色前臂原型的圆钝近端被直接
当作临时 QA 覆盖。V4 归档未修改；仅在本目录的临时前臂代理中，收回外弯侧圆钝
近端，并把必要覆盖集中在内弯尖刺实际出现的小区域，避免鼓包和内弯尖刺。该代理
仍不是正式前臂材料。

最新复审指出袖口下方右侧仍有局部凸出。本轮已消除临时前臂右侧宽度峰值，并同步
收窄其后方的隐藏上臂末端；锁定的 544 个可见上臂像素保持不变。

## 产物分组

| 分组 | 入口 | 说明 |
| --- | --- | --- |
| 设计合同 | `design/complete-upper-arm-geometry-contract.json` | 冻结骨架、上臂轮廓和临时前臂根部责任 |
| 几何产物 | `masks/`、`materials/geometry/` | 完整上臂遮罩、纯色参考和临时覆盖参考 |
| 运动样本 | `samples/fk-41-and-continuous-elbow-scan.json` | 41 主路径、6 极值和连续肘角加密 |
| 视觉证据 | `qa/` | 默认、移开、放大、极值、慢扫和突出精修 |
| 审计与历史 | `audit/` | 工程报告、旧批准及其失效记录 |
| 可重建工具 | `tools/build_v6_complete_upper_arm_geometry.py` | 唯一生成入口 |

## 分区

- `Z1`：肩侧隐藏延伸；
- `Z2`：用户已批准的 544 个可见上臂像素；
- `Z3`：肘侧隐藏延伸；
- `Z4`：肘部双向覆盖责任区，不是独立材料。

## 证据入口

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

数值结论见 `audit/complete-upper-arm-geometry-report.json`，中文审查说明见
`audit/complete-upper-arm-geometry-report.zh-CN.md`。

## 下一门禁与停止线

下一最早门禁是 **正式前臂纯色几何**。正式前臂必须包含已冻结的临时根部最低
包络，并使用真实前臂几何重新验证肘部双向覆盖。

正式前臂纯色几何通过前，不制作上臂隐藏纹理。当前批准不包含上臂纹理、正式
前臂纹理、PSD、Cubism、Physics 或 Runtime。
