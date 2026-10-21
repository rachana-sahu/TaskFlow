const DEFAULT_TIMEZONE = "Asia/Kolkata";

export function resolveRegistrationTimezone(timezone: string | undefined): string {
  if (!timezone) return DEFAULT_TIMEZONE;
  try {
    new Intl.DateTimeFormat("en", { timeZone: timezone });
    return timezone;
  } catch {
    return DEFAULT_TIMEZONE;
  }
}

export function getRegistrationTimezone(): string {
  try {
    return resolveRegistrationTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone);
  } catch {
    return DEFAULT_TIMEZONE;
  }
}
