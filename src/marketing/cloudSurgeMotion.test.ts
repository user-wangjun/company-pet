import { describe, expect, test, vi } from "vitest";
import {
  applyCloudSurgeFrame,
  getCloudSurgeFrame,
  startCloudSurgeMotion,
} from "./cloudSurgeMotion";

function createStyleRoot() {
  const values = new Map<string, string>();
  const element = {
    style: {
      setProperty(name: string, value: string) {
        values.set(name, value);
      },
      getPropertyValue(name: string) {
        return values.get(name) ?? "";
      },
    },
  } as HTMLElement;

  return { element, values };
}

describe("cloud surge motion", () => {
  test("generates compositor-friendly layer frames", () => {
    const frame = getCloudSurgeFrame(2.4);

    for (const layer of Object.values(frame)) {
      expect(layer.transform).toContain("translate3d(");
      expect(layer.transform).toContain("scale3d(");
      expect(layer.opacity).toMatch(/^0\.\d{3}$/);
      expect(layer).not.toHaveProperty("backgroundPosition");
    }
  });

  test("applies only transform and opacity variables to the cloud root", () => {
    const { element, values } = createStyleRoot();

    applyCloudSurgeFrame(element, getCloudSurgeFrame(1.2));

    expect(element.style.getPropertyValue("--cloud-a-transform")).toContain(
      "translate3d(",
    );
    expect(element.style.getPropertyValue("--cloud-b-opacity")).toMatch(
      /^0\.\d{3}$/,
    );
    expect(Array.from(values.keys())).not.toContain("--cloud-a-bg");
    expect(Array.from(values.keys())).not.toContain("--cloud-b-bg");
    expect(Array.from(values.keys())).not.toContain("--cloud-c-bg");
  });

  test("drives motion with requestAnimationFrame", () => {
    const { element } = createStyleRoot();
    const requestFrame = vi.fn(() => 7);
    const cancelFrame = vi.fn();
    const getNow = vi.fn(() => 1000);

    const stop = startCloudSurgeMotion(element, {
      requestFrame,
      cancelFrame,
      getNow,
    });

    expect(requestFrame).toHaveBeenCalledTimes(1);

    stop();

    expect(cancelFrame).toHaveBeenCalledWith(7);
  });
});
