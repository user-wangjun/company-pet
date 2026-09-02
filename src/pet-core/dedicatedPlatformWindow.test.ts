import { describe, expect, test, vi } from "vitest";
import { revealDedicatedPlatformWindow } from "./dedicatedPlatformWindow";

describe("dedicated platform window reveal", () => {
  test("restores a minimized platform window before showing and focusing it", async () => {
    const calls: string[] = [];
    const platformWindow = {
      show: vi.fn(async () => {
        calls.push("show");
      }),
      unminimize: vi.fn(async () => {
        calls.push("unminimize");
      }),
      setFocus: vi.fn(async () => {
        calls.push("setFocus");
      }),
    };

    await revealDedicatedPlatformWindow(platformWindow);

    expect(calls).toEqual(["unminimize", "show", "setFocus"]);
  });
});
