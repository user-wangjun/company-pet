import type { PresenceMode } from '../pet-core/presence';

export type PetActionState =
  | 'idle_sleep'
  | 'idle_fishing'
  | 'notice_cursor'
  | 'chase_cursor'
  | 'hover_eat'
  | 'tickle'
  | 'grabbed_loop'
  | 'perch_sleep';

export interface PreviewActionInput {
  isDragging: boolean;
  presence: PresenceMode;
  obstructionScore: number;
  hoverMs: number;
  clickBurst: number;
  elapsedMs?: number;
}

export function decidePreviewAction(input: PreviewActionInput): PetActionState {
  if (input.isDragging) {
    return 'grabbed_loop';
  }
  if (input.presence === 'passive' && input.obstructionScore >= 70) {
    return 'perch_sleep';
  }
  if (input.hoverMs > 900 && input.presence === 'solid') {
    return 'hover_eat';
  }
  if (input.clickBurst >= 3) {
    return 'tickle';
  }

  return 'idle_sleep';
}

export function pickActionBubble(bubbles: Record<string, string[]>, actionState: PetActionState) {
  const lines = bubbles[actionState] ?? bubbles.idle_sleep ?? ['哼。'];
  return lines[0] ?? '哼。';
}
