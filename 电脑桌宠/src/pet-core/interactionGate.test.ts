import { describe, expect, it } from 'vitest';
import { canStartPetInteraction, type DesktopInteractionContext } from './interactionGate';

const petRect = { x: 120, y: 80, width: 160, height: 180 };
const pointer = { x: 180, y: 140 };

describe('canStartPetInteraction', () => {
  it('blocks pet interactions when the pointer is over a foreground app window', () => {
    const desktopContext: DesktopInteractionContext = {
      surface: 'foreground-window',
      foregroundWindowRect: { x: 0, y: 0, width: 640, height: 480 },
    };

    expect(
      canStartPetInteraction({
        pointer,
        petRect,
        presence: 'solid',
        desktopContext,
      }),
    ).toEqual({ canStart: false, reason: 'foreground-window' });
  });

  it('blocks foreground-window surfaces even when the native rect uses screen coordinates', () => {
    expect(
      canStartPetInteraction({
        pointer,
        petRect,
        presence: 'solid',
        desktopContext: {
          surface: 'foreground-window',
          foregroundWindowRect: { x: 1200, y: 640, width: 500, height: 400 },
        },
      }),
    ).toEqual({ canStart: false, reason: 'foreground-window' });
  });

  it('allows pet interactions when the pointer is on the desktop surface', () => {
    expect(
      canStartPetInteraction({
        pointer,
        petRect,
        presence: 'solid',
        desktopContext: { surface: 'desktop' },
      }),
    ).toEqual({ canStart: true, reason: 'desktop' });
  });

  it('keeps passive mode non-interactive even on the desktop', () => {
    expect(
      canStartPetInteraction({
        pointer,
        petRect,
        presence: 'passive',
        desktopContext: { surface: 'desktop' },
      }),
    ).toEqual({ canStart: false, reason: 'passive' });
  });

  it('can fail closed when desktop context is unknown', () => {
    expect(
      canStartPetInteraction({
        pointer,
        petRect,
        presence: 'solid',
        desktopContext: { surface: 'unknown', allowUnknown: false },
      }),
    ).toEqual({ canStart: false, reason: 'unknown-surface' });
  });
});
