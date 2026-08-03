# 小橘星球场景 Gate 2 拆层蓝图

> 状态：用户已通过 Gate 2。此蓝图描述最终完整素材；Gate 3 正按此责任表制作。

## 参考

| 角色 | 文件 |
| --- | --- |
| 身份/完整解剖 | `../../three-view-preview.png` |
| Rest 构图 | `../planet-scene-source/pose-keys-v3/00-rest.png` |
| 遮眼终点 | `../planet-scene-source/pose-keys-v3/04-cover.png` |
| 区域标注 | `gate2-layer-map.svg` |

## 场景与星球

| ID | 内容 | 隐藏补全/形变要求 |
| --- | --- | --- |
| `BG_Stars` | 星空 | 静态或极低幅视差 |
| `Planet_BackGlow` | 大气后光 | 独立透明层，低幅呼吸 |
| `Planet_Base` | 完整星球主体 | 补齐猫身后的球面，独立 Warp |
| `Planet_SurfaceDetail` | 蓝绿纹理 | 与主体共同变形但保持独立纹理控制 |
| `Planet_FrontRim` | 前景白色边缘 | 负责猫身和肢体遮挡，不包含背景 |
| `Planet_Highlight` | 星球高光 | 独立亮度/位置微调 |
| `Planet_ContactShadow` | 猫与星球接触阴影 | 随身体重心低幅变化 |

## 完整小橘

| 区域 | 必须拆分的最终层 | 隐藏补全责任 |
| --- | --- | --- |
| 躯干 | `Body_Base`, `Chest_Fur`, `Belly_Fill`, `RearBody_Base`, `Neck_Fill` | 补全星球与前肢后的胸腹、肩窝、腰背 |
| 后肢 | `Hip_L/R`, `HindLeg_L/R`, `HindPaw_L/R` | 依据三视图补全完整坐姿和接地轮廓 |
| 头脸 | `Head_Base`, `Cheek_L/R`, `Muzzle`, `Nose`, `Mouth_Line`, `Mouth_Inside`, `Chin_Fur` | 补全眼睛、耳根和前肢遮住的脸部纹理 |
| 眼睛 | 每侧 `EyeWhite`, `Iris`, `Pupil`, `Highlight`, `UpperLid`, `LowerLid`, `EyeSocket_Fur` | 完整闭眼纹理与眼眶安全边界 |
| 耳朵 | 每侧 `EarBack`, `EarInner`, `EarFrontFur`, `EarTipFur` | 补全耳根与头部连接 |
| 胡须 | `Whisker_L/R` | 根部跟随口鼻，尖端保留透明延展 |
| 前肢 | 每侧 `Shoulder_Fill`, `UpperArm`, `Elbow_Fur`, `Forearm`, `Wrist_Fur`, `Paw` | 从肩窝到爪完整；只保留一套视觉素材 |
| 尾巴 | `Tail_Base`, `Tail_Mid`, `Tail_Tip` | 从后躯内部补全尾根，允许多级 Deformer |

## Draw Order（后到前）

```text
BG_Stars
Planet_BackGlow
Planet_Base + Planet_SurfaceDetail
Xiaoju rear body / hind legs / tail rear segments
Xiaoju torso / head / facial base
eyes / eyelids / muzzle / whiskers
forelimbs
Planet_ContactShadow
Planet_FrontRim
joint-covering fur and foreground whisker tips
Planet_Highlight
```

## 完整 Deformer 根

```text
Scene_Root
├─ Planet_Rig
│  ├─ Planet_Global_Warp
│  └─ Planet_FrontRim_Warp
└─ Xiaoju_Rig
   └─ Xiaoju_Global_Warp
      └─ Body_Root
         ├─ Chest_Warp -> Foreleg_Rig_L/R
         ├─ Belly_Warp
         ├─ RearBody_Warp -> HindLeg_Rig_L/R + Tail_Rig
         └─ Neck_Warp -> Head_Rig -> Face/Eye/Ear rigs
```

## Gate 2 通过条件

- [x] 标注图中的 11 个区域均有明确图层责任。
- [x] 默认看不见的腹部、后躯、后腿、尾根和肩窝均纳入补画。
- [x] 左右前肢各只有一套完整视觉素材。
- [x] 眼睛具备独立眼球、眼睑和眼眶毛结构。
- [x] 星球前景遮挡与 Deformer 父子树相互独立。
- [x] 用户批准后才进入 Gate 3 拆图和补画。
