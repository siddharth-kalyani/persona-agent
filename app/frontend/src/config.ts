/** Runtime configuration. In AWS the CDK stack writes /config.json next to the app, so one
 * build serves every cell; locally it falls back to VITE_* variables from .env.local.
 * Microsoft sign-in is optional while only local password sign-in is set up (local/dev). */
export interface AppConfig {
  tenantId: string;
  clientId: string;
  /** Base URL of the API; empty = same origin (CloudFront routes /api/* to the API). */
  apiBase: string;
}

export interface SignInOptions {
  microsoft: boolean;
  password: boolean;
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
  cached = {
    tenantId: fromFile.tenantId ?? import.meta.env.VITE_ENTRA_TENANT_ID ?? "",
    clientId: fromFile.clientId ?? import.meta.env.VITE_ENTRA_CLIENT_ID ?? "",
    apiBase: fromFile.apiBase ?? "",
  };
  return cached;
}

export function microsoftConfigured(config: AppConfig): boolean {
  return Boolean(config.tenantId && config.clientId);
}

/** Which sign-in methods to offer: Microsoft if configured here, password if the API allows it. */
export async function loadSignInOptions(config: AppConfig): Promise<SignInOptions> {
  let password = false;
  try {
    const res = await fetch(`${config.apiBase}/api/auth/config`, { cache: "no-store" });
    if (res.ok) password = Boolean((await res.json()).passwordSignIn);
  } catch {
    // API unreachable: offer what the client knows about.
  }
  const options = { microsoft: microsoftConfigured(config), password };
  if (!options.microsoft && !options.password) {
    throw new Error("No sign-in method is configured. See app/README.md.");
  }
  return options;
}

export function apiScope(config: AppConfig): string {
  return `api://${config.clientId}/access_as_user`;
}
