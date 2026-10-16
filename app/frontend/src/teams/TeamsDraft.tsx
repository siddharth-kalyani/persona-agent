/** The Teams dialog (M5): "Draft reply" on a message, or Vanimo under the compose box. Drafts a chat
 * message in your voice through the same drafting service as the web app and Outlook. Teams has no way
 * to type into the message box, so you Copy the draft — or, where your organisation turned it on after
 * the prefill test, open the chat with the draft typed in. Vanimo never sends. */
import {
  Button,
  Caption1,
  Field,
  makeStyles,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  Select,
  Spinner,
  Text,
  Textarea,
  tokens,
} from "@fluentui/react-components";
import { useEffect, useState } from "react";
import { type Api, ApiError, type Draft, type DraftChat, type DraftCheck, type TeamsDialogTarget } from "../api/client";
import { DraftView, draftErrorText, hasBlock, RateButtons, recheck } from "../drafting/DraftView";
import { newChatLink } from "../pages/TeamsPrefill";

const useStyles = makeStyles({
  pane: { display: "grid", gap: tokens.spacingVerticalM, padding: tokens.spacingHorizontalL },
  row: { display: "flex", gap: tokens.spacingHorizontalS, alignItems: "center", flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
});

export interface TeamsHost {
  /** Opens the chat with the text typed in (TeamsJS chat API, or the documented deep link). */
  openChat: (users: string[], message: string) => Promise<void>;
  close: () => void;
}

export function browserHost(): TeamsHost {
  return {
    openChat: async (users, message) => {
      window.open(newChatLink(users.join(","), message), "_blank", "noreferrer");
    },
    close: () => window.close(),
  };
}

export function TeamsDraft({
  api,
  target,
  prefill,
  host,
}: {
  api: Api;
  /** From the message action (via its handle); null when opened directly: pick a chat. */
  target: TeamsDialogTarget | null;
  prefill: boolean;
  host: TeamsHost;
}) {
  const styles = useStyles();
  const [chats, setChats] = useState<DraftChat[] | null>(null);
  const [picked, setPicked] = useState("");
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [oneOffOffer, setOneOffOffer] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [text, setText] = useState("");
  const [checks, setChecks] = useState<DraftCheck[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [rated, setRated] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (target) return;
    api.draftingChats().then(
      (c) => setChats(c),
      (e) => setError(draftErrorText(e)),
    );
  }, [api, target]);

  if (target?.mode === "channel") {
    return (
      <div className={styles.pane}>
        <Text weight="semibold">Vanimo works in chats</Text>
        <Caption1>Drafting in Teams channels isn't available yet. Use it on a message in a 1:1, group or meeting chat.</Caption1>
        <Button onClick={host.close}>Close</Button>
      </div>
    );
  }

  const chatId = target?.chatId ?? (picked || null);
  const mode = target?.mode === "reply" ? "reply" : "new";

  async function run(oneOff = false) {
    if (!chatId) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    setOneOffOffer(false);
    try {
      const d = await api.createDraft({
        mode: target ? mode : "reply",
        surface: "teams",
        channel: "chat",
        conversationId: chatId,
        messageId: target?.messageId ?? null,
        instruction: instruction.trim() || null,
        oneOff,
      });
      setDraft(d);
      setText(d.text);
      setChecks(d.checks);
      setConfirmed(false);
      setRated(null);
    } catch (e) {
      setDraft(null);
      setError(draftErrorText(e));
      setOneOffOffer(e instanceof ApiError && e.code === "conversation_excluded" && e.body.oneOffAllowed === true);
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!draft) return;
    try {
      await navigator.clipboard.writeText(text);
      setNotice("Copied. Paste it into the message box and send it yourself.");
      if (draft.id) await api.draftFeedback(draft.id, { outcome: "copied" });
    } catch {
      setNotice("Couldn't copy automatically: select the text and copy it.");
    }
  }

  async function checkAgain() {
    if (!draft || !chatId) return;
    try {
      const res = await api.checkText(text, draft.audience.to, [], draft.oneOff ? null : chatId, "chat");
      const merged = recheck(draft.checks, res.checks);
      setChecks(merged);
      setNotice(merged.length ? null : "No problems found in your text.");
    } catch (e) {
      setError(draftErrorText(e));
    }
  }

  async function openChat() {
    if (!draft?.chatUsers?.length) return;
    try {
      await host.openChat(draft.chatUsers, text);
      if (draft.id) await api.draftFeedback(draft.id, { outcome: "opened_chat" }).catch(() => undefined);
    } catch {
      setNotice("Teams couldn't open the chat with the text. Copy it instead.");
    }
  }

  return (
    <div className={styles.pane}>
      <Text weight="semibold" size={400}>
        {mode === "reply" && target ? "Draft a reply in your voice" : "Draft a message in your voice"}
      </Text>
      {!target && (
        <Field label="Chat">
          {chats === null ? (
            <Spinner size="tiny" />
          ) : (
            <Select value={picked} onChange={(_, d) => setPicked(d.value)}>
              <option value="">Pick a chat…</option>
              {chats.map((c) => (
                <option key={c.chatId} value={c.chatId} disabled={c.excluded}>
                  {c.label}
                  {c.excluded ? " (excluded)" : ""}
                </option>
              ))}
            </Select>
          )}
        </Field>
      )}
      <Field
        label={mode === "reply" && target ? "What should the reply say? (optional)" : "What should it say?"}
        hint="For example: say I'll share the deck by 5"
      >
        <Textarea value={instruction} maxLength={1000} onChange={(_, d) => setInstruction(d.value)} />
      </Field>
      <div className={styles.row}>
        <Button
          appearance="primary"
          disabled={busy || !chatId || (mode === "new" && !!target && !instruction.trim())}
          onClick={() => void run()}
        >
          {busy ? "Drafting…" : draft ? "Draft again" : "Draft"}
        </Button>
        <Button appearance="subtle" onClick={host.close}>
          Close
        </Button>
      </div>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
          {oneOffOffer && (
            <MessageBarActions>
              <Button onClick={() => void run(true)}>Draft once without saving</Button>
            </MessageBarActions>
          )}
        </MessageBar>
      )}
      {notice && (
        <MessageBar intent="success">
          <MessageBarBody>{notice}</MessageBarBody>
        </MessageBar>
      )}
      {draft && (
        <DraftView
          draft={draft}
          text={text}
          onTextChange={setText}
          checks={checks}
          confirmed={confirmed}
          onConfirm={setConfirmed}
          actions={
            <>
              <Button appearance="primary" disabled={hasBlock(checks) && !confirmed} onClick={() => void copy()}>
                Copy
              </Button>
              {prefill && (draft.chatUsers?.length ?? 0) > 0 && (
                <Button disabled={hasBlock(checks) && !confirmed} onClick={() => void openChat()}>
                  Open the chat with this text
                </Button>
              )}
              <Button onClick={() => void checkAgain()}>Check my edits</Button>
              {draft.id && <RateButtons rated={rated} onRate={(r) => { setRated(r); void api.draftFeedback(draft.id!, { rating: r }).catch(() => undefined); }} />}
            </>
          }
        />
      )}
      <Caption1 className={styles.muted}>Vanimo never sends: you paste or open the draft and send it yourself.</Caption1>
    </div>
  );
}
