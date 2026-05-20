import { describe, expect, it } from 'vitest';
import { getFrameBlend, getTransitionAlpha, getTransitionPose } from './animationTransition';

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

describe('getTransitionPose', () => {
  it('starts the incoming state slightly lower and fully settles by the end', () => {
    const start = getTransitionPose(0, 320);
    const end = getTransitionPose(320, 320);

    expect(start.incoming.alpha).toBe(0);
    expect(start.incoming.y).toBeGreaterThan(0);
    expect(end.incoming).toEqual({ alpha: 1, x: 0, y: 0, scaleX: 1, scaleY: 1 });
    expect(end.outgoing.alpha).toBe(0);
  });

  it('adds a small body-like squash and lift through the middle of the transition', () => {
    const middle = getTransitionPose(160, 320);

    expect(middle.incoming.alpha).toBeGreaterThan(0.45);
    expect(middle.incoming.alpha).toBeLessThan(0.55);
    expect(middle.incoming.y).toBeLessThan(0);
    expect(middle.incoming.scaleX).toBeGreaterThan(1);
    expect(middle.incoming.scaleY).toBeLessThan(1);
    expect(middle.outgoing.y).toBeGreaterThan(0);
  });
});

describe('getFrameBlend', () => {
  it('keeps the current frame crisp until it approaches the next frame boundary', () => {
    const blend = getFrameBlend({
      elapsedMs: 125,
      frameDurationMs: 250,
      frames: 6,
      loop: true,
    });

    expect(blend.currentFrame).toBe(0);
    expect(blend.nextFrame).toBe(1);
    expect(blend.alpha).toBe(0);
  });

  it('blends toward the next frame near the end of the current frame', () => {
    const blend = getFrameBlend({
      elapsedMs: 225,
      frameDurationMs: 250,
      frames: 6,
      loop: true,
    });

    expect(blend.currentFrame).toBe(0);
    expect(blend.nextFrame).toBe(1);
    expect(blend.alpha).toBeGreaterThan(0.75);
  });

  it('wraps to the first frame for looping actions', () => {
    const blend = getFrameBlend({
      elapsedMs: 5 * 250 + 180,
      frameDurationMs: 250,
      frames: 6,
      loop: true,
    });

    expect(blend.currentFrame).toBe(5);
    expect(blend.nextFrame).toBe(0);
    expect(blend.alpha).toBeGreaterThan(0);
  });

  it('maps non-contiguous frame sequences so idle actions can skip disruptive frames', () => {
    const blend = getFrameBlend({
      elapsedMs: 3 * 250 + 225,
      frameDurationMs: 250,
      frames: 5,
      loop: true,
      frameSequence: [0, 1, 2, 4, 5],
    });

    expect(blend.currentFrame).toBe(4);
    expect(blend.nextFrame).toBe(5);
    expect(blend.alpha).toBeGreaterThan(0.75);
  });

  it('does not blend past the final frame for non-looping actions', () => {
    const blend = getFrameBlend({
      elapsedMs: 5 * 250 + 180,
      frameDurationMs: 250,
      frames: 6,
      loop: false,
    });

    expect(blend.currentFrame).toBe(5);
    expect(blend.nextFrame).toBe(5);
    expect(blend.alpha).toBe(0);
  });
});
