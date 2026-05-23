import type {
  NormalizedPetManifest,
  PetSpriteConfig,
  PetStateConfig,
  RawPetManifest,
} from './types';

const DEFAULT_SPRITE: Omit<PetSpriteConfig, 'file'> = {
  columns: 8,
  rows: 9,
  cellWidth: 192,
  cellHeight: 208,
};

const DEFAULT_PERSONALITY = ['lazy', 'foodie', 'curious', 'proud'];

const CODEX_XIAOJU_STATES: Record<string, PetStateConfig> = {
  idle_sleep: { row: 0, frames: 5, fps: 3, loop: true, priority: 10, frameSequence: [0, 1, 2, 4, 5] },
  idle_fishing: { row: 7, frames: 6, fps: 8, loop: true, priority: 10 },
  notice_cursor: { row: 3, frames: 4, fps: 10, loop: false, priority: 20 },
  chase_cursor: { row: 4, frames: 5, fps: 12, loop: true, priority: 30 },
  hover_eat: { row: 8, frames: 6, fps: 8, loop: true, priority: 40 },
  tickle: { row: 3, frames: 4, fps: 12, loop: true, priority: 50 },
  super_happy: { row: 4, frames: 5, fps: 12, loop: false, priority: 55 },
  grabbed_start: { row: 1, frames: 8, fps: 12, loop: false, priority: 90 },
  grabbed_loop: { row: 1, frames: 8, fps: 8, loop: true, priority: 100 },
  drop: { row: 4, frames: 5, fps: 12, loop: false, priority: 80 },
  annoyed: { row: 5, frames: 8, fps: 8, loop: false, priority: 60 },
  return_home: { row: 4, frames: 5, fps: 10, loop: false, priority: 15 },
  perch_sleep: { row: 1, frames: 8, fps: 4, loop: true, priority: 10 },
};

const DEFAULT_BUBBLES: Record<string, string[]> = {
  idle_sleep: ['我先睡一会儿。', '这块地方不错。'],
  idle_fishing: ['我抓到的。', '看吧。'],
  hover_eat: ['鱼鱼。', '再来一条也行。'],
  tickle: ['哼，还行。', '再挠一下也不是不行。'],
  grabbed_loop: ['喵？！', '你要带我去哪？'],
  annoyed: ['你很闲吗？', '够啦。'],
  perch_sleep: ['抱住！不许抢！', '贴贴～', '这个图标归我啦！'],
};

function normalizeState(state: Partial<PetStateConfig> & Pick<PetStateConfig, 'row' | 'frames'>): PetStateConfig {
  return {
    row: state.row,
    frames: state.frames,
    fps: state.fps ?? 8,
    loop: state.loop ?? true,
    priority: state.priority ?? 10,
    frameSequence: state.frameSequence,
  };
}

export function normalizePetManifest(raw: RawPetManifest): NormalizedPetManifest {
  const spriteFile = raw.sprite?.file ?? raw.spritesheetPath ?? 'spritesheet.webp';
  const explicitStates = raw.states
    ? Object.fromEntries(Object.entries(raw.states).map(([id, state]) => [id, normalizeState(state)]))
    : CODEX_XIAOJU_STATES;

  return {
    id: raw.id,
    displayName: raw.displayName ?? raw.name ?? raw.id,
    description: raw.description ?? '',
    version: raw.version ?? '1.0.0',
    personality: raw.personality ?? DEFAULT_PERSONALITY,
    sprite: {
      file: spriteFile,
      columns: raw.sprite?.columns ?? DEFAULT_SPRITE.columns,
      rows: raw.sprite?.rows ?? DEFAULT_SPRITE.rows,
      cellWidth: raw.sprite?.cellWidth ?? DEFAULT_SPRITE.cellWidth,
      cellHeight: raw.sprite?.cellHeight ?? DEFAULT_SPRITE.cellHeight,
    },
    states: explicitStates,
    bubbles: {
      ...DEFAULT_BUBBLES,
      ...raw.bubbles,
    },
  };
}
