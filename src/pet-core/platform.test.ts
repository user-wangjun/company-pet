import { readFileSync } from "node:fs";
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
  resolvePlatformSectionAfterCompanionExit,
  resolveRenderedPlatformSection,
} from "./platform";
import defaultCapability from "../../src-tauri/capabilities/default.json";
import tauriConfig from "../../src-tauri/tauri.conf.json";

const tauriCargoToml = readFileSync(resolve("src-tauri/Cargo.toml"), "utf8");
const appCss = readFileSync(resolve("src/App.css"), "utf8");

describe("platform branding", () => {
  test("uses Yuxin Desktop Pet as the platform name", () => {
    expect(APP_DISPLAY_NAME).toBe("愈心桌宠");
    expect(APP_WINDOW_TITLE).toBe("愈心桌宠");
  });

  test("starts with independent hidden pet and platform windows", () => {
    expect(PLATFORM_START_OPEN).toBe(true);
    expect(PLATFORM_START_SECTION).toBe("home");
    expect(tauriConfig.app.windows.map((window) => window.label)).toEqual([
      "main",
      "platform",
    ]);
    expect(tauriConfig.app.windows[0]).toMatchObject({
      label: "main",
      width: 165,
      height: 215,
      visible: false,
      resizable: false,
      skipTaskbar: true,
    });
    expect(tauriConfig.app.windows[1]).toMatchObject({
      label: "platform",
      width: 860,
      height: 590,
      minWidth: 560,
      minHeight: 420,
      visible: false,
      resizable: true,
      maximizable: true,
      minimizable: true,
      skipTaskbar: false,
    });
    expect(defaultCapability.windows).toEqual(["main", "platform"]);
    expect(defaultCapability.permissions).toContain(
      "core:window:allow-show",
    );
  });

  test("allows the platform panel to start native window dragging", () => {
    expect(defaultCapability.permissions).toContain(
      "core:window:allow-start-dragging",
    );
  });

  test("allows the dedicated platform window controls", () => {
    expect(defaultCapability.permissions).toEqual(
      expect.arrayContaining([
        "core:window:allow-minimize",
        "core:window:allow-toggle-maximize",
      ]),
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

describe("platform companion navigation contract", () => {
  test.each([
    "back",
    "close",
    "escape",
    "outside",
    "idle",
    "pet-switch",
    "mutual-surface",
    "return",
  ] as const)("routes %s exits to home", (reason) => {
    expect(resolvePlatformSectionAfterCompanionExit(reason)).toBe("home");
  });

  test("routes an explicit platform navigation away from chat to its destination", () => {
    expect(resolvePlatformSectionAfterCompanionExit("navigation", "settings")).toBe(
      "settings",
    );
    expect(resolvePlatformSectionAfterCompanionExit("navigation", "tasks")).toBe(
      "tasks",
    );
    expect(resolvePlatformSectionAfterCompanionExit("navigation", "chat")).toBe(
      "home",
    );
  });

  test("never renders an inactive chat section and preserves the active room", () => {
    expect(resolveRenderedPlatformSection("chat", "inactive")).toBe("home");
    expect(resolveRenderedPlatformSection("chat", "active")).toBe("chat");
    expect(resolveRenderedPlatformSection("settings", "inactive")).toBe("settings");
  });

  test("keeps the companion room shell as one flexible column", () => {
    const shellStart = appCss.indexOf(".platform-companion-chat-room-shell {");
    const shellEnd = appCss.indexOf("\n}", shellStart);
    expect(shellStart).toBeGreaterThanOrEqual(0);
    expect(shellEnd).toBeGreaterThan(shellStart);

    const shellRule = appCss.slice(shellStart, shellEnd);
    expect(shellRule).toContain("grid-template-columns: minmax(0, 1fr);");
    expect(shellRule).not.toMatch(/174px|204px/);
  });

  test("keeps the companion room input inside the platform window", () => {
    const inputStart = appCss.indexOf(".platform-companion-chat-input {");
    const inputEnd = appCss.indexOf("\n}", inputStart);
    expect(inputStart).toBeGreaterThanOrEqual(0);
    expect(inputEnd).toBeGreaterThan(inputStart);

    const inputRule = appCss.slice(inputStart, inputEnd);
    expect(inputRule).toContain("box-sizing: border-box;");
  });

  test("allows the remote-pending room input to shrink before placing Stop", () => {
    const providerStart = appCss.indexOf(".platform-companion-chat-room-provider {");
    const providerEnd = appCss.indexOf("\n}", providerStart);
    const roomInputStart = appCss.indexOf(".platform-companion-chat-room-input {");
    const roomInputEnd = appCss.indexOf("\n}", roomInputStart);
    expect(providerStart).toBeGreaterThanOrEqual(0);
    expect(providerEnd).toBeGreaterThan(providerStart);
    expect(roomInputStart).toBeGreaterThanOrEqual(0);
    expect(roomInputEnd).toBeGreaterThan(roomInputStart);

    const providerRule = appCss.slice(providerStart, providerEnd);
    const roomInputRule = appCss.slice(roomInputStart, roomInputEnd);
    expect(providerRule).toContain("min-width: 0;");
    expect(roomInputRule).toContain("min-width: 0;");
  });
});
