export type CareReminderWindow = {
  isVisible: () => Promise<boolean>;
  show: () => Promise<void>;
};

export type ReminderWindowSize = {
  width: number;
  height: number;
};

export function shouldUseExpandedReminderWindow(
  taskReminderCount: number,
  hasCareReminderPrompt: boolean,
): boolean {
  return taskReminderCount > 0 || hasCareReminderPrompt;
}

export function shouldResizeReminderWindow(
  current: ReminderWindowSize,
  desired: ReminderWindowSize,
): boolean {
  return current.width !== desired.width || current.height !== desired.height;
}

export type LatestWindowLayoutScheduler = {
  schedule: (applyLayout: () => Promise<void>) => Promise<boolean>;
};

export function createLatestWindowLayoutScheduler(): LatestWindowLayoutScheduler {
  let latestRequest = 0;
  let tail = Promise.resolve();

  return {
    schedule(applyLayout) {
      const request = latestRequest + 1;
      latestRequest = request;
      const result = tail.then(async () => {
        if (request !== latestRequest) return false;
        await applyLayout();
        return true;
      });

      tail = result.then(
        () => undefined,
        () => undefined,
      );
      return result;
    },
  };
}

export async function revealHiddenPetForCareReminder(
  appWindow: CareReminderWindow | null,
): Promise<boolean> {
  if (!appWindow || await appWindow.isVisible()) return false;

  await appWindow.show();
  return true;
}
