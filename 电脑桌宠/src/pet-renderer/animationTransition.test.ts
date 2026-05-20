import { describe, expect, it } from 'vitest';
import { getTransitionAlpha } from './animationTransition';

describe('getTransitionAlpha', () => {
  it('starts on the previous frame and ends on the next frame', () => {
    expect(getTransitionAlpha(0, 180)).toEqual({ incoming: 0, outgoing: 1 });
    expect(getTransitionAlpha(180, 180)).toEqual({ incoming: 1, outgoing: 0 });
  });

  it('eases the blend so state changes do not hard-cut', () => {
    const halfway = getTransitionAlpha(90, 180);

    expect(halfway.incoming).toBeGreaterThan(0.45);
    expect(halfway.incoming).toBeLessThan(0.55);
    expect(halfway.outgoing).toBeGreaterThan(0.45);
    expect(halfway.outgoing).toBeLessThan(0.55);
  });
});
