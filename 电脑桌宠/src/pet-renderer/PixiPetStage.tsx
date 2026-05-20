import { useEffect, useRef } from 'react';
import { Application, BaseTexture, Rectangle, SCALE_MODES, Sprite, Texture } from 'pixi.js';
import type { NormalizedPetManifest, PetStateConfig } from '../pet-assets/types';

interface PixiPetStageProps {
  manifest: NormalizedPetManifest;
  state: PetStateConfig;
  spriteUrl: string;
  scale: number;
  paused?: boolean;
}

export function PixiPetStage({ manifest, state, spriteUrl, scale, paused = false }: PixiPetStageProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) {
      return;
    }

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

    const baseTexture = BaseTexture.from(spriteUrl);
    baseTexture.scaleMode = SCALE_MODES.LINEAR;

    const sprite = new Sprite();
    sprite.width = manifest.sprite.cellWidth;
    sprite.height = manifest.sprite.cellHeight;
    app.stage.addChild(sprite);

    let elapsedMs = 0;
    let currentFrame = -1;

    const setFrame = (frame: number) => {
      if (frame === currentFrame) {
        return;
      }
      currentFrame = frame;
      sprite.texture = new Texture(
        baseTexture,
        new Rectangle(
          frame * manifest.sprite.cellWidth,
          state.row * manifest.sprite.cellHeight,
          manifest.sprite.cellWidth,
          manifest.sprite.cellHeight,
        ),
      );
    };

    setFrame(0);

    app.ticker.add((tickerDelta) => {
      if (paused) {
        return;
      }

      elapsedMs += app.ticker.deltaMS * tickerDelta;
      const frameDurationMs = 1000 / state.fps;
      const rawFrame = Math.floor(elapsedMs / frameDurationMs);
      const frame = state.loop ? rawFrame % state.frames : Math.min(rawFrame, state.frames - 1);
      setFrame(frame);
    });

    return () => {
      app.destroy(true, { children: true, texture: false, baseTexture: false });
    };
  }, [manifest.sprite.cellHeight, manifest.sprite.cellWidth, paused, scale, spriteUrl, state]);

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
