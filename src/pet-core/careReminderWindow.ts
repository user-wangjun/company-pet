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
  schedule: (
    applyLayout: (isLatest: () => boolean) => Promise<void>,
  ) => Promise<boolean>;
};

export function createLatestWindowLayoutScheduler(): LatestWindowLayoutScheduler {
  let latestRequest = 0;
  let tail = Promise.resolve();

  return {
    schedule(applyLayout) {
      const request = latestRequest + 1;
      latestRequest = request;
      const result = tail.then(async () => {
        // The callback must re-check this guard after every awaited native
        // mutation; a newer request can arrive while this one is in flight.
        const isLatest = () => request === latestRequest;
        if (!isLatest()) return false;
        await applyLayout(isLatest);
        return isLatest();
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
