/** The sample workspace as a mail client: a folder switcher, a list pane of two-line rows and a
 * reading pane, with what Vanimo did with each item stated plainly. On phones the list and the
 * reading pane are separate views. */
import { Button, makeStyles, mergeClasses, MessageBar, MessageBarBody, Spinner, tokens } from "@fluentui/react-components";
import { ArrowLeft16Regular, MailRead20Regular } from "@fluentui/react-icons";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ApiError, type ItemStatus, type SamplePerson, type SampleWorkspace as Workspace, type StoredItem } from "../../api/client";
import { useApi } from "../../api/context";
import {
  absoluteTime,
  EmptyState,
  hoverTransition,
  Page,
  PageSkeleton,
  Pill,
  relativeTime,
  Rise,
  Segmented,
  type Tone,
  typo,
  vt,
} from "../../ui";
import { errorText } from "../Home";

const NARROW = "@media (max-width: 759px)";

const useStyles = makeStyles({
  frame: {
    display: "grid",
    gridTemplateColumns: "minmax(260px, 340px) minmax(0, 1fr)",
    gridTemplateRows: "minmax(0, 1fr)",
    height: "clamp(480px, calc(100vh - 260px), 880px)",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusXLarge,
    backgroundColor: tokens.colorNeutralBackground1,
    overflow: "hidden",
    minWidth: 0,
    [NARROW]: { gridTemplateColumns: "minmax(0, 1fr)", gridTemplateRows: "auto", height: "auto" },
  },
  listPane: {
    overflowY: "auto",
    minHeight: 0,
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
    [NARROW]: { borderRight: "none" },
  },
  hideOnNarrow: { [NARROW]: { display: "none" } },
  list: { listStyle: "none", margin: 0, padding: 0, display: "grid" },
  row: {
    ...hoverTransition,
    position: "relative",
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr) auto",
    alignItems: "center",
    columnGap: "12px",
    rowGap: "2px",
    width: "100%",
    padding: "10px 16px",
    border: "none",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
    backgroundColor: "transparent",
    color: "inherit",
    font: "inherit",
    textAlign: "left",
    cursor: "pointer",
    "@media (hover: hover)": { ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover } },
    ":focus-visible": { outline: `2px solid ${tokens.colorStrokeFocus2}`, outlineOffset: "-2px" },
    "@media (pointer: coarse)": { minHeight: "56px" },
  },
  rowFirst: { borderTopColor: "transparent" },
  rowSelected: {
    backgroundColor: tokens.colorNeutralBackground1Selected,
    "@media (hover: hover)": { ":hover": { backgroundColor: tokens.colorNeutralBackground1Selected } },
    "::before": {
      content: '""',
      position: "absolute",
      left: 0,
      top: "8px",
      bottom: "8px",
      width: "2px",
      borderRadius: "2px",
      backgroundColor: vt.accent,
    },
  },
  rowTitle: { ...typo.itemTitle, color: vt.text1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  rowWhen: { ...typo.label, ...typo.tabular, fontWeight: 400, color: vt.text2, whiteSpace: "nowrap" },
  rowLine: { ...typo.meta, color: vt.text2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  rowEmpty: { ...typo.meta, color: vt.text2, padding: "16px" },
  // Focusable only from code (tabIndex -1) when it opens on phones; the pane itself needs no ring.
  readPane: { overflowY: "auto", minHeight: 0, padding: "24px 28px 32px", outline: "none", [NARROW]: { padding: "16px" } },
  back: { display: "none", marginBottom: "12px", [NARROW]: { display: "inline-flex" } },
  article: { display: "grid", gap: "20px", maxWidth: "720px", minWidth: 0 },
  head: { display: "grid", gap: "8px", paddingBottom: "16px", borderBottom: `1px solid ${tokens.colorNeutralStroke3}` },
  subject: { ...typo.sectionTitle, fontSize: "18px", lineHeight: "26px", color: vt.text1, margin: 0, overflowWrap: "anywhere" },
  people: { display: "grid", gap: "2px", ...typo.meta, color: vt.text1, margin: 0 },
  peopleRow: { display: "grid", gridTemplateColumns: "40px minmax(0, 1fr)", gap: "8px" },
  peopleLabel: { color: vt.text3 },
  peopleValue: { ...typo.address, minWidth: 0, margin: 0 },
  when: { ...typo.meta, ...typo.tabular, color: vt.text3 },
  reading: { ...typo.reading, color: vt.text1, whiteSpace: "pre-wrap", overflowWrap: "anywhere", margin: 0 },
  readingQuiet: { color: vt.text2 },
  verdict: {
    display: "flex",
    alignItems: "center",
    gap: "8px 12px",
    flexWrap: "wrap",
    paddingTop: "16px",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  verdictInline: { paddingTop: 0, borderTopColor: "transparent" },
  verdictText: { ...typo.meta, color: vt.text2, flex: "1 1 240px", minWidth: 0 },
  messages: { listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "12px" },
  message: {
    display: "grid",
    gap: "4px",
    maxWidth: "min(560px, 88%)",
    padding: "10px 14px",
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: vt.inset,
    justifySelf: "start",
  },
  mine: { justifySelf: "end", backgroundColor: vt.selected },
  messageHead: { display: "flex", gap: "8px", alignItems: "baseline", ...typo.label, color: vt.text2 },
  messageWhen: { fontWeight: 400, color: vt.text2, ...typo.tabular },
  messageText: { ...typo.reading, color: vt.text1, whiteSpace: "pre-wrap", overflowWrap: "anywhere", margin: 0 },
  messageStatus: { display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap", marginTop: "4px" },
  note: { ...typo.meta, color: vt.text2, margin: 0 },
  storedWrap: { marginTop: "20px" },
  stored: { display: "grid", gap: "12px", paddingTop: "20px", borderTop: `1px solid ${tokens.colorNeutralStroke3}`, minWidth: 0 },
  storedTitle: { ...typo.itemTitle, color: vt.text1, margin: 0 },
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
    border: `1px solid ${tokens.colorNeutralStroke3}`,
    borderRadius: tokens.borderRadiusLarge,
    padding: "10px 12px",
    margin: 0,
  },
  storedError: { ...typo.meta, color: vt.danger, margin: 0 },
});

const STATUS: Record<ItemStatus, { label: string; tone: Tone }> = {
  learned: { label: "Learned (redacted)", tone: "success" },
  excluded: { label: "Excluded", tone: "neutral" },
  not_learned: { label: "Not learned yet", tone: "neutral" },
  received: { label: "Received", tone: "neutral" },
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

export function StatusBadge({ status, reasons = [] }: { status: ItemStatus; reasons?: string[] }) {
  const s = STATUS[status];
  const why = because(reasons);
  return (
    <span title={why ? `Because of ${why}` : undefined} style={{ display: "inline-flex" }}>
      <Pill tone={s.tone}>{s.label}</Pill>
    </span>
  );
}

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
      <h3 className={styles.storedTitle}>What Vanimo stored</h3>
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

/** One two-line row in the list pane. */
function Row({
  id,
  first,
  selected,
  title,
  when,
  line,
  status,
  onClick,
}: {
  id: string;
  first: boolean;
  selected: boolean;
  title: ReactNode;
  when?: string;
  line: ReactNode;
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
        <span className={styles.rowTitle}>{title}</span>
        <span className={styles.rowWhen} title={when ? absoluteTime(when) : undefined}>
          {when ? relativeTime(when) : ""}
        </span>
        <span className={styles.rowLine}>{line}</span>
        <span>{status}</span>
      </button>
    </li>
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
  const listed = view === "chats" ? ws.chats.length : view === "meetings" ? ws.meetings.length : emails.length;

  return (
    <Page
      title="Sample workspace"
      width="wide"
      eyebrow={<Pill>Synthetic data</Pill>}
      description={`${ws.note} ${counts.learned} of your messages are learned so far.`}
    >
      <Segmented<View>
        label="Folder"
        value={view}
        onChange={(v) => {
          setView(v);
          setSelected(null);
          setShowStored(null);
        }}
        segments={[
          { value: "sent", label: "Sent", count: sentCount },
          { value: "inbox", label: "Inbox", count: ws.emails.length - sentCount },
          { value: "chats", label: "Chats", count: ws.chats.length },
          { value: "meetings", label: "Meetings", count: ws.meetings.length },
        ]}
      />
      <div className={styles.frame}>
        <div className={mergeClasses(styles.listPane, selected !== null && styles.hideOnNarrow)}>
          <ul className={styles.list} aria-label={view} ref={listRef}>
            {(view === "inbox" || view === "sent") &&
              emails.map((e, i) => (
                <Row
                  key={e.id}
                  id={e.id}
                  first={i === 0}
                  selected={selected === e.id}
                  onClick={() => select(e.id)}
                  title={view === "sent" ? `To ${e.to.map(who).join(", ")}` : who(e.sender)}
                  when={e.sentAt}
                  line={e.subject || "(no subject)"}
                  status={e.status !== "received" && <StatusBadge status={e.status} reasons={e.reasons} />}
                />
              ))}
            {view === "chats" &&
              ws.chats.map((c, i) => (
                <Row
                  key={c.id}
                  id={c.id}
                  first={i === 0}
                  selected={selected === c.id}
                  onClick={() => select(c.id)}
                  title={c.label}
                  when={c.messages.at(-1)?.createdAt}
                  line={`${c.members.length} people`}
                  status={c.excluded && <StatusBadge status="excluded" reasons={c.reasons} />}
                />
              ))}
            {view === "meetings" &&
              ws.meetings.map((m, i) => (
                <Row
                  key={m.id}
                  id={m.id}
                  first={i === 0}
                  selected={selected === m.id}
                  onClick={() => setSelected(m.id)}
                  title={m.subject || "(no subject)"}
                  when={m.start}
                  line={m.organizer ? `Organised by ${who(m.organizer)}` : `${m.attendees.length} attendees`}
                  status={m.excluded && <StatusBadge status="excluded" reasons={m.reasons} />}
                />
              ))}
            {listed === 0 && <li className={styles.rowEmpty}>Nothing here.</li>}
          </ul>
        </div>

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
            <EmptyState headingLevel={2} icon={<MailRead20Regular />} title="Select an item to read it">
              Each item says what Vanimo did with it: learned from a redacted copy, excluded, or not used.
            </EmptyState>
          )}
          {email && (
            <article className={styles.article}>
              <header className={styles.head}>
                <h2 className={styles.subject}>{email.subject || "(no subject)"}</h2>
                <dl className={styles.people}>
                  <div className={styles.peopleRow}>
                    <dt className={styles.peopleLabel}>From</dt>
                    <dd className={styles.peopleValue}>{who(email.sender)}</dd>
                  </div>
                  <div className={styles.peopleRow}>
                    <dt className={styles.peopleLabel}>To</dt>
                    <dd className={styles.peopleValue}>{email.to.map(who).join(", ")}</dd>
                  </div>
                  {email.cc.length > 0 && (
                    <div className={styles.peopleRow}>
                      <dt className={styles.peopleLabel}>Cc</dt>
                      <dd className={styles.peopleValue}>{email.cc.map(who).join(", ")}</dd>
                    </div>
                  )}
                </dl>
                <span className={styles.when}>{absoluteTime(email.sentAt)}</span>
              </header>
              <div className={styles.reading}>{email.body}</div>
              <div className={styles.verdict}>
                <StatusBadge status={email.status} reasons={email.reasons} />
                <span className={styles.verdictText}>{verdict(email.status, email.reasons)}</span>
                {email.storedId && (
                  <Button size="small" onClick={() => setShowStored(email.storedId)}>
                    See what Vanimo stored
                  </Button>
                )}
              </div>
            </article>
          )}
          {chat && (
            <article className={styles.article}>
              <header className={styles.head}>
                <h2 className={styles.subject}>{chat.label}</h2>
                <p className={mergeClasses(styles.people, styles.peopleValue)}>{chat.members.map(who).join(", ")}</p>
                {chat.excluded && (
                  <div className={mergeClasses(styles.verdict, styles.verdictInline)}>
                    <StatusBadge status="excluded" reasons={chat.reasons} />
                    <span className={styles.verdictText}>{verdict("excluded", chat.reasons)}</span>
                  </div>
                )}
              </header>
              <ol className={styles.messages} aria-label="Messages">
                {chat.messages.map((m) => (
                  <li key={m.id} className={mergeClasses(styles.message, m.fromMe && styles.mine)}>
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
                          <Button size="small" appearance="subtle" onClick={() => setShowStored(m.storedId)}>
                            See what was stored
                          </Button>
                        )}
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            </article>
          )}
          {meeting && (
            <article className={styles.article}>
              <header className={styles.head}>
                <h2 className={styles.subject}>{meeting.subject || "(no subject)"}</h2>
                <span className={styles.when}>
                  {absoluteTime(meeting.start)}
                  {meeting.organizer && ` · organised by ${who(meeting.organizer)}`}
                </span>
                <p className={mergeClasses(styles.people, styles.peopleValue)}>{meeting.attendees.map(who).join(", ")}</p>
              </header>
              <div className={mergeClasses(styles.reading, !meeting.agenda && styles.readingQuiet)}>
                {meeting.agenda || "No agenda."}
              </div>
              <div className={styles.verdict}>
                {meeting.excluded && <StatusBadge status="excluded" reasons={meeting.reasons} />}
                <span className={styles.verdictText}>
                  {meeting.excluded && `${verdict("excluded", meeting.reasons)} `}
                  Meetings aren't learned from yet (meeting memory comes in a later milestone).
                </span>
              </div>
            </article>
          )}
          {showStored && (
            <div ref={storedRef} className={styles.storedWrap}>
              <Rise visible appear>
                <div className={styles.article}>
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
