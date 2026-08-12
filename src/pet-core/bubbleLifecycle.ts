export const PLATFORM_FEEDBACK_BUBBLE_MS = 5_000;

export function expireBubbleText(
  currentText: string | null,
  scheduledText: string,
): string | null {
  return currentText === scheduledText ? null : currentText;
}

export function getBubbleTextAfterPetMovement(
  currentText: string | null,
  hasActiveCareReminderPrompt: boolean,
): string | null {
  return hasActiveCareReminderPrompt ? currentText : null;
}
