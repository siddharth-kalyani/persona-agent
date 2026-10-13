import {
  BrowserAuthError,
  BrowserCacheLocation,
  createStandardPublicClientApplication,
  InteractionRequiredAuthError,
  type IPublicClientApplication,
} from "@azure/msal-browser";
import { apiScope, type AppConfig } from "../config";

/** Test hook: reset the module's redirect flag. */
export function resetRedirectState(): void {
  redirecting = false;
}

export function bridgeUri(): string {
  return `${window.location.origin}/redirect.html`;
}

export function msalConfig(config: AppConfig) {
  return {
    auth: {
      clientId: config.clientId,
      // Single-tenant: only the organisation's own Entra tenant (D8).
      authority: `https://login.microsoftonline.com/${config.tenantId}`,
      // MSAL v5 sends every flow (silent iframe, popup, redirect) through this bridge page.
      redirectUri: bridgeUri(),
      // Must be a registered redirect URI. The bridge page has no sign-in payload after sign-out,
      // so it sends the browser home (see redirect.ts).
      postLogoutRedirectUri: bridgeUri(),
    },
    // Tokens live in sessionStorage: gone when the tab closes, never shared across tabs.
    cache: { cacheLocation: BrowserCacheLocation.SessionStorage },
  };
}

export async function createMsal(config: AppConfig): Promise<IPublicClientApplication> {
  const pca = await createStandardPublicClientApplication(msalConfig(config));
  const redirect = await pca.handleRedirectPromise({ navigateToLoginRequestUrl: true });
  if (redirect?.account) pca.setActiveAccount(redirect.account);
  else if (!pca.getActiveAccount() && pca.getAllAccounts()[0]) pca.setActiveAccount(pca.getAllAccounts()[0]!);
  return pca;
}

let redirecting = false;

/** Resolves never: the page is navigating away to sign in, so callers should just wait. */
function waitForNavigation(): Promise<never> {
  return new Promise<never>(() => {});
}

/** Access token for the Vanimo API (the backend exchanges it for Graph via On-Behalf-Of). */
export async function getApiToken(pca: IPublicClientApplication, config: AppConfig): Promise<string> {
  // A second API call in the same render must not start (or fail on) another interaction.
  if (redirecting) return waitForNavigation();
  const account = pca.getActiveAccount();
  const request = { scopes: [apiScope(config)], account: account ?? undefined };
  if (!account) {
    redirecting = true;
    await pca.loginRedirect(request);
    throw new Error("redirecting to sign-in");
  }
  try {
    return (await pca.acquireTokenSilent(request)).accessToken;
  } catch (err) {
    // Interaction required, or the silent iframe couldn't complete (e.g. the refresh token expired
    // and third-party cookies are blocked): fall back to a full-page sign-in instead of failing.
    const inProgress = err instanceof BrowserAuthError && err.errorCode === "interaction_in_progress";
    if (inProgress && redirecting) return waitForNavigation();
    if (!inProgress && (err instanceof InteractionRequiredAuthError || err instanceof BrowserAuthError)) {
      redirecting = true;
      await pca.acquireTokenRedirect(request);
      throw new Error("redirecting to sign-in");
    }
    throw err;
  }
}
