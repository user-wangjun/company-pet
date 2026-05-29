# 小橘声音系统设计

日期：2026-05-29

状态：待用户审阅

## 1. 背景与目标

本次只为内置宠物包 `xiaoju-cat` 增加声音系统。声音要强化“小橘像活着一样陪在桌面上”的感觉，但不把它变成吵闹的提示工具。

目标：

- 为小橘的核心动作状态提供短音效。
- 声音风格为 Q 版拟声，并带少量短音节情绪音。
- 使用安静陪伴型频率：互动和明显状态变化时才发声。
- 音频资产归属 `public/pets/xiaoju-cat/`，平台代码只提供通用播放能力。
- 不为平台打开、宠物切换、检查更新等系统事件单独加声音。

非目标：

- 不做完整中文语音台词。
- 不做连续背景音乐或持续循环猫叫。
- 不把小橘声音硬编码到 `App.tsx` 或其他平台组件里。
- 不影响其他未来宠物包的独立性。

## 2. 声音风格

小橘的声音是“Q 版拟声 + 少量短音节情绪音”。

允许的声音类型：

- 轻喵、软喵、短促抗议音。
- 呼噜、鼻息、舔嘴、轻啃、软落地、扑腾、小爪步。
- 很短的情绪音节，例如“嗯？”、“哼”、“欸？”、“喵呜！”。

不使用的声音类型：

- 完整人话句子。
- 长语音。
- 刺耳提醒音。
- 真实感太强的咀嚼、尖叫、警报或高频铃声。

整体听感要低音量、短时长、柔和，不打扰工作。

## 3. 声音状态表

| 状态 | 触发 | 声音变体方向 |
| --- | --- | --- |
| `idle` | 待机小动作偶发 | 轻呼噜、睡觉鼻息、很轻的“喵...” |
| `tickle` | 单击挠痒 | “嗯？”、“哼”、短呼噜 |
| `drag` | 开始拖拽 | “喵呜！”、“欸？”、“嗯？！” |
| `drag_end` | 松手放下 | 轻“哼”、小鼻音、软落地声 |
| `fishChase` | 抓鱼开始 | `mrrp!`、小爪步、扑腾声 |
| `fishEat` | 吃到鱼 | `nom`、舔嘴声、满足“嗯~” |
| `crouchAlert` | 警觉趴下 | “欸？”、`mrrp?`、很轻的警觉铃音 |
| `hugFish` | 抱鱼撒娇 | 低呼噜、软“喵~”、满足鼻音 |
| `gnawFish` | 啃鱼 | 轻啃声、咂嘴声、短满足音 |
| `iconHug` | 抱住桌面图标 | 软“扑”、安心呼噜、很轻“喵” |
| `care_reminder` | 护眼或喝水提醒 | 短喵或轻铃，只响一次 |

核心状态准备 2 到 3 个变体。变体数量足够避免机械重复，但不让宠物包资产膨胀。

## 4. 宠物包文件结构

声音文件放在小橘宠物包内部：

```text
public/pets/xiaoju-cat/
  pet.json
  spritesheet-scruff.webp
  icon-hug.webp
  sounds/
    idle-purr-1.webm
    idle-breath-1.webm
    tickle-hm-1.webm
    tickle-hmph-1.webm
    drag-meow-1.webm
    drag-question-1.webm
    drag-end-hmph-1.webm
    fish-chase-mrrp-1.webm
    fish-eat-nom-1.webm
    icon-hug-poof-1.webm
```

音频路径必须相对 `public/pets/xiaoju-cat/`。不要使用绝对 Windows 路径，也不要把声音资产放到项目根目录、`src/`、`src-tauri/`、`dist/`、`output/`、`prd_render/` 或 `releases/`。

优先使用 `.webm` 或 `.ogg`，因为它们适合短音效且文件较小。若 Tauri/WebView 兼容性验证发现问题，再退回 `.mp3`。

## 5. `pet.json` 扩展格式

`pet.json` 新增可选 `sounds` 字段。平台读取当前宠物 manifest 后，根据状态名查找声音列表并随机播放。下面是格式示例，不是完整声音清单。

```json
{
  "id": "xiaoju-cat",
  "displayName": "小橘",
  "description": "一只橘黄色毛绒小猫咪，会睡觉、抓鱼、吃鱼、跳来跳去，也会陪你等结果。",
  "spritesheetPath": "spritesheet-scruff.webp",
  "sounds": {
    "tickle": [
      { "path": "sounds/tickle-hm-1.webm", "volume": 0.45 },
      { "path": "sounds/tickle-hmph-1.webm", "volume": 0.4 }
    ],
    "drag": [
      { "path": "sounds/drag-meow-1.webm", "volume": 0.5 },
      { "path": "sounds/drag-question-1.webm", "volume": 0.45 }
    ],
    "fishEat": [
      { "path": "sounds/fish-eat-nom-1.webm", "volume": 0.42 },
      { "path": "sounds/fish-eat-purr-1.webm", "volume": 0.38 }
    ]
  }
}
```

建议类型：

```ts
type PetSoundCue = {
  path: string;
  volume?: number;
};

type PetManifestSounds = Record<string, PetSoundCue[]>;
```

`sounds` 是宠物包能力，不是平台全局配置。未来其他宠物可以拥有自己的声音表，也可以完全不提供声音。

## 6. 播放规则

基础规则：

- 同一状态从配置的变体中随机选一个。
- 高频交互状态需要冷却，`tickle` 和 `drag` 默认冷却 1.2 到 2 秒。
- 新状态声音可以打断旧的短音效，但不叠加很多层。
- 单个音效音量建议为 0.35 到 0.55。
- 平台预留全局音量和 `soundEnabled` 开关，供后续设置面板使用。
- 小橘加载后预加载 manifest 中声明的音效，减少第一次播放延迟。
- 声音文件缺失或加载失败时跳过，不影响动画和交互。
- `idle` 不做定时循环，只在待机小动作触发时偶尔播放。
- `care_reminder` 与护眼、喝水气泡同步，只响一次。
- 平台打开、宠物切换、检查更新等系统事件暂时无声。

触发点：

- `playAnimation("tickle")` 播放 `tickle`。
- `playAnimation("drag")` 播放 `drag`。
- 拖拽松手回到待机前播放 `drag_end`。
- `playHoverFishSequence()` 中分别播放 `fishChase` 和 `fishEat`。
- 随机待机小动作按所选动画播放 `fishEat`、`tickle`、`crouchAlert`、`hugFish` 或 `gnawFish`。
- 抱住桌面图标并进入 `iconHug` 时播放 `iconHug`。
- 护眼和喝水提醒触发时播放 `care_reminder`。

## 7. 架构边界

宠物包负责：

- 声音文件。
- `pet.json` 声音配置。
- 小橘专属命名、音色和变体数量。

平台代码负责：

- 解析 `PetManifest.sounds`。
- 使用 `resolvePetAssetUrl()` 解析相对音频路径。
- 预加载音频。
- 按状态、冷却、随机规则播放声音。
- 提供全局静音和音量能力。
- 在文件缺失时安静降级。

平台代码不负责：

- 硬编码 `/pets/xiaoju-cat/...`。
- 硬编码小橘专属声音文件名。
- 把声音资产放进 `src/` 或 `src-tauri/`。

## 8. 验收标准

设计验收：

- 小橘状态声音表覆盖当前主要动画和提醒。
- 声音资产路径都在 `public/pets/xiaoju-cat/` 下。
- `pet.json` 的声音路径全为相对路径。
- 系统事件不发声。
- 核心状态支持 2 到 3 个随机变体。

体验验收：

- 声音低频、短促、柔和，不干扰工作。
- 连续点击不会产生密集叠音。
- 音频缺失时小橘动画和气泡仍正常工作。
- 第一次触发声音没有明显卡顿。
- 小橘有一点情绪音，但不会说完整中文台词。

测试验收：

- 更新 `src/pet-core/petAssets.test.ts` 或新增声音相关测试，覆盖声音路径解析和 manifest 兼容。
- 运行 `npm test -- src/pet-core/petAssets.test.ts`。
- 运行 `npm run build`。
