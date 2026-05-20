export type PetStateId =
  | 'idle_sleep'
  | 'idle_fishing'
  | 'notice_cursor'
  | 'chase_cursor'
  | 'hover_eat'
  | 'tickle'
  | 'super_happy'
  | 'grabbed_start'
  | 'grabbed_loop'
  | 'drop'
  | 'annoyed'
  | 'return_home'
  | 'perch_sleep'
  | string;

export interface PetSpriteConfig {
  file: string;
  columns: number;
  rows: number;
  cellWidth: number;
  cellHeight: number;
}

export interface PetStateConfig {
  row: number;
  frames: number;
  fps: number;
  loop: boolean;
  priority: number;
  frameSequence?: number[];
}

export interface RawPetManifest {
  id: string;
  displayName?: string;
  name?: string;
  description?: string;
  spritesheetPath?: string;
  sprite?: Partial<PetSpriteConfig> & { file: string };
  states?: Record<string, Partial<PetStateConfig> & Pick<PetStateConfig, 'row' | 'frames'>>;
  bubbles?: Record<string, string[]>;
  personality?: string[];
  version?: string;
}

export interface NormalizedPetManifest {
  id: string;
  displayName: string;
  description: string;
  version: string;
  personality: string[];
  sprite: PetSpriteConfig;
  states: Record<PetStateId, PetStateConfig>;
  bubbles: Record<PetStateId, string[]>;
}
