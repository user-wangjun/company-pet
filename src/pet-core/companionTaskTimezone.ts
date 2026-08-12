/**
 * The Harness and the legacy Task Extractor intentionally use opposite offset
 * conventions. `CompanionInput.utcOffsetMinutes` is local time minus UTC
 * (+480 for Asia/Shanghai), while `TaskExtractorOptions.timezoneOffsetMinutes`
 * preserves JavaScript Date#getTimezoneOffset (UTC minus local, -480 there).
 * Keep this conversion at the Harness boundary; do not change the old Task
 * Extractor or TaskDatabase contract globally.
 */
export function toLegacyTaskExtractorTimezoneOffsetMinutes(
  utcOffsetMinutes: number,
): number {
  if (!Number.isFinite(utcOffsetMinutes)) {
    throw new RangeError("utcOffsetMinutes must be finite");
  }
  return utcOffsetMinutes === 0 ? 0 : -utcOffsetMinutes;
}

/**
 * Returns the current date in the CompanionInput local-time convention. This
 * is deliberately separate from the legacy Task Extractor offset conversion.
 */
export function currentLocalDateKeyFromUtcOffset(
  currentTime: string,
  utcOffsetMinutes: number,
): string {
  const currentMs = Date.parse(currentTime);
  if (!Number.isFinite(currentMs)) return currentTime.slice(0, 10);
  return new Date(currentMs + utcOffsetMinutes * 60_000).toISOString().slice(0, 10);
}
