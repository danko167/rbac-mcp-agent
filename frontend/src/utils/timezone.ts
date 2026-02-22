export function formatTimestampInTimezone(
  ts: string | undefined,
  timezone: string
): string {
  if (!ts) return "";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;

  try {
    return d.toLocaleString(undefined, { timeZone: timezone || "UTC" });
  } catch {
    return d.toLocaleString(undefined, { timeZone: "UTC" });
  }
}
