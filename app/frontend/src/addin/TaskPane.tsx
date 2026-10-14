/// <reference types="office-js" />
/** The Outlook task pane (M3): draft a reply or a new email in your voice, insert it at the cursor
 * (never replacing the quoted thread), and check what you're about to send. Never sends. */
import {
  Button,
  Caption1,
  Field,
  Input,
  makeStyles,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  Select,
  Spinner,
  Switch,
  Text,
  Textarea,
  tokens,
} from "@fluentui/react-components";
import { useEffect, useState } from "react";
import {
  Api,
  ApiError,
  type Draft,
  type DraftCheck,
  type DraftingStatus,
  type DraftRequest,
  type DraftThread,
  type Me,
} from "../api/client";
import { DraftView, draftErrorText, hasBlock, RateButtons, sortChecks } from "../drafting/DraftView";
import { bodyText, draftMode, insertAtCursor, openReply, readItemContext, type ItemContext } from "./office";

const useStyles = makeStyles({
  pane: { display: "grid", gap: tokens.spacingVerticalM, padding: tokens.spacingHorizontalL },
  row: { display: "flex", gap: tokens.spacingHorizontalS, alignItems: "center", flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
});

export function TaskPane({ api, onSignOut }: { api: Api; onSignOut?: () => void }) {
  const styles = useStyles();
  const item = Office.context.mailbox.item as Office.MessageCompose | Office.MessageRead | undefined;
  const [me, setMe] = useState<Me | null>(null);
  const [status, setStatus] = useState<DraftingStatus | null>(null);
  const [ctx, setCtx] = useState<ItemContext | null>(null);
  const [samples, setSamples] = useState<DraftThread[]>([]);
  const [sample, setSample] = useState("");
  const [instruction, setInstruction] = useState("");
  const [premium, setPremium] = useState(false);
  const [replyAll, setReplyAll] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [oneOffOffer, setOneOffOffer] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [text, setText] = useState("");
  const [checks, setChecks] = useState<DraftCheck[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [rated, setRated] = useState<string | null>(null);
  const [sendChecks, setSendChecks] = useState<DraftCheck[] | null>(null);

  useEffect(() => {
    let live = true;
    Promise.all([api.me(), api.draftingStatus()]).then(
      ([m, s]) => {
        if (!live) return;
        setMe(m);
        setStatus(s);
        if (m.dataSource === "sample") api.draftingThreads().then((t) => live && setSamples(t.filter((x) => !x.excluded)), () => undefined);
      },
      (e) => live && setError(draftErrorText(e)),
    );
    if (item) void readItemContext(item).then((c) => live && setCtx(c));
    return () => {
      live = false;
    };
  }, [api, item]);

  const isSample = me?.dataSource === "sample";
  // Reading a message in the sample workspace: there is no "new email" here, so start on a sample reply.
  useEffect(() => {
    if (isSample && ctx?.mode === "read" && !sample && samples[0]) setSample(samples[0].conversationId);
  }, [isSample, ctx, sample, samples]);
  const mode = isSample ? (sample ? "reply" : "new") : ctx ? draftMode(ctx) : "new";

  async function run(oneOff = false) {
    if (!item) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    setOneOffOffer(false);
    try {
      const fresh = await readItemContext(item); // recipients may have changed since the pane opened
      setCtx(fresh);
      const req: DraftRequest = {
        mode,
        surface: "outlook",
        instruction: instruction.trim() || null,
        quality: premium ? "premium" : "auto",
        oneOff,
      };
      if (isSample && sample) {
        req.conversationId = sample; // the sample conversation stands in for this Outlook item
      } else if (mode === "reply") {
        req.conversationId = fresh.conversationId;
        if (fresh.mode === "compose") {
          req.to = fresh.to;
          req.cc = fresh.cc;
        } else {
          req.replyAll = replyAll;
        }
      } else {
        req.to = fresh.to;
        req.cc = fresh.cc;
        req.subject = fresh.subject;
      }
      const d = await api.createDraft(req);
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

  async function insert() {
    try {
      await insertAtCursor(text);
      setNotice("Inserted at your cursor. Read it through before you send.");
      if (draft?.id) await api.draftFeedback(draft.id, { outcome: "inserted" }).catch(() => undefined);
    } catch (e) {
      setError(`Couldn't insert (${(e as Error).message}). Copy the text instead.`);
    }
  }

  async function reply(all: boolean) {
    openReply(text, all);
    if (draft?.id) await api.draftFeedback(draft.id, { outcome: "opened_reply" }).catch(() => undefined);
  }

  async function checkBeforeSending() {
    if (!item) return;
    setError(null);
    try {
      const [fresh, body] = await Promise.all([readItemContext(item), bodyText()]);
      const res = await api.checkText(body, fresh.to, fresh.cc, isSample ? null : fresh.conversationId);
      setSendChecks(res.checks);
    } catch (e) {
      setError(e instanceof ApiError ? draftErrorText(e) : `Couldn't read the email (${(e as Error).message}).`);
    }
  }

  async function rate(rating: "good" | "bad") {
    setRated(rating);
    if (draft?.id) await api.draftFeedback(draft.id, { rating }).catch(() => undefined);
  }

  if (!me || !status) {
    return <div className={styles.pane}>{error ? <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar> : <Spinner size="small" label="Connecting to Vanimo…" />}</div>; // prettier-ignore
  }
  const compose = ctx?.mode === "compose";
  const needsRecipients = !isSample && mode === "new" && ctx !== null && ctx.to.length + ctx.cc.length === 0;

  return (
    <div className={styles.pane}>
      <div className={styles.row}>
        <Text weight="semibold" size={400}>
          Vanimo
        </Text>
        {onSignOut && (
          <Button size="small" appearance="subtle" onClick={onSignOut}>
            Sign out
          </Button>
        )}
      </div>
      {!status.reviewDone && (
        <MessageBar intent="warning">
          <MessageBarBody>Open the Vanimo web app and finish choosing what Vanimo learns from first.</MessageBarBody>
        </MessageBar>
      )}
      {isSample && (
        <Field label="Sample workspace" hint="You're signed in to the sample workspace, so drafts use its conversations, not this email.">
          <Select value={sample} onChange={(_, d) => setSample(d.value)}>
            {ctx?.mode === "compose" && <option value="">New email to this email's recipients</option>}
            {samples.map((t) => (
              <option key={t.conversationId} value={t.conversationId}>
                Reply: {t.subject ?? "(no subject)"} ({t.sender.name ?? t.sender.email})
              </option>
            ))}
          </Select>
        </Field>
      )}
      <Caption1 className={styles.muted}>
        {mode === "reply" ? "Drafting a reply" : "Drafting a new email"}
        {status.generator === "offline" ? " · offline stand-in, no AI model" : ""}
      </Caption1>
      {needsRecipients && <Caption1>Add recipients to the email first, so Vanimo knows who it's for.</Caption1>}
      <Field label={mode === "new" ? "What should it say?" : "What should the reply say? (optional)"}>
        <Textarea value={instruction} maxLength={1000} onChange={(_, d) => setInstruction(d.value)} />
      </Field>
      <div className={styles.row}>
        {!compose && mode === "reply" && !isSample && (
          <Switch label="Reply all" checked={replyAll} onChange={(_, d) => setReplyAll(d.checked)} />
        )}
        {status.generator === "bedrock" && (
          <Switch
            label="Higher quality"
            checked={premium}
            disabled={status.premiumLeftToday === 0}
            onChange={(_, d) => setPremium(d.checked)}
          />
        )}
        <Button
          appearance="primary"
          disabled={busy || !status.reviewDone || needsRecipients || (mode === "new" && !instruction.trim())}
          onClick={() => void run()}
        >
          {busy ? "Drafting…" : draft ? "Draft again" : "Draft"}
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
              {compose ? (
                <Button appearance="primary" disabled={hasBlock(checks) && !confirmed} onClick={() => void insert()}>
                  Insert at cursor
                </Button>
              ) : (
                <>
                  <Button appearance="primary" disabled={hasBlock(checks) && !confirmed} onClick={() => void reply(false)}>
                    Reply with this
                  </Button>
                  <Button disabled={hasBlock(checks) && !confirmed} onClick={() => void reply(true)}>
                    Reply all
                  </Button>
                </>
              )}
              {draft.id && <RateButtons rated={rated} onRate={(r) => void rate(r)} />}
            </>
          }
        />
      )}
      {compose && (
        <>
          <Button onClick={() => void checkBeforeSending()}>Check before sending</Button>
          {sendChecks && sendChecks.length === 0 && (
            <MessageBar intent="success">
              <MessageBarBody>No problems found.</MessageBarBody>
            </MessageBar>
          )}
          {sendChecks &&
            sortChecks(sendChecks).map((c) => (
              <MessageBar key={c.code} intent={c.severity === "block" ? "error" : c.severity === "warn" ? "warning" : "info"}>
                <MessageBarBody>{c.message}</MessageBarBody>
              </MessageBar>
            ))}
        </>
      )}
      <Caption1 className={styles.muted}>
        {Office.context.diagnostics.platform} · {Office.context.diagnostics.version} · nested app auth{" "}
        {Office.context.requirements.isSetSupported("NestedAppAuth", "1.1") ? "yes" : "no"}
      </Caption1>
    </div>
  );
}

/** Local/dev only, while the Entra app is pending: the add-in signs in with a Vanimo password
 * account (the API refuses this in prod). The session lives in this pane's session storage. */
export function PasswordSignIn({ apiBase, onSignedIn }: { apiBase: string; onSignedIn: (token: string) => void }) {
  const styles = useStyles();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const body = (await res.json().catch(() => ({}))) as { token?: string; mustChangePassword?: boolean; error?: string };
      if (!res.ok || !body.token) throw new Error(body.error ?? `http_${res.status}`);
      if (body.mustChangePassword) {
        setError("Change your one-time password in the Vanimo web app first, then sign in here.");
        return;
      }
      onSignedIn(body.token);
    } catch (e) {
      setError((e as Error).message === "invalid_credentials" ? "Wrong email or password." : `Sign-in failed (${(e as Error).message}).`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.pane}>
      <Text weight="semibold" size={400}>
        Vanimo
      </Text>
      <Caption1 className={styles.muted}>Local sign-in (Microsoft sign-in isn't set up here yet).</Caption1>
      <Field label="Email">
        <Input type="email" value={email} onChange={(_, d) => setEmail(d.value)} />
      </Field>
      <Field label="Password">
        <Input type="password" value={password} onChange={(_, d) => setPassword(d.value)} />
      </Field>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      <Button appearance="primary" disabled={busy || !email || !password} onClick={() => void submit()}>
        Sign in
      </Button>
    </div>
  );
}
