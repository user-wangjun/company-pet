import { useEffect, useRef } from 'react';
import { Application, Assets, Rectangle, SCALE_MODES, Sprite, Texture } from 'pixi.js';
import type { NormalizedPetManifest, PetStateConfig } from '../pet-assets/types';
import { getTransitionPose } from './animationTransition';

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
  const outgoingSpriteRef = useRef<Sprite | null>(null);

  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  useEffect(() => {
    if (stateRef.current === state) {
      return;
    }
    const activeSprite = activeSpriteRef.current;
    const outgoingSprite = outgoingSpriteRef.current;
    if (activeSprite && outgoingSprite && activeSprite.texture !== Texture.EMPTY) {
      outgoingSprite.texture = activeSprite.texture;
      outgoingSprite.alpha = 1;
      outgoingSprite.visible = true;
      activeSprite.alpha = 0;
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
    let currentRow = -1;
    let activeSprite: Sprite | null = null;
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

    const setFrame = (frame: number, row: number) => {
      if (!activeSprite || (frame === currentFrame && row === currentRow)) {
        return;
      }
      currentFrame = frame;
      currentRow = row;
      activeSprite.texture = makeFrameTexture(frame, row);
    };

    app.ticker.add((tickerDelta) => {
      if (pausedRef.current || !activeSprite || !outgoingSprite || !baseTexture) {
        return;
      }

      elapsedMs += app.ticker.deltaMS * tickerDelta;
      const activeState = stateRef.current;
      const frameDurationMs = 1000 / activeState.fps;
      const rawFrame = Math.floor(elapsedMs / frameDurationMs);
      const frame = activeState.loop ? rawFrame % activeState.frames : Math.min(rawFrame, activeState.frames - 1);
      setFrame(frame, activeState.row);

      if (transitionRef.current) {
        const elapsedTransitionMs = performance.now() - transitionRef.current.startedAtMs;
        const pose = getTransitionPose(elapsedTransitionMs, transitionRef.current.durationMs);
        applyPose(activeSprite, pose.incoming, manifest.sprite.cellWidth, manifest.sprite.cellHeight);
        applyPose(outgoingSprite, pose.outgoing, manifest.sprite.cellWidth, manifest.sprite.cellHeight);
        outgoingSprite.visible = pose.outgoing.alpha > 0.01;

        if (pose.incoming.alpha >= 1) {
          transitionRef.current = null;
          applyPose(activeSprite, pose.incoming, manifest.sprite.cellWidth, manifest.sprite.cellHeight);
          outgoingSprite.visible = false;
        }
      } else {
        applyPose(activeSprite, null, manifest.sprite.cellWidth, manifest.sprite.cellHeight);
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
      activeSpriteRef.current = activeSprite;
      outgoingSpriteRef.current = outgoingSprite;

      setFrame(0, stateRef.current.row);
    });

    return () => {
      disposed = true;
      activeSpriteRef.current = null;
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
