export type ForelegMotion = {
  progress: number;
  leftTransform: string;
  rightTransform: string;
};

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));

const smoothstep = (edge0: number, edge1: number, value: number) => {
  const progress = clamp01((value - edge0) / (edge1 - edge0));
  return progress * progress * (3 - (2 * progress));
};

const mix = (from: number, to: number, progress: number) => from + ((to - from) * progress);

const transformFor = (
  progress: number,
  rest: { x: number; y: number; rotation: number; scaleY: number },
) => [
  `translate3d(${mix(rest.x, 0, progress).toFixed(3)}%, ${mix(rest.y, 0, progress).toFixed(3)}%, 0)`,
  `rotate(${mix(rest.rotation, 0, progress).toFixed(3)}deg)`,
  `scaleY(${mix(rest.scaleY, 1, progress).toFixed(4)})`,
].join(" ");

/**
 * Drives the two real foreleg layers along one reversible, continuous path.
 * The slight timing offset keeps the movement organic without ever duplicating
 * a paw or cross-fading between whole kitten images.
 */
export function getForelegMotion(pawCover: number): ForelegMotion {
  const progress = smoothstep(0, 1, clamp01(pawCover));
  const leftProgress = smoothstep(0, .88, progress);
  const rightProgress = smoothstep(.08, 1, progress);

  return {
    progress,
    leftTransform: transformFor(leftProgress, {
      x: 2.4,
      y: -8.5,
      rotation: -9,
      scaleY: .42,
    }),
    rightTransform: transformFor(rightProgress, {
      x: 2.5,
      y: -12,
      rotation: 27,
      scaleY: .46,
    }),
  };
}
