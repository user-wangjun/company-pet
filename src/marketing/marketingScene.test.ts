import { describe, expect, test } from "vitest";
import {
  MARKETING_COMPANION_LINKS,
  MARKETING_ENTITY_INTERACTIONS,
  MARKETING_SCENE_ENTITIES,
  getAdjacentMarketingEntity,
  getMarketingCameraFrame,
} from "./marketingScene";

describe("marketing scene", () => {
  test("gives every visible planet, character and landmark a unique interaction", () => {
    expect(MARKETING_SCENE_ENTITIES.length).toBeGreaterThanOrEqual(12);
    expect(new Set(MARKETING_SCENE_ENTITIES.map((entity) => entity.id)).size).toBe(
      MARKETING_SCENE_ENTITIES.length,
    );
    expect(MARKETING_SCENE_ENTITIES.filter((entity) => entity.kind === "character")).toHaveLength(4);

    for (const entity of MARKETING_SCENE_ENTITIES) {
      expect(entity.x).toBeGreaterThan(0);
      expect(entity.x).toBeLessThan(100);
      expect(entity.y).toBeGreaterThan(10);
      expect(entity.y).toBeLessThan(90);
      expect(entity.zoom).toBeGreaterThan(1);
      expect(entity.name.length).toBeGreaterThan(1);
      expect(entity.description.length).toBeGreaterThan(12);
      expect(MARKETING_ENTITY_INTERACTIONS[entity.id]?.title.length).toBeGreaterThan(4);
      expect(MARKETING_ENTITY_INTERACTIONS[entity.id]?.cue.length).toBeGreaterThan(8);
    }
  });

  test("binds every desktop pet to an existing companion planet", () => {
    const characters = MARKETING_SCENE_ENTITIES.filter(
      (entity) => entity.kind === "character",
    );
    expect(MARKETING_COMPANION_LINKS).toHaveLength(characters.length);

    for (const link of MARKETING_COMPANION_LINKS) {
      expect(characters.some((entity) => entity.id === link.characterId)).toBe(true);
      expect(
        MARKETING_SCENE_ENTITIES.some(
          (entity) => entity.id === link.planetId && entity.kind === "planet",
        ),
      ).toBe(true);
      expect(link.label.length).toBeGreaterThan(5);
    }
  });

  test("centers the selected entity with a zoomed camera frame", () => {
    const entity = MARKETING_SCENE_ENTITIES[3];
    const frame = getMarketingCameraFrame(entity);

    expect(frame.scale).toBe(entity.zoom);
    expect(frame.x + entity.x * frame.scale).toBeCloseTo(50);
    expect(frame.y + entity.y * frame.scale).toBeCloseTo(51);
    expect(getMarketingCameraFrame(null)).toEqual({ x: 0, y: 0, scale: 1 });
  });

  test("cycles through targets in both directions", () => {
    const first = MARKETING_SCENE_ENTITIES[0];
    const last = MARKETING_SCENE_ENTITIES[MARKETING_SCENE_ENTITIES.length - 1];

    expect(getAdjacentMarketingEntity(null, 1).id).toBe(first.id);
    expect(getAdjacentMarketingEntity(first.id, -1).id).toBe(last.id);
    expect(getAdjacentMarketingEntity(last.id, 1).id).toBe(first.id);
  });
});
