# 小橘 Gate 4 关节、力矩与 Physics 规格

> 状态：Gate 3 尚未签收；本文先冻结建模规则，防止进入 Cubism 后凭感觉乱调。

## 官方约束依据

- Rotation Deformer 的父层旋转会带动其内部对象，标准角必须以素材当前姿态设为 `0°`：<https://docs.live2d.com/en/cubism-editor-manual/making-and-rotation-of-rotationdeformer/>
- 四肢应使用 Rotation Deformer → Rotation Deformer 的关节链；呼吸/耸肩可使用 Warp Deformer → Rotation Deformer：<https://docs.live2d.com/en/cubism-editor-manual/combintion-of-parent-child-relation/>
- 父级变化传递给子级，子级变化不反推父级：<https://docs.live2d.com/en/cubism-editor-manual/system-of-parent-child-relation/>
- 多段摆动物理的 pendulum 数必须与输出段匹配；同一输出参数来自多个组时总 Influence 不得超过 `100%`：<https://docs.live2d.com/en/cubism-editor-manual/physical-operation-setting/>
- 标准眼睛参数使用 `ParamEyeLOpen/R`（`0` 闭、`1` 开）与 `ParamEyeBallX/Y`（`-1..1`）：<https://docs.live2d.com/en/cubism-editor-manual/standard-parameter-list/>

## 文章复习后的控制分层

知乎文章《Live2D动画引擎的图形学原理及实现》给出的核心链路是：

```text
独立图层 → 三角网格 → 关节节点父子级联 → 顶点弹性 → Action Tracer
```

对应到小橘不能简化成“前肢三个重力矩”。正式控制分为四层：

1. `ArtMesh`：连续纹理表面，网格沿关节、眼睑、嘴角和毛边加密。
2. `Deformer hierarchy`：父节点变换逐级传给子节点，保持骨段长度和体积块。
3. `Active dynamics`：身体配重、肩胛、肩、肘、腕和爪接触由目标轨迹与逆动力学约束生成。
4. `Secondary dynamics`：耳尖、尾尖、胡须、胸毛、脸颊毛和身体回稳才交给 Cubism Physics。

文章中的“弹性节点”按离支点距离增加响应的思想，只用于软组织顶点权重；骨段端点和接触锁顶点必须保持刚性或高阻尼。

## 全身广义坐标与逆动力学

此前仅计算每条前肢三个刚体的屏幕平面重力矩，只能用于发现骨段跳变，不能作为完整控制器。正式控制状态为：

```text
q = [
  body_tx, body_ty, body_pitch, chest_breath, hip_shift,
  neck_pitch, head_yaw, head_pitch, head_roll,
  scapula_L/R, shoulder_L/R, elbow_L/R, wrist_L/R, paw_L/R,
  hind_load_L/R, tail_root, tail_mid, tail_tip,
  ear_root_L/R, ear_tip_L/R,
  eye_x, eye_y, eyelid_L/R, whisker_L/R
]
```

主动链的离线轨迹用约束逆动力学审计：

```text
M(q) q'' + C(q,q') q' + G(q)
  + J_contact(q)^T lambda
  + K_limit(q) + D q'
  = tau_active + tau_external
```

- `M(q)`：全身质量/惯量耦合，不再把每个关节当成互不影响的单摆。
- `C(q,q')q'`：父子链运动产生的速度耦合与离心/科氏项的二维近似。
- `G(q)`：头、胸腔、骨盆、四肢和尾根的重力矩。
- `J_contact^T lambda`：胸腹、后爪、星球和爪—脸接触的约束反力。
- `K_limit`：肘、腕、颈、耳根等生物关节极限的软约束。
- `Dq'`：关节阻尼，负责抑制无意义的高频振荡。

Cubism 不直接求解上述方程。离线审计器依据它生成可接受的角度、速度、加速度和接触区间；Cubism 参数关键形与 Motion 曲线再逼近这些轨迹。运行时只发送连续目标值，不逐帧切换姿态图。

## 广义坐标与广义作用通道

`35` 是连续广义坐标总数，不是 `35` 个旋转力矩。为避免把眼球位移、接触载荷和关节力矩混为一谈，控制合同按物理量重新分组：

| 物理量 | 数量 | 通道 |
| --- | ---: | --- |
| 主动旋转力矩 `tau_active` | 14 | 身体俯仰、颈俯仰、头 yaw/pitch/roll、肩 L/R、肘 L/R、腕 L/R、尾根、耳根 L/R |
| 被动弹性力矩 `tau_passive` | 6 | 尾中/尾尖、耳尖 L/R、胡须根 L/R |
| 主动线性力 `f_active` | 5 | 身体 X/Y、骨盆平移、肩胛滑动 L/R |
| 约束力/压力变量 `lambda` | 6 | 胸腹呼吸压力、腹部接触、后躯载荷 L/R、爪接触 L/R |
| 纯运动学控制 | 4 | 眼球 X/Y、眼睑开合 L/R |

因此可直接审计的旋转力矩共有 `20` 路，其中 `14` 路主动、`6` 路被动。接触反力不伪装成关节力矩，而是通过 `J_contact^T lambda` 回传到全身链；眼球和眼睑只做连续运动学控制。

每个主动执行器在进入 Cubism 前必须拥有独立的 `inertia/mass`、`effort_min/max`、`velocity_max`、`acceleration_max` 和阻尼参数。数值必须由最终分层材料的骨段长度、面积和支点测量得到，不能在 Gate 3 尚未通过时凭感觉写死。

| 通道 | 自由度 | 主动/次级 | 主要耦合与职责 |
| --- | ---: | --- | --- |
| Body translation/pitch | 3 | 主动 | 全身重心、胸腹与后肢支撑反力 |
| Chest/Belly volume | 2 | 主动+次级 | 呼吸相位、局部接触压缩、面积守恒 |
| Hip shift / hind load L/R | 3 | 主动 | 双前爪离地后的后躯配重 |
| Neck + Head yaw/pitch/roll | 4 | 主动 | 眼先头后、抬爪反向配重 |
| Scapula L/R | 2 | 主动 | 沿胸廓切向滑动，传递肩带力矩 |
| Shoulder L/R | 2 | 主动 | 抬臂主驱动，承担最大近端力矩 |
| Elbow L/R | 2 | 主动 | 控制力臂与遮眼弧线，禁止 IK 翻侧 |
| Wrist L/R | 2 | 主动 | 末端方向校正，不承担整条肢体抬升 |
| Paw contact L/R | 2 | 主动 | 眼眶接触锁、趾垫和面部毛发局部压缩 |
| Tail root/mid/tip | 3 | 根主动、末端次级 | 配重、滞后和衰减 |
| Ear root/tip L/R | 4 | 根主动、末端次级 | 注意方向、头动后随 |
| Eye X/Y + lids L/R | 4 | 主动 | Action Tracer、眼—头协同、眨眼 |
| Whisker L/R | 2 | 次级 | 口鼻与头动输入，根部稳定 |

正式规格包含 `35` 个连续广义坐标；它们不是同时自由摆动，也不等同于 `35` 个力矩，而是按父子层级、执行器类型、优先级和接触状态协同。

## 单关节阻尼模型

关节不做等角度、同时起停的机械插值。每条链按阻尼转动系统验收：

```text
I * theta'' + c * theta' + k * (theta - theta_target) = tau_external
I ~= m * L^2 / 3
```

- `I`：该段绕近端关节的转动惯量。
- `k`：向目标姿态回正的刚度。
- `c`：阻尼；控制过冲与收敛。
- 主动作由参数目标驱动；Physics 只叠加低幅跟随，不替代关键姿势。

该式只用于单通道局部调参；全身验收必须使用上一节的耦合方程，不能把所有关节各算各的后直接相加。

## 前肢旋转链

```text
Chest_Warp
└─ ScapulaSlide_Warp_L/R
   └─ Shoulder_Rot_L/R
      └─ UpperArm_Rot_L/R
         └─ Elbow_Rot_L/R
            └─ Forearm_Rot_L/R
               └─ Wrist_Rot_L/R
                  └─ Paw_Warp_L/R
```

| 段 | 相对质量 | 相对长度 | 阻尼比 | 目标延迟 | 最大二次摆幅 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 上臂 | 0.32 | 1.00 | 0.82 | 0 ms | 2.0° |
| 前臂 | 0.22 | 0.85 | 0.76 | 24 ms | 3.0° |
| 腕 | 0.10 | 0.42 | 0.70 | 42 ms | 4.0° |
| 爪 | 0.15 | 0.48 | 0.74 | 58 ms | 3.0° |

肩胛不是可省略的装饰节点。它的切向位移上限为胸腔宽度的 `6%`，超出时必须回到姿势/素材设计，不能继续拉长上臂。

- 主参数：`ParamForelegCoverL/R`，范围 `0..1`，`0=rest`，`1=cover`。
- 两侧默认相差 `18–35 ms`，避免镜像同步的机器人感。
- 肩先启动，肘随后，腕和爪最后收拢；回落顺序相反但不是时间倒放。
- 所有关节在五张 pose key 上建立关键形；中间帧必须由 Cubism 连续插值，不允许换 PNG。

## 尾巴、耳朵、胡须

| Physics 组 | 输入 | 输出链 | Pendulum | 阻尼倾向 | 备注 |
| --- | --- | --- | ---: | --- | --- |
| `Physics_Tail` | Body X 55%、Body Angle 45% | Tail Base/Mid/Tip | 3 | 0.55 | 越到尾尖延迟越大，尾根不可橡皮化 |
| `Physics_Ears` | Head Angle X/Y | Ear Base/Tip L/R | 2 | 0.82 | 仅 `1–2.5°`，左右可反向少量展开 |
| `Physics_Whiskers` | Head X、Body X | Whisker Root/Mid/Tip | 3 | 0.68 | 根部稳定，尖端轻摆；不穿过前肢 |
| `Physics_ForelegFollow` | Cover 参数速度 | Wrist/Paw secondary | 2 | 0.78 | 总 Influence ≤ 25%，不能改写主姿势 |

- Physics FPS：`60`。
- 同一输出参数的所有 Physics Influence 总和必须 `<=100%`。
- 左右对称物可使用 Reflect，但只反转方向，不复制完全相同的相位。

## 眨眼与目光

| 项目 | 规格 |
| --- | --- |
| `ParamEyeLOpen/R` | `0..1`；闭合 90–120 ms，停留 35–55 ms，开启 130–180 ms |
| 左右眼时差 | 常规眨眼 `0–18 ms`；低概率微表情 `20–45 ms` |
| `ParamEyeBallX` | 运行安全范围 `-0.65..0.65` |
| `ParamEyeBallY` | 运行安全范围 `-0.45..0.45` |
| 目光平滑 | 临界阻尼目标跟随，时间常数约 120 ms |
| 高光 | 跟随瞳孔位移的 `0.55–0.70`，不能与瞳孔完全锁死 |

- `Iris_L/R_Clean` 必须在隐藏瞳孔后没有任何黑色残留；否则直接判定重影失败。
- 眼睑要压住眼球边缘，不能靠缩放整只眼睛模拟闭眼。
- 遮眼动作中，眼睛仍继续低幅眨眼/目光参数，但被前爪 Draw Order 遮挡，避免姿态切换时突然跳相位。

## 验收

1. 逐段旋转时不露透明缝，关节毛覆盖层不滑离皮肤。
2. `rest -> cover -> rest` 慢放四分之一速时，肩、肘、腕、爪启动顺序清晰且无折线跳变。
3. 隐藏瞳孔 QA 不出现第二个黑瞳；目光极值不露出眼眶外透明区。
4. Physics 关闭时关键姿势仍正确；开启后只增加跟随与余韵。
5. 物理输出总 Influence、Deformer 越界和空 Deformer 均通过 Cubism 验证。
