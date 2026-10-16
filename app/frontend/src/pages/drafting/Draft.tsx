/** Draft (M3): reply to a conversation or write a new email in your voice, see the pre-send
 * checks, and copy the result. The same drafting service backs the Outlook add-in; this page is
 * also the persona test bench. M5: Teams chats too (the same service as Teams' "Draft reply").
 * Nothing is ever sent from here. */
import {
  Badge,
  Button,
  Caption1,
  Card,
  CardHeader,
  Field,
  Input,
  Link,
  makeStyles,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  Spinner,
  Switch,
  Text,
  Textarea,
  Title3,
  tokens,
} from "@fluentui/react-components";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ApiError,
  type ChatView,
  type Draft as DraftResult,
  type DraftChat,
  type DraftCheck,
  type DraftingStatus,
  type DraftRequest,
  type DraftSummary,
  type DraftThread,
  type PersonRef,
  type ThreadView,
} from "../../api/client";
import { useApi } from "../../api/context";
import { DraftView, draftErrorText, hasBlock, RateButtons } from "../../drafting/DraftView";
import { errorText } from "../Home";
import { newChatLink } from "../TeamsPrefill";

const useStyles = makeStyles({
  stack: { display: "grid", gap: tokens.spacingVerticalL },
  layout: { display: "grid", gap: tokens.spacingHorizontalXL, gridTemplateColumns: "minmax(240px, 320px) 1fr", "@media (max-width: 760px)": { gridTemplateColumns: "1fr" } },
  list: { display: "grid", gap: tokens.spacingVerticalXS, alignContent: "start" },
  thread: { textAlign: "left", justifyContent: "flex-start", height: "auto", padding: tokens.spacingVerticalS },
  threadText: { display: "grid", gap: "2px" },
  row: { display: "flex", gap: tokens.spacingHorizontalM, alignItems: "center", flexWrap: "wrap" },
  muted: { color: tokens.colorNeutralForeground3 },
  message: { whiteSpace: "pre-wrap", margin: 0, fontFamily: tokens.fontFamilyBase, fontSize: tokens.fontSizeBase300 },
}); // prettier-ignore

/** "a@x.com, Bob <b@y.com>" → people. Invalid entries are returned separately. */
export function parseRecipients(value: string): { people: PersonRef[]; invalid: string[] } {
  const people: PersonRef[] = [];
  const invalid: string[] = [];
  for (const raw of value.split(/[,;\n]+/)) {
    const part = raw.trim();
    if (!part) continue;
    const m = part.match(/^(?:"?([^"<]*?)"?\s*<)?\s*([^\s<>@]+@[^\s<>@]+\.[^\s<>@]+)\s*>?$/);
    if (m?.[2]) people.push({ email: m[2].toLowerCase(), name: m[1]?.trim() || null });
    else invalid.push(part);
  }
  return { people, invalid };
}

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

type Target = { kind: "reply"; thread: DraftThread } | { kind: "new" } | { kind: "chat"; chat: DraftChat };

const CHAT_TYPES: Record<DraftChat["chatType"], string> = { oneOnOne: "1:1 chat", group: "group chat", meeting: "meeting chat" };

export function Draft() {
  const styles = useStyles();
  const api = useApi();
  const navigate = useNavigate();
  const [status, setStatus] = useState<DraftingStatus | null>(null);
  const [threads, setThreads] = useState<DraftThread[]>([]);
  const [recent, setRecent] = useState<DraftSummary[]>([]);
  const [target, setTarget] = useState<Target | null>(null);
  const [view, setView] = useState<ThreadView | null>(null);
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [instruction, setInstruction] = useState("");
  const [premium, setPremium] = useState(false);
  const [replyAll, setReplyAll] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [oneOffOffer, setOneOffOffer] = useState(false);
  const [draft, setDraft] = useState<DraftResult | null>(null);
  const [text, setText] = useState("");
  const [checks, setChecks] = useState<DraftCheck[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [rated, setRated] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [chats, setChats] = useState<DraftChat[]>([]);
  const [chatView, setChatView] = useState<ChatView | null>(null);
  const [chatNew, setChatNew] = useState(false);
  const [prefill, setPrefill] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [s, t, r] = await Promise.all([api.draftingStatus(), api.draftingThreads(), api.drafts()]);
      setStatus(s);
      setThreads(t);
      setRecent(r);
    } catch (e) {
      setError(errorText(e));
    }
    // Teams chats and the organisation's prefill switch: optional extras, never block the page.
    api.draftingChats().then(setChats, () => setChats([]));
    api.teamsConfig().then((c) => setPrefill(c.prefill), () => setPrefill(false));
  }, [api]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function reset(next: Target) {
    setTarget(next);
    setDraft(null);
    setError(null);
    setNotice(null);
    setOneOffOffer(false);
    setView(null);
    setChatView(null);
    setChatNew(false);
    setInstruction("");
    if (next.kind === "reply" && !next.thread.excluded) {
      api.draftingThread(next.thread.conversationId).then(setView, () => setView(null));
    }
    if (next.kind === "chat" && !next.chat.excluded) {
      api.draftingChat(next.chat.chatId).then(setChatView, () => setChatView(null));
    }
  }

  async function run(oneOff = false) {
    if (!target) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    setOneOffOffer(false);
    const req: DraftRequest = {
      mode: target.kind === "chat" ? (chatNew ? "new" : "reply") : target.kind,
      surface: "web",
      instruction: instruction.trim() || null,
      quality: premium ? "premium" : "auto",
      oneOff,
    };
    if (target.kind === "chat") {
      req.channel = "chat";
      req.conversationId = target.chat.chatId;
    } else if (target.kind === "reply") {
      req.conversationId = target.thread.conversationId;
      req.replyAll = replyAll;
    } else {
      const { people, invalid } = parseRecipients(to);
      if (invalid.length) {
        setError(`Not an email address: ${invalid.join(", ")}`);
        setBusy(false);
        return;
      }
      req.to = people;
      req.subject = subject.trim() || null;
    }
    try {
      const d = await api.createDraft(req);
      setDraft(d);
      setText(d.text);
      setChecks(d.checks);
      setConfirmed(false);
      setRated(null);
      void api.drafts().then(setRecent, () => undefined);
    } catch (e) {
      setDraft(null);
      setError(draftErrorText(e));
      setOneOffOffer(e instanceof ApiError && e.code === "conversation_excluded" && e.body.oneOffAllowed === true);
    } finally {
      setBusy(false);
    }
  }

  async function checkAgain() {
    if (!draft) return;
    try {
      const res = await api.checkText(text, draft.audience.to, draft.audience.cc, draft.oneOff ? null : (target?.kind === "reply" ? target.thread.conversationId : null));
      // A block found when drafting (a payment-change request in the thread) still stands: re-checking
      // your edits can't see the thread of a one-off draft, so it must not clear it.
      const blocks = draft.checks.filter((c) => c.severity === "block" && !res.checks.some((r) => r.code === c.code));
      setChecks([...blocks, ...res.checks]);
      setNotice(res.checks.length || blocks.length ? null : "No problems found in your text.");
    } catch (e) {
      setError(draftErrorText(e));
    }
  }

  async function copy() {
    if (!draft) return;
    try {
      await navigator.clipboard.writeText(text);
      setNotice("Copied. Paste it into your email.");
      if (draft.id) await api.draftFeedback(draft.id, { outcome: "copied" });
    } catch {
      setNotice("Couldn't copy automatically: select the text and copy it.");
    }
  }

  async function openInTeams() {
    if (!draft?.chatUsers?.length) return;
    window.open(newChatLink(draft.chatUsers.join(","), text), "_blank", "noreferrer");
    if (draft.id) await api.draftFeedback(draft.id, { outcome: "opened_chat" }).catch(() => undefined);
  }

  async function placeInOutlook() {
    if (!draft?.id) return;
    try {
      const res = await api.placeDraft(draft.id, text, confirmed);
      setNotice(res.webLink ? "In your Outlook Drafts folder." : "In your Drafts folder (simulated in the sample workspace).");
    } catch (e) {
      setError(draftErrorText(e));
    }
  }

  async function markSent() {
    if (!draft?.id) return;
    try {
      const res = await api.markSent(draft.id, text);
      const label = { sent_as_is: "sent as is", light_edit: "a light edit", heavy_edit: "a heavy edit", rewritten: "a rewrite" }[
        res.outcome
      ];
      const learnt = res.edits.filter((e) => e !== "content");
      setNotice(
        `Recorded as ${label ?? res.outcome} (${Math.round(res.editShare * 100)}% changed).` +
          (learnt.length ? ` Vanimo will learn from your changes to: ${learnt.join(", ").replace("_", "-")}.` : ""),
      );
    } catch (e) {
      setError(draftErrorText(e));
    }
  }

  async function rate(rating: "good" | "bad") {
    setRated(rating);
    if (draft?.id) await api.draftFeedback(draft.id, { rating }).catch(() => undefined);
  }

  async function discard() {
    if (draft?.id) await api.draftFeedback(draft.id, { outcome: "discarded" }).catch(() => undefined);
    setDraft(null);
  }

  if (!status) return error ? <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar> : <Spinner label="Loading…" />;

  return (
    <div className={styles.stack}>
      <div>
        <Title3 as="h2">Draft</Title3>
        <Text as="p">
          Reply or write a new email or Teams message in your voice. Vanimo never sends: copy the draft into Outlook or
          Teams, or use the Vanimo button inside Outlook (or "Draft reply" on a Teams message).
        </Text>
      </div>
      <div className={styles.row}>
        {status.generator === "offline" ? (
          <Badge appearance="tint" color="warning">Offline stand-in, no AI model</Badge>
        ) : (
          <Badge appearance="tint">Claude on Amazon Bedrock</Badge>
        )}
        <Caption1 className={styles.muted}>
          {status.generator === "offline"
            ? "Until the AWS account is connected, drafts are built without a model: your greeting, sign-off and register around your instruction."
            : `Standard: ${status.defaultModel} · Higher quality: ${status.premiumModel} (${status.premiumLeftToday} left today)`}
        </Caption1>
      </div>
      {!status.reviewDone && (
        <MessageBar intent="warning">
          <MessageBarBody>Vanimo can't draft until you finish choosing what it learns from.</MessageBarBody>
          <MessageBarActions>
            <Button onClick={() => navigate("/setup")}>Go to setup</Button>
          </MessageBarActions>
        </MessageBar>
      )}
      {status.reviewDone && status.learnedItems === 0 && (
        <MessageBar intent="info">
          <MessageBarBody>
            Your style isn't learned yet, so drafts use a neutral style. <Link onClick={() => navigate("/learning")}>Start learning</Link>
          </MessageBarBody>
        </MessageBar>
      )}

      <div className={styles.layout}>
        <div className={styles.list}>
          <Button appearance={target?.kind === "new" ? "primary" : "secondary"} onClick={() => reset({ kind: "new" })}>
            New email
          </Button>
          <Caption1 className={styles.muted}>Reply to</Caption1>
          {threads.length === 0 && <Caption1>No received mail found.</Caption1>}
          {threads.map((t) => (
            <Button
              key={t.conversationId}
              className={styles.thread}
              appearance={target?.kind === "reply" && target.thread.conversationId === t.conversationId ? "primary" : "subtle"}
              onClick={() => reset({ kind: "reply", thread: t })}
            >
              <span className={styles.threadText}>
                <Text weight="semibold" truncate wrap={false}>{t.subject ?? "(no subject)"}</Text>
                <Caption1>
                  {t.sender.name ?? t.sender.email} · {when(t.receivedAt)}
                  {t.excluded &&
                    (t.excludedBy === "unverifiable"
                      ? " · not used (someone can't be checked)"
                      : ` · excluded by ${t.excludedBy === "organisation" ? "your organisation" : "you"}`)}
                </Caption1>
              </span>
            </Button>
          ))}
          {chats.length > 0 && <Caption1 className={styles.muted}>Teams chats</Caption1>}
          {chats.map((c) => (
            <Button
              key={c.chatId}
              className={styles.thread}
              appearance={target?.kind === "chat" && target.chat.chatId === c.chatId ? "primary" : "subtle"}
              onClick={() => reset({ kind: "chat", chat: c })}
            >
              <span className={styles.threadText}>
                <Text weight="semibold" truncate wrap={false}>{c.label}</Text>
                <Caption1>
                  {CHAT_TYPES[c.chatType]} · {c.members} people
                  {c.excluded &&
                    (c.excludedBy === "unverifiable"
                      ? " · not used (can't be checked)"
                      : ` · excluded by ${c.excludedBy === "organisation" ? "your organisation" : "you"}`)}
                </Caption1>
              </span>
            </Button>
          ))}
        </div>

        <div className={styles.stack}>
          {!target && <Text>Pick a conversation or a Teams chat to reply to, or start a new email.</Text>}
          {target?.kind === "chat" && (
            <Card>
              <CardHeader header={<Text weight="semibold">{chatView?.label ?? target.chat.label}</Text>} />
              {target.chat.excluded && <Caption1>You can't view or use this chat: it's excluded.</Caption1>}
              {chatView?.messages.map((m, i) => (
                <div key={i}>
                  <Caption1 className={styles.muted}>
                    {m.fromMe ? "You" : (m.sender.name ?? m.sender.email)} · {when(m.sentAt)}
                  </Caption1>
                  <pre className={styles.message}>{m.text}</pre>
                </div>
              ))}
            </Card>
          )}
          {target?.kind === "reply" && (
            <Card>
              <CardHeader header={<Text weight="semibold">{view?.subject ?? target.thread.subject ?? "(no subject)"}</Text>} />
              {target.thread.excluded && <Caption1>You can't view or use this conversation: it's excluded.</Caption1>}
              {view?.messages.map((m, i) => (
                <div key={i}>
                  <Caption1 className={styles.muted}>
                    {m.fromMe ? "You" : (m.sender.name ?? m.sender.email)} · {when(m.sentAt)}
                  </Caption1>
                  <pre className={styles.message}>{m.text}</pre>
                </div>
              ))}
            </Card>
          )}
          {target && (
            <>
              {target.kind === "new" && (
                <>
                  <Field label="To" hint="Email addresses, separated by commas">
                    <Input value={to} onChange={(_, d) => setTo(d.value)} />
                  </Field>
                  <Field label="Subject">
                    <Input value={subject} onChange={(_, d) => setSubject(d.value)} />
                  </Field>
                </>
              )}
              <Field
                label={
                  target.kind === "new" || (target.kind === "chat" && chatNew)
                    ? "What should it say?"
                    : "What should the reply say? (optional)"
                }
                hint="For example: tell her I'll send the plan by Wednesday; ask him for the UAT feedback"
              >
                <Textarea value={instruction} maxLength={1000} onChange={(_, d) => setInstruction(d.value)} />
              </Field>
              <div className={styles.row}>
                {target.kind === "reply" && (
                  <Switch label="Reply all" checked={replyAll} onChange={(_, d) => setReplyAll(d.checked)} />
                )}
                {target.kind === "chat" && (
                  <Switch label="New message (not a reply)" checked={chatNew} onChange={(_, d) => setChatNew(d.checked)} />
                )}
                {status.generator === "bedrock" && (
                  <Switch
                    label="Higher quality"
                    checked={premium}
                    disabled={status.premiumLeftToday === 0}
                    onChange={(_, d) => setPremium(d.checked)}
                  />
                )}
                <Button appearance="primary" disabled={busy || !status.reviewDone} onClick={() => void run()}>
                  {busy ? "Drafting…" : draft ? "Draft again" : "Draft"}
                </Button>
              </div>
            </>
          )}
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
                  {draft.channel === "chat" && prefill && (
                    <Button disabled={hasBlock(checks) && !confirmed} onClick={() => void openInTeams()}>
                      Open in Teams with this text
                    </Button>
                  )}
                  {draft.channel !== "chat" && <Button onClick={() => void checkAgain()}>Check my edits</Button>}
                  {draft.id && target?.kind === "reply" && (
                    <Button disabled={hasBlock(checks) && !confirmed} onClick={() => void placeInOutlook()}>
                      Put in my Drafts folder
                    </Button>
                  )}
                  {draft.id && status.sourceKind === "sample" && (
                    <Button onClick={() => void markSent()}>Mark as sent (sample)</Button>
                  )}
                  <Button appearance="subtle" onClick={() => void discard()}>
                    Discard
                  </Button>
                  {draft.id && <RateButtons rated={rated} onRate={(r) => void rate(r)} />}
                </>
              }
            />
          )}
        </div>
      </div>

      {recent.length > 0 && (
        <Card>
          <CardHeader header={<Text weight="semibold">Recent drafts</Text>} description={<Caption1>What was drafted, never the text</Caption1>} />
          {recent.map((r) => (
            <Caption1 key={r.id}>
              {when(r.createdAt)} · {r.mode === "reply" ? "reply" : "new message"} to {r.relationship} · {r.surface} ·{" "}
              {r.generator === "offline" ? "offline stand-in" : r.modelId} · {r.wordCount} words
              {r.outcome ? ` · ${r.outcome.replace("_", " ")}` : ""}
              {r.checks.length ? ` · checks: ${r.checks.join(", ")}` : ""}
            </Caption1>
          ))}
        </Card>
      )}
    </div>
  );
}
