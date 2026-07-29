// @ts-expect-error Vitest runs this in Node, while the app tsconfig keeps Node
// types out of browser code.
import { readFileSync } from "node:fs";
// @ts-expect-error Vitest runs this in Node, while the app tsconfig keeps Node
// types out of browser code.
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";
import {
  APP_DISPLAY_NAME,
  APP_WINDOW_TITLE,
  clampWindowPositionToWorkArea,
  getPhysicalPetAnchor,
  getInitialPetWindowPosition,
  getWindowPositionForPhysicalPetAnchor,
  PLATFORM_START_OPEN,
  PLATFORM_START_SECTION,
} from "./platform";
import defaultCapability from "../../src-tauri/capabilities/default.json";
import tauriConfig from "../../src-tauri/tauri.conf.json";

const tauriCargoToml = readFileSync(resolve("src-tauri/Cargo.toml"), "utf8");

describe("platform branding", () => {
  test("uses Yuxin Desktop Pet as the platform name", () => {
    expect(APP_DISPLAY_NAME).toBe("愈心桌宠");
    expect(APP_WINDOW_TITLE).toBe("愈心桌宠");
  });

  test("starts on the platform panel before showing a pet", () => {
    expect(PLATFORM_START_OPEN).toBe(true);
    expect(PLATFORM_START_SECTION).toBe("pets");
  });

  test("allows the platform panel to start native window dragging", () => {
    expect(defaultCapability.permissions).toContain(
      "core:window:allow-start-dragging",
    );
  });

  test("allows the platform and pet modes to resize the native window", () => {
    expect(defaultCapability.permissions).toContain("core:window:allow-set-size");
  });

  test("enables macOS transparent window rendering support", () => {
    expect(tauriConfig.app.windows.some((window) => window.transparent)).toBe(
      true,
    );
    expect(tauriConfig.app.macOSPrivateApi).toBe(true);
    expect(tauriCargoToml).toContain('"macos-private-api"');
  });

  test("places the initial pet window at the lower right of the work area", () => {
    expect(
      getInitialPetWindowPosition(
        {
          position: { x: 0, y: 0 },
          size: { width: 1920, height: 1040 },
        },
        { width: 165, height: 215 },
      ),
    ).toEqual({ x: 1731, y: 801 });
  });

  test("keeps initial pet placement inside offset and small work areas", () => {
    expect(
      getInitialPetWindowPosition(
        {
          position: { x: -1280, y: 120 },
          size: { width: 1280, height: 720 },
        },
        { width: 165, height: 215 },
      ),
    ).toEqual({ x: -189, y: 601 });

    expect(
      getInitialPetWindowPosition(
        {
          position: { x: 40, y: 80 },
          size: { width: 120, height: 140 },
        },
        { width: 165, height: 215 },
      ),
    ).toEqual({ x: 40, y: 80 });
  });

  test.each([1, 1.25, 1.5, 2])(
    "round-trips the physical pet anchor at %sx display scaling",
    (scaleFactor) => {
      const petViewport = { x: 0, y: 0, width: 165, height: 215 };
      const initialPosition = { x: 1371, y: 611 };
      const anchor = getPhysicalPetAnchor(
        initialPosition,
        petViewport,
        scaleFactor,
      );
      const reminderPosition = getWindowPositionForPhysicalPetAnchor(
        anchor,
        { x: 75, y: 235, width: 165, height: 215 },
        scaleFactor,
      );
      const restoredPosition = getWindowPositionForPhysicalPetAnchor(
        anchor,
        petViewport,
        scaleFactor,
      );

      expect(restoredPosition).toEqual(initialPosition);
      const reminderAnchor = getPhysicalPetAnchor(
        reminderPosition,
        { x: 75, y: 235, width: 165, height: 215 },
        scaleFactor,
      );
      expect(Math.abs(reminderAnchor.x - anchor.x)).toBeLessThanOrEqual(0.5);
      expect(Math.abs(reminderAnchor.y - anchor.y)).toBeLessThanOrEqual(0.5);
      expect(
        Math.abs(
          reminderPosition.x + 240 * scaleFactor
          - (initialPosition.x + 165 * scaleFactor),
        ),
      ).toBeLessThanOrEqual(0.5);
    },
  );

  test("places the platform to the left and above the same pet anchor", () => {
    const anchor = getPhysicalPetAnchor(
      { x: 1731, y: 801 },
      { x: 0, y: 0, width: 165, height: 215 },
      1,
    );
    const platformViewport = {
      x: 1037 - 6 - 165,
      y: 590 - 215,
      width: 165,
      height: 215,
    };

    expect(
      getWindowPositionForPhysicalPetAnchor(anchor, platformViewport, 1),
    ).toEqual({ x: 865, y: 426 });
    expect(
      getPhysicalPetAnchor(
        { x: 865, y: 426 },
        platformViewport,
        1,
      ),
    ).toEqual(anchor);
  });

  test("clamps expanded windows to positive and offset work areas", () => {
    expect(
      clampWindowPositionToWorkArea(
        { x: 1680, y: 800 },
        { width: 360, height: 675 },
        {
          position: { x: 0, y: 0 },
          size: { width: 1920, height: 1040 },
        },
      ),
    ).toEqual({ x: 1560, y: 365 });

    expect(
      clampWindowPositionToWorkArea(
        { x: -1700, y: 20 },
        { width: 900, height: 700 },
        {
          position: { x: -1280, y: 120 },
          size: { width: 1280, height: 720 },
        },
      ),
    ).toEqual({ x: -1280, y: 120 });
  });
});
