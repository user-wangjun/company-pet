import { describe, expect, it } from 'vitest';
import { readDesktopInteractionContext, type DesktopContextInvoker } from './desktopInteractionContext';

describe('readDesktopInteractionContext', () => {
  it('asks the native layer for the surface under the pointer', async () => {
    const calls: Array<{ command: string; args: unknown }> = [];
    const invoke: DesktopContextInvoker = async (command, args) => {
      calls.push({ command, args });
      return {
        surface: 'foreground-window',
        foregroundWindowRect: { x: 0, y: 0, width: 640, height: 480 },
      };
    };

    await expect(readDesktopInteractionContext({ x: 12.4, y: 35.8 }, invoke)).resolves.toEqual({
      surface: 'foreground-window',
      foregroundWindowRect: { x: 0, y: 0, width: 640, height: 480 },
    });
    expect(calls).toEqual([
      {
        command: 'desktop_interaction_context_at',
        args: { x: 12, y: 36 },
      },
    ]);
  });

  it('falls back to an unknown surface when native sensing is unavailable', async () => {
    const invoke: DesktopContextInvoker = async () => {
      throw new Error('command not registered');
    };

    await expect(readDesktopInteractionContext({ x: 10, y: 20 }, invoke)).resolves.toEqual({
      surface: 'unknown',
      allowUnknown: true,
    });
  });
});
