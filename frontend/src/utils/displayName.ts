export function displayNameFromEmail(email?: string | null): string {
  if (!email) return "Agent";

  const local = email.split("@")[0] ?? "";
  if (!local) return "Agent";

  // take first part before dot if present
  const first = local.split(".")[0] ?? local;

  // sanitize (optional)
  const cleaned = first.replace(/[^a-zA-Z0-9_-]/g, "");
  if (!cleaned) return "Agent";

  // capitalize first letter
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}
