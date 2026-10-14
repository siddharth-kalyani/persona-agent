/// <reference types="office-js" />
import { createNestablePublicClientApplication, type IPublicClientApplication } from "@azure/msal-browser";
import { Button, Caption1, FluentProvider, makeStyles, Text, tokens, webLightTheme } from "@fluentui/react-components";
import { StrictMode, useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Api } from "../api/client";
import { bridgeUri } from "../auth/msal";
import { apiScope, loadConfig, loadSignInOptions, type AppConfig, type SignInOptions } from "../config";
import { PasswordSignIn, TaskPane } from "./TaskPane";

/**
 * Outlook task pane entry (M3). Sign-in:
 *  - Microsoft: nested app authentication (NAA) through Outlook, silently; a button opens the
 *    popup fallback when Outlook needs you to sign in (popups need a click);
 *  - local/dev only, while the Entra app is pending: a Vanimo password account.
 */

const useStyles = makeStyles({
  pane: { display: "grid", gap: tokens.spacingVerticalM, padding: tokens.spacingHorizontalL },
});

const SESSION_KEY = "vanimo.addin.session";

function storedToken(): string | null {
  try {
    return sessionStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

function storeToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(SESSION_KEY, token);
    else sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // Storage blocked: the session lives in memory for this pane only.
  }
}

function MicrosoftPane({ config }: { config: AppConfig }) {
  const styles = useStyles();
  const [pca, setPca] = useState<IPublicClientApplication | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useMemo(() => ({ scopes: [apiScope(config)] }), [config]);

  useEffect(() => {
    let live = true;
    createNestablePublicClientApplication({
      auth: {
        clientId: config.clientId,
        authority: `https://login.microsoftonline.com/${config.tenantId}`,
        // Used only if the host lacks NAA and MSAL falls back to a popup (MSAL v5 bridge page).
        redirectUri: bridgeUri(),
      },
    }).then(async (app) => {
      if (!live) return;
      setPca(app);
      try {
        await app.acquireTokenSilent(request);
        if (live) setReady(true);
      } catch {
        // Needs an interactive sign-in: wait for the button (popups need a user click).
      }
    }, (e) => live && setError((e as Error).message));
    return () => {
      live = false;
    };
  }, [config, request]);

  const token = useCallback(async () => {
    if (!pca) throw new Error("not_signed_in");
    return (await pca.acquireTokenSilent(request)).accessToken;
  }, [pca, request]);
  const api = useMemo(() => new Api(config.apiBase, token), [config.apiBase, token]);

  if (ready) return <TaskPane api={api} />;
  return (
    <div className={styles.pane}>
      <Text weight="semibold" size={400}>
        Vanimo
      </Text>
      <Button
        appearance="primary"
        disabled={!pca}
        onClick={() =>
          void pca?.acquireTokenPopup(request).then(
            () => setReady(true),
            (e) => setError((e as Error).message),
          )
        }
      >
        Sign in with Microsoft
      </Button>
      {error && <Caption1>Sign-in failed: {error}</Caption1>}
    </div>
  );
}

function PasswordPane({ config }: { config: AppConfig }) {
  const [token, setToken] = useState<string | null>(() => storedToken());
  const signOut = useCallback(() => {
    storeToken(null);
    setToken(null);
  }, []);
  const api = useMemo(
    () => (token ? new Api(config.apiBase, async () => token, () => signOut()) : null),
    [config.apiBase, token, signOut],
  );
  if (!api) {
    return (
      <PasswordSignIn
        apiBase={config.apiBase}
        onSignedIn={(t) => {
          storeToken(t);
          setToken(t);
        }}
      />
    );
  }
  return <TaskPane api={api} onSignOut={signOut} />;
}

function AddIn({ config, options }: { config: AppConfig; options: SignInOptions }) {
  return options.microsoft ? <MicrosoftPane config={config} /> : <PasswordPane config={config} />;
}

Office.onReady(async () => {
  const root = createRoot(document.getElementById("root")!);
  try {
    const config = await loadConfig();
    const options = await loadSignInOptions(config);
    root.render(
      <StrictMode>
        <FluentProvider theme={webLightTheme}>
          <AddIn config={config} options={options} />
        </FluentProvider>
      </StrictMode>,
    );
  } catch (e) {
    root.render(<p style={{ padding: 16, fontFamily: "Segoe UI, sans-serif" }}>{(e as Error).message}</p>);
  }
});
