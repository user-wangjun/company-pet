import { describe, expect, it, vi } from "vitest";
import { revealHiddenPetForCareReminder } from "./careReminderWindow";

describe("revealHiddenPetForCareReminder", () => {
  it("shows a hidden pet window", async () => {
    const appWindow = {
      isVisible: vi.fn().mockResolvedValue(false),
      show: vi.fn().mockResolvedValue(undefined),
    };

    await expect(revealHiddenPetForCareReminder(appWindow)).resolves.toBe(true);
    expect(appWindow.show).toHaveBeenCalledOnce();
  });

  it("does not disturb an already visible pet window", async () => {
    const appWindow = {
      isVisible: vi.fn().mockResolvedValue(true),
      show: vi.fn().mockResolvedValue(undefined),
    };

    await expect(revealHiddenPetForCareReminder(appWindow)).resolves.toBe(false);
    expect(appWindow.show).not.toHaveBeenCalled();
  });

  it("does nothing in browser preview", async () => {
    await expect(revealHiddenPetForCareReminder(null)).resolves.toBe(false);
  });
});
