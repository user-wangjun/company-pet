import { describe, expect, test } from "vitest";
import { getForelegMotion } from "./accountPoseSequence";

describe("account foreleg motion", () => {
  test("starts with both forelegs shortened behind the planet", () => {
    const motion = getForelegMotion(0);
    expect(motion.progress).toBe(0);
    expect(motion.leftTransform).toContain("scaleY(0.4200)");
    expect(motion.rightTransform).toContain("scaleY(0.4600)");
  });

  test("uses continuous transforms instead of switching pose images", () => {
    const before = getForelegMotion(.49);
    const after = getForelegMotion(.51);
    expect(after.progress).toBeGreaterThan(before.progress);
    expect(after.leftTransform).not.toBe(before.leftTransform);
    expect(after.rightTransform).not.toBe(before.rightTransform);
  });

  test("lands on the authored eye-cover pose", () => {
    const motion = getForelegMotion(1);
    expect(motion.progress).toBe(1);
    expect(motion.leftTransform).toBe("translate3d(0.000%, 0.000%, 0) rotate(0.000deg) scaleY(1.0000)");
    expect(motion.rightTransform).toBe(motion.leftTransform);
  });

  test("returns the same pose at the same value while reversing", () => {
    expect(getForelegMotion(.63)).toEqual(getForelegMotion(.63));
  });
});
