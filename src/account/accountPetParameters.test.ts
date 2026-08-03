import { describe, expect, test } from "vitest";
import {
  dampAccountPetParameters,
  getAccountPetTargetParameters,
} from "./accountPetParameters";

describe("account Live2D parameter controller", () => {
  test("maps pointer movement to bounded eye and head targets", () => {
    const left = getAccountPetTargetParameters("idle", { x: -2, y: 2 });
    const right = getAccountPetTargetParameters("idle", { x: 2, y: -2 });

    expect(left.eyeBallX).toBe(-.72);
    expect(right.eyeBallX).toBe(.72);
    expect(left.angleX).toBe(-10);
    expect(right.angleX).toBe(10);
  });

  test("biases email focus toward the form with a happy head tilt", () => {
    const target = getAccountPetTargetParameters("email", { x: 0, y: 0 });
    expect(target.eyeBallX).toBe(.55);
    expect(target.angleZ).toBe(-6);
    expect(target.mouthForm).toBe(.8);
  });

  test("closes the eyes and raises both paws for password focus", () => {
    const target = getAccountPetTargetParameters("password", { x: 1, y: 1 });
    expect(target.eyeOpen).toBe(0);
    expect(target.pawCover).toBe(1);
    expect(target.eyeBallX).toBe(0);
  });

  test("damps toward targets without snapping", () => {
    const current = getAccountPetTargetParameters("idle", { x: 0, y: 0 });
    const target = getAccountPetTargetParameters("password", { x: 0, y: 0 });
    const next = dampAccountPetParameters(current, target, 16);

    expect(next.eyeOpen).toBeGreaterThan(0);
    expect(next.eyeOpen).toBeLessThan(1);
    expect(next.pawCover).toBeGreaterThan(0);
    expect(next.pawCover).toBeLessThan(1);
  });
});
