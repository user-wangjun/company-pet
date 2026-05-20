import { useEffect, useRef } from 'react';
import { Application, Assets, Rectangle, SCALE_MODES, Sprite, Texture } from 'pixi.js';
import type { NormalizedPetManifest, PetStateConfig } from '../pet-assets/types';
import { getFrameBlend, getTransitionPose } from './animationTransition';

interface PixiPetStageProps {
  manifest: NormalizedPetManifest;
  state: PetStateConfig;
  spriteUrl: string;
  scale: number;
  paused?: boolean;
}

export function PixiPetStage({ manifest, state, spriteUrl, scale, paused = false }: PixiPetStageProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const stateRef = useRef(state);
  const pausedRef = useRef(paused);
  const transitionRef = useRef<null | { startedAtMs: number; durationMs: number }>(null);
  const activeSpriteRef = useRef<Sprite | null>(null);
  const activeNextFrameSpriteRef = useRef<Sprite | null>(null);
  const outgoingSpriteRef = useRef<Sprite | null>(null);

  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  useEffect(() => {
    if (stateRef.current === state) {
      return;
    }
    const activeSprite = activeSpriteRef.current;
    const activeNextFrameSprite = activeNextFrameSpriteRef.current;
    const outgoingSprite = outgoingSpriteRef.current;
    if (activeSprite && outgoingSprite && activeSprite.texture !== Texture.EMPTY) {
      outgoingSprite.texture = activeSprite.texture;
      outgoingSprite.alpha = 1;
      outgoingSprite.visible = true;
      activeSprite.alpha = 0;
      if (activeNextFrameSprite) {
        activeNextFrameSprite.alpha = 0;
      }
    }
    stateRef.current = state;
    transitionRef.current = {
      startedAtMs: performance.now(),
      durationMs: 320,
    };
  }, [state]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) {
      return;
    }

    let disposed = false;
    host.innerHTML = '';
    const app = new Application({
      width: manifest.sprite.cellWidth,
      height: manifest.sprite.cellHeight,
      backgroundAlpha: 0,
      antialias: true,
      autoDensity: true,
      resolution: Math.min(window.devicePixelRatio || 1, 2),
    });

    host.appendChild(app.view as HTMLCanvasElement);

    let elapsedMs = 0;
    let currentFrame = -1;
    let currentNextFrame = -1;
    let currentRow = -1;
    let currentNextRow = -1;
    let activeSprite: Sprite | null = null;
    let activeNextFrameSprite: Sprite | null = null;
    let outgoingSprite: Sprite | null = null;
    let baseTexture: Texture['baseTexture'] | null = null;

    const makeFrameTexture = (frame: number, row: number) => {
      if (!baseTexture) {
        return Texture.EMPTY;
      }

      return new Texture(
        baseTexture,
        new Rectangle(
          frame * manifest.sprite.cellWidth,
          row * manifest.sprite.cellHeight,
          manifest.sprite.cellWidth,
          manifest.sprite.cellHeight,
        ),
      );
    };

    const setFrame = (frame: number, nextFrame: number, row: number) => {
      if (!activeSprite || !activeNextFrameSprite) {
        return;
      }
      if (frame !== currentFrame || row !== currentRow) {
        currentFrame = frame;
        currentRow = row;
        activeSprite.texture = makeFrameTexture(frame, row);
      }
      if (nextFrame !== currentNextFrame || row !== currentNextRow) {
        currentNextFrame = nextFrame;
        currentNextRow = row;
        activeNextFrameSprite.texture = makeFrameTexture(nextFrame, row);
      }
    };

    app.ticker.add((tickerDelta) => {
      if (pausedRef.current || !activeSprite || !activeNextFrameSprite || !outgoingSprite || !baseTexture) {
        return;
      }

      elapsedMs += app.ticker.deltaMS * tickerDelta;
      const activeState = stateRef.current;
      const frameDurationMs = 1000 / activeState.fps;
      const frameBlend = getFrameBlend({
        elapsedMs,
        frameDurationMs,
        frames: activeState.frames,
        loop: activeState.loop,
      });
      setFrame(frameBlend.currentFrame, frameBlend.nextFrame, activeState.row);

      if (transitionRef.current) {
        const elapsedTransitionMs = performance.now() - transitionRef.current.startedAtMs;
        const pose = getTransitionPose(elapsedTransitionMs, transitionRef.current.durationMs);
        applyPose(
          activeSprite,
          { ...pose.incoming, alpha: pose.incoming.alpha * (1 - frameBlend.alpha) },
          manifest.sprite.cellWidth,
          manifest.sprite.cellHeight,
        );
        applyPose(
          activeNextFrameSprite,
          { ...pose.incoming, alpha: pose.incoming.alpha * frameBlend.alpha },
          manifest.sprite.cellWidth,
          manifest.sprite.cellHeight,
        );
        applyPose(outgoingSprite, pose.outgoing, manifest.sprite.cellWidth, manifest.sprite.cellHeight);
        outgoingSprite.visible = pose.outgoing.alpha > 0.01;
        activeNextFrameSprite.visible = frameBlend.alpha > 0.01;

        if (pose.incoming.alpha >= 1) {
          transitionRef.current = null;
          applyFrameBlendPose(activeSprite, activeNextFrameSprite, frameBlend.alpha, manifest.sprite.cellWidth, manifest.sprite.cellHeight);
          outgoingSprite.visible = false;
        }
      } else {
        applyFrameBlendPose(activeSprite, activeNextFrameSprite, frameBlend.alpha, manifest.sprite.cellWidth, manifest.sprite.cellHeight);
        outgoingSprite.visible = false;
      }
    });

    Assets.load<Texture>(spriteUrl).then((texture) => {
      if (disposed) {
        return;
      }

      baseTexture = texture.baseTexture;
      baseTexture.scaleMode = SCALE_MODES.LINEAR;

      outgoingSprite = new Sprite(Texture.EMPTY);
      configureSprite(outgoingSprite, manifest.sprite.cellWidth, manifest.sprite.cellHeight);
      outgoingSprite.visible = false;
      app.stage.addChild(outgoingSprite);

      activeSprite = new Sprite(Texture.EMPTY);
      configureSprite(activeSprite, manifest.sprite.cellWidth, manifest.sprite.cellHeight);
      app.stage.addChild(activeSprite);

      activeNextFrameSprite = new Sprite(Texture.EMPTY);
      configureSprite(activeNextFrameSprite, manifest.sprite.cellWidth, manifest.sprite.cellHeight);
      activeNextFrameSprite.visible = false;
      app.stage.addChild(activeNextFrameSprite);

      activeSpriteRef.current = activeSprite;
      activeNextFrameSpriteRef.current = activeNextFrameSprite;
      outgoingSpriteRef.current = outgoingSprite;

      setFrame(0, stateRef.current.frames > 1 ? 1 : 0, stateRef.current.row);
    });

    return () => {
      disposed = true;
      activeSpriteRef.current = null;
      activeNextFrameSpriteRef.current = null;
      outgoingSpriteRef.current = null;
      app.destroy(true, { children: true, texture: false, baseTexture: false });
    };
  }, [manifest.sprite.cellHeight, manifest.sprite.cellWidth, spriteUrl]);

  return (
    <div
      ref={hostRef}
      className="pet-pixi-stage"
      style={{
        width: manifest.sprite.cellWidth * scale,
        height: manifest.sprite.cellHeight * scale,
      }}
    />
  );
}

interface SpritePose {
  alpha: number;
  x: number;
  y: number;
  scaleX: number;
  scaleY: number;
}

function configureSprite(sprite: Sprite, cellWidth: number, cellHeight: number) {
  sprite.anchor.set(0.5, 1);
  sprite.position.set(cellWidth / 2, cellHeight);
}

function applyPose(sprite: Sprite, pose: SpritePose | null, cellWidth: number, cellHeight: number) {
  const nextPose = pose ?? {
    alpha: 1,
    x: 0,
    y: 0,
    scaleX: 1,
    scaleY: 1,
  };
  sprite.alpha = nextPose.alpha;
  sprite.scale.set(nextPose.scaleX, nextPose.scaleY);
  sprite.position.set(cellWidth / 2 + nextPose.x, cellHeight + nextPose.y);
}

function applyFrameBlendPose(current: Sprite, next: Sprite, nextAlpha: number, cellWidth: number, cellHeight: number) {
  applyPose(
    current,
    {
      alpha: 1 - nextAlpha,
      x: 0,
      y: 0,
      scaleX: 1,
      scaleY: 1,
    },
    cellWidth,
    cellHeight,
  );
  applyPose(
    next,
    {
      alpha: nextAlpha,
      x: 0,
      y: 0,
      scaleX: 1,
      scaleY: 1,
    },
    cellWidth,
    cellHeight,
  );
  next.visible = nextAlpha > 0.01;
}
