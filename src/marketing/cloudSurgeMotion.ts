export type CloudSurgeLayerFrame = {
  transform: string;
  opacity: string;
};

export type CloudSurgeFrame = {
  a: CloudSurgeLayerFrame;
  b: CloudSurgeLayerFrame;
  c: CloudSurgeLayerFrame;
};

type CloudSurgeMotionOptions = {
  getNow?: () => number;
  requestFrame?: (callback: FrameRequestCallback) => number;
  cancelFrame?: (handle: number) => void;
};

function formatPercent(value: number): string {
  return `${value.toFixed(3)}%`;
}

function formatUnit(value: number): string {
  return value.toFixed(3);
}

function createLayerTransform({
  x,
  y,
  scaleX,
  scaleY,
}: {
  x: number;
  y: number;
  scaleX: number;
  scaleY: number;
}): string {
  return `translate3d(${formatPercent(x)}, ${formatPercent(y)}, 0) scale3d(${formatUnit(scaleX)}, ${formatUnit(scaleY)}, 1)`;
}

export function getCloudSurgeFrame(elapsedSeconds: number): CloudSurgeFrame {
  const a = Math.sin(elapsedSeconds * 0.62);
  const b = Math.cos(elapsedSeconds * 0.48);
  const c = Math.sin(elapsedSeconds * 0.38 + 1.4);

  return {
    a: {
      transform: createLayerTransform({
        x: -1.4 + a * 2.6,
        y: 0.5 - b * 1.4,
        scaleX: 1.05 + b * 0.045,
        scaleY: 1.02 + a * 0.06,
      }),
      opacity: formatUnit(0.58 + c * 0.08),
    },
    b: {
      transform: createLayerTransform({
        x: 1.8 - b * 3.1,
        y: 0.9 + a * 1.1,
        scaleX: 1.08 + a * 0.055,
        scaleY: 1.0 + c * 0.08,
      }),
      opacity: formatUnit(0.46 + b * 0.07),
    },
    c: {
      transform: createLayerTransform({
        x: -0.8 + c * 2.2,
        y: 0.6 - a * 1.3,
        scaleX: 1.06 + c * 0.05,
        scaleY: 1.05 + b * 0.09,
      }),
      opacity: formatUnit(0.32 + a * 0.06),
    },
  };
}

export function applyCloudSurgeFrame(
  root: HTMLElement,
  frame: CloudSurgeFrame,
): void {
  root.style.setProperty("--cloud-a-transform", frame.a.transform);
  root.style.setProperty("--cloud-a-opacity", frame.a.opacity);
  root.style.setProperty("--cloud-b-transform", frame.b.transform);
  root.style.setProperty("--cloud-b-opacity", frame.b.opacity);
  root.style.setProperty("--cloud-c-transform", frame.c.transform);
  root.style.setProperty("--cloud-c-opacity", frame.c.opacity);
}

export function startCloudSurgeMotion(
  root: HTMLElement,
  {
    getNow = () => window.performance.now(),
    requestFrame = (callback) => window.requestAnimationFrame(callback),
    cancelFrame = (handle) => window.cancelAnimationFrame(handle),
  }: CloudSurgeMotionOptions = {},
): () => void {
  const startedAt = getNow();
  let frameHandle: number | null = null;
  let isStopped = false;

  const draw = () => {
    if (isStopped) return;

    const elapsedSeconds = (getNow() - startedAt) / 1000;
    applyCloudSurgeFrame(root, getCloudSurgeFrame(elapsedSeconds));
    frameHandle = requestFrame(draw);
  };

  draw();

  return () => {
    isStopped = true;
    if (frameHandle !== null) {
      cancelFrame(frameHandle);
    }
  };
}
