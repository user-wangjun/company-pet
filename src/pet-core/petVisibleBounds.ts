import { buildAnimationFrameRects } from "./animationRows";
import type { Bounds } from "./interaction";
import { resolvePetAssetUrl, type PetManifest } from "./petAssets";
import { PET_VISUAL_SCALE, PET_WINDOW_HEIGHT, PET_WINDOW_WIDTH } from "./visual";

const FRAME_WIDTH = 192;
const FRAME_HEIGHT = 208;
const PET_BOTTOM_INSET_PX = 6;
const ALPHA_THRESHOLD = 8;

type FrameSample = {
  specScale: number;
  offsetX: number;
  offsetY: number;
  sourceWidth: number;
  sourceHeight: number;
  frameRect: { x: number; y: number; width: number; height: number } | null;
};

const DEFAULT_PET_VISIBLE_BOUNDS: Bounds = {
  x: 40,
  y: 108,
  width: 85,
  height: 100,
};

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`Unable to load pet sprite sheet: ${url}`));
    image.src = url;
  });
}

function scanFrameBounds(
  ctx: CanvasRenderingContext2D,
  sample: FrameSample,
): Bounds | null {
  const rect = sample.frameRect ?? {
    x: 0,
    y: 0,
    width: sample.sourceWidth,
    height: sample.sourceHeight,
  };
  const { data } = ctx.getImageData(rect.x, rect.y, rect.width, rect.height);
  let minX = rect.width;
  let minY = rect.height;
  let maxX = -1;
  let maxY = -1;

  for (let y = 0; y < rect.height; y += 1) {
    for (let x = 0; x < rect.width; x += 1) {
      const alpha = data[(y * rect.width + x) * 4 + 3];
      if (alpha <= ALPHA_THRESHOLD) continue;
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }

  if (maxX < 0 || maxY < 0) return null;

  const left = Math.min(minX, rect.width - (maxX + 1));
  const right = Math.max(maxX + 1, rect.width - minX);

  return {
    x: left,
    y: minY,
    width: right - left,
    height: maxY + 1 - minY,
  };
}

function unionBounds(bounds: Bounds | null, next: Bounds): Bounds {
  if (!bounds) return next;
  const left = Math.min(bounds.x, next.x);
  const top = Math.min(bounds.y, next.y);
  const right = Math.max(bounds.x + bounds.width, next.x + next.width);
  const bottom = Math.max(bounds.y + bounds.height, next.y + next.height);
  return {
    x: left,
    y: top,
    width: right - left,
    height: bottom - top,
  };
}

function toWindowBounds(sample: FrameSample, frameBounds: Bounds): Bounds {
  const scale = PET_VISUAL_SCALE * sample.specScale;
  const left = PET_WINDOW_WIDTH / 2 - (sample.sourceWidth / 2) * scale + frameBounds.x * scale + sample.offsetX;
  const top = PET_WINDOW_HEIGHT - PET_BOTTOM_INSET_PX - sample.sourceHeight * scale + frameBounds.y * scale + sample.offsetY;

  return {
    x: left,
    y: top,
    width: frameBounds.width * scale,
    height: frameBounds.height * scale,
  };
}

export async function measurePetVisibleBounds(manifest: PetManifest): Promise<Bounds> {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return DEFAULT_PET_VISIBLE_BOUNDS;
  }

  try {
    const samplesByUrl = new Map<string, FrameSample[]>();
    for (const spec of Object.values(manifest.animations)) {
      const scale = spec.scale ?? 1;
      const offsetX = spec.offsetX ?? 0;
      const offsetY = spec.offsetY ?? 0;
      const spriteSheetUrl = resolvePetAssetUrl(manifest.id, spec.spritesheetPath ?? manifest.spritesheetPath);
      const sheetSamples = samplesByUrl.get(spriteSheetUrl) ?? [];
      for (const rect of buildAnimationFrameRects(spec, FRAME_WIDTH, FRAME_HEIGHT)) {
        sheetSamples.push({
          specScale: scale,
          offsetX,
          offsetY,
          sourceWidth: FRAME_WIDTH,
          sourceHeight: FRAME_HEIGHT,
          frameRect: rect,
        });
      }
      samplesByUrl.set(spriteSheetUrl, sheetSamples);

      if (spec.finishFramePath) {
        const finishUrl = resolvePetAssetUrl(manifest.id, spec.finishFramePath);
        const finishSamples = samplesByUrl.get(finishUrl) ?? [];
        finishSamples.push({
          specScale: scale,
          offsetX,
          offsetY,
          sourceWidth: 0,
          sourceHeight: 0,
          frameRect: null,
        });
        samplesByUrl.set(finishUrl, finishSamples);
      }
    }

    let union: Bounds | null = null;
    for (const [url, samples] of samplesByUrl) {
      const image = await loadImage(url);
      const canvas = document.createElement("canvas");
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) continue;
      ctx.drawImage(image, 0, 0);

      for (const sample of samples) {
        const resolvedSample = sample.frameRect
          ? sample
          : {
              ...sample,
              sourceWidth: image.naturalWidth,
              sourceHeight: image.naturalHeight,
            };
        const frameBounds = scanFrameBounds(ctx, resolvedSample);
        if (!frameBounds) continue;
        union = unionBounds(union, toWindowBounds(resolvedSample, frameBounds));
      }
    }

    if (!union) return DEFAULT_PET_VISIBLE_BOUNDS;
    return {
      x: Math.floor(union.x),
      y: Math.floor(union.y),
      width: Math.ceil(union.x + union.width) - Math.floor(union.x),
      height: Math.ceil(union.y + union.height) - Math.floor(union.y),
    };
  } catch {
    return DEFAULT_PET_VISIBLE_BOUNDS;
  }
}

export { DEFAULT_PET_VISIBLE_BOUNDS };
