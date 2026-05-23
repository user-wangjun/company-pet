export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Point {
  x: number;
  y: number;
}

export type PerchType = 'icon-edge' | 'icon-cluster-edge' | 'screen-corner' | 'user-anchor';

export interface PerchCandidate extends Point {
  type: PerchType;
  score: number;
  reason: string;
}

export interface PerchContext {
  current: Point;
  screen: Rect;
  taskbar?: Rect;
  petSize?: { width: number; height: number };
}

const DEFAULT_PET_SIZE = { width: 192, height: 208 };

export function createIconEdgeCandidates(
  icons: Rect[],
  petSize = DEFAULT_PET_SIZE,
): PerchCandidate[] {
  return icons.flatMap((icon) => {
    const horizontalGap = 10;
    const verticalGap = 8;
    return [
      {
        x: icon.x + icon.width / 2 - petSize.width / 2,
        y: icon.y + icon.height - petSize.height - 16,
        type: 'icon-edge' as const,
        score: 95,
        reason: 'hug icon center',
      },
      {
        x: icon.x + icon.width + horizontalGap,
        y: icon.y + icon.height - petSize.height,
        type: 'icon-edge' as const,
        score: 78,
        reason: 'right icon edge',
      },
      {
        x: icon.x - petSize.width - horizontalGap,
        y: icon.y + icon.height - petSize.height,
        type: 'icon-edge' as const,
        score: 74,
        reason: 'left icon edge',
      },
      {
        x: icon.x,
        y: icon.y - petSize.height - verticalGap,
        type: 'icon-edge' as const,
        score: 70,
        reason: 'top icon edge',
      },
      {
        x: icon.x,
        y: icon.y + icon.height + verticalGap,
        type: 'icon-edge' as const,
        score: 68,
        reason: 'bottom icon edge',
      },
    ];
  });
}

export function chooseBestPerch(candidates: PerchCandidate[], context: PerchContext): PerchCandidate | null {
  const petSize = context.petSize ?? DEFAULT_PET_SIZE;
  const safe = candidates
    .filter((candidate) => isInsideScreen(candidate, context.screen, petSize))
    .filter((candidate) => !context.taskbar || !overlaps(toRect(candidate, petSize), context.taskbar));

  if (safe.length === 0) {
    return null;
  }

  return [...safe].sort((a, b) => scoreCandidate(b, context.current) - scoreCandidate(a, context.current))[0];
}

function scoreCandidate(candidate: PerchCandidate, current: Point): number {
  const distance = Math.hypot(candidate.x - current.x, candidate.y - current.y);
  const closenessBonus = Math.max(0, 40 - distance / 20);
  return candidate.score + closenessBonus;
}

function isInsideScreen(candidate: Point, screen: Rect, petSize: { width: number; height: number }) {
  return (
    candidate.x >= screen.x &&
    candidate.y >= screen.y &&
    candidate.x + petSize.width <= screen.x + screen.width &&
    candidate.y + petSize.height <= screen.y + screen.height
  );
}

function toRect(point: Point, size: { width: number; height: number }): Rect {
  return {
    x: point.x,
    y: point.y,
    width: size.width,
    height: size.height,
  };
}

function overlaps(a: Rect, b: Rect): boolean {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
}
