# 小星 Live2D 当前范围

更新时间：2026-08-12

## 当前授权

- 角色显示名：小星。
- 当前制作对象：正面视图的画面左侧手臂，即角色解剖学右臂；内部记录必须同时写明
  `screenSide=left` 与 `anatomicalSide=right`，不得只写含混的 `left`。
- 当前任务：按新的“物理身体 → 线稿语义 → 平色几何 → 多姿态门禁 → 锁定纹理 →
  网格和动作 → 二次物理 → Runtime”流程重新制作该侧手臂。
- 当前状态：`R2_APPROVED_CURRENT_SCOPE / R2-GATE_APPROVED`。
- 当前权威执行文档：`LEFT-REBUILD-WORKPLAN.md`。
- 当前不是正式 pet：不注册、不加载、不发布，不修改 `public/pets/index.json`。

## 实现边界

- 权威中间格式为同坐标 JSON 合同与透明 PNG；Photoshop 和 Cubism 均不是前置依赖。
- 首选目标是可被自定义 Pixi/WebGL Runtime 消费的独立 2D 关节角色数据；是否额外导出
  PSD/Cubism 包，留到几何、纹理、主动动作全部通过后再决定。
- 平色色块只用于证明几何、像素所有权和拼装，不是最终材料，也不能替代纹理成品。
- 当前只重制 `sleeve → upper_arm → forearm → hand` 链及独立 `bracelet`；不扩展到
  另一侧手臂、全身、表情或平台动作映射。

## 权威输入

- `source/xiaoxing-three-view-line.png`
- `source/xiaoxing-three-view-color.png`
- `source/masters/front-line-source-exact-after-reset.png`
- `source/masters/front-color-source-exact-after-reset.png`

阶段一必须重新核对这些文件的尺寸与 SHA-256。线稿决定可见结构和语义边界；彩稿决定
身份、颜色和材质参照；三视图与统一身体模型共同约束隐藏补全。

## 旧链边界

- `validation/arm-chain-screen-left-v12-*` 至 `arm-chain-screen-left-v38-*` 全部保留原样，
  不删除、不覆盖、不就地修复。
- 旧用户批准仍是对应旧工件的历史事实，但不会自动批准本次新分支。
- V25 骨架、V30–V36 冻结几何可作为比较证据，不是新几何的权威输入。
- V37/V38 暴露的腕部断口、皮肤 RGB 污染和手链混入前臂 alpha 是必须纳入的新回归用例。
- V38 最终状态仍为 `rejected_by_user_visual_review`；数值通过不能替代用户视觉通过。

## 当前门禁

R1 与 R2 已分别完成工程门禁和用户视觉批准；R2 正式材料已提升并冻结。当前停止在
`R2_FORMAL_PROMOTED / R3_READY_NOT_STARTED`：R3 尚未获得新的执行授权，历史 R3 失败候选
只作只读回归证据。R2 批准仅覆盖当前平色几何与 layer-only 拼装范围，不自动授权 R3、
纹理、PSD、ArtMesh、节点、参数、动作、Physics、Cubism 或 Runtime。

## 暂不纳入

- 另一侧手臂或全身材料生产。
- 正式桌宠动作、对话、音效与人格设定。
- `pet.json`、spritesheet 或平台注册。
- Photoshop/Cubism 适配器及正式模型导出。
- ArtMesh、节点、参数、Physics 和 Runtime 实现。
