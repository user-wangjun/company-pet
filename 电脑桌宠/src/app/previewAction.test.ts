import { describe, expect, it } from 'vitest';
import { TICKLE_HOLD_MS, decidePreviewAction, pickActionBubble } from './previewAction';

describe('decidePreviewAction', () => {
  it('keeps the default preview action stable instead of time-toggling idle states', () => {
    const baseInput = {
      isDragging: false,
      presence: 'solid' as const,
      obstructionScore: 0,
      hoverMs: 0,
      clickBurst: 0,
    };

    expect(decidePreviewAction({ ...baseInput, elapsedMs: 0 })).toBe('idle_sleep');
    expect(decidePreviewAction({ ...baseInput, elapsedMs: 9000 })).toBe('idle_sleep');
    expect(decidePreviewAction({ ...baseInput, elapsedMs: 18000 })).toBe('idle_sleep');
  });

  it('still switches to intentional interaction states', () => {
    expect(
      decidePreviewAction({
        isDragging: true,
        presence: 'dragging',
        obstructionScore: 0,
        hoverMs: 0,
        clickBurst: 0,
      }),
    ).toBe('grabbed_loop');

    expect(
      decidePreviewAction({
        isDragging: false,
        presence: 'solid',
        obstructionScore: 0,
        hoverMs: 1200,
        clickBurst: 0,
      }),
    ).toBe('hover_eat');
  });

  it('treats one left click as tickling and lets it override hover eating', () => {
    expect(
      decidePreviewAction({
        isDragging: false,
        presence: 'solid',
        obstructionScore: 0,
        hoverMs: 1200,
        clickBurst: 1,
      }),
    ).toBe('tickle');
  });
});

describe('pickActionBubble', () => {
  it('uses a stable first bubble line for an action', () => {
    expect(
      pickActionBubble(
        {
          idle_sleep: ['我先睡一会儿。', '这块地方不错。'],
        },
        'idle_sleep',
      ),
    ).toBe('我先睡一会儿。');
  });
});

describe('TICKLE_HOLD_MS', () => {
  it('keeps a single click in the tickle animation long enough to read as a continuous action', () => {
    expect(TICKLE_HOLD_MS).toBeGreaterThanOrEqual(2000);
  });
});
