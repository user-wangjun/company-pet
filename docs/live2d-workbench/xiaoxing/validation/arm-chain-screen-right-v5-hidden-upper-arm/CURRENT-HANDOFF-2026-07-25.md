# 小星单臂验证：当前权威交接

日期：2026-07-26

## 当前结论

当前最后一个真实通过门禁是 **V9 袖子下面的上臂肩侧隐藏真实纹理证明，
批准候选 B**。

已冻结通过：

1. V4 单臂纯色 FK 参考；
2. 画面右侧完整袖子几何与真实纹理；
3. V6 完整上臂纯色几何；
4. V7-C1 正式前臂纯色几何；
5. V8-A 精确 `V_hand` 可见像素所有权；
6. V8-B1 正式完整 `M_hand` 纯色几何；
7. V8-C 真实手部腕部全域；
8. V9 `R_shoulder_hidden` 肩侧隐藏真实纹理候选 B。

单臂阶段 A 的 `sleeve → upper_arm → production_forearm → whole_hand`
四材料几何链已完成并冻结。

用户对 V8-B1/V8-C 给出的是**带保留意见的视觉通过**并明确授权冻结：当前结果
足以关闭本门禁，但不得解释为无保留的高级视觉品质认可，也不授权擅自加粗、
改形或重做冻结腕部与手部几何。

V9 只关闭 `4465 px` 肩侧隐藏纹理证明，不代表完整上臂纹理完成；其余
`349 px` 上臂隐藏区域仍未进入纹理范围。用户批准 V9 允许记录冻结和讨论
最小 Cubism 草绑，但不等于授权实际制作 PSD、ArtMesh、Cubism、Physics
或 Runtime。

## 新对话最小必读

按顺序只读以下当前冻结入口：

1. 本文档；
2. `../arm-chain-screen-right-v9-upper-arm-hidden-texture-proof/audit/v9-upper-arm-hidden-texture-freeze-manifest-2026-07-26.json`；
3. `../arm-chain-screen-right-v9-upper-arm-hidden-texture-proof/audit/v9-candidate-b-user-visual-approval-2026-07-26.json`；
4. `../arm-chain-screen-right-v7-production-forearm-geometry/CURRENT-V7-COMPLETION-AUDIT-2026-07-26.md`；
5. `../arm-chain-screen-right-v7-production-forearm-geometry/v7c1-elbow-seam-fairing/audit/v7-production-forearm-geometry-freeze-manifest-2026-07-26.json`；
6. `../arm-chain-screen-right-v8-formal-hand-geometry/audit/v8a-final-freeze-manifest-2026-07-26.json`；
7. `../arm-chain-screen-right-v8-formal-hand-geometry/v8b1-complete-hand-geometry/audit/v8b1-v8c-freeze-manifest-2026-07-26.json`；
8. `../arm-chain-screen-right-v8-formal-hand-geometry/v8b1-complete-hand-geometry/audit/V8-B1-V8-C-FINAL-COMPLETION-AUDIT-2026-07-26.zh-CN.md`；
9. `../arm-chain-screen-right-v8-formal-hand-geometry/v8b1-complete-hand-geometry/audit/v8b1-v8c-user-visual-approval-and-freeze-authorization-2026-07-26.json`。

只有出现具体校验差异或合同争议时，才读取 V7-A、V7-B、旧否决记录或详细
历史报告；不要每轮全量读取历史文档。

## 冻结状态

### V4 单臂 FK

- 肩、肘、腕坐标和固定 `L1/L2` 已锁定；
- 肘参数和主动腕参数已存在；
- 41 个 `0→1→0` 样本及组合极值通过；
- 无骨长漂移、透明缝、部件断开或原型三角形翻折；
- 无 Physics。

V4 只证明自建纯色 FK，不证明 Cubism。

### 完整袖子

- 几何与真实纹理已冻结；
- 单连通，隐藏袖筒完整；
- 冻结清单 16 项一致；
- 不得修改或重新生成。

### V6 完整上臂纯色几何

- 用户批准并冻结；
- 冻结清单 22 项一致；
- 可见源像素保持不变；
- 单连通、无孔；
- 肩侧 18 个条件像素仍需在未来衣身或头发正式分层后重开。

V6 文件保持冻结且未被修改。V6 曾使用的临时静态前臂根部包络后来被证明与
正式像素所有权不相容；该依赖现已由 V7-C1 主动肘根结果合同替代，但不回写
或改动 V6。

### V7-C1 正式前臂纯色几何

- 正式前臂 `3855 px`，连通分量 `1`，孔洞 `0`；
- F1/F2/F3/F4 互斥且重建差 `0`；F5 仅为腕部 QA 责任区；
- 手链并入前臂，不设独立运行层，也不得承担腕缝覆盖；
- 用户批准双侧 `10 px` 肘根渐缩圆滑修正；
- 用户批准 `35 px` 中性边界例外；
- 保留 `3721` 个源像素，RGB 差 `0`；
- 肘部 `41 + 6 + 241`：缺口、断开、回程差和骨长误差均为 `0`；
- 腕部 `201 + 11 + 81`：缺口、断开和回程差均为 `0`；
- 肘×腕 `9×9` 组合域缺口 `0`；
- 全姿态前臂断裂 `0`；
- 确定性重新生成差异 `0`；
- 已获得用户视觉批准并冻结。

V7-C1 已在隔离临时副本中完成独立复验：冻结工具要求 `17/17` 通过，
V4 `17/17`、完整袖子 `16/16`、V6 `22/22`，29 个冻结文件逐项差异 `0`；
肘部与腕部各抽查 61 帧慢扫中的 12 帧，未见突出、闪缝、缺口或断开。
复验未写入 V7 冻结目录，临时副本已清理。

双侧 `10 px` 渐缩与 `35 px` 例外是用户批准的 V7-C1 条件；改变任一条件都会
重开 V7-C1。

### V8-A 精确可见手部像素所有权

- 最终 `V_hand` 锁定为 `2629 px`，未决像素 `0`；
- 其中稳定源像素 `2586 px`；
- 用户审查并批准 `66 px` 混合 AA：纳入 `43 px`，排除 `23 px`；
- 可见手部与袖子、上臂、前臂、手链的所有权交集均为 `0`；
- 腕缝责任区未归属像素 `0`，指缝背景误填 `0`；
- 源坐标差 `0`，源 RGB 差 `0`；
- `389 px` 包络未分类像素 `0`，局部坐标往返差 `0`；
- 层序锁定为“前臂含手链位于整手之上”；
- 手链仍并入前臂，不设独立运行层；
- 用户已明确视觉批准，确定性重新生成差异 `0`。

V8-A 门禁当时只冻结可见像素所有权；该门禁本身不证明完整手部连通性、孔洞
或真实手部腕部全域。上述后续证明现由已冻结的 V8-B1/V8-C 提供。

### V8-B1 正式完整手部与 V8-C 真实腕部

- 正式 `M_hand` 为 `2752 px`；
- H1 `2629 px`、H2 `81 px`、H3 `42 px`，三者责任交集均为 `0`；
- H1 坐标差 `0`、RGB 差 `0`；
- 完整包含冻结 `389 px` 包络，缺失 `0`；
- 单连通，孔洞 `0`，指缝误填 `0`；
- H3 位于腕根许可区内，超区 `0`，中性位置未被前臂皮肤遮挡的像素 `0`；
- 默认回组锁定可见坐标差 `0`，人物轮廓外新增像素 `0`；
- 腕部 `201 + 11 + 81`：最大缺口 `0`、断开 `0`、回程差 `0`；
- 肘×腕 `9×9`：最大缺口 `0`、断开 `0`、未批准碰撞 `0`；
- 手链隐藏后皮肤覆盖缺口 `0`，手链未计入皮肤覆盖；
- 原型三角形翻折 `0`，骨长误差在 `0.01 px` 内；
- 确定性重新生成差异 `0`；
- 用户带保留意见视觉通过并明确授权冻结。

冻结清单：

`../arm-chain-screen-right-v8-formal-hand-geometry/v8b1-complete-hand-geometry/audit/v8b1-v8c-freeze-manifest-2026-07-26.json`

冻结清单 SHA-256：

`6c256bc1037ada098a1dd3daaa4a9bbe3fac807c532f9716cbf7b71eb0614e4c`

### V9 袖下上臂肩侧隐藏真实纹理

- 本轮唯一补画区 `R_shoulder_hidden` 为 `4465 px`；
- 它严格属于 `M_upper \ V_upper`，肘侧纳入像素 `0`；
- 其余 `349 px` 上臂隐藏区域仍是未进入本轮的 QA 占位，不得当作真实纹理；
- 使用本地确定性骨骼坐标低阶颜色场延拓、可见皮肤邻域统计和低幅非周期纹理；
- `V_upper` `544 px` 的坐标、RGB、alpha 差均为 `0`；
- `M_upper` 几何差、许可区外补画和 alpha 越界均为 `0`；
- 41 样本首尾差 `0`，确定性完整重生差异 `0`；
- 用户最新明确批准候选 B，并授权冻结本门禁；
- 本批准只覆盖肩侧隐藏纹理证明，不覆盖完整上臂、前臂或手部纹理。

冻结清单：

`../arm-chain-screen-right-v9-upper-arm-hidden-texture-proof/audit/v9-upper-arm-hidden-texture-freeze-manifest-2026-07-26.json`

冻结清单 SHA-256：

`6c22bce8369b7314e85af8f2ddc41236fa6365efcb30da320beda15aeaba6f4c`

## 389 px 临时手根合同

V7 腕部验证使用的临时手根最低包络 `E_hand` 已由正式 `M_hand` 静态包含，
并已由 V8-C 使用真实手部重跑全域。

- `389 px`，单连通，孔洞 `0`；
- 使用冻结腕点 `[393, 533]` 和冻结手局部坐标；
- 中性位置完全位于原始手部轮廓内；
- 当前 Draw Order 是前臂含手链位于整手之上；
- 正式完整手部材料已静态包含该包络：
  `temporary_hand_envelope ⊆ M_hand`；
- 其中 `308 px` 已归属锁定 `V_hand`；其余 `81 px` 是前臂/手链可见所有权，
  允许由未来完整手部材料在后方静态包含；
- 手链不得计入腕缝覆盖；
- V8-C 已使用真实手部重跑腕部全域并通过；
- 若未来修改正式手部使其不再包含该包络，V7/V8 腕部结论自动失效。

静态局部坐标包含与腕参数全域运动覆盖两个独立要求均已通过。

## 当前阶段结论与下一门禁

单臂阶段 A 四材料几何链完成并冻结：

```text
sleeve
→ upper_arm
→ production_forearm_including_bracelet
→ whole_hand
```

V9 肩侧隐藏纹理证明已经关闭。下一步只允许讨论最小 Cubism 草绑的范围和
证据门禁；在用户另行明确授权前，不制作 PSD、ArtMesh 或 Cubism 文件。

## 当前禁止项

- 不修改 V4、完整袖子、V6 或 V7-C1 冻结产物；
- 不修改 V8-A、V8-B1 或 V8-C 冻结产物；
- 不修改 V9 候选 B、`R_shoulder_hidden` 或其冻结证据；
- 不把 V9 扩张为完整上臂、前臂或手部纹理；
- 不制作 PSD；
- 不进入 ArtMesh、Cubism、Physics 或 Runtime；
- 不拆分手指；
- 不创建局部反向 Draw Order、clipping 或独立腕部材料；
- 不使用手链遮住腕缝；
- 不因 V6 曾有合同冲突就预设 V8 必然需要复杂拆层。
