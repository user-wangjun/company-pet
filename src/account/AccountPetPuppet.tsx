import { useEffect, useRef, type MutableRefObject } from "react";
import { DEFAULT_PET_ID, resolvePetAssetUrl } from "../pet-core/petAssets";
import {
  dampAccountPetParameters,
  getAccountPetTargetParameters,
  type AccountPetMood,
  type AccountPetParameters,
  type NormalizedPointer,
} from "./accountPetParameters";
import { getForelegMotion } from "./accountPoseSequence";
import { Live2DPlanetScene } from "./live2dCoreRenderer";

const MODEL_BASE_URL = resolvePetAssetUrl(
  DEFAULT_PET_ID,
  "live2d/runtime/xiaoju-planet-login",
);
const FALLBACK_URL = resolvePetAssetUrl(
  DEFAULT_PET_ID,
  "live2d/planet-scene-source/pose-keys-v3/00-rest.png",
);
const EYE_OVERLAY_URLS = [
  resolvePetAssetUrl(DEFAULT_PET_ID, "live2d/planet-scene-source/layers-v2/20_Eye_L_Whole.png"),
  resolvePetAssetUrl(DEFAULT_PET_ID, "live2d/planet-scene-source/layers-v2/21_Eye_R_Whole.png"),
];
const FORELEG_URLS = [
  resolvePetAssetUrl(DEFAULT_PET_ID, "live2d/planet-scene-source/layers-v3/60_Foreleg_L_Complete.png"),
  resolvePetAssetUrl(DEFAULT_PET_ID, "live2d/planet-scene-source/layers-v3/61_Foreleg_R_Complete.png"),
];
const PLANET_OVERLAY_URL = resolvePetAssetUrl(
  DEFAULT_PET_ID,
  "live2d/planet-scene-source/layers-v2/50_Planet_Foreground.png",
);
const SHOULDER_OCCLUDER_URLS = [
  resolvePetAssetUrl(DEFAULT_PET_ID, "live2d/planet-scene-source/layers-v3/30_Shoulder_Occluder_L.png"),
  resolvePetAssetUrl(DEFAULT_PET_ID, "live2d/planet-scene-source/layers-v3/31_Shoulder_Occluder_R.png"),
];
const INITIAL_PARAMETERS = getAccountPetTargetParameters("idle", { x: 0, y: 0 });

export function AccountPetPuppet({
  mood,
  pointer,
}: {
  mood: AccountPetMood;
  pointer: MutableRefObject<NormalizedPointer>;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const eyeRefs = useRef<Array<HTMLImageElement | null>>([]);
  const forelegRefs = useRef<Array<HTMLImageElement | null>>([]);
  const currentRef = useRef<AccountPetParameters>(INITIAL_PARAMETERS);
  const moodRef = useRef(mood);

  useEffect(() => {
    moodRef.current = mood;
  }, [mood]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let scene: Live2DPlanetScene | null = null;
    let frame = 0;
    let cancelled = false;
    let previous = performance.now();
    const started = previous;

    void Live2DPlanetScene.create(canvas, MODEL_BASE_URL)
      .then((loadedScene) => {
        if (cancelled) {
          loadedScene.destroy();
          return;
        }
        scene = loadedScene;
        canvas.dataset.live2dReady = "true";

        const animate = (now: number) => {
          const delta = Math.min(50, now - previous);
          previous = now;
          const target = getAccountPetTargetParameters(moodRef.current, pointer.current);
          const current = dampAccountPetParameters(currentRef.current, target, delta, 6.8);
          currentRef.current = current;

          const elapsed = (now - started) / 1000;
          const blinkPhase = elapsed % 5.15;
          const naturalBlink = blinkPhase > 4.86
            ? clamp01(1 - Math.abs(blinkPhase - 5) / .14)
            : 0;
          const blink = Math.max(1 - current.eyeOpen, naturalBlink);
          const forelegMotion = getForelegMotion(current.pawCover);
          if (forelegRefs.current[0]) forelegRefs.current[0].style.transform = forelegMotion.leftTransform;
          if (forelegRefs.current[1]) forelegRefs.current[1].style.transform = forelegMotion.rightTransform;

          const eyeOpacity = 1 - blink;
          const eyeTransform = `translate3d(${current.eyeBallX * 2.2}px, ${current.eyeBallY * 1.6}px, 0)`;
          eyeRefs.current.forEach((image) => {
            if (!image) return;
            image.style.opacity = String(eyeOpacity);
            image.style.transform = eyeTransform;
          });
          if (rootRef.current) {
            rootRef.current.dataset.poseProgress = forelegMotion.progress.toFixed(3);
          }
          scene?.render(current, elapsed, blink);
          frame = requestAnimationFrame(animate);
        };

        frame = requestAnimationFrame(animate);
      })
      .catch((error: unknown) => {
        canvas.dataset.live2dError = error instanceof Error ? error.message : "Live2D scene failed";
        console.error(error);
      });

    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      scene?.destroy();
    };
  }, [pointer]);

  return (
    <div
      className="account-puppet account-live2d-scene"
      data-model-url={`${MODEL_BASE_URL}/xiaoju-planet-login.model3.json`}
      ref={rootRef}
    >
      <img className="account-live2d-fallback" alt="" src={FALLBACK_URL} />
      <canvas className="account-live2d-canvas" ref={canvasRef} />
      {EYE_OVERLAY_URLS.map((url, index) => (
        <img
          alt=""
          className="account-live2d-eye-layer"
          key={url}
          ref={(element) => { eyeRefs.current[index] = element; }}
          src={url}
        />
      ))}
      <div className="account-foreleg-rig" aria-hidden="true">
        {FORELEG_URLS.map((url, index) => (
          <img
            alt=""
            className={`account-foreleg-layer account-foreleg-layer-${index === 0 ? "left" : "right"}`}
            key={url}
            ref={(element) => { forelegRefs.current[index] = element; }}
            src={url}
          />
        ))}
      </div>
      <img className="account-planet-overlay" alt="" src={PLANET_OVERLAY_URL} />
      {SHOULDER_OCCLUDER_URLS.map((url) => (
        <img className="account-shoulder-occluder" alt="" key={url} src={url} />
      ))}
    </div>
  );
}

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));
