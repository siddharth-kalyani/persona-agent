import { createNestablePublicClientApplication, type IPublicClientApplication } from "@azure/msal-browser";
import { AriaLiveAnnouncer, Button, Caption1, FluentProvider, makeStyles, Text, tokens, webLightTheme } from "@fluentui/react-components";
import { app, chat, dialog } from "@microsoft/teams-js";
import { StrictMode, useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { Api, type TeamsDialogTarget } from "../api/client";
import { ApiTestProvider } from "../api/context";
import { PasswordSignIn } from "../addin/TaskPane";
import { bridgeUri } from "../auth/msal";
import { apiScope, loadConfig, loadSignInOptions, type AppConfig, type SignInOptions } from "../config";
import { draftErrorText } from "../drafting/DraftView";
import { Commitments } from "../pages/commitments/Commitments";
import { Meetings } from "../pages/meetings/Meetings";
import { browserHost, TeamsDraft, type TeamsHost } from "./TeamsDraft";

/**
 * Teams entry (M5): the "Draft reply" / "Draft with Vanimo" dialog (`?h=<handle>`) and the personal
 * tabs (`?tab=commitments`, and M6's `?tab=meetings`). Sign-in:
 *  - Microsoft: nested app authentication through Teams (TeamsJS is initialised first, then MSAL's
 *    nestable client); a button opens the popup fallback when Teams needs you to sign in;
 *  - local/dev only, while the Entra app is pending: a Vanimo password account (sample workspace).
 * Opened outside Teams (a browser, for local testing), the same page works without TeamsJS.
 */

const useStyles = makeStyles({
  pane: { display: "grid", gap: tokens.spacingVerticalM, padding: tokens.spacingHorizontalL },
});

const params = new URLSearchParams(window.location.search);
const HANDLE = params.get("h");
const TAB = params.get("tab");

function teamsHost(inTeams: boolean): TeamsHost {
  if (!inTeams) return browserHost();
  return {
    openChat: async (users, message) => {
      // 1:1 chats only (the API offers no others until spike 1 shows group prefill opens the right chat).
      if (!chat.isSupported() || users.length !== 1) return browserHost().openChat(users, message);
      await chat.openChat({ user: users[0]!, message });
    },
    close: () => {
      if (dialog.isSupported()) dialog.url.submit();
    },
  };
}

function Surface({ api, inTeams }: { api: Api; inTeams: boolean }) {
  const styles = useStyles();
  const [target, setTarget] = useState<TeamsDialogTarget | null | undefined>(HANDLE ? undefined : null);
  const [prefill, setPrefill] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const host = useMemo(() => teamsHost(inTeams), [inTeams]);

  useEffect(() => {
    api.teamsConfig().then((c) => setPrefill(c.prefill), () => setPrefill(false));
    if (HANDLE) api.teamsDialog(HANDLE).then(setTarget, (e) => setError(draftErrorText(e)));
  }, [api]);

  if (error) return <div className={styles.pane}><Caption1>{error}</Caption1></div>; // prettier-ignore
  if (TAB === "commitments") {
    return (
      <ApiTestProvider api={api}>
        <div className={styles.pane}>
          <Commitments embedded prefill={prefill} />
        </div>
      </ApiTestProvider>
    );
  }
  if (TAB === "meetings") {
    return (
      <ApiTestProvider api={api}>
        <div className={styles.pane}>
          <Meetings embedded />
        </div>
      </ApiTestProvider>
    );
  }
  if (target === undefined) return <div className={styles.pane}><Caption1>Loading…</Caption1></div>; // prettier-ignore
  return <TeamsDraft api={api} target={target} prefill={prefill} host={host} />;
}

function MicrosoftSurface({ config, inTeams }: { config: AppConfig; inTeams: boolean }) {
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
        redirectUri: bridgeUri(),
      },
    }).then(async (a) => {
      if (!live) return;
      setPca(a);
      try {
        await a.acquireTokenSilent(request);
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

  if (ready) return <Surface api={api} inTeams={inTeams} />;
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

function PasswordSurface({ config, inTeams }: { config: AppConfig; inTeams: boolean }) {
  // In memory only: a Teams dialog lives for one draft.
  const [token, setToken] = useState<string | null>(null);
  const api = useMemo(
    () => (token ? new Api(config.apiBase, async () => token, () => setToken(null)) : null),
    [config.apiBase, token],
  );
  if (!api) return <PasswordSignIn apiBase={config.apiBase} onSignedIn={setToken} />;
  return <Surface api={api} inTeams={inTeams} />;
}

function TeamsApp({ config, options, inTeams }: { config: AppConfig; options: SignInOptions; inTeams: boolean }) {
  return options.microsoft ? (
    <MicrosoftSurface config={config} inTeams={inTeams} />
  ) : (
    <PasswordSurface config={config} inTeams={inTeams} />
  );
}

async function start() {
  const root = createRoot(document.getElementById("root")!);
  // TeamsJS first (NAA needs the host bridge); outside Teams this fails fast and the page still works.
  const inTeams = await Promise.race([
    app.initialize().then(
      () => true,
      () => false,
    ),
    new Promise<boolean>((resolve) => setTimeout(() => resolve(false), 3000)),
  ]);
  if (inTeams) app.notifySuccess();
  try {
    const config = await loadConfig();
    const options = await loadSignInOptions(config);
    root.render(
      <StrictMode>
        <FluentProvider theme={webLightTheme}>
          <AriaLiveAnnouncer>
            <TeamsApp config={config} options={options} inTeams={inTeams} />
          </AriaLiveAnnouncer>
        </FluentProvider>
      </StrictMode>,
    );
  } catch (e) {
    root.render(<p style={{ padding: 16, fontFamily: "Segoe UI, sans-serif" }}>{(e as Error).message}</p>);
  }
}

void start();
