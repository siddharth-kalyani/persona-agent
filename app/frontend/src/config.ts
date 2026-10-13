/** Runtime configuration. In AWS the CDK stack writes /config.json next to the app, so one
 * build serves every cell; locally it falls back to VITE_* variables from .env.local. */
export interface AppConfig {
  tenantId: string;
  clientId: string;
  /** Base URL of the API; empty = same origin (CloudFront routes /api/* to the API). */
  apiBase: string;
}

let cached: AppConfig | undefined;

export async function loadConfig(): Promise<AppConfig> {
  if (cached) return cached;
  let fromFile: Partial<AppConfig> = {};
  try {
    const res = await fetch("/config.json", { cache: "no-store" });
    if (res.ok && res.headers.get("content-type")?.includes("json")) fromFile = await res.json();
  } catch {
    // No config.json in local dev.
  }
  const config: AppConfig = {
    tenantId: fromFile.tenantId ?? import.meta.env.VITE_ENTRA_TENANT_ID ?? "",
    clientId: fromFile.clientId ?? import.meta.env.VITE_ENTRA_CLIENT_ID ?? "",
    apiBase: fromFile.apiBase ?? "",
  };
  if (!config.tenantId || !config.clientId) {
    throw new Error("Missing Entra configuration (tenantId/clientId). See app/README.md.");
  }
  cached = config;
  return config;
}

export function apiScope(config: AppConfig): string {
  return `api://${config.clientId}/access_as_user`;
}
