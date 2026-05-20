import { describe, expect, it } from 'vitest';
import { DEFAULT_PET_SCALE } from './petPreviewConfig';

describe('pet preview config', () => {
  it('uses a compact default pet scale for the desktop preview', () => {
    expect(DEFAULT_PET_SCALE).toBe(0.86);
  });
});
