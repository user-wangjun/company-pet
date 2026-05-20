import { describe, expect, it } from 'vitest';
import { chooseBestPerch, createIconEdgeCandidates } from './perchPlanner';

describe('perchPlanner', () => {
  it('prefers an icon-edge perch close to the current pet position', () => {
    const icons = [
      { x: 80, y: 80, width: 72, height: 92 },
      { x: 80, y: 190, width: 72, height: 92 },
    ];

    const candidates = createIconEdgeCandidates(icons, { width: 192, height: 208 });
    const best = chooseBestPerch(candidates, {
      current: { x: 170, y: 100 },
      screen: { x: 0, y: 0, width: 1280, height: 720 },
      taskbar: { x: 0, y: 680, width: 1280, height: 40 },
    });

    expect(best?.type).toBe('icon-edge');
    expect(best?.x).toBeGreaterThan(120);
    expect(best?.reason).toContain('icon edge');
  });

  it('rejects candidates overlapping the taskbar', () => {
    const best = chooseBestPerch(
      [
        {
          x: 100,
          y: 620,
          type: 'icon-edge',
          score: 100,
          reason: 'bad taskbar overlap',
        },
        {
          x: 100,
          y: 360,
          type: 'screen-corner',
          score: 40,
          reason: 'safe fallback',
        },
      ],
      {
        current: { x: 100, y: 360 },
        screen: { x: 0, y: 0, width: 1280, height: 720 },
        taskbar: { x: 0, y: 680, width: 1280, height: 40 },
      },
    );

    expect(best?.reason).toBe('safe fallback');
  });
});
