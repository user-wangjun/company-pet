# V8-A1 前臂在整手之上的层序复验

## 工程结论

状态：`engineering_and_user_visual_pass`。

- 默认位置手链可见像素丢失：`0`；
- 隐藏手链后的腕部 `201 + 11 + 81`：最大缺口 `0`，断开 `0`，回程差 `0`；
- 肘×腕 `9×9`：最大缺口 `0`，断开 `0`；
- 全组合中手链被手部遮挡的像素：`0`；
- 独立二值遮罩重采样的诊断性子集漂移：最大
  `1 px`，位置
  `[[402, 533]]`；手链并非独立图层，因此正式
  判定使用同一前臂材料的注册标签变换；
- 骨长最大误差：`0.000000000000 px`；
- 慢扫 `61` 帧：最大缺口 `0`，断开 `0`，回程差 `0`；
- 手链未计入腕缝覆盖；
- 原 V7-C1 冻结文件未修改。

## 新合同

从后到前：

1. 整只手；
2. 正式前臂（包含手链）。

手链继续并入前臂，不新增运行层；整只手仍为一个材料，不使用 clipping，
不拆手根或手指。

## 视觉审查

请重点检查：

1. `qa/V8-A1-NEUTRAL-DRAW-ORDER-COMPARISON.png`：默认位置手链是否自然；
2. `qa/V8-A1-BRACELET-HIDDEN-SKIN-SEAM-THREE-ANGLES.png`：隐藏手链后是否仍无腕缝；
3. `qa/V8-A1-FOREARM-ABOVE-HAND-WRIST-SLOW-SCAN.gif`：运动中是否有闪缝或突起；
4. `qa/V8-A1-FOREARM-ABOVE-HAND-WRIST-SLOW-SCAN-SAMPLES.png`：慢扫等效抽帧；
5. `qa/V8-A1-FOREARM-ABOVE-HAND-FULL-CHAIN-3X3.png`：肘腕组合是否连续。

用户已批准上述视觉证据，当前允许恢复精确 `V_hand` 所有权工作。
