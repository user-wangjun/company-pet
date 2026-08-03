# 小星 Live2D 拆件蓝图（Gate 2C 草案）

> 此文件目前只用于记录候选结构。Gate 2A 统一身体与 Gate 2B 姿势预检通过前，
> 不得据此生成正式部件、网格或节点。

## 参考图

| 角色 | 文件 | 权威范围 |
| --- | --- | --- |
| 身份与配色 | `../source/xiaoxing-three-view-color.png` | 发色、肤色、服装、饰品、整体气质 |
| 结构与边界 | `../source/xiaoxing-three-view-line.png` | 三视图轮廓、发束、衣服与肢体边界 |
| 默认正面构图 | 待建立 | 必须从审核后的统一身体派生 |
| 隐藏结构 | 待建立 | 后脑、耳后、颈肩、袖内、裙腰等 |

## 候选层级

```text
Xiaoxing_Root
└─ Body_Global
   ├─ Torso
   │  ├─ Neck
   │  ├─ TShirt
   │  ├─ Shirt_Print
   │  ├─ Skirt
   │  ├─ Arm_L
   │  │  ├─ UpperArm_L
   │  │  ├─ Forearm_L
   │  │  ├─ Hand_L
   │  │  └─ Bracelet_L
   │  └─ Arm_R
   │     ├─ UpperArm_R
   │     ├─ Forearm_R
   │     ├─ Hand_R
   │     └─ Bracelet_R
   ├─ Leg_L
   │  ├─ Thigh_L
   │  ├─ LowerLeg_L
   │  ├─ Sock_L
   │  └─ Shoe_L
   ├─ Leg_R
   │  ├─ Thigh_R
   │  ├─ LowerLeg_R
   │  ├─ Sock_R
   │  └─ Shoe_R
   └─ Head
      ├─ BackHair
      ├─ FaceBase
      ├─ Ear_L
      ├─ Ear_R
      ├─ Brow_L / Brow_R
      ├─ EyeWhite_L / EyeWhite_R
      ├─ Iris_L / Iris_R
      ├─ Pupil_L / Pupil_R
      ├─ Highlight_L / Highlight_R
      ├─ UpperLid_L / UpperLid_R
      ├─ LowerLid_L / LowerLid_R
      ├─ Nose
      ├─ Mouth
      ├─ FrontHair
      ├─ SideHair_L / SideHair_R
      └─ HairStrand_Groups
```

## 首批隐藏补画候选

| 区域 | 原因 | 当前证据 |
| --- | --- | --- |
| 完整后脑与头皮 | 后发、前发移动会暴露 | 正侧背三视图 |
| 完整双耳和耳后脸侧 | 转头与侧发摆动会暴露 | 正面与侧面 |
| 完整颈部、肩根与衣领内侧 | 长发和宽松领口遮挡 | 三视图 |
| 双侧完整上臂根部 | 袖子遮住肩臂连接 | 正面与侧面 |
| T 恤下的躯干体积 | 衣服摆动不能代替身体 | 三视图轮廓 |
| 裙腰与上腿根部 | T 恤下摆和裙子遮挡 | 正侧背三视图 |

## 当前门禁

- [x] 保存原始参考图
- [x] 完成自动输入审计
- [x] 完成人工可用性初审
- [x] 用户确认 Gate 1 / Gate 2A 结论
- [x] 三视图身体地标叠加
- [x] 统一骨架、体积与左右身份合同
- [x] 41 样本待机支撑工程预检
- [x] 用户确认 Gate 2B 动作视觉
- [ ] 正面生产母稿方案获用户批准
