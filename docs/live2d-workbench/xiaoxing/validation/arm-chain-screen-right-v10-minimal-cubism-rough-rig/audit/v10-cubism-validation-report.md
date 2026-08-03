# V10 Cubism 工程粗绑收口报告

## 当前结论

V10 的工程收口、中文视觉批准和冻结授权均已完成，状态为
`frozen_v10_engineering_rough_rig_user_visual_approved`。

旧冻结清单生成后，CMO3 在保持 `80794` 字节不变的情况下由
`7d94374e…` 变为 `6b3c6d56…`，因此旧冻结被视为失效，未以“长度相同”
代替哈希一致性。当前 CMO3 已重新在真实 Cubism GUI 中完成最小复核，并按
审计 → 审批记录 → 冻结清单的依赖顺序重新绑定。

材料颜色纠错仍是已完成的工程事实。历史肘部视觉否决和旧证据均保留，
但不再把旧证据解释为当前通过。用户后来确认的静态肘部外观也仍保留为
历史视觉意见；本轮新增动态 taper 后，用户已重新明确批准整个 V10 工程粗绑。

当前成果只是一条单侧手臂的 Cubism 工程粗绑，不是正式纹理模型、正式 PSD、
完整 Cubism、Physics 或 Runtime 成品。

## 根因与实际修正

真实 Cubism GUI 诊断排除了透明缝、颜色污染、Draw Order、肘部旋转中心、
隐藏上臂缺失和红色控制器错觉。根因是：

1. 用户最后一次微调后的前臂根部第二轮廓行仍略微向内，保守测量一度达到
   5.25 px，超过 V7 的 4.373770766592578 px 上限；
2. `ParamV7ForearmRootTaper` 虽有三个关键形，但旧状态在 0、0.25、0.5、
   0.75、1 下没有可见变化，不能证明随弯曲量变化的肘根收束；
3. 旧 `D_ForearmRootTaper` 的 2x2 Bezier 网格无法把影响限制在
   `s <= 22 px`。

本轮只做了两项最小修正：

- 将前臂根部第二行外侧边界点向外移动 2 个屏幕像素，约 0.98 画布像素；
- 将现有 `D_ForearmRootTaper` 的 Bezier 分割从 2x2 改为 2x6，并只在
  最大关键形移动外侧顶部主控制点 10 个屏幕像素，约 4.202 画布像素。

没有新增 ArtMesh、Warp Deformer、补丁材料或 Draw Order 遮盖。

## 位移与影响范围

测量方法和可复核数据在
`audit/v10-final-closeout-audit.json`。

| 项目 | 最终保守结果 | 限制 | 结果 |
| --- | ---: | ---: | --- |
| 静态前臂根部最大边界位移 | 4.27 px | 4.373770766592578 px | 满足 |
| 静态轮廓影响范围 | 20.3 px | 22 px | 满足 |
| 动态 taper 最大控制位移 | 4.202 px | 4.373770766592578 px | 满足 |
| 动态 taper 影响范围 | 20.66129 px | 22 px | 满足 |

静态修正方向向外，动态 taper 方向向内，两者不是同向叠加；整个参数包络的
最大绝对边界位移仍为 4.27 px。

## Cubism 结构

四个独立 ArtMesh：

1. `01_sleeve`：5 顶点、4 三角形，Draw Order 400
2. `02_upper_arm_engineering`：5 顶点、4 三角形，Draw Order 100
3. `03_forearm_including_bracelet`：10 顶点、10 三角形，Draw Order 300
4. `04_whole_hand`：5 顶点、4 三角形，Draw Order 200

Deformer 层级：

```text
D_Shoulder
  01_sleeve
  02_upper_arm_engineering
  D_Elbow
    D_ForearmRootTaper
      03_forearm_including_bracelet
    D_Wrist
      04_whole_hand
```

四个网格的数值检查未发现退化三角形、翻折或越界顶点。真实 GUI 另行检查了
默认、各关节中间值/极值、taper 五档和组合极值，未见透明缝、脱节、
轮廓突跳或可见翻折。前臂长轴三角形仍偏细长，只适合作为工程粗绑。

## 连续运动与回零

`qa/V10-FINAL-CONTINUOUS-MOTION.mp4` 是旧哈希状态下的真实连续屏幕录制，
不是静态截图拼接，但不重新解释为当前哈希的直接证据。当前 CMO3 另行在真实
Cubism GUI 中实际执行了肩、肘、腕的默认/零值→最大→默认/零值，以及 taper
的 `0→1→0`，并覆盖保存当前极值和回零截图。

taper 的最终 0、25%、50%、75%、100%、回零截图来自真实 Cubism GUI。
固定画布裁切区域在 `0→1→0` 后：

- changed pixels：0
- maximum channel difference：0
- exact match：true

旧 `qa/cubism-v10-0-1-0.gif` 仅作为历史静态拼接证据保留，不再作为连续
运动证明。

## 冻结内容

以下内容保持不变：

- 512×1086 画布；
- 肩 `(332, 261)`、肘 `(355, 415)`、腕 `(393, 533)`；
- `L1 = 155.70806 px`、`L2 = 123.967738 px`；
- 四材料颜色、alpha、PSD 注册位置和纹理输入；
- 参数范围；
- Deformer 父子层级；
- Draw Order 100/200/300/400；
- Physics 关闭，未进行 Runtime 工作。

最终 CMO3 已在真实 Cubism Editor GUI 中打开并完成当前最小复核，复核过程
没有再次保存或改写工程。当前 SHA-256 为
`6b3c6d5682eec1a019dc7f14c6ebe185bb1cdeca24f3fcd3d93b502e8aa60bf0`，
长度为 `80794` 字节。

当前最小复核结果：

- 肩：默认→最大→默认，无透明缝、脱节或轮廓突跳；
- 肘：默认→最大→默认，无透明缝、脱节或轮廓突跳；
- 腕：`0→最大→0`，手腕连接稳定；
- taper：`0→1→0`，局部收束可见且回零确定；
- 默认与最终回零的固定画布裁切 changed pixels 为 `0`；
- 复核前后当前 CMO3 哈希保持不变。

## 当前证据

优先给用户查看：

- `qa/V10-FINAL-USER-REVIEW.zh-CN.png`
- `qa/V10-FINAL-ENGINEERING-QA.zh-CN.png`
- `qa/V10-FINAL-CONTINUOUS-MOTION.mp4`

逐项证据：

- `qa/cubism-31-final-forearm-artmesh-wireframe.png`
- `qa/cubism-32-taper-100-clean.png`
- `qa/cubism-33-taper-75-clean.png`
- `qa/cubism-34-taper-50-clean.png`
- `qa/cubism-35-taper-25-clean.png`
- `qa/cubism-36-taper-0-clean.png`
- `qa/cubism-37-taper-100-grid.png`
- `qa/cubism-38-taper-reset-clean.png`
- `qa/cubism-39-final-default-clean.png`
- `qa/cubism-40-shoulder-mid.png`
- `qa/cubism-41-shoulder-max.png`
- `qa/cubism-42-elbow-mid.png`
- `qa/cubism-43-elbow-max.png`
- `qa/cubism-44-wrist-mid.png`
- `qa/cubism-45-wrist-max.png`
- `qa/cubism-46-sleeve-moved-away-isolation.png`
- `qa/cubism-47-forearm-moved-away-isolation.png`
- `qa/cubism-48-hand-moved-away-isolation.png`
- `qa/cubism-49-final-hierarchy-parameters-draw-order.png`
- `audit/v10-cubism-return-determinism.json`
- `audit/v10-final-closeout-audit.json`

## 尚存限制与审批门

- `ParamV7ForearmRootTaper` 已有真实可见、连续的局部关键形；它与肘角度的
  派生关系仍是工程参数约定，Runtime 自动驱动不在本轮范围。
- 前臂、上臂、袖子和手部仍是工程材料与稀疏网格，不代表正式纹理质量。
- V10 freeze manifest 和整个 V10 的用户审批记录已生成并绑定当前 CMO3 与证据。

V10 工程粗绑已通过并冻结；正式纹理、正式 PSD、完整角色 Cubism、Physics
和 Runtime 仍未完成。
