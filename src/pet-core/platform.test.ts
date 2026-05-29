import { describe, expect, test } from "vitest";
import {
  APP_DISPLAY_NAME,
  APP_WINDOW_TITLE,
  PLATFORM_START_OPEN,
} from "./platform";
import defaultCapability from "../../src-tauri/capabilities/default.json";

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
});
