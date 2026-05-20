import { describe, expect, it } from 'vitest';
import { normalizePetManifest } from './normalizePetManifest';

describe('normalizePetManifest', () => {
  it('expands a Codex-minimal xiaoju manifest into desktop pet states', () => {
    const manifest = normalizePetManifest({
      id: 'xiaoju',
      displayName: '小橘',
      description: '一只橘黄色毛绒小猫咪。',
      spritesheetPath: 'spritesheet-scruff.webp',
    });

    expect(manifest.id).toBe('xiaoju');
    expect(manifest.sprite.file).toBe('spritesheet-scruff.webp');
    expect(manifest.sprite.cellWidth).toBe(192);
    expect(manifest.sprite.cellHeight).toBe(208);
    expect(manifest.states.idle_sleep).toMatchObject({
      row: 0,
      frames: 6,
      fps: 8,
      loop: true,
    });
    expect(manifest.states.hover_eat).toMatchObject({
      row: 8,
      frames: 6,
    });
    expect(manifest.states.grabbed_loop).toMatchObject({
      row: 1,
      frames: 8,
    });
    expect(manifest.bubbles.annoyed).toContain('你很闲吗？');
  });

  it('preserves explicit extended state definitions', () => {
    const manifest = normalizePetManifest({
      id: 'custom',
      displayName: '自定义',
      sprite: {
        file: 'custom.webp',
        columns: 4,
        rows: 2,
        cellWidth: 128,
        cellHeight: 128,
      },
      states: {
        proud_idle: {
          row: 1,
          frames: 3,
          fps: 6,
          loop: true,
          priority: 12,
        },
      },
      bubbles: {
        proud_idle: ['看吧。'],
      },
    });

    expect(manifest.sprite.columns).toBe(4);
    expect(manifest.states.proud_idle).toEqual({
      row: 1,
      frames: 3,
      fps: 6,
      loop: true,
      priority: 12,
    });
    expect(manifest.bubbles.proud_idle).toEqual(['看吧。']);
  });
});
