import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import {
  MARKETING_COMPANION_LINKS,
  MARKETING_ENTITY_INTERACTIONS,
  MARKETING_SCENE_ENTITIES,
  getAdjacentMarketingEntity,
  getMarketingCameraFrame,
  type MarketingSceneEntity,
} from "./marketingScene";
import MarketingStarParticles from "./MarketingStarParticles";

function MarketingSpaceVisual({ entity }: { entity: MarketingSceneEntity }) {
  if (entity.visual === "world-yuxin") {
    return (
      <span className="marketing-generated-world" aria-hidden="true">
        <img
          className="marketing-world-art"
          src="/marketing-assets/healing-world-v2.png"
          alt=""
        />
        <span className="marketing-world-atmosphere" />
        <span className="marketing-world-spark marketing-world-spark-a">✦</span>
        <span className="marketing-world-spark marketing-world-spark-b">✦</span>
        <span className="marketing-world-ring marketing-world-ring-back" />
        <span className="marketing-world-ring marketing-world-ring-front" />
      </span>
    );
  }

  if (entity.visual.startsWith("pet-")) {
    const companion = MARKETING_COMPANION_LINKS.find(
      (link) => link.characterId === entity.id,
    );
    return (
      <span
        className="marketing-pet-visual"
        data-companion-planet={companion?.planetId}
        aria-hidden="true"
      >
        <span className="marketing-pet-orbit" />
        <span className="marketing-pet-home">
          <i />
          <b>✦</b>
        </span>
        <span
          className={`marketing-pet-sprite marketing-${entity.visual}`}
        />
        <span className="marketing-pet-shadow" />
      </span>
    );
  }

  const planetArt = entity.visual.includes("honey") || entity.visual.includes("lime")
    ? "/marketing-assets/planet-honey-v2.png"
    : entity.visual.includes("tiny-earth")
      ? "/marketing-assets/planet-earth-v2.png"
      : "/marketing-assets/planet-moon-v2.png";

  return (
    <span
      className={`marketing-generated-planet marketing-${entity.visual} has-art`}
      aria-hidden="true"
    >
      <img className="marketing-planet-art" src={planetArt} alt="" />
      {entity.visual.includes("ring") && (
        <span className="marketing-generated-planet-ring" />
      )}
    </span>
  );
}

function MarketingCompanionConstellation() {
  return (
    <svg
      className="marketing-companion-constellation"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      aria-label="桌宠与伴生星球之间的星光航线"
    >
      {MARKETING_COMPANION_LINKS.map((link, index) => {
        const character = MARKETING_SCENE_ENTITIES.find(
          (entity) => entity.id === link.characterId,
        );
        const planet = MARKETING_SCENE_ENTITIES.find(
          (entity) => entity.id === link.planetId,
        );
        if (!character || !planet) return null;
        const midpointX = (character.x + planet.x) / 2;
        const midpointY = (character.y + planet.y) / 2;

        return (
          <g
            key={link.characterId}
            className="marketing-companion-route"
            style={{ "--route-accent": link.accent, "--route-delay": `${index * -1.4}s` } as CSSProperties}
          >
            <title>{link.label}</title>
            <line x1={planet.x} y1={planet.y} x2={character.x} y2={character.y} />
            <circle cx={midpointX} cy={midpointY} r="0.42" />
          </g>
        );
      })}
    </svg>
  );
}

function MarketingEncounter({ entity }: { entity: MarketingSceneEntity }) {
  const interaction = MARKETING_ENTITY_INTERACTIONS[entity.id];
  if (!interaction) return null;

  return (
    <section
      key={entity.id}
      className={`marketing-encounter marketing-encounter-${interaction.kind}`}
      data-interaction-duration="7.2s"
      aria-label={`${entity.name}互动片段：${interaction.title}`}
    >
      <span className="marketing-encounter-live">LIVE ENCOUNTER · 07 SEC</span>
      <div className="marketing-encounter-stage" aria-hidden="true">
        <i /><i /><i /><i /><i />
        <b>{interaction.glyph}</b>
      </div>
      <strong>{interaction.title}</strong>
      <small>{interaction.cue}</small>
      <span className="marketing-encounter-progress" aria-hidden="true" />
    </section>
  );
}

function MarketingUniverse() {
  const [activeEntityId, setActiveEntityId] = useState<string | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const activeEntity = useMemo(
    () =>
      MARKETING_SCENE_ENTITIES.find((entity) => entity.id === activeEntityId) ??
      null,
    [activeEntityId],
  );
  const cameraFrame = getMarketingCameraFrame(activeEntity);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setActiveEntityId(null);
        return;
      }

      if (event.key === "ArrowRight" || event.key === "ArrowDown") {
        event.preventDefault();
        setActiveEntityId(getAdjacentMarketingEntity(activeEntityId, 1).id);
      } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
        event.preventDefault();
        setActiveEntityId(getAdjacentMarketingEntity(activeEntityId, -1).id);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeEntityId]);

  const updatePointer = (event: React.PointerEvent<HTMLDivElement>) => {
    const viewport = viewportRef.current;
    if (!viewport || event.pointerType === "touch") return;

    const bounds = viewport.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width - 0.5;
    const y = (event.clientY - bounds.top) / bounds.height - 0.5;
    const strength = activeEntity ? 0.45 : 1;

    viewport.style.setProperty("--universe-look-x", `${(-x * 2.2 * strength).toFixed(3)}%`);
    viewport.style.setProperty("--universe-look-y", `${(-y * 1.6 * strength).toFixed(3)}%`);
    viewport.style.setProperty("--universe-tilt-x", `${(y * -1.4 * strength).toFixed(3)}deg`);
    viewport.style.setProperty("--universe-tilt-y", `${(x * 1.8 * strength).toFixed(3)}deg`);
    viewport.style.setProperty("--pet-look-x", `${(x * 7 * strength).toFixed(2)}px`);
    viewport.style.setProperty("--pet-look-y", `${(y * 5 * strength).toFixed(2)}px`);
  };

  const resetPointer = () => {
    const viewport = viewportRef.current;
    viewport?.style.setProperty("--universe-look-x", "0%");
    viewport?.style.setProperty("--universe-look-y", "0%");
    viewport?.style.setProperty("--universe-tilt-x", "0deg");
    viewport?.style.setProperty("--universe-tilt-y", "0deg");
    viewport?.style.setProperty("--pet-look-x", "0px");
    viewport?.style.setProperty("--pet-look-y", "0px");
  };

  return (
    <div
      ref={viewportRef}
      className={`marketing-universe-viewport${activeEntity ? " is-focused" : ""}`}
      onPointerMove={updatePointer}
      onPointerLeave={resetPointer}
    >
      <div className="marketing-universe-backdrop" aria-hidden="true">
        <img
          className="marketing-universe-backdrop-art"
          src="/marketing-assets/universe-backdrop-v2.png"
          alt=""
        />
        <span className="marketing-nebula marketing-nebula-a" />
        <span className="marketing-nebula marketing-nebula-b" />
        <span className="marketing-nebula marketing-nebula-c" />
        <span className="marketing-aurora" />
        <span className="marketing-starfield marketing-starfield-far" />
        <span className="marketing-starfield marketing-starfield-near" />
      </div>
      <MarketingStarParticles />

      <div
        className="marketing-universe-camera"
        data-camera-target={activeEntity?.id ?? "overview"}
        style={
          {
            "--universe-camera-x": `${cameraFrame.x}%`,
            "--universe-camera-y": `${cameraFrame.y}%`,
            "--universe-camera-scale": cameraFrame.scale,
          } as CSSProperties
        }
      >
        <MarketingCompanionConstellation />
        <div className="marketing-orbit-line marketing-orbit-line-a" aria-hidden="true" />
        <div className="marketing-orbit-line marketing-orbit-line-b" aria-hidden="true" />
        <div className="marketing-orbit-line marketing-orbit-line-c" aria-hidden="true" />

        {MARKETING_SCENE_ENTITIES.map((entity, index) => {
          const interaction = MARKETING_ENTITY_INTERACTIONS[entity.id];
          return (
          <button
            key={entity.id}
            className={`marketing-space-object marketing-space-object-${entity.kind}${
              entity.id === activeEntityId ? " is-active" : ""
            } marketing-effect-${interaction.kind}`}
            type="button"
            aria-label={`探索${entity.name}`}
            aria-pressed={entity.id === activeEntityId}
            data-entity-id={entity.id}
            style={
              {
                left: `${entity.x}%`,
                top: `${entity.y}%`,
                width: `${entity.size}%`,
                "--object-accent": entity.accent,
                "--object-depth": `${entity.depth}px`,
                "--object-delay": `${index * -0.37}s`,
              } as CSSProperties
            }
            onClick={(event) => {
              event.stopPropagation();
              setActiveEntityId(entity.id);
            }}
          >
            <MarketingSpaceVisual entity={entity} />
            <span className="marketing-object-focus-ring" aria-hidden="true" />
            <span className="marketing-object-label">
              <small>{entity.eyebrow}</small>
              <strong>{entity.name}</strong>
              <i>点击进入轨道</i>
            </span>
          </button>
          );
        })}

        <div className="marketing-universe-title" aria-hidden="true">
          <span>YOUR LITTLE UNIVERSE</span>
          <strong>愈心桌宠</strong>
          <small>在桌面上，留一颗陪你呼吸的小星球</small>
        </div>
      </div>

      <img
        className="marketing-foreground-clouds"
        src="/marketing-assets/foreground-clouds-v2.png"
        alt=""
        aria-hidden="true"
      />

      {activeEntity && <MarketingEncounter entity={activeEntity} />}

      <div className={`marketing-universe-intro${activeEntity ? " is-hidden" : ""}`}>
        <span>DRAG YOUR VIEW</span>
        <strong>每颗星球，都有回应</strong>
        <small>移动鼠标感受空间，点击任意星球或桌宠靠近</small>
      </div>

      <aside
        className={`marketing-universe-card${activeEntity ? " is-visible" : ""}`}
        aria-live="polite"
      >
        {activeEntity && (
          <>
            <span className="marketing-universe-card-index">
              {String(
                MARKETING_SCENE_ENTITIES.findIndex(
                  (entity) => entity.id === activeEntity.id,
                ) + 1,
              ).padStart(2, "0")}
              <i />
              {String(MARKETING_SCENE_ENTITIES.length).padStart(2, "0")}
            </span>
            <p>{activeEntity.eyebrow}</p>
            <h2>{activeEntity.name}</h2>
            <span>{activeEntity.description}</span>
            <button type="button" onClick={() => setActiveEntityId(null)}>
              <b aria-hidden="true">↙</b> 返回宇宙全景
            </button>
          </>
        )}
      </aside>

      <div
        className={`marketing-universe-controls${activeEntity ? " is-visible" : ""}`}
        aria-label="切换探索目标"
      >
        <button
          type="button"
          aria-label="上一个探索目标"
          onClick={() =>
            setActiveEntityId(getAdjacentMarketingEntity(activeEntityId, -1).id)
          }
        >
          ←
        </button>
        <span>{activeEntity?.name ?? "探索"}</span>
        <button
          type="button"
          aria-label="下一个探索目标"
          onClick={() =>
            setActiveEntityId(getAdjacentMarketingEntity(activeEntityId, 1).id)
          }
        >
          →
        </button>
      </div>
    </div>
  );
}

export default MarketingUniverse;
