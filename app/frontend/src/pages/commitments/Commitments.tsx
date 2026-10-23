/** Commitments (M5): the promises you made in your sent email and Teams chats (and, M6, in Teams
 * meetings), with follow-ups drafted in your voice. Shown in the web app and as the Vanimo tab in Teams.
 * Vanimo never sends: you copy or open the follow-up and send it yourself. A promise made in a meeting
 * has no conversation to follow up in.
 * Layout: a segmented filter (Open · Done · Not promises), a ledger grouped by when things are due,
 * hairline rows with the due date and row actions on the right, and the follow-up drafted in place.
 * No router hooks: the Teams tab renders this without a router. */
import {
  Button,
  Field,
  Input,
  makeStyles,
  mergeClasses,
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
  MessageBar,
  MessageBarBody,
  Tab,
  TabList,
  tokens,
  Tooltip,
} from "@fluentui/react-components";
import {
  ArrowUndo16Regular,
  CalendarLtr16Regular,
  Chat16Regular,
  Checkmark16Regular,
  Dismiss16Regular,
  Mail16Regular,
  Snooze16Regular,
  TaskListSquareLtr20Regular,
} from "@fluentui/react-icons";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import type { Commitment, Draft, DraftCheck, FollowUpKind, Ledger } from "../../api/client";
import { useApi } from "../../api/context";
import { DraftView, draftErrorText, hasBlock, recheck } from "../../drafting/DraftView";
import {
  absoluteTime,
  EmptyState,
  Page,
  PageSkeleton,
  Pill,
  relativeTime,
  Rise,
  StatusDot,
  typo,
  vt,
} from "../../ui";
import { newChatLink } from "../TeamsPrefill";

const useStyles = makeStyles({
  embedded: { display: "grid", gap: "24px", minWidth: 0 },
  toolbar: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px 16px", flexWrap: "wrap" },
  segmented: { flexWrap: "wrap" },
  tabCount: { ...typo.tabular, color: vt.text3, marginLeft: "2px", fontWeight: 400 },
  groups: { display: "grid", gap: "28px", minWidth: 0 },
  group: { display: "grid", gap: "8px", minWidth: 0 },
  groupTitle: { ...typo.itemTitle, color: vt.text1, margin: 0, display: "flex", alignItems: "baseline", gap: "8px" },
  groupCount: { ...typo.meta, ...typo.tabular, color: vt.text3, fontWeight: 400 },
  list: {
    display: "grid",
    margin: 0,
    padding: 0,
    listStyle: "none",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusXLarge,
    backgroundColor: tokens.colorNeutralBackground1,
    overflow: "hidden",
  },
  row: {
    display: "grid",
    gridTemplateColumns: "16px minmax(0, 1fr) auto",
    columnGap: "12px",
    rowGap: "8px",
    padding: "14px 16px",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
    ":first-child": { borderTop: "none" },
    "@media (max-width: 639px)": { gridTemplateColumns: "16px minmax(0, 1fr)" },
  },
  icon: { color: vt.text3, height: "20px", display: "grid", placeItems: "center" },
  main: { display: "grid", gap: "4px", minWidth: 0 },
  titleLine: { display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", minWidth: 0 },
  what: { ...typo.itemTitle, color: vt.text1, overflowWrap: "anywhere" },
  quote: { ...typo.meta, color: vt.text1, margin: 0, overflowWrap: "anywhere" },
  meta: { ...typo.meta, ...typo.tabular, color: vt.text2, overflowWrap: "anywhere" },
  side: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: "10px",
    "@media (max-width: 639px)": {
      gridColumn: "2 / -1",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      flexWrap: "wrap",
    },
  },
  due: { ...typo.meta, ...typo.tabular, color: vt.text2, whiteSpace: "nowrap" },
  dueSoon: { color: vt.text1, fontWeight: 500 },
  actions: { display: "flex", alignItems: "center", gap: "4px", flexWrap: "wrap", justifyContent: "flex-end" },
  extra: {
    gridColumn: "2 / -1",
    display: "grid",
    gap: "12px",
    minWidth: 0,
    padding: "16px",
    borderRadius: tokens.borderRadiusLarge,
    backgroundColor: tokens.colorNeutralBackground2,
    border: `1px solid ${tokens.colorNeutralStroke3}`,
    "@media (max-width: 639px)": { gridColumn: "1 / -1" },
  },
  // The draft card has its own border: no box around it (never a card inside a card).
  extraPlain: { gridColumn: "2 / -1", display: "grid", gap: "8px", minWidth: 0, "@media (max-width: 639px)": { gridColumn: "1 / -1" } },
  extraTitle: { ...typo.itemTitle, color: vt.text1, margin: 0 },
  form: { display: "flex", alignItems: "flex-end", gap: "8px", flexWrap: "wrap" },
  field: { flex: "1 1 220px", maxWidth: "320px" },
  footer: {
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "4px 12px",
    ...typo.meta,
    ...typo.tabular,
    color: vt.text2,
    margin: 0,
    paddingTop: "12px",
    borderTop: `1px solid ${tokens.colorNeutralStroke3}`,
  },
});

export const AUDIENCE: Record<string, string> = {
  manager: "your manager",
  report: "your team",
  peer: "colleagues",
  external: "a client or partner",
  personal: "a personal contact",
};

const CHANNEL: Record<Commitment["channel"], string> = { email: "Email", chat: "Teams", meeting: "Meeting" };

const FOLLOW_UP: Record<FollowUpKind, string> = {
  done: "It's done: send it",
  late: "Running late: ask for more time",
  update: "Still on it: send an update",
};

function day(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

/** Which group a promise is in now. */
export function bucket(c: Commitment, now = new Date()): "overdue" | "soon" | "later" | "undated" {
  if (!c.dueAt) return "undated";
  const due = new Date(c.dueAt).getTime();
  if (due < now.getTime()) return "overdue";
  return due < now.getTime() + 86_400_000 ? "soon" : "later";
}

const GROUPS = [
  ["overdue", "Overdue"],
  ["soon", "Due in the next day"],
  ["later", "Later"],
  ["undated", "No date given"],
] as const;

/** relativeTime, readable mid-sentence ("due tomorrow", not "due Tomorrow"). */
function rel(iso: string): string {
  const r = relativeTime(iso);
  return r === "Tomorrow" || r === "Yesterday" ? r.toLowerCase() : r;
}

/** A relative date in a phrase, with the exact date and time on hover. */
function When({ iso, children, className }: { iso: string; children: ReactNode; className?: string }) {
  return (
    <Tooltip content={absoluteTime(iso)} relationship="description" withArrow>
      <time dateTime={iso} className={className}>
        {children}
      </time>
    </Tooltip>
  );
}

export function Commitments({ embedded = false, prefill = false }: { embedded?: boolean; prefill?: boolean }) {
  const styles = useStyles();
  const api = useApi();
  const [status, setStatus] = useState<"open" | "done" | "dismissed">("open");
  const [ledger, setLedger] = useState<Ledger | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scanNote, setScanNote] = useState<string | null>(null);
  const [active, setActive] = useState<{ id: string; kind: FollowUpKind } | null>(null);
  const [newDate, setNewDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<{ id: string; draft: Draft } | null>(null);
  const [text, setText] = useState("");
  const [checks, setChecks] = useState<DraftCheck[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  // Which commitment the notice is about (null: the page as a whole).
  const [noticeFor, setNoticeFor] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLedger(await api.commitments(status));
    } catch (e) {
      setError(draftErrorText(e));
    }
  }, [api, status]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    // Look for new promises in what you sent since the last look (at most once a minute).
    api.scanCommitments().then(
      (r) => {
        if (r.found || r.hints) {
          setScanNote(
            [r.found ? `${r.found} new promise${r.found > 1 ? "s" : ""} found` : "", r.hints ? `${r.hints} look done` : ""]
              .filter(Boolean)
              .join(" · "),
          );
          void refresh();
        }
      },
      () => undefined, // e.g. the review isn't done yet: the list explains itself
    );
  }, [api, refresh]);

  async function decide(c: Commitment, action: "done" | "dismiss" | "reopen" | "snooze") {
    try {
      await api.decideCommitment(c.id, action);
      await refresh();
    } catch (e) {
      setError(draftErrorText(e));
    }
  }

  async function followUp(c: Commitment, kind: FollowUpKind) {
    setBusy(true);
    setNotice(null);
    try {
      const d = await api.followUp(c.id, kind, newDate.trim() || null);
      setDraft({ id: c.id, draft: d });
      setText(d.text);
      setChecks(d.checks);
      setConfirmed(false);
      setActive(null);
    } catch (e) {
      setNoticeFor(c.id);
      setNotice(draftErrorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function copy(d: Draft) {
    setNoticeFor(draft?.id ?? null);
    try {
      await navigator.clipboard.writeText(text);
      setNotice(d.channel === "chat" ? "Copied. Paste it into the Teams chat." : "Copied. Paste it into your reply.");
      if (d.id) await api.draftFeedback(d.id, { outcome: "copied" });
    } catch {
      setNotice("Couldn't copy automatically: select the text and copy it.");
    }
  }

  async function checkAgain(d: Draft) {
    setNoticeFor(draft?.id ?? null);
    try {
      // The follow-up's conversation is the promise's: the API knows it, the page doesn't (no ID here).
      const res = await api.checkText(text, d.audience.to, d.audience.cc, null, d.channel === "chat" ? "chat" : "email");
      const merged = recheck(d.checks, res.checks);
      setChecks(merged);
      setNotice(merged.length ? null : "No problems found in your text.");
    } catch (e) {
      setNotice(draftErrorText(e));
    }
  }

  async function place(d: Draft) {
    if (!d.id) return;
    setNoticeFor(draft?.id ?? null);
    try {
      const res = await api.placeDraft(d.id, text, confirmed);
      setNotice(res.webLink ? "In your Outlook Drafts folder." : "In your Drafts folder (simulated in the sample workspace).");
    } catch (e) {
      setNotice(draftErrorText(e));
    }
  }

  const frame = (children: ReactNode) =>
    embedded ? (
      <div className={styles.embedded}>{children}</div>
    ) : (
      <Page
        title="Commitments"
        description="What you promised people in your emails, Teams chats and meetings, found in what Vanimo is allowed to learn from. Mark them done, or let Vanimo draft the follow-up in your voice. Vanimo never sends."
      >
        {children}
      </Page>
    );

  if (error)
    return frame(
      <MessageBar intent="error">
        <MessageBarBody>{error}</MessageBarBody>
      </MessageBar>,
    );
  if (!ledger) return <PageSkeleton label="Loading your promises…" />;

  // A notice about the follow-up being edited sits with it; anything else goes above the list.
  const noticeInDraft = Boolean(draft && noticeFor === draft.id && ledger.items.some((c) => c.id === draft.id));
  const noticeBar = notice && (
    <MessageBar intent="info">
      <MessageBarBody>{notice}</MessageBarBody>
    </MessageBar>
  );

  const row = (c: Commitment) => {
    const open = c.status === "open";
    const Icon = c.channel === "email" ? Mail16Regular : c.channel === "chat" ? Chat16Regular : CalendarLtr16Regular;
    const snoozed = Boolean(c.snoozedUntil && new Date(c.snoozedUntil) > new Date());
    const when = bucket(c);
    return (
      <li key={c.id} className={styles.row}>
        <span className={styles.icon}>
          <Icon aria-hidden />
        </span>
        <div className={styles.main}>
          <div className={styles.titleLine}>
            <span className={styles.what}>{c.what}</span>
            {c.looksDoneAt && open && <Pill tone="success">Looks done</Pill>}
            {snoozed && open && <Pill>Snoozed</Pill>}
          </div>
          <p className={styles.quote}>“{c.sentence}”</p>
          <div className={styles.meta}>
            {c.channel === "meeting"
              ? `In a meeting with ${AUDIENCE[c.relationship] ?? c.relationship}`
              : `${CHANNEL[c.channel]} · to ${AUDIENCE[c.relationship] ?? c.relationship}`}
            {" · made "}
            <When iso={c.madeAt}>{rel(c.madeAt)}</When>
            {c.duePhrase ? ` · “${c.duePhrase}”` : ""}
            {snoozed && c.snoozedUntil ? ` · snoozed until ${day(c.snoozedUntil)}` : ""}
            {c.looksDoneAt && open ? ` · you wrote in the same thread on ${day(c.looksDoneAt)}` : ""}
            {!open && c.statusAt && (
              <>
                {" · "}
                {c.status === "done" ? "marked done" : "marked not a promise"} <When iso={c.statusAt}>{rel(c.statusAt)}</When>
              </>
            )}
          </div>
        </div>
        <div className={styles.side}>
          {open && c.dueAt && (
            <When iso={c.dueAt}>
              {when === "overdue" ? (
                <Pill tone="danger">Was due {rel(c.dueAt)}</Pill>
              ) : (
                <span className={mergeClasses(styles.due, when === "soon" && styles.dueSoon)}>Due {rel(c.dueAt)}</span>
              )}
            </When>
          )}
          {open ? (
            <div className={styles.actions}>
              {c.channel !== "meeting" && (
                <Menu>
                  <MenuTrigger disableButtonEnhancement>
                    <MenuButton size="small" disabled={busy}>
                      Draft a follow-up
                    </MenuButton>
                  </MenuTrigger>
                  <MenuPopover>
                    <MenuList>
                      {(Object.keys(FOLLOW_UP) as FollowUpKind[]).map((k) => (
                        <MenuItem key={k} onClick={() => (k === "done" ? void followUp(c, k) : setActive({ id: c.id, kind: k }))}>
                          {FOLLOW_UP[k]}
                        </MenuItem>
                      ))}
                    </MenuList>
                  </MenuPopover>
                </Menu>
              )}
              <Button size="small" appearance="subtle" icon={<Checkmark16Regular />} onClick={() => void decide(c, "done")}>
                Done
              </Button>
              <Tooltip content="Remind me tomorrow" relationship="label">
                <Button size="small" appearance="subtle" icon={<Snooze16Regular />} onClick={() => void decide(c, "snooze")} />
              </Tooltip>
              <Tooltip content="Not a promise" relationship="label">
                <Button size="small" appearance="subtle" icon={<Dismiss16Regular />} onClick={() => void decide(c, "dismiss")} />
              </Tooltip>
            </div>
          ) : (
            <div className={styles.actions}>
              <Button size="small" appearance="subtle" icon={<ArrowUndo16Regular />} onClick={() => void decide(c, "reopen")}>
                Reopen
              </Button>
            </div>
          )}
        </div>
        {active?.id === c.id && (
          <Rise visible appear>
            <div className={styles.extra}>
              <p className={styles.extraTitle}>{FOLLOW_UP[active.kind]}</p>
              <div className={styles.form}>
                <Field label={active.kind === "late" ? "New date (optional)" : "Next update by (optional)"} className={styles.field}>
                  <Input value={newDate} maxLength={40} placeholder="Monday, 21 Oct…" onChange={(_, d) => setNewDate(d.value)} />
                </Field>
                <Button
                  appearance={draft?.id === c.id ? "secondary" : "primary"}
                  disabled={busy}
                  onClick={() => void followUp(c, active.kind)}
                >
                  {busy ? "Drafting…" : "Draft it"}
                </Button>
                <Button appearance="subtle" onClick={() => setActive(null)}>Cancel</Button>
              </div>
            </div>
          </Rise>
        )}
        {draft?.id === c.id && (
          <Rise visible appear>
            <div className={styles.extraPlain} role="group" aria-label="Follow-up draft">
              <p className={styles.extraTitle}>Follow-up draft</p>
              <DraftView
                draft={draft.draft}
                text={text}
                onTextChange={setText}
                checks={checks}
                confirmed={confirmed}
                onConfirm={setConfirmed}
                actions={
                  <>
                    <Button appearance="primary" disabled={hasBlock(checks) && !confirmed} onClick={() => void copy(draft.draft)}>
                      Copy
                    </Button>
                    {draft.draft.channel === "chat" && prefill && (draft.draft.chatUsers?.length ?? 0) > 0 && (
                      <Button
                        disabled={hasBlock(checks) && !confirmed}
                        onClick={() => window.open(newChatLink((draft.draft.chatUsers ?? []).join(","), text), "_blank", "noreferrer")}
                      >
                        Open in Teams with this text
                      </Button>
                    )}
                    <Button onClick={() => void checkAgain(draft.draft)}>Check my edits</Button>
                    {draft.draft.channel !== "chat" && draft.draft.id && (
                      <Button disabled={hasBlock(checks) && !confirmed} onClick={() => void place(draft.draft)}>
                        Put in my Drafts folder
                      </Button>
                    )}
                    <Button appearance="subtle" onClick={() => setDraft(null)}>Close</Button>
                  </>
                }
              />
              {noticeInDraft && noticeBar}
            </div>
          </Rise>
        )}
      </li>
    );
  };

  const offline = ledger.label.startsWith("Offline");
  let body: ReactNode;
  if (ledger.items.length === 0) {
    body = (
      <EmptyState
        headingLevel={2}
        icon={<TaskListSquareLtr20Regular />}
        title={status === "open" ? "No open promises" : status === "done" ? "Nothing marked done yet" : "Nothing marked as not a promise"}
      >
        {status === "open"
          ? "Vanimo looks in what you sent: run Learning first, then new mail and chats are checked each time you open this page."
          : "Nothing here yet."}
      </EmptyState>
    );
  } else if (status === "open") {
    body = (
      <div className={styles.groups}>
        {GROUPS.map(([key, title]) => {
          const items = ledger.items.filter((c) => bucket(c) === key);
          return items.length ? (
            <section key={key} className={styles.group} aria-labelledby={`commitments-${key}`}>
              <h2 id={`commitments-${key}`} className={styles.groupTitle}>
                {title}
                <span className={styles.groupCount}>{items.length}</span>
              </h2>
              <ul className={styles.list}>{items.map(row)}</ul>
            </section>
          ) : null;
        })}
      </div>
    );
  } else {
    body = (
      <ul className={styles.list} aria-label={status === "done" ? "Done" : "Not promises"}>
        {ledger.items.map(row)}
      </ul>
    );
  }

  return frame(
    <>
      <div className={styles.toolbar}>
        <TabList
          size="small"
          appearance="subtle-circular"
          className={styles.segmented}
          aria-label="Show"
          selectedValue={status}
          onTabSelect={(_, d) => setStatus(d.value as typeof status)}
        >
          <Tab value="open">
            Open <span className={styles.tabCount}>{ledger.open}</span>
          </Tab>
          <Tab value="done">Done</Tab>
          <Tab value="dismissed">Not promises</Tab>
        </TabList>
        {scanNote && <StatusDot tone="success">{scanNote}</StatusDot>}
      </div>
      {!noticeInDraft && noticeBar}
      {body}
      <p className={styles.footer}>
        <StatusDot tone={offline ? "warning" : "neutral"}>{ledger.label}</StatusDot>
        <span>
          {ledger.overdue} overdue · {ledger.dueSoon} due in the next day · {ledger.capturedThisWeek} found this week
        </span>
        {ledger.precision !== null && (
          <span>{`${Math.round(ledger.precision * 100)}% of the ${ledger.decided} you decided on were real promises`}</span>
        )}
        {ledger.hidden > 0 && <span>{ledger.hidden} hidden because of a rule you added; they're being deleted.</span>}
      </p>
    </>,
  );
}
