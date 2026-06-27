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
  getCenteredWindowPosition,
  getInitialPetWindowPosition,
  PLATFORM_START_OPEN,
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

  test("centers the platform panel independently from the pet position", () => {
    expect(
      getCenteredWindowPosition(
        {
          position: { x: 0, y: 0 },
          size: { width: 1920, height: 1040 },
        },
        { width: 680, height: 520 },
      ),
    ).toEqual({ x: 620, y: 260 });
  });
});
