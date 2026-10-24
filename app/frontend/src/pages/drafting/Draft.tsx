/** Draft (M3): reply to a conversation or write a new email in your voice, see the pre-send
 * checks, and copy the result. The same drafting service backs the Outlook add-in; this page is
 * also the persona test bench. M5: Teams chats too (the same service as Teams' "Draft reply").
 * Nothing is ever sent from here.
 *
 * Layout: a conversation list on the left (email or Teams, people as avatars), the conversation and
 * a composer card on the right, the draft card below it. Ctrl/⌘ Enter drafts from the instruction box. */
import {
  Button,
  Field,
  Input,
  Link,
  makeStyles,
  Menu,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
  MessageBar,
  MessageBarActions,
  MessageBarBody,
  Spinner,
  Switch,
  Textarea,
  Tooltip,
  useAnnounce,
} from "@fluentui/react-components";
import {
  ArrowReply16Regular,
  CalendarLtr16Regular,
  Chat16Regular,
  ChevronDown16Regular,
  ChevronUp16Regular,
  Compose16Regular,
  Compose20Regular,
  Copy16Regular,
  Delete16Regular,
  EyeOff16Regular,
  FolderArrowRight16Regular,
  LockClosed16Regular,
  Mail16Regular,
  MoreHorizontal16Regular,
  Open16Regular,
  People16Regular,
  Send16Regular,
  ShieldTask16Regular,
  Warning16Regular,
} from "@fluentui/react-icons";
import { useCallback, useEffect, useRef, useState, type ReactElement } from "react";
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
import { AUTOSIZE, DraftView, draftErrorText, hasBlock, RateButtons, recheck } from "../../drafting/DraftView";
import {
  absoluteTime,
  EmptyState,
  EngineBadge,
  IconTile,
  isMod,
  Kbd,
  List,
  ListRow,
  modKey,
  Page,
  PageSkeleton,
  PersonAvatar,
  Pill,
  relativeTime,
  Rise,
  Section,
  Segmented,
  Surface,
  Time,
  typo,
  vt,
  type Tone,
} from "../../ui";
import { AUDIENCE } from "../commitments/Commitments";
import { errorText } from "../Home";
import { newChatLink } from "../TeamsPrefill";

const useStyles = makeStyles({
  layout: {
    display: "grid",
    gap: "20px",
    gridTemplateColumns: "minmax(300px, 400px) minmax(0, 1fr)",
    alignItems: "start",
    "@media (max-width: 899px)": { gridTemplateColumns: "minmax(0, 1fr)" },
  },
  listPane: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    position: "sticky",
    top: "16px",
    maxHeight: "calc(100vh - 32px)",
    minWidth: 0,
    // Below 1024px the 52px top bar is sticky too.
    "@media (max-width: 1023px)": { top: "68px", maxHeight: "calc(100vh - 84px)" },
    "@media (max-width: 899px)": { position: "static", maxHeight: "none" },
  },
  listTools: { display: "flex", alignItems: "center", gap: "8px", minWidth: 0, flexShrink: 0 },
  listSwitch: { flex: "1 1 auto", minWidth: 0 },
  scroll: {
    flex: "1 1 auto",
    overflowY: "auto",
    minHeight: 0,
    borderRadius: "12px",
    "@media (max-width: 899px)": { maxHeight: "420px" },
  },
  rowTime: { ...typo.label, fontWeight: 400, color: vt.text3, ...typo.tabular, whiteSpace: "nowrap" },
  work: { display: "grid", gap: "16px", minWidth: 0, outline: "none", scrollMarginTop: "68px" },
  convoHead: {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr)",
    gap: "12px",
    alignItems: "center",
    padding: "14px 16px",
    borderBottom: `1px solid ${vt.borderSubtle}`,
  },
  convoText: { display: "grid", gap: "2px", minWidth: 0 },
  convoTitle: { ...typo.sectionTitle, color: vt.text1, margin: 0, overflowWrap: "anywhere" },
  convoMeta: { ...typo.meta, color: vt.text2, display: "flex", alignItems: "center", gap: "4px", "& svg": { color: vt.text3 } },
  messages: { display: "grid", maxHeight: "440px", overflowY: "auto" },
  message: {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr)",
    gap: "4px 12px",
    padding: "16px",
    borderTop: `1px solid ${vt.borderSubtle}`,
    ":first-child": { borderTop: "none" },
  },
  from: { display: "flex", gap: "8px", alignItems: "baseline", flexWrap: "wrap", ...typo.meta, color: vt.text3 },
  fromName: { ...typo.itemTitle, color: vt.text1 },
  body: {
    gridColumn: "2",
    whiteSpace: "pre-wrap",
    margin: 0,
    fontFamily: "inherit",
    ...typo.reading,
    color: vt.text1,
    overflowWrap: "anywhere",
  },
  excluded: { display: "flex", gap: "8px", alignItems: "center", ...typo.meta, color: vt.text2, padding: "16px" },
  composer: { display: "grid", gap: "16px" },
  composerFields: { display: "grid", gap: "12px", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", "@media (max-width: 639px)": { gridTemplateColumns: "1fr" } },
  instruction: { ...typo.body, minHeight: "84px", maxHeight: "40vh", fieldSizing: "content" },
  controls: {
    display: "flex",
    gap: "12px 16px",
    alignItems: "center",
    flexWrap: "wrap",
    justifyContent: "space-between",
    paddingTop: "14px",
    borderTop: `1px solid ${vt.borderSubtle}`,
  },
  switches: { display: "flex", gap: "4px 16px", alignItems: "center", flexWrap: "wrap" },
  go: { display: "flex", gap: "12px", alignItems: "center", marginLeft: "auto" },
  hint: { display: "inline-flex", gap: "4px", alignItems: "center", ...typo.meta, color: vt.text3, "@media (pointer: coarse)": { display: "none" } },
  never: { display: "inline-flex", gap: "6px", alignItems: "center", ...typo.meta, color: vt.text3, "& svg": { flexShrink: 0 } },
  working: { display: "flex", gap: "10px", alignItems: "center", ...typo.meta, color: vt.text2 },
  // Fills the space beside the list; on one column the list is right above it, so it isn't needed.
  emptyCard: {
    display: "grid",
    placeItems: "center",
    minHeight: "min(560px, calc(100vh - 220px))",
    padding: "8px 24px",
    "@media (max-width: 899px)": { display: "none" },
  },
  spacer: { flexGrow: 1 },
  metaIcons: { display: "inline-flex", alignItems: "center", gap: "4px", "& + &": { marginLeft: "10px" } },
  checksTip: { display: "grid", gap: "2px" },
  more: { display: "flex", justifyContent: "center" },
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

/** A Teams chat's face: the person for a 1:1, a tile for a group or a meeting chat. */
function ChatLeading({ chat }: { chat: DraftChat }) {
  if (chat.chatType === "oneOnOne") return <PersonAvatar name={chat.label} size={32} />;
  return <IconTile icon={chat.chatType === "meeting" ? <CalendarLtr16Regular /> : <People16Regular />} tone="purple" size={32} />;
}

/** Pre-send checks by name, for the recent drafts list. */
const CHECK_NAMES: Record<string, string> = {
  lookalike_sender: "Look-alike sender",
  lookalike_domain: "Look-alike domain",
  payment_change: "Payment-details change",
  fill_in: "Placeholder to fill in",
};

/** Where a recent draft was made. */
const SURFACES: Record<string, { icon: ReactElement; tone: Tone; label: string }> = {
  outlook: { icon: <Mail16Regular />, tone: "blue", label: "Outlook" },
  teams: { icon: <Chat16Regular />, tone: "purple", label: "Teams" },
  web: { icon: <Compose16Regular />, tone: "accent", label: "Web" },
};

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
  const workRef = useRef<HTMLDivElement>(null);
  const { announce } = useAnnounce();
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
  const [list, setList] = useState<"email" | "chat">("email");
  const [allRecent, setAllRecent] = useState(false);

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
    // One column on narrow screens: the list comes first, so bring the chosen conversation into view.
    if (window.matchMedia?.("(max-width: 899px)").matches === true) {
      requestAnimationFrame(() => {
        workRef.current?.scrollIntoView?.({ block: "start" });
        workRef.current?.focus({ preventScroll: true });
      });
    }
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
      announce(`Draft ready, ${d.text.split(/\s+/).filter(Boolean).length} words.`, { polite: true });
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
  const blocked = hasBlock(checks) && !confirmed;
  const showing = chats.length > 0 ? list : "email";

  return (
    <Page
      title="Draft"
      width="wide"
      description="Reply or write in your voice. Vanimo never sends: you do."
      info="Copy the draft into Outlook or Teams, put a reply in your Outlook Drafts folder, or use the Vanimo button inside Outlook (or “Draft reply” on a Teams message). Names, ID numbers and never-send words are masked before any model sees the conversation."
      actions={
        <EngineBadge
          offline={status.generator === "offline"}
          detail={
            status.generator === "offline"
              ? "Until the AWS account is connected, drafts are built without a model: your greeting, sign-off and register around your instruction."
              : `Standard: ${status.defaultModel} · Higher quality: ${status.premiumModel} (${status.premiumLeftToday} left today)`
          }
        />
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
          <div className={styles.listTools}>
            {chats.length > 0 && (
              <div className={styles.listSwitch}>
                <Segmented
                  label="Conversations to reply to"
                  value={list}
                  onChange={setList}
                  segments={[
                    { value: "email", label: "Email", icon: <Mail16Regular />, count: threads.length },
                    { value: "chat", label: "Teams", icon: <Chat16Regular />, count: chats.length },
                  ]}
                />
              </div>
            )}
            <Button icon={<Compose16Regular />} aria-pressed={target?.kind === "new"} onClick={() => reset({ kind: "new" })}>
              New email
            </Button>
          </div>
          <div className={styles.scroll}>
            {showing === "email" &&
              (threads.length === 0 ? (
                <Surface padding="none">
                  <EmptyState headingLevel={2} icon={<Mail16Regular />} title="No received mail" center>
                    Mail you receive shows up here to reply to.
                  </EmptyState>
                </Surface>
              ) : (
                <List bordered label="Emails to reply to">
                  {threads.map((t) => (
                    <ListRow
                      key={t.conversationId}
                      leading={<PersonAvatar name={t.sender.name ?? t.sender.email} id={t.sender.email} size={32} />}
                      title={t.subject ?? "(no subject)"}
                      meta={
                        <>
                          {t.sender.name ?? t.sender.email}
                          {t.excluded && ` · ${exclusion(t.excludedBy, "not used (someone can't be checked)")}`}
                        </>
                      }
                      trailing={
                        t.excluded ? (
                          <Pill icon={<EyeOff16Regular />}>Excluded</Pill>
                        ) : (
                          <span className={styles.rowTime} title={absoluteTime(t.receivedAt)}>
                            {shortTime(t.receivedAt)}
                          </span>
                        )
                      }
                      selected={target?.kind === "reply" && target.thread.conversationId === t.conversationId}
                      onClick={() => reset({ kind: "reply", thread: t })}
                    />
                  ))}
                </List>
              ))}
            {showing === "chat" && (
              <List bordered label="Teams chats to reply to">
                {chats.map((c) => (
                  <ListRow
                    key={c.chatId}
                    leading={<ChatLeading chat={c} />}
                    title={c.label}
                    meta={
                      <>
                        {CHAT_TYPES[c.chatType]} · {c.members} people
                        {c.excluded && ` · ${exclusion(c.excludedBy, "not used (can't be checked)")}`}
                      </>
                    }
                    trailing={
                      c.excluded ? (
                        <Pill icon={<EyeOff16Regular />}>Excluded</Pill>
                      ) : c.lastActivityAt ? (
                        <span className={styles.rowTime} title={absoluteTime(c.lastActivityAt)}>
                          {shortTime(c.lastActivityAt)}
                        </span>
                      ) : undefined
                    }
                    selected={target?.kind === "chat" && target.chat.chatId === c.chatId}
                    onClick={() => reset({ kind: "chat", chat: c })}
                  />
                ))}
              </List>
            )}
          </div>
        </nav>

        <div className={styles.work} ref={workRef} tabIndex={-1} aria-label="Conversation and draft">
          {!target && (
            <Surface padding="none" className={styles.emptyCard}>
              <EmptyState headingLevel={2} icon={<Compose20Regular />} title="Pick a conversation" center>
                Choose an email or a Teams chat to reply to, or start a new email. Vanimo writes in your voice for that
                audience; you edit and send it yourself.
              </EmptyState>
            </Surface>
          )}
          {(target?.kind === "reply" || target?.kind === "chat") && (
            <Surface padding="none" as="article" aria-label="Conversation">
              <div className={styles.convoHead}>
                <IconTile
                  icon={target.kind === "chat" ? <Chat16Regular /> : <Mail16Regular />}
                  tone={target.kind === "chat" ? "purple" : "blue"}
                  size={36}
                />
                <div className={styles.convoText}>
                  <h2 className={styles.convoTitle}>
                    {target.kind === "chat"
                      ? (chatView?.label ?? target.chat.label)
                      : (view?.subject ?? target.thread.subject ?? "(no subject)")}
                  </h2>
                  <span className={styles.convoMeta}>
                    {target.kind === "chat" ? (
                      <>
                        <People16Regular aria-hidden />
                        {`${CHAT_TYPES[target.chat.chatType]} · ${target.chat.members} people`}
                      </>
                    ) : conversation ? (
                      <>
                        <Mail16Regular aria-hidden />
                        {`${conversation.messages.length} message${conversation.messages.length === 1 ? "" : "s"}`}
                      </>
                    ) : (
                      "Email"
                    )}
                  </span>
                </div>
              </div>
              {(target.kind === "chat" ? target.chat.excluded : target.thread.excluded) && (
                <p className={styles.excluded}>
                  <EyeOff16Regular aria-hidden />
                  You can't view or use this {target.kind === "chat" ? "chat" : "conversation"}: it's excluded.
                </p>
              )}
              {conversation && conversation.messages.length > 0 && (
                <div className={styles.messages}>
                  {conversation.messages.map((m, i) => (
                    <div key={i} className={styles.message}>
                      <PersonAvatar name={m.fromMe ? "You" : (m.sender.name ?? m.sender.email)} id={m.sender.email} size={32} />
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
            <Surface padding="m" as="section" className={styles.composer} aria-label="Composer">
              {target.kind === "new" && (
                <div className={styles.composerFields}>
                  <Field label="To" hint="Email addresses, separated by commas">
                    <Input value={to} contentBefore={<People16Regular />} onChange={(_, d) => setTo(d.value)} />
                  </Field>
                  <Field label="Subject">
                    <Input value={subject} onChange={(_, d) => setSubject(d.value)} />
                  </Field>
                </div>
              )}
              <Field
                label={drafting ? "What should it say?" : "What should the reply say? (optional)"}
                hint="For example: tell her I'll send the plan by Wednesday; ask him for the UAT feedback"
              >
                <Textarea
                  value={instruction}
                  maxLength={1000}
                  resize={AUTOSIZE ? "none" : "vertical"}
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
                    <Kbd>{modKey}</Kbd>
                    <Kbd>↵</Kbd>
                  </span>
                  <Tooltip content={`Draft (${modKey}+Enter in the instruction box)`} relationship="description">
                    <Button
                      appearance={draft ? "secondary" : "primary"}
                      icon={busy ? <Spinner size="extra-tiny" /> : target.kind === "new" || drafting ? <Compose16Regular /> : <ArrowReply16Regular />}
                      disabled={busy || !status.reviewDone}
                      onClick={() => void run()}
                    >
                      {busy ? "Drafting…" : draft ? "Draft again" : "Draft"}
                    </Button>
                  </Tooltip>
                </div>
              </div>
            </Surface>
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
                      <Button appearance="primary" icon={<Copy16Regular />} disabled={blocked} onClick={() => void copy()}>
                        Copy
                      </Button>
                      {draft.id && target?.kind === "reply" && (
                        <Button icon={<FolderArrowRight16Regular />} disabled={blocked} onClick={() => void placeInOutlook()}>
                          Put in my Drafts folder
                        </Button>
                      )}
                      {draft.channel === "chat" && prefill && (draft.chatUsers?.length ?? 0) > 0 && (
                        <Button icon={<Open16Regular />} disabled={blocked} onClick={() => void openInTeams()}>
                          Open in Teams with this text
                        </Button>
                      )}
                      <Button icon={<ShieldTask16Regular />} onClick={() => void checkAgain()}>
                        Check my edits
                      </Button>
                      {draft.id ? <RateButtons rated={rated} onRate={(r) => void rate(r)} /> : <span className={styles.spacer} />}
                      <Menu positioning="below-end">
                        <MenuTrigger disableButtonEnhancement>
                          <Tooltip content="More actions" relationship="label" withArrow>
                            <Button appearance="subtle" size="small" icon={<MoreHorizontal16Regular />} />
                          </Tooltip>
                        </MenuTrigger>
                        <MenuPopover>
                          <MenuList>
                            {draft.id && status.sourceKind === "sample" && (
                              <MenuItem icon={<Send16Regular />} onClick={() => void markSent()}>
                                Mark as sent (sample)
                              </MenuItem>
                            )}
                            <MenuItem icon={<Delete16Regular />} onClick={() => void discard()}>
                              Discard
                            </MenuItem>
                          </MenuList>
                        </MenuPopover>
                      </Menu>
                    </>
                  }
                />
              </div>
            </Rise>
          )}
          {target && (
            <span className={styles.never}>
              <LockClosed16Regular aria-hidden />
              Vanimo never sends. You copy or place the draft and send it yourself.
            </span>
          )}
        </div>
      </div>

      {recent.length > 0 && (
        <Section title="Recent drafts" count={recent.length} description="What was drafted, never the text.">
          <List bordered label="Recent drafts">
            {(allRecent ? recent : recent.slice(0, 5)).map((r) => {
              const surface = SURFACES[r.surface] ?? SURFACES.web!;
              return (
                <ListRow
                  key={r.id}
                  leading={<IconTile icon={surface.icon} tone={surface.tone} size={32} />}
                  title={`${r.mode === "reply" ? "Reply" : "New message"} to ${AUDIENCE[r.relationship] ?? r.relationship}`}
                  meta={
                    <>
                      <span className={styles.metaIcons}>
                        {surface.label} · {r.generator === "offline" ? "offline stand-in" : r.modelId} · {r.wordCount} words
                      </span>
                      {r.checks.length > 0 && (
                        <span className={styles.metaIcons}>
                          <Tooltip
                            relationship="description"
                            withArrow
                            content={
                              <span className={styles.checksTip}>
                                {r.checks.map((c) => (
                                  <span key={c}>{CHECK_NAMES[c] ?? c.replaceAll("_", " ")}</span>
                                ))}
                              </span>
                            }
                          >
                            <Pill tabIndex={0} tone="warning" icon={<Warning16Regular />}>
                              {r.checks.length} {r.checks.length === 1 ? "check" : "checks"}
                            </Pill>
                          </Tooltip>
                        </span>
                      )}
                    </>
                  }
                  trailing={
                    <>
                      {r.outcome && (
                        <Pill tone={r.outcome === "discarded" ? "neutral" : "success"} dot>
                          {r.outcome.replace("_", " ")}
                        </Pill>
                      )}
                      <Time iso={r.createdAt} />
                    </>
                  }
                />
              );
            })}
          </List>
          {recent.length > 5 && (
            <div className={styles.more}>
              <Button
                appearance="subtle"
                size="small"
                icon={allRecent ? <ChevronUp16Regular /> : <ChevronDown16Regular />}
                aria-expanded={allRecent}
                onClick={() => setAllRecent((v) => !v)}
              >
                {allRecent ? "Show fewer" : `Show all ${recent.length}`}
              </Button>
            </div>
          )}
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
