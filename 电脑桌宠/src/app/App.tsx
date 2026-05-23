import { MouseEvent as ReactMouseEvent, PointerEvent, useEffect, useMemo, useRef, useState } from 'react';
import { normalizePetManifest } from '../pet-assets/normalizePetManifest';
import type { NormalizedPetManifest, RawPetManifest } from '../pet-assets/types';
import { decidePresenceMode, type ForcedPresenceMode, type PresenceMode } from '../pet-core/presence';
import { canStartPetInteraction } from '../pet-core/interactionGate';
import { chooseBestPerch, createIconEdgeCandidates, type Rect } from '../pet-core/perchPlanner';
import { PixiPetStage } from '../pet-renderer/PixiPetStage';
import { readDesktopInteractionContext } from './desktopInteractionContext';
import { DEFAULT_PET_SCALE } from './petPreviewConfig';
import { TICKLE_HOLD_MS, decidePreviewAction, pickActionBubble } from './previewAction';
import { checkForAppUpdate } from './updateService';

const PET_ASSET_ROOT = '/pets/xiaoju';
const APP_VERSION = import.meta.env.VITE_APP_VERSION ?? '0.1.0';
const UPDATE_MANIFEST_URL = import.meta.env.VITE_UPDATE_MANIFEST_URL ?? '';
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
  const [isCheckingUpdate, setIsCheckingUpdate] = useState(false);
  const dragOffsetRef = useRef({ x: 0, y: 0 });
  const clearTickleTimeoutRef = useRef<number | null>(null);
  const activePointerIdRef = useRef<number | null>(null);
  const lastActivityRef = useRef(performance.now());

  const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
  const dragStartScreenRef = useRef({ x: 0, y: 0 });
  const initialWindowPosRef = useRef({ x: 0, y: 0 });
  const scaleFactorRef = useRef(1.0);

  const petSize = useMemo(() => {
    if (!manifest) {
      return { width: 192 * DEFAULT_PET_SCALE, height: 208 * DEFAULT_PET_SCALE };
    }
    return { width: manifest.sprite.cellWidth * DEFAULT_PET_SCALE, height: manifest.sprite.cellHeight * DEFAULT_PET_SCALE };
  }, [manifest]);

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
    return () => {
      if (clearTickleTimeoutRef.current !== null) {
        window.clearTimeout(clearTickleTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (hoverStart === null) {
      return;
    }
    const interval = window.setInterval(() => setNow(performance.now()), 120);
    return () => window.clearInterval(interval);
  }, [hoverStart]);

  useEffect(() => {
    const updateActivity = () => {
      lastActivityRef.current = performance.now();
    };

    window.addEventListener('mousemove', updateActivity);
    window.addEventListener('mousedown', updateActivity);
    window.addEventListener('keydown', updateActivity);

    return () => {
      window.removeEventListener('mousemove', updateActivity);
      window.removeEventListener('mousedown', updateActivity);
      window.removeEventListener('keydown', updateActivity);
    };
  }, []);

  useEffect(() => {
    if (isDragging || forcedMode === 'passive') {
      return;
    }

    const checkIdle = window.setInterval(() => {
      const timeSinceLastActivity = performance.now() - lastActivityRef.current;
      if (timeSinceLastActivity >= 15000) {
        readDesktopInteractionContext({
          x: position.x + petSize.width / 2,
          y: position.y + petSize.height / 2,
        }).then((desktopContext) => {
          const isOnDesktop =
            desktopContext.surface === 'desktop' ||
            (desktopContext.surface === 'unknown' && desktopContext.allowUnknown !== false);

          if (!isOnDesktop) {
            return; // Not on desktop (e.g. floating over active application window), abort auto-perch!
          }

          // Check if we are already perched
          const perched = ICONS.some((icon) => {
            const candidates = createIconEdgeCandidates([icon], petSize);
            return candidates.some((cand) => Math.hypot(cand.x - position.x, cand.y - position.y) < 2);
          });

          if (!perched) {
            const best = chooseBestPerch(createIconEdgeCandidates(ICONS, petSize), {
              current: position,
              screen: { x: 0, y: 0, width: window.innerWidth, height: window.innerHeight },
              taskbar: { x: 0, y: window.innerHeight - 54, width: window.innerWidth, height: 54 },
              petSize,
            });

            if (best) {
              setPosition({ x: best.x, y: best.y });
              setBubble('这里舒服。');
            }
          }
        });
      }
    }, 1000);

    return () => window.clearInterval(checkIdle);
  }, [isDragging, position, petSize, forcedMode]);



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
        if (isTauri) {
          const deltaX = (event.screenX - dragStartScreenRef.current.x) * scaleFactorRef.current;
          const deltaY = (event.screenY - dragStartScreenRef.current.y) * scaleFactorRef.current;
          const newX = Math.round(initialWindowPosRef.current.x + deltaX);
          const newY = Math.round(initialWindowPosRef.current.y + deltaY);
          
          Promise.all([
            import('@tauri-apps/api/window'),
            import('@tauri-apps/api/dpi')
          ]).then(([{ getCurrentWindow }, { PhysicalPosition }]) => {
            getCurrentWindow().setPosition(new PhysicalPosition(newX, newY)).catch(console.error);
          });
        } else {
          setPosition({
            x: event.clientX - dragOffsetRef.current.x,
            y: event.clientY - dragOffsetRef.current.y,
          });
        }
      }
    };

    const onUp = (event: MouseEvent) => {
      if (isDragging) {
        if (isTauri) {
          setIsDragging(false);
          activePointerIdRef.current = null;
          return;
        }

        const finalX = event.clientX - dragOffsetRef.current.x;
        const finalY = event.clientY - dragOffsetRef.current.y;

        readDesktopInteractionContext({
          x: finalX + petSize.width / 2,
          y: finalY + petSize.height / 2,
        }).then((desktopContext) => {
          const isOnDesktop =
            desktopContext.surface === 'desktop' ||
            (desktopContext.surface === 'unknown' && desktopContext.allowUnknown !== false);

          if (isOnDesktop) {
            const candidates = createIconEdgeCandidates(ICONS, petSize);
            const best = chooseBestPerch(candidates, {
              current: { x: finalX, y: finalY },
              screen: { x: 0, y: 0, width: window.innerWidth, height: window.innerHeight },
              taskbar: { x: 0, y: window.innerHeight - 54, width: window.innerWidth, height: 54 },
              petSize,
            });

            if (best) {
              const distance = Math.hypot(best.x - finalX, best.y - finalY);
              const SNAP_THRESHOLD = 100;
              if (distance <= SNAP_THRESHOLD) {
                setPosition({ x: best.x, y: best.y });
                setBubble('抱住！');
                return;
              }
            }
          }
          setPosition({ x: finalX, y: finalY });
        });
      }
      activePointerIdRef.current = null;
      setIsDragging(false);
    };

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

  const resolvePetInteractionGate = async (pointer: { x: number; y: number }) => {
    const petRect = { x: position.x, y: position.y, width: petSize.width, height: petSize.height };
    const desktopContext = await readDesktopInteractionContext(pointer);
    return canStartPetInteraction({
      pointer,
      petRect,
      presence,
      desktopContext,
    });
  };

  const handlePetPointerDown = async (event: PointerEvent<HTMLDivElement>) => {
    const pointer = { x: event.clientX, y: event.clientY };
    const pointerId = event.pointerId;
    const pointerTarget = event.currentTarget;
    activePointerIdRef.current = pointerId;
    const gate = await resolvePetInteractionGate(pointer);

    if (activePointerIdRef.current !== pointerId || !gate.canStart) {
      return;
    }

    try {
      pointerTarget.setPointerCapture(pointerId);
    } catch {
      // Pointer capture is best-effort; window-level mouseup still clears dragging.
    }

    dragOffsetRef.current = {
      x: pointer.x - position.x,
      y: pointer.y - position.y,
    };

    if (isTauri) {
      try {
        const { getCurrentWindow } = await import('@tauri-apps/api/window');
        const appWindow = getCurrentWindow();
        const pos = await appWindow.outerPosition();
        const scale = await appWindow.scaleFactor();
        initialWindowPosRef.current = { x: pos.x, y: pos.y };
        scaleFactorRef.current = scale;
        dragStartScreenRef.current = { x: event.screenX, y: event.screenY };
      } catch (err) {
        console.error('Failed to initialize Tauri window drag:', err);
      }
    }

    setIsDragging(true);
  };

  const handlePetClick = async (event: ReactMouseEvent<HTMLDivElement>) => {
    const gate = await resolvePetInteractionGate({ x: event.clientX, y: event.clientY });
    if (!gate.canStart) {
      return;
    }

    setClickBurst(1);
    if (clearTickleTimeoutRef.current !== null) {
      window.clearTimeout(clearTickleTimeoutRef.current);
    }
    clearTickleTimeoutRef.current = window.setTimeout(() => {
      setClickBurst(0);
      clearTickleTimeoutRef.current = null;
    }, TICKLE_HOLD_MS);
  };

  const handleCheckUpdate = async () => {
    setIsCheckingUpdate(true);
    const status = await checkForAppUpdate({
      currentVersion: APP_VERSION,
      manifestUrl: UPDATE_MANIFEST_URL,
    });
    setIsCheckingUpdate(false);

    if (status.kind === 'not-configured') {
      setBubble('更新接口已预留。');
      return;
    }
    if (status.kind === 'available') {
      setBubble(`发现 ${status.latestVersion}。`);
      return;
    }
    if (status.kind === 'current') {
      setBubble('已经是最新版。');
      return;
    }

    setBubble('暂时检查不了更新。');
  };

  useEffect(() => {
    if (isTauri) {
      const promise = import('@tauri-apps/api/event').then(({ listen }) => {
        return listen('check-update', () => {
          handleCheckUpdate();
        });
      });
      return () => {
        promise.then((unlisten) => unlisten());
      };
    }
  }, [isTauri]);

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
        <button type="button" onClick={handleCheckUpdate} disabled={isCheckingUpdate}>
          {isCheckingUpdate ? '检查中' : '更新'}
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
