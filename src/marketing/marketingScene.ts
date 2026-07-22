export type MarketingSceneEntityKind = "planet" | "character" | "landmark";

export type MarketingSceneEntity = {
  id: string;
  kind: MarketingSceneEntityKind;
  name: string;
  eyebrow: string;
  description: string;
  x: number;
  y: number;
  size: number;
  zoom: number;
  accent: string;
  visual: string;
  depth: number;
};

export type MarketingCameraFrame = {
  x: number;
  y: number;
  scale: number;
};

export type MarketingInteraction = {
  kind: string;
  title: string;
  cue: string;
  glyph: string;
};

export type MarketingCompanionLink = {
  characterId: string;
  planetId: string;
  label: string;
  accent: string;
};

export const MARKETING_ENTITY_INTERACTIONS: Record<string, MarketingInteraction> = {
  "honey-ring": { kind: "warm-pulse", title: "蜜糖光环正在升温", cue: "沿着光带移动鼠标，收下一点暖意", glyph: "✦" },
  "lavender-moon": { kind: "slow-breath", title: "和月亮慢慢呼吸", cue: "吸气四秒，呼气四秒", glyph: "◌" },
  "blue-moon": { kind: "water-drop", title: "蓝莓补给已经抵达", cue: "这一站，记得喝一口水", glyph: "●" },
  xiaoju: { kind: "cat-purr", title: "小橘发现你了", cue: "它眨眨眼，把呼噜声送进星光里", glyph: "ฅ" },
  "yuxin-world": { kind: "world-heart", title: "愈心星球与你同频", cue: "每一次回应，都在这里留下微光", glyph: "♥" },
  "mint-moon": { kind: "mint-breath", title: "薄荷气流经过", cue: "放松肩膀，给自己一个深呼吸", glyph: "≈" },
  "lime-ring": { kind: "orbit-spark", title: "青柠航线点亮", cue: "跟随轨道，启动今天的一小步", glyph: "↗" },
  "violet-moon": { kind: "crystal-chime", title: "灵感正在结晶", cue: "把刚刚闪过的念头轻轻接住", glyph: "◆" },
  "rose-moon": { kind: "rose-echo", title: "温柔回声返回", cue: "今天也请对自己说一句好话", glyph: "♡" },
  "orbit-bunny": { kind: "whale-wave", title: "ds 跃过星浪", cue: "它沿着蓝莓月的引力向你靠近", glyph: "⌁" },
  "ufo-bunny": { kind: "leaf-flutter", title: "蒜鸟发来轻松信号", cue: "从口袋地球带回一阵清爽的风", glyph: "♧" },
  "tiny-earth": { kind: "home-signal", title: "故乡信号已连接", cue: "无论多远，都能找到安心的坐标", glyph: "⌂" },
  "heart-station": { kind: "energy-bounce", title: "ikun 投递元气", cue: "玫瑰月为这一球加上温柔的弧线", glyph: "●" },
};

export const MARKETING_COMPANION_LINKS: MarketingCompanionLink[] = [
  { characterId: "xiaoju", planetId: "honey-ring", label: "小橘的甜梦航线", accent: "#ffc06f" },
  { characterId: "orbit-bunny", planetId: "blue-moon", label: "ds 的蓝莓巡游线", accent: "#86d9ff" },
  { characterId: "ufo-bunny", planetId: "tiny-earth", label: "蒜鸟的故乡补给线", accent: "#9ee6b0" },
  { characterId: "heart-station", planetId: "rose-moon", label: "ikun 的玫瑰元气线", accent: "#ff9fc8" },
];

export const MARKETING_SCENE_ENTITIES: MarketingSceneEntity[] = [
  {
    id: "honey-ring",
    kind: "planet",
    name: "蜜糖星环",
    eyebrow: "甜梦轨道 · 01",
    description: "轻轻靠近，它会把今天积攒的小疲惫变成一圈暖黄色的星光。",
    x: 14.6,
    y: 21.5,
    size: 10,
    zoom: 1.58,
    accent: "#ffd58a",
    visual: "planet-honey-ring",
    depth: -70,
  },
  {
    id: "lavender-moon",
    kind: "planet",
    name: "薰衣草月",
    eyebrow: "安静信号 · 02",
    description: "一颗适合发呆的小月亮。停留片刻，宇宙也会跟着慢下来。",
    x: 24.7,
    y: 18.1,
    size: 5.6,
    zoom: 1.88,
    accent: "#bda0ff",
    visual: "planet-lavender",
    depth: -35,
  },
  {
    id: "blue-moon",
    kind: "planet",
    name: "蓝莓月球",
    eyebrow: "清醒补给 · 03",
    description: "微凉的蓝色能量正在充电，适合提醒自己喝一口水。",
    x: 24.9,
    y: 33.6,
    size: 6.2,
    zoom: 1.85,
    accent: "#7fd7ff",
    visual: "planet-blue",
    depth: -15,
  },
  {
    id: "xiaoju",
    kind: "character",
    name: "小橘",
    eyebrow: "桌面陪伴员 · 04",
    description: "趴在星球边缘偷偷看你。点击、双击或拖动时，它会用自己的方式回应。",
    x: 35.8,
    y: 22.3,
    size: 11.5,
    zoom: 1.62,
    accent: "#ffb15f",
    visual: "pet-xiaoju",
    depth: 90,
  },
  {
    id: "yuxin-world",
    kind: "landmark",
    name: "愈心星球",
    eyebrow: "陪伴发生的地方 · 05",
    description: "这里收纳桌宠、轻提醒与每一次小小互动。忙碌的时候，也有人安静待在身边。",
    x: 52,
    y: 47,
    size: 35,
    zoom: 1.18,
    accent: "#ff75a8",
    visual: "world-yuxin",
    depth: 0,
  },
  {
    id: "mint-moon",
    kind: "planet",
    name: "薄荷月",
    eyebrow: "呼吸坐标 · 06",
    description: "像一颗漂浮的深呼吸按钮，让紧绷的节奏暂时松开一点。",
    x: 69.2,
    y: 19.1,
    size: 5.8,
    zoom: 1.9,
    accent: "#8ce1c6",
    visual: "planet-mint",
    depth: -65,
  },
  {
    id: "lime-ring",
    kind: "planet",
    name: "青柠星环",
    eyebrow: "活力航线 · 07",
    description: "沿着清亮的轨道绕一圈，给今天补充一点轻盈的行动力。",
    x: 86,
    y: 21.2,
    size: 9.5,
    zoom: 1.62,
    accent: "#d7f07d",
    visual: "planet-lime-ring",
    depth: -45,
  },
  {
    id: "violet-moon",
    kind: "planet",
    name: "紫晶月",
    eyebrow: "灵感电波 · 08",
    description: "它把偶然掠过的灵感折射成紫色微光，提醒你及时接住。",
    x: 82.2,
    y: 37.6,
    size: 6.8,
    zoom: 1.82,
    accent: "#a98cff",
    visual: "planet-violet",
    depth: 5,
  },
  {
    id: "rose-moon",
    kind: "planet",
    name: "玫瑰月",
    eyebrow: "温柔回声 · 09",
    description: "今天对自己说过的好话，会在这里变成柔软的粉色回声。",
    x: 92,
    y: 36.2,
    size: 6.9,
    zoom: 1.8,
    accent: "#ff9dcc",
    visual: "planet-rose",
    depth: -5,
  },
  {
    id: "orbit-bunny",
    kind: "character",
    name: "ds",
    eyebrow: "云海巡游员 · 10",
    description: "圆滚滚的小鲸鱼沿着发光轨道巡游，发现你时会开心地跃起回应。",
    x: 85.5,
    y: 51.7,
    size: 9.6,
    zoom: 1.7,
    accent: "#ffc1dd",
    visual: "pet-ds",
    depth: 75,
  },
  {
    id: "ufo-bunny",
    kind: "character",
    name: "蒜鸟",
    eyebrow: "轻松领航员 · 11",
    description: "扑扑翅膀、晃晃蒜叶，把工作间隙里短短的快乐稳稳送到你身边。",
    x: 14.5,
    y: 68.4,
    size: 10.5,
    zoom: 1.65,
    accent: "#7ed4ff",
    visual: "pet-suan-bird",
    depth: 110,
  },
  {
    id: "tiny-earth",
    kind: "planet",
    name: "口袋地球",
    eyebrow: "微型故乡 · 12",
    description: "再远的旅程也可以带着熟悉感。这颗小星球负责保存安心。",
    x: 30.4,
    y: 79.4,
    size: 7.8,
    zoom: 1.72,
    accent: "#8edca8",
    visual: "planet-tiny-earth",
    depth: 35,
  },
  {
    id: "heart-station",
    kind: "character",
    name: "ikun",
    eyebrow: "活力球场 · 13",
    description: "抱着篮球守在下一站入口，点击靠近时，会把今天的元气稳稳传给你。",
    x: 76,
    y: 73.5,
    size: 12,
    zoom: 1.5,
    accent: "#ff88b7",
    visual: "pet-ikun",
    depth: 80,
  },
];

export function getMarketingCameraFrame(
  entity: MarketingSceneEntity | null,
): MarketingCameraFrame {
  if (!entity) {
    return { x: 0, y: 0, scale: 1 };
  }

  const centerY = 51;

  return {
    x: 50 - entity.x * entity.zoom,
    y: centerY - entity.y * entity.zoom,
    scale: entity.zoom,
  };
}

export function getAdjacentMarketingEntity(
  currentId: string | null,
  direction: -1 | 1,
): MarketingSceneEntity {
  const currentIndex = MARKETING_SCENE_ENTITIES.findIndex(
    (entity) => entity.id === currentId,
  );
  const startIndex = currentIndex < 0 ? (direction > 0 ? -1 : 0) : currentIndex;
  const nextIndex =
    (startIndex + direction + MARKETING_SCENE_ENTITIES.length) %
    MARKETING_SCENE_ENTITIES.length;

  return MARKETING_SCENE_ENTITIES[nextIndex];
}
