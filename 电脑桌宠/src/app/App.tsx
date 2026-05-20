import { PointerEvent, useEffect, useMemo, useRef, useState } from 'react';
import { normalizePetManifest } from '../pet-assets/normalizePetManifest';
import type { NormalizedPetManifest, RawPetManifest } from '../pet-assets/types';
import { decidePresenceMode, type ForcedPresenceMode, type PresenceMode } from '../pet-core/presence';
import { chooseBestPerch, createIconEdgeCandidates, type Rect } from '../pet-core/perchPlanner';
import { PixiPetStage } from '../pet-renderer/PixiPetStage';
import { DEFAULT_PET_SCALE } from './petPreviewConfig';
import { decidePreviewAction, pickActionBubble } from './previewAction';

const PET_ASSET_ROOT = '/pets/xiaoju';
const ICONS: Rect[] = [
  { x: 62, y: 76, width: 74, height: 94 },
  { x: 62, y: 188, width: 74, height: 94 },
  { x: 62, y: 300, width: 74, height: 94 },
  { x: 170, y: 76, width: 74, height: 94 },
  { x: 170, y: 188, width: 74, height: 94 },
  { x: 170, y: 300, width: 74, height: 94 },
];

interface DesktopIcon {
  id: string;
  label: string;
  rect: Rect;
}

const DESKTOP_ICONS: DesktopIcon[] = ICONS.map((rect, index) => ({
  id: `file-${index}`,
  label: ['PRD', '素材', '小鱼', '代码', '设置', '计划'][index],
  rect,
}));

export function App() {
  const [manifest, setManifest] = useState<NormalizedPetManifest | null>(null);
  const [position, setPosition] = useState({ x: 246, y: 118 });
  const [forcedMode, setForcedMode] = useState<ForcedPresenceMode>('auto');
  const [isDragging, setIsDragging] = useState(false);
  const [hoverStart, setHoverStart] = useState<number | null>(null);
  const [now, setNow] = useState(performance.now());
  const [clickBurst, setClickBurst] = useState(0);
  const [bubble, setBubble] = useState('这块地方不错。');
  const dragOffsetRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    fetch(`${PET_ASSET_ROOT}/codex-pet.json`)
      .then((response) => response.json() as Promise<RawPetManifest>)
      .then((raw) => setManifest(normalizePetManifest(raw)))
      .catch(() =>
        setManifest(
          normalizePetManifest({
            id: 'xiaoju',
            displayName: '小橘',
            spritesheetPath: 'spritesheet.webp',
          }),
        ),
      );
  }, []);

  useEffect(() => {
    if (hoverStart === null) {
      return;
    }
    const interval = window.setInterval(() => setNow(performance.now()), 120);
    return () => window.clearInterval(interval);
  }, [hoverStart]);

  const petSize = useMemo(() => {
    if (!manifest) {
      return { width: 192 * DEFAULT_PET_SCALE, height: 208 * DEFAULT_PET_SCALE };
    }
    return { width: manifest.sprite.cellWidth * DEFAULT_PET_SCALE, height: manifest.sprite.cellHeight * DEFAULT_PET_SCALE };
  }, [manifest]);

  const obstructionScore = useMemo(() => {
    const petRect = { x: position.x, y: position.y, width: petSize.width, height: petSize.height };
    const overlaps = ICONS.filter((icon) => rectsOverlap(petRect, icon)).length;
    return Math.min(100, overlaps * 42);
  }, [petSize.height, petSize.width, position.x, position.y]);

  const hoverMs = hoverStart === null ? 0 : now - hoverStart;
  const presence = decidePresenceMode({
    isDragging,
    nearbyObstructionScore: obstructionScore,
    hoverMs,
    forcedMode,
  });

  const actionState = useMemo(
    () =>
      decidePreviewAction({
        isDragging,
        presence,
        obstructionScore,
        hoverMs,
        clickBurst,
      }),
    [clickBurst, hoverMs, isDragging, obstructionScore, presence],
  );

  useEffect(() => {
    if (!manifest) {
      return;
    }
    setBubble(pickActionBubble(manifest.bubbles, actionState));
  }, [actionState, manifest]);

  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      const inside = pointInRect(
        { x: event.clientX, y: event.clientY },
        { x: position.x, y: position.y, width: petSize.width, height: petSize.height },
      );
      setHoverStart((startedAt) => {
        if (inside) {
          return startedAt ?? performance.now();
        }
        return null;
      });

      if (isDragging) {
        setPosition({
          x: event.clientX - dragOffsetRef.current.x,
          y: event.clientY - dragOffsetRef.current.y,
        });
      }
    };

    const onUp = () => setIsDragging(false);

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [isDragging, petSize.height, petSize.width, position.x, position.y]);

  const perchNearIcons = () => {
    const best = chooseBestPerch(createIconEdgeCandidates(ICONS, petSize), {
      current: position,
      screen: { x: 0, y: 0, width: window.innerWidth, height: window.innerHeight },
      taskbar: { x: 0, y: window.innerHeight - 54, width: window.innerWidth, height: 54 },
      petSize,
    });
    if (best) {
      setPosition({ x: best.x, y: best.y });
      setForcedMode('auto');
    }
  };

  const handlePetPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (presence === 'passive') {
      return;
    }
    dragOffsetRef.current = {
      x: event.clientX - position.x,
      y: event.clientY - position.y,
    };
    setIsDragging(true);
  };

  const handlePetClick = () => {
    if (presence === 'passive') {
      return;
    }
    setClickBurst((value) => Math.min(value + 1, 4));
    window.setTimeout(() => setClickBurst(0), 1600);
  };

  if (!manifest) {
    return <main className="desktop-preview" />;
  }

  const activeState = manifest.states[actionState] ?? manifest.states.idle_sleep;
  const spriteUrl = `${PET_ASSET_ROOT}/${manifest.sprite.file}`;

  return (
    <main className="desktop-preview">
      <div className="desktop-icons" aria-hidden>
        {DESKTOP_ICONS.map((icon) => (
          <button
            key={icon.id}
            className="desktop-icon"
            style={{ left: icon.rect.x, top: icon.rect.y, width: icon.rect.width, height: icon.rect.height }}
            onClick={() => setBubble(`${icon.label} 是你的。`)}
          >
            <span className="icon-glyph" />
            <span>{icon.label}</span>
          </button>
        ))}
      </div>

      <section className="tray-panel">
        <strong>{manifest.displayName}</strong>
        <button type="button" onClick={() => setForcedMode('solid')}>
          实体化
        </button>
        <button type="button" onClick={() => setForcedMode('passive')}>
          防误触
        </button>
        <button type="button" onClick={() => setForcedMode('auto')}>
          自动
        </button>
        <button type="button" onClick={perchNearIcons}>
          趴边缘
        </button>
      </section>

      <div
        className={`pet-shell presence-${presence}`}
        style={{
          left: position.x,
          top: position.y,
          width: petSize.width,
          height: petSize.height,
          cursor: presence === 'passive' ? 'default' : isDragging ? 'grabbing' : 'grab',
          pointerEvents: presence === 'passive' ? 'none' : 'auto',
        }}
        onPointerDown={handlePetPointerDown}
        onClick={handlePetClick}
      >
        <div className="pet-bubble">{bubble}</div>
        <PixiPetStage manifest={manifest} state={activeState} spriteUrl={spriteUrl} scale={DEFAULT_PET_SCALE} />
      </div>

      <div className={`presence-badge presence-${presence}`}>
        {presence === 'solid' && '实体'}
        {presence === 'passive' && '防误触'}
        {presence === 'materializing' && '可抓取'}
        {presence === 'dragging' && '拖动中'}
      </div>
    </main>
  );
}

function rectsOverlap(a: Rect, b: Rect) {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
}

function pointInRect(point: { x: number; y: number }, rect: Rect) {
  return point.x >= rect.x && point.x <= rect.x + rect.width && point.y >= rect.y && point.y <= rect.y + rect.height;
}
