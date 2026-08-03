# 小橘登录页 Live2D 模型

这个目录保存小橘登录页专用的 Live2D 规划、源文件、导出文件和接入证据。通用制作方法不放在本目录重复维护，由已安装的 `rig-live2d-pet` Skill 负责。

## 当前权威文档

- 通用产出流程：`rig-live2d-pet` Skill，负责 Gate、ArtMesh、节点树、弹性链、Action Tracer、模型边界、运行时和 QA。
- 小橘实施方案：`XIAOJU-LIVE2D-IMPLEMENTATION-PRD-v2.1.md`，负责三视图、猫科结构、星球接触、遮眼动作、登录状态和小橘专用证据。
- 机器可读状态：`blueprints/v2-artifact-disposition.json`。
- `LIVE2D-SKILL-BLUEPRINT-PRD.md` 与 `XIAOJU-LIVE2D-V2-RECOVERY-PRD.md` 为历史蓝图，不再单独授权制作。

当前状态为 planning-only；X1 尚未执行，Gate 3 未通过。未经当前 PRD 审批，不生成新图、不拆层、不导入 PSD、不操作 Cubism。

## 交互目标

- `idle`：轻微呼吸和眨眼；头部、眼球以阻尼方式跟随鼠标，移动幅度保持克制。
- `email`：头部向表单方向偏转，眼球看向输入位置，耳朵放松，嘴角保持开心。
- `password`：停止目光跟随，闭眼并抬起双爪遮住眼睛；离开密码框后平滑回到上一状态。
- 所有状态都使用参数连续插值，不使用整张图片切帧或突变。

## 历史参数草案（非权威）

下表只用于识别旧模型能力，不再作为新模型的参数预算。正式参数必须在 X1/X2 和 Layer-Mesh-Node 合同通过后重算。

| 参数 | Cubism ID | 范围 | 用途 |
| --- | --- | --- | --- |
| 头部 X | `ParamAngleX` | -30..30 | 横向跟随 |
| 头部 Y | `ParamAngleY` | -20..20 | 纵向跟随 |
| 头部 Z | `ParamAngleZ` | -10..10 | 邮箱状态偏头 |
| 眼球 X | `ParamEyeBallX` | -1..1 | 横向视线 |
| 眼球 Y | `ParamEyeBallY` | -1..1 | 纵向视线 |
| 左眼开合 | `ParamEyeLOpen` | 0..1 | 眨眼/捂眼 |
| 右眼开合 | `ParamEyeROpen` | 0..1 | 眨眼/捂眼 |
| 嘴形 | `ParamMouthForm` | -1..1 | 开心表情 |
| 左爪遮眼 | `ParamArmLCover` | 0..1 | 密码状态 |
| 右爪遮眼 | `ParamArmRCover` | 0..1 | 密码状态 |
| 呼吸 | `ParamBreath` | 0..1 | 待机呼吸 |

不再预先承诺“30 个参数以内”或单一 2048px 图集；参数数量、图集和模型文件边界由完整拆层、网格合同和 X8 运行时试片决定。

## 目录约定

- `source/`：三视图裁切、分层 PSD 和制作辅助文件。
- `editor/`：Cubism Editor 的 `.cmo3` 源模型。
- `runtime/`：网页运行所需的 `.moc3`、`.model3.json`、纹理和动作文件。

网页侧的状态目标值由 `src/account/accountPetParameters.ts` 管理。
