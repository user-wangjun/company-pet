# 橘猫桌面宠物正式设计

日期：2026-05-20

状态：待用户审阅

## 1. 背景与目标

本项目要做一个 Windows-first 的独立桌面宠物 App。第一版主角是“小橘”：一只骄傲、懒洋洋、贪吃、好奇、有点小脾气但亲人的橘猫。

产品第一阶段不是 AI 助手，也不是开发工具状态面板，而是一只“活在桌面上的小宠物”。它默认实体可交互，可以睡觉、抓鱼、追鼠标、吃鱼、被挠痒痒、被拖拽；当周围有图标、文件或应用控件密集时，它仍然完整显示，但进入防误触点击穿透模式，避免影响用户操作。

第一版目标：

- Windows 桌面上显示透明背景的小橘。
- 支持拖动位置并保存。
- 支持加载 `pet.json + spritesheet.webp` 的宠物包。
- 兼容用户已有 Codex 自建 Pet“小橘”的资产形态。
- 建立正式架构，为后续 macOS、AI 对话、换装、Pet Studio 和工具监听留出扩展空间。

第一版非目标：

- 不接入 Codex、Trae、Cursor 等工具监听。
- 不做复杂 AI 长对话。
- 不做宠物市场。
- 不做 Live2D 绑定。
- 不做复杂养成系统。
- 不优先支持 macOS，但架构要避免 Windows 逻辑污染核心层。

## 2. 已确认产品决策

- 平台策略：先做 Windows，后做 macOS。
- 技术路线：`Tauri + React + TypeScript + PixiJS + Windows Native Adapter`。
- 产品气质：真正的小宠物，不是始终主动提醒的小助手。
- 默认存在模式：启动后默认实体可交互。
- 防误触机制：周围图标、文件或应用控件密集时，视觉保持实体，但点击穿透。
- 激活交互：用户悬停约 5 秒，或通过托盘菜单点“实体化”。
- 栖息行为：小橘可以自动找图标边缘趴着睡觉，不直接盖住图标中心。
- 角色性格：骄傲但亲人，抓到鱼会得意，被点多了会不耐烦，被拎起来委屈但不服气。

## 3. 架构分层

系统分为四层：

```text
Windows Native Layer
负责透明窗口、置顶、点击穿透、桌面图标探测、托盘、DPI、多显示器

Tauri App Layer
负责桌面应用壳、系统命令、存档、窗口生命周期、设置入口

Pet Core Layer
负责状态机、存在模式、防误触判断、栖息点规划、气泡规则

Renderer Layer
负责 PixiJS 播放 spritesheet、动画切换、缩放、气泡显示
```

核心原则：

- 行为逻辑不绑死在窗口里。
- 渲染器只负责显示，不负责业务判断。
- Windows API 只提供桌面环境信息，不直接决定小橘行为。
- `pet-core` 尽量平台无关，后续 macOS 可以替换 Native Adapter。
- 宠物资产使用结构化包格式，避免把状态、帧数、动画语义写死在代码里。

建议目录：

```text
orange-cat-desktop/
  src-tauri/
    windows/              # Windows 原生窗口能力、点击穿透、图标探测、托盘
    commands/             # 前端调用的 Tauri 命令
    storage/              # 配置和位置存档

  src/
    app/                  # React 设置面板、调试面板
    pet-core/             # 状态机、交互规则、存在模式、栖息点算法
    pet-renderer/         # PixiJS spritesheet 播放器
    pet-assets/           # pet.json 解析、资源加载、默认小橘包
    desktop-sensing/      # 前端侧环境感知封装
```

## 4. 动作状态机

动作状态描述“小橘正在做什么”。

```text
idle_sleep      睡觉
idle_fishing    抓鱼
notice_cursor   注意鼠标
chase_cursor    追鼠标
hover_eat       悬停吃鱼
tickle          挠痒痒
super_happy     连续点击超开心
grabbed_start   被抓起瞬间
grabbed_loop    被拎着
drop            落地恢复
annoyed         小生气
return_home     回到附近位置
perch_sleep     趴在图标边缘睡觉
```

动作优先级：

1. `dragging / grabbed_loop`
2. `drop`
3. `tickle / super_happy / annoyed`
4. `hover_eat`
5. `chase_cursor`
6. `notice_cursor`
7. `return_home`
8. `idle_sleep / idle_fishing / perch_sleep`

基础流转：

- 启动后进入 `idle_sleep` 或 `idle_fishing`。
- 鼠标进入观察区时进入 `notice_cursor`。
- 鼠标进入追逐区时进入 `chase_cursor`，并限制追逐距离。
- 鼠标悬停在宠物主体区域约 0.8 秒时进入 `hover_eat`。
- 左键单击进入 `tickle`。
- 短时间连续点击进入 `super_happy`。
- 点击过多或拖拽过久进入 `annoyed`。
- 按住并拖动进入 `grabbed_start`，随后进入 `grabbed_loop`。
- 松开鼠标进入 `drop`，之后回到待机或 `annoyed`。
- 空闲时可由 `PerchPlanner` 触发 `perch_sleep`。

## 5. 存在模式与防误触

存在模式描述“小橘现在能不能被交互”。

```text
solid           实体，可点击、可拖、可互动
passive         看起来实体，但点击穿透，防误触
materializing   悬停 5 秒后逐渐进入实体
dragging        拖动中，强制实体
```

规则：

- 启动默认 `solid`。
- 小橘周围内容密集，或趴在图标边缘睡觉时，自动切到 `passive`。
- `passive` 时视觉仍然完整，不明显变透明，但点击穿透到底层。
- 鼠标停在小橘身上约 5 秒后进入 `materializing`。
- `materializing` 期间光标变成抓取手势，并用轻微动作提示用户可以交互。
- 托盘菜单可以强制“实体化 / 防误触”。
- 用户拖动时进入 `dragging`，释放后按环境决定回到 `solid` 或 `passive`。

`passive` 不是消失，也不是幽灵化。它的含义是：小橘仍然像实体一样在桌面上，但它懂得让出点击路径。

## 6. 桌面感知与栖息点系统

`DesktopSensing` 负责收集环境信息：

- 桌面图标位置。
- 当前前台窗口区域。
- 任务栏区域。
- 多显示器边界。
- DPI 缩放信息。
- 鼠标在小橘附近的停留和点击行为。

`PerchPlanner` 根据环境信息寻找小橘的栖息点：

```text
图标组边缘 > 单个图标边缘 > 屏幕角落 > 用户上次放置位置附近 > 默认位置
```

栖息点结构：

```json
{
  "x": 1200,
  "y": 680,
  "type": "icon-edge",
  "score": 86,
  "reason": "near icon cluster edge with low obstruction"
}
```

评分因素：

- 少遮挡图标文字和图标主体。
- 不压住任务栏。
- 离当前点不要太远。
- 不贴屏幕边太死。
- 周围图标密集时优先停在边缘，不停在正中央。
- 用户刚手动拖过的位置要尊重一段时间。

行为：

- 小橘空闲一段时间后，可以慢慢移动到图标边缘趴下。
- 趴在图标边缘时进入 `perch_sleep + passive`。
- 如果用户悬停 5 秒，小橘进入 `materializing` 并恢复交互。
- 如果图标探测失败，退化为屏幕角落或用户上次位置附近待机。

Windows 第一版优先尝试通过 Shell/Win32 获取桌面 ListView 图标矩形。该能力必须封装在 Native Adapter 中，避免影响 macOS 后续实现。

## 7. Pet 包格式与小橘资产兼容

第一版 App 内置默认小橘资源，同时支持加载外部 Pet 包。

建议包结构：

```text
orange-cat-pet/
  pet.json
  spritesheet.webp
  preview.png
  README.md
  prompts.md
```

兼容用户已有 Codex 自建 Pet 的最小格式：

```json
{
  "id": "xiaoju-cat",
  "displayName": "小橘",
  "description": "一只橘黄色毛绒小猫咪，会睡觉、抓鱼、吃鱼、跳来跳去，也会陪你等结果。",
  "spritesheetPath": "spritesheet.webp"
}
```

推荐扩展格式：

```json
{
  "id": "xiaoju-cat",
  "displayName": "小橘",
  "version": "1.0.0",
  "personality": ["lazy", "foodie", "curious", "proud"],
  "sprite": {
    "file": "spritesheet.webp",
    "columns": 8,
    "rows": 9,
    "cellWidth": 192,
    "cellHeight": 208
  },
  "states": {
    "idle_sleep": {
      "row": 0,
      "frames": 6,
      "fps": 8,
      "loop": true,
      "priority": 10
    },
    "hover_eat": {
      "row": 4,
      "frames": 5,
      "fps": 8,
      "loop": true,
      "priority": 40
    }
  },
  "bubbles": {
    "idle_sleep": ["我先睡一会儿。", "这块地方不错。"],
    "idle_fishing": ["我抓到的。", "看吧。"],
    "tickle": ["哼，还行。", "再挠一下也不是不行。"],
    "annoyed": ["你很闲吗？", "够啦。"]
  }
}
```

设计要求：

- 每个状态单独声明 `frames`，不能假设每行都是 8 帧。
- 支持 `fps` 和 `loop`，便于不同动作拥有不同节奏。
- 支持状态别名映射，让 Codex 风格的 `idle/running/waving/jumping/failed/waiting/review` 可以映射到桌宠状态。
- `personality` 会影响气泡、动作偏好和自动行为。
- 第一版可直接使用现有 `xiaoju-cat` 图集验证播放器。
- 后续再生成 PRD 专用动作图集：`idle_sleep / idle_fishing / chase_cursor / hover_eat / tickle / grabbed_loop / drop / annoyed`。

资产生产流程借鉴 Codex Hatch Pet：

```text
角色基准图
-> 分状态生成行图
-> 帧提取
-> 图集验证
-> contact sheet QA
-> 打包 pet.json + spritesheet.webp
```

独立 App 不依赖 Codex 运行。Codex 生成流程只是资产生产线。

## 8. 气泡与角色表达

气泡短句要低频、短、状态相关，不做长篇对话。

性格方向：

```text
懒洋洋
贪吃
好奇
骄傲
有点小脾气
被摸会开心但嘴硬
抓到鱼会得意
被拎起来会委屈但不服气
被点太多会摆出“你很闲吗”的表情
```

文案方向：

- 待机：`我先睡一会儿。`、`这块地方不错。`
- 抓鱼：`我抓到的。`、`看吧。`
- 吃鱼：`鱼鱼。`、`再来一条也行。`
- 挠痒痒：`哼，还行。`、`再挠一下也不是不行。`
- 被拖动：`喵？！`、`你要带我去哪？`
- 小生气：`你很闲吗？`、`够啦。`

频率规则：

- 任意文案间隔不少于 5 秒。
- 同一状态文案 10 秒内不重复出现。
- 待机随机文案间隔不少于 3 分钟。
- 长时间未互动文案间隔不少于 10 分钟。

## 9. 设置与存储

MVP 设置项：

- 开机启动。
- 始终置顶。
- 显示气泡。
- 气泡频率。
- 宠物大小。
- 追鼠标强度。
- 防误触模式。
- 悬停实体化时间。
- 重置位置。

本地存档示例：

```json
{
  "position": { "x": 1200, "y": 680 },
  "scale": 1,
  "alwaysOnTop": true,
  "bubbleEnabled": true,
  "bubbleFrequency": "medium",
  "chaseStrength": "medium",
  "antiMistouchEnabled": true,
  "materializeHoverMs": 5000
}
```

Windows 第一版存储在 AppData。存储 API 要封装，后续 macOS 切换到 Application Support。

## 10. MVP 开发阶段

阶段 0：项目底座

- 创建 Tauri + React + TypeScript + PixiJS 工程。
- 建立资源目录、配置存档和基础窗口。

阶段 1：Pet 播放器

- 加载 `pet.json` 和 `spritesheet.webp`。
- 支持 `row / frames / fps / loop`。
- 使用现有 `xiaoju` 图集验证不满 8 帧的动画行。

阶段 2：Windows 桌宠窗口

- 透明无边框。
- 默认置顶。
- 可拖动。
- 保存位置。
- 托盘入口。
- 右键菜单。

阶段 3：状态机与基础交互

- 睡觉/抓鱼。
- 鼠标靠近。
- 悬停吃鱼。
- 点击挠痒。
- 拖拽被拎。
- 松开落地。

阶段 4：存在模式与防误触

- 实现 `solid / passive / materializing / dragging`。
- 实现点击穿透。
- 实现悬停 5 秒实体化。
- 实现托盘强制实体化。

阶段 5：桌面感知与栖息点

- 识别桌面图标或窗口密集区域。
- 找图标边缘栖息点。
- 小橘可以自动趴到图标边缘。

阶段 6：气泡与设置

- 实现低频气泡。
- 写入骄傲橘猫文案。
- 实现大小、置顶、气泡、防误触、追逐强度设置。

阶段 7：打包与验证

- 生成 Windows 安装包。
- 验证开机启动。
- 验证 DPI、多显示器和重启恢复位置。

## 11. 验收标准

功能验收：

- 启动后 Windows 桌面出现透明背景小橘，无明显边框。
- 默认实体可交互，可以拖动并保存位置。
- 能加载现有 `xiaoju-cat` Codex 风格 Pet 包。
- 能正确播放每行帧数不同的 spritesheet 动画。
- 鼠标靠近、悬停、点击、拖拽都有明确状态反馈。
- 小橘周围图标或窗口内容密集时，视觉仍完整，但点击穿透到底层。
- 鼠标悬停约 5 秒后，小橘重新变为可交互。
- 空闲时能移动到图标边缘附近趴下睡觉。
- 设置和位置能本地保存。

体验验收：

- 用户第一眼能认出是橘猫。
- 小橘不是工具面板，而像桌面上的小生命。
- 小橘有骄傲但亲人的性格。
- 点击后有明确反馈，但不会过度打扰。
- 防误触模式不会让用户误以为小橘消失。
- 连续使用 5 分钟不会影响正常桌面操作。

资产验收：

- 角色在所有动作中保持一致。
- 背景透明。
- 无文字、水印、杂散边框。
- 每个状态帧数由 `pet.json` 明确声明。
- 单帧大小统一。
- 播放时动作连续。
- 不满 8 帧的行，剩余格必须保持透明。

扩展验收：

- 后续 macOS 可以替换 Native Adapter，不重写 `pet-core`。
- 后续 AI 对话、换装、Pet Studio 可以作为独立模块加入。
- 后续新 Pet 包可以沿用同一加载协议。

## 12. 风险与处理

Windows 桌面图标探测可能受系统版本、DPI、桌面管理器或安全策略影响。处理方式：Native Adapter 封装实现，失败时退化到屏幕边缘和鼠标行为策略。

透明点击穿透可能和 Tauri 默认窗口事件冲突。处理方式：在 Windows 原生层集中管理窗口样式切换，由前端只发送存在模式请求。

PixiJS 与透明窗口性能可能受高 DPI 和多显示器影响。处理方式：从第一版开始验证 DPI、缩放和多显示器，不把渲染尺寸硬编码。

现有 Codex Pet 图集状态语义与 PRD 桌宠状态不完全一致。处理方式：第一版支持状态别名映射，播放器先验证图集能力，后续再生成 PRD 专用动作资产。

防误触过于智能可能让用户困惑。处理方式：托盘菜单提供强制实体化和防误触开关，悬停 5 秒期间给出明确的抓取光标和轻微动作反馈。

## 13. 下一步

用户审阅本设计文档后，进入实现计划阶段。实现计划应拆分为可执行任务，优先建立工程底座、Pet 播放器和 Windows 透明窗口，再逐步加入状态机、防误触和桌面栖息点系统。
