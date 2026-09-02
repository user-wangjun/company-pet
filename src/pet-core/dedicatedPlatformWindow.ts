export type DedicatedPlatformWindow = {
  unminimize: () => Promise<void>;
  show: () => Promise<void>;
  setFocus: () => Promise<void>;
};

export async function revealDedicatedPlatformWindow(
  platformWindow: DedicatedPlatformWindow,
): Promise<void> {
  await platformWindow.unminimize();
  await platformWindow.show();
  await platformWindow.setFocus();
}
