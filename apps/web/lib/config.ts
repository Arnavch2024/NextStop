/**
 * Application client configuration.
 */

export function isDemoEnabled(): boolean {
  if (
    process.env.NEXT_PUBLIC_DEMO_ENABLED === "false" ||
    process.env.NEXT_PUBLIC_DEMO_ENABLED === "0"
  ) {
    return false;
  }
  return true;
}
