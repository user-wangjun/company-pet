import { describe, expect, test, vi } from "vitest";
import { startInstallerUpdate } from "./installUpdate";

describe("installer update", () => {
  test("uses the native installer command inside Tauri", async () => {
    const invoke = vi.fn(async () => undefined);
    const openUrl = vi.fn(async () => undefined);

    await startInstallerUpdate("https://example.test/yuxin.exe", {
      invoke,
      openUrl,
      isTauriRuntime: () => true,
    });

    expect(invoke).toHaveBeenCalledWith("download_and_open_installer", {
      downloadUrl: "https://example.test/yuxin.exe",
    });
    expect(openUrl).not.toHaveBeenCalled();
  });

  test("opens the direct installer URL outside Tauri previews", async () => {
    const invoke = vi.fn(async () => undefined);
    const openUrl = vi.fn(async () => undefined);

    await startInstallerUpdate("https://example.test/yuxin.dmg", {
      invoke,
      openUrl,
      isTauriRuntime: () => false,
    });

    expect(invoke).not.toHaveBeenCalled();
    expect(openUrl).toHaveBeenCalledWith("https://example.test/yuxin.dmg");
  });
});
