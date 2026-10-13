/// <reference types="office-js" />
import { createNestablePublicClientApplication, type IPublicClientApplication } from "@azure/msal-browser";
import {
  Body1,
  Button,
  Caption1,
  FluentProvider,
  makeStyles,
  MessageBar,
  MessageBarBody,
  Text,
  tokens,
  webLightTheme,
} from "@fluentui/react-components";
import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Api } from "../api/client";
import { HELLO_TEXT, insertAtCursor, readItemContext, type ItemContext } from "./office";
import { bridgeUri } from "../auth/msal";
import { apiScope, loadConfig, type AppConfig } from "../config";

/**
 * M0 "hello" task pane (docs/05 §5, spike 2): proves the add-in can
 *  1. read the compose context as metadata only (compose type, recipient count, thread ID present),
 *  2. insert text at the cursor without wiping the quoted thread,
 *  3. sign in silently with nested app authentication (NAA) and call the Vanimo API.
 */

const useStyles = makeStyles({
  pane: { display: "grid", gap: tokens.spacingVerticalM, padding: tokens.spacingHorizontalL },
});

async function naaToken(pca: IPublicClientApplication, config: AppConfig): Promise<string> {
  const request = { scopes: [apiScope(config)] };
  try {
    return (await pca.acquireTokenSilent(request)).accessToken;
  } catch {
    return (await pca.acquireTokenPopup(request)).accessToken;
  }
}

function TaskPane({ config }: { config: AppConfig }) {
  const styles = useStyles();
  const item = Office.context.mailbox.item as Office.MessageCompose | Office.MessageRead | undefined;
  const [ctx, setCtx] = useState<ItemContext | null>(null);
  const isCompose = ctx?.mode === "compose";
  const [status, setStatus] = useState<{ intent: "success" | "error"; text: string } | null>(null);
  const [name, setName] = useState<string | null>(null);

  useEffect(() => {
    if (item) void readItemContext(item).then(setCtx);
  }, [item]);

  async function signInAndCallApi() {
    setStatus(null);
    try {
      const pca = await createNestablePublicClientApplication({
        auth: {
          clientId: config.clientId,
          authority: `https://login.microsoftonline.com/${config.tenantId}`,
          // Used only if the host lacks NAA and MSAL falls back to a popup (MSAL v5 bridge page).
          redirectUri: bridgeUri(),
        },
      });
      const api = new Api(config.apiBase, () => naaToken(pca, config));
      const me = await api.me();
      setName(me.user.displayName);
      setStatus({ intent: "success", text: "Signed in silently and reached the Vanimo API." });
    } catch (e) {
      setStatus({ intent: "error", text: `Sign-in or API call failed: ${(e as Error).message}` });
    }
  }

  async function insert() {
    try {
      await insertAtCursor(HELLO_TEXT);
      setStatus({ intent: "success", text: "Inserted at the cursor. Check the quoted thread is still there." });
    } catch (e) {
      setStatus({ intent: "error", text: `Insert failed: ${(e as Error).message}` });
    }
  }

  return (
    <div className={styles.pane}>
      <Text weight="semibold" size={400}>
        Vanimo
      </Text>
      <Caption1>
        Host: {Office.context.diagnostics.platform} · {Office.context.diagnostics.version} · NAA:{" "}
        {Office.context.requirements.isSetSupported("NestedAppAuth", "1.1") ? "yes" : "no"}
      </Caption1>
      {ctx && (
        <Caption1>
          Mode: {ctx.mode}
          {ctx.composeType ? ` (${ctx.composeType})` : ""} · recipients: {ctx.recipients ?? "?"} · thread ID:{" "}
          {ctx.hasConversationId ? "yes" : "no"}
        </Caption1>
      )}
      {status && (
        <MessageBar intent={status.intent}>
          <MessageBarBody>{status.text}</MessageBarBody>
        </MessageBar>
      )}
      <Button appearance="primary" onClick={() => void signInAndCallApi()}>
        Test sign-in
      </Button>
      {name && <Body1>Hello, {name}.</Body1>}
      <Button disabled={!isCompose} onClick={() => void insert()}>
        Insert test text at cursor
      </Button>
      {!isCompose && <Caption1>Open a reply or new email to test inserting text.</Caption1>}
    </div>
  );
}

Office.onReady(async () => {
  const root = createRoot(document.getElementById("root")!);
  try {
    const config = await loadConfig();
    root.render(
      <StrictMode>
        <FluentProvider theme={webLightTheme}>
          <TaskPane config={config} />
        </FluentProvider>
      </StrictMode>,
    );
  } catch (e) {
    root.render(<p>{(e as Error).message}</p>);
  }
});
