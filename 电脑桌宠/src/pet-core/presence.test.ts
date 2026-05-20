import { describe, expect, it } from 'vitest';
import { decidePresenceMode } from './presence';

describe('decidePresenceMode', () => {
  it('keeps the pet solid by default', () => {
    expect(
      decidePresenceMode({
        isDragging: false,
        nearbyObstructionScore: 0,
        hoverMs: 0,
        forcedMode: 'auto',
      }),
    ).toBe('solid');
  });

  it('uses passive anti-mistouch mode near dense desktop content', () => {
    expect(
      decidePresenceMode({
        isDragging: false,
        nearbyObstructionScore: 85,
        hoverMs: 0,
        forcedMode: 'auto',
      }),
    ).toBe('passive');
  });

  it('materializes after the user intentionally hovers long enough', () => {
    expect(
      decidePresenceMode({
        isDragging: false,
        nearbyObstructionScore: 85,
        hoverMs: 5200,
        forcedMode: 'auto',
      }),
    ).toBe('materializing');
  });

  it('forces dragging mode while the pet is being dragged', () => {
    expect(
      decidePresenceMode({
        isDragging: true,
        nearbyObstructionScore: 100,
        hoverMs: 5200,
        forcedMode: 'auto',
      }),
    ).toBe('dragging');
  });

  it('honors manual solid and passive overrides', () => {
    expect(
      decidePresenceMode({
        isDragging: false,
        nearbyObstructionScore: 100,
        hoverMs: 0,
        forcedMode: 'solid',
      }),
    ).toBe('solid');

    expect(
      decidePresenceMode({
        isDragging: false,
        nearbyObstructionScore: 0,
        hoverMs: 0,
        forcedMode: 'passive',
      }),
    ).toBe('passive');
  });
});
