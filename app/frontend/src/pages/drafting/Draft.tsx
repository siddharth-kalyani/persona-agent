/** Draft (M3): reply to a conversation or write a new email in your voice, see the pre-send
 * checks, and copy the result. The same drafting service backs the Outlook add-in; this page is
 * also the persona test bench. M5: Teams chats too (the same service as Teams' "Draft reply").
 * Nothing is ever sent from here.
 *
 * Layout: conversations on the left (two-line rows), the conversation and composer on the right,
 * the draft below it in reading type. Ctrl/⌘ Enter drafts from the instruction box. */
import {
  Button,
  Field,
  Input,
  Link,
  makeStyles,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  Spinner,
  Switch,
  Textarea,
  tokens,
  Tooltip,
} from "@fluentui/react-components";
import { Chat16Regular, Compose16Regular, Mail16Regular } from "@fluentui/react-icons";
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
import { DraftView, draftErrorText, hasBlock, RateButtons, recheck } from "../../drafting/DraftView";
import {
  absoluteTime,
  EmptyState,
  isMod,
  List,
  ListRow,
  modKey,
  Page,
  PageSkeleton,
  Pill,
  relativeTime,
  Rise,
  Section,
  StatusDot,
  Surface,
  Time,
  typo,
  vt,
} from "../../ui";
import { errorText } from "../Home";
import { newChatLink } from "../TeamsPrefill";

const useStyles = makeStyles({
  layout: {
    display: "grid",
    gap: "24px",
    gridTemplateColumns: "minmax(260px, 340px) minmax(0, 1fr)",
    alignItems: "start",
    "@media (max-width: 899px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  listPane: {
    display: "grid",
    gap: "12px",
    alignContent: "start",
    position: "sticky",
    top: "16px",
    maxHeight: "calc(100vh - 32px)",
    overflowY: "auto",
    "@media (max-width: 899px)": { position: "static", maxHeight: "none" },
  },
  groupLabel: { ...typo.label, color: vt.text3, padding: "8px 2px 0" },
  work: { display: "grid", gap: "20px", minWidth: 0 },
  engine: { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" },
  engineMeta: { ...typo.meta, color: vt.text3, ...typo.tabular },
  convoHead: { display: "grid", gap: "2px", paddingBottom: "12px", borderBottom: `1px solid ${tokens.colorNeutralStroke3}` },
  convoTitle: { ...typo.sectionTitle, color: vt.text1, margin: 0, overflowWrap: "anywhere" },
  convoMeta: { ...typo.meta, color: vt.text2 },
  messages: { display: "grid", maxHeight: "420px", overflowY: "auto", marginRight: "-8px", paddingRight: "8px" },
  message: { display: "grid", gap: "4px", padding: "14px 0", borderTop: `1px solid ${tokens.colorNeutralStroke3}`, ":first-child": { borderTop: "none" } },
  from: { display: "flex", gap: "8px", alignItems: "baseline", ...typo.meta, color: vt.text2 },
  fromName: { ...typo.itemTitle, color: vt.text1 },
  body: { whiteSpace: "pre-wrap", margin: 0, fontFamily: tokens.fontFamilyBase, ...typo.reading, color: vt.text1, overflowWrap: "anywhere" },
  excluded: { ...typo.meta, color: vt.text2, padding: "12px 0 0" },
  composer: { display: "grid", gap: "16px" },
  instruction: { ...typo.body, minHeight: "72px" },
  controls: {
    display: "flex",
    gap: "16px",
    alignItems: "center",
    flexWrap: "wrap",
    justifyContent: "space-between",
  },
  switches: { display: "flex", gap: "8px 16px", alignItems: "center", flexWrap: "wrap" },
  go: { display: "flex", gap: "10px", alignItems: "center", marginLeft: "auto" },
  hint: { ...typo.meta, color: vt.text3, "@media (pointer: coarse)": { display: "none" } },
  working: { display: "flex", gap: "10px", alignItems: "center", ...typo.meta, color: vt.text2 },
});

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
      const chat = draft.channel === "chat" && target?.kind === "chat";
      const conversation = draft.oneOff ? null : chat ? target.chat.chatId : target?.kind === "reply" ? target.thread.conversationId : null;
      const res = await api.checkText(text, draft.audience.to, draft.audience.cc, conversation, chat ? "chat" : "email");
      // A block found when drafting (a payment-change request in the thread) still stands: re-checking
      // your edits can't see the thread of a one-off draft, so it must not clear it.
      const merged = recheck(draft.checks, res.checks);
      setChecks(merged);
      setNotice(merged.length ? null : "No problems found in your text.");
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

  if (!status)
    return error ? (
      <Page title="Draft">
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      </Page>
    ) : (
      <PageSkeleton label="Loading…" />
    );

  const exclusion = (by: string | null, unverifiable: string) =>
    by === "unverifiable" ? unverifiable : `excluded by ${by === "organisation" ? "your organisation" : "you"}`;
  const drafting = target?.kind === "new" || (target?.kind === "chat" && chatNew);
  const conversation = target?.kind === "chat" ? chatView : view;

  return (
    <Page
      title="Draft"
      width="wide"
      description="Reply or write a new email or Teams message in your voice. Vanimo never sends: copy the draft into Outlook or Teams, or use the Vanimo button inside Outlook (or “Draft reply” on a Teams message)."
      eyebrow={
        <span className={styles.engine}>
          {status.generator === "offline" ? (
            <Pill tone="warning">Offline stand-in, no AI model</Pill>
          ) : (
            <StatusDot tone="accent">Claude on Amazon Bedrock</StatusDot>
          )}
          <span className={styles.engineMeta}>
            {status.generator === "offline"
              ? "Until the AWS account is connected, drafts are built without a model: your greeting, sign-off and register around your instruction."
              : `Standard: ${status.defaultModel} · Higher quality: ${status.premiumModel} (${status.premiumLeftToday} left today)`}
          </span>
        </span>
      }
    >
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
        <nav className={styles.listPane} aria-label="Conversations">
          <Button
            icon={<Compose16Regular />}
            appearance={target?.kind === "new" ? "primary" : "secondary"}
            onClick={() => reset({ kind: "new" })}
          >
            New email
          </Button>
          <div className={styles.groupLabel}>Reply to</div>
          {threads.length === 0 ? (
            <EmptyState title="No received mail">Mail you receive shows up here to reply to.</EmptyState>
          ) : (
            <List bordered label="Emails to reply to">
              {threads.map((t) => (
                <ListRow
                  key={t.conversationId}
                  leading={<Mail16Regular aria-hidden />}
                  title={t.subject ?? "(no subject)"}
                  meta={
                    <>
                      {t.sender.name ?? t.sender.email}
                      {t.excluded && ` · ${exclusion(t.excludedBy, "not used (someone can't be checked)")}`}
                    </>
                  }
                  trailing={t.excluded ? <Pill>Excluded</Pill> : <span title={absoluteTime(t.receivedAt)}>{shortTime(t.receivedAt)}</span>}
                  selected={target?.kind === "reply" && target.thread.conversationId === t.conversationId}
                  onClick={() => reset({ kind: "reply", thread: t })}
                />
              ))}
            </List>
          )}
          {chats.length > 0 && (
            <>
              <div className={styles.groupLabel}>Teams chats</div>
              <List bordered label="Teams chats to reply to">
                {chats.map((c) => (
                  <ListRow
                    key={c.chatId}
                    leading={<Chat16Regular aria-hidden />}
                    title={c.label}
                    meta={
                      <>
                        {CHAT_TYPES[c.chatType]} · {c.members} people
                        {c.excluded && ` · ${exclusion(c.excludedBy, "not used (can't be checked)")}`}
                      </>
                    }
                    trailing={c.excluded ? <Pill>Excluded</Pill> : undefined}
                    selected={target?.kind === "chat" && target.chat.chatId === c.chatId}
                    onClick={() => reset({ kind: "chat", chat: c })}
                  />
                ))}
              </List>
            </>
          )}
        </nav>

        <div className={styles.work}>
          {!target && (
            <EmptyState icon={<Compose16Regular />} title="Pick a conversation">
              Choose an email or a Teams chat to reply to, or start a new email. Vanimo writes in your voice for that
              audience; you edit and send it yourself.
            </EmptyState>
          )}
          {(target?.kind === "reply" || target?.kind === "chat") && (
            <Surface padding="m" as="article" aria-label="Conversation">
              <div className={styles.convoHead}>
                <h2 className={styles.convoTitle}>
                  {target.kind === "chat"
                    ? (chatView?.label ?? target.chat.label)
                    : (view?.subject ?? target.thread.subject ?? "(no subject)")}
                </h2>
                <span className={styles.convoMeta}>
                  {target.kind === "chat"
                    ? `${CHAT_TYPES[target.chat.chatType]} · ${target.chat.members} people`
                    : conversation
                      ? `${conversation.messages.length} message${conversation.messages.length === 1 ? "" : "s"}`
                      : "Email"}
                </span>
              </div>
              {(target.kind === "chat" ? target.chat.excluded : target.thread.excluded) && (
                <p className={styles.excluded}>
                  You can't view or use this {target.kind === "chat" ? "chat" : "conversation"}: it's excluded.
                </p>
              )}
              {conversation && conversation.messages.length > 0 && (
                <div className={styles.messages}>
                  {conversation.messages.map((m, i) => (
                    <div key={i} className={styles.message}>
                      <div className={styles.from}>
                        <span className={styles.fromName}>{m.fromMe ? "You" : (m.sender.name ?? m.sender.email)}</span>
                        <Time iso={m.sentAt} />
                      </div>
                      <pre className={styles.body}>{m.text}</pre>
                    </div>
                  ))}
                </div>
              )}
            </Surface>
          )}
          {target && (
            <div className={styles.composer}>
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
                label={drafting ? "What should it say?" : "What should the reply say? (optional)"}
                hint="For example: tell her I'll send the plan by Wednesday; ask him for the UAT feedback"
              >
                <Textarea
                  value={instruction}
                  maxLength={1000}
                  resize="vertical"
                  textarea={{ className: styles.instruction }}
                  onChange={(_, d) => setInstruction(d.value)}
                  onKeyDown={(e) => {
                    if (isMod(e, "Enter") && !busy && status.reviewDone) {
                      e.preventDefault();
                      void run();
                    }
                  }}
                />
              </Field>
              <div className={styles.controls}>
                <div className={styles.switches}>
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
                </div>
                <div className={styles.go}>
                  <span className={styles.hint} aria-hidden>
                    {modKey} ↵
                  </span>
                  <Tooltip content={`Draft (${modKey}+Enter in the instruction box)`} relationship="description">
                    <Button appearance="primary" disabled={busy || !status.reviewDone} onClick={() => void run()}>
                      {busy ? "Drafting…" : draft ? "Draft again" : "Draft"}
                    </Button>
                  </Tooltip>
                </div>
              </div>
            </div>
          )}
          {busy && (
            <div className={styles.working} role="status">
              <Spinner size="extra-tiny" />
              Writing in your voice. Names, ID numbers and never-send words are masked before the model sees anything.
            </div>
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
            <Rise visible appear>
              <div>
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
                      {draft.channel === "chat" && prefill && (draft.chatUsers?.length ?? 0) > 0 && (
                        <Button disabled={hasBlock(checks) && !confirmed} onClick={() => void openInTeams()}>
                          Open in Teams with this text
                        </Button>
                      )}
                      {draft.id && target?.kind === "reply" && (
                        <Button disabled={hasBlock(checks) && !confirmed} onClick={() => void placeInOutlook()}>
                          Put in my Drafts folder
                        </Button>
                      )}
                      <Button onClick={() => void checkAgain()}>Check my edits</Button>
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
              </div>
            </Rise>
          )}
        </div>
      </div>

      {recent.length > 0 && (
        <Section title="Recent drafts" description="What was drafted, never the text.">
          <List bordered label="Recent drafts">
            {recent.map((r) => (
              <ListRow
                key={r.id}
                title={`${r.mode === "reply" ? "Reply" : "New message"} to ${r.relationship}`}
                meta={[
                  r.surface,
                  r.generator === "offline" ? "offline stand-in" : r.modelId,
                  `${r.wordCount} words`,
                  r.checks.length ? `checks: ${r.checks.join(", ")}` : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
                trailing={
                  <>
                    {r.outcome && (
                      <Pill tone={r.outcome === "discarded" ? "neutral" : "success"}>{r.outcome.replace("_", " ")}</Pill>
                    )}
                    <Time iso={r.createdAt} />
                  </>
                }
              />
            ))}
          </List>
        </Section>
      )}
    </Page>
  );
}

/** Compact time for the conversation list: today's time, otherwise the day. */
function shortTime(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return relativeTime(iso, now);
}
