export type CareReminderWindow = {
  isVisible: () => Promise<boolean>;
  show: () => Promise<void>;
};

export async function revealHiddenPetForCareReminder(
  appWindow: CareReminderWindow | null,
): Promise<boolean> {
  if (!appWindow || await appWindow.isVisible()) return false;

  await appWindow.show();
  return true;
}
