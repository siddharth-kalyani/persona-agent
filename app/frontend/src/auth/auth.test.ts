import { BrowserAuthError, InteractionRequiredAuthError, type IPublicClientApplication } from "@azure/msal-browser";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AppConfig } from "../config";
import { bridgeUri, getApiToken, msalConfig, resetRedirectState } from "./msal";

const CONFIG: AppConfig = { tenantId: "tid", clientId: "cid", apiBase: "" };

function fakePca(silent: () => Promise<{ accessToken: string }>, account: object | null = { homeAccountId: "a" }) {
  return {
    getActiveAccount: vi.fn(() => account),
    acquireTokenSilent: vi.fn(silent),
    acquireTokenRedirect: vi.fn(async () => undefined),
    loginRedirect: vi.fn(async () => undefined),
  } as unknown as IPublicClientApplication & {
    acquireTokenRedirect: ReturnType<typeof vi.fn>;
    loginRedirect: ReturnType<typeof vi.fn>;
  };
}

describe("msalConfig", () => {
  it("is single-tenant, uses the v5 redirect bridge and session storage", () => {
    const cfg = msalConfig(CONFIG);
    expect(cfg.auth.authority).toBe("https://login.microsoftonline.com/tid");
    expect(cfg.auth.redirectUri).toBe(`${window.location.origin}/redirect.html`);
    expect(bridgeUri()).toBe(cfg.auth.redirectUri);
    expect(cfg.cache.cacheLocation).toBe("sessionStorage");
    expect(cfg.auth.postLogoutRedirectUri).toBe(cfg.auth.redirectUri); // registered in Entra
  });
});

describe("getApiToken", () => {
  beforeEach(() => resetRedirectState());

  it("requests the API scope silently", async () => {
    const pca = fakePca(async () => ({ accessToken: "tok" }));
    await expect(getApiToken(pca, CONFIG)).resolves.toBe("tok");
    expect(pca.acquireTokenSilent).toHaveBeenCalledWith(expect.objectContaining({ scopes: ["api://cid/access_as_user"] }));
  });

  it("falls back to a redirect when interaction is required", async () => {
    const pca = fakePca(async () => {
      throw new InteractionRequiredAuthError("login_required", "test");
    });
    await expect(getApiToken(pca, CONFIG)).rejects.toThrow("redirecting");
    expect(pca.acquireTokenRedirect).toHaveBeenCalledOnce();
  });

  it("falls back to a redirect when the silent iframe times out", async () => {
    const pca = fakePca(async () => {
      throw new BrowserAuthError("monitor_window_timeout", "test");
    });
    await expect(getApiToken(pca, CONFIG)).rejects.toThrow("redirecting");
    expect(pca.acquireTokenRedirect).toHaveBeenCalledOnce();
  });

  it("does not start a second interaction while one is in progress", async () => {
    const pca = fakePca(async () => {
      throw new BrowserAuthError("interaction_in_progress", "test");
    });
    await expect(getApiToken(pca, CONFIG)).rejects.toBeInstanceOf(BrowserAuthError);
    expect(pca.acquireTokenRedirect).not.toHaveBeenCalled();
  });

  it("a second call during a redirect waits instead of erroring", async () => {
    const pca = fakePca(async () => {
      throw new InteractionRequiredAuthError("login_required", "test");
    });
    await expect(getApiToken(pca, CONFIG)).rejects.toThrow("redirecting");
    const second = await Promise.race([getApiToken(pca, CONFIG).then(() => "resolved", () => "rejected"),
      new Promise((r) => setTimeout(() => r("pending"), 20))]);
    expect(second).toBe("pending");
    expect(pca.acquireTokenRedirect).toHaveBeenCalledOnce();
  });

  it("signs in when there is no account", async () => {
    const pca = fakePca(async () => ({ accessToken: "x" }), null);
    await expect(getApiToken(pca, CONFIG)).rejects.toThrow("redirecting");
    expect(pca.loginRedirect).toHaveBeenCalledOnce();
  });
});

describe("loadConfig", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("reads /config.json when it is served as JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ tenantId: "t1", clientId: "c1", apiBase: "" }), {
        headers: { "content-type": "application/json" },
      })),
    );
    const { loadConfig } = await import("../config");
    await expect(loadConfig()).resolves.toEqual({ tenantId: "t1", clientId: "c1", apiBase: "" });
  });

  it("ignores an HTML fallback page; offers password sign-in when only the API allows it", async () => {
    vi.stubEnv("VITE_ENTRA_TENANT_ID", "");
    vi.stubEnv("VITE_ENTRA_CLIENT_ID", "");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url === "/config.json"
          ? new Response("<html>", { headers: { "content-type": "text/html" } })
          : new Response(JSON.stringify({ passwordSignIn: true, microsoftSignIn: false })),
      ),
    );
    const { loadConfig, loadSignInOptions } = await import("../config");
    const config = await loadConfig();
    expect(config.tenantId).toBe("");
    await expect(loadSignInOptions(config)).resolves.toEqual({ microsoft: false, password: true });
    vi.unstubAllEnvs();
  });

  it("fails clearly when no sign-in method is available", async () => {
    vi.stubEnv("VITE_ENTRA_TENANT_ID", "");
    vi.stubEnv("VITE_ENTRA_CLIENT_ID", "");
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 404 })));
    const { loadConfig, loadSignInOptions } = await import("../config");
    await expect(loadSignInOptions(await loadConfig())).rejects.toThrow("No sign-in method");
    vi.unstubAllEnvs();
  });
});
