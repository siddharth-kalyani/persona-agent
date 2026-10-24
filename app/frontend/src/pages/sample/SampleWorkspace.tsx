/** The sample workspace as a mail client: a folder rail, a message list and a reading pane, with what
 * Vanimo did with each item stated plainly. Below 1220px the folders run across the top; on phones the
 * list and the reading pane are separate views. */
import { Button, makeStyles, mergeClasses, MessageBar, MessageBarBody, shorthands, Spinner, tokens } from "@fluentui/react-components";
import {
  ArrowLeft16Regular,
  CalendarLtr16Regular,
  Chat16Regular,
  ChatMultiple16Regular,
  Clock16Regular,
  Database16Regular,
  EyeOff16Regular,
  Info16Regular,
  MailInbox16Regular,
  MailRead20Regular,
  People16Regular,
  Person16Regular,
  Send16Regular,
  ShieldCheckmark16Regular,
} from "@fluentui/react-icons";
import { useEffect, useMemo, useRef, useState, type ReactElement, type ReactNode } from "react";
import {
  ApiError,
  type ItemStatus,
  type SampleChat,
  type SamplePerson,
  type SampleWorkspace as Workspace,
  type StoredItem,
} from "../../api/client";
import { useApi } from "../../api/context";
import {
  absoluteTime,
  CHANNELS,
  EmptyState,
  hoverTransition,
  IconTile,
  Page,
  PageSkeleton,
  PersonAvatar,
  Pill,
  relativeTime,
  Rise,
  type Tone,
  typo,
  vt,
} from "../../ui";
import { errorText } from "../Home";

const WIDE = "@media (max-width: 1219px)"; // folders move from a rail to a strip across the top
const NARROW = "@media (max-width: 759px)"; // list and reading pane become separate views

const card = {
  backgroundColor: tokens.colorNeutralBackground1,
  border: `1px solid ${vt.border}`,
  borderRadius: tokens.borderRadiusXLarge,
  boxShadow: vt.shadowCard,
} as const;

const useStyles = makeStyles({
  client: {
    display: "grid",
    gridTemplateColumns: "156px minmax(260px, 300px) minmax(0, 1fr)",
    gridTemplateRows: "clamp(480px, calc(100vh - 230px), 880px)",
    gap: "12px",
    minWidth: 0,
    [WIDE]: {
      gridTemplateColumns: "minmax(260px, 340px) minmax(0, 1fr)",
      gridTemplateRows: "auto clamp(480px, calc(100vh - 290px), 880px)",
      gap: "12px 16px",
    },
    [NARROW]: { gridTemplateColumns: "minmax(0, 1fr)", gridTemplateRows: "auto auto" },
  },
  // Folders: a rail like the app's sidebar; across the top below 1220px.
  rail: {
    display: "grid",
    alignContent: "start",
    gap: "2px",
    minWidth: 0,
    [WIDE]: { gridColumn: "1 / -1", display: "flex", gap: "4px", overflowX: "auto", scrollbarWidth: "none", padding: "1px" },
  },
  railLabel: {
    ...typo.label,
    color: vt.text3,
    padding: "12px 10px 6px",
    ":first-child": { paddingTop: "4px" },
    [WIDE]: { display: "none" },
  },
  folder: {
    ...hoverTransition,
    display: "flex",
    alignItems: "center",
    gap: "10px",
    minHeight: "34px",
    padding: "0 10px",
    border: "1px solid transparent",
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: "transparent",
    color: vt.text2,
    font: "inherit",
    ...typo.body,
    fontWeight: 500,
    textAlign: "left",
    cursor: "pointer",
    whiteSpace: "nowrap",
    "& > svg": { flexShrink: 0, color: vt.text3 },
    "@media (hover: hover)": { ":hover": { backgroundColor: vt.hover, color: vt.text1 } },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "-2px" },
    [WIDE]: { flexShrink: 0 },
  },
  folderSelected: {
    ...card,
    color: vt.text1,
    "& > svg": { color: vt.accent },
    "@media (hover: hover)": { ":hover": { backgroundColor: tokens.colorNeutralBackground1 } },
  },
  folderLabel: { flexGrow: 1 },
  folderCount: { ...typo.label, ...typo.tabular, color: vt.text3, marginLeft: "8px" },
  // The message list and the reading pane are cards that scroll inside themselves.
  listPane: {
    ...card,
    display: "grid",
    gridTemplateRows: "auto minmax(0, 1fr)",
    minHeight: 0,
    minWidth: 0,
    overflow: "hidden",
    [NARROW]: { gridTemplateRows: "auto auto" },
  },
  paneHead: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    minHeight: "48px",
    padding: "10px 16px",
    borderBottom: `1px solid ${vt.borderSubtle}`,
  },
  paneTitle: { ...typo.cardTitle, color: vt.text1, margin: 0 },
  paneMeta: { ...typo.meta, ...typo.tabular, color: vt.text3, marginLeft: "auto" },
  scroll: { overflowY: "auto", minHeight: 0 },
  hideOnNarrow: { [NARROW]: { display: "none" } },
  list: { listStyle: "none", margin: 0, padding: 0, display: "grid" },
  row: {
    ...hoverTransition,
    position: "relative",
    display: "grid",
    gridTemplateColumns: "32px minmax(0, 1fr)",
    columnGap: "12px",
    alignItems: "start",
    width: "100%",
    padding: "12px 16px",
    border: "none",
    borderTop: `1px solid ${vt.borderSubtle}`,
    backgroundColor: "transparent",
    color: "inherit",
    font: "inherit",
    textAlign: "left",
    cursor: "pointer",
    "@media (hover: hover)": { ":hover": { backgroundColor: vt.hover } },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "-2px", borderRadius: "8px" },
  },
  rowFirst: { borderTopColor: "transparent" },
  // As in ListRow: a neutral fill and an accent bar; tertiary text moves up to secondary on it.
  rowSelected: {
    backgroundColor: vt.selected,
    "@media (hover: hover)": { ":hover": { backgroundColor: vt.selected } },
    "::before": {
      content: '""',
      position: "absolute",
      left: 0,
      top: "10px",
      bottom: "10px",
      width: "3px",
      borderRadius: "0 3px 3px 0",
      backgroundColor: vt.accent,
    },
  },
  rowBody: { display: "grid", gap: "1px", minWidth: 0 },
  rowTop: { display: "flex", alignItems: "baseline", gap: "8px", minWidth: 0 },
  rowName: { ...typo.itemTitle, color: vt.text1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flexGrow: 1 },
  rowWhen: { ...typo.label, ...typo.tabular, fontWeight: 400, color: vt.text3, whiteSpace: "nowrap", flexShrink: 0 },
  rowSubject: { ...typo.meta, fontWeight: 500, color: vt.text1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  rowBottom: { display: "flex", alignItems: "center", gap: "8px", minWidth: 0, marginTop: "1px" },
  rowSnippet: {
    ...typo.meta,
    color: vt.text3,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    flexGrow: 1,
    minWidth: 0,
    "& > svg": { verticalAlign: "-3px", marginRight: "4px" },
  },
  onSelected: { color: vt.text2 },
  rowStatus: { flexShrink: 0, marginLeft: "auto" },
  rowEmpty: { padding: "8px 16px" },
  // Focusable only from code (tabIndex -1) when it opens on phones; the pane itself needs no ring.
  readPane: { ...card, overflowY: "auto", minHeight: 0, minWidth: 0, outline: "none" },
  back: { display: "none", margin: "12px 16px 0", [NARROW]: { display: "inline-flex" } },
  article: { display: "grid", minWidth: 0 },
  head: {
    display: "grid",
    gap: "14px",
    padding: "22px 28px 18px",
    borderBottom: `1px solid ${vt.borderSubtle}`,
    [NARROW]: { padding: "16px" },
  },
  subject: { ...typo.sectionTitle, fontSize: "18px", lineHeight: "26px", color: vt.text1, margin: 0, overflowWrap: "anywhere" },
  // Avatar | name and time on one line, the address under it, then To and Cc.
  sender: { display: "grid", gridTemplateColumns: "auto minmax(0, 1fr)", columnGap: "12px", alignItems: "start" },
  senderAvatar: { gridRow: "1 / span 3" },
  senderTop: { display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: "2px 12px", flexWrap: "wrap", minWidth: 0 },
  senderName: { ...typo.itemTitle, color: vt.text1, minWidth: 0 },
  address: { ...typo.meta, ...typo.address, color: vt.text3, minWidth: 0 },
  when: { ...typo.meta, ...typo.tabular, color: vt.text3, whiteSpace: "nowrap" },
  recipients: { ...typo.meta, color: vt.text2, display: "grid", gap: "1px", margin: "4px 0 0", minWidth: 0 },
  recipientRow: { display: "flex", gap: "6px", minWidth: 0 },
  recipientLabel: { color: vt.text3, flexShrink: 0 },
  recipientValue: { ...typo.address, margin: 0, minWidth: 0, overflowWrap: "anywhere" },
  facts: { display: "flex", gap: "6px 16px", flexWrap: "wrap", ...typo.meta, color: vt.text2 },
  fact: { display: "inline-flex", alignItems: "center", gap: "6px", minWidth: 0, "& > svg": { color: vt.text3, flexShrink: 0 } },
  titleRow: { display: "flex", alignItems: "center", gap: "12px", minWidth: 0 },
  body: { padding: "22px 28px 28px", display: "grid", gap: "22px", minWidth: 0, [NARROW]: { padding: "16px" } },
  reading: { ...typo.reading, color: vt.text1, whiteSpace: "pre-wrap", overflowWrap: "anywhere", margin: 0, maxWidth: "72ch" },
  readingQuiet: { color: vt.text2 },
  // What Vanimo did with the item: a well at the end of the message.
  verdict: {
    display: "flex",
    alignItems: "center",
    gap: "10px 12px",
    flexWrap: "wrap",
    padding: "12px 14px",
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: vt.inset,
    border: `1px solid ${vt.borderSubtle}`,
    maxWidth: "72ch",
  },
  verdictText: { ...typo.meta, color: vt.text2, flex: "1 1 220px", minWidth: 0 },
  messages: { listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "14px" },
  message: { display: "grid", gridTemplateColumns: "28px minmax(0, 1fr)", gap: "10px", alignItems: "start", maxWidth: "min(600px, 92%)" },
  mineRow: { justifySelf: "end", gridTemplateColumns: "minmax(0, 1fr)" },
  bubble: {
    display: "grid",
    gap: "4px",
    padding: "10px 14px",
    borderRadius: "12px",
    borderTopLeftRadius: "4px",
    backgroundColor: vt.neutralTint,
    border: "1px solid transparent",
    minWidth: 0,
  },
  mine: { backgroundColor: vt.accentTint, ...shorthands.borderColor("transparent"), borderTopLeftRadius: "12px", borderTopRightRadius: "4px" },
  messageHead: { display: "flex", gap: "8px", alignItems: "baseline", ...typo.label, color: vt.text1 },
  messageWhen: { fontWeight: 400, color: vt.text2, ...typo.tabular },
  messageText: { ...typo.reading, color: vt.text1, whiteSpace: "pre-wrap", overflowWrap: "anywhere", margin: 0 },
  messageStatus: { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap", marginTop: "4px" },
  storedWrap: { padding: "0 28px 28px", [NARROW]: { padding: "0 16px 16px" } },
  stored: { display: "grid", gap: "12px", paddingTop: "20px", borderTop: `1px solid ${vt.borderSubtle}`, minWidth: 0 },
  storedTitle: { ...typo.cardTitle, color: vt.text1, margin: 0, display: "flex", alignItems: "center", gap: "8px", "& > svg": { color: vt.accent } },
  storedLabels: { display: "flex", gap: "4px", flexWrap: "wrap" },
  compare: { display: "grid", gap: "12px", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" },
  pane: { display: "grid", gap: "6px", alignContent: "start", minWidth: 0 },
  paneLabel: { ...typo.label, color: vt.text2 },
  code: {
    ...typo.mono,
    color: vt.text1,
    whiteSpace: "pre-wrap",
    overflowWrap: "anywhere",
    backgroundColor: vt.inset,
    border: `1px solid ${vt.borderSubtle}`,
    borderRadius: tokens.borderRadiusLarge,
    padding: "10px 12px",
    margin: 0,
  },
  storedError: { ...typo.meta, color: vt.danger, margin: 0 },
});

const STATUS: Record<ItemStatus, { label: string; short: string; tone: Tone }> = {
  learned: { label: "Learned (redacted)", short: "Learned", tone: "success" },
  excluded: { label: "Excluded", short: "Excluded", tone: "neutral" },
  not_learned: { label: "Not learned yet", short: "Not learned", tone: "neutral" },
  received: { label: "Received", short: "Received", tone: "neutral" },
};

const REASON: Record<string, string> = {
  person: "a person you excluded",
  domain: "a domain you excluded",
  thread: "a thread you excluded",
  chat: "a chat you excluded",
  meeting: "a meeting you excluded",
  series: "a meeting series you excluded",
  client_account: "a client your organisation excluded",
  not_approved: "an external party your organisation hasn't approved",
};

function because(reasons: string[]): string {
  return reasons.map((r) => REASON[r] ?? r).join(", ");
}

/** An item's status. `short` is the list's version ("Learned"); the reading pane says it in full. */
export function StatusBadge({ status, reasons = [], short }: { status: ItemStatus; reasons?: string[]; short?: boolean }) {
  const s = STATUS[status];
  const why = because(reasons);
  return (
    <Pill tone={s.tone} dot title={why ? `Because of ${why}` : short ? s.label : undefined}>
      {short ? s.short : s.label}
    </Pill>
  );
}

/** The verdict well's icon: learned (a redacted copy), excluded, or neither. */
const VERDICT_ICON: Record<ItemStatus, { icon: ReactElement; tone: Tone }> = {
  learned: { icon: <ShieldCheckmark16Regular />, tone: "success" },
  excluded: { icon: <EyeOff16Regular />, tone: "neutral" },
  not_learned: { icon: <Info16Regular />, tone: "neutral" },
  received: { icon: <Info16Regular />, tone: "neutral" },
};

/** What happened to an item, in one plain sentence. */
function verdict(status: ItemStatus, reasons: string[]): string {
  const why = because(reasons);
  switch (status) {
    case "learned":
      return "Vanimo stores a redacted copy of this message to learn how you write.";
    case "excluded":
      return why ? `Not used at all, because of ${why}.` : "Not used at all.";
    case "not_learned":
      return "Allowed, but not learned from yet.";
    case "received":
      return "Vanimo doesn't learn from mail you receive.";
  }
}

function who(p: SamplePerson | null) {
  return p ? p.name || p.email : "—";
}

/** One line of a message body for the list. */
function snippet(text: string): string {
  return text.replace(/\s+/g, " ").trim().slice(0, 160);
}

/** What Vanimo kept for one item: the stored L1 text next to your re-hydrated view of it. */
export function StoredView({ storedId }: { storedId: string }) {
  const styles = useStyles();
  const api = useApi();
  const [item, setItem] = useState<StoredItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    api.storedItems({ ids: [storedId] }).then(
      (r) => live && setItem(r.items[0] ?? null),
      (e) => live && setError(errorText(e)),
    );
    return () => {
      live = false;
    };
  }, [api, storedId]);
  if (error) return <p className={styles.storedError}>{error}</p>;
  if (!item) return <Spinner size="tiny" labelPosition="after" label="Loading what was stored…" />;
  return (
    <section className={styles.stored} aria-label="What Vanimo stored">
      <h3 className={styles.storedTitle}>
        <Database16Regular aria-hidden />
        What Vanimo stored
      </h3>
      <div className={styles.storedLabels} role="group" aria-label="Labels">
        <Pill>{item.relationship}</Pill>
        <Pill>{item.intent}</Pill>
        <Pill>{item.language}</Pill>
        <Pill>{item.wordCount} words</Pill>
        {item.heldOut && <Pill>Held out for evaluation</Pill>}
      </div>
      <div className={styles.compare}>
        <div className={styles.pane}>
          <span className={styles.paneLabel}>Stored (encrypted at rest)</span>
          <pre className={styles.code}>{item.stored}</pre>
        </div>
        <div className={styles.pane}>
          <span className={styles.paneLabel}>Shown to you</span>
          <pre className={styles.code}>{item.display}</pre>
        </div>
      </div>
      {item.contextStored && (
        <div className={styles.pane}>
          <span className={styles.paneLabel}>The message you replied to, as stored</span>
          <pre className={styles.code}>{item.contextStored}</pre>
        </div>
      )}
    </section>
  );
}

type View = "inbox" | "sent" | "chats" | "meetings";

const FOLDERS: { value: View; label: string; icon: ReactElement; group?: string }[] = [
  { value: "sent", label: "Sent", icon: <Send16Regular />, group: "Outlook" },
  { value: "inbox", label: "Inbox", icon: <MailInbox16Regular /> },
  { value: "chats", label: "Chats", icon: <Chat16Regular />, group: "Teams" },
  { value: "meetings", label: "Meetings", icon: <CalendarLtr16Regular /> },
];

/** A chat as the list draws it: a person's avatar for a 1:1, a purple tile for a group. */
function ChatLeading({ chat, size = 32 }: { chat: SampleChat; size?: 32 | 36 }) {
  if (chat.chatType === "oneOnOne")
    return <PersonAvatar name={chat.label} id={chat.members.find((m) => m.name === chat.label)?.email} size={size} />;
  return <IconTile icon={<ChatMultiple16Regular />} tone={CHANNELS.chat.tone} size={size} />;
}

/** One row in the list pane: who, when, what, a line of the body and what Vanimo did with it. */
function Row({
  id,
  first,
  selected,
  leading,
  name,
  when,
  subject,
  line,
  status,
  onClick,
}: {
  id: string;
  first: boolean;
  selected: boolean;
  leading: ReactNode;
  name: ReactNode;
  when?: string;
  subject?: ReactNode;
  line?: ReactNode;
  status?: ReactNode;
  onClick: () => void;
}) {
  const styles = useStyles();
  return (
    <li>
      <button
        type="button"
        data-row={id}
        className={mergeClasses(styles.row, first && styles.rowFirst, selected && styles.rowSelected)}
        aria-current={selected ? "true" : undefined}
        onClick={onClick}
      >
        {leading}
        <span className={styles.rowBody}>
          <span className={styles.rowTop}>
            <span className={styles.rowName}>{name}</span>
            <span className={mergeClasses(styles.rowWhen, selected && styles.onSelected)} title={when ? absoluteTime(when) : undefined}>
              {when ? relativeTime(when) : ""}
            </span>
          </span>
          {subject && <span className={styles.rowSubject}>{subject}</span>}
          {(line || status) && (
            <span className={styles.rowBottom}>
              <span className={mergeClasses(styles.rowSnippet, selected && styles.onSelected)}>{line}</span>
              {status && <span className={styles.rowStatus}>{status}</span>}
            </span>
          )}
        </span>
      </button>
    </li>
  );
}

/** The item's verdict: an icon, its status pill, one sentence and (when there is one) the stored copy. */
function Verdict({
  status,
  reasons,
  text,
  badge = true,
  children,
}: {
  status: ItemStatus;
  reasons: string[];
  text?: string;
  /** Show the status pill (meetings that aren't excluded have none). */
  badge?: boolean;
  children?: ReactNode;
}) {
  const styles = useStyles();
  const v = VERDICT_ICON[status];
  return (
    <div className={styles.verdict}>
      <IconTile icon={v.icon} tone={v.tone} size={28} />
      {badge && <StatusBadge status={status} reasons={reasons} />}
      <span className={styles.verdictText}>{text ?? verdict(status, reasons)}</span>
      {children}
    </div>
  );
}

/** The sample workspace as Outlook and Teams would show it, with what Vanimo did with each item. */
export function SampleWorkspace() {
  const styles = useStyles();
  const api = useApi();
  const [ws, setWs] = useState<Workspace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("sent");
  const [selected, setSelected] = useState<string | null>(null);
  const [showStored, setShowStored] = useState<string | null>(null);
  const readRef = useRef<HTMLDivElement>(null);
  const storedRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const returnTo = useRef<string | null>(null);

  // On phones the list and the reading pane are separate views: move focus with the view, so it
  // never drops to the page when the focused row (or the Back button) disappears.
  useEffect(() => {
    if (window.matchMedia?.("(max-width: 759px)").matches !== true) return;
    if (selected) readRef.current?.focus();
    else if (returnTo.current) listRef.current?.querySelector<HTMLElement>(`[data-row="${returnTo.current}"]`)?.focus();
  }, [selected]);

  useEffect(() => {
    let live = true;
    api.sampleWorkspace().then(
      (w) => live && setWs(w),
      (e) =>
        live &&
        setError(
          e instanceof ApiError && e.code === "sample_workspace_only"
            ? "You're connected to Microsoft 365, so there's no sample workspace to show."
            : errorText(e),
        ),
    );
    return () => {
      live = false;
    };
  }, [api]);

  const emails = useMemo(
    () => (ws ? ws.emails.filter((e) => (view === "sent" ? e.direction === "sent" : e.direction === "received")) : []),
    [ws, view],
  );

  // A new item opens at its top; the stored copy scrolls into view when asked for.
  useEffect(() => {
    if (readRef.current) readRef.current.scrollTop = 0;
  }, [selected]);
  useEffect(() => {
    if (showStored) storedRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [showStored]);

  if (error)
    return (
      <Page title="Sample workspace">
        <MessageBar intent="info">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      </Page>
    );
  if (!ws) return <PageSkeleton label="Opening the sample workspace…" />;

  const counts = {
    learned: ws.emails.filter((e) => e.status === "learned").length +
      ws.chats.flatMap((c) => c.messages).filter((m) => m.status === "learned").length,
  };
  const email = ws.emails.find((e) => e.id === selected);
  const chat = ws.chats.find((c) => c.id === selected);
  const meeting = ws.meetings.find((m) => m.id === selected);
  const select = (id: string) => {
    setSelected(id);
    setShowStored(null);
  };
  const sentCount = ws.emails.filter((e) => e.direction === "sent").length;
  const folderCount: Record<View, number> = {
    sent: sentCount,
    inbox: ws.emails.length - sentCount,
    chats: ws.chats.length,
    meetings: ws.meetings.length,
  };
  const listed = folderCount[view];
  const learnedHere =
    view === "chats"
      ? ws.chats.flatMap((c) => c.messages).filter((m) => m.status === "learned").length
      : view === "meetings"
        ? 0
        : emails.filter((e) => e.status === "learned").length;
  const folder = FOLDERS.find((f) => f.value === view)!;

  return (
    <Page
      title="Sample workspace"
      width="wide"
      description={`Synthetic data: ${counts.learned} of your messages are learned so far.`}
      info={ws.note}
    >
      <div className={styles.client}>
        <nav className={styles.rail} aria-label="Folders">
          {FOLDERS.flatMap((f) => [
            ...(f.group ? [<span key={`${f.value}-group`} className={styles.railLabel}>{f.group}</span>] : []),
            <button
              key={f.value}
              type="button"
              className={mergeClasses(styles.folder, view === f.value && styles.folderSelected)}
              aria-current={view === f.value ? "true" : undefined}
              onClick={() => {
                setView(f.value);
                setSelected(null);
                setShowStored(null);
              }}
            >
              {f.icon}
              <span className={styles.folderLabel}>{f.label}</span>
              <span className={styles.folderCount}>{folderCount[f.value]}</span>
            </button>,
          ])}
        </nav>

        <section className={mergeClasses(styles.listPane, selected !== null && styles.hideOnNarrow)} aria-label={folder.label}>
          <div className={styles.paneHead}>
            <h2 className={styles.paneTitle}>{folder.label}</h2>
            <Pill>{listed}</Pill>
            {learnedHere > 0 && <span className={styles.paneMeta}>{learnedHere} learned</span>}
          </div>
          <div className={styles.scroll}>
            <ul className={styles.list} aria-label={view} ref={listRef}>
              {(view === "inbox" || view === "sent") &&
                emails.map((e, i) => {
                  const person = view === "sent" ? e.to[0] ?? null : e.sender;
                  return (
                    <Row
                      key={e.id}
                      id={e.id}
                      first={i === 0}
                      selected={selected === e.id}
                      onClick={() => select(e.id)}
                      leading={<PersonAvatar name={person?.name} id={person?.email} size={32} />}
                      name={view === "sent" ? `To ${e.to.map(who).join(", ")}` : who(e.sender)}
                      when={e.sentAt}
                      subject={e.subject || "(no subject)"}
                      line={snippet(e.body)}
                      status={e.status !== "received" && <StatusBadge status={e.status} reasons={e.reasons} short />}
                    />
                  );
                })}
              {view === "chats" &&
                ws.chats.map((c, i) => {
                  const last = c.messages.at(-1);
                  return (
                    <Row
                      key={c.id}
                      id={c.id}
                      first={i === 0}
                      selected={selected === c.id}
                      onClick={() => select(c.id)}
                      leading={<ChatLeading chat={c} />}
                      name={c.label}
                      when={last?.createdAt}
                      line={
                        last ? (
                          `${last.fromMe ? "You" : who(last.sender)}: ${snippet(last.text)}`
                        ) : (
                          <>
                            <People16Regular aria-hidden />
                            {c.members.length} people
                          </>
                        )
                      }
                      status={c.excluded && <StatusBadge status="excluded" reasons={c.reasons} short />}
                    />
                  );
                })}
              {view === "meetings" &&
                ws.meetings.map((m, i) => (
                  <Row
                    key={m.id}
                    id={m.id}
                    first={i === 0}
                    selected={selected === m.id}
                    onClick={() => setSelected(m.id)}
                    leading={<IconTile icon={CHANNELS.meeting.icon} tone={CHANNELS.meeting.tone} size={32} />}
                    name={m.subject || "(no subject)"}
                    when={m.start}
                    line={
                      m.organizer ? (
                        <>
                          <Person16Regular aria-hidden />
                          Organised by {who(m.organizer)}
                        </>
                      ) : (
                        <>
                          <People16Regular aria-hidden />
                          {m.attendees.length} attendees
                        </>
                      )
                    }
                    status={m.excluded && <StatusBadge status="excluded" reasons={m.reasons} short />}
                  />
                ))}
              {listed === 0 && (
                <li className={styles.rowEmpty}>
                  <EmptyState icon={<MailRead20Regular />} title="Nothing here" headingLevel={3} center />
                </li>
              )}
            </ul>
          </div>
        </section>

        <div
          ref={readRef}
          tabIndex={-1}
          aria-label="Reading pane"
          className={mergeClasses(styles.readPane, selected === null && styles.hideOnNarrow)}
        >
          <Button
            className={styles.back}
            appearance="subtle"
            size="small"
            icon={<ArrowLeft16Regular />}
            onClick={() => {
              returnTo.current = selected;
              setSelected(null);
              setShowStored(null);
            }}
          >
            Back to the list
          </Button>
          {!selected && (
            <EmptyState headingLevel={2} icon={<MailRead20Regular />} title="Select an item to read it" center>
              Each item says what Vanimo did with it: learned from a redacted copy, excluded, or not used.
            </EmptyState>
          )}
          {email && (
            <article className={styles.article}>
              <header className={styles.head}>
                <h2 className={styles.subject}>{email.subject || "(no subject)"}</h2>
                <div className={styles.sender}>
                  <span className={styles.senderAvatar}>
                    <PersonAvatar name={email.sender.name} id={email.sender.email} size={36} />
                  </span>
                  <span className={styles.senderTop}>
                    <span className={styles.senderName}>{who(email.sender)}</span>
                    <span className={styles.when}>{absoluteTime(email.sentAt)}</span>
                  </span>
                  {email.sender.name && <span className={styles.address}>{email.sender.email}</span>}
                  <dl className={styles.recipients}>
                    <div className={styles.recipientRow}>
                      <dt className={styles.recipientLabel}>To</dt>
                      <dd className={styles.recipientValue}>{email.to.map(who).join(", ")}</dd>
                    </div>
                    {email.cc.length > 0 && (
                      <div className={styles.recipientRow}>
                        <dt className={styles.recipientLabel}>Cc</dt>
                        <dd className={styles.recipientValue}>{email.cc.map(who).join(", ")}</dd>
                      </div>
                    )}
                  </dl>
                </div>
              </header>
              <div className={styles.body}>
                <div className={styles.reading}>{email.body}</div>
                <Verdict status={email.status} reasons={email.reasons}>
                  {email.storedId && (
                    <Button size="small" icon={<Database16Regular />} onClick={() => setShowStored(email.storedId)}>
                      See what Vanimo stored
                    </Button>
                  )}
                </Verdict>
              </div>
            </article>
          )}
          {chat && (
            <article className={styles.article}>
              <header className={styles.head}>
                <div className={styles.titleRow}>
                  <ChatLeading chat={chat} size={36} />
                  <h2 className={styles.subject}>{chat.label}</h2>
                </div>
                <div className={styles.facts}>
                  <span className={styles.fact}>
                    <People16Regular aria-hidden />
                    <span className={styles.recipientValue}>{chat.members.map(who).join(", ")}</span>
                  </span>
                </div>
                {chat.excluded && <Verdict status="excluded" reasons={chat.reasons} />}
              </header>
              <div className={styles.body}>
                <ol className={styles.messages} aria-label="Messages">
                  {chat.messages.map((m) => (
                    <li key={m.id} className={mergeClasses(styles.message, m.fromMe && styles.mineRow)}>
                      {!m.fromMe && <PersonAvatar name={m.sender.name} id={m.sender.email} size={28} />}
                      <div className={mergeClasses(styles.bubble, m.fromMe && styles.mine)}>
                        <span className={styles.messageHead}>
                          {m.fromMe ? "You" : who(m.sender)}
                          <span className={styles.messageWhen} title={absoluteTime(m.createdAt)}>
                            {relativeTime(m.createdAt)}
                          </span>
                        </span>
                        <p className={styles.messageText}>{m.text}</p>
                        {m.fromMe && (
                          <div className={styles.messageStatus}>
                            <StatusBadge status={m.status} reasons={chat.reasons} />
                            {m.storedId && (
                              <Button
                                size="small"
                                appearance="subtle"
                                icon={<Database16Regular />}
                                onClick={() => setShowStored(m.storedId)}
                              >
                                See what was stored
                              </Button>
                            )}
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            </article>
          )}
          {meeting && (
            <article className={styles.article}>
              <header className={styles.head}>
                <div className={styles.titleRow}>
                  <IconTile icon={CHANNELS.meeting.icon20} tone={CHANNELS.meeting.tone} size={36} />
                  <h2 className={styles.subject}>{meeting.subject || "(no subject)"}</h2>
                </div>
                <div className={styles.facts}>
                  <span className={styles.fact}>
                    <Clock16Regular aria-hidden />
                    {absoluteTime(meeting.start)}
                  </span>
                  {meeting.organizer && (
                    <span className={styles.fact}>
                      <Person16Regular aria-hidden />
                      Organised by {who(meeting.organizer)}
                    </span>
                  )}
                  <span className={styles.fact}>
                    <People16Regular aria-hidden />
                    <span className={styles.recipientValue}>{meeting.attendees.map(who).join(", ")}</span>
                  </span>
                </div>
              </header>
              <div className={styles.body}>
                <div className={mergeClasses(styles.reading, !meeting.agenda && styles.readingQuiet)}>
                  {meeting.agenda || "No agenda."}
                </div>
                <Verdict
                  status={meeting.excluded ? "excluded" : "not_learned"}
                  badge={meeting.excluded}
                  reasons={meeting.reasons}
                  text={`${meeting.excluded ? `${verdict("excluded", meeting.reasons)} ` : ""}Meetings aren't learned from yet (meeting memory comes in a later milestone).`}
                />
              </div>
            </article>
          )}
          {showStored && (
            <div ref={storedRef} className={styles.storedWrap}>
              <Rise visible appear>
                <div>
                  <StoredView storedId={showStored} />
                </div>
              </Rise>
            </div>
          )}
        </div>
      </div>
    </Page>
  );
}
